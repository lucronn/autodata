"""Draft from a source-only reprojection through the exact article worker."""

from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from autodata_ingestion.article_lifecycle_types import AUTOMATIC_REWRITE_PROFILE, SOURCE_BOUND_REWRITE_PROFILE
from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
from autodata_ingestion.source_job_persistence import schedule_source_bound_rewrite
from autodata_ingestion.source_revision_reprojection import apply_media_reprojection
from lifecycle_support import fresh_database, runtime, seed_configuration
from test_source_bound_rewrite_worker import run_job
from test_source_revision_reprojection import all_rows, media_preview_args, seed_historical_figure


class FixtureMediaDraft:
    _model = "fixture-retained-media"

    def __init__(self):
        self.calls = []

    def complete_json(self, prompt):
        request = json.loads(prompt)
        self.calls.append(request["profile_version"])
        slots = request["slots"]
        assert [slot["text"] for slot in slots] == ["Remove the pump.", "Install the replacement."]
        return {
            "introduction": "This procedure describes service information for the pump.",
            "replacements": [
                {"block_id": slot["block_id"], "path": slot["path"], "action": "rewrite", "text": text, "reason": ""}
                for slot, text in zip(slots, ("Take off the pump.", "Fit the replacement."), strict=True)
            ],
        }


@pytest.fixture
def source_only_figure(runtime, monkeypatch):
    configuration = seed_configuration(runtime.repo, runtime.vehicle)
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE vehicle_configurations SET trim='Touring' WHERE vehicle_configuration_id=%s",
                     (configuration,))
    for job in ensure_article_catalog_jobs(
        runtime.repo, vehicle_id=runtime.vehicle, vehicle_configuration_id=configuration,
    ):
        assert run_job(runtime, job.job_id, None, registry=runtime.registry)
    with runtime.repo.connect() as conn:
        article = conn.execute("""UPDATE canonical_articles SET target_rewrite_profile_version='technical-prose-v1'
            WHERE vehicle_configuration_id=%s AND provider_slug='bankone' RETURNING canonical_article_id""",
            (configuration,)).fetchone()
    runtime.articles["bankone"] = article["canonical_article_id"]
    original_id = seed_historical_figure(runtime, monkeypatch, "bankone")
    original_job_id = runtime.current_job_id()
    # The source-only correction inherits the article's active automatic profile.
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE canonical_articles SET target_rewrite_profile_version=%s WHERE canonical_article_id=%s",
                     (AUTOMATIC_REWRITE_PROFILE, runtime.article_id))
    fix = apply_media_reprojection(
        runtime.repo, runtime.article_id, original_id, **media_preview_args(runtime, original_id),
    )
    assert fix["status"] == "applied"
    source = runtime.read_current()
    assert source["source_revision_id"] != original_id and source["content_origin"] == "source"
    assert source["processing_error_code"] == "SOURCE_ONLY_REPROJECTION"
    assert [block["type"] for block in source["document"]["blocks"]] == ["paragraph", "image", "paragraph"]
    assert source["images"][0]["status"] == "available"
    runtime.reset_counters()
    return original_job_id, source


def schedule(runtime, source):
    return schedule_source_bound_rewrite(
        runtime.repo, runtime.article_id, expected_job_id=source["job_id"],
        expected_source_revision_id=source["source_revision_id"], actor="fixture-editor",
        reason="Draft distinct prose from the retained article and its figure.",
    )


def test_source_only_reprojection_can_draft_without_recapturing_the_figure(runtime, source_only_figure):
    original_job_id, source = source_only_figure
    before = all_rows(runtime.repo)
    figure_key = source["images"][0]["storage_key"]
    figure_bytes = runtime.objects.get_object(figure_key, max_bytes=1024 * 1024)
    [predecessor] = [row for row in before["source_fetch_jobs"] if row["source_fetch_job_id"] == source["job_id"]]
    [observation] = [
        row for row in before["canonical_article_source_observations"] if row["source_fetch_job_id"] == source["job_id"]
    ]
    assert (predecessor["status"], predecessor["phase"]) == ("needs_review", "completed")
    assert predecessor["lease_owner"] is None and predecessor["transformation_key"] is None
    assert observation["source_revision_id"] == source["source_revision_id"]
    assert observation["request_generation"] == predecessor["request_generation"]
    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(schedule, runtime, source)
        second = workers.submit(schedule, runtime, source)
        scheduled, repeated = first.result(), second.result()
    assert scheduled.job_id == repeated.job_id
    assert scheduled.created != repeated.created
    current = runtime.read_current()
    assert current["content_origin"] == "source" and current["document"] == source["document"]
    with runtime.repo.connect() as conn:
        job = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (scheduled.job_id,)).fetchone()
    assert (job["status"], job["phase"], job["max_attempts"]) == ("pending", "normalizing", 1)
    assert job["source_revision_id"] == source["source_revision_id"]
    binding = job["checkpoint"]["source_bound_rewrite"]
    assert binding["prior_job_id"] == str(predecessor["source_fetch_job_id"])
    assert binding["prior_source_observation_id"] == str(observation["source_observation_id"])
    model = FixtureMediaDraft()
    paused = []

    def observe_dispatch(phase):
        if phase == "after_model_dispatch":
            state = runtime.read_current()
            assert state["content_origin"] == "source" and state["availability"] == "available"
            assert state["document"] == source["document"] and state["images"] == source["images"]
            assert model.calls == []
            paused.append(phase)

    assert run_job(runtime, scheduled.job_id, model, registry=runtime.registry, hooks=observe_dispatch)
    assert paused == ["after_model_dispatch"] and model.calls == [SOURCE_BOUND_REWRITE_PROFILE]
    assert not run_job(runtime, scheduled.job_id, model)
    current = runtime.read_current()
    assert current["content_origin"] == "canonical" and current["source_revision_id"] == source["source_revision_id"]
    assert "Take off the pump." in current["body"] and "Fit the replacement." in current["body"]
    assert [block["type"] for block in current["document"]["blocks"]] == [
        "paragraph", "paragraph", "image", "paragraph",
    ]
    assert current["images"] == [
        {**image, "source_order": image["source_order"] + 1} for image in source["images"]
    ]
    assert runtime.objects.get_object(figure_key, max_bytes=1024 * 1024) == figure_bytes
    joined = schedule(runtime, source)
    assert joined.job_id == scheduled.job_id and not joined.created
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 1}

    after = all_rows(runtime.repo)
    for table in (
        "canonical_article_source_revisions", "canonical_article_source_observations", "source_snapshots", "source_artifacts",
    ):
        assert after[table] == before[table]
    original_ids = {source["job_id"], original_job_id}
    assert [row for row in after["source_fetch_jobs"] if row["source_fetch_job_id"] in original_ids] == [
        row for row in before["source_fetch_jobs"] if row["source_fetch_job_id"] in original_ids
    ]
    [attempt] = after["canonical_article_rewrite_attempts"]
    [revision] = after["canonical_article_revisions"]
    [event] = after["publication_events"]
    assert attempt["source_fetch_job_id"] == scheduled.job_id and attempt["status"] == "succeeded"
    assert revision["status"] == "published" and revision["validation_report"]["passed"]
    assert attempt["canonical_article_revision_id"] == event["canonical_article_revision_id"] == current["canonical_revision_id"]


@pytest.mark.parametrize(("damage", "error"), (
    ("current-generation", "CURRENT_JOB_CHANGED"),
    ("observation-generation", "PRIOR_JOB_CHANGED"),
    ("marker", "PRIOR_JOB_CHANGED"),
    ("withdrawn-figure", "SOURCE_UNAVAILABLE"),
))
def test_source_only_predecessor_rejects_mismatched_evidence_or_rights(runtime, source_only_figure, damage, error):
    _, source = source_only_figure
    with runtime.repo.connect() as conn:
        if damage in ("current-generation", "observation-generation"):
            conn.execute("""UPDATE canonical_articles SET request_generation=request_generation+1
                WHERE canonical_article_id=%s""", (runtime.article_id,))
            if damage == "observation-generation":
                # The owner stays aligned with the article while the observation keeps its historical generation.
                conn.execute("""UPDATE source_fetch_jobs SET request_generation=request_generation+1
                    WHERE source_fetch_job_id=%s""", (source["job_id"],))
        if damage == "marker":
            conn.execute("""UPDATE source_fetch_jobs SET checkpoint=checkpoint-'source_only_reprojection'
                WHERE source_fetch_job_id=%s""", (source["job_id"],))
        if damage == "withdrawn-figure":
            conn.execute("""UPDATE source_snapshots SET takedown_status='takedown'
                WHERE content_sha256=(SELECT resource_manifest->1->>'sha256'
                FROM canonical_article_source_revisions WHERE source_revision_id=%s)""",
                (source["source_revision_id"],))
    if damage == "withdrawn-figure":
        assert runtime.read_current()["availability"] == "unavailable"
    before = all_rows(runtime.repo)
    with pytest.raises(ValueError, match=f"^SOURCE_BOUND_REWRITE_{error}$"):
        schedule(runtime, source)
    assert all_rows(runtime.repo) == before
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}


def test_worker_rechecks_the_pinned_source_observation_before_dispatch(runtime, source_only_figure):
    original_job_id, source = source_only_figure
    job_id = schedule(runtime, source).job_id
    with runtime.repo.connect() as conn:
        superseded = conn.execute("""SELECT source_observation_id FROM canonical_article_source_observations
            WHERE source_fetch_job_id=%s""", (original_job_id,)).fetchone()
        conn.execute("""UPDATE source_fetch_jobs
            SET checkpoint=jsonb_set(checkpoint,'{source_bound_rewrite,prior_source_observation_id}',to_jsonb(%s::text))
            WHERE source_fetch_job_id=%s""", (str(superseded["source_observation_id"]), job_id))
    runtime.reset_counters()
    model = FixtureMediaDraft()
    assert run_job(runtime, job_id, model, registry=runtime.registry)
    assert model.calls == []
    current = runtime.read_current()
    assert current["processing_error_code"] == "SOURCE_BOUND_REWRITE_SOURCE_UNAVAILABLE"
    assert current["content_origin"] == "source" and current["document"] == source["document"]
    assert current["images"] == source["images"]
    after = all_rows(runtime.repo)
    assert after["canonical_article_rewrite_attempts"] == after["publication_events"] == []
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}
