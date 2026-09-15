from __future__ import annotations

import json
import os
from typing import Any

import pytest

from autodata_ingestion.chat_service import (
    ChatRuntime,
    configure_chat_runtime_from_environment,
)
from autodata_ingestion.chat_durable_runtime import (
    PostgresChatQueue,
    PostgresChatRepository,
    PostgresProgressEventStore,
    build_postgres_chat_runtime,
)


class RecordingCursor:
    def __init__(self, *, fetchone_values=(), fetchall_values=()):
        self.statements: list[tuple[str, tuple[Any, ...]]] = []
        self._fetchone_values = list(fetchone_values)
        self._fetchall_values = list(fetchall_values)

    def execute(self, statement: str, parameters=()):
        self.statements.append((statement, tuple(parameters)))

    def fetchone(self):
        return self._fetchone_values.pop(0) if self._fetchone_values else None

    def fetchall(self):
        return self._fetchall_values.pop(0) if self._fetchall_values else []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class RecordingConnection:
    def __init__(self, cursor: RecordingCursor):
        self.cursor_value = cursor
        self.commits = 0

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_repository_redacts_and_round_trips_the_full_query_snapshot():
    cursor = RecordingCursor(fetchone_values=[("query-1", "fp-1"), ({"status": "processing"},)])
    connection = RecordingConnection(cursor)
    repository = PostgresChatRepository(open_connection=lambda: connection)
    query = {
        "query_id": "query-1",
        "idempotency_key": "idem-1",
        "request_fingerprint": "fp-1",
        "owner_id": "owner-1",
        "organization_id": "org-1",
        "answer": {"status": "processing"},
        "credential": "must-not-persist",
    }

    repository.save(query)
    result = repository.get("query-1")

    assert result == {"status": "processing"}
    save_sql, save_args = cursor.statements[0]
    assert "ON CONFLICT (idempotency_key)" in save_sql
    assert "must-not-persist" not in json.dumps(save_args, default=str)


def test_queue_claim_uses_skip_locked_leases_and_ack_preserves_requeued_work():
    cursor = RecordingCursor(fetchall_values=[[('query-1', 'source', 'lease-token', "2026-09-11T00:01:00+00:00")]])
    connection = RecordingConnection(cursor)
    queue = PostgresChatQueue(open_connection=lambda: connection, lease_seconds=30)

    queue.enqueue("query-1", kind="source", available_at="2026-09-11T00:00:00Z")
    claimed = queue.claim_due(kind="source", limit=1, now="2026-09-11T00:00:01Z")
    queue.ack(claimed[0])

    assert claimed[0].query_id == "query-1"
    statements = [statement for statement, _args in cursor.statements]
    assert any("FOR UPDATE SKIP LOCKED" in statement for statement in statements)
    assert any("lease_expires_at" in statement for statement in statements)
    assert any("lease_token = %s" in statement for statement in statements)


def test_progress_store_persists_redacted_idempotent_events_and_context():
    context_row = (
        "10000000-0000-0000-0000-000000000001",
        "10000000-0000-0000-0000-000000000002",
        "10000000-0000-0000-0000-000000000003",
        "owner-1",
        "org-1",
    )
    event_row = {
        "query_id": "query-1",
        "correlation_id": context_row[0],
        "payload": {"api_key": "[REDACTED_SECRET]"},
    }
    cursor = RecordingCursor(fetchone_values=[context_row, context_row, None, (event_row,)])
    connection = RecordingConnection(cursor)
    store = PostgresProgressEventStore(open_connection=lambda: connection)

    store.register_context(
        "query-1",
        correlation_id="correlation-1",
        request_id="request-1",
        projection_id="projection-1",
        owner_id="owner-1",
        organization_id="org-1",
    )
    event = store.publish(
        "query-1",
        "source_retrieval",
        "completed",
        data_state="source_unnormalized",
        payload={"message": "source ready", "api_key": "do-not-persist"},
        idempotency_key="source:completed",
    )

    assert event["query_id"] == "query-1"
    assert event["correlation_id"]
    assert event["payload"]["api_key"] == "[REDACTED_SECRET]"
    assert any("ON CONFLICT (idempotency_key) DO NOTHING" in statement for statement, _args in cursor.statements)
    assert "do-not-persist" not in json.dumps(cursor.statements, default=str)


def test_factory_only_builds_postgres_runtime_when_explicitly_selected(monkeypatch):
    monkeypatch.setenv("AUTODATA_CHAT_RUNTIME_BACKEND", "postgres")
    monkeypatch.setenv("AUTODATA_POSTGRES_PASSWORD", "local-only")

    runtime = build_postgres_chat_runtime(connect_factory=lambda: RecordingConnection(RecordingCursor()))

    assert isinstance(runtime, ChatRuntime)
    assert runtime.durable is True
    runtime.validate()


def test_environment_without_backend_remains_fail_closed(monkeypatch):
    monkeypatch.delenv("AUTODATA_CHAT_RUNTIME_BACKEND", raising=False)
    monkeypatch.delenv("AUTODATA_CHAT_RUNTIME_FACTORY", raising=False)
    monkeypatch.delenv("AUTODATA_CHAT_ALLOW_IN_MEMORY", raising=False)

    runtime = configure_chat_runtime_from_environment()

    assert runtime.durable is False
