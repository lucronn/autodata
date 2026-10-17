"""Bounded client for the independent Source Connector v1 HTTP contract.

Provider-specific authentication and upstream routes belong to the banks. This
module only accepts the public, versioned envelope and preserves source bytes.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
import re
import socket
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from .source_adapters import SourceResource


DEFAULT_MAX_BYTES = 20_000_000
DEFAULT_TIMEOUT_SECONDS = 25.0
_PROVIDERS = {"bankone": "autoapi", "banktwo": "autoapitwo"}
_ORIGINS = {"bankone": "https://bankone.cars.tk", "banktwo": "https://banktwo.cars.tk"}
_CAPABILITIES = {"catalog", "vehicle_resolution", "article_list", "article_search", "resource_read"}
_SCOPES = {"years", "makes", "models", "configurations"}
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SENSITIVE_QUERY_KEY = re.compile(r"token|sig(?:nature)?|key|auth|secret|password|session|cookie", re.I)


class SourceConnectorError(RuntimeError):
    """Sanitized connector failure with a stable retry decision."""

    def __init__(self, code: str, *, retryable: bool = False, status: int | None = None):
        self.code = code
        self.retryable = retryable
        self.status = status
        super().__init__(f"source connector {code.lower()}")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class SourceEnvelopeV1:
    request_id: str
    provider: str
    source_revision: str
    fetched_at: str
    source_locator: str | None
    body: Mapping[str, Any]
    resource_uri: str | None = None
    raw_resource: bytes | None = None

    @property
    def persisted_provider(self) -> str:
        return _PROVIDERS[self.provider]

    @property
    def complete(self) -> bool:
        return self.body.get("complete") is True

    @property
    def next_cursor(self) -> str | None:
        value = self.body.get("next_cursor")
        return value if isinstance(value, str) else None

    def to_source_resource(self) -> SourceResource:
        """Keep the original resource bytes and verify their declared hash."""

        kind = self.body.get("kind")
        if kind not in {"article", "labor", "text", "asset", "binary"}:
            raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
        if self.raw_resource is None:
            raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
        digest = hashlib.sha256(self.raw_resource).hexdigest()
        if digest != self.body.get("sha256"):
            raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
        locator = self.source_locator or self.resource_uri
        if not locator:
            raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
        return SourceResource.from_bytes(
            source_uri=locator,
            source_version=self.source_revision,
            payload=self.raw_resource,
            media_type=self.body["media_type"],
            locator=locator,
            metadata={
                "provider": self.persisted_provider,
                "source_provider": self.provider,
                "request_id": self.request_id,
                "fetched_at": self.fetched_at,
                "kind": kind,
                "source_sha256": digest,
            },
        )


class SourceConnectorClient:
    """Read a single bank origin using the shared `/v1` operations only."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        *,
        provider: str | None = None,
        opener: Any = None,
    ):
        parsed = urlsplit(str(base_url).strip())
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not (parsed.scheme == "https" or local_http)
            or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
            or parsed.port is not None and not 1 <= parsed.port <= 65535
        ):
            raise ValueError("source connector base URL must be a credential-free HTTPS origin")
        if provider is not None and provider not in _PROVIDERS:
            raise ValueError("unknown source connector provider")
        if timeout <= 0 or max_bytes <= 0:
            raise ValueError("source connector limits must be positive")
        if token is not None and (not token.strip() or "\r" in token or "\n" in token):
            raise ValueError("invalid source connector token")
        self.base_url = parsed.geturl().rstrip("/")
        self.provider = provider
        self._token = token
        self.timeout = timeout
        self.max_bytes = max_bytes
        self._opener = opener or build_opener(_NoRedirect()).open

    def capabilities(self) -> SourceEnvelopeV1:
        return self._read("GET", "/v1/capabilities", operation="capabilities")

    def catalog(
        self, scope: str, selector: Mapping[str, Any] | None = None, cursor: str | None = None
    ) -> SourceEnvelopeV1:
        if not isinstance(scope, str) or scope not in _SCOPES:
            raise ValueError("unsupported catalog scope")
        selector = selector or {}
        if not isinstance(selector, Mapping):
            raise ValueError("catalog selector must be a mapping")
        query: dict[str, str | int] = {}
        for key in ("year", "make", "model"):
            if key in selector and selector[key] is not None:
                query[key] = _selector_field(key, selector[key])
        if cursor is not None:
            query["cursor"] = _bounded_text(cursor, "cursor", 512)
        suffix = f"?{urlencode(query)}" if query else ""
        return self._read("GET", f"/v1/catalog/{scope}{suffix}", operation="catalog", scope=scope)

    def resolve_vehicle(self, selector: Mapping[str, Any]) -> SourceEnvelopeV1:
        if not isinstance(selector, Mapping):
            raise ValueError("vehicle selector must be a mapping")
        allowed = {"year", "make", "model", "configuration", "region", "vin"}
        if set(selector) - allowed or not {"year", "make", "model"}.issubset(selector):
            raise ValueError("invalid vehicle selector")
        value = {key: _selector_field(key, item) for key, item in selector.items()}
        return self._read("POST", "/v1/vehicle-resolutions", operation="resolution", payload=value)

    def list_articles(self, source_vehicle_ref: str, cursor: str | None = None) -> SourceEnvelopeV1:
        path = f"/v1/vehicles/{_opaque_ref(source_vehicle_ref, 1024)}/articles"
        if cursor is not None:
            path += "?" + urlencode({"cursor": _bounded_text(cursor, "cursor", 512)})
        return self._read("GET", path, operation="articles")

    def search_articles(
        self, source_vehicle_ref: str, query: str, cursor: str | None = None
    ) -> SourceEnvelopeV1:
        body = {"query": _bounded_text(query, "query", 512)}
        if cursor is not None:
            body["cursor"] = _bounded_text(cursor, "cursor", 512)
        return self._read(
            "POST", f"/v1/vehicles/{_opaque_ref(source_vehicle_ref, 1024)}/article-search",
            operation="articles", payload=body,
        )

    def read_resource(self, resource_ref: str) -> SourceEnvelopeV1:
        return self._read("GET", f"/v1/resources/{_opaque_ref(resource_ref, 2048)}", operation="resource")

    def _read(
        self, method: str, path: str, *, operation: str, payload: Mapping[str, Any] | None = None,
        scope: str | None = None,
    ) -> SourceEnvelopeV1:
        url = self.base_url + path
        data = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
        headers = {"Accept": "application/json, application/octet-stream", "User-Agent": "autodata-source-client/1"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener(request, timeout=self.timeout) as response:
                status = int(getattr(response, "status", getattr(response, "code", 200)))
                if status != 200:
                    raise _status_error(status)
                final_url = response.geturl() if hasattr(response, "geturl") else url
                if final_url != url:
                    raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
                response_headers = getattr(response, "headers", {})
                declared = _header(response_headers, "content-length")
                if declared is not None:
                    try:
                        if int(declared) > self.max_bytes or int(declared) < 0:
                            raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
                    except ValueError as error:
                        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE") from error
                raw = response.read(self.max_bytes + 1)
                if len(raw) > self.max_bytes:
                    raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
                media = (_header(response_headers, "content-type") or "").split(";", 1)[0].strip().lower()
                if operation == "resource" and media == "application/octet-stream":
                    return _binary_envelope(raw, response_headers, url, self.provider)
                if media != "application/json":
                    raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
                try:
                    body = json.loads(raw)
                except (UnicodeError, ValueError) as error:
                    raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE") from error
                return _validated_envelope(body, operation, self.provider, scope, url)
        except HTTPError as error:
            raise _status_error(error.code) from None
        except (URLError, socket.timeout, TimeoutError, ConnectionError) as error:
            raise SourceConnectorError("UPSTREAM_UNAVAILABLE", retryable=True) from None


def source_connector_registry(*, include_defaults: bool = False) -> dict[str, SourceConnectorClient]:
    """Create independently configured clients without sharing bank secrets."""

    result = {}
    for provider in _PROVIDERS:
        prefix = provider.upper()
        base_url = os.getenv(f"{prefix}_BASE_URL", "").strip()
        if not base_url and not include_defaults:
            continue
        result[provider] = SourceConnectorClient(
            base_url or _ORIGINS[provider],
            token=os.getenv(f"{prefix}_API_TOKEN") or None,
            provider=provider,
        )
    return result


def _status_error(status: int) -> SourceConnectorError:
    if 300 <= status < 400:
        return SourceConnectorError("INVALID_UPSTREAM_RESPONSE", status=status)
    code = {400: "INVALID_INPUT", 401: "UNAUTHORIZED", 403: "UNAUTHORIZED", 404: "NOT_FOUND", 409: "AMBIGUOUS", 429: "RATE_LIMITED"}.get(status)
    if code is None:
        code = "UPSTREAM_UNAVAILABLE" if status >= 500 else "INVALID_UPSTREAM_RESPONSE"
    return SourceConnectorError(code, retryable=status in {429, 502, 503, 504}, status=status)


def _header(headers: Any, name: str) -> str | None:
    if hasattr(headers, "get"):
        return headers.get(name) or headers.get(name.title())
    return None


def _opaque_ref(value: str, limit: int) -> str:
    ref = _bounded_text(value, "opaque reference", limit)
    if ref in {".", ".."} or any(ord(char) < 32 for char in ref):
        raise ValueError("invalid opaque reference")
    return quote(ref, safe="")


def _bounded_text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\r" in value or "\n" in value:
        raise ValueError(f"invalid {name}")
    return value


def _selector_field(name: str, value: Any) -> str | int:
    if name == "year":
        if isinstance(value, bool) or not isinstance(value, int) or not 1886 <= value <= 2200:
            raise ValueError("invalid selector year")
        return value
    limit = {"make": 160, "model": 160, "configuration": 512, "region": 64, "vin": 32}[name]
    return _bounded_text(value, name, limit)


def _validated_envelope(
    body: Any, operation: str, expected_provider: str | None, scope: str | None, url: str
) -> SourceEnvelopeV1:
    if not isinstance(body, dict):
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    required = {"request_id", "provider", "source_revision", "fetched_at"}
    if not required.issubset(body) or not isinstance(body["provider"], str) or body["provider"] not in _PROVIDERS:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    if expected_provider and body["provider"] != expected_provider:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    try:
        UUID(body["request_id"])
        fetched = datetime.fromisoformat(body["fetched_at"].replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as error:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE") from None
    if fetched.tzinfo is None or fetched.utcoffset() is None:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    if not isinstance(body["source_revision"], str) or not 1 <= len(body["source_revision"]) <= 256:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    locator = body.get("source_locator")
    if "source_locator" in body and (not isinstance(locator, str) or len(locator) > 2048 or not _safe_locator(locator)):
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    common = required | {"source_locator"}
    if operation == "capabilities":
        allowed = common | {"capabilities"}
        values = body.get("capabilities")
        valid = (isinstance(values, list) and all(isinstance(value, str) for value in values)
                 and len(values) == len(set(values)) and set(values) <= _CAPABILITIES)
    elif operation == "catalog":
        allowed = common | {"scope", "complete", "next_cursor", "items"}
        valid = body.get("scope") == scope and _valid_page(body) and _valid_rows(body.get("items"), "catalog", 1000)
    elif operation == "resolution":
        allowed = common | {"selector", "candidates"}
        valid = _valid_selector(body.get("selector")) and _valid_rows(body.get("candidates"), "candidate", 100)
    elif operation == "articles":
        allowed = common | {"complete", "next_cursor", "articles"}
        valid = _valid_page(body) and _valid_rows(body.get("articles"), "article", 1000)
    elif operation == "resource":
        kind = body.get("kind")
        valid = isinstance(kind, str) and kind in {"article", "labor", "text", "asset", "binary"}
        allowed = common | {"kind", "media_type", "sha256"}
        allowed |= {"content", "asset_resource_refs"} if kind in {"article", "labor", "text"} else {"content_base64"}
        valid = valid and isinstance(body.get("media_type"), str) and 0 < len(body["media_type"]) <= 128
        valid = valid and isinstance(body.get("sha256"), str) and bool(_SHA256.fullmatch(body["sha256"]))
        valid = valid and ("content" in body) != ("content_base64" in body)
        if valid and "content" in body:
            valid = kind in {"article", "labor", "text"} and isinstance(body["content"], str) and len(body["content"]) <= 10_000_000
        if valid and "content_base64" in body:
            valid = kind in {"asset", "binary"} and isinstance(body["content_base64"], str) and len(body["content_base64"]) <= 20_000_000
        if valid and "asset_resource_refs" in body:
            valid = _valid_ref_list(body["asset_resource_refs"], 128)
    else:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    if set(body) - allowed or not valid:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    raw_resource = None
    if operation == "resource":
        try:
            raw_resource = body["content"].encode("utf-8") if "content" in body else base64.b64decode(body["content_base64"], validate=True)
        except (UnicodeError, ValueError, binascii.Error):
            raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE") from None
        if hashlib.sha256(raw_resource).hexdigest() != body["sha256"]:
            raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    return SourceEnvelopeV1(body["request_id"], body["provider"], body["source_revision"], body["fetched_at"], locator, body, url if operation == "resource" else None, raw_resource)


def _valid_page(body: Mapping[str, Any]) -> bool:
    complete = body.get("complete")
    if not isinstance(complete, bool):
        return False
    if complete:
        return "next_cursor" not in body or body["next_cursor"] is None
    cursor = body.get("next_cursor")
    return isinstance(cursor, str) and 0 < len(cursor) <= 512


def _valid_selector(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) - {"year", "make", "model", "configuration", "region", "vin"}:
        return False
    if not {"year", "make", "model"}.issubset(value):
        return False
    if isinstance(value["year"], bool) or not isinstance(value["year"], int) or not 1886 <= value["year"] <= 2200:
        return False
    for key in set(value) - {"year"}:
        limit = {"make": 160, "model": 160, "configuration": 512, "region": 64, "vin": 32}[key]
        if not isinstance(value[key], str) or len(value[key]) > limit or (key in {"make", "model"} and not value[key]):
            return False
    return True


def _valid_rows(rows: Any, kind: str, max_items: int) -> bool:
    if not isinstance(rows, list) or len(rows) > max_items:
        return False
    for row in rows:
        if not isinstance(row, dict):
            return False
        if kind == "catalog":
            allowed = {"opaque_ref", "label", "year", "make", "model", "configuration", "engine", "drivetrain", "region", "source_label"}
            if not _valid_ref(row.get("opaque_ref"), 1024) or not _valid_label(row.get("label"), 512):
                return False
            if "year" in row and (isinstance(row["year"], bool) or not isinstance(row["year"], int)):
                return False
        elif kind == "candidate":
            allowed = {"opaque_ref", "label", "confidence", "evidence"}
            if not _valid_ref(row.get("opaque_ref"), 1024) or not _valid_label(row.get("label"), 512):
                return False
            if isinstance(row.get("confidence"), bool) or not isinstance(row.get("confidence"), (float, int)) or not 0 <= row["confidence"] <= 1:
                return False
            if "evidence" in row and (not isinstance(row["evidence"], list) or len(row["evidence"]) > 32 or not all(_valid_label(value, 512) for value in row["evidence"])):
                return False
        else:
            allowed = {"opaque_ref", "title", "category", "component", "labor_resource_ref", "resource_ref", "asset_resource_refs"}
            if not _valid_ref(row.get("opaque_ref"), 2048) or not _valid_label(row.get("title"), 1000):
                return False
            for key in ("labor_resource_ref", "resource_ref"):
                if key in row and not _valid_ref(row[key], 2048):
                    return False
            if "asset_resource_refs" in row and not _valid_ref_list(row["asset_resource_refs"], 128):
                return False
        if set(row) - allowed:
            return False
        for key in set(row) & {"make", "model", "configuration", "engine", "drivetrain", "region", "source_label", "category", "component"}:
            limit = {"make": 160, "model": 160, "configuration": 512, "engine": 256,
                     "drivetrain": 128, "region": 64, "source_label": 512,
                     "category": 256, "component": 256}[key]
            if not isinstance(row[key], str) or len(row[key]) > limit:
                return False
    return True


def _valid_label(value: Any, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit


def _valid_ref(value: Any, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit


def _valid_ref_list(value: Any, limit: int) -> bool:
    return isinstance(value, list) and len(value) <= limit and all(_valid_ref(item, 2048) for item in value)


def _safe_locator(value: str) -> bool:
    if any(ord(char) < 32 for char in value):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.username or parsed.password:
        return False
    return not any(_SENSITIVE_QUERY_KEY.search(key) for key, _ in parse_qsl(parsed.query, keep_blank_values=True))


def _binary_envelope(raw: bytes, headers: Any, url: str, expected_provider: str | None) -> SourceEnvelopeV1:
    values = {name: _header(headers, "x-" + name.replace("_", "-")) for name in ("request_id", "provider", "source_revision", "fetched_at", "source_locator", "source_sha256", "source_media_type")}
    if any(value is None for value in values.values()):
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    body = {
        "request_id": values["request_id"], "provider": values["provider"],
        "source_revision": values["source_revision"], "fetched_at": values["fetched_at"],
        "source_locator": values["source_locator"], "kind": "binary",
        "media_type": values["source_media_type"], "sha256": values["source_sha256"],
        "content_base64": base64.b64encode(raw).decode("ascii"),
    }
    return _validated_envelope(body, "resource", expected_provider, None, url)


__all__ = ["SourceConnectorClient", "SourceConnectorError", "SourceEnvelopeV1", "source_connector_registry"]
