"""Offline v1 contract and disposable local script tests; no daemon/network."""
import copy
import hashlib
import importlib.util
import json
import os
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
            'schema_version': 1, 'environment': 'staging', 'public_origin': 'https://staging.cars.example',
            'firebase': {'project_id': 'firebase-stage', 'web_api_key': 'public-web-key',
                         'web_app_id': '1:123456:web:abcdef', 'auth_domain': 'firebase-stage.firebaseapp.com'},
            'resources': {'host_project_id': 'autodata-host', 'backup_project_id': 'autodata-backup',
                          'region': 'us-central1', 'zone': 'us-central1-a', 'instance_name': 'workshop-stage',
                          'data_disk_name': 'workshop-data', 'data_disk_filesystem_uuid': '12345678-1234-4234-8234-123456789abc',
                          'static_ip_name': 'workshop-ip', 'artifact_repository': 'us-central1-docker.pkg.dev/autodata-host/workshop',
                          'backup_bucket': 'autodata-private-backup', 'acme_email': 'ops@example.com'},
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

    def rejected_manifest(self, mutate):
        candidate = copy.deepcopy(self.manifest)
        mutate(candidate)
        with self.assertRaises(self.rt.ContractError):
            self.rt.validate_manifest(candidate, self.config)

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


if __name__ == '__main__':
    unittest.main()
