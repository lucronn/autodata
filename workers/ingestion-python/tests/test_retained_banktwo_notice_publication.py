"""Verify a retained Banktwo notice correction through the normal publication records."""

import json
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image

from autodata_ingestion import source_article_capture
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_store import automatic_candidate_validation, load_source_revision
from autodata_ingestion.article_lifecycle_types import RETAINED_SHORT_ACTION_REPAIR_PROFILE
from autodata_ingestion.procedure_rewrite_recovery import (
    BANKONE_REFERENCED_RECOVERY_METHOD, recover_structured_bankone_first_draft,
)
from autodata_ingestion.procedure_rewrite_auto import PROFILE, failed_rewrite_passages
from autodata_ingestion.published_media_publication import _publication_evidence_for_revision
from autodata_ingestion.retained_banktwo_notice_publication import (
    preview_bankone_definition_heading_publication, preview_banktwo_notice_publication,
    preview_bankone_list_boundary_publication, publish_bankone_definition_heading,
    publish_bankone_list_boundary, publish_banktwo_notice,
)
from autodata_ingestion.source_job_persistence import (
    publish_source_bound_first_draft, read_bankone_archive_structure, refresh_article_job,
    source_bound_correction_prior_attempt,
)
from lifecycle_support import fresh_database, runtime
from test_bankone_graphic_positions import GRAPHIC_LOCATOR
from test_paid_catalog_api_integration import configure_scoped_runtime
from test_first_draft_recovery_worker import queue_article
from test_source_bound_rewrite_worker import run_job
from test_source_revision_reprojection import all_rows


class NoticeModel:
    _model = "fixture-publication-model"

    def __init__(self):
        self.calls = 0

    def complete_json(self, prompt):
        self.calls += 1
        paraphrases = {
            "Remove the pump.": "Take off the pump.",
            "Install the replacement.": "Fit the replacement unit.",
            "Note: Keep the pump seal in position.": "Note: Leave the pump seal where it is.",
            "CorrectionPump alignment": "Correcting pump alignment",
        }
        return {
            "introduction": "This procedure describes pump removal and replacement.",
            "replacements": [{
                "block_id": slot["block_id"], "path": slot["path"],
                "action": "rewrite", "text": paraphrases[slot["text"]], "reason": "",
            } for slot in json.loads(prompt)["slots"]],
        }


def test_notice_repair_switches_source_and_publication_together(runtime, monkeypatch):
    configure_scoped_runtime(runtime, "banktwo")
    connector = runtime.servers["banktwo"]
    html = (
        '<ol><li>Remove the pump.<img data-resource-ref="figure" alt="Pump figure"></li>'
        '<div><b>Note:</b> Keep the pump seal in position.</div>'
        '<li>Install the replacement.</li></ol>'
    )
    connector.body(json.dumps({"_embedded": {"data": {"article": {"content": html}}}}).encode(),
                   "application/hal+json", assets=["figure"])
    source_capture = source_article_capture.capture_source_article

    def legacy_capture(*args, **kwargs):
        kwargs["keep_banktwo_list_notices"] = False
        return source_capture(*args, **kwargs)

    model = NoticeModel()
    refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="publish pre-correction article",
                        rewrite_profile_version=PROFILE)
    with monkeypatch.context() as historical:
        historical.setattr(source_article_capture, "capture_source_article", legacy_capture)
        assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=model)
    prior = runtime.read_current()
    assert prior["content_origin"] == "canonical", runtime.diagnostics()
    before = all_rows(runtime.repo)
    traffic = runtime.counters()

    manifest = preview_banktwo_notice_publication(runtime.repo, prior["source_revision_id"], object_store=runtime.objects)
    assert all_rows(runtime.repo) == before
    args = dict(expected=manifest, object_store=runtime.objects, actor="fixture",
                reason="Restore the original notice position and preserve the archived rewrite.")

    with pytest.raises(ValueError, match="BANKTWO_NOTICE_PUBLICATION_STALE"):
        publish_banktwo_notice(runtime.repo, **{**args, "expected": {
            **manifest, "repaired_published_document_hash": "0" * 64,
        }})

    def stop_inside_publication(point):
        assert point == "inside_publication" and runtime.read_current() == prior
        raise RuntimeError("fixture interruption")

    with pytest.raises(RuntimeError, match="fixture interruption"):
        publish_banktwo_notice(runtime.repo, hooks=stop_inside_publication, **args)
    assert all_rows(runtime.repo) == before

    result = publish_banktwo_notice(runtime.repo, **args)
    assert result["status"] == "published"
    assert publish_banktwo_notice(runtime.repo, **args) == {**result, "status": "already_published"}
    current = runtime.read_current()
    assert str(current["source_revision_id"]) == result["source_revision_id"]
    assert str(current["canonical_revision_id"]) == result["canonical_revision_id"]
    source = load_source_revision(runtime.repo, current["source_revision_id"])
    for document, offset, first, last in (
        (source.source_document, 0, "Remove the pump.", "Install the replacement."),
        (current["document"], 1, "Take off the pump.", "Fit the replacement unit."),
    ):
        first_list, notice, second_list = document["blocks"][offset:]
        assert [block["type"] for block in (first_list, notice, second_list)] == ["ordered_list", "callout", "ordered_list"]
        assert (notice["label"], notice["text"]) == ("Note", "Keep the pump seal in position.")
        assert first_list["items"][0]["text"] == first
        assert first_list["items"][0]["blocks"][0]["type"] == "image"
        assert second_list["start"] == 2 and second_list["items"] == [last]

    assert {x["content_sha256"] for x in source.source_images} == {x["content_sha256"] for x in prior["images"]}
    after = all_rows(runtime.repo)
    assert len(after["publication_events"]) == len(before["publication_events"]) + 1
    assert after["canonical_article_rewrite_attempts"] == before["canonical_article_rewrite_attempts"]
    assert model.calls == 1 and runtime.counters() == {**traffic, "schedule": traffic["schedule"] + 1}
    with runtime.repo.connect() as conn:
        candidate = conn.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                                 (result["canonical_revision_id"],)).fetchone()
        job = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (result["job_id"],)).fetchone()
        assert automatic_candidate_validation(conn, job, candidate, require_current=True).passed
        article = conn.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                               (runtime.article_id,)).fetchone()
        article["target_rewrite_profile_version"] = RETAINED_SHORT_ACTION_REPAIR_PROFILE
        binding = SimpleNamespace(source_revision_id=candidate["source_revision_id"])
        with pytest.raises(ValueError, match="PUBLISHED_MEDIA_REPAIR_PROFILE_UNSUPPORTED"):
            _publication_evidence_for_revision(
                conn, article, binding, candidate["canonical_article_revision_id"], fixture_mode=False, lock=False,
            )
        retained, *_ = _publication_evidence_for_revision(
            conn, article, binding, candidate["canonical_article_revision_id"], fixture_mode=False, lock=False,
            expected_profile=PROFILE,
        )
        assert retained == candidate


def test_definition_heading_repair_preserves_existing_steps_and_media(runtime, monkeypatch):
    configure_scoped_runtime(runtime, "bankone")
    connector = runtime.servers["bankone"]
    connector.body(
        b'<p>Remove the pump.</p><dl><dt class="document-subheader">Correction</dt>'
        b'<dd><span class="satitle">Pump alignment</span><ol start="2">'
        b'<li>Install the replacement.</li></ol></dd></dl>'
        b'<mtr-image id="71" alt="Alignment marks"></mtr-image>'
        b'<table><tbody><tr><td colspan="2">Torque</td></tr>'
        b'<tr><td>First</td><td>25 Nm</td></tr></tbody></table>',
        assets=["figure"],
    )
    connector.body(b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"/>',
                   "image/svg+xml", ref="figure", kind="asset")
    stream = BytesIO()
    Image.new("RGB", (24, 24), "green").save(stream, format="PNG")
    monkeypatch.setattr(source_article_capture, "rasterize_svg", lambda svg, *, timeout: stream.getvalue())
    client = runtime.registry["bankone"]
    read = client.read_resource

    def bound_graphic(resource, **kwargs):
        result = read(resource, **kwargs)
        return replace(result, source_locator=GRAPHIC_LOCATOR) if resource == "figure" else result

    monkeypatch.setattr(client, "read_resource", bound_graphic)
    capture = source_article_capture.capture_source_article

    def before_heading_support(*args, **kwargs):
        kwargs["keep_bankone_definition_headings"] = False
        return capture(*args, **kwargs)

    model = NoticeModel()
    refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="publish pre-correction article",
                        rewrite_profile_version=PROFILE)
    with monkeypatch.context() as historical:
        historical.setattr(source_article_capture, "capture_source_article", before_heading_support)
        assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=model)
    prior = runtime.read_current()
    assert prior["content_origin"] == "canonical", runtime.diagnostics()
    before = all_rows(runtime.repo)
    plan = preview_bankone_definition_heading_publication(runtime.repo, prior["source_revision_id"],
                                                          object_store=runtime.objects)
    assert all_rows(runtime.repo) == before
    args = dict(expected=plan, object_store=runtime.objects, actor="fixture",
                reason="Restore the separate authored section headings.")
    result = publish_bankone_definition_heading(runtime.repo, **args)
    assert publish_bankone_definition_heading(runtime.repo, **args) == {**result, "status": "already_published"}
    current = runtime.read_current()
    source = load_source_revision(runtime.repo, current["source_revision_id"])
    assert [block["text"] for block in source.source_document["blocks"] if block["type"] == "heading"] == [
        "Correction", "Pump alignment",
    ]
    assert [block["text"] for block in current["document"]["blocks"] if block["type"] == "heading"] == [
        "Correction", "Pump alignment",
    ]
    assert "Take off the pump." in current["body"] and "Fit the replacement unit." in current["body"]
    assert [image["content_sha256"] for image in current["images"]] == [
        image["content_sha256"] for image in prior["images"]
    ]


def test_bankone_list_repair_carries_archived_wording_and_links_atomically(runtime, monkeypatch):
    configure_scoped_runtime(runtime, "bankone")
    job_id = queue_article(runtime)
    connector = runtime.servers["bankone"]
    html = (
        '<h2>Fixture System Service</h2><dl><dt>Installation Procedure</dt><dd><ol>'
        '<li>Install the hinge bracket. Refer to <mtr-doc-link id="fixture-install">'
        'Hinge Bracket Installation</mtr-doc-link>.</li>'
        '<ul><li><mtr-doc-link id="fixture-details">Related service information</mtr-doc-link></li></ul>'
        '<ol><div class="note"><p><b>Note:</b></p></div>'
        '<li>Fill the fixture reservoir. Refer to <mtr-doc-link id="fixture-fill">'
        'Reservoir Filling Instructions.</mtr-doc-link></li></ol>'
        '<li>Install the pivot pin. Refer to <mtr-doc-link id="fixture-pin">'
        'Pivot Pin Installation</mtr-doc-link>.</li></ol></dd></dl>'
        '<mtr-image id="71" alt="Bracket locations"></mtr-image>'
    ).encode()
    connector.body(html, assets=["figure"])
    connector.body(b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"/>',
                   "image/svg+xml", ref="figure", kind="asset")
    stream = BytesIO()
    Image.new("RGB", (24, 24), "green").save(stream, format="PNG")
    monkeypatch.setattr(source_article_capture, "rasterize_svg", lambda svg, *, timeout: stream.getvalue())
    client = runtime.registry["bankone"]
    read = client.read_resource

    def bound_graphic(ref, **kwargs):
        result = read(ref, **kwargs)
        return replace(result, source_locator=GRAPHIC_LOCATOR) if ref == "figure" else result

    monkeypatch.setattr(client, "read_resource", bound_graphic)
    capture = source_article_capture.capture_source_article

    def before_list_support(*args, **kwargs):
        kwargs["keep_bankone_list_boundaries"] = False
        return capture(*args, **kwargs)

    class CopyDraft:
        _model = "fixture-list-model"
        calls = 0

        def complete_json(self, prompt):
            self.calls += 1
            return {"introduction": "This article covers the service information that follows.", "replacements": [
                {"block_id": slot["block_id"], "path": slot["path"], "action": slot["required_action"],
                 "text": ("The fixture reservoir must be filled. See Reservoir Filling Instructions for the procedure."
                          if slot["text"].startswith("Fill the fixture reservoir.") else slot["text"]),
                 "reason": "Preserve the authored parameter."}
                for slot in json.loads(prompt)["slots"]
            ]}

    model = CopyDraft()
    with monkeypatch.context() as historical:
        historical.setattr(source_article_capture, "capture_source_article", before_list_support)
        historical.setattr("autodata_ingestion.article_lifecycle_store._read_automatic_bankone_structure", lambda *_: None)
        assert run_job(runtime, job_id, model, registry=runtime.registry)
    source_id = runtime.read_current()["source_revision_id"]
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        prior_job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (job_id,)).fetchone()
        attempt = source_bound_correction_prior_attempt(cur, prior_job, first_draft=True)
    archive = read_bankone_archive_structure(
        runtime.repo, runtime.article_id, job_id, source_id, object_store=runtime.objects, structure_version=3,
    )
    checked = recover_structured_bankone_first_draft(prior_job["checkpoint"]["normalized_document"], attempt,
        archive["proof"], method=BANKONE_REFERENCED_RECOVERY_METHOD)
    if not checked or checked.error_code is not None:
        pytest.fail(json.dumps({
            "error": attempt["error_code"], "proof": archive["proof"]["slots"],
            "failed": failed_rewrite_passages(prior_job["checkpoint"]["normalized_document"], attempt["response"],
                prompt_version=attempt["guard_version"], bankone_structure=archive["proof"]),
        }))
    publish_source_bound_first_draft(
        runtime.repo, runtime.article_id, expected_job_id=job_id, expected_source_revision_id=source_id,
        recovery_method=BANKONE_REFERENCED_RECOVERY_METHOD, expected_recovery_hash=checked.evidence["output_hash"],
        actor="fixture-editor", reason="Recover the exact retained draft.", object_store=runtime.objects,
    )
    prior = runtime.read_current()
    nodes = [node for node in source_article_capture._walk(prior["document"]) if node.get("type") == "link"]
    [old_link] = nodes
    label = sha256(old_link["text"].encode()).hexdigest()
    target = sha256(b"fixture-target").hexdigest()
    body = sha256(html).hexdigest()
    with runtime.repo.connect() as conn:
        conn.execute("""INSERT INTO canonical_article_link_bindings(canonical_article_id,source_revision_id,
            canonical_article_revision_id,block_id,label_sha256,authored_id_sha256,target_ref_sha256,body_sha256)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", (runtime.article_id, source_id, prior["canonical_revision_id"],
            old_link["block_id"], label, sha256(b"fixture-details").hexdigest(), target, body))

    before = all_rows(runtime.repo)
    manifest = preview_bankone_list_boundary_publication(runtime.repo, source_id, object_store=runtime.objects)
    assert manifest["retained_link_count"] == 1 and all_rows(runtime.repo) == before
    args = dict(expected=manifest, object_store=runtime.objects, actor="fixture",
                reason="Preserve authored step boundaries and the exact reference.")

    def stop(point):
        assert point == "inside_publication" and runtime.read_current() == prior
        raise RuntimeError("fixture interruption")

    with pytest.raises(RuntimeError, match="fixture interruption"):
        publish_bankone_list_boundary(runtime.repo, hooks=stop, **args)
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS links FROM canonical_article_link_bindings").fetchone()["links"] == 1
    assert all_rows(runtime.repo) == before

    result = publish_bankone_list_boundary(runtime.repo, **args)
    assert publish_bankone_list_boundary(runtime.repo, **args) == {**result, "status": "already_published"}
    current = runtime.read_current()
    visible = current["body"]
    assert visible.index("The hinge bracket must be installed.") < visible.index("Note:")
    assert visible.index("Note:") < visible.index("The fixture reservoir must be filled.")
    assert [image["content_sha256"] for image in current["images"]] == [image["content_sha256"] for image in prior["images"]]
    with runtime.repo.connect() as conn:
        copied = conn.execute("""SELECT * FROM canonical_article_link_bindings WHERE canonical_article_revision_id=%s""",
                              (result["canonical_revision_id"],)).fetchone()
        assert copied["source_revision_id"] == current["source_revision_id"]
        assert copied["target_ref_sha256"] == target and copied["label_sha256"] == label
        assert copied["body_sha256"] == body and copied["block_id"] != old_link["block_id"]
        candidate = conn.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                                 (result["canonical_revision_id"],)).fetchone()
        job = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (result["job_id"],)).fetchone()
        assert automatic_candidate_validation(conn, job, candidate, require_current=True).passed
    assert model.calls == 1
    assert all_rows(runtime.repo)["canonical_article_rewrite_attempts"] == before["canonical_article_rewrite_attempts"]
    assert model.calls == 1
