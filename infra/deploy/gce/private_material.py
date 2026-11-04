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


def read_stream(fd, deadline):
    raise Denied()


def install_cli(source, service):
    return finish(receipt(source, service), 3)


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
