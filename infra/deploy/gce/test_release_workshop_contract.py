"""Read the JSON-compatible workflow without running a workflow or credentials."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

WORKFLOW = Path(__file__).resolve().parents[3] / '.github/workflows/release-workshop.yml'
BASELINE = {
    'publish': '5e1618ac1a73b3ecdb08a43226be6edc9d3178922be3c1e7369b2f9f36168763',
    'deploy': 'f9f4133f0092899a1174044ea4fd7dd8258e1fd21ae1828cb543095dd013f731',
}


class ReleaseWorkflowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = json.loads(WORKFLOW.read_text())

    def test_production_authority_equals_pinned_checkpoint(self):
        self.assertEqual(self.workflow['permissions'], {'contents': 'read'})
        for name, digest in BASELINE.items():
            raw = json.dumps(self.workflow['jobs'][name], sort_keys=True, separators=(',', ':')).encode()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)

    def test_only_staging_jobs_receive_dormant_oidc_scope(self):
        self.assertEqual(set(self.workflow['jobs']), {'publish', 'deploy', 'staging-build-candidate', 'staging-finalize'})
        choices = self.workflow['on']['workflow_dispatch']['inputs']['operation']['options']
        self.assertEqual(choices, ['publish', 'deploy', 'staging-build-candidate', 'staging-finalize'])
        for name in ('staging-build-candidate', 'staging-finalize'):
            job = self.workflow['jobs'][name]
            self.assertEqual(job['environment'], 'workshop-staging-publish')
            self.assertEqual(job['permissions'], {'contents': 'read', 'actions': 'read', 'id-token': 'write'})
            self.assertEqual(job['timeout-minutes'], 125)
            for guard in ["vars.WORKSHOP_STAGING_PUBLISH_ENABLED == 'true'", "github.repository == 'lucronn/autodata'", "github.ref == 'refs/heads/master'", "github.event_name == 'workflow_dispatch'", f"inputs.operation == '{name}'"]:
                self.assertIn(guard, job['if'])

    def test_no_step_can_bypass_the_unconditional_precredential_blocker(self):
        for name in ('staging-build-candidate', 'staging-finalize'):
            steps = self.workflow['jobs'][name]['steps']
            self.assertEqual(len(steps), 3)
            self.assertEqual(steps[2]['uses'], 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683')
            self.assertEqual(steps[2]['with'], {'ref': '${{ github.workflow_sha }}', 'path': 'control', 'persist-credentials': False, 'fetch-depth': 1, 'submodules': False, 'lfs': False})
            self.assertEqual(steps[0]['id'], 'validate')
            self.assertEqual(steps[1]['id'], 'activation-blocker')
            for step in steps[:2]:
                self.assertNotIn('if', step)
                self.assertNotIn('uses', step)
                self.assertNotIn('continue-on-error', step)
                self.assertNotIn('${{', step['run'])
            result = subprocess.run(['bash', '-c', steps[1]['run']], env={}, capture_output=True, timeout=3)
            self.assertEqual(result.returncode, 3)
            self.assertEqual(result.stdout, b'')
            self.assertIn(b'missing_dependency:', result.stderr)

    def env(self, operation):
        return {
            'EVENT_NAME': 'workflow_dispatch', 'REPOSITORY': 'lucronn/autodata', 'REF': 'refs/heads/master',
            'WORKFLOW_REF': 'lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master',
            'WORKFLOW_SHA': 'a' * 40, 'SOURCE_SHA': 'b' * 40,
            'REPOSITORY_ID': '123', 'EXPECTED_REPOSITORY_ID': '123',
            'REPOSITORY_OWNER_ID': '456', 'EXPECTED_OWNER_ID': '456',
            'RUN_ID': '789', 'RUN_ATTEMPT': '2', 'OPERATION': operation,
            'CONFIG_SHA256': 'c' * 64, 'ACTIVATION_SHA256': 'd' * 64,
            'TOOLCHAIN_SHA256': 'e' * 64, 'TRUST_POLICY_SHA256': 'f' * 64,
            'CANDIDATE_DIGEST': '', 'CANDIDATE_RUN_ID': '', 'CANDIDATE_RUN_ATTEMPT': '', 'APPROVAL_RECORD_SHA256': '',
        }

    def validate(self, name, env):
        script = self.workflow['jobs'][name]['steps'][0]['run']
        # The shell wrapper only starts isolated Python; no checkout/auth/network exists.
        return subprocess.run(['bash', '-c', script], env=env, capture_output=True, timeout=3)

    def test_candidate_validates_separate_source_and_workflow_shas(self):
        env = self.env('staging-build-candidate')
        self.assertEqual(self.validate('staging-build-candidate', env).returncode, 0)
        for field, value in [('EXPECTED_OWNER_ID', ''), ('RUN_ATTEMPT', '0'), ('WORKFLOW_SHA', 'bad'), ('ACTIVATION_SHA256', ''), ('CANDIDATE_DIGEST', 'sha256:' + '1' * 64), ('REPOSITORY_ID', '999'), ('OPERATION', 'staging-finalize')]:
            bad = {**env, field: value}
            result = self.validate('staging-build-candidate', bad)
            self.assertEqual(result.returncode, 2, field)
            self.assertEqual(result.stdout, b'')
            self.assertNotIn(value.encode(), result.stderr) if value else None

    def test_finalize_requires_exact_candidate_and_independent_approval_reference(self):
        env = self.env('staging-finalize')
        self.assertEqual(self.validate('staging-finalize', env).returncode, 2)
        env.update(CANDIDATE_DIGEST='us-central1-docker.pkg.dev/test-project/test-repo/candidate@sha256:' + '1' * 64, CANDIDATE_RUN_ID='788', CANDIDATE_RUN_ATTEMPT='1', APPROVAL_RECORD_SHA256='2' * 64)
        self.assertEqual(self.validate('staging-finalize', env).returncode, 0)
        for field in ('CANDIDATE_DIGEST', 'CANDIDATE_RUN_ID', 'CANDIDATE_RUN_ATTEMPT', 'APPROVAL_RECORD_SHA256'):
            self.assertEqual(self.validate('staging-finalize', {**env, field: ''}).returncode, 2)


if __name__ == '__main__':
    unittest.main()
