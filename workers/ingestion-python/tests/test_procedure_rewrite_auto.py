"""Automatic mechanical publication checks; synthetic, not semantic proof."""
from copy import deepcopy
import json

import pytest

from autodata_ingestion import procedure_rewrite as rewrite
from autodata_ingestion.article_lifecycle_types import digest_json
from test_procedure_rewrite_full import document, response, Draft

PROFILE = "full-prose-auto-v1"


def run(source, payload):
    return rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version=PROFILE)


def test_automatic_rewrite_has_own_identity_and_no_manual_acceptance():
    source = document("Remove the cover.", "Tighten the bolts to 25 Nm with tool T-42.")
    payload = response("Take the cover off.", source["blocks"][1]["text"])
    payload["replacements"][1].update(action="retain", reason="Keep the named bolts and tool with their torque.")
    result = run(source, payload)
    assert result.error_code is None
    assert result.profile_version == PROFILE
    report = rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).report
    assert report["passed"] and not report["content_acceptance_required"]
    assert report["publication_mode"] == "automatic"
    assert report["profile_version"] == PROFILE
    assert report["changed_prose_slots"] == ["/blocks/0/text"]
    assert report["retained_paths"] == ["/blocks/1/text"]
    reviewed = rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version="full-prose-review-v1")
    assert reviewed.error_code is None
    assert result.document["blocks"][0]["block_id"] != reviewed.document["blocks"][0]["block_id"]
    assert rewrite.validate_article_rewrite(source, reviewed.document, profile_version="full-prose-review-v1").report["content_acceptance_required"]


@pytest.mark.parametrize("replacement", ["Remove the cover.", " REMOVE  THE COVER. ", "Remove the cover!"])
def test_automatic_profile_rejects_unchanged_ordinary_prose(replacement):
    source = document("Remove the cover.")
    payload = response(replacement)
    if replacement == source["blocks"][0]["text"]:
        payload["replacements"][0].update(action="retain", reason="Keep accurate source instructions")
    result = run(source, payload)
    assert result.error_code == "REWRITE_UNCHANGED"
    assert result.document == source


@pytest.mark.parametrize(("source_text", "replacement"), [
    (
        "After the cap comes off, gently slide the cable from the guide beside the outer bracket.",
        "Once the cap comes off, gently slide the cable from the guide beside the outer bracket.",
    ),
    (
        "Release the latch, slide the cable along the inner guide and lift it out by hand.",
        "Open the clip, slide the cable along the inner guide and lift it out manually.",
    ),
    ("Remove the cap.", "First, remove the cap."),
    ("Remove the cap.", "Remove the cap before proceeding."),
    ("Remove the cap before proceeding.", "Remove the cap."),
])
def test_automatic_profile_rejects_near_verbatim_ordinary_prose(source_text, replacement):
    source = document(source_text)
    result = run(source, response(replacement))
    assert result.error_code == "REWRITE_PROSE_TOO_SIMILAR"
    assert result.document == source


@pytest.mark.parametrize("warning", [
    "Never connect the battery while the connector is wet.",
    "Warning: Wear eye protection during this procedure.",
    "Inspect the cable, but do not connect the battery yet.",
    "The battery cannot be connected while the connector is wet.",
])
def test_automatic_profile_retains_inline_safety_instruction(warning):
    source = document(warning, "Remove the cover.")
    payload = response("Reconnect the battery before drying the connector.", "Take the cover off.")
    assert run(source, payload).error_code == "REWRITE_SAFETY_MUTATION"
    payload["replacements"][0].update(action="retain", text=warning, reason="Exact safety wording")
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == warning


def test_current_and_historical_validation_bind_their_own_prose_rules():
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = document("Remove the cover.")
    payload = response("First, remove the cover.")
    candidate = render_full(source, payload, profile_version=PROFILE)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version="full-prose-auto-prompt-v2")
    assert historical.passed
    assert historical.report["validator_version"] == "full-prose-auto-validator-v1"
    for bound_response in (payload, None):
        current = auto.validate_auto(source, candidate, response=bound_response, prompt_version="full-prose-auto-prompt-v4")
        assert current.error_codes == ("REWRITE_PROSE_TOO_SIMILAR",)
        assert current.report["validator_version"] == "full-prose-auto-validator-v2"


def test_ordinary_text_cannot_be_reduced_to_its_specification():
    source = document("Tighten the bolts to 25 Nm.")
    result = run(source, response("25 Nm."))
    assert result.error_code == "REWRITE_PROSE_MISSING"
    assert result.document == source


def test_automatic_profile_rejects_new_inline_warning_or_prohibition():
    source = document("Remove the cover.")
    for payload in (
        response("Never take the cover off."),
        response("Take the cover off.", introduction="Do not take the cover off."),
    ):
        result = run(source, payload)
        assert result.error_code == "REWRITE_SAFETY_MUTATION"
        assert result.document == source


def test_distinct_prose_preserves_action_order_facts_and_source_blocks():
    source = document(
        "After removing the cover, inspect the cable to check whether the guide is secure.",
        "Use tool T-42 to tighten the cover bolts evenly to 25 Nm after seating the gasket.",
    )
    source["blocks"].extend([
        {"block_id": "warning", "source_order": 3, "type": "callout",
         "text": "Before work, isolate the battery.", "evidence_ids": ["safety-evidence"]},
        {"block_id": "image", "source_order": 4, "type": "image",
         "status": "unavailable", "unavailable_reason": "fixture", "evidence_ids": ["media-evidence"]},
    ])
    replacements = (
        "Take the cover off before checking that the cable guide is firmly attached.",
        source["blocks"][1]["text"],
    )
    payload = response(*replacements)
    payload["replacements"][1].update(action="retain", reason="Keep the gasket condition and the specified torque.")
    result = run(source, payload)
    assert result.error_code is None
    assert [block["source_order"] for block in result.document["blocks"]] == [1, 2, 3, 4, 5]
    for original, rendered, text in zip(source["blocks"][:2], result.document["blocks"][1:3], replacements):
        assert rendered == dict(original, source_order=original["source_order"] + 1, text=text)
    for original, rendered in zip(source["blocks"][2:], result.document["blocks"][3:]):
        assert rendered == dict(original, source_order=original["source_order"] + 1)


@pytest.mark.parametrize("source_text,draft,code", [
    ("Avoid reconnecting the battery while the connector is wet.",
     "Reconnect the battery before drying the connector.", "REWRITE_SAFETY_MUTATION"),
    ("The battery needs to stay disconnected until the connector is dry.",
     "Let the connector dry while the battery is attached.", "REWRITE_SAFETY_MUTATION"),
    ("Tighten the cover to 7 Nm only after the seal sits flush.",
     "Set the cover torque to 7 Nm.", "REWRITE_SAFETY_MUTATION"),
    ("Fit the connector cover unless the harness is damaged.",
     "Install the connector cover.", "REWRITE_SAFETY_MUTATION"),
    ("Disconnect the battery before handling the connector.",
     "Attach the battery ahead of connector service.", "REWRITE_ACTION_MUTATION"),
    ("Tighten the connector cover screws to 7 Nm.",
     "Loosen the connector cover screws until they reach 7 Nm.", "REWRITE_SPEC_SCOPE_MUTATION"),
    ("First disconnect the battery, then remove the connector cover.",
     "Take the connector cover off before detaching the battery.", "REWRITE_ACTION_MUTATION"),
    ("Remove the connector cover.",
     "Take the cover off the connector and start the engine.", "REWRITE_ACTION_MUTATION"),
    ("Check that the guide clips are attached.",
     "Inspect whether the guide clips hold firmly and start the engine.", "REWRITE_ACTION_MUTATION"),
])
def test_automatic_rewrite_rejects_changed_safety_conditions_and_recognizable_actions(source_text, draft, code):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == code
    assert result.document == source


def test_prerequisite_remains_verbatim_when_the_other_steps_are_rewritten():
    condition = "Fit the cover only after the seal sits flush."
    source = document(condition, "Inspect the cable.")
    payload = response(condition, "Check the cable for wear.")
    payload["replacements"][0].update(action="retain", reason="Preserve the seal prerequisite.")
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == condition
    assert result.document["blocks"][2]["text"] == "Check the cable for wear."


def test_automatic_rewrite_checks_actions_bound_to_each_slot():
    source = document("Remove the connector cover.", "Inspect the guide.")
    result = run(source, response("Check the guide visually.", "Take the cover off the connector."))
    assert result.error_code == "REWRITE_ACTION_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("First disconnect the battery, then remove the connector cover.",
     "Once power has been isolated at the battery, take the cover off the connector."),
    ("Tighten the connector cover screws evenly.",
     "For an even fit, tighten each screw on the connector cover."),
    ("Remove the latch cover and inspect the cable.",
     "Check the cable once the latch cover is removed."),
    ("Open the housing before disconnecting the battery.",
     "Detach the battery after opening the housing."),
])
def test_automatic_rewrite_accepts_recognizable_action_paraphrases(source_text, draft):
    result = run(document(source_text), response(draft))
    assert result.error_code is None


@pytest.mark.parametrize("intro", [
    "Start the engine before removing the cover.",
    "This article covers cover access. Then, start the engine.",
    "You should start the engine first.",
    "The engine must be started before this procedure.",
])
def test_automatic_rewrite_rejects_an_imperative_introduction(intro):
    source = document("Remove the connector cover.")
    result = run(source, response("Take the cover off the connector.", introduction=intro))
    assert result.error_code == "REWRITE_INTRODUCTION_INSTRUCTION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Tighten the connector cover screws to 7 Nm.", "Set the torque of the battery mounting screws to 7 Nm."),
    ("Inflate the front left tire to 33 psi.", "Raise the spare tire pressure to 33 psi."),
    ("Tighten the cover screws to 25Nm.", "Tighten the mounting screws to 25Nm."),
    ("Warm the cover to 30–40 °C before testing the seal.",
     "Before testing the seal, warm the housing to 30–40 °C."),
    ("Cool the probe to -25 °C.", "Lower the axle temperature to -25 °C."),
    ("Set the front tire pressure to 30-40 psi.", "Use a range of 30-40 psi for the spare tire."),
    ("Read the gauge in kilopascals after it stabilizes.",
     "Once the needle settles, read the result in pounds per square inch."),
    ("Read the gauge in kilopascals after it stabilizes.",
     "Observe the needle after it settles."),
    ("Read the gauge in psi once it stabilizes.", "Read the needle once it settles."),
    ("Report the measurement using kilopascals.", "Report the measurement using megapascals."),
    ("Use kilopascals rather than pounds per square inch.",
     "Report pressures in pounds per square inch rather than kilopascals."),
])
def test_automatic_rewrite_preserves_full_specification_scope(source_text, draft):
    source = document(source_text, "Inspect the cover.")
    payload = response(draft, "Check the cover for wear.")
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source

    payload["replacements"][0].update(action="retain", text=source_text, reason="Keep the specification and its context.")
    model = Draft(payload)
    result = rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE)
    assert model.prompt["slots"][0]["required_action"] == "retain"
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == source_text
    assert result.document["blocks"][2]["text"] == "Check the cover for wear."


def test_automatic_rewrite_cannot_invent_a_unit_assignment():
    source = document("Read the indicated pressure after the needle settles.")
    result = run(source, response("Read the gauge in kilopascals once it settles."))
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Inspect 2 guides for wear.", "Check the condition of the 2 guides."),
    ("Inspect the guide at step 2.", "At step 2, check the guide for wear."),
    ("In the tray, inspect the filter.", "Check the filter in the tray."),
    ("Spend a few minutes checking the guide.", "Take a moment to inspect the guide."),
    ("Read the odometer once the display settles.", "Once the display settles, note the odometer reading."),
    ("The sensor cable extends for miles along the track.", "The sensor cable follows the track for a long distance."),
    ("The service depot is in Watts.", "Watts is home to the service depot."),
])
def test_scoped_guard_leaves_bare_numbers_and_incidental_units_editable(source_text, draft):
    source = document(source_text)
    model = Draft(response(draft))
    result = rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE)
    assert model.prompt["slots"][0]["required_action"] == "rewrite"
    assert result.error_code is None


def test_introduction_cannot_reassign_an_exact_source_specification():
    source = document("Tighten the connector cover screws to 7 Nm.", "Inspect the cover.")
    payload = response("Tighten the connector cover screws to 7 Nm.", "Check the cover for wear.",
                       introduction="The battery mounting screws require 7 Nm.")
    payload["replacements"][0].update(action="retain", reason="The scope is exact.")
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Remove the left rear splash shield for access.",
     "Take off the splash shield from the right rear to gain access."),
    ("Inspect the left front harness connector.",
     "Check the harness connector at the left rear."),
    ("Disconnect the left sensor and remove the right cover.",
     "Detach the right sensor, then take off the left cover."),
    ("Remove the left-hand wheel-arch liner.",
     "Take off the liner from the wheel arch."),
    ("Open the LH engine bay access panel.",
     "Swing the RH access panel open in the engine bay."),
    ("Inspect the inboard pad and remove the outboard shim.",
     "Check the outboard pad, then take the inboard shim off."),
    ("Remove the left cover first, then remove the right cover.",
     "Take off the right cover before lifting off the left cover."),
    ("Inspect the upper guide and remove the lower bracket.",
     "Check the lower guide, then take off the upper bracket."),
])
def test_automatic_rewrite_rejects_changed_direction_for_each_recognized_action(source_text, draft):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_DIRECTION_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Remove the left rear splash shield for access.",
     "Take off the splash shield from the left rear to gain access."),
    ("Remove the left-hand wheel-arch liner.",
     "Take the liner off the LH wheel arch."),
    ("Inspect the left front harness connector.",
     "Check the front-left connector for the harness."),
    ("Inspect the cover for debris left behind by the gasket.",
     "Check the cover for any debris that remained by the gasket."),
    ("Inspect the rubber pad on the inside face of the door.",
     "Check the pad on the inner face of the door."),
    ("Remove the left cover first, then remove the right cover.",
     "Take off the right cover after lifting off the left cover."),
    ("Disconnect the right harness before removing the left sensor.",
     "Once the right harness is detached, take off the left sensor."),
    ("The guard is on the right side of the housing.",
     "The housing's right-hand side carries the guard."),
    ("Remove the lifting hook after the hoist has left the bay.",
     "Take off the lifting hook once the hoist has departed."),
    ("Lower the spare tire to the ground.", "Bring the spare tire down to the ground."),
])
def test_automatic_rewrite_accepts_equivalent_direction_and_ordinary_prose(source_text, draft):
    result = run(document(source_text), response(draft))
    assert result.error_code is None


@pytest.mark.parametrize("source_text,draft", [
    ("If the seal is not flush, inspect the connector.",
     "Check the connector once the seal is flush."),
    ("Inspect the harness if no moisture is visible.",
     "Check the harness when moisture can be seen."),
    ("For vehicles without an auxiliary battery, inspect the starter connection.",
     "Check the starter connection on vehicles with an auxiliary battery."),
    ("Reconnection is forbidden while the connector is damp.",
     "Restore the electrical connection while the connector is still damp."),
    ("Remove the cover without lifting the cable guide.",
     "Take the cover off after lifting the cable guide."),
    ("Inspect only the connector shell for corrosion.",
     "Check the entire harness for corrosion."),
])
def test_automatic_rewrite_protects_negative_applicability_and_restrictions(source_text, draft):
    source = document(source_text, "Inspect the cover.")
    payload = response(draft, "Check the cover for wear.")
    result = run(source, payload)
    assert result.error_code == "REWRITE_SAFETY_MUTATION"
    assert result.document == source

    payload["replacements"][0].update(action="retain", text=source_text, reason="Keep the full restriction.")
    model = Draft(payload)
    result = rewrite.rewrite_ordered_document(source, client=model, context={}, profile_version=PROFILE)
    assert model.prompt["slots"][0]["required_action"] == "retain"
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == source_text
    assert result.document["blocks"][2]["text"] == "Check the cover for wear."


@pytest.mark.parametrize("source_text,draft", [
    ("The connector cover is supplied without a gasket.",
     "The gasket and connector cover are supplied separately."),
    ("Only the connector shell is supplied with the kit.",
     "The kit contains the connector shell by itself."),
])
def test_automatic_rewrite_keeps_nonprocedural_negative_phrasing_editable(source_text, draft):
    model = Draft(response(draft))
    result = rewrite.rewrite_ordered_document(document(source_text), client=model, context={}, profile_version=PROFILE)
    assert model.prompt["slots"][0]["required_action"] == "rewrite"
    assert result.error_code is None


@pytest.mark.parametrize("draft", [
    ("Remove the cable shield.", "Remove the inlet cover."),
    ("Take off the cable shield.", "Lift off the inlet cover."),
    ("Take the cable shield off.", "Lift the inlet cover off."),
])
def test_automatic_rewrite_rejects_reciprocal_swaps_of_unambiguous_simple_targets(draft):
    source = document("Remove the inlet cover.", "Remove the cable shield.")
    result = run(source, response(*draft))
    assert result.error_code == "REWRITE_COMPONENT_SWAP"
    assert result.document == source


def test_automatic_rewrite_rejects_swapping_brief_unarticled_targets():
    source = document("Remove inlet cover.", "Remove harness shield.")
    result = run(source, response("Take off the harness shield.", "Lift the inlet cover off."))
    assert result.error_code == "REWRITE_COMPONENT_SWAP"
    assert result.document == source


def test_automatic_rewrite_rejects_a_cycle_of_distinct_simple_targets():
    source = document("Remove the inlet cover.", "Remove the cable shield.", "Remove the pump guard.")
    result = run(source, response("Take off the cable shield.", "Take the pump guard off.",
                                  "Lift off the inlet cover."))
    assert result.error_code == "REWRITE_COMPONENT_SWAP"
    assert result.document == source


@pytest.mark.parametrize("source_texts,draft", [
    (("Remove the inlet cover.", "Remove the inlet cover."),
     ("Take off the inlet cover.", "Take off the inlet cover.")),
    (("Remove the inlet cover.", "Remove the cable shield."),
     ("Take the cover off the inlet.", "Take off the wiring shield.")),
    (("Remove the inlet cover.", "Remove the cover from the inlet."),
     ("Take the cover off the inlet.", "Lift off the inlet cover.")),
    (("Remove the inlet cover.", "Remove the cable shield after the latch releases."),
     ("Take the inlet cover off.", "Once the latch releases, take the cable shield off.")),
    (("Inspect the pump casing.", "Check the pump casing."),
     ("Look over and inspect the casing of the pump.", "Visually inspect the casing of the pump.")),
    (("Remove the inlet cover.", "Remove the cable shield.", "Remove the inlet cover."),
     ("Take off the cable shield.", "Lift off the inlet cover.", "Take the inlet cover off.")),
])
def test_automatic_rewrite_keeps_repeat_operations_and_nonliteral_aliases_editable(source_texts, draft):
    result = run(document(*source_texts), response(*draft))
    assert result.error_code is None


@pytest.mark.parametrize("intro", [
    "This procedure applies to diesel models equipped with an auxiliary battery.",
    "No battery isolation is required for this service.",
    "This repair is safe to perform with the engine running.",
    "This procedure restores hydraulic pressure by bleeding the brake lines.",
    "This procedure describes access to the right rear pump cover.",
    "The pump cover procedure is guaranteed to fix the issue.",
])
def test_automatic_rewrite_rejects_unsupported_claims_in_introduction(intro):
    source = document("Remove the pump cover.")
    result = run(source, response("Take the cover off the pump.", introduction=intro))
    assert result.error_code == "REWRITE_INTRODUCTION_UNSUPPORTED_CLAIM"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft,intro", [
    ("Remove the pump cover.", "Take the cover off the pump.",
     "This procedure covers access to the pump by removing its cover."),
    ("Remove the pump cover.", "Take the cover off the pump.", "This article covers pump cover removal."),
    ("Remove the right rear pump cover.", "Take the pump cover off from the right rear.",
     "This procedure describes access to the rear-right pump cover."),
    ("Inspect the brake lines.", "Check the brake lines for wear.",
     "This procedure covers a brake line inspection."),
    ("Inspect the brake lines.", "Check the brake lines for wear.",
     "This section describes checking the brake lines."),
    ("Remove the high-voltage battery cover.", "Take the cover off the high-voltage battery.",
     "This procedure describes gaining access to the high voltage battery."),
])
def test_automatic_rewrite_accepts_coherent_source_bound_introductions(source_text, draft, intro):
    result = run(document(source_text), response(draft, introduction=intro))
    assert result.error_code is None


def test_intro_component_can_be_grounded_in_protected_source_text():
    source = document("Remove the guide bracket.")
    source["blocks"].append({
        "block_id": "s0", "source_order": 2, "type": "callout", "label": "Caution",
        "text": "Protect the brake lines before removing the guide bracket.",
        "evidence_ids": ["fixture-evidence"],
    })
    payload = response("Take off the guide bracket.", introduction="This procedure describes access near the brake line.")
    assert run(source, payload).error_code is None


@pytest.mark.parametrize("source_text,draft", [
    pytest.param("Remove the inlet cover first, then remove the cable shield.",
                 "Take the cable shield off before lifting off the inlet cover.",
                 id="same-action-reversal-explicit-then"),
    pytest.param("Remove the inlet cover. Then remove the cable shield.",
                 "Take the cable shield off first. Lift off the inlet cover next.",
                 id="same-action-reversal-across-sentences"),
    pytest.param("Disconnect the pump lead and remove the inlet cover.",
                 "Detach the inlet cover, then take off the pump lead.",
                 id="verbs-assigned-to-opposite-targets"),
    pytest.param("Inspect the guide bracket and remove the harness shield.",
                 "Check the harness shield, then take the guide bracket off.",
                 id="parallel-distinct-assignments-reversed-with-grammatical-order-unchanged"),
    pytest.param("Inspect the cover after removing the connector.",
                 "After taking off the cover, check the connector.",
                 id="conditional-mixup-retains-both-verb-and-object-words"),
])
def test_automatic_rewrite_rejects_proven_within_leaf_clause_mutation(source_text, draft):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_CLAUSE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    (
        "Remove the inlet cover first, then remove the cable shield.",
        "Lift off the cable shield and take the inlet cover off.",
    ),
    (
        "Inspect the connector shell, then inspect the retaining clip.",
        "Check the connector shell for damage.",
    ),
    (
        "Inspect the connector and seal, then remove the cable shield.",
        "Check the shield before taking off the connector and seal.",
    ),
])
def test_within_leaf_guard_abstains_without_two_exact_bound_targets(source_text, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    assert auto._clause_assignment_changed(source_text, draft) is False


@pytest.mark.parametrize("source_text,draft", [
    pytest.param("Remove the inlet cover first, then remove the cable shield.",
                 "Take the cable shield off after lifting off the inlet cover.",
                 id="same-action-reversal-with-matching-valid-before-after-paraphrase"),
    pytest.param("Remove the inlet cover, reinstall the cover temporarily, then remove the inlet cover again.",
                 "Take off the inlet cover. Fit the cover temporarily, then lift off the inlet cover a second time.",
                 id="same-action-repeated-identical-object-remains-legitimate"),
    pytest.param("Inspect the connector. Inspect the connector again.",
                 "Check the connector, then inspect it a second time.",
                 id="same-action-repeat-across-simple-sentences"),
    pytest.param("Disconnect the pump lead and remove the inlet cover.",
                 "Detach the lead from the pump before taking the cover off the inlet.",
                 id="distinct-different-verb-objects-paraphrased-by-noun-complement"),
    pytest.param("Inspect the connector shell and cover for visible wear.",
                 "Check the cover and connector shell for signs of wear.",
                 id="unordered-shared-verb-noun-phrase"),
    pytest.param("Disconnect the pump lead before removing the inlet cover.",
                 "Once the pump lead is detached, lift off the inlet cover.",
                 id="different-clauses-rendered-via-conditional-grammar"),
    pytest.param("Inspect the inlet cover and the cable shield.",
                 "Check the cable shield and the inlet cover.",
                 id="coordinated-shared-verb-objects-reordered"),
    pytest.param("Inspect the cover for rust and confirm the guide is attached.",
                 "Check the cover for corrosion and inspect the guide for secure attachment.",
                 id="one-directive-paraphrased-with-duplicate-synonym"),
    pytest.param("Inspect the cable shield and inspect the inlet cover.",
                 "Check the inlet cover and check the cable shield.",
                 id="bare-conjunction-does-not-state-an-order-for-inspection"),
    pytest.param("Inspect the cable shield; inspect the inlet cover.",
                 "Check the inlet cover. Also check the cable shield.",
                 id="semicolon-without-explicit-timing-leaves-prose-order-ambiguous"),
    pytest.param("Disconnect the pump lead before removing the inlet cover.",
                 "After detaching the pump lead, lift off the inlet cover.",
                 id="different-grammar-preserves-explicit-before-after-with-exact-targets"),
    pytest.param("Remove the inlet cover, then remove the inlet cover.",
                 "Take off the inlet cover before lifting off the inlet cover.",
                 id="same-action-on-one-component-intentionally-repeated"),
    pytest.param("Disconnect the pump lead and remove the inlet cover.",
                 "Lift off the inlet cover and detach the pump lead.",
                 id="parallel-distinct-actions-with-the-same-assignment-in-opposite-syntax"),
])
def test_within_leaf_guard_keeps_repeat_parallel_and_qualified_controls(source_text, draft):
    from autodata_ingestion import procedure_rewrite_auto as auto

    assert auto._clause_assignment_changed(source_text, draft) is False
    source = document(source_text)
    payload = response(draft)
    current = run(source, payload)
    try:
        auto.render_auto(source, payload, prompt_version="full-prose-auto-prompt-v7")
    except ValueError as error:
        # Recognized v7 limitations stay visible. The new check does not
        # reinterpret installer synonyms or parallel action grammar.
        assert current.error_code == str(error) == "REWRITE_ACTION_MUTATION"
    else:
        assert current.error_code is None


@pytest.mark.parametrize("source_text,draft", [
    ("Remove the cover.", "Take the cover off if the seal is dry."),
    ("If the retaining clip is damaged, inspect the harness.", "Check the harness for signs of wear."),
    ("If the seal is dry, remove the cover.", "Take the cover off if the connector is dry."),
    ("Disconnect the battery.", "Detach the battery after the ignition is off."),
    ("Inspect the seal once the cover is cool.", "Check the seal for damage."),
    ("Install the seal.", "Fit the old seal into place."),
    ("Remove the seal.", "Take the new seal off."),
    ("Install a new seal.", "Fit the used seal into place."),
    ("Install a new seal.", "Fit the seal into place."),
    ("Remove the cover.", "Take the cover off with a pry bar."),
    ("On models equipped with a trailer package, inspect the connector.",
     "On trims equipped with a trailer package, check the connector."),
    ("Remove the seal.", "Take the seal off with a heat gun."),
    ("Remove the cover with a pry bar.", "Take the cover off with a screwdriver."),
    ("Remove the cover with a pry bar.", "Take the cover off."),
    ("Inspect the housing.", "If desired, check the housing for damage."),
    ("Inspect the connector.", "On models equipped with a trailer package, check the connector."),
    ("Inspect the seal for wear.", "Check the seal for corrosion."),
    ("Inspect the seal for wear.", "Check the seal."),
])
def test_automatic_rewrite_rejects_proven_new_missing_or_changed_task_qualifiers(source_text, draft):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Remove the cover.", "Take the cover off."),
    ("If the retaining clip is damaged, inspect the harness.", "Check the harness if the retaining clip is damaged."),
    ("If the seal is dry, remove the cover.", "When the seal has dried, take the cover off."),
    ("Inspect the seal once the cover is cool.", "After the cover is cool, check the seal."),
    ("Disconnect the battery once the ignition is off.", "After switching the ignition off, detach the battery."),
    ("Install a new seal.", "Fit a replacement seal into place."),
    ("Install the old gasket.", "Fit the original gasket into place."),
    ("Remove the old gasket.", "Take the original gasket off."),
    ("Remove the cover using a pry bar.", "With a pry bar, take the cover off."),
    ("Remove the cover when accessing the seal.", "Take the cover off to reach the seal."),
    ("Inspect the seal to determine if the lip is damaged.", "Check the seal for a damaged lip."),
    ("Inspect the seal for wear.", "Check the seal for signs of wear."),
    ("Inspect the seal.", "Check the seal for wear."),
    ("The filter housing is supplied with a heat gun.", "The heat gun comes together with the filter housing."),
    ("Before removing the cover, disconnect the battery.",
     "Detach the battery before taking off the cover."),
    ("If the latch vibrates, inspect the motor.", "Check the motor when the latch makes a rattling sound."),
])
def test_automatic_rewrite_preserves_equivalent_and_unresolved_qualifier_phrasing(source_text, draft):
    result = run(document(source_text), response(draft))
    assert result.error_code is None


@pytest.mark.parametrize("source_text,draft,error", [
    ("Remove all fasteners except the captive bolt.",
     "Take off every fastener, including the captive bolt.", "REWRITE_QUALIFIER_MUTATION"),
    ("Remove the clips, other than the cable clip.",
     "Take off the cable clip as well as the other clips.", "REWRITE_QUALIFIER_MUTATION"),
    ("Inspect all hinges excluding the latch hinge.",
     "Check all hinges except the center hinge.", "REWRITE_QUALIFIER_MUTATION"),
    ("Remove all fasteners except the captive bolt.",
     "Take off every fastener.", "REWRITE_QUALIFIER_MUTATION"),
    ("Except if the seal is dry, inspect the housing.",
     "Check the housing whenever needed.", "REWRITE_SAFETY_MUTATION"),
    ("Inspect the seal, then inspect the cover.",
     "Check the seal, or check the cover instead.", "REWRITE_CLAUSE_MUTATION"),
    ("Inspect either the seal or the cover.",
     "Check the seal and check the cover.", "REWRITE_CLAUSE_MUTATION"),
    ("Either inspect the seal or inspect the cover.",
     "Check the seal and check the cover.", "REWRITE_CLAUSE_MUTATION"),
    ("If the retaining clip is damaged and the seal is dry, inspect the harness.",
     "Check the harness if the retaining clip is damaged or the seal is dry.", "REWRITE_QUALIFIER_MUTATION"),
    ("If the retaining clip is damaged and the seal is dry, inspect the harness.",
     "Check the harness if the retaining clip is damaged.", "REWRITE_QUALIFIER_MUTATION"),
    ("If the seal is dry and cool, remove the cover.",
     "Take the cover off if the seal is dry.", "REWRITE_QUALIFIER_MUTATION"),
    ("When the seal is dry, remove the cover.",
     "Take the cover off if the seal is dry and cool.", "REWRITE_QUALIFIER_MUTATION"),
    ("If the seal is dry or cool, remove the cover.",
     "When the seal is cool and dry, take the cover off.", "REWRITE_QUALIFIER_MUTATION"),
    ("If the seal is dry and the housing is cool, inspect the harness.",
     "Check the harness if the seal is cool and the housing is dry.", "REWRITE_QUALIFIER_MUTATION"),
    ("Install a new oil seal.", "Fit the used oil seal into place.", "REWRITE_QUALIFIER_MUTATION"),
    ("Install a new outer seal.", "Fit the used outer seal into place.", "REWRITE_QUALIFIER_MUTATION"),
    ("Install an undamaged new seal.", "Fit a damaged new seal into place.", "REWRITE_QUALIFIER_MUTATION"),
    ("Install a new rubber oil seal.", "Fit a used rubber oil seal into place.", "REWRITE_QUALIFIER_MUTATION"),
    ("Remove the old transmission seal.", "Take the new transmission seal off.", "REWRITE_QUALIFIER_MUTATION"),
])
def test_automatic_rewrite_v10_rejects_proven_scope_changes(source_text, draft, error):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == error
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("Remove all fasteners except the captive bolt.",
     "Take off all fasteners other than the captive bolt."),
    ("Inspect either the seal or the cover.",
     "Either check the cover or check the seal instead."),
    ("Inspect the seal, then inspect the cover.",
     "After checking the seal, check the cover."),
    ("If the seal is dry and the housing is cool, inspect the harness.",
     "Check the harness when the housing is cool and the seal is dry."),
    ("If the seal is dry and cool, remove the cover.",
     "Take the cover off when the seal is cool and dry."),
    ("If the retaining clip is damaged or the seal is dry, inspect the harness.",
     "Check the harness when the seal is dry or the retaining clip is damaged."),
    ("If the seal is dry and the housing is cool, inspect the harness.",
     "Check the harness when the seal has dried and the housing has cooled."),
    ("Install a new rubber oil seal.", "Fit the replacement rubber oil seal into place."),
    ("Install a new outer seal.", "Fit the outer replacement seal into place."),
    ("Install an undamaged original oil seal.", "Fit the old undamaged oil seal into place."),
])
def test_automatic_rewrite_v10_preserves_equivalent_scope(source_text, draft):
    result = run(document(source_text), response(draft))
    assert result.error_code is None


def test_automatic_rewrite_v10_retains_conditional_exception_exactly():
    first = "Except if the seal is dry, inspect the housing."
    source = document(first, "Remove the cover.")
    payload = response(first, "Take the cover off.")
    payload["replacements"][0].update(action="retain", reason="Keep the source exception.")
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == first


def test_technical_only_retention_is_explicit_and_table_stays_exact():
    source = document("25 Nm", "Remove the cover.")
    source["blocks"].append({"block_id":"table", "source_order":3,"type":"table",
        "columns":["Part","Torque"],"rows":[["Cover","25 Nm"]],"evidence_ids":["fixture"]})
    payload = response("25 Nm", "Take the cover off.")
    payload["replacements"][0].update(action="retain", reason="Exact technical specification")
    result = run(source, payload)
    assert result.error_code is None
    report = rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).report
    assert report["retained_paths"] == ["/blocks/0/text"]
    assert result.document["blocks"][-1] == dict(source["blocks"][-1], source_order=4)


def test_auto_table_only_introduction_and_saved_response_binding():
    from autodata_ingestion.procedure_rewrite_auto import validate_auto
    source = document()
    source["blocks"] = [{"block_id":"table","source_order":1,"type":"table",
        "columns":["Part","Torque"],"rows":[["Cover","25 Nm"]],"evidence_ids":["fixture"]}]
    payload = response(introduction="The table lists the cover torque of 25 Nm.")
    result = run(source, payload)
    assert result.error_code is None
    assert validate_auto(source, result.document, response=payload).passed
    changed = deepcopy(payload); changed["introduction"] = "Cover torque is listed as 25 Nm."
    assert not validate_auto(source, result.document, response=changed).passed


@pytest.mark.parametrize("mutation", ["number", "order", "missing", "extra", "context"])
def test_automatic_profile_rejects_corrupt_or_incomplete_model_outputs(mutation):
    source = document("Tighten the bolts to 25 Nm.", "Remove the cover.")
    payload = response("The bolts require tightening to 25 Nm.", "Take the cover off.")
    if mutation == "number": payload["replacements"][0]["text"] = "The bolts require tightening to 30 Nm."
    if mutation == "order": payload["replacements"].reverse()
    if mutation == "missing": payload["replacements"].pop()
    if mutation == "extra": payload["replacements"].append(deepcopy(payload["replacements"][0]))
    if mutation == "context": payload["introduction"] = "Use this for the 2012 Audi A3."
    result = run(source, payload)
    assert result.error_code is not None and result.document == source


def test_prompt_asks_for_automatic_full_prose_without_human_review_obligations():
    prompt = json.loads(rewrite.build_rewrite_prompt(document("Remove the cover."), context={}, profile_version=PROFILE))
    assert prompt["profile_version"] == PROFILE
    assert "human" not in " ".join(prompt["rules"]).lower()
    assert "automatically" in " ".join(prompt["rules"]).lower()
    assert prompt["slots"][0]["text"] == "Remove the cover."


def test_prompt_v10_declares_complete_response_rows_and_server_required_actions():
    source = document("Remove the cover.", "25 Nm", "Never start the motor.",
                      "Fit the cover only after the seal sits flush.",
                      "Except if the seal is dry, inspect the housing.")
    before = deepcopy(source)
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context={}, profile_version=PROFILE))
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v10"
    assert prompt["response_shape"] == {"introduction": "string", "replacements": [
        {"block_id": "string", "path": "string", "action": "rewrite|retain", "text": "string", "reason": "string"}]}
    assert [slot["required_action"] for slot in prompt["slots"]] == ["rewrite", "rewrite_or_retain", "retain", "retain", "retain"]
    rules = " ".join(prompt["rules"])
    assert 'reason:""' in rules
    assert "exactly five keys" in rules
    assert "copying long phrases" in rules
    assert source == before


def test_historical_auto_prompt_digest_remains_exact():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _build_auto_prompt_v1
    prompt = _build_auto_prompt_v1(document("Remove the cover."), context={})
    assert sha256(prompt.encode()).hexdigest() == "cc5ef47228dc07abee81956adabf0de870247950fc3f5867ce6ed8b110f62e51"
    assert json.loads(prompt)["prompt_version"] == "full-prose-auto-prompt-v1"


def test_historical_v4_prompt_digest_and_validation_report_remain_stable():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _auto_prompt_version, _build_auto_prompt_v4, render_auto, validate_auto

    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompt_hash = sha256(_build_auto_prompt_v4(source, context=context).encode()).hexdigest()
    assert prompt_hash == "00e8a399286299d7c8bb588c9c38f10a99895bb4e0f8a252d18c9f4338c21b2d"
    version = _auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v4"

    # The old validator accepted this changed operation and resulting report.
    payload = response("Fit the cover.")
    candidate = render_auto(source, payload, prompt_version=version)
    historical = validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed and historical.report["validator_version"] == "full-prose-auto-validator-v2"
    current = validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_ACTION_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v8"


def test_historical_v5_prompt_digest_and_validation_report_remain_stable():
    from autodata_ingestion import procedure_rewrite_auto as auto
    from hashlib import sha256

    source = document("Remove the left-hand wheel-arch liner.")
    context = {"vehicle": "routing-only"}
    prompt = auto._build_auto_prompt_v5(source, context=context)
    prompt_hash = sha256(prompt.encode()).hexdigest()
    assert prompt_hash == "096c23f47e4a38e3a48175b377e3f49cf1f5ca24204e59837e5f3a916365b3f9"
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v5"

    payload = response("Take off the liner from the right-hand wheel arch.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed and historical.report["validator_version"] == "full-prose-auto-validator-v3"
    current = auto.validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_DIRECTION_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v8"


def test_historical_v6_prompt_digest_and_validation_report_remain_stable():
    from autodata_ingestion import procedure_rewrite_auto as auto
    from hashlib import sha256

    source = document("Remove the inlet cover.", "Remove the cable shield.")
    context = {"vehicle": "routing-only"}
    digest = sha256(auto._build_auto_prompt_v6(source, context=context).encode()).hexdigest()
    assert digest == "8cb4564ba563dc7fbd04a443abc67b71b2c50718ed5607d194a06227e86bf87d"
    version = auto._auto_prompt_version(source, context=context, prompt_hash=digest)
    assert version == "full-prose-auto-prompt-v6"

    payload = response("Take off the cable shield.", "Lift off the inlet cover.")
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed and historical.report["validator_version"] == "full-prose-auto-validator-v4"
    current = auto.validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_COMPONENT_SWAP",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v8"


def test_historical_v7_prompt_candidate_and_validation_hashes_remain_stable():
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("Remove the inlet cover first, then remove the cable shield.")
    payload = response("Take the cable shield off before lifting off the inlet cover.")
    context = {"vehicle": "routing-only"}
    prompt = auto._build_auto_prompt_v7(source, context=context)
    prompt_hash = sha256(prompt.encode()).hexdigest()
    assert prompt_hash == "d17f83f22c979878e4e5f11dc3f47e33c8c7affb0decc511047e323842432857"
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v7"

    candidate = auto.render_auto(source, payload, prompt_version=version)
    validation = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert validation.passed is True
    assert validation.report["content_acceptance_required"] is False
    assert validation.report["complete_rewrite"] is False
    assert digest_json(candidate) == "8597df2a50095d2a843c0b87b571d590831babc8416bee23977d08d166ceb487"
    assert digest_json(validation.report) == "96d1fb4a3d6efe7135794fd5ba9fdce64c4efbc2bd481b1dd48b773b16522d66"

    current = auto.validate_auto(source, candidate, response=payload)
    assert current.passed is False
    assert current.report["passed"] is False
    assert current.report["validator_version"] == "full-prose-auto-validator-v8"
    assert current.error_codes == ("REWRITE_CLAUSE_MUTATION",)


def test_historical_v8_prompt_candidate_and_validation_hashes_remain_stable():
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("Remove the cover.")
    payload = response("Take the cover off if the seal is dry.")
    context = {"vehicle": "routing-only"}
    prompt = auto._build_auto_prompt_v8(source, context=context)
    prompt_hash = sha256(prompt.encode()).hexdigest()
    assert prompt_hash == "7214abba87a6086a1023c317b31d0586f19a6946b241aec7ca7e776b79037f3a"
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v8"

    candidate = auto.render_auto(source, payload, prompt_version=version)
    validation = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert validation.passed is True
    assert validation.report["content_acceptance_required"] is False
    assert validation.report["complete_rewrite"] is False
    assert digest_json(candidate) == "3da3ec07cb74b58eab8eea69bfd1cb6d46088a8790201cd2f8aeac5719116daf"
    assert digest_json(validation.report) == "574e67861f5c7c268db9fa436f22137cf587a41ab7676eb37ecd0e94e8e4403c"

    current = auto.validate_auto(source, candidate, response=payload)
    assert current.passed is False
    assert current.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


def test_historical_v9_prompt_candidate_and_validation_hashes_remain_stable():
    from hashlib import sha256
    from autodata_ingestion import procedure_rewrite_auto as auto

    source = document("Install a new oil seal.")
    payload = response("Fit the used oil seal into place.")
    context = {"vehicle": "routing-only"}
    prompt = auto._build_auto_prompt_v9(source, context=context)
    prompt_hash = sha256(prompt.encode()).hexdigest()
    assert prompt_hash == "13cb6f8ddc88bed61bacf96da7839468447a6c6c2bf2c496289faac1b8289e38"
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v9"

    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert historical.report["validator_version"] == "full-prose-auto-validator-v7"
    assert digest_json(candidate) == "79c64e1180988281853e16b91a4da5e124a5a6250cd92b40b96713a9345cd0f4"
    assert digest_json(historical.report) == "edfe4cdccc79773c6098aa4679e2cb57850601de0c4494ccc3dc4f1e67a2e268"

    current = auto.validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_QUALIFIER_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v8"


def test_auto_prompt_hash_accepts_only_exact_server_reconstructions():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import (
        _auto_prompt_version, _build_auto_prompt_v1, _build_auto_prompt_v2,
        _build_auto_prompt_v4, _build_auto_prompt_v5, _build_auto_prompt_v6, _build_auto_prompt_v7,
        _build_auto_prompt_v8, _build_auto_prompt_v9, build_auto_prompt,
    )
    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompts = [builder(source, context=context) for builder in
               (_build_auto_prompt_v1, _build_auto_prompt_v2, _build_auto_prompt_v4, _build_auto_prompt_v5,
                _build_auto_prompt_v6, _build_auto_prompt_v7, _build_auto_prompt_v8, build_auto_prompt)]
    for prompt in prompts:
        digest = sha256(prompt.encode()).hexdigest()
        assert _auto_prompt_version(source, context=context, prompt_hash=digest) == json.loads(prompt)["prompt_version"]
        assert not _auto_prompt_version(document("Remove the panel."), context=context, prompt_hash=digest)
        assert not _auto_prompt_version(source, context={}, prompt_hash=digest)
    for mutation in ("rule", "required_action", "version"):
        changed = json.loads(prompts[-1])
        if mutation == "rule": changed["rules"].pop()
        if mutation == "required_action": del changed["slots"][0]["required_action"]
        if mutation == "version": changed["prompt_version"] = "full-prose-auto-prompt-v3"
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert not _auto_prompt_version(source, context=context, prompt_hash=sha256(encoded.encode()).hexdigest())
    assert not _auto_prompt_version(source, context=context, prompt_hash="0" * 64)


def test_prompt_v9_response_example_satisfies_strict_renderer():
    source = document("Remove the cover.", "25 Nm")
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context={}, profile_version=PROFILE))
    payload = {"introduction": "The procedure covers removal of the cover.", "replacements": []}
    for slot, text in zip(prompt["slots"], ["Take the cover off.", "25 Nm"]):
        row = {key: "" for key in prompt["response_shape"]["replacements"][0]}
        row.update(block_id=slot["block_id"], path=slot["path"], text=text,
                   action="rewrite" if slot["required_action"] == "rewrite" else "retain")
        if row["action"] == "retain": row["reason"] = "Exact technical specification"
        payload["replacements"].append(row)
    assert run(source, payload).error_code is None
    del payload["replacements"][0]["reason"]
    assert run(source, payload).error_code == "REWRITE_SLOT_MISMATCH"


def zero_slot_document():
    """Synthetic shape of the failed proof; no production text or references."""
    source = document()
    source["title"] = "Cover service references"
    kinds = ["callout"] * 35 + ["heading"] * 24 + ["link"] * 4
    source["blocks"] = [
        {"block_id": f"protected-{i}", "source_order": i + 1, "type": kind,
         "text": "Cover service references", "evidence_ids": ["fixture-evidence"]}
        for i, kind in enumerate(kinds)
    ]
    return source


def test_zero_slot_prompt_v3_requests_only_source_introduction_without_routing():
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    source = zero_slot_document()
    before = deepcopy(source)
    context = {"vehicle": "2099 RoutingModel CTX-99"}
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context=context, profile_version=PROFILE))
    assert len(source["blocks"]) == 63 and prose_slots(source) == []
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v3"
    assert prompt["replacement_count"] == 0 and prompt["slots"] == []
    assert prompt["response_shape"] == {"introduction": "string", "replacements": []}
    assert "context" not in prompt and "RoutingModel" not in json.dumps(prompt)
    rules = " ".join(prompt["rules"])
    assert '"replacements":[]' in rules
    assert "Do not invent replacement rows" in rules
    assert "document is the only source of facts" in rules
    assert "numeric, identifier or reference facts" in rules
    assert prompt["document"] == source == before


def test_zero_slot_output_preserves_all_protected_content_and_saved_response_binding():
    from autodata_ingestion.procedure_rewrite_auto import validate_auto
    source = zero_slot_document()
    before = deepcopy(source)
    payload = response(introduction="The article provides cover service references.")
    result = run(source, payload)
    assert result.error_code is None
    assert validate_auto(source, result.document, response=payload).passed
    restored = deepcopy(result.document)
    restored["blocks"].pop(0)
    for block in restored["blocks"]:
        block["source_order"] -= 1
    assert digest_json(restored) == digest_json(source)
    assert source == before
    changed = deepcopy(payload)
    changed["introduction"] = "Cover service references are provided here."
    assert not validate_auto(source, result.document, response=changed).passed
    report = validate_auto(source, result.document, response=payload).report
    assert report["complete_rewrite"] is False


@pytest.mark.parametrize("mutation", ["fabricated_slot", "numeric", "identifier", "third_key"])
def test_zero_slot_output_still_rejects_fabricated_slots_and_unsupported_facts(mutation):
    source = zero_slot_document()
    payload = response(introduction="The article provides cover service references.")
    if mutation == "fabricated_slot":
        payload["replacements"] = response("Reword this protected heading.")["replacements"]
    elif mutation == "numeric":
        payload["introduction"] = "The cover requires 99 Nm."
    elif mutation == "identifier":
        payload["introduction"] = "Use tool UNSUPPORTED-99 for cover service."
    else:
        payload["replacement_count"] = 0
    result = run(source, payload)
    assert result.error_code == {
        "fabricated_slot": "REWRITE_SLOT_MISMATCH", "numeric": "REWRITE_TECHNICAL_MUTATION",
        "identifier": "REWRITE_TECHNICAL_MUTATION", "third_key": "REWRITE_RESPONSE_INVALID",
    }[mutation]
    assert result.document == source


def test_zero_slot_historical_prompt_reconstruction_and_current_routing_omission():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import (
        _build_auto_prompt_v1, _build_auto_prompt_v2, build_auto_prompt, _auto_prompt_version,
    )
    source = zero_slot_document()
    context = {"vehicle": "routing-only"}
    historical = [(_build_auto_prompt_v1, "ce519878922481405f40028c3af5ebf2ff742af5bab96126ea21650311d67ea0"),
                  (_build_auto_prompt_v2, "e1fb10033d5aec793c15dda664767656be5530d380972e76bf48a2bb5d2ee3f5")]
    for builder, expected in historical:
        digest = sha256(builder(source, context=context).encode()).hexdigest()
        assert digest == expected
        assert _auto_prompt_version(source, context=context, prompt_hash=digest)
        assert not _auto_prompt_version(source, context={}, prompt_hash=digest)
    current = build_auto_prompt(source, context=context)
    digest = sha256(current.encode()).hexdigest()
    assert current == build_auto_prompt(source, context={"vehicle": "other routing"})
    assert _auto_prompt_version(source, context={}, prompt_hash=digest)
    changed_source = deepcopy(source)
    changed_source["blocks"][0]["text"] = "Other protected content"
    assert not _auto_prompt_version(changed_source, context=context, prompt_hash=digest)
    for key, value in [("replacement_count", 1), ("prompt_version", "unrecognized"),
                       ("response_shape", {"introduction": "string", "replacements": [{}]})]:
        changed = json.loads(current)
        changed[key] = value
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert not _auto_prompt_version(source, context=context, prompt_hash=sha256(encoded.encode()).hexdigest())


def test_nonzero_slot_historical_v2_prompt_digest_remains_exact():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _build_auto_prompt_v2
    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompt = _build_auto_prompt_v2(source, context=context)
    assert json.loads(prompt)["prompt_version"] == "full-prose-auto-prompt-v2"
    assert sha256(prompt.encode()).hexdigest() == "d972668e5934f6f66dee2ead79ee6bd45e4ca3c98e4f8fb94128fa330cdd22b6"


def test_server_zero_slot_candidate_is_exact_heading_and_preserves_source():
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document(); before = deepcopy(source)
    candidate, metadata = auto.build_source_preserving_candidate(source)
    heading = next(b['text'] for b in source['blocks'] if b['type'] == 'heading')
    assert candidate['blocks'][0]['text'] == heading
    restored = deepcopy(candidate); restored['blocks'].pop(0)
    for block in restored['blocks']: block['source_order'] -= 1
    assert restored == source == before
    assert metadata == {"transformation_method":"source-preserving-zero-slot-v1",
        "drafting_actor":"server", "model":"server-zero-slot-v1", "profile_version":PROFILE,
        "model_calls":0, "model_dispatch_count":0, "complete_rewrite":False,
        "source_hash":digest_json(source), "output_hash":digest_json(candidate)}
    validation = auto.validate_source_preserving_candidate(source, candidate, metadata)
    assert validation.passed and validation.report['complete_rewrite'] is False
    assert validation.report['introduction_origin'] == 'source_heading'
    assert validation.report['model_dispatch_count'] == 0
    assert auto.build_source_preserving_candidate(source) == (candidate, metadata)


def test_server_zero_slot_skips_ambiguous_heading_without_editing_it():
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document()
    first = next(i for i,b in enumerate(source['blocks']) if b['type']=='heading')
    source['blocks'][first]['text'] = 'Specification ½'
    candidate, metadata = auto.build_source_preserving_candidate(source)
    assert candidate['blocks'][0]['text'] == next(b['text'] for b in source['blocks'][first+1:] if b['type']=='heading')
    assert candidate['blocks'][first+1]['text'] == 'Specification ½'
    assert auto.validate_source_preserving_candidate(source, candidate, metadata).passed


@pytest.mark.parametrize('kind', ['no_heading', 'ambiguous', 'oversize', 'nonzero'])
def test_server_zero_slot_fails_closed_without_an_eligible_heading(kind):
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document()
    if kind == 'nonzero': source = document('Remove the cover.')
    else:
        for b in source['blocks']:
            if b['type'] == 'heading':
                if kind == 'no_heading': b.update(type='callout', label='note'); b.pop('level', None)
                else: b['text'] = 'Specification ½' if kind=='ambiguous' else 'A'*(1024*1024)
    with pytest.raises(ValueError): auto.build_source_preserving_candidate(source)


@pytest.mark.parametrize('mutation', ['candidate', 'source', 'method', 'extra', 'zero_boolean'])
def test_server_zero_slot_revalidation_rejects_tampered_candidate_or_provenance(mutation):
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document(); candidate, metadata = auto.build_source_preserving_candidate(source)
    if mutation == 'candidate': candidate['blocks'][0]['text'] += ' Unsupported-99'
    elif mutation == 'source': source['blocks'][0]['text'] += ' changed'
    elif mutation == 'method': metadata['transformation_method'] = 'forged'
    elif mutation == 'extra': metadata['prompt_hash'] = '0'*64
    else: metadata['model_calls'] = False
    with pytest.raises(ValueError): auto.validate_source_preserving_candidate(source, candidate, metadata)
