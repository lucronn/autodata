'use strict';
const fs=require('fs'),assert=require('assert/strict');
const {installRoutes,observeSignIn}=require('./browser_contract.cjs');
const ORIGIN='http://127.0.0.1:18432',CDP='http://127.0.0.1:18433';
const syntheticConfig={version:'v1',mode:'firebase',login_available:true,providers:['google.com'],firebase:{apiKey:'synthetic-only',authDomain:'fixture-project.firebaseapp.com',projectId:'fixture-project',appId:'1:123456:web:abcdef'}};
const SDK=`export const inMemoryPersistence={},browserPopupRedirectResolver={};export const initializeApp=()=>({});export const initializeAuth=()=>({});export class GoogleAuthProvider{};export const setPersistence=()=>Promise.resolve();export const signOut=()=>Promise.resolve();export const signInWithPopup=()=>{globalThis.__syntheticSignInCalls=(globalThis.__syntheticSignInCalls||0)+1;return Promise.reject(Object.assign(new Error('Synthetic cancellation'),{code:'auth/popup-closed-by-user'}));};`;
async function fulfillAllowed(route,url){
 const json=(status,body)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 if(url.pathname==='/auth/config'){await json(200,syntheticConfig);return true;}
 if(url.pathname==='/auth/session'){await json(401,{error:{code:'AUTH_REQUIRED'}});return true;}
 if(url.pathname==='/workshop/firebase-web.mjs'){await route.fulfill({status:200,contentType:'text/javascript',body:SDK});return true;}
 return false;
}
async function routeStateAcceptance(page){
 const configuration='11111111-1111-4111-8111-111111111111';
 const cases=[
  {name:'direct route clears prior query',query:'?configuration='+configuration+'&region=US',search:''},
  {name:'direct route restores decoded query',query:'?configuration='+configuration+'&region=US&q=brake+pads',search:'brake pads'},
  {name:'library history clears prior context',query:'?view=library',search:''},
  {name:'order history clears prior context',query:'?order=22222222-2222-4222-8222-222222222222',search:''},
 ];
 const results=[];
 for(const item of cases){
  await page.evaluate(({query})=>{
   for(const name of ['year','make','model','configuration']){
    const node=document.getElementById(name);node.replaceChildren(new Option('Prior vehicle','prior'));node.value='prior';node.disabled=false;
   }
   document.getElementById('search').value='old vehicle only';
   history.pushState(null,'','/workshop/'+query);dispatchEvent(new PopStateEvent('popstate'));
  },item);
  await page.waitForFunction(expected=>document.getElementById('search').value===expected&&['year','make','model','configuration'].every(name=>{const s=document.getElementById(name);return s.value===''&&s.disabled&&s.options.length===1}),item.search,{timeout:5000});
  const observed=await page.evaluate(()=>({search:document.getElementById('search').value,selectors:['year','make','model','configuration'].map(name=>({name,value:document.getElementById(name).value,disabled:document.getElementById(name).disabled,options:document.getElementById(name).options.length})),purchaseActionDisabled:document.getElementById('purchase-action').disabled}));
  assert.equal(observed.search,item.search);assert(observed.selectors.every(s=>s.value===''&&s.disabled&&s.options===1));
  results.push({...item,...observed,syntheticHistoryOnly:true,authenticatedArticleProven:false});
 }
 await page.locator('#browse').click();
 await page.waitForFunction(()=>location.search===''&&document.getElementById('search').value===''&&document.getElementById('year').disabled,null,{timeout:5000});
 return {passed:true,cases:results,browseRestored:true,libraryActivation:'exact protected-source Node harness; anonymous browser cannot authenticate'};
}
async function run(){
 assert.deepEqual(process.argv.slice(2),['--reviewed-local-only']);
 const {chromium}=require('/home/corp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
 const browser=await chromium.connectOverCDP(CDP,{timeout:10000});const results=[];
 try{
  for(const viewport of [{width:390,height:844},{width:1440,height:900}]){
   const context=await browser.newContext({viewport,deviceScaleFactor:1,serviceWorkers:'block'});
   const controller=await installRoutes(context,ORIGIN,{fulfillAllowed});const page=await context.newPage();const errors=[];
   page.on('pageerror',e=>errors.push(e.name));
   try{
    const initial=await observeSignIn(page,ORIGIN+'/workshop/',controller);
    await controller.waitForCatalogSuppression();
    await page.waitForLoadState('domcontentloaded',{timeout:10000});
    const before=await page.evaluate(()=>({signInEnabled:!document.querySelector('#signin').disabled,horizontalOverflow:document.documentElement.scrollWidth>innerWidth+1,purchaseHidden:document.querySelector('#purchase').hidden||getComputedStyle(document.querySelector('#purchase')).display==='none',criticalError:document.querySelector('#critical-error').textContent.trim(),yearDisabled:document.querySelector('#year').disabled,yearOptionCount:document.querySelector('#year').options.length}));
    assert.equal(initial.htmlStatus,200);assert(initial.initialDisabled&&initial.configGateVerified);
    assert(before.signInEnabled&&!before.horizontalOverflow&&before.purchaseHidden&&!before.criticalError&&before.yearDisabled&&before.yearOptionCount<=1);
    await page.locator('#signin').click();
    await page.waitForFunction(()=>globalThis.__syntheticSignInCalls===1&&!document.querySelector('#signin').disabled,null,{timeout:5000});
    assert.match(await page.locator('#account-status').innerText(),/cancel|try again/i);
    assert.deepEqual(errors,[]);assert.deepEqual(controller.state.blockedRequests,[]);
    const routeState=await routeStateAcceptance(page);
    assert.deepEqual(controller.state.blockedRequests,[]);
    const baseline=JSON.parse(JSON.stringify(controller.state));
    const telemetry=await page.evaluate(async()=>{const r=await fetch('/cdn-cgi/rum',{method:'POST',body:'synthetic metrics'});return r.status;});assert.equal(telemetry,204);
    await page.evaluate(async()=>{for(const [path,method]of [['/auth/session','POST'],['/v1/workshop/quote','GET'],['/v1/workshop/prepare','POST'],['/v1/catalog/years?x=1','GET'],['/cdn-cgi/rum?x=1','POST'],['/cdn-cgi/rum/','POST'],['/cdn-cgi/rum','PUT'],['https://accounts.google.com/','GET'],['https://checkout.stripe.com/','GET']])await fetch(path,{method}).catch(()=>{});});
    assert.equal(controller.state.blockedRequests.length,9);assert.equal(controller.state.suppressedEdgeTelemetry.length,1);
    await page.screenshot({path:__dirname+'/viewport-'+viewport.width+'.png',fullPage:true});
    results.push({viewport,...initial,...before,syntheticSignInCalls:1,routeState,pageErrors:errors,successfulPageState:baseline,negativePolicyProof:{expectedBlockedRequests:9,actualBlockedRequests:controller.state.blockedRequests,telemetryStatus:telemetry,telemetry:controller.state.suppressedEdgeTelemetry}});
   }finally{controller.releaseConfig();await context.close();}
  }
 }finally{await browser.close();}
 const receipt={status:'SYNTHETIC_LOCAL_BROWSER_PASS',passed:true,results,sourceSHA:'09524db599a82e7f8c79a1d8fb43bfadc6bbe2f3',exactBinaryAssetsVerifiedByRunner:true,syntheticOverrides:['auth/config','auth/session','firebase-web.mjs SDK stub','anonymous exact years GET','exact RUM POST'],publicRequests:0,providerRequests:0,realFirebaseAuthentication:false,realSupplierCatalog:false,authenticatedArticleAcceptance:false,introAcceptance:'separate synthetic Node client tests only'};
 fs.writeFileSync(__dirname+'/BROWSER-RESULT.json',JSON.stringify(receipt,null,2)+'\n',{mode:0o600,flag:'wx'});console.log(JSON.stringify({passed:true,viewports:results.length}));
}
module.exports={fulfillAllowed,SDK,syntheticConfig,routeStateAcceptance};
if(require.main===module)run().catch(e=>{console.error(JSON.stringify({failed:true,type:e.name,message:e.message}));process.exitCode=1;});
