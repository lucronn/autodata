"""Bind shorthand temperature values to their original procedure conditions."""

from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_full import render_full
from test_procedure_rewrite_auto import PROFILE, _scoped_prose_response, _scoped_prose_source, run


CAP_CHECK = "Inspect the radiator cap for leakage above 95 C."
INVERTED_CAP_CHECK = "Check the radiator cap for signs of leakage below 95 C."
CAP_RELEASE = "Release the cap after the engine reaches 90 C."
PLACEMENTS = pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])


@PLACEMENTS
@pytest.mark.parametrize("original,draft", [
    (CAP_CHECK, INVERTED_CAP_CHECK),
    (CAP_CHECK, "Check the radiator cap for signs of corrosion above 95 C."),
    (CAP_CHECK, "Check the thermostat housing for signs of leakage above 95 C."),
    ("Check the coolant tank for leakage above 200 F.",
     "Inspect the coolant tank for signs of leakage below 200 F."),
    ("Check the coolant tank for leakage above 200F.",
     "Inspect the coolant tank for signs of leakage below 200F."),
    (CAP_RELEASE, "Release the cap before the engine reaches 90 C."),
    (CAP_RELEASE, "Release the cap after the exhaust reaches 90 C."),
    ("Inspect the radiator cap for leaks at or above 95 C.",
     "Check the radiator cap for signs of leakage above 95 C."),
    ("Inspect the radiator cap for leaks at 95 C.",
     "Check the radiator cap for signs of leakage around 95 C."),
])
def test_rejects_changed_temperature_binding(in_cell, original, draft):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    validation = auto.validate_auto(source, candidate, response=payload)
    assert validation.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@PLACEMENTS
@pytest.mark.parametrize("different_value", ["96 C", "95 F"])
def test_retains_literal_temperature_amount_and_scale(in_cell, different_value):
    source = _scoped_prose_source(CAP_CHECK, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, f"Check the radiator cap for signs of leakage above {different_value}.")
    result = run(source, payload)
    assert result.error_code == "REWRITE_TECHNICAL_MUTATION"
    assert result.document == source


@PLACEMENTS
@pytest.mark.parametrize("original,draft", [
    (CAP_CHECK, "Above 95 C, check the radiator cap for signs of leakage."),
    (CAP_RELEASE, "After the engine reaches 90 C, release the cap."),
    ("Inspect the heater core for leaks below 200F.",
     "Check the heater core for signs of leakage below 200F."),
    ("Install the 3 C grade inserts.", "Fit the 3 C grade inserts in place."),
    ("Inspect connector 4 C for corrosion.", "Check connector 4 C for signs of corrosion."),
    ("Inspect the temperature sensor at connector 4 C.", "Check the temperature sensor at connector 4 C for damage."),
    ("Install the 2 temperature sensors.", "Fit the 2 temperature sensors in place."),
    ("Inspect connector DEG-C17.", "Check connector DEG-C17 for damage."),
    ("Inspect the engine harness at 4 C connector.", "Check the engine harness at 4 C connector for wear."),
    ("Inspect the engine harness at 4C connector.", "Check the engine harness at 4C connector for wear."),
    ("Check the engine ground at 3 C terminal.", "Inspect the engine ground at 3 C terminal for damage."),
])
def test_distinct_prose_stays_editable(in_cell, original, draft):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["slots"][-1]["required_action"] == "rewrite"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code is None
    validation = auto.validate_auto(source, result.document, response=payload)
    assert validation.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@PLACEMENTS
@pytest.mark.parametrize("original,draft", [
    ("Inspect the radiator cap for leakage above 95 C and below 100 C.",
     "Check the radiator cap for signs of leakage below 95 C and above 100 C."),
    ("Tighten the insert before the housing reaches 90 C.", "Tighten the insert after the housing reaches 90 C."),
    ("95 C minimum for the cooling fan test.", "For the cooling fan test, use 95 C maximum."),
    ("The thermostat test requires a minimum of 95 C.", "A maximum of 95 C is specified for the thermostat test."),
    ("The radiator should be checked from 40 C to 60 C.",
     "The radiator needs to be inspected at the endpoints 40 C and 60 C."),
    ("Between 40 C and 60 C", "From 40 C to 60 C"),
    ("Above 95 C", "Below 95 C"),
])
def test_retains_temperature_conditions_without_a_proven_binding(in_cell, original, draft):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    payload = _scoped_prose_response(prompt, draft)
    assert run(source, payload).error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    payload["replacements"][-1].update(action="retain", text=original, reason="Preserve the exact temperature range.")
    result = run(source, payload)
    assert result.error_code is None
    validation = auto.validate_auto(source, result.document, response=payload)
    assert validation.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert validation.report["retained_paths"] == [payload["replacements"][-1]["path"]]


@PLACEMENTS
@pytest.mark.parametrize("original", ["Turn the crankshaft through 90 degrees.", "Keep the flange at the 90° alignment mark."])
def test_bare_temperature_guard_does_not_reclassify_angles(in_cell, original):
    source = _scoped_prose_source(original, in_cell=in_cell)
    current = json.loads(auto.build_auto_prompt(source, context={}))
    historical = json.loads(auto._build_auto_prompt_v52(source, context={}))
    assert current["slots"] == historical["slots"]


@PLACEMENTS
def test_introduction_cannot_reverse_temperature_preserved_in_body(in_cell):
    source = _scoped_prose_source(CAP_CHECK, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, "Check the radiator cap for signs of leakage above 95 C.")
    faithful = run(source, payload)
    assert faithful.error_code is None
    assert auto.validate_auto(source, faithful.document, response=payload).report["changed_prose_slots"] == [
        row["path"] for row in payload["replacements"]
    ]

    payload["introduction"] = "Radiator cap leakage is inspected below 95 C."
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "3a51dfc9593e23405644c7cff3f12ac8db018193c1bd5418e1b2b6dc59f55b40",
     "b28a87d50b252b3c70f286882765b959a8a1eb1f516f9d0374b7efcafa2f7ca3",
     "e38d0b15f92cd056f9ad454b4baf45f6432e53e0630c817629fdf2eb5229ba28"),
    (True, "0abc40e71685f945fe5a4a12f2b509498ef72ac1143419c0bad92e5b458ab022",
     "44467658a21bb25f93dccddcba7e454e9d7f32ae540827b01bbfa6065194c6ea",
     "90727d443279d5032a96f1259e343c41fc04dfe62dea52d39942a80466293c49"),
])
def test_v52_replay_preserves_saved_temperature_prompt_document_and_validation(
    in_cell, prompt_hash, candidate_hash, report_hash,
):
    source = _scoped_prose_source(CAP_CHECK, in_cell=in_cell)
    context = {"make": "Fixture"}
    prompt = auto._build_auto_prompt_v52(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v52"
    payload = _scoped_prose_response(prompt, INVERTED_CAP_CHECK)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    current = auto.validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v53"
