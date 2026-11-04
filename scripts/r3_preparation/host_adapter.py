"""Library-only preparation orchestration; there is no host observation entrypoint.

A later separately reviewed embedding must authenticate ApprovalBundle, anchor
handoff, containment and the independent startup/controller watchdog. Synchronous
PR241 Popen and uninterruptible kernel calls have no guaranteed local return.
"""
from dataclasses import dataclass, fields
import hashlib
import codecs
import selectors
import threading
import time
from . import policy as p
from . import real_admission as a
from . import file_transport as f
from . import process_transport as transport

FINALIZATION_STATES=('OBSERVED','SNAPSHOT_WRITTEN','REPORT_WRITTEN','CHECKSUMS_WRITTEN',
                     'ARTIFACTS_VERIFIED','WORKER_RETIRED','MONITOR_RETIRED','FINAL_RETURN')
_AUTHORITIES=('fixture_verified','product_candidate_verified','staging_verified','deployment_authorized',
              'cutover_verified','implementation_authorized','runtime_execution_authorized',
              'profile_promotion_authorized','merge_authorized')
_SECOND=10**9


@dataclass(frozen=True, slots=True)
class StreamDigest:
    stream: str
    sha256: str
    bytes: int
    complete: bool


@dataclass(frozen=True, slots=True)
class CommandCleanup:
    command_id: str
    status: str
    primary_fault: str | None
    returncode: int | None
    cleanup: str
    elapsed_ns: int
    retained_bytes: int
    stream_digest: tuple
    complete: bool


@dataclass(frozen=True, slots=True)
class CleanupRecord:
    schema_version: int
    record_stage: str
    attempt_token: str
    outer_deadline_ns: int
    primary_fault: str | None
    commands_started_count: int
    command_cleanup: tuple
    file_worker_started: bool
    file_worker_cleanup: str
    capture_descriptors_closed: bool
    worker_ipc_closed: bool
    monitor_stopped: bool
    scope_termination_attestation_ref: str | None
    cleanup_status: str
    quarantine_required: bool
    final_receipt_issued: bool


@dataclass(frozen=True, slots=True)
class Observation:
    command_id: str
    data: bytes
    evidence_kind: str = 'preparation_observation'


@dataclass(frozen=True, slots=True)
class FinalReceipt:
    record_stage: str
    attempt_token: str
    checkpoint: str
    artifact_binding: tuple
    covered_names: tuple
    evidence_kind: str = 'preparation_observation'
    host_observed: bool = False
    accepted_case_credit: int = 0


@dataclass(frozen=True, slots=True)
class PreparationResult:
    record_stage: str
    status: str
    classification: str
    problem: str | None
    observations: tuple
    commands: tuple
    cleanup: CleanupRecord
    receipt: FinalReceipt | None
    authorities: tuple = tuple((n,False) for n in _AUTHORITIES)
    evidence_kind: str = 'preparation_observation'
    trusted: bool = False
    runtime_accepted: bool = False
    host_observed: bool = False
    accepted_case_credit: int = 0
    authority: bool = False
    profiles_enabled: bool = False
    enabled_tiers: tuple = ()
    runtime_lock: None = None
    run_record: None = None
    release_state: str = 'unverified'


def _data(value):
    if type(value) in (CleanupRecord,CommandCleanup,StreamDigest):
        return {field.name:_data(getattr(value,field.name)) for field in fields(value)}
    if type(value) is tuple:return [_data(v) for v in value]
    return value


class _Monitor:
    def __init__(self,fd,cancel,outer):
        self.fd=fd;self.cancel=cancel;self.outer=outer;self.stop=threading.Event()
        self.thread=threading.Thread(target=self._watch,name='r3-owner-cancellation',daemon=True)
        self.thread.start()

    def _watch(self):
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self.fd,selectors.EVENT_READ)
                while not self.stop.is_set():
                    if time.monotonic_ns()>=self.outer or selector.select(.05):
                        self.cancel.set();return
        except BaseException:self.cancel.set()

    def retire(self):
        self.stop.set();self.thread.join(.1)
        return not self.thread.is_alive()


def _owner_cancelled(fd):
    # Readiness includes EOF. Never consume, reopen or change the owner's FD.
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(fd,selectors.EVENT_READ)
            return bool(selector.select(0))
    except (OSError,ValueError):return True


class _Fault(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)


class _Attempt:
    def __init__(self,contract,cancel_fd,deadline):
        self.contract=contract;self.cancel_fd=cancel_fd;self.deadline=deadline
        self.cancel=threading.Event();self.json=a.JsonBudget(deadline,self.cancel)
        self.fault=None;self.worker=None;self.worker_started=False;self.failed_worker_ipc_closed=True
        self.monitor=None;self.worker_cleanup='not_started'
        self.monitor_stopped=True;self.monitor_retirement_attempted=False;self.commands=[];self.observations=[];self.binding=()
        self.quarantine=False;self.missing=False;self.d=None;self.outputs={};self.file_observations={}

    def fail(self,code):
        if self.fault is None:self.fault=code if code in ('cancel','deadline','cap','storage','integrity','port_failure') else 'integrity'
        self.cancel.set();raise _Fault(self.fault)

    def check(self):
        if self.fault:raise _Fault(self.fault)
        if self.cancel.is_set():self.fail('cancel')
        if time.monotonic_ns()>=self.deadline:self.fail('deadline')
        self.json.check_json()

    def safe(self,value):
        self.check();return a.serialize(value,self.json)

    def write(self,name,raw):
        self.check();self.worker.space();self.check()
        result=self.worker.create_output(name,raw);self.check()
        if (type(result) is not dict or set(result)!={'sha256','size','complete'} or
            result['sha256']!=hashlib.sha256(raw).hexdigest() or type(result['size']) is not int or
            result['size']!=len(raw) or result['complete'] is not True):self.fail('integrity')
        self.outputs[name]=result['sha256']

    def revalidate(self,command):
        ids=set()
        for requirement in command.prerequisites:
            self.check()
            if requirement in self.d['prerequisites']:
                ids.update(self.d['prerequisites'][requirement])
        for reference in sorted(ids):
            self.check();result=self.worker.observe(reference);self.check()
            if result=={'blocked_missing_input':True}:return False
            if type(result) is not dict:self.fail('integrity')
            self.file_observations[reference]=result
        return True

    def cleanup_record(self,stage,issued=False):
        started=self.worker_started
        pending=stage=='pre_finalization_snapshot'
        command_closed=all(c.cleanup=='reaped' for c in self.commands)
        uncertain=self.quarantine or (started and self.worker_cleanup=='unconfirmed') or not command_closed
        ipc_closed=self.worker.ipc_closed if self.worker is not None else self.failed_worker_ipc_closed
        return CleanupRecord(1,stage,self.d['token'] if self.d else 'withheld',self.deadline,self.fault,
            len(self.commands),tuple(self.commands),started,'pending' if pending and started else self.worker_cleanup,
            command_closed,False if pending else ipc_closed,False if pending else self.monitor_stopped,
            None,'pending' if pending else 'unconfirmed' if uncertain else 'confirmed_local' if started else 'not_started',
            uncertain,issued)

    def retire_worker(self):
        if self.worker is not None and self.worker_cleanup=='pending':
            self.worker_cleanup=self.worker.close()
            if self.worker_cleanup!='reaped':self.worker_cleanup='unconfirmed';self.quarantine=True;self.fail('port_failure')

    def retire_monitor(self):
        if self.monitor is not None:
            self.monitor_retirement_attempted=True
            self.monitor_stopped=self.monitor.retire()
            if not self.monitor_stopped:self.quarantine=True;self.fail('port_failure')

    def cleanup(self):
        # Each owned lifecycle has one idempotent retirement allowance. A failed
        # retirement is never retried with a fresh grace period.
        if self.worker is not None and self.worker_cleanup=='pending':
            try:self.worker_cleanup=self.worker.close()
            except BaseException:self.worker_cleanup='unconfirmed'
            if self.worker_cleanup!='reaped':self.worker_cleanup='unconfirmed';self.quarantine=True
        if self.monitor is not None and not self.monitor_stopped and not self.monitor_retirement_attempted:
            self.monitor_retirement_attempted=True
            try:self.monitor_stopped=self.monitor.retire()
            except BaseException:self.monitor_stopped=False
            if not self.monitor_stopped:self.quarantine=True


def _capture(result,command,budget):
    if type(result) is not transport.RunResult:raise _Fault('port_failure')
    if (type(result.status) is not str or result.status not in ('completed','cancelled','deadline','capture_limit',
            'capture_failed','spawn_failed','cleanup_unconfirmed','invalid_request','unsupported_platform','budget_stopped','busy','output_limit') or
        type(result.stdout) is not bytes or type(result.stderr) is not bytes or
        type(result.captured_bytes) is not int or result.captured_bytes!=len(result.stdout)+len(result.stderr) or
        result.captured_bytes>16*1024**2 or type(result.elapsed_ns) is not int or result.elapsed_ns<0 or
        result.cleanup not in ('reaped','unconfirmed','not_started') or
        (result.returncode is not None and type(result.returncode) is not int)):
        raise _Fault('port_failure')
    complete=result.status=='completed' and result.cleanup=='reaped' and result.primary_fault is None
    streams=[]
    for name,raw in (('stdout',result.stdout),('stderr',result.stderr)):
        digest=hashlib.sha256()
        for offset in range(0,len(raw),65536):
            budget.check_json();digest.update(raw[offset:offset+65536])
        streams.append(StreamDigest(name,digest.hexdigest(),len(raw),complete))
    primary={'cancelled':'cancel','output_limit':'cap','capture_failed':'port_failure','spawn_failed':'port_failure'}.get(result.primary_fault,result.primary_fault)
    if result.status=='budget_stopped' and primary is None:primary='cap'
    if primary not in (None,'cancel','deadline','cap','storage','integrity','port_failure'):
        primary='port_failure'
    return CommandCleanup(command.id,result.status,primary,result.returncode,result.cleanup,
                           result.elapsed_ns,result.captured_bytes,tuple(streams),complete)


_JSON_COMMANDS=frozenset(('compose_version','context_inspect','daemon_version','daemon_info',
                         'image_runner','image_postgres','image_nats','image_minio','compose_baseline','compose_effective'))


def _projection(attempt,command,raw):
    with attempt.json.operation():
        if command.id in _JSON_COMMANDS:value=a._parse(raw,attempt.json)
        elif command.id=='git_files':value=raw
        else:
            decoder=codecs.getincrementaldecoder('utf-8')('strict');pieces=[]
            for offset in range(0,len(raw),65536):
                attempt.check();piece=decoder.decode(raw[offset:offset+65536]);pieces.append(piece)
            pieces.append(decoder.decode(b'',final=True));attempt.check();value=''.join(pieces)
        projected=a.project(command.id,value,attempt.contract,attempt.json)
        if isinstance(projected,p.Problem):attempt.fail('integrity')
        encoded=attempt.safe(projected)
        return Observation(command.id,encoded)


def _handoff(contract,anchors,cancel_fd,d):
    if type(anchors) is not tuple or type(cancel_fd) is not int or cancel_fd<3:return False
    if len(anchors)!=len(d['anchors']) or any(type(x) is not a.Anchor for x in anchors):return False
    specs={x['reference']:x for x in d['anchors']}
    if len({x.reference for x in anchors})!=len(anchors) or len({x.fd for x in anchors})!=len(anchors):return False
    for anchor in anchors:
        row=specs.get(anchor.reference)
        if (row is None or type(anchor.fd) is not int or anchor.fd<3 or anchor.fd==cancel_fd or
            type(anchor.identity) is not a.FileIdentity or anchor.identity!=a.FileIdentity(**row['identity'])):return False
    return True


def _finalize(attempt,checkpoint):
    w=attempt.worker;d=attempt.d
    def transition(state):
        attempt.check()
        if checkpoint is not None:checkpoint(state,attempt)
        attempt.check()
    transition('OBSERVED')
    grouped={o.command_id:a._parse(o.data,attempt.json) for o in attempt.observations}
    manifest=[dict(id=c.id,argv=list(c.argv),cwd=c.cwd,env=dict(c.env),kind=c.kind,
                   prerequisites=list(c.prerequisites)) for c in attempt.contract.commands]
    pending=attempt.cleanup_record('pre_finalization_snapshot')
    payloads={
        'command-manifest.json':manifest,
        'source-pins.json':dict(candidate=p.CANDIDATE,tree=p.TREE,tracked_manifest_sha256=d['tracked_manifest'],
                                checkpoint=a.CHECKPOINT,adapter_sha=d['adapter_sha']),
        'file-observations.json':attempt.file_observations,
        'tool-observations.json':{k:grouped[k] for k in p.COMMAND_IDS[:4]+p.COMMAND_IDS[8:11]},
        'daemon-observations.json':{k:grouped[k] for k in p.COMMAND_IDS[4:8]},
        'image-observations.json':{k:grouped[k] for k in p.COMMAND_IDS[11:15]},
        'inventory-observations.json':{k:grouped[k] for k in p.COMMAND_IDS[15:18]},
        'compose-baseline.json':grouped['compose_baseline'],
        'compose-effective.json':grouped['compose_effective'],
        'command-receipts.json':_data(pending),
        'classification.json':dict(record_stage='pre_finalization_snapshot',classification='preparation_finalization_pending',
            predicate_assessment='evidenced' if d['created_container_evidence'] else 'blocked_missing_input',final_receipt_issued=False)}
    for name,payload in payloads.items():attempt.write(name,attempt.safe(payload))
    transition('SNAPSHOT_WRITTEN')
    report=(b'# Preparation observation\n\npreparation_finalization_pending\n\n'
            b'These payloads are provisional until a separately returned final receipt '
            b'authenticates this exact SHA256SUMS digest. Worker cleanup and monitor retirement '
            b'are pending. No execution, acceptance or release authority is established.\n')
    attempt.write('REPORT.md',report);transition('REPORT_WRITTEN')
    covered=tuple(sorted(attempt.outputs))
    sums=b''.join((attempt.outputs[name]+'  '+name+'\n').encode('ascii') for name in covered)
    attempt.write('SHA256SUMS',sums)
    attempt.binding=tuple((name,attempt.outputs[name]) for name in ('SHA256SUMS','command-receipts.json','classification.json'))
    transition('CHECKSUMS_WRITTEN')
    # After this boundary there is no create/write/flush operation.
    expected=covered+('SHA256SUMS',)
    for name in expected:
        attempt.check()
        if name in p.OUTPUT_NAMES[:2]:
            recipe=next((r for r in attempt.contract.files if r.id==attempt.operator_files[name]),None)
            result=w.observe(recipe.id)
        else:result=w.verify_output(name)
        if result.get('sha256')!=attempt.outputs[name] or result.get('complete') is not True:attempt.fail('integrity')
    w.inventory_outputs(expected);transition('ARTIFACTS_VERIFIED')
    attempt.retire_worker();transition('WORKER_RETIRED')
    attempt.retire_monitor();transition('MONITOR_RETIRED')
    if _owner_cancelled(attempt.cancel_fd):attempt.fail('cancel')
    attempt.check();transition('FINAL_RETURN')
    return FinalReceipt('final_return',d['token'],a.CHECKPOINT,attempt.binding,covered)


def _collect(contract,anchors,cancel_fd,*,worker_type,runner,checkpoint=None,validate_handoff=False):
    now=time.monotonic_ns();expiry=contract.approvals.expires_ns if type(contract) is a.ActualContract and type(contract.approvals) is a.ApprovalBundle and type(contract.approvals.expires_ns) is int else now
    attempt=_Attempt(contract,cancel_fd,min(now+1800*_SECOND,expiry))
    receipt=None;classification='collection_blocked';problem='invalid_actual_contract'
    try:
        attempt.check()
        admitted=a._admit_actual(contract.document,contract.approvals,attempt.json)
        if type(admitted) is not a.ActualContract or type(contract) is not a.ActualContract or admitted!=contract:raise _Fault('integrity')
        attempt.d=a.values(admitted,attempt.json)
        if type(cancel_fd) is not int or cancel_fd<3 or (validate_handoff and not _handoff(contract,anchors,cancel_fd,attempt.d)):
            raise _Fault('integrity')
        if _owner_cancelled(cancel_fd):attempt.fail('cancel')
        # This is the adapter's only direct Python worker fork. It precedes the
        # monitor; subsequent required PR241 Popen calls remain unchanged.
        attempt.worker=worker_type(anchors,contract.files,'root',attempt.deadline,attempt.cancel,json_budget=attempt.json)
        attempt.worker_started=True;attempt.worker_cleanup='pending'
        attempt.monitor=_Monitor(cancel_fd,attempt.cancel,attempt.deadline);attempt.monitor_stopped=False
        attempt.check();attempt.worker.space()
        attempt.worker.inventory_outputs(p.OUTPUT_NAMES[:2])
        attempt.operator_files={}
        roots={row['reference']:row['path'] for row in attempt.d['anchors']}
        for name in p.OUTPUT_NAMES[:2]:
            recipe=next((r for r in contract.files if roots[r.anchor].rstrip('/')+'/'+ '/'.join(r.components)==attempt.d['prep_root']+'/'+name),None)
            if recipe is None:attempt.fail('integrity')
            result=attempt.worker.observe(recipe.id)
            if result.get('complete') is not True or result.get('sha256')!=recipe.sha256:attempt.fail('integrity')
            attempt.outputs[name]=recipe.sha256;attempt.operator_files[name]=recipe.id
        capture=transport.CaptureBudget(attempt.deadline,128*1024**2)
        completed=set();seen=set()
        for command in contract.commands:
            attempt.check()
            if command.id in seen:attempt.fail('integrity')
            seen.add(command.id)
            dependencies=[x for x in command.prerequisites if x in p.COMMAND_IDS or x=='effective_output']
            if not all(x in completed for x in dependencies):attempt.missing=True;continue
            if not attempt.revalidate(command):attempt.missing=True;continue
            attempt.worker.space();attempt.check()
            request=transport.RunRequest(command.id,command.argv[0],command.argv,command.cwd,command.env,command.kind)
            # Startup is synchronous and may stall before PR241 capture begins.
            # The external owner watchdog, not Event cancellation, covers it.
            result=runner(request,capture,attempt.cancel)
            with attempt.json.operation():record=_capture(result,command,attempt.json)
            attempt.commands.append(record)
            if record.cleanup=='unconfirmed':attempt.quarantine=True
            if not record.complete or record.returncode!=command.expected_returncode:
                attempt.fail(record.primary_fault or 'integrity')
            attempt.check()
            if not attempt.revalidate(command):attempt.fail('integrity')
            observation=_projection(attempt,command,result.stdout)
            result=None
            attempt.observations.append(observation);completed.add(command.id)
            if command.id=='compose_baseline':
                attempt.write('effective.json',attempt.safe(a.effective_model(contract,attempt.json)))
                completed.add('effective_output')
        if attempt.missing:raise _Fault('blocked_missing_input')
        receipt=_finalize(attempt,checkpoint)
        classification='preparation_compatible_pending_execution_gate' if attempt.d['created_container_evidence'] else 'preparation_complete_execution_blocked'
        problem=None
    except (_Fault,f.TransportFault,a.BudgetFault,a._Rejected,MemoryError,RecursionError,UnicodeError,TypeError,ValueError,KeyError,AttributeError,OSError) as error:
        if type(error) is f.WorkerStartupFault:
            outcome=error.outcome
            attempt.worker_started=outcome.file_worker_started
            attempt.worker_cleanup=outcome.file_worker_cleanup
            attempt.failed_worker_ipc_closed=outcome.worker_ipc_closed
            attempt.quarantine |= outcome.quarantine_required
        code=getattr(error,'code','port_failure')
        if code=='blocked_missing_input':attempt.missing=True;problem='blocked_missing_input'
        else:
            if attempt.fault is None:attempt.fault=code if code in ('cancel','deadline','cap','storage','integrity','port_failure') else 'port_failure'
            attempt.cancel.set();problem=attempt.fault
        classification='collection_incomplete' if attempt.commands or attempt.outputs or attempt.worker_started else 'collection_blocked'
        if attempt.missing:classification='collection_blocked'
    finally:attempt.cleanup()
    if receipt is not None and (attempt.fault or attempt.quarantine or not attempt.monitor_stopped or attempt.worker_cleanup!='reaped'):
        receipt=None;classification='collection_incomplete';problem=attempt.fault or 'port_failure'
    cleanup=attempt.cleanup_record('final_return',receipt is not None)
    return PreparationResult('final_return','complete' if receipt else 'blocked' if classification=='collection_blocked' else 'incomplete',
        classification,problem,tuple(attempt.observations),tuple(attempt.commands),cleanup,receipt)


def collect_preparation(contract,anchors,cancel_fd):
    """Fixed production binding. Requires separately authorized actual embedding."""
    return _collect(contract,anchors,cancel_fd,worker_type=f.FileWorker,runner=transport.run,validate_handoff=True)
