"""Local-only fixed operator contracts; no cloud or host application."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
SHA = 'a' * 40
HASH = 'b' * 64


def load():
    path = HERE / 'staging_deploy.py'
    if not path.exists():
        raise AssertionError('fixed staging operator is missing')
    spec = importlib.util.spec_from_file_location('operator_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config():
    return dict(schema_version=1, environment='staging', source_sha=SHA,
        project_id='staging-project', region='us-east1', zone='us-east1-b',
        maximum_monthly_budget_usd=100, staging_origin='https://staging.example.test',
        instance_name='workshop-staging', instance_id='123456789', os_login_user='operator',
        repository_id='123', repository_owner_id='456', protected_environment='workshop-staging-publish',
        wif_provider='projects/123/locations/global/workloadIdentityPools/staging/providers/github',
        service_account='staging@staging-project.iam.gserviceaccount.com',
        registry='us-east1-docker.pkg.dev/staging-project/workshop',
        toolchain_image='us-east1-docker.pkg.dev/staging-project/tools/publisher@sha256:' + HASH,
        service_config_sha256=HASH, bundle_inventory_sha256=HASH,
        known_hosts_sha256=HASH, tools={name: HASH for name in ('gcloud', 'ssh', 'cloud-bootstrap.sh')})


class OperatorContracts(unittest.TestCase):
    def test_owner_configuration_is_complete_and_staging_only(self):
        op = load()
        op.validate_config(config(), SHA)
        for key in config():
            bad = config(); bad[key] = None
            with self.subTest(key=key), self.assertRaises(op.Rejected):
                op.validate_config(bad, SHA)
        for origin in ('https://cars.tk', 'https://www.cars.tk', 'http://staging.example.test',
                       'https://cars.tk.', 'https://user:pass@staging.example.test', 'https://staging.example.test/path'):
            bad = config(); bad['staging_origin'] = origin
            with self.subTest(origin=origin), self.assertRaises(op.Rejected):
                op.validate_config(bad, SHA)

    def test_fixed_commands_cannot_accept_destinations_or_shell_text(self):
        op = load(); cfg = config()
        for phase in op.PHASES[1:]:
            command = op.remote_argv(cfg, phase, SHA, 'api' if phase == 'private' else None)
            self.assertEqual(command[0], '/usr/bin/gcloud')
            self.assertIn('--tunnel-through-iap', command)
            self.assertIn('--ssh-flag=-oBatchMode=yes', command)
            self.assertIn('--ssh-flag=-oForwardAgent=no', command)
            self.assertIn('--ssh-flag=-oStrictHostKeyChecking=yes', command)
            self.assertIn('--ssh-flag=-oUserKnownHostsFile=/etc/autodata/staging-operator/known_hosts', command)
        for phase in ('destroy', 'receive;touch /tmp/owned', 'stop', '--command'):
            with self.assertRaises(op.Rejected): op.remote_argv(cfg, phase, SHA)
        for value in ('x; touch /tmp/owned', '--project=production', 'a' * 39):
            with self.assertRaises(op.Rejected): op.remote_argv(cfg, 'start', value)

    def test_receipt_claim_dictionary_does_not_authorize_readiness(self):
        op = load()
        claim = dict(schema_version=1, operation='deploy.sh check', source_sha=SHA, status='passed',
                     checks={'runtime_evidence': True}, failure_code=None)
        with self.assertRaises(op.Rejected): op.validate_receipt('check', claim, SHA, HASH)
        claim['checks'] = dict.fromkeys(op.READINESS, True)
        claim.update(run_id=None, started_at='2026-11-05T12:00:00Z', finished_at='2026-11-05T12:00:01Z')
        op.validate_receipt('check', claim, SHA, HASH)
        for key in op.READINESS:
            bad = copy.deepcopy(claim); bad['checks'][key] = False
            with self.subTest(key=key), self.assertRaises(op.Rejected): op.validate_receipt('check', bad, SHA, HASH)

    def test_real_bounded_process_rejects_failure_oversize_and_timeout(self):
        op = load()
        result = op.run_process(['/usr/bin/python3', '-I', '-c', 'print("local process")'], timeout=2)
        self.assertEqual(result, b'local process\n')
        for code, kwargs in [('raise SystemExit(9)', {}), ('print("x" * 65536)', {'maximum': 100}),
                             ('import time; time.sleep(3)', {'timeout': .05})]:
            with self.subTest(code=code), self.assertRaises(op.Incomplete):
                op.run_process(['/usr/bin/python3', '-I', '-c', code], **kwargs)

    def test_cli_rejects_extra_flags_and_invalid_sha_before_input_access(self):
        for args in ([], ['start', SHA, '--project=evil'], ['start', 'bad'], ['destroy', SHA]):
            result = subprocess.run([sys.executable, '-I', str(HERE/'staging_deploy.py'), *args],
                                    capture_output=True, timeout=3)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)['failure_code'], 'invalid_input')
            self.assertNotIn(b'evil', result.stdout)

    def test_duplicate_json_never_silently_changes_approval(self):
        op = load()
        for raw in (b'{"phase":"start","phase":"check"}', b'{"budget":NaN}', b'[]'):
            with self.assertRaises(op.Rejected): op.object_json(raw)


class PhaseAuthority(unittest.TestCase):
    def approval(self, op, phase='install'):
        return dict(schema_version=1, phase=phase, authorization_id='12345678-1234-4234-8234-123456789abc',
            expires_at=(datetime.now(timezone.utc)+timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            source_sha=SHA, operator_config_sha256=op.digest(op.canonical(config())),
            instance_id='123456789', service_config_sha256=HASH, service=None,
            predecessor_sha256=HASH, inputs={'host_approval_sha256': HASH})

    def test_phase_approval_binds_config_host_source_expiry_and_predecessor(self):
        op = load(); good = self.approval(op)
        op.validate_phase_approval(good, config(), 'install', SHA, HASH)
        for key, value in [('source_sha', 'c'*40), ('instance_id', '9'), ('phase', 'database'),
                           ('expires_at', '2000-01-01T00:00:00Z'), ('operator_config_sha256', 'c'*64),
                           ('predecessor_sha256', 'c'*64), ('service', 'api')]:
            bad = copy.deepcopy(good); bad[key] = value
            with self.subTest(key=key), self.assertRaises(op.Rejected):
                op.validate_phase_approval(bad, config(), 'install', SHA, HASH)

    def test_private_requires_the_next_service_and_five_verified_receipts(self):
        op = load()
        self.assertEqual(op.next_private([]), 'api')
        self.assertEqual(op.next_private(['api', 'ingestion-http']), 'article-worker')
        self.assertIsNone(op.next_private(list(op.SERVICES)))
        for prior in (['article-worker'], ['api', 'api'], list(reversed(op.SERVICES))):
            with self.assertRaises(op.Rejected): op.next_private(prior)

    def test_transfer_exact_inventory_and_approval_binding(self):
        import base64
        op = load()
        approval = {'files': [{'path': name, 'bytes': len(raw), 'sha256': op.digest(raw)}
                    for name, raw in [('db/migrations/001_first.sql', b'sql'), ('release.json', b'{}'),
                                      ('scripts/dev/migrate_sql.sh', b'sh')]]}
        approval['publisher_verification_receipt_sha256'] = op.digest(b'{"verified":true}')
        members = {item['path']: raw for item, raw in zip(approval['files'], (b'sql', b'{}', b'sh'))}
        members['publisher-verification.json'] = b'{"verified":true}'
        frame = dict(schema_version=1, source_sha=SHA, install_approval_sha256=HASH,
                     files=[{'path': name, 'data': base64.b64encode(raw).decode()} for name, raw in members.items()])
        self.assertEqual(op.decode_transfer(op.canonical(frame), SHA, HASH, approval), members)
        for change in ('traversal', 'duplicate', 'link', 'approval', 'unknown', 'oversized'):
            bad = copy.deepcopy(frame)
            if change == 'traversal': bad['files'][0]['path'] = '../etc/shadow'
            if change == 'duplicate': bad['files'].append(bad['files'][0])
            if change == 'link': bad['files'][0]['link'] = '/etc/shadow'
            if change == 'approval': bad['install_approval_sha256'] = 'c'*64
            if change == 'unknown': bad['files'][0]['path'] = 'secrets/api.env'
            if change == 'oversized': bad['files'][0]['data'] = base64.b64encode(b'x'*(op.MIB+1)).decode()
            with self.subTest(change=change), self.assertRaises(op.Rejected):
                op.decode_transfer(op.canonical(bad), SHA, HASH, approval)

    def test_receiver_commits_real_local_files_and_denies_collision(self):
        import os
        import tempfile
        op = load()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'incoming').mkdir(mode=0o700); (root/'evidence').mkdir(mode=0o700)
            incoming = os.open(root/'incoming', os.O_RDONLY|os.O_DIRECTORY)
            evidence = os.open(root/'evidence', os.O_RDONLY|os.O_DIRECTORY)
            members = {'release.json': b'{}', 'db/migrations/001_first.sql': b'sql',
                       'scripts/dev/migrate_sql.sh': b'sh', 'publisher-verification.json': b'evidence'}
            try:
                op.commit_transfer(incoming, evidence, SHA, members)
                self.assertEqual((root/'incoming'/SHA/'release.json').read_bytes(), b'{}')
                self.assertEqual((root/'evidence'/(SHA+'.json')).read_bytes(), b'evidence')
                self.assertEqual((root/'incoming'/SHA/'db/migrations/001_first.sql').stat().st_mode & 0o777, 0o444)
                with self.assertRaises((op.Rejected, FileExistsError)):
                    op.commit_transfer(incoming, evidence, SHA, members)
            finally: os.close(incoming); os.close(evidence)

class ExecutableWiring(unittest.TestCase):
    def test_preflight_missing_owner_material_reaches_no_process(self):
        from unittest.mock import patch
        op = load()
        with patch.object(op, 'run_process', side_effect=AssertionError('no process before owner inputs')):
            code, result = op.main(['start', SHA])
        self.assertNotEqual(code, 0)
        self.assertNotEqual(result.get('status'), 'staging_deployed')

    def test_transfer_read_is_deadline_and_size_bounded(self):
        import os
        import threading
        op = load()
        read_fd, write_fd = os.pipe()
        def writer():
            try: os.write(write_fd, b'opaque-secret-stream')
            finally: os.close(write_fd)
        thread = threading.Thread(target=writer); thread.start()
        try: self.assertEqual(op.read_pipe(read_fd, maximum=100, timeout=1), b'opaque-secret-stream')
        finally: os.close(read_fd); thread.join()
        read_fd, write_fd = os.pipe()
        try:
            with self.assertRaises(op.Incomplete): op.read_pipe(read_fd, maximum=100, timeout=.01)
        finally: os.close(read_fd); os.close(write_fd)

    def test_unverified_or_simulated_publication_is_denied(self):
        op = load()
        receipt = dict(protocol_version=3, status='publication_verified', simulation=False,
            provenance_authenticated=True, deployment_authorized=False, binding_sha256=HASH,
            checks=dict(schema=False, services=False, runtime_evidence=False))
        op.validate_publication_receipt(receipt, HASH)
        for key, value in [('protocol_version', 2), ('simulation', True), ('provenance_authenticated', False),
                           ('deployment_authorized', True), ('binding_sha256', 'c'*64), ('checks', {'runtime_evidence': True})]:
            bad = copy.deepcopy(receipt); bad[key] = value
            with self.subTest(key=key), self.assertRaises(op.Rejected): op.validate_publication_receipt(bad, HASH)

class OrderingAndCancellation(unittest.TestCase):
    def test_start_requires_all_five_private_receipts(self):
        op = load()
        class MissingPins:
            def read(self, path, **kwargs): raise FileNotFoundError()
        with self.assertRaises(op.Rejected): op.predecessor(MissingPins(), config(), 'start')

    def test_remote_identity_is_not_an_injected_destination(self):
        op = load()
        for field in ('project_id', 'zone', 'instance_name', 'os_login_user'):
            bad = config(); bad[field] = 'a;echo owned'
            with self.subTest(field=field), self.assertRaises(op.Rejected): op.host_argv(bad, 'start', SHA)
        argv = op.host_argv(config(), 'provision', SHA)
        self.assertIn('/var/lib/autodata-bootstrap/bundle/opt/autodata/bin/staging_deploy.py', argv[-1])
        self.assertIn('--host-phase provision '+SHA, argv[-1])

    def test_signal_cleans_owned_process_group(self):
        import os
        import signal
        import tempfile
        import time
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder)/'child.pid'
            driver = ('import importlib.util; '
                's=importlib.util.spec_from_file_location("op", '+repr(str(HERE/'staging_deploy.py'))+'); '
                'op=importlib.util.module_from_spec(s); s.loader.exec_module(op); '
                'op.run_process(["/usr/bin/python3","-I","-c",'
                +repr('import os,time; from pathlib import Path; Path('+repr(str(marker))+').write_text(str(os.getpid())); time.sleep(30)')+'])')
            process = subprocess.Popen([sys.executable, '-I', '-c', driver], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                end = time.monotonic()+3
                while not marker.exists() and time.monotonic() < end: time.sleep(.01)
                self.assertTrue(marker.exists())
                child = int(marker.read_text())
                process.send_signal(signal.SIGTERM); process.communicate(timeout=3)
                with self.assertRaises(ProcessLookupError): os.kill(child, 0)
            finally:
                if process.poll() is None: process.kill(); process.communicate()
                if marker.exists():
                    try: os.kill(int(marker.read_text()), signal.SIGKILL)
                    except ProcessLookupError: pass

class BootstrapBoundary(unittest.TestCase):
    def test_only_bootstrap_permits_unknown_generated_host_identity(self):
        op = load(); initial = config()
        initial['instance_id'] = None; initial['known_hosts_sha256'] = None
        op.validate_config(initial, SHA, bootstrap=True)
        for phase in op.PHASES[1:]:
            with self.subTest(phase=phase), self.assertRaises(op.Rejected): op.validate_config(initial, SHA)
        for field in ('instance_id', 'known_hosts_sha256'):
            missing = config(); missing[field] = None
            with self.subTest(field=field), self.assertRaises(op.Rejected): op.validate_config(missing, SHA)

    def test_remote_receiver_modes_are_not_operator_cli_flags(self):
        op = load()
        for args in (['--receive', SHA], ['--host-phase', 'private', SHA]):
            self.assertEqual(op.entry(args)[0], 2)
