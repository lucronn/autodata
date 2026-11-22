"""Protect fuel-line and fuel-rail prerequisites in ordinary rewrite slots."""

from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_full import render_full
from test_procedure_rewrite_auto import PROFILE, _scoped_prose_response, _scoped_prose_source, run


FUEL_GAUGE = "Disconnect the fuel line after the gauge returns to zero."
INVERTED_GAUGE = "Detach the fuel line before the gauge returns to zero."
FUEL_RAIL = "Remove the fuel rail after pressure in the rail has dissipated."
DEPRESSURIZE = "Disconnect the fuel line after depressurizing the fuel rail."
PARKED = "Disconnect the fuel line after the vehicle is parked."
PLACEMENTS = pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])


@PLACEMENTS
@pytest.mark.parametrize("original,draft", [
    (FUEL_GAUGE, INVERTED_GAUGE),
    (FUEL_GAUGE, "Detach the fuel line after the gauge returns to normal."),
    (FUEL_GAUGE, "Detach the fuel line."),
    ("Disconnect the fuel line.", INVERTED_GAUGE),
    (FUEL_RAIL, "Take off the fuel rail before pressure in the rail has dissipated."),
    (DEPRESSURIZE, "Detach the fuel line before depressurizing the fuel rail."),
    (PARKED, "Detach the fuel line before the vehicle is parked."),
    ("Disconnect the fuel-lines after the gauge returns to zero.",
     "Before the gauge returns to zero, detach the fuel-lines."),
    ("Disconnect the fuel line while the fuel rail is depressurized.",
     "With the fuel rail pressurised, detach the fuel line."),
])
def test_rejects_changed_fuel_prerequisites(in_cell, original, draft):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["slots"][-1]["required_action"] == "rewrite"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_QUALIFIER_MUTATION",)


@PLACEMENTS
@pytest.mark.parametrize("original,draft", [
    (FUEL_GAUGE, "Once the gauge returns to zero, detach the fuel line."),
    (FUEL_RAIL, "After pressure in the rail has dissipated, take off the fuel rail."),
    (DEPRESSURIZE, "After depressurizing the fuel rail, detach the fuel line."),
    (PARKED, "After the vehicle is parked, detach the fuel line."),
    ("Open the fuel line while the fuel rail is depressurized.",
     "With the fuel rail depressurised, open the fuel line."),
    ("Disconnect the fuel line while the fuel rail is depressurized.",
     "With the fuel rail depressurised, detach the fuel line."),
    ("Inspect the gauge after the vehicle is parked.", "Check the gauge for damage after the vehicle is parked."),
    ("Inspect the fuel level gauge after the vehicle is parked.",
     "Check the fuel level gauge for signs of damage after the vehicle is parked."),
    ("Check the parking brake after the vehicle has stopped.",
     "Inspect the parking brake for signs of wear after the vehicle has stopped."),
    ("Inspect the fuel line with a mirror.", "Check the fuel line using a mirror."),
])
def test_fuel_prerequisite_scope_allows_distinct_faithful_prose(in_cell, original, draft):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["slots"][-1]["required_action"] == "rewrite"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@PLACEMENTS
def test_retains_compound_fuel_prerequisite(in_cell):
    original = "Disconnect the fuel line after the gauge returns to zero and the pump has stopped."
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    payload = _scoped_prose_response(prompt, INVERTED_GAUGE)
    result = run(source, payload)
    assert result.error_code == "REWRITE_QUALIFIER_MUTATION"
    assert result.document == source
    payload["replacements"][-1].update(action="retain", text=original, reason="Keep both prerequisites together.")
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert checked.report["retained_paths"] == [payload["replacements"][-1]["path"]]


@PLACEMENTS
def test_introduction_cannot_reverse_fuel_prerequisite_preserved_in_body(in_cell):
    source = _scoped_prose_source(FUEL_GAUGE, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, "Once the gauge returns to zero, detach the fuel line.")
    assert run(source, payload).error_code is None
    payload["introduction"] = "Fuel line service before the gauge returns to zero."
    result = run(source, payload)
    assert result.error_code == "REWRITE_INTRODUCTION_UNSUPPORTED_CLAIM"
    assert result.document == source


@pytest.mark.parametrize("in_cell,prompt_hash,document_hash,report_hash", [
    (False, "dabaf77101ab1b5c088c14be9894d08659031bfa8eaf4965afa1b0d713d689ce",
     "31e1b5a6cbd068fe884d34e3a43ac21790de2bc8bb20ccc93fd295376a53d723",
     "cc8a4a78f13e547661639ef03a7a54dc67c40c1636142da371c55749e918e2f7"),
    (True, "777d7fdb5df994e21fcbe6b012dab305ac4ce9178a98e1be30e2d2f7aaeda321",
     "05c7d2944a1d2fcf3a99c707797912058eecc7b90ec35a5fd5ce07abec6f61f2",
     "d3e15cc7b6e03494b039924f6f889b2418ee61c58e02f1efb0fb2a0811796da8"),
])
def test_v53_replay_preserves_historical_fuel_prompt_document_and_report(in_cell, prompt_hash, document_hash, report_hash):
    source = _scoped_prose_source(FUEL_GAUGE, in_cell=in_cell)
    context = {}
    prompt = auto._build_auto_prompt_v53(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v53"
    payload = _scoped_prose_response(prompt, INVERTED_GAUGE)
    document = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, document, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(document) == document_hash
    assert digest_json(historical.report) == report_hash
    current = auto.validate_auto(source, document, response=payload)
    assert current.error_codes == ("REWRITE_QUALIFIER_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v52"
