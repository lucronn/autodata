import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.section_lifecycle import (  # noqa: E402
    DeepSectionValidationError,
    deep_job_idempotency_key,
    merge_revision_content,
    next_job_status,
    validate_evidence,
)


class SectionLifecycleTests(unittest.TestCase):
    def test_job_key_is_stable_and_scoped_to_source_request_lane_and_version(self):
        first = deep_job_idempotency_key("snapshot-1", "request-1", "diagnostics", "deep-v1")
        second = deep_job_idempotency_key("snapshot-1", "request-1", "diagnostics", "deep-v1")

        self.assertEqual(first, second)
        self.assertNotEqual(
            first,
            deep_job_idempotency_key("snapshot-1", "request-1", "procedures", "deep-v1"),
        )
        self.assertNotEqual(
            first,
            deep_job_idempotency_key("snapshot-1", "request-1", "diagnostics", "deep-v2"),
        )

    def test_section_merge_does_not_mutate_prior_revision_content(self):
        prior = {"vehicle_identity": {"make": "Toyota"}, "diagnostics": {"old": True}}

        merged = merge_revision_content(prior, "diagnostics", {"codes": ["P0300"]})

        self.assertEqual(prior["diagnostics"], {"old": True})
        self.assertEqual(merged["vehicle_identity"], {"make": "Toyota"})
        self.assertEqual(merged["diagnostics"], {"codes": ["P0300"]})

    def test_evidence_requires_locator_text_confidence_and_approved_state(self):
        approved = {
            "evidence_id": "evidence-1",
            "locator": "page=4",
            "extracted_text": "Diagnostic procedure",
            "confidence": 0.98,
            "reviewer_state": "approved",
        }

        self.assertIsNone(validate_evidence([approved]))
        with self.assertRaises(DeepSectionValidationError):
            validate_evidence([{**approved, "reviewer_state": "pending"}])
        with self.assertRaises(DeepSectionValidationError):
            validate_evidence([{**approved, "confidence": 1.2}])

    def test_failures_dead_letter_only_after_bounded_attempts(self):
        self.assertEqual(next_job_status(1, 3), "failed")
        self.assertEqual(next_job_status(2, 3), "failed")
        self.assertEqual(next_job_status(3, 3), "dead_letter")
        self.assertEqual(next_job_status(9, 3), "dead_letter")

    def test_duplicate_section_names_can_be_deduplicated_before_fanout(self):
        sections = tuple(dict.fromkeys(("diagnostics", "procedures", "diagnostics")))

        self.assertEqual(sections, ("diagnostics", "procedures"))


if __name__ == "__main__":
    unittest.main()
