#!/usr/bin/python3 -I
"""Fixed local release lifecycle; provisioning and credentials remain external."""
from contextlib import ExitStack, contextmanager
import fcntl
import importlib.util
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import time
import uuid

OPT = '/opt/autodata'
RELEASES = OPT + '/releases'
DATA = '/var/lib/autodata'
RUN = '/run/autodata'
HELPER = OPT + '/bin/runtime-check.py'
DOCKER = ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock']
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'HOME': '/nonexistent'}
MAXIMUM = 1048576
SHA = r'[0-9a-f]{40}'
MAINTENANCE = b'respond "Maintenance" 503\n'
APPS = ('api', 'ingestion-http', 'article-worker', 'payment-reconciler')
STATEFUL = ('postgres', 'nats', 'minio')


class ActivationError(ValueError):
    def __init__(self): super().__init__('local activation failed')


def require(value):
    if not value: raise ActivationError()


def bounded_command(argv, timeout=5, deadline=None, maximum=MAXIMUM, input_data=None):
    """Streaming bounded capture; exceptions never contain command output.

    Start a session so timeout/cancellation also kills CLI descendants. Docker
    daemon operations have their own bounded stop/reload timeouts as well.
    """
    end = min(time.monotonic() + timeout, deadline if deadline is not None else float('inf'))
    if time.monotonic() >= end: raise subprocess.TimeoutExpired('local operation', timeout)
    require(input_data is None or type(input_data) is bytes and len(input_data) <= maximum)
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='/', env=dict(ENV), start_new_session=True)
    selector = selectors.DefaultSelector()
    output = bytearray()
    retained = 0
    try:
        for pipe in (process.stdout, process.stderr):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ)
        if input_data is not None:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE)
        pending = memoryview(input_data or b'')
        while selector.get_map():
            remaining = end - time.monotonic()
            if remaining <= 0: raise subprocess.TimeoutExpired('local operation', timeout)
            events = selector.select(remaining)
            if not events: raise subprocess.TimeoutExpired('local operation', timeout)
            for key, _ in events:
                pipe = key.fileobj
                if pipe is process.stdin:
                    if pending:
                        count = os.write(pipe.fileno(), pending[:4096]); pending = pending[count:]
                    if not pending:
                        selector.unregister(pipe); pipe.close()
                    continue
                chunk = os.read(pipe.fileno(), min(4096, maximum + 1 - retained))
                if not chunk:
                    selector.unregister(pipe); continue
                retained += len(chunk)
                require(retained <= maximum)
                if pipe is process.stdout: output.extend(chunk)
        remaining = end - time.monotonic()
        if remaining <= 0: raise subprocess.TimeoutExpired('local operation', timeout)
        require(process.wait(timeout=remaining) == 0)
        return bytes(output)
    finally:
        # Even a reaped parent can leave children holding a pipe open.
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        finally:
            selector.close()
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None: pipe.close()
            process.wait(timeout=1)


def ident(value): return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid)


class Pins:
    """Pin every ancestor descriptor and reject replaced/untrusted entries."""
    def __init__(self): self.stack = ExitStack(); self.dirs = {}; self.files = []
    def __enter__(self): return self
    def __exit__(self, *args): return self.stack.__exit__(*args)
    def directory(self, path, mode=None, create=False):
        require(path.startswith('/'))
        if path in self.dirs:
            fd = self.dirs[path][0]
        else:
            if path == '/':
                parent, name = None, '/'
            else:
                prefix, name = path.rsplit('/', 1)
                parent = self.directory(prefix or '/')
                if create:
                    try: os.mkdir(name, 0o700, dir_fd=parent); os.fsync(parent)
                    except FileExistsError: pass
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            self.stack.callback(os.close, fd)
            self.dirs[path] = (fd, parent, name, ident(os.fstat(fd)))
        value = os.fstat(fd)
        require(stat.S_ISDIR(value.st_mode) and value.st_uid == 0 and value.st_gid == 0 and not value.st_mode & 0o022)
        if mode is not None: require(stat.S_IMODE(value.st_mode) == mode)
        return fd
    def read(self, parent, name, mode=0o600, maximum=MAXIMUM, empty=False):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_gid == 0 and before.st_nlink == 1)
            require(stat.S_IMODE(before.st_mode) == mode and (0 if empty else 1) <= before.st_size <= maximum)
            data = bytearray()
            while len(data) <= maximum:
                chunk = os.read(fd, min(65536, maximum + 1 - len(data)))
                if not chunk: break
                data.extend(chunk)
            after = os.fstat(fd)
            require(len(data) == before.st_size and ident(before) == ident(after) and
                    (before.st_nlink,before.st_size,before.st_mtime,before.st_ctime) ==
                    (after.st_nlink,after.st_size,after.st_mtime,after.st_ctime))
            require(ident(os.stat(name, dir_fd=parent, follow_symlinks=False)) == ident(before))
            return bytes(data)
        finally: os.close(fd)
    def pin(self, parent, name, mode=0o600):
        data = self.read(parent, name, mode)
        self.files.append((parent, name, mode, ident(os.stat(name, dir_fd=parent, follow_symlinks=False)), data))
        return data
    def recheck(self):
        for fd, parent, name, original in self.dirs.values():
            require(ident(os.fstat(fd)) == original)
            if parent is not None: require(ident(os.stat(name, dir_fd=parent, follow_symlinks=False)) == original)
        for parent, name, mode, original, data in self.files:
            require(ident(os.stat(name, dir_fd=parent, follow_symlinks=False)) == original and self.read(parent, name, mode) == data)


def materialize(pins, directory, name, data):
    require(type(data) is bytes and 0 < len(data) <= MAXIMUM and b'${' not in data)
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
    except FileExistsError:
        require(pins.read(directory, name) == data)
    else:
        try:
            os.fchmod(fd, 0o600)
            offset = 0
            while offset < len(data): offset += os.write(fd, data[offset:])
            os.fsync(fd)
        finally: os.close(fd)
        os.fsync(directory)
    require(pins.pin(directory, name) == data)
    pins.recheck()


def selection(pins):
    directory = pins.directory(OPT)
    try: value = os.stat('current', dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError: return None
    require(stat.S_ISLNK(value.st_mode) and value.st_uid == 0 and value.st_gid == 0)
    target = os.readlink('current', dir_fd=directory)
    require(re.fullmatch(re.escape(RELEASES) + '/' + SHA, target) is not None)
    return (target.rsplit('/', 1)[1], ident(value))


def select(pins, source_sha, previous, on_publish=None):
    require(re.fullmatch(SHA, source_sha) is not None and selection(pins) == previous)
    pins.recheck()
    directory = pins.directory(OPT)
    name = '.current-' + uuid.uuid4().hex
    os.symlink(RELEASES + '/' + source_sha, name, dir_fd=directory)
    try:
        require(selection(pins) == previous)
        published = (source_sha,ident(os.stat(name,dir_fd=directory,follow_symlinks=False)))
        os.replace(name, 'current', src_dir_fd=directory, dst_dir_fd=directory)
        # Record the precise inode at publication, before durability can fail.
        if on_publish is not None: on_publish(published)
        os.fsync(directory)
    finally:
        try: os.unlink(name, dir_fd=directory)
        except FileNotFoundError: pass


def runtime():
    spec = importlib.util.spec_from_file_location('autodata_runtime_activation', HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module




def validate_data_directories(rt):
    """Never initialize an absent PostgreSQL or service data directory."""
    with ExitStack() as stack:
        root = rt._owned_directory(DATA)
        stack.callback(os.close, root)
        for name, uid in (('postgres',999),('nats',1000),('seaweedfs',1000),('caddy',0)):
            fd = rt._owned_directory(name,uid,uid,parent=root)
            stack.callback(os.close,fd)
            if name == 'postgres':
                pgdata = rt._owned_directory('pgdata',999,999,0o700,parent=fd)
                stack.callback(os.close,pgdata)
                require(rt._owned_bytes(pgdata,'PG_VERSION',999,999,0o600,16) == b'17\n')
    return True


class Lifecycle:
    def __init__(self, rt, pins):
        self.rt, self.pins = rt, pins
        self.end = time.monotonic() + 120
        self.deadline = self.end - 30
        self.checks = {}
        self.operations = None
        self.lockfiles = []
        self.mutated = False
        self.expected_current = None

    def command(self, argv, timeout=5):
        self.pins.recheck()
        return bounded_command(argv,timeout=timeout,deadline=self.deadline)

    def mounts(self, config):
        values = []
        for target in (DATA,RUN):
            output = self.command(['/usr/bin/findmnt','--json','--list','--mountpoint',target,'--output','TARGET,UUID,FSTYPE,OPTIONS'])
            values.append(self.rt.strict_json(output))
        self.rt.validate_mount_observations(config,*values)
        self.checks['disk_uuid'] = True

    def prerequisites(self, manifest, config):
        self.pins.recheck()
        self.mounts(config)
        code, _ = self.rt.guard_cli()
        if code == 5: raise subprocess.TimeoutExpired('local guard observation',5)
        require(code == 0)
        self.checks.update(metadata_guard=True,storage_guard=True)
        self.rt.validate_runtime_secret_files()
        self.checks['secrets'] = True
        self.rt.collect_cached_images(manifest)
        self.checks['cached_images'] = True
        self.rt.validate_installed_migration_tree(manifest)
        self.checks['migration_tree'] = True
        require(time.monotonic() < self.deadline)

    def inputs(self, sha):
        manifest,config = self.rt._installed_deploy_inputs(sha)
        host = self.pins.directory(os.path.dirname(self.rt.HOST_CONFIG))
        require(self.rt.strict_json(self.pins.pin(host,os.path.basename(self.rt.HOST_CONFIG))) == config)
        directory = self.pins.directory(RELEASES + '/' + sha)
        require(self.rt.strict_json(self.pins.pin(directory,'release.json')) == manifest)
        self.checks.update(config=True,manifest=True)
        self.config = config
        return manifest,config

    def lock(self):
        # The private-delivery lock always precedes the persistent activation lock.
        self.pins.directory(RUN,0o700)
        state = self.pins.directory(RUN + '/state',0o700,create=True)
        operations = self.pins.directory(DATA + '/operations',0o700,create=True)
        for directory,name in ((state,'operation.lock'),(operations,'activation.lock')):
            fd = os.open(name,os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,0o600,dir_fd=directory)
            self.pins.stack.callback(os.close,fd)
            value = os.fstat(fd)
            require(stat.S_ISREG(value.st_mode) and value.st_uid == 0 and value.st_gid == 0 and value.st_nlink == 1 and stat.S_IMODE(value.st_mode) == 0o600)
            fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lockfiles.append((directory,name,fd,ident(value)))
        self.operations = operations

    def recheck(self, manifest, config):
        self.pins.recheck()
        for parent,name,fd,original in self.lockfiles:
            require(ident(os.fstat(fd)) == original and ident(os.stat(name,dir_fd=parent,follow_symlinks=False)) == original)
            fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.prerequisites(manifest,config)
        require(selection(self.pins) == self.expected_current)

    def bundle(self, manifest, config):
        previous = manifest.get('rollback_source_sha')
        old = self.rt._installed_deploy_inputs(previous)[0] if previous else None
        bundle = self.rt.render_bundle(manifest,config,old)
        directory = self.pins.directory(RELEASES + '/' + manifest['source_sha'])
        for name in ('compose.production.yaml','Caddyfile'):
            materialize(self.pins,directory,name,bundle[name].encode('utf-8'))

    def compose(self, sha, action, services):
        require(action in ('up','stop') and services and all(s in APPS + STATEFUL + ('caddy',) for s in services))
        release = RELEASES + '/' + sha
        prefix = DOCKER + ['compose','--project-name','autodata-production','--project-directory',release,
            '--file',release + '/compose.production.yaml','--env-file','/dev/null']
        args = ['up','-d','--no-deps','--pull','never'] if action == 'up' else ['stop','--timeout','10']
        self.mutated = True
        self.command(prefix + args + list(services),30)

    def graph(self, manifests):
        output = self.command(DOCKER + ['container','ls','--all','--quiet','--no-trunc','--filter','label=com.docker.compose.project=autodata-production'])
        ids = output.decode('ascii').splitlines()
        require(len(ids) <= 8 and len(set(ids)) == len(ids))
        result = {}
        for container in ids:
            # Docker IDs, never service names/commands supplied by a caller.
            require(re.fullmatch(r'[0-9a-f]{64}',container) is not None)
            value = self.rt.strict_json(self.command(DOCKER + ['container','inspect','--format',self.rt.SERVICE_INSPECT_TEMPLATE,container]))
            require(type(value) is dict)
            service = value['service']
            require(service in APPS + STATEFUL + ('caddy',) and service not in result and value['id'] == container and value['project'] == 'autodata-production')
            role = 'ingestion' if service in APPS[1:] else service
            candidates = [m for m in manifests if m['images'][role]['image_id'] == value['image']]
            require(candidates)
            entrypoint = self.rt.strict_json(self.command(DOCKER + ['image','inspect','--format','{{json .Config.Entrypoint}}',value['image']]))
            require(entrypoint is None or type(entrypoint) is list and all(type(item) is str for item in entrypoint))
            validated = False
            for manifest in candidates:
                try:
                    desired = self.rt._runtime_rendered_compose(manifest,self.config)['services'][service]
                    self.rt._validate_service_container(manifest,service,desired,value,entrypoint,require_running=False)
                    validated = True
                    break
                except ValueError: pass
            require(validated)
            require(all(type(value[key]) is bool for key in ('running','paused','restarting','dead')))
            require(not any(value[key] for key in ('paused','restarting','dead')))
            result[service] = value
        return result

    def maintenance(self, enabled, manifest, manifests):
        directory = self.pins.directory(RUN + '/caddy')
        old = self.pins.read(directory,'maintenance.caddy',0o444,empty=True)
        require(old in (b'',MAINTENANCE))
        graph = self.graph(manifests)
        name = '.maintenance-' + uuid.uuid4().hex
        fd = os.open(name,os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,0o444,dir_fd=directory)
        self.mutated = True
        try:
            os.fchmod(fd,0o444)
            data = MAINTENANCE if enabled else b''
            offset = 0
            while offset < len(data): offset += os.write(fd,data[offset:])
            os.fsync(fd)
        finally: os.close(fd)
        try:
            self.pins.recheck()
            os.replace(name,'maintenance.caddy',src_dir_fd=directory,dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try: os.unlink(name,dir_fd=directory)
            except FileNotFoundError: pass
        require(self.pins.read(directory,'maintenance.caddy',0o444,empty=True) == data)
        if graph.get('caddy',{}).get('running'):
            try:
                self.command(DOCKER + ['exec','--user','0:0','--workdir','/',graph['caddy']['id'],
                    'caddy','reload','--config','/etc/caddy/Caddyfile','--adapter','caddyfile','--address','unix//run/caddy/admin.sock'],30)
            except BaseException:
                # Never retain an edge whose effective maintenance is unknown.
                self.compose(manifest['source_sha'],'stop',('caddy',))
                raise

    def ready(self, manifest, config):
        observation = self.rt.collect_runtime_readiness(manifest,config)
        keys = {'schema','services','postgres','nats','s3','no_work','runtime_evidence'}
        require(type(observation) is dict and set(observation) == keys and all(value is True for value in observation.values()))
        self.checks.update(observation)
        require(time.monotonic() < self.deadline)

    def launch(self, manifest, config):
        self.compose(manifest['source_sha'],'up',STATEFUL)
        self.rt.collect_postgres_schema(manifest)
        self.checks['schema'] = True
        self.compose(manifest['source_sha'],'up',APPS + ('caddy',))
        self.ready(manifest,config)

    def stop(self, manifest):
        self.compose(manifest['source_sha'],'stop',APPS)
        self.compose(manifest['source_sha'],'stop',('caddy',))
        self.compose(manifest['source_sha'],'stop',STATEFUL)
        graph = self.graph([manifest])
        require(all(not value['running'] for value in graph.values()))
        self.checks.update(services=True,runtime_evidence=False)

    def track_selection(self, selected):
        self.expected_current = selected

    def recovery_budget(self):
        self.deadline = self.end
        if signal.getsignal(signal.SIGALRM) is _expired:
            signal.setitimer(signal.ITIMER_REAL,max(.001,self.end - time.monotonic()))

    def recover(self, target, config, prior, previous):
        self.recovery_budget()
        # Retain the closed ingress file even after a failed opening reload.
        self.maintenance(True,target,[m for m in (target,prior) if m is not None])
        self.compose(target['source_sha'],'stop',APPS + ('caddy',))
        if prior is None:
            current = selection(self.pins)
            if current is not None:
                require(current == self.expected_current and current[0] == target['source_sha'])
                self.pins.recheck()
                directory = self.pins.directory(OPT)
                os.unlink('current',dir_fd=directory)
                os.fsync(directory)
            require(selection(self.pins) is None)
            return
        self.prerequisites(prior,config)
        self.bundle(prior,config)
        self.launch(prior,config)
        current = selection(self.pins)
        require(current == previous or current == self.expected_current and current is not None and current[0] == target['source_sha'])
        if current != previous: select(self.pins,prior['source_sha'],current,self.track_selection)
        self.expected_current = selection(self.pins)
        self.recheck(prior,config)
        self.maintenance(True,prior,[prior])

    def persist(self, receipt):
        require(self.operations is not None)
        data = json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False).encode() + b'\n'
        materialize(self.pins,self.operations,'activation-' + uuid.uuid4().hex + '.json',data)


def _activation_cli(argv):
    """Only installed launcher arguments; injection is internal to unit tests."""
    rt = runtime()
    checks = {}
    sha = None
    operation = 'deploy.sh start'
    if type(argv) not in (list,tuple) or len(argv) != 2 or argv[0] not in ('start','stop','maintenance','resume') or type(argv[1]) is not str or re.fullmatch(SHA,argv[1]) is None:
        return 2,rt.operation_receipt(operation,None,None,2,{},'invalid_input')
    verb,sha = argv
    operation = 'deploy.sh ' + verb
    code,failure = 3,'missing_dependency'
    with Pins() as pins:
        host = Lifecycle(rt,pins)
        manifest = config = prior = previous = None
        try:
            require(os.geteuid() == 0)
            manifest,config = host.inputs(sha)
            pins.directory(DATA)
            host.mounts(config)
            host.lock()
            host.prerequisites(manifest,config)
            previous = selection(pins)
            host.expected_current = previous
            if verb == 'start':
                if previous is not None and previous[0] != sha:
                    require(manifest['rollback_source_sha'] == previous[0])
                    prior,old_config = host.inputs(previous[0])
                    require(old_config == config)
                    rt.validate_manifest(manifest,config,prior)
                    host.prerequisites(prior,config)
                elif previous is not None:
                    # Restarting the selected source is not a new rollback chain.
                    prior = manifest
                else: require(manifest['rollback_source_sha'] is None)
            else: require(previous is not None and previous[0] == sha)
            host.bundle(manifest,config)
            host.recheck(manifest,config)
            manifests = [m for m in (manifest,prior) if m is not None]
            graph = host.graph(manifests)
            if verb == 'maintenance':
                require(set(graph) == set(APPS + STATEFUL + ('caddy',)) and all(v['running'] for v in graph.values()))
            host.maintenance(True,manifest,manifests)
            if verb == 'start':
                validate_data_directories(rt)
                host.launch(manifest,config)
                host.recheck(manifest,config)
                select(pins,sha,previous,host.track_selection)
                host.expected_current = selection(pins)
                host.recheck(manifest,config)
                host.maintenance(False,manifest,[manifest])
            elif verb == 'resume':
                host.ready(manifest,config)
                host.recheck(manifest,config)
                host.maintenance(False,manifest,[manifest])
            elif verb == 'stop': host.stop(manifest)
            else: host.checks.update(services=True,runtime_evidence=False)
            host.recheck(manifest,config)
            code,failure = 0,None
        except BaseException as error:
            code,failure = (5,'operation_timed_out') if isinstance(error,subprocess.TimeoutExpired) else (4,'operation_failed') if host.mutated else (3,'operation_failed')
            if host.mutated and manifest is not None:
                try:
                    if verb == 'start': host.recover(manifest,config,prior,previous)
                    else:
                        host.recovery_budget()
                        host.maintenance(True,manifest,[manifest])
                except BaseException: code,failure = 6,'recovery_incomplete'
        checks = dict(host.checks)
        if code: checks['runtime_evidence'] = False
        receipt = rt.operation_receipt(operation,sha,None,code,checks,failure)
        if host.operations is not None:
            try: host.persist(receipt)
            except BaseException:
                if host.mutated and manifest is not None:
                    try:
                        host.recovery_budget()
                        host.maintenance(True,manifest,[m for m in (manifest,prior) if m is not None])
                    except BaseException: pass
                code,failure = (6,'recovery_incomplete') if host.mutated else (3,'operation_failed')
                checks['runtime_evidence'] = False
                receipt = rt.operation_receipt(operation,sha,None,code,checks,failure)
        return code,receipt


def _expired(signum, frame):
    raise subprocess.TimeoutExpired('local operation',120)


@contextmanager
def watchdog(seconds):
    """Bound Python collectors as well as child processes, preserving caller state."""
    previous = signal.getsignal(signal.SIGALRM)
    timer = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()
    signal.signal(signal.SIGALRM,_expired)
    signal.setitimer(signal.ITIMER_REAL,seconds)
    try: yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)
        if timer[0]: signal.setitimer(signal.ITIMER_REAL,max(.001,timer[0] - (time.monotonic()-started)),timer[1])


def activation_cli(argv):
    # Thirty final seconds are available only for one recovery attempt.
    with watchdog(90): return _activation_cli(argv)
