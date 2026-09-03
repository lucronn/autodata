import asyncio
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.deep_consumer import consume_once  # noqa: E402


def valid_event():
    return {
        "event_id": "event-1",
        "event_type": "dataset.deep.requested",
        "event_version": 1,
        "producer": "enrichment-worker",
        "request_id": "request-1",
        "projection_id": "projection-1",
        "revision_id": None,
        "correlation_id": "correlation-1",
        "idempotency_key": "deep-1",
        "payload": {
            "section": "diagnostics",
            "processing_version": "deep-v1",
            "source_snapshot_id": "snapshot-1",
        },
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


class DeepConsumerTests(unittest.TestCase):
    def run_consumer(self, message, handler, **kwargs):
        jetstream = JetStream(message)
        connection = Connection(jetstream)

        async def connect(_url):
            return connection

        result = asyncio.run(consume_once(handler, connect=connect, **kwargs))
        return result, jetstream, connection

    def test_successful_handler_acknowledges_deep_event(self):
        message = Message(valid_event())
        handled = []

        async def handler(request):
            handled.append(request.section_name)

        result, jetstream, connection = self.run_consumer(message, handler)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(handled, ["diagnostics"])
        self.assertTrue(message.acked)
        self.assertEqual(jetstream.published, [])
        self.assertTrue(connection.closed)

    def test_invalid_event_is_dead_lettered_without_retry(self):
        message = Message({**valid_event(), "event_version": 2})

        result, jetstream, _connection = self.run_consumer(message, lambda _request: self.fail())

        self.assertEqual(result["status"], "dead_lettered")
        self.assertTrue(message.acked)
        self.assertEqual(message.nak_delays, [])
        self.assertEqual(jetstream.published[0][0], "dataset.deep.dead_letter")
        self.assertEqual(jetstream.published[0][2], {"Nats-Msg-Id": "deep-dead-letter:deep-1:1"})

    def test_transient_handler_failure_uses_bounded_backoff(self):
        message = Message(valid_event(), deliveries=2)

        async def handler(_request):
            raise RuntimeError("temporary extractor failure")

        result, jetstream, _connection = self.run_consumer(message, handler)

        self.assertEqual(result["status"], "retrying")
        self.assertEqual(result["retry_delay_seconds"], 2)
        self.assertEqual(message.nak_delays, [2])
        self.assertFalse(message.acked)
        self.assertEqual(jetstream.published, [])


if __name__ == "__main__":
    unittest.main()
