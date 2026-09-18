"""Durable, idempotent AutoAPItwo year-manifest warm-up."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from threading import Thread
from typing import Any

from .autoapitwo_catalog import AutoAPITwoCatalogConnector
from .catalog_sync import _claim, _conninfo, _finish
from .source_adapters import SourceResource, adapt_source_resource
from .bundle_persistence import (
    _persist_artifact_rows,
    _persist_snapshots,
    store_source_artifacts,
)
from .source_bundle import SourceBundle


DEFAULT_SOURCE_VERSION = "autoapitwo-fleet-v1"
DEFAULT_TRAVERSAL_VERSION = "year-manifest-v1"


def ensure_catalog_years(serialized_request: str) -> dict[str, object]:
    """Schedule one provider year-manifest fetch without blocking selectors."""

    request = json.loads(serialized_request or "{}")
    if not isinstance(request, dict):
        raise ValueError("catalog years request must be an object")
    source_version = str(
        request.get("source_version")
        or os.getenv("AUTODATA_AUTOAPITWO_CATALOG_SOURCE_VERSION", DEFAULT_SOURCE_VERSION)
    ).strip()
    if not source_version:
        raise ValueError("catalog years source version is required")

    sync = _claim(source_version, DEFAULT_TRAVERSAL_VERSION)
    result = {
        "provider": "autoapitwo",
        "source_version": source_version,
        "traversal_version": DEFAULT_TRAVERSAL_VERSION,
        "row_count": sync["row_count"],
    }
    if sync["status"] in {"completed", "running", "dead_letter"}:
        return {"status": sync["status"], **result}

    Thread(
        target=_run_claimed,
        args=(sync["id"], source_version),
        name="autoapitwo-year-manifest",
        daemon=True,
    ).start()
    return {"status": "scheduled", **result}


def _run_claimed(sync_id: str, source_version: str) -> None:
    base_url = os.getenv("AUTODATA_AUTOAPITWO_BASE_URL", "https://autoapitwo.vercel.app")
    try:
        connector = AutoAPITwoCatalogConnector(
            base_url,
            timeout=float(os.getenv("AUTODATA_AUTOAPITWO_TIMEOUT_SECONDS", "25")),
            retry_attempts=int(os.getenv("AUTODATA_AUTOAPITWO_RETRY_ATTEMPTS", "3")),
            retry_delay=float(os.getenv("AUTODATA_AUTOAPITWO_RETRY_DELAY_SECONDS", "0.25")),
        )
        result = persist_catalog_years(
            connector.fetch_years(),
            source_uri=f"{base_url.rstrip('/')}/api/v1/fleet/years",
            source_version=source_version,
        )
        _finish(
            sync_id,
            status="completed",
            row_count=int(result["year_count"]),
            checkpoint={"phase": "persisted", "year_count": result["year_count"]},
        )
    except Exception as error:  # noqa: BLE001 - persisted state is the recovery boundary
        _finish(
            sync_id,
            status="failed",
            row_count=0,
            checkpoint={"phase": "failed"},
            error=f"{type(error).__name__}: {error}"[:500],
        )


def persist_catalog_years(
    values: list[str | int],
    *,
    source_uri: str,
    source_version: str,
) -> dict[str, object]:
    """Persist a source-backed, de-duplicated year manifest."""

    years = sorted(
        {
            int(value)
            for value in values
            if str(value).strip().isdigit() and 1886 <= int(value) <= 2100
        }
    )
    if not years:
        raise ValueError("AutoAPItwo returned no valid catalog years")

    payload = json.dumps(
        [{"year": year} for year in years],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    resource = SourceResource.from_bytes(
        source_uri,
        source_version,
        payload,
        "application/json",
        metadata={"source_kind": "vehicle_catalog_year_manifest"},
    )
    artifact = adapt_source_resource(resource)
    store_source_artifacts([artifact])

    import psycopg
    from psycopg.types.json import Jsonb

    now = datetime.now(UTC).replace(microsecond=0)
    response_hash = resource.content_sha256
    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            snapshot_ids = _persist_snapshots(cursor, [artifact], "autoapitwo-catalog-years", now, Jsonb)
            _persist_artifact_rows(
                cursor,
                [artifact],
                snapshot_ids,
                SourceBundle(
                    status="ready",
                    vehicle=None,
                    specifications=(),
                    models=(),
                    powertrains=(),
                    parts=(),
                    articles=(),
                    documents=(),
                    diagrams=(),
                    evidence=(),
                    quarantined=(),
                    conflicts=(),
                ),
                now,
                Jsonb,
            )
            source_snapshot_id = snapshot_ids[resource.content_sha256]
            for year in years:
                cursor.execute(
                    """
                    INSERT INTO vehicle_catalog_years
                        (provider, source_version, year, source_uri, response_hash,
                         source_snapshot_id, fetched_at, updated_at)
                    VALUES ('autoapitwo', %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider, source_version, year) DO UPDATE
                    SET source_uri = EXCLUDED.source_uri,
                        response_hash = EXCLUDED.response_hash,
                        source_snapshot_id = EXCLUDED.source_snapshot_id,
                        fetched_at = EXCLUDED.fetched_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (source_version, year, source_uri, response_hash, source_snapshot_id, now, now),
                )
        connection.commit()
    return {
        "status": "persisted",
        "provider": "autoapitwo",
        "source_version": source_version,
        "source_uri": source_uri,
        "year_count": len(years),
        "min_year": years[0],
        "max_year": years[-1],
    }


__all__ = ["ensure_catalog_years", "persist_catalog_years"]
