"""Real PostgreSQL restart acceptance for the shared migration driver."""
from pathlib import Path
import subprocess
import os
import tempfile
import shutil
import concurrent.futures
import time
import pytest
from lifecycle_support import (ROOT, fresh_database, apply_migration, seed_vehicle,
                               seed_snapshot, seed_configuration,
                               seed_legacy_jobs_and_read_invariants,
                               read_imported_job_invariants)

MIGRATION_NAMES = [path.name for path in sorted((ROOT / "db/migrations").glob("*.sql"))]


def run_driver(repo, directory=None, check=True, **extra):
    args = ['sh', str(ROOT / 'scripts/dev/migrate_sql.sh')]
    if directory is not None:
        args += ['--migrations-dir', str(directory)]
    result = subprocess.run(args, env=driver_env(repo, **extra), capture_output=True, text=True)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def raw_chain(repo, through=38):
    for number in range(1, through + 1):
        apply_migration(repo, number)


def versions(repo):
    with repo.connect() as conn:
        return conn.execute('SELECT * FROM schema_migrations ORDER BY version').fetchall()


def snapshot(repo):
    # pg_dump normalizes object definitions (columns, constraints, indexes,
    # functions, triggers and views); random dump restrict tokens are omitted.
    env = {**os.environ, 'PGHOST':'postgres', 'PGUSER':'lifecycle_test',
           'PGPASSWORD':'lifecycle_test_only', 'PGDATABASE':repo.database_name}
    dump = subprocess.run(['pg_dump', '--schema-only', '--no-owner', '--no-privileges'],
                          env=env, check=True, capture_output=True, text=True).stdout
    return '\n'.join(line for line in dump.splitlines()
                     if not line.startswith(('\\restrict ', '\\unrestrict ')))


def fixture_prefix(directory, through):
    for path in sorted((ROOT / 'db/migrations').glob('*.sql'))[:through]:
        shutil.copyfile(path, directory / path.name)
    return directory


def test_full_chain_restart_preserves_every_marker_and_schema(fresh_database):
    repo = fresh_database()
    before = versions(repo)
    schema = snapshot(repo)
    result = run_driver(repo)
    assert result.stdout.count('AUTODATA_SKIPPED ') == len(MIGRATION_NAMES)
    assert 'AUTODATA_APPLIED ' not in result.stdout
    assert versions(repo) == before
    assert snapshot(repo) == schema


def test_partial_catalog_row_survives_full_restart(fresh_database):
    repo = fresh_database()
    vehicle, source = seed_vehicle(repo), seed_snapshot(repo)
    with repo.connect() as conn:
        conn.execute("INSERT INTO catalog_articles(vehicle_id,article_id,source_snapshot_id,evidence_locator,evidence_confidence,content_status) VALUES (%s,'partial',%s,'fixture',1,'content_partial')", (vehicle,source))
        before = conn.execute('SELECT * FROM catalog_articles').fetchall()
    schema = snapshot(repo)
    run_driver(repo)
    with repo.connect() as conn:
        assert conn.execute('SELECT * FROM catalog_articles').fetchall() == before
    assert snapshot(repo) == schema


def driver_env(repo, **extra):
    return {**os.environ, 'PGHOST':'postgres', 'PGUSER':'lifecycle_test',
            'PGPASSWORD':'lifecycle_test_only', 'PGDATABASE':repo.database_name, **extra}


def applied(result):
    return [line.split(' ', 1)[1] for line in result.stdout.splitlines()
            if line.startswith('AUTODATA_APPLIED ')]


@pytest.mark.parametrize('empty_ledger', [False, True])
def test_empty_bootstrap_and_untracked_application_rejection(fresh_database, empty_ledger):
    repo = fresh_database(through=0)
    if empty_ledger:
        with repo.connect() as conn:
            conn.execute('CREATE TABLE schema_migrations(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
    assert applied(run_driver(repo)) == MIGRATION_NAMES
    assert len(versions(repo)) == len(MIGRATION_NAMES)
    for table in ('vehicles', 'canonical_article_revisions', 'customer_accounts', 'auth_sessions',
                  'workshop_orders', 'workshop_checkout_requests', 'canonical_article_link_bindings'):
        untracked = fresh_database(through=0)
        with untracked.connect() as conn:
            if empty_ledger:
                conn.execute('CREATE TABLE schema_migrations(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
            conn.execute('CREATE TABLE ' + table + '(sentinel text)')
        before = snapshot(untracked)
        failed = run_driver(untracked, check=False)
        assert failed.returncode != 0
        assert 'known application tables' in failed.stderr
        assert snapshot(untracked) == before


@pytest.mark.parametrize('corruption', ['unknown', 'wrong_stem', 'gap', 'duplicate_shape', 'wrong_timestamp'])
def test_invalid_ledger_fails_before_pending_application_ddl(fresh_database, corruption):
    repo = fresh_database(through=36)
    with repo.connect() as conn:
        if corruption in ('unknown','wrong_stem'):
            conn.execute('INSERT INTO schema_migrations(version) VALUES (%s)',
                         ('040_future' if corruption == 'unknown' else '032_wrong',))
        elif corruption == 'gap':
            conn.execute("DELETE FROM schema_migrations WHERE version='032_catalog_article_source_original'")
        elif corruption == 'duplicate_shape':
            conn.execute('ALTER TABLE schema_migrations DROP CONSTRAINT schema_migrations_pkey')
            conn.execute('INSERT INTO schema_migrations SELECT * FROM schema_migrations LIMIT 1')
        else:
            conn.execute('ALTER TABLE schema_migrations ALTER COLUMN applied_at DROP DEFAULT')
    before, old_versions = snapshot(repo), versions(repo)
    failure = run_driver(repo, check=False)
    assert failure.returncode != 0
    assert 'AUTODATA_APPLIED ' not in failure.stdout
    assert snapshot(repo) == before
    assert versions(repo) == old_versions


def test_original_038_adoption_and_markerless_033_effects_are_once_only(fresh_database, tmp_path):
    repo = fresh_database(through=0)
    raw_chain(repo)
    directory = fixture_prefix(tmp_path, 38)
    vehicle = seed_vehicle(repo)
    malformed = seed_configuration(repo, vehicle)
    control = seed_configuration(repo, vehicle)
    with repo.connect() as conn:
        base = conn.execute('SELECT vehicle_identity_base_id FROM vehicle_configurations WHERE vehicle_configuration_id=%s', (malformed,)).fetchone()['vehicle_identity_base_id']
        conn.execute("UPDATE vehicle_identity_bases SET make='Silverado', model='1500', updated_at='2000-01-01' WHERE vehicle_identity_base_id=%s", (base,))
        conn.execute("UPDATE vehicle_configurations SET updated_at='2000-01-01' WHERE vehicle_configuration_id=%s", (malformed,))
        before_control = conn.execute('SELECT * FROM vehicle_configurations WHERE vehicle_configuration_id=%s', (control,)).fetchone()
        before_base = conn.execute('SELECT * FROM vehicle_identity_bases WHERE vehicle_identity_base_id=%s', (base,)).fetchone()
        before_bad = conn.execute('SELECT * FROM vehicle_configurations WHERE vehicle_configuration_id=%s', (malformed,)).fetchone()
    before_versions, schema = versions(repo), snapshot(repo)
    assert applied(run_driver(repo, directory)) == ['033_catalog_scope_coverage.sql']
    with repo.connect() as conn:
        after_base = conn.execute('SELECT * FROM vehicle_identity_bases WHERE vehicle_identity_base_id=%s', (base,)).fetchone()
        after_bad = conn.execute('SELECT * FROM vehicle_configurations WHERE vehicle_configuration_id=%s', (malformed,)).fetchone()
        assert conn.execute('SELECT * FROM vehicle_configurations WHERE vehicle_configuration_id=%s', (control,)).fetchone() == before_control
    for before, after in ((before_base, after_base), (before_bad, after_bad)):
        assert after['reviewer_state'] == 'rejected'
        assert after['updated_at'] > before['updated_at']
        assert {k:v for k,v in before.items() if k not in ('reviewer_state','updated_at')} == {k:v for k,v in after.items() if k not in ('reviewer_state','updated_at')}
    assert [row for row in versions(repo) if row['version'] != '033_catalog_scope_coverage'] == before_versions
    assert snapshot(repo) == schema
    adopted_versions = versions(repo)
    assert applied(run_driver(repo, directory)) == []
    assert versions(repo) == adopted_versions
    with repo.connect() as conn:
        assert conn.execute('SELECT * FROM vehicle_identity_bases WHERE vehicle_identity_base_id=%s', (base,)).fetchone() == after_base
        assert conn.execute('SELECT * FROM vehicle_configurations WHERE vehicle_configuration_id=%s', (malformed,)).fetchone() == after_bad


def test_genuine_036_upgrade_preserves_jobs_and_matches_fresh_schema(fresh_database):
    legacy = fresh_database(through=0)
    raw_chain(legacy, through=35)
    jobs = seed_legacy_jobs_and_read_invariants(legacy)
    apply_migration(legacy, 36)
    old_versions = versions(legacy)
    assert applied(run_driver(legacy)) == ['033_catalog_scope_coverage.sql', *MIGRATION_NAMES[36:]]
    assert read_imported_job_invariants(legacy) == jobs
    assert [r for r in versions(legacy) if r['version'] in {v['version'] for v in old_versions}] == old_versions
    assert snapshot(legacy) == snapshot(fresh_database())
    assert applied(run_driver(legacy)) == []
    assert read_imported_job_invariants(legacy) == jobs


@pytest.mark.parametrize('number', [2, 33, *range(36, len(MIGRATION_NAMES) + 1)])
def test_migration_failure_rolls_back_only_active_file_then_retry(fresh_database, tmp_path, number):
    repo = fresh_database(through=number - 1)
    directory = fixture_prefix(tmp_path, number)
    path = next(directory.glob(f'{number:03d}_*.sql'))
    original = path.read_text()
    injection = '\nCREATE TABLE driver_rollback_first(id int);\nCREATE TABLE driver_rollback_second(id int);\nSELECT 1/0;\n'
    if number >= 36:
        location = original.index('INSERT INTO schema_migrations')
        changed = original[:location] + injection + original[location:]
    else:
        changed = original + injection
    path.write_text(changed)
    before, before_versions = snapshot(repo), versions(repo)
    result = run_driver(repo, directory, check=False)
    assert result.returncode != 0
    assert 'division by zero' in result.stderr
    assert snapshot(repo) == before
    assert versions(repo) == before_versions
    path.write_text(original)
    assert applied(run_driver(repo, directory)) == [path.name]
    assert applied(run_driver(repo, directory)) == []


def test_recorded_001_and_partial_unmarked_next_file_remain_retryable(fresh_database):
    repo = fresh_database(through=1)
    # A historical partial002 can leave this replay-oriented first table behind.
    body = (ROOT / 'db/migrations/002_platform_spine.sql').read_text()
    with repo.connect() as conn:
        conn.execute(body[:body.index(';') + 1])
    assert applied(run_driver(repo)) == MIGRATION_NAMES[1:]
    assert len(versions(repo)) == len(MIGRATION_NAMES)


@pytest.mark.parametrize('upgrade', [False, True])
def test_two_full_runners_serialize_and_apply_each_version_once(fresh_database, tmp_path, upgrade):
    repo = fresh_database(through=0)
    if upgrade:
        raw_chain(repo, through=36)
    directory = fixture_prefix(tmp_path, len(MIGRATION_NAMES))
    number = 33 if upgrade else 1
    path = next(directory.glob(f'{number:03d}_*.sql'))
    path.write_text(path.read_text() + '\nSELECT pg_sleep(4);\n')

    def wait_for_driver(name, event, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with repo.connect() as conn:
                observed = conn.execute(
                    'SELECT 1 FROM pg_stat_activity WHERE datname=%s AND application_name=%s AND wait_event=%s',
                    (repo.database_name, name, event),
                ).fetchone()
            if observed:
                return
            time.sleep(.02)
        pytest.fail(f'{name} did not reach {event}')

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        first = pool.submit(run_driver, repo, directory, PGAPPNAME='workshop-migration-first')
        wait_for_driver('workshop-migration-first', 'PgSleep', 10)
        second = pool.submit(run_driver, repo, PGAPPNAME='workshop-migration-second')
        wait_for_driver('workshop-migration-second', 'advisory', 4)
        results = [first.result(), second.result()]
    all_applied = sum((applied(r) for r in results), [])
    expected = ['033_catalog_scope_coverage.sql', *MIGRATION_NAMES[36:]] if upgrade else MIGRATION_NAMES
    assert sorted(all_applied) == sorted(expected)
    assert len(versions(repo)) == len(MIGRATION_NAMES)
    assert applied(run_driver(repo)) == []


def test_connection_death_releases_lock_and_rolls_back_active_file(fresh_database, tmp_path):
    repo = fresh_database(through=1)
    directory = fixture_prefix(tmp_path, 2)
    path = next(directory.glob('002_*.sql'))
    path.write_text(path.read_text() + '\nCREATE TABLE killed_backend_ddl(id int);\nSELECT pg_sleep(30);\n')
    before = versions(repo)
    process = subprocess.Popen(['sh', str(ROOT/'scripts/dev/migrate_sql.sh'), '--migrations-dir', str(directory)],
        env=driver_env(repo, PGAPPNAME='autodata-connection-death'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with repo.connect() as conn:
                backend = conn.execute("SELECT pid FROM pg_stat_activity WHERE datname=%s AND application_name='autodata-connection-death' AND wait_event='PgSleep'", (repo.database_name,)).fetchone()
            if backend:
                break
            time.sleep(.02)
        else:
            pytest.fail('migration did not enter injected pause')
        with repo.connect() as conn:
            conn.execute('SELECT pg_terminate_backend(%s)', (backend['pid'],))
        output, error = process.communicate(timeout=5)
        assert process.returncode != 0, output + error
        assert versions(repo) == before
        with repo.connect() as conn:
            assert conn.execute("SELECT to_regclass('killed_backend_ddl') AS object").fetchone()['object'] is None
            assert conn.execute("SELECT to_regclass('dataset_products') AS object").fetchone()['object'] is None
        assert applied(run_driver(repo)) == MIGRATION_NAMES[1:]
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


def test_restart_after_committed_037_applies_only_pending_migrations(fresh_database):
    repo = fresh_database(through=37)
    old_versions = versions(repo)
    assert applied(run_driver(repo)) == MIGRATION_NAMES[37:]
    assert versions(repo)[:37] == old_versions
    assert applied(run_driver(repo)) == []


def test_native_python_adapter_applies_then_skips_in_one_session(fresh_database):
    import sys
    sys.path.insert(0, str(ROOT/'scripts/dev'))
    from migrate import apply_migrations
    repo = fresh_database(through=0)
    from unittest.mock import patch
    with patch.dict(os.environ, {'AUTODATA_POSTGRES_USER':'lifecycle_test',
         'AUTODATA_POSTGRES_PASSWORD':'lifecycle_test_only', 'AUTODATA_POSTGRES_DB':repo.database_name}):
        assert len(apply_migrations(ROOT, 'postgres:5432')) == len(MIGRATION_NAMES)
        old_versions, schema = versions(repo), snapshot(repo)
        assert apply_migrations(ROOT, 'postgres:5432') == []
    assert versions(repo) == old_versions
    assert snapshot(repo) == schema


def test_markerless_033_failure_rolls_back_reviewer_effects_and_marker(fresh_database, tmp_path):
    repo = fresh_database(through=0)
    raw_chain(repo, through=36)
    configuration = seed_configuration(repo, seed_vehicle(repo))
    with repo.connect() as conn:
        base = conn.execute('SELECT vehicle_identity_base_id FROM vehicle_configurations WHERE vehicle_configuration_id=%s', (configuration,)).fetchone()['vehicle_identity_base_id']
        conn.execute("UPDATE vehicle_identity_bases SET make='Silverado',model='1500' WHERE vehicle_identity_base_id=%s", (base,))
        before_base = conn.execute('SELECT * FROM vehicle_identity_bases WHERE vehicle_identity_base_id=%s', (base,)).fetchone()
        before_config = conn.execute('SELECT * FROM vehicle_configurations WHERE vehicle_configuration_id=%s', (configuration,)).fetchone()
    old_versions = versions(repo)
    directory = fixture_prefix(tmp_path, 38)
    path = next(directory.glob('033_*.sql'))
    original = path.read_text()
    path.write_text(original + '\nSELECT 1/0;\n')
    failure = run_driver(repo, directory, check=False)
    assert failure.returncode != 0
    assert versions(repo) == old_versions
    with repo.connect() as conn:
        assert conn.execute('SELECT * FROM vehicle_identity_bases WHERE vehicle_identity_base_id=%s', (base,)).fetchone() == before_base
        assert conn.execute('SELECT * FROM vehicle_configurations WHERE vehicle_configuration_id=%s', (configuration,)).fetchone() == before_config
    path.write_text(original)
    assert applied(run_driver(repo, directory)) == ['033_catalog_scope_coverage.sql', '037_article_source_lifecycle.sql', '038_article_transform_publication.sql']


from lifecycle_support import runtime  # noqa: E402,F401 -- pytest fixture


def test_populated_publication_and_all_lifecycle_records_survive_restart(runtime):
    runtime.ingest_to_publication('bankone')
    runtime.stop_workers()
    repo = runtime.repo
    tables = ('schema_migrations', 'catalog_articles', 'canonical_articles',
              'canonical_article_source_revisions', 'canonical_article_source_observations',
              'canonical_article_revisions', 'canonical_article_reviews',
              'canonical_article_rewrite_attempts', 'source_fetch_jobs', 'publication_events')
    def rows():
        with repo.connect() as conn:
            return {table:conn.execute('SELECT to_jsonb(t) AS record FROM ' + table + ' t ORDER BY to_jsonb(t)::text').fetchall() for table in tables}
    before, schema = rows(), snapshot(repo)
    assert before['canonical_article_revisions']
    assert before['publication_events']
    assert applied(run_driver(repo)) == []
    assert rows() == before
    assert snapshot(repo) == schema


def test_populated_038_upgrade_only_adds_identity_schema(fresh_database, tmp_path):
    repo = fresh_database(through=38)
    seed_vehicle(repo)
    old_versions = versions(repo)
    with repo.connect() as conn:
        before = conn.execute('SELECT to_jsonb(v) AS row FROM vehicles v ORDER BY vehicle_id').fetchall()
    assert applied(run_driver(repo, fixture_prefix(tmp_path,39))) == ['039_production_identity_sessions.sql']
    assert versions(repo)[:38] == old_versions
    with repo.connect() as conn:
        assert conn.execute('SELECT to_jsonb(v) AS row FROM vehicles v ORDER BY vehicle_id').fetchall() == before
        assert conn.execute("SELECT to_regclass('customer_accounts') AS name").fetchone()['name']
        assert conn.execute("SELECT to_regclass('auth_sessions') AS name").fetchone()['name']
    assert snapshot(repo) == snapshot(fresh_database(through=39))
    assert applied(run_driver(repo)) == MIGRATION_NAMES[39:]
    assert snapshot(repo) == snapshot(fresh_database())
    assert applied(run_driver(repo)) == []


def test_populated_customer_identity_restart_preserves_rows_and_ledger(fresh_database):
    repo = fresh_database()
    with repo.connect() as conn:
        for status in ('active', 'blocked'):
            account = conn.execute("INSERT INTO customer_accounts(firebase_project_id,firebase_uid,status) VALUES ('fixture-project',%s,%s) RETURNING customer_account_id", (status,status)).fetchone()['customer_account_id']
            for number,state in enumerate(('active','expired','revoked')):
                conn.execute("INSERT INTO auth_sessions(session_token_hash,customer_account_id,firebase_auth_time,created_at,expires_at,revoked_at) VALUES (%s,%s,1,now()-interval '2 hours',CASE WHEN %s='expired' THEN now()-interval '1 hour' ELSE now()+interval '1 hour' END,CASE WHEN %s='revoked' THEN now() ELSE NULL END)", (bytes([number + (10 if status == 'blocked' else 0)])*32,account,state,state))
    def identity_rows():
        with repo.connect() as conn:
            return {table:conn.execute('SELECT to_jsonb(t) AS row FROM ' + table + ' t ORDER BY to_jsonb(t)::text').fetchall() for table in ('customer_accounts','auth_sessions')}
    before,ledger,schema = identity_rows(),versions(repo),snapshot(repo)
    assert applied(run_driver(repo)) == []
    assert identity_rows() == before
    assert versions(repo) == ledger
    assert snapshot(repo) == schema


def test_populated_040_projection_upgrade_and_restart_preserve_rows(fresh_database):
    from test_article_lifecycle_schema import seed_v1_publication, lifecycle_history, append_projection

    repo = fresh_database(through=40)
    _, source = seed_v1_publication(repo)
    before, ledger = lifecycle_history(repo), versions(repo)
    assert applied(run_driver(repo)) == MIGRATION_NAMES[40:]
    assert lifecycle_history(repo) == before
    assert versions(repo)[:40] == ledger
    append_projection(repo, source, 'source-projection-v2')
    append_projection(repo, source, 'source-projection-v3')
    populated, upgraded_schema, upgraded_ledger = lifecycle_history(repo), snapshot(repo), versions(repo)
    result = run_driver(repo)
    assert applied(result) == []
    assert result.stdout.count('AUTODATA_SKIPPED ') == len(MIGRATION_NAMES)
    assert lifecycle_history(repo) == populated
    assert snapshot(repo) == upgraded_schema
    assert versions(repo) == upgraded_ledger


def test_retained_article_link_bindings_upgrade_from_populated_052(fresh_database):
    from uuid import uuid4

    from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation

    from autodata_ingestion.article_lifecycle_types import ArticleKey
    from lifecycle_support import insert_descriptor
    from test_article_lifecycle_schema import append_projection, lifecycle_history, seed_v1_publication

    repo = fresh_database(through=52)
    article, source = seed_v1_publication(repo)
    second_source = append_projection(repo, source, "source-projection-v10")
    other_article = insert_descriptor(repo, ArticleKey("banktwo", seed_vehicle(repo), None, "fixture-v", "fixture-a"))
    second_job, second_revision = uuid4(), uuid4()
    with repo.connect() as conn:
        prior = conn.execute(
            "SELECT current_job_id, current_canonical_revision_id FROM canonical_articles WHERE canonical_article_id=%s",
            (article,),
        ).fetchone()
        revision = prior["current_canonical_revision_id"]
        conn.execute("""
            INSERT INTO source_fetch_jobs
            SELECT (jsonb_populate_record(NULL::source_fetch_jobs,
                to_jsonb(j) || jsonb_build_object('source_fetch_job_id', %s::uuid, 'idempotency_key', %s::text,
                    'request_generation', 1, 'source_revision_id', %s::uuid, 'transformation_key', %s::text))).*
            FROM source_fetch_jobs j WHERE j.source_fetch_job_id=%s
        """, (second_job, str(second_job), second_source, "f"*64, prior["current_job_id"]))
        conn.execute("""
            INSERT INTO canonical_article_revisions
            SELECT (jsonb_populate_record(NULL::canonical_article_revisions,
                to_jsonb(r) || jsonb_build_object('canonical_article_revision_id', %s::uuid,
                    'source_revision_id', %s::uuid, 'transformation_key', %s::text))).*
            FROM canonical_article_revisions r WHERE r.canonical_article_revision_id=%s
        """, (second_revision, second_source, "f"*64, revision))

    def legacy_read():
        with repo.connect() as conn:
            return conn.execute("SELECT * FROM catalog_article_current WHERE canonical_article_id=%s", (article,)).fetchone()

    before, old_ledger, old_read = lifecycle_history(repo), versions(repo), legacy_read()
    assert old_read["canonical_revision_id"] == revision
    assert applied(run_driver(repo)) == [
        "053_canonical_article_link_bindings.sql",
        "054_canonical_article_inline_link_bindings.sql",
    ]
    ledger = versions(repo)
    assert ledger[:-2] == old_ledger
    assert [entry["version"] for entry in ledger[-2:]] == [
        "053_canonical_article_link_bindings", "054_canonical_article_inline_link_bindings",
    ]
    assert snapshot(repo) == snapshot(fresh_database())

    binding = {
        "canonical_article_id": article, "source_revision_id": source, "canonical_article_revision_id": revision,
        "block_id": "x"*256, "label_sha256": "1"*64, "authored_id_sha256": "2"*64,
        "target_ref_sha256": "a"*64, "body_sha256": "b"*64,
    }
    insert = """
        INSERT INTO canonical_article_link_bindings
            (canonical_article_id, source_revision_id, canonical_article_revision_id,
             block_id, label_sha256, authored_id_sha256, target_ref_sha256, body_sha256)
        VALUES (%(canonical_article_id)s, %(source_revision_id)s, %(canonical_article_revision_id)s,
                %(block_id)s, %(label_sha256)s, %(authored_id_sha256)s, %(target_ref_sha256)s, %(body_sha256)s)
        RETURNING created_at
    """
    with repo.connect() as conn:
        assert conn.execute(insert, binding).fetchone()["created_at"] is not None
        conn.execute(insert, {**binding, "canonical_article_revision_id": second_revision, "source_revision_id": second_source})
    with pytest.raises(UniqueViolation), repo.connect() as conn:
        conn.execute(insert, {**binding, "target_ref_sha256": "c"*64})
    for mismatched in ({"canonical_article_id": other_article}, {"source_revision_id": second_source}):
        with pytest.raises(ForeignKeyViolation), repo.connect() as conn:
            conn.execute(insert, {**binding, "block_id": "other-block", **mismatched})
    for block_id in ("", " \t\n", "x"*257, "é"*129):
        with pytest.raises(CheckViolation), repo.connect() as conn:
            conn.execute(insert, {**binding, "block_id": block_id})
    for digest in ("label_sha256", "authored_id_sha256", "target_ref_sha256", "body_sha256"):
        for malformed in ("a"*63, "a"*64 + "\n", "A"*64, "g"*64):
            with pytest.raises(CheckViolation), repo.connect() as conn:
                conn.execute(insert, {**binding, "block_id": "other-block", digest: malformed})

    def bindings():
        with repo.connect() as conn:
            return conn.execute("SELECT * FROM canonical_article_link_bindings ORDER BY canonical_article_revision_id").fetchall()

    stored = bindings()
    assert len(stored) == 2
    assert applied(run_driver(repo)) == []
    assert versions(repo) == ledger
    assert bindings() == stored
    assert lifecycle_history(repo) == before
    assert legacy_read() == old_read
