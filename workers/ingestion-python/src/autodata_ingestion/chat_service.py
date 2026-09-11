"""Fast, cache-first orchestration for one natural-language chat request.

The service owns the request state machine and keeps source/model work behind
small dependency callables.  The default callables bridge to the existing
ingestion runtime; tests and local smoke runs can install deterministic fakes.
The in-process repository is intentionally shaped like a durable repository so
that a PostgreSQL-backed adapter can be supplied without changing the public
chat functions.
"""

from __future__ import annotations

from collections import deque
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


@dataclass(frozen=True)
class ChatDependencies:
    """Provider-neutral boundaries used by the chat state machine."""

    vehicle_candidates: Callable[[str, Mapping[str, Any]], Iterable[Mapping[str, Any]]] | None = None
    normalized_cache: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None] | None = None
    source_retriever: Callable[[str, Mapping[str, Any], Iterable[Mapping[str, Any]]], Mapping[str, Any]] | None = None
    composer: Callable[[str, Mapping[str, Any], Iterable[Mapping[str, Any]]], Mapping[str, Any]] | None = None
    persist: Callable[[Mapping[str, Any]], Any] | None = None
    max_attempts: int = DEFAULT_MAX_ATTEMPTS


class InMemoryChatRepository:
    """Deterministic query/job repository used by local workers and tests."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._queries: dict[str, dict[str, Any]] = {}
        self._idempotency: dict[str, str] = {}
        self._pending: deque[str] = deque()
        self._pending_ids: set[str] = set()

    def save(self, query: Mapping[str, Any]) -> None:
        if not isinstance(query, Mapping):
            raise TypeError("chat query must be a mapping")
        query_id = _required_text(query.get("query_id"), "query_id")
        idempotency_key = _required_text(query.get("idempotency_key"), "idempotency_key")
        with self._lock:
            self._queries[query_id] = deepcopy(dict(query))
            self._idempotency[idempotency_key] = query_id

    def get(self, query_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._queries.get(str(query_id).strip())
            return deepcopy(value) if value is not None else None

    def get_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._lock:
            query_id = self._idempotency.get(str(idempotency_key).strip())
            if query_id is None:
                return None
            value = self._queries.get(query_id)
            return deepcopy(value) if value is not None else None

    def enqueue(self, query_id: str) -> None:
        query_text = _required_text(query_id, "query_id")
        with self._lock:
            if query_text not in self._pending_ids:
                self._pending.append(query_text)
                self._pending_ids.add(query_text)

    def pop_pending(self, limit: int | None = None) -> list[str]:
        if limit is not None and limit < 1:
            return []
        with self._lock:
            count = len(self._pending) if limit is None else min(limit, len(self._pending))
            values = [self._pending.popleft() for _ in range(count)]
            self._pending_ids.difference_update(values)
            return values


_dependencies = ChatDependencies()
_repository: Any = InMemoryChatRepository()
_event_store = ProgressEventStore()
_runtime_lock = threading.RLock()


def configure_chat_runtime(
    *,
    dependencies: ChatDependencies | None = None,
    repository: Any | None = None,
    event_store: ProgressEventStore | None = None,
) -> None:
    """Install deterministic boundaries for one process or test run."""

    global _dependencies, _repository, _event_store
    with _runtime_lock:
        _dependencies = dependencies or ChatDependencies()
        _repository = repository or InMemoryChatRepository()
        _event_store = event_store or ProgressEventStore()
        ProgressEventStore.set_current(_event_store)


configure_chat_dependencies = configure_chat_runtime


def create_chat_query(
    message: str,
    *,
    idempotency_key: str,
    principal: Mapping[str, Any],
) -> dict[str, Any]:
    """Create or replay one query and begin its cache-first execution."""

    message_text = _require_message(message)
    key = _required_text(idempotency_key, "idempotency_key")
    if not isinstance(principal, Mapping):
        raise TypeError("chat principal must be a mapping")
    with _runtime_lock:
        existing = _repository.get_by_idempotency(key)
        if existing is not None:
            return _public_query(existing)

        candidates = _vehicle_candidates(message_text, principal)
        intent = interpret_chat_message(message_text, tuple(candidates))
        query_id = _stable_uuid("query", key)
        conversation_id = _conversation_id(principal, key)
        correlation_id = _stable_uuid("correlation", query_id)
        register_query_context(
            query_id,
            correlation_id=correlation_id,
            request_id=query_id,
            projection_id=_stable_uuid("projection", query_id),
        )
        options = _vehicle_options(intent)
        matched_vehicle = _selected_vehicle(intent, options)
        ambiguous = intent.vehicle_observation.get("status") == "ambiguous"
        query: dict[str, Any] = {
            "query_id": query_id,
            "conversation_id": conversation_id,
            "message": message_text,
            "idempotency_key": key,
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


def select_chat_vehicle(query_id: str, selection: Mapping[str, Any]) -> dict[str, Any]:
    """Apply a numbered or clicked selection and start the pending request."""

    query_text = _required_text(query_id, "query_id")
    if not isinstance(selection, Mapping):
        raise TypeError("chat selection must be a mapping")
    with _runtime_lock:
        query = _repository.get(query_text)
        if query is None:
            raise KeyError(f"chat query {query_text} was not found")
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
        previous_key = str(query.get("_selected_candidate_key") or "").strip()
        if previous_key and previous_key != selected_key:
            raise ValueError("chat query already has a different vehicle selection")
        if previous_key == selected_key and query.get("status") != "awaiting_vehicle":
            return _public_query(query)
        query["_selected_candidate_key"] = selected_key
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
        )
        _start_execution(query)
        return _public_query(query)


def get_chat_query(query_id: str) -> dict[str, Any]:
    query_text = _required_text(query_id, "query_id")
    with _runtime_lock:
        query = _repository.get(query_text)
        if query is None:
            raise KeyError(f"chat query {query_text} was not found")
        return _public_query(query)


def iter_chat_events(
    query_id: str,
    *,
    last_event_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    return iter_progress_events(query_id, last_event_id=last_event_id)


def publish_chat_progress(
    query_id: str,
    stage: str,
    status: str,
    *,
    data_state: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish one idempotent, redacted progress frame correlated to a query."""

    return publish_progress_event(
        query_id,
        stage,
        status,
        data_state=data_state,
        payload=redact_secrets(dict(payload)),
    )


def process_chat_jobs(*, max_jobs: int | None = None) -> list[dict[str, Any]]:
    """Process queued source/model fan-out without blocking the HTTP caller."""

    with _runtime_lock:
        query_ids = _repository.pop_pending(max_jobs)
    completed: list[dict[str, Any]] = []
    for query_id in query_ids:
        _process_one_job(query_id)
        try:
            completed.append(get_chat_query(query_id))
        except KeyError:
            continue
    return completed


drain_chat_jobs = process_chat_jobs


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
        )
    if isinstance(cached, Mapping) and cached.get("cache_hit", True) is not False:
        answer = _answer_from_result(cached, vehicle=vehicle, query_id=query_id)
        _apply_answer(query, answer)
        query["status"] = "available" if answer["answer_status"] not in {"failed", "needs_review"} else "failed"
        query["job_plan"]["status"] = "complete"
        publish_chat_progress(
            query_id,
            "lookup_derived",
            "completed",
            data_state=answer["data_state"],
            payload={"message": "Reusable cached answer returned", "cache_hit": True, "revision_id": answer.get("revision_id")},
        )
        publish_chat_progress(
            query_id,
            "answer",
            "completed",
            data_state=answer["data_state"],
            payload={"message": "Cached answer is available", "answer": answer, "revision_id": answer.get("revision_id")},
        )
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
    )
    _repository.enqueue(query_id)
    _save(query)


def _process_one_job(query_id: str) -> None:
    with _runtime_lock:
        query = _repository.get(query_id)
        if query is None:
            return
        job = query.get("job_plan")
        vehicle = _query_vehicle(query)
        if not isinstance(job, dict) or vehicle is None or job.get("status") in _TERMINAL_JOB_STATES:
            return
        dependencies = _dependencies
        max_attempts = _configured_max_attempts(dependencies.max_attempts)
        job["status"] = "processing"
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
                source_result = {"status": "unavailable", "data_state": "unavailable"}
            job["_source_result"] = redact_secrets(dict(source_result))
            source_result = job["_source_result"]

        source_state = _result_data_state(source_result, default="source_unnormalized")
        source_answer = _answer_from_result(source_result, vehicle=vehicle, query_id=query_id)
        _apply_answer(query, source_answer)
        publish_chat_progress(
            query_id,
            "source_retrieval",
            "completed",
            data_state=source_state,
            payload={
                "message": "Source data is available while normalization continues",
                "source_uri": source_result.get("source_uri"),
                "data_state": source_state,
            },
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
        )
        articles = _source_articles(source_result)
        if dependencies.composer is None and not articles:
            job["status"] = "complete"
            query["status"] = "available" if source_answer["answer_status"] != "failed" else "failed"
            _save(query)
            return
        publish_chat_progress(
            query_id,
            "procedure_composition",
            "processing",
            data_state="normalizing",
            payload={"message": "Composing quote and procedure from retrieved source data"},
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
        if isinstance(composed, Mapping):
            normalized_answer = _answer_from_result(
                composed,
                vehicle=vehicle,
                query_id=query_id,
                default_data_state="normalized",
            )
            _apply_answer(query, normalized_answer)
            publish_chat_progress(
                query_id,
                "procedure_composition",
                "completed",
                data_state=normalized_answer["data_state"],
                payload={
                    "message": "Quote and procedure revision published",
                    "answer": normalized_answer,
                    "revision_id": normalized_answer.get("revision_id"),
                },
            )
            publish_chat_progress(
                query_id,
                "answer",
                "completed",
                data_state=normalized_answer["data_state"],
                payload={"message": "Same answer updated with normalized data", "answer": normalized_answer, "revision_id": normalized_answer.get("revision_id")},
            )
        job["status"] = "complete"
        query["status"] = "available"
        publish_chat_progress(
            query_id,
            "enrichment",
            "queued",
            data_state=query["answer"]["data_state"],
            payload={"message": "Optional enrichment remains asynchronous"},
        )
        _save(query)


def _handle_retry_result(query: dict[str, Any], job: dict[str, Any], retry: Mapping[str, Any]) -> None:
    query_id = str(query["query_id"])
    job["last_error"] = retry.get("error")
    job["retry"] = {key: value for key, value in retry.items() if key != "event"}
    if retry.get("status") == "dead_letter":
        job["status"] = "dead_letter"
        query["status"] = "available" if _has_usable_answer(query.get("answer")) else "failed"
        _save(query)
        return
    job["status"] = "pending"
    query["status"] = "available" if _has_usable_answer(query.get("answer")) else "processing"
    _repository.enqueue(query_id)
    _save(query)


def _cache_lookup(query: Mapping[str, Any], vehicle: Mapping[str, Any], intent: Mapping[str, Any]) -> Mapping[str, Any] | None:
    callback = _dependencies.normalized_cache or _default_normalized_cache
    return _invoke(callback, str(query["message"]), vehicle, intent)


def _source_retrieve(query: Mapping[str, Any], vehicle: Mapping[str, Any]) -> Mapping[str, Any]:
    callback = _dependencies.source_retriever or _default_source_retriever
    operations = query.get("_intent", {}).get("requested_operations", ())
    return _invoke(callback, str(query["message"]), vehicle, operations)


def _compose(query: Mapping[str, Any], vehicle: Mapping[str, Any], articles: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    callback = _dependencies.composer or _default_composer
    return _invoke(callback, str(query["message"]), vehicle, tuple(articles))


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
        from .worker import _cached_derived_job_plan

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
) -> dict[str, Any]:
    safe = redact_secrets(dict(result))
    nested = safe.get("answer")
    base = dict(nested) if isinstance(nested, Mapping) else {}
    answer_vehicle = safe.get("vehicle") or base.get("vehicle") or vehicle
    if not isinstance(answer_vehicle, Mapping):
        answer_vehicle = vehicle
    procedure = safe.get("procedure", base.get("procedure"))
    quote = safe.get("quote", base.get("quote"))
    data_state = _result_data_state(safe, default=default_data_state or "normalizing")
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
        "worker_stream": list(iter_chat_events(query_id)),
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
        answer["revision_id"] = str(revision)
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
    update_number = len(query.get("updates", [])) + 1
    if not str(updated.get("revision_id") or "").strip():
        updated["revision_id"] = _stable_uuid("answer-revision", f"{query_id}:{update_number}")
    query["answer"] = updated
    update = {
        "revision_id": updated["revision_id"],
        "data_state": updated["data_state"],
        "answer_status": updated["answer_status"],
        "answer": deepcopy(updated),
        "updated_at": updated["updated_at"],
    }
    query.setdefault("updates", []).append(update)


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
    answer = public.get("answer")
    if isinstance(answer, dict):
        answer["worker_stream"] = list(iter_chat_events(str(public["query_id"])))
    return public


def _save(query: Mapping[str, Any]) -> None:
    _repository.save(query)
    if _dependencies.persist is not None:
        _dependencies.persist(_public_query(query))


def _result_data_state(result: Mapping[str, Any], *, default: str) -> str:
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


def _conversation_id(principal: Mapping[str, Any], key: str) -> str:
    raw = principal.get("conversation_id")
    try:
        return str(uuid.UUID(str(raw))) if raw else _stable_uuid("conversation", key)
    except (ValueError, AttributeError):
        return _stable_uuid("conversation", str(raw))


def _stable_uuid(kind: str, value: Any) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata:chat:{kind}:v1:{value}"))


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


__all__ = [
    "ChatDependencies",
    "InMemoryChatRepository",
    "PROCESSING_VERSION",
    "configure_chat_dependencies",
    "configure_chat_runtime",
    "create_chat_query",
    "drain_chat_jobs",
    "get_chat_query",
    "iter_chat_events",
    "process_chat_jobs",
    "publish_chat_progress",
    "select_chat_vehicle",
]
