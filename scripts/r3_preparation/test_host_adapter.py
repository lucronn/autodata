"""Scripted graph and owned Python-child binding verification only."""
import copy
import hashlib
import json
import os
import socket
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from unittest.mock import patch
from test_policy import load
from test_real_admission import fixture,encode,bundle

a=load('real_admission');p=load('policy');t=load('process_transport');h=load('host_adapter')


def actual_contract():
    d=fixture();now=time.monotonic_ns();d['issued_ns']=now-100;d['expires_ns']=now+1200*10**9
    raw=encode(d);approval=replace(bundle(raw),now_ns=now)
    return a.admit_actual(raw,approval)


class ScriptWorker:
    instances=[]
    def __init__(self,anchors,recipes,root,deadline,cancel,**kwargs):
        self.recipes={v.id:v for v in recipes};self.deadline=deadline;self.cancel=cancel
        self.files={'owner-contract.json':b'owned contract','dispatch.json':b'owned dispatch'}
        self.log=[];self.ipc_closed=False;self.quarantine_required=False
        self.__class__.instances.append(self)
    def observe(self,reference):
        self.log.append(('observe',reference));r=self.recipes[reference]
        if r.kind=='absence':return {'absent':True}
        if r.kind=='socket':return {'socket_metadata':True}
        return {'sha256':r.sha256,'size':r.identity.size,'complete':True}
    def space(self):self.log.append(('space',));return {'available_bytes':1024**3}
    def inventory_outputs(self,names):
        self.log.append(('inventory',tuple(names)))
        if set(names)!=set(self.files):raise h.f.TransportFault('integrity')
        return {'count':len(names)}
    def create_output(self,name,raw):
        self.log.append(('write',name));self.space()
        if name in self.files:raise h.f.TransportFault('integrity')
        self.files[name]=raw
        return dict(sha256=hashlib.sha256(raw).hexdigest(),size=len(raw),complete=True)
    def verify_output(self,name):
        self.log.append(('verify',name));raw=self.files[name]
        return dict(sha256=hashlib.sha256(raw).hexdigest(),size=len(raw),complete=True)
    def close(self):self.log.append(('close',));self.ipc_closed=True;return 'reaped'


def output(command,contract):
    d=a.values(contract);name=command.command_id
    if name=='python_version':return b'Python 3.12.1\n'
    if name=='git_version':return b'git version 2.45.1\n'
    if name=='docker_version':return b'Docker version 27.1.1\n'
    if name=='compose_version':return encode({'version':'v2.30.0'})
    if name=='context_show':return b'default\n'
    if name=='context_inspect':return encode(dict(Name='default',Endpoints=dict(docker=dict(Host=d['local_socket'],SkipTLSVerify=False))))
    if name=='daemon_version':return encode({'Server':dict(Os='linux',Arch='amd64',Version='27.1.1')})
    if name=='daemon_info':return encode(dict(OSType='linux',Architecture='x86_64',ID='private',HTTPProxy='',HTTPSProxy='',NoProxy=''))
    if name in p.COMMAND_IDS[8:11]:return ' '.join(d['required_flags'][name]).encode()
    if name in p.COMMAND_IDS[11:15]:
        im=p.IMAGES[p.COMMAND_IDS[11:15].index(name)]
        return encode([dict(Id=im,Os='linux',Architecture='amd64',Config=d['image_configs'][im],RootFS=d['image_rootfs'][im],RepoDigests=[])])
    if name=='git_files':return b'fixture tracked manifest'
    if name=='git_head':return (p.CANDIDATE+'\n').encode()
    if name=='git_tree':return (p.TREE+'\n').encode()
    if name=='compose_baseline':return encode(d['baseline'])
    if name=='compose_effective':return encode(a.effective_model(contract))
    return b''


class HostTests(unittest.TestCase):
    def setUp(self):
        ScriptWorker.instances=[];self.contract=actual_contract();self.assertIsInstance(self.contract,a.ActualContract)
        # Bind the scripted Git stream to the admitted literal digest.
        d=a.values(self.contract);d['tracked_manifest']=hashlib.sha256(b'fixture tracked manifest').hexdigest()
        raw=encode(d);self.contract=a.admit_actual(raw,replace(bundle(raw),now_ns=time.monotonic_ns()))
        self.readfd,self.writefd=os.pipe();self.addCleanup(os.close,self.readfd);self.addCleanup(os.close,self.writefd)
        self.calls=[]

    def runner(self,request,budget,cancel):
        self.calls.append((request,budget,cancel));raw=output(request,self.contract)
        return t.RunResult('completed',1 if request.command_id=='git_symbolic' else 0,raw,b'',len(raw),'reaped',100,None)

    def collect(self,**changes):
        return h._collect(self.contract,(),self.readfd,worker_type=changes.pop('worker_type',ScriptWorker),
                          runner=changes.pop('runner',self.runner),**changes)

    def test_full_graph_one_budget_and_truthful_pending_snapshots(self):
        result=self.collect();self.assertIsNotNone(result.receipt,result)
        self.assertEqual(tuple(x[0].command_id for x in self.calls),p.COMMAND_IDS)
        self.assertEqual(len({id(x[1]) for x in self.calls}),1)
        self.assertEqual(len({id(x[2]) for x in self.calls}),1)
        w=ScriptWorker.instances[-1]
        snapshot=json.loads(w.files['command-receipts.json'])
        self.assertEqual(snapshot['record_stage'],'pre_finalization_snapshot')
        self.assertEqual(snapshot['file_worker_cleanup'],'pending')
        self.assertEqual(snapshot['cleanup_status'],'pending');self.assertFalse(snapshot['worker_ipc_closed'])
        self.assertFalse(snapshot['monitor_stopped']);self.assertFalse(snapshot['final_receipt_issued'])
        classification=json.loads(w.files['classification.json'])
        self.assertEqual(classification['classification'],'preparation_finalization_pending')
        self.assertIn(b'provisional',w.files['REPORT.md'])
        self.assertEqual(result.cleanup.file_worker_cleanup,'reaped')
        self.assertTrue(result.cleanup.monitor_stopped);self.assertTrue(result.cleanup.final_receipt_issued)
        self.assertEqual(dict(result.receipt.artifact_binding),{name:hashlib.sha256(w.files[name]).hexdigest()
            for name in ('SHA256SUMS','command-receipts.json','classification.json')})
        self.assertNotIn('independent-review.md',w.files)
        self.assertFalse(result.host_observed);self.assertEqual(result.accepted_case_credit,0)
        self.assertTrue(all(value is False for key,value in result.authorities))
        writes=[entry for entry in w.log if entry[0]=='write'];self.assertEqual(writes[-1],('write','SHA256SUMS'))

    def test_cancellation_at_every_finalization_boundary_never_rewrites(self):
        for boundary in h.FINALIZATION_STATES[:-1]:
            with self.subTest(boundary=boundary):
                saved={}
                def fault(state,attempt):
                    if state==boundary:
                        saved.update(ScriptWorker.instances[-1].files);attempt.cancel.set()
                result=self.collect(checkpoint=fault)
                self.assertIsNone(result.receipt);self.assertFalse(result.cleanup.final_receipt_issued)
                self.assertEqual(ScriptWorker.instances[-1].files,saved)
                self.assertEqual(result.cleanup.primary_fault,'cancel')

    def test_worker_and_monitor_retirement_failures_withhold_receipt(self):
        class Unconfirmed(ScriptWorker):
            def close(self):super().close();self.quarantine_required=True;return 'unconfirmed'
        r=self.collect(worker_type=Unconfirmed)
        self.assertIsNone(r.receipt);self.assertTrue(r.cleanup.quarantine_required)
        monitors=[];retire=h._Monitor.retire
        with patch.object(h._Monitor,'retire',autospec=True,side_effect=lambda monitor:monitors.append(monitor) or False):
            r=self.collect();self.assertIsNone(r.receipt);self.assertTrue(r.cleanup.quarantine_required)
        for monitor in monitors:retire(monitor)

    def test_dependency_missing_skips_without_retry(self):
        class Missing(ScriptWorker):
            def observe(self,reference):
                if reference=='file_0':return {'blocked_missing_input':True}
                return super().observe(reference)
        # The full fixture deliberately places every file in every window.
        r=self.collect(worker_type=Missing)
        self.assertEqual(self.calls,[]);self.assertEqual(r.classification,'collection_blocked')

    def test_fault_prefix_cleanup_and_private_bytes_never_project(self):
        for status,cleanup,fault,rc in (('output_limit','reaped','output_limit',0),
                                       ('cleanup_unconfirmed','unconfirmed','deadline',0),
                                       ('completed','reaped',None,7)):
            def failed(req,budget,cancel):
                self.calls.append((req,budget,cancel))
                return t.RunResult(status,rc,b'PRIVATE_SENTINEL',b'\xffprivate',len(b'PRIVATE_SENTINEL')+len(b'\xffprivate'),cleanup,100,fault)
            r=self.collect(runner=failed);self.assertIsNone(r.receipt)
            self.assertNotIn('PRIVATE_SENTINEL',repr(r));self.assertEqual(len(r.commands),1)
            self.assertEqual(r.commands[0].complete,status=='completed' and cleanup=='reaped')
            if cleanup=='unconfirmed':self.assertTrue(r.cleanup.quarantine_required)

    def test_owner_channel_eof_cancels_before_commands(self):
        os.dup2(self.readfd,self.writefd)  # Replace the sole writer with an owned read end.
        r=self.collect();self.assertIsNone(r.receipt);self.assertEqual(self.calls,[])

    def test_public_api_readmits_before_worker_or_commands(self):
        with patch.object(h.f,'FileWorker',side_effect=AssertionError('unexpected worker')):
            r=h.collect_preparation(replace(self.contract,commands=()),(),self.readfd)
            self.assertEqual(r.classification,'collection_blocked')

    def test_owned_python_child_binding_keeps_opaque_stderr_and_expected_exit(self):
        with tempfile.TemporaryDirectory() as root:
            def child(req,budget,cancel):
                # Private test substitution. Production graph never admits -c.
                raw=output(req,self.contract)
                code='import os;os.write(1,'+repr(raw)+');os.write(2,b"\\xffprivate");raise SystemExit('+str(1 if req.command_id=='git_symbolic' else 0)+')'
                return t.run(t.RunRequest(req.command_id,sys.executable,(sys.executable,'-I','-B','-c',code),root,(),req.kind),budget,cancel)
            result=self.collect(runner=child);self.assertIsNotNone(result.receipt,result)
            self.assertNotIn('private',repr(result))

    def test_owned_child_exact_command_cap_and_prefix_cap(self):
        with tempfile.TemporaryDirectory() as root:
            for size,complete in ((16*1024**2,True),(16*1024**2+1,False)):
                def child(req,budget,cancel):
                    code='import os;data=b"x"*65536;size='+str(size)+'\nwhile size:\n n=os.write(1,data[:size]);size-=n'
                    return t.run(t.RunRequest(req.command_id,sys.executable,(sys.executable,'-I','-B','-c',code),root,(),req.kind),budget,cancel)
                result=self.collect(runner=child)
                self.assertIsNone(result.receipt);self.assertEqual(result.commands[0].complete,complete)
                self.assertEqual(result.commands[0].retained_bytes,16*1024**2)
                if not complete:self.assertEqual(result.cleanup.primary_fault,'cap')

    def test_shared_primitive_budget_exhaustion_stops_later_commands(self):
        budgets=[]
        with tempfile.TemporaryDirectory() as root:
            def child(req,budget,cancel):
                budgets.append(budget);raw=output(req,self.contract)
                code='import os;out='+repr(raw)+';os.write(1,out);size=16*1024**2-len(out);data=b"x"*65536\nwhile size:\n n=os.write(2,data[:size]);size-=n'
                return t.run(t.RunRequest(req.command_id,sys.executable,(sys.executable,'-I','-B','-c',code),root,(),req.kind),budget,cancel)
            result=self.collect(runner=child)
        self.assertIsNone(result.receipt);self.assertEqual(len(budgets),9)
        self.assertEqual(len({id(b) for b in budgets}),1);self.assertEqual(budgets[0].remaining_bytes,0)
        self.assertEqual(result.cleanup.primary_fault,'cap')

    def test_actual_file_worker_finalizes_owned_temp_artifacts(self):
        from test_file_transport import identity
        with tempfile.TemporaryDirectory() as base:
            base=Path(base);base.chmod(0o700);root=base/'prep';clone=base/'clone'
            for directory in (root,root/'home',root/'artifacts',root/'minio',root/'home'/'.config',
                              root/'home'/'.config'/'git',clone,clone/'.git',base/'tools',base/'etc'):
                directory.mkdir(mode=0o700)
            d=a.values(self.contract);d['prep_root']=str(root);d['checkout']=str(clone)
            d['tools']={key:str(base/'tools'/key) for key in d['tools']}
            d['local_socket']='unix://'+str(base/'docker.sock')
            d['env'].update(HOME=str(root/'home'),AUTODATA_LIFECYCLE_ARTIFACT_DIR=str(root/'artifacts'))
            d['git_provenance']['absent_paths']=[str(base/'etc'/'gitconfig'),str(root/'home'/'.gitconfig'),
                str(root/'home'/'.config'/'git'/'config'),str(clone/'.git'/'config.worktree')]
            sources=dict(system=[str(base/'etc'/'gitconfig')],global_paths=[str(root/'home'/'.gitconfig')],
                xdg=[str(root/'home'/'.config'/'git'/'config')],local=[str(clone/'.git'/'config')],
                worktree=[str(clone/'.git'/'config.worktree')])
            d['git_provenance']['installation_sources']=sources
            d['git_provenance']['installation_manifest']=hashlib.sha256(encode(sources)).hexdigest()
            for path in d['tools'].values():Path(path).write_bytes(b'owned tool');Path(path).chmod(0o600)
            (clone/'.git'/'config').write_text(p.CONFIG);(clone/'.git'/'config').chmod(0o600)
            (root/'owner-contract.json').write_bytes(b'owned contract');(root/'owner-contract.json').chmod(0o600)
            (root/'dispatch.json').write_bytes(b'owned dispatch');(root/'dispatch.json').chmod(0o600)
            owned_socket=socket.socket(socket.AF_UNIX);owned_socket.bind(str(base/'docker.sock'))
            self.addCleanup(owned_socket.close);(base/'docker.sock').chmod(0o600)
            def mapping(target):return {name:getattr(identity(target),name) for name in a.FileIdentity.__dataclass_fields__}
            locations={'filesystem':base,'root':root,**{n:root/n for n in ('home','artifacts','minio')}}
            d['anchors']=[dict(reference=n,path=str(path),identity=mapping(path)) for n,path in locations.items()]
            paths=[(Path(v),'regular') for v in d['tools'].values()]
            paths += [(Path(v),'absence') for v in d['git_provenance']['absent_paths']]
            paths += [(base/'docker.sock','socket'),(clone/'.git'/'config','regular'),
                      (root/'owner-contract.json','regular'),(root/'dispatch.json','regular')]
            d['files']=[]
            for i,(path,kind) in enumerate(paths):
                components=path.relative_to(base).parts;parent=base;parents=[]
                for name in components:parents.append(mapping(parent));parent=parent/name
                literal=p.CONFIG if path==clone/'.git'/'config' else None
                d['files'].append(dict(id='file_'+str(i),anchor='filesystem',components=list(components),kind=kind,
                    identity=None if kind=='absence' else mapping(path),parents=parents,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest() if kind=='regular' else None,literal=literal))
            d['prerequisites']={n:[r['id'] for r in d['files']] for n in a.WINDOWS}
            d['commands']=[dict(id=c.id,argv=list(c.argv),cwd=c.cwd,env=dict(c.env),kind=c.kind,prerequisites=list(c.prerequisites)) for c in a.command_graph(d)]
            raw=encode(d);self.contract=a.admit_actual(raw,replace(bundle(raw),now_ns=time.monotonic_ns()))
            self.assertIsInstance(self.contract,a.ActualContract)
            descriptors={n:os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC) for n,path in locations.items()}
            try:
                anchors=tuple(a.Anchor(n,fd,identity(fd)) for n,fd in descriptors.items())
                result=h._collect(self.contract,anchors,self.readfd,worker_type=h.f.FileWorker,
                                  runner=self.runner,validate_handoff=True)
                self.assertIsNotNone(result.receipt,result)
                sums=(root/'SHA256SUMS').read_bytes();binding=dict(result.receipt.artifact_binding)
                self.assertEqual(hashlib.sha256(sums).hexdigest(),binding['SHA256SUMS'])
                for line in sums.decode().splitlines():
                    digest,name=line.split('  ');self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest)
                self.assertEqual(json.loads((root/'command-receipts.json').read_bytes())['file_worker_cleanup'],'pending')
                self.assertEqual(result.cleanup.file_worker_cleanup,'reaped')
            finally:
                for fd in descriptors.values():os.close(fd)

    def test_startup_stall_is_not_interrupted_by_setting_event(self):
        entered=threading.Event();release=threading.Event();still_blocked=[]
        def stalled(req,budget,cancel):
            entered.set();cancel.set()
            def owner_watchdog():
                still_blocked.append(not release.is_set());release.set()
            owner=threading.Timer(.05,owner_watchdog);owner.start()
            release.wait(1);owner.join()
            return t.RunResult('cancelled',None,b'',b'',0,'reaped',100,'cancel')
        result=self.collect(runner=stalled)
        self.assertEqual(still_blocked,[True]);self.assertIsNone(result.receipt)
