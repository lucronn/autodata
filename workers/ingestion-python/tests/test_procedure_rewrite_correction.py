"""Correction drafts stay bound to the source, failed response, and model calls."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_correction import correct_retained_draft, replay_retained_correction
from test_procedure_rewrite_full import document, response


class Replies:
    def __init__(self, *batches):
        self.batches = iter(batches)
        self.attempts = []

    def complete(self, prompt):
        decoded = json.loads(prompt)
        candidates = next(self.batches)
        reply = {"rewrites": [
            {"slot": index, "candidates": wording} for index, wording in enumerate(candidates, 1)
        ]}
        self.attempts.append({
            "prompt": decoded,
            "prompt_hash": sha256(prompt.encode()).hexdigest(),
            "response": reply,
            "response_hash": digest_json(reply),
        })
        return reply


@pytest.mark.parametrize("preserve_notes", [False, True])
def test_correction_replays_note_labels_only_under_the_bound_policy(preserve_notes):
    source = document("Note: Remove the cover.", "Inspect the seal.")
    previous = response("Take the cover off.", "Inspect the seal.")
    delegate = Replies([["Check the seal.", "Check the seal.", "Inspect the seal."]])
    corrected = correct_retained_draft(
        source, previous, complete_json=delegate.complete, model_call_budget=1, preserve_notes=preserve_notes,
    )
    assert corrected.error_code is None
    assert corrected.response["replacements"][0]["text"] == "Take the cover off."
    expected = "Note: Take the cover off." if preserve_notes else "Take the cover off."
    assert corrected.document["blocks"][1]["text"] == expected
    assert corrected.document["blocks"][2]["text"] == "Check the seal."
    assert replay_retained_correction(
        source, previous, model_call_budget=1, evidence=corrected.evidence, attempts=delegate.attempts,
        preserve_notes=preserve_notes,
    ) == corrected


def test_correction_replays_all_guards_and_keeps_the_prior_response():
    source = document("Remove the cover.", "Install the shield.", "Tighten the bolts to 25 Nm.")
    previous = response("Remove the cover.", "Take off the shield.", "Tighten the bolts to 20 Nm.",
                        introduction="This model applies to 2016.")
    unchanged = deepcopy(previous)
    delegate = Replies([
        ["Remove the cover.", "Take the cover off.", "Detach the cover."],
        ["Take off the shield.", "Fit the shield.", "Install the shield."],
    ])

    corrected = correct_retained_draft(source, previous, complete_json=delegate.complete, model_call_budget=2)

    assert previous == unchanged
    assert len(delegate.attempts) == 1 and len(delegate.attempts[0]["prompt"]["passages"]) == 2
    assert corrected.error_code is None
    assert corrected.document["blocks"][0]["text"] == "This article describes the service information that follows."
    assert [block["text"] for block in corrected.document["blocks"][1:]] == [
        "Take the cover off.", "Fit the shield.", "Tighten the bolts to 25 Nm.",
    ]
    assert corrected.response["replacements"][2]["action"] == "retain"
    assert replay_retained_correction(
        source, previous, model_call_budget=2, evidence=corrected.evidence, attempts=delegate.attempts,
    ) == corrected


def test_masked_retry_requires_exact_reference_tokens():
    section = "Remove the cover shown in figure 2."
    source = document(section)
    previous = response(section)
    delegate = Replies(
        [[section, section, section]],
        [[
            "Take off the cover in figure 2.",
            "Take off the cover in figure [TOKEN2].",
            "Take off the cover shown in figure [TOKEN1].",
            section,
        ]],
    )
    result = correct_retained_draft(source, previous, complete_json=delegate.complete, model_call_budget=2)

    assert len(delegate.attempts) == 2
    assert delegate.attempts[1]["prompt"]["passages"][0]["source"].endswith("figure [TOKEN1].")
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == "Take off the cover shown in figure 2."


def test_unresolved_draft_stops_at_explicit_budget_and_keeps_source():
    text = "Remove the cover."
    source = document(text)
    previous = response(text)
    delegate = Replies([[text, text, text]])

    result = correct_retained_draft(source, previous, complete_json=delegate.complete, model_call_budget=1)

    assert len(delegate.attempts) == 1
    assert result.error_code == "REWRITE_UNCHANGED"
    assert result.document is None
    assert source["blocks"][0]["text"] == text
    assert previous["replacements"][0]["text"] == text


def test_retry_does_not_replace_an_authored_marker_like_literal():
    section = "Remove the cover tagged [TOKEN1]."
    source = document(section)
    previous = response(section)
    wording = "Take off the cover tagged [TOKEN1]."
    delegate = Replies([[section] * 3], [[section, wording, section, section]])

    result = correct_retained_draft(source, previous, complete_json=delegate.complete, model_call_budget=2)

    assert delegate.attempts[1]["prompt"]["passages"][0]["source"] == section
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == wording


@pytest.mark.parametrize("tamper", ["prompt_hash", "response", "extra", "source", "prior"])
def test_correction_replay_rejects_a_changed_binding(tamper):
    text = "Remove the cover."
    source = document(text)
    previous = response(text)
    delegate = Replies([[text, "Take off the cover.", "Detach the cover."]])
    result = correct_retained_draft(source, previous, complete_json=delegate.complete, model_call_budget=1)
    attempts = deepcopy(delegate.attempts)
    if tamper == "prompt_hash":
        attempts[0]["prompt_hash"] = "0" * 64
    elif tamper == "response":
        attempts[0]["response"]["rewrites"][0]["candidates"][1] = "Install the cover."
    elif tamper == "extra":
        attempts.append(attempts[0])
    elif tamper == "source":
        source["blocks"][0]["evidence_ids"] = ["another-source"]
    else:
        previous["introduction"] = "This article describes access."

    with pytest.raises(ValueError, match="REWRITE_CORRECTION_EVIDENCE_INVALID"):
        replay_retained_correction(source, previous, model_call_budget=1, evidence=result.evidence, attempts=attempts)


def test_corrective_drafting_rejects_malformed_proposals():
    source = document("Remove the cover.")
    previous = response("Remove the cover.")

    with pytest.raises(ValueError, match="REWRITE_CORRECTION_RESPONSE_INVALID"):
        correct_retained_draft(
            source, previous, model_call_budget=1,
            complete_json=lambda _prompt: {"rewrites": [{"slot": True, "candidates": ["Take the cover off."] * 3}]},
        )
