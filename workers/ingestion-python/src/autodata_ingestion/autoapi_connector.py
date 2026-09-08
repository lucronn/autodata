"""Client for the local AutoAPI read-only connector service.

The connector speaks only the documented ``/v1/api`` surface exposed by the
separate AutoAPI repository.  It preserves each response as a
``SourceResource`` so the existing universal adapter, provenance, evidence,
deduplication, and persistence boundaries remain authoritative.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .source_adapters import SourceResource
from .vehicle_identity import canonicalize_vehicle_observation
from .vehicle_selection import normalize_vehicle_list


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_CONCURRENCY = 8
DEFAULT_VEHICLE_ID_BATCH_SIZE = 100


@dataclass(frozen=True)
class AutoAPIVehicleBundle:
    """One AutoAPI vehicle and all fetched source resources for that vehicle."""

    vehicle_id: str
    content_source: str
    vehicle: dict[str, Any]
    configurations: tuple[dict[str, Any], ...]
    resources: tuple[SourceResource, ...]
    article_ids: tuple[str, ...]
    article_errors: tuple[dict[str, str], ...] = ()


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
                article_errors=bundle.article_errors,
            )
            for bundle in self.vehicles
        )


class AutoAPIConnector:
    """Traverse the local AutoAPI catalog and fetch every available article."""

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
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        vehicle_id_batch_size: int = DEFAULT_VEHICLE_ID_BATCH_SIZE,
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
            or max_concurrency < 1
            or vehicle_id_batch_size < 1
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
        self._max_concurrency = max_concurrency
        self._vehicle_id_batch_size = vehicle_id_batch_size
        self._request_headers = _request_headers(request_headers)
        self._opener = opener

    def fetch_catalog(self) -> AutoAPICatalog:
        """Fetch years, makes, models, vehicle identities, and all articles."""

        years_payload, _ = self._get_json("/v1/api/years")
        years = tuple(sorted({_year_value(item) for item in _items(years_payload)}))
        vehicle_targets: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for year in years:
            makes_scope = f"makes:{year}"
            try:
                makes_payload, _ = self._get_json(
                    f"/v1/api/year/{quote(str(year), safe='')}/makes"
                )
            except Exception as error:  # noqa: BLE001 - retain other years
                errors.append({"scope": makes_scope, "error": _safe_error(error)})
                continue
            for make in _items(makes_payload):
                make_name = _first_text(make, "makeName", "name", "make")
                if not make_name:
                    continue
                make_route_value = _first_text(make, "makeId", "id") or make_name
                models_scope = f"models:{year}:{make_route_value}"
                try:
                    models_payload, _ = self._get_json(
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
                        vehicles_payload, _ = self._get_json(
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
                                "model": _first_text(vehicle, "modelName", "model", "name") or "Unknown",
                                "vehicle_id": vehicle_id,
                                "display_name": _first_text(
                                    vehicle, "vehicleName", "displayName", "name"
                                ),
                            }
                        )

        bundles_list: list[AutoAPIVehicleBundle] = []
        for target in _dedupe_vehicle_targets(vehicle_targets):
            try:
                bundles_list.append(self.fetch_vehicle_bundle(target))
            except Exception as error:  # noqa: BLE001 - retain other vehicles
                errors.append(
                    {
                        "scope": f"vehicle:{target['vehicle_id']}",
                        "error": _safe_error(error),
                    }
                )
        bundles = tuple(bundles_list)
        selection_rows = tuple(
            row
            for bundle in bundles
            for row in _rows_for_bundle(bundle)
        )
        return AutoAPICatalog(years, selection_rows, bundles, tuple(errors))

    def fetch_vehicle_bundle(self, target: Mapping[str, Any]) -> AutoAPIVehicleBundle:
        """Fetch vehicle identity, engine configurations, article index, and details."""

        vehicle_id = _required_text(target, "vehicle_id")
        source_path = f"/v1/api/source/{quote(self._content_source, safe='')}/{quote(vehicle_id, safe='') }"
        resources: list[SourceResource] = []

        name_payload, name_resource = self._get_json(f"{source_path}/name")
        resources.append(name_resource)
        motor_payload, motor_resource = self._get_json(f"{source_path}/motorvehicles")
        resources.append(motor_resource)
        articles_payload, articles_resource = self._get_json(
            f"/v1/api/source/{quote(self._content_source, safe='')}/vehicle/{quote(vehicle_id, safe='')}/articles/v2"
        )
        resources.append(articles_resource)

        article_ids = tuple(
            dict.fromkeys(
                article_id
                for article in _article_items(articles_payload)
                if (article_id := _first_text(article, "id", "articleId", "article_id"))
            )
        )
        article_errors: list[dict[str, str]] = []
        details_path = f"/v1/api/source/{quote(self._content_source, safe='')}/vehicle/{quote(vehicle_id, safe='')}/article"
        with ThreadPoolExecutor(max_workers=self._max_concurrency) as executor:
            futures = {
                executor.submit(
                    self._get_json,
                    f"{details_path}/{quote(article_id, safe='')}",
                ): article_id
                for article_id in article_ids
            }
            for future in as_completed(futures):
                article_id = futures[future]
                try:
                    _payload, resource = future.result()
                except Exception as error:  # noqa: BLE001 - retain partial catalog progress
                    article_errors.append(
                        {"article_id": article_id, "error": _safe_error(error)}
                    )
                else:
                    resources.append(resource)

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
            article_errors=tuple(sorted(article_errors, key=lambda item: item["article_id"])),
        )

    def _get_json(
        self,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
    ) -> tuple[Any, SourceResource]:
        uri = _build_uri(self._base_url, path, query)
        headers = {"Accept": "application/json", "User-Agent": "autodata-ingestion/1", **self._request_headers}
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
            metadata={"connector": self.name, "http_status": status},
        )
        return parsed, resource


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
    for key in ("vehicleId", "vehicle_id"):
        if model.get(key) is not None:
            return [str(model[key]).strip()]
    for key in ("id", "modelId", "model_id"):
        if model.get(key) is not None:
            return [str(model[key]).strip()]
    return []


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


def _safe_error(error: Exception) -> str:
    return str(error).strip() or error.__class__.__name__


__all__ = ["AutoAPICatalog", "AutoAPIConnector", "AutoAPIVehicleBundle"]
