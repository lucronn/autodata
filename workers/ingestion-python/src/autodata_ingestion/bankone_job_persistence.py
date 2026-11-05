"""Durable per-vehicle Bankone article-fetch job persistence."""

from __future__ import annotations

import os
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping


_JOB_STATUSES = {"pending", "completed", "needs_review", "failed"}
_TERMINAL_JOB_STATUSES = {"completed", "needs_review", "dead_letter"}


def _binding_review(idempotency_key=None):
    result={"status":"needs_review","error_code":"ARTICLE_BINDING_REVIEW_REQUIRED"}
    if idempotency_key is not None:result["idempotency_key"]=idempotency_key
    return result


def persist_bankone_article_fetch_jobs(batches,results,*,selector_persistence,source_version,adapter_name="bankone-local",address=None):
    """Compatibility boundary. Historical bundle status cannot authorize new IO.

    New callers supply proven canonical IDs; unbound source drops require offline
    reviewed mapping and do not create or update either historical queue.
    """
    from uuid import UUID
    from .worker import ArticleRepository
    from .source_job_persistence import ensure_article_job
    from psycopg.rows import dict_row
    result_by_vehicle={str(item["vehicle_key"]):item for item in results}
    vehicles=_vehicle_ids(selector_persistence)
    planned=[]
    for batch in batches:
        result=result_by_vehicle.get(str(batch.vehicle_key),{})
        ids=result.get("canonical_article_ids")
        if not isinstance(ids,list) or not ids or str(batch.vehicle_key) not in vehicles:
            return {**_binding_review(),"job_count":0,"jobs":[]}
        try:
            planned.extend((UUID(str(identifier)),UUID(str(vehicles[str(batch.vehicle_key)]))) for identifier in ids)
        except (ValueError, TypeError, AttributeError):
            return {**_binding_review(),"job_count":0,"jobs":[]}
    repo=ArticleRepository(address=address) if address else ArticleRepository()
    rows=[]
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        for identifier,vehicle in planned:
            row=cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s AND vehicle_id=%s AND provider_slug='bankone'",(identifier,vehicle)).fetchone()
            if row is None:return {**_binding_review(),"job_count":0,"jobs":[]}
            rows.append(row)
    jobs=[]
    for row in rows:
        item=ensure_article_job(repo,row["canonical_article_id"],normalization_version=row["target_normalization_version"],rewrite_profile_version=row["target_rewrite_profile_version"])
        jobs.append({"job_id":str(item.job_id),"canonical_article_id":str(item.canonical_article_id),"status":item.state})
    return {"status":"scheduled","job_count":len(jobs),"jobs":jobs}


def claim_autoapi_article_fetch_job(idempotency_key,*,max_attempts=3):
    if not str(idempotency_key).strip():raise ValueError("AutoAPI job idempotency key is required")
    if not 1<=max_attempts<=3:raise ValueError("maximum AutoAPI job attempts must be between one and three")
    return _binding_review(idempotency_key)


def record_autoapi_article_fetch_success(idempotency_key,*,checkpoint=None):
    return _binding_review(idempotency_key)


def record_autoapi_article_fetch_failure(idempotency_key,error,*,max_attempts=3):
    if not str(error).strip():raise ValueError("AutoAPI job failure message is required")
    return _binding_review(idempotency_key)


def _vehicle_ids(selector_persistence: Mapping[str, Any] | None) -> dict[str, str]:
    if selector_persistence is None:
        return {}
    return {
        str(item["vehicle_key"]): str(item["vehicle_id"])
        for item in selector_persistence.get("observations", [])
        if item.get("vehicle_key") and item.get("vehicle_id")
    }


def _source_locations(batch: Any) -> list[str]:
    """Return a sorted, de-duplicated source-location set for a batch."""

    source_locations = getattr(batch, "article_source_locations", None)
    if callable(source_locations):
        return sorted({str(location) for location in source_locations()})
    directories = ()
    source_directory = getattr(batch, "source_directory", None)
    if source_directory is not None:
        directories = (source_directory,)
    return sorted({str(Path(directory)) for directory in directories})


def _connection(address: str | None = None) -> Any:
    import psycopg
    from autodata_ingestion.bundle_persistence import _resolve_database_address

    host, port_text = _resolve_database_address(address).rsplit(":", 1)
    return psycopg.connect(
        host=host,
        port=int(port_text),
        dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        password=os.getenv("AUTODATA_POSTGRES_PASSWORD", "local-dev-only"),
    )


def _jsonb(value: Any) -> Any:
    from psycopg.types.json import Jsonb

    return Jsonb(value)


def _job_result(
    job_id: Any,
    status: str,
    attempt_count: Any,
    checkpoint: Any,
    last_error: Any,
) -> dict[str, Any]:
    return {
        "status": str(status),
        "job_id": str(job_id),
        "attempt_count": int(attempt_count),
        "checkpoint": checkpoint,
        "last_error": last_error,
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


__all__ = [
    "claim_autoapi_article_fetch_job",
    "persist_bankone_article_fetch_jobs",
    "record_autoapi_article_fetch_failure",
    "record_autoapi_article_fetch_success",
]
