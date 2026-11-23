"""Supplier document labels stay in the ordered article without becoming prose."""

from hashlib import sha256
import json
from uuid import uuid4

import pytest

from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_store import load_source_revision
from autodata_ingestion.article_lifecycle_types import HTML_DOCUMENT_LINK_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite_auto import PROFILE as AUTO_PROFILE
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.source_article_capture import capture_source_article
from autodata_ingestion.source_job_persistence import refresh_article_job
from lifecycle_support import fresh_database, runtime
from test_source_article_capture import capture_fixture
from test_workshop_linked_pdf import FixtureDraft


LABEL = "Auxiliary Steering Reference"
PRIVATE_REF = "private-reference-123"
HTML = (
    "<p>Check the shield for damage.</p>"
    "<ol><li>Remove the cover.<ul>"
    f"<li><mtr-doc-link document-id='{PRIVATE_REF}'>{LABEL}</mtr-doc-link></li>"
    "<li>Keep the bracket in place.</li>"
    "</ul></li><li>Install the cover.</li></ol>"
)


def blocks(value):
    if isinstance(value, dict):
        if "block_id" in value:
            yield value
        for item in value.values():
            yield from blocks(item)
    elif isinstance(value, list):
        for item in value:
            yield from blocks(item)


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("media_type", ["text/html", "application/hal+json"])
def test_standalone_document_link_survives_capture(capture_fixture, provider, media_type):
    payload = (
        HTML.encode() if media_type == "text/html"
        else json.dumps({"_embedded": {"data": {"article": {"body": HTML}}}}).encode()
    )
    capture_fixture.body(provider, payload, media_type)
    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects)
    previous = capture_source_article(context, **options)
    current = capture_source_article(context, keep_html_document_links=True, **options)

    old_document = previous.source_document
    document = current.source_document
    assert LABEL in [slot["text"] for slot in prose_slots(old_document)]
    assert [slot["text"] for slot in prose_slots(document)] == [
        "Check the shield for damage.", "Remove the cover.",
        "Keep the bracket in place.", "Install the cover.",
    ]
    links = [block for block in blocks(document) if block["type"] == "link"]
    assert len(links) == 1 and links[0]["text"] == LABEL
    assert PRIVATE_REF not in json.dumps(document)
    assert not validate_ordered_document(document, strict=True)

    assert "html_document_link_layout" not in previous.resource_manifest[0]
    assert current.resource_manifest[0]["html_document_link_layout"] == HTML_DOCUMENT_LINK_LAYOUT
    assert current.projection_version == "source-projection-v5"
    assert current.body_source_snapshot_id == previous.body_source_snapshot_id
    assert current.source_fingerprint != previous.source_fingerprint
    assert current.resource_manifest[0]["sha256"] == sha256(payload).hexdigest()
    assert normalize_procedure_article(
        {"normalized_document": document, "body": current.source_body, "steps": current.source_steps},
        resource_manifest=current.resource_manifest,
    )["normalized_document"] == document


@pytest.mark.parametrize("provider,media_type", [("bankone", "text/html"), ("banktwo", "application/hal+json")])
def test_published_document_link_refresh_keeps_same_body_revision(runtime, monkeypatch, provider, media_type):
    from autodata_ingestion import source_article_capture

    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    label = "Pump Removal Reference"

    def set_body(instruction):
        html = (f"<p>{instruction}</p><ul><li>"
                f"<mtr-doc-link document-id='{PRIVATE_REF}'>{label}</mtr-doc-link></li></ul>")
        payload = html.encode() if media_type == "text/html" else json.dumps({
            "_embedded": {"data": {"article": {"body": html}}},
        }).encode()
        connector.body(payload, media_type)

    model = FixtureDraft(
        introduction="This procedure covers pump service.",
        paraphrases={"Remove the pump.": "Take off the pump.",
                     "Install the replacement.": "Fit the replacement unit.",
                     label: "Reference for removing the pump."},
    )

    def refresh():
        job = refresh_article_job(
            runtime.repo, runtime.article_id, actor="fixture", reason="inspect supplier reference update",
            rewrite_profile_version=AUTO_PROFILE,
        )
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), registry=runtime.registry,
            object_store=runtime.objects, model_client=model, job_id=job.job_id,
        )
        view = runtime.read_current()
        assert view["content_origin"] == "canonical", runtime.diagnostics()
        return view

    set_body("Remove the pump.")
    with monkeypatch.context() as legacy:
        legacy.setattr(source_article_capture, "capture_source_article", lambda *args, **kwargs: (
            capture_source_article(*args, **{**kwargs, "keep_html_document_links": False})
        ))
        previous = refresh()
    previous_source = load_source_revision(runtime.repo, previous["source_revision_id"])
    assert "html_document_link_layout" not in previous_source.resource_manifest[0]
    assert model.requests == [["Remove the pump.", label]]

    unchanged = refresh()
    for field in ("source_revision_id", "canonical_revision_id", "document"):
        assert unchanged[field] == previous[field]
    assert len(model.requests) == 1

    set_body("Install the replacement.")
    updated = refresh()
    assert updated["canonical_revision_id"] != previous["canonical_revision_id"]
    assert updated["source_revision_id"] != previous["source_revision_id"]
    updated_source = load_source_revision(runtime.repo, updated["source_revision_id"])
    assert updated_source.resource_manifest[0]["html_document_link_layout"] == HTML_DOCUMENT_LINK_LAYOUT
    assert [block["text"] for block in blocks(updated["document"]) if block["type"] == "link"] == [label]
    assert model.requests[-1] == ["Install the replacement."]

    repeated = refresh()
    for field in ("source_revision_id", "canonical_revision_id", "document"):
        assert repeated[field] == updated[field]
    assert len(model.requests) == 2
