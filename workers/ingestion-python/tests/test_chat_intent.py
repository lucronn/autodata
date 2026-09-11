import importlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


RAV4_2WD = {
    "vehicle_id": "rav4-2wd",
    "year": 1997,
    "make": "Toyota",
    "model": "RAV4",
    "drivetrain": "2WD",
    "confidence": 0.81,
}
RAV4_4WD = {
    "vehicle_id": "rav4-4wd",
    "year": 1997,
    "make": "Toyota",
    "model": "RAV4",
    "drivetrain": "4WD",
    "confidence": 0.92,
}


def _module():
    spec = importlib.util.find_spec("autodata_ingestion.chat_intent")
    assert spec is not None, "chat intent module must exist"
    return importlib.import_module("autodata_ingestion.chat_intent")


def test_interprets_structured_brake_line_replacement_procedure_and_quote():
    module = _module()

    result = module.interpret_chat_message(
        "97 Toyota RAV4 brake line replacement procedure, and quote",
        (RAV4_2WD,),
    )

    assert result.vehicle_observation["year"] == 1997
    assert result.vehicle_observation["make"] == "Toyota"
    assert result.vehicle_observation["model"] == "RAV4"
    assert result.requested_operations == (
        {
            "operation_id": "replace-brake-line",
            "action": "replace",
            "component": "brake_line",
            "status": "matched",
            "source": "deterministic",
        },
    )
    assert result.quote_requested is True
    assert result.procedure_requested is True
    assert result.clarification is None


def test_normalizes_component_and_operation_spelling_variants():
    module = _module()

    result = module.interpret_chat_message(
        "1997 toyota rav-4 need a brakeline replacment",
        (RAV4_2WD,),
    )

    assert result.requested_operations == (
        {
            "operation_id": "replace-brake-line",
            "action": "replace",
            "component": "brake_line",
            "status": "matched",
            "source": "deterministic",
        },
    )


def test_interprets_multiple_component_operations_in_message_order():
    module = _module()

    result = module.interpret_chat_message(
        "97 Toyota RAV4 replace the oil pump and water pump",
        (RAV4_2WD,),
    )

    assert [operation["component"] for operation in result.requested_operations] == [
        "oil_pump",
        "water_pump",
    ]
    assert [operation["operation_id"] for operation in result.requested_operations] == [
        "replace-oil-pump",
        "replace-water-pump",
    ]


def test_preserves_quote_only_and_procedure_only_requests_without_operations():
    module = _module()

    quote = module.interpret_chat_message("97 Toyota RAV4 quote", (RAV4_2WD,))
    procedure = module.interpret_chat_message("97 Toyota RAV4 procedure", (RAV4_2WD,))

    assert quote.requested_operations == ()
    assert quote.quote_requested is True
    assert quote.procedure_requested is False
    assert procedure.requested_operations == ()
    assert procedure.quote_requested is False
    assert procedure.procedure_requested is True


def test_requests_component_clarification_when_none_is_identifiable():
    module = _module()

    result = module.interpret_chat_message("97 Toyota RAV4 please help", (RAV4_2WD,))

    assert result.requested_operations == ()
    assert result.clarification == "Which component needs service?"


def test_returns_stable_vehicle_options_with_preserved_confidence_and_one_question():
    module = _module()

    result = module.interpret_chat_message("97 Toyota RAV4 brake line replacement", (RAV4_4WD, RAV4_2WD))

    assert result.vehicle_observation["status"] == "ambiguous"
    assert [option["vehicle_id"] for option in result.vehicle_observation["candidates"]] == [
        "rav4-2wd",
        "rav4-4wd",
    ]
    assert [option["confidence"] for option in result.vehicle_observation["candidates"]] == [0.81, 0.92]
    assert result.clarification == "Which RAV4 configuration should I use?"


def test_unambiguous_vehicle_has_no_clarification():
    module = _module()

    result = module.interpret_chat_message("97 Toyota RAV4 4x4 brake line replacement", (RAV4_2WD, RAV4_4WD))

    assert result.vehicle_observation["status"] == "matched"
    assert result.vehicle_observation["selected_vehicle_id"] == "rav4-4wd"
    assert result.clarification is None


def test_mercury_proposal_is_constrained_to_candidates_and_allowlisted_components():
    module = _module()

    class FakeMercury:
        def complete_json(self, prompt):
            self.prompt = json.loads(prompt)
            return {"components": ["brake_line", "made_up_component"], "selected_candidate_key": "not-a-candidate"}

    mercury = FakeMercury()
    result = module.interpret_chat_message("97 Toyota RAV4 need service", (RAV4_2WD,), mercury_client=mercury)

    assert mercury.prompt["allowed_components"] == ["alternator", "battery", "brake_caliper", "brake_line", "brake_pads", "brake_rotor", "brakes", "oil_pump", "power_steering_pump", "starter", "timing_belt", "water_pump"]
    assert mercury.prompt["vehicle_candidates"][0]["vehicle_id"] == "rav4-2wd"
    assert result.requested_operations == (
        {
            "operation_id": "replace-brake-line",
            "action": "replace",
            "component": "brake_line",
            "status": "needs_review",
            "source": "mercury2_advisory",
        },
    )
    assert result.vehicle_observation["status"] == "needs_review"


def test_derives_source_and_rule_backed_support_operations_and_keeps_advisories_unknown():
    module = _module()

    result = module.derive_supporting_operations(
        ({"operation_id": "replace-brake-line", "component": "brake_line"},),
        (
            {
                "article_id": "P:brake-line",
                "supporting_operations": [
                    {"operation_id": "bleed-brakes", "action": "Bleed brakes", "classification": "required"},
                ],
            },
            {
                "article_id": "R:brake-line",
                "trusted_rules": [
                    {"operation_id": "inspect-hoses", "action": "Inspect hoses", "classification": "recommended"},
                ],
            },
            {
                "article_id": "M:brake-line",
                "model_suggestions": [
                    {"operation_id": "replace-master-cylinder", "action": "Replace master cylinder", "classification": "required"},
                ],
            },
        ),
    )

    assert result == (
        {
            "operation_id": "bleed-brakes",
            "action": "Bleed brakes",
            "category": "required",
            "basis": "source_article",
            "source_article_ids": ["P:brake-line"],
        },
        {
            "operation_id": "inspect-hoses",
            "action": "Inspect hoses",
            "category": "recommended",
            "basis": "trusted_rule",
            "source_article_ids": ["R:brake-line"],
        },
        {
            "operation_id": "replace-master-cylinder",
            "action": "Replace master cylinder",
            "category": "needs_review",
            "basis": "model_advisory",
            "source_article_ids": ["M:brake-line"],
        },
    )
