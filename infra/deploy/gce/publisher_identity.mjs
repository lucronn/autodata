import {createPublicKey,verify,constants} from 'node:crypto';
import {types} from 'node:util';
import {parseStrictJsonBytes,verifyOwnerPolicyBytes,installedPolicyClaims,installedLivePolicyClaims} from './publisher_policy.mjs';

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
export function verifyInstalledLiveGithubOidc(tokenBytes,installedPolicyHandle,expectedContext) {
  try {
    const validated=installedLivePolicyClaims(installedPolicyHandle);
    return verifyJwt(tokenBytes,validated,expectedContext,Math.floor(Date.now()/1000));
  } catch {fail();}
}
export function authenticateActionsRuntime(handle,runtime,context) {
  // WeakMap selection occurs before any hostile argument or environment access.
  try {installedLivePolicyClaims(handle);} catch {throw Error('missing_dependency');}
  return (async()=>{
    const {runRuntimeChallenge}=await import('./publisher_artifact.mjs');
    return runRuntimeChallenge(handle,runtime,context);
  })();
}

// Node's HTTPS client does not consume proxy environment variables or .netrc.
// Every credential-bearing request has a fixed GitHub service scope and cannot
// follow a redirect. DNS is resolved once and public peers are checked again.
function publicAddress(address) {
  if(address.includes(':'))return /^[23][0-9a-f]{3}:/i.test(address) && !/^2001:db8:/i.test(address);
  const a=address.split('.').map(Number);if(a.length!==4 || a.some(n=>!Number.isInteger(n)||n<0||n>255))return false;
  return !(a[0]===0 || a[0]===10 || a[0]===127 || a[0]>=224 || (a[0]===100&&a[1]>=64&&a[1]<=127) ||
    (a[0]===169&&a[1]===254) || (a[0]===172&&a[1]>=16&&a[1]<=31) ||
    (a[0]===192&&(a[1]===168||a[1]===0||a[1]===2)) || (a[0]===198&&(a[1]===18||a[1]===19||a[1]===51)) || (a[0]===203&&a[1]===0));
}
function serviceURL(validated,kind,rawURL,token) {
  requireValue(typeof rawURL==='string' && rawURL.length<=8192 && !/[\x00-\x20\\]/.test(rawURL));
  const url=new URL(rawURL);requireValue(url.protocol==='https:' && !url.username && !url.password && !url.port && !url.hash);
  if(kind==='github')requireValue(url.origin==='https://api.github.com' && /^\/repos\/lucronn\/autodata\/actions\//.test(url.pathname) && !url.search);
  else if(kind==='storage')requireValue(validated.policy.storage_origins.includes(url.origin) && token===undefined);
  else if(kind==='oidc') {
    requireValue(/^[a-z0-9-]+\.actions\.githubusercontent\.com$/.test(url.hostname));
    requireValue(/^\/_apis\/distributedtask\/hubs\/build\/plans\/[0-9a-f-]{36}\/jobs\/[0-9a-f-]{36}\/idtoken$/.test(url.pathname));
    requireValue([...url.searchParams.keys()].every(k=>['api-version','audience'].includes(k)) && url.searchParams.getAll('api-version').length===1 && url.searchParams.get('api-version')==='2.0' && url.searchParams.getAll('audience').length===1 && url.searchParams.get('audience')===validated.policy.oidc.audience);
  } else fail();
  return url;
}
export async function installedServiceRequest(handle,kind,rawURL,{token,maximum=65536,deadline=Date.now()+30000}={}) {
  const validated=installedLivePolicyClaims(handle);
  const url=serviceURL(validated,kind,rawURL,token);
  requireValue(token===undefined || (typeof token==='string' && /^[\x21-\x7e]{1,16384}$/.test(token)));
  requireValue(Number.isInteger(maximum) && maximum>=1 && maximum<=16*1024*1024 && Number.isSafeInteger(deadline) && deadline>Date.now() && deadline-Date.now()<=60000);
  const {request}=await import('node:https'),{lookup}=await import('node:dns/promises');
  const addresses=await Promise.race([lookup(url.hostname,{all:true,verbatim:true}),new Promise((_,reject)=>{const timer=setTimeout(()=>reject(Error('operation_timed_out')),Math.max(1,deadline-Date.now()));timer.unref();})]);
  requireValue(addresses.length>=1 && addresses.length<=32 && addresses.every(a=>publicAddress(a.address)) && Date.now()<deadline);
  return new Promise((resolve,reject)=>{
    let done=false,requestObject;const sockets=new Set();
    const finish=(error,value)=>{if(done)return;done=true;clearTimeout(timer);if(error){requestObject?.destroy();for(const socket of sockets)socket.destroy();reject(Error('service_request_failed'));}else resolve(value);};
    const timer=setTimeout(()=>finish(Error('operation_timed_out')),Math.max(1,deadline-Date.now()));
    const headers={'User-Agent':'autodata-workshop-publisher-v3','Accept-Encoding':'identity'};
    if(token!==undefined)headers.Authorization='Bearer '+token;
    if(kind==='github'){headers.Accept='application/vnd.github+json';headers['X-GitHub-Api-Version']='2022-11-28';}
    requestObject=request(url,{method:'GET',agent:false,headers,lookup:(_host,opts,callback)=>{const selected=addresses[0];callback(null,opts.all?[selected]:selected.address,selected.family);}},response=>{
      const lengths=response.rawHeaders.filter((_,i)=>i%2===0&&response.rawHeaders[i].toLowerCase()==='content-length');
      if(lengths.length>1 || ![undefined,'identity'].includes(response.headers['content-encoding'])){finish(Error('invalid_response'));return;}
      const length=response.headers['content-length'];if(length!==undefined&&(!/^[0-9]{1,10}$/.test(length)||Number(length)>maximum)){finish(Error('output_limit'));return;}
      const chunks=[];let size=0;
      response.on('data',chunk=>{size+=chunk.length;if(size>maximum || Date.now()>=deadline){finish(Error('output_limit'));return;}chunks.push(chunk);});
      response.on('error',finish);response.on('end',()=>{if(length!==undefined&&Number(length)!==size){finish(Error('invalid_response'));return;}finish(null,{status:response.statusCode,location:response.headers.location,bytes:Buffer.concat(chunks,size)});});
    });
    requestObject.on('socket',socket=>{sockets.add(socket);socket.on('secureConnect',()=>{if(!addresses.some(a=>a.address===socket.remoteAddress)||!publicAddress(socket.remoteAddress))finish(Error('unsafe_address'));});socket.once('close',()=>sockets.delete(socket));});
    requestObject.on('error',finish);requestObject.end();
  });
}
export async function fetchInstalledGithubOidc(handle,context,requestCredentials) {
  const {policy}=installedLivePolicyClaims(handle);validateContext(context);
  if(requestCredentials!==undefined)ownData(requestCredentials,['ACTIONS_ID_TOKEN_REQUEST_URL','ACTIONS_ID_TOKEN_REQUEST_TOKEN']);
  const rawURL=requestCredentials===undefined?process.env.ACTIONS_ID_TOKEN_REQUEST_URL:requestCredentials.ACTIONS_ID_TOKEN_REQUEST_URL;
  requireValue(typeof rawURL==='string' && !rawURL.includes('audience='));
  const url=new URL(rawURL);url.searchParams.append('audience',policy.oidc.audience);
  serviceURL({policy},'oidc',url.href);
  const response=await installedServiceRequest(handle,'oidc',url.href,{token:requestCredentials===undefined?process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN:requestCredentials.ACTIONS_ID_TOKEN_REQUEST_TOKEN,maximum:32768});
  requireValue(response.status===200);const data=parseStrictJsonBytes(response.bytes,{maxBytes:32768});ownData(data,['value']);
  const raw=Buffer.from(data.value,'utf8'),claims=verifyInstalledLiveGithubOidc(raw,handle,context);
  verifiedTokens.set(claims,{handle,raw});return claims;
}

export const isPublicServiceAddress=publicAddress;

const verifiedTokens=new WeakMap();
/** Only genuine verified-token handles can create the fixed private signing file. */
export async function writeVerifiedSigstoreToken(handle,claims) {
 const {policy}=installedLivePolicyClaims(handle),token=verifiedTokens.get(claims);
 requireValue(token?.handle===handle && policy.oidc.audience==='sigstore' && claims.exp>Math.floor(Date.now()/1000)+30);
 const {open,realpath,unlink}=await import('node:fs/promises'),{constants}=await import('node:fs');
 const cwd=process.cwd();requireValue(await realpath(cwd)===cwd);
 const directory=await open(cwd,constants.O_RDONLY|constants.O_DIRECTORY|constants.O_NOFOLLOW);let file,created=false;
 try {
  const before=await directory.stat();requireValue(before.uid===process.getuid() && (before.mode&0o7777)===0o700);
  const name=`/proc/self/fd/${directory.fd}/identity-token`;
  try {
   file=await open(name,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o600);created=true;
   await file.writeFile(token.raw);await file.sync();const after=await file.stat();
   requireValue(after.isFile() && after.nlink===1 && after.uid===process.getuid() && (after.mode&0o7777)===0o600 && after.size===token.raw.length);
   const later=await directory.stat();requireValue(before.dev===later.dev && before.ino===later.ino && before.mode===later.mode && before.uid===later.uid);
  } catch {if(created)await unlink(name);fail();}
 } finally {await file?.close();await directory.close();}
}
