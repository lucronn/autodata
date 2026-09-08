import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))

from knowledge_warm_path_benchmark import (  # noqa: E402
    DEFAULT_QUERY,
    WARM_PATH_TARGET,
    run_benchmark,
    validate_benchmark_report,
)


class KnowledgeWarmPathBenchmarkTests(unittest.TestCase):
    def test_report_distinguishes_fetched_cold_path_from_warm_cache_hit(self):
        observations = []
        clock_values = iter((1_000, 1_125, 2_000, 2_007))

        report = run_benchmark(
            clock=lambda: next(clock_values),
            on_measurement=observations.append,
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["query"], DEFAULT_QUERY)
        self.assertEqual(report["cold_fetch"]["status"], "fetched")
        self.assertEqual(report["warm_normalized_revision"]["status"], "cache_hit")
        self.assertEqual(report["cold_fetch"]["latency_ns"], 125)
        self.assertEqual(report["warm_normalized_revision"]["latency_ns"], 7)
        self.assertEqual(
            report["cold_fetch"]["result_count"],
            report["warm_normalized_revision"]["result_count"],
        )
        self.assertEqual(report["resolver_calls_total"], 1)
        self.assertEqual(report["cold_fetch"]["resolver_calls"], 1)
        self.assertEqual(report["warm_normalized_revision"]["resolver_calls"], 0)
        self.assertTrue(report["comparisons"]["cold_slower_than_warm"])
        validate_benchmark_report(report)
        json.dumps(report, sort_keys=True)
        self.assertEqual(
            [item.phase for item in observations],
            ["cold_fetch", "warm_normalized_revision"],
        )

    def test_warm_lookup_preserves_order_and_provenance_from_fetched_revision(self):
        report = run_benchmark(clock=iter((10, 20, 30, 40)).__next__)

        cold = report["cold_fetch"]
        warm = report["warm_normalized_revision"]

        self.assertEqual(cold["result_order"], warm["result_order"])
        self.assertEqual(cold["provenance"], warm["provenance"])
        self.assertEqual(cold["revision_id"], warm["revision_id"])
        self.assertEqual(
            cold["result_order"],
            ["article:TSB-42", "procedure:procedure:TSB-42"],
        )
        self.assertEqual(
            cold["provenance"],
            [
                {
                    "evidence_id": cold["provenance"][0]["evidence_id"],
                    "source_uri": "https://static.source.test/articles/tsb-42",
                    "source_version": "fixture-v1",
                }
            ],
        )

    def test_target_documents_report_only_measurement_hook(self):
        self.assertEqual(WARM_PATH_TARGET["name"], "normalized_revision_lookup")
        self.assertEqual(WARM_PATH_TARGET["metric"], "latency_ns")
        self.assertEqual(WARM_PATH_TARGET["enforcement"], "report_only")
        self.assertEqual(WARM_PATH_TARGET["measurement_hook"], "on_measurement")


if __name__ == "__main__":
    unittest.main()
