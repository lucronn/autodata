from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion.article_lifecycle import run_article_job
from autodata_ingestion.article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE,
    NORMALIZATION_VERSION,
    SOURCE_BOUND_REWRITE_PROFILE,
    transformation_key,
)
from autodata_ingestion.source_article_capture import capture_source_article
from autodata_ingestion.source_job_persistence import (
    claim_source_job,
    ensure_article_job,
    fail_source_job,
    schedule_source_bound_rewrite,
)
from lifecycle_support import fresh_database, insert_descriptor, seed_configuration, seed_snapshot, seed_vehicle
from test_article_worker import AutomaticModel
from test_source_article_capture import capture_fixture


def _v1_source(repo, capture_fixture, *, published=False):
    vehicle = seed_vehicle(repo)
    configuration = seed_configuration(repo, vehicle)
    context = capture_fixture.context("bankone")
    context = replace(
        context,
        key=replace(context.key, vehicle_id=vehicle, vehicle_configuration_id=configuration),
        descriptor_snapshot_id=seed_snapshot(repo),
        resolution_snapshot_id=seed_snapshot(repo, b"retained vehicle resolution"),
    )
    article = insert_descriptor(
        repo, context.key, descriptor=context.descriptor, rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE
    )
    job = ensure_article_job(
        repo, article, normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE,
    )
    lease = claim_source_job(repo, worker_id=uuid4(), job_id=job.job_id)
    capture_fixture.body("bankone", b"<p>Remove the pump.</p>")
    captured = capture_source_article(context, registry=capture_fixture.registry, object_store=capture_fixture.objects)
    source = store.store_captured_source(repo, lease, captured)
    lease = replace(lease, source_revision_id=source, phase="normalizing")
    model = AutomaticModel(unchanged=not published)
    run_article_job(repo, lease, registry={}, object_store=None, model_client=model)
    state = store.load_article_state(repo, article)
    assert model.calls == 1 and state["source_revision_id"] == source
    assert state["processing_state"] == ("completed" if published else "failed")
    assert bool(state["canonical_revision_id"]) is published
    return article, job.job_id, source


def _schedule(repo, scope, *, actor="fixture"):
    article, job, source = scope
    return schedule_source_bound_rewrite(
        repo, article, expected_job_id=job, expected_source_revision_id=source,
        actor=actor, reason="Re-author the retained pump procedure",
    )


def _job(repo, job_id):
    with repo.connect() as conn:
        return conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (job_id,)).fetchone()


def test_concurrent_source_bound_admission_reuses_one_exact_job(fresh_database, capture_fixture):
    repo = fresh_database()
    scope = _v1_source(repo, capture_fixture)
    article, prior_id, source_id = scope
    prior = _job(repo, prior_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _schedule(repo, scope), range(2)))
    assert sum(result.created for result in results) == 1
    assert results[0].job_id == results[1].job_id
    assert all(result.source_revision_id == source_id for result in results)

    job = _job(repo, results[0].job_id)
    source = store.load_source_revision(repo, source_id)
    assert job["transformation_key"] == transformation_key(
        article, source.source_fingerprint, NORMALIZATION_VERSION, SOURCE_BOUND_REWRITE_PROFILE,
        projection_version=source.projection_version,
    )
    assert job["transformation_key"] != prior["transformation_key"]
    assert job["max_attempts"] == 1 and job["retry_count"] == 0
    assert job["checkpoint"] == {"source_bound_rewrite": {
        "version": 1, "prior_job_id": str(prior_id), "source_revision_id": str(source_id),
        "prior_generation": prior["request_generation"], "actor": "fixture",
        "reason": "Re-author the retained pump procedure",
    }}
    assert job["request_generation"] == prior["request_generation"] + 1
    assert _job(repo, prior_id) == prior
    assert not ensure_article_job(
        repo, article, normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=SOURCE_BOUND_REWRITE_PROFILE,
    ).created
    state = store.load_article_state(repo, article)
    assert state["job_id"] == job["source_fetch_job_id"] and state["content_origin"] == "source"
    with pytest.raises(ValueError, match="^SOURCE_BOUND_REWRITE_ALREADY_SCHEDULED$"):
        _schedule(repo, scope, actor="another-operator")

    first = claim_source_job(repo, worker_id=uuid4(), job_id=job["source_fetch_job_id"])
    assert first.source_revision_id == source_id and first.rewrite_profile_version == SOURCE_BOUND_REWRITE_PROFILE
    fail_source_job(repo, first, code="REWRITE_UNCHANGED", retryable=False)
    assert claim_source_job(repo, worker_id=uuid4(), job_id=job["source_fetch_job_id"]) is None
    stopped = _job(repo, first.job_id)
    assert stopped["status"] == "dead_letter" and stopped["retry_count"] == 1
    assert _schedule(repo, scope).job_id == first.job_id
    assert _job(repo, prior_id) == prior


def test_source_bound_model_parking_resumes_without_an_extra_attempt(fresh_database, capture_fixture):
    repo = fresh_database()
    scope = _v1_source(repo, capture_fixture)
    result = _schedule(repo, scope)
    lease = claim_source_job(repo, worker_id=uuid4(), model_ready=False, job_id=result.job_id)
    run_article_job(repo, lease, registry={}, object_store=None, model_client=None)
    parked = _job(repo, result.job_id)
    assert parked["status"] == "failed" and parked["error_code"] == "MODEL_NOT_CONFIGURED"
    assert parked["checkpoint"]["awaiting_model_configuration"] is True
    assert claim_source_job(repo, worker_id=uuid4(), model_ready=False, job_id=result.job_id) is None

    resumed = claim_source_job(repo, worker_id=uuid4(), model_ready=True, job_id=result.job_id)
    assert resumed is not None and resumed.job_id == lease.job_id and resumed.token > lease.token
    assert resumed.source_revision_id == scope[2] and resumed.phase == "rewriting"
    assert _job(repo, result.job_id)["retry_count"] == parked["retry_count"] == 1
    with repo.connect() as conn:
        assert conn.execute(
            "SELECT 1 FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s", (result.job_id,),
        ).fetchone() is None


@pytest.mark.parametrize("blocked", ["source", "quarantine", "retained_descriptor", "retained_resolution", "published"])
def test_source_bound_admission_leaves_ineligible_current_state_intact(fresh_database, capture_fixture, blocked):
    repo = fresh_database()
    scope = _v1_source(repo, capture_fixture, published=blocked == "published")
    article, prior_id, source_id = scope
    if blocked == "quarantine":
        with repo.connect() as conn:
            conn.execute(
                """INSERT INTO source_review_items(source_review_item_id,item_key,item_kind,reason_code,source_snapshot_ids)
                SELECT gen_random_uuid(),gen_random_uuid()::text,'quarantine','FIXTURE',
                    jsonb_build_array(body_source_snapshot_id::text)
                FROM canonical_article_source_revisions WHERE source_revision_id=%s""",
                (source_id,),
            )
    elif blocked in ("retained_descriptor", "retained_resolution"):
        replacement = seed_snapshot(repo, b"new descriptor from a later catalog observation")
        with repo.connect() as conn:
            observation = conn.execute(
                """SELECT descriptor_source_snapshot_id,resolution_source_snapshot_id
                FROM canonical_article_source_observations WHERE source_revision_id=%s
                ORDER BY captured_at,source_observation_id LIMIT 1""", (source_id,),
            ).fetchone()
            conn.execute("UPDATE canonical_articles SET descriptor_source_snapshot_id=%s WHERE canonical_article_id=%s",
                         (replacement, article))
            if blocked == "retained_descriptor":
                conn.execute("UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=%s",
                             (observation["descriptor_source_snapshot_id"],))
            else:
                conn.execute(
                    """INSERT INTO source_review_items(source_review_item_id,item_key,item_kind,reason_code,source_snapshot_ids)
                    VALUES (gen_random_uuid(),gen_random_uuid()::text,'quarantine','FIXTURE',jsonb_build_array(%s::text))""",
                    (observation["resolution_source_snapshot_id"],),
                )
    attempted_scope = (article, prior_id, uuid4()) if blocked == "source" else scope
    expected = {
        "source": "PRIOR_JOB_CHANGED", "quarantine": "SOURCE_UNAVAILABLE", "published": "ALREADY_PUBLISHED",
        "retained_descriptor": "SOURCE_UNAVAILABLE", "retained_resolution": "SOURCE_UNAVAILABLE",
    }
    before = store.load_article_state(repo, article)
    with pytest.raises(ValueError, match=f"^SOURCE_BOUND_REWRITE_{expected[blocked]}$"):
        _schedule(repo, attempted_scope)
    assert store.load_article_state(repo, article) == before
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"] == 1


@pytest.mark.parametrize("crash_stage", ["claimed", "prepared", "dispatched", "ambiguous"])
def test_source_bound_expired_lease_preserves_only_an_undelivered_attempt(fresh_database, capture_fixture, crash_stage):
    from autodata_ingestion.procedure_normalize import normalize_procedure_article
    from autodata_ingestion.source_job_persistence import LeaseLost, park_automatic_for_model

    repo = fresh_database()
    scope = _v1_source(repo, capture_fixture)
    result = _schedule(repo, scope)
    first = claim_source_job(repo, worker_id=uuid4(), job_id=result.job_id)
    attempt = None
    if crash_stage != "claimed":
        source = store.load_source_revision(repo, first.source_revision_id)
        normalized = normalize_procedure_article(source.as_article(), resource_manifest=source.resource_manifest)
        store.save_normalized_input(repo, first, normalized)
        attempt = store.prepare_rewrite_attempt(
            repo, first, normalized["normalized_document"], context=source.vehicle, model="fixture-auto",
        )
        if crash_stage == "dispatched":
            store.mark_rewrite_dispatched(repo, first, attempt)
            with pytest.raises(ValueError, match="^MODEL_CONFIGURATION_PARK_INVALID$"):
                park_automatic_for_model(repo, first)
        elif crash_stage == "ambiguous":
            store.record_rewrite_failure(repo, first, code="MODEL_DELIVERY_AMBIGUOUS", ambiguous=True)
    with repo.connect() as conn:
        conn.execute(
            "UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s",
            (first.job_id,),
        )

    resumed = claim_source_job(repo, worker_id=uuid4(), job_id=result.job_id, model_ready=False)
    if crash_stage in ("dispatched", "ambiguous"):
        assert resumed is None
        assert _job(repo, first.job_id)["status"] == "dead_letter"
        assert claim_source_job(repo, worker_id=uuid4(), job_id=result.job_id) is None
        with repo.connect() as conn:
            old = conn.execute(
                "SELECT status,dispatched_at FROM canonical_article_rewrite_attempts WHERE rewrite_attempt_id=%s",
                (attempt,),
            ).fetchone()
        assert old["status"] == "ambiguous"
        assert bool(old["dispatched_at"]) is (crash_stage == "dispatched")
        return

    assert resumed is not None and resumed.job_id == first.job_id and resumed.token > first.token
    assert _job(repo, first.job_id)["retry_count"] == 1
    if attempt is not None:
        with pytest.raises(LeaseLost):
            store.mark_rewrite_dispatched(repo, first, attempt)
        with repo.connect() as conn:
            old = conn.execute(
                "SELECT status,error_code,dispatched_at,completed_at FROM canonical_article_rewrite_attempts WHERE rewrite_attempt_id=%s",
                (attempt,),
            ).fetchone()
        assert old["status"] == "failed" and old["error_code"] == "MODEL_NOT_DISPATCHED_LEASE_EXPIRED"
        assert old["dispatched_at"] is None and old["completed_at"] is not None

    run_article_job(repo, resumed, registry={}, object_store=None, model_client=None)
    assert _job(repo, first.job_id)["error_code"] == "MODEL_NOT_CONFIGURED"
    assert claim_source_job(repo, worker_id=uuid4(), job_id=result.job_id, model_ready=False) is None
    configured = claim_source_job(repo, worker_id=uuid4(), job_id=result.job_id)
    assert configured is not None and configured.token > resumed.token
    model = AutomaticModel()
    run_article_job(repo, configured, registry={}, object_store=None, model_client=model)
    assert model.calls == 1
    assert store.load_article_state(repo, scope[0])["content_origin"] == "canonical"
    assert _job(repo, first.job_id)["retry_count"] == 1
    with repo.connect() as conn:
        [delivered] = conn.execute(
            """SELECT attempt_number,status FROM canonical_article_rewrite_attempts
            WHERE source_fetch_job_id=%s AND dispatched_at IS NOT NULL""", (result.job_id,),
        ).fetchall()
    assert delivered == {"attempt_number": 1, "status": "succeeded"}
