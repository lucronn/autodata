"""Keep compound measurements bound to their source instruction during rewriting."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_document import project_ordered_document
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.source_article_capture import capture_source_article
from test_procedure_rewrite_auto import PROFILE, _scoped_prose_response, _scoped_prose_source, run
from test_procedure_rewrite_full import document, response
from test_source_article_capture import capture_fixture


_OPENING = "Remove the cover."
_REWRITTEN = "Take off the cover."
_FLOW = "Set the return line flow rate to a maximum of 14 L/min."
_WRONG_FLOW = "Set the return line flow rate to a maximum of 14 L/s."
_EXPONENT = "Apply 1.2 × 10³ Pa to the fixture."
_INTRODUCTION = "This procedure covers access to the return line."


def _reply(slots):
    return {"introduction": _INTRODUCTION, "replacements": [
        {"block_id": slot["block_id"], "path": slot["path"], "action": slot["required_action"],
         "text": _REWRITTEN if slot["text"] == _OPENING else slot["text"],
         "reason": "Preserve the complete specification." if slot["required_action"] == "retain" else ""}
        for slot in slots
    ]}


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_compound_flow_survives_both_supplier_captures_and_rewrite(capture_fixture, provider):
    if provider == "bankone":
        source_payload = {"blocks": [{"type": "paragraph", "text": text} for text in (_OPENING, _FLOW)]}
        raw, media_type = json.dumps(source_payload).encode(), "application/json"
    else:
        raw, media_type = f"<p>{_OPENING}</p><p>{_FLOW}</p>".encode(), "text/html"
    capture_fixture.body(provider, raw, media_type)
    captured = capture_source_article(
        capture_fixture.context(provider), registry=capture_fixture.registry, object_store=capture_fixture.objects,
    )
    assert capture_fixture.resource_calls(provider, "body") == 1
    assert captured.source_body.splitlines() == [_OPENING, _FLOW]
    resource = captured.resources[0]
    assert resource["sha256"] == sha256(raw).hexdigest()
    assert capture_fixture.objects.data[resource["object_key"]] == (raw, media_type)

    source = captured.source_document
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v57"
    assert [slot["required_action"] for slot in prompt["slots"]] == ["rewrite", "retain"]
    good = _reply(prompt["slots"])
    invalid = deepcopy(good)
    invalid["replacements"][1].update(action="rewrite", text=_WRONG_FLOW, reason="")
    rejected = run(source, invalid)
    assert rejected.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert rejected.document == source

    accepted = run(source, good)
    assert accepted.error_code is None
    assert project_ordered_document(accepted.document)["body"].splitlines() == [_INTRODUCTION, _REWRITTEN, _FLOW]
    assert accepted.document["blocks"][-1]["evidence_ids"] == source["blocks"][-1]["evidence_ids"]
    report = auto.validate_auto(source, accepted.document, response=good, prompt_version=prompt["prompt_version"]).report
    assert report["retained_paths"] == [prompt["slots"][1]["path"]]
    assert report["changed_prose_slots"] == [prompt["slots"][0]["path"]]


@pytest.mark.parametrize("in_cell", [False, True], ids=["paragraph", "table-cell"])
@pytest.mark.parametrize("original,changed", [
    (_FLOW, "Set the return line flow rate to a minimum of 14 L/min."),
    ("Set the return flow to at least 14 l / min.", "Set the return flow to at most 14 l / min."),
    ("Set the coolant pump flow rate to 14 mL/s.", "Set the fuel pump flow rate to 14 mL/s."),
    ("The return flow must reach 14 liters per minute.", "The feed flow must reach 14 liters per minute."),
    ("Set the return flow to at least .5 L/min.", "Set the return flow to at most .5 L/min."),
    ("Set the return flow to at least 14 ℓ/min.", "Set the return flow to at most 14 ℓ/min."),
    ("Set the return flow to at most 14 US gallons per minute.",
     "Set the return flow to at least 14 US gallons per minute."),
    ("The pump moves 14 US gal of water every minute.", "The pump moves 14 US gal of water every second."),
    ("Set the return flow to at most 14 imperial gal/min.", "Set the return flow to at least 14 imperial gal/min."),
    ("The blower output is at least 14 cubic feet per minute.", "The blower output is at most 14 cubic feet per minute."),
    ("The blower output is at least 14 CFM.", "The blower output is at most 14 CFM."),
    ("Tighten the cover bolts to a maximum of 18 kgf·cm.", "Torque the cover bolts to a minimum of 18 kgf·cm."),
    ("Tighten the cover bolts to a maximum of 18 kgf–cm.", "Torque the cover bolts to a minimum of 18 kgf–cm."),
    ("Adjust outlet pressure to a maximum of 2 kgf/cm2.", "Adjust outlet pressure to a minimum of 2 kgf/cm2."),
    ("Adjust outlet pressure to a maximum of 2 kgf/cm².", "Adjust outlet pressure to a minimum of 2 kgf/cm²."),
    ("Adjust outlet pressure to a maximum of 2 kgf per square centimeter.",
     "Adjust outlet pressure to a minimum of 2 kgf per square centimeter."),
])
def test_compound_measurements_keep_numerator_denominator_and_scope(in_cell, original, changed):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    parsed = json.loads(prompt)
    assert parsed["prompt_version"] == "full-prose-auto-prompt-v57"
    assert parsed["slots"][-1]["required_action"] == "retain"
    result = run(source, _scoped_prose_response(prompt, changed))
    # The shared renderer checks non-decimal numerals before automatic prose validation.
    expected = "REWRITE_TECHNICAL_AMBIGUOUS" if "²" in original else "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.error_code == expected
    assert result.document == source

    retained = _scoped_prose_response(prompt, original)
    retained["replacements"][-1].update(action="retain", reason="Preserve the complete specification.")
    accepted = run(source, retained)
    assert accepted.error_code is None
    report = auto.validate_auto(source, accepted.document, response=retained, prompt_version=parsed["prompt_version"]).report
    assert report["retained_paths"] == [parsed["slots"][-1]["path"]]
    assert report["changed_prose_slots"] == [parsed["slots"][0]["path"]]


def test_generated_introduction_cannot_turn_a_plain_quantity_into_a_rate():
    volume = "Fill the rinse reservoir with 14 L of water."
    source = document(_OPENING, volume)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v55"
    payload = _reply(prompt["slots"])
    payload["introduction"] = "The rinse reservoir takes water at 14 L/s."
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source

    legacy = auto.render_auto(source, payload, prompt_version="full-prose-auto-prompt-v55")
    assert auto.validate_auto(source, legacy, prompt_version="full-prose-auto-prompt-v55").passed
    with pytest.raises(ValueError, match="^REWRITE_SPEC_SCOPE_MUTATION$"):
        auto.require_current_publication_checks(source, legacy, saved_prompt_version="full-prose-auto-prompt-v55")


@pytest.mark.parametrize("denominator", ["per", "every", "for each"])
def test_fluid_phrase_cannot_turn_a_plain_quantity_into_a_rate(denominator):
    source = document(_OPENING, "The reservoir contains 14 US gal of water.")
    wrong_rate = f"The reservoir holds 14 US gal of water {denominator} second."
    payload = response(_REWRITTEN, wrong_rate)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v55"

    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source

    legacy = auto.render_auto(source, payload, prompt_version="full-prose-auto-prompt-v55")
    assert legacy["blocks"][-1]["text"] == wrong_rate
    assert auto.validate_auto(source, legacy, response=payload, prompt_version="full-prose-auto-prompt-v55").passed
    with pytest.raises(ValueError, match="^REWRITE_SPEC_SCOPE_MUTATION$"):
        auto.require_current_publication_checks(source, legacy, saved_prompt_version="full-prose-auto-prompt-v55")


def test_compound_measurement_and_numeric_superscript_keep_their_protection():
    source = document(_OPENING, _FLOW, _EXPONENT)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v57"
    assert [slot["required_action"] for slot in prompt["slots"]] == ["rewrite", "retain", "retain"]
    payload = _reply(prompt["slots"])
    accepted = run(source, payload)
    assert accepted.error_code is None
    assert [row["text"] for row in accepted.document["blocks"][1:]] == [_REWRITTEN, _FLOW, _EXPONENT]

    payload["replacements"][-1].update(action="rewrite", text=_EXPONENT.replace("10³", "103"), reason="")
    result = run(source, payload)
    assert result.error_code == "REWRITE_TECHNICAL_AMBIGUOUS"
    assert result.document == source


@pytest.mark.parametrize("version,prompt_hash,document_hash,report_hash", [
    ("full-prose-auto-prompt-v55", "e41c9e66946d5473bcef8e96d262409dcb3b2b222baa11b5df44d90856ef0508",
     "3190aa7f02d3603f1677daa543584e9246b73f7df24019bee9ce9e7868eaba93",
     "c1bdb775cd0f131c52a8a8384d6e480fa6090394eb9a0a858d7fba35a9fe56c3"),
    ("full-prose-auto-prompt-v56", "def4f4de8b79d08f650fcff36c6029708033beeb62645c1a12c2f041cbd57cb2",
     "e7ee438aa4f8c7b8def65f16f633720064d47947f462544a302f91e29ccad3c9",
     "66678e1a9ee25e55e39ea717406e14a2c22a2204b6d331dabceacb755ff42e89"),
])
def test_saved_prompt_and_candidate_replay_before_current_first_publication_check(
    version, prompt_hash, document_hash, report_hash,
):
    superscripts = (_EXPONENT,) if version.endswith("v56") else ()
    source = document(_OPENING, _FLOW, *superscripts)
    payload = response(_REWRITTEN, _WRONG_FLOW, *superscripts, introduction=_INTRODUCTION)
    if superscripts:
        payload["replacements"][-1].update(action="retain", reason="Preserve the complete specification.")
    assert auto._auto_prompt_version(source, context={}, prompt_hash=prompt_hash) == version
    legacy = auto.render_auto(source, payload, prompt_version=version)
    report = auto.validate_auto(source, legacy, response=payload, prompt_version=version)
    assert report.passed
    assert digest_json(legacy) == document_hash
    assert digest_json(report.report) == report_hash
    with pytest.raises(ValueError, match="^REWRITE_SPEC_SCOPE_MUTATION$"):
        auto.require_current_publication_checks(source, legacy, saved_prompt_version=version)


@pytest.mark.parametrize("original,changed", [
    (_OPENING, _REWRITTEN),
    ("Inspect connector L-4.", "Check connector L-4 for corrosion."),
    ("Inspect the flow-control valve housing.", "Check the flow-control valve housing."),
])
def test_no_compound_measurement_keeps_the_historical_prompt_and_editable_prose(original, changed):
    source = document(original)
    prompt = auto.build_auto_prompt(source, context={})
    assert prompt == auto._build_auto_prompt_v55(source, context={})
    assert json.loads(prompt)["slots"][0]["required_action"] == "rewrite"
    result = run(source, response(changed))
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == changed
