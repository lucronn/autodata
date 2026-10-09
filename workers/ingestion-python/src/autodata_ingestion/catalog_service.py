"""Provider-neutral, cache-first catalog resolution."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import inspect
import json
import os
import re
import time
from copy import deepcopy
from threading import RLock
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import quote


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
            result = _result_from_payload(cached, cache_hit=True, scope=request.scope)
            return result

        rows: list[dict[str, Any]] = []
        missing = set(_missing_scopes(cached))
        provenance: list[dict[str, Any]] = []
        complete = False
        if isinstance(cached, Mapping):
            rows.extend(_canonical_rows(cached.get("rows", cached.get("records", [])), scope=request.scope))
            provenance.extend(_provenance(cached.get("provenance", ())))

        for provider in self._providers:
            try:
                payload = _call_provider(provider, request)
            except Exception as error:  # noqa: BLE001 - one source may be unavailable while another is usable
                missing.add("provider")
                continue
            normalized_rows = _canonical_rows(payload.get("rows", payload.get("records", ())), scope=request.scope)
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


class _ArticleCatalogProgress:
    """Publish throttled, durable progress for one vehicle article catalog."""

    _MIN_PUBLISH_INTERVAL_SECONDS = 0.5
    _MIN_PROCESSED_DELTA = 100

    def __init__(self, request: Mapping[str, Any]):
        self.request = request
        self.last_published = 0.0
        self.last_published_processed = 0
        self.last_state: tuple[Any, ...] | None = None

    def publish(self, payload: Mapping[str, Any], *, force: bool = False) -> None:
        phase = str(payload.get("phase") or "starting").strip() or "starting"
        processed = max(0, int(payload.get("processed_units") or 0))
        total = max(0, int(payload.get("total_units") or 0))
        title = str(payload.get("current_title") or "").strip()
        article_id = str(payload.get("current_article_id") or "").strip()
        detail = str(payload.get("detail") or "").strip()
        state = (phase, processed, total, title, article_id, detail)
        now = time.monotonic()
        if not force and state == self.last_state:
            return
        if (
            not force
            and now - self.last_published < self._MIN_PUBLISH_INTERVAL_SECONDS
            and processed - self.last_published_processed < self._MIN_PROCESSED_DELTA
        ):
            return
        _update_article_catalog_progress(
            self.request,
            status="running",
            phase=phase,
            processed_units=processed,
            total_units=total,
            current_article_id=article_id,
            current_title=title,
            detail=detail,
        )
        self.last_published = now
        self.last_published_processed = processed
        self.last_state = state

    def start(self) -> None:
        year = str(self.request.get("year") or "selected year")
        make = str(self.request.get("make") or "selected make")
        model = str(self.request.get("model") or "selected model")
        self.publish(
            {
                "phase": "resolving",
                "detail": f"Preparing the full article list for {year} {make} {model}…",
            },
            force=True,
        )

    def complete(self, records: Iterable[Mapping[str, Any]]) -> None:
        rows = [record for record in records if isinstance(record, Mapping)]
        total = len(rows)
        last = rows[-1].get("article", {}) if rows else {}
        if not isinstance(last, Mapping):
            last = {}
        _update_article_catalog_progress(
            self.request,
            status="completed",
            phase="complete",
            processed_units=total,
            total_units=total,
            current_article_id=str(last.get("article_id") or ""),
            current_title=str(last.get("title") or ""),
            detail=f"Catalog ready — {total:,} articles indexed.",
        )

    def failed(self, detail: str) -> None:
        _update_article_catalog_progress(
            self.request,
            status="failed",
            phase="failed",
            processed_units=0,
            total_units=0,
            detail=detail,
        )


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
        resolved = _result_from_payload(cached, cache_hit=True, scope=scope)
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
        primary_error = None
        try:
            records, metadata = _load_autoapi_job_catalog(vehicle, target, query=query)
            matched = [
                record for record in records
                if str(record.get("article", {}).get("article_id", "")) in {source_article_id, str(request.get("article_id", ""))}
                or str(record.get("article", {}).get("title", "")).casefold() == str(request.get("title", "")).casefold()
            ]
            if not matched:
                primary_error = RuntimeError("primary article detail was not found")
        except Exception as error:  # noqa: BLE001 - try the second source
            primary_error = error

        if primary_error is not None:
            try:
                matched, metadata = _load_autoapitwo_article_detail(request, vehicle)
            except Exception as fallback_error:  # noqa: BLE001 - source failure is a retryable miss
                result = {
                    "status": "source_unavailable",
                    "hydration_key": key,
                    "scope": scope,
                    "complete": False,
                    "missing_scopes": [scope],
                    "rows": [],
                    "metadata": {
                        "reason": type(fallback_error).__name__,
                        "primary_source_reason": type(primary_error).__name__,
                    },
                }
                with _HYDRATION_LOCK:
                    _HYDRATION_RESULTS[key] = deepcopy(result)
                return result
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


def _load_autoapitwo_article_detail(
    request: Mapping[str, Any], vehicle: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch one selected Banktwo article through the shared v1 contract."""

    from dataclasses import replace

    from .procedure_normalize import normalize_procedure_article
    from .procedure_images import localize_procedure_images
    from .source_adapters import adapt_source_resource
    from .source_bundle import normalize_source_bundle
    from .source_connector_client import source_connector_registry

    connector = source_connector_registry().get("banktwo")
    if connector is None:
        raise RuntimeError("Banktwo source connector is not configured")
    requested_source_id = str(request.get("source_article_id") or "").strip()
    source_vehicle_ref = _resolve_source_vehicle_ref(connector, request, vehicle)
    descriptor = _find_source_article(connector, source_vehicle_ref, request)
    resource_refs = [descriptor.get("resource_ref")]
    resource_refs.extend([descriptor.get("labor_resource_ref")])
    resource_refs.extend(descriptor.get("asset_resource_refs") or [])
    resources = []
    for resource_ref in resource_refs:
        if not resource_ref:
            continue
        resource = connector.read_resource(str(resource_ref)).to_source_resource()
        resources.append(resource)
    if not resources:
        raise RuntimeError("Banktwo article has no readable source resource")
    artifacts = [adapt_source_resource(resource) for resource in resources]
    bundle = normalize_source_bundle(
        artifacts,
        str(vehicle.get("region") or "US"),
        expected_vehicle=dict(vehicle),
    )
    if bundle.vehicle is None or not bundle.articles:
        raise RuntimeError("AutoAPItwo article did not normalize for the requested vehicle")
    normalized_articles = []
    for article in bundle.articles:
        normalized = normalize_procedure_article(article)
        requested_article_id = str(descriptor.get("_requested_article_id") or "").strip()
        if requested_article_id:
            # The caller's persisted lineage ID is authoritative when a v1
            # opaque reference resolves an older catalog entry.
            normalized["article_id"] = requested_article_id
        try:
            normalized = localize_procedure_images(normalized, vehicle=vehicle)
        except Exception:  # noqa: BLE001 - preserve readable text if object storage is unavailable
            pass
        normalized_articles.append(normalized)
    normalized_articles = tuple(normalized_articles)
    bundle = replace(bundle, articles=normalized_articles)
    if os.getenv("AUTODATA_SOURCE_PERSIST", "1") == "1":
        from .bundle_persistence import persist_source_bundle

        persist_source_bundle(bundle, artifacts, adapter_name="autoapitwo")
    evidence_by_id = {
        str(item["evidence_id"]): item
        for item in bundle.evidence
        if item.get("evidence_id")
    }
    records = []
    for article in bundle.articles:
        records.append(
            {
                "kind": "article",
                "vehicle_key": bundle.vehicle.get("vehicle_key"),
                "vehicle_identity": dict(bundle.vehicle),
                "article": dict(article),
                "evidence": (
                    [evidence_by_id[str(article["evidence_id"])] ]
                    if article.get("evidence_id")
                    and str(article["evidence_id"]) in evidence_by_id
                    else []
                ),
            }
        )
    return records, {
        "mode": "autoapitwo_article_detail",
        "content_source": "autoapitwo",
        "traversal": "selected_article_only",
        "vehicle_count": 1,
        "materialized_records": len(records),
        "index_read_count": len(descriptor.get("_catalog_request_ids", ())),
        "targeted_article_fetch_count": 1,
        "targeted_labor_fetch_count": int(bool(descriptor.get("labor_resource_ref"))),
    }


def _resolve_source_vehicle_ref(
    connector: Any, request: Mapping[str, Any], vehicle: Mapping[str, Any]
) -> str:
    """Resolve exactly one source vehicle without guessing among candidates."""

    supplied = str(request.get("source_vehicle_ref") or "").strip()
    if supplied:
        return supplied
    from .source_connector_client import SourceConnectorError

    selector: dict[str, Any] = {
        "year": int(vehicle.get("model_year", vehicle.get("year"))),
        "make": str(vehicle["make"]),
        "model": str(vehicle["model"]),
        "region": str(vehicle.get("region") or "US"),
    }
    configuration = " ".join(
        str(value).strip()
        for value in (vehicle.get("trim"), vehicle.get("engine"), vehicle.get("drivetrain"))
        if value not in (None, "")
    )
    if configuration:
        selector["configuration"] = configuration
    resolution = connector.resolve_vehicle(selector)
    candidates = resolution.body.get("candidates", ())
    if len(candidates) != 1:
        raise SourceConnectorError("AMBIGUOUS" if candidates else "NOT_FOUND")
    return str(candidates[0]["opaque_ref"])


def _source_article_pages(connector: Any, source_vehicle_ref: str) -> tuple[list[Any], list[dict[str, Any]]]:
    """Read article pages in source order, rejecting repeated or stalled cursors."""

    pages: list[Any] = []
    articles: list[dict[str, Any]] = []
    cursor: str | None = None
    seen: set[str] = set()
    for _ in range(1000):
        page = connector.list_articles(source_vehicle_ref, cursor)
        pages.append(page)
        articles.extend(dict(item) for item in page.body["articles"])
        if page.complete:
            return pages, articles
        cursor = page.next_cursor
        if cursor is None or cursor in seen:
            from .source_connector_client import SourceConnectorError

            raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
        seen.add(cursor)
    from .source_connector_client import SourceConnectorError

    raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")


def _find_source_article(
    connector: Any, source_vehicle_ref: str, request: Mapping[str, Any]
) -> dict[str, Any]:
    """Select one list entry by its opaque ref or by a unique title search."""

    from .source_connector_client import SourceConnectorError

    requested_id = str(request.get("source_article_id") or request.get("article_id") or "").strip()
    title = str(request.get("title") or "").strip().casefold()
    pages: list[Any] = []
    articles: list[dict[str, Any]] = []
    if requested_id:
        pages, articles = _source_article_pages(connector, source_vehicle_ref)
        legacy_suffix = requested_id.rsplit(":", 1)[-1]
        matches = [
            item for item in articles
            if item["opaque_ref"] == requested_id
            or item["opaque_ref"] == legacy_suffix
            or item["opaque_ref"].endswith(f":{legacy_suffix}")
        ]
        if not matches and title:
            # A historical AutoData ID may refer to an old provider key. Use
            # the exact persisted title to map it to the new opaque ref.
            matches = _search_source_articles(connector, source_vehicle_ref, title)
    else:
        if not title:
            raise SourceConnectorError("INVALID_INPUT")
        matches = _search_source_articles(connector, source_vehicle_ref, str(request.get("title")))
    if len(matches) != 1:
        raise SourceConnectorError("AMBIGUOUS" if matches else "NOT_FOUND")
    selected = dict(matches[0])
    selected["_requested_article_id"] = requested_id
    selected["_catalog_request_ids"] = [page.request_id for page in pages]
    return selected


def _search_source_articles(connector: Any, source_vehicle_ref: str, query: str) -> list[dict[str, Any]]:
    """Search all v1 pages and keep exact title matches in returned order."""

    from .source_connector_client import SourceConnectorError

    normalized_title = query.strip().casefold()
    matches: list[dict[str, Any]] = []
    cursor: str | None = None
    seen: set[str] = set()
    for _ in range(1000):
        page = connector.search_articles(source_vehicle_ref, query, cursor)
        matches.extend(
            dict(item) for item in page.body["articles"]
            if str(item.get("title") or "").strip().casefold() == normalized_title
        )
        if page.complete:
            return matches
        cursor = page.next_cursor
        if cursor is None or cursor in seen:
            raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
        seen.add(cursor)
    raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")

def _hydrate_article_catalog(request: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Persist one vehicle's article index without fetching article bodies."""

    from .article_intake import VehicleTarget
    from .worker import _load_autoapi_job_catalog

    progress = _ArticleCatalogProgress(request)
    progress.start()
    primary_error = None
    progress.publish(
        {
            "phase": "source_autoapi",
            "detail": "Trying to retrieve the full article list from AutoAPI…",
        },
        force=True,
    )
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
    except Exception as error:  # noqa: BLE001 - try the second source
        primary_error = error
    if primary_error is None and not records:
        primary_error = RuntimeError("primary article catalog was empty")

    if primary_error is not None:
        primary_detail = _source_failure_detail("AutoAPI", primary_error)
        progress.publish(
            {
                "phase": "source_autoapi_failed",
                "detail": f"{primary_detail} Trying to retrieve the full article list from AutoAPItwo…",
            },
            force=True,
        )
        progress.publish(
            {
                "phase": "source_autoapitwo",
                "detail": "Trying to retrieve the full article list from AutoAPItwo…",
            },
            force=True,
        )
        try:
            records, metadata = _invoke_autoapitwo_article_catalog_loader(
                request, vehicle, progress
            )
        except Exception as fallback_error:  # noqa: BLE001 - source failure is a retryable miss
            fallback_detail = _source_failure_detail("AutoAPItwo", fallback_error)
            progress.failed(f"{primary_detail} {fallback_detail}")
            return {
                "status": "source_unavailable",
                "hydration_key": key,
                "scope": "articles",
                "complete": False,
                "missing_scopes": ["articles"],
                "rows": [],
                "metadata": {
                    "reason": type(fallback_error).__name__,
                    "primary_source_reason": type(primary_error).__name__,
                    "detail": f"{primary_detail} {fallback_detail}",
                },
            }
    else:
        progress.publish(
            {
                "phase": "source_autoapi_complete",
                "processed_units": len(records),
                "total_units": len(records),
                "detail": f"AutoAPI returned {len(records):,} article records. Saving the catalog…",
            },
            force=True,
        )

    rows = [dict(record) for record in records if isinstance(record, Mapping)]
    if rows:
        progress.complete(rows)
    else:
        progress.failed("No articles were returned for this vehicle.")
    return {
        "status": "hydrated" if rows else "source_miss",
        "hydration_key": key,
        "scope": "articles",
        "complete": bool(rows),
        "missing_scopes": [] if rows else ["articles"],
        "rows": rows,
        "metadata": metadata if isinstance(metadata, Mapping) else {},
    }


def _invoke_autoapitwo_article_catalog_loader(
    request: Mapping[str, Any],
    vehicle: Mapping[str, Any],
    progress: _ArticleCatalogProgress,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Call the loader while keeping older provider test doubles compatible."""

    loader = _load_autoapitwo_article_catalog
    try:
        parameters = inspect.signature(loader).parameters
    except (TypeError, ValueError):
        parameters = {}
    accepts_progress = "progress" in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    if accepts_progress:
        return loader(request, vehicle, progress=progress)
    return loader(request, vehicle)


def _load_autoapitwo_article_catalog(
    request: Mapping[str, Any],
    vehicle: Mapping[str, Any],
    *,
    progress: _ArticleCatalogProgress | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Persist a vehicle's Banktwo v1 article index without reading content."""

    from .source_adapters import SourceResource, adapt_source_resource
    from .source_bundle import normalize_source_bundle
    from .source_connector_client import source_connector_registry

    connector = source_connector_registry().get("banktwo")
    if connector is None:
        raise RuntimeError("Banktwo source connector is not configured")
    source_vehicle_ref = _resolve_source_vehicle_ref(connector, request, vehicle)
    pages, source_articles = _source_article_pages(connector, source_vehicle_ref)
    if not pages or not pages[-1].complete:
        raise RuntimeError("Banktwo article index is incomplete")
    provider_id = pages[0].persisted_provider
    source_revision = pages[0].source_revision
    source_locator = pages[0].source_locator or (
        f"{connector.base_url}/v1/vehicles/{quote(source_vehicle_ref, safe='')}/articles"
    )
    articles = [
        {
            "id": f"{provider_id}:{source_vehicle_ref}:{item['opaque_ref']}",
            "title": item["title"],
            "bucket": item.get("category"),
            "component": item.get("component"),
            "resource_ref": item.get("resource_ref"),
            "labor_resource_ref": item.get("labor_resource_ref"),
            "asset_resource_refs": item.get("asset_resource_refs", []),
        }
        for item in source_articles
    ]

    total_articles = len(articles)
    if progress is not None:
        progress.publish(
            {
                "phase": "normalizing",
                "processed_units": 0,
                "total_units": total_articles,
                "detail": f"Building catalog — 0/{total_articles:,} articles prepared…",
            },
            force=True,
        )

    records: list[dict[str, Any]] = []
    bundles: list[tuple[Any, list[Any]]] = []
    processed_articles = 0
    year = int(vehicle.get("model_year", vehicle.get("year")))
    source_engine = vehicle.get("engine_displacement_l", vehicle.get("engine"))
    source_engine_number = _engine_number(source_engine)
    if source_engine_number is not None:
        source_engine = f"{source_engine_number:.1f}L"
    payload = {
        "kind": "vehicle",
        "year": year,
        "make": str(vehicle["make"]),
        "model": str(vehicle["model"]),
        "region": str(vehicle.get("region") or "US"),
        "engine": source_engine,
        "articleDetails": articles,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    resource = SourceResource.from_bytes(
        source_locator,
        source_revision,
        raw,
        "application/json",
        locator=source_locator,
        metadata={
            "provider": provider_id,
            "source_provider": "banktwo",
            "vehicle_id": source_vehicle_ref,
            "request_ids": [page.request_id for page in pages],
            "page_locators": [page.source_locator for page in pages if page.source_locator],
        },
    )
    artifact = adapt_source_resource(resource)
    bundle = normalize_source_bundle(
        [artifact],
        str(vehicle.get("region") or "US"),
        expected_vehicle=dict(vehicle),
        preserve_article_order=True,
    )
    if bundle.vehicle is not None:
        evidence_by_id = {
            str(item["evidence_id"]): item
            for item in bundle.evidence
            if item.get("evidence_id")
        }
        for article in bundle.articles:
            processed_articles += 1
            records.append(
                {
                    "kind": "article",
                    "vehicle_key": bundle.vehicle.get("vehicle_key"),
                    "vehicle_identity": dict(bundle.vehicle),
                    "article": dict(article),
                    "evidence": (
                        [evidence_by_id[str(article["evidence_id"])] ]
                        if article.get("evidence_id")
                        and str(article["evidence_id"]) in evidence_by_id
                        else []
                    ),
                }
            )
            if progress is not None:
                progress.publish(
                    {
                        "phase": "normalizing",
                        "processed_units": processed_articles,
                        "total_units": total_articles,
                        "current_article_id": str(article.get("article_id") or ""),
                        "current_title": str(article.get("title") or "Untitled article"),
                        "detail": (
                            f"Building catalog — Processing article "
                            f"{processed_articles:,}/{total_articles:,} — "
                            f"{article.get('title') or 'Untitled article'}"
                        ),
                    }
                )
        bundles.append((bundle, [artifact]))

    if progress is not None:
        progress.publish(
            {
                "phase": "persisting",
                "processed_units": processed_articles,
                "total_units": total_articles,
                "detail": f"Saving {processed_articles:,} catalog articles…",
            },
            force=True,
        )
    if os.getenv("AUTODATA_SOURCE_PERSIST", "1") == "1":
        from .bundle_persistence import persist_source_bundle

        for bundle, artifacts in bundles:
            persist_source_bundle(bundle, artifacts, adapter_name="autoapitwo")
    return records, {
        "mode": "autoapitwo_article_index",
        "content_source": "autoapitwo",
        "traversal": "vehicle_article_index",
        "vehicle_count": int(bool(bundle.vehicle)),
        "materialized_records": len(records),
        "index_read_count": len(pages),
        "targeted_article_fetch_count": 0,
        "targeted_labor_fetch_count": 0,
    }


def _source_failure_detail(source: str, error: BaseException) -> str:
    """Convert provider failures into concise, actionable UI status text."""

    chain: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in chain and len(chain) < 8:
        chain.append(current)
        current = current.__cause__ or current.__context__
    status = next(
        (
            int(getattr(item, attribute))
            for item in chain
            for attribute in ("code", "status", "status_code")
            if str(getattr(item, attribute, "")).isdigit()
        ),
        None,
    )
    text = " ".join(
        str(getattr(item, "reason", "") or item).casefold()
        for item in chain
    ).replace("_", " ")
    if status == 429 or "rate limit" in text or "too many requests" in text:
        reason = "rate limited"
    elif status == 401 or "expired" in text or "authentication" in text or "unauthorized" in text:
        reason = "authentication expired or unauthorized"
    elif status == 403 or "forbidden" in text:
        reason = "forbidden"
    elif status in {408, 504} or "timed out" in text or "timeout" in text:
        reason = "server timed out"
    elif status is not None and status >= 500:
        reason = "source server unavailable"
    elif "redirect" in text:
        reason = "unexpected redirect"
    elif "ambiguous" in text:
        reason = "matched more than one source item"
    elif "no matching" in text or "did not resolve" in text or "no vehicle" in text:
        reason = "returned no matching vehicle"
    elif "empty" in text or "not found" in text or "no article" in text:
        reason = "returned no matching articles"
    elif "incomplete" in text and "article" in text:
        reason = "article index was incomplete"
    elif "source read failed" in text:
        reason = "source read failed"
    else:
        reason = "request failed"
    suffix = f" (HTTP {status})" if status is not None else ""
    return f"{source} failed — {reason}{suffix}."


def _update_article_catalog_progress(
    request: Mapping[str, Any],
    *,
    status: str,
    phase: str,
    processed_units: int,
    total_units: int,
    current_article_id: str = "",
    current_title: str = "",
    detail: str = "",
) -> None:
    """Best-effort progress write; source hydration must not fail on UI telemetry."""

    if os.getenv("AUTODATA_SOURCE_PERSIST", "1") != "1":
        return
    vehicle_id = str(request.get("vehicle_id") or "").strip()
    year = int(request.get("year", 0) or 0)
    make = str(request.get("make") or "").strip()
    model = str(request.get("model") or "").strip()
    region = str(request.get("region") or "US").strip().upper()
    scope_key = (
        f"articles:vehicle:{vehicle_id}"
        if vehicle_id
        else "|".join(("articles", str(year), make.casefold(), model.casefold(), region))
    )
    processed = max(0, int(processed_units))
    total = max(0, int(total_units))
    if status == "completed":
        percent = 100
    elif total:
        percent = min(99, max(0, round(processed * 100 / total)))
    else:
        percent = 0
    try:
        import psycopg

        host, port_text = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
        with psycopg.connect(
            host=host,
            port=int(port_text),
            dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
            user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
            password=os.environ["AUTODATA_POSTGRES_PASSWORD"],
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO vehicle_catalog_hydration_scopes
                        (scope_key, scope, model_year, make, model, region, vehicle_id,
                         status, phase, processed_units, total_units,
                         current_article_id, current_title, progress_detail, progress_percent)
                    VALUES (%s, 'articles', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (scope_key) DO UPDATE SET
                        status = EXCLUDED.status,
                        phase = EXCLUDED.phase,
                        processed_units = EXCLUDED.processed_units,
                        total_units = EXCLUDED.total_units,
                        current_article_id = EXCLUDED.current_article_id,
                        current_title = EXCLUDED.current_title,
                        progress_detail = EXCLUDED.progress_detail,
                        progress_percent = EXCLUDED.progress_percent,
                        updated_at = now()
                    """,
                    (
                        scope_key,
                        year,
                        make,
                        model,
                        region,
                        vehicle_id,
                        status,
                        phase,
                        processed,
                        total,
                        current_article_id,
                        current_title,
                        detail,
                        percent,
                    ),
                )
            connection.commit()
    except Exception:
        return


def _engine_number(value: Any) -> float | None:
    matches = re.findall(r"\d+(?:\.\d+)?", str(value or ""))
    if not matches:
        return None
    decimal_matches = [match for match in matches if "." in match]
    return float(decimal_matches[-1] if decimal_matches else matches[0])


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
    if scope == "years":
        # The years index is not year-scoped: this table requires a valid
        # model_year, so there is no durable coverage marker to write for it.
        return {"status": "not_applicable"}
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
    from .source_connector_client import source_connector_registry

    clients = source_connector_registry()
    return tuple(_SourceCatalogProvider(client) for client in clients.values())


class _SourceCatalogProvider:
    """Project contract rows into the existing canonical catalog shape."""

    def __init__(self, client: Any):
        self.client = client

    def resolve_catalog(self, request: CatalogRequest) -> Mapping[str, Any]:
        scope = request.scope if request.scope in {"years", "makes", "models", "configurations"} else "configurations"
        # `year` is a required CatalogRequest field, but years are an
        # unfiltered index and must not receive that synthetic placeholder.
        selector: dict[str, Any] = {}
        if scope != "years":
            selector["year"] = request.year
        if scope in {"models", "configurations"}:
            selector["make"] = request.make
        if scope == "configurations":
            selector["model"] = request.model
        rows: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        cursor: str | None = None
        seen: set[str] = set()
        for _ in range(1000):
            page = self.client.catalog(scope, selector, cursor)
            provenance.append({
                "provider": page.persisted_provider,
                "source_uri": page.source_locator or f"{self.client.base_url}/v1/catalog/{scope}",
                "source_version": page.source_revision,
                "retrieved_at": page.fetched_at,
                "metadata": {"request_id": page.request_id, "wire_provider": page.provider},
            })
            for item in page.body["items"]:
                fields_by_scope = {
                    "years": ("year",),
                    "makes": ("year", "make"),
                    "models": ("year", "make", "model"),
                    "configurations": ("year", "make", "model", "engine", "drivetrain", "region"),
                }
                row = {
                    key: item[key]
                    for key in fields_by_scope[scope]
                    if key in item
                }
                if scope == "configurations":
                    row.setdefault("region", item.get("region") or request.region)
                if scope == "configurations" and "configuration" in item:
                    row["engine_label"] = item["configuration"]
                row["provider_mappings"] = [{
                    "provider": page.persisted_provider,
                    "entity_type": "car",
                    "provider_id": item["opaque_ref"],
                    "provider_label": item["label"],
                }]
                rows.append(row)
            if page.complete:
                # Completeness belongs to the requested selector scope. Sparse
                # scope rows remain available to selectors; full-vehicle
                # persistence performs its own field check.
                return {"rows": rows, "complete": True, "provenance": provenance,
                        "missing_scopes": []}
            cursor = page.next_cursor
            if cursor is None or cursor in seen:
                raise ValueError("source catalog pagination did not advance")
            seen.add(cursor)
        raise ValueError("source catalog exceeded pagination limit")


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


def _result_from_payload(
    payload: Mapping[str, Any], *, cache_hit: bool, scope: str = "configurations"
) -> CatalogResult:
    rows = tuple(_canonical_rows(payload.get("rows", payload.get("records", ())), scope=scope))
    return CatalogResult(
        rows=rows,
        complete=True,
        provenance=tuple(_dedupe_provenance(_provenance(payload.get("provenance", ())))),
        cache_hit=cache_hit,
    )


def _canonical_rows(values: Any, *, scope: str = "configurations") -> list[dict[str, Any]]:
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
        required = {
            "years": {"year"},
            "makes": {"year", "make"},
            "models": {"year", "make", "model"},
            "configurations": {"year", "make", "model", "region"},
        }.get(scope, {"year", "make", "model", "region"})
        if not required.issubset(row):
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
            incoming = {key: value for key, value in row.items() if value not in (None, "")}
            if "provider_mappings" in incoming:
                incoming["provider_mappings"] = _merge_provider_mappings(
                    current.get("provider_mappings", ()), incoming["provider_mappings"]
                )
            current.update(incoming)
    return result


def _merge_provider_mappings(existing: Any, additions: Any) -> list[dict[str, Any]]:
    """Keep distinct source identities when providers share a canonical row."""

    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for value in (*_mapping_sequence(existing), *_mapping_sequence(additions)):
        if not isinstance(value, Mapping):
            continue
        mapping = dict(value)
        key = (
            str(mapping.get("provider", "")),
            str(mapping.get("entity_type", "")),
            str(mapping.get("provider_id", "")),
        )
        if key not in seen:
            seen.add(key)
            merged.append(mapping)
    return merged


def _mapping_sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return tuple(value)
    return ()


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
