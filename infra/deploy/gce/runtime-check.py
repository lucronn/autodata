#!/usr/bin/env python3
"""Workshop hosting v1 passive contract.

This first milestone validates and renders definitions only. The installed CLI
fails closed: no host, endpoint, daemon, secret, or runtime observation is made.
Imports are the shared interface for later, separately authorized helpers.
"""
import copy
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from urllib.parse import urlsplit
import uuid

MAX_JSON_BYTES = 1048576
HOST_CONFIG = '/etc/autodata/host.json'
RELEASE_ROOT = '/opt/autodata/releases'
CURRENT_RELEASE = '/opt/autodata/current'
HELPER_ROOT = '/opt/autodata/bin'
DATA_ROOT = '/var/lib/autodata'
SECRET_ROOT = '/run/autodata'
NORMAL_SERVICES = ('caddy', 'api', 'ingestion-http', 'article-worker', 'payment-reconciler', 'postgres', 'nats', 'minio')
IMAGE_ROLES = ('api', 'ingestion', 'migration', 'caddy', 'postgres', 'nats', 'minio')
SHA_PATTERN = r'[0-9a-f]{40}'
HASH_PATTERN = r'[0-9a-f]{64}'
TOPOLOGY = {
    'edge': {'bridge': 'br-ad-edge', 'subnet': '172.30.10.0/24', 'internal': False,
             'addresses': {'api': '172.30.10.10', 'caddy': '172.30.10.20'}, 'enable_ipv6': False},
    'backend': {'bridge': 'br-ad-back', 'subnet': '172.30.20.0/24', 'internal': True,
                'addresses': {'api': '172.30.20.10', 'ingestion-http': '172.30.20.11',
                              'article-worker': '172.30.20.12', 'payment-reconciler': '172.30.20.13',
                              'postgres': '172.30.20.20', 'nats': '172.30.20.30', 'minio': '172.30.20.40',
                              'migration': '172.30.20.50', 'bootstrap': '172.30.20.51', 'metrics-probe': '172.30.20.52'},
                'enable_ipv6': False},
    'workers-egress': {'bridge': 'br-ad-work', 'subnet': '172.30.30.0/24', 'internal': False,
                      'addresses': {'ingestion-http': '172.30.30.11', 'article-worker': '172.30.30.12',
                                    'payment-reconciler': '172.30.30.13'}, 'enable_ipv6': False}}
COMMANDS = {
    'api': ['/usr/local/bin/autodata-api'],
    'ingestion-http': ['python', '-m', 'autodata_ingestion.http_service'],
    'article-worker': ['python', '-c', 'from autodata_ingestion.worker import article_worker_main; raise SystemExit(article_worker_main())'],
    'payment-reconciler': ['python', '/app/scripts/reconcile_payments.py', '--poll-seconds', '15', '--batch-size', '50'],
    'migration': ['sh', '/release/scripts/dev/migrate_sql.sh', '--migrations-dir', '/release/db/migrations'],
    'metrics-probe': ['python', '/app/scripts/operational_metrics.py', '--address', 'postgres:5432']}
# These are delivered file names, not Compose environment entries. Server config
# files are generated privately from the named minio/nats inputs in a later gate.
DB_SECRET = ('AUTODATA_POSTGRES_PASSWORD',)
S3_SECRETS = ('AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY')
BANK_SECRETS = ('BANKONE_API_TOKEN', 'BANKTWO_API_TOKEN')
STRIPE_SECRETS = ('AUTODATA_STRIPE_SECRET_KEY', 'AUTODATA_STRIPE_WEBHOOK_SECRET')
INTERNAL_SECRET = ('AUTODATA_INGESTION_INTERNAL_TOKEN',)
SECRET_NAMES = {
    'api': DB_SECRET + S3_SECRETS + INTERNAL_SECRET + ('AUTODATA_IMAGE_URL_KEY',),
    'ingestion-http': DB_SECRET + S3_SECRETS + INTERNAL_SECRET + STRIPE_SECRETS + BANK_SECRETS,
    'article-worker': DB_SECRET + S3_SECRETS + BANK_SECRETS + ('INCEPTION_API_KEY',),
    'payment-reconciler': DB_SECRET + INTERNAL_SECRET + STRIPE_SECRETS,
    'postgres': ('POSTGRES_PASSWORD',),
    'nats': ('NATS_METRICS_USER', 'NATS_METRICS_PASSWORD'),
    'minio': ('S3_WORKER_ACCESS_KEY', 'S3_WORKER_SECRET_KEY', 'S3_API_ACCESS_KEY', 'S3_API_SECRET_KEY'),
    'migration': ('PGPASSWORD',),
    'bootstrap': ('AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY'),
    'metrics-probe': DB_SECRET + ('NATS_METRICS_USER', 'NATS_METRICS_PASSWORD')}
# Missing observations are omitted; none of these names implies a measurement.
METRIC_UNITS = {
    'disk_free_bytes': 'By', 'service_restarts': '1', 'services_unavailable': '1',
    'postgres_connected': '1', 'nats_connected': '1', 's3_errors': '1',
    'article_oldest_lease_seconds': 's', 'index_oldest_lease_seconds': 's',
    'rewrite_oldest_lease_seconds': 's', 'retry_oldest_age_seconds': 's',
    'preparation_lag_seconds': 's', 'preparation_pending_count': '1',
    'reconciliation_lag_seconds': 's', 'reconciliation_pending_count': '1',
    'outbox_lag_seconds': 's', 'outbox_pending_count': '1',
    'last_verified_backup_timestamp': 's', 'last_restore_drill_timestamp': 's',
    'exporter_heartbeat_timestamp': 's', 'api_latency_seconds': 's', 'api_error_count': '1'}
CHECK_NAMES = frozenset(('manifest', 'config', 'migration_tree', 'schema', 'disk_uuid',
                        'metadata_guard', 'storage_guard', 'secrets', 'cached_images',
                        'services', 'postgres', 'nats', 's3', 'no_work', 'runtime_evidence'))
FAILURE_CODES = frozenset(('invalid_input', 'missing_dependency', 'guard_missing', 'operation_failed',
                           'operation_timed_out', 'recovery_incomplete'))
EXIT_STATUS = {0: 'passed', 2: 'failed', 3: 'failed', 4: 'failed', 5: 'timed_out', 6: 'incomplete'}


class ContractError(ValueError):
    """Deliberately contains no caller data or underlying exception details."""


def require(condition):
    if not condition:
        raise ContractError('invalid v1 contract')


def canonical_bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError):
        raise ContractError('invalid JSON') from None


def sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def strict_json(data):
    require(isinstance(data, bytes) and len(data) <= MAX_JSON_BYTES)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    def invalid(_):
        raise ContractError('nonfinite JSON')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
        canonical_bytes(value)  # catches overflow such as 1e999 and invalid Unicode
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError('invalid JSON') from None


def exact_object(value, fields):
    require(type(value) is dict and set(value) == set(fields))


def match(value, pattern):
    require(type(value) is str and re.fullmatch(pattern, value) is not None)


def _schema_validate(value, schema):
    """The small, explicit JSON Schema subset used by release.schema.json."""
    if 'const' in schema:
        require(type(value) is type(schema['const']) and value == schema['const'])
    if 'enum' in schema:
        require(value in schema['enum'])
    kind = schema.get('type')
    if isinstance(kind, list):
        require(kind == ['string', 'null'])
        if value is None: return
        kind = 'string'
    if kind == 'object':
        require(type(value) is dict)
        properties = schema['properties']
        require(schema['additionalProperties'] is False and set(value) <= set(properties))
        require(set(schema.get('required', ())) <= set(value))
        for key, item in value.items(): _schema_validate(item, properties[key])
    elif kind == 'array':
        require(type(value) is list and len(value) >= schema.get('minItems', 0))
        for item in value: _schema_validate(item, schema['items'])
    elif kind == 'string':
        require(type(value) is str and 0 < len(value) <= schema.get('maxLength', 4096))
        if 'pattern' in schema: match(value, schema['pattern'])
        require(not any(token in value for token in ('<', '>', '\n', '\r', '\x00', '${')))
    elif kind == 'integer':
        require(type(value) is int)
    else:
        require(kind is None)


def _https(value, origin=False):
    require(type(value) is str and len(value) <= 2048)
    try:
        parsed = urlsplit(value)
        require(parsed.scheme == 'https' and parsed.hostname is not None and parsed.port in (None, 443))
        require(not parsed.username and not parsed.password and not parsed.query and not parsed.fragment)
        match(parsed.hostname, r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}')
        require(parsed.hostname != 'localhost' and not parsed.hostname.endswith('.localhost'))
        try:
            ipaddress.ip_address(parsed.hostname)
        except ValueError:
            pass
        else:
            raise ContractError('IP endpoint not allowed')
        if origin: require(value == 'https://' + parsed.hostname)
        require(not any(token in value for token in ('<', '>', '${', '\\', '\n', '\r', '\x00', ' ')))
    except (ValueError, TypeError):
        raise ContractError('invalid HTTPS configuration') from None


def validate_config(config):
    exact_object(config, ('schema_version', 'environment', 'public_origin', 'firebase', 'resources', 'topology', 'commands', 'tuning'))
    require(type(config['schema_version']) is int and config['schema_version'] == 1)
    require(config['environment'] in ('production', 'staging'))
    _https(config['public_origin'], origin=True)
    require((config['public_origin'] == 'https://cars.tk') == (config['environment'] == 'production'))
    firebase = config['firebase']
    exact_object(firebase, ('project_id', 'web_api_key', 'web_app_id', 'auth_domain'))
    match(firebase['project_id'], r'[a-z][a-z0-9-]{4,28}[a-z0-9]')
    match(firebase['web_api_key'], r'[A-Za-z0-9_-]{8,200}')
    match(firebase['web_app_id'], r'1:[0-9]+:web:[A-Za-z0-9]+')
    match(firebase['auth_domain'], r'[a-z0-9][a-z0-9.-]*\.[a-z]{2,63}')
    resources = config['resources']
    exact_object(resources, ('host_project_id', 'backup_project_id', 'region', 'zone', 'instance_name',
                             'data_disk_name', 'data_disk_filesystem_uuid', 'static_ip_name',
                             'artifact_repository', 'backup_bucket', 'acme_email'))
    for key in ('host_project_id', 'backup_project_id'): match(resources[key], r'[a-z][a-z0-9-]{4,28}[a-z0-9]')
    for key in ('instance_name', 'data_disk_name', 'static_ip_name'): match(resources[key], r'[a-z][a-z0-9-]{0,61}[a-z0-9]')
    match(resources['region'], r'[a-z]+-[a-z]+[0-9]')
    require(resources['zone'] in [resources['region'] + '-' + suffix for suffix in ('a', 'b', 'c', 'd', 'e', 'f')])
    _uuid(resources['data_disk_filesystem_uuid'])
    match(resources['artifact_repository'], r'[a-z]+-[a-z]+[0-9]-docker\.pkg\.dev/[a-z][a-z0-9-]+/[a-z][a-z0-9-]+')
    require(resources['artifact_repository'].split('/')[1] == resources['host_project_id'])
    match(resources['backup_bucket'], r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]')
    match(resources['acme_email'], r'[A-Za-z0-9._+-]+@[a-z0-9.-]+\.[a-z]{2,63}')
    require(type(config['topology']) is dict and canonical_bytes(config['topology']) == canonical_bytes(TOPOLOGY))
    require(type(config['commands']) is dict and config['commands'] == COMMANDS)
    tuning = config['tuning']
    exact_object(tuning, ('bankone_base_url', 'banktwo_base_url', 'inception_api_base_url', 'inception_model',
                          'inception_api_timeout_seconds', 'stripe_account_id', 'stripe_price_id',
                          'source_http_timeout_seconds', 'source_max_bytes', 'mercury2_extraction_enabled',
                          'mercury2_job_plans_enabled', 'mercury2_procedure_composition_enabled'))
    for key in ('bankone_base_url', 'banktwo_base_url', 'inception_api_base_url'): _https(tuning[key])
    match(tuning['inception_model'], r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}')
    match(tuning['stripe_account_id'], r'acct_[A-Za-z0-9]+')
    match(tuning['stripe_price_id'], r'price_[A-Za-z0-9]+')
    for key, maximum in (('inception_api_timeout_seconds', 120), ('source_http_timeout_seconds', 120), ('source_max_bytes', 104857600)):
        require(type(tuning[key]) is int and 1 <= tuning[key] <= maximum)
    for key in ('mercury2_extraction_enabled', 'mercury2_job_plans_enabled', 'mercury2_procedure_composition_enabled'):
        require(type(tuning[key]) is bool)
    canonical_bytes(config)
    return sha256(config)


def validate_manifest(manifest, config, rollback_manifest=None):
    config_hash = validate_config(config)
    schema = strict_json((Path(__file__).parent / 'release.schema.json').read_bytes())
    _schema_validate(manifest, schema)
    require(len(canonical_bytes(manifest)) <= MAX_JSON_BYTES)
    require(manifest['service_config_sha256'] == config_hash)
    for role in ('api', 'ingestion', 'migration'):
        require(manifest['images'][role]['reference'].startswith(config['resources']['artifact_repository'] + '/' + role + '@sha256:'))
    require(manifest['images']['minio']['reference'] == 'ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d')
    require(manifest['images']['minio']['image_id'] == 'sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5')
    files = manifest['migrations']['files']
    require(len(files) <= 999)
    require([f['name'] for f in files] == sorted(f['name'] for f in files))
    require([int(f['name'][:3]) for f in files] == list(range(1, len(files) + 1)))
    require(manifest['migrations']['inventory_sha256'] == sha256(files))
    for image in manifest['images'].values():
        for key in ('provenance_uri', 'sbom_uri'):
            # Immutable HTTP(S) artifact locator; no URL credentials or aliases.
            _https(image[key])
    previous = manifest['rollback_source_sha']
    if previous is not None:
        require(previous != manifest['source_sha'] and rollback_manifest is not None)
        # Do not recursively demand older historical manifests for this boundary.
        _schema_validate(rollback_manifest, schema)
        require(rollback_manifest['source_sha'] == previous)
        require(rollback_manifest['platform'] == manifest['platform'])
        require(rollback_manifest['service_config_sha256'] == config_hash)
        require(rollback_manifest['migrations'] == manifest['migrations'])
        # Conservative v1: automatic image rollback only with identical SQL tree.
    return sha256(manifest)


def validate_migration_tree(manifest, directory, runner, actual_schema):
    directory, runner = Path(directory), Path(runner)
    require(directory.is_dir() and not directory.is_symlink() and runner.is_file() and not runner.is_symlink())
    expected = manifest['migrations']['files']
    require(sorted(p.name for p in directory.iterdir()) == [f['name'] for f in expected])
    for item in expected:
        path = directory / item['name']
        require(path.is_file() and not path.is_symlink())
        require(hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'])
    require(hashlib.sha256(runner.read_bytes()).hexdigest() == manifest['migrations']['runner_sha256'])
    require(type(actual_schema) is int and actual_schema == len(expected))
    return True


def validate_cached_images(manifest, observations):
    """Validate already collected local image facts; performs no image inspection."""
    exact_object(observations, IMAGE_ROLES)
    for role in IMAGE_ROLES:
        image = observations[role]
        exact_object(image, ('reference', 'image_id', 'platform'))
        require(image['reference'] == manifest['images'][role]['reference'])
        require(image['image_id'] == manifest['images'][role]['image_id'])
        require(image['platform'] == manifest['platform'])
    return True


def validate_start_prerequisites(config, evidence):
    """Validate supplied evidence shape, not discover or certify actual host state.

    Later installed helpers must collect these facts using fixed trusted probes
    before accepting them. Neither callers nor this offline renderer can attest
    that a guard, mount, secret, or image actually exists on a machine.
    """
    validate_config(config)
    exact_object(evidence, ('disk_uuid', 'data_mount', 'metadata_guard', 'storage_guard', 'tmpfs_secrets', 'cached_images'))
    require(evidence['disk_uuid'] == config['resources']['data_disk_filesystem_uuid'])
    require(evidence['data_mount'] == DATA_ROOT)
    require(all(evidence[name] is True for name in ('metadata_guard', 'storage_guard', 'tmpfs_secrets', 'cached_images')))
    return True


def read_private_json(path, owner_uid=0):
    """Bounded descriptor read, refusing symlinks, wrong owner/mode or replacement.

    Installed callers use HOST_CONFIG only; the CLI accepts no config path.
    Bootstrap is responsible for protecting the containing root-owned directory.
    """
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        metadata = os.fstat(descriptor)
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == owner_uid and stat.S_IMODE(metadata.st_mode) == 0o600)
        require(metadata.st_size <= MAX_JSON_BYTES)
        data = bytearray()
        while len(data) <= MAX_JSON_BYTES:
            block = os.read(descriptor, min(65536, MAX_JSON_BYTES + 1 - len(data)))
            if not block: break
            data.extend(block)
        return strict_json(bytes(data))
    except OSError:
        raise ContractError('private configuration unavailable') from None
    finally:
        if descriptor is not None: os.close(descriptor)


def _uuid(value):
    match(value, r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
    require(str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0)


def parse_helper_args(helper, args):
    require(type(args) in (list, tuple) and all(type(arg) is str for arg in args))
    verbs = {'deploy.sh': ('install', 'check', 'start', 'stop', 'maintenance', 'resume'),
             'backup-host.sh': ('begin', 'status', 'export', 'resume'), 'restore.sh': ('restore', 'validate'),
             'runtime-check.py': ('check', 'metrics')}
    require(helper in verbs)
    require(len(args) == (3 if helper == 'runtime-check.py' else 2) and args[0] in verbs[helper])
    if helper == 'runtime-check.py': require(args[1] == '--release')
    value = args[-1]
    if helper in ('deploy.sh', 'runtime-check.py'): match(value, SHA_PATTERN)
    else: _uuid(value)
    return {'operation': helper + ' ' + args[0], 'source_sha': value if helper in ('deploy.sh', 'runtime-check.py') else None,
            'run_id': None if helper in ('deploy.sh', 'runtime-check.py') else value}


def _timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def operation_receipt(operation, source_sha, run_id, exit_code, checks, failure_code=None):
    require(operation in [helper + ' ' + verb for helper, verbs in {
        'deploy.sh': ('install', 'check', 'start', 'stop', 'maintenance', 'resume'),
        'backup-host.sh': ('begin', 'status', 'export', 'resume'), 'restore.sh': ('restore', 'validate'),
        'runtime-check.py': ('check', 'metrics')}.items() for verb in verbs])
    if source_sha is not None: match(source_sha, SHA_PATTERN)
    if run_id is not None: _uuid(run_id)
    require(exit_code in EXIT_STATUS and type(checks) is dict and set(checks) <= CHECK_NAMES)
    require(all(type(value) is bool for value in checks.values()))
    require((exit_code == 0 and failure_code is None and all(checks.values())) or
            (exit_code != 0 and failure_code in FAILURE_CODES))
    now = _timestamp()
    receipt = {'schema_version': 1, 'operation': operation, 'run_id': run_id, 'source_sha': source_sha,
               'status': EXIT_STATUS[exit_code], 'started_at': now, 'finished_at': now,
               'checks': copy.deepcopy(checks), 'failure_code': failure_code}
    require(len(canonical_bytes(receipt)) <= 65536)
    return receipt


def metrics_receipt(source_sha, measurements):
    match(source_sha, SHA_PATTERN)
    require(type(measurements) is list and len(measurements) <= len(METRIC_UNITS))
    names = set()
    for item in measurements:
        exact_object(item, ('name', 'value', 'unit', 'state'))
        name = item['name']
        require(type(name) is str and name in METRIC_UNITS and name not in names)
        names.add(name)
        require(type(item['value']) in (int, float) and math.isfinite(item['value']) and item['value'] >= 0)
        require(item['unit'] == METRIC_UNITS[name] and item['state'] in ('ok', 'warning', 'critical'))
    return {'schema_version': 1, 'source_sha': source_sha, 'observed_at': _timestamp(), 'metrics': copy.deepcopy(measurements)}


def _service_environments(config):
    tuning, firebase = config['tuning'], config['firebase']
    shared = {'AUTODATA_ENV': config['environment'], 'AUTODATA_PUBLIC_ORIGIN': config['public_origin'],
              'AUTODATA_COMMERCE_MODE': 'stripe_live' if config['environment'] == 'production' else 'stripe_test'}
    db = {'AUTODATA_DB_ADDRESS': 'postgres:5432', 'AUTODATA_POSTGRES_DB': 'autodata'}
    s3 = {'AUTODATA_S3_ADDRESS': 'minio:9000', 'AUTODATA_S3_ENDPOINT': 'minio:9000', 'AUTODATA_SOURCE_BUCKET': 'autodata-sources'}
    bank = {'BANKONE_BASE_URL': tuning['bankone_base_url'], 'BANKTWO_BASE_URL': tuning['banktwo_base_url']}
    stripe = {'AUTODATA_STRIPE_ACCOUNT_ID': tuning['stripe_account_id'], 'AUTODATA_STRIPE_PRICE_ID': tuning['stripe_price_id']}
    result = {}
    for service, user in (('api', 'autodata_api'), ('ingestion-http', 'autodata_http'),
                          ('article-worker', 'autodata_article'), ('payment-reconciler', 'autodata_reconciler')):
        result[service] = dict(shared, **db, AUTODATA_POSTGRES_USER=user, AUTODATA_RUNTIME_SERVICE=service)
    result['api'].update(s3, AUTODATA_AUTH_MODE='firebase', AUTODATA_PROJECTION_STORE='postgres', AUTODATA_API_ADDR=':8080',
                         AUTODATA_NATS_ADDRESS='nats:4222', AUTODATA_INGESTION_URL='http://ingestion-http:8081',
                         AUTODATA_FIREBASE_PROJECT_ID=firebase['project_id'], AUTODATA_FIREBASE_WEB_API_KEY=firebase['web_api_key'],
                         AUTODATA_FIREBASE_WEB_APP_ID=firebase['web_app_id'], AUTODATA_FIREBASE_AUTH_DOMAIN=firebase['auth_domain'])
    result['ingestion-http'].update(s3, **bank, **stripe, AUTODATA_INGESTION_HTTP_ADDR=':8081',
                                    AUTODATA_SOURCE_HTTP_TIMEOUT_SECONDS=str(tuning['source_http_timeout_seconds']),
                                    AUTODATA_SOURCE_MAX_BYTES=str(tuning['source_max_bytes']))
    result['payment-reconciler'].update(stripe)
    result['article-worker'].update(s3, **bank, INCEPTION_API_BASE_URL=tuning['inception_api_base_url'], INCEPTION_MODEL=tuning['inception_model'],
                                    INCEPTION_API_TIMEOUT_SECONDS=str(tuning['inception_api_timeout_seconds']))
    for key in ('extraction', 'job_plans', 'procedure_composition'):
        result['article-worker']['AUTODATA_MERCURY2_' + key.upper() + '_ENABLED'] = '1' if tuning['mercury2_' + key + '_enabled'] else '0'
    result['postgres'] = {'POSTGRES_DB': 'autodata', 'POSTGRES_USER': 'autodata_admin',
                          'POSTGRES_PASSWORD_FILE': '/run/autodata/postgres/POSTGRES_PASSWORD', 'PGDATA': '/var/lib/postgresql/data/pgdata'}
    result['migration'] = {'AUTODATA_RUNTIME_SERVICE': 'migration', 'PGHOST': 'postgres', 'PGPORT': '5432',
                           'PGDATABASE': 'autodata', 'PGUSER': 'autodata_migrator'}
    result['bootstrap'] = dict(s3, AUTODATA_RUNTIME_SERVICE='bootstrap')
    result['metrics-probe'] = dict(db, AUTODATA_POSTGRES_USER='autodata_metrics', AUTODATA_RUNTIME_SERVICE='metrics-probe')
    return result


def render_bundle(manifest, config, rollback_manifest=None):
    """Render nonsecret definitions, never a runtime readiness result.

    nats/S3 @@...@@ tokens deliberately remain for later private config delivery.
    Only the Compose/Caddy nonsecret tokens below are replaced; ambient env is
    never consulted. Deploy must check all x-autodata-prerequisites separately.
    """
    validate_manifest(manifest, config, rollback_manifest)
    here = Path(__file__).parent
    template = strict_json((here.parents[1] / 'compose' / 'compose.production.yaml').read_bytes())
    mapping = {'RELEASE_DIR': RELEASE_ROOT + '/' + manifest['source_sha'], 'DISK_UUID': config['resources']['data_disk_filesystem_uuid']}
    mapping.update({'IMAGE_' + role.upper(): image['reference'] for role, image in manifest['images'].items()})
    mapping.update({'ENV_' + name.upper().replace('-', '_'): env for name, env in _service_environments(config).items()})
    def expand(value):
        if isinstance(value, dict): return {key: expand(item) for key, item in value.items()}
        if isinstance(value, list): return [expand(item) for item in value]
        if not isinstance(value, str): return value
        token = re.fullmatch(r'\$\{([A-Z_]+):\?required\}', value)
        if token:
            require(token[1] in mapping)
            return copy.deepcopy(mapping[token[1]])
        for key, replacement in mapping.items():
            if type(replacement) is str: value = value.replace('${' + key + ':?required}', replacement)
        require('${' not in value)
        return value
    compose = expand(template)
    for service in compose['services'].values():
        # Escape Compose interpolation in literal owner-approved nonsecret values.
        for key, value in service.get('environment', {}).items(): require('$' not in value)
    caddy = (here / 'Caddyfile').read_text()
    for token, value in {'PUBLIC_ORIGIN': config['public_origin'], 'ACME_EMAIL': config['resources']['acme_email']}.items():
        caddy = caddy.replace('${' + token + ':?required}', value)
    require('${' not in caddy)
    return {'compose.production.yaml': json.dumps(compose, indent=2) + '\n', 'Caddyfile': caddy,
            'nats.conf.template': (here / 'nats.conf.template').read_text(),
            'seaweedfs-s3.json.template': (here / 'seaweedfs-s3.json.template').read_text()}


def cli(argv):
    try:
        args = parse_helper_args('runtime-check.py', argv)
    except ContractError:
        return 2, operation_receipt('runtime-check.py check', None, None, 2, {}, 'invalid_input')
    # No fallback to local shell, credentials, cwd, or probes in this milestone.
    return 3, operation_receipt(args['operation'], args['source_sha'], None, 3,
                                {'runtime_evidence': False}, 'missing_dependency')


if __name__ == '__main__':
    code, output = cli(sys.argv[1:])
    sys.stdout.buffer.write(canonical_bytes(output) + b'\n')
    raise SystemExit(code)
