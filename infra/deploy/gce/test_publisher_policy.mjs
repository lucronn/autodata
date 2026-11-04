import test from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPairSync, createHash, sign} from 'node:crypto';
import {parseStrictJsonBytes, verifyOwnerPolicyBytes, OwnedTrustReadScope, loadInstalledOwnerPolicy, installedPolicyClaims} from './publisher_policy.mjs';

const hash = b => createHash('sha256').update(b).digest('hex');
const bytes = v => Buffer.from(JSON.stringify(v));
const now = 1800000000;
const owner = generateKeyPairSync('ed25519');
const rsa = generateKeyPairSync('rsa', {modulusLength:2048});
const rawOwner = owner.publicKey.export({format:'der',type:'spki'}).subarray(-32);
const keyId = hash(rawOwner);
const publicRsa = rsa.publicKey.export({format:'jwk'});
function fixture(overrides={}, options={}) {
  const jwks = options.jwks ?? bytes({keys:[{kty:'RSA',kid:'fixture-key',use:'sig',alg:'RS256',n:publicRsa.n,e:publicRsa.e}]});
  const policy = {protocol_version:1,purpose:'autodata.publisher.stage1a.offline',epoch:2,issued_at:now-60,expires_at:now+600,repository:'lucronn/autodata',repository_id:'123',repository_owner_id:'456',environment:'staging',protected_environment:'workshop-staging-publish',workflow_ref:'lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master',workflow_sha:'a'.repeat(40),ref:'refs/heads/master',event_name:'workflow_dispatch',upload_enabled:false,runtime_bearer_authentication:'unsupported',oidc:{issuer:'https://token.actions.githubusercontent.com',audience:'urn:autodata:publisher:stage1a:offline',subject:'repo:lucronn/autodata:environment:workshop-staging-publish',jwks_sha256:hash(jwks),jwks_issued_at:now-100,jwks_expires_at:now+1000},...overrides};
  const payload = options.payload ?? bytes(policy);
  const signature = sign(null,Buffer.concat([Buffer.from(options.domain ?? 'AutoData-Publisher-Owner-Policy-v1\0'),payload]),owner.privateKey);
  const envelope = options.envelope ?? bytes({protocol_version:1,key_id:keyId,payload:payload.toString('base64'),signature:signature.toString('base64')});
  const bootstrap = bytes({protocol_version:1,purpose:'autodata.publisher.bootstrap.v1',key_id:keyId,owner_public_key:rawOwner.toString('base64'),policy_sha256:hash(envelope),minimum_epoch:1,...options.bootstrap});
  return {bootstrap,envelope,jwks,policy};
}
function verify(f, clock=now) {return verifyOwnerPolicyBytes(f.bootstrap,f.envelope,f.jwks,clock);}
const invalid = fn => assert.throws(fn,{message:'invalid_trust_input'});
const delay = ms => new Promise(r=>setTimeout(r,ms));

test('strict JSON accepts neutral objects and rejects ambiguous byte representations',()=>{
  const parsed = parseStrictJsonBytes(Buffer.from('{"a":[1,true,null,"é"]}'),{maxBytes:1024});
  assert.equal(Object.getPrototypeOf(parsed),null);
  assert.equal(parsed.a[3],'é');
  for(const input of ['{"a":1,"a":2}','{"a":1,"\\u0061":2}','1e2','1.0','-0','9007199254740992','"\\ud800"','"\\udfff"','\ufeff{}','{}x','[1,]']) invalid(()=>parseStrictJsonBytes(Buffer.from(input),{maxBytes:1024}));
  invalid(()=>parseStrictJsonBytes(Buffer.from([0xc0,0xaf]),{maxBytes:1024}));
  invalid(()=>parseStrictJsonBytes('{}',{maxBytes:1024}));
  invalid(()=>parseStrictJsonBytes(Buffer.from('{}'),{maxBytes:1}));
});
test('strict parser enforces depth, key, array and string budgets',()=>{
  for(const input of ['['.repeat(17)+'0'+']'.repeat(17), JSON.stringify(Array(17).fill(0)),JSON.stringify('x'.repeat(8193)),JSON.stringify(Object.fromEntries(Array.from({length:257},(_,i)=>[String(i),i])))]) invalid(()=>parseStrictJsonBytes(Buffer.from(input),{maxBytes:65536}));
});
test('real Ed25519 exact-byte fixture yields only deeply frozen passive trust',()=>{
  const f=fixture(); const result=verify(f);
  assert.deepEqual(Object.keys(result).sort(),['activation_sha256','jwks','policy','trust_bytes']);
  assert.equal(result.activation_sha256,hash(f.envelope));
  assert.equal(result.trust_bytes.bootstrap_base64,f.bootstrap.toString('base64'));
  assert.ok(Object.isFrozen(result.policy.oidc)); assert.ok(Object.isFrozen(result.jwks.keys[0]));
  invalid(()=>installedPolicyClaims(result)); invalid(()=>installedPolicyClaims({}));
  f.bootstrap.fill(0); assert.equal(result.policy.epoch,2);
});
test('policy rejects positive authority, schema, identity, time and epoch deviations',()=>{
  for(const changes of [{upload_enabled:true},{runtime_bearer_authentication:'supported'},{environment:'production'},{protected_environment:'staging'},{repository:'other/repo'},{repository_id:'01'},{repository_owner_id:1},{workflow_sha:'A'.repeat(40)},{ref:'refs/heads/main'},{event_name:'push'},{epoch:0},{epoch:2147483648},{issued_at:now+1},{expires_at:now},{expires_at:now+90000},{issued_at:now-0.5},{unknown:true}]) invalid(()=>verify(fixture(changes)));
  invalid(()=>verify(fixture(),-1)); invalid(()=>verify(fixture(),NaN));
  invalid(()=>verify(fixture({}, {bootstrap:{minimum_epoch:3}})));
  invalid(()=>verify(fixture({oidc:{...fixture().policy.oidc,jwks_expires_at:now+500}})));
});
test('signature domain, exact signed payload and exact envelope digest are bound',()=>{
  invalid(()=>verify(fixture({}, {domain:'other\0'})));
  const f=fixture(); const envelope=JSON.parse(f.envelope); envelope.payload=Buffer.from(JSON.stringify(f.policy,null,1)).toString('base64');
  invalid(()=>verify(fixture({}, {envelope:bytes(envelope)})));
  const changed={...f,envelope:Buffer.concat([f.envelope,Buffer.from(' ')] )}; invalid(()=>verify(changed));
  const sig=JSON.parse(f.envelope); sig.signature=Buffer.alloc(64).toString('base64'); invalid(()=>verify(fixture({}, {envelope:bytes(sig)})));
  const key=Buffer.alloc(32,1); invalid(()=>verify(fixture({}, {bootstrap:{owner_public_key:key.toString('base64'),key_id:hash(key)}})));
});
test('canonical base64 and all raw byte bounds are mandatory',()=>{
  const f=fixture();
  for(const field of ['payload','signature']) {const e=JSON.parse(f.envelope); e[field]+='\n'; invalid(()=>verify(fixture({}, {envelope:bytes(e)})));}
  invalid(()=>verify(fixture({}, {bootstrap:{owner_public_key:rawOwner.toString('base64').replace(/=+$/,'')}})));
  for(const field of ['bootstrap','envelope','jwks']) {invalid(()=>verify({...f,[field]:Buffer.alloc(65537)}));invalid(()=>verify({...f,[field]:'{}'}));}
  invalid(()=>verify(fixture({}, {payload:Buffer.from('{"epoch":2,"epoch":2}')})));
});
test('normalized JWKS rejects private, duplicate, unsorted and weak key metadata',()=>{
  const base={kty:'RSA',kid:'fixture-key',use:'sig',alg:'RS256',n:publicRsa.n,e:publicRsa.e};
  for(const keys of [[],[base,base],[{...base,kid:'z'},{...base,kid:'a'}],[{...base,d:'secret'}],[{...base,alg:'PS256'}],[{...base,e:'Aw'}],[{...base,n:'AA'}],[{...base,n:base.n+'='}],[{...base,kid:'bad kid'}]]) invalid(()=>verify(fixture({}, {jwks:bytes({keys})})));
});
test('owned scope closes handles once and rejects invalid budget/capacity',async()=>{
  for(const options of [{budgetMs:0},{budgetMs:5001},{budgetMs:1.1},{cleanupReserveMs:1001}]) invalid(()=>new OwnedTrustReadScope(options));
  const scope=new OwnedTrustReadScope({budgetMs:100,cleanupReserveMs:20});let closed=0;
  await scope.trackOpen(Promise.resolve({close:async()=>{closed++;}})); await scope.track(Promise.resolve(1)); await scope.finish(); assert.equal(closed,1);
  const full=new OwnedTrustReadScope({budgetMs:10,cleanupReserveMs:10});
  for(let i=0;i<16;i++) full.track(new Promise(()=>{})).catch(()=>{});
  assert.throws(()=>full.check(),{message:'invalid_trust_input'});
  await assert.rejects(full.finish(),{message:'cleanup_failed'});
});
test('never-settling open, read and close have bounded cleanup failure',async()=>{
  for(const kind of ['open','read','close']) {
    const scope=new OwnedTrustReadScope({budgetMs:10,cleanupReserveMs:15});let closeCount=0;
    if(kind==='open') scope.trackOpen(new Promise(()=>{})).catch(()=>{});
    else {await scope.trackOpen(Promise.resolve({close:()=>{closeCount++;return kind==='close'?new Promise(()=>{}):Promise.resolve();}}));if(kind==='read')scope.track(new Promise(()=>{})).catch(()=>{});}
    const start=performance.now();await assert.rejects(scope.finish(),{message:'cleanup_failed'}); assert.ok(performance.now()-start<1000);
    if(kind==='read')assert.equal(closeCount,0);
  }
});
test('late opens close exactly once, late reads drain before close, late rejections are consumed',async()=>{
  let resolveOpen,resolveRead,rejectRead,closed=0;
  const scope=new OwnedTrustReadScope({budgetMs:5,cleanupReserveMs:5});
  scope.trackOpen(new Promise(r=>resolveOpen=r)).catch(()=>{});
  await assert.rejects(scope.finish(),{message:'cleanup_failed'});
  resolveOpen({close:async()=>{closed++;}});await delay(10);assert.equal(closed,1);
  const reading=new OwnedTrustReadScope({budgetMs:5,cleanupReserveMs:5});closed=0;
  await reading.trackOpen(Promise.resolve({close:async()=>{closed++;}}));
  reading.track(new Promise(r=>resolveRead=r)).catch(()=>{});
  await assert.rejects(reading.finish(),{message:'cleanup_failed'});assert.equal(closed,0);
  resolveRead(Buffer.from('discarded'));await delay(10);assert.equal(closed,1);
  const rejected=new OwnedTrustReadScope({budgetMs:5,cleanupReserveMs:5});rejected.track(new Promise((_,r)=>rejectRead=r)).catch(()=>{});
  await assert.rejects(rejected.finish(),{message:'cleanup_failed'});rejectRead(Error('secret'));await delay(10);
});
test('failed close remains failed and is never retried',async()=>{
  let closes=0;const scope=new OwnedTrustReadScope({budgetMs:10,cleanupReserveMs:10});
  await scope.trackOpen(Promise.resolve({close:async()=>{closes++;throw Error('secret');}}));
  await assert.rejects(scope.finish(),{message:'cleanup_failed'});await assert.rejects(scope.finish(),{message:'cleanup_failed'});assert.equal(closes,1);
});
test('cancelled scope cannot succeed and missing fixed installation yields no handle',async()=>{
  const controller=new AbortController();const scope=new OwnedTrustReadScope({signal:controller.signal,budgetMs:100,cleanupReserveMs:10});controller.abort();
  assert.throws(()=>scope.check(),{message:'operation_cancelled'});await assert.rejects(scope.finish(),{message:'operation_cancelled'});
  await assert.rejects(loadInstalledOwnerPolicy(),{message:'missing_dependency'});
});
test('fixed loader refuses injected sources and simultaneous acquisition',async()=>{
  const first=loadInstalledOwnerPolicy();
  await assert.rejects(loadInstalledOwnerPolicy(),{message:'cleanup_failed'});
  await assert.rejects(first,{message:'missing_dependency'});
  await assert.rejects(loadInstalledOwnerPolicy({path:'/tmp/attacker'}),{message:'invalid_trust_input'});
  await assert.rejects(loadInstalledOwnerPolicy({get signal(){throw Error('secret');}}),{message:'invalid_trust_input'});
  invalid(()=>new OwnedTrustReadScope({get budgetMs(){throw Error('secret');}}));
});
test('scope adopts already-started opens even when the verification deadline passes',async()=>{
  let closes=0;const scope=new OwnedTrustReadScope({budgetMs:1,cleanupReserveMs:20});
  await delay(3);
  await assert.rejects(scope.trackOpen(Promise.resolve({close:async()=>{closes++;}})),{message:'operation_timed_out'});
  await assert.rejects(scope.finish(),{message:'operation_timed_out'});assert.equal(closes,1);
});
