import sys
import unittest
from unittest.mock import patch
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.deep_dispatch import DeepRequest  # noqa: E402
from autodata_enrichment.quality_processor import (  # noqa: E402
    build_quality_report,
    process_quality_request,
)


class QualityProcessorTests(unittest.TestCase):
    def test_builds_deterministic_report_from_approved_evidence(self):
        report, evidence = build_quality_report(
            "snapshot-1",
            [
                {
                    "evidence_id": "evidence-c",
                    "locator": "page:3",
                    "artifact_key": "sources/b.pdf",
                    "extracted_text": "low confidence source",
                    "confidence": 0.2,
                    "reviewer_state": "approved",
                },
                {
                    "evidence_id": "evidence-a",
                    "locator": "body.vehicle",
                    "artifact_key": "sources/a.json",
                    "extracted_text": "vehicle identity",
                    "confidence": 1.0,
                    "reviewer_state": "approved",
                },
                {
                    "evidence_id": "evidence-b",
                    "locator": "page:2",
                    "artifact_key": "sources/b.pdf",
                    "extracted_text": "medium confidence source",
                    "confidence": 0.75,
                    "reviewer_state": "approved",
                },
            ],
        )

        self.assertEqual(report["report_type"], "approved-evidence-quality")
        self.assertEqual(report["source_snapshot_id"], "snapshot-1")
        self.assertEqual(report["evidence_count"], 3)
        self.assertEqual(report["artifact_count"], 2)
        self.assertEqual(
            report["confidence_distribution"], {"high": 1, "medium": 1, "low": 1}
        )
        self.assertEqual(report["source_evidence_ids"], ["evidence-a", "evidence-b", "evidence-c"])
        self.assertEqual([item["evidence_id"] for item in evidence], report["source_evidence_ids"])

    def test_rejects_unapproved_evidence(self):
        with self.assertRaisesRegex(ValueError, "approved"):
            build_quality_report(
                "snapshot-1",
                [
                    {
                        "evidence_id": "evidence-pending",
                        "locator": "page:1",
                        "artifact_key": "sources/a.pdf",
                        "extracted_text": "unreviewed source",
                        "confidence": 0.8,
                        "reviewer_state": "pending",
                    }
                ],
            )

    def test_publishes_quality_report_through_the_immutable_section_contract(self):
        request = DeepRequest(
            event_id="event-1",
            request_id="request-1",
            projection_id="projection-1",
            correlation_id="correlation-1",
            idempotency_key="deep-1",
            section_name="quality",
            source_snapshot_id="snapshot-1",
            processing_version="deep-v1",
        )
        source_evidence = [
            {
                "evidence_id": "evidence-a",
                "locator": "page:1",
                "artifact_key": "sources/a.pdf",
                "extracted_text": "approved source",
                "confidence": 1.0,
                "reviewer_state": "approved",
            }
        ]

        with patch(
            "autodata_enrichment.quality_processor.load_approved_source_evidence",
            return_value=source_evidence,
        ):
            with patch(
                "autodata_enrichment.quality_processor.publish_deep_section",
                return_value={"status": "published"},
            ) as publish:
                result = process_quality_request(request)

        self.assertEqual(result, {"status": "published"})
        job = publish.call_args.args[0]
        self.assertEqual(job.section_name, "quality")
        self.assertEqual(job.content["evidence_count"], 1)
        self.assertEqual(job.evidence, tuple(source_evidence))


if __name__ == "__main__":
    unittest.main()
