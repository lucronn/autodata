"""Persist a normalized source bundle and its immutable raw artifacts."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from io import BytesIO
from typing import Any, Iterable

from .source_adapters import SourceArtifact
from .source_bundle import SourceBundle


def persist_source_bundle(
    bundle: SourceBundle,
    artifacts: Iterable[SourceArtifact],
    adapter_name: str = "source-connector",
) -> dict[str, Any]:
    """Store resources first, then atomically persist normalized records."""

    artifact_list = list(artifacts)
    store_source_artifacts(artifact_list)

    import psycopg
    from psycopg.types.json import Jsonb

    host, port_text = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
    conninfo = {
        "host": host,
        "port": int(port_text),
        "dbname": os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        "user": os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        "password": os.environ["AUTODATA_POSTGRES_PASSWORD"],
    }
    now = datetime.now(UTC).replace(microsecond=0)
    evidence_by_id = {item["evidence_id"]: item for item in bundle.evidence}
    artifact_by_hash = {artifact.content_sha256: artifact for artifact in artifact_list}

    with psycopg.connect(**conninfo) as connection:
        with connection.cursor() as cursor:
            snapshot_ids = _persist_snapshots(
                cursor, artifact_list, adapter_name, now, Jsonb
            )
            _persist_artifact_rows(cursor, artifact_list, snapshot_ids, bundle, now, Jsonb)
            _persist_extraction_evidence(
                cursor, artifact_list, snapshot_ids, evidence_by_id, bundle.status, now
            )
            if bundle.vehicle is None:
                connection.commit()
                return {"status": bundle.status, "source_artifacts": len(artifact_list), "quarantined": len(bundle.quarantined)}

            vehicle = bundle.vehicle
            vehicle_evidence = evidence_by_id[vehicle["evidence_id"]]
            vehicle_snapshot_id = snapshot_ids[vehicle_evidence["content_sha256"]]
            vehicle_id = _upsert_returning_id(
                cursor,
                """
                INSERT INTO vehicles
                    (vehicle_id, vehicle_key, make, model, model_year, region,
                     source_snapshot_id, source_watermark)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (vehicle_key)
                DO UPDATE SET source_snapshot_id = EXCLUDED.source_snapshot_id,
                              source_watermark = EXCLUDED.source_watermark,
                              updated_at = now()
                RETURNING vehicle_id
                """,
                (
                    _stable_uuid(f"vehicle:{vehicle['vehicle_key']}"),
                    vehicle["vehicle_key"],
                    vehicle["make"],
                    vehicle["model"],
                    vehicle["model_year"],
                    vehicle["region"],
                    vehicle_snapshot_id,
                    _source_version(artifact_by_hash[vehicle_evidence["content_sha256"]]),
                ),
            )

            model_ids: dict[str, str] = {}
            for model in bundle.models:
                model_evidence = evidence_by_id[model["evidence_id"]]
                model_id = _upsert_returning_id(
                    cursor,
                    """
                    INSERT INTO vehicle_models
                        (vehicle_model_id, vehicle_id, provider_model_id, name,
                         source_snapshot_id, evidence_locator, evidence_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (vehicle_id, provider_model_id, source_snapshot_id)
                    DO UPDATE SET name = EXCLUDED.name,
                                  evidence_locator = EXCLUDED.evidence_locator,
                                  evidence_confidence = EXCLUDED.evidence_confidence
                    RETURNING vehicle_model_id
                    """,
                    (
                        _stable_uuid(f"vehicle-model:{vehicle_id}:{model['model_key']}"),
                        vehicle_id,
                        model["provider_model_id"],
                        model["name"],
                        snapshot_ids[model_evidence["content_sha256"]],
                        model_evidence["locator"],
                        model_evidence["confidence"],
                    ),
                )
                model_ids[model["model_key"]] = model_id

            for powertrain in bundle.powertrains:
                powertrain_evidence = evidence_by_id[powertrain["evidence_id"]]
                model_id = model_ids.get(powertrain["model_key"])
                if model_id is None:
                    continue
                _upsert_returning_id(
                    cursor,
                    """
                    INSERT INTO powertrains
                        (powertrain_id, vehicle_model_id, provider_powertrain_id, name,
                         source_snapshot_id, evidence_locator, evidence_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (vehicle_model_id, provider_powertrain_id, source_snapshot_id)
                    DO UPDATE SET name = EXCLUDED.name,
                                  evidence_locator = EXCLUDED.evidence_locator,
                                  evidence_confidence = EXCLUDED.evidence_confidence
                    RETURNING powertrain_id
                    """,
                    (
                        _stable_uuid(f"powertrain:{model_id}:{powertrain['powertrain_key']}"),
                        model_id,
                        powertrain["provider_powertrain_id"],
                        powertrain["name"],
                        snapshot_ids[powertrain_evidence["content_sha256"]],
                        powertrain_evidence["locator"],
                        powertrain_evidence["confidence"],
                    ),
                )

            for part in bundle.parts:
                part_evidence = evidence_by_id[part["evidence_id"]]
                _upsert_returning_id(
                    cursor,
                    """
                    INSERT INTO inventory_parts
                        (inventory_part_id, vehicle_id, part_number, description, quantity,
                         price_minor, currency, price_status, source_snapshot_id,
                         evidence_locator, evidence_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (vehicle_id, part_number, source_snapshot_id)
                    DO UPDATE SET description = EXCLUDED.description,
                                  quantity = EXCLUDED.quantity,
                                  price_minor = EXCLUDED.price_minor,
                                  currency = EXCLUDED.currency,
                                  price_status = EXCLUDED.price_status,
                                  evidence_locator = EXCLUDED.evidence_locator,
                                  evidence_confidence = EXCLUDED.evidence_confidence
                    RETURNING inventory_part_id
                    """,
                    (
                        _stable_uuid(f"part:{vehicle_id}:{part['part_number']}:{part_evidence['content_sha256']}"),
                        vehicle_id,
                        part["part_number"],
                        str(part.get("description") or ""),
                        part.get("quantity"),
                        part.get("price_minor"),
                        part.get("currency"),
                        part["price_status"],
                        snapshot_ids[part_evidence["content_sha256"]],
                        part_evidence["locator"],
                        part_evidence["confidence"],
                    ),
                )

            for article in bundle.articles:
                article_evidence = evidence_by_id[article["evidence_id"]]
                _upsert_returning_id(
                    cursor,
                    """
                    INSERT INTO catalog_articles
                        (catalog_article_id, vehicle_id, article_id, bucket, title,
                         bulletin_number, release_date, sort_order, source_snapshot_id,
                         source_locator, evidence_locator, evidence_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (vehicle_id, article_id, source_snapshot_id, source_locator)
                    DO UPDATE SET bucket = EXCLUDED.bucket,
                                  title = EXCLUDED.title,
                                  bulletin_number = EXCLUDED.bulletin_number,
                                  release_date = EXCLUDED.release_date,
                                  sort_order = EXCLUDED.sort_order,
                                  evidence_locator = EXCLUDED.evidence_locator,
                                  evidence_confidence = EXCLUDED.evidence_confidence
                    RETURNING catalog_article_id
                    """,
                    (
                        _stable_uuid(
                            f"article:{vehicle_id}:{article['article_key']}:{article_evidence['content_sha256']}"
                        ),
                        vehicle_id,
                        article["article_id"],
                        article.get("bucket"),
                        article.get("title"),
                        article.get("bulletin_number"),
                        article.get("release_date"),
                        article.get("sort"),
                        snapshot_ids[article_evidence["content_sha256"]],
                        article_evidence["locator"],
                        article_evidence["locator"],
                        article_evidence["confidence"],
                    ),
                )
            connection.commit()
    return {
        "status": bundle.status,
        "vehicle_id": str(vehicle_id),
        "vehicle_key": vehicle["vehicle_key"],
        "source_artifacts": len(artifact_list),
        "models": len(bundle.models),
        "powertrains": len(bundle.powertrains),
        "parts": len(bundle.parts),
        "articles": len(bundle.articles),
        "documents": len(bundle.documents),
        "diagrams": len(bundle.diagrams),
        "evidence": len(bundle.evidence),
        "quarantined": len(bundle.quarantined),
    }


def store_source_artifacts(artifacts: Iterable[SourceArtifact]) -> None:
    from minio import Minio

    client = Minio(
        os.getenv("AUTODATA_S3_ENDPOINT", "minio:9000"),
        access_key=os.environ["AUTODATA_S3_ACCESS_KEY"],
        secret_key=os.environ["AUTODATA_S3_SECRET_KEY"],
        secure=False,
    )
    bucket = os.getenv("AUTODATA_SOURCE_BUCKET", "autodata-sources")
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    for artifact in artifacts:
        client.put_object(
            bucket,
            artifact.object_key,
            BytesIO(artifact.raw_payload),
            len(artifact.raw_payload),
            content_type=artifact.media_type,
        )


def _persist_snapshots(cursor: Any, artifacts: list[SourceArtifact], adapter_name: str, now: datetime, jsonb: Any) -> dict[str, str]:
    snapshot_ids: dict[str, str] = {}
    for artifact in artifacts:
        snapshot_id = _stable_uuid(f"source-snapshot:{artifact.content_sha256}")
        cursor.execute(
            """
            INSERT INTO source_snapshots
                (source_snapshot_id, adapter_name, source_uri, source_version,
                 content_sha256, object_key, license_metadata, retrieved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (content_sha256) DO NOTHING
            """,
            (
                snapshot_id,
                adapter_name,
                artifact.source_uri,
                artifact.source_version,
                artifact.content_sha256,
                artifact.object_key,
                jsonb({
                    "attribution": artifact.metadata.get("attribution"),
                    "redistribution_status": "unknown",
                }),
                now,
            ),
        )
        cursor.execute("SELECT source_snapshot_id FROM source_snapshots WHERE content_sha256 = %s", (artifact.content_sha256,))
        snapshot_ids[artifact.content_sha256] = str(cursor.fetchone()[0])
    return snapshot_ids


def _persist_artifact_rows(cursor: Any, artifacts: list[SourceArtifact], snapshot_ids: dict[str, str], bundle: SourceBundle, now: datetime, jsonb: Any) -> None:
    candidate_ready_hashes = {item["content_sha256"] for item in bundle.evidence}
    for artifact in artifacts:
        if artifact.kind == "quarantine":
            extraction_status = "quarantined"
        elif artifact.kind in {"document", "diagram"}:
            extraction_status = "complete"
        elif artifact.content_sha256 in candidate_ready_hashes:
            extraction_status = "candidate_ready"
        else:
            extraction_status = "needs_review"
        cursor.execute(
            """
            INSERT INTO source_artifacts
                (source_artifact_id, source_snapshot_id, artifact_kind, media_type,
                 content_sha256, object_key, metadata, extraction_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (content_sha256) DO UPDATE SET metadata = EXCLUDED.metadata,
                                                        extraction_status = EXCLUDED.extraction_status
            """,
            (
                _stable_uuid(f"source-artifact:{artifact.content_sha256}"),
                snapshot_ids[artifact.content_sha256],
                artifact.kind,
                artifact.media_type,
                artifact.content_sha256,
                artifact.object_key,
                jsonb(artifact.metadata),
                extraction_status,
            ),
        )


def _persist_extraction_evidence(
    cursor: Any,
    artifacts: list[SourceArtifact],
    snapshot_ids: dict[str, str],
    evidence_by_id: dict[str, dict[str, Any]],
    bundle_status: str,
    now: datetime,
) -> None:
    """Persist evidence with deterministic IDs so a source replay is idempotent."""

    artifact_by_hash = {artifact.content_sha256: artifact for artifact in artifacts}
    evidence_by_hash: dict[str, list[dict[str, Any]]] = {}
    for evidence in evidence_by_id.values():
        evidence_by_hash.setdefault(evidence["content_sha256"], []).append(evidence)

    for content_sha256, evidence_items in evidence_by_hash.items():
        extraction_run_id = _stable_uuid(f"extraction-run:{content_sha256}")
        status = "needs_review" if bundle_status == "needs_review" else "completed"
        cursor.execute(
            """
            INSERT INTO extraction_runs
                (extraction_run_id, source_snapshot_id, processor_name,
                 processor_version, status, confidence, input_hash,
                 started_at, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (extraction_run_id) DO UPDATE SET status = EXCLUDED.status,
                confidence = EXCLUDED.confidence, completed_at = EXCLUDED.completed_at
            """,
            (
                extraction_run_id,
                snapshot_ids[content_sha256],
                "universal-normalizer",
                "1",
                status,
                min(float(item["confidence"]) for item in evidence_items),
                content_sha256,
                now,
                now,
            ),
        )
        artifact = artifact_by_hash.get(content_sha256)
        if artifact is None:
            continue
        for evidence in evidence_items:
            cursor.execute(
                """
                INSERT INTO extraction_evidence
                    (extraction_evidence_id, source_snapshot_id, extraction_run_id,
                     locator, artifact_key, extracted_text, confidence, reviewer_state)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (extraction_evidence_id) DO UPDATE SET
                    locator = EXCLUDED.locator,
                    artifact_key = EXCLUDED.artifact_key,
                    extracted_text = EXCLUDED.extracted_text,
                    confidence = EXCLUDED.confidence,
                    reviewer_state = EXCLUDED.reviewer_state
                """,
                (
                    evidence["evidence_id"],
                    snapshot_ids[content_sha256],
                    extraction_run_id,
                    evidence["locator"],
                    artifact.object_key,
                    evidence["extracted_text"],
                    evidence["confidence"],
                    evidence["reviewer_state"],
                ),
            )


def _upsert_returning_id(cursor: Any, query: str, params: tuple[Any, ...]) -> str:
    cursor.execute(query, params)
    return str(cursor.fetchone()[0])


def _source_version(artifact: SourceArtifact) -> str:
    return artifact.source_version


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata-bundle:{value}"))
