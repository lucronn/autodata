import pathlib,os,sys,subprocess,json,hashlib,time,tarfile,signal,importlib.util
from datetime import datetime,timezone
R=pathlib.Path(__file__).resolve().parent
REPO=pathlib.Path('/home/corp/autodata-evidence/workshop-route-release-integration-20261116')
PKG=pathlib.Path('/home/corp/.local/state/autodata-workshop-route-preview-09524db-20261116')
SHA='09524db599a82e7f8c79a1d8fb43bfadc6bbe2f3';TREE='983f9d6bc294f16bf9e1a4c0d490d8a8c24bfc42'
FLOOR=5368709120;CAP=134217728;HOME=pathlib.Path('/home');CACHE=pathlib.Path('/home/corp/autodata-evidence/workshop-client-preview-a82b31d-attempt2-build-20261115/cache');WORK=R/'work';LOG=R/'logs'
CHILD={'PATH':'/home/corp/go-sdk/bin:/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','GOROOT':'/home/corp/go-sdk','GOPATH':'/home/corp/go','GOMODCACHE':'/home/corp/go/pkg/mod','GOCACHE':str(CACHE),'GOTMPDIR':str(WORK/'temp'),'TMPDIR':str(WORK/'temp'),'GOPROXY':'off','GOSUMDB':'off','GOTOOLCHAIN':'local','CGO_ENABLED':'0','GOMAXPROCS':'2','GOMEMLIMIT':'1GiB','GOTELEMETRY':'off','GOFLAGS':'-mod=readonly','PYTHONDONTWRITEBYTECODE':'1'}
spec=importlib.util.spec_from_file_location('h',R/'identity_helpers.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
from budget_guard import budget,ABSOLUTE,DRIFT,PREP,INSTALL,ENTRY
INSTALL_ROOT=pathlib.Path('/usr/local/libexec/autodata/workshop-route-preview-09524db')
assert not PKG.exists() and not INSTALL_ROOT.exists(),'candidate_paths_already_exist'
for d in [CACHE,WORK,LOG,WORK/'temp']:d.mkdir(mode=0o700,exist_ok=True)
assert R.stat().st_dev!=HOME.stat().st_dev and R.stat().st_dev==1792,'offloaded_device'
HOME_BASE=os.statvfs(HOME).f_bavail*os.statvfs(HOME).f_frsize
require_entry=HOME_BASE>ENTRY
assert require_entry,'strict_entry_admission'
from capacity_guard import allocated,require_floor,wait_guarded
cache_base=allocated(CACHE);peaks={'scratch':0,'cache':0,'package':0,'min_home_free':2**63,'min_mem_available':2**63,'max_external_growth':0};steps=[]
def guard():
 v=os.statvfs(HOME);free=v.f_bavail*v.f_frsize
 require_floor(free,v.f_favail,ABSOLUTE+DRIFT+INSTALL)
 package=allocated(PKG)
 accounting=budget(free,v.f_favail,package,0,HOME_BASE,0)
 peaks['max_external_growth']=max(peaks['max_external_growth'],accounting['external_growth'])
 assert not INSTALL_ROOT.exists(),'unexpected_install_allocation'
 scratch=allocated(WORK);cache=allocated(CACHE)
 mem=int(next(x.split()[1] for x in pathlib.Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
 for k,n in [('scratch',scratch),('cache',cache),('package',package)]:peaks[k]=max(peaks[k],n)
 peaks['min_home_free']=min(peaks['min_home_free'],free);peaks['min_mem_available']=min(peaks['min_mem_available'],mem)
 assert package<=CAP,'package_cap';assert free>accounting['required_free_exclusive'],'home_reservation';assert v.f_favail>1000,'home_inodes';assert scratch<=1073741824,'scratch_cap';assert cache<=cache_base+134217728,'cache_cap';assert mem>=2147483648,'memory_reserve'
 off=os.statvfs(R);assert off.f_bavail*off.f_frsize>=1073741824,'offloaded_reserve'
 cg=pathlib.Path('/sys/fs/cgroup')/pathlib.Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
 while cg.is_relative_to('/sys/fs/cgroup'):
  mx=cg/'memory.max';cur=cg/'memory.current'
  if mx.exists() and mx.read_text().strip()!='max':assert int(mx.read_text())-int(cur.read_text())>=2147483648,'cgroup_reserve'
  if cg==pathlib.Path('/sys/fs/cgroup'):break
  cg=cg.parent
 return {'home_free':free,'package':package,'scratch':scratch,'cache':cache,'mem_available':mem,**accounting}
def run(name,cmd,cwd=REPO,timeout=600):
 guard();started=time.monotonic();log=LOG/(name+'.log');print('START '+name,flush=True)
 with log.open('xb') as out:
  proc=subprocess.Popen(cmd,cwd=cwd,env=CHILD,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
  wait_guarded(proc,guard,timeout=timeout)
 step={'name':name,'seconds':round(time.monotonic()-started,3),'log':str(log),'sha256':h.sha(log.read_bytes()),'exit':proc.returncode};steps.append(step);print(json.dumps(step),flush=True);guard()
def baseline():
 pid=subprocess.check_output(['/usr/bin/systemctl','show','autodata-api.service','-p','MainPID','--value'],text=True,env=h.CHILD_ENV,timeout=5).strip();exe=os.readlink('/proc/'+pid+'/exe')
 names=[h.ENV,h.OVERRIDE,h.DEPENDENCY,pathlib.Path(exe)];files={str(p):h.metadata(p) for p in names};assert pid=='1293423' and exe=='/usr/local/libexec/autodata/workshop-client-preview-a82b31d-a2/autodata-api','api_identity'
 assert files[exe]['sha256']=='bb11d963666e4fc44f6b0879ebb55a14cf7b2ca221bad6ffa8d3282d5360203e','binary_pin'
 assert files[str(h.DEPENDENCY)]['sha256']=='493beef2c5d9fe2190995c1b63ab9c3f094f58f3cda3930048031b6a57c5ecd3','dependency_pin'
 assert files[str(h.ENV)]['sha256']=='74a93e2198fe8b024fadce9a26845990f3c15cbc9681ddd873a704e13a16aa03' and files[str(h.OVERRIDE)]['sha256']=='b9d00378ce917cc53d515e7460774712c5e179ae9bfefed3bee7886b55b74c7c','env_override'
 assert h.running_binary_matches(pid,exe,files[exe]),'loaded_binary'
 cmd=['/usr/bin/docker','--config',str(R/'docker-cli-config'),'--host','unix:///var/run/docker.sock','inspect','17295fae5fe60b5b9c78b81206a3a0c8f3e202b811093f91ebb821babe648f3e']
 x=json.loads(subprocess.check_output(cmd,env=h.CHILD_ENV,timeout=5))[0];identity=h.private_identity(x);assert identity['running'] and identity['pid']==1552737 and identity['restart_count']==0,'private_identity'
 assert identity['id']=='17295fae5fe60b5b9c78b81206a3a0c8f3e202b811093f91ebb821babe648f3e' and identity['image']=='sha256:3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7','private_container_image_pin'
 assert identity['started_at']=='2026-11-15T04:15:19.01131429Z' and identity['env_sha256']=='cd689562807dab0e495a88105bbc66b54eaa97194fb1b02e5faa1ea7a119fe06','private_lifecycle_env_pin'
 root=pathlib.Path('/home/corp/autodata-candidate/private-configuration-budget-272aeea-20261115');m=json.loads((root/'manifest.json').read_text());assert h.sha((root/'source.tar').read_bytes())==m['archive_sha256']=='693a088572e589a33f59cf509550e072c81376d35050a63ed6dac5b9b397dabd','private_archive'
 assert m['source_sha']=='272aeeaad8399c305468e5d486cc391d7340f6a4','private_source_pin'
 for name,digest in m['files'].items():assert h.sha((root/'source'/name).read_bytes())==digest,'private_source_file'
 return {'api_pid':int(pid),'api_start_ticks':pathlib.Path('/proc',pid,'stat').read_text().split(') ')[1].split()[19],'api_exe':exe,'files':files,'ingestion':identity,'private_start_ticks':pathlib.Path('/proc',str(identity['pid']),'stat').read_text().split(') ')[1].split()[19],'private_source':{'root':str(root/'source'),'archive_path':str(root/'source.tar'),'archive_sha256':m['archive_sha256'],'source_sha':m['source_sha'],'guard_sha256':h.source_guard(root/'source')},'target_env_sha256':files[str(h.ENV)]['sha256']}
try:
 initial=guard();b=baseline();guard()
 if sys.argv[1:]==['--dry-proof']:
  tests=subprocess.run(['/usr/bin/python3','-B','-m','unittest','-v','test_capacity_guard','test_budget_guard'],cwd=R,env=CHILD,capture_output=True,text=True,check=True)
  (R/'guard-tests.log').write_text(tests.stdout+tests.stderr)
  receipt={'status':'DRY_GUARD_PASS_NO_BUILD_DISPATCH','checkpoint':'91891acb','source_sha':SHA,'source_tree':TREE,'paths':{'offloaded':str(R),'physical':str(PKG),'future_install':str(INSTALL_ROOT)},'physical_and_install_absent':not PKG.exists() and not INSTALL_ROOT.exists(),'entry_exclusive':ENTRY,'absolute_reserve':ABSOLUTE,'drift_reserve':DRIFT,'prep_cap':PREP,'install_reservation':INSTALL,'external_stop':100663296,'burst_margin':33554432,'capacity':guard(),'baseline':b,'helpers':{p.name:h.sha(p.read_bytes()) for p in R.glob('*.py')},'tests_sha256':h.sha((R/'guard-tests.log').read_bytes()),'utc':datetime.now(timezone.utc).isoformat()}
  with (R/'DRY-GUARD-RECEIPT.json').open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n')
  print(json.dumps(receipt,indent=2));sys.exit(0)
 assert sys.argv[1:]==['--run-reviewed-build'],'explicit_build_argument_required'
 assert list(WORK.iterdir())==[WORK/'temp'] and not any((WORK/'temp').iterdir()) and not any(LOG.iterdir()),'fresh_work_cache_logs_required'
 dry=json.loads((R/'DRY-GUARD-RECEIPT.json').read_text());assert dry['status']=='DRY_GUARD_PASS_NO_BUILD_DISPATCH'
 for name,digest in dry['helpers'].items():assert h.sha((R/name).read_bytes())==digest,'helper_changed_since_dry_proof'
 assert b==dry['baseline'],'runtime_changed_since_dry_proof'
 with (R/'build-attempted').open('x') as marker:marker.write(SHA+'\n');marker.flush();os.fsync(marker.fileno())
 with (R/'baseline.json').open('x') as f:f.write(json.dumps(b,indent=2)+'\n')
 assert subprocess.check_output(['git','rev-parse',SHA+'^{tree}'],cwd=REPO,text=True).strip()==TREE
 run('archive',['git','archive','--format=tar','--output='+str(WORK/'source.tar'),SHA])
 source=WORK/'source';source.mkdir(mode=0o700)
 with tarfile.open(WORK/'source.tar') as archive:
  assert all(m.isfile() or m.isdir() for m in archive.getmembers()),'archive_special_file'
  archive.extractall(source,filter='data')
 guard();files={}
 for index,line in enumerate(subprocess.check_output(['git','ls-tree','-r','--name-only',SHA],cwd=REPO,text=True).splitlines()):
  if index%100==0:guard()
  raw=subprocess.check_output(['git','show',SHA+':'+line],cwd=REPO);assert (source/line).read_bytes()==raw,'source_mismatch';files[line]=h.sha(raw)
 (R/'source-manifest.json').write_text(json.dumps({'source_sha':SHA,'source_tree':TREE,'archive_sha256':h.sha((WORK/'source.tar').read_bytes()),'files':files},indent=2)+'\n')
 run('api-go-tests',['/home/corp/go-sdk/bin/go','test','-p','2','./...'],cwd=source/'apps/api-go')
 run('contracts-go-tests',['/home/corp/go-sdk/bin/go','test','-p','2','./...'],cwd=source/'packages/contracts/go')
 run('workshop-node-tests',['/usr/bin/node','--test','apps/api-go/workshop-client.test.mjs','apps/api-go/workshop-demo.test.mjs'],cwd=source)
 run('build',['/home/corp/go-sdk/bin/go','build','-p','2','-trimpath','-o',str(WORK/'autodata-api'),'.'],cwd=source/'apps/api-go')
 guard();assert baseline()==b,'baseline_drift'
 assets={str(p.relative_to(source/'apps/api-go/workshop')):{'sha256':h.sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted((source/'apps/api-go/workshop').rglob('*')) if p.is_file()}
 assert len(assets)==15 and sum(x['bytes'] for x in assets.values())==json.loads((R/'expected-assets.json').read_text())['total_bytes'],'asset_inventory'
 (R/'asset-manifest.json').write_text(json.dumps(assets,indent=2)+'\n')
 assert (WORK/'source.tar').stat().st_size<=34*1048576 and (WORK/'autodata-api').stat().st_size<=60*1048576,'physical_component_caps'
 PKG.mkdir(mode=0o700);guard()
 def copy_sealed(src,name):
  guard();dest=PKG/name
  with src.open('rb') as inp,dest.open('xb') as out:
   os.chmod(dest,0o600)
   while True:
    guard();chunk=inp.read(1048576)
    if not chunk:break
    out.write(chunk);out.flush();guard()
   os.fsync(out.fileno())
  assert h.sha(src.read_bytes())==h.sha(dest.read_bytes()),'physical_copy_hash'
  guard()
 for src,name in [(WORK/'source.tar','source.tar'),(WORK/'autodata-api','autodata-api'),(R/'source-manifest.json','source-manifest.json'),(R/'asset-manifest.json','asset-manifest.json'),(R/'DRY-GUARD-RECEIPT.json','DRY-GUARD-RECEIPT.json')]:copy_sealed(src,name)
 for src in sorted(R.glob('*.py')):copy_sealed(src,src.name)
 for src in sorted(LOG.glob('*.log')):copy_sealed(src,'test-'+src.name)
 fd=os.open(PKG,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 guard();assert baseline()==b,'final_baseline_drift'
 result={'status':'BUILD_TESTS_PASS_NOT_DEPLOYED','planning_checkpoint':'91891acb','physical_package':str(PKG),'assets':assets,'physical_files':{p.name:{'sha256':h.sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(PKG.iterdir()) if p.is_file()},'source_sha':SHA,'source_tree':TREE,'archive_sha256':h.sha((WORK/'source.tar').read_bytes()),'archive_bytes':(WORK/'source.tar').stat().st_size,'binary_sha256':h.sha((WORK/'autodata-api').read_bytes()),'binary_bytes':(WORK/'autodata-api').stat().st_size,'steps':steps,'peaks':peaks,'cache_baseline':cache_base,'initial_capacity':initial,'final_capacity':guard(),'utc':datetime.now(timezone.utc).isoformat()}
 
 with (R/'BUILD-RESULT.json').open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
 copy_sealed(R/'BUILD-RESULT.json','BUILD-RESULT.json')
 fd=os.open(PKG,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 print(json.dumps(result,indent=2),flush=True)
except SystemExit as error:
 if error.code:raise
except BaseException as error:
 with (R/'BUILD-STOP.json').open('x') as f:f.write(json.dumps({'status':'STOP','error':str(error),'type':type(error).__name__,'steps':steps,'peaks':peaks},indent=2)+'\n')
 print('STOP '+str(error),flush=True);raise
