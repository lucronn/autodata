"""In-memory ports exercise the collector; no host compatibility observations."""
import copy
from dataclasses import asdict, replace
import hashlib
import json
import unittest
from test_policy import load, fixture, contract, SENTINEL, CONFIG
p=load('policy')
c=load('collector')
E=c.Event

class Clock:
    def __init__(self):self.tick=0
    def now(self):return self.tick

class Cancel:
    def __init__(self):self.value=False
    def cancelled(self):return self.value

IDENT=p.Identity(1,2,'regular',1000,1000,0o600,0,1,1,'parent')
PARENT=replace(IDENT,type='directory',mode=0o700,inode=1)
ROOT=replace(PARENT,inode=3,parent='anchor')

def file_record(i,purpose='source',body=b'{}',path=None,identity=None):
    return {'id':'file_'+str(i),'path':path or '/synthetic/clone/input'+str(i),
            'purpose':purpose,'identity':asdict(identity or replace(IDENT,inode=10+i,size=len(body))),
            'sha256':hashlib.sha256(body).hexdigest(),'parents':[asdict(PARENT)]}

def doc(commands=(),extra_files=()):
    d=fixture();d['commands']=list(commands)
    d['approved_files']=[file_record(0,'root',path=d['prep_root'],identity=ROOT)]+list(extra_files)
    if commands:
        for role,path in [('tool',d['python_abs']),('tool',d['git_abs']),('tool',d['docker_abs']),('runtime','/synthetic/runtime'),('plugin',d['compose_plugin_abs'])]:
            d['approved_files'].append(file_record(len(d['approved_files']),role,b'{}',path))
    return d

def admitted(d):
    result=p.admit_contract(json.dumps(d).encode())
    if isinstance(result,p.Problem):raise AssertionError(result)
    return result

class Files:
    def __init__(self,contract):
        self.contract=contract;self.calls=[];self.scripts={};self.rechecks={}
    def observe(self,spec):
        self.calls.append(('observe',spec.id))
        if spec.id in self.scripts:return iter(self.scripts[spec.id])
        events=[E('parents',spec.parents)]
        if spec.purpose=='git_absent':events +=[E('absent','ENOENT')]
        elif spec.identity.type in ('directory','socket'):
            events += [E('metadata',spec.identity),E('entry',spec.identity)]
        else:
            body=CONFIG.encode() if spec.purpose=='git_config' else b'{}'
            events += [E('opened',('fd-'+spec.id,spec.identity)),E('bytes',('fd-'+spec.id,body)),
                       E('after',('fd-'+spec.id,spec.identity)),E('entry',spec.identity)]
        return iter(events+[E('done')])
    def revalidate(self,spec):
        self.calls.append(('revalidate',spec.id))
        events=self.rechecks.get(spec.id,[E('parents',spec.parents),
            E('absent','ENOENT') if spec.purpose=='git_absent' else E('entry',spec.identity),E('done')])
        return iter(events)

class Commands:
    def __init__(self):self.calls=[];self.scripts={};self.termination=[];self.acks={'TERM':True,'KILL':True}
    def start(self,spec):
        self.calls.append(spec)
        return 'owned-child',iter(self.scripts.get(spec.id,[E('stdout',b'Python 3.12.1\n'),E('eof','stdout'),E('eof','stderr'),E('exit',0),E('done')]))
    def terminate(self,child,signal,deadline_ms):
        self.termination.append((child,signal,deadline_ms))
        return iter([E('ack')] if self.acks[signal] else [])

class Outputs:
    def __init__(self):
        self.calls=[];self.saved={};self.identities={};self.free=1024**3;self.existing_names=[]
        self.mutate=None;self.fail=None;self.partial=None;self.hook=None
    def inventory(self):
        self.calls.append(('inventory',));return iter([E('existing',tuple(dict.fromkeys(self.existing_names+list(self.saved)))),E('done')])
    def space(self):
        self.calls.append(('space',));return iter([E('free',self.free),E('done')])
    def create(self,name,body,owner,mode,exclusive):
        self.calls.append(('create',name,owner,mode,exclusive))
        assert owner=='collector' and mode==0o600 and exclusive
        return self.events(name,body)
    def finalize_existing(self,name,body,owner):
        self.calls.append(('existing',name,owner));return self.events(name,body,True)
    def events(self,name,body,existing=False):
        ident=replace(IDENT,inode=100+len(self.saved),parent='file_0',size=len(body) if existing else 0)
        self.identities[name]=replace(ident,size=len(body))
        for kind,data in [('opened',ident),('read' if existing else 'written',body if existing else len(body)),
                          ('flushed',None),('synced',None),('identity',self.identities[name]),('done',None)]:
            if self.hook:self.hook(name,kind)
            if self.fail==(name,kind):yield E('error',SENTINEL);return
            if self.partial==name and kind=='written':data=len(body)-1
            if self.mutate==(name,kind) and kind=='identity':data=replace(data,nlink=2)
            if kind=='synced':self.saved[name]=body
            yield E(kind,data)
    def verify(self,expected):
        self.calls.append(('verify',tuple(x[0] for x in expected)))
        for name,digest,identity in expected:
            yield E('verified',(name,hashlib.sha256(self.saved[name]).hexdigest(),self.identities[name]))
        yield E('done')

def run(d=None,limits=None,setup=None):
    cc=admitted(d or doc())
    if limits:cc=replace(cc,limits=limits)
    f,cmd,o,clock,cancel=Files(cc),Commands(),Outputs(),Clock(),Cancel()
    if setup:setup(f,cmd,o,clock,cancel)
    result=c.collect(cc,f,cmd,o,clock,cancel)
    return result,f,cmd,o,clock,cancel

class CollectorTests(unittest.TestCase):
    def incomplete(self,r,code=None):
        self.assertEqual(r.status,'INCOMPLETE');self.assertIsNone(r.receipt)
        if code:self.assertIn(code,[p.code for p in r.problems])
        self.assertFalse(r.host_observed);self.assertFalse(r.runtime_accepted);self.assertFalse(r.trusted)
        self.assertEqual(r.accepted_case_credit,0)
        self.assertNotIn(SENTINEL,repr(r))

    def test_happy_finalization_order_manifest_and_nonpromotion(self):
        r,f,cmd,o,_,_=run(doc(['python_version']))
        self.assertEqual(r.status,'COMPLETE');self.assertEqual(r.classification,'preparation_complete_execution_blocked')
        self.assertEqual(r.states,('NEW','ADMITTED','FILE_ELIGIBLE','COMMAND_ELIGIBLE','PROJECTED','COMPLETE'))
        self.assertEqual([v.id for v in cmd.calls],['python_version'])
        created=[x[1] for x in o.calls if x[0]=='create']
        self.assertEqual(created[-2:],['REPORT.md','SHA256SUMS'])
        self.assertNotIn('independent-review.md',created)
        sums=o.saved['SHA256SUMS'].decode().splitlines()
        expected=[hashlib.sha256(o.saved[n]).hexdigest()+'  '+n for n in sorted(o.saved) if n!='SHA256SUMS']
        self.assertEqual(sums,expected);self.assertIn('REPORT.md',r.receipt.covered_names)
        self.assertEqual(r.receipt.checksum_digest,hashlib.sha256(o.saved['SHA256SUMS']).hexdigest())
        self.assertNotIn(b'COMPLETE',o.saved['REPORT.md'])
        self.assertIn(b'completion_requires_validated_SHA256SUMS_and_final_receipt',o.saved['REPORT.md'])
        self.assertIn(b'compose-baseline.json',o.saved['REPORT.md'])
        self.assertFalse(r.receipt.trusted);self.assertEqual(r.receipt.evidence_kind,'synthetic')

    def test_invalid_or_expired_admission_precedes_all_ports(self):
        cc=contract();f,cmd,o,clock,cancel=Files(cc),Commands(),Outputs(),Clock(),Cancel()
        for bad in (p.Problem('invalid_contract'),replace(cc,trusted=True),replace(cc,commands=(replace(cc.commands[0],argv=('/bad',)),))):
            r=c.collect(bad,f,cmd,o,clock,cancel)
            self.assertEqual(r.status,'BLOCKED');self.assertEqual(f.calls,[]);self.assertEqual(cmd.calls,[]);self.assertEqual(o.calls,[])
        clock.tick=1800000
        self.assertEqual(c.collect(cc,f,cmd,o,clock,cancel).status,'BLOCKED');self.assertEqual(o.calls,[])

    def test_git_and_compose_never_start_without_config_proofs(self):
        for command in ('git_version','git_head','compose_baseline','compose_effective'):
            r,_,cmd,_,_,_=run(doc([command]))
            self.assertEqual(cmd.calls,[]);self.assertIn('missing_prerequisite',[v.code for v in r.problems])
        d=doc(['python_version','git_version']);d['git_provenance']['complete']=False
        r,_,cmd,_,_,_=run(d);self.assertEqual([v.id for v in cmd.calls],['python_version'])

    def test_identity_and_descriptor_races_stop_before_commands(self):
        d=doc(['python_version']);target='file_1'
        cases=[E('parents',(replace(PARENT,inode=999),)), E('opened',('fd-'+target,replace(IDENT,inode=999))),
               E('opened',('fd-'+target,replace(IDENT,type='fifo'))),E('opened',('fd-'+target,replace(IDENT,type='symlink'))),
               E('bytes',('wrong-descriptor',b'{}')), E('after',('fd-'+target,replace(IDENT,ctime_ns=99))),
               E('entry',replace(IDENT,dev=99)),E('blocked')]
        for bad in cases:
            def setup(f,cmd,o,clock,cancel):
                spec=f.contract.files[1];events=list(f.observe(spec));f.calls=[]
                kinds=[e.kind for e in events];index=kinds.index(bad.kind) if bad.kind in kinds else len(events)-1
                events[index]=bad;f.scripts[target]=events
            r,_,cmd,o,_,_=run(d,setup=setup);self.incomplete(r);self.assertEqual(cmd.calls,[]);self.assertEqual(o.saved,{})

    def test_absence_accepts_only_enoent_and_is_rechecked(self):
        d=doc();d['approved_files'].append(file_record(1,'git_absent',path='/synthetic/config'))
        for error in ('EACCES','EIO',SENTINEL):
            def setup(f,cmd,o,clock,cancel):f.scripts['file_1']=[E('parents',(PARENT,)),E('absent',error),E('done')]
            r,_,cmd,_,_,_=run(d,setup=setup);self.incomplete(r,'integrity');self.assertEqual(cmd.calls,[])

    def test_file_bytes_chunks_counts_and_nonrenewable_budget(self):
        d=doc(extra_files=[file_record(1,body=b'{}')])
        r,*_=run(d,replace(p.Limits(),file_bytes=2,input_bytes=2));self.assertEqual(r.status,'COMPLETE')
        for lim in (replace(p.Limits(),file_bytes=1),replace(p.Limits(),input_bytes=1),
                    replace(p.Limits(),input_files=0),replace(p.Limits(),metadata_entries=1),replace(p.Limits(),chunk_bytes=1)):
            r,_,cmd,_,_,_=run(d,lim);self.incomplete(r,'cap');self.assertEqual(cmd.calls,[])
        def setup(f,cmd,o,clock,cancel):
            def events():
                yield E('parents',(PARENT,));clock.tick=5000;yield E('metadata',ROOT);yield E('entry',ROOT);yield E('done')
            f.scripts['file_0']=events()
        r,*_=run(d,setup=setup);self.incomplete(r,'deadline')

    def test_capture_combined_and_aggregate_caps_no_raw_leak(self):
        d=doc(['python_version'])
        for events in ([E('stdout',b'Python 3.12.1\n'),E('stderr',SENTINEL.encode()),E('eof','stdout'),E('eof','stderr'),E('exit',0),E('done')],
                       [E('stderr',b'a'*20),E('done')]):
            def setup(f,cmd,o,clock,cancel):cmd.scripts['python_version']=events
            r,_,cmd,o,_,_=run(d,replace(p.Limits(),command_bytes=15),setup)
            self.incomplete(r,'cap');self.assertEqual(cmd.termination,[('owned-child','TERM',2000)]);self.assertNotIn(SENTINEL,str(o.saved))
        r,*_=run(d,replace(p.Limits(),command_bytes=14,capture_bytes=14));self.assertEqual(r.status,'COMPLETE')
        r,*_=run(d,replace(p.Limits(),capture_bytes=13));self.incomplete(r,'cap')

    def test_missing_eof_nonzero_and_malformed_never_source_counterexample(self):
        d=doc(['python_version'])
        for events in ([E('stdout',b'Python 3.12.1\n'),E('eof','stdout'),E('exit',0),E('done')],
                       [E('stdout',b'Python 3.12.1\n'),E('eof','stdout'),E('eof','stderr'),E('exit',2),E('done')],
                       [E('stdout',SENTINEL.encode()),E('eof','stdout'),E('eof','stderr'),E('exit',0),E('done')]):
            def setup(f,cmd,o,clock,cancel):cmd.scripts['python_version']=events
            r,_,cmd,o,_,_=run(d,setup=setup)
            self.incomplete(r);self.assertNotEqual(r.classification,'source_incompatible');self.assertNotIn(SENTINEL,str(o.saved))
            self.assertEqual(len(cmd.calls),1)

    def test_cancel_deadline_and_storage_precedence_termination(self):
        d=doc(['python_version'])
        def setup(f,cmd,o,clock,cancel):
            def events():
                yield E('stdout',b'Python ');cancel.value=True;clock.tick=10000;yield E('stdout',b'3.12.1\n')
            cmd.scripts['python_version']=events();cmd.acks['TERM']=False;cmd.acks['KILL']=False
        r,_,cmd,_,_,_=run(d,setup=setup);self.incomplete(r,'cancel')
        self.assertEqual(cmd.termination,[('owned-child','TERM',2000),('owned-child','KILL',2000)])
        self.assertTrue(r.captures);self.assertFalse(r.captures[0].complete)
        def low(f,cmd,o,clock,cancel):o.free=1024**3-1
        r,_,cmd,_,_,_=run(d,setup=low);self.incomplete(r,'storage');self.assertEqual(cmd.calls,[])
        def cancelled(f,cmd,o,clock,cancel):cancel.value=True
        r,f,cmd,o,_,_=run(d,setup=cancelled);self.incomplete(r,'cancel');self.assertEqual(f.calls,[])

    def test_every_output_boundary_failure_blocks_final_receipt(self):
        baseline,*_,out,clock,cancel=run()
        names=list(out.saved)
        for name in names:
            for kind in ('opened','written','flushed','synced','identity','done'):
                def setup(f,cmd,o,clock,cancel):o.fail=(name,kind)
                r,_,_,o,_,_=run(setup=setup)
                self.incomplete(r);self.assertNotIn(('create','independent-review.md'),o.calls)
        for name in ('REPORT.md','SHA256SUMS'):
            for kind in ('opened','written','flushed','synced','identity','done'):
                def setup(f,cmd,o,clock,cancel):
                    def hook(n,k):
                        if (n,k)==(name,kind):cancel.value=True
                    o.hook=hook
                r,*_=run(setup=setup);self.incomplete(r,'cancel')

    def test_output_collisions_links_partial_writes_and_exceptions(self):
        for name in p.OUTPUT_NAMES+('execution-bundle.json',SENTINEL):
            def setup(f,cmd,o,clock,cancel):o.existing_names=[name]
            r,_,_,o,_,_=run(setup=setup);self.incomplete(r);self.assertEqual(o.saved,{})
        for attr,value in [('partial','REPORT.md'),('mutate',('REPORT.md','identity'))]:
            def setup(f,cmd,o,clock,cancel):setattr(o,attr,value)
            r,*_=run(setup=setup);self.incomplete(r)
        def setup(f,cmd,o,clock,cancel):
            def bad():raise RuntimeError(SENTINEL)
            o.inventory=bad
        r,*_=run(setup=setup);self.incomplete(r)

    def test_clock_rollback_and_final_verification_failure(self):
        def setup(f,cmd,o,clock,cancel):
            clock.tick=2
            def events():
                yield E('parents',(PARENT,));clock.tick=1;yield E('metadata',ROOT)
            f.scripts['file_0']=events()
        r,*_=run(setup=setup);self.incomplete(r,'integrity')
        def setup(f,cmd,o,clock,cancel):
            def verify(expected):
                yield E('verified',('REPORT.md','0'*64,IDENT));yield E('done')
            o.verify=verify
        r,*_=run(setup=setup);self.incomplete(r,'integrity')

class AdversarialMatrixTests(unittest.TestCase):
    """Additional matrix rows with cheap scaled boundaries and virtual time."""
    def test_complete_git_prerequisites_and_config_creation_race(self):
        d=doc(['git_version']);gp=d['git_provenance']
        d['approved_files'].append(file_record(len(d['approved_files']),'git_config',CONFIG.encode(),d['checkout']+'/.git/config'))
        for path in gp['absent_paths']:
            d['approved_files'].append(file_record(len(d['approved_files']),'git_absent',path=path,identity=replace(IDENT,type='absent')))
        def success(f,cmd,o,clock,cancel):
            cmd.scripts['git_version']=[E('stdout',b'git version 2.43.0\n'),E('eof','stdout'),E('eof','stderr'),E('exit',0),E('done')]
        r,_,cmd,_,_,_=run(d,setup=success)
        self.assertEqual(r.status,'COMPLETE');self.assertEqual([s.id for s in cmd.calls],['git_version'])
        for after in (False,True):
            def race(f,cmd,o,clock,cancel):
                success(f,cmd,o,clock,cancel)
                target=next(s for s in f.contract.files if s.purpose=='git_absent')
                if not after:f.rechecks[target.id]=[E('parents',target.parents),E('absent','PRESENT'),E('done')]
                else:
                    def events():
                        yield E('stdout',b'git version 2.43.0\n');yield E('eof','stdout');yield E('eof','stderr');yield E('exit',0)
                        f.rechecks[target.id]=[E('parents',target.parents),E('absent','PRESENT'),E('done')];yield E('done')
                    cmd.scripts['git_version']=events()
            r,_,cmd,o,_,_=run(d,setup=race)
            self.assertEqual(r.status,'INCOMPLETE');self.assertEqual(len(cmd.calls),int(after));self.assertEqual(o.saved,{})

    def test_aggregate_capture_across_commands_and_complete_stderr_hash(self):
        d=doc(['python_version','docker_version'])
        def setup(f,cmd,o,clock,cancel):
            cmd.scripts['docker_version']=[E('stderr',SENTINEL.encode()),E('stdout',b'Docker version 27.1.0\n'),E('eof','stderr'),E('eof','stdout'),E('exit',0),E('done')]
        r,_,cmd,o,_,_=run(d,replace(p.Limits(),capture_bytes=30),setup)
        self.assertEqual(r.status,'INCOMPLETE');self.assertEqual(len(cmd.calls),2)
        self.assertTrue(r.captures[0].complete);self.assertFalse(r.captures[1].complete)
        self.assertEqual(cmd.termination,[('owned-child','TERM',2000)])
        r,_,_,o,_,_=run(d,setup=setup)
        self.assertEqual(r.status,'COMPLETE');self.assertNotIn(SENTINEL,str(o.saved));self.assertNotIn(SENTINEL,repr(r))
        self.assertEqual(r.captures[1].stderr_digest,hashlib.sha256(SENTINEL.encode()).hexdigest())

    def test_command_deadline_at_eof_or_after_stream_and_exception_prefix(self):
        d=doc(['python_version'])
        for phase in ('eof','after'):
            def setup(f,cmd,o,clock,cancel):
                def events():
                    yield E('stdout',b'Python 3.12.1\n');yield E('eof','stdout');yield E('eof','stderr');yield E('exit',0)
                    if phase=='eof':clock.tick=10000
                    yield E('done')
                    if phase=='after':clock.tick=10000
                cmd.scripts['python_version']=events()
            r,*_=run(d,setup=setup)
            self.assertEqual(r.status,'INCOMPLETE');self.assertIn('deadline',[x.code for x in r.problems])
        def setup(f,cmd,o,clock,cancel):
            def events():
                yield E('stderr',SENTINEL.encode());raise RuntimeError(SENTINEL)
            cmd.scripts['python_version']=events()
        r,_,cmd,_,_,_=run(d,setup=setup)
        self.assertEqual(r.status,'INCOMPLETE');self.assertEqual(len(r.captures),1)
        self.assertFalse(r.captures[0].complete);self.assertNotIn(SENTINEL,repr(r))

    def test_cumulative_file_time_and_output_time_do_not_renew(self):
        d=doc(extra_files=[file_record(1),file_record(2)])
        def setup(f,cmd,o,clock,cancel):
            original=f.observe
            def observe(spec):
                for event in original(spec):
                    if event.kind=='done':clock.tick+=2
                    yield event
            f.observe=observe
        r,*_=run(d,replace(p.Limits(),files_ms=5),setup)
        self.assertEqual(r.status,'INCOMPLETE');self.assertIn('deadline',[v.code for v in r.problems])
        def setup(f,cmd,o,clock,cancel):
            def hook(n,k):
                if k in ('written','flushed','synced'):clock.tick+=3
            o.hook=hook
        # Each operation stays below 5ms; a payload may take more than 5ms.
        r,*_=run(limits=replace(p.Limits(),write_ms=5,writes_ms=100),setup=setup)
        self.assertEqual(r.status,'COMPLETE')
        r,*_=run(limits=replace(p.Limits(),write_ms=5,writes_ms=20),setup=setup)
        self.assertEqual(r.status,'INCOMPLETE');self.assertIn('deadline',[v.code for v in r.problems])

    def test_exclusive_output_size_aggregate_and_late_collision(self):
        for limits in (replace(p.Limits(),output_bytes=100),replace(p.Limits(),document_bytes=100)):
            r,*_=run(limits=limits);self.assertEqual(r.status,'INCOMPLETE');self.assertIn('cap',[v.code for v in r.problems])
        def setup(f,cmd,o,clock,cancel):
            old=o.verify
            def verify(expected):
                o.existing_names.append('source-pins-extra.json')
                yield from old(expected)
            o.verify=verify
        r,*_=run(setup=setup);self.assertEqual(r.status,'INCOMPLETE')

    def test_owner_supplied_payloads_are_finalized_without_overwrite(self):
        d=doc();d['output_owners']['owner-contract.json']='operator';d['output_owners']['dispatch.json']='operator'
        def setup(f,cmd,o,clock,cancel):o.existing_names=['owner-contract.json','dispatch.json']
        r,_,_,o,_,_=run(d,setup=setup)
        self.assertEqual(r.status,'COMPLETE')
        self.assertEqual([x[1] for x in o.calls if x[0]=='existing'],['dispatch.json','owner-contract.json'])
        self.assertFalse(any(x[0]=='create' and x[1] in o.existing_names for x in o.calls))

    def test_stop_after_checksum_before_receipt_and_mutated_final_payload(self):
        for failure in ('cancel','mutation','omission'):
            def setup(f,cmd,o,clock,cancel):
                original=o.verify
                def verify(expected):
                    if failure=='mutation':o.saved['REPORT.md']+=b'changed'
                    if failure=='omission':expected=expected[:-1]
                    yield from original(expected)
                    if failure=='cancel':cancel.value=True
                o.verify=verify
            r,*_=run(setup=setup);self.assertEqual(r.status,'INCOMPLETE');self.assertIsNone(r.receipt)

    def test_termination_deadline_forces_kill_and_no_unrelated_calls(self):
        def setup(f,cmd,o,clock,cancel):
            cmd.scripts['python_version']=[E('blocked')]
            def terminate(child,signal,deadline_ms):
                cmd.termination.append((child,signal,deadline_ms))
                if signal=='TERM':clock.tick+=2000
                yield E('ack')
            cmd.terminate=terminate
        r,_,cmd,o,_,_=run(doc(['python_version']),setup=setup)
        self.assertEqual(r.status,'INCOMPLETE');self.assertEqual(cmd.termination,[('owned-child','TERM',2000),('owned-child','KILL',2000)])
        self.assertEqual(o.saved,{})

class ComposeSequencingTests(unittest.TestCase):
    def test_effective_model_is_finalized_before_effective_compose_command(self):
        d=doc(['git_files','git_head','git_tree','git_status','git_remote','git_symbolic','compose_baseline','compose_effective'])
        d['manifest_pin']=hashlib.sha256(b'100644 '+b'a'*40+b' 0\tinput.json\x00').hexdigest()
        source=file_record(len(d['approved_files']),'source',b'{}','/synthetic/clone/input.json')
        d['approved_files'].append(source)
        d['approved_files'].append(file_record(len(d['approved_files']),'git_config',CONFIG.encode(),d['checkout']+'/.git/config'))
        for path in d['git_provenance']['absent_paths']:
            d['approved_files'].append(file_record(len(d['approved_files']),'git_absent',path=path,identity=replace(IDENT,type='absent')))
        seen=[]
        def setup(f,cmd,o,clock,cancel):
            answers={'git_files':b'100644 '+b'a'*40+b' 0\tinput.json\x00','git_head':p.CANDIDATE.encode()+b'\n',
                'git_tree':p.TREE.encode()+b'\n','git_status':b'','git_remote':b'','git_symbolic':b'',
                'compose_baseline':json.dumps(d['baseline']).encode(),
                'compose_effective':json.dumps(p.effective_model(f.contract)).encode()}
            for k,body in answers.items():
                cmd.scripts[k]=([E('stdout',body)] if body else [])+[E('eof','stdout'),E('eof','stderr'),E('exit',1 if k=='git_symbolic' else 0),E('done')]
            old=cmd.start
            def start(spec):
                if spec.id=='compose_effective':seen.append('effective.json' in o.saved)
                return old(spec)
            cmd.start=start
        r,_,cmd,o,_,_=run(d,setup=setup)
        self.assertEqual(r.status,'COMPLETE');self.assertEqual(seen,[True])
        self.assertEqual(len([x for x in o.calls if x[0]=='create' and x[1]=='effective.json']),1)
        self.assertIn('effective.json',r.receipt.covered_names)

class BudgetAndStopMatrixTests(unittest.TestCase):
    def test_cancel_during_file_and_fsync_and_storage_during_write(self):
        for phase in ('read','fsync','storage'):
            def setup(f,cmd,o,clock,cancel):
                if phase=='read':
                    original=f.observe
                    def observe(spec):
                        for event in original(spec):
                            if event.kind=='bytes':cancel.value=True
                            yield event
                    f.observe=observe
                else:
                    def hook(n,k):
                        if k=='synced':
                            if phase=='fsync':cancel.value=True
                            else:raise OSError(SENTINEL)
                    o.hook=hook
            r,_,cmd,o,_,_=run(doc(['python_version']),setup=setup)
            self.assertEqual(r.status,'INCOMPLETE');self.assertIsNone(r.receipt);self.assertNotIn(SENTINEL,repr(r));self.assertNotIn(SENTINEL,str(o.saved))
            if phase=='read':self.assertEqual(cmd.calls,[])

    def test_json_parse_validate_serialize_and_aggregate_deadlines(self):
        # The operation timer is tested through the real collector mechanism;
        # scripted ports remain idle while virtual time expires in each phase.
        cc=admitted(doc());clock=Clock();a=c._Attempt(cc,Files(cc),Commands(),Outputs(),clock,Cancel())
        for label in ('parse','validate','serialize'):
            with self.subTest(label=label):
                clock.tick=0;a.last=0;a.spent['json']=0;a.problems=[]
                with self.assertRaises(c._Stop):
                    with a.operation('json',5000):clock.tick=5000;a.boundary()
                self.assertEqual(a.problems,[p.Problem('deadline')])
        clock.tick=0;a.last=0;a.spent['json']=59999;a.problems=[]
        with self.assertRaises(c._Stop):
            with a.operation('json',5000):clock.tick=1;a.boundary()
        self.assertEqual(a.problems,[p.Problem('deadline')])

    def test_scaled_file_and_metadata_exact_boundaries(self):
        d=doc(extra_files=[file_record(1),file_record(2)])
        # root uses 3 metadata entries; each regular file uses 3.
        # Verify counting before observation directly, so later output metadata
        # cannot obscure the exact input-file and metadata boundary.
        cc=admitted(d);f=Files(cc);a=c._Attempt(replace(cc,limits=replace(p.Limits(),input_files=2,metadata_entries=9)),f,Commands(),Outputs(),Clock(),Cancel())
        for spec in cc.files:a.observe(spec)
        self.assertEqual(a.totals['regular'],2);self.assertEqual(a.totals['metadata'],9)
        with self.assertRaises(c._Stop):a.observe(cc.files[1])
        self.assertEqual(len([v for v in f.calls if v[0]=='observe']),3)

    def test_outer_deadline_and_monotonic_clock_stop_latch(self):
        def setup(f,cmd,o,clock,cancel):
            def stream():
                yield E('parents',(PARENT,));clock.tick=1800000;yield E('metadata',ROOT)
                clock.tick=0;yield E('entry',ROOT);yield E('done')
            f.scripts['file_0']=stream()
        r,_,cmd,o,_,_=run(setup=setup)
        self.assertEqual(r.status,'INCOMPLETE');self.assertIn('deadline',[v.code for v in r.problems]);self.assertEqual(cmd.calls,[]);self.assertEqual(o.saved,{})

class IndependentReviewRegressionTests(unittest.TestCase):
    def test_socket_alone_or_partial_context_does_not_enable_daemon_reads(self):
        for names in (['image_runner'],['context_inspect','image_runner'],
                      ['context_show','image_runner'],['context_show','context_inspect','image_runner']):
            d=doc(names)
            d['approved_files'].append(file_record(len(d['approved_files']),'socket',
                path=d['local_socket'][7:],identity=replace(IDENT,type='socket')))
            def setup(f,cmd,o,clock,cancel):
                cmd.scripts['context_show']=[E('stdout',b'default\n'),E('eof','stdout'),E('eof','stderr'),E('exit',0),E('done')]
                # A mismatched route must stop before the later image request.
                bad={'Name':'default','Endpoints':{'docker':{'Host':'tcp://remote','SkipTLSVerify':False}}}
                cmd.scripts['context_inspect']=[E('stdout',json.dumps(bad).encode()),E('eof','stdout'),E('eof','stderr'),E('exit',0),E('done')]
            r,_,cmd,_,_,_=run(d,setup=setup)
            self.assertNotIn('image_runner',[s.id for s in cmd.calls])
            self.assertEqual([s.id for s in cmd.calls],
                ['context_show','context_inspect'] if len(names)==3 else
                ['context_show'] if names[0]=='context_show' else [])

    def test_daemon_commands_do_not_start_without_socket_and_context_chain(self):
        for command in ('context_show','context_inspect','daemon_version','daemon_info','image_runner',
                        'inventory_names','inventory_owner','inventory_project'):
            d=doc([command])
            def setup(f,cmd,o,clock,cancel):
                image=[{'Id':p.IMAGES[0],'Os':'linux','Architecture':'amd64',
                    'Config':d['image_configs'][p.IMAGES[0]],'RootFS':{'Type':'layers','Layers':[]},'RepoDigests':[]}]
                cmd.scripts[command]=[E('stdout',json.dumps(image).encode()),E('eof','stdout'),E('eof','stderr'),E('exit',0),E('done')]
            r,_,cmd,_,_,_=run(d,setup=setup)
            self.assertEqual(cmd.calls,[],command)
            self.assertIn('missing_prerequisite',[v.code for v in r.problems])

    def test_socket_and_default_context_chain_enables_image_and_rechecks_socket(self):
        d=doc(['context_show','context_inspect','image_runner'])
        path=d['local_socket'][7:]
        socket=file_record(len(d['approved_files']),'socket',path=path,identity=replace(IDENT,type='socket'))
        d['approved_files'].append(socket)
        def setup(f,cmd,o,clock,cancel):
            answers={'context_show':b'default\n','context_inspect':json.dumps({'Name':'default','Endpoints':{'docker':{'Host':d['local_socket'],'SkipTLSVerify':False}}}).encode(),
              'image_runner':json.dumps([{'Id':p.IMAGES[0],'Os':'linux','Architecture':'amd64','Config':d['image_configs'][p.IMAGES[0]],'RootFS':{'Type':'layers','Layers':[]},'RepoDigests':[]}]).encode()}
            for name,body in answers.items():cmd.scripts[name]=[E('stdout',body),E('eof','stdout'),E('eof','stderr'),E('exit',0),E('done')]
        r,f,cmd,_,_,_=run(d,setup=setup)
        self.assertEqual(r.status,'COMPLETE');self.assertEqual([s.id for s in cmd.calls],['context_show','context_inspect','image_runner'])
        self.assertEqual(len([v for v in f.calls if v==('revalidate',socket['id'])]),6)
        def race(f,cmd,o,clock,cancel):
            setup(f,cmd,o,clock,cancel)
            original=cmd.start
            def start(spec):
                if spec.id=='context_inspect':
                    def events():
                        for event in original(spec)[1]:
                            if event.kind=='done':f.rechecks[socket['id']]=[E('parents',(PARENT,)),E('entry',replace(IDENT,type='socket',inode=999)),E('done')]
                            yield event
                    return 'owned-child',events()
                return original(spec)
            cmd.start=start
        r,_,cmd,_,_,_=run(d,setup=race)
        self.assertEqual(r.status,'INCOMPLETE');self.assertEqual([s.id for s in cmd.calls],['context_show','context_inspect'])

    def test_incomplete_attempt_never_has_completed_preparation_classification(self):
        def setup(f,cmd,o,clock,cancel):cancel.value=True
        r,f,cmd,o,_,_=run(setup=setup)
        self.assertEqual(r.status,'INCOMPLETE');self.assertEqual(r.classification,'collection_incomplete')
        self.assertEqual(f.calls,[]);self.assertEqual(cmd.calls,[]);self.assertEqual(o.calls,[])
        def failure(f,cmd,o,clock,cancel):o.fail=('REPORT.md','synced')
        r,*_=run(setup=failure)
        self.assertEqual(r.classification,'collection_incomplete');self.assertIsNone(r.receipt)

    def test_forged_contract_is_rejected_before_stock_serialization_or_ports(self):
        cc=admitted(doc());data=p.thaw(cc.data);data['extra']='x'*(p.Limits().json_string+1)
        forged=replace(cc,data=p.freeze(data));calls=[];original=p.encode
        def spy(value):
            calls.append('stock_encode');return original(value)
        p.encode=spy
        try:
            f,cmd,o=Files(cc),Commands(),Outputs()
            r=c.collect(forged,f,cmd,o,Clock(),Cancel())
        finally:p.encode=original
        self.assertEqual(r.status,'BLOCKED');self.assertEqual(calls,[])
        self.assertEqual(f.calls,[]);self.assertEqual(cmd.calls,[]);self.assertEqual(o.calls,[])
        self.assertEqual(r.classification,'collection_blocked')
