"""Automatic mechanical publication checks; synthetic, not semantic proof."""
from copy import deepcopy
import json

import pytest

from autodata_ingestion import procedure_rewrite as rewrite
from autodata_ingestion.article_lifecycle_types import digest_json
from test_procedure_rewrite_full import document, response, Draft

PROFILE = "full-prose-auto-v1"


def run(source, payload):
    return rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version=PROFILE)


def test_automatic_rewrite_has_own_identity_and_no_manual_acceptance():
    source = document("Remove the cover.", "Tighten the bolts to 25 Nm with tool T-42.")
    payload = response("Take the cover off.", "The bolts require tightening to 25 Nm using tool T-42.")
    result = run(source, payload)
    assert result.error_code is None
    assert result.profile_version == PROFILE
    report = rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).report
    assert report["passed"] and not report["content_acceptance_required"]
    assert report["publication_mode"] == "automatic"
    assert report["profile_version"] == PROFILE
    assert report["changed_prose_slots"] == ["/blocks/0/text", "/blocks/1/text"]
    reviewed = rewrite.rewrite_ordered_document(source, client=Draft(payload), context={}, profile_version="full-prose-review-v1")
    assert reviewed.error_code is None
    assert result.document["blocks"][0]["block_id"] != reviewed.document["blocks"][0]["block_id"]
    assert rewrite.validate_article_rewrite(source, reviewed.document, profile_version="full-prose-review-v1").report["content_acceptance_required"]


@pytest.mark.parametrize("replacement", ["Remove the cover.", " REMOVE  THE COVER. ", "Remove the cover!"])
def test_automatic_profile_rejects_unchanged_ordinary_prose(replacement):
    source = document("Remove the cover.")
    payload = response(replacement)
    if replacement == source["blocks"][0]["text"]:
        payload["replacements"][0].update(action="retain", reason="Keep accurate source instructions")
    result = run(source, payload)
    assert result.error_code == "REWRITE_UNCHANGED"
    assert result.document == source


def test_technical_only_retention_is_explicit_and_table_stays_exact():
    source = document("25 Nm", "Remove the cover.")
    source["blocks"].append({"block_id":"table", "source_order":3,"type":"table",
        "columns":["Part","Torque"],"rows":[["Cover","25 Nm"]],"evidence_ids":["fixture"]})
    payload = response("25 Nm", "Take the cover off.")
    payload["replacements"][0].update(action="retain", reason="Exact technical specification")
    result = run(source, payload)
    assert result.error_code is None
    report = rewrite.validate_article_rewrite(source, result.document, profile_version=PROFILE).report
    assert report["retained_paths"] == ["/blocks/0/text"]
    assert result.document["blocks"][-1] == dict(source["blocks"][-1], source_order=4)


def test_auto_table_only_introduction_and_saved_response_binding():
    from autodata_ingestion.procedure_rewrite_auto import validate_auto
    source = document()
    source["blocks"] = [{"block_id":"table","source_order":1,"type":"table",
        "columns":["Part","Torque"],"rows":[["Cover","25 Nm"]],"evidence_ids":["fixture"]}]
    payload = response(introduction="The table lists the cover torque of 25 Nm.")
    result = run(source, payload)
    assert result.error_code is None
    assert validate_auto(source, result.document, response=payload).passed
    changed = deepcopy(payload); changed["introduction"] = "Cover torque is listed as 25 Nm."
    assert not validate_auto(source, result.document, response=changed).passed


@pytest.mark.parametrize("mutation", ["number", "order", "missing", "extra", "context"])
def test_automatic_profile_rejects_corrupt_or_incomplete_model_outputs(mutation):
    source = document("Tighten the bolts to 25 Nm.", "Remove the cover.")
    payload = response("The bolts require tightening to 25 Nm.", "Take the cover off.")
    if mutation == "number": payload["replacements"][0]["text"] = "The bolts require tightening to 30 Nm."
    if mutation == "order": payload["replacements"].reverse()
    if mutation == "missing": payload["replacements"].pop()
    if mutation == "extra": payload["replacements"].append(deepcopy(payload["replacements"][0]))
    if mutation == "context": payload["introduction"] = "Use this for the 2012 Audi A3."
    result = run(source, payload)
    assert result.error_code is not None and result.document == source


def test_prompt_asks_for_automatic_full_prose_without_human_review_obligations():
    prompt = json.loads(rewrite.build_rewrite_prompt(document("Remove the cover."), context={}, profile_version=PROFILE))
    assert prompt["profile_version"] == PROFILE
    assert "human" not in " ".join(prompt["rules"]).lower()
    assert "automatically" in " ".join(prompt["rules"]).lower()
    assert prompt["slots"][0]["text"] == "Remove the cover."


def test_prompt_v2_declares_complete_response_rows_and_server_required_actions():
    source = document("Remove the cover.", "25 Nm")
    before = deepcopy(source)
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context={}, profile_version=PROFILE))
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v2"
    assert prompt["response_shape"] == {"introduction": "string", "replacements": [
        {"block_id": "string", "path": "string", "action": "rewrite|retain", "text": "string", "reason": "string"}]}
    assert [slot["required_action"] for slot in prompt["slots"]] == ["rewrite", "rewrite_or_retain"]
    rules = " ".join(prompt["rules"])
    assert 'reason:""' in rules
    assert "exactly five keys" in rules
    assert "punctuation changes alone" in rules
    assert source == before


def test_historical_auto_prompt_digest_remains_exact():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _build_auto_prompt_v1
    prompt = _build_auto_prompt_v1(document("Remove the cover."), context={})
    assert sha256(prompt.encode()).hexdigest() == "cc5ef47228dc07abee81956adabf0de870247950fc3f5867ce6ed8b110f62e51"
    assert json.loads(prompt)["prompt_version"] == "full-prose-auto-prompt-v1"


def test_auto_prompt_hash_accepts_only_exact_server_reconstructions():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _build_auto_prompt_v1, build_auto_prompt, _matches_auto_prompt_hash
    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompts = [_build_auto_prompt_v1(source, context=context), build_auto_prompt(source, context=context)]
    for prompt in prompts:
        digest = sha256(prompt.encode()).hexdigest()
        assert _matches_auto_prompt_hash(source, context=context, prompt_hash=digest)
        assert not _matches_auto_prompt_hash(document("Remove the panel."), context=context, prompt_hash=digest)
        assert not _matches_auto_prompt_hash(source, context={}, prompt_hash=digest)
    for mutation in ("rule", "required_action", "version"):
        changed = json.loads(prompts[1])
        if mutation == "rule": changed["rules"].pop()
        if mutation == "required_action": del changed["slots"][0]["required_action"]
        if mutation == "version": changed["prompt_version"] = "full-prose-auto-prompt-v3"
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert not _matches_auto_prompt_hash(source, context=context, prompt_hash=sha256(encoded.encode()).hexdigest())
    assert not _matches_auto_prompt_hash(source, context=context, prompt_hash="0" * 64)


def test_prompt_v2_response_example_satisfies_strict_existing_renderer():
    source = document("Remove the cover.", "25 Nm")
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context={}, profile_version=PROFILE))
    payload = {"introduction": "The procedure covers removal of the cover.", "replacements": []}
    for slot, text in zip(prompt["slots"], ["Take the cover off.", "25 Nm"]):
        row = {key: "" for key in prompt["response_shape"]["replacements"][0]}
        row.update(block_id=slot["block_id"], path=slot["path"], text=text,
                   action="rewrite" if slot["required_action"] == "rewrite" else "retain")
        if row["action"] == "retain": row["reason"] = "Exact technical specification"
        payload["replacements"].append(row)
    assert run(source, payload).error_code is None
    del payload["replacements"][0]["reason"]
    assert run(source, payload).error_code == "REWRITE_SLOT_MISMATCH"


def zero_slot_document():
    """Synthetic shape of the failed proof; no production text or references."""
    source = document()
    source["title"] = "Cover service references"
    kinds = ["callout"] * 35 + ["heading"] * 24 + ["link"] * 4
    source["blocks"] = [
        {"block_id": f"protected-{i}", "source_order": i + 1, "type": kind,
         "text": "Cover service references", "evidence_ids": ["fixture-evidence"]}
        for i, kind in enumerate(kinds)
    ]
    return source


def test_zero_slot_prompt_v3_requests_only_source_introduction_without_routing():
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    source = zero_slot_document()
    before = deepcopy(source)
    context = {"vehicle": "2099 RoutingModel CTX-99"}
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context=context, profile_version=PROFILE))
    assert len(source["blocks"]) == 63 and prose_slots(source) == []
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v3"
    assert prompt["replacement_count"] == 0 and prompt["slots"] == []
    assert prompt["response_shape"] == {"introduction": "string", "replacements": []}
    assert "context" not in prompt and "RoutingModel" not in json.dumps(prompt)
    rules = " ".join(prompt["rules"])
    assert '"replacements":[]' in rules
    assert "Do not invent replacement rows" in rules
    assert "document is the only source of facts" in rules
    assert "numeric, identifier or reference facts" in rules
    assert prompt["document"] == source == before


def test_zero_slot_output_preserves_all_protected_content_and_saved_response_binding():
    from autodata_ingestion.procedure_rewrite_auto import validate_auto
    source = zero_slot_document()
    before = deepcopy(source)
    payload = response(introduction="The article provides cover service references.")
    result = run(source, payload)
    assert result.error_code is None
    assert validate_auto(source, result.document, response=payload).passed
    restored = deepcopy(result.document)
    restored["blocks"].pop(0)
    for block in restored["blocks"]:
        block["source_order"] -= 1
    assert digest_json(restored) == digest_json(source)
    assert source == before
    changed = deepcopy(payload)
    changed["introduction"] = "Cover service references are provided here."
    assert not validate_auto(source, result.document, response=changed).passed
    report = validate_auto(source, result.document, response=payload).report
    assert report["complete_rewrite"] is False


@pytest.mark.parametrize("mutation", ["fabricated_slot", "numeric", "identifier", "third_key"])
def test_zero_slot_output_still_rejects_fabricated_slots_and_unsupported_facts(mutation):
    source = zero_slot_document()
    payload = response(introduction="The article provides cover service references.")
    if mutation == "fabricated_slot":
        payload["replacements"] = response("Reword this protected heading.")["replacements"]
    elif mutation == "numeric":
        payload["introduction"] = "The cover requires 99 Nm."
    elif mutation == "identifier":
        payload["introduction"] = "Use tool UNSUPPORTED-99 for cover service."
    else:
        payload["replacement_count"] = 0
    result = run(source, payload)
    assert result.error_code == {
        "fabricated_slot": "REWRITE_SLOT_MISMATCH", "numeric": "REWRITE_TECHNICAL_MUTATION",
        "identifier": "REWRITE_TECHNICAL_MUTATION", "third_key": "REWRITE_RESPONSE_INVALID",
    }[mutation]
    assert result.document == source


def test_zero_slot_historical_prompt_reconstruction_and_current_routing_omission():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import (
        _build_auto_prompt_v1, _build_auto_prompt_v2, build_auto_prompt, _matches_auto_prompt_hash,
    )
    source = zero_slot_document()
    context = {"vehicle": "routing-only"}
    historical = [(_build_auto_prompt_v1, "ce519878922481405f40028c3af5ebf2ff742af5bab96126ea21650311d67ea0"),
                  (_build_auto_prompt_v2, "e1fb10033d5aec793c15dda664767656be5530d380972e76bf48a2bb5d2ee3f5")]
    for builder, expected in historical:
        digest = sha256(builder(source, context=context).encode()).hexdigest()
        assert digest == expected
        assert _matches_auto_prompt_hash(source, context=context, prompt_hash=digest)
        assert not _matches_auto_prompt_hash(source, context={}, prompt_hash=digest)
    current = build_auto_prompt(source, context=context)
    digest = sha256(current.encode()).hexdigest()
    assert current == build_auto_prompt(source, context={"vehicle": "other routing"})
    assert _matches_auto_prompt_hash(source, context={}, prompt_hash=digest)
    changed_source = deepcopy(source)
    changed_source["blocks"][0]["text"] = "Other protected content"
    assert not _matches_auto_prompt_hash(changed_source, context=context, prompt_hash=digest)
    for key, value in [("replacement_count", 1), ("prompt_version", "unrecognized"),
                       ("response_shape", {"introduction": "string", "replacements": [{}]})]:
        changed = json.loads(current)
        changed[key] = value
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert not _matches_auto_prompt_hash(source, context=context, prompt_hash=sha256(encoded.encode()).hexdigest())


def test_nonzero_slot_prompt_remains_exact_v2_bytes():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _build_auto_prompt_v2, build_auto_prompt
    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompt = build_auto_prompt(source, context=context)
    assert prompt == _build_auto_prompt_v2(source, context=context)
    assert sha256(prompt.encode()).hexdigest() == "d972668e5934f6f66dee2ead79ee6bd45e4ca3c98e4f8fb94128fa330cdd22b6"
