from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.chat_service import (  # noqa: E402
    ChatDependencies,
    InMemoryChatRepository,
    configure_chat_runtime,
    create_chat_query,
    get_chat_query,
    process_chat_jobs,
    select_chat_vehicle,
)
from autodata_ingestion.http_service import dispatch_request  # noqa: E402
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


def install_runtime(*, candidates, cache=None, source=None, compose=None):
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

    repository = InMemoryChatRepository()
    configure_chat_runtime(
        dependencies=ChatDependencies(
            vehicle_candidates=candidates,
            normalized_cache=cache or (lambda _query, _vehicle, _intent: None),
            source_retriever=source_call,
            composer=compose_call,
        ),
        repository=repository,
        event_store=ProgressEventStore(),
    )
    return calls


@pytest.fixture(autouse=True)
def reset_runtime():
    yield
    configure_chat_runtime()


def test_query_creation_is_idempotent_and_exposes_numbered_clickable_options():
    calls = install_runtime(candidates=lambda _message, _principal: (VEHICLE_B, VEHICLE_A))

    first = create_chat_query(
        "1997 Toyota RAV4 brake line replacement procedure and quote",
        idempotency_key="chat-duplicate-1",
        principal={"organization_id": "org-1"},
    )
    replay = create_chat_query(
        "1997 Toyota RAV4 brake line replacement procedure and quote",
        idempotency_key="chat-duplicate-1",
        principal={"organization_id": "org-1"},
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
        principal={},
    )

    selected = select_chat_vehicle(
        pending["query_id"],
        {"selection_type": "vehicle", "option_number": "1"},
    )
    process_chat_jobs()
    completed = get_chat_query(pending["query_id"])

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
        principal={},
    )

    assert result["status"] == "available"
    assert result["answer"]["data_state"] == "normalized"
    assert result["answer"]["procedure"]["title"] == "Cached brake line service"
    assert calls["source"] == []
    assert calls["compose"] == []


def test_unambiguous_source_work_uses_the_canonical_candidate_identity():
    calls = install_runtime(candidates=lambda _message, _principal: (VEHICLE_A,))

    created = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-canonical-vehicle-1",
        principal={},
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
        principal={},
    )
    before_worker = get_chat_query(created["query_id"])
    process_chat_jobs()
    after_worker = get_chat_query(created["query_id"])

    assert before_worker["answer"]["answer_status"] == "processing"
    assert after_worker["answer"]["procedure"]["title"] == "Normalized brake line service"
    assert [update["data_state"] for update in after_worker["updates"]] == [
        "source_unnormalized",
        "normalized",
    ]
    assert after_worker["answer"]["vehicle"]["vehicle_id"] == VEHICLE_A["vehicle_id"]
    assert len(calls["source"]) == 1
    assert len(calls["compose"]) == 1


def test_invalid_selection_does_not_start_source_work():
    calls = install_runtime(candidates=lambda _message, _principal: (VEHICLE_A, VEHICLE_B))
    pending = create_chat_query(
        "1997 Toyota RAV4 brake line replacement",
        idempotency_key="chat-selection-invalid",
        principal={},
    )

    with pytest.raises(ValueError, match="vehicle option"):
        select_chat_vehicle(pending["query_id"], {"selection_type": "vehicle", "option_number": 3})

    assert calls["source"] == []


def test_http_dispatch_exposes_chat_json_and_replay_routes():
    install_runtime(candidates=lambda _message, _principal: (VEHICLE_A,))
    payload = {
        "message": "1997 Toyota RAV4 brake line replacement",
        "idempotency_key": "http-chat-1",
        "principal": {},
    }

    created = dispatch_request("/v1/chat/queries", payload)
    query_id = created["query_id"]
    selected = dispatch_request(
        f"/v1/chat/queries/{query_id}/selections",
        {"selection_type": "vehicle", "option_number": 1},
    )
    fetched = dispatch_request(f"/v1/chat/queries/{query_id}", {})
    events = dispatch_request(f"/v1/chat/queries/{query_id}/events", {})
    replayed_events = dispatch_request(
        f"/v1/chat/queries/{query_id}/events?last_event_id={events['events'][0]['event_id']}",
        {},
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
        '"idempotency_key":"worker-chat-1","principal":{}}'
    )

    assert result["query_id"]
    assert result["status"] in {"processing", "available"}
