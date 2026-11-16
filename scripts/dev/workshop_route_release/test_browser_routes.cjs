'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {requestDecision,installRoutes}=require('./browser_contract.cjs');
const origin='https://autodata.cars.tk';
test('unknown same-origin paths and non-GET static reads are rejected',()=>{
 for(const [method,path] of [['GET','/v1'],['GET','/auth'],['GET','/supplier'],['GET','/workshop/app.mjs?cache=1'],['GET','/workshop/app.mjs/'],['HEAD','/workshop/app.mjs'],['GET','/workshop/unknown.mjs'],['GET','/cdn-cgi/rum']])
  assert.match(requestDecision(method,origin+path,origin),/^deny/);
});
async function fixture(){
 let handler;
 const context={route:async(pattern,callback)=>{assert.equal(pattern,'**/*');handler=callback;}};
 const controller=await installRoutes(context,origin+'/workshop');
 const dispatches=[],fulfillments=[],aborts=[];
 async function request(method,path){
  const url=path.startsWith('https://')?path:origin+path;
  await handler({request:()=>({method:()=>method,url:()=>url}),
   continue:async()=>dispatches.push({method,url}),
   fulfill:async(response)=>fulfillments.push({method,url,response}),
   abort:async()=>aborts.push({method,url})});
 }
 return {controller,dispatches,fulfillments,aborts,request};
}
test('years GET and CF RUM POST are fulfilled locally with zero dispatch',async()=>{
 const f=await fixture();
 await f.request('GET','/v1/catalog/years');await f.request('POST','/cdn-cgi/rum');
 assert.deepEqual(f.dispatches,[]);assert.deepEqual(f.aborts,[]);
 assert.deepEqual(f.fulfillments.map(x=>x.response.status),[200,204]);
 assert.deepEqual(JSON.parse(f.fulfillments[0].response.body),{items:[],complete:true,hydrating:false});
 for(const record of [...f.controller.state.suppressedCatalogPrefetch,...f.controller.state.suppressedEdgeTelemetry]){
  assert.equal(record.syntheticBrowserResponse,true);assert.equal(record.networkDispatched,false);
 }
});
test('controlled auth GETs and known assets dispatch; protected and external requests do not',async()=>{
 const f=await fixture();f.controller.releaseConfig();
 for(const path of ['/auth/config','/auth/session','/workshop','/workshop/styles.css','/workshop/fonts/InstrumentSans.ttf'])await f.request('GET',path);
 assert.equal(f.dispatches.length,5);
 for(const [method,path] of [['POST','/auth/session'],['GET','/v1/workshop/quote'],['POST','/v1/workshop/prepare'],['GET','/v1/catalog/years?x=1'],['POST','/cdn-cgi/rum?x=1'],['POST','/cdn-cgi/rum/'],['GET','https://accounts.google.com/'],['GET','https://checkout.stripe.com/'],['GET','/unknown']])await f.request(method,path);
 assert.equal(f.dispatches.length,5);assert.equal(f.aborts.length,9);assert.equal(f.controller.state.blockedRequests.length,9);
});
