"""Exercise exact rollout selection against an isolated database."""

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from autodata_ingestion.article_lifecycle import run_article_job
from autodata_ingestion.article_lifecycle_store import mark_rewrite_dispatched, prepare_rewrite_attempt, upsert_article_descriptor
from autodata_ingestion.article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION, SOURCE_BOUND_CORRECTION_PROFILE,
    ArticleKey, digest_json, transformation_key,
)
from autodata_ingestion import commerce_service, rollout_model_lane
from autodata_ingestion.rollout_model_lane import claim_rollout_model_job
from autodata_ingestion.source_job_persistence import ensure_article_job
from lifecycle_support import fresh_database, seed_configuration, seed_snapshot, seed_vehicle
from test_commerce_simulation import account, call, setup_env
from test_procedure_rewrite_full import document


LIFT_GATE_SOURCE = "The cover protects the drive gear from debris while the lift gate travels through its normal range."


def rollout():
    return {
        "schema": 2, "enabled": True, "rollout_id": str(uuid4()), "source_sha": "a" * 40,
        "cutoff": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "max_jobs": 10, "providers": ["bankone", "banktwo"], "reservations": [],
    }


def parked_job(repo, snapshot, *, provider="bankone", admitted=True, source_sha=None, scoped=True,
               source_body="Remove the access cover."):
    vehicle = seed_vehicle(repo)
    configuration = seed_configuration(repo, vehicle, engine_displacement_l=2.0) if scoped else None
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
    normalized = document(source_body)
    marker = {"rollout_id": snapshot["rollout_id"], "source_sha": source_sha or snapshot["source_sha"],
              "cutoff": snapshot["cutoff"], "max_model_attempts": 1}
    checkpoint = {"new_article_rollout": marker, "awaiting_model_configuration": True,
                  "normalized_document": normalized, "normalized_hash": digest_json(normalized)}
    captured_context = {
        "vehicle": {"region": "US"}, "descriptor": {"title": "Pump fixture"},
        "evidence_ids": ["fixture-evidence"],
    }
    with repo.connect() as conn:
        conn.execute("""INSERT INTO catalog_article_provider_scopes(catalog_provider_scope_id,vehicle_id,
            vehicle_configuration_id,scope_key,provider_slug,source_vehicle_ref,resolution_source_snapshot_id,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'complete')""",
            (uuid4(), vehicle, configuration, key.scope_key, provider, key.source_vehicle_ref, resolution))
        conn.execute("""INSERT INTO canonical_article_source_revisions(source_revision_id,canonical_article_id,
            source_fingerprint,body_source_snapshot_id,resource_manifest,source_document,source_images,
            source_body,source_steps,projection_status,evidence_manifest,captured_at)
            VALUES (%s,%s,%s,%s,'[]',%s,'[]',%s,'[]','readable','[{}]',clock_timestamp())""",
            (source, article, fingerprint, body, Jsonb(normalized), source_body))
        conn.execute("""INSERT INTO canonical_article_source_observations(source_observation_id,canonical_article_id,
            source_revision_id,source_fetch_job_id,request_generation,body_provider_revision,resource_provenance,
            captured_context,resolution_source_snapshot_id,descriptor_source_snapshot_id,captured_at)
            VALUES (%s,%s,%s,%s,0,'fixture','[]',%s,%s,%s,clock_timestamp())""",
            (uuid4(), article, source, job, Jsonb(captured_context), resolution, descriptor))
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


def add_attempt(repo, job, *, lease_token, dispatched_at=None, profile=AUTOMATIC_REWRITE_PROFILE, number=1):
    with repo.connect() as conn:
        conn.execute("""INSERT INTO canonical_article_rewrite_attempts(rewrite_attempt_id,source_fetch_job_id,
            lease_token,attempt_number,provider,model,profile_version,prompt_hash,input_hash,status,dispatched_at)
            VALUES (%s,%s,%s,%s,'inception','fixture',%s,%s,%s,%s,%s)""",
            (uuid4(), job, lease_token, number, profile, "b" * 64, "c" * 64,
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


class CopiedFirstDraft:
    _model = "fixture-first-draft"

    def complete_json(self, prompt):
        request = json.loads(prompt)
        return {
            "introduction": "This article describes service information.",
            "replacements": [{
                "block_id": slot["block_id"], "path": slot["path"], "text": slot["text"],
                "action": slot["required_action"], "reason": "",
            } for slot in request["slots"]],
        }


def rejected_first_draft(repo, snapshot):
    job, _ = parked_job(repo, snapshot, provider="banktwo", source_body=LIFT_GATE_SOURCE)
    lease = claim_rollout_model_job(repo, snapshot, worker_id=uuid4())
    assert lease.job_id == job
    run_article_job(repo, lease, registry={}, object_store=None, model_client=CopiedFirstDraft())
    with repo.connect() as conn:
        result = conn.execute("""SELECT j.source_fetch_job_id,j.source_revision_id,j.canonical_article_id,
                j.error_code,j.status,a.vehicle_configuration_id
            FROM source_fetch_jobs j JOIN canonical_articles a USING (canonical_article_id)
            WHERE j.source_fetch_job_id=%s""", (job,)).fetchone()
    assert (result["status"], result["error_code"]) == ("dead_letter", "REWRITE_UNCHANGED")
    return result


def grant_scope(repo, configuration, monkeypatch):
    setup_env(monkeypatch)
    service = commerce_service.configured_commerce(connection_factory=repo.connect)
    receipt = call(service, "checkouts", {
        **account(repo), "expected_mode": "simulation", "configuration_id": str(configuration),
        "region": "US", "terms_version": commerce_service.TERMS, "idempotency_key": str(uuid4()),
    })
    assert receipt["state"] == "owned"
    return receipt["order_id"]


def test_automatic_correction_admits_once_and_resumes_its_pending_job(fresh_database, monkeypatch):
    repo = fresh_database()
    snapshot = rollout()
    prior = rejected_first_draft(repo, snapshot)
    grant_scope(repo, prior["vehicle_configuration_id"], monkeypatch)
    # Losing the worker between the schedule commit and the lease leaves one
    # pending correction for the next model lane tick.
    claim = rollout_model_lane.claim_source_job
    monkeypatch.setattr(rollout_model_lane, "claim_source_job", lambda *args, **kwargs: None)
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()) is None
    with repo.connect() as conn:
        pending = conn.execute("""SELECT source_fetch_job_id,status FROM source_fetch_jobs
            WHERE canonical_article_id=%s AND rewrite_profile_version=%s""",
            (prior["canonical_article_id"], SOURCE_BOUND_CORRECTION_PROFILE)).fetchone()
    assert pending["status"] == "pending"

    monkeypatch.setattr(rollout_model_lane, "claim_source_job", claim)
    lease = claim_rollout_model_job(repo, snapshot, worker_id=uuid4())
    assert lease.job_id == pending["source_fetch_job_id"]
    assert lease.source_revision_id == prior["source_revision_id"]
    assert lease.rewrite_profile_version == SOURCE_BOUND_CORRECTION_PROFILE
    binding = lease.checkpoint["source_bound_rewrite"]
    assert binding["prior_job_id"] == str(prior["source_fetch_job_id"])
    assert binding["model_call_budget"] == 2
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()) is None


@pytest.mark.parametrize("revoked", [False, True])
def test_automatic_correction_requires_current_paid_scope(fresh_database, monkeypatch, revoked):
    repo = fresh_database()
    snapshot = rollout()
    prior = rejected_first_draft(repo, snapshot)
    if revoked:
        order_id = grant_scope(repo, prior["vehicle_configuration_id"], monkeypatch)
        with repo.connect() as conn:
            conn.execute("UPDATE entitlements SET status='revoked' WHERE commerce_order_id=%s", (order_id,))
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()) is None
    with repo.connect() as conn:
        assert conn.execute("""SELECT count(*) AS total FROM source_fetch_jobs
            WHERE canonical_article_id=%s""", (prior["canonical_article_id"],)).fetchone()["total"] == 1


def test_automatic_correction_uses_two_slots_in_shared_delivery_window(fresh_database, monkeypatch):
    repo = fresh_database()
    snapshot = rollout()
    prior = rejected_first_draft(repo, snapshot)
    grant_scope(repo, prior["vehicle_configuration_id"], monkeypatch)
    filler, _ = parked_job(repo, snapshot)
    now = datetime.now(timezone.utc)
    for token in range(1, 9):
        add_attempt(repo, filler, lease_token=token, dispatched_at=now)
    # Nine of ten deliveries have been spent, leaving no room for both
    # correction rounds.
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()) is None
    with repo.connect() as conn:
        conn.execute("""UPDATE canonical_article_rewrite_attempts
            SET dispatched_at=%s WHERE source_fetch_job_id=%s AND lease_token=8""",
            (now - timedelta(hours=25), filler))

    correction = claim_rollout_model_job(repo, snapshot, worker_id=uuid4())
    assert correction.source_revision_id == prior["source_revision_id"]
    for number in (1, 2):
        add_attempt(repo, correction.job_id, lease_token=correction.token,
                    dispatched_at=now, profile=SOURCE_BOUND_CORRECTION_PROFILE, number=number)
    parked_job(repo, snapshot)
    # Both corrective deliveries are attributed to the original rollout.
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()) is None


@pytest.mark.parametrize("spent_dispatches", [9, 10])
def test_automatic_correction_finalizes_an_expired_delivery_without_model_budget(
    fresh_database, monkeypatch, spent_dispatches,
):
    repo = fresh_database()
    snapshot = rollout()
    prior = rejected_first_draft(repo, snapshot)
    grant_scope(repo, prior["vehicle_configuration_id"], monkeypatch)
    filler, _ = parked_job(repo, snapshot)
    now = datetime.now(timezone.utc)
    for token in range(1, 8):
        add_attempt(repo, filler, lease_token=token, dispatched_at=now)
    correction = claim_rollout_model_job(repo, snapshot, worker_id=uuid4())
    assert correction.rewrite_profile_version == SOURCE_BOUND_CORRECTION_PROFILE

    class DeliveryInterrupted(Exception):
        pass

    class InterruptedModel:
        _model = "fixture-sentence-correction"

        def complete_json(self, prompt):
            raise DeliveryInterrupted

    with pytest.raises(DeliveryInterrupted):
        run_article_job(repo, correction, registry={}, object_store=None, model_client=InterruptedModel())

    with repo.connect() as conn:
        dispatched, = conn.execute("""SELECT rewrite_attempt_id,dispatched_at,status
            FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s""", (correction.job_id,)).fetchall()
        assert dispatched["status"] == "dispatched" and dispatched["dispatched_at"]
        conn.execute("""UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second'
            WHERE source_fetch_job_id=%s""", (correction.job_id,))
    if spent_dispatches == 10:
        add_attempt(repo, filler, lease_token=8, dispatched_at=now)

    # The first draft, seven filler dispatches, and the interrupted delivery
    # leave at most one slot. Expiring the lease needs no further delivery.
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()) is None
    with repo.connect() as conn:
        expired = conn.execute("""SELECT j.status,j.error_code,j.retryable,j.lease_owner,
                j.source_revision_id,a.current_source_revision_id,a.current_canonical_revision_id
            FROM source_fetch_jobs j JOIN canonical_articles a USING (canonical_article_id)
            WHERE j.source_fetch_job_id=%s""", (correction.job_id,)).fetchone()
        attempt, = conn.execute("""SELECT rewrite_attempt_id,dispatched_at,status,error_code
            FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s""", (correction.job_id,)).fetchall()
    assert (expired["status"], expired["error_code"]) == ("dead_letter", "LEASE_ATTEMPTS_EXHAUSTED")
    assert not expired["retryable"] and expired["lease_owner"] is None
    assert expired["source_revision_id"] == expired["current_source_revision_id"] == prior["source_revision_id"]
    assert expired["current_canonical_revision_id"] is None
    assert attempt == {
        **dispatched, "status": "ambiguous", "error_code": "MODEL_DELIVERY_AMBIGUOUS",
    }


def test_automatic_correction_resumes_saved_publication_when_model_budget_is_exhausted(
    fresh_database, monkeypatch,
):
    repo = fresh_database()
    snapshot = rollout()
    prior = rejected_first_draft(repo, snapshot)
    grant_scope(repo, prior["vehicle_configuration_id"], monkeypatch)
    filler, _ = parked_job(repo, snapshot)
    now = datetime.now(timezone.utc)
    for token in range(1, 8):
        add_attempt(repo, filler, lease_token=token, dispatched_at=now)
    correction = claim_rollout_model_job(repo, snapshot, worker_id=uuid4())
    assert correction.rewrite_profile_version == SOURCE_BOUND_CORRECTION_PROFILE

    class CorrectedDraft:
        _model = "fixture-sentence-correction"

        def complete_json(self, prompt):
            request = json.loads(prompt)
            if "passages" in request:
                assert request["passages"][0]["source"] == LIFT_GATE_SOURCE
                candidates = [LIFT_GATE_SOURCE] * 3
            else:
                assert request["statements"][0]["statement"] == LIFT_GATE_SOURCE
                wording = "During the lift gate's normal travel, the cover keeps debris away from the drive gear."
                candidates = [wording, LIFT_GATE_SOURCE, wording]
            return {"rewrites": [{"slot": 1, "candidates": candidates}]}

    class PublicationInterrupted(Exception):
        pass

    def interrupt_after_correction(phase):
        if phase == "after_model_result_commit":
            raise PublicationInterrupted

    with pytest.raises(PublicationInterrupted):
        run_article_job(repo, correction, registry={}, object_store=None, model_client=CorrectedDraft(),
                        hooks=interrupt_after_correction)
    with repo.connect() as conn:
        staged = conn.execute("""SELECT phase,checkpoint->>'candidate_revision_id' AS candidate
            FROM source_fetch_jobs WHERE source_fetch_job_id=%s""", (correction.job_id,)).fetchone()
        assert staged["phase"] == "publishing" and staged["candidate"]
        assert conn.execute("""SELECT count(*) AS total FROM canonical_article_rewrite_attempts
            WHERE source_fetch_job_id=%s AND dispatched_at IS NOT NULL""",
            (correction.job_id,)).fetchone()["total"] == 2
        conn.execute("""UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second'
            WHERE source_fetch_job_id=%s""", (correction.job_id,))
    parked_job(repo, snapshot)
    resumed = claim_rollout_model_job(repo, snapshot, worker_id=uuid4())
    assert resumed.job_id == correction.job_id and resumed.phase == "validating"

    class UnexpectedModelCall:
        def complete_json(self, prompt):
            raise AssertionError("saved canonical draft must publish without another model dispatch")

    run_article_job(repo, resumed, registry={}, object_store=None, model_client=UnexpectedModelCall())
    with repo.connect() as conn:
        published = conn.execute("""SELECT current_source_revision_id,current_canonical_revision_id::text AS revision
            FROM canonical_articles WHERE canonical_article_id=%s""", (prior["canonical_article_id"],)).fetchone()
    assert published["current_source_revision_id"] == prior["source_revision_id"]
    assert published["revision"] == staged["candidate"]
    assert claim_rollout_model_job(repo, snapshot, worker_id=uuid4()) is None
