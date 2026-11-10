import unittest

from autodata_ingestion.article_document import build_ordered_document
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.vehicle_article_query import query_vehicle_articles


VEHICLE = {"year": 1999, "make": "Chevy", "model": "Silverado 1500", "region": "US", "drivetrain": "2WD"}
KEY = "chevrolet-silverado-1500-1999-us"


class VehicleArticleQueryTests(unittest.TestCase):
    def test_existing_normalized_article_is_returned_without_fetch(self):
        def fail_fetch(_vehicle, _query):
            raise AssertionError("fetcher must not run for a local hit")

        result = query_vehicle_articles(
            VEHICLE,
            "brake connector",
            {KEY: [{"article_id": "TSB-42", "title": "Brake connector bulletin"}]},
            fetcher=fail_fetch,
        )
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["results"][0]["article_id"], "TSB-42")
        self.assertEqual(result["results"][0]["match_score"], 1.0)

    def test_article_summary_is_searchable_without_source_fallback(self):
        def fail_fetch(_vehicle, _query):
            raise AssertionError("fetcher must not run for a local summary hit")

        result = query_vehicle_articles(
            VEHICLE,
            "bleeder screw",
            {KEY: [{"article_id": "article-summary", "title": "Service notes", "summary": "Locate the bleeder screw."}]},
            fetcher=fail_fetch,
        )
        self.assertEqual(result["status"], "found")
        self.assertEqual([article["article_id"] for article in result["results"]], ["article-summary"])

    def test_article_description_is_searchable_without_source_fallback(self):
        def fail_fetch(_vehicle, _query):
            raise AssertionError("fetcher must not run for a local description hit")

        result = query_vehicle_articles(
            VEHICLE,
            "coolant bleed valve",
            {KEY: [{"article_id": "article-description", "title": "Service notes", "description": "Check the coolant bleed valve."}]},
            fetcher=fail_fetch,
        )
        self.assertEqual(result["status"], "found")
        self.assertEqual([article["article_id"] for article in result["results"]], ["article-description"])

    def test_article_blocks_are_searchable_without_source_fallback(self):
        def fail_fetch(_vehicle, _query):
            raise AssertionError("fetcher must not run for a local block hit")

        result = query_vehicle_articles(
            VEHICLE,
            "ground strap location",
            {KEY: [{"article_id": "article-blocks", "title": "Service notes", "blocks": [{"type": "paragraph", "text": "Ground strap location is behind the intake."}]}]},
            fetcher=fail_fetch,
        )
        self.assertEqual(result["status"], "found")
        self.assertEqual([article["article_id"] for article in result["results"]], ["article-blocks"])

    def test_normalized_blocks_are_searchable_without_source_fallback(self):
        article = normalize_procedure_article({
            "article_id": "article-normalized",
            "title": "Service notes",
            "blocks": [{"kind": "table", "rows": [{"cells": ["Ground strap bolt", "12 Nm"]}]}],
        })

        def fail_fetch(_vehicle, _query):
            raise AssertionError("fetcher must not run for a normalized block hit")

        result = query_vehicle_articles(
            VEHICLE,
            "ground strap bolt",
            {KEY: [article]},
            fetcher=fail_fetch,
        )
        self.assertEqual(result["status"], "found")
        self.assertEqual([match["article_id"] for match in result["results"]], ["article-normalized"])

    def test_block_metadata_alone_does_not_match_article_query(self):
        result = query_vehicle_articles(
            VEHICLE,
            "paragraph",
            {KEY: [{
                "article_id": "article-metadata",
                "title": "Service notes",
                "blocks": [{"type": "paragraph", "text": "Replace timing belt."}],
            }]},
        )
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["results"], [])

    def test_hidden_normalized_step_label_does_not_match_article_query(self):
        article = {"article_id": "article-step-label", "title": "Service notes"}
        article["normalized_document"] = build_ordered_document(
            article,
            [{"kind": "step", "text": "Inspect ground strap.", "label": "HiddenCalibrationMarker"}],
        )

        result = query_vehicle_articles(
            VEHICLE,
            "HiddenCalibrationMarker",
            {KEY: [article]},
        )
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["results"], [])

    def test_hidden_normalized_list_label_does_not_match_article_query(self):
        article = {"article_id": "article-list-label", "title": "Service notes"}
        article["normalized_document"] = build_ordered_document(
            article,
            [{"kind": "ordered_list", "label": "HiddenListMarker", "items": ["Inspect ground strap."]}],
        )

        result = query_vehicle_articles(
            VEHICLE,
            "HiddenListMarker",
            {KEY: [article]},
        )
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["results"], [])

    def test_displayed_callout_and_table_labels_are_searchable(self):
        article = {"article_id": "article-visible-labels", "title": "Service notes"}
        article["normalized_document"] = build_ordered_document(
            article,
            [
                {"kind": "warning", "label": "High voltage isolation", "text": "Disconnect the battery."},
                {"kind": "table", "label": "Brake torque values", "rows": [["Caliper", "28 Nm"]]},
            ],
        )

        for query in ("High voltage isolation", "Brake torque values"):
            with self.subTest(query=query):
                result = query_vehicle_articles(VEHICLE, query, {KEY: [article]})
                self.assertEqual(result["status"], "found")
                self.assertEqual(result["results"][0]["article_id"], "article-visible-labels")

    def test_miss_invokes_source_fallback_and_indexes_fetched_article(self):
        calls = []

        def fetch(vehicle, query):
            calls.append((vehicle, query))
            return [{"article_id": "TSB-99", "title": "Transmission fluid procedure"}]

        index = {}
        result = query_vehicle_articles(VEHICLE, "transmission fluid", index, fetcher=fetch)
        self.assertEqual(result["status"], "fetched")
        self.assertEqual(result["results"][0]["article_id"], "TSB-99")
        self.assertEqual(calls[0][0]["make"], "Chevrolet")
        self.assertIn(KEY, index)

    def test_unknown_query_returns_not_found_without_fabricating_article(self):
        result = query_vehicle_articles(VEHICLE, "wiring diagram", {KEY: [{"article_id": "TSB-42", "title": "Brake connector bulletin"}]})
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["results"], [])


if __name__ == "__main__":
    unittest.main()
