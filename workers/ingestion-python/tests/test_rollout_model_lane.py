"""Exercise exact rollout selection against an isolated database."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from autodata_ingestion.article_lifecycle_store import mark_rewrite_dispatched, prepare_rewrite_attempt, upsert_article_descriptor
from autodata_ingestion.article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION, ArticleKey, digest_json, transformation_key,
)
from autodata_ingestion.rollout_model_lane import claim_rollout_model_job
from autodata_ingestion.source_job_persistence import ensure_article_job
from lifecycle_support import fresh_database, seed_configuration, seed_snapshot, seed_vehicle
from test_procedure_rewrite_full import document


def rollout():
    return {
        "schema": 2, "enabled": True, "rollout_id": str(uuid4()), "source_sha": "a" * 40,
        "cutoff": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "max_jobs": 10, "providers": ["bankone", "banktwo"], "reservations": [],
    }


def parked_job(repo, snapshot, *, provider="bankone", admitted=True, source_sha=None, scoped=True):
    vehicle = seed_vehicle(repo)
    configuration = seed_configuration(repo, vehicle) if scoped else None
    key = ArticleKey(provider, vehicle, configuration, "fixture-vehicle", "fixture-article")
    descriptor = seed_snapshot(repo, f"{vehicle}: descriptor".encode())
    resolution = seed_snapshot(repo, f"{vehicle}: resolution".encode())
    body = seed_snapshot(repo, f"{vehicle}: body".encode())
    article = upsert_article_descriptor(
        repo, key, {"title": "Pump fixture"}, descriptor, 0, rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE,
    )
    job = ensure_article_job(
        repo, article, normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE,
    ).job_id
    source = uuid4()
    fingerprint = digest_json(str(source))
    normalized = document("Remove the access cover.")
    marker = {"rollout_id": snapshot["rollout_id"], "source_sha": source_sha or snapshot["source_sha"],
              "cutoff": snapshot["cutoff"], "max_model_attempts": 1}
    checkpoint = {"new_article_rollout": marker, "awaiting_model_configuration": True,
                  "normalized_document": normalized, "normalized_hash": digest_json(normalized)}
    with repo.connect() as conn:
        conn.execute("""INSERT INTO catalog_article_provider_scopes(catalog_provider_scope_id,vehicle_id,
            vehicle_configuration_id,scope_key,provider_slug,source_vehicle_ref,resolution_source_snapshot_id,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'complete')""",
            (uuid4(), vehicle, configuration, key.scope_key, provider, key.source_vehicle_ref, resolution))
        conn.execute("""INSERT INTO canonical_article_source_revisions(source_revision_id,canonical_article_id,
            source_fingerprint,body_source_snapshot_id,resource_manifest,source_document,source_images,
            source_body,source_steps,projection_status,evidence_manifest,captured_at)
            VALUES (%s,%s,%s,%s,'[]',%s,'[]','Remove the access cover.','[]','readable','[{}]',clock_timestamp())""",
            (source, article, fingerprint, body, Jsonb(normalized)))
        conn.execute("""INSERT INTO canonical_article_source_observations(source_observation_id,canonical_article_id,
            source_revision_id,source_fetch_job_id,request_generation,body_provider_revision,resource_provenance,
            captured_context,resolution_source_snapshot_id,descriptor_source_snapshot_id,captured_at)
            VALUES (%s,%s,%s,%s,0,'fixture','[]','{"vehicle":{"region":"US"}}',%s,%s,clock_timestamp())""",
            (uuid4(), article, source, job, resolution, descriptor))
        conn.execute("""UPDATE source_fetch_jobs SET source_revision_id=%s,transformation_key=%s,
            status='failed',phase='rewriting',retryable=true,error_code='MODEL_NOT_CONFIGURED',
            max_attempts=1,retry_count=1,lease_token=1,checkpoint=%s WHERE source_fetch_job_id=%s""",
            (source, transformation_key(article, fingerprint, NORMALIZATION_VERSION, AUTOMATIC_REWRITE_PROFILE),
             Jsonb(checkpoint), job))
        conn.execute("UPDATE canonical_articles SET current_source_revision_id=%s WHERE canonical_article_id=%s",
                     (source, article))
    if admitted:
        snapshot["reservations"].append({"job_id": str(job), "reserved_at": datetime.now(timezone.utc).isoformat()})
    return job, resolution


def add_attempt(repo, job, *, lease_token, dispatched_at=None):
    with repo.connect() as conn:
        conn.execute("""INSERT INTO canonical_article_rewrite_attempts(rewrite_attempt_id,source_fetch_job_id,
            lease_token,attempt_number,provider,model,profile_version,prompt_hash,input_hash,status,dispatched_at)
            VALUES (%s,%s,%s,1,'inception','fixture',%s,%s,%s,%s,%s)""",
            (uuid4(), job, lease_token, AUTOMATIC_REWRITE_PROFILE, "b" * 64, "c" * 64,
             "prepared" if dispatched_at is None else "dispatched", dispatched_at))


def test_rollout_model_lane_claims_only_eligible_retained_source(fresh_database):
    repo = fresh_database()
    snapshot = rollout()
    parked_job(repo, snapshot, admitted=False)
    parked_job(repo, snapshot, source_sha="unknown")
    _, withdrawn = parked_job(repo, snapshot)
    done, _ = parked_job(repo, snapshot, provider="banktwo")
    add_attempt(repo, done, lease_token=1)
    rebound, _ = parked_job(repo, snapshot, source_sha="c" * 40, scoped=False)
    target, _ = parked_job(repo, snapshot, provider="banktwo")
    assert claim_rollout_model_job(repo, {**snapshot, "enabled": False}, worker_id=uuid4()) is None
    assert claim_rollout_model_job(repo, {**snapshot, "schema": 1}, worker_id=uuid4()) is None
    with repo.connect() as conn:
        conn.execute("UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=%s", (withdrawn,))
    claimed = claim_rollout_model_job(repo, snapshot, worker_id=uuid4())
    assert claimed.job_id == rebound and claimed.source_revision_id
    assert claimed.checkpoint.get("rollout_model_observation_id")
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()).job_id == target
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()) is None


def test_actual_dispatch_fence_counts_rebound_jobs_and_ignores_expired_or_prepared_attempts(fresh_database):
    repo = fresh_database()
    snapshot = rollout()
    rebound, _ = parked_job(repo, snapshot, source_sha="c" * 40)
    now = datetime.now(timezone.utc)
    for lease_token in range(1, 10):
        add_attempt(repo, rebound, lease_token=lease_token, dispatched_at=now)
    add_attempt(repo, rebound, lease_token=10)
    add_attempt(repo, rebound, lease_token=11, dispatched_at=now - timedelta(hours=25))
    target, _ = parked_job(repo, snapshot)
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()).job_id == target
    parked_job(repo, snapshot)
    add_attempt(repo, rebound, lease_token=12, dispatched_at=now)
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()) is None


def test_rollout_model_lane_rechecks_source_permission_at_dispatch(fresh_database):
    repo = fresh_database()
    snapshot = rollout()
    job, resolution = parked_job(repo, snapshot)
    lease = claim_rollout_model_job(repo, snapshot, worker_id=uuid4())
    assert lease.job_id == job
    normalized = lease.checkpoint["normalized_document"]
    attempt = prepare_rewrite_attempt(repo, lease, normalized, context={"region": "US"}, model="fixture")
    with repo.connect() as conn:
        conn.execute("UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=%s", (resolution,))
    with pytest.raises(ValueError, match="SOURCE_BOUND_REWRITE_SOURCE_UNAVAILABLE"):
        mark_rewrite_dispatched(repo, lease, attempt)
    with repo.connect() as conn:
        row = conn.execute("SELECT dispatched_at FROM canonical_article_rewrite_attempts WHERE rewrite_attempt_id=%s",
                           (attempt,)).fetchone()
    assert row["dispatched_at"] is None
