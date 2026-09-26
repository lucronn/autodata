"""Provider-neutral, cache-first catalog resolution."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import inspect
import json
import os
from copy import deepcopy
from threading import RLock
from typing import Any, Callable, Iterable, Mapping


@dataclass(frozen=True)
class CatalogRequest:
    year: int
    make: str
    model: str
    region: str = "US"
    engine: str | float | None = None
    trim: str | None = None
    scope: str = "catalog"

    def __post_init__(self) -> None:
        if int(self.year) < 1886 or int(self.year) > 2100:
            raise ValueError("catalog year is outside the supported range")
        for name in ("make", "model", "region"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"catalog {name} is required")


@dataclass(frozen=True)
class CatalogResult:
    rows: tuple[dict[str, Any], ...]
    complete: bool
    missing_scopes: tuple[str, ...] = ()
    provenance: tuple[dict[str, Any], ...] = ()
    cache_hit: bool = False


def canonical_catalog_id(row: Mapping[str, Any]) -> str:
    """Return a stable provider-neutral ID from canonical selector fields."""

    identity = {
        key: _canonical_value(row.get(key))
        for key in ("year", "make", "model", "region", "engine", "trim")
        if row.get(key) not in (None, "")
    }
    digest = sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"catalog:{digest[:24]}"


class CacheFirstCatalogService:
    """Resolve a catalog request from complete cache data before providers."""

    def __init__(
        self,
        *,
        cache_reader: Callable[[CatalogRequest], Mapping[str, Any] | None],
        providers: Iterable[Any],
        cache_writer: Callable[[CatalogResult], Any] | None = None,
    ):
        self._cache_reader = cache_reader
        self._providers = tuple(providers)
        self._cache_writer = cache_writer

    def resolve(self, request: CatalogRequest) -> CatalogResult:
        cached = self._cache_reader(request)
        if _is_complete(cached):
            result = _result_from_payload(cached, cache_hit=True)
            return result

        rows: list[dict[str, Any]] = []
        missing = set(_missing_scopes(cached))
        provenance: list[dict[str, Any]] = []
        complete = False
        if isinstance(cached, Mapping):
            rows.extend(_canonical_rows(cached.get("rows", cached.get("records", []))))
            provenance.extend(_provenance(cached.get("provenance", ())))

        for provider in self._providers:
            try:
                payload = _call_provider(provider, request)
            except Exception as error:  # noqa: BLE001 - one source may be unavailable while another is usable
                missing.add("provider")
                continue
            normalized_rows = _canonical_rows(payload.get("rows", payload.get("records", ())))
            rows = _merge_rows(rows, normalized_rows)
            provenance.extend(_provenance(payload.get("provenance", ())))
            missing.update(_missing_scopes(payload))
            if bool(payload.get("complete")) and not _missing_scopes(payload):
                complete = True
        if complete:
            missing.clear()

        result = CatalogResult(
            rows=tuple(rows),
            complete=complete,
            missing_scopes=tuple(sorted(missing)),
            provenance=tuple(_dedupe_provenance(provenance)),
        )
        if self._cache_writer is not None:
            self._cache_writer(result)
        return result


_HYDRATION_LOCK = RLock()
_HYDRATION_RESULTS: dict[str, dict[str, Any]] = {}


def ensure_catalog_hydration(serialized_request: str) -> dict[str, Any]:
    """Resolve one bounded catalog scope behind the internal HTTP boundary.

    The API supplies this route only after its durable read found a missing or
    incomplete scope. The idempotency key therefore represents the exact
    request scope and prevents repeated provider traversal while the worker
    process is alive. Tests and other callers can provide ``cache``; deployed
    workers use explicitly configured provider base URLs.
    """

    request = json.loads(serialized_request or "{}")
    if not isinstance(request, dict):
        raise ValueError("catalog hydration request must be an object")
    key = str(request.get("idempotency_key", "")).strip()
    if not key:
        raise ValueError("catalog hydration idempotency_key is required")
    scope = str(request.get("scope", "")).strip()
    if scope not in {"years", "makes", "models", "configurations", "articles", "article"}:
        raise ValueError("catalog hydration scope is invalid")

    with _HYDRATION_LOCK:
        previous = _HYDRATION_RESULTS.get(key)
        if previous is not None:
            return deepcopy(previous)

    cached = request.get("cache")
    if not isinstance(cached, Mapping):
        cached = {"complete": False, "missing_scopes": [scope], "rows": []}
    if _is_complete(cached):
        resolved = _result_from_payload(cached, cache_hit=True)
        result = {
            "status": "cache_hit",
            "hydration_key": key,
            "scope": scope,
            "complete": True,
            "missing_scopes": [],
            "rows": list(resolved.rows),
            "provenance": list(resolved.provenance),
        }
        with _HYDRATION_LOCK:
            _HYDRATION_RESULTS[key] = deepcopy(result)
        return result

    # Article detail is a selected, vehicle-scoped miss. Use the existing
    # targeted AutoAPI fetch so one article does not trigger a full catalog
    # traversal. The worker persists the raw source and normalized article
    # through the canonical bundle boundary before the API re-reads it.
    if scope == "article" and request.get("year") and request.get("make") and request.get("model"):
        from .article_intake import VehicleTarget
        from .worker import _load_autoapi_job_catalog

        vehicle = {
            "model_year": int(request["year"]),
            "year": int(request["year"]),
            "make": str(request["make"]),
            "model": str(request["model"]),
            "region": str(request.get("region") or "US"),
        }
        for key in ("trim", "engine"):
            if request.get(key) not in (None, ""):
                vehicle[key] = request[key]
        source_article_id = str(request.get("source_article_id") or "").strip()
        if source_article_id:
            vehicle["requested_article_id"] = source_article_id
        query = str(request.get("title") or source_article_id or request.get("article_id") or "").strip()
        target = VehicleTarget(
            vehicle["make"], vehicle["model"], vehicle["model_year"], vehicle["region"],
            vehicle.get("trim"), None,
        )
        records, metadata = _load_autoapi_job_catalog(vehicle, target, query=query)
        matched = [
            record for record in records
            if str(record.get("article", {}).get("article_id", "")) in {source_article_id, str(request.get("article_id", ""))}
            or str(record.get("article", {}).get("title", "")).casefold() == str(request.get("title", "")).casefold()
        ]
        result = {
            "status": "hydrated" if matched else "source_miss",
            "hydration_key": key,
            "scope": scope,
            "complete": bool(matched),
            "missing_scopes": [] if matched else [scope],
            "rows": matched,
            "metadata": metadata,
        }
        with _HYDRATION_LOCK:
            _HYDRATION_RESULTS[key] = deepcopy(result)
        return result

    # Article discovery is a vehicle-scoped index read. It must not enter the
    # provider-neutral selector dispatcher: providers that only expose a full
    # snapshot would otherwise make one selected vehicle walk every year,
    # make, model, and vehicle before the caller can see its article list.
    if scope == "articles":
        result = _hydrate_article_catalog(request, key)
        with _HYDRATION_LOCK:
            _HYDRATION_RESULTS[key] = deepcopy(result)
        return result

    providers = _configured_catalog_providers()
    if not providers:
        result = {
            "status": "accepted",
            "hydration_key": key,
            "scope": scope,
            "complete": False,
            "missing_scopes": [scope],
            "rows": [],
        }
    else:
        request_model = CatalogRequest(
            int(request.get("year", 2000)),
            str(request.get("make", "unknown")),
            str(request.get("model", "unknown")),
            str(request.get("region", "US")),
            request.get("engine"),
            request.get("trim"),
            scope,
        )
        service = CacheFirstCatalogService(
            cache_reader=lambda _request: cached,
            providers=providers,
        )
        resolved = service.resolve(request_model)
        persistence = _persist_resolved_catalog_rows(
            resolved.rows,
            scope=scope,
            provenance=resolved.provenance,
        )
        coverage = _persist_hydration_scope(request, resolved)
        result = {
            "status": "cache_hit" if resolved.cache_hit else "hydrated",
            "hydration_key": key,
            "scope": scope,
            "complete": resolved.complete,
            "missing_scopes": list(resolved.missing_scopes),
            "rows": list(resolved.rows),
            "provenance": list(resolved.provenance),
            "persistence": persistence,
            "coverage": coverage,
        }
    with _HYDRATION_LOCK:
        _HYDRATION_RESULTS[key] = deepcopy(result)
    return result


def _hydrate_article_catalog(request: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Persist one vehicle's article index without fetching article bodies."""

    base_url = os.getenv("AUTODATA_AUTOAPI_BASE_URL", "").strip()
    if not base_url:
        return {
            "status": "accepted",
            "hydration_key": key,
            "scope": "articles",
            "complete": False,
            "missing_scopes": ["articles"],
            "rows": [],
            "metadata": {"reason": "autoapi_not_configured"},
        }

    from .article_intake import VehicleTarget
    from .worker import _load_autoapi_job_catalog

    try:
        year = int(request["year"])
        make = str(request["make"]).strip()
        model = str(request["model"]).strip()
        region = str(request.get("region") or "US").strip()
        vehicle = {
            "model_year": year,
            "year": year,
            "make": make,
            "model": model,
            "region": region,
        }
        for field in ("trim", "engine", "drivetrain"):
            if request.get(field) not in (None, ""):
                vehicle[field] = request[field]
        target_engine = vehicle.get("engine")
        if isinstance(target_engine, str) and target_engine.strip():
            stripped_engine = target_engine.strip()
            try:
                float(stripped_engine)
            except ValueError:
                pass
            else:
                target_engine = f"{stripped_engine}L"
        target = VehicleTarget(
            make,
            model,
            year,
            region,
            vehicle.get("trim"),
            None,
            vehicle.get("drivetrain"),
            target_engine,
        )
        vehicle.update(target.as_dict())
        vehicle["model_year"] = year
        # An empty query is the important boundary: _load_autoapi_job_catalog
        # reads the index and persists list_only rows, but its selected-article
        # loop is entered only when a query selects one or more article IDs.
        records, metadata = _load_autoapi_job_catalog(vehicle, target, query="")
    except Exception as error:  # noqa: BLE001 - source failure is a retryable miss
        return {
            "status": "source_unavailable",
            "hydration_key": key,
            "scope": "articles",
            "complete": False,
            "missing_scopes": ["articles"],
            "rows": [],
            "metadata": {"reason": type(error).__name__},
        }

    rows = [dict(record) for record in records if isinstance(record, Mapping)]
    return {
        "status": "hydrated" if rows else "source_miss",
        "hydration_key": key,
        "scope": "articles",
        "complete": bool(rows),
        "missing_scopes": [] if rows else ["articles"],
        "rows": rows,
        "metadata": metadata if isinstance(metadata, Mapping) else {},
    }


def _persist_resolved_catalog_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    scope: str,
    provenance: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Write provider-neutral selector rows through the canonical identity store."""

    if os.getenv("AUTODATA_SOURCE_PERSIST", "1") != "1":
        return {"status": "disabled", "row_count": 0}
    persistable = [
        dict(row)
        for row in rows
        if all(row.get(key) not in (None, "") for key in ("year", "make", "model", "region"))
    ]
    if not persistable:
        return {"status": "no_persistable_rows", "row_count": 0}
    from .vehicle_selection_persistence import persist_vehicle_selection_list

    first = next(iter(provenance), {})
    source_uri = str(first.get("source_uri") or first.get("uri") or f"autodata://catalog/{scope}")
    source_version = str(first.get("source_version") or "catalog-hydration-v1")
    result = persist_vehicle_selection_list(
        persistable,
        source_uri=source_uri,
        source_version=source_version,
        region=str(persistable[0].get("region") or "US"),
    )
    return {"status": "persisted", "row_count": len(persistable), **result}


def _persist_hydration_scope(request: Mapping[str, Any], result: CatalogResult) -> dict[str, Any]:
    """Persist a durable completeness marker for a successful scoped read."""

    if not result.complete or not result.rows or os.getenv("AUTODATA_SOURCE_PERSIST", "1") != "1":
        return {"status": "not_complete"}
    from .catalog_sync import _conninfo

    scope = str(request.get("scope", "")).strip()
    year = int(request.get("year", 0))
    make = str(request.get("make", "")).strip()
    model = str(request.get("model", "")).strip()
    region = str(request.get("region", "US")).strip().upper()
    scope_key = "|".join((scope, str(year), make.casefold(), model.casefold(), region))
    import psycopg
    from psycopg.types.json import Jsonb

    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO vehicle_catalog_hydration_scopes
                    (scope_key, scope, model_year, make, model, region, provenance)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (scope_key) DO UPDATE
                SET provenance = EXCLUDED.provenance, updated_at = now()
                """,
                (scope_key, scope, year, make, model, region, Jsonb(list(result.provenance))),
            )
        connection.commit()
    return {"status": "persisted", "scope_key": scope_key}


def _configured_catalog_providers() -> tuple[Any, ...]:
    providers: list[Any] = []
    autoapi_base = os.getenv("AUTODATA_AUTOAPI_BASE_URL", "").strip()
    if autoapi_base:
        from .autoapi_connector import AutoAPIConnector

        providers.append(AutoAPIConnector(autoapi_base))
    autoapitwo_base = os.getenv("AUTODATA_AUTOAPITWO_BASE_URL", "").strip()
    if autoapitwo_base:
        from .autoapitwo_catalog import AutoAPITwoCatalogConnector

        providers.append(AutoAPITwoCatalogConnector(autoapitwo_base))
    return tuple(providers)


def _call_provider(provider: Any, request: CatalogRequest) -> Mapping[str, Any]:
    if request.scope == "articles":
        if callable(provider):
            result = provider(request)
        elif hasattr(provider, "resolve_catalog"):
            result = provider.resolve_catalog(request)
        elif hasattr(provider, "fetch_article_catalog"):
            result = _call_with_optional_request(provider.fetch_article_catalog, request)
        else:
            raise TypeError(
                "article catalog provider must expose a list-only article catalog method"
            )
    elif callable(provider):
        result = provider(request)
    elif hasattr(provider, "resolve_catalog"):
        result = provider.resolve_catalog(request)
    elif request.scope in {"makes", "models", "configurations"} and hasattr(provider, "fetch_catalog_scope"):
        result = provider.fetch_catalog_scope(request)
    elif hasattr(provider, "fetch_catalog_snapshot"):
        result = _call_with_optional_request(provider.fetch_catalog_snapshot, request)
    elif hasattr(provider, "fetch_catalog"):
        result = _call_with_optional_request(provider.fetch_catalog, request)
    else:
        raise TypeError("catalog provider must be callable or expose a catalog method")
    if hasattr(result, "to_provider_response"):
        result = result.to_provider_response()
    if not isinstance(result, Mapping):
        raise TypeError("catalog provider must return a mapping")
    return result


def _call_with_optional_request(method: Callable[..., Any], request: CatalogRequest) -> Any:
    parameters = inspect.signature(method).parameters
    return method() if not parameters else method(request)


def _is_complete(payload: Mapping[str, Any] | None) -> bool:
    return isinstance(payload, Mapping) and payload.get("complete") is True and not _missing_scopes(payload)


def _result_from_payload(payload: Mapping[str, Any], *, cache_hit: bool) -> CatalogResult:
    rows = tuple(_canonical_rows(payload.get("rows", payload.get("records", ()))))
    return CatalogResult(
        rows=rows,
        complete=True,
        provenance=tuple(_dedupe_provenance(_provenance(payload.get("provenance", ())))),
        cache_hit=cache_hit,
    )


def _canonical_rows(values: Any) -> list[dict[str, Any]]:
    if isinstance(values, Mapping):
        values = values.get("rows", values.get("records", ()))
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, Mapping)):
        return []
    rows: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        row = {
            key: value[key]
            for key in (
                "year", "make", "model", "region", "engine", "engine_label",
                "trim", "body_style", "drivetrain", "provider_mappings",
            )
            if value.get(key) not in (None, "")
        }
        if not {"year", "make", "model", "region"}.issubset(row):
            continue
        row["catalog_id"] = canonical_catalog_id(row)
        rows.append(row)
    return _merge_rows([], rows)


def _merge_rows(existing: list[dict[str, Any]], additions: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = [dict(row) for row in existing]
    by_id = {row["catalog_id"]: row for row in result if row.get("catalog_id")}
    for addition in additions:
        row = dict(addition)
        row["catalog_id"] = canonical_catalog_id(row)
        current = by_id.get(row["catalog_id"])
        if current is None:
            by_id[row["catalog_id"]] = row
            result.append(row)
        else:
            current.update({key: value for key, value in row.items() if value not in (None, "")})
    return result


def _missing_scopes(payload: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(payload, Mapping):
        return ()
    values = payload.get("missing_scopes", ())
    if isinstance(values, str):
        values = (values,)
    if not isinstance(values, Iterable):
        return ()
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _provenance(values: Any) -> list[dict[str, Any]]:
    if isinstance(values, Mapping):
        values = (values,)
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
        return []
    result = []
    for value in values:
        if isinstance(value, Mapping):
            result.append({key: value[key] for key in ("provider", "source_uri", "uri", "source_version", "content_sha256", "hash", "retrieved_at", "metadata") if key in value})
    return result


def _dedupe_provenance(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for value in values:
        key = (value.get("provider"), value.get("source_uri", value.get("uri")), value.get("content_sha256", value.get("hash")))
        if key not in seen:
            seen.add(key)
            result.append(dict(value))
    return result


def _canonical_value(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    return value


__all__ = [
    "CatalogRequest",
    "CatalogResult",
    "CacheFirstCatalogService",
    "canonical_catalog_id",
    "ensure_catalog_hydration",
]
