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


def claim_source_job(repo, *, worker_id):
    with repo.connect() as conn, _cursor(conn) as cur:
        # Expiry recovery owns the row lock, independently of the dead worker's
        # live-lease guard. Account for uncertain external delivery even on the
        # final permitted claim before terminating or handing work to a new owner.
        expired = cur.execute("""SELECT source_fetch_job_id,lease_token FROM source_fetch_jobs
            WHERE job_kind IN ('article','catalog_index') AND status='processing'
              AND lease_expires_at<clock_timestamp() FOR UPDATE SKIP LOCKED""").fetchall()
        for old in expired:
            cur.execute("""UPDATE canonical_article_rewrite_attempts
                SET status='ambiguous',error_code='MODEL_DELIVERY_AMBIGUOUS',completed_at=clock_timestamp()
                WHERE source_fetch_job_id=%s AND lease_token=%s AND status='dispatched' AND response IS NULL""",
                (old["source_fetch_job_id"], old["lease_token"]))
        cur.execute(
            """WITH exhausted AS (SELECT source_fetch_job_id FROM source_fetch_jobs
        WHERE job_kind IN ('article','catalog_index') AND status='processing' AND retry_count>=max_attempts AND lease_expires_at<clock_timestamp() FOR UPDATE SKIP LOCKED)
        UPDATE source_fetch_jobs j SET status='dead_letter',error_code='LEASE_ATTEMPTS_EXHAUSTED',retryable=false,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=clock_timestamp()
        FROM exhausted e WHERE j.source_fetch_job_id=e.source_fetch_job_id"""
        )
        job = cur.execute(
            """SELECT * FROM source_fetch_jobs WHERE job_kind IN ('article','catalog_index') AND retry_count<max_attempts AND
        ((status IN ('pending','failed') AND COALESCE(next_attempt_at,'-infinity'::timestamptz)<=clock_timestamp()) OR (status='processing' AND lease_expires_at<clock_timestamp()))
        ORDER BY created_at,source_fetch_job_id FOR UPDATE SKIP LOCKED LIMIT 1"""
        ).fetchone()
        if job is None:
            return None
        row = cur.execute(
            """UPDATE source_fetch_jobs SET status='processing',retry_count=retry_count+1,lease_token=lease_token+1,lease_owner=%s,
        lease_expires_at=clock_timestamp()+interval '90 seconds',heartbeat_at=clock_timestamp(),updated_at=clock_timestamp(),
        phase=CASE WHEN phase='queued' THEN 'fetching_source' ELSE phase END WHERE source_fetch_job_id=%s RETURNING *""",
            (worker_id, job["source_fetch_job_id"]),
        ).fetchone()
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
        retry = retryable and row["retry_count"] < row["max_attempts"]
        delay = (
            max(
                5 if row["retry_count"] == 1 else 30,
                min(900, max(1, int(retry_after_seconds or 1))),
            )
            if retry
            else None
        )
        status = "failed" if retry else ("dead_letter" if retryable else "needs_review")
        cur.execute(
            """UPDATE source_fetch_jobs SET status=%s,error_code=%s,retryable=%s,next_attempt_at=CASE WHEN %s::int IS NULL THEN NULL ELSE statement_timestamp()+make_interval(secs=>%s) END,
        lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=statement_timestamp() WHERE source_fetch_job_id=%s""",
            (status, code, retry, delay, delay, lease.job_id),
        )
