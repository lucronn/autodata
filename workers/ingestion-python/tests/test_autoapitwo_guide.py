import unittest

from autodata_ingestion.autoapitwo_guide import (
    compose_illustrated_guide,
    retrieve_autoapitwo_articles,
    vehicle_candidates_from_autoapitwo,
)


class FakeConnector:
    def __init__(self):
        self.articles = {
            "oil-removal": {"article_id": "oil-removal", "title": "Removal", "body": "Remove oil pump. Torque 8 Nm.", "blocks": [{"kind": "image", "url": "https://autoapitwo.vercel.app/fig/oil.png", "alt": "Oil pump"}, {"kind": "text", "text": "Remove oil pump. Torque 8 Nm.", "evidence_ids": ["e-oil"]}], "images": [{"url": "https://autoapitwo.vercel.app/fig/oil.png", "alt": "Oil pump", "evidence_ids": ["e-oil"]}], "evidence_ids": ["e-oil"], "vehicle": {"id": "41215"}},
            "oil-install": {"article_id": "oil-install", "title": "Installation", "body": "Install oil pump. Torque 8 Nm.", "blocks": [{"kind": "text", "text": "Install oil pump. Torque 8 Nm.", "evidence_ids": ["e-oil-i"]}], "images": [], "evidence_ids": ["e-oil-i"], "vehicle": {"id": "41215"}},
            "water-removal": {"article_id": "water-removal", "title": "Removal", "body": "Remove water pump.", "blocks": [{"kind": "text", "text": "Remove water pump.", "evidence_ids": ["e-water-r"]}], "images": [], "evidence_ids": ["e-water-r"], "vehicle": {"id": "41215"}},
            "water-install": {"article_id": "water-install", "title": "Installation", "body": "Install water pump.", "blocks": [{"kind": "text", "text": "Install water pump.", "evidence_ids": ["e-water-i"]}], "images": [], "evidence_ids": ["e-water-i"], "vehicle": {"id": "41215"}},
            "timing-removal": {"article_id": "timing-removal", "title": "Removal", "body": "Remove timing belt.", "blocks": [{"kind": "text", "text": "Remove timing belt.", "evidence_ids": ["e-timing-r"]}], "images": [], "evidence_ids": ["e-timing-r"], "vehicle": {"id": "41215"}},
            "timing-install": {"article_id": "timing-install", "title": "Installation", "body": "Install timing belt and verify timing marks.", "blocks": [{"kind": "text", "text": "Install timing belt and verify timing marks.", "evidence_ids": ["e-timing-i"]}], "images": [], "evidence_ids": ["e-timing-i"], "vehicle": {"id": "41215"}},
        }

    def search_vehicles(self, query):
        return [{"id": "41215", "year": "1997", "make": "Toyota Truck", "model": "RAV4 2-Door 2WD", "engine": "L4-2.0L (3S-FE)", "description": "1997 Toyota Truck RAV4 2-Door 2WD L4-2.0L (3S-FE)"}]

    def search(self, car_id, term):
        values = [
            {"display": "Oil Pump, Engine >> Procedures (Service and Repair) >> Removal", "_links": {"self": {"href": "/oil-removal"}}},
            {"display": "Oil Pump, Engine >> Procedures (Service and Repair) >> Installation", "_links": {"self": {"href": "/oil-install"}}},
            {"display": "Water Pump >> Procedures (Service and Repair) >> Removal and Installation >> Removal", "_links": {"self": {"href": "/water-removal"}}},
            {"display": "Water Pump >> Procedures (Service and Repair) >> Removal and Installation >> Installation", "_links": {"self": {"href": "/water-install"}}},
        ]
        if "timing" in term.casefold():
            values = [
                {"display": "Timing Belt >> Procedures (Service and Repair) >> Removal", "_links": {"self": {"href": "/timing-removal"}}},
                {"display": "Timing Belt >> Procedures (Service and Repair) >> Installation", "_links": {"self": {"href": "/timing-install"}}},
            ]
        return values

    def article(self, car_id, href, title=None):
        return self.articles[href.lstrip("/")]


class IllustratedGuideTests(unittest.TestCase):
    def test_vehicle_candidates_keep_provider_identity_separate(self):
        candidate = vehicle_candidates_from_autoapitwo("1997 Toyota RAV4 oil pump", connector=FakeConnector())[0]
        self.assertEqual(candidate["autoapitwo_vehicle_id"], "41215")
        self.assertNotEqual(candidate["vehicle_id"], "41215")

    def test_retrieval_selects_procedure_pairs_and_composer_keeps_figures(self):
        articles = retrieve_autoapitwo_articles(
            "1997 Toyota RAV4 oil pump and water pump replacement",
            {"year": 1997, "make": "Toyota", "model": "RAV4", "autoapitwo_vehicle_id": "41215"},
            connector=FakeConnector(),
        )
        guide = compose_illustrated_guide("oil pump and water pump replacement", {"year": 1997, "make": "Toyota", "model": "RAV4"}, articles)
        self.assertEqual(guide["content_status"], "complete")
        self.assertTrue(guide["pdf_ready"])
        self.assertIn("https://autoapitwo.vercel.app/fig/oil.png", [image["url"] for step in guide["steps"] for image in step["images"]])
        self.assertEqual(len({step["sequence"] for step in guide["steps"]}), len(guide["steps"]))
        self.assertNotIn("source says", str(guide).casefold())

    def test_missing_installation_is_an_actionable_preview(self):
        connector = FakeConnector()
        connector.articles.pop("water-install")
        articles = retrieve_autoapitwo_articles(
            "water pump replacement", {"year": 1997, "make": "Toyota", "model": "RAV4", "autoapitwo_vehicle_id": "41215"}, connector=connector
        )
        guide = compose_illustrated_guide("water pump replacement", {"year": 1997, "make": "Toyota", "model": "RAV4"}, articles)
        self.assertEqual(guide["content_status"], "partial")
        self.assertFalse(guide["pdf_ready"])
        self.assertIn("missing_installation:water_pump", guide["gaps"])
