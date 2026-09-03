"""Transactional fast-lane publication for an entitled dataset projection."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from .projection import build_viewable_content, required_sections_ready, viewable_sections
from .source_adapters import SourceArtifact
from .source_bundle import SourceBundle


class FastLanePersistenceError(RuntimeError):
    """A fast-lane request cannot be published without violating invariants."""


@dataclass(frozen=True)
class FastLanePublication:
    request_id: str
    projection_id: str
    correlation_id: str
    idempotency_key: str
    processing_version: str


def publish_fast_lane_revision(
    cursor: Any,
    bundle: SourceBundle,
    artifacts: Iterable[SourceArtifact],
    snapshot_ids: dict[str, str],
    vehicle_id: str,
    vehicle_snapshot_id: str,
    publication: FastLanePublication,
    now: datetime,
    jsonb: Any,
) -> dict[str, Any]:
    """Persist one immutable viewable revision or a durable review outcome.

    The caller must invoke this inside the same PostgreSQL transaction that
    persists the source snapshots, canonical rows, and extraction evidence.
    """

    artifact_list = list(artifacts)
    request = _load_entitled_request(cursor, publication)
    if bundle.vehicle is not None:
        if bundle.vehicle["vehicle_key"] != request["vehicle_key"]:
            raise FastLanePersistenceError("normalized vehicle does not match the requested vehicle")
        if bundle.vehicle["region"] != request["region"]:
            raise FastLanePersistenceError("normalized vehicle region does not match the requested region")
    job = _claim_job(cursor, publication, vehicle_snapshot_id, now, jsonb)
    if job["completed"]:
        return dict(job["result"])

    required = _json_list(request["minimum_sections"])
    available = viewable_sections(bundle, artifact_list)
    missing = sorted(set(required) - available)
    review_evidence = sorted(
        evidence["evidence_id"]
        for evidence in bundle.evidence
        if evidence.get("reviewer_state") != "approved"
    )
    if (
        bundle.status != "ready"
        or not required_sections_ready(available, required)
        or review_evidence
    ):
        cursor.execute(
            """
            UPDATE dataset_requests
            SET status = CASE WHEN status IN ('purchased', 'fast_lane_processing')
                              THEN 'needs_review' ELSE status END,
                source_snapshot_id = %s, vehicle_id = %s, updated_at = %s
            WHERE dataset_request_id = %s
            """,
            (vehicle_snapshot_id, vehicle_id, now, publication.request_id),
        )
        result = {
            "status": "needs_review",
            "published": False,
            "request_id": publication.request_id,
            "projection_id": publication.projection_id,
            "ingestion_job_id": job["job_id"],
            "missing_sections": missing,
            "review_evidence": review_evidence,
            "quarantined": len(bundle.quarantined),
            "conflicts": len(bundle.conflicts),
        }
        _complete_job(cursor, job["job_id"], result, now, jsonb)
        return result

    content = build_viewable_content(bundle, artifact_list)
    source_snapshot_ids = sorted(set(snapshot_ids.values()))
    source_watermark = _source_watermark(artifact_list)
    revision_id = _stable_uuid(f"fast-revision:{publication.idempotency_key}")
    cursor.execute(
        """
        INSERT INTO dataset_revisions
            (dataset_revision_id, dataset_projection_id, revision_number,
             availability, source_watermark, schema_version, changelog, content,
             published_at)
        VALUES (%s, %s, 1, 'viewable', %s, 1, %s, %s, %s)
        ON CONFLICT (dataset_projection_id, revision_number) DO NOTHING
        """,
        (
            revision_id,
            publication.projection_id,
            source_watermark,
            jsonb(
                {
                    "kind": "initial-fast-lane-publication",
                    "processing_version": publication.processing_version,
                    "idempotency_key": publication.idempotency_key,
                    "source_snapshot_ids": source_snapshot_ids,
                }
            ),
            jsonb(content),
            now,
        ),
    )
    cursor.execute(
        """
        SELECT dataset_revision_id::text
        FROM dataset_revisions
        WHERE dataset_projection_id = %s AND revision_number = 1
        """,
        (publication.projection_id,),
    )
    stored_revision_id = str(cursor.fetchone()[0])
    section_names = (set(required) | set(content)) & set(content)
    for section_name in sorted(section_names):
        cursor.execute(
            """
            INSERT INTO dataset_section_status
                (dataset_projection_id, section_name, status,
                 last_published_revision_id, updated_at)
            VALUES (%s, %s, 'viewable', %s, %s)
            ON CONFLICT (dataset_projection_id, section_name)
            DO UPDATE SET status = 'viewable',
                          last_published_revision_id = EXCLUDED.last_published_revision_id,
                          updated_at = EXCLUDED.updated_at
            """,
            (publication.projection_id, section_name, stored_revision_id, now),
        )
    for source_snapshot_id in source_snapshot_ids:
        cursor.execute(
            """
            UPDATE extraction_evidence
            SET dataset_revision_id = %s
            WHERE source_snapshot_id = %s AND dataset_revision_id IS NULL
            """,
            (stored_revision_id, source_snapshot_id),
        )
    cursor.execute(
        """
        UPDATE dataset_requests
        SET status = 'viewable', source_snapshot_id = %s,
            vehicle_id = %s, updated_at = %s
        WHERE dataset_request_id = %s AND status <> 'revoked'
        """,
        (vehicle_snapshot_id, vehicle_id, now, publication.request_id),
    )
    event_idempotency_key = f"viewable:{publication.request_id}:{publication.processing_version}"
    cursor.execute(
        """
        INSERT INTO publication_events
            (event_type, event_version, dataset_request_id,
             dataset_projection_id, dataset_revision_id, correlation_id,
             idempotency_key, payload, published_at, producer)
        VALUES ('dataset.viewable', 1, %s, %s, %s, %s, %s, %s, %s, 'ingestion-worker')
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        (
            publication.request_id,
            publication.projection_id,
            stored_revision_id,
            publication.correlation_id,
            event_idempotency_key,
            jsonb(
                {
                    "source_snapshot_ids": source_snapshot_ids,
                    "source_watermark": source_watermark,
                    "processing_version": publication.processing_version,
                }
            ),
            now,
        ),
    )
    result = {
        "status": "viewable",
        "published": True,
        "request_id": publication.request_id,
        "projection_id": publication.projection_id,
        "revision_id": stored_revision_id,
        "ingestion_job_id": job["job_id"],
        "source_watermark": source_watermark,
        "event_idempotency_key": event_idempotency_key,
    }
    _complete_job(cursor, job["job_id"], result, now, jsonb)
    return result


def _load_entitled_request(cursor: Any, publication: FastLanePublication) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT dr.status, dr.vehicle_key, dr.region,
               dp.dataset_projection_id::text, e.status, p.minimum_sections
        FROM dataset_requests dr
        JOIN dataset_projections dp ON dp.dataset_request_id = dr.dataset_request_id
        JOIN entitlements e ON e.entitlement_id = dp.entitlement_id
        JOIN dataset_products p ON p.dataset_product_id = dp.dataset_product_id
        WHERE dr.dataset_request_id = %s
          AND dp.dataset_projection_id = %s
        FOR UPDATE
        """,
        (publication.request_id, publication.projection_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise FastLanePersistenceError("fast-lane request or projection was not found")
    status, vehicle_key, region, projection_id, entitlement_status, minimum_sections = row
    if status == "revoked" or entitlement_status != "active":
        raise FastLanePersistenceError("fast-lane request entitlement is not active")
    return {
        "status": str(status),
        "vehicle_key": str(vehicle_key),
        "region": str(region),
        "projection_id": str(projection_id),
        "minimum_sections": minimum_sections,
    }


def _claim_job(
    cursor: Any,
    publication: FastLanePublication,
    source_snapshot_id: str,
    now: datetime,
    jsonb: Any,
) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT ingestion_job_id::text, status, checkpoint
        FROM ingestion_jobs
        WHERE idempotency_key = %s
        FOR UPDATE
        """,
        (publication.idempotency_key,),
    )
    row = cursor.fetchone()
    if row is not None:
        job_id, status, checkpoint = str(row[0]), str(row[1]), row[2]
        checkpoint = _json_object(checkpoint)
        if status == "completed":
            return {"job_id": job_id, "completed": True, "result": checkpoint.get("result", checkpoint)}
        if status == "dead_letter":
            raise FastLanePersistenceError("fast-lane job is dead-lettered and requires operator replay")
        cursor.execute(
            """
            UPDATE ingestion_jobs
            SET status = 'processing', attempt_count = attempt_count + 1, updated_at = %s
            WHERE ingestion_job_id = %s
            """,
            (now, job_id),
        )
        return {"job_id": job_id, "completed": False}

    job_id = _stable_uuid(f"fast-job:{publication.idempotency_key}")
    cursor.execute(
        """
        INSERT INTO ingestion_jobs
            (ingestion_job_id, dataset_request_id, source_snapshot_id,
             lane, processing_version, idempotency_key, status,
             attempt_count, checkpoint, created_at, updated_at)
        VALUES (%s, %s, %s, 'fast', %s, %s, 'processing', 1, %s, %s, %s)
        """,
        (
            job_id,
            publication.request_id,
            source_snapshot_id,
            publication.processing_version,
            publication.idempotency_key,
            jsonb({"lane": "fast"}),
            now,
            now,
        ),
    )
    return {"job_id": job_id, "completed": False}


def _complete_job(cursor: Any, job_id: str, result: dict[str, Any], now: datetime, jsonb: Any) -> None:
    cursor.execute(
        """
        UPDATE ingestion_jobs
        SET status = 'completed', checkpoint = %s, updated_at = %s
        WHERE ingestion_job_id = %s
        """,
        (jsonb({"result": result}), now, job_id),
    )


def _source_watermark(artifacts: list[SourceArtifact]) -> str:
    versions = sorted({artifact.source_version for artifact in artifacts})
    return ",".join(versions)


def _json_list(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata-fast-lane:{value}"))
