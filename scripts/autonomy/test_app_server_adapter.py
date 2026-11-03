"""Offline protocol fixtures and real bounded fake-process regressions."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import app_server_adapter as a
except ImportError:
    a = None

PROFILE = {"model": "gpt-6.1-sol", "reasoning_effort": "medium", "service_tier": "fast"}
ARGV = ["codex", "app-server", "--stdio", "--strict-config", "-c", 'model="gpt-6.1-sol"', "-c", 'model_reasoning_effort="medium"', "-c", 'service_tier="fast"', "-c", "features.fast_mode=true"]


def expected_context(cwd="/tmp/run/agents/architect/worktree"):
    return {"run_id": "run-architect", "task_id": "task", "agent_name": "autodata-architect",
            "evidence_label": "architect", "trusted_base_sha": "a"*40, "subject_sha": "a"*40,
            "cwd": cwd, "codex_home": "/tmp/codex-disposable", "prompt": "frozen prompt",
            "schema": {"type": "object"}}


def boundary(cwd):
    return {"version": 1, "purpose": "r0-disposable-provider", "network_policy": "standard-docker-bridge-unrestricted-outbound",
            "github_credentials_or_integrations": False, "bank_credentials_or_integrations": False,
            "production_credentials_or_integrations": False, "codex_auth_delivery": "authorized-readonly-file",
            "codex_auth_mount": "/tmp/codex-disposable/auth.json", "worktree_root": str(Path(cwd).parent),
            "output_root": str(Path(cwd).parent), "codex_home": "/tmp/codex-disposable",
            "namespaces": {"mnt": "mnt:[1]", "net": "net:[2]", "pid": "pid:[3]"}}


def exchange():
    e = expected_context()
    response = {"schema_version": 2, "assessments": []}
    records = []
    def add(direction, frame):
        records.append({"seq": len(records)+1, "direction": direction, "raw": json.dumps(frame)+"\n"})
    add("client", {"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "autodata-r0", "title": "AutoData R0", "version": "1"}, "capabilities": {"experimentalApi": False, "optOutNotificationMethods": []}}})
    add("server", {"id": 1, "result": {"userAgent": "codex/0.162.1", "codexHome": e["codex_home"], "platformFamily": "unix", "platformOs": "linux"}})
    add("client", {"method": "initialized"})
    add("client", {"id": 2, "method": "model/list", "params": {"cursor": None, "limit": 100, "includeHidden": True}})
    add("server", {"id": 2, "result": {"data": [{"id": "sol", "model": "gpt-6.1-sol", "supportedReasoningEfforts": [{"reasoningEffort": "medium", "description": "Medium"}], "serviceTiers": [{"id": "priority", "name": "Fast", "description": "Priority"}]}], "nextCursor": None}})
    add("client", {"id": 3, "method": "thread/start", "params": {"model": "gpt-6.1-sol", "modelProvider": "openai", "serviceTier": "priority", "cwd": e["cwd"], "approvalPolicy": "never", "sandbox": "danger-full-access", "ephemeral": True, "config": {"model_reasoning_effort": "medium", "features.fast_mode": True}}})
    add("server", {"method": "thread/started", "params": {"thread": {"id": "thread-1"}}})
    add("server", {"id": 3, "result": {"thread": {"id": "thread-1"}, "model": "gpt-6.1-sol", "modelProvider": "openai", "serviceTier": "priority", "reasoningEffort": "medium", "cwd": e["cwd"], "approvalPolicy": "never", "sandbox": {"type": "dangerFullAccess"}}})
    add("client", {"id": 4, "method": "turn/start", "params": {"threadId": "thread-1", "input": [{"type": "text", "text": e["prompt"], "text_elements": []}], "outputSchema": e["schema"]}})
    add("server", {"method": "turn/started", "params": {"threadId": "thread-1", "turn": {"id": "turn-1", "status": "inProgress", "error": None, "items": []}}})
    add("server", {"id": 4, "result": {"turn": {"id": "turn-1", "status": "inProgress", "error": None, "items": []}}})
    user = {"id": "u1", "type": "userMessage", "content": [{"type": "text", "text": e["prompt"], "text_elements": []}]}
    for method in ["item/started", "item/completed"]:
        add("server", {"method": method, "params": {"threadId": "thread-1", "turnId": "turn-1", "item": user, "completedAtMs": 1}})
    item = {"id": "answer", "type": "agentMessage", "phase": "final_answer", "text": json.dumps(response)}
    add("server", {"method": "item/completed", "params": {"threadId": "thread-1", "turnId": "turn-1", "item": item, "completedAtMs": 2}})
    add("server", {"method": "turn/completed", "params": {"threadId": "thread-1", "turn": {"id": "turn-1", "status": "completed", "error": None, "items": [user, item]}}})
    return records, e


def mutate(records, predicate, change):
    for r in records:
        frame = json.loads(r["raw"])
        if predicate(frame):
            change(frame)
            r["raw"] = json.dumps(frame)+"\n"
            return
    raise AssertionError("fixture frame absent")


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(a, "bounded app-server adapter has not been implemented")

    def test_configured_profile_and_actual_final_answer_with_interleaving(self):
        frames, expected = exchange()
        result = a.replay_protocol(frames, expected=expected)
        self.assertEqual(result["profile"], PROFILE)
        self.assertEqual(result["thread_id"], "thread-1")
        self.assertEqual(result["turn_id"], "turn-1")
        self.assertEqual(json.loads(result["response_text"]), {"schema_version": 2, "assessments": []})

    def test_missing_wrong_and_unsupported_resolved_settings_block(self):
        cases = [lambda x: x["result"].pop("reasoningEffort"),
                 lambda x: x["result"].update(model="other"),
                 lambda x: x["result"].update(serviceTier="fast"),
                 lambda x: x["result"].update(reasoningEffort=None),
                 lambda x: x["result"].update(modelProvider="other"),
                 lambda x: x["result"].update(cwd="/elsewhere")]
        for change in cases:
            with self.subTest(change=change):
                frames, expected = exchange()
                mutate(frames, lambda f: f.get("id")==3 and "result" in f, change)
                with self.assertRaises(a.ProtocolError): a.replay_protocol(frames, expected=expected)
        for field, value in [("serviceTiers", []), ("supportedReasoningEfforts", [])]:
            frames, expected = exchange()
            mutate(frames, lambda f: f.get("id")==2 and "result" in f,
                   lambda f: f["result"]["data"][0].update({field: value}))
            with self.assertRaises(a.ProtocolError): a.replay_protocol(frames, expected=expected)

    def test_forbidden_overrides_reroute_foreign_ids_and_incomplete_turn_block(self):
        for mutation in ["override", "reroute", "foreign", "interrupted", "missing", "duplicate", "user"]:
            with self.subTest(mutation=mutation):
                frames, expected = exchange()
                if mutation=="override":
                    mutate(frames, lambda f:f.get("method")=="turn/start", lambda f:f["params"].update(effort="high"))
                elif mutation=="reroute": frames.append({"seq":len(frames)+1,"direction":"server","raw":json.dumps({"method":"model/rerouted","params":{"threadId":"thread-1","turnId":"turn-1"}})+"\n"})
                elif mutation=="foreign": mutate(frames, lambda f:f.get("method")=="turn/completed", lambda f:f["params"].update(threadId="other"))
                elif mutation=="interrupted": mutate(frames, lambda f:f.get("method")=="turn/completed", lambda f:f["params"]["turn"].update(status="interrupted"))
                elif mutation=="missing": frames.pop()
                elif mutation=="duplicate": frames[-1]["raw"]='{"method":"turn/completed","method":"ignored"}\n'
                else: mutate(frames, lambda f:f.get("method")=="item/completed" and f["params"]["item"]["type"]=="userMessage", lambda f:f["params"]["item"]["content"][0].update(text="conflicting"))
                with self.assertRaises(a.ProtocolError): a.replay_protocol(frames, expected=expected)

    def test_scoped_events_require_prior_requests_and_cannot_follow_completion(self):
        for stage in ('before-thread', 'before-turn', 'after-completion'):
            for method in ('item/started', 'item/completed', 'item/agentMessage/delta',
                           'turn/started', 'turn/completed'):
                with self.subTest(stage=stage, method=method):
                    frames, expected = exchange()
                    if method == 'item/started':
                        event = next(x for x in frames if json.loads(x['raw']).get('method') == method)
                        frame = json.loads(event['raw'])
                    elif method == 'item/completed':
                        event = next(x for x in frames if json.loads(x['raw']).get('method') == method
                                     and json.loads(x['raw'])['params']['item']['type'] == 'agentMessage')
                        frames.remove(event)
                        frame = json.loads(event['raw'])
                    elif method == 'item/agentMessage/delta':
                        frame = {'method': method, 'params': {'threadId': 'thread-1', 'turnId': 'turn-1',
                                                             'itemId': 'answer', 'delta': 'text'}}
                    else:
                        event = next(x for x in frames if json.loads(x['raw']).get('method') == method)
                        if not (stage == 'after-completion' and method == 'turn/completed'):
                            frames.remove(event)
                        frame = json.loads(event['raw'])
                    event = {'direction': 'server', 'raw': json.dumps(frame)+'\n'}
                    if stage == 'after-completion':
                        frames.append(event)
                    else:
                        request = 'thread/start' if stage == 'before-thread' else 'turn/start'
                        index = next(i for i, x in enumerate(frames)
                                     if x['direction'] == 'client' and json.loads(x['raw']).get('method') == request)
                        frames.insert(index, event)
                    for index, record in enumerate(frames, 1):
                        record['seq'] = index
                    with self.assertRaises(a.ProtocolError):
                        a.replay_protocol(frames, expected=expected)

    def test_thread_notifications_cannot_precede_written_thread_request(self):
        for method in ('thread/status/changed', 'thread/tokenUsage/updated'):
            with self.subTest(method=method):
                frames, expected = exchange()
                event={'direction':'server','raw':json.dumps({'method':method,
                       'params':{'threadId':'thread-1'}})+'\n'}
                index=next(i for i,x in enumerate(frames) if x['direction']=='client'
                           and json.loads(x['raw']).get('method')=='thread/start')
                frames.insert(index,event)
                for index,record in enumerate(frames,1):record['seq']=index
                with self.assertRaises(a.ProtocolError):
                    a.replay_protocol(frames,expected=expected)

    def test_items_between_written_turn_request_and_response_remain_valid(self):
        frames, expected = exchange()
        event = next(x for x in frames if json.loads(x['raw']).get('method') == 'item/completed'
                     and json.loads(x['raw'])['params']['item']['type'] == 'agentMessage')
        frames.remove(event)
        index = next(i for i, x in enumerate(frames) if x['direction'] == 'client'
                     and json.loads(x['raw']).get('method') == 'turn/start')
        frames.insert(index+1, event)
        for index, record in enumerate(frames, 1):
            record['seq'] = index
        self.assertTrue(a.replay_protocol(frames, expected=expected)['completed'])

    def test_catalog_requires_exhaustion_and_rejects_ambiguous_models(self):
        for mode in ["cursor", "duplicate", "same-model"]:
            frames, expected = exchange()
            def change(f):
                if mode=="cursor": f["result"]["nextCursor"]="more"
                else:
                    model=copy.deepcopy(f["result"]["data"][0]);model["id"]="second" if mode=="same-model" else "sol";f["result"]["data"].append(model)
            mutate(frames, lambda f:f.get("id")==2 and "result" in f, change)
            with self.assertRaises(a.ProtocolError): a.replay_protocol(frames, expected=expected)

    def test_prose_deltas_and_ambiguous_final_messages_are_not_response_metadata(self):
        frames, expected=exchange()
        mutate(frames, lambda f:f.get("method")=="item/completed" and f["params"]["item"]["type"]=="agentMessage", lambda f:f["params"]["item"].update(text='{"schema_version":2,"schema_version":1}'))
        with self.assertRaises(a.ProtocolError):a.replay_protocol(frames,expected=expected)



FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time
from pathlib import Path
if '--version' in sys.argv:
    print('codex-cli 0.162.0' if os.environ.get('FAKE_CODEX_MODE')=='bad-version' else 'codex-cli 0.162.1');sys.exit(0)
mode=os.environ.get('FAKE_CODEX_MODE','success')
if mode=='unavailable-security': mode='unavailable' if Path.cwd().parent.name=='security' else 'success'
def send(x):
    print(json.dumps(x),flush=True)
def answer(i,r): send({'id':i,'result':r})
thread='thread-1';turn='turn-1';home=os.environ.get('CODEX_HOME','/tmp/codex-disposable')
for line in sys.stdin:
    f=json.loads(line);method=f.get('method');i=f.get('id');p=f.get('params',{})
    if method=='initialize':
        assert p=={'clientInfo':{'name':'autodata-r0','title':'AutoData R0','version':'1'},'capabilities':{'experimentalApi':False,'optOutNotificationMethods':[]}}
        if mode=='flood':
            sys.stdout.write('x'*(2*1024*1024));sys.stdout.flush();time.sleep(30)
        if mode=='stderr-flood':
            sys.stderr.write('x'*(6*1024*1024));sys.stderr.flush();time.sleep(30)
        if mode=='stall': time.sleep(30)
        if mode=='descendant':
            child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
            if os.environ.get('FAKE_CHILD_PID_FILE'):Path(os.environ['FAKE_CHILD_PID_FILE']).write_text(str(child.pid))
            sys.exit(0)
        answer(i,{'userAgent':'codex/0.162.1','codexHome':home,'platformFamily':'unix','platformOs':'linux'})
    elif method=='initialized': assert set(f)=={'method'}
    elif method=='model/list':
        assert p=={'cursor':None,'limit':100,'includeHidden':True}
        models=[{'id':'sol','model':'gpt-6.1-sol','supportedReasoningEfforts':[{'reasoningEffort':'medium','description':'Medium'}],'serviceTiers':[{'id':'priority','name':'Fast','description':'Priority'}]}]
        answer(i,{'data':[] if mode=='unavailable' else models,'nextCursor':None})
    elif method=='thread/start':
        assert p=={'model':'gpt-6.1-sol','modelProvider':'openai','serviceTier':'priority','cwd':os.getcwd(),'approvalPolicy':'never','sandbox':'danger-full-access','ephemeral':True,'config':{'model_reasoning_effort':'medium','features.fast_mode':True}}
        send({'method':'thread/started','params':{'thread':{'id':thread}}})
        answer(i,{'thread':{'id':thread},'model':'gpt-6.1-sol','modelProvider':'openai','serviceTier':'priority','reasoningEffort':'medium','cwd':os.getcwd(),'approvalPolicy':'never','sandbox':{'type':'dangerFullAccess'}})
        if mode=='blocked-stdin':time.sleep(30)
    elif method=='turn/start':
        assert set(p)=={'threadId','input','outputSchema'} and p['threadId']==thread
        assert p['input'][0]['text_elements']==[]
        prompt=p['input'][0]['text']
        answer(i,{'turn':{'id':turn,'status':'inProgress','error':None,'items':[]}})
        send({'method':'turn/started','params':{'threadId':thread,'turn':{'id':turn,'status':'inProgress','error':None,'items':[]}}})
        if mode=='interrupt': continue
        if mode=='approval':
            send({'id':100,'method':'item/commandExecution/requestApproval','params':{'threadId':thread,'turnId':turn,'itemId':'command'}});continue
        if 'FROZEN ENVELOPE:\n' in prompt:
            envelope=json.JSONDecoder().raw_decode(prompt.split('FROZEN ENVELOPE:\n',1)[1])[0]
            if envelope['agent_name']=='autodata-python-builder':
                Path('app.txt').write_text('after');subprocess.run(['git','add','app.txt'],check=True);subprocess.run(['git','commit','-m','fixture implementation'],stdout=sys.stderr,check=True)
            subject=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
            checks=[c for c in envelope['task_contract']['verification']['checks'] if c['gate']==envelope.get('gate')] if 'verification' in envelope['task_contract'] else []
            # Assignment is deliberately read from runner's explicit prompt, not inferred from all contract checks.
            assigned=json.JSONDecoder().raw_decode(prompt.split('ASSIGNED CHECK IDS:\n',1)[1])[0]
            response={'schema_version':2,'run_id':envelope['run_id'],'task_id':envelope['task_id'],'agent_name':envelope['agent_name'],'subject_sha':subject,'decision':'pass','summary':'offline fake server','task_contract':envelope['task_contract'] if envelope['agent_name']=='autodata-architect' else None,'findings':None if mode=='malformed' and envelope.get('gate')=='security' else [],'assessments':[{'check_id':c,'decision':'pass','evidence_ids':[c+':command'],'explanation':'assessed retained check'} for c in assigned],'evidence_ids':[]}
        else: response={'schema_version':2,'assessments':[]}
        user={'id':'user','type':'userMessage','content':p['input']}
        item={'id':'answer','type':'agentMessage','phase':'final_answer','text':json.dumps(response)}
        for m in ['item/started','item/completed']:send({'method':m,'params':{'threadId':thread,'turnId':turn,'item':user,'completedAtMs':1}})
        send({'method':'item/completed','params':{'threadId':thread,'turnId':turn,'item':item,'completedAtMs':2}})
        send({'method':'turn/completed','params':{'threadId':thread,'turn':{'id':turn,'status':'completed','error':None,'items':[user,item]}}})
        if mode=='nonzero':sys.exit(9)
    elif method=='turn/interrupt':
        answer(i,{});send({'method':'turn/completed','params':{'threadId':thread,'turn':{'id':turn,'status':'interrupted','error':None,'items':[]}}})
    elif 'result' in f:
        assert f=={'id':100,'result':{'decision':'cancel'}}
    else: raise AssertionError(f)
'''


def fake_codex(directory):
    bindir=directory/'fake-bin';bindir.mkdir()
    script=bindir/'codex';script.write_text(FAKE_CODEX.replace('#!/usr/bin/env python3','#!'+sys.executable));script.chmod(0o755)
    return bindir


class TransportTests(unittest.TestCase):
    def test_ordered_fake_process_and_raw_capture_replay(self):
        self.assertTrue(a is not None and hasattr(a,'run_app_server'), 'bounded transport missing')
        with tempfile.TemporaryDirectory() as d:
            cwd=Path(d);bindir=fake_codex(cwd);e=expected_context(str(cwd))
            env={**os.environ,'PATH':str(bindir)+os.pathsep+os.environ['PATH'],'CODEX_HOME':e['codex_home']}
            with patch.object(a,'validate_boundary',return_value=boundary(cwd)):
                result=a.run_app_server(argv=ARGV,cwd=cwd,env=env,prompt=e['prompt'],schema=e['schema'],expected=e,boundary_proof=a.BOUNDARY,timeout_seconds=6)
            self.assertEqual((result['status'],result['exit_code']),('completed',0),result)
            replay=a.replay_capture(result['protocol'],stdout=result['stdout'],expected=e)
            self.assertEqual(replay['profile'],PROFILE)
            self.assertEqual(json.loads(result['response']),{'schema_version':2,'assessments':[]})
            captured=[json.loads(x) for x in result['protocol'].splitlines()]
            outbound=[json.loads(x['raw']).get('method') for x in captured[1:-1] if x['direction']=='client']
            self.assertEqual(outbound,['initialize','initialized','model/list','thread/start','turn/start'])
            with self.assertRaises(a.ProtocolError):a.replay_capture(result['protocol'],stdout=result['stdout']+b'{}\n',expected=e)

    def test_unavailable_profile_never_starts_thread_or_turn(self):
        self.assertTrue(a is not None and hasattr(a,'run_app_server'),'bounded transport missing')
        with tempfile.TemporaryDirectory() as d:
            cwd=Path(d);bindir=fake_codex(cwd);e=expected_context(str(cwd));env={**os.environ,'PATH':str(bindir)+os.pathsep+os.environ['PATH'],'CODEX_HOME':e['codex_home'],'FAKE_CODEX_MODE':'unavailable'}
            with patch.object(a,'validate_boundary',return_value=boundary(cwd)):
                result=a.run_app_server(argv=ARGV,cwd=cwd,env=env,prompt=e['prompt'],schema=e['schema'],expected=e,boundary_proof=a.BOUNDARY,timeout_seconds=5)
            self.assertNotEqual(result['status'],'completed')
            frames=[json.loads(x) for x in result['protocol'].splitlines()][1:-1]
            methods=[json.loads(x['raw']).get('method') for x in frames if x['direction']=='client']
            self.assertEqual(methods,['initialize','initialized','model/list'])

    def test_failure_bounds_approval_and_interrupt_are_not_success(self):
        self.assertTrue(a is not None and hasattr(a,'run_app_server'),'bounded transport missing')
        with tempfile.TemporaryDirectory() as d:
            cwd=Path(d);bindir=fake_codex(cwd);e=expected_context(str(cwd))
            for mode in ['nonzero','flood','stderr-flood','stall','descendant','approval','interrupt','bad-version','blocked-stdin']:
                with self.subTest(mode=mode):
                    env={**os.environ,'PATH':str(bindir)+os.pathsep+os.environ['PATH'],'CODEX_HOME':e['codex_home'],'FAKE_CODEX_MODE':mode,'FAKE_CHILD_PID_FILE':str(cwd/'child-pid')}
                    e['prompt']='x'*500000 if mode=='blocked-stdin' else 'frozen prompt'
                    started=time.monotonic()
                    with patch.object(a,'validate_boundary',return_value=boundary(cwd)):
                        result=a.run_app_server(argv=ARGV,cwd=cwd,env=env,prompt=e['prompt'],schema=e['schema'],expected=e,boundary_proof=a.BOUNDARY,timeout_seconds=4)
                    self.assertLess(time.monotonic()-started,5)
                    self.assertNotEqual(result['status'],'completed')
                    self.assertLessEqual(len(result['stdout']),4*1024*1024)
                    self.assertLessEqual(len(result['stderr']),4*1024*1024)
                    if mode in ['flood','stderr-flood']:self.assertTrue(result['output_budget_exhausted'])
                    if mode=='descendant':
                        pid=int((cwd/'child-pid').read_text())
                        statfile=Path('/proc')/str(pid)/'stat'
                        # SIGKILL delivery is asynchronous even after the group leader exits.
                        until=time.monotonic()+0.5
                        while statfile.exists() and statfile.read_text().split()[2]!='Z' and time.monotonic()<until:
                            time.sleep(0.01)
                        self.assertTrue(not statfile.exists() or statfile.read_text().split()[2]=='Z')
                    if mode in ['approval','interrupt']:
                        frames=[json.loads(x) for x in result['protocol'].splitlines()][1:-1]
                        self.assertTrue(any(x.get('direction')=='client' and json.loads(x['raw']).get('method')=='turn/interrupt' for x in frames))
                    if mode=='interrupt':
                        self.assertTrue(any(x.get('direction')=='server' and json.loads(x['raw']).get('method')=='turn/completed' and json.loads(x['raw'])['params']['turn']['status']=='interrupted' for x in frames),'actual interrupt receipt missing')
                    if mode=='approval':
                        self.assertTrue(any(x.get('direction')=='client' and json.loads(x['raw'])=={'id':100,'result':{'decision':'cancel'}} for x in frames))

    def test_boundary_failure_does_not_spawn_any_process(self):
        self.assertTrue(a is not None and hasattr(a,'run_app_server'),'bounded transport missing')
        with patch.object(a.subprocess,'Popen',side_effect=AssertionError('provider must not start')):
            with self.assertRaises(a.ProtocolError):
                a.run_app_server(argv=ARGV,cwd=Path('/tmp'),env={},prompt='',schema={},expected=expected_context(),boundary_proof=Path('/tmp/no-runtime-proof'),timeout_seconds=5)

class StrictScopeTests(unittest.TestCase):
    def test_boolean_request_id_and_missing_item_scope_are_rejected(self):
        for mode in ['boolean-id','missing-thread','missing-turn']:
            frames,e=exchange()
            if mode=='boolean-id':
                mutate(frames,lambda f:f.get('method')=='initialize',lambda f:f.update(id=True))
            else:
                mutate(frames,lambda f:f.get('method')=='item/completed',lambda f:f['params'].pop('threadId' if mode=='missing-thread' else 'turnId'))
            with self.subTest(mode=mode),self.assertRaises(a.ProtocolError):a.replay_protocol(frames,expected=e)

    def test_catalog_pagination_follows_actual_cursor_then_exhausts(self):
        frames,e=exchange()
        first=frames[4]
        frame=json.loads(first['raw']);frame['result']['nextCursor']='page-2';frame['result']['data']=[];first['raw']=json.dumps(frame)+'\n'
        page={'seq':6,'direction':'client','raw':json.dumps({'id':3,'method':'model/list','params':{'cursor':'page-2','limit':100,'includeHidden':True}})+'\n'}
        models=json.loads(exchange()[0][4]['raw'])['result']
        response={'seq':7,'direction':'server','raw':json.dumps({'id':3,'result':models})+'\n'}
        tail=frames[5:]
        for r in tail:
            f=json.loads(r['raw'])
            if 'id' in f:f['id']+=1
            r['raw']=json.dumps(f)+'\n'
        frames=frames[:5]+[page,response]+tail
        for seq,r in enumerate(frames,1):r['seq']=seq
        self.assertEqual(a.replay_protocol(frames,expected=e)['profile'],PROFILE)
        response['raw']=json.dumps({'id':3,'result':{'data':[],'nextCursor':'page-2'}})+'\n'
        with self.assertRaises(a.ProtocolError):a.replay_protocol(frames,expected=e)


class BoundaryTests(unittest.TestCase):
    def test_unprotected_proofs_and_env_marker_never_authorize_host_launch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);proof=root/'proof';proof.write_text(json.dumps(boundary(root)))
            env={'CODEX_HOME':'/tmp/codex-disposable','AUTODATA_DISPOSABLE_CONTAINER':'enabled'}
            with patch.object(a,'_readonly_mount',return_value=True):
                with self.assertRaises(a.ProtocolError):a.validate_boundary(proof,cwd=root,env=env)
            link=root/'link';link.symlink_to(proof)
            with self.assertRaises(a.ProtocolError):a.validate_boundary(link,cwd=root,env=env)
            with patch.object(a.os,'geteuid',return_value=0):
                with self.assertRaises(a.ProtocolError):a.validate_boundary(proof,cwd=root,env=env)

    def test_evidence_parent_must_be_inside_supervisor_output_root(self):
        proof=boundary(Path('/evidence/run/worktree'))
        proof['worktree_root']='/evidence/run/worktree'
        proof['output_root']='/evidence/run/worktree'
        with self.assertRaises(a.ProtocolError):
            a._proof_shape(proof,cwd='/evidence/run/worktree',codex_home=proof['codex_home'])
        proof['output_root']='/evidence/run'
        a._proof_shape(proof,cwd='/evidence/run/worktree',codex_home=proof['codex_home'])

    def test_default_home_is_derived_without_overriding_environment(self):
        env={'HOME':'/home/node'}
        self.assertEqual(a.codex_home(env),'/home/node/.codex')
        self.assertEqual(env,{'HOME':'/home/node'})

class CompletedItemTests(unittest.TestCase):
    def test_optional_turn_item_metadata_does_not_replace_or_invalidate_final_text(self):
        frames,e=exchange()
        mutate(frames,lambda f:f.get('method')=='turn/completed',lambda f:f['params']['turn']['items'][-1].update(memoryCitation=None))
        self.assertEqual(json.loads(a.replay_protocol(frames,expected=e)['response_text']),{'schema_version':2,'assessments':[]})

    def test_conflicting_user_content_in_completed_turn_and_null_scope_block(self):
        for mode in ['user-content','null-thread']:
            frames,e=exchange()
            if mode=='user-content':mutate(frames,lambda f:f.get('method')=='turn/completed',lambda f:f['params']['turn']['items'][0]['content'][0].update(text='other request'))
            else:mutate(frames,lambda f:f.get('method')=='turn/completed',lambda f:f['params'].update(threadId=None))
            with self.subTest(mode=mode),self.assertRaises(a.ProtocolError):a.replay_protocol(frames,expected=e)


if __name__ == "__main__": unittest.main()
