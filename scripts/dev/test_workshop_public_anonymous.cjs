'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {decision,validateResponse,safeConsole,observeResponse}=require('./workshop_public_anonymous.cjs');
const base='https://autodata.cars.tk';
test('only exact static/auth reads and local synthetic exceptions',()=>{
 assert.equal(decision('GET',base+'/auth/config'),'real');assert.equal(decision('GET',base+'/workshop'),'real');assert.equal(decision('GET',base+'/v1/catalog/years'),'years');assert.equal(decision('POST',base+'/cdn-cgi/rum'),'rum');
 for(const [method,path] of [['POST','/auth/firebase/session'],['GET','/v1/catalog/articles/x'],['GET','/workshop/quote'],['POST','/workshop/checkout'],['GET','/auth/config?x=1'],['GET','/workshop/app.mjs?v=1'],['GET','/workshop/index.html'],['GET','/auth/config#x']])assert.equal(decision(method,base+path),'deny');
 for(const url of ['https://google.com/auth/config','http://autodata.cars.tk/auth/config','https://x:pass@autodata.cars.tk/auth/config','https://autodata.cars.tk.evil/auth/config'])assert.equal(decision('GET',url),'deny');
});
test('real auth/config/session and asset response assertions',()=>{
 const crypto=require('node:crypto'),raw=Buffer.from('exact'),manifest={assets:{'app.mjs':{bytes:raw.length,sha256:crypto.createHash('sha256').update(raw).digest('hex')}}};
 assert.equal(validateResponse('/workshop/app.mjs',200,raw,manifest),true);assert.equal(validateResponse('/workshop/app.mjs',200,Buffer.from('other'),manifest),false);assert.equal(validateResponse('/workshop/app.mjs',302,raw,manifest),false);
 assert.equal(validateResponse('/auth/session',401,Buffer.from('{"error":"unauthenticated"}'),manifest),true);assert.equal(validateResponse('/auth/session',200,raw,manifest),false);
 const config={version:'v1',mode:'firebase',login_available:true,providers:['google.com'],firebase:{apiKey:'public',authDomain:'example.firebaseapp.com',projectId:'example',appId:'1:123:web:abc'}};
 assert.equal(validateResponse('/auth/config',200,Buffer.from(JSON.stringify(config)),manifest),true);config.mode='local';assert.equal(validateResponse('/auth/config',200,Buffer.from(JSON.stringify(config)),manifest),false);
});
test('safe console classification never contains raw JS message',()=>{
 assert.equal(safeConsole('Failed to load resource: the server responded with a status of 401 ()',base+'/auth/session'),'expected_anonymous401');
 assert.equal(safeConsole('secret response text',base+'/workshop/app.mjs'),'unexpected_console_error');assert.equal(safeConsole('status of 401',base+'/other'),'unexpected_console_error');
});

test('anonymous401 console exception is exact-origin and query-free',()=>{assert.equal(safeConsole('status of 401','https://evil.example/auth/session'),'unexpected_console_error');assert.equal(safeConsole('status of 401',base+'/auth/session?x=1'),'unexpected_console_error');});

test('failure preserves safe category/status before body read or assertion',async()=>{const events=[];const response={url:()=>base+'/auth/config',status:()=>403,allHeaders:async()=>({}),body:async()=>Buffer.from('protected error body')};await assert.rejects(observeResponse(response,{},(code,fields)=>events.push({code,...fields})));assert.deepEqual(events[0],{code:'response_status',category:'auth_config',status:403});assert.equal(JSON.stringify(events).includes('protected error body'),false);const broken={...response,body:async()=>{throw Error('do not expose');}};const second=[];await assert.rejects(observeResponse(broken,{},(code,fields)=>second.push({code,...fields})));assert.equal(second[0].status,403);});
