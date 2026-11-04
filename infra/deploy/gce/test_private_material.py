"""Offline synthetic private-material contracts; no host or provider actions."""
import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import test_host_runtime as fixtures

HERE = Path(__file__).resolve().parent
SHA = 'a' * 40
AUTH = '12345678-1234-4234-8234-123456789abc'
BOOT = '87654321-1234-4234-8234-123456789abc'
NOW = datetime(2026, 11, 4, 18, tzinfo=timezone.utc)
MAPS = {
    'api': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY', 'AUTODATA_INGESTION_INTERNAL_TOKEN', 'AUTODATA_IMAGE_URL_KEY'),
    'ingestion-http': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY', 'AUTODATA_INGESTION_INTERNAL_TOKEN', 'AUTODATA_STRIPE_SECRET_KEY', 'AUTODATA_STRIPE_WEBHOOK_SECRET', 'BANKONE_API_TOKEN', 'BANKTWO_API_TOKEN'),
    'article-worker': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY', 'BANKONE_API_TOKEN', 'BANKTWO_API_TOKEN', 'INCEPTION_API_KEY'),
    'payment-reconciler': ('AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_INGESTION_INTERNAL_TOKEN', 'AUTODATA_STRIPE_SECRET_KEY', 'AUTODATA_STRIPE_WEBHOOK_SECRET')}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def hashed(value):
    return hashlib.sha256(value).hexdigest()


def load():
    path = HERE / 'private_material.py'
    if not path.exists():
        raise AssertionError('private material helper is missing')
    spec = importlib.util.spec_from_file_location('private_material_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.pm = load()
        source = fixtures.ContractTests()
        source.setUp()
        self.addCleanup(source.doCleanups)
        self.runtime, self.config, self.manifest = source.rt, source.config, source.manifest
        self.schema = (HERE / 'release.schema.json').read_bytes()
        self.approval = {
            'schema_version': 1, 'operation': 'install-first-application-private-material',
            'authorization_id': AUTH, 'source_sha': SHA, 'service': 'api',
            'expires_at': '2026-11-04T19:00:00Z',
            'service_config_sha256': hashed(encoded(self.config)),
            'secret_versions': self.manifest['secret_versions']['api']}
        for field in ('manifest_raw_sha256', 'manifest_canonical_sha256', 'host_install_helper_sha256',
                      'runtime_helper_sha256', 'release_schema_sha256', 'findmnt_binary_sha256',
                      'publisher_verification_receipt_sha256', 'owner_publisher_acceptance_evidence_sha256',
                      'owner_data_device_binding_evidence_sha256', 'owner_pre_daemon_host_evidence_sha256'):
            self.approval[field] = 'b' * 64
        self.values = {name: ('synthetic-' + str(i) + '-sentinel').encode() for i, name in enumerate(MAPS['api'])}
        self.frame = {'schema_version': 1, 'authorization_id': AUTH, 'source_sha': SHA, 'service': 'api',
                      'secret_versions': self.approval['secret_versions'],
                      'values': {name: base64.b64encode(value).decode() for name, value in self.values.items()}}
        self.record = {'schema_version': 1, 'operation': 'accept-pre-daemon-first-install',
                       'authorization_id': AUTH, 'source_sha': SHA, 'service': 'api',
                       'service_config_sha256': self.approval['service_config_sha256'],
                       **{k: self.config['resources'][k] for k in ('host_project_id', 'zone', 'instance_name')},
                       'machine_id_sha256': hashed(b'a' * 32 + b'\n'), 'boot_id': BOOT,
                       'issued_at': '2026-11-04T17:59:59Z', 'expires_at': '2026-11-04T18:10:00Z',
                       'assertions': {k: True for k in ('no_installed_workload_lifecycle', 'no_running_workload',
                           'no_restartable_workload', 'no_untrusted_uid1000_process', 'root_exclusive_preparation_window')}}

    def test_fixed_cli_denies_before_input(self):
        for args in ([], ['install'], ['start', SHA, 'api'], ['install', SHA, 'postgres'],
                     ['install', SHA.upper(), 'api'], ['install', SHA, 'api', '/tmp']):
            with patch.object(self.pm, 'read_stream', side_effect=AssertionError('stdin forbidden')):
                code, receipt = self.pm.main(args)
            self.assertEqual(code, 2)
            self.assertEqual(receipt['failure_code'], 'invalid_input')

    def test_exact_maps_match_runtime_and_wrappers(self):
        for service, names in MAPS.items():
            self.assertEqual(self.pm.SERVICE_NAMES[service], names)
            self.assertEqual(names, self.runtime.SECRET_NAMES[service])
            wrapper = (HERE / 'runtime-entrypoint.sh').read_text()
            for name in names:
                self.assertIn(name, wrapper)

    def test_approval_exact_binding(self):
        self.pm.validate_approval(self.approval, SHA, 'api', self.approval['service_config_sha256'], NOW)
        for field, value in (('extra', 1), ('schema_version', True), ('authorization_id', BOOT),
                             ('expires_at', '2026-11-04T18:00:00Z'), ('expires_at', '2026-11-06T00:00:00Z'),
                             ('service', 'postgres'), ('source_sha', 'c' * 40), ('release_schema_sha256', 'B' * 64),
                             ('secret_versions', {'AUTODATA_POSTGRES_PASSWORD': 'projects/x/secrets/x/versions/latest'})):
            bad = copy.deepcopy(self.approval); bad[field] = value
            # BOOT is also a UUIDv4, so substitute a noncanonical authorization here.
            if field == 'authorization_id': bad[field] = AUTH.upper()
            with self.subTest(field=field), self.assertRaises(self.pm.Denied):
                self.pm.validate_approval(bad, SHA, 'api', self.approval['service_config_sha256'], NOW)

    def test_strict_stream_validates_without_normalization(self):
        self.values[next(iter(self.values))] = '  café  '.encode()
        self.frame['values'] = {k: base64.b64encode(v).decode() for k, v in self.values.items()}
        self.assertEqual(self.pm.parse_stream(encoded(self.frame), self.approval), self.values)

    def test_stream_rejects_frames_and_secret_byte_ambiguity(self):
        for raw in (b'{}{}', b'\xff', b'{"x":NaN}', b'{"x":1,"x":1}', b' ' * (1048576 + 1)):
            with self.subTest(raw=raw[:20]), self.assertRaises(self.pm.InvalidInput):
                self.pm.parse_stream(raw, self.approval)
        name = MAPS['api'][0]
        for value in (b'', b'x' * 16385, b'\x00', b'a\rb', b'a\nb', b'@@NAME@@', b'\xff'):
            bad = copy.deepcopy(self.frame); bad['values'][name] = base64.b64encode(value).decode()
            with self.subTest(value=value[:20]), self.assertRaises(self.pm.InvalidInput):
                self.pm.parse_stream(encoded(bad), self.approval)
        for value in ('YQ', 'YQ===', 'YR==', 'Y Q==', 1):
            bad = copy.deepcopy(self.frame); bad['values'][name] = value
            with self.subTest(value=value), self.assertRaises(self.pm.InvalidInput):
                self.pm.parse_stream(encoded(bad), self.approval)
        for key, value in (('schema_version', True), ('service', 'article-worker'), ('extra', 1),
                           ('authorization_id', BOOT), ('secret_versions', {}), ('values', {})):
            bad = copy.deepcopy(self.frame); bad[key] = value
            with self.subTest(key=key), self.assertRaises(self.pm.InvalidInput):
                self.pm.parse_stream(encoded(bad), self.approval)

    def test_schema_validation_never_reopens_path_and_matches_candidate(self):
        accepted = self.runtime.validate_manifest(self.manifest, self.config)
        with patch.object(self.runtime.Path, 'read_bytes', side_effect=AssertionError('path read forbidden')):
            self.assertEqual(self.pm.validate_pinned_first_manifest(self.manifest, self.config, self.schema, self.runtime), accepted)
        mutations = [lambda m: m.update(extra=True), lambda m: m.update(platform='linux/arm64'),
                     lambda m: m.update(schema_version=True), lambda m: m.update(service_config_sha256='0' * 64),
                     lambda m: m['migrations'].update(inventory_sha256='0' * 64),
                     lambda m: m['migrations']['files'].reverse(),
                     lambda m: m['migrations']['files'][1].update(name='003_gap.sql'),
                     lambda m: m['images']['api'].update(reference='postgres:latest'),
                     lambda m: m['secret_versions']['api'].update(AUTODATA_POSTGRES_PASSWORD='projects/a/secrets/a/versions/latest')]
        for mutate in mutations:
            bad = copy.deepcopy(self.manifest); mutate(bad)
            with self.subTest(mutate=mutate):
                with self.assertRaises(self.runtime.ContractError): self.runtime.validate_manifest(bad, self.config)
                with self.assertRaises((self.pm.Denied, self.runtime.ContractError)):
                    self.pm.validate_pinned_first_manifest(bad, self.config, self.schema, self.runtime)
        bad = copy.deepcopy(self.manifest); bad['rollback_source_sha'] = 'c' * 40
        with self.assertRaises(self.pm.Denied):
            self.pm.validate_pinned_first_manifest(bad, self.config, self.schema, self.runtime)

    def test_host_acceptance_exact_identity_freshness_and_assertions(self):
        self.pm.validate_host_record(self.record, self.approval, self.config, b'a' * 32 + b'\n', BOOT.encode() + b'\n', NOW)
        for key, value in (('extra', True), ('issued_at', '2026-11-04T18:00:06Z'),
                           ('expires_at', '2026-11-04T18:00:00Z'), ('issued_at', '2026-11-04T17:00:00Z'),
                           ('boot_id', AUTH), ('machine_id_sha256', 'b' * 64), ('authorization_id', BOOT),
                           ('service', 'ingestion-http'), ('host_project_id', 'other-project'), ('schema_version', True)):
            bad = copy.deepcopy(self.record); bad[key] = value
            with self.subTest(key=key), self.assertRaises(self.pm.Denied):
                self.pm.validate_host_record(bad, self.approval, self.config, b'a' * 32 + b'\n', BOOT.encode(), NOW)
        for value in (False, 1, None):
            bad = copy.deepcopy(self.record); bad['assertions']['no_running_workload'] = value
            with self.assertRaises(self.pm.Denied):
                self.pm.validate_host_record(bad, self.approval, self.config, b'a' * 32 + b'\n', BOOT.encode(), NOW)


if __name__ == '__main__':
    unittest.main()
