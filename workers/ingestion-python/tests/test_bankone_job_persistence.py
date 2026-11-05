"""Legacy jobs are immutable history; only proven canonical work is scheduled."""
from types import SimpleNamespace
import pytest
from lifecycle_support import fresh_database,seed_vehicle,seed_snapshot,insert_descriptor
from autodata_ingestion.article_lifecycle_types import ArticleKey
from autodata_ingestion import bankone_job_persistence as jobs


def test_unbound_batch_requires_review_without_any_database_access(monkeypatch):
    def never(*args,**kwargs):pytest.fail("unbound legacy batch opened database")
    monkeypatch.setattr(jobs,"_connection",never)
    result=jobs.persist_bankone_article_fetch_jobs([SimpleNamespace(vehicle_key="v")],[{"vehicle_key":"v","status":"completed"}],selector_persistence={"observations":[{"vehicle_key":"v","vehicle_id":"unproven"}]},source_version="v1")
    assert result["status"]=="needs_review" and result["error_code"]=="ARTICLE_BINDING_REVIEW_REQUIRED"


def test_legacy_claim_and_record_do_not_mutate_imported_audit_rows(fresh_database,monkeypatch):
    from lifecycle_support import seed_legacy_jobs_and_read_invariants,read_imported_job_invariants,apply_migration
    repo=fresh_database(through=35);seed_legacy_jobs_and_read_invariants(repo)
    for migration in (36,37,38):apply_migration(repo,migration)
    before=read_imported_job_invariants(repo)
    monkeypatch.setattr(jobs,"_connection",repo.connect)
    for row in before:
        result=jobs.claim_autoapi_article_fetch_job(row["idempotency_key"])
        assert result["status"]=="needs_review" and result["error_code"]=="ARTICLE_BINDING_REVIEW_REQUIRED"
        jobs.record_autoapi_article_fetch_success(row["idempotency_key"],checkpoint={"fake":"value"})
        jobs.record_autoapi_article_fetch_failure(row["idempotency_key"],"fixture")
    assert read_imported_job_invariants(repo)==before


def test_bound_batch_delegates_to_generic_ensure_and_replays(fresh_database,monkeypatch):
    repo=fresh_database();vehicle=seed_vehicle(repo)
    article=insert_descriptor(repo,ArticleKey("bankone",vehicle,None,"v","a"))
    monkeypatch.setattr("autodata_ingestion.worker.ArticleRepository",lambda:repo)
    kwargs=dict(selector_persistence={"observations":[{"vehicle_key":"v","vehicle_id":str(vehicle)}]},source_version="v1")
    batch=SimpleNamespace(vehicle_key="v")
    first=jobs.persist_bankone_article_fetch_jobs([batch],[{"vehicle_key":"v","canonical_article_ids":[str(article)]}],**kwargs)
    second=jobs.persist_bankone_article_fetch_jobs([batch],[{"vehicle_key":"v","canonical_article_ids":[str(article)]}],**kwargs)
    assert first["jobs"][0]["job_id"]==second["jobs"][0]["job_id"]
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM autoapi_article_fetch_jobs").fetchone()["n"]==0
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs WHERE job_kind='article'").fetchone()["n"]==1
