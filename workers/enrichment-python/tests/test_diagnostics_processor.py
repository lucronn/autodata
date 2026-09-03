import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.deep_dispatch import DeepRequest  # noqa: E402
from autodata_enrichment.diagnostics_processor import (  # noqa: E402
    DiagnosticsProcessorError,
    build_diagnostics_section,
    process_diagnostics_request,
)


def evidence(evidence_id, locator, text, confidence=0.9, reviewer_state="approved"):
    return {
        "evidence_id": evidence_id,
        "locator": locator,
        "artifact_key": f"sources/{evidence_id}.pdf",
        "extracted_text": text,
        "confidence": confidence,
        "reviewer_state": reviewer_state,
    }


class DiagnosticsProcessorTests(unittest.TestCase):
    def test_projects_explicit_diagnostic_evidence_and_normalizes_dtc_codes(self):
        content, selected = build_diagnostics_section(
            "snapshot-1",
            [
                evidence("evidence-b", "page:2", "Diagnostic trouble code U0100 and dtc p0300."),
                evidence("evidence-a", "page:1", "DTC P0171 fuel trim fault."),
                evidence("evidence-c", "page:3", "General brake inspection procedure."),
            ],
        )

        self.assertEqual(content["section"], "diagnostics")
        self.assertEqual(content["source_snapshot_id"], "snapshot-1")
        self.assertEqual(content["record_count"], 2)
        self.assertEqual(
            [record["source_evidence_id"] for record in content["records"]],
            ["evidence-a", "evidence-b"],
        )
        self.assertEqual(content["records"][0]["diagnostic_codes"], ["P0171"])
        self.assertEqual(content["records"][1]["diagnostic_codes"], ["P0300", "U0100"])
        self.assertEqual([row["evidence_id"] for row in selected], ["evidence-a", "evidence-b"])

    def test_requires_approved_diagnostic_evidence(self):
        with self.assertRaisesRegex(ValueError, "approved"):
            build_diagnostics_section(
                "snapshot-1",
                [evidence("pending", "page:1", "DTC P0300", reviewer_state="pending")],
            )

    def test_does_not_publish_an_empty_diagnostics_section(self):
        with self.assertRaisesRegex(DiagnosticsProcessorError, "diagnostic evidence"):
            build_diagnostics_section(
                "snapshot-1",
                [evidence("generic", "page:1", "Vehicle owner maintenance notes")],
            )

    def test_processes_diagnostics_through_the_immutable_publisher(self):
        request = DeepRequest(
            event_id="event-1",
            request_id="request-1",
            projection_id="projection-1",
            correlation_id="correlation-1",
            idempotency_key="deep-1",
            section_name="diagnostics",
            source_snapshot_id="snapshot-1",
            processing_version="deep-v1",
        )
        source_evidence = [evidence("evidence-a", "page:1", "DTC P0300 random misfire")]

        with patch(
            "autodata_enrichment.diagnostics_processor.load_approved_source_evidence",
            return_value=source_evidence,
        ):
            with patch(
                "autodata_enrichment.diagnostics_processor.publish_deep_section",
                return_value={"status": "published"},
            ) as publish:
                result = process_diagnostics_request(request)

        self.assertEqual(result, {"status": "published"})
        job = publish.call_args.args[0]
        self.assertEqual(job.section_name, "diagnostics")
        self.assertEqual(job.content["records"][0]["diagnostic_codes"], ["P0300"])
        self.assertEqual(job.evidence, tuple(source_evidence))


if __name__ == "__main__":
    unittest.main()
