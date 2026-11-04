/** Dormant Actions upload boundary. No default runtime package loading or activation.
 * The injected contract is deliberately unusable as evidence of live publication.
 * The reviewed candidate toolkit lock/runtime still requires a runtime-token authenticator, bounded
 * REST raw readback + ZIP decoder and activation gate are required to wire IPC.
 */
import {createHash} from 'node:crypto';
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
  require(installed.version===pkg.version && installed.name===name.split('node_modules/').at(-1));
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
const RUNTIME_KEYS=['ACTIONS_RUNTIME_TOKEN','ACTIONS_RESULTS_URL','GITHUB_REPOSITORY','GITHUB_REPOSITORY_ID','GITHUB_REPOSITORY_OWNER_ID','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_WORKFLOW_SHA','GITHUB_WORKFLOW_REF'];
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
 const env=Object.fromEntries(RUNTIME_KEYS.map(k=>[k,deps.runtime[k]]));
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

// Internal mode deliberately remains denied: no independently authenticated fixed
// owner trust source/signature format is provisioned. Private FDs/JSON/flags cannot
// self-authorize an official SDK import. A separate activation gate must supply it.
// Separately installed activation and toolkit packages are absent. Never read
// stdin, env credentials or load a package in this default executable path.
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
 process.stderr.write(JSON.stringify({status:'missing_dependency',message:'reviewed toolkit and staging activation required'})+'\n');process.exitCode=3;
}
