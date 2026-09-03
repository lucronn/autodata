"""Provider-neutral HTTP(S) source connector with bounded resource capture."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .source_adapters import SourceResource


DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 30
_SENSITIVE_RESPONSE_HEADERS = {
    "authorization",
    "proxy-authenticate",
    "proxy-authorization",
    "set-cookie",
    "set-cookie2",
    "www-authenticate",
}


class HttpSourceConnector:
    """Fetch one HTTP(S) resource without interpreting its domain schema.

    The connector captures response metadata and raw bytes, while media type
    detection and candidate extraction remain in the shared intake layer.
    """

    name = "http"

    def __init__(
        self,
        source_uri: str,
        source_version: str | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        request_headers: dict[str, str] | None = None,
        opener: Callable[..., Any] = urlopen,
    ):
        self._source_uri = _validate_uri(source_uri)
        self._source_version = str(source_version or "").strip() or None
        if timeout_seconds <= 0:
            raise ValueError("HTTP timeout must be positive")
        if max_bytes <= 0:
            raise ValueError("maximum source size must be positive")
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._opener = opener
        self._request_headers = _request_headers(request_headers)

    def fetch(self, request: dict[str, Any]) -> list[SourceResource]:
        """Fetch the configured URI or a URI supplied by the request envelope."""

        uri = _validate_uri(str(request.get("source_uri", self._source_uri)))
        headers = {"User-Agent": "autodata-ingestion/1", **self._request_headers}
        http_request = Request(uri, headers=headers, method="GET")
        with self._opener(http_request, timeout=self._timeout_seconds) as response:
            status = int(getattr(response, "status", getattr(response, "code", 200)))
            if status >= 400:
                raise ValueError(f"source returned HTTP status {status}")
            headers = _response_headers(getattr(response, "headers", {}))
            declared_length = _content_length(headers)
            if declared_length is not None and declared_length > self._max_bytes:
                raise ValueError(f"source exceeds maximum source size of {self._max_bytes} bytes")
            payload = _read_bounded(response, self._max_bytes)
            content_sha256 = hashlib.sha256(payload).hexdigest()
            source_version = _source_version(request, self._source_version, headers, content_sha256)
            final_uri = str(response.geturl()) if hasattr(response, "geturl") else uri
            metadata = {
                "connector": self.name,
                "http_status": status,
                "retrieved_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "final_source_uri": final_uri,
                "response_headers": headers,
            }
            resource = SourceResource.from_bytes(
                source_uri=uri,
                source_version=source_version,
                payload=payload,
                media_type=headers.get("content-type"),
                locator=uri,
                metadata=metadata,
            )
        return [resource]


def _validate_uri(source_uri: str) -> str:
    uri = source_uri.strip()
    parsed = urlsplit(uri)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source URI must use an http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("source URI must not contain credentials")
    return uri


def _response_headers(headers: Any) -> dict[str, str]:
    if hasattr(headers, "items"):
        return {
            str(key).lower(): str(value).strip()
            for key, value in headers.items()
            if str(key).lower() not in _SENSITIVE_RESPONSE_HEADERS
        }
    return {}


def _request_headers(headers: dict[str, str] | None) -> dict[str, str]:
    normalized = {}
    for key, value in (headers or {}).items():
        name = str(key).strip()
        content = str(value)
        if not name or "\r" in name or "\n" in name or "\r" in content or "\n" in content:
            raise ValueError("request header names and values must not contain newlines")
        normalized[name] = content
    return normalized


def _content_length(headers: dict[str, str]) -> int | None:
    value = headers.get("content-length")
    if value is None:
        return None
    try:
        length = int(value)
    except ValueError:
        return None
    return length if length >= 0 else None


def _read_bounded(response: Any, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(1024 * 1024, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"source exceeds maximum source size of {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _source_version(
    request: dict[str, Any],
    configured_version: str | None,
    headers: dict[str, str],
    content_sha256: str,
) -> str:
    for candidate in (
        request.get("source_version"),
        configured_version,
        _strip_etag(headers.get("etag")),
        headers.get("last-modified"),
    ):
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    return f"content-sha256:{content_sha256}"


def _strip_etag(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.startswith('W/"') and normalized.endswith('"'):
        return normalized[3:-1]
    if len(normalized) >= 2 and normalized.startswith('"') and normalized.endswith('"'):
        return normalized[1:-1]
    return normalized
