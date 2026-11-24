"""Exact retained correction through the real lifecycle and publication storage."""

from copy import deepcopy
from dataclasses import replace
from io import BytesIO
import json
from uuid import uuid4

from PIL import Image
from psycopg.errors import CheckViolation
import pytest

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion.article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION, SOURCE_BOUND_CORRECTION_PROFILE,
    SOURCE_BOUND_REWRITE_PROFILE, digest_json,
)
from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
from autodata_ingestion.published_media_publication import _publication_evidence, preview_published_media_repair
from autodata_ingestion.source_job_persistence import (
    ensure_article_job, schedule_source_bound_correction, schedule_source_bound_rewrite,
)
from lifecycle_support import fresh_database, runtime, seed_configuration
from test_source_bound_rewrite_worker import FixtureDraft, retained_job, run_job


class CopiedSource:
    _model = "fixture-original"

    def complete_json(self, prompt):
        request = json.loads(prompt)
        return {
            "introduction": "This article describes service information.",
            "replacements": [{
                "block_id": slot["block_id"], "path": slot["path"], "text": slot["text"],
                # Leave the first draft unresolved so this fixture can reach v2/v3.
                "action": "retain" if request["profile_version"] == AUTOMATIC_REWRITE_PROFILE else slot["required_action"],
                "reason": "Keep the protected source wording.",
            } for slot in request["slots"]],
        }


class CorrectedSource:
    _model = "fixture-correction"

    def __init__(self, *, hold_cover=False):
        self.prompts = []
        self.responses = []
        self.hold_cover = hold_cover

    def complete_json(self, prompt):
        request = json.loads(prompt)
        self.prompts.append(prompt)
        masked = len(request["response_shape"]["rewrites"][0]["candidates"]) == 4
        rows = []
        for passage in request["passages"]:
            source = passage["source"]
            candidate = source.replace("Remove ", "Take off ", 1).replace("Install ", "Fit ", 1)
            if self.hold_cover and source == "Remove the cover." and not masked:
                candidate = source
            rows.append({
                "slot": passage["slot"], "candidates": [source, candidate, source, source] if masked
                else [source, candidate, source],
            })
        result = {"rewrites": rows}
        self.responses.append(deepcopy(result))
        return result


class InvalidIntroduction(CopiedSource):
    def complete_json(self, prompt):
        draft = super().complete_json(prompt)
        draft["introduction"] = "This procedure applies to 2016."
        for row in draft["replacements"]:
            if row["action"] == "rewrite":
                row["text"] = row["text"].replace("Remove ", "Take off ", 1).replace("Install ", "Fit ", 1)
        return draft


def attempt_rows(runtime, job_id):
    with runtime.repo.connect() as conn:
        return conn.execute("""SELECT * FROM canonical_article_rewrite_attempts
            WHERE source_fetch_job_id=%s ORDER BY lease_token,attempt_number""", (job_id,)).fetchall()


def schedule_correction(runtime, prior, source, budget):
    return schedule_source_bound_correction(
        runtime.repo, runtime.article_id, expected_job_id=prior,
        expected_source_revision_id=source, actor="fixture-editor", reason="Correct the exact source draft.",
        model_call_budget=budget,
    )


@pytest.fixture
def retained_media(runtime, request, monkeypatch):
    configuration = seed_configuration(runtime.repo, runtime.vehicle)
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE vehicle_configurations SET trim='Touring' WHERE vehicle_configuration_id=%s",
                     (configuration,))
    for result in ensure_article_catalog_jobs(
        runtime.repo, vehicle_id=runtime.vehicle, vehicle_configuration_id=configuration,
    ):
        assert run_job(runtime, result.job_id, None, registry=runtime.registry)
    with runtime.repo.connect() as conn:
        runtime.article_id = conn.execute("""SELECT canonical_article_id FROM canonical_articles
            WHERE vehicle_configuration_id=%s AND provider_slug='bankone'""",
            (configuration,)).fetchone()["canonical_article_id"]
    parts = ("cover", "shield", "panel", "plate", "retainer", "bracket", "handle", "latch",
             "hinge", "housing", "support", "guard", "sleeve", "bushing", "gasket", "seal", "plug")
    items = [f"<li>Remove the {part}.</li>" for part in parts]
    historical_ordinals = getattr(request, "param", None) == "historical_ordinals"
    heading = "" if historical_ordinals else "<h2>Cover Service</h2>"
    figure = ("<img data-resource-ref='figure' alt='Cover locations'>" if historical_ordinals
              else "<img src='/fixture/diagram' alt='Cover locations'>")
    body = (
        heading + "<ol start='3'>" + "".join(items[:8]) + "</ol>"
        + figure + "<ol start='11'>" + "".join(items[8:]) + "</ol><p>Do not force the cover.</p>"
    ).encode()
    connector = runtime.servers["bankone"]
    connector.body(body, assets=["figure"], asset_bindings=[
        {"source_url": "/fixture/diagram", "resource_ref": "figure"},
    ])
    png = BytesIO()
    Image.new("RGB", (10, 8), (23, 89, 132)).save(png, format="PNG")
    connector.body(png.getvalue(), media_type="image/png", ref="figure", kind="asset")

    if historical_ordinals:
        from autodata_ingestion import source_article_capture as capture

        capture_current = capture.capture_source_article

        def omit_ordinals(*args, **kwargs):
            result = capture_current(*args, registry=kwargs["registry"], object_store=kwargs["object_store"])
            document = deepcopy(result.source_document)
            for block in document["blocks"]:
                if block["type"] == "ordered_list":
                    del block["start"]
            text, steps, images = capture.project_document(document)
            return replace(result, source_document=document, source_body=text, source_steps=steps,
                           source_images=images, projection_version="source-projection-v2")

        monkeypatch.setattr(capture, "capture_source_article", omit_ordinals)

    first = ensure_article_job(runtime.repo, runtime.article_id, normalization_version=NORMALIZATION_VERSION,
                               rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE)
    assert run_job(runtime, first.job_id, CopiedSource(), registry=runtime.registry)
    source = runtime.read_current()
    assert source["content_origin"] == "source"
    assert source["images"][0]["status"] == "available"
    prior = schedule_source_bound_rewrite(
        runtime.repo, runtime.article_id, expected_job_id=first.job_id,
        expected_source_revision_id=source["source_revision_id"], actor="fixture-editor", reason="Retry.",
    )
    assert run_job(runtime, prior.job_id, InvalidIntroduction() if historical_ordinals else CopiedSource())
    expected_failure = "REWRITE_TECHNICAL_MUTATION" if historical_ordinals else "REWRITE_UNCHANGED"
    assert runtime.read_current()["processing_error_code"] == expected_failure
    return prior.job_id, source, parts


def test_four_dispatches_publish_and_media_replays_without_model_or_recapture(runtime, retained_media):
    prior, source, parts = retained_media
    previous = attempt_rows(runtime, prior)
    image_key = source["images"][0]["storage_key"]
    image_bytes = runtime.objects.get_object(image_key, max_bytes=1024 * 1024)
    model = CorrectedSource(hold_cover=True)
    job = schedule_correction(runtime, prior, source["source_revision_id"], 4)
    runtime.reset_counters()
    assert not run_job(runtime, None, model)
    assert not model.prompts

    class Interrupted(Exception):
        pass

    def stop_after_saved_candidate(phase):
        if phase == "after_model_result_commit":
            raise Interrupted

    with pytest.raises(Interrupted):
        run_job(runtime, job.job_id, model, hooks=stop_after_saved_candidate)
    assert runtime.read_current()["content_origin"] == "source"
    assert len(model.prompts) == 4
    runtime.expire_lease(job.job_id)
    assert not run_job(runtime, None, None)
    assert run_job(runtime, job.job_id, None)

    current = runtime.read_current()
    assert current["content_origin"] == "canonical"
    assert current["source_revision_id"] == source["source_revision_id"]
    # The introduction shifts the top-level block numbers by one.
    assert current["images"] == [
        {**image, "source_order": image["source_order"] + 1} for image in source["images"]
    ]
    assert runtime.objects.get_object(image_key, max_bytes=1024 * 1024) == image_bytes
    assert all(f"Take off the {part}." in current["body"] for part in parts)
    assert "Do not force the cover." in current["body"]
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}
    assert attempt_rows(runtime, prior) == previous
    attempts = attempt_rows(runtime, job.job_id)
    assert [item["attempt_number"] for item in attempts] == [1, 2, 3, 4]
    assert {item["profile_version"] for item in attempts} == {SOURCE_BOUND_CORRECTION_PROFILE}
    assert [item["response"] for item in attempts] == model.responses
    assert all(item["response_hash"] == digest_json(item["response"]) for item in attempts)
    assert all(item["dispatched_at"] is not None for item in attempts)
    assert [item["canonical_article_revision_id"] for item in attempts] == [
        None, None, None, current["canonical_revision_id"],
    ]

    binding = store.load_source_revision(runtime.repo, source["source_revision_id"])
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        revision, _, decision, attempt, response, version, _ = _publication_evidence(
            cur, article, binding, fixture_mode=True, lock=False,
        )
        assert revision["canonical_article_revision_id"] == current["canonical_revision_id"]
        assert decision == "UNREVIEWED"
        assert attempt["rewrite_attempt_id"] == attempts[-1]["rewrite_attempt_id"]
        assert len(response["replacements"]) == 18
        assert version.startswith("full-prose-auto-prompt-")
        blocks = revision["canonical_document"]["blocks"]
        assert [block["type"] for block in blocks] == [
            "paragraph", "heading", "ordered_list", "image", "ordered_list", "paragraph",
        ]
        assert [block["start"] for block in blocks if block["type"] == "ordered_list"] == [3, 11]

    with runtime.repo.connect() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE canonical_article_rewrite_attempts SET response_hash=%s
            WHERE rewrite_attempt_id=%s""", ("0" * 64, attempts[1]["rewrite_attempt_id"]))
        with pytest.raises(ValueError, match="REWRITE_CORRECTION_EVIDENCE_INVALID"):
            _publication_evidence(cur, article, binding, fixture_mode=True, lock=False)

    # The compatible migration preserves the old profiles' dispatch bound.
    with pytest.raises(CheckViolation):
        with runtime.repo.connect() as conn:
            conn.execute("""UPDATE canonical_article_rewrite_attempts SET attempt_number=4
                WHERE source_fetch_job_id=%s AND profile_version=%s""",
                (prior, SOURCE_BOUND_REWRITE_PROFILE))


def test_dispatch_interruption_cannot_repeat_calls_or_publish_a_partial_draft(runtime, retained_media):
    prior, source, _ = retained_media
    model = CorrectedSource(hold_cover=True)
    job = schedule_correction(runtime, prior, source["source_revision_id"], 4)
    dispatches = []

    class Interrupted(Exception):
        pass

    def stop_on_second_dispatch(phase):
        if phase == "after_model_dispatch":
            dispatches.append(phase)
            if len(dispatches) == 2:
                raise Interrupted

    with pytest.raises(Interrupted):
        run_job(runtime, job.job_id, model, hooks=stop_on_second_dispatch)
    assert len(model.prompts) == 1
    attempts = attempt_rows(runtime, job.job_id)
    assert [row["status"] for row in attempts] == ["succeeded", "dispatched"]
    assert all(row["canonical_article_revision_id"] is None for row in attempts)
    runtime.expire_lease(job.job_id)
    assert not run_job(runtime, job.job_id, model)
    assert len(model.prompts) == 1
    assert runtime.read_current()["content_origin"] == "source"


def test_correction_checks_rights_again_before_first_model_call(runtime, retained_job, monkeypatch):
    _, source_id, prior = retained_job
    assert run_job(runtime, prior, FixtureDraft(copy_source=True))
    job = schedule_correction(runtime, prior, source_id, 3)
    original = store.save_normalized_input

    def save_and_withdraw(*args, **kwargs):
        original(*args, **kwargs)
        with runtime.repo.connect() as conn:
            conn.execute("""UPDATE source_snapshots SET takedown_status='takedown'
                WHERE source_snapshot_id=(SELECT body_source_snapshot_id
                    FROM canonical_article_source_revisions WHERE source_revision_id=%s)""", (source_id,))

    monkeypatch.setattr(store, "save_normalized_input", save_and_withdraw)
    model = CorrectedSource()
    assert run_job(runtime, job.job_id, model)
    assert not model.prompts and attempt_rows(runtime, job.job_id) == []
    assert runtime.read_current()["canonical_revision_id"] is None


def test_safe_introduction_correction_resumes_with_no_provider_attempts(runtime, retained_job):
    _, source_id, prior = retained_job

    class InvalidPumpIntroduction(FixtureDraft):
        def complete_json(self, prompt):
            draft = super().complete_json(prompt)
            draft["introduction"] = "This procedure applies to 2016."
            return draft

    assert run_job(runtime, prior, InvalidPumpIntroduction())
    assert runtime.read_current()["processing_error_code"] == "REWRITE_TECHNICAL_MUTATION"
    job = schedule_correction(runtime, prior, source_id, 3)
    model = CorrectedSource()

    class Interrupted(Exception):
        pass

    def stop_after_saved_candidate(phase):
        if phase == "after_model_result_commit":
            raise Interrupted

    with pytest.raises(Interrupted):
        run_job(runtime, job.job_id, model, hooks=stop_after_saved_candidate)
    assert not model.prompts and attempt_rows(runtime, job.job_id) == []
    runtime.expire_lease(job.job_id)
    assert not run_job(runtime, None, None)
    assert run_job(runtime, job.job_id, None)
    assert runtime.read_current()["content_origin"] == "canonical"
    assert attempt_rows(runtime, job.job_id) == []


@pytest.mark.parametrize("retained_media", ["historical_ordinals"], indirect=True)
def test_zero_dispatch_correction_can_preview_a_retained_ordinal_repair(runtime, retained_media, tmp_path):
    prior, source, _ = retained_media
    job = schedule_correction(runtime, prior, source["source_revision_id"], 3)
    model = CorrectedSource()
    assert run_job(runtime, job.job_id, model)
    assert not model.prompts and attempt_rows(runtime, job.job_id) == []
    assert runtime.read_current()["content_origin"] == "canonical"

    preview = preview_published_media_repair(
        runtime.repo, article_id=runtime.article_id, source_revision_id=source["source_revision_id"],
        object_store=runtime.objects, destination=tmp_path / "ordinal-preview",
        fixture_mode=True, ordinals=True,
    )
    assert preview["status"] == "preview"
