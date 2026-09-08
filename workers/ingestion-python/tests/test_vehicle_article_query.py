import unittest

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
