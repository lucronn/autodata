"""Deterministic synthetic-only collector. Ports have no default instances."""
from dataclasses import dataclass
from . import policy as p

@dataclass(frozen=True)
class Event:
    kind:str
    data:object=None

@dataclass(frozen=True)
class Capture:
    stdout_digest:str
    stderr_digest:str
    complete:bool

@dataclass(frozen=True)
class CollectionResult:
    status:str
    states:tuple=()
    problems:tuple=()
    observations:tuple=()
    captures:tuple=()
    receipt:object=None
    classification:str='preparation_complete_execution_blocked'
    trusted:bool=False
    runtime_accepted:bool=False
    host_observed:bool=False
    evidence_kind:str='synthetic'
    release_state:str='unverified'
    accepted_case_credit:int=0

from contextlib import contextmanager
from dataclasses import replace
import hashlib
from typing import Protocol, Iterable

class FilePort(Protocol):
    def observe(self,spec:p.FileSpec)->Iterable[Event]: ...
    def revalidate(self,spec:p.FileSpec)->Iterable[Event]: ...
class CommandPort(Protocol):
    def start(self,spec:p.CommandSpec)->tuple[object,Iterable[Event]]: ...
    def terminate(self,child:object,signal:str,deadline_ms:int)->Iterable[Event]: ...
class OutputPort(Protocol):
    def inventory(self)->Iterable[Event]: ...
    def space(self)->Iterable[Event]: ...
    def create(self,name:str,body:bytes,owner:str,mode:int,exclusive:bool)->Iterable[Event]: ...
    def finalize_existing(self,name:str,body:bytes,owner:str)->Iterable[Event]: ...
    def verify(self,expected:tuple)->Iterable[Event]: ...
class Clock(Protocol):
    def now(self)->int: ...
class CancelPort(Protocol):
    def cancelled(self)->bool: ...

class _Stop(Exception): pass

_ORDER={'cancel':0,'deadline':1,'cap':2,'storage':3,'integrity':4}

class _Attempt:
    def __init__(self,contract,files,commands,outputs,clock,cancel):
        self.contract=contract;self.d=p.values(contract);self.limits=contract.limits
        self.files=files;self.commands=commands;self.outputs=outputs;self.clock=clock;self.cancel=cancel
        self.last=clock.now();self.start=self.last;self.active=[]
        self.spent={'files':0,'json':0,'writes':0};self.totals={'input':0,'capture':0,'output':0,'regular':0,'metadata':0}
        self.states=['NEW','ADMITTED'];self.problems=[];self.observations=[];self.captures=[]
        self.approved=set();self.seen=set();self.child=None;self.root=None;self.finalized={};self.existing=()
        self.classification='preparation_complete_execution_blocked'
    def stop(self,*codes):
        for code in sorted(set(codes),key=lambda x:_ORDER.get(x,10)):
            if p.Problem(code) not in self.problems:self.problems.append(p.Problem(code))
        raise _Stop()
    def boundary(self):
        codes=[]
        if self.cancel.cancelled():codes.append('cancel')
        now=self.clock.now()
        if type(now) is not int or now<self.last:codes.append('integrity')
        else:
            self.last=now
            if now-self.start>=self.limits.outer_ms or now>=self.d['expires_tick']:codes.append('deadline')
            for category,began,limit in self.active:
                cumulative={'files':self.limits.files_ms,'json':self.limits.json_ms,'writes':self.limits.writes_ms}[category]
                if now-began>=limit or self.spent[category]+now-began>=cumulative:codes.append('deadline')
        if codes:self.stop(*codes)
        return now
    @contextmanager
    def operation(self,category,limit):
        self.boundary();began=self.last;self.active.append((category,began,limit))
        try:
            yield
            self.boundary()
        finally:
            self.active.pop();self.spent[category]+=max(0,self.last-began)
    def check_json(self):self.boundary()
    def charge(self,key,count,limit):
        if type(count) is not int or count<0:self.stop('integrity')
        if self.totals[key]+count>limit:self.stop('cap')
        self.totals[key]+=count
    def event_stream(self,events,max_events=None):
        """No success after done, incomplete stream or unbounded empty events."""
        done=False;count=0
        for event in events:
            self.boundary();count+=1
            if count>(max_events if max_events is not None else self.limits.metadata_entries+10):self.stop('cap')
            if not isinstance(event,Event) or done:self.stop('integrity')
            if event.kind in ('error','blocked'):self.stop('integrity')
            if event.kind=='done':done=True
            yield event
        self.boundary()
        if not done:self.stop('incomplete')
    def metadata(self,count=1):self.charge('metadata',count,self.limits.metadata_entries)
    def validate_identity(self,actual,expected):
        if not isinstance(actual,p.Identity) or actual!=expected:self.stop('integrity')
        if actual.mode&0o022 or actual.type not in ('regular','directory','socket','absent'):self.stop('integrity')
    def observe(self,spec):
        regular=spec.identity.type=='regular' and spec.purpose!='git_absent'
        if regular:
            self.charge('regular',1,self.limits.input_files)
            if spec.identity.size>self.limits.file_bytes:self.stop('cap')
        if spec.purpose not in ('git_absent','socket','root') and not regular:self.stop('integrity')
        stage=0;handle=None;size=0;hasher=hashlib.sha256();config=[]
        with self.operation('files',self.limits.file_ms):
            for event in self.event_stream(self.files.observe(spec),max_events=self.limits.file_bytes+10):
                k,v=event.kind,event.data
                if stage==0 and k=='parents':
                    self.metadata(len(spec.parents));
                    if v!=spec.parents:self.stop('integrity')
                    for parent in v:
                        if parent.type!='directory' or parent.mode&0o022:self.stop('integrity')
                    stage=1
                elif stage==1 and spec.purpose=='git_absent' and k=='absent':
                    self.metadata();
                    if v!='ENOENT':self.stop('integrity')
                    stage=5
                elif stage==1 and not regular and k=='metadata':
                    self.metadata();self.validate_identity(v,spec.identity);stage=4
                elif stage==1 and regular and k=='opened':
                    self.metadata();handle,ident=v;self.validate_identity(ident,spec.identity);stage=2
                elif stage==2 and k=='bytes':
                    descriptor,chunk=v
                    if descriptor!=handle or type(chunk) is not bytes or not chunk:self.stop('integrity')
                    if len(chunk)>self.limits.chunk_bytes or size+len(chunk)>self.limits.file_bytes or size+len(chunk)>spec.identity.size:self.stop('cap')
                    self.charge('input',len(chunk),self.limits.input_bytes);size+=len(chunk);hasher.update(chunk)
                    if spec.purpose=='git_config':
                        if size>len(p.CONFIG.encode()):self.stop('integrity')
                        config.append(chunk)
                elif stage==2 and k=='after':
                    descriptor,ident=v
                    if descriptor!=handle:self.stop('integrity')
                    self.validate_identity(ident,spec.identity)
                    if size!=spec.identity.size or hasher.hexdigest()!=spec.sha256:self.stop('integrity')
                    if spec.purpose=='git_config' and b''.join(config)!=p.CONFIG.encode():self.stop('integrity')
                    stage=4
                elif stage==4 and k=='entry':
                    self.metadata();self.validate_identity(v,spec.identity);stage=5
                elif stage==5 and k=='done':stage=6
                else:self.stop('integrity')
        if stage!=6:self.stop('incomplete')
        self.approved.add(spec.id)
        if spec.purpose=='root':
            if spec.path!=self.d['prep_root'] or spec.identity.type!='directory' or spec.identity.mode!=0o700:self.stop('integrity')
            if self.root is not None:self.stop('integrity')
            self.root=spec
        self.observations.append(p.SafeObservation('file',p.freeze({'id':spec.id,'purpose':spec.purpose,'equal':True,'digest':spec.sha256})))
    def revalidate(self,spec):
        stage=0
        with self.operation('files',self.limits.file_ms):
            for event in self.event_stream(self.files.revalidate(spec),4):
                if stage==0 and event.kind=='parents':
                    self.metadata(len(spec.parents))
                    if event.data!=spec.parents:self.stop('integrity')
                    stage=1
                elif stage==1 and event.kind==('absent' if spec.purpose=='git_absent' else 'entry'):
                    self.metadata()
                    if spec.purpose=='git_absent':
                        if event.data!='ENOENT':self.stop('integrity')
                    else:self.validate_identity(event.data,spec.identity)
                    stage=2
                elif stage==2 and event.kind=='done':stage=3
                else:self.stop('integrity')
        if stage!=3:self.stop('incomplete')
    def prerequisites(self,spec):
        d=self.d
        needed=[f for f in self.contract.files if f.path==spec.argv[0] and f.purpose=='tool']
        if len(needed)!=1:return None
        if spec.id=='python_version':
            runtime=[f for f in self.contract.files if f.purpose=='runtime']
            if not runtime:return None
            needed+=runtime
        if spec.argv[0]==d['docker_abs']:
            plugin=[f for f in self.contract.files if f.path==d['compose_plugin_abs'] and f.purpose=='plugin']
            if not plugin:return None
            needed+=plugin
        if spec.id.startswith('git_') or spec.id in ('compose_baseline','compose_effective'):
            if p.git_eligibility(self.contract):return None
            configs=[f for f in self.contract.files if f.purpose in ('git_config','git_absent')]
            required={d['checkout']+'/.git/config'}|set(d['git_provenance']['absent_paths'])
            if {f.path for f in configs}!=required:return None
            if any((f.purpose=='git_config')!=(f.path==d['checkout']+'/.git/config') for f in configs):return None
            needed+=configs
        if spec.id in ('compose_baseline','compose_effective'):
            required={'git_files','git_head','git_tree','git_status','git_remote','git_symbolic'}
            if not required<=self.seen:return None
            source=[f for f in self.contract.files if f.purpose=='source']
            if not source:return None
            needed+=source
        if spec.id=='compose_effective' and 'compose_baseline' not in self.seen:return None
        if any(f.id not in self.approved for f in needed):return None
        return tuple(dict.fromkeys(needed))
    def space(self):
        stage=0
        with self.operation('files',self.limits.file_ms):
            for event in self.event_stream(self.outputs.space(),3):
                if stage==0 and event.kind=='free':
                    if type(event.data) is not int:self.stop('integrity')
                    if event.data<self.limits.free_bytes:self.stop('storage')
                    stage=1
                elif stage==1 and event.kind=='done':stage=2
                else:self.stop('integrity')
        if stage!=2:self.stop('incomplete')
    def terminate(self):
        if self.child is None:return
        # Termination is the sole allowed post-stop port activity. It addresses
        # the exact opaque child returned by start, never an inferred process.
        for signal,limit in (('TERM',self.limits.term_ms),('KILL',self.limits.kill_ms)):
            acknowledged=False;began=self.clock.now();last=began
            try:
                for i,event in enumerate(self.commands.terminate(self.child,signal,limit)):
                    now=self.clock.now()
                    if type(now) is not int or now<last or now-began>=limit or i>1:break
                    last=now
                    if isinstance(event,Event) and event.kind=='ack':acknowledged=True;break
            except Exception:pass
            if acknowledged:break
        self.child=None
    def command(self,spec,needed):
        problem=p.check_command(spec,self.contract,self.seen)
        if problem:self.stop(problem.code)
        for f in needed:self.revalidate(f)
        self.space();began=self.boundary()
        self.seen.add(spec.id)
        stdout=[];hashes={'stdout':hashlib.sha256(),'stderr':hashlib.sha256()};eof=set();exitcode=None;total=0;done=False
        try:
            self.child,events=self.commands.start(spec)
            if self.child is None:self.stop('integrity')
            for event in self.event_stream(events,self.limits.command_bytes+8):
                if self.last-began>=min(spec.deadline_ms,self.limits.source_command_ms if spec.deadline_ms==30000 else self.limits.command_ms):self.stop('deadline')
                k,v=event.kind,event.data
                if k in ('stdout','stderr'):
                    if k in eof or type(v) is not bytes or not v:self.stop('integrity')
                    if len(v)>self.limits.chunk_bytes or total+len(v)>self.limits.command_bytes:self.stop('cap')
                    self.charge('capture',len(v),self.limits.capture_bytes);total+=len(v);hashes[k].update(v)
                    if k=='stdout':stdout.append(v)
                elif k=='eof':
                    if v not in ('stdout','stderr') or v in eof:self.stop('integrity')
                    eof.add(v)
                elif k=='exit':
                    if type(v) is not int or exitcode is not None:self.stop('integrity')
                    exitcode=v
                elif k=='done':
                    if eof!={'stdout','stderr'} or exitcode is None:self.stop('incomplete')
                    done=True
                else:self.stop('integrity')
            if not done:self.stop('incomplete')
            if self.last-began>=min(spec.deadline_ms,self.limits.source_command_ms if spec.deadline_ms==30000 else self.limits.command_ms):self.stop('deadline')
            self.child=None
            # Complete stream digests require both EOFs and a complete event
            # sequence. A nonzero exit is still a complete but unusable capture.
            self.captures.append(Capture(hashes['stdout'].hexdigest(),hashes['stderr'].hexdigest(),True))
            if exitcode!=(1 if spec.id=='git_symbolic' else 0):self.stop('command_failed')
            for f in needed:self.revalidate(f)
            with self.operation('json',self.limits.operation_ms):
                raw=b''.join(stdout)
                if spec.id in ('compose_version','context_inspect','daemon_version','daemon_info','image_runner','image_postgres','image_nats','image_minio','compose_baseline','compose_effective'):
                    value=p.parse_bounded_json(stdout,self)
                    if isinstance(value,p.Problem):self.stop(value.code)
                else:
                    try:value=raw.decode('utf-8','strict')
                    except UnicodeError:self.stop('invalid_json')
            with self.operation('json',self.limits.operation_ms):
                observation=p.project(spec.id,value,self.contract)
                if isinstance(observation,p.Problem):self.stop(observation.code)
                self.observations.append(observation)
            if spec.id=='compose_baseline':
                if self.root is None:self.stop('missing_prerequisite')
                self.output('effective.json',self.serialize(p.effective_model(self.contract)))
        except Exception:
            if not done:self.captures.append(Capture(hashes['stdout'].hexdigest(),hashes['stderr'].hexdigest(),False))
            raise
    def inventory(self):
        stage=0
        with self.operation('files',self.limits.file_ms):
            for event in self.event_stream(self.outputs.inventory(),3):
                if stage==0 and event.kind=='existing':
                    names=event.data
                    if not isinstance(names,tuple) or len(names)!=len(set(names)):self.stop('integrity')
                    for name in names:
                        if name not in p.OUTPUT_NAMES or self.d['output_owners'][name]!='operator' or name not in ('owner-contract.json','dispatch.json'):self.stop('collision')
                    self.existing=names;stage=1
                elif stage==1 and event.kind=='done':stage=2
                else:self.stop('integrity')
        if stage!=2:self.stop('incomplete')
    def serialize(self,value):
        # Only caller-created, closed projections reach this routine. The same
        # parser applies output node/string/depth limits before port invocation.
        with self.operation('json',self.limits.operation_ms):
            body=p.serialize_bounded(value,self)
            if isinstance(body,p.Problem):self.stop(body.code)
            return body
    def output(self,name,body):
        if name not in p.OUTPUT_NAMES or name in self.finalized or name=='independent-review.md':self.stop('integrity')
        if type(body) is not bytes or len(body)>self.limits.document_bytes:self.stop('cap')
        self.charge('output',len(body),self.limits.output_bytes)
        self.space();self.revalidate(self.root)
        owner=self.d['output_owners'][name]
        if owner!='collector' and (owner!='operator' or name not in self.existing):self.stop('missing_prerequisite')
        stage=0;opened=None;final=None
        with self.operation('writes',self.limits.writes_ms):
            prior=self.last
            events=self.outputs.finalize_existing(name,body,owner) if name in self.existing else self.outputs.create(name,body,owner,0o600,True)
            for event in self.event_stream(events,8):
                if self.last-prior>=self.limits.write_ms:self.stop('deadline')
                prior=self.last
                k,v=event.kind,event.data
                if stage==0 and k=='opened':
                    if not isinstance(v,p.Identity) or v.type!='regular' or v.uid!=self.root.identity.uid or v.gid!=self.root.identity.gid or v.dev!=self.root.identity.dev or v.parent!=self.root.id or v.mode!=0o600 or v.nlink!=1 or v.size!=(len(body) if name in self.existing else 0):self.stop('integrity')
                    opened=v;stage=1
                elif stage==1 and k==('read' if name in self.existing else 'written'):
                    if v!=(body if name in self.existing else len(body)):self.stop('storage')
                    stage=2
                elif stage==2 and k=='flushed':stage=3
                elif stage==3 and k=='synced':stage=4
                elif stage==4 and k=='identity':
                    expected=replace(opened,size=len(body))
                    self.validate_identity(v,expected);final=v;stage=5
                elif stage==5 and k=='done':stage=6
                else:self.stop('integrity')
        if stage!=6:self.stop('incomplete')
        self.finalized[name]=(p.digest(body),final)
    def payloads(self):
        markers={'trusted':False,'runtime_accepted':False,'host_observed':False,'evidence_kind':'synthetic','release_state':'unverified','accepted_case_credit':0}
        binding={'attempt':self.d['token'],'checkpoint':p.CHECKPOINT,**markers}
        payloads={'owner-contract.json':binding,'dispatch.json':binding,
                  'command-manifest.json':{'commands':[s.id for s in self.contract.commands],**markers},
                  'source-pins.json':{'candidate':p.CANDIDATE,'tree':p.TREE,**markers},
                  'classification.json':{'classification':self.classification,'missing_created_container_shape':True,
                        'problems':[{'code':v.code,'count':v.count} for v in self.problems],**markers},
                  'command-receipts.json':{'captures':[{'stdout_digest':v.stdout_digest,'stderr_digest':v.stderr_digest,'complete':v.complete} for v in self.captures],**markers}}
        groups={'file':'file-observations.json','python_version':'tool-observations.json','git_version':'tool-observations.json',
                'docker_version':'tool-observations.json','compose_version':'tool-observations.json'}
        grouped={}
        for obs in self.observations:
            if obs.kind in ('compose_baseline','compose_effective'):
                model=p.thaw(obs.data)['model'];payloads['compose-baseline.json' if obs.kind=='compose_baseline' else 'compose-effective.json']=model
                if obs.kind=='compose_baseline':payloads['effective.json']=p.effective_model(self.contract)
                continue
            name=groups.get(obs.kind,'image-observations.json' if obs.kind.startswith('image_') else
                'inventory-observations.json' if obs.kind.startswith(('inventory_','git_')) else 'daemon-observations.json')
            grouped.setdefault(name,[]).append({'kind':obs.kind,'data':p.thaw(obs.data)})
        for name,items in grouped.items():payloads[name]={'observations':items,**markers}
        return payloads
    def finalize(self):
        if self.root is None:self.stop('missing_prerequisite')
        payloads=self.payloads()
        for name in sorted(payloads):
            body=self.serialize(payloads[name])
            if name in self.finalized:
                if self.finalized[name][0]!=p.digest(body):self.stop('integrity')
            else:self.output(name,body)
        present=tuple(sorted(self.finalized))
        absent=[name for name in p.OUTPUT_NAMES if name not in present and name not in ('REPORT.md','SHA256SUMS')]
        report=('Synthetic R3 preparation report\n'+self.classification+'\n'
                'trusted:false runtime_accepted:false host_observed:false evidence_kind:synthetic release:unverified credit:0\n'
                'completion_requires_validated_SHA256SUMS_and_final_receipt\n'+
                ''.join('present '+n+'\n' for n in present)+
                ''.join('absent '+n+' '+('reviewer_owned' if n=='independent-review.md' else 'blocked_missing_input')+'\n' for n in absent)).encode()
        self.output('REPORT.md',report)
        covered=tuple(sorted(self.finalized))
        sums=''.join(self.finalized[n][0]+'  '+n+'\n' for n in covered).encode()
        self.output('SHA256SUMS',sums)
        expected=tuple((n,*self.finalized[n]) for n in sorted(self.finalized));index=0
        with self.operation('files',self.limits.file_ms):
            for event in self.event_stream(self.outputs.verify(expected),len(expected)+2):
                if event.kind=='verified' and index<len(expected):
                    if event.data!=expected[index]:self.stop('integrity')
                    index+=1
                elif event.kind=='done' and index==len(expected):pass
                else:self.stop('integrity')
        # Re-enumerate exact output names after verifying hashes to detect an
        # added file as well as a changed/missing finalized payload.
        stage=0
        with self.operation('files',self.limits.file_ms):
            for event in self.event_stream(self.outputs.inventory(),3):
                if stage==0 and event.kind=='existing':
                    if set(event.data)!=set(self.finalized) or len(event.data)!=len(self.finalized):self.stop('integrity')
                    stage=1
                elif stage==1 and event.kind=='done':stage=2
                else:self.stop('integrity')
        if stage!=2:self.stop('incomplete')
        self.boundary()
        return p.Receipt(p.digest(sums),covered,self.d['token'],p.CHECKPOINT)
    def run(self):
        self.boundary();self.states.append('FILE_ELIGIBLE')
        for spec in self.contract.files:self.boundary();self.observe(spec)
        if self.root is not None:self.inventory()
        self.states.append('COMMAND_ELIGIBLE')
        for spec in self.contract.commands:
            self.boundary();needed=self.prerequisites(spec)
            if needed is None:
                if p.Problem('missing_prerequisite') not in self.problems:self.problems.append(p.Problem('missing_prerequisite'))
                continue
            self.command(spec,needed)
        self.states.append('PROJECTED');receipt=self.finalize();self.states.append('COMPLETE')
        return self.result('COMPLETE',receipt)
    def result(self,status,receipt=None):
        return CollectionResult(status,tuple(self.states),tuple(self.problems),tuple(self.observations),tuple(self.captures),receipt,self.classification)

def collect(contract,files,commands,outputs,clock,cancel):
    """Consume injected scripted ports. Never creates a production transport.

    Admission is repeated to reject fabricated/mutated dataclass instances.
    Smaller limits support synthetic boundary tests; no limit may be widened.
    Missing dependent prerequisites skip that observation. Every integrity,
    capture, cancellation or finalization failure latches the entire attempt.
    """
    if not isinstance(contract,p.Contract):return CollectionResult('BLOCKED',('NEW','BLOCKED'),(p.Problem('invalid_contract'),))
    try:
        admitted=p.admit_contract(p.encode(contract.data))
        if isinstance(admitted,p.Problem) or replace(contract,limits=p.Limits())!=admitted:
            return CollectionResult('BLOCKED',('NEW','BLOCKED'),(p.Problem('invalid_contract'),))
        if any(type(v) is not int or v<0 or v>getattr(p.Limits(),k) for k,v in vars(contract.limits).items()):
            return CollectionResult('BLOCKED',('NEW','BLOCKED'),(p.Problem('invalid_contract'),))
        now=clock.now();d=p.values(contract)
        if type(now) is not int or not d['issued_tick']<=now<d['expires_tick']:
            return CollectionResult('BLOCKED',('NEW','BLOCKED'),(p.Problem('expired_dispatch'),))
        attempt=_Attempt(contract,files,commands,outputs,clock,cancel)
    except Exception:return CollectionResult('BLOCKED',('NEW','BLOCKED'),(p.Problem('invalid_contract'),))
    try:return attempt.run()
    except _Stop:
        attempt.terminate();attempt.states.append('INCOMPLETE');return attempt.result('INCOMPLETE')
    except Exception:
        # Deliberately discard exception text and arbitrary port error payloads.
        attempt.problems.append(p.Problem('port_failure'));attempt.terminate()
        attempt.states.append('INCOMPLETE');return attempt.result('INCOMPLETE')
