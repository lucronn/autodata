import test from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPairSync,createHash,sign,constants} from 'node:crypto';
import {verifyOwnerPolicyBytes} from './publisher_policy.mjs';
import {verifyGithubOidcBytes,verifyInstalledGithubOidc,authenticateActionsRuntime} from './publisher_identity.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
const bytes=value=>Buffer.from(JSON.stringify(value));
const now=1800000000;
const owner=generateKeyPairSync('ed25519');
const rsa2048=generateKeyPairSync('rsa',{modulusLength:2048});
const rsa4096=generateKeyPairSync('rsa',{modulusLength:4096});
const wrongSigner=generateKeyPairSync('rsa',{modulusLength:2048});
const rawOwner=owner.publicKey.export({type:'spki',format:'der'}).subarray(-32);
const context={run_id:'123456789',run_attempt:2};
function fixture(rsa=rsa2048,policyChanges={},jwksChanges) {
  const publicKey=rsa.publicKey.export({format:'jwk'});
  const jwks=bytes(jwksChanges??{keys:[{kty:'RSA',kid:'fixture-key',use:'sig',alg:'RS256',n:publicKey.n,e:publicKey.e}]});
  const policy={protocol_version:1,purpose:'autodata.publisher.stage1a.offline',epoch:2,issued_at:now-60,expires_at:now+600,repository:'lucronn/autodata',repository_id:'123',repository_owner_id:'456',environment:'staging',protected_environment:'workshop-staging-publish',workflow_ref:'lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master',workflow_sha:'a'.repeat(40),ref:'refs/heads/master',event_name:'workflow_dispatch',upload_enabled:false,runtime_bearer_authentication:'unsupported',oidc:{issuer:'https://token.actions.githubusercontent.com',audience:'urn:autodata:publisher:stage1a:offline',subject:'repo:lucronn/autodata:environment:workshop-staging-publish',jwks_sha256:hash(jwks),jwks_issued_at:now-100,jwks_expires_at:now+1000},...policyChanges};
  const payload=bytes(policy),keyId=hash(rawOwner);
  const envelope=bytes({protocol_version:1,key_id:keyId,payload:payload.toString('base64'),signature:sign(null,Buffer.concat([Buffer.from('AutoData-Publisher-Owner-Policy-v1\0'),payload]),owner.privateKey).toString('base64')});
  const bootstrap=bytes({protocol_version:1,purpose:'autodata.publisher.bootstrap.v1',key_id:keyId,owner_public_key:rawOwner.toString('base64'),policy_sha256:hash(envelope),minimum_epoch:1});
  const result=verifyOwnerPolicyBytes(bootstrap,envelope,jwks,now);
  const claims={iss:policy.oidc.issuer,aud:policy.oidc.audience,sub:policy.oidc.subject,exp:now+240,iat:now-60,nbf:now-60,jti:'fixture-token',repository:policy.repository,repository_id:policy.repository_id,repository_owner_id:policy.repository_owner_id,run_id:context.run_id,run_attempt:String(context.run_attempt),workflow_ref:policy.workflow_ref,workflow_sha:policy.workflow_sha,ref:policy.ref,sha:policy.workflow_sha,event_name:policy.event_name,environment:policy.protected_environment};
  function token(changes={},options={}) {
    const header=options.headerRaw??bytes({alg:'RS256',typ:'JWT',kid:'fixture-key',...options.header});
    const payload=options.payloadRaw??bytes({...claims,...changes});
    const input=header.toString('base64url')+'.'+payload.toString('base64url');
    const signature=sign('RSA-SHA256',Buffer.from(input),{key:options.signer??rsa.privateKey,padding:options.padding??constants.RSA_PKCS1_PADDING});
    return Buffer.from(input+'.'+signature.toString('base64url'));
  }
  return {result,claims,token};
}
const invalid=fn=>assert.throws(fn,{message:'invalid_oidc_input'});
const verify=(f,changes={},options={},clock=now,expected=context)=>verifyGithubOidcBytes(f.token(changes,options),f.result.trust_bytes,expected,clock);

test('real RSA2048 and RSA4096 tokens return only frozen required OIDC claims',()=>{
  for(const rsa of [rsa2048,rsa4096]) {
    const f=fixture(rsa);const result=verify(f,{actor:'fixture',ref_protected:true});
    assert.deepEqual({...result},f.claims);assert.ok(Object.isFrozen(result));
    assert.equal(result.environment,'workshop-staging-publish');assert.equal(f.result.policy.environment,'staging');
    assert.equal(result.source_sha,undefined);assert.equal(result.runtime_service_origin,undefined);
  }
});
test('protected environment is an exact signed binding',()=>{
  const f=fixture();for(const environment of ['staging','other-environment',123,null])invalid(()=>verify(f,{environment}));
  const claims={...f.claims};delete claims.environment;invalid(()=>verify(f,{}, {payloadRaw:bytes(claims)}));
});
test('all identity, subject and workflow claims bind the signed owner policy',()=>{
  const f=fixture();
  for(const key of ['iss','aud','sub','repository','repository_id','repository_owner_id','workflow_ref','workflow_sha','ref','sha','event_name']) {
    invalid(()=>verify(f,{[key]:'wrong'}));invalid(()=>verify(f,{[key]:123}));
  }
  invalid(()=>verify(f,{aud:[f.claims.aud]}));
  for(const key of Object.keys(f.claims)) {const claims={...f.claims};delete claims[key];invalid(()=>verify(f,{}, {payloadRaw:bytes(claims)}));}
});
test('run and attempt must be exact canonical strings and context must be exact',()=>{
  const f=fixture();
  for(const changes of [{run_id:123456789},{run_id:'0123456789'},{run_id:'0'},{run_attempt:2},{run_attempt:'02'},{run_attempt:'1'},{run_attempt:'1001'},{run_attempt:'0'}])invalid(()=>verify(f,changes));
  for(const expected of [{run_id:context.run_id,run_attempt:'2'},{...context,extra:true},{...context,run_id:'01'},{...context,run_attempt:0},{...context,run_attempt:1001},{...context,run_attempt:1},{get run_id(){throw Error('secret');},run_attempt:2},Object.assign(Object.create({hidden:true}),context)])invalid(()=>verify(f,{}, {},now,expected));
});
test('JWT lifetime boundaries have exact expiration and bounded clock skew',()=>{
  const f=fixture();
  verify(f,{iat:now,nbf:now-30,exp:now+300});
  verify(f,{iat:now+30,nbf:now+30,exp:now+31});
  verify(f,{iat:now-299,nbf:now-299,exp:now+1});
  for(const changes of [{exp:now},{exp:now-1},{exp:now+241},{iat:now+31},{iat:now-301},{nbf:now-91},{nbf:now+31},{nbf:now+240},{exp:now+0.5},{iat:'1800000000'},{nbf:null}])invalid(()=>verify(f,changes));
  for(const clock of [-1,NaN,Infinity,now+0.5])invalid(()=>verify(f,{}, {},clock));
});
test('JWT requires canonical bounded segments, strict headers and RS256 PKCS1 signatures',()=>{
  const f=fixture();
  for(const header of [{alg:'none'},{alg:'HS256'},{alg:'PS256'},{typ:'jwt'},{kid:'unknown'},{jku:'https://attacker.invalid'},{jwk:{}},{x5u:'https://attacker.invalid'},{crit:[]},{b64:false},{extra:true}])invalid(()=>verify(f,{}, {header}));
  invalid(()=>verify(f,{}, {signer:wrongSigner.privateKey}));
  invalid(()=>verify(f,{}, {padding:constants.RSA_PKCS1_PSS_PADDING}));
  invalid(()=>verify(f,{}, {headerRaw:Buffer.from('{"alg":"RS256","alg":"RS256","typ":"JWT","kid":"fixture-key"}')}));
  invalid(()=>verify(f,{}, {headerRaw:Buffer.alloc(1025,32)}));
  const token=f.token().toString(),segments=token.split('.');
  for(const text of ['',token+'.x',segments.slice(0,2).join('.'),token+'=',token+'\n',segments[0]+'=.'+segments[1]+'.'+segments[2],segments[0]+'.'+segments[1]+'.'+Buffer.alloc(255).toString('base64url'),segments[0]+'.'+segments[1]+'.'+Buffer.alloc(512).toString('base64url'),'x'.repeat(16385)])invalid(()=>verifyGithubOidcBytes(Buffer.from(text),f.result.trust_bytes,context,now));
  invalid(()=>verifyGithubOidcBytes(token,f.result.trust_bytes,context,now));
});
test('strict payload rejects duplicate/unknown/unbounded claims and missing jti',()=>{
  const f=fixture();
  for(const changes of [{unknown:'value'},{source_sha:'b'.repeat(40)},{jti:''},{jti:'x'.repeat(257)},{jti:'bad\nvalue'},{actor:1},{ref_protected:'yes'}])invalid(()=>verify(f,changes));
  for(const value of [true,false,'true','false'])verify(f,{ref_protected:value});
  verify(f,{head_ref:'',job_workflow_sha:'b'.repeat(40)});
  const duplicate=JSON.stringify(f.claims).replace('"jti":"fixture-token"','"jti":"fixture-token","jti":"another"');
  invalid(()=>verify(f,{}, {payloadRaw:Buffer.from(duplicate)}));
  invalid(()=>verify(f,{}, {payloadRaw:Buffer.alloc(8193,32)}));
});
test('PolicyTrustBytes rejects parsed, full-result, forged, accessor and extra-field substitutes',()=>{
  const f=fixture();
  for(const trust of [f.result,f.result.policy,{policy:f.result.policy,jwks:f.result.jwks},{},{...f.result.trust_bytes,verified:true},Object.assign(Object.create({}),f.result.trust_bytes),{...f.result.trust_bytes,get bootstrap_base64(){throw Error('secret');}},new Proxy(f.result.trust_bytes,{get(){throw Error('secret');}})])invalid(()=>verifyGithubOidcBytes(f.token(),trust,context,now));
  verifyGithubOidcBytes(f.token(),{...f.result.trust_bytes},context,now);
});
test('every trust component is fully reverified and old passive records expire',()=>{
  const f=fixture();
  for(const key of Object.keys(f.result.trust_bytes)) {
    const raw=Buffer.from(f.result.trust_bytes[key],'base64');raw[0]^=1;
    invalid(()=>verifyGithubOidcBytes(f.token(),{...f.result.trust_bytes,[key]:raw.toString('base64')},context,now));
    invalid(()=>verifyGithubOidcBytes(f.token(),{...f.result.trust_bytes,[key]:f.result.trust_bytes[key]+'\n'},context,now));
  }
  invalid(()=>verifyGithubOidcBytes(f.token({iat:now+600,nbf:now+600,exp:now+700}),f.result.trust_bytes,context,now+600));
  const expiring=fixture(rsa2048,{expires_at:now+1});
  invalid(()=>verifyGithubOidcBytes(expiring.token(),expiring.result.trust_bytes,context,now+1));
});
test('installed wrapper cannot accept passive claims, copied handles or claimed receipts',()=>{
  const f=fixture();for(const handle of [{},{...f.result},f.result.trust_bytes,{verified:true},Object.freeze(Object.create(null))])invalid(()=>verifyInstalledGithubOidc(f.token(),handle,context));
});
test('runtime authenticator always denies with zero argument and environment inspection',()=>{
  let inspections=0;const hostile=new Proxy(function(){inspections++;throw Error('callback');},{get(){inspections++;throw Error('argument');},ownKeys(){inspections++;throw Error('keys');},apply(){inspections++;throw Error('apply');}});
  const originalEnvironment=process.env;
  process.env=new Proxy(originalEnvironment,{get(){inspections++;throw Error('environment');}});
  try {
    for(const args of [[],[hostile],[hostile,hostile],[fixture().result],['token']])assert.throws(()=>authenticateActionsRuntime(...args),{message:'missing_dependency'});
  } finally {process.env=originalEnvironment;}
  assert.equal(inspections,0);
});
