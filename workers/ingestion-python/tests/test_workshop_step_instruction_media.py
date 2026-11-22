"""Verify authored numbered steps keep instructions and retained figures in order."""

from io import BytesIO
import json
from uuid import uuid4

from PIL import Image
import pytest

from autodata_ingestion import source_article_capture
from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_types import ORDERED_STEP_IMAGE_ONLY_LAYOUT, ORDERED_STEP_INSTRUCTIONS_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite_auto import PROFILE, render_auto, validate_auto
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.source_job_persistence import refresh_article_job

from lifecycle_support import fresh_database, runtime
from test_source_article_capture import capture_fixture
from test_workshop_linked_pdf import FixtureDraft, _INTRODUCTION, _PARAPHRASES


_NEW_PROSE = {
    **_PARAPHRASES,
    "Loosen the pump bolts.": "Loosen the bolts on the pump.",
    "Inspect the gasket.": "Check the gasket.",
    "Remove the cover while the ignition is off.": "With the ignition off, take the cover off.",
}


def _supplier_body(provider, *, with_media=True, explicit=False, with_lead=True):
    first = {"instruction": "Inspect the gasket."}
    if with_media:
        first["images"] = [{"asset_resource_ref": "figure", "alt": "Gasket diagram", "caption": "Gasket orientation"}]
    middle = {"instructions": [first, "Remove the cover while the ignition is off."]}
    if with_lead:
        middle["text"] = "Inspect the seal."
    steps = [{"text": "Remove the pump."}, middle, {"text": "Install the replacement."}]
    article = {"steps": steps}
    if explicit:
        article = {"blocks": [{**step, "kind": "step", "number": 6 + index} for index, step in enumerate(steps)]}
    if provider == "banktwo":
        return json.dumps({"_embedded": {"data": {"article": article}}}).encode(), "application/hal+json"
    return json.dumps(article).encode(), "application/json"


def _fixture_png():
    buffer = BytesIO()
    Image.new("RGB", (96, 48), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


def _image_only_supplier_body(provider, *, leading=False):
    raw, media = _supplier_body(provider)
    container = json.loads(raw)
    article = container["_embedded"]["data"]["article"] if provider == "banktwo" else container
    first, target, _ = article["steps"]
    first["instructions"] = ["Loosen the pump bolts."]
    prose, last = target["instructions"]
    media_item = {"images": prose.pop("images")}
    if leading:
        del target["text"]
    target["instructions"] = [media_item, prose, last] if leading else [prose, media_item, last]
    return json.dumps(container).encode(), media


@pytest.mark.parametrize("provider,with_media,available,explicit,with_lead", [
    ("bankone", True, True, False, True), ("banktwo", True, True, False, True),
    ("banktwo", True, False, False, True), ("bankone", False, False, False, True),
    ("banktwo", False, False, True, False),
])
def test_numbered_step_keeps_nested_instruction_order_through_rewrite(
    capture_fixture, provider, with_media, available, explicit, with_lead,
):
    raw, media = _supplier_body(provider, with_media=with_media, explicit=explicit, with_lead=with_lead)
    figure = _fixture_png()
    capture_fixture.body(provider, raw, media, assets=["figure"] if with_media else [])
    if available:
        capture_fixture.body(provider, figure, "image/png", kind="asset", ref="figure")
    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects)
    legacy = source_article_capture.capture_source_article(context, **options)
    corrected = source_article_capture.capture_source_article(context, keep_ordered_step_instructions=True, **options)
    assert legacy.source_fingerprint != corrected.source_fingerprint
    assert legacy.body_source_snapshot_id == corrected.body_source_snapshot_id
    assert corrected.resource_manifest[0]["ordered_step_instructions_layout"] == ORDERED_STEP_INSTRUCTIONS_LAYOUT
    assert corrected.resource_manifest[1:] == legacy.resource_manifest[1:]
    assert corrected.evidence_manifest == legacy.evidence_manifest
    assert not validate_ordered_document(corrected.source_document, strict=True)
    old = legacy.source_document["blocks"][1]
    if with_lead:
        assert old["text"] == "Inspect the seal."
        assert "Inspect the gasket." not in legacy.source_body
    expected = ["Remove the pump."] + (["Inspect the seal."] if with_lead else []) + [
        "Inspect the gasket.", "Remove the cover while the ignition is off.", "Install the replacement.",
    ]
    assert corrected.source_body.splitlines() == expected
    step = corrected.source_document["blocks"][1]
    assert step["type"] == "ordered_list" and step["start"] == (7 if explicit else 2)
    [item] = step["items"]
    assert item["text"] == ("Inspect the seal." if with_lead else "Inspect the gasket.")
    assert [block["type"] for block in item["blocks"]] == (
        (["paragraph"] if with_lead else []) + (["image"] if with_media else []) + ["paragraph"]
    )
    if with_media:
        [image] = corrected.source_images
        assert item["blocks"][1] == image
        assert image["image_id"] == legacy.source_images[0]["image_id"]
        assert image["caption"] == "Gasket orientation"
        if available:
            assert capture_fixture.objects.data[image["storage_key"]] == (figure, "image/png")
        else:
            assert image["status"] == "unavailable" and image["unavailable_reason"] == "SOURCE_NOT_FOUND"

    source = normalize_procedure_article({
        "normalized_document": corrected.source_document, "body": corrected.source_body, "steps": corrected.source_steps,
    }, resource_manifest=corrected.resource_manifest)["normalized_document"]
    slots = prose_slots(source, include_cell_blocks=True)
    assert [slot["text"] for slot in slots] == expected
    model = {"introduction": _INTRODUCTION, "replacements": [
        {**slot, "action": "rewrite", "text": _NEW_PROSE[slot["text"]], "reason": ""} for slot in slots
    ]}
    canonical = render_auto(source, model)
    assert validate_auto(source, canonical, response=model).passed
    canonical_step = canonical["blocks"][2]
    assert canonical_step["start"] == step["start"]
    assert canonical_step["items"][0]["blocks"][-1]["text"] == "With the ignition off, take the cover off."
    if with_media:
        assert canonical_step["items"][0]["blocks"][1] == image


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("leading,available", [(False, True), (True, True), (False, False)])
def test_image_only_instruction_keeps_source_order_and_provenance(capture_fixture, provider, leading, available):
    raw, media = _image_only_supplier_body(provider, leading=leading)
    figure = _fixture_png()
    capture_fixture.body(provider, raw, media, assets=["figure"])
    if available:
        capture_fixture.body(provider, figure, "image/png", kind="asset", ref="figure")
    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects,
                   keep_ordered_step_instructions=True)
    v1 = source_article_capture.capture_source_article(context, **options)
    v2 = source_article_capture.capture_source_article(context, keep_image_only_step_instructions=True, **options)
    assert v1.source_document["blocks"][1]["type"] == "step"
    assert v1.source_document["blocks"][0] == v2.source_document["blocks"][0]
    assert v1.resource_manifest[0]["ordered_step_instructions_layout"] == ORDERED_STEP_INSTRUCTIONS_LAYOUT
    assert v2.resource_manifest[0]["ordered_step_instructions_layout"] == ORDERED_STEP_IMAGE_ONLY_LAYOUT
    assert v1.source_fingerprint != v2.source_fingerprint
    assert v1.body_source_snapshot_id == v2.body_source_snapshot_id
    assert v1.resource_manifest[1:] == v2.resource_manifest[1:]
    assert v1.evidence_manifest == v2.evidence_manifest
    assert not validate_ordered_document(v2.source_document, strict=True)
    step = v2.source_document["blocks"][1]
    assert step["type"] == "ordered_list" and step["start"] == 2
    [item] = step["items"]
    [image] = v2.source_images
    assert image["image_id"] == v1.source_images[0]["image_id"]
    assert image["caption"] == "Gasket orientation"
    if available:
        assert capture_fixture.objects.data[image["storage_key"]] == (figure, "image/png")
    else:
        assert image["status"] == "unavailable" and image["unavailable_reason"] == "SOURCE_NOT_FOUND"
    assert item["text"] == ("" if leading else "Inspect the seal.")
    order = ["image", "paragraph", "paragraph"] if leading else ["paragraph", "image", "paragraph"]
    assert [child["type"] for child in item["blocks"]] == order
    figure_at = order.index("image")
    assert item["blocks"][figure_at] == image

    source = normalize_procedure_article({
        "normalized_document": v2.source_document, "body": v2.source_body, "steps": v2.source_steps,
    }, resource_manifest=v2.resource_manifest)["normalized_document"]
    slots = prose_slots(source, include_cell_blocks=True)
    expected = ["Remove the pump.", "Loosen the pump bolts."]
    if not leading:
        expected.append("Inspect the seal.")
    expected.extend(["Inspect the gasket.", "Remove the cover while the ignition is off.", "Install the replacement."])
    assert [slot["text"] for slot in slots] == expected
    model = {"introduction": _INTRODUCTION, "replacements": [
        {**slot, "action": "rewrite", "text": _NEW_PROSE[slot["text"]], "reason": ""} for slot in slots
    ]}
    canonical = render_auto(source, model)
    assert validate_auto(source, canonical, response=model).passed
    edited = canonical["blocks"][2]["items"][0]["blocks"]
    assert [child["type"] for child in edited] == order
    assert edited[figure_at] == image
    assert edited[-1]["text"] == "With the ignition off, take the cover off."


@pytest.mark.parametrize("image_only", [False, True])
def test_step_instruction_refresh_preserves_old_immutable_revision(runtime, monkeypatch, image_only):
    provider = "banktwo"
    runtime.article_id = runtime.articles[provider]
    raw, media = (_image_only_supplier_body if image_only else _supplier_body)(provider)
    figure = _fixture_png()
    connector = runtime.servers[provider]
    connector.body(raw, media, assets=["figure"])
    connector.body(figure, "image/png", kind="asset", ref="figure")
    capture = source_article_capture.capture_source_article
    draft = FixtureDraft(paraphrases=_NEW_PROSE)

    def legacy_capture(*args, **kwargs):
        return capture(*args, **{**kwargs, "keep_ordered_step_instructions": image_only,
                                 "keep_image_only_step_instructions": False})

    def source(revision):
        with runtime.repo.connect() as conn:
            return conn.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                                (revision,)).fetchone()

    def refresh():
        job = refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="restore authored subinstructions",
                                  rewrite_profile_version=PROFILE)
        assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=draft, job_id=job.job_id)
        view = runtime.read_current()
        assert view["content_origin"] == "canonical", runtime.diagnostics()
        return view

    with monkeypatch.context() as legacy:
        legacy.setattr(source_article_capture, "capture_source_article", legacy_capture)
        before = refresh()
    old = source(before["source_revision_id"])
    assert before["document"]["blocks"][2]["text"] == "Check the seal."
    after = refresh()
    current = source(after["source_revision_id"])
    assert after["canonical_revision_id"] != before["canonical_revision_id"]
    if image_only:
        assert old["resource_manifest"][0]["ordered_step_instructions_layout"] == ORDERED_STEP_INSTRUCTIONS_LAYOUT
        assert current["resource_manifest"][0]["ordered_step_instructions_layout"] == ORDERED_STEP_IMAGE_ONLY_LAYOUT
    assert current["body_source_snapshot_id"] == old["body_source_snapshot_id"]
    assert current["resource_manifest"][1:] == old["resource_manifest"][1:]
    assert source(before["source_revision_id"]) == old
    step = after["document"]["blocks"][2]
    assert step["type"] == "ordered_list" and step["start"] == 2
    [item] = step["items"]
    assert [block["type"] for block in item["blocks"]] == ["paragraph", "image", "paragraph"]
    assert runtime.objects.get_object(item["blocks"][1]["storage_key"], max_bytes=1 << 20) == figure
    assert refresh()["canonical_revision_id"] == after["canonical_revision_id"] and len(draft.requests) == 2
