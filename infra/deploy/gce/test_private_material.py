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
    'outbox-relay': ('AUTODATA_POSTGRES_PASSWORD', 'NATS_OUTBOX_USER', 'NATS_OUTBOX_PASSWORD'),
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


class Fixture(unittest.TestCase):
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



class BoundaryTests(Fixture):
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

    def test_stream_accepts_full_value_limit_and_exact_frame_limit(self):
        name = MAPS['api'][0]
        self.frame['values'][name] = base64.b64encode(b'x' * 16384).decode()
        raw = encoded(self.frame)
        framed = raw + b' ' * (1048576 - len(raw))
        self.assertEqual(self.pm.parse_stream(framed, self.approval)[name], b'x' * 16384)
        with self.assertRaises(self.pm.InvalidInput): self.pm.parse_stream(framed + b' ', self.approval)

    def test_host_identity_rejects_malformed_actual_machine_and_boot(self):
        for machine, boot in ((b'A' * 32, BOOT.encode()), (b'a' * 32 + b'\n\n', BOOT.encode()),
                              (b'a' * 32 + b'\n', BOOT.upper().encode()), (b'a' * 32 + b'\n', b'not-a-boot-id')):
            with self.subTest(machine=machine, boot=boot), self.assertRaises(self.pm.Denied):
                self.pm.validate_host_record(self.record, self.approval, self.config, machine, boot, NOW)


class TransactionTests(Fixture):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('etc', 'var', 'var/lib', 'opt', 'run', 'usr', 'usr/bin', 'opt/autodata/bin',
                     'proc', 'proc/sys', 'proc/sys/kernel', 'proc/sys/kernel/random'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
            (self.root / name).chmod(0o755)
        self.root.chmod(0o755)
        (self.root / 'var/run').symlink_to('../run')
        for name in ('etc/autodata', 'etc/autodata/publisher-accepted', 'etc/autodata/pre-daemon-accepted',
                     'opt/autodata', 'opt/autodata/releases', 'run/autodata', 'var/lib/autodata'):
            (self.root / name).mkdir(exist_ok=True)
            (self.root / name).chmod(0o700)
        (self.root / ('opt/autodata/releases/' + SHA)).mkdir(mode=0o700)
        self.put('opt/autodata/releases/' + SHA + '/release.json', encoded(self.manifest), 0o600)
        (self.root / ('opt/autodata/releases/' + SHA)).chmod(0o500)
        self.put('etc/autodata/host.json', encoded(self.config), 0o600)
        for name in ('host_install.py', 'runtime-check.py', 'release.schema.json'):
            self.put('opt/autodata/bin/' + name, (HERE / name).read_bytes(), 0o444)
        self.put('usr/bin/findmnt', b'fake-never-executed', 0o555)
        self.put('etc/autodata/publisher-accepted/' + SHA + '.json', b'{"accepted":"opaque"}', 0o600)
        self.put('etc/machine-id', b'a' * 32 + b'\n', 0o444)
        self.put('proc/sys/kernel/random/boot_id', BOOT.encode() + b'\n', 0o444)
        self.put('etc/autodata/pre-daemon-accepted/' + AUTH + '.json', encoded(self.record), 0o600)
        paths = {'manifest_raw_sha256': 'opt/autodata/releases/' + SHA + '/release.json',
                 'manifest_canonical_sha256': 'opt/autodata/releases/' + SHA + '/release.json',
                 'host_install_helper_sha256': 'opt/autodata/bin/host_install.py',
                 'runtime_helper_sha256': 'opt/autodata/bin/runtime-check.py',
                 'release_schema_sha256': 'opt/autodata/bin/release.schema.json',
                 'findmnt_binary_sha256': 'usr/bin/findmnt',
                 'publisher_verification_receipt_sha256': 'etc/autodata/publisher-accepted/' + SHA + '.json',
                 'owner_pre_daemon_host_evidence_sha256': 'etc/autodata/pre-daemon-accepted/' + AUTH + '.json'}
        for key, path in paths.items(): self.approval[key] = hashed((self.root / path).read_bytes())
        self.save()
        self.clock = 0.0
        self.probes, self.chowns = [], []
        self.hook = None
        self.stream_reads = 0
        self.assertTrue(callable(getattr(self.pm, '_open_root', None)), 'descriptor transaction missing')
        guards = [patch.object(self.pm, '_open_root', lambda: os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)),
                  patch.object(self.pm, '_owner', lambda s, uid=0, gid=0: s.st_uid == os.getuid() and s.st_gid == os.getgid()),
                  patch.object(self.pm.os, 'geteuid', return_value=0),
                  patch.object(self.pm.os, 'fchown', side_effect=lambda fd, uid, gid: self.chowns.append((uid, gid))),
                  patch.object(self.pm, 'utcnow', return_value=NOW),
                  patch.object(self.pm.time, 'monotonic', side_effect=lambda: self.clock),
                  patch.object(self.pm, 'probe', self.probe),
                  patch.object(self.pm, 'read_stream', self.stream)]
        for guard in guards:
            guard.start(); self.addCleanup(guard.stop)

    def put(self, path, data, mode):
        target = self.root / path
        if target.exists(): target.chmod(0o600)
        target.write_bytes(data); target.chmod(mode)

    def save(self):
        self.put('etc/autodata/private-material-approval.json', encoded(self.approval), 0o600)

    def probe(self, host, fd, target, budget):
        self.probes.append(target)
        if self.hook: self.hook(target)
        item = {'target': target, 'uuid': None, 'fstype': 'tmpfs', 'options': 'rw,nosuid,nodev,noexec'}
        if target == '/var/lib/autodata':
            item.update(uuid=self.config['resources']['data_disk_filesystem_uuid'], fstype='ext4', options='rw')
        return encoded({'filesystems': [item]})

    def stream(self, fd, budget):
        self.stream_reads += 1
        return encoded(self.frame)

    def install(self):
        code, output = self.pm.install_cli(SHA, self.approval['service'])
        self.assertLessEqual(len(encoded(output)), 65536)
        for key in self.pm.AUTHORITIES: self.assertIs(output[key], False)
        for key in ('global_ready', 'schema', 'services', 'no_work', 'runtime_evidence'): self.assertIs(output[key], False)
        return code, output

    def journal(self):
        return self.root / ('var/lib/autodata/operations/private-material-' + AUTH + '.json')

    def test_transaction_all_services_exact_bytes_and_non_success_journal(self):
        for service, names in MAPS.items():
            self.approval['service'] = service
            self.approval['secret_versions'] = self.manifest['secret_versions'][service]
            self.record['service'] = service
            self.put('etc/autodata/pre-daemon-accepted/' + AUTH + '.json', encoded(self.record), 0o600)
            self.approval['owner_pre_daemon_host_evidence_sha256'] = hashed(encoded(self.record))
            self.save()
            self.frame.update(service=service, secret_versions=self.approval['secret_versions'])
            self.values = {name: ('synthetic-' + service + '-' + str(i) + '-sentinel').encode() for i, name in enumerate(names)}
            self.frame['values'] = {k: base64.b64encode(v).decode() for k, v in self.values.items()}
            code, output = self.install()
            self.assertEqual(code, 0, output)
            self.assertTrue(output['one_service_private_material_installed'])
            self.assertTrue(output['secret_material_committed'])
            final = self.root / ('run/autodata/' + service)
            self.assertEqual(stat.S_IMODE(final.stat().st_mode), 0o500)
            self.assertEqual(set(p.name for p in final.iterdir()), set(names))
            for name, value in self.values.items():
                self.assertEqual((final / name).read_bytes(), value)
                self.assertEqual(stat.S_IMODE((final / name).stat().st_mode), 0o400)
                self.assertEqual((final / name).stat().st_nlink, 1)
            journal = json.loads(self.journal().read_text())
            self.assertEqual(journal['phase'], 'material_verified')
            self.assertEqual(journal['operation_status'], 'unconfirmed')
            self.assertNotIn('status', journal)
            self.assertEqual(set(journal), set(('schema_version', 'operation', 'source_sha', 'service', 'authorization_id',
                'started_at', 'updated_at', 'elapsed_seconds', 'approval_sha256', 'secret_versions', 'phase', 'operation_status')) | set(self.pm.HASH_FIELDS))
            for value in self.values.values():
                for representation in (value, base64.b64encode(value), hashed(value).encode()):
                    self.assertNotIn(representation, self.journal().read_bytes() + encoded(output))
            self.assertNotIn(hashed(encoded(self.frame)).encode(), self.journal().read_bytes() + encoded(output))
            self.assertEqual(self.install()[0], 3)
            final.chmod(0o700)
            for child in final.iterdir(): child.unlink()
            final.rmdir(); self.journal().unlink()
        self.assertTrue(all(pair == (1000, 1000) for pair in self.chowns))
        self.assertFalse((self.root / 'opt/autodata/current').exists())

    def test_missing_or_stale_acceptance_denies_before_stream_or_writes(self):
        path = self.root / ('etc/autodata/pre-daemon-accepted/' + AUTH + '.json')
        path.unlink()
        self.assertEqual(self.install()[0], 3)
        self.assertEqual(self.stream_reads, 0)
        self.assertFalse(self.journal().exists())
        self.record['expires_at'] = '2026-11-04T18:00:00Z'
        self.put(str(path.relative_to(self.root)), encoded(self.record), 0o600)
        self.approval['owner_pre_daemon_host_evidence_sha256'] = hashed(encoded(self.record)); self.save()
        self.assertEqual(self.install()[0], 3)
        self.assertEqual(self.stream_reads, 0)

    def test_production_denies_before_approval_and_stream(self):
        self.config['environment'] = 'production'
        self.put('etc/autodata/host.json', encoded(self.config), 0o600)
        (self.root / 'etc/autodata/private-material-approval.json').unlink()
        self.assertEqual(self.install()[0], 3)
        self.assertEqual(self.stream_reads, 0)
        self.assertEqual(self.probes, [])

    def test_residue_current_sockets_and_target_are_never_overwritten(self):
        for path in ('opt/autodata/current', 'run/docker.sock', 'run/autodata/api',
                     'run/autodata/.private-' + AUTH):
            target = self.root / path; target.write_bytes(b'existing')
            self.assertEqual(self.install()[0], 3, path)
            self.assertEqual(self.stream_reads, 0)
            self.assertEqual(target.read_bytes(), b'existing'); target.unlink()

    def test_schema_swap_uses_only_pinned_bytes_then_denies(self):
        def hook(target):
            if len(self.probes) == 1:
                p = self.root / 'opt/autodata/bin/release.schema.json'
                p.unlink(); self.put('opt/autodata/bin/release.schema.json', b'{"type":"object"}', 0o444)
        self.hook = hook
        with patch.object(self.runtime.Path, 'read_bytes', side_effect=AssertionError('path reopen forbidden')):
            self.assertEqual(self.install()[0], 3)
        self.assertEqual(self.stream_reads, 0)

    def test_late_machine_or_lock_swap_fails_closed(self):
        def hook(target):
            if self.stream_reads and target == '/var/lib/autodata':
                self.put('etc/machine-id', b'c' * 32, 0o444)
        self.hook = hook
        code, output = self.install()
        self.assertNotEqual(code, 0)
        self.assertFalse(output['one_service_private_material_installed'])
        self.assertFalse((self.root / 'run/autodata/api').exists())

    def test_intent_is_durable_before_any_secret_file(self):
        real_write = os.write
        def write(fd, data):
            if any(value in bytes(data) for value in self.values.values()):
                self.assertEqual(json.loads(self.journal().read_text())['phase'], 'writing')
            return real_write(fd, data)
        with patch.object(self.pm.os, 'write', side_effect=write):
            self.assertEqual(self.install()[0], 0)

    def test_short_writes_are_completed(self):
        real_write = os.write
        with patch.object(self.pm.os, 'write', side_effect=lambda fd, data: real_write(fd, data[:7])):
            self.assertEqual(self.install()[0], 0)

    def test_enospc_cleans_only_own_tree_and_journals_unconfirmed(self):
        real_write = os.write
        def write(fd, data):
            if any(value in bytes(data) for value in self.values.values()): raise OSError('synthetic sentinel error')
            return real_write(fd, data)
        with patch.object(self.pm.os, 'write', side_effect=write):
            code, output = self.install()
        self.assertEqual(code, 4, output)
        self.assertFalse((self.root / 'run/autodata/api').exists())
        self.assertFalse((self.root / ('run/autodata/.private-' + AUTH)).exists())
        self.assertEqual(json.loads(self.journal().read_text())['operation_status'], 'unconfirmed')
        self.assertNotIn('sentinel error', str(output))

    def test_slow_final_fsync_never_yields_passing_journal_or_receipt(self):
        real_fsync = os.fsync
        def fsync(fd):
            real_fsync(fd)
            if self.journal().exists() and json.loads(self.journal().read_text())['phase'] == 'material_verified':
                self.clock = 271
        with patch.object(self.pm.os, 'fsync', side_effect=fsync):
            code, output = self.install()
        self.assertIn(code, (5, 6), output)
        self.assertFalse(output['one_service_private_material_installed'])
        self.assertEqual(json.loads(self.journal().read_text())['operation_status'], 'unconfirmed')

    def test_current_appearing_during_last_probe_denies_promotion(self):
        def hook(target):
            if self.stream_reads and target == '/run/autodata':
                self.put('opt/autodata/current', b'appeared', 0o600)
        self.hook = hook
        code, output = self.install()
        self.assertNotEqual(code, 0, output)
        self.assertFalse((self.root / 'run/autodata/api').exists())

    def test_temp_residue_other_authorization_requires_recovery(self):
        (self.root / ('run/autodata/.private-' + BOOT)).mkdir(mode=0o700)
        self.assertEqual(self.install()[0], 3)
        self.assertEqual(self.stream_reads, 0)

    def test_late_failed_syscall_still_observes_deadline(self):
        budget = self.pm.Budget()
        def late_error():
            self.clock = 271
            raise OSError('redacted')
        try:
            budget.call(late_error)
        except self.pm.Expired:
            pass
        except OSError:
            self.fail('late syscall error bypassed deadline observation')
        else:
            self.fail('late syscall returned without denial')

    def test_material_fault_matrix_never_publishes_success(self):
        for operation in ('write', 'fchmod', 'fchown', 'fsync', 'mkdir'):
            real = getattr(os, operation)
            fired = False
            def fail(*args, **kwargs):
                nonlocal fired
                if not fired and self.journal().exists():
                    fired = True
                    raise OSError('synthetic fault')
                return real(*args, **kwargs)
            with patch.object(self.pm.os, operation, side_effect=fail):
                code, output = self.install()
            self.assertNotEqual(code, 0, operation)
            self.assertFalse(output['one_service_private_material_installed'])
            self.assertFalse((self.root / 'run/autodata/api').exists())
            self.assertEqual(json.loads(self.journal().read_text())['operation_status'], 'unconfirmed')
            # Recovery of synthetic owned test artifacts belongs to the test only.
            for item in (self.root / 'run/autodata').iterdir():
                if item.name.startswith('.private-'):
                    item.chmod(0o700)
                    for child in item.iterdir(): child.unlink()
                    item.rmdir()
            self.journal().unlink()

    def test_failed_close_after_promotion_cannot_return_zero(self):
        real_close = self.pm.close_fd
        fired = False
        def close(fd):
            nonlocal fired
            real_close(fd)
            if not fired and (self.root / 'run/autodata/api').exists():
                fired = True
                raise self.pm.RecoveryIncomplete()
        with patch.object(self.pm, 'close_fd', side_effect=close):
            code, output = self.install()
        self.assertEqual(code, 6)
        self.assertTrue(output['secret_material_committed'])
        self.assertEqual(output['commit_state'], 'incomplete')
        self.assertTrue((self.root / 'run/autodata/api').exists())
        self.assertEqual(json.loads(self.journal().read_text())['operation_status'], 'unconfirmed')

    def test_no_replace_target_race_preserves_existing_tree(self):
        original = self.pm.module_bytes
        def module(data, path, name):
            result = original(data, path, name)
            if path.endswith('host_install.py'):
                real_rename = result._rename_noreplace
                def rename(parent, old, new):
                    if new == 'api':
                        os.mkdir('api', 0o700, dir_fd=parent)
                        marker = os.open('api/marker', os.O_CREAT | os.O_WRONLY, 0o600, dir_fd=parent)
                        os.write(marker, b'preexisting'); os.close(marker)
                    return real_rename(parent, old, new)
                result._rename_noreplace = rename
            return result
        with patch.object(self.pm, 'module_bytes', side_effect=module):
            self.assertNotEqual(self.install()[0], 0)
        self.assertEqual((self.root / 'run/autodata/api/marker').read_bytes(), b'preexisting')

    def test_lock_conflict_and_replacement_deny(self):
        state = self.root / 'run/autodata/state'; state.mkdir(mode=0o700)
        lock = state / 'operation.lock'; lock.write_bytes(b''); lock.chmod(0o600)
        fd = os.open(lock, os.O_RDWR)
        import fcntl
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.install()[0], 3)
        finally: os.close(fd)
        def hook(target):
            if self.stream_reads and lock.exists():
                lock.unlink(); lock.write_bytes(b''); lock.chmod(0o600)
        self.hook = hook
        self.assertNotEqual(self.install()[0], 0)
        self.assertFalse((self.root / 'run/autodata/api').exists())

    def test_mount_flag_or_uuid_drift_denies_before_read(self):
        def invalid(host, fd, target, budget):
            value = json.loads(self.probe(host, fd, target, budget))
            value['filesystems'][0]['options'] = 'rw'
            value['filesystems'][0]['uuid'] = AUTH if target.endswith('autodata') else None
            return encoded(value)
        with patch.object(self.pm, 'probe', side_effect=invalid):
            self.assertEqual(self.install()[0], 3)
        self.assertEqual(self.stream_reads, 0)

    def test_guard_drift_during_intent_fsync_blocks_material_creation(self):
        real_fsync = os.fsync
        real_mkdir = os.mkdir
        drifted = False
        creations = []
        def fsync(fd):
            nonlocal drifted
            real_fsync(fd)
            if self.journal().exists() and not drifted:
                drifted = True
                self.put('etc/machine-id', b'd' * 32, 0o444)
        def mkdir(name, *args, **kwargs):
            if str(name).startswith('.private-'): creations.append(name)
            return real_mkdir(name, *args, **kwargs)
        with patch.object(self.pm.os, 'fsync', side_effect=fsync), patch.object(self.pm.os, 'mkdir', side_effect=mkdir):
            self.assertNotEqual(self.install()[0], 0)
        self.assertEqual(creations, [])

    def test_symlink_hardlink_and_parent_permissions_deny_without_input(self):
        approval = self.root / 'etc/autodata/private-material-approval.json'
        alias = self.root / 'etc/autodata/alias'
        os.link(approval, alias)
        self.assertEqual(self.install()[0], 3)
        alias.unlink()
        approval.rename(alias); approval.symlink_to('alias')
        self.assertEqual(self.install()[0], 3)
        approval.unlink(); alias.rename(approval)
        private = self.root / 'etc/autodata'; private.chmod(0o755)
        self.assertEqual(self.install()[0], 3)
        private.chmod(0o700)
        self.assertEqual(self.stream_reads, 0)

    def test_unsafe_substitution_prevents_cleanup(self):
        real_write = os.write
        swapped = False
        def write(fd, data):
            nonlocal swapped
            if not swapped and any(value in bytes(data) for value in self.values.values()):
                swapped = True
                original = self.root / ('run/autodata/.private-' + AUTH)
                original.rename(self.root / 'run/autodata/retained-owned-tree')
                original.mkdir(mode=0o700)
                (original / 'unrelated').write_bytes(b'preserve-me')
                raise OSError('redacted')
            return real_write(fd, data)
        with patch.object(self.pm.os, 'write', side_effect=write):
            code, output = self.install()
        self.assertEqual(code, 6)
        self.assertEqual((self.root / ('run/autodata/.private-' + AUTH + '/unrelated')).read_bytes(), b'preserve-me')
        self.assertEqual(json.loads(self.journal().read_text())['operation_status'], 'unconfirmed')

    def test_budget_exhausted_during_rename_preserves_promoted_material(self):
        real_module = self.pm.module_bytes
        def module(*args):
            result = real_module(*args)
            if args[1].endswith('host_install.py'):
                real_rename = result._rename_noreplace
                def rename(parent, old, new):
                    real_rename(parent, old, new)
                    if new == 'api': self.clock = 301
                result._rename_noreplace = rename
            return result
        with patch.object(self.pm, 'module_bytes', side_effect=module):
            code, output = self.install()
        self.assertEqual(code, 6)
        self.assertTrue(output['secret_material_committed'])
        self.assertTrue((self.root / 'run/autodata/api').exists())
        self.assertFalse(output['one_service_private_material_installed'])
        self.assertEqual(json.loads(self.journal().read_text())['operation_status'], 'unconfirmed')

    def test_missing_run_mount_fails_without_creating_boot_persistence(self):
        (self.root / 'run/autodata').rmdir()
        self.assertEqual(self.install()[0], 3)
        self.assertEqual(self.stream_reads, 0)
        self.assertFalse((self.root / 'etc/systemd').exists())
        self.assertFalse((self.root / 'opt/autodata/current').exists())
        self.assertFalse(self.journal().exists())

    def test_redaction_across_all_persistent_input_and_journal_files(self):
        code, output = self.install()
        self.assertEqual(code, 0)
        persisted = b''.join(path.read_bytes() for base in ('etc', 'var', 'opt')
                             for path in (self.root / base).rglob('*') if path.is_file())
        observed = persisted + encoded(output)
        for value in self.values.values():
            for representation in (value, base64.b64encode(value), hashed(value).encode()):
                self.assertNotIn(representation, observed)
        self.assertNotIn(hashed(encoded(self.frame)).encode(), observed)
        self.assertEqual(set(p.name for p in (self.root / 'var/lib/autodata/operations').iterdir()), {'private-material-' + AUTH + '.json'})



class PipeAndProbeTests(unittest.TestCase):
    def setUp(self):
        self.pm = load()
        self.clock = 0
        self.guard = patch.object(self.pm.time, 'monotonic', side_effect=lambda: self.clock)
        self.guard.start(); self.addCleanup(self.guard.stop)

    def fifo(self, inode=10):
        from types import SimpleNamespace
        return SimpleNamespace(st_mode=stat.S_IFIFO | 0o600, st_dev=1, st_ino=inode)

    def selector(self, ready=True):
        owner = self
        class Selector:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def register(self, fd, flags): pass
            def select(self, timeout):
                if not ready: owner.clock += timeout
                return [True] if ready else []
        return Selector

    def test_pipe_only_bounded_eof_and_identity_drift(self):
        budget = self.pm.Budget()
        with patch.object(self.pm.os, 'fstat', return_value=self.fifo()), \
             patch.object(self.pm.os, 'read', side_effect=[b'{}', b'']), \
             patch.object(self.pm.selectors, 'DefaultSelector', self.selector()):
            self.assertEqual(self.pm.read_stream(0, budget), b'{}')
        for mode in (stat.S_IFREG, stat.S_IFSOCK, stat.S_IFCHR):
            node = self.fifo(); node.st_mode = mode
            with patch.object(self.pm.os, 'fstat', return_value=node), self.assertRaises(self.pm.InvalidInput):
                self.pm.read_stream(0, budget)
        with patch.object(self.pm.os, 'fstat', side_effect=[self.fifo(), self.fifo(11)]), \
             patch.object(self.pm.selectors, 'DefaultSelector', self.selector()), self.assertRaises(self.pm.InvalidInput):
            self.pm.read_stream(0, budget)

    def test_pipe_timeout_consumes_shared_budget_and_oversize_denies(self):
        with patch.object(self.pm.os, 'fstat', return_value=self.fifo()), \
             patch.object(self.pm.selectors, 'DefaultSelector', self.selector(False)), self.assertRaises(self.pm.Expired):
            self.pm.read_stream(0, self.pm.Budget())
        self.assertEqual(self.clock, 270)
        self.clock = 0
        with patch.object(self.pm.os, 'fstat', return_value=self.fifo()), \
             patch.object(self.pm.os, 'read', return_value=b'x' * 65536), \
             patch.object(self.pm.selectors, 'DefaultSelector', self.selector()), self.assertRaises(self.pm.InvalidInput):
            self.pm.read_stream(0, self.pm.Budget())

    def test_probe_uses_fixed_command_and_fake_process_cleanup(self):
        import types
        host = self.pm.module_bytes((HERE / 'host_install.py').read_bytes(), '/opt/autodata/bin/host_install.py', 'fake_probe_host')
        calls = []
        class Pipe:
            def fileno(self): return 77
            def close(self): calls.append('close')
        class Child:
            pid = 999999
            stdout = Pipe()
            def wait(self, timeout): calls.append(('wait', timeout)); return 0
        def popen(argv, **kwargs):
            calls.append((argv, kwargs)); return Child()
        with patch.object(host.subprocess, 'Popen', side_effect=popen), \
             patch.object(host.selectors, 'DefaultSelector', self.selector()), \
             patch.object(host.os, 'read', side_effect=[b'{}', b'']), \
             patch.object(host.os, 'killpg', side_effect=lambda pid, sig: calls.append(('kill', pid, sig))):
            self.assertEqual(self.pm.probe(host, 42, '/run/autodata', self.pm.Budget()), b'{}')
        self.assertEqual(calls[0][0], ['/proc/self/fd/42', '--json', '--list', '--mountpoint', '/run/autodata', '--output', 'TARGET,UUID,FSTYPE,OPTIONS'])
        self.assertEqual(calls[0][1]['env'], {})
        self.assertTrue(calls[0][1]['start_new_session'])
        self.assertEqual(len([c for c in calls if c[0] == 'kill']), 2)
        self.assertEqual(calls[-1], 'close')

    def test_probe_descendant_pipe_timeout_and_reap_error_are_redacted(self):
        host = self.pm.module_bytes((HERE / 'host_install.py').read_bytes(), '/opt/autodata/bin/host_install.py', 'fake_probe_host')
        class Pipe:
            def close(self): pass
        class Child:
            pid = 999999
            stdout = Pipe()
            def wait(self, timeout): return 0
        kills = []
        with patch.object(host.subprocess, 'Popen', return_value=Child()), \
             patch.object(host.selectors, 'DefaultSelector', self.selector(False)), \
             patch.object(host.os, 'killpg', side_effect=lambda pid, sig: kills.append(sig)), self.assertRaises(self.pm.Expired):
            self.pm.probe(host, 42, '/var/lib/autodata', self.pm.Budget())
        self.assertEqual(len(kills), 2)
        self.clock = 0
        def unreap(timeout): raise host.subprocess.TimeoutExpired('redacted', timeout)
        child = Child(); child.wait = unreap
        with patch.object(host.subprocess, 'Popen', return_value=child), \
             patch.object(host.selectors, 'DefaultSelector', self.selector(False)), \
             patch.object(host.os, 'killpg', return_value=None), self.assertRaises(self.pm.RecoveryIncomplete):
            self.pm.probe(host, 42, '/var/lib/autodata', self.pm.Budget())


class CliDenialTests(unittest.TestCase):
    def test_isolated_cli_denial_emits_only_bounded_redacted_json(self):
        import subprocess
        import sys
        for args in ([], ['install', SHA, 'postgres'], ['exec', SHA, 'api'], ['install', SHA, 'api', '/tmp']):
            result = subprocess.run([sys.executable, '-I', str(HERE / 'private_material.py'), *args],
                                    input=b'synthetic-cli-secret-sentinel', capture_output=True, timeout=5,
                                    env={'UNTRUSTED_VALUE': 'synthetic-env-secret-sentinel'}, cwd='/')
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stderr, b'')
            self.assertLessEqual(len(result.stdout), 65536)
            output = json.loads(result.stdout)
            self.assertEqual(output['failure_code'], 'invalid_input')
            self.assertNotIn(b'synthetic-', result.stdout)


if __name__ == '__main__':
    unittest.main()
