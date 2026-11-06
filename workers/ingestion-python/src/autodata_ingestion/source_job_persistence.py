"""Durable generic source jobs. PostgreSQL time/locks are lifecycle authority."""

import re
from uuid import uuid4
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .article_lifecycle_types import EnsureResult, JobLease


class LeaseLost(RuntimeError):
    pass


class ProfileRefreshRequired(ValueError):
    code = "PROFILE_REFRESH_REQUIRED"


ACTIVE = ("pending", "processing", "failed")


def _cursor(conn):
    return conn.cursor(row_factory=dict_row)


def _result(cur, article, job, created=False):
    delay = (
        cur.execute(
            "SELECT CASE WHEN %s::timestamptz IS NOT NULL THEN GREATEST(0,ceil(extract(epoch FROM %s::timestamptz-clock_timestamp()))::int) END AS delay",
            (job["next_attempt_at"], job["next_attempt_at"]),
        ).fetchone()["delay"]
        if job["status"] == "failed" and job["retryable"]
        else None
    )
    state = job["status"]
    published = None
    if article:
        view = cur.execute(
            "SELECT canonical_revision_id,processing_error_code FROM catalog_article_current WHERE canonical_article_id=%s",
            (article["canonical_article_id"],),
        ).fetchone()
        if view:
            published = view["canonical_revision_id"]
            if view["processing_error_code"] == "CANONICAL_REVIEW_REJECTED":
                state = "needs_review"
    return EnsureResult(
        job["source_fetch_job_id"],
        article["canonical_article_id"] if article else None,
        state,
        job["source_revision_id"],
        delay,
        published,
        created,
    )


def _ensure_locked(cur, article, *, force_new=False):
    if article["current_job_id"] and not force_new:
        job = cur.execute(
            "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
            (article["current_job_id"],),
        ).fetchone()
        # The authoritative pointer may be to an older terminal transformation.
        if job:
            return _result(cur, article, job)
    job_id = uuid4()
    job = cur.execute(
        """INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_article_ref,source_version,connector_name,idempotency_key,status,job_kind,canonical_article_id,request_generation,normalization_version,rewrite_profile_version)
    VALUES (%s,%s,%s,%s,%s,'lifecycle-v1',%s,%s,'pending','article',%s,%s,%s,%s) RETURNING *""",
        (
            job_id,
            article["provider_slug"],
            article["vehicle_id"],
            article["source_vehicle_ref"],
            article["source_article_ref"],
            article["provider_slug"],
            f'article:{article["canonical_article_id"]}:{article["request_generation"]}',
            article["canonical_article_id"],
            article["request_generation"],
            article["target_normalization_version"],
            article["target_rewrite_profile_version"],
        ),
    ).fetchone()
    cur.execute(
        "UPDATE canonical_articles SET current_job_id=%s,updated_at=clock_timestamp() WHERE canonical_article_id=%s",
        (job_id, article["canonical_article_id"]),
    )
    return _result(cur, article, job, True)


def ensure_article_job(
    repo, canonical_article_id, *, normalization_version, rewrite_profile_version
):
    with repo.connect() as conn, _cursor(conn) as cur:
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
            (canonical_article_id,),
        ).fetchone()
        if article is None:
            raise KeyError("canonical article not found")
        if (normalization_version, rewrite_profile_version) != (
            article["target_normalization_version"],
            article["target_rewrite_profile_version"],
        ):
            raise ProfileRefreshRequired()
        return _ensure_locked(cur, article)


def refresh_article_job(
    repo,
    canonical_article_id,
    *,
    actor,
    reason,
    normalization_version=None,
    rewrite_profile_version=None,
    expected_source_revision_id=None,
):
    if not actor.strip() or not reason.strip():
        raise ValueError("refresh actor and reason required")
    with repo.connect() as conn, _cursor(conn) as cur:
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
            (canonical_article_id,),
        ).fetchone()
        if article is None:
            raise KeyError("canonical article not found")
        if expected_source_revision_id is not None:
            if str(article["current_source_revision_id"]) != str(expected_source_revision_id):
                raise ValueError("AUTOMATIC_SOURCE_CHANGED")
            if article["current_canonical_revision_id"] is not None:
                raise ValueError("AUTOMATIC_ALREADY_PUBLISHED")
        if article["current_job_id"]:
            job = cur.execute(
                "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                (article["current_job_id"],),
            ).fetchone()
            if job["status"] in ACTIVE:
                return _result(cur, article, job)
        article = cur.execute(
            """UPDATE canonical_articles SET request_generation=request_generation+1,
        target_normalization_version=COALESCE(%s,target_normalization_version),target_rewrite_profile_version=COALESCE(%s,target_rewrite_profile_version)
        WHERE canonical_article_id=%s RETURNING *""",
            (normalization_version, rewrite_profile_version, canonical_article_id),
        ).fetchone()
        result = _ensure_locked(cur, article, force_new=True)
        cur.execute(
            "UPDATE source_fetch_jobs SET checkpoint=%s WHERE source_fetch_job_id=%s",
            (Jsonb({"refresh_actor": actor, "refresh_reason": reason}), result.job_id),
        )
        return result


def _mark_delivery_ambiguous(cur, job):
    # Only the locked row actually reclaimed/swept determines delivery ownership.
    # The transition and ambiguity accounting commit or roll back together.
    cur.execute("""UPDATE canonical_article_rewrite_attempts
        SET status='ambiguous',error_code='MODEL_DELIVERY_AMBIGUOUS',completed_at=clock_timestamp()
        WHERE source_fetch_job_id=%s AND lease_token=%s AND status='dispatched' AND response IS NULL""",
        (job["source_fetch_job_id"], job["lease_token"]))


def _claim_review_resume(cur, worker_id, job_id=None):
    """Saved full drafts have a publication lease, never another model attempt."""
    from .article_lifecycle_store import _require_full_approval
    jobs = cur.execute("""SELECT * FROM source_fetch_jobs WHERE job_kind='article' AND NOT (checkpoint ? 'bankone_exact_recovery')
        AND rewrite_profile_version='full-prose-review-v1' AND (%s::uuid IS NULL OR source_fetch_job_id=%s)
        AND checkpoint->'content_review'->>'state'='approved'
        AND ((status='pending' AND COALESCE(next_attempt_at,'-infinity'::timestamptz)<=clock_timestamp())
          OR (status='processing' AND lease_expires_at<clock_timestamp()))
        ORDER BY created_at,source_fetch_job_id FOR UPDATE SKIP LOCKED LIMIT 1""", (job_id,job_id)).fetchall()
    for job in jobs:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE", (job["canonical_article_id"],)).fetchone()
        candidate = cur.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s FOR UPDATE", (job["transformation_key"],)).fetchone()
        try:
            _require_full_approval(cur, job, article, candidate)
        except ValueError:
            cur.execute("""UPDATE source_fetch_jobs SET status='needs_review',error_code='CONTENT_REVIEW_REQUIRED',retryable=false,
                lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,next_attempt_at=NULL,checkpoint=jsonb_set(checkpoint,'{content_review,state}','"awaiting_review"'::jsonb) WHERE source_fetch_job_id=%s""", (job["source_fetch_job_id"],))
            continue
        row = cur.execute("""UPDATE source_fetch_jobs SET status='processing',phase='publishing',lease_token=lease_token+1,
            lease_owner=%s,lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),
            error_code=NULL,next_attempt_at=NULL,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s RETURNING *""",
            (worker_id,job["source_fetch_job_id"])).fetchone()
        return _lease_from_row(row,worker_id)
    return None


def _claim_automatic_resume(cur, worker_id, job_id=None):
    """Saved successful auto output consumes publication leases, not model attempts."""
    from .article_lifecycle_store import automatic_candidate_validation
    job = cur.execute("""SELECT j.* FROM source_fetch_jobs j
        JOIN canonical_article_revisions r ON r.transformation_key=j.transformation_key
        WHERE j.job_kind='article' AND NOT (j.checkpoint ? 'bankone_exact_recovery') AND j.rewrite_profile_version='full-prose-auto-v1' AND (%s::uuid IS NULL OR j.source_fetch_job_id=%s)
          AND (EXISTS (SELECT 1 FROM canonical_article_rewrite_attempts a WHERE a.canonical_article_revision_id=r.canonical_article_revision_id AND a.status='succeeded')
            OR r.model_metadata->>'transformation_method'='source-preserving-zero-slot-v1')
          AND r.status IN ('building','validated') AND j.checkpoint->>'rewrite_error_code' IS NULL
          AND j.checkpoint->>'candidate_revision_id'=r.canonical_article_revision_id::text
          AND ((j.status='pending' AND COALESCE(j.next_attempt_at,'-infinity'::timestamptz)<=clock_timestamp())
            OR (j.status='processing' AND j.lease_expires_at<clock_timestamp()))
        ORDER BY j.created_at,j.source_fetch_job_id FOR UPDATE OF j SKIP LOCKED LIMIT 1""", (job_id,job_id)).fetchone()
    if job is None:
        return None
    article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE", (job["canonical_article_id"],)).fetchone()
    candidate = cur.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s FOR UPDATE", (job["transformation_key"],)).fetchone()
    try:
        if (article is None or article["current_job_id"] != job["source_fetch_job_id"]
            or article["request_generation"] != job["request_generation"]
            or article["current_source_revision_id"] != job["source_revision_id"]
            or article["target_rewrite_profile_version"] != job["rewrite_profile_version"]
            or article["target_normalization_version"] != job["normalization_version"]):
            raise ValueError("automatic publication owner changed")
        automatic_candidate_validation(cur,job,candidate)
    except ValueError:
        cur.execute("""UPDATE source_fetch_jobs SET status='dead_letter',error_code='AUTOMATIC_CANDIDATE_INVALID',retryable=false,
            lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,next_attempt_at=NULL,updated_at=clock_timestamp()
            WHERE source_fetch_job_id=%s""", (job["source_fetch_job_id"],))
        return None
    row = cur.execute("""UPDATE source_fetch_jobs SET status='processing',phase='validating',lease_token=lease_token+1,
        lease_owner=%s,lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),
        error_code=NULL,next_attempt_at=NULL,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s RETURNING *""",
        (worker_id,job["source_fetch_job_id"])).fetchone()
    return _lease_from_row(row,worker_id)


def park_automatic_for_model(repo, lease):
    """Release only an undispatched auto job after source/normalization commit."""
    from .article_lifecycle_store import _lock_transform
    with repo.connect() as conn, _cursor(conn) as cur:
        job, _ = _lock_transform(cur, lease)
        if (job["rewrite_profile_version"] != "full-prose-auto-v1"
            or not job["source_revision_id"] or not job["checkpoint"].get("normalized_hash")
            or cur.execute("SELECT 1 FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s", (lease.job_id,)).fetchone()):
            raise ValueError("MODEL_CONFIGURATION_PARK_INVALID")
        cur.execute("""UPDATE source_fetch_jobs SET status='failed',error_code='MODEL_NOT_CONFIGURED',retryable=true,
            checkpoint=checkpoint||'{"awaiting_model_configuration":true}'::jsonb,next_attempt_at=NULL,
            lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=clock_timestamp()
            WHERE source_fetch_job_id=%s""", (lease.job_id,))


def _claim_model_configuration_resume(cur, worker_id, job_id):
    """Configuration waits dispatched nothing and consume no additional attempt."""
    job = cur.execute("""SELECT j.* FROM source_fetch_jobs j JOIN canonical_articles a
        ON a.canonical_article_id=j.canonical_article_id
        WHERE j.job_kind='article' AND NOT (j.checkpoint ? 'bankone_exact_recovery') AND j.rewrite_profile_version='full-prose-auto-v1'
          AND (%s::uuid IS NULL OR j.source_fetch_job_id=%s)
          AND j.status IN ('failed','dead_letter') AND j.error_code='MODEL_NOT_CONFIGURED'
          AND j.source_revision_id IS NOT NULL AND j.checkpoint ? 'normalized_document' AND j.checkpoint ? 'normalized_hash'
          AND a.current_job_id=j.source_fetch_job_id AND a.request_generation=j.request_generation
          AND a.current_source_revision_id=j.source_revision_id
          AND a.target_rewrite_profile_version=j.rewrite_profile_version AND a.target_normalization_version=j.normalization_version
          AND NOT EXISTS (SELECT 1 FROM canonical_article_rewrite_attempts r WHERE r.source_fetch_job_id=j.source_fetch_job_id)
        ORDER BY j.created_at,j.source_fetch_job_id FOR UPDATE OF j SKIP LOCKED LIMIT 1""", (job_id,job_id)).fetchone()
    if job is None:
        return None
    article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE", (job["canonical_article_id"],)).fetchone()
    if (article["current_job_id"] != job["source_fetch_job_id"] or article["request_generation"] != job["request_generation"]
        or article["current_source_revision_id"] != job["source_revision_id"]
        or article["target_rewrite_profile_version"] != job["rewrite_profile_version"]
        or article["target_normalization_version"] != job["normalization_version"]):
        return None
    row = cur.execute("""UPDATE source_fetch_jobs SET status='processing',phase='rewriting',lease_token=lease_token+1,
        lease_owner=%s,lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),
        checkpoint=checkpoint-'awaiting_model_configuration',error_code=NULL,retryable=false,next_attempt_at=NULL,updated_at=clock_timestamp()
        WHERE source_fetch_job_id=%s RETURNING *""", (worker_id,job["source_fetch_job_id"])).fetchone()
    return _lease_from_row(row,worker_id)


class BankoneRecoveryBlocked(ValueError):
    """A stable, content-free reason the exceptional recovery was rejected."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


BANKONE_RECOVERY_JOB = "a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d"
BANKONE_RECOVERY_ARTICLE = "aad66f67-355c-5d92-ab21-b4894bca9069"
BANKONE_RECOVERY_SOURCE = "acd11534-199a-40f7-bf94-717b34895752"
BANKTWO_FROZEN_JOB = "64888ce4-429e-4e22-9892-48d1fb4b82eb"


def claim_exact_bankone_recovery(
    repo, *, worker_id, job_id, canonical_article_id, source_revision_id,
    rewrite_profile_version, expected_generation, normalization_version,
    expected_normalized_hash, expected_lease_token, expected_retry_count,
    recovery_id, actor, reason, implementation_sha,
):
    """Consume the sole frozen recovery authorization and return its live lease.

    No polling/ensure path calls this function. Repeating even an identical
    request blocks: a prepared recovery resumes only using the returned lease.
    The dispatch boundary must atomically consume its checkpoint allowance.
    """
    from .article_lifecycle_types import digest_json, transformation_key

    def require(condition, code):
        if not condition:
            raise BankoneRecoveryBlocked(code)

    require((str(job_id), str(canonical_article_id), str(source_revision_id),
             rewrite_profile_version, normalization_version) ==
            (BANKONE_RECOVERY_JOB, BANKONE_RECOVERY_ARTICLE, BANKONE_RECOVERY_SOURCE,
             "full-prose-auto-v1", "ordered-article-v1"), "RECOVERY_SCOPE_MISMATCH")
    require(all(isinstance(value, str) and value.strip() and len(value) <= limit
                and not any(ord(c) < 32 or ord(c) == 127 for c in value)
                for value, limit in ((recovery_id, 128), (actor, 128), (reason, 512))),
            "RECOVERY_AUDIT_INVALID")
    require(isinstance(implementation_sha, str) and
            re.fullmatch(r"[a-f0-9]{40}", implementation_sha) is not None,
            "RECOVERY_IMPLEMENTATION_INVALID")
    require(isinstance(expected_normalized_hash, str) and
            re.fullmatch(r"[a-f0-9]{64}", expected_normalized_hash) is not None and
            all(type(value) is int and value >= 0 for value in
                (expected_generation, expected_lease_token, expected_retry_count)),
            "RECOVERY_FENCE_INVALID")
    with repo.connect() as conn, _cursor(conn) as cur:
        # Lock both exact budgets before examining attempts. This also serializes
        # competing recovery requests and ordinary claims for either frozen job.
        banks = cur.execute("""SELECT * FROM source_fetch_jobs
            WHERE source_fetch_job_id IN (%s,%s)
            ORDER BY source_fetch_job_id FOR UPDATE""", (job_id, BANKTWO_FROZEN_JOB)).fetchall()
        require(len(banks) == 2, "RECOVERY_HISTORY_UNKNOWN")
        jobs = {str(row["source_fetch_job_id"]): row for row in banks}
        job = jobs[BANKONE_RECOVERY_JOB]
        banktwo = jobs[BANKTWO_FROZEN_JOB]
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                              (canonical_article_id,)).fetchone()
        require("bankone_exact_recovery" not in job["checkpoint"], "RECOVERY_ALREADY_CONSUMED")
        require(job["status"] == "dead_letter" and job["error_code"] == "REWRITE_RESPONSE_INVALID"
                and job["job_kind"] == "article" and job["provider_slug"] == "bankone"
                and job["phase"] == "rewriting" and not job["retryable"]
                and job["lease_owner"] is None and job["lease_expires_at"] is None
                and job["heartbeat_at"] is None, "RECOVERY_JOB_STATE_CHANGED")
        require(article is not None and str(job["canonical_article_id"]) == str(canonical_article_id)
                and article["current_job_id"] == job["source_fetch_job_id"]
                and article["provider_slug"] == "bankone" and article["membership_status"] == "active"
                and article["takedown_status"] == "active"
                and article["current_source_revision_id"] == job["source_revision_id"]
                and str(job["source_revision_id"]) == str(source_revision_id)
                and article["request_generation"] == job["request_generation"] == expected_generation
                and article["target_normalization_version"] == job["normalization_version"] == normalization_version
                and article["target_rewrite_profile_version"] == job["rewrite_profile_version"] == rewrite_profile_version,
                "RECOVERY_OWNER_CHANGED")
        require(job["lease_token"] == expected_lease_token and job["retry_count"] == expected_retry_count,
                "RECOVERY_LEASE_CHANGED")
        require(job["retry_count"] < job["max_attempts"], "RECOVERY_RETRY_BUDGET_EXHAUSTED")
        source = cur.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s FOR SHARE",
                             (source_revision_id,)).fetchone()
        document = job["checkpoint"].get("normalized_document")
        require(source is not None and source["canonical_article_id"] == article["canonical_article_id"]
                and isinstance(document, dict) and isinstance(document.get("blocks"), list)
                and bool(document["blocks"])
                and digest_json(document) == job["checkpoint"].get("normalized_hash") == expected_normalized_hash
                and job["transformation_key"] == transformation_key(canonical_article_id,
                    source["source_fingerprint"], normalization_version, rewrite_profile_version,
                    projection_version=source["projection_version"]), "RECOVERY_INPUT_CHANGED")
        require(article["current_canonical_revision_id"] is None
                and not job["checkpoint"].get("candidate_revision_id")
                and cur.execute("SELECT 1 FROM canonical_article_revisions WHERE canonical_article_id=%s LIMIT 1",
                                (canonical_article_id,)).fetchone() is None
                and cur.execute("SELECT 1 FROM publication_events WHERE canonical_article_id=%s LIMIT 1",
                                (canonical_article_id,)).fetchone() is None, "RECOVERY_CANDIDATE_EXISTS")
        attempts = cur.execute("""SELECT * FROM canonical_article_rewrite_attempts
            WHERE source_fetch_job_id IN (%s,%s) ORDER BY source_fetch_job_id,attempt_number FOR UPDATE""",
            (job_id, BANKTWO_FROZEN_JOB)).fetchall()
        prior = [row for row in attempts if str(row["source_fetch_job_id"]) == BANKONE_RECOVERY_JOB]
        other = [row for row in attempts if str(row["source_fetch_job_id"]) == BANKTWO_FROZEN_JOB]
        require(banktwo["provider_slug"] == "banktwo" and banktwo["job_kind"] == "article"
                and banktwo["status"] == "completed" and banktwo["lease_owner"] is None
                and len(prior) == 1 and bool(other) and len(prior) < 2 and len(attempts) < 4,
                "RECOVERY_DISPATCH_BUDGET_BLOCKED")
        require(all(row["status"] in ("failed", "succeeded", "ambiguous")
                    and row["dispatched_at"] is not None and row["completed_at"] is not None
                    and row["provider"] == "inception" and row["model"] == "mercury-3"
                    and row["profile_version"] == "full-prose-auto-v1"
                    and row["lease_token"] <= jobs[str(row["source_fetch_job_id"])]["lease_token"]
                    and row["attempt_number"] <= jobs[str(row["source_fetch_job_id"])]["retry_count"]
                    for row in attempts)
                and prior[0]["status"] == "failed" and prior[0]["error_code"] == "REWRITE_RESPONSE_INVALID"
                and prior[0]["input_hash"] == expected_normalized_hash
                and prior[0]["canonical_article_revision_id"] is None,
                "RECOVERY_HISTORY_UNKNOWN")
        marker = dict(version=1, recovery_id=recovery_id, actor=actor, reason=reason,
                      implementation_sha=implementation_sha, state="prepared",
                      max_additional_dispatches=1, dispatches_consumed=0,
                      lease_token=job["lease_token"]+1, prior_lease_token=job["lease_token"],
                      prior_retry_count=job["retry_count"], original_error_code=job["error_code"])
        row = cur.execute("""UPDATE source_fetch_jobs SET status='processing',phase='rewriting',
            retry_count=retry_count+1,lease_token=lease_token+1,lease_owner=%s,
            lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),
            next_attempt_at=NULL,retryable=false,error_code=NULL,
            checkpoint=checkpoint||%s,updated_at=clock_timestamp()
            WHERE source_fetch_job_id=%s RETURNING *""",
            (worker_id, Jsonb({"bankone_exact_recovery": marker}), job_id)).fetchone()
        return _lease_from_row(row, worker_id)


def _finalize_expired_bankone_recovery(cur, job_id):
    """End only the frozen one-shot lease; never reacquire or return it."""
    job = cur.execute("""SELECT * FROM source_fetch_jobs
        WHERE source_fetch_job_id=%s AND canonical_article_id=%s AND source_revision_id=%s
          AND (%s::uuid IS NULL OR source_fetch_job_id=%s)
          AND checkpoint ? 'bankone_exact_recovery' AND status='processing'
          AND lease_expires_at<clock_timestamp()
        FOR UPDATE SKIP LOCKED""", (BANKONE_RECOVERY_JOB, BANKONE_RECOVERY_ARTICLE,
            BANKONE_RECOVERY_SOURCE, job_id, job_id)).fetchone()
    if job is None:
        return
    # Unknown delivery remains consumed. Change only this lease's unresolved
    # dispatched attempt; the original terminal attempt is immutable evidence.
    _mark_delivery_ambiguous(cur, job)
    ambiguous = cur.execute("""SELECT 1 FROM canonical_article_rewrite_attempts
        WHERE source_fetch_job_id=%s AND lease_token=%s AND status='ambiguous'
          AND response IS NULL AND dispatched_at IS NOT NULL
        LIMIT 1""", (job["source_fetch_job_id"], job["lease_token"])).fetchone()
    # A consumed allowance proves dispatch, not unknown delivery: a saved
    # response remains known evidence even when the publication lease expires.
    code = "MODEL_DELIVERY_AMBIGUOUS" if ambiguous else "RECOVERY_LEASE_EXPIRED"
    cur.execute("""UPDATE source_fetch_jobs SET status='dead_letter',error_code=%s,retryable=false,
        lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,next_attempt_at=NULL,
        updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""",
        (code, job["source_fetch_job_id"]))


def claim_source_job(repo, *, worker_id, model_ready=True, job_id=None):
    with repo.connect() as conn, _cursor(conn) as cur:
        _finalize_expired_bankone_recovery(cur, job_id)
        resumed = _claim_automatic_resume(cur, worker_id, job_id)
        if resumed is not None:
            return resumed
        resumed = _claim_review_resume(cur, worker_id, job_id)
        if resumed is not None:
            return resumed
        if model_ready:
            resumed = _claim_model_configuration_resume(cur, worker_id, job_id)
            if resumed is not None:
                return resumed
        cur.execute(
            """WITH exhausted AS (SELECT source_fetch_job_id FROM source_fetch_jobs
        WHERE job_kind IN ('article','catalog_index') AND NOT (checkpoint ? 'bankone_exact_recovery') AND (%s::uuid IS NULL OR source_fetch_job_id=%s) AND NOT (rewrite_profile_version='full-prose-auto-v1' AND COALESCE(error_code,'')='MODEL_NOT_CONFIGURED') AND NOT (checkpoint @> '{"source_only_reprojection":true}'::jsonb) AND NOT (rewrite_profile_version='full-prose-review-v1' AND checkpoint ? 'content_review') AND status='processing' AND retry_count>=max_attempts AND lease_expires_at<clock_timestamp() FOR UPDATE SKIP LOCKED)
        UPDATE source_fetch_jobs j SET status='dead_letter',error_code='LEASE_ATTEMPTS_EXHAUSTED',retryable=false,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=clock_timestamp()
        FROM exhausted e WHERE j.source_fetch_job_id=e.source_fetch_job_id
        RETURNING j.source_fetch_job_id,j.lease_token""", (job_id,job_id)
        )
        for exhausted in cur.fetchall():
            _mark_delivery_ambiguous(cur, exhausted)
        job = cur.execute(
            """SELECT * FROM source_fetch_jobs WHERE job_kind IN ('article','catalog_index') AND NOT (checkpoint ? 'bankone_exact_recovery') AND (%s::uuid IS NULL OR source_fetch_job_id=%s) AND NOT (rewrite_profile_version='full-prose-auto-v1' AND COALESCE(error_code,'')='MODEL_NOT_CONFIGURED') AND NOT (checkpoint @> '{"source_only_reprojection":true}'::jsonb) AND NOT (rewrite_profile_version='full-prose-review-v1' AND checkpoint ? 'content_review') AND retry_count<max_attempts AND
        ((status IN ('pending','failed') AND COALESCE(next_attempt_at,'-infinity'::timestamptz)<=clock_timestamp()) OR (status='processing' AND lease_expires_at<clock_timestamp()))
        ORDER BY created_at,source_fetch_job_id FOR UPDATE SKIP LOCKED LIMIT 1""", (job_id,job_id)
        ).fetchone()
        if job is None:
            return None
        if job["status"] == "processing":
            _mark_delivery_ambiguous(cur, job)
        row = cur.execute(
            """UPDATE source_fetch_jobs SET status='processing',retry_count=retry_count+1,lease_token=lease_token+1,lease_owner=%s,
        lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),updated_at=clock_timestamp(),
        phase=CASE WHEN phase='queued' THEN 'fetching_source' ELSE phase END WHERE source_fetch_job_id=%s RETURNING *""",
            (worker_id, job["source_fetch_job_id"]),
        ).fetchone()
        return _lease_from_row(row, worker_id)



def _lease_from_row(row, worker_id):
    return JobLease(
        row["source_fetch_job_id"],
        worker_id,
        row["lease_token"],
        row["request_generation"],
        row["job_kind"],
        row["phase"],
        row["canonical_article_id"],
        row["catalog_provider_scope_id"],
        row["source_revision_id"],
        row["normalization_version"],
        row["rewrite_profile_version"],
        row["checkpoint"],
        row["lease_expires_at"],
    )


def claim_source_only_job(cur, job_id, canonical_article_id, *, worker_id):
    """Claim only the specified offline job in its caller's transaction."""
    row = cur.execute("""UPDATE source_fetch_jobs SET status='processing',
        retry_count=retry_count+1,lease_token=lease_token+1,lease_owner=%s,
        lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),
        phase='fetching_source',updated_at=clock_timestamp()
        WHERE source_fetch_job_id=%s AND canonical_article_id=%s AND job_kind='article'
          AND status='pending' AND retry_count<max_attempts
          AND checkpoint @> '{"source_only_reprojection":true}'::jsonb
        RETURNING *""", (worker_id, job_id, canonical_article_id)).fetchone()
    if row is None:
        raise LeaseLost("source-only exact claim rejected")
    return _lease_from_row(row, worker_id)


def lock_live_lease(cur, lease):
    row = cur.execute(
        """SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s AND status='processing' AND lease_owner=%s AND lease_token=%s AND lease_expires_at>clock_timestamp() FOR UPDATE""",
        (lease.job_id, lease.worker_id, lease.token),
    ).fetchone()
    if row is None:
        raise LeaseLost("source job lease lost")
    return row


def heartbeat_source_job(repo, lease):
    with repo.connect() as conn, _cursor(conn) as cur:
        lock_live_lease(cur, lease)
        cur.execute(
            "UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp() WHERE source_fetch_job_id=%s",
            (lease.job_id,),
        )
        return True


def advance_source_job(repo, lease, *, phase, checkpoint):
    with repo.connect() as conn, _cursor(conn) as cur:
        lock_live_lease(cur, lease)
        cur.execute(
            """UPDATE source_fetch_jobs SET phase=%s,checkpoint=checkpoint||%s,status=CASE WHEN %s='completed' THEN 'completed' ELSE status END,
        lease_owner=CASE WHEN %s='completed' THEN NULL ELSE lease_owner END,lease_expires_at=CASE WHEN %s='completed' THEN NULL ELSE lease_expires_at END,
        heartbeat_at=CASE WHEN %s='completed' THEN NULL ELSE heartbeat_at END,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s""",
            (phase, Jsonb(checkpoint), phase, phase, phase, phase, lease.job_id),
        )


def fail_source_job(repo, lease, *, code, retryable, retry_after_seconds=None):
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code):
        raise ValueError("redacted stable error code required")
    with repo.connect() as conn, _cursor(conn) as cur:
        row = lock_live_lease(cur, lease)
        retry = retryable and "bankone_exact_recovery" not in row["checkpoint"] and row["retry_count"] < row["max_attempts"]
        delay = (
            max(
                5 if row["retry_count"] == 1 else 30,
                min(900, max(1, int(retry_after_seconds or 1))),
            )
            if retry
            else None
        )
        status = "failed" if retry else ("dead_letter" if retryable or row["rewrite_profile_version"] == "full-prose-auto-v1" else "needs_review")
        cur.execute(
            """UPDATE source_fetch_jobs SET status=%s,error_code=%s,retryable=%s,next_attempt_at=CASE WHEN %s::int IS NULL THEN NULL ELSE statement_timestamp()+make_interval(secs=>%s) END,
        lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=statement_timestamp() WHERE source_fetch_job_id=%s""",
            (status, code, retry, delay, delay, lease.job_id),
        )
