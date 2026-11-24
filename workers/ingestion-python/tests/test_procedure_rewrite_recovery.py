from copy import deepcopy
import json

import pytest

from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_auto import build_auto_prompt
from autodata_ingestion.procedure_rewrite_recovery import (
    FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD,
    FIRST_DRAFT_RECOVERY_METHOD,
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
    "Position the bracket and install the 3 bolts finger tight before lowering it.",
    "Tighten the 3 return bracket nuts to 8 N·m.",
    "Tighten the 1 nut.",
])
def test_directive_recovery_leaves_conditional_or_unrecognized_forms_unedited(original):
    assert _equivalent_directive(original) is None


def test_directive_recovery_rejects_an_unbound_introduction_and_misaligned_rows():
    source = document("Tighten the 3 return bracket nuts.")
    raw = response("Tighten the 4 return bracket nuts.", introduction="Apply 18 N·m as instructed.")
    version = json.loads(build_auto_prompt(source, context={}))["prompt_version"]
    assert recover_first_draft(source, raw, prompt_version=version) is None
    raw["introduction"] = "This procedure describes the fastener work."
    raw["replacements"][0]["block_id"] = "unrelated-block"
    assert recover_first_draft(source, raw, prompt_version=version) is None
