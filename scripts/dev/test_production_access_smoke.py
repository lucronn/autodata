"""Pure collector checks and the explicitly required real PostgreSQL/SDK bridge."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import production_access_smoke as smoke


class AccessCollectorTests(unittest.TestCase):
    def test_requires_root_and_all_five_without_skips(self):
        events = [{'Action': action, 'Test': name, 'Time': '2026-11-03T00:00:00Z'}
                  for name in (smoke.GO_ROOT, *smoke.GO_IDS) for action in ('run', 'pass')]
        self.assertEqual(smoke.go_results(events), {name: True for name in smoke.GO_NAMES})
        for name in (smoke.GO_ROOT, *smoke.GO_IDS):
            self.assertFalse(all(smoke.go_results([e for e in events if e['Test'] != name]).values()))
        self.assertFalse(all(smoke.go_results(events + [{'Action': 'skip', 'Test': smoke.GO_IDS[0]}]).values()))
        self.assertFalse(all(smoke.go_results(events + [{'Action': 'fail', 'Test': smoke.GO_IDS[0]}]).values()))
        for extra in ({'Action': 'fail'}, {'Action': 'skip', 'Test': 'Unexpected'},
                      {'Action': 'fail', 'Test': smoke.GO_IDS[0] + '/Nested'},
                      {'Action': 'pass', 'Test': 'Unexpected'},
                      {'Action': 'run', 'Test': smoke.GO_IDS[0] + '/Nested'}):
            self.assertFalse(all(smoke.go_results(events + [extra]).values()), extra)
        inherited = {'PATH': '/fixture/bin', 'HOME': '/original', 'AWS_SECRET_ACCESS_KEY': 'no',
                     'AUTODATA_FIREBASE_PROJECT_ID': 'no', 'AUTODATA_STRIPE_KEY': 'no',
                     'BANKONE_BASE_URL': 'no', 'GOOGLE_APPLICATION_CREDENTIALS': 'no'}
        self.assertEqual(smoke.go_environment(inherited), {'PATH': '/fixture/bin'})


    def test_junit_missing_empty_or_skip_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'junit.xml'
            self.assertEqual(smoke.junit_results(path), (0, False))
            for xml in ('<testsuites/>', '<testsuites><testsuite><testcase><skipped/></testcase></testsuite></testsuites>',
                        '<testsuite><testcase><failure/></testcase></testsuite>'):
                path.write_text(xml)
                self.assertFalse(smoke.junit_results(path)[1])
            path.write_text('<testsuite><testcase name="actual"/></testsuite>')
            self.assertEqual(smoke.junit_results(path), (1, True))

    def test_failed_process_cannot_be_success(self):
        flags = {key: True for key in smoke.ASSERTION_KEYS}
        self.assertFalse(smoke.success(1, False, flags))
        self.assertFalse(smoke.success(0, True, flags))
        flags[smoke.GO_NAMES[0]] = False
        self.assertFalse(smoke.success(0, False, flags))
        self.assertFalse(smoke.success(0, False, {}))


if os.getenv('AUTODATA_REQUIRE_AUTH_INTEGRATION') == '1':
    if os.getenv('AUTODATA_LIFECYCLE_TEST') != '1':
        raise RuntimeError('required auth bridge needs explicit lifecycle fixture')
    from lifecycle_support import fresh_database  # noqa: F401

    def test_required_postgres_auth_sessions(fresh_database):
        """Actual Go HTTP/SDK/PG five-case suite, with a separate 038 startup DB."""
        full, old = fresh_database(), fresh_database(through=38)
        artifacts = Path('/artifacts')
        env = smoke.go_environment(os.environ)
        env.update(AUTODATA_REQUIRE_AUTH_INTEGRATION='1', AUTODATA_LIFECYCLE_TEST='1',
                   AUTODATA_AUTH_TEST_DATABASE_URL=f'postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{full.database_name}?sslmode=disable',
                   AUTODATA_AUTH_TEST_UNMIGRATED_DATABASE_URL=f'postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{old.database_name}?sslmode=disable',
                   GOMODCACHE='/opt/go-module-cache', GOPROXY='off', GOFLAGS='-mod=readonly',
                   GOTOOLCHAIN='local', CGO_ENABLED='0', PYTHONDONTWRITEBYTECODE='1')
        timed_out = False
        with tempfile.TemporaryDirectory(prefix='r5-go-') as temporary:
            env.update(GOCACHE=temporary + '/cache', GOTMPDIR=temporary)
            with (artifacts / 'r5-access-go-events.jsonl').open('wb') as out, (artifacts / 'r5-access-go-stderr.log').open('wb') as err:
                try:
                    result = subprocess.run(['go', 'test', '-json', '-count=1', '-run', '^' + smoke.GO_ROOT + '$', '.'],
                                            cwd=smoke.ROOT / 'apps/api-go', env=env, stdout=out, stderr=err,
                                            timeout=180, check=False)
                    code = result.returncode
                except subprocess.TimeoutExpired:
                    timed_out, code = True, -1
        # Capture only safe synthetic fixture columns; no raw tokens or SDK payloads.
        with full.connect() as conn, old.connect() as old_conn:
            ledger = lambda c: c.execute('SELECT version, applied_at FROM schema_migrations ORDER BY version').fetchall()
            rows = {'schema_version': 1, 'candidate_sha': os.environ['AUTODATA_R3_CANDIDATE_SHA'],
                    'fixture_database': full.database_name,
                    'server_version_num': int(conn.execute('SHOW server_version_num').fetchone()['server_version_num']),
                    'schema_migrations': ledger(conn),
                    'customer_accounts': conn.execute('SELECT customer_account_id,firebase_project_id,firebase_uid,personal_organization_id,status,created_at FROM customer_accounts ORDER BY customer_account_id').fetchall(),
                    'auth_sessions': conn.execute("SELECT encode(session_token_hash,'hex') AS session_token_hash,customer_account_id,firebase_auth_time,created_at,expires_at,revoked_at FROM auth_sessions ORDER BY session_token_hash").fetchall(),
                    'unmigrated_fixture_database': old.database_name,
                    'unmigrated_schema_migrations': ledger(old_conn),
                    'go_exit_code': code, 'go_timed_out': timed_out}
        smoke.write_json(artifacts / 'r5-access-migration-rows.json', rows)
        assert not timed_out and code == 0, 'required Go suite failed; retained raw events and stderr'


if __name__ == '__main__':
    unittest.main()
