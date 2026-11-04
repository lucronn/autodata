import {createPublicKey,verify,constants} from 'node:crypto';
import {types} from 'node:util';
import {parseStrictJsonBytes,verifyOwnerPolicyBytes,installedPolicyClaims} from './publisher_policy.mjs';

const fail=()=>{throw new Error('invalid_oidc_input');};
const requireValue=condition=>{if(!condition)fail();};
const decimal=value=>typeof value==='string' && /^[1-9][0-9]{0,19}$/.test(value);
const safeTime=value=>Number.isSafeInteger(value) && value>=0;
const requiredClaims=['iss','aud','sub','exp','iat','nbf','jti','repository','repository_id','repository_owner_id','run_id','run_attempt','workflow_ref','workflow_sha','ref','sha','event_name','environment'];
const optionalClaims=['run_number','actor','actor_id','workflow','repository_owner','repository_visibility','ref_type','ref_protected','head_ref','base_ref','runner_environment','job_workflow_ref','job_workflow_sha','environment_node_id','enterprise','enterprise_id','issuer_scope','check_run_id'];
function ownData(value,required,optional=[]) {
  requireValue(value!==null && typeof value==='object' && !types.isProxy(value) && [Object.prototype,null].includes(Object.getPrototypeOf(value)));
  const keys=Reflect.ownKeys(value);requireValue(required.every(key=>keys.includes(key)) && keys.every(key=>typeof key==='string' && [...required,...optional].includes(key)));
  for(const key of keys) {const descriptor=Object.getOwnPropertyDescriptor(value,key);requireValue(descriptor && Object.hasOwn(descriptor,'value') && descriptor.enumerable);}
}
function decode(value,max,url=true,min=1) {
  requireValue(typeof value==='string' && value.length>0 && value.length<=Math.ceil(max/3)*4);
  requireValue((url?/^[A-Za-z0-9_-]+$/:/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/).test(value));
  const raw=Buffer.from(value,url?'base64url':'base64');requireValue(raw.length>=min && raw.length<=max && raw.toString(url?'base64url':'base64')===value);return raw;
}
function validateContext(context) {
  ownData(context,['run_id','run_attempt']);requireValue(decimal(context.run_id) && Number.isInteger(context.run_attempt) && context.run_attempt>=1 && context.run_attempt<=1000);
}
function verifyJwt(tokenBytes,validated,expectedContext,nowSeconds) {
  requireValue(safeTime(nowSeconds) && Buffer.isBuffer(tokenBytes) && tokenBytes.length>0 && tokenBytes.length<=16384);
  validateContext(expectedContext);
  const token=Buffer.from(tokenBytes).toString('utf8');const segments=token.split('.');requireValue(segments.length===3);
  const headerRaw=decode(segments[0],1024),payloadRaw=decode(segments[1],8192),signature=decode(segments[2],512,true,256);
  const header=parseStrictJsonBytes(headerRaw,{maxBytes:1024});ownData(header,['alg','typ','kid']);
  requireValue(header.alg==='RS256' && header.typ==='JWT' && typeof header.kid==='string' && /^[A-Za-z0-9_-]{1,128}$/.test(header.kid));
  const {policy,jwks}=validated;
  // The installed accessor has already reverified all original trust bytes. This later
  // clock check also rejects crossing policy/snapshot expiry between accessor and JWT.
  requireValue(policy.issued_at<=nowSeconds && nowSeconds<policy.expires_at && policy.oidc.jwks_issued_at<=nowSeconds && nowSeconds<policy.oidc.jwks_expires_at);
  const jwk=jwks.keys.find(key=>key.kid===header.kid);requireValue(Boolean(jwk));
  const modulus=decode(jwk.n,512,true,256);requireValue(signature.length===modulus.length);
  const key=createPublicKey({key:jwk,format:'jwk'});requireValue(key.asymmetricKeyType==='rsa' && key.asymmetricKeyDetails.modulusLength>=2048 && key.asymmetricKeyDetails.modulusLength<=4096);
  requireValue(verify('RSA-SHA256',Buffer.from(segments[0]+'.'+segments[1],'ascii'),{key,padding:constants.RSA_PKCS1_PADDING},signature));
  // No payload field influences verification before the signature succeeds.
  const claims=parseStrictJsonBytes(payloadRaw,{maxBytes:8192});ownData(claims,requiredClaims,optionalClaims);
  for(const name of requiredClaims) if(!['exp','iat','nbf'].includes(name))requireValue(typeof claims[name]==='string');
  requireValue(claims.iss===policy.oidc.issuer && claims.aud===policy.oidc.audience && claims.sub===policy.oidc.subject);
  for(const name of ['repository','repository_id','repository_owner_id','workflow_ref','workflow_sha','ref','event_name'])requireValue(claims[name]===policy[name]);
  requireValue(claims.environment===policy.protected_environment && claims.sha===policy.workflow_sha && decimal(claims.run_id) && claims.run_id===expectedContext.run_id);
  requireValue(/^[1-9][0-9]{0,3}$/.test(claims.run_attempt) && Number(claims.run_attempt)<=1000 && claims.run_attempt===String(expectedContext.run_attempt));
  const {exp,iat,nbf}=claims;
  requireValue(safeTime(exp) && safeTime(iat) && safeTime(nbf) && exp>nowSeconds && exp>iat && exp-iat<=300 && iat<=nowSeconds+30 && nowSeconds-iat<=300 && iat-30<=nbf && nbf<exp && nbf<=nowSeconds+30);
  requireValue(/^[\x20-\x7e]{1,256}$/.test(claims.jti));
  for(const name of optionalClaims) if(Object.hasOwn(claims,name)) {
    const value=claims[name];
    if(name==='ref_protected')requireValue(typeof value==='boolean' || value==='true' || value==='false');
    else requireValue(typeof value==='string' && Buffer.byteLength(value,'utf8')<=8192);
  }
  const result=Object.create(null);for(const name of requiredClaims)result[name]=claims[name];return Object.freeze(result);
}
export function verifyGithubOidcBytes(tokenBytes,validatedPolicy,expectedContext,nowSeconds) {
  try {
    requireValue(Buffer.isBuffer(tokenBytes) && tokenBytes.length>0 && tokenBytes.length<=16384 && safeTime(nowSeconds));
    ownData(validatedPolicy,['bootstrap_base64','envelope_base64','jwks_base64']);
    const bootstrap=decode(validatedPolicy.bootstrap_base64,16384,false),envelope=decode(validatedPolicy.envelope_base64,65536,false),jwks=decode(validatedPolicy.jwks_base64,65536,false);
    const validated=verifyOwnerPolicyBytes(bootstrap,envelope,jwks,nowSeconds);
    return verifyJwt(tokenBytes,validated,expectedContext,nowSeconds);
  } catch {fail();}
}
export function verifyInstalledGithubOidc(tokenBytes,installedPolicyHandle,expectedContext) {
  try {
    const validated=installedPolicyClaims(installedPolicyHandle);
    return verifyJwt(tokenBytes,validated,expectedContext,Math.floor(Date.now()/1000));
  } catch {fail();}
}
export function authenticateActionsRuntime() {throw new Error('missing_dependency');}
