"""Offline checks of the real fixture's final browser subprocess boundary."""
import ast
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'workers/ingestion-python/tests/test_workshop_browser_integration.py'


class BrowserBoundary(Exception):
    pass


@contextmanager
def served(_handler):
    yield 'https://127.0.0.1:12345'


class BrowserEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = {
            'PATH': os.defpath, 'GOTOOLCHAIN': 'local', 'GOPROXY': 'off',
            'GOCACHE': str(self.root / 'go-cache'), 'GOTMPDIR': str(self.root / 'go-tmp'),
            'GOMODCACHE': '/fixture/go-modules', 'PLAYWRIGHT_BROWSERS_PATH': '/fixture/browsers',
            'XDG_CACHE_HOME': '/fixture/cache', 'XDG_CONFIG_HOME': '/fixture/config',
            'TMPDIR': '/fixture/tmp',
            'AUTODATA_R3_CANDIDATE_SHA': 'a' * 40,
            'AUTODATA_WORKSHOP_BROWSER_DATABASE': 'lifecycle_test_offline',
            'INCEPTION_API_KEY': 'secret-sentinel', 'UNRELATED_SECRET': 'secret-sentinel',
        }

    def run_to_browser(self, directory):
        """Execute _child, replacing only its external API/worker/process services."""
        directory.mkdir(mode=0o700, exist_ok=True)
        (directory / 'ready.json').write_text(json.dumps({'kind': 'api-fixture', 'origin': 'https://127.0.0.1:12345'}))
        captured = []
        process = SimpleNamespace(poll=lambda: None, terminate=lambda: None, wait=lambda **_: 0)

        def browser_run(_command, **kwargs):
            captured.append(kwargs['env'])
            raise BrowserBoundary()

        def go_start(*_args, **kwargs):
            self.assertNotIn('HOME', kwargs['env'])
            return process

        runtime = SimpleNamespace(env={}, vehicle='vehicle', article_id='article',
                                  articles={'bankone': 'one', 'banktwo': 'two'}, bucket='fixture', close=lambda: None)
        bridge = SimpleNamespace(token='fixture-token', model_handler=lambda: None,
                                 ensure_handler=lambda: None, control_handler=lambda: None,
                                 release_model=SimpleNamespace(set=lambda: None), stop=lambda: None)
        namespace = dict(ExitStack=ExitStack, json=json, os=os, Path=Path, time=time,
                         sys=sys, stat=stat, ROOT=ROOT, Repository=lambda _: SimpleNamespace(database_name='lifecycle_test_offline'),
                         LifecycleRuntime=lambda *_: runtime, BrowserBridge=lambda _: bridge,
                         configure_scoped_runtime=lambda *_: {'configuration': 'one', 'adjacent': 'two', 'other_region': 'three', 'unscoped': 'four'},
                         serve=served, subprocess=SimpleNamespace(Popen=go_start, run=browser_run, STDOUT=subprocess.STDOUT, TimeoutExpired=subprocess.TimeoutExpired))
        # Compile the actual fixture functions without importing its PostgreSQL/worker dependencies.
        tree = ast.parse(FIXTURE.read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and not node.decorator_list]
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(FIXTURE), 'exec'), namespace)
        with patch.dict(os.environ, self.environment, clear=True):
            try:
                namespace['_child']('offline-case', 'chromium', 'bankone', directory,
                                    SimpleNamespace(setenv=lambda key, value: os.environ.__setitem__(key, value)))
            except BrowserBoundary:
                pass
        return captured

    def test_final_browser_gets_private_home_without_inheriting_host_home(self):
        homes = []
        for index, inherited in enumerate((None, '/', '', '/host-only/private-home')):
            with self.subTest(inherited=inherited):
                if inherited is None:
                    self.environment.pop('HOME', None)
                else:
                    self.environment['HOME'] = inherited
                case = self.root / str(index)
                (environment,) = self.run_to_browser(case)
                self.assertIn('HOME', environment, 'final browser boundary has no HOME for numeric UID without passwd entry')
                home = Path(environment['HOME'])
                self.assertEqual(home, case / 'browser-home')
                self.assertTrue(home.is_absolute())
                self.assertFalse(home.is_symlink())
                self.assertEqual(stat.S_IMODE(home.stat().st_mode), 0o700)
                self.assertEqual(home.stat().st_uid, os.getuid())
                (home / 'writable').write_text('owned')
                self.assertNotIn('secret-sentinel', environment.values())
                for key in ('GOCACHE', 'GOTMPDIR', 'GOMODCACHE', 'PLAYWRIGHT_BROWSERS_PATH', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'TMPDIR'):
                    self.assertEqual(environment[key], self.environment[key])
                homes.append(home)
        self.assertEqual(len(set(homes)), 4)

    def test_existing_directory_file_and_symlink_fail_before_browser_start(self):
        for kind in ('directory', 'file', 'symlink'):
            with self.subTest(kind=kind):
                case = self.root / kind
                case.mkdir(mode=0o700)
                home = case / 'browser-home'
                if kind == 'directory':
                    home.mkdir(mode=0o700)
                elif kind == 'file':
                    home.write_text('collision')
                else:
                    home.symlink_to(self.root, target_is_directory=True)
                with self.assertRaises(FileExistsError):
                    self.run_to_browser(case)

    def test_explicit_home_avoids_absent_passwd_lookup_for_numeric_uid(self):
        (environment,) = self.run_to_browser(self.root / 'numeric-uid')
        with patch.dict(os.environ, {}, clear=True), patch.object(pwd, 'getpwuid', side_effect=KeyError(os.getuid())) as lookup:
            with self.assertRaises(RuntimeError):
                Path.home()
            self.assertEqual(lookup.call_args.args, (os.getuid(),))
            lookup.reset_mock()
            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual(Path.home(), self.root / 'numeric-uid/browser-home')
            lookup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
