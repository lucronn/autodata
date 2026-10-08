"""Durable, non-blocking AutoAPItwo vehicle catalog warm-up."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from threading import Thread
from typing import Any, Iterator

from .source_connector_client import SourceConnectorClient, source_connector_registry


DEFAULT_SOURCE_VERSION = "autoapitwo-fleet-v1"  # Stable persisted job identity.
DEFAULT_TRAVERSAL_VERSION = "fleet-vocabulary-v1"
DEFAULT_MAX_ATTEMPTS = 3
_STALE_RUNNING_AFTER = timedelta(minutes=10)


def ensure_catalog_sync(serialized_request: str) -> dict[str, object]:
    """Claim one source/version sync and run it in a detached worker thread."""

    request = json.loads(serialized_request or "{}")
    if not isinstance(request, dict):
        raise ValueError("catalog sync request must be an object")
    source_version = str(
        request.get("source_version")
        or os.getenv("BANKTWO_CATALOG_SOURCE_VERSION", DEFAULT_SOURCE_VERSION)
    ).strip()
    traversal_version = str(
        request.get("traversal_version")
        or os.getenv("BANKTWO_CATALOG_TRAVERSAL_VERSION", DEFAULT_TRAVERSAL_VERSION)
    ).strip()
    if not source_version or not traversal_version:
        raise ValueError("catalog sync source and traversal versions are required")
    sync = _claim(source_version, traversal_version)
    if sync["status"] in {"completed", "running", "dead_letter"}:
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
    total = 0
    try:
        connector = source_connector_registry(include_defaults=True)["banktwo"]
        rows = _iter_catalog_rows(connector)
        source_uri = f"{connector.base_url}/v1/catalog/configurations"

        batch: list[dict[str, object]] = []
        batch_source_version = source_version
        batch_source_uri = source_uri
        for row in rows:
            row_source_version = str(row.get("source_revision") or source_version)
            row_source_uri = str(row.get("source_locator") or source_uri)
            if batch and (row_source_version != batch_source_version or row_source_uri != batch_source_uri):
                _persist_batch(sync_id, batch, batch_source_version, batch_source_uri)
                total += len(batch)
                batch = []
            batch_source_version = row_source_version
            batch_source_uri = row_source_uri
            batch.append(row)
            if len(batch) >= 100:
                _persist_batch(sync_id, batch, batch_source_version, batch_source_uri)
                total += len(batch)
                batch = []
        if batch:
            _persist_batch(sync_id, batch, batch_source_version, batch_source_uri)
            total += len(batch)
        if total == 0:
            raise RuntimeError("AutoAPItwo catalog returned no vehicle rows")
        _finish(
            sync_id,
            status="completed",
            row_count=total,
            checkpoint={"phase": "persisted", "scope_count": total},
        )
    except Exception as error:  # noqa: BLE001 - persisted status is the recovery boundary
        _finish(
            sync_id,
            status="partial" if total else "failed",
            row_count=total,
            checkpoint={"phase": "partial" if total else "failed", "scope_count": total},
            error=f"{type(error).__name__}: {error}"[:500],
        )


def _iter_catalog_rows(connector: SourceConnectorClient) -> Iterator[dict[str, object]]:
    """Read complete configuration pages and keep opaque refs separate from legacy IDs."""

    cursor: str | None = None
    seen: set[str] = set()
    for _ in range(10_000):
        page = connector.catalog("configurations", cursor=cursor)
        for item in page.body["items"]:
            if not all(item.get(key) not in (None, "") for key in ("year", "make", "model")):
                raise ValueError("source configuration lacks canonical vehicle fields")
            source_ref = item["opaque_ref"]
            row: dict[str, object] = {
                "year": item["year"],
                "make": item["make"],
                "model": item["model"],
                "region": item.get("region") or os.getenv("AUTODATA_SOURCE_REGION", "US"),
                "source_vehicle_ref": source_ref,
                "source_locator": page.source_locator or f"{connector.base_url}/v1/catalog/configurations",
                "source_revision": page.source_revision,
                "provider_mappings": [{
                    "provider": page.persisted_provider,
                    "entity_type": "car",
                    "provider_id": source_ref,
                    "provider_label": item["label"],
                }],
            }
            for key in ("engine", "drivetrain"):
                if item.get(key):
                    row[key] = item[key]
            if item.get("configuration"):
                row["engine_label"] = item["configuration"]
            yield row
        if page.complete:
            return
        cursor = page.next_cursor
        if cursor is None or cursor in seen:
            raise ValueError("source catalog pagination did not advance")
        seen.add(cursor)
    raise ValueError("source catalog exceeded pagination limit")


def _persist_batch(
    sync_id: str,
    rows: list[dict[str, object]],
    source_version: str,
    source_uri: str,
) -> None:
    from .vehicle_selection_persistence import persist_vehicle_selection_list

    # Keep the legacy source_version as the job/idempotency key; snapshots
    # for configured V1 sources use the revision and locator from that page.
    snapshot_version = str(rows[0].get("source_revision") or source_version)
    snapshot_uri = str(rows[0].get("source_locator") or source_uri)
    persist_vehicle_selection_list(
        rows,
        source_uri=snapshot_uri,
        source_version=snapshot_version,
        region=os.getenv("AUTODATA_SOURCE_REGION", "US"),
    )
    _record_scopes(sync_id, rows)


def _record_scopes(sync_id: str, rows: list[dict[str, object]]) -> None:
    import psycopg
    from psycopg.types.json import Jsonb

    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            for row in rows:
                scope_key = ":".join(
                    str(row.get(key, "")).strip()
                    for key in ("year", "make", "model", "engine")
                ) + ":" + str(row.get("source_vehicle_ref") or row.get("autoapitwo_vehicle_id") or "").strip()
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
                    updated_at = now()
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


def _claim(source_version: str, traversal_version: str) -> dict[str, object]:
    import psycopg

    now = datetime.now(UTC).replace(microsecond=0)
    stale_before = now - _STALE_RUNNING_AFTER
    max_attempts = int(os.getenv("BANKTWO_CATALOG_MAX_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS)))
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
                       started_at
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
            sync_id, status, attempt_count, row_count, started_at = row
            if status == "completed":
                connection.commit()
                return {"id": sync_id, "status": status, "row_count": row_count}
            if status == "running" and started_at and started_at > stale_before:
                connection.commit()
                return {"id": sync_id, "status": status, "row_count": row_count}
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
