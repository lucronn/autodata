import {createHash, createPublicKey, verify} from 'node:crypto';
import {open} from 'node:fs/promises';
import {constants} from 'node:fs';

const fail = (code='invalid_trust_input') => {throw new Error(code);};
const requireValue = condition => {if (!condition) fail();};
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const safeTime = value => Number.isSafeInteger(value) && value >= 0;
const ascii = (value,max) => typeof value === 'string' && /^[\x20-\x7e]+$/.test(value) && value.length <= max;
const decimal = value => typeof value === 'string' && /^[1-9][0-9]{0,19}$/.test(value);
const hex = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
function freeze(value) {
  if (value && typeof value === 'object') {for (const child of Object.values(value)) freeze(child);Object.freeze(value);}
  return value;
}
function fields(value,names) {
  requireValue(value !== null && typeof value === 'object' && !Array.isArray(value));
  const keys=Object.keys(value);requireValue(keys.length === names.length && names.every(k=>Object.hasOwn(value,k)));
}
function dataOptions(value,allowed) {
  try {
    requireValue(value!==null && typeof value==='object' && [Object.prototype,null].includes(Object.getPrototypeOf(value)));
    for(const key of Reflect.ownKeys(value)) {requireValue(typeof key==='string' && allowed.includes(key));const descriptor=Object.getOwnPropertyDescriptor(value,key);requireValue(descriptor && Object.hasOwn(descriptor,'value'));}
    return value;
  } catch {fail();}
}
function copyBytes(raw,max) {requireValue(Buffer.isBuffer(raw) && raw.length > 0 && raw.length <= max);return Buffer.from(raw);}
function decode(value,max,url=false,min=1) {
  requireValue(typeof value === 'string' && value.length > 0 && value.length <= Math.ceil(max/3)*4);
  requireValue((url ? /^[A-Za-z0-9_-]+$/ : /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/).test(value));
  const bytes=Buffer.from(value,url?'base64url':'base64');
  requireValue(bytes.length >= min && bytes.length <= max && bytes.toString(url?'base64url':'base64') === value);return bytes;
}

// Recursive descent retains decoded-key identity and rejects syntax JSON.parse normalizes.
export function parseStrictJsonBytes(raw, limits={}) {
  try {
    const maxima={maxBytes:65536,maxDepth:16,maxKeys:256,maxStringBytes:8192,maxArrayLength:16};
    for (const [key,value] of Object.entries(limits)) {requireValue(Object.hasOwn(maxima,key) && Number.isSafeInteger(value) && value>0 && value<=maxima[key]);maxima[key]=value;}
    const bytes=copyBytes(raw,maxima.maxBytes), text=bytes.toString('utf8');
    requireValue(Buffer.from(text,'utf8').equals(bytes) && text.charCodeAt(0)!==0xfeff);
    let position=0,keyCount=0;
    const ws=()=>{while(/[\x20\t\r\n]/.test(text[position] ?? '\0'))position++;};
    function string() {
      const start=position++;let escaped=false;
      while(position<text.length) {
        const char=text[position++];
        if(char==='"' && !escaped) {
          const value=JSON.parse(text.slice(start,position));
          requireValue(Buffer.byteLength(value,'utf8')<=maxima.maxStringBytes);
          for(let i=0;i<value.length;i++) {
            const c=value.charCodeAt(i);
            if(c>=0xd800 && c<=0xdbff){const next=value.charCodeAt(++i);requireValue(next>=0xdc00 && next<=0xdfff);}
            else requireValue(c<0xdc00 || c>0xdfff);
          }
          return value;
        }
        if(char==='\\' && !escaped) escaped=true;else escaped=false;
      }
      fail();
    }
    function value(depth) {
      requireValue(depth<=maxima.maxDepth);ws();const char=text[position];
      if(char==='"') return string();
      if(char==='{') {
        position++;const result=Object.create(null);ws();if(text[position]==='}'){position++;return result;}
        while(true) {
          ws();requireValue(text[position]==='"');const key=string();requireValue(!Object.hasOwn(result,key) && ++keyCount<=maxima.maxKeys);
          ws();requireValue(text[position++]===':');result[key]=value(depth+1);ws();const next=text[position++];
          if(next==='}')return result;requireValue(next===',');
        }
      }
      if(char==='[') {
        position++;const result=[];ws();if(text[position]===']'){position++;return result;}
        while(true){requireValue(result.length<maxima.maxArrayLength);result.push(value(depth+1));ws();const next=text[position++];if(next===']')return result;requireValue(next===',');}
      }
      for(const [word,result] of [['true',true],['false',false],['null',null]]) if(text.startsWith(word,position)){position+=word.length;return result;}
      const match=/^-?(?:0|[1-9][0-9]*)/.exec(text.slice(position));requireValue(Boolean(match));
      position+=match[0].length;const number=Number(match[0]);requireValue(Number.isSafeInteger(number) && !Object.is(number,-0));return number;
    }
    const result=value(0);ws();requireValue(position===text.length);return result;
  } catch {fail();}
}

function validateJwks(jwks) {
  fields(jwks,['keys']);requireValue(Array.isArray(jwks.keys) && jwks.keys.length>=1 && jwks.keys.length<=16);
  let previous='';
  for(const key of jwks.keys) {
    fields(key,['kty','kid','use','alg','n','e']);
    requireValue(key.kty==='RSA' && key.use==='sig' && key.alg==='RS256' && key.e==='AQAB' && typeof key.kid==='string' && /^[A-Za-z0-9_-]{1,128}$/.test(key.kid) && key.kid>previous);previous=key.kid;
    const modulus=decode(key.n,512,true,256);requireValue((modulus[0]&128)!==0 && (modulus.at(-1)&1)===1);
    const publicKey=createPublicKey({key,format:'jwk'});const bits=publicKey.asymmetricKeyDetails?.modulusLength;
    requireValue(publicKey.asymmetricKeyType==='rsa' && bits>=2048 && bits<=4096);
  }
}
export function verifyOwnerPolicyBytes(bootstrapBytes,envelopeBytes,jwksBytes,nowSeconds) {
  try {
    requireValue(safeTime(nowSeconds));
    const bootstrapRaw=copyBytes(bootstrapBytes,16384),envelopeRaw=copyBytes(envelopeBytes,65536),jwksRaw=copyBytes(jwksBytes,65536);
    const bootstrap=parseStrictJsonBytes(bootstrapRaw,{maxBytes:16384});
    fields(bootstrap,['protocol_version','purpose','key_id','owner_public_key','policy_sha256','minimum_epoch']);
    requireValue(bootstrap.protocol_version===1 && bootstrap.purpose==='autodata.publisher.bootstrap.v1' && hex(bootstrap.key_id) && hex(bootstrap.policy_sha256) && Number.isSafeInteger(bootstrap.minimum_epoch) && bootstrap.minimum_epoch>=1 && bootstrap.minimum_epoch<=2147483647);
    const rawKey=decode(bootstrap.owner_public_key,32);requireValue(rawKey.length===32 && digest(rawKey)===bootstrap.key_id && digest(envelopeRaw)===bootstrap.policy_sha256);
    const envelope=parseStrictJsonBytes(envelopeRaw,{maxBytes:65536});fields(envelope,['protocol_version','key_id','payload','signature']);requireValue(envelope.protocol_version===1 && envelope.key_id===bootstrap.key_id);
    const payload=decode(envelope.payload,32768),signature=decode(envelope.signature,64);requireValue(signature.length===64);
    const publicKey=createPublicKey({key:Buffer.concat([Buffer.from('302a300506032b6570032100','hex'),rawKey]),format:'der',type:'spki'});
    requireValue(verify(null,Buffer.concat([Buffer.from('AutoData-Publisher-Owner-Policy-v1\0','ascii'),payload]),publicKey,signature));
    const policy=parseStrictJsonBytes(payload,{maxBytes:32768});
    fields(policy,['protocol_version','purpose','epoch','issued_at','expires_at','repository','repository_id','repository_owner_id','environment','protected_environment','workflow_ref','workflow_sha','ref','event_name','upload_enabled','runtime_bearer_authentication','oidc']);
    requireValue(policy.protocol_version===1 && policy.purpose==='autodata.publisher.stage1a.offline' && Number.isSafeInteger(policy.epoch) && policy.epoch>=bootstrap.minimum_epoch && policy.epoch<=2147483647);
    requireValue(safeTime(policy.issued_at) && safeTime(policy.expires_at) && policy.issued_at<=nowSeconds && nowSeconds<policy.expires_at && policy.expires_at-policy.issued_at<=86400);
    requireValue(policy.repository==='lucronn/autodata' && decimal(policy.repository_id) && decimal(policy.repository_owner_id) && policy.environment==='staging' && policy.protected_environment==='workshop-staging-publish' && policy.workflow_ref==='lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master' && typeof policy.workflow_sha==='string' && /^[0-9a-f]{40}$/.test(policy.workflow_sha) && policy.ref==='refs/heads/master' && policy.event_name==='workflow_dispatch' && policy.upload_enabled===false && policy.runtime_bearer_authentication==='unsupported');
    const oidc=policy.oidc;fields(oidc,['issuer','audience','subject','jwks_sha256','jwks_issued_at','jwks_expires_at']);
    requireValue(oidc.issuer==='https://token.actions.githubusercontent.com' && oidc.audience==='urn:autodata:publisher:stage1a:offline' && ascii(oidc.subject,512) && hex(oidc.jwks_sha256) && digest(jwksRaw)===oidc.jwks_sha256);
    requireValue(safeTime(oidc.jwks_issued_at) && safeTime(oidc.jwks_expires_at) && oidc.jwks_issued_at<=policy.issued_at && policy.expires_at<=oidc.jwks_expires_at && oidc.jwks_expires_at-oidc.jwks_issued_at>0 && oidc.jwks_expires_at-oidc.jwks_issued_at<=86400);
    const jwks=parseStrictJsonBytes(jwksRaw,{maxBytes:65536});validateJwks(jwks);
    return freeze({policy,jwks,activation_sha256:digest(envelopeRaw),trust_bytes:{bootstrap_base64:bootstrapRaw.toString('base64'),envelope_base64:envelopeRaw.toString('base64'),jwks_base64:jwksRaw.toString('base64')}});
  } catch {fail();}
}

// Only state, pending work and owned descriptors survive failed cleanup. No late authority.
const scopeStates=new WeakMap(),quarantine=new Set();
let installedScope=null;
function clean(state) {return state.pending.size===0 && [...state.handles.values()].every(h=>h.status==='closed');}
function drain(state) {
  if(!state.ending || state.pending.size) return;
  let closing=[...state.handles.values()].filter(h=>h.status==='closing').length;
  for(const [handle,entry] of state.handles) {
    if(closing>=16)break;
    if(entry.status!=='open')continue;
    entry.status='closing';closing++;
    // A closure is never retried, including a synchronous failure.
    entry.promise=Promise.resolve().then(()=>handle.close()).then(()=>{entry.status='closed';drain(state);},()=>{entry.status='failed';drain(state);});
  }
  if(clean(state)){quarantine.delete(state);if(installedScope===state && state.returned)installedScope=null;}
}
function reason(state) {
  if(state.signal?.aborted)return 'operation_cancelled';
  if(performance.now()>=state.verifyCutoff)return 'operation_timed_out';
  return null;
}
function register(scope,promise,isOpen) {
  const state=scopeStates.get(scope);requireValue(Boolean(state) && !state.ending && state.pending.size<16);
  const entry={};state.pending.add(entry);
  const observed=Promise.resolve(promise).then(value=>{
    if(isOpen) {
      if(!value || typeof value.close!=='function')fail();
      if(!state.handles.has(value))state.handles.set(value,{status:'open'});
    }
    return value;
  });
  entry.promise=observed;
  observed.then(()=>{state.pending.delete(entry);drain(state);},()=>{state.pending.delete(entry);drain(state);});
  return new Promise((resolve,reject)=>{
    let settled=false;
    const complete=(fn,value)=>{if(settled)return;settled=true;clearTimeout(timer);state.signal?.removeEventListener('abort',abort);fn(value);};
    const abort=()=>complete(reject,new Error('operation_cancelled'));
    const timer=setTimeout(()=>complete(reject,new Error('operation_timed_out')),Math.max(0,state.verifyCutoff-performance.now()));
    state.signal?.addEventListener('abort',abort,{once:true});
    observed.then(value=>{const error=reason(state);if(error || state.ending)complete(reject,new Error(error??'invalid_trust_input'));else complete(resolve,value);},error=>complete(reject,new Error(error?.message==='missing_dependency'?'missing_dependency':'invalid_trust_input')));
    if(state.signal?.aborted)abort();
  });
}
export class OwnedTrustReadScope {
  constructor(options={}) {
    const {signal,budgetMs=5000,cleanupReserveMs=1000}=dataOptions(options,['signal','budgetMs','cleanupReserveMs']);
    requireValue(Number.isInteger(budgetMs) && budgetMs>=1 && budgetMs<=5000 && Number.isInteger(cleanupReserveMs) && cleanupReserveMs>=1 && cleanupReserveMs<=1000);
    requireValue(signal===undefined || (signal instanceof AbortSignal));
    const start=performance.now();const state={signal,verifyCutoff:start+budgetMs,finalCutoff:start+budgetMs+cleanupReserveMs,cleanupReserveMs,pending:new Set(),handles:new Map(),ending:false,returned:false,finishPromise:null};
    state.abort=()=>{const now=performance.now();state.verifyCutoff=Math.min(state.verifyCutoff,now);state.finalCutoff=Math.min(state.finalCutoff,now+cleanupReserveMs);};
    signal?.addEventListener('abort',state.abort,{once:true});if(signal?.aborted)state.abort();scopeStates.set(this,state);
  }
  check() {const state=scopeStates.get(this);requireValue(Boolean(state) && !state.ending && state.pending.size<16);const error=reason(state);if(error)fail(error);}
  trackOpen(promise) {return register(this,promise,true);}
  track(promise) {return register(this,promise,false);}
  finish() {
    const state=scopeStates.get(this);if(state.finishPromise)return state.finishPromise;
    state.ending=true;drain(state);
    state.finishPromise=(async()=>{
      let timer;
      try {
        while(!clean(state) && performance.now()<state.finalCutoff) await new Promise(resolve=>{timer=setTimeout(resolve,Math.min(5,Math.max(0,state.finalCutoff-performance.now())));});
        if(!clean(state)){quarantine.add(state);fail('cleanup_failed');}
        const error=reason(state);if(error)fail(error);
      } finally {clearTimeout(timer);state.returned=true;state.signal?.removeEventListener('abort',state.abort);if(clean(state) && installedScope===state)installedScope=null;}
    })();return state.finishPromise;
  }
}

const installedPolicies=new WeakMap();
const fileNames=['bootstrap-v1.json','policy-v1.envelope.json','github-oidc-jwks-v1.json'];
const bounds=[16384,65536,65536];
const trustDirectory='/etc/autodata/publisher';
const fileFlags=constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK|(constants.O_CLOEXEC??0);
const directoryFlags=fileFlags|constants.O_DIRECTORY;
function validateStat(stat,directory,max) {
  requireValue(stat.uid===0 && (stat.mode&0o7000)===0);
  if(directory)requireValue(stat.isDirectory() && (stat.mode&0o022)===0);
  else requireValue(stat.isFile() && stat.nlink===1 && [0o400,0o444].includes(stat.mode&0o777) && Number.isSafeInteger(stat.size) && stat.size>0 && stat.size<=max);
}
function identity(stat) {return [stat.dev,stat.ino,stat.mode,stat.uid,stat.gid,stat.nlink,stat.size].join(':');}
function parseMounts(raw) {
  const text=raw.toString('utf8');requireValue(Buffer.from(text).equals(raw));const result=new Map();
  const unescape=value=>value.replace(/\\(040|011|012|134)/g,(_,octal)=>String.fromCharCode(parseInt(octal,8)));
  for(const line of text.trimEnd().split('\n')) {
    const parts=line.split(' '),separator=parts.indexOf('-');
    requireValue(separator>=6 && parts.length===separator+4 && /^[1-9][0-9]*$/.test(parts[0]) && !result.has(parts[0]) && parts[4].startsWith('/'));
    const options=parts[5].split(',');requireValue(options.includes('ro')!==options.includes('rw'));
    result.set(parts[0],{path:unescape(parts[4]),readonly:options.includes('ro')});
  }
  requireValue(result.size>0);return result;
}
function mountId(raw) {
  const text=raw.toString('utf8');requireValue(Buffer.from(text).equals(raw));
  const matches=[...text.matchAll(/^mnt_id:\s+([1-9][0-9]*)\s*$/gm)];requireValue(matches.length===1);return matches[0][1];
}
export async function loadInstalledOwnerPolicy(options={}) {
  const {signal}=dataOptions(options,['signal']);
  if(installedScope)fail('cleanup_failed');
  const scope=new OwnedTrustReadScope({signal,budgetMs:5000,cleanupReserveMs:1000});
  const state=scopeStates.get(scope);installedScope=state;
  const op=(fn,isOpen=false)=>{scope.check();const promise=fn().catch(error=>{if(error?.code==='ENOENT')fail('missing_dependency');throw error;});return isOpen?scope.trackOpen(promise):scope.track(promise);};
  let result,error;
  try {
    async function procBytes(path,max) {
      const handle=await op(()=>open(path,fileFlags),true);return read(handle,max);
    }
    async function read(handle,max,declared) {
      const chunks=[];let total=0;
      while(true) {
        const buffer=Buffer.alloc(Math.min(32768,max+1-total));
        const {bytesRead}=await op(()=>handle.read(buffer,0,buffer.length,total));scope.check();
        if(bytesRead===0)break;total+=bytesRead;requireValue(total<=max);chunks.push(buffer.subarray(0,bytesRead));
      }
      requireValue(declared===undefined || total===declared);return Buffer.concat(chunks,total);
    }
    async function chain() {
      const nodes=[];let handle=await op(()=>open('/',directoryFlags),true);
      for(const component of [null,'etc','autodata','publisher']) {
        if(component!==null)handle=await op(()=>open(`/proc/self/fd/${handle.fd}/${component}`,directoryFlags),true);
        const stat=await op(()=>handle.stat());validateStat(stat,true);nodes.push({handle,stat});
      }
      for(let i=0;i<fileNames.length;i++) {
        const handle=await op(()=>open(`/proc/self/fd/${nodes[3].handle.fd}/${fileNames[i]}`,fileFlags),true);
        const stat=await op(()=>handle.stat());validateStat(stat,false,bounds[i]);nodes.push({handle,stat});
      }
      return nodes;
    }
    const nodes=await chain();const initialMounts=await procBytes('/proc/self/mountinfo',1048576);
    async function checkMounts(nodes,raw) {
      const mounts=parseMounts(raw);const ids=[];
      for(const node of nodes) {
        const id=mountId(await procBytes(`/proc/self/fdinfo/${node.handle.fd}`,4096));requireValue(mounts.has(id));ids.push(id);
      }
      for(let i=3;i<nodes.length;i++)requireValue(mounts.get(ids[i]).readonly);
      for(const mount of mounts.values())if(mount.path.startsWith(trustDirectory+'/'))requireValue(mount.readonly);
      return ids;
    }
    const ids=await checkMounts(nodes,initialMounts);const trust=[];
    for(let i=0;i<3;i++)trust.push(await read(nodes[i+4].handle,bounds[i],nodes[i+4].stat.size));
    for(let i=0;i<nodes.length;i++) {
      const after=await op(()=>nodes[i].handle.stat());validateStat(after,i<4,bounds[i-4]);requireValue(identity(after)===identity(nodes[i].stat));
    }
    const laterMounts=await procBytes('/proc/self/mountinfo',1048576);requireValue(initialMounts.equals(laterMounts));
    const laterIds=await checkMounts(nodes,laterMounts);requireValue(ids.every((id,i)=>id===laterIds[i]));
    const reopened=await chain();requireValue(reopened.every((node,i)=>identity(node.stat)===identity(nodes[i].stat)));
    const reopenedIds=await checkMounts(reopened,laterMounts);requireValue(ids.every((id,i)=>id===reopenedIds[i]));
    scope.check();result=verifyOwnerPolicyBytes(...trust,Math.floor(Date.now()/1000));scope.check();
  } catch(caught) {
    error=new Error(caught?.code==='ENOENT'?'missing_dependency':['missing_dependency','operation_timed_out','operation_cancelled'].includes(caught?.message)?caught.message:'invalid_trust_input');
  }
  try {await scope.finish();}catch(cleanup){error=cleanup;}
  if(error)throw error;
  const handle=Object.freeze(Object.create(null));installedPolicies.set(handle,result.trust_bytes);return handle;
}
export function installedPolicyClaims(handle) {
  try {
    const trust=installedPolicies.get(handle);requireValue(Boolean(trust));
    // Revalidate original private bytes with a trusted current clock on every access.
    const verified=verifyOwnerPolicyBytes(decode(trust.bootstrap_base64,16384),decode(trust.envelope_base64,65536),decode(trust.jwks_base64,65536),Math.floor(Date.now()/1000));
    return freeze({policy:verified.policy,jwks:verified.jwks,activation_sha256:verified.activation_sha256});
  } catch {fail();}
}
