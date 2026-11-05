#!/usr/bin/python3 -I
"""Fixed staging operator. Importing this module discovers no credentials.

Owner-installed inputs are under /etc/autodata/staging-operator. Each process
executes one phase; private is explicitly one service per invocation. Failed
remote commands are incomplete and require owner readback, never blind retry.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit
import uuid

ROOT = '/etc/autodata/staging-operator'
STATE = '/var/lib/autodata-staging-operator'
BIN = '/opt/autodata/bin'
PHASES = ('bootstrap', 'provision-check', 'provision', 'install', 'images', 'database', 'private', 'start', 'check')
SERVICES = ('api', 'ingestion-http', 'article-worker', 'payment-reconciler', 'outbox-relay')
# Frozen helper budgets include their existing cleanup reserves. Bootstrap
# reads its owner token for up to30s before starting the1800s cloud budget.
HELPER_LIMITS = {'bootstrap': 1830, 'provision-check': 900, 'provision': 900,
                 'install': 300, 'images': 2400, 'database': 2400,
                 'private': 330, 'start': 120, 'check': 120}
WRAPPER_MARGIN = 180
TRANSPORT_MARGIN = 180
MAX_PROCESS_SECONDS = max(max(1800, value+WRAPPER_MARGIN)+TRANSPORT_MARGIN for value in HELPER_LIMITS.values())
READINESS = ('config', 'manifest', 'disk_uuid', 'metadata_guard', 'storage_guard', 'secrets', 'cached_images',
             'migration_tree', 'schema', 'services', 'postgres', 'nats', 's3', 'no_work', 'runtime_evidence')
MIB = 1048576
ENV = {'PATH': '/usr/bin:/bin', 'HOME': '/root', 'LANG': 'C', 'LC_ALL': 'C',
       'CLOUDSDK_CONFIG': ROOT + '/gcloud', 'CLOUDSDK_CORE_DISABLE_PROMPTS': '1'}
TOOLS = {'gcloud': '/usr/bin/gcloud', 'ssh': '/usr/bin/ssh', 'cloud-bootstrap.sh': BIN + '/cloud-bootstrap.sh'}
SHA = r'[0-9a-f]{40}'
HASH = r'[0-9a-f]{64}'
NAME = r'[a-z][a-z0-9-]{0,57}'
CONFIG_FIELDS = ('schema_version environment source_sha project_id region zone maximum_monthly_budget_usd staging_origin '
                 'instance_name instance_id os_login_user repository_id repository_owner_id protected_environment '
                 'wif_provider service_account registry toolchain_image service_config_sha256 bundle_inventory_sha256 '
                 'known_hosts_sha256 ssh_identity_sha256 tools').split()


class Rejected(ValueError):
    def __init__(self): super().__init__('staging operator rejected input')


class Incomplete(Exception):
    def __init__(self): super().__init__('operation incomplete; owner readback required')


def require(value):
    if not value: raise Rejected()


def matches(value, pattern): return type(value) is str and re.fullmatch(pattern, value) is not None

def digest(data): return hashlib.sha256(data).hexdigest()

def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def object_json(data, maximum=MIB):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result); result[key] = value
        return result
    try:
        require(type(data) is bytes and 0 < len(data) <= maximum)
        value = json.loads(data, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(Rejected()))
        require(type(value) is dict)
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError): raise Rejected() from None


def validate_config(value, source, *, bootstrap=False):
    require(matches(source, SHA) and type(value) is dict and set(value) == set(CONFIG_FIELDS))
    require(type(value['schema_version']) is int and value['schema_version'] == 1)
    require(value['environment'] == 'staging' and value['source_sha'] == source)
    for name in ('project_id', 'region', 'zone', 'instance_name'): require(matches(value[name], NAME))
    require(value['zone'].startswith(value['region'] + '-'))
    if bootstrap: require((value['instance_id'] is None) == (value['known_hosts_sha256'] is None))
    require(type(value['maximum_monthly_budget_usd']) in (int, float) and 0 < value['maximum_monthly_budget_usd'] < 1e9)
    for name in ('instance_id', 'repository_id', 'repository_owner_id'):
        if bootstrap and name == 'instance_id' and value[name] is None: continue
        require(matches(value[name], r'[1-9][0-9]{0,19}'))
    require(matches(value['os_login_user'], r'[a-z_][a-z0-9_-]{0,63}'))
    require(value['protected_environment'] == 'workshop-staging-publish')
    require(matches(value['wif_provider'], r'projects/[1-9][0-9]*/locations/global/workloadIdentityPools/[a-z0-9-]+/providers/[a-z0-9-]+'))
    require(matches(value['service_account'], r'[a-z][a-z0-9-]+@' + re.escape(value['project_id']) + r'\.iam\.gserviceaccount\.com'))
    require(matches(value['registry'], re.escape(value['region']) + r'-docker\.pkg\.dev/' + re.escape(value['project_id']) + r'/[a-z0-9-]+'))
    require(matches(value['toolchain_image'], r'[a-z0-9./-]+@sha256:' + HASH))
    for name in ('service_config_sha256', 'bundle_inventory_sha256', 'known_hosts_sha256', 'ssh_identity_sha256'):
        if bootstrap and name == 'known_hosts_sha256' and value[name] is None: continue
        require(matches(value[name], HASH))
    require(type(value['tools']) is dict and set(value['tools']) == set(TOOLS))
    require(all(matches(pin, HASH) for pin in value['tools'].values()))
    try:
        origin = urlsplit(value['staging_origin'])
        require(origin.scheme == 'https' and origin.username is None and origin.password is None and origin.port is None)
        require(origin.path == '' and not origin.query and not origin.fragment)
        require(matches(origin.hostname, r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?'))
        require(origin.hostname not in ('cars.tk', 'www.cars.tk'))
    except (ValueError, TypeError, AttributeError): raise Rejected() from None


def phase_timeout(phase, *, workstation):
    require(phase in HELPER_LIMITS and type(workstation) is bool)
    wrapper = max(1800, HELPER_LIMITS[phase]+WRAPPER_MARGIN)
    return wrapper + (TRANSPORT_MARGIN if workstation else 0)


def _bootstrap_descriptor(argv, approved):
    require(type(approved) is bool)
    if not approved: return ()
    require(argv == [TOOLS['cloud-bootstrap.sh'], 'apply'])
    try:
        value = os.fstat(3)
        require(stat.S_ISFIFO(value.st_mode))
        require(fcntl.fcntl(3, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY)
    except OSError: raise Rejected() from None
    return (3,)


def _run_process(argv, *, input_data=None, timeout=120, maximum=65536, bootstrap_token=False):
    """Finite argv, bounded combined output, process-group deadline and cleanup.

    Child stderr is intentionally never returned or persisted, including errors.
    The supplied environment has no ambient proxy, token or SSH agent discovery.
    """
    require(type(argv) is list and argv and all(type(arg) is str and '\x00' not in arg for arg in argv))
    require(argv[0].startswith('/') and 0 < timeout <= MAX_PROCESS_SECONDS and 0 < maximum <= 70*MIB)
    require(input_data is None or type(input_data) is bytes and len(input_data) <= 70*MIB)
    approved_fds = _bootstrap_descriptor(argv, bootstrap_token)
    end = time.monotonic() + timeout
    try:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='/', env=ENV, start_new_session=True,
                                   close_fds=True, pass_fds=approved_fds)
    except OSError: raise Incomplete() from None
    output, total = bytearray(), 0
    try:
        with selectors.DefaultSelector() as selector:
            for pipe in (process.stdout, process.stderr):
                os.set_blocking(pipe.fileno(), False); selector.register(pipe, selectors.EVENT_READ)
            pending = memoryview(input_data or b'')
            if input_data is not None:
                os.set_blocking(process.stdin.fileno(), False); selector.register(process.stdin, selectors.EVENT_WRITE)
            while selector.get_map():
                remaining = end - time.monotonic()
                if remaining <= 0: raise Incomplete()
                events = selector.select(remaining)
                if not events: raise Incomplete()
                for key, _ in events:
                    pipe = key.fileobj
                    if pipe is process.stdin:
                        if pending: pending = pending[os.write(pipe.fileno(), pending[:4096]):]
                        if not pending: selector.unregister(pipe); pipe.close()
                    else:
                        part = os.read(pipe.fileno(), min(65536, maximum+1-total))
                        if not part: selector.unregister(pipe); continue
                        total += len(part)
                        if total > maximum: raise Incomplete()
                        if pipe is process.stdout: output.extend(part)
            if process.wait(timeout=max(.001, end-time.monotonic())) != 0: raise Incomplete()
        return bytes(output)
    except (OSError, subprocess.TimeoutExpired): raise Incomplete() from None
    finally:
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None: pipe.close()
        process.wait(timeout=2)


def run_process(argv, *, input_data=None, timeout=120, maximum=65536, bootstrap_token=False):
    previous_handler = signal.getsignal(signal.SIGTERM)
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    require(signal.SIGTERM not in previous_mask)
    def cancelled(*_): raise Incomplete()
    try:
        signal.signal(signal.SIGTERM, cancelled)
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        return _run_process(argv, input_data=input_data, timeout=timeout, maximum=maximum, bootstrap_token=bootstrap_token)
    finally:
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
        signal.signal(signal.SIGTERM, previous_handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def remote_argv(config, phase, source, service=None):
    validate_config(config, source)
    require(phase in PHASES[1:] or phase == 'receive')
    if phase == 'private': require(service in SERVICES)
    else: require(service is None)
    commands = {
        'provision-check': [BIN+'/host_provision.py', 'check', source],
        'provision': [BIN+'/host_provision.py', 'apply', source],
        'install': [BIN+'/deploy.sh', 'install', source],
        'images': [BIN+'/host_prepare_release.py', 'images', source],
        'database': [BIN+'/host_prepare_release.py', 'database', source],
        'private': [BIN+'/private_material.py', 'install', source, service or ''],
        'start': [BIN+'/deploy.sh', 'start', source],
        'check': [BIN+'/deploy.sh', 'check', source],
        'receive': [BIN+'/staging_deploy.py', '--receive', source]}
    command = commands[phase]
    if command[0].endswith('.py'): command = ['/usr/bin/python3', '-I'] + command
    # Every atom is a fixed literal, a validated SHA, or a fixed service name.
    remote = ' '.join(['/usr/bin/sudo', '-n', '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin'] + command)
    # Direct OpenSSH owns every option. gcloud compute ssh is deliberately
    # avoided: its generated options could precede and override key pinning.
    proxy = ' '.join([TOOLS['gcloud'], '--quiet', 'compute', 'start-iap-tunnel', config['instance_name'], '22',
                      '--listen-on-stdin', '--project='+config['project_id'], '--zone='+config['zone']])
    options = ['IdentityFile='+ROOT+'/identity', 'BatchMode=yes', 'ForwardAgent=no', 'ClearAllForwardings=yes', 'StrictHostKeyChecking=yes',
        'UserKnownHostsFile='+ROOT+'/known_hosts', 'GlobalKnownHostsFile=/dev/null',
        'HostKeyAlias=compute.'+config['instance_id'], 'HostKeyAlgorithms=ssh-ed25519',
        'IdentitiesOnly=yes', 'PasswordAuthentication=no', 'KbdInteractiveAuthentication=no',
        'PreferredAuthentications=publickey', 'PermitLocalCommand=no', 'ControlMaster=no', 'ControlPath=none',
        'RequestTTY=no', 'ConnectTimeout=20', 'ServerAliveInterval=15', 'ServerAliveCountMax=2',
        'ProxyCommand='+proxy]
    argv = [TOOLS['ssh'], '-F', '/dev/null']
    for option in options: argv.extend(['-o', option])
    return argv + ['--', config['os_login_user']+'@'+config['instance_name'], remote]


def validate_receipt(phase, value, source, config_hash, service=None):
    require(type(value) is dict and value.get('source_sha') == source)
    if phase == 'provision-check':
        require(set(value) == {'status', 'source_sha', 'production_ready'} and value['status'] == 'checked' and value['production_ready'] is False)
        return
    require(type(value.get('schema_version')) is int and value['schema_version'] == 1 and value.get('status') == 'passed')
    if phase in ('start', 'check'):
        fields = set(('schema_version operation run_id source_sha status started_at finished_at checks failure_code').split())
    elif phase == 'install': fields = set(_sibling('host_install')._receipt(source))
    elif phase == 'private': fields = set(_sibling('private_material').receipt(source, service))
    else:
        fields = set(('schema_version authorization_id source_sha operation bundle_inventory_sha256 '
                      'service_config_sha256 approval_sha256 production_ready status stages').split())
        if phase in ('images', 'database'): fields.add('manifest_raw_sha256')
        if phase == 'images': fields.add('images')
        if phase == 'database': fields.add('image_cache_receipt_sha256')
    require(set(value) == fields)
    operations = {'provision': ('prepare-new-empty-staging-host',), 'images': ('cache-accepted-staging-images',),
                  'database': ('initialize-fresh-staging-database', 'resume-created-staging-database'),
                  'install': ('deploy.sh install',), 'private': ('install-first-application-private-material',),
                  'start': ('deploy.sh start',), 'check': ('deploy.sh check',)}
    require(value.get('operation') in operations[phase])
    if phase in ('provision', 'images', 'database', 'install', 'private'):
        require(value.get('service_config_sha256') == config_hash)
    if phase in ('start', 'check', 'install'):
        require(value.get('failure_code') is None and type(value.get('checks')) is dict)
        for name in ('started_at', 'finished_at'):
            require(matches(value.get(name), r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ'))
        require(value['started_at'] <= value['finished_at'])
    if phase in ('start', 'check'):
        require(value.get('run_id') is None and set(value['checks']) == set(READINESS))
        require(all(value['checks'][name] is True for name in READINESS))
    if phase == 'install':
        require(value.get('release_material_committed') is True and value.get('commit_state') == 'receipt_committed')
        require(all(value['checks'].get(name) is True for name in ('config', 'manifest', 'migration_tree', 'disk_uuid')))
        require(all(value['checks'].get(name) is False for name in ('schema', 'services', 'runtime_evidence')))
    if phase in ('provision', 'images', 'database'):
        require(value.get('production_ready') is False and type(value.get('stages')) is list)
        stages = {'provision': ('docker-started',), 'images': ('images-verified',), 'database': ('schema-verified',)}[phase]
        require(all(name in value['stages'] for name in stages))
    if phase == 'private':
        require(value.get('service') == service and value.get('failure_code') is None)
        require(value.get('one_service_private_material_installed') is True and value.get('secret_material_committed') is True)
        require(value.get('runtime_evidence') is False)


def _sibling(name):
    spec = importlib.util.spec_from_file_location('_staging_'+name.replace('-', '_'), Path(__file__).resolve().parent/(name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main(argv):
    if len(argv) != 2 or argv[0] not in PHASES or not matches(argv[1], SHA):
        return 2, {'status': 'failed', 'failure_code': 'invalid_input'}
    try: return operate(argv[0], argv[1])
    except Rejected: return 2, {'status': 'failed', 'failure_code': 'invalid_input'}
    except Exception: return 6, {'status': 'incomplete', 'failure_code': 'owner_readback_required'}


def validate_phase_approval(value, config, phase, source, predecessor, service=None):
    fields = ('schema_version phase authorization_id expires_at source_sha operator_config_sha256 instance_id '
              'service_config_sha256 service predecessor_sha256 inputs').split()
    require(type(value) is dict and set(value) == set(fields))
    require(type(value['schema_version']) is int and value['schema_version'] == 1)
    require(value['phase'] == phase and value['source_sha'] == source and value['service'] == service)
    require(value['operator_config_sha256'] == digest(canonical(config)))
    require(value['instance_id'] == config['instance_id'] and value['service_config_sha256'] == config['service_config_sha256'])
    require(value['predecessor_sha256'] == predecessor)
    require(matches(value['authorization_id'], r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'))
    require(matches(value['expires_at'], r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ'))
    try:
        expiry = datetime.strptime(value['expires_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        require(0 < (expiry-datetime.now(timezone.utc)).total_seconds() <= 86400)
    except (TypeError, ValueError): raise Rejected() from None
    require(type(value['inputs']) is dict and value['inputs'])
    require(all(matches(key, r'[a-z_]+_sha256') and matches(pin, HASH) for key, pin in value['inputs'].items()))


def next_private(completed):
    require(type(completed) is list and completed == list(SERVICES[:len(completed)]))
    return SERVICES[len(completed)] if len(completed) < len(SERVICES) else None


def decode_transfer(raw, source, approval_hash, approval):
    import base64
    import binascii
    frame = object_json(raw, 70*MIB)
    require(set(frame) == {'schema_version', 'source_sha', 'install_approval_sha256', 'files'})
    require(type(frame['schema_version']) is int and frame['schema_version'] == 1)
    require(frame['source_sha'] == source and frame['install_approval_sha256'] == approval_hash)
    require(type(frame['files']) is list and len(frame['files']) == len(approval['files'])+1)
    expected = {item['path']: (item['bytes'], item['sha256']) for item in approval['files']}
    require(len(expected) == len(approval['files']))
    expected['publisher-verification.json'] = (None, approval['publisher_verification_receipt_sha256'])
    result, total = {}, 0
    for item in frame['files']:
        require(type(item) is dict and set(item) == {'path', 'data'})
        name = item['path']; require(type(name) is str and name in expected and name not in result)
        require(name in ('release.json', 'publisher-verification.json', 'scripts/dev/migrate_sql.sh') or
                matches(name, r'db/migrations/[0-9]{3}_[a-z0-9_]+\.sql'))
        require(type(item['data']) is str and len(item['data']) <= 1400000)
        try: data = base64.b64decode(item['data'], validate=True)
        except (ValueError, binascii.Error): raise Rejected() from None
        require(base64.b64encode(data).decode() == item['data'] and 0 < len(data) <= MIB)
        size, pin = expected[name]; require((size is None or size == len(data)) and digest(data) == pin)
        total += len(data); require(total <= 64*MIB)
        result[name] = data
    require(set(result) == set(expected))
    return result


def _new_file(parent, name, data, mode):
    require('/' not in name and name not in ('.', '..'))
    fd = os.open(name, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC, mode, dir_fd=parent)
    try:
        os.fchmod(fd, mode)
        view = memoryview(data)
        while view:
            count = os.write(fd, view); require(count > 0); view = view[count:]
        os.fsync(fd)
    finally: os.close(fd)
    os.fsync(parent)


def commit_transfer(incoming, evidence, source, members):
    """Descriptor-relative writes into a new inbox; never merge or overwrite.

    On interruption the partial inbox stays as evidence and blocks blind retry.
    The caller holds pinned root-owned parents and the separate receiver lock.
    """
    require(matches(source, SHA) and 'publisher-verification.json' in members)
    for name in members:
        require(name in ('release.json', 'publisher-verification.json', 'scripts/dev/migrate_sql.sh') or
                matches(name, r'db/migrations/[0-9]{3}_[a-z0-9_]+\.sql'))
    try:
        os.stat(source+'.json', dir_fd=evidence, follow_symlinks=False)
    except FileNotFoundError: pass
    else: raise Rejected()
    os.mkdir(source, 0o700, dir_fd=incoming)
    root = os.open(source, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC, dir_fd=incoming)
    directories = {'': root}
    try:
        os.fchmod(root, 0o700)
        for name in ('db', 'db/migrations', 'scripts', 'scripts/dev'):
            parent, leaf = name.rsplit('/', 1) if '/' in name else ('', name)
            os.mkdir(leaf, 0o700, dir_fd=directories[parent])
            directories[name] = os.open(leaf, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC, dir_fd=directories[parent])
        for name, data in members.items():
            if name == 'publisher-verification.json': continue
            parent, leaf = name.rsplit('/', 1) if '/' in name else ('', name)
            _new_file(directories[parent], leaf, data, 0o600 if name == 'release.json' else 0o444)
        _new_file(evidence, source+'.json', members['publisher-verification.json'], 0o600)
        os.fsync(incoming)
    finally:
        for fd in reversed(list(directories.values())): os.close(fd)


def read_pipe(fd, *, maximum, timeout=120):
    require(stat.S_ISFIFO(os.fstat(fd).st_mode))
    end, output = time.monotonic()+timeout, bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while True:
            remaining = end-time.monotonic()
            if remaining <= 0 or not selector.select(remaining): raise Incomplete()
            data = os.read(fd, min(65536, maximum+1-len(output)))
            if not data: return bytes(output)
            output.extend(data)
            if len(output) > maximum: raise Rejected()


def validate_publication_receipt(value, binding_hash):
    require(set(value) == {'protocol_version', 'status', 'simulation', 'provenance_authenticated',
                          'deployment_authorized', 'binding_sha256', 'checks'})
    require(type(value['protocol_version']) is int and value['protocol_version'] == 3)
    require(value['status'] == 'publication_verified' and value['simulation'] is False)
    require(value['provenance_authenticated'] is True and value['deployment_authorized'] is False)
    require(value['binding_sha256'] == binding_hash)
    require(value['checks'] == {'schema': False, 'services': False, 'runtime_evidence': False})
    require(all(type(v) is bool for v in value['checks'].values()))


HOST_APPROVALS = {'bootstrap': '/etc/autodata/staging-bootstrap.json',
    'provision-check': '/etc/autodata/host-provision-approval.json',
    'provision': '/etc/autodata/host-provision-approval.json', 'install': '/etc/autodata/install-approval.json',
    'images': '/etc/autodata/host-prepare-approval.json', 'database': '/etc/autodata/host-prepare-approval.json',
    'private': '/etc/autodata/private-material-approval.json'}
BUNDLE = '/var/lib/autodata-bootstrap/bundle'


@contextmanager
def workstation_lock(pins):
    directory = pins.directory(STATE, 0o700)
    fd = os.open('operation.lock', os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC, 0o600, dir_fd=directory)
    try:
        value = os.fstat(fd)
        require(stat.S_ISREG(value.st_mode) and value.st_uid == 0 and value.st_gid == 0 and value.st_nlink == 1)
        require(stat.S_IMODE(value.st_mode) == 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield directory
        require(os.fstat(fd).st_ino == os.stat('operation.lock', dir_fd=directory, follow_symlinks=False).st_ino)
    finally: os.close(fd)


def _state_name(phase, service=None): return phase + ('-'+service if service else '')


def predecessor(pins, config, phase):
    """Revalidate every prior raw helper receipt, link and input identity."""
    previous, completed, private_service = None, [], None
    for prior in PHASES:
        if prior == phase and phase != 'private': return previous, None
        names = SERVICES if prior == 'private' else (None,)
        for service in names:
            name = _state_name(prior, service)
            path = STATE+'/'+config['source_sha']+'/'+name+'.json'
            try: raw = pins.read(path, maximum=2*MIB)
            except FileNotFoundError:
                if prior == phase == 'private': return previous, next_private(completed)
                raise Rejected() from None
            value = object_json(raw, 2*MIB)
            require(set(value) == {'schema_version', 'phase', 'service', 'source_sha', 'operator_config_sha256',
                                  'instance_id', 'status', 'predecessor_sha256', 'approval_sha256', 'input_sha256', 'receipt'})
            require(type(value['schema_version']) is int and value['schema_version'] == 1 and value['phase'] == prior and value['service'] == service)
            require(value['status'] == ('bootstrap_unaccepted' if prior == 'bootstrap' else 'passed'))
            require(value['source_sha'] == config['source_sha'])
            if prior == 'bootstrap':
                # The new independently approved config may fill only these
                # generated identity fields; all other configuration stays bound.
                initial = dict(config, instance_id=None, known_hosts_sha256=None)
                require(value['operator_config_sha256'] in (digest(canonical(config)), digest(canonical(initial))))
            else: require(value['operator_config_sha256'] == digest(canonical(config)))
            require(value['instance_id'] == config['instance_id'] and value['predecessor_sha256'] == previous)
            require(matches(value['approval_sha256'], HASH) and type(value['input_sha256']) is dict)
            if prior == 'bootstrap': validate_bootstrap_receipt(value['receipt'], config)
            else: validate_receipt(prior, value['receipt'], config['source_sha'], config['service_config_sha256'], service)
            previous = digest(raw)
            if prior == 'private': completed.append(service)
        if prior == phase == 'private': raise Rejected()  # Completed phase is never replayed.
    raise Rejected()


def validate_bootstrap_receipt(value, config):
    require(value.get('schema_version') == 1 and value.get('operation') == 'cloud-bootstrap.sh apply')
    require(value.get('status') == 'passed' and value.get('failure_code') is None)
    require(value.get('source_sha') is None and value.get('definition_only') is False)
    require(value.get('service_config_sha256') == config['service_config_sha256'])
    require(all(value.get('checks', {}).get(name) is True for name in ('config', 'prerequisites', 'address', 'disk', 'instance')))
    require(all(value['checks'].get(name) is False for name in ('schema', 'services', 'runtime_evidence')))
    # staging_bootstrap preserves exact resource selfLinks and numeric IDs.
    actual = value.get('resources', {}).get('instance', {}).get('id')
    require(matches(actual, r'[1-9][0-9]{0,19}'))
    if config['instance_id'] is not None: require(actual == config['instance_id'])


def _bound(raw, expected):
    require(digest(raw) == expected)
    return raw


def owner_inputs(pins, config, phase, approval, service):
    """Validate independently delivered bytes before tool/token access."""
    source, expected = config['source_sha'], approval['inputs']
    inputs, host_approval = {'bundle_inventory_sha256': config['bundle_inventory_sha256']}, None
    if phase in HOST_APPROVALS:
        raw = pins.read(ROOT+'/host-approval.json', maximum=MIB)
        _bound(raw, expected.get('host_approval_sha256'))
        host_approval = object_json(raw)
        inputs['host_approval_sha256'] = digest(raw)
        p = _sibling('host_provision')
        if phase == 'bootstrap':
            rt = _sibling('runtime-check'); bootstrap = _sibling('staging_bootstrap')
            bootstrap.validate_approval(object_json(pins.read('/etc/autodata/host.json')), host_approval, rt, datetime.now(timezone.utc))
        elif phase in ('provision-check', 'provision', 'images', 'database'):
            p.validate_approval(host_approval, source, 'provision' if phase.startswith('provision') else phase)
        elif phase == 'install': _sibling('host_install').validate_approval(host_approval, source, config['service_config_sha256'])
        elif phase == 'private':
            _sibling('private_material').validate_approval(host_approval, source, service, config['service_config_sha256'], datetime.now(timezone.utc))
        if phase != 'bootstrap': require(host_approval['service_config_sha256'] == config['service_config_sha256'])
        if phase in ('provision-check', 'provision', 'images', 'database'):
            require(host_approval['bundle_inventory_sha256'] == config['bundle_inventory_sha256'])
    transfer = None
    if phase == 'install':
        import base64
        material = {name: pins.read(ROOT+'/publication/'+name, maximum=64*MIB if name == 'release.zip' else MIB)
                    for name in ('verification.json', 'binding.json', 'release.json', 'release.zip')}
        for name, raw in material.items(): inputs[name.replace('.', '_')+'_sha256'] = digest(raw)
        binding = object_json(material['binding.json']); receipt = object_json(material['verification.json'])
        validate_publication_receipt(receipt, digest(canonical(binding)))
        require(binding.get('source_sha') == source)
        _bound(material['verification.json'], host_approval['publisher_verification_receipt_sha256'])
        _bound(material['release.json'], host_approval['manifest_raw_sha256'])
        ops = _sibling('cloud-ops'); rt = _sibling('runtime-check')
        manifest = object_json(material['release.json']); host_config = object_json(pins.read('/etc/autodata/host.json'))
        require(rt.validate_manifest(manifest, host_config, None) == host_approval['manifest_canonical_sha256'])
        ops.verify_release_archive(material['release.zip'], manifest,
            expected_archive_sha256=binding['archive_sha256'], expected_member_sha256=binding['member_sha256'])
        # Migration bytes come from the exact owner-delivered reviewed bundle,
        # never from ZIP extraction, repository working files or secret output.
        inventory_raw = pins.read(ROOT+'/bundle/inventory.json', mode=0o444)
        _bound(inventory_raw, config['bundle_inventory_sha256'])
        p.validate_inventory(ROOT+'/bundle', object_json(inventory_raw), source, pins)
        members = {}
        for item in host_approval['files']:
            name = item['path']
            raw = material['release.json'] if name == 'release.json' else pins.read(ROOT+'/bundle/opt/autodata/source/'+name, mode=0o555 if name.endswith('.sh') else 0o444)
            require(len(raw) == item['bytes'] and digest(raw) == item['sha256'])
            members[name] = raw
        members['publisher-verification.json'] = material['verification.json']
        transfer = canonical({'schema_version': 1, 'source_sha': source,
            'install_approval_sha256': inputs['host_approval_sha256'],
            'files': [{'path': name, 'data': base64.b64encode(raw).decode()} for name, raw in sorted(members.items())]})
        decode_transfer(transfer, source, inputs['host_approval_sha256'], host_approval)
    require(inputs == expected)
    return host_approval, transfer


def _host_control(config, phase, approval, service):
    return {'schema_version': 1, 'phase': phase, 'source_sha': config['source_sha'], 'service': service,
            'service_config_sha256': config['service_config_sha256'],
            'bundle_inventory_sha256': config['bundle_inventory_sha256'],
            'host_approval_sha256': approval['inputs'].get('host_approval_sha256')}


def host_argv(config, phase, source, service=None):
    # Reuse the fixed IAP/OS Login options while replacing only the fixed command.
    argv = remote_argv(config, phase, source, service)
    helper = (BUNDLE+'/opt/autodata/bin' if phase in ('provision-check', 'provision') else BIN)+'/staging_deploy.py'
    command = ['/usr/bin/sudo', '-n', '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin',
               '/usr/bin/python3', '-I', helper, '--host-phase', phase, source]
    argv[-1] = ' '.join(command)
    return argv


def operate(phase, source):
    require(os.geteuid() == 0)
    p = _sibling('host_provision')
    with p.Pins() as pins:
        config = object_json(pins.read(ROOT+'/config.json')); validate_config(config, source, bootstrap=phase == 'bootstrap')
        host_raw = pins.read('/etc/autodata/host.json'); host = object_json(host_raw)
        rt = _sibling('runtime-check')
        require(host.get('environment') == 'staging' and rt.validate_config(host) == config['service_config_sha256'])
        require(host['public_origin'] == config['staging_origin'])
        for name, key in (('project_id', 'host_project_id'), ('region', 'region'), ('zone', 'zone'), ('instance_name', 'instance_name')):
            require(config[name] == host['resources'][key])
        with workstation_lock(pins) as directory:
            previous, service = predecessor(pins, config, phase)
            approval_raw = pins.read(ROOT+'/phase-approval.json')
            approval = object_json(approval_raw)
            validate_phase_approval(approval, config, phase, source, previous, service)
            host_approval, transfer = owner_inputs(pins, config, phase, approval, service)
            if phase != 'bootstrap':
                known = pins.read(ROOT+'/known_hosts', mode=0o600)
                _bound(known, config['known_hosts_sha256'])
                require(re.fullmatch(re.escape(('compute.'+config['instance_id']+' ssh-ed25519 ').encode())+rb'[A-Za-z0-9+/]+={0,2}\n?', known) is not None)
            for name, path in TOOLS.items():
                mode = stat.S_IMODE(os.stat(path, follow_symlinks=False).st_mode)
                require(mode in (0o555, 0o755))
                _bound(pins.read(path, mode=mode, maximum=64*MIB), config['tools'][name])
            pins.directory(ROOT+'/gcloud', 0o700)
            if phase != 'bootstrap':
                _bound(pins.read(ROOT+'/identity', maximum=65536), config['ssh_identity_sha256'])
            pins.recheck()
            try: os.mkdir(source, 0o700, dir_fd=directory)
            except FileExistsError: pass
            state_dir = pins.directory(STATE+'/'+source, 0o700)
            name = _state_name(phase, service)
            # An immutable intent is written before any cloud/remote process.
            # A retained intent without success requires explicit owner recovery.
            _new_file(state_dir, name+'.intent', canonical({'source_sha': source,
                'phase': phase, 'service': service, 'approval_sha256': digest(approval_raw),
                'operator_config_sha256': digest(canonical(config)), 'instance_id': config['instance_id'],
                'predecessor_sha256': previous, 'input_sha256': approval['inputs']}), 0o600)
            try:
                pins.recheck()
                if phase == 'bootstrap':
                    # Preserve bootstrap's installed fixed-input authority.
                    _bound(pins.read(HOST_APPROVALS[phase]), approval['inputs']['host_approval_sha256'])
                    output = run_process([TOOLS['cloud-bootstrap.sh'], 'apply'],
                        timeout=phase_timeout('bootstrap', workstation=True), bootstrap_token=True)
                    result = object_json(output); validate_bootstrap_receipt(result, config)
                else:
                    described = object_json(run_process([TOOLS['gcloud'], '--quiet', 'compute', 'instances', 'describe',
                        config['instance_name'], '--project='+config['project_id'], '--zone='+config['zone'], '--format=json'], maximum=MIB))
                    require(described.get('id') == config['instance_id'] and described.get('name') == config['instance_name'])
                    require(described.get('status') == 'RUNNING')
                    pins.recheck()
                    if phase == 'install':
                        received = object_json(run_process(remote_argv(config, 'receive', source), input_data=transfer, timeout=300))
                        require(received == {'schema_version': 1, 'status': 'material_received', 'source_sha': source,
                                             'install_approval_sha256': approval['inputs']['host_approval_sha256']})
                    control = canonical(_host_control(config, phase, approval, service))
                    data = len(control).to_bytes(4, 'big')+control
                    if phase == 'private': data += read_pipe(0, maximum=MIB, timeout=120)
                    pins.recheck()
                    output = run_process(host_argv(config, phase, source, service), input_data=data,
                        timeout=phase_timeout(phase, workstation=True))
                    result = object_json(output)
                    validate_receipt(phase, result, source, config['service_config_sha256'], service)
                    if phase in ('provision', 'images', 'database'):
                        require(result.get('approval_sha256') == digest(canonical(host_approval)))
                        require(result.get('bundle_inventory_sha256') == config['bundle_inventory_sha256'])
                    if phase == 'install': require(result.get('install_approval_sha256') == approval['inputs']['host_approval_sha256'])
                    if phase == 'private': require(result.get('approval_sha256') == approval['inputs']['host_approval_sha256'])
                pins.recheck()
                validate_phase_approval(approval, config, phase, source, previous, service)
                record = {'schema_version': 1, 'phase': phase, 'service': service, 'source_sha': source,
                    'operator_config_sha256': digest(canonical(config)),
                    'instance_id': result['resources']['instance']['id'] if phase == 'bootstrap' else config['instance_id'],
                    'status': 'bootstrap_unaccepted' if phase == 'bootstrap' else 'passed', 'predecessor_sha256': previous, 'approval_sha256': digest(approval_raw),
                    'input_sha256': approval['inputs'], 'receipt': result}
                _new_file(state_dir, name+'.json', canonical(record), 0o600)
                # Only check, with a verified predecessor chain including actual
                # start readiness, may make the deployment assertion.
                return 0, {'status': 'staging_deployed' if phase == 'check' else 'bootstrap_unaccepted' if phase == 'bootstrap' else 'phase_passed',
                           'phase': phase, 'service': service, 'source_sha': source,
                           'receipt_sha256': digest(canonical(record)), 'instance_id': record['instance_id']}
            except BaseException:
                try:
                    _new_file(state_dir, name+'.failure', canonical({'status': 'incomplete',
                        'source_sha': source, 'phase': phase, 'service': service,
                        'instance_id': config['instance_id'], 'predecessor_sha256': previous,
                        'input_sha256': approval['inputs'], 'approval_sha256': digest(approval_raw),
                        'failure_code': 'owner_readback_required'}), 0o600)
                except Exception: pass
                raise Incomplete() from None


def receive(source):
    require(matches(source, SHA) and os.geteuid() == 0)
    p, install = _sibling('host_provision'), _sibling('host_install')
    with p.Pins() as pins:
        config = object_json(pins.read('/etc/autodata/host.json'))
        require(config.get('environment') == 'staging')
        approval_raw = pins.read('/etc/autodata/install-approval.json')
        approval = object_json(approval_raw)
        install.validate_approval(approval, source, digest(canonical(config)))
        raw = read_pipe(0, maximum=70*MIB, timeout=120)
        members = decode_transfer(raw, source, digest(approval_raw), approval)
        incoming = pins.directory('/var/lib/autodata/incoming', 0o700)
        evidence = pins.directory('/etc/autodata/publisher-accepted', 0o700)
        # Separate receiver lock; never hold operation.lock around host helpers.
        with p.locked('/var/lib/autodata-bootstrap/receiver.lock'):
            pins.recheck(); install.validate_expiry(approval)
            commit_transfer(incoming, evidence, source, members)
            pins.recheck(); install.validate_expiry(approval)
        return {'schema_version': 1, 'status': 'material_received', 'source_sha': source,
                'install_approval_sha256': digest(approval_raw)}


def host_phase(phase, source):
    """Installed finite host dispatcher, binding inputs before helper invocation.

    The control frame is bounded and contains no authority beyond the existing
    root-owned host approval. Private frame bytes stay opaque until the existing
    private_material helper consumes its pipe. No secret value enters a receipt.
    """
    require(os.geteuid() == 0 and phase in PHASES[1:] and matches(source, SHA))
    stream = read_pipe(0, maximum=MIB+65536, timeout=120)
    require(len(stream) >= 4)
    size = int.from_bytes(stream[:4], 'big'); require(0 < size <= 65536 and len(stream) >= 4+size)
    control, opaque = object_json(stream[4:4+size]), stream[4+size:]
    require(set(control) == {'schema_version', 'phase', 'source_sha', 'service', 'service_config_sha256',
                             'bundle_inventory_sha256', 'host_approval_sha256'})
    require(control['schema_version'] == 1 and control['phase'] == phase and control['source_sha'] == source)
    service = control['service']
    if phase == 'private': require(service in SERVICES and opaque and len(opaque) <= MIB)
    else: require(service is None and not opaque)
    p = _sibling('host_provision')
    with p.Pins() as pins:
        config = object_json(pins.read('/etc/autodata/host.json'))
        require(config.get('environment') == 'staging')
        rt = _sibling('runtime-check')
        require(rt.validate_config(config) == control['service_config_sha256'])
        inventory_raw = pins.read(BUNDLE+'/inventory.json', mode=0o444)
        _bound(inventory_raw, control['bundle_inventory_sha256'])
        entries = p.validate_inventory(BUNDLE, object_json(inventory_raw), source, pins)
        staged = phase in ('provision-check', 'provision')
        if not staged:
            for item in entries:
                _bound(pins.read('/'+item['path'], mode=item['mode']), item['sha256'])
        if phase in HOST_APPROVALS:
            raw = pins.read(HOST_APPROVALS[phase]); _bound(raw, control['host_approval_sha256'])
            approval = object_json(raw)
            if phase in ('provision-check', 'provision', 'images', 'database'):
                p.validate_approval(approval, source, 'provision' if staged else phase)
            elif phase == 'install': _sibling('host_install').validate_approval(approval, source, control['service_config_sha256'])
            else: _sibling('private_material').validate_approval(approval, source, service, control['service_config_sha256'], datetime.now(timezone.utc))
        else: require(control['host_approval_sha256'] is None)
        helper_bin = BUNDLE+'/opt/autodata/bin' if staged else BIN
        commands = {'provision-check': [helper_bin+'/host_provision.py', 'check', source],
            'provision': [helper_bin+'/host_provision.py', 'apply', source],
            'install': [BIN+'/deploy.sh', 'install', source],
            'images': [BIN+'/host_prepare_release.py', 'images', source],
            'database': [BIN+'/host_prepare_release.py', 'database', source],
            'private': [BIN+'/private_material.py', 'install', source, service or ''],
            'start': [BIN+'/deploy.sh', 'start', source], 'check': [BIN+'/deploy.sh', 'check', source]}
        command = commands[phase]
        if command[0].endswith('.py'): command = ['/usr/bin/python3', '-I']+command
        pins.recheck()
        output = run_process(command, input_data=opaque if phase == 'private' else None,
            timeout=phase_timeout(phase, workstation=False))
        result = object_json(output)
        # Existing helper owns its locking, journal and checks. The dispatcher
        # cannot convert a failing or malformed helper response into success.
        validate_receipt(phase, result, source, control['service_config_sha256'], service)
        pins.recheck()
        return result


def entry(argv):
    # Internal receiver/dispatcher are callable only from accepted host paths,
    # never alternative operator flags or caller-chosen script destinations.
    installed = str(Path(__file__).absolute()) in (BIN+'/staging_deploy.py', BUNDLE+'/opt/autodata/bin/staging_deploy.py')
    if argv and argv[0] in ('--receive', '--host-phase'):
        if not installed: return 2, {'status': 'failed', 'failure_code': 'invalid_input'}
        try:
            if len(argv) == 2 and argv[0] == '--receive': return 0, receive(argv[1])
            if len(argv) == 3 and argv[0] == '--host-phase': return 0, host_phase(argv[1], argv[2])
            raise Rejected()
        except Rejected: return 2, {'status': 'failed', 'failure_code': 'invalid_input'}
        except Exception: return 6, {'status': 'incomplete', 'failure_code': 'owner_readback_required'}
    return main(argv)


if __name__ == '__main__':
    code, result = entry(sys.argv[1:])
    sys.stdout.write(canonical(result).decode()+'\n')
    raise SystemExit(code)
