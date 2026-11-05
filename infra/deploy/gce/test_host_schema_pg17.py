"""Real production SQL protocol on a disposable cached PostgreSQL17 container.

AUTODATA_REQUIRE_PG17=1 makes missing Docker/image a hard acceptance failure.
No host runtime config, credentials, published port or external network is used.
"""
import copy
import json
import os
import subprocess
import time
import unittest
import uuid
from unittest.mock import patch
from test_host_runtime import load_runtime, postgres_wire


class Postgres17ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rt = load_runtime()
        cls.container = 'autodata-schema-test-' + uuid.uuid4().hex
        cls.image = 'pgvector/pgvector:pg17'
        probe = subprocess.run(['/usr/bin/docker', 'image', 'inspect', cls.image], capture_output=True, timeout=5)
        if probe.returncode:
            message = 'real PG17 unavailable: cached pgvector/pgvector:pg17 required; schema acceptance UNVERIFIED'
            if os.environ.get('AUTODATA_REQUIRE_PG17') == '1': raise AssertionError(message)
            raise unittest.SkipTest(message)
        result = subprocess.run(['/usr/bin/docker', 'run', '--pull=never', '--rm', '-d', '--network=none',
            '--name', cls.container, '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', '-e', 'POSTGRES_DB=autodata', cls.image],
            capture_output=True, timeout=30)
        if result.returncode: raise AssertionError('disposable PG17 startup failed')
        cls.addClassCleanup(lambda: subprocess.run(['/usr/bin/docker', 'rm', '-f', cls.container], capture_output=True, timeout=10))
        for _ in range(100):
            result = cls.sql('SELECT 1;', check=False)
            if result.returncode == 0: break
            time.sleep(.1)
        else: raise AssertionError('disposable PG17 did not become ready')
        cls.sql('CREATE ROLE autodata_metrics LOGIN NOINHERIT;')
        version = cls.sql('SHOW server_version_num;').stdout.strip()
        if not 170000 <= int(version) < 180000: raise AssertionError('test requires real PG17')

    @classmethod
    def sql(cls, sql, role='postgres', check=True):
        result = subprocess.run(['/usr/bin/docker', 'exec', '-i', cls.container,
            '/usr/lib/postgresql/17/bin/psql', '-X', '-A', '-t', '-q', '-v', 'ON_ERROR_STOP=1',
            '-h', '/var/run/postgresql', '-U', role, '-d', 'autodata'], input=sql.encode(), capture_output=True, timeout=8)
        if check and result.returncode: raise AssertionError(result.stderr.decode())
        return result

    def setUp(self):
        self.rt = load_runtime()
        self.sql('ALTER ROLE autodata_metrics NOSUPERUSER NOBYPASSRLS NOINHERIT; DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
            'CREATE TABLE public.schema_migrations(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());'
            "INSERT INTO public.schema_migrations(version) VALUES ('001_initial'),('002_next');")
        self.sql((__import__('pathlib').Path(__file__).parent / 'runtime-grants.sql').read_text())
        self.manifest = {'migrations': {'files': [{'name': '001_initial.sql'}, {'name': '002_next.sql'}]},
                         'images': {'postgres': {'image_id': 'sha256:' + 'c' * 64}}}

    def collect(self, script=None):
        original = self.rt._bounded_schema_command
        fixture = postgres_wire(self.manifest['images']['postgres']['image_id'])
        def execute(argv, maximum, deadline, input_data=None):
            if 'inspect' in argv: return json.dumps(fixture).encode()
            argv = list(argv)
            argv[argv.index('d' * 64)] = self.container
            return original(argv, maximum, deadline, input_data=input_data if script is None else script)
        with patch.object(self.rt, '_bounded_schema_command', side_effect=execute):
            return self.rt.collect_postgres_schema(self.manifest)

    def test_correct_ledger_and_exact_probe_grants_succeed(self):
        self.assertEqual(self.collect(), {'version': 2, 'migrations': ['001_initial', '002_next']})

    def test_missing_extra_duplicate_inventory_and_long_text_fail(self):
        for sql in ("DELETE FROM public.schema_migrations WHERE version='002_next';",
                    "INSERT INTO public.schema_migrations(version) VALUES ('003_extra');",
                    'ALTER TABLE public.schema_migrations DROP CONSTRAINT schema_migrations_pkey;',
                    "UPDATE public.schema_migrations SET version=repeat('a',129) WHERE version='002_next';"):
            with self.subTest(sql=sql):
                self.setUp(); self.sql(sql)
                with self.assertRaises(self.rt.ContractError): self.collect()

    def test_unsafe_role_and_catalog_fail_before_ledger_select(self):
        mutations = ('REVOKE SELECT ON public.schema_migrations FROM autodata_metrics;',
            'REVOKE CONNECT ON DATABASE autodata FROM autodata_metrics;',
            'ALTER ROLE autodata_metrics SUPERUSER;', 'ALTER ROLE autodata_metrics BYPASSRLS;',
            'GRANT UPDATE ON public.schema_migrations TO autodata_metrics;',
            'GRANT MAINTAIN ON public.schema_migrations TO PUBLIC;',
            'ALTER TABLE public.schema_migrations OWNER TO autodata_metrics;',
            'ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;',
            'DROP TABLE public.schema_migrations;',
            'ALTER TABLE public.schema_migrations RENAME TO old; CREATE VIEW public.schema_migrations AS SELECT * FROM public.old;',
            'CREATE DOMAIN public.version_type AS text; ALTER TABLE public.schema_migrations ALTER version TYPE public.version_type;',
            'CREATE INDEX expression_idx ON public.schema_migrations ((lower(version)));')
        for sql in mutations:
            with self.subTest(sql=sql):
                # Previous PUBLIC grant is intentionally removed before reset.
                self.sql('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;')
                self.setUp(); self.sql(sql)
                with self.assertRaises(self.rt.ContractError): self.collect()

    def test_concurrent_ddl_blocks_until_locked_protocol_finishes(self):
        script = self.rt._postgres_schema_script(self.manifest)
        # A pipe-controlled psql session runs exactly the production protocol up
        # to its lock, then the remainder. No timing-dependent sleep in SQL.
        before, rest = script.split(b'SELECT observed', 1)
        child = subprocess.Popen(['/usr/bin/docker', 'exec', '-i', self.container,
            '/usr/bin/env', '-i', 'PGOPTIONS=' + self.rt.POSTGRES_PGOPTIONS,
            '/usr/lib/postgresql/17/bin/psql', '-X', '-A', '-t', '-q', '-v', 'ON_ERROR_STOP=1',
            '-h', '/var/run/postgresql', '-U', 'autodata_metrics', '-d', 'autodata'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            child.stdin.write(before + b"\\echo LOCKED\n"); child.stdin.flush()
            self.assertEqual(child.stdout.readline().strip(), b'LOCKED')
            for ddl in ('ALTER TABLE public.schema_migrations RENAME TO replacement;',
                        'ALTER TABLE public.schema_migrations ADD COLUMN unsafe text;',
                        'DROP TABLE public.schema_migrations;'):
                outcome = self.sql("SET lock_timeout='100ms'; " + ddl, check=False)
                self.assertNotEqual(outcome.returncode, 0)
                self.assertIn(b'lock timeout', outcome.stderr)
            child.stdin.write(b'SELECT observed' + rest); child.stdin.close(); child.stdin = None
            output, errors = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 0, errors.decode())
            ledger = self.rt.strict_json(output.splitlines()[1])
            self.rt.validate_schema_ledger(self.manifest, ledger)
        finally:
            if child.poll() is None: child.kill()
            child.communicate(timeout=5)


if __name__ == '__main__': unittest.main()
