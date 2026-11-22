"""Protect explicit Workshop procedure conditions and applicability."""

from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_full import render_full
from test_procedure_rewrite_auto import PROFILE, _scoped_prose_response, _scoped_prose_source, run


RESERVOIR = "Open the coolant reservoir when the engine has cooled."
EARLY_RESERVOIR = "Open the coolant reservoir before the engine cools down."
HIGH_VOLTAGE = "Disconnect the battery cable before working on the high-voltage connector."
OPTION = "On vehicles with air suspension, remove the shield."
OPTION_HEADING = "Vehicles with air suspension: Remove the shield."
OPTION_CONDITION = "Remove the shield when the vehicle has air suspension."
PLACEMENTS = pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])


@PLACEMENTS
@pytest.mark.parametrize("original,draft", [
    (RESERVOIR, EARLY_RESERVOIR),
    ("Open the bleed valve when the system is cool.", "Open the bleed valve before the system cools down."),
    (HIGH_VOLTAGE, "Detach the battery cable after carrying out work on the high-voltage connector."),
    (HIGH_VOLTAGE, "Detach the battery cable before working on the high-voltage battery."),
    ("Disconnect the connector after the indicator lamp goes out.",
     "Detach the connector before the indicator lamp goes out."),
    ("Open the coolant reservoir with the engine cold.", "Open the coolant reservoir with the engine hot."),
    ("Open the coolant reservoir with the engine cold.",
     "Open the coolant reservoir with the engine at operating temperature."),
    ("With the engine cold, open the coolant reservoir.", "With the engine hot, open the coolant reservoir."),
    ("Open the coolant reservoir as long as the engine is cool.",
     "Open the coolant reservoir as long as the engine is hot."),
    ("Open the coolant reservoir provided the engine is cool.",
     "Open the coolant reservoir provided that the engine is hot."),
    (OPTION, "Take the shield off on all vehicles."),
    (OPTION, "Take the shield off on vehicles with coil springs."),
    (OPTION, "Take the shield off."),
    ("Remove the shield.", "Take the shield off on vehicles with air suspension."),
    (OPTION_HEADING, "Take the shield off."),
    (OPTION_HEADING, "Vehicles with coil springs: Take the shield off."),
    (OPTION_CONDITION, "Take the shield off."),
    (OPTION_CONDITION, "Take the shield off when the vehicle has coil springs."),
    ("Remove the shield.", "If the vehicle has air suspension, take the shield off."),
])
def test_rejects_changed_conditions_and_vehicle_scope(in_cell, original, draft):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    version = json.loads(prompt)["prompt_version"]
    checked = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert checked.error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@PLACEMENTS
@pytest.mark.parametrize("original,draft", [
    (RESERVOIR, "When the engine has cooled, open the coolant reservoir."),
    ("Open the coolant reservoir after the engine has cooled.",
     "Once the engine has cooled, open the coolant reservoir."),
    (HIGH_VOLTAGE, "Before working on the high-voltage connector, detach the battery cable."),
    (OPTION, "Take the shield off on vehicles equipped with air suspension."),
    (OPTION_HEADING, "Take the shield off on vehicles with air suspension."),
    ("For models equipped with a trailer package, inspect the connector.",
     "Check the connector on models with a trailer package."),
    ("Inspect the shield on vehicle body panels for wear.",
     "Check the shield on vehicle body panels for signs of wear."),
    ("Remove the shield when the vehicle has stopped.",
     "Take the shield off when the vehicle has stopped."),
    ("When the vehicle has cooled, inspect the seal.",
     "Check the seal when the vehicle has cooled."),
    ("Open the coolant reservoir with the engine cold.",
     "With the engine cold, open the coolant reservoir."),
    ("Open the coolant reservoir as long as the engine is cool.",
     "As long as the engine is cool, open the coolant reservoir."),
    ("Open the coolant reservoir provided the engine is cool.",
     "Provided that the engine is cool, open the coolant reservoir."),
    ("Remove the radiator cover with a screwdriver.", "With a screwdriver, take the radiator cover off."),
])
def test_proven_conditions_still_support_distinct_prose(in_cell, original, draft):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["slots"][-1]["required_action"] == "rewrite"
    response = _scoped_prose_response(prompt, draft)
    result = run(source, response)
    assert result.error_code is None
    verified = auto.validate_auto(source, result.document, response=response)
    assert verified.passed
    assert verified.report["changed_prose_slots"] == [row["path"] for row in response["replacements"]]


@PLACEMENTS
@pytest.mark.parametrize("original,draft", [
    ("Open the coolant reservoir after the engine has cooled and the fan has stopped.", EARLY_RESERVOIR),
    ("The shield can be removed on vehicles with air suspension.", "Take the shield off on all vehicles."),
    (OPTION_CONDITION, "Take the shield off."),
])
def test_retains_conditions_without_a_proven_binding(in_cell, original, draft):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    response = _scoped_prose_response(prompt, draft)
    rejected = run(source, response)
    assert rejected.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert rejected.document == source
    response["replacements"][-1].update(action="retain", text=original, reason="Exact service condition.")
    retained = run(source, response)
    assert retained.error_code is None
    checked = auto.validate_auto(source, retained.document, response=response)
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert checked.report["retained_paths"] == [response["replacements"][-1]["path"]]


@pytest.mark.parametrize("introduction", [
    "Component access on all vehicles.",
    "Coolant access before the engine cools down.",
])
def test_procedure_conditions_cannot_be_added_in_the_introduction(introduction):
    source = _scoped_prose_source("Remove the shield.", in_cell=False)
    prompt = auto.build_auto_prompt(source, context={})
    response = _scoped_prose_response(prompt, "Take the shield off.")
    response["introduction"] = introduction
    assert run(source, response).error_code == "REWRITE_INTRODUCTION_UNSUPPORTED_CLAIM"


@pytest.mark.parametrize("in_cell,prompt_hash,candidate_hash,report_hash", [
    (False, "52c6e99085eea24b0280f04766bca404f185a53e60569302ab31279ee2e8d8f3",
     "e3b122970cdcbf182aa24a557fa6ff7bca7bc7b099b67919826c601568853c02",
     "5a0dc4f4a94015ddaffd755f7f8cf814d62af72636b7f2cd59e2c3cffe6b422d"),
    (True, "47deaec3c6f3e978d83303b2934bc2ea71e1ea790e2d6c9d0a8c7dc05c15a9b9",
     "b3368c6a16a6970429ef8ae4af25f10423ca0a0a106f006079186b3b9e9d234d",
     "405eaa26686ceaca48f987496523d38f05ec80f598270e2009e2725faec425b1"),
])
def test_v51_replay_preserves_saved_prompt_document_and_validation(in_cell, prompt_hash, candidate_hash, report_hash):
    source = _scoped_prose_source(RESERVOIR, in_cell=in_cell)
    context = {"make": "Fixture"}
    prompt = auto._build_auto_prompt_v51(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v51"
    payload = _scoped_prose_response(prompt, EARLY_RESERVOIR)
    candidate = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(candidate) == candidate_hash
    assert digest_json(historical.report) == report_hash
    current = auto.validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_QUALIFIER_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v52"
