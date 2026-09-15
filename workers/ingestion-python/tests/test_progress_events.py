from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.progress_events import (  # noqa: E402
    ProgressEventStore,
    event_to_sse,
    publish_progress_event,
    record_chat_retry,
    register_query_context,
    reset_progress_events,
)


@pytest.fixture(autouse=True)
def clean_events():
    reset_progress_events()
    yield
    reset_progress_events()


def test_event_ids_and_idempotency_keys_are_deterministic_and_query_correlated():
    correlation_id = "8a3e8d8b-5f4c-4b4c-86be-7df22dbb0401"
    register_query_context("query-1", correlation_id=correlation_id)
    first = publish_progress_event(
        "query-1",
        "article_normalization",
        "completed",
        data_state="normalized",
        payload={"message": "article ready", "revision_id": "revision-1"},
    )
    replay = publish_progress_event(
        "query-1",
        "article_normalization",
        "completed",
        data_state="normalized",
        payload={"revision_id": "revision-1", "message": "article ready"},
    )

    assert replay == first
    assert first["query_id"] == "query-1"
    assert first["payload"]["query_id"] == "query-1"
    assert first["correlation_id"] == correlation_id
    assert first["event_id"]
    assert first["idempotency_key"]


def test_credential_like_values_are_redacted_from_message_and_payload():
    register_query_context("query-redact")
    event = publish_progress_event(
        "query-redact",
        "source_retrieval",
        "failed",
        data_state="unavailable",
        payload={
            "message": "Authorization: Bearer super-secret-token",
            "request_headers": {"X-Api-Key": "secret-api-key"},
            "nested": "password=hunter2 api_key=secret",
        },
    )

    serialized = str(event)
    assert "super-secret-token" not in serialized
    assert "secret-api-key" not in serialized
    assert "hunter2" not in serialized
    assert "[REDACTED_SECRET]" in serialized


def test_replay_starts_after_last_event_id_and_frames_are_sse_compatible():
    register_query_context("query-replay")
    first = publish_progress_event(
        "query-replay", "interpret", "completed", data_state="normalizing", payload={"message": "interpreted"}
    )
    second = publish_progress_event(
        "query-replay", "resolve_vehicle", "completed", data_state="normalizing", payload={"message": "resolved"}
    )

    store = ProgressEventStore.current()
    assert [event["event_id"] for event in store.iter_events("query-replay", last_event_id=first["event_id"])] == [
        second["event_id"]
    ]
    frame = event_to_sse(second)
    assert frame.startswith(f"id: {second['event_id']}\n")
    assert f"event: {second['event_type']}\n" in frame
    assert "data: {" in frame
    assert frame.endswith("\n\n")


def test_event_envelope_rejects_non_contract_state_and_owns_correlation_fields():
    store = ProgressEventStore()
    with pytest.raises(ValueError, match="unsupported data state"):
        store.publish(
            "query-contract",
            "answer",
            "completed",
            data_state="processing",
            payload={},
        )

    event = store.publish(
        "query-contract",
        "answer",
        "completed",
        data_state="normalizing",
        payload={"query_id": "another-query", "stage": "wrong"},
    )
    assert event["query_id"] == "query-contract"
    assert event["payload"]["query_id"] == "query-contract"
    assert event["payload"]["stage"] == "answer"


def test_stage_idempotency_ignores_timestamps_and_recursive_history():
    register_query_context("query-stage")
    first = publish_progress_event(
        "query-stage",
        "answer",
        "completed",
        data_state="source_unnormalized",
        payload={
            "message": "provisional",
            "answer": {
                "answer_status": "partial",
                "data_state": "source_unnormalized",
                "updated_at": "2026-09-11T00:00:00Z",
                "worker_stream": [{"event_id": "history-1"}],
                "source_uri": "https://source.test/raw",
            },
        },
    )
    replay = publish_progress_event(
        "query-stage",
        "answer",
        "completed",
        data_state="source_unnormalized",
        payload={
            "message": "provisional",
            "answer": {
                "answer_status": "partial",
                "data_state": "source_unnormalized",
                "updated_at": "2026-09-11T00:01:00Z",
                "worker_stream": [{"event_id": "history-2"}],
                "source_uri": "https://source.test/raw",
            },
        },
    )

    assert replay["event_id"] == first["event_id"]
    assert len(list(ProgressEventStore.current().iter_events("query-stage"))) == 1


def test_redaction_covers_url_userinfo_serialized_headers_and_query_secrets():
    event = publish_progress_event(
        "query-url-redact",
        "source_retrieval",
        "failed",
        data_state="unavailable",
        payload={
            "url": "https://user:secret-userinfo@source.test/path?api_key=secret-query&ok=1",
            "headers": '{"Authorization":"Bearer serialized-secret","X-Api-Key":"header-secret"}',
            "message": "request https://source.test/?token=secret-message",
        },
    )

    rendered = str(event)
    for secret in ("secret-userinfo", "secret-query", "serialized-secret", "header-secret", "secret-message"):
        assert secret not in rendered


def test_progress_retry_metadata_is_redacted_and_truncated():
    result = record_chat_retry(
        "query-error",
        "source_retrieval",
        RuntimeError("password=hidden " + "x" * 2000),
        max_attempts=2,
    )

    assert result["error"]["message"].startswith("password=[REDACTED_SECRET]")
    assert len(result["error"]["message"]) <= 512


def test_retries_are_bounded_and_exhaustion_publishes_dead_letter():
    register_query_context("query-retry")
    first = record_chat_retry(
        "query-retry", "procedure_composition", RuntimeError("provider password=hidden"), max_attempts=2
    )
    second = record_chat_retry(
        "query-retry", "procedure_composition", RuntimeError("provider password=hidden"), max_attempts=2
    )
    third = record_chat_retry(
        "query-retry", "procedure_composition", RuntimeError("provider password=hidden"), max_attempts=2
    )

    assert first["status"] == "retrying"
    assert first["attempt"] == 1
    assert second["status"] == "dead_letter"
    assert second["attempt"] == 2
    assert third == second
    events = list(ProgressEventStore.current().iter_events("query-retry"))
    assert events[-1]["status"] == "dead_letter"
    assert events[-1]["stage"] == "procedure_composition"
    assert "hidden" not in str(events[-1])
