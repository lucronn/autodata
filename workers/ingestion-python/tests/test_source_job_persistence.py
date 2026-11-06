from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import uuid
import pytest
from lifecycle_support import fresh_database, seed_vehicle, insert_descriptor
from test_source_article_capture import capture_fixture
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


def test_saved_automatic_candidate_reclaims_final_budget_without_reset(fresh_database, capture_fixture):
    from test_article_worker import prepare_automatic, AutomaticModel
    from autodata_ingestion import article_lifecycle_store as store
    from autodata_ingestion.article_lifecycle import run_article_job
    from autodata_ingestion.procedure_rewrite import rewrite_ordered_document
    from autodata_ingestion.source_job_persistence import claim_source_job, LeaseLost
    repo = fresh_database(); lease, source = prepare_automatic(repo, capture_fixture)
    store.save_normalized_input(repo, lease, source.as_article())
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET retry_count=max_attempts WHERE source_fetch_job_id=%s", (lease.job_id,))
    attempt = store.prepare_rewrite_attempt(repo, lease, source.source_document, context=source.vehicle, model="fixture-auto")
    store.mark_rewrite_dispatched(repo, lease, attempt)
    result = rewrite_ordered_document(source.source_document, client=AutomaticModel(), context=source.vehicle, profile_version=lease.rewrite_profile_version)
    store.store_rewrite_result(repo, lease, result)
    expire(repo, lease)
    resumed = claim_source_job(repo, worker_id=uuid.uuid4())
    assert resumed is not None and resumed.job_id == lease.job_id and resumed.token > lease.token
    with repo.connect() as conn:
        assert conn.execute("SELECT retry_count FROM source_fetch_jobs").fetchone()["retry_count"] == 3
    with pytest.raises(LeaseLost): store.load_candidate(repo, lease)
    class Never:
        def complete_json(self, prompt): pytest.fail("publication redrafted exhausted saved candidate")
    run_article_job(repo, resumed, registry={}, object_store=None, model_client=Never())
    assert store.load_article_state(repo, lease.canonical_article_id)["content_origin"] == "canonical"
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_rewrite_attempts").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 1


@pytest.mark.parametrize("mode", ["failed", "ambiguous"])
def test_failed_or_ambiguous_automatic_result_cannot_bypass_budget(fresh_database, capture_fixture, mode):
    from test_article_worker import prepare_automatic, AutomaticModel
    from autodata_ingestion import article_lifecycle_store as store
    from autodata_ingestion.procedure_rewrite import rewrite_ordered_document
    from autodata_ingestion.source_job_persistence import claim_source_job
    repo = fresh_database(); lease, source = prepare_automatic(repo, capture_fixture)
    store.save_normalized_input(repo, lease, source.as_article())
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET retry_count=max_attempts WHERE source_fetch_job_id=%s", (lease.job_id,))
    attempt = store.prepare_rewrite_attempt(repo, lease, source.source_document, context=source.vehicle, model="fixture-auto")
    store.mark_rewrite_dispatched(repo, lease, attempt)
    if mode == "failed":
        result = rewrite_ordered_document(source.source_document, client=AutomaticModel(unchanged=True), context=source.vehicle, profile_version=lease.rewrite_profile_version)
        store.store_rewrite_result(repo, lease, result)
    expire(repo, lease)
    assert claim_source_job(repo, worker_id=uuid.uuid4()) is None
    assert store.load_article_state(repo, lease.canonical_article_id)["content_origin"] == "source"


def test_exact_job_claim_does_not_claim_or_sweep_unselected_jobs(fresh_database):
    from autodata_ingestion.source_job_persistence import claim_source_job
    repo = fresh_database()
    first = ensure(repo, seed_article(repo))
    second = ensure(repo, seed_article(repo))
    old = claim_source_job(repo, worker_id=uuid.uuid4(), job_id=first.job_id)
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET retry_count=max_attempts,lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s", (first.job_id,))
    selected = claim_source_job(repo, worker_id=uuid.uuid4(), job_id=second.job_id)
    assert selected.job_id == second.job_id
    assert claim_source_job(repo, worker_id=uuid.uuid4(), job_id=uuid.uuid4()) is None
    with repo.connect() as conn:
        row = conn.execute("SELECT status,lease_token FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (first.job_id,)).fetchone()
        assert row == {"status":"processing", "lease_token":old.token}
    assert claim_source_job(repo, worker_id=uuid.uuid4(), job_id=first.job_id) is None
    with repo.connect() as conn:
        assert conn.execute("SELECT status FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (first.job_id,)).fetchone()["status"] == "dead_letter"


BANKONE_JOB = 'a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d'
BANKONE_ARTICLE = 'aad66f67-355c-5d92-ab21-b4894bca9069'
BANKONE_SOURCE = 'acd11534-199a-40f7-bf94-717b34895752'
BANKTWO_JOB = '64888ce4-429e-4e22-9892-48d1fb4b82eb'


def recovery_fixture(repo):
    """The frozen identities with synthetic content, in the isolated fixture DB."""
    from lifecycle_support import seed_snapshot
    from psycopg.types.json import Jsonb
    from autodata_ingestion.article_lifecycle_types import digest_json, transformation_key
    vehicle = seed_vehicle(repo)
    snapshot = seed_snapshot(repo)
    document = {'blocks': [{'kind': 'paragraph', 'text': 'Fixture prose.'}]}
    digest = digest_json(document)
    with repo.connect() as conn:
        for provider, article, job in [('bankone', BANKONE_ARTICLE, BANKONE_JOB), ('banktwo', str(uuid.uuid4()), BANKTWO_JOB)]:
            conn.execute("""INSERT INTO canonical_articles(canonical_article_id,provider_slug,vehicle_id,scope_key,source_vehicle_ref,source_article_ref,identity_key,descriptor,descriptor_source_snapshot_id,target_rewrite_profile_version)
                VALUES (%s,%s,%s,%s,'v',%s,%s,'{}',%s,'full-prose-auto-v1')""", (article, provider, vehicle, 'vehicle:'+str(vehicle), provider, ('a' if provider=='bankone' else 'b')*64, snapshot))
            if provider == 'bankone':
                conn.execute("""INSERT INTO canonical_article_source_revisions(source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,resource_manifest,source_document,source_images,source_body,source_steps,projection_status,evidence_manifest,captured_at)
                    VALUES (%s,%s,%s,%s,'[]',%s,'[]','Fixture prose.','[]','readable','[{}]',now())""", (BANKONE_SOURCE,article,'c'*64,snapshot,Jsonb(document)))
            conn.execute("""INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_article_ref,source_version,connector_name,idempotency_key,status,job_kind,canonical_article_id,normalization_version,rewrite_profile_version,retry_count,lease_token,phase,error_code,source_revision_id,transformation_key,checkpoint)
                VALUES (%s,%s,%s,'v',%s,'v1',%s,%s,%s,'article',%s,'ordered-article-v1','full-prose-auto-v1',1,1,'rewriting',%s,%s,%s,%s)""", (job,provider,vehicle,provider,provider,job,'dead_letter' if provider=='bankone' else 'completed',article,'REWRITE_RESPONSE_INVALID' if provider=='bankone' else None,BANKONE_SOURCE if provider=='bankone' else None,transformation_key(article,'c'*64,'ordered-article-v1','full-prose-auto-v1') if provider=='bankone' else None,Jsonb({'normalized_document':document,'normalized_hash':digest}) if provider=='bankone' else Jsonb({})))
            conn.execute("UPDATE canonical_articles SET current_job_id=%s,current_source_revision_id=%s WHERE canonical_article_id=%s", (job,BANKONE_SOURCE if provider=='bankone' else None,article))
            conn.execute("""INSERT INTO canonical_article_rewrite_attempts(rewrite_attempt_id,source_fetch_job_id,lease_token,attempt_number,provider,model,profile_version,prompt_hash,input_hash,status,dispatched_at,completed_at,error_code)
                VALUES (%s,%s,1,1,'inception','mercury-3','full-prose-auto-v1',%s,%s,%s,now(),now(),%s)""", (uuid.uuid4(),job,'d'*64,digest,'failed' if provider=='bankone' else 'succeeded','REWRITE_RESPONSE_INVALID' if provider=='bankone' else None))
    return dict(worker_id=uuid.uuid4(),job_id=BANKONE_JOB,canonical_article_id=BANKONE_ARTICLE,source_revision_id=BANKONE_SOURCE,rewrite_profile_version='full-prose-auto-v1',expected_generation=0,normalization_version='ordered-article-v1',expected_normalized_hash=digest,expected_lease_token=1,expected_retry_count=1,recovery_id='bankone-diagnostic-recovery-2026-11-06',actor='fixture',reason='bounded exact recovery',implementation_sha='e'*40)


def recovery_snapshot(repo):
    with repo.connect() as conn:
        return tuple(conn.execute('SELECT * FROM '+table+' ORDER BY 1').fetchall() for table in ('canonical_articles','source_fetch_jobs','canonical_article_rewrite_attempts','canonical_article_revisions','publication_events'))


def test_exact_bankone_recovery_preserves_history_and_is_one_use(fresh_database):
    from autodata_ingestion import source_job_persistence as jobs
    repo = fresh_database(); args = recovery_fixture(repo)
    before = recovery_snapshot(repo)
    lease = jobs.claim_exact_bankone_recovery(repo, **args)
    assert str(lease.job_id) == BANKONE_JOB and lease.token == 2
    assert lease.phase == 'rewriting'
    marker = lease.checkpoint['bankone_exact_recovery']
    assert marker['state'] == 'prepared' and marker['dispatches_consumed'] == 0
    assert marker['max_additional_dispatches'] == 1 and marker['lease_token'] == 2
    after = recovery_snapshot(repo)
    assert after[0] == before[0] and after[2:] == before[2:]
    assert [r for r in after[1] if str(r['source_fetch_job_id']) == BANKTWO_JOB] == [r for r in before[1] if str(r['source_fetch_job_id']) == BANKTWO_JOB]
    with repo.connect() as conn:
        row = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(BANKONE_JOB,)).fetchone()
    assert row['retry_count'] == 2 and row['max_attempts'] == 3
    with pytest.raises(jobs.BankoneRecoveryBlocked): jobs.claim_exact_bankone_recovery(repo, **args)
    expire(repo,lease)
    assert jobs.claim_source_job(repo,worker_id=uuid.uuid4(),job_id=BANKONE_JOB) is None
    assert jobs.ensure_article_job(repo,BANKONE_ARTICLE,normalization_version='ordered-article-v1',rewrite_profile_version='full-prose-auto-v1').job_id == lease.job_id


@pytest.mark.parametrize('mutation', [
    "UPDATE source_fetch_jobs SET lease_token=2 WHERE source_fetch_job_id='%s'" % BANKONE_JOB,
    "UPDATE source_fetch_jobs SET retry_count=3 WHERE source_fetch_job_id='%s'" % BANKONE_JOB,
    "UPDATE source_fetch_jobs SET error_code='OTHER_ERROR' WHERE source_fetch_job_id='%s'" % BANKONE_JOB,
    "UPDATE source_fetch_jobs SET status='needs_review' WHERE source_fetch_job_id='%s'" % BANKONE_JOB,
    "UPDATE canonical_articles SET request_generation=1 WHERE canonical_article_id='%s'" % BANKONE_ARTICLE,
    "UPDATE canonical_articles SET target_rewrite_profile_version='technical-prose-v1' WHERE canonical_article_id='%s'" % BANKONE_ARTICLE,
    "UPDATE canonical_articles SET target_normalization_version='changed' WHERE canonical_article_id='%s'" % BANKONE_ARTICLE,
    "UPDATE canonical_articles SET current_job_id=NULL,current_source_revision_id=NULL WHERE canonical_article_id='%s'" % BANKONE_ARTICLE,
    "UPDATE canonical_articles SET current_source_revision_id=NULL WHERE canonical_article_id='%s'" % BANKONE_ARTICLE,
    "UPDATE source_fetch_jobs SET checkpoint=jsonb_set(checkpoint,'{normalized_hash}','\"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff\"') WHERE source_fetch_job_id='%s'" % BANKONE_JOB,
    "UPDATE source_fetch_jobs SET checkpoint=jsonb_set(checkpoint,'{normalized_document}','{}') WHERE source_fetch_job_id='%s'" % BANKONE_JOB,
    "UPDATE canonical_article_rewrite_attempts SET status='prepared',dispatched_at=NULL WHERE source_fetch_job_id='%s'" % BANKONE_JOB,
    "UPDATE canonical_article_rewrite_attempts SET status='dispatched',completed_at=NULL WHERE source_fetch_job_id='%s'" % BANKONE_JOB,
    "UPDATE canonical_article_rewrite_attempts SET dispatched_at=NULL WHERE source_fetch_job_id='%s'" % BANKTWO_JOB,
    "DELETE FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id='%s'" % BANKTWO_JOB,
])
def test_exact_bankone_recovery_rejects_drift_without_mutation(fresh_database, mutation):
    from autodata_ingestion import source_job_persistence as jobs
    repo = fresh_database(); args = recovery_fixture(repo)
    with repo.connect() as conn: conn.execute(mutation)
    before = recovery_snapshot(repo)
    with pytest.raises(jobs.BankoneRecoveryBlocked): jobs.claim_exact_bankone_recovery(repo, **args)
    assert recovery_snapshot(repo) == before


def test_recovery_retryable_failure_is_terminal(fresh_database):
    from autodata_ingestion import source_job_persistence as jobs
    repo=fresh_database(); args=recovery_fixture(repo)
    lease=jobs.claim_exact_bankone_recovery(repo,**args)
    jobs.fail_source_job(repo,lease,code='MODEL_DELIVERY_AMBIGUOUS',retryable=True)
    with repo.connect() as conn:
        row=conn.execute('SELECT status,retryable,retry_count FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(BANKONE_JOB,)).fetchone()
    assert row == {'status':'dead_letter','retryable':False,'retry_count':2}
    assert jobs.claim_source_job(repo,worker_id=uuid.uuid4()) is None


@pytest.mark.parametrize('field,value', [
    ('job_id',str(uuid.uuid4())), ('canonical_article_id',str(uuid.uuid4())),
    ('source_revision_id',str(uuid.uuid4())), ('rewrite_profile_version','technical-prose-v1'),
    ('normalization_version','changed'), ('expected_generation',1),
    ('expected_lease_token',2), ('expected_retry_count',2),
    ('expected_normalized_hash','f'*64), ('recovery_id',''), ('actor',''),
    ('reason',''), ('implementation_sha','not-a-sha'),
])
def test_exact_recovery_rejects_wrong_request_fences(fresh_database,field,value):
    from autodata_ingestion import source_job_persistence as jobs
    repo=fresh_database(); args=recovery_fixture(repo); args[field]=value
    before=recovery_snapshot(repo)
    with pytest.raises(jobs.BankoneRecoveryBlocked): jobs.claim_exact_bankone_recovery(repo,**args)
    assert recovery_snapshot(repo)==before


def test_concurrent_recoveries_have_one_winner(fresh_database):
    from concurrent.futures import ThreadPoolExecutor
    from autodata_ingestion import source_job_persistence as jobs
    repo=fresh_database(); args=recovery_fixture(repo)
    def claim(_):
        try: return jobs.claim_exact_bankone_recovery(repo,**args)
        except jobs.BankoneRecoveryBlocked as error: return error.code
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(claim,range(2)))
    assert sum(not isinstance(result,str) for result in results)==1
    assert 'RECOVERY_ALREADY_CONSUMED' in results
    with repo.connect() as conn:
        assert conn.execute('SELECT retry_count,lease_token FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(BANKONE_JOB,)).fetchone()=={'retry_count':2,'lease_token':2}
        assert conn.execute('SELECT count(*) AS n FROM canonical_article_rewrite_attempts').fetchone()['n']==2


@pytest.mark.parametrize('bank,count',[(BANKONE_JOB,2),(BANKTWO_JOB,3)])
def test_recovery_rejects_consumed_bank_or_global_budget(fresh_database,bank,count):
    from autodata_ingestion import source_job_persistence as jobs
    repo=fresh_database(); args=recovery_fixture(repo)
    with repo.connect() as conn:
        conn.execute('UPDATE source_fetch_jobs SET retry_count=%s,lease_token=%s WHERE source_fetch_job_id=%s',(count,count,bank))
        for number in range(2,count+1):
            conn.execute("""INSERT INTO canonical_article_rewrite_attempts(rewrite_attempt_id,source_fetch_job_id,lease_token,attempt_number,provider,model,profile_version,prompt_hash,input_hash,status,dispatched_at,completed_at)
                VALUES (%s,%s,%s,%s,'inception','mercury-3','full-prose-auto-v1',%s,%s,'ambiguous',now(),now())""",(uuid.uuid4(),bank,number,number,'a'*64,args['expected_normalized_hash']))
    if bank==BANKONE_JOB: args.update(expected_retry_count=count,expected_lease_token=count)
    before=recovery_snapshot(repo)
    with pytest.raises(jobs.BankoneRecoveryBlocked): jobs.claim_exact_bankone_recovery(repo,**args)
    assert recovery_snapshot(repo)==before


def test_recovery_rejects_existing_candidate(fresh_database):
    from autodata_ingestion import source_job_persistence as jobs
    repo=fresh_database(); args=recovery_fixture(repo)
    with repo.connect() as conn:
        conn.execute("""INSERT INTO canonical_article_revisions(canonical_article_revision_id,canonical_article_id,source_revision_id,transformation_key,normalization_version,rewrite_profile_version,status,normalized_source_document,normalized_source_hash,canonical_document,canonical_body,canonical_steps,canonical_images,validation_report,validation_hash,rewrite_result_hash,model_metadata)
            SELECT %s,canonical_article_id,source_revision_id,transformation_key,normalization_version,rewrite_profile_version,'building',checkpoint->'normalized_document',checkpoint->>'normalized_hash','{}','fixture','[]','[]','{}',%s,%s,'{}' FROM source_fetch_jobs WHERE source_fetch_job_id=%s""",(uuid.uuid4(),'f'*64,'f'*64,BANKONE_JOB))
    before=recovery_snapshot(repo)
    with pytest.raises(jobs.BankoneRecoveryBlocked) as error: jobs.claim_exact_bankone_recovery(repo,**args)
    assert error.value.code=='RECOVERY_CANDIDATE_EXISTS'
    assert recovery_snapshot(repo)==before


@pytest.mark.parametrize('state',['prepared','dispatched'])
def test_generic_claim_cannot_reclaim_recovery_or_consume_more_budget(fresh_database,state):
    from autodata_ingestion import source_job_persistence as jobs
    repo=fresh_database(); args=recovery_fixture(repo)
    lease=jobs.claim_exact_bankone_recovery(repo,**args)
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second',checkpoint=jsonb_set(checkpoint,'{bankone_exact_recovery,state}',%s::jsonb) WHERE source_fetch_job_id=%s",('"'+state+'"',BANKONE_JOB))
    before=recovery_snapshot(repo)
    assert jobs.claim_source_job(repo,worker_id=uuid.uuid4()) is None
    assert jobs.claim_source_job(repo,worker_id=uuid.uuid4(),job_id=BANKONE_JOB) is None
    assert recovery_snapshot(repo)==before
