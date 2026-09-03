import asyncio
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.viewable_consumer import consume_once  # noqa: E402


def valid_event():
    return {
        "event_id": "event-1",
        "event_type": "dataset.viewable",
        "event_version": 1,
        "occurred_at": "2026-09-03T12:00:00+00:00",
        "producer": "ingestion-worker",
        "request_id": "request-1",
        "projection_id": "projection-1",
        "revision_id": "revision-1",
        "correlation_id": "correlation-1",
        "idempotency_key": "viewable-1",
        "payload": {"deep_sections": ["diagnostics"]},
    }


class Metadata:
    def __init__(self, deliveries):
        self.num_delivered = deliveries


class Message:
    def __init__(self, data, deliveries=1):
        self.data = json.dumps(data).encode()
        self.metadata = Metadata(deliveries)
        self.acked = False
        self.nak_delays = []

    async def ack(self):
        self.acked = True

    async def nak(self, delay=None):
        self.nak_delays.append(delay)


class Subscription:
    def __init__(self, message):
        self.message = message

    async def fetch(self, _batch, timeout):
        if self.message is None:
            raise asyncio.TimeoutError
        message, self.message = self.message, None
        return [message]


class JetStream:
    def __init__(self, message):
        self.message = message
        self.published = []

    async def stream_info(self, _stream):
        return {"name": "AUTODATA"}

    async def pull_subscribe(self, _subject, durable=None, stream=None):
        return Subscription(self.message)

    async def publish(self, subject, payload, headers=None):
        self.published.append((subject, json.loads(payload), headers))


class Connection:
    def __init__(self, jetstream):
        self._jetstream = jetstream
        self.closed = False

    def jetstream(self):
        return self._jetstream

    async def close(self):
        self.closed = True


class ViewableConsumerTests(unittest.TestCase):
    def run_consumer(self, message, handler, **kwargs):
        jetstream = JetStream(message)
        connection = Connection(jetstream)

        async def connect(_url):
            return connection

        result = asyncio.run(consume_once(handler, connect=connect, **kwargs))
        return result, jetstream, connection

    def test_successful_fanout_handler_acknowledges_event(self):
        message = Message(valid_event())
        handled = []

        async def handler(envelope):
            handled.append(envelope["projection_id"])

        result, jetstream, connection = self.run_consumer(message, handler)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(handled, ["projection-1"])
        self.assertTrue(message.acked)
        self.assertEqual(jetstream.published, [])
        self.assertTrue(connection.closed)

    def test_invalid_event_is_dead_lettered_without_retry(self):
        message = Message({**valid_event(), "event_version": 2})

        result, jetstream, _connection = self.run_consumer(message, lambda _event: self.fail())

        self.assertEqual(result["status"], "dead_lettered")
        self.assertTrue(message.acked)
        self.assertEqual(message.nak_delays, [])
        self.assertEqual(jetstream.published[0][0], "dataset.deep.schedule.dead_letter")
        self.assertEqual(jetstream.published[0][2], {"Nats-Msg-Id": "viewable-dead-letter:viewable-1:1"})

    def test_transient_failure_uses_bounded_nak_backoff(self):
        message = Message(valid_event(), deliveries=2)

        async def handler(_event):
            raise RuntimeError("temporary database failure")

        result, jetstream, _connection = self.run_consumer(message, handler)

        self.assertEqual(result["status"], "retrying")
        self.assertEqual(result["retry_delay_seconds"], 2)
        self.assertEqual(message.nak_delays, [2])
        self.assertFalse(message.acked)
        self.assertEqual(jetstream.published, [])


if __name__ == "__main__":
    unittest.main()
