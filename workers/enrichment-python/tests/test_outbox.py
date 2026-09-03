import asyncio
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.outbox import (  # noqa: E402
    OutboxEvent,
    build_event_envelope,
    delivery_status_after_failure,
    event_subject,
    publish_event,
)


class _FakeJetStream:
    def __init__(self):
        self.calls = []

    async def publish(self, subject, payload, headers=None):
        self.calls.append((subject, payload, headers))
        return {"stream": "AUTODATA", "seq": len(self.calls)}


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.event = OutboxEvent(
            publication_event_id="event-1",
            event_type="dataset.section.published",
            event_version=1,
            request_id="request-1",
            projection_id="projection-1",
            revision_id="revision-1",
            correlation_id="correlation-1",
            idempotency_key="deep-job-1",
            payload={"section": "diagnostics"},
            occurred_at=datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
            producer="enrichment-worker",
        )

    def test_event_type_maps_only_to_a_versioned_dataset_subject(self):
        self.assertEqual(event_subject(self.event), "dataset.section.published")
        with self.assertRaises(ValueError):
            event_subject(OutboxEvent(**{**self.event.__dict__, "event_type": "internal.secret"}))

    def test_envelope_preserves_database_identity_and_normalizes_timestamp(self):
        self.assertEqual(
            build_event_envelope(self.event),
            {
                "event_id": "event-1",
                "event_type": "dataset.section.published",
                "event_version": 1,
                "occurred_at": "2026-09-03T12:00:00+00:00",
                "producer": "enrichment-worker",
                "request_id": "request-1",
                "projection_id": "projection-1",
                "revision_id": "revision-1",
                "correlation_id": "correlation-1",
                "idempotency_key": "deep-job-1",
                "payload": {"section": "diagnostics"},
            },
        )

    def test_publish_uses_idempotency_key_as_nats_message_id(self):
        jetstream = _FakeJetStream()

        asyncio.run(publish_event(self.event, jetstream))

        self.assertEqual(len(jetstream.calls), 1)
        subject, payload, headers = jetstream.calls[0]
        self.assertEqual(subject, "dataset.section.published")
        self.assertEqual(headers, {"Nats-Msg-Id": "deep-job-1"})
        self.assertIn('"event_id": "event-1"', payload.decode())

    def test_delivery_failures_become_dead_letter_only_at_attempt_limit(self):
        self.assertEqual(delivery_status_after_failure(1, 3), "failed")
        self.assertEqual(delivery_status_after_failure(2, 3), "failed")
        self.assertEqual(delivery_status_after_failure(3, 3), "dead_letter")

    def test_envelope_rejects_missing_required_database_identity(self):
        with self.assertRaisesRegex(ValueError, "request_id"):
            build_event_envelope(OutboxEvent(**{**self.event.__dict__, "request_id": ""}))


if __name__ == "__main__":
    unittest.main()
