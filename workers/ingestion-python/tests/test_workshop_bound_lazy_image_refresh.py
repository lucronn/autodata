"""Exercise publication and refresh of a connector-bound lazy image."""

from hashlib import sha256
from io import BytesIO
import json
from uuid import uuid4

from PIL import Image
import pytest

from autodata_ingestion import source_article_capture
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_types import HTML_BOUND_IMAGE_LAYOUT
from autodata_ingestion.procedure_rewrite_auto import PROFILE as AUTO_PROFILE
from autodata_ingestion.source_job_persistence import refresh_article_job
from lifecycle_support import fresh_database, runtime
from test_workshop_linked_pdf import FixtureDraft


_LOCATOR = "/fixture/pump-alignment.png"
_OPENING = "Remove the pump."
_CAPTION = "Inspect the seal."
_CLOSING = "Install the replacement."
_ALT = "Pump alignment marks"
_LAYOUT_KEY = "html_bound_image_layout"


def _revisions(repo, view):
    # Select by the recorded revision IDs and compare stable, serialized rows.
    with repo.connect() as conn:
        source = conn.execute(
            """SELECT r.*, to_jsonb(r)::text AS record, body.object_key AS body_object_key
            FROM canonical_article_source_revisions r JOIN source_snapshots body
            ON body.source_snapshot_id=r.body_source_snapshot_id WHERE r.source_revision_id=%s""",
            (view["source_revision_id"],),
        ).fetchone()
        canonical = conn.execute(
            """SELECT r.*, to_jsonb(r)::text AS record FROM canonical_article_revisions r
            WHERE canonical_article_revision_id=%s""",
            (view["canonical_revision_id"],),
        ).fetchone()
    assert canonical["source_revision_id"] == source["source_revision_id"]
    return source, canonical


def _outline(blocks):
    return [(block["type"], block.get("text"), block.get("caption")) for block in blocks]


@pytest.mark.parametrize("provider,media_type", [("bankone", "text/html"), ("banktwo", "application/hal+json")])
def test_bound_lazy_image_refresh_preserves_published_history(runtime, monkeypatch, provider, media_type):
    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    html = (
        f"<p>{_OPENING}</p><figure><img data-src=\"{_LOCATOR}\" alt=\"{_ALT}\">"
        f"<figcaption>{_CAPTION}</figcaption></figure><p>{_CLOSING}</p>"
    )
    raw = html.encode() if media_type == "text/html" else json.dumps({
        "_embedded": {"data": {"article": {"content": html}}},
    }).encode()
    with Image.new("RGB", (24, 16), "green") as figure, BytesIO() as output:
        figure.save(output, format="PNG")
        image_bytes = output.getvalue()
    connector.body(raw, media_type, assets=["figure"], asset_bindings=[
        {"source_url": _LOCATOR, "resource_ref": "figure"},
    ])
    connector.body(image_bytes, "image/png", ref="figure", kind="asset")
    model = FixtureDraft(introduction="This procedure covers pump removal and replacement.")
    capture = source_article_capture.capture_source_article

    def legacy_capture(*args, **kwargs):
        return capture(*args, **{**kwargs, "keep_bound_html_images": False})

    def refresh():
        job = refresh_article_job(
            runtime.repo, runtime.article_id, actor="fixture", reason="verify lazy image placement",
            rewrite_profile_version=AUTO_PROFILE,
        )
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), registry=runtime.registry,
            object_store=runtime.objects, model_client=model, job_id=job.job_id,
        )
        view = runtime.read_current()
        assert view["content_origin"] == "canonical", runtime.diagnostics()
        return view

    with monkeypatch.context() as legacy:
        legacy.setattr(source_article_capture, "capture_source_article", legacy_capture)
        previous = refresh()
    old_source, old_canonical = _revisions(runtime.repo, previous)
    assert _LAYOUT_KEY not in old_source["resource_manifest"][0]
    assert ("image", None, _CAPTION) not in _outline(old_canonical["canonical_document"]["blocks"])
    assert len(model.requests) == 1

    corrected = refresh()
    source, canonical = _revisions(runtime.repo, corrected)
    assert corrected["source_revision_id"] != previous["source_revision_id"]
    assert corrected["canonical_revision_id"] != previous["canonical_revision_id"]
    assert source["body_source_snapshot_id"] == old_source["body_source_snapshot_id"]
    assert source["source_fingerprint"] != old_source["source_fingerprint"]
    body = source["resource_manifest"][0]
    assert body[_LAYOUT_KEY] == HTML_BOUND_IMAGE_LAYOUT
    assert body["sha256"] == old_source["resource_manifest"][0]["sha256"] == sha256(raw).hexdigest()
    assert runtime.objects.get_object(source["body_object_key"], max_bytes=1 << 20) == raw

    source_blocks = source["source_document"]["blocks"]
    assert _outline(source_blocks) == [
        ("paragraph", _OPENING, None), ("image", None, _CAPTION), ("paragraph", _CLOSING, None),
    ]
    canonical_blocks = canonical["canonical_document"]["blocks"][1:]
    assert _outline(canonical_blocks) == [
        ("paragraph", "Take off the pump.", None), ("image", None, _CAPTION),
        ("paragraph", "Fit the replacement unit.", None),
    ]
    source_image = source_blocks[1]
    assert canonical_blocks[1] == {**source_image, "source_order": source_image["source_order"] + 1}
    assert canonical_blocks[1]["alt"] == _ALT
    [image] = corrected["images"]
    assert image["status"] == "available"
    assert runtime.objects.get_object(image["storage_key"], max_bytes=1 << 20) == image_bytes
    assert len(model.requests) == 2

    repeated = refresh()
    assert repeated["source_revision_id"] == corrected["source_revision_id"]
    assert repeated["canonical_revision_id"] == corrected["canonical_revision_id"]
    assert _revisions(runtime.repo, previous) == (old_source, old_canonical)
    assert _revisions(runtime.repo, repeated) == (source, canonical)
    assert len(model.requests) == 2
