#!/usr/bin/python3 -I
"""Fixed host backup lease. Adapters are injectable only by Python callers.

No cloud, snapshot, upload, provider or host-install authority is present.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import tarfile
import time
import uuid

MAX_RECEIPT = 65536
MAX_EXPORT = 1073741824
LEASE_SECONDS = 1800
RECOVERY_SECONDS = 300
ROOT = '/var/lib/autodata/operations/backups'
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'
BEGIN = ('maintenance', 'stop_writers', 'dump', 'stop_stateful', 'sync')
RESUME = ('start_stateful', 'start_apps', 'ready', 'open_ingress')


def require(value):
    if not value: raise ValueError('local backup failed')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def stamp(value): return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result); result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda _: require(False))


def load_installed(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Clock:
    def monotonic(self): return time.monotonic()
    def utc(self): return datetime.now(timezone.utc)
    def boot_id(self):
        with open('/proc/sys/kernel/random/boot_id', encoding='ascii') as source:
            value = source.read(64).strip()
        require(re.fullmatch(UUID, value)); return value


class LeaseStore:
    """Private descriptor-pinned lease files; no run may be initialized twice."""
    def __init__(self, root, run_id, *, owner=0):
        require(type(run_id) is str and re.fullmatch(UUID, run_id))
        self.root, self.path, self.owner = Path(root), Path(root) / run_id, owner
        self.root_identity = None
        self.identity = None
    def _directory(self, path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        value = os.fstat(fd)
        try:
            require(value.st_uid == self.owner and stat.S_IMODE(value.st_mode) == 0o700)
            identity = (value.st_dev, value.st_ino)
            if path == self.root:
                require(self.root_identity in (None, identity)); self.root_identity = identity
            else:
                require(self.identity in (None, identity)); self.identity = identity
            return fd
        except BaseException: os.close(fd); raise
    @contextmanager
    def directory(self):
        parent = self._directory(self.root)
        try:
            fd = os.open(self.path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            try:
                value = os.fstat(fd); identity = (value.st_dev, value.st_ino)
                require(value.st_uid == self.owner and stat.S_IMODE(value.st_mode) == 0o700)
                require(self.identity in (None, identity)); self.identity = identity
                yield fd
                current = os.stat(self.path.name, dir_fd=parent, follow_symlinks=False)
                require((current.st_dev, current.st_ino) == identity)
            finally: os.close(fd)
        finally: os.close(parent)
    def exists(self):
        parent = self._directory(self.root)
        try:
            try: os.stat(self.path.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError: return False
            return True
        finally: os.close(parent)
    def create(self, state):
        parent = self._directory(self.root)
        try: os.mkdir(self.path.name, 0o700, dir_fd=parent); os.fsync(parent)
        finally: os.close(parent)
        self.write(state)
    def write(self, state):
        data = canonical(state); require(0 < len(data) <= MAX_RECEIPT)
        with self.directory() as parent:
            try:
                prior = os.stat('lease.json',dir_fd=parent,follow_symlinks=False)
                require(stat.S_ISREG(prior.st_mode) and prior.st_uid == self.owner and prior.st_nlink == 1 and stat.S_IMODE(prior.st_mode) == 0o600)
            except FileNotFoundError: pass
            name = '.lease-' + uuid.uuid4().hex
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, 'wb', closefd=False) as target: target.write(data); target.flush(); os.fsync(fd)
                os.replace(name, 'lease.json', src_dir_fd=parent, dst_dir_fd=parent); os.fsync(parent)
            finally:
                os.close(fd)
                try: os.unlink(name, dir_fd=parent)
                except FileNotFoundError: pass
    @contextmanager
    def open_file(self, name):
        require(name in ('postgres.dump', 'lease.json'))
        with self.directory() as parent:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
            try:
                before = os.fstat(fd)
                require(stat.S_ISREG(before.st_mode) and before.st_uid == self.owner and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600)
                require(0 < before.st_size < (MAX_EXPORT if name == 'postgres.dump' else MAX_RECEIPT + 1))
                with os.fdopen(fd, 'rb', closefd=False) as source: yield source
                after = os.fstat(fd); current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_nlink) ==
                        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_nlink))
                require((current.st_dev, current.st_ino) == (before.st_dev, before.st_ino))
            finally: os.close(fd)
    def read(self):
        with self.open_file('lease.json') as source: return strict_json(source.read(MAX_RECEIPT + 1))
    @contextmanager
    def create_dump(self):
        with self.directory() as parent:
            fd = os.open('postgres.dump', os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, 'w+b', closefd=False) as target:
                    yield target
                    target.flush(); require(0 < os.fstat(fd).st_size < MAX_EXPORT); os.fsync(fd)
                os.fsync(parent)
            finally: os.close(fd)
    def dump_identity(self):
        digest, size = hashlib.sha256(), 0
        with self.open_file('postgres.dump') as source:
            while True:
                chunk = source.read(65536)
                if not chunk: break
                size += len(chunk); require(size < MAX_EXPORT); digest.update(chunk)
        return size, digest.hexdigest()


def validate_state(state, run_id):
    expected = {'schema_version','run_id','boot_id','source_sha','manifest_sha256','disk_uuid','started_at','last_utc',
                'deadline','lease_expires_at','phase','incomplete','state','dump_bytes','dump_sha256','explicit_resume'}
    require(type(state) is dict and set(state) == expected)
    require(type(state['schema_version']) is int and state['schema_version'] == 1 and state['run_id'] == run_id)
    for key, pattern in (('source_sha', r'[0-9a-f]{40}'), ('manifest_sha256', r'[0-9a-f]{64}'), ('disk_uuid', UUID), ('boot_id', UUID)):
        require(type(state[key]) is str and re.fullmatch(pattern, state[key]))
    for key in ('started_at','last_utc','lease_expires_at'):
        require(type(state[key]) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', state[key]))
        datetime.strptime(state[key], '%Y-%m-%dT%H:%M:%SZ')
    require(datetime.strptime(state['lease_expires_at'], '%Y-%m-%dT%H:%M:%SZ') - datetime.strptime(state['started_at'], '%Y-%m-%dT%H:%M:%SZ') == timedelta(seconds=LEASE_SECONDS))
    require(state['last_utc'] >= state['started_at'])
    require(type(state['deadline']) in (float, int) and 0 < state['deadline'] < 1e15)
    require(type(state['incomplete']) is bool and type(state['explicit_resume']) is bool)
    require(state['phase'] in BEGIN + RESUME + ('intent','quiesced','resumed','failed'))
    require(state['state'] in ('intent','quiesced','resumed','failed'))
    require(type(state['dump_bytes']) is int and 0 <= state['dump_bytes'] < MAX_EXPORT)
    require(state['dump_sha256'] is None or type(state['dump_sha256']) is str and re.fullmatch(r'[0-9a-f]{64}', state['dump_sha256']))
    return state


def receipt(verb, run_id, state, clock, checks, code):
    now = stamp(clock.utc())
    result = {'schema_version':1, 'operation':'backup-host.sh ' + verb, 'run_id':run_id,
              'source_sha':state.get('source_sha'), 'status':'passed' if code == 0 else 'failed',
              'started_at':state.get('started_at', now), 'finished_at':now,
              'checks':{key: value for key, value in checks.items() if value is True},
              'failure_code':None if code == 0 else {2:'invalid_input',3:'missing_dependency',4:'operation_failed',5:'timeout',6:'incomplete_recovery'}[code]}
    if state:
        result.update({key:state[key] for key in ('lease_expires_at','dump_sha256','dump_bytes','manifest_sha256','disk_uuid')})
        result['state'] = state['state'] if code == 0 else 'incomplete'
        if code == 0 and state['state'] == 'resumed': result.update(writers_resumed=True, stateful_resumed=True)
    require(len(canonical(result)) <= MAX_RECEIPT)
    return result


def _intent(state, phase, store, clock):
    state.update(phase=phase, last_utc=stamp(clock.utc()), incomplete=True)
    store.write(state)


def _recover(state, host, store, clock, *, explicit):
    end = clock.monotonic() + RECOVERY_SECONDS
    host.preflight('resume', state)
    for phase in RESUME:
        require(clock.monotonic() < end)
        _intent(state, phase, store, clock)
        host.step(phase, store, end)
    state.update(state='resumed', phase='resumed', explicit_resume=explicit)
    store.write(state)


def run_backup(verb, run_id, host, store, clock):
    state, checks = {}, {}
    if type(verb) is not str or verb not in ('begin','status','export','resume') or type(run_id) is not str or re.fullmatch(UUID, run_id) is None:
        return 2, receipt('status', None, {}, clock, {}, 2)
    mutated, primary = False, 0
    try:
        if verb == 'resume':
            state = validate_state(store.read(),run_id)
            if clock.boot_id() != state['boot_id'] or clock.monotonic() >= state['deadline'] or stamp(clock.utc()) < state['last_utc'] or stamp(clock.utc()) >= state['lease_expires_at']:
                state['incomplete'] = True
                store.write(state)
        manifest, config = host.preflight(verb)
        checks = host.checks
        if verb == 'begin':
            require(not store.exists())
            now = clock.utc()
            state = dict(schema_version=1, run_id=run_id, boot_id=clock.boot_id(), source_sha=manifest['source_sha'],
                manifest_sha256=hashlib.sha256(canonical(manifest)).hexdigest(), disk_uuid=config['resources']['data_disk_filesystem_uuid'],
                started_at=stamp(now), last_utc=stamp(now), deadline=clock.monotonic() + LEASE_SECONDS,
                lease_expires_at=stamp(now + timedelta(seconds=LEASE_SECONDS)), phase='intent', state='intent',
                incomplete=True, dump_bytes=0, dump_sha256=None, explicit_resume=False)
            store.create(state)
            end = clock.monotonic() + 300
            for phase in BEGIN:
                require(clock.monotonic() < min(end, state['deadline'] - RECOVERY_SECONDS))
                _intent(state, phase, store, clock)
                mutated = True
                host.step(phase, store, end)
                if phase == 'dump':
                    host.verify_dump(store, end)
                    state['dump_bytes'], state['dump_sha256'] = store.dump_identity()
                    store.write(state)
            host.check_stopped()
            state.update(state='quiesced', phase='quiesced', incomplete=False)
            store.write(state)
        else:
            state = validate_state(store.read(), run_id)
            require(manifest['source_sha'] == state['source_sha'] and hashlib.sha256(canonical(manifest)).hexdigest() == state['manifest_sha256'])
            require(config['resources']['data_disk_filesystem_uuid'] == state['disk_uuid'])
            abandoned = clock.boot_id() != state['boot_id'] or clock.monotonic() >= state['deadline'] or stamp(clock.utc()) < state['last_utc'] or stamp(clock.utc()) >= state['lease_expires_at']
            if verb == 'resume':
                if state['state'] != 'resumed':
                    was_incomplete = state['incomplete'] or state['phase'] != 'quiesced' or abandoned
                    state['incomplete'] = True
                    mutated = True
                    _recover(state, host, store, clock, explicit=not was_incomplete)
                    state['incomplete'] = was_incomplete
                    store.write(state)
                require(not abandoned and not state['incomplete'] and state['explicit_resume'])
                host.observe_ready()
            else:
                require(not abandoned and not state['incomplete'] and state['phase'] == state['state'])
                if state['state'] == 'quiesced': host.check_stopped()
                else: host.observe_ready()
                require(verb != 'export' or state['state'] == 'resumed' and state['explicit_resume'])
                require(store.dump_identity() == (state['dump_bytes'], state['dump_sha256']))
        return 0, receipt(verb, run_id, state, clock, checks, 0)
    except Exception as error:
        primary = 5 if isinstance(error, subprocess.TimeoutExpired) else (6 if verb == 'resume' and state else 4 if state else 3)
        if mutated:
            try:
                state['incomplete'] = True; store.write(state)
                if verb == 'begin': _recover(state, host, store, clock, explicit=False)
            except Exception: primary = 6
            finally:
                state['incomplete'] = True
                try: store.write(state)
                except Exception: primary = 6
        return primary, receipt(verb, run_id, state, clock, checks, primary)


def export_archive(store, manifest, status, output):
    """Construct/verify before emitting bytes. File is temporary, never a caller path."""
    require(status['status'] == 'passed' and status['state'] == 'resumed')
    require(store.dump_identity() == (status['dump_bytes'], status['dump_sha256']))
    import tempfile
    with tempfile.TemporaryFile() as temporary:
        with tarfile.open(fileobj=temporary, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for name, data in (('release.json', canonical(manifest)), ('backup.json', canonical(status))):
                info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o600
                archive.addfile(info, io.BytesIO(data))
            info = tarfile.TarInfo('postgres.dump'); info.size = status['dump_bytes']; info.mode = 0o600
            with store.open_file('postgres.dump') as source: archive.addfile(info, source)
        require(temporary.tell() <= MAX_EXPORT)
        temporary.seek(0)
        # Existing independent verifier is the compatibility oracle. Its input is
        # bounded to the contract cap, including tar headers and padding.
        ops = load_installed('backup_cloud_contract', str(Path(__file__).with_name('cloud-ops.py')))
        ops.verify_export(temporary.read(MAX_EXPORT + 1), manifest, status)
        temporary.seek(0)
        while True:
            chunk = temporary.read(65536)
            if not chunk: break
            output.write(chunk)
        output.flush()


def stream_dump(argv, output, timeout, maximum=MAX_EXPORT - 1):
    """Bound both pipes, persist stdout incrementally, kill all descendants."""
    end = time.monotonic() + timeout
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd='/', env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C','LC_ALL':'C','HOME':'/nonexistent'}, start_new_session=True)
    selector = selectors.DefaultSelector(); size = errors = 0
    try:
        for pipe in (process.stdout, process.stderr):
            os.set_blocking(pipe.fileno(), False); selector.register(pipe, selectors.EVENT_READ)
        while selector.get_map():
            remaining = end - time.monotonic()
            if remaining <= 0: raise subprocess.TimeoutExpired('local dump', timeout)
            events = selector.select(remaining)
            if not events: raise subprocess.TimeoutExpired('local dump', timeout)
            for key, _ in events:
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk: selector.unregister(key.fileobj); continue
                if key.fileobj is process.stdout:
                    size += len(chunk); require(size <= maximum); output.write(chunk)
                else: errors += len(chunk); require(errors <= MAX_RECEIPT)
        remaining = end - time.monotonic()
        if remaining <= 0: raise subprocess.TimeoutExpired('local dump', timeout)
        require(process.wait(timeout=remaining) == 0 and size > 0)
    finally:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        finally:
            selector.close(); process.stdout.close(); process.stderr.close(); process.wait(timeout=1)


class InstalledHost:
    """Only fixed installed paths, existing shared locks and reviewed lifecycle."""
    def __init__(self, activation, runtime, pins, end):
        self.a, self.rt, self.pins, self.end = activation, runtime, pins, end
        self.life = activation.Lifecycle(runtime, pins)
        self.life.deadline = end
        self.life.lock()
        self.checks = self.life.checks
        self.manifest = self.config = None
    def preflight(self, verb, state=None):
        require(os.geteuid() == 0)
        selected = self.a.selection(self.pins)
        require(selected is not None)
        if self.life.expected_current is None: self.life.expected_current = selected
        require(selected == self.life.expected_current)
        self.manifest, self.config = self.life.inputs(selected[0])
        if state is not None:
            require(state['source_sha'] == selected[0] and state['manifest_sha256'] == hashlib.sha256(canonical(self.manifest)).hexdigest())
            require(state['disk_uuid'] == self.config['resources']['data_disk_filesystem_uuid'])
        self.life.recheck(self.manifest, self.config)
        self.a.validate_data_directories(self.rt)
        graph = self.life.graph([self.manifest])
        require(set(graph) == set(self.a.APPS + self.a.STATEFUL + ('caddy',)))
        if verb == 'begin':
            require(all(value['running'] for value in graph.values()))
            disk = os.statvfs('/var/lib/autodata')
            require(disk.f_bavail * disk.f_frsize >= MAX_EXPORT + 1048576)
        return self.manifest, self.config
    def _graph(self):
        graph = self.life.graph([self.manifest])
        require(set(graph) == set(self.a.APPS + self.a.STATEFUL + ('caddy',)))
        return graph
    def step(self, phase, store, deadline):
        self.life.deadline = min(self.end, deadline)
        self.pins.recheck()
        require(self.a.selection(self.pins) == self.life.expected_current)
        sha = self.manifest['source_sha']
        if phase == 'maintenance': self.life.maintenance(True, self.manifest, [self.manifest])
        elif phase == 'stop_writers':
            self.life.compose(sha, 'stop', self.a.APPS)
            graph = self._graph()
            require(all(not graph[name]['running'] for name in self.a.APPS))
        elif phase == 'dump':
            graph = self._graph(); require(graph['postgres']['running'])
            require(all(not graph[name]['running'] for name in self.a.APPS))
            argv = self.a.DOCKER + ['exec','--user','999:999','--workdir','/',graph['postgres']['id'],
                '/usr/bin/env','-i','PATH=/usr/lib/postgresql/17/bin:/usr/bin:/bin','LANG=C','LC_ALL=C',
                'HOME=/nonexistent','PGPASSFILE=/dev/null','PGSERVICEFILE=/dev/null',
                '/usr/lib/postgresql/17/bin/pg_dump','--no-password','--host=/var/run/postgresql',
                '--username=autodata_admin','--dbname=autodata','--format=custom']
            with store.create_dump() as target:
                stream_dump(argv, target, max(.001, self.life.deadline - time.monotonic()))
        elif phase == 'stop_stateful': self.life.compose(sha, 'stop', self.a.STATEFUL)
        elif phase == 'sync': self.life.command(['/usr/bin/sync','-f','/var/lib/autodata'], 30)
        elif phase == 'start_stateful':
            self.life.recheck(self.manifest, self.config)
            self.life.compose(sha, 'up', self.a.STATEFUL)
            self.rt.collect_postgres_schema(self.manifest)
        elif phase == 'start_apps': self.life.compose(sha, 'up', self.a.APPS)
        elif phase == 'ready': self.observe_ready()
        elif phase == 'open_ingress':
            self.life.recheck(self.manifest, self.config)
            self.life.maintenance(False, self.manifest, [self.manifest])
        else: require(False)
    def verify_dump(self, store, deadline):
        # Verification is on the identical pinned descriptor, never a caller path.
        # docker exec cannot consume a host descriptor by path; bounded stdin is
        # streamed through the fixed container client with no shell.
        graph = self._graph(); require(graph['postgres']['running'])
        argv = self.a.DOCKER + ['exec','-i','--user','999:999','--workdir','/',graph['postgres']['id'],
            '/usr/lib/postgresql/17/bin/pg_restore','--list']
        with store.open_file('postgres.dump') as source:
            command_input_stream(argv, source, min(self.end, deadline), self.a.ENV)
    def check_stopped(self):
        graph = self._graph()
        require(graph['caddy']['running'] and all(not graph[name]['running'] for name in self.a.APPS + self.a.STATEFUL))
        self.checks['services'] = True
    def observe_ready(self):
        require(all(value['running'] for value in self._graph().values()))
        self.life.ready(self.manifest, self.config)


def command_input_stream(argv, source, deadline, environment):
    """Stream a pinned dump to pg_restore; independently bound combined output."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd='/', env=dict(environment), start_new_session=True)
    selector = selectors.DefaultSelector(); retained = 0; pending = b''
    try:
        for pipe, event in ((process.stdin, selectors.EVENT_WRITE), (process.stdout, selectors.EVENT_READ), (process.stderr, selectors.EVENT_READ)):
            os.set_blocking(pipe.fileno(), False); selector.register(pipe, event)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise subprocess.TimeoutExpired('local dump inspection', 600)
            events = selector.select(remaining)
            if not events: raise subprocess.TimeoutExpired('local dump inspection', 600)
            for key, _ in events:
                pipe = key.fileobj
                if pipe is process.stdin:
                    if not pending: pending = source.read(65536)
                    if not pending: selector.unregister(pipe); pipe.close()
                    else: pending = pending[os.write(pipe.fileno(), pending):]
                else:
                    chunk = os.read(pipe.fileno(), 65536)
                    if not chunk: selector.unregister(pipe)
                    else: retained += len(chunk); require(retained <= MAX_RECEIPT)
        require(process.wait(timeout=max(.001, deadline - time.monotonic())) == 0)
    finally:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        finally:
            selector.close()
            for pipe in (process.stdin, process.stdout, process.stderr): pipe.close()
            process.wait(timeout=1)


@contextmanager
def installed_host(seconds):
    require(os.geteuid() == 0)
    a = load_installed('autodata_backup_activation', '/opt/autodata/bin/host_activation.py')
    rt = a.runtime()
    with a.Pins() as pins:
        host = InstalledHost(a, rt, pins, time.monotonic() + seconds)
        pins.directory(ROOT, 0o700, create=True)
        yield host


def backup_cli(argv):
    clock = Clock()
    if type(argv) not in (tuple, list) or len(argv) != 2 or not all(type(item) is str for item in argv) or argv[0] not in ('begin','status','export','resume') or re.fullmatch(UUID, argv[1]) is None:
        return 2, None if argv[:1] == ['export'] else receipt('status', None, {}, clock, {}, 2)
    verb, run_id = argv
    try:
        with installed_host({'begin':600,'resume':300,'status':30,'export':300}[verb]) as host:
            store = LeaseStore(ROOT, run_id)
            code, result = run_backup(verb, run_id, host, store, clock)
            if verb == 'export':
                if code: return code, None
                # Export metadata is the fresh status receipt consumed by cloud.
                code, result = run_backup('status', run_id, host, store, clock)
                if code: return code, None
                export_archive(store, host.manifest, result, sys.stdout.buffer)
                return 0, None
            return code, result
    except Exception:
        return 3, None if verb == 'export' else receipt(verb, run_id, {}, clock, {}, 3)


def watchdog_cli():
    clock = Clock(); failures = 0; recovered = 0
    try:
        with installed_host(300) as host:
            root = host.pins.directory(ROOT, 0o700)
            runs = os.listdir(root)
            require(len(runs) <= 100 and all(re.fullmatch(UUID, item) for item in runs))
            for run_id in sorted(runs):
                require(time.monotonic() < host.end)
                store = LeaseStore(ROOT, run_id)
                state = validate_state(store.read(), run_id)
                abandoned = state['incomplete'] or state['boot_id'] != clock.boot_id() or clock.monotonic() >= state['deadline'] or stamp(clock.utc()) < state['last_utc'] or stamp(clock.utc()) >= state['lease_expires_at']
                if abandoned and (state['state'] != 'resumed' or not state['explicit_resume']):
                    state['incomplete'] = True
                    store.write(state)
                    code, _ = run_backup('resume', run_id, host, store, clock)
                    recovered += 1
                    if code: failures += 1
        return (6 if failures else 0), {'schema_version':1,'operation':'backup_restore.py watchdog','recovered':recovered,'incomplete':bool(failures)}
    except Exception:
        return 6, {'schema_version':1,'operation':'backup_restore.py watchdog','recovered':recovered,'incomplete':True}


def _alarm(signum, frame): raise subprocess.TimeoutExpired('local backup', 900)


RESTORE_PLAN_FIELDS = frozenset(('schema_version','run_id','source_sha','manifest_sha256','archive_sha256',
    'expected_disk_uuid','restore_disk_uuid','postgres_image_id','fixture_inventory_sha256'))
RELATIONS = frozenset(('schema_migrations','customer_accounts','auth_sessions','workshop_orders','entitlements',
    'vehicle_configurations','canonical_articles','canonical_article_source_revisions','source_snapshots',
    'extraction_evidence','vehicles','vehicle_identity_bases','dataset_products','dataset_requests','source_fetch_jobs'))


def validate_restore_inputs(run_id, plan, manifest, status, archive, inventory):
    require(type(plan) is dict and set(plan) == RESTORE_PLAN_FIELDS)
    require(type(plan['schema_version']) is int and plan['schema_version'] == 1 and plan['run_id'] == run_id)
    for key, pattern in (('run_id',UUID),('expected_disk_uuid',UUID),('restore_disk_uuid',UUID),
        ('source_sha',r'[0-9a-f]{40}'),('postgres_image_id',r'sha256:[0-9a-f]{64}'),
        ('manifest_sha256',r'[0-9a-f]{64}'),('archive_sha256',r'[0-9a-f]{64}'),('fixture_inventory_sha256',r'[0-9a-f]{64}')):
        require(type(plan[key]) is str and re.fullmatch(pattern,plan[key]))
    require(plan['restore_disk_uuid'] != plan['expected_disk_uuid'])
    require(manifest['source_sha'] == plan['source_sha'])
    require(manifest['images']['postgres']['image_id'] == plan['postgres_image_id'])
    require(hashlib.sha256(canonical(manifest)).hexdigest() == plan['manifest_sha256'])
    require(type(archive) is bytes and 0 < len(archive) <= MAX_EXPORT and hashlib.sha256(archive).hexdigest() == plan['archive_sha256'])
    require(type(inventory) is dict and set(inventory) == {'schema_version','relations','objects','jetstream'})
    require(type(inventory['schema_version']) is int and inventory['schema_version'] == 1)
    encoded = canonical(inventory)
    require(len(encoded) <= 1048576 and hashlib.sha256(encoded).hexdigest() == plan['fixture_inventory_sha256'])
    relations, objects, jetstream = inventory['relations'], inventory['objects'], inventory['jetstream']
    require(type(relations) is dict and set(relations) <= RELATIONS and 'schema_migrations' in relations)
    require(all(type(rows) is list and all(type(row) is dict for row in rows) for rows in relations.values()))
    require(type(objects) is list and type(jetstream) is dict)
    require(sum(len(rows) for rows in relations.values()) + len(objects) + len(jetstream) <= 1000)
    for obj in objects:
        require(type(obj) is dict and set(obj) == {'bucket','key','sha256','bytes'})
        require(type(obj['bucket']) is str and re.fullmatch(r'[a-z][a-z0-9-]{2,62}',obj['bucket']))
        require(type(obj['key']) is str and 1 <= len(obj['key']) <= 1024 and not obj['key'].startswith('/') and all(part not in ('','.','..') for part in obj['key'].split('/')))
        require(type(obj['sha256']) is str and re.fullmatch(r'[0-9a-f]{64}',obj['sha256']))
        require(type(obj['bytes']) is int and 0 < obj['bytes'] <= 1048576)
    migrations = manifest['migrations']['files']
    require(type(migrations) is list and 0 < len(migrations) <= 1000)
    names = [item['name'] for item in migrations]
    require(names == sorted(set(names)) and all(type(name) is str and re.fullmatch(r'[0-9]{3}_[a-z0-9_]+\.sql',name) for name in names))
    require(sorted(row['version'] for row in relations['schema_migrations']) == [name[:-4] for name in names])
    ops = load_installed('restore_cloud_contract', str(Path(__file__).with_name('cloud-ops.py')))
    ops._host(status, 'status', 'resumed', manifest, {'resources':{'data_disk_filesystem_uuid':plan['expected_disk_uuid']}}, run_id)
    return ops.verify_export(archive, manifest, status)


def run_restore(verb, run_id, target, store, clock):
    """Portable verification only. Cleanup failure overrides data success."""
    code, failure, created, clean = 2, 'invalid_input', False, False
    started = stamp(clock.utc()); source_sha = None
    if type(verb) is str and verb in ('restore','validate') and type(run_id) is str and re.fullmatch(UUID,run_id):
        try:
            plan, manifest, status, archive, inventory = target.preflight(verb, run_id)
            members = validate_restore_inputs(run_id, plan, manifest, status, archive, inventory)
            source_sha = plan['source_sha']
            created = True
            target.create(plan, manifest)
            target.restore_dump(members['postgres.dump'])
            observed = target.inspect(inventory)
            failure = 'inventory_mismatch'
            require(canonical(observed) == canonical(inventory))
            code, failure = 0, None
        except subprocess.TimeoutExpired:
            code, failure = 5, 'timeout'
        except Exception:
            code = 4
            if failure != 'inventory_mismatch': failure = 'input_or_restore_failed'
        finally:
            if created:
                try: target.cleanup(); clean = True
                except Exception: code, failure = 6, 'cleanup_failed'
    return code, {'schema_version':1,'operation':'restore.sh '+str(verb),'run_id':run_id,
        'source_sha':source_sha,'status':'passed' if code == 0 else 'failed', 'started_at':started,
        'finished_at':stamp(clock.utc()),'checks':{'portable_restore':code == 0},'failure_code':failure,
        'cleanup_verified':clean,'production_recovery_verified':False}

PINNED_FIXTURE_IMAGES = {
    'postgres':'sha256:151aa1c2e849e7828ed8aef2183ae15f692cbe887d2f28921d8b44b26e154d7e',
    'nats':'sha256:8b9f712ae2148dcbd9d7f3d16a942d515e290526e5d018500931eab62b18e045',
    'minio':'sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5'}
DOCKER = ['/usr/bin/docker','--host','unix:///var/run/docker.sock']
SYNTHETIC_S3_ACCESS = 'fixture-access'
SYNTHETIC_S3_SECRET = 'fixture-secret'


def archive_metadata(archive):
    """Inspect at most three raw USTAR headers before parsing bounded metadata."""
    require(type(archive) is bytes and 1024 <= len(archive) <= MAX_EXPORT)
    metadata, names, offset = {}, set(), 0
    while offset + 512 <= len(archive):
        header = archive[offset:offset+512]
        if header == b'\0'*512: break
        require(len(names) < 3 and header[257:263] == b'ustar\0')
        member = tarfile.TarInfo.frombuf(header,'utf-8','strict')
        require(member.name in ('postgres.dump','release.json','backup.json') and member.name not in names)
        require(member.type in (tarfile.REGTYPE,tarfile.AREGTYPE) and not member.linkname and not member.pax_headers)
        names.add(member.name)
        limit = MAX_EXPORT-1 if member.name == 'postgres.dump' else MAX_RECEIPT if member.name == 'backup.json' else 1048576
        require(0 < member.size <= limit)
        start = offset+512; end = start+member.size
        offset = start+((member.size+511)//512)*512
        require(offset <= len(archive))
        if member.name != 'postgres.dump': metadata[member.name] = strict_json(archive[start:end])
    require(names == {'postgres.dump','release.json','backup.json'})
    return metadata['release.json'],metadata['backup.json']


class InstalledRestoreTarget:
    """Fixed synthetic portable target; all resources are owned and disposable.

    The trusted per-run plan authorizes exact input hashes, never a command,
    connection string, production credential or arbitrary host path.
    """
    def __init__(self, activation, pins, run_id):
        self.a, self.pins, self.run_id = activation, pins, run_id
        self.root = '/var/lib/autodata-restore/' + run_id
        self.prefix = 'autodata-restore-' + run_id
        self.labels = {'io.autodata.restore.run':run_id}
        self.created = []; self.containers = {}; self.owned_tokens = {}; self.cold_files = []; self.end = time.monotonic() + 780
    def command(self, args, timeout=30, input_data=None, maximum=1048576):
        self.pins.recheck()
        return self.a.bounded_command(DOCKER + args, timeout=timeout, deadline=self.end, input_data=input_data, maximum=maximum)
    def json(self, args): return strict_json(self.command(args))
    def preflight(self, verb, run_id):
        require(run_id == self.run_id and os.geteuid() == 0)
        plans = self.pins.directory('/etc/autodata/restore',0o700)
        self.plan = strict_json(self.pins.pin(plans,run_id+'.json'))
        root = self.pins.directory(self.root,0o700)
        require(set(os.listdir(root)) == ({'input'} if verb == 'restore' else {'input','result'}))
        data = self.pins.directory('/var/lib/autodata')
        require(os.fstat(root).st_dev != os.fstat(data).st_dev)
        mount = strict_json(self.a.bounded_command(['/usr/bin/findmnt','--json','--list','--mountpoint',self.root,'--output','TARGET,UUID,FSTYPE,OPTIONS'],timeout=5,deadline=self.end))
        require(type(mount) is dict and set(mount) == {'filesystems'} and len(mount['filesystems']) == 1)
        observed = mount['filesystems'][0]
        require(observed['target'] == self.root and observed['uuid'] == self.plan['restore_disk_uuid'] and observed['uuid'] != self.plan['expected_disk_uuid'])
        require(observed['fstype'] == 'ext4' and 'rw' in observed['options'].split(','))
        inputs = self.pins.directory(self.root+'/input',0o700)
        require(set(os.listdir(inputs)) == {'export.tar','inventory.json','cold-state'})
        archive = self.pins.read(inputs,'export.tar',maximum=MAX_EXPORT)
        inventory = strict_json(self.pins.pin(inputs,'inventory.json'))
        manifest, status = archive_metadata(archive)
        self.cold = self.root+'/input/cold-state'
        cold = self.pins.directory(self.cold,0o700)
        require(set(os.listdir(cold)) == {'nats','minio'})
        # Pin every cold-state file and directory before docker cp. Symlinks and
        # hardlinks are never admitted; retained data is bounded as a whole.
        count = total = 0
        for current, dirs, files in os.walk(self.cold, followlinks=False):
            parent = self.pins.directory(current,0o700)
            for name in dirs: self.pins.directory(current+'/'+name,0o700)
            for name in files:
                count += 1; require(count <= 1000)
                payload = self.pins.read(parent,name,maximum=MAX_EXPORT,empty=True)
                self.cold_files.append((current,name,hashlib.sha256(payload).hexdigest(),len(payload)))
                total += len(payload); require(total <= MAX_EXPORT)
        self.result = self.root+'/result'
        exists = 'result' in os.listdir(root)
        require(not exists if verb == 'restore' else exists)
        if exists:
            previous = self.pins.directory(self.result,0o700)
            record = strict_json(self.pins.pin(previous,'restore.json'))
            require(record['run_id'] == run_id and record['archive_sha256'] == self.plan['archive_sha256'])
        # Approved local fixture pins cannot become a caller-selected image.
        require(self.plan['postgres_image_id'] == PINNED_FIXTURE_IMAGES['postgres'])
        for role, image in PINNED_FIXTURE_IMAGES.items():
            value = self.json(['image','inspect','--format','{{json .}}',image])
            require(value['Id'] == image and value['Os'] == 'linux' and value['Architecture'] == 'amd64')
            if role == 'postgres': require('PG_MAJOR=17' in value['Config']['Env'])
            if role == 'minio': require('ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d' in value['RepoDigests'])
        # No guessed daemon context or ambient DOCKER_HOST is used.
        for kind in ('container','network','volume'):
            names = self.command([kind,'ls'] + (['--all'] if kind == 'container' else []) + ['--format','{{.Names}}' if kind == 'container' else '{{.Name}}']).decode().splitlines()
            require(not any(name == self.prefix or name.startswith(self.prefix+'-') for name in names))
        return self.plan, manifest, status, archive, inventory
    def _owned(self, kind, identity):
        values = self.json([kind,'inspect',identity]); require(type(values) is list and len(values) == 1)
        value = values[0]
        labels = value['Config']['Labels'] if kind == 'container' else value['Labels']
        require(type(labels) is dict and all(labels.get(key) == value for key,value in self.labels.items()))
        require(value['Name'].lstrip('/').startswith(self.prefix))
        if kind == 'volume':
            mount = os.stat(value['Mountpoint'],follow_symlinks=False)
            require(stat.S_ISDIR(mount.st_mode))
            token = canonical({key:value[key] for key in ('Name','CreatedAt','Driver','Options','Mountpoint','Labels')}) + canonical([mount.st_dev,mount.st_ino])
        else:
            require(value['Id'] == identity)
            token = canonical([value['Id'],value['Name'],labels])
        key = (kind,identity)
        require(key not in self.owned_tokens or self.owned_tokens[key] == token)
        self.owned_tokens[key] = token
        return value
    def create(self, plan, manifest):
        require(plan == self.plan and plan['postgres_image_id'] == PINNED_FIXTURE_IMAGES['postgres'])
        label = 'io.autodata.restore.run='+self.run_id
        network = self.command(['network','create','--internal','--label',label,self.prefix]).decode().strip()
        require(re.fullmatch(r'[0-9a-f]{64}',network))
        self.created.append(('network',network)); observation = self._owned('network',network)
        require(observation['Internal'] is True and observation['Driver'] == 'bridge')
        for role in ('postgres','nats','minio'):
            volume = self.prefix+'-'+role
            self.command(['volume','create','--label',label,volume])
            observation = self._owned('volume',volume)
            require(observation['Driver'] == 'local' and not observation['Options'])
            self.created.append(('volume',volume))
            destination = '/var/lib/postgresql/data' if role == 'postgres' else '/data'
            options = ['container','create','--pull=never','--name',self.prefix+'-'+role,'--label',label,
                '--network',self.prefix,'--cpus','1','--memory','512m' if role == 'postgres' else '256m',
                '--pids-limit','128','--security-opt','no-new-privileges:true',
                '--log-driver','json-file','--log-opt','max-size=16m','--log-opt','max-file=1',
                '--mount','type=volume,source='+volume+',destination='+destination]
            if role != 'postgres': options += ['--user','0:0','--entrypoint','/usr/bin/weed' if role == 'minio' else '/nats-server']
            if role == 'postgres': options += ['--env','POSTGRES_HOST_AUTH_METHOD=trust','--env','POSTGRES_DB=autodata']
            command = []
            if role == 'nats': command = ['-js','-sd','/data','--user','fixture-user','--pass','fixture-password']
            if role == 'minio': command = ['mini','-dir=/data','-s3.port=9000','-s3.config=/tmp/fixture-s3.json',
                '-admin.ui=false','-webdav=false','-s3.iam=false','-s3.port.iceberg=0','-s3.port.lance=0','-master.telemetry=false','-volume.max=1','-volumeSizeLimitMB=16']
            identity = self.command(options+[PINNED_FIXTURE_IMAGES[role]]+command).decode().strip()
            require(re.fullmatch(r'[0-9a-f]{64}',identity))
            self.created.append(('container',identity)); self.containers[role] = identity
            value = self._owned('container',identity)
            require(not value['HostConfig']['Privileged'] and not value['HostConfig']['PortBindings'])
            require(value['Image'] == PINNED_FIXTURE_IMAGES[role])
            if role != 'postgres': self.copy_cold(role,identity)
            if role == 'minio':
                config = canonical({'identities':[{'name':'fixture','credentials':[{'accessKey':SYNTHETIC_S3_ACCESS,'secretKey':SYNTHETIC_S3_SECRET}], 'actions':['Read','Write','List','Admin']}]})
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as archive:
                    entry=tarfile.TarInfo('fixture-s3.json'); entry.size=len(config); entry.mode=0o600
                    archive.addfile(entry,io.BytesIO(config))
                self.command(['cp','-',identity+':/tmp'],input_data=buffer.getvalue())
            self.command(['container','start',identity])
        for _ in range(60):
            try:
                require(self.sql('SHOW server_version_num;').strip().startswith(b'17')); break
            except Exception: time.sleep(.2)
        else: require(False)
    def copy_cold(self, role, identity):
        import tempfile
        with tempfile.TemporaryFile() as output:
            with tarfile.open(fileobj=output,mode='w',format=tarfile.USTAR_FORMAT) as archive:
                for directory,name,digest,size in self.cold_files:
                    relative = os.path.relpath(directory+'/'+name,self.cold+'/'+role)
                    if relative.startswith('../'): continue
                    parent = self.pins.directory(directory,0o700)
                    payload = self.pins.read(parent,name,maximum=MAX_EXPORT,empty=True)
                    require(len(payload) == size and hashlib.sha256(payload).hexdigest() == digest)
                    entry = tarfile.TarInfo(relative); entry.size=size; entry.mode=0o600
                    archive.addfile(entry,io.BytesIO(payload))
            require(output.tell() <= MAX_EXPORT)
            output.seek(0)
            command_input_stream(DOCKER+['cp','-',identity+':/data'],output,self.end,self.a.ENV)
    def sql(self, query):
        return self.command(['exec','-i',self.containers['postgres'],'/usr/bin/env','-i',
            'PATH=/usr/lib/postgresql/17/bin:/usr/bin:/bin','LANG=C','LC_ALL=C','HOME=/nonexistent',
            '/usr/lib/postgresql/17/bin/psql','-X','-A','-t','-q','-v','ON_ERROR_STOP=1',
            '-h','/var/run/postgresql','-U','postgres','-d','autodata'],input_data=query.encode())
    def restore_dump(self, data):
        self.pins.recheck()
        require(type(data) is bytes and 0 < len(data) < MAX_EXPORT)
        # Streaming stdin uses the same bounded process-group primitive as dump
        # inspection; no caller-controlled SQL or connection argument exists.
        argv = DOCKER+['exec','-i',self.containers['postgres'],'/usr/lib/postgresql/17/bin/pg_restore',
            '--exit-on-error','--no-owner','--no-privileges','--host=/var/run/postgresql','--username=postgres','--dbname=autodata']
        command_input_stream(argv,io.BytesIO(data),self.end,self.a.ENV)
    def address(self, role):
        value = self._owned('container',self.containers[role])
        require(value['State']['Running'] and not value['State']['OOMKilled'])
        require(value['HostConfig']['NetworkMode'] == self.prefix and not value['HostConfig']['PortBindings'])
        networks = value['NetworkSettings']['Networks']; require(set(networks) == {self.prefix})
        address = networks[self.prefix]['IPAddress']
        import ipaddress
        require(ipaddress.ip_address(address).is_private)
        return address
    def inspect(self, inventory):
        observed = {'schema_version':1,'relations':{},'objects':[],'jetstream':{}}
        for table in sorted(inventory['relations']):
            require(table in RELATIONS)
            # Table names come from the fixed allowlist. Values/SQL never come
            # from inventory. LIMIT detects overflow without unbounded output.
            data = self.sql('SELECT COALESCE(json_agg(row_to_json(t)),\'[]\'::json) FROM (SELECT * FROM public.'+table+' LIMIT 1001) t;')
            rows = strict_json(data); require(type(rows) is list and len(rows) <= 1000)
            observed['relations'][table] = sorted(rows,key=canonical)
        for obj in inventory['objects']:
            payload = s3_read(self.address('minio'),obj['bucket'],obj['key'])
            observed['objects'].append({'bucket':obj['bucket'],'key':obj['key'],'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload)})
        if inventory['jetstream']: observed['jetstream'] = inspect_jetstream(self.address('nats'),inventory['jetstream'])
        for role in self.containers: self.address(role)
        return observed
    def cleanup(self):
        # Cleanup has its own finite reserve even after the workload deadline.
        self.end = time.monotonic()+120
        failures=[]
        for kind, identity in reversed(self.created):
            try:
                value = self._owned(kind,identity)
                if kind == 'container':
                    if value['State']['OOMKilled']: failures.append('oom')
                    self.command([kind,'rm','--force',identity])
                else: self.command([kind,'rm',identity])
            except Exception: failures.append(kind)
        for kind in ('container','network','volume'):
            try:
                names = self.command([kind,'ls']+(['--all'] if kind=='container' else [])+['--filter','label=io.autodata.restore.run='+self.run_id,'--quiet'])
                require(not names.strip())
            except Exception: failures.append(kind)
        require(not failures)


def s3_read(address, bucket, key):
    """Fixed synthetic credentials and local target; no proxy or ambient auth."""
    import hmac
    import http.client
    from urllib.parse import quote
    now = datetime.now(timezone.utc); date = now.strftime('%Y%m%d'); timestamp = now.strftime('%Y%m%dT%H%M%SZ')
    host = address+':9000'; path = '/'+quote(bucket,safe='')+'/'+quote(key,safe='/')
    empty = hashlib.sha256(b'').hexdigest()
    headers = 'host:'+host+'\nx-amz-content-sha256:'+empty+'\nx-amz-date:'+timestamp+'\n'
    signed = 'host;x-amz-content-sha256;x-amz-date'
    request = 'GET\n'+path+'\n\n'+headers+'\n'+signed+'\n'+empty
    scope = date+'/us-east-1/s3/aws4_request'
    string = 'AWS4-HMAC-SHA256\n'+timestamp+'\n'+scope+'\n'+hashlib.sha256(request.encode()).hexdigest()
    key_bytes = ('AWS4'+SYNTHETIC_S3_SECRET).encode()
    for value in (date,'us-east-1','s3','aws4_request'): key_bytes = hmac.new(key_bytes,value.encode(),hashlib.sha256).digest()
    signature = hmac.new(key_bytes,string.encode(),hashlib.sha256).hexdigest()
    connection = http.client.HTTPConnection(address,9000,timeout=5)
    try:
        connection.request('GET',path,headers={'Host':host,'x-amz-date':timestamp,'x-amz-content-sha256':empty,
            'Authorization':'AWS4-HMAC-SHA256 Credential='+SYNTHETIC_S3_ACCESS+'/'+scope+', SignedHeaders='+signed+', Signature='+signature})
        response = connection.getresponse(); require(response.status == 200)
        payload = response.read(1048577); require(len(payload) <= 1048576)
        return payload
    finally: connection.close()


def nats_request(address, subject, body):
    import socket
    require(type(subject) is str and re.fullmatch(r'\$JS\.API\.[A-Z._a-z0-9-]{1,200}',subject))
    payload = canonical(body); require(len(payload) <= 1048576)
    with socket.create_connection((address,4222),timeout=5) as connection:
        connection.settimeout(5)
        with connection.makefile('rb') as stream:
            greeting = stream.readline(65537); require(greeting.startswith(b'INFO ') and len(greeting) <= 65536)
            auth = canonical({'verbose':False,'pedantic':True,'user':'fixture-user','pass':'fixture-password'})
            inbox = '_INBOX.fixture'+uuid.uuid4().hex
            connection.sendall(b'CONNECT '+auth+b'\r\nSUB '+inbox.encode()+b' 1\r\nPUB '+subject.encode()+b' '+inbox.encode()+b' '+str(len(payload)).encode()+b'\r\n'+payload+b'\r\nPING\r\n')
            for _ in range(20):
                line = stream.readline(65537); require(0 < len(line) <= 65536)
                if line == b'PING\r\n': connection.sendall(b'PONG\r\n'); continue
                if line.startswith(b'MSG '):
                    fields = line.split(); require(len(fields) in (4,5))
                    size = int(fields[-1]); require(0 < size <= 1048576)
                    data = stream.read(size); require(len(data) == size and stream.read(2) == b'\r\n')
                    value = strict_json(data); require(type(value) is dict and 'error' not in value)
                    return value
                require(line in (b'+OK\r\n',b'PONG\r\n') or line.startswith(b'INFO '))
    require(False)


def inspect_jetstream(address, expected):
    import base64
    keys = {'stream','sequence','subject','payload_sha256','consumer','delivered_stream_seq','ack_floor_stream_seq','messages'}
    require(type(expected) is dict and set(expected) == keys)
    for key in ('stream','consumer','subject'):
        require(type(expected[key]) is str and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*',expected[key]))
    for key in ('sequence','delivered_stream_seq','ack_floor_stream_seq','messages'): require(type(expected[key]) is int and 0 <= expected[key] <= 1000)
    stream = expected['stream']; consumer = expected['consumer']
    info = nats_request(address,'$JS.API.STREAM.INFO.'+stream,{})
    message = nats_request(address,'$JS.API.STREAM.MSG.GET.'+stream,{'seq':expected['sequence']})['message']
    state = nats_request(address,'$JS.API.CONSUMER.INFO.'+stream+'.'+consumer,{})
    data = base64.b64decode(message['data'],validate=True); require(len(data) <= 1048576)
    return {'stream':info['config']['name'],'sequence':message['seq'],'subject':message['subject'],
        'payload_sha256':hashlib.sha256(data).hexdigest(),'consumer':state['name'],
        'delivered_stream_seq':state['delivered']['stream_seq'],'ack_floor_stream_seq':state['ack_floor']['stream_seq'],
        'messages':info['state']['messages']}


def restore_cli(argv):
    clock = Clock()
    if type(argv) not in (tuple,list) or len(argv) != 2 or argv[0] not in ('restore','validate') or type(argv[1]) is not str or re.fullmatch(UUID,argv[1]) is None:
        return run_restore('invalid',None,None,None,clock)
    verb, run_id = argv
    try:
        require(os.geteuid() == 0)
        a = load_installed('autodata_restore_activation','/opt/autodata/bin/host_activation.py')
        with a.Pins() as pins:
            # Reuse the established lock order without selecting a production
            # release, loading credentials or starting any production service.
            locks = a.Lifecycle(a.runtime(),pins); locks.lock()
            target = InstalledRestoreTarget(a,pins,run_id)
            code, result = run_restore(verb,run_id,target,None,clock)
            if target.created:
                directory = pins.directory(target.result,0o700,create=True)
                evidence = {'run_id':run_id,'archive_sha256':target.plan['archive_sha256'],'receipt':result}
                filename = 'restore.json' if verb == 'restore' else 'validate-'+uuid.uuid4().hex+'.json'
                a.materialize(pins,directory,filename,canonical(evidence))
            return code,result
    except Exception:
        code, result = run_restore('invalid',run_id,None,None,clock)
        result.update(operation='restore.sh '+verb,failure_code='missing_dependency')
        return 3,result


if __name__ == '__main__':
    args = sys.argv[1:]
    signal.signal(signal.SIGALRM,_alarm)
    signal.setitimer(signal.ITIMER_REAL,900 if args[:1] == ['restore-target'] else 600 if args[:2] == ['backup','begin'] else 300)
    try:
        if args[:1] == ['restore-target']: code,result = restore_cli(args[1:])
        elif args[:1] == ['backup']: code,result = backup_cli(args[1:])
        elif args == ['watchdog']: code,result = watchdog_cli()
        else: code,result = 2,receipt('status',None,{},Clock(),{},2)
        if result is not None: sys.stdout.write(canonical(result).decode()+'\n')
        if code and args[:2] == ['backup','export']: sys.stderr.write('local backup failed\n')
    finally: signal.setitimer(signal.ITIMER_REAL,0)
    raise SystemExit(code)
