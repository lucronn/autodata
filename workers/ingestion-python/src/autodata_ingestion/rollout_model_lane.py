"""Find one parked source for the serialized rollout model worker."""

from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .article_lifecycle_types import AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION, digest_json, transformation_key
from .new_article_worker import WINDOW, _timestamp
from .source_job_persistence import (
    _SOURCE_BOUND_CURRENT_OWNER_SQL, _lease_from_row, source_bound_rewrite_source_allowed,
)


MAX_MODEL_DISPATCHES_PER_WINDOW = 10


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
    }
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        # A release can rebind the source SHA without resetting the rollout's
        # actual-delivery window. Count dispatches recorded before the rebind too.
        used = cur.execute("""SELECT count(*) AS used
            FROM canonical_article_rewrite_attempts t
            JOIN source_fetch_jobs j ON j.source_fetch_job_id=t.source_fetch_job_id
            WHERE t.dispatched_at>clock_timestamp()-%(window)s
              AND j.checkpoint->'new_article_rollout'->>'rollout_id'=%(rollout_id)s
              AND j.checkpoint->'new_article_rollout'->>'cutoff'=%(cutoff)s
            """, args).fetchone()["used"]
        if used >= MAX_MODEL_DISPATCHES_PER_WINDOW:
            return None
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
    return None
