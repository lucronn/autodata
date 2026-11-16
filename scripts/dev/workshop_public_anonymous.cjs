'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const ORIGIN='https://autodata.cars.tk';
const ASSETS=new Set(['app.mjs','article-read.mjs','auth.mjs','bootstrap.mjs','catalog.mjs','commerce.mjs','demo.mjs','firebase-web.mjs','firebase-web.mjs.LEGAL.txt','firebase-web.provenance.json','fonts/InstrumentSans.ttf','fonts/OFL.txt','index.html','progress.mjs','styles.css']);
function decision(method,value){
 let u;try{u=new URL(value);}catch{return 'deny';}
 if(u.origin!==ORIGIN||u.username||u.password||u.hash||u.search)return 'deny';
 if(method==='POST'&&u.pathname==='/cdn-cgi/rum')return 'rum';
 if(method!=='GET')return 'deny';
 if(u.pathname==='/v1/catalog/years')return 'years';
 if(['/workshop','/workshop/purchase-config.json','/workshop/demo-mode.json','/auth/config','/auth/session'].includes(u.pathname))return 'real';
 return u.pathname.startsWith('/workshop/')&&ASSETS.has(u.pathname.slice(10))&&u.pathname!=='/workshop/index.html'?'real':'deny';
}
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
function durable(root,name,value){const fd=fs.openSync(path.join(root,name),'wx',0o600);try{fs.writeSync(fd,JSON.stringify(value)+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}const dir=fs.openSync(root,'r');fs.fsyncSync(dir);fs.closeSync(dir);}
async function screenshot(page,root,name){const target=path.join(root,name);await page.screenshot({path:target,fullPage:true,timeout:5000});fs.chmodSync(target,0o600);const fd=fs.openSync(target,'r');fs.fsyncSync(fd);fs.closeSync(fd);}
function validateResponse(p,status,body,m){
 if(body.length>1048576)return false;
 if(p==='/auth/session'){try{return status===401&&JSON.parse(body)?.error!==undefined&&JSON.parse(body)?.authenticated!==true;}catch{return false;}}
 if(status!==200)return false;
 if(p==='/workshop'||(p.startsWith('/workshop/')&&ASSETS.has(p.slice(10)))){const name=p==='/workshop'?'index.html':p.slice(10),v=m.assets[name];return Boolean(v&&body.length===v.bytes&&hash(body)===v.sha256);}
 let v;try{v=JSON.parse(body);}catch{return false;}
 if(p==='/auth/config')return v.version==='v1'&&v.mode==='firebase'&&v.login_available===true&&Array.isArray(v.providers)&&v.providers.includes('google.com')&&['apiKey','authDomain','projectId','appId'].every(k=>typeof v.firebase?.[k]==='string'&&v.firebase[k].length>0);
 if(p==='/workshop/demo-mode.json')return v.enabled===false&&Object.keys(v).length===1;
 if(p==='/workshop/purchase-config.json')return v.enabled===false&&v.terms_version==='workshop-v1'&&['terms_url','privacy_url','refund_url','contact_url','tax_notice'].every(k=>v[k]===null)&&Object.keys(v).length===7;
 return false;
}
async function observeResponse(response,m,record){
 const p=new URL(response.url()).pathname,status=response.status(),category=p==='/auth/config'?'auth_config':p==='/auth/session'?'auth_session':p.includes('purchase-config')?'purchase':p.includes('demo-mode')?'demo':'asset';
 record('response_status',{category,status});const headers=await response.allHeaders();
 if(Number(headers['content-length']||0)>1048576)throw Error('response_body_bound');
 const body=await response.body();if(!validateResponse(p,status,body,m)){record('response_rejected',{category,status,bytes:body.length});throw Error('response_contract');}
 const result={category,status,bytes:body.length};if(category==='asset')result.sha256=hash(body);
 if(p==='/workshop'){const csp=headers['content-security-policy']||'';result.cspHeaderPresent=Boolean(csp);result.cspHeaderSha256=csp?hash(Buffer.from(csp)):null;}
 record('response_verified',result);return {...result,path:p};
}
function safeConsole(message,url){let u;try{u=new URL(url);}catch{}return u?.origin===ORIGIN&&u.pathname==='/auth/session'&&!u.search&&/status of 401\b/.test(message)?'expected_anonymous401':'unexpected_console_error';}
async function run(){
 if(process.argv[2]!=='--run-reviewed')throw Error('dispatch_not_reviewed');
 const root=__dirname,m=JSON.parse(fs.readFileSync(path.join(root,'manifest.json')));if(process.ppid!==Number(process.env.AUTODATA_ANON_SUPERVISOR_PID)||hash(fs.readFileSync(path.join(root,'PACKAGE-SEAL.json')))!==process.env.AUTODATA_ANON_REVIEWED_SEAL||fs.readFileSync(path.join(root,'browser-attempted'),'utf8')!==process.env.AUTODATA_ANON_REVIEWED_SEAL+'\n'||!process.env.HOME?.startsWith('/tmp/ad-pa-')||process.env.HOME!==process.env.TMPDIR||!fs.readFileSync('/proc/'+process.ppid+'/cmdline','utf8').includes(path.join(root,'workshop_public_anonymous.py')))throw Error('supervisor_fence');const journal=fs.openSync(path.join(root,'BROWSER-JOURNAL.jsonl'),'wx',0o600);let stage='launch',events=0;const errors=[],results=[];let browser,currentPage;
 const record=(code,extra={})=>{if(++events>256)throw Error('journal_bound');fs.writeSync(journal,JSON.stringify({stage,code,...extra})+'\n');fs.fsyncSync(journal);};
 const check=(ok,code)=>{if(!ok){record(code);throw Error(code);}};
 try{
  const {chromium}=require(m.playwright);
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,chromiumSandbox:true,proxy:{server:'http://127.0.0.1:18434',bypass:'<-loopback>'},args:['--disable-background-networking','--disable-component-update','--disable-domain-reliability','--disable-sync','--disable-extensions','--no-first-run','--disable-client-side-phishing-detection','--metrics-recording-only','--disable-crash-reporter','--disable-breakpad','--disk-cache-size=1048576','--media-cache-size=1048576','--host-resolver-rules=MAP * ~NOTFOUND'],timeout:20000});
  for(const viewport of [{width:1440,height:900},{width:390,height:844}]){
   stage='viewport-'+viewport.width;record('context_start');const startErrors=errors.length,context=await browser.newContext({viewport,serviceWorkers:'block',acceptDownloads:false});const state={real:0,years:0,rum:0,denied:0,config:0,session:0,assets:new Set(),expected401:0,csp:0,cspHeaderPresent:false,cspHeaderSha256:null,pageErrors:0};const pending=new Set();let release,heldResolve;const barrier=new Promise(r=>{release=r;}),held=new Promise(r=>{heldResolve=r;});let released=false;
   await context.exposeBinding('__publicCsp',(_,directive)=>{state.csp++;errors.push('csp_violation');record('csp_violation',{category:['script-src','script-src-elem','style-src','style-src-elem','connect-src','font-src','img-src','frame-src'].includes(directive)?directive:'other'});});
   await context.addInitScript(()=>document.addEventListener('securitypolicyviolation',e=>void window.__publicCsp(e.effectiveDirective)));
   await context.routeWebSocket('**/*',ws=>{errors.push('websocket_denied');record('websocket_denied');ws.close();});
   await context.route('**/*',async route=>{
    const req=route.request(),d=decision(req.method(),req.url());
    if(d==='years'){state.years++;record('synthetic_years',{status:200,networkDispatched:false});return route.fulfill({status:200,contentType:'application/json',body:'{"items":[],"complete":true,"hydrating":false}'});}
    if(d==='rum'){state.rum++;record('synthetic_rum',{status:204,networkDispatched:false});return route.fulfill({status:204,body:''});}
    if(d!=='real'){state.denied++;errors.push('route_denied');record('route_denied',{category:new URL(req.url()).origin===ORIGIN?'protected_or_unknown':'external'});return route.abort();}
    const headers=await req.allHeaders();if(['authorization','cookie','x-csrf-token'].some(k=>headers[k])){state.denied++;errors.push('credential_header');record('credential_header');return route.abort();}
    if(new URL(req.url()).pathname==='/auth/config'&&!released){heldResolve();await Promise.race([barrier,new Promise((_,reject)=>setTimeout(()=>reject(Error('config_hold_deadline')),5000))]);}
    state.real++;return route.continue();
   });
   const page=await context.newPage();currentPage=page;
   context.on('page',p=>{if(p!==page){errors.push('popup_denied');void p.close();}});
   page.on('download',d=>{errors.push('download_denied');void d.cancel();});
   page.on('pageerror',()=>{state.pageErrors++;errors.push('page_error');record('page_error');});
   page.on('console',msg=>{if(msg.type()==='error'){const code=safeConsole(msg.text(),msg.location().url);if(code==='expected_anonymous401')state.expected401++;else errors.push(code);record(code);}});
   page.on('requestfailed',req=>{if(decision(req.method(),req.url())==='real'){errors.push('real_resource_failed');record('real_resource_failed');}});
   page.on('response',response=>{
    if(response.request().method()!=='GET'||decision('GET',response.url())!=='real')return;
    const work=(async()=>{const seen=await observeResponse(response,m,record);if(seen.category==='auth_config')state.config++;if(seen.category==='auth_session')state.session++;if(seen.category==='asset')state.assets.add(seen.path==='/workshop'?'index.html':seen.path.slice(10));if(seen.path==='/workshop'){state.cspHeaderPresent=seen.cspHeaderPresent;state.cspHeaderSha256=seen.cspHeaderSha256;}})();pending.add(work);work.catch(()=>{errors.push('response_contract');}).finally(()=>pending.delete(work));
   });
   try{
    stage='navigate-'+viewport.width;const response=await page.goto(ORIGIN+'/workshop',{waitUntil:'commit',timeout:20000});check(response?.status()===200,'navigation_status');const signin=page.locator('#signin');await signin.waitFor({state:'attached',timeout:5000});await Promise.race([held,new Promise((_,reject)=>setTimeout(()=>reject(Error('config_not_held')),5000))]);check(await signin.isDisabled(),'initial_signin_not_disabled');released=true;release();await page.waitForFunction(()=>{const b=document.querySelector('#signin');return b&&!b.disabled;},null,{timeout:20000});
    stage='layout-'+viewport.width;await page.waitForFunction(()=>{const e=document.querySelector('#year');return e&&e.disabled&&e.options.length===1&&document.querySelector('#purchase')?.hidden===true;},null,{timeout:10000});await page.evaluate(()=>document.fonts.ready);await Promise.allSettled([...pending]);
    check((await page.locator('#critical-error').innerText()).trim()==='','critical_error');check(await page.locator('#purchase').isHidden(),'purchase_visible');check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'horizontal_overflow');check(await page.locator('#signin').isVisible(),'signin_not_visible');check(state.config>0&&state.session>0&&state.years>0,'bootstrap_observation_missing');check(['index.html','app.mjs','auth.mjs','catalog.mjs','firebase-web.mjs','styles.css'].every(x=>state.assets.has(x)),'essential_asset_missing');check(await page.evaluate(()=>['#signin','#page-title','#year'].every(s=>{const e=document.querySelector(s),r=e?.getBoundingClientRect();return r&&r.width>0&&r.left>=-1&&r.right<=innerWidth+1;})),'control_clipping');check(errors.length===startErrors,'page_diagnostics');
    await screenshot(page,root,'viewport-'+viewport.width+'.png');record('viewport_pass',{width:viewport.width,real:state.real,syntheticYears:state.years,syntheticRum:state.rum,assetCount:state.assets.size});results.push({viewport,...state,assets:[...state.assets].sort(),passed:true});
   }catch(e){await screenshot(page,root,'failure-'+viewport.width+'.png').catch(()=>{});throw e;}finally{released=true;release();await Promise.allSettled([...pending]);await context.close();}
   check(errors.length===startErrors,'post_context_diagnostics');
  }
  stage='complete';check(errors.length===0,'final_diagnostics');record('browser_pass');durable(root,'BROWSER-RESULT.json',{passed:true,status:'PUBLIC_ANONYMOUS_UI_PASS',viewports:results,errors:[],signinClicked:false,syntheticAuth:false,syntheticYears:true,publicStaticAndAuthReal:true,providerRequestsDispatched:0,writeRequestsDispatched:0});
 }catch(e){
  record('browser_failed',{errorCount:errors.length});if(currentPage&&!currentPage.isClosed())await screenshot(currentPage,root,'failure.png').catch(()=>{});durable(root,'BROWSER-RESULT.json',{passed:false,status:'PUBLIC_ANONYMOUS_UI_FAILED',stage,errors:errors.slice(0,64),signinClicked:false});process.exitCode=1;
 }finally{if(browser)await browser.close().catch(()=>{});fs.fsyncSync(journal);fs.closeSync(journal);}
}
module.exports={decision,validateResponse,safeConsole,observeResponse};
if(require.main===module)run().catch(()=>{process.stdout.write('{"passed":false,"code":"browser_top_level_failure"}\n');process.exitCode=1;});
