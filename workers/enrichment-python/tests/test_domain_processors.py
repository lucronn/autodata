import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.deep_dispatch import DeepRequest  # noqa: E402
from autodata_enrichment.domain_processors import (  # noqa: E402
    DomainProcessorError,
    build_electrical_section,
    build_inventory_section,
    build_maintenance_section,
    build_procedures_section,
    process_electrical_request,
    process_inventory_request,
    process_maintenance_request,
    process_procedures_request,
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


DOMAIN_CASES = (
    ("procedures", build_procedures_section, "Repair procedure: remove cover, install replacement, and torque fastener."),
    ("electrical", build_electrical_section, "Wiring harness connector C101 pinout: check circuit voltage and ground."),
    ("inventory", build_inventory_section, "Inventory part number A-123, special tool, quantity 2."),
    ("maintenance", build_maintenance_section, "Maintenance service interval: replace engine oil and filter."),
)


class DomainProcessorTests(unittest.TestCase):
    def test_projects_each_domain_from_explicit_section_signals(self):
        for section_name, builder, text in DOMAIN_CASES:
            with self.subTest(section=section_name):
                content, selected = builder(
                    "snapshot-1",
                    [evidence("evidence-b", "page:2", text), evidence("generic", "page:1", "Vehicle identity only")],
                )

                self.assertEqual(content["section"], section_name)
                self.assertEqual(content["projection"], "approved-section-evidence")
                self.assertEqual(content["record_count"], 1)
                self.assertEqual(content["records"][0]["source_evidence_id"], "evidence-b")
                self.assertTrue(content["records"][0]["matched_terms"])
                self.assertEqual(selected, (evidence("evidence-b", "page:2", text),))

    def test_requires_approved_evidence(self):
        with self.assertRaisesRegex(ValueError, "approved"):
            build_procedures_section(
                "snapshot-1",
                [evidence("pending", "page:1", "Repair procedure", reviewer_state="pending")],
            )

    def test_does_not_publish_a_section_without_matching_evidence(self):
        with self.assertRaisesRegex(DomainProcessorError, "procedures evidence"):
            build_procedures_section("snapshot-1", [evidence("generic", "page:1", "Vehicle identity only")])

    def test_each_section_uses_the_immutable_publisher(self):
        request = DeepRequest(
            event_id="event-1",
            request_id="request-1",
            projection_id="projection-1",
            correlation_id="correlation-1",
            idempotency_key="deep-1",
            section_name="electrical",
            source_snapshot_id="snapshot-1",
            processing_version="deep-v1",
        )
        source_evidence = [evidence("evidence-a", "page:1", "Wiring harness connector C101")]

        with patch(
            "autodata_enrichment.domain_processors.load_approved_source_evidence",
            return_value=source_evidence,
        ):
            with patch(
                "autodata_enrichment.domain_processors.publish_deep_section",
                return_value={"status": "published"},
            ) as publish:
                result = process_electrical_request(request)

        self.assertEqual(result, {"status": "published"})
        job = publish.call_args.args[0]
        self.assertEqual(job.section_name, "electrical")
        self.assertEqual(job.evidence, tuple(source_evidence))
        self.assertEqual(job.content["record_count"], 1)

    def test_all_remaining_domain_processors_are_registered(self):
        from autodata_enrichment.deep_dispatch import _SECTION_PROCESSORS
        from autodata_enrichment.search_processor import register_builtin_processors

        register_builtin_processors()

        for section_name in ("diagnostics", "procedures", "electrical", "inventory", "maintenance", "search", "quality"):
            with self.subTest(section=section_name):
                self.assertIn(section_name, _SECTION_PROCESSORS)

    def test_process_functions_have_the_expected_section_identity(self):
        functions = (
            (process_procedures_request, "procedures"),
            (process_electrical_request, "electrical"),
            (process_inventory_request, "inventory"),
            (process_maintenance_request, "maintenance"),
        )
        for processor, section_name in functions:
            self.assertEqual(processor.__name__, f"process_{section_name}_request")


if __name__ == "__main__":
    unittest.main()
