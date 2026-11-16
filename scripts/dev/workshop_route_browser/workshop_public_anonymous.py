"""Offloaded, one-use anonymous browser controller; default is no-dispatch."""
import argparse,ctypes,hashlib,importlib.util,ipaddress,json,os,select,shutil,signal,socket,socketserver,stat,subprocess,sys,tempfile,threading,time
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
CLEAN={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
class Refused(RuntimeError):pass
def need(v,code):
 if not v:raise Refused(code)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def syncdir(p):
 fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
def reserve_marker(path,data):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 syncdir(path.parent)
def allocation(p):
 total=p.stat().st_blocks*512
 for x in p.rglob('*'):
  try:total+=x.lstat().st_blocks*512
  except (FileNotFoundError,NotADirectoryError):pass
 return total
def capacity_errors(v):
 e=[]
 for condition,code in [(v['home']<=5570035712,'home_entry'),(v['root']<=2181038080,'root_floor'),(v['docker']<=813694976,'docker_floor'),(v['offload']<=1073741824,'offload_floor'),(v['tmp']<536870912,'tmp_floor'),(v['memory']<1073741824,'memory_floor'),(v['growth']>=33554432,'home_guard'),(v['tmp_growth']>=100663296,'tmp_guard'),(v['artifact']>4194304,'evidence_cap')]:
  if condition:e.append(code)
 return e
def capacity(m,baseline=None,profile=None):
 def free(p):
  v=os.statvfs(p);need(v.f_favail>1000,'inodes');return v.f_bavail*v.f_frsize
 values={k:free(p) for k,p in [('home','/home'),('root','/'),('docker','/mnt/openfoam/docker'),('offload',ROOT),('tmp','/tmp')]}
 values.update(memory=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024,growth=max(0,(baseline or values)['home']-values['home']),tmp_growth=allocation(profile) if profile and profile.exists() else 0,artifact=allocation(ROOT))
 need(not capacity_errors(values),'capacity_guard');return values
def filesystem_type(path):
 resolved=str(path.resolve());matches=[]
 for row in Path('/proc/self/mountinfo').read_text().splitlines():
  left,right=row.split(' - ',1);mount=left.split()[4]
  if resolved==mount or resolved.startswith(mount.rstrip('/')+'/'):matches.append((len(mount),right.split()[0]))
 return max(matches)[1]
def load(reviewed):
 seal=ROOT/'PACKAGE-SEAL.json';need(len(reviewed)==64 and sha(seal)==reviewed,'review_hash');s=json.loads(seal.read_text());need(ROOT.resolve()==ROOT and ROOT.stat().st_dev!=Path('/home').stat().st_dev and filesystem_type(ROOT)=='ext4' and ROOT.stat().st_uid==os.getuid() and stat.S_IMODE(ROOT.stat().st_mode)==0o700,'offload_root')
 for name,pin in s['files'].items():
  p=ROOT/name;st=p.lstat();need(not p.is_symlink() and p.is_file() and st.st_nlink==1 and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o600 and sha(p)==pin,'sealed_file')
 m=json.loads((ROOT/'manifest.json').read_text());need(m['root']==str(ROOT),'root_pin')
 guards={}
 for name,pin in m['dependencies'].items():
  p=Path(name);before=p.stat();need(sha(p)==pin and p.stat()==before,'dependency_drift');guards[name]=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns,before.st_mode)
 m['_reviewed_seal']=reviewed;m['_sealed_files']=s['files'];m['_dependency_guard']=guards;return m
def runtime_guard(m,live=False):
 need(sha(ROOT/'PACKAGE-SEAL.json')==m['_reviewed_seal'],'seal_drift')
 for name,pin in m['_sealed_files'].items():need(sha(ROOT/name)==pin,'control_drift')
 for name,want in m['_dependency_guard'].items():
  st=Path(name).stat();need((st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode)==want,'toolchain_guard')
 original=Path(m['release_manifest']);need(sha(original)==m['release_manifest_sha256'],'release_manifest');b=json.loads(original.read_text());module=Path(m['release_helper']);need(sha(module)==m['release_helper_sha256'],'release_helper')
 spec=importlib.util.spec_from_file_location('release_dependency',module);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);r.payload_check(b);r.env_policy(r.ENV.read_bytes());r.private_check(b,False)
 for name,want in b['baseline']['files'].items():
  if name==str(r.OVERRIDE):want={**want,'sha256':b['target_override_sha256']}
  need(r.metadata(Path(name))==want,'public_file_drift')
 p=Path('/proc')/str(m['pid']);exe=Path(m['install_binary']);need((p/'stat').read_text().split()[21]==m['start_ticks'] and os.readlink(p/'exe')==str(exe) and sha(p/'exe')==m['binary_sha256']==sha(exe),'public_runtime')
 need((p/'exe').stat().st_ino==exe.stat().st_ino and exe.stat().st_uid==0 and stat.S_IMODE(exe.stat().st_mode)==0o555,'public_inode_mode')
 if live:
  cmd=['/usr/bin/sudo','-n','/usr/bin/env','-i',*['%s=%s'%x for x in CLEAN.items() if x[0]!='PYTHONDONTWRITEBYTECODE'],'/usr/bin/python3','-I',m['physical_release_helper'],'--reviewed-manifest-sha256',m['release_manifest_sha256'],'--reviewed-helper-sha256',m['release_helper_sha256'],'--root-execute','--phase','candidate-check']
  result=subprocess.run(cmd,env=CLEAN,capture_output=True,timeout=40);need(result.returncode==0 and len(result.stdout)<4096 and json.loads(result.stdout)=={'phase':'candidate-check','passed':True},'privileged_readonly_guard')
def valid_connect(line,headers):
 if line!=b'CONNECT autodata.cars.tk:443 HTTP/1.1\r\n' or len(headers)>16 or sum(map(len,headers))>4096:return False
 host=[]
 for item in headers:
  try:key,value=item.decode('ascii').strip().split(':',1)
  except (UnicodeError,ValueError):return False
  if key.lower() not in ('host','proxy-connection','user-agent'):return False
  if key.lower()=='host':host.append(value.strip())
 return host==['autodata.cars.tk:443']
def public_addresses():
 previous=signal.getsignal(signal.SIGALRM);timer=signal.getitimer(signal.ITIMER_REAL);started=time.monotonic()
 def expired(*args):raise Refused('dns_deadline')
 signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,min(5,timer[0]) if timer[0] else 5)
 try:addresses=sorted({x[4][0] for x in socket.getaddrinfo('autodata.cars.tk',443,socket.AF_INET,socket.SOCK_STREAM)})
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
  if timer[0]:signal.setitimer(signal.ITIMER_REAL,max(.001,timer[0]-(time.monotonic()-started)),timer[1])
 need(addresses and all(ipaddress.ip_address(x).is_global and not ipaddress.ip_address(x).is_multicast for x in addresses),'upstream_address');return addresses
class ProxyState:
 def __init__(self,ips):self.ips=ips;self.lock=threading.Lock();self.active=0;self.total=0;self.bytes=0;self.denied=0;self.end=time.monotonic()+120;self.failed=False;self.header_rejected=0;self.upstream_attempted=0;self.upstream_connected=0;self.upstream_failed=0;self.client_io_failed=0
 def count(self,name):
  with self.lock:setattr(self,name,getattr(self,name)+1)
 def enter(self):
  with self.lock:
   if self.active>=16 or self.total>=128 or time.monotonic()>=self.end:self.failed=True;return False
   self.active+=1;self.total+=1;return True
 def account(self,n):
  with self.lock:self.bytes+=n;self.failed=self.failed or self.bytes>33554432;return not self.failed
class Tunnel(socketserver.StreamRequestHandler):
 def handle(self):
  s=self.server.state
  if not s.enter():return
  try:
   phase='headers';self.connection.settimeout(5);line=self.rfile.readline(4097);headers=[]
   while True:
    item=self.rfile.readline(4097)
    if item==b'\r\n':break
    if not item or len(item)>4096 or len(headers)>=16:s.count('denied');s.count('header_rejected');return
    headers.append(item)
   if not valid_connect(line,headers):s.count('denied');s.count('header_rejected');return
   phase='upstream_connect';s.count('upstream_attempted')
   with socket.create_connection((s.ips[0],443),timeout=5) as upstream:
    s.count('upstream_connected');phase='tunnel_io';self.wfile.write(b'HTTP/1.1 200 Connection Established\r\n\r\n');self.wfile.flush();sockets=[self.connection,upstream]
    while time.monotonic()<s.end and not s.failed:
     ready,_,_=select.select(sockets,[],[],.25)
     for source in ready:
      data=source.recv(16384)
      if not data:return
      if not s.account(len(data)):return
      (upstream if source is self.connection else self.connection).sendall(data)
  except (OSError,ValueError):s.count('upstream_failed' if phase=='upstream_connect' else 'client_io_failed')
  finally:
   with s.lock:s.active-=1
class Proxy(socketserver.ThreadingTCPServer):
 allow_reuse_address=False;daemon_threads=True
 def handle_error(self,*args):self.state.failed=True
def proc_identity(pid):
 try:
  values=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return str(Path('/proc',str(pid)).stat().st_uid),values[19]
 except OSError:return None
def descendants(parent):
 result={};parents={parent}
 for _ in range(8):
  found=False
  for p in Path('/proc').iterdir():
   if p.name.isdigit():
    ident=proc_identity(int(p.name))
    if ident:
     try:ppid=int((p/'stat').read_text().rsplit(')',1)[1].split()[1])
     except (OSError,ValueError):continue
     if ppid in parents and int(p.name) not in parents:result[int(p.name)]=ident;parents.add(int(p.name));found=True
  if not found:break
 return result
def kill_owned(owned):
 for pid,ident in reversed(list(owned.items())):
  if proc_identity(pid)==ident:
   try:os.kill(pid,signal.SIGKILL)
   except (ProcessLookupError,PermissionError):pass
def persist(name,value):reserve_marker(ROOT/name,(json.dumps(value,sort_keys=True)+'\n').encode())
def run_once(m,seal):
 reserve_marker(ROOT/'browser-attempted',(seal+'\n').encode())
 profile=None;server=None;child=None;owned={};failure='';passed=False;residual={};proxy_state=None
 try:
  baseline=capacity(m);runtime_guard(m,True);need(not list(ROOT.glob('viewport-*.png')),'screenshots_exist');need(ctypes.CDLL(None).prctl(36,1,0,0,0)==0,'subreaper')
  need(Path('/tmp').stat().st_dev!=Path('/home').stat().st_dev and any(x.split()[1]=='/tmp' and x.split()[2]=='tmpfs' for x in Path('/proc/mounts').read_text().splitlines()),'tmpfs_required')
  profile=Path(tempfile.mkdtemp(prefix='ad-pa-',dir='/tmp'));need(len(str(profile))<40 and stat.S_IMODE(profile.stat().st_mode)==0o700,'profile_path');env={**CLEAN,'HOME':str(profile),'TMPDIR':str(profile),'TMP':str(profile),'TEMP':str(profile),'AUTODATA_ANON_SUPERVISOR_PID':str(os.getpid()),'AUTODATA_ANON_REVIEWED_SEAL':seal}
  proxy_state=ProxyState(public_addresses());server=Proxy(('127.0.0.1',18434),Tunnel);server.state=proxy_state;threading.Thread(target=server.serve_forever,daemon=True).start()
  child=subprocess.Popen(['/usr/bin/node',str(ROOT/'workshop_public_anonymous.cjs'),'--run-reviewed'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);owned[child.pid]=proc_identity(child.pid);end=time.monotonic()+120;last=0
  while child.poll() is None:
   owned.update(descendants(os.getpid()));capacity(m,baseline,profile);need(not proxy_state.failed,'proxy_cap');need(time.monotonic()<end,'browser_deadline')
   if time.monotonic()-last>=1:runtime_guard(m);last=time.monotonic()
   time.sleep(.2)
  output,errors=child.communicate();need(child.returncode==0 and len(output)<4096 and len(errors)<65536,'browser_child');runtime_guard(m,True);capacity(m,baseline,profile);passed=True
 except BaseException:failure='anonymous_browser_refused_or_failed'
 finally:
  owned.update(descendants(os.getpid()));kill_owned(owned)
  if child:
   try:child.communicate(timeout=5)
   except subprocess.TimeoutExpired:pass
  if server:
   server.shutdown();server.server_close();drain=time.monotonic()+6
   while server.state.active and time.monotonic()<drain:time.sleep(.05)
   passed=passed and server.state.active==0
  end=time.monotonic()+3
  while time.monotonic()<end:
   try:
    pid,_=os.waitpid(-1,os.WNOHANG)
    if pid==0:time.sleep(.05)
   except ChildProcessError:break
  left={p:i for p,i in owned.items() if proc_identity(p)==i};port_absent=not any(row.split()[1].endswith(':4802') and row.split()[3]=='0A' for row in Path('/proc/net/tcp').read_text().splitlines()[1:]);passed=passed and not left and port_absent
  if profile:
   residual={'path':str(profile),'bytes':allocation(profile),'entries':sum(1 for _ in profile.rglob('*')),'owned_remaining':len(left)}
   if not left:shutil.rmtree(profile);residual['removed_after_reap']=True
  persist('OUTCOME.json',{'passed':passed,'failure':failure,'remaining_owned':len(left),'proxy_listener_absent':port_absent,'tmpfs_metadata':residual,'proxy':None if proxy_state is None else {'total':proxy_state.total,'denied':proxy_state.denied,'bytes':proxy_state.bytes,'header_rejected':proxy_state.header_rejected,'upstream_attempted':proxy_state.upstream_attempted,'upstream_connected':proxy_state.upstream_connected,'upstream_failed':proxy_state.upstream_failed,'client_io_failed':proxy_state.client_io_failed},'no_service_mutation':True,'no_signin_or_provider_or_stripe_acceptance':True})
 return 0 if passed else 1
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--reviewed-seal',required=True);p.add_argument('--run-once',action='store_true');args=p.parse_args(argv)
 try:
  m=load(args.reviewed_seal);runtime_guard(m);v=capacity(m)
  if not args.run_once:print(json.dumps({'check':'PASS','dispatches':0,'browser_dispatched':False,'capacity':v}));return 0
  return run_once(m,args.reviewed_seal)
 except BaseException:print(json.dumps({'passed':False,'failure':'anonymous_admission_refused','browser_dispatched':False}));return 1
if __name__=='__main__':raise SystemExit(main())
