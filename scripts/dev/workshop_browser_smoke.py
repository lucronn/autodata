#!/usr/bin/env python3
"""Bounded Workshop browser acceptance; DTO checks never count as real API proof."""
import argparse
import base64
import signal
import socket
import stat
import struct
import sys
import asyncio
import hashlib
import importlib.metadata
import ipaddress
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name('fixtures') / 'workshop_customer'
CONFIG = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'
ARTICLE = '33333333-3333-4333-8333-333333333333'
REVISION = '44444444-4444-4444-8444-444444444444'
ORDER = '55555555-5555-4555-8555-555555555555'
ENGINES = ('chromium', 'firefox', 'webkit')


# This contract is test-only. No environment override or runtime authority.
DTO_TIMING_V1 = {'version': 'v1', 'engines': 3, 'scenarios_per_engine': 40, 'case_execution_seconds': 20, 'case_cleanup_seconds': 3, 'provenance_seconds': 150, 'playwright_start_seconds': 10, 'engine_launch_seconds': 15, 'engine_close_seconds': 3, 'playwright_stop_seconds': 10, 'evidence_persistence_seconds': 10, 'worker_hard_seconds': 4380, 'producer_hard_seconds': 4440, 'worker_term_seconds': 2, 'worker_kill_seconds': 2, 'worker_reap_seconds': 2, 'readiness_seconds': 120, 'handoff_seconds': 10, 'fixture_stop_seconds': 10, 'safety_seconds': 60, 'dto_fixture_seconds': 4800, 'api_fixture_seconds': 4400, 'go_test_seconds': 5040, 'fixture_startup_seconds': 120, 'fixture_teardown_seconds': 60, 'ci_exercise_seconds': 5100, 'ci_job_minutes': 100, 'parent_initialization_seconds': 10, 'parent_progress_read_parse_seconds': 10, 'parent_final_read_parse_stage_seconds': 10, 'parent_commit_seconds': 2, 'io_helper_term_seconds': 2, 'io_helper_kill_seconds': 2, 'io_helper_reap_seconds': 2, 'max_io_helper_cleanup_episodes': 2, 'parent_scheduling_reserve_seconds': 10, 'worker_deadline_reserve_seconds': 50}
DTO_TIMING_KEYS = frozenset(['version', 'engines', 'scenarios_per_engine', 'case_execution_seconds', 'case_cleanup_seconds', 'provenance_seconds', 'playwright_start_seconds', 'engine_launch_seconds', 'engine_close_seconds', 'playwright_stop_seconds', 'evidence_persistence_seconds', 'worker_hard_seconds', 'producer_hard_seconds', 'worker_term_seconds', 'worker_kill_seconds', 'worker_reap_seconds', 'readiness_seconds', 'handoff_seconds', 'fixture_stop_seconds', 'safety_seconds', 'dto_fixture_seconds', 'api_fixture_seconds', 'go_test_seconds', 'fixture_startup_seconds', 'fixture_teardown_seconds', 'ci_exercise_seconds', 'ci_job_minutes', 'parent_initialization_seconds', 'parent_progress_read_parse_seconds', 'parent_final_read_parse_stage_seconds', 'parent_commit_seconds', 'io_helper_term_seconds', 'io_helper_kill_seconds', 'io_helper_reap_seconds', 'max_io_helper_cleanup_episodes', 'parent_scheduling_reserve_seconds', 'worker_deadline_reserve_seconds'])


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def load_dto_timing(path):
    timing = json.loads(Path(path).read_text(), object_pairs_hook=_unique_json)
    validate_dto_schedule(timing, 120)
    return timing


def validate_dto_schedule(timing, case_count):
    if not isinstance(timing, dict) or set(timing) != DTO_TIMING_KEYS or timing['version'] != 'v1':
        raise ValueError('invalid DTO timing schema/version')
    if any(type(value) is not int or not 0 < value <= 1000000 for key,value in timing.items() if key != 'version'):
        raise ValueError('DTO timing values must be finite positive integers')
    if timing != DTO_TIMING_V1:raise ValueError('v1 timing budgets differ from reviewed schedule')
    t = timing
    fixed = dict(engines=3, scenarios_per_engine=40, case_execution_seconds=20,
        case_cleanup_seconds=3, producer_hard_seconds=4440, api_fixture_seconds=4400,
        max_io_helper_cleanup_episodes=2)
    if case_count != 120 or any(t[key] != value for key,value in fixed.items()):
        raise ValueError('frozen DTO inventory or phase cap changed')
    serial = (t['provenance_seconds'] + t['playwright_start_seconds'] +
        3*t['engine_launch_seconds'] + 120*(t['case_execution_seconds']+t['case_cleanup_seconds']) +
        3*t['engine_close_seconds'] + t['playwright_stop_seconds'] + t['evidence_persistence_seconds'])
    worker_cleanup = sum(t['worker_'+part+'_seconds'] for part in ('term','kill','reap'))
    helper_cleanup = 2*sum(t['io_helper_'+part+'_seconds'] for part in ('term','kill','reap'))
    parent = (t['parent_initialization_seconds'] + t['worker_hard_seconds'] + worker_cleanup +
        helper_cleanup + t['parent_final_read_parse_stage_seconds'] + t['parent_commit_seconds'] +
        t['parent_scheduling_reserve_seconds'])
    fixture = sum(t[key] for key in ('readiness_seconds','handoff_seconds','producer_hard_seconds','fixture_stop_seconds','safety_seconds'))
    go = sum(t[key] for key in ('fixture_startup_seconds','dto_fixture_seconds','fixture_teardown_seconds'))
    if not (serial < t['worker_hard_seconds'] and parent < t['producer_hard_seconds'] and
            fixture < t['dto_fixture_seconds'] and go < t['go_test_seconds'] and
            t['go_test_seconds']+t['fixture_stop_seconds']+t['evidence_persistence_seconds'] < t['ci_exercise_seconds'] and
            t['ci_exercise_seconds'] < t['ci_job_minutes']*60 and
            worker_cleanup+helper_cleanup+t['parent_final_read_parse_stage_seconds']+t['parent_commit_seconds']+t['parent_scheduling_reserve_seconds'] <= t['worker_deadline_reserve_seconds']):
        raise ValueError('inconsistent DTO timing inequalities')
    return dict(serial_seconds=serial, parent_total_seconds=parent, fixture_requirement_seconds=fixture, go_requirement_seconds=go)


def remaining(deadline, now):
    if not all(isinstance(value, (int,float)) and not isinstance(value,bool) and
            float('-inf') < value < float('inf') for value in (deadline,now)):
        raise ValueError('invalid monotonic clock')
    return max(0., deadline-now)


def inventory():
    data = json.loads((FIXTURES / 'scenarios.json').read_text())
    names = data['scenarios']
    if data['version'] != 'v1' or len(names) != 40 or len(set(names)) != 40:
        raise ValueError('frozen 40-case inventory is incomplete')
    return names


def fixture_origin(value):
    url = urlsplit(value)
    try: loopback = url.hostname == 'localhost' or ipaddress.ip_address(url.hostname).is_loopback
    except ValueError: loopback = False
    if not (url.scheme == 'https' and loopback and url.port and not url.username and not url.password and not url.path and not url.query and not url.fragment):
        raise ValueError('only an owned loopback HTTPS fixture origin is allowed')
    return value


def candidate_identity(value):
    if not re.fullmatch(r'[a-f0-9]{40}', value or ''): raise ValueError('candidate SHA must be 40 lowercase hex characters')
    return value


def allowed_external(value):
    url = urlsplit(value)
    return url.scheme == 'https' and not url.username and not url.password and url.port is None and (
        (url.hostname == 'apis.google.com' and url.path == '/js/api.js') or
        (url.hostname == 'fixture-project.firebaseapp.com' and url.path in ('/__/auth/handler', '/__/auth/iframe')) or
        (url.hostname == 'identitytoolkit.googleapis.com' and url.path in ('/v1/projects', '/v1/accounts:signInWithIdp', '/v1/accounts:lookup')) or
        (url.hostname == 'securetoken.googleapis.com' and url.path == '/v1/token') or
        (url.hostname == 'checkout.stripe.com' and re.fullmatch(r'/c/pay/(?:fixture|cs_test_[a-f0-9]{32})',url.path)))


def validate_results(rows, expected):
    keys = [(row['browser'], row['scenario']) for row in rows]
    if len(keys) != len(set(keys)) or set(keys) != set(expected) or any(row.get('status') != 'passed' for row in rows):
        raise ValueError('missing, duplicate, failed, unavailable or skipped browser cases cannot pass acceptance')


def verify_provenance(args):
    head=subprocess.run(['git','--no-optional-locks','-c',f'safe.directory={ROOT}','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True,check=True,timeout=5).stdout.strip()
    if head!=args.candidate_sha: raise ValueError('candidate SHA does not match the actual checkout/image input')
    host=urlsplit(args.base_url)
    certificate=ssl.get_server_certificate((host.hostname,host.port),timeout=5)
    certificate_hash=hashlib.sha256(ssl.PEM_cert_to_DER_cert(certificate)).hexdigest()
    assets={}
    for name in ('index.html','app.mjs','auth.mjs','catalog.mjs','progress.mjs','commerce.mjs','article-read.mjs','styles.css','firebase-web.mjs','firebase-web.mjs.LEGAL.txt','firebase-web.provenance.json'):
        local=(ROOT/'apps/api-go/workshop'/name).read_bytes()
        with urlopen(args.base_url+'/workshop/'+name,context=ssl._create_unverified_context(),timeout=10) as response: served=response.read()
        if local!=served: raise ValueError(f'compiled Go asset differs from candidate: {name}')
        assets[name]={'sha256':hashlib.sha256(served).hexdigest(),'bytes':len(served)}
    return {'certificate_sha256':certificate_hash,'assets':assets}


def quote(configuration=CONFIG):
    return dict(version='v1', product_key='workshop-configuration-v1', configuration_id=configuration, region='US', configuration_label='2024 Fixture / Engine', amount_minor=2000, currency='USD', purchase_terms_version='workshop-v1', purchasable=True)


def session():
    return dict(authenticated=True, roles=['dataset_viewer'], expires_at='2099-01-01T00:00:00Z', csrf_token='synthetic-csrf-memory-only')


def article(state='completed', origin='canonical', images=False):
    value = dict(id=ARTICLE, title='Fixture repair procedure', content_origin=origin, view_revision=f'{origin}:revision-1', document={'blocks':[
        {'type':'heading','text':'Disconnect battery'}, {'type':'paragraph','text':'Keep the source order.'},
        {'type':'table','columns':['Value','Enabled'],'rows':[[0,False]]},
        {'type':'step','number':1,'action':'Remove the cover','instructions':['Preserve the fasteners.']},
    ]}, images=[], source_review={'available':True,'url':f'/v1/catalog/vehicles/{CONFIG}/articles/{ARTICLE}/source?source_revision_id={REVISION}'})
    if state != 'completed': value['processing'] = dict(job_id='synthetic-job', state=state, retry_after_seconds=1)
    if images:
        value['images'] = [{'asset_id':'image-one','url':'/v1/catalog/images/v2.expired-one'},{'asset_id':'image-two','url':'/v1/catalog/images/v2.expired-two'}]
        value['document']['blocks'] += [{'type':'image','asset_id':'image-one'},{'type':'image','asset_id':'image-two'}]
    return value


class DTOFixture:
    def __init__(self, origin, scenario):
        self.origin, self.scenario = origin, scenario
        self.requests, self.unexpected, self.errors = [], [], []
        self.authenticated = scenario not in {'google-popup-exchange','google-popup-blocked','google-popup-cancelled','google-stale-reauthentication','firebase-memory-persistence','signin-unavailable-local','signin-malformed-config'}
        self.detail_count = self.checkout_count = self.exchange_count = self.prepare_count = self.index_count = 0
        self.images_release = asyncio.Event()
        self.keys, self.checkout_bodies = [], []
        self.renewed = False
        self.prepared = False
        self.token = None
        self.account = 'user'

    async def route(self, route):
        request = route.request
        url = urlsplit(request.url)
        path, query = url.path, parse_qs(url.query)
        self.requests.append({'method':request.method,'path':path,'query':query})
        if not request.url.startswith(self.origin + '/'):
            if not allowed_external(request.url):
                self.unexpected.append(request.url); await route.abort(); return
            await self.external(route); return
        if path.startswith('/__fixture/') or path.startswith('/workshop/') and path != '/workshop/purchase-config.json':
            await route.continue_(); return
        status, data = 200, None
        if path == '/auth/config':
            data = dict(version='v1',mode='firebase',login_available=True,providers=['google.com'],firebase={'apiKey':'fixture-key','authDomain':'fixture-project.firebaseapp.com','projectId':'fixture-project','appId':'1:123456:web:abcdef'})
            if self.scenario == 'signin-unavailable-local': data = dict(version='v1',mode='local',login_available=False)
            if self.scenario == 'signin-malformed-config': data['firebase']['authDomain'] = 'evil.invalid'
        elif path == '/auth/session':
            data = session()
            if self.scenario == 'session-blocked': status, data = 403, {'error':{'code':'FORBIDDEN'}}
            elif self.scenario == 'auth-dependency-unavailable': status, data = 503, {'error':{'code':'AUTHENTICATION_UNAVAILABLE','retryable':True}}
            elif not self.authenticated: status, data = 401, {'error':{'code':'UNAUTHENTICATED'}}
        elif path == '/auth/firebase/session':
            self.exchange_count += 1
            assert request.headers.get('x-autodata-session-exchange') == '1'
            assert json.loads(request.post_data).keys() == {'id_token'}
            self.authenticated = True
            status, data = 204, None
        elif path == '/auth/logout':
            assert request.headers.get('x-csrf-token') == session()['csrf_token']
            self.authenticated = False; status, data = 204, None
        elif path == '/workshop/purchase-config.json':
            data = dict(terms_version='workshop-v1',enabled=True,terms_url=self.origin+'/__fixture/policy/terms',privacy_url=self.origin+'/__fixture/policy/privacy',refund_url=self.origin+'/__fixture/policy/refund',contact_url=self.origin+'/__fixture/policy/contact',tax_notice='Tax included in the displayed price.')
            if self.scenario == 'terms-config-unavailable': data['enabled'] = False
        elif path == '/v1/catalog/years': data = {'items':[{'year':2024}]}
        elif path.endswith('/makes'): data = {'items':[{'id':'fixture-make','name':'Fixture Make'}]}
        elif path.endswith('/models'): data = {'items':[{'id':'fixture-model','name':'Fixture Model'}]}
        elif path.endswith('/configurations'):
            data = {'items':[dict(id=CONFIG,region='US',engine='Engine',trim='Base',coverage={'bankone':True,'banktwo':self.scenario!='one-bank-unavailable'}),dict(id=OTHER,region='US',engine='Other Engine',trim='Sport')]}
        elif path == '/v1/workshop/quote': data = quote(query['configuration_id'][0])
        elif path == '/v1/workshop/library':
            states = ['paid','preparing','viewable','revoked'] if not query.get('cursor') else ['viewable']
            data = {'version':'v1','items':[dict(library_item_id=ORDER,configuration_id=OTHER,region='US',label=f'Fixture {state}',access_state=state,granted_at='2026-01-01T00:00:00Z') for state in states], 'next_cursor':None if query.get('cursor') else 'synthetic-next'}
        elif path == '/v1/workshop/checkout-sessions':
            self.checkout_count += 1
            self.keys.append(request.headers.get('idempotency-key'))
            self.checkout_bodies.append(request.post_data)
            assert request.headers.get('x-csrf-token') == session()['csrf_token']
            if self.scenario == 'checkout-double-click-retry' and self.checkout_count == 1: await route.abort(); return
            data = dict(version='v1',state='checkout',order_id=ORDER,configuration_id=CONFIG,region='US',checkout_url='https://checkout.stripe.com/c/pay/fixture',provider_expires_at='2099-01-01T00:00:00Z')
        elif path == f'/v1/workshop/orders/{ORDER}':
            state = 'expired' if self.scenario == 'checkout-expired' else 'processing'
            data = dict(version='v1',order_id=ORDER,configuration_id=CONFIG,region='US',state=state,retry_disposition='new_key' if state=='expired' else 'do_not_repay')
        elif path.endswith('/articles'):
            self.index_count += 1
            if self.scenario=='one-bank-unavailable' and self.index_count==1:
                data={'items':[],'hydrating':True,'complete':False}
            elif self.scenario in {'quote-exact-scope','terms-config-unavailable','checkout-double-click-retry'}:
                status, data = 403, {'error':{'code':'ENTITLEMENT_REQUIRED'}}
            elif self.scenario == 'selection-change-in-flight' and CONFIG in path:
                await asyncio.sleep(1); data = {'items':[{'id':ARTICLE,'title':'Stale configuration article'}]}
            else: data = {'items':[{'id':ARTICLE,'title':'Fixture repair procedure'}]}
        elif path.endswith('/prepare') or path.endswith(f'/{ARTICLE}'):
            if path.endswith('/prepare'):
                assert request.method == 'POST' and json.loads(request.post_data) == {}
                assert request.headers.get('x-csrf-token') == session()['csrf_token']
                self.prepared = True
                self.prepare_count += 1
            else:
                self.detail_count += 1
                assert self.prepared, 'detail polling must follow CSRF prepare'
            state, origin = 'completed','canonical'
            if self.scenario == 'pending-no-content' or self.scenario=='cancel-and-retry' and self.prepare_count==1: state='queued'
            if self.scenario == 'source-to-canonical' and not self.detail_count: state,origin='running','source'
            if self.scenario == 'source-rewrite-failure': state,origin='failed','source'
            if self.scenario == 'review-required': state,origin='needs_review','source'
            data = {'article':article(state,origin,self.scenario in {'missing-media','media-renew-coalesced'})}
            if self.scenario == 'pending-no-content': data['article'].pop('document')
            if self.scenario == 'withdrawal': status,data = 410, {'error':{'code':'ARTICLE_WITHDRAWN'}}
            if self.scenario == 'session-expired': self.authenticated=False;status,data=401,{'error':{'code':'UNAUTHENTICATED'}}
            if self.scenario == 'media-renew-coalesced' and self.detail_count:
                for image in data['article']['images']: image['url']=image['url'].replace('expired','renewed')
        elif path.endswith('/source'):
            if self.scenario == 'source-review-change-in-flight': await asyncio.sleep(1)
            hostile=json.loads((FIXTURES/'hostile_source.json').read_text())
            data={'version':'v1','source':{'available':True,'snapshot_id':REVISION,'version':'v1','content_sha256':'a'*64,'format':'json','url':path+'?source_revision_id='+REVISION},'content':'Stored source',**hostile}
        elif path.startswith('/v1/catalog/images/'):
            if 'renewed' in path:
                await route.fulfill(status=200,content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"/>'); return
            if self.scenario=='media-renew-coalesced': await self.images_release.wait()
            status,data=404,{'error':{'code':'NOT_FOUND'}}
        else:
            self.unexpected.append(request.url);await route.abort();return
        await route.fulfill(status=status,content_type='application/json',body='' if data is None else json.dumps(data))

    async def external(self, route):
        request=route.request;url=urlsplit(request.url)
        if url.hostname == 'apis.google.com':
            await route.fulfill(content_type='application/javascript',body=(FIXTURES/'firebase_transport.js').read_text());return
        if url.path == '/__/auth/handler':
            query=parse_qs(url.query);kind=query['authType'][0];event=query['eventId'][0]
            if self.scenario == 'google-popup-cancelled':
                body='<script>setTimeout(()=>window.close(),50)</script>'
            else:
                payload={'fixture':'autodata-google-transport','authEvent':{'type':kind,'eventId':event,'urlResponse':'https://fixture-project.firebaseapp.com/__/auth/handler','sessionId':'synthetic-session','postBody':'providerId=google.com&id_token=synthetic-provider-token','tenantId':None,'pendingToken':None}}
                body='<script>setTimeout(()=>{window.opener.postMessage('+json.dumps(payload)+',"*");},100);</script>'
            await route.fulfill(content_type='text/html',body=body);return
        if url.path == '/v1/projects': data={'projectId':'fixture-project','authorizedDomains':['127.0.0.1','localhost']}
        elif url.path == '/v1/accounts:signInWithIdp':
            if self.token is None:
                response=await route.request.frame.page.context.request.get(self.origin+'/__fixture/token?account='+self.account+('&stale=1' if self.scenario=='google-stale-reauthentication' else ''))
                self.token=await response.json()
            else:
                response=await route.request.frame.page.context.request.get(self.origin+'/__fixture/token?account='+self.account);self.token=await response.json()
            data=self.token
        elif url.path == '/v1/accounts:lookup': data={'users':[{'localId':self.token['localId'],'email':'fixture@example.invalid','emailVerified':True,'providerUserInfo':[{'providerId':'google.com','federatedId':self.token['localId'],'email':'fixture@example.invalid'}],'lastLoginAt':str(int(time.time()*1000)),'createdAt':'1600000000000'}]}
        elif url.hostname == 'securetoken.googleapis.com':
            data={'access_token':self.token['idToken'],'id_token':self.token['idToken'],'expires_in':'3600','token_type':'Bearer','refresh_token':'synthetic-refresh-never-persist','user_id':self.token['localId'],'project_id':'fixture-project'}
        elif url.hostname == 'checkout.stripe.com':
            await route.fulfill(content_type='text/html',body=(FIXTURES/'stripe_checkout.html').read_text());return
        else:
            self.unexpected.append(request.url);await route.abort();return
        await route.fulfill(content_type='application/json',body=json.dumps(data),headers={'Access-Control-Allow-Origin':self.origin})


# Keep abandoned Playwright operations alive until their browser shutdown settles
# them. In particular, never await a cancellation-resistant task past a deadline.
_DTO_PENDING_TASKS = set()


def _dto_task(coroutine):
    task = asyncio.create_task(coroutine)
    _DTO_PENDING_TASKS.add(task)
    def settled(done):
        _DTO_PENDING_TASKS.discard(done)
        if not done.cancelled(): done.exception()
    task.add_done_callback(settled)
    return task


async def _dto_bounded(coroutine, timeout, *, late_cleanup=None, late_result_cleanup=None):
    task = _dto_task(coroutine)
    try:
        done, _ = await asyncio.wait({task}, timeout=max(0, timeout))
        if not done: raise TimeoutError('operation deadline exceeded')
        return task.result()
    except BaseException:
        if late_cleanup is not None:
            task.add_done_callback(lambda done: late_cleanup())
        if late_result_cleanup is not None:
            task.add_done_callback(late_result_cleanup)
        if not task.done(): task.cancel()
        raise


async def close_dto_browser(browser, *, timeout=3):
    try: await _dto_bounded(browser.close(), timeout)
    except Exception as error:
        raise RuntimeError(f'DTO browser shutdown failed: {error}') from error


class DTODiagnostics:
    def __init__(self, output, name, *, cleanup_timeout=3):
        self.output, self.name = Path(output), name
        self.cleanup_timeout = cleanup_timeout
        self.stage = 'context.create'
        self.fixture = self.context = self.page = None
        self.failure_stage = self.failure_kind = self.error = None
        self.trace_status = 'not_started'
        self.trace_path = None
        self.tracing_started = False
        self.requests, self.errors, self.unexpected = [], [], []
        self.diagnostic_errors = []
        self.execution_elapsed_seconds = self.cleanup_elapsed_seconds = 0

    def fail(self, error, *, kind=None):
        if self.failure_kind is not None: return
        if kind is None:
            from playwright.async_api import TimeoutError as ActionTimeoutError
            kind = 'cancelled' if isinstance(error, asyncio.CancelledError) else (
                'action_timeout' if isinstance(error, ActionTimeoutError) else 'exception')
        self.failure_stage, self.failure_kind = self.stage, kind
        self.error = str(error) or type(error).__name__
        if self.fixture is not None:
            # DTO requests already contain no headers or bodies. Exclude credential
            # query parameters as well; unexpected URLs retain origin/path only.
            self.requests = [dict(method=row['method'], path=row['path'], query={
                key: value for key, value in row['query'].items()
                if not re.search(r'token|csrf|authorization|cookie|session', key, re.I)
            }) for row in self.fixture.requests]
            self.errors = list(self.fixture.errors)
            self.unexpected = [urlsplit(url)._replace(query='', fragment='').geturl()
                               for url in self.fixture.unexpected]

    def snapshot(self):
        data = dict(failure_stage=self.failure_stage, failure_kind=self.failure_kind,
            requests=self.requests, errors=self.errors, unexpected=self.unexpected,
            trace_status=self.trace_status, diagnostic_errors=self.diagnostic_errors,
            execution_elapsed_seconds=round(self.execution_elapsed_seconds, 3),
            cleanup_elapsed_seconds=round(self.cleanup_elapsed_seconds, 3))
        if self.trace_path is not None: data['trace_path'] = self.trace_path
        return data

    def write_failure(self):
        if self.failure_kind is None: return
        self.output.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.output, 0o700)
        target = self.output / (self.name + '-failure.json')
        target.write_text(json.dumps(dict(status='failed', error=self.error,
            diagnostics=self.snapshot()), indent=2) + '\n')
        os.chmod(target, 0o600)

    async def finish(self):
        start = time.monotonic()
        deadline = start + self.cleanup_timeout
        self.write_failure()
        cancelled = None
        async def operation(name, factory, *, limit=1, late_cleanup=None):
            nonlocal cancelled
            self.stage = name
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise TimeoutError('cleanup deadline exceeded')
                await _dto_bounded(factory(), remaining if limit is None else min(limit, remaining),
                                   late_cleanup=late_cleanup)
                return True
            except asyncio.CancelledError as error:
                cancelled = error
                self.diagnostic_errors.append(f'{name}: cancelled')
                self.fail(error, kind='cancelled')
                return False
            except Exception as error:
                self.diagnostic_errors.append(f'{name}: {error}')
                if self.failure_kind is None: self.fail(error)
                return False
        if self.failure_kind is not None and self.page is not None:
            image_path = self.output / (self.name + '-failure.png')
            if await operation('screenshot', lambda: self.page.screenshot(path=str(image_path), timeout=1000),
                               late_cleanup=lambda: image_path.unlink(missing_ok=True)):
                os.chmod(image_path, 0o600)
        trace_path = self.output / (self.name + '-failure-trace.zip')
        def remove_failed_trace():
            try:
                trace_path.unlink(missing_ok=True)
            except OSError as error:
                self.diagnostic_errors.append(f'trace.remove: {error}')
                self.fail(error)
                # A resistant export may complete after finish() returned. Keep
                # its cleanup error visible in both the shared row and disk evidence.
                try: self.write_failure()
                except OSError as write_error:
                    self.diagnostic_errors.append(f'failure.write: {write_error}')
        if self.tracing_started:
            # Stage the trace before close: close itself may be the first failure.
            self.output.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(self.output, 0o700)
            stopped = await operation('trace.stop',
                lambda: self.context.tracing.stop(path=str(trace_path)),
                late_cleanup=remove_failed_trace)
            if not stopped:
                remove_failed_trace()
                self.trace_status = 'timeout' if 'deadline exceeded' in self.diagnostic_errors[-1] else 'failed'
            else:
                try:
                    if not trace_path.is_file():
                        self.trace_status = 'missing'
                        raise RuntimeError('exported trace missing')
                    size = trace_path.stat().st_size
                    if size == 0 or size > 16 * 1024 * 1024:
                        self.trace_status = 'empty' if size == 0 else 'oversize'
                        trace_path.unlink()
                        raise RuntimeError('exported trace empty' if size == 0 else 'exported trace exceeds 16 MiB')
                    os.chmod(trace_path, 0o600)
                    self.trace_status = 'retained'
                    self.trace_path = self.output.name + '/' + trace_path.name
                except Exception as error:
                    self.diagnostic_errors.append(f'trace.stop: {error}')
                    self.fail(error)
        if self.context is not None:
            # The shared deadline, not a fresh per-operation allowance, owns close.
            await operation('context.close', self.context.close, limit=None)
        if self.failure_kind is None and self.trace_path is not None:
            self.stage = 'trace.delete'
            try:
                trace_path.unlink()
                self.trace_status, self.trace_path = 'deleted', None
            except OSError as error:
                self.diagnostic_errors.append(f'trace.delete: {error}')
                self.fail(error)
        self.cleanup_elapsed_seconds = time.monotonic() - start
        self.write_failure()
        if cancelled is not None: raise cancelled


async def run_dto_case(browser, origin, name, output, *, case_timeout=20, cleanup_timeout=3):
    diagnostics = DTODiagnostics(output, name, cleanup_timeout=cleanup_timeout)
    start = time.monotonic()
    task = _dto_task(dto_case(browser, origin, name, output, diagnostics=diagnostics))
    result = None
    try:
        done, _ = await asyncio.wait({task}, timeout=case_timeout)
        if not done:
            diagnostics.fail(TimeoutError('DTO case exceeded 20-second execution watchdog'), kind='case_timeout')
            task.cancel()
        else: result = task.result()
    except asyncio.CancelledError as error:
        diagnostics.fail(error, kind='cancelled')
        task.cancel()
        error.dto_diagnostics=diagnostics
        raise
    except Exception as error:
        diagnostics.fail(error)
    finally:
        diagnostics.execution_elapsed_seconds = time.monotonic() - start
        try:await diagnostics.finish()
        except asyncio.CancelledError as error:
            error.dto_diagnostics=diagnostics
            raise
    if diagnostics.failure_kind is not None:
        return dict(status='failed', error=diagnostics.error, diagnostics=diagnostics.snapshot())
    return result


async def select_vehicle(page, configuration=CONFIG, *, diagnostics=None):
    for field,value in [('year','2024'),('make','fixture-make'),('model','fixture-model'),('configuration',configuration)]:
        if diagnostics is not None: diagnostics.stage = 'vehicle.' + field
        await page.locator('#'+field).select_option(value)
    if diagnostics is not None: diagnostics.stage = 'scenario.' + diagnostics.name + '.actions'


async def open_article(page, *, diagnostics=None):
    if diagnostics is not None: diagnostics.stage = 'article.open.click'
    await page.locator('#articles a').first.click()
    if diagnostics is not None: diagnostics.stage = 'article.open.title'
    await page.locator('#article-title').filter(has_text='Fixture repair procedure').wait_for()
    if diagnostics is not None: diagnostics.stage = 'scenario.' + diagnostics.name + '.actions'


async def assert_text(page, selector, value):
    from playwright.async_api import expect
    await expect(page.locator(selector)).to_contain_text(value)


async def dto_case(browser, origin, name, output, *, diagnostics=None):
    from playwright.async_api import expect
    owns_diagnostics = diagnostics is None
    diagnostics = diagnostics or DTODiagnostics(output, name)
    try:
        def late_context(done):
            if not done.cancelled() and done.exception() is None:
                _dto_task(_dto_bounded(done.result().close(),3))
        context=await _dto_bounded(browser.new_context(ignore_https_errors=True,viewport={'width':390 if name=='keyboard-print-mobile' else 1280,'height':900}),20,late_result_cleanup=late_context)
        diagnostics.context = context
        context.set_default_timeout(10000)
        context.set_default_navigation_timeout(10000)
        diagnostics.stage = 'trace.start'
        diagnostics.trace_status = 'start_failed'
        await context.tracing.start(screenshots=True, snapshots=True, sources=False)
        diagnostics.tracing_started = True
        diagnostics.trace_status = 'recording'
        fixture=DTOFixture(origin,name)
        diagnostics.fixture = fixture
        await context.route('**/*',fixture.route)
        diagnostics.stage = 'page.create'
        page=await context.new_page();diagnostics.page = page;page.on('pageerror',lambda error:fixture.errors.append(str(error)))
        if name == 'google-popup-blocked':
            # Browser popup blocking is exercised at window.open, never by replacing SDK functions.
            await page.add_init_script('window.open=()=>null')
        url=origin+'/workshop/'
        if name in {'checkout-processing-return','checkout-untrusted-return','checkout-expired'}: url+='?order='+ORDER
        diagnostics.stage = 'navigation'
        await page.goto(url)
        diagnostics.stage = 'scenario.' + name + '.actions'
        if name in {'signin-unavailable-local','signin-malformed-config','session-blocked','auth-dependency-unavailable'}:
            await expect(page.locator('#signin')).to_be_disabled()
            await expect(page.locator('#year')).to_be_enabled()
            assert not any('/firebase-web.mjs' in row['path'] for row in fixture.requests)
        elif name.startswith('google-') or name=='firebase-memory-persistence':
            await expect(page.locator('#signin')).to_be_enabled();await page.locator('#signin').click()
            if name=='google-popup-blocked': await assert_text(page,'#account-status','blocked')
            elif name=='google-popup-cancelled': await expect(page.locator('#account-status')).to_contain_text('canceled',timeout=15000)
            elif name=='google-stale-reauthentication':
                await expect(page.locator('#signin')).to_have_text('Confirm Google sign-in');await page.locator('#signin').click();await assert_text(page,'#account-status','Signed in.')
            else: await assert_text(page,'#account-status','Signed in.')
            if name not in {'google-popup-blocked','google-popup-cancelled'}: assert fixture.exchange_count==1
            assert await page.evaluate('Object.keys(localStorage).filter(k=>/firebase|token|csrf/i.test(k))') == []
            assert await page.evaluate('Object.keys(sessionStorage).filter(k=>/firebase|token|csrf/i.test(k))') == []
            stored=await page.evaluate('''async()=>{const result=[];for(const {name} of await indexedDB.databases()){const db=await new Promise((resolve,reject)=>{const r=indexedDB.open(name);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});for(const store of db.objectStoreNames){const values=await new Promise((resolve,reject)=>{const r=db.transaction(store).objectStore(store).getAll();r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});result.push({name,store,values});}db.close();}return JSON.stringify(result);}''')
            assert not re.search(r'firebase:authUser|synthetic-refresh|stsTokenManager|idToken|refreshToken|accessToken',stored), 'SDK credentials persisted in IndexedDB' 
        elif name in {'checkout-processing-return','checkout-untrusted-return','checkout-expired'}:
            if name=='checkout-expired': await assert_text(page,'#activity-text','previous payment attempt ended')
            else: await assert_text(page,'#purchase-message','Do not pay again')
            assert fixture.checkout_count==0
        elif name=='library-pagination-and-states':
            await select_vehicle(page, diagnostics=diagnostics);await assert_text(page,'#articles','Fixture repair procedure');await page.locator('#my-vehicles').click()
            await expect(page.locator('#library-items > li')).to_have_count(4)
            await expect(page.locator('#library-items button')).to_have_count(3)
            await page.locator('#library-more').click();await expect(page.locator('#library-items > li')).to_have_count(5)
            await page.locator('#library-items button').first.click();await assert_text(page,'#articles','Fixture repair procedure')
            assert 'year=' not in page.url and 'configuration='+OTHER in page.url, 'library route retained another vehicle hierarchy'
            await page.reload();await assert_text(page,'#articles','Fixture repair procedure')
        else:
            await select_vehicle(page, diagnostics=diagnostics)
            if name in {'quote-exact-scope','terms-config-unavailable','checkout-double-click-retry'}:
                await assert_text(page,'#purchase-message','purchase' if name!='terms-config-unavailable' else 'unavailable')
                if name=='checkout-double-click-retry':
                    await page.locator('#purchase-action').click();await expect(page.locator('#agreement')).to_be_focused()
                    await page.locator('#agreement').check();await page.locator('#purchase-action').dblclick()
                    await expect(page.locator('#retry')).to_be_visible();await page.locator('#retry').click()
                    await page.wait_for_url('https://checkout.stripe.com/c/pay/fixture')
                    assert fixture.checkout_count==2 and len(set(fixture.keys))==1 and len(set(fixture.checkout_bodies))==1
                elif name=='terms-config-unavailable': await expect(page.locator('#purchase-action')).to_be_disabled()
                else:
                    assert any(row['query'].get('configuration_id')==[CONFIG] and row['query'].get('region')==['US'] for row in fixture.requests if row['path']=='/v1/workshop/quote')
            elif name=='selection-change-in-flight':
                await page.locator('#configuration').select_option(OTHER)
                await assert_text(page,'#articles','Fixture repair procedure');await asyncio.sleep(1.1)
                assert 'Stale configuration' not in await page.locator('#articles').inner_text()
            elif name in {'warm-reload','history-restore','auth-cookie-reload'}:
                await assert_text(page,'#articles','Fixture repair procedure')
                if name=='history-restore':
                    await open_article(page, diagnostics=diagnostics);await page.go_back();await assert_text(page,'#articles','Fixture repair procedure');await page.go_forward();await assert_text(page,'#article-content','Disconnect battery')
                else:
                    await page.reload();await assert_text(page,'#articles','Fixture repair procedure')
                assert not any('/firebase-web.mjs' in row['path'] for row in fixture.requests)
            else:
                if name in {'session-expired','withdrawal'}:
                    await page.locator('#articles a').first.click()
                    await expect(page.locator('#critical-error')).not_to_be_empty()
                else: await open_article(page, diagnostics=diagnostics)
                if name=='pending-no-content':
                    await expect(page.locator('#print')).to_be_disabled();await expect(page.locator('#loading-progress-bar')).not_to_have_attribute('value',re.compile('.+'));await page.locator('#cancel').click()
                elif name=='session-expired': await expect(page.locator('#article-content')).to_be_empty()
                elif name=='withdrawal': await expect(page.locator('#article-content')).to_be_empty();await assert_text(page,'#activity-text','no longer available')
                else:
                    await assert_text(page,'#article-content','Disconnect battery');await expect(page.locator('#article-content td').nth(0)).to_have_text('0');await expect(page.locator('#article-content td').nth(1)).to_have_text('false')
                    if name=='source-to-canonical': await expect(page.locator('#article-kind')).to_have_text('Workshop article')
                    if name in {'source-rewrite-failure','review-required'}: await expect(page.locator('#print')).to_be_enabled()
                    if name in {'source-media-isolation','source-review-change-in-flight'}:
                        await page.locator('#article-reference summary').click();await page.locator('#source-review-load').click()
                        if name=='source-review-change-in-flight':
                            await page.locator('#back').click();await asyncio.sleep(1.1);await expect(page.locator('#source-review-frame')).to_be_empty()
                        else:
                            await assert_text(page,'#source-review-frame','<script>');assert await page.evaluate('globalThis.hostileExecuted') is None
                            assert await page.locator('#source-review-frame img').count()==0
                    if name=='media-renew-coalesced':
                        await expect(page.locator('#article-content img')).to_have_count(2)
                        original=await page.locator('#article-content h3').first.element_handle()
                        fixture.images_release.set()
                        await expect(page.locator('#article-content img').first).to_have_attribute('src',re.compile('renewed'))
                        assert fixture.detail_count==1
                        assert await original.evaluate('(node)=>node.isConnected'), 'unchanged revision replaced content DOM'
                    if name=='missing-media': await expect(page.locator('.image-missing').first).to_be_visible()
                    if name=='paid-prepare-before-poll': assert fixture.prepared
                    if name=='logout-and-bfcache-clear':
                        await page.locator('#signout').click();await expect(page.locator('#article-content')).to_be_empty()
                        await page.evaluate('window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true}))');await expect(page.locator('#article-content')).to_be_empty()
                    if name=='keyboard-print-mobile':
                        await expect(page.locator('#print')).to_be_enabled();await page.emulate_media(media='print');await expect(page.locator('#article-content')).to_be_visible();assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    if name=='cancel-and-retry':
                        await page.locator('#cancel').click();await assert_text(page,'#activity-text','Loading stopped');await page.locator('#retry').click();await assert_text(page,'#activity-text','Article ready.');assert fixture.prepare_count==2
        diagnostics.stage = 'assertions'
        assert not fixture.unexpected, f'unexpected external/application requests: {fixture.unexpected}'
        assert not fixture.errors, f'browser errors: {fixture.errors}'
        return {'status':'passed','requests':fixture.requests,'sdk_requests':sum(row['path']=='/workshop/firebase-web.mjs' for row in fixture.requests)}
    except BaseException as error:
        diagnostics.fail(error)
        raise
    finally:
        if owns_diagnostics: await diagnostics.finish()


API_CASES=(
    'test_browser_google_exchange_checkout_library_real_api',
    'test_browser_owned_source_canonical_and_media_real_api',
    'test_browser_account_scope_and_revocation_real_api',
    'test_browser_signed_refund_blocks_old_links_real_api',
)

API21_VERSION = 'api21-producer-v2'
API21_REASONS = frozenset(('not_observed','unsupported_byte_source','not_required_image_body',
    'over_limit','invalid_json','invalid_utf8','read_failed','secret_detected','launch_failed',
    'timeout','cancelled','assertion_failed','http_failed','close_failed','signal_failed','reap_failed',
    'mapping_unavailable','log_not_finalized','source_binding_failed','publication_failed','prior_failure','internal_error'))
API21_PHASES = {'test_browser_google_exchange_checkout_library_real_api': ('setup', 'metadata', 'initial-measurement', 'signed-in-measurement', 'checkout-first-http', 'checkout-first-delivery', 'response-lost-measurement', 'response-lost-snapshot', 'checkout-retry-http', 'checkout-retry-delivery', 'pending-checkout-measurement', 'retry-pending-snapshot', 'return-without-grant-measurement', 'settlement-control', 'settled-measurement', 'owner-library-initial-http', 'owner-library-reload-http', 'library-reload-measurement', 'restart-before-measurement', 'runtime-before', 'restart-control', 'runtime-poll', 'owner-library-restart-http', 'restart-after-measurement', 'final-measurement'), 'test_browser_owned_source_canonical_and_media_real_api': ('setup', 'metadata', 'initial-measurement', 'signed-in-measurement', 'checkout-http', 'pending-checkout-measurement', 'return-without-grant-measurement', 'settlement-control', 'settled-measurement', 'owner-library-initial-http', 'owner-library-reload-http', 'library-reload-measurement', 'restart-before-measurement', 'runtime-before', 'restart-control', 'runtime-poll', 'owner-library-restart-http', 'restart-after-measurement', 'start-workers-control', 'source-page-http', 'source-image-http', 'source-review-http', 'release-model-control', 'warm-before-snapshot', 'reader-before-measurement', 'warm-page-http', 'warm-image-http', 'warm-pinned-source-http', 'warm-after-snapshot', 'reader-after-measurement', 'final-measurement'), 'test_browser_account_scope_and_revocation_real_api': ('setup', 'metadata', 'initial-measurement', 'signed-in-measurement', 'checkout-http', 'pending-checkout-measurement', 'return-without-grant-measurement', 'settlement-control', 'settled-measurement', 'owner-library-initial-http', 'owner-library-reload-http', 'library-reload-measurement', 'restart-before-measurement', 'runtime-before', 'restart-control', 'runtime-poll', 'owner-library-restart-http', 'restart-after-measurement', 'start-workers-control', 'source-page-http', 'source-image-http', 'source-review-http', 'release-model-control', 'warm-before-snapshot', 'reader-before-measurement', 'warm-page-http', 'warm-image-http', 'warm-pinned-source-http', 'warm-after-snapshot', 'reader-after-measurement', 'adjacent-denial', 'other-region-denial', 'unscoped-article-denial', 'legacy-vehicle-denial', 'other-catalogue-denial', 'other-library-http', 'other-image-denial', 'logout-image-denial', 'disable-control', 'disabled-image-denial', 'final-measurement'), 'test_browser_signed_refund_blocks_old_links_real_api': ('setup', 'metadata', 'initial-measurement', 'signed-in-measurement', 'checkout-http', 'pending-checkout-measurement', 'return-without-grant-measurement', 'settlement-control', 'settled-measurement', 'owner-library-initial-http', 'owner-library-reload-http', 'library-reload-measurement', 'restart-before-measurement', 'runtime-before', 'restart-control', 'runtime-poll', 'owner-library-restart-http', 'restart-after-measurement', 'start-workers-control', 'source-page-http', 'source-image-http', 'source-review-http', 'release-model-control', 'warm-before-snapshot', 'reader-before-measurement', 'warm-page-http', 'warm-image-http', 'warm-pinned-source-http', 'warm-after-snapshot', 'reader-after-measurement', 'refund-control', 'refund-old-image-denial', 'refund-source-denial', 'refund-detail-denial', 'revoked-measurement', 'final-measurement')}
API21_ALL_MISSING = (
    'lost_response_pending_measurement_and_snapshot_raw',
    'checkout_idempotency_key_request_response_bytes_and_body_hashes',
    'other_account_denial_http_status_and_response_bytes',
    'logout_disable_revocation_http_observations')
API21_MISSING = (
    'actual_child_go_browser_exit_receipts','parent_pytest_exit_and_command_receipts',
    'signed_settlement_refund_http_bytes_and_authentic_delivery',
    'runtime_image_browser_cache_sdk_install_identity','authenticated_capture_source_observer_and_containment',
    'global_worker_log_per_case_ownership_mapping','finite_api_success_schedule',
    'junit_byte_preserving_capture_mapping','all_final180_families_and_profile_promotion',
    'independent_authentic_raw_review','actual_engine_os_exit_and_descendant_reap',
    'original_go_webhook_request_signature_response_capture','source_contract_current_integration_rebinding',
    'dto_trace_16MiB_producer_8MiB_consumer_conflict','v2_consumer_schema_validator_and_profile',
    'producer_observations_are_unexecuted_until_separate_capture_gate')


class APIObservationError(ValueError):
    pass


def api21_json(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8',errors='strict')


def api21_load(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate key')
            result[key]=value
        return result
    def constant(value):raise ValueError('nonfinite JSON')
    value=json.loads(raw.decode('utf-8',errors='strict'),object_pairs_hook=pairs,parse_constant=constant)
    api21_json(value)  # Reject unpaired surrogates and nonfinite float overflow.
    return value


def api21_body(raw, source, *, image=False, reason=None, json_required=True):
    body=dict(availability='unavailable',byte_source='unavailable',encoding=None,
        base64=None,length=None,sha256=None,parsed=None,reason=reason or 'not_observed')
    if reason:return body
    if not isinstance(raw,bytes):body['reason']='unsupported_byte_source';return body
    if len(raw)>131072:body['reason']='over_limit';return body
    if image:
        return dict(body,availability='hash_only',byte_source=source,length=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),reason='not_required_image_body')
    decode_reason=None
    try:parsed=api21_load(raw)
    except UnicodeError:parsed=None;decode_reason='invalid_utf8'
    except (ValueError,TypeError,RecursionError):
        parsed=None;decode_reason='invalid_json' if json_required else None
    # Retain safe entity bytes, including strict-decode failures. Never retain authentication responses,
    # headers, cookies or exception text, even when persistence itself fails.
    secret=re.compile(r'(?i)^(authorization|cookie|set-cookie|token|id_?token|access_?token|refresh_?token|password|csrf(?:_?token)?|firebase_?token|api_?key|client_secret|fixture_token|x-r3-fixture-token)$')
    def sensitive(value):
        if isinstance(value,dict):return any(secret.fullmatch(k) or sensitive(v) for k,v in value.items())
        if isinstance(value,list):return any(sensitive(v) for v in value)
        return isinstance(value,str) and bool(re.search(r'(?i)(bearer |__Host-autodata_session=|eyJ[A-Za-z0-9_-]+\.eyJ)',value))
    text=raw.decode('utf-8',errors='replace')
    raw_secret=any(secret.fullmatch(key) for key in re.findall(r'[\"\']([^\"\']+)[\"\']\s*:',text))
    # A malformed outer entity can still contain valid escaped JSON strings.
    # Decode those strings independently so escaped secret keys/tokens cannot
    # bypass the privacy check merely because the full entity did not parse.
    escaped_secret=False
    for match in re.finditer(r'"(?:\\.|[^"\\])*"',text):
        try:value=api21_load(match.group().encode('utf-8'))
        except (ValueError,UnicodeError,TypeError,RecursionError):continue
        if sensitive(value) or secret.fullmatch(value) and text[match.end():].lstrip().startswith(':'):
            escaped_secret=True;break
    if sensitive(parsed) or sensitive(text) or raw_secret or escaped_secret:body['reason']='secret_detected';return body
    return dict(body,availability='retained',byte_source=source,encoding='base64',
        base64=base64.b64encode(raw).decode('ascii'),length=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),parsed=parsed,reason=decode_reason)


def api21_route(url,scope=None):
    path=urlsplit(url).path
    if path.startswith('/__fixture/'):
        allowed=('metadata','measurement','snapshot','runtime','restart','stop','disable',
            'payment/settle','payment/refund','control/start-workers','control/release-model')
        return path if path[len('/__fixture/'):] in allowed else None
    if path in ('/v1/workshop/checkout-sessions','/v1/workshop/library','/v1/workshop/quote'):return path
    uuid=r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}'
    if re.fullmatch('/v1/workshop/orders/'+uuid,path):return '/v1/workshop/orders/{order}'
    if re.fullmatch(r'/v1/catalog/images/v2[.][^/]+',path):return '/v1/catalog/images/{capability}'
    match=re.fullmatch('/v1/catalog/vehicles/('+uuid+')/articles(?:/('+uuid+')(?:/(source))?)?',path)
    if not match:return None
    vehicle,article,source=match.groups();scope=scope or {}
    vehicle_name=next((key for key in ('configuration','adjacent','other_region','vehicle') if scope.get(key)==vehicle),'configuration')
    safe='/v1/catalog/vehicles/{'+vehicle_name+'}/articles'
    if article:safe+='/{'+('unscoped' if scope.get('unscoped')==article else 'article')+'}'
    if source:safe+='/source'
    return safe


def api21_checkout_identity(request,response,key):
    uuid_pattern=r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}'
    if not isinstance(key,str) or not re.fullmatch(uuid_pattern,key):raise ValueError('invalid key')
    if not request or request['availability']!='retained' or response['availability']!='retained':raise ValueError('original body unavailable')
    posted=request['parsed'];checkout=response['parsed']
    if not isinstance(posted,dict) or not isinstance(checkout,dict):raise ValueError('invalid JSON object')
    if checkout.get('version')!='v1' or checkout.get('state')!='checkout':raise ValueError('invalid state')
    if posted.get('configuration_id')!=checkout.get('configuration_id') or posted.get('region')!='US' or checkout.get('region')!='US':raise ValueError('invalid scope')
    for field in ('configuration_id','order_id'):
        if not isinstance(checkout.get(field),str) or not re.fullmatch(uuid_pattern,checkout[field]):raise ValueError('invalid identity')
    hosted=checkout.get('checkout_url')
    if not isinstance(hosted,str):raise ValueError('invalid hosted checkout')
    url=urlsplit(hosted)
    if not isinstance(hosted,str) or url.scheme!='https' or url.netloc!='checkout.stripe.com' or not re.fullmatch(r'/c/pay/cs_test_[a-f0-9]{32}',url.path) or url.query:raise ValueError('invalid hosted checkout')
    return {field:checkout[field] for field in ('order_id','configuration_id','region','checkout_url')}


def api21_validate_body(body):
    keys={'availability','byte_source','encoding','base64','length','sha256','parsed','reason'}
    if not isinstance(body,dict) or set(body)!=keys:raise ValueError('invalid body shape')
    available=body['availability'];source=body['byte_source'];reason=body['reason']
    if available=='unavailable':
        if source!='unavailable' or reason not in API21_REASONS or any(body[k] is not None for k in ('encoding','base64','length','sha256','parsed')):raise ValueError('invalid unavailable body')
        return
    if source not in ('playwright-request-post-data-buffer','playwright-response-body') or type(body['length']) is not int or not 0<=body['length']<=131072 or not isinstance(body['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',body['sha256']):raise ValueError('invalid body provenance')
    if available=='hash_only':
        if reason!='not_required_image_body' or source!='playwright-response-body' or any(body[k] is not None for k in ('encoding','base64','parsed')):raise ValueError('invalid hash-only body')
        return
    if available!='retained' or reason not in (None,'invalid_json','invalid_utf8') or body['encoding']!='base64' or not isinstance(body['base64'],str):raise ValueError('invalid retained body')
    raw=base64.b64decode(body['base64'],validate=True)
    if base64.b64encode(raw).decode('ascii')!=body['base64'] or len(raw)!=body['length'] or hashlib.sha256(raw).hexdigest()!=body['sha256']:raise ValueError('body digest mismatch')
    if reason is not None:
        checked=api21_body(raw,source)
        if checked!=body:raise ValueError('invalid failed JSON body')
        return
    if raw==b'' and body['parsed'] is None:return  # Actual no-content response.
    parsed=api21_load(raw)
    if api21_json(parsed)!=api21_json(body['parsed']):raise ValueError('body parsed mismatch')


def api21_validate_payload(payload,phase):
    if not isinstance(payload,dict):raise ValueError('payload object required')
    kind=payload.get('kind')
    if kind=='lifecycle':
        if set(payload)!={'kind','operation','state','reason'} or payload['operation'] not in ('setup','context-create','page-create','metadata','browser-launch','context-close','browser-close','fixture-stop','worker-start','worker-stop','runtime-close','publish') or payload['state'] not in ('requested','completed','failed','unavailable'):raise ValueError('invalid lifecycle')
    elif kind=='producer-assertion':
        if set(payload)!={'kind','name','result','reason'} or not isinstance(payload['name'],str) or len(payload['name'])>128 or (payload['result'] is not None and type(payload['result']) is not bool):raise ValueError('invalid assertion')
    elif kind=='checkout-delivery':
        if set(payload)!={'kind','attempt','state','http_event'} or type(payload['attempt']) is not int or not 1<=payload['attempt']<=2 or payload['state'] not in ('fetch-completed','response-abort-requested','response-aborted','response-fulfill-requested','response-fulfilled'):raise ValueError('invalid delivery')
    elif kind=='http':
        keys={'kind','channel','method','route_template','actor','attempt','status','idempotency_key','request','response','checkout_identity'}
        if set(payload)!=keys or payload['channel'] not in ('application','fixture-control') or payload['method'] not in ('GET','POST') or payload['actor'] not in ('owner','other','logged-out','disabled','fixture-control'):raise ValueError('invalid HTTP shape')
        expected=2 if phase=='checkout-retry-http' else 1
        limit=100 if phase=='runtime-poll' else 16 if phase in ('owner-library-initial-http','owner-library-reload-http','owner-library-restart-http') else expected
        if type(payload['attempt']) is not int or not expected<=payload['attempt']<=limit:raise ValueError('invalid attempt')
        if payload['status'] is not None and (type(payload['status']) is not int or not 100<=payload['status']<=599):raise ValueError('invalid status')
        route=payload['route_template']
        if not isinstance(route,str) or len(route)>128 or '?' in route or not route.startswith(('/__fixture/','/v1/')):raise ValueError('invalid route')
        api21_validate_body(payload['response'])
        if payload['request'] is not None:api21_validate_body(payload['request'])
        key=payload['idempotency_key']
        if key is not None and (route!='/v1/workshop/checkout-sessions' or not isinstance(key,str) or not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',key)):raise ValueError('invalid checkout key')
        if payload['checkout_identity'] is not None and payload['checkout_identity']!=api21_checkout_identity(payload['request'],payload['response'],key):raise ValueError('invalid checkout identity')
    else:raise ValueError('unknown payload')
    if 'reason' in payload and payload['reason'] is not None and payload['reason'] not in API21_REASONS:raise ValueError('invalid reason')


class APIObservations:
    """One bounded producer stream; failures and original bytes are sticky."""
    def __init__(self,binding,*,max_events=512,max_bytes=1048576,clock=time.monotonic):
        self.binding=dict(binding);self.primary=None
        self.status='partial';self.publication='not_attempted';self.phase='setup'
        self.clock=clock;self.start=clock();self.max_events=min(max_events,512)
        self.max_bytes=min(max_bytes,1048576);self.tasks=set();self.counts={};self.pending={};self.started_counts={};self.capturing=set();self.responses={}
        self._slots=[None]*self.max_events;self._count=0;self.last=self.start
        self.reserve=bytearray(16384);self.scope={};self.owner_scope=None
    @property
    def events(self):return self._slots[:self._count]
    def fail(self,reason):
        if reason not in API21_REASONS:reason='internal_error'
        if self.primary is None:self.primary=reason
        self.status='failed'
    def snapshot(self):
        return dict(binding=self.binding,status=self.status,events=list(self.events),
            primary_failure=self.primary,publication=self.publication,
            unavailable_families=list(API21_MISSING+(API21_ALL_MISSING if self.status!='passed' else ())),engine_os_exit=None,outer_pytest_exit=None)
    def event(self,phase,payload,caused_by=()):
        try:
            api21_validate_payload(payload,phase)
            if payload['kind']=='http' and any(e['phase']==phase and e['payload']['kind']=='http' and e['payload']['attempt']==payload['attempt'] for e in self.events):raise ValueError('duplicate attempt')
            if phase not in set().union(*API21_PHASES.values()):raise ValueError('unknown phase')
            if len(caused_by)>8:raise ValueError('too many references')
            def checked_ref(ref):
                if not isinstance(ref,dict) or set(ref)!={'stream','producer_role','seq'} or ref['stream']!='observations' or ref['producer_role']!='browser-runner' or type(ref['seq']) is not int or not 1<=ref['seq']<=self._count:raise ValueError('unobserved reference')
                return self._slots[ref['seq']-1]
            for ref in caused_by:checked_ref(ref)
            if payload['kind']=='checkout-delivery':
                original=checked_ref(payload['http_event'])['payload']
                if original['kind']!='http' or original['route_template']!='/v1/workshop/checkout-sessions' or original['attempt']!=payload['attempt']:raise ValueError('invalid delivery cause')
            now=self.clock()
            if type(now) not in (int,float) or not float('-inf')<now<float('inf') or now<self.last:raise ValueError('invalid local clock')
            self.last=now
        except (ValueError,TypeError,KeyError,UnicodeError,RecursionError):
            self.fail('internal_error');raise APIObservationError('internal_error') from None
        event=dict(seq=len(self.events)+1,phase=phase,caused_by=list(caused_by),
            elapsed_us=int((now-self.start)*1000000),payload=payload)
        try:
            size=len(api21_json(event));candidate=dict(self.snapshot(),events=self.events+[event],
                status='partial',primary_failure=max(API21_REASONS,key=len))
            if len(self.events)>=self.max_events or size>262144 or len(api21_json(candidate))>self.max_bytes:
                raise APIObservationError('over_limit')
        except (ValueError,UnicodeError,TypeError,RecursionError):
            self.fail('over_limit');raise APIObservationError('over_limit') from None
        self._slots[self._count]=event;self._count+=1
        return dict(stream='observations',producer_role='browser-runner',seq=event['seq'])
    def lifecycle(self,phase,operation,state,reason=None):
        return self.event(phase,dict(kind='lifecycle',operation=operation,state=state,reason=reason))
    def note_lifecycle(self,phase,operation,state,reason=None):
        try:return self.lifecycle(phase,operation,state,reason)
        except APIObservationError:return None
    def assertion(self,name,result):
        if not result:self.fail('assertion_failed')
        self.event(self.phase,dict(kind='producer-assertion',name=name,result=result,
            reason=None if result else 'assertion_failed'))
    async def http(self,response,url,method='GET',*,phase=None,actor='owner',request=None,key=None,identity=None,attempt=None):
        phase=phase or self.phase;safe=api21_route(url,self.scope)
        if safe is None:return None
        count=self.counts.get(phase,0)+1
        self.counts[phase]=count
        ordinal=2 if phase=='checkout-retry-http' and count==1 else count
        if attempt is not None:ordinal=attempt
        limit=100 if phase=='runtime-poll' else 16 if phase in ('owner-library-initial-http','owner-library-reload-http','owner-library-restart-http') else 2 if phase=='checkout-retry-http' else 1
        if count>limit:
            self.fail('over_limit');raise APIObservationError('over_limit')
        try:
            raw=await response.body()
            empty_control=phase in ('stop-control','restart-control','disable-control') and response.status==204 and raw==b''
            body=api21_body(raw,'playwright-response-body',image='/images/' in safe and response.status==200,
                json_required=not empty_control)
        except Exception:body=api21_body(None,'unavailable',reason='read_failed')
        status=getattr(response,'status',None)
        if type(status) is not int or not 100<=status<=599:status=None
        if status is None or body['availability']=='unavailable' or body['reason'] in ('invalid_json','invalid_utf8'):self.fail(body['reason'] if body['reason'] in ('over_limit','secret_detected') else 'http_failed')
        if safe=='/v1/workshop/checkout-sessions':
            try:identity=api21_checkout_identity(request,body,key)
            except (ValueError,TypeError,KeyError):
                identity=None
                self.fail('assertion_failed')
            if not isinstance(key,str) or not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',key):key=None
        payload=dict(kind='http',channel='fixture-control' if safe.startswith('/__fixture/') else 'application',
            method=method,route_template=safe,actor='fixture-control' if safe.startswith('/__fixture/') else actor,
            attempt=ordinal,status=status,idempotency_key=key,request=request,response=body,
            checkout_identity=identity)
        ref=self.event(phase,payload)
        if status is None or body['availability']=='unavailable' or body['reason'] in ('invalid_json','invalid_utf8'):self.fail(body['reason'] if body['reason'] in ('over_limit','secret_detected') else 'http_failed')
        return ref
    def _page_owns(self,phase,url):
        safe=api21_route(url,self.scope)
        if phase.startswith('owner-library-'):return safe=='/v1/workshop/library'
        if phase=='checkout-http':return safe=='/v1/workshop/checkout-sessions'
        source='/v1/catalog/vehicles/{configuration}/articles/{article}'
        if phase in ('source-page-http','warm-page-http'):return safe==source
        if phase=='source-review-http':return safe==source+'/source'
        return False
    def page_request(self,request):
        phase=self.phase
        if not self._page_owns(phase,request.url):return
        if len(self.pending)>=512:self.fail('over_limit');return
        key=id(request)
        if key in self.pending:self.fail('http_failed');return
        ordinal=self.started_counts.get(phase,0)+1;self.started_counts[phase]=ordinal
        self.pending[key]=(request,phase,asyncio.get_running_loop().create_future(),ordinal)
    def page_response(self,response):
        self._page_complete(response.request,response)
    def page_request_failed(self,request):
        self._page_complete(request,None)
    def _page_complete(self,request,response):
        owned=self.pending.get(id(request))
        if owned is None:
            # Response-time labels cannot establish an initiating action window.
            if self._page_owns(self.phase,request.url):self.fail('http_failed')
            return
        original,phase,done,ordinal=owned
        if original is not request or done.done() or id(request) in self.capturing:self.fail('http_failed');return
        self.capturing.add(id(request));self.responses[id(request)]=response
        async def capture():
            try:
                body=None;key=None
                if phase=='checkout-http':
                    body=api21_body(getattr(request,'post_data_buffer',None),'playwright-request-post-data-buffer')
                    key=request.headers.get('idempotency-key')
                await self.http(response,request.url,request.method,phase=phase,request=body,key=key,attempt=ordinal)
            except BaseException as error:
                self.fail('cancelled' if isinstance(error,asyncio.CancelledError) else 'http_failed')
                try:self._unavailable_page_request(request,phase,ordinal,response)
                except APIObservationError:pass
            finally:
                self.pending.pop(id(request),None);self.capturing.discard(id(request));self.responses.pop(id(request),None)
                if not done.done():done.set_result(None)
        if len(self.tasks)>=512:self.fail('over_limit');return
        task=asyncio.create_task(capture());self.tasks.add(task)
    async def drain(self):
        # Includes requests whose headers have not arrived yet. The existing
        # case deadline bounds this await; no new timeout or polling is added.
        while self.pending or self.tasks:
            tasks=list(self.tasks);self.tasks.difference_update(tasks)
            await asyncio.gather(*tasks,*(entry[2] for entry in list(self.pending.values())))
    def _unavailable_page_request(self,request,phase,ordinal,response):
        if any(e['phase']==phase and e['payload']['kind']=='http' and e['payload']['attempt']==ordinal for e in self.events):return
        safe=api21_route(request.url,self.scope);body=None;key=None
        if phase=='checkout-http':
            body=api21_body(getattr(request,'post_data_buffer',None),'playwright-request-post-data-buffer')
            key=request.headers.get('idempotency-key')
            if not isinstance(key,str) or not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',key):key=None
        status=getattr(response,'status',None)
        if type(status) is not int or not 100<=status<=599:status=None
        self.event(phase,dict(kind='http',channel='application',method=request.method,route_template=safe,
            actor='owner',attempt=ordinal,status=status,idempotency_key=key,request=body,
            response=api21_body(None,'unavailable',reason='read_failed'),checkout_identity=None))
    async def abandon_pending(self):
        # Terminal cleanup follows context.close(). Never await missing headers
        # or a transport-dependent body to retain an already attempted request.
        pending=[(entry,self.responses.get(key)) for key,entry in self.pending.items()]
        tasks=list(self.tasks);self.tasks.clear()
        for task in tasks:task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        for (request,phase,done,ordinal),response in pending:
            try:self._unavailable_page_request(request,phase,ordinal,response)
            except APIObservationError:pass  # Preserve the bounded prefix and sticky failure.
            finally:
                self.pending.pop(id(request),None);self.capturing.discard(id(request));self.responses.pop(id(request),None)
                if not done.done():done.set_result(None)
    def require_window(self,phase):
        events=[e['payload'] for e in self.events if e['phase']==phase and e['payload']['kind']=='http']
        def owner_item(payload):
            body=payload['response'];parsed=body['parsed']
            if not (payload['status']==200 and body['availability']=='retained' and isinstance(parsed,dict) and isinstance(parsed.get('items'),list) and len(parsed['items'])==1):return False
            if self.owner_scope is None:return True
            configuration,order=self.owner_scope;item=parsed['items'][0]
            return isinstance(item,dict) and item.get('library_item_id')==order and item.get('configuration_id')==configuration and item.get('region')=='US' and item.get('access_state') in ('paid','preparing','viewable')
        if not 1<=len(events)<=16 or not all(e['response']['availability']=='retained' and e['status']==200 for e in events) or not any(owner_item(e) for e in events):
            self.fail('assertion_failed');raise APIObservationError('assertion_failed')
    def complete_case(self,name):
        expected=API21_PHASES[name]
        observed=list(dict.fromkeys(e['phase'] for e in self.events))
        if tuple(observed)!=expected:self.fail('assertion_failed')
        ranks={phase:index for index,phase in enumerate(expected)};last=-1
        for event in self.events:
            rank=ranks.get(event['phase'],-1)
            if rank<last:self.fail('assertion_failed')
            last=max(last,rank)
        if name==API_CASES[0]:
            for phase,states in (('checkout-first-delivery',('fetch-completed','response-abort-requested','response-aborted')),
                    ('checkout-retry-delivery',('fetch-completed','response-fulfill-requested','response-fulfilled'))):
                actual=tuple(e['payload'].get('state') for e in self.events if e['phase']==phase and e['payload']['kind']=='checkout-delivery')
                if actual!=states:self.fail('assertion_failed')
        for phase in expected:
            if phase.startswith('owner-library-'):
                try:self.require_window(phase)
                except APIObservationError:pass
        for phase in expected:
            events=[e['payload'] for e in self.events if e['phase']==phase and e['payload']['kind']=='http']
            if phase=='setup' or phase.endswith('-delivery'):continue
            if not events:self.fail('assertion_failed');continue
            repeat=phase.startswith('owner-library-') or phase in ('source-page-http','source-review-http','warm-page-http','runtime-poll')
            if not repeat and len(events)!=1:self.fail('assertion_failed')
            for event in events:
                status=event['status'];body=event['response']
                allowed=(403,404) if phase in ('adjacent-denial','other-region-denial','unscoped-article-denial','legacy-vehicle-denial') else (404,) if phase=='other-image-denial' else (401,) if phase in ('logout-image-denial','disabled-image-denial') else (403,) if 'denial' in phase else (200,201) if phase.startswith('checkout') else (200,204) if phase.endswith('-control') else (200,)
                if status not in allowed or body['availability']=='unavailable':self.fail('http_failed')
                if phase.endswith('-image-http') and (body['length'] is None or body['length']<=0):self.fail('http_failed')
                if phase.startswith('checkout') and (event['request'] is None or event['request']['availability']!='retained' or event['checkout_identity'] is None):self.fail('assertion_failed')
        self.finish()
    def finish(self):
        self.status='failed' if self.primary else 'passed'


def api21_write_bytes(target,raw):
    """Confined same-directory replacement; never follow or replace links."""
    if not isinstance(raw,bytes) or len(raw)>8388608:raise APIObservationError('over_limit')
    parent=target.parent
    for directory in (parent,*parent.parents):
        if directory.is_symlink():raise OSError('unsafe output directory')
    directory=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    info=os.fstat(directory)
    if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
        os.close(directory);raise OSError('unsafe output directory')
    temp='.api21-'+os.urandom(16).hex()+'.tmp';owned=None
    def identity():
        try:
            info=os.stat(target.name,dir_fd=directory,follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise OSError('unsafe output')
            return (info.st_dev,info.st_ino)
        except FileNotFoundError:return None
    try:
        original=identity()
        descriptor=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
        info=os.fstat(descriptor);owned=(info.st_dev,info.st_ino)
        with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        info=os.stat(temp,dir_fd=directory,follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or (info.st_dev,info.st_ino)!=owned:raise OSError('temporary replaced')
        if identity()!=original:raise OSError('output replaced')
        os.replace(temp,target.name,src_dir_fd=directory,dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            if owned is not None:
                info=os.stat(temp,dir_fd=directory,follow_symlinks=False)
                if (info.st_dev,info.st_ino)==owned:os.unlink(temp,dir_fd=directory)
        except FileNotFoundError:pass
        finally:os.close(directory)


def api21_write(target,value):
    raw=api21_json(value)
    if len(raw)>4194304:raise APIObservationError('over_limit')
    api21_write_bytes(target,raw)


def api21_publish(target,evidence,observations):
    observations.publication='written'
    try:
        api21_write(target,evidence);return True
    except Exception:
        observations.fail('publication_failed');observations.publication='failed'
        observations.reserve=None
        # A bounded last attempt retains binding and failure, without asserting
        # that the full prefix or unavailable legacy fields were persisted.
        minimal=dict(api_observability_version=API21_VERSION,binding=observations.binding,
            version='v1',mode='api-fixture',candidate_sha=observations.binding.get('candidate_sha'),
            results=[dict(browser=observations.binding.get('engine'),scenario=observations.binding.get('root'),
                status='failed',observations=dict(observations.snapshot(),events=[]))])
        try:api21_write(target,minimal)
        except Exception:print('API21_PUBLICATION_FAILED',file=sys.stderr)
        return False


class APIFixture(DTOFixture):
    def __init__(self,origin,scenario,observations=None):
        super().__init__(origin,scenario)
        self.observations=observations
        self.lost_response_count=0
        # Exact request/response identities stay in memory, never browser evidence.
        self.checkout_responses=[]
        self.checkout_raws=[]

    async def route(self,route):
        request=route.request
        if request.url.startswith(self.origin+'/'):
            path=urlsplit(request.url).path
            # Observe safe route templates only. Never manufacture an app response.
            safe=re.sub(r'/v2\.[^/?]+','/{capability}',path)
            safe=re.sub(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}','{uuid}',safe)
            self.requests.append({'method':request.method,'path':safe})
            if request.headers.get('authorization'):self.errors.append('browser sent bearer authorization')
            if self.scenario==API_CASES[0] and request.method=='POST' and path=='/v1/workshop/checkout-sessions':
                # Reserve the one-shot before awaiting the real API. A concurrent
                # activation must fail rather than hide another checkout response.
                self.checkout_count+=1
                attempt=self.checkout_count
                assert attempt<=2, 'checkout must have exactly one manual retry'
                if attempt==2:
                    assert self.lost_response_count==1, 'retry preceded the completed response loss'
                key=request.headers.get('idempotency-key')
                uuid_pattern=r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}'
                assert isinstance(key,str) and re.fullmatch(uuid_pattern,key), 'checkout key must be a UUID'
                try:body=api21_load(request.post_data_buffer) if self.observations else json.loads(request.post_data)
                except (TypeError,ValueError):raise AssertionError('checkout request must be JSON') from None
                assert isinstance(body,dict), 'checkout request must be an object'
                configuration=body.get('configuration_id')
                assert isinstance(configuration,str) and re.fullmatch(uuid_pattern,configuration), 'invalid checkout configuration'
                assert body.get('region')=='US', 'unexpected checkout region'
                if attempt==2:
                    assert key==self.keys[0] and request.post_data==self.checkout_bodies[0], 'retry changed checkout request'
                if self.observations:
                    if attempt==2:assert request.post_data_buffer==self.checkout_raws[0], 'retry changed original request bytes'
                    self.checkout_raws.append(request.post_data_buffer)
                self.keys.append(key);self.checkout_bodies.append(request.post_data)
                try:response=await route.fetch(max_redirects=0,max_retries=0)
                except BaseException:
                    if self.observations:
                        await self.observations.http(None,request.url,'POST',
                            phase='checkout-first-http' if attempt==1 else 'checkout-retry-http',
                            request=api21_body(request.post_data_buffer,'playwright-request-post-data-buffer'),key=key,attempt=attempt)
                    raise
                http_ref=None
                phase='checkout-first-http' if attempt==1 else 'checkout-retry-http'
                if self.observations:
                    http_ref=await self.observations.http(response,request.url,'POST',phase=phase,
                        request=api21_body(request.post_data_buffer,'playwright-request-post-data-buffer'),key=key,attempt=attempt)
                assert response.status in (200,201), 'actual API did not complete checkout'
                checkout=self.observations.events[http_ref['seq']-1]['payload']['response']['parsed'] if self.observations else await response.json()
                assert isinstance(checkout,dict) and checkout.get('version')=='v1' and checkout.get('state')=='checkout', 'invalid actual checkout response'
                assert checkout.get('configuration_id')==configuration and checkout.get('region')==body['region'], 'checkout response changed scope'
                order=checkout.get('order_id');hosted=checkout.get('checkout_url')
                assert isinstance(order,str) and re.fullmatch(uuid_pattern,order), 'invalid checkout order'
                assert isinstance(hosted,str) and allowed_external(hosted), 'untrusted hosted checkout'
                hosted_url=urlsplit(hosted)
                assert hosted_url.hostname=='checkout.stripe.com' and re.fullmatch(r'/c/pay/cs_test_[a-f0-9]{32}',hosted_url.path) and not hosted_url.query, 'invalid hosted checkout session'
                identity={'order_id':order,'configuration_id':configuration,'region':body['region'],'checkout_url':hosted}
                if self.observations:
                    def delivery(state):
                        self.observations.event(phase.replace('-http','-delivery'),
                            dict(kind='checkout-delivery',attempt=attempt,state=state,http_event=http_ref),[http_ref])
                    delivery('fetch-completed')
                if attempt==1:
                    self.checkout_responses.append(identity)
                    if self.observations:delivery('response-abort-requested')
                    await route.abort()
                    if self.observations:delivery('response-aborted')
                    self.lost_response_count+=1
                else:
                    assert identity==self.checkout_responses[0], 'retry changed actual checkout identity'
                    self.checkout_responses.append(identity)
                    if self.observations:delivery('response-fulfill-requested')
                    await route.fulfill(response=response)
                    if self.observations:delivery('response-fulfilled')
                return
            await route.continue_();return
        if not allowed_external(request.url):
            self.unexpected.append(urlsplit(request.url).hostname);await route.abort();return
        await self.external(route)

    def validate_pending_checkout(self,measurement,snapshot,previous_snapshot=None):
        assert self.lost_response_count==1 and self.checkout_count in (1,2)
        assert len(self.checkout_responses)==self.checkout_count
        checkout=self.checkout_responses[0]
        assert measurement['workshop_orders']==1 and measurement['workshop_checkout_requests']==1 and measurement['entitlements']==0
        assert len(measurement['orders'])==1
        order=measurement['orders'][0]
        assert order['state']=='open'
        for field in ('order_id','configuration_id','region'):assert order[field]==checkout[field]
        rows=snapshot['paid_rows']
        assert len(rows['workshop_orders'])==1 and rows['entitlements']==[]
        durable=rows['workshop_orders'][0]
        assert durable['status']=='open'
        for field in ('order_id','configuration_id','region'):assert durable[field]==checkout[field]
        assert durable['checkout_session_id']==urlsplit(checkout['checkout_url']).path.rsplit('/',1)[1]
        assert snapshot['payment_calls']>0
        if previous_snapshot is not None:
            assert snapshot['payment_calls']==previous_snapshot['payment_calls'], 'retry created provider work'

async def api21_get(context,url,*,phase=None,actor='owner',**kwargs):
    observations=getattr(context,'_api21',None)
    if observations and phase:
        await observations.drain();observations.phase=phase
    try:response=await context.request.get(url,**kwargs)
    except BaseException as error:
        if observations:
            observations.fail('cancelled' if isinstance(error,asyncio.CancelledError) else 'http_failed')
            await observations.http(None,url,phase=phase,actor=actor)
        raise
    if observations:await observations.http(response,url,phase=phase,actor=actor)
    return response


async def api_measure(context,origin,phase=None):
    response=await api21_get(context,origin+'/__fixture/measurement',phase=phase)
    assert response.status==200
    return await response.json()

async def api_control(context,origin,path,phase=None):
    observations=getattr(context,'_api21',None)
    if observations:
        await observations.drain()
        if phase:observations.phase=phase
    try:response=await context.request.post(origin+'/__fixture/'+path)
    except BaseException as error:
        if observations:
            observations.fail('cancelled' if isinstance(error,asyncio.CancelledError) else 'http_failed')
            await observations.http(None,origin+'/__fixture/'+path,'POST',phase=phase)
        raise
    if observations:await observations.http(response,origin+'/__fixture/'+path,'POST',phase=phase)
    assert response.status in (200,204), f'owned fixture control failed: {path.split("?")[0]} status{response.status}'
    return response

async def api_signin(page):
    from playwright.async_api import expect
    await expect(page.locator('#signin')).to_be_enabled()
    await page.locator('#signin').click()
    await expect(page.locator('#account-status')).to_have_text('Signed in.',timeout=10000)

def validate_warm_runtime(before,after,reader_before,reader_after):
    for field in ('provider_calls','source_calls','asset_calls','model_calls','counts','immutable_sha256'):
        assert before[field]==after[field], 'warm canonical read changed '+field
    assert before['model_calls']>0 and before['counts']['published_revisions']==1
    assert reader_after>reader_before, 'explicit approved image delivery did not reach actual S3 reader'


async def api_snapshot(context,origin,phase=None):
    response=await api21_get(context,origin+'/__fixture/snapshot',phase=phase)
    assert response.status==200
    return await response.json()


class APIAssertions(dict):
    def __init__(self,observations):super().__init__();self.observations=observations
    def __setitem__(self,name,value):
        if self.observations:self.observations.assertion(name,value)
        super().__setitem__(name,value)


async def api_case(browser,origin,name,output,observations=None):
    from playwright.async_api import expect
    context=page=None;failure=None;result=None
    transport=APIFixture(origin,name,observations=observations)
    assertions=APIAssertions(observations);restart_receipt={};warm_receipt={}
    try:
        if observations:observations.note_lifecycle('setup','context-create','requested')
        context=await browser.new_context(ignore_https_errors=True,viewport={'width':1280,'height':900})
        if observations:
            context._api21=observations
            observations.note_lifecycle('setup','context-create','completed')
        await context.route('**/*',transport.route)
        if observations:observations.note_lifecycle('setup','page-create','requested')
        page=await context.new_page()
        if observations:
            observations.note_lifecycle('setup','page-create','completed')
            page.on('request',observations.page_request)
            page.on('response',observations.page_response)
            page.on('requestfailed',observations.page_request_failed)
        page.on('pageerror',lambda error:transport.errors.append('internal_error'))
        response=await api21_get(context,origin+'/__fixture/metadata',phase='metadata');metadata=await response.json()
        assert metadata['kind']=='api-fixture'
        scope=metadata['scope'];configuration=scope['configuration'];article_id=scope['article']
        if observations:observations.scope=dict(scope)
        route=origin+'/workshop/?configuration='+configuration+'&region=US'
        before=await api_measure(context,origin,'initial-measurement')
        await page.goto(route);await api_signin(page)
        cookies=await context.cookies(origin)
        cookie=next(c for c in cookies if c['name']=='__Host-autodata_session')
        assert cookie['secure'] and cookie['httpOnly'] and cookie['sameSite']=='Lax'
        signed=await api_measure(context,origin,'signed-in-measurement')
        assert signed['auth_sessions']==before['auth_sessions']+1 and signed['hashed_sessions']==signed['auth_sessions'] and signed['sdk_cert_calls']>=1 and signed['sdk_user_calls']>=2 and signed['sdk_unexpected']==0
        assertions['official_sdk_cookie_and_pg_session']=True
        await expect(page.locator('#purchase-action')).to_be_enabled()
        await expect(page.locator('#purchase-message')).to_contain_text('purchase')
        await page.locator('#agreement').check()
        if observations:observations.phase='checkout-first-http' if name==API_CASES[0] else 'checkout-http'
        await page.locator('#purchase-action').click(click_count=2,delay=0)
        if name==API_CASES[0]:
            await expect(page.locator('#retry')).to_be_visible()
            assert transport.checkout_count==1 and transport.lost_response_count==1
            lost_measurement=await api_measure(context,origin,'response-lost-measurement')
            lost_snapshot=await api_snapshot(context,origin,'response-lost-snapshot')
            transport.validate_pending_checkout(lost_measurement,lost_snapshot)
            if observations:observations.phase='checkout-retry-http'
            await page.locator('#retry').click()
        await page.wait_for_url(re.compile(r'https://checkout\.stripe\.com/c/pay/cs_test_[a-f0-9]{32}.*'))
        pending=await api_measure(context,origin,'pending-checkout-measurement')
        assert pending['workshop_orders']==1 and pending['entitlements']==0
        if name==API_CASES[0]:
            assert transport.checkout_count==2 and transport.lost_response_count==1
            assert len(transport.keys)==2 and transport.keys[0]==transport.keys[1]
            assert len(transport.checkout_bodies)==2 and transport.checkout_bodies[0]==transport.checkout_bodies[1]
            assert len(transport.checkout_responses)==2 and transport.checkout_responses[0]==transport.checkout_responses[1]
            assert page.url==transport.checkout_responses[0]['checkout_url']
            transport.validate_pending_checkout(pending,await api_snapshot(context,origin,'retry-pending-snapshot'),lost_snapshot)
            assertions['client_response_loss_same_key_one_checkout']=True
        order=pending['orders'][0]['order_id']
        # A provider return is only a request to check the owner-scoped ledger.
        await page.goto(origin+'/workshop/?order='+order)
        await expect(page.locator('#purchase-message')).to_contain_text('Do not pay again')
        assert (await api_measure(context,origin,'return-without-grant-measurement'))['entitlements']==0
        assertions['return_does_not_grant']=True
        await api_control(context,origin,'payment/settle?order_id='+order,'settlement-control')
        settled=await api_measure(context,origin,'settled-measurement')
        assert settled['workshop_orders']==1 and settled['entitlements']==1 and settled['dataset_requests']==1 and settled['dataset_projections']==1 and settled['payment_events']==1
        assertions['signed_public_webhook_grants_once']=True
        if observations:
            observations.owner_scope=(configuration,order)
            observations.phase='owner-library-initial-http'
        await page.goto(route)
        await expect(page.locator('#articles a')).not_to_have_count(0)
        await page.locator('#my-vehicles').click()
        if observations:
            await expect(page.locator('#library-items > li')).to_have_count(1)
            await observations.drain();observations.require_window('owner-library-initial-http')
        await expect(page.locator('#library-items > li')).to_have_count(1)
        if observations:observations.phase='owner-library-reload-http'
        await page.reload()
        if observations:
            await expect(page.locator('#library-items > li')).to_have_count(1)
            await observations.drain();observations.require_window('owner-library-reload-http')
        await expect(page.locator('#library-items > li')).to_have_count(1)
        assert (await api_measure(context,origin,'library-reload-measurement'))['workshop_orders']==1
        assertions['permanent_owner_library_reload']=True
        restart_before=await api_measure(context,origin,'restart-before-measurement')
        runtime_before=await (await api21_get(context,origin+'/__fixture/runtime',phase='runtime-before')).json()
        await api_control(context,origin,'restart','restart-control')
        deadline=time.monotonic()+5
        while True:
            try:
                runtime_after=await (await api21_get(context,origin+'/__fixture/runtime',phase='runtime-poll',timeout=1000)).json()
                if runtime_after['application_generation']==runtime_before['application_generation']+1:break
            except Exception:
                if time.monotonic()>=deadline:raise
            assert time.monotonic()<deadline,'actual application restart did not finish'
            await asyncio.sleep(.05)
        if observations:observations.phase='owner-library-restart-http'
        await page.reload()
        if observations:
            await expect(page.locator('#library-items > li')).to_have_count(1)
            await observations.drain();observations.require_window('owner-library-restart-http')
        await expect(page.locator('#library-items > li')).to_have_count(1)
        restart_after=await api_measure(context,origin,'restart-after-measurement')
        durable=('workshop_orders','workshop_checkout_requests','entitlements','dataset_requests','dataset_projections','payment_events','orders','auth_sessions','hashed_sessions')
        assert {key:restart_before[key] for key in durable}=={key:restart_after[key] for key in durable}
        restart_receipt={'runtime_before':runtime_before,'runtime_after':runtime_after,'before':restart_before,'after':restart_after}
        assertions['permanent_owner_library_server_restart']=True
        if name==API_CASES[0]:
            assert await page.evaluate('Object.keys(localStorage).filter(k=>/firebase:authUser|token|csrf/i.test(k))')==[]
        else:
            await api_control(context,origin,'control/start-workers','start-workers-control')
            if observations:observations.phase='source-page-http'
            await page.goto(route+'&article='+article_id)
            await expect(page.locator('#article-kind')).to_have_text('Stored source',timeout=15000)
            await expect(page.locator('#article-content')).to_contain_text('Remove the pump.')
            await expect(page.locator('#print')).to_be_enabled()
            await expect(page.locator('#article-content img')).not_to_have_count(0)
            image_url=await page.locator('#article-content img').first.get_attribute('src')
            assert urlsplit(image_url).path.startswith('/v1/catalog/images/v2.')
            image=await api21_get(context,image_url,phase='source-image-http');assert image.status==200 and len(await image.body())>0
            if observations:observations.phase='source-review-http'
            await page.locator('#article-reference summary').click();await page.locator('#source-review-load').click()
            await expect(page.locator('#source-review-frame')).to_contain_text('Remove the pump.')
            source_path=await page.locator('#source-review-link').get_attribute('href')
            assert parse_qs(urlsplit(source_path).query).get('source_revision_id')
            assertions['paid_source_and_actual_s3_image']=True
            await api_control(context,origin,'control/release-model','release-model-control')
            await expect(page.locator('#article-kind')).to_have_text('Workshop article',timeout=15000)
            await expect(page.locator('#article-content')).not_to_be_empty()
            warm_before=await api_snapshot(context,origin,'warm-before-snapshot')
            reader_before=(await api_measure(context,origin,'reader-before-measurement'))['image_reads']
            if observations:observations.phase='warm-page-http'
            await page.reload();await expect(page.locator('#article-kind')).to_have_text('Workshop article')
            await expect(page.locator('#article-content img')).not_to_have_count(0)
            warm_image=await page.locator('#article-content img').first.get_attribute('src')
            delivered=await api21_get(context,warm_image,phase='warm-image-http');assert delivered.status==200 and len(await delivered.body())>0
            pinned=await api21_get(context,origin+source_path,phase='warm-pinned-source-http');assert pinned.status==200
            warm_after=await api_snapshot(context,origin,'warm-after-snapshot')
            reader_after=(await api_measure(context,origin,'reader-after-measurement'))['image_reads']
            validate_warm_runtime(warm_before,warm_after,reader_before,reader_after)
            warm_receipt={'before':warm_before,'after':warm_after,'reader_before':reader_before,'reader_after':reader_after}
            assertions['source_to_canonical_and_warm_reuse']=True
            assertions['warm_raw_runtime_unchanged_with_approved_s3_delivery']=True
            if name==API_CASES[2]:
                for denial_phase,denied in zip(('adjacent-denial','other-region-denial','unscoped-article-denial','legacy-vehicle-denial'),(f'/v1/catalog/vehicles/{scope["adjacent"]}/articles',f'/v1/catalog/vehicles/{scope["other_region"]}/articles',f'/v1/catalog/vehicles/{configuration}/articles/{scope["unscoped"]}',f'/v1/catalog/vehicles/{scope["vehicle"]}/articles')):
                    denied_response=await api21_get(context,origin+denied,phase=denial_phase)
                    assert denied_response.status in (403,404), f'adjacent/legacy route exposed status{denied_response.status}'
                other=await browser.new_context(ignore_https_errors=True)
                if observations:other._api21=observations
                other_transport=APIFixture(origin,name);other_transport.account='other';await other.route('**/*',other_transport.route)
                other_page=await other.new_page()
                try:
                    await other_page.goto(route);await api_signin(other_page)
                    denied=await api21_get(other,origin+f'/v1/catalog/vehicles/{configuration}/articles',phase='other-catalogue-denial',actor='other');assert denied.status==403
                    library_response=await api21_get(other,origin+'/v1/workshop/library?limit=20',phase='other-library-http',actor='other');assert (await library_response.json())['items']==[]
                    denied_image=await api21_get(other,image_url,phase='other-image-denial',actor='other');assert denied_image.status==404
                    assert not other_transport.unexpected and not other_transport.errors
                finally:await other.close()
                assertions['account_and_exact_scope_isolation']=True
                await page.locator('#signout').click();await expect(page.locator('#article-content')).to_be_empty()
                assert (await api21_get(context,image_url,phase='logout-image-denial',actor='logged-out')).status==401
                await page.evaluate('window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true}))');await expect(page.locator('#article-content')).to_be_empty()
                await api_signin(page);await page.goto(route+'&article='+article_id);await expect(page.locator('#article-kind')).to_have_text('Workshop article')
                await api_control(context,origin,'disable','disable-control')
                assert (await api21_get(context,image_url,phase='disabled-image-denial',actor='disabled')).status==401
                await page.reload();await expect(page.locator('#article-content')).to_be_empty()
                assertions['logout_bfcache_and_firebase_disable_deny']=True
            elif name==API_CASES[3]:
                await api_control(context,origin,'payment/refund?order_id='+order,'refund-control')
                old=await api21_get(context,image_url,phase='refund-old-image-denial');assert old.status==403
                source=await api21_get(context,origin+source_path,phase='refund-source-denial');assert source.status==403
                detail=await api21_get(context,origin+f'/v1/catalog/vehicles/{configuration}/articles/{article_id}',phase='refund-detail-denial');assert detail.status==403
                revoked=await api_measure(context,origin,'revoked-measurement');assert revoked['orders'][0]['state']=='revoked' and revoked['entitlements']==1
                await page.reload();await expect(page.locator('#article-content')).to_be_empty();await expect(page.locator('#purchase-action')).to_be_disabled()
                await page.locator('#my-vehicles').click();await expect(page.locator('#library-items')).to_contain_text('Access revoked')
                assertions['signed_full_refund_denies_old_content_and_media']=True
        assert not transport.unexpected and not transport.errors, {'unexpected':transport.unexpected,'errors':transport.errors}
        final=await api_measure(context,origin,'final-measurement');assert final['sdk_unexpected']==0
        result={'status':'passed','assertions':assertions,'provider':scope['provider'],'requests':transport.requests,'measurement':final,'restart':restart_receipt,'warm':warm_receipt}
    except BaseException as error:
        failure=error
        if observations:
            reason=('cancelled' if isinstance(error,asyncio.CancelledError) else
                'launch_failed' if context is None else 'assertion_failed' if isinstance(error,AssertionError) else 'http_failed')
            observations.fail(reason)
            observations.note_lifecycle(observations.phase,'context-create' if context is None else 'page-create' if page is None else 'setup','failed',reason)
        if page is not None:
            try:
                output.mkdir(mode=0o700,parents=True,exist_ok=True)
                screenshot=await page.screenshot(timeout=1500)
                api21_write_bytes(output/(name+'-failure.png'),screenshot)
            except Exception:pass
        raise
    finally:
        if observations and failure is None:
            try:await observations.drain()
            except BaseException:observations.fail('cancelled')
        if context is not None:
            if observations:observations.note_lifecycle(observations.phase,'context-close','requested')
            try:
                await context.close()
                if observations:observations.note_lifecycle(observations.phase,'context-close','completed')
            except BaseException:
                if observations:
                    observations.fail('close_failed')
                    observations.note_lifecycle(observations.phase,'context-close','failed','close_failed')
                if failure is None:raise
        if observations and failure is not None:await observations.abandon_pending()
    if observations:
        observations.complete_case(name)
        result['observations']=observations.snapshot()
        if observations.primary:result['status']='failed'
    return result


def complete_dto_failure(expected, observations, *, stage, kind, cleanup):
    """Terminal failures retain original observations without promoting prior passes."""
    observed = {(row['browser'],row['scenario']):row for row in observations}
    rows = []
    for engine,name in expected:
        original = observed.get((engine,name))
        row = dict(original or {}, browser=engine, scenario=name, status='failed')
        if original is not None:
            row['observed_case_result'] = dict(original)
        else:
            row['failure_kind'] = 'not_started_after_lifecycle_failure'
        row['lifecycle_failure'] = dict(stage=stage,kind=kind,cleanup_status=cleanup)
        rows.append(row)
    return rows


class DTOClock:
    def __init__(self, clock): self.clock, self.last = clock, None
    def __call__(self):
        now = self.clock()
        remaining(now,now)  # Reject NaN/infinite/bool timestamps.
        if self.last is not None and now < self.last: raise ValueError('monotonic clock moved backward')
        self.last = now
        return now


async def run_dto_inventory(args, *, clock, lifecycle, persist, timing, bounded=_dto_bounded):
    validate_dto_schedule(timing,120)
    clock = DTOClock(clock)
    engines = ENGINES if args.browser == 'all' else (args.browser,)
    expected = [(engine,name) for engine in engines for name in inventory()]
    evidence = dict(lifecycle.evidence, version='v1', mode='dto-fixture', results=[],
        configured_budgets=dict(timing), cleanup_status='unverified')
    rows = evidence['results']; browser = None; started = False
    stage = 'playwright.start'; failure = None; persistence_left = timing['evidence_persistence_seconds']
    async def operation(factory, seconds, *, late_result_cleanup=None):
        deadline = clock()+seconds
        allowance = remaining(deadline,clock())
        if allowance <= 0: raise TimeoutError('phase deadline exceeded before admission')
        result = await bounded(factory(), allowance, late_result_cleanup=late_result_cleanup)
        if clock() >= deadline: raise TimeoutError('phase deadline exceeded')
        return result
    async def snapshot():
        nonlocal persistence_left, stage
        previous = stage; stage = 'persistence'; begin = clock()
        if persistence_left <= 0: raise TimeoutError('cumulative persistence budget exhausted')
        if not await operation(lambda:persist(evidence),persistence_left):
            raise OSError('persistence acknowledgement missing')
        persistence_left -= clock()-begin; stage = previous
    def fail(error, where):
        nonlocal failure
        if failure is None: failure = (where, 'cancelled' if isinstance(error,asyncio.CancelledError) else
            'clock_or_lifecycle_failure', getattr(getattr(error,'dto_diagnostics',None),'error',None) or str(error) or type(error).__name__)
        else:evidence.setdefault('secondary_errors',[]).append(where+': '+(str(error) or type(error).__name__))
    # Late resource cleanup is tracked by the same registry as case operations.
    def late_browser(done):
        if not done.cancelled() and done.exception() is None:
            _dto_task(close_dto_browser(done.result(), timeout=timing['engine_close_seconds']))
    try:
        await snapshot()
        await operation(lifecycle.start,timing['playwright_start_seconds']); started=True
        await snapshot()
        for engine in engines:
            stage='engine.launch'
            try:
                browser=await operation(lambda:lifecycle.launch(engine,timeout=15000),
                    timing['engine_launch_seconds'],late_result_cleanup=late_browser)
            except Exception as error:
                # Both watchdog and Playwright timeouts leave ownership uncertain.
                # Playwright's native timeout does not inherit built-in TimeoutError.
                try:from playwright.async_api import TimeoutError as PlaywrightTimeoutError
                except ImportError:PlaywrightTimeoutError=TimeoutError
                if isinstance(error,(TimeoutError,PlaywrightTimeoutError)): raise
                rows.extend(dict(browser=engine,scenario=name,status='failed',error=str(error)) for name in inventory())
                await snapshot();continue
            try:
                for name in inventory():
                    stage='case';begin=clock()
                    try:result=await lifecycle.case(browser,name,Path(args.output)/engine)
                    except BaseException as error:
                        diagnostics=getattr(error,'dto_diagnostics',None)
                        if diagnostics is not None:
                            rows.append(dict(browser=engine,scenario=name,status='failed',error=diagnostics.error,
                                diagnostics=diagnostics.snapshot(),elapsed_seconds=round(clock()-begin,3)))
                        fail(error,'case')
                        raise
                    rows.append(dict(browser=engine,scenario=name,elapsed_seconds=round(clock()-begin,3),**result))
                    evidence.setdefault('browser_versions',{})[engine]=browser.version
                    await snapshot()
            except BaseException as error:
                fail(error,stage)
                raise
            finally:
                stage='engine.close'
                owned,browser=browser,None
                had_failure=failure is not None
                try:await operation(lambda:lifecycle.close(owned),timing['engine_close_seconds'])
                except BaseException as error:
                    fail(error,stage)
                    # The recorded primary failure remains sticky, including cancel.
                    if not had_failure:raise
            await snapshot()
    except BaseException as error:
        fail(error,stage)
    finally:
        stage='playwright.stop'
        # start may have allocated resources even if its ACK never arrived.
        try:
            await operation(lifecycle.stop,timing['playwright_stop_seconds'])
        except BaseException as error: fail(error,stage)
        unresolved=[task for task in _DTO_PENDING_TASKS if not task.done()]
        if unresolved: fail(RuntimeError('unresolved tracked operations'),stage)
        for task in unresolved: task.cancel()
        evidence['cleanup_status']='verified' if failure is None else 'unverified'
        if failure is not None:
            evidence.update(failure_stage=failure[0],failure_kind=failure[1],error=failure[2])
            evidence['results']=complete_dto_failure(expected,rows,stage=failure[0],kind=failure[1],cleanup='unverified')
        try: await snapshot()
        except BaseException as error:
            fail(error,'persistence')
            evidence.update(failure_stage=failure[0],failure_kind=failure[1],error=failure[2],persistence_status='unverified',cleanup_status='unverified')
            evidence['results']=complete_dto_failure(expected,rows,stage=failure[0],kind=failure[1],cleanup='unverified')
    if failure is not None and failure[1]=='cancelled':raise asyncio.CancelledError(failure[2])
    return evidence


class DTOPlaywrightLifecycle:
    def __init__(self, args, evidence):
        self.args, self.evidence = args,evidence
        self.manager = self.playwright = None
    async def start(self):
        from playwright.async_api import async_playwright
        self.manager=async_playwright()
        self.playwright=await self.manager.start()
    async def launch(self,engine,timeout):return await getattr(self.playwright,engine).launch(timeout=timeout)
    async def case(self,browser,name,output):return await run_dto_case(browser,self.args.base_url,name,output)
    async def close(self,browser):await browser.close()
    async def stop(self):
        if self.playwright is not None:await self.playwright.stop()
        elif self.manager is not None:await self.manager.__aexit__(None,None,None)


def api21_binding(args,name):
    keys=('binding_state','unavailable_reason','api_observability_version','run_id','attempt_id',
        'case_id','root','engine','bank','candidate_sha','source_tree','source_input_sha256','producer_role')
    fallback=dict.fromkeys(keys)
    fallback.update(binding_state='partial',unavailable_reason='source_binding_failed',
        api_observability_version=API21_VERSION,root=name,engine=args.browser,
        candidate_sha=args.candidate_sha,producer_role='browser-runner')
    try:
        encoded=os.environ.get('AUTODATA_API21_BINDING','').encode()
        if len(encoded)>16384:return fallback
        supplied=api21_load(encoded)
        if set(supplied)!=set(keys):return fallback
        if (supplied['binding_state']!='complete' or supplied['unavailable_reason'] is not None or
                supplied['api_observability_version']!=API21_VERSION or supplied['root']!=name or
                supplied['engine']!=args.browser or supplied['candidate_sha']!=args.candidate_sha or
                supplied['bank'] not in ('bankone','banktwo') or
                any(not isinstance(supplied[k],str) or not re.fullmatch('[a-f0-9]{32}',supplied[k]) for k in ('run_id','attempt_id')) or
                any(not isinstance(supplied[k],str) or not re.fullmatch('[a-f0-9]{40}',supplied[k]) for k in ('candidate_sha','source_tree'))):
            raise ValueError('invalid binding')
        sources=supplied['source_input_sha256']
        if not isinstance(sources,dict) or len(sources)!=7 or any(not isinstance(k,str) or len(k)>256 or not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for k,v in sources.items()):raise ValueError('invalid sources')
        suffix=args.browser if name==API_CASES[0] else args.browser+'-'+supplied['bank']
        if supplied['case_id']!=name+'['+suffix+']':raise ValueError('invalid case')
        return dict(supplied,producer_role='browser-runner')
    except (ValueError,TypeError,KeyError,UnicodeError):
        fallback.update(binding_state='partial',unavailable_reason='source_binding_failed')
        return fallback


async def run(args):
    if args.mode=='dto-fixture':raise ValueError('DTO CLI requires the owned supervisor')
    engines=ENGINES if args.browser=='all' else (args.browser,)
    name=os.environ.get('AUTODATA_WORKSHOP_BROWSER_CASE')
    if len(engines)!=1 or name not in API_CASES:raise ValueError('API mode requires one frozen owned pytest case/engine')
    binding=api21_binding(args,name)
    observations=APIObservations(binding)  # Buffer and reserve precede setup.
    rows=[];browser=None;failure=None
    evidence=dict(version='v1',mode='api-fixture',candidate_sha=args.candidate_sha,
        api_observability_version=API21_VERSION,binding=binding,results=rows)
    output=Path(args.output);target=output/'evidence.json'
    stage='setup'
    try:
        output.mkdir(mode=0o700,parents=True,exist_ok=True)
        info=output.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
            raise OSError('unsafe output')
        observations.note_lifecycle('setup','setup','completed')
        stage='metadata'
        observations.note_lifecycle('setup','metadata','requested')
        provenance=verify_provenance(args)
        sdk=(ROOT/'apps/api-go/workshop/firebase-web.mjs').read_bytes()
        browser_manifest=Path(importlib.metadata.distribution('playwright').locate_file('playwright/driver/package/browsers.json'))
        revisions={item['name']:item['revision'] for item in api21_load(browser_manifest.read_bytes())['browsers']}
        paths=[Path(__file__),FIXTURES/'scenarios.json',FIXTURES/'firebase_transport.js',
            FIXTURES/'hostile_source.json',FIXTURES/'stripe_checkout.html',ROOT/'apps/api-go/workshop_browser_fixture_test.go']
        inputs={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        integration='workers/ingestion-python/tests/test_workshop_browser_integration.py'
        seven=dict(inputs,**{integration:hashlib.sha256((ROOT/integration).read_bytes()).hexdigest()})
        if binding['binding_state']!='complete' or binding['source_input_sha256']!=seven:
            binding.update(binding_state='partial',unavailable_reason='source_binding_failed')
            observations.binding.update(binding)
            raise ValueError('source binding failed')
        evidence.update(engine_revisions=revisions,input_sha256=inputs,
            sdk_sha256=hashlib.sha256(sdk).hexdigest(),playwright_version=importlib.metadata.version('playwright'),
            provenance=provenance)
        if evidence['playwright_version']!='1.64.1':raise ValueError('exact Playwright 1.64.1 is required')
        observations.note_lifecycle('setup','metadata','completed')
        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            stage='browser-launch';observations.note_lifecycle('setup','browser-launch','requested')
            browser=await getattr(playwright,engines[0]).launch()
            observations.note_lifecycle('setup','browser-launch','completed')
            stage='case';start=time.monotonic()
            try:
                result=await asyncio.wait_for(api_case(browser,args.base_url,name,output/engines[0],observations=observations),timeout=65)
                rows.append(dict(browser=engines[0],scenario=name,elapsed_seconds=round(time.monotonic()-start,3),**result))
                evidence['browser_versions']={engines[0]:browser.version}
            except BaseException as error:
                failure=error
                observations.fail('cancelled' if isinstance(error,asyncio.CancelledError) else
                    'timeout' if isinstance(error,TimeoutError) else 'assertion_failed' if isinstance(error,AssertionError) else 'internal_error')
            finally:
                stage='browser-close';observations.note_lifecycle(observations.phase,'browser-close','requested')
                try:
                    await browser.close()
                    observations.note_lifecycle(observations.phase,'browser-close','completed')
                except BaseException as error:
                    observations.fail('close_failed')
                    observations.note_lifecycle(observations.phase,'browser-close','failed','close_failed')
                    if failure is None:failure=error
                browser=None
    except BaseException as error:
        if failure is None:failure=error
        reason=('cancelled' if isinstance(error,asyncio.CancelledError) else
            'source_binding_failed' if stage=='metadata' else 'launch_failed' if stage=='browser-launch' else 'internal_error')
        observations.fail(reason)
        try:observations.note_lifecycle('setup','metadata' if stage=='metadata' else 'browser-launch' if stage=='browser-launch' else 'setup','failed',reason)
        except APIObservationError:pass
    finally:
        try:await observations.drain()
        except BaseException:observations.fail('cancelled')
        if observations.binding.get('binding_state')!='complete':observations.fail('source_binding_failed')
        observations.finish()
        if not rows:rows.append(dict(browser=engines[0],scenario=name,status='failed'))
        if observations.primary:
            for row in rows:row['status']='failed'
        observations.publication='written'
        for row in rows:row['observations']=observations.snapshot()
        if not api21_publish(target,evidence,observations) and failure is None:
            failure=APIObservationError('publication_failed')
    if failure is not None:
        if isinstance(failure,asyncio.CancelledError):raise asyncio.CancelledError(observations.primary) from None
        raise APIObservationError(observations.primary or 'internal_error') from None
    validate_results(rows,[(engines[0],name)])
    return evidence


# Finite DTO-main scheduling is CONDITIONAL on responsive parent clock/create/
# poll/signal/publication syscalls. Independent watchdog and actual descendant
# containment are not admitted by this source protocol.
DTO_RUNTIME_BLOCKERS = ('independent_watchdog_not_admitted', 'descendant_containment_not_admitted',
    'trace_16MiB_producer_8MiB_consumer_not_admitted')
DTO_MAX_BYTES = 32*1024*1024


class DTOAttempt:
    def __init__(self, attempt_id, candidate_sha):
        if not re.fullmatch('[a-f0-9]{32}',attempt_id):raise ValueError('fresh 128-bit attempt required')
        self.attempt_id,self.candidate_sha = attempt_id,candidate_identity(candidate_sha)
        self.epoch,self.state,self.reason = 0,'INITIALIZING',None
        self.pending={}; self.used=set(); self.pins=None; self.final_ack=None
    def request(self,kind):
        if self.state in ('COMMITTED','REVOKED') and kind!='nonpass':raise ValueError('terminal attempt')
        nonce=os.urandom(16).hex()
        request=dict(kind=kind,attempt_id=self.attempt_id,epoch=self.epoch,stage_nonce=nonce)
        self.pending[nonce]=request
        return request
    def ack(self,request,ack):
        if self.state in ('COMMITTED','REVOKED') or not isinstance(ack,dict):return False
        nonce=request['stage_nonce']
        if nonce in self.used or self.pending.get(nonce)!=request:return False
        if any(ack.get(key)!=request[key] for key in ('attempt_id','epoch','stage_nonce')):return False
        if ack.get('candidate_sha')!=self.candidate_sha:return False
        if any(not isinstance(ack.get(key),str) or not re.fullmatch('[a-f0-9]{64}',ack[key])
                for key in ('content_sha256','timing_contract_sha256','input_fingerprint')):return False
        if type(ack.get('byte_length')) is not int or not 0<ack['byte_length']<=DTO_MAX_BYTES:return False
        pins=(ack['timing_contract_sha256'],ack['input_fingerprint'])
        if self.pins is not None and pins!=self.pins:return False
        if self.pins is None:self.pins=pins
        self.used.add(nonce);del self.pending[nonce]
        return True
    def activate(self):
        if self.state!='INITIALIZING' or self.pins is None:raise ValueError('initialization not acknowledged')
        self.state='ACTIVE'
    def prepare(self,ack):
        if self.state!='ACTIVE' or not ack.get('complete') or not ack.get('cleanup_verified'):
            raise ValueError('complete clean final ACK required')
        self.final_ack=ack;self.state='PREPARED'
    def revoke(self,reason):
        if self.state in ('COMMITTED','REVOKED'):return
        self.reason=reason;self.epoch+=1;self.state='REVOKED';self.pending.clear()
    def commit_eligible(self,now,deadline,cancelled):
        return self.state=='PREPARED' and self.final_ack is not None and not cancelled and now<deadline-2


def dto_receipt(ack,attempt):
    return dict(version='v1',attempt_id=attempt.attempt_id,epoch=attempt.epoch,
        candidate_sha=attempt.candidate_sha,timing_contract_sha256=ack['timing_contract_sha256'],
        evidence_sha256=ack['content_sha256'],terminal_state='committed',cleanup_status='verified')


def accept_dto_success(raw,receipt,*,invocation,expected_attempt,candidate_sha,timing_sha256,expected,expected_input_sha256,expected_epoch=0):
    """A receipt is not an invocation acknowledgement; consumers need both."""
    try:
        if len(raw)>DTO_MAX_BYTES or not isinstance(invocation,dict) or not isinstance(receipt,dict):return False
        evidence=json.loads(raw,object_pairs_hook=_unique_json)
        if type(receipt.get('epoch')) is not int or receipt['epoch']!=expected_epoch:return False
        if evidence.get('input_sha256')!=expected_input_sha256:return False
        if evidence.get('input_fingerprint')!=hashlib.sha256(_dto_bytes(expected_input_sha256)).hexdigest():return False
        if invocation != dict(attempt_id=expected_attempt,epoch=receipt['epoch'],exit_code=0,terminal_state='COMMITTED'):return False
        if receipt!=dict(version='v1',attempt_id=expected_attempt,epoch=evidence['epoch'],candidate_sha=candidate_sha,
            timing_contract_sha256=timing_sha256,evidence_sha256=hashlib.sha256(raw).hexdigest(),
            terminal_state='committed',cleanup_status='verified'):return False
        if any(evidence.get(key)!=value for key,value in dict(attempt_id=expected_attempt,candidate_sha=candidate_sha,
                timing_contract_sha256=timing_sha256,publication_state='requires_commit_receipt',cleanup_status='verified').items()):return False
        if evidence.get('failure_kind') or evidence.get('revoked'):return False
        rows=evidence['results']
        if [(r['browser'],r['scenario']) for r in rows]!=expected:return False
        validate_results(rows,expected)
        return True
    except (ValueError,KeyError,TypeError):return False


def supervise_dto(args,*,clock,process_factory,writer_factory,timing,sleep=time.sleep,
                  publisher=None,cancelled=lambda:False,observer=lambda attempt:None,producer_started=None):
    """Watch only owned handles and fixed-size ACKs; file I/O/JSON stays in helpers.

    Creation/poll/signal and the <=2s parent publication section are responsive-
    syscall preconditions, not a claim of kernel-stall survival.
    """
    clock=DTOClock(clock)
    started=clock() if producer_started is None else producer_started
    deadline=started+4440
    attempt=DTOAttempt(os.urandom(16).hex(),args.candidate_sha);observer(attempt)
    init_deadline=started+10;worker=helper=None;helper_episodes=0;initialized=False
    worker_deadline=None;progress_left=10;progress_read=False;progress_begin=None;progress_ack=None;final_deadline=None
    publisher=publisher or (lambda ack,attempt,success:publish_dto_stage(args.output,ack,attempt,success))
    def pause(until):sleep(min(.02,max(0,until-clock())))
    def stop(handle,helper_stop=False):
        nonlocal helper_episodes
        if handle is None:return True
        if helper_stop:
            helper_episodes+=1
            if helper_episodes>2:return False
        if handle.poll() is not None:handle.close();return True
        for event,seconds in (('TERM',2),('KILL',2),('REAP',2)):
            end=clock()+seconds
            if event!='REAP':
                try:handle.signal_owned_group(event)
                except Exception:return False
            while clock()<end:
                if handle.poll() is not None:handle.close();return True
                pause(end)
        handle.close();return False
    def collect(handle,until,request,prior_ack=None):
        ack=prior_ack
        while clock()<until:
            if cancelled():raise InterruptedError('external cancellation')
            current=handle.read_ack()
            if current is not None:
                if ack is not None:raise ValueError('duplicate helper ACK')
                ack=current
            code=handle.poll()
            if code is not None:
                if ack is None:ack=handle.read_ack()
                if clock()>=until:raise TimeoutError('expired helper ACK')
                if code!=0 or ack is None or not attempt.ack(request,ack):raise ValueError('helper ACK/exit unverified')
                handle.close();return ack
            pause(until)
        raise TimeoutError('helper phase deadline')
    def create(factory,kind):
        request=attempt.request(kind)
        # A nonpass helper gets the sticky reason, never a success publication target.
        request.update(failure_reason=attempt.reason)
        attempt.pending[request['stage_nonce']]=dict(request)
        return factory(kind,request,args),request
    def publish(ack,success,until):
        begin=clock()
        if cancelled() or begin>=until-2:raise InterruptedError('publication fence expired')
        try:
            if not publisher(ack,attempt,success) or cancelled() or clock()>=begin+2 or clock()>=until:
                raise RuntimeError('commit_uncertain')
        except BaseException as error:
            # Renames/fsync may already have changed canonical bytes. Preserve
            # them and never schedule recovery publication after an ambiguous commit.
            raise RuntimeError('commit_uncertain') from error
    try:
        if clock()>=init_deadline:raise TimeoutError('initialization_unverified')
        helper,request=create(writer_factory,'init')
        ack=collect(helper,init_deadline,request);helper=None
        publish(ack,False,init_deadline);initialized=True
        # Validate exact contract before ANY browser worker is created. In production
        # initialization helper performed file parsing; this object is its fixed v1 contract.
        validate_dto_schedule(timing,120)
        if clock()>=init_deadline or deadline-clock()<timing['worker_deadline_reserve_seconds']:
            raise TimeoutError('initialization_unverified')
        attempt.activate();worker_started=clock()
        worker,worker_request=create(process_factory,'worker')
        worker_deadline=min(worker_started+timing['worker_hard_seconds'],deadline-timing['worker_deadline_reserve_seconds'])
        if clock()>=init_deadline:raise TimeoutError('late worker creation')
        while True:
            now=clock()
            if cancelled():raise InterruptedError('external cancellation')
            if now>=worker_deadline:raise TimeoutError('worker hard deadline')
            code=worker.poll()
            if code is not None:
                worker.close();worker=None
                if code!=0:raise RuntimeError('worker exit/cleanup_unverified')
                break
            # One optional progress read plus one final read: no per-case renewal.
            if not progress_read and getattr(worker,'progress_ready',lambda:False)():
                helper,request=create(writer_factory,'progress');progress_read=True;progress_begin=now
            if helper is not None:
                current=helper.read_ack();code=helper.poll()
                if clock()>=progress_begin+progress_left:
                    raise TimeoutError('cumulative progress read/parse exhausted')
                if current is not None:
                    if progress_ack is not None:raise ValueError('duplicate progress ACK')
                    progress_ack=current
                if code is not None:
                    ack=progress_ack if progress_ack is not None else helper.read_ack()
                    if code!=0 or ack is None or not attempt.ack(request,ack):raise ValueError('progress ACK/exit unverified')
                    progress_left-=clock()-progress_begin
                    helper.close();helper=None
                elif now-progress_begin>=progress_left:raise TimeoutError('cumulative progress read/parse exhausted')
            pause(min(worker_deadline,progress_begin+progress_left if helper is not None else worker_deadline))
        # Any still-owned progress helper must ACK AND reap; final10s is shared.
        final_deadline=min(clock()+timing['parent_final_read_parse_stage_seconds'],deadline-12)
        if helper is not None:
            collect(helper,min(final_deadline,progress_begin+progress_left),request,progress_ack);helper=None
        helper,request=create(writer_factory,'final')
        ack=collect(helper,final_deadline,request);helper=None
        attempt.prepare(ack)
        if not attempt.commit_eligible(clock(),deadline,cancelled()):raise InterruptedError('commit fence denied')
        # No await/helper action occurs between fence and serialized parent publication.
        publish(ack,True,deadline)
        attempt.state='COMMITTED'
        return 0
    except BaseException as error:
        reason='commit_uncertain' if 'commit_uncertain' in str(error) else str(error) or type(error).__name__
        attempt.revoke(reason)  # Terminal epoch fence precedes EVERY cleanup signal.
        try:worker_clean=stop(worker)
        except BaseException:worker_clean=False
        worker=None
        try:helper_clean=stop(helper,True)
        except BaseException:helper_clean=False
        helper=None
        if initialized and reason!='commit_uncertain' and 'clock' not in reason and (final_deadline is None or clock()<final_deadline):
            # Exactly one post-fault nonpass stage, never another success attempt.
            try:
                end=min(clock()+10 if final_deadline is None else final_deadline,deadline-2)
                helper,request=create(writer_factory,'nonpass')
                ack=None
                while clock()<end:
                    current=helper.read_ack()
                    if current is not None:ack=current
                    code=helper.poll()
                    if code is not None:
                        if ack is None:ack=helper.read_ack()
                        if code!=0 or ack is None:raise ValueError('nonpass staging unverified')
                        if any(ack.get(key)!=request[key] for key in ('attempt_id','epoch','stage_nonce')):raise ValueError('nonpass identity')
                        helper.close();helper=None
                        # Publish only failure bytes; no receipt and no terminal success.
                        if worker_clean and helper_clean:publish(ack,False,deadline)
                        break
                    pause(end)
                if helper is not None:stop(helper,True);helper=None
            except BaseException:
                stop(helper,True);helper=None
        return 1


# Fixed binary ACK framing keeps the watchdog free of file reads and JSON parsing.
_DTO_ACK = struct.Struct('!16sQ16s32sQI20s32s32s')

def encode_dto_ack(ack):
    return _DTO_ACK.pack(bytes.fromhex(ack['attempt_id']),ack['epoch'],bytes.fromhex(ack['stage_nonce']),
        bytes.fromhex(ack['content_sha256']),ack['byte_length'],int(ack['complete']) | (int(ack['cleanup_verified'])<<1),
        bytes.fromhex(ack['candidate_sha']),bytes.fromhex(ack['timing_contract_sha256']),bytes.fromhex(ack['input_fingerprint']))

def decode_dto_ack(raw):
    if len(raw)!=_DTO_ACK.size:raise ValueError('invalid ACK frame size')
    attempt,epoch,nonce,digest,length,flags,candidate,timing,inputs=_DTO_ACK.unpack(raw)
    if flags & ~3:raise ValueError('invalid ACK flags')
    return dict(attempt_id=attempt.hex(),epoch=epoch,stage_nonce=nonce.hex(),content_sha256=digest.hex(),byte_length=length,
        complete=bool(flags&1),cleanup_verified=bool(flags&2),candidate_sha=candidate.hex(),
        timing_contract_sha256=timing.hex(),input_fingerprint=inputs.hex())


def dto_worker_environment(environment):
    allowed=('PATH','HOME','TMPDIR','XDG_CACHE_HOME','PLAYWRIGHT_BROWSERS_PATH','SSL_CERT_FILE','SSL_CERT_DIR','LANG','LC_ALL')
    result={key:environment[key] for key in allowed if key in environment}
    for key,value in result.items():
        if not isinstance(value,str) or '\0' in value:raise ValueError('invalid worker environment')
        if key not in ('LANG','LC_ALL'):
            paths=value.split(os.pathsep) if key=='PATH' else [value]
            if any(not Path(part).is_absolute() for part in paths):raise ValueError('worker paths must be absolute')
    return result


def dto_stage_path(output,request):
    if not re.fullmatch('[a-f0-9]{32}',request['attempt_id']) or not re.fullmatch('[a-f0-9]{32}',request['stage_nonce']):
        raise ValueError('invalid staging identity')
    if type(request['epoch']) is not int or request['epoch']<0:raise ValueError('invalid epoch')
    return Path(output)/'staging'/request['attempt_id']/str(request['epoch'])/(request['stage_nonce']+'.json')


def _dto_bytes(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def _dto_read(path):
    # Helpers only: retain oversize/raw files and reject without truncating them.
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or not 0<info.st_size<=DTO_MAX_BYTES:
            raise ValueError('owned regular evidence <=32MiB required')
        with os.fdopen(descriptor,'rb',closefd=False) as stream:raw=stream.read(DTO_MAX_BYTES+1)
        if len(raw)>DTO_MAX_BYTES:raise ValueError('oversize evidence')
        return json.loads(raw,object_pairs_hook=_unique_json)
    finally:os.close(descriptor)


def _dto_write_private(path,value):
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    raw=_dto_bytes(value)
    if len(raw)>DTO_MAX_BYTES:raise ValueError('oversize staged evidence')
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(descriptor,'wb',closefd=False) as stream:stream.write(raw);stream.flush();os.fsync(descriptor)
    finally:os.close(descriptor)
    return raw


def _dto_inputs():
    paths=[Path(__file__),FIXTURES/'timing.json',FIXTURES/'scenarios.json',FIXTURES/'firebase_transport.js',
        FIXTURES/'hostile_source.json',FIXTURES/'stripe_checkout.html',ROOT/'apps/api-go/workshop_browser_fixture_test.go']
    return {str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def _dto_expected(args):
    return [(engine,name) for engine in (ENGINES if args.browser=='all' else (args.browser,)) for name in inventory()]


def _dto_validate_progress(evidence,initial,args,request,*,final=False):
    expected=_dto_expected(args)
    for key in ('candidate_sha','timing_contract_sha256','input_sha256','input_fingerprint','attempt_id'):
        if evidence.get(key)!=initial.get(key):raise ValueError('stale/mismatched progress pin: '+key)
    if evidence.get('epoch')!=0 or evidence.get('publication_state')!='requires_commit_receipt':raise ValueError('stale progress epoch')
    rows=evidence.get('results')
    if not isinstance(rows,list):raise ValueError('progress results required')
    keys=[(row['browser'],row['scenario']) for row in rows]
    if len(keys)!=len(set(keys)) or keys!=expected[:len(keys)] or any(row.get('status') not in ('passed','failed') for row in rows):
        raise ValueError('malformed/duplicate/unordered progress')
    if final:
        validate_results(rows,expected)
        if evidence.get('cleanup_status')!='verified' or evidence.get('failure_kind') or evidence.get('persistence_status')=='unverified':
            raise ValueError('final lifecycle/cleanup not verified')


def perform_dto_io(kind,request,args):
    """Owned helpers stage private bytes only. They have no canonical publish API."""
    output=Path(args.output)
    if kind=='init':
        timing=load_dto_timing(FIXTURES/'timing.json');expected=_dto_expected(args)
        inputs=_dto_inputs();timing_hash=inputs[str((FIXTURES/'timing.json').relative_to(ROOT))]
        evidence=dict(version='v1',mode='dto-fixture',candidate_sha=args.candidate_sha,attempt_id=request['attempt_id'],
            epoch=request['epoch'],publication_state='requires_commit_receipt',input_sha256=inputs,
            timing_contract_sha256=timing_hash,input_fingerprint=hashlib.sha256(_dto_bytes(inputs)).hexdigest(),
            configured_budgets=timing,cleanup_status='unverified',runtime_blockers=list(DTO_RUNTIME_BLOCKERS),
            results=complete_dto_failure(expected,[],stage='initialization',kind='not_started',cleanup='unverified'))
        # Fresh output is exclusive; an old invocation cannot be silently reused.
        output.mkdir(mode=0o700,parents=False,exist_ok=False)
        _dto_write_private(output/'initial-observation.json',evidence)
    else:
        initial=_dto_read(output/'initial-observation.json')
        try:evidence=_dto_read(output/'progress.json')
        except FileNotFoundError:
            if kind!='nonpass':raise
            evidence=dict(initial,results=[])
        if kind!='nonpass':_dto_validate_progress(evidence,initial,args,request,final=kind=='final')
        else:
            try:_dto_validate_progress(evidence,initial,args,request)
            except Exception:evidence=dict(initial,results=[])
            evidence=dict(evidence,epoch=request['epoch'],failure_kind=request.get('failure_reason') or 'lifecycle_failure',cleanup_status='unverified')
            evidence['results']=complete_dto_failure(_dto_expected(args),evidence['results'],stage='parent',kind=evidence['failure_kind'],cleanup='unverified')
    raw=_dto_write_private(dto_stage_path(output,request),evidence)
    return dict(attempt_id=request['attempt_id'],epoch=request['epoch'],stage_nonce=request['stage_nonce'],
        content_sha256=hashlib.sha256(raw).hexdigest(),byte_length=len(raw),candidate_sha=args.candidate_sha,
        timing_contract_sha256=evidence['timing_contract_sha256'],input_fingerprint=evidence['input_fingerprint'],
        complete=len(evidence['results'])==len(_dto_expected(args)) and all(row['status']=='passed' for row in evidence['results']),
        cleanup_verified=evidence['cleanup_status']=='verified')


def publish_dto_stage(output,ack,attempt,success):
    """Parent-only serialized <=2s critical section, under responsive-local-I/O assumption.

    No read/parse/hash is performed here. Source-owned helper ACK binds staged
    bytes; metadata/rename/fsync/receipt publication are the explicit precondition.
    """
    if success and (attempt.state!='PREPARED' or attempt.final_ack!=ack):raise ValueError('terminal fence')
    if success and (ack['epoch']!=attempt.epoch or ack['attempt_id']!=attempt.attempt_id):raise ValueError('stale publication')
    root=os.open(output,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        relative=str(dto_stage_path('.',ack))
        source=os.open(relative,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=root)
        try:
            info=os.fstat(source)
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size!=ack['byte_length']:
                raise ValueError('stage metadata mismatch')
        finally:os.close(source)
        os.replace(relative,'evidence.json',src_dir_fd=root,dst_dir_fd=root);os.fsync(root)
        if success:
            # Receipt is published LAST. Its presence alone never establishes exit0.
            name='receipt-'+attempt.attempt_id+'.stage'
            descriptor=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=root)
            try:
                raw=_dto_bytes(dto_receipt(ack,attempt));written=os.write(descriptor,raw)
                if written!=len(raw):raise OSError('partial commit receipt')
                os.fsync(descriptor)
            finally:os.close(descriptor)
            os.replace(name,'commit.json',src_dir_fd=root,dst_dir_fd=root);os.fsync(root)
        return True
    finally:os.close(root)


class DTOOwnedProcess:
    """Only Popen-created identity is signalable; no caller-supplied PID surface."""
    def __init__(self,process,control,kind):
        self.process,self.control,self.kind=process,control,kind
        self.buffer=bytearray();self.ack_read=False;self.saw_progress=False
    def poll(self):return self.process.poll()  # poll performs WNOHANG reap.
    def _receive(self):
        try:
            raw=self.control.recv(4096)
            if self.kind=='worker':
                if any(byte!=ord('P') for byte in raw):raise ValueError('invalid worker control notification')
                self.saw_progress|=bool(raw)
            else:
                self.buffer.extend(raw)
                if len(self.buffer)>_DTO_ACK.size:raise ValueError('oversize/duplicate control ACK')
        except BlockingIOError:pass
    def read_ack(self):
        self._receive()
        if self.ack_read or len(self.buffer)<_DTO_ACK.size:return None
        self.ack_read=True
        return decode_dto_ack(self.buffer)
    def progress_ready(self):self._receive();return self.saw_progress
    def signal_owned_group(self,event):
        if self.process.poll() is None:os.killpg(self.process.pid,signal.SIGTERM if event=='TERM' else signal.SIGKILL)
    def close(self):self.control.close()


def create_dto_process(kind,request,args):
    parent,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
    parent.setblocking(False)
    job=dict(kind=kind,request=request,args=vars(args))
    encoded=base64.urlsafe_b64encode(_dto_bytes(job)).decode('ascii')
    if len(encoded)>16384:raise ValueError('oversize internal job')
    try:
        process=subprocess.Popen([sys.executable,str(ROOT/'scripts/dev/workshop_browser_smoke.py'),'--_dto-owned-fd',str(child.fileno()),encoded],
            start_new_session=True,pass_fds=(child.fileno(),),env=dto_worker_environment(os.environ),close_fds=True)
    except BaseException:
        parent.close();child.close();raise
    child.close()
    return DTOOwnedProcess(process,parent,kind)


async def _dto_worker_run(args,request,control):
    timing=load_dto_timing(FIXTURES/'timing.json')
    initial=_dto_read(Path(args.output)/'initial-observation.json')
    async def provenance():
        def gather():
            provenance=verify_provenance(args)
            sdk=(ROOT/'apps/api-go/workshop/firebase-web.mjs').read_bytes()
            manifest=Path(importlib.metadata.distribution('playwright').locate_file('playwright/driver/package/browsers.json'))
            revisions={item['name']:item['revision'] for item in json.loads(manifest.read_text())['browsers']}
            version=importlib.metadata.version('playwright')
            if version!='1.64.1':raise ValueError('exact Playwright 1.64.1 required')
            return dict(initial,results=[],provenance=provenance,sdk_sha256=hashlib.sha256(sdk).hexdigest(),
                engine_revisions=revisions,playwright_version=version)
        return await asyncio.to_thread(gather)
    persistence_left=timing['evidence_persistence_seconds']
    async def persist(evidence):
        def write():
            nonce=os.urandom(16).hex();target=Path(args.output)/('progress-'+nonce+'.stage')
            _dto_write_private(target,evidence)
            os.replace(target,Path(args.output)/'progress.json')
            directory=os.open(args.output,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(directory)
            finally:os.close(directory)
        await asyncio.to_thread(write)
        # Nonblocking notifications are hints; durable progress survives dropped hints.
        try:control.send(b'P')
        except BlockingIOError:pass
        return True
    try:evidence=await _dto_bounded(provenance(),timing['provenance_seconds'])
    except BaseException as error:
        evidence=dict(initial,failure_kind='provenance_failure',error=str(error),results=complete_dto_failure(_dto_expected(args),[],stage='provenance',kind='provenance_failure',cleanup='unverified'))
        try:await _dto_bounded(persist(evidence),persistence_left)
        except BaseException:pass
        return 1
    lifecycle=DTOPlaywrightLifecycle(args,evidence)
    evidence=await run_dto_inventory(args,clock=time.monotonic,lifecycle=lifecycle,persist=persist,timing=timing)
    try:
        validate_results(evidence['results'],_dto_expected(args))
        if evidence['cleanup_status']!='verified' or evidence.get('failure_kind'):return 1
        return 0
    except ValueError:return 1


def dto_internal_entry(argv):
    """Internal marker is usable only with the inherited socket from our parent."""
    control=None
    try:
        if len(argv)!=3 or argv[0]!='--_dto-owned-fd':raise ValueError('owned descriptor required')
        descriptor=int(argv[1]);control=socket.socket(fileno=descriptor)
        pid,uid,gid=struct.unpack('3i',control.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if pid!=os.getppid() or uid!=os.getuid() or control.family!=socket.AF_UNIX:raise ValueError('unowned control peer')
        if len(argv[2])>16384:raise ValueError('oversize job')
        job=json.loads(base64.urlsafe_b64decode(argv[2]),object_pairs_hook=_unique_json)
        args=argparse.Namespace(**job['args']);request=job['request'];kind=job['kind']
        if kind not in ('init','progress','final','nonpass','worker') or kind!=request['kind']:raise ValueError('invalid helper job')
        candidate_identity(args.candidate_sha);fixture_origin(args.base_url)
        if args.mode!='dto-fixture' or args.browser not in (*ENGINES,'all'):raise ValueError('DTO-only internal job')
        dto_stage_path(args.output,request);control.setblocking(False)
    except (OSError,ValueError,KeyError,TypeError) as error:
        if control is not None:control.close()
        raise ValueError('direct worker mode requires an owned control descriptor') from error
    try:
        if kind=='worker':
            # Never asyncio.run(): do not drain cancellation-resistant tasks/executors.
            loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
            try:return loop.run_until_complete(_dto_worker_run(args,request,control))
            finally:
                for task in asyncio.all_tasks(loop):task.cancel()
                loop.close()
        ack=perform_dto_io(kind,request,args)
        raw=encode_dto_ack(ack)
        if control.send(raw)!=len(raw):raise OSError('partial helper ACK')
        return 0
    finally:control.close()


def main(argv=None):
    producer_started=time.monotonic()  # FIRST action: argparse and all DTO I/O consume this epoch.
    argv=list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0]=='--_dto-owned-fd':return dto_internal_entry(argv)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True,type=fixture_origin)
    parser.add_argument('--mode',required=True,choices=['dto-fixture','api-fixture'])
    parser.add_argument('--browser',required=True,choices=[*ENGINES,'all'])
    parser.add_argument('--candidate-sha',required=True,type=candidate_identity)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    if args.mode=='api-fixture':
        asyncio.run(asyncio.wait_for(run(args),timeout=4440))
        return 0
    if not Path(args.output).is_absolute() or '\0' in args.output:raise ValueError('absolute owned DTO output required')
    pending=[]
    def latch(signum,frame):pending.append(signum)
    previous={sig:signal.signal(sig,latch) for sig in (signal.SIGINT,signal.SIGTERM)}
    try:
        return supervise_dto(args,clock=time.monotonic,process_factory=create_dto_process,
            writer_factory=create_dto_process,timing=DTO_TIMING_V1,cancelled=lambda:bool(pending),
            producer_started=producer_started)
    finally:
        for sig,handler in previous.items():signal.signal(sig,handler)


if __name__=='__main__':
    if sys.argv[1:2]==['--_dto-owned-fd']:
        # Even exceptions cannot enter interpreter executor/task cancellation drain.
        try:code=main()
        except BaseException:code=1
        os._exit(code)
    raise SystemExit(main())
