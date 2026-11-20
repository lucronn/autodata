"""Offline checks of the real fixture's failed final browser subprocess boundary."""
from contextlib import ExitStack, contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import socket
import ssl  # Load HTTPS dependencies before installing the socket guard.
import stat
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'workers/ingestion-python/tests/test_workshop_browser_integration.py'
ROOT_NAME = 'test_browser_google_exchange_checkout_library_real_api'
HANDOFF = ('AUTODATA_API21_BINDING', 'AUTODATA_API21_RUN_ID', 'AUTODATA_API21_ATTEMPT_ID')
CACHE_KEYS = ('GOCACHE', 'GOTMPDIR', 'GOMODCACHE', 'PLAYWRIGHT_BROWSERS_PATH',
              'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'TMPDIR')


class BrowserBoundary(Exception):
    """Deliberate failure before any actual browser process is launched."""


@contextmanager
def private_producer():
    """Import the complete producer privately, denying external operations by default."""
    forbidden = {}

    def deny(name):
        forbidden[name] = []

        def called(*args, **kwargs):
            forbidden[name].append((args, kwargs))
            raise AssertionError('forbidden external operation: ' + name)
        return called

    lifecycle = ModuleType('lifecycle_support')
    for name in ('fresh_database', 'Repository', 'LifecycleRuntime'):
        setattr(lifecycle, name, deny(name))
    paid = ModuleType('test_paid_catalog_api_integration')
    denied_bridge = deny('PaidBridge')

    class PaidBridge:
        def __init__(self, *args, **kwargs):
            denied_bridge(*args, **kwargs)

    paid.PaidBridge = PaidBridge
    for name in ('configure_scoped_runtime', 'serve'):
        setattr(paid, name, deny(name))
    with ExitStack() as stack:
        stack.enter_context(patch.dict(sys.modules, {
            'lifecycle_support': lifecycle, 'test_paid_catalog_api_integration': paid}))
        for target, name in ((subprocess, 'Popen'), (subprocess, 'run'),
                             (socket, 'socket'), (os, 'killpg'), (urllib.request, 'urlopen')):
            stack.enter_context(patch.object(target, name, deny(target.__name__ + '.' + name)))
        spec = importlib.util.spec_from_file_location('_private_environment_api21', FIXTURE)
        module = importlib.util.module_from_spec(spec)
        stack.enter_context(patch.dict(sys.modules, {spec.name: module}))
        spec.loader.exec_module(module)
        stack.enter_context(patch.object(module, 'urlopen', deny('integration.urlopen')))
        stack.enter_context(patch.object(module, 'BrowserBridge', deny('BrowserBridge')))
        yield module, forbidden


class FakeGoProcess:
    """Stateful owned process; cleanup must explicitly wait for its fake exit."""
    def __init__(self, calls):
        self.calls = calls
        self.returncode = None

    def poll(self):
        self.calls['poll'].append(())
        return self.returncode

    def terminate(self):
        self.calls['terminate'].append(())

    def kill(self):
        self.calls['kill'].append(())

    def wait(self, *, timeout):
        self.calls['wait'].append(timeout)
        self.returncode = 0
        return self.returncode


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
            'AUTODATA_API21_SOURCE_TREE': 'b' * 40,
            'AUTODATA_WORKSHOP_BROWSER_DATABASE': 'lifecycle_test_offline',
            'INCEPTION_API_KEY': 'secret-sentinel', 'UNRELATED_SECRET': 'secret-sentinel',
        }

    def run_to_browser(self, directory, *, invalid_handoff=None, collision=False):
        """Run real _child with an inherited binding and only explicit offline services."""
        directory.mkdir(mode=0o700, exist_ok=True)
        (directory / 'ready.json').write_text(json.dumps({
            'kind': 'api-fixture', 'origin': 'https://127.0.0.1:12345'}))
        calls = {name: [] for name in ('Repository', 'runtime', 'configure', 'bridge', 'serve',
                 'go', 'browser', 'poll', 'terminate', 'kill', 'wait', 'stop', 'close',
                 'stop_workers', 'release_model')}

        def record(name, value):
            calls[name].append(value)

        def browser_run(command, **kwargs):
            record('browser', (command, kwargs))
            raise BrowserBoundary('deliberate offline boundary')

        def go_start(command, **kwargs):
            record('go', (command, kwargs))
            return FakeGoProcess(calls)

        def repository(database):
            record('Repository', database)
            return SimpleNamespace(database_name=database)

        def runtime_start(repo, stack):
            record('runtime', repo)
            return SimpleNamespace(env={}, vehicle='vehicle', article_id='article',
                articles={'bankone': 'one', 'banktwo': 'two'}, bucket='fixture',
                workers=[], logs=[], barrier=None, close=lambda: record('close', ()),
                stop_workers=lambda: record('stop_workers', ()))

        def bridge_start(runtime):
            record('bridge', runtime)

            def stop():
                record('stop', ())
                return []
            return SimpleNamespace(token='fixture-token', model_handler=lambda: 'model',
                ensure_handler=lambda: 'ensure', control_handler=lambda: 'control', stop=stop,
                release_model=SimpleNamespace(set=lambda: record('release_model', ())))

        def configure(runtime, provider):
            record('configure', provider)
            return {'configuration': 'one', 'adjacent': 'two', 'other_region': 'three', 'unscoped': 'four'}

        @contextmanager
        def serve(handler):
            record('serve', handler)
            yield 'https://127.0.0.1:12345'

        with patch.dict(os.environ, self.environment, clear=True), private_producer() as (module, forbidden):
            self.assertEqual(Path(module.__file__), FIXTURE)
            self.assertEqual(module.ROOT, ROOT)
            module.ARTIFACT_ROOT = self.root
            parent = module._binding(ROOT_NAME, 'chromium', 'bankone', 'parent-pytest')
            self.assertEqual(parent['binding_state'], 'complete')
            hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in module._INPUTS}
            self.assertEqual(len(hashes), 7)
            self.assertEqual(parent['source_input_sha256'], hashes)
            inherited = module._binding_env(parent, 'child-pytest')
            os.environ.update(inherited)
            if invalid_handoff == 'absent':
                for key in HANDOFF:
                    os.environ.pop(key)
            elif invalid_handoff:
                action, key = invalid_handoff.split('-', 1)
                key = dict(binding=HANDOFF[0], run=HANDOFF[1], attempt=HANDOFF[2])[key]
                if action == 'missing':
                    os.environ.pop(key)
                else:
                    os.environ[key] = '' if action == 'empty' else 'invalid-identity'
            if invalid_handoff is None:
                module.Repository = repository
                module.LifecycleRuntime = runtime_start
                module.BrowserBridge = bridge_start
                module.configure_scoped_runtime = configure
                module.serve = serve
                # Keep the process-wide subprocess guards installed; sanction only these two calls.
                module.subprocess = SimpleNamespace(Popen=go_start, run=browser_run,
                    STDOUT=subprocess.STDOUT, TimeoutExpired=subprocess.TimeoutExpired)
            error = 'assertion_failed' if invalid_handoff else 'internal_error'
            try:
                with self.assertRaisesRegex(RuntimeError, '^API21 ' + error + '$'):
                    module._child(ROOT_NAME, 'chromium', 'bankone', directory,
                        SimpleNamespace(setenv=lambda key, value: os.environ.__setitem__(key, value)))
            finally:
                self.assertEqual({name: len(rows) for name, rows in forbidden.items()},
                                 dict.fromkeys(forbidden, 0), 'forbidden calls survived producer sanitization')
            result = json.loads((directory / 'result.json').read_text())
            sidecar = json.loads((directory / 'child-processes.json').read_text())
            self.assertFalse(result['passed'])
            self.assertEqual(sidecar['status'], 'failed')
            self.assertEqual(sidecar['primary_failure'], error)
            self.assertIsNone(sidecar['publication_failure'])
            self.assertIsNone(sidecar['browser_runner']['return_code'])
            self.assertEqual(sidecar['browser_runner']['return_code_source'], 'unavailable')
            self.assertIsNone(sidecar['engine_os_exit'])
            self.assertIsNone(sidecar['outer_pytest_exit'])
            binding = result['binding']
            self.assertEqual(sidecar['binding'], binding)
            self.assertEqual(binding['candidate_sha'], 'a' * 40)
            self.assertEqual(binding['source_tree'], 'b' * 40)
            self.assertEqual(binding['source_input_sha256'], hashes)
            self.assertEqual(binding['producer_role'], 'child-pytest')
            if invalid_handoff is None:
                self.assertEqual(binding, dict(parent, producer_role='child-pytest'))
                for name in ('Repository', 'runtime', 'configure', 'bridge', 'go', 'wait', 'terminate', 'stop', 'close', 'release_model'):
                    self.assertEqual(len(calls[name]), 1, name)
                self.assertEqual(calls['serve'], ['model', 'ensure', 'control'])
                self.assertEqual(calls['wait'], [2])
                self.assertEqual(calls['kill'], [])
                self.assertEqual(calls['stop_workers'], [])
                self.assertEqual(sidecar['go']['return_code'], 0)
                self.assertEqual(sidecar['go']['return_code_source'], 'wait')
                self.assertTrue(sidecar['go']['reaped'])
                self.assertEqual(len(calls['browser']), 0 if collision else 1)
                go_argv, go_kwargs = calls['go'][0]
                self.assertEqual(go_argv, ['go', 'test', '-count=1', '-run', '^TestWorkshopBrowserFixtureHTTP$', '-timeout=85s', '.'])
                self.assertEqual(go_kwargs['cwd'], ROOT / 'apps/api-go')
                self.assertNotIn('HOME', go_kwargs['env'])
                if not collision:
                    argv, kwargs = calls['browser'][0]
                    self.assertEqual(argv, [sys.executable, str(ROOT / 'scripts/dev/workshop_browser_smoke.py'),
                        '--base-url', 'https://127.0.0.1:12345', '--mode', 'api-fixture', '--browser', 'chromium',
                        '--candidate-sha', 'a' * 40, '--output', str(directory / 'browser')])
                    self.assertEqual(kwargs['cwd'], ROOT)
                    self.assertGreater(kwargs['timeout'], 0)
                    self.assertLessEqual(kwargs['timeout'], 70)
                    environment = kwargs['env']
                    browser_binding = json.loads(environment[HANDOFF[0]])
                    self.assertEqual(browser_binding, dict(parent, producer_role='browser-runner'))
                    self.assertEqual(environment[HANDOFF[1]], parent['run_id'])
                    self.assertEqual(environment[HANDOFF[2]], parent['attempt_id'])
                    self.assertEqual(environment['AUTODATA_API21_SOURCE_TREE'], 'b' * 40)
            else:
                self.assertEqual({name: len(rows) for name, rows in calls.items()}, dict.fromkeys(calls, 0))
                self.assertEqual(binding['binding_state'], 'partial')
                self.assertEqual(binding['unavailable_reason'], 'source_binding_failed')
                for name, kinds in (('run_id', ('absent', 'missing-run', 'malformed-run')),
                                    ('attempt_id', ('absent', 'missing-attempt', 'malformed-attempt'))):
                    self.assertEqual(binding[name], None if invalid_handoff in kinds else parent[name])
                self.assertFalse(sidecar['go']['launched'])
                self.assertFalse(sidecar['browser_runner']['launched'])
        return SimpleNamespace(calls=calls, result=result, sidecar=sidecar)

    def test_final_browser_gets_private_home_without_inheriting_host_home(self):
        homes = []
        for index, inherited in enumerate((None, '/', '', '/host-only/private-home')):
            with self.subTest(inherited=inherited):
                if inherited is None:
                    self.environment.pop('HOME', None)
                else:
                    self.environment['HOME'] = inherited
                case = self.root / str(index)
                outcome = self.run_to_browser(case)
                environment = outcome.calls['browser'][0][1]['env']
                self.assertIn('HOME', environment, 'final browser boundary has no HOME for numeric UID without passwd entry')
                home = Path(environment['HOME'])
                self.assertEqual(home, case / 'browser-home')
                self.assertTrue(home.is_absolute())
                self.assertFalse(home.is_symlink())
                self.assertEqual(stat.S_IMODE(home.stat().st_mode), 0o700)
                self.assertEqual(home.stat().st_uid, os.getuid())
                (home / 'writable').write_text('owned')
                self.assertNotIn('secret-sentinel', environment.values())
                self.assertNotIn('INCEPTION_API_KEY', environment)
                self.assertNotIn('UNRELATED_SECRET', environment)
                for key in CACHE_KEYS:
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
                    (home / 'original').write_text('owned-original')
                elif kind == 'file':
                    home.write_text('collision')
                else:
                    home.symlink_to(self.root, target_is_directory=True)
                before = home.lstat()
                self.run_to_browser(case, collision=True)
                after = home.lstat()
                self.assertEqual((after.st_dev, after.st_ino, after.st_mode),
                                 (before.st_dev, before.st_ino, before.st_mode))
                if kind == 'directory':
                    self.assertEqual(list(home.iterdir()), [home / 'original'])
                    self.assertEqual((home / 'original').read_text(), 'owned-original')
                elif kind == 'file':
                    self.assertEqual(home.read_text(), 'collision')
                else:
                    self.assertEqual(home.readlink(), self.root)

    def test_invalid_parent_handoff_fails_before_external_dependencies(self):
        for kind in ('absent', 'missing-binding', 'empty-binding', 'missing-run',
                     'missing-attempt', 'malformed-run', 'malformed-attempt'):
            with self.subTest(kind=kind):
                self.run_to_browser(self.root / kind, invalid_handoff=kind)

    def test_explicit_home_avoids_absent_passwd_lookup_for_numeric_uid(self):
        outcome = self.run_to_browser(self.root / 'numeric-uid')
        environment = outcome.calls['browser'][0][1]['env']
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
