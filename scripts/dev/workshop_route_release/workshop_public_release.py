"""Root-fenced one-attempt public source release. Default check never dispatches."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
PHYSICAL=Path('/home/corp/.local/state/autodata-workshop-route-preview-09524db-release-20261116')
PAYLOAD=Path('/home/corp/.local/state/autodata-workshop-route-preview-09524db-20261116')
ENV=Path('/etc/autodata/preview/api-public-preview.env')
OVERRIDE=Path('/etc/systemd/system/autodata-api.service.d/99-public-preview.conf')
DEPENDENCY=Path('/etc/systemd/system/autodata-api.service.d/10-docker-dependency.conf')
INSTALL=Path('/usr/local/libexec/autodata/workshop-route-preview-09524db/autodata-api')
UNIT=Path('/etc/systemd/system/autodata-api.service')
SERVICE='autodata-api.service'
CLEAN={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
SEAL='a6c2380eea81b3c1339b4f2bf17496ce2975b42e5cdfa4d18e97234aa1f1cf5a'
class Refused(RuntimeError):pass

def require(ok,code):
 if not ok:raise Refused(code)

def digest(data):return hashlib.sha256(data).hexdigest()

def private_json(path):
 st=path.lstat();require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_uid==os.geteuid() and stat.S_IMODE(st.st_mode)==0o600 and st.st_size<=1048576,'control_metadata')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb') as f:
  require(os.fstat(f.fileno())==st,'control_race');return json.load(f)

def metadata(path):
 st=path.lstat();require(stat.S_ISREG(st.st_mode) and st.st_nlink==1,'regular_single_link')
 return {'sha256':digest(path.read_bytes()),'uid':st.st_uid,'gid':st.st_gid,'mode':oct(stat.S_IMODE(st.st_mode))}

def sync_dir(path):
 fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)

def exclusive(path,data,mode=0o600):
 fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,mode)
 with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 sync_dir(path.parent)

def atomic_file(path,data,info):
 require(not path.is_symlink(),'live_symlink');fd,name=tempfile.mkstemp(prefix='.source-release-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:
   os.fchown(f.fileno(),info['uid'],info['gid']);os.fchmod(f.fileno(),int(info['mode'],8));f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(name,path);sync_dir(path.parent)
 finally:
  if os.path.exists(name):os.unlink(name)

def check_marker(path,expected):
 require(metadata(path)=={'sha256':digest(expected),'uid':0,'gid':0,'mode':'0o600'},'marker_drift')


def target_override(data,old,new):
 require(data.count(old)==1,'override_path_count');return data.replace(old,new)

def allocation(path):return path.stat().st_blocks*512+sum(p.stat().st_blocks*512 for p in path.rglob('*'))

def env_policy(data):
 pairs=[line.split('=',1) for line in data.decode().splitlines() if line and not line.lstrip().startswith('#') and '=' in line]
 for key,want in [('AUTODATA_COMMERCE_MODE','read_only'),('AUTODATA_AUTH_MODE','firebase')]:
  require([v for k,v in pairs if k==key]==[want],'public_env_policy')

def dry_baseline(m):
 b=m['baseline']
 for name,want in b['files'].items():require(metadata(Path(name))==want,'baseline_file_drift')
 env_policy(ENV.read_bytes());p=Path('/proc')/str(b['api_pid']);require((p/'stat').read_text().split()[21]==b['api_start_ticks'] and os.readlink(p/'exe')==b['api_exe'],'baseline_lifecycle')
 a=Path(b['api_exe']).stat();v=(p/'exe').stat();require((a.st_dev,a.st_ino)==tuple(b['api_dev_inode'])==(v.st_dev,v.st_ino) and digest((p/'exe').read_bytes())==b['files'][b['api_exe']]['sha256'],'loaded_binary_drift')


def capacity_errors(v,p):
 errors=[]
 if v['prep']>p['prep_cap'] or v['install']>p['install_cap'] or v.get('control',0)>4194304 or v.get('browser',0)>20971520:errors.append('owned_cap')
 if v['home_free']<=p['home_absolute']+p['drift']+max(0,p['prep_cap']-v['prep'])+max(0,p['install_cap']-v['install']):errors.append('home_reserve')
 if v['root_free']<=p['root_absolute']+p['root_burst']+max(0,p['install_cap']-v['install']):errors.append('root_reserve')
 if v['docker_free']<=p['docker_floor'] or v['inodes']<1000:errors.append('docker_or_inode')
 if v['external_growth']>=p['external_stop']:errors.append('unowned_drift')
 return errors

def capacity(m):
 h=os.statvfs('/home');r=os.statvfs('/');d=os.statvfs('/mnt/openfoam/docker')
 prep=allocation(PAYLOAD)+(allocation(ROOT) if ROOT==PHYSICAL else 0);installed=allocation(INSTALL.parent) if INSTALL.parent.exists() else 0
 browser=allocation(ROOT/'browser-runtime') if (ROOT/'browser-runtime').exists() else 0
 control=allocation(ROOT)-browser if ROOT==PHYSICAL else 0
 v={'control':control,'browser':browser,'home_free':h.f_bavail*h.f_frsize,'root_free':r.f_bavail*r.f_frsize,'docker_free':d.f_bavail*d.f_frsize,'inodes':min(h.f_favail,r.f_favail,d.f_favail),'prep':prep,'install':installed,'external_growth':0}
 if (ROOT/'capacity-baseline.json').exists():
  b=private_json(ROOT/'capacity-baseline.json');v['external_growth']=max(0,b['home_free']-v['home_free']-(prep-b['prep']),b['root_free']-v['root_free']-(installed-b['install']))
 require(not capacity_errors(v,m['capacity']),'capacity_guard');return v

def command(args,timeout=5):
 require(isinstance(args,list) and args and args[0] in ('/usr/bin/docker','/usr/bin/systemctl'),'command_allowlist')
 try:result=subprocess.run(args,env=CLEAN,capture_output=True,timeout=timeout,check=False)
 except Exception:raise Refused('child_failed') from None
 require(result.returncode==0 and len(result.stdout)<=4194304,'child_failed');return result.stdout

def docker(args,timeout=5):return command(['/usr/bin/docker','--config',str(ROOT/'docker-cli-config'),'--host','unix:///var/run/docker.sock',*args],timeout)

def source_guard(path):
 paths=list(itertools.islice(path.rglob('*'),10000));require(len(paths)<10000,'source_bound');rows=[]
 for p in [path,*sorted(paths)]:
  st=p.lstat();require(not p.is_symlink() and (p.is_file() or p.is_dir()),'source_kind');rows.append([str(p.relative_to(path)),st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode,digest(p.read_bytes()) if p.is_file() else None])
 return digest(json.dumps(rows,separators=(',',':')).encode())

def private_identity(x):return {'id':x['Id'],'image':x['Image'],'name':x['Name'],'mounts':x['Mounts'],'restart':x['HostConfig']['RestartPolicy'],'readonly_root':x['HostConfig']['ReadonlyRootfs'],'network':x['HostConfig']['NetworkMode'],'running':x['State']['Running'],'started_at':x['State']['StartedAt'],'pid':x['State']['Pid'],'restart_count':x['RestartCount'],'env_sha256':digest(json.dumps(x['Config']['Env'],separators=(',',':')).encode())}

def private_check(m,live=False):
 b=m['baseline'];s=b['private_source'];require(digest(Path(s['archive_path']).read_bytes())==s['archive_sha256'] and source_guard(Path(s['root']))==s['guard_sha256'],'private_source_drift')
 proc=Path('/proc')/str(b['ingestion']['pid']);require(proc.is_dir() and (proc/'stat').read_text().split()[21]==b['private_start_ticks'],'private_lifecycle_drift')
 if live:require(private_identity(json.loads(docker(['inspect',b['ingestion']['id']]))[0])==b['ingestion'],'private_identity_drift')
 for path in (DEPENDENCY,UNIT):require(metadata(path)==b['files'][str(path)],'unit_dependency_drift')

def running_identity(executable,expected,timeout=5):
 try:
  props=dict(line.split('=',1) for line in command(['/usr/bin/systemctl','show',SERVICE,'--property=MainPID','--property=ActiveState'],timeout).decode().splitlines())
  pid=props.get('MainPID','0')
  if props.get('ActiveState')!='active' or not pid.isdecimal() or int(pid)<=0:return False
  installed=Path(executable);loaded=Path('/proc')/pid/'exe'
  if os.readlink(loaded)!=executable:return False
  a=installed.stat();b=loaded.stat()
  return (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino) and metadata(installed)==expected and digest(loaded.read_bytes())==expected['sha256']
 except (OSError,Refused):return False

def wait_identity(executable,expected,timeout=30):
 end=time.monotonic()+timeout
 while True:
  if running_identity(executable,expected,timeout=min(5,max(.001,end-time.monotonic()))):return
  require(time.monotonic()<end,'identity_deadline');time.sleep(min(.1,max(0,end-time.monotonic())))

def payload_check(m):
 require(digest((PAYLOAD/'PACKAGE-SEAL.json').read_bytes())==SEAL,'payload_seal')
 require(PAYLOAD.resolve()==PAYLOAD and PAYLOAD.stat().st_dev==Path('/home').stat().st_dev and stat.S_IMODE(PAYLOAD.stat().st_mode)==0o700,'payload_physical');seal=json.loads((PAYLOAD/'PACKAGE-SEAL.json').read_text())
 for name,want in seal['files'].items():require(metadata(PAYLOAD/name)=={k:want[k] for k in ('sha256','uid','gid','mode')} and (PAYLOAD/name).stat().st_size==want['bytes'],'payload_file')
 require(m['payload_seal_sha256']==SEAL and m['binary_sha256']==seal['files']['autodata-api']['sha256'] and m['source_sha']==seal['source_sha'] and m['source_tree']==seal['source_tree'],'payload_source')

def load(manifest_hash,helper_hash,check_payload=True):
 require(re.fullmatch('[a-f0-9]{64}',manifest_hash or '') and re.fullmatch('[a-f0-9]{64}',helper_hash or ''),'review_hash_required')
 require(digest((ROOT/'release-manifest.json').read_bytes())==manifest_hash and digest(Path(__file__).read_bytes())==helper_hash,'review_hash_drift')
 m=private_json(ROOT/'release-manifest.json');require(set(m['control_files'])=={'workshop_public_release.py','workshop_public_probe.py'},'control_inventory');require(m['version']==1 and m['unit']==SERVICE and m['install_binary']==str(INSTALL) and m['physical_control']==str(PHYSICAL) and m['payload']==str(PAYLOAD),'manifest_contract')
 require(m['capacity']=={'home_absolute':5368709120,'drift':134217728,'prep_cap':134217728,'install_cap':67108864,'root_absolute':2147483648,'root_burst':33554432,'docker_floor':813694976,'external_stop':100663296},'capacity_contract')
 for name,pin in m['control_files'].items():require(name in ('workshop_public_release.py','workshop_public_probe.py') and metadata(ROOT/name)['sha256']==pin,'control_file_drift')
 if check_payload:payload_check(m)
 return m

def execution_fence(m,manifest_hash,helper_hash,rollback=False):
 require(ROOT==PHYSICAL and ROOT.resolve()==ROOT and ROOT.stat().st_dev==Path('/home').stat().st_dev,'physical_execution_required')
 require(os.geteuid()==0 and ROOT.stat().st_uid==0 and stat.S_IMODE(ROOT.stat().st_mode)==0o700,'root_execution_required')
 for name in ('release-manifest.json','workshop_public_release.py','workshop_public_probe.py','docker-cli-config/config.json'):
  p=ROOT/name;require(p.resolve()==p and p.stat().st_dev==ROOT.stat().st_dev and p.stat().st_uid==0 and p.stat().st_gid==0 and stat.S_IMODE(p.stat().st_mode)==(0o500 if name.endswith('.py') else 0o600),'physical_control_owner')
 require(INSTALL.parent.parent.resolve()==INSTALL.parent.parent and INSTALL.parent.parent.stat().st_uid==0 and INSTALL.parent.parent.stat().st_dev==Path('/').stat().st_dev,'install_parent_physical');require((ROOT/'docker-cli-config/config.json').read_bytes()==b'{}\n','docker_config')
 approval=private_json(ROOT/'ROOT-APPROVAL.json');require(approval=={'manifest_sha256':manifest_hash,'helper_sha256':helper_hash,'scope':'one-source-switch-one-rollback','local_fixture_sha256':m['local_fixture_sha256']},'approval_contract')
 if rollback:return
 require(m['local_fixture_sha256'] is not None and digest((ROOT/'LOCAL-FIXTURE-PASS.json').read_bytes())==m['local_fixture_sha256'],'local_fixture_pending')
 proof=private_json(ROOT/'LOCAL-FIXTURE-PASS.json');require(proof.get('status')=='PASS' and proof.get('source_binary_sha256')==m['binary_sha256'] and all(proof.get(k) is True for k in ('source_package_unchanged','public_private_unchanged','all_owned_children_reaped')),'local_fixture_failed')
 for name,pin in m['fixture_files'].items():require(name in ('LOCAL-FIXTURE-PASS.json','LOCAL-BROWSER-PASS.json','LOCAL-ASSET-PASS.json','LOCAL-FIXTURE-OUTCOME.json') and digest((ROOT/name).read_bytes())==pin,'fixture_file_drift')
 browser=private_json(ROOT/'LOCAL-BROWSER-PASS.json');require(browser.get('status')=='SYNTHETIC_LOCAL_BROWSER_PASS' and browser.get('passed') is True and browser.get('publicRequests')==0 and browser.get('providerRequests')==0,'browser_fixture_failed')
 require(private_json(ROOT/'LOCAL-ASSET-PASS.json').get('all15_verified') is True,'fixture_assets_failed')

def probe_receipt(m,phase):
 args=['/usr/bin/python3','-I',str(ROOT/'workshop_public_probe.py'),'--phase',phase,'--manifest-sha256',digest((ROOT/'release-manifest.json').read_bytes())]
 capacity(m);process=subprocess.Popen(args,env=CLEAN,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);end=time.monotonic()+210
 try:
  while True:
   capacity(m);remaining=end-time.monotonic();require(remaining>0,'probe_outer_deadline')
   try:out,err=process.communicate(timeout=min(.25,remaining));break
   except subprocess.TimeoutExpired:pass
  require(process.returncode==0 and len(out)<=65536,'probe_child_failed');result=json.loads(out);require(result.get('phase')==phase and type(result.get('passed')) is bool and len(result.get('checks',[]))<=42,'probe_child_shape');return result
 except BaseException:
  if process.poll() is None:os.killpg(process.pid,signal.SIGKILL)
  process.communicate();raise


class Control:
 def __init__(self,m,manifest_hash):self.m=m;self.hash=manifest_hash;self.root=ROOT
 def persist(self,name,data=None):exclusive(self.root/name,data if data is not None else (self.hash+'\n').encode())
 def baseline_check(self):
  m=self.m;b=m['baseline'];payload_check(m);capacity(m);private_check(m,True);dry_baseline(m)
  for name,want in b['files'].items():require(metadata(Path(name))==want,'baseline_file_drift')
  props=dict(line.split('=',1) for line in command(['/usr/bin/systemctl','show',SERVICE,'--property=MainPID','--property=ActiveState']).decode().splitlines())
  require(props.get('ActiveState')=='active' and props.get('MainPID')==str(b['api_pid']),'baseline_pid_drift')
  require((Path('/proc')/str(b['api_pid'])/'stat').read_text().split()[21]==b['api_start_ticks'],'baseline_pid_reused')
  require(running_identity(b['api_exe'],b['files'][b['api_exe']]),'baseline_executable')
 def protected(self):
  predicate="tablename IN ('auth_sessions','customer_accounts','entitlements','payment_events','workshop_checkout_requests','workshop_orders','publication_events','source_fetch_jobs','source_review_items','source_artifacts','source_snapshots','dataset_requests','dataset_projections') OR tablename LIKE 'canonical_article%' OR tablename LIKE 'derived_article%' OR tablename LIKE 'catalog_article%'"
  def sql(q):
   data=docker(['exec','-e','PGOPTIONS=-c default_transaction_read_only=on','autodata-postgres-1','psql','-X','-A','-t','-q','-v','ON_ERROR_STOP=1','-U','autodata','-d','autodata','-c',q],20);require(len(data)<=65536,'protected_bound');return data.decode().strip()
  names=sql("SELECT tablename FROM pg_tables WHERE schemaname='public' AND ("+predicate+") ORDER BY tablename").splitlines();require(len(names)==27 and all(re.fullmatch('[a-z][a-z0-9_]*',n) for n in names),'protected_inventory')
  terms=["SELECT '"+n+"' AS name,count(*) AS count,md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),'')) AS hash FROM public.\""+n+'\" t' for n in names]
  q="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='3s'; SELECT json_build_object('inventory',(SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='public' AND ("+predicate+")),'fingerprints',(SELECT json_object_agg(name,json_build_object('count',count,'hash',hash)) FROM ("+' UNION ALL '.join(terms)+") q)); ROLLBACK;"
  result=json.loads(sql(q));require(result['inventory']==names and len(result['fingerprints'])==27,'protected_snapshot');return result
 def prepare(self):
  self.baseline_check();require(not INSTALL.parent.exists(),'install_exists');state=self.root/'rollback-state';state.mkdir(mode=0o700);sync_dir(self.root)
  original=OVERRIDE.read_bytes();target=target_override(original,self.m['baseline']['api_exe'].encode(),str(INSTALL).encode());require(digest(target)==self.m['target_override_sha256'],'target_override')
  for name,data in [('original.env',ENV.read_bytes()),('original.conf',original),('target.conf',target)]:exclusive(state/name,data)
  exclusive(state/'protected-before.json',(json.dumps(self.protected(),sort_keys=True)+'\n').encode());self.persist('capacity-baseline.json',(json.dumps(capacity(self.m),sort_keys=True)+'\n').encode());self.persist('prepared')
 def prepared(self):
  check_marker(self.root/'prepared',(self.hash+'\n').encode());state=self.root/'rollback-state';require(state.stat().st_uid==0 and stat.S_IMODE(state.stat().st_mode)==0o700 and not state.is_symlink(),'backup_directory')
  for path,name in [(ENV,'original.env'),(OVERRIDE,'original.conf')]:require(metadata(state/name)=={'sha256':self.m['baseline']['files'][str(path)]['sha256'],'uid':0,'gid':0,'mode':'0o600'},'backup_drift')
  require(digest((state/'target.conf').read_bytes())==self.m['target_override_sha256'],'target_backup_drift')
 def install(self):
  self.prepared();self.baseline_check();require(not INSTALL.parent.exists(),'install_exists');self.protected_check();check_marker(self.root/'baseline-postcheck-passed',(self.hash+'\n').encode());approval=private_json(self.root/'ROOT-INSTALL-APPROVAL.json');require(approval=={'manifest_sha256':self.hash,'protected_before_sha256':digest((self.root/'rollback-state/protected-before.json').read_bytes())},'protected_review_pending');self.persist('activation-attempted');INSTALL.parent.mkdir(mode=0o755);sync_dir(INSTALL.parent.parent)
  fd=os.open(INSTALL,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as out,(PAYLOAD/'autodata-api').open('rb') as src:
   while chunk:=src.read(1048576):capacity(self.m);out.write(chunk)
   out.flush();os.fsync(out.fileno());require(digest(INSTALL.read_bytes())==self.m['binary_sha256'],'installed_hash');os.fchmod(out.fileno(),0o555);os.fsync(out.fileno())
  sync_dir(INSTALL.parent);capacity(self.m)
 def restart(self):
  command(['/usr/bin/systemctl','daemon-reload'],30);command(['/usr/bin/systemctl','restart',SERVICE],30)
 def protected_check(self):require(self.protected()==private_json(self.root/'rollback-state/protected-before.json'),'protected_changed')
 def candidate_check(self,bind=False):
  payload_check(self.m);private_check(self.m,True);capacity(self.m);require(metadata(ENV)==self.m['baseline']['files'][str(ENV)],'candidate_env');want={**self.m['baseline']['files'][str(OVERRIDE)],'sha256':self.m['target_override_sha256']};require(metadata(OVERRIDE)==want,'candidate_override');wait_identity(str(INSTALL),{'sha256':self.m['binary_sha256'],'uid':0,'gid':0,'mode':'0o555'});props=dict(line.split('=',1) for line in command(['/usr/bin/systemctl','show',SERVICE,'--property=ActiveState','--property=MainPID','--property=NRestarts']).decode().splitlines());require(props.get('NRestarts')=='0' and props.get('ActiveState')=='active' and props.get('MainPID','0')!='0' and os.readlink(Path('/proc')/props['MainPID']/'exe')==str(INSTALL),'candidate_service')
  pid=props['MainPID'];lifecycle={'pid':int(pid),'start_ticks':(Path('/proc')/pid/'stat').read_text().split()[21]}
  if bind:self.persist('candidate-lifecycle.json',(json.dumps(lifecycle,sort_keys=True)+'\n').encode())
  else:require(private_json(self.root/'candidate-lifecycle.json')==lifecycle,'candidate_restarted')
  self.protected_check()
 def switch(self):
  self.prepared();self.baseline_check();self.protected_check();check_marker(self.root/'activation-attempted',(self.hash+'\n').encode());require(metadata(INSTALL)=={'sha256':self.m['binary_sha256'],'uid':0,'gid':0,'mode':'0o555'},'install_drift');self.persist('switch-attempted')
  atomic_file(OVERRIDE,(self.root/'rollback-state/target.conf').read_bytes(),self.m['baseline']['files'][str(OVERRIDE)]);self.restart();self.candidate_check(bind=True)
 def canary(self,phase):
  self.prepared()
  check=self.candidate_check if phase=='candidate' else self.old_check if phase=='rollback' else self.baseline_check
  if phase=='rollback':check_marker(self.root/'rollback-attempted',(self.hash+'\n').encode())
  check();
  if phase=='baseline':self.protected_check()
  self.persist(phase+'-probes-attempted');result=probe_receipt(self.m,phase);self.persist(phase+'-probes.json',(json.dumps(result,sort_keys=True)+'\n').encode());require(result.get('passed') is True,'canary_failed');check();
  if phase=='baseline':self.protected_check()
  self.persist(phase+'-postcheck-passed')


 def rollback_inputs(self):
  self.prepared();check_marker(self.root/'activation-attempted',(self.hash+'\n').encode());check_marker(self.root/'switch-attempted',(self.hash+'\n').encode());private_check(self.m,True);b=self.m['baseline'];require(metadata(Path(b['api_exe']))==b['files'][b['api_exe']],'old_binary_drift');require(metadata(ENV)==b['files'][str(ENV)],'rollback_env_drift');current=metadata(OVERRIDE);require(current['sha256'] in (b['files'][str(OVERRIDE)]['sha256'],self.m['target_override_sha256']) and all(current[k]==b['files'][str(OVERRIDE)][k] for k in ('uid','gid','mode')),'rollback_unknown_override');return [(OVERRIDE,(self.root/'rollback-state/original.conf').read_bytes(),b['files'][str(OVERRIDE)])]
 def old_check(self):
  b=self.m['baseline'];wait_identity(b['api_exe'],b['files'][b['api_exe']]);private_check(self.m,True);require(metadata(OVERRIDE)==b['files'][str(OVERRIDE)] and metadata(ENV)==b['files'][str(ENV)],'restored_files');self.protected_check()
 def rollback(self):
  originals=self.rollback_inputs();self.persist('rollback-attempted')
  for path,data,info in originals:atomic_file(path,data,info)
  self.restart();self.old_check()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['dry-check','prepare','baseline-canary','install','switch','candidate-check','canary','rollback','rollback-canary'],default='dry-check');parser.add_argument('--reviewed-manifest-sha256',required=True);parser.add_argument('--reviewed-helper-sha256',required=True);parser.add_argument('--root-execute',action='store_true');args=parser.parse_args()
 try:
  m=load(args.reviewed_manifest_sha256,args.reviewed_helper_sha256,check_payload=args.phase not in ('rollback','rollback-canary'))
  if args.phase=='dry-check':
   private_check(m,False);dry_baseline(m);v=capacity(m);print(json.dumps({'dry_only':True,'dispatches':0,'package_verified':True,'capacity':v,'pending':['root_approval','physical_control_copy','physical_fixture_proof_copy','fresh_protected_baseline']}));return 0
  require(args.root_execute,'execution_not_authorized');execution_fence(m,args.reviewed_manifest_sha256,args.reviewed_helper_sha256,rollback=args.phase in ('rollback','rollback-canary'));c=Control(m,args.reviewed_manifest_sha256)
  if args.phase in ('canary','baseline-canary','rollback-canary'):c.canary({'canary':'candidate','baseline-canary':'baseline','rollback-canary':'rollback'}[args.phase])
  else:getattr(c,args.phase.replace('-','_'))()
  print(json.dumps({'phase':args.phase,'passed':True}));return 0
 except Exception:
  print(json.dumps({'phase':args.phase,'passed':False,'error':'release_refused_preserve_state','rollback_required_if_switch_mutated':args.phase in ('switch','canary')}));return 1
if __name__=='__main__':raise SystemExit(main())
