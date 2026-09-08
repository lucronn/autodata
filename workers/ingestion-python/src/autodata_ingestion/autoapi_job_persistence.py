"""Durable per-vehicle AutoAPI article-fetch job persistence."""

from __future__ import annotations

import os
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


_JOB_STATUSES = {"pending", "completed", "needs_review", "failed"}


def persist_autoapi_article_fetch_jobs(
    batches: Iterable[Any],
    results: Iterable[Mapping[str, Any]],
    *,
    selector_persistence: Mapping[str, Any] | None,
    source_version: str,
    adapter_name: str = "autoapi-local",
) -> dict[str, Any]:
    """Persist one replayable all-articles job for every planned vehicle.

    Selector persistence supplies the stable vehicle IDs and selector snapshot
    used to prove why each job exists. A bundle result then advances the same
    job to ``completed``, ``needs_review``, or ``failed``. The idempotency key
    includes the source version and location, so a later source refresh gets a
    new auditable job without duplicating a replay of the same drop.
    """

    batch_list = list(batches)
    result_by_vehicle = {str(item["vehicle_key"]): item for item in results}
    vehicle_ids = _vehicle_ids(selector_persistence)
    if not vehicle_ids:
        raise ValueError("selector persistence is required to create AutoAPI jobs")

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
    selector_snapshot_id = selector_persistence.get("source_snapshot_id")
    jobs: list[dict[str, Any]] = []
    with psycopg.connect(**conninfo) as connection:
        with connection.cursor() as cursor:
            for batch in batch_list:
                vehicle_key = str(batch.vehicle_key)
                vehicle_id = vehicle_ids.get(vehicle_key)
                if vehicle_id is None:
                    raise ValueError(f"selector persistence has no vehicle ID for {vehicle_key}")
                result = result_by_vehicle.get(vehicle_key, {"status": "failed", "error": "missing batch result"})
                status = _job_status(result.get("status"))
                source_location = (
                    str(Path(batch.source_directory))
                    if batch.source_directory is not None
                    else None
                )
                source_snapshot_id = _source_snapshot_id(result) or selector_snapshot_id
                idempotency_key = _idempotency_key(
                    adapter_name,
                    source_version,
                    vehicle_key,
                    source_location,
                )
                checkpoint = {
                    "vehicle_key": vehicle_key,
                    "source_location": source_location,
                    "result": dict(result),
                }
                last_error = (
                    {"message": str(result.get("error"))}
                    if result.get("error")
                    else None
                )
                cursor.execute(
                    """
                    INSERT INTO autoapi_article_fetch_jobs
                        (autoapi_article_fetch_job_id, vehicle_id, vehicle_key,
                         selector_source_snapshot_id, source_snapshot_id,
                         source_location, source_version, adapter_name,
                         idempotency_key, status, attempt_count, checkpoint,
                         last_error, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (idempotency_key)
                    DO UPDATE SET vehicle_id = EXCLUDED.vehicle_id,
                                  vehicle_key = EXCLUDED.vehicle_key,
                                  selector_source_snapshot_id = COALESCE(
                                      EXCLUDED.selector_source_snapshot_id,
                                      autoapi_article_fetch_jobs.selector_source_snapshot_id),
                                  source_snapshot_id = COALESCE(
                                      EXCLUDED.source_snapshot_id,
                                      autoapi_article_fetch_jobs.source_snapshot_id),
                                  status = EXCLUDED.status,
                                  checkpoint = EXCLUDED.checkpoint,
                                  last_error = EXCLUDED.last_error,
                                  updated_at = EXCLUDED.updated_at
                    """,
                    (
                        _stable_uuid(f"autoapi-article-fetch-job:{idempotency_key}"),
                        vehicle_id,
                        vehicle_key,
                        selector_snapshot_id,
                        source_snapshot_id,
                        source_location,
                        source_version,
                        adapter_name,
                        idempotency_key,
                        status,
                        1 if status != "pending" else 0,
                        Jsonb(checkpoint),
                        Jsonb(last_error) if last_error is not None else None,
                        now,
                        now,
                    ),
                )
                jobs.append(
                    {
                        "vehicle_key": vehicle_key,
                        "vehicle_id": vehicle_id,
                        "idempotency_key": idempotency_key,
                        "status": status,
                        "source_location": source_location,
                    }
                )
        connection.commit()
    return {"status": "persisted", "job_count": len(jobs), "jobs": jobs}


def _vehicle_ids(selector_persistence: Mapping[str, Any] | None) -> dict[str, str]:
    if selector_persistence is None:
        return {}
    return {
        str(item["vehicle_key"]): str(item["vehicle_id"])
        for item in selector_persistence.get("observations", [])
        if item.get("vehicle_key") and item.get("vehicle_id")
    }


def _source_snapshot_id(result: Mapping[str, Any]) -> str | None:
    persistence = result.get("persistence")
    if isinstance(persistence, Mapping) and persistence.get("source_snapshot_id"):
        return str(persistence["source_snapshot_id"])
    return None


def _job_status(value: Any) -> str:
    if value == "pending_source":
        return "pending"
    if value in _JOB_STATUSES:
        return str(value)
    return "failed"


def _idempotency_key(
    adapter_name: str,
    source_version: str,
    vehicle_key: str,
    source_location: str | None,
) -> str:
    raw = "|".join(
        (
            adapter_name,
            source_version,
            vehicle_key,
            source_location or "pending",
        )
    )
    return f"autoapi-article-fetch:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def _stable_uuid(value: str) -> str:
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))


__all__ = ["persist_autoapi_article_fetch_jobs"]
