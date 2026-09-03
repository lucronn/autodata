import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.deep_dispatch import (  # noqa: E402
    DeepRequest,
    DeepRequestError,
    dispatch_deep_request,
    parse_deep_request,
    register_section_processor,
)


def event(section="diagnostics"):
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
            "section": section,
            "processing_version": "deep-v1",
            "source_snapshot_id": "snapshot-1",
        },
    }


class DeepDispatchTests(unittest.TestCase):
    def test_parser_returns_provider_neutral_deep_request(self):
        request = parse_deep_request(event())

        self.assertEqual(
            request,
            DeepRequest(
                event_id="event-1",
                request_id="request-1",
                projection_id="projection-1",
                correlation_id="correlation-1",
                idempotency_key="deep-1",
                section_name="diagnostics",
                source_snapshot_id="snapshot-1",
                processing_version="deep-v1",
            ),
        )

    def test_registered_section_processor_receives_only_validated_identity(self):
        received = []
        register_section_processor("diagnostics", lambda request: received.append(request) or {"status": "accepted"})

        result = dispatch_deep_request(event())

        self.assertEqual(result, {"status": "accepted"})
        self.assertEqual(received[0].section_name, "diagnostics")
        self.assertEqual(received[0].source_snapshot_id, "snapshot-1")

    def test_unregistered_section_is_a_terminal_configuration_error(self):
        with self.assertRaisesRegex(DeepRequestError, "no processor"):
            dispatch_deep_request(event("procedures"))

    def test_invalid_event_is_rejected(self):
        for invalid in (
            {**event(), "event_type": "dataset.viewable"},
            {**event(), "event_version": 2},
            {**event(), "payload": {"section": ""}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(DeepRequestError):
                parse_deep_request(invalid)


if __name__ == "__main__":
    unittest.main()
