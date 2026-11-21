"""Retained diagrams in provider table headers and their immutable refresh."""

from hashlib import sha256
from io import BytesIO
import json
from uuid import uuid4

from PIL import Image
import pytest

from autodata_ingestion import source_article_capture
from autodata_ingestion.article_document import project_ordered_document, validate_ordered_document
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_types import STRUCTURED_TABLE_COLUMNS_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite_auto import PROFILE, render_auto, validate_auto
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.source_job_persistence import refresh_article_job

from lifecycle_support import fresh_database, runtime
from test_source_article_capture import capture_fixture
from test_workshop_linked_pdf import _INTRODUCTION, _PARAPHRASES, FixtureDraft


def _supplier_body(provider):
    article = {"blocks": [
        {"type": "paragraph", "text": "Remove the pump."},
        {"type": "table", "label": "Pressure data", "columns": [
            {"text": "Pressure profile", "images": [
                {"asset_resource_ref": "chart", "alt": "Pressure chart", "caption": "Pressure at 2,000 rpm"},
            ]}, {"text": "Limit"},
        ], "rows": [["Supply", "500 kPa"]]},
        {"type": "paragraph", "text": "Inspect the seal."},
        {"type": "paragraph", "text": "Install the replacement."},
    ]}
    if provider == "banktwo":
        return json.dumps({"_embedded": {"data": {"article": article}}}).encode(), "application/hal+json"
    return json.dumps(article).encode(), "application/json"


def _fixture_png():
    buffer = BytesIO()
    Image.new("RGB", (96, 48), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize("provider,available", [("bankone", True), ("banktwo", True), ("banktwo", False)])
def test_structured_table_column_keeps_retained_chart_through_rewrite(capture_fixture, provider, available):
    raw, media = _supplier_body(provider)
    figure = _fixture_png()
    capture_fixture.body(provider, raw, media, assets=["chart"])
    if available:
        capture_fixture.body(provider, figure, "image/png", kind="asset", ref="chart")
    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects)
    legacy = source_article_capture.capture_source_article(context, **options)
    captured = source_article_capture.capture_source_article(context, keep_structured_table_columns=True, **options)
    assert isinstance(legacy.source_document["blocks"][1]["columns"][0], str)
    assert ("storage_key" in legacy.source_document["blocks"][1]["columns"][0]) is available
    assert legacy.source_images == []
    assert captured.source_fingerprint != legacy.source_fingerprint
    assert captured.body_source_snapshot_id == legacy.body_source_snapshot_id
    assert captured.resource_manifest[0]["structured_table_columns_layout"] == STRUCTURED_TABLE_COLUMNS_LAYOUT
    assert captured.resource_manifest[1:] == legacy.resource_manifest[1:]
    assert captured.evidence_manifest == legacy.evidence_manifest
    assert captured.projection_status == ("readable" if available else "partial")
    assert not validate_ordered_document(captured.source_document, strict=True)
    table = captured.source_document["blocks"][1]
    header, limit = table["columns"]
    assert header["text"] == "Pressure profile" and limit == "Limit"
    [image] = header["images"]
    assert captured.source_images == [image]
    assert image["caption"] == "Pressure at 2,000 rpm" and image["alt"] == "Pressure chart"
    assert table["rows"] == [["Supply", "500 kPa"]]
    assert "storage_key" not in captured.source_body
    if available:
        assert capture_fixture.objects.data[image["storage_key"]] == (figure, "image/png")
    else:
        assert image["status"] == "unavailable" and image["unavailable_reason"] == "SOURCE_NOT_FOUND"

    normalized = normalize_procedure_article({
        "normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps,
    }, resource_manifest=captured.resource_manifest)
    assert normalized["images"] == [image]
    document = normalized["normalized_document"]
    slots = prose_slots(document, include_cell_blocks=True)
    assert [slot["text"] for slot in slots] == list(_PARAPHRASES)
    model = {"introduction": _INTRODUCTION, "replacements": [
        {**slot, "action": "rewrite", "text": _PARAPHRASES[slot["text"]], "reason": ""} for slot in slots
    ]}
    canonical = render_auto(document, model)
    assert validate_auto(document, canonical, response=model).passed
    assert canonical["blocks"][2]["columns"] == table["columns"]
    assert project_ordered_document(canonical)["images"] == [image]


def test_structured_table_column_explicit_refresh_preserves_old_revisions(runtime, monkeypatch):
    provider = "banktwo"
    runtime.article_id = runtime.articles[provider]
    raw, media = _supplier_body(provider)
    figure = _fixture_png()
    connector = runtime.servers[provider]
    connector.body(raw, media, assets=["chart"])
    connector.body(figure, "image/png", kind="asset", ref="chart")
    model = FixtureDraft()
    capture = source_article_capture.capture_source_article

    def legacy_capture(*args, **kwargs):
        return capture(*args, **{**kwargs, "keep_structured_table_columns": False})

    def refresh():
        job = refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="refresh table figure",
                                  rewrite_profile_version=PROFILE)
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), registry=runtime.registry,
            object_store=runtime.objects, model_client=model, job_id=job.job_id,
        )
        current = runtime.read_current()
        assert current["content_origin"] == "canonical", runtime.diagnostics()
        with runtime.repo.connect() as conn:
            source = conn.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                                  (current["source_revision_id"],)).fetchone()
        return current, source

    with monkeypatch.context() as legacy:
        legacy.setattr(source_article_capture, "capture_source_article", legacy_capture)
        old, old_source = refresh()
    assert old["images"] == []
    current, source = refresh()
    assert current["source_revision_id"] != old["source_revision_id"]
    assert current["canonical_revision_id"] != old["canonical_revision_id"]
    assert source["body_source_snapshot_id"] == old_source["body_source_snapshot_id"]
    assert source["resource_manifest"][0]["sha256"] == sha256(raw).hexdigest()
    assert source["resource_manifest"][1:] == old_source["resource_manifest"][1:]
    assert source["source_document"]["blocks"][1]["columns"] == current["document"]["blocks"][2]["columns"]
    [image] = current["images"]
    assert runtime.objects.get_object(image["storage_key"], max_bytes=1 << 20) == figure
    repeated, repeated_source = refresh()
    assert repeated["canonical_revision_id"] == current["canonical_revision_id"]
    assert repeated_source == source and len(model.requests) == 2
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                            (old["source_revision_id"],)).fetchone() == old_source
        original = conn.execute("SELECT canonical_document,canonical_images FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                                (old["canonical_revision_id"],)).fetchone()
    assert original == {"canonical_document": old["document"], "canonical_images": []}
