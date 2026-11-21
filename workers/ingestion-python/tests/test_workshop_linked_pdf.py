"""Linked provider PDF capture, publication, and withdrawal through the real lifecycle."""

from hashlib import sha256
from io import BytesIO
import json
from random import Random
from uuid import uuid4

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_types import PDF_REPEAT_MARGIN_LAYOUT
from autodata_ingestion.procedure_rewrite_auto import PROFILE as AUTO_PROFILE
from autodata_ingestion.source_job_persistence import refresh_article_job

from lifecycle_support import fresh_database, runtime
from test_pdf_figure_order import _pdf_with_logo


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


def _pdf_with_fixture_figure(*, trailing_text=None, second_figure=False):
    pixels = Random(7).randbytes(96 * 96 * 3)
    with Image.frombytes("RGB", (96, 96), pixels) as figure, BytesIO() as output:
        document = canvas.Canvas(output)
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
        document.save()
        return output.getvalue(), pixels


def _layout(document):
    return [(block["type"], block.get("text")) for block in document["blocks"]]


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


def test_linked_pdf_publishes_in_order_and_private_original_controls_visibility(runtime):
    provider = "banktwo"
    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    raw_pdf, figure_pixels = _pdf_with_fixture_figure(trailing_text="Install the replacement.")
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
    assert runtime.counters()["source"] == runtime.counters()["asset"] == 1
    assert len(draft.requests) == 1
