/** Dormant Actions upload boundary. No default runtime package loading or activation.
 * The injected contract is deliberately unusable as evidence of live publication.
 * The reviewed candidate toolkit lock/runtime still requires a runtime-token authenticator, bounded
 * REST raw readback + ZIP decoder and activation gate are required to wire IPC.
 */
import {createHash} from 'node:crypto';
import {open, lstat, readdir, readFile, realpath} from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

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
export function parseUploadRequest(raw) {
 try {
  require(Buffer.isBuffer(raw) && raw.length>=1 && raw.length<=MAX_JSON);
  const text=new TextDecoder('utf-8',{fatal:true}).decode(raw);let i=0,fields=0;
  const ws=()=>{while(/[ \t\r\n]/.test(text[i]??'!'))i++;};
  function string() {
   const start=i;require(text[i++]==='"');
   while(i<text.length){const ch=text[i++];if(ch==='"'){const s=JSON.parse(text.slice(start,i));require(Buffer.byteLength(s)<=8192);return s;}if(ch==='\\'){i++;}}
   throw Error(INVALID);
  }
  function value(depth) {
   require(depth<=32);ws();const ch=text[i];
   if(ch==='"')return string();
   if(ch==='{') {i++;const result=Object.create(null),seen=new Set();ws();if(text[i]==='}'){i++;return result;}
    while(true){ws();const key=string();require(!seen.has(key) && ++fields<=256);seen.add(key);ws();require(text[i++]===':');result[key]=value(depth+1);ws();const end=text[i++];if(end==='}')return result;require(end===',');}
   }
   if(ch==='['){i++;const result=[];ws();if(text[i]===']'){i++;return result;}while(true){require(result.length<256);result.push(value(depth+1));ws();const end=text[i++];if(end===']')return result;require(end===',');}}
   const match=/^(?:true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/.exec(text.slice(i));require(match);i+=match[0].length;const scalar=JSON.parse(match[0]);require(typeof scalar!=='number'||Number.isFinite(scalar));return scalar;
  }
  const result=value(0);ws();require(i===text.length);validateRequest(result);
  // Return plain JSON objects only after duplicate detection and exact validation.
  return JSON.parse(JSON.stringify(result));
 } catch {throw Error(INVALID);}
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
 require(typeof cwd==='string' && path.isAbsolute(cwd) && path.normalize(cwd)===cwd);
 const parent=await lstat(cwd);require(parent.isDirectory() && !parent.isSymbolicLink() && (parent.mode&0o777)===0o700 && parent.uid===process.getuid());
 const names=await readdir(cwd);require(names.length===1 && names[0]==='release.zip');
 const handle=await open(path.join(cwd,'release.zip'),constants.O_RDONLY|constants.O_NOFOLLOW);
 try {const s=await handle.stat();require(s.isFile() && s.nlink===1 && (s.mode&0o777)===0o600 && s.uid===process.getuid() && s.size===request.archive_bytes);
  const bytes=Buffer.alloc(s.size+1);const {bytesRead}=await handle.read(bytes,0,bytes.length,0);require(bytesRead===s.size);const result=bytes.subarray(0,bytesRead);require(hash(result)===request.archive_sha256);return result;
 } finally {await handle.close();}
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

// SDK logs never share the private JSON IPC stream. This helper runs in one
// supervisor-owned private process; concurrent uploads in that process are denied.
let capturing=false;
async function capturedToolkit(operation) {
 if(capturing)throw Error(INVALID);
 capturing=true;
 const stdout=process.stdout.write,stderr=process.stderr.write;let total=0;
 const discard=(chunk,encoding,callback)=>{
  const length=Buffer.isBuffer(chunk)?chunk.length:Buffer.byteLength(chunk,typeof encoding==='string'?encoding:undefined);
  total+=length;
  if(total>MAX_JSON)throw Error('output_limit_exceeded');
  const done=typeof encoding==='function'?encoding:callback;if(typeof done==='function')queueMicrotask(done);
  return true;
 };
 process.stdout.write=discard;process.stderr.write=discard;
 try {return await operation();}
 finally {process.stdout.write=stdout;process.stderr.write=stderr;capturing=false;}
}

/**
 * Injected official-SDK contract, not an activated uploader. readback must use a
 * separate actions:read REST credential, returned immutable ID and original
 * outer bytes, then independently decode exactly release.zip. No extracted-file
 * SDK download or caller-provided UploadSession is accepted here. All injected
 * operations must honor AbortSignal and synchronously close/reap during cleanup.
 */
async function uploadReleaseInternal(input,deps) {
 const request=validateRequest(parseUploadRequest(Buffer.from(JSON.stringify(input))));
 if(!deps?.policy)throw Error('missing_dependency');
 const p=deps.policy;keys(p,['runtime_origins','toolkit_lock_sha256','control_workflow_sha']);
 require(SHA.test(p.toolkit_lock_sha256) && p.control_workflow_sha===request.context.workflow_sha);
 require(Array.isArray(p.runtime_origins) && p.runtime_origins.length>=1 && p.runtime_origins.length<=8);
 for(const origin of p.runtime_origins)require(serviceOrigin(origin)===origin);
 for(const fn of ['authenticateRuntime','readback','cleanup','now','monotonic'])require(typeof deps[fn]==='function');
 require(typeof deps.toolkit?.uploadArtifact==='function');
 require(Number.isFinite(deps.deadline) && Number.isFinite(deps.monotonic()));
 if(deps.deadline-deps.monotonic()<=330000)throw Error('operation_timed_out');
 if(deps.signal?.aborted)throw Error('operation_cancelled');
 const env=deps.runtime,c=request.context;require(env && typeof env.ACTIONS_RUNTIME_TOKEN==='string' && env.ACTIONS_RUNTIME_TOKEN.length>=1 && env.ACTIONS_RUNTIME_TOKEN.length<=16384);
 const origin=serviceOrigin(env.ACTIONS_RESULTS_URL);require(p.runtime_origins.includes(origin));
 for(const [key,want] of Object.entries({GITHUB_REPOSITORY:c.repository,GITHUB_REPOSITORY_ID:c.repository_id,GITHUB_REPOSITORY_OWNER_ID:c.repository_owner_id,GITHUB_RUN_ID:c.run_id,GITHUB_RUN_ATTEMPT:String(c.run_attempt),GITHUB_WORKFLOW_SHA:c.workflow_sha,GITHUB_WORKFLOW_REF:c.workflow_ref}))require(env[key]===want);
 const bytes=await privateArchive(deps.cwd,request);
 const controller=new AbortController();let failure,result;
 const remaining=()=>Math.min(300000,deps.deadline-deps.monotonic()-30000);
 try {
  const identity=await bounded(()=>deps.authenticateRuntime(env,c,{signal:controller.signal}),Math.min(30000,remaining()),deps.signal,controller);
  keys(identity,['repository_id','repository_owner_id','run_id','run_attempt','runtime_service_origin']);
  for(const k of ['repository_id','repository_owner_id','run_id','run_attempt'])require(identity[k]===c[k]);require(identity.runtime_service_origin===origin);
  const started=clock(deps);
  const uploadRequest={filename:'release.zip',archive_sha256:request.archive_sha256,archive_bytes:request.archive_bytes,artifact_name:request.artifact_name,overwrite:false,retention_days:7,compression_level:0,include_hidden_files:false,run_id:c.run_id,run_attempt:c.run_attempt};
  require(remaining()>0);
  const uploaded=await capturedToolkit(()=>bounded(()=>deps.toolkit.uploadArtifact(request.artifact_name,[path.join(deps.cwd,'release.zip')],deps.cwd,{compressionLevel:0,retentionDays:7,overwrite:false,includeHiddenFiles:false}),remaining(),deps.signal,controller));
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
 } catch(error) {failure=new Error(['operation_timed_out','operation_cancelled','output_limit_exceeded',INVALID].includes(error?.message)?error.message:INVALID);}
 finally {controller.abort();try{await bounded(()=>deps.cleanup(),30000);}catch{failure=Error('cleanup_failed');}}
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
export async function loadOfficialToolkit(context,policy) {
 if(!policy)throw Error('missing_dependency');
 try {
  keys(policy,['activation_sha256','toolchain_sha256','trust_policy_sha256','toolkit_lock_sha256','helper_sha256','control_workflow_sha','runtime_origins','dependency_review_sha256']);
  validateRequest({protocol_version:3,operation:'upload',context,archive_sha256:'0'.repeat(64),archive_bytes:1,artifact_name:`workshop-release-${context.source_sha}-run-${context.run_id}-attempt-${context.run_attempt}`});
  for(const field of ['activation_sha256','toolchain_sha256','trust_policy_sha256'])require(policy[field]===context[field]);
  for(const field of ['toolkit_lock_sha256','helper_sha256','dependency_review_sha256'])require(typeof policy[field]==='string' && SHA.test(policy[field]));
  require(policy.control_workflow_sha===context.workflow_sha);
  require(Array.isArray(policy.runtime_origins) && policy.runtime_origins.length>=1 && policy.runtime_origins.length<=8);
  for(const origin of policy.runtime_origins)require(serviceOrigin(origin)===origin);
  if(process.version!=='v22.23.4' || process.platform!=='linux' || process.arch!=='x64')throw Error('missing_dependency');
  const base=fileURLToPath(new URL('./publisher-toolkit/',import.meta.url));
  const lock=await readFile(path.join(base,'package-lock.json'));require(lock.length<=1024*1024 && hash(lock)===policy.toolkit_lock_sha256);
  require(hash(await readFile(fileURLToPath(import.meta.url)))===policy.helper_sha256);
  require(hash(await readFile(process.execPath))==='94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90');
  const manifest=JSON.parse(await readFile(path.join(base,'package.json')));
  require(manifest.dependencies['@actions/artifact']==='6.3.1' && manifest.engines.node==='22.23.4');
  const locked=JSON.parse(lock).packages['node_modules/@actions/artifact'];
  require(locked.version==='6.3.1' && locked.integrity==='sha512-DBXgdB9T4yj2KSe0tFg+MTi9T5se+16bdrFQh+3Y6Nq1lZ3gYQk1BjHoTof+7Zf36bEAlfVMf+8ifRKeyGJugQ==');
  // Runtime values come solely from this private worker's actual job environment.
  const env=process.env;require(typeof env.ACTIONS_RUNTIME_TOKEN==='string' && env.ACTIONS_RUNTIME_TOKEN.length>=1 && env.ACTIONS_RUNTIME_TOKEN.length<=16384);
  require(policy.runtime_origins.includes(serviceOrigin(env.ACTIONS_RESULTS_URL)));
  for(const [name,value] of Object.entries({GITHUB_REPOSITORY:context.repository,GITHUB_REPOSITORY_ID:context.repository_id,GITHUB_REPOSITORY_OWNER_ID:context.repository_owner_id,GITHUB_RUN_ID:context.run_id,GITHUB_RUN_ATTEMPT:String(context.run_attempt),GITHUB_WORKFLOW_SHA:context.workflow_sha,GITHUB_WORKFLOW_REF:context.workflow_ref}))require(env[name]===value);
  const packageDir=path.join(base,'node_modules/@actions/artifact');
  require(await realpath(packageDir)===packageDir);
  const installed=JSON.parse(await readFile(path.join(packageDir,'package.json')));require(installed.name==='@actions/artifact' && installed.version==='6.3.1' && installed.main==='lib/artifact.js');
  const entry=path.join(packageDir,'lib/artifact.js');require(await realpath(entry)===entry);
  const sdk=await import(pathToFileURL(entry).href);require(typeof sdk.DefaultArtifactClient==='function');
  const client=new sdk.DefaultArtifactClient();require(typeof client.uploadArtifact==='function');
  // Expose only upload. No list/latest, overwrite/delete, extraction or arbitrary
  // package-selected download channel can escape into the finalizer interface.
  return Object.freeze({uploadArtifact:async(name,files,root,options)=>{
   keys(options,['compressionLevel','retentionDays','overwrite','includeHiddenFiles']);
   require(options.compressionLevel===0 && options.retentionDays===7 && options.overwrite===false && options.includeHiddenFiles===false);
   require(name===`workshop-release-${context.source_sha}-run-${context.run_id}-attempt-${context.run_attempt}` && Array.isArray(files) && files.length===1 && files[0]===path.join(root,'release.zip'));
   // Do not pass invented options to the official API: overwrite is prohibited
   // by exposing no delete method, hidden input by the one fixed file check.
   return client.uploadArtifact(name,files,root,{compressionLevel:0,retentionDays:7});
  }});
 } catch(error) {throw Error(error?.message===INVALID?INVALID:'missing_dependency');}
}

// Separately installed activation and toolkit packages are absent. Never read
// stdin, env credentials or load a package in this default executable path.
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
 process.stderr.write(JSON.stringify({status:'missing_dependency',message:'reviewed toolkit and staging activation required'})+'\n');process.exitCode=3;
}
