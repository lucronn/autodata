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

class RestoreTarget:
    def __init__(self, module):
        self.m = module; self.calls = []
        self.manifest = {'source_sha':'a' * 40, 'images':{'postgres':{'image_id':'sha256:'+'b'*64}}, 'migrations':{'files':[{'name':'001_extensions.sql'}]}}
        self.inventory = {'schema_version':1, 'relations':{'schema_migrations':[{'version':'001_extensions'}]}, 'objects':[], 'jetstream':{}}
        host = Host(module); host.manifest = self.manifest
        self.temp = tempfile.TemporaryDirectory(dir='/tmp')
        self.store = module.LeaseStore(Path(self.temp.name), RUN, owner=__import__('os').getuid())
        module.run_backup('begin', RUN, host, self.store, Clock())
        module.run_backup('resume', RUN, host, self.store, Clock())
        _, self.status = module.run_backup('status', RUN, host, self.store, Clock())
        output = io.BytesIO(); module.export_archive(self.store, self.manifest, self.status, output)
        self.archive = output.getvalue()
        self.plan = {'schema_version':1,'run_id':RUN,'source_sha':'a'*40,
            'manifest_sha256':hashlib.sha256(module.canonical(self.manifest)).hexdigest(),
            'archive_sha256':hashlib.sha256(self.archive).hexdigest(), 'expected_disk_uuid':RUN,
            'restore_disk_uuid':'22345678-1234-4234-8234-123456789abc',
            'postgres_image_id':'sha256:'+'b'*64,
            'fixture_inventory_sha256':hashlib.sha256(module.canonical(self.inventory)).hexdigest()}
        self.observed = copy.deepcopy(self.inventory)
    def preflight(self, verb, run_id):
        self.calls.append('preflight')
        return self.plan, self.manifest, self.status, self.archive, self.inventory
    def create(self, plan, manifest): self.calls.append('create')
    def restore_dump(self, data): self.calls.append('restore'); assert data.startswith(b'PGDMP')
    def inspect(self, inventory): self.calls.append('inspect'); return self.observed
    def cleanup(self): self.calls.append('cleanup')


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.m = load('restore_test', 'backup_restore.py')
        self.assertTrue(hasattr(self.m, 'run_restore'), 'isolated restore boundary is missing')
        self.target = RestoreTarget(self.m); self.addCleanup(self.target.temp.cleanup)
    def run_restore(self): return self.m.run_restore('restore', RUN, self.target, None, Clock())
    def test_portable_restore_exact_inventory_and_cleanup(self):
        self.assertEqual(self.run_restore()[0], 0)
        self.assertEqual(self.target.calls, ['preflight','create','restore','inspect','cleanup'])
    def test_same_disk_unknown_keys_and_scalar_confusion_fail_before_creation(self):
        for key, value in [('restore_disk_uuid', RUN),('schema_version',True),('command','arbitrary'),('postgres_image_id','postgres:17')]:
            with self.subTest(key=key):
                original = dict(self.target.plan); self.target.plan[key] = value
                self.assertNotEqual(self.run_restore()[0], 0)
                self.assertNotIn('create', self.target.calls)
                self.target.plan = original; self.target.calls.clear()
    def test_corruption_and_migration_ledger_mismatch_fail(self):
        self.target.archive = self.target.archive[:-512] + b'x'*512
        self.assertNotEqual(self.run_restore()[0],0)
        self.assertNotIn('create',self.target.calls)
    def test_wrong_owner_missing_session_object_and_message_reject_independently(self):
        for key in ('relations','objects','jetstream'):
            with self.subTest(key=key):
                self.target.observed = copy.deepcopy(self.target.inventory)
                self.target.observed[key] = {'corrupt': True}
                self.assertNotEqual(self.run_restore()[0],0)
                self.assertEqual(self.target.calls[-1], 'cleanup')
    def test_cleanup_failure_cannot_be_passed(self):
        def fail(): raise ValueError('cleanup failure')
        self.target.cleanup = fail
        code, value = self.run_restore()
        self.assertEqual(code,6); self.assertFalse(value['cleanup_verified'])

class AdditionalGuardsTests(unittest.TestCase):
    setUp = LeaseTests.setUp
    run_backup = LeaseTests.run_backup
    def test_store_write_rejects_substituted_lease(self):
        self.run_backup('begin'); state = self.store.read()
        lease = self.store.path/'lease.json'; lease.unlink()
        outside = Path(self.temp.name)/'outside'; outside.write_bytes(b'private'); outside.chmod(0o600)
        lease.symlink_to(outside)
        with self.assertRaises((ValueError,OSError)): self.store.write(state)
        self.assertEqual(outside.read_bytes(),b'private')
    def test_replaced_run_directory_is_rejected(self):
        self.run_backup('begin')
        self.store.path.rename(self.store.path.with_name('old'))
        self.store.path.mkdir(mode=0o700)
        with self.assertRaises((ValueError,OSError)): self.store.read()
    def test_stale_boot_with_missing_secrets_marks_incomplete_without_starting_apps(self):
        self.run_backup('begin'); self.clock.boot_id=lambda:'different-boot'; self.host.fail='preflight'
        self.assertEqual(self.run_backup('resume')[0],6)
        self.assertTrue(self.store.read()['incomplete'])
        self.assertNotIn('start_apps',self.host.calls)


class ArchiveRestoreGuards(unittest.TestCase):
    setUp = RestoreTests.setUp
    run_restore = RestoreTests.run_restore
    def test_raw_duplicate_and_link_members_rejected_after_hashes_updated(self):
        for kind in ('duplicate','link','traversal'):
            with self.subTest(kind=kind):
                target=RestoreTarget(self.m); self.addCleanup(target.temp.cleanup)
                output=io.BytesIO()
                import tarfile
                with tarfile.open(fileobj=io.BytesIO(target.archive),mode='r:') as old, tarfile.open(fileobj=output,mode='w',format=tarfile.USTAR_FORMAT) as new:
                    for member in old.getmembers(): new.addfile(member,old.extractfile(member))
                    member=tarfile.TarInfo('postgres.dump' if kind=='duplicate' else '../outside' if kind=='traversal' else 'extra')
                    if kind=='link': member.type=tarfile.SYMTYPE; member.linkname='postgres.dump'
                    new.addfile(member)
                target.archive=output.getvalue(); target.plan['archive_sha256']=hashlib.sha256(target.archive).hexdigest()
                self.assertNotEqual(self.m.run_restore('restore',RUN,target,None,Clock())[0],0)
                self.assertNotIn('create',target.calls)
    def test_migration_ledger_and_inventory_bounds_fail_before_creation(self):
        target=self.target
        target.inventory['relations']['schema_migrations'][0]['version']='wrong'
        target.plan['fixture_inventory_sha256']=hashlib.sha256(self.m.canonical(target.inventory)).hexdigest()
        before=(target.archive,self.m.canonical(target.inventory))
        self.assertNotEqual(self.run_restore()[0],0); self.assertNotIn('create',target.calls)
        self.assertEqual(before,(target.archive,self.m.canonical(target.inventory)))

class ResourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.m=load('restore_identity_test','backup_restore.py')
        self.target=self.m.InstalledRestoreTarget(None,None,RUN)
    def test_image_labels_do_not_hide_run_ownership(self):
        value={'Config':{'Labels':{'io.autodata.restore.run':RUN,'org.opencontainers.image.version':'4.48'}},'Name':self.target.prefix+'-minio','Id':'a'*64}
        self.target.json=lambda args:[value]
        self.assertEqual(self.target._owned('container','a'*64),value)
    def test_volume_replacement_or_changed_driver_options_is_rejected(self):
        value={'Name':self.target.prefix+'-nats','CreatedAt':'2026-11-05T12:00:00Z','Driver':'local','Options':{},'Mountpoint':'/tmp', 'Labels':{'io.autodata.restore.run':RUN}}
        self.target.json=lambda args:[value]
        self.target._owned('volume',value['Name'])
        value['Options']={'device':'foreign'}
        with self.assertRaises(ValueError):self.target._owned('volume',value['Name'])
    def test_metadata_parser_rejects_extensions_duplicates_and_oversized_headers(self):
        target=RestoreTarget(self.m);self.addCleanup(target.temp.cleanup)
        manifest,status=self.m.archive_metadata(target.archive)
        self.assertEqual(manifest,target.manifest);self.assertEqual(status,target.status)
        import tarfile
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode='w',format=tarfile.PAX_FORMAT) as archive:
            item=tarfile.TarInfo('a'*200);item.size=1;archive.addfile(item,io.BytesIO(b'x'))
        with self.assertRaises(ValueError):self.m.archive_metadata(output.getvalue())

class InstalledHostGuardTests(unittest.TestCase):
    """Exercise new adapter guards with a fake lifecycle, never a real host."""
    def setUp(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        self.m=load('installed_backup_guard_test','backup_restore.py')
        self.apps=('api','ingestion-http','article-worker','payment-reconciler','outbox-relay')
        self.stateful=('postgres','nats','minio')
        self.events=[]
        self.manifest={'source_sha':'a'*40}; self.config={'resources':{'data_disk_filesystem_uuid':RUN}}
        self.graph={name:{'running':True} for name in self.apps+self.stateful+('caddy',)}
        outer=self
        class Life:
            def __init__(self,*args):self.checks={};self.expected_current=None
            def lock(self):outer.events.append('lock')
            def inputs(self,sha):outer.events.append('inputs');return outer.manifest,outer.config
            def recheck(self,*args):outer.events.append('recheck')
            def graph(self,*args):outer.events.append('graph');return outer.graph
        self.selected=('a'*40,'pinned-symlink')
        a=SimpleNamespace(Lifecycle=Life,selection=lambda pins:self.selected,APPS=self.apps,STATEFUL=self.stateful,
            validate_data_directories=lambda rt:True,DOCKER=['docker'])
        self.host=self.m.InstalledHost(a,None,None,999999999.)
        for item in (patch.object(self.m.os,'geteuid',return_value=0),patch.object(self.m.os,'statvfs',return_value=SimpleNamespace(f_bavail=2**30+1048576,f_frsize=1))):
            item.start();self.addCleanup(item.stop)
    def test_exact_graph_and_free_space_required_before_mutation(self):
        self.assertEqual(self.host.preflight('begin'),(self.manifest,self.config))
        self.graph['unknown']={'running':False}
        with self.assertRaises(ValueError):self.host.preflight('begin')
        self.graph.pop('unknown');self.graph.pop('outbox-relay')
        with self.assertRaises(ValueError):self.host.preflight('begin')
        self.assertEqual(set(self.events),{'lock','inputs','recheck','graph'})
    def test_guard_and_missing_secret_failure_propagates_before_mutation(self):
        for reason in ('wrong mount','missing secrets','wrong cached images'):
            with self.subTest(reason=reason):
                def fail(*args):raise ValueError(reason)
                self.host.life.recheck=fail
                with self.assertRaises(ValueError):self.host.preflight('begin')
                self.assertNotIn('graph',self.events)
    def test_pinned_release_and_low_space_rejected(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        self.host.preflight('begin');self.selected=('b'*40,'other-inode')
        with self.assertRaises(ValueError):self.host.preflight('begin')
        self.selected=('a'*40,'pinned-symlink')
        with patch.object(self.m.os,'statvfs',return_value=SimpleNamespace(f_bavail=10,f_frsize=1)):
            with self.assertRaises(ValueError):self.host.preflight('begin')

    def test_quiescence_rejects_forced_or_oom_stateful_stop(self):
        self.host.preflight('begin')
        for name in self.apps+self.stateful:
            self.graph[name]={'running':False,'id':name}
        states={name:{'Running':False,'OOMKilled':False,'ExitCode':0} for name in self.stateful}
        commands=[]
        def command(argv,*args):
            commands.append(argv);return self.m.canonical(states[argv[-1]])
        self.host.life.command=command
        self.host.check_stopped()
        self.assertEqual({argv[-1] for argv in commands},set(self.stateful))
        for changed in ({'ExitCode':137},{'OOMKilled':True},{'Running':True},{'ExitCode':True}):
            with self.subTest(changed=changed):
                states['minio']={'Running':False,'OOMKilled':False,'ExitCode':0,**changed}
                with self.assertRaises(ValueError):self.host.check_stopped()


if __name__ == '__main__': unittest.main()
