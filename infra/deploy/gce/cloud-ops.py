#!/usr/bin/env python3
"""Offline Workshop operation definitions against the reviewed host v1 contract.

No subprocess, network, credential discovery or live adapter exists here. The CLI
always fails closed. evaluate_backup consumes an explicitly supplied fake CLI
transcript; its passed receipt is a simulated definition result, never evidence
of an actual backup. Provider pins, bootstrap, IAM and execution remain gated.
"""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
from pathlib import Path
import sys
import tarfile

_SPEC = importlib.util.spec_from_file_location('workshop_runtime_v1', Path(__file__).with_name('runtime-check.py'))
rt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rt)
ContractError = rt.ContractError
require = rt.require
MAX_RECEIPT = 65536
MAX_EXPORT = 1073741824
MAX_LEASE_SECONDS = 1800
RESUME_RESERVE_SECONDS = 300
WORKFLOWS = {'publish': 'release-workshop.yml', 'deploy': 'release-workshop.yml',
             'backup': 'backup-workshop.yml', 'monitor': 'monitor-workshop.yml'}
IDENTITY_FIELDS = ('repository', 'repository_id', 'repository_owner_id', 'environment', 'ref', 'workflow_ref')
COMMON_RECEIPT = ('schema_version', 'operation', 'run_id', 'source_sha', 'status',
                  'started_at', 'finished_at', 'checks', 'failure_code')
BACKUP_FIELDS = ('state', 'lease_expires_at', 'dump_sha256', 'dump_bytes', 'manifest_sha256', 'disk_uuid')


def read_input(path):
    """The same no-follow, root-owned 0600 descriptor contract as A."""
    return rt.read_private_json(path)


def timestamp(value):
    rt.match(value, r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError:
        raise ContractError('invalid timestamp') from None


def validate_identity(operation, policy, claims, environment):
    """Validate an explicit reviewed trust tuple; there are no owner/ref defaults.

    Policy is a separate proposed WIF binding, never a release manifest field.
    Equality checks unverified claims for offline tests; this does not authenticate
    an OIDC token or establish that GitHub protects the named environment.
    Restore has no reviewed workflow and therefore cannot acquire this authority.
    """
    require(operation in WORKFLOWS and environment in ('staging', 'production'))
    rt.exact_object(policy, IDENTITY_FIELDS)
    rt.exact_object(claims, IDENTITY_FIELDS)
    rt.match(policy['repository'], r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+')
    for field in ('repository_id', 'repository_owner_id'):
        rt.match(policy[field], r'[1-9][0-9]{0,19}')
    require(policy['environment'] == environment)
    rt.match(policy['ref'], r'refs/(?:heads|tags)/[A-Za-z0-9][A-Za-z0-9_./-]{0,199}')
    require(not any(part in ('', '.', '..') for part in policy['ref'].split('/')))
    require(policy['workflow_ref'] == policy['repository'] + '/.github/workflows/' + WORKFLOWS[operation] + '@' + policy['ref'])
    require(claims == policy)
    return True


def parse_args(argv):
    require(type(argv) in (list, tuple) and len(argv) == 2 and all(type(x) is str for x in argv))
    operation, identifier = argv
    require(operation in ('publish', 'deploy', 'backup', 'monitor', 'restore'))
    if operation in ('backup', 'restore'): rt._uuid(identifier)
    else: rt.match(identifier, rt.SHA_PATTERN)
    return operation, identifier


def _external_receipt(operation, identifier, status, failure):
    now = rt._timestamp()
    return {'schema_version': 1, 'operation': 'cloud-ops.py ' + operation,
            'run_id': identifier if operation in ('backup', 'restore') else None,
            'source_sha': identifier if operation in ('publish', 'deploy', 'monitor') else None,
            'status': status, 'started_at': now, 'finished_at': now,
            'checks': {}, 'failure_code': failure}


def cli(argv):
    try:
        operation, identifier = parse_args(argv)
    except ContractError:
        return 2, _external_receipt('backup', None, 'failed', 'invalid_input')
    # Intentionally no apply/execute flag, ambient config, gcloud or SSH fallback.
    return 3, _external_receipt(operation, identifier, 'failed', 'missing_dependency')


def validate_metrics(value, source_sha):
    rt.exact_object(value, ('schema_version', 'source_sha', 'observed_at', 'metrics'))
    require(type(value['schema_version']) is int and value['schema_version'] == 1)
    require(value['source_sha'] == source_sha)
    timestamp(value['observed_at'])
    rt.metrics_receipt(source_sha, value['metrics'])
    require(len(rt.canonical_bytes(value)) <= MAX_RECEIPT)
    return copy.deepcopy(value)


def read_stream(stream, limit=MAX_EXPORT):
    require(type(limit) is int and 0 < limit <= MAX_EXPORT)
    result = bytearray()
    while len(result) <= limit:
        chunk = stream.read(min(65536, limit + 1 - len(result)))
        require(type(chunk) is bytes)
        if not chunk: break
        result.extend(chunk)
    require(len(result) <= limit)
    return bytes(result)


def verify_export(data, manifest, status):
    """Inspect raw regular ustar members without extracting paths or extensions.

    Parsing raw headers also rejects duplicate names hidden by PAX/GNU extension
    handling. Bounds are intentionally conservative for this offline definition.
    """
    require(type(data) is bytes and 1024 <= len(data) <= MAX_EXPORT and len(data) % 512 == 0)
    expected = {'postgres.dump', 'release.json', 'backup.json'}
    members, offset = {}, 0
    try:
        while offset + 512 <= len(data):
            header = data[offset:offset + 512]
            if header == b'\0' * 512:
                require(len(data) - offset >= 1024 and not any(data[offset:]))
                break
            member = tarfile.TarInfo.frombuf(header, 'utf-8', 'strict')
            require(member.name in expected and member.name not in members)
            require(member.type in (tarfile.REGTYPE, tarfile.AREGTYPE) and not member.linkname)
            require(not member.pax_headers and member.size >= 0)
            limit = status['dump_bytes'] if member.name == 'postgres.dump' else rt.MAX_JSON_BYTES
            require(type(limit) is int and 0 < member.size <= limit)
            start = offset + 512
            end = start + member.size
            offset = start + ((member.size + 511) // 512) * 512
            require(offset <= len(data))
            members[member.name] = data[start:end]
        else:
            raise ContractError('missing tar terminator')
        require(set(members) == expected)
        require(len(members['postgres.dump']) == status['dump_bytes'])
        require(hashlib.sha256(members['postgres.dump']).hexdigest() == status['dump_sha256'])
        require(hashlib.sha256(members['release.json']).hexdigest() == status['manifest_sha256'])
        require(rt.strict_json(members['release.json']) == manifest)
        require(rt.strict_json(members['backup.json']) == status)
        return members
    except (ValueError, UnicodeError, tarfile.TarError, KeyError, OverflowError):
        raise ContractError('invalid backup export') from None


def _host(value, verb, state, manifest, config, run_id):
    extra = ('writers_resumed', 'stateful_resumed') if state == 'resumed' else ()
    rt.exact_object(value, COMMON_RECEIPT + BACKUP_FIELDS + extra)
    require(len(rt.canonical_bytes(value)) <= MAX_RECEIPT)
    require(type(value['schema_version']) is int and value['schema_version'] == 1)
    require(value['operation'] == 'backup-host.sh ' + verb and value['run_id'] == run_id)
    require(value['source_sha'] == manifest['source_sha'] and value['state'] == state)
    require(value['status'] == 'passed' and value['failure_code'] is None)
    require(type(value['checks']) is dict and set(value['checks']) <= rt.CHECK_NAMES)
    require(all(type(item) is bool and item for item in value['checks'].values()))
    require(timestamp(value['started_at']) <= timestamp(value['finished_at']))
    require(value['disk_uuid'] == config['resources']['data_disk_filesystem_uuid'])
    require(value['manifest_sha256'] == rt.sha256(manifest))
    rt.match(value['dump_sha256'], rt.HASH_PATTERN)
    require(type(value['dump_bytes']) is int and 0 < value['dump_bytes'] < MAX_EXPORT)
    timestamp(value['lease_expires_at'])
    if state == 'resumed':
        require(value['writers_resumed'] is True and value['stateful_resumed'] is True)
        require(value['checks'].get('services') is True and value['checks'].get('no_work') is True)
    return value


def _snapshot(value, config, run_id, begin, now):
    rt.exact_object(value, ('self_link', 'operation', 'source_disk', 'status', 'cutoff_at', 'completed_at'))
    resources = config['resources']
    prefix = 'https://www.googleapis.com/compute/v1/projects/'
    require(value['self_link'] == prefix + resources['backup_project_id'] + '/global/snapshots/autodata-' + run_id)
    rt.match(value['operation'], prefix.replace('.', r'\.') + resources['backup_project_id'] + r'/global/operations/[a-zA-Z0-9-]{1,100}')
    require(value['source_disk'] == prefix + resources['host_project_id'] + '/zones/' + resources['zone'] + '/disks/' + resources['data_disk_name'])
    require(value['status'] == 'READY')
    require(now <= timestamp(begin['finished_at']) <= timestamp(value['cutoff_at']) <= timestamp(value['completed_at']) < timestamp(begin['lease_expires_at']))
    return value


def _step(name, run_id):
    # These are finite offline definitions, not subprocess wrappers. Cloud steps
    # have no executable argv until a later reviewed/pinned adapter is approved.
    helpers = {'begin': 'begin', 'resume': 'resume', 'status': 'status', 'export': 'export'}
    deadlines = {'begin': 600, 'snapshot': 600, 'resume': 300, 'status': 30,
                 'export': 300, 'upload': 600, 'cleanup': 60}
    argv = [rt.HELPER_ROOT + '/backup-host.sh', helpers[name], run_id] if name in helpers else []
    if argv: rt.parse_helper_args('backup-host.sh', argv[1:])
    return {'name': name, 'argv': argv, 'timeout_seconds': deadlines[name],
            'max_output_bytes': MAX_EXPORT if name == 'export' else MAX_RECEIPT}


def evaluate_backup(manifest, config, run_id, policy, claims, fake_cli, *, now, rollback_manifest=None):
    """Evaluate a fake transcript only; never execute planned provider commands.

    The fake adapter receives a finite step/argv/output budget and may raise
    TimeoutError or EOFError. Real subprocess cancellation/kill and IAP streaming
    require a later authorized implementation; this function certifies neither.
    A resume attempt and cleanup remain mandatory after any attempted begin.
    """
    rt.validate_manifest(manifest, config, rollback_manifest)
    rt._uuid(run_id)
    validate_identity('backup', policy, claims, config['environment'])
    require(type(now) is datetime and now.tzinfo is not None and now.utcoffset().total_seconds() == 0)
    result = _external_receipt('backup', run_id, 'failed', 'operation_failed')
    result.update(source_sha=manifest['source_sha'], simulation=True, last_verified_backup=None,
                  snapshot=None, objects=None, dump_sha256=None, dump_bytes=None,
                  manifest_sha256=rt.sha256(manifest), migrations=copy.deepcopy(manifest['migrations']),
                  resumed=False, cleanup=False, object_prefix='gs://' + config['resources']['backup_bucket'] + '/' + run_id + '/')
    begin, snapshot, members = None, None, None
    failure, resume_ok = None, False
    def call(name):
        value = fake_cli(_step(name, run_id))
        if name == 'export':
            require(type(value) is bytes and len(value) <= MAX_EXPORT)
        else:
            require(len(rt.canonical_bytes(value)) <= MAX_RECEIPT)
        return value
    try:
        begin = _host(call('begin'), 'begin', 'quiesced', manifest, config, run_id)
        lease_seconds = (timestamp(begin['lease_expires_at']) - now).total_seconds()
        require(RESUME_RESERVE_SECONDS < lease_seconds <= MAX_LEASE_SECONDS)
        require(timestamp(begin['finished_at']) >= now)
        snapshot = _snapshot(call('snapshot'), config, run_id, begin, now)
        require((timestamp(begin['lease_expires_at']) - timestamp(snapshot['completed_at'])).total_seconds() >= RESUME_RESERVE_SECONDS)
    except Exception as error:
        failure = 'operation_timed_out' if isinstance(error, TimeoutError) else 'operation_failed'
    finally:
        try:
            resumed = _host(call('resume'), 'resume', 'resumed', manifest, config, run_id)
            if begin is not None:
                require(all(resumed[key] == begin[key] for key in BACKUP_FIELDS if key != 'state'))
            if snapshot is not None:
                require(timestamp(snapshot['completed_at']) <= timestamp(resumed['started_at']) <=
                        timestamp(resumed['finished_at']) < timestamp(begin['lease_expires_at']))
            resume_ok = True
            result['resumed'] = True
        except Exception:
            failure = 'recovery_incomplete'
    try:
        if failure is None and resume_ok:
            status = _host(call('status'), 'status', 'resumed', manifest, config, run_id)
            require(all(status[key] == resumed[key] for key in BACKUP_FIELDS))
            members = verify_export(call('export'), manifest, status)
            uploaded = call('upload')
            rt.exact_object(uploaded, members)
            for name, data in members.items():
                item = uploaded[name]
                rt.exact_object(item, ('bucket', 'name', 'generation', 'sha256', 'bytes'))
                require(item['bucket'] == config['resources']['backup_bucket'])
                require(item['name'] == run_id + '/' + name)
                rt.match(item['generation'], r'[1-9][0-9]{0,29}')
                require(item['sha256'] == hashlib.sha256(data).hexdigest())
                require(type(item['bytes']) is int and item['bytes'] == len(data))
            result.update(snapshot=copy.deepcopy(snapshot), objects=copy.deepcopy(uploaded),
                          dump_sha256=status['dump_sha256'], dump_bytes=status['dump_bytes'],
                          checks={'manifest': True, 'disk_uuid': True, 'services': True, 'no_work': True})
    except Exception as error:
        failure = 'operation_timed_out' if isinstance(error, TimeoutError) else 'operation_failed'
    finally:
        try:
            require(call('cleanup') is True)
            result['cleanup'] = True
        except Exception:
            failure = 'recovery_incomplete'
    if failure is None:
        result.update(status='passed', failure_code=None, last_verified_backup=snapshot['completed_at'])
    else:
        result.update(status='incomplete' if failure == 'recovery_incomplete' else 'timed_out' if failure == 'operation_timed_out' else 'failed', failure_code=failure)
    result['finished_at'] = rt._timestamp()
    require(len(rt.canonical_bytes(result)) <= MAX_RECEIPT)
    return result


if __name__ == '__main__':
    code, receipt = cli(sys.argv[1:])
    sys.stdout.buffer.write(rt.canonical_bytes(receipt) + b'\n')
    raise SystemExit(code)
