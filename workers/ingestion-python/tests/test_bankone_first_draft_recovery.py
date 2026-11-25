"""Synthetic controls for checked Bankone prose and exact authored scopes."""

from copy import deepcopy

import pytest

from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.bankone_first_draft_recovery import _plain_wording, check_bankone_passage, recover_bankone_draft
from autodata_ingestion.bankone_first_draft_structure import extract_bankone_structure
from autodata_ingestion.procedure_rewrite_auto import (
    _NOTE_LABEL_PROMPT_VERSION, _near_copy, render_auto, validate_auto,
)
from test_procedure_rewrite_full import document, response


TOOL = "FW-730 Reservoir Alignment Gauge"
TARGET = "Fixture filter (7)"
OPTIONS = ("hose (upper left)", "hose (lower left)", "hose (upper right)", "hose (lower right)")
SUFFIX = ", ".join(OPTIONS[:3]) + ", or " + OPTIONS[3]
ALTERNATIVES = f"{TARGET} » Remove {SUFFIX}"
RECAST = f"For {TARGET}, follow the applicable removal option: {SUFFIX}"


def variant_entry(block_id):
    return {
        "block_id": block_id, "kind": "alternatives",
        "reference_hashes": [digest_json([label, index]) for index, label in enumerate(OPTIONS)],
    }


def test_alternatives_preserve_every_option_target_and_the_action_wrapper():
    entry = variant_entry("p1")
    assert not _near_copy(*check_bankone_passage(ALTERNATIVES, RECAST, entry), check_sentences=True)
    assert _near_copy(*check_bankone_passage(ALTERNATIVES, ALTERNATIVES, entry), check_sentences=True)
    for damaged in (
        RECAST.replace(OPTIONS[0] + ", ", ""),
        RECAST.replace(", ".join(OPTIONS[:2]), ", ".join(reversed(OPTIONS[:2]))),
        RECAST.replace(", or ", ", and "),
        RECAST.replace(TARGET, "Another filter (7)"),
        RECAST.replace("removal option", "installation option"),
    ):
        with pytest.raises(ValueError, match="REWRITE_VARIANT_SCOPE_MUTATION"):
            check_bankone_passage(ALTERNATIVES, damaged, entry)
    with pytest.raises(ValueError, match="REWRITE_VARIANT_SCOPE_MUTATION"):
        check_bankone_passage(ALTERNATIVES, RECAST, {**entry, "reference_hashes": entry["reference_hashes"][:-1]})


def test_archived_structure_rejects_hidden_references_and_compound_instructions():
    parts = [f'<mtr-doc-link id="fixture-{index}">{label}</mtr-doc-link>' for index, label in enumerate(OPTIONS)]
    html = f"<ol><li>{TARGET} » Remove {', '.join(parts[:3])}, or {parts[3]}</li></ol>"
    source = document(ALTERNATIVES)
    assert len(extract_bankone_structure(source, html.encode())["slots"]) == 1
    hidden = html.replace('id="fixture-2"', 'id="fixture-2" aria-hidden="true"')
    assert not extract_bankone_structure(source, hidden.encode())["slots"]
    assert not list(_plain_wording("Drain the reservoir and discard the seal."))


def test_note_and_tool_proof_never_allows_an_ordinary_row_or_changed_label():
    note = {"block_id": "p1", "kind": "note_label"}
    tool = {"block_id": "p2", "kind": "tool_label"}
    assert check_bankone_passage("Note:", "Note:", note) is None
    assert check_bankone_passage(TOOL, TOOL, tool) is None
    for original, replacement in (("Note:", "NOTE:"), ("Note: Unbound detail.", "Note: Unbound detail.")):
        with pytest.raises(ValueError, match="REWRITE_NOTE_LABEL_MUTATION"):
            check_bankone_passage(original, replacement, note)
    with pytest.raises(ValueError, match="REWRITE_BANKONE_TOOL_LABEL_MUTATION"):
        check_bankone_passage(TOOL, TOOL.replace("730", "735"), tool)
    with pytest.raises(ValueError, match="REWRITE_BANKONE_STRUCTURE_INVALID"):
        check_bankone_passage("Drain the reservoir.", "Drain the reservoir.", {"block_id": "p3", "kind": "ordinary"})


def test_complete_recovery_keeps_passing_rows_and_original_reply():
    source = document("Note:", TOOL, ALTERNATIVES, "Drain the fixture reservoir.", "Remove the shield.")
    structure = {
        "source_hash": digest_json(source),
        "slots": {
            "/blocks/0/text": {"block_id": "p0", "kind": "note_label"},
            "/blocks/1/text": {"block_id": "p1", "kind": "tool_label"},
            "/blocks/2/text": variant_entry("p2"),
        },
    }
    raw = response(
        "Note:", TOOL, ALTERNATIVES, "Drain the fixture reservoir.", "The shield must be removed.",
        introduction="It is safe to service the fixture while the motor is running.",
    )
    saved = deepcopy(raw)
    version = _NOTE_LABEL_PROMPT_VERSION
    with pytest.raises(ValueError):
        render_auto(source, raw, prompt_version=version)

    recovered, paths = recover_bankone_draft(source, raw, prompt_version=version, structure=structure)

    assert raw == saved
    assert paths == [row["path"] for row in raw["replacements"][:4]]
    assert recovered["introduction"] != raw["introduction"]
    assert [row["text"] for row in recovered["replacements"]] == [
        "Note:", TOOL, RECAST, "The fixture reservoir must be drained.", "The shield must be removed.",
    ]
    assert [row["action"] for row in recovered["replacements"]] == ["retain", "retain", "rewrite", "rewrite", "rewrite"]
    assert recovered["replacements"][4] == raw["replacements"][4]
    with pytest.raises(ValueError):
        render_auto(source, recovered, prompt_version=version)
    candidate = render_auto(source, recovered, prompt_version=version, bankone_structure=structure)
    assert validate_auto(
        source, candidate, response=recovered, prompt_version=version, bankone_structure=structure,
    ).passed

    changed = deepcopy(source)
    changed["blocks"][-1]["text"] = "Remove the cap."
    assert recover_bankone_draft(changed, raw, prompt_version=version, structure=structure) is None
    swapped = deepcopy(structure)
    swapped["slots"]["/blocks/2/text"]["block_id"] = "p1"
    assert recover_bankone_draft(source, raw, prompt_version=version, structure=swapped) is None
    changed["blocks"][-1]["text"] = "Warning: Do not release the fixture latch while the motor is running."
    unsafe = deepcopy(raw)
    unsafe["replacements"][-1]["text"] = "Warning: Release the fixture latch while the motor is running."
    assert recover_bankone_draft(
        changed, unsafe, prompt_version=version, structure={**structure, "source_hash": digest_json(changed)},
    ) is None


def test_recovery_keeps_mixture_scope_and_instruction_sequence():
    instructions = (
        "Use the service mixture of distilled water and cleaner to fill the fixture reservoir during the rinse stage.",
        "Fill the chamber to the reference mark and wait for the bubbles to stop.",
        "Adjust the detergent level in the reservoir to the upper mark.",
        "With a funnel, add the detergent to the fixture reservoir.",
    )
    source = document("Note:", *instructions)
    structure = {
        "source_hash": digest_json(source), "slots": {"/blocks/0/text": {"block_id": "p0", "kind": "note_label"}},
    }
    raw = response("Note:", *instructions, introduction="This article describes the service information that follows.")
    version = _NOTE_LABEL_PROMPT_VERSION

    recovered, paths = recover_bankone_draft(source, raw, prompt_version=version, structure=structure)

    assert paths == [row["path"] for row in raw["replacements"]]
    assert [row["text"] for row in recovered["replacements"][1:]] == [
        "During the rinse stage, fill the fixture reservoir with the service mixture. "
        "The mixture consists of distilled water and cleaner.",
        "Fill the chamber until it reaches the reference mark. Then wait for the bubbles to stop.",
        "In the reservoir, adjust the detergent level to the upper mark.",
        "With a funnel, add to the fixture reservoir the detergent.",
    ]
