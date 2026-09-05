"""Fast vehicle-scoped knowledge catalog reads from PostgreSQL."""

from __future__ import annotations

import os
from typing import Any

from .article_intake import VehicleTarget


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
               vc.engine_displacement_l
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
        WHERE v.vehicle_key = %s
          AND NOT EXISTS (
              SELECT 1
              FROM catalog_article_vehicle_links links
              WHERE links.duplicate_catalog_article_id = ca.catalog_article_id
          )
          AND ss.takedown_status = 'active'
        ORDER BY ca.title NULLS LAST, ca.article_id, ca.catalog_article_id
    """
    with psycopg.connect(**conninfo) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (target.vehicle_key,))
            rows = cursor.fetchall()
    return _rows_to_catalog(rows, target)


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
            "content_locator": source_locator or evidence_locator,
        }
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
                "evidence": [evidence],
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
                    "evidence": [evidence],
                }
            )
    return catalog


__all__ = ["load_vehicle_knowledge_catalog"]
