/** Dormant Actions upload boundary. No default runtime package loading or activation.
 * The injected contract is deliberately unusable as evidence of live publication.
 * The reviewed candidate toolkit lock/runtime still requires a runtime-token authenticator, bounded
 * REST raw readback + ZIP decoder and activation gate are required to wire IPC.
 */
import {createHash,randomBytes} from 'node:crypto';
import {installedLivePolicyClaims,loadInstalledLiveOwnerPolicy} from './publisher_policy.mjs';
import {fetchInstalledGithubOidc,installedServiceRequest,authenticateActionsRuntime,isPublicServiceAddress,writeVerifiedSigstoreToken} from './publisher_identity.mjs';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {writeSync} from 'node:fs';
import {inflateRawSync} from 'node:zlib';
import {open, lstat, readdir, readFile, realpath} from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn as spawnProcess, ChildProcess} from 'node:child_process';

const INVALID='invalid authenticated publication input';
const MAX_JSON=65536, MAX_INNER=8*1024*1024, MAX_OUTER=16*1024*1024;
const SHA=/^[0-9a-f]{64}$/, COMMIT=/^[0-9a-f]{40}$/, ID=/^[1-9][0-9]{0,19}$/;
const WORKFLOW='lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master';
function require(condition) {if(!condition) throw Error(INVALID);}
function keys(value, names) {
  require(value!==null && typeof value==='object' && !Array.isArray(value));
  require(Object.keys(value).sort().join(',')===[...names].sort().join(','));
}
function hash(bytes) {return createHash('sha256').update(bytes).digest('hex');}
function canonical(value) {
  if(Array.isArray(value)) return '['+value.map(canonical).join(',')+']';
  if(value!==null && typeof value==='object') return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
  return JSON.stringify(value);
}
const CONTEXT_KEYS=['protocol_version','environment','repository','repository_id','repository_owner_id','run_id','run_attempt','workflow_ref','workflow_sha','source_sha','service_config_sha256','protected_environment','activation_sha256','toolchain_sha256','trust_policy_sha256'];
function validateRequest(request) {
  keys(request,['protocol_version','operation','context','archive_sha256','archive_bytes','artifact_name']);
  require(request.protocol_version===3 && request.operation==='upload');
  const c=request.context;keys(c,CONTEXT_KEYS);
  require(c.protocol_version===3 && c.environment==='staging' && c.repository==='lucronn/autodata');
  require(c.protected_environment==='workshop-staging-publish' && c.workflow_ref===WORKFLOW);
  for(const k of ['repository_id','repository_owner_id','run_id']) require(typeof c[k]==='string' && ID.test(c[k]));
  require(Number.isInteger(c.run_attempt) && c.run_attempt>=1 && c.run_attempt<=1000);
  for(const k of ['workflow_sha','source_sha']) require(typeof c[k]==='string' && COMMIT.test(c[k]));
  for(const k of ['service_config_sha256','activation_sha256','toolchain_sha256','trust_policy_sha256']) require(typeof c[k]==='string' && SHA.test(c[k]));
  require(typeof request.archive_sha256==='string' && SHA.test(request.archive_sha256));
  require(Number.isInteger(request.archive_bytes) && request.archive_bytes>=1 && request.archive_bytes<=MAX_INNER);
  require(request.artifact_name===`workshop-release-${c.source_sha}-run-${c.run_id}-attempt-${c.run_attempt}`);
  return request;
}

/** Strict UTF-8, duplicate-key/depth/field/byte bounded private IPC parser. */
function strictJSON(raw,limit=MAX_JSON,maxFields=256,maxString=8192,maxArray=256) {
 try {
  require(Buffer.isBuffer(raw) && raw.length>=1 && raw.length<=limit);
  const text=new TextDecoder('utf-8',{fatal:true}).decode(raw);let i=0,fields=0;
  const ws=()=>{while(/[ \t\r\n]/.test(text[i]??'!'))i++;};
  function string() {
   const start=i;require(text[i++]==='"');
   while(i<text.length){const ch=text[i++];if(ch==='"'){const s=JSON.parse(text.slice(start,i));require(Buffer.byteLength(s)<=maxString);return s;}if(ch==='\\'){i++;}}
   throw Error(INVALID);
  }
  function value(depth) {
   require(depth<=32);ws();const ch=text[i];
   if(ch==='"')return string();
   if(ch==='{') {i++;const result=Object.create(null),seen=new Set();ws();if(text[i]==='}'){i++;return result;}
    while(true){ws();const key=string();require(!seen.has(key) && ++fields<=maxFields);seen.add(key);ws();require(text[i++]===':');result[key]=value(depth+1);ws();const end=text[i++];if(end==='}')return result;require(end===',');}
   }
   if(ch==='['){i++;const result=[];ws();if(text[i]===']'){i++;return result;}while(true){require(result.length<maxArray);result.push(value(depth+1));ws();const end=text[i++];if(end===']')return result;require(end===',');}}
   const match=/^(?:true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/.exec(text.slice(i));require(match);i+=match[0].length;const scalar=JSON.parse(match[0]);require(typeof scalar!=='number'||Number.isFinite(scalar));return scalar;
  }
  const result=value(0);ws();require(i===text.length);
  // Return plain JSON objects only after duplicate detection and exact validation.
  return JSON.parse(JSON.stringify(result));
 } catch {throw Error(INVALID);}
}
export function parseUploadRequest(raw) {return validateRequest(strictJSON(raw));}

// Private cooperative inspection ownership. Racing a waiter is insufficient:
// outstanding filesystem work must settle/close within the original reserve.
const inspections=new WeakSet();
function inspectionScope(remaining,signal,reserve) {
 const end=performance.now()+Math.max(0,Math.min(30000,remaining())),controller=new AbortController();
 const handles=new Set();
 let failure,notify;const cancelled=new Promise(resolve=>{notify=resolve;});
 // Closure failure is sticky, including when abort/timeout won the initial race.
 const cancel=reason=>{if(!failure || reason==='cleanup_failed'){failure=reason;controller.abort();notify(Error(reason));}};
 const check=()=>{
  if(!failure && signal?.aborted)cancel('operation_cancelled');
  if(!failure && (!(remaining()>0) || performance.now()>=end))cancel('operation_timed_out');
  if(!failure && signal?.aborted)cancel('operation_cancelled');
  if(failure)throw Error(failure);
 };
 const abort=()=>cancel('operation_cancelled');signal?.addEventListener('abort',abort,{once:true});
 const timer=setInterval(()=>{try{check();}catch{}},10);
 const scope={signal:controller.signal,check,
  acquire(handle){handles.add(handle);},
  async close(handle){
   try{await handle.close();handles.delete(handle);}
   catch{cancel('cleanup_failed');throw Error('cleanup_failed');}
  },
  async step(operation){check();const result=await operation();check();return result;},
  hash(bytes){const digest=createHash('sha256');for(let i=0;i<bytes.length;i+=1024*1024){check();digest.update(bytes.subarray(i,i+1024*1024));}check();return digest.digest('hex');},
  async run(operation){
   check();let settled=false;
   const task=Promise.resolve().then(()=>{check();return operation();}).then(result=>{check();if(handles.size)throw Error('cleanup_failed');return result;});
   task.then(()=>{settled=true;},()=>{settled=true;});
   try{return await Promise.race([task,cancelled.then(error=>{throw error;})]);}
   catch(error){
    const reason=failure??error?.message??INVALID;cancel(reason);
    if(!settled){
     const cleanupEnd=performance.now()+Math.max(0,Math.min(30000,reserve()));let cleanupTimer;
     try{
      const settledWithinReserve=await Promise.race([task.then(()=>true,()=>true),new Promise(resolve=>{
       const expired=()=>{if(!(reserve()>0) || performance.now()>=cleanupEnd)resolve(false);};
       cleanupTimer=setInterval(expired,10);expired();
      })]);
      if(!settledWithinReserve)throw Error('cleanup_failed');
     }finally{clearInterval(cleanupTimer);}
    }
    // Settlement alone says nothing about whether an acquired FD closed.
    if(failure==='cleanup_failed' || handles.size)throw Error('cleanup_failed');
    throw Error(reason);
   }
  },
  dispose(){clearInterval(timer);signal?.removeEventListener('abort',abort);}
 };
 inspections.add(scope);return scope;
}
function localInspection(){const start=performance.now();return inspectionScope(()=>30000-(performance.now()-start),undefined,()=>60000-(performance.now()-start));}
const unscoped={check(){},step:operation=>operation(),hash,acquire(){},async close(handle){try{await handle.close();}catch{throw Error('cleanup_failed');}}};
function sameFile(a,b) {return a.dev===b.dev && a.ino===b.ino && a.size===b.size && a.mode===b.mode && a.uid===b.uid && a.nlink===b.nlink && a.mtimeMs===b.mtimeMs && a.ctimeMs===b.ctimeMs;}
async function fixedRead(filename,max,expected,scope=unscoped) {
 const before=await scope.step(()=>lstat(filename));require(before.isFile() && before.nlink===1 && before.uid===process.getuid() && before.size<=max);
 if(expected)require(sameFile(before,expected));
 scope.check();const h=await open(filename,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
 scope.acquire(h);
 try {
  scope.check();const start=await scope.step(()=>h.stat());require(start.isFile() && sameFile(before,start));
  const buffer=Buffer.alloc(start.size+1);let offset=0;
  while(offset<buffer.length){const {bytesRead}=await scope.step(()=>h.read(buffer,offset,Math.min(1024*1024,buffer.length-offset),offset));if(!bytesRead)break;offset+=bytesRead;}
  require(offset===start.size && sameFile(start,await scope.step(()=>h.stat())) && sameFile(start,await scope.step(()=>lstat(filename))));
  return buffer.subarray(0,offset);
 }finally{await scope.close(h);}
}
function relativeName(name) {
 require(typeof name==='string' && Buffer.byteLength(name)<=1024 && name.length>0 && !/[\\\x00-\x20\x7f]/.test(name) && !name.startsWith('/'));
 const pieces=name.split('/');require(pieces.length<=32 && pieces.every(p=>p && p!=='.' && p!=='..'));return name;
}
/** Pure byte verifier; callers cannot turn a fixture result into loader authority. */
export async function verifyInstalledTree(root,manifestBytes,approvedHash,lockBytes) {
 const scope=localInspection();try{return await scope.run(()=>verifyTree(root,manifestBytes,approvedHash,lockBytes,scope));}finally{scope.dispose();}
}
async function verifyTree(root,manifestBytes,approvedHash,lockBytes,scope) {
 require(typeof root==='string' && path.isAbsolute(root) && path.normalize(root)===root && await scope.step(()=>realpath(root))===root);
 require(typeof approvedHash==='string' && SHA.test(approvedHash) && Buffer.isBuffer(manifestBytes) && scope.hash(manifestBytes)===approvedHash);
 const m=strictJSON(manifestBytes,8*1024*1024,400000,8192,50000);keys(m,['protocol_version','toolkit_lock_sha256','packages','files']);
 require(m.protocol_version===1 && Buffer.isBuffer(lockBytes) && lockBytes.length<=1024*1024 && m.toolkit_lock_sha256===scope.hash(lockBytes));
 const lock=strictJSON(lockBytes,1024*1024,100000,8192,50000);require(lock.packages && typeof lock.packages==='object');
 const wanted=Object.create(null);
 for(const [name,pkg] of Object.entries(lock.packages)){scope.check();
  if(!name)continue;relativeName(name);require(name.startsWith('node_modules/') && typeof pkg.version==='string' && typeof pkg.resolved==='string' && /^https:\/\/registry\.npmjs\.org\/[^?#]+$/.test(pkg.resolved) && typeof pkg.integrity==='string' && /^sha512-[A-Za-z0-9+/]+=*$/.test(pkg.integrity) && !pkg.hasInstallScript);
  wanted[name]={version:pkg.version,resolved:pkg.resolved,integrity:pkg.integrity};
 }
 require(canonical(m.packages)===canonical(wanted));
 require(Array.isArray(m.files) && m.files.length>=2 && m.files.length<=50000);
 const entries=new Map(),dirs=new Set(['']);let total=0,previous='';
 for(const f of m.files){scope.check();keys(f,['path','bytes','sha256','mode']);relativeName(f.path);require(f.path!=='installed-tree.json' && f.path>previous);previous=f.path;
  require(Number.isSafeInteger(f.bytes) && f.bytes>=0 && f.bytes<=64*1024*1024 && typeof f.sha256==='string' && SHA.test(f.sha256) && Number.isInteger(f.mode) && f.mode>=0 && f.mode<=0o777 && !(f.mode&0o222));
  total+=f.bytes;require(total<=1024*1024*1024);entries.set(f.path,f);
  const parts=f.path.split('/');parts.pop();while(parts.length){dirs.add(parts.join('/'));parts.pop();}
 }
 require(entries.has('package.json') && entries.has('package-lock.json'));
 const seen=new Set();
 async function walk(rel){
  const absolute=path.join(root,rel),s=await scope.step(()=>lstat(absolute));require(s.isDirectory() && !s.isSymbolicLink() && s.uid===process.getuid() && !(s.mode&0o222));
  for(const name of await scope.step(()=>readdir(absolute))){scope.check();
   const next=rel?rel+'/'+name:name;relativeName(next);const file=path.join(root,next),st=await scope.step(()=>lstat(file));
   if(next==='installed-tree.json'){require(st.isFile() && st.nlink===1 && st.uid===process.getuid() && !(st.mode&0o222));continue;}
   if(st.isDirectory()){require(dirs.has(next));await walk(next);continue;}
   const f=entries.get(next);require(f && st.isFile() && st.nlink===1 && st.uid===process.getuid() && (st.mode&0o7777)===f.mode && st.size===f.bytes);
   const bytes=await fixedRead(file,64*1024*1024,st,scope);require(scope.hash(bytes)===f.sha256);seen.add(next);
  }
 }
 await walk('');require(seen.size===entries.size);
 require(scope.hash(await fixedRead(path.join(root,'package-lock.json'),1024*1024,undefined,scope))===scope.hash(lockBytes));
 for(const [name,pkg] of Object.entries(wanted)){
  require(entries.has(name+'/package.json'));
  const installed=strictJSON(await fixedRead(path.join(root,name,'package.json'),1024*1024,undefined,scope),1024*1024,100000,8192,50000);
  require(installed.version===pkg.version && installed.name===(lock.packages[name].name??name.split('node_modules/').at(-1)));
 }
 scope.check();return true;
}
/** Mount flags are authoritative; chmod is not immutable-code evidence. */
export function verifyReadOnlyMount(root,text) {
 require(typeof root==='string' && path.isAbsolute(root) && typeof text==='string' && Buffer.byteLength(text)<=1024*1024);
 const unescape=s=>s.replace(/\\(040|011|012|134)/g,(_,n)=>String.fromCharCode(parseInt(n,8)));
 const mounts=text.trim().split('\n').map(line=>{const a=line.split(' ');require(a.length>=10 && a.includes('-'));return {at:unescape(a[4]),ro:a[5].split(',').includes('ro')};});
 const contains=(a,b)=>a==='/' || b===a || b.startsWith(a+'/');
 const covering=mounts.filter(m=>contains(m.at,root)).sort((a,b)=>b.at.length-a.at.length);
 require(covering.length && covering[0].ro && !mounts.some(m=>contains(root,m.at) && !m.ro));return true;
}
function serviceOrigin(raw) {
 require(typeof raw==='string' && raw.length<=8192 && !/[\x00-\x20\\]/.test(raw));
 const u=new URL(raw);require(u.protocol==='https:' && !u.username && !u.password && !u.search && !u.hash && !u.port && u.pathname==='/');
 require(/^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])$/.test(u.hostname) && !/^[0-9.]+$/.test(u.hostname) && u.hostname.includes('.'));
 require(raw===u.origin || raw===u.origin+'/');return u.origin;
}
function stamp(value) {
 require(typeof value==='string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value));
 const n=Date.parse(value);require(Number.isFinite(n) && new Date(n).toISOString()===value.replace('Z','.000Z'));return n;
}
function clock(deps) {const now=deps.now();require(now instanceof Date && Number.isFinite(now.getTime()));return now.toISOString().replace(/\.[0-9]{3}Z$/,'Z');}
async function privateArchive(cwd,request) {
 require(typeof cwd==='string' && path.isAbsolute(cwd) && path.normalize(cwd)===cwd && await realpath(cwd)===cwd);
 const parent=await lstat(cwd);require(parent.isDirectory() && !parent.isSymbolicLink() && (parent.mode&0o7777)===0o700 && parent.uid===process.getuid());
 const names=await readdir(cwd);require(names.length===1 && names[0]==='release.zip');
 const file=path.join(cwd,'release.zip'),before=await lstat(file);
 require(before.isFile() && before.nlink===1 && (before.mode&0o7777)===0o600 && before.uid===process.getuid() && before.size===request.archive_bytes);
 const result=await fixedRead(file,MAX_INNER,before);require(hash(result)===request.archive_sha256);return result;
}
async function bounded(operation,ms,signal,controller) {
 if(signal?.aborted)throw Error('operation_cancelled');
 if(!(ms>0))throw Error('operation_timed_out');
 let timer,onAbort;
 try {
  return await Promise.race([Promise.resolve().then(operation),new Promise((_,reject)=>{
   timer=setTimeout(()=>{controller?.abort();reject(Error('operation_timed_out'));},ms);
   onAbort=()=>{controller?.abort();reject(Error('operation_cancelled'));};
   if(signal?.aborted)onAbort();else signal?.addEventListener('abort',onAbort,{once:true});
  })]);
 } finally {clearTimeout(timer);signal?.removeEventListener('abort',onAbort);}
}

const SELF=fileURLToPath(import.meta.url);
const RUNTIME_KEYS=['ACTIONS_RUNTIME_TOKEN','ACTIONS_RESULTS_URL','GITHUB_REPOSITORY','GITHUB_REPOSITORY_ID','GITHUB_REPOSITORY_OWNER_ID','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_WORKFLOW_SHA','GITHUB_WORKFLOW_REF','ACTIONS_ID_TOKEN_REQUEST_URL','ACTIONS_ID_TOKEN_REQUEST_TOKEN','GITHUB_TOKEN'];
function groupExists(pid){try{process.kill(-pid,0);return true;}catch(e){if(e.code==='ESRCH')return false;throw Error('cleanup_failed');}}
/** The sole SDK-capable boundary. Every outcome waits for owned OS resources. */
async function ownedUpload(request,deps,remaining,cleanupRemaining) {
 const stop=new AbortController(),terminate=()=>stop.abort();
 process.on('SIGTERM',terminate);
 let scope;
 try{
  const signal=deps.signal?AbortSignal.any([deps.signal,stop.signal]):stop.signal;
  scope=inspectionScope(remaining,signal,cleanupRemaining);
  const selected=workers.get(deps.worker);
  if(!selected && typeof deps.spawn!=='function')throw Error('missing_dependency');
  if(selected){
   require(canonical(selected.context)===canonical(request.context));
   require(selected.policy.toolkit_lock_sha256===deps.policy.toolkit_lock_sha256 && canonical(selected.policy.runtime_origins)===canonical(deps.policy.runtime_origins));
   await loadOfficialToolkit(selected.context,selected.policy,scope);
  }
  return await ownedChild(request,deps,remaining,selected,scope,signal,cleanupRemaining);
 }finally{scope?.dispose();process.removeListener('SIGTERM',terminate);}
}
async function ownedChild(request,deps,remaining,selected,scope,signal,cleanupRemaining) {
 const executable=selected?.executable??process.execPath,helper=selected?.helper??SELF;
 const env={...Object.fromEntries(RUNTIME_KEYS.map(k=>[k,deps.runtime[k]])),NODE_OPTIONS:'--use-openssl-ca'};
 const input=Buffer.from(JSON.stringify({request,policy:selected?.policy??deps.policy}));require(input.length<=MAX_JSON);
 const spawn=deps.spawn??spawnProcess,args=[helper,'--internal-upload-worker'];
 const options={cwd:deps.cwd,env,shell:false,detached:true,stdio:['pipe','pipe','pipe','pipe']};
 // Observe queued cancellation/SIGTERM after the final asynchronous ready step.
 await scope.run(()=>new Promise(resolve=>setImmediate(()=>setTimeout(resolve,0))));
 scope.dispose();scope.check();
 const child=spawn(executable,args,options);
 require(child instanceof ChildProcess);
 if(!Number.isInteger(child.pid)){await new Promise(resolve=>{child.on('error',()=>{});child.once('close',resolve);});throw Error(INVALID);}
 require(child.pid>1 && child.stdio.length===4 && child.stdio.every(Boolean));
 const pid=child.pid,started=performance.now(),streams=child.stdio;
 return new Promise((resolve,reject)=>{
  let failure,closed=false,exitCode,exitSignal,settled=false,killAt,cleanupUntil,logs=0,resultSize=0;const chunks=[],logSizes=[0,0];
  const groupSignal=signal=>{try{process.kill(-pid,signal);}catch(e){if(e.code!=='ESRCH')failure='cleanup_failed';}};
  const stop=message=>{
   if(!failure){failure=message;cleanupUntil=performance.now()+Math.max(0,cleanupRemaining());killAt=performance.now()+2000;child.stdin.destroy();groupSignal('SIGTERM');}
  };
  const finish=()=>{
   if(settled)return;
   let exists;try{exists=groupExists(pid);}catch{stop('cleanup_failed');exists=true;}
   if(closed && streams.every(stream=>stream.destroyed) && !exists){
    settled=true;clearInterval(timer);signal?.removeEventListener('abort',abort);process.removeListener('SIGTERM',terminate);
    if(failure){reject(Error(failure));return;}
    try{require(exitCode===0 && exitSignal===null);const observation=strictJSON(Buffer.concat(chunks));
     require(observation && typeof observation==='object' && !Array.isArray(observation));
     const names=['id','size','digest'];if(Object.hasOwn(observation,'digestMismatch'))names.push('digestMismatch');keys(observation,names);
     resolve(observation);
    }catch{reject(Error(INVALID));}return;
   }
   if(failure && performance.now()>=cleanupUntil){
    settled=true;clearInterval(timer);signal?.removeEventListener('abort',abort);process.removeListener('SIGTERM',terminate);groupSignal('SIGKILL');for(const stream of streams)stream.destroy();reject(Error('cleanup_failed'));
   }
  };
  const abort=()=>stop('operation_cancelled'),terminate=()=>stop('operation_cancelled');
  const timer=setInterval(()=>{
   if(!failure && (remaining()<=0 || performance.now()-started>=300000))stop('operation_timed_out');
   if(failure && performance.now()>=killAt){groupSignal('SIGKILL');killAt=Infinity;}
   finish();
  },10);
  child.on('error',()=>{stop(INVALID);finish();});
  child.on('exit',(code,signal)=>{exitCode=code;exitSignal=signal;if(code!==0 || signal)stop(failure??INVALID);});
  child.on('close',()=>{closed=true;try{if(!failure && groupExists(pid))stop(INVALID);}catch{stop('cleanup_failed');}finish();});
  for(const [index,stream] of streams.entries()){
   stream.on('error',()=>{stop(INVALID);finish();});stream.on('close',finish);
   if(index===1 || index===2)stream.on('data',chunk=>{logs+=chunk.length;logSizes[index-1]+=chunk.length;if(logs>MAX_JSON || logSizes[index-1]>MAX_JSON)stop('output_limit_exceeded');});
   if(index===3)stream.on('data',chunk=>{resultSize+=chunk.length;if(resultSize>MAX_JSON)stop('output_limit_exceeded');else if(!failure)chunks.push(chunk);});
  }
  process.on('SIGTERM',terminate);signal?.addEventListener('abort',abort,{once:true});
  if(signal?.aborted)abort();
  if(!failure)child.stdin.end(input);
 });
}

/**
 * Injected OS-process contract, not an activated uploader. readback must use a
 * separate actions:read REST credential, returned immutable ID and original
 * outer bytes, then independently decode exactly release.zip. No extracted-file
 * SDK download or caller-provided UploadSession is accepted here. The SDK process is owned and reaped here. Separately trusted runtime-auth and
 * REST transports must honor AbortSignal and close their own resources in cleanup.
 */
async function uploadReleaseInternal(input,deps) {
 const request=validateRequest(parseUploadRequest(Buffer.from(JSON.stringify(input))));
 if(!deps?.policy)throw Error('missing_dependency');
 const p=deps.policy;keys(p,['runtime_origins','toolkit_lock_sha256','control_workflow_sha']);
 require(SHA.test(p.toolkit_lock_sha256) && p.control_workflow_sha===request.context.workflow_sha);
 require(Array.isArray(p.runtime_origins) && p.runtime_origins.length>=1 && p.runtime_origins.length<=8);
 for(const origin of p.runtime_origins)require(serviceOrigin(origin)===origin);
 for(const fn of ['authenticateRuntime','readback','cleanup','now','monotonic'])require(typeof deps[fn]==='function');
 if(typeof deps.spawn!=='function' && !workers.has(deps.worker))throw Error('missing_dependency');
 require(Number.isFinite(deps.deadline) && Number.isFinite(deps.monotonic()));
 if(deps.deadline-deps.monotonic()<=330000)throw Error('operation_timed_out');
 if(deps.signal?.aborted)throw Error('operation_cancelled');
 const env=deps.runtime,c=request.context;require(env && typeof env.ACTIONS_RUNTIME_TOKEN==='string' && env.ACTIONS_RUNTIME_TOKEN.length>=1 && env.ACTIONS_RUNTIME_TOKEN.length<=16384);
 const origin=serviceOrigin(env.ACTIONS_RESULTS_URL);require(p.runtime_origins.includes(origin));
 for(const [key,want] of Object.entries({GITHUB_REPOSITORY:c.repository,GITHUB_REPOSITORY_ID:c.repository_id,GITHUB_REPOSITORY_OWNER_ID:c.repository_owner_id,GITHUB_RUN_ID:c.run_id,GITHUB_RUN_ATTEMPT:String(c.run_attempt),GITHUB_WORKFLOW_SHA:c.workflow_sha,GITHUB_WORKFLOW_REF:c.workflow_ref}))require(env[key]===want);
 let bytes;
 const controller=new AbortController();let failure,result;
 const operationStart=performance.now(),operationDeadline=Math.min(deps.deadline-30000,deps.monotonic()+300000);
 const remaining=()=>Math.min(operationDeadline-deps.monotonic(),300000-(performance.now()-operationStart));
 let cleanupEnd;const cleanupRemaining=()=>{cleanupEnd??=performance.now()+30000;return Math.max(0,Math.min(cleanupEnd-performance.now(),deps.deadline-deps.monotonic()));};
 try {
  bytes=await bounded(()=>privateArchive(deps.cwd,request),Math.min(30000,remaining()),deps.signal,controller);
  const identity=await bounded(()=>deps.authenticateRuntime(env,c,{signal:controller.signal}),Math.min(30000,remaining()),deps.signal,controller);
  keys(identity,['repository_id','repository_owner_id','run_id','run_attempt','runtime_service_origin']);
  for(const k of ['repository_id','repository_owner_id','run_id','run_attempt'])require(identity[k]===c[k]);require(identity.runtime_service_origin===origin);
  const started=clock(deps);
  const uploadRequest={filename:'release.zip',archive_sha256:request.archive_sha256,archive_bytes:request.archive_bytes,artifact_name:request.artifact_name,overwrite:false,retention_days:7,compression_level:0,include_hidden_files:false,run_id:c.run_id,run_attempt:c.run_attempt};
  require(remaining()>0);
  const uploaded=await ownedUpload(request,deps,remaining,cleanupRemaining);
  require(uploaded && Number.isSafeInteger(uploaded.id) && uploaded.id>0 && typeof uploaded.digest==='string' && SHA.test(uploaded.digest));
  require(Number.isSafeInteger(uploaded.size) && uploaded.size>=1 && uploaded.size<=MAX_OUTER);
  if(Object.hasOwn(uploaded,'digestMismatch'))require(uploaded.digestMismatch===false);
  const id=String(uploaded.id),digest='sha256:'+uploaded.digest;
  require(remaining()>0);
  const read=await bounded(()=>deps.readback(id,{signal:controller.signal}),remaining(),deps.signal,controller);
  keys(read,['artifact_id','artifact_name','digest','outer_bytes','archive_bytes','metadata_sha256','created_at','expires_at','expired']);
  require(read.artifact_id===id && read.artifact_name===request.artifact_name && read.digest===digest && SHA.test(read.metadata_sha256));
  require(Buffer.isBuffer(read.outer_bytes) && read.outer_bytes.length===uploaded.size && read.outer_bytes.length>=1 && read.outer_bytes.length<=MAX_OUTER && 'sha256:'+hash(read.outer_bytes)===digest);
  require(Buffer.isBuffer(read.archive_bytes) && read.archive_bytes.equals(bytes));
  const now=stamp(clock(deps)),created=stamp(read.created_at),expiry=stamp(read.expires_at);
  require(read.expired===false && created<=now+60000 && now-created<=86400000 && expiry-now>=3600000 && expiry>created && expiry-created<=7*86400000+60000);
  const finished=clock(deps);require(stamp(finished)>=stamp(started));
  result={protocol_version:3,artifact_id:id,digest,digestMismatch:false,runtime_service_origin:origin,upload_request_sha256:hash(canonical(uploadRequest)),upload_started_at:started,upload_finished_at:finished,toolkit_lock_sha256:p.toolkit_lock_sha256,control_workflow_sha:c.workflow_sha,run_id:c.run_id,run_attempt:c.run_attempt};
  require(Buffer.byteLength(JSON.stringify(result))<=MAX_JSON);
 } catch(error) {failure=new Error(['operation_timed_out','operation_cancelled','output_limit_exceeded','cleanup_failed','missing_dependency',INVALID].includes(error?.message)?error.message:INVALID);}
 finally {controller.abort();try{await bounded(()=>deps.cleanup(),cleanupRemaining());}catch{failure=Error('cleanup_failed');}}
 if(failure)throw failure;return result;
}

export async function uploadRelease(input,deps) {
 try {return await uploadReleaseInternal(input,deps);}
 catch(error) {throw Error([INVALID,'missing_dependency','operation_cancelled','operation_timed_out','cleanup_failed','output_limit_exceeded'].includes(error?.message)?error.message:INVALID);}
}

/**
 * Fixed offline official-toolkit loader for a separately installed toolchain.
 * The caller must first authenticate the owner-signed activation/trust policy;
 * these hashes are selections from that policy, never authorization by themselves.
 * No npm install, fallback resolution, caller package path or runtime download.
 * Unresolved moderate audit findings and buffers license require independent
 * toolchain review before any policy is installed. Default CLI never calls this.
 */
const workers=new WeakMap();
export async function loadOfficialToolkit(context,policy,scope) {
 const own=!scope;scope??=localInspection();require(inspections.has(scope));
 try{return await scope.run(()=>loadToolkit(context,policy,scope));}finally{if(own)scope.dispose();}
}
async function loadToolkit(context,policy,scope) {
 if(!policy)throw Error('missing_dependency');
 try {
  keys(policy,['activation_sha256','toolchain_sha256','trust_policy_sha256','toolkit_lock_sha256','helper_sha256','control_workflow_sha','runtime_origins','dependency_review_sha256','toolkit_tree_sha256']);
  validateRequest({protocol_version:3,operation:'upload',context,archive_sha256:'0'.repeat(64),archive_bytes:1,artifact_name:`workshop-release-${context.source_sha}-run-${context.run_id}-attempt-${context.run_attempt}`});
  for(const field of ['activation_sha256','toolchain_sha256','trust_policy_sha256'])require(policy[field]===context[field]);
  for(const field of ['toolkit_lock_sha256','helper_sha256','dependency_review_sha256','toolkit_tree_sha256'])require(typeof policy[field]==='string' && SHA.test(policy[field]));
  require(policy.control_workflow_sha===context.workflow_sha);
  require(Array.isArray(policy.runtime_origins) && policy.runtime_origins.length>=1 && policy.runtime_origins.length<=8);
  for(const origin of policy.runtime_origins)require(serviceOrigin(origin)===origin);
  if(process.version!=='v22.23.4' || process.platform!=='linux' || process.arch!=='x64')throw Error('missing_dependency');
  const base=fileURLToPath(new URL('./publisher-toolkit/',import.meta.url));
  const lock=await fixedRead(path.join(base,'package-lock.json'),1024*1024,undefined,scope);require(lock.length<=1024*1024 && scope.hash(lock)===policy.toolkit_lock_sha256);
  require(scope.hash(await fixedRead(SELF,1024*1024,undefined,scope))===policy.helper_sha256);
  require(scope.hash(await fixedRead(process.execPath,128*1024*1024,undefined,scope))==='94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90');
  const manifest=strictJSON(await fixedRead(path.join(base,'package.json'),1024*1024,undefined,scope),1024*1024,100000);
  require(manifest.dependencies['@actions/artifact']==='6.3.1' && manifest.engines.node==='22.23.4');
  const locked=JSON.parse(lock).packages['node_modules/@actions/artifact'];
  require(locked.version==='6.3.1' && locked.integrity==='sha512-DBXgdB9T4yj2KSe0tFg+MTi9T5se+16bdrFQh+3Y6Nq1lZ3gYQk1BjHoTof+7Zf36bEAlfVMf+8ifRKeyGJugQ==');
  const tree=await fixedRead(path.join(base,'installed-tree.json'),8*1024*1024,undefined,scope);
  const mounts=await scope.step(()=>readFile('/proc/self/mountinfo',{encoding:'utf8',signal:scope.signal}));
  for(const immutable of [base.replace(/\/$/,''),SELF,process.execPath])verifyReadOnlyMount(immutable,mounts);
  await verifyTree(base.replace(/\/$/,''),tree,policy.toolkit_tree_sha256,lock,scope);
  // No SDK import in the parent. This opaque descriptor is not activation authority.
  scope.check();const descriptor=Object.freeze({});workers.set(descriptor,{context:structuredClone(context),policy:structuredClone(policy),executable:process.execPath,helper:fileURLToPath(import.meta.url)});return descriptor;
 } catch(error) {throw Error([INVALID,'operation_timed_out','operation_cancelled','cleanup_failed'].includes(error?.message)?error.message:'missing_dependency');}
}

/** Derive the worker selections exclusively from independently installed trust. */
async function liveToolkitPolicy(handle,context) {
 const trusted=installedLivePolicyClaims(handle),p=trusted.policy,a=trusted.adapter_policy;
 validateRequest({protocol_version:3,operation:'upload',context,archive_sha256:'0'.repeat(64),archive_bytes:1,artifact_name:`workshop-release-${context.source_sha}-run-${context.run_id}-attempt-${context.run_attempt}`});
 for(const name of ['repository','repository_id','repository_owner_id','workflow_ref','workflow_sha','protected_environment'])require(context[name]===p[name]);
 for(const name of ['activation_sha256','toolchain_sha256','trust_policy_sha256'])require(context[name]===a[name]);
 require(a.toolkit_lock_sha256===p.toolkit_lock_sha256 && p.runtime_origins.includes(a.runtime_service_origin) && canonical(a.approval_keys)===canonical(p.approval_keys));
 const reviewPath='/etc/autodata/publisher/dependency-review-v1.json';
 const reviewBytes=await fixedRead(reviewPath,65536);require(hash(reviewBytes)===p.dependency_review_sha256);
 const review=strictJSON(reviewBytes);keys(review,['protocol_version','toolkit_lock_sha256','audit_report_sha256','audit_findings','buffers_license_decision','reviewed_by','expires_at']);
 require(review.protocol_version===1 && review.toolkit_lock_sha256===p.toolkit_lock_sha256 && SHA.test(review.audit_report_sha256) && review.buffers_license_decision==='accepted' && a.approvers.includes(review.reviewed_by) && stamp(review.expires_at)>Date.now());
 require(Array.isArray(review.audit_findings) && review.audit_findings.length<=32);
 for(const finding of review.audit_findings){keys(finding,['id','decision']);require(typeof finding.id==='string' && finding.id.length>=1 && finding.id.length<=200 && finding.decision==='accepted');}
 verifyReadOnlyMount(reviewPath,await readFile('/proc/self/mountinfo','utf8'));
 return {activation_sha256:a.activation_sha256,toolchain_sha256:a.toolchain_sha256,trust_policy_sha256:a.trust_policy_sha256,toolkit_lock_sha256:p.toolkit_lock_sha256,helper_sha256:p.helper_sha256,control_workflow_sha:p.workflow_sha,runtime_origins:p.runtime_origins,dependency_review_sha256:p.dependency_review_sha256,toolkit_tree_sha256:p.toolkit_tree_sha256};
}
async function liveRead(handle,url,maximum=65536,kind='github',restToken) {
 const options={maximum};if(kind==='github')options.token=restToken;
 require(kind!=='github' || typeof options.token==='string');
 return installedServiceRequest(handle,kind,url,options);
}
function crc32(bytes) {let crc=0xffffffff;for(const byte of bytes){crc^=byte;for(let bit=0;bit<8;bit++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);}return (crc^0xffffffff)>>>0;}
function zipExtra(raw) {
 const result=new Map();let at=0;
 while(at<raw.length){require(at+4<=raw.length);const kind=raw.readUInt16LE(at),size=raw.readUInt16LE(at+2);at+=4;require([0x5455,0xa].includes(kind) && !result.has(kind) && at+size<=raw.length);const value=raw.subarray(at,at+size);at+=size;
 if(kind===0x5455){require(size>=1 && [1,3,5,7].includes(value[0]) && size===1+4*value[0].toString(2).replace(/0/g,'').length);result.set(kind,value.subarray(1,5));}
 else {require(size===32 && value.subarray(0,8).equals(Buffer.from('0000000001001800','hex')));result.set(kind,value.subarray(8));}}
 return result;
}
export function decodeActionsOuter(outer,expectedSha,expectedBytes) {
 try {
 require(typeof expectedSha==='string' && SHA.test(expectedSha) && Number.isInteger(expectedBytes) && expectedBytes>=1 && expectedBytes<=MAX_INNER);
 require(Buffer.isBuffer(outer) && outer.length>=98 && outer.length<=MAX_OUTER);
 const end=outer.length-22;require(outer.readUInt32LE(end)===0x06054b50 && outer.readUInt16LE(end+4)===0 && outer.readUInt16LE(end+6)===0 && outer.readUInt16LE(end+8)===1 && outer.readUInt16LE(end+10)===1 && outer.readUInt16LE(end+20)===0);
 const offset=outer.readUInt32LE(end+16),length=outer.readUInt32LE(end+12);require(offset+length===end && outer.readUInt32LE(offset)===0x02014b50);
 const made=outer.readUInt16LE(offset+4),needed=outer.readUInt16LE(offset+6),flags=outer.readUInt16LE(offset+8),method=outer.readUInt16LE(offset+10),packed=outer.readUInt32LE(offset+20),size=outer.readUInt32LE(offset+24),name=outer.readUInt16LE(offset+28),extra=outer.readUInt16LE(offset+30),comment=outer.readUInt16LE(offset+32),external=outer.readUInt32LE(offset+38);
 require(needed<=20 && (flags&~0x808)===0 && [0,8].includes(method) && size===expectedBytes && name===11 && comment===0 && outer.readUInt16LE(offset+34)===0 && length===46+name+extra && outer.subarray(offset+46,offset+57).toString()==='release.zip' && outer.readUInt32LE(offset+42)===0 && packed<=MAX_OUTER);
 require([0,3].includes(made>>>8) && !(external&0x18));if(made>>>8===3)require([0,0o100000].includes((external>>>16)&0o170000));
 const centralExtra=zipExtra(outer.subarray(offset+57,offset+length));
 require(outer.readUInt32LE(0)===0x04034b50 && outer.readUInt16LE(4)===needed && outer.readUInt16LE(6)===flags && outer.readUInt16LE(8)===method && outer.readUInt32LE(10)===outer.readUInt32LE(offset+12) && outer.readUInt16LE(26)===11 && outer.subarray(30,41).toString()==='release.zip');
 const localExtra=zipExtra(outer.subarray(41,41+outer.readUInt16LE(28)));for(const [kind,raw]of centralExtra)if(localExtra.has(kind))require(raw.equals(localExtra.get(kind)));
 const start=41+outer.readUInt16LE(28),finish=start+packed;require(finish<=offset);
 if(flags&8){const local=[outer.readUInt32LE(14),outer.readUInt32LE(18),outer.readUInt32LE(22)];require(local.every(n=>n===0)||(local[0]===outer.readUInt32LE(offset+16)&&local[1]===packed&&local[2]===size));const descriptor=outer.subarray(finish,offset);require([12,16].includes(descriptor.length));const at=descriptor.length===16?4:0;if(at)require(descriptor.readUInt32LE(0)===0x08074b50);require(descriptor.readUInt32LE(at)===outer.readUInt32LE(offset+16) && descriptor.readUInt32LE(at+4)===packed && descriptor.readUInt32LE(at+8)===size);}
 else require(finish===offset && outer.readUInt32LE(14)===outer.readUInt32LE(offset+16) && outer.readUInt32LE(18)===packed && outer.readUInt32LE(22)===size);
 let bytes;if(method===0)bytes=outer.subarray(start,finish);else {const inflated=inflateRawSync(outer.subarray(start,finish),{maxOutputLength:expectedBytes+1,info:true});require(inflated.engine.bytesWritten===packed);bytes=inflated.buffer;}
 require(bytes.length===expectedBytes && hash(bytes)===expectedSha && crc32(bytes)===outer.readUInt32LE(offset+16));return bytes;
 }catch{throw Error(INVALID);}
}
async function serviceWorker(request,runtime,policy,cwd) {
 const start=performance.now(),remaining=()=>120000-(performance.now()-start),cleanupRemaining=()=>150000-(performance.now()-start);
 const worker=await loadOfficialToolkit(request.context,policy),scope=localInspection();
 try {return await ownedChild(request,{runtime,cwd},remaining,workers.get(worker),scope,new AbortController().signal,cleanupRemaining);}
 finally {scope.dispose();}
}
export async function runRuntimeChallenge(handle,runtime,context) {
 try {installedLivePolicyClaims(handle);}catch {throw Error('missing_dependency');}
 const p=await liveToolkitPolicy(handle,context);
 const claims=await fetchInstalledGithubOidc(handle,{run_id:context.run_id,run_attempt:context.run_attempt},{ACTIONS_ID_TOKEN_REQUEST_URL:runtime.ACTIONS_ID_TOKEN_REQUEST_URL,ACTIONS_ID_TOKEN_REQUEST_TOKEN:runtime.ACTIONS_ID_TOKEN_REQUEST_TOKEN});
 const read=(url,maximum=65536,kind='github')=>liveRead(handle,url,maximum,kind,runtime.GITHUB_TOKEN);
 require(claims.run_id===context.run_id && Number(claims.run_attempt)===context.run_attempt);
 const origin=serviceOrigin(runtime.ACTIONS_RESULTS_URL);require(p.runtime_origins.includes(origin));
 const base='https://api.github.com/repos/lucronn/autodata/actions/',name=`workshop-runtime-probe-${context.run_id}-${context.run_attempt}`;
 const runResponse=await read(base+'runs/'+context.run_id+'/attempts/'+context.run_attempt);require(runResponse.status===200);
 const run=strictJSON(runResponse.bytes);require(run.id===Number(context.run_id) && run.run_attempt===context.run_attempt && run.head_sha===context.workflow_sha && run.status==='in_progress' && run.conclusion===null && run.repository.id===Number(context.repository_id) && run.repository.owner.id===Number(context.repository_owner_id));
 const before=await read(base+'runs/'+context.run_id+'/artifacts');require(before.status===200);
 const inventory=strictJSON(before.bytes);require(Number.isInteger(inventory.total_count) && inventory.total_count===inventory.artifacts.length && inventory.total_count<=30 && !inventory.artifacts.some(a=>a.name===name));
 const nonce=randomBytes(32),cwd=await mkdtemp('/tmp/autodata-runtime-probe-');let uploaded,deleted=false,failure,result;
 try {
  uploaded=await serviceWorker({protocol_version:3,operation:'probe-upload',context,nonce_base64:nonce.toString('base64')},runtime,p,cwd);
  require(Number.isSafeInteger(uploaded.id) && uploaded.id>0 && SHA.test(uploaded.digest));
  const metadataResponse=await read(base+'artifacts/'+uploaded.id);require(metadataResponse.status===200);
  const metadata=strictJSON(metadataResponse.bytes);require(metadata.id===uploaded.id && metadata.name===name && metadata.workflow_run.id===Number(context.run_id) && metadata.workflow_run.repository_id===Number(context.repository_id) && metadata.workflow_run.head_sha===context.workflow_sha && metadata.expired===false && metadata.digest==='sha256:'+uploaded.digest && metadata.size_in_bytes===uploaded.size && stamp(metadata.created_at)>=stamp(run.run_started_at)-60000 && stamp(metadata.created_at)<=Date.now()+60000);
  const redirect=await read(base+'artifacts/'+uploaded.id+'/zip',1024*1024);require(redirect.status===302 && typeof redirect.location==='string');
  const outer=await read(redirect.location,1024*1024,'storage');require(outer.status===200 && outer.bytes.length===uploaded.size && hash(outer.bytes)===uploaded.digest);require(decodeActionsOuter(outer.bytes,hash(nonce),nonce.length).equals(nonce));
  const removed=await serviceWorker({protocol_version:3,operation:'probe-delete',context,artifact_id:uploaded.id},runtime,p,cwd);require(removed.id===uploaded.id);deleted=true;
  const absent=await read(base+'artifacts/'+uploaded.id);require(absent.status===404);
  result={repository_id:context.repository_id,repository_owner_id:context.repository_owner_id,run_id:context.run_id,run_attempt:context.run_attempt,runtime_service_origin:origin};
 } catch(error) {failure=error;}
 finally {
  if(uploaded&&!deleted){try{const removed=await serviceWorker({protocol_version:3,operation:'probe-delete',context,artifact_id:uploaded.id},runtime,p,cwd);require(removed.id===uploaded.id);const absent=await read(base+'artifacts/'+uploaded.id);require(absent.status===404);}catch{failure=Error('cleanup_failed');}}
  await rm(cwd,{recursive:true,force:true});
 }
 if(failure)throw failure;return result;
}
async function readInput() {const chunks=[];let size=0;for await(const chunk of process.stdin){size+=chunk.length;require(size<=MAX_JSON);chunks.push(chunk);}return strictJSON(Buffer.concat(chunks));}
/** Constrain the official SDK transport before importing any package code. */
async function constrainSdkNetwork(handle) {
 const p=installedLivePolicyClaims(handle).policy,https=await import('node:https'),http=await import('node:http'),dns=await import('node:dns'),{syncBuiltinESMExports}=await import('node:module');
 const original=https.default.request;
 const request=(...args)=>{
  const first=args[0],provided=typeof args[1]==='object'&&args[1]!==null?args[1]:{},callback=typeof args.at(-1)==='function'?args.at(-1):undefined;
  const initial=typeof first==='string'||first instanceof URL?new URL(first):new URL(`https://${first.hostname??first.host}${first.path??'/'}`),options=typeof first==='object'&&!(first instanceof URL)?{...first,...provided}:{...provided};
  const hostname=options.hostname??options.host??initial.hostname,protocol=options.protocol??initial.protocol,port=options.port??initial.port;
  require(protocol==='https:' && (!port||Number(port)===443) && typeof hostname==='string' && !hostname.includes(':') && !initial.username && !initial.password);
  const origin='https://'+hostname;require([...p.runtime_origins,...p.storage_origins].includes(origin));
  require(options.rejectUnauthorized!==false && options.ca===undefined && options.checkServerIdentity===undefined && (options.servername===undefined||options.servername===hostname));
  if(!p.runtime_origins.includes(origin))for(const key of Object.keys(options.headers??{}))require(key.toLowerCase()!=='authorization');
  let addresses=[];
  const lookup=(host,lookupOptions,done)=>dns.lookup(host,{all:true,verbatim:true},(error,found)=>{
   if(error){done(Error('sdk_transport_failed'));return;}
   try{require(found.length>=1 && found.length<=32 && found.every(a=>isPublicServiceAddress(a.address)));addresses=found;done(null,lookupOptions.all?[found[0]]:found[0].address,found[0].family);}catch{done(Error('sdk_transport_failed'));}
  });
  const selected={...options,hostname,protocol:'https:',port:443,path:options.path??initial.pathname+initial.search,agent:false,lookup,rejectUnauthorized:true,maxHeaderSize:16384};
  delete selected.socketPath;delete selected.createConnection;delete selected.host;
  const result=original.call(https.default,selected,callback);
  result.setTimeout(30000,()=>result.destroy(Error('sdk_transport_failed')));
  result.on('socket',socket=>socket.once('secureConnect',()=>{if(!addresses.some(a=>a.address===socket.remoteAddress)||!isPublicServiceAddress(socket.remoteAddress))result.destroy(Error('sdk_transport_failed'));}));return result;
 };
 https.default.request=request;https.default.get=(...args)=>{const result=request(...args);result.end();return result;};
 http.default.request=()=>{throw Error('sdk_transport_failed');};http.default.get=http.default.request;syncBuiltinESMExports();
}
async function internalWorker(handle,input) {
 keys(input,['request','policy']);const request=input.request,context=request.context;
 const policy=await liveToolkitPolicy(handle,context);require(canonical(policy)===canonical(input.policy));
 await fetchInstalledGithubOidc(handle,{run_id:context.run_id,run_attempt:context.run_attempt},{ACTIONS_ID_TOKEN_REQUEST_URL:process.env.ACTIONS_ID_TOKEN_REQUEST_URL,ACTIONS_ID_TOKEN_REQUEST_TOKEN:process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN});
 await loadOfficialToolkit(context,policy);
 const runtime=Object.fromEntries(RUNTIME_KEYS.map(k=>[k,process.env[k]]));
 const probe=request.operation.startsWith('probe-'),deleting=request.operation==='release-delete';
 if(!probe)await authenticateActionsRuntime(handle,runtime,context);
 // The official SDK receives only its runtime capability after authentication.
 delete process.env.GITHUB_TOKEN;delete process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN;delete process.env.ACTIONS_ID_TOKEN_REQUEST_URL;
 await constrainSdkNetwork(handle);
 const {DefaultArtifactClient}=await import(new URL('./node_modules/@actions/artifact/lib/artifact.js',new URL('./publisher-toolkit/',import.meta.url)));
 const client=new DefaultArtifactClient();let result;
 if(probe||deleting){
  const name=probe?`workshop-runtime-probe-${context.run_id}-${context.run_attempt}`:`workshop-release-${context.source_sha}-run-${context.run_id}-attempt-${context.run_attempt}`;
  const found=await client.listArtifacts();require(found.artifacts.filter(a=>a.name===name).length===(request.operation==='probe-upload'?0:1));
  if(request.operation==='probe-upload'){
   keys(request,['protocol_version','operation','context','nonce_base64']);require(request.protocol_version===3 && /^[A-Za-z0-9+/]{43}=$/.test(request.nonce_base64));
   const nonce=Buffer.from(request.nonce_base64,'base64');require(nonce.length===32 && nonce.toString('base64')===request.nonce_base64);
   const cwd=await mkdtemp('/tmp/autodata-probe-worker-');try{const filename=path.join(cwd,'release.zip');await writeFile(filename,nonce,{mode:0o600,flag:'wx'});result=await client.uploadArtifact(name,[filename],cwd,{retentionDays:1,compressionLevel:0,overwrite:false,includeHiddenFiles:false});}finally{await rm(cwd,{recursive:true,force:true});}
  } else {
   keys(request,['protocol_version','operation','context','artifact_id']);require(request.protocol_version===3 && ['probe-delete','release-delete'].includes(request.operation));
   require(found.artifacts.find(a=>a.name===name).id===request.artifact_id);
   const removed=await client.deleteArtifact(name);require(removed.id===request.artifact_id);result={id:removed.id,size:0,digest:'0'.repeat(64)};
  }
 } else {
  validateRequest(request);await privateArchive(process.cwd(),request);
  result=await client.uploadArtifact(request.artifact_name,[path.join(process.cwd(),'release.zip')],process.cwd(),{retentionDays:7,compressionLevel:0,overwrite:false,includeHiddenFiles:false});
 }
 require(Number.isSafeInteger(result.id) && result.id>0 && Number.isSafeInteger(result.size) && typeof result.digest==='string' && SHA.test(result.digest));
 writeSync(3,JSON.stringify(result));
}
const CREDENTIAL_KEYS=['ACTIONS_ID_TOKEN_REQUEST_URL','ACTIONS_ID_TOKEN_REQUEST_TOKEN','ACTIONS_RUNTIME_TOKEN','ACTIONS_RESULTS_URL','GITHUB_TOKEN'];
function runtimeFromCredentials(credentials,context) {
 keys(credentials,CREDENTIAL_KEYS);
 // OIDC is already verified before this function accesses runtime capability.
 for(const name of CREDENTIAL_KEYS)require(typeof credentials[name]==='string' && credentials[name].length>=1 && credentials[name].length<=16384);
 return {...credentials,GITHUB_REPOSITORY:context.repository,GITHUB_REPOSITORY_ID:context.repository_id,GITHUB_REPOSITORY_OWNER_ID:context.repository_owner_id,GITHUB_RUN_ID:context.run_id,GITHUB_RUN_ATTEMPT:String(context.run_attempt),GITHUB_WORKFLOW_SHA:context.workflow_sha,GITHUB_WORKFLOW_REF:context.workflow_ref};
}
async function bridge(handle,mode,input) {
 const context=mode==='--installed-policy'?input:mode==='--authenticate-context'?input.context:input.request.context;
 if(mode==='--authenticate-context')keys(input,['context','credentials']);
 if(mode==='--upload-release')keys(input,['request','credentials']);
 const policy=await liveToolkitPolicy(handle,context),worker=await loadOfficialToolkit(context,policy);
 if(mode==='--installed-policy'){
  const trusted=installedLivePolicyClaims(handle);
  return {protocol_version:3,live_policy:trusted.policy,adapter_policy:trusted.adapter_policy};
 }
 const credentials=input.credentials;keys(credentials,CREDENTIAL_KEYS);
 const oidc={ACTIONS_ID_TOKEN_REQUEST_URL:credentials.ACTIONS_ID_TOKEN_REQUEST_URL,ACTIONS_ID_TOKEN_REQUEST_TOKEN:credentials.ACTIONS_ID_TOKEN_REQUEST_TOKEN};
 await fetchInstalledGithubOidc(handle,{run_id:context.run_id,run_attempt:context.run_attempt},oidc);
 const runtime=runtimeFromCredentials(credentials,context);
 if(mode==='--authenticate-context'){
  await authenticateActionsRuntime(handle,runtime,context);
  const signingIdentity=await fetchInstalledGithubOidc(handle,{run_id:context.run_id,run_attempt:context.run_attempt},oidc);
  await writeVerifiedSigstoreToken(handle,signingIdentity);
  return {protocol_version:3,context_sha256:hash(canonical(context)),status:'runtime_authenticated'};
 }
 const request=validateRequest(input.request),trusted=installedLivePolicyClaims(handle);let uploadedId;
 const read=(url,maximum=65536,kind='github')=>liveRead(handle,url,maximum,kind,runtime.GITHUB_TOKEN);
 try {
  return await uploadRelease(request,{worker,cwd:process.cwd(),runtime,policy:{runtime_origins:policy.runtime_origins,toolkit_lock_sha256:policy.toolkit_lock_sha256,control_workflow_sha:context.workflow_sha},deadline:performance.now()+600000,monotonic:()=>performance.now(),now:()=>new Date(),
   authenticateRuntime:()=>authenticateActionsRuntime(handle,runtime,context),
   async readback(id){
    uploadedId=Number(id);const metadataResponse=await read('https://api.github.com/repos/lucronn/autodata/actions/artifacts/'+id);require(metadataResponse.status===200);
    const metadata=strictJSON(metadataResponse.bytes);require(metadata.id===Number(id) && metadata.workflow_run.id===Number(context.run_id) && metadata.workflow_run.repository_id===Number(context.repository_id));
    const redirect=await read('https://api.github.com/repos/lucronn/autodata/actions/artifacts/'+id+'/zip',MAX_OUTER);require(redirect.status===302 && typeof redirect.location==='string');
    const outer=await read(redirect.location,MAX_OUTER,'storage');require(outer.status===200);
    const projection=Object.fromEntries(['id','name','expired','digest','size_in_bytes','created_at','expires_at','workflow_run'].map(k=>[k,metadata[k]]));
    return {artifact_id:id,artifact_name:metadata.name,digest:metadata.digest,outer_bytes:outer.bytes,archive_bytes:decodeActionsOuter(outer.bytes,request.archive_sha256,request.archive_bytes),metadata_sha256:hash(canonical(projection)),created_at:metadata.created_at,expires_at:metadata.expires_at,expired:metadata.expired};
   },async cleanup(){}});
 } catch(error) {
  if(uploadedId){try{const removed=await serviceWorker({protocol_version:3,operation:'release-delete',context,artifact_id:uploadedId},runtime,policy,process.cwd());require(removed.id===uploadedId);const absent=await read('https://api.github.com/repos/lucronn/autodata/actions/artifacts/'+uploadedId);require(absent.status===404);}catch{throw Error('cleanup_failed');}}
  throw error;
 }
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
 (async()=>{
  const handle=await loadInstalledLiveOwnerPolicy();
  require(process.argv.length===3 && ['--internal-upload-worker','--installed-policy','--authenticate-context','--upload-release'].includes(process.argv[2]));
  const input=await readInput();
  if(process.argv[2]==='--internal-upload-worker'){await internalWorker(handle,input);return;}
  const result=await bridge(handle,process.argv[2],input);process.stdout.write(canonical(result)+'\n');
 })().catch(()=>{process.stderr.write(JSON.stringify({status:'missing_dependency',message:'reviewed toolkit and staging activation required'})+'\n');process.exitCode=3;});
}
