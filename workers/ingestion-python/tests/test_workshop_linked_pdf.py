"""Linked provider PDF capture, publication, and withdrawal through the real lifecycle."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from random import Random
from threading import Event, Lock
from uuid import uuid4

from PIL import Image
from pypdf import PageObject
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import pytest

from autodata_ingestion import source_adapters
from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_store import load_source_revision
from autodata_ingestion.article_lifecycle_types import (
    HTML_DOCUMENT_LINK_LAYOUT, PDF_BLANK_PAGE_LAYOUT, PDF_COMPACT_FIGURE_LAYOUT, PDF_LEGACY_FIGURE_LAYOUT, PDF_REPEAT_MARGIN_LAYOUT,
    PDF_SINGLE_LINE_FIGURE_LAYOUT, PDF_WORDLESS_FIGURE_LAYOUT,
)
from autodata_ingestion.procedure_rewrite_auto import PROFILE as AUTO_PROFILE
from autodata_ingestion.ocr import OCRUnavailable
from autodata_ingestion.source_job_persistence import refresh_article_job

from lifecycle_support import fresh_database, runtime
from test_linked_wordless_pdf_figures import _linked_pdf
from test_pdf_figure_order import _compact_figure, _pdf_with_logo, _single_line_compact_pdf


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


@pytest.mark.parametrize("bare_link", [True, False])
def test_linked_pdf_preview_precedes_figures_and_unrelated_assets(runtime, monkeypatch, bare_link):
    from test_article_lifecycle_integration import scoped_runtime_article

    scoped_runtime_article(runtime)
    connector = runtime.servers["bankone"]
    pdf, _ = _pdf_with_fixture_figure(trailing_text="Install the replacement.")
    title = escape(runtime.read_current()["title"])
    body = (
        f'<a href="{_PDF_LOCATOR}">{title}</a>' if bare_link else
        f'<p>Remove the pump.</p><iframe src="{_PDF_LOCATOR}"></iframe><p>Verify the fitting.</p>'
    ).encode()
    # Bare anchors must probe MIME first. The iframe already declares a
    # positioned document and can take a slot before unrelated images.
    asset_refs = [f"fixture-unrelated-figure-{index}" for index in range(1 if bare_link else 4)]
    png = BytesIO()
    Image.new("RGB", (2, 2), "blue").save(png, format="PNG")
    connector.body(body, assets=[*asset_refs, _PDF_REF],
                   asset_bindings=[{"source_url": _PDF_LOCATOR, "resource_ref": _PDF_REF}])
    connector.body(pdf, "application/pdf", ref=_PDF_REF, kind="binary")
    for asset_ref in asset_refs:
        connector.body(png.getvalue(), "image/png", ref=asset_ref, kind="asset")
    job = refresh_article_job(
        runtime.repo, runtime.article_id, actor="fixture", reason="capture linked PDF preview",
        rewrite_profile_version=AUTO_PROFILE,
    )
    asset_started = {asset_ref: Event() for asset_ref in asset_refs}
    pdf_started, asset_release = Event(), Event()
    read_lock = Lock()
    active_reads = peak_reads = 0
    figure_started, figure_release = Event(), Event()
    client = runtime.registry["bankone"]
    put_object = runtime.objects.put_object

    class HeldAssetConnector:
        provider = "bankone"

        def read_resource(self, ref, **kwargs):
            nonlocal active_reads, peak_reads
            with read_lock:
                active_reads += 1
                peak_reads = max(peak_reads, active_reads)
            try:
                if ref == _PDF_REF:
                    pdf_started.set()
                if ref in asset_started:
                    asset_started[ref].set()
                    assert asset_release.wait(12)
                return client.read_resource(ref, **kwargs)
            finally:
                with read_lock:
                    active_reads -= 1

    def hold_pdf_figure(key, payload, media_type):
        if media_type == "image/png" and payload != png.getvalue():
            figure_started.set()
            assert figure_release.wait(12)
        return put_object(key, payload, media_type)

    def current_preview():
        with runtime.repo.connect() as conn:
            row = conn.execute("""
                SELECT checkpoint->'source_body_preview' AS preview,source_revision_id
                FROM source_fetch_jobs WHERE source_fetch_job_id=%s
            """, (job.job_id,)).fetchone()
        preview = row["preview"]
        if preview and "linked_preview" in preview and any(
            block["type"] == "image" for block in preview["linked_preview"]["document"]["blocks"]
        ):
            assert row["source_revision_id"] is None
            return preview

    monkeypatch.setattr(runtime.objects, "put_object", hold_pdf_figure)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            run_article_worker_once, runtime.repo, worker_id=uuid4(), job_id=job.job_id,
            registry={"bankone": HeldAssetConnector()}, object_store=runtime.objects, model_client=None,
        )
        try:
            assert all(started.wait(5) for started in asset_started.values())
            if not bare_link:
                assert pdf_started.is_set(), "four unrelated image reads starved the predeclared PDF"
            preview = runtime.wait_for(current_preview)
            assert not asset_release.is_set()
            with read_lock:
                assert active_reads == len(asset_refs)
                assert peak_reads <= 4
            assert ("document" in preview) is not bare_link
            if not bare_link:
                assert "Inspect the seal." not in json.dumps(preview["document"])
                assert "Remove the pump." in json.dumps(preview["document"])
            expanded = preview["linked_preview"]
            [snapshot_id] = expanded["snapshot_ids"]
            with runtime.repo.connect() as conn:
                artifact = conn.execute("""
                    SELECT a.media_type,a.content_sha256 FROM source_artifacts a WHERE a.source_snapshot_id=%s
                """, (snapshot_id,)).fetchone()
            assert artifact == {"media_type": "application/pdf", "content_sha256": sha256(pdf).hexdigest()}
            blocks = expanded["document"]["blocks"]
            texts = [block.get("text") for block in blocks]
            assert texts.index("Inspect the seal.") < texts.index("Install the replacement.")
            if not bare_link:
                assert texts.index("Remove the pump.") < texts.index("Inspect the seal.")
                assert texts.index("Install the replacement.") < texts.index("Verify the fitting.")
            [figure] = [block for block in blocks if block["type"] == "image"]
            assert figure["unavailable_reason"] == "SOURCE_MEDIA_PENDING"
            assert not ({"storage_key", "href", "content_sha256", "asset_resource_ref"} & figure.keys())
            assert _PDF_LOCATOR not in json.dumps(expanded)
            asset_release.set()
            assert figure_started.wait(5)
            assert current_preview() == preview
        finally:
            asset_release.set()
            figure_release.set()
        assert future.result(timeout=10)
    final = runtime.read_current()
    assert final["source_revision_id"] and final["content_origin"] == "source"
    assert len([figure for figure in final["images"] if figure["status"] == "available"]) >= 1
    retained = load_source_revision(runtime.repo, final["source_revision_id"])
    assets = [ref for ref in retained.resource_manifest if ref["role"] in {"asset", "document_asset"}]
    assert [ref["opaque_ref"] for ref in assets] == [*asset_refs, _PDF_REF]
    assert assets[-1]["sha256"] == sha256(pdf).hexdigest()
    preview_layout = _layout(expanded["document"])
    assert _layout(final["document"])[:len(preview_layout)] == preview_layout
    assert current_preview() is None


@pytest.mark.parametrize("inferred", [False, True])
def test_linked_native_pdf_preview_precedes_figure_decode(runtime, monkeypatch, inferred):
    from test_article_lifecycle_integration import scoped_runtime_article

    scoped_runtime_article(runtime)
    connector = runtime.servers["bankone"]
    pdf, _ = _pdf_with_fixture_figure(trailing_text="0.5 mm maximum clearance.", blank_page=True)
    marked = (
        f'<a href="{_PDF_LOCATOR}">Service bulletin</a>' if inferred else f'<iframe src="{_PDF_LOCATOR}"></iframe>'
    )
    body = f"<p>Remove the pump.</p>{marked}<p>Install the replacement.</p>".encode()
    connector.body(body, assets=[_PDF_REF],
                   asset_bindings=[{"source_url": _PDF_LOCATOR, "resource_ref": _PDF_REF}])
    connector.body(pdf, "application/pdf", ref=_PDF_REF, kind="binary")
    job = refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="initial native PDF",
                              rewrite_profile_version=AUTO_PROFILE)
    decode_started, decode_release = Event(), Event()
    original_decode = source_adapters._extract_pdf_page_images
    original_extract = PageObject.extract_text
    client = runtime.registry["bankone"]
    downloaded = []
    native_pages = []

    class CountPDFReads:
        provider = "bankone"

        def read_resource(self, ref, **kwargs):
            downloaded.append(ref)
            return client.read_resource(ref, **kwargs)

    def read_native_text(page, *args, **kwargs):
        if not args and not kwargs:
            native_pages.append(True)
        return original_extract(page, *args, **kwargs)

    def hold_decode(*args, **kwargs):
        if not decode_started.is_set():
            decode_started.set()
            assert decode_release.wait(12)
        return original_decode(*args, **kwargs)

    def find_linked_preview():
        with runtime.repo.connect() as conn:
            row = conn.execute("""
                SELECT source_revision_id,checkpoint->'source_body_preview'->'linked_preview' AS preview
                FROM source_fetch_jobs WHERE source_fetch_job_id=%s
            """, (job.job_id,)).fetchone()
        assert row["source_revision_id"] is None
        return row["preview"]

    monkeypatch.setattr(source_adapters, "_extract_pdf_page_images", hold_decode)
    monkeypatch.setattr(PageObject, "extract_text", read_native_text)
    with ThreadPoolExecutor(max_workers=1) as executor:
        worker = executor.submit(run_article_worker_once, runtime.repo, worker_id=uuid4(), job_id=job.job_id,
                                 registry={"bankone": CountPDFReads()}, object_store=runtime.objects, model_client=None)
        try:
            assert decode_started.wait(5)
            preview = runtime.wait_for(find_linked_preview)
            assert not decode_release.is_set() and len(native_pages) == 2
            assert not validate_ordered_document(preview["document"])
            layout = _layout(preview["document"])
            assert all(kind != "image" for kind, _ in layout)
            assert ("paragraph", "0.5 mm maximum clearance.") in layout
            texts = [text for _, text in layout]
            assert texts.index("Remove the pump.") < texts.index("Inspect the seal.")
            assert texts.index("Inspect the seal.") < texts.index("0.5 mm maximum clearance.")
            assert texts.index("0.5 mm maximum clearance.") < texts.index("Install the replacement.")
            [snapshot] = preview["snapshot_ids"]
            with runtime.repo.connect() as conn:
                artifact = conn.execute("""
                    SELECT s.takedown_status,a.media_type,a.content_sha256 FROM source_snapshots s
                    JOIN source_artifacts a USING (source_snapshot_id)
                    WHERE s.source_snapshot_id=%s AND a.content_sha256=s.content_sha256
                """, (snapshot,)).fetchone()
            assert artifact == {"takedown_status": "active", "media_type": "application/pdf",
                                "content_sha256": sha256(pdf).hexdigest()}
        finally:
            decode_release.set()
        assert worker.result(timeout=10)
    final = runtime.read_current()
    assert final["source_revision_id"] and downloaded.count(_PDF_REF) == 1 and len(native_pages) == 2
    final_layout = _layout(final["document"])
    assert any(kind == "image" for kind, _ in final_layout)
    assert [(kind, text) for kind, text in final_layout if kind != "image"] == layout


def test_linked_pdf_does_not_signal_incomplete_native_text_when_ocr_is_needed(monkeypatch):
    pdf, _ = _linked_pdf("middle")
    resource = source_adapters.SourceResource.from_bytes("https://fixture.invalid/bulletin", "fixture",
                                                         pdf, "application/pdf")
    native_documents, ocr_pages = [], []

    def require_ocr(digest, payload, native_pages, *, page_range):
        assert digest == sha256(pdf).hexdigest() and payload == pdf and native_pages == {1, 3}
        ocr_pages.append(page_range)
        raise OCRUnavailable("synthetic OCR unavailable")

    monkeypatch.setattr(source_adapters, "extract_scanned_pdf_text", require_ocr)
    with pytest.raises(ValueError, match="pages requiring unavailable OCR"):
        source_adapters.adapt_bound_pdf_embed(resource, require_complete_ocr=True, skip_blank_pages=True,
                                             on_native_text=native_documents.append)
    assert native_documents == [] and ocr_pages == [(2, 2)]


def test_linked_single_line_figure_refresh_reuses_original_pdf_bytes(runtime, monkeypatch):
    from autodata_ingestion import source_article_capture as capture_module

    provider = "banktwo"
    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    original_pdf = _single_line_compact_pdf()
    body = (f'<p>Remove the pump.</p><iframe src="{_PDF_LOCATOR}"></iframe>'
            '<p>Install the replacement.</p>').encode()
    connector.body(body, assets=[_PDF_REF], asset_bindings=[{"source_url": _PDF_LOCATOR, "resource_ref": _PDF_REF}])
    connector.body(original_pdf, "application/pdf", ref=_PDF_REF, kind="binary")
    draft = FixtureDraft()
    capture = capture_module.capture_source_article

    def historic_capture(*args, **kwargs):
        return capture(*args, **{**kwargs, "keep_single_line_pdf_figures": False})

    def source(revision):
        with runtime.repo.connect() as conn:
            return conn.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                                (revision,)).fetchone()

    def refresh():
        job = refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="refresh compact service diagram",
                                  rewrite_profile_version=AUTO_PROFILE)
        assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=draft, job_id=job.job_id)
        current = runtime.read_current()
        assert current["content_origin"] == "canonical", runtime.diagnostics()
        return current

    with monkeypatch.context() as old:
        old.setattr(capture_module, "capture_source_article", historic_capture)
        published_old = refresh()
    assert not published_old["images"]
    prior = source(published_old["source_revision_id"])
    published = refresh()
    current = source(published["source_revision_id"])
    assert published["canonical_revision_id"] != published_old["canonical_revision_id"]
    assert current["body_source_snapshot_id"] == prior["body_source_snapshot_id"]
    assert source(published_old["source_revision_id"]) == prior
    assert current["resource_manifest"][1] == {
        **prior["resource_manifest"][1], "pdf_single_line_figure_layout": PDF_SINGLE_LINE_FIGURE_LAYOUT,
    }
    assert _layout(published["document"]) == [
        ("paragraph", _INTRODUCTION), ("paragraph", "Take off the pump."), ("paragraph", "Check the seal."),
        ("image", None), ("paragraph", "Fit the replacement unit."),
    ]
    [image] = published["images"]
    data = runtime.objects.get_object(image["storage_key"], max_bytes=1 << 20)
    with Image.open(BytesIO(data)) as decoded, _compact_figure() as expected:
        assert decoded.tobytes() == expected.tobytes()
    assert refresh()["canonical_revision_id"] == published["canonical_revision_id"] and len(draft.requests) == 2


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


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_wordless_linked_pdf_refresh_preserves_pinned_source(runtime, monkeypatch, provider):
    from autodata_ingestion import source_adapters, source_article_capture as capture_module

    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    pdf, figure = _linked_pdf("middle")
    connector.body(
        (f'<p>Remove the pump.</p><iframe src="{_PDF_LOCATOR}"></iframe>'
         '<p>Install the replacement.</p>').encode(),
        assets=[_PDF_REF], asset_bindings=[{"source_url": _PDF_LOCATOR, "resource_ref": _PDF_REF}],
    )
    connector.body(pdf, "application/pdf", ref=_PDF_REF, kind="binary")

    def no_text(digest, payload, covered, *, page_range):
        assert payload == pdf and digest == sha256(pdf).hexdigest()
        assert covered == {1, 3}
        assert page_range == (2, 2)
        return ()

    monkeypatch.setattr(source_adapters, "extract_scanned_pdf_text", no_text)
    draft = FixtureDraft(paraphrases={
        **_PARAPHRASES,
        "Inspect the harness connector.": "Check the harness connector.",
        "Seat the terminal in the connector.": "Fit the terminal into the connector.",
    })

    def refresh():
        job = refresh_article_job(
            runtime.repo, runtime.article_id, actor="fixture", reason="verify wordless PDF diagram",
            rewrite_profile_version=AUTO_PROFILE,
        )
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), registry=runtime.registry, object_store=runtime.objects,
            model_client=draft, job_id=job.job_id,
        )
        result = runtime.read_current()
        assert result["content_origin"] == "canonical", runtime.diagnostics()
        return result

    def source(row):
        with runtime.repo.connect() as conn:
            return conn.execute(
                "SELECT * FROM canonical_article_source_revisions WHERE source_revision_id = %s",
                (row["source_revision_id"],),
            ).fetchone()

    capture = capture_module.capture_source_article
    with monkeypatch.context() as patch:
        patch.setattr(capture_module, "capture_source_article", lambda *args, **kwargs: capture(
            *args, **{**kwargs, "keep_wordless_linked_pdf_figures": False},
        ))
        prior = refresh()
    prior_source = source(prior)
    assert not prior["images"]

    corrected = refresh()
    assert corrected["canonical_revision_id"] != prior["canonical_revision_id"]
    assert corrected["source_revision_id"] != prior["source_revision_id"]
    corrected_source = source(corrected)
    assert source(prior) == prior_source
    old_pdf, new_pdf = (
        next(r for r in row["resource_manifest"] if r["role"] == "document_asset")
        for row in (prior_source, corrected_source)
    )
    assert new_pdf["sha256"] == old_pdf["sha256"] == sha256(pdf).hexdigest()
    assert corrected_source["body_source_snapshot_id"] == prior_source["body_source_snapshot_id"]
    assert new_pdf["pdf_wordless_figure_layout"] == PDF_WORDLESS_FIGURE_LAYOUT
    assert _layout(corrected_source["source_document"])[1:4] == [
        ("paragraph", "Inspect the harness connector."), ("image", None),
        ("paragraph", "Seat the terminal in the connector."),
    ]
    assert _layout(corrected["document"])[2:5] == [
        ("paragraph", "Check the harness connector."), ("image", None),
        ("paragraph", "Fit the terminal into the connector."),
    ]
    [image] = corrected["images"]
    with Image.open(BytesIO(runtime.objects.get_object(image["storage_key"], max_bytes=1_048_576))) as stored:
        assert stored.size == figure.size and stored.convert("RGB").tobytes() == figure.tobytes()
    assert refresh()["canonical_revision_id"] == corrected["canonical_revision_id"]
    assert len(draft.requests) == 2


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


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_published_pdf_anchor_reuses_the_same_digest(runtime, provider):
    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    label = "Pump service addendum"
    html = (
        '<p>Remove the pump.</p>'
        f'<a href="{_PDF_LOCATOR}">{label}</a>'
        '<p>Install the replacement.</p>'
    )
    raw, media = html.encode(), "text/html"
    if provider == "banktwo":
        structured = [{"kind": "text", "text": text} for text in ("Remove the pump.", "Install the replacement.")]
        raw = json.dumps({"_embedded": {"data": {"article": {"content": html, "blocks": structured}}}}).encode()
        media = "application/hal+json"
    pdf, _ = _pdf_with_fixture_figure()
    connector.body(raw, media, assets=[_PDF_REF], asset_bindings=[
        {"source_url": _PDF_LOCATOR, "resource_ref": _PDF_REF},
    ])
    connector.body(pdf, "application/pdf", ref=_PDF_REF, kind="binary")
    draft = FixtureDraft()

    def refresh():
        job = refresh_article_job(
            runtime.repo, runtime.article_id, actor="fixture", reason="refresh PDF anchor without changing bytes",
            rewrite_profile_version=AUTO_PROFILE,
        )
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), registry=runtime.registry,
            object_store=runtime.objects, model_client=draft, job_id=job.job_id,
        )
        view = runtime.read_current()
        assert view["content_origin"] == "canonical", runtime.diagnostics()
        return view

    first = refresh()
    assert _layout(first["document"]) == [
        ("paragraph", _INTRODUCTION), ("paragraph", "Take off the pump."),
        ("link", label), ("paragraph", "Check the seal."), ("image", None),
        ("paragraph", "Fit the replacement unit."),
    ]
    repeated = refresh()
    for field in ("source_revision_id", "canonical_revision_id", "document", "images"):
        assert repeated[field] == first[field]
    source = load_source_revision(runtime.repo, first["source_revision_id"])
    assert source.resource_manifest[0]["sha256"] == sha256(raw).hexdigest()
    assert source.resource_manifest[0]["html_document_link_layout"] == HTML_DOCUMENT_LINK_LAYOUT
    [retained] = [item for item in source.resource_manifest if item["role"] == "document_asset"]
    assert retained["sha256"] == sha256(pdf).hexdigest()
    assert draft.requests == [list(("Remove the pump.", "Inspect the seal.", "Install the replacement."))]


def test_published_hal_anchor_label_stays_safe_when_the_png_changes(runtime):
    provider = "banktwo"
    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    label = "Protect the pump during service."
    html = f'<a href="{_PDF_LOCATOR}">{label}</a>'
    raw = json.dumps({"_embedded": {"data": {"article": {"content": html}}}}).encode()
    connector.body(raw, "application/hal+json", assets=[_PDF_REF], asset_bindings=[
        {"source_url": _PDF_LOCATOR, "resource_ref": _PDF_REF},
    ])
    draft = FixtureDraft(
        introduction="This reference covers pump service.",
        paraphrases={label: "Shield the pump while working on it."},
    )

    def refresh():
        job = refresh_article_job(
            runtime.repo, runtime.article_id, actor="fixture", reason="refresh the figure for the same anchor label",
            rewrite_profile_version=AUTO_PROFILE,
        )
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), registry=runtime.registry,
            object_store=runtime.objects, model_client=draft, job_id=job.job_id,
        )
        view = runtime.read_current()
        assert view["content_origin"] == "canonical", runtime.diagnostics()
        binding = load_source_revision(runtime.repo, view["source_revision_id"])
        assert binding.resource_manifest[0]["sha256"] == sha256(raw).hexdigest()
        assert "html_document_link_layout" not in binding.resource_manifest[0]
        assert binding.source_body == label
        assert _PDF_LOCATOR not in json.dumps(view["document"])
        return view, binding

    def set_image(color):
        with BytesIO() as png:
            Image.new("RGB", (4, 4), color).save(png, format="PNG")
            pixels = png.getvalue()
        connector.body(pixels, "image/png", ref=_PDF_REF, kind="binary")
        return sha256(pixels).hexdigest()

    initial_image = set_image("green")
    first, source = refresh()
    repeated, _ = refresh()
    assert repeated["source_revision_id"] == first["source_revision_id"]
    assert repeated["canonical_revision_id"] == first["canonical_revision_id"]
    assert source.resource_manifest[1]["sha256"] == initial_image
    assert draft.requests == [[label]]

    revised_image = set_image("red")
    changed, refreshed_source = refresh()
    assert changed["source_revision_id"] != first["source_revision_id"]
    assert refreshed_source.body_source_snapshot_id == source.body_source_snapshot_id
    assert refreshed_source.resource_manifest[1]["sha256"] == revised_image
    assert changed["images"][0]["content_sha256"] == revised_image
    assert draft.requests == [[label], [label]]


@pytest.mark.parametrize(('provider', 'embed_tag'), [('banktwo', 'iframe'), ('bankone', 'object'), ('banktwo', 'object')])
def test_linked_pdf_publishes_in_order_and_private_original_controls_visibility(runtime, monkeypatch, provider, embed_tag):
    from autodata_ingestion import source_adapters
    from autodata_ingestion.ocr import OCRUnavailable

    def unavailable_ocr(*_, **__):
        raise OCRUnavailable("Fixture OCR unavailable")

    monkeypatch.setattr(source_adapters, "extract_scanned_pdf_text", unavailable_ocr)
    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    raw_pdf, figure_pixels = _pdf_with_fixture_figure(trailing_text="Install the replacement.", blank_page=True)
    locator_attr = 'src' if embed_tag == 'iframe' else 'data'
    body = (
        '<p>Remove the pump.</p>'
        f'<{embed_tag} {locator_attr}="{_PDF_LOCATOR}" title="Private provider title">Hidden fallback.</{embed_tag}>'
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
