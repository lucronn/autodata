"""Bounded sentence correction uses only source and accounted model replies."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_sentence_correction import (
    MAX_SENTENCE_CORRECTION_CALLS, SENTENCE_CORRECTION_METHOD, SENTENCE_RECOVERY_METHOD,
    correct_sentence_draft, recover_sentence_correction,
)
from test_procedure_rewrite_full import document, response


class Replies:
    def __init__(self, *rounds):
        self._rounds = iter(rounds)
        self.prompts = []
        self.exchanges = []

    def complete(self, prompt):
        decoded = json.loads(prompt)
        self.prompts.append(decoded)
        assert decoded["method"] == SENTENCE_CORRECTION_METHOD
        choices = next(self._rounds)(decoded)
        reply = {"rewrites": [{"slot": index, "candidates": variants}
                             for index, variants in enumerate(choices, 1)]}
        self.exchanges.append({"prompt_hash": sha256(prompt.encode()).hexdigest(),
                               "response_hash": digest_json(reply)})
        return reply


def echo_passages(prompt):
    return [[passage["source"]] * 3 for passage in prompt["passages"]]


def echo_statements(prompt):
    return [[statement["statement"]] * 3 for statement in prompt["statements"]]


def test_compact_round_keeps_valid_v2_prose_and_binds_exchanges():
    source = document("Remove the cover.", "Install the shield.", "Tighten the bolts to 25 Nm.")
    previous = response("Take the cover off.", "Install the shield.", "Tighten the bolts to 20 Nm.")
    original = deepcopy((source, previous))
    replies = Replies(lambda _: [["Take off the shield.", "Fit the shield.", "Install the shield."]])

    result = correct_sentence_draft(source, previous, complete_json=replies.complete, model_call_budget=2)

    assert (source, previous) == original
    assert len(replies.prompts) == 1
    [passage] = replies.prompts[0]["passages"]
    assert passage["source"] == "Install the shield."
    assert passage["rejection"] == "REWRITE_UNCHANGED"
    assert result.error_code is None
    assert result.response["introduction"] == previous["introduction"]
    assert result.response["replacements"][0] == previous["replacements"][0]
    assert [block["text"] for block in result.document["blocks"][1:]] == [
        "Take the cover off.", "Fit the shield.", "Tighten the bolts to 25 Nm.",
    ]
    assert result.evidence == {
        "method": SENTENCE_CORRECTION_METHOD, "input_hash": digest_json(source),
        "guard_version": result.evidence["guard_version"], "prior_response_hash": digest_json(previous),
        "model_call_budget": 2, "exchanges": replies.exchanges, "draft_hash": digest_json(result.response),
    }
    assert result.evidence["guard_version"]


@pytest.mark.parametrize("reference", ("[TOKEN1]", "2"))
def test_second_round_splits_and_preserves_exact_marker_or_literal(reference):
    text = "Install the cover over the pump housing. Connect the plug shown in figure 2."
    source, previous = document(text), response(text)
    def sentences(prompt):
        assert [row["statement"] for row in prompt["statements"]] == [
            "Install the cover over the pump housing.", "Connect the plug shown in figure [TOKEN1].",
        ]
        return [
            ["Fit the cover over the pump housing.", "Detach the cover.", "Install the cover."],
            ["Attach the plug shown in figure [TOKEN2].", "Attach the plug shown in figure 3.",
             f"Attach the plug shown in figure {reference}."],
        ]
    replies = Replies(echo_passages, sentences)

    result = correct_sentence_draft(source, previous, complete_json=replies.complete, model_call_budget=2)

    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == (
        "Fit the cover over the pump housing. Attach the plug shown in figure 2."
    )
    assert result.evidence["exchanges"] == replies.exchanges
    assert len(replies.exchanges) == MAX_SENTENCE_CORRECTION_CALLS


def test_sentence_round_can_recover_an_action_rejection_from_source_only():
    source, previous = document("Install the shield."), response("Remove the shield.")
    def sentences(prompt):
        [statement] = prompt["statements"]
        assert statement["statement"] == "Install the shield."
        assert "Remove the shield" not in json.dumps(prompt)
        return [["Remove the shield.", "Fit the shield.", "Take off the shield."]]
    replies = Replies(echo_passages, sentences)

    result = correct_sentence_draft(source, previous, complete_json=replies.complete, model_call_budget=2)

    assert replies.prompts[0]["passages"][0]["rejection"] == "REWRITE_ACTION_MUTATION"
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == "Fit the shield."


@pytest.mark.parametrize("separator", (",", ""))
def test_local_inspection_equivalent_preserves_condition_and_installed_state(separator):
    condition = f"If the module is warm{separator} check to make sure the seal is installed."
    bad_variants = [
        "Check to confirm the seal is installed if the module is cold.",
        "Check to confirm the seal is installed.",
        "Check to confirm the seal is not installed if the module is warm.",
    ]
    source, previous = document(condition), response(bad_variants[0])
    replies = Replies(lambda _: [bad_variants], lambda _: [bad_variants])

    result = correct_sentence_draft(source, previous, complete_json=replies.complete, model_call_budget=2)

    assert len(replies.prompts) == 2
    assert replies.prompts[0]["passages"][0]["rejection"] == "REWRITE_QUALIFIER_MUTATION"
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == "Check to confirm the seal is installed if the module is warm."


def test_local_inspection_equivalent_cannot_reorder_an_action():
    condition = "If the service cover was removed, check to make sure the sealing ring is installed."
    source, previous = document(condition), response(condition)
    replies = Replies(echo_passages, echo_statements)

    result = correct_sentence_draft(source, previous, complete_json=replies.complete, model_call_budget=2)

    assert result.document is None
    assert result.error_code == "REWRITE_UNCHANGED"
    assert len(replies.exchanges) == 2


@pytest.mark.parametrize(("subject", "verb", "recovered"), [
    ("The two receivers", "does not communicate", True),
    ("Only the spare modules", "does not communicate", True),
    ("They", "does not communicate", True),
    ("The two receivers", "communicates", False),
])
def test_sentence_archive_recovery_preserves_wiring_and_communication_state(subject, verb, recovered):
    text = (f"{subject} are not wired to the central controller, thus the monitor "
            f"{verb} directly on a service data network.")
    source, previous = document(text), response(text)
    replies = Replies(echo_passages, echo_statements)
    archive = []

    def record(prompt):
        reply = replies.complete(prompt)
        archive.append({**replies.exchanges[-1], "response": reply})
        return reply

    original = correct_sentence_draft(source, previous, complete_json=record, model_call_budget=2)
    result = recover_sentence_correction(source, previous, model_call_budget=2, attempts=archive)

    assert original.document is None
    assert original.error_code == "REWRITE_UNCHANGED"
    assert result.evidence["method"] == SENTENCE_RECOVERY_METHOD
    assert result.evidence["original_error_code"] == original.error_code
    assert result.evidence["base_draft_hash"] == original.evidence["draft_hash"]
    assert result.evidence["exchanges"] == original.evidence["exchanges"]
    if recovered:
        assert result.error_code is None
        assert result.document["blocks"][1]["text"] == (
            f"{subject} lack wiring to the central controller, so the monitor "
            "has no direct communication on a service data network."
        )
        assert result.evidence["draft_hash"] != original.evidence["draft_hash"]
    else:
        assert result.document is None and result.error_code == original.error_code
    archive[-1]["response_hash"] = "0" * 64
    with pytest.raises(ValueError, match="^REWRITE_CORRECTION_EVIDENCE_INVALID$"):
        recover_sentence_correction(source, previous, model_call_budget=2, attempts=archive)


def test_single_call_budget_keeps_unresolved_source():
    text = "Install the shield."
    replies = Replies(echo_passages)

    result = correct_sentence_draft(document(text), response(text), complete_json=replies.complete, model_call_budget=1)

    assert result.document is None
    assert result.error_code == "REWRITE_UNCHANGED"
    assert result.response["replacements"][0]["text"] == text
    assert len(replies.exchanges) == 1


@pytest.mark.parametrize("budget", (True, 0, 3, "2"))
def test_rejects_invalid_budget_before_any_call(budget):
    replies = Replies()
    with pytest.raises(ValueError, match="^REWRITE_CORRECTION_BUDGET_INVALID$"):
        correct_sentence_draft(
            document("Install the shield."), response("Install the shield."),
            complete_json=replies.complete, model_call_budget=budget,
        )
    assert replies.prompts == []


def test_sentence_count_limit_blocks_the_second_call():
    texts = ("Install the shield.",) * 61
    replies = Replies(echo_passages)
    with pytest.raises(ValueError, match="^REWRITE_CORRECTION_INPUT_LIMIT$"):
        correct_sentence_draft(
            document(*texts), response(*texts), complete_json=replies.complete, model_call_budget=2,
        )
    assert len(replies.exchanges) == 1


def test_rejects_malformed_alternative_row():
    text = "Install the shield."
    with pytest.raises(ValueError, match="^REWRITE_CORRECTION_RESPONSE_INVALID$"):
        correct_sentence_draft(
            document(text), response(text), model_call_budget=2,
            complete_json=lambda _: {"rewrites": [{"slot": True, "candidates": ["Fit the shield."] * 3}]},
        )
