import dataclasses
import uuid
import pytest
import psycopg
from lifecycle_support import (
    fresh_database,
    seed_vehicle,
    seed_snapshot,
    insert_descriptor,
    apply_migration,
    seed_legacy_jobs_and_read_invariants,
    read_imported_job_invariants,
)


def test_provider_identity_is_unique_without_cross_bank_merging(fresh_database):
    from autodata_ingestion.article_lifecycle_types import ArticleKey, article_id

    repo = fresh_database()
    vehicle = seed_vehicle(repo)
    first = ArticleKey("bankone", vehicle, None, "same:vehicle", "same/article")
    second = dataclasses.replace(first, provider="banktwo")
    assert article_id(first) == article_id(first)
    assert article_id(first) != article_id(second)
    assert insert_descriptor(repo, first) == insert_descriptor(repo, first)
    assert insert_descriptor(repo, first) != insert_descriptor(repo, second)


def test_upgrade_preserves_imported_legacy_jobs(fresh_database):
    repo = fresh_database(through=35)
    before = seed_legacy_jobs_and_read_invariants(repo)
    for number in (36, 37, 38, 36):
        apply_migration(repo, number)
    assert read_imported_job_invariants(repo) == before


def test_identity_scope_and_hash_constraints(fresh_database):
    from autodata_ingestion.article_lifecycle_types import ArticleKey

    repo = fresh_database()
    article = insert_descriptor(
        repo, ArticleKey("bankone", seed_vehicle(repo), None, "v", "a")
    )
    for assignment in (
        "identity_key='bad'",
        "scope_key='vehicle:wrong'",
        "vehicle_configuration_id='00000000-0000-0000-0000-000000000001'",
    ):
        with pytest.raises(psycopg.IntegrityError), repo.connect() as conn:
            conn.execute(
                "UPDATE canonical_articles SET "
                + assignment
                + " WHERE canonical_article_id=%s",
                (article,),
            )


def test_read_contract_columns_exist(fresh_database):
    repo = fresh_database()
    with repo.connect() as conn:
        columns = {
            r["column_name"]
            for r in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='catalog_article_current'"
            )
        }
    assert {
        "canonical_article_id",
        "vehicle_configuration_id",
        "document",
        "processing_state",
        "source_content_sha256",
        "review_status",
        "source_captured_at",
    } <= columns


def test_existing_catalog_statuses_survive_upgrade(fresh_database):
    repo = fresh_database(through=36)
    vehicle = seed_vehicle(repo)
    snapshot = seed_snapshot(repo)
    with repo.connect() as conn:
        for status in ("list_only", "content_complete"):
            conn.execute(
                "INSERT INTO catalog_articles(vehicle_id,article_id,source_snapshot_id,evidence_locator,evidence_confidence,content_status) VALUES (%s,%s,%s,'fixture',1,%s)",
                (vehicle, status, snapshot, status),
            )
    apply_migration(repo, 37)
    apply_migration(repo, 38)
    with repo.connect() as conn:
        assert {
            r["content_status"]
            for r in conn.execute("SELECT content_status FROM catalog_articles")
        } == {"list_only", "content_complete"}


def test_configuration_ownership_is_not_widened(fresh_database):
    from autodata_ingestion.article_lifecycle_types import ArticleKey
    from lifecycle_support import seed_configuration

    repo = fresh_database()
    vehicle = seed_vehicle(repo)
    other = seed_vehicle(repo)
    configuration = seed_configuration(repo, other)
    with pytest.raises(psycopg.IntegrityError):
        insert_descriptor(repo, ArticleKey("bankone", vehicle, configuration, "v", "a"))


def test_article_identity_cannot_change_after_creation(fresh_database):
    from autodata_ingestion.article_lifecycle_types import ArticleKey

    repo = fresh_database()
    article = insert_descriptor(
        repo, ArticleKey("bankone", seed_vehicle(repo), None, "v", "a")
    )
    with pytest.raises(psycopg.Error), repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_articles SET source_article_ref='different' WHERE canonical_article_id=%s",
            (article,),
        )
