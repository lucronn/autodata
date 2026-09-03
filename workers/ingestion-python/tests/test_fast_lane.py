import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.fast_lane import (  # noqa: E402
    FastLaneRequest,
    FastLaneRequestError,
    connector_for_request,
)


def event(payload):
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
        "payload": payload,
    }


class FastLaneRequestTests(unittest.TestCase):
    def test_directory_source_descriptor_selects_the_local_connector(self):
        request = FastLaneRequest.from_envelope(
            event(
                {
                    "vehicle_key": "toyota-corolla-2024-us",
                    "region": "US",
                    "source": {"kind": "directory", "location": "/sample-data", "version": "drop-v1"},
                }
            )
        )

        connector = connector_for_request(request)

        self.assertEqual(request.request_id, "request-1")
        self.assertEqual(request.processing_version, "fast-v1")
        self.assertEqual(connector.name, "local-directory")

    def test_http_source_descriptor_selects_the_http_connector(self):
        request = FastLaneRequest.from_envelope(
            event(
                {
                    "vehicle_key": "toyota-corolla-2024-us",
                    "region": "US",
                    "source": {"kind": "http", "location": "https://source.example/vehicle", "version": "v2"},
                    "processing_version": "fast-v2",
                }
            )
        )

        connector = connector_for_request(request)

        self.assertEqual(request.processing_version, "fast-v2")
        self.assertEqual(connector.name, "http")

    def test_request_rejects_missing_or_ambiguous_source_descriptor(self):
        base = {"vehicle_key": "toyota-corolla-2024-us", "region": "US"}
        for source in (None, {}, {"kind": "ftp", "location": "ftp://a", "version": "v1"}):
            with self.subTest(source=source), self.assertRaises(FastLaneRequestError):
                FastLaneRequest.from_envelope(event({**base, "source": source}))

    def test_request_rejects_wrong_version_and_embedded_source_credentials(self):
        with self.assertRaisesRegex(FastLaneRequestError, "event type"):
            FastLaneRequest.from_envelope({**event({}), "event_type": "dataset.deep.requested"})
        with self.assertRaisesRegex(FastLaneRequestError, "event version"):
            FastLaneRequest.from_envelope({**event({}), "event_version": 2})
        request = FastLaneRequest.from_envelope(
            event(
                {
                    "vehicle_key": "toyota-corolla-2024-us",
                    "region": "US",
                    "source": {"kind": "http", "location": "https://user:password@source.example/a", "version": "v1"},
                }
            )
        )
        with self.assertRaisesRegex(ValueError, "credentials"):
            connector_for_request(request)


if __name__ == "__main__":
    unittest.main()
