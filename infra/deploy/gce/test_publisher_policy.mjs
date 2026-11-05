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
  const adapter=bytes({registry:'us-central1-docker.pkg.dev/owner-project/releases'});
  const policy={...f.policy,protocol_version:2,purpose:'autodata.publisher.staging.live.v1',
    upload_enabled:true,runtime_bearer_authentication:'service-challenge-v1',
    adapter_policy_sha256:hash(adapter),toolchain_image_digest:'sha256:'+'1'.repeat(64),
    toolkit_lock_sha256:'2'.repeat(64),toolkit_tree_sha256:'3'.repeat(64),helper_sha256:'4'.repeat(64),
    dependency_review_sha256:'5'.repeat(64),runtime_origins:['https://results.actions.githubusercontent.com'],
    storage_origins:['https://productionresultssa0.blob.core.windows.net'],
    approval_keys:{[hash(Buffer.from('independent-owner-key'))]:'independent-owner-key'},
    oidc:{...f.policy.oidc,audience:'urn:autodata:publisher:staging:live:v1'},...changes};
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
    {adapter_policy_sha256:'0'.repeat(64)},{helper_sha256:null},{dependency_review_sha256:''},
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
    const script=`set -eu
mount -t tmpfs -o mode=755 tmpfs /etc
mkdir -p /etc/autodata/publisher
for name in bootstrap-live-v1.json policy-live-v1.envelope.json github-oidc-jwks-live-v1.json adapter-policy-v2.json; do
  cp -- "$1/$name" "/etc/autodata/publisher/$name"
  chmod 444 "/etc/autodata/publisher/$name"
done
mount --bind /etc/autodata/publisher /etc/autodata/publisher
mount -o remount,bind,ro /etc/autodata/publisher
exec "$2" --input-type=module -e "$3"
`;
    const program=`import {loadInstalledLiveOwnerPolicy,installedLivePolicyClaims,installedPolicyClaims} from ${JSON.stringify(new URL('./publisher_policy.mjs',import.meta.url).href)};
const handle=await loadInstalledLiveOwnerPolicy();
const result=installedLivePolicyClaims(handle);
if(result.policy.purpose!=='autodata.publisher.staging.live.v1')process.exit(2);
try {installedPolicyClaims(handle);process.exit(4);} catch {}
console.log('installed-live-policy-verified');`;
    const result=spawnSync('sudo',['-n','unshare','--mount','--propagation','private','/bin/sh','-c',script,'trust-test',directory,process.execPath,program],{encoding:'utf8',timeout:15000,maxBuffer:65536});
    assert.equal(result.status,0,result.stderr);assert.equal(result.stdout,'installed-live-policy-verified\n');
  } finally {await rm(directory,{recursive:true,force:true});}
});
