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


def run_driver(repo, directory=None, check=True):
    args = ['sh', str(ROOT / 'scripts/dev/migrate_sql.sh')]
    if directory is not None:
        args += ['--migrations-dir', str(directory)]
    result = subprocess.run(args, env={**os.environ, 'PGHOST': 'postgres',
        'PGUSER': 'lifecycle_test', 'PGPASSWORD': 'lifecycle_test_only',
        'PGDATABASE': repo.database_name}, capture_output=True, text=True)
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
    assert result.stdout.count('AUTODATA_SKIPPED ') == 40
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
    assert len(applied(run_driver(repo))) == 40
    assert len(versions(repo)) == 40
    for table in ('vehicles', 'canonical_article_revisions', 'customer_accounts', 'auth_sessions', 'workshop_orders', 'workshop_checkout_requests'):
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
    assert applied(run_driver(legacy)) == ['033_catalog_scope_coverage.sql',
        '037_article_source_lifecycle.sql', '038_article_transform_publication.sql',
        '039_production_identity_sessions.sql', '040_workshop_commerce.sql']
    assert read_imported_job_invariants(legacy) == jobs
    assert [r for r in versions(legacy) if r['version'] in {v['version'] for v in old_versions}] == old_versions
    assert snapshot(legacy) == snapshot(fresh_database())
    assert applied(run_driver(legacy)) == []
    assert read_imported_job_invariants(legacy) == jobs


@pytest.mark.parametrize('number', [2, 33, 36, 37, 38, 39, 40])
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
    assert len(applied(run_driver(repo))) == 39
    assert len(versions(repo)) == 40


@pytest.mark.parametrize('upgrade', [False, True])
def test_two_full_runners_serialize_and_apply_each_version_once(fresh_database, tmp_path, upgrade):
    repo = fresh_database(through=0)
    if upgrade:
        raw_chain(repo, through=36)
    directory = fixture_prefix(tmp_path, 39)
    number = 33 if upgrade else 1
    path = next(directory.glob(f'{number:03d}_*.sql'))
    path.write_text(path.read_text() + '\nSELECT pg_sleep(1);\n')
    # One explicit fixture pauses inside the pending migration transaction.
    # Both complete drivers still use the same production lock/check path.
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        first = pool.submit(run_driver, repo, directory)
        time.sleep(.1)
        second = pool.submit(run_driver, repo)
        deadline = time.monotonic() + .8
        waiting = False
        while time.monotonic() < deadline:
            with repo.connect() as conn:
                waiting = conn.execute("SELECT EXISTS(SELECT FROM pg_stat_activity WHERE datname=%s AND wait_event='advisory') AS waiting", (repo.database_name,)).fetchone()['waiting']
            if waiting:
                break
            time.sleep(.01)
        assert waiting, 'second full driver never waited on the session advisory lock'
        results = [first.result(), second.result()]
    all_applied = sum((applied(r) for r in results), [])
    expected = ['033_catalog_scope_coverage.sql', '037_article_source_lifecycle.sql', '038_article_transform_publication.sql', '039_production_identity_sessions.sql', '040_workshop_commerce.sql'] if upgrade else [p.name for p in sorted((ROOT/'db/migrations').glob('*.sql'))]
    assert sorted(all_applied) == sorted(expected)
    assert len(versions(repo)) == 40
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
        assert len(applied(run_driver(repo))) == 39
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


def test_restart_after_committed_037_only_applies_038_and_039(fresh_database):
    repo = fresh_database(through=37)
    old_versions = versions(repo)
    assert applied(run_driver(repo)) == ['038_article_transform_publication.sql', '039_production_identity_sessions.sql', '040_workshop_commerce.sql']
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
        assert len(apply_migrations(ROOT, 'postgres:5432')) == 40
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
    assert applied(run_driver(repo)) == ['040_workshop_commerce.sql']
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
