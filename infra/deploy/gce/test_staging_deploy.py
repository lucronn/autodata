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


if __name__ == '__main__': unittest.main()
