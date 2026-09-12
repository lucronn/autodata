"""Fast, cache-first orchestration for one natural-language chat request.

The service owns the request state machine and keeps source/model work behind
small dependency callables.  The default callables bridge to the existing
ingestion runtime; tests and local smoke runs can install deterministic fakes.
The in-process repository is intentionally shaped like a durable repository so
that a PostgreSQL-backed adapter can be supplied without changing the public
chat functions.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
import re
import threading
import uuid
from typing import Any

from .chat_intent import ChatIntent, interpret_chat_message
from .progress_events import (
    DEFAULT_MAX_ATTEMPTS,
    ProgressEventStore,
    iter_progress_events,
    publish_progress_event,
    record_chat_retry,
    redact_secrets,
    register_query_context,
    sanitize_text,
)


PROCESSING_VERSION = "chat-v1"
_TERMINAL_JOB_STATES = {"complete", "dead_letter", "failed"}
_ALLOWED_DATA_STATES = {
    "normalized",
    "source_unnormalized",
    "stale",
    "normalizing",
    "mixed",
    "unavailable",
    "needs_review",
}


class ChatDurabilityError(RuntimeError):
    """Raised when chat work has no configured shared durable boundary."""


class ChatConflictError(ValueError):
    """Raised when an idempotency or selection key is reused incompatibly."""

    http_status = 409


@dataclass(frozen=True)
class ChatRuntime:
    """Provider-neutral repository, queue, and event adapters for both edges."""

    repository: Any
    queue: Any
    event_store: Any
    durable: bool = True

    def validate(self) -> None:
        for adapter, names in (
            (self.repository, ("save", "get", "get_by_idempotency")),
            (self.queue, ("enqueue", "claim_due")),
            (self.event_store, ("register_context", "publish", "iter_events", "retry")),
        ):
            if adapter is None or not all(hasattr(adapter, name) for name in names):
                raise ChatDurabilityError("configured chat runtime is missing a shared durability adapter")


class _UnavailableRepository:
    def _fail(self, *_args: Any, **_kwargs: Any) -> Any:
        raise ChatDurabilityError("durable chat runtime is not configured")

    save = get = get_by_idempotency = _fail


class _UnavailableQueue:
    def _fail(self, *_args: Any, **_kwargs: Any) -> Any:
        raise ChatDurabilityError("durable chat queue is not configured")

    enqueue = claim_due = _fail


class _UnavailableEvents:
    def _fail(self, *_args: Any, **_kwargs: Any) -> Any:
        raise ChatDurabilityError("durable chat event store is not configured")

    register_context = publish = iter_events = retry = _fail


_UNAVAILABLE_RUNTIME = ChatRuntime(
    repository=_UnavailableRepository(),
    queue=_UnavailableQueue(),
    event_store=_UnavailableEvents(),
    durable=False,
)


@dataclass(frozen=True)
class ChatDependencies:
    """Provider-neutral boundaries used by the chat state machine."""

    vehicle_candidates: Callable[[str, Mapping[str, Any]], Iterable[Mapping[str, Any]]] | None = None
    normalized_cache: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None] | None = None
    source_retriever: Callable[[str, Mapping[str, Any], Iterable[Mapping[str, Any]]], Mapping[str, Any]] | None = None
    normalizer: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None] | None = None
    price_refresher: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None] | None = None
    composer: Callable[[str, Mapping[str, Any], Iterable[Mapping[str, Any]]], Mapping[str, Any]] | None = None
    persist: Callable[[Mapping[str, Any]], Any] | None = None
    max_attempts: int = DEFAULT_MAX_ATTEMPTS


class InMemoryChatRepository:
    """Deterministic query/job repository used by local workers and tests."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._queries: dict[str, dict[str, Any]] = {}
        self._idempotency: dict[str, tuple[str, str]] = {}
        self._queue = InMemoryChatQueue()
        self.durable = False

    def save(self, query: Mapping[str, Any]) -> None:
        if not isinstance(query, Mapping):
            raise TypeError("chat query must be a mapping")
        query_id = _required_text(query.get("query_id"), "query_id")
        idempotency_key = _required_text(query.get("idempotency_key"), "idempotency_key")
        fingerprint = _required_text(query.get("request_fingerprint"), "request_fingerprint")
        with self._lock:
            existing = self._idempotency.get(idempotency_key)
            if existing is not None and existing[1] != fingerprint:
                raise ChatConflictError("idempotency key conflicts with a different chat request")
            self._queries[query_id] = deepcopy(dict(query))
            self._idempotency[idempotency_key] = (query_id, fingerprint)

    def get(self, query_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._queries.get(str(query_id).strip())
            return deepcopy(value) if value is not None else None

    def get_by_idempotency(self, idempotency_key: str, *, fingerprint: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            record = self._idempotency.get(str(idempotency_key).strip())
            if record is None:
                return None
            query_id, existing_fingerprint = record
            if fingerprint is not None and existing_fingerprint != fingerprint:
                raise ChatConflictError("idempotency key conflicts with a different chat request")
            value = self._queries.get(query_id)
            return deepcopy(value) if value is not None else None

    def enqueue(self, query_id: str, *, kind: str = "source", available_at: str | None = None) -> None:
        self._queue.enqueue(query_id, kind=kind, available_at=available_at)

    def pop_pending(self, limit: int | None = None, *, now: str | None = None) -> list[str]:
        return self._queue.claim_due(kind="source", limit=limit, now=now)


class InMemoryChatQueue:
    """Explicit local queue adapter; production must supply a shared queue."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[tuple[str, str], str] = {}
        self.durable = False

    def enqueue(self, query_id: str, *, kind: str = "source", available_at: str | None = None) -> None:
        query_text = _required_text(query_id, "query_id")
        kind_text = _required_text(kind, "work kind")
        due = available_at or _timestamp()
        with self._lock:
            self._items.setdefault((kind_text, query_text), due)

    def claim_due(
        self,
        *,
        kind: str = "source",
        limit: int | None = None,
        now: str | None = None,
    ) -> list[str]:
        if limit is not None and limit < 1:
            return []
        cutoff = _parse_timestamp(now) if now else datetime.now(UTC)
        with self._lock:
            due = [
                (key, value)
                for key, value in self._items.items()
                if key[0] == kind and _parse_timestamp(value) <= cutoff
            ]
            due.sort(key=lambda item: (item[1], item[0][1]))
            if limit is not None:
                due = due[:limit]
            for key, _value in due:
                self._items.pop(key, None)
            return [key[1] for key, _value in due]


_runtime: ChatRuntime = _UNAVAILABLE_RUNTIME


_dependencies = ChatDependencies()
_runtime_lock = threading.RLock()


def configure_chat_runtime(
    *,
    dependencies: ChatDependencies | None = None,
    repository: Any | None = None,
    queue: Any | None = None,
    event_store: Any | None = None,
    runtime: ChatRuntime | None = None,
    allow_in_memory: bool = False,
) -> None:
    """Install the same repository/queue/event adapters at both chat edges.

    A no-argument call deliberately installs a fail-closed runtime.  Local
    in-memory adapters are accepted only when explicitly selected by tests or
    local callers with ``allow_in_memory=True``.
    """

    global _dependencies, _runtime
    with _runtime_lock:
        if dependencies is not None:
            _dependencies = dependencies
        elif runtime is None and repository is None and queue is None and event_store is None:
            _dependencies = ChatDependencies()
        if runtime is None and repository is None and queue is None and event_store is None:
            _runtime = _UNAVAILABLE_RUNTIME
            return
        if runtime is None:
            if repository is None or event_store is None:
                raise ChatDurabilityError("repository, queue, and event store must be configured together")
            if queue is None and isinstance(repository, InMemoryChatRepository):
                queue = repository._queue
            runtime = ChatRuntime(
                repository=repository,
                queue=queue,
                event_store=event_store,
                durable=not any(isinstance(adapter, (InMemoryChatRepository, InMemoryChatQueue, ProgressEventStore)) for adapter in (repository, queue, event_store)),
            )
        elif any(
            isinstance(adapter, (InMemoryChatRepository, InMemoryChatQueue, ProgressEventStore))
            for adapter in (runtime.repository, runtime.queue, runtime.event_store)
        ):
            # A caller cannot make process-local adapters durable merely by
            # setting the flag on ChatRuntime.  Local/test use remains
            # available only through the explicit allow_in_memory switch.
            runtime = ChatRuntime(
                repository=runtime.repository,
                queue=runtime.queue,
                event_store=runtime.event_store,
                durable=False,
            )
        runtime.validate()
        if not allow_in_memory and not runtime.durable:
            raise ChatDurabilityError("in-memory chat adapters require explicit local/test configuration")
        _runtime = runtime
        ProgressEventStore.set_current(runtime.event_store)


def configure_chat_runtime_from_environment(*, dependencies: ChatDependencies | None = None) -> ChatRuntime:
    """Load PostgreSQL adapters only when the durable backend is explicit."""

    backend = os.getenv("AUTODATA_CHAT_RUNTIME_BACKEND", "").strip().casefold()
    if backend:
        if backend != "postgres":
            raise ChatDurabilityError(f"unsupported chat runtime backend: {backend}")
        from .chat_durable_runtime import create_postgres_chat_runtime

        result = create_postgres_chat_runtime()
        configure_chat_runtime(runtime=result, dependencies=dependencies)
        return result
    configure_chat_runtime(dependencies=dependencies)
    return _runtime


def get_chat_runtime() -> ChatRuntime:
    with _runtime_lock:
        return _runtime


def ensure_chat_runtime(runtime: ChatRuntime | None = None) -> ChatRuntime:
    """Use an injected shared runtime, or build production adapters from env."""

    if runtime is not None:
        configure_chat_runtime(runtime=runtime, allow_in_memory=True)
        return runtime
    with _runtime_lock:
        configured = _runtime is not _UNAVAILABLE_RUNTIME
    if configured:
        return get_chat_runtime()
    return configure_chat_runtime_from_environment()


configure_chat_dependencies = configure_chat_runtime


def create_chat_query(
    message: str,
    *,
    idempotency_key: str,
    principal: Mapping[str, Any],
    conversation_id: str | None = None,
    request_params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or replay one query and begin its cache-first execution."""

    message_text = _require_message(message)
    key = _required_text(idempotency_key, "idempotency_key")
    if not isinstance(principal, Mapping):
        raise TypeError("chat principal must be a mapping")
    owner_id, organization_id = _principal_identity(principal)
    conversation = _conversation_id(principal, key, conversation_id)
    params = _request_params(request_params)
    fingerprint = _request_fingerprint(
        owner_id=owner_id,
        organization_id=organization_id,
        conversation_id=conversation,
        message=message_text,
        request_params=params,
    )
    with _runtime_lock:
        _require_durable_runtime()
        existing = _runtime.repository.get_by_idempotency(key, fingerprint=fingerprint)
        if existing is not None:
            _authorize_query(existing, principal)
            return _public_query(existing)

        candidates = _vehicle_candidates(message_text, principal)
        intent = interpret_chat_message(message_text, tuple(candidates))
        query_id = _stable_uuid("query", fingerprint)
        correlation_id = _stable_uuid("correlation", query_id)
        register_query_context(
            query_id,
            correlation_id=correlation_id,
            request_id=query_id,
            projection_id=_stable_uuid("projection", query_id),
            owner_id=owner_id,
            organization_id=organization_id,
        )
        options = _vehicle_options(intent)
        matched_vehicle = _selected_vehicle(intent, options)
        ambiguous = intent.vehicle_observation.get("status") == "ambiguous"
        query: dict[str, Any] = {
            "query_id": query_id,
            "conversation_id": conversation,
            "message": message_text,
            "idempotency_key": key,
            "owner_id": owner_id,
            "organization_id": organization_id,
            "request_fingerprint": fingerprint,
            "request_params": params,
            "status": "awaiting_vehicle" if ambiguous else "processing",
            "vehicle_options": options,
            "answer": _new_answer(
                matched_vehicle or intent.vehicle_observation,
                answer_status="options" if ambiguous else "processing",
                data_state="normalizing",
                warnings=_initial_warnings(intent),
            ),
            "correlation_id": correlation_id,
            "updates": [],
            "job_plan": _new_job_plan(query_id, intent, matched_vehicle),
            "_intent": _intent_dict(intent),
            "_candidates": [dict(candidate) for candidate in candidates],
        }
        if matched_vehicle is not None:
            query["_selected_candidate_key"] = _source_candidate_key(matched_vehicle)
            query["_selected_option_number"] = matched_vehicle.get("option_number", 1)
            query["_selection"] = {
                "selection_type": "vehicle",
                "option_number": query["_selected_option_number"],
                "vehicle_id": matched_vehicle.get("vehicle_id"),
                "candidate_key": query["_selected_candidate_key"],
            }
        _save(query)
        publish_chat_progress(
            query_id,
            "interpret",
            "completed",
            data_state="normalizing",
            payload={
                "message": "Natural-language request interpreted",
                "requested_operations": intent.requested_operations,
            },
        )
        publish_chat_progress(
            query_id,
            "resolve_vehicle",
            "completed",
            data_state="normalizing",
            payload={
                "message": "Vehicle resolution completed",
                "resolution_status": intent.vehicle_observation.get("status", "unmatched"),
                "option_count": len(options),
            },
            idempotency_key=(
                f"resolve_vehicle:completed:{intent.vehicle_observation.get('status', 'unmatched')}:{len(options)}"
            ),
        )
        if ambiguous:
            publish_chat_progress(
                query_id,
                "vehicle_options",
                "completed",
                data_state="needs_review",
                payload={"message": "Vehicle options are ready", "options": options},
            )
            _save(query)
            return _public_query(query)

        if matched_vehicle is None:
            query["status"] = "failed"
            query["answer"] = _new_answer(
                intent.vehicle_observation,
                answer_status="needs_review",
                data_state="needs_review",
                warnings=_initial_warnings(intent) or [{"message": "A matching vehicle configuration is required"}],
            )
            query["job_plan"]["status"] = "needs_review"
            _save(query)
            return _public_query(query)

        _start_execution(query)
        return _public_query(query)


def select_chat_vehicle(
    query_id: str,
    selection: Mapping[str, Any],
    *,
    principal: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a numbered or clicked selection and start the pending request."""

    query_text = _required_text(query_id, "query_id")
    if not isinstance(selection, Mapping):
        raise TypeError("chat selection must be a mapping")
    with _runtime_lock:
        _require_durable_runtime()
        query = _runtime.repository.get(query_text)
        if query is None:
            raise KeyError(f"chat query {query_text} was not found")
        _authorize_query(query, principal)
        selection = _normalize_selection(selection)
        previous_key = str(query.get("_selected_candidate_key") or "").strip()
        if previous_key and query.get("status") != "awaiting_vehicle":
            if _selection_matches(query, selection, previous_key):
                return _public_query(query)
            raise ChatConflictError("chat query already has a different vehicle selection")
        selection_type = str(selection.get("selection_type", "vehicle")).strip().casefold()
        if selection_type != "vehicle":
            raise ValueError("chat selection_type must be vehicle")
        options = query.get("vehicle_options", [])
        if not isinstance(options, list):
            options = []
        option_number = _positive_int(selection.get("option_number"))
        selected = next(
            (
                option
                for option in options
                if isinstance(option, Mapping)
                and option_number is not None
                and int(option.get("option_number", 0)) == option_number
            ),
            None,
        )
        selected_vehicle_id = str(selection.get("vehicle_id") or "").strip()
        if selected is None and selected_vehicle_id:
            selected = next(
                (
                    option
                    for option in options
                    if isinstance(option, Mapping)
                    and selected_vehicle_id
                    in {
                        str(option.get("vehicle_id") or "").strip(),
                        str(option.get("candidate_key") or "").strip(),
                    }
                ),
                None,
            )
        if selected is None:
            raise ValueError("vehicle option is not available")
        selected_key = str(selected.get("candidate_key") or selected.get("vehicle_id") or "").strip()
        if previous_key and previous_key != selected_key:
            raise ChatConflictError("chat query already has a different vehicle selection")
        if previous_key == selected_key and query.get("status") != "awaiting_vehicle":
            return _public_query(query)
        query["_selected_candidate_key"] = selected_key
        query["_selected_option_number"] = option_number
        query["_selection"] = {
            "selection_type": "vehicle",
            "option_number": option_number,
            "vehicle_id": selected.get("vehicle_id"),
            "candidate_key": selected_key,
        }
        query["vehicle_options"] = []
        query["status"] = "processing"
        intent = dict(query.get("_intent") or {})
        observation = dict(intent.get("vehicle_observation") or {})
        observation.update(
            {
                key: value
                for key, value in selected.items()
                if key in {
                    "vehicle_id",
                    "candidate_key",
                    "year",
                    "make",
                    "model",
                    "region",
                    "body_style",
                    "trim",
                    "drivetrain",
                    "engine_displacement_l",
                }
            }
        )
        observation["status"] = "matched"
        observation["selected_vehicle_id"] = selected.get("vehicle_id") or selected.get("candidate_key")
        observation["selected_candidate_key"] = selected_key
        intent["vehicle_observation"] = observation
        query["_intent"] = intent
        query["answer"] = _new_answer(observation, answer_status="processing", data_state="normalizing")
        query["job_plan"] = _new_job_plan(
            query_text,
            _intent_from_dict(intent),
            selected,
        )
        _save(query)
        publish_chat_progress(
            query_text,
            "resolve_vehicle",
            "completed",
            data_state="normalizing",
            payload={"message": "Vehicle selection accepted", "option_number": option_number, "vehicle_id": selected.get("vehicle_id")},
            idempotency_key=f"resolve_vehicle:selected:{selected_key}",
        )
        _start_execution(query)
        return _public_query(query)


def get_chat_query(query_id: str, *, principal: Mapping[str, Any] | None = None) -> dict[str, Any]:
    query_text = _required_text(query_id, "query_id")
    with _runtime_lock:
        _require_durable_runtime()
        query = _runtime.repository.get(query_text)
        if query is None:
            raise KeyError(f"chat query {query_text} was not found")
        _authorize_query(query, principal)
        return _public_query(query)


def iter_chat_events(
    query_id: str,
    *,
    last_event_id: str | None = None,
    principal: Mapping[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    query_text = _required_text(query_id, "query_id")
    with _runtime_lock:
        _require_durable_runtime()
        query = _runtime.repository.get(query_text)
        if query is None:
            raise KeyError(f"chat query {query_text} was not found")
        _authorize_query(query, principal)
        return iter_progress_events(query_text, last_event_id=last_event_id, principal=principal)


def publish_chat_progress(
    query_id: str,
    stage: str,
    status: str,
    *,
    data_state: str,
    payload: Mapping[str, Any],
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Publish one idempotent, redacted progress frame correlated to a query."""

    return publish_progress_event(
        query_id,
        stage,
        status,
        data_state=data_state,
        payload=_compact_progress_payload(payload),
        idempotency_key=idempotency_key or f"{stage}:{status}",
    )


def process_chat_jobs(*, max_jobs: int | None = None, now: str | None = None) -> list[dict[str, Any]]:
    """Process queued source/model fan-out without blocking the HTTP caller."""

    with _runtime_lock:
        _require_durable_runtime()
        claims = _runtime.queue.claim_due(kind="source", limit=max_jobs, now=now)
    completed: list[dict[str, Any]] = []
    for claim in claims:
        query_id = _claim_query_id(claim)
        _process_one_job(query_id)
        stored = _runtime.repository.get(query_id)
        if stored is not None:
            completed.append(_public_query(stored))
        _ack_chat_claim(claim)
    return completed


drain_chat_jobs = process_chat_jobs


def process_chat_price_jobs(*, max_jobs: int | None = None, now: str | None = None) -> list[dict[str, Any]]:
    """Run queued price refreshes separately from answer publication."""

    with _runtime_lock:
        _require_durable_runtime()
        claims = _runtime.queue.claim_due(kind="price_refresh", limit=max_jobs, now=now)
    completed: list[dict[str, Any]] = []
    for claim in claims:
        query_id = _claim_query_id(claim)
        _process_one_price_job(query_id)
        query = _runtime.repository.get(query_id)
        if query is not None:
            completed.append(_public_query(query))
        _ack_chat_claim(claim)
    return completed


def _process_one_price_job(query_id: str) -> None:
    with _runtime_lock:
        query = _runtime.repository.get(query_id)
        if query is None:
            return
        answer = query.get("answer")
        vehicle = _query_vehicle(query)
        if not isinstance(answer, Mapping) or vehicle is None:
            return
        callback = _dependencies.price_refresher
        if callback is None:
            return
        publish_chat_progress(
            query_id,
            "price_refresh",
            "processing",
            data_state=str(answer.get("data_state") or "normalizing"),
            payload={"message": "Refreshing source price snapshots"},
            idempotency_key="price_refresh:processing",
        )
        try:
            result = _invoke(callback, str(query["message"]), vehicle, answer)
        except Exception as error:  # noqa: BLE001 - preserve the displayed price
            retry = record_chat_retry(query_id, "price_refresh", error, max_attempts=_configured_max_attempts(_dependencies.max_attempts))
            job = query.setdefault("job_plan", {})
            _handle_retry_result(query, job, retry, kind="price_refresh")
            return
        if not isinstance(result, Mapping) or _result_is_failure(result):
            retry = record_chat_retry(
                query_id,
                "price_refresh",
                RuntimeError(_result_failure_message(result, "price refresh unavailable")),
                max_attempts=_configured_max_attempts(_dependencies.max_attempts),
            )
            job = query.setdefault("job_plan", {})
            _handle_retry_result(query, job, retry, kind="price_refresh")
            return
        refreshed = _merge_price_result(answer, result)
        _apply_answer(query, refreshed)
        publish_chat_progress(
            query_id,
            "price_refresh",
            "completed",
            data_state=refreshed["data_state"],
            payload={"message": "Source price snapshot refreshed", "revision_id": refreshed.get("revision_id")},
            idempotency_key=f"price_refresh:completed:{refreshed.get('revision_id')}",
        )
        publish_chat_progress(
            query_id,
            "answer",
            "completed",
            data_state=refreshed["data_state"],
            payload={"message": "Price refresh updated the same answer", "answer": refreshed, "revision_id": refreshed.get("revision_id")},
            idempotency_key=f"answer:price:{refreshed.get('revision_id')}",
        )
        query.setdefault("job_plan", {})["price_refresh"] = {"status": "complete", "next_attempt_at": None}
        query["job_plan"]["price_refresh_pending"] = False
        _save(query)


def _start_execution(query: dict[str, Any]) -> None:
    query_id = str(query["query_id"])
    vehicle = _query_vehicle(query)
    if vehicle is None:
        query["status"] = "failed"
        _save(query)
        return
    intent = query.get("_intent", {})
    publish_chat_progress(
        query_id,
        "lookup_derived",
        "processing",
        data_state="normalizing",
        payload={"message": "Checking normalized and derived answer cache"},
        idempotency_key="lookup_derived:processing",
    )
    try:
        cached = _cache_lookup(query, vehicle, intent)
    except Exception as error:  # noqa: BLE001 - cache errors degrade to source work
        cached = None
        publish_chat_progress(
            query_id,
            "lookup_derived",
            "failed",
            data_state="unavailable",
            payload={"message": "Answer cache unavailable", "error_type": type(error).__name__},
            idempotency_key="lookup_derived:failed",
        )
    if isinstance(cached, Mapping) and cached.get("cache_hit", True) is not False:
        answer = _answer_from_result(cached, vehicle=vehicle, query_id=query_id)
        _apply_answer(query, answer)
        pending = bool(cached.get("normalization_pending"))
        query["status"] = "available" if _has_usable_answer(answer) else "processing"
        query["job_plan"]["status"] = "pending" if pending else "complete"
        publish_chat_progress(
            query_id,
            "lookup_derived",
            "completed",
            data_state=answer["data_state"],
            payload={"message": "Reusable cached answer returned", "cache_hit": True, "revision_id": answer.get("revision_id")},
            idempotency_key="lookup_derived:completed",
        )
        publish_chat_progress(
            query_id,
            "answer",
            "completed",
            data_state=answer["data_state"],
            payload={"message": "Cached answer is available", "answer": answer, "revision_id": answer.get("revision_id")},
            idempotency_key=f"answer:cache:{answer.get('revision_id') or answer['data_state']}",
        )
        if _price_refresh_needed(cached, answer):
            _queue_price_refresh(query)
        _save(query)
        return
    query["job_plan"]["status"] = "pending"
    query["job_plan"]["attempt_count"] = 0
    publish_chat_progress(
        query_id,
        "source_retrieval",
        "queued",
        data_state="normalizing",
        payload={"message": "Source retrieval queued after cache miss"},
        idempotency_key="source_retrieval:queued",
    )
    _runtime.queue.enqueue(query_id, kind="source", available_at=_timestamp())
    _save(query)


def _process_one_job(query_id: str) -> None:
    with _runtime_lock:
        _require_durable_runtime()
        query = _runtime.repository.get(query_id)
        if query is None:
            return
        job = query.get("job_plan")
        vehicle = _query_vehicle(query)
        if not isinstance(job, dict) or vehicle is None or job.get("status") in _TERMINAL_JOB_STATES:
            return
        dependencies = _dependencies
        max_attempts = _configured_max_attempts(dependencies.max_attempts)
        job["status"] = "processing"
        job["next_attempt_at"] = None
        job["attempt_count"] = int(job.get("attempt_count", 0)) + 1
        _save(query)

        source_result = job.get("_source_result")
        if not isinstance(source_result, Mapping):
            publish_chat_progress(
                query_id,
                "source_retrieval",
                "processing",
                data_state="normalizing",
                payload={"message": "Retrieving vehicle-scoped source resources"},
                idempotency_key="source_retrieval:processing",
            )
            try:
                source_result = _source_retrieve(query, vehicle)
            except Exception as error:  # noqa: BLE001 - retry at the stage boundary
                retry = record_chat_retry(
                    query_id,
                    "source_retrieval",
                    error,
                    max_attempts=max_attempts,
                )
                _handle_retry_result(query, job, retry)
                return
            if not isinstance(source_result, Mapping):
                _handle_retry_result(
                    query,
                    job,
                    record_chat_retry(
                        query_id,
                        "source_retrieval",
                        RuntimeError("source boundary returned no result"),
                        max_attempts=max_attempts,
                    ),
                )
                return
            job["_source_result"] = redact_secrets(dict(source_result))
            source_result = job["_source_result"]

        if _result_is_failure(source_result):
            _handle_retry_result(
                query,
                job,
                record_chat_retry(
                    query_id,
                    "source_retrieval",
                    RuntimeError(_result_failure_message(source_result, "source retrieval unavailable")),
                    max_attempts=max_attempts,
                ),
            )
            return
        source_answer = _answer_from_result(
            source_result,
            vehicle=vehicle,
            query_id=query_id,
            force_data_state="source_unnormalized",
        )
        _apply_answer(query, source_answer)
        publish_chat_progress(
            query_id,
            "source_retrieval",
            "completed",
            data_state="source_unnormalized",
            payload={
                "message": "Source data is available while normalization continues",
                "source_uri": source_result.get("source_uri"),
                "data_state": "source_unnormalized",
            },
            idempotency_key="source_retrieval:completed",
        )
        publish_chat_progress(
            query_id,
            "answer",
            "completed",
            data_state=source_answer["data_state"],
            payload={
                "message": "Provisional answer published",
                "answer": source_answer,
                "revision_id": source_answer.get("revision_id"),
            },
            idempotency_key="answer:source_unnormalized",
        )
        # Persist the provisional answer before any normalization/composition
        # work.  A slow or failed later stage must not hide this revision.
        _save(query)
        articles = _source_articles(source_result)
        if not articles:
            job["status"] = "complete"
            query["status"] = "available" if _has_usable_answer(source_answer) else "failed"
            _save(query)
            return
        normalized_result = job.get("_normalized_result")
        if not isinstance(normalized_result, Mapping):
            publish_chat_progress(
                query_id,
                "normalization",
                "processing",
                data_state="normalizing",
                payload={"message": "Normalizing retrieved source articles"},
                idempotency_key="normalization:processing",
            )
            try:
                normalized_result = _normalize(query, vehicle, source_result)
            except Exception as error:  # noqa: BLE001 - retry at the stage boundary
                _handle_retry_result(
                    query,
                    job,
                    record_chat_retry(query_id, "normalization", error, max_attempts=max_attempts),
                )
                return
            if not isinstance(normalized_result, Mapping) or _result_is_failure(normalized_result):
                _handle_retry_result(
                    query,
                    job,
                    record_chat_retry(
                        query_id,
                        "normalization",
                        RuntimeError(_result_failure_message(normalized_result, "normalization unavailable")),
                        max_attempts=max_attempts,
                    ),
                )
                return
            job["_normalized_result"] = redact_secrets(dict(normalized_result))
            normalized_result = job["_normalized_result"]
        if bool(normalized_result.get("normalization_pending")):
            # A pending normalization response is a stage result, not a
            # successful normalized revision.  Drop it so a due retry asks
            # the normalizer for its current state instead of replaying the
            # same pending snapshot forever.
            job.pop("_normalized_result", None)
            publish_chat_progress(
                query_id,
                "normalization",
                "processing",
                data_state="normalizing",
                payload={"message": "Normalization is still pending"},
                idempotency_key="normalization:pending",
            )
            _handle_retry_result(
                query,
                job,
                record_chat_retry(
                    query_id,
                    "normalization",
                    RuntimeError("normalization is still pending"),
                    max_attempts=max_attempts,
                ),
            )
            return
        publish_chat_progress(
            query_id,
            "normalization",
            "completed",
            data_state="normalized",
            payload={"message": "Source articles normalized", "article_count": len(_source_articles(normalized_result))},
            idempotency_key="normalization:completed",
        )
        _queue_price_refresh(query)
        articles = _source_articles(normalized_result) or articles
        publish_chat_progress(
            query_id,
            "procedure_composition",
            "processing",
            data_state="normalizing",
            payload={"message": "Composing quote and procedure from retrieved source data"},
            idempotency_key="procedure_composition:processing",
        )
        try:
            composed = _compose(query, vehicle, articles)
        except Exception as error:  # noqa: BLE001 - keep the provisional answer visible
            retry = record_chat_retry(
                query_id,
                "procedure_composition",
                error,
                max_attempts=max_attempts,
            )
            _handle_retry_result(query, job, retry)
            return
        if not isinstance(composed, Mapping) or _result_is_failure(composed):
            _handle_retry_result(
                query,
                job,
                record_chat_retry(
                    query_id,
                    "procedure_composition",
                    RuntimeError(_result_failure_message(composed, "procedure composition unavailable")),
                    max_attempts=max_attempts,
                ),
            )
            return
        normalized_answer = _answer_from_result(
            composed,
            vehicle=vehicle,
            query_id=query_id,
            default_data_state="normalized",
        )
        if normalized_answer["data_state"] != "normalized":
            _handle_retry_result(
                query,
                job,
                record_chat_retry(
                    query_id,
                    "procedure_composition",
                    RuntimeError("procedure composition did not produce normalized data"),
                    max_attempts=max_attempts,
                ),
            )
            return
        _apply_answer(query, normalized_answer)
        publish_chat_progress(
            query_id,
            "procedure_composition",
            "completed",
            data_state="normalized",
            payload={
                "message": "Quote and procedure revision published",
                "answer": normalized_answer,
                "revision_id": normalized_answer.get("revision_id"),
            },
            idempotency_key=f"procedure_composition:completed:{normalized_answer.get('revision_id')}",
        )
        publish_chat_progress(
            query_id,
            "answer",
            "completed",
            data_state="normalized",
            payload={"message": "Same answer updated with normalized data", "answer": normalized_answer, "revision_id": normalized_answer.get("revision_id")},
            idempotency_key=f"answer:normalized:{normalized_answer.get('revision_id')}",
        )
        job["status"] = "complete"
        query["status"] = "available"
        _save(query)


def _handle_retry_result(
    query: dict[str, Any],
    job: dict[str, Any],
    retry: Mapping[str, Any],
    *,
    kind: str = "source",
) -> None:
    query_id = str(query["query_id"])
    retry_metadata = redact_secrets({key: value for key, value in retry.items() if key != "event"})
    safe_error = redact_secrets(retry.get("error"))
    attempt = int(retry.get("attempt") or job.get("attempt_count") or 1)
    if kind == "price_refresh":
        price_job = job.setdefault("price_refresh", {})
        price_job["last_error"] = safe_error
        price_job["retry"] = retry_metadata
        if retry.get("status") == "dead_letter":
            price_job.update({"status": "dead_letter", "next_attempt_at": None})
            job["price_refresh_pending"] = False
            _save(query)
            return
        delay = min(300, 2 ** max(0, attempt - 1))
        next_attempt_at = _timestamp(datetime.now(UTC).timestamp() + delay)
        price_job.update(
            {
                "status": "pending",
                "backoff_seconds": delay,
                "next_attempt_at": next_attempt_at,
            }
        )
        job["price_refresh_pending"] = True
        _runtime.queue.enqueue(query_id, kind=kind, available_at=next_attempt_at)
        _save(query)
        return

    job["last_error"] = safe_error
    job["retry"] = retry_metadata
    if retry.get("status") == "dead_letter":
        job["next_attempt_at"] = None
        job["status"] = "dead_letter"
        query["status"] = "failed"
        _save(query)
        return
    job["status"] = "pending"
    delay = min(300, 2 ** max(0, attempt - 1))
    job["backoff_seconds"] = delay
    job["next_attempt_at"] = _timestamp(datetime.now(UTC).timestamp() + delay)
    query["status"] = "processing"
    _runtime.queue.enqueue(
        query_id,
        kind=kind,
        available_at=job["next_attempt_at"],
    )
    _save(query)


def _cache_lookup(query: Mapping[str, Any], vehicle: Mapping[str, Any], intent: Mapping[str, Any]) -> Mapping[str, Any] | None:
    callback = _dependencies.normalized_cache or _default_normalized_cache
    return _invoke(callback, str(query["message"]), vehicle, intent)


def _source_retrieve(query: Mapping[str, Any], vehicle: Mapping[str, Any]) -> Mapping[str, Any]:
    callback = _dependencies.source_retriever or _default_source_retriever
    operations = query.get("_intent", {}).get("requested_operations", ())
    return _invoke(callback, str(query["message"]), vehicle, operations)


def _normalize(
    query: Mapping[str, Any],
    vehicle: Mapping[str, Any],
    source_result: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    callback = _dependencies.normalizer or _default_normalizer
    return _invoke(callback, str(query["message"]), vehicle, source_result)


def _compose(query: Mapping[str, Any], vehicle: Mapping[str, Any], articles: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    callback = _dependencies.composer or _default_composer
    return _invoke(callback, str(query["message"]), vehicle, tuple(articles))


def _default_normalizer(
    _query: str,
    _vehicle: Mapping[str, Any],
    source_result: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Keep normalization as an explicit boundary without inventing facts."""

    return {
        "articles": _source_articles(source_result),
        "status": "ready",
        "normalization_boundary": "ingestion-python",
    }


def _result_is_failure(result: Mapping[str, Any] | None) -> bool:
    if not isinstance(result, Mapping):
        return True
    status = str(result.get("status") or result.get("answer_status") or "").casefold()
    return result.get("ok") is False or result.get("success") is False or status in {
        "failed",
        "failure",
        "unavailable",
        "dead_letter",
        "error",
    }


def _result_failure_message(result: Mapping[str, Any] | None, default: str) -> str:
    if isinstance(result, Mapping):
        return sanitize_text(result.get("error") or result.get("message") or default)
    return default


def _queue_price_refresh(query: dict[str, Any]) -> None:
    answer = query.get("answer")
    if not isinstance(answer, Mapping) or _dependencies.price_refresher is None:
        return
    if query.get("job_plan", {}).get("price_refresh_pending"):
        return
    query.setdefault("job_plan", {})["price_refresh_pending"] = True
    publish_chat_progress(
        str(query["query_id"]),
        "price_refresh",
        "queued",
        data_state=str(answer.get("data_state") or "normalizing"),
        payload={"message": "Price refresh queued asynchronously"},
        idempotency_key="price_refresh:queued",
    )
    _runtime.queue.enqueue(str(query["query_id"]), kind="price_refresh", available_at=_timestamp())


def _price_refresh_needed(result: Mapping[str, Any], answer: Mapping[str, Any]) -> bool:
    if result.get("price_refresh_pending") or result.get("refresh_status") in {"queued", "processing"}:
        return True
    parts = answer.get("quote")
    if isinstance(parts, Mapping):
        values = parts.get("parts", ())
        return any(isinstance(part, Mapping) and part.get("freshness") == "stale" for part in values) if isinstance(values, list) else False
    return False


def _merge_price_result(answer: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(answer))
    if isinstance(result.get("answer"), Mapping):
        candidate = result["answer"]
        for key in ("procedure", "quote", "warnings", "source_watermark"):
            if key in candidate:
                merged[key] = deepcopy(candidate[key])
    elif isinstance(result.get("quote"), Mapping):
        merged["quote"] = deepcopy(result["quote"])
    merged["data_state"] = _result_data_state(result, default=str(answer.get("data_state") or "normalized"))
    merged["answer_status"] = "available" if merged.get("procedure") is not None or merged.get("quote") is not None else str(merged.get("answer_status") or "partial")
    merged["updated_at"] = _timestamp()
    merged["revision_id"] = _contract_uuid("answer-revision", result.get("revision_id") or json.dumps(result, sort_keys=True, default=str))
    if result.get("revision_id") and str(result["revision_id"]) != merged["revision_id"]:
        merged["source_revision_id"] = str(result["revision_id"])
    return merged


def _invoke(callback: Callable[..., Any], *args: Any) -> Any:
    return callback(*args)


def _default_normalized_cache(
    query: str,
    vehicle: Mapping[str, Any],
    _intent: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    try:
        from .article_intake import VehicleTarget
        from .knowledge_catalog import load_vehicle_knowledge_catalog
        from .worker import (
            _cached_derived_job_plan,
            _catalog_needs_procedure_content_hydration,
        )

        year = vehicle.get("model_year", vehicle.get("year"))
        region = vehicle.get("region") or os.getenv("AUTODATA_SOURCE_REGION", "US")
        if year is None:
            return None
        target = VehicleTarget(
            str(vehicle["make"]),
            str(vehicle["model"]),
            year,
            str(region),
            vehicle.get("trim"),
            vehicle.get("body_style"),
            vehicle.get("drivetrain"),
            vehicle.get("engine_displacement_l", vehicle.get("engine")),
        )
        catalog = load_vehicle_knowledge_catalog(target, query=query)
        if _catalog_needs_procedure_content_hydration(query, catalog):
            # A title/labor row is not a usable procedure. Treat it as a
            # source miss so the retriever hydrates only the selected article
            # detail and labor resources.
            return None
        derived = _cached_derived_job_plan(query, dict(vehicle), catalog)
        if derived is not None:
            return {**derived, "cache_hit": True, "data_state": "normalized"}
        if not catalog:
            return None
        # Normalized articles are still useful on a warm read.  The local
        # deterministic composer is used only when the catalog has no reusable
        # composed revision; it never calls a source or model provider.
        composed = _default_composer(query, vehicle, _source_articles({"articles": catalog}))
        return {**dict(composed), "cache_hit": True, "data_state": "normalized"}
    except Exception:  # noqa: BLE001 - a cache miss is safe and retryable
        return None


def _default_source_retriever(
    query: str,
    vehicle: Mapping[str, Any],
    _operations: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any]:
    from .article_intake import VehicleTarget
    from .worker import _load_autoapi_job_catalog

    year = vehicle.get("model_year", vehicle.get("year"))
    if year is None:
        return {"status": "unavailable", "data_state": "unavailable", "reason": "vehicle_year_missing"}
    target = VehicleTarget(
        str(vehicle["make"]),
        str(vehicle["model"]),
        year,
        str(vehicle.get("region") or os.getenv("AUTODATA_SOURCE_REGION", "US")),
        vehicle.get("trim"),
        vehicle.get("body_style"),
        vehicle.get("drivetrain"),
        vehicle.get("engine_displacement_l", vehicle.get("engine")),
    )
    records, source_info = _load_autoapi_job_catalog(dict(vehicle), target, query=query)
    if not records:
        return {
            "status": "unavailable",
            "data_state": "unavailable",
            "vehicle": dict(vehicle),
            "source": source_info,
            "articles": [],
        }
    return {
        "status": "source_unnormalized",
        "data_state": "source_unnormalized",
        "vehicle": dict(vehicle),
        "articles": records,
        "source": source_info,
        "normalization_pending": True,
    }


def _default_composer(
    query: str,
    vehicle: Mapping[str, Any],
    articles: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any]:
    from .job_plan import build_quote_and_procedure

    result = build_quote_and_procedure(query, vehicle, articles)
    return {**result, "data_state": "normalized"}


def _source_articles(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    values: Any = result.get("articles")
    if values is None:
        values = result.get("catalog")
    if values is None:
        values = result.get("records")
    if values is None:
        values = result.get("results")
    if isinstance(values, Mapping):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return []
    output: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        article = value.get("article", value)
        if isinstance(article, Mapping):
            output.append(dict(article))
    return output


def _answer_from_result(
    result: Mapping[str, Any],
    *,
    vehicle: Mapping[str, Any],
    query_id: str,
    default_data_state: str | None = None,
    force_data_state: str | None = None,
) -> dict[str, Any]:
    safe = redact_secrets(dict(result))
    nested = safe.get("answer")
    base = dict(nested) if isinstance(nested, Mapping) else {}
    answer_vehicle = safe.get("vehicle") or base.get("vehicle") or vehicle
    if not isinstance(answer_vehicle, Mapping):
        answer_vehicle = vehicle
    procedure = safe.get("procedure", base.get("procedure"))
    quote = safe.get("quote", base.get("quote"))
    data_state = force_data_state or _result_data_state(safe, default=default_data_state or "normalizing")
    status = str(safe.get("answer_status") or base.get("answer_status") or "").strip()
    result_status = str(safe.get("status") or "").casefold()
    if status not in {"options", "processing", "available", "partial", "complete", "failed", "needs_review"}:
        if result_status in {"failed", "unavailable", "dead_letter"} and not procedure and not quote:
            status = "failed"
        elif data_state == "needs_review":
            status = "needs_review"
        elif procedure is not None or quote is not None:
            status = "available"
        elif data_state == "source_unnormalized":
            status = "partial"
        elif data_state == "normalizing":
            status = "processing"
        else:
            status = "failed"
    warnings = safe.get("warnings", base.get("warnings", []))
    if not isinstance(warnings, list):
        warnings = [warnings]
    warnings = [item for item in warnings if isinstance(item, Mapping)]
    for reason in safe.get("review_reasons", ()) if isinstance(safe.get("review_reasons", ()), (list, tuple)) else ():
        reason_text = str(reason).strip()
        if reason_text and not any(str(item.get("message")) == reason_text for item in warnings):
            warnings.append({"message": reason_text, "status": "needs_review"})
    answer: dict[str, Any] = {
        "answer_status": status,
        "data_state": data_state,
        "vehicle": dict(answer_vehicle),
        "procedure": deepcopy(procedure) if isinstance(procedure, Mapping) else None,
        "quote": deepcopy(quote) if isinstance(quote, Mapping) else None,
        "warnings": deepcopy(warnings),
        "updated_at": _timestamp(),
        # Event history is projected at the public boundary. Keeping it out
        # of the persisted answer prevents recursive payload growth.
        "worker_stream": [],
    }
    source_watermark = safe.get("source_watermark")
    if source_watermark is None and isinstance(safe.get("source"), Mapping):
        source_watermark = safe["source"].get("source_watermark") or safe["source"].get("source_version")
    if source_watermark:
        answer["source_watermark"] = str(source_watermark)
    revision = safe.get("revision_id") or base.get("revision_id")
    if revision is None and isinstance(safe.get("derived_article"), Mapping):
        revision = safe["derived_article"].get("revision_id")
    if revision:
        answer["revision_id"] = _contract_uuid("answer-revision", revision)
        if str(revision) != answer["revision_id"]:
            answer["source_revision_id"] = str(revision)
    else:
        stable_answer = {
            key: value
            for key, value in answer.items()
            if key not in {"updated_at", "worker_stream"}
        }
        answer["revision_id"] = _stable_uuid(
            "answer-revision",
            json.dumps(_stable_revision_material(stable_answer), sort_keys=True, default=str),
        )
    if data_state == "source_unnormalized":
        raw_source = safe.get("source_unnormalized")
        if not isinstance(raw_source, Mapping):
            raw_source = {
                "source_uri": safe.get("source_uri"),
                "articles": _source_articles(safe),
                "normalization_pending": bool(safe.get("normalization_pending", True)),
            }
        answer["source_unnormalized"] = dict(raw_source)
    return answer


def _apply_answer(query: dict[str, Any], answer: Mapping[str, Any]) -> None:
    query_id = str(query["query_id"])
    updated = deepcopy(dict(answer))
    updated["worker_stream"] = []
    if not str(updated.get("revision_id") or "").strip():
        stable_answer = {
            key: value
            for key, value in updated.items()
            if key not in {"updated_at", "worker_stream"}
        }
        updated["revision_id"] = _stable_uuid(
            "answer-revision",
            f"{query_id}:{json.dumps(stable_answer, sort_keys=True, default=str)}",
        )
    updated["revision_id"] = _contract_uuid("answer-revision", updated["revision_id"])
    existing_updates = query.setdefault("updates", [])
    if any(item.get("revision_id") == updated["revision_id"] for item in existing_updates if isinstance(item, Mapping)):
        query["answer"] = updated
        return
    query["answer"] = updated
    update = {
        "revision_id": updated["revision_id"],
        "data_state": updated["data_state"],
        "answer_status": updated["answer_status"],
        "answer": deepcopy(updated),
        "updated_at": updated["updated_at"],
    }
    existing_updates.append(update)


def _new_answer(
    vehicle: Mapping[str, Any],
    *,
    answer_status: str,
    data_state: str,
    warnings: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "answer_status": answer_status,
        "data_state": data_state,
        "vehicle": dict(vehicle),
        "procedure": None,
        "quote": None,
        "warnings": [dict(item) for item in warnings if isinstance(item, Mapping)],
        "updated_at": _timestamp(),
        "worker_stream": [],
    }


def _initial_warnings(intent: ChatIntent) -> list[dict[str, Any]]:
    if intent.clarification:
        return [{"message": intent.clarification, "status": "needs_review"}]
    return []


def _new_job_plan(query_id: str, intent: ChatIntent, vehicle: Mapping[str, Any] | None) -> dict[str, Any]:
    operations = [dict(item) for item in intent.requested_operations]
    identity = hashlib.sha256(
        json.dumps(
            {
                "query_id": query_id,
                "vehicle": dict(vehicle or intent.vehicle_observation),
                "operations": operations,
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "job_plan_id": _stable_uuid("job-plan", query_id),
        "query_id": query_id,
        "status": "pending",
        "processing_version": PROCESSING_VERSION,
        "request_fingerprint": identity,
        "requested_operations": operations,
        "supporting_operations": [],
        "attempt_count": 0,
        "source_watermarks": [],
    }


def _vehicle_candidates(message: str, principal: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    callback = _dependencies.vehicle_candidates
    if callback is not None:
        values = callback(message, principal)
    else:
        values = principal.get("vehicle_candidates", principal.get("candidates", ()))
        if not values:
            values = _environment_candidates()
    if isinstance(values, Mapping):
        values = [values]
    candidates = [value for value in values if isinstance(value, Mapping)] if isinstance(values, Iterable) else []
    if candidates:
        return [dict(candidate) for candidate in candidates]
    # A fully specified message can safely act as its own one-item candidate;
    # this keeps the default local service useful without inventing a catalog.
    try:
        parsed = interpret_chat_message(message, ()).vehicle_observation
    except Exception:  # noqa: BLE001 - the normal interpreter reports review state
        return []
    if not all(parsed.get(key) is not None for key in ("year", "make", "model")):
        return []
    candidate = {
        key: parsed.get(key)
        for key in (
            "year",
            "make",
            "model",
            "region",
            "body_style",
            "trim",
            "drivetrain",
            "engine_displacement_l",
        )
        if parsed.get(key) is not None
    }
    candidate["region"] = candidate.get("region") or os.getenv("AUTODATA_SOURCE_REGION", "US")
    candidate["vehicle_id"] = _stable_uuid("vehicle", json.dumps(candidate, sort_keys=True, default=str))
    candidate["candidate_key"] = _vehicle_candidate_key(candidate)
    candidate["confidence"] = 1.0
    return [candidate]


def _environment_candidates() -> list[Mapping[str, Any]]:
    raw = os.getenv("AUTODATA_CHAT_VEHICLE_CANDIDATES_JSON", "").strip()
    if not raw:
        return []
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return values if isinstance(values, list) else []


def _vehicle_options(intent: ChatIntent) -> list[dict[str, Any]]:
    values = intent.vehicle_observation.get("candidates", [])
    if not isinstance(values, list):
        return []
    options: list[dict[str, Any]] = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, Mapping):
            continue
        option = dict(value)
        option_number = int(option.get("option_number", index))
        vehicle_id = str(option.get("vehicle_id") or option.get("candidate_key") or "").strip()
        candidate_key = str(option.get("candidate_key") or vehicle_id).strip()
        option["option_number"] = option_number
        option["selection"] = {
            "selection_type": "vehicle",
            "option_number": option_number,
            "vehicle_id": vehicle_id or None,
        }
        option["clickable"] = True
        option["candidate_key"] = candidate_key
        options.append(option)
    return options


def _selected_vehicle(intent: ChatIntent, options: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    if intent.vehicle_observation.get("status") != "matched":
        return None
    selected_id = str(intent.vehicle_observation.get("selected_vehicle_id") or "").strip()
    selected_key = str(intent.vehicle_observation.get("selected_candidate_key") or "").strip()
    for option in options:
        if selected_id and str(option.get("vehicle_id") or "").strip() == selected_id:
            return dict(option)
        if selected_key and str(option.get("candidate_key") or "").strip() == selected_key:
            return dict(option)
    return dict(intent.vehicle_observation)


def _query_vehicle(query: Mapping[str, Any]) -> dict[str, Any] | None:
    intent = query.get("_intent")
    if not isinstance(intent, Mapping):
        return None
    vehicle = intent.get("vehicle_observation")
    if not isinstance(vehicle, Mapping) or vehicle.get("status") not in {"matched", "unresolved"}:
        return None
    if not vehicle.get("make") or not vehicle.get("model") or vehicle.get("year") is None:
        return None
    selected_key = str(
        query.get("_selected_candidate_key")
        or vehicle.get("selected_candidate_key")
        or vehicle.get("selected_vehicle_id")
        or ""
    ).strip()
    candidates = query.get("_candidates", ())
    if selected_key and isinstance(candidates, (list, tuple)):
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            if selected_key in {
                str(candidate.get("candidate_key") or "").strip(),
                str(candidate.get("vehicle_id") or "").strip(),
            }:
                return {**dict(vehicle), **dict(candidate), "status": "matched"}
    return dict(vehicle)


def _intent_dict(intent: ChatIntent) -> dict[str, Any]:
    return {
        "vehicle_observation": deepcopy(intent.vehicle_observation),
        "requested_operations": [dict(item) for item in intent.requested_operations],
        "quote_requested": intent.quote_requested,
        "procedure_requested": intent.procedure_requested,
        "clarification": intent.clarification,
    }


def _intent_from_dict(value: Mapping[str, Any]) -> ChatIntent:
    return ChatIntent(
        vehicle_observation=dict(value.get("vehicle_observation") or {}),
        requested_operations=tuple(
            dict(item) for item in value.get("requested_operations", ()) if isinstance(item, Mapping)
        ),
        quote_requested=bool(value.get("quote_requested")),
        procedure_requested=bool(value.get("procedure_requested")),
        clarification=value.get("clarification"),
    )


def _public_query(query: Mapping[str, Any]) -> dict[str, Any]:
    public = redact_secrets(deepcopy(dict(query)))
    public.pop("_intent", None)
    public.pop("_candidates", None)
    public.pop("_selected_candidate_key", None)
    public.pop("_selected_option_number", None)
    public.pop("_selection", None)
    job_plan = public.get("job_plan")
    if isinstance(job_plan, dict):
        # Source and normalized provider payloads are persisted for retries,
        # but are not part of the compact query projection.  The answer and
        # replay stream expose the bounded public revisions instead.
        job_plan.pop("_source_result", None)
        job_plan.pop("_normalized_result", None)
    answer = public.get("answer")
    if isinstance(answer, dict):
        answer["worker_stream"] = list(
            iter_progress_events(
                str(public["query_id"]),
                principal=_owner_principal(public),
            )
        )
    return public


def _owner_principal(query: Mapping[str, Any]) -> dict[str, str]:
    return {
        "owner_id": str(query.get("owner_id") or ""),
        "organization_id": str(query.get("organization_id") or ""),
    }


def _save(query: Mapping[str, Any]) -> None:
    _runtime.repository.save(query)
    if _dependencies.persist is not None:
        _dependencies.persist(_public_query(query))


def _result_data_state(result: Mapping[str, Any], *, default: str) -> str:
    if result.get("normalization_pending"):
        return "source_unnormalized"
    value = str(result.get("data_state") or "").strip()
    if value in _ALLOWED_DATA_STATES:
        return value
    status = str(result.get("status") or "").casefold()
    if status in {"source_unnormalized", "rejected"} or result.get("normalization_pending"):
        return "source_unnormalized"
    if status in {"unavailable", "failed", "dead_letter"}:
        return "unavailable"
    if status == "needs_review":
        return "needs_review"
    return default if default in _ALLOWED_DATA_STATES else "normalizing"


def _source_candidate_key(value: Mapping[str, Any]) -> str:
    return str(value.get("candidate_key") or value.get("vehicle_id") or _vehicle_candidate_key(value)).strip()


def _vehicle_candidate_key(value: Mapping[str, Any]) -> str:
    parts = [str(value.get(key) or "") for key in ("year", "make", "model", "region")]
    return re.sub(r"[^a-z0-9]+", "-", "-".join(parts).casefold()).strip("-")


def _conversation_id(principal: Mapping[str, Any], key: str, requested: str | None = None) -> str:
    raw = requested or principal.get("conversation_id")
    try:
        return str(uuid.UUID(str(raw))) if raw else _stable_uuid("conversation", key)
    except (ValueError, AttributeError):
        return _stable_uuid("conversation", str(raw))


def _principal_identity(principal: Mapping[str, Any]) -> tuple[str, str]:
    owner = str(
        principal.get("owner_id")
        or principal.get("user_id")
        or principal.get("subject")
        or ""
    ).strip()
    organization = str(
        principal.get("organization_id")
        or principal.get("org_id")
        or ""
    ).strip()
    if not owner and organization:
        owner = organization
    if not organization and owner:
        organization = owner
    if not owner or not organization:
        raise ValueError("chat principal requires owner_id and organization_id")
    return owner, organization


def _request_params(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("chat request_params must be an object")
    return redact_secrets(deepcopy(dict(value)))


def _request_fingerprint(
    *,
    owner_id: str,
    organization_id: str,
    conversation_id: str,
    message: str,
    request_params: Mapping[str, Any],
) -> str:
    normalized_message = re.sub(r"\s+", " ", message).strip().casefold()
    material = {
        "owner_id": owner_id,
        "organization_id": organization_id,
        "conversation_id": conversation_id,
        "message": normalized_message,
        "request_params": request_params,
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _authorize_query(query: Mapping[str, Any], principal: Mapping[str, Any] | None) -> None:
    owner = str(query.get("owner_id") or "").strip()
    organization = str(query.get("organization_id") or "").strip()
    if not owner and not organization:
        return
    if not isinstance(principal, Mapping):
        raise PermissionError("chat owner authorization is required")
    try:
        requested_owner, requested_organization = _principal_identity(principal)
    except ValueError as error:
        raise PermissionError("chat owner authorization is required") from error
    if owner != requested_owner:
        raise PermissionError("chat owner authorization failed")
    if organization != requested_organization:
        raise PermissionError("chat organization authorization failed")


def _require_durable_runtime() -> None:
    if _runtime is _UNAVAILABLE_RUNTIME:
        raise ChatDurabilityError("durable chat runtime is not configured")


def _normalize_selection(selection: Mapping[str, Any]) -> dict[str, Any]:
    nested = selection.get("selection")
    if isinstance(nested, Mapping):
        merged = dict(selection)
        merged.pop("selection", None)
        merged.update(nested)
        return merged
    normalized = dict(selection)
    if normalized.get("option_number") is None and isinstance(nested, (str, int)):
        normalized["option_number"] = nested
    return normalized


def _selection_matches(query: Mapping[str, Any], selection: Mapping[str, Any], previous_key: str) -> bool:
    selected_key = str(selection.get("vehicle_id") or selection.get("candidate_key") or "").strip()
    option_number = _positive_int(selection.get("option_number"))
    return (
        (selected_key and selected_key == previous_key)
        or (option_number is not None and option_number == query.get("_selected_option_number"))
    )


def _compact_progress_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError("chat progress payload must be a mapping")
    compact = redact_secrets(dict(payload))
    answer = compact.get("answer")
    if isinstance(answer, Mapping):
        compact["answer"] = {
            key: answer[key]
            for key in ("answer_status", "data_state", "revision_id", "source_watermark")
            if key in answer
        }
    return compact


def _stable_revision_material(value: Any) -> Any:
    """Remove retry/history timestamps before deriving a public revision ID."""

    if isinstance(value, Mapping):
        volatile = {
            "created_at",
            "occurred_at",
            "retrieved_at",
            "timestamp",
            "updated_at",
            "worker_stream",
            "history",
            "updates",
        }
        return {
            str(key): _stable_revision_material(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key).casefold() not in volatile
        }
    if isinstance(value, (list, tuple, set)):
        return [_stable_revision_material(child) for child in value]
    return value


def _stable_uuid(kind: str, value: Any) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata:chat:{kind}:v1:{value}"))


def _contract_uuid(kind: str, value: Any) -> str:
    text = str(value or "").strip()
    try:
        return str(uuid.UUID(text))
    except (ValueError, AttributeError):
        return _stable_uuid(kind, text)


def _timestamp(epoch_seconds: float | None = None) -> str:
    value = datetime.now(UTC) if epoch_seconds is None else datetime.fromtimestamp(epoch_seconds, UTC)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=UTC)


def _require_message(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("chat message must be a non-empty string")
    return re.sub(r"\s+", " ", value.strip())


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _configured_max_attempts(value: Any) -> int:
    try:
        configured = int(value)
    except (TypeError, ValueError):
        configured = DEFAULT_MAX_ATTEMPTS
    return max(1, min(configured, 10))


def _has_usable_answer(answer: Any) -> bool:
    return isinstance(answer, Mapping) and (
        answer.get("procedure") is not None or answer.get("quote") is not None
    )


def _claim_query_id(claim: Any) -> str:
    return _required_text(getattr(claim, "query_id", claim), "query_id")


def _ack_chat_claim(claim: Any) -> None:
    if not getattr(claim, "lease_token", None):
        return
    ack = getattr(_runtime.queue, "ack", None)
    if callable(ack):
        ack(claim)


__all__ = [
    "ChatDependencies",
    "InMemoryChatRepository",
    "InMemoryChatQueue",
    "PROCESSING_VERSION",
    "configure_chat_dependencies",
    "configure_chat_runtime",
    "configure_chat_runtime_from_environment",
    "create_chat_query",
    "drain_chat_jobs",
    "ensure_chat_runtime",
    "ChatConflictError",
    "ChatDurabilityError",
    "ChatRuntime",
    "get_chat_query",
    "iter_chat_events",
    "process_chat_jobs",
    "process_chat_price_jobs",
    "publish_chat_progress",
    "select_chat_vehicle",
]
