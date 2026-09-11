"""Durable persistence for composed multi-component procedures."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
import uuid
from typing import Any, Mapping


DERIVED_ARTICLE_CONTRACT_VERSION = 3


def derived_article_identity(result: Mapping[str, Any]) -> tuple[str, str]:
    """Return the deterministic article ID and content fingerprint for a plan.

    The fingerprint intentionally includes only canonical, source-backed
    inputs.  It excludes timestamps, model-selected identifiers, and database
    generated UUIDs so a replay can find the same immutable revision.
    """

    derived = result.get("derived_article")
    if not isinstance(derived, Mapping) or not str(derived.get("article_id", "")).strip():
        raise ValueError("job plan does not contain a derived article identity")
    labor = result.get("labor", {})
    if not isinstance(labor, Mapping):
        labor = {}
    procedure = result.get("procedure", {})
    if not isinstance(procedure, Mapping):
        procedure = {}
    quote = result.get("quote", {})
    if not isinstance(quote, Mapping):
        quote = {}
    canonical_vehicle = result.get("canonical_vehicle") or result.get("vehicle") or {}
    if not isinstance(canonical_vehicle, Mapping):
        canonical_vehicle = {}
    source_watermarks = result.get("source_watermarks")
    if source_watermarks is None:
        source_watermarks = derived.get("source_watermarks")
    if source_watermarks is None and isinstance(result.get("source", {}), Mapping):
        source_watermarks = result.get("source", {}).get("source_watermark", [])
    if isinstance(source_watermarks, str):
        source_watermarks = [source_watermarks]
    if not isinstance(source_watermarks, (list, tuple, set)):
        source_watermarks = []
    visual_artifacts = result.get("visual_artifacts", derived.get("visual_artifacts", []))
    if not isinstance(visual_artifacts, list):
        visual_artifacts = []
    fingerprint_payload = {
        "article_id": str(derived["article_id"]),
        "canonical_vehicle": _canonical_vehicle(canonical_vehicle),
        "requested_components": sorted(
            str(value)
            for value in result.get("requested_components", derived.get("requested_components", []))
            if str(value).strip()
        ),
        "required_supporting_components": sorted(
            str(value)
            for value in result.get(
                "required_supporting_components", derived.get("required_supporting_components", [])
            )
            if str(value).strip()
        ),
        "recommended_supporting_components": sorted(
            str(value)
            for value in result.get(
                "recommended_supporting_components", derived.get("recommended_supporting_components", [])
            )
            if str(value).strip()
        ),
        "labor": _identity_labor(labor),
        "procedure": procedure,
        "images": result.get("images", []),
        "visual_artifacts": visual_artifacts,
        "source_article_ids": sorted(
            str(value)
            for value in result.get("selected_articles", derived.get("source_article_ids", []))
            if str(value).strip()
        ),
        "source_watermarks": sorted(
            str(value) for value in source_watermarks if str(value).strip()
        ),
        "quote_identity": result.get("quote_identity") or quote.get("quote_identity") or derived.get("quote_identity"),
        "procedure_revision": result.get("procedure_revision") or procedure.get("procedure_revision") or derived.get("procedure_revision"),
        "contract_version": DERIVED_ARTICLE_CONTRACT_VERSION,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return str(derived["article_id"]), fingerprint


def _canonical_vehicle(vehicle: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "vehicle_id",
        "vehicle_key",
        "year",
        "model_year",
        "make",
        "model",
        "region",
        "engine",
        "engine_displacement_l",
        "drivetrain",
        "trim",
    )
    return {
        key: vehicle[key]
        for key in keys
        if key in vehicle and vehicle[key] not in (None, "")
    }


def _identity_labor(labor: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "required_hours",
        "recommended_hours",
        "total_hours",
        "total_labor_hours",
        "overlap_hours_removed",
        "overlap_operations",
        "required_operations",
        "recommended_operations",
        "operations",
    )
    identity = {key: labor.get(key) for key in keys if key in labor}
    for key in ("required_operations", "recommended_operations", "operations"):
        if isinstance(identity.get(key), list):
            identity[key] = sorted(
                identity[key],
                key=lambda item: str(item.get("operation_id", "")) if isinstance(item, Mapping) else str(item),
            )
    return identity


def persist_derived_article(result: Mapping[str, Any], *, vehicle: Mapping[str, Any]) -> dict[str, Any]:
    """Insert or replay a composed article revision in PostgreSQL."""

    article_id, fingerprint = derived_article_identity(result)
    password = os.getenv("AUTODATA_POSTGRES_PASSWORD")
    if not password:
        return {"status": "skipped", "reason": "database_not_configured", "article_id": article_id}
    import psycopg
    from psycopg.types.json import Jsonb

    host, port_text = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
    conninfo = {
        "host": host,
        "port": int(port_text),
        "dbname": os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        "user": os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        "password": password,
    }
    canonical_vehicle = result.get("canonical_vehicle") or result.get("vehicle") or vehicle
    if not isinstance(canonical_vehicle, Mapping):
        canonical_vehicle = vehicle
    source_watermarks = result.get("source_watermarks") or result.get("derived_article", {}).get("source_watermarks", [])
    if isinstance(source_watermarks, str):
        source_watermarks = [source_watermarks]
    if not isinstance(source_watermarks, (list, tuple, set)):
        source_watermarks = []
    source_watermarks = sorted({str(value) for value in source_watermarks if str(value).strip()})
    source_watermark = ",".join(source_watermarks) or str(
        result.get("source", {}).get("source_version", "unknown")
        if isinstance(result.get("source", {}), Mapping)
        else "unknown"
    )
    procedure = result.get("procedure", {})
    if not isinstance(procedure, Mapping):
        procedure = {}
    quote = result.get("quote", {})
    if not isinstance(quote, Mapping):
        quote = {}
    labor = result.get("labor", {})
    if not isinstance(labor, Mapping):
        labor = {}
    visual_artifacts = result.get("visual_artifacts", [])
    if not isinstance(visual_artifacts, list):
        visual_artifacts = []
    vehicle_id = str(canonical_vehicle.get("vehicle_id", vehicle.get("vehicle_id", ""))).strip()
    with psycopg.connect(**conninfo) as connection:
        with connection.cursor() as cursor:
            if not _is_uuid(vehicle_id):
                cursor.execute(
                    "SELECT vehicle_id::text FROM vehicles WHERE vehicle_key = %s",
                    (_vehicle_key(vehicle),),
                )
                row = cursor.fetchone()
                vehicle_id = str(row[0]) if row else ""
            if not _is_uuid(vehicle_id):
                connection.commit()
                return {"status": "skipped", "reason": "vehicle_not_persisted", "article_id": article_id}
            derived_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata:derived-article:{article_id}"))
            now = datetime.now(UTC).replace(microsecond=0)
            cursor.execute(
                """
                INSERT INTO derived_articles
                    (derived_article_id, article_id, vehicle_id, title,
                     current_revision_number, current_status, creating_job_plan_id,
                     created_at, updated_at)
                VALUES (%s, %s, %s, %s, 0, %s, %s, %s, %s)
                ON CONFLICT (article_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    current_status = EXCLUDED.current_status,
                    updated_at = EXCLUDED.updated_at
                RETURNING derived_article_id::text
                """,
                (
                    derived_id,
                    article_id,
                    vehicle_id,
                    str(procedure.get("title") or article_id),
                    str(result.get("status", "needs_review")),
                    str(result.get("job_plan_id", "")) or None,
                    now,
                    now,
                ),
            )
            derived_id = str(cursor.fetchone()[0])
            cursor.execute(
                "SELECT derived_article_revision_id::text, revision_number FROM derived_article_revisions WHERE derived_article_id = %s AND normalized_fingerprint = %s",
                (derived_id, fingerprint),
            )
            existing = cursor.fetchone()
            if existing is not None:
                connection.commit()
                return {"status": "replayed", "article_id": article_id, "derived_article_id": derived_id, "revision_id": str(existing[0]), "revision_number": int(existing[1]), "fingerprint": fingerprint}
            cursor.execute(
                "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM derived_article_revisions WHERE derived_article_id = %s",
                (derived_id,),
            )
            revision_number = int(cursor.fetchone()[0])
            revision_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata:derived-revision:{article_id}:{fingerprint}"))
            procedure = result.get("procedure", {})
            cursor.execute(
                """
                INSERT INTO derived_article_revisions
                    (derived_article_revision_id, derived_article_id, revision_number,
                     normalized_fingerprint, source_watermark, body, steps, labor,
                     images, provenance, model, contract_version, status, published_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    revision_id,
                    derived_id,
                    revision_number,
                    fingerprint,
                    source_watermark,
                    str(procedure.get("title") or article_id),
                    Jsonb(procedure.get("steps", [])),
                    Jsonb(result.get("labor", {})),
                    Jsonb(result.get("images", [])),
                    Jsonb({
                        "article_ids": sorted(
                            str(value)
                            for value in result.get("selected_articles", [])
                            if str(value).strip()
                        ),
                        "evidence_ids": _evidence_ids(result),
                        "requested_components": sorted(
                            str(value)
                            for value in result.get("requested_components", [])
                            if str(value).strip()
                        ),
                        "required_supporting_components": sorted(
                            str(value)
                            for value in result.get("required_supporting_components", [])
                            if str(value).strip()
                        ),
                        "recommended_supporting_components": sorted(
                            str(value)
                            for value in result.get("recommended_supporting_components", [])
                            if str(value).strip()
                        ),
                        "canonical_vehicle": _canonical_vehicle(canonical_vehicle),
                        "source_watermarks": source_watermarks,
                        "quote_identity": result.get("quote_identity") or quote.get("quote_identity"),
                        "procedure_revision": result.get("procedure_revision") or procedure.get("procedure_revision"),
                        "required_operations": labor.get("required_operations", []),
                        "recommended_operations": labor.get("recommended_operations", []),
                        "visual_artifacts": visual_artifacts,
                    }),
                    str(
                        procedure.get("generation")
                        or result.get("llm_status")
                        or "deterministic"
                    ),
                    DERIVED_ARTICLE_CONTRACT_VERSION,
                    str(result.get("status", "needs_review")),
                    now if result.get("status") == "ready" else None,
                ),
            )
            for source_article_id in result.get("selected_articles", []):
                cursor.execute(
                    """
                    INSERT INTO derived_article_lineage
                        (derived_article_lineage_id, derived_article_revision_id,
                         source_article_identifier, lineage_role)
                    VALUES (%s, %s, %s, 'article')
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        str(uuid.uuid5(uuid.NAMESPACE_URL, f"lineage:{revision_id}:article:{source_article_id}")),
                        revision_id,
                        str(source_article_id),
                    ),
                )
            for evidence_id in _evidence_ids(result):
                if not _is_uuid(evidence_id):
                    continue
                cursor.execute(
                    """
                    INSERT INTO derived_article_lineage
                        (derived_article_lineage_id, derived_article_revision_id,
                         source_article_identifier, extraction_evidence_id, lineage_role)
                    VALUES (%s, %s, %s, %s, 'evidence')
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        str(uuid.uuid5(uuid.NAMESPACE_URL, f"lineage:{revision_id}:evidence:{evidence_id}")),
                        revision_id,
                        evidence_id,
                        evidence_id,
                    ),
                )
            for visual_key in _visual_lineage_keys(visual_artifacts):
                cursor.execute(
                    """
                    INSERT INTO derived_article_lineage
                        (derived_article_lineage_id, derived_article_revision_id,
                         source_article_identifier, lineage_role)
                    VALUES (%s, %s, %s, 'image')
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        str(uuid.uuid5(uuid.NAMESPACE_URL, f"lineage:{revision_id}:image:{visual_key}")),
                        revision_id,
                        visual_key,
                    ),
                )
            cursor.execute(
                "UPDATE derived_articles SET current_revision_number = %s, current_status = %s, updated_at = %s WHERE derived_article_id = %s",
                (revision_number, str(result.get("status", "needs_review")), now, derived_id),
            )
        connection.commit()
    return {"status": "persisted", "article_id": article_id, "derived_article_id": derived_id, "revision_id": revision_id, "revision_number": revision_number, "fingerprint": fingerprint}


def _evidence_ids(result: Mapping[str, Any]) -> list[str]:
    evidence_ids: set[str] = set()
    labor = result.get("labor", {})
    if isinstance(labor, Mapping):
        for operation in labor.get("operations", []):
            if isinstance(operation, Mapping):
                evidence_ids.update(
                    str(value) for value in operation.get("evidence_ids", []) if str(value).strip()
                )
    procedure = result.get("procedure", {})
    if isinstance(procedure, Mapping):
        for step in procedure.get("steps", []):
            if isinstance(step, Mapping):
                evidence_ids.update(
                    str(value) for value in step.get("evidence_ids", []) if str(value).strip()
                )
        for warning in procedure.get("warnings", []):
            if isinstance(warning, Mapping):
                evidence_ids.update(
                    str(value) for value in warning.get("evidence_ids", []) if str(value).strip()
                )
    quote = result.get("quote", {})
    if isinstance(quote, Mapping):
        evidence_ids.update(
            str(value) for value in quote.get("evidence_ids", []) if str(value).strip()
        )
    evidence_ids.update(
        str(value) for value in result.get("evidence_ids", []) if str(value).strip()
    )
    return sorted(evidence_ids)


def _visual_lineage_keys(visual_artifacts: list[Any]) -> list[str]:
    keys: set[str] = set()
    for artifact in visual_artifacts:
        if not isinstance(artifact, Mapping):
            continue
        key = str(
            artifact.get("source_artifact_key")
            or artifact.get("derived_artifact_key")
            or artifact.get("source_object_key")
            or ""
        ).strip()
        if key:
            keys.add(key)
    return sorted(keys)


def _vehicle_key(vehicle: Mapping[str, Any]) -> str:
    parts = [str(vehicle.get(key, "")).strip().casefold().replace(" ", "-") for key in ("make", "model")]
    parts.append(str(vehicle.get("year", vehicle.get("model_year", ""))))
    if vehicle.get("region"):
        parts.append(str(vehicle["region"]).strip().casefold())
    return "-".join(value for value in parts if value)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return True


__all__ = ["derived_article_identity", "persist_derived_article"]
