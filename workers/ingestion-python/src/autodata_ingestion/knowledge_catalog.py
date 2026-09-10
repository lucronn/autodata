"""Fast vehicle-scoped knowledge catalog reads from PostgreSQL."""

from __future__ import annotations

import os
from typing import Any

from .article_intake import VehicleTarget


DEFAULT_KNOWLEDGE_CACHE_LIMIT = 200
MAX_KNOWLEDGE_CACHE_LIMIT = 1000


def load_vehicle_knowledge_catalog(target: VehicleTarget) -> list[dict[str, Any]]:
    """Load non-duplicate normalized articles for one canonical vehicle key.

    This is deliberately a narrow indexed read. It does not scan all source
    text or perform semantic work; keyword ranking remains in the fallback
    module. A missing local database configuration returns an empty catalog so
    the caller can use its configured source resolver instead.
    """

    password = os.getenv("AUTODATA_POSTGRES_PASSWORD")
    if not password:
        return []
    try:
        import psycopg
    except ImportError:
        return []

    host, port_text = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
    conninfo = {
        "host": host,
        "port": int(port_text),
        "dbname": os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        "user": os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        "password": password,
    }
    query = """
        SELECT ca.catalog_article_id::text, ca.article_id, ca.bucket, ca.title,
               ca.bulletin_number, ca.release_date, ca.sort_order, ca.body,
               ca.steps, ca.source_snapshot_id::text, ca.source_locator,
               ca.evidence_locator, ca.evidence_confidence,
               ss.source_uri, ss.source_version,
               ee.extraction_evidence_id::text, ee.artifact_key,
               ee.extracted_text, ee.reviewer_state,
               v.make, v.model, v.model_year, v.region,
               vib.body_style, vib.drivetrain, vc.trim,
               vc.engine_displacement_l,
               ca.content_source_snapshot_id::text,
               ca.content_source_locator,
               ca.content_extraction_evidence_id::text,
               css.source_uri,
               css.source_version,
               cee.artifact_key,
               cee.extracted_text,
               cee.confidence,
               cee.reviewer_state,
               ca.images, ca.operations
        FROM catalog_articles ca
        JOIN vehicles v ON v.vehicle_id = ca.vehicle_id
        JOIN source_snapshots ss ON ss.source_snapshot_id = ca.source_snapshot_id
        JOIN extraction_evidence ee
          ON ee.source_snapshot_id = ca.source_snapshot_id
         AND ee.locator = ca.evidence_locator
        LEFT JOIN vehicle_configurations vc
          ON vc.vehicle_configuration_id = ca.vehicle_configuration_id
        LEFT JOIN vehicle_identity_bases vib
          ON vib.vehicle_identity_base_id = vc.vehicle_identity_base_id
          OR (ca.vehicle_configuration_id IS NULL AND vib.vehicle_id = ca.vehicle_id)
        LEFT JOIN source_snapshots css
          ON css.source_snapshot_id = ca.content_source_snapshot_id
        LEFT JOIN extraction_evidence cee
          ON cee.extraction_evidence_id = ca.content_extraction_evidence_id
        WHERE v.vehicle_key = %s
          AND NOT EXISTS (
              SELECT 1
              FROM catalog_article_vehicle_links links
              WHERE links.duplicate_catalog_article_id = ca.catalog_article_id
          )
          AND ss.takedown_status = 'active'
        ORDER BY ca.title NULLS LAST, ca.article_id, ca.catalog_article_id
        LIMIT %s
    """
    limit = _knowledge_cache_limit()
    with psycopg.connect(**conninfo) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (target.vehicle_key, limit))
            rows = cursor.fetchall()
            catalog = _rows_to_catalog(rows, target)
            if os.getenv("AUTODATA_DERIVED_ARTICLE_CACHE_ENABLED", "0") == "1":
                try:
                    cursor.execute(
                        """
                        SELECT da.article_id, da.title, dar.body, dar.steps,
                               dar.source_watermark, dar.status,
                               dar.derived_article_revision_id::text,
                               dar.provenance, dar.images, dar.labor,
                               dar.normalized_fingerprint
                        FROM derived_articles da
                        JOIN derived_article_revisions dar
                          ON dar.derived_article_id = da.derived_article_id
                         AND dar.revision_number = da.current_revision_number
                        JOIN vehicles v ON v.vehicle_id = da.vehicle_id
                        WHERE v.vehicle_key = %s
                          AND dar.status IN ('ready', 'needs_review')
                        ORDER BY dar.published_at DESC NULLS LAST, da.article_id
                        LIMIT %s
                        """,
                        (target.vehicle_key, limit),
                    )
                    catalog.extend(_derived_rows_to_catalog(cursor.fetchall(), target))
                except Exception:  # noqa: BLE001 - older databases lack the optional derived cache
                    pass
    return catalog


def _knowledge_cache_limit() -> int:
    raw_limit = os.getenv("AUTODATA_KNOWLEDGE_CACHE_MAX_RECORDS", "")
    if not raw_limit.strip():
        return DEFAULT_KNOWLEDGE_CACHE_LIMIT
    try:
        parsed = int(raw_limit)
    except ValueError:
        return DEFAULT_KNOWLEDGE_CACHE_LIMIT
    return max(1, min(parsed, MAX_KNOWLEDGE_CACHE_LIMIT))


def _rows_to_catalog(rows: list[tuple[Any, ...]], target: VehicleTarget) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 27:
            continue
        (
            catalog_article_id,
            article_id,
            bucket,
            title,
            bulletin_number,
            release_date,
            sort_order,
            body,
            steps,
            source_snapshot_id,
            source_locator,
            evidence_locator,
            evidence_confidence,
            source_uri,
            source_version,
            extraction_evidence_id,
            artifact_key,
            extracted_text,
            reviewer_state,
            make,
            model,
            model_year,
            region,
            body_style,
            drivetrain,
            trim,
            engine_displacement_l,
        ) = row[:27]
        content_values = list(row[27:]) + [None] * 9
        (
            content_source_snapshot_id,
            content_source_locator,
            content_extraction_evidence_id,
            content_source_uri,
            content_source_version,
            content_artifact_key,
            content_extracted_text,
            content_confidence,
            content_reviewer_state,
        ) = content_values[:9]
        # Keep compatibility with compact test/fallback rows that omit the
        # optional content-provenance join columns.
        images = row[36] if len(row) > 36 else row[27] if len(row) == 28 else []
        operations = row[37] if len(row) > 37 else row[28] if len(row) == 29 else []
        content_locator = content_source_locator or source_locator or evidence_locator or "catalog"
        content_uri = content_source_uri or source_uri
        content_version = content_source_version or source_version
        article = {
            "article_id": str(article_id),
            "article_key": f"catalog:{catalog_article_id}",
            "bucket": bucket,
            "title": title,
            "bulletin_number": bulletin_number,
            "release_date": release_date,
            "sort": sort_order,
            "body": body,
            "steps": steps,
            "source_uri": source_uri,
            "source_version": source_version,
            "content_locator": content_locator,
        }
        if images:
            article["images"] = images
        if operations:
            article["operations"] = operations
        article = {key: value for key, value in article.items() if value is not None}
        evidence_id = str(extraction_evidence_id)
        evidence = {
            "evidence_id": evidence_id,
            "source_snapshot_id": str(source_snapshot_id),
            "locator": source_locator or evidence_locator or "catalog",
            "artifact_key": artifact_key,
            "source_uri": source_uri,
            "source_version": source_version,
            "extracted_text": extracted_text,
            "confidence": float(evidence_confidence or 0),
            "reviewer_state": reviewer_state,
        }
        content_evidence = None
        if content_extraction_evidence_id and str(content_extraction_evidence_id) != evidence_id:
            content_evidence = {
                "evidence_id": str(content_extraction_evidence_id),
                "source_snapshot_id": str(content_source_snapshot_id),
                "locator": content_locator,
                "artifact_key": content_artifact_key,
                "source_uri": content_uri,
                "source_version": content_version,
                "extracted_text": content_extracted_text,
                "confidence": float(content_confidence or 0),
                "reviewer_state": content_reviewer_state,
            }
        evidence_items = [evidence]
        if content_evidence is not None:
            evidence_items.append(content_evidence)
        vehicle_identity = {
            "vehicle_key": target.vehicle_key,
            "make": make,
            "model": model,
            "year": model_year,
            "region": region,
            "body_style": body_style,
            "drivetrain": drivetrain,
            "trim": trim,
            "engine_displacement_l": engine_displacement_l,
        }
        vehicle_identity = {
            key: value for key, value in vehicle_identity.items() if value is not None
        }
        catalog.append(
            {
                "vehicle_key": target.vehicle_key,
                "vehicle_identity": vehicle_identity,
                "kind": "article",
                "article": article,
                "evidence": evidence_items,
            }
        )
        bucket_text = str(bucket or "").casefold()
        if steps or any(signal in bucket_text for signal in ("procedure", "repair", "maintenance")):
            catalog.append(
                {
                    "vehicle_key": target.vehicle_key,
                    "vehicle_identity": vehicle_identity,
                    "kind": "procedure",
                    "procedure": {
                        "procedure_id": f"procedure:{article_id}",
                        "section": "procedures",
                        "excerpt": str(body or "").strip(),
                        "matched_terms": [],
                    },
                    "evidence": evidence_items,
                }
            )
    return catalog


def _derived_rows_to_catalog(rows: list[tuple[Any, ...]], target: VehicleTarget) -> list[dict[str, Any]]:
    """Expose persisted combined procedures through the same search catalog."""

    catalog: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 9:
            continue
        article_id, title, body, steps, source_watermark, status, revision_id, provenance, images = row[:9]
        labor = row[9] if len(row) > 9 and isinstance(row[9], dict) else {}
        fingerprint = str(row[10]) if len(row) > 10 and row[10] else ""
        evidence_ids = []
        source_article_ids = []
        requested_components = []
        if isinstance(provenance, dict):
            evidence_ids = [str(value) for value in provenance.get("evidence_ids", [])]
            source_article_ids = [str(value) for value in provenance.get("article_ids", [])]
            requested_components = [str(value) for value in provenance.get("requested_components", [])]
        article = {
            "article_id": str(article_id),
            "article_key": f"derived:{revision_id}",
            "bucket": "composed procedure",
            "title": title,
            "body": body,
            "steps": steps or [],
            "images": images or [],
            "source_version": source_watermark,
            "status": status,
            "derived_revision_id": str(revision_id),
            "derived_components": requested_components,
            "source_article_ids": source_article_ids,
            "evidence_ids": evidence_ids,
            "labor": labor,
            "fingerprint": fingerprint,
            "procedure": {
                "title": title,
                "steps": steps or [],
                "warnings": [],
                "requires_review": status != "ready",
                "generation": "persisted_derived_article",
            },
        }
        evidence = [
            {
                "evidence_id": evidence_id,
                "locator": "derived-article-lineage",
                "source_version": source_watermark,
                "confidence": 1.0,
                "reviewer_state": status,
            }
            for evidence_id in evidence_ids
        ]
        catalog.append(
            {
                "vehicle_key": target.vehicle_key,
                "vehicle_identity": target.as_dict(),
                "kind": "article",
                "article": article,
                "evidence": evidence,
            }
        )
    return catalog


__all__ = ["load_vehicle_knowledge_catalog"]
