"""Inert installer tests: private temporary inodes and intercepted fixed probes only."""
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

import test_host_runtime as runtime_tests

HERE = Path(__file__).resolve().parent
SHA = 'a' * 40
AUTH = '12345678-1234-4234-8234-123456789abc'
HASH = 'b' * 64


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def hashed(value):
    return hashlib.sha256(value).hexdigest()


def load_installer():
    path = HERE / 'host_install.py'
    if not path.exists():
        raise AssertionError('inert installation implementation is missing')
    spec = importlib.util.spec_from_file_location('host_install_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.module = load_installer()
        source = runtime_tests.ContractTests()
        source.setUp()
        self.addCleanup(source.doCleanups)
        self.config = copy.deepcopy(source.config)
        self.manifest = copy.deepcopy(source.manifest)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o755)
        for name in ('etc', 'var', 'var/lib', 'opt', 'run', 'usr', 'usr/bin', 'opt/autodata/bin'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
            (self.root / name).chmod(0o755)
        for name in ('etc/autodata', 'etc/autodata/publisher-accepted', 'opt/autodata',
                     'opt/autodata/releases', 'var/lib/autodata', 'var/lib/autodata/incoming',
                     'run/autodata'):
            (self.root / name).mkdir(exist_ok=True)
            (self.root / name).chmod(0o700)
        self.inbox = self.root / ('var/lib/autodata/incoming/' + SHA)
        for name in ('', 'db', 'db/migrations', 'scripts', 'scripts/dev'):
            (self.inbox / name).mkdir(parents=True, exist_ok=True)
            (self.inbox / name).chmod(0o700)
        sql = b'SELECT 1;\n'
        runner = b'#!/bin/sh\nexit 0\n'
        self.manifest['migrations']['runner_sha256'] = hashed(runner)
        files = self.manifest['migrations']['files']
        for item in files:
            item['sha256'] = hashed(sql)
            self.put('var/lib/autodata/incoming/' + SHA + '/db/migrations/' + item['name'], sql, 0o444)
        self.manifest['migrations']['inventory_sha256'] = hashed(encoded(files))
        self.put('var/lib/autodata/incoming/' + SHA + '/scripts/dev/migrate_sql.sh', runner, 0o444)
        self.put('var/lib/autodata/incoming/' + SHA + '/release.json', encoded(self.manifest), 0o600)
        self.put('etc/autodata/host.json', encoded(self.config), 0o600)
        self.put('etc/autodata/publisher-accepted/' + SHA + '.json', b'{"opaque":"redacted-owner-evidence"}', 0o600)
        for name in ('runtime-check.py', 'release.schema.json'):
            self.put('opt/autodata/bin/' + name, (HERE / name).read_bytes(), 0o444)
        self.put('usr/bin/findmnt', b'not executed in fixture', 0o555)
        self.approval = {
            'schema_version': 1, 'operation': 'install-inert-staging-release', 'authorization_id': AUTH,
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'source_sha': SHA, 'service_config_sha256': hashed(encoded(self.config)),
            'manifest_raw_sha256': hashed(encoded(self.manifest)),
            'manifest_canonical_sha256': hashed(encoded(self.manifest)),
            'publisher_verification_receipt_sha256': hashed((self.root / ('etc/autodata/publisher-accepted/' + SHA + '.json')).read_bytes()),
            'owner_publisher_acceptance_evidence_sha256': HASH,
            'owner_data_device_binding_evidence_sha256': HASH,
            'owner_bare_host_evidence_sha256': HASH,
            'runtime_helper_sha256': hashed((HERE / 'runtime-check.py').read_bytes()),
            'release_schema_sha256': hashed((HERE / 'release.schema.json').read_bytes()),
            'findmnt_binary_sha256': hashed(b'not executed in fixture'),
            'files': [{'path': str(p.relative_to(self.inbox)), 'bytes': p.stat().st_size, 'sha256': hashed(p.read_bytes())}
                      for p in sorted(self.inbox.rglob('*')) if p.is_file()]}
        self.save_approval()
        self.probes = []
        self.before_probe = None
        self.probe_count = 0
        real_read = Path.read_bytes
        fixture_schema = (HERE / 'release.schema.json').read_bytes()
        guards = [patch.object(self.module, '_open_root', lambda: os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)),
                  patch.object(self.module, '_owned', lambda s: s.st_uid == os.getuid() and s.st_gid == os.getgid()),
                  patch.object(self.module.os, 'geteuid', return_value=0),
                  patch.object(self.module, '_probe', self.probe),
                  patch.object(Path, 'read_bytes', lambda p: fixture_schema if str(p) == '/opt/autodata/bin/release.schema.json' else real_read(p))]
        for guard in guards:
            guard.start()
            self.addCleanup(guard.stop)

    def put(self, path, data, mode):
        target = self.root / path
        if target.exists():
            target.chmod(0o600)
        target.write_bytes(data)
        target.chmod(mode)

    def save_approval(self):
        self.put('etc/autodata/install-approval.json', encoded(self.approval), 0o600)

    def probe(self, fd, target, deadline):
        self.probes.append(target)
        self.probe_count += 1
        if self.before_probe:
            self.before_probe(target)
        entry = {'target': target, 'uuid': None, 'fstype': 'tmpfs', 'options': 'rw,nosuid,nodev,noexec'}
        if target == '/var/lib/autodata':
            entry.update(uuid=self.config['resources']['data_disk_filesystem_uuid'], fstype='ext4', options='rw')
        return encoded({'filesystems': [entry]})

    def install(self):
        code, value = self.module.install_cli(SHA)
        self.assertLessEqual(len(encoded(value)), 65536)
        self.assertNotIn('redacted-owner-evidence', str(value))
        self.assertFalse(value['deployment_authorized'])
        self.assertTrue(value['inert_installation_only'])
        for check in ('schema', 'services', 'secrets', 'cached_images', 'runtime_evidence'):
            self.assertIs(value['checks'][check], False)
        return code, value

    def assert_no_material(self):
        self.assertEqual(list((self.root / 'opt/autodata/releases').iterdir()), [])
        self.assertFalse((self.root / 'var/lib/autodata/operations').exists())
        self.assertFalse((self.root / 'opt/autodata/current').exists())

    def test_staging_install_material_only(self):
        code, receipt = self.install()
        self.assertEqual(code, 0, receipt)
        self.assertEqual(receipt['commit_state'], 'receipt_committed')
        self.assertTrue(receipt['release_material_committed'])
        release = self.root / ('opt/autodata/releases/' + SHA)
        self.assertEqual(stat.S_IMODE(release.stat().st_mode), 0o500)
        for item in self.approval['files']:
            target = release / item['path']
            self.assertEqual(hashed(target.read_bytes()), item['sha256'])
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600 if item['path'] == 'release.json' else 0o444)
        persisted = self.root / ('var/lib/autodata/operations/' + AUTH + '.json')
        self.assertEqual(json.loads(persisted.read_text()), receipt)
        self.assertEqual(stat.S_IMODE(persisted.stat().st_mode), 0o600)
        self.assertFalse((self.root / 'opt/autodata/current').exists())
        self.assertFalse((self.root / 'run/autodata/secrets').exists())
        self.assertEqual(set(self.probes), {'/var/lib/autodata', '/run/autodata'})

    def test_missing_publisher_acceptance_blocks_before_write(self):
        (self.root / ('etc/autodata/publisher-accepted/' + SHA + '.json')).unlink()
        self.assertEqual(self.install()[0], 3)
        self.assert_no_material()

    def test_hash_shaped_untrusted_receipt_is_not_approval(self):
        (self.root / 'etc/autodata/install-approval.json').unlink()
        self.assertEqual(self.install()[0], 3)
        self.assert_no_material()

    def test_production_denied_before_approval_is_read(self):
        self.config['environment'] = 'production'
        self.config['public_origin'] = 'https://cars.tk'
        self.put('etc/autodata/host.json', encoded(self.config), 0o600)
        (self.root / 'etc/autodata/install-approval.json').unlink()
        self.assertEqual(self.install()[0], 3)
        self.assertEqual(self.probes, [])
        self.assert_no_material()

    def test_approval_unknown_duplicate_null_expired_source_config_denied(self):
        for field, value in (('extra', True), ('source_sha', 'c' * 40), ('service_config_sha256', 'd' * 64),
                             ('expires_at', '2020-01-01T00:00:00Z'), ('expires_at', None), ('schema_version', True),
                             ('authorization_id', '../../bad')):
            original = copy.deepcopy(self.approval)
            self.approval[field] = value
            self.save_approval()
            self.assertEqual(self.install()[0], 3, field)
            self.assert_no_material()
            self.approval = original
        self.put('etc/autodata/install-approval.json', b'{"schema_version":1,"schema_version":1}', 0o600)
        self.assertEqual(self.install()[0], 3)

    def test_standard_protected_0755_and_private_0700_accepted(self):
        self.assertEqual(self.install()[0], 0)

    def test_standard_parent_writable_or_private_0755_denied(self):
        for name, mode in (('', 0o1777), ('var', 0o775), ('var/lib', 0o757),
                           ('etc/autodata', 0o755), ('var/lib/autodata', 0o755),
                           ('opt/autodata/releases', 0o755), ('run/autodata', 0o755)):
            directory = self.root / name
            old = directory.stat().st_mode & 0o7777
            directory.chmod(mode)
            self.assertEqual(self.install()[0], 3, name)
            self.assert_no_material()
            directory.chmod(old)

    def test_symlink_parent_denied(self):
        directory = self.root / 'var/lib'
        directory.rename(self.root / 'var/real-lib')
        directory.symlink_to('real-lib')
        self.assertEqual(self.install()[0], 3)
        self.assert_no_material()

    def test_extra_secret_directory_and_file_denied(self):
        for name in ('secrets', 'extra-empty'):
            (self.inbox / name).mkdir()
            self.assertEqual(self.install()[0], 3)
            self.assert_no_material()
            (self.inbox / name).rmdir()
        self.put('var/lib/autodata/incoming/' + SHA + '/token.env', b'NEVER_EMIT_TOKEN', 0o600)
        code, value = self.install()
        self.assertEqual(code, 3)
        self.assertNotIn('NEVER_EMIT_TOKEN', str(value))
        self.assert_no_material()

    def test_link_fifo_and_source_hash_drift_denied(self):
        runner = self.inbox / 'scripts/dev/migrate_sql.sh'
        original = runner.read_bytes()
        runner.unlink()
        os.mkfifo(runner, 0o444)
        self.assertEqual(self.install()[0], 3)
        runner.unlink()
        runner.symlink_to(self.inbox / 'release.json')
        self.assertEqual(self.install()[0], 3)
        runner.unlink()
        runner.write_bytes(original)
        runner.chmod(0o444)
        os.link(runner, self.root / 'extra-link')
        self.assertEqual(self.install()[0], 3)
        (self.root / 'extra-link').unlink()
        runner.chmod(0o600)
        runner.write_bytes(b'drift')
        runner.chmod(0o444)
        self.assertEqual(self.install()[0], 3)
        self.assert_no_material()

    def test_wrong_or_unmounted_disk_never_initializes_boot_disk(self):
        with patch.object(self.module, '_probe', return_value=b'{"filesystems":[]}'):
            self.assertEqual(self.install()[0], 3)
        self.assert_no_material()
        self.assertFalse((self.root / 'run/autodata/state').exists())

    def test_lock_busy_no_persistent_write(self):
        import fcntl
        state = self.root / 'run/autodata/state'
        state.mkdir(mode=0o700)
        lock = state / 'operation.lock'
        lock.write_bytes(b'')
        lock.chmod(0o600)
        with lock.open('rb') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.install()[0], 3)
        self.assert_no_material()

    def test_existing_release_exact_rerun_only(self):
        self.assertEqual(self.install()[0], 0)
        self.assertEqual(self.install()[0], 0)
        target = self.root / ('opt/autodata/releases/' + SHA + '/release.json')
        target.write_bytes(b'drift')
        code, value = self.install()
        self.assertEqual(code, 3)
        self.assertFalse(value['release_material_committed'])

    def test_preexisting_temp_refused_without_removal(self):
        temp = self.root / ('opt/autodata/releases/.install-' + AUTH)
        temp.mkdir(mode=0o700)
        (temp / 'keep').write_bytes(b'keep')
        self.assertEqual(self.install()[0], 3)
        self.assertEqual((temp / 'keep').read_bytes(), b'keep')

    def test_current_object_and_rollback_denied(self):
        (self.root / 'opt/autodata/current').symlink_to('missing')
        self.assertEqual(self.install()[0], 3)
        self.assert_no_material()

    def test_copy_failure_cleanup_bounded(self):
        with patch.object(self.module, '_write_all', side_effect=OSError('PRIVATE_FAILURE')):
            code, receipt = self.install()
        self.assertEqual(code, 4)
        self.assertNotIn('PRIVATE_FAILURE', str(receipt))
        self.assert_no_material()

    def test_receipt_failure_after_commit_incomplete(self):
        with patch.object(self.module, '_persist_receipt', side_effect=OSError('PRIVATE_FAILURE')):
            code, receipt = self.install()
        self.assertEqual(code, 6)
        self.assertTrue(receipt['release_material_committed'])
        self.assertEqual(receipt['failure_code'], 'recovery_incomplete')
        self.assertTrue((self.root / ('opt/autodata/releases/' + SHA)).exists())

    def test_mount_replacement_before_commit_denied(self):
        def swap(target):
            if self.probe_count == 3:
                data = self.root / 'var/lib/autodata'
                data.rename(self.root / 'var/lib/old-data')
                data.mkdir(mode=0o700)
        self.before_probe = swap
        code, receipt = self.install()
        self.assertNotEqual(code, 0)
        self.assertFalse(receipt['release_material_committed'])
        self.assert_no_material()

    def test_argument_surface_and_redaction(self):
        for value in ('', '../bad', SHA.upper(), SHA + '\n', None):
            code, receipt = self.module.install_cli(value)
            self.assertEqual(code, 2)
            self.assertIsNone(receipt['source_sha'])

    def test_inbox_replacement_after_validation_denied(self):
        def replace(target):
            if self.probe_count == 3:
                original = self.inbox / 'scripts/dev/migrate_sql.sh'
                data = original.read_bytes()
                original.unlink()
                original.write_bytes(data)
                original.chmod(0o444)
        self.before_probe = replace
        code, receipt = self.install()
        self.assertNotEqual(code, 0)
        self.assertFalse(receipt['release_material_committed'])
        self.assert_no_material()

    def test_temporary_tree_replacement_before_promotion_denied(self):
        def replace(target):
            if self.probe_count == 3:
                base = self.root / ('opt/autodata/releases/.install-' + AUTH)
                base.chmod(0o700)
                original = base / 'release.json'
                original.unlink()
                original.write_bytes(b'injected')
                original.chmod(0o600)
                base.chmod(0o500)
        self.before_probe = replace
        code, receipt = self.install()
        self.assertEqual(code, 6)
        self.assertFalse(receipt['release_material_committed'])
        self.assertFalse((self.root / ('opt/autodata/releases/' + SHA)).exists())
        self.assertEqual((self.root / ('opt/autodata/releases/.install-' + AUTH + '/release.json')).read_bytes(), b'injected')

    def test_noreplace_race_preserves_existing_tree(self):
        real = self.module._rename_noreplace
        def race(parent, old, new):
            os.mkdir(new, 0o500, dir_fd=parent)
            real(parent, old, new)
        with patch.object(self.module, '_rename_noreplace', race):
            code, receipt = self.install()
        self.assertEqual(code, 4)
        self.assertFalse(receipt['release_material_committed'])
        self.assertEqual(list((self.root / ('opt/autodata/releases/' + SHA)).iterdir()), [])
        self.assertFalse((self.root / ('opt/autodata/releases/.install-' + AUTH)).exists())

    def test_same_authorization_changed_approval_denied(self):
        self.assertEqual(self.install()[0], 0)
        self.approval['owner_bare_host_evidence_sha256'] = 'f' * 64
        self.save_approval()
        self.assertEqual(self.install()[0], 3)

    def test_image_tag_and_unknown_secret_alias_denied(self):
        for mutate in (lambda m: m['images']['api'].update(reference='registry.example/api:latest'),
                       lambda m: m['secret_versions']['api'].update(extra='projects/autodata-host/secrets/a/versions/latest'),
                       lambda m: m.update(rollback_source_sha='c' * 40)):
            original = copy.deepcopy(self.manifest)
            mutate(self.manifest)
            data = encoded(self.manifest)
            self.put('var/lib/autodata/incoming/' + SHA + '/release.json', data, 0o600)
            self.approval['manifest_raw_sha256'] = self.approval['manifest_canonical_sha256'] = hashed(data)
            for item in self.approval['files']:
                if item['path'] == 'release.json':
                    item.update(bytes=len(data), sha256=hashed(data))
            self.save_approval()
            self.assertEqual(self.install()[0], 3)
            self.assert_no_material()
            self.manifest = original

    def test_approval_inventory_duplicate_overflow_traversal_denied(self):
        for change in (lambda a: a['files'].append(a['files'][0].copy()),
                       lambda a: a['files'][0].update(bytes=1048577),
                       lambda a: a['files'][0].update(path='../escape'),
                       lambda a: a['files'].reverse()):
            original = copy.deepcopy(self.approval)
            change(self.approval)
            self.save_approval()
            self.assertEqual(self.install()[0], 3)
            self.assert_no_material()
            self.approval = original

    def test_tool_or_schema_drift_and_reboot_missing_tmpfs_denied(self):
        for relative in ('opt/autodata/bin/runtime-check.py', 'opt/autodata/bin/release.schema.json', 'usr/bin/findmnt'):
            original = (self.root / relative).read_bytes()
            self.put(relative, b'drift', 0o444)
            self.assertEqual(self.install()[0], 3)
            self.assert_no_material()
            self.put(relative, original, 0o444)
        original_probe = self.probe
        def disk_backed(fd, target, deadline):
            data = json.loads(original_probe(fd, target, deadline))
            if target == '/run/autodata':
                data['filesystems'][0]['fstype'] = 'ext4'
            return encoded(data)
        with patch.object(self.module, '_probe', disk_backed):
            self.assertEqual(self.install()[0], 3)
        self.assert_no_material()

    def test_cleanup_unlink_failure_incomplete(self):
        with patch.object(self.module, '_write_all', side_effect=OSError('write failure')), \
             patch.object(self.module.os, 'unlink', side_effect=OSError('unlink failure')):
            code, receipt = self.install()
        self.assertEqual(code, 6)
        self.assertEqual(receipt['commit_state'], 'incomplete')
        self.assertFalse(receipt['release_material_committed'])

    def test_missing_noreplace_primitive_is_dependency_failure(self):
        with patch.object(self.module, '_rename_noreplace', side_effect=self.module.Denied):
            self.assertEqual(self.install()[0], 3)
        self.assert_no_material()


class ProbeAndLauncherTests(unittest.TestCase):
    def setUp(self):
        self.module = load_installer()

    def test_install_launcher_fixed_isolated_and_empty_environment(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            probe = base / 'probe.py'
            probe.write_text("import os,sys\ndef install_cli(sha):\n return 0, {'sha':sha,'env':dict(os.environ),'isolated':sys.flags.isolated,'cwd':os.getcwd()}\n")
            script = base / 'deploy.sh'
            script.write_text((HERE / 'deploy.sh').read_text().replace('/opt/autodata/bin/host_install.py', str(probe)))
            env = {'PATH': '/not-real', 'PYTHONHOME': '/not-real', 'PYTHONPATH': str(base), 'TOKEN': 'NEVER_EMIT'}
            result = subprocess.run(['/bin/sh', str(script), 'install', SHA], env=env, cwd=base,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual(value['sha'], SHA)
            self.assertEqual(value['isolated'], 1)
            self.assertEqual(value['cwd'], '/')
            self.assertTrue(set(value['env']).isdisjoint(env))
            self.assertEqual(result.stderr, '')
            for argv in (['start', SHA], ['stop', SHA], ['maintenance', SHA], ['resume', SHA],
                         ['install', SHA, '/caller/path'], ['install', '../bad']):
                result = subprocess.run(['/bin/sh', str(script), *argv], env=env, capture_output=True, text=True, timeout=5)
                self.assertIn(result.returncode, (2, 3))
                self.assertEqual(result.stderr, '')
                self.assertNotIn('NEVER_EMIT', result.stdout)

    def run_probe(self, body, short=False):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'probe'
            script.write_text('#!/usr/bin/python3\n' + body)
            script.chmod(0o500)
            fd = os.open(script, os.O_RDONLY)
            self.addCleanup(os.close, fd)
            children = []
            real_popen = subprocess.Popen
            def start(argv, **kwargs):
                self.assertEqual(argv, ['/proc/self/fd/' + str(fd), '--json', '--list', '--mountpoint',
                                        '/var/lib/autodata', '--output', 'TARGET,UUID,FSTYPE,OPTIONS'])
                self.assertEqual(kwargs['env'], {})
                self.assertEqual(kwargs['cwd'], '/')
                self.assertEqual(kwargs['pass_fds'], (fd,))
                child = real_popen(argv, **kwargs)
                children.append(child)
                return child
            deadline = self.module.Deadline()
            if short:
                import time
                deadline.end = time.monotonic() + 30.15
            with patch.object(self.module.subprocess, 'Popen', start):
                try:
                    return self.module._probe(fd, '/var/lib/autodata', deadline)
                finally:
                    for child in children:
                        self.assertIsNotNone(child.poll())
                        with self.assertRaises(ProcessLookupError):
                            os.kill(child.pid, 0)

    def test_probe_fixed_fd_bounded_output(self):
        self.assertEqual(self.run_probe("import os\nos.write(1,b'{}')\n"), b'{}')
        with self.assertRaises(self.module.Denied):
            self.run_probe("import os\nos.write(1,b'x'*131072)\n")

    def test_probe_timeout_child_reaped_and_stderr_discarded(self):
        with self.assertRaises(self.module.Expired):
            self.run_probe("import os,time\nos.write(2,b'NEVER_EMIT')\ntime.sleep(30)\n", short=True)


if __name__ == '__main__':
    unittest.main()
