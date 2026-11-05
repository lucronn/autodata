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
    def __init__(self): self.value=0.0
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

class Fixture:
    offline=True
    def __init__(self,pages=1,mutate=None): self.calls=[];self.pages=pages;self.mutate=mutate
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
                if not env['complete']: env['next_cursor']=str(page)
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
if __name__=='__main__': unittest.main()
