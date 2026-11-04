"""Owned synthetic children only; no runtime or host acceptance is asserted."""
import dataclasses
import importlib.util
import os
from pathlib import Path
import signal
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


class CaptureTests(unittest.TestCase):
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

    def run_child(self, code='pass', budget=None):
        return transport.run(self.request(code), budget or self.budget(), threading.Event())

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
                 dict(executable='python'), dict(cwd='relative'), dict(cwd=''), dict(cwd='/x\x00'),
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
            r = transport.run(self.request(code, env=(('LC_ALL','C.UTF-8'),)), self.budget(), threading.Event())
        self.assertEqual((r.status, r.returncode), ('completed', 0))


if __name__ == '__main__':
    unittest.main()
