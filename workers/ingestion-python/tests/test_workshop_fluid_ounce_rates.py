"""Keep authored fluid-ounce rates exact through automatic Workshop rewriting."""

from hashlib import sha256
import json

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_document import project_ordered_document
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.source_article_capture import capture_source_article
from test_procedure_rewrite_auto import run
from test_procedure_rewrite_full import document, response
from test_source_article_capture import capture_fixture


_OPENING = "Remove the cover."
_REWRITTEN = "Take off the cover."
_CLOSING = "Install the replacement."
_REWRITTEN_CLOSING = "Fit the replacement unit."
_VOLUME = "The rinse reservoir contains 14 fl oz of water."
_OLD_FLOW = "Set the return line flow rate to a maximum of 14 L/min."
_OUNCE_FLOW = "The feed pump moves 14 fl oz per minute."
_CHANGED_FLOW = "The feed pump moves 14 fl oz per second."
_INTRODUCTION = "This article describes access to the cover."
_RETAIN_REASON = "Preserve the complete flow limit."
_SCOPE_ERROR = "REWRITE_SPEC_SCOPE_MUTATION"
_V55 = "full-prose-auto-prompt-v55"
_V56 = "full-prose-auto-prompt-v56"
_V57 = "full-prose-auto-prompt-v57"
_V58 = "full-prose-auto-prompt-v58"


@pytest.mark.parametrize(("rate", "changed_rate"), [
    ("fl oz per minute", "fl oz per second"),
    ("fl. oz. per minute", "fl. oz. per second"),
    ("fl. oz./min", "fl. oz./s"),
    ("US fluid ounces per minute", "US fluid ounces per second"),
    ("Imperial fluid ounces per minute", "Imperial fluid ounces per second"),
    ("fl oz of brake fluid per minute", "fl oz of brake fluid per second"),
    ("fl oz of hydraulic oil per minute", "fl oz of hydraulic oil per second"),
    ("fl oz of automatic transmission fluid every minute", "fl oz of automatic transmission fluid every second"),
    ("fl oz (US) per minute", "fl oz (US) per second"),
    ("fluid oz per minute", "fluid oz per second"),
    ("fl. ounces per minute", "fl. ounces per second"),
])
def test_fluid_ounce_rate_requires_exact_retention(rate, changed_rate):
    original = f"The feed pump moves at most 14 {rate}."
    source = document(_OPENING, original)
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["prompt_version"] == _V58
    assert [slot["required_action"] for slot in prompt["slots"]] == ["rewrite", "retain"]

    mutations = (
        f"The feed pump moves at most 14 {changed_rate}.",
        original.replace("at most", "at least"),
    )
    for changed in mutations:
        rejected = run(source, response(_REWRITTEN, changed))
        assert rejected.error_code == _SCOPE_ERROR
        assert rejected.document == source

    payload = response(_REWRITTEN, original)
    payload["replacements"][-1].update(action="retain", reason=_RETAIN_REASON)
    accepted = run(source, payload)
    assert accepted.error_code is None
    assert accepted.document["blocks"][-1]["text"] == original
    report = auto.validate_auto(source, accepted.document, response=payload, prompt_version=_V58)
    assert report.passed
    assert report.report["retained_paths"] == [prompt["slots"][-1]["path"]]


@pytest.mark.parametrize("location", ["prose", "introduction"])
def test_plain_fluid_ounce_quantity_cannot_acquire_a_rate(location):
    source = document(_OPENING, _VOLUME)
    ordinary = "The rinse reservoir holds 14 fl oz of water."
    if location == "prose":
        payload = response(_REWRITTEN, f"{ordinary[:-1]} per second.")
    else:
        payload = response(_REWRITTEN, ordinary, introduction=f"{_VOLUME[:-1]} per second.")
    assert json.loads(auto.build_auto_prompt(source, context={}))["prompt_version"] == _V55

    rejected = run(source, payload)
    assert rejected.error_code == _SCOPE_ERROR
    assert rejected.document == source

    previous = auto.render_auto(source, payload, prompt_version=_V55)
    assert auto.validate_auto(source, previous, response=payload, prompt_version=_V55).passed
    with pytest.raises(ValueError, match=f"^{_SCOPE_ERROR}$"):
        auto.require_current_publication_checks(source, previous, saved_prompt_version=_V55)


@pytest.mark.parametrize(("text", "version", "prompt_hash"), [
    (_VOLUME, _V55, "f6f2bb3f248c3c369c429cbddff90bdc0bf10be7c871af5a89b39a2c9096f0f1"),
    ("Apply 1.2 × 10³ Pa to the fixture.", _V56, "5d23a44654a1315ef1c44e23aabb29c1978b34dc7be874e28683a8446b75ddf1"),
    (_OLD_FLOW, _V57, "e78b0a746af27b7c438aa1c90d7d463c5943e54cd1dad43213a6eb64e9f16055"),
])
def test_prior_prompt_bytes_without_an_authored_fluid_ounce_rate(text, version, prompt_hash):
    # Prompt hashes are from cb983d4 before fluid-ounce rates were recognized.
    prompt = auto.build_auto_prompt(document(_OPENING, text), context={})
    assert json.loads(prompt)["prompt_version"] == version
    assert sha256(prompt.encode()).hexdigest() == prompt_hash


def test_v57_saved_draft_replays_exactly_and_fails_current_first_publication():
    source = document(_OPENING, _OLD_FLOW, _OUNCE_FLOW)
    payload = response(_REWRITTEN, _OLD_FLOW, _CHANGED_FLOW)
    payload["replacements"][1].update(action="retain", reason=_RETAIN_REASON)
    before_prompt_hash = "e403fafefa4ca7127f73fa461d72bd98a58c23f9c719c42fe30d26c8d8e27b4e"

    current = json.loads(auto.build_auto_prompt(source, context={}))
    assert current["prompt_version"] == _V58
    assert [slot["required_action"] for slot in current["slots"]] == ["rewrite", "retain", "retain"]
    assert auto._auto_prompt_version(source, context={}, prompt_hash=before_prompt_hash) == _V57

    previous = auto.render_auto(source, payload, prompt_version=_V57)
    report = auto.validate_auto(source, previous, response=payload, prompt_version=_V57)
    assert report.passed
    # The rendered document and report digests are also from cb983d4.
    assert digest_json(previous) == "0f8f519f1b589ab8095f8bedfff7d142a0768c93b64f0e9d27dee70270de1168"
    assert digest_json(report.report) == "d181cae58dfcb752438e9b84126e9fd892aa0a5faf5efb43aa0045ecf8292878"

    assert auto.validate_auto(source, previous, response=payload).error_codes == (_SCOPE_ERROR,)
    with pytest.raises(ValueError, match=f"^{_SCOPE_ERROR}$"):
        auto.require_current_publication_checks(source, previous, saved_prompt_version=_V57)


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_fluid_ounce_rate_survives_capture_between_distinct_prose(capture_fixture, provider):
    source_lines = (_OPENING, _OUNCE_FLOW, _CLOSING)
    if provider == "bankone":
        raw = json.dumps({"blocks": [{"kind": "text", "text": line} for line in source_lines]}).encode()
        media_type = "application/json"
    else:
        raw = "".join(f"<p>{line}</p>" for line in source_lines).encode()
        media_type = "text/html"
    capture_fixture.body(provider, raw, media_type)
    captured = capture_source_article(
        capture_fixture.context(provider), registry=capture_fixture.registry, object_store=capture_fixture.objects,
    )
    assert captured.source_body.splitlines() == list(source_lines)
    [body] = captured.resources
    assert body["sha256"] == sha256(raw).hexdigest()
    assert capture_fixture.objects.data[body["object_key"]] == (raw, media_type)

    source = captured.source_document
    prompt = json.loads(auto.build_auto_prompt(source, context={}))
    assert prompt["prompt_version"] == _V58
    assert [slot["required_action"] for slot in prompt["slots"]] == ["rewrite", "retain", "rewrite"]
    output = (_REWRITTEN, _OUNCE_FLOW, _REWRITTEN_CLOSING)
    payload = {
        "introduction": _INTRODUCTION,
        "replacements": [
            {
                "block_id": slot["block_id"], "path": slot["path"], "action": slot["required_action"], "text": text,
                "reason": _RETAIN_REASON if slot["required_action"] == "retain" else "",
            }
            for slot, text in zip(prompt["slots"], output, strict=True)
        ],
    }
    rewritten = run(source, payload)
    assert rewritten.error_code is None
    assert project_ordered_document(rewritten.document)["body"].splitlines() == [_INTRODUCTION, *output]
    assert rewritten.document["blocks"][2]["evidence_ids"] == source["blocks"][1]["evidence_ids"]
