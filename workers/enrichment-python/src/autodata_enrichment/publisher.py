"""Transactional deep-lane section publication for PostgreSQL."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .embeddings import embedding_provider_from_env, format_pgvector
from .section_lifecycle import (
    DeepSectionValidationError,
    deep_job_idempotency_key,
    evidence_input_hash,
    merge_revision_content,
    next_job_status,
    validate_evidence,
)


class DeepSectionError(RuntimeError):
    """A deep section could not be published without violating lifecycle rules."""


class EntitlementRevokedError(DeepSectionError):
    """The projection cannot receive new content after access revocation."""


def schedule_deep_sections(
    projection_id: str,
    section_names: tuple[str, ...],
    processing_version: str = "deep-v1",
) -> dict[str, Any]:
    """Fan out independent deep jobs and durable outbox requests for a projection."""

    if not section_names:
        raise DeepSectionError("at least one deep section is required")
    import psycopg
    from psycopg.types.json import Jsonb

    now = _timestamp()
    with psycopg.connect(**_connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            request_id, source_snapshot_id, request_status, entitlement_status, _, _ = _load_dataset(
                cursor, projection_id
            )
            if entitlement_status == "revoked" or request_status == "revoked":
                raise EntitlementRevokedError("entitlement or dataset request is revoked")
            if request_status not in {"viewable", "enriching", "needs_review", "complete"}:
                raise DeepSectionError(f"dataset request is not ready for deep enrichment: {request_status}")

            jobs = []
            for section_name in dict.fromkeys(section_names):
                idempotency_key = deep_job_idempotency_key(
                    source_snapshot_id, request_id, section_name, processing_version
                )
                job_id = _stable_uuid(f"deep-job:{idempotency_key}")
                cursor.execute(
                    """
                    INSERT INTO ingestion_jobs
                        (ingestion_job_id, dataset_request_id, source_snapshot_id,
                         lane, processing_version, idempotency_key, status,
                         attempt_count, checkpoint)
                    VALUES (%s, %s, %s, 'deep', %s, %s, 'pending', 0, %s)
                    ON CONFLICT (idempotency_key) DO UPDATE SET status =
                        CASE WHEN ingestion_jobs.status IN ('completed', 'dead_letter')
                             THEN ingestion_jobs.status ELSE 'pending' END,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        job_id,
                        request_id,
                        source_snapshot_id,
                        processing_version,
                        idempotency_key,
                        Jsonb({"section": section_name}),
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO dataset_section_status
                        (dataset_projection_id, section_name, status, updated_at)
                    VALUES (%s, %s, 'pending', %s)
                    ON CONFLICT (dataset_projection_id, section_name) DO UPDATE SET
                        status = CASE WHEN dataset_section_status.status IN ('complete', 'failed')
                                      THEN dataset_section_status.status ELSE 'pending' END,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (projection_id, section_name, now),
                )
                cursor.execute(
                    """
                    INSERT INTO publication_events
                        (event_type, event_version, dataset_request_id,
                         dataset_projection_id, correlation_id, idempotency_key,
                         payload, published_at, producer)
                    SELECT 'dataset.deep.requested', 1, dr.dataset_request_id,
                           %s, dr.correlation_id, %s, %s, %s, 'enrichment-worker'
                    FROM dataset_requests dr
                    WHERE dr.dataset_request_id = %s
                    ON CONFLICT (idempotency_key) DO NOTHING
                    """,
                    (
                        projection_id,
                        f"deep-request:{idempotency_key}",
                        Jsonb({
                            "section": section_name,
                            "processing_version": processing_version,
                            "source_snapshot_id": source_snapshot_id,
                        }),
                        now,
                        request_id,
                    ),
                )
                jobs.append({"section": section_name, "idempotency_key": idempotency_key})
            cursor.execute(
                """
                UPDATE dataset_requests
                SET status = CASE WHEN status = 'viewable' THEN 'enriching' ELSE status END,
                    updated_at = %s
                WHERE dataset_request_id = %s
                """,
                (now, request_id),
            )
        connection.commit()
    return {"status": "scheduled", "projection_id": projection_id, "jobs": jobs}


@dataclass(frozen=True)
class DeepSectionJob:
    projection_id: str
    section_name: str
    content: dict[str, Any]
    evidence: tuple[dict[str, Any], ...]
    processing_version: str = "deep-v1"

    def idempotency_key(self, source_snapshot_id: str, request_id: str) -> str:
        return deep_job_idempotency_key(
            source_snapshot_id,
            request_id,
            self.section_name,
            self.processing_version,
        )


def publish_deep_section(job: DeepSectionJob) -> dict[str, Any]:
    """Publish one section as a new immutable revision or return its prior result."""

    validate_evidence(job.evidence)
    import psycopg
    from psycopg.types.json import Jsonb

    now = _timestamp()
    embedding_provider = embedding_provider_from_env()
    with psycopg.connect(**_connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            dataset = _load_dataset(cursor, job.projection_id)
            request_id, source_snapshot_id, request_status, entitlement_status, source_version, source_hash = dataset
            if entitlement_status == "revoked" or request_status == "revoked":
                raise EntitlementRevokedError("entitlement or dataset request is revoked")
            if request_status not in {"viewable", "enriching", "needs_review", "complete"}:
                raise DeepSectionError(f"dataset request is not ready for deep enrichment: {request_status}")

            idempotency_key = job.idempotency_key(source_snapshot_id, request_id)
            existing = _existing_publication(cursor, idempotency_key)
            if existing is not None:
                connection.commit()
                return existing

            job_id = _stable_uuid(f"deep-job:{idempotency_key}")
            cursor.execute(
                """
                INSERT INTO ingestion_jobs
                    (ingestion_job_id, dataset_request_id, source_snapshot_id,
                     lane, processing_version, idempotency_key, status,
                     attempt_count, checkpoint)
                VALUES (%s, %s, %s, 'deep', %s, %s, 'processing', 1, %s)
                ON CONFLICT (idempotency_key) DO UPDATE SET status = 'processing',
                    updated_at = now()
                """,
                (
                    job_id,
                    request_id,
                    source_snapshot_id,
                    job.processing_version,
                    idempotency_key,
                    Jsonb({"section": job.section_name}),
                ),
            )
            cursor.execute(
                """
                INSERT INTO dataset_section_status
                    (dataset_projection_id, section_name, status, updated_at)
                VALUES (%s, %s, 'processing', %s)
                ON CONFLICT (dataset_projection_id, section_name)
                DO UPDATE SET status = 'processing', updated_at = EXCLUDED.updated_at
                """,
                (job.projection_id, job.section_name, now),
            )

            extraction_run_id = _stable_uuid(f"deep-extraction:{idempotency_key}")
            cursor.execute(
                """
                INSERT INTO extraction_runs
                    (extraction_run_id, ingestion_job_id, source_snapshot_id,
                     processor_name, processor_version, status, confidence,
                     input_hash, started_at, completed_at)
                VALUES (%s, %s, %s, 'deep-section-enricher', %s, 'completed', %s, %s, %s, %s)
                ON CONFLICT (extraction_run_id) DO UPDATE SET status = 'completed',
                    confidence = EXCLUDED.confidence, completed_at = EXCLUDED.completed_at
                """,
                (
                    extraction_run_id,
                    job_id,
                    source_snapshot_id,
                    job.processing_version,
                    min(float(item["confidence"]) for item in job.evidence),
                    evidence_input_hash(job.evidence),
                    now,
                    now,
                ),
            )
            evidence_ids = []
            for item in job.evidence:
                evidence_id = _stable_uuid(
                    f"deep-evidence:{idempotency_key}:{item['evidence_id']}"
                )
                evidence_ids.append(evidence_id)
                cursor.execute(
                    """
                    INSERT INTO extraction_evidence
                        (extraction_evidence_id, source_snapshot_id, extraction_run_id,
                         locator, artifact_key, extracted_text, confidence, reviewer_state, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'approved', %s::vector)
                    ON CONFLICT (extraction_evidence_id) DO UPDATE SET
                        locator = EXCLUDED.locator,
                        artifact_key = EXCLUDED.artifact_key,
                        extracted_text = EXCLUDED.extracted_text,
                        confidence = EXCLUDED.confidence,
                        reviewer_state = EXCLUDED.reviewer_state,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        evidence_id,
                        source_snapshot_id,
                        extraction_run_id,
                        item["locator"],
                        item.get("artifact_key", f"source-snapshot/{source_snapshot_id}"),
                        item["extracted_text"],
                        item["confidence"],
                        format_pgvector(embedding_provider.embed(item["extracted_text"])),
                    ),
                )

            prior_revision_id, prior_revision_number, prior_content = _load_latest_revision(
                cursor, job.projection_id
            )
            revision_number = prior_revision_number + 1
            revision_id = _stable_uuid(f"deep-revision:{idempotency_key}")
            published_section = dict(job.content)
            published_section["evidence_ids"] = evidence_ids
            content = merge_revision_content(prior_content, job.section_name, published_section)
            changelog = {
                "kind": "deep-lane-section-publication",
                "section": job.section_name,
                "source_snapshot_id": source_snapshot_id,
                "source_watermark": source_version,
                "processing_version": job.processing_version,
                "embedding_provider": embedding_provider.name,
                "embedding_version": embedding_provider.version,
                "prior_revision_id": prior_revision_id,
                "evidence_ids": evidence_ids,
            }
            cursor.execute(
                """
                INSERT INTO dataset_revisions
                    (dataset_revision_id, dataset_projection_id, revision_number,
                     availability, source_watermark, schema_version, changelog,
                     content, published_at)
                VALUES (%s, %s, %s, 'viewable', %s, 1, %s, %s, %s)
                ON CONFLICT (dataset_revision_id) DO NOTHING
                """,
                (
                    revision_id,
                    job.projection_id,
                    revision_number,
                    source_version,
                    Jsonb(changelog),
                    Jsonb(content),
                    now,
                ),
            )
            cursor.execute(
                """
                UPDATE extraction_evidence
                SET dataset_revision_id = %s
                WHERE extraction_run_id = %s
                """,
                (revision_id, extraction_run_id),
            )
            cursor.execute(
                """
                UPDATE dataset_section_status
                SET status = 'complete', last_published_revision_id = %s, updated_at = %s
                WHERE dataset_projection_id = %s AND section_name = %s
                """,
                (revision_id, now, job.projection_id, job.section_name),
            )
            cursor.execute(
                """
                UPDATE dataset_requests
                SET status = CASE WHEN status IN ('viewable', 'needs_review')
                                  THEN 'enriching' ELSE status END,
                    updated_at = %s
                WHERE dataset_request_id = %s
                """,
                (now, request_id),
            )
            cursor.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'completed', checkpoint = %s, updated_at = %s
                WHERE ingestion_job_id = %s
                """,
                (Jsonb({"section": job.section_name, "revision_id": revision_id}), now, job_id),
            )
            cursor.execute(
                """
                INSERT INTO publication_events
                    (event_type, event_version, dataset_request_id,
                     dataset_projection_id, dataset_revision_id, correlation_id,
                     idempotency_key, payload, published_at, producer)
                SELECT 'dataset.section.published', 1, dr.dataset_request_id,
                       %s, %s, dr.correlation_id, %s, %s, %s, 'enrichment-worker'
                FROM dataset_requests dr
                WHERE dr.dataset_request_id = %s
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    job.projection_id,
                    revision_id,
                    idempotency_key,
                    Jsonb({
                        "section": job.section_name,
                        "source_snapshot_id": source_snapshot_id,
                        "source_watermark": source_version,
                        "evidence_ids": evidence_ids,
                    }),
                    now,
                    request_id,
                ),
            )
        connection.commit()
    return {
        "status": "published",
        "projection_id": job.projection_id,
        "revision_id": revision_id,
        "revision_number": revision_number,
        "section": job.section_name,
        "source_watermark": source_version,
        "evidence_ids": evidence_ids,
        "idempotency_key": idempotency_key,
    }


def record_deep_failure(
    projection_id: str,
    section_name: str,
    error_message: str,
    max_attempts: int = 3,
    processing_version: str = "deep-v1",
) -> dict[str, Any]:
    """Record an isolated failure and dead-letter only after bounded attempts."""

    import psycopg
    from psycopg.types.json import Jsonb

    now = _timestamp()
    with psycopg.connect(**_connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            request_id, source_snapshot_id, request_status, entitlement_status, _, _ = _load_dataset(
                cursor, projection_id
            )
            if entitlement_status == "revoked" or request_status == "revoked":
                raise EntitlementRevokedError("entitlement or dataset request is revoked")
            idempotency_key = deep_job_idempotency_key(
                source_snapshot_id, request_id, section_name, processing_version
            )
            cursor.execute(
                "SELECT ingestion_job_id::text, attempt_count FROM ingestion_jobs WHERE idempotency_key = %s FOR UPDATE",
                (idempotency_key,),
            )
            existing = cursor.fetchone()
            if existing is None:
                job_id, attempt_count = _stable_uuid(f"deep-job:{idempotency_key}"), 1
                job_status = next_job_status(attempt_count, max_attempts)
                cursor.execute(
                    """
                    INSERT INTO ingestion_jobs
                        (ingestion_job_id, dataset_request_id, source_snapshot_id,
                         lane, processing_version, idempotency_key, status,
                         attempt_count, last_error)
                    VALUES (%s, %s, %s, 'deep', %s, %s, %s, %s, %s)
                    """,
                    (
                        job_id,
                        request_id,
                        source_snapshot_id,
                        processing_version,
                        idempotency_key,
                        job_status,
                        attempt_count,
                        Jsonb({"message": error_message}),
                    ),
                )
            else:
                job_id, prior_attempt_count = existing
                attempt_count = int(prior_attempt_count) + 1
                job_status = next_job_status(attempt_count, max_attempts)
                cursor.execute(
                    """
                    UPDATE ingestion_jobs
                    SET status = %s, attempt_count = %s, last_error = %s, updated_at = %s
                    WHERE ingestion_job_id = %s
                    """,
                    (job_status, attempt_count, Jsonb({"message": error_message}), now, job_id),
                )
            cursor.execute(
                """
                INSERT INTO dataset_section_status
                    (dataset_projection_id, section_name, status, updated_at)
                VALUES (%s, %s, 'failed', %s)
                ON CONFLICT (dataset_projection_id, section_name)
                DO UPDATE SET status = 'failed', updated_at = EXCLUDED.updated_at
                """,
                (projection_id, section_name, now),
            )
            if request_status in {"viewable", "complete", "needs_review"}:
                cursor.execute(
                    "UPDATE dataset_requests SET status = 'enriching', updated_at = %s WHERE dataset_request_id = %s AND status <> 'revoked'",
                    (now, request_id),
                )
            failure_key = f"{idempotency_key}:failure:{attempt_count}"
            cursor.execute(
                """
                INSERT INTO publication_events
                    (event_type, event_version, dataset_request_id,
                     dataset_projection_id, correlation_id, idempotency_key,
                     payload, published_at, producer)
                SELECT 'dataset.enrichment.failed', 1, dr.dataset_request_id,
                       %s, dr.correlation_id, %s, %s, %s, 'enrichment-worker'
                FROM dataset_requests dr
                WHERE dr.dataset_request_id = %s
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    projection_id,
                    failure_key,
                    Jsonb({
                        "section": section_name,
                        "attempt_count": attempt_count,
                        "status": job_status,
                        "error": error_message,
                    }),
                    now,
                    request_id,
                ),
            )
        connection.commit()
    return {
        "status": job_status,
        "projection_id": projection_id,
        "section": section_name,
        "attempt_count": attempt_count,
        "idempotency_key": idempotency_key,
    }


def _load_dataset(cursor: Any, projection_id: str) -> tuple[str, str, str, str, str, str]:
    cursor.execute(
        """
        SELECT dr.dataset_request_id::text, dr.source_snapshot_id::text,
               dr.status, e.status, ss.source_version, ss.content_sha256
        FROM dataset_projections dp
        JOIN dataset_requests dr ON dr.dataset_request_id = dp.dataset_request_id
        JOIN entitlements e ON e.entitlement_id = dp.entitlement_id
        JOIN source_snapshots ss ON ss.source_snapshot_id = dr.source_snapshot_id
        WHERE dp.dataset_projection_id = %s
        FOR UPDATE OF dr, e
        """,
        (projection_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise DeepSectionError("dataset projection was not found")
    return tuple(row)  # type: ignore[return-value]


def _existing_publication(cursor: Any, idempotency_key: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT dataset_projection_id::text, dataset_revision_id::text,
               payload->>'section', payload->'evidence_ids',
               payload->>'source_watermark'
        FROM publication_events
        WHERE event_type = 'dataset.section.published' AND idempotency_key = %s
        """,
        (idempotency_key,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "status": "published",
        "projection_id": row[0],
        "revision_id": row[1],
        "section": row[2],
        "evidence_ids": row[3],
        "source_watermark": row[4],
        "idempotency_key": idempotency_key,
    }


def _load_latest_revision(cursor: Any, projection_id: str) -> tuple[str, int, dict[str, Any]]:
    cursor.execute(
        """
        SELECT dataset_revision_id::text, revision_number, content
        FROM dataset_revisions
        WHERE dataset_projection_id = %s AND published_at IS NOT NULL
        ORDER BY revision_number DESC
        LIMIT 1
        FOR UPDATE
        """,
        (projection_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise DeepSectionError("deep enrichment requires an existing viewable revision")
    content = row[2] if isinstance(row[2], dict) else json.loads(row[2])
    return str(row[0]), int(row[1]), content


def _connection_kwargs() -> dict[str, Any]:
    address = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432")
    host, separator, port = address.rpartition(":")
    if not separator:
        host, port = address, "5432"
    return {
        "host": host,
        "port": int(port),
        "dbname": os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        "user": os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        "password": os.environ["AUTODATA_POSTGRES_PASSWORD"],
    }


def _timestamp() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata-deep:{value}"))
