"""Private real-store browser smoke; one explicit exact-origin session simulation.

Uses an already-installed matching Node Playwright API/driver, never the broken
Python driver. No installs, downloads, global auth headers or response fixtures.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import re
import stat
import subprocess
import tempfile
import importlib
import time
from contextlib import contextmanager
from urllib.parse import urlsplit

ORIGIN='http://127.0.0.1:3042'
NODE=Path('/usr/bin/node')
PACKAGE_BASE=Path('/home/corp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')
PACKAGE_PINS={'playwright':('1.62.1','cfb3610ff1e5ae0ce983a5a0d74706d14e698f10f65eb885f8123e6c697eb640'), 'playwright-core':('1.62.1','6e4e424e7d4651b64e250707f41548e71ef0620e61252b39f1a91d2354e0ece0')}
FILE_PINS={'/usr/bin/node':'6d2106bd43423cd5b13d414271ae57a4e422b63646fcbd1b008c3ab9ab0f9094','/usr/bin/chromium':'2254527d9535f2b6ba7d11b536cc29d631879546d80f4b88d35791300ec36f5c','/usr/lib/chromium/chromium':'729ba93e76f878b956394b9be6fdcc12ee38c7e52574583e469de34ef73dc80b','/usr/lib/chromium/chrome-sandbox':'3493d4ac9732cb4b038d9aeded97eb14d4bf100a57f5128d06e63cd36b594fb7','/usr/bin/python3.14':'7b6c7e71d7b8caeb173b848d24a9a90bb3ecc348ef0f9a6762b477afc798a91e'}


def request_policy(url,method):
    try:
        u=urlsplit(url)
        if method!='GET' or u.scheme!='http' or u.netloc!='127.0.0.1:3042' or u.username or u.password or u.fragment:return 'abort'
        if u.path=='/auth/session':return 'session' if not u.query else 'abort'
        if u.path.startswith('/v1/catalog/images/'):return 'real'
        if re.fullmatch(r'/v1/catalog/(?:years(?:/[0-9]{4}/makes(?:/[A-Za-z0-9._~-]+/models(?:/[A-Za-z0-9._~-]+/configurations)?)?)?|vehicles/[A-Za-z0-9-]+/articles(?:/[A-Za-z0-9-]+)?)',u.path):return 'catalog'
        if u.path in ('/auth/config','/workshop/purchase-config.json') or u.path.startswith('/workshop/'):return 'real'
    except ValueError:pass
    return 'abort'


def expected_http_denial(url,status,simulated):
    try:
        u=urlsplit(url)
        if u.scheme!='http' or u.netloc!='127.0.0.1:3042' or u.username or u.password:return False
        return (not simulated and u.path=='/auth/session' and not u.query and status==401)
    except ValueError:return False


def trace_errors(simulated_paths,external_requests,console_errors):
    errors=[]
    if not simulated_paths or set(simulated_paths)!={'/auth/session'}:errors.append('simulation_scope')
    if external_requests:errors.append('outbound_request')
    if console_errors:errors.append('console_errors')
    return errors


def dependencies():
    result={}
    for name,(version,pin) in PACKAGE_PINS.items():
        root=PACKAGE_BASE/name
        if json.loads((root/'package.json').read_text())['version']!=version:raise ValueError('package_version')
        h=hashlib.sha256();count=0
        for p in sorted(root.rglob('*')):
            if p.is_symlink():raise ValueError('package_symlink')
            if p.is_file():
                count+=1
                if count>2000:raise ValueError('package_bound')
                h.update(str(p.relative_to(root)).encode()+b'\0'+hashlib.sha256(p.read_bytes()).digest())
        if h.hexdigest()!=pin:raise ValueError('package_hash')
        result[name]={'version':version,'tree_sha256':pin,'files':count}
    for name,pin in FILE_PINS.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=pin:raise ValueError('runtime_hash')
    if stat.S_IMODE(Path('/usr/lib/chromium/chrome-sandbox').stat().st_mode)!=0o4755:raise ValueError('sandbox_mode')
    return {'packages':result,'files':FILE_PINS,'sandbox_enabled':True}

FAILURE_CODES = {'page_clip', 'real_article_steps', 'real_local_disabled_config', 'browser_errors', 'response_bound', 'real_article_text', 'real_config_status', 'browser_runtime', 'one_image', 'commerce_disabled', 'no_quote_or_prepare', 'auth_config_local', 'negative_auth_reader', 'real_config_each_context', 'image_clip', 'one_article_index', 'back_forward_route', 'session_scope', 'display_body_once_and_step_order', 'authentic_data_path', 'reload_clip', 'unsupported_action', 'real_response_status', 'real_png'}
FAILURE_STAGES = {'negative_auth', 'desktop_history', 'desktop_selectors', 'negative_config', 'mobile_detail', 'mobile_index', 'mobile_history', 'probe', 'desktop_navigation', 'host', 'mobile_screenshot', 'mobile_config', 'negative_navigation', 'final_validation', 'desktop_screenshot', 'unknown', 'mobile_image', 'desktop_detail', 'desktop_config', 'desktop_image', 'mobile_navigation', 'negative_selectors', 'desktop_index', 'launch', 'input', 'mobile_selectors'}
FAILURE_COUNTERS = {'external_requests', 'simulated_sessions', 'real_config_verified', 'prepare_requests', 'layouts_completed', 'page_errors', 'requests', 'console_errors', 'quote_requests'}
ROUTE_CATEGORIES = {'catalog', 'static', 'session', 'auth_config', 'commerce', 'image', 'quote', 'prepare', 'blocked'}


def validate_failure_receipt(result):
    if not isinstance(result,dict) or set(result)!={'ok','error','code','stage','counters','route_statuses','partial_screenshot'}:raise ValueError('failure_shape')
    if result['ok'] is not False or result['error']!='owned_browser_failed_preserve_state' or result['code'] not in FAILURE_CODES or result['stage'] not in FAILURE_STAGES:raise ValueError('failure_code')
    counts=result['counters']
    if not isinstance(counts,dict) or set(counts)-FAILURE_COUNTERS or any(type(v) is not int or not 0<=v<=221 for v in counts.values()):raise ValueError('failure_counters')
    routes=result['route_statuses']
    if not isinstance(routes,list) or len(routes)>64:raise ValueError('failure_routes')
    for item in routes:
        if not isinstance(item,dict) or set(item)!={'category','status','count'} or item['category'] not in ROUTE_CATEGORIES or type(item['status']) is not int or not 100<=item['status']<=599 or type(item['count']) is not int or not 1<=item['count']<=221:raise ValueError('failure_route')
    image=result['partial_screenshot']
    if not isinstance(image,dict) or set(image) not in ({'attempted','saved'},{'attempted','saved','sha256'}) or type(image.get('attempted')) is not bool or type(image.get('saved')) is not bool:raise ValueError('failure_screenshot')
    if image['saved'] and (not image['attempted'] or re.fullmatch('[a-f0-9]{64}',image.get('sha256','')) is None):raise ValueError('failure_screenshot_hash')
    if not image['saved'] and 'sha256' in image:raise ValueError('failure_screenshot_hash')
    return result


def write_failure_receipt(path,result):
    validate_failure_receipt(result)
    if path.parent.is_symlink() or path.parent.stat().st_mode&0o777!=0o700:raise ValueError('failure_directory')
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as out:json.dump(result,out,sort_keys=True);out.write('\n')


class BrowserFailure(ValueError):
    def __init__(self,result):
        self.receipt=validate_failure_receipt(result)
        super().__init__('browser_failed')


RUNTIME_ROOT=Path('/home/corp/autodata-workshop-owned-article-data-20261115/m2a')
OPERATIONAL_SEAL=Path('/home/corp/autodata-evidence/m2a-tmpfs-v2-operational-20261115/operational-seal.json')
HELPERS=('workshop_owned_article_admission','workshop_owned_article_forwarder','workshop_owned_article_seed')


def identity_errors(expected,actual):
    return [] if expected==actual else ['operational_identity']


def tmpfs_errors(kind,device,home_device,socket_bytes):
    return [] if kind=='tmpfs' and device!=home_device and 0<socket_bytes<108 else ['tmpfs_policy']


def capacity_errors(observed,policy,entry=False):
    errors=[]
    if policy['home_free_baseline']-observed['home_free']>=policy['home_guard_growth']:errors.append('home_growth_guard')
    if policy['tmp_free_baseline']-observed['tmp_free']>=policy['tmp_guard_growth']:errors.append('tmp_growth_guard')
    if observed['home_free']<=policy['home_absolute_floor']:errors.append('home_floor')
    if observed['docker_free']<=policy['docker_absolute_floor']:errors.append('docker_floor')
    if observed['memory_available']<policy['min_available_memory']:errors.append('memory_guard')
    if observed['inodes']<policy['min_inodes']:errors.append('inode_guard')
    if entry and (observed['home_free']<policy['entry_home_floor'] or observed['tmp_free']<policy['tmp_entry_floor']):errors.append('entry_guard')
    return errors


def observation():
    home=os.statvfs(RUNTIME_ROOT);docker=os.statvfs('/mnt/openfoam/docker');tmp=os.statvfs('/tmp')
    memory=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    return {'home_free':home.f_bavail*home.f_frsize,'docker_free':docker.f_bavail*docker.f_frsize,'tmp_free':tmp.f_bavail*tmp.f_frsize,'memory_available':memory,'inodes':min(home.f_favail,docker.f_favail,tmp.f_favail)}


def runtime_modules():
    directory=RUNTIME_ROOT/'source/scripts/dev'
    for name in HELPERS:
        loaded=sys.modules.get(name)
        if loaded is not None and Path(loaded.__file__).resolve()!=directory/(name+'.py'):raise ValueError('physical_helper_import')
    sys.path.insert(0,str(directory))
    modules={name:importlib.import_module(name) for name in HELPERS}
    if any(Path(module.__file__).resolve()!=directory/(name+'.py') for name,module in modules.items()):raise ValueError('physical_helper_import')
    return modules['workshop_owned_article_forwarder'],modules['workshop_owned_article_seed']


def operational_guard():
    info=OPERATIONAL_SEAL.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size>32768:raise ValueError('operational_receipt')
    fd=os.open(OPERATIONAL_SEAL,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        if os.fstat(stream.fileno())!=info:raise ValueError('operational_receipt_changed')
        seal=json.load(stream)
    required={'version','gate_sha','harness_source_sha','harness_tree','harness_sha256','test_sha256','runtime_source_sha','runtime_tree','runtime_manifest_sha256','runtime_archive_sha256','runtime_binary_sha256','runtime_config_sha256','runtime_accepted_sha256','helper_sha256','capacity','namespace','dependency_pins'}
    if set(seal)!=required or seal['version']!=1 or seal['namespace']!='image-contract-v2' or seal['runtime_source_sha']!='668d4c86f4097b9d2c7880dedf2e0fccc8079da6':raise ValueError('operational_contract')
    hashes={name:hashlib.sha256((RUNTIME_ROOT/'source/scripts/dev'/(name+'.py')).read_bytes()).hexdigest() for name in HELPERS}
    actual={'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'helper_sha256':hashes}
    if identity_errors({key:seal[key] for key in actual},actual):raise ValueError('operational_identity')
    for child,key in [('source.tar','runtime_archive_sha256'),('bin/autodata-api','runtime_binary_sha256'),('private-config/manifest.json','runtime_manifest_sha256'),('private-config/accepted-state.json','runtime_accepted_sha256')]:
        if hashlib.sha256((RUNTIME_ROOT/child).read_bytes()).hexdigest()!=seal[key]:raise ValueError('runtime_identity')
    manifest=json.loads((RUNTIME_ROOT/'private-config/manifest.json').read_text())
    if manifest['source_sha']!=seal['runtime_source_sha'] or manifest['source_tree']!=seal['runtime_tree'] or manifest['config_sha256']!=seal['runtime_config_sha256']:raise ValueError('runtime_manifest')
    policy=seal['capacity']
    if (policy['home_growth_cap'],policy['home_guard_growth'],policy['tmp_growth_cap'],policy['tmp_guard_growth'])!=(67108864,33554432,134217728,100663296):raise ValueError('capacity_policy')
    return seal


@contextmanager
def browser_environment(policy=None):
    mount=[line.split(' - ',1)[1].split()[0] for line in Path('/proc/self/mountinfo').read_text().splitlines() if line.split()[4]=='/tmp']
    if len(mount)!=1 or tmpfs_errors(mount[0],Path('/tmp').stat().st_dev,RUNTIME_ROOT.stat().st_dev,81):raise ValueError('tmpfs_policy')
    if policy and capacity_errors(observation(),policy,entry=True):raise ValueError('browser_capacity')
    with tempfile.TemporaryDirectory(prefix='.m2a-browser-',dir='/tmp') as tmp:
        root=Path(tmp);root.chmod(0o700);cache=root/'.cache';cache.mkdir(mode=0o700)
        if len(os.fsencode(str(root/'playwright_chromiumdev_profile-XXXXXX/SingletonSocket')))>=108:raise ValueError('socket_path')
        yield {'PATH':'/usr/bin:/bin','HOME':tmp,'TMPDIR':tmp,'XDG_CACHE_HOME':str(cache),'LANG':'C.UTF-8'}


RUNNER=r'''
const fs=require('fs');const crypto=require('crypto');
process.umask(0o077);
const ORIGIN='http://127.0.0.1:3042';
const token='Bearer local:11111111-1111-4111-8111-111111111111:dataset_viewer';
function policy(url,method){try{const u=new URL(url);if(method!=='GET'||u.origin!==ORIGIN||u.username||u.password||u.hash)return'abort';if(u.pathname==='/auth/session')return u.search?'abort':'session';if(u.pathname.startsWith('/v1/catalog/images/'))return'real';if(/^\/v1\/catalog\/(?:years(?:\/[0-9]{4}\/makes(?:\/[A-Za-z0-9._~-]+\/models(?:\/[A-Za-z0-9._~-]+\/configurations)?)?)?|vehicles\/[A-Za-z0-9-]+\/articles(?:\/[A-Za-z0-9-]+)?)$/.test(u.pathname))return'catalog';if(['/auth/config','/workshop/purchase-config.json'].includes(u.pathname)||u.pathname.startsWith('/workshop/'))return'real';}catch{}return'abort';}
function expectedDenial(url,status,simulated){try{const u=new URL(url);if(u.origin!==ORIGIN||u.username||u.password)return false;return(!simulated&&u.pathname==='/auth/session'&&!u.search&&status===401);}catch{return false;}}
function configSafe(auth,commerce){return auth?.mode==='local'&&commerce?.enabled===false;}
function pngSafe(item,fixture){return item.kind==='image'&&item.status===200&&item.bytes===151&&item.mime==='image/png'&&item.sha256===fixture.image.sha256;}
function presentationSafe(text,article){
 const body=article.body;if(!body||text.split(body).length!==2)return false;
 let position=text.indexOf(body)+body.length;
 for(const step of article.steps){for(const part of [step.heading,...step.instructions]){const next=text.indexOf(part,position);if(next<position)return false;position=next+part.length;}}
 return true;
}
const SAFE_CODES=new Set(["browser_runtime", "unsupported_action", "auth_config_local", "authentic_data_path", "back_forward_route", "browser_errors", "commerce_disabled", "display_body_once_and_step_order", "image_clip", "negative_auth_reader", "no_quote_or_prepare", "one_article_index", "one_image", "page_clip", "real_article_steps", "real_article_text", "real_config_each_context", "real_config_status", "real_local_disabled_config", "real_png", "real_response_status", "reload_clip", "response_bound", "session_scope"]);
const SAFE_STAGES=new Set(["unknown", "input", "launch", "probe", "host", "negative_config", "negative_navigation", "negative_selectors", "negative_auth", "final_validation", "desktop_config", "desktop_navigation", "desktop_selectors", "desktop_index", "desktop_detail", "desktop_image", "desktop_history", "desktop_screenshot", "mobile_config", "mobile_navigation", "mobile_selectors", "mobile_index", "mobile_detail", "mobile_image", "mobile_history", "mobile_screenshot"]);
const COUNTERS=["requests", "simulated_sessions", "external_requests", "console_errors", "page_errors", "quote_requests", "prepare_requests", "real_config_verified", "layouts_completed"];
const CATEGORIES=new Set(["auth_config", "session", "commerce", "quote", "prepare", "image", "catalog", "static", "blocked"]);
function safeCode(code){return SAFE_CODES.has(code)?code:'browser_runtime';}
function category(url,method='GET'){try{const u=new URL(url);if(u.origin!==ORIGIN)return'blocked';if(u.pathname==='/auth/config')return'auth_config';if(u.pathname==='/auth/session')return'session';if(u.pathname==='/workshop/purchase-config.json')return'commerce';if(u.pathname==='/v1/workshop/quote')return'quote';if(u.pathname.endsWith('/prepare'))return'prepare';if(u.pathname.startsWith('/v1/catalog/images/'))return'image';if(policy(url,method)==='catalog')return'catalog';if(u.pathname.startsWith('/workshop/'))return'static';}catch{}return'blocked';}
function failureDiagnostic(code,stage,report={}){
 const counters={};for(const key of COUNTERS){const value=report[key];counters[key]=Number.isInteger(value)?Math.max(0,Math.min(221,value)):0;}
 const routes=(Array.isArray(report.route_statuses)?report.route_statuses:[]).filter(x=>CATEGORIES.has(x.category)&&Number.isInteger(x.status)&&x.status>=100&&x.status<=599&&Number.isInteger(x.count)&&x.count>=1&&x.count<=221).slice(0,64).map(x=>({category:x.category,status:x.status,count:x.count}));
 return{ok:false,error:'owned_browser_failed_preserve_state',code:safeCode(code),stage:SAFE_STAGES.has(stage)?stage:'unknown',counters,route_statuses:routes,partial_screenshot:{attempted:false,saved:false}};
}
async function captureFailure(result,page,target){
 if(!page)return result;result.partial_screenshot.attempted=true;
 try{const bytes=await page.screenshot({path:target,fullPage:true,timeout:1500});result.partial_screenshot.saved=true;result.partial_screenshot.sha256=hash(bytes);if(target)fs.chmodSync(target,0o600);}catch{}
 return result;
}

function journalValid(e){return e&&Object.keys(e).sort().join(',')==='category,count,method,stage,status'&&SAFE_STAGES.has(e.stage)&&[...CATEGORIES,'lifecycle'].includes(e.category)&&['GET','NONE','OTHER'].includes(e.method)&&Number.isInteger(e.status)&&(e.status===0||e.status>=100&&e.status<=599)&&Number.isInteger(e.count)&&e.count>=0&&e.count<=220;}
function journalWriter(write){let bytes=0,count=0;return e=>{if(!journalValid(e))throw Error('journal_schema');const line=JSON.stringify(e)+'\n';const size=Buffer.byteLength(line);if(bytes+size>65536||count>=512)throw Error('journal_bound');write(line);bytes+=size;count++;};}

const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
function assert(value,code){if(!value)throw Error(code);}
(async()=>{let browser,input,report,diagnosticPage,journalFD,journal,requests=0,stage='input';try{
 input=JSON.parse(fs.readFileSync(0,'utf8'));
 if(input.action==='policy'&&input.journal_test){const lines=[];const writer=journalWriter(line=>lines.push(line));writer(input.journal_test[0]);const preserved=lines[0];let bounded=false;try{for(let n=0;n<600;n++)writer(input.journal_test[0]);}catch{bounded=true;}console.log(JSON.stringify({ok:true,journal_valid:input.journal_test.map(journalValid),journal_prefix_preserved:lines[0]===preserved,journal_bound_rejected:bounded}));return;}
 if(input.action==='policy'&&input.failure_policy){const failures=[];for(const item of input.failures){const result=failureDiagnostic(item.code,item.stage,{requests:item.requests,route_statuses:item.route_statuses});if(input.screenshot_failure)await captureFailure(result,{screenshot:async()=>{throw Error('synthetic screenshot failure');}},null);failures.push(result);}console.log(JSON.stringify({ok:true,failures}));return;}
 if(input.action==='policy'){console.log(JSON.stringify({ok:true,policies:input.cases.map(([u,m])=>policy(u,m)),denials:(input.denials||[]).map(([u,status,simulated])=>expectedDenial(u,status,simulated))}));return;}
 if(input.action==='validate'){console.log(JSON.stringify({ok:true,configs:input.configs.map(([a,c])=>configSafe(a,c)),presentations:input.presentations.map(([t,a])=>presentationSafe(t,a)),pngs:(input.pngs||[]).map(([r,f])=>pngSafe(r,f))}));return;}
 if(!['probe','smoke'].includes(input.action))throw Error('unsupported_action');stage='launch';
 if(input.action==='smoke'){journalFD=fs.openSync(input.journal,'wx',0o600);journal=journalWriter(line=>{const bytes=Buffer.from(line);let at=0;while(at<bytes.length)at+=fs.writeSync(journalFD,bytes,at,bytes.length-at);fs.fsyncSync(journalFD);});journal({stage:'launch',category:'lifecycle',method:'NONE',status:0,count:0});}
 const {chromium}=require('/home/corp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',chromiumSandbox:true,headless:true,timeout:15000});
 if(input.action==='probe'){stage='probe';const page=await browser.newPage();await page.goto('about:blank');console.log(JSON.stringify({ok:true,version:browser.version(),sandbox_enabled:true}));return;}
 const fixture=input.fixture;report={ok:false,simulated_paths:[],external_requests:[],console_errors:[],page_errors:[],responses:[],layouts:[],negative_auth:false,expected_http_denials:[],quote_requests:0,prepare_requests:0,real_config_verified:0,route_statuses:[]};
 const pending=[];
 const makeContext=async(simulate,viewport)=>{
  const boundary={auth:null,commerce:null};
  const context=await browser.newContext({viewport,serviceWorkers:'block',acceptDownloads:false});
  await context.route('**/*',async route=>{
   const req=route.request(),kind=policy(req.url(),req.method());
   const path=new URL(req.url()).pathname;if(path==='/v1/workshop/quote')report.quote_requests++;if(path.endsWith('/prepare'))report.prepare_requests++;
   if(++requests<=220&&journal)journal({stage,category:category(req.url(),req.method()),method:req.method()==='GET'?'GET':'OTHER',status:0,count:requests});
   if(requests>220){report.external_requests.push('request_bound');return route.abort();}
   if(kind==='abort'){report.external_requests.push('blocked_request');return route.abort();}
   if(kind==='session'&&simulate){if(!configSafe(boundary.auth,boundary.commerce)){report.page_errors.push('config_before_simulation');return route.abort();}report.simulated_paths.push('/auth/session');return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({version:'v1',authenticated:true,roles:['dataset_viewer'],expires_at:new Date(Date.now()+180000).toISOString(),csrf_token:'synthetic-m2a-browser-only'})});}
   const headers={...req.headers()};delete headers.authorization;
   if(kind==='catalog')headers.authorization=token;
   return route.continue({headers});
  });
  for(const [path,key] of [['/auth/config','auth'],['/workshop/purchase-config.json','commerce']]){
   if(++requests>220)throw Error('response_bound');if(journal)journal({stage,category:category(ORIGIN+path),method:'GET',status:0,count:requests});
   const response=await context.request.get(ORIGIN+path,{maxRedirects:0,timeout:5000});
   if(journal)journal({stage,category:category(ORIGIN+path),method:'GET',status:response.status(),count:requests});
   assert(response.status()===200,'real_config_status');boundary[key]=await response.json();
  }
  assert(configSafe(boundary.auth,boundary.commerce),'real_local_disabled_config');report.real_config_verified++;
  const page=await context.newPage();diagnosticPage=page;page.setDefaultTimeout(10000);page.setDefaultNavigationTimeout(10000);
  page.on('download',async download=>{await download.cancel();report.external_requests.push('download');});
  page.on('pageerror',()=>report.page_errors.push('page_error'));
  page.on('console',msg=>{if(msg.type()!=='error')return;const text=msg.text(),match=text.match(/^Failed to load resource: the server responded with a status of (401|503) /);if(match&&expectedDenial(msg.location().url,Number(match[1]),simulate))report.expected_http_denials.push({kind:'unshimmed_session',status:Number(match[1])});else report.console_errors.push('console_error');});
  page.on('response',response=>{pending.push((async()=>{
   const u=new URL(response.url());const cat=category(response.url());if(journal)journal({stage,category:cat,method:'GET',status:response.status(),count:requests});const found=report.route_statuses.find(x=>x.category===cat&&x.status===response.status());if(found)found.count++;else if(report.route_statuses.length<64)report.route_statuses.push({category:cat,status:response.status(),count:1});if(u.origin!==ORIGIN){report.external_requests.push('external_response');return;}
   if(response.status()>=300&&response.status()<400){report.external_requests.push('redirect');return;}
   const image=u.pathname.startsWith('/v1/catalog/images/');const catalog=policy(response.url(),'GET')==='catalog';
   if(!image&&!catalog&&u.pathname!=='/workshop/purchase-config.json'&&u.pathname!=='/auth/config')return;
   const data=await response.body();assert(data.length<=2097152,'response_bound');
   const item={kind:image?'image':catalog?'catalog':u.pathname==='/auth/config'?'auth_config':'commerce',status:response.status(),bytes:data.length,sha256:hash(data),mime:(response.headers()['content-type']||'').split(';')[0]};
   report.responses.push(item);
   if(!simulate)return;
   assert(response.status()===200,'real_response_status');
   if(image){assert(pngSafe(item,fixture),'real_png');return;}
   const parsed=JSON.parse(data);
   if(item.kind==='auth_config'){assert(parsed.mode==='local','auth_config_local');return;}
   if(item.kind==='commerce'){assert(parsed.enabled===false,'commerce_disabled');return;}
   if(u.pathname.endsWith('/articles/'+fixture.ids.article)){
    const article=parsed.article||parsed;assert(article.title===fixture.article.title&&article.body===fixture.article.body,'real_article_text');
    assert(JSON.stringify(article.steps.map(s=>({number:s.number,heading:s.heading,instructions:s.instructions})))===JSON.stringify(fixture.article.steps),'real_article_steps');
    report.real_detail_verified=true;
   }
  })().catch(error=>report.page_errors.push(safeCode(error.message))));});
  return{context,page};
 };
 for(const [name,viewport] of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
  const imageStart=report.responses.filter(r=>r.kind==='image').length;
  stage=name+'_config';const {context,page}=await makeContext(true,viewport);stage=name+'_navigation';await page.goto(ORIGIN+'/workshop/');
  stage=name+'_selectors';for(const selector of ['year','make','model','configuration']){
   await page.waitForFunction(id=>{const e=document.getElementById(id);return e&&!e.disabled&&e.options.length===2;},selector);
   await page.selectOption('#'+selector,{index:1});
  }
  stage=name+'_index';const link=page.locator('#articles a').filter({hasText:fixture.article.title});await link.waitFor({state:'visible'});
  assert(await page.locator('#articles a').count()===1,'one_article_index');
  stage=name+'_detail';await link.click();await page.locator('#article-title').filter({hasText:fixture.article.title}).waitFor({state:'visible'});
  assert(presentationSafe(await page.locator('#article-content').innerText(),fixture.article),'display_body_once_and_step_order');
  stage=name+'_image';const image=page.locator('#article-content img');assert(await image.count()===1,'one_image');
  await image.waitFor({state:'visible'});await page.waitForFunction(()=>{const e=document.querySelector('#article-content img');return e?.complete&&e.naturalWidth===64&&e.naturalHeight===48;});
  const box=await image.boundingBox();assert(box&&box.width>0&&box.height>0&&box.x>=0&&box.x+box.width<=viewport.width+1,'image_clip');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'page_clip');
  stage=name+'_history';const detailURL=page.url();await page.goBack();await link.waitFor({state:'visible'});await link.click();
  assert(page.url()===detailURL,'back_forward_route');await page.reload();await image.waitFor({state:'visible'});
  await page.waitForFunction(title=>document.getElementById('article-title').textContent===title,fixture.article.title);
  assert(presentationSafe(await page.locator('#article-content').innerText(),fixture.article),'display_body_once_and_step_order');
  assert(await image.count()===1,'one_image');await page.waitForFunction(()=>{const e=document.querySelector('#article-content img');return e?.complete&&e.naturalWidth===64&&e.naturalHeight===48;});
  const reloadBox=await image.boundingBox();assert(reloadBox&&reloadBox.width>0&&reloadBox.height>0&&reloadBox.x>=0&&reloadBox.x+reloadBox.width<=viewport.width+1,'image_clip');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'reload_clip');
  await Promise.all(pending);const realPNGs=report.responses.filter(r=>r.kind==='image').slice(imageStart);assert(realPNGs.length>0&&realPNGs.every(r=>pngSafe(r,fixture)),'real_png');
  stage=name+'_screenshot';const screenshot=input.output+'/'+name+'.png';await page.screenshot({path:screenshot,fullPage:true});
  report.layouts.push({name,viewport,back:true,reload:true,clipping:false,png_natural:[64,48],real_png_200_count:realPNGs.length,original_body_and_order:true,screenshot_sha256:hash(fs.readFileSync(screenshot))});
  await Promise.all(pending);await context.close();
 }
 stage='negative_config';const {context:negative,page:np}=await makeContext(false,{width:390,height:844});stage='negative_navigation';await np.goto(ORIGIN+'/workshop/');
 stage='negative_selectors';for(const selector of ['year','make','model','configuration']){
  await np.waitForFunction(id=>{const e=document.getElementById(id);return e&&!e.disabled&&e.options.length===2;},selector);await np.selectOption('#'+selector,{index:1});
 }
 stage='negative_auth';await np.getByText('Sign in to check access to your selected vehicle.',{exact:true}).waitFor({state:'visible'});
 assert(await np.locator('#article-content:visible').count()===0,'negative_auth_reader');report.negative_auth=true;
 await Promise.all(pending);await negative.close();
 stage='final_validation';assert(report.real_detail_verified&&report.responses.some(r=>r.kind==='image'&&r.status===200),'authentic_data_path');
 assert(report.simulated_paths.length>0&&report.simulated_paths.every(p=>p==='/auth/session'),'session_scope');
 assert(report.quote_requests===0&&report.prepare_requests===0,'no_quote_or_prepare');
 assert(report.real_config_verified===3,'real_config_each_context');
 assert(!report.external_requests.length&&!report.console_errors.length&&!report.page_errors.length,'browser_errors');
 report.ok=true;report.requests=requests;report.browser_version=browser.version();report.sandbox_enabled=true;console.log(JSON.stringify(report));
 }catch(e){const safeReport=report?{requests,simulated_sessions:report.simulated_paths.length,external_requests:report.external_requests.length,console_errors:report.console_errors.length,page_errors:report.page_errors.length,quote_requests:report.quote_requests,prepare_requests:report.prepare_requests,real_config_verified:report.real_config_verified,layouts_completed:report.layouts.length,route_statuses:report.route_statuses}:{};const code=e.message==='browser_errors'&&report?.page_errors.length?report.page_errors[0]:e.message;const result=failureDiagnostic(code,stage,safeReport);await captureFailure(result,diagnosticPage,input?.output?input.output+'/failure.png':null);console.log(JSON.stringify(result));process.exitCode=1;}finally{if(browser)await browser.close();if(journalFD!==undefined)fs.closeSync(journalFD);}})();
'''


def node_run(payload,timeout):
    policy=operational_guard()['capacity'] if payload.get('action')=='smoke' else None
    with browser_environment(policy) as env:
        process=subprocess.Popen([str(NODE),'-e',RUNNER],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,env=env)
        deadline=time.monotonic()+timeout;initial=True
        try:
            while True:
                if policy and capacity_errors(observation(),policy):raise ValueError('browser_capacity')
                remaining=deadline-time.monotonic()
                if remaining<=0:raise ValueError('browser_timeout')
                try:
                    out,err=process.communicate(json.dumps(payload) if initial else None,timeout=min(.05,remaining));break
                except subprocess.TimeoutExpired:initial=False
        except BaseException:
            os.killpg(process.pid,signal.SIGKILL);process.communicate();raise
        if len(out)>65536:raise ValueError('browser_output_bound')
        result=json.loads(out)
        if process.returncode or not result.get('ok',True):raise BrowserFailure(result)
        return result


def listener_guard(manifest_hash,state_hash):
    import workshop_owned_article_forwarder as f
    receipt,_=f.read_private(f.PRIVATE/'forwarder-process.json')
    if receipt['manifest_sha256']!=manifest_hash or receipt['state_sha256']!=state_hash or receipt['script_sha256']!=hashlib.sha256(Path(f.__file__).read_bytes()).hexdigest():raise ValueError('forwarder_receipt')
    proc=Path('/proc')/str(receipt['pid'])
    if proc.stat().st_uid!=os.getuid() or (proc/'stat').read_text().split()[21]!=receipt['process_start'] or hashlib.sha256((proc/'exe').read_bytes()).hexdigest()!=receipt['executable_sha256']:raise ValueError('forwarder_process')
    owned={os.readlink(fd)[8:-1] for fd in (proc/'fd').iterdir() if os.readlink(fd).startswith('socket:[')}
    listeners=[line.split() for line in Path('/proc/net/tcp').read_text().splitlines()[1:] if line.split()[3]=='0A' and line.split()[1].endswith(':0BE2')]
    if len(listeners)!=1 or listeners[0][1]!='0100007F:0BE2' or listeners[0][9] not in owned:raise ValueError('listener_identity')
    return receipt


ATTEMPT_NAME='browser-attempt-image-contract-v2.started.json'
OUTPUT_NAME='browser-image-contract-v2'
FAILURE_NAME='browser-failure-image-contract-v2.json'
SUCCESS_NAME='browser-acceptance-image-contract-v2.json'
JOURNAL_NAME='browser-events-image-contract-v2.jsonl'


def reserve_attempt(private,manifest_hash,state_hash):
    # One-use reservation precedes process launch; every earlier attempt is kept.
    for name in (OUTPUT_NAME,FAILURE_NAME,SUCCESS_NAME,JOURNAL_NAME):
        if os.path.lexists(private/name):raise FileExistsError('attempt_output_exists')
    fd=os.open(private/ATTEMPT_NAME,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump({'operation':'one_browser_dispatch_reserved','manifest_sha256':manifest_hash,'accepted_sha256':state_hash},stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    directory=os.open(private,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(directory)
    finally:os.close(directory)
    output=private/OUTPUT_NAME;output.mkdir(mode=0o700,exist_ok=False)
    return output


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--probe',action='store_true');args=parser.parse_args()
    try:
        if args.probe:raise ValueError('probe_not_authorized')
        seal=operational_guard();f,s=runtime_modules();pins=dependencies()
        if pins!=seal['dependency_pins']:raise ValueError('dependency_seal')
        if args.probe:
            result=node_run({'action':'probe'},25);result['dependency_pins']=pins
        else:
            check,mh,sh=f.make_checker();binding=check();listener_guard(mh,sh)
            seed,_=f.read_private(f.PRIVATE/'owned-seed.json')
            if seed.get('manifest_sha256')!=mh or seed.get('accepted_sha256')!=sh or seed.get('fixture_sha256')!=hashlib.sha256((s.FIXTURES/'article.json').read_bytes()).hexdigest() or not seed.get('commerce_zero') or seed.get('object_count')!=2:raise ValueError('seed_receipt')
            output=reserve_attempt(f.PRIVATE,mh,sh)
            result=node_run({'action':'smoke','fixture':s.load_fixture(),'output':str(output),'journal':str(f.PRIVATE/JOURNAL_NAME)},120)
            if operational_guard()!=seal or check()!=binding or dependencies()!=pins:raise ValueError('browser_binding_changed')
            listener_guard(mh,sh)
            if trace_errors(result['simulated_paths'],result['external_requests'],result['console_errors']) or result['page_errors']:raise ValueError('browser_trace')
            for path in output.iterdir():os.chmod(path,0o600)
            result.update(dependency_pins=pins,manifest_sha256=mh,accepted_sha256=sh,fixture_sha256=seed['fixture_sha256'],auth_simulation_only=True,operational_seal_sha256=hashlib.sha256(OPERATIONAL_SEAL.read_bytes()).hexdigest(),journal_sha256=hashlib.sha256((f.PRIVATE/JOURNAL_NAME).read_bytes()).hexdigest())
            path=f.PRIVATE/SUCCESS_NAME;fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as stream:json.dump(result,stream,sort_keys=True);stream.write('\n')
        print(json.dumps(result,sort_keys=True));return 0
    except BrowserFailure as error:
        if not args.probe:write_failure_receipt(f.PRIVATE/FAILURE_NAME,error.receipt)
        print(json.dumps(error.receipt,sort_keys=True));return 1
    except Exception:
        print(json.dumps({'ok':False,'error':'owned_browser_failed_preserve_state'}));return 1
if __name__=='__main__':raise SystemExit(main())
