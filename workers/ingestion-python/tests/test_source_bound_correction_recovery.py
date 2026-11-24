"""Terminal correction recovery through the exact publication worker."""

import json
from uuid import uuid4

import pytest

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion.article_lifecycle_types import AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION
from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
from autodata_ingestion.source_job_persistence import ensure_article_job, schedule_source_bound_rewrite
from lifecycle_support import fresh_database, runtime, seed_configuration
from test_source_bound_correction_worker import CopiedSource, attempt_rows, schedule_correction
from test_source_bound_rewrite_worker import run_job


class UnchangedCorrection:
    _model = "fixture-unchanged"

    def complete_json(self, prompt):
        request = json.loads(prompt)
        count = len(request["response_shape"]["rewrites"][0]["candidates"])
        assert [passage["source"] for passage in request["passages"]] == ["Remove the upper cover."]
        return {"rewrites": [{"slot": 1, "candidates": ["Remove the upper cover."] * count}]}


@pytest.fixture
def terminal_correction(runtime):
    configuration_id = seed_configuration(runtime.repo, runtime.vehicle)
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE vehicle_configurations SET trim='Touring' WHERE vehicle_configuration_id=%s",
                     (configuration_id,))
    for job in ensure_article_catalog_jobs(
        runtime.repo, vehicle_id=runtime.vehicle, vehicle_configuration_id=configuration_id,
    ):
        assert run_job(runtime, job.job_id, None, registry=runtime.registry)
    with runtime.repo.connect() as conn:
        runtime.article_id = conn.execute("""SELECT canonical_article_id FROM canonical_articles
            WHERE vehicle_configuration_id=%s AND provider_slug='bankone'""",
            (configuration_id,)).fetchone()["canonical_article_id"]
    runtime.servers["bankone"].body(
        "<h2>Upper Cover Service</h2><ol start='3'><li>Remove the upper cover.</li>"
        "<li>Tighten the bolts to 18 N·m.</li></ol>".encode(),
    )
    captured = ensure_article_job(
        runtime.repo, runtime.article_id, normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE,
    )
    assert run_job(runtime, captured.job_id, CopiedSource(), registry=runtime.registry)
    source_id = runtime.read_current()["source_revision_id"]
    prior = schedule_source_bound_rewrite(
        runtime.repo, runtime.article_id, expected_job_id=captured.job_id, expected_source_revision_id=source_id,
        actor="fixture-editor", reason="Rewrite the retained cover procedure.",
    )
    assert run_job(runtime, prior.job_id, CopiedSource())
    job = schedule_correction(runtime, prior.job_id, source_id, 2)
    assert run_job(runtime, job.job_id, UnchangedCorrection())
    assert runtime.read_current()["processing_error_code"] == "REWRITE_UNCHANGED"
    assert [item["status"] for item in attempt_rows(runtime, job.job_id)] == ["succeeded", "succeeded"]
    runtime.reset_counters()
    return job.job_id, source_id, prior.job_id


def recover(runtime, job_id, source_id):
    return store.recover_source_bound_correction(
        runtime.repo, runtime.article_id, expected_job_id=job_id, expected_source_revision_id=source_id,
        actor="fixture-editor", reason="Recover the terminal correction from its archived replies.",
    )


def job_and_candidates(runtime, job_id):
    with runtime.repo.connect() as conn:
        job = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (job_id,)).fetchone()
        candidates = conn.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s",
                                  (job["transformation_key"],)).fetchall()
    return job, candidates


def test_terminal_correction_replays_and_publishes_exactly_once(runtime, terminal_correction):
    job_id, source_id, prior_id = terminal_correction
    archived = attempt_rows(runtime, job_id)
    prior_attempts = attempt_rows(runtime, prior_id)
    terminal, candidates = job_and_candidates(runtime, job_id)
    assert (terminal["status"], terminal["phase"], terminal["retryable"]) == ("dead_letter", "rewriting", False)
    assert candidates == []
    assert all(item["canonical_article_revision_id"] is None for item in archived)

    revision_id = recover(runtime, job_id, source_id)

    queued, (candidate,) = job_and_candidates(runtime, job_id)
    assert (queued["status"], queued["phase"]) == ("pending", "publishing")
    assert queued["lease_token"] == terminal["lease_token"]
    assert candidate["canonical_article_revision_id"] == revision_id
    assert candidate["source_revision_id"] == source_id
    assert candidate["status"] == "validated"
    assert candidate["validation_report"]["passed"]
    assert "The upper cover must be removed." in candidate["canonical_body"]
    assert "Tighten the bolts to 18 N·m." in candidate["canonical_body"]
    assert [
        block["start"] for block in candidate["canonical_document"]["blocks"] if block["type"] == "ordered_list"
    ] == [3]
    audit = queued["checkpoint"]["correction_recovery"]
    assert candidate["model_metadata"]["correction_recovery"] == audit
    assert audit["actor"] == "fixture-editor"
    assert audit["reason"] == "Recover the terminal correction from its archived replies."
    assert audit["terminal_error"] == "REWRITE_UNCHANGED"
    assert audit["attempts"] == [{
        "attempt_id": str(item["rewrite_attempt_id"]), "prompt_hash": item["prompt_hash"],
        "response_hash": item["response_hash"],
    } for item in archived]
    assert runtime.read_current()["content_origin"] == "source"
    with pytest.raises(ValueError, match="SOURCE_BOUND_CORRECTION_RECOVERY_STALE"):
        recover(runtime, job_id, source_id)
    assert job_and_candidates(runtime, job_id) == (queued, [candidate])
    assert not run_job(runtime, None, None)
    assert run_job(runtime, job_id, None)
    assert not run_job(runtime, job_id, None)
    with pytest.raises(ValueError, match="SOURCE_BOUND_CORRECTION_RECOVERY_STALE"):
        recover(runtime, job_id, source_id)

    current = runtime.read_current()
    assert current["content_origin"] == "canonical"
    assert current["source_revision_id"] == source_id
    assert current["canonical_revision_id"] == revision_id
    assert current["body"] == candidate["canonical_body"]
    assert attempt_rows(runtime, job_id) == [archived[0], {**archived[1], "canonical_article_revision_id": revision_id}]
    assert attempt_rows(runtime, prior_id) == prior_attempts
    with runtime.repo.connect() as conn:
        events = conn.execute("""SELECT canonical_article_revision_id FROM publication_events
            WHERE canonical_article_id=%s AND event_type='catalog.article.published'""",
            (runtime.article_id,)).fetchall()
    assert events == [{"canonical_article_revision_id": revision_id}]
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}


@pytest.mark.parametrize(("change", "error_code"), (
    ("generation", "SOURCE_BOUND_CORRECTION_RECOVERY_STALE"),
    ("source", "SOURCE_BOUND_CORRECTION_RECOVERY_STALE"),
    ("nonterminal", "SOURCE_BOUND_CORRECTION_RECOVERY_STALE"),
    ("rights", "SOURCE_BOUND_REWRITE_SOURCE_UNAVAILABLE"),
    ("response_hash", "REWRITE_CORRECTION_EVIDENCE_INVALID"),
    ("terminal_error", "REWRITE_CORRECTION_EVIDENCE_INVALID"),
))
def test_terminal_correction_rejects_changed_owner_rights_or_evidence(runtime, terminal_correction, change, error_code):
    job_id, source_id, _ = terminal_correction
    expected_source = uuid4() if change == "source" else source_id
    with runtime.repo.connect() as conn:
        if change == "generation":
            conn.execute("""UPDATE canonical_articles SET request_generation=request_generation+1
                WHERE canonical_article_id=%s""", (runtime.article_id,))
        if change == "nonterminal":
            conn.execute("""UPDATE source_fetch_jobs SET status='pending',error_code=NULL
                WHERE source_fetch_job_id=%s""", (job_id,))
        if change == "rights":
            conn.execute("""UPDATE source_snapshots SET takedown_status='takedown'
                WHERE source_snapshot_id=(SELECT body_source_snapshot_id
                    FROM canonical_article_source_revisions WHERE source_revision_id=%s)""", (source_id,))
        if change == "response_hash":
            conn.execute("""UPDATE canonical_article_rewrite_attempts SET response_hash=%s
                WHERE source_fetch_job_id=%s AND attempt_number=1""", ("0" * 64, job_id))
        if change == "terminal_error":
            conn.execute("""UPDATE source_fetch_jobs SET error_code='LEASE_ATTEMPTS_EXHAUSTED'
                WHERE source_fetch_job_id=%s""", (job_id,))

    before = job_and_candidates(runtime, job_id)
    archived = attempt_rows(runtime, job_id)
    with pytest.raises(ValueError, match=f"^{error_code}$"):
        recover(runtime, job_id, expected_source)
    assert job_and_candidates(runtime, job_id) == before
    assert attempt_rows(runtime, job_id) == archived
    assert runtime.read_current()["canonical_revision_id"] is None
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}
