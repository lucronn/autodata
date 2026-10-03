"""Bounded HTTP client for the standalone AutoDBtwo source connector."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from typing import Any


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AutoDBtwoRequestError("connector returned an unexpected redirect")


class AutoDBtwoRequestError(RuntimeError):
    """Safe, source-level failure raised by the connector HTTP boundary."""


@dataclass(frozen=True)
class AutoDBtwoResponse:
    body: bytes
    content_type: str
    source_uri: str
    content_sha256: str


class AutoDBtwoHTTPClient:
    def __init__(
        self,
        base_url: str,
        *,
        upstream_base_url: str = "https://autoapitwo.vercel.app",
        opener: Any | None = None,
        timeout: float = 25,
        max_bytes: int = 8_000_000,
    ):
        parsed = urlsplit(str(base_url).strip())
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1", "autodbtwo"}
        if (
            parsed.scheme != "https" and not local_http
            or not parsed.netloc or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
        ):
            raise ValueError("AutoDBtwo URL must be a trusted HTTP(S) origin")
        upstream = urlsplit(str(upstream_base_url).strip())
        if upstream.scheme != "https" or not upstream.netloc or upstream.username or upstream.password:
            raise ValueError("AutoAPItwo base URL must be an HTTPS origin")
        if timeout <= 0 or max_bytes <= 0:
            raise ValueError("AutoDBtwo request limits must be positive")
        self.base_url = parsed.geturl().rstrip("/")
        self.upstream_base_url = f"{upstream.scheme}://{upstream.netloc}"
        self.opener = opener or build_opener(_NoRedirect()).open
        self.timeout = timeout
        self.max_bytes = max_bytes

    def read(self, source_uri: str, *, binary: bool = False, car_id: str | None = None) -> AutoDBtwoResponse:
        upstream = urlsplit(str(source_uri))
        if upstream.scheme != "https" or upstream.netloc != urlsplit(self.upstream_base_url).netloc or upstream.username or upstream.password or upstream.fragment:
            raise AutoDBtwoRequestError("source link leaves the configured AutoAPItwo origin")
        path = upstream.path
        path = _validate_source_path(path, car_id)
        source_query = upstream.query
        if path.startswith("/api/v1/fleet/"):
            if source_query:
                raise AutoDBtwoRequestError("fleet source links cannot include query parameters")
            route = "/v1/fleet/resource?" + urlencode({"path": path})
        else:
            match = re.fullmatch(r"/api/v1/content/carids/(\d+)/search/(.+)", path)
            if match and car_id is not None and match.group(1) == str(car_id) and not source_query:
                route = f"/v1/content/carids/{match.group(1)}/search/{quote(match.group(2), safe='')}"
            else:
                query = {"path": path}
                if source_query:
                    query["sourceQuery"] = source_query
                if binary:
                    query["binary"] = "true"
                route = f"/v1/content/carids/{_validate_car_id(car_id or _extract_car_id(path))}/resource?{urlencode(query)}"
        connector_url = self.base_url + route
        try:
            with self.opener(
                Request(connector_url, headers={"Accept": "image/*,application/octet-stream" if binary else "application/json"}),
                timeout=self.timeout,
            ) as response:
                final_url = response.geturl() if hasattr(response, "geturl") else connector_url
                if final_url != connector_url:
                    raise AutoDBtwoRequestError("connector returned an unexpected redirect")
                status = int(getattr(response, "status", getattr(response, "code", 200)))
                body = response.read(self.max_bytes + 1)
                headers = getattr(response, "headers", {}) or {}
        except HTTPError as error:
            code = _safe_connector_error(error)
            raise AutoDBtwoRequestError(code) from error
        except AutoDBtwoRequestError:
            raise
        except Exception as error:  # noqa: BLE001 - normalize transport failures
            raise AutoDBtwoRequestError("AutoDBtwo request failed") from error
        if len(body) > self.max_bytes:
            raise AutoDBtwoRequestError("AutoDBtwo response exceeded the configured size limit")
        if status < 200 or status >= 300:
            raise AutoDBtwoRequestError(f"AutoDBtwo returned HTTP {status}")
        source = str(_header(headers, "x-source-uri") or source_uri)
        if not source.startswith(self.upstream_base_url + "/"):
            raise AutoDBtwoRequestError("connector returned an invalid source reference")
        digest = sha256(body).hexdigest()
        advertised_hash = str(_header(headers, "x-content-sha256") or "").strip()
        if advertised_hash and not re.fullmatch(r"[a-fA-F0-9]{64}", advertised_hash):
            raise AutoDBtwoRequestError("connector returned an invalid source hash")
        if advertised_hash and advertised_hash.casefold() != digest:
            raise AutoDBtwoRequestError("connector source hash did not match the returned response")
        content_type = str(_header(headers, "content-type") or ("application/octet-stream" if binary else "application/json"))
        if not binary:
            try:
                json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise AutoDBtwoRequestError("AutoDBtwo returned invalid JSON") from error
        return AutoDBtwoResponse(body, content_type, source, digest)


def _validate_source_path(path: str, car_id: str | None) -> str:
    if "\\" in path or any(part in {".", ".."} for part in path.split("/")) or re.search(r"%(?:2f|5c|2e)", path, re.I):
        raise AutoDBtwoRequestError("source link contains an invalid path")
    if path.startswith("/api/v1/fleet/"):
        return path
    match = re.match(r"^/api/v1/content/carids/(\d+)/", path)
    if not match or (car_id is not None and match.group(1) != str(car_id)):
        raise AutoDBtwoRequestError("source content vehicle does not match request")
    return path


def _validate_car_id(value: str | None) -> str:
    if value is None or not re.fullmatch(r"\d{1,20}", str(value)):
        raise AutoDBtwoRequestError("source content vehicle ID must be numeric")
    return str(value)


def _extract_car_id(path: str) -> str | None:
    match = re.match(r"^/api/v1/content/carids/(\d+)/", path)
    return match.group(1) if match else None


def _header(headers: Any, key: str) -> Any:
    if hasattr(headers, "get"):
        return headers.get(key) or headers.get(key.title())
    return None


def _safe_connector_error(error: HTTPError) -> str:
    try:
        payload = json.loads(error.read(32_768))
    except Exception:  # noqa: BLE001 - provider error body is intentionally discarded
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        code = str(payload["error"].get("code") or "").strip()
        if code and re.fullmatch(r"[a-z0-9_]{1,64}", code):
            return f"AutoDBtwo {code} (HTTP {error.code})"
    return f"AutoDBtwo request failed (HTTP {error.code})"


__all__ = ["AutoDBtwoHTTPClient", "AutoDBtwoRequestError", "AutoDBtwoResponse"]
