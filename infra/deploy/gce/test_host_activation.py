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
        self.temp = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.a.OPT = str(self.base)
        self.a.RELEASES = str(self.base / 'releases')
        Path(self.a.RELEASES).mkdir(mode=0o700)
        self.release = Path(self.a.RELEASES) / SHA
        self.release.mkdir(mode=0o700)
        original_stat, original_fstat = os.stat, os.fstat
        def owned(value):
            fields = list(value); fields[4] = fields[5] = 0
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
