#!/usr/bin/python3 -I
"""Owner-accepted, local-only inert staging material installation.

No network, activation, credential delivery, package management or disk setup.
All authority comes from separately provisioned protected host inputs.
"""
from contextlib import ExitStack
import ctypes
from datetime import datetime, timezone
import errno
import fcntl
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import types
import uuid

MIB = 1048576
HASH = r'[0-9a-f]{64}'
SHA = r'[0-9a-f]{40}'
DATA = '/var/lib/autodata'
RUN = '/run/autodata'
HELPER = '/opt/autodata/bin/runtime-check.py'
SCHEMA = '/opt/autodata/bin/release.schema.json'
RELEASES = '/opt/autodata/releases'
DIRECTORIES = ('db', 'db/migrations', 'scripts', 'scripts/dev')
EVIDENCE = ('publisher_verification_receipt_sha256', 'owner_publisher_acceptance_evidence_sha256',
            'owner_data_device_binding_evidence_sha256', 'owner_bare_host_evidence_sha256')
APPROVAL_FIELDS = ('schema_version', 'operation', 'authorization_id', 'expires_at', 'source_sha',
                   'service_config_sha256', 'manifest_raw_sha256', 'manifest_canonical_sha256',
                   'runtime_helper_sha256', 'release_schema_sha256', 'findmnt_binary_sha256', 'files') + EVIDENCE
PROTECTED = frozenset(('/', '/etc', '/var', '/var/lib', '/opt', '/run', '/usr', '/usr/bin', '/opt/autodata/bin'))


class Denied(Exception):
    """No input or underlying exception is included in a public error."""


class Expired(Exception):
    pass


class RecoveryIncomplete(Exception):
    pass


def require(value):
    if not value:
        raise Denied()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def strict_json(data):
    require(type(data) is bytes and len(data) <= MIB)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    def invalid(_):
        raise Denied()
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
        canonical(value)
        return value
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise Denied() from None


def digest(data):
    return hashlib.sha256(data).hexdigest()


def matches(value, pattern):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def _owned(value):
    return value.st_uid == 0 and value.st_gid == 0


def identity(value):
    return value.st_dev, value.st_ino


def metadata(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid,
            value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _open_root():
    return os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)


class Deadline:
    def __init__(self):
        self.end = time.monotonic() + 300

    def check(self, cleanup=False):
        if time.monotonic() >= self.end - (0 if cleanup else 30):
            raise Expired()


class Filesystem:
    """All traversal starts at a pinned root; no caller-selected production root."""
    def __init__(self, stack, deadline):
        self.stack = stack
        self.deadline = deadline
        root = _open_root()
        stack.callback(os.close, root)
        self.dirs = {'/': root}
        self.modes = {'/': None}
        self.entries = []
        self.check_dir(root, None)

    def check_dir(self, fd, mode):
        value = os.fstat(fd)
        require(stat.S_ISDIR(value.st_mode) and _owned(value))
        require((value.st_mode & 0o22) == 0 if mode is None else stat.S_IMODE(value.st_mode) == mode)

    def directory(self, path, mode=None, create=False):
        self.deadline.check()
        if path in self.dirs:
            fd = self.dirs[path]
            self.check_dir(fd, mode)
            return fd
        parent, name = path.rsplit('/', 1)
        parent = parent or '/'
        parent_fd = self.directory(parent, self.modes.get(parent, None if parent in PROTECTED else 0o700))
        if create:
            try:
                os.mkdir(name, 0o700, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except FileExistsError:
                pass
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent_fd)
        self.stack.callback(os.close, fd)
        self.check_dir(fd, mode)
        self.dirs[path] = fd
        self.modes[path] = mode
        self.entries.append((parent_fd, name, fd, mode))
        return fd

    def recheck(self):
        self.check_dir(self.dirs['/'], None)
        for parent, name, fd, mode in self.entries:
            self.deadline.check()
            require(identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) == identity(os.fstat(fd)))
            self.check_dir(fd, mode)

    def file(self, path, mode, maximum=MIB):
        parent, name = path.rsplit('/', 1)
        fd = self.directory(parent, None if parent in PROTECTED else 0o700)
        return PinnedFile(self.stack, self.deadline, fd, name, mode, maximum)


class PinnedFile:
    def __init__(self, stack, deadline, parent, name, mode, maximum=MIB):
        self.parent, self.name, self.deadline = parent, name, deadline
        self.fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
        stack.callback(os.close, self.fd)
        value = os.fstat(self.fd)
        require(stat.S_ISREG(value.st_mode) and _owned(value) and value.st_nlink == 1)
        require(0 < value.st_size <= maximum)
        require(value.st_mode & 0o22 == 0 if mode is None else stat.S_IMODE(value.st_mode) == mode)
        self.meta = metadata(value)
        self.maximum = maximum
        self.expected = None

    def read(self):
        self.deadline.check()
        require(metadata(os.fstat(self.fd)) == self.meta)
        require(metadata(os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)) == self.meta)
        os.lseek(self.fd, 0, os.SEEK_SET)
        chunks, total = [], 0
        while True:
            self.deadline.check()
            chunk = os.read(self.fd, min(65536, self.maximum + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            require(total <= self.maximum)
            chunks.append(chunk)
        data = b''.join(chunks)
        require(len(data) == self.meta[6] and metadata(os.fstat(self.fd)) == self.meta)
        require(metadata(os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)) == self.meta)
        if self.expected is not None:
            require(digest(data) == self.expected)
        return data

    def bind(self, expected):
        require(matches(expected, HASH))
        self.expected = expected
        return self.read()


def validate_approval(approval, source_sha, config_hash):
    require(type(approval) is dict and set(approval) == set(APPROVAL_FIELDS))
    require(type(approval['schema_version']) is int and approval['schema_version'] == 1)
    require(approval['operation'] == 'install-inert-staging-release')
    authorization = approval['authorization_id']
    require(matches(authorization, r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'))
    require(str(uuid.UUID(authorization)) == authorization)
    require(approval['source_sha'] == source_sha and approval['service_config_sha256'] == config_hash)
    for field in ('service_config_sha256', 'manifest_raw_sha256', 'manifest_canonical_sha256',
                  'runtime_helper_sha256', 'release_schema_sha256', 'findmnt_binary_sha256') + EVIDENCE:
        require(matches(approval[field], HASH))
    validate_expiry(approval)
    files = approval['files']
    require(type(files) is list and 3 <= len(files) <= 258)
    names, total = [], 0
    for item in files:
        require(type(item) is dict and set(item) == {'path', 'bytes', 'sha256'})
        path = item['path']
        require(path in ('release.json', 'scripts/dev/migrate_sql.sh') or
                matches(path, r'db/migrations/[0-9]{3}_[a-z0-9_]+\.sql'))
        require(type(item['bytes']) is int and 0 < item['bytes'] <= MIB and matches(item['sha256'], HASH))
        names.append(path)
        total += item['bytes']
    require(names == sorted(set(names)) and total <= 64 * MIB)


def validate_expiry(approval):
    value = approval['expires_at']
    require(matches(value, r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z'))
    expires = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    seconds = (expires - datetime.now(timezone.utc)).total_seconds()
    require(0 < seconds <= 86400)


def _runtime(data):
    module = types.ModuleType('_autodata_install_runtime')
    module.__file__ = HELPER
    exec(compile(data, HELPER, 'exec'), module.__dict__)
    return module


def _probe(binary_fd, target, deadline):
    """Only fixed findmnt argv; bounded output, process-group kill and reap."""
    require(target in (DATA, RUN))
    deadline.check()
    argv = ['/proc/self/fd/' + str(binary_fd), '--json', '--list', '--mountpoint', target,
            '--output', 'TARGET,UUID,FSTYPE,OPTIONS']
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, env={}, cwd='/', pass_fds=(binary_fd,),
                             start_new_session=True)
    end = min(time.monotonic() + 5, deadline.end - 30)
    data = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            while True:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    raise Expired()
                if not selector.select(min(remaining, 0.1)):
                    continue
                chunk = os.read(child.stdout.fileno(), 4096)
                if not chunk:
                    break
                data.extend(chunk)
                require(len(data) <= 65536)
        try:
            code = child.wait(timeout=max(0.001, end - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise Expired() from None
        require(code == 0)
        return bytes(data)
    finally:
        # Kill the group even if its leader exited while a descendant held stdout.
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=0.2 if sig == signal.SIGTERM else 1)
            except subprocess.TimeoutExpired:
                if sig == signal.SIGKILL:
                    raise RecoveryIncomplete() from None
        child.stdout.close()


def _write_all(fd, data, deadline):
    view = memoryview(data)
    while view:
        deadline.check()
        count = os.write(fd, view[:65536])
        require(count > 0)
        view = view[count:]


def _rename_noreplace(parent, old, new):
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None:
        raise Denied()
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(parent, old.encode('ascii'), parent, new.encode('ascii'), 1) != 0:
        code = ctypes.get_errno()
        if code in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
            raise Denied()
        raise OSError(code, 'no-replace promotion failed')


def _absent(parent, name):
    try:
        os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return True
    return False


def _inventory(fs, base, mode, manifest):
    """Exact fixed directories and regular files, no recursive arbitrary traversal."""
    directories = {'': fs.directory(base, mode)}
    for name in DIRECTORIES:
        directories[name] = fs.directory(base + '/' + name, mode)
    paths = ['release.json', 'scripts/dev/migrate_sql.sh']
    paths += ['db/migrations/' + item['name'] for item in manifest['migrations']['files']]
    for name, fd in directories.items():
        expected = {p[len(name) + 1:] if name else p for p in paths if p.rsplit('/', 1)[0] == name or ('/' not in p and name == '')}
        expected |= {p.rsplit('/', 1)[-1] for p in DIRECTORIES if (p.rsplit('/', 1)[0] if '/' in p else '') == name}
        require(set(os.listdir(fd)) == expected)
    return paths, directories


class Transaction:
    """Only this operation's exclusively created, identity-pinned temporary tree."""
    def __init__(self, fs, parent, name):
        self.fs, self.parent, self.name = fs, parent, name
        self.dirs, self.files = {}, []
        self.created = False

    def start(self):
        parent, name, fs = self.parent, self.name, self.fs
        os.mkdir(name, 0o700, dir_fd=parent)
        self.created = True
        self.root_identity = identity(os.stat(name, dir_fd=parent, follow_symlinks=False))
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
        fs.stack.callback(os.close, fd)
        self.dirs[''] = fd
        self.root_identity = identity(os.fstat(fd))

    def build(self, inputs):
        for name in DIRECTORIES:
            parent, leaf = name.rsplit('/', 1) if '/' in name else ('', name)
            os.mkdir(leaf, 0o700, dir_fd=self.dirs[parent])
            fd = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.dirs[parent])
            self.fs.stack.callback(os.close, fd)
            self.dirs[name] = fd
        for item, source in inputs:
            path = item['path']
            parent, name = path.rsplit('/', 1) if '/' in path else ('', path)
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=self.dirs[parent])
            self.files.append((parent, name, identity(os.fstat(fd))))
            try:
                _write_all(fd, source.read(), self.fs.deadline)
                os.fchmod(fd, 0o600 if path == 'release.json' else 0o444)
                os.fsync(fd)
            finally:
                os.close(fd)
        for name in sorted(self.dirs, key=lambda p: p.count('/') + bool(p), reverse=True):
            os.fchmod(self.dirs[name], 0o500)
            os.fsync(self.dirs[name])

    def verify(self, inputs):
        self.fs.deadline.check()
        require(identity(os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)) == self.root_identity)
        for name, fd in self.dirs.items():
            self.fs.check_dir(fd, 0o500)
            expected = {leaf for parent, leaf, _ in self.files if parent == name}
            expected |= {p.rsplit('/', 1)[-1] for p in self.dirs if p and (p.rsplit('/', 1)[0] if '/' in p else '') == name}
            require(set(os.listdir(fd)) == expected)
            if name:
                parent, leaf = name.rsplit('/', 1) if '/' in name else ('', name)
                require(identity(os.stat(leaf, dir_fd=self.dirs[parent], follow_symlinks=False)) == identity(os.fstat(fd)))
        for (item, _), (parent, name, ident) in zip(inputs, self.files):
            with ExitStack() as stack:
                copied = PinnedFile(stack, self.fs.deadline, self.dirs[parent], name,
                                    0o600 if item['path'] == 'release.json' else 0o444)
                require(identity(os.fstat(copied.fd)) == ident and copied.meta[6] == item['bytes'])
                copied.bind(item['sha256'])

    def cleanup(self):
        if not self.created:
            return
        require('' in self.dirs)
        self.fs.deadline.check(cleanup=True)
        require(identity(os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)) == self.root_identity)
        for name, fd in self.dirs.items():
            self.fs.deadline.check(cleanup=True)
            expected = {leaf for parent, leaf, _ in self.files if parent == name}
            expected |= {p.rsplit('/', 1)[-1] for p in self.dirs if p and (p.rsplit('/', 1)[0] if '/' in p else '') == name}
            require(set(os.listdir(fd)) == expected)
            require(_owned(os.fstat(fd)))
            if name:
                parent, leaf = name.rsplit('/', 1) if '/' in name else ('', name)
                require(identity(os.stat(leaf, dir_fd=self.dirs[parent], follow_symlinks=False)) == identity(os.fstat(fd)))
        for parent, name, ident in self.files:
            value = os.stat(name, dir_fd=self.dirs[parent], follow_symlinks=False)
            require(identity(value) == ident and stat.S_ISREG(value.st_mode) and value.st_nlink == 1 and _owned(value))
        for fd in self.dirs.values():
            os.fchmod(fd, 0o700)
        for parent, name, _ in self.files:
            self.fs.deadline.check(cleanup=True)
            os.unlink(name, dir_fd=self.dirs[parent])
        for name in sorted((p for p in self.dirs if p), key=lambda p: p.count('/'), reverse=True):
            self.fs.deadline.check(cleanup=True)
            parent, leaf = name.rsplit('/', 1) if '/' in name else ('', name)
            os.rmdir(leaf, dir_fd=self.dirs[parent])
        os.rmdir(self.name, dir_fd=self.parent)
        os.fsync(self.parent)


def _persist_receipt(fs, directory, authorization, receipt):
    data = canonical(receipt)
    require(len(data) <= 65536)
    name, temporary = authorization + '.json', '.receipt-' + authorization
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600, dir_fd=directory)
    ident = identity(os.fstat(fd))
    try:
        _write_all(fd, data, fs.deadline)
        os.fsync(fd)
        require(identity(os.stat(temporary, dir_fd=directory, follow_symlinks=False)) == ident)
        os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        os.close(fd)
        if not _absent(directory, temporary):
            value = os.stat(temporary, dir_fd=directory, follow_symlinks=False)
            require(identity(value) == ident and stat.S_ISREG(value.st_mode) and value.st_nlink == 1 and _owned(value))
            os.unlink(temporary, dir_fd=directory)
            os.fsync(directory)


def _receipt(source_sha):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return {'schema_version': 1, 'operation': 'deploy.sh install', 'source_sha': source_sha,
            'run_id': None, 'status': 'failed', 'started_at': now, 'finished_at': now,
            'checks': {key: False for key in ('config', 'manifest', 'migration_tree', 'disk_uuid',
                                             'schema', 'services', 'secrets', 'cached_images', 'runtime_evidence')},
            'failure_code': 'missing_dependency', 'inert_installation_only': True,
            'deployment_authorized': False, 'release_material_committed': False,
            'commit_state': 'not_started',
            **{key: None for key in ('manifest_raw_sha256', 'manifest_canonical_sha256', 'service_config_sha256', 'install_approval_sha256') + EVIDENCE}}


def _finish(receipt, code):
    receipt['status'] = {0: 'passed', 2: 'failed', 3: 'failed', 4: 'failed', 5: 'timed_out', 6: 'incomplete'}[code]
    receipt['failure_code'] = {0: None, 2: 'invalid_input', 3: 'missing_dependency', 4: 'operation_failed',
                               5: 'operation_timed_out', 6: 'recovery_incomplete'}[code]
    receipt['finished_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return code, receipt


def install_cli(source_sha):
    valid = matches(source_sha, SHA)
    receipt = _receipt(source_sha if valid else None)
    if not valid:
        return _finish(receipt, 2)
    deadline = Deadline()
    transaction = None
    committed = False
    writing = False
    with ExitStack() as stack:
        try:
            require(os.geteuid() == 0)
            stack.callback(os.umask, os.umask(0o077))
            fs = Filesystem(stack, deadline)
            config_file = fs.file('/etc/autodata/host.json', 0o600)
            config_data = config_file.read()
            config_file.expected = digest(config_data)
            config = strict_json(config_data)
            # Deny production before opening any approval/evidence/inbox bytes.
            require(type(config) is dict and config.get('environment') == 'staging')
            approval_file = fs.file('/etc/autodata/install-approval.json', 0o600, 65536)
            approval_data = approval_file.read()
            approval_file.expected = digest(approval_data)
            approval = strict_json(approval_data)
            validate_approval(approval, source_sha, digest(canonical(config)))
            receipt['run_id'] = approval['authorization_id']
            receipt['service_config_sha256'] = approval['service_config_sha256']
            receipt['install_approval_sha256'] = approval_file.expected
            for key in ('manifest_raw_sha256', 'manifest_canonical_sha256') + EVIDENCE:
                receipt[key] = approval[key]
            evidence = fs.file('/etc/autodata/publisher-accepted/' + source_sha + '.json', 0o600, 65536)
            evidence.bind(approval['publisher_verification_receipt_sha256'])
            helper = fs.file(HELPER, None)
            runtime = _runtime(helper.bind(approval['runtime_helper_sha256']))
            schema = fs.file(SCHEMA, None)
            schema.bind(approval['release_schema_sha256'])
            require(runtime.validate_config(config) == approval['service_config_sha256'])
            receipt['checks']['config'] = True
            opt = fs.directory('/opt/autodata', 0o700)
            require(_absent(opt, 'current'))
            releases = fs.directory(RELEASES, 0o700)
            binary = fs.file('/usr/bin/findmnt', None)
            binary.bind(approval['findmnt_binary_sha256'])
            data_fd = fs.directory(DATA, 0o700)
            run_fd = fs.directory(RUN, 0o700)
            pinned_mounts = (identity(os.fstat(data_fd)), identity(os.fstat(run_fd)))

            def mounts():
                binary.read()
                runtime.validate_mount_observations(config, runtime.strict_json(_probe(binary.fd, DATA, deadline)),
                                                     runtime.strict_json(_probe(binary.fd, RUN, deadline)))
                binary.read()
                fs.recheck()
                require((identity(os.fstat(data_fd)), identity(os.fstat(run_fd))) == pinned_mounts)

            mounts()
            receipt['checks']['disk_uuid'] = True
            state = fs.directory(RUN + '/state', 0o700, create=True)
            lock = os.open('operation.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                           0o600, dir_fd=state)
            stack.callback(os.close, lock)
            lock_stat = os.fstat(lock)
            require(stat.S_ISREG(lock_stat.st_mode) and _owned(lock_stat) and lock_stat.st_nlink == 1
                    and stat.S_IMODE(lock_stat.st_mode) == 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            inbox = DATA + '/incoming/' + source_sha
            manifest_file = fs.file(inbox + '/release.json', 0o600)
            manifest = runtime.strict_json(manifest_file.bind(approval['manifest_raw_sha256']))
            require(runtime.validate_manifest(manifest, config, None) == approval['manifest_canonical_sha256'])
            schema.read()
            require(manifest['source_sha'] == source_sha and manifest['rollback_source_sha'] is None)
            require(1 <= len(manifest['migrations']['files']) <= 256)
            receipt['checks']['manifest'] = True
            paths, _ = _inventory(fs, inbox, 0o700, manifest)
            require(sorted(paths) == [item['path'] for item in approval['files']])
            inputs = []
            for item in approval['files']:
                path = item['path']
                source = manifest_file if path == 'release.json' else fs.file(inbox + '/' + path, 0o444)
                require(source.meta[6] == item['bytes'])
                source.bind(item['sha256'])
                if path == 'scripts/dev/migrate_sql.sh':
                    require(item['sha256'] == manifest['migrations']['runner_sha256'])
                elif path.startswith('db/migrations/'):
                    require(item['sha256'] == next(f['sha256'] for f in manifest['migrations']['files'] if path == 'db/migrations/' + f['name']))
                inputs.append((item, source))
            receipt['checks']['migration_tree'] = True
            # Prior receipt is a replay binding only, never proof of installed bytes.
            operations = None
            if not _absent(data_fd, 'operations'):
                operations = fs.directory(DATA + '/operations', 0o700)
                name = approval['authorization_id'] + '.json'
                if not _absent(operations, name):
                    previous = strict_json(fs.file(DATA + '/operations/' + name, 0o600, 65536).read())
                    for key in ('run_id', 'source_sha', 'manifest_raw_sha256', 'manifest_canonical_sha256', 'service_config_sha256', 'install_approval_sha256') + EVIDENCE:
                        require(previous[key] == receipt[key])
            if not _absent(releases, '.install-' + approval['authorization_id']):
                raise Denied()
            final_inputs = []
            if _absent(releases, source_sha):
                transaction = Transaction(fs, releases, '.install-' + approval['authorization_id'])
                writing = True
                receipt['commit_state'] = 'copying'
                transaction.start()
                transaction.build(inputs)
            else:
                paths, final_dirs = _inventory(fs, RELEASES + '/' + source_sha, 0o500, manifest)
                for item, _ in inputs:
                    path = item['path']
                    parent, name = path.rsplit('/', 1) if '/' in path else ('', path)
                    existing = PinnedFile(stack, deadline, final_dirs[parent], name, 0o600 if path == 'release.json' else 0o444)
                    require(existing.meta[6] == item['bytes'])
                    existing.bind(item['sha256'])
                    final_inputs.append(existing)
            deadline.check()
            validate_expiry(approval)
            config_file.read(); approval_file.read(); evidence.read(); helper.read(); schema.read()
            for _, source in inputs:
                source.read()
            _inventory(fs, inbox, 0o700, manifest)
            require(_absent(opt, 'current'))
            require(identity(os.stat('operation.lock', dir_fd=state, follow_symlinks=False)) == identity(lock_stat))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            mounts()
            for _, source in inputs:
                source.read()
            for existing in final_inputs:
                existing.read()
            config_file.read(); approval_file.read(); evidence.read(); helper.read(); schema.read()
            require(_absent(opt, 'current'))
            validate_expiry(approval)
            if transaction is not None:
                transaction.verify(inputs)
                _rename_noreplace(releases, transaction.name, source_sha)
                committed = True
                transaction = None
                os.fsync(releases)
            else:
                committed = True
            receipt['release_material_committed'] = True
            receipt['commit_state'] = 'material_committed'
            mounts()
            validate_expiry(approval)
            require(_absent(opt, 'current'))
            operations = fs.directory(DATA + '/operations', 0o700, create=True)
            receipt['commit_state'] = 'receipt_committed'
            _finish(receipt, 0)
            _persist_receipt(fs, operations, approval['authorization_id'], receipt)
            return 0, receipt
        except BaseException as error:
            # Fixed public outcomes; no raw input, path, tool output or exception text.
            code = (6 if committed or isinstance(error, RecoveryIncomplete) else
                    5 if isinstance(error, Expired) else 3 if isinstance(error, Denied) else 4 if writing else 3)
            if transaction is not None:
                try:
                    transaction.cleanup()
                    receipt['commit_state'] = 'not_started'
                except BaseException:
                    code = 6
            if code == 6:
                receipt['commit_state'] = 'incomplete'
            receipt['release_material_committed'] = committed
            return _finish(receipt, code)


def main(argv):
    os.environ.clear()
    os.chdir('/')
    if len(argv) != 1:
        return _finish(_receipt(None), 2)
    return install_cli(argv[0])


if __name__ == '__main__':
    code, output = main(sys.argv[1:])
    sys.stdout.write(canonical(output).decode('utf-8') + '\n')
    raise SystemExit(code)
