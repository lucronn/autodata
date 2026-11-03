"""Opt-in owned local PG17 fixture; skips are never runtime acceptance evidence.

AUTODATA_SCHEMA_PROBE_PG17=1 AUTODATA_PG17_ROOT=/local/pg17
AUTODATA_SCHEMA_PROBE_EVIDENCE=/owned/private/temp/directory python3 -m unittest
  discover -s infra/deploy/gce -p test_schema_probe_pg17.py -v

No Docker, network downloads, existing server, DSN or production configuration.
"""
import pwd
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

SPEC = importlib.util.spec_from_file_location('schema_probe', Path(__file__).with_name('schema_probe.py'))
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
HERE = Path(__file__).resolve().parent
ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}
ADMIN = 'autodata_fixture_admin'
EXPECTED = ('001_initial', '002_accounts')


def receipt(status, **details):
    """Fixed safe fields only, never exception/log/SQL/source payloads."""
    value = {'protocol_version': 3, 'scope': 'disposable_schema_ledger',
             'status': status, 'production_ready': False, 'deployment_authorized': False, **details}
    data = json.dumps(value, sort_keys=True).encode()
    if len(data) > 65536:
        raise RuntimeError('fixture receipt limit')
    location = os.environ.get('AUTODATA_SCHEMA_PROBE_EVIDENCE')
    if location:
        directory = Path(location)
        if directory.is_symlink() or not directory.is_dir() or directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
            raise RuntimeError('fixture evidence directory must be owned and private')
        target = directory / ('pg17-' + uuid.uuid4().hex + '.json')
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data + b'\n')
    print(data.decode(), flush=True)
    return value


def toolchain():
    """No fallback to PATH's different-major server/client or package install."""
    reason = 'missing_pg17_root'
    root = Path(os.environ.get('AUTODATA_PG17_ROOT', '/usr/lib/postgresql/17'))
    tools = {}
    try:
        if not root.is_absolute() or not root.is_dir():
            raise ValueError()
        version = None
        for name in ('postgres', 'initdb', 'pg_ctl', 'psql', 'pg_config'):
            path = root / 'bin' / name
            reason = 'missing_pg17_executable'
            if not path.is_file() or not os.access(path, os.X_OK): raise ValueError()
            reason = 'non_pg17_or_mismatched_toolchain'
            output = subprocess.run([str(path), '--version'], env=ENV, cwd='/', stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=2, check=True).stdout.decode('ascii')
            match = re.search(r'(?:PostgreSQL\)? )?(17\.[0-9]+)(?:\s|$)', output)
            if not match: raise ValueError()
            if version is not None and version != match[1]: raise ValueError()
            version = match[1]; tools[name] = path
        reason = 'missing_pg17_headers'
        out = subprocess.run([str(tools['pg_config']), '--includedir-server'], env=ENV, cwd='/',
                             stdin=subprocess.DEVNULL, capture_output=True, timeout=2, check=True).stdout
        include = Path(out.decode('ascii').strip())
        header = include / 'pg_config.h'
        if not include.is_absolute() or not header.is_file() or not (include / 'postgres.h').is_file(): raise ValueError()
        if not re.search(r'^#define PG_VERSION_NUM 17[0-9]{4}$', header.read_text(), re.M): raise ValueError()
        reason = 'missing_local_c_compiler'
        compiler = shutil.which('cc', path=ENV['PATH'])
        if compiler is None: raise ValueError()
        reason = 'root_os_account_not_allowed'
        if os.getuid() == 0: raise ValueError()
        hashes = {key: hashlib.sha256(value.read_bytes()).hexdigest() for key, value in tools.items()}
        hashes['pg_config.h'] = hashlib.sha256(header.read_bytes()).hexdigest()
        for name in ('schema_probe.py', 'testdata/schema_probe_sentinel.c', 'testdata/schema_probe_fixtures.sql'):
            hashes[name] = hashlib.sha256((HERE / name).read_bytes()).hexdigest()
        return tools, include, compiler, version, hashes
    except (OSError, ValueError, subprocess.SubprocessError, UnicodeError):
        receipt('blocked_prerequisite', reason=reason, runtime_verified=False)
        raise RuntimeError('PG17 fixture prerequisite unavailable: ' + reason) from None


class PsqlTransport:
    """A single bounded fixture-owned process. No arbitrary server endpoints."""
    def __init__(self, fixture, role='autodata_schema_probe'):
        self.deadline = time.monotonic() + 12
        self.buffer = bytearray()
        self.writes = []
        self.fixture = fixture
        self.proc = subprocess.Popen(fixture.argv(role), env={**fixture.env, 'PGOPTIONS': probe.PGOPTIONS,
                                    'PGAPPNAME': 'autodata_probe_fixture'}, cwd=fixture.root,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        os.set_blocking(self.proc.stdin.fileno(), False)
        os.set_blocking(self.proc.stdout.fileno(), False)
        fixture.clients.append(self)

    def send(self, data):
        if type(data) is not bytes or len(data) > 65536: raise probe.ProbeUnavailable()
        if self.proc.poll() is not None: raise probe.ProbeUnavailable()
        limit = min(self.deadline, time.monotonic() + 1)
        with selectors.DefaultSelector() as selected:
            selected.register(self.proc.stdin, selectors.EVENT_WRITE)
            pos = 0
            while pos < len(data):
                remaining = limit - time.monotonic()
                if remaining <= 0 or not selected.select(remaining): raise probe.ProbeTimedOut()
                try: count = os.write(self.proc.stdin.fileno(), data[pos:pos + 4096])
                except BlockingIOError: continue
                if count <= 0: raise probe.ProbeUnavailable()
                pos += count
        self.writes.append(hashlib.sha256(data).hexdigest())

    def read_frame(self, maximum, deadline):
        with selectors.DefaultSelector() as selected:
            selected.register(self.proc.stdout, selectors.EVENT_READ)
            while True:
                newline = self.buffer.find(b'\n')
                if newline >= 0:
                    result = bytes(self.buffer[:newline + 1]); del self.buffer[:newline + 1]
                    if len(result) > maximum or self.buffer: raise probe.ProbeUnavailable()
                    return result
                remaining = min(self.deadline, deadline) - time.monotonic()
                if remaining <= 0 or not selected.select(remaining): raise probe.ProbeTimedOut()
                try: block = os.read(self.proc.stdout.fileno(), min(4096, maximum + 1 - len(self.buffer)))
                except BlockingIOError: continue
                if not block: raise probe.ProbeUnavailable()
                self.buffer.extend(block)
                if len(self.buffer) > maximum: raise probe.ProbeUnavailable()

    def close(self):
        marker = self.read_frame(524288, min(self.deadline, time.monotonic() + 1))
        if marker != probe.TERMINAL: raise probe.ProbeUnavailable()
        self.proc.stdin.close()
        if self.proc.wait(timeout=1) != 0: raise probe.ProbeUnavailable()
        trailing = os.read(self.proc.stdout.fileno(), 1)
        if trailing or self.buffer: raise probe.ProbeUnavailable()
        self.proc.stdout.close()

    def abort(self):
        if not self.proc.stdin.closed: self.proc.stdin.close()
        if self.proc.poll() is None:
            self.proc.terminate()
            try: self.proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self.proc.kill(); self.proc.wait(timeout=0.5)
        if not self.proc.stdout.closed: self.proc.stdout.close()


class LocalFixture:
    def __init__(self, tools, include, compiler):
        self.tools = tools
        self.root = Path(tempfile.mkdtemp(prefix='ad-schema-'))
        os.chmod(self.root, 0o700)
        self.data = self.root / 'data'
        self.socket = self.root / 'socket'; self.socket.mkdir(mode=0o700)
        self.log = self.root / 'server.log'
        self.env = {**ENV, 'HOME': str(self.root)}
        self.clients = []
        self.started = False
        self.start_attempted = False
        try:
            self.module = self.root / 'sentinel.so'
            subprocess.run([compiler, '-shared', '-fPIC', '-I' + str(include), '-o', str(self.module),
                            str(HERE / 'testdata/schema_probe_sentinel.c')], env=self.env, cwd=self.root,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30, check=True)
            subprocess.run([str(tools['initdb']), '-D', str(self.data), '-U', ADMIN, '--no-locale', '--encoding=UTF8'],
                           env=self.env, cwd=self.root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=30, check=True)
            (self.data / 'pg_hba.conf').write_text('local all all peer map=fixture\n')
            user = pwd.getpwuid(os.getuid()).pw_name
            if not re.fullmatch('[a-zA-Z0-9_.-]{1,64}', user): raise RuntimeError('unsupported fixture OS account')
            (self.data / 'pg_ident.conf').write_text(''.join('fixture ' + user + ' ' + role + '\n'
                for role in (ADMIN, 'autodata_schema_probe', 'autodata_metrics')))
            with (self.data / 'postgresql.conf').open('a') as config:
                config.write("\nlisten_addresses=''\nport=5432\nunix_socket_directories='" + str(self.socket) + "'\n"
                    "shared_preload_libraries=''\nsession_preload_libraries=''\nlocal_preload_libraries=''\n"
                    "log_min_messages=warning\nlog_statement='none'\n")
            self.start_attempted = True
            subprocess.run([str(tools['pg_ctl']), '-D', str(self.data), '-l', str(self.log), '-w', '-t', '10', 'start'],
                           env=self.env, cwd=self.root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=12, check=True)
            self.started = True
            self.admin('CREATE DATABASE autodata;', database='postgres')
            # Pristine PG17 built-ins are observed before loading fixture code.
            baseline = self.admin("SELECT count(*) FROM pg_catalog.pg_amproc p JOIN pg_catalog.pg_opfamily f ON f.oid=p.amprocfamily JOIN pg_catalog.pg_namespace n ON n.oid=f.opfnamespace WHERE n.nspname='pg_catalog' AND f.opfname='text_ops' AND f.opfmethod=(SELECT oid FROM pg_catalog.pg_am WHERE amname='btree');")
            if baseline.strip() != b'8': raise RuntimeError('PG17 builtin baseline mismatch')
            self.admin((HERE / 'testdata/schema_probe_fixtures.sql').read_text(),
                       options=['--set=sentinel_module=' + str(self.module)])
        except BaseException:
            self.stop()
            raise

    def argv(self, role, database='autodata'):
        if role not in (ADMIN, 'autodata_schema_probe', 'autodata_metrics') or database not in ('autodata', 'postgres'):
            raise RuntimeError('invalid fixture identity')
        return [str(self.tools['psql']), '-X', '--no-password', '--quiet', '--tuples-only', '--no-align',
                '--set=ON_ERROR_STOP=1', '--host=' + str(self.socket), '--port=5432', '--username=' + role,
                '--dbname=' + database]

    def admin(self, sql, database='autodata', options=(), success=True):
        result = subprocess.run(self.argv(ADMIN, database) + list(options), input=sql.encode(),
                                env=self.env, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=5, check=False)
        if len(result.stdout) > 1048576 or (result.returncode == 0) != success:
            raise RuntimeError('fixture administrator command failed')
        return result.stdout

    def reset(self):
        self.admin("""DO $f$ DECLARE k text; BEGIN
 SELECT relkind::text INTO k FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname='schema_migrations';
 IF k='v' THEN DROP VIEW public.schema_migrations CASCADE;
 ELSIF k='f' THEN DROP FOREIGN TABLE public.schema_migrations CASCADE;
 ELSIF k IS NOT NULL THEN DROP TABLE public.schema_migrations CASCADE; END IF; END $f$;
 CREATE TABLE public.schema_migrations(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
 ALTER TABLE public.schema_migrations OWNER TO autodata_schema_owner;
 GRANT SELECT,MAINTAIN ON public.schema_migrations TO autodata_schema_probe;
 GRANT SELECT ON public.schema_migrations TO autodata_metrics;
 INSERT INTO public.schema_migrations(version) VALUES ('001_initial'),('002_accounts');""")

    def marker_count(self, offset):
        with self.log.open('rb') as stream:
            stream.seek(offset)
            return stream.read(1048576).count(b'AUTODATA_PROBE_SENTINEL:')

    def clean_sessions(self):
        limit = time.monotonic() + 7
        while time.monotonic() < limit:
            count = self.admin("SELECT count(*) FROM pg_catalog.pg_stat_activity WHERE usename='autodata_schema_probe';")
            locks = self.admin("SELECT count(*) FROM pg_catalog.pg_locks l JOIN pg_catalog.pg_stat_activity a ON a.pid=l.pid WHERE a.usename='autodata_schema_probe';")
            if count.strip() == b'0' and locks.strip() == b'0': return
            time.sleep(0.05)
        raise RuntimeError('probe backend cleanup unavailable')

    def wait_lock(self):
        limit = time.monotonic() + 2
        while time.monotonic() < limit:
            count = self.admin("SELECT count(*) FROM pg_catalog.pg_locks l JOIN pg_catalog.pg_stat_activity a ON a.pid=l.pid WHERE a.usename='autodata_schema_probe' AND l.mode='ShareRowExclusiveLock' AND l.granted;")
            if count.strip() == b'1': return
            time.sleep(0.02)
        raise RuntimeError('fixture lock barrier unavailable')

    def stop(self):
        errors = []
        for client in self.clients:
            try: client.abort()
            except BaseException: errors.append('client_cleanup')
        if self.start_attempted:
            try:
                result = subprocess.run([str(self.tools['pg_ctl']), '-D', str(self.data), '-m', 'immediate', '-w', '-t', '5', 'stop'],
                                        env=self.env, cwd=self.root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, timeout=7, check=False)
                # A failed start/stop must never delete an uncertain live PGDATA.
                if result.returncode != 0 and (self.data / 'postmaster.pid').exists():
                    raise RuntimeError('fixture server shutdown uncertain')
                self.started = False
                self.start_attempted = False
            except BaseException:
                raise RuntimeError('fixture server cleanup failed; owned directory retained') from None
        shutil.rmtree(self.root)
        if errors: raise RuntimeError('fixture client cleanup failed')


class ToolchainGateTests(unittest.TestCase):
    def test_missing_toolchain_writes_redacted_blocking_receipt(self):
        with tempfile.TemporaryDirectory(prefix='ad-probe-gate-') as temporary:
            directory = Path(temporary)
            os.chmod(directory, 0o700)
            with patch.dict(os.environ, {'AUTODATA_PG17_ROOT': str(directory / 'absent'),
                                        'AUTODATA_SCHEMA_PROBE_EVIDENCE': str(directory)}), patch('sys.stdout', new=io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'missing_pg17_root'):
                    toolchain()
            reports = list(directory.glob('pg17-*.json'))
            self.assertEqual(len(reports), 1)
            value = json.loads(reports[0].read_text())
            self.assertEqual(value, {'protocol_version': 3, 'scope': 'disposable_schema_ledger',
                                    'status': 'blocked_prerequisite', 'reason': 'missing_pg17_root',
                                    'runtime_verified': False, 'production_ready': False,
                                    'deployment_authorized': False})
            self.assertEqual(reports[0].stat().st_mode & 0o777, 0o600)

    def test_transport_bounds_frames_and_reaps_owned_client(self):
        import sys
        class ProcessFixture:
            def __init__(self, root, source):
                self.root = root
                self.env = ENV
                self.clients = []
                self.source = source
            def argv(self, role):
                return [sys.executable, '-c', self.source]
        with tempfile.TemporaryDirectory(prefix='ad-probe-pipe-') as root:
            source = "import sys; sys.stdin.buffer.read(4); sys.stdout.buffer.write(b'one\\n'); sys.stdout.buffer.flush(); sys.stdin.buffer.read(5); sys.stdout.buffer.write(b'AUTODATA_SCHEMA_PROBE_CLOSED_V3\\n'); sys.stdout.buffer.flush()"
            fixture = ProcessFixture(root, source)
            t = PsqlTransport(fixture)
            try:
                t.send(b'PING')
                self.assertEqual(t.read_frame(16, time.monotonic() + 2), b'one\n')
                t.send(b'CLOSE')
                t.close()
                self.assertEqual(t.proc.returncode, 0)
            finally:
                t.abort()
            for payload in (b'x' * 17, b'one\ntwo\n', b''):
                source = 'import sys; sys.stdout.buffer.write(' + repr(payload) + '); sys.stdout.buffer.flush()'
                t = PsqlTransport(ProcessFixture(root, source))
                try:
                    with self.assertRaises(probe.ProbeUnavailable):
                        t.read_frame(16, time.monotonic() + 2)
                finally:
                    t.abort()
                self.assertIsNotNone(t.proc.poll())


@unittest.skipUnless(os.environ.get('AUTODATA_SCHEMA_PROBE_PG17') == '1', 'PG17 opt-in absent; no runtime acceptance')
class Pg17Acceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tools, include, compiler, version, hashes = toolchain()
        cls.cases = []
        try: cls.fixture = LocalFixture(tools, include, compiler)
        except BaseException:
            receipt('blocked_fixture_setup', runtime_verified=False)
            raise RuntimeError('PG17 disposable fixture setup failed') from None
        receipt('fixture_started', server_version=version, tool_source_hashes=hashes, runtime_verified=False,
                module_sha256=hashlib.sha256(cls.fixture.module.read_bytes()).hexdigest())

    @classmethod
    def tearDownClass(cls):
        try:
            cls.fixture.clean_sessions()
            cls.fixture.stop()
        except BaseException:
            receipt('cleanup_failed', runtime_verified=False)
            raise
        receipt('fixture_stopped', passed_cases=cls.cases, runtime_verified=False,
                qualification='Individual case receipts do not establish production or full planned-matrix acceptance.')

    def setUp(self):
        self.fixture.reset()

    def tearDown(self):
        for client in self.fixture.clients: client.abort()
        self.fixture.clean_sessions()

    def passed(self):
        self.cases.append(self.id().split('.')[-1])
        receipt('case_passed', case=self.cases[-1], runtime_verified=False)

    def observe(self, expected=EXPECTED):
        return probe.observe_catalog_ledger(PsqlTransport(self.fixture), expected)

    def rejected(self):
        offset = self.fixture.log.stat().st_size
        transport = PsqlTransport(self.fixture)
        with self.assertRaises(probe.ProbeUnavailable): probe.observe_catalog_ledger(transport, EXPECTED)
        self.assertNotIn(hashlib.sha256(probe.LEDGER_SQL).hexdigest(), transport.writes)
        self.assertEqual(self.fixture.marker_count(offset), 0)

    def test_safe_ledger_and_select_only_lock_denial(self):
        self.assertFalse(self.observe()['production_ready'])
        t = PsqlTransport(self.fixture, 'autodata_metrics')
        t.send(probe.BEGIN_SQL + probe.CATALOG_SQL)
        with self.assertRaises(probe.ProbeUnavailable): t.read_frame(524288, time.monotonic() + 3)
        t.abort()
        self.passed()

    def test_hostile_sentinels_have_positive_controls(self):
        # Every negative control intentionally reads the hostile object locally.
        # Setup log output is excluded before observing either control or probe.
        cases = [
            ("DROP TABLE public.schema_migrations; CREATE VIEW public.schema_migrations AS SELECT public.probe_text('001_initial') AS version,now() AS applied_at; GRANT SELECT ON public.schema_migrations TO autodata_schema_probe;", "SELECT * FROM public.schema_migrations;", True),
            ("DROP TABLE public.schema_migrations; CREATE FOREIGN TABLE public.schema_migrations(version text,applied_at timestamptz) SERVER probe_server; GRANT SELECT ON public.schema_migrations TO autodata_schema_probe;", "SELECT * FROM public.schema_migrations;", False),
            ("ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY; ALTER TABLE public.schema_migrations FORCE ROW LEVEL SECURITY; CREATE POLICY fixture ON public.schema_migrations USING(public.probe_predicate('rls'));", "SET ROLE autodata_schema_probe; SELECT * FROM public.schema_migrations;", True),
            ("DROP TABLE public.schema_migrations; CREATE TABLE public.schema_migrations(version public.probe_type,applied_at timestamptz NOT NULL); INSERT INTO public.schema_migrations VALUES('001_initial',now()); ALTER TABLE public.schema_migrations OWNER TO autodata_schema_owner; GRANT SELECT,MAINTAIN ON public.schema_migrations TO autodata_schema_probe;", "SELECT * FROM public.schema_migrations;", True),
            ("ALTER TABLE public.schema_migrations SET ACCESS METHOD probe_heap;", "SELECT * FROM public.schema_migrations;", True),
            ("CREATE INDEX fixture ON public.schema_migrations USING probe_btree(version);", "SELECT * FROM public.schema_migrations;", True),
            ("CREATE INDEX fixture ON public.schema_migrations((public.probe_text('constant')));", "SELECT * FROM public.schema_migrations;", True),
            ("CREATE INDEX fixture ON public.schema_migrations(version) WHERE public.probe_predicate('constant');", "SELECT * FROM public.schema_migrations;", True),
        ]
        for setup, control, success in cases:
            with self.subTest(fixture=cases.index((setup, control, success))):
                self.fixture.reset(); self.fixture.admin(setup)
                offset = self.fixture.log.stat().st_size
                self.fixture.admin(control, success=success)
                self.assertGreater(self.fixture.marker_count(offset), 0, 'invalid sentinel negative control')
                self.rejected()
        self.passed()

    def test_additional_indexes_columns_rls_and_privileges(self):
        statements = ["CREATE INDEX fixture ON public.schema_migrations(applied_at);",
                      "CREATE INDEX fixture ON public.schema_migrations(version public.probe_text_ops);",
                      "ALTER TABLE public.schema_migrations ALTER COLUMN applied_at DROP NOT NULL;",
                      "ALTER TABLE public.schema_migrations ADD COLUMN extra text;",
                      "ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;",
                      "GRANT UPDATE ON public.schema_migrations TO PUBLIC;",
                      "GRANT UPDATE(version) ON public.schema_migrations TO autodata_schema_probe;",
                      "GRANT MAINTAIN ON public.other_table TO PUBLIC;",
                      "ALTER TABLE public.schema_migrations OWNER TO autodata_schema_probe;"]
        for sql in statements:
            with self.subTest(statement=statements.index(sql)):
                self.fixture.reset(); self.fixture.admin(sql); self.rejected()
                self.fixture.admin('REVOKE MAINTAIN ON public.other_table FROM PUBLIC;')
        self.passed()

    def test_bounded_ledger_values(self):
        for rows in ([], ['003_extra'], ['001_' + 'x' * 129], ['001_é'], [f'{i:03}_entry' for i in range(257)]):
            self.fixture.reset(); self.fixture.admin('TRUNCATE public.schema_migrations;')
            if rows:
                self.fixture.admin('INSERT INTO public.schema_migrations(version) VALUES ' + ','.join("('" + value + "')" for value in rows) + ';')
            with self.assertRaises(probe.ProbeUnavailable): self.observe()
        self.fixture.reset(); self.fixture.admin('TRUNCATE public.schema_migrations;')
        rows = tuple(f'{i:03}_entry' for i in range(256))
        self.fixture.admin('INSERT INTO public.schema_migrations(version) VALUES ' + ','.join("('" + value + "')" for value in rows) + ';')
        self.assertTrue(self.observe(rows)['ledger_matches'])
        self.passed()

    def test_concurrent_ddl_waits_for_strong_lock(self):
        statements = ['CREATE INDEX fixture ON public.schema_migrations(applied_at);',
                      'CREATE INDEX CONCURRENTLY fixture ON public.schema_migrations(applied_at);',
                      'REINDEX TABLE CONCURRENTLY public.schema_migrations;',
                      'ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;',
                      'ALTER TABLE public.schema_migrations ALTER COLUMN version TYPE varchar(128);',
                      'ALTER TABLE public.schema_migrations RENAME TO fixture_old;',
                      'DROP TABLE public.schema_migrations;',
                      "INSERT INTO public.schema_migrations(version) VALUES('003_extra');"]
        for sql in statements:
            with self.subTest(statement=statements.index(sql)):
                self.fixture.reset()
                t = PsqlTransport(self.fixture); t.send(probe.BEGIN_SQL); self.fixture.wait_lock()
                self.fixture.admin("SET lock_timeout='1s'; " + sql, success=False)
                t.send(probe.FINISH_SQL); t.close()
                if 'CREATE INDEX' in sql: self.fixture.admin('DROP INDEX IF EXISTS public.fixture;')
                self.fixture.admin(sql)
                if 'RENAME' in sql: self.fixture.admin('DROP TABLE public.fixture_old;')
        self.passed()

    def test_first_snapshot_after_ddl_commit(self):
        # A fixture-owned second psql holds DDL before the observer's first LOCK.
        owner = subprocess.Popen(self.fixture.argv(ADMIN), env=self.fixture.env, cwd=self.fixture.root,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            owner.stdin.write(b'BEGIN; CREATE INDEX fixture ON public.schema_migrations(applied_at); \\echo HELD\n'); owner.stdin.flush()
            with selectors.DefaultSelector() as selected:
                selected.register(owner.stdout, selectors.EVENT_READ)
                if not selected.select(2) or os.read(owner.stdout.fileno(), 4096) != b'HELD\n':
                    self.fail('DDL barrier unavailable')
            t = PsqlTransport(self.fixture); t.send(probe.BEGIN_SQL)
            # Observe a real waiting lock before allowing the DDL commit.
            deadline = time.monotonic() + 0.7
            while True:
                waiting = self.fixture.admin("SELECT count(*) FROM pg_catalog.pg_locks l JOIN pg_catalog.pg_stat_activity a ON a.pid=l.pid WHERE a.usename='autodata_schema_probe' AND NOT l.granted;")
                if waiting.strip() == b'1': break
                if time.monotonic() >= deadline: self.fail('waiting-lock barrier unavailable')
                time.sleep(0.01)
            owner.stdin.write(b'COMMIT;\n\\quit\n'); owner.stdin.flush(); owner.wait(timeout=1)
            t.send(probe.CATALOG_SQL)
            with self.assertRaises(probe.ProbeUnavailable): probe.validate_catalog(probe._decode(t.read_frame(524288, time.monotonic() + 3)))
            t.abort()
        finally:
            if owner.poll() is None: owner.kill(); owner.wait(timeout=1)
            owner.stdin.close(); owner.stdout.close()
        self.passed()

    def test_abandoned_backend_idle_cleanup(self):
        t = PsqlTransport(self.fixture); t.send(probe.BEGIN_SQL); self.fixture.wait_lock()
        # Leave the frontend process alive but send no further bytes. Server's
        # idle_in_transaction_session_timeout must release backend/session locks.
        self.fixture.clean_sessions()
        t.abort()
        self.passed()


if __name__ == '__main__':
    unittest.main()
