#!/usr/bin/python3 -I
"""First-install local private files only. No workload or remote authority.

The owner acceptance is a trust prerequisite, not observed host quiescence.
Deadlines are cooperative: synchronous kernel I/O and close can stall indefinitely.
"""
import base64
import binascii
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import re
import selectors
import stat
import sys
import time
import types

MIB = 1048576
SHA = r'[0-9a-f]{40}'
HASH = r'[0-9a-f]{64}'
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
UUID4 = r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'
DATA, RUN = '/var/lib/autodata', '/run/autodata'
BIN = '/opt/autodata/bin/'
OPERATION = 'install-first-application-private-material'
SERVICE_NAMES = {
    'api': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY', 'AUTODATA_INGESTION_INTERNAL_TOKEN', 'AUTODATA_IMAGE_URL_KEY'),
    'ingestion-http': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY', 'AUTODATA_INGESTION_INTERNAL_TOKEN', 'AUTODATA_STRIPE_SECRET_KEY', 'AUTODATA_STRIPE_WEBHOOK_SECRET', 'BANKONE_API_TOKEN', 'BANKTWO_API_TOKEN'),
    'article-worker': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY', 'BANKONE_API_TOKEN', 'BANKTWO_API_TOKEN', 'INCEPTION_API_KEY'),
    'payment-reconciler': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_INGESTION_INTERNAL_TOKEN', 'AUTODATA_STRIPE_SECRET_KEY', 'AUTODATA_STRIPE_WEBHOOK_SECRET')}
HASH_FIELDS = ('service_config_sha256', 'manifest_raw_sha256', 'manifest_canonical_sha256',
               'host_install_helper_sha256', 'runtime_helper_sha256', 'release_schema_sha256',
               'findmnt_binary_sha256', 'publisher_verification_receipt_sha256',
               'owner_publisher_acceptance_evidence_sha256', 'owner_data_device_binding_evidence_sha256',
               'owner_pre_daemon_host_evidence_sha256')
APPROVAL_FIELDS = ('schema_version', 'operation', 'authorization_id', 'expires_at', 'source_sha', 'service', 'secret_versions') + HASH_FIELDS
ASSERTIONS = ('no_installed_workload_lifecycle', 'no_running_workload', 'no_restartable_workload',
              'no_untrusted_uid1000_process', 'root_exclusive_preparation_window')
AUTHORITIES = ('implementation_dispatch_authorized', 'repository_mutation_authorized', 'github_mutation_authorized',
               'integration_authorized', 'merge_authorized', 'cloud_execution_authorized', 'vm_operation_authorized',
               'host_mutation_authorized', 'docker_execution_authorized', 'credential_access_authorized',
               'secret_delivery_authorized', 'authenticated_remote_transport_authorized', 'image_pull_authorized',
               'application_activation_authorized', 'migration_authorized', 'runtime_execution_authorized',
               'provider_call_authorized', 'payment_operation_authorized', 'backup_restore_authorized',
               'dns_tls_cutover_authorized', 'production_deployment_authorized', 'runtime_verified', 'production_ready')


class Denied(Exception):
    """Fixed public failure; never carries input or underlying exception text."""


class InvalidInput(Exception):
    pass


class Expired(Exception):
    pass


class RecoveryIncomplete(Exception):
    pass


def require(condition):
    if not condition:
        raise Denied()


def matches(value, pattern):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


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
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise Denied() from None


def utcnow():
    return datetime.now(timezone.utc)


def stamp(value=None):
    return (value or utcnow()).strftime('%Y-%m-%dT%H:%M:%SZ')


def timestamp(value):
    require(matches(value, r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z'))
    try:
        result = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError:
        raise Denied() from None
    require(stamp(result) == value)
    return result


def validate_approval(approval, source_sha, service, config_hash, now):
    require(type(approval) is dict and set(approval) == set(APPROVAL_FIELDS))
    require(type(approval['schema_version']) is int and approval['schema_version'] == 1)
    require(approval['operation'] == OPERATION and matches(approval['authorization_id'], UUID4))
    require(approval['source_sha'] == source_sha and approval['service'] == service)
    require(approval['service_config_sha256'] == config_hash)
    for field in HASH_FIELDS:
        require(matches(approval[field], HASH))
    require(0 < (timestamp(approval['expires_at']) - now).total_seconds() <= 86400)
    versions = approval['secret_versions']
    require(type(versions) is dict and set(versions) == set(SERVICE_NAMES[service]))
    for version in versions.values():
        require(matches(version, r'projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/secrets/[a-zA-Z0-9_-]{1,255}/versions/[1-9][0-9]*'))


def parse_stream(data, approval):
    try:
        frame = strict_json(data)
        require(type(frame) is dict and set(frame) == {'schema_version', 'authorization_id', 'source_sha', 'service', 'secret_versions', 'values'})
        require(type(frame['schema_version']) is int and frame['schema_version'] == 1)
        for key in ('authorization_id', 'source_sha', 'service', 'secret_versions'):
            require(frame[key] == approval[key])
        require(type(frame['values']) is dict and set(frame['values']) == set(SERVICE_NAMES[approval['service']]))
        values = {}
        for name, value in frame['values'].items():
            require(type(value) is str and len(value) <= 21848)
            decoded = base64.b64decode(value.encode('ascii'), validate=True)
            require(base64.b64encode(decoded).decode('ascii') == value)
            require(1 <= len(decoded) <= 16384 and not any(c in decoded for c in (b'\x00', b'\r', b'\n')))
            text = decoded.decode('utf-8')
            require(re.search(r'@@[^@\r\n]+@@', text) is None)
            values[name] = decoded
        return values
    except (Denied, ValueError, UnicodeError, binascii.Error, TypeError, KeyError):
        raise InvalidInput() from None


def validate_pinned_first_manifest(manifest, config, schema_bytes, runtime):
    """Intentional candidate parity subset; schema comes only from accepted bytes."""
    require(type(schema_bytes) is bytes)
    config_hash = runtime.validate_config(config)
    schema = runtime.strict_json(schema_bytes)
    runtime._schema_validate(manifest, schema)
    require(len(runtime.canonical_bytes(manifest)) <= runtime.MAX_JSON_BYTES)
    require(manifest['service_config_sha256'] == config_hash)
    runtime._validate_immutable_images(manifest, config)
    files = manifest['migrations']['files']
    require(len(files) <= 999)
    require([f['name'] for f in files] == sorted(f['name'] for f in files))
    require([int(f['name'][:3]) for f in files] == list(range(1, len(files) + 1)))
    require(manifest['migrations']['inventory_sha256'] == runtime.sha256(files))
    require(manifest['rollback_source_sha'] is None)
    return runtime.sha256(manifest)


def validate_host_record(record, approval, config, machine, boot, now):
    keys = ('schema_version', 'operation', 'authorization_id', 'source_sha', 'service', 'service_config_sha256',
            'host_project_id', 'zone', 'instance_name', 'machine_id_sha256', 'boot_id', 'issued_at', 'expires_at', 'assertions')
    require(type(record) is dict and set(record) == set(keys))
    require(type(record['schema_version']) is int and record['schema_version'] == 1)
    require(record['operation'] == 'accept-pre-daemon-first-install')
    for key in ('authorization_id', 'source_sha', 'service', 'service_config_sha256'):
        require(record[key] == approval[key])
    for key in ('host_project_id', 'zone', 'instance_name'):
        require(record[key] == config['resources'][key])
    require(type(machine) is bytes and re.fullmatch(rb'[0-9a-f]{32}\n?', machine) is not None)
    require(type(boot) is bytes)
    boot_text = boot.decode('ascii')
    require(matches(boot_text, UUID + r'\n?'))
    require(record['machine_id_sha256'] == digest(machine) and record['boot_id'] == boot_text.rstrip('\n'))
    issued, expires = timestamp(record['issued_at']), timestamp(record['expires_at'])
    require((issued - now).total_seconds() <= 5 and expires > now and 0 < (expires - issued).total_seconds() <= 900)
    assertions = record['assertions']
    require(type(assertions) is dict and set(assertions) == set(ASSERTIONS))
    require(all(assertions[key] is True for key in ASSERTIONS))


def receipt(source=None, service=None):
    return {'schema_version': 1, 'operation': OPERATION, 'source_sha': source, 'service': service,
            'authorization_id': None, 'started_at': stamp(), 'finished_at': stamp(), 'status': 'failed',
            'failure_code': 'missing_dependency', 'commit_state': 'not_started', 'secret_material_committed': False,
            'one_service_private_material_installed': False, 'secret_versions': None,
            **{k: None for k in HASH_FIELDS + ('approval_sha256',)},
            **{k: False for k in AUTHORITIES + ('global_ready', 'schema', 'services', 'no_work', 'runtime_evidence')}}


def finish(output, code):
    output['status'] = {0: 'passed', 2: 'failed', 3: 'failed', 4: 'failed', 5: 'timed_out', 6: 'incomplete'}[code]
    output['failure_code'] = {0: None, 2: 'invalid_input', 3: 'missing_dependency', 4: 'operation_failed', 5: 'operation_timed_out', 6: 'recovery_incomplete'}[code]
    output['finished_at'] = stamp()
    output['one_service_private_material_installed'] = code == 0
    return code, output


class Budget:
    """One monotonic budget, with a best-effort cleanup reserve, never reset."""
    def __init__(self):
        self.started = time.monotonic()
        self.cleanup = False

    @property
    def end(self):
        # The pinned probe reserves 30s itself. During cleanup it may use the reserve.
        return self.started + 300 + (30 if self.cleanup else 0)

    def check(self, cleanup=False):
        if time.monotonic() - self.started >= (300 if cleanup or self.cleanup else 270):
            raise Expired()

    def remaining(self):
        self.check()
        return max(0, self.started + (300 if self.cleanup else 270) - time.monotonic())

    def call(self, function, *args, **kwargs):
        self.check()
        try:
            return function(*args, **kwargs)
        finally:
            self.check()


def _owner(value, uid=0, gid=0):
    return value.st_uid == uid and value.st_gid == gid


def identity(value):
    return value.st_dev, value.st_ino


def metadata(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid,
            value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _open_root():
    return os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)


def close_fd(fd):
    # Never retry close: even an error can mean the number has been released.
    try:
        os.close(fd)
    except BaseException:
        raise RecoveryIncomplete() from None


PROTECTED = frozenset(('/', '/etc', '/var', '/var/lib', '/opt', '/run', '/usr', '/usr/bin',
                       '/opt/autodata/bin', '/proc', '/proc/sys', '/proc/sys/kernel', '/proc/sys/kernel/random'))


class Filesystem:
    def __init__(self, stack, budget):
        self.stack, self.budget = stack, budget
        self.dirs, self.entries, self.files = {}, [], []
        root = self.open(_open_root)
        self.dirs['/'] = root
        self.check_dir(root, None)

    def open(self, function, *args, **kwargs):
        self.budget.check()
        fd = function(*args, **kwargs)
        # Register before the post-call deadline check so slow opens cannot leak.
        self.stack.callback(close_fd, fd)
        self.budget.check()
        return fd

    def check_dir(self, fd, mode):
        value = self.budget.call(os.fstat, fd)
        require(stat.S_ISDIR(value.st_mode) and _owner(value))
        require(value.st_mode & 0o22 == 0 if mode is None else stat.S_IMODE(value.st_mode) == mode)

    def directory(self, path, mode=None, create=False):
        if path in self.dirs:
            self.check_dir(self.dirs[path], mode)
            return self.dirs[path]
        parent, name = path.rsplit('/', 1); parent = parent or '/'
        pfd = self.directory(parent, None if parent in PROTECTED else 0o700)
        if create:
            try:
                self.budget.call(os.mkdir, name, 0o700, dir_fd=pfd)
                self.budget.call(os.fsync, pfd)
            except FileExistsError:
                pass
        fd = self.open(os.open, name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=pfd)
        self.check_dir(fd, mode)
        self.dirs[path] = fd
        self.entries.append((pfd, name, fd, mode))
        return fd

    def file(self, path, mode, maximum=MIB, virtual=False):
        parent, name = path.rsplit('/', 1)
        pfd = self.directory(parent, None if parent in PROTECTED else (0o500 if parent.startswith('/opt/autodata/releases/') else 0o700))
        item = PinnedFile(self, pfd, name, mode, maximum, virtual)
        self.files.append(item)
        return item

    def recheck(self):
        self.check_dir(self.dirs['/'], None)
        for parent, name, fd, mode in self.entries:
            require(identity(self.budget.call(os.stat, name, dir_fd=parent, follow_symlinks=False)) == identity(self.budget.call(os.fstat, fd)))
            self.check_dir(fd, mode)
        for item in self.files:
            item.read()


class PinnedFile:
    def __init__(self, fs, parent, name, mode, maximum, virtual=False):
        self.fs, self.parent, self.name = fs, parent, name
        self.maximum, self.virtual, self.expected = maximum, virtual, None
        self.fd = fs.open(os.open, name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
        value = fs.budget.call(os.fstat, self.fd)
        require(stat.S_ISREG(value.st_mode) and _owner(value) and value.st_nlink == 1)
        require((0 if virtual else 1) <= value.st_size <= maximum)
        require(value.st_mode & 0o222 == 0 if mode is None else stat.S_IMODE(value.st_mode) == mode)
        self.meta = metadata(value)

    def read(self):
        b = self.fs.budget
        require(metadata(b.call(os.fstat, self.fd)) == self.meta)
        require(metadata(b.call(os.stat, self.name, dir_fd=self.parent, follow_symlinks=False)) == self.meta)
        b.call(os.lseek, self.fd, 0, os.SEEK_SET)
        chunks, total = [], 0
        while True:
            chunk = b.call(os.read, self.fd, min(65536, self.maximum + 1 - total))
            if not chunk: break
            total += len(chunk); require(total <= self.maximum); chunks.append(chunk)
        data = b''.join(chunks)
        require(self.virtual or len(data) == self.meta[6])
        require(metadata(b.call(os.fstat, self.fd)) == self.meta)
        require(metadata(b.call(os.stat, self.name, dir_fd=self.parent, follow_symlinks=False)) == self.meta)
        if self.expected is not None: require(digest(data) == self.expected)
        return data

    def bind(self, expected=None):
        data = self.read()
        self.expected = expected if expected is not None else digest(data)
        require(matches(self.expected, HASH) and digest(data) == self.expected)
        return data


def read_stream(fd, budget):
    """Pipe/FIFO only, bounded until EOF; no reader may outlive the shared budget."""
    before = budget.call(os.fstat, fd)
    if not stat.S_ISFIFO(before.st_mode): raise InvalidInput()
    chunks, total = [], 0
    with selectors.DefaultSelector() as selector:
        budget.call(selector.register, fd, selectors.EVENT_READ)
        while True:
            events = budget.call(selector.select, budget.remaining())
            if not events: raise Expired()
            current = budget.call(os.fstat, fd)
            if identity(current) != identity(before) or not stat.S_ISFIFO(current.st_mode): raise InvalidInput()
            chunk = budget.call(os.read, fd, min(65536, MIB + 1 - total))
            if not chunk: break
            total += len(chunk)
            if total > MIB: raise InvalidInput()
            chunks.append(chunk)
    budget.check()
    return b''.join(chunks)


def module_bytes(data, path, name):
    module = types.ModuleType(name)
    module.__file__ = path
    exec(compile(data, path, 'exec'), module.__dict__)
    return module


def probe(host, fd, target, budget):
    budget.check()
    try:
        result = host._probe(fd, target, budget)
    except host.Expired:
        raise Expired() from None
    except host.RecoveryIncomplete:
        raise RecoveryIncomplete() from None
    except host.Denied:
        raise Denied() from None
    budget.check()
    return result


def absent(fs, parent, name):
    try:
        fs.budget.call(os.stat, name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return True
    return False


def socket_guards(fs):
    run = fs.directory('/run', None)
    require(absent(fs, run, 'docker.sock'))
    var = fs.directory('/var', None)
    value = fs.budget.call(os.stat, 'run', dir_fd=var, follow_symlinks=False)
    if stat.S_ISLNK(value.st_mode):
        require(_owner(value) and fs.budget.call(os.readlink, 'run', dir_fd=var) in ('/run', '../run'))
        # Only this standard root-controlled alias is accepted, and only for absence.
        require(identity(fs.budget.call(os.stat, 'run', dir_fd=var, follow_symlinks=False)) == identity(value))
    else:
        alternate = fs.directory('/var/run', None)
        require(absent(fs, alternate, 'docker.sock'))


def write_all(fd, data, budget):
    view = memoryview(data)
    while view:
        count = budget.call(os.write, fd, view[:65536])
        require(type(count) is int and 0 < count <= len(view[:65536]))
        view = view[count:]


class Transaction:
    """Exclusive flat tree. Cleanup never removes a promoted or substituted tree."""
    def __init__(self, fs, parent, name):
        self.fs, self.parent, self.name = fs, parent, name
        self.fd, self.ident, self.files = None, None, {}
        self.created = self.promoted = False

    def start(self):
        b = self.fs.budget
        b.check()
        os.mkdir(self.name, 0o700, dir_fd=self.parent)
        self.created = True
        self.ident = identity(os.stat(self.name, dir_fd=self.parent, follow_symlinks=False))
        self.fd = self.fs.open(os.open, self.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.parent)
        require(identity(b.call(os.fstat, self.fd)) == self.ident)
        b.check()

    def build(self, values):
        b = self.fs.budget
        for name, data in values.items():
            b.check()
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)
            try:
                self.files[name] = identity(os.fstat(fd))
                b.check()
                write_all(fd, data, b)
                b.call(os.fsync, fd)
                b.call(os.fchown, fd, 1000, 1000)
                b.call(os.fchmod, fd, 0o400)
                b.call(os.fsync, fd)
            finally:
                close_fd(fd)
            b.check()
        b.call(os.fchown, self.fd, 1000, 1000)
        b.call(os.fchmod, self.fd, 0o500)
        b.call(os.fsync, self.fd)

    def verify(self, values, name=None):
        b = self.fs.budget
        name = name or self.name
        require(identity(b.call(os.stat, name, dir_fd=self.parent, follow_symlinks=False)) == self.ident)
        # Reopen the final tree as well as retaining the pinned original descriptor.
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.parent)
        try:
            b.check()
            value = b.call(os.fstat, fd)
            require(identity(value) == self.ident and _owner(value, 1000, 1000) and stat.S_IMODE(value.st_mode) == 0o500)
            require(set(b.call(os.listdir, fd)) == set(values))
            for leaf, expected in values.items():
                item = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
                try:
                    b.check()
                    initial = b.call(os.fstat, item)
                    require(identity(initial) == self.files[leaf] and stat.S_ISREG(initial.st_mode) and initial.st_nlink == 1)
                    require(_owner(initial, 1000, 1000) and stat.S_IMODE(initial.st_mode) == 0o400 and initial.st_size == len(expected))
                    chunks, size = [], 0
                    while True:
                        chunk = b.call(os.read, item, min(16385 - size, 4096))
                        if not chunk: break
                        size += len(chunk); require(size <= 16384); chunks.append(chunk)
                    require(b''.join(chunks) == expected)
                    require(metadata(b.call(os.fstat, item)) == metadata(initial))
                    require(metadata(b.call(os.stat, leaf, dir_fd=fd, follow_symlinks=False)) == metadata(initial))
                finally:
                    close_fd(item)
                b.check()
        finally:
            close_fd(fd)
        b.check()

    def cleanup(self):
        if not self.created or self.promoted: return
        b = self.fs.budget
        b.check()
        require(self.fd is not None and self.ident is not None)
        require(identity(b.call(os.stat, self.name, dir_fd=self.parent, follow_symlinks=False)) == self.ident)
        require(identity(b.call(os.fstat, self.fd)) == self.ident)
        require(set(b.call(os.listdir, self.fd)) == set(self.files))
        for name, ident in self.files.items():
            value = b.call(os.stat, name, dir_fd=self.fd, follow_symlinks=False)
            require(identity(value) == ident and stat.S_ISREG(value.st_mode) and value.st_nlink == 1)
            require(_owner(value) or _owner(value, 1000, 1000))
        b.call(os.fchmod, self.fd, 0o700)
        for name in self.files: b.call(os.unlink, name, dir_fd=self.fd)
        b.call(os.rmdir, self.name, dir_fd=self.parent)
        b.call(os.fsync, self.parent)


class Journal:
    def __init__(self, fs, directory, authorization, bindings):
        self.fs, self.directory = fs, directory
        self.name = 'private-material-' + authorization + '.json'
        self.temporary = '.private-material-' + authorization
        self.bindings, self.ident = bindings, None
        require(absent(fs, directory, self.name) and absent(fs, directory, self.temporary))

    def persist(self, phase):
        b = self.fs.budget
        data = canonical({**self.bindings, 'updated_at': stamp(),
                          'elapsed_seconds': max(0, time.monotonic() - b.started),
                          'phase': phase, 'operation_status': 'unconfirmed'})
        require(len(data) <= 65536)
        # Refuse unrelated journal replacements, even under the shared lock.
        if self.ident is not None:
            require(identity(b.call(os.stat, self.name, dir_fd=self.directory, follow_symlinks=False)) == self.ident)
        else:
            require(absent(self.fs, self.directory, self.name))
        b.check()
        fd = os.open(self.temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.directory)
        ident = identity(os.fstat(fd))
        try:
            b.check()
            write_all(fd, data, b)
            b.call(os.fchmod, fd, 0o600)
            b.call(os.fsync, fd)
        finally:
            close_fd(fd)
        b.check()
        value = b.call(os.stat, self.temporary, dir_fd=self.directory, follow_symlinks=False)
        require(identity(value) == ident and stat.S_ISREG(value.st_mode) and value.st_nlink == 1 and _owner(value))
        if self.ident is not None:
            require(identity(b.call(os.stat, self.name, dir_fd=self.directory, follow_symlinks=False)) == self.ident)
            b.call(os.replace, self.temporary, self.name, src_dir_fd=self.directory, dst_dir_fd=self.directory)
        else:
            # Initial intent must never overwrite an existing authorization.
            self.fs.host._rename_noreplace(self.directory, self.temporary, self.name)
            b.check()
        self.ident = ident
        b.call(os.fsync, self.directory)


def install_cli(source, service):
    output = receipt(source if matches(source, SHA) else None, service if service in SERVICE_NAMES else None)
    if not matches(source, SHA) or service not in SERVICE_NAMES: return finish(output, 2)
    b, stack = Budget(), ExitStack()
    tx = journal = fs = None
    writing = committed = False
    code = 3
    try:
        require(os.geteuid() == 0)
        stack.callback(os.umask, os.umask(0o077))
        fs = Filesystem(stack, b)
        config_file = fs.file('/etc/autodata/host.json', 0o600)
        config = strict_json(config_file.bind())
        require(type(config) is dict and config.get('environment') == 'staging')
        approval_file = fs.file('/etc/autodata/private-material-approval.json', 0o600, 65536)
        approval = strict_json(approval_file.bind())
        validate_approval(approval, source, service, digest(canonical(config)), utcnow())
        output.update({key: approval[key] for key in HASH_FIELDS + ('authorization_id', 'secret_versions')})
        output['approval_sha256'] = approval_file.expected
        evidence = fs.file('/etc/autodata/publisher-accepted/' + source + '.json', 0o600, 65536)
        evidence.bind(approval['publisher_verification_receipt_sha256'])
        host_file = fs.file(BIN + 'host_install.py', None)
        host_data = host_file.bind(approval['host_install_helper_sha256'])
        runtime_file = fs.file(BIN + 'runtime-check.py', None)
        runtime_data = runtime_file.bind(approval['runtime_helper_sha256'])
        schema_file = fs.file(BIN + 'release.schema.json', None)
        schema_data = schema_file.bind(approval['release_schema_sha256'])
        fs.host = module_bytes(host_data, BIN + 'host_install.py', '_private_material_host')
        runtime = module_bytes(runtime_data, BIN + 'runtime-check.py', '_private_material_runtime')
        b.check()
        require(runtime.validate_config(config) == approval['service_config_sha256'])
        for selected, names in SERVICE_NAMES.items(): require(runtime.SECRET_NAMES[selected] == names)
        manifest_file = fs.file('/opt/autodata/releases/' + source + '/release.json', 0o600)
        manifest = runtime.strict_json(manifest_file.bind(approval['manifest_raw_sha256']))
        require(validate_pinned_first_manifest(manifest, config, schema_data, runtime) == approval['manifest_canonical_sha256'])
        require(manifest['source_sha'] == source and manifest['secret_versions'][service] == approval['secret_versions'])
        acceptance_file = fs.file('/etc/autodata/pre-daemon-accepted/' + approval['authorization_id'] + '.json', 0o600, 65536)
        accepted = strict_json(acceptance_file.bind(approval['owner_pre_daemon_host_evidence_sha256']))
        machine = fs.file('/etc/machine-id', None, 128)
        machine.bind()
        boot = fs.file('/proc/sys/kernel/random/boot_id', None, 128, virtual=True)
        boot.bind()
        binary = fs.file('/usr/bin/findmnt', None)
        require(binary.meta[2] & 0o111 != 0)
        binary.bind(approval['findmnt_binary_sha256'])
        data, run = fs.directory(DATA, 0o700), fs.directory(RUN, 0o700)
        opt = fs.directory('/opt/autodata', 0o700)
        mounts_identity = (identity(b.call(os.fstat, data)), identity(b.call(os.fstat, run)))
        lock = lock_identity = state = None

        def guards():
            b.check()
            fs.recheck()
            validate_approval(approval, source, service, approval['service_config_sha256'], utcnow())
            validate_host_record(accepted, approval, config, machine.read(), boot.read(), utcnow())
            require(absent(fs, opt, 'current'))
            socket_guards(fs)
            binary.read()
            runtime.validate_mount_observations(config, runtime.strict_json(probe(fs.host, binary.fd, DATA, b)),
                                                runtime.strict_json(probe(fs.host, binary.fd, RUN, b)))
            binary.read()
            fs.recheck()
            validate_host_record(accepted, approval, config, machine.read(), boot.read(), utcnow())
            validate_approval(approval, source, service, approval['service_config_sha256'], utcnow())
            require((identity(b.call(os.fstat, data)), identity(b.call(os.fstat, run))) == mounts_identity)
            if lock is not None:
                require(metadata(b.call(os.stat, 'operation.lock', dir_fd=state, follow_symlinks=False)) == lock_identity)
                require(metadata(b.call(os.fstat, lock)) == lock_identity)
                b.call(fcntl.flock, lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(absent(fs, opt, 'current'))
            socket_guards(fs)
            b.check()

        guards()
        require(absent(fs, run, service) and not any(name.startswith('.private-') for name in b.call(os.listdir, run)))
        # Replay/temp checks precede stream reads and any material writes.
        if not absent(fs, data, 'operations'):
            operations = fs.directory(DATA + '/operations', 0o700)
            require(absent(fs, operations, 'private-material-' + approval['authorization_id'] + '.json'))
            require(absent(fs, operations, '.private-material-' + approval['authorization_id']))
        state = fs.directory(RUN + '/state', 0o700, create=True)
        lock = fs.open(os.open, 'operation.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=state)
        value = b.call(os.fstat, lock)
        require(stat.S_ISREG(value.st_mode) and _owner(value) and value.st_nlink == 1 and stat.S_IMODE(value.st_mode) == 0o600)
        lock_identity = metadata(value)
        b.call(fcntl.flock, lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        guards()
        values = parse_stream(read_stream(0, b), approval)
        guards()
        require(absent(fs, run, service) and absent(fs, run, '.private-' + approval['authorization_id']))
        operations = fs.directory(DATA + '/operations', 0o700, create=True)
        bindings = {key: output[key] for key in ('schema_version', 'operation', 'source_sha', 'service', 'authorization_id',
                                                'started_at', 'approval_sha256', 'secret_versions') + HASH_FIELDS}
        journal = Journal(fs, operations, approval['authorization_id'], bindings)
        journal.persist('writing')
        writing = True
        output['commit_state'] = 'writing'
        guards()
        tx = Transaction(fs, run, '.private-' + approval['authorization_id'])
        tx.start(); tx.build(values); tx.verify(values)
        guards()
        require(absent(fs, run, service))
        b.check()
        fs.host._rename_noreplace(run, tx.name, service)
        tx.promoted = committed = True
        output['secret_material_committed'] = True
        output['commit_state'] = 'promoted'
        b.check()
        b.call(os.fsync, run)
        guards()
        journal.persist('promoted')
        tx.verify(values, service)
        guards()
        # All writers are already closed. Keep journal/lock resources until fsync.
        journal.persist('material_verified')
        output['commit_state'] = 'material_verified'
        stack.close()
        b.check()
        return finish(output, 0)
    except BaseException as error:
        code = (6 if isinstance(error, RecoveryIncomplete) else 5 if isinstance(error, Expired)
                else 2 if isinstance(error, InvalidInput) else 3 if isinstance(error, Denied) or not writing else 4)
        if committed and code not in (5, 6): code = 6
        b.cleanup = True
        try:
            if fs is not None and tx is not None and not committed:
                guards()
                tx.cleanup()
            if journal is not None:
                guards()
                journal.persist('incomplete')
        except BaseException:
            code = 6
        try:
            stack.close()
        except BaseException:
            code = 6
        output['secret_material_committed'] = committed
        if code == 6: output['commit_state'] = 'incomplete'
        return finish(output, code)


def main(argv):
    if (len(argv) != 3 or argv[0] != 'install' or not matches(argv[1], SHA) or argv[2] not in SERVICE_NAMES):
        return finish(receipt(), 2)
    return install_cli(argv[1], argv[2])


if __name__ == '__main__':
    os.environ.clear()
    os.chdir('/')
    code, output = main(sys.argv[1:])
    sys.stdout.write(canonical(output).decode('utf-8') + '\n')
    raise SystemExit(code)
