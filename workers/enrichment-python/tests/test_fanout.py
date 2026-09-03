import unittest
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.fanout import (  # noqa: E402
    DEFAULT_DEEP_SECTIONS,
    ViewableEventError,
    deep_sections_from_event,
    normalize_deep_sections,
)


def event(payload=None):
    return {
        "event_id": "event-1",
        "producer": "ingestion-worker",
        "event_type": "dataset.viewable",
        "event_version": 1,
        "request_id": "request-1",
        "projection_id": "projection-1",
        "correlation_id": "correlation-1",
        "idempotency_key": "viewable-1",
        "payload": payload or {},
    }


class FanoutTests(unittest.TestCase):
    def test_missing_section_list_uses_the_stable_default_catalog(self):
        self.assertEqual(deep_sections_from_event(event()), DEFAULT_DEEP_SECTIONS)

    def test_explicit_sections_are_normalized_and_deduplicated(self):
        self.assertEqual(
            deep_sections_from_event(event({"deep_sections": ["Diagnostics", "procedures", "diagnostics"]})),
            ("diagnostics", "procedures"),
        )
        self.assertEqual(normalize_deep_sections(("quality", "quality")), ("quality",))

    def test_invalid_or_empty_section_lists_are_rejected(self):
        for payload in ({"deep_sections": "diagnostics"}, {"deep_sections": []}):
            with self.subTest(payload=payload), self.assertRaises(ViewableEventError):
                deep_sections_from_event(event(payload))

    def test_invalid_event_identity_is_rejected(self):
        with self.assertRaisesRegex(ViewableEventError, "projection_id"):
            deep_sections_from_event({**event(), "projection_id": ""})


if __name__ == "__main__":
    unittest.main()
