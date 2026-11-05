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

    def test_executable_staging_launch_uses_pinned_control_and_owner_runner(self):
        for name in ('staging-build-candidate', 'staging-finalize'):
            job = self.workflow['jobs'][name]
            self.assertEqual(job['runs-on'], ['self-hosted','linux','x64','workshop-staging-publisher'])
            steps = job['steps']
            self.assertEqual(len(steps), 3)
            self.assertEqual(steps[0]['id'], 'validate')
            self.assertEqual(steps[1]['uses'], 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683')
            self.assertEqual(steps[1]['with'], {'ref': '${{ github.workflow_sha }}', 'path': 'control', 'persist-credentials': False, 'fetch-depth': 1, 'submodules': False, 'lfs': False})
            self.assertEqual(steps[2]['uses'], 'actions/github-script@ed597411d8f924073f98dfc5c65a23a2325f34cd')
            self.assertEqual(steps[2]['env'], {'GITHUB_TOKEN':'${{ github.token }}'})
            for step in steps:
                for field in ('if','continue-on-error'): self.assertNotIn(field, step)
            script = steps[2]['with']['script']
            self.assertNotIn('${{', script)
            self.assertNotIn('GITHUB_ENV', script)
            self.assertNotIn('npm install', script)
            self.assertIn("'--pull=never'", script)
            self.assertIn("'--read-only'", script)
            self.assertIn("'--cap-drop=ALL'", script)
            self.assertIn('readonly', script)
            self.assertIn("'--installed-policy'", script)
            self.assertIn("'--authenticate-context'", script)
            self.assertIn("'auth','login','--cred-file'", script)
            self.assertIn("'auth','print-access-token'", script)
            self.assertIn("'/control/infra/deploy/gce/publisher_cli.py',e.OPERATION,e.SOURCE_SHA", script)
            self.assertLess(script.index("helper,'--installed-policy'"), script.index('const credentials='))
            self.assertLess(script.index("await container('/usr/bin/python3',['-I','-c',preflight"), script.index('const credentials='))
            self.assertLess(script.index("helper,'--authenticate-context'"), script.index('const external='))
            self.assertIn("runtime[field]===installed.live_policy[field]", script)
            self.assertIn('service_account_impersonation_url', script)
            self.assertIn("ownedContainers.add", script)

    def test_static_registry_token_window_bounds_the_entire_cli_and_cleanup(self):
        import re
        node = '/tmp/node-v22.23.4-linux-x64/bin/node'
        if not Path(node).exists(): node = 'node'
        for name in ('staging-build-candidate', 'staging-finalize'):
            script = self.workflow['jobs'][name]['steps'][2]['with']['script']
            self.assertIn('service_account_impersonation:{token_lifetime_seconds:3600}', script)
            self.assertNotIn('7200000', script)
            self.assertLess(script.index('const credentialStartedAt=performance.now()'), script.index("await container('/usr/bin/python3',['-I','-c',exchange]"))
            self.assertIn('credentialWindow(credentialStartedAt)', script)
            body = re.search(r'function credentialWindow\(startedAt,now=performance.now\(\)\) \{([\s\S]*?)\n\}', script).group(1)
            harness = r"""
const assert=require('node:assert/strict');
const requireValue=value=>{if(!value)throw Error('credential_window_expired');};
const credentialWindow=Function('requireValue','return function(startedAt,now){'+process.argv[1]+'}')(requireValue);
assert.equal(credentialWindow(1000,1000),45*60*1000);
assert.equal(credentialWindow(1000,1000+5*60*1000),40*60*1000);
assert.equal(credentialWindow(1000,1000+45*60*1000-30001),30001);
for(const [start,now] of [[1000,1000+45*60*1000-30000],[1000,1000+45*60*1000],[1000,1000+60*60*1000],[1000,999],[NaN,1000],[1000,Infinity]])assert.throws(()=>credentialWindow(start,now));
// The fixed one-hour IAM token request leaves at least ten minutes beyond
// the maximum45-minute operation and five-minute cleanup reserve.
assert.ok(credentialWindow(1000,1000)+5*60*1000<=3600*1000-10*60*1000);
"""
            result=subprocess.run([node,'-e',harness,body],capture_output=True,timeout=3)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_launch_script_and_embedded_python_are_executable_and_precredential_failure_is_bounded(self):
        script = self.workflow['jobs']['staging-build-candidate']['steps'][2]['with']['script']
        # Compile the actual action body and both finite Python programs. No
        # service or SDK fixture is involved in this workflow syntax check.
        node = '/tmp/node-v22.23.4-linux-x64/bin/node'
        if not Path(node).exists(): node = 'node'
        import re
        for name in ('preflight','exchange'):
            template = re.search(r'const '+name+r' = `([\s\S]*?)`;', script).group(1)
            decoded = subprocess.run([node,'-e','process.stdout.write(Function("return `"+process.argv[1]+"`")())',template],capture_output=True,check=True,timeout=3).stdout.decode()
            compile(decoded, '<workflow-'+name+'>', 'exec')
        harness = r"""
const fs=require('node:fs');
const script=fs.readFileSync(0,'utf8');
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
let secretReads=0;
const allowed={EVENT_NAME:'workflow_dispatch',REPOSITORY:'wrong',REF:'refs/heads/master'};
const fakeProcess={getuid:()=>0,platform:'linux',env:new Proxy(allowed,{get(target,key){if(!(key in target)){secretReads++;throw Error('secret access');}return target[key];}})};
new AsyncFunction('require','process','core',script)(require,fakeProcess,{info(){throw Error('unexpected output');}}).then(()=>process.exit(9)).catch(error=>{if(secretReads||!error.message.startsWith('missing_dependency:'))process.exit(8);});
"""
        result = subprocess.run([node,'-e',harness],input=script.encode(),capture_output=True,timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'')

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
