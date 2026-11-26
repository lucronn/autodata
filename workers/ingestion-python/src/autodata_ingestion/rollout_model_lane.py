"""Claim one stored-source rewrite or correction for the serialized model worker."""

from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION, SOURCE_BOUND_CORRECTION_PROFILE,
    digest_json, transformation_key,
)
from .new_article_worker import WINDOW, _PAID_SOURCE_SCOPE, _timestamp
from .procedure_rewrite_sentence_correction import MAX_SENTENCE_CORRECTION_CALLS
from .source_job_persistence import (
    _SOURCE_BOUND_CURRENT_OWNER_SQL, _claim_automatic_resume, _finalize_exhausted_source_jobs,
    _lease_from_row, claim_source_job, schedule_source_bound_correction, source_bound_rewrite_source_allowed,
)


MAX_MODEL_DISPATCHES_PER_WINDOW = 10
_CORRECTION_ACTOR = "workshop-automatic-sentence-correction"
_CORRECTION_ERRORS = ["REWRITE_UNCHANGED", "REWRITE_PROSE_TOO_SIMILAR", "REWRITE_TECHNICAL_MUTATION"]


def _claim_automatic_correction(repo, args, *, worker_id, model_budget_available):
    # Select only first drafts spent by this rollout. Scheduling and claiming
    # use the existing exact-source transaction and lease checks.
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(f"""SELECT j.source_fetch_job_id AS current_id, a.canonical_article_id,
                       failed.source_fetch_job_id AS prior_id, failed.source_revision_id
            FROM source_fetch_jobs failed
            JOIN canonical_articles a ON a.canonical_article_id=failed.canonical_article_id
            JOIN source_fetch_jobs j ON {_SOURCE_BOUND_CURRENT_OWNER_SQL}
            WHERE failed.job_kind='article' AND failed.rewrite_profile_version=%(profile)s
              AND failed.normalization_version=%(normalization)s AND failed.request_generation=0
              AND failed.created_at>%(cutoff_at)s AND failed.provider_slug=ANY(%(providers)s)
              AND failed.status='dead_letter' AND failed.phase='validating' AND NOT failed.retryable
              AND failed.error_code=ANY(%(correction_errors)s)
              AND failed.source_revision_id=j.source_revision_id
              AND (failed.source_fetch_job_id=ANY(%(reserved)s::uuid[])
                   OR failed.checkpoint ? 'paid_source_reserved_at')
              AND ((failed.checkpoint->'new_article_rollout') - 'source_sha'::text)=%(marker)s
              AND failed.checkpoint->'new_article_rollout'->>'source_sha' ~ '^[a-f0-9]{{40}}$'
              AND a.membership_status='active' AND a.takedown_status='active'
              AND a.current_canonical_revision_id IS NULL AND {_PAID_SOURCE_SCOPE}
              AND (%(model_budget_available)s OR (j.rewrite_profile_version=%(correction_profile)s AND (
                   (j.phase IN ('validating','publishing') AND j.checkpoint->>'candidate_revision_id' IS NOT NULL)
                   OR (j.status='processing' AND j.retry_count>=j.max_attempts
                       AND j.lease_expires_at<clock_timestamp()
                       AND EXISTS (SELECT 1 FROM canonical_article_rewrite_attempts attempt
                           WHERE attempt.source_fetch_job_id=j.source_fetch_job_id
                             AND attempt.lease_token=j.lease_token AND attempt.dispatched_at IS NOT NULL)))))
              AND (j.source_fetch_job_id=failed.source_fetch_job_id OR (
                   j.rewrite_profile_version=%(correction_profile)s
                   AND j.checkpoint->'source_bound_rewrite'->>'actor'=%(correction_actor)s
                   AND j.checkpoint->'source_bound_rewrite'->>'prior_job_id'=failed.source_fetch_job_id::text
                   AND (j.status='pending'
                        OR (j.status='processing' AND j.lease_expires_at<clock_timestamp())
                        OR (j.status='failed' AND j.error_code='MODEL_NOT_CONFIGURED'))))
            ORDER BY failed.created_at,failed.source_fetch_job_id
            """, {**args, "model_budget_available": model_budget_available}).fetchall()
    for row in rows:
        job_id = row["current_id"]
        if not model_budget_available:
            # Settle existing work without admitting another model call.
            with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
                lease = _claim_automatic_resume(cur, worker_id, job_id)
                if lease is None:
                    _finalize_exhausted_source_jobs(cur, job_id)
            if lease is not None:
                return lease
            continue
        if job_id == row["prior_id"]:
            try:
                scheduled = schedule_source_bound_correction(
                    repo, row["canonical_article_id"], expected_job_id=job_id,
                    expected_source_revision_id=row["source_revision_id"],
                    actor=_CORRECTION_ACTOR, reason="Correct a rejected Workshop first draft.",
                    model_call_budget=MAX_SENTENCE_CORRECTION_CALLS, by_sentence=True, first_draft=True,
                )
            except ValueError:
                # The source or current job may have changed since selection,
                # or the archived reply may not have the required exact shape.
                continue
            job_id = scheduled.job_id
        lease = claim_source_job(repo, worker_id=worker_id, job_id=job_id)
        if lease is not None:
            return lease
    return None


def claim_rollout_model_job(repo, snapshot, *, worker_id):
    """Claim a retained source while the coordinator holds its only model lane."""
    if snapshot["schema"] != 2 or not snapshot["enabled"]:
        return None
    marker = {"rollout_id": snapshot["rollout_id"], "cutoff": snapshot["cutoff"], "max_model_attempts": 1}
    args = {
        **marker, "cutoff_at": _timestamp(snapshot["cutoff"]), "window": WINDOW,
        "providers": snapshot["providers"], "marker": Jsonb(marker),
        "reserved": [UUID(item["job_id"]) for item in snapshot["reservations"]],
        "profile": AUTOMATIC_REWRITE_PROFILE, "normalization": NORMALIZATION_VERSION,
        "correction_actor": _CORRECTION_ACTOR, "correction_profile": SOURCE_BOUND_CORRECTION_PROFILE,
        "correction_errors": _CORRECTION_ERRORS,
    }
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        # A release can rebind the source SHA without resetting the rollout's
        # actual-delivery window. Count dispatches recorded before the rebind too.
        used = cur.execute("""SELECT count(*) AS used
            FROM canonical_article_rewrite_attempts t
            JOIN source_fetch_jobs j ON j.source_fetch_job_id=t.source_fetch_job_id
            LEFT JOIN source_fetch_jobs prior ON prior.canonical_article_id=j.canonical_article_id
                AND j.rewrite_profile_version=%(correction_profile)s
                AND j.checkpoint->'source_bound_rewrite'->>'actor'=%(correction_actor)s
                AND prior.source_fetch_job_id::text=j.checkpoint->'source_bound_rewrite'->>'prior_job_id'
            WHERE t.dispatched_at>clock_timestamp()-%(window)s
              AND COALESCE(prior.checkpoint,j.checkpoint)->'new_article_rollout'->>'rollout_id'=%(rollout_id)s
              AND COALESCE(prior.checkpoint,j.checkpoint)->'new_article_rollout'->>'cutoff'=%(cutoff)s
            """, args).fetchone()["used"]
        if used >= MAX_MODEL_DISPATCHES_PER_WINDOW:
            return _claim_automatic_correction(repo, args, worker_id=worker_id, model_budget_available=False)
        # Source pins can change during a release. Keep the rollout identity
        # and spent job UUID bound to the parked source across a release.
        candidates = cur.execute(f"""SELECT a.*,j.source_fetch_job_id,
                   j.source_revision_id,j.transformation_key,j.checkpoint,
                   s.source_fingerprint,s.projection_version,o.source_observation_id
            FROM source_fetch_jobs j
            JOIN canonical_articles a ON a.canonical_article_id=j.canonical_article_id
            JOIN canonical_article_source_revisions s ON s.source_revision_id=j.source_revision_id
                 AND s.canonical_article_id=j.canonical_article_id
            JOIN canonical_article_source_observations o ON o.source_fetch_job_id=j.source_fetch_job_id
                 AND o.canonical_article_id=j.canonical_article_id AND o.source_revision_id=j.source_revision_id
                 AND o.request_generation=j.request_generation AND o.captured_at>=j.created_at
            WHERE {_SOURCE_BOUND_CURRENT_OWNER_SQL}
              AND (j.source_fetch_job_id=ANY(%(reserved)s::uuid[])
                   OR j.checkpoint ? 'paid_source_reserved_at')
              AND j.job_kind='article' AND j.status='failed' AND j.phase='rewriting'
              AND j.error_code='MODEL_NOT_CONFIGURED' AND j.retryable
              AND j.lease_owner IS NULL AND j.lease_expires_at IS NULL AND j.heartbeat_at IS NULL
              AND j.next_attempt_at IS NULL AND j.max_attempts=1 AND j.retry_count=1 AND j.lease_token=1
              AND j.created_at>%(cutoff_at)s AND j.request_generation=0
              AND j.rewrite_profile_version=%(profile)s AND j.normalization_version=%(normalization)s
              AND j.provider_slug=ANY(%(providers)s) AND j.provider_slug=a.provider_slug
              AND j.canonical_vehicle_id=a.vehicle_id AND j.source_vehicle_ref=a.source_vehicle_ref
              AND j.source_article_ref=a.source_article_ref
              AND a.membership_status='active' AND a.takedown_status='active'
              AND a.current_canonical_revision_id IS NULL
              AND ((j.checkpoint->'new_article_rollout') - 'source_sha'::text)=%(marker)s
              AND j.checkpoint->'new_article_rollout'->>'source_sha' ~ '^[a-f0-9]{{40}}$'
              AND j.checkpoint->'awaiting_model_configuration'='true'::jsonb
              AND jsonb_typeof(j.checkpoint->'normalized_document')='object'
              AND j.checkpoint->>'normalized_hash' ~ '^[a-f0-9]{{64}}$'
              AND NOT (j.checkpoint ?| ARRAY['candidate_revision_id','rewrite_error_code','source_bound_rewrite',
                                              'bankone_exact_recovery','content_review','source_only_reprojection'])
              AND NOT EXISTS (SELECT 1 FROM source_fetch_jobs old
                  WHERE old.canonical_article_id=j.canonical_article_id
                    AND old.source_fetch_job_id<>j.source_fetch_job_id)
              AND NOT EXISTS (SELECT 1 FROM canonical_article_rewrite_attempts t
                  WHERE t.source_fetch_job_id=j.source_fetch_job_id)
              AND NOT EXISTS (SELECT 1 FROM canonical_article_revisions r
                  WHERE r.canonical_article_id=j.canonical_article_id)
            ORDER BY j.created_at,j.source_fetch_job_id
            FOR UPDATE OF j,a SKIP LOCKED
            """, args).fetchall()
        for row in candidates:
            if row["transformation_key"] != transformation_key(
                row["canonical_article_id"], row["source_fingerprint"], NORMALIZATION_VERSION,
                AUTOMATIC_REWRITE_PROFILE, projection_version=row["projection_version"],
            ):
                continue
            checkpoint = row["checkpoint"]
            if digest_json(checkpoint["normalized_document"]) != checkpoint["normalized_hash"]:
                continue
            observation = (row["source_observation_id"], row["source_fetch_job_id"], row["request_generation"])
            if not source_bound_rewrite_source_allowed(
                cur, row, row["source_revision_id"], predecessor_observation=observation,
                require_current_observation_scope=True, allow_unscoped=True,
            ):
                continue
            lease = cur.execute("""UPDATE source_fetch_jobs SET status='processing',
                lease_token=lease_token+1,lease_owner=%s,lease_expires_at=clock_timestamp()+interval '90 seconds',
                heartbeat_at=clock_timestamp(),error_code=NULL,retryable=false,updated_at=clock_timestamp(),
                checkpoint=(checkpoint-'awaiting_model_configuration')||%s
                WHERE source_fetch_job_id=%s RETURNING *""",
                (worker_id, Jsonb({"rollout_model_observation_id": str(row["source_observation_id"])}),
                 row["source_fetch_job_id"])).fetchone()
            return _lease_from_row(lease, worker_id)
    return _claim_automatic_correction(
        repo, args, worker_id=worker_id,
        model_budget_available=used + MAX_SENTENCE_CORRECTION_CALLS <= MAX_MODEL_DISPATCHES_PER_WINDOW,
    )
