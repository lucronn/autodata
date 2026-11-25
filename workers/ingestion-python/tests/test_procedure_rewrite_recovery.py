from copy import deepcopy
import json

import pytest

from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_auto import build_auto_prompt
from autodata_ingestion.procedure_rewrite_recovery import (
    FIRST_DRAFT_COOLING_RECOVERY_METHOD,
    FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD,
    FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD,
    FIRST_DRAFT_RECOVERY_METHOD,
    FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD,
    _equivalent_cooling_directive,
    _equivalent_directive,
    _equivalent_wording,
    recover_first_draft,
)
from test_procedure_rewrite_full import document, response


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
