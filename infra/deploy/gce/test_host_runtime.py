"""Offline v1 contract and disposable local script tests; no daemon/network."""
import copy
import hashlib
import importlib.util
import json
import os
import ipaddress
import shlex
import re
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SHA = 'a' * 40
HEX = 'b' * 64


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_runtime():
    path = HERE / 'runtime-check.py'
    if not path.is_file():
        raise AssertionError('v1 passive contract implementation is missing')
    spec = importlib.util.spec_from_file_location('host_runtime', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContractTests(unittest.TestCase):
    def setUp(self):
        # Any attempt by the implementation to execute/probe escapes this pure gate.
        self.guards = [patch.object(subprocess, 'Popen', side_effect=AssertionError('subprocess forbidden')),
                       patch.object(socket, 'socket', side_effect=AssertionError('network forbidden'))]
        for guard in self.guards:
            guard.start()
            self.addCleanup(guard.stop)
        self.rt = load_runtime()
        expected_secrets = {
            'api': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY', 'AUTODATA_INGESTION_INTERNAL_TOKEN', 'AUTODATA_IMAGE_URL_KEY'),
            'ingestion-http': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY', 'AUTODATA_INGESTION_INTERNAL_TOKEN', 'AUTODATA_STRIPE_SECRET_KEY', 'AUTODATA_STRIPE_WEBHOOK_SECRET', 'BANKONE_API_TOKEN', 'BANKTWO_API_TOKEN'),
            'article-worker': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY', 'BANKONE_API_TOKEN', 'BANKTWO_API_TOKEN', 'INCEPTION_API_KEY'),
            'payment-reconciler': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_INGESTION_INTERNAL_TOKEN', 'AUTODATA_STRIPE_SECRET_KEY', 'AUTODATA_STRIPE_WEBHOOK_SECRET'),
            'postgres': ('POSTGRES_PASSWORD',), 'nats': ('NATS_METRICS_USER', 'NATS_METRICS_PASSWORD'),
            'minio': ('S3_WORKER_ACCESS_KEY', 'S3_WORKER_SECRET_KEY', 'S3_API_ACCESS_KEY', 'S3_API_SECRET_KEY'),
            'migration': ('PGPASSWORD',), 'bootstrap': ('AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY'),
            'metrics-probe': ('AUTODATA_POSTGRES_PASSWORD', 'NATS_METRICS_USER', 'NATS_METRICS_PASSWORD')}
        self.config = {
            'schema_version': 2, 'environment': 'staging', 'public_origin': 'https://staging.cars.example',
            'firebase': {'project_id': 'firebase-stage', 'web_api_key': 'public-web-key',
                         'web_app_id': '1:123456:web:abcdef', 'auth_domain': 'firebase-stage.firebaseapp.com'},
            'resources': {'host_project_id': 'autodata-host', 'backup_project_id': 'autodata-backup',
                          'region': 'us-central1', 'zone': 'us-central1-a', 'instance_name': 'workshop-stage',
                          'data_disk_name': 'workshop-data', 'data_disk_filesystem_uuid': '12345678-1234-4234-8234-123456789abc',
                          'static_ip_name': 'workshop-ip', 'artifact_repository': 'us-central1-docker.pkg.dev/autodata-host/workshop',
                          'backup_bucket': 'autodata-private-backup', 'acme_email': 'ops@example.com'},
            'workshop_purchase_config': {'enabled': False, 'terms_version': 'workshop-v1',
                                         'terms_url': None, 'privacy_url': None, 'refund_url': None,
                                         'contact_url': None, 'tax_notice': None},
            'topology': copy.deepcopy(self.rt.TOPOLOGY), 'commands': copy.deepcopy(self.rt.COMMANDS),
            'tuning': {'bankone_base_url': 'https://bankone.example', 'banktwo_base_url': 'https://banktwo.example',
                       'inception_api_base_url': 'https://model.example/v1', 'inception_model': 'mercury-2',
                       'inception_api_timeout_seconds': 45, 'stripe_account_id': 'acct_test123',
                       'stripe_price_id': 'price_test123', 'source_http_timeout_seconds': 30,
                       'source_max_bytes': 52428800, 'mercury2_extraction_enabled': False,
                       'mercury2_job_plans_enabled': True, 'mercury2_procedure_composition_enabled': True}}
        files = [{'name': '001_initial.sql', 'sha256': HEX}, {'name': '002_next.sql', 'sha256': HEX}]
        self.manifest = {
            'schema_version': 1, 'source_sha': SHA, 'platform': 'linux/amd64',
            'images': {role: {'reference': 'registry.example/autodata/' + role + '@sha256:' + HEX,
                              'image_id': 'sha256:' + 'c' * 64,
                              'provenance_uri': 'https://artifacts.example/provenance@sha256:' + HEX,
                              'sbom_uri': 'https://artifacts.example/sbom@sha256:' + HEX}
                       for role in ('api', 'ingestion', 'migration', 'caddy', 'postgres', 'nats', 'minio')},
            'migrations': {'runner_sha256': HEX, 'files': files, 'inventory_sha256': digest(files)},
            'toolchain': {tool: {'version': version, 'package_sha256': HEX}
                          for tool, version in [('docker_engine', '28.5.1'), ('docker_compose', '2.40.3')]},
            'service_config_sha256': digest(self.config),
            'secret_versions': {service: {name: 'projects/autodata-host/secrets/' + service + '-' + name.lower().replace('_', '-') + '/versions/1'
                                         for name in names} for service, names in expected_secrets.items()},
            'rollback_source_sha': None}
        for role in ('api', 'ingestion', 'migration'):
            self.manifest['images'][role]['reference'] = 'us-central1-docker.pkg.dev/autodata-host/workshop/' + role + '@sha256:' + HEX
        self.manifest['images']['minio']['reference'] = 'ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d'
        self.manifest['images']['minio']['image_id'] = 'sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5'

        self.manifest['secret_versions']['ingestion-http']['AUTODATA_INGESTION_INTERNAL_TOKEN'] = self.manifest['secret_versions']['api']['AUTODATA_INGESTION_INTERNAL_TOKEN']

    def rejected_manifest(self, mutate):
        candidate = copy.deepcopy(self.manifest)
        mutate(candidate)
        with self.assertRaises(self.rt.ContractError):
            self.rt.validate_manifest(candidate, self.config)

    def test_host_v2_requires_explicit_closed_purchase_object(self):
        self.assertEqual(self.rt.validate_config(self.config), digest(self.config))
        for mutate in (lambda c: c.update(schema_version=1),
                       lambda c: c.pop('workshop_purchase_config'),
                       lambda c: c.update(workshop_purchase_config=None),
                       lambda c: c.update(workshop_purchase_config='disabled'),
                       lambda c: c['workshop_purchase_config'].pop('tax_notice'),
                       lambda c: c['workshop_purchase_config'].update(extra=False),
                       lambda c: c['workshop_purchase_config'].update(enabled=0),
                       lambda c: c['workshop_purchase_config'].update(terms_version='other'),
                       lambda c: c['workshop_purchase_config'].update(tax_notice='disabled')):
            candidate = copy.deepcopy(self.config); mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(self.rt.ContractError):
                self.rt.validate_config(candidate)

    def test_enabled_purchase_config_validates_notices_and_raw_https_urls(self):
        enabled = {'enabled': True, 'terms_version': 'workshop-v1',
                   'terms_url': 'https://example.com/terms', 'privacy_url': 'https://example.com/privacy',
                   'refund_url': 'https://example.com/refund', 'contact_url': 'https://example.com/contact',
                   'tax_notice': 'Synthetic USD20 notice'}
        candidate = copy.deepcopy(self.config); candidate['workshop_purchase_config'] = enabled
        self.rt.validate_config(candidate)
        for key, value in (('enabled', 1), ('tax_notice', None), ('tax_notice', '  '),
                           ('tax_notice', 'line\nline'), ('tax_notice', '\ud800'),
                           ('terms_url', ' https://example.com'), ('terms_url', 'https://127.0.0.1'),
                           ('terms_url', 'https://example.com?x=1'), ('terms_url', 'https://example.com:444'),
                           ('terms_url', 'https://example.com/%bad%'), ('terms_url', None)):
            changed = copy.deepcopy(candidate); changed['workshop_purchase_config'][key] = value
            with self.subTest(key=key, value=repr(value)), self.assertRaises(self.rt.ContractError):
                self.rt.validate_config(changed)

    def test_private_authority_requires_same_numeric_token_reference(self):
        self.rt.validate_manifest(self.manifest, self.config)
        for value in ('projects/autodata-host/secrets/other/versions/1',
                      'projects/autodata-host/secrets/api-autodata-ingestion-internal-token/versions/2'):
            self.rejected_manifest(lambda m: m['secret_versions']['ingestion-http'].update(
                AUTODATA_INGESTION_INTERNAL_TOKEN=value))

    def test_valid_manifest_has_stable_canonical_digest(self):
        self.assertEqual(self.rt.validate_manifest(self.manifest, self.config), digest(self.manifest))
        self.assertEqual(self.rt.canonical_bytes({'z': 1, 'a': [True, None]}), b'{"a":[true,null],"z":1}')

    def test_json_rejects_duplicate_nonfinite_and_oversize_input(self):
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b' ' * (1048576 + 1), b'\xff'):
            with self.subTest(data=data[:30]), self.assertRaises(self.rt.ContractError):
                self.rt.strict_json(data)

    def test_unknown_fields_and_wrong_scalar_types_rejected(self):
        mutations = [lambda m: m.update(extra=True), lambda m: m['images']['api'].update(extra=True),
                     lambda m: m['migrations'].update(extra=True), lambda m: m['toolchain']['docker_engine'].update(extra=True),
                     lambda m: m.update(schema_version=True), lambda m: m.update(platform='linux/arm64'),
                     lambda m: m.update(source_sha='../' + SHA), lambda m: m.update(source_sha=SHA.upper())]
        for mutation in mutations:
            with self.subTest(mutation=mutation): self.rejected_manifest(mutation)

    def test_immutable_images_and_artifact_references_only(self):
        for key, value in [('reference', 'postgres:17'), ('reference', 'registry.example/a:latest@sha256:' + HEX),
                           ('reference', 'registry.example/a@sha256:' + HEX.upper()), ('image_id', HEX),
                           ('sbom_uri', 'https://artifacts.example/latest'), ('provenance_uri', 'file:///tmp/a'),
                           ('sbom_uri', 'https://user:password@artifacts.example/a@sha256:' + HEX)]:
            with self.subTest(key=key, value=value):
                self.rejected_manifest(lambda m: m['images']['api'].update({key: value}))

    def test_migration_inventory_contiguous_and_bound(self):
        for replacement in ([], [{'name': '002_gap.sql', 'sha256': HEX}],
                            [{'name': '001_a.sql', 'sha256': HEX}, {'name': '001_b.sql', 'sha256': HEX}],
                            [{'name': '../001_a.sql', 'sha256': HEX}]):
            def mutate(m):
                m['migrations']['files'] = replacement
                m['migrations']['inventory_sha256'] = digest(replacement)
            self.rejected_manifest(mutate)
        self.rejected_manifest(lambda m: m['migrations'].update(inventory_sha256='0' * 64))

    def test_actual_migration_bytes_and_schema_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            sql = base / 'sql'; sql.mkdir()
            runner = base / 'runner.sh'; runner.write_bytes(b'run\n')
            names = ['001_initial.sql', '002_next.sql']
            for name in names: (sql / name).write_bytes(name.encode())
            manifest = copy.deepcopy(self.manifest)
            files = [{'name': name, 'sha256': hashlib.sha256(name.encode()).hexdigest()} for name in names]
            manifest['migrations'] = {'files': files, 'inventory_sha256': digest(files), 'runner_sha256': hashlib.sha256(b'run\n').hexdigest()}
            self.rt.validate_migration_tree(manifest, sql, runner, actual_schema=2)
            for schema in (1, 3, True):
                with self.assertRaises(self.rt.ContractError): self.rt.validate_migration_tree(manifest, sql, runner, actual_schema=schema)
            (sql / names[0]).write_bytes(b'tampered')
            with self.assertRaises(self.rt.ContractError): self.rt.validate_migration_tree(manifest, sql, runner, actual_schema=2)
            (sql / names[0]).unlink(); (sql / names[0]).symlink_to(runner)
            with self.assertRaises(self.rt.ContractError): self.rt.validate_migration_tree(manifest, sql, runner, actual_schema=2)

    def test_schema_ledger_requires_exact_version_inventory_and_order(self):
        observation = {'version': 2, 'migrations': ['001_initial', '002_next']}
        self.assertTrue(callable(getattr(self.rt, 'validate_schema_ledger', None)), 'schema ledger validator missing')
        self.assertTrue(self.rt.validate_schema_ledger(self.manifest, observation))
        for candidate in ({'version': True, 'migrations': observation['migrations']},
                          {'version': 1, 'migrations': observation['migrations']},
                          {'version': 2, 'migrations': ['001_initial', '002_other']},
                          {'version': 2, 'migrations': ['002_next', '001_initial']},
                          {'version': 2, 'migrations': ['001_initial', '001_initial']},
                          {'version': 2, 'migrations': ['001_initial']},
                          {'version': 2, 'migrations': ['001_initial', '002_next', '003_future']},
                          dict(observation, extra=True), {'version': 2, 'migrations': None}):
            with self.subTest(candidate=candidate), self.assertRaises(self.rt.ContractError):
                self.rt.validate_schema_ledger(self.manifest, candidate)

    def test_secret_version_maps_reject_aliases_unknown_and_missing(self):
        service = 'api'; name = 'AUTODATA_POSTGRES_PASSWORD'
        for value in ('projects/autodata-host/secrets/db/versions/latest', 'projects/autodata-host/secrets/db/versions/0',
                      'projects/<project>/secrets/db/versions/1', 'fake-secret-value'):
            self.rejected_manifest(lambda m: m['secret_versions'][service].update({name: value}))
        self.rejected_manifest(lambda m: m['secret_versions']['article-worker'].update(AUTODATA_STRIPE_SECRET_KEY='projects/x/secrets/y/versions/1'))
        self.rejected_manifest(lambda m: m['secret_versions']['api'].pop(name))

    def test_config_hash_and_origin_bind_environment(self):
        changed = copy.deepcopy(self.config); changed['tuning']['inception_model'] = 'other-model'
        with self.assertRaises(self.rt.ContractError): self.rt.validate_manifest(self.manifest, changed)
        for origin in ('http://staging.example', 'https://user:pw@staging.example', 'https://localhost',
                       'https://staging.example/path', 'https://staging.example?token=x', 'https://cars.tk'):
            changed = copy.deepcopy(self.config); changed['public_origin'] = origin
            with self.subTest(origin=origin), self.assertRaises(self.rt.ContractError): self.rt.validate_config(changed)
        production = copy.deepcopy(self.config); production.update(environment='production', public_origin='https://cars.tk')
        self.rt.validate_config(production)

    def test_config_rejects_ambient_aliases_dynamic_graph_and_secret_values(self):
        for mutate in (lambda c: c.update(GOOGLE_APPLICATION_CREDENTIALS='/tmp/key'),
                       lambda c: c['tuning'].update(BANKONE_API_TOKEN='secret'),
                       lambda c: c['topology']['edge'].update(subnet='10.0.0.0/8'),
                       lambda c: c['commands']['api'].append('--fake'),
                       lambda c: c['resources'].update(data_disk_filesystem_uuid='../disk'),
                       lambda c: c['tuning'].update(bankone_base_url='https://bankone.example?token=secret')):
            config = copy.deepcopy(self.config); mutate(config)
            with self.assertRaises(self.rt.ContractError): self.rt.validate_config(config)

    def test_rollback_requires_existing_compatible_manifest(self):
        candidate = copy.deepcopy(self.manifest); candidate['rollback_source_sha'] = 'd' * 40
        with self.assertRaises(self.rt.ContractError): self.rt.validate_manifest(candidate, self.config)
        previous = copy.deepcopy(self.manifest); previous['source_sha'] = 'd' * 40
        self.rt.validate_manifest(candidate, self.config, rollback_manifest=previous)
        previous['service_config_sha256'] = '0' * 64
        with self.assertRaises(self.rt.ContractError): self.rt.validate_manifest(candidate, self.config, rollback_manifest=previous)

    def test_rollback_images_reject_foreign_registry_and_wrong_role(self):
        candidate = copy.deepcopy(self.manifest); candidate['rollback_source_sha'] = 'd' * 40
        for role in ('api', 'ingestion', 'migration'):
            references = ['attacker.example/autodata/' + role + '@sha256:' + HEX,
                          'us-central1-docker.pkg.dev/autodata-host/workshop/wrong-role@sha256:' + HEX]
            for reference in references:
                previous = copy.deepcopy(self.manifest); previous['source_sha'] = 'd' * 40
                previous['images'][role]['reference'] = reference
                with self.subTest(role=role, reference=reference), self.assertRaises(self.rt.ContractError):
                    self.rt.validate_manifest(candidate, self.config, rollback_manifest=previous)

    def test_rollback_artifacts_require_same_https_authority_checks(self):
        candidate = copy.deepcopy(self.manifest); candidate['rollback_source_sha'] = 'd' * 40
        # These digest-pinned locators pass schema syntax but violate _https.
        locations = ['https://localhost/artifact@sha256:', 'https://127.0.0.1/artifact@sha256:',
                     'https://-invalid.example/artifact@sha256:', 'https://artifacts.example/a\\b@sha256:']
        for role in ('api', 'ingestion', 'migration', 'caddy', 'postgres', 'nats', 'minio'):
            for field in ('provenance_uri', 'sbom_uri'):
                for location in locations:
                    previous = copy.deepcopy(self.manifest); previous['source_sha'] = 'd' * 40
                    previous['images'][role][field] = location + HEX
                    with self.subTest(role=role, field=field, location=location), self.assertRaises(self.rt.ContractError):
                        self.rt.validate_manifest(candidate, self.config, rollback_manifest=previous)

    def test_rollback_compatibility_checks_source_config_platform_and_sql(self):
        candidate = copy.deepcopy(self.manifest); candidate['rollback_source_sha'] = 'd' * 40
        for field, value in [('source_sha', 'e' * 40), ('service_config_sha256', '0' * 64),
                             ('platform', 'linux/arm64')]:
            previous = copy.deepcopy(self.manifest); previous['source_sha'] = 'd' * 40
            previous[field] = value
            with self.subTest(field=field), self.assertRaises(self.rt.ContractError):
                self.rt.validate_manifest(candidate, self.config, rollback_manifest=previous)
        previous = copy.deepcopy(self.manifest); previous['source_sha'] = 'd' * 40
        previous['migrations']['runner_sha256'] = '0' * 64
        with self.assertRaises(self.rt.ContractError):
            self.rt.validate_manifest(candidate, self.config, rollback_manifest=previous)

    def test_rollback_validation_does_not_require_historical_chain(self):
        candidate = copy.deepcopy(self.manifest); candidate['rollback_source_sha'] = 'd' * 40
        previous = copy.deepcopy(self.manifest)
        previous.update(source_sha='d' * 40, rollback_source_sha='e' * 40)
        self.assertEqual(self.rt.validate_manifest(candidate, self.config, rollback_manifest=previous), digest(candidate))

    def test_render_has_fixed_graph_and_only_caddy_publishes(self):
        bundle = self.rt.render_bundle(self.manifest, self.config)
        compose = json.loads(bundle['compose.production.yaml'])
        services = compose['services']
        self.assertEqual(set(services), {'caddy', 'api', 'ingestion-http', 'article-worker', 'payment-reconciler', 'postgres', 'nats', 'minio', 'migration', 'bootstrap', 'metrics-probe'})
        for name, service in services.items():
            self.assertNotIn('build', service); self.assertNotIn('env_file', service)
            self.assertEqual(service['platform'], 'linux/amd64')
            self.assertEqual(service['cap_drop'], ['ALL'])
            self.assertEqual(service['security_opt'], ['no-new-privileges:true'])
            self.assertTrue(service['read_only'])
            if name != 'caddy': self.assertNotIn('ports', service)
        self.assertEqual(services['caddy']['ports'], ['80:80/tcp', '443:443/tcp', '443:443/udp'])
        self.assertEqual(set(compose['networks']), {'edge', 'backend', 'workers-egress'})
        self.assertEqual(services['minio']['networks'], {'backend': {'ipv4_address': '172.30.20.40'}})
        self.assertEqual(services['api']['networks']['edge'], {'ipv4_address': '172.30.10.10', 'gw_priority': 100})
        self.assertTrue(compose['networks']['backend']['internal'])
        self.assertEqual(compose['networks']['backend']['driver_opts']['com.docker.network.bridge.name'], 'br-ad-back')
        for network in compose['networks'].values(): self.assertFalse(network['enable_ipv6'])
        self.assertEqual(compose['x-autodata-prerequisites'], {'disk_uuid': '12345678-1234-4234-8234-123456789abc', 'metadata_guard': 'required', 'storage_guard': 'required', 'tmpfs_secrets': 'required', 'cached_images': 'required'})

    def test_rendered_commands_and_secret_mounts_do_not_persist_secret_values(self):
        with patch.dict(os.environ, {'AUTODATA_POSTGRES_PASSWORD': 'FAKE_SECRET_NEVER_RENDER', 'API_IMAGE': 'evil:latest'}, clear=False):
            bundle = self.rt.render_bundle(self.manifest, self.config)
        serialized = json.dumps(bundle)
        self.assertNotIn('FAKE_SECRET_NEVER_RENDER', serialized); self.assertNotIn('evil:latest', serialized)
        self.assertNotIn('${', serialized)
        compose = json.loads(bundle['compose.production.yaml'])
        for name, service in compose['services'].items():
            for secret in self.rt.SECRET_NAMES.get(name, ()):
                self.assertNotIn(secret, service.get('environment', {}))
            for mount in service['volumes']:
                self.assertIsInstance(mount, dict)
                self.assertFalse(mount.get('bind', {}).get('create_host_path', True))
                self.assertNotIn(mount['source'], ('/run/autodata', '/var/run/docker.sock', '/home', '/root'))
        self.assertEqual(compose['services']['api']['command'], ['/usr/local/bin/autodata-api'])
        self.assertEqual(compose['services']['ingestion-http']['command'], ['python', '-m', 'autodata_ingestion.http_service'])
        self.assertEqual(compose['services']['article-worker']['command'], ['python', '-c', 'from autodata_ingestion.worker import article_worker_main; raise SystemExit(article_worker_main())'])
        self.assertEqual(compose['services']['migration']['command'], ['sh', '/release/scripts/dev/migrate_sql.sh', '--migrations-dir', '/release/db/migrations'])
        self.assertEqual(compose['services']['payment-reconciler']['command'], ['python', '/app/scripts/reconcile_payments.py', '--poll-seconds', '15', '--batch-size', '50'])
        self.assertEqual(compose['services']['api']['environment']['AUTODATA_COMMERCE_MODE'], 'stripe_test')
        self.assertNotIn('INCEPTION_API_KEY', compose['services']['ingestion-http']['environment'])

    def test_templates_keep_sensitive_configs_private(self):
        bundle = self.rt.render_bundle(self.manifest, self.config)
        self.assertIn('unix//run/caddy/admin.sock', bundle['Caddyfile'])
        self.assertIn('output discard', bundle['Caddyfile'])
        self.assertIn('import /run/autodata/caddy/maintenance.caddy', bundle['Caddyfile'])
        self.assertIn('http://api:8080', bundle['Caddyfile'])
        self.assertNotIn('no_auth_user', bundle['nats.conf.template'])
        s3 = json.loads(bundle['seaweedfs-s3.json.template'])
        self.assertEqual([i['name'] for i in s3['identities']], ['worker', 'api'])
        self.assertEqual(s3['identities'][1]['actions'], ['Read:autodata-sources'])
        self.assertNotIn('Admin', json.dumps(s3))

    def test_helper_parsers_validate_count_and_identifiers(self):
        valid = [('deploy.sh', ['check', SHA]), ('backup-host.sh', ['status', '12345678-1234-4234-8234-123456789abc']),
                 ('restore.sh', ['validate', '12345678-1234-4234-8234-123456789abc']),
                 ('runtime-check.py', ['metrics', '--release', SHA])]
        for helper, args in valid: self.rt.parse_helper_args(helper, args)
        for helper, args in valid:
            for bad in (args + ['extra'], [], ['unknown'] + args[1:], args[:-1] + ['../../etc/passwd']):
                with self.assertRaises(self.rt.ContractError): self.rt.parse_helper_args(helper, bad)

    def test_runtime_cli_fails_closed_without_probing(self):
        for argv in (['check', '--release', SHA], ['metrics', '--release', SHA], ['check', '--release', SHA, '--config', '/tmp/config']):
            code, output = self.rt.cli(argv)
            self.assertIn(code, (2, 3)); self.assertNotEqual(output.get('status'), 'passed')
            self.assertNotIn('passed', output.get('checks', {}))
            self.assertLess(len(json.dumps(output)), 65536)

    def test_metrics_reject_dynamic_labels_nonfinite_and_wrong_units(self):
        data = [{'name': 'disk_free_bytes', 'value': 1234, 'unit': 'By', 'state': 'ok'}]
        result = self.rt.metrics_receipt(SHA, data)
        self.assertEqual(result['metrics'], data)
        for changed in ([dict(data[0], value=float('nan'))], [dict(data[0], value=True)],
                        [dict(data[0], name='customer_123')], [dict(data[0], unit='seconds')],
                        [dict(data[0], token='secret')], data + data):
            with self.assertRaises(self.rt.ContractError): self.rt.metrics_receipt(SHA, changed)
        self.assertEqual(self.rt.metrics_receipt(SHA, [])['metrics'], [])

    def test_release_images_bind_reviewed_registry_and_seaweed_pin(self):
        self.rejected_manifest(lambda m: m['images']['api'].update(reference='attacker.example/api@sha256:' + HEX))
        self.rejected_manifest(lambda m: m['images']['minio'].update(image_id='sha256:' + HEX))
        self.rejected_manifest(lambda m: m['images']['minio'].update(reference='ghcr.io/chrislusf/seaweedfs@sha256:' + HEX))

    def test_cached_images_require_platform_reference_and_local_identity(self):
        self.assertTrue(callable(getattr(self.rt, 'validate_cached_images', None)), 'cached identity validator missing')
        observed = {name: {'reference': image['reference'], 'image_id': image['image_id'], 'platform': 'linux/amd64'}
                    for name, image in self.manifest['images'].items()}
        self.rt.validate_cached_images(self.manifest, observed)
        for field, value in [('reference', 'evil:latest'), ('image_id', 'sha256:' + '0' * 64), ('platform', 'linux/arm64')]:
            changed = copy.deepcopy(observed); changed['api'][field] = value
            with self.assertRaises(self.rt.ContractError): self.rt.validate_cached_images(self.manifest, changed)
        observed.pop('minio')
        with self.assertRaises(self.rt.ContractError): self.rt.validate_cached_images(self.manifest, observed)

    def test_secure_config_read_rejects_symlinks_and_wrong_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'host.json'
            path.write_text('{"ok":true}'); path.chmod(0o600)
            self.assertEqual(self.rt.read_private_json(path, owner_uid=os.getuid()), {'ok': True})
            path.chmod(0o644)
            with self.assertRaises(self.rt.ContractError): self.rt.read_private_json(path, owner_uid=os.getuid())
            path.chmod(0o600)
            link = Path(directory) / 'link.json'; link.symlink_to(path)
            with self.assertRaises(self.rt.ContractError): self.rt.read_private_json(link, owner_uid=os.getuid())
            with self.assertRaises(self.rt.ContractError): self.rt.read_private_json(path, owner_uid=os.getuid() + 1)

    def test_missing_or_wrong_guard_disk_secrets_prevent_start_approval(self):
        self.assertTrue(callable(getattr(self.rt, 'validate_start_prerequisites', None)), 'prerequisite validator missing')
        evidence = {'disk_uuid': '12345678-1234-4234-8234-123456789abc', 'data_mount': '/var/lib/autodata',
                    'metadata_guard': True, 'storage_guard': True, 'tmpfs_secrets': True, 'cached_images': True}
        self.rt.validate_start_prerequisites(self.config, evidence)
        for key in ('metadata_guard', 'storage_guard', 'tmpfs_secrets', 'cached_images'):
            bad = dict(evidence); bad[key] = False
            with self.assertRaises(self.rt.ContractError): self.rt.validate_start_prerequisites(self.config, bad)
        for key, value in [('disk_uuid', '87654321-1234-4234-8234-123456789abc'), ('data_mount', '/')]:
            bad = dict(evidence); bad[key] = value
            with self.assertRaises(self.rt.ContractError): self.rt.validate_start_prerequisites(self.config, bad)
        with self.assertRaises(self.rt.ContractError): self.rt.validate_start_prerequisites(self.config, {})

    def test_receipts_reject_unknown_checks_and_inconsistent_success(self):
        for code, checks, failure in [(0, {'disk_uuid': False}, None), (4, {}, None),
                                      (0, {'secret_value': True}, None), (0, {'disk_uuid': 1}, None)]:
            with self.assertRaises(self.rt.ContractError):
                self.rt.operation_receipt('deploy.sh check', SHA, None, code, checks, failure)
        for code, failure, status in [(2, 'invalid_input', 'failed'), (3, 'missing_dependency', 'failed'),
                                      (4, 'operation_failed', 'failed'), (5, 'operation_timed_out', 'timed_out'),
                                      (6, 'recovery_incomplete', 'incomplete')]:
            receipt = self.rt.operation_receipt('deploy.sh check', SHA, None, code, {}, failure)
            self.assertEqual(receipt['status'], status)
            self.assertEqual(set(receipt), {'schema_version', 'operation', 'run_id', 'source_sha', 'status',
                                            'started_at', 'finished_at', 'checks', 'failure_code'})

    def test_schema_enumerates_exact_nested_fields(self):
        schema = self.rt.strict_json((HERE / 'release.schema.json').read_bytes())
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(set(schema['required']), set(self.manifest))
        def walk(value):
            if isinstance(value, dict):
                if value.get('type') == 'object': self.assertFalse(value['additionalProperties'])
                for child in value.values(): walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(schema)



class EntrypointTests(unittest.TestCase):
    """Run only a copied wrapper and a harmless local Python child in a temp tree.

    The sole rewritten literal is the fixed secret root; production has no path
    override. No container, daemon, endpoint, credential or provider is used.
    """
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.cleanup_tree)
        self.base = Path(self.temp.name)
        self.secret_root = self.base / 'secrets'; self.secret_root.mkdir(mode=0o700)
        self.script = self.base / 'entrypoint.sh'
        source = HERE / 'runtime-entrypoint.sh'
        self.assertTrue(source.is_file(), 'secret entrypoint is missing')
        text = source.read_text()
        self.assertEqual(text.count('secret_root=/run/autodata'), 1)
        self.script.write_text(text.replace('secret_root=/run/autodata', 'secret_root=' + str(self.secret_root)))
        self.rt = load_runtime()

    def cleanup_tree(self):
        for base, directories, _ in os.walk(self.temp.name):
            Path(base).chmod(0o700)
        self.temp.cleanup()

    def provision(self, service):
        directory = self.secret_root / service; directory.mkdir(mode=0o700)
        values = {name: 'opaque-$()`;"\\-value' for name in self.rt.SECRET_NAMES[service]}
        for name, value in values.items():
            path = directory / name; path.write_text(value); path.chmod(0o400)
        directory.chmod(0o500)
        return directory, values

    def run_script(self, service='api', extra=None, command=None):
        env = {'PATH': '/usr/bin:/bin', 'AUTODATA_RUNTIME_SERVICE': service,
               'AUTODATA_ENV': 'production', 'AUTODATA_PUBLIC_ORIGIN': 'https://cars.tk'}
        env.update(extra or {})
        child = command or ['/usr/bin/python', '-c', 'import os,json; print(json.dumps(dict(os.environ)))']
        return subprocess.run(['/bin/sh', str(self.script), *child], env=env,
                              capture_output=True, text=True, timeout=5)

    def test_each_service_loads_literal_approved_values_and_executes_child(self):
        for service in ('api', 'ingestion-http', 'article-worker', 'payment-reconciler', 'migration', 'bootstrap', 'metrics-probe'):
            with self.subTest(service=service):
                _, values = self.provision(service)
                result = self.run_script(service)
                self.assertEqual(result.returncode, 0, result.stderr)
                env = json.loads(result.stdout)
                self.assertEqual({name: env[name] for name in values}, values)
                self.assertEqual(env['AUTODATA_PUBLIC_ORIGIN'], 'https://cars.tk')
                self.assertEqual(result.stderr, '')
                for names in self.rt.SECRET_NAMES.values():
                    for name in names:
                        if name not in values: self.assertNotIn(name, env)

    def test_rejects_missing_extra_empty_multiline_nul_and_oversize_files(self):
        directory, _ = self.provision('api')
        target = directory / 'AUTODATA_POSTGRES_PASSWORD'
        for data in (b'', b'line\nline', b'trailing\n', b'cr\rvalue', b'nul\x00value', b'x' * 16385):
            with self.subTest(data=data[:20]):
                target.chmod(0o600); target.write_bytes(data); target.chmod(0o400)
                result = self.run_script()
                self.assertEqual(result.returncode, 3)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr, 'runtime entrypoint: invalid secret files\n')
        target.chmod(0o600); target.write_bytes(b'ok'); target.chmod(0o400)
        directory.chmod(0o700); target.unlink(); directory.chmod(0o500)
        self.assertEqual(self.run_script().returncode, 3)
        directory.chmod(0o700); target.write_bytes(b'ok'); target.chmod(0o400)
        extra = directory / '.unexpected'; extra.write_bytes(b'do-not-print'); directory.chmod(0o500)
        self.assertEqual(self.run_script().returncode, 3)

    def test_rejects_symlinks_hardlinks_wrong_mode_and_wrong_directory(self):
        directory, _ = self.provision('api')
        target = directory / 'AUTODATA_POSTGRES_PASSWORD'
        directory.chmod(0o700); target.unlink()
        outside = self.base / 'outside'; outside.write_bytes(b'private'); outside.chmod(0o400)
        target.symlink_to(outside); directory.chmod(0o500)
        self.assertEqual(self.run_script().returncode, 3)
        directory.chmod(0o700); target.unlink(); os.link(outside, target); directory.chmod(0o500)
        self.assertEqual(self.run_script().returncode, 3)
        directory.chmod(0o700); target.unlink(); target.write_bytes(b'private'); target.chmod(0o644); directory.chmod(0o500)
        self.assertEqual(self.run_script().returncode, 3)
        target.chmod(0o400); directory.chmod(0o777)
        self.assertEqual(self.run_script().returncode, 3)
        directory.chmod(0o700); moved = self.secret_root / 'moved'; directory.rename(moved); directory.symlink_to(moved)
        self.assertEqual(self.run_script().returncode, 3)

    def test_rejects_ambient_credentials_aliases_and_unknown_service(self):
        self.provision('api')
        for name in ('AUTODATA_POSTGRES_PASSWORD', 'INCEPTION_API_KEY', 'BANKONE_API_TOKEN',
                     'AUTODATA_BANKONE_API_KEY', 'AUTODATA_BANKTWO_API_KEY', 'GOOGLE_APPLICATION_CREDENTIALS',
                     'CLOUDSDK_AUTH_ACCESS_TOKEN', 'AUTODATA_READINESS_MODE', 'FIREBASE_AUTH_EMULATOR_HOST',
                     'GOOGLE_API_KEY', 'AWS_SECRET_ACCESS_KEY', 'AUTODATA_STRIPE_SECRET_KEY'):
            with self.subTest(name=name):
                result = self.run_script(extra={name: 'do-not-print'})
                self.assertEqual(result.returncode, 2)
                self.assertNotIn('do-not-print', result.stdout + result.stderr)
        for service in ('', '../api', 'postgres', 'unknown'):
            with self.subTest(service=service): self.assertEqual(self.run_script(service).returncode, 2)
        self.assertEqual(self.run_script(command=[]).returncode, 0)
        result = subprocess.run(['/bin/sh', str(self.script)], env={'AUTODATA_RUNTIME_SERVICE':'api'}, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2)

    def test_migration_build_rejects_floating_base_and_wrong_pg_client(self):
        definition = HERE / 'migration.Dockerfile'
        self.assertTrue(definition.is_file())
        lines = definition.read_text().splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith('RUN '))
        command = lines[start][4:]
        while command.endswith('\\'):
            start += 1
            command = command[:-1] + lines[start]
        fake = self.base / 'psql'
        fake.write_text('#!/bin/sh\nprintf "%s\\n" "$FAKE_VERSION"\n'); fake.chmod(0o755)
        for reference, version, valid in (
            ('postgres:17', 'psql (PostgreSQL) 17.6', False),
            ('registry.example/pg@sha256:' + 'a'*64, 'psql (PostgreSQL) 16.9', False),
            ('registry.example/pg@sha256:' + 'a'*64, 'psql (PostgreSQL) 17.6', True)):
            result = subprocess.run(['/bin/sh', '-c', command], env={
                'PATH': str(self.base) + ':/usr/bin:/bin', 'POSTGRES_IMAGE': reference,
                'FAKE_VERSION': version}, capture_output=True, timeout=5)
            self.assertEqual(result.returncode == 0, valid)

    def test_child_exit_status_is_preserved(self):
        self.provision('api')
        result = self.run_script(command=['/bin/sh', '-c', 'exit 17'])
        self.assertEqual(result.returncode, 17)

    def test_hosted_and_development_bare_python_resolve_official_image_local_bin(self):
        # Model directory membership of the image PATH, not the host's Python
        # installation. Utilities retain their absolute production paths. The
        # harmless child exists ONLY in the image fixture's /usr/local/bin.
        image = self.base / 'image'
        interpreter = image / 'usr/local/bin/python'
        interpreter.parent.mkdir(parents=True)
        interpreter.write_text('#!/bin/sh\nprintf "%s\\n" official-image-python "$@"\n')
        interpreter.chmod(0o755)
        source = self.script.read_text()
        assignments = [line for line in source.splitlines() if line.startswith('PATH=')]
        self.assertEqual(len(assignments), 1)
        production_path = assignments[0].split('=', 1)[1]
        mapped_path = ':'.join(str(image / directory.lstrip('/')) for directory in production_path.split(':'))
        self.script.write_text(source.replace(assignments[0], 'PATH=' + mapped_path))
        attacker = self.base / 'caller-bin'; attacker.mkdir()
        malicious = attacker / 'python'
        malicious.write_text('#!/bin/sh\nprintf "%s\\n" caller-path-hijacked\n'); malicious.chmod(0o755)
        for service in ('ingestion-http', 'article-worker', 'payment-reconciler', 'metrics-probe'):
            with self.subTest(service=service):
                self.provision(service)
                command = self.rt.COMMANDS[service]
                self.assertEqual(command[0], 'python')
                result = self.run_script(service, extra={'PATH': str(attacker)}, command=command)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines()[0], 'official-image-python')
                self.assertNotIn('caller-path-hijacked', result.stdout)
        result = subprocess.run(['/bin/sh', str(self.script), 'python', '-m', 'autodata_ingestion.worker'],
                                env={'PATH': str(attacker)}, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'official-image-python\n-m\nautodata_ingestion.worker\n')

    def test_development_default_keeps_existing_image_commands(self):
        result = subprocess.run(['/bin/sh', str(self.script), '/bin/echo', 'development'],
                                env={'PATH': '/usr/bin:/bin'}, capture_output=True, text=True, timeout=5)
        self.assertEqual((result.returncode, result.stdout), (0, 'development\n'))

    def test_image_definitions_package_wrapper_and_released_sql_without_source_mounts(self):
        api = (ROOT / 'apps/api-go/Dockerfile').read_text()
        ingestion = (ROOT / 'workers/ingestion-python/Dockerfile').read_text()
        migration = HERE / 'migration.Dockerfile'
        self.assertTrue(migration.is_file(), 'released migration image definition missing')
        for text in (api, ingestion, migration.read_text()):
            self.assertIn('COPY --chmod=0555 infra/deploy/gce/runtime-entrypoint.sh /usr/local/bin/autodata-runtime-entrypoint', text)
            self.assertIn('ENTRYPOINT ["/usr/local/bin/autodata-runtime-entrypoint"]', text)
        self.assertIn('CMD ["/usr/local/bin/autodata-api"]', api)
        text = migration.read_text()
        self.assertIn('ARG POSTGRES_IMAGE', text)
        self.assertIn('FROM ${POSTGRES_IMAGE}', text)
        self.assertIn('COPY scripts/dev/migrate_sql.sh /release/scripts/dev/migrate_sql.sh', text)
        copy_line = next(line for line in text.splitlines() if line.startswith('COPY db/migrations/'))
        source = copy_line.split()[1]
        copied = list((ROOT / 'db/migrations').iterdir()) if source.endswith('/') else list(ROOT.glob(source))
        self.assertEqual(sorted(p.name for p in copied), sorted(p.name for p in (ROOT / 'db/migrations').glob('*.sql')))
        self.assertGreater(len(copied), 0)
        self.assertIn('psql --version', text)
        self.assertIn('USER 1000:1000', text)



# This intentionally small offline reader models only the nft syntax emitted by
# this artifact. It is NOT nft parser/kernel validation; staging must do that.
def guard_fixture():
    source = (HERE / 'metadata-guard.nft').read_text()
    records, family, table, chain = [], None, None, None
    declarations = []
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith(('add table ', 'flush table ')):
            declarations.append(line)
            continue
        words = shlex.split(line)
        if words[0] == 'table':
            family, table = words[1:3]
            records.append({'table': {'family': family, 'name': table, 'handle': 1}})
        elif words[0] == 'chain':
            chain = words[1]
        elif words[0] == 'type':
            records.append({'chain': {'family': family, 'table': table, 'name': chain,
                'type': words[1], 'hook': words[3], 'prio': int(words[5].rstrip(';')),
                'policy': words[7].rstrip(';'), 'handle': 2}})
        elif words[0] == '}':
            continue
        else:
            expr = []
            while len(words) > 1:
                kind, field, value = words[:3]; words = words[3:]
                left = {'meta': {'key': field}} if kind == 'meta' else {'payload': {'protocol': kind, 'field': field}}
                if '/' in value:
                    address = ipaddress.ip_network(value)
                    value = {'prefix': {'addr': str(address.network_address), 'len': address.prefixlen}}
                elif value.isdecimal(): value = int(value)
                expr.append({'match': {'op': '==', 'left': left, 'right': value}})
            if words not in (['accept'], ['drop']): raise AssertionError('unsupported rule')
            expr.append({words[0]: None})
            records.append({'rule': {'family': family, 'table': table, 'chain': chain, 'expr': expr, 'handle': 3}})
    if declarations != ['add table inet autodata_guard', 'flush table inet autodata_guard',
                        'add table bridge autodata_guard', 'flush table bridge autodata_guard']:
        raise AssertionError('must replace only owned tables atomically')
    return {'inet': {'nftables': [r for r in records if next(iter(r.values()))['family'] == 'inet']},
            'bridge': {'nftables': [r for r in records if next(iter(r.values()))['family'] == 'bridge']}}



def upstream_guard_readback(*, chains_first=True, explicit_l4proto=False):
    """Independent JSON fixture following nftables 1.1.3 output protocol.

    json.c table_print_json_full declares chains before any rules. The first
    tcp.t.json case contains only tcp dport: delinearization removes the meta
    dependency. No source tokenizer or production expected-value helper is used.
    Optional forms isolate each reviewed mismatch in a fake-CLI regression.
    """
    def meta(key, value):
        return {'match': {'op': '==', 'left': {'meta': {'key': key}}, 'right': value}}
    def payload(protocol, field, value):
        return {'match': {'op': '==', 'left': {'payload': {'protocol': protocol, 'field': field}}, 'right': value}}
    def port(value):
        return ([meta('l4proto', 'tcp')] if explicit_l4proto else []) + [payload('tcp', 'dport', value)]
    def accept(expressions): return expressions + [{'accept': None}]
    def drop(expressions): return expressions + [{'drop': None}]
    def subnet(value): return {'prefix': {'addr': value, 'len': 24}}
    inet_forward = [
        accept([meta('iifname', 'br-ad-edge'), payload('ip', 'saddr', '172.30.10.10'), payload('ip', 'daddr', '169.254.169.254')] + port(80)),
        drop([payload('ip', 'daddr', '169.254.169.254')]),
        drop([payload('ip6', 'daddr', 'fd20:ce::254')]),
        drop([meta('iifname', 'br-ad-edge'), meta('nfproto', 'ipv6')]),
        drop([meta('iifname', 'br-ad-back'), meta('nfproto', 'ipv6')]),
        drop([meta('iifname', 'br-ad-work'), meta('nfproto', 'ipv6')]),
        accept([meta('iifname', 'br-ad-edge'), payload('ip', 'saddr', subnet('172.30.10.0')), payload('ip', 'daddr', '172.30.20.40')] + port(9000)),
        accept([meta('iifname', 'br-ad-back'), payload('ip', 'saddr', subnet('172.30.20.0')), payload('ip', 'daddr', '172.30.20.40')] + port(9000)),
        accept([meta('iifname', 'br-ad-work'), payload('ip', 'saddr', subnet('172.30.30.0')), payload('ip', 'daddr', '172.30.20.40')] + port(9000)),
        drop([payload('ip', 'daddr', '172.30.20.40')])]
    inet_output = [
        accept([meta('skuid', 0), payload('ip', 'daddr', '169.254.169.254')] + port(80)),
        drop([payload('ip', 'daddr', '169.254.169.254')]),
        drop([payload('ip6', 'daddr', 'fd20:ce::254')])]
    bridge_forward = [
        drop([meta('ibrname', 'br-ad-edge'), payload('ether', 'type', 'ip6')]),
        drop([meta('ibrname', 'br-ad-back'), payload('ether', 'type', 'ip6')]),
        drop([meta('ibrname', 'br-ad-work'), payload('ether', 'type', 'ip6')]),
        accept([meta('ibrname', 'br-ad-back'), payload('ip', 'saddr', subnet('172.30.20.0')), payload('ip', 'daddr', '172.30.20.40')] + port(9000)),
        drop([payload('ip', 'daddr', '172.30.20.40')])]
    snapshots = {}
    for family, chains in (('inet', [('forward', inet_forward), ('output', inet_output)]),
                            ('bridge', [('forward', bridge_forward)])):
        declarations, rules, interleaved = [], [], []
        for name, expressions in chains:
            declaration = {'chain': {'family': family, 'table': 'autodata_guard', 'name': name,
                'type': 'filter', 'hook': name, 'prio': -200, 'policy': 'accept', 'handle': 2}}
            group = [{'rule': {'family': family, 'table': 'autodata_guard', 'chain': name, 'expr': expr,
                               'handle': number + 3}} for number, expr in enumerate(expressions)]
            declarations.append(declaration); rules.extend(group); interleaved.extend([declaration] + group)
        snapshots[family] = {'nftables': [
            {'metainfo': {'version': '1.1.3', 'json_schema_version': 1}},
            {'table': {'family': family, 'name': 'autodata_guard', 'handle': 1}}
        ] + (declarations + rules if chains_first else interleaved)}
    return snapshots


def packet_verdict(snapshot, chain, **packet):
    for record in snapshot['nftables']:
        rule = record.get('rule')
        if rule is None or rule['chain'] != chain: continue
        matched = True
        for expr in rule['expr'][:-1]:
            match = expr['match']; left = match['left']; right = match['right']
            key = left['meta']['key'] if 'meta' in left else left['payload']['protocol'] + '.' + left['payload']['field']
            actual = packet.get(key)
            if isinstance(right, dict):
                prefix = right['prefix']; matched &= actual is not None and ipaddress.ip_address(actual) in ipaddress.ip_network(prefix['addr'] + '/' + str(prefix['len']))
            else: matched &= actual == right
        if matched: return next(iter(rule['expr'][-1]))
    return 'accept'


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.rt = load_runtime()
        self.daemon_guard = patch.object(subprocess, 'Popen', side_effect=AssertionError('real subprocess forbidden'))
        self.network_guard = patch.object(socket, 'socket', side_effect=AssertionError('network forbidden'))
        self.daemon_guard.start(); self.network_guard.start()
        self.addCleanup(self.daemon_guard.stop); self.addCleanup(self.network_guard.stop)

    def snapshots(self):
        self.assertTrue((HERE / 'metadata-guard.nft').is_file(), 'guard artifact missing')
        return guard_fixture()

    def test_metadata_exception_requires_both_api_source_and_edge_ingress(self):
        rules = self.snapshots()['inet']
        base = {'iifname': 'br-ad-edge', 'ip.saddr': '172.30.10.10', 'ip.daddr': '169.254.169.254',
                'l4proto': 'tcp', 'tcp.dport': 80, 'nfproto': 'ipv4'}
        self.assertEqual(packet_verdict(rules, 'forward', **base), 'accept')
        for network in self.rt.TOPOLOGY.values():
            for address in network['addresses'].values():
                if address == '172.30.10.10': continue
                with self.subTest(service_address=address):
                    self.assertEqual(packet_verdict(rules, 'forward', **dict(base, **{'ip.saddr': address})), 'drop')
        for changed in ({'iifname': 'br-ad-work'}, {'iifname': 'eth0'}, {'ip.saddr': '172.30.10.20'},
                        {'ip.saddr': '172.30.20.10'}, {'ip.saddr': '172.30.30.11'}, {'tcp.dport': 443},
                        {'l4proto': 'udp'}, {'l4proto': 'icmp'}, {'ip.daddr': None, 'ip6.daddr': 'fd20:ce::254', 'nfproto': 'ipv6'}):
            with self.subTest(changed=changed):
                self.assertEqual(packet_verdict(rules, 'forward', **dict(base, **changed)), 'drop')

    def test_root_host_exception_never_exempts_unprivileged_output(self):
        rules = self.snapshots()['inet']
        base = {'skuid': 0, 'ip.daddr': '169.254.169.254', 'l4proto': 'tcp', 'tcp.dport': 80}
        self.assertEqual(packet_verdict(rules, 'output', **base), 'accept')
        for changed in ({'skuid': 1000}, {'skuid': 65534}, {'tcp.dport': 443}, {'l4proto': 'udp'},
                        {'ip.daddr': None, 'ip6.daddr': 'fd20:ce::254'}):
            with self.subTest(changed=changed):
                self.assertEqual(packet_verdict(rules, 'output', **dict(base, **changed)), 'drop')

    def test_storage_boundary_covers_routed_and_same_bridge_listeners(self):
        rules = self.snapshots()
        for family, interface_key, interface, address in (
            ('inet', 'iifname', 'br-ad-edge', '172.30.10.10'),
            ('inet', 'iifname', 'br-ad-work', '172.30.30.11'),
            ('inet', 'iifname', 'br-ad-back', '172.30.20.12'),
            ('bridge', 'ibrname', 'br-ad-back', '172.30.20.10'),
            ('bridge', 'ibrname', 'br-ad-back', '172.30.20.11'),
            ('bridge', 'ibrname', 'br-ad-back', '172.30.20.12')):
            base = {interface_key: interface, 'ip.saddr': address, 'ip.daddr': '172.30.20.40', 'l4proto': 'tcp', 'tcp.dport': 9000}
            self.assertEqual(packet_verdict(rules[family], 'forward', **base), 'accept')
            for port in (0, 22, 80, 443, 8888, 18888, 9333, 19333, 8080, 18080, 23646, 33646, 65535):
                with self.subTest(family=family, address=address, port=port):
                    self.assertEqual(packet_verdict(rules[family], 'forward', **dict(base, **{'tcp.dport': port})), 'drop')
            for change in ({'l4proto': 'udp'}, {interface_key: 'other'}, {'ip.saddr': '192.0.2.1'}):
                self.assertEqual(packet_verdict(rules[family], 'forward', **dict(base, **change)), 'drop')

    def test_unrelated_forwarding_is_untouched_and_application_ipv6_is_denied(self):
        rules = self.snapshots()
        for family, key in (('inet', 'iifname'), ('bridge', 'ibrname')):
            self.assertEqual(packet_verdict(rules[family], 'forward', **{key: 'other', 'nfproto': 'ipv6', 'ether.type': 'ip6'}), 'accept')
            for bridge in ('br-ad-edge', 'br-ad-back', 'br-ad-work'):
                self.assertEqual(packet_verdict(rules[family], 'forward', **{key: bridge, 'nfproto': 'ipv6', 'ether.type': 'ip6'}), 'drop')

    def test_live_validator_rejects_missing_reordered_and_extra_rules(self):
        snapshots = self.snapshots()
        self.rt.validate_guard_tables(snapshots)
        for family in ('inet', 'bridge'):
            for mutation in ('missing', 'extra', 'priority', 'verdict', 'reordered', 'foreign_table'):
                changed = copy.deepcopy(snapshots); records = changed[family]['nftables']
                rules = [r['rule'] for r in records if 'rule' in r]
                if mutation == 'missing': records.pop()
                elif mutation == 'extra': records.append(copy.deepcopy(records[-1]))
                elif mutation == 'priority': next(r['chain'] for r in records if 'chain' in r)['prio'] = 0
                elif mutation == 'verdict': rules[0]['expr'][-1] = {'accept': None} if rules[0]['expr'][-1] == {'drop': None} else {'drop': None}
                elif mutation == 'reordered': rules[0]['expr'], rules[1]['expr'] = rules[1]['expr'], rules[0]['expr']
                else: records[0]['table']['name'] = 'docker'
                with self.subTest(family=family, mutation=mutation), self.assertRaises(self.rt.ContractError):
                    self.rt.validate_guard_tables(changed)
        self.assertTrue(all(next(r['chain'] for r in v['nftables'] if 'chain' in r)['prio'] < -100 for v in snapshots.values()))

    def test_live_validator_accepts_only_exact_protocol_encoding_equivalents(self):
        snapshots = self.snapshots()
        numeric = copy.deepcopy(snapshots)
        for family, snapshot in numeric.items():
            snapshot['nftables'].insert(0, {'metainfo': {'version': 'review-in-staging', 'json_schema_version': 1}})
            for record in snapshot['nftables']:
                if 'rule' not in record: continue
                for expression in record['rule']['expr']:
                    if 'match' not in expression: continue
                    match = expression['match']; left = match['left']
                    if left == {'meta': {'key': 'ibrname'}}:
                        match['left'] = {'meta': {'key': 'ibridgename'}}
                    elif left == {'meta': {'key': 'l4proto'}}: match['right'] = 6
                    elif left == {'meta': {'key': 'nfproto'}}: match['right'] = 10
                    elif left == {'payload': {'protocol': 'ether', 'field': 'type'}}: match['right'] = 34525
        self.assertTrue(self.rt.validate_guard_tables(numeric))
        changed = copy.deepcopy(numeric)
        first_rule = next(r['rule'] for r in changed['inet']['nftables'] if 'rule' in r)
        first_rule['expr'][-2]['match']['right'] = 443
        with self.assertRaises(self.rt.ContractError): self.rt.validate_guard_tables(changed)
        for snapshot in numeric.values():
            snapshot['nftables'].append({'metainfo': {}})
        with self.assertRaises(self.rt.ContractError): self.rt.validate_guard_tables(numeric)

    def test_guard_cli_uses_only_fixed_readonly_observations_and_redacts_failure(self):
        snapshots = self.snapshots()
        expected = [['/usr/sbin/nft', '--json', '--numeric', 'list', 'table', family, 'autodata_guard'] for family in ('inet', 'bridge')]
        seen = []
        def execute(argv, **kwargs):
            self.assertEqual(argv, expected[len(seen)]); seen.append(argv)
            self.assertEqual(kwargs, {'stdin': subprocess.DEVNULL, 'stdout': subprocess.PIPE, 'stderr': subprocess.DEVNULL,
                'timeout': 5, 'check': False, 'cwd': '/', 'env': {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}})
            return subprocess.CompletedProcess(argv, 0, json.dumps(snapshots[argv[-2]]).encode())
        with patch.object(os, 'geteuid', return_value=0), patch.object(subprocess, 'run', side_effect=execute):
            code, result = self.rt.cli(['guard'])
        self.assertEqual(code, 0); self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['checks'], {'metadata_guard': True, 'storage_guard': True})
        self.assertEqual(len(seen), 2)
        failures = ((subprocess.CompletedProcess(expected[0], 1, b'secret-do-not-print'), 3),
                    (subprocess.CompletedProcess(expected[0], 0, b'{}'), 3),
                    (FileNotFoundError('secret-do-not-print'), 3),
                    (subprocess.TimeoutExpired(expected[0], 5, output=b'secret-do-not-print'), 5))
        for outcome, status in failures:
            with patch.object(os, 'geteuid', return_value=0), patch.object(subprocess, 'run', **({'side_effect': outcome} if isinstance(outcome, Exception) else {'return_value': outcome})):
                code, result = self.rt.cli(['guard'])
            self.assertEqual(code, status); self.assertNotEqual(result['status'], 'passed')
            self.assertNotIn('secret-do-not-print', json.dumps(result))
        with patch.object(os, 'geteuid', return_value=1000):
            self.assertEqual(self.rt.cli(['guard'])[0], 3)
        self.assertEqual(self.rt.cli(['guard', '/tmp/rules'])[0], 2)

    def assert_readback_cli_passes(self, snapshots):
        def execute(argv, **kwargs):
            self.assertEqual(argv, ['/usr/sbin/nft', '--json', '--numeric', 'list', 'table', argv[-2], 'autodata_guard'])
            self.assertIn(argv[-2], ('inet', 'bridge'))
            return subprocess.CompletedProcess(argv, 0, json.dumps(snapshots[argv[-2]]).encode())
        with patch.object(os, 'geteuid', return_value=0), patch.object(subprocess, 'run', side_effect=execute):
            code, result = self.rt.cli(['guard'])
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['checks'], {'metadata_guard': True, 'storage_guard': True})

    def test_guard_cli_accepts_upstream_all_chain_declarations_before_rules(self):
        # Isolate object ordering from the redundant dependency defect.
        self.assert_readback_cli_passes(upstream_guard_readback(explicit_l4proto=True))

    def test_guard_cli_accepts_tcp_payload_without_redundant_meta_dependency(self):
        # Isolate dependency removal from the object ordering defect.
        self.assert_readback_cli_passes(upstream_guard_readback(chains_first=False))

    def test_guard_cli_accepts_combined_upstream_readback_shape(self):
        self.assert_readback_cli_passes(upstream_guard_readback())

    def test_upstream_readback_rejects_missing_extra_and_changed_predicates(self):
        baseline = upstream_guard_readback()
        # Every predicate remaining after legitimate delinearization is required.
        for family in ('inet', 'bridge'):
            original = [r['rule'] for r in baseline[family]['nftables'] if 'rule' in r]
            for rule_index, rule in enumerate(original):
                for expression_index, expression in enumerate(rule['expr'][:-1]):
                    for mutation in ('missing', 'extra', 'changed'):
                        changed = copy.deepcopy(baseline)
                        target = [r['rule'] for r in changed[family]['nftables'] if 'rule' in r][rule_index]['expr']
                        if mutation == 'missing': target.pop(expression_index)
                        elif mutation == 'extra': target.insert(expression_index, copy.deepcopy(expression))
                        else: target[expression_index]['match']['right'] = 'wrong-protocol-address-port-interface-or-uid'
                        with self.subTest(family=family, rule=rule_index, expression=expression_index, mutation=mutation), self.assertRaises(self.rt.ContractError):
                            self.rt.validate_guard_tables(changed)
        for mutation in ('chain_order', 'rule_order', 'extra_chain', 'extra_rule', 'wrong_transport', 'wrong_dependency'):
            changed = copy.deepcopy(baseline); records = changed['inet']['nftables']
            chains = [i for i, r in enumerate(records) if 'chain' in r]
            rules = [i for i, r in enumerate(records) if 'rule' in r]
            if mutation == 'chain_order': records[chains[0]], records[chains[1]] = records[chains[1]], records[chains[0]]
            elif mutation == 'rule_order': records[rules[0]], records[rules[1]] = records[rules[1]], records[rules[0]]
            elif mutation == 'extra_chain': records.insert(chains[-1], copy.deepcopy(records[chains[0]]))
            elif mutation == 'extra_rule': records.append(copy.deepcopy(records[rules[-1]]))
            elif mutation == 'wrong_transport': records[rules[0]]['rule']['expr'][-2]['match']['left']['payload']['protocol'] = 'udp'
            else: records[rules[0]]['rule']['expr'].insert(-2, {'match': {'op': '==', 'left': {'meta': {'key': 'l4proto'}}, 'right': 'udp'}})
            with self.subTest(mutation=mutation), self.assertRaises(self.rt.ContractError): self.rt.validate_guard_tables(changed)

    def test_systemd_dependencies_fail_closed_before_docker_start(self):
        import configparser
        def unit(name):
            self.assertTrue((HERE / name).is_file(), name + ' missing')
            config = configparser.ConfigParser(interpolation=None, strict=False)
            config.read(HERE / name); return config
        guard = unit('autodata-metadata-guard.service')
        docker = unit('docker-autodata.conf')
        self.assertIn('docker.service', guard['Unit']['Before'].split())
        for key in ('Requires', 'After'):
            self.assertTrue({'var-lib-autodata.mount', 'autodata-metadata-guard.service'} <= set(docker['Unit'][key].split()))
        self.assertEqual(guard['Service']['ExecStart'], '/usr/sbin/nft -f /etc/autodata/metadata-guard.nft')
        check = '/usr/bin/env -i /usr/bin/python3 -I /opt/autodata/bin/runtime-check.py guard'
        self.assertEqual(guard['Service']['ExecStartPost'], check)
        self.assertEqual(docker['Service']['ExecStartPre'], check)
        self.assertNotIn('ExecStop', guard['Service'])



def catalog_wire():
    return {'protocol_version': 2, 'phase': 'catalog',
        'identity': {'session_user': 'autodata_metrics', 'current_user': 'autodata_metrics', 'database': 'autodata',
                     'server_version_num': 170006, 'transaction_read_only': True, 'default_transaction_read_only': True,
                     'client_addr': None, 'client_port': None},
        'rights': {'login': True, 'superuser': False, 'create_db': False, 'create_role': False, 'replication': False,
                   'bypass_rls': False, 'inherit': False, 'membership_count': 0, 'connect': True, 'schema_usage': True,
                   'ledger_select': True, 'database_create': False, 'database_temp': False, 'database_owner': False,
                   'schema_create': False, 'schema_owner': False, 'relation_owner': False, 'sequence_owner': False,
                   'relation_write': False, 'column_write': False, 'sequence_write': False},
        'ledger_relation': {'oid': 16389, 'schema': 'public', 'name': 'schema_migrations', 'kind': 'r', 'persistence': 'p',
                            'is_partition': False, 'has_inheritance': False, 'rls': False, 'force_rls': False,
                            'version_type': 'pg_catalog.text', 'version_not_null': True, 'version_generated': '',
                            'version_identity': '', 'primary_key_version': True}}

def postgres_wire(image_id, data='/var/lib/autodata', secrets='/run/autodata'):
    # Pinned Docker typed InspectResponse; bind mount list order is unspecified.
    return {'id': 'd' * 64, 'name': '/autodata-production-postgres-1', 'image': image_id,
            'user': '999:999', 'project': 'autodata-production', 'service': 'postgres', 'command': ['postgres'],
            'running': True, 'paused': False, 'restarting': False, 'dead': False,
            'started_at': '2026-11-03T12:00:00.123456789Z', 'readonly_root': True, 'privileged': False,
            'cap_add': None, 'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
            'mounts': [{'Type': 'bind', 'Source': data + '/postgres', 'Destination': '/var/lib/postgresql/data',
                        'Mode': '', 'RW': True, 'Propagation': 'rprivate'},
                       {'Type': 'bind', 'Source': secrets + '/postgres', 'Destination': '/run/autodata/postgres',
                        'Mode': '', 'RW': False, 'Propagation': 'rprivate'}],
            'tmpfs': {'/tmp': 'rw,nosuid,nodev,noexec,size=67108864,mode=1777',
                      '/var/run/postgresql': 'rw,nosuid,nodev,noexec,size=16777216,uid=999,gid=999,mode=0700'}}


class FakeSchemaPipe:
    def __init__(self, payload, chunk=4096):
        self.payload = payload; self.chunk = chunk; self.offset = 0; self.closed = False; self.requests = []
    def read1(self, size):
        assert not self.closed
        self.requests.append(size)
        size = min(size, self.chunk)
        data = self.payload[self.offset:self.offset + size]; self.offset += len(data)
        return data
    def close(self): self.closed = True


class FakeSchemaProcess:
    def __init__(self, payload, code=0, chunk=4096):
        self.stdout = FakeSchemaPipe(payload, chunk); self.code = code
        self.done = False; self.killed = False; self.waits = []; self.wait_timeout = False; self.cleanup_failure = False
    def poll(self): return self.code if self.done else None
    def kill(self): self.killed = True
    def wait(self, timeout):
        self.waits.append(timeout)
        if self.cleanup_failure or (self.wait_timeout and not self.killed): raise subprocess.TimeoutExpired('fake', timeout)
        self.done = True; return self.code


class FakeSchemaSelector:
    def __init__(self, ready=True): self.ready = ready; self.closed = False
    def register(self, pipe, events): self.pipe = pipe
    def select(self, timeout): return [(None, None)] if self.ready else []
    def close(self): self.closed = True


class CatalogObservationTests(unittest.TestCase):
    def setUp(self):
        ContractTests.setUp(self)
        self.observation = catalog_wire()
        self.container = postgres_wire(self.manifest['images']['postgres']['image_id'])
        self.calls = []; self.children = []; self.after = None; self.sql_payload = None; self.application_code_executions = 0

    def require_feature(self, name):
        self.assertTrue(callable(getattr(self.rt, name, None)), name + ' missing')

    def fake_exec(self, argv, **kwargs):
        self.calls.append(argv)
        for arg in argv:
            if arg.startswith('--command=') and re.search(r'public[.]schema_migrations|\b(?:EXPLAIN|COPY|EXECUTE)\b', arg, re.I):
                self.application_code_executions += 1
                raise AssertionError('untrusted relation planning/execution forbidden')
        self.assertEqual(kwargs, {'stdin': subprocess.DEVNULL, 'stdout': subprocess.PIPE, 'stderr': subprocess.DEVNULL,
                                 'cwd': '/', 'env': {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}})
        template = self.rt.POSTGRES_INSPECT_TEMPLATE
        prefix = ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock']
        if argv == prefix + ['container', 'inspect', '--format', template, 'autodata-production-postgres-1']:
            payload = json.dumps(self.container).encode()
        elif argv == prefix + ['container', 'inspect', '--format', template, 'd' * 64]:
            payload = json.dumps(self.after or self.container).encode()
        else:
            self.assertEqual(argv, prefix + ['exec', '--user', '999:999', '--workdir', '/', 'd' * 64,
                '/usr/bin/env', '-i', 'PATH=/usr/lib/postgresql/17/bin:/usr/bin:/bin', 'LANG=C', 'LC_ALL=C',
                'HOME=/nonexistent', 'PGPASSFILE=/dev/null', 'PGSERVICEFILE=/dev/null',
                'PGOPTIONS=-c default_transaction_read_only=on -c statement_timeout=2000 -c lock_timeout=1000 -c search_path=pg_catalog',
                '/usr/lib/postgresql/17/bin/psql', '--no-psqlrc', '--no-password', '--no-align', '--tuples-only', '--quiet',
                '--host=/var/run/postgresql', '--port=5432', '--username=autodata_metrics', '--dbname=autodata',
                '--set=ON_ERROR_STOP=1', '--command=' + self.rt.POSTGRES_CATALOG_SQL])
            payload = self.sql_payload if self.sql_payload is not None else json.dumps(self.observation).encode()
        child = FakeSchemaProcess(payload, chunk=37); self.children.append(child); return child

    def collect(self):
        self.require_feature('collect_postgres_catalog')
        with patch.object(subprocess, 'Popen', side_effect=self.fake_exec), patch.object(self.rt.selectors, 'DefaultSelector', side_effect=FakeSchemaSelector):
            return self.rt.collect_postgres_catalog(self.manifest)

    def test_fixed_schema_observation_has_only_three_readonly_processes(self):
        self.assertIsNone(self.collect())
        self.assertEqual(len(self.calls), 3)
        self.assertTrue(all(p.stdout.closed and p.done and not p.killed for p in self.children))
        self.assertTrue(all(0 < n <= 4096 for p in self.children for n in p.stdout.requests))
        projection = [('id', '.ID'), ('name', '.Name'), ('image', '.Image'), ('user', '.Config.User'),
            ('project', '(index .Config.Labels "com.docker.compose.project")'),
            ('service', '(index .Config.Labels "com.docker.compose.service")'), ('command', '.Config.Cmd'),
            ('running', '.State.Running'), ('paused', '.State.Paused'), ('restarting', '.State.Restarting'),
            ('dead', '.State.Dead'), ('started_at', '.State.StartedAt'), ('readonly_root', '.HostConfig.ReadonlyRootfs'),
            ('privileged', '.HostConfig.Privileged'), ('cap_add', '.HostConfig.CapAdd'), ('cap_drop', '.HostConfig.CapDrop'),
            ('security_opt', '.HostConfig.SecurityOpt'), ('mounts', '.Mounts'), ('tmpfs', '.HostConfig.Tmpfs')]
        expected = '{' + ','.join('"' + key + '":{{json ' + expression + '}}' for key, expression in projection) + '}'
        self.assertEqual(self.rt.POSTGRES_INSPECT_TEMPLATE, expected)
        self.assertNotIn('.Config.Env', self.rt.POSTGRES_INSPECT_TEMPLATE)
        self.assertNotIn('data_directory', self.rt.POSTGRES_CATALOG_SQL)

    def test_container_identity_and_hardening_fail_before_sql(self):
        for key, value in [('id', 'bad'), ('name', '/other'), ('image', 'sha256:' + '0' * 64), ('user', '0:0'),
                           ('project', 'other'), ('service', 'api'), ('command', ['sh']), ('running', False),
                           ('paused', True), ('restarting', True), ('dead', True), ('readonly_root', False),
                           ('privileged', True), ('cap_add', ['SYS_ADMIN']), ('cap_drop', []), ('security_opt', []),
                           ('started_at', ''), ('running', 1)]:
            with self.subTest(key=key):
                saved = copy.deepcopy(self.container); self.container[key] = value; self.calls.clear()
                with self.assertRaises(self.rt.ContractError): self.collect()
                self.assertEqual(len(self.calls), 1); self.container = saved

    def test_mounts_cannot_shadow_data_secrets_or_socket(self):
        original = copy.deepcopy(self.container)
        candidates = []
        for key, value in [('Source', '/wrong'), ('Destination', '/wrong'), ('Type', 'volume'), ('RW', False)]:
            candidate = copy.deepcopy(original); candidate['mounts'][0][key] = value; candidates.append(candidate)
        for key, value in [('RW', True), ('Source', '/wrong')]:
            candidate = copy.deepcopy(original); candidate['mounts'][1][key] = value; candidates.append(candidate)
        for destination in ('/var/lib/postgresql/data/pgdata', '/var/run/postgresql', '/', '/tmp'):
            candidate = copy.deepcopy(original); candidate['mounts'].append(dict(candidate['mounts'][0], Destination=destination)); candidates.append(candidate)
        candidate = copy.deepcopy(original); candidate['tmpfs']['/var/run/postgresql'] = 'rw'; candidates.append(candidate)
        candidate = copy.deepcopy(original); candidate['tmpfs']['/extra'] = 'rw'; candidates.append(candidate)
        candidate = copy.deepcopy(original); candidate['mounts'].pop(); candidates.append(candidate)
        for candidate in candidates:
            self.container = candidate; self.calls.clear()
            with self.assertRaises(self.rt.ContractError): self.collect()
            self.assertEqual(len(self.calls), 1)
        self.container = original; self.container['mounts'].reverse(); self.assertIsNone(self.collect())

    def test_every_identity_right_and_relation_fact_is_strict(self):
        self.require_feature('validate_postgres_catalog')
        self.assertIsNone(self.rt.validate_postgres_catalog(self.observation))
        for group in ('identity', 'rights', 'ledger_relation'):
            for key, value in self.observation[group].items():
                wrong = (not value if type(value) is bool else (0 if key == 'oid' else (value + 100000 if type(value) is int else 'wrong')))
                candidate = copy.deepcopy(self.observation); candidate[group][key] = wrong
                with self.subTest(group=group, key=key), self.assertRaises(self.rt.ContractError):
                    self.rt.validate_postgres_catalog(candidate)
                candidate[group][key] = None
                if value is not None:
                    with self.assertRaises(self.rt.ContractError): self.rt.validate_postgres_catalog(candidate)
        for key in self.observation:
            candidate = copy.deepcopy(self.observation); candidate[key] = None
            with self.assertRaises(self.rt.ContractError): self.rt.validate_postgres_catalog(candidate)
        for group in (None, 'identity', 'rights', 'ledger_relation'):
            candidate = copy.deepcopy(self.observation)
            (candidate if group is None else candidate[group])['extra'] = True
            with self.assertRaises(self.rt.ContractError): self.rt.validate_postgres_catalog(candidate)

    def test_revoked_create_temp_does_not_make_database_owner_safe(self):
        self.require_feature('validate_postgres_catalog')
        self.observation['rights']['database_owner'] = True
        self.assertFalse(self.observation['rights']['database_create']); self.assertFalse(self.observation['rights']['database_temp'])
        with self.assertRaises(self.rt.ContractError): self.rt.validate_postgres_catalog(self.observation)

    def test_public_maintain_and_column_only_write_grants_are_unsafe(self):
        self.require_feature('validate_postgres_catalog')
        for key in ('relation_write', 'column_write'):
            candidate = copy.deepcopy(self.observation); candidate['rights'][key] = True
            with self.assertRaises(self.rt.ContractError): self.rt.validate_postgres_catalog(candidate)
        sql = self.rt.POSTGRES_CATALOG_SQL
        for expression in ("has_table_privilege", "'MAINTAIN'", 'has_any_column_privilege', "'INSERT'", "'UPDATE'", "'REFERENCES'", 'd.datdba = r.oid', 'has_schema_privilege'):
            self.assertIn(expression, sql)
        self.assertNotIn('pg_authid', sql); self.assertNotIn('pg_read_all_settings', sql)

    def test_schema_output_is_strict_and_post_query_restart_never_passes(self):
        for payload in (b'{}', b'{"protocol_version":1,"protocol_version":1}', b'NaN', b'opaque-do-not-print'):
            self.sql_payload = payload
            with self.assertRaises(self.rt.ContractError): self.collect()
        self.sql_payload = None
        for key, value in [('id', 'e' * 64), ('started_at', '2026-11-04T12:00:00Z'), ('running', False)]:
            self.after = dict(self.container, **{key: value})
            with self.assertRaises(self.rt.ContractError): self.collect()

    def test_streaming_capture_caps_retention_and_reaps_failed_children(self):
        self.require_feature('_bounded_schema_command')
        for cap in (65536, 524288):
            child = FakeSchemaProcess(b'x' * cap, chunk=13)
            with patch.object(subprocess, 'Popen', return_value=child), patch.object(self.rt.selectors, 'DefaultSelector', side_effect=FakeSchemaSelector):
                result = self.rt._bounded_schema_command(['/fake-only'], cap, self.rt.time.monotonic() + 15)
            self.assertEqual(len(result), cap); self.assertFalse(child.killed); self.assertTrue(child.stdout.closed)
            child = FakeSchemaProcess(b'x' * (cap + 10000), chunk=4096)
            with patch.object(subprocess, 'Popen', return_value=child), patch.object(self.rt.selectors, 'DefaultSelector', side_effect=FakeSchemaSelector), self.assertRaises(self.rt.ContractError):
                self.rt._bounded_schema_command(['/fake-only'], cap, self.rt.time.monotonic() + 15)
            self.assertTrue(child.killed and child.stdout.closed and child.done)
            self.assertEqual(child.stdout.offset, cap + 1)
            self.assertTrue(all(0 < n <= 4096 for n in child.stdout.requests))
            self.assertLessEqual(child.waits[-1], 1)

    def test_sql_rights_checks_do_not_call_table_functions_on_sequences(self):
        self.require_feature('collect_postgres_catalog')
        sql = self.rt.POSTGRES_CATALOG_SQL
        self.assertIn("CASE WHEN x.relkind IN ('r','p','v','m','f') THEN pg_catalog.has_table_privilege", sql)
        self.assertIn("CASE WHEN x.relkind IN ('r','p','v','m','f') THEN pg_catalog.has_any_column_privilege", sql)
        self.assertIn("CASE WHEN x.relkind = 'S' THEN pg_catalog.has_sequence_privilege", sql)

    def test_capture_deadline_cannot_reset_during_stream_or_spawn_after_expiry(self):
        self.require_feature('_bounded_schema_command')
        clock = {'now': 0}
        child = FakeSchemaProcess(b'opaque-do-not-print' * 10000, chunk=10)
        read = child.stdout.read1
        def slow_read(size):
            result = read(size); clock['now'] += 6; return result
        child.stdout.read1 = slow_read
        with patch.object(subprocess, 'Popen', return_value=child), patch.object(self.rt.selectors, 'DefaultSelector', side_effect=FakeSchemaSelector), patch.object(self.rt.time, 'monotonic', side_effect=lambda: clock['now']), self.assertRaises(subprocess.TimeoutExpired):
            self.rt._bounded_schema_command(['/fake-only'], 65536, 15)
        self.assertEqual(child.stdout.offset, 10); self.assertTrue(child.killed and child.stdout.closed and child.done)
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('expired collector must not spawn')), self.assertRaises(subprocess.TimeoutExpired):
            self.rt._bounded_schema_command(['/fake-only'], 65536, self.rt.time.monotonic() - 1)

    def test_oversized_single_read_and_read_error_close_and_reap(self):
        self.require_feature('_bounded_schema_command')
        for failure in ('oversized', 'read_error'):
            child = FakeSchemaProcess(b'')
            child.stdout.read1 = lambda size: b'x' * 70000
            if failure == 'read_error':
                def broken(size): raise OSError('opaque-do-not-print')
                child.stdout.read1 = broken
            expected = self.rt.ContractError if failure == 'oversized' else OSError
            with patch.object(subprocess, 'Popen', return_value=child), patch.object(self.rt.selectors, 'DefaultSelector', side_effect=FakeSchemaSelector), self.assertRaises(expected):
                self.rt._bounded_schema_command(['/fake-only'], 65536, self.rt.time.monotonic() + 15)
            self.assertTrue(child.stdout.closed and child.killed and child.done)

    def test_capture_timeout_failure_and_cleanup_failure_are_unavailable(self):
        self.require_feature('_bounded_schema_command')
        for kind in ('idle', 'wait_timeout', 'exit', 'cleanup'):
            child = FakeSchemaProcess(b'{}', code=1 if kind == 'exit' else 0)
            child.wait_timeout = kind in ('wait_timeout', 'cleanup'); child.cleanup_failure = kind == 'cleanup'
            selector = FakeSchemaSelector(ready=kind != 'idle')
            expected = subprocess.TimeoutExpired if kind in ('idle', 'wait_timeout') else self.rt.ContractError
            with self.subTest(kind=kind), patch.object(subprocess, 'Popen', return_value=child), patch.object(self.rt.selectors, 'DefaultSelector', return_value=selector), self.assertRaises(expected):
                self.rt._bounded_schema_command(['/fake-only'], 65536, self.rt.time.monotonic() + 15)
            self.assertTrue(child.stdout.closed and selector.closed)
            if kind in ('idle', 'wait_timeout', 'cleanup'): self.assertTrue(child.killed)

    def test_missing_fields_wrong_scalar_types_and_unsafe_relations_fail_without_data(self):
        self.require_feature('validate_postgres_catalog')
        for group in (None, 'identity', 'rights', 'ledger_relation'):
            source = self.observation if group is None else self.observation[group]
            for key, value in source.items():
                candidate = copy.deepcopy(self.observation)
                target = candidate if group is None else candidate[group]
                target.pop(key)
                with self.subTest(group=group, missing=key), self.assertRaises(self.rt.ContractError):
                    self.rt.validate_postgres_catalog(candidate)
                for wrong in ([], {}, 1 if type(value) is bool else True):
                    candidate = copy.deepcopy(self.observation)
                    (candidate if group is None else candidate[group])[key] = wrong
                    with self.assertRaises(self.rt.ContractError): self.rt.validate_postgres_catalog(candidate)
        for change in ({'kind': 'v'}, {'kind': 'f'}, {'kind': 'p'}, {'rls': True}, {'force_rls': True},
                       {'version_type': 'application.custom'}, {'primary_key_version': False}, {'has_inheritance': True}):
            self.observation = catalog_wire(); self.observation['ledger_relation'].update(change); self.calls.clear()
            with self.assertRaises(self.rt.ContractError): self.collect()
            self.assertEqual(len(self.calls), 2); self.assertEqual(self.application_code_executions, 0)

    def test_v2_rejects_v1_ledger_and_cached_evidence_without_fallback(self):
        self.require_feature('validate_postgres_catalog')
        candidates = [{'version': 2, 'migrations': ['001_initial', '002_next']}, []]
        for update in ({'protocol_version': 1}, {'phase': 'ledger'}, {'ledger': {}}, {'migrations': []}, {'schema': True}):
            candidates.append(dict(self.observation, **update))
        legacy = copy.deepcopy(self.observation); legacy.pop('phase'); legacy['protocol_version'] = 1; legacy['ledger'] = {}
        candidates += [legacy, dict(legacy, protocol_version=2)]
        for group in ('identity', 'rights', 'ledger_relation'):
            for key in ('ledger', 'version', 'count', 'overflow', 'invalid_value', 'migrations'):
                candidate = copy.deepcopy(self.observation); candidate[group][key] = []
                candidates.append(candidate)
        with patch.object(self.rt, 'validate_schema_ledger', side_effect=AssertionError('offline ledger validator must be unreachable')):
            self.assertIsNone(self.rt.validate_postgres_catalog(self.observation))
            for candidate in candidates:
                with self.assertRaises(self.rt.ContractError): self.rt.validate_postgres_catalog(candidate)
        self.assertTrue(callable(getattr(self.rt, 'collect_postgres_schema', None)))
        self.assertFalse(hasattr(self.rt, 'validate_schema_observation'))

    def test_wire_numeric_string_depth_and_framing_bounds(self):
        self.require_feature('collect_postgres_catalog')
        good = json.dumps(self.observation).encode()
        for field, allowed in (('server_version_num', (170000, 179999)), ('oid', (1, 4294967295))):
            group = 'identity' if field == 'server_version_num' else 'ledger_relation'
            for number in allowed:
                value = copy.deepcopy(self.observation); value[group][field] = number
                self.assertIsNone(self.rt.validate_postgres_catalog(value))
        cases = [b'', b'[]', good + b'\n{}', good + b'\v', b'\xff', good.replace(b'170006', b'1.70006e5'),
                 good.replace(b'170006', b'170006.0'), good.replace(b'170006', b'-170006'),
                 good.replace(b'170006', b'0170006'), good.replace(b'170006', b'17000600000'),
                 good.replace(b'170006', b'true'), good.replace(b'170006', b'NaN'),
                 good.replace(b'"catalog"', b'"' + b'x' * 65 + b'"'),
                 good.replace(b'"catalog"', b'"caf\xc3\xa9"'),
                 b'{"a":{"b":{}}}', b'{' + b','.join(b'"k%d":0' % i for i in range(33)) + b'}',
                 good.replace(b'"phase": "catalog"', b'"phase":"catalog","phase":"catalog"')]
        for payload in cases:
            self.sql_payload = payload
            with self.subTest(payload=payload[:50]), self.assertRaises(self.rt.ContractError): self.collect()
        self.sql_payload = b' \t\r\n' + good + b'\n'
        self.assertIsNone(self.collect())

    def test_sql_only_references_catalogs_and_never_queues_a_ledger_command(self):
        self.require_feature('collect_postgres_catalog')
        sql = self.rt.POSTGRES_CATALOG_SQL
        self.assertNotIn('public.schema_migrations', sql)
        for forbidden in ('EXPLAIN', 'COPY', 'LOCK TABLE', 'EXECUTE', 'pg_get_expr', 'pg_get_viewdef', 'pg_authid', 'pg_index', 'pg_am', 'pg_read_all_settings'):
            self.assertNotIn(forbidden.lower(), sql.lower())
        references = re.findall(r'\b(?:FROM|JOIN)\s+([a-z_][a-z_0-9.]*)', sql, re.I)
        allowed = {'r', 'd', 'n', 'c', 'a', 'app_ns', 'app_rel', 'pg_catalog.pg_roles', 'pg_catalog.pg_database',
                   'pg_catalog.pg_namespace', 'pg_catalog.pg_class', 'pg_catalog.pg_attribute',
                   'pg_catalog.pg_auth_members', 'pg_catalog.pg_inherits', 'pg_catalog.pg_constraint', 'pg_catalog.unnest'}
        self.assertTrue(set(references) <= allowed, set(references) - allowed)
        self.assertIn("'protocol_version', 2, 'phase', 'catalog'", sql)
        # A fake-world sentinel models any data/planning command as untrusted execution.
        # AM/index facts are deliberately absent from the wire; they cannot authorize reads.
        for sentinel in ('view_function', 'foreign_handler', 'rls_policy', 'custom_type_output',
                         'table_am', 'index_am', 'expression_index', 'concurrent_ddl'):
            self.calls.clear()
            with self.subTest(sentinel=sentinel): self.assertIsNone(self.collect())
            self.assertEqual(len(self.calls), 3)
            self.assertEqual(self.application_code_executions, 0)
            self.assertEqual(sum('--command=' + sql in cmd for cmd in self.calls), 1)



class LockedSchemaTests(unittest.TestCase):
    def setUp(self):
        ContractTests.setUp(self)

    def test_schema_cannot_be_inferred_from_catalog(self):
        self.assertTrue(callable(getattr(self.rt, 'collect_postgres_schema', None)), 'locked schema collector missing')
        with patch.object(self.rt, 'collect_postgres_catalog', return_value={}), patch.object(
                self.rt, '_bounded_schema_command', side_effect=self.rt.ContractError('unavailable')):
            with self.assertRaises(self.rt.ContractError):
                self.rt.collect_postgres_schema(self.manifest)

    def test_locked_protocol_gates_ledger_and_bounds_inventory(self):
        self.assertTrue(callable(getattr(self.rt, '_postgres_schema_script', None)), 'locked protocol missing')
        script = self.rt._postgres_schema_script(self.manifest).decode()
        self.assertLess(script.index('LOCK TABLE ONLY public.schema_migrations'), script.index('WITH'))
        self.assertLess(script.index('\\if :safe'), script.index('FROM ONLY public.schema_migrations'))
        self.assertIn('LIMIT 3', script)
        self.assertIn('COMMIT;', script)
        self.assertIn('idle_in_transaction_session_timeout', script)

    def test_runtime_readiness_does_not_accept_missing_dependency_fields(self):
        self.assertTrue(callable(getattr(self.rt, '_validate_readyz', None)), 'readyz validator missing')
        for value in ({}, {'database':'ready'}, {'database':'ready','nats':'ready','object_storage':'ready','paid_catalog':'unavailable'}):
            with self.assertRaises(self.rt.ContractError): self.rt._validate_readyz(value)
        self.rt._validate_readyz({'database':'ready','nats':'ready','object_storage':'ready'})


class RuntimeReadinessTests(unittest.TestCase):
    def setUp(self):
        ContractTests.setUp(self)

    def test_fixed_readyz_uses_bodyless_get_and_fails_closed(self):
        self.assertTrue(callable(getattr(self.rt, '_collect_readyz', None)), 'readyz collector missing')
        class Response:
            status = 200
            def __init__(self, payload): self.payload = payload
            def read1(self, size): data,self.payload=self.payload[:size],self.payload[size:]; return data
        class Sock:
            def shutdown(self, how): pass
        class Connection:
            def __init__(inner, host, port, timeout):
                self.assertEqual((host,port),('172.30.10.10',8080)); inner.sock=Sock()
            def connect(inner): pass
            def request(inner, method, path, body=None, headers=None):
                self.assertEqual((method,path,body),('GET','/readyz',None))
            def getresponse(inner): return Response(b'{"database":"ready","nats":"ready","object_storage":"ready"}')
            def close(inner): pass
        with patch.object(self.rt.http.client,'HTTPConnection',Connection): self.rt._collect_readyz()

    def test_runtime_evidence_requires_fresh_identical_graph_and_schema(self):
        self.assertTrue(callable(getattr(self.rt, 'collect_runtime_readiness', None)), 'readiness collector missing')
        with patch.object(self.rt,'collect_postgres_schema',return_value={'version':2}), patch.object(
                self.rt,'_collect_service_graph',side_effect=[{'id':'first'},{'id':'changed'}]), patch.object(
                self.rt,'_collect_readyz'):
            with self.assertRaises(self.rt.ContractError): self.rt.collect_runtime_readiness(self.manifest,self.config)
        with patch.object(self.rt,'collect_postgres_schema',return_value={'version':2}), patch.object(
                self.rt,'_collect_service_graph',return_value={'id':'first'}), patch.object(self.rt,'_collect_readyz'):
            result=self.rt.collect_runtime_readiness(self.manifest,self.config)
        self.assertEqual(result,dict.fromkeys(('schema','services','postgres','nats','s3','no_work','runtime_evidence'),True))


class DeployCheckTests(unittest.TestCase):
    """Disposable filesystem plus fixed fake findmnt/nft/Docker transcripts only."""
    def setUp(self):
        ContractTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.cleanup_tree)
        self.base = Path(self.temp.name)
        self.rt.HOST_CONFIG = str(self.base / 'config/host.json')
        self.rt.RELEASE_ROOT = str(self.base / 'releases')
        self.rt.DATA_ROOT = str(self.base / 'data')
        self.rt.SECRET_ROOT = str(self.base / 'secrets')
        for directory in (Path(self.rt.HOST_CONFIG).parent, Path(self.rt.RELEASE_ROOT), Path(self.rt.RELEASE_ROOT) / SHA,
                          Path(self.rt.DATA_ROOT), Path(self.rt.SECRET_ROOT)):
            directory.mkdir(mode=0o700)
        self.private_json(Path(self.rt.HOST_CONFIG), self.config)
        self.release = Path(self.rt.RELEASE_ROOT) / SHA
        self.sql = self.release / 'db/migrations'
        self.sql.mkdir(parents=True)
        self.runner = self.release / 'scripts/dev/migrate_sql.sh'
        self.runner.parent.mkdir(parents=True)
        for directory in (self.release / 'db', self.sql, self.release / 'scripts', self.runner.parent):
            directory.chmod(0o755)
        self.runner.write_bytes(b'released runner bytes\n'); self.runner.chmod(0o444)
        for item in self.manifest['migrations']['files']:
            content = item['name'].encode()
            target = self.sql / item['name']; target.write_bytes(content); target.chmod(0o444)
            item['sha256'] = hashlib.sha256(content).hexdigest()
        self.manifest['migrations']['inventory_sha256'] = digest(self.manifest['migrations']['files'])
        self.manifest['migrations']['runner_sha256'] = hashlib.sha256(self.runner.read_bytes()).hexdigest()
        self.private_json(self.release / 'release.json', self.manifest)
        self.images = {role: {'image_id': image['image_id'], 'repo_digests': [image['reference']],
                              'os': 'linux', 'architecture': 'amd64', 'variant': ''}
                       for role, image in self.manifest['images'].items()}
        for service in ('api', 'ingestion-http', 'article-worker', 'payment-reconciler'):
            self.secret_directory(service, {name: b'opaque-do-not-print' for name in self.rt.SECRET_NAMES[service]})
        self.secret_directory('postgres', {'POSTGRES_PASSWORD': b'opaque-do-not-print'})
        nats = (HERE / 'nats.conf.template').read_bytes().replace(b'@@NATS_METRICS_USER@@', b'metrics_user').replace(b'@@NATS_METRICS_PASSWORD@@', b'opaque-do-not-print')
        self.secret_directory('nats', {'nats.conf': nats})
        s3 = (HERE / 'seaweedfs-s3.json.template').read_bytes()
        for name in ('S3_WORKER_ACCESS_KEY', 'S3_WORKER_SECRET_KEY', 'S3_API_ACCESS_KEY', 'S3_API_SECRET_KEY'):
            s3 = s3.replace(('@@' + name + '@@').encode(), ('opaque-' + name).encode())
        self.secret_directory('minio', {'s3.json': s3})
        self.secret_directory('caddy', {'maintenance.caddy': b''})
        self.data_mount = {'filesystems': [{'target': self.rt.DATA_ROOT, 'uuid': self.config['resources']['data_disk_filesystem_uuid'], 'fstype': 'ext4', 'options': 'rw,relatime'}]}
        self.secret_mount = {'filesystems': [{'target': self.rt.SECRET_ROOT, 'uuid': None, 'fstype': 'tmpfs', 'options': 'rw,nosuid,nodev,noexec,relatime'}]}
        self.guard_tables = upstream_guard_readback()
        self.calls = []
        self.wrong_owner = None
        self.wrong_group = None
        # Simulate a root-installed filesystem using real disposable inodes.
        # Preserve actual modes/links/sizes/types; only UID/GID differ on hosts
        # where tests run as the ordinary developer rather than UID0.
        original_fstat = os.fstat
        def metadata(fd):
            result = list(original_fstat(fd))
            path = Path(os.readlink('/proc/self/fd/' + str(fd)))
            relative = path.relative_to(self.base) if path.is_relative_to(self.base) else None
            if relative is not None:
                parts = relative.parts
                service = parts[1] if len(parts) >= 2 and parts[0] == 'secrets' else None
                owner = 999 if service == 'postgres' else (1000 if service in ('api', 'ingestion-http', 'article-worker', 'payment-reconciler', 'nats', 'minio') else 0)
                result[4] = result[5] = owner
                if path == self.wrong_owner: result[4] = 12345
                if path == self.wrong_group: result[5] = 12345
            return os.stat_result(result)
        for guard in (patch.object(os, 'geteuid', return_value=0), patch.object(os, 'fstat', side_effect=metadata),
                      patch.object(subprocess, 'run', side_effect=self.execute),
                      patch.object(subprocess, 'Popen', side_effect=FileNotFoundError('catalog client unavailable'))):
            guard.start(); self.addCleanup(guard.stop)

    def cleanup_tree(self):
        for directory, _, _ in os.walk(self.temp.name): Path(directory).chmod(0o700)
        self.temp.cleanup()

    def private_json(self, path, value):
        path.write_bytes(self.rt.canonical_bytes(value)); path.chmod(0o600)

    def secret_directory(self, service, files):
        directory = Path(self.rt.SECRET_ROOT) / service; directory.mkdir(mode=0o700)
        for name, value in files.items():
            target = directory / name; target.write_bytes(value); target.chmod(0o400)
        directory.chmod(0o500)

    def execute(self, argv, **kwargs):
        self.calls.append(argv)
        self.assertEqual(kwargs, {'stdin': subprocess.DEVNULL, 'stdout': subprocess.PIPE, 'stderr': subprocess.DEVNULL,
            'timeout': 5, 'check': False, 'cwd': '/', 'env': {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}})
        for path, data in ((self.rt.DATA_ROOT, self.data_mount), (self.rt.SECRET_ROOT, self.secret_mount)):
            if argv == ['/usr/bin/findmnt', '--json', '--list', '--mountpoint', path, '--output', 'TARGET,UUID,FSTYPE,OPTIONS']:
                return subprocess.CompletedProcess(argv, 0, json.dumps(data).encode())
        for family in ('inet', 'bridge'):
            if argv == ['/usr/sbin/nft', '--json', '--numeric', 'list', 'table', family, 'autodata_guard']:
                return subprocess.CompletedProcess(argv, 0, json.dumps(self.guard_tables[family]).encode())
        for role, image in self.manifest['images'].items():
            template = '{"image_id":{{json .ID}},"repo_digests":{{json .RepoDigests}},"os":{{json .Os}},"architecture":{{json .Architecture}},"variant":{{json .Variant}}}'
            if argv == ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock', 'image', 'inspect', '--platform', 'linux/amd64', '--format', template, image['reference']]:
                return subprocess.CompletedProcess(argv, 0, json.dumps(self.images[role]).encode())
        raise AssertionError('unexpected command: ' + repr(argv))

    def deploy(self, argv=None):
        self.assertTrue(callable(getattr(self.rt, 'deploy_cli', None)), 'fixed deploy check implementation missing')
        code, receipt = self.rt.deploy_cli(argv or ['check', SHA])
        self.assertIn(code, (2, 3, 5)); self.assertNotEqual(receipt['status'], 'passed')
        self.assertNotIn('opaque-do-not-print', json.dumps(receipt))
        self.assertEqual(set(receipt), {'schema_version', 'operation', 'run_id', 'source_sha', 'status',
                                       'started_at', 'finished_at', 'checks', 'failure_code'})
        return code, receipt

    def test_valid_local_prerequisites_do_not_claim_unimplemented_runtime_evidence(self):
        code, receipt = self.deploy()
        self.assertEqual(code, 3)
        self.assertEqual(receipt['failure_code'], 'missing_dependency')
        self.assertEqual(receipt['checks'], {'config': True, 'manifest': True, 'disk_uuid': True,
            'metadata_guard': True, 'storage_guard': True, 'secrets': True, 'cached_images': True, 'migration_tree': True,
            'schema': False, 'services': False, 'runtime_evidence': False})
        self.assertEqual(len(self.calls), 11)

    def test_catalog_and_cached_validators_cannot_promote_schema_or_readiness(self):
        fixture = CatalogObservationTests(); fixture.rt = self.rt; fixture.manifest = self.manifest
        fixture.container = postgres_wire(self.manifest['images']['postgres']['image_id'], self.rt.DATA_ROOT, self.rt.SECRET_ROOT)
        fixture.observation = catalog_wire(); fixture.calls = []; fixture.children = []; fixture.after = None; fixture.sql_payload = None
        fixture.application_code_executions = 0
        for result in (True, False, AssertionError('offline validator must be unreachable')):
            option = {'side_effect': result} if isinstance(result, Exception) else {'return_value': result}
            with patch.object(self.rt, 'validate_schema_ledger', **option) as offline, patch.object(subprocess, 'Popen', side_effect=fixture.fake_exec), patch.object(self.rt.selectors, 'DefaultSelector', side_effect=FakeSchemaSelector):
                code, receipt = self.deploy()
            offline.assert_not_called()
            self.assertEqual(code, 3); self.assertEqual(receipt['failure_code'], 'missing_dependency')
            self.assertTrue(receipt['checks']['cached_images']); self.assertTrue(receipt['checks']['migration_tree'])
            self.assertFalse(receipt['checks']['schema']); self.assertFalse(receipt['checks']['services']); self.assertFalse(receipt['checks']['runtime_evidence'])
            self.assertEqual(len(fixture.calls), 3); self.assertEqual(fixture.application_code_executions, 0)
            fixture.calls.clear()
        for error, expected in ((FileNotFoundError('opaque-do-not-print'), 3), (subprocess.TimeoutExpired('fake', 5), 5)):
            with patch.object(subprocess, 'Popen', side_effect=error):
                code, receipt = self.deploy()
            self.assertEqual(code, expected); self.assertFalse(receipt['checks']['schema'])

    def test_every_cached_role_requires_selected_digest_and_local_image_id(self):
        for role in self.images:
            for key, value in (('image_id', 'sha256:' + '0' * 64), ('repo_digests', []),
                               ('os', 'windows'), ('architecture', 'arm64'), ('variant', 'v8')):
                with self.subTest(role=role, key=key):
                    before = copy.deepcopy(self.images[role]); self.images[role][key] = value
                    code, receipt = self.deploy()
                    self.assertEqual(code, 3); self.assertFalse(receipt['checks']['cached_images'])
                    self.assertFalse(receipt['checks']['schema'])
                    self.images[role] = before

    def test_cached_inspect_rejects_malformed_or_unavailable_evidence_without_fallback(self):
        role = 'api'; before = copy.deepcopy(self.images[role])
        for value in (None, {}, dict(before, extra=True), dict(before, repo_digests=None),
                      dict(before, repo_digests=[before['repo_digests'][0]] * 2)):
            self.images[role] = value
            self.assertFalse(self.deploy()[1]['checks']['cached_images'])
        self.images[role] = before
        execute = self.execute
        for outcome, expected in ((FileNotFoundError('opaque-do-not-print'), 3),
                                  (subprocess.TimeoutExpired('docker', 5), 5),
                                  (subprocess.CompletedProcess([], 1, b'opaque-do-not-print'), 3),
                                  (subprocess.CompletedProcess([], 0, b'{"image_id":1,"image_id":2}'), 3)):
            def fake(argv, **kwargs):
                if argv[0] != '/usr/bin/docker': return execute(argv, **kwargs)
                self.calls.append(argv)
                if isinstance(outcome, Exception): raise outcome
                return outcome
            self.calls.clear()
            with patch.object(subprocess, 'run', side_effect=fake):
                code, receipt = self.deploy()
            self.assertEqual(code, expected); self.assertFalse(receipt['checks']['cached_images'])
            self.assertEqual(len(self.calls), 5)

    def test_migration_tree_rejects_changed_missing_extra_and_untrusted_files(self):
        self.assertTrue(self.deploy()[1]['checks'].get('migration_tree', False), 'released tree collector missing')
        target = self.sql / '001_initial.sql'; baseline = target.read_bytes()
        for case in ('changed', 'runner_changed', 'missing', 'extra', 'symlink', 'hardlink', 'owner', 'mode', 'directory_mode'):
            with self.subTest(case=case):
                extra = self.sql / '003_unreleased.sql'
                if case == 'changed': target.chmod(0o600); target.write_bytes(b'tampered'); target.chmod(0o444)
                elif case == 'runner_changed': self.runner.chmod(0o600); self.runner.write_bytes(b'tampered'); self.runner.chmod(0o444)
                elif case == 'missing': target.unlink()
                elif case == 'extra': extra.write_bytes(b'unreleased')
                elif case == 'symlink': target.unlink(); target.symlink_to(self.runner)
                elif case == 'hardlink': extra = self.base / 'external-hardlink'; os.link(target, extra)
                elif case == 'owner': self.wrong_owner = target
                elif case == 'mode': target.chmod(0o666)
                else: self.sql.chmod(0o777)
                code, receipt = self.deploy()
                self.assertEqual(code, 3); self.assertFalse(receipt['checks'].get('migration_tree', False))
                self.assertFalse(receipt['checks']['schema'])
                if target.is_symlink(): target.unlink()
                if extra.exists(): extra.unlink()
                if target.exists(): target.chmod(0o600)
                target.write_bytes(baseline); target.chmod(0o444)
                self.runner.chmod(0o600); self.runner.write_bytes(b'released runner bytes\n'); self.runner.chmod(0o444)
                self.sql.chmod(0o755); self.wrong_owner = None

    def test_migration_tree_does_not_follow_parent_symlinks(self):
        original = self.release / 'db'; moved = self.release / 'untrusted-db'
        original.rename(moved); original.symlink_to(moved)
        code, receipt = self.deploy()
        self.assertEqual(code, 3); self.assertFalse(receipt['checks'].get('migration_tree', False))
        self.assertFalse(receipt['checks']['schema'])

    def test_missing_wrong_or_readonly_mount_never_creates_data_files(self):
        baseline = copy.deepcopy(self.data_mount)
        for key, value in (('uuid', '87654321-1234-4234-8234-123456789abc'), ('target', '/'),
                           ('fstype', 'tmpfs'), ('options', 'ro,relatime')):
            self.data_mount = copy.deepcopy(baseline); self.data_mount['filesystems'][0][key] = value
            code, receipt = self.deploy()
            self.assertEqual(code, 3); self.assertFalse(receipt['checks']['disk_uuid'])
            self.assertEqual(list(Path(self.rt.DATA_ROOT).iterdir()), [])
        self.data_mount = {'filesystems': []}
        self.assertFalse(self.deploy()[1]['checks']['disk_uuid'])

    def test_tmpfs_must_be_exact_mount_with_safe_options(self):
        baseline = copy.deepcopy(self.secret_mount)
        for key, value in (('target', '/run'), ('fstype', 'ext4'), ('options', 'rw,nosuid,nodev'),
                           ('options', 'ro,nosuid,nodev,noexec')):
            self.secret_mount = copy.deepcopy(baseline); self.secret_mount['filesystems'][0][key] = value
            self.assertFalse(self.deploy()[1]['checks']['secrets'])
        self.secret_mount = {'filesystems': [baseline['filesystems'][0], baseline['filesystems'][0]]}
        self.assertFalse(self.deploy()[1]['checks']['secrets'])

    def test_guard_drift_blocks_secret_and_runtime_approval(self):
        self.guard_tables['inet']['nftables'].pop()
        code, receipt = self.deploy()
        self.assertEqual(code, 3); self.assertEqual(receipt['failure_code'], 'guard_missing')
        self.assertFalse(receipt['checks']['metadata_guard']); self.assertFalse(receipt['checks']['secrets'])

    def test_manifest_config_source_and_private_metadata_are_enforced_before_tools(self):
        cases = ('config_hash', 'source_sha', 'manifest_mode', 'manifest_owner', 'config_mode', 'release_symlink', 'config_directory_mode')
        manifest_path = Path(self.rt.RELEASE_ROOT) / SHA / 'release.json'
        for case in cases:
            with self.subTest(case=case):
                self.calls.clear(); self.private_json(manifest_path, self.manifest)
                Path(self.rt.HOST_CONFIG).chmod(0o600); Path(self.rt.HOST_CONFIG).parent.chmod(0o700)
                self.wrong_owner = None
                candidate = copy.deepcopy(self.manifest)
                if case == 'config_hash': candidate['service_config_sha256'] = '0' * 64; self.private_json(manifest_path, candidate)
                elif case == 'source_sha': candidate['source_sha'] = 'b' * 40; self.private_json(manifest_path, candidate)
                elif case == 'manifest_mode': manifest_path.chmod(0o644)
                elif case == 'manifest_owner': self.wrong_owner = manifest_path
                elif case == 'config_mode': Path(self.rt.HOST_CONFIG).chmod(0o644)
                elif case == 'config_directory_mode': Path(self.rt.HOST_CONFIG).parent.chmod(0o777)
                else:
                    moved = manifest_path.parent.with_name('moved'); manifest_path.parent.rename(moved)
                    manifest_path.parent.symlink_to(moved)
                try:
                    code, receipt = self.deploy()
                    self.assertEqual(code, 3); self.assertFalse(receipt['checks']['manifest']); self.assertEqual(self.calls, [])
                finally:
                    if case == 'release_symlink': manifest_path.parent.unlink(); moved.rename(manifest_path.parent)

    def test_secret_files_reject_wrong_metadata_links_names_and_malformed_values(self):
        directory = Path(self.rt.SECRET_ROOT) / 'api'; target = directory / 'AUTODATA_POSTGRES_PASSWORD'
        for value in (b'', b'new\nline', b'new\rline', b'nul\x00value', b'x' * 16385):
            target.chmod(0o600); target.write_bytes(value); target.chmod(0o400)
            self.assertFalse(self.deploy()[1]['checks']['secrets'])
        target.chmod(0o600); target.write_bytes(b'opaque-do-not-print'); target.chmod(0o400)
        target.chmod(0o644); self.assertFalse(self.deploy()[1]['checks']['secrets']); target.chmod(0o400)
        self.wrong_owner = target; self.assertFalse(self.deploy()[1]['checks']['secrets']); self.wrong_owner = None
        self.wrong_group = target; self.assertFalse(self.deploy()[1]['checks']['secrets']); self.wrong_group = None
        directory.chmod(0o700); self.assertFalse(self.deploy()[1]['checks']['secrets']); directory.chmod(0o500)
        directory.chmod(0o700); extra = directory / '.unexpected'; extra.write_bytes(b'opaque-do-not-print'); directory.chmod(0o500)
        self.assertFalse(self.deploy()[1]['checks']['secrets'])
        directory.chmod(0o700); extra.unlink(); target.unlink(); target.symlink_to(Path(self.rt.HOST_CONFIG)); directory.chmod(0o500)
        self.assertFalse(self.deploy()[1]['checks']['secrets'])
        directory.chmod(0o700); target.unlink(); other = self.base / 'other'; other.write_bytes(b'opaque-do-not-print'); other.chmod(0o400); os.link(other, target); directory.chmod(0o500)
        self.assertFalse(self.deploy()[1]['checks']['secrets'])

    def test_native_secret_configs_reject_missing_unresolved_or_widened_policy(self):
        for service, filename in (('postgres', 'POSTGRES_PASSWORD'), ('nats', 'nats.conf'), ('minio', 's3.json'), ('caddy', 'maintenance.caddy')):
            target = Path(self.rt.SECRET_ROOT) / service / filename
            before = target.read_bytes(); target.chmod(0o600); target.write_bytes(b'@@UNRESOLVED@@'); target.chmod(0o400)
            self.assertFalse(self.deploy()[1]['checks']['secrets'])
            target.chmod(0o600); target.write_bytes(before); target.chmod(0o400)
        target = Path(self.rt.SECRET_ROOT) / 'nats/nats.conf'; before = target.read_bytes()
        target.chmod(0o600); target.write_bytes(before.replace(b'["$JS.API.INFO"]', b'[">"]')); target.chmod(0o400)
        self.assertFalse(self.deploy()[1]['checks']['secrets'])
        target.chmod(0o600); target.write_bytes(before); target.chmod(0o400)
        directory = target.parent; directory.chmod(0o700); target.unlink(); directory.chmod(0o500)
        self.assertFalse(self.deploy()[1]['checks']['secrets'])
        directory.chmod(0o700); target.write_bytes(before); target.chmod(0o400); directory.chmod(0o500)
        target = Path(self.rt.SECRET_ROOT) / 'minio/s3.json'; before = target.read_bytes()
        widened = json.loads(before); widened['identities'][1]['actions'] = ['Admin']
        target.chmod(0o600); target.write_bytes(json.dumps(widened).encode()); target.chmod(0o400)
        self.assertFalse(self.deploy()[1]['checks']['secrets'])

    def test_all_mutation_verbs_and_invalid_input_are_blocked_without_observation(self):
        for verb in ('install', 'start', 'stop', 'maintenance', 'resume'):
            code, receipt = self.deploy([verb, SHA])
            self.assertEqual(code, 3); self.assertEqual(receipt['operation'], 'deploy.sh ' + verb)
            self.assertEqual(self.calls, [])
        for args in ([], ['check'], ['check', SHA, 'extra'], ['check', '../' + SHA], ['unknown', SHA]):
            self.assertEqual(self.rt.deploy_cli(args)[0], 2); self.assertEqual(self.calls, [])

    def test_missing_tools_timeout_and_failed_observation_are_redacted(self):
        for outcome, code in ((FileNotFoundError('opaque-do-not-print'), 3),
                              (subprocess.TimeoutExpired('findmnt', 5, output=b'opaque-do-not-print'), 5),
                              (subprocess.CompletedProcess([], 1, b'opaque-do-not-print'), 3),
                              (subprocess.CompletedProcess([], 0, b'{"filesystems":[]}'), 3)):
            with patch.object(subprocess, 'run', **({'side_effect': outcome} if isinstance(outcome, Exception) else {'return_value': outcome})):
                self.assertEqual(self.deploy()[0], code)

    def test_wrapper_isolated_fixed_import_and_mutation_fallback(self):
        source = HERE / 'deploy.sh'; self.assertTrue(source.is_file(), 'fixed deploy wrapper missing')
        body = source.read_text().split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        namespace = {'__name__': 'deploy_test'}; exec(compile(body, str(source), 'exec'), namespace)
        expected = '/opt/autodata/bin/runtime-check.py'
        original_spec = importlib.util.spec_from_file_location
        def spec(name, path):
            self.assertEqual(path, expected)
            return original_spec(name, HERE / 'runtime-check.py')
        with patch.object(importlib.util, 'spec_from_file_location', side_effect=spec):
            # Loading is real but fixtures are injected into the loaded module
            # only by the fake loader below; production accepts no path/env hook.
            loaded = namespace['load_runtime']()
            self.assertEqual(loaded.HOST_CONFIG, '/etc/autodata/host.json')
        for argv in (['start', SHA], ['check', '../bad']):
            with patch.object(subprocess, 'run', side_effect=AssertionError('tool forbidden')):
                code, result = namespace['main'](argv)
            self.assertIn(code, (2, 3)); self.assertNotEqual(result['status'], 'passed')


class DeployWrapperTests(unittest.TestCase):
    """Execute only a disposable wrapper and local import-boundary probe."""
    def test_shell_clears_caller_environment_and_uses_isolated_python(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = (HERE / 'deploy.sh').read_text()
            literal = '/opt/autodata/bin/runtime-check.py'
            self.assertEqual(source.count(literal), 1)
            probe = base / 'probe.py'
            probe.write_text("import os,sys\ndef deploy_cli(argv):\n return 3, {'argv':argv,'environment':dict(os.environ),'isolated':sys.flags.isolated}\n")
            script = base / 'deploy.sh'; script.write_text(source.replace(literal, str(probe)))
            environment = {'PATH': '/nonexistent-caller-path', 'PYTHONPATH': str(base), 'PYTHONHOME': '/nonexistent',
                           'AUTODATA_POSTGRES_PASSWORD': 'opaque-do-not-print', 'GOOGLE_APPLICATION_CREDENTIALS': '/do-not-read',
                           'CLOUDSDK_AUTH_ACCESS_TOKEN': 'opaque-do-not-print'}
            result = subprocess.run(['/bin/sh', str(script), 'check', SHA], env=environment, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 3, result.stderr)
            observed = json.loads(result.stdout)
            self.assertEqual(observed['argv'], ['check', SHA]); self.assertEqual(observed['isolated'], 1)
            self.assertTrue(set(observed['environment']).isdisjoint(environment))
            self.assertNotIn('opaque-do-not-print', result.stdout + result.stderr)
            self.assertEqual(result.stderr, '')
            # Blocked/invalid inputs never import even the fixed runtime module.
            probe.write_text("raise RuntimeError('opaque-do-not-print')\n")
            for verb in ('install', 'start', 'stop', 'maintenance', 'resume'):
                result = subprocess.run(['/bin/sh', str(script), verb, SHA], env=environment, capture_output=True, text=True, timeout=5)
                receipt = json.loads(result.stdout)
                self.assertEqual(result.returncode, 3); self.assertEqual(receipt['operation'], 'deploy.sh ' + verb)
                self.assertEqual(receipt['checks'], {'runtime_evidence': False}); self.assertEqual(result.stderr, '')
            result = subprocess.run(['/bin/sh', str(script), 'check', SHA, '/tmp/caller-path'], env=environment, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2); self.assertEqual(json.loads(result.stdout)['failure_code'], 'invalid_input')

    def test_fixed_module_load_failure_returns_only_redacted_common_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); probe = base / 'probe.py'
            probe.write_text("raise RuntimeError('opaque-do-not-print')\n")
            source = (HERE / 'deploy.sh').read_text().replace('/opt/autodata/bin/runtime-check.py', str(probe))
            script = base / 'deploy.sh'; script.write_text(source)
            result = subprocess.run(['/bin/sh', str(script), 'check', SHA], env={'PATH': '/usr/bin:/bin'}, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 3); self.assertEqual(result.stderr, '')
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt['failure_code'], 'missing_dependency'); self.assertEqual(receipt['status'], 'failed')
            self.assertNotIn('opaque-do-not-print', result.stdout)

if __name__ == '__main__':
    unittest.main()
