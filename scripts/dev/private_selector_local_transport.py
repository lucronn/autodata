"""Concrete local operations, disabled by default; CLI validates metadata only.

This file must be copied into the physical execution root and independently
sealed before a separately reviewed launcher can enable dispatch. Importing or
validating it does not open Docker, SQL or HTTP connections or create files.
"""
import argparse
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import stat
import subprocess
import threading
import time
import uuid
import private_selector_adapter_contract as c

ROOT = Path('/home/corp/.local/state/autodata/initial-selector-runtime-20261115')
PACKAGE = Path('/home/corp/autodata-candidate/private-initial-selector-a82b31d-20261115')
EVIDENCE = Path('/home/corp/autodata-evidence')
PHYSICAL_DEVICE = 66315
OFFLOADED_DEVICE = 1792
SOCKET = Path('/var/run/docker.sock')
SOCKET_REAL = Path('/run/docker.sock')
SOCKET_ID = (25, 66375)
DOCKER_ROOT = '/mnt/openfoam/docker'
CHILD_ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
PG = 'fa007d1a844f3cd2f76f256b99f868dcb1b6aac26733e55f9f0453440a3e9d16'
PUBLIC_EXE = '/usr/local/libexec/autodata/workshop-client-preview-a82b31d-a2/autodata-api'
ARCHIVE_SHA = '4d1536d534a9327a4524b0e35cf234c83e5de4a8d18353fd6ca3b6343f7d5e74'
ARCHIVE_BYTES = 33884160
ROLLBACK = {
    c.OLD: Path('/home/corp/autodata-candidate/private-configuration-budget-272aeea-20261115'),
    c.SECONDARY: Path('/home/corp/autodata-candidate/private-diagnostics-svg-083f1a5-20261115'),
}
# Git archive executable paths are identical for these three immutable sources.
# The exact path set is pinned, rather than accepting executable mode everywhere.
_ARCHIVE_EXECUTABLES = frozenset({
    'infra/deploy/gce/backup-host.sh', 'infra/deploy/gce/cloud-bootstrap.sh',
    'infra/deploy/gce/deploy.sh', 'infra/deploy/gce/restore.sh',
    'infra/deploy/gce/runtime-entrypoint.sh', 'scripts/dev/ingest_banktwo_service.py',
})
SOURCE_EXECUTABLE_PATHS = {source: _ARCHIVE_EXECUTABLES for source in (
    c.SOURCE, c.OLD_IDENTITY['source'], c.SECONDARY_IDENTITY['source'])}

PROTECTED = tuple(sorted('''auth_sessions canonical_article_aliases canonical_article_reviews
canonical_article_revisions canonical_article_rewrite_attempts canonical_article_source_observations
canonical_article_source_revisions canonical_articles catalog_article_index_pages
catalog_article_provider_scopes catalog_article_vehicle_links catalog_articles customer_accounts
dataset_projections dataset_requests derived_article_lineage derived_article_revisions derived_articles
entitlements payment_events publication_events source_artifacts source_fetch_jobs source_review_items
source_snapshots workshop_checkout_requests workshop_orders'''.split()))
CATALOG = tuple(sorted('''vehicles vehicle_specifications vehicle_models vehicle_identity_bases
vehicle_configurations vehicle_aliases vehicle_identity_observations vehicle_provider_mappings
vehicle_catalog_syncs vehicle_catalog_sync_scopes vehicle_catalog_years vehicle_catalog_hydration_scopes'''.split()))
TABLES = tuple(sorted(PROTECTED + CATALOG))


def bounded(argv, *, data=None, timeout=15, limit=262144):
    """Fixed-environment child, bounded pipes and owned process group cleanup."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT,
                               env=CHILD_ENV, start_new_session=True)
    selector = selectors.DefaultSelector()
    output = bytearray(); discarded = 0; deadline = time.monotonic() + timeout
    try:
        for stream, name in ((process.stdout, 'out'), (process.stderr, 'err')):
            os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, name)
        pending = memoryview(data or b'')
        if process.stdin:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, 'in')
        while selector.get_map():
            c.require(time.monotonic() < deadline, 'child_deadline')
            for key, _ in selector.select(min(.05, max(0, deadline - time.monotonic()))):
                if key.data == 'in':
                    if pending:
                        try: pending = pending[os.write(key.fd, pending[:65536]):]
                        except BrokenPipeError: pending = memoryview(b'')
                    if not pending:
                        selector.unregister(key.fileobj); key.fileobj.close()
                    continue
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj); key.fileobj.close(); continue
                if key.data == 'out': output.extend(chunk)
                else: discarded += len(chunk)
                c.require(len(output) <= limit and discarded <= 262144, 'child_output_bound')
        c.require(process.wait(timeout=max(.01, deadline - time.monotonic())) == 0, 'child_failed')
        return bytes(output)
    except Exception:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        try: process.communicate(timeout=2)
        except Exception: pass
        try: process.wait(timeout=2)
        except Exception: pass
        raise c.Refused('bounded_child_failed') from None
    finally:
        selector.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream and not stream.closed: stream.close()


def regular(path, *, maximum=128 * c.MIB, modes=(0o600, 0o444), device=PHYSICAL_DEVICE):
    path = Path(path)
    c.require(path.is_absolute() and path.resolve() == path, 'artifact_path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    stream = os.fdopen(fd, 'rb')
    state = os.fstat(stream.fileno())
    if not (stat.S_ISREG(state.st_mode) and state.st_uid == os.getuid()
            and state.st_nlink == 1 and state.st_dev == device
            and stat.S_IMODE(state.st_mode) in modes and state.st_size <= maximum):
        stream.close(); raise c.Refused('artifact_metadata')
    return stream


def file_hash(path, **kwargs):
    digest = hashlib.sha256()
    with regular(path, **kwargs) as stream:
        for block in iter(lambda: stream.read(65536), b''): digest.update(block)
    return digest.hexdigest()


def private_json(path, *, maximum=65536):
    with regular(path, maximum=maximum) as stream: return json.load(stream)


def allocated(root):
    seen = set(); total = 0
    for folder, dirs, files in os.walk(root, followlinks=False):
        for path in [Path(folder)] + [Path(folder) / n for n in files]:
            state = path.lstat()
            c.require(not stat.S_ISLNK(state.st_mode) and state.st_dev == Path(root).stat().st_dev,
                      'allocation_escape')
            key = (state.st_dev, state.st_ino)
            if key not in seen: total += state.st_blocks * 512; seen.add(key)
        c.require(not any((Path(folder) / n).is_symlink() for n in dirs), 'allocation_symlink')
    return total


def verify_inventory(parent, expected_manifest, source, tree):
    parent = Path(parent)
    c.require(file_hash(parent / 'manifest.json') == expected_manifest, 'source_manifest_hash')
    manifest = private_json(parent / 'manifest.json', maximum=2 * c.MIB)
    c.require(manifest.get('source_sha') == source and manifest.get('tree') == tree, 'source_pin')
    entries = manifest.get('files', {})
    c.require(isinstance(entries, dict) and 0 < len(entries) <= 2000, 'source_inventory')
    executables = SOURCE_EXECUTABLE_PATHS.get(source)
    c.require(executables is not None and executables <= set(entries), 'source_mode_pin')
    actual = set(); root = parent / 'source'
    for folder, dirs, files in os.walk(root, followlinks=False):
        directory = Path(folder); state = directory.lstat()
        c.require(stat.S_ISDIR(state.st_mode) and state.st_dev == PHYSICAL_DEVICE
                  and state.st_uid == os.getuid() and stat.S_IMODE(state.st_mode) == 0o555,
                  'source_directory')
        for n in dirs: c.require(not (directory / n).is_symlink(), 'source_symlink')
        for n in files:
            p = directory / n; relative = str(p.relative_to(root)); actual.add(relative)
            c.require(relative in entries and c.full_id(entries[relative])
                      and file_hash(p, modes=(0o555,) if relative in executables else (0o444,))
                      == entries[relative], 'source_file')
    c.require(actual == set(entries), 'source_extras_or_missing')


def combined_sql():
    """One fixed statement inside one bounded read-only transaction; no user SQL."""
    pairs = []
    for name in TABLES:
        pairs += ["'" + name + "'", "(SELECT jsonb_build_object('count',count(*),'rows',"
                  "md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),'')),"
                  "'schema',(SELECT md5(string_agg(attname||':'||atttypid::text||':'||attnotnull::text,',' ORDER BY attnum)) "
                  "FROM pg_attribute WHERE attrelid='public." + name + "'::regclass AND attnum>0 AND NOT attisdropped)) "
                  'FROM public."' + name + '" t)']
    inventory = "(SELECT jsonb_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='public' AND (tablename IN (" + ','.join("'" + x + "'" for x in PROTECTED) + ") OR tablename LIKE 'vehicle%' OR tablename LIKE 'canonical_article%' OR tablename LIKE 'derived_article%' OR tablename LIKE 'catalog_article%'))"
    quote = "(SELECT c.vehicle_configuration_id::text FROM vehicle_configurations c JOIN vehicle_identity_bases b USING(vehicle_identity_base_id) WHERE c.reviewer_state<>'rejected' AND b.reviewer_state<>'rejected' AND b.region='US' ORDER BY c.vehicle_configuration_id LIMIT 1)"
    statement = "SELECT jsonb_build_object('tables',jsonb_build_object(" + ','.join(pairs) + "),'inventory'," + inventory + ",'quote_uuid'," + quote + ",'connection',jsonb_build_object('pid',pg_backend_pid(),'snapshot',pg_current_snapshot()::text,'isolation',current_setting('transaction_isolation'),'read_only',current_setting('transaction_read_only'),'default_read_only',current_setting('default_transaction_read_only')))"
    return "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='10s'; SET LOCAL lock_timeout='1s'; SET LOCAL transaction_timeout='12s'; " + statement + '; COMMIT;'


class UnixDocker(http.client.HTTPConnection):
    def __init__(self, checker):
        super().__init__('localhost', timeout=5); self.checker = checker
        self.expired = threading.Event(); self.owned_socket = None
    def connect(self):
        c.require(not self.expired.is_set(), 'docker_http_deadline')
        self.checker()  # Immediately before raw connect, in addition to admission.
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.owned_socket = self.sock
        self.sock.settimeout(self.timeout)
        try:
            self.sock.connect(str(SOCKET_REAL))
            if self.expired.is_set(): self.abort(); raise c.Refused('docker_http_deadline')
        except Exception:
            self.abort(); raise c.Refused('docker_socket_connect') from None
    def abort(self):
        self.expired.set(); owned = self.owned_socket or self.sock
        if owned:
            try: owned.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            try: owned.close()
            except OSError: pass
        self.close()


class DeadlineLoopback(http.client.HTTPConnection):
    """Keep the actual socket even when HTTPResponse takes ownership of it."""
    def __init__(self):
        super().__init__('127.0.0.1', 3031, timeout=2)
        self.expired = threading.Event(); self.owned_socket = None
    def connect(self):
        c.require(not self.expired.is_set(), 'http_deadline')
        super().connect(); self.owned_socket = self.sock
        if self.expired.is_set(): self.abort(); raise c.Refused('http_deadline')
    def abort(self):
        self.expired.set(); owned = self.owned_socket or self.sock
        if owned:
            try: owned.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            try: owned.close()
            except OSError: pass
        self.close()


class LocalTransport:
    def __init__(self, manifest, *, external_seal_sha=None, dispatch_enabled=False, runner=None):
        self.manifest = manifest; self.phase = manifest.get('phase')
        self.external_seal_sha = external_seal_sha; self.dispatch_enabled = dispatch_enabled
        self.runner = runner or bounded; self.lock_fd = None; self.created = {}; self.fixture_cleanup = False; self.fixture_metadata = None

    def enabled(self):
        c.require(self.dispatch_enabled is True and c.full_id(self.external_seal_sha), 'dispatch_disabled')

    def paths(self):
        names = {'archive': PACKAGE / 'source.tar', 'source_inventory': PACKAGE / 'manifest.json',
                 'contract': ROOT / 'private_selector_adapter_contract.py',
                 'transport': ROOT / 'private_selector_local_transport.py',
                 'fixture_adapter': ROOT / 'private_selector_image_fixture.py',
                 'runtime_adapter': ROOT / 'private_selector_runtime_adapter.py',
                 'fixture_bootstrap': ROOT / 'fixture_bootstrap.py', 'fixture_client': ROOT / 'fixture_client.py',
                 'fixture_plan': ROOT / 'fixture-plan.json',
                 'fixture_payload_bootstrap': ROOT / 'fixture-bootstrap.create.json',
                 'fixture_payload_worker': ROOT / 'fixture-worker.create.json',
                 'dump': ROOT / 'before.dump', 'toc': ROOT / 'before.toc',
                 'baseline39': ROOT / 'baseline-before.json', 'fixture_receipt': ROOT / 'actual-image-fixture.json',
                 'launcher': ROOT / 'launch_reviewed.py', 'payload': ROOT / 'candidate.create.json'}
        return {name: names[name] for name in c.ARTIFACTS[self.phase]}

    def physical_dir(self, path, mode=0o700):
        state = Path(path).lstat()
        c.require(Path(path).resolve() == Path(path) and stat.S_ISDIR(state.st_mode)
                  and state.st_dev == PHYSICAL_DEVICE and state.st_uid == os.getuid()
                  and stat.S_IMODE(state.st_mode) == mode, 'physical_directory')

    def seal(self):
        self.enabled(); c.validate(self.manifest, self.phase)
        c.require(self.manifest.get('execution_approved') is True, 'phase_unapproved')
        self.physical_dir(ROOT); self.physical_dir(PACKAGE)
        c.require(Path(__file__).resolve() == ROOT / 'private_selector_local_transport.py', 'physical_transport_copy')
        c.require(Path(c.__file__).resolve() == ROOT / 'private_selector_adapter_contract.py', 'loaded_contract')
        seal_path = ROOT / 'transport-execution-seal.json'
        c.require(file_hash(seal_path) == self.external_seal_sha, 'external_seal')
        seal = private_json(seal_path)
        c.require(seal.get('manifest_sha256') == c.digest(self.manifest), 'manifest_seal')
        paths = self.paths()
        c.require(seal.get('artifacts') == self.manifest['artifacts'], 'artifact_seal')
        for name, path in paths.items():
            c.require(file_hash(path) == self.manifest['artifacts'][name], 'sealed_artifact_drift')
        verify_inventory(PACKAGE, self.manifest['artifacts']['source_inventory'], c.SOURCE, c.TREE)
        c.require(file_hash(PACKAGE / 'source.tar') == ARCHIVE_SHA
                  and (PACKAGE / 'source.tar').stat().st_size == ARCHIVE_BYTES, 'archive_pin')
        c.require((PACKAGE / 'source.tar').stat().st_blocks * 512 <= 36 * c.MIB
                  and allocated(PACKAGE / 'source') <= 40 * c.MIB, 'source_subcaps')
        if self.phase == 'runtime':
            c.require(sum((ROOT / n).stat().st_blocks * 512 for n in ('before.dump', 'before.toc'))
                      <= 24 * c.MIB, 'backup_subcap')
            with regular(ROOT / 'before.dump') as stream:
                c.require(stream.read(5) == b'PGDMP', 'backup_format')
        scratch = allocated(ROOT / 'scratch') if (ROOT / 'scratch').exists() else 0
        backup = sum((ROOT / n).stat().st_blocks * 512 for n in ('before.dump', 'before.toc')
                     if (ROOT / n).exists())
        c.require(scratch <= 20 * c.MIB and allocated(ROOT) - scratch - backup <= 8 * c.MIB,
                  'execution_subcaps')
        return seal

    def lease(self):
        self.enabled()
        if self.lock_fd is not None:
            current = (ROOT / 'transport.lock').lstat(); opened = os.fstat(self.lock_fd)
            c.require((current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino)
                      and current.st_nlink == 1 and current.st_uid == os.getuid()
                      and stat.S_IMODE(current.st_mode) == 0o600, 'lease_inode_drift')
            return
        fd = os.open(ROOT / 'transport.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        state = os.fstat(fd)
        try:
            c.require(stat.S_ISREG(state.st_mode) and state.st_dev == PHYSICAL_DEVICE
                      and state.st_uid == os.getuid() and state.st_nlink == 1
                      and stat.S_IMODE(state.st_mode) == 0o600, 'lock_file')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception: os.close(fd); raise c.Refused('exclusive_lease') from None
        self.lock_fd = fd

    def close(self):
        if self.lock_fd is not None: os.close(self.lock_fd); self.lock_fd = None

    def socket_check(self):
        self.enabled(); state = SOCKET.stat()
        c.require(SOCKET.resolve() == SOCKET_REAL and stat.S_ISSOCK(state.st_mode)
                  and (state.st_dev, state.st_ino) == SOCKET_ID, 'socket_identity')
        self.physical_dir(ROOT / 'docker-config')
        c.require(not list((ROOT / 'docker-config').iterdir()), 'docker_config_not_empty')

    def invoke(self, argv, **kwargs):
        self.enabled()
        try: return self.runner(argv, **kwargs)
        except Exception: raise c.Refused('local_command_failed') from None

    def docker(self, *args, data=None, timeout=15, limit=262144):
        self.seal(); self.socket_check()
        prefix = ['/usr/bin/docker', '--config', str(ROOT / 'docker-config'),
                  '--host', 'unix:///var/run/docker.sock']
        root = self.invoke(prefix + ['info', '--format', '{{.DockerRootDir}}'], timeout=5, limit=4096)
        c.require(root.decode().strip() == DOCKER_ROOT, 'docker_data_root')
        self.socket_check()
        return self.invoke(prefix + list(args), data=data, timeout=timeout, limit=limit)

    def record_once(self, name, value):
        self.seal(); self.lease()
        c.require(re.fullmatch('[a-z][a-z0-9-]{0,63}', name) is not None, 'receipt_name')
        data = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
        c.require(len(data) <= 65536, 'receipt_bound')
        fd = os.open(ROOT / (name + '.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
        fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)

    def public_identity(self):
        pid = c.PUBLIC['pid']; proc = Path('/proc') / str(pid)
        before = (proc / 'stat').read_text().split(') ', 1)[1].split()[19]
        c.require(os.readlink(proc / 'exe') == PUBLIC_EXE, 'public_executable')
        digest = hashlib.sha256()
        with (proc / 'exe').open('rb') as stream:
            for block in iter(lambda: stream.read(65536), b''): digest.update(block)
        after = (proc / 'stat').read_text().split(') ', 1)[1].split()[19]
        c.require(before == after, 'public_pid_changed')
        return {'pid': pid, 'start_ticks': after, 'binary_sha256': digest.hexdigest()}

    def raw_inspect(self, identifier):
        c.require(c.full_id(identifier), 'container_id')
        rows = json.loads(self.docker('inspect', identifier))
        c.require(len(rows) == 1 and rows[0]['Id'] == identifier, 'inspect_identity')
        return rows[0]

    def inspect(self, identifier):
        value = self.raw_inspect(identifier); mounts = value['Mounts']
        c.require(len(mounts) == 1 and mounts[0]['Destination'] == '/app' and mounts[0]['RW'] is False,
                  'application_mount')
        if identifier in ROLLBACK:
            seal = self.seal(); parent = ROLLBACK[identifier]
            expected = c.OLD_IDENTITY if identifier == c.OLD else c.SECONDARY_IDENTITY
            hashes = seal.get('rollback_manifests', {})
            c.require(c.full_id(hashes.get(identifier)), 'rollback_inventory_seal')
            inventory = private_json(parent / 'manifest.json', maximum=2 * c.MIB)
            verify_inventory(parent, hashes[identifier], expected['source'], inventory['tree'])
            source = expected['source']
        else:
            c.require(identifier == self.manifest.get('candidate', {}).get('id'), 'unapproved_container')
            parent, source = PACKAGE, c.SOURCE
        c.require(mounts[0]['Source'] == str(parent / 'source'), 'source_mount')
        state = value['State']
        return {'id': value['Id'], 'image': value['Image'], 'source': source,
                'config': c.digest(value['Config']), 'hostconfig': c.digest(value['HostConfig']),
                'mounts': c.digest(value['Mounts']), 'status': state['Status'],
                'running': state['Running'], 'restarting': state['Restarting'], 'pid': state['Pid'],
                'started_at': state['StartedAt'], 'restart_count': value['RestartCount']}

    def boundary_proof(self, phase, manifest_sha):
        seal = self.seal(); self.lease()
        c.require(phase == self.phase and manifest_sha == c.digest(self.manifest), 'boundary_manifest')
        for path in (ROOT, PACKAGE):
            data = self.invoke(['/usr/bin/findmnt', '--json', '--target', str(path), '--output',
                                'SOURCE,FSTYPE,TARGET'], timeout=5, limit=4096)
            c.require(json.loads(data).get('filesystems') == [
                {'source': '/dev/nvme0n1p11', 'fstype': 'ext4', 'target': '/home'}], 'physical_mount')
        image = self.docker('image', 'inspect', c.IMAGE, '--format', '{{.Id}}', limit=4096)
        c.require(image.decode().strip() == c.IMAGE, 'cached_image_identity')
        home = os.statvfs('/home/corp'); docker = os.statvfs(DOCKER_ROOT)
        off = Path(self.manifest['transport']['offloaded_root'])
        c.require(off.parent == EVIDENCE and off.resolve() == off and off.stat().st_dev == OFFLOADED_DEVICE,
                  'offloaded_root')
        usage = os.statvfs(off)
        return {'approved_manifest': seal['manifest_sha256'], 'physical_device': ROOT.stat().st_dev,
                'docker_root': DOCKER_ROOT, 'socket_identity': list(SOCKET_ID),
                'empty_fixed_docker_config': True, 'artifact_hashes': self.manifest['artifacts'],
                'home_allocated': allocated(ROOT) + allocated(PACKAGE),
                'docker_allocated': self.docker_growth(), 'offloaded_allocated': allocated(off),
                'home_free': home.f_bavail * home.f_frsize, 'docker_free': docker.f_bavail * docker.f_frsize,
                'offloaded_free': usage.f_bavail * usage.f_frsize}

    def docker_growth(self):
        # A separate reviewed pre-create daemon filesystem sample is mandatory.
        start = self.manifest['transport'].get('docker_start_free')
        c.require(type(start) is int and start >= 947912704, 'docker_start_sample')
        usage = os.statvfs(DOCKER_ROOT)
        return max(0, start - usage.f_bavail * usage.f_frsize)

    def pause(self, seconds):
        c.require(type(seconds) in (int, float) and 0 <= seconds <= .5, 'pause_bound'); time.sleep(seconds)

    def stop(self, identifier):
        c.require(self.phase == 'runtime', 'runtime_phase_required')
        expected = c.OLD_IDENTITY if identifier == c.OLD else self.manifest.get('candidate', {})
        c.require(identifier == expected.get('id'), 'runtime_mutation_id')
        c.identity(self.inspect(identifier), expected)
        self.docker('stop', '--time', '0', identifier, timeout=5, limit=4096)

    def start(self, identifier):
        c.require(self.phase == 'runtime', 'runtime_phase_required')
        expected = c.OLD_IDENTITY if identifier == c.OLD else self.manifest.get('candidate', {})
        c.require(identifier == expected.get('id'), 'runtime_mutation_id')
        c.identity(self.inspect(identifier), expected)
        self.docker('start', identifier, timeout=10, limit=4096)

    def create_payload(self, name, payload):
        self.seal(); self.socket_check()
        c.require(self.phase == 'fixture', 'fixture_phase_required')
        c.require(re.fullmatch('autodata-selector-fixture-[a-f0-9]{32}-(bootstrap|worker)', name) is not None,
                  'fixture_name')
        role = name.rsplit('-', 1)[1]
        c.require(name == 'autodata-selector-fixture-' + self.manifest['run_id'] + '-' + role,
                  'fixture_run_name')
        approved = private_json(self.paths()['fixture_payload_' + role], maximum=262144)
        c.require(c.typed_equal(payload, approved), 'unsealed_create_payload')
        self.validate_fixture_payload(role, payload)
        self.docker('info', '--format', '{{.DockerRootDir}}', limit=4096)
        data = json.dumps(payload, separators=(',', ':')).encode(); c.require(len(data) <= 262144, 'payload_bound')
        def connect_check(): self.seal(); self.socket_check()
        connection = UnixDocker(connect_check)
        timer = threading.Timer(5, connection.abort); timer.daemon = True; timer.start()
        try:
            self.socket_check()
            connection.request('POST', '/v1.43/containers/create?name=' + name, body=data,
                               headers={'Content-Type': 'application/json'})
            response = connection.getresponse(); body = response.read(65537)
            c.require(response.status == 201 and len(body) <= 65536, 'docker_create')
            value = json.loads(body); c.require(c.full_id(value.get('Id')), 'created_id')
            return value['Id']
        finally:
            timer.cancel(); connection.abort(); timer.join(timeout=.2)
            c.require(not timer.is_alive(), 'docker_http_cleanup_unknown')

    def validate_fixture_payload(self, role, payload):
        plan = private_json(self.paths()['fixture_plan'])
        c.require(plan.get('run_id') == self.manifest['run_id'], 'fixture_plan_run')
        image = c.TEST_IMAGE if role == 'bootstrap' else c.IMAGE
        host = payload.get('HostConfig', {})
        network = plan.get('network', {})
        c.require(c.full_id(network.get('id')) and host.get('NetworkMode') == network['id'],
                  'fixture_network_pin')
        actual = json.loads(self.docker('network', 'inspect', network['id']))[0]
        peers = network.get('peer_identities', {})
        c.require(isinstance(peers, dict) and all(c.full_id(k) and c.full_id(v) for k, v in peers.items())
                  and not ({PG, c.OLD, c.SECONDARY} & set(peers)), 'synthetic_peers')
        for identifier, expected in peers.items():
            value = self.raw_inspect(identifier)
            c.require(value['Name'].startswith(('/autodata-catalog-compat-', '/autodata-selector-fixture-'))
                      and c.digest({k: value[k] for k in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts')})
                      == expected, 'synthetic_peer_identity')
        c.require(actual['Id'] == network['id'] and actual['Internal'] is True
                  and set(actual.get('Containers', {})) <= set(peers) | set(self.created), 'fixture_network')
        c.require(payload.get('Image') == image and payload.get('Entrypoint') == ['/usr/local/bin/python']
                  and payload.get('WorkingDir') == '/app/workers/ingestion-python', 'fixture_image_argv')
        if role == 'worker':
            c.require(payload.get('Cmd') == ['-m', 'autodata_ingestion.http_service'], 'fixture_worker_cmd')
        else:
            with regular(self.paths()['fixture_bootstrap'], maximum=262144) as stream:
                script = stream.read().decode()
            c.require(payload.get('Cmd') == ['-B', '-u', '-c', script], 'fixture_bootstrap_cmd')
            c.require(payload.get('OpenStdin') is True and payload.get('StdinOnce') is False,
                      'fixture_bootstrap_stdin')
        c.require(host.get('ReadonlyRootfs') is True and not host.get('PortBindings')
                  and host.get('Memory') == 768 * c.MIB and host.get('PidsLimit') == 128
                  and host.get('CapDrop') == ['ALL'] and host.get('SecurityOpt') == ['no-new-privileges']
                  and host.get('Tmpfs') == {'/tmp': 'rw,noexec,nosuid,size=67108864'}
                  and host.get('Mounts') == [{'Type': 'bind', 'Source': str(PACKAGE / 'source'),
                                            'Target': '/app', 'ReadOnly': True}], 'fixture_security')
        entries = payload.get('Env', [])
        c.require(isinstance(entries, list) and all(isinstance(x, str) and '=' in x for x in entries),
                  'fixture_environment')
        env = dict(x.split('=', 1) for x in entries)
        c.require(len(env) == len(entries) and env == plan.get('synthetic_environment', {}).get(role),
                  'synthetic_environment_seal')
        raw_old = self.raw_inspect(c.OLD); old_env = dict(x.split('=', 1) for x in raw_old['Config']['Env'])
        c.require(set(env) == set(old_env) and payload.get('User', '') == raw_old['Config']['User'],
                  'fixture_environment_names_user')
        metadata = json.loads(self.docker('image', 'inspect', image))[0]
        c.require(metadata['Id'] == image and {x.split('=', 1)[0] for x in metadata['Config']['Env']} <= set(env),
                  'image_environment_defaults')
        for key in ('BANKONE_BASE_URL', 'BANKTWO_BASE_URL'):
            c.require(re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}', env.get(key, '')) is not None,
                      'synthetic_provider_endpoint')
        c.require(env.get('AUTODATA_DB_ADDRESS') == 'postgres:5432'
                  and env.get('AUTODATA_POSTGRES_DB') == 'lifecycle_test_' + self.manifest['run_id']
                  and env.get('AUTODATA_POSTGRES_USER') == 'lifecycle_test'
                  and env.get('AUTODATA_POSTGRES_PASSWORD') == 'lifecycle_test_only'
                  and env.get('AUTODATA_COMMERCE_MODE') == 'read_only'
                  and env.get('AUTODATA_STRIPE_ACCOUNT_ID') == 'acct_fixture'
                  and env.get('AUTODATA_STRIPE_PRICE_ID') == 'price_fixture', 'synthetic_database_merchant')
        for key, value in env.items():
            if re.search(r'PASSWORD|SECRET|TOKEN|API_KEY|CREDENTIAL|BEARER|AUTHORIZATION|_KEY$', key):
                c.require(value == '' or value == 'lifecycle_test_only' or value.startswith('fixture'),
                          'fixture_secret_substitution')

    def create_fixture(self, role, manifest):
        c.require(role in ('bootstrap', 'worker') and c.digest(manifest) == c.digest(self.manifest),
                  'fixture_manifest')
        payload = private_json(self.paths()['fixture_payload_' + role], maximum=262144)
        name = 'autodata-selector-fixture-' + self.manifest['run_id'] + '-' + role
        identifier = self.create_payload(name, payload)
        c.require(identifier not in (c.OLD, c.SECONDARY, PG), 'created_protected_id')
        self.created[identifier] = role
        self.record_once('transport-created-' + role, {'id': identifier, 'name': name})
        return identifier

    def fixture_identity(self, identifier):
        c.require(identifier in self.created, 'fixture_not_owned')
        role = self.created[identifier]; raw = self.raw_inspect(identifier)
        payload = private_json(self.paths()['fixture_payload_' + role], maximum=262144)
        plan = private_json(self.paths()['fixture_plan'])
        self.validate_fixture_payload(role, payload)
        status = raw['State']['Status']
        expected_hash = plan.get('hostconfig_by_status', {}).get(role, {}).get(status)
        c.require(c.full_id(expected_hash) and c.digest(raw['HostConfig']) == expected_hash,
                  'fixture_lifecycle_hash')
        expected_name = '/autodata-selector-fixture-' + self.manifest['run_id'] + '-' + role
        c.require(raw['Name'] == expected_name and raw['Image'] == payload['Image'], 'fixture_actual_name_image')
        for name in ('User', 'WorkingDir', 'Entrypoint', 'Cmd'):
            c.require(c.typed_equal(raw['Config'].get(name), payload.get(name)), 'fixture_actual_config')
        c.require(dict(x.split('=', 1) for x in raw['Config']['Env'])
                  == dict(x.split('=', 1) for x in payload['Env']), 'fixture_effective_environment')
        c.require(len(raw['Mounts']) == 1 and raw['Mounts'][0]['Source'] == str(PACKAGE / 'source')
                  and raw['Mounts'][0]['Destination'] == '/app' and raw['Mounts'][0]['RW'] is False,
                  'fixture_actual_mount')
        import private_selector_image_fixture as fixture
        c.require(Path(fixture.__file__).resolve() == ROOT / 'private_selector_image_fixture.py',
                  'loaded_fixture_adapter')
        return {'id': identifier, 'run_id': self.manifest['run_id'], 'role': role,
                'image': payload['Image'], 'source': c.SOURCE, 'owned_synthetic': True,
                'policy': fixture.OWNED_POLICY}

    def start_fixture(self, identifier):
        self.fixture_identity(identifier)
        self.docker('start', identifier, timeout=10, limit=4096)

    def wait_fixture_ready(self, identifier):
        self.fixture_identity(identifier)
        c.require(self.created.get(identifier) == 'bootstrap', 'fixture_bootstrap_role')
        deadline = time.monotonic() + 60
        names = {'database', 'configuration', 'foreign_configuration', 'owner', 'organization', 'entitlement'}
        while time.monotonic() < deadline:
            self.fixture_identity(identifier)
            c.require(self.raw_inspect(identifier)['State']['Running'] is True, 'fixture_bootstrap_exited')
            raw = self.docker('logs', '--tail', '1', identifier, timeout=5, limit=16384).strip()
            if raw:
                data = json.loads(raw)
                c.require(isinstance(data, dict) and set(data) == names
                          and data['database'] == 'lifecycle_test_' + self.manifest['run_id'], 'fixture_database_metadata')
                for key in names - {'database'}:
                    c.require(isinstance(data[key], str) and str(uuid.UUID(data[key])) == data[key], 'fixture_uuid')
                self.fixture_metadata = data
                return
            self.pause(.2)
        raise c.Refused('fixture_bootstrap_deadline')

    def exercise_fixture(self, identifier, manifest):
        self.fixture_identity(identifier)
        c.require(c.digest(manifest) == c.digest(self.manifest), 'fixture_client_manifest')
        bootstrap = [k for k, role in self.created.items() if role == 'bootstrap']
        c.require(len(bootstrap) == 1, 'fixture_bootstrap_id')
        c.require(isinstance(self.fixture_metadata, dict), 'fixture_bootstrap_not_ready')
        data = dict(self.fixture_metadata)
        data['bucket'] = 'autodata-selector-fixture-' + manifest['run_id']
        with regular(self.paths()['fixture_client'], maximum=262144) as stream: script = stream.read()
        prefix = ('import json\nFIXTURE=json.loads(' + repr(json.dumps(data)) + ')\n').encode()
        value = json.loads(self.docker('exec', '-i', identifier, '/usr/local/bin/python', '-B', '-',
                                       data=prefix + script, timeout=120, limit=65536))
        c.require(isinstance(value, dict) and set(value) == {'checks', 'cleanup'}, 'fixture_client_result')
        c.require(c.typed_equal(value['cleanup'], {'database_removed': True, 'bucket_removed': True}), 'fixture_client_cleanup_unknown')
        self.record_once('transport-fixture-client', value)
        return value['checks']

    def stop_fixture(self, identifier):
        self.fixture_identity(identifier)
        bootstrap = self.created[identifier] == 'bootstrap'
        self.docker('stop', '--time', '65' if bootstrap else '0', identifier,
                    timeout=70 if bootstrap else 5, limit=4096)
        if bootstrap:
            value = json.loads(self.docker('logs', '--tail', '1', identifier, timeout=5, limit=16384))
            self.fixture_cleanup = c.typed_equal(value, {'cleanup': {'database_removed': True, 'bucket_removed': True}})
            c.require(self.fixture_cleanup, 'fixture_bootstrap_cleanup_unknown')

    def fixture_stopped(self, identifier):
        samples = []
        for index in range(3):
            if index: self.pause(.2)
            self.fixture_identity(identifier)
            value = self.raw_inspect(identifier)['State']
            c.require(value['Running'] is False and value['Pid'] == 0 and value['Restarting'] is False
                      and value['Status'] in ('created', 'exited'), 'fixture_stop_unknown')
            samples.append(value)
        c.require(samples[0] == samples[1] == samples[2], 'fixture_stop_unstable')
        return True

    def remove_fixture(self, identifier):
        self.fixture_identity(identifier); self.fixture_stopped(identifier)
        self.docker('rm', identifier, timeout=5, limit=4096)

    def fixture_absent(self, identifier):
        c.require(identifier in self.created, 'fixture_absence_id')
        output = self.docker('ps', '-aq', '--no-trunc', '--filter', 'id=' + identifier,
                             timeout=5, limit=4096).decode().strip()
        return output == ''

    def owned_database_bucket_removed(self, run_id):
        return run_id == self.manifest['run_id'] and self.fixture_cleanup is True

    def serving_snapshot(self):
        return {'old': self.inspect(c.OLD), 'secondary': self.inspect(c.SECONDARY),
                'public': self.public_identity()}

    def compact_snapshot(self):
        self.seal(); c.require(self.phase == 'runtime' and self.manifest['transport'].get('sql_approved') is True,
                               'sql_not_approved')
        database = self.raw_inspect(PG)
        expected = self.manifest['transport'].get('postgres_identity_sha256')
        c.require(c.full_id(expected) and c.digest({k: database[k] for k in
                  ('Id', 'Image', 'Config', 'HostConfig', 'Mounts')}) == expected, 'postgres_identity')
        output = self.docker('exec', '-e', 'PGOPTIONS=-c default_transaction_read_only=on', '-i', PG,
                             '/usr/lib/postgresql/17/bin/psql', '-X', '-A', '-t', '-q', '-v', 'ON_ERROR_STOP=1',
                             '-U', 'autodata', '-d', 'autodata', '-c', combined_sql(), timeout=15, limit=65536)
        value = json.loads(output); meta = value.get('connection', {})
        c.require(value.get('inventory') == list(TABLES) and set(value.get('tables', {})) == set(TABLES)
                  and meta.get('isolation') == 'repeatable read' and meta.get('read_only') == 'on'
                  and meta.get('default_read_only') == 'on' and type(meta.get('pid')) is int,
                  'coherent_snapshot')
        for row in value['tables'].values():
            c.require(isinstance(row, dict) and set(row) == {'count', 'rows', 'schema'}
                      and type(row['count']) is int and row['count'] >= 0
                      and all(isinstance(row[k], str) and re.fullmatch('[a-f0-9]{32}', row[k])
                              for k in ('rows', 'schema')), 'snapshot_hash_shape')
        return value

    def loopback(self, path, data=None, token=None):
        self.seal()
        c.require(self.phase == 'runtime' and self.manifest['transport'].get('http_approved') is True,
                  'http_not_approved')
        c.require(path in ('/healthz', '/internal/commerce/purchase-config', '/internal/commerce/quote'),
                  'http_path_forbidden')
        connection = DeadlineLoopback()
        timer = threading.Timer(2, connection.abort); timer.daemon = True; timer.start()
        headers = {'Content-Type': 'application/json'}
        if token is not None: headers['X-Autodata-Internal-Token'] = token
        try:
            connection.request('GET' if data is None else 'POST', path,
                               body=None if data is None else json.dumps(data).encode(), headers=headers)
            result = connection.getresponse(); body = result.read(65537)
            c.require(result.status == 200 and len(body) <= 65536, 'loopback_result')
            return body
        finally:
            timer.cancel(); connection.abort(); timer.join(timeout=.2)
            c.require(not timer.is_alive(), 'http_deadline_cleanup_unknown')

    def postcheck(self, identifier):
        self.inspect(identifier); current = self.compact_snapshot()
        before = private_json(ROOT / 'baseline-before.json')
        c.require(set(before.get('tables', {})) == set(TABLES), 'baseline_inventory')
        configuration = current.get('quote_uuid', '')
        c.require(isinstance(configuration, str) and re.fullmatch('[a-f0-9-]{36}', configuration), 'quote_scope')
        raw = self.raw_inspect(identifier)
        env = dict(x.split('=', 1) for x in raw['Config']['Env'])
        c.require(env.get('AUTODATA_COMMERCE_MODE') == 'read_only', 'commerce_mode')
        token = env.get('AUTODATA_INGESTION_INTERNAL_TOKEN'); c.require(bool(token), 'private_token')
        self.loopback('/healthz')
        purchase = json.loads(self.loopback('/internal/commerce/purchase-config', {}, token))
        quote = json.loads(self.loopback('/internal/commerce/quote',
                                        {'configuration_id': configuration, 'region': 'US'}, token))
        probe = b"import json;from autodata_ingestion.commerce_service import configured_commerce;s=configured_commerce();assert s.read_only and s.provider is None;print(json.dumps({'provider_none':True}))"
        provider = json.loads(self.docker('exec', '-i', identifier, '/usr/local/bin/python', '-B', '-',
                                          data=probe, timeout=5, limit=4096))
        expected = c.OLD_IDENTITY if identifier == c.OLD else self.manifest['candidate']
        final = c.identity(self.inspect(identifier), expected)
        c.require(final['running'] is True and final['pid'] > 0, 'postcheck_process_ended')
        return {'health': 200, 'purchase_enabled': purchase.get('enabled'),
                'quote_purchasable': quote.get('purchasable'), 'provider_none': provider.get('provider_none'),
                'protected27_equal': all(current['tables'][t] == before['tables'][t] for t in PROTECTED),
                'catalog12_equal': all(current['tables'][t] == before['tables'][t] for t in CATALOG),
                'public_unchanged': c.typed_equal(self.public_identity(), c.PUBLIC)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only', action='store_true', required=True)
    parser.add_argument('--phase', choices=('fixture', 'runtime'), required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args(argv)
    try: value = c.validate(c.read_manifest(args.manifest), args.phase)
    except (c.Refused, OSError, ValueError, TypeError):
        print(json.dumps({'status': 'REFUSED', 'execution_authorized': False})); return 2
    value.update(live_dispatch_enabled=False, physical_package_verified=False, live_fixture_plan_reviewed=False)
    print(json.dumps(value, sort_keys=True)); return 0


if __name__ == '__main__': raise SystemExit(main())
