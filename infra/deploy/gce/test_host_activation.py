"""Lifecycle tests use disposable files and intercepted local commands only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SHA = 'a' * 40
OLD = 'b' * 40


def load():
    spec = importlib.util.spec_from_file_location('activation_test', HERE / 'host_activation.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE / 'host_activation.py').exists(), 'fixed activation executor is missing')
        self.a = load()

    def test_real_executor_clears_environment_and_returns_only_stdout(self):
        with patch.dict(os.environ, {'AUTODATA_SECRET': 'do-not-print'}):
            output = self.a.bounded_command([sys.executable, '-c', 'import os;print(os.getenv("AUTODATA_SECRET","clean"))'])
        self.assertEqual(output, b'clean\n')

    def test_stdout_and_stderr_overflow_are_rejected(self):
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream), self.assertRaises(self.a.ActivationError):
                self.a.bounded_command([sys.executable, '-c', f'import sys;sys.{stream}.write("x"*1025)'], maximum=1024)

    def test_timeout_kills_child_group_and_returns_boundedly(self):
        start = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            self.a.bounded_command([sys.executable, '-c', 'import subprocess,time;subprocess.Popen(["/bin/sleep","20"]);time.sleep(20)'], timeout=.1)
        self.assertLess(time.monotonic() - start, 2)

    def test_nonzero_never_returns_stderr(self):
        with self.assertRaises(self.a.ActivationError) as caught:
            self.a.bounded_command([sys.executable, '-c', 'import sys;sys.stderr.write("private-token");sys.exit(7)'])
        self.assertNotIn('private-token', str(caught.exception))


class FileTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE / 'host_activation.py').exists(), 'fixed activation filesystem is missing')
        self.a = load()
        # CI provides a writable TMPDIR while the checkout remains read-only.
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.a.OPT = str(self.base)
        self.a.RELEASES = str(self.base / 'releases')
        Path(self.a.RELEASES).mkdir(mode=0o700)
        self.release = Path(self.a.RELEASES) / SHA
        self.release.mkdir(mode=0o700)
        original_stat, original_fstat = os.stat, os.fstat
        def owned(value):
            fields = list(value); fields[4] = fields[5] = 0; fields[0] &= ~0o022
            return os.stat_result(fields)
        for mocked in (patch.object(os, 'fstat', side_effect=lambda fd: owned(original_fstat(fd))),
                       patch.object(os, 'stat', side_effect=lambda *a, **k: owned(original_stat(*a, **k)))):
            mocked.start(); self.addCleanup(mocked.stop)

    def test_materialization_is_exact_and_refuses_replacement(self):
        with self.a.Pins() as pins:
            fd = pins.directory(str(self.release))
            self.a.materialize(pins, fd, 'Caddyfile', b'exact\n')
            self.a.materialize(pins, fd, 'Caddyfile', b'exact\n')
            with self.assertRaises(self.a.ActivationError):
                self.a.materialize(pins, fd, 'Caddyfile', b'changed\n')
        self.assertEqual((self.release / 'Caddyfile').read_bytes(), b'exact\n')
        self.assertEqual((self.release / 'Caddyfile').stat().st_mode & 0o777, 0o600)

    def test_materialization_rejects_symlinks_and_hardlinks(self):
        outside = self.base / 'outside'; outside.write_bytes(b'exact\n'); outside.chmod(0o600)
        for kind in ('symlink', 'hardlink'):
            target = self.release / 'Caddyfile'
            if kind == 'symlink': target.symlink_to(outside)
            else: os.link(outside, target)
            with self.a.Pins() as pins, self.assertRaises((OSError, self.a.ActivationError)):
                self.a.materialize(pins, pins.directory(str(self.release)), 'Caddyfile', b'exact\n')
            target.unlink()

    def test_current_rejects_relative_and_outside_targets(self):
        for target in ('releases/' + SHA, '/tmp/' + SHA):
            (self.base / 'current').symlink_to(target)
            with self.a.Pins() as pins, self.assertRaises(self.a.ActivationError):
                self.a.selection(pins)
            (self.base / 'current').unlink()

    def test_atomic_selection_refuses_stale_previous_link(self):
        with self.a.Pins() as pins:
            previous = self.a.selection(pins)
            (self.base / 'current').symlink_to(self.a.RELEASES + '/' + OLD)
            with self.assertRaises(self.a.ActivationError):
                self.a.select(pins, SHA, previous)
        self.assertEqual(os.readlink(self.base / 'current'), self.a.RELEASES + '/' + OLD)

    def test_pinned_parent_replacement_is_rejected(self):
        with self.a.Pins() as pins:
            pins.directory(str(self.release))
            self.release.rename(str(self.release) + '-old')
            self.release.mkdir()
            with self.assertRaises(self.a.ActivationError): pins.recheck()


if __name__ == '__main__': unittest.main()

class LifecycleTests(FileTests):
    def setUp(self):
        super().setUp()
        self.assertTrue(hasattr(self.a, 'activation_cli'), 'lifecycle dispatch is missing')
        import types
        self.a.DATA = str(self.base / 'data'); self.a.RUN = str(self.base / 'run')
        for path in (self.a.DATA, self.a.RUN, self.a.RUN + '/state', self.a.RUN + '/caddy'):
            Path(path).mkdir(mode=0o700)
        self.config = {'resources': {'data_disk_filesystem_uuid': 'synthetic'}}
        self.manifest = {'source_sha': SHA, 'rollback_source_sha': None,
                         'images': {name: {'image_id': 'sha256:' + name, 'reference': name + '@sha256:' + 'd'*64} for name in ('api','ingestion','caddy','postgres','nats','minio')}}
        self.events = []; self.graph = {}; self.failed_ready = False; self.failed_reload = False
        self.fail_recovery = False
        for name, value in (('host.json', json.dumps(self.config).encode()),):
            path = self.base / name; path.write_bytes(value); path.chmod(0o600)
        for sha in (SHA, OLD):
            release = Path(self.a.RELEASES) / sha; release.mkdir(exist_ok=True, mode=0o700)
            p = release / 'release.json'; p.write_text(json.dumps(dict(self.manifest,source_sha=sha))); p.chmod(0o600)
        def manifest(sha):
            value = dict(self.manifest, source_sha=sha)
            if sha == OLD: value['rollback_source_sha'] = None
            return value, self.config
        self.rt = types.SimpleNamespace(
            IMAGE_ROLES=tuple(self.manifest['images']),
            validate_guard_tables=lambda *args: True,
            validate_cached_images=lambda *args: True,
            SERVICE_INSPECT_TEMPLATE='fixed-full-inspection',
            _runtime_rendered_compose=lambda *a: {'services':{s:{} for s in ('api','ingestion-http','article-worker','payment-reconciler','postgres','nats','minio','caddy')}},
            _validate_service_container=lambda *a, **k: a[3],
            HOST_CONFIG=str(self.base / 'host.json'),
            _installed_deploy_inputs=manifest,
            validate_manifest=lambda *a: 'valid',
            validate_mount_observations=lambda *a: True,
            strict_json=json.loads,
            guard_cli=lambda: (0, {}),
            validate_runtime_secret_files=lambda: True,
            collect_cached_images=lambda *a: True,
            validate_installed_migration_tree=lambda *a: True,
            collect_postgres_schema=lambda *a: {'version': 1, 'migrations': ['001']},
            render_bundle=lambda *a: {'compose.production.yaml': '{}\n', 'Caddyfile': 'safe\n'},
            collect_runtime_readiness=self.readiness,
            parse_helper_args=lambda helper, argv: {'operation':helper + ' ' + argv[0], 'source_sha':argv[1]},
            operation_receipt=lambda op, sha, run, code, checks, fail: {'operation':op,'source_sha':sha,'status':'passed' if code == 0 else 'failed','checks':dict(checks),'failure_code':fail})
        for mocked in (patch.object(self.a, 'runtime', return_value=self.rt),
                       patch.object(self.a, 'bounded_command', side_effect=self.execute),
                       patch.object(self.a, 'validate_data_directories', return_value=True),
                       patch.object(os, 'geteuid', return_value=0)):
            mocked.start(); self.addCleanup(mocked.stop)
        self.edge = Path(self.a.RUN) / 'caddy/maintenance.caddy'
        self.edge.write_bytes(b''); self.edge.chmod(0o444)

    def readiness(self, manifest, config):
        self.events.append('ready:' + manifest['source_sha'])
        if self.failed_ready and manifest['source_sha'] == SHA: raise ValueError('private token')
        if self.fail_recovery and manifest['source_sha'] == OLD: raise subprocess.TimeoutExpired('private', 5)
        return {key: True for key in ('schema','services','postgres','nats','s3','no_work','runtime_evidence')}

    def execute(self, argv, **kwargs):
        self.events.append(argv)
        self.assertLessEqual(kwargs.get('timeout', 5), 30)
        if argv[0] in ('/usr/bin/findmnt','/usr/sbin/nft'): return b'{}'
        self.assertEqual(argv[:3], ['/usr/bin/docker','--host','unix:///var/run/docker.sock'])
        if argv[3:5] == ['container','ls']:
            return ('\n'.join(self.graph) + ('\n' if self.graph else '')).encode()
        if argv[3:5] == ['image','inspect']:
            if argv[-2] == '{{json .Config.Entrypoint}}': return b'null'
            role = argv[-1].split('@')[0]
            return json.dumps({'image_id':self.manifest['images'][role]['image_id'],'repo_digests':[argv[-1]],'os':'linux','architecture':'amd64','variant':''}).encode()
        if argv[3:5] == ['container','inspect']:
            return json.dumps(self.graph[argv[-1]]).encode()
        if argv[3:5] == ['exec','--user']:
            if self.failed_reload: raise self.a.ActivationError()
            return b''
        self.assertEqual(argv[3], 'compose')
        self.assertIn('--env-file', argv); self.assertEqual(argv[argv.index('--env-file') + 1], '/dev/null')
        if 'up' in argv:
            self.assertIn('--no-deps', argv); self.assertIn('never', argv)
            services = argv[argv.index('never') + 1:]
            for service in services:
                role = 'ingestion' if service in ('ingestion-http','article-worker','payment-reconciler') else service
                container = (str(('api','ingestion-http','article-worker','payment-reconciler','postgres','nats','minio','caddy').index(service) + 1) * 64)
                self.graph[container] = {'id': container, 'project':'autodata-production','service':service,
                    'image':self.manifest['images'][role]['image_id'], 'running':True,'paused':False,'restarting':False,'dead':False}
        elif 'stop' in argv:
            for service in argv[argv.index('10') + 1:]:
                for value in self.graph.values():
                    if value['service'] == service: value['running'] = False
        else: self.fail('unapproved operation: ' + repr(argv))
        return b''

    def start(self): return self.a.activation_cli(['start', SHA])
    def current(self, sha=SHA): (self.base / 'current').symlink_to(self.a.RELEASES + '/' + sha)

    def test_start_selects_after_readiness_and_reloads_closed_edge_first(self):
        code, receipt = self.start()
        self.assertEqual(code, 0, receipt)
        self.assertEqual(os.readlink(self.base / 'current'), self.a.RELEASES + '/' + SHA)
        self.assertEqual(self.edge.read_bytes(), b'')
        self.assertIn('ready:' + SHA, self.events)
        ups = [event for event in self.events if isinstance(event,list) and 'up' in event]
        self.assertEqual(ups[0][-3:], ['postgres','nats','minio'])
        self.assertEqual(ups[1][-5:], ['api','ingestion-http','article-worker','payment-reconciler','caddy'])

    def test_failed_first_start_leaves_current_absent_and_maintenance(self):
        self.failed_ready = True
        code, receipt = self.start()
        self.assertEqual(code, 4, receipt)
        self.assertFalse((self.base / 'current').exists())
        self.assertEqual(self.edge.read_bytes(), b'respond "Maintenance" 503\n')
        self.assertTrue(all(not x['running'] for x in self.graph.values() if x['service'] not in ('postgres','nats','minio')))
        self.assertNotIn('private token', json.dumps(receipt))

    def test_compatible_recovery_stays_failed_and_in_maintenance(self):
        self.current(OLD); self.manifest['rollback_source_sha'] = OLD; (self.release/'release.json').write_text(json.dumps(self.manifest)); self.failed_ready = True
        code, receipt = self.start()
        self.assertEqual(code, 4, receipt)
        self.assertEqual(os.readlink(self.base / 'current'), self.a.RELEASES + '/' + OLD)
        self.assertEqual(self.edge.read_bytes(), b'respond "Maintenance" 503\n')
        self.assertEqual(self.events.count('ready:' + OLD), 1)

    def test_wrong_rollback_reference_rejected_before_mutation(self):
        self.current(OLD)
        code, receipt = self.start()
        self.assertEqual(code, 3, receipt)
        self.assertEqual(self.edge.read_bytes(), b'')
        self.assertFalse(any(isinstance(x,list) and 'up' in x for x in self.events))

    def test_recovery_timeout_is_incomplete(self):
        self.current(OLD); self.manifest['rollback_source_sha'] = OLD; (self.release/'release.json').write_text(json.dumps(self.manifest)); self.failed_ready = True; self.fail_recovery = True
        code, receipt = self.start()
        self.assertEqual(code, 6, receipt)
        self.assertEqual(receipt['failure_code'], 'recovery_incomplete')
        self.assertEqual(self.edge.read_bytes(), b'respond "Maintenance" 503\n')

    def test_resume_failure_retains_maintenance(self):
        self.assertEqual(self.start()[0], 0)
        self.failed_ready = True
        code, receipt = self.a.activation_cli(['resume',SHA])
        self.assertNotEqual(code, 0)
        self.assertEqual(self.edge.read_bytes(), b'respond "Maintenance" 503\n')

    def test_stop_is_observed_and_idempotent(self):
        self.assertEqual(self.start()[0], 0)
        for _ in range(2):
            code, receipt = self.a.activation_cli(['stop',SHA])
            self.assertEqual(code, 0, receipt)
            self.assertFalse(receipt['checks']['runtime_evidence'])
            self.assertTrue(all(not v['running'] for v in self.graph.values()))

    def test_private_delivery_and_activation_locks_exclude_start(self):
        import fcntl
        for filename in ('run/state/operation.lock','data/operations/activation.lock'):
            path = self.base / filename; path.parent.mkdir(exist_ok=True,mode=0o700)
            fd = os.open(path,os.O_CREAT|os.O_RDWR,0o600)
            try:
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                code, receipt = self.start()
                self.assertNotEqual(code,0,receipt)
                self.assertFalse(any(isinstance(x,list) and 'up' in x for x in self.events))
            finally: os.close(fd)

    def test_unowned_extra_container_prevents_stop(self):
        self.current()
        self.graph['untrusted'] = {'id':'untrusted','project':'autodata-production','service':'other','image':'bad','running':True,'paused':False,'restarting':False,'dead':False}
        code, receipt = self.a.activation_cli(['stop',SHA])
        self.assertNotEqual(code,0,receipt)
        self.assertFalse(any(isinstance(x,list) and 'stop' in x for x in self.events))

class LauncherTests(unittest.TestCase):
    def test_installed_mutation_verbs_dispatch_fixed_module_with_clean_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            probe = base / 'activation.py'
            probe.write_text('import os,sys\ndef activation_cli(argv):\n return 0,{"argv":argv,"isolated":sys.flags.isolated,"secret":os.getenv("AUTODATA_SECRET")}\n')
            script = base / 'deploy.sh'
            script.write_text((HERE/'deploy.sh').read_text().replace('/opt/autodata/bin/host_activation.py',str(probe)))
            for verb in ('start','stop','maintenance','resume'):
                result = subprocess.run(['/bin/sh',str(script),verb,SHA],env={'AUTODATA_SECRET':'private'},capture_output=True,timeout=5)
                self.assertEqual(result.returncode,0,result.stdout)
                self.assertEqual(json.loads(result.stdout),{'argv':[verb,SHA],'isolated':1,'secret':None})
            result = subprocess.run(['/bin/sh',str(script),'start',SHA,'--exec','bad'],capture_output=True,timeout=5)
            self.assertEqual(result.returncode,2)
            self.assertEqual(result.stderr,b'')

class RecoveryBoundaryTests(LifecycleTests):
    def test_first_activation_failure_after_selection_removes_current(self):
        original = self.a.Lifecycle.maintenance
        def failure(host, enabled, *args):
            if not enabled: raise self.a.ActivationError()
            return original(host, enabled, *args)
        with patch.object(self.a.Lifecycle,'maintenance',failure): code,receipt = self.start()
        self.assertEqual(code,4,receipt)
        self.assertFalse((self.base / 'current').is_symlink())
        self.assertEqual(self.edge.read_bytes(),b'respond "Maintenance" 503\n')

    def test_failed_receipt_commit_closes_ingress(self):
        with patch.object(self.a.Lifecycle,'persist',side_effect=OSError('private')):
            code,receipt = self.start()
        self.assertEqual(code,6,receipt)
        self.assertEqual(self.edge.read_bytes(),b'respond "Maintenance" 503\n')

    def test_config_replaced_during_read_is_denied_before_mutation(self):
        self.rt._installed_deploy_inputs = lambda sha: (self.manifest,{'resources':{'wrong':'configuration'}})
        code,receipt = self.start()
        self.assertEqual(code,3,receipt)
        self.assertEqual(self.edge.read_bytes(),b'')

    def test_missing_disk_and_cache_never_run_compose(self):
        for method in ('validate_mount_observations','validate_cached_images'):
            with self.subTest(method=method), patch.object(self.rt,method,side_effect=ValueError('private')):
                code,receipt = self.start()
                self.assertEqual(code,3,receipt)
                self.assertFalse(any(isinstance(x,list) and 'compose' in x for x in self.events))

class LifecycleDeadlineTests(unittest.TestCase):
    def test_whole_lifecycle_watchdog_bounds_python_collectors_and_restores_signal(self):
        import signal
        a = load()
        self.assertTrue(hasattr(a,'watchdog'),'whole-operation deadline is missing')
        before = signal.getsignal(signal.SIGALRM)
        began = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            with a.watchdog(.05): time.sleep(5)
        self.assertLess(time.monotonic() - began,1)
        self.assertEqual(signal.getsignal(signal.SIGALRM),before)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.,0.))

class OwnershipTests(LifecycleTests):
    def test_invalid_full_container_security_blocks_stop_before_mutation(self):
        self.assertEqual(self.start()[0],0)
        with patch.object(self.rt,'_validate_service_container',side_effect=ValueError('unsafe mount'),create=True):
            before = len(self.events)
            code,receipt = self.a.activation_cli(['stop',SHA])
        self.assertEqual(code,3,receipt)
        self.assertFalse(any(isinstance(x,list) and 'stop' in x for x in self.events[before:]))

class ReviewRegressionTests(LifecycleTests):
    def test_selection_directory_fsync_failure_removes_published_first_current(self):
        real_fsync = os.fsync
        failed = False
        def fsync(fd):
            nonlocal failed
            if os.readlink('/proc/self/fd/' + str(fd)) == str(self.base) and not failed:
                failed = True
                raise OSError('directory fsync failure')
            return real_fsync(fd)
        with patch.object(os,'fsync',side_effect=fsync):
            code,receipt = self.start()
        self.assertTrue(failed)
        self.assertEqual(code,4,receipt)
        self.assertFalse((self.base/'current').is_symlink())
        self.assertEqual(self.edge.read_bytes(),b'respond "Maintenance" 503\n')
        self.assertTrue(all(not value['running'] for value in self.graph.values() if value['service'] not in ('postgres','nats','minio')))

    def test_guard_timeout_before_mutation_preserves_timeout_exit(self):
        with patch.object(self.a.Lifecycle,'guards',return_value=(5,{'failure_code':'operation_timed_out'})):
            code,receipt = self.start()
        self.assertEqual(code,5,receipt)
        self.assertEqual(receipt['failure_code'],'operation_timed_out')
        self.assertEqual(self.edge.read_bytes(),b'')

class BoundedObservationTests(LifecycleTests):
    def test_lifecycle_does_not_call_legacy_unbounded_collectors(self):
        self.rt.guard_cli = lambda: (_ for _ in ()).throw(AssertionError('legacy guard collector'))
        self.rt.collect_cached_images = lambda *args: (_ for _ in ()).throw(AssertionError('legacy image collector'))
        code,receipt = self.start()
        self.assertEqual(code,0,receipt)
        self.assertTrue(any(isinstance(x,list) and x[:3] == ['/usr/sbin/nft','--json','--numeric'] for x in self.events))
