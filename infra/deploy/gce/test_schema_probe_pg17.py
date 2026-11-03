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

# Every case below runs against the owned disposable cluster when opted in.
# IDs are the required runtime inventory, not evidence of execution.
def _case(case, setup, **options):
    return {'case': case, 'setup': setup, **options}


HOSTILE_RELATIONS = [
    _case('view_constant_expression', "DROP TABLE public.schema_migrations; CREATE VIEW public.schema_migrations AS SELECT public.probe_text('001_initial') AS version,now() AS applied_at; GRANT SELECT,MAINTAIN ON public.schema_migrations TO autodata_schema_probe;",
          control='SELECT * FROM public.schema_migrations;', marker='expression'),
    _case('view_custom_heap_dependency', "CREATE TABLE public.fixture_backing(version text,applied_at timestamptz) USING probe_heap; INSERT INTO public.fixture_backing VALUES('001_initial',now()); DROP TABLE public.schema_migrations; CREATE VIEW public.schema_migrations AS SELECT public.probe_text(version) AS version,applied_at FROM public.fixture_backing; GRANT SELECT,MAINTAIN ON public.schema_migrations,public.fixture_backing TO autodata_schema_probe;",
          cleanup='DROP VIEW IF EXISTS public.schema_migrations; DROP TABLE public.fixture_backing;',
          control='SELECT * FROM public.schema_migrations;', marker='heap'),
    _case('foreign_relation', "DROP TABLE public.schema_migrations; CREATE FOREIGN TABLE public.schema_migrations(version text,applied_at timestamptz) SERVER probe_server; GRANT SELECT ON public.schema_migrations TO autodata_schema_probe;",
          control='SELECT * FROM public.schema_migrations;', marker='fdw', control_success=False),
    _case('rls_policy', "ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY; CREATE POLICY fixture_policy ON public.schema_migrations USING(public.probe_predicate('rls'));",
          control='SET ROLE autodata_schema_probe; SELECT * FROM public.schema_migrations;', marker='predicate'),
    _case('force_rls_policy', "ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY; ALTER TABLE public.schema_migrations FORCE ROW LEVEL SECURITY; CREATE POLICY fixture_policy ON public.schema_migrations USING(public.probe_predicate('rls'));",
          control='SET ROLE autodata_schema_probe; SELECT * FROM public.schema_migrations;', marker='predicate'),
    _case('custom_type_output', "DROP TABLE public.schema_migrations; CREATE TABLE public.schema_migrations(version public.probe_type,applied_at timestamptz NOT NULL); INSERT INTO public.schema_migrations VALUES('001_initial',now()); ALTER TABLE public.schema_migrations OWNER TO autodata_schema_owner; GRANT SELECT,MAINTAIN ON public.schema_migrations TO autodata_schema_probe;",
          control='SELECT * FROM public.schema_migrations;', marker='output'),
    _case('domain_version_type', "CREATE DOMAIN public.fixture_domain AS text; ALTER TABLE public.schema_migrations ALTER COLUMN version TYPE public.fixture_domain;",
          cleanup='DROP DOMAIN public.fixture_domain CASCADE;'),
    _case('custom_heap_am', 'ALTER TABLE public.schema_migrations SET ACCESS METHOD probe_heap;',
          control='SELECT * FROM public.schema_migrations;', marker='heap'),
    _case('custom_index_am', 'CREATE INDEX fixture ON public.schema_migrations USING probe_btree(version);',
          control='SELECT * FROM public.schema_migrations;', marker='btree'),
    _case('expression_index', "CREATE INDEX fixture ON public.schema_migrations((public.probe_text('constant')));",
          control='SELECT * FROM public.schema_migrations;', marker='expression'),
    _case('predicate_index', "CREATE INDEX fixture ON public.schema_migrations(version) WHERE public.probe_predicate('constant');",
          control='SELECT * FROM public.schema_migrations;', marker='predicate'),
    _case('custom_opclass_support_function', 'CREATE INDEX fixture ON public.schema_migrations(version public.probe_text_ops);',
          control="ALTER TABLE public.schema_migrations DROP CONSTRAINT schema_migrations_pkey; SET enable_seqscan=off; SELECT version FROM public.schema_migrations WHERE version>'000_a';", marker='compare'),
    _case('custom_operator_family', "CREATE FUNCTION public.fixture_op(text,text) RETURNS boolean LANGUAGE sql IMMUTABLE AS 'SELECT public.probe_predicate($1)'; CREATE OPERATOR public.#< (LEFTARG=text,RIGHTARG=text,FUNCTION=public.fixture_op); CREATE OPERATOR CLASS public.fixture_opclass FOR TYPE text USING btree AS OPERATOR 1 public.#<(text,text), OPERATOR 2 pg_catalog.<=(text,text), OPERATOR 3 pg_catalog.=(text,text), OPERATOR 4 pg_catalog.>=(text,text), OPERATOR 5 pg_catalog.>(text,text), FUNCTION 1 pg_catalog.bttextcmp(text,text); CREATE INDEX fixture ON public.schema_migrations(version public.fixture_opclass);",
          cleanup='DROP OPERATOR CLASS public.fixture_opclass USING btree CASCADE; DROP OPERATOR FAMILY IF EXISTS public.fixture_opclass USING btree CASCADE; DROP OPERATOR public.#<(text,text); DROP FUNCTION public.fixture_op(text,text);',
          control="SELECT 'a'::text OPERATOR(public.#<) 'b'::text;", marker='predicate'),
    _case('custom_collation', "CREATE COLLATION public.fixture_collation(provider=libc,locale='C'); ALTER TABLE public.schema_migrations ALTER COLUMN version TYPE text COLLATE public.fixture_collation;",
          cleanup='DROP COLLATION public.fixture_collation CASCADE;'),
    _case('nondeterministic_collation', "CREATE COLLATION public.fixture_nondeterministic(provider=icu,locale='und',deterministic=false); ALTER TABLE public.schema_migrations ALTER COLUMN version TYPE text COLLATE public.fixture_nondeterministic;",
          cleanup='DROP COLLATION public.fixture_nondeterministic CASCADE;'),
    _case('invalid_concurrent_index', "CREATE UNIQUE INDEX CONCURRENTLY fixture_invalid ON public.schema_migrations((pg_catalog.left(version,1)));", setup_success=False),
    _case('unlogged_ledger', 'ALTER TABLE public.schema_migrations SET UNLOGGED;'),
    _case('exclusion_index', 'ALTER TABLE public.schema_migrations ADD CONSTRAINT fixture_exclusion EXCLUDE USING btree(version WITH =);'),
    _case('extra_index', 'CREATE INDEX fixture ON public.schema_migrations(applied_at);'),
    _case('include_index', 'CREATE INDEX fixture ON public.schema_migrations(version) INCLUDE(applied_at);'),
    _case('non_immediate_primary_key', 'ALTER TABLE public.schema_migrations DROP CONSTRAINT schema_migrations_pkey; ALTER TABLE public.schema_migrations ADD PRIMARY KEY(version) DEFERRABLE INITIALLY DEFERRED;'),
    _case('partitioned_ledger', "DROP TABLE public.schema_migrations; CREATE TABLE public.schema_migrations(version text PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now()) PARTITION BY RANGE(version); CREATE TABLE public.fixture_partition PARTITION OF public.schema_migrations DEFAULT; ALTER TABLE public.schema_migrations OWNER TO autodata_schema_owner; GRANT SELECT,MAINTAIN ON public.schema_migrations TO autodata_schema_probe;"),
    _case('inherited_ledger', 'CREATE TABLE public.fixture_child () INHERITS(public.schema_migrations);', cleanup='DROP TABLE public.fixture_child;'),
    _case('version_nullable', 'ALTER TABLE public.schema_migrations DROP CONSTRAINT schema_migrations_pkey; ALTER TABLE public.schema_migrations ALTER COLUMN version DROP NOT NULL;'),
    _case('applied_at_nullable', 'ALTER TABLE public.schema_migrations ALTER COLUMN applied_at DROP NOT NULL;'),
    _case('version_varchar', 'ALTER TABLE public.schema_migrations ALTER COLUMN version TYPE varchar(128);'),
    _case('applied_at_date', 'ALTER TABLE public.schema_migrations ALTER COLUMN applied_at TYPE date;'),
    _case('missing_applied_at_column', 'ALTER TABLE public.schema_migrations DROP COLUMN applied_at;'),
    _case('extra_column', 'ALTER TABLE public.schema_migrations ADD COLUMN extra text;'),
    _case('dropped_column', 'ALTER TABLE public.schema_migrations ADD COLUMN extra text; ALTER TABLE public.schema_migrations DROP COLUMN extra;'),
    _case('reordered_columns', 'DROP TABLE public.schema_migrations; CREATE TABLE public.schema_migrations(applied_at timestamptz NOT NULL DEFAULT now(),version text PRIMARY KEY); ALTER TABLE public.schema_migrations OWNER TO autodata_schema_owner; GRANT SELECT,MAINTAIN ON public.schema_migrations TO autodata_schema_probe;'),
    _case('generated_version', "DROP TABLE public.schema_migrations; CREATE TABLE public.schema_migrations(version text GENERATED ALWAYS AS('001_initial'::text) STORED PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now()); ALTER TABLE public.schema_migrations OWNER TO autodata_schema_owner; GRANT SELECT,MAINTAIN ON public.schema_migrations TO autodata_schema_probe;"),
    _case('identity_version', 'DROP TABLE public.schema_migrations; CREATE TABLE public.schema_migrations(version bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now()); ALTER TABLE public.schema_migrations OWNER TO autodata_schema_owner; GRANT SELECT,MAINTAIN ON public.schema_migrations TO autodata_schema_probe;'),
    _case('trigger', "CREATE FUNCTION public.fixture_trigger() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN PERFORM public.probe_predicate('trigger'); RETURN NEW; END$$; CREATE TRIGGER fixture BEFORE INSERT ON public.schema_migrations FOR EACH ROW EXECUTE FUNCTION public.fixture_trigger();",
          cleanup='DROP FUNCTION public.fixture_trigger() CASCADE;', control="INSERT INTO public.schema_migrations(version) VALUES('003_extra');", marker='predicate'),
    _case('rewrite_rule', "CREATE RULE fixture_rule AS ON UPDATE TO public.schema_migrations DO ALSO SELECT public.probe_text('rule');",
          control='UPDATE public.schema_migrations SET applied_at=applied_at;', marker='expression'),
    _case('missing_ledger', 'DROP TABLE public.schema_migrations;'),
]

_RESTORE_PROBE = '''CREATE ROLE autodata_schema_probe LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 GRANT CONNECT ON DATABASE autodata TO autodata_schema_probe;
 GRANT USAGE ON SCHEMA public TO autodata_schema_probe;
 GRANT SELECT,MAINTAIN ON public.schema_migrations TO autodata_schema_probe;'''
REQUIRED_PRIVILEGES = [
    _case('missing_role', 'DROP OWNED BY autodata_schema_probe; DROP ROLE autodata_schema_probe;', cleanup=_RESTORE_PROBE),
    _case('role_cannot_login', 'ALTER ROLE autodata_schema_probe NOLOGIN;', cleanup='ALTER ROLE autodata_schema_probe LOGIN;'),
    _case('missing_ledger_select', 'REVOKE SELECT ON public.schema_migrations FROM autodata_schema_probe;'),
    _case('missing_ledger_maintain', 'REVOKE MAINTAIN ON public.schema_migrations FROM autodata_schema_probe;'),
    _case('missing_database_connect', 'REVOKE CONNECT ON DATABASE autodata FROM autodata_schema_probe;', cleanup='GRANT CONNECT ON DATABASE autodata TO autodata_schema_probe;'),
    _case('missing_schema_usage', 'REVOKE USAGE ON SCHEMA public FROM autodata_schema_probe;', cleanup='GRANT USAGE ON SCHEMA public TO autodata_schema_probe;'),
]
ROLE_AND_OWNERSHIP = [
    _case('database_owner_even_after_revoke', 'ALTER DATABASE autodata OWNER TO autodata_schema_probe; REVOKE CREATE,TEMP ON DATABASE autodata FROM autodata_schema_probe;', cleanup='ALTER DATABASE autodata OWNER TO autodata_fixture_admin;'),
    _case('schema_owner_even_after_revoke', 'ALTER SCHEMA public OWNER TO autodata_schema_probe; REVOKE CREATE ON SCHEMA public FROM autodata_schema_probe;', cleanup='ALTER SCHEMA public OWNER TO autodata_fixture_admin;'),
    _case('relation_owner', 'ALTER TABLE public.schema_migrations OWNER TO autodata_schema_probe;'),
    _case('sequence_owner', 'CREATE SEQUENCE public.fixture_sequence; ALTER SEQUENCE public.fixture_sequence OWNER TO autodata_schema_probe;', cleanup='DROP SEQUENCE public.fixture_sequence;'),
    _case('ledger_owner_login', 'ALTER ROLE autodata_schema_owner LOGIN;', cleanup='ALTER ROLE autodata_schema_owner NOLOGIN;'),
    _case('membership_without_inherit', 'CREATE ROLE fixture_power NOLOGIN; GRANT fixture_power TO autodata_schema_probe;', cleanup='REVOKE fixture_power FROM autodata_schema_probe; DROP ROLE fixture_power;'),
    _case('inherited_write_privilege', 'CREATE ROLE fixture_power NOLOGIN; ALTER ROLE autodata_schema_probe INHERIT; GRANT fixture_power TO autodata_schema_probe; GRANT UPDATE ON public.schema_migrations TO fixture_power;', cleanup='ALTER ROLE autodata_schema_probe NOINHERIT; DROP OWNED BY fixture_power; REVOKE fixture_power FROM autodata_schema_probe; DROP ROLE fixture_power;'),
]
for _name, _flag, _restore in [('superuser','SUPERUSER','NOSUPERUSER'),('createdb','CREATEDB','NOCREATEDB'),
                              ('createrole','CREATEROLE','NOCREATEROLE'),('replication','REPLICATION','NOREPLICATION'),
                              ('bypassrls','BYPASSRLS','NOBYPASSRLS'),('inherit','INHERIT','NOINHERIT')]:
    ROLE_AND_OWNERSHIP.append(_case('role_flag_' + _name, 'ALTER ROLE autodata_schema_probe ' + _flag + ';',
                                   cleanup='ALTER ROLE autodata_schema_probe ' + _restore + ';'))

EFFECTIVE_PRIVILEGES = []
for _grantee, _label in [('autodata_schema_probe','direct'),('PUBLIC','public')]:
    for _privilege in ('INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
        EFFECTIVE_PRIVILEGES.append(_case(_label + '_table_' + _privilege.lower(),
            'GRANT ' + _privilege + ' ON public.schema_migrations TO ' + _grantee + ';'))
    for _privilege in ('INSERT','UPDATE','REFERENCES'):
        EFFECTIVE_PRIVILEGES.append(_case(_label + '_column_' + _privilege.lower(),
            'GRANT ' + _privilege + '(version) ON public.schema_migrations TO ' + _grantee + ';'))
    EFFECTIVE_PRIVILEGES.extend([
        _case(_label + '_other_maintain', 'GRANT MAINTAIN ON public.other_table TO ' + _grantee + ';', cleanup='REVOKE MAINTAIN ON public.other_table FROM ' + _grantee + ';'),
        _case(_label + '_schema_create', 'GRANT CREATE ON SCHEMA public TO ' + _grantee + ';', cleanup='REVOKE CREATE ON SCHEMA public FROM ' + _grantee + ';'),
        _case(_label + '_database_create', 'GRANT CREATE ON DATABASE autodata TO ' + _grantee + ';', cleanup='REVOKE CREATE ON DATABASE autodata FROM ' + _grantee + ';'),
        _case(_label + '_database_temp', 'GRANT TEMP ON DATABASE autodata TO ' + _grantee + ';', cleanup='REVOKE TEMP ON DATABASE autodata FROM ' + _grantee + ';'),
    ])
    for _privilege in ('USAGE','UPDATE'):
        EFFECTIVE_PRIVILEGES.append(_case(_label + '_sequence_' + _privilege.lower(),
            'CREATE SEQUENCE public.fixture_sequence; GRANT ' + _privilege + ' ON SEQUENCE public.fixture_sequence TO ' + _grantee + ';',
            cleanup='DROP SEQUENCE public.fixture_sequence;'))

FORBIDDEN_OPERATIONS = [
    ('probe_insert_denied', "INSERT INTO public.schema_migrations(version) VALUES('003_extra');"),
    ('probe_update_denied', 'UPDATE public.schema_migrations SET applied_at=applied_at;'),
    ('probe_delete_denied', 'DELETE FROM public.schema_migrations;'),
    ('probe_truncate_denied', 'TRUNCATE public.schema_migrations;'),
    ('probe_other_table_sre_denied', 'BEGIN; LOCK TABLE public.other_table IN SHARE ROW EXCLUSIVE MODE;'),
]
LEDGER_CASES = [
    ('ledger_empty', (), EXPECTED), ('ledger_missing', ('001_initial',), EXPECTED),
    ('ledger_extra', (*EXPECTED,'003_extra'), EXPECTED), ('ledger_wrong_manifest', EXPECTED, ('003_other',)),
    ('ledger_value_124_bytes', ('001_'+'a'*120,), ('001_'+'a'*120,)),
    ('ledger_value_125_bytes_invalid_suffix', ('001_'+'a'*121,), EXPECTED),
    ('ledger_value_129_bytes', ('001_'+'a'*125,), EXPECTED),
    ('ledger_non_ascii', ('001_é',), EXPECTED), ('ledger_invalid_spelling', ('001_UPPER',), EXPECTED),
    ('ledger_256', tuple(f'{n:03}_entry' for n in range(256)), tuple(f'{n:03}_entry' for n in range(256))),
    ('ledger_257', tuple(f'{n:03}_entry' for n in range(257)), EXPECTED),
]
DDL_CASES = [
    ('locked_create_index', 'CREATE INDEX fixture ON public.schema_migrations(applied_at);', ''),
    ('locked_create_index_concurrently', 'CREATE INDEX CONCURRENTLY fixture ON public.schema_migrations(applied_at);', ''),
    ('locked_reindex_concurrently', 'REINDEX TABLE CONCURRENTLY public.schema_migrations;', ''),
    ('locked_alter_rls', 'ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;', ''),
    ('locked_alter_type', 'ALTER TABLE public.schema_migrations ALTER COLUMN version TYPE varchar(128);', ''),
    ('locked_rename', 'ALTER TABLE public.schema_migrations RENAME TO fixture_old;', 'DROP TABLE public.fixture_old;'),
    ('locked_drop', 'DROP TABLE public.schema_migrations;', ''),
    ('locked_drop_recreate', 'DROP TABLE public.schema_migrations; CREATE TABLE public.schema_migrations(version text PRIMARY KEY,applied_at timestamptz NOT NULL);', ''),
    ('locked_insert', "INSERT INTO public.schema_migrations(version) VALUES('003_extra');", ''),
]
QUEUED_DDL_CASES = [
    ('queued_create_index', 'CREATE INDEX fixture ON public.schema_migrations(applied_at);'),
    ('queued_create_index_concurrently', 'CREATE INDEX CONCURRENTLY fixture ON public.schema_migrations(applied_at);'),
    ('queued_reindex_concurrently', 'REINDEX TABLE CONCURRENTLY public.schema_migrations;'),
    ('queued_ledger_insert', "INSERT INTO public.schema_migrations(version) VALUES('003_extra');"),
]
PRELOCK_CASES = [
    ('snapshot_after_index_commit', 'CREATE INDEX fixture ON public.schema_migrations(applied_at);', True),
    ('snapshot_after_type_commit', 'ALTER TABLE public.schema_migrations ALTER COLUMN version TYPE varchar(128);', True),
    ('snapshot_after_rls_commit', 'ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;', True),
    ('snapshot_after_writer_commit', "INSERT INTO public.schema_migrations(version) VALUES('003_extra');", False),
]
FRAME_FAULTS = [
    ('frame_invalid_json', lambda value: b'{bad}\n'), ('frame_unknown_protocol', lambda value: json.dumps({**json.loads(value), 'protocol_version': 1}).encode()+b'\n'),
    ('frame_capture_overflow', lambda value: b' '*524289), ('frame_truncated', lambda value: value[:-1]),
    ('frame_second_row', lambda value: value+b'{}\n'), ('frame_invalid_utf8', lambda value: b'\xff\n'),
    ('frame_excessive_depth', lambda value: b'['*9+b']'*9+b'\n'),
]
LEDGER_FRAME_FAULTS = (
    'ledger_frame_count_bool','ledger_frame_overflow','ledger_frame_invalid',
    'ledger_frame_reordered','ledger_frame_truncated','ledger_frame_capture_overflow',
    'ledger_frame_second_row','ledger_frame_missing_values')
FINALIZE_FAULTS = ('terminal_marker_wrong','frontend_killed_before_clean_exit','finish_write_failure')
CLIENT_FAULTS = ('client_killed_after_lock','client_killed_after_catalog','partial_write_after_lock',
                 'stdin_pipe_closed_after_lock','server_terminated_after_catalog','stdout_eof_after_catalog',
                 'transport_deadline_after_catalog')
REQUIRED_RUNTIME_CASES = frozenset(
    [case['case'] for table in (HOSTILE_RELATIONS, REQUIRED_PRIVILEGES, ROLE_AND_OWNERSHIP, EFFECTIVE_PRIVILEGES) for case in table]
    + [case[0] for table in (FORBIDDEN_OPERATIONS, LEDGER_CASES, DDL_CASES, QUEUED_DDL_CASES, PRELOCK_CASES, FRAME_FAULTS) for case in table]
    + list(CLIENT_FAULTS) + list(LEDGER_FRAME_FAULTS) + list(FINALIZE_FAULTS)
    + ['safe_ledger','maintain_sre_read_only_non_owner','select_only_sre_denied',
       'duplicate_rows_without_primary_key','safe_oid_replacement_before_lock',
       'server_statement_timeout','server_query_cancelled','probe_lock_timeout',
       'idle_cleanup_after_lock','idle_cleanup_after_catalog','closed_connection_reuse_rejected',
       'containerless_wrong_socket_role_identity','containerless_wrong_database_identity'])


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
        for name in ('schema_probe.py', 'test_schema_probe_pg17.py', 'testdata/schema_probe_sentinel.c', 'testdata/schema_probe_fixtures.sql'):
            hashes[name] = hashlib.sha256((HERE / name).read_bytes()).hexdigest()
        return tools, include, compiler, version, hashes
    except (OSError, ValueError, subprocess.SubprocessError, UnicodeError):
        receipt('blocked_prerequisite', reason=reason, runtime_verified=False)
        raise RuntimeError('PG17 fixture prerequisite unavailable: ' + reason) from None


class PsqlTransport:
    """A single bounded fixture-owned process. No arbitrary server endpoints."""
    def __init__(self, fixture, role='autodata_schema_probe', *, administrator=False):
        self.deadline = time.monotonic() + 12
        self.buffer = bytearray()
        self.writes = []
        self.fixture = fixture
        if administrator and role != ADMIN: raise RuntimeError('invalid fixture administrator identity')
        options = '-c statement_timeout=4000 -c lock_timeout=1000 -c search_path=pg_catalog' if administrator else probe.PGOPTIONS
        self.proc = subprocess.Popen(fixture.argv(role), env={**fixture.env, 'PGOPTIONS': options,
                                    'PGAPPNAME': 'autodata_ddl_fixture' if administrator else 'autodata_probe_fixture'}, cwd=fixture.root,
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
        # Restore global fixture authority so a previous privilege adversary
        # cannot make later catalog cases pass merely through an auth failure.
        self.admin("""ALTER DATABASE autodata OWNER TO autodata_fixture_admin;
 ALTER SCHEMA public OWNER TO autodata_fixture_admin;
 ALTER ROLE autodata_schema_probe LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 REVOKE CREATE,TEMP ON DATABASE autodata FROM PUBLIC,autodata_schema_probe,autodata_metrics;
 GRANT CONNECT ON DATABASE autodata TO autodata_schema_probe,autodata_metrics;
 REVOKE ALL ON SCHEMA public FROM PUBLIC;
 REVOKE CREATE ON SCHEMA public FROM autodata_schema_probe,autodata_metrics;
 GRANT USAGE ON SCHEMA public TO autodata_schema_probe,autodata_metrics,autodata_schema_owner;
 REVOKE ALL ON public.other_table FROM PUBLIC,autodata_schema_probe;
 DO $f$ DECLARE k text; BEGIN
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

    def marker_count(self, offset, kind=None):
        with self.log.open('rb') as stream:
            stream.seek(offset)
            data = stream.read(1048577)
            if len(data) > 1048576: raise RuntimeError('fixture log observation limit')
            marker = b'AUTODATA_PROBE_SENTINEL:' + (kind.encode('ascii') if kind else b'')
            return data.count(marker)

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

    def wait_catalog(self, sql, expected=b'1', seconds=0.7):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.admin(sql).strip() == expected:
                return
            time.sleep(0.01)
        raise RuntimeError('fixture catalog barrier unavailable')

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

    def test_startup_receipt_failure_stops_once_and_preserves_primary_error(self):
        from types import SimpleNamespace
        for stop_fails in (False, True):
            with self.subTest(stop_fails=stop_fails), tempfile.TemporaryDirectory(prefix='ad-probe-setup-') as temporary:
                root = Path(temporary)
                owned = root / 'owned_fixture'
                owned.mkdir()
                module = owned / 'sentinel.so'
                module.write_bytes(b'controlled local fixture module')
                calls = []
                primary = OSError('injected startup receipt failure')
                def stop():
                    calls.append('stop')
                    shutil.rmtree(owned)
                    if stop_fails: raise RuntimeError('secondary shutdown failure')
                fixture = SimpleNamespace(module=module, stop=stop)
                class StartupCase(unittest.TestCase):
                    setUpClass = classmethod(Pg17Acceptance.setUpClass.__func__)
                    @classmethod
                    def tearDownClass(cls): calls.append('tearDownClass')
                    def test_body(self): calls.append('body')
                class CaptureResult(unittest.TestResult):
                    def addError(self, test, error):
                        self.primary = error[1]
                        super().addError(test, error)
                result = CaptureResult()
                with patch(__name__ + '.toolchain', return_value=({}, None, None, '17.controlled', {})), \
                     patch(__name__ + '.LocalFixture', return_value=fixture), \
                     patch(__name__ + '.receipt', side_effect=primary):
                    unittest.TestSuite([StartupCase('test_body')]).run(result)
                self.assertEqual(len(result.errors), 1)
                self.assertIs(result.primary, primary)
                self.assertEqual(calls, ['stop'])
                self.assertFalse(owned.exists())

    def test_class_cleanup_always_stops_and_preserves_primary_failure(self):
        from types import SimpleNamespace
        for clean_fails, stop_fails, receipt_fails in ((True, False, False), (True, True, False),
                                                      (True, True, True), (False, True, False)):
            with self.subTest(clean=clean_fails, stop=stop_fails, receipt=receipt_fails):
                clean_error = RuntimeError('primary cleanup failure')
                stop_error = RuntimeError('shutdown failure')
                calls = []
                def clean():
                    calls.append('clean')
                    if clean_fails: raise clean_error
                def stop():
                    calls.append('stop')
                    if stop_fails: raise stop_error
                owner = SimpleNamespace(fixture=SimpleNamespace(clean_sessions=clean, stop=stop), cases=[])
                with patch(__name__ + '.receipt', side_effect=RuntimeError('receipt failure') if receipt_fails else None):
                    with self.assertRaises(RuntimeError) as caught:
                        Pg17Acceptance.tearDownClass.__func__(owner)
                self.assertEqual(calls, ['clean', 'stop'])
                self.assertIs(caught.exception, clean_error if clean_fails else stop_error)

    def test_missing_runtime_case_fails_after_owned_server_shutdown(self):
        from types import SimpleNamespace
        calls = []
        owner = SimpleNamespace(fixture=SimpleNamespace(
            clean_sessions=lambda: calls.append('clean'),
            stop=lambda: calls.append('stop')), cases=[])
        with patch(__name__ + '.receipt') as emit:
            with self.assertRaisesRegex(AssertionError, 'PG17 runtime matrix incomplete'):
                Pg17Acceptance.tearDownClass.__func__(owner)
        self.assertEqual(calls, ['clean', 'stop'])
        details = emit.call_args.kwargs
        self.assertFalse(details['matrix_complete'])
        self.assertFalse(details['runtime_verified'])
        self.assertEqual(set(details['missing_cases']), REQUIRED_RUNTIME_CASES)
        self.assertEqual(details['passed_cases'], [])

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
        try:
            receipt('fixture_started', server_version=version, tool_source_hashes=hashes, runtime_verified=False,
                    module_sha256=hashlib.sha256(cls.fixture.module.read_bytes()).hexdigest())
        except BaseException:
            # unittest skips tearDownClass when setUpClass fails. Everything
            # after successful construction must therefore guard the owned
            # server, including module hashing and receipt creation/write.
            try:
                cls.fixture.stop()
            except BaseException:
                pass  # Preserve the original setup error if shutdown also fails.
            raise

    @classmethod
    def tearDownClass(cls):
        primary = None
        try:
            cls.fixture.clean_sessions()
        except BaseException as error:
            primary = error
        finally:
            # A failed session/lock observation must not leave the owned server
            # running. Shutdown is attempted even when that observation raises.
            try:
                cls.fixture.stop()
            except BaseException as error:
                if primary is None:
                    primary = error
        if primary is not None:
            try:
                receipt('cleanup_failed', runtime_verified=False)
            except BaseException:
                pass  # Evidence I/O must not replace the original cleanup error.
            raise primary
        missing = sorted(REQUIRED_RUNTIME_CASES.difference(cls.cases))
        receipt('fixture_stopped', passed_cases=sorted(cls.cases), missing_cases=missing,
                runtime_verified=False, matrix_complete=not missing,
                qualification='Execution still requires independent evidence review; production authority remains false.')
        if missing:
            raise AssertionError('PG17 runtime matrix incomplete: ' + ','.join(missing))

    def setUp(self):
        self.fixture.reset()

    def tearDown(self):
        for client in self.fixture.clients: client.abort()
        self.fixture.clean_sessions()

    def passed(self, case, **details):
        self.assertNotIn(case, self.cases)
        self.cases.append(case)
        receipt('case_passed', case=case, runtime_verified=False, **details)

    def observe(self, expected=EXPECTED, transport=None):
        return probe.observe_catalog_ledger(transport or PsqlTransport(self.fixture), expected)

    def rejected(self, role='autodata_schema_probe', transport=None):
        offset = self.fixture.log.stat().st_size
        transport = transport or PsqlTransport(self.fixture, role)
        with self.assertRaises(probe.ProbeUnavailable): self.observe(transport=transport)
        self.assertNotIn(hashlib.sha256(probe.LEDGER_SQL).hexdigest(), transport.writes)
        self.assertEqual(self.fixture.marker_count(offset), 0)
        self.fixture.clean_sessions()
        return {'sql_sha256_order': transport.writes, 'sentinel_offset': offset, 'sentinel_count': 0,
                'backend_and_lock_cleanup': True}

    def hostile_case(self, case, setup, cleanup='', control=None, marker=None, control_success=True,
                     setup_success=True):
        with self.subTest(case=case):
            self.fixture.reset()
            self.assertTrue(self.observe()['ledger_matches'], 'invalid clean fixture control')
            evidence = {}
            try:
                self.fixture.admin(setup, success=setup_success)
                evidence = {}
                if control is not None:
                    offset = self.fixture.log.stat().st_size
                    self.fixture.admin(control, success=control_success)
                    count = self.fixture.marker_count(offset, marker)
                    self.assertGreater(count, 0, 'invalid sentinel positive control')
                    evidence.update(control_offset=offset, control_marker=marker, control_count=count)
                evidence.update(self.rejected())
            finally:
                for client in self.fixture.clients: client.abort()
                if cleanup: self.fixture.admin(cleanup)
            self.passed(case, **evidence)

    def test_safe_ledger_and_effective_probe_authority(self):
        self.assertEqual(self.observe(), {'protocol_version': 3, 'scope': 'disposable_schema_ledger',
                         'ledger_matches': True, 'schema_attested': False,
                         'production_ready': False, 'deployment_authorized': False})
        self.passed('safe_ledger')
        t = PsqlTransport(self.fixture)
        t.send(probe.BEGIN_SQL); self.fixture.wait_lock()
        t.send(probe.CATALOG_SQL)
        facts = probe._decode(t.read_frame(524288, time.monotonic() + 3))
        probe.validate_catalog(facts)
        self.assertFalse(facts['rights']['relation_owner'])
        self.assertEqual(facts['rights']['membership_count'], 0)
        self.assertTrue(facts['identity']['transaction_read_only'])
        self.assertTrue(facts['rights']['ledger_maintain'])
        t.send(probe.FINISH_SQL); t.close()
        self.passed('maintain_sre_read_only_non_owner')
        t = PsqlTransport(self.fixture, 'autodata_metrics')
        t.send(probe.BEGIN_SQL + probe.CATALOG_SQL)
        with self.assertRaises(probe.ProbeUnavailable): t.read_frame(524288, time.monotonic() + 3)
        t.abort()
        self.passed('select_only_sre_denied')
        for name, statement in FORBIDDEN_OPERATIONS:
            with self.subTest(case=name):
                self.fixture.admin('SET ROLE autodata_schema_probe; ' + statement, success=False)
                self.assertTrue(self.observe()['ledger_matches'])
                self.passed(name)

    def test_hostile_relation_and_execution_matrix(self):
        for case in HOSTILE_RELATIONS:
            self.hostile_case(**case)

    def test_missing_role_and_required_privileges(self):
        for case in REQUIRED_PRIVILEGES:
            self.hostile_case(**case)

    def test_role_flags_membership_and_object_ownership(self):
        for case in ROLE_AND_OWNERSHIP:
            self.hostile_case(**case)

    def test_effective_public_table_column_sequence_privileges(self):
        for case in EFFECTIVE_PRIVILEGES:
            self.hostile_case(**case)

    def test_bounded_ledger_value_matrix(self):
        for case, versions, expected in LEDGER_CASES:
            with self.subTest(case=case):
                self.fixture.reset()
                self.fixture.admin('TRUNCATE public.schema_migrations;')
                if versions:
                    # Values are fixture-owned literals, never user inputs.
                    values = ','.join("('" + value.replace("'", "''") + "')" for value in versions)
                    self.fixture.admin('INSERT INTO public.schema_migrations(version) VALUES ' + values + ';')
                offset = self.fixture.log.stat().st_size
                transport = PsqlTransport(self.fixture)
                if case in ('ledger_256', 'ledger_value_124_bytes'):
                    self.assertTrue(self.observe(expected, transport)['ledger_matches'])
                else:
                    with self.assertRaises(probe.ProbeUnavailable): self.observe(expected, transport)
                self.assertIn(hashlib.sha256(probe.LEDGER_SQL).hexdigest(), transport.writes)
                self.assertEqual(self.fixture.marker_count(offset), 0)
                self.fixture.clean_sessions()
                self.passed(case, sql_sha256_order=transport.writes, sentinel_count=0)
        # A duplicate is impossible in the accepted primary-key shape. Removing
        # that constraint permits a duplicate fixture but must fail catalog phase.
        self.hostile_case('duplicate_rows_without_primary_key',
            "ALTER TABLE public.schema_migrations DROP CONSTRAINT schema_migrations_pkey; "
            "INSERT INTO public.schema_migrations(version) VALUES('001_initial');")

    def test_concurrent_ddl_lock_timeout_and_completion(self):
        for case, statement, cleanup in DDL_CASES:
            with self.subTest(case=case):
                self.fixture.reset()
                t = PsqlTransport(self.fixture); t.send(probe.BEGIN_SQL); self.fixture.wait_lock()
                started = time.monotonic()
                self.fixture.admin("SET lock_timeout='1s'; " + statement, success=False)
                self.assertLess(time.monotonic() - started, 4)
                self.fixture.wait_lock()  # observer still owns its strong lock
                t.send(probe.FINISH_SQL); t.close()
                # Concurrent CREATE INDEX can leave an invalid index after its
                # timeout. Remove that test-owned remnant before retrying.
                if 'CREATE INDEX' in statement: self.fixture.admin('DROP INDEX IF EXISTS public.fixture;')
                self.fixture.admin(statement)
                if cleanup: self.fixture.admin(cleanup)
                self.passed(case, held_lock_barrier=True, denied_while_locked=True,
                            completed_after_rollback=True)

    def test_queued_ddl_completes_only_after_rollback(self):
        for case, statement in QUEUED_DDL_CASES:
            with self.subTest(case=case):
                self.fixture.reset()
                t = PsqlTransport(self.fixture); t.send(probe.BEGIN_SQL); self.fixture.wait_lock()
                waiter = PsqlTransport(self.fixture, ADMIN, administrator=True)
                try:
                    waiter.send(statement.encode() + b'\n\\echo DDL_COMPLETED\n')
                    self.fixture.wait_catalog("SELECT count(*) FROM pg_catalog.pg_locks l JOIN pg_catalog.pg_stat_activity a ON a.pid=l.pid WHERE a.application_name='autodata_ddl_fixture' AND NOT l.granted;")
                    self.assertIsNone(waiter.proc.poll())
                    t.send(probe.FINISH_SQL); t.close()
                    self.assertEqual(waiter.read_frame(64, time.monotonic() + 2), b'DDL_COMPLETED\n')
                    waiter.send(probe.FINISH_SQL); waiter.close()
                    self.passed(case, waiting_lock_barrier=True, completed_after_rollback=True)
                finally:
                    waiter.abort(); t.abort()

    def test_first_snapshot_follows_committed_index_type_rls_or_write(self):
        for case, ddl, should_reject_catalog in PRELOCK_CASES:
            with self.subTest(case=case):
                self.fixture.reset()
                owner = PsqlTransport(self.fixture, ADMIN, administrator=True)
                t = PsqlTransport(self.fixture)
                try:
                    owner.send(('BEGIN; ' + ddl + '\n\\echo HELD\n').encode())
                    self.assertEqual(owner.read_frame(64, time.monotonic() + 2), b'HELD\n')
                    t.send(probe.BEGIN_SQL)
                    self.fixture.wait_catalog("SELECT count(*) FROM pg_catalog.pg_locks l JOIN pg_catalog.pg_stat_activity a ON a.pid=l.pid WHERE a.usename='autodata_schema_probe' AND NOT l.granted;")
                    owner.send(b'COMMIT;\n\\echo AUTODATA_SCHEMA_PROBE_CLOSED_V3\n\\quit\n'); owner.close()
                    t.send(probe.CATALOG_SQL)
                    facts = probe._decode(t.read_frame(524288, time.monotonic() + 3))
                    if should_reject_catalog:
                        with self.assertRaises(probe.ProbeUnavailable): probe.validate_catalog(facts)
                        self.assertNotIn(hashlib.sha256(probe.LEDGER_SQL).hexdigest(), t.writes)
                    else:
                        probe.validate_catalog(facts)
                        t.send(probe.LEDGER_SQL)
                        rows = probe._decode(t.read_frame(524288, time.monotonic() + 3))
                        self.assertEqual(rows['count'], 3)
                        self.assertEqual(rows['migrations'], ['001_initial', '002_accounts', '003_extra'])
                    t.send(probe.FINISH_SQL); t.close()
                    self.passed(case, waited_before_snapshot=True, observed_committed_change=True)
                finally:
                    owner.abort(); t.abort()

    def test_new_safe_relation_oid_before_lock(self):
        old = self.fixture.admin("SELECT 'public.schema_migrations'::regclass::oid;").strip()
        self.fixture.reset()
        new = self.fixture.admin("SELECT 'public.schema_migrations'::regclass::oid;").strip()
        self.assertNotEqual(old, new)
        self.assertTrue(self.observe()['ledger_matches'])
        self.passed('safe_oid_replacement_before_lock')

    def test_malformed_frames_under_actual_held_transaction(self):
        for case, corrupt in FRAME_FAULTS:
            with self.subTest(case=case):
                t = PsqlTransport(self.fixture)
                class CorruptFrame:
                    def send(self, data): return t.send(data)
                    def read_frame(self, maximum, deadline):
                        actual = t.read_frame(maximum, deadline)
                        return corrupt(actual)
                    def abort(self): return t.abort()
                    def close(self): return t.close()
                with self.assertRaises(probe.ProbeUnavailable): self.observe(transport=CorruptFrame())
                self.assertNotIn(hashlib.sha256(probe.LEDGER_SQL).hexdigest(), t.writes)
                self.fixture.clean_sessions()
                self.passed(case, backend_and_lock_cleanup=True)

    def test_ledger_frame_failures_after_valid_catalog(self):
        for case in LEDGER_FRAME_FAULTS:
            with self.subTest(case=case):
                t = PsqlTransport(self.fixture)
                class CorruptLedger:
                    reads = 0
                    def send(self, data): return t.send(data)
                    def read_frame(self, maximum, deadline):
                        actual = t.read_frame(maximum, deadline)
                        self.reads += 1
                        if self.reads == 1: return actual
                        if case == 'ledger_frame_truncated': return actual[:-1]
                        if case == 'ledger_frame_capture_overflow': return b' ' * 524289
                        if case == 'ledger_frame_second_row': return actual + b'{}\n'
                        value = json.loads(actual)
                        if case == 'ledger_frame_count_bool': value['count'] = True
                        elif case == 'ledger_frame_overflow': value['overflow'] = True
                        elif case == 'ledger_frame_invalid': value['invalid'] = True
                        elif case == 'ledger_frame_reordered': value['migrations'].reverse()
                        elif case == 'ledger_frame_missing_values': del value['migrations']
                        return json.dumps(value).encode() + b'\n'
                    def close(self): return t.close()
                    def abort(self): return t.abort()
                with self.assertRaises(probe.ProbeUnavailable): self.observe(transport=CorruptLedger())
                self.assertEqual(t.writes.count(hashlib.sha256(probe.LEDGER_SQL).hexdigest()), 1)
                self.fixture.clean_sessions()
                self.passed(case, backend_and_lock_cleanup=True)

    def test_terminal_and_exit_failures_cannot_emit_success(self):
        for case in FINALIZE_FAULTS:
            with self.subTest(case=case):
                t = PsqlTransport(self.fixture)
                class FinalizeFault:
                    def send(self, data):
                        if data == probe.FINISH_SQL and case == 'terminal_marker_wrong':
                            return t.send(b'ROLLBACK;\n\\echo WRONG_MARKER\n\\quit\n')
                        if data == probe.FINISH_SQL and case == 'frontend_killed_before_clean_exit':
                            return t.send(probe.ROLLBACK_SQL + b'\\echo AUTODATA_SCHEMA_PROBE_CLOSED_V3\n')
                        if data == probe.FINISH_SQL and case == 'finish_write_failure':
                            t.send(probe.ROLLBACK_SQL)
                            raise BrokenPipeError()
                        return t.send(data)
                    def read_frame(self, maximum, deadline): return t.read_frame(maximum, deadline)
                    def close(self):
                        if case == 'frontend_killed_before_clean_exit':
                            # Hold frontend alive until this injected exit fault,
                            # rather than racing a naturally completed psql exit.
                            if t.read_frame(524288, time.monotonic() + 1) != probe.TERMINAL:
                                raise probe.ProbeUnavailable()
                            t.proc.kill(); t.proc.wait(timeout=1)
                            raise OSError('injected nonzero client exit')
                        return t.close()
                    def abort(self): return t.abort()
                with self.assertRaises(probe.ProbeUnavailable): self.observe(transport=FinalizeFault())
                self.assertEqual(t.writes.count(hashlib.sha256(probe.LEDGER_SQL).hexdigest()), 1)
                self.fixture.clean_sessions()
                self.passed(case, backend_and_lock_cleanup=True)

    def test_client_faults_before_and_after_catalog(self):
        for case in CLIENT_FAULTS:
            with self.subTest(case=case):
                t = PsqlTransport(self.fixture)
                fixture = self.fixture
                class FaultClient:
                    def send(self, data):
                        if data == probe.CATALOG_SQL and case == 'client_killed_after_lock':
                            fixture.wait_lock(); t.proc.kill(); t.proc.wait(timeout=1)
                            raise BrokenPipeError()
                        if data == probe.CATALOG_SQL and case == 'partial_write_after_lock':
                            fixture.wait_lock(); t.send(data[:32]); raise BrokenPipeError()
                        if data == probe.CATALOG_SQL and case == 'stdin_pipe_closed_after_lock':
                            fixture.wait_lock(); t.proc.stdin.close(); raise BrokenPipeError()
                        return t.send(data)
                    def read_frame(self, maximum, deadline):
                        value = t.read_frame(maximum, deadline)
                        if case == 'client_killed_after_catalog':
                            t.proc.kill(); t.proc.wait(timeout=1)
                        elif case == 'server_terminated_after_catalog':
                            fixture.admin("SELECT pg_catalog.pg_terminate_backend(pid) FROM pg_catalog.pg_stat_activity WHERE usename='autodata_schema_probe';")
                            t.proc.wait(timeout=2)
                        elif case == 'stdout_eof_after_catalog':
                            t.proc.stdout.close(); raise EOFError()
                        elif case == 'transport_deadline_after_catalog':
                            raise TimeoutError()
                        return value
                    def close(self): return t.close()
                    def abort(self): return t.abort()
                with self.assertRaises(probe.ProbeUnavailable): self.observe(transport=FaultClient())
                self.assertNotIn(hashlib.sha256(probe.LEDGER_SQL).hexdigest(), t.writes)
                self.fixture.clean_sessions()
                self.passed(case, backend_and_lock_cleanup=True)

    def test_statement_cancellation_timeout_and_lock_timeout(self):
        for case in ('server_statement_timeout', 'server_query_cancelled'):
            with self.subTest(case=case):
                t = PsqlTransport(self.fixture)
                fixture = self.fixture
                class SlowCatalog:
                    def send(self, data):
                        if data == probe.CATALOG_SQL:
                            t.send(b'SELECT pg_catalog.pg_sleep(5);\n')
                            if case == 'server_query_cancelled':
                                fixture.wait_catalog("SELECT count(*) FROM pg_catalog.pg_stat_activity WHERE usename='autodata_schema_probe' AND state='active' AND wait_event='PgSleep';")
                                fixture.admin("SELECT pg_catalog.pg_cancel_backend(pid) FROM pg_catalog.pg_stat_activity WHERE usename='autodata_schema_probe';")
                            return
                        return t.send(data)
                    def read_frame(self, maximum, deadline): return t.read_frame(maximum, deadline)
                    def close(self): return t.close()
                    def abort(self): return t.abort()
                with self.assertRaises(probe.ProbeUnavailable): self.observe(transport=SlowCatalog())
                self.assertNotIn(hashlib.sha256(probe.LEDGER_SQL).hexdigest(), t.writes)
                self.fixture.clean_sessions()
                self.passed(case, backend_and_lock_cleanup=True)
        owner = PsqlTransport(self.fixture, ADMIN, administrator=True)
        try:
            owner.send(b'BEGIN; LOCK TABLE public.schema_migrations IN ACCESS EXCLUSIVE MODE;\n\\echo HELD\n')
            self.assertEqual(owner.read_frame(64, time.monotonic() + 2), b'HELD\n')
            t = PsqlTransport(self.fixture)
            with self.assertRaises(probe.ProbeUnavailable): self.observe(transport=t)
            self.assertNotIn(hashlib.sha256(probe.LEDGER_SQL).hexdigest(), t.writes)
            self.fixture.clean_sessions()
            self.passed('probe_lock_timeout', backend_and_lock_cleanup=True)
        finally:
            owner.abort()

    def test_abandoned_live_frontend_uses_server_idle_cleanup(self):
        for case, after_catalog in (('idle_cleanup_after_lock', False), ('idle_cleanup_after_catalog', True)):
            with self.subTest(case=case):
                t = PsqlTransport(self.fixture); t.send(probe.BEGIN_SQL); self.fixture.wait_lock()
                if after_catalog:
                    t.send(probe.CATALOG_SQL)
                    probe.validate_catalog(probe._decode(t.read_frame(524288, time.monotonic() + 3)))
                self.assertIsNone(t.proc.poll())
                self.fixture.clean_sessions()
                self.assertNotIn(hashlib.sha256(probe.LEDGER_SQL).hexdigest(), t.writes)
                t.abort()
                self.passed(case, backend_and_lock_cleanup=True, frontend_was_left_alive=True)

    def test_connection_reuse_and_wrong_identity_cannot_succeed(self):
        t = PsqlTransport(self.fixture)
        self.assertTrue(self.observe(transport=t)['ledger_matches'])
        with self.assertRaises(probe.ProbeUnavailable): self.observe(transport=t)
        self.assertEqual(t.writes.count(hashlib.sha256(probe.LEDGER_SQL).hexdigest()), 1)
        self.passed('closed_connection_reuse_rejected')
        self.fixture.admin('GRANT MAINTAIN ON public.schema_migrations TO autodata_metrics;')
        try:
            evidence = self.rejected(role='autodata_metrics')
            self.passed('containerless_wrong_socket_role_identity', **evidence)
        finally:
            self.fixture.admin('REVOKE MAINTAIN ON public.schema_migrations FROM autodata_metrics;')
        self.fixture.admin('CREATE TABLE public.schema_migrations(version text PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now()); ALTER TABLE public.schema_migrations OWNER TO autodata_schema_owner; GRANT SELECT,MAINTAIN ON public.schema_migrations TO autodata_schema_probe;', database='postgres')
        try:
            fixture = self.fixture
            class OtherDatabase:
                root = fixture.root
                env = fixture.env
                clients = fixture.clients
                def argv(self, role): return fixture.argv(role, database='postgres')
            evidence = self.rejected(transport=PsqlTransport(OtherDatabase()))
            self.passed('containerless_wrong_database_identity', **evidence)
        finally:
            self.fixture.admin('DROP TABLE public.schema_migrations;', database='postgres')


if __name__ == '__main__':
    unittest.main()
