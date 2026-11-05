#!/usr/bin/python3 -I
"""Fixed staging-only host preparation. No network or credential discovery."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid

MIB = 1048576
BUNDLE = '/var/lib/autodata-bootstrap/bundle'
PACKAGES = '/var/lib/autodata-bootstrap/packages'
RECEIPTS = '/var/lib/autodata-bootstrap/receipts'
DATA = '/var/lib/autodata'
RUN = '/run/autodata'
DEVICE = '/dev/disk/by-id/google-autodata-data'
POLICY = '/usr/sbin/policy-rc.d'
ENV = {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/nonexistent','LANG':'C','LC_ALL':'C'}
DOCKER = ['/usr/bin/docker','--host','unix:///var/run/docker.sock']
COMMON = ('schema_version','operation','authorization_id','expires_at','source_sha','service_config_sha256','bundle_inventory_sha256','environment')
PROVISION = ('boot_id','machine_id_sha256','data_device_major_minor','data_device_serial','data_device_bytes','data_filesystem_uuid','packages')
PREPARE = ('manifest_raw_sha256','publisher_acceptance_sha256')
IMAGES = ('images','registry_config_sha256')
DATABASE = ('bootstrap_roles_sha256','runtime_grants_sha256','pgdata_initial_empty','image_cache_receipt_sha256','resume')
REQUIRED_PACKAGES = {'docker-ce','docker-ce-cli','docker-compose-plugin','containerd.io','nftables','util-linux','e2fsprogs','python3'}

class Rejected(ValueError):
    def __init__(self): super().__init__('host operation rejected')

def require(value):
    if not value: raise Rejected()

def digest(data): return hashlib.sha256(data).hexdigest()
def metadata(value): return (value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns)
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def match(value, pattern): return type(value) is str and re.fullmatch(pattern,value) is not None

def strict_json(data):
    def pairs(items):
        result = {}
        for key,value in items:
            require(key not in result); result[key] = value
        return result
    try:
        require(type(data) is bytes and len(data) <= MIB)
        return json.loads(data,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(Rejected()))
    except (UnicodeError,TypeError,RecursionError,json.JSONDecodeError): raise Rejected() from None

def exact(value,fields): require(type(value) is dict and set(value) == set(fields))
def validate_sha(sha): require(match(sha,r'[0-9a-f]{40}'))
def validate_hash(value): require(match(value,r'[0-9a-f]{64}'))

def validate_approval(value,sha,kind):
    validate_sha(sha)
    fields = COMMON + (PROVISION if kind == 'provision' else PREPARE + (IMAGES if kind == 'images' else DATABASE))
    exact(value,fields)
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and value['source_sha'] == sha)
    require(value['environment'] == 'staging')
    for key in fields:
        if key.endswith('_sha256'): validate_hash(value[key])
    try:
        identifier = uuid.UUID(value['authorization_id'])
        require(identifier.version == 4 and str(identifier) == value['authorization_id'])
        require(match(value['expires_at'],r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ'))
        delta = (datetime.fromisoformat(value['expires_at'].replace('Z','+00:00'))-datetime.now(timezone.utc)).total_seconds()
        require(0 < delta <= 86400)
    except (ValueError,TypeError,AttributeError): raise Rejected() from None
    expected = {'provision':('prepare-new-empty-staging-host',), 'images':('cache-accepted-staging-images',),
                'database':('initialize-fresh-staging-database','resume-created-staging-database')}[kind]
    require(value['operation'] in expected)
    if kind == 'provision':
        require(match(value['boot_id'],r'[0-9a-f-]{36}') and match(value['data_device_major_minor'],r'[0-9]+:[0-9]+'))
        require(type(value['data_device_serial']) is str and 1 <= len(value['data_device_serial']) <= 256)
        require(type(value['data_device_bytes']) is int and value['data_device_bytes'] > 0)
        require(str(uuid.UUID(value['data_filesystem_uuid'])) == value['data_filesystem_uuid'])
        packages = value['packages']; require(type(packages) is list and 8 <= len(packages) <= 512)
        names = []
        for package in packages:
            exact(package,('name','version','architecture','filename','bytes','sha256'))
            require(match(package['name'],r'[a-z0-9][a-z0-9+.-]+') and match(package['version'],r'[A-Za-z0-9:+.~-]+'))
            require(package['architecture'] in ('amd64','all') and match(package['filename'],r'[A-Za-z0-9_+.:~-]+\.deb'))
            require(type(package['bytes']) is int and 0 < package['bytes'] <= 512*MIB); validate_hash(package['sha256']); names.append(package['name'])
        require(names == sorted(set(names)) and REQUIRED_PACKAGES <= set(names))
        require(len(set(item['filename'] for item in packages)) == len(packages))
    elif kind == 'images':
        require(type(value['images']) is list and len(value['images']) == 7)
        roles = []
        for item in value['images']:
            exact(item,('role','reference','image_id')); roles.append(item['role'])
            require(match(item['reference'],r'[a-z0-9./_-]+@sha256:[0-9a-f]{64}') and match(item['image_id'],r'sha256:[0-9a-f]{64}'))
        require(roles == sorted(set(roles)))
    else:
        fresh = value['operation'] == 'initialize-fresh-staging-database'
        require(type(value['pgdata_initial_empty']) is bool and value['pgdata_initial_empty'] is fresh)
        if fresh: require(value['resume'] is None)
        else:
            exact(value['resume'],('journal_sha256','observed_ledger_prefix')); validate_hash(value['resume']['journal_sha256'])
            prefix = value['resume']['observed_ledger_prefix']
            require(type(prefix) is list and len(prefix) <= 256 and all(match(name,r'[0-9]{3}_[a-z0-9_]+') for name in prefix))
    return value

def command(argv,timeout=120,deadline=None,maximum=MIB,input_data=None, allowed_codes=(0,)):
    end = min(time.monotonic()+timeout,deadline or float('inf'))
    require(time.monotonic() < end and (input_data is None or type(input_data) is bytes and len(input_data) <= maximum))
    process = subprocess.Popen(argv,stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=ENV,cwd='/',start_new_session=True)
    selector = selectors.DefaultSelector(); output = bytearray(); total = 0
    try:
        for pipe in (process.stdout,process.stderr): os.set_blocking(pipe.fileno(),False); selector.register(pipe,selectors.EVENT_READ)
        pending = memoryview(input_data or b'')
        if input_data is not None: os.set_blocking(process.stdin.fileno(),False); selector.register(process.stdin,selectors.EVENT_WRITE)
        while selector.get_map():
            remaining = end-time.monotonic(); require(remaining > 0)
            events = selector.select(remaining); require(events)
            for key,_ in events:
                pipe = key.fileobj
                if pipe is process.stdin:
                    if pending: pending = pending[os.write(pipe.fileno(),pending[:4096]):]
                    if not pending: selector.unregister(pipe); pipe.close()
                else:
                    data = os.read(pipe.fileno(),min(65536,maximum+1-total))
                    if not data: selector.unregister(pipe); continue
                    total += len(data); require(total <= maximum)
                    if pipe is process.stdout: output.extend(data)
        require(process.wait(timeout=max(.001,end-time.monotonic())) in allowed_codes)
        return bytes(output)
    finally:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        selector.close()
        for pipe in (process.stdin,process.stdout,process.stderr):
            if pipe is not None: pipe.close()
        process.wait(timeout=1)

class Pins:
    """Descriptor-relative traversal; retain bytes and metadata until mutation."""
    def __init__(self): self.dirs = {}; self.files = []
    def __enter__(self): return self
    def __exit__(self,*args):
        for fd,_,_,_ in reversed(list(self.dirs.values())): os.close(fd)
    def directory(self,path,mode=None,uid=0,gid=0):
        path = str(path); require(path.startswith('/') and '..' not in path.split('/'))
        if path not in self.dirs:
            parent,name = (None,'/') if path == '/' else (self.directory(path.rsplit('/',1)[0] or '/'),path.rsplit('/',1)[1])
            fd = os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
            self.dirs[path] = (fd,parent,name,os.fstat(fd))
        fd = self.dirs[path][0]; value = os.fstat(fd)
        require(stat.S_ISDIR(value.st_mode) and value.st_uid == uid and value.st_gid == gid and not value.st_mode & 0o022)
        if mode is not None: require(stat.S_IMODE(value.st_mode) == mode)
        return fd
    def read(self,path,mode=0o600,maximum=MIB,uid=0,gid=0,pin=True):
        path = str(path); parent,name = path.rsplit('/',1); directory = self.directory(parent,uid=uid,gid=gid)
        fd = os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=directory)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_uid == uid and before.st_gid == gid and before.st_nlink == 1)
            require(stat.S_IMODE(before.st_mode) == mode and 0 < before.st_size <= maximum)
            data = bytearray()
            while len(data) <= maximum:
                part = os.read(fd,min(65536,maximum+1-len(data)))
                if not part: break
                data.extend(part)
            require(len(data) == before.st_size and metadata(before) == metadata(os.fstat(fd)) == metadata(os.stat(name,dir_fd=directory,follow_symlinks=False)))
            if pin: self.files.append((path,mode,maximum,uid,gid,before,bytes(data)))
            return bytes(data)
        finally: os.close(fd)
    def recheck(self):
        for fd,parent,name,before in self.dirs.values():
            after = os.fstat(fd); named = os.stat(name,dir_fd=parent,follow_symlinks=False)
            identity = lambda value:(value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid)
            require(identity(after) == identity(before) == identity(named))
        for path,mode,maximum,uid,gid,before,data in self.files:
            require(metadata(os.stat(path,follow_symlinks=False)) == metadata(before) and self.read(path,mode,maximum,uid,gid,False) == data)

# Only these installed destinations may be accepted, regardless of self hashes.
def allowed_path(path):
    if match(path,r'opt/autodata/bin/[A-Za-z0-9_.-]+'):
        name = path.rsplit('/',1)[1]
        return (name.endswith('.py') and not name.startswith('test_') and name != 'build_host_bundle.py') or name in {
            'release.schema.json','runtime-entrypoint.sh','deploy.sh','metadata-guard.nft','autodata-metadata-guard.service',
            'docker-autodata.conf','Caddyfile','nats.conf.template','seaweedfs-s3.json.template','runtime-grants.sql','host-bootstrap-roles.sql'}
    return path == 'opt/compose/compose.production.yaml' or path == 'opt/autodata/source/scripts/dev/migrate_sql.sh' or match(path,r'opt/autodata/source/db/migrations/[0-9]{3}_[a-z0-9_]+\.sql')

def validate_inventory(root,value,sha,pins=None):
    exact(value,('schema_version','source_sha','files')); require(type(value['schema_version']) is int and value['schema_version'] == 1 and value['source_sha'] == sha)
    entries = value['files']; require(type(entries) is list and 40 <= len(entries) <= 128)
    paths = []
    for item in entries:
        exact(item,('path','bytes','sha256','mode')); path = item['path']; require(type(path) is str and allowed_path(path))
        require(type(item['bytes']) is int and 0 < item['bytes'] <= MIB); validate_hash(item['sha256'])
        require(type(item['mode']) is int and item['mode'] == (0o555 if path.endswith('.sh') else 0o444))
        target = Path(root)/path
        if pins: data = pins.read(str(target),item['mode'])
        else:
            require(not target.is_symlink()); value_stat = target.stat()
            require(stat.S_ISREG(value_stat.st_mode) and value_stat.st_nlink == 1 and stat.S_IMODE(value_stat.st_mode) == item['mode'])
            data = target.read_bytes()
        require(len(data) == item['bytes'] and digest(data) == item['sha256']); paths.append(path)
    require(paths == sorted(set(paths)))
    actual = []
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in dirs: require(not (Path(base)/name).is_symlink())
        for name in files:
            relative = str((Path(base)/name).relative_to(root))
            if relative != 'inventory.json': actual.append(relative)
    require(sorted(actual) == paths)
    required = {'opt/autodata/bin/'+name for name in ('runtime-check.py','host_activation.py','host_install.py','host_provision.py','host_prepare_release.py','host-bootstrap-roles.sql','release.schema.json')}
    require(required <= set(paths) and len([name for name in paths if '/db/migrations/' in name]) == 40)
    return entries

def load_module(path,name):
    spec = importlib.util.spec_from_file_location(name,path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def make_directory(path,mode=0o700,uid=0,gid=0):
    # No implicit parents: every parent has already been pinned/created.
    try: os.mkdir(path,mode)
    except FileExistsError:
        value = os.lstat(path); require(stat.S_ISDIR(value.st_mode) and value.st_uid == uid and value.st_gid == gid and stat.S_IMODE(value.st_mode) == mode); return
    os.chown(path,uid,gid); os.chmod(path,mode)

def write_new(path,data,mode=0o600):
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,mode)
    try:
        os.fchmod(fd,mode); offset = 0
        while offset < len(data): offset += os.write(fd,data[offset:])
        os.fsync(fd)
    finally: os.close(fd)
    parent = os.open(str(Path(path).parent),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try: os.fsync(parent)
    finally: os.close(parent)

@contextmanager
def locked(path):
    fd = os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,0o600)
    try:
        value = os.fstat(fd); require(stat.S_ISREG(value.st_mode) and value.st_nlink == 1 and value.st_uid == value.st_gid == 0 and stat.S_IMODE(value.st_mode) == 0o600)
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB); yield
        require(os.stat(path,follow_symlinks=False) == value or (os.stat(path,follow_symlinks=False).st_ino,os.stat(path,follow_symlinks=False).st_dev) == (value.st_ino,value.st_dev))
    finally: os.close(fd)

class Journal:
    def __init__(self,approval):
        self.path = RECEIPTS+'/'+approval['authorization_id']+'.json'
        require(not os.path.lexists(self.path))
        self.value = {'schema_version':1,'authorization_id':approval['authorization_id'],'source_sha':approval['source_sha'],
            'operation':approval['operation'],'bundle_inventory_sha256':approval['bundle_inventory_sha256'],
            'service_config_sha256':approval['service_config_sha256'],'approval_sha256':digest(canonical(approval)),'production_ready':False,'status':'incomplete','stages':[]}
        self.save()
    def save(self):
        temporary = self.path+'.new'; write_new(temporary,canonical(self.value)+b'\n'); os.replace(temporary,self.path)
        fd = os.open(RECEIPTS,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)
    def stage(self,name): self.value['stages'].append(name); self.save()
    def success(self): self.value['status']='passed'; self.save()

@contextmanager
def inhibit_starts(pins):
    path = POLICY; prior = None
    if os.path.lexists(path):
        value = os.lstat(path); require(stat.S_ISREG(value.st_mode) and value.st_uid == value.st_gid == 0 and value.st_nlink == 1)
        prior = pins.read(path,stat.S_IMODE(value.st_mode),pin=False); os.rename(path,path+'.autodata-saved')
    try:
        write_new(path,b'#!/bin/sh\nexit 101\n',0o755)
        yield
    finally:
        value = os.lstat(path); require(stat.S_ISREG(value.st_mode) and value.st_uid == 0)
        require(Path(path).read_bytes() == b'#!/bin/sh\nexit 101\n'); os.unlink(path)
        if prior is not None: os.rename(path+'.autodata-saved',path)

class Provision:
    def __init__(self,pins,approval,config,inventory,executor=command):
        self.pins,self.a,self.config,self.inventory,self.execute = pins,approval,config,inventory,executor
        self.deadline = time.monotonic()+900
    def run(self,argv,timeout=120,allowed_codes=(0,)):
        self.pins.recheck(); validate_approval(self.a,self.a['source_sha'],'provision')
        return self.execute(argv,timeout=timeout,deadline=self.deadline,allowed_codes=allowed_codes)
    def observe(self):
        a = self.a
        require(Path('/etc/os-release').read_text().split('VERSION_ID=')[1].splitlines()[0].strip('"') == '12')
        require('ID=debian' in Path('/etc/os-release').read_text().splitlines())
        require(self.run(['/usr/bin/dpkg','--print-architecture']).strip() == b'amd64')
        require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == a['boot_id'])
        require(digest(Path('/etc/machine-id').read_bytes()) == a['machine_id_sha256'])
        self.device()
        require(not os.path.exists('/var/run/docker.sock'))
        require(self.run(['/usr/bin/systemctl','is-active','docker.service'],allowed_codes=(3,4)).strip() in (b'inactive',b'unknown'))
        # A persistent prior journal must be explicitly recovered, never retried.
        require(not any(strict_json(self.pins.read(str(path))).get('operation') == 'prepare-new-empty-staging-host' for path in Path(RECEIPTS).glob('*.json')))
        require(not os.path.lexists('/usr/sbin/policy-rc.d.autodata-saved'))
        require(not os.path.lexists('/etc/systemd/system/var-lib-autodata.mount'))
        require(not os.path.lexists('/etc/systemd/system/run-autodata.mount'))
        require(not os.path.lexists('/etc/systemd/system/autodata-metadata-guard.service'))
        require(not os.path.lexists('/etc/systemd/system/docker.service.d/autodata.conf'))
        require(not os.path.lexists('/etc/autodata/metadata-guard.nft'))
        require(not os.path.lexists('/opt/autodata') and not os.path.lexists('/opt/compose'))
        for path in (DATA,RUN):
            if os.path.lexists(path):
                value = os.lstat(path); require(stat.S_ISDIR(value.st_mode) and value.st_uid == value.st_gid == 0 and stat.S_IMODE(value.st_mode) == 0o700)
                require(not os.listdir(path) and not os.path.ismount(path))
        for item in a['packages']:
            package = PACKAGES+'/'+item['filename']; data = self.pins.read(package,0o444,512*MIB)
            require(len(data) == item['bytes'] and digest(data) == item['sha256'])
            facts = self.run(['/usr/bin/dpkg-deb','--show','--showformat=${Package}\t${Version}\t${Architecture}',package]).decode().split('\t')
            require(facts == [item['name'],item['version'],item['architecture']])
        self.run(['/usr/bin/dpkg','--no-act','--install']+sorted(PACKAGES+'/'+item['filename'] for item in a['packages']))
    def device(self):
        # The fixed GCE udev alias is the only permitted link; target is no-follow.
        require(stat.S_ISLNK(os.lstat(DEVICE).st_mode))
        path = os.path.realpath(DEVICE); require(match(path,r'/dev/[a-zA-Z0-9]+'))
        fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        try:
            value = os.fstat(fd); require(stat.S_ISBLK(value.st_mode))
            major_minor = str(os.major(value.st_rdev))+':'+str(os.minor(value.st_rdev))
            require(major_minor == self.a['data_device_major_minor'])
            sysdev = Path('/sys/dev/block')/major_minor
            require(not (sysdev/'partition').exists() and not list((sysdev/'holders').iterdir()))
            tree = strict_json(self.run(['/usr/bin/lsblk','--json','--bytes','--paths','--output','NAME,MAJ:MIN,SERIAL,SIZE,TYPE,MOUNTPOINTS',path]))
            exact(tree,('blockdevices',)); require(len(tree['blockdevices']) == 1)
            disk = tree['blockdevices'][0]; exact(disk,('name','maj:min','serial','size','type','mountpoints'))
            require(disk == {'name':path,'maj:min':major_minor,'serial':self.a['data_device_serial'],'size':self.a['data_device_bytes'],'type':'disk','mountpoints':[None]})
            root = self.run(['/usr/bin/findmnt','--noheadings','--output','MAJ:MIN','--target','/']).decode().strip()
            require(root != major_minor and root not in {p.name for p in sysdev.iterdir() if (p/'partition').exists()})
            swaps = Path('/proc/swaps').read_text().splitlines()[1:]
            require(all(os.path.realpath(line.split()[0]) != path for line in swaps))
            signatures = strict_json(self.run(['/usr/sbin/wipefs','--json','--no-act',path])); require(signatures == {'signatures':[]})
            require(not self.run(['/usr/sbin/blkid','--probe','--output','export',path],allowed_codes=(2,)).strip())
            # blkid normally returns 2 for blank devices; handled below by caller executor.
            require(os.stat(path,follow_symlinks=False).st_rdev == value.st_rdev)
        finally: os.close(fd)
        return path
    def apply(self):
        self.observe(); journal = Journal(self.a)
        with inhibit_starts(self.pins):
            self.run(['/usr/bin/dpkg','--install']+sorted(PACKAGES+'/'+item['filename'] for item in self.a['packages']))
        journal.stage('packages-installed')
        for item in self.a['packages']:
            facts = self.run(['/usr/bin/dpkg-query','--show','--showformat=${Package}\t${Version}\t${Architecture}\t${db:Status-Status}',item['name']]).decode().split('\t')
            require(facts == [item['name'],item['version'],item['architecture'],'installed'])
        for binary in ('/usr/bin/docker','/usr/sbin/nft','/usr/bin/findmnt','/usr/sbin/mkfs.ext4','/usr/bin/python3'):
            value = os.stat(binary); require(stat.S_ISREG(value.st_mode) and value.st_uid == 0 and not value.st_mode & 0o022)
        plugin = self.run(DOCKER+['compose','version','--short']).decode().strip().removeprefix('v')
        package_version = next(item['version'] for item in self.a['packages'] if item['name'] == 'docker-compose-plugin').split(':')[-1].split('-')[0]
        require(plugin == package_version)
        path = self.device(); self.run(['/usr/sbin/mkfs.ext4','-U',self.a['data_filesystem_uuid'],path]); journal.stage('formatted')
        make_directory('/opt/autodata'); make_directory('/opt/autodata/bin',0o755); make_directory('/opt/autodata/releases'); make_directory('/opt/compose',0o755)
        for item in self.inventory:
            target = '/'+item['path']
            for parent in reversed(Path(target).parents):
                if str(parent) in ('/','/opt','/opt/autodata','/opt/autodata/bin','/opt/autodata/releases','/opt/compose'): continue
                make_directory(str(parent),0o755)
            write_new(target,self.pins.read(BUNDLE+'/'+item['path'],item['mode']),item['mode'])
        journal.stage('helpers-installed')
        make_directory(DATA); make_directory(RUN)
        units = {
            'var-lib-autodata.mount': '[Unit]\nDescription=AutoData accepted data disk\nBefore=docker.service\n[Mount]\nWhat=/dev/disk/by-uuid/'+self.a['data_filesystem_uuid']+'\nWhere='+DATA+'\nType=ext4\nOptions=rw,nodev,nosuid\n[Install]\nWantedBy=local-fs.target\n',
            'run-autodata.mount': '[Unit]\nDescription=AutoData ephemeral private inputs\nBefore=docker.service\n[Mount]\nWhat=tmpfs\nWhere='+RUN+'\nType=tmpfs\nOptions=rw,mode=0700,nodev,nosuid,noexec,size=64M\n[Install]\nWantedBy=local-fs.target\n'}
        for name,data in units.items(): write_new('/etc/systemd/system/'+name,data.encode(),0o644)
        write_new('/etc/autodata/metadata-guard.nft',self.pins.read(BUNDLE+'/opt/autodata/bin/metadata-guard.nft',0o444),0o600)
        write_new('/etc/systemd/system/autodata-metadata-guard.service',self.pins.read(BUNDLE+'/opt/autodata/bin/autodata-metadata-guard.service',0o444),0o644)
        make_directory('/etc/systemd/system/docker.service.d',0o755)
        write_new('/etc/systemd/system/docker.service.d/autodata.conf',self.pins.read(BUNDLE+'/opt/autodata/bin/docker-autodata.conf',0o444),0o644)
        self.run(['/usr/bin/systemctl','daemon-reload'])
        self.run(['/usr/bin/systemctl','enable','var-lib-autodata.mount','run-autodata.mount','autodata-metadata-guard.service'])
        self.run(['/usr/bin/systemctl','start','var-lib-autodata.mount','run-autodata.mount'])
        rt = load_module('/opt/autodata/bin/runtime-check.py','provision_runtime')
        observations = [strict_json(self.run(['/usr/bin/findmnt','--json','--list','--mountpoint',target,'--output','TARGET,UUID,FSTYPE,OPTIONS'])) for target in (DATA,RUN)]
        rt.validate_mount_observations(self.config,*observations)
        require(observations[0]['filesystems'][0]['fstype'] == 'ext4' and {'nodev','nosuid'} <= set(observations[0]['filesystems'][0]['options'].split(',')))
        self.pins.directory(DATA,0o700); self.pins.directory(RUN,0o700)
        for name,uid in (('postgres',999),('caddy',0),('nats',1000),('seaweedfs',1000),('operations',0)): make_directory(DATA+'/'+name,0o700,uid,uid)
        journal.stage('mounted')
        self.run(['/usr/bin/systemctl','start','autodata-metadata-guard.service'])
        tables = {family:strict_json(self.run(['/usr/sbin/nft','--json','--numeric','list','table',family,'autodata_guard'])) for family in ('inet','bridge')}
        rt.validate_guard_tables(tables); journal.stage('guard-verified')
        self.run(['/usr/bin/systemctl','start','docker.service']); journal.stage('docker-started'); journal.success()
        return journal.value

def main(argv):
    require(len(argv) == 2 and argv[0] in ('check','apply')); sha = argv[1]; validate_sha(sha); require(os.getuid() == 0)
    with Pins() as pins:
        config_data = pins.read('/etc/autodata/host.json'); approval_data = pins.read('/etc/autodata/host-provision-approval.json')
        approval = validate_approval(strict_json(approval_data),sha,'provision')
        inventory_data = pins.read(BUNDLE+'/inventory.json',0o444); require(digest(inventory_data) == approval['bundle_inventory_sha256'])
        inventory = validate_inventory(BUNDLE,strict_json(inventory_data),sha,pins)
        runtime = load_module(BUNDLE+'/opt/autodata/bin/runtime-check.py','provision_runtime')
        config = strict_json(config_data); require(config['environment'] == 'staging' and runtime.validate_config(config) == approval['service_config_sha256'])
        require(config['resources']['data_disk_filesystem_uuid'] == approval['data_filesystem_uuid'])
        pins.directory(RECEIPTS,0o700); pins.directory(PACKAGES,0o700)
        operation = Provision(pins,approval,config,inventory)
        if argv[0] == 'check': operation.observe(); return {'status':'checked','source_sha':sha,'production_ready':False}
        with locked('/var/lib/autodata-bootstrap/provision.lock'): return operation.apply()

if __name__ == '__main__':
    try: result = main(sys.argv[1:]); print(json.dumps(result,sort_keys=True))
    except Exception: print('{"status":"failed","production_ready":false}'); raise SystemExit(3)
