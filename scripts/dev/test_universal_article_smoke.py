import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))

from universal_article_smoke import (
    DEFAULT_TARGET,
    SAMPLE_ARTICLE_HTML,
    ReplayStore,
    StaticHTTPSource,
    build_structured_catalog,
    intake_fixture,
    intake_idempotency_key,
    keyword_to_structured_json,
    measure_keyword_lookup,
    validate_knowledge_response,
)


class UniversalArticleSmokeTests(unittest.TestCase):
    def test_static_http_intake_associates_article_with_target_vehicle(self):
        source = StaticHTTPSource(SAMPLE_ARTICLE_HTML)

        intake = intake_fixture(source)

        self.assertEqual(source.requests, [{"source_uri": source.source_uri}])
        self.assertEqual(intake.status, "ready")
        self.assertEqual(intake.bundle.vehicle["vehicle_key"], DEFAULT_TARGET.vehicle_key)
        self.assertEqual(intake.bundle.articles[0]["article_id"], "TSB-42")
        self.assertEqual(intake.bundle.articles[0]["content_locator"], "html:article")

    def test_keyword_lookup_returns_structured_article_and_procedure_json(self):
        intake = intake_fixture(StaticHTTPSource(SAMPLE_ARTICLE_HTML))
        catalog = build_structured_catalog(intake)

        response = keyword_to_structured_json(catalog, "brake caliper torque")

        validate_knowledge_response(response)
        json.loads(json.dumps(response, sort_keys=True))
        self.assertEqual(response["vehicle_identity"]["vehicle_key"], DEFAULT_TARGET.vehicle_key)
        self.assertEqual(
            [result["kind"] for result in response["results"]],
            ["article", "procedure"],
        )
        article = response["results"][0]["article"]
        procedure = response["results"][1]["procedure"]
        self.assertEqual(article["article_id"], "TSB-42")
        self.assertEqual(article["steps"], ["Remove the wheel", "Torque the caliper guide pins"])
        self.assertEqual(procedure["procedure_id"], "procedure:TSB-42")
        self.assertIn("torque", procedure["matched_terms"])
        self.assertTrue(response["results"][0]["evidence"])
        self.assertTrue(response["results"][1]["evidence"])

    def test_duplicate_publish_is_a_replay_without_a_second_record(self):
        source = StaticHTTPSource(SAMPLE_ARTICLE_HTML)
        first_intake = intake_fixture(source)
        replay_intake = intake_fixture(source)
        catalog = build_structured_catalog(first_intake)
        response = keyword_to_structured_json(catalog, "brake caliper")
        store = ReplayStore()
        key = intake_idempotency_key(first_intake)

        first = store.publish(key, response)
        replay = store.publish(key, response)

        self.assertEqual(first.status, "created")
        self.assertEqual(replay.status, "replay")
        self.assertEqual(first.payload, replay.payload)
        self.assertEqual(store.write_count, 1)
        self.assertEqual(replay_intake.bundle.articles[0]["article_id"], "TSB-42")
        with self.assertRaisesRegex(ValueError, "conflicting replay"):
            store.publish(key, {**response, "revision_id": "different-revision"})

    def test_lookup_latency_hook_reports_measured_duration(self):
        intake = intake_fixture(StaticHTTPSource(SAMPLE_ARTICLE_HTML))
        catalog = build_structured_catalog(intake)
        clock_values = iter((1_000_000, 1_004_250))
        observations = []

        response, metrics = measure_keyword_lookup(
            catalog,
            "brake caliper",
            clock=lambda: next(clock_values),
            on_latency=observations.append,
        )

        self.assertEqual(metrics.elapsed_ns, 4_250)
        self.assertEqual(metrics.result_count, len(response["results"]))
        self.assertEqual(observations, [metrics])
        self.assertGreaterEqual(metrics.elapsed_ns, 0)


if __name__ == "__main__":
    unittest.main()
