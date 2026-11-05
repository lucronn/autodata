"""Disposable adapter tests. Production helpers are never invoked."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
RUN = '12345678-1234-4234-8234-123456789abc'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class Clock:
    value = 100.
    def monotonic(self): return self.value
    def utc(self): return datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
    def boot_id(self): return RUN


class Host:
    def __init__(self, module):
        self.m = module
        self.calls = []
        self.fail = None
        self.manifest = {'source_sha': 'a' * 40}
        self.config = {'resources': {'data_disk_filesystem_uuid': RUN}}
        self.checks = {'manifest': True, 'config': True}
    def preflight(self, verb, state=None):
        if self.fail == 'preflight': raise ValueError('private host error')
        return self.manifest, self.config
    def step(self, name, store, deadline):
        # Intent must already be durable before every mutating adapter call.
        assert store.read()['phase'] == name
        self.calls.append(name)
        if self.fail == name: raise ValueError('private host error')
        if name == 'dump':
            with store.create_dump() as output: output.write(b'PGDMP synthetic offline dump')
        if name == 'ready': self.checks.update(services=True, no_work=True)
    def observe_ready(self): self.checks.update(services=True, no_work=True)
    def verify_dump(self, store, deadline):
        self.calls.append('verify_dump')
        if self.fail == 'verify_dump': raise ValueError('private host error')
    def check_stopped(self):
        self.calls.append('check_stopped')
        if self.fail == 'check_stopped': raise ValueError('private host error')


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE / 'backup_restore.py').is_file(), 'backup lease implementation is missing')
        self.m = load('backup_restore_test', 'backup_restore.py')
        self.temp = tempfile.TemporaryDirectory(dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.store = self.m.LeaseStore(Path(self.temp.name), RUN, owner=__import__('os').getuid())
        self.host, self.clock = Host(self.m), Clock()
    def run_backup(self, verb): return self.m.run_backup(verb, RUN, self.host, self.store, self.clock)
    def test_begin_order_and_independent_cloud_receipt(self):
        code, receipt = self.run_backup('begin')
        self.assertEqual(code, 0)
        self.assertEqual(self.host.calls, ['maintenance', 'stop_writers', 'dump', 'verify_dump', 'stop_stateful', 'sync', 'check_stopped'])
        ops = load('backup_cloud_oracle', 'cloud-ops.py')
        ops._host(receipt, 'begin', 'quiesced', self.host.manifest, self.host.config, RUN)
        state = self.store.read()
        self.assertEqual(state['deadline'], 1900.)
        self.assertFalse(state['incomplete'])
    def test_resume_is_idempotent_and_export_matches_cloud_oracle(self):
        self.assertEqual(self.run_backup('begin')[0], 0)
        self.assertEqual(self.run_backup('resume')[0], 0)
        count = len(self.host.calls)
        self.assertEqual(self.run_backup('resume')[0], 0)
        self.assertEqual(len(self.host.calls), count)
        code, status = self.run_backup('status')
        self.assertEqual(code, 0)
        ops = load('backup_cloud_oracle', 'cloud-ops.py')
        ops._host(status, 'status', 'resumed', self.host.manifest, self.host.config, RUN)
        output = io.BytesIO()
        self.m.export_archive(self.store, self.host.manifest, status, output)
        members = ops.verify_export(output.getvalue(), self.host.manifest, status)
        self.assertEqual(members['postgres.dump'], b'PGDMP synthetic offline dump')
    def test_invalid_arguments_never_reach_host(self):
        for verb, run in [('other', RUN), ('begin', RUN.upper()), ('begin', 'not-a-uuid'), ('begin', '12345678-1234-1234-8234-123456789abc')]:
            code, _ = self.m.run_backup(verb, run, self.host, self.store, self.clock)
            self.assertEqual(code, 2)
        self.assertEqual(self.host.calls, [])
    def test_failed_preflight_has_no_lease_or_mutations(self):
        self.host.fail = 'preflight'
        self.assertEqual(self.run_backup('begin')[0], 3)
        self.assertFalse(self.store.exists())
        self.assertEqual(self.host.calls, [])
    def test_run_uuid_never_reused(self):
        self.run_backup('begin')
        calls = list(self.host.calls)
        self.assertNotEqual(self.run_backup('begin')[0], 0)
        self.assertEqual(self.host.calls, calls)
    def test_failure_at_each_begin_step_recovers_but_never_passes(self):
        for step in ('maintenance', 'stop_writers', 'dump', 'verify_dump', 'stop_stateful', 'sync', 'check_stopped'):
            with self.subTest(step=step):
                with tempfile.TemporaryDirectory(dir='/tmp') as root:
                    store = self.m.LeaseStore(Path(root), RUN, owner=__import__('os').getuid())
                    host = Host(self.m); host.fail = step
                    code, receipt = self.m.run_backup('begin', RUN, host, store, self.clock)
                    self.assertNotEqual(code, 0)
                    self.assertTrue(store.read()['incomplete'])
                    self.assertIn('start_stateful', host.calls)
                    self.assertEqual(receipt['status'], 'failed')
                    self.assertNotIn('private host error', str(receipt))
    def test_failed_resume_stays_incomplete_and_keeps_maintenance(self):
        self.run_backup('begin'); self.host.fail = 'start_stateful'
        self.assertEqual(self.run_backup('resume')[0], 6)
        state = self.store.read()
        self.assertTrue(state['incomplete'])
        self.assertNotIn('open_ingress', self.host.calls)
    def test_changed_release_or_dump_is_rejected(self):
        self.run_backup('begin')
        self.host.manifest['source_sha'] = 'b' * 40
        self.assertNotEqual(self.run_backup('resume')[0], 0)
        self.assertNotIn('start_stateful', self.host.calls)
    def test_export_before_resume_and_corrupt_dump_fail(self):
        self.run_backup('begin')
        self.assertNotEqual(self.run_backup('export')[0], 0)
        self.run_backup('resume')
        (self.store.path / 'postgres.dump').write_bytes(b'corruption')
        self.assertNotEqual(self.run_backup('export')[0], 0)
    def test_expiry_and_boot_change_invalidate_success(self):
        for change in ('expired', 'boot'):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir='/tmp') as root:
                store = self.m.LeaseStore(Path(root), RUN, owner=__import__('os').getuid())
                host, clock = Host(self.m), Clock()
                self.m.run_backup('begin', RUN, host, store, clock)
                if change == 'expired': clock.value = 2000
                else: clock.boot_id = lambda: 'different-boot'
                code, _ = self.m.run_backup('resume', RUN, host, store, clock)
                self.assertEqual(code, 6)
                self.assertTrue(store.read()['incomplete'])
                self.assertIn('start_stateful', host.calls)
    def test_store_rejects_symlink_hardlink_and_replaced_directory(self):
        self.run_backup('begin')
        state = self.store.path / 'lease.json'
        saved = state.read_bytes(); state.unlink()
        outside = Path(self.temp.name) / 'outside'; outside.write_bytes(saved); outside.chmod(0o600)
        state.symlink_to(outside)
        with self.assertRaises((ValueError, OSError)): self.store.read()
        state.unlink(); __import__('os').link(outside, state)
        with self.assertRaises((ValueError, OSError)): self.store.read()
    def test_status_does_not_resume_abandoned_intent(self):
        self.run_backup('begin')
        state = self.store.read(); state.update(phase='stop_stateful', incomplete=True)
        self.store.write(state)
        calls = list(self.host.calls)
        self.assertNotEqual(self.run_backup('status')[0], 0)
        self.assertEqual(calls, self.host.calls)


if __name__ == '__main__': unittest.main()

class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.m = load('backup_stream_test', 'backup_restore.py')
        self.assertTrue(hasattr(self.m, 'stream_dump'), 'bounded dump streaming is missing')
    def test_streamed_dump_bound_and_timeout(self):
        import subprocess
        import sys
        with tempfile.TemporaryFile() as output:
            with self.assertRaises(ValueError):
                self.m.stream_dump([sys.executable, '-c', 'print("x"*10000)'], output, 2, maximum=100)
        with tempfile.TemporaryFile() as output:
            with self.assertRaises(subprocess.TimeoutExpired):
                self.m.stream_dump([sys.executable, '-c', 'import time;time.sleep(20)'], output, .05)
    def test_stream_clears_environment_and_redacts_stderr(self):
        import os
        import sys
        from unittest.mock import patch
        with tempfile.TemporaryFile() as output, patch.dict(os.environ, {'BACKUP_TEST_SECRET':'private'}):
            self.m.stream_dump([sys.executable, '-c', 'import os;print(os.getenv("BACKUP_TEST_SECRET","clean"))'], output, 2)
            output.seek(0); self.assertEqual(output.read(), b'clean\n')
        with tempfile.TemporaryFile() as output, self.assertRaises(ValueError) as caught:
            self.m.stream_dump([sys.executable, '-c', 'import sys;sys.stderr.write("secret");sys.exit(1)'], output, 2)
        self.assertNotIn('secret', str(caught.exception))

class BoundaryTests(unittest.TestCase):
    def setUp(self): self.m = load('backup_boundary_test', 'backup_restore.py')
    def test_cli_rejects_unknown_extra_or_non_uuid_before_import(self):
        from unittest.mock import patch
        for args in ([], ['begin'], ['begin', RUN, 'extra'], ['begin', RUN.upper()], ['shell', RUN], ['begin', '12345678-1234-1234-8234-123456789abc']):
            with patch.object(self.m, 'installed_host', side_effect=AssertionError('must not import/probe')):
                self.assertEqual(self.m.backup_cli(args)[0], 2)
    def test_wrappers_and_watchdog_definitions_have_fixed_bounds(self):
        shell = (HERE / 'backup-host.sh').read_text()
        self.assertIn('/usr/bin/env -i /usr/bin/python3 -I /opt/autodata/bin/backup_restore.py', shell)
        self.assertIn('cd /', shell)
        service = (HERE / 'autodata-backup-resume.service').read_text()
        self.assertIn('TimeoutStartSec=330', service)
        self.assertIn('User=root', service)
        self.assertIn('backup_restore.py watchdog', service)
        self.assertNotIn('Environment=', service)
        self.assertIn('OnUnitActiveSec=30s', (HERE / 'autodata-backup-resume.timer').read_text())
    def test_watchdog_bounds_run_directory_scan_before_recovery(self):
        from contextlib import contextmanager
        from unittest.mock import patch
        class Pins:
            def directory(self, *args): return 123
        class Host:
            pins = Pins()
        @contextmanager
        def host(seconds): yield Host()
        with patch.object(self.m, 'installed_host', host), patch.object(self.m.os, 'listdir', return_value=[RUN] * 101), patch.object(self.m, 'run_backup', side_effect=AssertionError('must not recover')):
            self.assertEqual(self.m.watchdog_cli()[0], 6)
    def test_state_schema_rejects_unknown_types_and_lease_extension(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as root:
            store = self.m.LeaseStore(Path(root), RUN, owner=__import__('os').getuid())
            self.m.run_backup('begin', RUN, Host(self.m), store, Clock())
            state = store.read()
            for key, value in [('schema_version', True), ('deadline', float('inf')), ('incomplete', 1), ('lease_expires_at','2027-11-05T12:30:00Z')]:
                altered = dict(state); altered[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError): self.m.validate_state(altered, RUN)
