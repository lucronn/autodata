from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import uuid
import pytest
from lifecycle_support import fresh_database, seed_vehicle, insert_descriptor
from autodata_ingestion.article_lifecycle_types import (
    ArticleKey,
    NORMALIZATION_VERSION,
    REWRITE_PROFILE_VERSION,
)


def seed_article(repo):
    return insert_descriptor(
        repo, ArticleKey("bankone", seed_vehicle(repo), None, "v", "a")
    )


def ensure(repo, article):
    from autodata_ingestion.source_job_persistence import ensure_article_job

    return ensure_article_job(
        repo,
        article,
        normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=REWRITE_PROFILE_VERSION,
    )


def ensure_child(args):
    repo, article = args
    return asdict(ensure(repo, article))


def expire(repo, lease):
    with repo.connect() as conn:
        conn.execute(
            "UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s",
            (lease.job_id,),
        )


def test_twenty_ensures_create_one_active_job(fresh_database):
    repo = fresh_database()
    article = seed_article(repo)
    with ProcessPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(ensure_child, [(repo, article)] * 20))
    assert len({r["job_id"] for r in results}) == 1
    assert sum(r["created"] for r in results) == 1


def test_expired_lease_cannot_mutate(fresh_database):
    from autodata_ingestion.source_job_persistence import (
        claim_source_job,
        advance_source_job,
        heartbeat_source_job,
        fail_source_job,
        LeaseLost,
    )

    repo = fresh_database()
    ensure(repo, seed_article(repo))
    first = claim_source_job(repo, worker_id=uuid.uuid4())
    expire(repo, first)
    second = claim_source_job(repo, worker_id=uuid.uuid4())
    assert second.token == first.token + 1
    for mutation in (
        lambda: advance_source_job(repo, first, phase="normalizing", checkpoint={}),
        lambda: heartbeat_source_job(repo, first),
        lambda: fail_source_job(
            repo, first, code="UPSTREAM_UNAVAILABLE", retryable=True
        ),
    ):
        with pytest.raises(LeaseLost):
            mutation()
    assert heartbeat_source_job(repo, second)


@pytest.mark.parametrize(
    "retry_after,expected", [(None, 5), (1, 5), (60, 60), (2000, 900)]
)
def test_retry_budget_and_backoff(fresh_database, retry_after, expected):
    from autodata_ingestion.source_job_persistence import (
        claim_source_job,
        fail_source_job,
    )

    repo = fresh_database()
    article = seed_article(repo)
    job = ensure(repo, article)
    for attempt in (1, 2, 3):
        lease = claim_source_job(repo, worker_id=uuid.uuid4())
        fail_source_job(
            repo,
            lease,
            code="UPSTREAM_UNAVAILABLE",
            retryable=True,
            retry_after_seconds=retry_after,
        )
        with repo.connect() as conn:
            row = conn.execute(
                "SELECT *,ceil(extract(epoch FROM next_attempt_at-updated_at)) AS delay FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                (job.job_id,),
            ).fetchone()
            assert row["retry_count"] == attempt
            assert row["status"] == ("dead_letter" if attempt == 3 else "failed")
            if attempt < 3:
                assert row["delay"] == max(expected, 30 if attempt == 2 else 5)
                conn.execute(
                    "UPDATE source_fetch_jobs SET next_attempt_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s",
                    (job.job_id,),
                )
    assert ensure(repo, article).job_id == job.job_id
    assert claim_source_job(repo, worker_id=uuid.uuid4()) is None


def test_expired_third_attempt_is_swept(fresh_database):
    from autodata_ingestion.source_job_persistence import claim_source_job

    repo = fresh_database()
    job = ensure(repo, seed_article(repo))
    for i in range(3):
        lease = claim_source_job(repo, worker_id=uuid.uuid4())
        expire(repo, lease)
    assert claim_source_job(repo, worker_id=uuid.uuid4()) is None
    with repo.connect() as conn:
        row = conn.execute(
            "SELECT status,error_code,lease_owner FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
            (job.job_id,),
        ).fetchone()
        assert row == {
            "status": "dead_letter",
            "error_code": "LEASE_ATTEMPTS_EXHAUSTED",
            "lease_owner": None,
        }


@pytest.mark.parametrize(
    "code",
    ["UNAUTHORIZED", "AMBIGUOUS", "INVALID_UPSTREAM_RESPONSE", "SOURCE_NOT_FOUND"],
)
def test_nonretryable_failure_is_sticky(fresh_database, code):
    from autodata_ingestion.source_job_persistence import (
        claim_source_job,
        fail_source_job,
        refresh_article_job,
    )

    repo = fresh_database()
    article = seed_article(repo)
    job = ensure(repo, article)
    lease = claim_source_job(repo, worker_id=uuid.uuid4())
    fail_source_job(repo, lease, code=code, retryable=False)
    assert ensure(repo, article).state == "needs_review"
    assert ensure(repo, article).job_id == job.job_id
    refreshed = refresh_article_job(repo, article, actor="fixture", reason="inspect")
    assert refreshed.job_id != job.job_id


def paused_advance(repo, lease, ready, release, results):
    from autodata_ingestion.source_job_persistence import advance_source_job, LeaseLost

    ready.set()
    release.wait(10)
    try:
        advance_source_job(repo, lease, phase="normalizing", checkpoint={"stale": True})
    except LeaseLost:
        results.put("fenced")
    else:
        results.put("unsafe")


def test_process_paused_before_write_is_fenced_after_reclaim(fresh_database):
    import multiprocessing
    from autodata_ingestion.source_job_persistence import claim_source_job

    repo = fresh_database()
    ensure(repo, seed_article(repo))
    first = claim_source_job(repo, worker_id=uuid.uuid4())
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    release = ctx.Event()
    results = ctx.Queue()
    child = ctx.Process(
        target=paused_advance, args=(repo, first, ready, release, results)
    )
    child.start()
    try:
        assert ready.wait(10)
        expire(repo, first)
        second = claim_source_job(repo, worker_id=uuid.uuid4())
        release.set()
        assert results.get(timeout=10) == "fenced"
        assert second.token > first.token
    finally:
        release.set()
        child.join(10)
        if child.is_alive():
            child.terminate()
            child.join()
    assert child.exitcode == 0


def test_completed_warm_ensure_has_no_writes(fresh_database):
    from autodata_ingestion.source_job_persistence import (
        claim_source_job,
        advance_source_job,
    )

    repo = fresh_database()
    article = seed_article(repo)
    job = ensure(repo, article)
    lease = claim_source_job(repo, worker_id=uuid.uuid4())
    advance_source_job(repo, lease, phase="completed", checkpoint={})
    with repo.connect() as conn:
        before = (
            conn.execute("SELECT * FROM canonical_articles").fetchall(),
            conn.execute("SELECT * FROM source_fetch_jobs").fetchall(),
        )
    assert ensure(repo, article).created is False
    with repo.connect() as conn:
        after = (
            conn.execute("SELECT * FROM canonical_articles").fetchall(),
            conn.execute("SELECT * FROM source_fetch_jobs").fetchall(),
        )
    assert before == after


def test_legacy_jobs_are_never_claimed(fresh_database):
    from lifecycle_support import seed_legacy_jobs_and_read_invariants, apply_migration
    from autodata_ingestion.source_job_persistence import claim_source_job

    repo = fresh_database(through=35)
    seed_legacy_jobs_and_read_invariants(repo)
    for number in (36, 37, 38):
        apply_migration(repo, number)
    assert claim_source_job(repo, worker_id=uuid.uuid4()) is None


@pytest.mark.parametrize("final", [False, True])
def test_expired_dispatched_attempt_is_ambiguous_in_reclaim_transaction(fresh_database, final):
    from lifecycle_support import seed_vehicle, insert_descriptor
    from autodata_ingestion.source_job_persistence import ensure_article_job, claim_source_job
    from autodata_ingestion.article_lifecycle_types import ArticleKey
    from uuid import uuid4
    repo=fresh_database()
    article=insert_descriptor(repo,ArticleKey("bankone",seed_vehicle(repo),None,"v","a"))
    ensure_article_job(repo,article,normalization_version="ordered-article-v1",rewrite_profile_version="technical-prose-v1")
    lease=claim_source_job(repo,worker_id=uuid4())
    with repo.connect() as conn:
        conn.execute("INSERT INTO canonical_article_rewrite_attempts(rewrite_attempt_id,source_fetch_job_id,lease_token,attempt_number,provider,model,profile_version,prompt_hash,input_hash,status,dispatched_at) VALUES (%s,%s,%s,1,'fixture','fixture','technical-prose-v1',%s,%s,'dispatched',now())",(uuid4(),lease.job_id,lease.token,"a"*64,"b"*64))
        conn.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second',retry_count=%s WHERE source_fetch_job_id=%s",(3 if final else 1,lease.job_id))
    claimed=claim_source_job(repo,worker_id=uuid4())
    assert (claimed is None)==final
    with repo.connect() as conn:
        attempt=conn.execute("SELECT status,error_code FROM canonical_article_rewrite_attempts").fetchone()
        assert attempt=={"status":"ambiguous","error_code":"MODEL_DELIVERY_AMBIGUOUS"}
        job=conn.execute("SELECT status,retry_count FROM source_fetch_jobs WHERE source_fetch_job_id=%s",(lease.job_id,)).fetchone()
        assert job=={"status":"dead_letter" if final else "processing","retry_count":3 if final else 2}


@pytest.mark.parametrize("final", [False, True])
@pytest.mark.parametrize("renewed", [False, True])
def test_expiry_at_actual_recovery_boundary(fresh_database, monkeypatch, final, renewed):
    """Change expiry after any preliminary scan, at the statement owning recovery."""
    from contextlib import contextmanager
    from autodata_ingestion import source_job_persistence as jobs
    repo = fresh_database()
    ensure(repo, seed_article(repo))
    lease = jobs.claim_source_job(repo, worker_id=uuid.uuid4())
    with repo.connect() as conn:
        conn.execute("INSERT INTO canonical_article_rewrite_attempts(rewrite_attempt_id,source_fetch_job_id,lease_token,attempt_number,provider,model,profile_version,prompt_hash,input_hash,status,dispatched_at) VALUES (%s,%s,%s,1,'fixture','fixture','technical-prose-v1',%s,%s,'dispatched',now())", (uuid.uuid4(), lease.job_id, lease.token, "a"*64, "b"*64))
        conn.execute("UPDATE source_fetch_jobs SET retry_count=%s WHERE source_fetch_job_id=%s", (3 if final else 1, lease.job_id))
    original = jobs._cursor
    boundary = "WITH exhausted" if final else "SELECT * FROM source_fetch_jobs WHERE job_kind"
    fired = []

    class BoundaryCursor:
        def __init__(self, cur):
            self.cur = cur

        def __getattr__(self, name):
            return getattr(self.cur, name)

        def execute(self, sql, params=None):
            if boundary in sql and not fired:
                fired.append(True)
                with repo.connect() as other:
                    other.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()+make_interval(secs=>%s) WHERE source_fetch_job_id=%s", (90 if renewed else -1, lease.job_id))
            return self.cur.execute(sql, params)

    @contextmanager
    def cursor(conn):
        with original(conn) as cur:
            yield BoundaryCursor(cur)

    monkeypatch.setattr(jobs, "_cursor", cursor)
    claimed = jobs.claim_source_job(repo, worker_id=uuid.uuid4())
    assert fired
    assert (claimed is None) == (final or renewed)
    with repo.connect() as conn:
        attempt = conn.execute("SELECT status FROM canonical_article_rewrite_attempts").fetchone()
        job = conn.execute("SELECT status,retry_count,lease_token FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (lease.job_id,)).fetchone()
    assert attempt["status"] == ("dispatched" if renewed else "ambiguous")
    assert job["status"] == ("dead_letter" if final and not renewed else "processing")
    assert job["retry_count"] == (3 if final else 1 if renewed else 2)
    assert job["lease_token"] == lease.token + (not final and not renewed)


def test_review_marker_never_uses_normal_model_claim_or_exhaustion(fresh_database):
    """An unbound resume must never resurrect a model delivery or consume budget."""
    from autodata_ingestion.source_job_persistence import claim_source_job
    from psycopg.types.json import Jsonb
    repo = fresh_database()
    job = ensure(repo, seed_article(repo))
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET rewrite_profile_version='full-prose-review-v1',checkpoint=%s WHERE source_fetch_job_id=%s", (Jsonb({"content_review":{"version":1,"state":"approved","candidate_revision_id":str(uuid.uuid4()),"candidate_hash":"a"*64}}), job.job_id))
    assert claim_source_job(repo, worker_id=uuid.uuid4()) is None
    with repo.connect() as conn:
        row = conn.execute("SELECT retry_count,status FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (job.job_id,)).fetchone()
    assert row["retry_count"] == 0
