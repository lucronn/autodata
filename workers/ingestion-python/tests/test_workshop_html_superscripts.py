"""Capture authored numeric superscripts without changing the stored source bytes."""

from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

import pytest

from autodata_ingestion import source_article_capture
from autodata_ingestion.article_document import build_ordered_document, validate_ordered_document
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.banktwo_connector import ArticleParser
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite import build_rewrite_prompt, rewrite_ordered_document
from autodata_ingestion.procedure_rewrite_auto import (
    _build_auto_prompt_v55, render_auto, require_current_publication_checks, validate_auto,
)
from autodata_ingestion.source_job_persistence import refresh_article_job
from lifecycle_support import fresh_database, runtime
from test_procedure_rewrite_full import Draft
from test_source_article_capture import capture_fixture


_LAYOUT = "html_numeric_superscript_layout"
_OPENING = "Remove the cover."
_MEASUREMENT = "Apply 1.2 × 10³ Pa to the fixture."
_LEGACY_MEASUREMENT = "Apply 1.2 × 103 Pa to the fixture."
_WARNING = "Warning: Do not exceed 2 × 10⁻³ Pa."
_CLOSING = "Install the cover."
_PROFILE = "full-prose-auto-v1"
_PARAPHRASES = {_OPENING: "Take off the cover.", _CLOSING: "Fit the cover."}
_ARTICLE_HTML = (
    f"<p>{_OPENING}</p>"
    "<p>Apply 1.2 × 10<sup>3</sup> Pa to the fixture.</p>"
    "<p>Warning: Do not exceed 2 × 10<sup><em>&minus;</em>3</sup> Pa.</p>"
    "<table><tr><td>Seal area</td><td>4 m<sup>2</sup></td></tr></table>"
    f"<p>{_CLOSING}</p>"
)


def _supplier_payload(media_type, html):
    if media_type == "application/hal+json":
        return json.dumps({"_embedded": {"data": {"article": {"body": html}}}}).encode()
    return html.encode()


def _capture_pair(fixture, provider, media_type, html):
    payload = _supplier_payload(media_type, html)
    fixture.body(provider, payload, media_type)
    context = fixture.context(provider)
    options = dict(registry=fixture.registry, object_store=fixture.objects, keep_bound_pdf_iframes=True)
    previous = source_article_capture.capture_source_article(context, **options)
    current = source_article_capture.capture_source_article(context, keep_html_numeric_superscripts=True, **options)
    return previous, current, payload


def _resource_identity(record):
    return {key: value for key, value in record.items() if key not in {"request_id", "fetched_at"}}


def _reply(slots):
    return {"introduction": "This procedure covers cover removal and installation.", "replacements": [
        {"block_id": slot["block_id"], "path": slot["path"],
         "action": slot["required_action"], "text": _PARAPHRASES.get(slot["text"], slot["text"]),
         "reason": "Keep the authored measurement or warning." if slot["required_action"] == "retain" else ""}
        for slot in slots
    ]}


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("media_type", ["text/html", "application/hal+json"], ids=["HTML", "HAL"])
def test_numeric_superscripts_survive_both_supplier_capture_and_rewrite(capture_fixture, provider, media_type):
    previous, current, payload = _capture_pair(capture_fixture, provider, media_type, _ARTICLE_HTML)
    assert current.projection_status == "readable"
    assert current.body_source_snapshot_id == previous.body_source_snapshot_id
    assert current.evidence_manifest == previous.evidence_manifest
    assert current.source_fingerprint != previous.source_fingerprint
    for before, after in (
        (previous.resources[0], current.resources[0]),
        (previous.resource_manifest[0], current.resource_manifest[0]),
        (previous.resource_provenance[0], current.resource_provenance[0]),
    ):
        assert _LAYOUT not in before
        assert _resource_identity(after) == {**_resource_identity(before), _LAYOUT: "html-numeric-superscript-v1"}
    resource = current.resources[0]
    assert resource["sha256"] == sha256(payload).hexdigest()
    assert capture_fixture.objects.data[resource["object_key"]] == (payload, media_type)
    assert previous.source_body.splitlines() == [
        _OPENING, _LEGACY_MEASUREMENT, "Warning: Do not exceed 2 × 10−3 Pa.",
        "Seal area", "4 m2", _CLOSING,
    ]
    assert current.source_body.splitlines() == [_OPENING, _MEASUREMENT, _WARNING, "Seal area", "4 m²", _CLOSING]
    document = normalize_procedure_article(
        {"normalized_document": current.source_document, "body": current.source_body, "steps": current.source_steps},
        resource_manifest=current.resource_manifest,
    )["normalized_document"]
    assert document == current.source_document
    assert not validate_ordered_document(document, strict=True)
    assert [(block["type"], block.get("text")) for block in document["blocks"]] == [
        ("paragraph", _OPENING), ("paragraph", _MEASUREMENT), ("paragraph", _WARNING),
        ("table", None), ("paragraph", _CLOSING),
    ]
    assert document["blocks"][3]["rows"] == [["Seal area", "4 m²"]]

    prompt = json.loads(build_rewrite_prompt(document, context={}, profile_version=_PROFILE))
    assert {slot["text"]: slot["required_action"] for slot in prompt["slots"]} == {
        _OPENING: "rewrite", _MEASUREMENT: "retain", _WARNING: "retain", _CLOSING: "rewrite",
    }
    reply = _reply(prompt["slots"])
    invalid = deepcopy(reply)
    bad_measurement = next(row for row in invalid["replacements"] if row["text"] == _MEASUREMENT)
    bad_measurement.update(action="rewrite", text=_LEGACY_MEASUREMENT, reason="")
    rejected = rewrite_ordered_document(document, client=Draft(invalid), context={}, profile_version=_PROFILE)
    assert rejected.error_code == "REWRITE_TECHNICAL_AMBIGUOUS"
    assert rejected.document == document

    accepted = rewrite_ordered_document(document, client=Draft(reply), context={}, profile_version=_PROFILE)
    assert accepted.error_code is None
    expected_blocks = deepcopy(document["blocks"])
    for block in expected_blocks:
        block["source_order"] += 1
        if block.get("text") in _PARAPHRASES:
            block["text"] = _PARAPHRASES[block["text"]]
    assert accepted.document["blocks"][1:] == expected_blocks


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("media_type", ["text/html", "application/hal+json"], ids=["HTML", "HAL"])
def test_decimal_fractional_and_spaced_sign_superscripts_survive_rewrite(capture_fixture, provider, media_type):
    html = (
        f"<p>{_OPENING}</p>"
        "<p>Use 10<sup>0.5</sup> Pa for the reference pressure.</p>"
        "<p>Set the reference pressure to 10<sup>1/2</sup> Pa.</p>"
        "<p>Measure leakage at 10<sup>− 3</sup> Pa.</p>"
        f"<p>{_CLOSING}</p>"
    )
    previous, current, _ = _capture_pair(capture_fixture, provider, media_type, html)
    decimal = "Use 10^(0.5) Pa for the reference pressure."
    fraction = "Set the reference pressure to 10^(1/2) Pa."
    signed = "Measure leakage at 10⁻³ Pa."
    expected = [_OPENING, decimal, fraction, signed, _CLOSING]
    assert current.body_source_snapshot_id == previous.body_source_snapshot_id
    assert current.source_fingerprint != previous.source_fingerprint
    assert current.source_body.splitlines() == expected
    document = current.source_document
    assert [block["text"] for block in document["blocks"]] == expected

    prompt = json.loads(build_rewrite_prompt(document, context={}, profile_version=_PROFILE))
    assert [(slot["text"], slot["required_action"]) for slot in prompt["slots"]] == [
        (_OPENING, "rewrite"), (decimal, "retain"), (fraction, "retain"),
        (signed, "retain"), (_CLOSING, "rewrite"),
    ]
    reply = _reply(prompt["slots"])
    flattened = previous.source_body.splitlines()[2]
    assert flattened == "Set the reference pressure to 101/2 Pa."
    for mutated in (flattened, fraction.replace("^", ""), fraction.replace("1/2", "1/3")):
        invalid = deepcopy(reply)
        row = next(row for row in invalid["replacements"] if row["text"] == fraction)
        row.update(action="rewrite", text=mutated, reason="")
        rejected = rewrite_ordered_document(document, client=Draft(invalid), context={}, profile_version=_PROFILE)
        assert rejected.error_code in {"REWRITE_TECHNICAL_AMBIGUOUS", "REWRITE_TECHNICAL_MUTATION"}
        assert rejected.document == document

    accepted = rewrite_ordered_document(document, client=Draft(reply), context={}, profile_version=_PROFILE)
    assert accepted.error_code is None
    assert [block["text"] for block in accepted.document["blocks"][1:]] == [
        _PARAPHRASES[_OPENING], decimal, fraction, signed, _PARAPHRASES[_CLOSING],
    ]


def test_numeric_superscript_scope_survives_line_break_and_ends_at_block_boundary():
    parser = ArticleParser(keep_html_numeric_superscripts=True)
    parser.feed("<p>Code<sup>3<br>2</sup>.</p><p>Index<sup>4</p><p>12</p>")
    parser.close()
    assert [block["text"] for block in parser.blocks] == ["Code³", "².", "Index⁴", "12"]


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("media_type", ["text/html", "application/hal+json"], ids=["HTML", "HAL"])
def test_unaffected_html_keeps_historical_capture_identity(capture_fixture, provider, media_type):
    html = (
        "<p>Inspect the seal.<sup></sup></p>"
        "<script>Hidden script 10<sup>5</sup></script>"
        '<object type="application/pdf" data="/fixture/unbound.pdf">Hidden fallback 10<sup>6</sup></object>'
        "<p>Existing exponent 7⁴.</p><p>Refer to <sup>note A</sup>.</p>"
    )
    previous, current, _ = _capture_pair(capture_fixture, provider, media_type, html)
    assert current.source_body.splitlines() == ["Inspect the seal.", "Existing exponent 7⁴.", "Refer to note A."]
    assert current.source_document == previous.source_document
    assert current.source_fingerprint == previous.source_fingerprint
    assert current.projection_version == previous.projection_version
    assert tuple(map(_resource_identity, current.resources)) == tuple(map(_resource_identity, previous.resources))
    assert current.resource_manifest == previous.resource_manifest
    assert [_resource_identity(record) for record in current.resource_provenance] == [
        _resource_identity(record) for record in previous.resource_provenance
    ]
    assert _LAYOUT not in current.resource_manifest[0]


def test_first_publication_rechecks_fractional_exponents_from_v55():
    source = build_ordered_document(
        {"article_id": "fixture", "evidence_ids": ["source:fixture"]},
        [{"kind": "text", "text": "Fixture scale factor: 10^(0.5)."}],
    )
    prompt = json.loads(_build_auto_prompt_v55(source, context={}))
    [slot] = prompt["slots"]
    assert slot["required_action"] == "rewrite"
    response = {
        "introduction": "This procedure covers the fixture.",
        "replacements": [{
            "block_id": slot["block_id"], "path": slot["path"], "action": "rewrite",
            "text": "The calibration multiplier for this fixture reads 10, 0.5.", "reason": "",
        }],
    }
    version = prompt["prompt_version"]
    candidate = render_auto(source, response, prompt_version=version)
    historical = validate_auto(source, candidate, response=response, prompt_version=version)
    assert historical.passed and historical.report["validator_version"] == "full-prose-auto-validator-v53"
    with pytest.raises(ValueError, match="REWRITE_TECHNICAL_AMBIGUOUS"):
        require_current_publication_checks(source, candidate, saved_prompt_version=version)


class _LifecycleDraft:
    _model = "fixture-superscript-draft"

    def __init__(self):
        self.calls = 0

    def complete_json(self, prompt):
        self.calls += 1
        return _reply(json.loads(prompt)["slots"])


@pytest.mark.parametrize("provider,media_type", [("bankone", "text/html"), ("banktwo", "application/hal+json")])
def test_same_body_refresh_publishes_corrected_superscripts_and_keeps_old_revisions(
    runtime, monkeypatch, provider, media_type
):
    runtime.article_id = runtime.articles[provider]
    payload = _supplier_payload(media_type, _ARTICLE_HTML)
    runtime.servers[provider].body(payload, media_type)
    model = _LifecycleDraft()
    capture = source_article_capture.capture_source_article

    def legacy_capture(*args, **kwargs):
        return capture(*args, **{**kwargs, "keep_html_numeric_superscripts": False})

    def revisions(view):
        with runtime.repo.connect() as conn:
            source = conn.execute(
                "SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                (view["source_revision_id"],),
            ).fetchone()
            canonical = conn.execute(
                "SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                (view["canonical_revision_id"],),
            ).fetchone()
        return source, canonical

    def refresh():
        job = refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="verify authored exponents",
                                  rewrite_profile_version=_PROFILE)
        assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=model, job_id=job.job_id)
        view = runtime.read_current()
        assert view["content_origin"] == "canonical", runtime.diagnostics()
        return view

    with monkeypatch.context() as legacy:
        legacy.setattr(source_article_capture, "capture_source_article", legacy_capture)
        old = refresh()
    old_source, old_canonical = revisions(old)
    assert _LEGACY_MEASUREMENT in old_source["source_body"]
    assert old_canonical["canonical_document"]["blocks"][2]["text"] == _LEGACY_MEASUREMENT

    corrected = refresh()
    source, canonical = revisions(corrected)
    assert corrected["source_revision_id"] != old["source_revision_id"]
    assert corrected["canonical_revision_id"] != old["canonical_revision_id"]
    assert source["body_source_snapshot_id"] == old_source["body_source_snapshot_id"]
    assert source["resource_manifest"][0] == {
        **old_source["resource_manifest"][0], _LAYOUT: "html-numeric-superscript-v1",
    }
    assert _MEASUREMENT in source["source_body"]
    blocks = canonical["canonical_document"]["blocks"]
    assert [block.get("text") for block in blocks[1:]] == [
        _PARAPHRASES[_OPENING], _MEASUREMENT, _WARNING, None, _PARAPHRASES[_CLOSING],
    ]
    assert blocks[4]["rows"] == [["Seal area", "4 m²"]]
    repeated = refresh()
    assert repeated["source_revision_id"] == corrected["source_revision_id"]
    assert repeated["canonical_revision_id"] == corrected["canonical_revision_id"]
    assert revisions(repeated) == (source, canonical)
    assert revisions(old) == (old_source, old_canonical)
    assert model.calls == 2
