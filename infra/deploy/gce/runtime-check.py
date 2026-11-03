#!/usr/bin/env python3
"""Workshop hosting v1 passive contract.

The release check/metrics CLI fails closed without runtime observations. The
additive fixed guard CLI only reads its two nft tables; it never mutates rules,
starts services, probes endpoints or reads credentials. Imports remain the
shared interface for later, separately authorized helpers.
"""
import copy
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import sys
import time
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


def _validate_immutable_images(manifest, config):
    """Enforce one nonrecursive image authority after manifest schema validation."""
    for role in ('api', 'ingestion', 'migration'):
        require(manifest['images'][role]['reference'].startswith(config['resources']['artifact_repository'] + '/' + role + '@sha256:'))
    require(manifest['images']['minio']['reference'] == 'ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d')
    require(manifest['images']['minio']['image_id'] == 'sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5')
    for image in manifest['images'].values():
        for key in ('provenance_uri', 'sbom_uri'):
            # Immutable HTTP(S) artifact locator; no URL credentials or aliases.
            _https(image[key])


def validate_manifest(manifest, config, rollback_manifest=None):
    config_hash = validate_config(config)
    schema = strict_json((Path(__file__).parent / 'release.schema.json').read_bytes())
    _schema_validate(manifest, schema)
    require(len(canonical_bytes(manifest)) <= MAX_JSON_BYTES)
    require(manifest['service_config_sha256'] == config_hash)
    _validate_immutable_images(manifest, config)
    files = manifest['migrations']['files']
    require(len(files) <= 999)
    require([f['name'] for f in files] == sorted(f['name'] for f in files))
    require([int(f['name'][:3]) for f in files] == list(range(1, len(files) + 1)))
    require(manifest['migrations']['inventory_sha256'] == sha256(files))
    previous = manifest['rollback_source_sha']
    if previous is not None:
        require(previous != manifest['source_sha'] and rollback_manifest is not None)
        # Do not recursively demand older historical manifests for this boundary.
        _schema_validate(rollback_manifest, schema)
        _validate_immutable_images(rollback_manifest, config)
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


def validate_schema_ledger(manifest, observation):
    """Pure ledger comparison only; no DB connection or schema attestation."""
    exact_object(observation, ('version', 'migrations'))
    expected = [item['name'][:-4] for item in manifest['migrations']['files']]
    require(type(observation['version']) is int and observation['version'] == len(expected))
    require(type(observation['migrations']) is list and observation['migrations'] == expected)
    return True


def collect_cached_images(manifest):
    """Inspect only immutable local references on the fixed local Docker socket.

    The output template excludes Config.Env, labels and other application data.
    No registry access, pull, container creation or caller-selected context exists.
    """
    # Docker CLI v28.5.1 first templates the typed InspectResponse: ID, not Id.
    # Using Id falls back to raw JSON where an empty Variant is omitted.
    template = '{"image_id":{{json .ID}},"repo_digests":{{json .RepoDigests}},"os":{{json .Os}},"architecture":{{json .Architecture}},"variant":{{json .Variant}}}'
    observations = {}
    for role in IMAGE_ROLES:
        reference = manifest['images'][role]['reference']
        result = subprocess.run(['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock', 'image', 'inspect', '--platform', 'linux/amd64', '--format', template, reference],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=5, check=False, cwd='/', env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'})
        require(result.returncode == 0)
        image = strict_json(result.stdout)
        exact_object(image, ('image_id', 'repo_digests', 'os', 'architecture', 'variant'))
        digests = image['repo_digests']
        require(type(digests) is list and 1 <= len(digests) <= 256)
        require(all(type(value) is str and len(value) <= 4096 for value in digests))
        require(len(set(digests)) == len(digests) and reference in digests)
        require(image['os'] == 'linux' and image['architecture'] == 'amd64' and image['variant'] == '')
        observations[role] = {'reference': reference, 'image_id': image['image_id'], 'platform': 'linux/amd64'}
    return validate_cached_images(manifest, observations)


# Passive schema wire v1: fixed literals, never host.json / environment options.
SCHEMA_PROTOCOL_VERSION = 1
POSTGRES_CONTAINER = 'autodata-production-postgres-1'
POSTGRES_ROLE = 'autodata_metrics'
POSTGRES_DATABASE = 'autodata'
POSTGRES_SOCKET = '/var/run/postgresql'
POSTGRES_PORT = 5432
POSTGRES_CLIENT = '/usr/lib/postgresql/17/bin/psql'
MAX_LEDGER_ROWS = 999
MAX_LEDGER_VALUE_BYTES = 251
MAX_INSPECT_STDOUT_BYTES = 65536
MAX_SQL_STDOUT_BYTES = 524288
READ_CHUNK_BYTES = 4096
COMMAND_TIMEOUT_SECONDS = 5
COLLECTOR_TIMEOUT_SECONDS = 15
REAP_TIMEOUT_SECONDS = 1
SCHEMA_HOST_ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}
POSTGRES_PGOPTIONS = '-c default_transaction_read_only=on -c statement_timeout=2000 -c lock_timeout=1000 -c search_path=pg_catalog'
POSTGRES_INSPECT_TEMPLATE = '{"id":{{json .ID}},"name":{{json .Name}},"image":{{json .Image}},"user":{{json .Config.User}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"command":{{json .Config.Cmd}},"running":{{json .State.Running}},"paused":{{json .State.Paused}},"restarting":{{json .State.Restarting}},"dead":{{json .State.Dead}},"started_at":{{json .State.StartedAt}},"readonly_root":{{json .HostConfig.ReadonlyRootfs}},"privileged":{{json .HostConfig.Privileged}},"cap_add":{{json .HostConfig.CapAdd}},"cap_drop":{{json .HostConfig.CapDrop}},"security_opt":{{json .HostConfig.SecurityOpt}},"mounts":{{json .Mounts}},"tmpfs":{{json .HostConfig.Tmpfs}}}'
# One SELECT, one snapshot. All rights functions use effective role privileges,
# including PUBLIC and column-only grants. No application function is called.
# Trusted concurrent administrative DDL and effective PGDATA remain outside this
# point-in-time observation; no restricted setting or elevated role is needed.
POSTGRES_SCHEMA_SQL = r'''WITH
r AS MATERIALIZED (SELECT oid, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
    rolreplication, rolbypassrls, rolinherit FROM pg_catalog.pg_roles WHERE rolname = 'autodata_metrics'),
d AS MATERIALIZED (SELECT oid, datdba FROM pg_catalog.pg_database WHERE datname = 'autodata'),
n AS MATERIALIZED (SELECT oid, nspowner FROM pg_catalog.pg_namespace WHERE nspname = 'public'),
app_ns AS MATERIALIZED (SELECT oid, nspowner FROM pg_catalog.pg_namespace
    WHERE nspname <> 'information_schema' AND nspname !~ '^pg_'),
app_rel AS MATERIALIZED (SELECT c.* FROM pg_catalog.pg_class c JOIN app_ns ON app_ns.oid = c.relnamespace),
c AS MATERIALIZED (SELECT c.* FROM pg_catalog.pg_class c JOIN n ON n.oid = c.relnamespace
    WHERE c.relname = 'schema_migrations'),
a AS MATERIALIZED (SELECT a.* FROM pg_catalog.pg_attribute a JOIN c ON c.oid = a.attrelid
    WHERE a.attname = 'version' AND a.attnum > 0 AND NOT a.attisdropped),
limited AS MATERIALIZED (SELECT version FROM public.schema_migrations LIMIT 1000),
sanitized AS MATERIALIZED (SELECT CASE WHEN version IS NOT NULL AND octet_length(version) <= 251
    THEN CASE WHEN version COLLATE "C" ~ '^[0-9]{3}_[a-z0-9_]+$' THEN version ELSE NULL END
    ELSE NULL END AS version FROM limited),
ledger AS MATERIALIZED (SELECT count(*) AS count, COALESCE(bool_or(version IS NULL), false) AS invalid,
    json_agg(version ORDER BY version COLLATE "C") AS versions FROM sanitized)
SELECT json_build_object(
 'protocol_version', 1,
 'identity', json_build_object('session_user', session_user, 'current_user', current_user,
    'database', current_database(), 'server_version_num', current_setting('server_version_num')::integer,
    'transaction_read_only', current_setting('transaction_read_only') = 'on',
    'default_transaction_read_only', current_setting('default_transaction_read_only') = 'on',
    'client_addr', inet_client_addr(), 'client_port', inet_client_port()),
 'rights', (SELECT json_build_object(
    'login', r.rolcanlogin, 'superuser', r.rolsuper, 'create_db', r.rolcreatedb,
    'create_role', r.rolcreaterole, 'replication', r.rolreplication,
    'bypass_rls', r.rolbypassrls, 'inherit', r.rolinherit,
    'membership_count', (SELECT count(*) FROM pg_catalog.pg_auth_members m WHERE m.member = r.oid),
    'connect', has_database_privilege(r.oid, d.oid, 'CONNECT'),
    'schema_usage', (SELECT has_schema_privilege(r.oid, n.oid, 'USAGE') FROM n),
    'ledger_select', (SELECT has_table_privilege(r.oid, c.oid, 'SELECT') FROM c),
    'database_create', has_database_privilege(r.oid, d.oid, 'CREATE'),
    'database_temp', has_database_privilege(r.oid, d.oid, 'TEMP'),
    'database_owner', d.datdba = r.oid,
    'schema_create', EXISTS (SELECT FROM app_ns x WHERE has_schema_privilege(r.oid, x.oid, 'CREATE')),
    'schema_owner', EXISTS (SELECT FROM app_ns x WHERE x.nspowner = r.oid),
    'relation_owner', EXISTS (SELECT FROM app_rel x WHERE x.relkind <> 'S' AND x.relowner = r.oid),
    'sequence_owner', EXISTS (SELECT FROM app_rel x WHERE x.relkind = 'S' AND x.relowner = r.oid),
    'relation_write', EXISTS (SELECT FROM app_rel x CROSS JOIN unnest(ARRAY[
        'INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN']) AS p(privilege)
        WHERE CASE WHEN x.relkind IN ('r','p','v','m','f') THEN has_table_privilege(r.oid, x.oid, p.privilege) ELSE false END),
    'column_write', EXISTS (SELECT FROM app_rel x CROSS JOIN unnest(ARRAY['INSERT','UPDATE','REFERENCES']) AS p(privilege)
        WHERE CASE WHEN x.relkind IN ('r','p','v','m','f') THEN has_any_column_privilege(r.oid, x.oid, p.privilege) ELSE false END),
    'sequence_write', EXISTS (SELECT FROM app_rel x WHERE CASE WHEN x.relkind = 'S' THEN has_sequence_privilege(r.oid, x.oid, 'USAGE,UPDATE') ELSE false END)
    ) FROM r CROSS JOIN d),
 'ledger_relation', (SELECT json_build_object(
    'oid', c.oid, 'schema', 'public', 'name', c.relname, 'kind', c.relkind, 'persistence', c.relpersistence,
    'is_partition', c.relispartition,
    'has_inheritance', EXISTS (SELECT FROM pg_catalog.pg_inherits i WHERE i.inhrelid = c.oid OR i.inhparent = c.oid),
    'rls', c.relrowsecurity, 'force_rls', c.relforcerowsecurity,
    'version_type', CASE WHEN a.atttypid = 'pg_catalog.text'::regtype THEN 'pg_catalog.text' ELSE NULL END,
    'version_not_null', a.attnotnull, 'version_generated', a.attgenerated, 'version_identity', a.attidentity,
    'primary_key_version', EXISTS (SELECT FROM pg_catalog.pg_constraint k
        WHERE k.conrelid = c.oid AND k.contype = 'p' AND k.conkey = ARRAY[a.attnum]::smallint[])
    ) FROM c CROSS JOIN a),
 'ledger', (SELECT json_build_object('version', ledger.count, 'overflow', ledger.count > 999,
    'invalid_value', ledger.invalid,
    'migrations', CASE WHEN ledger.count > 999 OR ledger.invalid THEN '[]'::json
                      ELSE COALESCE(ledger.versions, '[]'::json) END) FROM ledger))'''


def _bounded_schema_command(argv, maximum, collector_deadline):
    """Bound new schema observations before retaining bytes, including cleanup.

    CLI kill does not stop a remote exec; the fixed server statement_timeout
    separately bounds the SQL. Exceptional kill/reap has a single extra second.
    """
    deadline = min(collector_deadline, time.monotonic() + COMMAND_TIMEOUT_SECONDS)
    if time.monotonic() >= deadline:
        raise subprocess.TimeoutExpired('schema observation', COMMAND_TIMEOUT_SECONDS)
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, cwd='/', env=dict(SCHEMA_HOST_ENV))
    selector = None
    try:
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        data = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise subprocess.TimeoutExpired('schema observation', COMMAND_TIMEOUT_SECONDS)
            wanted = min(READ_CHUNK_BYTES, maximum + 1 - len(data))
            chunk = process.stdout.read1(wanted)
            require(type(chunk) is bytes and len(chunk) <= wanted)
            if not chunk:
                break
            data.extend(chunk)
            require(len(data) <= maximum)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired('schema observation', COMMAND_TIMEOUT_SECONDS)
        require(process.wait(timeout=remaining) == 0)
        return bytes(data)
    finally:
        cleanup_failed = False
        try:
            if process.poll() is None:
                process.kill()
        except OSError:
            cleanup_failed = True
        try:
            process.stdout.close()
        except OSError:
            cleanup_failed = True
        if selector is not None:
            try:
                selector.close()
            except OSError:
                cleanup_failed = True
        try:
            process.wait(timeout=max(0, min(REAP_TIMEOUT_SECONDS, collector_deadline + REAP_TIMEOUT_SECONDS - time.monotonic())))
        except (OSError, subprocess.TimeoutExpired):
            cleanup_failed = True
        require(not cleanup_failed)


def validate_postgres_container(manifest, value):
    """Bind only the inspected container facts; mounts do not attest PGDATA."""
    exact_object(value, ('id', 'name', 'image', 'user', 'project', 'service', 'command', 'running', 'paused',
                         'restarting', 'dead', 'started_at', 'readonly_root', 'privileged', 'cap_add', 'cap_drop',
                         'security_opt', 'mounts', 'tmpfs'))
    match(value['id'], HASH_PATTERN)
    require(value['name'] == '/' + POSTGRES_CONTAINER and value['image'] == manifest['images']['postgres']['image_id'])
    require(value['user'] == '999:999' and value['project'] == 'autodata-production' and value['service'] == 'postgres')
    require(value['command'] == ['postgres'])
    for key, expected in (('running', True), ('paused', False), ('restarting', False), ('dead', False),
                          ('readonly_root', True), ('privileged', False)):
        require(type(value[key]) is bool and value[key] is expected)
    match(value['started_at'], r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?Z')
    try:
        require(datetime.fromisoformat(value['started_at'].replace('Z', '+00:00')).year >= 1970)
    except ValueError:
        raise ContractError('invalid container timestamp') from None
    require(value['cap_add'] is None or value['cap_add'] == [])
    require(value['cap_drop'] == ['ALL'] and value['security_opt'] == ['no-new-privileges:true'])
    require(type(value['mounts']) is list and len(value['mounts']) == 2)
    mounts = {}
    expected = {'/var/lib/postgresql/data': (DATA_ROOT + '/postgres', True),
                '/run/autodata/postgres': (SECRET_ROOT + '/postgres', False)}
    for mount in value['mounts']:
        exact_object(mount, ('Type', 'Source', 'Destination', 'Mode', 'RW', 'Propagation'))
        target = mount['Destination']
        require(type(target) is str and target in expected and target not in mounts)
        source, writable = expected[target]
        require(mount['Type'] == 'bind' and mount['Source'] == source)
        require(type(mount['RW']) is bool and mount['RW'] is writable and mount['Propagation'] == 'rprivate')
        require(mount['Mode'] in ('', 'rw' if writable else 'ro'))
        mounts[target] = mount
    exact_object(value['tmpfs'], ('/tmp', POSTGRES_SOCKET))
    require(value['tmpfs'] == {'/tmp': 'rw,nosuid,nodev,noexec,size=67108864,mode=1777',
                             POSTGRES_SOCKET: 'rw,nosuid,nodev,noexec,size=16777216,uid=999,gid=999,mode=0700'})
    normalized = copy.deepcopy(value)
    normalized['mounts'] = [mounts[key] for key in sorted(mounts)]
    normalized['cap_add'] = []
    return normalized


def validate_schema_observation(manifest, value):
    """Strict wire v1; never accepts RLS-filtered or prefix-only ledger evidence."""
    exact_object(value, ('protocol_version', 'identity', 'rights', 'ledger_relation', 'ledger'))
    require(type(value['protocol_version']) is int and value['protocol_version'] == SCHEMA_PROTOCOL_VERSION)
    identity = value['identity']
    exact_object(identity, ('session_user', 'current_user', 'database', 'server_version_num', 'transaction_read_only',
                            'default_transaction_read_only', 'client_addr', 'client_port'))
    require(identity['session_user'] == POSTGRES_ROLE and identity['current_user'] == POSTGRES_ROLE)
    require(identity['database'] == POSTGRES_DATABASE)
    require(type(identity['server_version_num']) is int and 170000 <= identity['server_version_num'] <= 179999)
    require(identity['transaction_read_only'] is True and identity['default_transaction_read_only'] is True)
    require(identity['client_addr'] is None and identity['client_port'] is None)
    rights = value['rights']
    expected_rights = {'login': True, 'superuser': False, 'create_db': False, 'create_role': False,
        'replication': False, 'bypass_rls': False, 'inherit': False, 'membership_count': 0,
        'connect': True, 'schema_usage': True, 'ledger_select': True, 'database_create': False, 'database_temp': False,
        'database_owner': False, 'schema_create': False, 'schema_owner': False, 'relation_owner': False,
        'sequence_owner': False, 'relation_write': False, 'column_write': False, 'sequence_write': False}
    exact_object(rights, expected_rights)
    for key, expected in expected_rights.items():
        require(type(rights[key]) is type(expected) and rights[key] == expected)
    relation = value['ledger_relation']
    expected_relation = {'schema': 'public', 'name': 'schema_migrations', 'kind': 'r', 'persistence': 'p',
        'is_partition': False, 'has_inheritance': False, 'rls': False, 'force_rls': False, 'version_type': 'pg_catalog.text',
        'version_not_null': True, 'version_generated': '', 'version_identity': '', 'primary_key_version': True}
    exact_object(relation, (*expected_relation, 'oid'))
    require(type(relation['oid']) is int and 0 < relation['oid'] <= 4294967295)
    for key, expected in expected_relation.items():
        require(type(relation[key]) is type(expected) and relation[key] == expected)
    ledger = value['ledger']
    exact_object(ledger, ('version', 'overflow', 'invalid_value', 'migrations'))
    require(ledger['overflow'] is False and ledger['invalid_value'] is False)
    require(type(ledger['version']) is int and 1 <= ledger['version'] <= MAX_LEDGER_ROWS)
    require(type(ledger['migrations']) is list and 1 <= len(ledger['migrations']) <= MAX_LEDGER_ROWS)
    for version in ledger['migrations']:
        match(version, r'[0-9]{3}_[a-z0-9_]+')
        require(len(version.encode('ascii')) <= MAX_LEDGER_VALUE_BYTES)
    return validate_schema_ledger(manifest, {'version': ledger['version'], 'migrations': ledger['migrations']})


def collect_postgres_schema(manifest):
    """Fixed socket-only low-role observation; no provision/start/password fallback."""
    deadline = time.monotonic() + COLLECTOR_TIMEOUT_SECONDS
    prefix = ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock']
    def inspect(target):
        output = _bounded_schema_command(prefix + ['container', 'inspect', '--format', POSTGRES_INSPECT_TEMPLATE, target],
                                         MAX_INSPECT_STDOUT_BYTES, deadline)
        return validate_postgres_container(manifest, strict_json(output))
    before = inspect(POSTGRES_CONTAINER)
    argv = prefix + ['exec', '--user', '999:999', '--workdir', '/', before['id'],
        '/usr/bin/env', '-i', 'PATH=/usr/lib/postgresql/17/bin:/usr/bin:/bin', 'LANG=C', 'LC_ALL=C',
        'HOME=/nonexistent', 'PGPASSFILE=/dev/null', 'PGSERVICEFILE=/dev/null', 'PGOPTIONS=' + POSTGRES_PGOPTIONS,
        POSTGRES_CLIENT, '--no-psqlrc', '--no-password', '--no-align', '--tuples-only', '--quiet',
        '--host=' + POSTGRES_SOCKET, '--port=5432', '--username=' + POSTGRES_ROLE, '--dbname=' + POSTGRES_DATABASE,
        '--set=ON_ERROR_STOP=1', '--command=' + POSTGRES_SCHEMA_SQL]
    observation = strict_json(_bounded_schema_command(argv, MAX_SQL_STDOUT_BYTES, deadline))
    validate_schema_observation(manifest, observation)
    require(inspect(before['id']) == before)
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
    if helper == 'runtime-check.py' and args == ['guard']:
        return {'operation': 'runtime-check.py guard', 'source_sha': None, 'run_id': None}
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
        'runtime-check.py': ('check', 'metrics', 'guard')}.items() for verb in verbs])
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


def _guard_expected(family):
    """Literal guard contract in nft JSON form; no host observation or mutation.

    Exact readback deliberately fails closed on a different nft JSON encoding.
    The reviewed toolchain must prove its parser/JSON/kernel semantics in staging.
    """
    table = 'autodata_guard'
    chains = {}
    def match_meta(key, value):
        return {'match': {'op': '==', 'left': {'meta': {'key': key}}, 'right': value}}
    def match_payload(protocol, field, value):
        return {'match': {'op': '==', 'left': {'payload': {'protocol': protocol, 'field': field}}, 'right': value}}
    def rule(*expressions, verdict='drop'):
        return list(expressions) + [{verdict: None}]
    def destination(address):
        return match_payload('ip6' if ':' in address else 'ip', 'daddr', address)
    def s3(bridge, subnet, interface='iifname'):
        return rule(match_meta(interface, bridge), match_payload('ip', 'saddr', {'prefix': {'addr': subnet, 'len': 24}}),
                    destination('172.30.20.40'), match_payload('tcp', 'dport', 9000), verdict='accept')
    if family == 'inet':
        chains['forward'] = [
            rule(match_meta('iifname', 'br-ad-edge'), match_payload('ip', 'saddr', '172.30.10.10'),
                 destination('169.254.169.254'), match_payload('tcp', 'dport', 80), verdict='accept'),
            rule(destination('169.254.169.254')), rule(destination('fd20:ce::254'))]
        chains['forward'] += [rule(match_meta('iifname', bridge), match_meta('nfproto', 'ipv6'))
                              for bridge in ('br-ad-edge', 'br-ad-back', 'br-ad-work')]
        chains['forward'] += [s3(bridge, subnet) for bridge, subnet in (
            ('br-ad-edge', '172.30.10.0'), ('br-ad-back', '172.30.20.0'), ('br-ad-work', '172.30.30.0'))]
        chains['forward'] += [rule(destination('172.30.20.40'))]
        chains['output'] = [rule(match_meta('skuid', 0), destination('169.254.169.254'),
                                 match_payload('tcp', 'dport', 80), verdict='accept'),
                            rule(destination('169.254.169.254')), rule(destination('fd20:ce::254'))]
    else:
        require(family == 'bridge')
        chains['forward'] = [rule(match_meta('ibrname', bridge), match_payload('ether', 'type', 'ip6'))
                              for bridge in ('br-ad-edge', 'br-ad-back', 'br-ad-work')]
        chains['forward'] += [s3('br-ad-back', '172.30.20.0', 'ibrname'), rule(destination('172.30.20.40'))]
    records = [{'table': {'family': family, 'name': table}}]
    # nft table_print_json_full emits all chain declarations before rules.
    for name in chains:
        records.append({'chain': {'family': family, 'table': table, 'name': name, 'type': 'filter',
                                  'hook': name, 'prio': -200, 'policy': 'accept'}})
    for name, expressions in chains.items():
        records.extend({'rule': {'family': family, 'table': table, 'chain': name, 'expr': expr}} for expr in expressions)
    return records


def validate_guard_tables(snapshots):
    """Compare full table/chain/rule content, retaining rule order per chain.

    Only nondeterministic kernel handles and the nft version envelope are
    discarded; exact protocol number/name equivalents and the redundant TCP
    dependency are normalized. Extra chains/rules/fields fail closed.
    Docker's unrelated tables are neither read nor changed.
    """
    exact_object(snapshots, ('inet', 'bridge'))
    for family in ('inet', 'bridge'):
        snapshot = snapshots[family]
        exact_object(snapshot, ('nftables',))
        require(type(snapshot['nftables']) is list and len(snapshot['nftables']) <= 64)
        records, metainfo_seen = [], False
        for record in snapshot['nftables']:
            require(type(record) is dict and len(record) == 1)
            kind, data = next(iter(record.items()))
            if kind == 'metainfo':
                require(not metainfo_seen and type(data) is dict)
                metainfo_seen = True
                continue
            require(kind in ('table', 'chain', 'rule') and type(data) is dict)
            data = copy.deepcopy(data)
            if 'handle' in data:
                require(type(data['handle']) is int and data['handle'] >= 0)
                del data['handle']
            if kind == 'rule':
                # nft JSON versions use these exact symbolic/numeric spellings
                # for identical protocol values. Do not normalize other values,
                # operators, fields, or expressions.
                require(type(data.get('expr')) is list)
                for expression in data['expr']:
                    if type(expression) is not dict or set(expression) != {'match'}:
                        continue
                    match = expression['match']
                    require(type(match) is dict)
                    left = match.get('left')
                    if left == {'meta': {'key': 'ibridgename'}}:
                        match['left'] = {'meta': {'key': 'ibrname'}}
                    numeric = None
                    if left == {'meta': {'key': 'l4proto'}}:
                        numeric = (6, 'tcp')
                    elif left == {'meta': {'key': 'nfproto'}}:
                        numeric = (10, 'ipv6')
                    elif left == {'payload': {'protocol': 'ether', 'field': 'type'}}:
                        numeric = (34525, 'ip6')
                    if numeric and type(match.get('right')) is int and match['right'] == numeric[0]:
                        match['right'] = numeric[1]
                # nft delinearization removes meta l4proto tcp immediately
                # before a tcp payload match, whose typed protocol implies it
                # (payload_dependency_kill; upstream inet/tcp.t.json). Support
                # the retained form too, but only for our two exact TCP ports.
                dependency = {'match': {'op': '==', 'left': {'meta': {'key': 'l4proto'}}, 'right': 'tcp'}}
                ports = [{'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}}, 'right': port}}
                         for port in (80, 9000)]
                expressions = data['expr']
                data['expr'] = [expr for index, expr in enumerate(expressions)
                    if not (expr == dependency and index + 1 < len(expressions) and expressions[index + 1] in ports)]
            records.append({kind: data})
        # Normalize only object-class placement: source and nft readback put
        # declarations differently. Preserve chain order and the entire rule
        # sequence; never sort/deduplicate rules or predicates. Exact equality
        # rejects all extra/missing/changed objects and expressions.
        records = [record for kind in ('table', 'chain', 'rule') for record in records if kind in record]
        require(canonical_bytes(records) == canonical_bytes(_guard_expected(family)))
    return True


def guard_cli():
    """One fixed read-only operation for trusted root/systemd, with no paths."""
    checks = {'metadata_guard': False, 'storage_guard': False}
    code, failure = 3, 'guard_missing'
    try:
        require(os.geteuid() == 0)
        snapshots = {}
        for family in ('inet', 'bridge'):
            result = subprocess.run(['/usr/sbin/nft', '--json', '--numeric', 'list', 'table', family, 'autodata_guard'],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=5, check=False, cwd='/', env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'})
            require(result.returncode == 0)
            snapshots[family] = strict_json(result.stdout)
        validate_guard_tables(snapshots)
        code, failure = 0, None
        checks = {'metadata_guard': True, 'storage_guard': True}
    except subprocess.TimeoutExpired:
        code, failure = 5, 'operation_timed_out'
    except (OSError, ContractError):
        pass
    return code, operation_receipt('runtime-check.py guard', None, None, code, checks, failure)



def _owned_directory(path, uid=0, gid=0, mode=None, parent=None):
    """Open a directory without following its final component; never create it.

    Fixed /etc, /opt and /run ancestors are bootstrap's trusted installation
    boundary. Release/service children are opened relative to pinned parent FDs.
    """
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    try:
        metadata = os.fstat(fd)
        require(stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == uid and metadata.st_gid == gid)
        actual = stat.S_IMODE(metadata.st_mode)
        require(actual == mode if mode is not None else not actual & 0o022)
        return fd
    except Exception:
        os.close(fd)
        raise


def _owned_bytes(parent, name, uid, gid, mode, maximum=16384, empty=False):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == uid and before.st_gid == gid)
        require(stat.S_IMODE(before.st_mode) == mode and before.st_nlink == 1)
        require((0 if empty else 1) <= before.st_size <= maximum)
        data = bytearray()
        while len(data) <= maximum:
            chunk = os.read(fd, min(65536, maximum + 1 - len(data)))
            if not chunk: break
            data.extend(chunk)
        after = os.fstat(fd)
        require(len(data) == before.st_size)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns))
        return bytes(data)
    finally:
        os.close(fd)


def _installed_deploy_inputs(source_sha):
    """Only fixed root-owned host/release inputs; no cwd or current-link fallback."""
    match(source_sha, SHA_PATTERN)
    with ExitStack() as resources:
        def directory(path, parent=None):
            fd = _owned_directory(path, parent=parent)
            resources.callback(os.close, fd)
            return fd
        host_parent = directory(str(Path(HOST_CONFIG).parent))
        config = strict_json(_owned_bytes(host_parent, Path(HOST_CONFIG).name, 0, 0, 0o600, MAX_JSON_BYTES))
        root = directory(RELEASE_ROOT)
        selected = directory(source_sha, parent=root)
        manifest = strict_json(_owned_bytes(selected, 'release.json', 0, 0, 0o600, MAX_JSON_BYTES))
        require(type(manifest) is dict and manifest.get('source_sha') == source_sha)
        previous = manifest.get('rollback_source_sha')
        rollback = None
        if previous is not None:
            match(previous, SHA_PATTERN)
            old = directory(previous, parent=root)
            rollback = strict_json(_owned_bytes(old, 'release.json', 0, 0, 0o600, MAX_JSON_BYTES))
        validate_manifest(manifest, config, rollback)
        return manifest, config


def validate_installed_migration_tree(manifest):
    """Hash the staged released inputs, never execute SQL or the runner.

    Bootstrap must stage db/migrations/*.sql and scripts/dev/migrate_sql.sh
    inside the immutable selected release, root-owned mode0444. Every directory
    component is pinned without following symlinks; unexpected SQL entries fail.
    This proves local bytes only, not the running DB or migration image contents.
    """
    match(manifest['source_sha'], SHA_PATTERN)
    with ExitStack() as resources:
        def directory(path, parent=None):
            fd = _owned_directory(path, parent=parent)
            resources.callback(os.close, fd)
            return fd
        root = directory(RELEASE_ROOT)
        selected = directory(manifest['source_sha'], root)
        sql = directory('migrations', directory('db', selected))
        expected = manifest['migrations']['files']
        require(sorted(os.listdir(sql)) == [item['name'] for item in expected])
        for item in expected:
            content = _owned_bytes(sql, item['name'], 0, 0, 0o444, MAX_JSON_BYTES)
            require(hashlib.sha256(content).hexdigest() == item['sha256'])
        scripts = directory('dev', directory('scripts', selected))
        runner = _owned_bytes(scripts, 'migrate_sql.sh', 0, 0, 0o444, MAX_JSON_BYTES)
        require(hashlib.sha256(runner).hexdigest() == manifest['migrations']['runner_sha256'])
    return True


def validate_mount_observations(config, data, secrets):
    """Validate exact findmnt --mountpoint output; no ancestor-filesystem fallback."""
    validate_config(config)
    def filesystem(observation, target):
        exact_object(observation, ('filesystems',))
        require(type(observation['filesystems']) is list and len(observation['filesystems']) == 1)
        value = observation['filesystems'][0]
        exact_object(value, ('target', 'uuid', 'fstype', 'options'))
        require(value['target'] == target and type(value['options']) is str)
        options = value['options'].split(',')
        require('rw' in options and 'ro' not in options)
        return value, set(options)
    mounted, _ = filesystem(data, DATA_ROOT)
    require(mounted['uuid'] == config['resources']['data_disk_filesystem_uuid'])
    require(mounted['fstype'] in ('ext4', 'xfs'))
    temporary, options = filesystem(secrets, SECRET_ROOT)
    require(temporary['fstype'] == 'tmpfs' and temporary['uuid'] is None)
    require({'nosuid', 'nodev', 'noexec'} <= options)
    return True


def _opaque_secret(data, multiline=False, empty=False):
    require(type(data) is bytes and (0 if empty else 1) <= len(data) <= 16384)
    require(b'\x00' not in data and (multiline or (b'\r' not in data and b'\n' not in data)))
    require(re.fullmatch(rb'@@[A-Z_]+@@', data) is None)


def validate_runtime_secret_files():
    """Check normal-service file delivery, not credentials' remote permissions.

    Temporary migration/bootstrap/metrics jobs have separate lifecycles. Native
    NATS and S3 configs must retain their frozen rendered permission templates;
    values never enter process environment, logs or receipts here.
    """
    with ExitStack() as resources:
        root = _owned_directory(SECRET_ROOT, mode=0o700)
        resources.callback(os.close, root)
        for service in NORMAL_SERVICES:
            uid = 0 if service == 'caddy' else (999 if service == 'postgres' else 1000)
            directory = _owned_directory(service, uid, uid, 0o500, parent=root)
            resources.callback(os.close, directory)
            filenames = {'caddy': ('maintenance.caddy',), 'nats': ('nats.conf',), 'minio': ('s3.json',)}.get(service, SECRET_NAMES.get(service))
            require(set(os.listdir(directory)) == set(filenames))
            values = {name: _owned_bytes(directory, name, uid, uid, 0o400, empty=service == 'caddy') for name in filenames}
            for data in values.values(): _opaque_secret(data, multiline=service in ('nats', 'minio', 'caddy'), empty=service == 'caddy')
            if service == 'nats':
                template = (Path(__file__).parent / 'nats.conf.template').read_text()
                pattern = re.escape(template)
                for name in ('NATS_METRICS_USER', 'NATS_METRICS_PASSWORD'):
                    pattern = pattern.replace(re.escape('@@' + name + '@@'), r'([^"\\\x00-\x20]+)')
                matched = re.fullmatch(pattern, values['nats.conf'].decode('utf-8'))
                require(matched is not None)
                for value in matched.groups(): _opaque_secret(value.encode('utf-8'))
            elif service == 'minio':
                expected = strict_json((Path(__file__).parent / 'seaweedfs-s3.json.template').read_bytes())
                candidate = strict_json(values['s3.json'])
                exact_object(candidate, ('identities',))
                require(type(candidate['identities']) is list and len(candidate['identities']) == 2)
                keys = []
                for identity, template in zip(candidate['identities'], expected['identities']):
                    exact_object(identity, ('name', 'credentials', 'actions'))
                    require(type(identity['credentials']) is list and len(identity['credentials']) == 1)
                    credential = identity['credentials'][0]
                    exact_object(credential, ('accessKey', 'secretKey'))
                    for value in credential.values():
                        require(type(value) is str)
                        _opaque_secret(value.encode('utf-8'))
                    keys.append(credential['accessKey'])
                    identity['credentials'] = template['credentials']
                require(len(set(keys)) == 2 and canonical_bytes(candidate) == canonical_bytes(expected))
    return True


def deploy_cli(argv):
    """Bounded check-only stage. Every mutation verb remains unavailable.

    Partial local observations never certify start: service/no-work readiness and
    complete native credential-rights validation remain absent.
    """
    try:
        args = parse_helper_args('deploy.sh', argv)
    except ContractError:
        return 2, operation_receipt('deploy.sh check', None, None, 2, {}, 'invalid_input')
    if argv[0] != 'check':
        return 3, operation_receipt(args['operation'], args['source_sha'], None, 3, {'runtime_evidence': False}, 'missing_dependency')
    checks = {name: False for name in ('config', 'manifest', 'disk_uuid', 'metadata_guard', 'storage_guard',
                                      'secrets', 'cached_images', 'migration_tree', 'schema', 'services', 'runtime_evidence')}
    code, failure = 3, 'missing_dependency'
    try:
        require(os.geteuid() == 0)
        manifest, config = _installed_deploy_inputs(args['source_sha'])
        checks.update(config=True, manifest=True)
        # Validate existing directories without ever initializing boot-disk data.
        fd = _owned_directory(DATA_ROOT)
        os.close(fd)
        observations = []
        for target in (DATA_ROOT, SECRET_ROOT):
            result = subprocess.run(['/usr/bin/findmnt', '--json', '--list', '--mountpoint', target, '--output', 'TARGET,UUID,FSTYPE,OPTIONS'],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=5, check=False, cwd='/', env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'})
            require(result.returncode == 0)
            observations.append(strict_json(result.stdout))
        validate_mount_observations(config, *observations)
        checks['disk_uuid'] = True
        guard_code, guard = guard_cli()
        if guard_code != 0:
            return guard_code, operation_receipt(args['operation'], args['source_sha'], None, guard_code, checks, guard['failure_code'])
        checks.update(metadata_guard=True, storage_guard=True)
        validate_runtime_secret_files()
        checks['secrets'] = True
        collect_cached_images(manifest)
        checks['cached_images'] = True
        validate_installed_migration_tree(manifest)
        checks['migration_tree'] = True
        collect_postgres_schema(manifest)
        checks['schema'] = True
        # Intentionally retain missing_dependency/exit3 even when all above pass.
    except subprocess.TimeoutExpired:
        code, failure = 5, 'operation_timed_out'
    except (OSError, ContractError, UnicodeError):
        pass
    return code, operation_receipt(args['operation'], args['source_sha'], None, code, checks, failure)


def cli(argv):
    if argv == ['guard']:
        return guard_cli()
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
