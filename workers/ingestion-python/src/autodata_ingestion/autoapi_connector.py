"""Client for the local AutoAPI read-only connector service.

The connector speaks only the documented ``/v1/api`` surface exposed by the
separate AutoAPI repository.  It preserves each response as a
``SourceResource`` so the existing universal adapter, provenance, evidence,
deduplication, and persistence boundaries remain authoritative.
"""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
from dataclasses import dataclass, replace
import hashlib
import re
from threading import Condition, RLock
import time
from typing import Any, Callable, Iterable, Mapping
import uuid
import weakref
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .source_adapters import SourceResource
from .pricing import price_freshness
from .vehicle_identity import canonicalize_vehicle_observation
from .vehicle_selection import normalize_vehicle_list


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_VEHICLE_MAX_CONCURRENCY = 4
DEFAULT_VEHICLE_ID_BATCH_SIZE = 100
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 0.25
DEFAULT_SOURCE_CACHE_MAX_ENTRIES = 512
DEFAULT_SOURCE_CACHE_TTL_SECONDS = 300.0

_SHARED_SOURCE_CACHE: OrderedDict[str, tuple[Any, SourceResource]] = OrderedDict()
_SHARED_SOURCE_INFLIGHT: dict[str, Condition] = {}
_SHARED_SOURCE_CACHE_LOCK = RLock()
_OPENER_NAMESPACES: weakref.WeakKeyDictionary[Any, str] = weakref.WeakKeyDictionary()


@dataclass(frozen=True)
class AutoAPIVehicleBundle:
    """One AutoAPI vehicle and all fetched source resources for that vehicle."""

    vehicle_id: str
    content_source: str
    vehicle: dict[str, Any]
    configurations: tuple[dict[str, Any], ...]
    resources: tuple[SourceResource, ...]
    article_ids: tuple[str, ...]


@dataclass(frozen=True)
class AutoAPICatalog:
    """The complete catalog traversal result before AutoData persistence."""

    years: tuple[int, ...]
    selection_rows: tuple[dict[str, Any], ...]
    vehicles: tuple[AutoAPIVehicleBundle, ...]
    errors: tuple[dict[str, str], ...] = ()

    def to_batches(self) -> tuple[Any, ...]:
        """Convert fetched provider bundles into the shared batch executor."""

        from .autoapi_batch import AutoAPIBatch

        return tuple(
            AutoAPIBatch(
                vehicle_key=str(bundle.vehicle["vehicle_key"]),
                vehicle=dict(bundle.vehicle),
                source_directory=None,
                configurations=bundle.configurations,
                source_resources=bundle.resources,
            )
            for bundle in self.vehicles
        )


class AutoAPIConnector:
    """Traverse the local AutoAPI catalog and fetch each vehicle's article list."""

    name = "autoapi"

    def __init__(
        self,
        base_url: str,
        *,
        content_source: str = "GeneralMotors",
        default_region: str = "US",
        source_version: str = "autoapi-http-v1",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        vehicle_max_concurrency: int = DEFAULT_VEHICLE_MAX_CONCURRENCY,
        vehicle_id_batch_size: int = DEFAULT_VEHICLE_ID_BATCH_SIZE,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
        source_cache_ttl_seconds: float | None = DEFAULT_SOURCE_CACHE_TTL_SECONDS,
        request_headers: Mapping[str, str] | None = None,
        opener: Callable[..., Any] = urlopen,
    ):
        parsed = urlsplit(str(base_url).strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("AutoAPI base URL must use http or https")
        if parsed.username or parsed.password:
            raise ValueError("AutoAPI base URL must not contain credentials")
        if not str(content_source).strip():
            raise ValueError("AutoAPI content source is required")
        if not str(default_region).strip():
            raise ValueError("AutoAPI default region is required")
        if (
            timeout_seconds <= 0
            or max_bytes <= 0
            or vehicle_max_concurrency < 1
            or vehicle_id_batch_size < 1
            or retry_attempts < 1
            or retry_backoff_seconds < 0
            or (
                source_cache_ttl_seconds is not None
                and source_cache_ttl_seconds < 0
            )
        ):
            raise ValueError("AutoAPI limits must be positive")
        self._base_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
        self._content_source = str(content_source).strip()
        self._default_region = str(default_region).strip().upper()
        self.source_version = str(source_version).strip()
        if not self.source_version:
            raise ValueError("AutoAPI source version is required")
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._vehicle_max_concurrency = vehicle_max_concurrency
        self._vehicle_id_batch_size = vehicle_id_batch_size
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._source_cache_ttl_seconds = source_cache_ttl_seconds
        self._request_headers = _request_headers(request_headers)
        self._opener = opener
        self._opener_namespace = _opener_namespace(opener)
        # A connector instance is the read-through cache boundary for one
        # request worker.  Keys are complete normalized request URIs, so a
        # replay never silently reuses a response from another vehicle or
        # endpoint.  SourceResource keeps the original bytes for persistence.
        self._source_cache: dict[str, tuple[Any, SourceResource]] = {}
        self._required_source_cache: dict[str, dict[str, Any]] = {}
        self._source_cache_lock = RLock()

    def fetch_catalog(self) -> AutoAPICatalog:
        """Fetch years, makes, models, vehicle identities, and all articles."""

        years_payload, _ = self._cached_get_json("/v1/api/years")
        years = tuple(sorted({_year_value(item) for item in _items(years_payload)}))
        vehicle_targets: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for year in years:
            makes_scope = f"makes:{year}"
            try:
                makes_payload, _ = self._cached_get_json(
                    f"/v1/api/year/{quote(str(year), safe='')}/makes"
                )
            except Exception as error:  # noqa: BLE001 - retain other years
                errors.append({"scope": makes_scope, "error": _safe_error(error)})
                continue
            for make in _items(makes_payload):
                make_name = _first_text(make, "makeName", "name", "make")
                if not make_name:
                    continue
                # MOTOR's models route accepts the displayed make name. The
                # numeric make ID is only metadata from the makes response.
                make_route_value = make_name
                models_scope = f"models:{year}:{make_route_value}"
                try:
                    models_payload, _ = self._cached_get_json(
                        "/v1/api/year/{}/make/{}/models".format(
                            quote(str(year), safe=""), quote(make_route_value, safe="")
                        )
                    )
                except Exception as error:  # noqa: BLE001 - retain other makes
                    errors.append({"scope": models_scope, "error": _safe_error(error)})
                    continue
                models = _items(models_payload)
                model_vehicle_ids = [
                    vehicle_id
                    for model in models
                    for vehicle_id in _vehicle_ids_from_model(model)
                ]
                model_name_by_vehicle_id = {
                    vehicle_id: _first_text(model, "modelName", "model", "name")
                    for model in models
                    for vehicle_id in _vehicle_ids_from_model(model)
                    if _first_text(model, "modelName", "model", "name")
                }
                if not model_vehicle_ids:
                    continue
                for batch_index, model_id_batch in enumerate(
                    _chunks(
                        list(dict.fromkeys(model_vehicle_ids)),
                        self._vehicle_id_batch_size,
                    )
                ):
                    vehicles_scope = f"vehicles:{year}:{make_route_value}:{batch_index}"
                    try:
                        vehicles_payload, _ = self._cached_get_json(
                            f"/v1/api/source/{quote(self._content_source, safe='')}/vehicles",
                            query={"vehicleIds": ",".join(model_id_batch)},
                        )
                    except Exception as error:  # noqa: BLE001 - retain other makes
                        errors.append({"scope": vehicles_scope, "error": _safe_error(error)})
                        continue
                    for vehicle in _items(vehicles_payload):
                        vehicle_id = _first_text(vehicle, "vehicleId", "id", "vehicle_id")
                        if not vehicle_id:
                            continue
                        vehicle_targets.append(
                            {
                                "year": year,
                                "make": make_name,
                                "model": (
                                    _first_text(vehicle, "modelName", "model", "name")
                                    or model_name_by_vehicle_id.get(vehicle_id)
                                    or "Unknown"
                                ),
                                "vehicle_id": vehicle_id,
                                "display_name": _first_text(
                                    vehicle, "vehicleName", "displayName", "name"
                                ),
                            }
                        )

        targets = _dedupe_vehicle_targets(vehicle_targets)
        bundles_by_vehicle: dict[str, AutoAPIVehicleBundle] = {}
        with ThreadPoolExecutor(max_workers=self._vehicle_max_concurrency) as executor:
            futures = {
                executor.submit(self.fetch_vehicle_bundle, target): target
                for target in targets
            }
            for future in as_completed(futures):
                target = futures[future]
                try:
                    bundle = future.result()
                except Exception as error:  # noqa: BLE001 - retain other vehicles
                    errors.append(
                        {
                            "scope": f"vehicle:{target['vehicle_id']}",
                            "error": _safe_error(error),
                        }
                    )
                else:
                    bundles_by_vehicle[bundle.vehicle_id] = bundle
        bundles = tuple(bundles_by_vehicle[key] for key in sorted(bundles_by_vehicle))
        selection_rows = tuple(
            row
            for bundle in bundles
            for row in _rows_for_bundle(bundle)
        )
        return AutoAPICatalog(years, selection_rows, bundles, tuple(errors))

    def find_vehicle_targets(
        self, year: int, make: str, model: str
    ) -> tuple[dict[str, Any], ...]:
        """Resolve one YMM family through the provider's narrow selector path.

        This is the cold-request path used by a user-selected vehicle. It
        avoids the complete all-years catalog traversal and returns provider
        vehicle IDs that can be passed to :meth:`fetch_vehicle_bundle`.
        """

        makes_payload, _ = self._cached_get_json(
            f"/v1/api/year/{quote(str(year), safe='')}/makes"
        )
        requested_make = " ".join(str(make).split()).casefold()
        make_record = next(
            (
                item
                for item in _items(makes_payload)
                if (_first_text(item, "makeName", "name", "make") or "").casefold()
                == requested_make
            ),
            None,
        )
        if make_record is None:
            return ()
        make_name = _first_text(make_record, "makeName", "name", "make") or str(make)
        make_route_value = make_name
        models_payload, _ = self._cached_get_json(
            "/v1/api/year/{}/make/{}/models".format(
                quote(str(year), safe=""), quote(make_route_value, safe="")
            )
        )
        requested_model = " ".join(str(model).split()).casefold()
        model_vehicle_ids = [
            vehicle_id
            for model_record in _items(models_payload)
            if _model_matches(model_record, requested_model)
            for vehicle_id in _vehicle_ids_from_model(model_record)
        ]
        model_vehicle_ids = list(dict.fromkeys(model_vehicle_ids))
        if not model_vehicle_ids:
            return ()
        vehicles_payload, _ = self._cached_get_json(
            f"/v1/api/source/{quote(self._content_source, safe='')}/vehicles",
            query={"vehicleIds": ",".join(model_vehicle_ids)},
        )
        targets = []
        for vehicle in _items(vehicles_payload):
            vehicle_id = _first_text(vehicle, "vehicleId", "id", "vehicle_id")
            if not vehicle_id:
                continue
            targets.append(
                {
                    "year": year,
                    "make": make_name,
                    "model": _first_text(vehicle, "modelName", "model", "name") or model,
                    "requested_model": model,
                    "vehicle_id": vehicle_id,
                    "display_name": _first_text(
                        vehicle, "vehicleName", "displayName", "name"
                    ),
                }
            )
        return _dedupe_vehicle_targets(targets)

    def fetch_vehicle_bundle(self, target: Mapping[str, Any]) -> AutoAPIVehicleBundle:
        """Fetch vehicle identity, engine configurations, article index, and details."""

        vehicle_id = _required_text(target, "vehicle_id")
        source_path = f"/v1/api/source/{quote(self._content_source, safe='')}/{quote(vehicle_id, safe='') }"
        resources: list[SourceResource] = []

        # The article index is the narrow discovery gate.  Hydrate vehicle
        # identity/configuration only after the list has established which
        # article IDs are available for a query-time selection.
        articles_payload, articles_resource = self.fetch_article_list(vehicle_id)
        resources.append(articles_resource)
        name_payload, name_resource = self._cached_get_json(f"{source_path}/name")
        resources.append(name_resource)
        motor_payload, motor_resource = self._cached_get_json(f"{source_path}/motorvehicles")
        resources.append(motor_resource)

        article_items = _article_items(articles_payload)
        reported_article_count = _reported_article_count(articles_payload)
        if reported_article_count is not None and len(article_items) != reported_article_count:
            raise ValueError(
                "AutoAPI returned an incomplete article index: "
                f"expected {reported_article_count}, received {len(article_items)}"
            )
        article_ids = tuple(
            dict.fromkeys(
                article_id
                for article in article_items
                if (article_id := _first_text(article, "id", "articleId", "article_id"))
            )
        )

        resources.sort(key=lambda item: (item.source_uri, item.content_sha256))
        rows = _selector_rows(
            name_payload,
            motor_payload,
            target,
            default_region=self._default_region,
        )
        selection = normalize_vehicle_list(rows, default_region=self._default_region)
        if len(selection) != 1:
            raise ValueError(f"AutoAPI vehicle {vehicle_id} did not resolve to one vehicle family")
        selected = selection[0]
        return AutoAPIVehicleBundle(
            vehicle_id=vehicle_id,
            content_source=self._content_source,
            vehicle={
                "vehicle_key": selected.vehicle_key,
                "year": selected.year,
                "make": selected.make,
                "model": selected.model,
                "region": selected.region,
                "drivetrain": selected.drivetrain,
            },
            configurations=tuple(selected.configurations),
            resources=tuple(resources),
            article_ids=article_ids,
        )

    def fetch_article_list(
        self, vehicle_id: str
    ) -> tuple[Any, SourceResource]:
        """Read the vehicle article index without hydrating article bodies."""

        vehicle = quote(str(_required_text({"vehicle_id": vehicle_id}, "vehicle_id")), safe="")
        source = quote(self._content_source, safe="")
        return self._cached_get_json(
            f"/v1/api/source/{source}/vehicle/{vehicle}/articles/v2"
        )

    def fetch_parts_resource(
        self, vehicle_id: str
    ) -> tuple[Any, SourceResource]:
        """Read the provider's vehicle-scoped parts/price resource once."""

        vehicle = quote(str(_required_text({"vehicle_id": vehicle_id}, "vehicle_id")), safe="")
        source = quote(self._content_source, safe="")
        return self._cached_get_json(
            f"/v1/api/source/{source}/vehicle/{vehicle}/parts"
        )

    # The plural spelling mirrors the domain interface used by callers while
    # retaining the singular provider resource name in the implementation.
    fetch_part_resources = fetch_parts_resource

    def fetch_article_resources(
        self,
        vehicle_id: str,
        article_id: str,
        *,
        labor_article_id: str | None = None,
    ) -> tuple[SourceResource, ...]:
        """Fetch one requested article body and its labor resource.

        Article indexes remain the default discovery path. This method is
        intentionally query-time and caller-scoped so a cache miss does not
        fan out to every article in a vehicle catalog.
        """

        source = quote(self._content_source, safe="")
        vehicle = quote(str(vehicle_id), safe="")
        article = quote(str(article_id), safe="")
        labor_article = quote(str(labor_article_id or article_id), safe="")
        _detail_payload, detail_resource = self._cached_get_json(
            f"/v1/api/source/{source}/vehicle/{vehicle}/article/{article}"
        )
        try:
            _labor_payload, labor_resource = self._cached_get_json(
                f"/v1/api/source/{source}/vehicle/{vehicle}/labor/{labor_article}"
            )
        except Exception:
            # Labor is an enrichment resource. Preserve a usable article body
            # when the provider cannot supply labor for an otherwise valid
            # procedure; the planner will expose labor as unavailable/review.
            return (detail_resource,)
        if labor_article_id and str(labor_article_id) != str(article_id):
            labor_resource = replace(
                labor_resource,
                metadata={
                    **labor_resource.metadata,
                    "target_article_id": str(article_id),
                    "labor_article_id": str(labor_article_id),
                },
            )
        return detail_resource, labor_resource

    def _cached_get_json(
        self,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
    ) -> tuple[Any, SourceResource]:
        """Return a source response from the per-connector read-through cache."""

        uri = _build_uri(self._base_url, path, query)
        key = self._source_cache_key(uri)
        now = datetime.now(UTC)
        with self._source_cache_lock:
            cached = self._source_cache.get(key)
            if cached is not None and not self._source_cache_entry_is_fresh(cached[1], now):
                self._source_cache.pop(key, None)
                cached = None
        if cached is not None:
            payload, resource = cached
            return deepcopy(payload), replace(resource, metadata=deepcopy(resource.metadata))

        with _SHARED_SOURCE_CACHE_LOCK:
            while True:
                cached = _SHARED_SOURCE_CACHE.get(key)
                if cached is not None and not self._source_cache_entry_is_fresh(cached[1], now):
                    _SHARED_SOURCE_CACHE.pop(key, None)
                    cached = None
                if cached is not None:
                    _SHARED_SOURCE_CACHE.move_to_end(key)
                    payload, resource = cached
                    break
                waiter = _SHARED_SOURCE_INFLIGHT.get(key)
                if waiter is None:
                    _SHARED_SOURCE_INFLIGHT[key] = Condition(_SHARED_SOURCE_CACHE_LOCK)
                    break
                waiter.wait()
        if cached is not None:
            result = deepcopy(cached[0]), replace(
                cached[1], metadata=deepcopy(cached[1].metadata)
            )
            with self._source_cache_lock:
                self._source_cache[key] = (
                    deepcopy(result[0]),
                    replace(result[1], metadata=deepcopy(result[1].metadata)),
                )
            return result

        try:
            payload, resource = self._get_json(path, query=query)
        except Exception:
            with _SHARED_SOURCE_CACHE_LOCK:
                waiter = _SHARED_SOURCE_INFLIGHT.pop(key, None)
                if waiter is not None:
                    waiter.notify_all()
            raise

        cached_value = (
            deepcopy(payload),
            replace(resource, metadata=deepcopy(resource.metadata)),
        )
        with _SHARED_SOURCE_CACHE_LOCK:
            while len(_SHARED_SOURCE_CACHE) >= DEFAULT_SOURCE_CACHE_MAX_ENTRIES:
                _SHARED_SOURCE_CACHE.popitem(last=False)
            _SHARED_SOURCE_CACHE[key] = cached_value
            waiter = _SHARED_SOURCE_INFLIGHT.pop(key, None)
            if waiter is not None:
                waiter.notify_all()
        with self._source_cache_lock:
            while len(self._source_cache) >= DEFAULT_SOURCE_CACHE_MAX_ENTRIES:
                self._source_cache.pop(next(iter(self._source_cache)))
            self._source_cache[key] = cached_value
        return deepcopy(payload), replace(resource, metadata=deepcopy(resource.metadata))

    def _source_cache_entry_is_fresh(
        self, resource: SourceResource, now: datetime
    ) -> bool:
        """Apply the process-wide read-through cache TTL to one source entry."""

        if self._source_cache_ttl_seconds is None:
            return True
        retrieved_at = resource.metadata.get("retrieved_at")
        if not isinstance(retrieved_at, str):
            return False
        try:
            retrieved = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if retrieved.tzinfo is None or retrieved.utcoffset() is None:
            return False
        return now - retrieved.astimezone(UTC) < timedelta(
            seconds=self._source_cache_ttl_seconds
        )

    def _source_cache_key(self, uri: str) -> str:
        header_fingerprint = hashlib.sha256(
            json.dumps(
                sorted(self._request_headers.items()), separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        return "|".join(
            (
                self._content_source,
                self.source_version,
                header_fingerprint,
                self._opener_namespace,
                uri,
            )
        )

    def _get_json(
        self,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
    ) -> tuple[Any, SourceResource]:
        for attempt in range(self._retry_attempts):
            try:
                return self._get_json_once(path, query=query)
            except Exception as error:  # noqa: BLE001 - retry only safe transient GET failures
                if attempt + 1 >= self._retry_attempts or not _is_retryable(error):
                    raise
                delay = self._retry_backoff_seconds * (2**attempt)
                if delay:
                    time.sleep(delay)
        raise AssertionError("AutoAPI retry loop must return or raise")

    def _get_json_once(
        self,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
    ) -> tuple[Any, SourceResource]:
        uri = _build_uri(self._base_url, path, query)
        headers = {"Accept": "application/json", "User-Agent": "autodata-ingestion/1", **self._request_headers}
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        with self._opener(Request(uri, headers=headers, method="GET"), timeout=self._timeout_seconds) as response:
            status = int(getattr(response, "status", getattr(response, "code", 200)))
            if status < 200 or status >= 300:
                raise ValueError(f"AutoAPI returned HTTP status {status}")
            payload = _read_bounded(response, self._max_bytes)
            try:
                parsed = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("AutoAPI returned invalid JSON") from error
        if not isinstance(parsed, Mapping) or "body" not in parsed or "header" not in parsed:
            raise ValueError("AutoAPI returned an invalid response envelope")
        resource = SourceResource.from_bytes(
            source_uri=uri,
            source_version=self.source_version,
            payload=payload,
            media_type="application/json",
            locator=uri,
            metadata={
                "connector": self.name,
                "http_status": status,
                "retrieved_at": retrieved_at,
            },
        )
        return parsed, resource


def fetch_required_source_resources(
    vehicle: Mapping[str, Any],
    operations: Iterable[Mapping[str, Any]],
    connector: AutoAPIConnector,
) -> dict[str, Any]:
    """Read the article index, then hydrate only resources required by ops.

    The index is authoritative for article IDs.  An operation that names an
    unknown article is reported as unavailable and cannot cause an arbitrary
    provider detail URL to be fetched.  Part retrieval is vehicle-scoped in
    AutoAPI, so one parts resource is read when at least one requested
    operation needs a named part.  The returned ``SourceResource`` values are
    the raw payload retention boundary; normalization can safely run later.
    """

    if not isinstance(vehicle, Mapping):
        raise TypeError("AutoAPI vehicle must be a mapping")
    if not isinstance(connector, AutoAPIConnector):
        raise TypeError("source connector must be an AutoAPIConnector")
    vehicle_id = _first_text(
        vehicle,
        "vehicle_id",
        "autoapi_vehicle_id",
        "provider_vehicle_id",
        "id",
    )
    if not vehicle_id:
        raise ValueError("AutoAPI vehicle requires vehicle_id")
    operation_list = [dict(operation) for operation in operations if isinstance(operation, Mapping)]
    request_key = _required_resource_request_key(vehicle_id, operation_list)
    with connector._source_cache_lock:
        cached_result = connector._required_source_cache.get(request_key)
    if cached_result is not None:
        return deepcopy(cached_result)

    article_list_payload, article_list_resource = connector.fetch_article_list(vehicle_id)
    reported_article_count = _reported_article_count(article_list_payload)
    article_items = _article_items(article_list_payload)
    if reported_article_count is not None and len(article_items) != reported_article_count:
        raise ValueError(
            "AutoAPI returned an incomplete article index: "
            f"expected {reported_article_count}, received {len(article_items)}"
        )
    article_by_id = {
        article_id: article
        for article in article_items
        if (article_id := _first_text(article, "id", "articleId", "article_id"))
    }
    labor_by_title = {
        _normalized_text(_first_text(article, "title", "name") or ""): article_id
        for article_id, article in article_by_id.items()
        if _is_labor_article_record(article)
        and _normalized_text(_first_text(article, "title", "name") or "")
    }

    requested_article_ids: list[str] = []
    missing_article_ids: list[str] = []
    labor_ids: dict[str, str] = {}
    requested_part_ids: list[str] = []
    all_parts_requested = False
    for operation in operation_list:
        article_ids = _operation_values(
            operation,
            "article_id",
            "articleId",
            "source_article_id",
            "sourceArticleId",
        )
        article_ids.extend(
            _operation_values(
                operation,
                "article_ids",
                "articleIds",
                "source_article_ids",
                "sourceArticleIds",
            )
        )
        if not article_ids:
            search_text = _normalized_text(
                _first_text(operation, "article_title", "title", "component", "name") or ""
            )
            article_ids = [
                article_id
                for article_id, article in article_by_id.items()
                if search_text
                and search_text in _normalized_text(
                    _first_text(article, "title", "name") or ""
                )
            ]
        for article_id in dict.fromkeys(article_ids):
            if article_id not in article_by_id:
                missing_article_ids.append(article_id)
                continue
            if article_id not in requested_article_ids:
                requested_article_ids.append(article_id)
            labor_id = _first_text(
                operation,
                "labor_article_id",
                "laborArticleId",
                "source_labor_article_id",
            )
            if labor_id is None:
                title = _normalized_text(
                    _first_text(article_by_id[article_id], "title", "name") or ""
                )
                labor_id = labor_by_title.get(title)
            if labor_id:
                labor_ids[article_id] = labor_id

        part_values = _operation_values(
            operation,
            "part_number",
            "partNumber",
            "source_part_number",
            "sourcePartNumber",
            "part_id",
            "partId",
        )
        part_values.extend(
            _operation_values(
                operation,
                "part_numbers",
                "partNumbers",
                "source_part_numbers",
                "sourcePartNumbers",
                "part_ids",
                "partIds",
            )
        )
        nested_parts = operation.get("parts")
        if isinstance(nested_parts, list):
            part_values.extend(
                value
                for nested in nested_parts
                for value in _operation_values(
                    nested if isinstance(nested, Mapping) else {"part_number": nested},
                    "part_number",
                    "partNumber",
                    "source_part_number",
                    "sourcePartNumber",
                    "part_id",
                    "partId",
                )
            )
        if operation.get("requires_parts") is True or operation.get("parts_requested") is True:
            all_parts_requested = not part_values
        requested_part_ids.extend(part_values)

    requested_part_ids = list(dict.fromkeys(requested_part_ids))
    source_resources: list[SourceResource] = [article_list_resource]
    article_details: dict[str, Any] = {}
    labor: dict[str, Any] = {}
    for article_id in requested_article_ids:
        resources = connector.fetch_article_resources(
            vehicle_id,
            article_id,
            **(
                {"labor_article_id": labor_ids[article_id]}
                if article_id in labor_ids
                else {}
            ),
        )
        source_resources.extend(resources)
        detail_resource = resources[0]
        article_details[article_id] = _resource_payload(detail_resource)
        if len(resources) > 1:
            labor[article_id] = _resource_payload(resources[1])

    parts_payload: Any | None = None
    if requested_part_ids or all_parts_requested:
        parts_payload, parts_resource = connector.fetch_parts_resource(vehicle_id)
        source_resources.append(parts_resource)
    parts = _canonical_price_snapshots(
        parts_payload,
        requested_part_ids,
        all_parts_requested,
        parts_resource if parts_payload is not None else None,
    )
    source_payloads = tuple(
        {
            "source_uri": resource.source_uri,
            "source_version": resource.source_version,
            "content_sha256": resource.content_sha256,
            "payload": resource.payload,
            "source_snapshot_id": _source_snapshot_id(resource),
            "source_artifact_id": _source_artifact_id(resource),
            "object_key": _source_object_key(resource),
        }
        for resource in source_resources
    )
    source_references = tuple(
        {
            key: value
            for key, value in payload.items()
            if key != "payload"
        }
        for payload in source_payloads
    )
    result = {
        "vehicle_id": vehicle_id,
        "requested_article_ids": tuple(requested_article_ids),
        "missing_article_ids": tuple(dict.fromkeys(missing_article_ids)),
        "article_list": deepcopy(article_list_payload),
        "article_details": article_details,
        "labor": labor,
        "parts": parts,
        "data_state": "source_unnormalized",
        "source_unnormalized": {
            "article_list": deepcopy(article_list_payload),
            "article_details": deepcopy(article_details),
            "labor": deepcopy(labor),
            "parts": deepcopy(parts_payload),
        },
        "source_resources": tuple(source_resources),
        "source_payloads": source_payloads,
        "source_references": source_references,
    }
    with connector._source_cache_lock:
        connector._required_source_cache[request_key] = deepcopy(result)
    return result

def _selector_rows(
    name_payload: Mapping[str, Any],
    motor_payload: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    default_region: str,
) -> list[dict[str, Any]]:
    name = _name_value(name_payload) or _first_text(target, "display_name")
    if not name:
        name = "{year} {make} {model}".format(**target)
    # The provider name includes trim/engine text (for example, ``RAV4 Base
    # 2.0L ...``). Preserve the user-selected base model as the canonical
    # identity while retaining provider engine data as configurations below.
    identity_input = dict(target)
    requested_model = _first_text(target, "requested_model")
    if requested_model:
        identity_input["model"] = requested_model
    try:
        identity = canonicalize_vehicle_observation(identity_input)
    except (TypeError, ValueError):
        identity = canonicalize_vehicle_observation(name)
    rows: list[dict[str, Any]] = [identity.to_dict()]
    for model in _items(motor_payload):
        model_name = _first_text(model, "modelName", "model", "name")
        if not model_name:
            continue
        trim = _trim_from_model_name(identity.model, model_name)
        engines = model.get("engines", []) if isinstance(model, Mapping) else []
        if not isinstance(engines, list) or not engines:
            row = identity.to_dict()
            if trim:
                row["trim"] = trim
            rows.append(row)
            continue
        for engine in engines:
            if not isinstance(engine, Mapping):
                continue
            row = identity.to_dict()
            if trim:
                row["trim"] = trim
            for key in ("name", "engineName", "engineDisplacementL", "displacement"):
                if engine.get(key) is not None:
                    row["engine"] = engine[key]
                    break
            rows.append(row)
    for row in rows:
        row.setdefault("region", default_region)
    return rows


def _rows_for_bundle(bundle: AutoAPIVehicleBundle) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [dict(bundle.vehicle)]
    rows.extend(
        {
            **bundle.vehicle,
            **{
                key: value
                for key, value in (
                    ("trim", configuration.get("trim")),
                    ("engine_displacement_l", configuration.get("engine_displacement_l")),
                )
                if value is not None
            },
        }
        for configuration in bundle.configurations
        if configuration.get("status") != "needs_review"
    )
    return rows


def _items(envelope: Mapping[str, Any]) -> list[Any]:
    body = envelope.get("body")
    if isinstance(body, list):
        return body
    if isinstance(body, Mapping):
        for key in ("vehicles", "models", "makes", "items", "results", "records", "rows"):
            value = body.get(key)
            if isinstance(value, list):
                return value
    return []


def _article_items(envelope: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    body = envelope.get("body")
    if isinstance(body, Mapping) and isinstance(body.get("articleDetails"), list):
        return [item for item in body["articleDetails"] if isinstance(item, Mapping)]
    return [item for item in _items(envelope) if isinstance(item, Mapping)]


def _required_resource_request_key(
    vehicle_id: str, operations: Iterable[Mapping[str, Any]]
) -> str:
    canonical_operations = sorted(
        (_canonical_request_value(operation) for operation in operations),
        key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")),
    )
    payload = json.dumps(
        {"vehicle_id": vehicle_id, "operations": canonical_operations},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return payload


def _canonical_request_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_request_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple, set)):
        values = [_canonical_request_value(item) for item in value]
        return sorted(
            values,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), default=str),
        )
    return value


def _operation_values(operation: Mapping[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = operation.get(key)
        if value is None:
            continue
        candidates = value if isinstance(value, (list, tuple, set)) else (value,)
        values.extend(str(candidate).strip() for candidate in candidates if str(candidate).strip())
    return list(dict.fromkeys(values))


def _normalized_text(value: Any) -> str:
    return " ".join(str(value).casefold().split())


def _is_labor_article_record(article: Mapping[str, Any]) -> bool:
    article_id = _first_text(article, "id", "articleId", "article_id") or ""
    bucket = _first_text(article, "bucket", "bucketName", "articleType") or ""
    return article_id.casefold().startswith("l:") or bucket.casefold() == "labor"


def _resource_payload(resource: SourceResource) -> Any:
    try:
        return json.loads(resource.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"raw_payload": resource.payload}


def _part_items(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    body = payload.get("body")
    if isinstance(body, list):
        return [item for item in body if isinstance(item, Mapping)]
    if isinstance(body, Mapping):
        for key in ("parts", "partDetails", "part_details", "items", "results", "records", "rows"):
            values = body.get(key)
            if isinstance(values, list):
                return [item for item in values if isinstance(item, Mapping)]
    return []


def _requested_parts(
    payload: Any,
    requested_part_ids: list[str],
    all_parts_requested: bool,
) -> list[dict[str, Any]]:
    parts = _part_items(payload)
    if all_parts_requested or not requested_part_ids:
        return [deepcopy(dict(part)) for part in parts]
    requested = {value.casefold() for value in requested_part_ids}
    return [
        deepcopy(dict(part))
        for part in parts
        if (
            _first_text(
                part,
                "partNumber",
                "part_number",
                "sourcePartNumber",
                "source_part_number",
                "id",
                "partId",
            )
            or ""
        ).casefold()
        in requested
    ]


def _canonical_price_snapshots(
    payload: Any,
    requested_part_ids: list[str],
    all_parts_requested: bool,
    source_resource: SourceResource | None,
) -> list[dict[str, Any]]:
    """Convert provider part rows into immutable, source-priced snapshots."""

    selected = _requested_parts(payload, requested_part_ids, all_parts_requested)
    if source_resource is None:
        return selected
    source_snapshot_id = _source_snapshot_id(source_resource)
    retrieved_at = source_resource.metadata.get("retrieved_at")
    now = datetime.now(UTC)
    snapshots: list[dict[str, Any]] = []
    for raw in selected:
        snapshot = deepcopy(raw)
        source_part_number = _first_text(
            raw,
            "source_part_number",
            "sourcePartNumber",
            "part_number",
            "partNumber",
            "id",
            "partId",
        )
        amount, currency = _provider_price(raw)
        priced_at = _first_text(
            raw,
            "priced_at",
            "pricedAt",
            "price_date",
            "priceDate",
            "last_updated",
            "lastUpdated",
            "updated_at",
            "updatedAt",
        ) or (str(retrieved_at).strip() if retrieved_at is not None else None)
        if not source_part_number or amount is None or currency is None or not priced_at:
            snapshot.update(
                {
                    "freshness": "unknown",
                    "refresh_status": "current",
                    "markup_applied": False,
                    "price_status": "needs_review",
                }
            )
            snapshots.append(snapshot)
            continue
        try:
            priced_at_utc = _provider_timestamp(priced_at)
            freshness = price_freshness(priced_at_utc, now)
        except ValueError:
            snapshot.update(
                {
                    "source_part_number": source_part_number,
                    "amount": amount,
                    "currency": currency,
                    "priced_at": priced_at,
                    "freshness": "unknown",
                    "refresh_status": "current",
                    "markup_applied": False,
                    "price_status": "needs_review",
                }
            )
            snapshots.append(snapshot)
            continue
        canonical_part_id = _canonical_part_id(raw, source_part_number)
        snapshot.update(
            {
                "canonical_part_id": canonical_part_id,
                "source_part_number": source_part_number,
                "amount": amount,
                "currency": currency,
                "priced_at": priced_at,
                "source_snapshot_id": source_snapshot_id,
                "parts_price_snapshot_id": _parts_price_snapshot_id(
                    canonical_part_id, source_snapshot_id, priced_at_utc
                ),
                "source_uri": source_resource.source_uri,
                "freshness": freshness,
                "refresh_status": "current",
                "markup_applied": False,
                "price_status": "normalized",
            }
        )
        snapshots.append(snapshot)
    return snapshots


def _provider_price(part: Mapping[str, Any]) -> tuple[float | None, str | None]:
    value: Any = None
    for key in ("amount", "price", "unit_price", "unitPrice", "source_price", "sourcePrice"):
        if part.get(key) is not None:
            value = part[key]
            break
    if isinstance(value, Mapping):
        currency = _first_text(value, "currency", "currencyCode", "unit")
        value = value.get("amount", value.get("value", value.get("price")))
    else:
        currency = None
    currency = currency or _first_text(part, "currency", "currencyCode", "source_currency")
    text = str(value).strip() if value is not None else ""
    if not text:
        return None, None
    if currency is None:
        for symbol, symbol_currency in (("$", "USD"), ("€", "EUR"), ("£", "GBP")):
            if symbol in text:
                currency = symbol_currency
                break
        if currency is None:
            match = re.search(r"\b([A-Za-z]{3})\b", text)
            if match:
                currency = match.group(1)
    match = re.search(r"(?<![A-Za-z])[+-]?\d[\d,]*(?:\.\d+)?", text)
    if match is None:
        return None, None
    try:
        amount = Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None, None
    if not amount.is_finite() or amount < 0 or currency is None:
        return None, None
    currency = currency.strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        return None, None
    return float(amount), currency


def _provider_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("provider priced_at must be timezone-aware")
    return parsed.astimezone(UTC)


def _canonical_part_id(part: Mapping[str, Any], source_part_number: str) -> str:
    supplied = _first_text(part, "canonical_part_id", "canonicalPartId")
    if supplied:
        return supplied
    slug = re.sub(r"[^a-z0-9]+", "-", source_part_number.casefold()).strip("-")
    return "part:" + (slug or hashlib.sha256(source_part_number.encode("utf-8")).hexdigest()[:16])


def _source_snapshot_id(resource: SourceResource) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"autodata-bundle:source-snapshot:{resource.content_sha256}",
        )
    )


def _source_artifact_id(resource: SourceResource) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"autodata-bundle:source-artifact:{resource.content_sha256}",
        )
    )


def _source_object_key(resource: SourceResource) -> str:
    return f"sources/{resource.content_sha256[:16]}/{resource.content_sha256}"


def _parts_price_snapshot_id(
    canonical_part_id: str, source_snapshot_id: str, priced_at: datetime
) -> str:
    identity = f"parts-price-snapshot:{canonical_part_id}:{source_snapshot_id}:{priced_at.isoformat()}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def _reported_article_count(envelope: Mapping[str, Any]) -> int | None:
    """Return AutoAPI's authoritative all-articles count when present."""

    body = envelope.get("body")
    if not isinstance(body, Mapping):
        return None
    filter_tabs = body.get("filterTabs")
    if isinstance(filter_tabs, list):
        for tab in filter_tabs:
            if not isinstance(tab, Mapping):
                continue
            if str(tab.get("name", "")).casefold() == "all":
                count = _nonnegative_int(tab.get("articlesCount"))
                if count is not None:
                    return count
    for key in ("articlesCount", "articleCount", "totalCount"):
        count = _nonnegative_int(body.get(key))
        if count is not None:
            return count
    return None


def _nonnegative_int(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _vehicle_ids_from_model(model: Any) -> list[str]:
    if not isinstance(model, Mapping):
        return []
    values = model.get("vehicleIds", model.get("vehicle_ids"))
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    nested = model.get("vehicles")
    if isinstance(nested, list):
        return [
            vehicle_id
            for vehicle in nested
            for vehicle_id in _vehicle_ids_from_model(vehicle)
        ]
    engines = model.get("engines")
    if isinstance(engines, list):
        engine_ids = [
            str(engine.get("id")).strip()
            for engine in engines
            if isinstance(engine, Mapping) and engine.get("id") is not None
        ]
        if engine_ids:
            return list(dict.fromkeys(value for value in engine_ids if value))
    for key in ("vehicleId", "vehicle_id"):
        if model.get(key) is not None:
            return [str(model[key]).strip()]
    for key in ("id", "modelId", "model_id"):
        if model.get(key) is not None:
            return [str(model[key]).strip()]
    return []


def _model_matches(model: Any, requested_model: str) -> bool:
    candidate = _first_text(model, "modelName", "model", "name", "vehicleModel")
    if not candidate:
        return False
    normalized = " ".join(candidate.split()).casefold()
    requested = " ".join(str(requested_model).split()).casefold()
    return normalized == requested or normalized.startswith(requested + " ")


def _chunks(values: list[str], size: int) -> tuple[list[str], ...]:
    return tuple(values[index : index + size] for index in range(0, len(values), size))


def _dedupe_vehicle_targets(values: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    seen: dict[str, dict[str, Any]] = {}
    for value in values:
        seen.setdefault(str(value["vehicle_id"]), value)
    return tuple(seen[key] for key in sorted(seen))


def _name_value(envelope: Mapping[str, Any]) -> str | None:
    body = envelope.get("body")
    if isinstance(body, str) and body.strip():
        return body.strip()
    if isinstance(body, Mapping):
        return _first_text(body, "name", "vehicleName", "displayName", "value")
    return None


def _first_text(value: Any, *keys: str) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in keys:
        candidate = value.get(key)
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    return None


def _required_text(value: Mapping[str, Any], key: str) -> str:
    result = _first_text(value, key)
    if not result:
        raise ValueError(f"AutoAPI target requires {key}")
    return result


def _year_value(value: Any) -> int:
    if isinstance(value, Mapping):
        value = value.get("year", value.get("modelYear", value.get("value")))
    year = int(str(value).strip())
    if year < 1886 or year > 2100:
        raise ValueError("AutoAPI returned an unsupported year")
    return year


def _trim_from_model_name(base_model: str, model_name: str) -> str | None:
    base = " ".join(str(base_model).split())
    candidate = " ".join(str(model_name).split())
    if candidate.casefold() == base.casefold():
        return None
    if candidate.casefold().startswith(base.casefold() + " "):
        return candidate[len(base):].strip() or None
    return candidate


def _build_uri(base_url: str, path: str, query: Mapping[str, str] | None) -> str:
    normalized_path = "/" + path.lstrip("/")
    uri = f"{base_url}{normalized_path}"
    return f"{uri}?{urlencode(query)}" if query else uri


def _read_bounded(response: Any, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(1024 * 1024, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"AutoAPI response exceeds maximum size of {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _request_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in (headers or {}).items():
        name = str(key).strip()
        content = str(value)
        if not name or any(character in name + content for character in "\r\n"):
            raise ValueError("AutoAPI request headers must not contain newlines")
        result[name] = content
    return result


def _opener_namespace(opener: Callable[..., Any]) -> str:
    if opener is urlopen:
        return ""
    try:
        with _SHARED_SOURCE_CACHE_LOCK:
            namespace = _OPENER_NAMESPACES.get(opener)
            if namespace is None:
                namespace = f"opener:{uuid.uuid4()}"
                _OPENER_NAMESPACES[opener] = namespace
            return namespace
    except TypeError:
        # Non-weak-referenceable callable instances are uncommon test or
        # embedding hooks. Keep their cache isolated without retaining them.
        return f"opener:{id(opener)}"


def _safe_error(error: Exception) -> str:
    return str(error).strip() or error.__class__.__name__


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, URLError)):
        return True
    if isinstance(error, HTTPError):
        return error.code in {408, 425, 429, 500, 502, 503, 504}
    message = str(error)
    return any(f"AutoAPI returned HTTP status {status}" in message for status in (408, 425, 429, 500, 502, 503, 504))


__all__ = [
    "AutoAPICatalog",
    "AutoAPIConnector",
    "AutoAPIVehicleBundle",
    "fetch_required_source_resources",
]
