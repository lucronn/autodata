"""PostgreSQL-backed shared state for the chat HTTP and worker processes."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
import uuid
from typing import Any

from .progress_events import (
    DATA_STATE_VALUES,
    DEFAULT_MAX_ATTEMPTS,
    EVENT_VERSION,
    MAX_EVENT_PAYLOAD_BYTES,
    PROGRESS_STATUS_VALUES,
    _authorize_context,
    _compact_event_payload,
    _contract_uuid,
    _redact_text,
    _stable_for_idempotency,
    _stable_uuid,
    redact_secrets,
    sanitize_text,
)


DEFAULT_QUEUE_LEASE_SECONDS = 60
DEFAULT_MAX_EVENTS_PER_QUERY = 1000
_WORK_KINDS = frozenset({"source", "price_refresh"})
_OpenConnection = Callable[[], Any]


def _conflict() -> Exception:
    from .chat_service import ChatConflictError

    return ChatConflictError("idempotency key conflicts with a different chat request")


class _PostgresAdapter:
    def __init__(self, *, open_connection: _OpenConnection | None = None) -> None:
        self._open_connection = open_connection or _open_postgres_from_environment
        self.durable = True

    def _open(self) -> Any:
        return self._open_connection()


class PostgresChatRepository(_PostgresAdapter):
    """Persist the complete redacted internal query snapshot."""

    def save(self, query: Mapping[str, Any]) -> None:
        if not isinstance(query, Mapping):
            raise TypeError("chat query must be a mapping")
        safe = redact_secrets(deepcopy(dict(query)))
        query_id = _required_text(safe.get("query_id"), "query_id")
        idempotency_key = _required_text(safe.get("idempotency_key"), "idempotency_key")
        fingerprint = _required_text(safe.get("request_fingerprint"), "request_fingerprint")
        owner_id = _optional_text(safe.get("owner_id"))
        organization_id = _optional_text(safe.get("organization_id"))
        snapshot = _json(safe)
        try:
            with self._open() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        /* repository.save */
                        INSERT INTO chat_runtime_queries
                            (query_id, idempotency_key, request_fingerprint,
                             owner_id, organization_id, query_snapshot)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (idempotency_key) DO UPDATE
                        SET owner_id = EXCLUDED.owner_id,
                            organization_id = EXCLUDED.organization_id,
                            query_snapshot = EXCLUDED.query_snapshot,
                            updated_at = now()
                        WHERE chat_runtime_queries.query_id = EXCLUDED.query_id
                          AND chat_runtime_queries.request_fingerprint = EXCLUDED.request_fingerprint
                        RETURNING query_id, request_fingerprint
                        """,
                        (
                            query_id,
                            idempotency_key,
                            fingerprint,
                            owner_id,
                            organization_id,
                            snapshot,
                        ),
                    )
                    row = cursor.fetchone()
        except Exception as error:
            if getattr(error, "sqlstate", None) == "23505":
                raise _conflict() from error
            raise
        if row is None or str(row[0]) != query_id or str(row[1]) != fingerprint:
            raise _conflict()

    def get(self, query_id: str) -> dict[str, Any] | None:
        query_text = _required_text(query_id, "query_id")
        with self._open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    /* repository.get */
                    SELECT query_snapshot
                    FROM chat_runtime_queries
                    WHERE query_id = %s
                    """,
                    (query_text,),
                )
                row = cursor.fetchone()
        return _mapping(row[0]) if row is not None else None

    def get_by_idempotency(
        self,
        idempotency_key: str,
        *,
        fingerprint: str | None = None,
    ) -> dict[str, Any] | None:
        key = _required_text(idempotency_key, "idempotency_key")
        with self._open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    /* repository.get_by_idempotency */
                    SELECT request_fingerprint, query_snapshot
                    FROM chat_runtime_queries
                    WHERE idempotency_key = %s
                    """,
                    (key,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        if fingerprint is not None and str(row[0]) != fingerprint:
            raise _conflict()
        return _mapping(row[1])


@dataclass(frozen=True)
class ChatQueueLease:
    query_id: str
    kind: str
    lease_token: str
    lease_expires_at: str


class PostgresChatQueue(_PostgresAdapter):
    """Two-kind durable queue with reclaimable, token-bound leases."""

    def __init__(
        self,
        *,
        open_connection: _OpenConnection | None = None,
        lease_seconds: int = DEFAULT_QUEUE_LEASE_SECONDS,
    ) -> None:
        super().__init__(open_connection=open_connection)
        if lease_seconds < 1:
            raise ValueError("chat queue lease_seconds must be positive")
        self._lease_seconds = lease_seconds

    def enqueue(
        self,
        query_id: str,
        *,
        kind: str = "source",
        available_at: str | None = None,
    ) -> None:
        query_text = _required_text(query_id, "query_id")
        kind_text = _work_kind(kind)
        due = _datetime(available_at)
        with self._open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    /* queue.enqueue */
                    INSERT INTO chat_runtime_queue
                        (query_id, work_kind, available_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (query_id, work_kind) DO UPDATE
                    SET available_at = CASE
                            WHEN chat_runtime_queue.lease_token IS NULL
                            THEN LEAST(chat_runtime_queue.available_at, EXCLUDED.available_at)
                            ELSE EXCLUDED.available_at
                        END,
                        lease_token = NULL,
                        lease_expires_at = NULL,
                        updated_at = now()
                    """,
                    (query_text, kind_text, due),
                )

    def claim_due(
        self,
        *,
        kind: str = "source",
        limit: int | None = None,
        now: str | None = None,
    ) -> list[ChatQueueLease]:
        kind_text = _work_kind(kind)
        if limit is not None and limit < 1:
            return []
        batch_size = min(limit if limit is not None else 1000, 1000)
        cutoff = _datetime(now)
        lease_token = str(uuid.uuid4())
        lease_expires_at = cutoff + timedelta(seconds=self._lease_seconds)
        with self._open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    /* queue.claim_due */
                    WITH due AS (
                        SELECT query_id, work_kind
                        FROM chat_runtime_queue
                        WHERE work_kind = %s
                          AND available_at <= %s
                          AND (lease_expires_at IS NULL OR lease_expires_at <= %s)
                        ORDER BY available_at, query_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                    )
                    UPDATE chat_runtime_queue AS work
                    SET lease_token = %s,
                        lease_expires_at = %s,
                        updated_at = now()
                    FROM due
                    WHERE work.query_id = due.query_id
                      AND work.work_kind = due.work_kind
                    RETURNING work.query_id, work.work_kind,
                              work.lease_token::text, work.lease_expires_at
                    """,
                    (
                        kind_text,
                        cutoff,
                        cutoff,
                        batch_size,
                        lease_token,
                        lease_expires_at,
                    ),
                )
                rows = cursor.fetchall()
        return [
            ChatQueueLease(
                query_id=str(row[0]),
                kind=str(row[1]),
                lease_token=str(row[2]),
                lease_expires_at=_timestamp(row[3]),
            )
            for row in rows
        ]

    def ack(
        self,
        lease: ChatQueueLease | str,
        *,
        kind: str | None = None,
        lease_token: str | None = None,
        now: str | None = None,
    ) -> bool:
        if isinstance(lease, ChatQueueLease):
            query_id = lease.query_id
            kind_text = lease.kind
            token = lease.lease_token
        else:
            query_id = _required_text(lease, "query_id")
            kind_text = _work_kind(kind or "source")
            token = _required_text(lease_token, "lease_token")
        cutoff = _datetime(now)
        with self._open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    /* queue.ack */
                    DELETE FROM chat_runtime_queue
                    WHERE query_id = %s
                      AND work_kind = %s
                      AND lease_token = %s
                      AND lease_expires_at > %s
                    RETURNING query_id
                    """,
                    (query_id, kind_text, token, cutoff),
                )
                return cursor.fetchone() is not None


class PostgresProgressEventStore(_PostgresAdapter):
    """Replayable event envelopes and retry state shared across processes."""

    def __init__(
        self,
        *,
        open_connection: _OpenConnection | None = None,
        max_events_per_query: int = DEFAULT_MAX_EVENTS_PER_QUERY,
    ) -> None:
        super().__init__(open_connection=open_connection)
        if max_events_per_query < 1:
            raise ValueError("max_events_per_query must be positive")
        self._max_events_per_query = max_events_per_query

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
        supplied_correlation = (
            _contract_uuid("correlation", correlation_id)
            if _optional_text(correlation_id)
            else None
        )
        supplied_request = (
            _contract_uuid("request", request_id) if _optional_text(request_id) else None
        )
        supplied_projection = (
            _contract_uuid("projection", projection_id)
            if _optional_text(projection_id)
            else None
        )
        owner = _optional_text(owner_id)
        organization = _optional_text(organization_id)
        initial = {
            "correlation_id": supplied_correlation
            or _contract_uuid("correlation", query_text),
            "request_id": supplied_request or _contract_uuid("request", query_text),
            "projection_id": supplied_projection or _contract_uuid("projection", query_text),
        }
        with self._open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    /* context.register */
                    INSERT INTO chat_runtime_event_contexts
                        (query_id, correlation_id, request_id, projection_id,
                         owner_id, organization_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (query_id) DO UPDATE
                    SET correlation_id = COALESCE(%s, chat_runtime_event_contexts.correlation_id),
                        request_id = COALESCE(%s, chat_runtime_event_contexts.request_id),
                        projection_id = COALESCE(%s, chat_runtime_event_contexts.projection_id),
                        owner_id = COALESCE(%s, chat_runtime_event_contexts.owner_id),
                        organization_id = COALESCE(%s, chat_runtime_event_contexts.organization_id),
                        updated_at = now()
                    RETURNING correlation_id::text, request_id::text,
                              projection_id::text, owner_id, organization_id
                    """,
                    (
                        query_text,
                        initial["correlation_id"],
                        initial["request_id"],
                        initial["projection_id"],
                        owner,
                        organization,
                        supplied_correlation,
                        supplied_request,
                        supplied_projection,
                        owner,
                        organization,
                    ),
                )
                row = cursor.fetchone()
        if row is None:
            raise RuntimeError("chat event context was not persisted")
        context = {
            "correlation_id": str(row[0]),
            "request_id": str(row[1]),
            "projection_id": str(row[2]),
        }
        if row[3] is not None:
            context["owner_id"] = str(row[3])
        if row[4] is not None:
            context["organization_id"] = str(row[4])
        return context

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
        safe_payload["query_id"] = query_text
        safe_payload["stage"] = stage_text
        safe_payload["status"] = status_text
        safe_payload["data_state"] = data_state_text
        serialized = json.dumps(
            _stable_for_idempotency(safe_payload),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        logical_key = (
            sanitize_text(idempotency_key, limit=256)
            if idempotency_key
            else hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        )
        event_idempotency_key = f"chat-progress:v1:{query_text}:{logical_key}"
        if len(serialized.encode("utf-8")) > MAX_EVENT_PAYLOAD_BYTES:
            safe_payload = {
                "message": sanitize_text(
                    safe_payload.get("message") or f"{stage_text} {status_text}"
                ),
                "payload_truncated": True,
                "payload_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
                "query_id": query_text,
                "stage": stage_text,
                "status": status_text,
                "data_state": data_state_text,
            }
        context = self.register_context(query_text)
        event_id = _stable_uuid("event", event_idempotency_key)
        revision_value = safe_payload.get("revision_id") or safe_payload.get(
            "answer_revision_id"
        )
        revision_id = (
            _contract_uuid("revision", revision_value) if revision_value else None
        )
        message = str(
            safe_payload.get("message") or f"{stage_text} {status_text}"
        ).strip()
        event = {
            "event_id": event_id,
            "event_type": event_type or _event_type(stage_text),
            "event_version": EVENT_VERSION,
            "occurred_at": _timestamp(),
            "producer": str(
                safe_payload.get("producer") or "ingestion-python-chat"
            ),
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
        with self._open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    /* event.insert */
                    INSERT INTO chat_runtime_events
                        (query_id, event_id, idempotency_key, occurred_at, event_snapshot)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING event_snapshot
                    """,
                    (
                        query_text,
                        event_id,
                        event_idempotency_key,
                        _datetime(event["occurred_at"]),
                        _json(event),
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    cursor.execute(
                        """
                        /* event.get_by_idempotency */
                        SELECT event_snapshot
                        FROM chat_runtime_events
                        WHERE idempotency_key = %s
                        """,
                        (event_idempotency_key,),
                    )
                    row = cursor.fetchone()
                else:
                    cursor.execute(
                        """
                        /* event.trim */
                        DELETE FROM chat_runtime_events
                        WHERE event_sequence IN (
                            SELECT event_sequence
                            FROM chat_runtime_events
                            WHERE query_id = %s
                            ORDER BY event_sequence DESC
                            OFFSET %s
                        )
                        """,
                        (query_text, self._max_events_per_query),
                    )
        if row is None:
            raise RuntimeError("chat progress event was not persisted")
        return _mapping(row[0])

    def iter_events(
        self,
        query_id: str,
        *,
        last_event_id: str | None = None,
        principal: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        query_text = _required_text(query_id, "query_id")
        context = self._get_context(query_text)
        _authorize_context(context, principal)
        with self._open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    /* event.list */
                    SELECT event_snapshot
                    FROM chat_runtime_events
                    WHERE query_id = %s
                    ORDER BY event_sequence
                    """,
                    (query_text,),
                )
                events = [_mapping(row[0]) for row in cursor.fetchall()]
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
        with self._open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    /* retry.ensure */
                    INSERT INTO chat_runtime_event_retries
                        (query_id, stage, attempt_count)
                    VALUES (%s, %s, 0)
                    ON CONFLICT (query_id, stage) DO NOTHING
                    """,
                    (query_text, stage_text),
                )
                cursor.execute(
                    """
                    /* retry.get_for_update */
                    SELECT attempt_count, terminal_result
                    FROM chat_runtime_event_retries
                    WHERE query_id = %s AND stage = %s
                    FOR UPDATE
                    """,
                    (query_text, stage_text),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("chat retry state was not persisted")
                if row[1] is not None:
                    return _mapping(row[1])
                attempt = int(row[0]) + 1
                cursor.execute(
                    """
                    /* retry.increment */
                    UPDATE chat_runtime_event_retries
                    SET attempt_count = %s, updated_at = now()
                    WHERE query_id = %s AND stage = %s
                    """,
                    (attempt, query_text, stage_text),
                )
        safe_error = redact_secrets(
            {
                "error_type": type(error).__name__,
                "message": sanitize_text(
                    str(error).strip() or type(error).__name__
                ),
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
            with self._open() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        /* retry.set_terminal */
                        UPDATE chat_runtime_event_retries
                        SET terminal_result = %s::jsonb, updated_at = now()
                        WHERE query_id = %s AND stage = %s
                        """,
                        (_json(result), query_text, stage_text),
                    )
        return result

    def _get_context(self, query_id: str) -> dict[str, Any] | None:
        with self._open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    /* context.get */
                    SELECT correlation_id::text, request_id::text,
                           projection_id::text, owner_id, organization_id
                    FROM chat_runtime_event_contexts
                    WHERE query_id = %s
                    """,
                    (query_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return {
            "correlation_id": str(row[0]),
            "request_id": str(row[1]),
            "projection_id": str(row[2]),
            "owner_id": str(row[3]) if row[3] is not None else None,
            "organization_id": str(row[4]) if row[4] is not None else None,
        }


def create_postgres_chat_runtime(
    *,
    open_connection: _OpenConnection | None = None,
    queue_lease_seconds: int | None = None,
    max_events_per_query: int | None = None,
) -> Any:
    """Build one shared runtime without importing psycopg until first use."""

    from .chat_service import ChatRuntime

    lease_seconds = queue_lease_seconds or _positive_environment_int(
        "AUTODATA_CHAT_QUEUE_LEASE_SECONDS", DEFAULT_QUEUE_LEASE_SECONDS
    )
    event_limit = max_events_per_query or _positive_environment_int(
        "AUTODATA_CHAT_MAX_EVENTS_PER_QUERY", DEFAULT_MAX_EVENTS_PER_QUERY
    )
    return ChatRuntime(
        repository=PostgresChatRepository(open_connection=open_connection),
        queue=PostgresChatQueue(
            open_connection=open_connection, lease_seconds=lease_seconds
        ),
        event_store=PostgresProgressEventStore(
            open_connection=open_connection, max_events_per_query=event_limit
        ),
        durable=True,
    )


def build_postgres_chat_runtime(
    *,
    connect_factory: _OpenConnection | None = None,
    queue_lease_seconds: int | None = None,
    max_events_per_query: int | None = None,
) -> Any:
    """Compatibility-named factory for callers wiring the durable runtime.

    ``connect_factory`` is intentionally injectable for contract tests and
    provider-neutral deployments.  Production callers should omit it so the
    adapter opens PostgreSQL connections from the configured environment.
    """

    return create_postgres_chat_runtime(
        open_connection=connect_factory,
        queue_lease_seconds=queue_lease_seconds,
        max_events_per_query=max_events_per_query,
    )


def _open_postgres_from_environment() -> Any:
    import psycopg

    host, port_text = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(
        ":", 1
    )
    return psycopg.connect(
        host=host,
        port=int(port_text),
        dbname=os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        user=os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        password=os.environ["AUTODATA_POSTGRES_PASSWORD"],
    )


def _event_type(stage: str) -> str:
    return {
        "answer": "chat.answer.updated",
        "answer_update": "chat.answer.updated",
        "publication": "chat.answer.updated",
        "vehicle_options": "chat.vehicle.options",
        "price_refresh": "chat.price.refresh.requested",
        "procedure": "chat.procedure.published",
        "procedure_composition": "chat.procedure.published",
        "visual": "chat.visual.published",
    }.get(stage, "chat.worker.progress")


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _work_kind(value: Any) -> str:
    kind = _required_text(value, "work kind")
    if kind not in _WORK_KINDS:
        raise ValueError(f"unsupported chat work kind: {kind}")
    return kind


def _datetime(value: Any = None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("chat runtime timestamps must include a timezone")
    return parsed.astimezone(UTC)


def _timestamp(value: Any = None) -> str:
    parsed = _datetime(value)
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, Mapping):
        raise TypeError("chat runtime JSON state must be an object")
    return deepcopy(dict(value))


def _positive_environment_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


__all__ = [
    "ChatQueueLease",
    "DEFAULT_MAX_EVENTS_PER_QUERY",
    "DEFAULT_QUEUE_LEASE_SECONDS",
    "PostgresChatQueue",
    "PostgresChatRepository",
    "PostgresProgressEventStore",
    "build_postgres_chat_runtime",
    "create_postgres_chat_runtime",
]
