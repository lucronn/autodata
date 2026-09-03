"""Validation and source selection for version-one fast-lane requests."""

from __future__ import annotations

from dataclasses import dataclass
from re import fullmatch
from typing import Any, Callable


class FastLaneRequestError(ValueError):
    """A fast-lane event cannot be safely dispatched."""


_SOURCE_CONNECTORS: dict[str, Callable[["FastLaneRequest"], Any]] = {}


def register_source_connector(kind: str, factory: Callable[["FastLaneRequest"], Any]) -> None:
    """Register a provider-specific connector behind the universal boundary."""

    normalized_kind = str(kind).strip().casefold()
    if fullmatch(r"[a-z][a-z0-9_-]{1,31}", normalized_kind) is None:
        raise ValueError("source connector kind must be a stable lowercase token")
    _SOURCE_CONNECTORS[normalized_kind] = factory


@dataclass(frozen=True)
class SourceDescriptor:
    kind: str
    location: str
    version: str | None


@dataclass(frozen=True)
class FastLaneRequest:
    event_id: str
    request_id: str
    projection_id: str
    correlation_id: str
    idempotency_key: str
    vehicle_key: str
    region: str
    source: SourceDescriptor
    processing_version: str

    @classmethod
    def from_envelope(cls, envelope: dict[str, Any]) -> "FastLaneRequest":
        if not isinstance(envelope, dict):
            raise FastLaneRequestError("fast-lane event envelope must be an object")
        if envelope.get("event_type") != "dataset.fast.requested":
            raise FastLaneRequestError("fast-lane event type must be dataset.fast.requested")
        if envelope.get("event_version") != 1:
            raise FastLaneRequestError("fast-lane event version must be 1")
        for field in ("event_id", "request_id", "projection_id", "correlation_id", "idempotency_key"):
            if not str(envelope.get(field, "")).strip():
                raise FastLaneRequestError(f"fast-lane event is missing {field}")

        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise FastLaneRequestError("fast-lane event payload must be an object")
        vehicle_key = _required_text(payload, "vehicle_key")
        region = _required_text(payload, "region").upper()
        raw_source = payload.get("source")
        if not isinstance(raw_source, dict):
            raise FastLaneRequestError("fast-lane payload requires one source descriptor")
        kind = _required_text(raw_source, "kind").casefold()
        if fullmatch(r"[a-z][a-z0-9_-]{1,31}", kind) is None:
            raise FastLaneRequestError("fast-lane source kind must be a stable lowercase token")
        location = _required_text(raw_source, "location")
        version = str(raw_source.get("version", "")).strip() or None
        if kind == "directory" and version is None:
            raise FastLaneRequestError("directory source version is required")
        processing_version = str(payload.get("processing_version", "fast-v1")).strip()
        if not processing_version:
            raise FastLaneRequestError("fast-lane processing version is required")
        return cls(
            event_id=str(envelope["event_id"]).strip(),
            request_id=str(envelope["request_id"]).strip(),
            projection_id=str(envelope["projection_id"]).strip(),
            correlation_id=str(envelope["correlation_id"]).strip(),
            idempotency_key=str(envelope["idempotency_key"]).strip(),
            vehicle_key=vehicle_key,
            region=region,
            source=SourceDescriptor(kind, location, version),
            processing_version=processing_version,
        )


def connector_for_request(
    request: FastLaneRequest,
    *,
    request_headers: dict[str, str] | None = None,
    timeout_seconds: float = 30,
    max_bytes: int = 50 * 1024 * 1024,
) -> Any:
    """Build a connector from trusted configuration and a validated descriptor."""

    if request.source.kind == "directory":
        from .directory_connector import DirectorySourceConnector

        return DirectorySourceConnector(request.source.location, request.source.version or "")
    if request.source.kind == "http":
        from .http_connector import HttpSourceConnector

        return HttpSourceConnector(
            request.source.location,
            request.source.version,
            request_headers=request_headers,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
        )
    factory = _SOURCE_CONNECTORS.get(request.source.kind)
    if factory is None:
        raise FastLaneRequestError(
            f"no source connector is registered for kind {request.source.kind}"
        )
    return factory(request)


def _required_text(container: dict[str, Any], field: str) -> str:
    value = str(container.get(field, "")).strip()
    if not value:
        raise FastLaneRequestError(f"fast-lane payload requires {field}")
    return value
