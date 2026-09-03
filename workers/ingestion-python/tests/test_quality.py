import dataclasses
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.quality import evaluate_source_bundle  # noqa: E402
from autodata_ingestion.source_adapters import SourceResource, adapt_source_resource  # noqa: E402
from autodata_ingestion.source_bundle import normalize_source_bundle  # noqa: E402


def ready_bundle():
    resources = [
        SourceResource.from_bytes(
            "provider://vehicle/name",
            "source-v1",
            b'{"body":"2019 Cadillac Escalade ESV - 2WD"}',
            "application/json",
        ),
    ]
    return normalize_source_bundle([adapt_source_resource(resource) for resource in resources], "US")


class QualityTests(unittest.TestCase):
    def test_ready_bundle_is_traceable_even_before_review_approval(self):
        report = evaluate_source_bundle(ready_bundle())

        self.assertEqual(report.status, "needs_review")
        self.assertEqual(report.evidence_coverage, 1.0)
        self.assertTrue(any(item.code == "review_required" for item in report.findings))

    def test_missing_evidence_is_a_blocking_quality_failure(self):
        bundle = ready_bundle()
        bundle = dataclasses.replace(bundle, evidence=())

        report = evaluate_source_bundle(bundle)

        self.assertEqual(report.status, "failed")
        self.assertEqual(report.evidence_coverage, 0.0)
        self.assertTrue(any(item.code == "missing_evidence" for item in report.findings))

    def test_quarantine_is_reviewable_without_being_silently_accepted(self):
        bundle = ready_bundle()
        report = evaluate_source_bundle(
            dataclasses.replace(bundle, quarantined=({"reason": "source_terms_unknown"},))
        )

        self.assertEqual(report.status, "needs_review")
        self.assertTrue(any(item.code == "quarantined_input" for item in report.findings))


if __name__ == "__main__":
    unittest.main()
