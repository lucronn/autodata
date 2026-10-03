"""Durable, non-blocking AutoAPItwo vehicle catalog warm-up."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from threading import Thread
from typing import Any

from .autoapitwo_catalog import AutoAPITwoCatalogConnector


DEFAULT_SOURCE_VERSION = "autoapitwo-fleet-v1"
DEFAULT_TRAVERSAL_VERSION = "fleet-vocabulary-v1"
DEFAULT_MAX_ATTEMPTS = 3
# Fleet traversal is multi-hour. Heartbeats refresh updated_at per batch; stale
# reclaim must use that signal or a long-lived sync is wrongly abandoned.
_STALE_RUNNING_AFTER = timedelta(minutes=45)


def ensure_catalog_sync(serialized_request: str) -> dict[str, object]:
    """Claim one source/version sync and run it in a detached worker thread."""

    request = json.loads(serialized_request or "{}")
    if not isinstance(request, dict):
        raise ValueError("catalog sync request must be an object")
    source_version = str(
        request.get("source_version")
        or os.getenv("AUTODATA_AUTOAPITWO_CATALOG_SOURCE_VERSION", DEFAULT_SOURCE_VERSION)
    ).strip()
    traversal_version = str(
        request.get("traversal_version")
        or os.getenv("AUTODATA_AUTOAPITWO_CATALOG_TRAVERSAL_VERSION", DEFAULT_TRAVERSAL_VERSION)
    ).strip()
    if not source_version or not traversal_version:
        raise ValueError("catalog sync source and traversal versions are required")
    # Selector reads call ensure repeatedly. That call is the explicit replay
    # signal for dead_lettered fleet warmups that stopped mid-catalog.
    sync = _claim(source_version, traversal_version, force_replay=True)
    if sync["status"] in {"completed", "running"}:
        return {
            "status": sync["status"],
            "provider": "autoapitwo",
            "source_version": source_version,
            "traversal_version": traversal_version,
            "row_count": sync["row_count"],
        }
    if sync["status"] == "dead_letter":
        return {
            "status": sync["status"],
            "provider": "autoapitwo",
            "source_version": source_version,
            "traversal_version": traversal_version,
            "row_count": sync["row_count"],
        }
    Thread(
        target=_run_claimed,
        args=(sync["id"], source_version, traversal_version),
        name="autoapitwo-catalog-sync",
        daemon=True,
    ).start()
    return {
        "status": "scheduled",
        "provider": "autoapitwo",
        "source_version": source_version,
        "traversal_version": traversal_version,
        "row_count": sync["row_count"],
    }


def _run_claimed(sync_id: str, source_version: str, traversal_version: str) -> None:
    base_url = os.getenv("AUTODATA_AUTOAPITWO_BASE_URL", "https://autoapitwo.vercel.app")
    persisted = 0
    try:
        connector = AutoAPITwoCatalogConnector(
            base_url,
            timeout=float(os.getenv("AUTODATA_AUTOAPITWO_TIMEOUT_SECONDS", "25")),
            retry_attempts=int(os.getenv("AUTODATA_AUTOAPITWO_RETRY_ATTEMPTS", "3")),
            retry_delay=float(os.getenv("AUTODATA_AUTOAPITWO_RETRY_DELAY_SECONDS", "0.25")),
        )
        completed_keys = _completed_scope_keys(sync_id)
        resume_after_year = _resume_after_year(completed_keys)
        batch: list[dict[str, object]] = []
        for row in connector.iter_rows():
            year_text = str(row.get("year") or "").strip()
            try:
                year = int(year_text)
            except ValueError:
                year = 0
            if resume_after_year is not None and year and year < resume_after_year:
                continue
            scope_key = _scope_key(row)
            if scope_key in completed_keys:
                continue
            batch.append(row)
            if len(batch) >= 100:
                _persist_batch(sync_id, batch, source_version, base_url)
                persisted += len(batch)
                completed_keys.update(_scope_key(item) for item in batch)
                batch = []
        if batch:
            _persist_batch(sync_id, batch, source_version, base_url)
            persisted += len(batch)
        scope_count = _scope_count(sync_id)
        if scope_count == 0:
            raise RuntimeError("AutoAPItwo catalog returned no vehicle rows")
        _finish(
            sync_id,
            status="completed",
            row_count=scope_count,
            checkpoint={
                "phase": "persisted",
                "scope_count": scope_count,
                "persisted_this_run": persisted,
                "resume_after_year": resume_after_year,
            },
        )
    except Exception as error:  # noqa: BLE001 - persisted status is the recovery boundary
        scope_count = _scope_count(sync_id)
        _finish(
            sync_id,
            status="partial" if scope_count else "failed",
            row_count=scope_count,
            checkpoint={
                "phase": "partial" if scope_count else "failed",
                "scope_count": scope_count,
                "persisted_this_run": persisted,
            },
            error=f"{type(error).__name__}: {error}"[:500],
        )


def _scope_key(row: dict[str, object]) -> str:
    return ":".join(
        str(row.get(key, "")).strip()
        for key in ("year", "make", "model", "engine", "autoapitwo_vehicle_id")
    )


def _completed_scope_keys(sync_id: str) -> set[str]:
    import psycopg

    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT scope_key
                FROM vehicle_catalog_sync_scopes
                WHERE vehicle_catalog_sync_id = %s AND status = 'completed'
                """,
                (sync_id,),
            )
            return {str(row[0]) for row in cursor.fetchall()}


def _resume_after_year(completed_keys: set[str]) -> int | None:
    """Skip years fully behind the latest completed scope year.

    The newest year in the checkpoint may be partial, so only years strictly
    before that watermark are skipped. The watermark year is re-walked and
    filtered by completed scope keys.
    """

    years: list[int] = []
    for key in completed_keys:
        prefix = key.split(":", 1)[0]
        try:
            years.append(int(prefix))
        except ValueError:
            continue
    return max(years) if years else None


def _scope_count(sync_id: str) -> int:
    import psycopg

    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM vehicle_catalog_sync_scopes
                WHERE vehicle_catalog_sync_id = %s
                """,
                (sync_id,),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0


def _persist_batch(
    sync_id: str,
    rows: list[dict[str, object]],
    source_version: str,
    base_url: str,
) -> None:
    from .vehicle_selection_persistence import persist_vehicle_selection_list

    persist_vehicle_selection_list(
        rows,
        source_uri=f"{base_url.rstrip('/')}/api/v1/fleet/years",
        source_version=source_version,
        region=os.getenv("AUTODATA_SOURCE_REGION", "US"),
    )
    _record_scopes(sync_id, rows)


def _record_scopes(sync_id: str, rows: list[dict[str, object]]) -> None:
    import psycopg
    from psycopg.types.json import Jsonb

    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            for row in rows:
                scope_key = _scope_key(row)
                response_hash = hashlib.sha256(
                    json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()
                cursor.execute(
                    """
                    INSERT INTO vehicle_catalog_sync_scopes
                        (vehicle_catalog_sync_id, scope_key, status, attempt_count, response_hash, checkpoint)
                    VALUES (%s, %s, 'completed', 1, %s, %s)
                    ON CONFLICT (vehicle_catalog_sync_id, scope_key) DO UPDATE
                    SET status = 'completed', response_hash = EXCLUDED.response_hash,
                        checkpoint = EXCLUDED.checkpoint, updated_at = now()
                    """,
                    (
                        sync_id,
                        scope_key,
                        response_hash,
                        Jsonb({"phase": "persisted", "source_locator": row.get("source_locator")}),
                    ),
                )
            cursor.execute(
                """
                UPDATE vehicle_catalog_syncs
                SET row_count = (
                        SELECT count(*)
                        FROM vehicle_catalog_sync_scopes
                        WHERE vehicle_catalog_sync_id = %s
                    ),
                    checkpoint = jsonb_build_object('phase', 'persisting'),
                    updated_at = now(),
                    started_at = now()
                WHERE vehicle_catalog_sync_id = %s
                """,
                (sync_id, sync_id),
            )
        connection.commit()


def _conninfo() -> dict[str, Any]:
    host, port_text = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
    return {
        "host": host,
        "port": int(port_text),
        "dbname": os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        "user": os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        "password": os.environ["AUTODATA_POSTGRES_PASSWORD"],
    }


def _claim(
    source_version: str,
    traversal_version: str,
    *,
    force_replay: bool = False,
) -> dict[str, object]:
    import psycopg

    now = datetime.now(UTC).replace(microsecond=0)
    stale_before = now - _STALE_RUNNING_AFTER
    max_attempts = int(os.getenv("AUTODATA_AUTOAPITWO_CATALOG_MAX_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS)))
    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO vehicle_catalog_syncs
                    (provider, source_version, traversal_version, status)
                VALUES ('autoapitwo', %s, %s, 'pending')
                ON CONFLICT (provider, source_version, traversal_version) DO NOTHING
                """,
                (source_version, traversal_version),
            )
            cursor.execute(
                """
                SELECT vehicle_catalog_sync_id::text, status, attempt_count, row_count,
                       started_at, updated_at
                FROM vehicle_catalog_syncs
                WHERE provider = 'autoapitwo'
                  AND source_version = %s
                  AND traversal_version = %s
                FOR UPDATE
                """,
                (source_version, traversal_version),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("catalog sync state could not be created")
            sync_id, status, attempt_count, row_count, started_at, updated_at = row
            if status == "completed":
                connection.commit()
                return {"id": sync_id, "status": status, "row_count": row_count}
            heartbeat = updated_at or started_at
            if status == "running" and heartbeat and heartbeat > stale_before:
                connection.commit()
                return {"id": sync_id, "status": status, "row_count": row_count}
            if status == "dead_letter":
                if not force_replay:
                    connection.commit()
                    return {"id": sync_id, "status": status, "row_count": row_count}
                # Explicit ensure/replay resets the attempt budget and resumes.
                cursor.execute(
                    """
                    UPDATE vehicle_catalog_syncs
                    SET status = 'pending', attempt_count = 0, last_error = NULL, updated_at = now()
                    WHERE vehicle_catalog_sync_id = %s
                    """,
                    (sync_id,),
                )
                attempt_count = 0
                status = "pending"
            if attempt_count >= max_attempts:
                cursor.execute(
                    "UPDATE vehicle_catalog_syncs SET status = 'dead_letter', updated_at = now() WHERE vehicle_catalog_sync_id = %s",
                    (sync_id,),
                )
                connection.commit()
                return {"id": sync_id, "status": "dead_letter", "row_count": row_count}
            cursor.execute(
                """
                UPDATE vehicle_catalog_syncs
                SET status = 'running', attempt_count = attempt_count + 1,
                    started_at = %s, last_error = NULL, updated_at = now()
                WHERE vehicle_catalog_sync_id = %s
                """,
                (now, sync_id),
            )
            connection.commit()
            return {"id": sync_id, "status": "claimed", "row_count": row_count}


def _finish(
    sync_id: str,
    *,
    status: str,
    row_count: int,
    checkpoint: dict[str, object],
    error: str | None = None,
) -> None:
    import psycopg
    from psycopg.types.json import Jsonb

    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE vehicle_catalog_syncs
                SET status = %s, row_count = %s, checkpoint = %s,
                    last_error = %s,
                    completed_at = CASE WHEN %s = 'completed' THEN now() ELSE completed_at END,
                    updated_at = now()
                WHERE vehicle_catalog_sync_id = %s
                """,
                (status, row_count, Jsonb(checkpoint), error, status, sync_id),
            )
        connection.commit()


__all__ = ["ensure_catalog_sync"]
