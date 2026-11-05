import test from 'node:test';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {generateKeyPairSync, createHash, sign} from 'node:crypto';
import {readFile, writeFile, mkdtemp, rm, open, link, unlink, symlink as symlinkFile, mkdir, chmod, lstat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
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
test('strict parser counts empty container depth and decoded duplicate names',()=>{
  invalid(()=>parseStrictJsonBytes(Buffer.from('['.repeat(17)+']'.repeat(17)),{maxBytes:1024}));
  for(const input of ['{"__proto__":1,"\\u005f_proto__":2}','{"a":"\\uD834"}','{"a":"\\uDD1E"}','+1','01','[NaN]','[Infinity]','true false','{"a":1,}','"line\nfeed"']) invalid(()=>parseStrictJsonBytes(Buffer.from(input),{maxBytes:1024}));
  const value=parseStrictJsonBytes(Buffer.from('{"__proto__":{"x":1},"unicode":"\\uD834\\uDD1E"}'),{maxBytes:1024});assert.equal(Object.getPrototypeOf(value),null);assert.equal(value.unicode,'𝄞');
  invalid(()=>parseStrictJsonBytes(Buffer.from(JSON.stringify('é'.repeat(4097))),{maxBytes:16384}));
});
test('a close settling after cleanup cutoff cannot change the original failure',async()=>{
  let resolveClose,closes=0;const scope=new OwnedTrustReadScope({budgetMs:5,cleanupReserveMs:5});
  await scope.trackOpen(Promise.resolve({close:()=>{closes++;return new Promise(resolve=>resolveClose=resolve);}}));
  await assert.rejects(scope.finish(),{message:'cleanup_failed'});resolveClose();await delay(10);
  await assert.rejects(scope.finish(),{message:'cleanup_failed'});assert.equal(closes,1);
});
test('missing fixed installation never reads environment token properties',async()=>{
  const original=process.env;let reads=0;
  process.env=new Proxy(original,{get(target,key){if(['ACTIONS_RUNTIME_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN','AUTODATA_PUBLISHER_POLICY'].includes(key)){reads++;throw Error('secret');}return Reflect.get(target,key);}});
  try {await assert.rejects(loadInstalledOwnerPolicy(),{message:'missing_dependency'});}finally{process.env=original;}
  assert.equal(reads,0);
});
test('invalid signal and option objects cannot leak underlying exceptions',async()=>{
  invalid(()=>new OwnedTrustReadScope({signal:Object.create(AbortSignal.prototype)}));
  invalid(()=>new OwnedTrustReadScope(new Proxy({},{get(){throw Error('secret');}})));
  await assert.rejects(loadInstalledOwnerPolicy(new Proxy({},{get(){throw Error('secret');}})),{message:'invalid_trust_input'});
});

// The copied production prefix is byte-for-byte identical. Appending passive
// exports grants tests no path selection seam or installed-policy authority.
async function withPolicyValidators(run) {
  const sourcePath=new URL('./publisher_policy.mjs',import.meta.url);
  const source=await readFile(sourcePath);
  const directory=await mkdtemp(tmpdir()+'/autodata-policy-validators-');
  const modulePath=directory+'/policy-copy.mjs';
  const suffix=Buffer.from('\nexport {validateStat,parseMounts,mountId,identity};\n');
  try {
    await writeFile(modulePath,Buffer.concat([source,suffix]),{mode:0o400});
    const copied=await readFile(modulePath);
    assert.deepEqual(copied.subarray(0,source.length),source);
    assert.deepEqual(copied.subarray(source.length),suffix);
    const module=await import(new URL(modulePath,'file:').href);
    await run({source,module,directory});
    assert.deepEqual(await readFile(sourcePath),source);
  } finally {await rm(directory,{recursive:true,force:true});}
}

test('exact-source test copy exposes only passive validators and preserves installed call sites',async()=>{
  await withPolicyValidators(async ({source,module})=>{
    assert.equal(module.validateStat.name,'validateStat');
    // These checks bind the exercised helpers to the production fixed-loader sites.
    const text=source.toString('utf8');
    for(const call of ['validateStat(stat,true)','validateStat(stat,false,bounds[i])','validateStat(after,i<4,bounds[i-4])','const mounts=parseMounts(raw)','mountId(await procBytes(',"mount.path.startsWith(trustDirectory+'/')",'requireValue(mount.readonly)','identity(after)===identity(nodes[i].stat)','identity(node.stat)===identity(nodes[i].stat)']) assert.ok(text.includes(call),call);
  });
});
test('rootless temporary filesystem metadata rejects owner, type, links, writable/special modes and size',async()=>{
  await withPolicyValidators(async ({module:{validateStat,identity},directory})=>{
    const file=directory+'/policy.json',hardlink=directory+'/hardlink.json',symlink=directory+'/symlink.json',subdirectory=directory+'/trust-directory';
    await writeFile(file,'{}',{mode:0o400});
    const handle=await open(file,'r');
    try {
      const stat=await handle.stat();
      assert.equal(stat.uid,process.getuid());
      if(stat.uid!==0)invalid(()=>validateStat(stat,false,16384));
      // Root ownership is projected only in fixture metadata to isolate the real
      // kernel type/link/mode/size observations on an unprivileged test host.
      const rootOwned=stat=>Object.assign(Object.create(stat),{uid:0});
      validateStat(rootOwned(stat),false,16384);
      invalid(()=>validateStat(rootOwned(stat),false,1));
      await link(file,hardlink);const linked=await handle.stat();invalid(()=>validateStat(rootOwned(linked),false,16384));
      await unlink(hardlink);
      for(const mode of [0o600,0o440,0o4444,0o2400,0o1400]) {await chmod(file,mode);const observed=await handle.stat();invalid(()=>validateStat(rootOwned(observed),false,16384));}
      await chmod(file,0o444);validateStat(rootOwned(await handle.stat()),false,16384);
      await symlinkFile(file,symlink);const linkStat=await lstat(symlink);assert.ok(linkStat.isSymbolicLink());invalid(()=>validateStat(rootOwned(linkStat),false,16384));
      await mkdir(subdirectory,{mode:0o755});let directoryStat=await lstat(subdirectory);validateStat(rootOwned(directoryStat),true);invalid(()=>validateStat(rootOwned(directoryStat),false,16384));
      for(const mode of [0o777,0o775,0o1755,0o2755,0o4755]) {await chmod(subdirectory,mode);directoryStat=await lstat(subdirectory);invalid(()=>validateStat(rootOwned(directoryStat),true));}
      await writeFile(directory+'/empty.json','',{mode:0o400});const empty=await lstat(directory+'/empty.json');invalid(()=>validateStat(rootOwned(empty),false,16384));
      await writeFile(directory+'/replacement.json','{}',{mode:0o400});const replacement=await lstat(directory+'/replacement.json');assert.notEqual(replacement.ino,stat.ino);assert.notEqual(identity(replacement),identity(stat));
      assert.equal(identity(stat),identity(Object.create(stat)));
      for(const field of ['dev','ino','mode','uid','gid','nlink','size'])assert.notEqual(identity(Object.assign(Object.create(stat),{[field]:stat[field]+1})),identity(stat));
      // Privileged/nonportable file states are fixture-only snapshots.
      const baseline=rootOwned(stat);
      for(const changes of [{uid:1},{mode:0o010400,isFile:()=>false},{size:16385},{size:NaN},{size:-1},{nlink:0}])invalid(()=>validateStat(Object.assign(Object.create(baseline),changes),false,16384));
    } finally {await handle.close();}
  });
});
test('fixture-only mount and fdinfo parsers retain RO/nested mount identity and reject ambiguity',async()=>{
  await withPolicyValidators(async ({module:{parseMounts,mountId}})=>{
    const line=(id,path,options='ro')=>`${id} 1 0:2 / ${path} ${options},relatime - ext4 /dev/fixture rw\n`;
    const raw=Buffer.from(line('1','/','rw')+line('42','/etc/autodata/publisher')+line('43','/etc/autodata/publisher/nested','rw'));
    const mounts=parseMounts(raw);
    assert.deepEqual(mounts.get('42'),{path:'/etc/autodata/publisher',readonly:true});
    assert.deepEqual(mounts.get('43'),{path:'/etc/autodata/publisher/nested',readonly:false});
    assert.equal(mounts.get('1').readonly,false);
    assert.equal(mountId(Buffer.from('pos:\t0\nflags:\t0100000\nmnt_id:\t42\nino:\t987654\n')),'42');
    assert.equal(mounts.has(mountId(Buffer.from('mnt_id:\t999\n'))),false);
    assert.notEqual(mountId(Buffer.from('mnt_id:\t42\n')),mountId(Buffer.from('mnt_id:\t43\n')));
    assert.equal(parseMounts(Buffer.from(line('44','/escaped\\040space\\134name'))).get('44').path,'/escaped space\\name');
    for(const text of [line('42','/a')+line('42','/b'),line('0','/a'),line('-1','/a'),line('2','relative'),line('2','/a','ro,rw'),line('2','/a','nosuid'),'not mountinfo\n',line('2','/a').replace(' - ',' ')])invalid(()=>parseMounts(Buffer.from(text)));
    invalid(()=>parseMounts(Buffer.from([0xc0,0xaf])));
    for(const text of ['','pos:\t0\n','mnt_id:\t0\n','mnt_id:\t-1\n','mnt_id:\t+42\n','mnt_id:\t42\nmnt_id:\t43\n','mnt_id:\t42\nmnt_id:\t42\n','mnt_id:\t42garbage\n'])invalid(()=>mountId(Buffer.from(text)));
    invalid(()=>mountId(Buffer.from([0xc0,0xaf])));
    // These are parser observations under supplied fixtures, never proof of a real immutable installation.
  });
});

function liveFixture(changes={},options={}) {
  const f=fixture();
  const adapter=options.adapter??bytes({registry:'us-central1-docker.pkg.dev/owner-project/releases'});
  const policy={...f.policy,protocol_version:2,purpose:'autodata.publisher.staging.live.v1',
    upload_enabled:true,runtime_bearer_authentication:'service-challenge-v1',
    adapter_policy_sha256:hash(adapter),toolchain_image_digest:'sha256:'+'1'.repeat(64),
    toolkit_lock_sha256:'2'.repeat(64),toolkit_tree_sha256:'3'.repeat(64),helper_sha256:'4'.repeat(64),
    dependency_review_sha256:'5'.repeat(64),wif_provider:'projects/123456/locations/global/workloadIdentityPools/staging-pool/providers/github-provider',publisher_service_account:'staging-publisher@test-project.iam.gserviceaccount.com',runtime_origins:['https://results.actions.githubusercontent.com'],
    storage_origins:['https://productionresultssa0.blob.core.windows.net'],
    approval_keys:{[hash(Buffer.from('independent-owner-key'))]:'independent-owner-key'},
    oidc:{...f.policy.oidc,audience:'sigstore'},...changes};
  const payload=bytes(policy),envelope=bytes({protocol_version:2,key_id:keyId,payload:payload.toString('base64'),
    signature:sign(null,Buffer.concat([Buffer.from(options.domain??'AutoData-Publisher-Owner-Policy-v2\0'),payload]),owner.privateKey).toString('base64')});
  const bootstrap=bytes({protocol_version:2,purpose:'autodata.publisher.bootstrap.live.v1',key_id:keyId,
    owner_public_key:rawOwner.toString('base64'),policy_sha256:hash(envelope),minimum_epoch:1});
  return {bootstrap,envelope,jwks:f.jwks,adapter,policy};
}
test('live policy uses separate signature domain, adapter bytes, purpose and immutable toolchain selection',async()=>{
  const module=await import('./publisher_policy.mjs');
  assert.equal(typeof module.verifyLiveOwnerPolicyBytes,'function');
  const f=liveFixture(),result=module.verifyLiveOwnerPolicyBytes(f.bootstrap,f.envelope,f.jwks,f.adapter,now);
  assert.equal(result.policy.protocol_version,2);assert.equal(result.policy.upload_enabled,true);
  assert.equal(result.policy.adapter_policy_sha256,hash(f.adapter));assert.ok(Object.isFrozen(result.policy.approval_keys));
  invalid(()=>installedPolicyClaims(result));
  invalid(()=>verify(f));
  invalid(()=>module.verifyLiveOwnerPolicyBytes(f.bootstrap,f.envelope,f.jwks,Buffer.concat([f.adapter,Buffer.from(' ')]),now));
  const wrong=liveFixture({}, {domain:'AutoData-Publisher-Owner-Policy-v1\0'});
  invalid(()=>module.verifyLiveOwnerPolicyBytes(wrong.bootstrap,wrong.envelope,wrong.jwks,wrong.adapter,now));
});
test('live policy rejects unresolved fields, insecure origins and passive policy substitution',async()=>{
  const {verifyLiveOwnerPolicyBytes}=await import('./publisher_policy.mjs');
  assert.equal(typeof verifyLiveOwnerPolicyBytes,'function');
  for(const changes of [{protocol_version:1},{purpose:'autodata.publisher.stage1a.offline'},{upload_enabled:false},
    {runtime_bearer_authentication:'unsupported'},{toolchain_image_digest:null},{toolchain_image_digest:'latest'},
    {wif_provider:null},{publisher_service_account:''},{wif_provider:'projects/0/locations/global/workloadIdentityPools/staging/providers/github'}, {adapter_policy_sha256:'0'.repeat(64)},{helper_sha256:null},{dependency_review_sha256:''},
    {runtime_origins:[]},{runtime_origins:['http://results.actions.githubusercontent.com']},
    {runtime_origins:['https://localhost']},{storage_origins:['https://storage.invalid/path']},{approval_keys:{}}]) {
    const f=liveFixture(changes);invalid(()=>verifyLiveOwnerPolicyBytes(f.bootstrap,f.envelope,f.jwks,f.adapter,now));
  }
});
test('installed live loader grants no authority from supplied bytes, path or passive handles',async()=>{
  const module=await import('./publisher_policy.mjs');
  assert.equal(typeof module.loadInstalledLiveOwnerPolicy,'function');
  assert.equal(typeof module.installedLivePolicyClaims,'function');
  await assert.rejects(module.loadInstalledLiveOwnerPolicy(),{message:'missing_dependency'});
  await assert.rejects(module.loadInstalledLiveOwnerPolicy({path:'/tmp/fixture'}),{message:'invalid_trust_input'});
  for(const value of [{},liveFixture(),{installed:true}]) invalid(()=>module.installedLivePolicyClaims(value));
});

// This test installs real root-owned trust on a read-only mount in a private
// mount namespace. It does not project fixture stat/mount data into the loader.
test('real installed live policy acquires private handle only from root-owned read-only trust',async t=>{
  const available=spawnSync('sudo',['-n','unshare','--mount','--propagation','private','true']);
  if(available.status!==0){assert.notEqual(process.env.AUTODATA_REQUIRE_ROOT_TRUST,'1','required mount namespace unavailable');t.skip('requires sudo mount namespace');return;}
  const current=Math.floor(Date.now()/1000),base=liveFixture();
  const f=liveFixture({issued_at:current-60,expires_at:current+600,
    oidc:{...base.policy.oidc,jwks_issued_at:current-100,jwks_expires_at:current+1000}});
  const directory=await mkdtemp(tmpdir()+'/autodata-live-install-');
  try {
    for(const [name,raw] of [['bootstrap-live-v1.json',f.bootstrap],['policy-live-v1.envelope.json',f.envelope],['github-oidc-jwks-live-v1.json',f.jwks],['adapter-policy-v2.json',f.adapter]])await writeFile(directory+'/'+name,raw,{mode:0o600});
    const certificate=spawnSync('/usr/bin/openssl',['req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=api.github.com','-addext','subjectAltName=DNS:api.github.com,DNS:oidc.actions.githubusercontent.com','-keyout',directory+'/tls.key','-out',directory+'/ca.pem'],{encoding:'utf8',timeout:10000,maxBuffer:65536});
    assert.equal(certificate.status,0,certificate.stderr);
    const script=`set -eu
/usr/sbin/ip link set lo up
/usr/sbin/ip addr add 8.8.8.8/32 dev lo
mount -t tmpfs -o mode=755 tmpfs /etc
mkdir -p /etc/autodata/publisher
printf "8.8.8.8 api.github.com oidc.actions.githubusercontent.com\\n" > /etc/hosts
for name in bootstrap-live-v1.json policy-live-v1.envelope.json github-oidc-jwks-live-v1.json adapter-policy-v2.json; do
  cp -- "$1/$name" "/etc/autodata/publisher/$name"
  chmod 444 "/etc/autodata/publisher/$name"
done
mount --bind /etc/autodata/publisher /etc/autodata/publisher
mount -o remount,bind,ro /etc/autodata/publisher
NODE_EXTRA_CA_CERTS="$1/ca.pem" exec "$2" --input-type=module -e "$3"
`;
    const claims={iss:f.policy.oidc.issuer,aud:f.policy.oidc.audience,sub:f.policy.oidc.subject,exp:current+240,iat:current-60,nbf:current-60,jti:'real-installed-test',repository:f.policy.repository,repository_id:f.policy.repository_id,repository_owner_id:f.policy.repository_owner_id,run_id:'123',run_attempt:'2',workflow_ref:f.policy.workflow_ref,workflow_sha:f.policy.workflow_sha,ref:f.policy.ref,sha:f.policy.workflow_sha,event_name:f.policy.event_name,environment:f.policy.protected_environment};
    const jwtInput=bytes({alg:'RS256',typ:'JWT',kid:'fixture-key'}).toString('base64url')+'.'+bytes(claims).toString('base64url');
    const token=jwtInput+'.'+sign('RSA-SHA256',Buffer.from(jwtInput),rsa.privateKey).toString('base64url');
    const program=`import {createServer} from 'node:https';
import {readFile} from 'node:fs/promises';
import {verifyInstalledLiveGithubOidc,fetchInstalledGithubOidc,installedServiceRequest,writeVerifiedSigstoreToken} from ${JSON.stringify(new URL('./publisher_identity.mjs',import.meta.url).href)};
import {loadInstalledLiveOwnerPolicy,installedLivePolicyClaims,installedPolicyClaims} from ${JSON.stringify(new URL('./publisher_policy.mjs',import.meta.url).href)};
const handle=await loadInstalledLiveOwnerPolicy();
const result=installedLivePolicyClaims(handle);
const identity=verifyInstalledLiveGithubOidc(Buffer.from(${JSON.stringify(token)}),handle,{run_id:'123',run_attempt:2});
if(identity.run_id!=='123')process.exit(5);
const server=createServer({key:await readFile(${JSON.stringify(directory+'/tls.key')}),cert:await readFile(${JSON.stringify(directory+'/ca.pem')})},(request,response)=>{
if(request.headers.authorization!=='Bearer owned-test-token'){response.writeHead(401);response.end();return;}
const raw=Buffer.from(JSON.stringify(request.url.startsWith('/_apis/')?{value:${JSON.stringify(token)}}:{authenticated:true}));response.setHeader('Content-Length',raw.length);response.end(raw);
});
await new Promise(resolve=>server.listen(443,'8.8.8.8',resolve));
try {
process.env.ACTIONS_ID_TOKEN_REQUEST_URL='https://oidc.actions.githubusercontent.com/_apis/distributedtask/hubs/build/plans/11111111-1111-1111-1111-111111111111/jobs/22222222-2222-2222-2222-222222222222/idtoken?api-version=2.0';
process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN='owned-test-token';
const fetched=await fetchInstalledGithubOidc(handle,{run_id:'123',run_attempt:2});if(fetched.jti!=='real-installed-test')process.exit(6);
const fs=await import('node:fs/promises'),original=process.cwd(),privateCwd=await fs.mkdtemp('/tmp/autodata-identity-file-');
try {process.chdir(privateCwd);await writeVerifiedSigstoreToken(handle,fetched);const file=await fs.lstat('identity-token');if((file.mode&0o7777)!==0o600 || file.nlink!==1 || (await fs.readFile('identity-token','utf8'))!==${JSON.stringify(token)})process.exit(8);
try{await writeVerifiedSigstoreToken(handle,fetched);process.exit(9);}catch{}
try{await writeVerifiedSigstoreToken(handle,{});process.exit(10);}catch{}
} finally {process.chdir(original);await fs.rm(privateCwd,{recursive:true,force:true});}

const response=await installedServiceRequest(handle,'github','https://api.github.com/repos/lucronn/autodata/actions/runs/123',{token:'owned-test-token'});
if(response.status!==200 || JSON.parse(response.bytes).authenticated!==true)process.exit(7);
} finally {server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}

if(result.policy.purpose!=='autodata.publisher.staging.live.v1')process.exit(2);
try {installedPolicyClaims(handle);process.exit(4);} catch {}
console.log('installed-live-policy-verified');`;
    const result=spawnSync('sudo',['-n','unshare','--mount','--net','--propagation','private','/bin/sh','-c',script,'trust-test',directory,process.execPath,program],{encoding:'utf8',timeout:15000,maxBuffer:65536});
    assert.equal(result.status,0,result.stderr);assert.equal(result.stdout,'installed-live-policy-verified\n');
  } finally {await rm(directory,{recursive:true,force:true});}
});

test('real bridge authenticates owned SDK probe, independent REST ZIP readback, deletion and release upload',async t=>{
 const toolkit=process.env.AUTODATA_REAL_TOOLKIT_ROOT;
 if(!toolkit){assert.notEqual(process.env.AUTODATA_REQUIRE_REAL_TOOLKIT,'1','required official toolkit absent');t.skip('requires independently installed test toolkit');return;}
 const current=Math.floor(Date.now()/1000),directory=await mkdtemp(tmpdir()+'/autodata-sdk-live-');
 try {
  const control=new URL('./',import.meta.url),helper=await readFile(new URL('./publisher_artifact.mjs',import.meta.url));
  const lock=await readFile(toolkit+'/package-lock.json'),tree=await readFile(toolkit+'/installed-tree.json');
  assert.deepEqual(lock,await readFile(new URL('./publisher-toolkit/package-lock.json',import.meta.url)));
  const context={protocol_version:3,environment:'staging',repository:'lucronn/autodata',repository_id:'123',repository_owner_id:'456',run_id:'123',run_attempt:2,workflow_ref:'lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master',workflow_sha:'a'.repeat(40),source_sha:'b'.repeat(40),service_config_sha256:'c'.repeat(64),protected_environment:'workshop-staging-publish',activation_sha256:'d'.repeat(64),toolchain_sha256:'e'.repeat(64),trust_policy_sha256:'f'.repeat(64)};
  const approvalKeys={[hash(Buffer.from('independent-owner-key'))]:'independent-owner-key'};
  const adapter={...Object.fromEntries(['activation_sha256','repository_id','repository_owner_id','workflow_sha','toolchain_sha256','trust_policy_sha256'].map(k=>[k,context[k]])),tools:{node:{path:'/usr/local/bin/node',sha256:'94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90',version:'v22.23.4'}},storage_origins:['productionresultssa0.blob.core.windows.net'],upstream_policy_sha256:'0'.repeat(64),approval_keys:approvalKeys,approvers:['independent-owner'],registry:'us-central1-docker.pkg.dev/owner-project/releases',evidence_layout:'https://productionresultssa0.blob.core.windows.net/evidence',toolkit_lock_sha256:hash(lock),runtime_service_origin:'https://results.actions.githubusercontent.com'};
  const review=bytes({protocol_version:1,toolkit_lock_sha256:hash(lock),audit_report_sha256:'0'.repeat(64),audit_findings:[{id:'independently-reviewed-test-findings',decision:'accepted'}],buffers_license_decision:'accepted',reviewed_by:'independent-owner',expires_at:new Date((current+600)*1000).toISOString().replace('.000Z','Z')});
  const f=liveFixture({issued_at:current-60,expires_at:current+600,toolkit_lock_sha256:hash(lock),toolkit_tree_sha256:hash(tree),helper_sha256:hash(helper),dependency_review_sha256:hash(review),approval_keys:approvalKeys,oidc:{...liveFixture().policy.oidc,jwks_issued_at:current-100,jwks_expires_at:current+1000}},{adapter:bytes(adapter)});
  await mkdir(directory+'/control');
  for(const name of ['publisher_policy.mjs','publisher_identity.mjs','publisher_artifact.mjs'])await writeFile(directory+'/control/'+name,await readFile(new URL(name,control)),{mode:0o400});
  for(const [name,raw] of [['bootstrap-live-v1.json',f.bootstrap],['policy-live-v1.envelope.json',f.envelope],['github-oidc-jwks-live-v1.json',f.jwks],['adapter-policy-v2.json',f.adapter],['dependency-review-v1.json',review]])await writeFile(directory+'/'+name,raw,{mode:0o600});
  const certificate=spawnSync('/usr/bin/openssl',['req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=api.github.com','-addext','subjectAltName=DNS:api.github.com,DNS:oidc.actions.githubusercontent.com,DNS:results.actions.githubusercontent.com,DNS:productionresultssa0.blob.core.windows.net','-keyout',directory+'/tls.key','-out',directory+'/ca.pem'],{encoding:'utf8',timeout:10000,maxBuffer:65536});assert.equal(certificate.status,0,certificate.stderr);
  const claims={iss:f.policy.oidc.issuer,aud:f.policy.oidc.audience,sub:f.policy.oidc.subject,exp:current+240,iat:current-60,nbf:current-60,jti:'actual-sdk-service-test',repository:f.policy.repository,repository_id:f.policy.repository_id,repository_owner_id:f.policy.repository_owner_id,run_id:context.run_id,run_attempt:String(context.run_attempt),workflow_ref:f.policy.workflow_ref,workflow_sha:f.policy.workflow_sha,ref:f.policy.ref,sha:f.policy.workflow_sha,event_name:f.policy.event_name,environment:f.policy.protected_environment};
  const jwtInput=bytes({alg:'RS256',typ:'JWT',kid:'fixture-key'}).toString('base64url')+'.'+bytes(claims).toString('base64url'),oidcToken=jwtInput+'.'+sign('RSA-SHA256',Buffer.from(jwtInput),rsa.privateKey).toString('base64url');
  const runtimeToken='e30.'+bytes({scp:'Actions.Results:11111111-1111-1111-1111-111111111111:22222222-2222-2222-2222-222222222222'}).toString('base64url')+'.c2ln';
  const credentials={ACTIONS_ID_TOKEN_REQUEST_URL:'https://oidc.actions.githubusercontent.com/_apis/distributedtask/hubs/build/plans/11111111-1111-1111-1111-111111111111/jobs/22222222-2222-2222-2222-222222222222/idtoken?api-version=2.0',ACTIONS_ID_TOKEN_REQUEST_TOKEN:'oidc-request-token',ACTIONS_RUNTIME_TOKEN:runtimeToken,ACTIONS_RESULTS_URL:'https://results.actions.githubusercontent.com',GITHUB_TOKEN:'independent-actions-read'};
  const program=`
import {createServer} from 'node:https';import {readFile,mkdtemp,writeFile,rm,lstat} from 'node:fs/promises';import {spawn} from 'node:child_process';import {createHash} from 'node:crypto';
const hash=b=>createHash('sha256').update(b).digest('hex'),context=${JSON.stringify(context)},credentials=${JSON.stringify(credentials)},oidcToken=${JSON.stringify(oidcToken)},runtimeToken=${JSON.stringify(runtimeToken)};
const state=new Map();let next=900,created=0,deleted=0,releaseUploads=0;const utc=()=>new Date().toISOString().replace(/\\.[0-9]{3}Z$/,'Z');
const json=(response,value,status=200)=>{const raw=Buffer.from(JSON.stringify(value));response.writeHead(status,{'Content-Length':raw.length,'Content-Type':'application/json'});response.end(raw);};
const metadata=a=>({id:a.id,name:a.name,expired:false,digest:'sha256:'+hash(a.zip),size_in_bytes:a.zip.length,created_at:a.created,expires_at:new Date(Date.now()+86400000).toISOString().replace(/\\.[0-9]{3}Z$/,'Z'),workflow_run:{id:123,repository_id:123,head_sha:context.workflow_sha}});
const server=createServer({key:await readFile(${JSON.stringify(directory+'/tls.key')}),cert:await readFile(${JSON.stringify(directory+'/ca.pem')})},async(request,response)=>{
 try {
 const url=new URL(request.url,'https://'+request.headers.host),chunks=[];for await(const chunk of request)chunks.push(chunk);const body=Buffer.concat(chunks);
 if(request.headers.host==='oidc.actions.githubusercontent.com'){if(request.headers.authorization!=='Bearer oidc-request-token')return json(response,{},401);return json(response,{value:oidcToken});}
 if(request.headers.host==='api.github.com'){
 if(request.headers.authorization!=='Bearer independent-actions-read')return json(response,{},401);
 if(url.pathname.endsWith('/attempts/2'))return json(response,{id:123,run_attempt:2,head_sha:context.workflow_sha,status:'in_progress',conclusion:null,repository:{id:123,owner:{id:456}},run_started_at:new Date(Date.now()-60000).toISOString().replace(/\\.[0-9]{3}Z$/,'Z')});
 if(url.pathname.endsWith('/runs/123/artifacts'))return json(response,{total_count:state.size,artifacts:[...state.values()].map(a=>({id:a.id,name:a.name}))});
 const match=/\\/artifacts\\/(\\d+)(\\/zip)?$/.exec(url.pathname),a=match&&state.get(Number(match[1]));if(!a)return json(response,{},404);
 if(match[2]){response.writeHead(302,{Location:'https://productionresultssa0.blob.core.windows.net/download/'+a.id+'?sig=owned-test'});response.end();return;}
 return json(response,metadata(a));
 }
 if(request.headers.host==='results.actions.githubusercontent.com'){
 if(request.headers.authorization!=='Bearer '+runtimeToken)return json(response,{},401);
 const input=JSON.parse(body),operation=url.pathname.split('/').at(-1);
 if(operation==='ListArtifacts')return json(response,{artifacts:[...state.values()].map(a=>({workflowRunBackendId:'11111111-1111-1111-1111-111111111111',workflowJobRunBackendId:'22222222-2222-2222-2222-222222222222',databaseId:String(a.id),name:a.name,size:String(a.zip?.length??0)}))});
 if(operation==='CreateArtifact'){if([...state.values()].some(a=>a.name===input.name))return json(response,{},409);const a={id:next++,name:input.name,created:utc(),blocks:new Map()};state.set(a.id,a);created++;return json(response,{ok:true,signedUploadUrl:'https://productionresultssa0.blob.core.windows.net/upload/'+a.id+'?sig=owned-test'});}
 if(operation==='FinalizeArtifact'){const a=[...state.values()].find(a=>a.name===input.name);if(!a?.zip || Number(input.size)!==a.zip.length || (input.hash?.value??input.hash)!=='sha256:'+hash(a.zip))return json(response,{},400);if(a.name.startsWith('workshop-release-'))releaseUploads++;return json(response,{ok:true,artifactId:String(a.id)});}
 if(operation==='DeleteArtifact'){const a=[...state.values()].find(a=>a.name===input.name);if(!a)return json(response,{},404);state.delete(a.id);deleted++;return json(response,{ok:true,artifactId:String(a.id)});}
 return json(response,{},404);
 }
 if(request.headers.host==='productionresultssa0.blob.core.windows.net'){
 const id=Number(url.pathname.split('/').at(-1)),a=state.get(id);if(!a)return json(response,{},404);
 if(request.method==='GET'){response.writeHead(200,{'Content-Length':a.zip.length});response.end(a.zip);return;}
 if(url.searchParams.get('comp')==='block')a.blocks.set(url.searchParams.get('blockid'),body);
 else if(url.searchParams.get('comp')==='blocklist')a.zip=Buffer.concat([...a.blocks.values()]);else a.zip=body;
 response.writeHead(201,{'Content-Length':'0',etag:'"owned"','x-ms-request-id':'owned','x-ms-version':'2023-11-03'});response.end();return;
 }
 json(response,{},403);
 }catch(error){json(response,{error:'bounded-local-service-test'},500);}
});
await new Promise(resolve=>server.listen(443,'8.8.8.8',resolve));
async function bridge(mode,input,cwd){return new Promise((resolve,reject)=>{const child=spawn('/opt/autodata/node',['/opt/autodata/control/publisher_artifact.mjs',mode],{cwd,env:{PATH:'/usr/bin:/bin',NODE_OPTIONS:'--use-openssl-ca'},stdio:['pipe','pipe','pipe']});let out='',err='';const timer=setTimeout(()=>{child.kill('SIGKILL');reject(Error('bridge-timeout'));},90000);child.stdout.on('data',b=>{out+=b;if(out.length>65536)child.kill('SIGKILL');});child.stderr.on('data',b=>{err+=b;if(err.length>65536)child.kill('SIGKILL');});child.on('close',code=>{clearTimeout(timer);if(code!==0)reject(Error('bridge-rejected '+mode+' '+err));else resolve(JSON.parse(out));});child.stdin.end(JSON.stringify(input));});}
const authCwd=await mkdtemp('/tmp/autodata-sdk-auth-'),uploadCwd=await mkdtemp('/tmp/autodata-sdk-upload-');
try {
 const installed=await bridge('--installed-policy',context,authCwd);if(installed.adapter_policy.registry!==${JSON.stringify(adapter.registry)})throw Error('installed-policy');
 const authenticated=await bridge('--authenticate-context',{context,credentials},authCwd);if(authenticated.status!=='runtime_authenticated' || state.size!==0 || deleted!==1)throw Error('probe-unaccepted');
 const token=await readFile(authCwd+'/identity-token','utf8'),st=await lstat(authCwd+'/identity-token');if(token!==oidcToken || (st.mode&0o777)!==0o600)throw Error('token-private-file');
 const inner=Buffer.from('real upload inner bytes');await writeFile(uploadCwd+'/release.zip',inner,{mode:0o600});
 const uploaded=await bridge('--upload-release',{request:{protocol_version:3,operation:'upload',context,archive_sha256:hash(inner),archive_bytes:inner.length,artifact_name:'workshop-release-'+context.source_sha+'-run-123-attempt-2'},credentials},uploadCwd);
 if(uploaded.protocol_version!==3 || uploaded.run_id!=='123' || uploaded.run_attempt!==2 || !uploaded.artifact_id || state.size!==1 || releaseUploads!==1 || deleted!==3 || created!==4)throw Error('upload-unaccepted');
 console.log('real-sdk-probe-rest-deletion-upload-verified');
}finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));await rm(authCwd,{recursive:true,force:true});await rm(uploadCwd,{recursive:true,force:true});}
`;
  await writeFile(directory+'/positive.mjs',program,{mode:0o600});
  const script=`set -eu
/usr/sbin/ip link set lo up
/usr/sbin/ip addr add 8.8.8.8/32 dev lo
mount -t tmpfs -o mode=755 tmpfs /etc
mkdir -p /etc/autodata/publisher /etc/ssl/certs
printf '8.8.8.8 api.github.com oidc.actions.githubusercontent.com results.actions.githubusercontent.com productionresultssa0.blob.core.windows.net\\n' > /etc/hosts
cp "$1/ca.pem" /etc/ssl/cert.pem
cp "$1/ca.pem" /etc/ssl/certs/ca-certificates.crt
for name in bootstrap-live-v1.json policy-live-v1.envelope.json github-oidc-jwks-live-v1.json adapter-policy-v2.json dependency-review-v1.json; do cp "$1/$name" "/etc/autodata/publisher/$name"; chmod 444 "/etc/autodata/publisher/$name"; done
mount --bind /etc/autodata/publisher /etc/autodata/publisher
mount -o remount,bind,ro /etc/autodata/publisher
mount -t tmpfs -o mode=755 tmpfs /opt
mkdir -p /opt/autodata/control/publisher-toolkit
cp "$1/control/"*.mjs /opt/autodata/control/
cp -R "$4/." /opt/autodata/control/publisher-toolkit/
cp "$2" /opt/autodata/node
chmod 555 /opt/autodata/node
chmod -R a-w /opt/autodata/control
mount --bind /opt/autodata /opt/autodata
mount -o remount,bind,ro /opt/autodata
NODE_OPTIONS=--use-openssl-ca exec /opt/autodata/node "$1/positive.mjs"
`;
  const result=spawnSync('sudo',['-n','unshare','--mount','--net','--pid','--fork','--kill-child=SIGKILL','--propagation','private','/bin/sh','-c',script,'sdk-test',directory,process.execPath,'unused',toolkit],{encoding:'utf8',timeout:240000,maxBuffer:65536});
  assert.equal(result.status,0,result.stderr);assert.equal(result.stdout,'real-sdk-probe-rest-deletion-upload-verified\n');
 } finally {await rm(directory,{recursive:true,force:true});}
});
