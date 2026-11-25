"""Sentence correction with saved drafts and real publication leases."""

from hashlib import sha256
import json

import pytest
from psycopg.types.json import Jsonb

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion.article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, SOURCE_BOUND_CORRECTION_PROFILE, SOURCE_BOUND_REWRITE_PROFILE, digest_json,
)
from autodata_ingestion.published_media_publication import _publication_evidence
from autodata_ingestion.procedure_rewrite_auto import build_auto_prompt
from autodata_ingestion.source_job_persistence import schedule_source_bound_correction
from lifecycle_support import fresh_database, runtime
from test_source_bound_correction_worker import CopiedSource, InvalidIntroduction, attempt_rows, retained_media
from test_source_bound_rewrite_worker import failed_first_draft, retained_job, run_job


SENTENCE_METHOD = "source-bound-sentence-correction-v1"


class SentenceReplies:
    _model = "fixture-sentence-correction"

    def __init__(self, *, defer_install=False):
        self.defer_install = defer_install
        self.prompts = []
        self.responses = []

    def complete_json(self, prompt):
        request = json.loads(prompt)
        assert request["method"] == SENTENCE_METHOD
        self.prompts.append(prompt)
        if "passages" in request:
            entries = request["passages"]
            text_field = "source"
        else:
            entries = request["statements"]
            text_field = "statement"
        rewrites = []
        for entry in entries:
            source = entry[text_field]
            lower = source[0].lower() + source[1:]
            candidate = source.replace("Remove ", "Take off ", 1).replace("Install ", "Fit ", 1)
            if self.defer_install and text_field == "source" and source == "Install the pump.":
                candidate = f"Next, {lower}"
            rewrites.append({"slot": entry["slot"], "candidates": [source, candidate, f"First, {lower}"]})
        response = {"rewrites": rewrites}
        self.responses.append(response)
        return response


@pytest.fixture
def pump_draft(runtime, retained_job):
    first_job_id, source_id, prior_id = retained_job
    assert run_job(runtime, prior_id, CopiedSource())
    current = runtime.read_current()
    assert current["content_origin"] == "source" and current["source_revision_id"] == source_id
    assert current["processing_error_code"] == "REWRITE_UNCHANGED"
    return first_job_id, prior_id, current


def schedule(runtime, prior_id, source_id, *, budget=2, first_draft=False):
    return schedule_source_bound_correction(
        runtime.repo, runtime.article_id, expected_job_id=prior_id, expected_source_revision_id=source_id,
        actor="fixture-editor", reason="Correct unresolved sentences in the retained draft.",
        model_call_budget=budget, by_sentence=True, first_draft=first_draft,
    )


def source_job(runtime, job_id):
    with runtime.repo.connect() as conn:
        return conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (job_id,)).fetchone()


class WorkerStopped(Exception):
    pass


def stop_after_candidate(phase):
    if phase == "after_model_result_commit":
        raise WorkerStopped


@pytest.mark.parametrize(
    "fixture_name", ("pump_draft", "retained_media", "failed_first_draft"),
    ids=("two-rounds", "retained-figure", "direct-from-first-draft"),
)
def test_sentence_correction_replays_saved_rounds_without_refetch(runtime, request, fixture_name):
    fixture = request.getfixturevalue(fixture_name)
    first_draft = fixture_name == "failed_first_draft"
    if fixture_name == "pump_draft":
        _, prior_id, source = fixture
        expected_calls = 2
    elif first_draft:
        prior_id, _ = fixture
        source = runtime.read_current()
        expected_calls = 1
    else:
        prior_id, source, _ = fixture
        expected_calls = 1
    source_id = source["source_revision_id"]
    [original_attempt] = attempt_rows(runtime, prior_id)
    prior = source_job(runtime, prior_id)
    assert (prior["status"], prior["phase"], prior["source_revision_id"]) == ("dead_letter", "validating", source_id)
    expected_profile = AUTOMATIC_REWRITE_PROFILE if first_draft else SOURCE_BOUND_REWRITE_PROFILE
    assert original_attempt["profile_version"] == expected_profile
    assert original_attempt["status"] == "failed" and original_attempt["error_code"] == "REWRITE_UNCHANGED"
    assert original_attempt["response_hash"] == digest_json(original_attempt["response"])
    job = schedule(runtime, prior_id, source_id, budget=expected_calls, first_draft=first_draft)
    binding = source_job(runtime, job.job_id)["checkpoint"]["source_bound_rewrite"]
    assert binding["correction_method"] == SENTENCE_METHOD and binding["model_call_budget"] == expected_calls
    assert binding["prior_job_id"] == str(prior_id) and binding["source_revision_id"] == str(source_id)
    assert binding["prior_attempt_id"] == str(original_attempt["rewrite_attempt_id"])
    assert binding["prior_response_hash"] == original_attempt["response_hash"]
    if first_draft:
        with runtime.repo.connect() as conn:
            observation = conn.execute("""SELECT source_observation_id FROM canonical_article_source_observations
                WHERE source_fetch_job_id=%s AND source_revision_id=%s""", (prior_id, source_id)).fetchone()
            assert binding["first_draft_observation_id"] == str(observation["source_observation_id"])
    else:
        assert "first_draft_observation_id" not in binding
    assert not schedule(runtime, prior_id, source_id, budget=expected_calls, first_draft=first_draft).created
    model = SentenceReplies(defer_install=expected_calls == 2)
    observed_dispatches = []
    runtime.reset_counters()
    assert not run_job(runtime, None, model, registry=runtime.registry)

    def observe_then_stop(phase):
        if phase == "after_model_dispatch":
            current = runtime.read_current()
            assert current["content_origin"] == "source" and current["availability"] == "available"
            assert current["document"] == source["document"] and current["images"] == source["images"]
            attempts = attempt_rows(runtime, job.job_id)
            assert len(attempts) == len(model.prompts) + 1
            assert attempts[-1]["status"] == "dispatched" and attempts[-1]["response"] is None
            observed_dispatches.append(attempts[-1]["rewrite_attempt_id"])
        stop_after_candidate(phase)

    with pytest.raises(WorkerStopped):
        run_job(runtime, job.job_id, model, registry=runtime.registry, hooks=observe_then_stop)
    assert runtime.read_current()["content_origin"] == "source"
    archived = attempt_rows(runtime, job.job_id)
    assert len(archived) == len(model.prompts) == len(observed_dispatches) == expected_calls
    assert [row["attempt_number"] for row in archived] == list(range(1, expected_calls + 1))
    assert [row["rewrite_attempt_id"] for row in archived] == observed_dispatches
    assert {row["profile_version"] for row in archived} == {SOURCE_BOUND_CORRECTION_PROFILE}
    assert [row["prompt_hash"] for row in archived] == [sha256(prompt.encode()).hexdigest() for prompt in model.prompts]
    assert [row["response"] for row in archived] == model.responses
    assert all(row["status"] == "succeeded" and row["response_hash"] == digest_json(row["response"]) for row in archived)
    if expected_calls == 2:
        second = json.loads(model.prompts[1])
        assert [entry["statement"] for entry in second["statements"]] == ["Install the pump."]
    runtime.expire_lease(job.job_id)
    assert not run_job(runtime, None, None)
    assert run_job(runtime, job.job_id, None)
    assert not run_job(runtime, job.job_id, model)

    current = runtime.read_current()
    assert current["content_origin"] == "canonical" and current["source_revision_id"] == source_id
    if fixture_name != "retained_media":
        assert "The pump must be removed." in current["body"] and "Fit the pump." in current["body"]
        assert "Tighten the bolts to 18 N·m." in current["body"]
    else:
        assert "The cover must be removed." in current["body"] and "Do not force the cover." in current["body"]
        assert current["images"] == [
            {**image, "source_order": image["source_order"] + 1} for image in source["images"]
        ]
    assert attempt_rows(runtime, prior_id) == [original_attempt] and source_job(runtime, prior_id) == prior
    assert attempt_rows(runtime, job.job_id) == archived and len(model.prompts) == expected_calls
    assert [row["canonical_article_revision_id"] for row in archived] == [
        *([None] * (expected_calls - 1)), current["canonical_revision_id"],
    ]
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}
    source_binding = store.load_source_revision(runtime.repo, source_id)
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        revision, _, _, attempt, _, _, _ = _publication_evidence(
            cur, article, source_binding, fixture_mode=True, lock=False,
        )
        events = cur.execute("SELECT canonical_article_revision_id FROM publication_events").fetchall()
        if first_draft:
            profiles = cur.execute("""SELECT rewrite_profile_version FROM source_fetch_jobs
                WHERE canonical_article_id=%s ORDER BY request_generation""", (runtime.article_id,)).fetchall()
            assert [row["rewrite_profile_version"] for row in profiles] == [
                AUTOMATIC_REWRITE_PROFILE, SOURCE_BOUND_CORRECTION_PROFILE,
            ]
    assert revision["model_metadata"]["transformation_method"] == SENTENCE_METHOD
    assert revision["validation_report"]["passed"] and attempt == archived[-1]
    assert events == [{"canonical_article_revision_id": current["canonical_revision_id"]}]


def test_sentence_candidate_without_model_calls_can_resume_after_commit(runtime, retained_job):
    _, source_id, prior_id = retained_job
    assert run_job(runtime, prior_id, InvalidIntroduction())
    assert runtime.read_current()["processing_error_code"] == "REWRITE_TECHNICAL_MUTATION"
    job = schedule(runtime, prior_id, source_id, budget=1)
    runtime.reset_counters()
    model = SentenceReplies()
    with pytest.raises(WorkerStopped):
        run_job(runtime, job.job_id, model, hooks=stop_after_candidate)
    assert runtime.read_current()["content_origin"] == "source"
    assert model.prompts == [] and attempt_rows(runtime, job.job_id) == []
    runtime.expire_lease(job.job_id)
    assert not run_job(runtime, None, None)
    assert run_job(runtime, job.job_id, None)

    current = runtime.read_current()
    assert current["content_origin"] == "canonical" and current["source_revision_id"] == source_id
    assert "Take off the pump." in current["body"] and "Fit the pump." in current["body"]
    assert "2016" not in current["body"]
    assert attempt_rows(runtime, job.job_id) == []
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}


@pytest.mark.parametrize("damage", ("method", "reply"))
def test_sentence_resume_rejects_changed_saved_evidence(runtime, pump_draft, damage):
    _, prior_id, source = pump_draft
    job = schedule(runtime, prior_id, source["source_revision_id"], budget=1)
    model = SentenceReplies()
    with pytest.raises(WorkerStopped):
        run_job(runtime, job.job_id, model, hooks=stop_after_candidate)
    with runtime.repo.connect() as conn:
        if damage == "method":
            conn.execute("""UPDATE source_fetch_jobs
                SET checkpoint=jsonb_set(checkpoint,'{source_bound_rewrite,correction_method}',to_jsonb(%s::text))
                WHERE source_fetch_job_id=%s""", ("unknown-correction", job.job_id))
        else:
            conn.execute("""UPDATE canonical_article_rewrite_attempts SET response='{"rewrites":[]}'::jsonb
                WHERE source_fetch_job_id=%s""", (job.job_id,))
    runtime.reset_counters()
    runtime.expire_lease(job.job_id)
    assert not run_job(runtime, job.job_id, model, registry=runtime.registry)
    current = runtime.read_current()
    assert current["content_origin"] == "source" and current["canonical_revision_id"] is None
    assert current["processing_error_code"] == "AUTOMATIC_CANDIDATE_INVALID"
    assert len(attempt_rows(runtime, job.job_id)) == len(model.prompts) == 1
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT 1 FROM publication_events").fetchone() is None
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}


def test_sentence_schedule_rejects_over_budget_or_stale_predecessor(runtime, pump_draft):
    first_id, prior_id, source = pump_draft
    source_id = source["source_revision_id"]
    runtime.reset_counters()
    for budget in (0, 3, True):
        with pytest.raises(ValueError, match="BUDGET_INVALID"):
            schedule(runtime, prior_id, source_id, budget=budget)
    with pytest.raises(ValueError, match="SOURCE_BOUND_REWRITE_PRIOR_JOB_CHANGED"):
        schedule(runtime, first_id, source_id, budget=2)
    assert runtime.read_current()["job_id"] == prior_id
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}


@pytest.mark.parametrize("damage", ("prompt-context", "slot-position", "descriptor"))
def test_first_draft_correction_rejects_mismatched_saved_evidence(runtime, failed_first_draft, damage):
    prior_id, source_id = failed_first_draft
    [original] = attempt_rows(runtime, prior_id)
    with runtime.repo.connect() as conn:
        if damage == "prompt-context":
            prior = source_job(runtime, prior_id)
            source = prior["checkpoint"]["normalized_document"]
            empty_context_hash = sha256(build_auto_prompt(source, context={}).encode()).hexdigest()
            assert empty_context_hash != original["prompt_hash"]
            conn.execute("""UPDATE canonical_article_rewrite_attempts SET prompt_hash=%s WHERE rewrite_attempt_id=%s""",
                         (empty_context_hash, original["rewrite_attempt_id"]))
            conn.execute("""UPDATE canonical_article_revisions
                SET model_metadata=jsonb_set(model_metadata,'{prompt_hash}',to_jsonb(%s::text))
                WHERE canonical_article_revision_id=%s""",
                         (empty_context_hash, original["canonical_article_revision_id"]))
        elif damage == "slot-position":
            reply = original["response"]
            reply["replacements"].reverse()
            conn.execute("""UPDATE canonical_article_rewrite_attempts SET response=%s,response_hash=%s
                WHERE rewrite_attempt_id=%s""", (Jsonb(reply), digest_json(reply), original["rewrite_attempt_id"]))
        else:
            conn.execute("""UPDATE canonical_articles
                SET descriptor_source_snapshot_id=(SELECT resolution_source_snapshot_id
                    FROM canonical_article_source_observations WHERE source_fetch_job_id=%s)
                WHERE canonical_article_id=%s""", (prior_id, runtime.article_id))

    runtime.reset_counters()
    with pytest.raises(ValueError, match="SOURCE_BOUND_CORRECTION_PRIOR_DRAFT_INVALID"):
        schedule(runtime, prior_id, source_id, budget=1, first_draft=True)
    assert runtime.read_current()["job_id"] == prior_id
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}


def test_first_draft_correction_rechecks_bound_resolution_before_dispatch(runtime, failed_first_draft):
    prior_id, source_id = failed_first_draft
    job = schedule(runtime, prior_id, source_id, budget=1, first_draft=True)
    with runtime.repo.connect() as conn:
        conn.execute("""UPDATE source_snapshots SET takedown_status='takedown'
            WHERE source_snapshot_id=(SELECT resolution_source_snapshot_id
                FROM canonical_article_source_observations WHERE source_fetch_job_id=%s)""", (prior_id,))
    runtime.reset_counters()
    model = SentenceReplies()
    run_job(runtime, job.job_id, model, registry=runtime.registry)
    assert model.prompts == [] and attempt_rows(runtime, job.job_id) == []
    assert runtime.read_current()["canonical_revision_id"] is None
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}
