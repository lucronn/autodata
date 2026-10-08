import unittest
from types import SimpleNamespace

from autodata_ingestion.banktwo_guide import (
    _actions,
    _components,
    compose_illustrated_guide,
    retrieve_banktwo_articles,
    vehicle_candidates_from_banktwo,
)


class FakeConnector:
    def __init__(self):
        self.articles = {
            "oil-removal": {"article_id": "oil-removal", "title": "Removal", "body": "Remove oil pump. Torque 8 Nm.", "blocks": [{"kind": "image", "asset_resource_ref": "asset-oil-opaque", "image_id": "oil-image", "alt": "Oil pump"}, {"kind": "text", "text": "Remove oil pump. Torque 8 Nm.", "evidence_ids": ["e-oil"]}], "images": [{"asset_resource_ref": "asset-oil-opaque", "image_id": "oil-image", "alt": "Oil pump", "evidence_ids": ["e-oil"]}], "evidence_ids": ["e-oil"], "vehicle": {"id": "vehicle-41215"}},
            "oil-install": {"article_id": "oil-install", "title": "Installation", "body": "Install oil pump. Torque 8 Nm.", "blocks": [{"kind": "text", "text": "Install oil pump. Torque 8 Nm.", "evidence_ids": ["e-oil-i"]}], "images": [], "evidence_ids": ["e-oil-i"], "vehicle": {"id": "vehicle-41215"}},
            "water-removal": {"article_id": "water-removal", "title": "Removal", "body": "Remove water pump.", "blocks": [{"kind": "text", "text": "Remove water pump.", "evidence_ids": ["e-water-r"]}], "images": [], "evidence_ids": ["e-water-r"], "vehicle": {"id": "vehicle-41215"}},
            "water-install": {"article_id": "water-install", "title": "Installation", "body": "Install water pump.", "blocks": [{"kind": "text", "text": "Install water pump.", "evidence_ids": ["e-water-i"]}], "images": [], "evidence_ids": ["e-water-i"], "vehicle": {"id": "vehicle-41215"}},
            "timing-removal": {"article_id": "timing-removal", "title": "Removal", "body": "Remove timing belt.", "blocks": [{"kind": "text", "text": "Remove timing belt.", "evidence_ids": ["e-timing-r"]}], "images": [], "evidence_ids": ["e-timing-r"], "vehicle": {"id": "vehicle-41215"}},
            "timing-install": {"article_id": "timing-install", "title": "Installation", "body": "Install timing belt and verify timing marks.", "blocks": [{"kind": "text", "text": "Install timing belt and verify timing marks.", "evidence_ids": ["e-timing-i"]}], "images": [], "evidence_ids": ["e-timing-i"], "vehicle": {"id": "vehicle-41215"}},
        }

    def resolve_vehicle(self, selector):
        return SimpleNamespace(body={"candidates": [{
            "opaque_ref": "vehicle-41215", "label": "1997 Toyota RAV4 2-Door 2WD 2.0L",
            "confidence": 0.99, "evidence": ["fixture catalog"],
        }]})

    def search(self, car_id, term):
        component = next((name for name in ("oil", "water", "timing", "starter") if name in term.casefold()), "oil")
        if component == "oil":
            ids = ("oil-removal", "oil-install")
        elif component == "water":
            ids = ("water-removal", "water-install")
        elif component == "timing":
            ids = ("timing-removal", "timing-install")
        else:
            ids = ("starter-combined",)
        return [
            {"opaque_ref": article_id, "resource_ref": f"resource-{article_id}",
             "title": self.articles[article_id]["title"], "category": "Service and Repair",
             "component": f"{component}_pump" if component in {"oil", "water"} else component}
            for article_id in ids if article_id in self.articles
        ]

    def article_by_descriptor(self, source_vehicle_ref, descriptor):
        key = str(descriptor.get("opaque_ref") or "").removeprefix("resource-")
        if key not in self.articles:
            key = str(descriptor.get("opaque_ref") or "").removeprefix("resource-")
        return self.articles[key]


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
                {"kind": "image", "asset_resource_ref": "asset-starter-opaque", "image_id": "starter-image", "alt": "Starter", "evidence_ids": ["e-starter"]},
            ],
            "images": [],
            "evidence_ids": ["e-starter"],
            "vehicle": {"id": "vehicle-41215"},
        }

    def search(self, car_id, term):
        if "starter" in term.casefold():
            return [{"opaque_ref": "starter-combined", "resource_ref": "resource-starter-combined",
                     "title": "Starter Motor Removal and Installation", "category": "Service and Repair",
                     "component": "starter"}]
        return super().search(car_id, term)


class SilveradoCandidateConnector:
    def resolve_vehicle(self, _selector):
        return SimpleNamespace(body={"candidates": [{
            "opaque_ref": "vehicle-49999", "confidence": 1.0,
            "label": "1999 For A Chevrolet Silverado 1500 2WD 5.3L",
        }]})


class IllustratedGuideTests(unittest.TestCase):
    def test_configured_provider_connector_is_reused_for_fast_repeat_lookups(self):
        from autodata_ingestion import banktwo_guide

        created = []

        source_client = object()
        class Connector:
            def __init__(self, source_client=None):
                created.append(source_client)

        original = banktwo_guide.BanktwoConnector
        original_registry = banktwo_guide.source_connector_registry
        original_connector = banktwo_guide._CONFIGURED_CONNECTOR
        original_base = banktwo_guide._CONFIGURED_CONNECTOR_BASE
        try:
            banktwo_guide._CONFIGURED_CONNECTOR = None
            banktwo_guide._CONFIGURED_CONNECTOR_BASE = None
            banktwo_guide.source_connector_registry = lambda **_kwargs: {"banktwo": source_client}
            banktwo_guide.BanktwoConnector = Connector
            first = banktwo_guide._configured_connector()
            second = banktwo_guide._configured_connector()
        finally:
            banktwo_guide.BanktwoConnector = original
            banktwo_guide.source_connector_registry = original_registry
            banktwo_guide._CONFIGURED_CONNECTOR = original_connector
            banktwo_guide._CONFIGURED_CONNECTOR_BASE = original_base

        self.assertIs(first, second)
        self.assertEqual(created, [source_client])

    def test_applicability_preserves_exact_selected_vehicle_label(self):
        vehicle = {
            "year": 1997,
            "make": "Toyota",
            "model": "RAV4",
            "body_style": "2-door",
            "drivetrain": "4WD",
            "engine": 2.0,
            "label": "1997 Toyota Truck RAV4 2-Door 4WD L4-2.0L (3S-FE)",
        }

        guide = compose_illustrated_guide("starter replacement", vehicle, [])

        self.assertEqual(guide["applicability"], vehicle["label"])

    def test_applicability_fallback_adds_missing_variant_details(self):
        vehicle = {
            "year": 1997,
            "make": "Toyota",
            "model": "RAV4",
            "body_style": "2-door",
            "drivetrain": "4WD",
            "engine_displacement_l": 2.0,
        }

        guide = compose_illustrated_guide("starter replacement", vehicle, [])

        self.assertEqual(guide["applicability"], "1997 Toyota RAV4 2-door 4WD 2.0L")

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

    def test_provider_prose_make_is_normalized_in_candidate_and_applicability(self):
        candidate = vehicle_candidates_from_banktwo(
            "1999 Chevrolet Silverado 1500 2WD 5.3L oil pump",
            connector=SilveradoCandidateConnector(),
        )[0]

        self.assertEqual(candidate["make"], "Chevrolet")
        self.assertEqual(candidate["label"], "1999 Chevrolet Silverado 1500 2WD 5.3L")
        guide = compose_illustrated_guide(
            "oil pump replacement",
            {**candidate, "label": "1999 For A Chevrolet Silverado 1500 2WD 5.3L"},
            [],
        )
        self.assertEqual(guide["applicability"], "1999 Chevrolet Silverado 1500 2WD 5.3L")

    def test_vehicle_candidates_keep_provider_identity_separate(self):
        candidate = vehicle_candidates_from_banktwo("1997 Toyota RAV4 oil pump", connector=FakeConnector())[0]
        self.assertEqual(candidate["autoapitwo_vehicle_id"], "vehicle-41215")
        self.assertNotEqual(candidate["vehicle_id"], "vehicle-41215")

    def test_vehicle_resolution_keeps_all_ambiguous_opaque_candidates(self):
        class AmbiguousConnector:
            def resolve_vehicle(self, _selector):
                return SimpleNamespace(body={"candidates": [
                    {"opaque_ref": "rav4-2wd", "label": "1997 Toyota RAV4 2WD", "confidence": 0.9},
                    {"opaque_ref": "rav4-4wd", "label": "1997 Toyota RAV4 4WD", "confidence": 0.9},
                ]})

        candidates = vehicle_candidates_from_banktwo(
            "1997 Toyota RAV4 oil pump", connector=AmbiguousConnector()
        )
        self.assertEqual([item["autoapitwo_vehicle_id"] for item in candidates], ["rav4-2wd", "rav4-4wd"])
        self.assertEqual(len({item["candidate_key"] for item in candidates}), 2)

    def test_retrieval_selects_procedure_pairs_and_composer_keeps_figures(self):
        articles = retrieve_banktwo_articles(
            "1997 Toyota RAV4 oil pump and water pump replacement",
            {"year": 1997, "make": "Toyota", "model": "RAV4", "autoapitwo_vehicle_id": "vehicle-41215"},
            connector=FakeConnector(),
        )
        guide = compose_illustrated_guide("oil pump and water pump replacement", {"year": 1997, "make": "Toyota", "model": "RAV4"}, articles)
        self.assertEqual(guide["content_status"], "complete")
        self.assertTrue(guide["pdf_ready"])
        images = [image for step in guide["steps"] for image in step["images"]]
        self.assertEqual(images[0]["asset_resource_ref"], "asset-oil-opaque")
        self.assertNotIn("url", images[0])
        self.assertEqual(len({step["sequence"] for step in guide["steps"]}), len(guide["steps"]))
        self.assertNotIn("source says", str(guide).casefold())

    def test_missing_installation_is_an_actionable_preview(self):
        connector = FakeConnector()
        connector.articles.pop("water-install")
        articles = retrieve_banktwo_articles(
            "water pump replacement", {"year": 1997, "make": "Toyota", "model": "RAV4", "autoapitwo_vehicle_id": "vehicle-41215"}, connector=connector
        )
        guide = compose_illustrated_guide("water pump replacement", {"year": 1997, "make": "Toyota", "model": "RAV4"}, articles)
        self.assertEqual(guide["content_status"], "partial")
        self.assertFalse(guide["pdf_ready"])
        self.assertIn("missing_installation:water_pump", guide["gaps"])

    def test_combined_removal_and_installation_article_covers_both_phases(self):
        connector = CombinedProcedureConnector()
        articles = retrieve_banktwo_articles(
            "starter replacement",
            {"year": 1997, "make": "Toyota", "model": "RAV4", "autoapitwo_vehicle_id": "vehicle-41215"},
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
        articles = retrieve_banktwo_articles(
            "starter replacement",
            {"year": 1997, "make": "Toyota", "model": "RAV4", "autoapitwo_vehicle_id": "vehicle-41215"},
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
