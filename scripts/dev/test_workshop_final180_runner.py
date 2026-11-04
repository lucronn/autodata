"""Offline Stage A contract and adversarial admission tests (no fixture execution)."""
import copy
import dataclasses
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).with_name('workshop_final180_runner.py')
spec = importlib.util.spec_from_file_location('final180_under_test', MODULE)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)
BASE = 'b8ffaa39e6b9104df67f69541ce4da8a936adc0f'
CANDIDATE = '4d82e413e04fb2401ac7bc28dc828375ac662180'
ROOT = Path(__file__).resolve().parents[2]


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


class FakeGit:
    def __init__(self):
        self.blobs = {}
        for path in (r.RECORD_PATH, r.TASK_PATH, r.INVENTORY_PATH, r.PLAN_PATH):
            self.blobs[(BASE, path)] = (ROOT / path).read_bytes()
        for path in json.loads(self.blobs[(BASE, r.RECORD_PATH)])['repository_doc_refs']:
            self.blobs[(BASE, path)] = (ROOT / path).read_bytes()
        self.inventory = json.loads(self.blobs[(BASE, r.INVENTORY_PATH)])
        self.data = {p['path']: b'file:' + p['path'].encode() for p in self.inventory['source_hashes']}
        self.data['not-one-of-the-82.txt'] = b'independent whole tree coverage'
        self.inventory['source_hashes'] = [dict(path=p, bytes=len(b), sha256=hashlib.sha256(b).hexdigest()) for p,b in self.data.items() if p != 'not-one-of-the-82.txt']
        self.refresh()
        self.observation = dict(head=CANDIDATE, dirty=(), untracked=(), ignored=(), remotes=(), hooks=(), alternates=(), submodules=())
        self.identity = r.GitToolIdentity('/usr/bin/git', 'a'*64, 'git version test')

    def refresh(self):
        self.blobs[(BASE, r.INVENTORY_PATH)] = canonical(self.inventory)
        for p,b in self.data.items(): self.blobs[(CANDIDATE,p)] = b

    def read_blob(self, sha, path): return self.blobs[(sha,path)]
    def tracked_entries(self, sha):
        assert sha == CANDIDATE
        return tuple((p, '100644', hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()) for p,b in sorted(self.data.items()))
    def observe_checkout(self, root): return copy.deepcopy(self.observation)
    def tool_identity(self): return self.identity
    def runner_sha(self): return BASE
    def close(self): pass


class FixtureBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'candidate'
        self.root.mkdir()
        self.output = Path(self.tmp.name) / 'output'
        self.git = FakeGit()
        for path,data in self.git.data.items():
            p=self.root/path; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data)
        self.contract = r.load_contract(BASE,self.git)

    def error(self, code, fn, *args):
        with self.assertRaises(r.ContractError) as ctx: fn(*args)
        self.assertEqual(str(ctx.exception),code)


class AdmissionTests(FixtureBase):
    def test_exact_inventory_and_complete_manifest(self):
        self.assertEqual([len(ids) for _,ids in self.contract.expected_ids],[5,8,14,12,120,21])
        self.assertEqual(len(self.contract.source_pins),82)
        out=r.inspect_candidate(self.contract,self.root,self.git)
        self.assertEqual(len(out.source_manifest),83)
        self.assertEqual(out.source_manifest_sha256,hashlib.sha256(canonical(r.manifest_document(out))).hexdigest())
        with self.assertRaises(dataclasses.FrozenInstanceError): self.contract.candidate_sha='bad'

    def test_checkpoint_requires_full_sha(self): self.error('checkpoint_sha',r.load_contract,'main',self.git)

    def test_checkpoint_task_record_mismatch(self):
        task=json.loads(self.git.blobs[(BASE,r.TASK_PATH)]);task['pre_implementation']['goal']='other'
        self.git.blobs[(BASE,r.TASK_PATH)]=canonical(task)
        self.error('checkpoint_contract',r.load_contract,BASE,self.git)

    def test_inventory_rejects_candidate_authority_and_count_mutation(self):
        original=copy.deepcopy(self.git.inventory)
        for mutate in (lambda i:i.update(selected_candidate_sha='a'*40),lambda i:i['authority'].update(merge_authorized=True),lambda i:i['expected_case_ids']['identity'].pop(),lambda i:i.update(profiles_enabled=True),lambda i:i['source_hashes'][0].update(bytes=True)):
            with self.subTest(mutate=mutate):
                self.git.inventory=copy.deepcopy(original);mutate(self.git.inventory);self.git.refresh()
                with self.assertRaises(r.ContractError):r.load_contract(BASE,self.git)

    def test_every_source_pin_independently_checked(self):
        for pin in self.contract.source_pins:
            with self.subTest(path=pin.path):
                contract=dataclasses.replace(self.contract,source_pins=(dataclasses.replace(pin,sha256='0'*64),))
                self.error('source_pin_mismatch',r.inspect_candidate,contract,self.root,self.git)

    def test_all_checkout_denials(self):
        for key in ('head','dirty','untracked','ignored','remotes','alternates','submodules'):
            with self.subTest(key=key):
                old=self.git.observation[key]; self.git.observation[key]='a'*40 if key=='head' else ('bad',)
                with self.assertRaises(r.ContractError):r.inspect_candidate(self.contract,self.root,self.git)
                self.git.observation[key]=old

    def test_sample_hooks_admitted_custom_hooks_rejected(self):
        self.git.observation['hooks']=(r.HookEntry('.git/hooks/pre-commit.sample','0755','b'*64,False),)
        r.inspect_candidate(self.contract,self.root,self.git)
        self.git.observation['hooks']=(r.HookEntry('.git/hooks/custom','0644','b'*64,False),)
        self.error('custom_hook',r.inspect_candidate,self.contract,self.root,self.git)

    def test_full_tree_content_and_mode_not_only_pins(self):
        p=self.root/'not-one-of-the-82.txt';p.write_bytes(b'changed')
        self.error('source_mismatch',r.inspect_candidate,self.contract,self.root,self.git)
        p.write_bytes(self.git.data[p.name]);p.chmod(0o755)
        self.error('source_mode',r.inspect_candidate,self.contract,self.root,self.git)

    def test_missing_extra_symlink_hardlink_fifo_and_parent_symlink(self):
        p=self.root/'not-one-of-the-82.txt';data=p.read_bytes()
        p.unlink();self.error('unsafe_input',r.inspect_candidate,self.contract,self.root,self.git)
        p.symlink_to('/etc/passwd');self.error('unsafe_input',r.inspect_candidate,self.contract,self.root,self.git)
        p.unlink();other=self.root/'other';other.write_bytes(data);os.link(other,p)
        self.error('unsafe_input',r.inspect_candidate,self.contract,self.root,self.git)
        p.unlink();other.unlink();os.mkfifo(p)
        self.error('unsafe_input',r.inspect_candidate,self.contract,self.root,self.git)

    def test_object_paths_and_modes_fail_closed(self):
        original=self.git.tracked_entries
        for entry in (('../escape','100644','a'*40),('bad','120000','a'*40),('bad','160000','a'*40)):
            with self.subTest(entry=entry):
                self.git.tracked_entries=lambda sha:(entry,)
                with self.assertRaises(r.ContractError):r.inspect_candidate(self.contract,self.root,self.git)
        self.git.tracked_entries=original

    def test_source_drift_during_read(self):
        original=r._hash_regular
        def drift(*args,**kw):
            result=original(*args,**kw)
            if args[1]=='not-one-of-the-82.txt':(self.root/args[1]).write_bytes(b'changed after read')
            return result
        with mock.patch.object(r,'_hash_regular',side_effect=drift):
            self.error('source_drift',r.inspect_candidate,self.contract,self.root,self.git)


class JSONTests(unittest.TestCase):
    def test_strict_json_bad_documents(self):
        bad=[b'{}\xff',b'\xef\xbb\xbf{}',b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'[]',b'{"x":'+b'['*34+b'0'+b']'*34+b'}',canonical({'x':'a'*65537}),b'{"x":"\\ud800"}',canonical({'x':[0]*65537})]
        for raw in bad:
            with self.subTest(raw=raw[:30]),self.assertRaises(r.ContractError):r.load_json_strict(raw,max_bytes=4*1024*1024)
        with self.assertRaises(r.ContractError):r.load_json_strict(b'{}',max_bytes=1)
        self.assertEqual(r.load_json_strict(b'{"x":true}',max_bytes=20),{'x':True})


class ObservationTests(FixtureBase):
    def document(self):
        return dict(contract='workshop-final180-observations-v1',candidate_sha=CANDIDATE,observations=[dict(family=f,logical_id=i,status='passed',raw_refs=[]) for f,ids in self.contract.expected_ids for i in ids])

    def test_exact180_claims_and_raw_refs_are_never_opened(self):
        doc=self.document();doc['observations'][0]['raw_refs']=['does-not-exist/private.json']
        observed=r.load_observations(canonical(doc),self.contract)
        with mock.patch('builtins.open',side_effect=AssertionError('raw ref opened')):
            self.assertEqual(r.reconcile(observed,self.contract),())

    def test_multiset_same_count_adversaries_every_family(self):
        for family,ids in self.contract.expected_ids:
            for status in ('failed','skipped','unavailable','duplicate','extra'):
                doc=self.document();row=next(x for x in doc['observations'] if x['family']==family)
                missing=row['logical_id']
                if status=='duplicate':row['logical_id']=ids[1]
                elif status=='extra':row['logical_id']='unknown'
                else:row['status']=status
                failures=r.reconcile(r.load_observations(canonical(doc),self.contract),self.contract)
                self.assertTrue(failures,(family,status))
                if status in ('duplicate','extra'):self.assertIn(f'missing:{family}:{missing}',failures)

    def test_observation_exact_schema_and_bounds(self):
        for mutation in (lambda d:d.update(count=180),lambda d:d.update(candidate_sha='a'*40),lambda d:d['observations'][0].update(family='support'),lambda d:d['observations'][0].update(logical_id=''),lambda d:d['observations'][0].update(logical_id='x'*257),lambda d:d['observations'][0].update(status=True),lambda d:d['observations'][0].update(raw_refs=['../x']),lambda d:d['observations'][0].update(raw_refs=['x','x']),lambda d:d['observations'][0].update(authority=False),lambda d:d['observations'][0].pop('raw_refs'),lambda d:d.update(observations=None)):
            doc=self.document();mutation(doc)
            with self.subTest(mutation=mutation),self.assertRaises(r.ContractError):r.load_observations(canonical(doc),self.contract)

    def test_513_and_3500_rows_rejected_without_prefix(self):
        for count in (513,3500):
            doc=self.document();doc['observations']=[doc['observations'][0]]*count
            self.error('observation_count_exceeded',r.load_observations,canonical(doc),self.contract)

    def test_worst_case_512_complete_failures_fit(self):
        doc=self.document();doc['observations']=[dict(family='identity',logical_id='\x01'*256,status='failed',raw_refs=[]) for _ in range(512)]
        rows=r.load_observations(canonical(doc),self.contract);fail=r.reconcile(rows,self.contract)
        self.assertEqual(sum(x.startswith('extra:') for x in fail),512)
        self.assertEqual(sum(x.startswith('duplicate:') for x in fail),1)
        self.assertEqual(sum(x.startswith('nonpass:') for x in fail),512)
        self.assertLess(len(canonical({'failures':fail})),4*1024*1024)

    def test_dto_cannot_replace_api_and_failure_order(self):
        doc=self.document();api=next(x for x in doc['observations'] if x['family']=='browser_api');api['logical_id']=self.contract.expected_ids[4][1][0]
        rows=r.load_observations(canonical(doc),self.contract)
        failures=r.reconcile(rows,self.contract)
        self.assertTrue(failures[0].startswith('missing:browser_api:'))
        self.assertTrue(failures[1].startswith('extra:browser_api:'))


class CLIFixture(FixtureBase):
    def invoke(self,mode='inspect',observations=None,output=None):
        args=[mode,'--checkpoint-sha',BASE,'--candidate-root',str(self.root),'--output-root',str(output or self.output)]
        if observations is not None:args+=['--observations',str(observations)]
        with mock.patch.object(r,'ProductionGitReader',return_value=self.git):return r.main(args)


class CLITests(CLIFixture):
    def test_private_atomic_diagnostic_all_authority_false(self):
        self.assertEqual(self.invoke(),0)
        out=self.output;d=json.loads((out/'diagnostic.json').read_bytes())
        self.assertEqual(d['status'],'consistent');self.assertFalse(any(d['authority'].values()));self.assertEqual(d['git_tool']['sha256'],'a'*64)
        self.assertEqual(stat.S_IMODE(out.stat().st_mode),0o700)
        for p in out.iterdir():self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
        self.assertEqual(d['source_manifest_sha256'],hashlib.sha256((out/'source-manifest.json').read_bytes()).hexdigest())

    def test_run_unknown_option_exit2_before_output(self):
        for args in (['run'],['inspect','--preflight-receipt','anything']):
            with self.assertRaises(SystemExit) as ctx:r.main(args)
            self.assertEqual(ctx.exception.code,2)
        self.assertFalse((self.output).exists())

    def test_output_existing_symlink_and_writable_parent_rejected(self):
        out=self.output;out.mkdir();self.assertEqual(self.invoke(),2)
        out.rmdir();out.symlink_to(self.root,target_is_directory=True);self.assertEqual(self.invoke(),2)
        out.unlink();self.output.parent.chmod(0o777);self.assertEqual(self.invoke(),2)

    def test_oversized_observations_diagnostic_only_error(self):
        doc=ObservationTests.document(self);doc['observations']=[doc['observations'][0]]*513
        obs=self.root.parent/'claims.json';obs.write_bytes(canonical(doc))
        self.assertEqual(self.invoke('reconcile',obs),2)
        d=json.loads((self.output/'diagnostic.json').read_bytes());self.assertEqual(d['failures'],['observation_count_exceeded']);self.assertEqual(d['status'],'unavailable')

    def test_interruption_retains_failed_diagnostic(self):
        with mock.patch.object(r,'inspect_candidate',side_effect=KeyboardInterrupt):self.assertEqual(self.invoke(),1)
        self.assertEqual(json.loads((self.output/'diagnostic.json').read_bytes())['status'],'interrupted')

    def test_diagnostic_invariant_fallback(self):
        with mock.patch.object(r,'MAX_DIAGNOSTIC',1):self.assertEqual(self.invoke(),2)
        d=json.loads((self.output/'diagnostic.json').read_bytes());self.assertEqual(d['failures'],['diagnostic_size_invariant']);self.assertEqual(d['status'],'unavailable')




class ProductionGitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        # Production command construction is tested using a real immutable host
        # executable and intercepted read-only command output, never fixture tools.
        self.git=r.ProductionGitReader(ROOT);self.addCleanup(self.git.close)

    def test_fixed_path_discovery_version_and_exact_isolated_argv(self):
        identity=self.git.tool_identity()
        self.assertTrue(Path(identity.path).is_absolute());self.assertEqual(len(identity.sha256),64)
        with mock.patch.object(self.git,'_capture',return_value=b'blob') as capture:
            self.assertEqual(self.git.read_blob(CANDIDATE,'safe/file'),b'blob')
        argv=capture.call_args.args[0]
        self.assertEqual(argv,(identity.path,'--no-optional-locks','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','protocol.file.allow=never','-C',str(ROOT),'cat-file','blob',CANDIDATE+':safe/file'))
        self.assertEqual(set(self.git.env),{'PATH','HOME','GIT_CONFIG_NOSYSTEM','GIT_CONFIG_GLOBAL','GIT_TERMINAL_PROMPT','GIT_NO_REPLACE_OBJECTS'})
        self.assertEqual(self.git.env['PATH'],r.FIXED_PATH)
        self.assertEqual(list(Path(self.git.env['HOME']).iterdir()),[])
        with mock.patch.object(r.shutil,'which',return_value=None) as which:
            with self.assertRaises(r.ContractError):r.ProductionGitReader(ROOT)
        which.assert_called_once_with('git',path='/usr/local/bin:/usr/bin:/bin')

    def test_version_argv_is_only_special_command(self):
        with mock.patch.object(r.ProductionGitReader,'_capture',return_value=b'git version unit\n') as cap:
            git=r.ProductionGitReader(ROOT)
            try:self.assertEqual(git.tool_identity().version,'git version unit')
            finally:git.close()
        self.assertEqual(cap.call_args.args[0],(str(Path(self.git.identity.path)),'--version'))
        for version in (b'',b'x\ny\n',b'x\r\n',b'x'*257,b'\xff'):
            with self.subTest(version=version),mock.patch.object(r.ProductionGitReader,'_capture',return_value=version),self.assertRaises(r.ContractError):
                r.ProductionGitReader(ROOT)

    def test_git_executable_changed_or_symlinked_after_discovery(self):
        executable=self.root/'git';executable.write_bytes(Path(self.git.identity.path).read_bytes());executable.chmod(0o755)
        with mock.patch.object(r.shutil,'which',return_value=str(executable)),mock.patch.object(r.ProductionGitReader,'_capture',return_value=b'git version unit\n'):
            git=r.ProductionGitReader(ROOT)
        self.addCleanup(git.close)
        executable.write_bytes(b'drift');self.assertRaises(r.ContractError,git.tool_identity)
        executable.unlink();executable.symlink_to(self.git.identity.path)
        self.assertRaises(r.ContractError,git.tool_identity)

    def metadata(self):
        gitdir=self.root/'.git';gitdir.mkdir();(gitdir/'config').write_text('[core]\n repositoryformatversion = 0\n')
        (gitdir/'hooks').mkdir();(gitdir/'objects/info').mkdir(parents=True)
        return gitdir

    def checkout_git(self,root,command,**kw):
        if command==('rev-parse','--verify','HEAD'):return CANDIDATE.encode()+b'\n'
        return b''

    def test_actual_hooks_sample_modes_and_nonsample_entries(self):
        gitdir=self.metadata();hook=gitdir/'hooks/pre-commit.sample';hook.write_bytes(b'sample')
        with mock.patch.object(self.git,'_git',side_effect=self.checkout_git):
            for mode in (0o644,0o755):
                hook.chmod(mode);out=self.git.observe_checkout(self.root);self.assertFalse(out['hooks'][0].active)
                self.assertEqual(out['hooks'][0].mode,f'{mode:04o}')
            for name,mode in (('custom',0o644),('pre-commit',0o644),('pre-commit',0o755)):
                p=gitdir/'hooks'/name;p.write_bytes(b'custom');p.chmod(mode)
                with self.assertRaises(r.ContractError) as ctx:self.git.observe_checkout(self.root)
                self.assertEqual(str(ctx.exception),'custom_hook');p.unlink()

    def test_unsafe_hook_entries_and_config(self):
        gitdir=self.metadata();hook=gitdir/'hooks/bad.sample'
        with mock.patch.object(self.git,'_git',side_effect=self.checkout_git):
            hook.symlink_to('/etc/passwd');self.assertRaises(r.ContractError,self.git.observe_checkout,self.root);hook.unlink()
            hook.mkdir();self.assertRaises(r.ContractError,self.git.observe_checkout,self.root);hook.rmdir()
            os.mkfifo(hook);self.assertRaises(r.ContractError,self.git.observe_checkout,self.root);hook.unlink()
            other=self.root/'other';other.write_bytes(b'x');os.link(other,hook);self.assertRaises(r.ContractError,self.git.observe_checkout,self.root);hook.unlink()
            for config in ('[core]\n hooksPath=/tmp/hooks\n','[include]\n path=/tmp/config\n','[extensions]\n partialClone=origin\n','[remote "origin"]\n promisor=true\n'):
                (gitdir/'config').write_text(config)
                with self.subTest(config=config),self.assertRaises(r.ContractError):self.git.observe_checkout(self.root)

    def test_alternates_detached_and_remote_constraints(self):
        gitdir=self.metadata();p=gitdir/'objects/info/alternates';p.write_bytes(b'')
        with mock.patch.object(self.git,'_git',side_effect=self.checkout_git):self.assertRaises(r.ContractError,self.git.observe_checkout,self.root)
        p.unlink()
        def attached(root,command,**kw):
            return b'refs/heads/main\n' if command[0]=='symbolic-ref' else self.checkout_git(root,command,**kw)
        with mock.patch.object(self.git,'_git',side_effect=attached):self.assertRaises(r.ContractError,self.git.observe_checkout,self.root)

    def test_git_subprocess_limits_without_running_candidate_code(self):
        class Process:
            def __init__(self,*args,**kw):
                self.stdout=tempfile.TemporaryFile();self.stderr=tempfile.TemporaryFile()
                self.stdout.write(b'x'*20);self.stdout.seek(0);self.code=None
            def poll(self):return self.code
            def wait(self,**kw):self.code=0;return 0
            def kill(self):self.code=-9
        # Regular files cannot be registered by epoll, so use a selector stub.
        class Selector:
            def __init__(self):self.entries={}
            def register(self,f,event,data):self.entries[f]=type('Key',(),{'fileobj':f,'data':data})()
            def get_map(self):return self.entries
            def select(self,timeout):return [(k,1) for k in self.entries.values()]
            def unregister(self,f):del self.entries[f]
            def close(self):pass
        with mock.patch.object(r.subprocess,'Popen',side_effect=Process) as popen,mock.patch.object(r.selectors,'DefaultSelector',Selector),mock.patch.object(r,'MAX_MANIFEST',10):
            with self.assertRaises(r.ContractError) as ctx:self.git._capture((self.git.identity.path,'cat-file','blob',CANDIDATE+':safe'))
            self.assertEqual(str(ctx.exception),'git_output_size')
        self.assertFalse(popen.call_args.kwargs['shell']);self.assertEqual(popen.call_args.kwargs['env'],self.git.env)


class AdditionalBoundaryTests(FixtureBase):
    def test_extra_file_and_parent_symlink(self):
        extra=self.root/'extra';extra.write_bytes(b'extra')
        self.error('source_members',r.inspect_candidate,self.contract,self.root,self.git);extra.unlink()
        real=self.root/'real';real.mkdir();(real/'file').write_bytes(b'outside')
        link=self.root/'link';link.symlink_to(real,target_is_directory=True)
        self.error('unsafe_input',r._read_regular,self.root,'link/file')

    def test_source_limit_and_timeout(self):
        with mock.patch.object(r.time,'monotonic',side_effect=[0,301]):
            self.error('inspection_timeout',r.inspect_candidate,self.contract,self.root,self.git)

    def test_api_families_missing_in_expected_order(self):
        result=r.reconcile((),self.contract)
        self.assertEqual(len(result),180)
        self.assertEqual(result[0],'missing:identity:'+self.contract.expected_ids[0][1][0])
        self.assertEqual(result[-1],'missing:browser_api:'+self.contract.expected_ids[-1][1][-1])


class WriteAndClaimBoundaryTests(CLIFixture):
    def test_interrupt_during_atomic_output_writes_failed_diagnostic(self):
        original=r._PrivateOutput.write
        interrupted=False
        def write(output,name,raw,limit):
            nonlocal interrupted
            if not interrupted:
                interrupted=True
                raise KeyboardInterrupt
            return original(output,name,raw,limit)
        with mock.patch.object(r._PrivateOutput,'write',new=write):self.assertEqual(self.invoke(),1)
        d=json.loads((self.output/'diagnostic.json').read_bytes())
        self.assertEqual(d['status'],'interrupted');self.assertEqual(d['failures'],['interrupted'])

    def test_output_error_retains_unavailable_diagnostic(self):
        original=r._PrivateOutput.write
        def write(output,name,raw,limit):
            if name=='source-manifest.json':raise OSError('private path must never be printed')
            return original(output,name,raw,limit)
        with mock.patch.object(r._PrivateOutput,'write',new=write):self.assertEqual(self.invoke(),2)
        self.assertEqual(json.loads((self.output/'diagnostic.json').read_bytes())['failures'],['output_failed'])

    def test_output_inside_candidate_rejected_before_any_write(self):
        self.assertEqual(self.invoke(output=self.root/'output'),2)
        self.assertFalse((self.root/'output').exists())

    def test_input_drift_in_reconciliation_is_unavailable(self):
        obs=self.root.parent/'claims.json';obs.write_bytes(canonical(ObservationTests.document(self)))
        original=r.reconcile
        def drift(*args):
            result=original(*args);obs.write_bytes(b'changed');return result
        with mock.patch.object(r,'reconcile',side_effect=drift):self.assertEqual(self.invoke('reconcile',obs),2)
        self.assertEqual(json.loads((self.output/'diagnostic.json').read_bytes())['failures'],['input_drift'])

    def test_all_passed_claim_cli_still_has_no_authority(self):
        doc=ObservationTests.document(self);doc['observations'][0]['raw_refs']=['never-opened.json']
        obs=self.root.parent/'claims.json';obs.write_bytes(canonical(doc))
        self.assertEqual(self.invoke('reconcile',obs),0)
        d=json.loads((self.output/'diagnostic.json').read_bytes());self.assertEqual(sum(d['observed_counts'].values()),180)
        self.assertEqual(d['observations_sha256'],hashlib.sha256(obs.read_bytes()).hexdigest())
        self.assertFalse(any(d['authority'].values()));self.assertEqual(d['status'],'consistent')

    def test_complete_worst_case_claim_diagnostic_below_4mib(self):
        doc=ObservationTests.document(self);doc['observations']=[dict(family='identity',logical_id='\x01'*256,status='failed',raw_refs=[]) for _ in range(512)]
        obs=self.root.parent/'claims.json';obs.write_bytes(canonical(doc))
        self.assertEqual(self.invoke('reconcile',obs),1)
        raw=(self.output/'diagnostic.json').read_bytes();d=json.loads(raw)
        self.assertLess(len(raw),4*1024*1024);self.assertEqual(len(d['failures']),1205)
        self.assertEqual(d['observed_counts']['identity'],512)

    def test_missing_tool_never_produces_consistent_diagnostic(self):
        with mock.patch.object(r,'ProductionGitReader',side_effect=r.ContractError('git_tool_discovery')):
            args=['inspect','--checkpoint-sha',BASE,'--candidate-root',str(self.root),'--output-root',str(self.output)]
            self.assertEqual(r.main(args),2)
        d=json.loads((self.output/'diagnostic.json').read_bytes());self.assertIsNone(d['git_tool']);self.assertEqual(d['status'],'unavailable')

    def test_option_abbreviations_are_unknown_before_output(self):
        args=['inspect','--check',BASE,'--candidate-root',str(self.root),'--output-root',str(self.output)]
        with self.assertRaises(SystemExit) as ctx:r.main(args)
        self.assertEqual(ctx.exception.code,2);self.assertFalse(self.output.exists())

    def test_task_authority_and_scope_cannot_drift(self):
        for mutate in (lambda t:t['authority'].update(runtime_execution_authorized=True),lambda t:t['allowed_paths'].append('application.py')):
            task=json.loads(self.git.blobs[(BASE,r.TASK_PATH)]);mutate(task);self.git.blobs[(BASE,r.TASK_PATH)]=canonical(task)
            self.error('checkpoint_contract',r.load_contract,BASE,self.git)

    def test_exact_diagnostic_shape_and_safe_unknown_options(self):
        args=['inspect','--checkpoint-sha',BASE,'--candidate-root',str(self.root),'--output-root',str(self.output),'--runtime-lock','x']
        with self.assertRaises(SystemExit) as ctx:r.main(args)
        self.assertEqual(ctx.exception.code,2);self.assertFalse(self.output.exists())
        self.assertEqual(self.invoke(),0)
        self.assertEqual(set(json.loads((self.output/'diagnostic.json').read_bytes())),{'contract','mode','checkpoint_sha','runner_sha','candidate_sha','inventory_sha256','source_manifest_sha256','observations_sha256','git_tool','status','observed_counts','failures','authority'})


if __name__=='__main__':unittest.main()
