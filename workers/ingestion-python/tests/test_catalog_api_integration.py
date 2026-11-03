"""Required Go -> actual R2 HTTP -> real worker acceptance, isolated by case.

The coordinator's bounded supervisor owns certification and the plain clone.
Ordinary suites may skip this module; required acceptance never skips a case.
"""
from __future__ import annotations

import asyncio
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import hashlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import io
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from urllib.parse import urlsplit, unquote
from urllib.request import Request, urlopen
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = Path('/artifacts')
GO_NAMES = (
    'TestPostgresCatalogLifecycleColdHTTPRaceOneJob',
    'TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP',
    'TestPostgresCatalogLifecycleAtomicPublication',
    'TestPostgresCatalogLifecycleWarmReadsNoExternalCalls',
)
REQUIRED = os.getenv('AUTODATA_CATALOG_INTEGRATION_REQUIRED') == '1'
if REQUIRED and os.getenv('AUTODATA_LIFECYCLE_TEST') != '1':
    raise RuntimeError('required acceptance needs explicit lifecycle fixture flag')
if not REQUIRED:
    pytestmark = pytest.mark.skip(reason='explicit required fixture acceptance only')
from lifecycle_support import fresh_database, LifecycleRuntime  # noqa: E402,F401

TABLES = ('schema_migrations', 'catalog_articles', 'canonical_articles',
          'canonical_article_source_revisions', 'canonical_article_source_observations',
          'canonical_article_revisions', 'canonical_article_reviews',
          'canonical_article_rewrite_attempts', 'source_fetch_jobs', 'publication_events',
          'source_snapshots', 'catalog_article_provider_scopes', 'catalog_article_index_pages',
          'canonical_article_aliases')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, payload):
    path.write_text(json.dumps(payload, default=str, sort_keys=True, indent=2) + '\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def bounded(argv, *, env=None, timeout=30, cwd=ROOT):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout, check=False)


def check_inputs(phase):
    manifest_bytes = (ARTIFACTS / 'inputs.sha256.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    host = json.loads((ARTIFACTS / 'host-before.json').read_bytes())
    candidate = os.environ['AUTODATA_CATALOG_TEST_CANDIDATE_SHA']
    assert re.fullmatch(r'[a-f0-9]{40}', candidate)
    assert manifest['schema_version'] == 1
    assert manifest['candidate_sha'] == host['candidate_sha'] == candidate
    assert manifest['candidate_origin'] == 'coordinator-host-plain-clone'
    assert host['input_manifest_sha256'] == digest(manifest_bytes)
    assert host['git_status_porcelain'] == '' and host['remotes'] == []
    assert host['checkout_kind'] == 'plain-clone'
    paths = []
    for entry in manifest['files']:
        relative = entry['path']
        assert not relative.startswith('/') and '..' not in Path(relative).parts
        assert entry['git_mode'] in ('100644', '100755')
        path = ROOT / relative
        assert path.is_file() and not path.is_symlink()
        assert digest(path.read_bytes()) == entry['sha256'], relative
        assert bool(path.stat().st_mode & 0o111) == (entry['git_mode'] == '100755')
        paths.append(relative)
    assert paths == sorted(set(paths))
    actual = []
    for directory, dirs, names in os.walk(ROOT):
        if Path(directory) == ROOT:
            dirs[:] = [name for name in dirs if name != '.git']
        for name in names:
            path = Path(directory) / name
            assert path.is_file() and not path.is_symlink()
            actual.append(path.relative_to(ROOT).as_posix())
    assert sorted(actual) == paths, 'mounted checkout has missing or additional inputs'
    observation = {'schema_version': 1, 'phase': phase,
                   'origin': 'runner-filesystem-hash-comparison',
                   'input_manifest_sha256': digest(manifest_bytes),
                   'candidate_sha': candidate, 'comparison_ok': True, 'file_count': len(paths)}
    write_json(ARTIFACTS / f'runner-input-{phase}.json', observation)
    prefix = ['git', '--no-optional-locks', '-c', 'safe.directory=/workspace',
              '-c', 'core.hooksPath=/dev/null', '-C', str(ROOT)]
    observed = []
    for args in (['rev-parse', 'HEAD'], ['status', '--porcelain=v1', '--untracked-files=all'], ['remote']):
        process = bounded(prefix + args)
        assert process.returncode == 0, process.stderr.decode()
        observed.append(process.stdout.decode().strip())
    assert observed == [candidate, '', '']
    git_observation = {'schema_version': 1, 'phase': phase, 'candidate_sha': observed[0],
                       'git_status_porcelain': observed[1], 'remotes': [],
                       'origin': 'runner-git-observed'}
    write_json(ARTIFACTS / f'runner-git-{phase}.json', git_observation)
    return {'candidate_sha': candidate, 'candidate_origin': manifest['candidate_origin'],
            'host_before_sha256': digest((ARTIFACTS / 'host-before.json').read_bytes()),
            'input_manifest_sha256': digest(manifest_bytes),
            'runner_git_observation': git_observation}


def migration_env(repo):
    # Image routing and HOME remain untouched; no inherited database routing.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('PG') and key != 'DATABASE_URL'}
    env.update(PGHOST='postgres', PGPORT='5432', PGDATABASE=repo.database_name,
               PGUSER='lifecycle_test', PGPASSWORD='lifecycle_test_only',
               PGSSLMODE='disable', PGCONNECT_TIMEOUT='3')
    return env


def immutable_rows(repo):
    with repo.connect() as conn:
        return {table: [row['record'] for row in conn.execute(
            'SELECT to_jsonb(t) AS record FROM ' + table + ' t ORDER BY to_jsonb(t)::text')]
                for table in TABLES}


def rows_hash(rows):
    return digest(json.dumps(rows, default=str, sort_keys=True).encode())


def migration_snapshot(repo, env):
    rows = immutable_rows(repo)
    dump = bounded(['pg_dump', '--schema-only', '--no-owner', '--no-privileges'], env=env)
    assert dump.returncode == 0, dump.stderr.decode()
    normalized = b'\n'.join(line for line in dump.stdout.splitlines()
                             if not line.startswith((b'\\restrict ', b'\\unrestrict ')))
    return {'ledger': rows['schema_migrations'], 'rows': rows,
            'ledger_sha256': rows_hash(rows['schema_migrations']),
            'schema_sha256': digest(normalized), 'data_sha256': rows_hash(rows)}, normalized


def run_migrations(repo, directory, phase, manifest, before=None):
    env = migration_env(repo)
    command = ['sh', str(ROOT / 'scripts/dev/migrate_sql.sh')]
    process = bounded(command, env=env, timeout=90)
    (directory / f'migration-{phase}.stdout').write_bytes(process.stdout)
    (directory / f'migration-{phase}.stderr').write_bytes(process.stderr)
    applied = re.findall(r'^AUTODATA_APPLIED\s+(\S+)', process.stdout.decode(), re.M)
    skipped = re.findall(r'^AUTODATA_SKIPPED\s+(\S+)', process.stdout.decode(), re.M)
    result = {'exit_code': process.returncode, 'timed_out': False,
              'applied': applied, 'skipped': skipped}
    write_json(directory / f'migration-{phase}.json', result)
    assert process.returncode == 0, process.stdout.decode() + process.stderr.decode()
    if phase == 'fresh':
        assert applied == manifest and not skipped
    else:
        assert skipped == manifest and not applied
    after, schema = migration_snapshot(repo, env)
    assert sorted(row['version'] for row in after['ledger']) == [name[:-4] for name in manifest]
    (directory / f'migration-{phase}.schema.sql').write_bytes(schema)
    write_json(directory / f'migration-{phase}.rows.json', after['rows'])
    for kind in ('ledger', 'schema', 'data'):
        result[kind + '_after_sha256'] = after[kind + '_sha256']
        if before is not None:
            result[kind + '_before_sha256'] = before[kind + '_sha256']
            assert before[kind + '_sha256'] == after[kind + '_sha256'], phase + ':' + kind
    return result, after


@contextmanager
def serve(handler):
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
        assert not thread.is_alive()


class Bridge:
    def __init__(self, runtime, name):
        self.runtime = runtime
        self.name = name
        self.token = uuid.uuid4().hex
        self.lock = threading.Lock()
        self.release_model = threading.Event()
        if name != GO_NAMES[1]:
            self.release_model.set()
        self.proxy = dict(request_received=0, upstream_completed=0, downstream_completed=0,
                          downstream_waiting=0, response_captured=False, errors=[])
        self.ensure = dict(entered=0, completed=0, active=0)
        self.started = False
        if name == GO_NAMES[2]:
            runtime.pause('inside_publication')

    def model_handler(self):
        owner = self

        class ModelProxy(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                try:
                    assert self.path == '/v1/chat/completions'
                    length = int(self.headers.get('Content-Length', '-1'))
                    assert 0 < length <= 1048576
                    body = self.rfile.read(length)
                    with owner.lock:
                        owner.proxy['request_received'] += 1
                    request = Request(owner.runtime.model.url + '/chat/completions', data=body,
                                      headers={'Content-Type': 'application/json',
                                               'Authorization': 'Bearer fixture-model'})
                    with urlopen(request, timeout=5) as result:
                        status = result.status
                        response = result.read(1048577)
                        media = result.headers.get('Content-Type', 'application/json')
                    assert len(response) <= 1048576
                    with owner.lock:
                        owner.proxy['upstream_completed'] += 1
                        owner.proxy['response_captured'] = True
                        owner.proxy['downstream_waiting'] += 1
                    assert owner.release_model.wait(25), 'model response release deadline'
                    self.send_response(status)
                    self.send_header('Content-Type', media)
                    self.send_header('Content-Length', str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                    self.wfile.flush()
                    with owner.lock:
                        owner.proxy['downstream_waiting'] -= 1
                        owner.proxy['downstream_completed'] += 1
                except Exception as error:
                    with owner.lock:
                        owner.proxy['errors'].append(type(error).__name__ + ': ' + str(error))
                    self.send_error(502)
        return ModelProxy

    def ensure_handler(self):
        from autodata_ingestion.http_service import make_handler
        parent = make_handler(internal_token='fixture-r3-internal')
        owner = self

        class CountingHandler(parent):
            def do_POST(self):
                with owner.lock:
                    owner.ensure['entered'] += 1
                    owner.ensure['active'] += 1
                try:
                    super().do_POST()
                finally:
                    with owner.lock:
                        owner.ensure['completed'] += 1
                        owner.ensure['active'] -= 1

            def log_message(self, *args):
                pass
        return CountingHandler

    def snapshot(self):
        runtime = self.runtime
        for worker in runtime.workers:
            if hasattr(worker, 'poll'):
                assert worker.poll() is None, 'ordinary CLI worker exited early'
            elif not worker.is_alive():
                assert self.name == GO_NAMES[2] and worker.exitcode == 0, 'one-shot worker failed'
        with runtime.repo.connect() as conn:
            counts = {}
            for name, table in (('article_jobs', 'source_fetch_jobs'),
                                ('source_revisions', 'canonical_article_source_revisions'),
                                ('canonical_revisions', 'canonical_article_revisions'),
                                ('published_revisions', 'canonical_article_revisions'),
                                ('publication_events', 'publication_events'),
                                ('source_observations', 'canonical_article_source_observations')):
                where = " AND job_kind='article'" if name == 'article_jobs' else " AND status='published'" if name == 'published_revisions' else ''
                counts[name] = conn.execute('SELECT count(*) AS n FROM ' + table +
                                           ' WHERE canonical_article_id=%s' + where,
                                           (runtime.article_id,)).fetchone()['n']
        with self.lock:
            proxy = json.loads(json.dumps(self.proxy))
            ensure = dict(self.ensure)
        traces = {p: list(s.calls) for p, s in runtime.servers.items()}
        return {'counts': counts, 'ensure': ensure,
                'provider_calls': {p: len(paths) for p, paths in traces.items()},
                'provider_traces': traces,
                'source_calls': {p: sum('/resources/' in path and unquote(path.split('/resources/', 1)[1]) == 'body' for path in paths) for p, paths in traces.items()},
                'asset_calls': {p: sum('/resources/' in path and unquote(path.split('/resources/', 1)[1]) != 'body' for path in paths) for p, paths in traces.items()},
                'model_calls': runtime.model.calls, 'proxy': proxy,
                'article': runtime.read_current(), 'immutable_sha256': rows_hash(immutable_rows(runtime.repo)),
                'workers': [{'kind': 'cli' if hasattr(w, 'poll') else 'one-shot',
                             'alive': w.poll() is None if hasattr(w, 'poll') else w.is_alive(),
                             'exit_code': w.poll() if hasattr(w, 'poll') else w.exitcode}
                            for w in runtime.workers]}

    def control_handler(self):
        owner = self

        class Control(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def dispatch(self):
                try:
                    assert self.headers.get('X-R3-Fixture-Token') == owner.token
                    assert self.headers.get('Content-Length', '0') == '0'
                    path = self.path
                    if self.command == 'GET' and path in ('/r3-fixture/snapshot', '/r3-fixture/publication'):
                        result = owner.snapshot()
                    elif self.command == 'GET' and path == '/r3-fixture/model-held':
                        with owner.lock:
                            result = dict(owner.proxy)
                    elif self.command == 'GET' and path == '/r3-fixture/publication-barrier':
                        assert owner.name == GO_NAMES[2]
                        result = {'arrived': owner.runtime.barrier[1].is_set()}
                    elif self.command == 'POST' and path == '/r3-fixture/start-workers':
                        assert not owner.started
                        owner.started = True
                        owner.runtime.start_workers(1 if owner.name == GO_NAMES[2] else 2)
                        result = {'started': True}
                    elif self.command == 'POST' and path == '/r3-fixture/release-model':
                        owner.release_model.set()
                        result = {'released': True}
                    elif self.command == 'POST' and path == '/r3-fixture/release-publication':
                        assert owner.name == GO_NAMES[2]
                        owner.runtime.release('inside_publication')
                        result = {'released': True}
                    else:
                        raise AssertionError('unexpected control route')
                    body = json.dumps(result, default=str).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    self.send_error(500, 'fixture control failure')

            do_GET = dispatch
            do_POST = dispatch
        return Control

    def stop(self):
        self.release_model.set()
        if self.runtime.barrier:
            self.runtime.release('inside_publication')
        owned = list(self.runtime.workers)
        # The one-shot hook exits normally after its one committed job.
        if self.name == GO_NAMES[2] and owned:
            owned[0].join(3)
            assert owned[0].exitcode == 0 and not owned[0].is_alive()
        self.runtime.stop_workers()
        result = []
        for worker in owned:
            if hasattr(worker, 'poll'):
                assert worker.poll() is not None
                result.append({'kind': 'cli', 'exit_code': worker.returncode, 'terminated': True})
            else:
                if worker.is_alive():
                    worker.kill()
                    worker.join(3)
                assert not worker.is_alive() and worker.exitcode is not None
                result.append({'kind': 'one-shot', 'exit_code': worker.exitcode, 'terminated': True})
        return result


def probes(runtime):
    with runtime.repo.connect() as conn:
        row = conn.execute('SELECT current_database() AS database,current_user AS "user",current_setting(\'server_version_num\')::int AS server_version_num').fetchone()
        assert row['database'] == runtime.repo.database_name and row['user'] == 'lifecycle_test'
        assert 170000 <= row['server_version_num'] < 180000
    name = 'r3-probe-' + uuid.uuid4().hex
    payload = b'isolated-r3-object-roundtrip'
    runtime.objects.client.put_object(runtime.bucket, name, io.BytesIO(payload), len(payload))
    response = runtime.objects.client.get_object(runtime.bucket, name)
    try:
        assert response.read() == payload
    finally:
        response.close()
        response.release_conn()
        runtime.objects.client.remove_object(runtime.bucket, name)

    async def nats_probe():
        import nats
        client = await nats.connect('nats://nats:4222', connect_timeout=3, max_reconnect_attempts=0)
        try:
            await asyncio.wait_for(client.jetstream().account_info(), timeout=3)
        finally:
            await client.close()
    asyncio.run(asyncio.wait_for(nats_probe(), timeout=6))
    return {'postgres': row, 's3': {'bucket': runtime.bucket, 'roundtrip_ok': True},
            'nats': {'jetstream_account_info_ok': True}}


def validate_go_events(path, name):
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert events
    package = 'github.com/lucronn/autodata/apps/api-go'
    assert all(event['Package'] == package for event in events)
    assert not any(event['Action'] in ('skip', 'fail') for event in events)
    runs = [event.get('Test') for event in events if event['Action'] == 'run']
    passes = [event.get('Test') for event in events if event['Action'] == 'pass' and 'Test' in event]
    assert runs == passes == [name]
    assert events[-1]['Action'] == 'pass' and 'Test' not in events[-1]


@pytest.mark.parametrize('go_name,provider', [(name, provider) for name in GO_NAMES for provider in ('bankone', 'banktwo')], ids=[name + '-' + provider for name in GO_NAMES for provider in ('bankone', 'banktwo')])
def test_required_go_catalog_lifecycle(go_name, provider, fresh_database, monkeypatch):
    assert REQUIRED and os.environ['AUTODATA_LIFECYCLE_TEST'] == '1'
    provenance = check_inputs('before')
    directory = ARTIFACTS / 'r3' / provider / go_name
    directory.mkdir(parents=True, exist_ok=False)
    started = now()
    result = {'schema_version': 1, 'provider': provider, 'go_test_name': go_name,
              **provenance, 'started_at': started, 'go_exit_code': None, 'timed_out': False,
              'phase_snapshots': {}, 'assertion_results': {}}
    runtime = bridge = None
    try:
        repo = fresh_database(through=0)
        assert re.fullmatch(r'lifecycle_test_[a-f0-9]{32}', repo.database_name)
        result['fixture_database'] = repo.database_name
        manifest = [path.name for path in sorted((ROOT / 'db/migrations').glob('*.sql'))]
        assert len(manifest) == 38 and manifest[32] == '033_catalog_scope_coverage.sql' and manifest[-1] == '038_article_transform_publication.sql'
        emitted = bounded(['sh', str(ROOT / 'scripts/dev/migrate_sql.sh'), '--emit'], timeout=30)
        (directory / 'migration-driver.sql').write_bytes(emitted.stdout)
        (directory / 'migration-driver.stderr').write_bytes(emitted.stderr)
        assert emitted.returncode == 0
        migrations = {'manifest': manifest, 'driver_sha256': digest(emitted.stdout),
                      'driver_exit_code': emitted.returncode, 'runner_sha256': digest((ROOT / 'scripts/dev/migrate_sql.sh').read_bytes())}
        migrations['fresh'], empty = run_migrations(repo, directory, 'fresh', manifest)
        migrations['empty_replay'], _ = run_migrations(repo, directory, 'replay-empty', manifest, empty)
        with ExitStack() as stack:
            runtime = LifecycleRuntime(repo, stack)
            runtime.article_id = runtime.articles[provider]
            bridge = Bridge(runtime, go_name)
            model_url = stack.enter_context(serve(bridge.model_handler()))
            runtime.env['INCEPTION_API_BASE_URL'] = model_url + '/v1'
            runtime.env['INCEPTION_API_TIMEOUT_SECONDS'] = '60'
            for key, value in runtime.env.items():
                monkeypatch.setenv(key, value)
            ensure_url = stack.enter_context(serve(bridge.ensure_handler()))
            control_url = stack.enter_context(serve(bridge.control_handler()))
            service_probes = probes(runtime)
            go_env = {key: os.environ[key] for key in ('PATH', 'HOME', 'GOTOOLCHAIN', 'GOPROXY', 'GOFLAGS', 'CGO_ENABLED', 'GOMODCACHE', 'GOCACHE', 'GOTMPDIR') if key in os.environ}
            assert go_env['GOTOOLCHAIN'] == 'local' and go_env['GOPROXY'] == 'off'
            Path(go_env['GOCACHE']).mkdir(parents=True, exist_ok=True)
            Path(go_env['GOTMPDIR']).mkdir(parents=True, exist_ok=True)
            go_env.update(AUTODATA_CATALOG_INTEGRATION_REQUIRED='1', AUTODATA_LIFECYCLE_TEST='1',
                          AUTODATA_CATALOG_TEST_DSN=f'postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{repo.database_name}?sslmode=disable',
                          AUTODATA_CATALOG_TEST_ENSURE_URL=ensure_url,
                          AUTODATA_CATALOG_TEST_CONTROL_URL=control_url,
                          AUTODATA_CATALOG_TEST_CONTROL_TOKEN=bridge.token,
                          AUTODATA_CATALOG_TEST_VEHICLE_ID=str(runtime.vehicle),
                          AUTODATA_CATALOG_TEST_ARTICLE_ID=str(runtime.article_id),
                          AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID=str(runtime.articles['banktwo' if provider == 'bankone' else 'bankone']),
                          AUTODATA_CATALOG_TEST_PROVIDER=provider,
                          AUTODATA_CATALOG_TEST_CANDIDATE_SHA=provenance['candidate_sha'],
                          AUTODATA_CATALOG_TEST_CASE_DIR=str(directory))
            argv = ['go', 'test', '-json', '-count=1', '-timeout=90s', '-run', '^' + go_name + '$', '.']
            write_json(directory / 'go-command.json', {'argv': argv, 'cwd': str(ROOT / 'apps/api-go')})
            with (directory / 'go-events.jsonl').open('wb') as stdout, (directory / 'go-stderr.log').open('wb') as stderr:
                process = subprocess.Popen(argv, cwd=ROOT / 'apps/api-go', env=go_env, stdout=stdout, stderr=stderr)
                try:
                    result['go_exit_code'] = process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    result['timed_out'] = True
                    process.kill()
                    process.wait(timeout=3)
                    result['go_exit_code'] = process.returncode
                    raise
            measurement = json.loads((directory / 'go-measurement.json').read_bytes())
            result['phase_snapshots'] = measurement['phase_snapshots']
            result['assertion_results'] = measurement['assertion_results']
            assert result['go_exit_code'] == 0, (directory / 'go-events.jsonl').read_text() + (directory / 'go-stderr.log').read_text()
            validate_go_events(directory / 'go-events.jsonl', go_name)
            final = bridge.snapshot()
            assert not final['proxy']['errors'] and final['ensure']['active'] == 0
            runtime.record_evidence(go_name + '-' + provider)
            worker_exits = bridge.stop()
            before, schema = migration_snapshot(repo, migration_env(repo))
            (directory / 'populated-before.schema.sql').write_bytes(schema)
            write_json(directory / 'populated-before.rows.json', before['rows'])
            migrations['populated_replay'], _ = run_migrations(repo, directory, 'replay-populated', manifest, before)
            result['assertion_results'].update(fresh_manifest_applied_001_038=True,
                                             empty_replay_noop_001_038=True,
                                             populated_replay_noop_001_038=True)
            versions = {}
            for tool, argv in {'go': ['go', 'version'], 'python': ['python', '--version'], 'psql': ['psql', '--version'], 'pg_dump': ['pg_dump', '--version']}.items():
                version = bounded(argv)
                assert version.returncode == 0
                versions[tool] = version.stdout.decode().strip()
            measured = {'schema_version': 1, 'provider': provider, 'go_test_name': go_name,
                        'fixture_database': repo.database_name, 'candidate_sha': provenance['candidate_sha'],
                        'snapshots': result['phase_snapshots'], 'migrations': migrations,
                        'service_probes': service_probes, 'worker_exits': worker_exits,
                        'versions': versions, **{key: value for key, value in measurement.items() if key not in ('phase_snapshots', 'assertion_results')}}
            write_json(directory / 'measured-runtime.json', measured)
            runtime.close()
            runtime = None
    finally:
        if bridge is not None:
            bridge.release_model.set()
            if runtime is not None and runtime.barrier:
                runtime.release('inside_publication')
        if runtime is not None:
            try:
                bridge.stop()
            finally:
                runtime.close()
        result['finished_at'] = now()
        result['artifact_sha256'] = {path.name: digest(path.read_bytes()) for path in sorted(directory.iterdir()) if path.is_file() and path.name != 'result.json'}
        write_json(directory / 'result.json', result)
        check_inputs('after')
