"""Provider-neutral contract for executing one deep-lane section request."""

from __future__ import annotations

from dataclasses import dataclass
from re import fullmatch
from typing import Any, Callable


class DeepRequestError(ValueError):
    """A deep request is invalid or has no deployed section processor."""


@dataclass(frozen=True)
class DeepRequest:
    event_id: str
    request_id: str
    projection_id: str
    correlation_id: str
    idempotency_key: str
    section_name: str
    source_snapshot_id: str
    processing_version: str


_SECTION_PROCESSORS: dict[str, Callable[[DeepRequest], Any]] = {}


def register_section_processor(
    section_name: str,
    processor: Callable[[DeepRequest], Any],
) -> None:
    """Register section-specific extraction/publication behind the event boundary."""

    normalized_name = str(section_name).strip().casefold()
    if fullmatch(r"[a-z][a-z0-9_-]{1,63}", normalized_name) is None:
        raise ValueError("section name must be a stable lowercase token")
    _SECTION_PROCESSORS[normalized_name] = processor


def parse_deep_request(envelope: dict[str, Any]) -> DeepRequest:
    """Validate an event before any source or database side effect occurs."""

    if not isinstance(envelope, dict):
        raise DeepRequestError("deep event must be an object")
    if envelope.get("event_type") != "dataset.deep.requested":
        raise DeepRequestError("event type must be dataset.deep.requested")
    if envelope.get("event_version") != 1:
        raise DeepRequestError("event version must be 1")
    required_envelope_fields = (
        "event_id",
        "producer",
        "request_id",
        "projection_id",
        "correlation_id",
        "idempotency_key",
    )
    for field in required_envelope_fields:
        if not str(envelope.get(field, "")).strip():
            raise DeepRequestError(f"deep event is missing {field}")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise DeepRequestError("deep event payload must be an object")
    section_name = str(payload.get("section", "")).strip().casefold()
    if fullmatch(r"[a-z][a-z0-9_-]{1,63}", section_name) is None:
        raise DeepRequestError("deep event section must be a stable lowercase token")
    source_snapshot_id = str(payload.get("source_snapshot_id", "")).strip()
    if not source_snapshot_id:
        raise DeepRequestError("deep event is missing source_snapshot_id")
    processing_version = str(payload.get("processing_version", "")).strip()
    if not processing_version:
        raise DeepRequestError("deep event is missing processing_version")
    return DeepRequest(
        event_id=str(envelope["event_id"]).strip(),
        request_id=str(envelope["request_id"]).strip(),
        projection_id=str(envelope["projection_id"]).strip(),
        correlation_id=str(envelope["correlation_id"]).strip(),
        idempotency_key=str(envelope["idempotency_key"]).strip(),
        section_name=section_name,
        source_snapshot_id=source_snapshot_id,
        processing_version=processing_version,
    )


def dispatch_deep_request(envelope: dict[str, Any]) -> Any:
    """Route one validated request to its registered section processor."""

    request = parse_deep_request(envelope)
    return dispatch_validated_deep_request(request)


def dispatch_validated_deep_request(request: DeepRequest) -> Any:
    """Route a request already validated by the durable consumer."""

    if not isinstance(request, DeepRequest):
        raise DeepRequestError("deep dispatcher received an invalid request")
    processor = _SECTION_PROCESSORS.get(request.section_name)
    if processor is None:
        raise DeepRequestError(f"no processor is registered for section {request.section_name}")
    return processor(request)
