"""Exact retained-source jobs through the normal worker and publication store."""

import json
from uuid import uuid4

import pytest

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE,
    NORMALIZATION_VERSION,
    SOURCE_BOUND_REWRITE_PROFILE,
)
from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
from autodata_ingestion.source_job_persistence import ensure_article_job, schedule_source_bound_rewrite
from lifecycle_support import fresh_database, runtime, seed_configuration


class FixtureDraft:
    _model = "fixture-mercury"

    def __init__(self, *, copy_source=False):
        self.copy_source = copy_source
        self.calls = []

    def complete_json(self, prompt):
        prompt = json.loads(prompt)
        self.calls.append(prompt["profile_version"])
        slots = prompt["slots"]
        assert [slot["text"] for slot in slots] == [
            "Remove the pump.", "Tighten the bolts to 18 N·m.", "Install the pump.",
        ]
        assert slots[1]["required_action"] == "retain"
        replacements = [
            {
                "block_id": slot["block_id"],
                "path": slot["path"],
                "action": action,
                "text": text,
                "reason": "Preserve the exact torque specification." if action == "retain" else "",
            }
            for slot, action, text in zip(
                slots,
                ("rewrite", "retain", "rewrite"),
                (
                    "Remove the pump." if self.copy_source else "Take off the pump.",
                    "Tighten the bolts to 18 N·m.",
                    "Fit the pump.",
                ),
                strict=True,
            )
        ]
        return {"introduction": "This procedure describes service information for the pump.", "replacements": replacements}


def run_job(runtime, job_id, model, *, registry=None, hooks=None):
    return run_article_worker_once(
        runtime.repo, worker_id=uuid4(), job_id=job_id,
        registry={} if registry is None else registry,
        object_store=runtime.objects, model_client=model, hooks=hooks,
    )


@pytest.fixture
def retained_job(runtime):
    configuration = seed_configuration(runtime.repo, runtime.vehicle)
    with runtime.repo.connect() as conn:
        conn.execute(
            "UPDATE vehicle_configurations SET trim='Touring' WHERE vehicle_configuration_id=%s", (configuration,),
        )
    for result in ensure_article_catalog_jobs(
        runtime.repo, vehicle_id=runtime.vehicle, vehicle_configuration_id=configuration,
    ):
        assert run_job(runtime, result.job_id, None, registry=runtime.registry)
    with runtime.repo.connect() as conn:
        runtime.article_id = conn.execute("""
            SELECT canonical_article_id FROM canonical_articles
            WHERE vehicle_configuration_id=%s AND provider_slug='bankone'
            """, (configuration,)).fetchone()["canonical_article_id"]
    runtime.servers["bankone"].body(
        b"<ol start='3'><li>Remove the pump.</li><li>Tighten the bolts to 18 N\xc2\xb7m.</li>"
        b"<li>Install the pump.</li></ol>"
    )
    runtime.reset_counters()
    first = ensure_article_job(
        runtime.repo, runtime.article_id,
        normalization_version=NORMALIZATION_VERSION, rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE,
    )
    copied = FixtureDraft(copy_source=True)
    assert run_job(runtime, first.job_id, copied, registry=runtime.registry)
    source = runtime.read_current()
    assert source["content_origin"] == "source"
    assert source["processing_error_code"] == "REWRITE_UNCHANGED"
    assert source["canonical_revision_id"] is None
    assert copied.calls == [AUTOMATIC_REWRITE_PROFILE]
    assert runtime.counters()["source"] == 1
    source_id = source["source_revision_id"]
    scheduled = schedule_source_bound_rewrite(
        runtime.repo, runtime.article_id, expected_job_id=first.job_id,
        expected_source_revision_id=source_id, actor="fixture-editor", reason="Retry the exact retained source.",
    )
    return first.job_id, source_id, scheduled.job_id


def test_retained_rewrite_replays_and_publishes_new_profile_without_recapture(runtime, retained_job):
    old_job_id, source_id, new_job_id = retained_job
    with runtime.repo.connect() as conn:
        original = conn.execute(
            "SELECT * FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s", (old_job_id,),
        ).fetchone()
        assert original["status"] == "failed"
        assert original["profile_version"] == AUTOMATIC_REWRITE_PROFILE
    runtime.reset_counters()
    draft = FixtureDraft()

    class WorkerStopped(Exception):
        pass

    def stop_after_saved_response(point):
        if point == "after_model_result_commit":
            raise WorkerStopped

    with pytest.raises(WorkerStopped):
        run_job(runtime, new_job_id, draft, hooks=stop_after_saved_response)
    assert runtime.read_current()["content_origin"] == "source"
    runtime.expire_lease(new_job_id)
    assert run_job(runtime, new_job_id, None)

    current = runtime.read_current()
    assert draft.calls == [SOURCE_BOUND_REWRITE_PROFILE]
    assert current["source_revision_id"] == source_id
    assert current["content_origin"] == "canonical"
    assert "Take off the pump." in current["body"]
    assert "Tighten the bolts to 18 N·m." in current["body"]
    assert "Fit the pump." in current["body"]
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}
    with runtime.repo.connect() as conn:
        assert conn.execute(
            "SELECT * FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s", (old_job_id,),
        ).fetchone() == original
        assert conn.execute("""
            SELECT a.profile_version,a.status,r.rewrite_profile_version,r.validation_report->>'profile_version' AS validated_profile
            FROM canonical_article_rewrite_attempts a
            JOIN canonical_article_revisions r ON r.canonical_article_revision_id=a.canonical_article_revision_id
            WHERE a.source_fetch_job_id=%s AND r.canonical_article_revision_id=%s
            """, (new_job_id, current["canonical_revision_id"])).fetchall() == [{
                "profile_version": SOURCE_BOUND_REWRITE_PROFILE, "status": "succeeded",
                "rewrite_profile_version": SOURCE_BOUND_REWRITE_PROFILE, "validated_profile": SOURCE_BOUND_REWRITE_PROFILE,
            }]
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_source_revisions").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 1


def test_retained_rewrite_rechecks_source_takedown_immediately_before_dispatch(runtime, retained_job, monkeypatch):
    _, source_id, new_job_id = retained_job
    original_prepare = store.prepare_rewrite_attempt

    def prepare_then_withdraw(*args, **kwargs):
        attempt = original_prepare(*args, **kwargs)
        with runtime.repo.connect() as conn:
            conn.execute("""
                UPDATE source_snapshots SET takedown_status='takedown'
                WHERE source_snapshot_id=(SELECT body_source_snapshot_id
                    FROM canonical_article_source_revisions WHERE source_revision_id=%s)
                """, (source_id,))
        return attempt

    monkeypatch.setattr(store, "prepare_rewrite_attempt", prepare_then_withdraw)
    draft = FixtureDraft()
    runtime.reset_counters()
    assert run_job(runtime, new_job_id, draft)
    assert draft.calls == []
    assert runtime.counters()["source"] == 0
    assert runtime.read_current()["availability"] == "unavailable"
    with runtime.repo.connect() as conn:
        assert conn.execute("""
            SELECT status,error_code,dispatched_at FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s
            """, (new_job_id,)).fetchone() == {
                "status": "failed", "error_code": "SOURCE_BOUND_REWRITE_SOURCE_UNAVAILABLE", "dispatched_at": None,
            }
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 0
