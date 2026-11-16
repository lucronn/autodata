"""Sealed local-only fixture runner. Dry proof never starts API or Chromium."""
import os,sys,pathlib,json,hashlib,subprocess,socket,time,signal,http.client,importlib.util,ctypes
from datetime import datetime,timezone
from capacity_guard import allocated,require_floor,wait_guarded
from budget_guard import budget
R=pathlib.Path(__file__).resolve().parent
PKG=pathlib.Path('/home/corp/.local/state/autodata-workshop-route-preview-09524db-20261116')
PROFILE=pathlib.Path('/tmp/ad-route-09524db-qa')
BUILD=pathlib.Path('/home/corp/autodata-evidence/workshop-route-preview-09524db-build-20261116')
PROFILE_CAP=134217728;PROFILE_STOP=100663296;FIXTURE_CAP=71303168
BINARY_SHA='23892e134b2746f7f75c827021559adf4024dd8f114552f5dce298ba6e354b0d'
SEAL_SHA='a6c2380eea81b3c1339b4f2bf17496ce2975b42e5cdfa4d18e97234aa1f1cf5a'
ENV={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}

def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write_once(p,value):
 with pathlib.Path(p).open('x') as f:
  os.chmod(p,0o600);f.write(json.dumps(value,indent=2)+'\n');f.flush();os.fsync(f.fileno())
 fd=os.open(pathlib.Path(p).parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def source_snapshot():
 assert sha(PKG/'PACKAGE-SEAL.json')==SEAL_SHA,'source_package_seal'
 seal=json.loads((PKG/'PACKAGE-SEAL.json').read_text());out={}
 for p in sorted(PKG.iterdir()):
  st=p.lstat();assert p.is_file() and not p.is_symlink() and st.st_dev==66315 and st.st_nlink==1 and st.st_mode&0o777==0o600,'physical_source_metadata'
  digest=sha(p)
  if p.name!='PACKAGE-SEAL.json':assert digest==seal['files'][p.name]['sha256'],'physical_source_bytes'
  out[p.name]=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode,st.st_uid,st.st_gid,digest]
 return out

def dependency_pins():
 pins={str(p):sha(p) for p in [pathlib.Path('/usr/bin/node'),pathlib.Path('/usr/bin/chromium'),pathlib.Path('/usr/lib/chromium/chromium')]}
 root=pathlib.Path('/home/corp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
 manifest={str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
 assert manifest and len(manifest)<5000,'playwright_inventory'
 assert json.loads((root/'package.json').read_text())['version']=='1.62.1','playwright_version'
 pins['playwright_files']=manifest
 return pins

def admit_mount(payload,actual_device):
 rows=payload.get('filesystems',[])
 expected={('systemd-1','autofs','0:63'),('/dev/loop0[/home/corp/autodata-evidence]','ext4','7:0')}
 assert len(rows)==2 and {(x.get('source'),x.get('fstype'),x.get('maj:min')) for x in rows}==expected,'exact_stacked_mount_rows'
 effective=next(x for x in rows if x['fstype']=='ext4')
 assert actual_device==os.makedev(7,0)==1792,'effective_mount_device'
 options=set(effective['options'].split(','))
 assert {'rw','nosuid','nodev'}<=options and not {'ro','noexec'}&options,'effective_mount_options'
 return effective

def runtime():
 from runtime_identity import baseline
 result=baseline();assert result==json.loads((BUILD/'baseline.json').read_text()),'public_private_runtime_changed'
 return result

def limits(free,inodes,profile_bytes,mem):
 if free<536870912:raise RuntimeError('tmpfs_free_floor')
 if inodes<=1000:raise RuntimeError('tmpfs_inode_floor')
 if profile_bytes>=PROFILE_STOP:raise RuntimeError('tmpfs_profile_early_stop')
 if profile_bytes>PROFILE_CAP:raise RuntimeError('tmpfs_profile_hard_cap')
 if mem<2147483648:raise RuntimeError('memory_reserve')

def port_free(port):
 with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:s.bind(('127.0.0.1',port))
def socket_owned(proc,port):
 owned=set()
 for fd in pathlib.Path('/proc',str(proc.pid),'fd').iterdir():
  try:target=os.readlink(fd)
  except FileNotFoundError:continue
  if target.startswith('socket:['):owned.add(target[8:-1])
 matches=[]
 for table in ['/proc/net/tcp','/proc/net/tcp6']:
  for row in pathlib.Path(table).read_text().splitlines()[1:]:
   f=row.split();address,p=f[1].split(':')
   if f[3]=='0A' and int(p,16)==port:
    assert address=='0100007F' and f[9] in owned,'listener_not_owned_loopback_only'
    matches.append(f[9])
 return bool(matches)
def asset_path(name):
 return '/workshop/' if name=='index.html' else '/workshop/'+name

def fetch(path,cap=2097152,expected_status=200,expected_location=None):
 assets=json.loads((PKG/'asset-manifest.json').read_text())
 assert path in {'/workshop/'+n for n in assets}|{'/workshop/'},'unexpected_local_asset_path'
 c=http.client.HTTPConnection('127.0.0.1',18432,timeout=2)
 try:
  c.request('GET',path);res=c.getresponse();raw=res.read(cap+1);location=res.getheader('Location')
  record={'path':path,'status':res.status,'location':location,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
  trace=R/'LOCAL-ASSET-REQUESTS.ndjson'
  with trace.open('a') as out:
   os.chmod(trace,0o600);out.write(json.dumps(record)+'\n');out.flush();os.fsync(out.fileno())
  assert res.status==expected_status and len(raw)<=cap,f'local_asset_status_or_size:{path}:{res.status}:{location}'
  assert location==expected_location,f'unexpected_local_asset_location:{path}:{location}'
  return raw,record
 finally:c.close()

def verify_asset(name,item):
 raw,record=fetch(asset_path(name))
 assert hashlib.sha256(raw).hexdigest()==item['sha256'] and len(raw)==item['bytes'],'embedded_asset_hash_or_size'
 return {'asset':name,**record}

def stop_owned(proc):
 if proc is None:return
 try:os.killpg(proc.pid,signal.SIGTERM)
 except ProcessLookupError:pass
 try:proc.wait(timeout=3)
 except subprocess.TimeoutExpired:
  try:os.killpg(proc.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  proc.wait(timeout=3)

class Resources:
 def __init__(self):
  v=os.statvfs('/home');self.home_base=v.f_bavail*v.f_frsize;self.owned_base=allocated(PKG);self.peak_profile=0;self.max_external=0;self.min_home=self.home_base
 def guard(self):
  v=os.statvfs('/home');free=v.f_bavail*v.f_frsize
  require_floor(free,v.f_favail,5368709120+134217728+67108864)
  owned=allocated(PKG);x=budget(free,v.f_favail,owned,0,self.home_base,self.owned_base)
  assert owned==self.owned_base,'immutable_physical_allocation_changed'
  v=os.statvfs('/tmp');mem=int(next(x.split()[1] for x in pathlib.Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
  assert not PROFILE.is_symlink(),'profile_symlink'
  profile=allocated(PROFILE);limits(v.f_bavail*v.f_frsize,v.f_favail,profile,mem)
  if PROFILE.exists():assert PROFILE.stat().st_dev==pathlib.Path('/tmp').stat().st_dev==46 and PROFILE.stat().st_mode&0o777==0o700,'profile_device_mode'
  assert R.stat().st_dev==1792 and allocated(R)<=FIXTURE_CAP,'fixture_offload_cap'
  v=os.statvfs(R);assert v.f_bavail*v.f_frsize>=1073741824,'offload_free'
  cg=pathlib.Path('/sys/fs/cgroup')/pathlib.Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
  while cg.is_relative_to('/sys/fs/cgroup'):
   mx=cg/'memory.max';cur=cg/'memory.current'
   if mx.exists() and mx.read_text().strip()!='max':assert int(mx.read_text())-int(cur.read_text())>=2147483648,'cgroup_reserve'
   if cg==pathlib.Path('/sys/fs/cgroup'):break
   cg=cg.parent
  self.peak_profile=max(self.peak_profile,profile);self.max_external=max(self.max_external,x['external_growth']);self.min_home=min(self.min_home,free)
  return {'home_free':free,'physical_owned':owned,'profile_allocated':profile,'mem_available':mem,'tmp_free':os.statvfs('/tmp').f_bavail*os.statvfs('/tmp').f_frsize,**x}

def reap_owned_descendants():
 # Linux subreaper makes detached Chromium descendants return to this runner.
 deadline=time.monotonic()+5;reaped=[]
 while True:
  while True:
   try:pid,_=os.waitpid(-1,os.WNOHANG)
   except ChildProcessError:pid=0
   if not pid:break
   reaped.append(pid)
  children=pathlib.Path('/proc',str(os.getpid()),'task',str(os.getpid()),'children').read_text().split()
  if not children:return {'reaped_descendants':reaped,'remaining':[]}
  for child in children:
   try:os.kill(int(child),signal.SIGKILL if time.monotonic()>=deadline-2 else signal.SIGTERM)
   except ProcessLookupError:pass
  if time.monotonic()>=deadline:raise RuntimeError('owned_descendants_not_reaped')
  time.sleep(.05)

def main():
 assert sys.argv[1:] in [['--dry-proof'],['--run-reviewed-fixture']],'explicit_mode_required'
 assert not any((R/n).exists() for n in ['fixture-attempted','LOCAL-ASSET-REQUESTS.ndjson','LOCAL-ASSET-RECEIPT.json','FIXTURE-RESULT.json','BROWSER-RESULT.json']),'fresh_one_attempt_paths_required'
 assert R==pathlib.Path('/home/corp/autodata-evidence/workshop-route-preview-09524db-fixture-20261116') and R==R.resolve(),'fixture_path'
 assert not PROFILE.exists() and not PROFILE.is_symlink(),'profile_must_be_absent'
 assert sha(R/'autodata-api')==BINARY_SHA and (R/'autodata-api').stat().st_mode&0o777==0o555,'fixture_binary'
 assert sha(BUILD/'guarded_build.py')=='97181f7f6e80c78f7ecd7286c6176009e44c4f3192e324becf97290b711359c9','reviewed_builder_pin'
 mounts=json.loads(subprocess.check_output(['/usr/bin/findmnt','--json','--list','-T',str(R),'-o','SOURCE,FSTYPE,OPTIONS,MAJ:MIN'],env=ENV,text=True))
 admit_mount(mounts,R.stat().st_dev)
 assert subprocess.check_output(['/usr/bin/findmnt','-n','-T','/tmp','-o','FSTYPE'],env=ENV,text=True).strip()=='tmpfs','tmp_mount'
 for port in [18432,18433]:port_free(port)
 original=source_snapshot();initial_runtime=runtime();resources=Resources();initial=resources.guard()
 helpers={p.name:sha(p) for p in R.iterdir() if p.suffix in ['.py','.cjs','.md']}
 dependencies=dependency_pins();resources.guard()
 if sys.argv[1]=='--dry-proof':
  for name,cmd in [('python-tests',['/usr/bin/python3','-B','-m','unittest','-v','test_fixture_guard','test_asset_routes']),('node-tests',['/usr/bin/node','--test','test_browser_policy.cjs','test_browser_routes.cjs','test_fixture_routes.cjs'])]:
   out=subprocess.run(cmd,cwd=R,env=ENV,capture_output=True,text=True,timeout=20,check=True)
   with (R/(name+'.log')).open('x') as f:f.write(out.stdout+out.stderr)
  assert source_snapshot()==original and runtime()==initial_runtime,'dry_source_runtime_drift'
  write_once(R/'DRY-FIXTURE-RECEIPT.json',{'status':'DRY_PROOF_PASS_NO_API_CHROMIUM_OR_BROWSER_DISPATCH','checkpoint':'91891acb','source_sha':'09524db599a82e7f8c79a1d8fb43bfadc6bbe2f3','source_package_seal':SEAL_SHA,'binary_sha256':BINARY_SHA,'binary_mode':'0555','source_mode':'0600','physical_source_unchanged':True,'profile':str(PROFILE),'profile_absent':not PROFILE.exists(),'profile_cap':PROFILE_CAP,'profile_stop':PROFILE_STOP,'profile_burst':PROFILE_CAP-PROFILE_STOP,'fixture_cap':FIXTURE_CAP,'initial_capacity':initial,'final_capacity':resources.guard(),'helpers':helpers,'dependencies':dependencies,'runtime':initial_runtime,'test_logs':{n:sha(R/n) for n in ['python-tests.log','node-tests.log']},'utc':datetime.now(timezone.utc).isoformat()})
  print('DRY_PROOF_PASS_NO_DISPATCH');return
 dry=json.loads((R/'DRY-FIXTURE-RECEIPT.json').read_text());assert dry['helpers']==helpers,'fixture_helpers_changed_since_review'
 assert dry['dependencies']==dependencies,'external_fixture_dependency_changed'
 write_once(R/'fixture-attempted',{'utc':datetime.now(timezone.utc).isoformat(),'source':BINARY_SHA})
 assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0,'subreaper_unavailable'
 PROFILE.mkdir(mode=0o700)
 for name in ['temp','config','cache','crashes']:(PROFILE/name).mkdir(mode=0o700)
 api=chrome=node=None;logs=[];status='FAIL';error=None;deadline=time.monotonic()+120
 def guard():
  if time.monotonic()>=deadline:raise RuntimeError('fixture_total_deadline')
  return resources.guard()
 def launch(name,cmd,env):
  guard();log=(R/(name+'.log')).open('xb');logs.append(log)
  return subprocess.Popen(cmd,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:
  api=launch('api',[str(R/'autodata-api')],{**ENV,'AUTODATA_ENV':'test','AUTODATA_AUTH_MODE':'local','AUTODATA_PUBLIC_ORIGIN':'http://127.0.0.1:18432','AUTODATA_API_ADDR':'127.0.0.1:18432','AUTODATA_READINESS_MODE':'static','AUTODATA_COMMERCE_MODE':'disabled'})
  for _ in range(50):
   guard();assert api.poll() is None,'api_early_exit'
   if socket_owned(api,18432):break
   time.sleep(.1)
  else:raise RuntimeError('api_listener_missing')
  assert sha(pathlib.Path('/proc',str(api.pid),'exe'))==BINARY_SHA,'loaded_fixture_binary'
  assets=json.loads((PKG/'asset-manifest.json').read_text())
  asset_results=[]
  for name,item in assets.items():
   guard();asset_results.append(verify_asset(name,item))
  guard();_,redirect=fetch('/workshop/index.html',expected_status=301,expected_location='./')
  write_once(R/'LOCAL-ASSET-RECEIPT.json',{'binary_sha256':BINARY_SHA,'assets':asset_results,'index_redirect':redirect,'all15_verified':len(asset_results)==15})
  flags=['/usr/bin/chromium','--headless=new','--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--disable-component-update','--disable-domain-reliability','--disable-sync','--disable-extensions','--no-first-run','--disable-client-side-phishing-detection','--metrics-recording-only','--disable-crash-reporter','--disable-breakpad','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--remote-debugging-address=127.0.0.1','--remote-debugging-port=18433','--user-data-dir='+str(PROFILE/'chromium'),'--crash-dumps-dir='+str(PROFILE/'crashes'),'about:blank']
  browser_env={**ENV,'TMPDIR':str(PROFILE/'temp'),'XDG_CONFIG_HOME':str(PROFILE/'config'),'XDG_CACHE_HOME':str(PROFILE/'cache')}
  chrome=launch('chromium',flags,browser_env)
  for _ in range(100):
   guard();assert chrome.poll() is None,'chromium_early_exit'
   if socket_owned(chrome,18433):break
   time.sleep(.1)
  else:raise RuntimeError('chromium_listener_missing')
  assert sha(pathlib.Path('/proc',str(chrome.pid),'exe'))==dependencies['/usr/lib/chromium/chromium'],'loaded_chromium_identity'
  node=launch('browser-node',['/usr/bin/node',str(R/'browser_fixture.cjs'),'--reviewed-local-only'],browser_env)
  wait_guarded(node,guard,timeout=min(80,deadline-time.monotonic()),interval=.5)
  assert json.loads((R/'BROWSER-RESULT.json').read_text())['passed'],'browser_result'
  status='PASS'
 except BaseException as e:error=type(e).__name__+':'+str(e)
 finally:
  for child in [node,chrome,api]:stop_owned(child)
  cleanup={'remaining':['not_verified']}
  try:cleanup=reap_owned_descendants()
  except BaseException as e:status='FAIL';error=type(e).__name__+':'+str(e)
  for log in logs:log.close()
  source_ok=runtime_ok=False
  try:
   guard();source_ok=source_snapshot()==original;runtime_ok=runtime()==initial_runtime
   assert source_ok and runtime_ok,'final_runtime_or_source_drift'
  except BaseException as e:status='FAIL';error=type(e).__name__+':'+str(e)
  write_once(R/'FIXTURE-RESULT.json',{'status':status,'error':error,'source_binary_sha256':BINARY_SHA,'source_package_unchanged':source_ok,'public_private_unchanged':runtime_ok,'cleanup':cleanup,'all_owned_children_reaped':all(p is None or p.poll() is not None for p in [node,chrome,api]),'profile_peak':resources.peak_profile,'max_external_physical_growth':resources.max_external,'min_home_free':resources.min_home,'browser_receipt_sha256':sha(R/'BROWSER-RESULT.json') if (R/'BROWSER-RESULT.json').exists() else None,'utc':datetime.now(timezone.utc).isoformat()})
 if status!='PASS':raise RuntimeError(error)
 print('LOCAL_SYNTHETIC_FIXTURE_PASS')
if __name__=='__main__':main()
