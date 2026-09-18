"""Catalog-only traversal of AutoAPItwo's fleet vocabulary."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator
from copy import deepcopy
import json
import re
import time
from threading import RLock
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


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
        self.opener = opener or build_opener(_NoRedirect()).open
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.cache_ttl = cache_ttl
        self._cache: OrderedDict[str, tuple[float, object]] = OrderedDict()
        self._lock = RLock()

    def fetch_rows(self) -> list[dict[str, object]]:
        """Traverse only fleet vocabulary and return deterministic selector rows."""

        return list(self.iter_rows())

    def fetch_years(self) -> list[str]:
        """Fetch only the provider year manifest for the lightweight bootstrap."""

        return self._years()

    def iter_rows(self) -> Iterator[dict[str, object]]:
        """Yield normalized rows as each engine scope becomes available."""

        seen: set[tuple[object, ...]] = set()
        for year in self._years():
            makes = self._read(f"/api/v1/fleet/years/{quote(year)}/makes")
            for make_record in self._items(makes):
                make = _text(make_record.get("make"))
                if not make:
                    continue
                models = self._read(
                    f"/api/v1/fleet/years/{quote(year)}/makes/{quote(make, safe='')}/models"
                )
                for model_record in self._items(models):
                    model = _text(model_record.get("model"))
                    if not model:
                        continue
                    engines = self._read(
                        "/api/v1/fleet/years/{}/makes/{}/models/{}/engines".format(
                            quote(year, safe=""),
                            quote(make, safe=""),
                            quote(model, safe=""),
                        )
                    )
                    for engine_record in self._items(engines):
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
        payload = self._read("/api/v1/fleet/years")
        values = []
        for item in self._items(payload):
            year = _text(item.get("year"))
            if year.isdigit() and 1886 <= int(year) <= 2100:
                values.append(year)
        return sorted(set(values), key=int)

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
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("results", "items", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []


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


__all__ = ["AutoAPITwoCatalogConnector", "CatalogSourceUnavailable"]
