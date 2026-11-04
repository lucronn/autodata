"""Owned synthetic children only; no runtime or host acceptance is asserted."""
import dataclasses
import importlib.util
import os
from pathlib import Path
import signal
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name('process_transport.py')
if MODULE_PATH.exists():
    SPEC = importlib.util.spec_from_file_location('r3_process_transport_under_test', MODULE_PATH)
    transport = importlib.util.module_from_spec(SPEC)
    sys.modules[SPEC.name] = transport
    SPEC.loader.exec_module(transport)
else:
    transport = None


class SyntheticTestCase(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(transport, 'owned subprocess transport is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def request(self, code='pass', **changes):
        values = dict(command_id='synthetic', executable=sys.executable,
                      argv=(sys.executable, '-I', '-B', '-c', code),
                      cwd=self.temp.name, env=(), kind='ordinary')
        values.update(changes)
        return transport.RunRequest(**values)

    def budget(self, size=128 * 1024 * 1024, seconds=20):
        return transport.CaptureBudget(time.monotonic_ns() + int(seconds * 1e9), size)

    def run_request(self,request,budget=None,cancel=None):
        backend=TrackingBackend()
        self.addCleanup(backend.teardown)
        with mock.patch.object(transport,'_Backend',return_value=backend):
            return transport.run(request,budget or self.budget(),cancel or threading.Event())

    def run_child(self, code='pass', budget=None):
        return self.run_request(self.request(code),budget)



class CaptureTests(SyntheticTestCase):
    def test_binary_split_and_stderr_preserve_opaque_bytes(self):
        result = self.run_child("import os; os.write(1,b'a\\x00\\xff'); os.write(2,b'\\xfeerr'); os.write(1,b'z')")
        self.assertEqual((result.status, result.returncode, result.cleanup), ('completed', 0, 'reaped'))
        self.assertEqual((result.stdout, result.stderr, result.captured_bytes), (b'a\x00\xffz', b'\xfeerr', 8))
        self.assertIsNone(result.primary_fault)

    def test_empty_stderr_only_and_nonzero_exit(self):
        for code, rc, err in [('pass', 0, b''), ("import os; os.write(2,b'err')", 0, b'err'),
                              ('raise SystemExit(7)', 7, b'')]:
            with self.subTest(code=code):
                r = self.run_child(code)
                self.assertEqual((r.status, r.returncode, r.stdout, r.stderr), ('completed', rc, b'', err))

    def test_streams_make_progress_without_starvation(self):
        r = self.run_child("import os\nfor i in range(32):\n os.write(1,b'a'*4096); os.write(2,b'b'*4096)")
        self.assertEqual((r.status, r.stdout, r.stderr), ('completed', b'a'*131072, b'b'*131072))

    def test_exact_shared_cap_succeeds_without_sentinel_retention(self):
        b = self.budget(9)
        r = self.run_child("import os; os.write(1,b'12345'); os.write(2,b'6789')", b)
        self.assertEqual((r.status, r.captured_bytes, b.remaining_bytes), ('completed', 9, 0))
        self.assertEqual(self.run_child('pass', b).status, 'completed')

    def test_overflow_latches_shared_budget_and_prevents_later_spawn(self):
        b = self.budget(9)
        self.assertEqual(self.run_child("import os; os.write(1,b'1234')", b).status, 'completed')
        r = self.run_child("import os; os.write(2,b'567890')", b)
        self.assertEqual((r.status, r.primary_fault, r.stderr, b.remaining_bytes),
                         ('output_limit', 'output_limit', b'56789', 0))
        with mock.patch.object(transport.subprocess, 'Popen', side_effect=AssertionError('spawn forbidden')):
            self.assertEqual(self.run_child('pass', b).status, 'budget_stopped')

    def test_full_production_command_cap_and_one_extra_byte(self):
        for count, status in [(16*1024*1024, 'completed'), (16*1024*1024+1, 'output_limit')]:
            with self.subTest(count=count):
                b = self.budget()
                r = self.run_child(f"import os\nn={count}\nwhile n:\n data=b'x'*min(n,32768); n-=os.write(1,data)", b)
                self.assertEqual((r.status, r.captured_bytes), (status, 16777216))
                self.assertEqual(len(r.stdout), 16777216)
                self.assertEqual(b.remaining_bytes, 117440512)

    def test_request_validation_rejects_without_spawn(self):
        cases = [dict(command_id='Bad'), dict(command_id='a\n'), dict(command_id=True),
                 dict(executable='python'), dict(cwd='relative'), dict(cwd=''), dict(cwd='/x\x00'), dict(cwd='/\ud800'),
                 dict(argv=(sys.executable, '')), dict(argv=(sys.executable, '\ud800')),
                 dict(argv=('wrong',)), dict(argv=[sys.executable]),
                 dict(argv=(sys.executable,)+('x',)*128), dict(argv=(sys.executable, 'x'*65536)),
                 dict(env=(('A','1'),('A','2'))), dict(env=(('BAD=KEY','1'),)),
                 dict(env=(('A','\x00'),)), dict(env=(('A','x'*65536),)),
                 dict(env=tuple((f'A{i}','') for i in range(65))), dict(kind='unknown')]
        with mock.patch.object(transport.subprocess, 'Popen', side_effect=AssertionError('spawn forbidden')):
            for changes in cases:
                with self.subTest(changes=repr(changes)[:100]):
                    self.assertEqual(transport.run(self.request(**changes), self.budget(), threading.Event()).status,
                                     'invalid_request')
            for request in [None, {}, object(), object.__new__(transport.RunRequest)]:
                self.assertEqual(transport.run(request, self.budget(), threading.Event()).status, 'invalid_request')
            mutated = self.request()
            object.__setattr__(mutated, 'argv', (sys.executable, '\x00'))
            self.assertEqual(transport.run(mutated, self.budget(), threading.Event()).status, 'invalid_request')
            self.assertEqual(transport.run(self.request(), self.budget(), None).status, 'invalid_request')
            self.assertEqual(transport.run(self.request(), None, threading.Event()).status, 'invalid_request')

    def test_budget_validation_and_public_immutability(self):
        for deadline, size in [(True, 1), (float('inf'), 1), (time.monotonic_ns()-1, 1),
                               (time.monotonic_ns()+1801_000_000_000, 1),
                               (time.monotonic_ns()+1_000_000_000, True),
                               (time.monotonic_ns()+1_000_000_000, 0),
                               (time.monotonic_ns()+1_000_000_000, 134217729)]:
            with self.subTest(deadline=deadline,size=size), self.assertRaises((TypeError, ValueError)):
                transport.CaptureBudget(deadline, size)
        for obj, field, value in [(self.budget(), 'outer_deadline_ns', 1), (self.budget(), 'max_bytes', 100),
                                   (self.request(), 'cwd', '/tmp'), (self.run_child(), 'status', 'bad')]:
            with self.assertRaises((dataclasses.FrozenInstanceError, AttributeError)):
                setattr(obj, field, value)

    def test_precancel_and_expired_budget_do_not_spawn_and_latch(self):
        b = self.budget()
        cancel = threading.Event(); cancel.set()
        with mock.patch.object(transport.subprocess, 'Popen', side_effect=AssertionError('spawn forbidden')):
            r = transport.run(self.request(), b, cancel)
            self.assertEqual((r.status, r.cleanup, r.primary_fault), ('cancelled', 'not_started', 'cancelled'))
            cancel.clear()
            self.assertEqual(transport.run(self.request(), b, cancel).status, 'budget_stopped')
            b = self.budget(seconds=0.001)
            time.sleep(0.003)
            self.assertEqual(transport.run(self.request(), b, cancel).status, 'deadline')

    def test_unsupported_platform_and_sigchld_disposition_do_not_spawn(self):
        with mock.patch.object(transport.subprocess, 'Popen', side_effect=AssertionError('spawn forbidden')):
            with mock.patch.object(transport.sys, 'platform', 'win32'):
                self.assertEqual(self.run_child().status, 'unsupported_platform')
            for disposition in [signal.SIG_IGN, lambda *_: None]:
                with mock.patch.object(transport.signal, 'getsignal', return_value=disposition):
                    self.assertEqual(self.run_child().status, 'unsupported_platform')

    def test_environment_is_explicit_and_descriptors_do_not_leak(self):
        readfd, writefd = os.pipe()
        self.addCleanup(os.close, readfd); self.addCleanup(os.close, writefd)
        os.set_inheritable(writefd, True)
        code = ("import os\nassert dict(os.environ)=={'LC_ALL':'C.UTF-8'}\n"
                f"try: os.fstat({writefd})\nexcept OSError: pass\nelse: raise SystemExit(9)")
        with mock.patch.dict(os.environ, {'R3_SYNTHETIC_AMBIENT': 'must_not_inherit'}):
            r = self.run_request(self.request(code, env=(('LC_ALL','C.UTF-8'),)))
        self.assertEqual((r.status, r.returncode), ('completed', 0))


class TrackingBackend(transport._Backend if transport else object):
    """Track only children created by this test for independent teardown."""
    def __init__(self, cancel=None, fail=None):
        self.processes = []
        self.signals = []
        self.ready = threading.Event()
        self.cancel = cancel
        self.fail = fail
        self.reads = 0
        self.observed_before_signal = []

    def spawn(self, request):
        if self.fail == 'spawn':
            raise OSError('synthetic private diagnostic')
        p = super().spawn(request)
        self.processes.append(p)
        return p

    def selector(self):
        if self.fail == 'selector':
            raise OSError('synthetic private diagnostic')
        inner = super().selector()
        failure = self.fail
        class Selector:
            def register(self, *args):
                if failure == 'register':
                    raise OSError('synthetic')
                return inner.register(*args)
            def unregister(self, *args):
                return inner.unregister(*args)
            def select(self, timeout):
                if failure == 'select':
                    raise OSError('synthetic')
                return inner.select(timeout)
            def close(self):
                inner.close()
                if failure == 'selector_close':
                    raise OSError('synthetic close failure')
        return Selector()

    def nonblocking(self, pipe):
        if self.fail == 'nonblocking':
            raise OSError('synthetic')
        return super().nonblocking(pipe)

    def read(self, pipe, count):
        self.reads += 1
        if self.fail == 'read':
            raise OSError('synthetic')
        if self.fail == 'eintr' and self.reads == 1:
            raise InterruptedError()
        data = super().read(pipe, count)
        if b'READY' in data:
            self.ready.set()
            if self.cancel:
                self.cancel.set()
        return data

    def send(self, proc, sig):
        # WNOWAIT must still observe our direct child before any group signal;
        # a competing or premature reap raises ChildProcessError here.
        self.observed_before_signal.append(os.waitid(os.P_PID, proc.pid, os.WEXITED|os.WNOHANG|os.WNOWAIT))
        self.signals.append(sig)
        if self.fail == 'term' and sig == signal.SIGTERM:
            raise PermissionError('synthetic')
        if self.fail == 'kill' and sig == signal.SIGKILL:
            raise PermissionError('synthetic')
        super().send(proc, sig)
        if self.fail == 'esrch':
            raise ProcessLookupError('synthetic post-delivery ESRCH')

    def reap(self, proc):
        if self.fail == 'reap_eintr':
            self.fail = None
            raise InterruptedError()
        if self.fail in ('reap', 'uninterruptible'):
            return None
        return super().reap(proc)

    def teardown(self):
        for p in self.processes:
            # Only the Popen-created identity is eligible; never caller PID input.
            if p.returncode is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    raise AssertionError('synthetic child teardown unconfirmed')
            for pipe in (p.stdout, p.stderr):
                if pipe:
                    pipe.close()
            try:
                os.waitpid(p.pid, os.WNOHANG)
            except ChildProcessError:
                pass
            else:
                raise AssertionError('synthetic direct-child reap was not proven')


class LifecycleTests(SyntheticTestCase):
    def backend(self, **kwargs):
        backend = TrackingBackend(**kwargs)
        self.addCleanup(backend.teardown)
        return backend

    def run_backend(self, code, backend, budget=None, cancel=None):
        return transport._run(self.request(code), budget or self.budget(), cancel or threading.Event(), backend)

    def test_cancel_after_ready_reaps_direct_child_and_preserves_parent_group(self):
        parent_group = os.getpgrp()
        cancel = threading.Event()
        backend = self.backend(cancel=cancel)
        r = self.run_backend("import os,time; os.write(1,b'READY\\n'); time.sleep(60)", backend, cancel=cancel)
        self.assertEqual((r.status,r.primary_fault,r.cleanup), ('cancelled','cancelled','reaped'))
        self.assertEqual(os.getpgrp(), parent_group)
        self.assertTrue(cancel.is_set())
        self.assertEqual(backend.signals[0], signal.SIGTERM)
        self.assertIsNotNone(backend.processes[0].returncode)
        with self.assertRaises(ChildProcessError):
            os.waitpid(backend.processes[0].pid, os.WNOHANG)

    def test_busy_has_no_effect_on_active_child_or_budget_latch(self):
        budget = self.budget()
        cancel = threading.Event(); backend = self.backend(); results = []
        def stop():
            cancel.set(); worker.join(6)
            self.assertFalse(worker.is_alive(), 'synthetic runner did not stop')
        worker = threading.Thread(target=lambda: results.append(self.run_backend(
            "import os,time; os.write(1,b'READY\\n'); time.sleep(60)", backend, budget, cancel)))
        self.addCleanup(stop)
        worker.start(); self.assertTrue(backend.ready.wait(3))
        remaining = budget.remaining_bytes
        r = self.run_child('pass', budget)
        self.assertEqual((r.status,r.cleanup,budget.remaining_bytes), ('busy','not_started',remaining))
        self.assertEqual(backend.signals, [])
        cancel.set(); worker.join(6)
        self.assertEqual(results[0].status, 'cancelled')

    def test_ordinary_ten_second_deadline_is_real(self):
        started = time.monotonic()
        backend = self.backend()
        r = self.run_backend("import os,time; os.write(1,b'READY\\n'); time.sleep(60)", backend)
        elapsed = time.monotonic()-started
        self.assertEqual((r.status,r.primary_fault,r.cleanup), ('deadline','deadline','reaped'))
        self.assertGreaterEqual(elapsed, 9.9)
        self.assertLess(elapsed, 15)

    def test_term_ignoring_child_requires_kill_after_grace(self):
        cancel = threading.Event(); backend = self.backend(cancel=cancel)
        code = "import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); os.write(1,b'READY\\n'); time.sleep(60)"
        started = time.monotonic()
        r = self.run_backend(code, backend, cancel=cancel)
        self.assertEqual((r.status,r.returncode,r.cleanup), ('cancelled',-signal.SIGKILL,'reaped'))
        self.assertEqual(backend.signals, [signal.SIGTERM,signal.SIGKILL])
        self.assertGreaterEqual(time.monotonic()-started, 2)
        self.assertLess(time.monotonic()-started, 5)

    def test_closed_output_does_not_turn_sleeping_child_into_success(self):
        cancel = threading.Event()
        class CancelAfterBothEOF(TrackingBackend):
            eof_count=0
            def read(self,pipe,count):
                data=super().read(pipe,count)
                if not data:
                    self.eof_count+=1
                    if self.eof_count==2: cancel.set()
                return data
        backend=CancelAfterBothEOF(); self.addCleanup(backend.teardown)
        r = self.run_backend("import os,time; os.write(1,b'READY\\n'); os.close(1); os.close(2); time.sleep(60)",
                             backend, cancel=cancel)
        self.assertEqual(backend.eof_count,2)
        self.assertEqual((r.status,r.cleanup), ('cancelled','reaped'))

    def test_exited_leader_with_term_ignoring_pipe_holder_is_killed_before_reap(self):
        cancel = threading.Event()
        class DescendantBackend(TrackingBackend):
            descendant_fd = None
            def read(self,pipe,count):
                data=super().read(pipe,count)
                if b'READY:' in data:
                    pid=int(data.split(b'READY:',1)[1].splitlines()[0])
                    # pidfd pins the synthetic descendant for independent exit
                    # observation and failure-path teardown without PID reuse.
                    self.descendant_fd=os.pidfd_open(pid,0)
                    end=time.monotonic()+2
                    while super().observe(self.processes[0]) is None:
                        if time.monotonic()>=end:
                            raise AssertionError('synthetic leader exit was not observed')
                        time.sleep(0.001)
                return data
            def descendant_exited(self,timeout_ms):
                poller=select.poll(); poller.register(self.descendant_fd,select.POLLIN)
                return bool(poller.poll(timeout_ms))
            def teardown(self):
                try:
                    super().teardown()
                    if self.descendant_fd is not None:
                        if not self.descendant_exited(0):
                            signal.pidfd_send_signal(self.descendant_fd,signal.SIGKILL)
                        if not self.descendant_exited(2000):
                            raise AssertionError('synthetic descendant exit unconfirmed')
                finally:
                    if self.descendant_fd is not None:
                        os.close(self.descendant_fd); self.descendant_fd=None
        backend=DescendantBackend(cancel=cancel)
        self.addCleanup(backend.teardown)
        # Grandchild remains in the owned session/group; no setsid or escape.
        code = """import os,signal,time
r,w=os.pipe()
pid=os.fork()
if pid==0:
 os.close(r); signal.signal(signal.SIGTERM,signal.SIG_IGN)
 os.write(w,b'x'); os.close(w); time.sleep(60); os._exit(0)
os.close(w); os.read(r,1); os.close(r)
os.write(1,b'READY:'+str(pid).encode('ascii')+b'\\n'); os._exit(7)
"""
        r = self.run_backend(code, backend, cancel=cancel)
        self.assertEqual((r.status,r.cleanup), ('cancelled','reaped'))
        self.assertEqual(backend.signals, [signal.SIGTERM,signal.SIGKILL])
        # The recorded WNOWAIT result proves the leader identity was unreaped.
        self.assertEqual(r.returncode,7)
        self.assertEqual(backend.observed_before_signal[0].si_status,7)
        self.assertIsNotNone(backend.descendant_fd)
        self.assertTrue(backend.descendant_exited(2000), 'synthetic descendant still live after group cleanup')

    def test_source_uses_smaller_outer_allowance_and_stops_ledger(self):
        b = self.budget(seconds=0.2); backend = self.backend()
        r = transport._run(self.request('import time; time.sleep(60)',kind='source'), b, threading.Event(), backend)
        self.assertIn(r.status, ('deadline','cleanup_unconfirmed'))
        self.assertEqual(r.primary_fault,'deadline')
        self.assertEqual(self.run_child('pass', b).status,'budget_stopped')
        self.assertLess(r.elapsed_ns, 2_000_000_000)

    def test_faults_close_pipes_and_stop_ledger_without_error_text(self):
        for failure in ('spawn','selector','register','nonblocking','select','read'):
            with self.subTest(failure=failure):
                backend = self.backend(fail=failure); b = self.budget()
                r = self.run_backend("import os,time; os.write(1,b'READY\\n'); time.sleep(60)",backend,b)
                expected = 'spawn_failed' if failure=='spawn' else 'capture_failed'
                self.assertEqual((r.status,r.primary_fault), (expected,expected))
                self.assertNotIn('synthetic', repr(r))
                self.assertEqual(self.run_child('pass',b).status,'budget_stopped')
                for p in backend.processes:
                    self.assertTrue(p.stdout.closed and p.stderr.closed)

    def test_interrupted_successful_reap_retries_without_latching_capture_failure(self):
        backend = self.backend(fail='reap_eintr')
        r = self.run_backend('raise SystemExit(7)',backend)
        self.assertEqual((r.status,r.returncode,r.primary_fault), ('completed',7,None))

    def test_selector_close_failure_is_a_capture_fault_and_stops_budget(self):
        backend=self.backend(fail='selector_close'); b=self.budget()
        r=self.run_backend('pass',backend,b)
        self.assertEqual((r.status,r.primary_fault,r.cleanup),('cleanup_unconfirmed','capture_failed','unconfirmed'))
        self.assertEqual(self.run_child('pass',b).status,'budget_stopped')

    def test_eintr_is_retryable_without_losing_bytes(self):
        backend = self.backend(fail='eintr')
        r = self.run_backend("import os; os.write(1,b'abc')", backend)
        self.assertEqual((r.status,r.stdout), ('completed',b'abc'))

    def test_signal_failure_is_unconfirmed_and_esrch_is_not(self):
        for failure in ('term','kill','esrch'):
            with self.subTest(failure=failure):
                cancel = threading.Event(); backend = self.backend(cancel=cancel,fail=failure)
                code = "import os,time; os.write(1,b'READY\\n'); time.sleep(60)"
                r = self.run_backend(code,backend,cancel=cancel)
                expected = 'cancelled' if failure=='esrch' else 'cleanup_unconfirmed'
                self.assertEqual((r.status,r.primary_fault), (expected,'cancelled'))

    def test_missing_reap_never_claims_completed_and_has_one_cleanup_allowance(self):
        backend = self.backend(fail='reap'); cancel=threading.Event(); backend.cancel=cancel
        b = self.budget(); started=time.monotonic()
        r = self.run_backend("import os,time; os.write(1,b'READY\\n'); time.sleep(60)",backend,b,cancel)
        self.assertEqual((r.status,r.cleanup,r.primary_fault), ('cleanup_unconfirmed','unconfirmed','cancelled'))
        self.assertEqual(self.run_child('pass',b).status,'budget_stopped')
        self.assertLess(time.monotonic()-started, 5)
        self.assertEqual(backend.signals, [signal.SIGTERM,signal.SIGKILL])

    def test_failed_test_body_still_terminates_and_reaps_owned_child(self):
        backend = TrackingBackend()
        request = self.request("import time; time.sleep(60)")
        p = backend.spawn(request)
        try:
            with self.assertRaises(AssertionError):
                try:
                    self.assertEqual(1,2,'deliberate synthetic assertion failure')
                finally:
                    backend.teardown()
        finally:
            backend.teardown()
        self.assertIsNotNone(p.returncode)
        with self.assertRaises(ChildProcessError):
            os.waitpid(p.pid,os.WNOHANG)

    def test_cleanup_expiry_keeps_first_fault_and_never_renews_after_second_error(self):
        class FailureBackend(TrackingBackend):
            def observe(self,proc):
                if self.signals:
                    raise OSError('second cleanup failure')
                return super().observe(proc)
            def reap(self,proc):
                return None
        cancel=threading.Event(); backend=FailureBackend(cancel=cancel)
        self.addCleanup(backend.teardown)
        b=self.budget(seconds=0.4); started=time.monotonic()
        r=self.run_backend("import os,time; os.write(1,b'READY\\n'); time.sleep(60)",backend,b,cancel)
        self.assertEqual((r.status,r.primary_fault,r.cleanup),('cleanup_unconfirmed','cancelled','unconfirmed'))
        self.assertLess(time.monotonic()-started,1.5)
        self.assertEqual(self.run_child('pass',b).status,'budget_stopped')

    def test_uninterruptible_standin_expires_without_false_reap_claim(self):
        class StuckBackend(TrackingBackend):
            def observe(self,proc):
                return None
        cancel=threading.Event(); backend=StuckBackend(cancel=cancel,fail='uninterruptible')
        self.addCleanup(backend.teardown)
        started=time.monotonic()
        r=self.run_backend("import os,time; os.write(1,b'READY\\n'); time.sleep(60)",backend,cancel=cancel)
        self.assertEqual((r.status,r.cleanup,r.primary_fault),('cleanup_unconfirmed','unconfirmed','cancelled'))
        self.assertLess(time.monotonic()-started,5)
        self.assertEqual(backend.signals,[signal.SIGTERM,signal.SIGKILL])

    def test_first_observed_output_limit_wins_over_cancellation_during_read(self):
        cancel=threading.Event(); backend=self.backend(cancel=cancel)
        r=self.run_backend("import os; os.write(1,b'READY!')",backend,self.budget(5),cancel)
        self.assertTrue(cancel.is_set())
        self.assertEqual((r.status,r.primary_fault,r.stdout),('output_limit','output_limit',b'READY'))

    def test_cancellation_after_select_prevents_even_ready_bytes_being_read(self):
        cancel=threading.Event()
        class CancelOnWake(TrackingBackend):
            def selector(self):
                inner=super().selector()
                class Selector:
                    def register(self,*args): return inner.register(*args)
                    def unregister(self,*args): return inner.unregister(*args)
                    def close(self): return inner.close()
                    def select(self,timeout):
                        events=inner.select(timeout)
                        if events: cancel.set()
                        return events
                return Selector()
        backend=CancelOnWake(); self.addCleanup(backend.teardown)
        r=self.run_backend("import os,time; os.write(1,b'READY!'); time.sleep(60)",backend,self.budget(1),cancel)
        self.assertEqual((r.status,r.primary_fault,r.captured_bytes),('cancelled','cancelled',0))
        self.assertEqual(backend.reads,0)

    def test_known_exitcode_survives_later_cleanup_observation_failure(self):
        class LoseObservation(TrackingBackend):
            first=True
            def observe(self,proc):
                if not self.first:
                    raise ChildProcessError('synthetic late observation loss')
                end=time.monotonic()+2
                while time.monotonic()<end:
                    info=super().observe(proc)
                    if info is not None:
                        self.first=False
                        return info
                    time.sleep(0.001)
                raise AssertionError('synthetic child did not exit')
            def read(self,pipe,count):
                raise OSError('synthetic capture fault after known exit')
            def reap(self,proc):
                raise ChildProcessError('synthetic reap loss')
        backend=LoseObservation(); self.addCleanup(backend.teardown)
        r=self.run_backend("import os; os.write(1,b'x'); raise SystemExit(7)",backend)
        self.assertEqual((r.status,r.primary_fault,r.returncode),('cleanup_unconfirmed','capture_failed',7))

    def test_observation_failure_and_reap_exception_are_conservative(self):
        for which in ('observe','reap'):
            class FailBackend(TrackingBackend):
                def observe(self,proc):
                    if which=='observe': raise ChildProcessError('synthetic competing reaper')
                    return super().observe(proc)
                def reap(self,proc):
                    if which=='reap': raise OSError('synthetic reap failure')
                    return super().reap(proc)
            cancel=threading.Event(); backend=FailBackend(cancel=cancel)
            self.addCleanup(backend.teardown)
            r=self.run_backend("import os,time; os.write(1,b'READY\\n'); time.sleep(60)",backend,cancel=cancel)
            self.assertEqual(r.status,'cleanup_unconfirmed')
            self.assertIn(r.primary_fault,('cancelled','capture_failed'))
            for p in backend.processes: self.assertTrue(p.stdout.closed and p.stderr.closed)

    def test_capture_budget_cannot_be_copied_or_mutated_to_renew(self):
        import copy
        b=self.budget()
        for copier in (copy.copy,copy.deepcopy):
            with self.assertRaises(TypeError):
                copier(b)
        object.__setattr__(b,'outer_deadline_ns',b.outer_deadline_ns+1)
        with mock.patch.object(transport.subprocess,'Popen',side_effect=AssertionError('spawn forbidden')):
            self.assertEqual(self.run_child('pass',b).status,'invalid_request')


if __name__ == '__main__':
    unittest.main()
