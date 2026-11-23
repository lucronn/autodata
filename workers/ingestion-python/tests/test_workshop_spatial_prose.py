"""Keep physical direction and real closure instructions attached to their targets."""

from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from test_procedure_rewrite_auto import run
from test_procedure_rewrite_full import document, response


_V55 = "full-prose-auto-prompt-v55"
_V59 = "full-prose-auto-prompt-v59"
_DIRECTION_ERROR = "REWRITE_DIRECTION_MUTATION"
_SOURCE_BOUNDARY = "The reference label sits on the inside guide face at the rear of the display support."
_DRAFT_BOUNDARY = "Find the identification tag at the rear of the display support, on the internal guide face."


@pytest.mark.parametrize(("source_word", "draft_word"), [
    ("inside", "internal"), ("internal", "inside"), ("outside", "external"), ("external", "outside"),
    ("inside", "interior"), ("interior", "inside"), ("outside", "exterior"), ("exterior", "outside"),
])
def test_equivalent_orientation_keeps_a_compound_boundary(source_word, draft_word):
    source = document(_SOURCE_BOUNDARY.replace("inside", source_word))
    payload = response(_DRAFT_BOUNDARY.replace("internal", draft_word))
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["prompt_version"] == _V59
    assert auto._auto_prompt_version(source, context={}, prompt_hash=sha256(prompt.encode()).hexdigest()) == _V59
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == payload["replacements"][0]["text"]
    validation = auto.validate_auto(source, result.document, response=payload, prompt_version=_V59)
    assert validation.passed
    assert validation.report["validator_version"] == "full-prose-auto-validator-v57"
    assert validation.report["changed_prose_slots"] == ["/blocks/0/text"]


@pytest.mark.parametrize("draft", [
    _DRAFT_BOUNDARY.replace("internal", "external"),
    _DRAFT_BOUNDARY.replace("guide face", "latch face"),
    _DRAFT_BOUNDARY.replace("guide face", "guide edge"),
    _DRAFT_BOUNDARY.replace("internal guide face", "guide face"),
])
def test_orientation_alias_does_not_allow_a_changed_polarity_or_target(draft):
    source = document(_SOURCE_BOUNDARY)
    result = run(source, response(draft))
    assert result.error_code == _DIRECTION_ERROR
    assert result.document == source


def test_historical_orientation_prompt_keeps_its_former_validation():
    source = document(_SOURCE_BOUNDARY)
    payload = response(_DRAFT_BOUNDARY)
    historical = auto._build_auto_prompt_v58(source, context={})
    assert json.loads(historical)["prompt_version"] == _V55
    assert auto._auto_prompt_version(source, context={}, prompt_hash=sha256(historical.encode()).hexdigest()) == _V55
    with pytest.raises(ValueError, match=_DIRECTION_ERROR):
        auto.render_auto(source, payload, prompt_version=_V55)


def test_nonspatial_internal_diagnostics_keep_their_prompt_bytes():
    source = document("The controller stores an internal fault when the power supply drops.")
    assert auto.build_auto_prompt(source, context={}) == auto._build_auto_prompt_v58(source, context={})


def test_saved_candidate_with_a_new_orientation_alias_still_gets_current_checks():
    source = document("The label sits on the guide face of the display support.")
    payload = response("The display support carries the identification tag on its external guide face.")
    historical = auto.render_auto(source, payload, prompt_version=_V55)
    assert auto.validate_auto(source, historical, response=payload, prompt_version=_V55).passed
    with pytest.raises(ValueError, match=_DIRECTION_ERROR):
        auto.require_current_publication_checks(source, historical, saved_prompt_version=_V55)


_SOURCE_NEAR = "The display tag sits near the rear exhibit frame."
_DRAFT_CLOSE = "At rest, the display tag remains close to the rear exhibit frame."


@pytest.mark.parametrize("source_text,draft", [(_SOURCE_NEAR, _DRAFT_CLOSE), (_DRAFT_CLOSE, _SOURCE_NEAR)])
def test_spatial_proximity_does_not_create_a_closing_instruction(source_text, draft):
    source = document(source_text)
    assert json.loads(auto.build_auto_prompt(source, context={}))['prompt_version'] == _V59
    payload = response(draft)
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == draft
    assert auto.validate_auto(source, result.document, response=payload, prompt_version=_V59).passed


@pytest.mark.parametrize("target", ["front exhibit frame", "rear exhibit stand", "rear exhibit frame spacer"])
def test_proximity_must_keep_the_full_reference_target(target):
    source = document(_SOURCE_NEAR)
    result = run(source, response(_DRAFT_CLOSE.replace("rear exhibit frame", target)))
    assert result.error_code == _DIRECTION_ERROR
    assert result.document == source


@pytest.mark.parametrize(("source_text", "draft"), [
    ("The interior panel rests near the stop.", "Close to the stop as the interior panel settles."),
    ("The interior panel rests near the stop.", "The interior panel can close to the stop."),
    ("Close to the stop, then remove the plate.", "Remove the plate, which rests near the stop."),
    ("Open the panel and close to the stop.", "Swing the panel open near the stop."),
    ("Close the cover near the stop assembly.", "Set the cover in place near the stop assembly."),
])
def test_actual_or_coordinated_closing_instructions_remain_actions(source_text, draft):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == "REWRITE_ACTION_MUTATION"
    assert result.document == source


@pytest.mark.parametrize(("source_text", "draft"), [
    ("The painted mark on the inside guide face of the cover identifies the latch.",
     "The latch is identified by the painted marking on the internal guide face of the bracket."),
    ("The cover's inside guide face carries the identification mark.",
     "The identification mark sits on the bracket's internal guide face."),
    ("The painted mark on the inside guide face of the cover plate identifies the latch.",
     "The latch is identified by the painted marking on the internal guide face of the cover support."),
    ("The retainers' inside guide face carries the identification mark.",
     "The identification mark sits on the brackets' internal guide face."),
    ("The painted mark on the inside guide face belonging to the cover identifies the latch.",
     "The latch is identified by the painted marking on the internal guide face belonging to the bracket."),
])
def test_boundary_alias_does_not_allow_a_different_explicit_owner(source_text, draft):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == _DIRECTION_ERROR
    assert result.document == source


def test_boundary_alias_keeps_the_same_explicit_owner_after_reordering():
    source = document("The marking on the inside guide face of the cover identifies the latch.")
    draft = "Find the latch by the reference mark on the cover's internal guide face."
    result = run(source, response(draft))
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == draft



def test_proximity_keeps_both_nouns_in_a_coordinated_reference():
    source = document("The identification mark sits near the frame and latch.")
    result = run(source, response("At rest, the identification mark remains close to the frame and bracket."))
    assert result.error_code == _DIRECTION_ERROR
    assert result.document == source



def test_proximity_must_still_describe_the_same_subject():
    source = document("The cover rests near the access panel.")
    result = run(source, response("At rest, the cable remains close to the access panel."))
    assert result.error_code == _DIRECTION_ERROR
    assert result.document == source



@pytest.mark.parametrize("draft", [
    "The cover moves close to the rear access panel.",
    "The cover formerly rested close to the rear access panel.",
    "The cover was close to the rear access panel in this arrangement.",
])
def test_proximity_cannot_replace_a_present_location_with_motion_or_past_state(draft):
    source = document("The cover rests near the rear access panel.")
    result = run(source, response(draft))
    assert result.error_code == _DIRECTION_ERROR
    assert result.document == source



@pytest.mark.parametrize("tail", [
    ("the cover, latch and tab.", "the cover, latch and bracket."),
    ("the cover, latch, and tab.", "the cover, latch, and bracket."),
    ("the cover but away from the latch.", "the cover but away from the bracket."),
])
def test_proximity_preserves_reference_continuations(tail):
    source = document("The guide remains near " + tail[0])
    result = run(source, response("At rest, the guide sits close to " + tail[1]))
    assert result.error_code == _DIRECTION_ERROR
    assert result.document == source



@pytest.mark.parametrize(("orientation", "other"), [
    ("inboard", "internal"), ("outboard", "external"), ("inboard", "inside"), ("outboard", "outside"),
])
def test_compound_boundary_preserves_inboard_and_outboard_direction(orientation, other):
    source = document(f"The alignment mark is on the cover's {orientation} guide face.")
    result = run(source, response(f"The cover's {other} guide face bears the reference marking."))
    assert result.error_code == _DIRECTION_ERROR
    assert result.document == source
