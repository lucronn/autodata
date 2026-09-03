import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts/dev"))

from ingestion_smoke import summarize_source_object, summarize_viewable_event  # noqa: E402
from normalize_source_directory import summarize_source_artifacts  # noqa: E402
from autodata_ingestion.source_adapters import SourceResource, adapt_source_resource  # noqa: E402


class IngestionSmokeContractTests(unittest.TestCase):
    def test_source_report_exposes_safe_deterministic_resource_outcomes(self):
        html = SourceResource.from_bytes(
            "file://b.html",
            "v1",
            b"<html><body>Brake procedure</body></html>",
            "text/html",
        )
        unknown = SourceResource.from_bytes(
            "file://a.bin",
            "v1",
            b"\x00opaque",
            "application/octet-stream",
        )

        report = summarize_source_artifacts(
            [adapt_source_resource(html), adapt_source_resource(unknown)]
        )

        self.assertEqual([item["source_uri"] for item in report], ["file://a.bin", "file://b.html"])
        self.assertEqual(report[0]["kind"], "quarantine")
        self.assertTrue(report[0]["needs_review"])
        self.assertEqual(report[0]["review_reasons"], ["unsupported_media_type"])
        self.assertEqual(report[1]["kind"], "document")
        self.assertEqual(report[1]["candidate_count"], 1)
        self.assertEqual(report[1]["candidate_kinds"], {"document_text": 1})
        self.assertFalse(report[1]["needs_review"])
        self.assertNotIn("payload", report[1])
        self.assertNotIn("raw_payload", report[1])

    def test_protected_workflow_runs_live_fast_lane_smoke_with_cleanup(self):
        workflow = (ROOT / ".github/workflows/autonomous-verification.yml").read_text()

        self.assertIn("timeout-minutes: 20", workflow)
        self.assertIn("Run live Compose fast-lane smoke", workflow)
        self.assertIn("docker compose -f infra/compose/compose.yaml up -d --wait postgres nats minio", workflow)
        self.assertIn("docker compose -f infra/compose/compose.yaml run migration-runner", workflow)
        self.assertIn("docker compose -f infra/compose/compose.yaml run --rm ingest-fixture", workflow)
        self.assertIn("docker compose -f infra/compose/compose.yaml run --rm --no-deps ingestion-smoke", workflow)
        self.assertIn(
            "trap 'docker compose -f infra/compose/compose.yaml down --volumes --remove-orphans' EXIT",
            workflow,
        )

    def test_source_object_summary_checks_content_hash_and_identity(self):
        payload = b'{"vehicle":{"make":"Toyota","model":"Corolla","year":2024,"region":"US"}}'

        summary = summarize_source_object(payload, "Toyota Corolla 2024", "toyota-corolla-2024-us")

        self.assertEqual(summary["object_bytes"], len(payload))
        self.assertEqual(summary["object_vehicle"], "Toyota Corolla 2024")

    def test_viewable_event_summary_requires_versioned_event_and_revision(self):
        event = {
            "event_type": "dataset.viewable",
            "event_version": 1,
            "revision_id": "revision-1",
            "idempotency_key": "viewable:request-1:1",
        }

        summary = summarize_viewable_event(event, "revision-1")

        self.assertEqual(summary["subject"], "dataset.viewable")
        self.assertEqual(summary["revision_id"], "revision-1")

    def test_viewable_event_summary_fails_actionably_for_wrong_event(self):
        with self.assertRaisesRegex(ValueError, "dataset.viewable"):
            summarize_viewable_event({"event_type": "dataset.deep.requested"}, "revision-1")


if __name__ == "__main__":
    unittest.main()
