"""Pure rules for selecting independent deep-lane work from viewable events."""

from __future__ import annotations

from typing import Any, Iterable


class ViewableEventError(ValueError):
    """A viewable event cannot be safely converted into deep-lane work."""


DEFAULT_DEEP_SECTIONS = (
    "diagnostics",
    "procedures",
    "electrical",
    "inventory",
    "maintenance",
    "search",
    "quality",
)


def deep_sections_from_event(envelope: dict[str, Any]) -> tuple[str, ...]:
    """Return a bounded, deterministic section list from a viewable event."""

    if not isinstance(envelope, dict):
        raise ViewableEventError("viewable event must be an object")
    if envelope.get("event_type") != "dataset.viewable":
        raise ViewableEventError("event type must be dataset.viewable")
    if envelope.get("event_version") != 1:
        raise ViewableEventError("event version must be 1")
    for field in ("event_id", "producer", "request_id", "projection_id", "correlation_id", "idempotency_key"):
        if not str(envelope.get(field, "")).strip():
            raise ViewableEventError(f"viewable event is missing {field}")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise ViewableEventError("viewable event payload must be an object")
    raw_sections = payload.get("deep_sections")
    if raw_sections is None:
        raw_sections = DEFAULT_DEEP_SECTIONS
    if not isinstance(raw_sections, (list, tuple)):
        raise ViewableEventError("deep_sections must be a list")
    sections: list[str] = []
    for raw_section in raw_sections:
        section = str(raw_section).strip().casefold()
        if not section or section in sections:
            continue
        if len(section) > 64 or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in section):
            raise ViewableEventError("deep section names must be lowercase tokens")
        sections.append(section)
    if not sections:
        raise ViewableEventError("viewable event must request at least one deep section")
    return tuple(sections)


def normalize_deep_sections(sections: Iterable[str]) -> tuple[str, ...]:
    """Normalize operator/configuration section lists using the event rules."""

    envelope = {
        "event_type": "dataset.viewable",
        "event_version": 1,
        "event_id": "configuration",
        "producer": "configuration",
        "request_id": "configuration",
        "projection_id": "configuration",
        "correlation_id": "configuration",
        "idempotency_key": "configuration",
        "payload": {"deep_sections": list(sections)},
    }
    return deep_sections_from_event(envelope)
