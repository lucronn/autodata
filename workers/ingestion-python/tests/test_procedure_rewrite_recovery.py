from copy import deepcopy
import json

import pytest

from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.bankone_brake_recovery import recast_brake_applicability, recast_reservoir_filling
from autodata_ingestion.procedure_rewrite_auto import build_auto_prompt, render_auto
from autodata_ingestion.procedure_rewrite_cooling_recovery import recast_cooling_passage
from autodata_ingestion.procedure_rewrite_diagnostic_recovery import recast_diagnostic_passage
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.procedure_rewrite_maintenance_recovery import recast_maintenance_passage
from autodata_ingestion.procedure_rewrite_recovery import (
    FIRST_DRAFT_BRAKE_APPLICABILITY_RECOVERY_METHOD,
    FIRST_DRAFT_COOLING_RECOVERY_METHOD,
    FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD,
    FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD,
    FIRST_DRAFT_DIAGNOSTIC_RECOVERY_METHOD,
    FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD,
    FIRST_DRAFT_INTRODUCTION_RECOVERY_METHOD,
    FIRST_DRAFT_MAINTENANCE_RECOVERY_METHOD,
    FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD,
    FIRST_DRAFT_RECOVERY_METHOD,
    FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD,
    FIRST_DRAFT_RESERVOIR_FILLING_RECOVERY_METHOD,
    NEUTRAL_INTRODUCTION,
    _equivalent_cooling_directive,
    _equivalent_directive,
    _equivalent_wording,
    _recast_compound_removal,
    recover_archived_first_draft,
    recover_first_draft,
)
from test_procedure_rewrite_full import document, response


@pytest.mark.parametrize(("modal", "strength"), (("should", "recommended"), ("must", "required")))
def test_brake_applicability_recast_keeps_either_condition_and_modality(modal, strength):
    scope = (
        f"This process {modal} be followed whenever the rear brake rotors are resurfaced or replaced, "
        "and/or whenever the rear brake pads are replaced."
    )
    assert recast_brake_applicability(scope) == (
        f"This procedure is {strength} after rear brake rotor resurfacing or replacement, "
        "after rear brake pad replacement, or after both kinds of work."
    )
    assert recast_brake_applicability(scope.replace("and/or", "and")) is None
    assert recast_brake_applicability(scope[:-1] + " unless the vehicle is stationary.") is None


def test_archived_brake_applicability_repairs_only_the_rejected_intro_and_scope():
    scope = (
        "This process should be followed whenever the rear brake rotors are resurfaced or replaced, "
        "and/or whenever the rear brake pads are replaced."
    )
    specification = "Tighten the sample bracket bolt to 18 N·m."
    source = document(scope, specification)
    raw = response(
        scope.replace("be followed", "be carried out"),
        specification,
        introduction="This article covers the 18 N·m specification.",
    )
    raw["replacements"][1].update(action="retain", reason="Keep the exact bolt torque.")
    saved = deepcopy(raw)
    guard = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    method = FIRST_DRAFT_BRAKE_APPLICABILITY_RECOVERY_METHOD
    result = recover_first_draft(source, raw, prompt_version=guard, method=method)
    assert result is not None and result.error_code is None
    assert raw == saved
    assert result.response["introduction"] == NEUTRAL_INTRODUCTION
    assert result.response["replacements"][0]["text"] == recast_brake_applicability(scope)
    assert result.response["replacements"][1:] == saved["replacements"][1:]
    assert result.evidence["corrected_paths"] == ["/blocks/0/text"] and result.evidence["introduction_replaced"]
    attempt = {"response": saved, "guard_version": guard, "error_code": "REWRITE_SPEC_SCOPE_MUTATION",
               "rewrite_attempt_id": "fixture-attempt", "prompt_hash": "fixture-prompt"}
    archived = recover_archived_first_draft(source, attempt, method=method, expected_hash=result.evidence["output_hash"])
    assert archived.response == result.response and archived.evidence["first_draft_recovery"] == result.evidence

    unsafe = deepcopy(saved)
    unsafe["replacements"][1].update(action="rewrite", text=specification.replace("18", "19"), reason="")
    assert recover_first_draft(source, unsafe, prompt_version=guard, method=method) is None


def test_reservoir_filling_recovery_keeps_conditions_and_step_order():
    level_check = "If the hydraulic fluid level is at or below the half-full point during routine fluid checks"
    fill_limit = "the hydraulic fluid may be topped-off up to the maximum-fill level."
    items = [
        f"{level_check}, the clutch system should be inspected for wear and possible hydraulic fluid leaks.",
        f"{level_check}, and an inspection of the clutch system did not reveal wear or hydraulic fluid leaks, {fill_limit}",
        f"If clutch system service was just completed, {fill_limit}",
        "If the hydraulic fluid level is above the half-full point, adding hydraulic fluid is not recommended under normal conditions.",
        "If hydraulic fluid is to be added to the clutch master reservoir, clean the outside of the reservoir "
        "on and around the reservoir cap prior to removing the cap and diaphragm.",
    ]
    expected = [
        "A routine fluid check showing a hydraulic fluid level of half-full or less calls for inspecting "
        "the clutch system for wear and possible fluid leaks.",
        "During a routine fluid check, a level of half-full or less permits topping up the hydraulic fluid "
        "to the maximum-fill level once an inspection finds the clutch system free of wear and hydraulic fluid leaks.",
        "You may bring the hydraulic fluid up to its maximum-fill level immediately after completing service on the clutch system.",
        "Under normal conditions, topping up is discouraged when the hydraulic fluid stands higher than half-full.",
        "To prepare the clutch master reservoir for added hydraulic fluid, clean its outside at the cap "
        "and around it prior to removing the cap and diaphragm.",
    ]
    specification = "Tighten the fixture bracket screw to 27 N·m."
    source = document("", specification)
    numbered_steps = source["blocks"][0]
    numbered_steps.pop("text")
    numbered_steps.update(type="ordered_list", items=items)
    raw = {
        "introduction": NEUTRAL_INTRODUCTION,
        "replacements": [
            {"block_id": slot["block_id"], "path": slot["path"], "action": "rewrite",
             "text": slot["text"].replace("If", "When", 1), "reason": ""}
            for slot in prose_slots(source)
        ],
    }
    raw["replacements"][-1].update(action="retain", reason="Keep the specified value.")
    saved = deepcopy(raw)
    guard = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    method = FIRST_DRAFT_RESERVOIR_FILLING_RECOVERY_METHOD
    candidate = recover_first_draft(source, raw, prompt_version=guard, method=method)
    assert candidate is not None and candidate.error_code is None
    assert raw == saved
    assert candidate.response["introduction"] == raw["introduction"]
    assert [entry["text"] for entry in candidate.response["replacements"][:-1]] == expected
    assert candidate.response["replacements"][-1] == raw["replacements"][-1]
    assert candidate.evidence["corrected_paths"] == [f"/blocks/0/items/{index}" for index in range(len(items))]
    attempt = {"response": saved, "guard_version": guard, "error_code": "REWRITE_PROSE_TOO_SIMILAR",
               "rewrite_attempt_id": "fixture-attempt", "prompt_hash": "fixture-prompt"}
    archive = recover_archived_first_draft(source, attempt, method=method, expected_hash=candidate.evidence["output_hash"])
    assert archive.response == candidate.response

    assert recast_reservoir_filling(items[0].replace("at or below", "below")) is None
    assert recast_reservoir_filling(items[1].replace("or hydraulic fluid leaks", "but did reveal hydraulic fluid leaks")) is None
    assert recast_reservoir_filling(items[2].replace("may", "must")) is None
    assert recast_reservoir_filling(items[3].replace("normal", "abnormal")) is None
    assert recast_reservoir_filling(items[4].replace("prior to", "after")) is None
    unsafe = deepcopy(raw)
    unsafe["replacements"][-1].update(action="rewrite", reason="", text=specification.replace("27", "28"))
    assert recover_first_draft(source, unsafe, prompt_version=guard, method=method) is None


def test_diagnostic_recovery_preserves_conditions_readings_and_referrals():
    source = document(
        "If the unit is equipped with a cabin HVAC system, "
        "go into the HVAC data with the scan tool and get the following readings:",
        "Note: Technicians should always be prepared to provide Service Record 19 or Sheet A when calling into OEM TAC.",
        "The protective cover prevents dirt from entering the sensor connector.",
        "Tighten the bracket bolt to 12 Nm.",
    )
    readings = {
        "block_id": "scanned-readings", "source_order": 2, "type": "ordered_list",
        "items": ["A/C compressor duty cycle", "Humidity", "Outside temperature", "Inside temperature sensor reading"],
        "evidence_ids": ["fixture-evidence"],
    }
    source["blocks"].insert(1, readings)
    for order, block in enumerate(source["blocks"], start=1):
        block["source_order"] = order
    updates = {"/blocks/3/text": "Dirt stays out of the sensor connector because of the protective cover."}
    raw = {
        "introduction": "This article describes the service information.",
        "replacements": [
            {"block_id": slot["block_id"], "path": slot["path"], "action": "rewrite",
             "text": updates.get(slot["path"], slot["text"]), "reason": ""}
            for slot in prose_slots(source)
        ],
    }
    raw["replacements"][-1].update(action="retain", reason="Preserve the torque specification.")
    saved = deepcopy(raw)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    method = FIRST_DRAFT_DIAGNOSTIC_RECOVERY_METHOD
    result = recover_first_draft(source, raw, prompt_version=version, method=method)
    assert result is not None
    assert raw == saved and result.response["replacements"][-2:] == saved["replacements"][-2:]
    assert result.evidence["corrected_paths"] == [row["path"] for row in saved["replacements"][:-2]]
    assert result.evidence["original_error_code"] == "REWRITE_UNCHANGED"
    assert [row["text"] for row in result.response["replacements"][:-2]] == [
        "If the unit is equipped with a cabin HVAC system, use the scan tool to open the HVAC data "
        "and collect the readings listed below:",
        "Duty cycle of the A/C compressor", "Moisture in the air", "Temperature measured outside",
        "Reading from the sensor for the inside temperature",
        "Note: When calling into OEM TAC, technicians should always have Service Record 19 or Sheet A ready to provide.",
    ]
    archived = recover_archived_first_draft(source, {
        "guard_version": version, "response": saved, "error_code": "REWRITE_UNCHANGED",
        "rewrite_attempt_id": "fixture-attempt", "prompt_hash": "fixture-prompt",
    }, method=method, expected_hash=result.evidence["output_hash"])
    assert archived.evidence["first_draft_recovery"] == result.evidence

    unsafe = deepcopy(saved)
    unsafe["replacements"][-1].update(action="rewrite", text="Tighten the bracket bolt to 13 Nm.", reason="")
    assert recover_first_draft(source, unsafe, prompt_version=version, method=method) is None


@pytest.mark.parametrize(("text", "reading"), [
    ("Humidity", False),
    ("Outside temperature above 30 °C", True),
    ("Note: Sam should always be prepared to provide Form 2 when calling into OEM TAC.", False),
    ("If the vehicle is equipped with HVAC, go into the HVAC data with the scan tool and log errors.", False),
])
def test_diagnostic_recovery_leaves_other_source_forms_to_the_existing_checks(text, reading):
    assert recast_diagnostic_passage(text, reading=reading) is None


def test_ambiguous_introduction_can_be_recovered_without_changing_the_saved_body():
    source = document("The acoustic insulation softens vibration from the ventilation system.")
    raw = response(
        "Vibration from the ventilation unit is damped by the acoustic insulation.",
        introduction="This article describes the service information for an area of 25 mm².",
    )
    saved = deepcopy(raw)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    with pytest.raises(ValueError, match="^REWRITE_TECHNICAL_AMBIGUOUS$"):
        render_auto(source, raw, prompt_version=version)

    result = recover_first_draft(source, raw, prompt_version=version)
    assert raw == saved
    assert result.response == {**saved, "introduction": NEUTRAL_INTRODUCTION}
    assert result.evidence["method"] == FIRST_DRAFT_INTRODUCTION_RECOVERY_METHOD
    assert result.evidence["introduction_replaced"] is True
    assert result.evidence["corrected_paths"] == []
    assert result.evidence["raw_response_hash"] == digest_json(saved)
    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_MAINTENANCE_RECOVERY_METHOD,
    ) is None

    archived = recover_archived_first_draft(source, {
        "guard_version": version, "response": saved, "error_code": "REWRITE_TECHNICAL_AMBIGUOUS",
        "rewrite_attempt_id": "fixture-attempt", "prompt_hash": "fixture-prompt",
    }, method=result.evidence["method"], expected_hash=result.evidence["output_hash"])
    assert archived.evidence["first_draft_recovery"] == result.evidence
    assert archived.response == result.response

    ambiguous_body = document("Area is 25 mm².")
    still_ambiguous = response("The area equals 25 mm².", introduction=saved["introduction"])
    assert recover_first_draft(ambiguous_body, still_ambiguous, prompt_version=version) is None


def test_maintenance_recovery_rebuilds_the_original_procedure_from_its_saved_draft():
    source = document(
        "Document ID: 8723",
        "Note: Ensure that the used reservoir seal has been removed.",
        "Retainer Clip(18) » Remove [2x]",
        "Install the access plug. (15) » Install",
        "Remove and discard the reservoir seal. (14)",
        "Lubricate the pump seal with clean machine oil.",
        "Pre-fill the new hydraulic filter (34) with clean machine oil. Adhesives, Fluids, Lubricants, and Sealers",
        "Approximate Fluid Capacities",
        "Start the pump and inspect for leaks.",
    )
    raw = response(
        "Guide number 8724 covers the service procedure.",
        "Note: The used reservoir seal is already clear.",
        "Retainer Clip(18) » Remove [2x]",
        "Install the access plug. (15) » Install",
        "Remove and discard the reservoir seal. (14)",
        "Apply clean machine oil to the flange.",
        "Pre-fill the new hydraulic filter (34) with clean machine oil. Adhesives, Fluids, Lubricants, and Sealers",
        "Approximate Fluid Capacities",
        "Inspect for leaks before starting the pump.",
        introduction="This article describes the service procedure.",
    )
    saved = deepcopy(raw)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    result = recover_first_draft(source, raw, prompt_version=version)

    assert raw == saved
    assert result.evidence["method"] == FIRST_DRAFT_MAINTENANCE_RECOVERY_METHOD
    assert result.evidence["original_error_code"] == "REWRITE_TECHNICAL_MUTATION"
    assert result.evidence["raw_response_hash"] == digest_json(saved)
    assert [row["text"] for row in result.response["replacements"]] == [
        "ID of this document: 8723",
        "Note: Confirm the removal of the used reservoir seal.",
        "Remove Retainer Clip(18) [2x]",
        "The access plug must be installed. (15) » Install",
        "The reservoir seal must be removed and discarded. (14)",
        "The pump seal must be lubricated with clean machine oil.",
        "With clean machine oil, pre-fill the new hydraulic filter (34). "
        "Reference for fluids and lubricants, plus adhesives and sealers.",
        "Estimated capacities for fluids",
        "The pump must be started. Then inspect for leaks.",
    ]
    archived = recover_archived_first_draft(source, {
        "guard_version": version, "response": saved, "error_code": "REWRITE_TECHNICAL_MUTATION",
        "rewrite_attempt_id": "fixture-attempt", "prompt_hash": "fixture-prompt",
    }, method=result.evidence["method"], expected_hash=result.evidence["output_hash"])
    assert archived.evidence["first_draft_recovery"] == result.evidence
    assert archived.response == result.response
    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD,
    ) is None


@pytest.mark.parametrize("instruction", [
    "Lubricate the seal with clean machine oil only after fitting the cover.",
    "Lubricate the seal with clean machine oil or service grease.",
    "Start the pump and inspect for leaks before resetting the controller.",
    "Remove and discard the seal only if damaged. (14)",
    "Install the access plug. (15) » Remove",
    "Retainer Clip(18) » Remove [2x] and inspect",
])
def test_maintenance_recovery_leaves_conditions_and_conflicting_actions_unedited(instruction):
    assert recast_maintenance_passage(instruction) is None


def test_maintenance_recovery_does_not_accept_another_changed_specification():
    source = document("Lubricate the pump seal with clean machine oil.", "Tighten the clamp to 12 N·m.")
    raw = response(
        "Apply clean machine oil to the flange.", "Tighten the clamp to 13 N·m.",
        introduction="This article describes the service procedure.",
    )
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_MAINTENANCE_RECOVERY_METHOD,
    ) is None


@pytest.mark.parametrize(("original", "expected"), [
    ("Remove the left-side access cover.", "The left-side access cover must be removed."),
    ("NOTE: The clip is removed for clarity. Remove the rear panel.",
     "NOTE: For clarity, the clip is removed. The rear panel must be removed."),
    ("Ensure that the drain plug (8) has been removed.", "Confirm the removal of the drain plug (8)."),
    ("Mounting Bracket(32)»Install", "Install Mounting Bracket(32)."),
    ("Install a new cartridge and tighten 1/2 to 2 full turn after the gasket makes contact with the "
     "seating surface on the cartridge holder.(42)",
     "Fit a new cartridge. After the seating surface on the cartridge holder comes into contact "
     "with the gasket, tighten 1/2 to 2 full turn.(42)"),
    ("Oil Filter", "Filter for the oil"),
])
def test_equivalent_wording_keeps_source_parts_conditions_and_references(original, expected):
    assert _equivalent_wording(original) == expected


@pytest.mark.parametrize("original", [
    "Remove the panel only when the vehicle is supported.",
    "Remove the upper cover and disconnect the fitting.",
    "Do not remove the left cover.",
    "NOTE: The clip is removed for service. Remove the rear panel.",
    "Install a new cartridge and tighten 5 N·m before the gasket makes contact with the "
    "seating surface on the cartridge holder.",
    "Mounting Bracket(32)»Install or inspect",
])
def test_equivalent_wording_leaves_unrecognized_passages_to_the_original_checks(original):
    assert _equivalent_wording(original) is None


def test_first_draft_recovers_an_echo_with_the_saved_reply_unchanged():
    source = document("Remove the left-side shield.", "Tighten the bolts to 25 Nm.")
    raw = response("Remove the left-side shield.", "Tighten the bolts to 25 Nm.")
    raw["replacements"][1].update(action="retain", reason="Preserve the torque value.")
    saved = deepcopy(raw)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]

    result = recover_first_draft(source, raw, prompt_version=version)

    assert raw == saved
    assert result.evidence["method"] == FIRST_DRAFT_RECOVERY_METHOD
    assert result.evidence["original_error_code"] == "REWRITE_UNCHANGED"
    assert result.evidence["raw_response_hash"] == digest_json(saved)
    assert result.evidence["draft_hash"] == digest_json(result.response)
    assert result.evidence["output_hash"] == digest_json(result.document)
    assert result.evidence["corrected_paths"] == [raw["replacements"][0]["path"]]
    assert result.response["replacements"][0]["text"] == "The left-side shield must be removed."
    assert result.response["replacements"][1] == raw["replacements"][1]


@pytest.mark.parametrize("unsafe", [
    "Tighten the bolts to 20 Nm.",
    "Loosen the bolts to 25 Nm.",
])
def test_first_draft_cannot_hide_a_second_row_failure_behind_a_copied_row(unsafe):
    source = document("Remove the cover.", "Tighten the bolts to 25 Nm.")
    raw = response("Remove the cover.", unsafe)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    assert recover_first_draft(source, raw, prompt_version=version) is None


def test_first_draft_keeps_a_retention_decision_for_the_normal_validator():
    source = document("Remove the cover.")
    raw = response("Remove the cover.")
    raw["replacements"][0].update(action="retain", reason="Preserve the wording.")
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    assert recover_first_draft(source, raw, prompt_version=version) is None


def test_recovers_installation_directives_without_reusing_the_model_mutations():
    source = document(
        "Install a new reservoir gasket and spacer.",
        "Install the mounting ring and the bolts.",
        "Position the bracket and install the 3 bolts finger tight.",
        "Install the outlet shield. For additional information, refer to Section 410-07C .",
        "Install the return duct. For additional information, refer to Duct Routing in this section.",
        "Tighten the 3 return bracket nuts.",
    )
    raw = response(
        "Put in a new reservoir gasket and spacer.",
        "Place the mounting ring and the bolts.",
        "Position the bracket and install the 4 bolts finger tight.",
        "Put the outlet shield in place. Consult Section 310-07C.",
        "Put the return duct in place and see the next section.",
        "Tighten the 3 return bracket nuts.",
        introduction="This procedure covers the assembly instructions.",
    )
    preserved = deepcopy(raw)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    result = recover_first_draft(source, raw, prompt_version=version)

    assert result is not None
    assert [row["text"] for row in result.response["replacements"]] == [
        "A new reservoir gasket and spacer must be installed.",
        "The mounting ring and the bolts must be installed.",
        "Bring the bracket into position. Install the 3 bolts finger tight.",
        "Fit the outlet shield. Details are in Section 410-07C.",
        "Fit the return duct. See Duct Routing in this section for details.",
        "Tighten each of the 3 return bracket nuts.",
    ]
    assert raw == preserved
    assert result.evidence["method"] == FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD
    assert result.evidence["raw_response_hash"] == digest_json(raw)
    assert result.evidence["corrected_paths"] == [row["path"] for row in raw["replacements"]]
    assert recover_first_draft(source, raw, prompt_version=version, method=FIRST_DRAFT_RECOVERY_METHOD) is None
    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD,
    ) == result


@pytest.mark.parametrize("original", [
    "Install the cover only after the adhesive sets.",
    "Install the cover or shim.",
    "Install the seal and tighten the ring.",
    "Install the ring during removal.",
    "Install the captive washer flat side down.",
    "Install the backing plate last.",
    "Install the new bracket only-if fitted.",
    "Position the bracket and install the 3 bolts finger tight before lowering it.",
    "Tighten the 3 return bracket nuts to 8 N·m.",
    "Tighten the 1 nut.",
])
def test_directive_recovery_leaves_conditional_or_unrecognized_forms_unedited(original):
    assert _equivalent_directive(original) is None


def test_earlier_recovery_cannot_rebuild_an_unbound_introduction():
    source = document("Tighten the 3 return bracket nuts.")
    raw = response("Tighten the 4 return bracket nuts.", introduction="Apply 18 N·m as instructed.")
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD,
    ) is None
    recovered = recover_first_draft(source, raw, prompt_version=version)
    assert recovered.evidence["method"] == FIRST_DRAFT_COOLING_RECOVERY_METHOD
    assert recovered.evidence["introduction_replaced"] is True
    assert recovered.response["introduction"] != raw["introduction"]
    assert recovered.response["replacements"][0]["text"] == "Tighten each of the 3 return bracket nuts."


@pytest.mark.parametrize("has_intro_spec", [False, True])
def test_first_draft_restores_bound_open_placement(has_intro_spec):
    source = document("Place the gauge on the open part of the service tray.", "Gauge width: 18 mm.")
    raw = response(
        "Position the gauge on the exposed section of the service tray.",
        "Gauge width: 18 mm.",
        introduction=("The gauge has a width of 18 mm." if has_intro_spec
                      else "This article describes the service information that follows."),
    )
    raw["replacements"][1].update(action="retain", reason="Exact source measurement.")
    saved = deepcopy(raw)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    result = recover_first_draft(source, raw, prompt_version=version)

    assert raw == saved
    assert result.evidence["method"] == FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD
    assert result.evidence["introduction_replaced"] is has_intro_spec
    assert result.evidence["corrected_paths"] == ["/blocks/0/text"]
    assert result.response["replacements"][0]["text"] == "Position the gauge on the open section of the service tray."
    assert result.response["replacements"][1] == raw["replacements"][1]
    assert recover_first_draft(source, raw, prompt_version=version, method=result.evidence["method"]) == result
    assert recover_first_draft(source, raw, prompt_version=version, method=FIRST_DRAFT_COOLING_RECOVERY_METHOD) is None


@pytest.mark.parametrize(("placement", "specification"), [
    ("Position the gauge in the exposed section of the service tray.", "Gauge width: 18 mm."),
    ("Position the gauge on the exposed section of the storage tray.", "Gauge width: 18 mm."),
    ("Position the spacer on the exposed section of the service tray.", "Gauge width: 18 mm."),
    ("Position the gauge on the covered section of the service tray.", "Gauge width: 18 mm."),
    ("Position the gauge on the exposed section of the service tray.", "Gauge width: 19 mm."),
])
def test_first_draft_placement_leaves_unbound_facts_rejected(placement, specification):
    source = document("Place the gauge on the open part of the service tray.", "Gauge width: 18 mm.")
    raw = response(placement, specification, introduction="The gauge has a width of 18 mm.")
    raw["replacements"][1].update(action="retain", reason="Exact source measurement.")
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    assert recover_first_draft(source, raw, prompt_version=version) is None


@pytest.mark.parametrize("has_intro_spec", [False, True])
def test_recovers_unconditional_compound_removal_from_the_source(has_intro_spec):
    instruction = "Remove the shield and the reservoir screen and return tube."
    measurement = "Shield width: 18 mm."
    source = document(instruction, measurement)
    raw = response(
        "Separate the shield from the reservoir screen and return tube.",
        measurement,
        introduction=("The shield has a width of 18 mm." if has_intro_spec
                      else "This article describes the service information that follows."),
    )
    raw["replacements"][1].update(action="retain", reason="Preserve the exact measurement.")
    saved = deepcopy(raw)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]

    result = recover_first_draft(source, raw, prompt_version=version)

    assert raw == saved
    assert result.evidence["method"] == FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD
    assert result.evidence["original_error_code"] == (
        "REWRITE_SPEC_SCOPE_MUTATION" if has_intro_spec else "REWRITE_ACTION_MUTATION"
    )
    assert result.evidence["introduction_replaced"] is has_intro_spec
    assert result.evidence["corrected_paths"] == ["/blocks/0/text"]
    assert result.response["replacements"][0]["text"] == (
        "The shield and the reservoir screen and return tube must be removed."
    )
    assert result.response["replacements"][1] == saved["replacements"][1]
    assert recover_first_draft(source, raw, prompt_version=version, method=result.evidence["method"]) == result
    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD,
    ) is None


@pytest.mark.parametrize(("original", "reply"), [
    ("Remove the shield and the tube only after the tank is drained.", "Set aside the shield and tube."),
    ("Remove the shield and the tube from the reservoir.", "Set aside the shield and tube."),
    ("Remove the shield or the tube.", "Set aside the shield and tube."),
    ("Remove the shield and the tube and discard the gasket.", "Set aside the shield and tube."),
    ("Remove the shield and the tube.", "Install the shield and tube."),
    ("Remove the shield (1) and the tube (2).", "Set aside the shield and tube."),
])
def test_compound_removal_recovery_rejects_qualifiers_and_competing_actions(original, reply):
    assert _recast_compound_removal(original, reply) is None


@pytest.mark.parametrize(("instruction", "advisory"), [
    ("Install the protective cap over the port.", "The protective cap should be installed over the port."),
    ("Tighten the sleeve clamp on the bracket.", "The sleeve clamp should be tightened on the bracket."),
    ("Note: Remove the left-side cover.", "Note: The left-side cover should be removed."),
])
def test_recovers_only_the_modal_in_a_bound_required_action(instruction, advisory):
    source = document(instruction, "Clamp width: 18 mm.")
    raw = response(advisory, "Clamp width: 18 mm.", introduction="This article describes service information.")
    raw["replacements"][1].update(action="retain", reason="Exact source measurement.")
    saved = deepcopy(raw)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    method = FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD

    result = recover_first_draft(source, raw, prompt_version=version, method=method)

    assert raw == saved
    assert result.evidence["method"] == method
    assert result.evidence["original_error_code"] == "REWRITE_REQUIRED_ACTION_WEAKENED"
    assert result.evidence["raw_response_hash"] == digest_json(saved)
    assert result.evidence["corrected_paths"] == ["/blocks/0/text"]
    assert result.response["introduction"] == saved["introduction"]
    assert result.response["replacements"] == [
        {**saved["replacements"][0], "text": advisory.replace("should", "must")}, saved["replacements"][1],
    ]
    assert recover_first_draft(source, raw, prompt_version=version) is None


@pytest.mark.parametrize(("instruction", "advisory"), [
    ("Install the protective cap over the port.", "The dust cap should be installed over the port."),
    ("Install the protective cap over the port.", "The protective cap should be installed on the port."),
    ("Install the protective cap over the port.", "The protective cap over the port should be installed."),
    ("Install the protective cap over the port.", "You should install the port's protective cap."),
    ("Install the protective cap if desired.", "The protective cap should be installed if desired."),
    ("Install the protective cap.", "The protective cap must be installed."),
])
def test_required_action_recovery_leaves_unproved_modal_changes_alone(instruction, advisory):
    source = document(instruction)
    raw = response(advisory, introduction="This article describes service information.")
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]

    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD,
    ) is None


def test_required_action_recovery_never_publishes_a_partly_fixed_draft():
    source = document("Remove the left-side cover.", "Install the protective cap over the port.")
    raw = response(
        "The left-side cover should be removed.",
        "You should install the port's protective cap.",
        introduction="This article describes service information.",
    )
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]

    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD,
    ) is None


def test_cooling_recovery_requires_a_source_aligned_reply():
    source = document("Loosen the mounting plate bolts.")
    raw = response("Remove the mounting plate bolts.")
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    raw["introduction"] = "This procedure describes the fastener work."
    raw["replacements"][0]["block_id"] = "unrelated-block"
    assert recover_first_draft(source, raw, prompt_version=version) is None


def test_recovers_loosen_and_fill_bleed_with_a_source_based_introduction():
    source = document(
        "Loosen the mounting plate bolts.",
        "Fill and bleed the cooling system. For additional information, refer to "
        "Cooling System Draining, Filling and Bleeding in this section.",
    )
    source["blocks"].append({
        "block_id": "heading", "source_order": 3, "type": "heading", "level": 2,
        "text": "Cooling system service", "evidence_ids": ["fixture-evidence"],
    })
    raw = response(
        "Remove the mounting plate bolts.",
        source["blocks"][1]["text"],
        introduction="It is safe to service this system while the engine is running.",
    )
    saved = deepcopy(raw)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    result = recover_first_draft(source, raw, prompt_version=version)

    assert result.evidence["method"] == FIRST_DRAFT_COOLING_RECOVERY_METHOD
    assert result.evidence["introduction_replaced"] is True
    assert result.evidence["raw_response_hash"] == digest_json(raw)
    assert result.evidence["corrected_paths"] == [row["path"] for row in raw["replacements"]]
    assert result.response["introduction"] == "This article covers the service information for Cooling system service."
    assert [row["text"] for row in result.response["replacements"]] == [
        "The mounting plate bolts must be loosened.",
        "Fill the cooling system and bleed it. See Cooling System Draining, Filling and Bleeding "
        "in this section for details.",
    ]
    assert raw == saved
    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_COOLING_RECOVERY_METHOD,
    ) == result
    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD,
    ) is None


@pytest.mark.parametrize("original", [
    "Loosen the mounting plate bolts only after the vehicle is supported.",
    "Loosen the ring and remove it.",
    "Loosen the two clips without detaching them.",
    "Bleed and fill the cooling system. For additional information, refer to "
    "Cooling System Draining, Filling and Bleeding in this section.",
    "Fill and bleed the brake system. For additional information, refer to "
    "Cooling System Draining, Filling and Bleeding in this section.",
])
def test_cooling_recovery_does_not_infer_conditions_sequence_or_system(original):
    assert _equivalent_cooling_directive(original) is None


@pytest.mark.parametrize("original", [
    "Close the valve and discard the seal.",
    "Close the gate without letting go.",
    "Install the plug and select service mode until it contacts the stop.",
    "Repeat Steps 1 through 2 a total of 3 times to remove residue and alert the operator.",
])
def test_cooling_sequence_rejects_extra_clauses_in_a_target(original):
    assert recast_cooling_passage(original, "REWRITE_ACTION_MUTATION") is None


def test_cooling_sequence_recovers_ratio_and_closure_without_touching_passing_rows():
    ratio = "Maximum additive mixture is 7/9 for a cold climate."
    closure = "Close the fixture valve."
    warning = "Warning: Do not release the fitting while the assembly is hot."
    source = document(ratio, closure, "Remove the access cover.", warning)
    raw = response(
        "The additive mixture must not exceed 7/9.",
        "Open the fixture valve.",
        "The access cover must be removed.",
        warning,
        introduction="This article describes the service information that follows.",
    )
    raw["replacements"][3].update(action="retain", reason="Preserve the exact safety wording.")
    saved = deepcopy(raw)
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    method = FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD

    result = recover_first_draft(source, raw, prompt_version=version)

    assert result.evidence["method"] == method
    assert result.evidence["original_error_code"] == "REWRITE_TECHNICAL_MUTATION"
    assert result.evidence["corrected_paths"] == ["/blocks/0/text", "/blocks/1/text"]
    assert result.evidence["raw_response_hash"] == digest_json(saved)
    assert result.evidence["output_hash"] == digest_json(result.document)
    assert raw == saved
    assert result.response["introduction"] == saved["introduction"]
    assert result.response["replacements"][2:] == saved["replacements"][2:]
    assert result.response["replacements"][0]["text"] == (
        "The additive mixture has a maximum of 7/9 for a cold climate."
    )
    assert result.response["replacements"][1]["text"] == "The fixture valve must be closed."
    assert recover_first_draft(source, raw, prompt_version=version, method=method) == result
    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_COOLING_RECOVERY_METHOD,
    ) is None

    for wording, error in (
        ("The additive mixture has a maximum of 7/8 for a cold climate.", "REWRITE_TECHNICAL_MUTATION"),
        ("The additive mixture must not exceed 7/9 for a cold climate.", "REWRITE_SAFETY_MUTATION"),
    ):
        changed = deepcopy(result.response)
        changed["replacements"][0]["text"] = wording
        with pytest.raises(ValueError, match=error):
            render_auto(source, changed, prompt_version=version)


def test_cooling_sequence_refuses_publication_when_an_authored_warning_changes():
    source = document(
        "Maximum additive mixture is 7/9 for a cold climate.",
        "Warning: Do not release the fitting while the assembly is hot.",
    )
    raw = response(
        "The additive mixture must not exceed 7/9.",
        "Warning: Release the fitting while the assembly is hot.",
    )
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]

    assert recover_first_draft(
        source, raw, prompt_version=version, method=FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD,
    ) is None


def test_cooling_sequence_preserves_the_contact_endpoint_and_exact_step_range():
    endpoint = "Install the fixture cap until it contacts the positive stop."
    repetition = "Repeat Steps 2 through 4 a total of 3 times to remove residue from the chamber."
    heading = "Filling and Bleeding with a service adapter"
    source = document(endpoint, repetition, heading)
    raw = response(
        "Remove the fixture cap at the positive stop.",
        "Perform Steps 2 through 4 a total of 3 times to leave residue in the chamber.",
        heading,
        introduction="This article describes the service information that follows.",
    )
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    method = FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD

    result = recover_first_draft(source, raw, prompt_version=version, method=method)

    assert result.evidence["corrected_paths"] == [row["path"] for row in raw["replacements"]]
    assert [row["text"] for row in result.response["replacements"]] == [
        "Install the fixture cap. Continue until it contacts the positive stop.",
        "Remove residue from the chamber by repeating Steps 2 through 4 a total of 3 times.",
        "How to fill and bleed with a service adapter",
    ]

    source["blocks"][0]["text"] = "Install the fixture cap until it contacts the stop only if the seal is cool."
    assert recover_first_draft(source, raw, prompt_version=version, method=method) is None


def test_cooling_sequence_keeps_both_idle_conditions_and_their_observation():
    instruction = (
        "Start the drive motor and let it idle until the chamber temperature reaches operating temperature "
        "and the bypass valve is fully open. A fully open bypass valve is verified by the status lamp "
        "cycling on at least once."
    )
    source = document(instruction)
    raw = response(
        "The drive motor can idle until the chamber reaches its operating temperature.",
        introduction="This article describes the service information that follows.",
    )
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    method = FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD

    result = recover_first_draft(source, raw, prompt_version=version, method=method)

    assert result.evidence["original_error_code"] == "REWRITE_ACTION_MUTATION"
    assert result.response["replacements"][0]["text"] == (
        "Start the drive motor. Keep it idling until both conditions are met: "
        "the chamber temperature has reached operating temperature, and the bypass valve is fully open. "
        "The status lamp cycling on at least once verifies a fully open bypass valve."
    )
    for changed in (
        instruction.replace("and the bypass valve", "or the bypass valve"),
        instruction.replace("A fully open bypass valve", "A fully open drain valve"),
        instruction.replace("at least once", "briefly"),
    ):
        assert recover_first_draft(document(changed), raw, prompt_version=version, method=method) is None
