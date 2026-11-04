#!/usr/bin/env python3
"""Bounded Workshop browser acceptance; DTO checks never count as real API proof."""
import argparse
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
    if any(type(value) is not int or value <= 0 for key,value in timing.items() if key != 'version'):
        raise ValueError('DTO timing values must be finite positive integers')
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
        raise
    except Exception as error:
        diagnostics.fail(error)
    finally:
        diagnostics.execution_elapsed_seconds = time.monotonic() - start
        await diagnostics.finish()
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

class APIFixture(DTOFixture):
    def __init__(self,origin,scenario):
        super().__init__(origin,scenario)
        self.lost_response_count=0
        # Exact request/response identities stay in memory, never browser evidence.
        self.checkout_responses=[]

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
                try:body=json.loads(request.post_data)
                except (TypeError,ValueError):raise AssertionError('checkout request must be JSON') from None
                assert isinstance(body,dict), 'checkout request must be an object'
                configuration=body.get('configuration_id')
                assert isinstance(configuration,str) and re.fullmatch(uuid_pattern,configuration), 'invalid checkout configuration'
                assert body.get('region')=='US', 'unexpected checkout region'
                if attempt==2:
                    assert key==self.keys[0] and request.post_data==self.checkout_bodies[0], 'retry changed checkout request'
                self.keys.append(key);self.checkout_bodies.append(request.post_data)
                response=await route.fetch(max_redirects=0,max_retries=0)
                assert response.status in (200,201), 'actual API did not complete checkout'
                checkout=await response.json()
                assert isinstance(checkout,dict) and checkout.get('version')=='v1' and checkout.get('state')=='checkout', 'invalid actual checkout response'
                assert checkout.get('configuration_id')==configuration and checkout.get('region')==body['region'], 'checkout response changed scope'
                order=checkout.get('order_id');hosted=checkout.get('checkout_url')
                assert isinstance(order,str) and re.fullmatch(uuid_pattern,order), 'invalid checkout order'
                assert isinstance(hosted,str) and allowed_external(hosted), 'untrusted hosted checkout'
                hosted_url=urlsplit(hosted)
                assert hosted_url.hostname=='checkout.stripe.com' and re.fullmatch(r'/c/pay/cs_test_[a-f0-9]{32}',hosted_url.path) and not hosted_url.query, 'invalid hosted checkout session'
                identity={'order_id':order,'configuration_id':configuration,'region':body['region'],'checkout_url':hosted}
                if attempt==1:
                    self.checkout_responses.append(identity)
                    await route.abort()
                    self.lost_response_count+=1
                else:
                    assert identity==self.checkout_responses[0], 'retry changed actual checkout identity'
                    self.checkout_responses.append(identity)
                    await route.fulfill(response=response)
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

async def api_measure(context,origin):
    response=await context.request.get(origin+'/__fixture/measurement')
    assert response.status==200
    return await response.json()

async def api_control(context,origin,path):
    response=await context.request.post(origin+'/__fixture/'+path)
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


async def api_snapshot(context,origin):
    response=await context.request.get(origin+'/__fixture/snapshot')
    assert response.status==200
    return await response.json()


async def api_case(browser,origin,name,output):
    from playwright.async_api import expect
    context=await browser.new_context(ignore_https_errors=True,viewport={'width':1280,'height':900})
    transport=APIFixture(origin,name)
    await context.route('**/*',transport.route)
    page=await context.new_page();page.on('pageerror',lambda error:transport.errors.append(str(error)))
    assertions={};restart_receipt={};warm_receipt={}
    try:
        response=await context.request.get(origin+'/__fixture/metadata');metadata=await response.json()
        assert metadata['kind']=='api-fixture'
        scope=metadata['scope'];configuration=scope['configuration'];article_id=scope['article']
        route=origin+'/workshop/?configuration='+configuration+'&region=US'
        before=await api_measure(context,origin)
        await page.goto(route);await api_signin(page)
        cookies=await context.cookies(origin)
        cookie=next(c for c in cookies if c['name']=='__Host-autodata_session')
        assert cookie['secure'] and cookie['httpOnly'] and cookie['sameSite']=='Lax'
        signed=await api_measure(context,origin)
        assert signed['auth_sessions']==before['auth_sessions']+1 and signed['hashed_sessions']==signed['auth_sessions'] and signed['sdk_cert_calls']>=1 and signed['sdk_user_calls']>=2 and signed['sdk_unexpected']==0
        assertions['official_sdk_cookie_and_pg_session']=True
        await expect(page.locator('#purchase-action')).to_be_enabled()
        await expect(page.locator('#purchase-message')).to_contain_text('purchase')
        await page.locator('#agreement').check()
        await page.locator('#purchase-action').click(click_count=2,delay=0)
        if name==API_CASES[0]:
            await expect(page.locator('#retry')).to_be_visible()
            assert transport.checkout_count==1 and transport.lost_response_count==1
            lost_measurement=await api_measure(context,origin)
            lost_snapshot=await api_snapshot(context,origin)
            transport.validate_pending_checkout(lost_measurement,lost_snapshot)
            await page.locator('#retry').click()
        await page.wait_for_url(re.compile(r'https://checkout\.stripe\.com/c/pay/cs_test_[a-f0-9]{32}.*'))
        pending=await api_measure(context,origin)
        assert pending['workshop_orders']==1 and pending['entitlements']==0
        if name==API_CASES[0]:
            assert transport.checkout_count==2 and transport.lost_response_count==1
            assert len(transport.keys)==2 and transport.keys[0]==transport.keys[1]
            assert len(transport.checkout_bodies)==2 and transport.checkout_bodies[0]==transport.checkout_bodies[1]
            assert len(transport.checkout_responses)==2 and transport.checkout_responses[0]==transport.checkout_responses[1]
            assert page.url==transport.checkout_responses[0]['checkout_url']
            transport.validate_pending_checkout(pending,await api_snapshot(context,origin),lost_snapshot)
            assertions['client_response_loss_same_key_one_checkout']=True
        order=pending['orders'][0]['order_id']
        # A provider return is only a request to check the owner-scoped ledger.
        await page.goto(origin+'/workshop/?order='+order)
        await expect(page.locator('#purchase-message')).to_contain_text('Do not pay again')
        assert (await api_measure(context,origin))['entitlements']==0
        assertions['return_does_not_grant']=True
        await api_control(context,origin,'payment/settle?order_id='+order)
        settled=await api_measure(context,origin)
        assert settled['workshop_orders']==1 and settled['entitlements']==1 and settled['dataset_requests']==1 and settled['dataset_projections']==1 and settled['payment_events']==1
        assertions['signed_public_webhook_grants_once']=True
        await page.goto(route)
        await expect(page.locator('#articles a')).not_to_have_count(0)
        await page.locator('#my-vehicles').click()
        await expect(page.locator('#library-items > li')).to_have_count(1)
        await page.reload();await expect(page.locator('#library-items > li')).to_have_count(1)
        assert (await api_measure(context,origin))['workshop_orders']==1
        assertions['permanent_owner_library_reload']=True
        restart_before=await api_measure(context,origin)
        runtime_before=await (await context.request.get(origin+'/__fixture/runtime')).json()
        await api_control(context,origin,'restart')
        deadline=time.monotonic()+5
        while True:
            try:
                runtime_after=await (await context.request.get(origin+'/__fixture/runtime',timeout=1000)).json()
                if runtime_after['application_generation']==runtime_before['application_generation']+1:break
            except Exception:
                if time.monotonic()>=deadline:raise
            assert time.monotonic()<deadline,'actual application restart did not finish'
            await asyncio.sleep(.05)
        await page.reload();await expect(page.locator('#library-items > li')).to_have_count(1)
        restart_after=await api_measure(context,origin)
        durable=('workshop_orders','workshop_checkout_requests','entitlements','dataset_requests','dataset_projections','payment_events','orders','auth_sessions','hashed_sessions')
        assert {key:restart_before[key] for key in durable}=={key:restart_after[key] for key in durable}
        restart_receipt={'runtime_before':runtime_before,'runtime_after':runtime_after,'before':restart_before,'after':restart_after}
        assertions['permanent_owner_library_server_restart']=True
        if name==API_CASES[0]:
            assert await page.evaluate('Object.keys(localStorage).filter(k=>/firebase:authUser|token|csrf/i.test(k))')==[]
        else:
            await api_control(context,origin,'control/start-workers')
            await page.goto(route+'&article='+article_id)
            await expect(page.locator('#article-kind')).to_have_text('Stored source',timeout=15000)
            await expect(page.locator('#article-content')).to_contain_text('Remove the pump.')
            await expect(page.locator('#print')).to_be_enabled()
            await expect(page.locator('#article-content img')).not_to_have_count(0)
            image_url=await page.locator('#article-content img').first.get_attribute('src')
            assert urlsplit(image_url).path.startswith('/v1/catalog/images/v2.')
            image=await context.request.get(image_url);assert image.status==200 and len(await image.body())>0
            await page.locator('#article-reference summary').click();await page.locator('#source-review-load').click()
            await expect(page.locator('#source-review-frame')).to_contain_text('Remove the pump.')
            source_path=await page.locator('#source-review-link').get_attribute('href')
            assert parse_qs(urlsplit(source_path).query).get('source_revision_id')
            assertions['paid_source_and_actual_s3_image']=True
            await api_control(context,origin,'control/release-model')
            await expect(page.locator('#article-kind')).to_have_text('Workshop article',timeout=15000)
            await expect(page.locator('#article-content')).not_to_be_empty()
            warm_before=await api_snapshot(context,origin)
            reader_before=(await api_measure(context,origin))['image_reads']
            await page.reload();await expect(page.locator('#article-kind')).to_have_text('Workshop article')
            await expect(page.locator('#article-content img')).not_to_have_count(0)
            warm_image=await page.locator('#article-content img').first.get_attribute('src')
            delivered=await context.request.get(warm_image);assert delivered.status==200 and len(await delivered.body())>0
            pinned=await context.request.get(origin+source_path);assert pinned.status==200
            warm_after=await api_snapshot(context,origin)
            reader_after=(await api_measure(context,origin))['image_reads']
            validate_warm_runtime(warm_before,warm_after,reader_before,reader_after)
            warm_receipt={'before':warm_before,'after':warm_after,'reader_before':reader_before,'reader_after':reader_after}
            assertions['source_to_canonical_and_warm_reuse']=True
            assertions['warm_raw_runtime_unchanged_with_approved_s3_delivery']=True
            if name==API_CASES[2]:
                for denied in (f'/v1/catalog/vehicles/{scope["adjacent"]}/articles',f'/v1/catalog/vehicles/{scope["other_region"]}/articles',f'/v1/catalog/vehicles/{configuration}/articles/{scope["unscoped"]}',f'/v1/catalog/vehicles/{scope["vehicle"]}/articles'):
                    denied_response=await context.request.get(origin+denied)
                    assert denied_response.status in (403,404), f'adjacent/legacy route exposed status{denied_response.status}'
                other=await browser.new_context(ignore_https_errors=True)
                other_transport=APIFixture(origin,name);other_transport.account='other';await other.route('**/*',other_transport.route)
                other_page=await other.new_page()
                try:
                    await other_page.goto(route);await api_signin(other_page)
                    denied=await other.request.get(origin+f'/v1/catalog/vehicles/{configuration}/articles');assert denied.status==403
                    library_response=await other.request.get(origin+'/v1/workshop/library?limit=20');assert (await library_response.json())['items']==[]
                    denied_image=await other.request.get(image_url);assert denied_image.status==404
                    assert not other_transport.unexpected and not other_transport.errors
                finally:await other.close()
                assertions['account_and_exact_scope_isolation']=True
                await page.locator('#signout').click();await expect(page.locator('#article-content')).to_be_empty()
                assert (await context.request.get(image_url)).status==401
                await page.evaluate('window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true}))');await expect(page.locator('#article-content')).to_be_empty()
                await api_signin(page);await page.goto(route+'&article='+article_id);await expect(page.locator('#article-kind')).to_have_text('Workshop article')
                await api_control(context,origin,'disable')
                assert (await context.request.get(image_url)).status==401
                await page.reload();await expect(page.locator('#article-content')).to_be_empty()
                assertions['logout_bfcache_and_firebase_disable_deny']=True
            elif name==API_CASES[3]:
                await api_control(context,origin,'payment/refund?order_id='+order)
                old=await context.request.get(image_url);assert old.status==403
                source=await context.request.get(origin+source_path);assert source.status==403
                detail=await context.request.get(origin+f'/v1/catalog/vehicles/{configuration}/articles/{article_id}');assert detail.status==403
                revoked=await api_measure(context,origin);assert revoked['orders'][0]['state']=='revoked' and revoked['entitlements']==1
                await page.reload();await expect(page.locator('#article-content')).to_be_empty();await expect(page.locator('#purchase-action')).to_be_disabled()
                await page.locator('#my-vehicles').click();await expect(page.locator('#library-items')).to_contain_text('Access revoked')
                assertions['signed_full_refund_denies_old_content_and_media']=True
        assert not transport.unexpected and not transport.errors, {'unexpected':transport.unexpected,'errors':transport.errors}
        final=await api_measure(context,origin);assert final['sdk_unexpected']==0
        return {'status':'passed','assertions':assertions,'provider':scope['provider'],'requests':transport.requests,'measurement':final,'restart':restart_receipt,'warm':warm_receipt}
    except BaseException:
        output.mkdir(mode=0o700,parents=True,exist_ok=True)
        try:await page.screenshot(path=str(output/(name+'-failure.png')),timeout=1500)
        except Exception:pass
        raise
    finally:await context.close()


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
            'clock_or_lifecycle_failure', str(error) or type(error).__name__)
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
                # A returned ordinary exception owns no browser. Timeout is uncertain.
                if isinstance(error,TimeoutError): raise
                rows.extend(dict(browser=engine,scenario=name,status='failed',error=str(error)) for name in inventory())
                await snapshot();continue
            try:
                for name in inventory():
                    stage='case';begin=clock()
                    result=await lifecycle.case(browser,name,Path(args.output)/engine)
                    rows.append(dict(browser=engine,scenario=name,elapsed_seconds=round(clock()-begin,3),**result))
                    evidence.setdefault('browser_versions',{})[engine]=browser.version
                    await snapshot()
            finally:
                stage='engine.close'
                owned,browser=browser,None
                await operation(lambda:lifecycle.close(owned),timing['engine_close_seconds'])
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
        if self.manager is not None:await self.manager.stop()


async def run(args):
    from playwright.async_api import async_playwright
    engines=ENGINES if args.browser=='all' else (args.browser,)
    names=inventory() if args.mode=='dto-fixture' else [os.environ.get('AUTODATA_WORKSHOP_BROWSER_CASE')]
    if args.mode=='api-fixture' and (len(engines)!=1 or names[0] not in API_CASES): raise ValueError('API mode requires one frozen owned pytest case/engine')
    expected=[(engine,name) for engine in engines for name in names]
    output=Path(args.output);output.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(output,0o700)
    provenance=verify_provenance(args)
    rows=[]
    sdk=(ROOT/'apps/api-go/workshop/firebase-web.mjs').read_bytes()
    browser_manifest=Path(importlib.metadata.distribution('playwright').locate_file('playwright/driver/package/browsers.json'))
    revisions={item['name']:item['revision'] for item in json.loads(browser_manifest.read_text())['browsers']}
    inputs={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [Path(__file__),FIXTURES/'scenarios.json',FIXTURES/'firebase_transport.js',FIXTURES/'hostile_source.json',FIXTURES/'stripe_checkout.html',ROOT/'apps/api-go/workshop_browser_fixture_test.go']}
    evidence={'engine_revisions':revisions,'input_sha256':inputs,'version':'v1','mode':args.mode,'candidate_sha':args.candidate_sha,'sdk_sha256':hashlib.sha256(sdk).hexdigest(),'playwright_version':importlib.metadata.version('playwright'),'results':rows,'provenance':provenance}
    if evidence['playwright_version']!='1.64.1': raise ValueError('exact Playwright 1.64.1 is required')
    try:
        async with async_playwright() as playwright:
            for engine in engines:
                try: browser=await getattr(playwright,engine).launch()
                except Exception as error:
                    rows.extend(dict(browser=engine,scenario=name,status='unavailable',error=str(error)) for name in names);continue
                try:
                    for name in names:
                        start=time.monotonic()
                        try:
                            if args.mode=='dto-fixture':
                                result=await run_dto_case(browser,args.base_url,name,output/engine)
                            else:
                                result=await asyncio.wait_for(api_case(browser,args.base_url,name,output/engine),timeout=65)
                        except Exception as error: result={'status':'failed','error':str(error) or type(error).__name__}
                        rows.append(dict(browser=engine,scenario=name,elapsed_seconds=round(time.monotonic()-start,3),**result))
                        evidence['browser_versions']=evidence.get('browser_versions',{})|{engine:browser.version}
                        target=output/'evidence.json';target.write_text(json.dumps(evidence,indent=2)+'\n');os.chmod(target,0o600)
                        print(f"{engine} {name}: {result['status']}",flush=True)
                finally:
                    if args.mode=='dto-fixture': await close_dto_browser(browser)
                    else: await browser.close()
        validate_results(rows,expected)
    finally:
        target=output/'evidence.json';target.write_text(json.dumps(evidence,indent=2)+'\n');os.chmod(target,0o600)
    return evidence


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True,type=fixture_origin)
    parser.add_argument('--mode',required=True,choices=['dto-fixture','api-fixture'])
    parser.add_argument('--browser',required=True,choices=[*ENGINES,'all'])
    parser.add_argument('--candidate-sha',required=True,type=candidate_identity)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    asyncio.run(asyncio.wait_for(run(args),timeout=4440))


if __name__=='__main__': main()
