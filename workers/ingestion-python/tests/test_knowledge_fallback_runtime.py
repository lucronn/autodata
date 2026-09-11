import os
import sys
import types
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from autodata_ingestion.article_intake import VehicleTarget
from autodata_ingestion.knowledge_fallback_runtime import (
    ConfiguredKnowledgeSourceResolver,
    _expose_provisional_source_result,
    persist_price_snapshots,
    persist_source_payloads,
    queue_price_refresh,
    record_price_refresh_failure,
    _source_configuration,
)


class RefreshDatabase:
    def __init__(self):
        self.rows = {}
        self.events = []
        self.connections = []

    def connection(self):
        connection = RefreshConnection(self)
        self.connections.append(connection)
        return connection


class RefreshConnection:
    def __init__(self, database):
        self.database = database
        self.cursor_value = RefreshCursor(database)
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True


class RefreshCursor:
    def __init__(self, database):
        self.database = database
        self.result = None
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        if (
            "SELECT refresh_attempt_number, refresh_status," in query
            and "refresh_idempotency_key LIKE" in query
        ):
            snapshot_id, request_id, _pattern = params
            candidates = [
                (key, row)
                for key, row in self.database.rows.items()
                if row["snapshot_id"] == snapshot_id
                and (
                    key == request_id
                    or key.startswith(f"{request_id}:attempt:")
                )
            ]
            key, row = max(
                candidates, key=lambda item: item[1]["attempt"], default=(None, None)
            )
            self.result = (
                None
                if row is None
                else (row["attempt"], row["status"], key, row["failure"])
            )
        elif "COALESCE(MAX(refresh_attempt_number)" in query:
            snapshot_id = params[0]
            attempts = [
                row["attempt"]
                for row in self.database.rows.values()
                if row["snapshot_id"] == snapshot_id
            ]
            self.result = (max(attempts, default=0),)
        elif "INSERT INTO parts_price_snapshot_refreshes" in query:
            refresh_id, snapshot_id, attempt, key = params
            self.database.rows.setdefault(
                key,
                {
                    "refresh_id": refresh_id,
                    "snapshot_id": snapshot_id,
                    "attempt": attempt,
                    "status": "queued",
                    "failure": None,
                },
            )
            self.result = None
        elif "SELECT refresh_attempt_number, refresh_status" in query:
            row = self.database.rows.get(params[0])
            self.result = None if row is None else (row["attempt"], row["status"])
        elif "SELECT parts_price_snapshot_refresh_id::text" in query:
            row = self.database.rows.get(params[0])
            self.result = (
                None
                if row is None
                else (row["refresh_id"], row["attempt"], row["status"])
            )
        elif "UPDATE parts_price_snapshot_refreshes" in query:
            failure, refresh_id = params
            for row in self.database.rows.values():
                if row["refresh_id"] == refresh_id:
                    row["status"] = "failed"
                    row["failure"] = failure
        elif "INSERT INTO publication_events" in query:
            self.database.events.append(params)

    def fetchone(self):
        return self.result

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class KnowledgeFallbackRuntimeTests(unittest.TestCase):
    target = VehicleTarget("Toyota", "Corolla", 2024, "US")

    def test_explicit_source_hint_wins_over_template(self):
        with patch.dict(
            os.environ,
            {"AUTODATA_KNOWLEDGE_SOURCE_URL_TEMPLATE": "https://template.test/{vehicle_key}"},
            clear=False,
        ):
            uri, version = _source_configuration(
                self.target, "brake caliper", ("brake", "caliper"),
                {"source_uri": "https://source.test/article", "source_version": "v7"},
            )
        self.assertEqual(uri, "https://source.test/article")
        self.assertEqual(version, "v7")

    def test_template_receives_canonical_vehicle_and_query_values(self):
        with patch.dict(
            os.environ,
            {
                "AUTODATA_KNOWLEDGE_SOURCE_URL_TEMPLATE": (
                    "https://source.test/{region}/{vehicle_key}?q={query}&k={keywords}"
                ),
                "AUTODATA_KNOWLEDGE_SOURCE_VERSION": "catalog-v2",
            },
            clear=False,
        ):
            resolver = ConfiguredKnowledgeSourceResolver()
            source = resolver(self.target, "brake caliper", ("brake", "caliper"))
        self.assertEqual(
            source.source_uri,
            "https://source.test/US/toyota-corolla-2024-us?q=brake caliper&k=brake,caliper",
        )
        self.assertEqual(source.source_version, "catalog-v2")
        self.assertEqual(source.connector.name, "http")

    def test_missing_source_configuration_is_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(LookupError, "source_hint"):
                _source_configuration(self.target, "brake", ("brake",), None)

    def test_credentials_in_source_hint_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "credentials"):
            _source_configuration(
                self.target, "brake", ("brake",), "https://user:password@source.test/article"
            )

    def test_resolver_persists_source_resources_before_returning_them(self):
        from autodata_ingestion.source_adapters import SourceResource

        captured = []
        resolver = ConfiguredKnowledgeSourceResolver(
            source_persister=lambda resources: captured.extend(resources)
        )
        source = resolver(self.target, "brake", ("brake",), "https://source.test/article")
        resource = SourceResource.from_bytes(
            "https://source.test/article",
            "source-v1",
            b'{"body": {"documentId": "a1"}}',
            "application/json",
        )
        from autodata_ingestion import knowledge_fallback_runtime as runtime

        with patch.object(runtime.HttpSourceConnector, "fetch", return_value=[resource]) as fetch:
            returned = source.connector.fetch({"source_uri": source.source_uri})
            self.assertEqual(returned, [resource])
            fetch.assert_called_once()
        # The configured persister is attached to the connector boundary and
        # receives the exact immutable resources that will be normalized.
        self.assertEqual(captured, [resource])

    def test_production_resolver_routes_autoapi_requests_through_required_resource_helper(self):
        from autodata_ingestion import knowledge_fallback_runtime as runtime
        from autodata_ingestion.source_adapters import SourceResource

        resource = SourceResource.from_bytes(
            "http://autoapi.test/v1/api/source/Motor/vehicle/v1/article/a1",
            "autoapi-v1",
            b'{"header": {}, "body": {"documentId": "a1", "html": "<p>Brake</p>"}}',
            "application/json",
        )
        helper_result = {"source_resources": (resource,), "requested_article_ids": ("a1",)}
        resolver = ConfiguredKnowledgeSourceResolver()
        with patch.dict(
            os.environ,
            {
                "AUTODATA_KNOWLEDGE_SOURCE_PROVIDER": "autoapi",
                "AUTODATA_AUTOAPI_BASE_URL": "http://autoapi.test",
                "AUTODATA_AUTOAPI_CONTENT_SOURCE": "Motor",
            },
            clear=False,
        ), patch.object(
            runtime, "fetch_required_source_resources", return_value=helper_result
        ) as helper:
            source = resolver(
                self.target,
                "brake",
                ("brake",),
                {
                    "provider": "autoapi",
                    "vehicle_id": "v1",
                    "operations": [{"article_id": "a1"}],
                },
            )
            returned = source.connector.fetch({"source_uri": source.source_uri})

        self.assertEqual(returned, [resource])
        helper.assert_called_once()
        self.assertEqual(helper.call_args.args[0]["vehicle_id"], "v1")
        self.assertEqual(helper.call_args.args[1], ({"article_id": "a1"},))

    def test_raw_source_is_retained_before_adaptation_failure(self):
        from autodata_ingestion import bundle_persistence, source_adapters
        from autodata_ingestion.source_adapters import SourceResource

        resource = SourceResource.from_bytes(
            "https://source.test/bad.json",
            "source-v1",
            b'{"invalid":',
            "application/json",
        )
        events = []
        fake_cursor = type(
            "Cursor",
            (),
            {
                "execute": lambda self, query, params: events.append(
                    ("execute", query, params)
                ),
                "__enter__": lambda self: self,
                "__exit__": lambda self, *_args: False,
            },
        )()
        fake_connection = type(
            "Connection",
            (),
            {
                "__enter__": lambda self: self,
                "__exit__": lambda self, *_args: False,
                "cursor": lambda self: fake_cursor,
                "commit": lambda self: events.append(("commit",)),
            },
        )()
        fake_json = types.ModuleType("psycopg.types.json")
        fake_json.Jsonb = lambda value: value
        fake_types = types.ModuleType("psycopg.types")
        fake_types.json = fake_json
        fake_psycopg = types.ModuleType("psycopg")
        fake_psycopg.connect = lambda **_kwargs: fake_connection

        def store(_artifacts):
            events.append(("store",))

        def adapt(_resource):
            events.append(("adapt",))
            raise ValueError("malformed source")

        with patch.dict(
            sys.modules,
            {
                "psycopg": fake_psycopg,
                "psycopg.types": fake_types,
                "psycopg.types.json": fake_json,
            },
        ), patch.dict(os.environ, {"AUTODATA_POSTGRES_PASSWORD": "test-only"}), patch.object(
            bundle_persistence, "store_source_artifacts", side_effect=store
        ), patch.object(
            bundle_persistence,
            "_persist_snapshots",
            side_effect=lambda *_args: {resource.content_sha256: "snapshot-1"},
        ), patch.object(source_adapters, "adapt_source_resource", side_effect=adapt):
            result = persist_source_payloads([resource])

        self.assertEqual(result["status"], "source_unnormalized")
        self.assertLess(
            next(index for index, event in enumerate(events) if event[0] == "store"),
            next(index for index, event in enumerate(events) if event[0] == "adapt"),
        )
        reference = result["source_references"][0]
        self.assertEqual(reference["source_snapshot_id"], "snapshot-1")
        self.assertIn("source_artifact_id", reference)
        self.assertIn("object_key", reference)

    def test_provisional_source_result_contains_safe_source_references(self):
        references = [
            {
                "source_uri": "https://source.test/article",
                "source_version": "source-v1",
                "content_sha256": "a" * 64,
                "source_snapshot_id": "snapshot-1",
                "source_artifact_id": "artifact-1",
                "object_key": "sources/a/a",
            }
        ]
        result = _expose_provisional_source_result(
            {
                "result": {
                    "status": "rejected",
                    "source_uri": references[0]["source_uri"],
                    "evidence": (),
                    "rejection_reason": "article_not_ready",
                }
            },
            references,
        )

        self.assertEqual(
            result["result"]["source_unnormalized"]["source_references"],
            references,
        )
        self.assertEqual(result["result"]["source_references"], references)

    def test_refresh_attempts_advance_and_dead_letter_without_deleting_snapshot(self):
        from autodata_ingestion.pricing import read_cached_price_or_queue_refresh

        database = RefreshDatabase()
        fake_json = types.ModuleType("psycopg.types.json")
        fake_json.Jsonb = lambda value: value
        fake_types = types.ModuleType("psycopg.types")
        fake_types.json = fake_json
        fake_psycopg = types.ModuleType("psycopg")
        fake_psycopg.connect = lambda **_kwargs: database.connection()
        part = {
            "parts_price_snapshot_id": "snapshot-1",
            "canonical_part_id": "part:p1",
            "source_part_number": "P1",
            "source_snapshot_id": "snapshot-source",
            "priced_at": "2026-08-01T12:00:00Z",
            "amount": 18.99,
            "currency": "USD",
        }
        with patch.dict(
            sys.modules,
            {
                "psycopg": fake_psycopg,
                "psycopg.types": fake_types,
                "psycopg.types.json": fake_json,
            },
        ), patch.dict(os.environ, {"AUTODATA_POSTGRES_PASSWORD": "test-only"}):
            first_snapshot = read_cached_price_or_queue_refresh(
                part,
                now=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
                refresh=queue_price_refresh,
            )
            attempt_one = first_snapshot
            failure_one = record_price_refresh_failure(
                attempt_one["refresh_idempotency_key"], TimeoutError("source unavailable")
            )
            attempt_two = queue_price_refresh(
                {**part, "refresh_idempotency_key": attempt_one["refresh_idempotency_key"]}
            )
            record_price_refresh_failure(
                attempt_two["refresh_idempotency_key"], TimeoutError("source unavailable")
            )
            attempt_three = queue_price_refresh(
                {**part, "refresh_idempotency_key": attempt_two["refresh_idempotency_key"]}
            )
            dead_letter = record_price_refresh_failure(
                attempt_three["refresh_idempotency_key"], TimeoutError("source unavailable")
            )
            repeated = queue_price_refresh(
                {**part, "refresh_idempotency_key": attempt_three["refresh_idempotency_key"]}
            )

        self.assertEqual(attempt_one["refresh_attempt_number"], 1)
        self.assertEqual(failure_one["status"], "failed")
        self.assertEqual(attempt_two["refresh_attempt_number"], 2)
        self.assertEqual(attempt_three["refresh_attempt_number"], 3)
        self.assertEqual(dead_letter["status"], "dead_letter")
        self.assertFalse(dead_letter["retryable"])
        self.assertEqual(repeated["status"], "dead_letter")
        self.assertEqual(len(database.rows), 3)
        self.assertEqual(len(database.events), 1)
        self.assertTrue(all(row["snapshot_id"] == "snapshot-1" for row in database.rows.values()))

    def test_price_snapshots_persist_through_immutable_migration_keys(self):
        from autodata_ingestion import bundle_persistence

        calls = []
        fake_cursor = type(
            "Cursor",
            (),
            {
                "execute": lambda self, query, params: calls.append((query, params)),
                "__enter__": lambda self: self,
                "__exit__": lambda self, *_args: False,
            },
        )()
        fake_connection = type(
            "Connection",
            (),
            {
                "__enter__": lambda self: self,
                "__exit__": lambda self, *_args: False,
                "cursor": lambda self: fake_cursor,
                "commit": lambda self: calls.append(("commit",)),
            },
        )()
        fake_json = types.ModuleType("psycopg.types.json")
        fake_json.Jsonb = lambda value: value
        fake_types = types.ModuleType("psycopg.types")
        fake_types.json = fake_json
        fake_psycopg = types.ModuleType("psycopg")
        fake_psycopg.connect = lambda **_kwargs: fake_connection
        part = {
            "parts_price_snapshot_id": "price-snapshot-1",
            "canonical_part_id": "part:p1",
            "source_part_number": "P1",
            "source_snapshot_id": "source-snapshot-1",
            "amount": 18.99,
            "currency": "USD",
            "priced_at": "2026-09-01T12:00:00Z",
            "freshness": "fresh",
            "refresh_status": "current",
            "markup_applied": False,
        }

        with patch.dict(
            sys.modules,
            {
                "psycopg": fake_psycopg,
                "psycopg.types": fake_types,
                "psycopg.types.json": fake_json,
            },
        ), patch.dict(os.environ, {"AUTODATA_POSTGRES_PASSWORD": "test-only"}):
            result = persist_price_snapshots([part])

        self.assertEqual(result["status"], "persisted")
        self.assertEqual(result["price_snapshot_ids"], ("price-snapshot-1",))
        insert = next(query for query, _params in calls if "INSERT INTO parts_price_snapshots" in query)
        self.assertIn("ON CONFLICT (canonical_part_id, source_snapshot_id, priced_at)", insert)

    def test_fulfillment_exposes_source_unnormalized_when_normalization_is_pending(self):
        from autodata_ingestion import knowledge_fallback_runtime as runtime

        envelope = {
            "event_type": "dataset.knowledge.fallback.requested",
            "event_version": 1,
            "event_id": "event-1",
            "occurred_at": "2026-09-11T12:00:00Z",
            "producer": "test",
            "request_id": "request-1",
            "projection_id": "projection-1",
            "revision_id": "revision-1",
            "correlation_id": "correlation-1",
            "idempotency_key": "fallback-1",
            "payload": {
                "vehicle_key": "toyota-corolla-2024-us",
                "region": "US",
                "query": "brake",
                "keywords": ["brake"],
                "kind": "article",
                "dataset_id": "dataset-1",
                "revision_id": "revision-1",
            },
        }
        fulfillment = {
            "status": "completed",
            "result": {
                "status": "rejected",
                "idempotency_key": "fallback-1",
                "vehicle": self.target.as_dict(),
                "query": "brake",
                "keywords": ("brake",),
                "results": (),
                "evidence": ({"evidence_id": "evidence-1"},),
                "source_uri": "https://source.test/article",
                "rejection_reason": "article_not_ready",
            },
        }
        fake_handler = type("FakeHandler", (), {"handle": lambda self, _envelope: fulfillment})()
        with patch.object(runtime, "load_revision_catalog", return_value={}), patch.object(
            runtime, "KnowledgeFallbackFulfillmentHandler", return_value=fake_handler
        ):
            result = runtime.fulfill_once(envelope)

        self.assertEqual(result["result"]["status"], "source_unnormalized")
        self.assertEqual(result["result"]["data_state"], "source_unnormalized")
        self.assertEqual(result["result"]["source_uri"], "https://source.test/article")


if __name__ == "__main__":
    unittest.main()
