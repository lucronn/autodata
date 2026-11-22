"""Keep lowercase-litre fluid quantities bound to the original specification."""

from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_full import render_full
from test_procedure_rewrite_auto import PROFILE, _scoped_prose_response, _scoped_prose_source, run


MINIMUM_FILL = "Fill the fluid reservoir with at least 1.5 l of brake fluid."
INVERTED_FILL = "Fill the fluid reservoir using at most 1.5 l of brake fluid."
PLACEMENTS = pytest.mark.parametrize("in_cell", [False, True], ids=["article", "table-cell"])


@PLACEMENTS
@pytest.mark.parametrize("original,draft", [
    (MINIMUM_FILL, INVERTED_FILL),
    (MINIMUM_FILL.replace("1.5 l", "1.5l"), INVERTED_FILL.replace("1.5 l", "1.5l")),
    ("Oil capacity is 4.2 l maximum.", "The minimum oil capacity is 4.2 l."),
    ("Brake fluid: 1.5 l minimum.", "Brake fluid: 1.5 l maximum."),
    ("Coolant: at least 1.5 l.", "Coolant: at most 1.5 l."),
    ("Fill the coolant tank with between 1.5 l and 2.0 l of coolant.",
     "Fill the coolant tank at either endpoint, 1.5 l or 2.0 l of coolant."),
])
def test_retains_lowercase_litre_limits_and_ranges(in_cell, original, draft):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["slots"][-1]["required_action"] == "retain"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source
    candidate = render_full(source, payload, profile_version=PROFILE, include_cell_blocks=in_cell)
    assert auto.validate_auto(source, candidate, response=payload).error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)

    payload["replacements"][-1].update(action="retain", text=original, reason="Keep the complete fluid specification.")
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.report["changed_prose_slots"] == ["/blocks/0/text"]
    assert checked.report["retained_paths"] == [payload["replacements"][-1]["path"]]


@PLACEMENTS
@pytest.mark.parametrize("original,draft", [
    ("Inspect terminal L-4.", "Check terminal L-4 for corrosion."),
    ("Inspect connector 4 l.", "Check connector 4 l for corrosion."),
    ("Inspect pin 3 l.", "Check pin 3 l for corrosion."),
    ("Inspect the coolant pump wiring at 4 l connector.",
     "Check the coolant pump wiring at 4 l connector for wear."),
    ("Inspect the fluid-level sensor at connector 4 l.",
     "Check the fluid-level sensor at connector 4 l for damage."),
    ("Inspect the 4 l fluid-level sensor.", "Check the 4 l fluid-level sensor for damage."),
])
def test_lowercase_litre_guard_leaves_identifiers_editable(in_cell, original, draft):
    source = _scoped_prose_source(original, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    assert json.loads(prompt)["slots"][-1]["required_action"] == "rewrite"
    payload = _scoped_prose_response(prompt, draft)
    result = run(source, payload)
    assert result.error_code is None
    checked = auto.validate_auto(source, result.document, response=payload)
    assert checked.report["changed_prose_slots"] == [row["path"] for row in payload["replacements"]]


@PLACEMENTS
@pytest.mark.parametrize("value", ["1.5 L", "1.5 mL", "1.5 litres"])
def test_lowercase_litre_guard_preserves_other_volume_unit_policy(in_cell, value):
    source = _scoped_prose_source(MINIMUM_FILL.replace("1.5 l", value), in_cell=in_cell)
    current = json.loads(auto.build_auto_prompt(source, context={}))
    earlier = json.loads(auto._build_auto_prompt_v54(source, context={}))
    assert current["slots"][-1]["required_action"] == "retain"
    assert current["slots"] == earlier["slots"]


@PLACEMENTS
def test_introduction_cannot_add_inverted_litre_limit_while_body_retains_source(in_cell):
    source = _scoped_prose_source(MINIMUM_FILL, in_cell=in_cell)
    prompt = auto.build_auto_prompt(source, context={})
    payload = _scoped_prose_response(prompt, MINIMUM_FILL)
    payload["replacements"][-1].update(action="retain", reason="Keep the complete fluid specification.")
    assert run(source, payload).error_code is None
    payload["introduction"] = "Brake fluid capacity is at most 1.5 l."
    result = run(source, payload)
    assert result.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("in_cell,prompt_hash,document_hash,report_hash", [
    (False, "8956bf729c2ed0cbe8dd20c86c38978fd88d05863471fe0d698daf4cd06dac9b",
     "fa3e441c85865dc2b05cae8c5381252391b9d8eb3dbf745aab5146ef8bda3bcf",
     "a275dc250c32cc42ab15461c657f47447a2782b60ef1f0888767eee155a3a65d"),
    (True, "d0e18d97572da3b344c0e3bfc871720488e474ba7d97d207175399063cd3b929",
     "94acf6fedb7655e225157a9722107e58b71dfa71cba797c39863f44b3ae1e3a4",
     "00a7ceeb2eeaad094ee4d32a7e57243c928ddbbbd275306a7f70cb50e61ec879"),
])
def test_v54_replay_preserves_lowercase_litre_prompt_document_and_report(in_cell, prompt_hash, document_hash, report_hash):
    source = _scoped_prose_source(MINIMUM_FILL, in_cell=in_cell)
    context = {}
    prompt = auto._build_auto_prompt_v54(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == prompt_hash
    version = auto._auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v54"
    payload = _scoped_prose_response(prompt, INVERTED_FILL)
    document = auto.render_auto(source, payload, prompt_version=version)
    historical = auto.validate_auto(source, document, response=payload, prompt_version=version)
    assert historical.passed
    assert digest_json(document) == document_hash
    assert digest_json(historical.report) == report_hash
    current = auto.validate_auto(source, document, response=payload)
    assert current.error_codes == ("REWRITE_SPEC_SCOPE_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v53"
