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
        sha = self.manifest['source_sha']
        if phase == 'maintenance': self.life.maintenance(True, self.manifest, [self.manifest])
        elif phase == 'stop_writers':
            self.life.compose(sha, 'stop', self.a.APPS)
            require(all(not self._graph()[name]['running'] for name in self.a.APPS))
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
    if type(argv) not in (tuple, list) or len(argv) != 2 or argv[0] not in ('begin','status','export','resume') or re.fullmatch(UUID, argv[1]) is None:
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


def main(argv):
    # SIGALRM bounds even filesystem/input work; child adapters kill process
    # groups in finally. systemd adds its own independent 330-second bound.
    signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, 600 if argv[:1] == ['begin'] else 300)
    try: return watchdog_cli() if argv == ['watchdog'] else backup_cli(argv)
    finally: signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    code, result = main(sys.argv[1:])
    if result is not None: sys.stdout.write(canonical(result).decode() + '\n')
    if code and sys.argv[1:2] == ['export']: sys.stderr.write('local backup failed\n')
    raise SystemExit(code)
