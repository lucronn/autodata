from __future__ import annotations

import http.client
import json
import sys
import threading
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.chat_service import (  # noqa: E402
    ChatConflictError,
    ChatDependencies,
    ChatDurabilityError,
    ChatRuntime,
    InMemoryChatQueue,
    InMemoryChatRepository,
    configure_chat_runtime,
    create_chat_query,
    get_chat_query,
    iter_chat_events,
    process_chat_price_jobs,
    process_chat_jobs,
    select_chat_vehicle,
)
from autodata_ingestion.http_service import dispatch_request, make_handler  # noqa: E402
from autodata_ingestion.progress_events import ProgressEventStore  # noqa: E402


VEHICLE_A = {
    "vehicle_id": "vehicle-rav4-4wd",
    "candidate_key": "rav4-4wd",
    "year": 1997,
    "make": "Toyota",
    "model": "RAV4",
    "region": "US",
    "drivetrain": "4WD",
}
VEHICLE_B = {
    "vehicle_id": "vehicle-rav4-2wd",
    "candidate_key": "rav4-2wd",
    "year": 1997,
    "make": "Toyota",
    "model": "RAV4",
    "region": "US",
    "drivetrain": "2WD",
}


def install_runtime(*, candidates, cache=None, source=None, compose=None, normalize=None, price=None):
    calls = {"source": [], "compose": []}

    def source_call(query, vehicle, operations):
        calls["source"].append((query, dict(vehicle), tuple(operations)))
        return source(query, vehicle, operations) if source else {
            "status": "source_unnormalized",
            "data_state": "source_unnormalized",
            "articles": [],
            "source_uri": "https://source.test/raw",
            "normalization_pending": True,
        }

    def compose_call(query, vehicle, articles):
        calls["compose"].append((query, dict(vehicle), tuple(articles)))
        return compose(query, vehicle, articles) if compose else {
            "status": "ready",
            "data_state": "normalized",
            "procedure": {"title": "Brake line service", "steps": []},
            "quote": {
                "required_hours": 1.0,
                "recommended_hours": 0.0,
                "total_hours": 1.0,
                "overlap_hours_removed": 0.0,
                "required_operations": [],
                "recommended_operations": [],
                "overlap_operations": [],
                "parts": [],
                "evidence": [],
            },
        }

    def normalize_call(query, vehicle, source_result):
        return normalize(query, vehicle, source_result) if normalize else {
            "articles": source_result.get("articles", []),
            "status": "ready",
        }

    def price_call(query, vehicle, normalized_result):
        return price(query, vehicle, normalized_result) if price else {
            "status": "current",
            "data_state": "normalized",
        }

    repository = InMemoryChatRepository()
    queue = InMemoryChatQueue()
    configure_chat_runtime(
        dependencies=ChatDependencies(
            vehicle_candidates=candidates,
            normalized_cache=cache or (lambda _query, _vehicle, _intent: None),
            source_retriever=source_call,
            normalizer=normalize_call,
            price_refresher=price_call,
            composer=compose_call,
        ),
        repository=repository,
        queue=queue,
        event_store=ProgressEventStore(),
        allow_in_memory=True,
    )
    calls["repository"] = repository
    return calls


@pytest.fixture(autouse=True)
def reset_runtime():
    yield
    configure_chat_runtime()


def principal(owner="owner-1", organization="org-1", conversation="conversation-1"):
    return {
        "owner_id": owner,
        "organization_id": organization,
        "conversation_id": conversation,
    }


def test_query_creation_is_idempotent_and_exposes_numbered_clickable_options():
    calls = install_runtime(candidates=lambda _message, _principal: (VEHICLE_B, VEHICLE_A))

    first = create_chat_query(
        "1997 Toyota RAV4 brake line replacement procedure and quote",
        idempotency_key="chat-duplicate-1",
        principal=principal(),
    )
    replay = create_chat_query(
        "1997 Toyota RAV4 brake line replacement procedure and quote",
        idempotency_key="chat-duplicate-1",
        principal=principal(),
    )

    assert replay == first
    assert first["status"] == "awaiting_vehicle"
    assert [option["option_number"] for option in first["vehicle_options"]] == [1, 2]
    assert [option["label"][:8] for option in first["vehicle_options"]] == ["Option 1", "Option 2"]
    assert all(
        option["selection"]["selection_type"] == "vehicle"
        and option["selection"]["option_number"] in {1, 2}
        for option in first["vehicle_options"]
    )
    assert calls["source"] == []
    assert calls["compose"] == []


def test_typed_or_clicked_vehicle_selection_executes_the_pending_request():
    def source(_query, vehicle, _operations):
        return {
            "status": "source_unnormalized",
            "data_state": "source_unnormalized",
            "vehicle": dict(vehicle),
            "articles": [{"article_id": "brake-line-source", "component": "brake_line"}],
            "source_uri": "https://source.test/brake-line",
            "normalization_pending": True,
        }

    calls = install_runtime(
        candidates=lambda _message, _principal: (VEHICLE_A, VEHICLE_B),
        source=source,
    )
    pending = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-selection-1",
        principal=principal(),
    )

    selected = select_chat_vehicle(
        pending["query_id"],
        {"selection_type": "vehicle", "option_number": "1"},
        principal=principal(),
    )
    process_chat_jobs()
    completed = get_chat_query(pending["query_id"], principal=principal())

    assert selected["query_id"] == pending["query_id"]
    assert selected["status"] in {"processing", "available"}
    assert completed["vehicle_options"] == []
    assert completed["answer"]["vehicle"]["vehicle_id"] == "vehicle-rav4-2wd"
    assert calls["source"][0][1]["vehicle_id"] == "vehicle-rav4-2wd"
    assert completed["updates"]
    assert completed["updates"][0]["data_state"] == "source_unnormalized"


def test_normalized_derived_cache_hit_skips_source_and_composition():
    cached = {
        "status": "ready",
        "data_state": "normalized",
        "cache_hit": True,
        "vehicle": dict(VEHICLE_A),
        "procedure": {"title": "Cached brake line service", "steps": []},
        "quote": {
            "required_hours": 2.0,
            "recommended_hours": 0.5,
            "total_hours": 2.5,
            "overlap_hours_removed": 0.0,
            "required_operations": [],
            "recommended_operations": [],
            "overlap_operations": [],
            "parts": [],
            "evidence": [],
        },
        "derived_article": {"revision_id": "cached-revision"},
    }
    calls = install_runtime(
        candidates=lambda _message, _principal: (VEHICLE_A,),
        cache=lambda _query, _vehicle, _intent: cached,
    )

    result = create_chat_query(
        "1997 Toyota RAV4 brake line replacement procedure and quote",
        idempotency_key="chat-cache-1",
        principal=principal(),
    )

    assert result["status"] == "available"
    assert result["answer"]["data_state"] == "normalized"
    assert result["answer"]["procedure"]["title"] == "Cached brake line service"
    uuid.UUID(result["answer"]["revision_id"])
    assert result["answer"]["source_revision_id"] == "cached-revision"
    assert calls["source"] == []
    assert calls["compose"] == []


def test_unambiguous_source_work_uses_the_canonical_candidate_identity():
    calls = install_runtime(candidates=lambda _message, _principal: (VEHICLE_A,))

    created = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-canonical-vehicle-1",
        principal=principal(),
    )
    process_chat_jobs()

    assert created["status"] in {"processing", "available"}
    assert calls["source"][0][1]["vehicle_id"] == VEHICLE_A["vehicle_id"]
    assert calls["source"][0][1]["drivetrain"] == VEHICLE_A["drivetrain"]


def test_source_unnormalized_answer_is_published_before_same_answer_is_normalized():
    source_data = {
        "status": "source_unnormalized",
        "data_state": "source_unnormalized",
        "vehicle": dict(VEHICLE_A),
        "articles": [{"article_id": "raw-brake-line", "body": "source body"}],
        "source_uri": "https://source.test/raw-brake-line",
        "normalization_pending": True,
    }
    normalized = {
        "status": "ready",
        "data_state": "normalized",
        "vehicle": dict(VEHICLE_A),
        "procedure": {"title": "Normalized brake line service", "steps": []},
        "quote": {
            "required_hours": 2.0,
            "recommended_hours": 0.0,
            "total_hours": 2.0,
            "overlap_hours_removed": 0.0,
            "required_operations": [],
            "recommended_operations": [],
            "overlap_operations": [],
            "parts": [],
            "evidence": [],
        },
    }
    calls = install_runtime(
        candidates=lambda _message, _principal: (VEHICLE_A,),
        source=lambda _query, _vehicle, _operations: source_data,
        compose=lambda _query, _vehicle, _articles: normalized,
    )

    created = create_chat_query(
        "1997 Toyota RAV4 brake line replacement procedure and quote",
        idempotency_key="chat-progress-1",
        principal=principal(),
    )
    before_worker = get_chat_query(created["query_id"], principal=principal())
    process_chat_jobs()
    after_worker = get_chat_query(created["query_id"], principal=principal())

    assert before_worker["answer"]["answer_status"] == "processing"
    assert after_worker["answer"]["procedure"]["title"] == "Normalized brake line service"
    assert [update["data_state"] for update in after_worker["updates"]] == [
        "source_unnormalized",
        "normalized",
    ]
    assert after_worker["answer"]["vehicle"]["vehicle_id"] == VEHICLE_A["vehicle_id"]
    assert len(calls["source"]) == 1
    assert len(calls["compose"]) == 1


def test_default_runtime_composes_source_articles_when_no_custom_composer_is_injected():
    source_articles = [
        {
            "article_id": "alternator-article",
            "title": "Alternator replacement",
            "component": "alternator",
            "operations": [
                {"operation_id": "battery-isolation", "action": "Disconnect battery", "duration_hours": 0.25},
                {"operation_id": "remove-alternator", "action": "Remove alternator", "duration_hours": 1.5},
            ],
        },
        {
            "article_id": "starter-article",
            "title": "Starter replacement",
            "component": "starter",
            "operations": [
                {"operation_id": "battery-isolation", "action": "Disconnect battery", "duration_hours": 0.25},
                {"operation_id": "remove-starter", "action": "Remove starter", "duration_hours": 2.5},
            ],
        },
    ]
    source = {
        "status": "source_unnormalized",
        "data_state": "source_unnormalized",
        "vehicle": dict(VEHICLE_A),
        "articles": source_articles,
        "normalization_pending": True,
    }
    configure_chat_runtime(
        dependencies=ChatDependencies(
            vehicle_candidates=lambda _message, _principal: (VEHICLE_A,),
            normalized_cache=lambda _query, _vehicle, _intent: None,
            source_retriever=lambda _query, _vehicle, _operations: source,
            normalizer=lambda _query, _vehicle, source_result: {
                "status": "ready",
                "articles": source_result["articles"],
            },
        ),
        repository=InMemoryChatRepository(),
        queue=InMemoryChatQueue(),
        event_store=ProgressEventStore(),
        allow_in_memory=True,
    )

    created = create_chat_query(
        "1997 Toyota RAV4 alternator and starter replacement procedure and quote",
        idempotency_key="chat-default-composer-1",
        principal=principal(),
    )
    process_chat_jobs()
    completed = get_chat_query(created["query_id"], principal=principal())

    assert completed["status"] == "available"
    assert completed["answer"]["data_state"] == "normalized"
    assert completed["answer"]["procedure"] is not None
    assert completed["answer"]["quote"] is not None


def test_invalid_selection_does_not_start_source_work():
    calls = install_runtime(candidates=lambda _message, _principal: (VEHICLE_A, VEHICLE_B))
    pending = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-selection-invalid",
        principal=principal(),
    )

    with pytest.raises(ValueError, match="vehicle option"):
        select_chat_vehicle(
            pending["query_id"],
            {"selection_type": "vehicle", "option_number": 3},
            principal=principal(),
        )

    assert calls["source"] == []


def test_http_dispatch_exposes_chat_json_and_replay_routes():
    install_runtime(candidates=lambda _message, _principal: (VEHICLE_A,))
    payload = {
        "message": "1997 Toyota RAV4 brake line replacement",
        "idempotency_key": "http-chat-1",
        "principal": principal(),
    }

    created = dispatch_request("/v1/chat/queries", payload)
    query_id = created["query_id"]
    selected = dispatch_request(
        f"/v1/chat/queries/{query_id}/selections",
        {"selection_type": "vehicle", "option_number": 1},
        principal=principal(),
    )
    fetched = dispatch_request(f"/v1/chat/queries/{query_id}", {}, principal=principal())
    events = dispatch_request(f"/v1/chat/queries/{query_id}/events", {}, principal=principal())
    replayed_events = dispatch_request(
        f"/v1/chat/queries/{query_id}/events?last_event_id={events['events'][0]['event_id']}",
        {},
        principal=principal(),
    )

    assert selected["query_id"] == query_id
    assert fetched["query_id"] == query_id
    assert events["query_id"] == query_id
    assert events["events"]
    assert replayed_events["events"] == events["events"][1:]


def test_worker_chat_entry_point_uses_the_same_idempotent_service():
    install_runtime(candidates=lambda _message, _principal: (VEHICLE_A,))
    from autodata_ingestion.worker import run_chat_query

    result = run_chat_query(
        '{"message":"1997 Toyota RAV4 brake line replacement",'
        '"idempotency_key":"worker-chat-1","principal":' + json.dumps(principal()) + '}'
    )

    assert result["query_id"]
    assert result["status"] in {"processing", "available"}


def test_unconfigured_chat_runtime_fails_closed_instead_of_using_process_local_state():
    configure_chat_runtime()

    with pytest.raises(ChatDurabilityError, match="durable chat runtime"):
        create_chat_query(
            "1997 Toyota RAV4 brake line replacement",
            idempotency_key="chat-no-runtime-1",
            principal=principal(),
        )
    with pytest.raises(ChatDurabilityError, match="in-memory chat adapters"):
        configure_chat_runtime(repository=InMemoryChatRepository(), event_store=ProgressEventStore())


def test_http_and_worker_can_share_an_explicit_runtime_boundary():
    calls = install_runtime(candidates=lambda _message, _principal: (VEHICLE_A,))
    from autodata_ingestion.worker import run_chat_worker_once

    runtime = ChatRuntime(
        repository=InMemoryChatRepository(),
        queue=InMemoryChatQueue(),
        event_store=ProgressEventStore(),
        durable=False,
    )
    configure_chat_runtime(
        dependencies=ChatDependencies(
            vehicle_candidates=lambda _message, _principal: (VEHICLE_A,),
            normalized_cache=lambda _query, _vehicle, _intent: None,
            source_retriever=lambda _query, vehicle, _operations: {
                "status": "source_unnormalized",
                "data_state": "source_unnormalized",
                "vehicle": dict(vehicle),
                "articles": [{"article_id": "raw-1"}],
            },
            normalizer=lambda _query, _vehicle, source_result: {
                "articles": source_result["articles"],
                "status": "ready",
            },
            composer=lambda _query, vehicle, _articles: {
                "status": "ready",
                "data_state": "normalized",
                "vehicle": dict(vehicle),
                "procedure": {"title": "service", "steps": []},
            },
        ),
        runtime=runtime,
        allow_in_memory=True,
    )

    created = dispatch_request(
        "/v1/chat/queries",
        {
            "message": "1997 Toyota RAV4 brake line replacement",
            "idempotency_key": "chat-shared-runtime-1",
            "principal": principal(),
        },
        chat_runtime=runtime,
    )
    worker_result = run_chat_worker_once(runtime=runtime)
    fetched = dispatch_request(
        f"/v1/chat/queries/{created['query_id']}",
        {},
        principal=principal(),
        chat_runtime=runtime,
    )

    assert worker_result["status"] == "completed"
    assert fetched["query_id"] == created["query_id"]
    assert fetched["answer"]["procedure"]["title"] == "service"
    assert calls["source"] == []


def test_worker_entry_point_drains_price_refresh_after_source_lane():
    refreshed = {"count": 0}
    install_runtime(
        candidates=lambda _message, _principal: (VEHICLE_A,),
        source=lambda _query, vehicle, _operations: {
            "status": "source_unnormalized",
            "data_state": "source_unnormalized",
            "vehicle": dict(vehicle),
            "articles": [{"article_id": "raw-source"}],
        },
        price=lambda _query, _vehicle, _answer: (
            refreshed.update(count=refreshed["count"] + 1)
            or {"status": "current", "data_state": "normalized"}
        ),
    )
    from autodata_ingestion.worker import run_chat_worker_once

    created = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-worker-price-lane-1",
        principal=principal(),
    )

    source_result = run_chat_worker_once()
    price_result = run_chat_worker_once()

    assert source_result["lane"] == "fast"
    assert price_result["lane"] == "price_refresh"
    assert price_result["status"] == "completed"
    assert price_result["query"]["query_id"] == created["query_id"]
    assert refreshed["count"] == 1


def test_idempotency_fingerprint_binds_owner_conversation_message_and_parameters():
    install_runtime(candidates=lambda _message, _principal: (VEHICLE_A,))
    owner_a = principal("owner-a", "org-a", "conversation-a")
    owner_b = principal("owner-b", "org-b", "conversation-b")
    create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-fingerprint-1",
        principal=owner_a,
        request_params={"include_prices": True},
    )

    with pytest.raises(ChatConflictError, match="idempotency key"):
        create_chat_query(
            "1997 Toyota RAV4 brake line inspection",
            idempotency_key="chat-fingerprint-1",
            principal=owner_a,
            request_params={"include_prices": True},
        )
    with pytest.raises(ChatConflictError, match="idempotency key"):
        create_chat_query(
            "1997 Toyota RAV4 brake line replacement",
            idempotency_key="chat-fingerprint-1",
            principal=owner_b,
            request_params={"include_prices": True},
        )

    query = get_chat_query(
        create_chat_query(
            "1997 Toyota RAV4 brake line replacement",
            idempotency_key="chat-fingerprint-2",
            principal=owner_a,
        )["query_id"],
        principal=owner_a,
    )
    with pytest.raises(PermissionError, match="owner"):
        get_chat_query(query["query_id"], principal=owner_b)
    with pytest.raises(PermissionError, match="owner"):
        list(iter_chat_events(query["query_id"], principal=owner_b))
    with pytest.raises(PermissionError, match="owner"):
        select_chat_vehicle(
            query["query_id"],
            {"selection_type": "vehicle", "option_number": 1},
            principal=owner_b,
        )


def test_repeated_selection_replays_after_options_are_cleared():
    calls = install_runtime(candidates=lambda _message, _principal: (VEHICLE_A, VEHICLE_B))
    owner = principal()
    pending = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-selection-replay-1",
        principal=owner,
    )
    first = select_chat_vehicle(
        pending["query_id"],
        {"selection_type": "vehicle", "option_number": 1},
        principal=owner,
    )
    second = select_chat_vehicle(
        pending["query_id"],
        {"selection_type": "vehicle", "option_number": 1},
        principal=owner,
    )

    assert first == second
    assert calls["source"] == []


def test_normalization_and_price_stages_are_explicit_and_pending_overrides_normalized():
    stages = []
    prices = []
    source_result = {
        "status": "source_unnormalized",
        "data_state": "source_unnormalized",
        "articles": [{"article_id": "raw-brake-line"}],
        "normalization_pending": True,
    }
    normalized_result = {
        "status": "ready",
        "data_state": "normalized",
        "procedure": {"title": "normalized", "steps": []},
    }
    install_runtime(
        candidates=lambda _message, _principal: (VEHICLE_A,),
        cache=lambda _query, _vehicle, _intent: {
            "cache_hit": True,
            "data_state": "normalized",
            "normalization_pending": True,
            "source_unnormalized": {"articles": [{"article_id": "cached-raw"}]},
            "vehicle": dict(VEHICLE_A),
        },
        source=lambda _query, _vehicle, _operations: source_result,
        normalize=lambda _query, _vehicle, _source: (stages.append("normalize") or {"articles": [{"article_id": "normalized-article"}], "status": "ready"}),
        compose=lambda _query, _vehicle, _articles: (stages.append("compose") or normalized_result),
        price=lambda _query, _vehicle, _normalized: (prices.append("price") or {"status": "current", "data_state": "normalized"}),
    )
    cached = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-pending-cache-1",
        principal=principal(),
    )
    assert cached["answer"]["data_state"] == "source_unnormalized"

    # A separate cache-miss query exercises source -> normalization -> price
    # queue -> composition in order.
    configure_chat_runtime(
        dependencies=ChatDependencies(
            vehicle_candidates=lambda _message, _principal: (VEHICLE_A,),
            normalized_cache=lambda _query, _vehicle, _intent: None,
            source_retriever=lambda _query, _vehicle, _operations: source_result,
            normalizer=lambda _query, _vehicle, _source: (stages.append("normalize") or {"articles": [{"article_id": "normalized-article"}], "status": "ready"}),
            price_refresher=lambda _query, _vehicle, _normalized: (prices.append("price") or {"status": "current", "data_state": "normalized"}),
            composer=lambda _query, _vehicle, _articles: (stages.append("compose") or normalized_result),
        ),
        repository=InMemoryChatRepository(),
        queue=InMemoryChatQueue(),
        event_store=ProgressEventStore(),
        allow_in_memory=True,
    )
    create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-explicit-stages-1",
        principal=principal(),
    )
    process_chat_jobs()

    assert stages[-2:] == ["normalize", "compose"]
    assert prices == []
    process_chat_price_jobs()
    assert prices == ["price"]


def test_reprocessing_a_claim_does_not_duplicate_answer_revision_or_event():
    calls = install_runtime(
        candidates=lambda _message, _principal: (VEHICLE_A,),
        source=lambda _query, vehicle, _operations: {
            "status": "source_unnormalized",
            "data_state": "source_unnormalized",
            "vehicle": dict(vehicle),
            "articles": [{"article_id": "raw-source"}],
        },
    )
    owner = principal()
    created = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-reprocess-1",
        principal=owner,
    )
    process_chat_jobs()
    stored = calls["repository"].get(created["query_id"])
    stored["job_plan"]["status"] = "pending"
    calls["repository"].save(stored)
    calls["repository"].enqueue(created["query_id"], kind="source")
    process_chat_jobs()
    result = get_chat_query(created["query_id"], principal=owner)

    assert len(result["updates"]) == 2
    answer_events = [event for event in result["answer"]["worker_stream"] if event["stage"] == "answer"]
    assert len(answer_events) == 2


def test_source_result_cannot_be_labeled_normalized_and_composer_failure_stays_retryable():
    compose_calls = []
    install_runtime(
        candidates=lambda _message, _principal: (VEHICLE_A,),
        source=lambda _query, _vehicle, _operations: {
            "status": "ready",
            "data_state": "normalized",
            "articles": [{"article_id": "raw-source"}],
        },
        compose=lambda _query, _vehicle, _articles: (compose_calls.append("failed") or {"status": "failed", "error": "unavailable"}),
    )
    created = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-composer-failure-1",
        principal=principal(),
    )
    process_chat_jobs()
    result = get_chat_query(created["query_id"], principal=principal())

    assert result["answer"]["data_state"] == "source_unnormalized"
    assert result["status"] == "processing"
    assert result["job_plan"]["status"] == "pending"
    assert result["job_plan"]["retry"]["retryable"] is True
    assert compose_calls == ["failed"]


def test_due_only_retry_queue_persists_backoff_and_dead_letters():
    attempts = []
    install_runtime(
        candidates=lambda _message, _principal: (VEHICLE_A,),
        source=lambda _query, _vehicle, _operations: (attempts.append("source") or (_ for _ in ()).throw(RuntimeError("temporary"))),
    )
    created = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-retry-schedule-1",
        principal=principal(),
    )
    process_chat_jobs()
    scheduled = get_chat_query(created["query_id"], principal=principal())
    next_attempt = scheduled["job_plan"]["next_attempt_at"]
    assert next_attempt
    assert process_chat_jobs() == []
    process_chat_jobs(now=next_attempt)
    scheduled = get_chat_query(created["query_id"], principal=principal())
    process_chat_jobs(now=scheduled["job_plan"]["next_attempt_at"])
    dead_letter = get_chat_query(created["query_id"], principal=principal())
    assert dead_letter["job_plan"]["status"] == "dead_letter"
    assert dead_letter["status"] == "failed"
    assert len(attempts) == 3


def test_price_refresh_retry_is_due_only_and_never_blocks_available_answer():
    attempts = []
    install_runtime(
        candidates=lambda _message, _principal: (VEHICLE_A,),
        source=lambda _query, vehicle, _operations: {
            "status": "source_unnormalized",
            "data_state": "source_unnormalized",
            "vehicle": dict(vehicle),
            "articles": [{"article_id": "raw-source"}],
        },
        price=lambda _query, _vehicle, _answer: (
            attempts.append("price") or (_ for _ in ()).throw(RuntimeError("price refresh unavailable"))
        ),
    )
    created = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-price-retry-1",
        principal=principal(),
    )
    process_chat_jobs()
    first = process_chat_price_jobs()[0]
    assert first["status"] == "available"
    assert first["job_plan"]["price_refresh"]["backoff_seconds"] == 1
    next_attempt = first["job_plan"]["price_refresh"]["next_attempt_at"]
    assert process_chat_price_jobs() == []
    second = process_chat_price_jobs(now=next_attempt)[0]
    next_attempt = second["job_plan"]["price_refresh"]["next_attempt_at"]
    dead_letter = process_chat_price_jobs(now=next_attempt)[0]

    assert dead_letter["status"] == "available"
    assert dead_letter["answer"]["data_state"] == "normalized"
    assert dead_letter["job_plan"]["price_refresh"]["status"] == "dead_letter"
    assert dead_letter["job_plan"]["price_refresh_pending"] is False
    assert attempts == ["price", "price", "price"]


def test_http_chat_get_auth_methods_errors_and_idempotency_header_conflicts():
    install_runtime(candidates=lambda _message, _principal: (VEHICLE_A,))
    owner = principal()
    created = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-http-auth-1",
        principal=owner,
    )
    from http.server import ThreadingHTTPServer

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler("internal-token"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def request(method, path, *, body=None, headers=None):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            data = response.read()
            connection.close()
            return response.status, response.getheader("Allow"), data

        status, _allow, _data = request("GET", f"/v1/chat/queries/{created['query_id']}")
        assert status == 401
        status, _allow, _data = request(
            "GET",
            f"/v1/chat/queries/{created['query_id']}",
            headers={"X-Autodata-Internal-Token": "internal-token"},
        )
        assert status == 403
        status, _allow, data = request(
            "GET",
            f"/v1/chat/queries/{created['query_id']}",
            headers={
                "X-Autodata-Internal-Token": "internal-token",
                "X-Autodata-Owner-Id": owner["owner_id"],
                "X-Autodata-Organization-Id": owner["organization_id"],
            },
        )
        assert status == 200
        assert json.loads(data)["query_id"] == created["query_id"]
        status, allow, _data = request(
            "PUT",
            f"/v1/chat/queries/{created['query_id']}",
            headers={"X-Autodata-Internal-Token": "internal-token"},
        )
        assert status == 405
        assert "GET" in (allow or "")
        status, allow, _data = request(
            "OPTIONS",
            f"/v1/chat/queries/{created['query_id']}",
            headers={"X-Autodata-Internal-Token": "internal-token"},
        )
        assert status == 204
        assert allow == "GET, OPTIONS"
        status, allow, _data = request(
            "POST",
            f"/v1/chat/queries/{created['query_id']}",
            body="{}",
            headers={
                "Content-Type": "application/json",
                "Content-Length": "2",
                "X-Autodata-Internal-Token": "internal-token",
            },
        )
        assert status == 405
        assert allow == "GET, OPTIONS"
        status, _allow, _data = request(
            "POST",
            "/v1/chat/queries",
            body=json.dumps({"message": ""}),
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(json.dumps({"message": ""}))),
                "X-Autodata-Internal-Token": "internal-token",
            },
        )
        assert status == 422
        body = {"message": "1997 Toyota RAV4 brake line replacement", "idempotency_key": "body-key", "principal": owner}
        status, _allow, _data = request(
            "POST",
            "/v1/chat/queries",
            body=json.dumps(body),
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(json.dumps(body))),
                "Idempotency-Key": "header-key",
                "X-Autodata-Internal-Token": "internal-token",
            },
        )
        assert status == 409
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
