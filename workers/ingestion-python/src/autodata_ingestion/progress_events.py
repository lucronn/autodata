"""Replayable, redacted progress events for one chat query.

The production event boundary is deliberately small.  A JetStream or database
adapter can forward the dictionaries emitted here, while the in-process store
keeps local tests deterministic and gives the HTTP service a bounded replay
surface.  Event identity is derived from the query, stage, status, and payload;
publishing the same logical event twice therefore returns the original event.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
import re
import threading
import uuid
from typing import Any


EVENT_VERSION = 1
DEFAULT_MAX_ATTEMPTS = 3
REDACTED_SECRET = "[REDACTED_SECRET]"
MAX_ERROR_TEXT = 512
MAX_EVENT_PAYLOAD_BYTES = 64 * 1024
DATA_STATE_VALUES = frozenset(
    {
        "normalized",
        "source_unnormalized",
        "stale",
        "normalizing",
        "mixed",
        "unavailable",
        "needs_review",
    }
)
PROGRESS_STATUS_VALUES = frozenset({"queued", "processing", "completed", "failed", "dead_letter"})

_SECRET_KEY_PATTERN = re.compile(
    r"(?:authorization|api[_-]?key|access[_-]?key|client[_-]?secret|credential|"
    r"password|private[_-]?key|refresh[_-]?token|secret|token)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[^\s,;]+"),
    re.compile(
        r"(?i)(\b(?:authorization|api[_-]?key|access[_-]?key|client[_-]?secret|"
        r"password|private[_-]?key|refresh[_-]?token|secret|token)\s*['\"]?\s*[:=]\s*)"
        r"([^\s,;]+)"
    ),
    re.compile(r"(?i)(https?://)([^/@\s:]+):([^/@\s]+)@"),
    re.compile(
        r"(?i)([?&](?:authorization|api[_-]?key|access[_-]?key|client[_-]?secret|"
        r"password|private[_-]?key|refresh[_-]?token|secret|token)=)[^&#\s]+"
    ),
    re.compile(r"\b(?:ghp|github_pat|sk|rk)_[A-Za-z0-9_-]+\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)

_EVENT_TYPES = {
    "answer": "chat.answer.updated",
    "answer_update": "chat.answer.updated",
    "publication": "chat.answer.updated",
    "vehicle_options": "chat.vehicle.options",
    "price_refresh": "chat.price.refresh.requested",
    "procedure": "chat.procedure.published",
    "procedure_composition": "chat.procedure.published",
    "visual": "chat.visual.published",
}


def redact_secrets(value: Any) -> Any:
    """Return a JSON-compatible copy with credential-like values removed."""

    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            output[key_text] = (
                REDACTED_SECRET
                if _SECRET_KEY_PATTERN.search(key_text)
                else redact_secrets(child)
            )
        return output
    if isinstance(value, (list, tuple, set)):
        return [redact_secrets(child) for child in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    redacted = value
    redacted = _SECRET_VALUE_PATTERNS[0].sub(
        lambda match: f"{match.group(1)}{REDACTED_SECRET}", redacted
    )
    redacted = _SECRET_VALUE_PATTERNS[1].sub(
        lambda match: f"{match.group(1)}{REDACTED_SECRET}", redacted
    )
    redacted = _SECRET_VALUE_PATTERNS[2].sub(
        lambda match: f"{match.group(1)}{REDACTED_SECRET}@", redacted
    )
    redacted = _SECRET_VALUE_PATTERNS[3].sub(
        lambda match: f"{match.group(1)}{REDACTED_SECRET}", redacted
    )
    for pattern in _SECRET_VALUE_PATTERNS[4:]:
        redacted = pattern.sub(REDACTED_SECRET, redacted)
    return redacted


def sanitize_text(value: Any, *, limit: int = MAX_ERROR_TEXT) -> str:
    """Redact and bound text before it crosses a persisted or HTTP boundary."""

    text = _redact_text(str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _stable_uuid(kind: str, value: Any) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata:chat:{kind}:v1:{value}"))


def _contract_uuid(kind: str, value: Any) -> str:
    text = str(value or "").strip()
    try:
        return str(uuid.UUID(text))
    except (ValueError, AttributeError):
        return _stable_uuid(kind, text)


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ProgressEventStore:
    """Thread-safe event history with deterministic idempotency and retries."""

    _current: Any = None
    _current_lock = threading.Lock()

    def __init__(self, *, max_events_per_query: int = 1000) -> None:
        if max_events_per_query < 1:
            raise ValueError("max_events_per_query must be positive")
        self._lock = threading.RLock()
        self._contexts: dict[str, dict[str, str]] = {}
        self._events: dict[str, list[dict[str, Any]]] = {}
        self._by_idempotency: dict[str, dict[str, Any]] = {}
        self._retry_attempts: dict[tuple[str, str], int] = {}
        self._retry_terminal: dict[tuple[str, str], dict[str, Any]] = {}
        self._max_events_per_query = max_events_per_query
        self.durable = False

    @classmethod
    def current(cls) -> Any:
        with cls._current_lock:
            if cls._current is None:
                cls._current = cls()
            return cls._current

    @classmethod
    def set_current(cls, store: Any) -> None:
        if store is None or not all(hasattr(store, name) for name in ("publish", "iter_events", "retry", "register_context")):
            raise TypeError("progress event store must implement the chat event boundary")
        with cls._current_lock:
            cls._current = store

    def register_context(
        self,
        query_id: str,
        *,
        correlation_id: str | None = None,
        request_id: str | None = None,
        projection_id: str | None = None,
        owner_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, str]:
        query_text = _required_text(query_id, "query_id")
        with self._lock:
            context = self._contexts.setdefault(
                query_text,
                {
                    "correlation_id": _contract_uuid("correlation", correlation_id or query_text),
                    "request_id": _contract_uuid("request", request_id or query_text),
                    "projection_id": _contract_uuid("projection", projection_id or query_text),
                },
            )
            for key, value in (("owner_id", owner_id), ("organization_id", organization_id)):
                if value is not None and str(value).strip():
                    context[key] = str(value).strip()
            for key, value, kind in (
                ("correlation_id", correlation_id, "correlation"),
                ("request_id", request_id, "request"),
                ("projection_id", projection_id, "projection"),
            ):
                if value is not None and str(value).strip():
                    context[key] = _contract_uuid(kind, value)
            return dict(context)

    def publish(
        self,
        query_id: str,
        stage: str,
        status: str,
        *,
        data_state: str,
        payload: Mapping[str, Any],
        event_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        query_text = _required_text(query_id, "query_id")
        stage_text = _required_text(stage, "stage")
        status_text = _required_text(status, "status")
        data_state_text = _required_text(data_state, "data_state")
        if status_text not in PROGRESS_STATUS_VALUES:
            raise ValueError(f"unsupported progress status: {status_text}")
        if data_state_text not in DATA_STATE_VALUES:
            raise ValueError(f"unsupported data state: {data_state_text}")
        if not isinstance(payload, Mapping):
            raise TypeError("progress event payload must be a mapping")
        safe_payload = _compact_event_payload(redact_secrets(dict(payload)))
        # These correlation fields are owned by the event envelope. Override
        # caller values so an embedded provider payload cannot cross-query a
        # replay stream or disagree with its envelope.
        safe_payload["query_id"] = query_text
        safe_payload["stage"] = stage_text
        safe_payload["status"] = status_text
        safe_payload["data_state"] = data_state_text
        serialized = json.dumps(_stable_for_idempotency(safe_payload), sort_keys=True, separators=(",", ":"), default=str)
        logical_key = sanitize_text(idempotency_key, limit=256) if idempotency_key else hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        event_idempotency_key = f"chat-progress:v1:{query_text}:{logical_key}"
        if len(serialized.encode("utf-8")) > MAX_EVENT_PAYLOAD_BYTES:
            safe_payload = {
                "message": sanitize_text(safe_payload.get("message") or f"{stage_text} {status_text}"),
                "payload_truncated": True,
                "payload_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
                "query_id": query_text,
                "stage": stage_text,
                "status": status_text,
                "data_state": data_state_text,
            }
        with self._lock:
            existing = self._by_idempotency.get(event_idempotency_key)
            if existing is not None:
                return deepcopy(existing)
            context = self.register_context(query_text)
            event_id = _stable_uuid("event", event_idempotency_key)
            revision_value = safe_payload.get("revision_id") or safe_payload.get("answer_revision_id")
            revision_id = _contract_uuid("revision", revision_value) if revision_value else None
            message = str(safe_payload.get("message") or f"{stage_text} {status_text}").strip()
            event = {
                "event_id": event_id,
                "event_type": event_type or _EVENT_TYPES.get(stage_text, "chat.worker.progress"),
                "event_version": EVENT_VERSION,
                "occurred_at": _timestamp(),
                "producer": str(safe_payload.get("producer") or "ingestion-python-chat"),
                "request_id": context["request_id"],
                "projection_id": context["projection_id"],
                "revision_id": revision_id,
                "correlation_id": context["correlation_id"],
                "idempotency_key": event_idempotency_key,
                "payload": safe_payload,
                "query_id": query_text,
                "stage": stage_text,
                "status": status_text,
                "data_state": data_state_text,
                "message": _redact_text(message),
            }
            events = self._events.setdefault(query_text, [])
            events.append(event)
            if len(events) > self._max_events_per_query:
                removed = events[: len(events) - self._max_events_per_query]
                del events[: len(removed)]
                for old_event in removed:
                    old_key = old_event.get("idempotency_key")
                    if old_key:
                        self._by_idempotency.pop(str(old_key), None)
            self._by_idempotency[event_idempotency_key] = event
            return deepcopy(event)

    def iter_events(
        self,
        query_id: str,
        *,
        last_event_id: str | None = None,
        principal: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        query_text = _required_text(query_id, "query_id")
        with self._lock:
            _authorize_context(self._contexts.get(query_text), principal)
            events = [deepcopy(event) for event in self._events.get(query_text, [])]
        if last_event_id:
            event_text = str(last_event_id).strip()
            for index, event in enumerate(events):
                if event.get("event_id") == event_text:
                    events = events[index + 1 :]
                    break
        yield from events

    def retry(
        self,
        query_id: str,
        stage: str,
        error: Exception,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> dict[str, Any]:
        query_text = _required_text(query_id, "query_id")
        stage_text = _required_text(stage, "stage")
        if max_attempts < 1:
            raise ValueError("maximum chat attempts must be positive")
        key = (query_text, stage_text)
        with self._lock:
            terminal = self._retry_terminal.get(key)
            if terminal is not None:
                return deepcopy(terminal)
            attempt = self._retry_attempts.get(key, 0) + 1
            self._retry_attempts[key] = attempt
        safe_error = redact_secrets(
            {
                "error_type": type(error).__name__,
                "message": sanitize_text(str(error).strip() or type(error).__name__),
            }
        )
        exhausted = attempt >= max_attempts
        event = self.publish(
            query_text,
            stage_text,
            "dead_letter" if exhausted else "failed",
            data_state="unavailable",
            payload={
                "attempt": attempt,
                "max_attempts": max_attempts,
                "retryable": not exhausted,
                "error": safe_error,
                "message": (
                    f"{stage_text} exhausted retry limit"
                    if exhausted
                    else f"{stage_text} failed; retry {attempt + 1} is allowed"
                ),
            },
            idempotency_key=f"retry:{stage_text}:{attempt}",
        )
        result = {
            "status": "dead_letter" if exhausted else "retrying",
            "attempt": attempt,
            "max_attempts": max_attempts,
            "retryable": not exhausted,
            "event": event,
            "error": safe_error,
        }
        if exhausted:
            with self._lock:
                self._retry_terminal[key] = deepcopy(result)
        return result


def register_query_context(
    query_id: str,
    *,
    correlation_id: str | None = None,
    request_id: str | None = None,
    projection_id: str | None = None,
    owner_id: str | None = None,
    organization_id: str | None = None,
) -> dict[str, str]:
    return ProgressEventStore.current().register_context(
        query_id,
        correlation_id=correlation_id,
        request_id=request_id,
        projection_id=projection_id,
        owner_id=owner_id,
        organization_id=organization_id,
    )


def publish_progress_event(
    query_id: str,
    stage: str,
    status: str,
    *,
    data_state: str,
    payload: Mapping[str, Any],
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    return ProgressEventStore.current().publish(
        query_id,
        stage,
        status,
        data_state=data_state,
        payload=payload,
        idempotency_key=idempotency_key,
    )


def record_chat_retry(
    query_id: str,
    stage: str,
    error: Exception,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    return ProgressEventStore.current().retry(
        query_id,
        stage,
        error,
        max_attempts=max_attempts,
    )


def iter_progress_events(
    query_id: str,
    *,
    last_event_id: str | None = None,
    principal: Mapping[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    return ProgressEventStore.current().iter_events(
        query_id,
        last_event_id=last_event_id,
        principal=principal,
    )


def event_to_sse(event: Mapping[str, Any]) -> str:
    """Encode one event as a bounded-compatible Server-Sent Events frame."""

    if not isinstance(event, Mapping):
        raise TypeError("SSE event must be a mapping")
    event_id = _required_text(event.get("event_id"), "event_id")
    event_type = _required_text(event.get("event_type"), "event_type")
    data = json.dumps(redact_secrets(dict(event)), ensure_ascii=False, sort_keys=True, default=str)
    return f"id: {event_id}\nevent: {event_type}\ndata: {data}\n\n"


def reset_progress_events() -> None:
    ProgressEventStore.set_current(ProgressEventStore())


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _stable_for_idempotency(value: Any) -> Any:
    if isinstance(value, Mapping):
        volatile = {"occurred_at", "updated_at", "worker_stream", "updates", "history"}
        return {
            str(key): _stable_for_idempotency(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key).casefold() not in volatile
        }
    if isinstance(value, (list, tuple, set)):
        return [_stable_for_idempotency(child) for child in value]
    return value


def _compact_event_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    compact = dict(payload)
    answer = compact.get("answer")
    if isinstance(answer, Mapping):
        summary: dict[str, Any] = {
            key: answer[key]
            for key in ("answer_status", "data_state", "revision_id", "source_watermark")
            if key in answer
        }
        vehicle = answer.get("vehicle")
        if isinstance(vehicle, Mapping):
            summary["vehicle"] = {
                key: vehicle[key]
                for key in ("vehicle_id", "candidate_key", "year", "make", "model", "region")
                if key in vehicle
            }
        summary["procedure_available"] = answer.get("procedure") is not None
        summary["quote_available"] = answer.get("quote") is not None
        if isinstance(answer.get("source_unnormalized"), Mapping):
            raw = answer["source_unnormalized"]
            summary["source_article_count"] = len(raw.get("articles", ())) if isinstance(raw.get("articles"), list) else 0
        compact["answer"] = summary
    for key in ("history", "updates", "worker_stream"):
        compact.pop(key, None)
    for key in ("revision_id", "answer_revision_id"):
        if compact.get(key):
            compact[key] = _contract_uuid("revision", compact[key])
    if isinstance(compact.get("answer"), Mapping) and compact["answer"].get("revision_id"):
        compact["answer"]["revision_id"] = _contract_uuid("revision", compact["answer"]["revision_id"])
    return compact


def _authorize_context(context: Mapping[str, Any] | None, principal: Mapping[str, Any] | None) -> None:
    if not context or not (context.get("owner_id") or context.get("organization_id")):
        return
    if not isinstance(principal, Mapping):
        raise PermissionError("chat owner authorization is required")
    owner = str(principal.get("owner_id") or principal.get("user_id") or principal.get("subject") or "").strip()
    organization = str(principal.get("organization_id") or principal.get("org_id") or "").strip()
    if context.get("owner_id") and context.get("owner_id") != owner:
        raise PermissionError("chat owner authorization failed")
    if context.get("organization_id") and context.get("organization_id") != organization:
        raise PermissionError("chat organization authorization failed")


__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "EVENT_VERSION",
    "DATA_STATE_VALUES",
    "MAX_ERROR_TEXT",
    "MAX_EVENT_PAYLOAD_BYTES",
    "PROGRESS_STATUS_VALUES",
    "ProgressEventStore",
    "REDACTED_SECRET",
    "event_to_sse",
    "iter_progress_events",
    "publish_progress_event",
    "record_chat_retry",
    "redact_secrets",
    "sanitize_text",
    "register_query_context",
    "reset_progress_events",
]
