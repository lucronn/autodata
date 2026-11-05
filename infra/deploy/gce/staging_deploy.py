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
                 'known_hosts_sha256 tools').split()


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


def validate_config(value, source):
    require(matches(source, SHA) and type(value) is dict and set(value) == set(CONFIG_FIELDS))
    require(type(value['schema_version']) is int and value['schema_version'] == 1)
    require(value['environment'] == 'staging' and value['source_sha'] == source)
    for name in ('project_id', 'region', 'zone', 'instance_name'): require(matches(value[name], NAME))
    require(value['zone'].startswith(value['region'] + '-'))
    require(type(value['maximum_monthly_budget_usd']) in (int, float) and 0 < value['maximum_monthly_budget_usd'] < 1e9)
    for name in ('instance_id', 'repository_id', 'repository_owner_id'): require(matches(value[name], r'[1-9][0-9]{0,19}'))
    require(matches(value['os_login_user'], r'[a-z_][a-z0-9_-]{0,63}'))
    require(value['protected_environment'] == 'workshop-staging-publish')
    require(matches(value['wif_provider'], r'projects/[1-9][0-9]*/locations/global/workloadIdentityPools/[a-z0-9-]+/providers/[a-z0-9-]+'))
    require(matches(value['service_account'], r'[a-z][a-z0-9-]+@' + re.escape(value['project_id']) + r'\.iam\.gserviceaccount\.com'))
    require(matches(value['registry'], re.escape(value['region']) + r'-docker\.pkg\.dev/' + re.escape(value['project_id']) + r'/[a-z0-9-]+'))
    require(matches(value['toolchain_image'], r'[a-z0-9./-]+@sha256:' + HASH))
    for name in ('service_config_sha256', 'bundle_inventory_sha256', 'known_hosts_sha256'): require(matches(value[name], HASH))
    require(type(value['tools']) is dict and set(value['tools']) == set(TOOLS))
    require(all(matches(pin, HASH) for pin in value['tools'].values()))
    try:
        origin = urlsplit(value['staging_origin'])
        require(origin.scheme == 'https' and origin.username is None and origin.password is None and origin.port is None)
        require(origin.path == '' and not origin.query and not origin.fragment)
        require(matches(origin.hostname, r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?'))
        require(origin.hostname not in ('cars.tk', 'www.cars.tk'))
    except (ValueError, TypeError, AttributeError): raise Rejected() from None


def run_process(argv, *, input_data=None, timeout=120, maximum=65536):
    """Finite argv, bounded combined output, process-group deadline and cleanup.

    Child stderr is intentionally never returned or persisted, including errors.
    The supplied environment has no ambient proxy, token or SSH agent discovery.
    """
    require(type(argv) is list and argv and all(type(arg) is str and '\x00' not in arg for arg in argv))
    require(argv[0].startswith('/') and 0 < timeout <= 1800 and 0 < maximum <= 70*MIB)
    require(input_data is None or type(input_data) is bytes and len(input_data) <= 70*MIB)
    end = time.monotonic() + timeout
    try:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='/', env=ENV, start_new_session=True)
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
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None: pipe.close()
        process.wait(timeout=2)


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
    return [TOOLS['gcloud'], '--quiet', 'compute', 'ssh', config['os_login_user']+'@'+config['instance_name'],
            '--project='+config['project_id'], '--zone='+config['zone'], '--tunnel-through-iap',
            '--ssh-key-expire-after=5m', '--strict-host-key-checking=yes',
            '--ssh-flag=-F/dev/null', '--ssh-flag=-oBatchMode=yes', '--ssh-flag=-oForwardAgent=no',
            '--ssh-flag=-oClearAllForwardings=yes', '--ssh-flag=-oStrictHostKeyChecking=yes',
            '--ssh-flag=-oUserKnownHostsFile='+ROOT+'/known_hosts', '--ssh-flag=-oGlobalKnownHostsFile=/dev/null',
            '--ssh-flag=-oConnectTimeout=20', '--ssh-flag=-oServerAliveInterval=15', '--ssh-flag=-oServerAliveCountMax=2',
            '--command='+remote]


def validate_receipt(phase, value, source, config_hash, service=None):
    require(type(value) is dict and value.get('source_sha') == source)
    if phase == 'provision-check':
        require(set(value) == {'status', 'source_sha', 'production_ready'} and value['status'] == 'checked' and value['production_ready'] is False)
        return
    require(type(value.get('schema_version')) is int and value['schema_version'] == 1 and value.get('status') == 'passed')
    operations = {'provision': ('prepare-new-empty-staging-host',), 'images': ('cache-accepted-staging-images',),
                  'database': ('initialize-fresh-staging-database', 'resume-created-staging-database'),
                  'install': ('deploy.sh install',), 'private': ('install-private-material',),
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


if __name__ == '__main__':
    code, result = main(sys.argv[1:])
    sys.stdout.write(canonical(result).decode()+'\n')
    raise SystemExit(code)
