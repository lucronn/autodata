import unittest

from autodata_ingestion.autoapitwo_guide import (
    _actions,
    _components,
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


class CombinedProcedureConnector(FakeConnector):
    def __init__(self):
        super().__init__()
        self.articles["starter-combined"] = {
            "article_id": "starter-combined",
            "title": "Removal and Installation",
            "body": "1. REMOVE STARTER. 2. INSTALL STARTER. Torque: 39 Nm.",
            "blocks": [
                {"kind": "text", "text": "1. REMOVE STARTER.", "evidence_ids": ["e-starter"]},
                {"kind": "text", "text": "2. INSTALL STARTER.", "evidence_ids": ["e-starter"]},
                {"kind": "image", "url": "https://autoapitwo.vercel.app/fig/starter.png", "alt": "Starter", "evidence_ids": ["e-starter"]},
            ],
            "images": [],
            "evidence_ids": ["e-starter"],
            "vehicle": {"id": "41215"},
        }

    def search(self, car_id, term):
        if "starter" in term.casefold():
            return [{"display": "Starter Motor >> Removal and Installation (Service and Repair)", "_links": {"self": {"href": "/starter-combined"}}}]
        return super().search(car_id, term)


class IllustratedGuideTests(unittest.TestCase):
    def test_ellipsized_provider_summary_is_omitted_but_concise_procedure_remains(self):
        articles = [
            {
                "article_id": "starter-removal",
                "component": "starter",
                "procedure_kind": "removal",
                "blocks": [{"kind": "text", "text": "Remove the starter.", "evidence_ids": ["e-removal"]}],
                "evidence_ids": ["e-removal"],
            },
            {
                "article_id": "starter-installation",
                "component": "starter",
                "procedure_kind": "installation",
                "blocks": [{"kind": "text", "text": "Install the starter and torque the mounting bolts.", "evidence_ids": ["e-installation"]}],
                "evidence_ids": ["e-installation"],
            },
            {
                "article_id": "detailed-long-removal",
                "component": "starter",
                "procedure_kind": "removal",
                "blocks": [{"kind": "text", "text": "Remove the starter after disconnecting the harness and removing the upper mounting fastener " + ("with care " * 35), "evidence_ids": ["e-long-removal"]}],
                "evidence_ids": ["e-long-removal"],
            },
            {
                "article_id": "provider-summary",
                "component": "starter",
                "procedure_kind": "procedure",
                "blocks": [{"kind": "text", "text": "Refer to Figs for the complete provider procedure " + ("x" * 220), "evidence_ids": ["e-summary"]}],
                "evidence_ids": ["e-summary"],
            },
            {
                "article_id": "concise-check",
                "component": "starter",
                "procedure_kind": "procedure",
                "blocks": [{"kind": "text", "text": "Check charging output after installation.", "evidence_ids": ["e-check"]}],
                "evidence_ids": ["e-check"],
            },
        ]

        guide = compose_illustrated_guide(
            "starter replacement", {"year": 2005, "make": "Toyota", "model": "Camry"}, articles
        )

        actions = [step["action"] for step in guide["steps"]]
        self.assertIn("Remove the starter.", actions)
        self.assertIn("Install the starter and torque the mounting bolts.", actions)
        self.assertIn("Check charging output after installation.", actions)
        self.assertTrue(any(action.startswith("Remove the starter after disconnecting") and len(action) > 180 for action in actions))
        self.assertFalse(any(action.endswith("...") for action in actions))

    def test_specific_brake_component_does_not_expand_to_generic_brakes(self):
        self.assertEqual(_components("front brake caliper replacement"), ["brake_caliper"])

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

    def test_combined_removal_and_installation_article_covers_both_phases(self):
        connector = CombinedProcedureConnector()
        articles = retrieve_autoapitwo_articles(
            "starter replacement",
            {"year": 1997, "make": "Toyota", "model": "RAV4", "autoapitwo_vehicle_id": "41215"},
            connector=connector,
        )
        guide = compose_illustrated_guide(
            "starter replacement", {"year": 1997, "make": "Toyota", "model": "RAV4"}, articles
        )
        self.assertEqual(len(articles), 1)
        self.assertEqual(guide["content_status"], "complete")
        self.assertFalse(any(gap.startswith("missing_") for gap in guide["gaps"]))
        self.assertEqual([step["phase"] for step in guide["steps"]], ["removal", "installation"])

    def test_composed_step_does_not_repeat_heading_as_first_instruction(self):
        connector = CombinedProcedureConnector()
        articles = retrieve_autoapitwo_articles(
            "starter replacement",
            {"year": 1997, "make": "Toyota", "model": "RAV4", "autoapitwo_vehicle_id": "41215"},
            connector=connector,
        )
        guide = compose_illustrated_guide(
            "starter replacement", {"year": 1997, "make": "Toyota", "model": "RAV4"}, articles
        )

        first_step = guide["steps"][0]
        self.assertEqual(first_step["action"], "REMOVE STARTER.")
        self.assertNotEqual(first_step["instructions"][0] if first_step["instructions"] else "", first_step["action"])

    def test_removal_and_replacement_title_is_a_combined_procedure(self):
        self.assertEqual(
            _actions("Water Pump >> Removal and Replacement (Service and Repair)"),
            ["removal_and_installation"],
        )
