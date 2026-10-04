"""Catalog-only traversal of AutoAPItwo's fleet vocabulary."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator
from copy import deepcopy
import json
import os
import re
import time
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .autodbtwo_http_client import AutoDBtwoHTTPClient, AutoDBtwoRequestError
from .source_adapters import SourceResource


class CatalogSourceUnavailable(RuntimeError):
    """Raised when the provider catalog cannot be read safely."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CatalogSourceUnavailable("unexpected catalog source redirect")


class AutoAPITwoCatalogConnector:
    """Read years, makes, models, engines, and summary vehicle identities."""

    source_version = "autoapitwo-fleet-v1"

    def __init__(
        self,
        base_url: str = "https://autoapitwo.vercel.app",
        *,
        opener=None,
        timeout: float = 25.0,
        max_bytes: int = 8_000_000,
        retry_attempts: int = 3,
        retry_delay: float = 0.25,
        cache_ttl: float = 300.0,
        connector_url: str | None = None,
    ):
        parsed = urlsplit(str(base_url).strip())
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("catalog source must be an HTTPS origin")
        if min(timeout, max_bytes, retry_attempts, cache_ttl) <= 0 or retry_delay < 0:
            raise ValueError("catalog source limits must be positive")
        self.base = base_url.rstrip("/")
        configured_connector_url = connector_url or os.getenv("AUTODATA_AUTODBTWO_BASE_URL")
        self._remote_client = (
            AutoDBtwoHTTPClient(
                configured_connector_url or "http://127.0.0.1:3001",
                upstream_base_url=self.base,
                opener=opener,
                timeout=timeout,
                max_bytes=max_bytes,
            )
            if configured_connector_url or opener is None
            else None
        )
        self.opener = opener or build_opener(_NoRedirect()).open
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.cache_ttl = cache_ttl
        self._cache: OrderedDict[str, tuple[float, object]] = OrderedDict()
        self._resources: OrderedDict[str, SourceResource] = OrderedDict()
        self._lock = RLock()

    def fetch_rows(self) -> list[dict[str, object]]:
        """Traverse only fleet vocabulary and return deterministic selector rows."""

        return list(self.iter_rows())

    def fetch_rows_with_provenance(self) -> tuple[list[dict[str, object]], tuple[SourceResource, ...]]:
        """Traverse the catalog and retain every raw provider response."""

        return self.fetch_rows(), tuple(self._resources.values())

    def fetch_catalog_snapshot(self) -> dict[str, object]:
        rows, resources = self.fetch_rows_with_provenance()
        return {
            "rows": rows,
            "complete": True,
            "provenance": [_resource_provenance(resource) for resource in resources],
            "source_resources": resources,
        }

    def fetch_years(self) -> list[str]:
        """Fetch only the provider year manifest for the lightweight bootstrap."""

        return self._years()

    def fetch_catalog_scope(self, request: Any) -> dict[str, object]:
        """Hydrate only the selector scope requested by the API.

        The full fleet walk is useful for a background warm-up, but a partial
        year must be repairable without replaying every year. Makes and models
        are obtained from the provider vocabulary endpoints; configurations
        additionally read the selected engine/car rows.
        """

        scope = str(getattr(request, "scope", "catalog")).strip()
        if scope not in {"makes", "models", "configurations"}:
            return self.fetch_catalog_snapshot()
        year = str(int(getattr(request, "year")))
        requested_make = _text(getattr(request, "make", ""))
        requested_model = _text(getattr(request, "model", ""))
        make_filter = "" if requested_make.casefold() in {"", "unknown"} else requested_make.casefold()
        model_filter = "" if requested_model.casefold() in {"", "unknown"} else requested_model.casefold()
        rows: list[dict[str, object]] = []
        makes_path = f"/api/v1/fleet/years/{quote(year)}/makes"
        for make_record in self._read_items(makes_path):
            make = _text(make_record.get("make"))
            if not make or (make_filter and make.casefold() != make_filter):
                continue
            models_path = (
                f"/api/v1/fleet/years/{quote(year)}/makes/{quote(make, safe='')}/models"
            )
            for model_record in self._read_items(models_path):
                model = _text(model_record.get("model"))
                if not model or (model_filter and model.casefold() != model_filter):
                    continue
                if scope in {"makes", "models"}:
                    rows.append({"year": int(year), "make": make, "model": model, "region": "US"})
                    continue
                engines_path = "/api/v1/fleet/years/{}/makes/{}/models/{}/engines".format(
                    quote(year, safe=""), quote(make, safe=""), quote(model, safe="")
                )
                for engine_record in self._read_items(engines_path):
                    engine = _text(engine_record.get("engine"))
                    car_path = _car_path(engine_record)
                    car = self._read(car_path) if car_path else dict(engine_record)
                    rows.append(_row(year, make, model, engine, car, car_path))
        return {
            "rows": rows,
            "complete": True,
            "provenance": [_resource_provenance(resource) for resource in self._resources.values()],
        }

    def iter_rows(self) -> Iterator[dict[str, object]]:
        """Yield normalized rows as each engine scope becomes available."""

        seen: set[tuple[object, ...]] = set()
        for year in self._years():
            makes_path = f"/api/v1/fleet/years/{quote(year)}/makes"
            for make_record in self._read_items(makes_path):
                make = _text(make_record.get("make"))
                if not make:
                    continue
                models_path = (
                f"/api/v1/fleet/years/{quote(year)}/makes/{quote(make, safe='')}/models"
            )
                for model_record in self._read_items(models_path):
                    model = _text(model_record.get("model"))
                    if not model:
                        continue
                    engines_path = "/api/v1/fleet/years/{}/makes/{}/models/{}/engines".format(
                        quote(year, safe=""), quote(make, safe=""), quote(model, safe="")
                    )
                    for engine_record in self._read_items(engines_path):
                        engine = _text(engine_record.get("engine"))
                        if not engine:
                            continue
                        car_path = _car_path(engine_record)
                        car = self._read(car_path) if car_path else dict(engine_record)
                        row = _row(year, make, model, engine, car, car_path)
                        key = (
                            row["year"],
                            str(row["make"]).casefold(),
                            str(row["model"]).casefold(),
                            str(row.get("engine") or "").casefold(),
                            str(row.get("autoapitwo_vehicle_id") or ""),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        yield row

    def _years(self) -> list[str]:
        values = []
        for item in self._read_items("/api/v1/fleet/years"):
            year = _text(item.get("year"))
            if year.isdigit() and 1886 <= int(year) <= 2100:
                values.append(year)
        return sorted(set(values), key=int)

    def _read_items(self, path: str) -> list[dict[str, object]]:
        payload = self._read(path)
        try:
            return self._items(payload)
        except CatalogSourceUnavailable:
            parsed = urlsplit(urljoin(self.base + "/", path))
            with self._lock:
                self._cache.pop(parsed.geturl(), None)
            raise

    def _read(self, path: str) -> object:
        parsed = urlsplit(urljoin(self.base + "/", path))
        if parsed.scheme != "https" or parsed.netloc != urlsplit(self.base).netloc:
            raise ValueError("catalog URL leaves the configured origin")
        if not unquote(parsed.path).startswith("/api/v1/fleet/"):
            raise ValueError("catalog connector only permits fleet endpoints")
        url = parsed.geturl()
        with self._lock:
            cached = self._cache.get(url)
            if cached and cached[0] > time.monotonic():
                return deepcopy(cached[1])
            if self._remote_client is not None:
                try:
                    response = self._remote_client.read(url)
                    value = json.loads(response.body)
                except (AutoDBtwoRequestError, json.JSONDecodeError) as error:
                    raise CatalogSourceUnavailable(str(error) or "AutoDBtwo catalog read failed") from error
                retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
                self._resources[response.source_uri] = SourceResource.from_bytes(
                    source_uri=response.source_uri,
                    source_version=self.source_version,
                    payload=response.body,
                    media_type=response.content_type,
                    locator=path,
                    metadata={
                        "provider": "autoapitwo",
                        "connector": "autodbtwo_catalog",
                        "content_sha256": response.content_sha256,
                        "retrieved_at": retrieved_at,
                    },
                )
                self._cache[url] = (time.monotonic() + self.cache_ttl, value)
                return deepcopy(value)
            for attempt in range(self.retry_attempts):
                try:
                    with self.opener(Request(url, headers={"Accept": "application/json"}), timeout=self.timeout) as response:
                        final_url = response.geturl() if hasattr(response, "geturl") else url
                        if final_url != url:
                            raise CatalogSourceUnavailable("unexpected catalog source redirect")
                        raw = response.read(self.max_bytes + 1)
                        if len(raw) > self.max_bytes:
                            raise CatalogSourceUnavailable("catalog response exceeds size limit")
                        value = json.loads(raw)
                        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
                        self._resources[url] = SourceResource.from_bytes(
                            source_uri=url,
                            source_version=self.source_version,
                            payload=raw,
                            media_type="application/json",
                            locator=path,
                            metadata={
                                "provider": "autoapitwo",
                                "connector": "autoapitwo_catalog",
                                "http_status": int(getattr(response, "status", getattr(response, "code", 200))),
                                "retrieved_at": retrieved_at,
                            },
                        )
                    break
                except CatalogSourceUnavailable:
                    raise
                except HTTPError as error:
                    if error.code not in {429, 502, 503, 504} or attempt + 1 >= self.retry_attempts:
                        raise CatalogSourceUnavailable("catalog source read failed") from error
                    if self.retry_delay:
                        time.sleep(self.retry_delay * (2**attempt))
                except Exception as error:  # noqa: BLE001 - normalize source boundary failures
                    if attempt + 1 >= self.retry_attempts:
                        raise CatalogSourceUnavailable("catalog source read failed") from error
                    if self.retry_delay:
                        time.sleep(self.retry_delay * (2**attempt))
            self._cache[url] = (time.monotonic() + self.cache_ttl, value)
            return deepcopy(value)

    @staticmethod
    def _items(payload: object) -> list[dict[str, object]]:
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = None
            for key in ("results", "items", "data"):
                if key in payload:
                    value = payload[key]
                    if isinstance(value, list):
                        items = value
                        break
                    if value is not None:
                        raise CatalogSourceUnavailable(
                            "catalog source returned a malformed response envelope"
                        )
            if items is None:
                raise CatalogSourceUnavailable("catalog source returned an unsupported response envelope")
        else:
            raise CatalogSourceUnavailable("catalog source returned an unsupported response shape")
        if not all(isinstance(item, dict) for item in items):
            raise CatalogSourceUnavailable("catalog source returned malformed catalog records")
        return items


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _car_path(engine_record: dict[str, object]) -> str | None:
    links = engine_record.get("_links")
    if isinstance(links, dict):
        car = links.get("car")
        if isinstance(car, dict) and isinstance(car.get("href"), str):
            href = car["href"]
            if "/api/v1/fleet/" in href:
                return href[href.index("/api/v1/fleet/") :]
    embedded = engine_record.get("_embedded")
    if isinstance(embedded, dict):
        car_id = _text(embedded.get("carId"))
        if car_id.isdigit():
            return f"/api/v1/fleet/carids/{car_id}"
    return None


def _row(year: str, make: str, model: str, engine: str, car: dict[str, object], source_locator: str | None) -> dict[str, object]:
    vehicle_id = _text(car.get("id")) or _text(car.get("carId"))
    mappings = []
    if vehicle_id.isdigit():
        mappings.append({"provider": "autoapitwo", "entity_type": "car", "provider_id": vehicle_id})
    for entity_type, key in (("aces_vehicle", "acesVehicleNames"), ("aces_engine", "acesEngineConfigNames"), ("aces_vec", "acesVehicleEngineConfigNames")):
        values = car.get(key, [])
        if not isinstance(values, list):
            continue
        for value in values:
            match = re.match(r"\s*(\d+)\s*:", str(value))
            if match:
                mappings.append({"provider": "autoapitwo", "entity_type": entity_type, "provider_id": match.group(1)})
    raw_engine = _text(car.get("engine")) or engine
    engine_displacement = _engine_displacement(raw_engine)
    row = {
        "year": int(_text(car.get("year")) or year),
        "make": _text(car.get("make")) or make,
        "model": _text(car.get("model")) or model,
        "engine": engine_displacement,
        "engine_label": raw_engine,
        "region": "CA" if _is_canadian(car) else "US",
        "provider_mappings": _unique_mappings(mappings),
    }
    if vehicle_id.isdigit():
        row["autoapitwo_vehicle_id"] = vehicle_id
    if source_locator:
        row["source_locator"] = source_locator
    description = _text(car.get("description"))
    for token in ("2WD", "4WD", "AWD"):
        if re.search(rf"\b{token}\b", description, re.IGNORECASE):
            row["drivetrain"] = token
            break
    return row


def _engine_displacement(value: str) -> float | None:
    match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*l(?:t|iter|itre)?\b", value.casefold())
    return float(match.group(1)) if match else None


def _is_canadian(car: dict[str, object]) -> bool:
    values = car.get("acesVehicleNames", [])
    text = " ".join(str(value) for value in values) if isinstance(values, list) else ""
    return bool(re.search(r"\bCAN(?:ADA)?\b", text, re.IGNORECASE)) and not bool(re.search(r"\bUSA\b", text, re.IGNORECASE))


def _unique_mappings(values: list[dict[str, str]]) -> list[dict[str, str]]:
    unique = {(item["entity_type"], item["provider_id"]): item for item in values}
    return [unique[key] for key in sorted(unique)]


def _resource_provenance(resource: SourceResource) -> dict[str, object]:
    return {
        "provider": "autoapitwo",
        "source_uri": resource.source_uri,
        "source_version": resource.source_version,
        "content_sha256": resource.content_sha256,
        "retrieved_at": resource.metadata.get("retrieved_at"),
        "metadata": dict(resource.metadata),
    }


__all__ = ["AutoAPITwoCatalogConnector", "CatalogSourceUnavailable"]
