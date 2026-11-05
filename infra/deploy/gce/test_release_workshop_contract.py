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

    def node_runtime(self):
        import os
        import shutil
        configured = os.environ.get('AUTODATA_WORKFLOW_NODE')
        executable = shutil.which(configured or 'node')
        if executable: return executable
        if configured or os.environ.get('AUTODATA_REQUIRE_NODE_PROBES') == '1' or os.environ.get('AUTODATA_REQUIRE_DOCKER_CLEANUP') == '1':
            self.fail('required executable workflow Node probe is unavailable')
        self.skipTest('optional executable JS probe requires Node; static workflow contracts still run')

    def test_missing_node_skips_optional_probe_but_required_probe_fails(self):
        import os
        from unittest.mock import patch
        with patch('shutil.which',return_value=None), patch.dict(os.environ,{'AUTODATA_WORKFLOW_NODE':'','AUTODATA_REQUIRE_NODE_PROBES':'','AUTODATA_REQUIRE_DOCKER_CLEANUP':''}):
            with self.assertRaises(unittest.SkipTest): self.node_runtime()
            with patch.dict(os.environ,{'AUTODATA_REQUIRE_NODE_PROBES':'1'}):
                with self.assertRaises(self.failureException): self.node_runtime()

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
            self.assertIn("fs.mkdir(lock,{mode:0o700})", script)
            self.assertIn("credentials/buildx-owner.json", script)
            self.assertIn("owner_nonce:crypto.randomBytes(32).toString('hex')", script)
            self.assertLess(script.index("credentials/buildx-owner.json"),script.index('const credentials='))
            self.assertLess(script.index('cleanupOwnedBuilder(builderOwner,cleanupRemaining)'),script.index('for(const id of ownedContainers)'))
            self.assertIn('builderLock&&!cleanupFailed',script)
            self.assertNotIn("['buildx','rm'",script)

    def test_static_registry_token_window_bounds_the_entire_cli_and_cleanup(self):
        import re
        for name in ('staging-build-candidate', 'staging-finalize'):
            script = self.workflow['jobs'][name]['steps'][2]['with']['script']
            self.assertIn('service_account_impersonation:{token_lifetime_seconds:3600}', script)
            self.assertNotIn('7200000', script)
            self.assertLess(script.index('const credentialStartedAt=performance.now()'), script.index("await container('/usr/bin/python3',['-I','-c',exchange]"))
            self.assertIn('credentialWindow(credentialStartedAt)', script)
            self.assertIsNotNone(re.search(r'function credentialWindow\(startedAt,now=performance.now\(\)\) \{([\s\S]*?)\n\}',script))

    def test_registry_token_window_executable_boundaries(self):
        import re
        node = self.node_runtime()
        for name in ('staging-build-candidate', 'staging-finalize'):
            script = self.workflow['jobs'][name]['steps'][2]['with']['script']
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

    def test_outer_cleanup_requires_nonce_ownership_and_removes_daemon_worker(self):
        node = self.node_runtime()
        import os
        import re
        import secrets
        import shutil
        import tempfile
        import time
        docker = shutil.which('docker')
        required = os.environ.get('AUTODATA_REQUIRE_DOCKER_CLEANUP') == '1'
        if not docker:
            if required: self.fail('real Docker cleanup required')
            self.skipTest('Docker unavailable')
        image = subprocess.run([docker,'image','inspect','python:3.12-slim','--format','{{json .RepoDigests}}'],capture_output=True,timeout=5)
        if image.returncode:
            if required: self.fail('cached immutable local cleanup fixture required')
            self.skipTest('cached immutable local cleanup fixture unavailable')
        image = json.loads(image.stdout)[0]
        script = self.workflow['jobs']['staging-build-candidate']['steps'][2]['with']['script']
        match=re.search(r'// BEGIN OWNED BUILDER CLEANUP\n([\s\S]*?)// END OWNED BUILDER CLEANUP',script)
        self.assertIsNotNone(match,'outer timeout has no daemon-owned builder cleanup')
        helper=match.group(1)
        harness=r"""
const assert=require('node:assert/strict'),{execFile}=require('node:child_process');
const requireValue=value=>{if(!value)throw Error('cleanup_failed');};
const docker=(args,{timeout=5000}={})=>new Promise((resolve,reject)=>execFile('/usr/bin/docker',args,{timeout,maxBuffer:1048576},(error,out)=>error?reject(error):resolve(Buffer.from(out))));
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
new AsyncFunction('docker','requireValue','owner',process.argv[1]+';return cleanupOwnedBuilder(owner,()=>5000);')(docker,requireValue,JSON.parse(process.argv[2])).then(()=>process.exit(0)).catch(()=>process.exit(3));
"""
        def call(args): return subprocess.run([docker,*args],capture_output=True,check=True,timeout=15).stdout
        for mismatch in ('none','container_nonce','volume_label','image'):
            run_id=str(time.time_ns()//1000); builder='workshop-'+run_id+'-1'; name='buildx_buildkit_'+builder+'0'; volume=name+'_state'
            nonce=secrets.token_hex(32)
            owner={'protocol_version':1,'context_sha256':'a'*64,'builder_name':builder,'container_name':name,'owner_nonce':nonce,'buildkit_image':image}
            with tempfile.TemporaryDirectory() as directory:
                Path(directory).chmod(0o777)
                call(['volume','create','--label','autodata.publisher.owner='+('c'*64 if mismatch=='volume_label' else nonce),volume])
                try:
                    call(['run','--pull=never','--detach','--network=none','--name',name,'--env','AUTODATA_PUBLISHER_OWNER='+('b'*64 if mismatch=='container_nonce' else nonce),
                          '--mount','type=volume,src='+volume+',dst=/var/lib/buildkit','--mount','type=bind,src='+directory+',dst=/marker',image,
                          'python','-c','import time;from pathlib import Path;time.sleep(2);Path("/marker/late").write_text("survived");time.sleep(30)'])
                    # The Docker client exited; the daemon-owned worker remains.
                    self.assertTrue(call(['container','ls','--quiet','--filter','name=^/'+name+'$']).strip())
                    if mismatch=='image': owner['buildkit_image']=image.rsplit(':',1)[0]+':'+'0'*64
                    result=subprocess.run([node,'-e',harness,helper,json.dumps(owner)],capture_output=True,timeout=15)
                    self.assertEqual(result.returncode,0 if mismatch=='none' else 3,result.stderr)
                    present=bool(call(['container','ls','--all','--quiet','--filter','name=^/'+name+'$']).strip())
                    self.assertEqual(present,mismatch in ('container_nonce','image'))
                    if mismatch=='none':
                        self.assertFalse(call(['volume','ls','--quiet','--filter','name=^'+volume+'$']).strip())
                        time.sleep(2.2);self.assertFalse((Path(directory)/'late').exists())
                    else:
                        self.assertTrue(call(['volume','ls','--quiet','--filter','name=^'+volume+'$']).strip())
                finally:
                    subprocess.run([docker,'container','rm','--force',name],capture_output=True,timeout=10)
                    subprocess.run([docker,'volume','rm',volume],capture_output=True,timeout=10)

    def test_launch_script_and_embedded_python_are_executable_and_precredential_failure_is_bounded(self):
        script = self.workflow['jobs']['staging-build-candidate']['steps'][2]['with']['script']
        # Compile the actual action body and both finite Python programs. No
        # service or SDK fixture is involved in this workflow syntax check.
        node = self.node_runtime()
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
