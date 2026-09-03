import asyncio
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.knowledge_fallback import (
    KnowledgeFallbackFulfillmentHandler,
    PermanentKnowledgeFallbackError,
    ResolvedSource,
    RetryableKnowledgeFallbackError,
)
from autodata_ingestion.knowledge_fallback_consumer import (
    consume_once,
)

VEHICLE_KEY = "toyota-corolla-2024-us"


def event(*, query="brake connector", keywords=None, kind="article"):
    return {
        "event_id": "event-1",
        "event_type": "dataset.knowledge.fallback.requested",
        "event_version": 1,
        "occurred_at": "2026-09-03T12:00:00+00:00",
        "producer": "api",
        "request_id": "request-1",
        "projection_id": "projection-1",
        "revision_id": "revision-1",
        "correlation_id": "correlation-1",
        "idempotency_key": "knowledge-request-1",
        "payload": {
            "vehicle_key": VEHICLE_KEY,
            "region": "US",
            "query": query,
            "keywords": ["service"] if keywords is None else keywords,
            "kind": kind,
            "dataset_id": "dataset-1",
            "revision_id": "revision-1",
            "source_hint": {"provider": "test"},
        },
    }


def intake_for(vehicle_key=VEHICLE_KEY):
    vehicle = {
        "vehicle_key": vehicle_key,
        "make": "Toyota",
        "model": "Corolla",
        "model_year": 2024,
        "region": "US",
    }
    evidence = {
        "evidence_id": "evidence-1",
        "locator": "article.body",
        "source_uri": "provider://test/article-1",
        "source_version": "v1",
        "extracted_text": "Brake connector service bulletin",
        "confidence": 0.95,
    }
    bundle = SimpleNamespace(
        vehicle=vehicle,
        articles=(
            {
                "article_id": "article-1",
                "title": "Brake connector service bulletin",
                "body": "Inspect the brake connector.",
                "evidence_id": "evidence-1",
            },
        ),
        evidence=(evidence,),
    )
    return SimpleNamespace(
        status="ready",
        source_uri="provider://test/article-1",
        target=SimpleNamespace(vehicle_key=VEHICLE_KEY),
        artifacts=("artifact-1",),
        bundle=bundle,
        rejection_reason=None,
    )


class FakeResolver:
    def __init__(self, source=None, error=None):
        self.source = source or ResolvedSource("provider://test/article-1")
        self.error = error
        self.calls = []

    def resolve(self, target, query, keywords, source_hint=None):
        self.calls.append((target, query, keywords, source_hint))
        if self.error:
            raise self.error
        return self.source


class FakeIntake:
    def __init__(self, result=None, error=None):
        self.result = result or intake_for()
        self.error = error
        self.calls = []

    def __call__(self, source_uri, target, **options):
        self.calls.append((source_uri, target, options))
        if self.error:
            raise self.error
        return self.result


class FakePersistence:
    def __init__(self, result=None, error=None):
        self.result = result or {"status": "persisted", "revision_id": "revision-1"}
        self.error = error
        self.calls = []

    def __call__(self, bundle, artifacts, **options):
        self.calls.append((bundle, tuple(artifacts), options))
        if self.error:
            raise self.error
        return self.result


class _Metadata:
    def __init__(self, deliveries):
        self.num_delivered = deliveries


class _Message:
    def __init__(self, value, deliveries=1):
        self.data = json.dumps(value).encode()
        self.metadata = _Metadata(deliveries)
        self.acked = False
        self.nak_delays = []

    async def ack(self):
        self.acked = True

    async def nak(self, delay=None):
        self.nak_delays.append(delay)


class _Subscription:
    def __init__(self, message):
        self.message = message

    async def fetch(self, _batch, timeout):
        if self.message is None:
            raise TimeoutError
        message, self.message = self.message, None
        return [message]


class _JetStream:
    def __init__(self, message):
        self.message = message
        self.published = []

    async def stream_info(self, _stream):
        return {"name": "AUTODATA"}

    async def pull_subscribe(self, _subject, durable=None, stream=None):
        return _Subscription(self.message)

    async def publish(self, subject, payload, headers=None):
        self.published.append((subject, json.loads(payload), headers))


class _Connection:
    def __init__(self, jetstream):
        self._jetstream = jetstream

    def jetstream(self):
        return self._jetstream

    async def close(self):
        pass


class KnowledgeFallbackFulfillmentTests(unittest.TestCase):
    def make_handler(self, *, catalog=(), resolver=None, intake=None, persistence=None):
        return KnowledgeFallbackFulfillmentHandler(
            catalog=catalog,
            source_resolver=resolver or FakeResolver(),
            intake=intake or FakeIntake(),
            persistence=persistence,
        )

    def test_cache_miss_fetches_normalizes_persists_and_publishes_deterministically(self):
        resolver = FakeResolver()
        intake = FakeIntake()
        persistence = FakePersistence()
        result = self.make_handler(
            resolver=resolver, intake=intake, persistence=persistence
        ).handle(event())

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["dataset_id"], "dataset-1")
        self.assertEqual(result["revision_id"], "revision-1")
        self.assertEqual(result["result"]["status"], "fetched")
        self.assertEqual(result["publication"]["event_type"], "dataset.knowledge.fallback.fulfilled")
        self.assertEqual(len(resolver.calls), 1)
        self.assertEqual(resolver.calls[0][3], {"provider": "test"})
        self.assertEqual(len(intake.calls), 1)
        self.assertEqual(len(persistence.calls), 1)
        self.assertEqual(result["publication"]["evidence"], result["result"]["evidence"])

    def test_cache_hit_does_not_resolve_fetch_or_persist(self):
        catalog = [
            {
                "vehicle_key": VEHICLE_KEY,
                "kind": "article",
                "article": {"article_id": "article-1", "title": "Brake connector"},
                "evidence": [{"evidence_id": "catalog-evidence", "locator": "title", "confidence": 0.9}],
            }
        ]
        resolver = FakeResolver()
        intake = FakeIntake()
        persistence = FakePersistence()
        result = self.make_handler(
            catalog=catalog, resolver=resolver, intake=intake, persistence=persistence
        ).handle(event())

        self.assertEqual(result["result"]["status"], "cache_hit")
        self.assertEqual(resolver.calls, [])
        self.assertEqual(intake.calls, [])
        self.assertEqual(persistence.calls, [])

    def test_vehicle_mismatch_is_rejected_with_evidence_and_not_persisted(self):
        resolver = FakeResolver()
        intake = FakeIntake(result=intake_for("honda-civic-2024-us"))
        persistence = FakePersistence()
        result = self.make_handler(
            resolver=resolver, intake=intake, persistence=persistence
        ).handle(event())

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result"]["status"], "rejected")
        self.assertEqual(result["result"]["rejection_reason"], "vehicle_identity_mismatch")
        self.assertEqual(len(result["result"]["evidence"]), 1)
        self.assertEqual(persistence.calls, [])

    def test_duplicate_replay_returns_the_same_payload_and_runs_once(self):
        resolver = FakeResolver()
        intake = FakeIntake()
        persistence = FakePersistence()
        handler = self.make_handler(resolver=resolver, intake=intake, persistence=persistence)

        first = handler.handle(event())
        replay = handler.handle(event())

        self.assertEqual(first, replay)
        self.assertEqual(len(resolver.calls), 1)
        self.assertEqual(len(intake.calls), 1)
        self.assertEqual(len(persistence.calls), 1)

    def test_invalid_envelope_is_permanent(self):
        with self.assertRaises(PermanentKnowledgeFallbackError):
            self.make_handler().handle({**event(), "event_version": 2})

    def test_retryable_source_failure_is_classified_explicitly(self):
        resolver = FakeResolver(error=RetryableKnowledgeFallbackError("upstream timeout"))
        with self.assertRaises(RetryableKnowledgeFallbackError):
            self.make_handler(resolver=resolver).handle(event())

    def test_delivery_retries_transient_failure_and_dead_letters_after_bound(self):
        message = _Message(event(), deliveries=2)
        jetstream = _JetStream(message)
        connection = _Connection(jetstream)

        async def connect(_url):
            return connection

        async def handler(_request):
            raise RetryableKnowledgeFallbackError("temporary source failure")

        result = asyncio.run(
            consume_once(handler, connect=connect, max_deliveries=3)
        )
        self.assertEqual(result["status"], "retrying")
        self.assertEqual(message.nak_delays, [2])
        self.assertFalse(message.acked)

        message = _Message(event(), deliveries=3)
        jetstream = _JetStream(message)
        connection = _Connection(jetstream)

        async def connect_again(_url):
            return connection

        result = asyncio.run(
            consume_once(handler, connect=connect_again, max_deliveries=3)
        )
        self.assertEqual(result["status"], "dead_lettered")
        self.assertTrue(message.acked)
        self.assertEqual(jetstream.published[0][0], "dataset.knowledge.fallback.dead_letter")
        dead_letter = jetstream.published[0][1]
        self.assertEqual(dead_letter["original_event"]["idempotency_key"], "knowledge-request-1")
        self.assertEqual(dead_letter["error_type"], "RetryableKnowledgeFallbackError")


if __name__ == "__main__":
    unittest.main()
