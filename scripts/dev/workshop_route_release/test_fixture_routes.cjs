const {test}=require('node:test'),a=require('assert/strict');
const {installRoutes,WORKSHOP_ASSETS,requestDecision}=require('./browser_contract.cjs');
const {fulfillAllowed}=require('./browser_fixture.cjs');const origin='http://127.0.0.1:18432';
test('all15 exact binary asset paths permitted; alternate loopback port denied',()=>{a.equal(WORKSHOP_ASSETS.length,15);for(const name of WORKSHOP_ASSETS)a.equal(requestDecision('GET',origin+'/workshop/'+name,origin),'allow');a.equal(requestDecision('GET','http://127.0.0.1:18433/workshop',origin),'deny_external');});
test('fixture auth/SDK is browser-local after config gate; all other protected paths deny',async()=>{
 let handler;const sent=[],fulfilled=[],aborted=[];const context={route:async(_,fn)=>handler=fn};const c=await installRoutes(context,origin,{fulfillAllowed});
 async function req(method,path){await handler({request:()=>({method:()=>method,url:()=>origin+path}),continue:async()=>sent.push(path),fulfill:async x=>fulfilled.push({path,...x}),abort:async()=>aborted.push(path)});}
 const pending=req('GET','/auth/config');await c.waitForConfigHeld();a.equal(fulfilled.length,0);a.equal(sent.length,0);c.releaseConfig();await pending;
 for(const p of ['/auth/session','/workshop/firebase-web.mjs','/v1/catalog/years'])await req('GET',p);await req('POST','/cdn-cgi/rum');a.equal(sent.length,0);a.equal(fulfilled.length,5);
 for(const [m,p]of [['POST','/auth/firebase/session'],['GET','/v1/catalog/years/2024/makes'],['GET','/v1/workshop/quote'],['GET','/workshop/firebase-web.mjs?x=1']])await req(m,p);
 a.equal(aborted.length,4);a.equal(sent.length,0);a.deepEqual(fulfilled.map(x=>x.status),[200,401,200,200,204]);
});
