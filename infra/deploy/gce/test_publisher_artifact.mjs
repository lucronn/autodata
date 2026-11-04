import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, writeFile, chmod, rm, symlink, link, mkdir, readFile, stat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync, spawn} from 'node:child_process';
const helper = await import('./publisher_artifact.mjs').catch(() => ({}));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const inner = Buffer.from('fixture inner archive, decoded by independently tested Python parser');
const outer = Buffer.from('original outer service archive');
const context = () => ({protocol_version:3,environment:'staging',repository:'lucronn/autodata',repository_id:'123',repository_owner_id:'456',run_id:'789',run_attempt:2,workflow_ref:'lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master',workflow_sha:'a'.repeat(40),source_sha:'b'.repeat(40),service_config_sha256:'c'.repeat(64),protected_environment:'workshop-staging-publish',activation_sha256:'d'.repeat(64),toolchain_sha256:'e'.repeat(64),trust_policy_sha256:'f'.repeat(64)});
const request = () => ({protocol_version:3,operation:'upload',context:context(),archive_sha256:sha(inner),archive_bytes:inner.length,artifact_name:`workshop-release-${'b'.repeat(40)}-run-789-attempt-2`});
async function fixture(t) {
  const cwd = await mkdtemp(path.join(tmpdir(),'workshop-artifact-'));
  await chmod(cwd,0o700);
  await writeFile(path.join(cwd,'release.zip'),inner,{mode:0o600});
  t.after(() => rm(cwd,{recursive:true,force:true}));
  const calls=[];
  const deps={cwd,policy:{runtime_origins:['https://results.example.invalid'],toolkit_lock_sha256:'1'.repeat(64),control_workflow_sha:'a'.repeat(40)},runtime:{ACTIONS_RESULTS_URL:'https://results.example.invalid/',ACTIONS_RUNTIME_TOKEN:'private-runtime-token',GITHUB_REPOSITORY:'lucronn/autodata',GITHUB_REPOSITORY_ID:'123',GITHUB_REPOSITORY_OWNER_ID:'456',GITHUB_RUN_ID:'789',GITHUB_RUN_ATTEMPT:'2',GITHUB_WORKFLOW_SHA:'a'.repeat(40),GITHUB_WORKFLOW_REF:context().workflow_ref},now:()=>new Date('2026-11-03T12:00:00Z'),monotonic:()=>1000,deadline:601000,signal:new AbortController().signal,
    authenticateRuntime:async()=>({repository_id:'123',repository_owner_id:'456',run_id:'789',run_attempt:2,runtime_service_origin:'https://results.example.invalid'}),
    toolkit:{uploadArtifact:async(...args)=>{calls.push(args);return {id:987,size:outer.length,digest:sha(outer)};}},
    readback:async(id,{signal})=>{assert.equal(id,'987');assert.ok(signal);return {artifact_id:'987',artifact_name:request().artifact_name,digest:'sha256:'+sha(outer),outer_bytes:outer,archive_bytes:inner,metadata_sha256:'2'.repeat(64),created_at:'2026-11-03T11:59:00Z',expires_at:'2026-11-10T11:59:00Z',expired:false};},
    cleanup:async()=>{calls.push('cleanup');},
  };
  return {cwd,deps,calls};
}
test('helper contract is implemented',()=>assert.equal(typeof helper.uploadRelease,'function'));
test('fixed single-file upload derives current session evidence and verifies original outer bytes',async t=>{
  const {cwd,deps,calls}=await fixture(t);
  const result=await helper.uploadRelease(request(),deps);
  assert.deepEqual(calls[0],[request().artifact_name,[path.join(cwd,'release.zip')],cwd,{compressionLevel:0,retentionDays:7,overwrite:false,includeHiddenFiles:false}]);
  assert.equal(result.artifact_id,'987');assert.equal(result.digest,'sha256:'+sha(outer));
  assert.notEqual(result.digest,'sha256:'+sha(inner));assert.equal(result.digestMismatch,false);
  assert.equal(result.run_attempt,2);assert.equal(result.run_id,'789');
  assert.equal(result.control_workflow_sha,'a'.repeat(40));assert.equal(result.toolkit_lock_sha256,'1'.repeat(64));
  assert.match(result.upload_request_sha256,/^[0-9a-f]{64}$/);assert.equal(calls.at(-1),'cleanup');
  assert.ok(!JSON.stringify(result).includes('private-runtime-token'));
});
for (const value of [true,0,'false',null]) test(`terminal SDK digestMismatch ${JSON.stringify(value)}`,async t=>{
  const {deps,calls}=await fixture(t);deps.toolkit.uploadArtifact=async()=>({id:987,size:outer.length,digest:sha(outer),digestMismatch:value});
  await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);assert.equal(calls.at(-1),'cleanup');
});
for(const result of [{id:987},{id:true,digest:sha(outer)},{id:0,digest:sha(outer)},{id:9007199254740992,digest:sha(outer)},{id:987,digest:'A'.repeat(64)},{id:987,digest:sha(inner)}]) test(`reject SDK ID/digest ${JSON.stringify(result)}`,async t=>{
  const {deps}=await fixture(t);deps.toolkit.uploadArtifact=async()=>({...result,size:outer.length});
  await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);
});
for(const patch of [{artifact_id:'986'},{artifact_name:'old-name'},{digest:'sha256:'+sha(inner)},{outer_bytes:Buffer.alloc(16*1024*1024+1)},{archive_bytes:Buffer.from('substitution')},{expired:true},{expired:0},{expires_at:'2026-11-03T12:30:00Z'},{created_at:'2026-11-01T12:00:00Z'},{created_at:'2026-11-03T12:01:01Z'}]) test(`reject readback drift ${Object.keys(patch)[0]}`,async t=>{
 const {deps}=await fixture(t);const read=deps.readback;deps.readback=async(...args)=>({...await read(...args),...patch});
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);
});
for(const key of ['run_id','run_attempt','repository_id','repository_owner_id','runtime_service_origin']) test(`reject authenticated runtime ${key} mismatch before upload`,async t=>{
 const {deps,calls}=await fixture(t);const authenticate=deps.authenticateRuntime;deps.authenticateRuntime=async()=>({...await authenticate(),[key]:'wrong'});
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);assert.ok(!Array.isArray(calls[0]));
});
for(const url of ['http://results.example.invalid/','https://results.example.invalid.evil/','https://user@results.example.invalid/','https://results.example.invalid:444/','https://results.example.invalid/?token=secret','https://127.0.0.1/']) test(`reject runtime URL ${url}`,async t=>{
 const {deps,calls}=await fixture(t);deps.runtime.ACTIONS_RESULTS_URL=url;
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);assert.equal(calls.length,0);
});
test('missing pin policy rejects before credential hook or toolkit',async t=>{
 const {deps,calls}=await fixture(t);delete deps.policy;deps.authenticateRuntime=()=>{assert.fail('credential hook');};
 await assert.rejects(helper.uploadRelease(request(),deps),/missing_dependency/);assert.equal(calls.length,0);
});
test('fixed cwd rejects extra file before credential hook',async t=>{
 const {deps,cwd}=await fixture(t);await writeFile(path.join(cwd,'token'), 'secret');deps.authenticateRuntime=()=>assert.fail('credential hook');
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);
});
for(const mode of ['symlink','hardlink','mode']) test(`reject private archive ${mode}`,async t=>{
 const {deps,cwd}=await fixture(t);const target=path.join(cwd,'release.zip');
 if(mode==='mode') await chmod(target,0o644);
 else {await rm(target);const elsewhere=path.join(tmpdir(),`artifact-${process.pid}-${mode}`);await writeFile(elsewhere,inner,{mode:0o600});t.after(()=>rm(elsewhere,{force:true}));await (mode==='symlink'?symlink:link)(elsewhere,target);}
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);
});
test('cancellation aborts in-flight upload and invokes bounded cleanup',async t=>{
 const {deps,calls}=await fixture(t);const ctrl=new AbortController();deps.signal=ctrl.signal;
 deps.toolkit.uploadArtifact=()=>new Promise(()=>{});setTimeout(()=>ctrl.abort(),10);
 await assert.rejects(helper.uploadRelease(request(),deps),/operation_cancelled/);assert.equal(calls.at(-1),'cleanup');
});
test('deadline preserves cleanup reserve before opening upload',async t=>{
 const {deps,calls}=await fixture(t);deps.deadline=31000;
 await assert.rejects(helper.uploadRelease(request(),deps),/operation_timed_out/);assert.equal(calls.length,0);
});
test('errors are fixed and cleanup failure cannot report success',async t=>{
 const {deps}=await fixture(t);deps.cleanup=async()=>{throw Error('secret-token');};
 await assert.rejects(helper.uploadRelease(request(),deps),e=>e.message==='cleanup_failed');
});
test('strict IPC rejects duplicate, unknown, invalid UTF8 and oversized JSON',()=>{
 for(const raw of [Buffer.from('{"a":1,"a":2}'),Buffer.from('{"__proto__":0}'),Buffer.from([0xff]),Buffer.alloc(65537,32),Buffer.from(JSON.stringify({...request(),token:'secret'})),Buffer.from(JSON.stringify(request()).replace('"protocol_version":3','"protocol_version":3,"protocol_version":3'))]) assert.throws(()=>helper.parseUploadRequest(raw),/invalid authenticated publication input/);
 assert.deepEqual(helper.parseUploadRequest(Buffer.from(JSON.stringify(request()))),request());
});
test('direct invocation stays blocked and emits only fixed redacted JSON',()=>{
 const p=spawnSync(process.execPath,['infra/deploy/gce/publisher_artifact.mjs'],{input:JSON.stringify(request()),encoding:'utf8',env:{}});
 assert.equal(p.status,3);assert.equal(p.stdout,'');assert.deepEqual(JSON.parse(p.stderr),{status:'missing_dependency',message:'reviewed toolkit and staging activation required'});
});

test('official loader cannot acquire ambient credentials or load a package without owner pins',async()=>{
 assert.equal(typeof helper.loadOfficialToolkit,'function');
 await assert.rejects(helper.loadOfficialToolkit(context()),/missing_dependency/);
 await assert.rejects(helper.loadOfficialToolkit(context(),{activation_sha256:'wrong'}),/invalid authenticated publication input/);
});

test('reviewed lock has only exact HTTPS integrity-pinned packages and no install scripts',async()=>{
 const {readFile}=await import('node:fs/promises');
 const manifest=JSON.parse(await readFile(new URL('./publisher-toolkit/package.json',import.meta.url)));
 const lock=JSON.parse(await readFile(new URL('./publisher-toolkit/package-lock.json',import.meta.url)));
 assert.equal(manifest.dependencies['@actions/artifact'],'6.3.1');
 assert.equal(manifest.engines.node,'22.23.4');
 assert.equal(lock.packages['node_modules/@actions/artifact'].integrity,'sha512-DBXgdB9T4yj2KSe0tFg+MTi9T5se+16bdrFQh+3Y6Nq1lZ3gYQk1BjHoTof+7Zf36bEAlfVMf+8ifRKeyGJugQ==');
 for(const [name,pkg] of Object.entries(lock.packages)) {
  if(!name)continue;
  assert.match(pkg.resolved,/^https:\/\/registry\.npmjs\.org\//);
  assert.match(pkg.integrity,/^sha512-[A-Za-z0-9+/]+=*$/);
  assert.ok(!pkg.hasInstallScript);
 }
});

test('toolkit stdout and stderr are discarded rather than entering private JSON IPC',async t=>{
 const {deps}=await fixture(t);
 deps.toolkit.uploadArtifact=async()=>{process.stdout.write('secret-runtime-token');process.stderr.write('signed-url?secret');return {id:987,size:outer.length,digest:sha(outer)};};
 const beforeOut=process.stdout.write,beforeErr=process.stderr.write,observed=[];
 const collector=chunk=>{observed.push(chunk);return true;};let result;
 process.stdout.write=collector;process.stderr.write=collector;
 try {result=await helper.uploadRelease(request(),deps);assert.equal(process.stdout.write,collector);assert.equal(process.stderr.write,collector);}
 finally {process.stdout.write=beforeOut;process.stderr.write=beforeErr;}
 assert.equal(result.artifact_id,'987');assert.deepEqual(observed,[]);
});
test('combined toolkit output limit rejects and still invokes cleanup',async t=>{
 const {deps,calls}=await fixture(t);
 deps.toolkit.uploadArtifact=async()=>{process.stdout.write(Buffer.alloc(40000));process.stderr.write(Buffer.alloc(30000));return {id:987,size:outer.length,digest:sha(outer)};};
 await assert.rejects(helper.uploadRelease(request(),deps),/output_limit_exceeded/);
 assert.equal(calls.at(-1),'cleanup');
});

for(const size of [undefined,true,0,outer.length+1]) test(`SDK size must equal measured raw archive bytes (${size})`,async t=>{
 const {deps}=await fixture(t);deps.toolkit.uploadArtifact=async()=>({id:987,digest:sha(outer),size});
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);
});

test('trusted clock with fractional milliseconds produces canonical second-resolution UTC evidence',async t=>{
 const {deps}=await fixture(t);deps.now=()=>new Date('2026-11-03T12:00:00.123Z');
 const result=await helper.uploadRelease(request(),deps);
 assert.equal(result.upload_started_at,'2026-11-03T12:00:00Z');
 assert.equal(result.upload_finished_at,'2026-11-03T12:00:00Z');
});

async function writableDirs(root,mode=0o755){await chmod(root,mode);for(const entry of await (await import('node:fs/promises')).readdir(root,{withFileTypes:true}))if(entry.isDirectory())await writableDirs(path.join(root,entry.name),mode);}
// The approved tree is recorded before tampering; installed bytes never approve themselves.
async function treeFixture(t) {
 const root=await mkdtemp(path.join(tmpdir(),'artifact-tree-'));t.after(async()=>{await writableDirs(root);await rm(root,{recursive:true,force:true});});
 const lock={packages:{'':{},'node_modules/@actions/artifact':{version:'6.3.1',resolved:'https://registry.npmjs.org/@actions/artifact/-/artifact-6.3.1.tgz',integrity:'sha512-YQ=='},'node_modules/transitive':{version:'1.0.0',resolved:'https://registry.npmjs.org/transitive/-/transitive-1.0.0.tgz',integrity:'sha512-Yg=='}}};
 const lockBytes=Buffer.from(JSON.stringify(lock)), contents={'package.json':'{}','package-lock.json':lockBytes,'node_modules/@actions/artifact/package.json':JSON.stringify({name:'@actions/artifact',version:'6.3.1',main:'lib/artifact.js'}),'node_modules/@actions/artifact/lib/artifact.js':'throw Error("must never import fixture");','node_modules/transitive/package.json':JSON.stringify({name:'transitive',version:'1.0.0'}),'node_modules/transitive/index.js':'original transitive bytes'};
 const files=[];
 for(const [name,value] of Object.entries(contents)){const target=path.join(root,name);await mkdir(path.dirname(target),{recursive:true});await writeFile(target,value,{mode:0o444});files.push({path:name,bytes:Buffer.byteLength(value),sha256:sha(value),mode:0o444});}
 const packages=Object.fromEntries(Object.entries(lock.packages).filter(([name])=>name));
 for(const dir of [root,path.join(root,'node_modules'),path.join(root,'node_modules/@actions'),path.join(root,'node_modules/@actions/artifact'),path.join(root,'node_modules/@actions/artifact/lib'),path.join(root,'node_modules/transitive')])await chmod(dir,0o555);
 const manifest=Buffer.from(JSON.stringify({protocol_version:1,toolkit_lock_sha256:sha(lockBytes),packages,files:files.sort((a,b)=>a.path.localeCompare(b.path,'en'))}));
 return {root,manifest,lockBytes,approved:sha(manifest)};
}
test('complete owner-selected installed tree accepts original bytes without importing',async t=>{
 const f=await treeFixture(t);await helper.verifyInstalledTree(f.root,f.manifest,f.approved,f.lockBytes);
});
for(const name of ['node_modules/@actions/artifact/lib/artifact.js','node_modules/transitive/index.js'])test(`metadata-preserving replacement rejects before import: ${name}`,async t=>{
 const f=await treeFixture(t);await chmod(path.join(f.root,name),0o644);await writeFile(path.join(f.root,name),'replacement executable');await chmod(path.join(f.root,name),0o444);
 await assert.rejects(helper.verifyInstalledTree(f.root,f.manifest,f.approved,f.lockBytes),/invalid authenticated publication input/);
});
for(const drift of ['writable-dir','extra','missing','symlink','hardlink','duplicate-key','duplicate-path','lock','approval','writable'])test(`installed tree rejects ${drift}`,async t=>{
 const f=await treeFixture(t),target=path.join(f.root,'node_modules/transitive/index.js');
 await writableDirs(f.root);
 if(drift==='writable-dir')await chmod(path.join(f.root,'node_modules'),0o755);
 if(drift==='extra'){await chmod(f.root,0o755);await writeFile(path.join(f.root,'extra'),'x');await chmod(f.root,0o555);}
 if(drift==='missing')await rm(target);
 if(drift==='symlink'){await rm(target);await symlink('package.json',target);}
 if(drift==='hardlink'){await rm(target);await link(path.join(f.root,'package.json'),target);}
 if(drift==='duplicate-key')f.manifest=Buffer.from(f.manifest.toString().replace('"protocol_version":1','"protocol_version":1,"protocol_version":1'));
 if(drift==='duplicate-path'){const m=JSON.parse(f.manifest);m.files.push(m.files[0]);f.manifest=Buffer.from(JSON.stringify(m));}
 if(drift==='lock')f.lockBytes=Buffer.from('{"packages":{}}');
 if(drift==='approval')f.approved='0'.repeat(64);
 if(drift==='writable')await chmod(target,0o644);
 if(['duplicate-key','duplicate-path'].includes(drift))f.approved=sha(f.manifest);
 await writableDirs(f.root,0o555);if(drift==='writable-dir')await chmod(path.join(f.root,'node_modules'),0o755);
 await assert.rejects(helper.verifyInstalledTree(f.root,f.manifest,f.approved,f.lockBytes),/invalid authenticated publication input/);
});
test('effective read-only mount rejects writable covers and nested mounts',()=>{
 const root='/toolkit';
 assert.equal(helper.verifyReadOnlyMount(root,'1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /toolkit ro - tmpfs tmpfs rw'),true);
 for(const text of ['1 0 0:1 / / rw - overlay overlay rw','1 0 0:1 / / ro - overlay overlay rw\n2 1 0:2 / /toolkit/node_modules rw - tmpfs tmpfs rw'])assert.throws(()=>helper.verifyReadOnlyMount(root,text),/invalid authenticated publication input/);
});
test('FIFO archive rejects promptly without credential hook and completes cleanup',async t=>{
 const {cwd}=await fixture(t);await rm(path.join(cwd,'release.zip'));assert.equal(spawnSync('mkfifo',['-m','600',path.join(cwd,'release.zip')]).status,0);
 const moduleUrl=new URL('./publisher_artifact.mjs',import.meta.url).href;
 const source=`import {uploadRelease} from ${JSON.stringify(moduleUrl)};const deps={cwd:${JSON.stringify(cwd)},policy:{runtime_origins:['https://results.example.invalid'],toolkit_lock_sha256:'1'.repeat(64),control_workflow_sha:'a'.repeat(40)},runtime:${JSON.stringify((await fixture(t)).deps.runtime)},now:()=>new Date(),monotonic:()=>1000,deadline:601000,authenticateRuntime:()=>{throw Error('credential hook reached')},readback:()=>{},cleanup:()=>{process.stdout.write('cleaned\\n')},toolkit:{uploadArtifact:()=>{}},spawn:()=>{throw Error('spawn reached')}};try{await uploadRelease(${JSON.stringify(request())},deps)}catch(e){process.stdout.write(e.message)}`;
 const result=spawnSync(process.execPath,['--input-type=module','-e',source],{encoding:'utf8',timeout:750});
 assert.equal(result.error,undefined,'FIFO must reject itself before watchdog');assert.equal(result.stdout,'cleaned\ninvalid authenticated publication input');
});
