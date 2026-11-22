"""Preserve literal lubrication assignments in automatic Workshop rewrites."""
from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_document import project_ordered_document
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_full import render_full
from test_procedure_rewrite_auto import PROFILE, _scoped_prose_response, _scoped_prose_source, run


_APPLY = "Apply silicone grease to the caliper slide pins."
_LUBRICATE = "Lubricate the caliper slide pins with silicone grease."
_GREASE = "Grease the caliper slide pins with silicone grease."
_WRONG_MATERIAL = "Lubricate the caliper slide pins with copper grease."
_WRONG_RECIPIENT = "Lubricate the brake pad friction surfaces with silicone grease."
_NO_GREASE = "Apply no grease to the brake pad friction surfaces."
_WARNING = "Never put lubricant on the brake pad friction surfaces."


def _source(instruction, *, in_cell):
    source = _scoped_prose_source(instruction, in_cell=in_cell)
    source["blocks"].append({
        "block_id": "lubricant-warning", "source_order": 3, "type": "paragraph",
        "text": _WARNING, "evidence_ids": ["fixture-evidence"],
    })
    return source


def _response(prompt, draft):
    payload = _scoped_prose_response(prompt, draft)
    payload["replacements"][-1].update(action="retain", text=_WARNING, reason="Keep the exact source warning.")
    return payload


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_APPLY, _WRONG_MATERIAL),
    (_APPLY, _WRONG_RECIPIENT),
    (_APPLY, "Lubricate the caliper slide pins without silicone grease."),
    (_APPLY, "Lubricate the caliper slide pins."),
    (_LUBRICATE, "Apply silicone grease to the caliper boots."),
    (_GREASE, "Apply grease to the caliper slide pins."),
    ("Apply clean engine oil to the O-ring.", "Lubricate the O-ring with engine oil."),
])
def test_rewrite_rejects_changed_lubricant_or_recipient(in_cell, original, draft):
    source = _source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _response(prompt, draft)
    result = run(source, payload)

    assert result.error_code == "REWRITE_LUBRICATION_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=json.loads(prompt)["prompt_version"])
    assert checked.error_codes == ("REWRITE_LUBRICATION_MUTATION",)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original,draft", [
    (_APPLY, _LUBRICATE),
    (_APPLY, _GREASE),
    (_LUBRICATE, _APPLY),
    (_GREASE, _APPLY),
    ("Apply clean engine oil to the O-ring.", "Lubricate the O-ring with clean engine oil."),
    ("Apply the parking brake.", "Engage the parking brake."),
    ("Apply paint to the liftgate.", "Coat the liftgate with paint."),
])
def test_rewrite_accepts_distinct_prose_with_the_same_assignment(in_cell, original, draft):
    source = _source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _response(prompt, draft)

    result = run(source, payload)

    assert result.error_code is None
    assert auto.validate_auto(source, result.document, response=payload).passed
    body = project_ordered_document(result.document)["body"]
    assert draft in body and original not in body
    assert body.endswith(_WARNING)


@pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])
@pytest.mark.parametrize("original", [
    _NO_GREASE,
    "Do not apply grease to the brake pad friction surfaces.",
    "Never lubricate the brake pad friction surfaces with silicone grease.",
])
def test_rewrite_keeps_negative_lubrication_instructions_exact(in_cell, original):
    source = _source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _response(prompt, _WRONG_RECIPIENT)
    result = run(source, payload)

    assert result.error_code == "REWRITE_SAFETY_MUTATION"
    assert result.document == source
    assert json.loads(prompt)["slots"][1]["required_action"] == "retain"

    payload["replacements"][1].update(action="retain", text=original, reason="Keep the source prohibition.")
    retained = run(source, payload)
    assert retained.error_code is None
    body = project_ordered_document(retained.document)["body"]
    assert original in body and body.endswith(_WARNING)


@pytest.mark.parametrize("separator", [". ", "; Then, ", ", then "], ids=["sentence", "semicolon", "comma-then"])
@pytest.mark.parametrize("location,error_code", [
    ("introduction", "REWRITE_INTRODUCTION_INSTRUCTION"),
    ("unrelated-slot", "REWRITE_LUBRICATION_MUTATION"),
    ("same-slot", "REWRITE_LUBRICATION_MUTATION"),
])
def test_rewrite_rejects_new_lubrication_assignments(location, error_code, separator):
    source = _source(_APPLY, in_cell=False)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _response(prompt, _LUBRICATE)
    addition = separator + _WRONG_RECIPIENT
    if location == "introduction":
        payload["introduction"] = payload["introduction"].rstrip(".") + addition
    else:
        row = payload["replacements"][0 if location == "unrelated-slot" else 1]
        row["text"] = row["text"].rstrip(".") + addition

    result = run(source, payload)

    assert result.error_code == error_code
    assert result.document == source


def test_rewrite_accepts_a_preserved_assignment_in_a_multisentence_slot():
    original = "Remove the pump. " + _APPLY
    draft = "Take the pump off. " + _LUBRICATE
    source = _source(original, in_cell=False)
    payload = _response(auto.build_auto_prompt(source, context={}), draft)

    result = run(source, payload)

    assert result.error_code is None
    assert draft in project_ordered_document(result.document)["body"]


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "d85fbfea3e244dd84758ea228aa5edd2359129adc4ca397012ec5929504f0e41",
     "9644b9fcdf23993644c96f295cb4d0a1b4a1f884c8ca6a25ff54a640263a8a3d",
     "c68badbae4056428dc62f89df8740f735f1e854074e85197088087ec02976108"),
    (True, "018c4032646f52f038e2913cd46aa9aec8b96e9e4a40140497e06da44cc17b4c",
     "6030b378985b610fa521d75b59a49be2f61df4fbffaa89b5b09d2b74a346ca20",
     "0e4b9cf00f885d0100981fc045711f104cbe9502860cfd906268a8c78b5bce05"),
])
def test_rewrite_replays_historical_v48_with_original_bytes(in_cell, prompt_hash, candidate_hash, report_hash):
    context = {"make": "Fixture"}
    source = _source(_APPLY, in_cell=in_cell)
    prompt = auto._build_auto_prompt_v48(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v48"
    payload = _response(prompt, _WRONG_RECIPIENT)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    original = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert original.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(original.report) == report_hash
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_LUBRICATION_MUTATION",)
