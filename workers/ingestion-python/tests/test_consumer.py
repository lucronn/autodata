import asyncio
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.consumer import consume_once, retry_delay_seconds  # noqa: E402


def valid_event():
    return {
        "event_id": "event-1",
        "event_type": "dataset.fast.requested",
        "event_version": 1,
        "occurred_at": "2026-09-03T12:00:00+00:00",
        "producer": "payment-reconciler",
        "request_id": "request-1",
        "projection_id": "projection-1",
        "revision_id": None,
        "correlation_id": "correlation-1",
        "idempotency_key": "fast-request-1",
        "payload": {
            "vehicle_key": "toyota-corolla-2024-us",
            "region": "US",
            "source": {"kind": "directory", "location": "/sample-data", "version": "drop-v1"},
        },
    }


class _Metadata:
    def __init__(self, deliveries):
        self.num_delivered = deliveries


class _Message:
    def __init__(self, data, deliveries=1):
        self.data = json.dumps(data).encode()
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
            raise asyncio.TimeoutError
        message, self.message = self.message, None
        return [message]


class _JetStream:
    def __init__(self, message):
        self.message = message
        self.published = []
        self.subscription = None

    async def stream_info(self, _stream):
        return {"name": "AUTODATA"}

    async def pull_subscribe(self, _subject, durable=None, stream=None):
        self.subscription = _Subscription(self.message)
        return self.subscription

    async def publish(self, subject, payload, headers=None):
        self.published.append((subject, json.loads(payload), headers))


class _Connection:
    def __init__(self, jetstream):
        self._jetstream = jetstream
        self.closed = False

    def jetstream(self):
        return self._jetstream

    async def close(self):
        self.closed = True


class ConsumerTests(unittest.TestCase):
    def run_consumer(self, message, handler, **kwargs):
        jetstream = _JetStream(message)
        connection = _Connection(jetstream)

        async def connect(_url):
            return connection

        result = asyncio.run(
            consume_once(
                handler,
                connect=connect,
                **kwargs,
            )
        )
        return result, jetstream, connection

    def test_successful_handler_acknowledges_the_message(self):
        message = _Message(valid_event())
        handled = []

        async def handler(request):
            handled.append(request.request_id)

        result, jetstream, connection = self.run_consumer(message, handler)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(handled, ["request-1"])
        self.assertTrue(message.acked)
        self.assertEqual(message.nak_delays, [])
        self.assertEqual(jetstream.published, [])
        self.assertTrue(connection.closed)

    def test_retryable_handler_failure_naks_with_bounded_backoff(self):
        message = _Message(valid_event(), deliveries=2)

        async def handler(_request):
            raise RuntimeError("temporary source failure")

        result, jetstream, _connection = self.run_consumer(message, handler, max_deliveries=3)

        self.assertEqual(result["status"], "retrying")
        self.assertEqual(result["delivery_count"], 2)
        self.assertEqual(message.nak_delays, [retry_delay_seconds(2)])
        self.assertFalse(message.acked)
        self.assertEqual(jetstream.published, [])

    def test_exhausted_handler_failure_is_dead_lettered_and_acked(self):
        message = _Message(valid_event(), deliveries=3)

        async def handler(_request):
            raise RuntimeError("temporary source failure")

        result, jetstream, _connection = self.run_consumer(message, handler, max_deliveries=3)

        self.assertEqual(result["status"], "dead_lettered")
        self.assertTrue(message.acked)
        self.assertEqual(len(jetstream.published), 1)
        subject, dead_letter, headers = jetstream.published[0]
        self.assertEqual(subject, "dataset.fast.dead_letter")
        self.assertEqual(headers, {"Nats-Msg-Id": "dead-letter:fast-request-1:3"})
        self.assertEqual(dead_letter["original_event"]["idempotency_key"], "fast-request-1")
        self.assertEqual(dead_letter["error_type"], "RuntimeError")

    def test_invalid_event_is_dead_lettered_without_retry(self):
        message = _Message({**valid_event(), "event_version": 2})

        async def handler(_request):
            self.fail("invalid event must not reach the handler")

        result, jetstream, _connection = self.run_consumer(message, handler)

        self.assertEqual(result["status"], "dead_lettered")
        self.assertTrue(message.acked)
        self.assertEqual(message.nak_delays, [])
        self.assertEqual(jetstream.published[0][1]["error_type"], "FastLaneRequestError")

    def test_empty_subscription_returns_idle(self):
        result, jetstream, connection = self.run_consumer(None, lambda _request: None)

        self.assertEqual(result, {"status": "idle", "received": 0})
        self.assertEqual(jetstream.published, [])
        self.assertTrue(connection.closed)

    def test_retry_backoff_is_positive_and_capped(self):
        self.assertEqual(retry_delay_seconds(1), 1)
        self.assertEqual(retry_delay_seconds(3), 4)
        self.assertEqual(retry_delay_seconds(99), 30)
        with self.assertRaises(ValueError):
            retry_delay_seconds(0)


if __name__ == "__main__":
    unittest.main()
