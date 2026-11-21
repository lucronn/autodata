"""Linked provider PDF capture, publication, and withdrawal through the real lifecycle."""

from hashlib import sha256
from io import BytesIO
import json
from random import Random
from uuid import uuid4

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import pytest

from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_types import (
    PDF_BLANK_PAGE_LAYOUT, PDF_COMPACT_FIGURE_LAYOUT, PDF_LEGACY_FIGURE_LAYOUT, PDF_REPEAT_MARGIN_LAYOUT,
)
from autodata_ingestion.procedure_rewrite_auto import PROFILE as AUTO_PROFILE
from autodata_ingestion.source_job_persistence import refresh_article_job

from lifecycle_support import fresh_database, runtime
from test_pdf_figure_order import _compact_figure, _pdf_with_logo


_PDF_REF = "fixture-linked-pdf"
_PDF_LOCATOR = "/provider-private/service-addendum.pdf"
_INTRODUCTION = "This procedure covers pump removal, seal inspection, and replacement."
_PARAPHRASES = {
    "Remove the pump.": "Take off the pump.",
    "Inspect the seal.": "Check the seal.",
    "Install the replacement.": "Fit the replacement unit.",
}


class FixtureDraft:
    _model = "fixture-linked-pdf-draft"

    def __init__(self, *, paraphrases=_PARAPHRASES, introduction=_INTRODUCTION):
        self.requests = []
        self.paraphrases = paraphrases
        self.introduction = introduction

    def complete_json(self, prompt):
        slots = json.loads(prompt)["slots"]
        self.requests.append([slot["text"] for slot in slots])
        return {
            "introduction": self.introduction,
            "replacements": [{
                "block_id": slot["block_id"],
                "path": slot["path"],
                "action": "rewrite",
                "text": self.paraphrases[slot["text"]],
                "reason": "",
            } for slot in slots],
        }


def _pdf_with_fixture_figure(*, trailing_text=None, second_figure=False, compact=False, title=None, blank_page=False):
    raster = _compact_figure() if compact else Image.frombytes("RGB", (96, 96), Random(7).randbytes(96 * 96 * 3))
    with raster as figure, BytesIO() as output:
        pixels = figure.tobytes()
        document = canvas.Canvas(output)
        if title:
            document.setTitle(title)
        document.drawString(72, 720, "Inspect the seal.")
        if second_figure:
            # Draw the lower figure first to exercise resource-to-layout identity.
            lower_pixels = Random(9).randbytes(128 * 96 * 3)
            lower = Image.frombytes("RGB", (128, 96), lower_pixels)
            document.drawImage(ImageReader(lower), 72, 520, width=128, height=70)
            document.drawString(72, 620, "Inspect the gasket.")
            document.drawImage(ImageReader(figure), 72, 648, width=96, height=48)
        else:
            document.drawImage(ImageReader(figure), 72, 500, width=96, height=96)
        if trailing_text:
            document.drawString(72, 450, trailing_text)
        document.showPage()
        if blank_page:
            document.showPage()
        document.save()
        return output.getvalue(), pixels


def _layout(document):
    return [(block["type"], block.get("text")) for block in document["blocks"]]


def test_compact_linked_pdf_preserves_legacy_pins_and_publishes_changed_bytes(runtime, monkeypatch):
    from autodata_ingestion import source_article_capture as capture_module

    runtime.article_id = runtime.articles["banktwo"]
    connector = runtime.servers["banktwo"]
    connector.body(
        f'<p>Remove the pump.</p><iframe src="{_PDF_LOCATOR}"></iframe>'.encode(),
        assets=[_PDF_REF], asset_bindings=[{"source_url": _PDF_LOCATOR, "resource_ref": _PDF_REF}],
    )
    options = {"trailing_text": "Install the replacement.", "compact": True}
    original_pdf, _ = _pdf_with_fixture_figure(**options, title="First fixture edition")
    connector.body(original_pdf, "application/pdf", ref=_PDF_REF, kind="binary")
    draft = FixtureDraft()

    def refresh():
        job = refresh_article_job(
            runtime.repo, runtime.article_id, actor="fixture", reason="inspect compact PDF diagram",
            rewrite_profile_version=AUTO_PROFILE,
        )
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), registry=runtime.registry, object_store=runtime.objects,
            model_client=draft, job_id=job.job_id,
        )
        current = runtime.read_current()
        assert current["content_origin"] == "canonical", runtime.diagnostics()
        with runtime.repo.connect() as conn:
            source = conn.execute(
                "SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                (current["source_revision_id"],),
            ).fetchone()
        return current, source

    capture = capture_module.capture_source_article

    def capture_before_compact_support(*args, **kwargs):
        return capture(*args, **{**kwargs, "keep_compact_pdf_figures": False})

    with monkeypatch.context() as patch:
        patch.setattr(capture_module, "capture_source_article", capture_before_compact_support)
        original, legacy_source = refresh()
    assert legacy_source["projection_version"] == "source-projection-v6"
    assert not original["images"]
    unchanged, same_source = refresh()
    assert unchanged["canonical_revision_id"] == original["canonical_revision_id"]
    assert same_source == legacy_source and len(draft.requests) == 1

    revised_pdf, pixels = _pdf_with_fixture_figure(**options, title="Second fixture edition")
    connector.body(revised_pdf, "application/pdf", ref=_PDF_REF, kind="binary")
    revised, source = refresh()
    assert revised["canonical_revision_id"] != original["canonical_revision_id"]
    assert source["projection_version"] == "source-projection-v7"
    assert _layout(source["source_document"]) == [
        ("paragraph", "Remove the pump."), ("paragraph", "Inspect the seal."), ("image", None),
        ("paragraph", "Install the replacement."),
    ]
    assert _layout(revised["document"]) == [
        ("paragraph", _INTRODUCTION), ("paragraph", "Take off the pump."), ("paragraph", "Check the seal."),
        ("image", None), ("paragraph", "Fit the replacement unit."),
    ]
    [parent] = [entry for entry in source["resource_manifest"] if entry["role"] == "document_asset"]
    assert (parent["sha256"], parent["pdf_compact_figure_layout"]) == (sha256(revised_pdf).hexdigest(), PDF_COMPACT_FIGURE_LAYOUT)
    [embedded] = revised["images"]
    stored = runtime.objects.get_object(embedded["storage_key"], max_bytes=1024 * 1024)
    with Image.open(BytesIO(stored)) as figure:
        assert figure.format == "PNG" and figure.tobytes() == pixels
    repeated, repeated_source = refresh()
    assert repeated["canonical_revision_id"] == revised["canonical_revision_id"]
    assert repeated_source == source and len(draft.requests) == 2


def test_linked_pdf_repeated_layout_survives_same_byte_refresh_and_changed_pdf(runtime):
    provider = "banktwo"
    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    connector.body(
        f'<p>Remove the pump.</p><iframe src="{_PDF_LOCATOR}"></iframe>'.encode(),
        assets=[_PDF_REF], asset_bindings=[{"source_url": _PDF_LOCATOR, "resource_ref": _PDF_REF}],
    )
    paraphrases = {"Remove the pump.": "Take off the pump."}
    for page in (1, 2):
        paraphrases[f"Inspect the seal on page {page}."] = f"Check the seal on page {page}."
        paraphrases[f"Check the seal on page {page}."] = f"Inspect the seal on page {page}."
        paraphrases[f"Clean the flange on page {page}."] = f"Wipe the flange clean on page {page}."
    introduction = "This procedure covers pump removal, seal inspection, and flange cleaning."
    draft = FixtureDraft(paraphrases=paraphrases, introduction=introduction)

    def refresh():
        job = refresh_article_job(
            runtime.repo, runtime.article_id, actor="fixture", reason="inspect retained PDF layout",
            rewrite_profile_version=AUTO_PROFILE,
        )
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), registry=runtime.registry, object_store=runtime.objects,
            model_client=draft, job_id=job.job_id,
        )
        current = runtime.read_current()
        assert current["content_origin"] == "canonical", runtime.diagnostics()
        with runtime.repo.connect() as conn:
            source = conn.execute(
                "SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                (current["source_revision_id"],),
            ).fetchone()
        assert source["projection_version"] == "source-projection-v10"
        return current, source

    for changed in (False, True):
        raw_pdf = _pdf_with_logo(changed=changed)
        connector.body(raw_pdf, "application/pdf", ref=_PDF_REF, kind="binary")
        current, source = refresh()
        if changed:
            assert current["canonical_revision_id"] != original_revision
            assert current["source_revision_id"] != original_source
        else:
            original_revision = current["canonical_revision_id"]
            original_source = current["source_revision_id"]

        parent, = [entry for entry in source["resource_manifest"] if entry["role"] == "document_asset"]
        assert (parent["sha256"], parent["pdf_figure_layout"]) == (sha256(raw_pdf).hexdigest(), PDF_REPEAT_MARGIN_LAYOUT)
        embedded, = [entry for entry in source["resource_manifest"] if entry["role"] == "embedded_asset"]
        assert len(current["images"]) == 2
        assert {image["storage_key"].rsplit("/", 1)[-1] for image in current["images"]} == {embedded["sha256"]}
        expected = [("paragraph", introduction), ("paragraph", "Take off the pump.")]
        for page in (1, 2):
            inspect = f"{'Inspect' if changed else 'Check'} the seal on page {page}."
            expected += [("paragraph", inspect), ("image", None), ("paragraph", f"Wipe the flange clean on page {page}.")]
        assert _layout(current["document"]) == expected

        assert len(draft.requests) == 1 + int(changed)
        repeated, same_source = refresh()
        assert len(draft.requests) == 1 + int(changed)
        assert repeated["canonical_revision_id"] == current["canonical_revision_id"]
        assert same_source == source


@pytest.mark.parametrize("layout", ["bare", "header"])
def test_v10_promotion_preserves_an_unchanged_sibling_pdf_across_refreshes(runtime, monkeypatch, layout):
    from autodata_ingestion import source_article_capture as capture_module

    runtime.article_id = runtime.articles["banktwo"]
    connector = runtime.servers["banktwo"]
    sibling_ref = "fixture-sibling-pdf"
    sibling_locator = "/provider-private/related.pdf"
    connector.body(
        (f'<p>Remove the pump.</p><iframe src="{_PDF_LOCATOR}"></iframe>'
         f'<iframe src="{sibling_locator}"></iframe>').encode(),
        assets=[_PDF_REF, sibling_ref], asset_bindings=[
            {"source_url": _PDF_LOCATOR, "resource_ref": _PDF_REF},
            {"source_url": sibling_locator, "resource_ref": sibling_ref},
        ],
    )
    sibling_pdf = _pdf_with_logo("bare", diagram_seed=9, unique_tail=True)
    original_pdf, _ = _pdf_with_fixture_figure(trailing_text="Install the replacement.")
    connector.body(sibling_pdf, "application/pdf", ref=sibling_ref, kind="binary")
    connector.body(original_pdf, "application/pdf", ref=_PDF_REF, kind="binary")
    paraphrases = dict(_PARAPHRASES)
    for page in (1, 2, 3):
        paraphrases[f"Inspect the seal on page {page}."] = f"Check the seal on page {page}."
        paraphrases[f"Check the seal on page {page}."] = f"Inspect the seal on page {page}."
        paraphrases[f"Clean the flange on page {page}."] = f"Wipe the flange clean on page {page}."
    draft = FixtureDraft(paraphrases=paraphrases, introduction="This guide covers pump removal and seal inspection.")

    def refresh():
        job = refresh_article_job(
            runtime.repo, runtime.article_id, actor="fixture", reason="inspect both PDF roots",
            rewrite_profile_version=AUTO_PROFILE,
        )
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), registry=runtime.registry, object_store=runtime.objects,
            model_client=draft, job_id=job.job_id,
        )
        current = runtime.read_current()
        assert current["content_origin"] == "canonical", runtime.diagnostics()
        with runtime.repo.connect() as conn:
            source = conn.execute(
                "SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                (current["source_revision_id"],),
            ).fetchone()
        return current, source

    capture = capture_module.capture_source_article

    def capture_before_v10(*args, **options):
        options.update(keep_repeated_pdf_figures=False, keep_pdf_figures_with_margins=False)
        return capture(*args, **options)

    with monkeypatch.context() as patch:
        patch.setattr(capture_module, "capture_source_article", capture_before_v10)
        original, pinned_source = refresh()
    assert pinned_source["projection_version"] == "source-projection-v7"
    assert len(original["images"]) == 2

    new_pdf = _pdf_with_logo(layout, changed=True)
    connector.body(new_pdf, "application/pdf", ref=_PDF_REF, kind="binary")
    promoted, promoted_source = refresh()
    assert promoted_source["projection_version"] == "source-projection-v10"
    assert len(promoted["images"]) == 3
    assert len(draft.requests) == 2

    repeated, same_source = refresh()
    assert len(draft.requests) == 2, "same-byte refresh drafted the previously pinned sibling PDF again"
    assert repeated["canonical_revision_id"] == promoted["canonical_revision_id"]
    assert same_source == promoted_source
    assert len(repeated["images"]) == 3
    linked = {entry["opaque_ref"]: entry for entry in same_source["resource_manifest"] if entry["role"] == "document_asset"}
    assert linked[sibling_ref]["sha256"] == sha256(sibling_pdf).hexdigest()
    assert linked[sibling_ref]["pdf_figure_layout"] == PDF_LEGACY_FIGURE_LAYOUT
    assert linked[_PDF_REF].get("pdf_figure_layout") == (PDF_REPEAT_MARGIN_LAYOUT if layout == "header" else None)
    with runtime.repo.connect() as conn:
        observation = conn.execute(
            """SELECT resource_provenance FROM canonical_article_source_observations WHERE source_revision_id=%s
               ORDER BY request_generation DESC LIMIT 1""",
            (repeated["source_revision_id"],),
        ).fetchone()
        assert conn.execute(
            "SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
            (original["source_revision_id"],),
        ).fetchone() == pinned_source
    [sibling_provenance] = [entry for entry in observation["resource_provenance"] if entry["opaque_ref"] == sibling_ref]
    assert sibling_provenance["pdf_figure_layout"] == PDF_LEGACY_FIGURE_LAYOUT

    connector.body(
        _pdf_with_logo("bare", changed=True, diagram_seed=9, unique_tail=True),
        "application/pdf", ref=sibling_ref, kind="binary",
    )
    updated, updated_source = refresh()
    assert updated_source["projection_version"] == "source-projection-v10"
    assert updated["canonical_revision_id"] != promoted["canonical_revision_id"]
    assert len(draft.requests) == 3
    assert len(updated["images"]) == 5
    assert all(entry.get("pdf_figure_layout") != PDF_LEGACY_FIGURE_LAYOUT for entry in updated_source["resource_manifest"])


def test_linked_pdf_publishes_in_order_and_private_original_controls_visibility(runtime, monkeypatch):
    from autodata_ingestion import source_adapters
    from autodata_ingestion.ocr import OCRUnavailable

    def unavailable_ocr(*_):
        raise OCRUnavailable("Fixture OCR unavailable")

    monkeypatch.setattr(source_adapters, "extract_scanned_pdf_text", unavailable_ocr)
    provider = "banktwo"
    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    raw_pdf, figure_pixels = _pdf_with_fixture_figure(trailing_text="Install the replacement.", blank_page=True)
    body = (
        '<p>Remove the pump.</p>'
        f'<iframe src="{_PDF_LOCATOR}" title="Private provider title">Hidden fallback.</iframe>'
    ).encode()
    connector.body(
        body, assets=[_PDF_REF],
        asset_bindings=[{"source_url": _PDF_LOCATOR, "resource_ref": _PDF_REF}],
    )
    connector.body(raw_pdf, "application/pdf", ref=_PDF_REF, kind="binary")
    runtime.reset_counters()
    job = refresh_article_job(
        runtime.repo, runtime.article_id, actor="fixture", reason="capture scoped PDF addendum",
        rewrite_profile_version=AUTO_PROFILE,
    )
    draft = FixtureDraft()
    assert run_article_worker_once(
        runtime.repo, worker_id=uuid4(), registry=runtime.registry,
        object_store=runtime.objects, model_client=draft, job_id=job.job_id,
    )
    published = runtime.read_current()
    assert published["content_origin"] == "canonical", runtime.diagnostics()
    assert published["availability"] == "available"
    assert published["takedown_status"] == "active"
    assert published["canonical_revision_id"]
    assert draft.requests == [list(_PARAPHRASES)]
    assert _layout(published["document"]) == [
        ("paragraph", _INTRODUCTION),
        ("paragraph", "Take off the pump."),
        ("paragraph", "Check the seal."),
        ("image", None),
        ("paragraph", "Fit the replacement unit."),
    ]

    with runtime.repo.connect() as conn:
        source = conn.execute(
            """SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s""",
            (published["source_revision_id"],),
        ).fetchone()
        observation = conn.execute(
            """SELECT resource_provenance FROM canonical_article_source_observations
               WHERE source_revision_id=%s AND source_fetch_job_id=%s""",
            (published["source_revision_id"], job.job_id),
        ).fetchone()
    assert source["projection_version"] == "source-projection-v7"
    assert source["projection_status"] == "readable"
    assert _layout(source["source_document"]) == [
        ("paragraph", "Remove the pump."),
        ("paragraph", "Inspect the seal."),
        ("image", None),
        ("paragraph", "Install the replacement."),
    ]
    for document in (source["source_document"], published["document"]):
        rendered = json.dumps(document)
        assert _PDF_LOCATOR not in rendered
        assert _PDF_REF not in rendered
        assert "Private provider title" not in rendered
        assert "Hidden fallback." not in rendered

    body_resource, pdf_resource, figure_resource = observation["resource_provenance"]
    assert [(entry["role"], entry["media_type"]) for entry in source["resource_manifest"]] == [
        ("body", "text/html"), ("document_asset", "application/pdf"), ("embedded_asset", "image/png"),
    ]
    assert source["resource_manifest"][1]["pdf_blank_page_layout"] == PDF_BLANK_PAGE_LAYOUT
    assert body_resource["sha256"] == sha256(body).hexdigest()
    assert pdf_resource["sha256"] == sha256(raw_pdf).hexdigest()
    assert pdf_resource["opaque_ref"] == _PDF_REF
    assert figure_resource["opaque_ref"] == f"embedded:{pdf_resource['sha256']}:{figure_resource['sha256']}"
    [pdf_evidence] = [
        entry["evidence_id"] for entry in source["evidence_manifest"]
        if entry["body_source_snapshot_id"] == pdf_resource["source_snapshot_id"]
    ]
    assert pdf_evidence in source["source_document"]["blocks"][1]["evidence_ids"]
    assert pdf_evidence in source["source_document"]["blocks"][2]["evidence_ids"]
    assert pdf_evidence in source["source_document"]["blocks"][3]["evidence_ids"]
    assert pdf_evidence in published["document"]["blocks"][2]["evidence_ids"]
    assert pdf_evidence in published["document"]["blocks"][3]["evidence_ids"]
    assert pdf_evidence in published["document"]["blocks"][4]["evidence_ids"]
    assert runtime.counters()["source"] == runtime.counters()["asset"] == 1

    assert runtime.objects.get_object(body_resource["object_key"], max_bytes=1024 * 1024) == body
    assert runtime.objects.get_object(pdf_resource["object_key"], max_bytes=1024 * 1024) == raw_pdf
    figure_bytes = runtime.objects.get_object(figure_resource["object_key"], max_bytes=1024 * 1024)
    assert sha256(figure_bytes).hexdigest() == figure_resource["sha256"]
    with Image.open(BytesIO(figure_bytes)) as figure:
        assert figure.format == "PNG"
        assert figure.tobytes() == figure_pixels
    [source_image] = source["source_images"]
    [published_image] = published["images"]
    for image in (source_image, published_image):
        assert image["storage_key"] == figure_resource["object_key"]
        assert image["media_type"] == "image/png"

    unchanged = refresh_article_job(
        runtime.repo, runtime.article_id, actor="fixture", reason="recheck retained PDF with the same blank page",
        rewrite_profile_version=AUTO_PROFILE,
    )
    assert run_article_worker_once(
        runtime.repo, worker_id=uuid4(), registry=runtime.registry,
        object_store=runtime.objects, model_client=draft, job_id=unchanged.job_id,
    )
    reread = runtime.read_current()
    assert reread["source_revision_id"] == published["source_revision_id"]
    assert reread["canonical_revision_id"] == published["canonical_revision_id"]

    with runtime.repo.connect() as conn:
        changed = conn.execute(
            """UPDATE source_snapshots SET takedown_status='takedown'
               WHERE source_snapshot_id=%s AND content_sha256=%s""",
            (pdf_resource["source_snapshot_id"], pdf_resource["sha256"]),
        )
        assert changed.rowcount == 1
        other_snapshots = conn.execute(
            """SELECT takedown_status FROM source_snapshots WHERE content_sha256 IN (%s, %s)""",
            (body_resource["sha256"], figure_resource["sha256"]),
        ).fetchall()
    assert [row["takedown_status"] for row in other_snapshots] == ["active", "active"]

    hidden = runtime.read_current()
    assert hidden["availability"] == "unavailable"
    assert hidden["takedown_status"] == "takedown"
    for field in ("source_revision_id", "canonical_revision_id", "content_origin", "body", "document", "images"):
        assert hidden[field] is None
    assert runtime.counters()["source"] == runtime.counters()["asset"] == 2
    assert len(draft.requests) == 1
