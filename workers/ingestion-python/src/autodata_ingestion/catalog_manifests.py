"""Durable provider-backed selector manifests for years, makes, and models.

Selector hydration resolves each index from the configured source connectors.
A make-only or model-only row is sparser than a canonical vehicle identity, so
it is recorded as a manifest entry rather than an identity fact: the manifest
lets the selector list every published value after one bounded hydration, and
keeps a later read database-only. Deeper traversal (configurations, articles)
still persists canonical identity rows through the existing boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from typing import Any, Iterable, Mapping


PROVIDER = "autodata"
SOURCE_VERSION = "catalog-selector-v1"

_YEARS_SQL = """
    INSERT INTO vehicle_catalog_years
        (provider, source_version, year, source_uri, response_hash, fetched_at, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (provider, source_version, year) DO UPDATE
    SET source_uri = EXCLUDED.source_uri,
        response_hash = EXCLUDED.response_hash,
        fetched_at = EXCLUDED.fetched_at,
        updated_at = EXCLUDED.updated_at
"""

_MAKES_SQL = """
    INSERT INTO vehicle_catalog_makes
        (provider, source_version, model_year, make, region, source_uri, response_hash,
         fetched_at, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (provider, source_version, model_year, make, region) DO UPDATE
    SET source_uri = EXCLUDED.source_uri,
        response_hash = EXCLUDED.response_hash,
        fetched_at = EXCLUDED.fetched_at,
        updated_at = EXCLUDED.updated_at
"""

_MODELS_SQL = """
    INSERT INTO vehicle_catalog_models
        (provider, source_version, model_year, make, model, region, source_uri, response_hash,
         fetched_at, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (provider, source_version, model_year, make, model, region) DO UPDATE
    SET source_uri = EXCLUDED.source_uri,
        response_hash = EXCLUDED.response_hash,
        fetched_at = EXCLUDED.fetched_at,
        updated_at = EXCLUDED.updated_at
"""


def persist_selector_manifest(
    scope: str,
    rows: Iterable[Mapping[str, Any]],
    *,
    region: str | None = None,
    provenance: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Record one resolved selector index so the picker reads it from the database."""

    if scope not in {"years", "makes", "models"}:
        return {"status": "not_applicable"}
    entries = _manifest_entries(scope, rows)
    if not entries:
        return {"status": "no_manifest_rows"}

    region_value = (str(region or "").strip() or os.getenv("AUTODATA_SOURCE_REGION", "US")).strip().upper()
    source_uri, source_version = _source_identity(provenance, scope)
    response_hash = sha256(
        json.dumps(entries, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    now = datetime.now(UTC).replace(microsecond=0)

    from .catalog_sync import _conninfo

    import psycopg

    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            for year, make, model in entries:
                if scope == "years":
                    cursor.execute(
                        _YEARS_SQL,
                        (PROVIDER, SOURCE_VERSION, year, source_uri, response_hash, now, now),
                    )
                elif scope == "makes":
                    cursor.execute(
                        _MAKES_SQL,
                        (PROVIDER, SOURCE_VERSION, year, make, region_value, source_uri, response_hash, now, now),
                    )
                else:
                    cursor.execute(
                        _MODELS_SQL,
                        (PROVIDER, SOURCE_VERSION, year, make, model, region_value, source_uri, response_hash, now, now),
                    )
        connection.commit()
    return {
        "status": "persisted",
        "scope": scope,
        "row_count": len(entries),
        "source_uri": source_uri,
        "source_version": source_version,
    }


def _manifest_entries(scope: str, rows: Iterable[Mapping[str, Any]]) -> list[tuple[int, str, str]]:
    """Keep only the fields the requested index publishes, de-duplicated."""

    entries: dict[tuple[int, str, str], None] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        year = row.get("year")
        if isinstance(year, bool) or not isinstance(year, int) or not 1886 <= year <= 2100:
            continue
        make = str(row.get("make") or "").strip() if scope in {"makes", "models"} else ""
        model = str(row.get("model") or "").strip() if scope == "models" else ""
        if scope in {"makes", "models"} and not make:
            continue
        if scope == "models" and not model:
            continue
        entries[(year, make, model)] = None
    return sorted(entries)


def _source_identity(provenance: Iterable[Mapping[str, Any]], scope: str) -> tuple[str, str]:
    for value in provenance:
        if not isinstance(value, Mapping):
            continue
        source_uri = str(value.get("source_uri") or value.get("uri") or "").strip()
        source_version = str(value.get("source_version") or "").strip()
        if source_uri:
            return source_uri, source_version or SOURCE_VERSION
    return f"autodata://catalog/{scope}", SOURCE_VERSION


__all__ = ["persist_selector_manifest"]
