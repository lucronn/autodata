import test from 'node:test';
import {fileURLToPath} from 'node:url';
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
    observation:{id:987,size:outer.length,digest:sha(outer)},
    spawn:(executable,args,options)=>{calls.push({executable,args,options});assert.equal(executable,process.execPath);assert.deepEqual(args,[new URL('./publisher_artifact.mjs',import.meta.url).pathname,'--internal-upload-worker']);assert.equal(options.shell,false);assert.equal(options.detached,true);assert.deepEqual(options.stdio,['pipe','pipe','pipe','pipe']);assert.equal(options.env.GITHUB_TOKEN,undefined);assert.equal(options.env.HTTP_PROXY,undefined);const source=`import {writeSync} from 'node:fs';let input='';for await(const data of process.stdin)input+=data;const envelope=JSON.parse(input);${deps.workerSource??''};writeSync(3,JSON.stringify(${JSON.stringify(deps.observation)}));`;const child=spawn(process.execPath,['--input-type=module','-e',source],options);deps.child=child;deps.onSpawn?.(child);return child;},
    readback:async(id,{signal})=>{assert.equal(id,'987');assert.ok(signal);assert.ok(deps.child.stdout.destroyed && deps.child.stderr.destroyed && deps.child.stdio[3].destroyed);assert.throws(()=>process.kill(-deps.child.pid,0),e=>e.code==='ESRCH');return {artifact_id:'987',artifact_name:request().artifact_name,digest:'sha256:'+sha(outer),outer_bytes:outer,archive_bytes:inner,metadata_sha256:'2'.repeat(64),created_at:'2026-11-03T11:59:00Z',expires_at:'2026-11-10T11:59:00Z',expired:false};},
    cleanup:async()=>{calls.push('cleanup');},
  };
  return {cwd,deps,calls};
}
test('helper contract is implemented',()=>assert.equal(typeof helper.uploadRelease,'function'));
test('fixed single-file upload derives current session evidence and verifies original outer bytes',async t=>{
  const {cwd,deps,calls}=await fixture(t);
  const result=await helper.uploadRelease(request(),deps);
  assert.equal(calls[0].options.cwd,cwd);assert.equal(calls[0].options.env.ACTIONS_RUNTIME_TOKEN,'private-runtime-token');
  assert.equal(result.artifact_id,'987');assert.equal(result.digest,'sha256:'+sha(outer));
  assert.notEqual(result.digest,'sha256:'+sha(inner));assert.equal(result.digestMismatch,false);
  assert.equal(result.run_attempt,2);assert.equal(result.run_id,'789');
  assert.equal(result.control_workflow_sha,'a'.repeat(40));assert.equal(result.toolkit_lock_sha256,'1'.repeat(64));
  assert.match(result.upload_request_sha256,/^[0-9a-f]{64}$/);assert.equal(calls.at(-1),'cleanup');
  assert.ok(!JSON.stringify(result).includes('private-runtime-token'));
});
for (const value of [true,0,'false',null]) test(`terminal SDK digestMismatch ${JSON.stringify(value)}`,async t=>{
  const {deps,calls}=await fixture(t);deps.observation={id:987,size:outer.length,digest:sha(outer),digestMismatch:value};
  await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);assert.equal(calls.at(-1),'cleanup');
});
for(const result of [{id:987},{id:true,digest:sha(outer)},{id:0,digest:sha(outer)},{id:9007199254740992,digest:sha(outer)},{id:987,digest:'A'.repeat(64)},{id:987,digest:sha(inner)}]) test(`reject SDK ID/digest ${JSON.stringify(result)}`,async t=>{
  const {deps}=await fixture(t);deps.observation={...result,size:outer.length};
  await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);
});
for(const patch of [{artifact_id:'986'},{artifact_name:'old-name'},{digest:'sha256:'+sha(inner)},{outer_bytes:Buffer.alloc(16*1024*1024+1)},{archive_bytes:Buffer.from('substitution')},{expired:true},{expired:0},{expires_at:'2026-11-03T12:30:00Z'},{created_at:'2026-11-01T12:00:00Z'},{created_at:'2026-11-03T12:01:01Z'}]) test(`reject readback drift ${Object.keys(patch)[0]}`,async t=>{
 const {deps}=await fixture(t);const read=deps.readback;deps.readback=async(...args)=>({...await read(...args),...patch});
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);
});
for(const key of ['run_id','run_attempt','repository_id','repository_owner_id','runtime_service_origin']) test(`reject authenticated runtime ${key} mismatch before upload`,async t=>{
 const {deps,calls}=await fixture(t);const authenticate=deps.authenticateRuntime;deps.authenticateRuntime=async()=>({...await authenticate(),[key]:'wrong'});
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);assert.deepEqual(calls,['cleanup']);
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
for(const mode of ['symlink','hardlink','mode','special-mode','directory','size']) test(`reject private archive ${mode}`,async t=>{
 const {deps,cwd}=await fixture(t);const target=path.join(cwd,'release.zip');
 if(mode==='mode') await chmod(target,0o644);
 else if(mode==='special-mode')await chmod(target,0o4600);
 else if(mode==='directory'){await rm(target);await mkdir(target);}
 else if(mode==='size')await writeFile(target,'different size');
 else {await rm(target);const elsewhere=path.join(tmpdir(),`artifact-${process.pid}-${mode}`);await writeFile(elsewhere,inner,{mode:0o600});t.after(()=>rm(elsewhere,{force:true}));await (mode==='symlink'?symlink:link)(elsewhere,target);}
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);
});
test('cancellation aborts in-flight upload and invokes bounded cleanup',async t=>{
 const {deps,calls}=await fixture(t);const ctrl=new AbortController();deps.signal=ctrl.signal;
 deps.workerSource="process.stdout.write('ready');await new Promise(()=>{});";deps.onSpawn=child=>child.stdout.once('data',()=>ctrl.abort());
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
 deps.workerSource="process.stdout.write('secret-runtime-token');process.stderr.write('signed-url?secret');";
 const beforeOut=process.stdout.write,beforeErr=process.stderr.write,observed=[];
 const collector=chunk=>{observed.push(chunk);return true;};let result;
 process.stdout.write=collector;process.stderr.write=collector;
 try {result=await helper.uploadRelease(request(),deps);assert.equal(process.stdout.write,collector);assert.equal(process.stderr.write,collector);}
 finally {process.stdout.write=beforeOut;process.stderr.write=beforeErr;}
 assert.equal(result.artifact_id,'987');assert.deepEqual(observed,[]);
});
test('combined toolkit output limit rejects and still invokes cleanup',async t=>{
 const {deps,calls}=await fixture(t);
 deps.workerSource="process.stdout.write(Buffer.alloc(40000));process.stderr.write(Buffer.alloc(30000));";
 await assert.rejects(helper.uploadRelease(request(),deps),/output_limit_exceeded/);
 assert.equal(calls.at(-1),'cleanup');
});

for(const size of [undefined,true,0,outer.length+1]) test(`SDK size must equal measured raw archive bytes (${size})`,async t=>{
 const {deps}=await fixture(t);deps.observation={id:987,digest:sha(outer),size};
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
for(const drift of ['writable-dir','extra-dir','special-mode','extra','missing','symlink','hardlink','duplicate-key','duplicate-path','lock','approval','writable'])test(`installed tree rejects ${drift}`,async t=>{
 const f=await treeFixture(t),target=path.join(f.root,'node_modules/transitive/index.js');
 await writableDirs(f.root);
 if(drift==='extra-dir')await mkdir(path.join(f.root,'unlisted'));
 if(drift==='special-mode')await chmod(target,0o4444);
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
 const source=`import {uploadRelease} from ${JSON.stringify(moduleUrl)};const deps={cwd:${JSON.stringify(cwd)},policy:{runtime_origins:['https://results.example.invalid'],toolkit_lock_sha256:'1'.repeat(64),control_workflow_sha:'a'.repeat(40)},runtime:${JSON.stringify((await fixture(t)).deps.runtime)},now:()=>new Date(),monotonic:()=>1000,deadline:601000,authenticateRuntime:()=>{process.stdout.write('AUTH_REACHED');throw Error('credential hook reached')},readback:()=>{},cleanup:()=>{process.stdout.write('cleaned\\n')},toolkit:{uploadArtifact:()=>{}},spawn:()=>{process.stdout.write('SPAWN_REACHED');throw Error('spawn reached')}};try{await uploadRelease(${JSON.stringify(request())},deps)}catch(e){process.stdout.write(e.message)}`;
 const result=spawnSync(process.execPath,['--input-type=module','-e',source],{encoding:'utf8',timeout:750});
 assert.equal(result.error,undefined,'FIFO must reject itself before watchdog');assert.equal(result.stdout,'cleaned\ninvalid authenticated publication input');
});

for(const failure of ['abort','deadline','overflow'])test(`real child ${failure} terminates before late output and completion marker`,async t=>{
 const {deps,cwd}=await fixture(t),marker=path.join(tmpdir(),`artifact-late-${process.pid}-${failure}`);t.after(()=>rm(marker,{force:true}));
 const ctrl=new AbortController();deps.signal=ctrl.signal;let child;
 deps.workerSource=`process.on('SIGTERM',()=>{});process.stdout.write('ready');setTimeout(()=>{process.stdout.write('late-private-secret');process.stderr.write('late-private-secret');writeSync((awaitImportFsPlaceholder), '');},3500);await new Promise(()=>{});`.replace("writeSync((awaitImportFsPlaceholder), '');",`(await import('node:fs')).writeFileSync(${JSON.stringify(marker)},'completed');`).replace('setTimeout(()=>{','setTimeout(async()=>{');
 deps.onSpawn=c=>{child=c;c.stdout.once('data',()=>{if(failure==='abort')ctrl.abort();if(failure==='deadline')deps.monotonic=()=>deps.deadline-30000;if(failure==='overflow')c.stdin.destroy();});};
 if(failure==='overflow')deps.workerSource="process.on('SIGTERM',()=>{});process.stdout.write(Buffer.alloc(65537));setTimeout(async()=>{(await import('node:fs')).writeFileSync("+JSON.stringify(marker)+",'completed')},3500);await new Promise(()=>{});";
 let reads=0;deps.readback=()=>{reads++;throw Error('must not readback');};
 const observed=[],out=process.stdout.write,err=process.stderr.write;process.stdout.write=chunk=>{observed.push(String(chunk));return true;};process.stderr.write=chunk=>{observed.push(String(chunk));return true;};
 const before=Date.now();try{await assert.rejects(helper.uploadRelease(request(),deps),new RegExp(failure==='abort'?'operation_cancelled':failure==='deadline'?'operation_timed_out':'output_limit_exceeded'));
 assert.ok(Date.now()-before<7000);assert.equal(reads,0);assert.throws(()=>process.kill(child.pid,0),e=>e.code==='ESRCH');assert.throws(()=>process.kill(-child.pid,0),e=>e.code==='ESRCH');
 await new Promise(resolve=>setTimeout(resolve,1800));await assert.rejects(stat(marker),e=>e.code==='ENOENT');}finally{process.stdout.write=out;process.stderr.write=err;}assert.deepEqual(observed,[]);
});
for(const mode of ['missing','duplicate','truncated','oversized','stderr','combined','nonzero','held-pipe'])test(`owned child rejects ${mode} and closes actual pipes`,async t=>{
 const {deps}=await fixture(t);let child;
 const sources={missing:'process.exit(0)',duplicate:'writeSync(3,JSON.stringify({id:987,size:30,digest:"'+sha(outer)+'"}));',truncated:'writeSync(3,"{");process.exit(0)',oversized:'writeSync(3,Buffer.alloc(65537));',stderr:'process.stderr.write(Buffer.alloc(65537));',combined:'process.stdout.write(Buffer.alloc(40000));process.stderr.write(Buffer.alloc(30000));',nonzero:'process.exit(1)',
 'held-pipe':`const {spawn}=await import('node:child_process');const descendant=spawn(process.execPath,['-e',"setInterval(()=>{},1000)"],{stdio:['ignore',1,2,3]});process.on('SIGTERM',()=>{descendant.kill('SIGTERM');descendant.once('exit',()=>process.exit(0));});writeSync(3,JSON.stringify({id:987,size:30,digest:'${sha(outer)}'}));process.stdout.write('ready');await new Promise(()=>{});`};
 deps.workerSource=sources[mode];const ctrl=new AbortController();deps.signal=ctrl.signal;
 deps.onSpawn=c=>{child=c;if(mode==='held-pipe')c.stdout.once('data',()=>ctrl.abort());};
 await assert.rejects(helper.uploadRelease(request(),deps),mode==='held-pipe'?/operation_cancelled/:mode==='oversized'||mode==='stderr'||mode==='combined'?/output_limit_exceeded/:/invalid authenticated publication input/);
 assert.ok(child.stdout.destroyed && child.stderr.destroyed && child.stdio[3].destroyed);assert.throws(()=>process.kill(-child.pid,0),e=>e.code==='ESRCH');
});
test('normal and explicit worker CLI modes remain denied without installed owner authority',()=>{
 for(const args of [['--unknown'],['--internal-upload-worker'],['--internal-upload-worker','anything']]){
  const p=spawnSync(process.execPath,['infra/deploy/gce/publisher_artifact.mjs',...args],{input:'untrusted owner policy',encoding:'utf8',env:{ACTIONS_RUNTIME_TOKEN:'do-not-read'}});assert.equal(p.status,3);assert.equal(p.stdout,'');assert.ok(!p.stderr.includes('do-not-read'));
 }
});

test('exhausted original cleanup deadline never accepts a result or claims cancellation proof',async t=>{
 const {deps}=await fixture(t);let child,now=1000;deps.monotonic=()=>now;const ctrl=new AbortController();deps.signal=ctrl.signal;
 deps.workerSource="process.on('SIGTERM',()=>{});process.stdout.write('ready');setInterval(()=>{},1000);await new Promise(()=>{});";
 deps.onSpawn=c=>{child=c;c.stdout.once('data',()=>{now=deps.deadline+1;ctrl.abort();});};
 deps.readback=()=>assert.fail('no evidence after cleanup timeout');
 await assert.rejects(helper.uploadRelease(request(),deps),/cleanup_failed/);
 // The failure may report missing proof; the test supervisor still reaps its fixture.
 if(child.exitCode===null && child.signalCode===null)await new Promise(resolve=>child.once('close',resolve));
 assert.throws(()=>process.kill(-child.pid,0),e=>e.code==='ESRCH');
});
test('failed actual OS spawn is redacted and cannot leave unhandled child events',async t=>{
 const {deps,calls}=await fixture(t);deps.spawn=(_exe,_args,options)=>spawn('/nonexistent-workshop-fixture-binary',[],options);
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);assert.equal(calls.at(-1),'cleanup');
});
test('default CLI does not inspect ambient runtime token or stdin even under explicit private pipes',()=>{
 const source=`Object.defineProperty(process,'env',{value:new Proxy({}, {get(_target,name){if(String(name).startsWith('ACTIONS_') || name==='GITHUB_TOKEN')throw Error('ambient credentials read');return undefined;}})});process.argv=[process.execPath,${JSON.stringify(new URL('./publisher_artifact.mjs',import.meta.url).pathname)},'--internal-upload-worker'];await import(${JSON.stringify(new URL('./publisher_artifact.mjs',import.meta.url).href)});`;
 const result=spawnSync(process.execPath,['--input-type=module','-e',source],{encoding:'utf8',stdio:['pipe','pipe','pipe','pipe'],input:'never parsed'});
 assert.equal(result.status,3);assert.equal(result.stdout,'');assert.ok(!result.stderr.includes('ambient credentials read'));
});

test('SIGTERM of containing process cancels and reaps SDK child before error returns',async t=>{
 const {deps,cwd}=await fixture(t);const pidFile=path.join(tmpdir(),`artifact-signal-${process.pid}.pid`);t.after(async()=>{try{const pid=Number(await readFile(pidFile,'utf8'));try{process.kill(-pid,'SIGKILL');}catch{}}catch{}await rm(pidFile,{force:true});});
 const source=`import {writeFileSync} from 'node:fs';import {spawn} from 'node:child_process';import {uploadRelease} from ${JSON.stringify(new URL('./publisher_artifact.mjs',import.meta.url).href)};const deps={cwd:${JSON.stringify(cwd)},policy:${JSON.stringify(deps.policy)},runtime:${JSON.stringify(deps.runtime)},now:()=>new Date('2026-11-03T12:00:00Z'),monotonic:()=>1000,deadline:601000,authenticateRuntime:async()=>({repository_id:'123',repository_owner_id:'456',run_id:'789',run_attempt:2,runtime_service_origin:'https://results.example.invalid'}),readback:()=>{throw Error('unexpected readback')},cleanup:()=>{},spawn:(_exe,_args,options)=>{const child=spawn(process.execPath,['-e',"process.stdin.resume();process.stdout.write('ready');setInterval(()=>{},1000)"],options);deps.child=child;writeFileSync(${JSON.stringify(pidFile)},String(child.pid));child.stdout.once('data',()=>process.kill(process.pid,'SIGTERM'));return child;}};try{await uploadRelease(${JSON.stringify(request())},deps)}catch(e){let absent=false;try{process.kill(-deps.child.pid,0)}catch(x){absent=x.code==='ESRCH'}process.stdout.write(JSON.stringify({error:e.message,absent,closed:deps.child.stdout.destroyed&&deps.child.stderr.destroyed&&deps.child.stdio[3].destroyed}));}`;
 const result=spawnSync(process.execPath,['--input-type=module','-e',source],{encoding:'utf8',timeout:7000});
 assert.equal(result.error,undefined);assert.equal(result.signal,null);assert.deepEqual(JSON.parse(result.stdout),{error:'operation_cancelled',absent:true,closed:true});
});

test('FIFO swapped after lstat cannot block the actual open descriptor',async t=>{
 const {cwd,deps}=await fixture(t),target=path.join(cwd,'release.zip');
 const source=`import fs from 'node:fs/promises';import {spawnSync} from 'node:child_process';import {syncBuiltinESMExports} from 'node:module';const original=fs.lstat;let hits=0;fs.lstat=async(filename,...rest)=>{const result=await original(filename,...rest);if(filename===${JSON.stringify(target)} && ++hits===2){await fs.unlink(filename);if(spawnSync('mkfifo',['-m','600',filename]).status!==0)throw Error('fixture failure');}return result;};syncBuiltinESMExports();const {uploadRelease}=await import(${JSON.stringify(new URL('./publisher_artifact.mjs',import.meta.url).href)});const deps={cwd:${JSON.stringify(cwd)},policy:${JSON.stringify(deps.policy)},runtime:${JSON.stringify(deps.runtime)},now:()=>new Date(),monotonic:()=>1000,deadline:601000,authenticateRuntime:()=>{process.stdout.write('AUTH_REACHED');throw Error('credential hook reached')},readback:()=>{},spawn:()=>{process.stdout.write('SPAWN_REACHED');throw Error('spawn reached')},cleanup:()=>{process.stdout.write('cleaned\\n')}};try{await uploadRelease(${JSON.stringify(request())},deps)}catch(e){process.stdout.write(e.message)}`;
 const result=spawnSync(process.execPath,['--input-type=module','-e',source],{encoding:'utf8',timeout:750});
 assert.equal(result.error,undefined,'replacement FIFO must not block open');assert.equal(result.stdout,'cleaned\ninvalid authenticated publication input');
});
test('valid result bytes before abort cannot start readback until child and pipes close',async t=>{
 const {deps}=await fixture(t),ctrl=new AbortController();deps.signal=ctrl.signal;
 deps.workerSource=`writeSync(3,JSON.stringify({id:987,size:${outer.length},digest:'${sha(outer)}'}));process.stdout.write('result-written');setInterval(()=>{},1000);await new Promise(()=>{});`;
 deps.onSpawn=child=>child.stdout.once('data',()=>ctrl.abort());deps.readback=()=>assert.fail('unclosed result must not start readback');
 await assert.rejects(helper.uploadRelease(request(),deps),/operation_cancelled/);assert.throws(()=>process.kill(-deps.child.pid,0),e=>e.code==='ESRCH');assert.ok(deps.child.stdio.every(stream=>stream.destroyed));
});

test('equal-depth writable overmount cannot be hidden by an earlier read-only mount',()=>{
 assert.throws(()=>helper.verifyReadOnlyMount('/toolkit','1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /toolkit ro - tmpfs tmpfs rw\n3 2 0:3 / /toolkit rw - tmpfs tmpfs rw'),/invalid authenticated publication input/);
});
test('private cwd cannot use a symlink ancestor before any credential call',async t=>{
 const {deps,cwd}=await fixture(t);const alias=path.join(tmpdir(),`artifact-alias-${process.pid}`);await symlink(path.dirname(cwd),alias);t.after(()=>rm(alias,{force:true}));deps.cwd=path.join(alias,path.basename(cwd));let credentials=0;deps.authenticateRuntime=()=>{credentials++;throw Error('credential hook');};
 await assert.rejects(helper.uploadRelease(request(),deps),/invalid authenticated publication input/);assert.equal(credentials,0);
});

// The copied helper selects a real opaque descriptor; mocked mount text is pure
// fixture evidence only, never an installed owner policy or immutable toolchain.
async function descriptorDeadlineProbe({mode,source,context:c,runtime}) {
 const fs=(await import('node:fs/promises')).default,{syncBuiltinESMExports}=await import('node:module'),{spawn}=await import('node:child_process'),path=await import('node:path'),{createHash}=await import('node:crypto');
 const {fstatSync}=await import('node:fs');
 const hash=b=>createHash('sha256').update(b).digest('hex');
 const root=await fs.mkdtemp('/tmp/artifact-deadline-contract-'),tree=path.join(root,'publisher-toolkit'),self=path.join(root,'publisher_artifact.mjs');
 await fs.mkdir(tree);await fs.copyFile(source,self);
 const packages={'node_modules/@actions/artifact':{version:'6.3.1',resolved:'https://registry.npmjs.org/@actions/artifact/-/artifact-6.3.1.tgz',integrity:'sha512-DBXgdB9T4yj2KSe0tFg+MTi9T5se+16bdrFQh+3Y6Nq1lZ3gYQk1BjHoTof+7Zf36bEAlfVMf+8ifRKeyGJugQ=='}};
 const lock=Buffer.from(JSON.stringify({packages:{'':{},...packages}}));
 const contents={'package.json':JSON.stringify({dependencies:{'@actions/artifact':'6.3.1'},engines:{node:'22.23.4'}}),'package-lock.json':lock,'node_modules/@actions/artifact/package.json':JSON.stringify({name:'@actions/artifact',version:'6.3.1'}),'node_modules/@actions/artifact/index.js':`throw Error('fixture must never import');`};
 const files=[];
 for(const [name,bytes] of Object.entries(contents)){const file=path.join(tree,name);await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file,bytes,{mode:0o444});files.push({path:name,bytes:Buffer.byteLength(bytes),sha256:hash(bytes),mode:0o444});}
 const manifest=Buffer.from(JSON.stringify({protocol_version:1,toolkit_lock_sha256:hash(lock),packages,files:files.sort((a,b)=>a.path<b.path?-1:1)}));await fs.writeFile(path.join(tree,'installed-tree.json'),manifest,{mode:0o444});
 async function dirs(file,mode){for(const e of await fs.readdir(file,{withFileTypes:true}))if(e.isDirectory())await dirs(path.join(file,e.name),mode);await fs.chmod(file,mode);}
 await dirs(tree,0o555);
 const originalRead=fs.readFile,originalOpen=fs.open,originalLstat=fs.lstat,ctrl=new AbortController(),deadline=601000;
 let now=1000,mountReads=0,opens=0,spawned=0,readbacks=0,cleanups=0,auth=0,transitioned=false,lateOperations=0,released=false,closedHandle=false,closedHandleAtReturn=false,returnedBeforeRelease=false;
 let heldHandle,heldFd,independentClose,observation;
 const fdOpen=()=>{if(heldFd===undefined)return null;try{fstatSync(heldFd);return true;}catch(e){if(e.code==='EBADF')return false;throw e;}};
 const mount='1 0 0:1 / / ro - overlay overlay ro';
 function transition(){transitioned=true;if(mode.includes('deadline'))now=301001;else if(mode==='pending-exhaustion')now=deadline+1;else if(mode.includes('sigterm'))process.kill(process.pid,'SIGTERM');else ctrl.abort();}
 fs.readFile=async(filename,...args)=>{
  if(filename==='/proc/self/mountinfo'){
   mountReads++;
   if(mountReads===2 && !mode.startsWith('final-') && mode!=='valid' && mode!=='pending-open' && !mode.startsWith('close-') && !mode.startsWith('closed-')){
    if(mode.startsWith('pending-'))return new Promise(resolve=>{setTimeout(transition,10);setTimeout(()=>{released=true;resolve(mount)},100);});
    transition();
   }
   return mount;
  }
  return originalRead(filename,...args);
 };
 fs.open=async(filename,...args)=>{
  if(transitioned)lateOperations++;
  const handle=await originalOpen(filename,...args);
  const target=mode==='close-archive'?path.join(root,'archive','release.zip'):path.join(tree,'package-lock.json');
  const selectedOpen=filename===path.join(tree,'package-lock.json') && ++opens===4;
  if(filename===target && (selectedOpen || mode==='close-archive') && (mode.startsWith('close-') || mode.startsWith('closed-'))){
   heldHandle=handle;heldFd=handle.fd;independentClose=handle.close.bind(handle);
   handle.close=async()=>{
    if(mode.startsWith('closed-') || mode==='close-after-success'){await independentClose();closedHandle=true;}
    if(!mode.startsWith('closed-'))throw Error('fixture close detail must be redacted');
   };
   if(['close-ordinary','close-after-success','close-archive'].includes(mode))handle.stat=async()=>{throw Error('fixture inspection failure');};
   else return new Promise(resolve=>{setTimeout(transition,10);setTimeout(()=>{released=true;resolve(handle)},100);});
  }
  if(selectedOpen && mode==='pending-open'){
   const close=handle.close.bind(handle);handle.close=async()=>{await close();closedHandle=true;};
   return new Promise(resolve=>{setTimeout(transition,10);setTimeout(()=>{released=true;resolve(handle)},100);});
  }
  return handle;
 };
 fs.lstat=async(...args)=>{if(transitioned)lateOperations++;return originalLstat(...args);};syncBuiltinESMExports();
 let child,error=null,result;
 try {
  const helper=await import(self),policy={activation_sha256:c.activation_sha256,toolchain_sha256:c.toolchain_sha256,trust_policy_sha256:c.trust_policy_sha256,toolkit_lock_sha256:hash(lock),helper_sha256:hash(await originalRead(self)),control_workflow_sha:c.workflow_sha,runtime_origins:['https://results.example.invalid'],dependency_review_sha256:'1'.repeat(64),toolkit_tree_sha256:hash(manifest)};
  const worker=await helper.loadOfficialToolkit(c,policy),cwd=path.join(root,'archive');await fs.mkdir(cwd,{mode:0o700});
  const inner=Buffer.from('descriptor fixture inner'),outer=Buffer.from('descriptor fixture original outer');await fs.writeFile(path.join(cwd,'release.zip'),inner,{mode:0o600});
  if(mode.startsWith('final-')){let reads=0;const token=runtime.ACTIONS_RUNTIME_TOKEN;Object.defineProperty(runtime,'ACTIONS_RUNTIME_TOKEN',{get(){if(++reads===4)transition();return token;}});}
  const request={protocol_version:3,operation:'upload',context:c,archive_sha256:hash(inner),archive_bytes:inner.length,artifact_name:`workshop-release-${c.source_sha}-run-${c.run_id}-attempt-${c.run_attempt}`};
  try{result=await helper.uploadRelease(request,{worker,cwd,policy:{runtime_origins:policy.runtime_origins,toolkit_lock_sha256:policy.toolkit_lock_sha256,control_workflow_sha:c.workflow_sha},runtime,deadline,monotonic:()=>now,now:()=>new Date('2026-11-03T12:00:00Z'),signal:ctrl.signal,
   authenticateRuntime:async()=>{auth++;return {repository_id:c.repository_id,repository_owner_id:c.repository_owner_id,run_id:c.run_id,run_attempt:c.run_attempt,runtime_service_origin:policy.runtime_origins[0]};},
   cleanup:async()=>{cleanups++;},
   readback:async()=>{readbacks++;return {artifact_id:'987',artifact_name:request.artifact_name,digest:'sha256:'+hash(outer),outer_bytes:outer,archive_bytes:inner,metadata_sha256:'2'.repeat(64),created_at:'2026-11-03T11:59:00Z',expires_at:'2026-11-10T11:59:00Z',expired:false};},
   spawn:(exe,_args,options)=>{spawned++;child=spawn(exe,['-e',`process.stdin.resume();require('node:fs').writeSync(3,${JSON.stringify(JSON.stringify({id:987,size:outer.length,digest:hash(outer)}))});`],options);return child;}
  });}catch(e){error=e.message;}
  closedHandleAtReturn=closedHandle;returnedBeforeRelease=!released;const fdOpenAtReturn=fdOpen();
  await new Promise(resolve=>setTimeout(resolve,150));
  observation={error,success:!!result,mountReads,spawned,readbacks,cleanups,auth,transitioned,lateOperations,released,closedHandle,closedHandleAtReturn,returnedBeforeRelease,fdOpenAtReturn};
 }finally{
  // Fixture cleanup is independent of the helper; never let a failed assertion
  // or rejected production close leak the actual file descriptor.
  if(heldHandle){if(heldHandle.fd>=0)await independentClose();if(observation)observation.fdOpenAfterFixtureCleanup=fdOpen();}
  fs.readFile=originalRead;fs.open=originalOpen;fs.lstat=originalLstat;syncBuiltinESMExports();
  if(child && child.exitCode===null && child.signalCode===null){try{process.kill(-child.pid,'SIGKILL')}catch{}await new Promise(resolve=>child.once('close',resolve));}
  await dirs(tree,0o755);await fs.rm(root,{recursive:true,force:true});
 }
 console.log(JSON.stringify(observation));
}
function runDescriptorProbe(mode,runtime){
 const source=`(${descriptorDeadlineProbe.toString()})(${JSON.stringify({mode,source:new URL('./publisher_artifact.mjs',import.meta.url).pathname,context:context(),runtime})})`;
 const result=spawnSync(process.execPath,['--input-type=module','-e',source],{encoding:'utf8',timeout:2500});
 assert.equal(result.error,undefined,'bounded descriptor probe must finish before its supervisor');assert.equal(result.signal,null);assert.equal(result.status,0,result.stderr);return JSON.parse(result.stdout);
}
for(const mode of ['deadline','abort','pending-deadline','pending-abort','pending-open','pending-exhaustion','final-deadline','final-abort','sigterm','final-sigterm'])test(`verified descriptor ${mode} prevents new spawn and readback`,async t=>{
 const {deps}=await fixture(t),r=runDescriptorProbe(mode,deps.runtime);
 assert.equal(r.transitioned,true);assert.equal(r.spawned,0);assert.equal(r.mountReads,mode==='pending-open'?1:2);assert.equal(r.readbacks,0);assert.equal(r.success,false);assert.equal(r.auth,1);
 assert.equal(r.error,mode==='pending-exhaustion'?'cleanup_failed':mode.includes('deadline')?'operation_timed_out':'operation_cancelled');
 assert.equal(r.lateOperations,0,'cancelled inspection cannot start another file operation');
 if(mode!=='pending-exhaustion')assert.equal(r.cleanups,1);
 if(mode==='pending-open')assert.equal(r.closedHandleAtReturn,true,'late acquired descriptor must close before return');
 if(mode.startsWith('pending-')){assert.equal(r.released,true);assert.equal(r.returnedBeforeRelease,mode==='pending-exhaustion');}
});
test('verified descriptor positive fixture retains fixed process and readback contract',async t=>{
 const {deps}=await fixture(t),r=runDescriptorProbe('valid',deps.runtime);assert.equal(r.error,null);assert.equal(r.success,true);assert.equal(r.mountReads,2);assert.equal(r.spawned,1);assert.equal(r.readbacks,1);assert.equal(r.cleanups,1);
});

// Removing close-failure ownership must expose a real still-open descriptor,
// never downgrade the public error to cancellation/timeout or loader redaction.
for(const [mode,want,openAtReturn] of [
 ['close-abort','cleanup_failed',true],
 ['close-deadline','cleanup_failed',true],
 ['close-ordinary','cleanup_failed',true],
 ['close-after-success','cleanup_failed',false],
 ['close-archive','cleanup_failed',true],
 ['closed-abort','operation_cancelled',false],
 ['closed-deadline','operation_timed_out',false],
])test(`actual FD ${mode} preserves inspection cleanup outcome`,async t=>{
 const {deps}=await fixture(t),r=runDescriptorProbe(mode,deps.runtime);
 assert.equal(r.fdOpenAtReturn,openAtReturn,'observe the actual captured FD before independent fixture cleanup');
 assert.equal(r.fdOpenAfterFixtureCleanup,false,'fixture must independently close its real descriptor');
 assert.equal(r.error,want);assert.equal(r.spawned,0);assert.equal(r.readbacks,0);assert.equal(r.success,false);assert.equal(r.cleanups,1);
 assert.equal(r.auth,mode==='close-archive'?0:1);
 assert.equal(r.lateOperations,0,'failed inspection must not start further file operations');
 if(mode.endsWith('abort') || mode.endsWith('deadline')){assert.equal(r.transitioned,true);assert.equal(r.released,true);assert.equal(r.returnedBeforeRelease,false);}
});

test('toolkit tree builder emits deterministic complete read-only byte inventory from real files',async t=>{
 const f=await treeFixture(t),builder=new URL('./publisher-toolkit/build_tree.mjs',import.meta.url);
 await writableDirs(f.root);
 const child=spawnSync(process.execPath,[fileURLToPath(builder)],{cwd:f.root,encoding:'utf8',timeout:10000});
 assert.equal(child.status,0,child.stderr);
 const manifest=await readFile(path.join(f.root,'installed-tree.json'));
 assert.equal(await helper.verifyInstalledTree(f.root,manifest,sha(manifest),f.lockBytes),true);
 await writableDirs(f.root);
 const again=spawnSync(process.execPath,[fileURLToPath(builder)],{cwd:f.root,encoding:'utf8',timeout:10000});
 assert.equal(again.status,0,again.stderr);assert.deepEqual(await readFile(path.join(f.root,'installed-tree.json')),manifest);
});

test('installed tree honors exact lock package name for npm aliases',async t=>{
 const f=await treeFixture(t);await writableDirs(f.root);
 const lock=JSON.parse(f.lockBytes);lock.packages['node_modules/transitive'].name='locked-alias-target';
 const lockBytes=Buffer.from(JSON.stringify(lock));
 const target='node_modules/transitive/package.json',installed=Buffer.from(JSON.stringify({name:'locked-alias-target',version:'1.0.0'}));
 for(const [name,raw] of [['package-lock.json',lockBytes],[target,installed]]){await chmod(path.join(f.root,name),0o644);await writeFile(path.join(f.root,name),raw);await chmod(path.join(f.root,name),0o444);}
 const m=JSON.parse(f.manifest);m.toolkit_lock_sha256=sha(lockBytes);
 for(const entry of m.files){if(entry.path==='package-lock.json'){entry.bytes=lockBytes.length;entry.sha256=sha(lockBytes);}if(entry.path===target){entry.bytes=installed.length;entry.sha256=sha(installed);}}
 const manifest=Buffer.from(JSON.stringify(m));await writableDirs(f.root,0o555);
 assert.equal(await helper.verifyInstalledTree(f.root,manifest,sha(manifest),lockBytes),true);
});
