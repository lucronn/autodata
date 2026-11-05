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


def seed_v1_publication(repo):
    """Seed historical rows without depending on the current capture/store binary."""
    from autodata_ingestion.article_lifecycle_types import ArticleKey
    article = insert_descriptor(repo, ArticleKey('bankone', seed_vehicle(repo), None, 'v', 'a'))
    source, job, revision = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    body = seed_snapshot(repo, b'historical raw body')
    with repo.connect() as conn:
        conn.execute("""INSERT INTO canonical_article_source_revisions
            (source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,
             resource_manifest,source_document,source_images,source_body,source_steps,
             projection_status,evidence_manifest,captured_at)
            VALUES (%s,%s,%s,%s,'[]','{"blocks":[{"text":"historical"}]}','[]',
                    'historical','[]','readable','[{}]','2026-01-01T00:00:00Z')""", (source, article, 'a'*64, body))
        conn.execute("""INSERT INTO source_fetch_jobs
            (source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,
             source_version,connector_name,idempotency_key,status,job_kind,canonical_article_id,
             source_revision_id,normalization_version,rewrite_profile_version,transformation_key)
            SELECT %s,provider_slug,vehicle_id,source_vehicle_ref,'fixture-v1','fixture',%s,
                   'completed','article',canonical_article_id,%s,'ordered-article-v1',
                   'technical-prose-v1',%s FROM canonical_articles WHERE canonical_article_id=%s""",
            (job, str(job), source, 'b'*64, article))
        conn.execute("""INSERT INTO canonical_article_source_observations
            (source_observation_id,canonical_article_id,source_revision_id,source_fetch_job_id,
             request_generation,body_provider_revision,resource_provenance,captured_context,
             resolution_source_snapshot_id,descriptor_source_snapshot_id,captured_at)
            VALUES (%s,%s,%s,%s,0,'fixture-v1','[]','{}',%s,%s,'2026-01-01T00:00:00Z')""",
            (uuid.uuid4(), article, source, job, body, body))
        conn.execute("""INSERT INTO canonical_article_revisions
            (canonical_article_revision_id,canonical_article_id,source_revision_id,
             transformation_key,normalization_version,rewrite_profile_version,status,
             normalized_source_document,normalized_source_hash,canonical_document,canonical_body,
             canonical_steps,canonical_images,validation_report,validation_hash,rewrite_result_hash,
             model_metadata,published_at)
            VALUES (%s,%s,%s,%s,'ordered-article-v1','technical-prose-v1','published',
                    '{}',%s,'{"blocks":[{"text":"published"}]}','published','[]','[]',
                    '{"passed":true,"changed_slots":["body"],"evidence_ids":["fixture"]}',
                    %s,%s,'{"model":"fixture","profile_version":"technical-prose-v1"}',now())""",
            (revision, article, source, 'b'*64, 'c'*64, 'd'*64, 'e'*64))
        conn.execute("""INSERT INTO publication_events
            (event_type,event_version,correlation_id,idempotency_key,payload,
             canonical_article_id,canonical_article_revision_id)
            VALUES ('catalog.article.published',1,%s,%s,'{}',%s,%s)""",
            (uuid.uuid4(), str(revision), article, revision))
        conn.execute("""UPDATE canonical_articles SET current_job_id=%s,
                        current_source_revision_id=%s,current_canonical_revision_id=%s
                        WHERE canonical_article_id=%s""", (job, source, revision, article))
    return article, source


def lifecycle_history(repo):
    with repo.connect() as conn:
        return {table: conn.execute('SELECT to_jsonb(t) AS record FROM ' + table +
                                   ' t ORDER BY to_jsonb(t)::text').fetchall()
                for table in ('canonical_articles', 'source_snapshots', 'source_fetch_jobs',
                              'canonical_article_source_revisions',
                              'canonical_article_source_observations',
                              'canonical_article_revisions', 'publication_events')}


def append_projection(repo, source, version):
    new_id = uuid.uuid4()
    with repo.connect() as conn:
        conn.execute("""INSERT INTO canonical_article_source_revisions
            SELECT (jsonb_populate_record(NULL::canonical_article_source_revisions,
                    to_jsonb(s) || jsonb_build_object('source_revision_id',%s::text,
                                                      'projection_version',%s::text))).*
            FROM canonical_article_source_revisions s WHERE source_revision_id=%s""",
            (str(new_id), version, source))
    return new_id


def test_populated_projection_upgrade_preserves_history_and_version_constraints(fresh_database):
    repo = fresh_database(through=40)
    article, v1 = seed_v1_publication(repo)
    before = lifecycle_history(repo)
    assert before['canonical_article_source_revisions'][0]['record']['projection_version'] == 'source-projection-v1'
    apply_migration(repo, 41)
    assert lifecycle_history(repo) == before
    v2 = append_projection(repo, v1, 'source-projection-v2')
    for version in ('source-projection-v1', 'source-projection-v2'):
        with pytest.raises(psycopg.errors.UniqueViolation):
            append_projection(repo, v1, version)
    with pytest.raises(psycopg.errors.CheckViolation):
        append_projection(repo, v1, 'source-projection-v3')
    # Old binaries must fail closed after removal of the two-column conflict key.
    with pytest.raises(psycopg.errors.InvalidColumnReference), repo.connect() as conn:
        conn.execute("INSERT INTO canonical_article_source_revisions SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s ON CONFLICT(canonical_article_id,source_fingerprint) DO NOTHING", (v1,))
    for table in ('canonical_article_source_revisions', 'canonical_article_source_observations',
                  'canonical_article_revisions'):
        for operation in ('UPDATE ' + table + ' SET canonical_article_id=canonical_article_id',
                          'DELETE FROM ' + table):
            with pytest.raises(psycopg.Error), repo.connect() as conn:
                conn.execute(operation)
    with repo.connect() as conn:
        conn.execute('UPDATE canonical_articles SET current_source_revision_id=%s,current_canonical_revision_id=NULL WHERE canonical_article_id=%s', (v2, article))
    for target in (v1, None):
        with pytest.raises(psycopg.errors.CheckViolation), repo.connect() as conn:
            conn.execute('UPDATE canonical_articles SET current_source_revision_id=%s WHERE canonical_article_id=%s', (target, article))
    # Unrelated article metadata and repeated v2 pointer writes remain valid.
    with repo.connect() as conn:
        conn.execute("UPDATE canonical_articles SET title='updated',current_source_revision_id=%s WHERE canonical_article_id=%s", (v2, article))
        assert conn.execute('SELECT current_source_revision_id FROM canonical_articles WHERE canonical_article_id=%s', (article,)).fetchone()['current_source_revision_id'] == v2
