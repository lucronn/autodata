"""Contract tests for the deterministic chat cold/warm smoke harness."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(Path(__file__).parent))

from chat_smoke import DEFAULT_QUERY, run_smoke, validate_smoke_report  # noqa: E402


class ChatSmokeTests(unittest.TestCase):
    def test_cold_path_publishes_source_then_normalized_answer_and_price_refresh(self):
        report = run_smoke()
        validate_smoke_report(report)

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["request"]["message"], DEFAULT_QUERY)
        cold = report["cold"]
        self.assertEqual(cold["source"]["answer"]["data_state"], "source_unnormalized")
        self.assertIn(
            cold["normalized"]["answer"]["procedure"]["status"],
            {"available_provisional", "ready"},
        )
        quote = cold["normalized"]["answer"]["quote"]
        self.assertFalse(quote["parts_summary"]["markup_applied"])
        self.assertGreaterEqual(quote["labor"]["required_hours"], 0)
        self.assertGreaterEqual(quote["labor"]["recommended_hours"], 0)
        self.assertGreaterEqual(quote["labor"]["overlap_hours_removed"], 0)
        self.assertTrue(quote["labor"]["overlap_operations"])
        self.assertTrue(cold["normalized"]["answer"]["procedure"]["steps"])
        self.assertTrue(cold["source"]["answer"]["source_unnormalized"]["articles"])
        self.assertTrue(cold["normalized"]["answer"]["quote"]["parts"])
        self.assertEqual(cold["stale_price"]["priced_at"], "2026-08-01T00:00:00Z")
        self.assertTrue(cold["stale_price"]["returned_before_refresh"])
        self.assertEqual(cold["refreshed"]["priced_at"], "2026-09-11T00:00:00Z")
        self.assertTrue(cold["normalized"]["workers"]["events"])
        self.assertTrue(
            any(
                update["data_state"] == "source_unnormalized"
                for update in cold["source"]["updates"]
            )
        )

    def test_warm_replays_reuse_revision_and_make_no_source_or_model_calls(self):
        report = run_smoke()
        warm = report["warm"]

        self.assertEqual(warm["same_idempotency"]["query_id"], report["cold"]["query_id"])
        self.assertEqual(warm["same_idempotency"]["source_calls"], 0)
        self.assertEqual(warm["same_idempotency"]["model_calls"], 0)
        self.assertEqual(warm["semantic_replay"]["source_calls"], 0)
        self.assertEqual(warm["semantic_replay"]["model_calls"], 0)
        self.assertEqual(
            warm["semantic_replay"]["revision_id"],
            report["cold"]["refreshed"]["revision_id"],
        )
        self.assertEqual(
            warm["semantic_replay"]["derived_article_id"],
            report["cold"]["refreshed"]["derived_article_id"],
        )

    def test_additional_vehicle_queries_resolve_quote_procedure_and_warm_replay(self):
        report = run_smoke()
        cases = report["additional_cases"]

        self.assertEqual(
            [case["name"] for case in cases],
            ["silverado_oil_water_pumps", "tacoma_alternator"],
        )
        for case in cases:
            with self.subTest(case=case["name"]):
                answer = case["cold"]["answer"]
                vehicle = answer["vehicle"]
                procedure = answer["procedure"]
                quote = answer["quote"]

                self.assertEqual(vehicle["vehicle_id"], case["expected_vehicle_id"])
                self.assertEqual(answer["answer_status"], "available")
                self.assertIn(procedure["status"], {"available_provisional", "ready"})
                self.assertTrue(procedure["steps"])
                self.assertTrue(quote["parts"])
                self.assertGreaterEqual(quote["labor"]["total_hours"], 0)
                self.assertGreaterEqual(quote["labor"]["overlap_hours_removed"], 0)

                if case["expects_overlap"]:
                    self.assertTrue(quote["labor"]["overlap_operations"])
                else:
                    self.assertFalse(quote["labor"]["overlap_operations"])

                warm = case["warm"]
                self.assertEqual(warm["status"], "available")
                self.assertEqual(warm["revision_id"], case["cold"]["revision_id"])
                self.assertEqual(warm["derived_article_id"], case["cold"]["derived_article_id"])
                self.assertEqual(warm["source_calls"], 0)
                self.assertEqual(warm["model_calls"], 0)

    def test_existing_diagram_is_redrawn_to_linked_vector_artifact(self):
        report = run_smoke()
        visual = report["cold"]["visual"]

        self.assertTrue(visual["renderable"])
        self.assertEqual(visual["review_state"], "pending")
        self.assertEqual(visual["label"], "AI-enhanced / UNREVIEWED")
        self.assertEqual(visual["source_uri"], "https://source.test/rav4/brake-line.png")
        self.assertTrue(visual["source_artifact_id"])
        self.assertTrue(visual["derived_artifact_id"])
        self.assertNotEqual(visual["source_artifact_id"], visual["derived_artifact_id"])
        self.assertEqual(report["calls"]["vectorizer"], 1)

    def test_report_is_json_serializable_and_contains_call_budget(self):
        report = run_smoke()
        encoded = json.dumps(report, sort_keys=True)
        self.assertIn('"status": "passed"', encoded)
        self.assertEqual(report["calls"], {
            "source": 3,
            "normalizer": 3,
            "model": 3,
            "composer": 3,
            "price_refresh": 3,
            "vectorizer": 1,
        })

    def test_compose_and_ci_wiring_are_opt_in_and_preserve_existing_smokes(self):
        compose = (ROOT / "infra/compose/compose.yaml").read_text()
        workflow = (ROOT / ".github/workflows/autonomous-verification.yml").read_text()

        self.assertIn("chat-smoke:", compose)
        self.assertIn('profiles: ["verification"]', compose)
        self.assertIn("scripts/dev/chat_smoke.py", compose)
        self.assertIn("ingestion-smoke:", compose)
        self.assertIn("run --rm --no-deps chat-smoke", workflow)
        self.assertIn("Run live Compose fast-lane smoke", workflow)


if __name__ == "__main__":
    unittest.main()
