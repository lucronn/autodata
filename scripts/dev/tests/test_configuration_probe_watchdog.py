import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'configuration_probe_watchdog.py'
spec = importlib.util.spec_from_file_location('configuration_probe_watchdog', MODULE)
w = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = w
spec.loader.exec_module(w)

ID = 'a' * 64
OLD = 'b' * 64

class Fake:
    def __init__(self):
        self.events = []
        self.states = {ID: {'id': ID, 'fingerprint': 'c' * 64, 'running': True, 'pid': 123, 'status': 'running', 'restarting': False}, OLD: {'id': OLD, 'fingerprint': 'd' * 64, 'running': False, 'pid': 0, 'status': 'exited', 'restarting': False}}
        self.stop_error = False
        self.missing = False
        self.supervisor_alive = True
    def verify_supervisor(self, proof):
        self.events.append(("verify_supervisor", proof["pid"]))
        return self.supervisor_alive
    def inspect(self, identifier):
        self.events.append(('inspect', identifier))
        if self.missing and identifier == ID:
            raise RuntimeError('SENTINEL_SECRET')
        return dict(self.states[identifier])
    def stop(self, identifier):
        self.events.append(('stop', identifier))
        if self.stop_error:
            raise TimeoutError('SENTINEL_SECRET')
        self.states[identifier].update(running=False, pid=0, status='exited', restarting=False)
    def start(self, identifier):
        self.events.append(('start', identifier))
        self.states[identifier].update(running=True, pid=456, status='running', restarting=False)
    def fetch(self, url):
        self.events.append(('get', url))
        return {'status': 200, 'bytes': 3, 'sha256': 'e' * 64}
    def postcheck(self, identifier):
        self.events.append(('postcheck', identifier))
        return {'protected_unchanged': True, 'catalog_baseline_preserved': True, 'healthy': True, 'purchase_enabled': False}

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = 10.0
        self.backend = Fake()
        self.manifest = {'source_sha': '1' * 40, 'runtime_reviewed': True, 'run_id': 'fixture01', 'scope_hash': '2' * 16, 'candidate': {'id': ID, 'fingerprint': 'c' * 64}, 'predecessor': {'id': OLD, 'fingerprint': 'd' * 64}}
        self.store = w.Store(self.root)
        self.probe = w.Probe(self.manifest, self.store, self.backend, lambda: self.now, lambda: 'fixture-boot')
        self.probe.verify_supervisor = self.backend.verify_supervisor
        self.probe.pause = lambda _: None
    def tearDown(self):
        self.tmp.cleanup()
    def arm(self):
        self.probe.arm({'verified': True, 'pid': 42, 'start_ticks': 17, 'boot_id': 'fixture-boot', 'run_id': 'fixture01'})
    def rows(self, reason='none', count=2):
        return [f'catalog configuration budget scope_hash={"2"*16} attempt={"3"*16} state=started stop_reason=none attempted_requests=0 elapsed_ms=0', f'catalog configuration budget scope_hash={"2"*16} attempt={"3"*16} state=finished stop_reason={reason} attempted_requests={count} elapsed_ms=100']
    def test_unresolved_source_refused(self):
        self.manifest['source_sha'] = None
        with self.assertRaises(w.Refused): self.arm()
        self.assertEqual(self.backend.events, [])
    def test_unreviewed_runtime_refused(self):
        self.manifest['runtime_reviewed'] = False
        with self.assertRaises(w.Refused): self.arm()
    def test_unverified_supervisor_refused(self):
        with self.assertRaises(w.Refused): self.probe.arm({'verified': False})
    def test_get_requires_arm(self):
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
        self.assertFalse(any(e[0] == 'get' for e in self.backend.events))
    def test_exactly_one_get_durable_before_dispatch(self):
        self.arm()
        original = self.backend.fetch
        def fetch(url):
            self.assertTrue((self.root / 'attempted.json').exists())
            return original(url)
        self.backend.fetch = fetch
        self.probe.dispatch_once()
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
        self.assertEqual([e for e in self.backend.events if e[0] == 'get'], [('get', w.URL)])
    def test_late_arm_never_gets(self):
        self.arm(); self.now += 1.01
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
        self.assertFalse((self.root / 'attempted.json').exists())
    def test_changed_boot_never_gets(self):
        self.arm(); self.probe.boot = lambda: 'other'
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
    def test_identity_drift_never_stops(self):
        self.arm(); self.probe.dispatch_once(); self.backend.states[ID]['fingerprint'] = 'f' * 64
        with self.assertRaises(w.Refused): self.probe.recover(start_seen=True)
        self.assertFalse(any(e[0] in ('stop', 'start') for e in self.backend.events))
    def test_normal_and_local_stop_finish(self):
        for reason in ('none', 'request_limit', 'elapsed', 'cancelled', 'rate_limited'):
            with self.subTest(reason=reason):
                self.assertTrue(w.finished(self.rows(reason), '2' * 16))
    def test_ambiguous_missing_reordered_or_malformed_finish(self):
        rows = self.rows()
        for bad in ([], rows[:1], rows[::-1], rows + rows, [rows[0], rows[1].replace('attempted_requests=2', 'attempted_requests=13')], [rows[0], rows[1].replace('state=finished', 'state=maybe')]):
            with self.subTest(bad=bad): self.assertFalse(w.finished(bad, '2' * 16))
    def test_secret_log_lines_not_retained(self):
        self.assertTrue(w.finished(['SENTINEL_SECRET url credentials'] + self.rows(), '2' * 16))
        self.assertEqual(w.safe_events(['SENTINEL_SECRET']), [])
    def test_finish_requires_attempt_and_matching_pair(self):
        self.arm()
        with self.assertRaises(w.Refused): self.probe.finish(self.rows())
        self.probe.dispatch_once()
        with self.assertRaises(w.Refused): self.probe.finish(self.rows()[:1])
        self.probe.finish(self.rows())
        self.assertTrue((self.root / 'disarmed.json').exists())
    def test_recover_stops_then_confirms_then_restarts_same_id(self):
        self.arm(); self.probe.dispatch_once(); self.now += 25
        self.probe.recover(start_seen=True)
        actions = [e[0] for e in self.backend.events]
        self.assertLess(actions.index('stop'), actions.index('start'))
        self.assertNotIn(('postcheck', ID), self.backend.events)
        self.assertTrue((self.root / 'disarmed.json').exists())
    def test_unknown_stop_never_restarts_or_disarms(self):
        self.arm(); self.probe.dispatch_once(); self.backend.stop_error = True
        with self.assertRaises(w.Refused) as error: self.probe.recover(start_seen=True)
        self.assertNotIn('SENTINEL_SECRET', str(error.exception))
        self.assertFalse(any(e[0] == 'start' for e in self.backend.events))
        self.assertFalse((self.root / 'disarmed.json').exists())
    def test_missing_start_holds_stopped(self):
        self.arm(); self.probe.dispatch_once()
        with self.assertRaises(w.Refused): self.probe.recover(start_seen=False)
        self.assertFalse(self.backend.states[ID]['running'])
        self.assertFalse(any(e[0] == 'start' for e in self.backend.events))
    def test_already_stopped_requires_intentional_stop(self):
        self.arm(); self.probe.dispatch_once(); self.backend.states[ID].update(running=False, pid=0, status='exited', restarting=False)
        self.probe.recover(start_seen=True)
        self.assertIn(('stop', ID), self.backend.events)
    def test_rollback_unknown_candidate_never_starts_predecessor(self):
        self.backend.missing = True
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertNotIn(('start', OLD), self.backend.events)
        self.assertTrue((self.root / 'rollback-refused.json').exists())
        self.assertTrue((self.root / 'rollback-attempted.json').exists())
    def test_rollback_one_attempt(self):
        self.probe.rollback()
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertEqual(self.backend.events.count(('start', OLD)), 1)
    def test_postcheck_drift_refuses_acceptance_after_execution_disarm(self):
        self.arm(); self.probe.dispatch_once(); self.backend.postcheck = lambda _: {'healthy': True, 'purchase_enabled': False, 'protected_unchanged': False, 'catalog_baseline_preserved': True}
        self.probe.recover(start_seen=True)
        self.assertTrue((self.root / 'disarmed.json').exists())
        with self.assertRaises(w.Refused): self.probe.verify_outcome()
        self.assertFalse((self.root / 'verified.json').exists())
    def test_durable_write_file_before_directory(self):
        calls = []
        real = os.fsync
        def fsync(fd): calls.append(os.fstat(fd).st_mode); real(fd)
        with patch.object(w.os, 'fsync', side_effect=fsync): self.store.put('fixture', {'safe': True})
        import stat
        self.assertTrue(stat.S_ISREG(calls[0])); self.assertTrue(stat.S_ISDIR(calls[1]))
        with self.assertRaises(w.Refused): self.store.put('fixture', {})
    def test_store_rejects_symlink(self):
        (self.root / 'bad.json').symlink_to(self.root / 'elsewhere')
        with self.assertRaises(w.Refused): self.store.put('bad', {})
    def test_fixed_runner_ignores_hostile_environment(self):
        with patch.dict(os.environ, {'PATH': '/evil', 'DOCKER_HOST': 'tcp://evil', 'HTTPS_PROXY': 'http://evil'}), patch.object(w.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, b'[]', b'')
            w.FixedRunner('/physical/config').docker(['inspect', ID])
        args, kwargs = run.call_args
        self.assertEqual(args[0][:5], ['/usr/bin/docker', '--config', '/physical/config', '--host', 'unix:///var/run/docker.sock'])
        self.assertEqual(kwargs['env'], w.CHILD_ENV)
        self.assertNotIn('shell', kwargs)
    def test_runner_does_not_expose_failure_text(self):
        with patch.object(w.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, [], stderr=b'SENTINEL_SECRET')):
            with self.assertRaises(w.Refused) as error: w.FixedRunner('/physical/config').docker(['inspect', ID])
        self.assertNotIn('SENTINEL_SECRET', str(error.exception))
    def test_finish_and_fence_are_serialized(self):
        self.arm(); self.probe.dispatch_once()
        with self.store.lock():
            with self.assertRaises(w.Refused): self.probe.finish(self.rows())
            with self.assertRaises(w.Refused): self.probe.recover(start_seen=True)
        self.assertFalse(any(e[0] == 'stop' for e in self.backend.events))
    def test_valid_disarm_prevents_finalizer_stop(self):
        self.arm(); self.probe.dispatch_once(); self.probe.finish(self.rows())
        self.probe.recover(start_seen=True)
        self.assertFalse(any(e[0] == 'stop' for e in self.backend.events))
    def test_unused_arm_recovery_never_stops_or_allows_late_get(self):
        self.arm(); self.probe.recover(start_seen=False)
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
        self.assertFalse(any(e[0] in ('get', 'stop', 'start') for e in self.backend.events))
    def test_incomplete_disarm_never_suppresses_fence(self):
        self.arm(); self.probe.dispatch_once()
        (self.root / 'disarmed.json').write_text('{')
        with self.assertRaises(w.Refused): self.probe.recover(start_seen=True)
        self.assertFalse(any(e[0] == 'start' for e in self.backend.events))
    def test_fence_prevents_late_finish_disarm(self):
        self.arm(); self.probe.dispatch_once()
        with self.assertRaises(w.Refused): self.probe.recover(start_seen=False)
        with self.assertRaises(w.Refused): self.probe.finish(self.rows())
        self.assertFalse((self.root / 'disarmed.json').exists())
    def test_fsync_failure_prevents_dispatch(self):
        self.arm()
        with patch.object(w.os, 'fsync', side_effect=OSError('SENTINEL_SECRET')):
            with self.assertRaises(w.Refused): self.probe.dispatch_once()
        self.assertFalse(any(e[0] == 'get' for e in self.backend.events))
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
    def test_request_failure_never_retries(self):
        self.arm()
        def fail(url):
            self.backend.events.append(('get', url))
            raise TimeoutError('SENTINEL_SECRET')
        self.backend.fetch = fail
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
        self.assertEqual(len([e for e in self.backend.events if e[0] == 'get']), 1)
        self.assertNotIn('SENTINEL_SECRET', (self.root / 'response.json').read_text())
    def test_rollback_refuses_unverified_predecessor_and_keeps_attempt_marker(self):
        self.backend.states[OLD]['fingerprint'] = 'f' * 64
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertTrue((self.root / 'rollback-attempted.json').exists())
        self.assertFalse(any(e[0] in ('start', 'stop') for e in self.backend.events))
        for name in ('fence-attempted', 'fenced', 'rollback-restarted', 'disarmed'):
            self.assertFalse((self.root / (name + '.json')).exists())
        with self.assertRaises(w.Refused): self.probe.rollback()
    def test_rollback_refuses_predecessor_inspection_failure(self):
        original = self.backend.inspect
        def inspect(identifier):
            if identifier == OLD: raise RuntimeError('SENTINEL_SECRET')
            return original(identifier)
        self.backend.inspect = inspect
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertFalse(any(e[0] in ('start', 'stop') for e in self.backend.events))
        self.assertTrue((self.root / 'rollback-attempted.json').exists())
    def test_rollback_stop_timeout_still_running_never_starts_old(self):
        self.backend.stop_error = True
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertNotIn(('start', OLD), self.backend.events)
        self.assertTrue((self.root / 'rollback-refused.json').exists())
        self.assertFalse((self.root / 'rollback-restarted.json').exists())
    def test_rollback_rechecks_old_immediately_before_start(self):
        original = self.backend.stop
        def stop(identifier):
            original(identifier)
            self.backend.states[OLD]['fingerprint'] = 'f' * 64
        self.backend.stop = stop
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertNotIn(('start', OLD), self.backend.events)
        self.assertFalse((self.root / 'rollback-restarted.json').exists())
    def test_rollback_post_start_identity_is_verified(self):
        original = self.backend.start
        def start(identifier):
            original(identifier)
            self.backend.states[OLD]['fingerprint'] = 'f' * 64
        self.backend.start = start
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertIn(('start', OLD), self.backend.events)
        self.assertFalse((self.root / 'rollback-restarted.json').exists())
    def test_dead_supervisor_refuses_before_attempt_marker(self):
        self.arm(); self.backend.supervisor_alive = False
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
        self.assertFalse((self.root / 'attempted.json').exists())
        self.assertFalse(any(e[0] == 'get' for e in self.backend.events))
    def test_missing_supervisor_verifier_refuses(self):
        self.arm(); self.probe.verify_supervisor = None
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
        self.assertFalse((self.root / 'attempted.json').exists())
    def test_slow_supervisor_verification_expires_arm(self):
        self.arm()
        def verifier(proof):
            self.now += 2
            return True
        self.probe.verify_supervisor = verifier
        with self.assertRaises(w.Refused): self.probe.dispatch_once()
        self.assertFalse((self.root / 'attempted.json').exists())
    def test_malformed_manifest_refused_without_backend_calls(self):
        for key, value in [('candidate', 'SENTINEL_SECRET'), ('run_id', 12), ('source_sha', False)]:
            manifest = dict(self.manifest); manifest[key] = value
            with self.assertRaises(w.Refused): w.validate_manifest(manifest)
        self.assertEqual(self.backend.events, [])
    def test_rollback_refusal_preserves_existing_attempt_and_fence(self):
        self.arm(); self.probe.dispatch_once()
        with self.assertRaises(w.Refused): self.probe.recover(start_seen=False)
        attempted = (self.root / 'attempted.json').read_bytes()
        fenced = (self.root / 'fenced.json').read_bytes()
        self.backend.states[OLD]['fingerprint'] = 'f' * 64
        before = list(self.backend.events)
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertEqual((self.root / 'attempted.json').read_bytes(), attempted)
        self.assertEqual((self.root / 'fenced.json').read_bytes(), fenced)
        self.assertTrue((self.root / 'rollback-attempted.json').exists())
        self.assertFalse((self.root / 'disarmed.json').exists())
        self.assertFalse((self.root / 'rollback-restarted.json').exists())
        self.assertFalse(any(e[0] in ('start', 'stop') for e in self.backend.events[len(before):]))
    def test_supervisor_verifier_error_refuses_without_secret_or_attempt(self):
        self.arm()
        def verifier(proof): raise RuntimeError('SENTINEL_SECRET')
        self.probe.verify_supervisor = verifier
        with self.assertRaises(w.Refused) as error: self.probe.dispatch_once()
        self.assertNotIn('SENTINEL_SECRET', str(error.exception))
        self.assertFalse((self.root / 'attempted.json').exists())
        self.assertFalse(any(e[0] == 'get' for e in self.backend.events))
    def test_rollback_stop_error_even_if_stopped_holds(self):
        def stop(identifier):
            self.backend.states[identifier].update(running=False, pid=0, status='exited', restarting=False)
            raise TimeoutError('SENTINEL_SECRET')
        self.backend.stop = stop
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertNotIn(('start', OLD), self.backend.events)
        self.assertFalse((self.root / 'rollback-restarted.json').exists())
    def test_rollback_already_running_verified_old_not_started_again(self):
        self.backend.states[ID].update(running=False, pid=0, status='exited', restarting=False)
        self.backend.states[OLD].update(running=True, pid=456, status='running', restarting=False)
        self.probe.rollback()
        self.assertFalse(any(e[0] == 'start' for e in self.backend.events))
        self.assertIn(('postcheck', OLD), self.backend.events)
    def test_rollback_false_running_but_nonzero_pid_refuses(self):
        self.backend.states[ID].update(running=False, pid=123)
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertNotIn(('start', OLD), self.backend.events)
    def test_rollback_already_stopped_is_intentionally_stopped(self):
        self.backend.states[ID].update(running=False, pid=0, status='exited', restarting=False)
        self.probe.rollback()
        self.assertIn(('stop', ID), self.backend.events)
    def test_rollback_restarting_flag_cannot_be_fenced(self):
        self.backend.states[ID].update(running=False, pid=0, status='restarting', restarting=True)
        self.backend.stop = lambda _: None
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertNotIn(('start', OLD), self.backend.events)
    def test_rollback_post_stop_state_must_be_stable(self):
        calls = []
        def pause(_):
            calls.append(True)
            if len(calls) == 2:self.backend.states[ID].update(running=True,pid=999,status='running')
        self.probe.pause = pause
        with self.assertRaises(w.Refused): self.probe.rollback()
        self.assertNotIn(('start', OLD), self.backend.events)
    def test_worker_finish_disarm_never_waits_for_slow_sql(self):
        self.arm(); self.probe.dispatch_once()
        def forbidden(_): raise AssertionError('SQL must be outside watchdog lifecycle')
        self.backend.postcheck = forbidden
        self.probe.finish(self.rows())
        self.assertTrue((self.root / 'worker-finished.json').exists())
        self.assertTrue((self.root / 'disarmed.json').exists())
    def test_final_acceptance_is_a_separate_receipt(self):
        self.arm(); self.probe.dispatch_once(); self.probe.finish(self.rows())
        self.assertFalse((self.root / 'verified.json').exists())
        self.probe.verify_outcome()
        self.assertTrue((self.root / 'verified.json').exists())
    def test_cli_has_no_live_action(self):
        result = subprocess.run([sys.executable, str(MODULE), 'arm'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

if __name__ == '__main__': unittest.main()
