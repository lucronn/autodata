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


async def select_vehicle(page, configuration=CONFIG):
    for field,value in [('year','2024'),('make','fixture-make'),('model','fixture-model'),('configuration',configuration)]:
        await page.locator('#'+field).select_option(value)


async def open_article(page):
    await page.locator('#articles a').first.click()
    await page.locator('#article-title').filter(has_text='Fixture repair procedure').wait_for()


async def assert_text(page, selector, value):
    from playwright.async_api import expect
    await expect(page.locator(selector)).to_contain_text(value)


async def dto_case(browser, origin, name, output):
    from playwright.async_api import expect
    context=await browser.new_context(ignore_https_errors=True,viewport={'width':390 if name=='keyboard-print-mobile' else 1280,'height':900})
    fixture=DTOFixture(origin,name)
    await context.route('**/*',fixture.route)
    page=await context.new_page();page.on('pageerror',lambda error:fixture.errors.append(str(error)))
    if name == 'google-popup-blocked':
        # Browser popup blocking is exercised at window.open, never by replacing SDK functions.
        await page.add_init_script('window.open=()=>null')
    try:
        url=origin+'/workshop/'
        if name in {'checkout-processing-return','checkout-untrusted-return','checkout-expired'}: url+='?order='+ORDER
        await page.goto(url)
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
            await select_vehicle(page);await assert_text(page,'#articles','Fixture repair procedure');await page.locator('#my-vehicles').click()
            await expect(page.locator('#library-items > li')).to_have_count(4)
            await expect(page.locator('#library-items button')).to_have_count(3)
            await page.locator('#library-more').click();await expect(page.locator('#library-items > li')).to_have_count(5)
            await page.locator('#library-items button').first.click();await assert_text(page,'#articles','Fixture repair procedure')
            assert 'year=' not in page.url and 'configuration='+OTHER in page.url, 'library route retained another vehicle hierarchy'
            await page.reload();await assert_text(page,'#articles','Fixture repair procedure')
        else:
            await select_vehicle(page)
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
                    await open_article(page);await page.go_back();await assert_text(page,'#articles','Fixture repair procedure');await page.go_forward();await assert_text(page,'#article-content','Disconnect battery')
                else:
                    await page.reload();await assert_text(page,'#articles','Fixture repair procedure')
                assert not any('/firebase-web.mjs' in row['path'] for row in fixture.requests)
            else:
                if name in {'session-expired','withdrawal'}:
                    await page.locator('#articles a').first.click()
                    await expect(page.locator('#critical-error')).not_to_be_empty()
                else: await open_article(page)
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
        assert not fixture.unexpected, f'unexpected external/application requests: {fixture.unexpected}'
        assert not fixture.errors, f'browser errors: {fixture.errors}'
        return {'status':'passed','requests':fixture.requests,'sdk_requests':sum(row['path']=='/workshop/firebase-web.mjs' for row in fixture.requests)}
    except BaseException:
        output.mkdir(mode=0o700,parents=True,exist_ok=True)
        try: await page.screenshot(path=str(output/(name+'-failure.png')),timeout=1500)
        except Exception: pass
        raise
    finally:
        await context.close()


API_CASES=(
    'test_browser_google_exchange_checkout_library_real_api',
    'test_browser_owned_source_canonical_and_media_real_api',
    'test_browser_account_scope_and_revocation_real_api',
    'test_browser_signed_refund_blocks_old_links_real_api',
)

class APIFixture(DTOFixture):
    async def route(self,route):
        request=route.request
        if request.url.startswith(self.origin+'/'):
            path=urlsplit(request.url).path
            # Observe safe route templates only. Never manufacture an app response.
            safe=re.sub(r'/v2\.[^/?]+','/{capability}',path)
            safe=re.sub(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}','{uuid}',safe)
            self.requests.append({'method':request.method,'path':safe})
            if request.headers.get('authorization'):self.errors.append('browser sent bearer authorization')
            await route.continue_();return
        if not allowed_external(request.url):
            self.unexpected.append(urlsplit(request.url).hostname);await route.abort();return
        await self.external(route)

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
        if name==API_CASES[0]:await api_control(context,origin,'control/lose-response')
        await page.locator('#purchase-action').click(click_count=2,delay=0)
        if name==API_CASES[0]:
            await expect(page.locator('#retry')).to_be_visible();await page.locator('#retry').click()
        await page.wait_for_url(re.compile(r'https://checkout\.stripe\.com/c/pay/cs_test_[a-f0-9]{32}.*'))
        pending=await api_measure(context,origin)
        assert pending['workshop_orders']==1 and pending['entitlements']==0
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
                    denied_image=await other.request.get(image_url);assert denied_image.status==403
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
                            case=dto_case if args.mode=='dto-fixture' else api_case
                            result=await asyncio.wait_for(case(browser,args.base_url,name,output/engine),timeout=20 if args.mode=='dto-fixture' else 65)
                        except Exception as error: result={'status':'failed','error':str(error) or type(error).__name__}
                        rows.append(dict(browser=engine,scenario=name,elapsed_seconds=round(time.monotonic()-start,3),**result))
                        evidence['browser_versions']=evidence.get('browser_versions',{})|{engine:browser.version}
                        target=output/'evidence.json';target.write_text(json.dumps(evidence,indent=2)+'\n');os.chmod(target,0o600)
                        print(f"{engine} {name}: {result['status']}",flush=True)
                finally: await browser.close()
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
