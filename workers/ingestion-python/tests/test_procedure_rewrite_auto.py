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


@pytest.mark.parametrize(("source_text", "replacement"), [
    (
        "After the cap comes off, gently slide the cable from the guide beside the outer bracket.",
        "Once the cap comes off, gently slide the cable from the guide beside the outer bracket.",
    ),
    (
        "Release the latch, slide the cable along the inner guide and lift it out by hand.",
        "Open the clip, slide the cable along the inner guide and lift it out manually.",
    ),
    ("Remove the cap.", "First, remove the cap."),
    ("Remove the cap.", "Remove the cap before proceeding."),
    ("Remove the cap before proceeding.", "Remove the cap."),
])
def test_automatic_profile_rejects_near_verbatim_ordinary_prose(source_text, replacement):
    source = document(source_text)
    result = run(source, response(replacement))
    assert result.error_code == "REWRITE_PROSE_TOO_SIMILAR"
    assert result.document == source


@pytest.mark.parametrize("warning", [
    "Never connect the battery while the connector is wet.",
    "Warning: Wear eye protection during this procedure.",
    "Inspect the cable, but do not connect the battery yet.",
    "The battery cannot be connected while the connector is wet.",
])
def test_automatic_profile_retains_inline_safety_instruction(warning):
    source = document(warning, "Remove the cover.")
    payload = response("Reconnect the battery before drying the connector.", "Take the cover off.")
    assert run(source, payload).error_code == "REWRITE_SAFETY_MUTATION"
    payload["replacements"][0].update(action="retain", text=warning, reason="Exact safety wording")
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == warning


def test_current_and_historical_validation_bind_their_own_prose_rules():
    from autodata_ingestion import procedure_rewrite_auto as auto
    from autodata_ingestion.procedure_rewrite_full import render_full

    source = document("Remove the cover.")
    payload = response("First, remove the cover.")
    candidate = render_full(source, payload, profile_version=PROFILE)
    historical = auto.validate_auto(source, candidate, response=payload, prompt_version="full-prose-auto-prompt-v2")
    assert historical.passed
    assert historical.report["validator_version"] == "full-prose-auto-validator-v1"
    for bound_response in (payload, None):
        current = auto.validate_auto(source, candidate, response=bound_response, prompt_version="full-prose-auto-prompt-v4")
        assert current.error_codes == ("REWRITE_PROSE_TOO_SIMILAR",)
        assert current.report["validator_version"] == "full-prose-auto-validator-v2"


def test_ordinary_text_cannot_be_reduced_to_its_specification():
    source = document("Tighten the bolts to 25 Nm.")
    result = run(source, response("25 Nm."))
    assert result.error_code == "REWRITE_PROSE_MISSING"
    assert result.document == source


def test_automatic_profile_rejects_new_inline_warning_or_prohibition():
    source = document("Remove the cover.")
    for payload in (
        response("Never take the cover off."),
        response("Take the cover off.", introduction="Do not take the cover off."),
    ):
        result = run(source, payload)
        assert result.error_code == "REWRITE_SAFETY_MUTATION"
        assert result.document == source


def test_distinct_prose_preserves_action_order_facts_and_source_blocks():
    source = document(
        "After removing the cover, inspect the cable to check whether the guide is secure.",
        "Use tool T-42 to tighten the cover bolts evenly to 25 Nm after seating the gasket.",
    )
    source["blocks"].extend([
        {"block_id": "warning", "source_order": 3, "type": "callout",
         "text": "Before work, isolate the battery.", "evidence_ids": ["safety-evidence"]},
        {"block_id": "image", "source_order": 4, "type": "image",
         "status": "unavailable", "unavailable_reason": "fixture", "evidence_ids": ["media-evidence"]},
    ])
    replacements = (
        "Take the cover off before checking that the cable guide is firmly attached.",
        "With tool T-42, bring the cover bolts up to 25 Nm uniformly once the gasket is seated.",
    )
    result = run(source, response(*replacements))
    assert result.error_code is None
    assert [block["source_order"] for block in result.document["blocks"]] == [1, 2, 3, 4, 5]
    for original, rendered, text in zip(source["blocks"][:2], result.document["blocks"][1:3], replacements):
        assert rendered == dict(original, source_order=original["source_order"] + 1, text=text)
    for original, rendered in zip(source["blocks"][2:], result.document["blocks"][3:]):
        assert rendered == dict(original, source_order=original["source_order"] + 1)


@pytest.mark.parametrize("source_text,draft,code", [
    ("Avoid reconnecting the battery while the connector is wet.",
     "Reconnect the battery before drying the connector.", "REWRITE_SAFETY_MUTATION"),
    ("The battery needs to stay disconnected until the connector is dry.",
     "Let the connector dry while the battery is attached.", "REWRITE_SAFETY_MUTATION"),
    ("Tighten the cover to 7 Nm only after the seal sits flush.",
     "Set the cover torque to 7 Nm.", "REWRITE_SAFETY_MUTATION"),
    ("Fit the connector cover unless the harness is damaged.",
     "Install the connector cover.", "REWRITE_SAFETY_MUTATION"),
    ("Disconnect the battery before handling the connector.",
     "Attach the battery ahead of connector service.", "REWRITE_ACTION_MUTATION"),
    ("Tighten the connector cover screws to 7 Nm.",
     "Loosen the connector cover screws until they reach 7 Nm.", "REWRITE_ACTION_MUTATION"),
    ("First disconnect the battery, then remove the connector cover.",
     "Take the connector cover off before detaching the battery.", "REWRITE_ACTION_MUTATION"),
    ("Remove the connector cover.",
     "Take the cover off the connector and start the engine.", "REWRITE_ACTION_MUTATION"),
    ("Check that the guide clips are attached.",
     "Inspect whether the guide clips hold firmly and start the engine.", "REWRITE_ACTION_MUTATION"),
])
def test_automatic_rewrite_rejects_changed_safety_conditions_and_recognizable_actions(source_text, draft, code):
    source = document(source_text)
    result = run(source, response(draft))
    assert result.error_code == code
    assert result.document == source


def test_prerequisite_remains_verbatim_when_the_other_steps_are_rewritten():
    condition = "Fit the cover only after the seal sits flush."
    source = document(condition, "Inspect the cable.")
    payload = response(condition, "Check the cable for wear.")
    payload["replacements"][0].update(action="retain", reason="Preserve the seal prerequisite.")
    result = run(source, payload)
    assert result.error_code is None
    assert result.document["blocks"][1]["text"] == condition
    assert result.document["blocks"][2]["text"] == "Check the cable for wear."


def test_automatic_rewrite_checks_actions_bound_to_each_slot():
    source = document("Remove the connector cover.", "Inspect the guide.")
    result = run(source, response("Check the guide visually.", "Take the cover off the connector."))
    assert result.error_code == "REWRITE_ACTION_MUTATION"
    assert result.document == source


@pytest.mark.parametrize("source_text,draft", [
    ("First disconnect the battery, then remove the connector cover.",
     "Once power has been isolated at the battery, take the cover off the connector."),
    ("Tighten the connector cover screws to 7 Nm.",
     "Set the connector cover screw torque to 7 Nm."),
    ("Remove the latch cover and inspect the cable.",
     "Check the cable once the latch cover is removed."),
    ("Open the housing before disconnecting the battery.",
     "Detach the battery after opening the housing."),
])
def test_automatic_rewrite_accepts_recognizable_action_paraphrases(source_text, draft):
    result = run(document(source_text), response(draft))
    assert result.error_code is None


@pytest.mark.parametrize("intro", [
    "Start the engine before removing the cover.",
    "This article covers cover access. Then, start the engine.",
    "You should start the engine first.",
    "The engine must be started before this procedure.",
])
def test_automatic_rewrite_rejects_an_imperative_introduction(intro):
    source = document("Remove the connector cover.")
    result = run(source, response("Take the cover off the connector.", introduction=intro))
    assert result.error_code == "REWRITE_INTRODUCTION_INSTRUCTION"
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


def test_prompt_v5_declares_complete_response_rows_and_server_required_actions():
    source = document("Remove the cover.", "25 Nm", "Never start the motor.",
                      "Fit the cover only after the seal sits flush.")
    before = deepcopy(source)
    prompt = json.loads(rewrite.build_rewrite_prompt(source, context={}, profile_version=PROFILE))
    assert prompt["prompt_version"] == "full-prose-auto-prompt-v5"
    assert prompt["response_shape"] == {"introduction": "string", "replacements": [
        {"block_id": "string", "path": "string", "action": "rewrite|retain", "text": "string", "reason": "string"}]}
    assert [slot["required_action"] for slot in prompt["slots"]] == ["rewrite", "rewrite_or_retain", "retain", "retain"]
    rules = " ".join(prompt["rules"])
    assert 'reason:""' in rules
    assert "exactly five keys" in rules
    assert "copying long phrases" in rules
    assert source == before


def test_historical_auto_prompt_digest_remains_exact():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _build_auto_prompt_v1
    prompt = _build_auto_prompt_v1(document("Remove the cover."), context={})
    assert sha256(prompt.encode()).hexdigest() == "cc5ef47228dc07abee81956adabf0de870247950fc3f5867ce6ed8b110f62e51"
    assert json.loads(prompt)["prompt_version"] == "full-prose-auto-prompt-v1"


def test_historical_v4_prompt_digest_and_validation_report_remain_stable():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _auto_prompt_version, _build_auto_prompt_v4, render_auto, validate_auto

    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompt_hash = sha256(_build_auto_prompt_v4(source, context=context).encode()).hexdigest()
    assert prompt_hash == "00e8a399286299d7c8bb588c9c38f10a99895bb4e0f8a252d18c9f4338c21b2d"
    version = _auto_prompt_version(source, context=context, prompt_hash=prompt_hash)
    assert version == "full-prose-auto-prompt-v4"

    # The old validator accepted this changed operation and resulting report.
    payload = response("Fit the cover.")
    candidate = render_auto(source, payload, prompt_version=version)
    historical = validate_auto(source, candidate, response=payload, prompt_version=version)
    assert historical.passed and historical.report["validator_version"] == "full-prose-auto-validator-v2"
    current = validate_auto(source, candidate, response=payload)
    assert current.error_codes == ("REWRITE_ACTION_MUTATION",)
    assert current.report["validator_version"] == "full-prose-auto-validator-v3"


def test_auto_prompt_hash_accepts_only_exact_server_reconstructions():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import (
        _build_auto_prompt_v1, _build_auto_prompt_v2, _build_auto_prompt_v4, _auto_prompt_version, build_auto_prompt,
    )
    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompts = [builder(source, context=context) for builder in
               (_build_auto_prompt_v1, _build_auto_prompt_v2, _build_auto_prompt_v4, build_auto_prompt)]
    for prompt in prompts:
        digest = sha256(prompt.encode()).hexdigest()
        assert _auto_prompt_version(source, context=context, prompt_hash=digest) == json.loads(prompt)["prompt_version"]
        assert not _auto_prompt_version(document("Remove the panel."), context=context, prompt_hash=digest)
        assert not _auto_prompt_version(source, context={}, prompt_hash=digest)
    for mutation in ("rule", "required_action", "version"):
        changed = json.loads(prompts[-1])
        if mutation == "rule": changed["rules"].pop()
        if mutation == "required_action": del changed["slots"][0]["required_action"]
        if mutation == "version": changed["prompt_version"] = "full-prose-auto-prompt-v3"
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert not _auto_prompt_version(source, context=context, prompt_hash=sha256(encoded.encode()).hexdigest())
    assert not _auto_prompt_version(source, context=context, prompt_hash="0" * 64)


def test_prompt_v5_response_example_satisfies_strict_renderer():
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
        _build_auto_prompt_v1, _build_auto_prompt_v2, build_auto_prompt, _auto_prompt_version,
    )
    source = zero_slot_document()
    context = {"vehicle": "routing-only"}
    historical = [(_build_auto_prompt_v1, "ce519878922481405f40028c3af5ebf2ff742af5bab96126ea21650311d67ea0"),
                  (_build_auto_prompt_v2, "e1fb10033d5aec793c15dda664767656be5530d380972e76bf48a2bb5d2ee3f5")]
    for builder, expected in historical:
        digest = sha256(builder(source, context=context).encode()).hexdigest()
        assert digest == expected
        assert _auto_prompt_version(source, context=context, prompt_hash=digest)
        assert not _auto_prompt_version(source, context={}, prompt_hash=digest)
    current = build_auto_prompt(source, context=context)
    digest = sha256(current.encode()).hexdigest()
    assert current == build_auto_prompt(source, context={"vehicle": "other routing"})
    assert _auto_prompt_version(source, context={}, prompt_hash=digest)
    changed_source = deepcopy(source)
    changed_source["blocks"][0]["text"] = "Other protected content"
    assert not _auto_prompt_version(changed_source, context=context, prompt_hash=digest)
    for key, value in [("replacement_count", 1), ("prompt_version", "unrecognized"),
                       ("response_shape", {"introduction": "string", "replacements": [{}]})]:
        changed = json.loads(current)
        changed[key] = value
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert not _auto_prompt_version(source, context=context, prompt_hash=sha256(encoded.encode()).hexdigest())


def test_nonzero_slot_historical_v2_prompt_digest_remains_exact():
    from hashlib import sha256
    from autodata_ingestion.procedure_rewrite_auto import _build_auto_prompt_v2
    source = document("Remove the cover.")
    context = {"vehicle": "routing-only"}
    prompt = _build_auto_prompt_v2(source, context=context)
    assert json.loads(prompt)["prompt_version"] == "full-prose-auto-prompt-v2"
    assert sha256(prompt.encode()).hexdigest() == "d972668e5934f6f66dee2ead79ee6bd45e4ca3c98e4f8fb94128fa330cdd22b6"


def test_server_zero_slot_candidate_is_exact_heading_and_preserves_source():
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document(); before = deepcopy(source)
    candidate, metadata = auto.build_source_preserving_candidate(source)
    heading = next(b['text'] for b in source['blocks'] if b['type'] == 'heading')
    assert candidate['blocks'][0]['text'] == heading
    restored = deepcopy(candidate); restored['blocks'].pop(0)
    for block in restored['blocks']: block['source_order'] -= 1
    assert restored == source == before
    assert metadata == {"transformation_method":"source-preserving-zero-slot-v1",
        "drafting_actor":"server", "model":"server-zero-slot-v1", "profile_version":PROFILE,
        "model_calls":0, "model_dispatch_count":0, "complete_rewrite":False,
        "source_hash":digest_json(source), "output_hash":digest_json(candidate)}
    validation = auto.validate_source_preserving_candidate(source, candidate, metadata)
    assert validation.passed and validation.report['complete_rewrite'] is False
    assert validation.report['introduction_origin'] == 'source_heading'
    assert validation.report['model_dispatch_count'] == 0
    assert auto.build_source_preserving_candidate(source) == (candidate, metadata)


def test_server_zero_slot_skips_ambiguous_heading_without_editing_it():
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document()
    first = next(i for i,b in enumerate(source['blocks']) if b['type']=='heading')
    source['blocks'][first]['text'] = 'Specification ½'
    candidate, metadata = auto.build_source_preserving_candidate(source)
    assert candidate['blocks'][0]['text'] == next(b['text'] for b in source['blocks'][first+1:] if b['type']=='heading')
    assert candidate['blocks'][first+1]['text'] == 'Specification ½'
    assert auto.validate_source_preserving_candidate(source, candidate, metadata).passed


@pytest.mark.parametrize('kind', ['no_heading', 'ambiguous', 'oversize', 'nonzero'])
def test_server_zero_slot_fails_closed_without_an_eligible_heading(kind):
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document()
    if kind == 'nonzero': source = document('Remove the cover.')
    else:
        for b in source['blocks']:
            if b['type'] == 'heading':
                if kind == 'no_heading': b.update(type='callout', label='note'); b.pop('level', None)
                else: b['text'] = 'Specification ½' if kind=='ambiguous' else 'A'*(1024*1024)
    with pytest.raises(ValueError): auto.build_source_preserving_candidate(source)


@pytest.mark.parametrize('mutation', ['candidate', 'source', 'method', 'extra', 'zero_boolean'])
def test_server_zero_slot_revalidation_rejects_tampered_candidate_or_provenance(mutation):
    from autodata_ingestion import procedure_rewrite_auto as auto
    source = zero_slot_document(); candidate, metadata = auto.build_source_preserving_candidate(source)
    if mutation == 'candidate': candidate['blocks'][0]['text'] += ' Unsupported-99'
    elif mutation == 'source': source['blocks'][0]['text'] += ' changed'
    elif mutation == 'method': metadata['transformation_method'] = 'forged'
    elif mutation == 'extra': metadata['prompt_hash'] = '0'*64
    else: metadata['model_calls'] = False
    with pytest.raises(ValueError): auto.validate_source_preserving_candidate(source, candidate, metadata)
