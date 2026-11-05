"""Synthetic-only acceptance tests. All origins use reserved .invalid names."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bank_canary_capture import validate_enrollment, run_capture

class Clock:
    def __init__(self):
        import multiprocessing
        self._value=multiprocessing.Value('d',0.0)
    @property
    def value(self):return self._value.value
    @value.setter
    def value(self,value):self._value.value=value
    def monotonic(self): return self.value
    def sleep(self,seconds): self.value+=seconds
    def utcnow(self): return datetime(2026,11,5,12,tzinfo=timezone.utc)

def enrollment():
    doc={k:'inert:'+k for k in ('operator_ref','reviewer_ref','custodian_ref','execution_approval_ref','protected_storage_ref','rights_ref')}
    doc.update(run_id='inert-run-1',window_start='2026-11-05T11:00:00Z',window_end='2026-11-05T13:00:00Z',retention_delete_at='2026-11-06T12:00:00Z',product_sha='1'*40,product_tree='2'*40,executor_sha='3'*40,client_sha256='4'*64,banks={})
    for bank in ('bankone','banktwo'):
        b={k:'inert:'+bank+':'+k for k in ('owner_identity_ref','deployment_revision','key_version_ref','egress_identity_ref','license_ref','revision_attestation_ref','incident_procedure_ref')}
        b.update(origin=f'https://{bank}.invalid',expected_source_revision='revision-1',minimum_fetched_at='2026-11-05T11:00:00Z',maximum_fetched_at='2026-11-05T13:00:00Z',selector=dict(year=2020,make='Example',model='Sedan',configuration='Base',region='US'),source_vehicle_ref='vehicle/1',article_ref='article/1',body_ref='body/1',resources={'items':[{'ref':'body/1','role':'body','media_type':'text/plain','required':True,'source_revision':'revision-1','expected_bytes':24,'sha256':hashlib.sha256(b'Procedure: inert fixture').hexdigest()}],'absent_roles':['asset','labor'],'membership_attestation_ref':'inert:membership'},applicability_mapping={'configuration_field':'configuration','region_field':'region','source_field':'source_label','expected_source':'fixture','owner_approval_ref':'inert:mapping'},procedure_content_rule={'markers':['Procedure:'],'minimum_text_length':10,'owner_approval_ref':'inert:rule'})
        doc['banks'][bank]=b
    return doc

class Response(io.BytesIO):
    def __init__(self,body,url,status=200,headers=None):
        super().__init__(body if isinstance(body,bytes) else json.dumps(body).encode())
        self.status,self.url=status,url
        self.headers=headers or {'Content-Type':'application/json'}
    def geturl(self): return self.url

class RequestLog:
    def __init__(self):self.file=tempfile.TemporaryFile()
    def append(self,request):
        import os
        os.lseek(self.file.fileno(),0,os.SEEK_END)
        os.write(self.file.fileno(),json.dumps([request.full_url,request.get_method(),request.data.decode() if request.data else None]).encode()+b'\n')
    def rows(self):
        import os
        from urllib.request import Request
        os.lseek(self.file.fileno(),0,os.SEEK_SET)
        raw=os.read(self.file.fileno(),1_000_000)
        return [Request(url,data=data.encode() if data else None,method=method) for url,method,data in map(json.loads,raw.splitlines())]
    def __len__(self):return len(self.rows())
    def __iter__(self):return iter(self.rows())
    def __del__(self):self.file.close()

class Fixture:
    offline=True
    def __init__(self,pages=1,mutate=None): self.calls=RequestLog();self.pages=pages;self.mutate=mutate
    def __call__(self,bank,config):
        def opener(request,timeout):
            self.calls.append(request);path=urlsplit(request.full_url).path;query=parse_qs(urlsplit(request.full_url).query)
            env=dict(request_id='00000000-0000-4000-8000-000000000001',provider=bank,source_revision='revision-1',fetched_at='2026-11-05T12:00:00Z')
            if path.endswith('capabilities'): env.update(capabilities=['catalog','vehicle_resolution','article_list','resource_read'])
            elif '/catalog/' in path:
                scope=path.rsplit('/',1)[1];key={'years':'year','makes':'make','models':'model','configurations':'configuration'}[scope]
                row=dict(opaque_ref='row/1',label='fixture',configuration='Base',region='US',source_label='fixture');row[key]=config['selector'][key];env.update(scope=scope,items=[row])
            elif path.endswith('vehicle-resolutions'): env.update(selector=json.loads(request.data),candidates=[dict(opaque_ref='vehicle/1',label='fixture',confidence=1)])
            elif path.endswith('/articles'): env.update(articles=[dict(opaque_ref='article/1',title='Inert',resource_ref='body/1',asset_resource_refs=[])])
            elif '/resources/' in path: env.update(kind='article',content='Procedure: inert fixture',media_type='text/plain',sha256=hashlib.sha256(b'Procedure: inert fixture').hexdigest(),asset_resource_refs=[])
            else: raise AssertionError('unexpected operation')
            if '/catalog/' in path or path.endswith('/articles'):
                page=int(query.get('cursor',['0'])[0])+1;env['complete']=page>=self.pages
                if not env['complete']:
                    env['next_cursor']=str(page)
                    if 'articles' in env: env['articles']=[dict(opaque_ref='other/'+str(page),title='Descriptor only')]
            if self.mutate: return self.mutate(bank,request,env) or Response(env,request.full_url)
            return Response(env,request.full_url)
        return opener

class EnrollmentTests(unittest.TestCase):
    def test_complete_frozen_enrollment(self): self.assertEqual(validate_enrollment(enrollment())['run_id'],'inert-run-1')
    def test_missing_unknown_fields_and_origins(self):
        for change in (lambda d:d.pop('reviewer_ref'),lambda d:d.update(extra=True),lambda d:d['banks']['bankone'].update(origin='https://user:secret@bank.invalid'),lambda d:d['banks']['bankone']['selector'].update(vin='inert'),lambda d:d['banks']['bankone'].update(resources={})):
            with self.subTest(change=change):
                doc=enrollment();change(doc)
                with self.assertRaises(ValueError): validate_enrollment(doc)
    def test_malformed_scalar_types_raise_only_sanitized_validation(self):
        for mutate in (lambda d:d.update(run_id=[]),lambda d:d['banks']['bankone']['resources']['items'][0].update(role=[])):
            doc=enrollment();mutate(doc)
            with self.assertRaises(ValueError):validate_enrollment(doc)
    def test_invalid_enrollment_never_constructs_transport(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError): run_capture({},lambda *a:self.fail('transport created'),Clock(),root)

class GraphTests(unittest.TestCase):
    def run_fixture(self,fixture,doc=None):
        with tempfile.TemporaryDirectory() as root:
            result=run_capture(doc or enrollment(),fixture,Clock(),root)
            files={p.name:p.read_bytes() for p in Path(root).rglob('*') if p.is_file()}
        return result,files
    def test_graph_complete_and_review_pending(self):
        f=Fixture();result,files=self.run_fixture(f);self.assertEqual(len(f.calls),16)
        self.assertEqual([r.get_method() for r in f.calls].count('POST'),2)
        self.assertTrue(all(b['state']=='observed_complete' for b in result['banks'].values()))
        self.assertTrue(all(b['review_state']=='pending' for b in result['banks'].values()));self.assertIn('attempts.jsonl',files)
    def test_page_ten_incomplete_stops_without_eleventh_and_other_bank_runs(self):
        f=Fixture(pages=11);result,_=self.run_fixture(f);self.assertEqual(len(f.calls),22)
        self.assertTrue(all(b['stop_code']=='PAGE_LIMIT' for b in result['banks'].values()))
    def test_null_terminal_cursor_is_nonpass(self):
        def mutate(bank,request,env):
            if '/catalog/' in request.full_url: env['next_cursor']=None
        result,_=self.run_fixture(Fixture(mutate=mutate));self.assertEqual(result['banks']['bankone']['stop_code'],'PAGINATION')
    def test_selector_drift_retains_original(self):
        def mutate(bank,request,env):
            if 'selector' in env: env['selector']['region']='XX'
        result,files=self.run_fixture(Fixture(mutate=mutate));self.assertEqual(result['banks']['bankone']['stop_code'],'SELECTOR')
        self.assertTrue(any(b'"region": "XX"' in b for n,b in files.items() if n.endswith('.raw')))

class TransportTests(unittest.TestCase):
    def transport(self,root,opener,allowance=100):
        from bank_canary_transport import CaptureTransport
        return CaptureTransport(root,opener=opener,allowance=allowance)
    def test_http_error_body_is_captured_before_client_rejects(self):
        from urllib.error import HTTPError
        from urllib.request import Request
        from bank_canary_transport import CaptureTransport
        raw=b'provider error original'
        def error(req,timeout): raise HTTPError(req.full_url,429,'untrusted error',{'Content-Type':'text/plain','Retry-After':'3'},io.BytesIO(raw))
        with tempfile.TemporaryDirectory() as root:
            transport=CaptureTransport(root,opener=error)
            response=transport(Request('https://bankone.invalid/v1/capabilities'))
            self.assertEqual(response.status,429);self.assertEqual(response.read(),raw)
            self.assertEqual(Path(root,'0001.raw').read_bytes(),raw)
    def test_unknown_framing_at_exact_ceiling_is_partial_without_sentinel(self):
        from urllib.request import Request
        from bank_canary_transport import CaptureFailure
        import multiprocessing
        count=multiprocessing.Value('i',0);size=multiprocessing.Value('i',0)
        class Counting(Response):
            def read(self,n=-1):count.value+=1;size.value=n;return super().read(n)
        response=Counting(b'abcdMORE','https://bankone.invalid/v1/capabilities')
        with tempfile.TemporaryDirectory() as root:
            transport=self.transport(root,lambda *a,**k:response,4)
            with self.assertRaises(CaptureFailure):transport(Request(response.url))
            self.assertEqual((count.value,size.value),(1,4));self.assertEqual(Path(root,'0001.raw').read_bytes(),b'abcd')
            self.assertEqual(transport.last['state'],'partial')
    def test_proven_eof_at_exact_ceiling_is_complete(self):
        from urllib.request import Request
        response=Response(b'abcd','https://bankone.invalid/v1/capabilities',headers={'Content-Length':'4'})
        with tempfile.TemporaryDirectory() as root:
            transport=self.transport(root,lambda *a,**k:response,4)
            self.assertEqual(transport(Request(response.url)).read(),b'abcd')
            self.assertEqual(transport.last['state'],'complete')
    def test_truncated_content_length_is_partial(self):
        from urllib.request import Request
        from bank_canary_transport import CaptureFailure
        response=Response(b'ab','https://bankone.invalid/v1/capabilities',headers={'Content-Length':'4'})
        with tempfile.TemporaryDirectory() as root:
            transport=self.transport(root,lambda *a,**k:response,4)
            with self.assertRaises(CaptureFailure):transport(Request(response.url))
            self.assertEqual(transport.last['reason'],'FRAMING')
    def test_secret_headers_stay_only_in_quarantine_journal(self):
        from urllib.request import Request
        from bank_canary_transport import CaptureFailure
        response=Response(b'abcd','https://bankone.invalid/v1/capabilities',headers={'X-Source-Locator':'https://fixture.invalid/path?token=INERT-SECRET','Set-Cookie':'forbidden'})
        with tempfile.TemporaryDirectory() as root:
            transport=self.transport(root,lambda *a,**k:response)
            with self.assertRaises(CaptureFailure):transport(Request(response.url))
            self.assertEqual(transport.last['state'],'quarantined')
            self.assertNotIn('INERT-SECRET',json.dumps(transport.last))
            self.assertNotIn('Set-Cookie',Path(root,'0001.journal').read_text())
    def test_actual_in_memory_credential_is_detected(self):
        from urllib.request import Request
        from bank_canary_transport import CaptureTransport,CaptureFailure
        with tempfile.TemporaryDirectory() as root:
            t=CaptureTransport(root,opener=lambda r,**k:Response(b'inert-sensitive-token',r.full_url),credentials=(b'inert-sensitive-token',))
            with self.assertRaises(CaptureFailure): t(Request('https://bankone.invalid/v1/capabilities'))
            self.assertEqual(t.last['reason'],'SECRET_INCIDENT')
    def test_watchdog_reaps_blocked_child(self):
        import multiprocessing
        import time
        from urllib.request import Request
        from bank_canary_transport import CaptureTransport,CaptureFailure
        def blocked(spec): time.sleep(30)
        before={p.pid for p in multiprocessing.active_children()}
        with tempfile.TemporaryDirectory() as root:
            t=CaptureTransport(root,child_target=blocked,deadline=time.monotonic()+.1)
            with self.assertRaises(CaptureFailure):t(Request('https://bankone.invalid/v1/capabilities'))
            self.assertEqual(t.last['state'],'absent');self.assertEqual(t.last['reason'],'DEADLINE')
        self.assertEqual({p.pid for p in multiprocessing.active_children()},before)
    def test_socketpair_slow_trickle_retains_flushed_partial_after_kill(self):
        import socket
        import time
        from urllib.request import Request
        from bank_canary_transport import CaptureTransport,CaptureFailure,_stream
        left,right=socket.socketpair()
        left.sendall(b'inert-prefix')
        def trickle(spec):
            left.close()
            class SocketResponse:
                status=200;headers={'Content-Type':'text/plain'}
                def read(self,size):return right.recv(size)
            _stream(SocketResponse(),spec['url'],spec['raw_path'],spec['journal_path'],spec['allowance'],())
        try:
            with tempfile.TemporaryDirectory() as root:
                t=CaptureTransport(root,child_target=trickle,deadline=time.monotonic()+.15)
                with self.assertRaises(CaptureFailure):t(Request('https://bankone.invalid/v1/capabilities'))
                self.assertEqual(Path(root,'0001.raw').read_bytes(),b'inert-prefix')
                self.assertEqual(t.last['state'],'partial');self.assertEqual(t.last['byte_count'],12)
                self.assertEqual(t.last['sha256'],hashlib.sha256(b'inert-prefix').hexdigest())
        finally:left.close();right.close()

class EvidenceTests(unittest.TestCase):
    run_fixture=GraphTests.run_fixture
    def test_secret_body_stops_both_and_does_not_copy_to_inventory(self):
        def mutate(bank,request,env): return Response(b'error?password=INERT-PRIVATE',request.full_url,403)
        result,files=self.run_fixture(Fixture(mutate=mutate))
        self.assertEqual(result['banks']['bankone']['stop_code'],'SECRET_INCIDENT')
        self.assertEqual(result['banks']['banktwo']['state'],'withdrawn')
        self.assertNotIn(b'INERT-PRIVATE',files['inventory.json'])
        self.assertNotIn(b'INERT-PRIVATE',files['summary.json'])
    def test_bad_json_keeps_exact_original_and_other_bank_completes(self):
        raw=b' { original malformed json '
        def mutate(bank,request,env):
            if bank=='bankone': return Response(raw,request.full_url)
        result,files=self.run_fixture(Fixture(mutate=mutate))
        self.assertEqual(result['banks']['bankone']['state'],'failed')
        self.assertEqual(result['banks']['banktwo']['state'],'observed_complete')
        self.assertIn(raw,files.values())
    def test_private_modes_and_existing_run_cannot_be_overwritten(self):
        import stat
        with tempfile.TemporaryDirectory() as root:
            run_capture(enrollment(),Fixture(),Clock(),root)
            for p in Path(root).rglob('*'):
                self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o700 if p.is_dir() else 0o600)
            before=Path(root,'inert-run-1','run.json').read_bytes()
            result=run_capture(enrollment(),Fixture(),Clock(),root)
            self.assertTrue(all(b['stop_code']=='OUTPUT_FAILURE' for b in result['banks'].values()))
            self.assertEqual(Path(root,'inert-run-1','run.json').read_bytes(),before)
    def test_summary_has_only_approved_fields(self):
        _,files=self.run_fixture(Fixture());summary=json.loads(files['summary.json'])
        self.assertEqual(set(summary),{'schema','run_ref','evidence_ref','banks'})
        for bank in summary['banks'].values(): self.assertEqual(set(bank),{'state','stop_code','review_state','intended','attempted','successful'})
    def test_116_request_maximum_and_rate_schedule(self):
        import base64
        doc=enrollment()
        for b in doc['banks'].values():
            b['resources']['absent_roles']=[]
            for role,ref in [('asset','asset/1'),('asset','asset/2'),('asset','asset/3'),('asset','asset/4'),('labor','labor/1')]:
                b['resources']['items'].append(dict(ref=ref,role=role,media_type='text/plain',required=True,source_revision='revision-1',expected_bytes=24,sha256=hashlib.sha256(b'Procedure: inert fixture').hexdigest()))
        def mutate(bank,request,env):
            if 'articles' in env and env['articles'][0]['opaque_ref']=='article/1': env['articles'][0].update(asset_resource_refs=['asset/'+str(n) for n in range(1,5)],labor_resource_ref='labor/1')
            if 'kind' in env: env['asset_resource_refs']=['asset/'+str(n) for n in range(1,5)]
        fixture=Fixture(pages=10,mutate=mutate)
        clock=Clock()
        with tempfile.TemporaryDirectory() as root:result=run_capture(doc,fixture,clock,root)
        self.assertEqual(len(fixture.calls),116)
        self.assertEqual(clock.value,115)
        self.assertTrue(all(b['state']=='observed_complete' for b in result['banks'].values()))

class FailureTests(unittest.TestCase):
    run_fixture=GraphTests.run_fixture
    def test_decoded_secret_quarantines_original_before_decoded_write(self):
        import base64
        payload=b'https://fixture.invalid/path?token=INERT-ENCODED'
        def mutate(bank,request,env):
            if 'kind' in env:
                env.pop('content');env.pop('asset_resource_refs');env.update(kind='binary',content_base64=base64.b64encode(payload).decode(),sha256=hashlib.sha256(payload).hexdigest())
        doc=enrollment()
        for b in doc['banks'].values():
            b['resources']['items'][0].update(expected_bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
        result,files=self.run_fixture(Fixture(mutate=mutate),doc)
        self.assertEqual(result['banks']['bankone']['stop_code'],'SECRET_INCIDENT')
        self.assertEqual(result['banks']['banktwo']['state'],'withdrawn')
        inventory=json.loads(files['inventory.json'])['objects']
        self.assertEqual(inventory[-1]['state'],'quarantined')
        self.assertFalse(any(n.endswith('.decoded') for n in files))
    def test_output_failure_during_initialization_is_sanitized(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root, patch('bank_canary_capture.private_json',side_effect=OSError('private-location-inert')):
            result=run_capture(enrollment(),Fixture(),Clock(),root)
        self.assertTrue(all(b['stop_code']=='OUTPUT_FAILURE' for b in result['banks'].values()))
        self.assertNotIn('private-location',json.dumps(result))
    def test_output_failure_stops_new_calls(self):
        from unittest.mock import patch
        fixture=Fixture()
        with tempfile.TemporaryDirectory() as root,patch('bank_canary_capture.Evidence.decoded',side_effect=OSError('inert')):
            result=run_capture(enrollment(),fixture,Clock(),root)
        self.assertEqual(len(fixture.calls),8)
        self.assertEqual(result['banks']['banktwo']['state'],'withdrawn')
    def test_global_cleanup_reserve_stops_before_launch(self):
        clock=Clock();fixture=Fixture()
        original=fixture.__call__
        class Delayed:
            offline=True
            def __call__(self,bank,config):
                opener=original(bank,config)
                def call(req,timeout):
                    response=opener(req,timeout);clock.value+=1790;return response
                return call
        with tempfile.TemporaryDirectory() as root:result=run_capture(enrollment(),Delayed(),clock,root)
        self.assertEqual(len(fixture.calls),1)
        self.assertTrue(all(b['stop_code']=='DEADLINE' for b in result['banks'].values()))
    def test_opaque_refs_percent_encoded_exactly_once_and_no_region_catalog(self):
        doc=enrollment();ref='vehicle/%2F?x=y'
        for b in doc['banks'].values():b['source_vehicle_ref']=ref
        def mutate(bank,request,env):
            if 'candidates' in env:env['candidates'][0]['opaque_ref']=ref
        fixture=Fixture(mutate=mutate);result,_=self.run_fixture(fixture,doc)
        self.assertTrue(all(b['state']=='observed_complete' for b in result['banks'].values()))
        self.assertTrue(any('/vehicle%2F%252F%3Fx%3Dy/articles' in r.full_url for r in fixture.calls))
        self.assertFalse(any('region=' in r.full_url for r in fixture.calls if '/catalog/' in r.full_url))
    def test_cli_capture_never_opens_credential_descriptors(self):
        from bank_canary_capture import main
        from contextlib import redirect_stdout
        from unittest.mock import patch
        stdout=io.StringIO()
        with patch('os.read',side_effect=AssertionError('read credential')),redirect_stdout(stdout):
            status=main(['capture','--enrollment','missing','--approval','missing','--bankone-key-fd','4','--banktwo-key-fd','5','--evidence-root','unused'])
        self.assertEqual(status,2);self.assertEqual(json.loads(stdout.getvalue())['reason'],'EXECUTION_GATE_REQUIRED')
    def test_unexpected_fixture_error_is_sanitized_and_second_bank_independent(self):
        class Broken(Fixture):
            def __call__(self,bank,config):
                if bank=='bankone':raise RuntimeError('private diagnostic')
                return super().__call__(bank,config)
        result,_=self.run_fixture(Broken())
        self.assertEqual(result['banks']['bankone']['stop_code'],'TRANSPORT')
        self.assertEqual(result['banks']['banktwo']['state'],'observed_complete')
    def test_optional_assets_are_descriptors_only(self):
        doc=enrollment()
        for b in doc['banks'].values():
            b['resources']['absent_roles']=['labor']
            b['resources']['items'].append(dict(ref='asset/optional',role='asset',media_type='text/plain',required=False,source_revision='revision-1',expected_bytes=24,sha256=hashlib.sha256(b'Procedure: inert fixture').hexdigest()))
        def mutate(bank,request,env):
            if 'articles' in env:env['articles'][0]['asset_resource_refs']=['asset/optional']
            if 'kind' in env:env['asset_resource_refs']=['asset/optional']
        fixture=Fixture(mutate=mutate);result,_=self.run_fixture(fixture,doc)
        self.assertEqual(len(fixture.calls),16)
        self.assertTrue(all(b['intended']['required_resources']==1 and b['state']=='observed_complete' for b in result['banks'].values()))

class BoundTests(unittest.TestCase):
    run_fixture=GraphTests.run_fixture
    def test_unattempted_graph_and_fixed_roles_are_recorded_before_calls(self):
        def failure(bank,request,env):return Response(b'inert failed start',request.full_url,401)
        _,files=self.run_fixture(Fixture(mutate=failure))
        planned=[json.loads(line) for line in files['attempts.jsonl'].splitlines() if json.loads(line)['event']=='planned']
        self.assertEqual(len(planned),2)
        self.assertEqual(planned[0]['resources'][0]['role'],'body')
        self.assertEqual(planned[0]['resolution_posts'],1)
    def test_source_not_found_still_writes_result_and_summary(self):
        def not_found(bank,request,env):return Response(b'inert missing',request.full_url,404)
        result,files=self.run_fixture(Fixture(mutate=not_found))
        self.assertEqual(result['banks']['bankone']['stop_code'],'NOT_FOUND')
        self.assertIn('result.json',files);self.assertIn('summary.json',files)
    def test_encoded_secret_is_quarantined_even_when_client_hash_will_fail(self):
        import base64
        def mutate(bank,request,env):
            if 'kind' in env:
                env.pop('content');env.pop('asset_resource_refs')
                env.update(kind='binary',content_base64=base64.b64encode(b'https://fixture.invalid/?token=INERT-HIDDEN').decode(),sha256='0'*64)
        result,files=self.run_fixture(Fixture(mutate=mutate))
        self.assertEqual(result['banks']['bankone']['stop_code'],'SECRET_INCIDENT')
        self.assertEqual(result['banks']['banktwo']['state'],'withdrawn')
        self.assertEqual(json.loads(files['inventory.json'])['objects'][-1]['state'],'quarantined')
    def test_injected_blocked_opener_is_killed_at_bank_deadline(self):
        import time
        clock=Clock();fixture=Fixture()
        class Blocked:
            offline=True
            def __call__(self,bank,config):
                if bank=='banktwo':return fixture(bank,config)
                def blocked(request,timeout):clock.value=901;time.sleep(30)
                return blocked
        started=time.monotonic()
        with tempfile.TemporaryDirectory() as root:result=run_capture(enrollment(),Blocked(),clock,root)
        self.assertLess(time.monotonic()-started,2)
        self.assertEqual(result['banks']['bankone']['stop_code'],'DEADLINE')
        self.assertEqual(result['banks']['banktwo']['state'],'observed_complete')
    def test_keyboard_interrupt_finalizes_inventory_and_results(self):
        def interrupt(bank,request,env):raise KeyboardInterrupt()
        result,files=self.run_fixture(Fixture(mutate=interrupt))
        self.assertEqual(result['banks']['bankone']['stop_code'],'CANCELLED')
        self.assertIn('inventory.json',files);self.assertIn('result.json',files);self.assertIn('summary.json',files)
    def test_socket_read_failure_keeps_other_bank_independent(self):
        import socket
        class BrokenResponse(Response):
            def read(self,n=-1):raise socket.timeout('inert diagnostic')
        def mutate(bank,request,env):
            if bank=='bankone':return BrokenResponse(b'',request.full_url)
        result,files=self.run_fixture(Fixture(mutate=mutate))
        self.assertEqual(result['banks']['bankone']['stop_code'],'READ')
        self.assertEqual(result['banks']['banktwo']['state'],'observed_complete')
        self.assertEqual(json.loads(files['inventory.json'])['objects'][0]['reason'],'READ')
    def test_summary_unknown_fields_are_rejected(self):
        from bank_canary_capture import validate_summary
        _,files=self.run_fixture(Fixture());summary=json.loads(files['summary.json']);summary['path']='private'
        with self.assertRaises(ValueError):validate_summary(summary)
    def test_partial_raw_write_failure_stops_both(self):
        from unittest.mock import patch
        import bank_canary_transport
        original=bank_canary_transport.exclusive
        def fail_raw(path):
            if str(path).endswith('.raw'): raise OSError('private-output-path')
            return original(path)
        fixture=Fixture()
        with tempfile.TemporaryDirectory() as root,patch('bank_canary_transport.exclusive',side_effect=fail_raw):
            result=run_capture(enrollment(),fixture,Clock(),root)
        self.assertEqual(len(fixture.calls),1)
        self.assertEqual(result['banks']['bankone']['stop_code'],'OUTPUT_FAILURE')
        self.assertEqual(result['banks']['banktwo']['state'],'withdrawn')
    def test_statuses_no_retry_no_wait_and_other_bank_independent(self):
        for status in (301,401,403,429,500):
            with self.subTest(status=status):
                def mutate(bank,request,env):
                    if bank=='bankone':return Response(b'inert failure body',request.full_url,status,{'Content-Type':'text/plain','Retry-After':'3600','Location':'https://unused.invalid'})
                fixture=Fixture(mutate=mutate);result,files=self.run_fixture(fixture)
                self.assertEqual(len(fixture.calls),9)
                self.assertEqual(result['banks']['bankone']['attempted']['requests'],1)
                self.assertEqual(result['banks']['banktwo']['state'],'observed_complete')
                self.assertNotIn(b'Location',files['inventory.json']);self.assertIn(b'inert failure body',files.values())
    def test_repeated_cursor_and_changed_membership_fail_without_new_fetches(self):
        def cursor(bank,request,env):
            if '/catalog/' in request.full_url:env.update(complete=False,next_cursor='1')
        fixture=Fixture(mutate=cursor);result,_=self.run_fixture(fixture)
        self.assertEqual(len(fixture.calls),6);self.assertEqual(result['banks']['bankone']['stop_code'],'PAGINATION')
        def membership(bank,request,env):
            if 'articles' in env:env['articles'][0]['asset_resource_refs']=['unfrozen/asset']
        fixture=Fixture(mutate=membership);result,_=self.run_fixture(fixture)
        self.assertEqual(len(fixture.calls),14);self.assertEqual(result['banks']['bankone']['stop_code'],'RESOURCE_MEMBERSHIP')
    def test_provider_revision_region_drift_rejected_after_raw_capture(self):
        for key,value,expected in [('provider','banktwo','INVALID_UPSTREAM_RESPONSE'),('source_revision','wrong','IDENTITY')]:
            with self.subTest(key=key):
                def mutate(bank,request,env):
                    if bank=='bankone':env[key]=value
                result,files=self.run_fixture(Fixture(mutate=mutate))
                self.assertEqual(result['banks']['bankone']['stop_code'],expected)
                self.assertEqual(result['banks']['banktwo']['state'],'observed_complete')
                self.assertTrue(any(b'"'+value.encode()+b'"' in raw for name,raw in files.items() if name.endswith('.raw')))
    def test_no_real_origin_can_construct_transport(self):
        doc=enrollment();doc['banks']['bankone']['origin']='https://real.example.com'
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):run_capture(doc,Fixture(),Clock(),root)
    def test_duplicate_resource_refs_fetch_once_preserving_roles(self):
        doc=enrollment()
        for b in doc['banks'].values():
            body=b['resources']['items'][0];b['resources']['items'].append(dict(body,role='asset'));b['resources']['absent_roles']=['labor']
        def mutate(bank,request,env):
            if 'articles' in env:env['articles'][0]['asset_resource_refs']=['body/1']
            if 'kind' in env:env['asset_resource_refs']=['body/1']
        fixture=Fixture(mutate=mutate);result,_=self.run_fixture(fixture,doc)
        self.assertEqual(len(fixture.calls),16)
        self.assertTrue(all(b['successful']['required_resources']==1 for b in result['banks'].values()))

class ChildBoundaryTests(unittest.TestCase):
    def test_child_dns_failure_has_no_invented_http_evidence(self):
        from urllib.request import Request
        from bank_canary_transport import CaptureTransport,CaptureFailure
        def dns_failure(spec):spec['completion'].send('DNS');spec['completion'].close()
        with tempfile.TemporaryDirectory() as root:
            transport=CaptureTransport(root,child_target=dns_failure)
            with self.assertRaises(CaptureFailure):transport(Request('https://bankone.invalid/v1/capabilities'))
            self.assertEqual(transport.last['reason'],'DNS');self.assertIsNone(transport.last['status']);self.assertIsNone(transport.last['raw_ref'])
    def test_direct_child_uses_one_tls_connection_identity_encoding_and_allowlisted_headers(self):
        from bank_canary_transport import _https_child
        from unittest.mock import patch
        class Completion:
            values=[]
            def send(self,value):self.values.append(value)
            def close(self):pass
        class Sock:
            def getpeercert(self,binary_form):return b'inert-cert'
            def version(self):return 'TLSv1.3'
            def cipher(self):return ('INERT', 'TLSv1.3', 256)
            def getpeername(self):return ('192.0.2.1',443)
        class Connection:
            calls=[]
            def __init__(self,*args,**kwargs):self.sock=Sock();self.calls.append(('construct',args,kwargs))
            def connect(self):self.calls.append(('connect',))
            def request(self,*args,**kwargs):self.calls.append(('request',args,kwargs))
            def getresponse(self):return Response(b'inert bytes','https://bankone.invalid/v1/capabilities',headers={'Content-Type':'text/plain','Content-Length':'11','Set-Cookie':'inert private cookie'})
            def close(self):self.calls.append(('close',))
        with tempfile.TemporaryDirectory() as root,patch('bank_canary_transport.http.client.HTTPSConnection',Connection):
            _https_child(dict(url='https://bankone.invalid/v1/capabilities',method='GET',data=None,headers={'Accept':'application/json'},raw_path=str(Path(root,'r.raw')),journal_path=str(Path(root,'r.journal')),allowance=100,completion=Completion()))
            self.assertEqual(Completion.values,[None])
            self.assertNotIn('Set-Cookie',Path(root,'r.journal').read_text())
        self.assertEqual([c[0] for c in Connection.calls].count('construct'),1)
        headers=next(c[2]['headers'] for c in Connection.calls if c[0]=='request')
        self.assertEqual(headers['Accept-Encoding'],'identity');self.assertNotIn('Cookie',headers)
    def test_aggregate_allowance_bounds_failed_originals(self):
        # The same ceiling mechanism receives the remaining per-bank allowance,
        # including a failed response; it cannot consume a sentinel byte beyond it.
        from urllib.request import Request
        from bank_canary_transport import CaptureTransport,CaptureFailure
        with tempfile.TemporaryDirectory() as root:
            transport=CaptureTransport(root,opener=lambda r,**k:Response(b'123456789',r.full_url,status=500),allowance=5)
            with self.assertRaises(CaptureFailure):transport(Request('https://bankone.invalid/v1/capabilities'))
            self.assertEqual(transport.last['byte_count'],5);self.assertEqual(transport.last['status'],500)
            self.assertEqual(Path(root,'0001.raw').read_bytes(),b'12345')

if __name__ == '__main__':
    unittest.main()
