#!/usr/bin/env python3
"""Offline Workshop operation definitions against the reviewed host v1 contract.

No subprocess, network, credential discovery or live adapter exists here. The CLI
always fails closed. evaluate_backup consumes an explicitly supplied fake CLI
transcript; its passed receipt is a simulated definition result, never evidence
of an actual backup. evaluate_published_release only compares supplied fake
metadata and bytes; consistency cannot authenticate provenance or authorize
deployment. verify_release_archive checks supplied synthetic ZIP bytes only;
archive consistency cannot authenticate publication or authorize execution.
Provider pins, bootstrap, IAM and execution remain gated.
"""
import copy
import binascii
import stat
import struct
import zlib
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


def evaluate_published_release(manifest, config, binding, policy, claims, fake_cli, *, rollback_manifest=None):
    """Compare a supplied read-only fake transcript with independently bound inputs.

    There is no executable argv or live adapter. Metadata/bytes are untrusted
    simulation inputs, not GitHub/registry authentication or signed provenance.
    Budgets describe a future adapter; this callback has no cancellation claim.
    Even a consistent transcript never authorizes publishing or deployment.
    """
    rt.validate_manifest(manifest, config, rollback_manifest)
    validate_identity('publish', policy, claims, config['environment'])
    rt.exact_object(binding, ('published_run_id', 'artifact_id', 'artifact_digest', 'manifest_sha256'))
    for field in ('published_run_id', 'artifact_id'):
        rt.match(binding[field], r'[1-9][0-9]{0,19}')
    rt.match(binding['artifact_digest'], r'sha256:[0-9a-f]{64}')
    require(binding['manifest_sha256'] == rt.sha256(manifest))
    result = _external_receipt('publish', manifest['source_sha'], 'failed', 'operation_failed')
    result.update(operation='cloud-ops.py publish-transcript', simulation=True,
                  deployment_authorized=False, consistent_binding=None)
    # Fixed read-only observation names; no cloud executable or shell is chosen.
    def observe(name):
        limits = {'run': (30, MAX_RECEIPT), 'artifact': (30, MAX_RECEIPT),
                  'manifest': (300, rt.MAX_JSON_BYTES), 'images': (300, MAX_RECEIPT)}
        seconds, maximum = limits[name]
        value = fake_cli({'name': name, 'argv': [], 'timeout_seconds': seconds,
                          'max_output_bytes': maximum})
        if name == 'manifest':
            require(type(value) is bytes and 0 < len(value) <= maximum)
        else:
            require(len(rt.canonical_bytes(value)) <= maximum)
        return value
    try:
        run = observe('run')
        rt.exact_object(run, ('id', 'repository', 'source_sha', 'workflow_ref', 'event', 'status', 'conclusion'))
        require(run['id'] == binding['published_run_id'])
        require(run['repository'] == policy['repository'])
        require(run['source_sha'] == manifest['source_sha'])
        require(run['workflow_ref'] == policy['workflow_ref'])
        require(run['event'] == 'workflow_dispatch' and run['status'] == 'completed' and run['conclusion'] == 'success')
        artifact = observe('artifact')
        rt.exact_object(artifact, ('id', 'run_id', 'name', 'expired', 'digest', 'bytes'))
        require(artifact['id'] == binding['artifact_id'] and artifact['run_id'] == binding['published_run_id'])
        require(artifact['name'] == 'workshop-release-' + manifest['source_sha'])
        require(artifact['expired'] is False and artifact['digest'] == binding['artifact_digest'])
        require(type(artifact['bytes']) is int and 0 < artifact['bytes'] <= rt.MAX_JSON_BYTES)
        payload = observe('manifest')
        require(len(payload) == artifact['bytes'])
        require('sha256:' + hashlib.sha256(payload).hexdigest() == binding['artifact_digest'])
        decoded = rt.strict_json(payload)
        # Bind both raw artifact bytes and the type-strict canonical manifest.
        # Python equality alone would accept JSON true as integer 1.
        require(rt.sha256(decoded) == binding['manifest_sha256'])
        require(rt.canonical_bytes(decoded) == rt.canonical_bytes(manifest))
        observations = observe('images')
        rt.exact_object(observations, manifest['images'])
        for role, image in manifest['images'].items():
            expected = dict(image, platform=manifest['platform'])
            rt.exact_object(observations[role], expected)
            require(rt.canonical_bytes(observations[role]) == rt.canonical_bytes(expected))
        result.update(status='transcript_consistent', failure_code=None,
                      checks={'manifest': True, 'cached_images': True},
                      consistent_binding=copy.deepcopy(binding))
    except Exception as error:
        timed_out = isinstance(error, TimeoutError)
        result.update(status='timed_out' if timed_out else 'failed',
                      failure_code='operation_timed_out' if timed_out else 'operation_failed')
    result['finished_at'] = rt._timestamp()
    require(len(rt.canonical_bytes(result)) <= MAX_RECEIPT)
    return result


_RELEASE_MEMBERS = (b'release.json', b'images.json')
_MAX_RELEASE_ARCHIVE = 8388608


def _release_zip_members(data):
    """Parse the reviewed ZIP32 subset; never search signatures or extract files."""
    def unpack(fmt, offset, end):
        size = struct.calcsize(fmt)
        require(0 <= offset <= end <= len(data) and size <= end - offset)
        return struct.unpack_from(fmt, data, offset), offset + size

    end = len(data) - 22
    eocd, _ = unpack('<4s4H2IH', end, len(data))
    signature, disk, central_disk, disk_count, count, central_size, central_offset, comment = eocd
    require(signature == b'PK\x05\x06' and disk == central_disk == comment == 0)
    require(disk_count == count == 2 and central_size != 0xffffffff and central_offset != 0xffffffff)
    require(central_offset + central_size == end)
    records = []
    position = central_offset
    total_size = 0
    for name in _RELEASE_MEMBERS:
        fields, position = unpack('<4s6H3I5H2I', position, end)
        (signature, creator, version, flags, method, clock, date, crc, packed_size, size,
         name_size, extra_size, comment_size, disk_start, internal, external, offset) = fields
        require(signature == b'PK\x01\x02' and name_size == len(name))
        require(position + name_size <= end and data[position:position + name_size] == name)
        position += name_size
        require(extra_size == comment_size == disk_start == internal == 0)
        require(creator >> 8 in (0, 3) and not external & 0x18)
        require(stat.S_IFMT(external >> 16) in (0, stat.S_IFREG))
        require(flags in (0, 8, 2048, 2056) and method in (0, 8))
        require(version in (10, 20) and (version == 20 or (method == 0 and not flags & 8)))
        require(0 < size <= rt.MAX_JSON_BYTES and 0 < packed_size <= rt.MAX_JSON_BYTES)
        require(size <= 100 * packed_size and (method != 0 or size == packed_size))
        require(offset != 0xffffffff)
        total_size += size
        require(total_size <= 2 * rt.MAX_JSON_BYTES)
        records.append((name, offset, version, flags, method, clock, date, crc, packed_size, size))
    require(position == end)

    # Validate ALL local records/descriptors before decoding any member. Central
    # offsets supply boundaries; neither embedded signatures nor CRCs do so.
    spans = []
    require(records[0][1] == 0)
    for i, record in enumerate(records):
        name, offset, version, flags, method, clock, date, crc, packed_size, size = record
        boundary = records[i + 1][1] if i + 1 < len(records) else central_offset
        fields, position = unpack('<4s5H3I2H', offset, boundary)
        signature, lv, lf, lm, lt, ld, lc, lp, ls, name_size, extra_size = fields
        require(signature == b'PK\x03\x04' and (lv, lf, lm, lt, ld) == (version, flags, method, clock, date))
        require(name_size == len(name) and extra_size == 0)
        require(position + name_size <= boundary and data[position:position + name_size] == name)
        position += name_size
        require(lp != 0xffffffff and ls != 0xffffffff)
        require((lc, lp, ls) == (crc, packed_size, size) or
                (flags & 8 and (lc, lp, ls) == (0, 0, 0)))
        data_end = position + packed_size
        require(data_end <= boundary)
        if flags & 8:
            length = boundary - data_end
            require(length in (12, 16))
            if length == 16:
                require(data[data_end:data_end + 4] == b'PK\x07\x08')
                data_end += 4
            descriptor, descriptor_end = unpack('<3I', data_end, boundary)
            require(descriptor == (crc, packed_size, size) and descriptor_end == boundary)
        else:
            require(data_end == boundary)
        spans.append((name.decode('ascii'), position, packed_size, size, method, crc))
    return spans


def _inflate_release_member(packed, size):
    """Bound every raw-DEFLATE call and retained output; flush is unnecessary."""
    decoder = zlib.decompressobj(-15)
    output = bytearray()
    for offset in range(0, len(packed), 65536):
        pending = packed[offset:offset + 65536]
        while pending:
            before = len(pending)
            chunk = decoder.decompress(pending, size - len(output) + 1)
            require(len(chunk) <= size - len(output))
            output.extend(chunk)
            pending = decoder.unconsumed_tail
            require(len(pending) < before or len(chunk) > 0)
            require(not decoder.unused_data)
        if decoder.eof:
            require(offset + 65536 >= len(packed))
    require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(output) == size)
    return bytes(output)


def verify_release_archive(archive_bytes: bytes, manifest: dict, *,
                           expected_archive_sha256: str,
                           expected_member_sha256: dict[str, str]) -> dict:
    """Verify supplied synthetic bytes, never publication, identity or deployment.

    Caller first validates manifest/config/rollback via rt.validate_manifest.
    This pure API has no transport, extraction, callback or CLI execution path.
    Archive/raw-member digests are independent approvals; canonical manifest
    comparison does not replace either. Actual publisher compatibility is gated.
    """
    try:
        require(type(archive_bytes) is bytes and 0 < len(archive_bytes) <= _MAX_RELEASE_ARCHIVE)
        rt.match(expected_archive_sha256, r'[0-9a-f]{64}')
        rt.exact_object(expected_member_sha256, ('release.json', 'images.json'))
        for digest in expected_member_sha256.values():
            rt.match(digest, r'[0-9a-f]{64}')
        require(hashlib.sha256(archive_bytes).hexdigest() == expected_archive_sha256)
        spans = _release_zip_members(archive_bytes)
        members, hashes, sizes = {}, {}, {}
        for name, start, packed_size, size, method, crc in spans:
            packed = archive_bytes[start:start + packed_size]
            member = packed if method == 0 else _inflate_release_member(packed, size)
            require(len(member) == size and binascii.crc32(member) == crc)
            digest = hashlib.sha256(member).hexdigest()
            require(digest == expected_member_sha256[name])
            hashes[name], sizes[name] = digest, len(member)
            members[name] = member
        require(type(manifest) is dict)
        decoded = rt.strict_json(members['release.json'])
        require(rt.canonical_bytes(decoded) == rt.canonical_bytes(manifest))
        manifest_digest = rt.sha256(manifest)
        require(rt.sha256(decoded) == manifest_digest)
        observations = rt.strict_json(members['images.json'])
        rt.exact_object(observations, manifest['images'])
        for role, image in manifest['images'].items():
            expected = dict(image, platform=manifest['platform'])
            rt.exact_object(observations[role], expected)
            require(rt.canonical_bytes(observations[role]) == rt.canonical_bytes(expected))
        return {'schema_version': 1, 'status': 'archive_consistent', 'simulation': True,
                'provenance_authenticated': False, 'deployment_authorized': False,
                'archive_sha256': expected_archive_sha256, 'member_sha256': hashes,
                'member_bytes': sizes, 'manifest_sha256': manifest_digest,
                'checks': {'archive': True, 'members': True, 'manifest': True, 'image_observations': True}}
    except (ValueError, TypeError, KeyError, IndexError, struct.error, zlib.error, RecursionError, OverflowError):
        raise ContractError('invalid release archive') from None


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
        # Python object equality collapses JSON bool/int/float distinctions.
        # Canonical encodings bind nested scalar types as well as field values.
        require(rt.canonical_bytes(rt.strict_json(members['backup.json'])) == rt.canonical_bytes(status))
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
