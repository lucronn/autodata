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


def disabled_notification():
    """Synthetic values with the exact official 0.162.1 notification shape."""
    return {"method": "remoteControl/status/changed", "params": {
        "status": "disabled", "serverName": "autodata-fixture",
        "installationId": "123e4567-e89b-12d3-a456-426614174000",
        "environmentId": None}, "emittedAtMs": 1793700000000}


def numbered(records):
    for seq, record in enumerate(records, 1):
        record["seq"] = seq
    return records


def startup_snapshot(records, *, after_initialized=False):
    records = [copy.deepcopy(r) for r in records
               if json.loads(r["raw"]).get("method") != "remoteControl/status/changed"]
    if after_initialized:
        index = next(i for i, r in enumerate(records) if r["direction"] == "client"
                     and json.loads(r["raw"]).get("method") == "initialized")
    else:
        index = next(i for i, r in enumerate(records) if r["direction"] == "server"
                     and json.loads(r["raw"]).get("id") == 1)
    records.insert(index+1, {"direction": "server", "raw": json.dumps(disabled_notification())+"\n"})
    return numbered(records)


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
    return startup_snapshot(records), e


def mutate(records, predicate, change):
    for r in records:
        frame = json.loads(r["raw"])
        if predicate(frame):
            change(frame)
            r["raw"] = json.dumps(frame)+"\n"
            return
    raise AssertionError("fixture frame absent")


class DisabledStartupTests(unittest.TestCase):
    def test_source_shaped_snapshot_before_or_after_written_initialized(self):
        for after in (False, True):
            with self.subTest(after_initialized=after):
                frames, expected = exchange()
                frames = startup_snapshot(frames, after_initialized=after)
                self.assertTrue(a.replay_protocol(frames, expected=expected)["completed"])
        # Metadata text is retained as information, never used as a hostname command.
        frames, expected = exchange()
        frames = startup_snapshot(frames)
        mutate(frames, lambda f: f.get("method") == "remoteControl/status/changed",
               lambda f: f["params"].update(serverName="évidence"))
        self.assertEqual(a.replay_protocol(frames, expected=expected)["profile"], PROFILE)
        for name, timestamp in (("x"*255, 0), ("é"*127+"x", 2**63-1)):
            frames, expected = exchange()
            mutate(frames, lambda f: f.get("method") == "remoteControl/status/changed",
                   lambda f: (f["params"].update(serverName=name), f.update(emittedAtMs=timestamp)))
            self.assertTrue(a.replay_protocol(frames, expected=expected)["completed"])

    def test_missing_snapshot_does_not_certify_or_queue_catalog(self):
        frames, expected = exchange()
        missing = numbered([r for r in frames if json.loads(r["raw"]).get("method") != "remoteControl/status/changed"])
        with self.assertRaises(a.ProtocolError):
            a.replay_protocol(missing, expected=expected)
        session = a._Session(expected)
        for rec in missing[:2]:
            session.feed(rec["direction"], json.loads(rec["raw"]))
        self.assertEqual(session.ready, [{"method": "initialized"}])
        with self.assertRaises(a.ProtocolError):session.finish()

    def test_exact_shape_types_bounds_and_disabled_state_are_required(self):
        mutations = []
        for value in ("connecting", "connected", "errored", "active", "unknown", None, True, {}):
            mutations.append(("status", lambda f, v=value: f["params"].update(status=v)))
        for field, values in {
            "serverName": (None, 4, "", " ", " padded", "bad\nname", "\x7f", "x"*256, "é"*128, "\ud800"),
            "installationId": (None, 4, "", "invalid", "123E4567-E89B-12D3-A456-426614174000",
                               "123e4567e89b12d3a456426614174000"),
            "environmentId": ("", "environment", False, {}),
        }.items():
            for value in values:
                mutations.append((field, lambda f, k=field, v=value: f["params"].update({k: v})))
        for field in ("status", "serverName", "installationId", "environmentId"):
            mutations.append(("missing-"+field, lambda f, k=field: f["params"].pop(k)))
        for value in (None, True, "1793700000000", -1, 2**63):
            mutations.append(("timestamp", lambda f, v=value: f.update(emittedAtMs=v)))
        mutations.extend([
            ("missing-timestamp", lambda f: f.pop("emittedAtMs")),
            ("profile", lambda f: f["params"].update(model="gpt-6.1-sol")),
            ("scope", lambda f: f["params"].update(threadId="thread-1")),
            ("extra-top", lambda f: f.update(settings={})),
            ("request", lambda f: f.update(id=100)),
            ("params-list", lambda f: f.update(params=[])),
        ])
        for label, change in mutations:
            with self.subTest(mutation=label, change=change):
                frames, expected = exchange()
                frames = startup_snapshot(frames)
                mutate(frames, lambda f: f.get("method") == "remoteControl/status/changed", change)
                with self.assertRaises(a.ProtocolError):a.replay_protocol(frames, expected=expected)
        frames, expected = exchange();frames = startup_snapshot(frames)
        rec = next(r for r in frames if json.loads(r["raw"]).get("method") == "remoteControl/status/changed")
        rec["raw"] = rec["raw"].replace('"status": "disabled"', '"status":"disabled","status":"disabled"')
        with self.assertRaises(a.ProtocolError):a.replay_protocol(frames, expected=expected)

    def test_snapshot_before_successful_initialize_and_all_repeats_block(self):
        for stage in ("before-request", "before-response", "failed-init", "repeat-startup",
                      "repeat-turn", "repeat-terminal", "changed-identity"):
            with self.subTest(stage=stage):
                frames, expected = exchange();frames = startup_snapshot(frames)
                snapshot = next(r for r in frames if json.loads(r["raw"]).get("method") == "remoteControl/status/changed")
                if stage.startswith("before"):
                    frames.remove(snapshot)
                    frames.insert(0 if stage == "before-request" else 1, snapshot)
                elif stage == "failed-init":
                    mutate(frames, lambda f: f.get("id") == 1 and "result" in f,
                           lambda f: (f.pop("result"), f.update(error={"code": -1, "message": "failed"})))
                else:
                    duplicate = copy.deepcopy(snapshot)
                    if stage == "changed-identity":
                        f = json.loads(duplicate["raw"]);f["params"]["serverName"] = "other";duplicate["raw"] = json.dumps(f)+"\n"
                    if stage == "repeat-terminal":frames.append(duplicate)
                    elif stage == "repeat-turn":
                        i = next(i for i,r in enumerate(frames) if json.loads(r["raw"]).get("method") == "turn/start")
                        frames.insert(i+1, duplicate)
                    else:frames.insert(frames.index(snapshot)+1, duplicate)
                with self.assertRaises(a.ProtocolError):a.replay_protocol(numbered(frames), expected=expected)

    def test_valid_snapshot_does_not_allow_other_remote_methods_warnings_or_settings(self):
        for method in ("remoteControl/status/read", "remoteControl/unknown", "configWarning", "warning",
                       "model/rerouted", "thread/settings/updated", "unknown/startup"):
            with self.subTest(method=method):
                frames, expected = exchange();frames = startup_snapshot(frames)
                index = next(i for i, rec in enumerate(frames)
                             if json.loads(rec["raw"]).get("method") == "remoteControl/status/changed")
                frames.insert(index+1, {"direction": "server", "raw": json.dumps({"method": method, "params": {}})+"\n"})
                with self.assertRaises(a.ProtocolError):a.replay_protocol(numbered(frames), expected=expected)


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
        if mode!='startup-missing':
            snapshot={'method':'remoteControl/status/changed','params':{'status':'disabled','serverName':'autodata-fixture','installationId':'123e4567-e89b-12d3-a456-426614174000','environmentId':None},'emittedAtMs':1793700000000}
            if mode in ('startup-connecting','startup-connected','startup-errored'):
                snapshot['params']['status']=mode.removeprefix('startup-')
            if mode=='startup-malformed':snapshot['params']['environmentId']='unexpected-environment'
            send(snapshot)
            if mode=='startup-repeated':send(snapshot)
            if mode in ('startup-unknown','startup-config-warning'):
                send({'method':'unknown/startup' if mode=='startup-unknown' else 'configWarning','params':{}})
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
            snapshots=[x for x in captured[1:-1] if x['direction']=='server'
                       and json.loads(x['raw']).get('method')=='remoteControl/status/changed']
            self.assertEqual(len(snapshots),1)
            self.assertEqual(json.loads(snapshots[0]['raw']),disabled_notification())
            discovery=next(x for x in captured[1:-1] if x['direction']=='client'
                           and json.loads(x['raw']).get('method')=='model/list')
            self.assertLess(snapshots[0]['seq'],discovery['seq'])
            with self.assertRaises(a.ProtocolError):a.replay_capture(result['protocol'],stdout=result['stdout']+b'{}\n',expected=e)

    def test_startup_failure_processes_are_bounded_and_never_start_thread_or_turn(self):
        modes=['startup-missing','startup-connecting','startup-connected','startup-errored',
               'startup-malformed','startup-repeated','startup-unknown','startup-config-warning']
        for mode in modes:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
                cwd=Path(d);bindir=fake_codex(cwd);e=expected_context(str(cwd))
                env={**os.environ,'PATH':str(bindir)+os.pathsep+os.environ['PATH'],
                     'CODEX_HOME':e['codex_home'],'FAKE_CODEX_MODE':mode}
                started=time.monotonic()
                with patch.object(a,'validate_boundary',return_value=boundary(cwd)):
                    result=a.run_app_server(argv=ARGV,cwd=cwd,env=env,prompt=e['prompt'],
                        schema=e['schema'],expected=e,boundary_proof=a.BOUNDARY,timeout_seconds=4)
                self.assertLess(time.monotonic()-started,5)
                self.assertNotEqual(result['status'],'completed')
                self.assertLessEqual(len(result['stdout']),4*1024*1024)
                self.assertLessEqual(len(result['stderr']),4*1024*1024)
                frames=[json.loads(x) for x in result['protocol'].splitlines()][1:-1]
                methods=[json.loads(x['raw']).get('method') for x in frames if x['direction']=='client']
                self.assertNotIn('thread/start',methods)
                self.assertNotIn('turn/start',methods)
                if mode in modes[:5]:
                    self.assertTrue(set(methods)<= {'initialize','initialized'},methods)
                server=[json.loads(x['raw']) for x in frames if x['direction']=='server']
                snapshots=[f for f in server if f.get('method')=='remoteControl/status/changed']
                self.assertEqual(len(snapshots),0 if mode=='startup-missing' else 2 if mode=='startup-repeated' else 1)
                self.assertTrue(result['stdout'])
                self.assertEqual(result['stdout'],b''.join(x['raw'].encode() for x in frames if x['direction']=='server'))

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
        first_index=next(i for i,r in enumerate(frames) if r['direction']=='server'
                         and json.loads(r['raw']).get('id')==2)
        first=frames[first_index]
        frame=json.loads(first['raw']);frame['result']['nextCursor']='page-2';frame['result']['data']=[];first['raw']=json.dumps(frame)+'\n'
        page={'seq':6,'direction':'client','raw':json.dumps({'id':3,'method':'model/list','params':{'cursor':'page-2','limit':100,'includeHidden':True}})+'\n'}
        models=next(json.loads(r['raw'])['result'] for r in exchange()[0]
                    if r['direction']=='server' and json.loads(r['raw']).get('id')==2)
        response={'seq':7,'direction':'server','raw':json.dumps({'id':3,'result':models})+'\n'}
        tail=frames[first_index+1:]
        for r in tail:
            f=json.loads(r['raw'])
            if 'id' in f:f['id']+=1
            r['raw']=json.dumps(f)+'\n'
        frames=frames[:first_index+1]+[page,response]+tail
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
