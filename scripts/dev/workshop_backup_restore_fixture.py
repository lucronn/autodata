#!/usr/bin/env python3
"""Opt-in disposable local portable restore proof. Never a cloud snapshot proof.

Default invocation is inert. All Docker access uses a private empty CLI config,
fixed local socket, cached immutable image IDs and UUID-labelled resources.
"""
from __future__ import annotations
import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import hmac
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import stat
import subprocess
import sys
import tarfile
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
LABEL = 'autodata.backup-fixture'
IMAGES = {
    'postgres': {'id':'sha256:151aa1c2e849e7828ed8aef2183ae15f692cbe887d2f28921d8b44b26e154d7e'},
    'nats': {'id':'sha256:8b9f712ae2148dcbd9d7f3d16a942d515e290526e5d018500931eab62b18e045'},
    'seaweed': {'id':'sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5',
                'digest':'ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d'},
}
ASSERTIONS = ('cached_image_pins','released_migrations','seed_readback','backup_state_machine',
              'stopped_owned_cold_copy','explicit_resume_export','portable_restore',
              'object_persistence','jetstream_persistence','negative_corrupt_dump',
              'negative_missing_object','negative_altered_owner','negative_missing_message')
TABLES = ('schema_migrations','source_snapshots','extraction_evidence','vehicles',
          'vehicle_identity_bases','vehicle_configurations','dataset_products','dataset_requests',
          'customer_accounts','auth_sessions','workshop_orders','entitlements','canonical_articles',
          'canonical_article_source_revisions','source_fetch_jobs')
PAYLOAD = b'{"fixture":"backup-recovery","body":"Synthetic workshop source article"}'
MESSAGE = b'synthetic persisted workshop backup event'


def require(condition, message='fixture assertion failed'):
    if not condition: raise ValueError(message)


def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(data): return hashlib.sha256(data).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    with path.open('xb') as out: out.write(canonical(value)+b'\n')
    path.chmod(0o600)


def new_evidence(path):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts,'evidence requires a new absolute directory')
    require(not any(path == Path(p) or Path(p) in path.parents for p in ('/run','/etc','/opt','/var/lib','/proc','/sys','/dev')), 'production/system evidence path forbidden')
    require(path.parent.resolve()==path.parent,'evidence parent symlink forbidden')
    path.mkdir(mode=0o700); return path


def success(assertions, cleanup):
    return set(assertions)==set(ASSERTIONS) and all(v is True for v in assertions.values()) and cleanup.get('passed') is True and cleanup.get('leftovers')==[]


def verify_seed_inventory(inventory,run_id):
    """Check known synthetic identities before accepting queried seed evidence."""
    uid=lambda key:str(uuid.uuid5(uuid.UUID(run_id),key))
    rows=inventory['relations']
    for table in ('customer_accounts','auth_sessions','workshop_orders','entitlements','dataset_requests','vehicle_configurations'):
        require(len(rows[table])==2,'two-owner fixture missing '+table)
    for k in ('1','2'):
        find=lambda table,column,key:next(row for row in rows[table] if row[column]==uid(key+k))
        account=find('customer_accounts','customer_account_id','account')
        order=find('workshop_orders','order_id','order');grant=find('entitlements','entitlement_id','grant')
        request=find('dataset_requests','dataset_request_id','request')
        require(account['personal_organization_id']==order['organization_id']==grant['organization_id']==request['organization_id']==uid('org'+k),'fixture owner pair mismatch')
        require(order['customer_account_id']==grant['customer_account_id']==uid('account'+k))
        require(order['configuration_id']==grant['configuration_id']==uid('config'+k))
        require(order['dataset_request_id']==grant['dataset_request_id']==uid('request'+k))
        require(order['entitlement_id']==uid('grant'+k) and grant['commerce_order_id']==uid('order'+k))
        require(any(row['customer_account_id']==uid('account'+k) and row['session_token_hash']=='\\x'+digest(('session'+k).encode()) for row in rows['auth_sessions']))
        require(any(row['vehicle_configuration_id']==uid('config'+k) for row in rows['vehicle_configurations']))
    require(len(rows['canonical_article_source_revisions'])==1 and rows['canonical_article_source_revisions'][0]['source_revision_id']==uid('revision'))
    require(inventory['objects'][0]['sha256']==digest(PAYLOAD) and inventory['objects'][0]['bytes']==len(PAYLOAD))
    js=inventory['jetstream']
    require(js['sequence']==js['messages']==1 and js['delivered_stream_seq']==js['ack_floor_stream_seq']==0)
    require(js['payload_sha256']==digest(canonical({'message':MESSAGE.decode()})),'seed JetStream payload mismatch')


def negative_rejected(case,code,receipt,observation):
    if code==0 or receipt.get('status')!='failed':return False
    stage,error=observation.get('stage'),observation.get('error','')
    if case=='corrupt_dump':return stage=='restore_dump' and receipt.get('failure_code')=='input_or_restore_failed'
    if case=='missing_object':return stage=='inspect_failed' and 'S3 request failed 404' in error
    if case=='missing_message':return stage=='inspect_failed' and 'JetStream request failed $JS.API.STREAM.MSG.GET.BACKUP_FIXTURE' in error
    if case=='altered_owner':return stage=='inspect_completed' and receipt.get('failure_code')=='inventory_mismatch'
    return False


class Commands:
    """Bound stdout/stderr as they arrive; kill the entire process group."""
    def __init__(self,evidence,deadline):
        self.evidence,self.deadline=evidence,deadline
        self.config=evidence/'docker-config'; self.config.mkdir(mode=0o700)
        self.entries=[];self.cleanup_mode=False
    def process(self,argv,*,input_data=b'',timeout=30,maximum=1048576,allowed=(0,),output=None):
        remaining=min(timeout,self.deadline-time.monotonic())
        require(remaining>0,'fixture deadline exhausted')
        start=time.monotonic()
        process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C','HOME':'/nonexistent'},cwd='/',start_new_session=True)
        selector=selectors.DefaultSelector(); result=bytearray(); errors=bytearray(); offset=0; size=0
        try:
            for pipe,event in ((process.stdin,selectors.EVENT_WRITE),(process.stdout,selectors.EVENT_READ),(process.stderr,selectors.EVENT_READ)):
                os.set_blocking(pipe.fileno(),False);selector.register(pipe,event)
            end=start+remaining
            while selector.get_map():
                left=end-time.monotonic()
                if left<=0: raise subprocess.TimeoutExpired('fixture command',remaining)
                for key,_ in selector.select(left):
                    pipe=key.fileobj
                    if pipe is process.stdin:
                        if offset==len(input_data):selector.unregister(pipe);pipe.close()
                        else:offset+=os.write(pipe.fileno(),input_data[offset:offset+65536])
                    else:
                        chunk=os.read(pipe.fileno(),65536)
                        if not chunk:selector.unregister(pipe);continue
                        if pipe is process.stdout:
                            size+=len(chunk);require(size<=maximum,'command output cap exceeded')
                            if output is None:result.extend(chunk)
                            else:output.write(chunk)
                        else:
                            errors.extend(chunk);require(len(errors)<=65536,'stderr cap exceeded')
            code=process.wait(timeout=max(.001,end-time.monotonic()))
            require(code in allowed,'command failed: '+str(code))
            return bytes(result)
        finally:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            selector.close()
            for pipe in (process.stdin,process.stdout,process.stderr):
                if not pipe.closed:pipe.close()
            process.wait(timeout=1)
            # Only synthetic credentials exist, but redact even those in argv.
            redact=lambda arg: '<synthetic-redacted>' if arg in ('fixture-secret','fixture-password','synthetic-fixture-only') else re.sub(r'(POSTGRES_PASSWORD|AWS_SECRET_ACCESS_KEY|AWS_ACCESS_KEY_ID)=.*',r'\1=<synthetic-redacted>',arg)
            self.entries.append({'argv':[redact(a) for a in argv],'stdin_bytes':len(input_data),
                'stdin_sha256':digest(input_data),'stdout_bytes':size,'stderr_sha256':digest(bytes(errors)),
                'stderr_redacted':bytes(errors).decode(errors='replace').replace('fixture-secret','<synthetic-redacted>').replace('fixture-password','<synthetic-redacted>').replace('synthetic-fixture-only','<synthetic-redacted>'),'exit_code':process.returncode,'seconds':round(time.monotonic()-start,6)})
    def __call__(self,args,**kwargs):
        return self.process(['/usr/bin/docker','--config',str(self.config),'--context','default',*args],**kwargs)


class OwnedDocker:
    def __init__(self,run_id,command):
        require(str(uuid.UUID(run_id))==run_id and uuid.UUID(run_id).version==4)
        self.run_id,self.command=run_id,command;self.resources=[];self.total_memory=0;self.states=[]
    def name(self,role):
        require(re.fullmatch('[a-z][a-z0-9-]{0,19}',role) is not None)
        return 'adbr-'+self.run_id.replace('-','')+'-'+role
    def inspect(self,kind,identity):return json.loads(self.command([kind,'inspect',identity]))[0]
    def labels(self,kind,value): return value.get('Config',{}).get('Labels',{}) if kind=='container' else value.get('Labels',{})
    def identity(self,kind,value):
        if kind=='volume':
            result={key:copy.deepcopy(value.get(key)) for key in ('Id','Name','CreatedAt','Mountpoint','Driver','Options','Labels')}
            mountpoint=value.get('Mountpoint')
            result['mountpoint_observation']={'status':'unavailable','reason':'daemon mountpoint not supplied'}
            if mountpoint:
                path=Path(mountpoint)
                require(path.is_absolute() and path.name=='_data' and path.parent.name==value['Name'],'unexpected owned volume mountpoint')
                try:
                    observed=path.stat()
                    result['mountpoint_observation']={'status':'observed','device':observed.st_dev,'inode':observed.st_ino}
                except OSError as error:
                    result['mountpoint_observation']={'status':'unavailable','reason':type(error).__name__}
            return result
        return value['Id']
    def create(self,kind,role,args,memory=0):
        name=self.name(role)
        names=self.command([kind,'ls',*(['--all'] if kind=='container' else []),
            '--format','{{.Names}}' if kind=='container' else '{{.Name}}']).decode().splitlines()
        require(name not in names,'resource name collision')
        item={'kind':kind,'role':role,'name':name,'id':None,'identity':None,'removed':False,'memory':memory}
        self.resources.append(item) # Intent retained even if create output is lost.
        self.command([kind,'create','--label',LABEL+'='+self.run_id,*args])
        value=self.inspect(kind,name)
        require(self.labels(kind,value).get(LABEL)==self.run_id and value['Name'].lstrip('/')==name,'created label/name mismatch')
        item['identity']=self.identity(kind,value);item['id']=name if kind=='volume' else value['Id']
        return item['id']
    def network(self):return self.create('network','net',['--internal',self.name('net')])
    def volume(self,role):return self.create('volume',role,[self.name(role)])
    def container(self,role,image,args,memory,volume=None,destination=None,extra_mounts=(),env=()):
        require(image in {v['id'] for v in IMAGES.values()},'unreviewed image')
        require(sum(r['kind']=='container' and not r['removed'] for r in self.resources)<6,'container cap')
        require(memory in (128,256,512) and self.total_memory+memory<=2048,'memory cap')
        options=['--name',self.name(role),'--pull=never','--network',self.name('net'),
            '--memory',str(memory)+'m','--memory-swap',str(memory)+'m','--cpus=1','--pids-limit=128',
            '--log-driver=json-file','--log-opt','max-size=8m','--log-opt','max-file=2',
            '--security-opt=no-new-privileges','--cap-drop=ALL']
        # PG entrypoint needs only ownership and uid transition on a fresh volume.
        if image==IMAGES['nats']['id']:options+=['--stop-signal=SIGINT']
        if image in (IMAGES['postgres']['id'],IMAGES['seaweed']['id']):options+=['--cap-add=CHOWN','--cap-add=SETUID','--cap-add=SETGID','--cap-add=DAC_OVERRIDE','--cap-add=FOWNER']
        mounts=list(extra_mounts)
        if volume:mounts.append((volume,destination,False))
        for source,target,readonly in mounts:
            require(any(r['kind']=='volume' and r['name']==self.name(source) and not r['removed'] for r in self.resources),'unowned mount')
            require(target.startswith('/') and not target.startswith(('/run','/opt','/etc')))
            options+=['--mount','type=volume,source='+self.name(source)+',target='+target+(',readonly' if readonly else '')]
        for item in env:options+=['--env',item]
        identity=self.create('container',role,[*options,image,*args],memory)
        self.total_memory+=memory
        return identity
    def resource(self,role):return next(r for r in reversed(self.resources) if r['role']==role and not r['removed'])
    def verified(self,item):
        value=self.inspect(item['kind'],item['id'] or item['name'])
        require(self.labels(item['kind'],value).get(LABEL)==self.run_id and value['Name'].lstrip('/')==item['name'],'refuse foreign resource')
        if item['identity'] is None:item['identity']=self.identity(item['kind'],value);item['id']=item['name'] if item['kind']=='volume' else value['Id']
        require(self.identity(item['kind'],value)==item['identity'],'resource identity changed')
        return value
    def stop_grace(self,role):return 45 if role.endswith('-s3') else 15
    def action(self,role,action):
        item=self.resource(role);self.verified(item)
        grace=self.stop_grace(role)
        return self.command(['container',action,*(['--time',str(grace)] if action=='stop' else []),item['id']],timeout=grace+5 if action=='stop' else 25)
    def remove(self,item):
        value=self.verified(item)
        if item['kind']=='container':
            if value['State']['Running']:
                grace=self.stop_grace(item['role'])
                self.command(['container','stop','--time',str(grace),item['id']],timeout=grace+5)
                value=self.verified(item)
            state=dict(value['State']);state['role']=item['role']
            logs=self.command(['container','logs','--tail','100',item['id']],maximum=65536,timeout=5)
            state['logs_redacted']=logs.decode(errors='replace').replace('fixture-secret','<synthetic-redacted>').replace('fixture-password','<synthetic-redacted>').replace('synthetic-fixture-only','<synthetic-redacted>')
            self.states.append(state)
        self.command([item['kind'],'rm',*(['--force'] if item['kind']=='container' else []),item['id']],timeout=20)
        item['removed']=True;self.total_memory-=item['memory']
    def require_stopped(self):
        for item in self.resources:
            if item['kind']=='container' and not item['removed']:
                state=dict(self.verified(item)['State']);state.update(role=item['role'],observation='before-cold-copy')
                self.states.append(state)
                require(state['Running'] is False and state['OOMKilled'] is False and state['ExitCode']==0,'cold copy requires clean stopped owned services')
    def cleanup(self):
        failures=[]
        for kind in ('container','network','volume'):
            for item in reversed(self.resources):
                if item['kind']!=kind or item['removed']:continue
                try:self.remove(item)
                except Exception as error:failures.append(item['name']+': '+type(error).__name__+': '+str(error))
        leftovers=[]
        for kind in ('container','network','volume'):
            try:
                names=self.command([kind,'ls',*(['--all'] if kind=='container' else []),'--quiet','--filter','label='+LABEL+'='+self.run_id],timeout=10).decode().split()
                leftovers.extend(kind+':'+name for name in names)
            except Exception as error:failures.append('leftover inspection: '+type(error).__name__)
        oom=any(s.get('OOMKilled') is True or s.get('ExitCode') != 0 for s in self.states)
        return {'passed':not failures and not leftovers and not oom,'failures':failures,'leftovers':leftovers,'container_states':self.states}


def load_backup():
    spec=importlib.util.spec_from_file_location('fixture_real_backup',ROOT/'infra/deploy/gce/backup_restore.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class Fixture:
    def __init__(self,owned,commands,evidence,run_id,backup):
        self.d,self.c,self.e,self.run,self.b=owned,commands,evidence,run_id,backup
        self.pg='source-pg';self.nats='source-nats';self.s3='source-s3';self.manifest=None
        self.inventory=None;self.archive=None;self.status=None;self.plan=None;self.target_created=False;self.fault=None
        self.checks={'manifest':True,'config':True,'services':True,'no_work':True}
        self.disk=str(uuid.uuid4());self.restore_disk=str(uuid.uuid4())
        self.events=[];self.restore_observation={};self.protocol_events=[]
    def exec(self,role,args,**kwargs):
        item=self.d.resource(role);self.d.verified(item)
        return self.c(['container','exec','-i',item['id'],*args],**kwargs)
    def sql(self,sql):
        return self.exec(self.pg,['psql','-X','--no-password','-qAt','-v','ON_ERROR_STOP=1','-U','fixture','-d','fixture'],input_data=sql.encode(),timeout=60)
    def wait_pg(self):
        end=min(self.c.deadline,time.monotonic()+45)
        while time.monotonic()<end:
            try:
                require(self.sql('SHOW server_version_num;').strip().startswith(b'17'));return
            except ValueError:time.sleep(.2)
        raise ValueError('PG17 readiness failed')
    def services(self,prefix,*,cold=False):
        pg=prefix+'-pg';nats=prefix+'-nats';s3=prefix+'-s3'
        if not cold:
            for role in (pg,nats,s3):self.d.volume(role)
        self.d.container(pg,IMAGES['postgres']['id'],['postgres','-c','max_connections=15','-c','shared_buffers=64MB'],512,pg,'/var/lib/postgresql/data',env=['POSTGRES_USER=fixture','POSTGRES_DB=fixture','POSTGRES_PASSWORD=synthetic-fixture-only'])
        self.d.container(nats,IMAGES['nats']['id'],['nats-server','-js','-sd','/data','--name','backup-fixture','--user','fixture-user','--pass','fixture-password'],256,nats,'/data')
        self.d.container(s3,IMAGES['seaweed']['id'],['mini','-dir=/data','-s3.port=9000'],256,s3,'/data',env=['AWS_ACCESS_KEY_ID=fixture-access','AWS_SECRET_ACCESS_KEY=fixture-secret','S3_BUCKET=fixture'])
        for role in (pg,nats,s3):self.d.action(role,'start')
        self.pg,self.nats,self.s3=pg,nats,s3;self.wait_pg()
    def tcp(self,role,port,data):
        # Bash's fixed TCP primitive runs inside the owned PG container. No host
        # ports or extra tools/containers are needed; destinations are owned names.
        require(role in (self.nats,self.s3))
        destination=self.d.verified(self.d.resource(role))['NetworkSettings']['Networks'][self.d.name('net')]['IPAddress']
        require(re.fullmatch(r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}',destination) is not None,'owned internal address absent')
        script='exec 3<>/dev/tcp/$1/$2; cat >&3; timeout 1 cat <&3; status=$?; test "$status" = 0 -o "$status" = 124'
        return self.exec(self.pg,['/bin/bash','-c',script,'fixture-tcp',destination,str(port)],input_data=data,timeout=5,maximum=1048576)
    def s3_request(self,method,key='',body=b''):
        host=self.d.name(self.s3);path='/fixture'+('/'+key if key else '')
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');day=stamp[:8];payload_hash=digest(body)
        headers={'host':host+':9000','x-amz-content-sha256':payload_hash,'x-amz-date':stamp}
        signed=';'.join(sorted(headers));header_text=''.join(k+':'+headers[k]+'\n' for k in sorted(headers))
        request_hash=digest((method+'\n'+path+'\n\n'+header_text+'\n'+signed+'\n'+payload_hash).encode())
        scope=day+'/us-east-1/s3/aws4_request'
        key_bytes=('AWS4'+'fixture-secret').encode()
        for part in (day,'us-east-1','s3','aws4_request'):key_bytes=hmac.new(key_bytes,part.encode(),hashlib.sha256).digest()
        signature=hmac.new(key_bytes,('AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+request_hash).encode(),hashlib.sha256).hexdigest()
        auth='AWS4-HMAC-SHA256 Credential=fixture-access/'+scope+', SignedHeaders='+signed+', Signature='+signature
        data=(method+' '+path+' HTTP/1.1\r\n'+''.join(k+': '+v+'\r\n' for k,v in headers.items())+'Authorization: '+auth+'\r\nConnection: close\r\nContent-Length: '+str(len(body))+'\r\n\r\n').encode()+body
        raw=self.tcp(self.s3,9000,data)
        head,content=raw.split(b'\r\n\r\n',1);code=int(head.split()[1])
        if b'transfer-encoding: chunked' in head.lower():
            chunks=[]
            while True:
                size_line,content=content.split(b'\r\n',1);size=int(size_line.split(b';')[0],16)
                if size==0:break
                chunks.append(content[:size]);content=content[size+2:]
            content=b''.join(chunks)
        error_code=None
        if code>=400:
            try:error_code=ET.fromstring(content).findtext('Code')
            except ET.ParseError:pass
        self.protocol_events.append({'protocol':'s3','method':method,'key':key,'status':code,
            'response_sha256':digest(raw),'error_code':error_code})
        owned_bucket=(code==409 and method=='PUT' and key=='' and self.s3=='source-s3'
                      and error_code=='BucketAlreadyOwnedByYou')
        require(code in (200,204) or owned_bucket,'S3 request failed '+str(code)+': '+str(error_code))
        return content
    def nats_request(self,subject,payload):
        inbox='_INBOX.fixture';data=canonical(payload)
        connect=canonical({'user':'fixture-user','pass':'fixture-password','verbose':False})
        request=b'CONNECT '+connect+b'\r\nSUB '+inbox.encode()+b' 1\r\nPUB '+subject.encode()+b' '+inbox.encode()+b' '+str(len(data)).encode()+b'\r\n'+data+b'\r\nPING\r\n'
        raw=self.tcp(self.nats,4222,request)
        match=re.search(rb'MSG _INBOX\.fixture 1 (\d+)\r\n',raw)
        require(match is not None,'JetStream response absent')
        result=json.loads(raw[match.end():match.end()+int(match[1])]);require('error' not in result,'JetStream request failed '+subject+': '+str(result.get('error')));return result
    def seed_protocols(self):
        end=min(self.c.deadline,time.monotonic()+45)
        while True:
            try:self.s3_request('PUT');break
            except (ValueError,IndexError) as error:
                require(time.monotonic()<end,'S3 readiness failed: '+str(error));time.sleep(.3)
        self.s3_request('PUT','source/article.json',PAYLOAD)
        self.nats_request('$JS.API.STREAM.CREATE.BACKUP_FIXTURE',{'name':'BACKUP_FIXTURE','subjects':['backup.fixture'],'storage':'file'})
        ack=self.nats_request('backup.fixture',json.loads(MESSAGE.decode()) if MESSAGE.startswith(b'{') else {'message':MESSAGE.decode()})
        require(ack['seq']==1)
        self.nats_request('$JS.API.CONSUMER.DURABLE.CREATE.BACKUP_FIXTURE.fixture-consumer',{'stream_name':'BACKUP_FIXTURE','config':{'durable_name':'fixture-consumer','ack_policy':'explicit','deliver_policy':'all','filter_subject':'backup.fixture'}})
    def rows(self):
        result={}
        for table in TABLES:
            # table is a literal from this module; inventory never supplies SQL.
            rows=json.loads(self.sql("SELECT COALESCE(json_agg(row_to_json(t)), '[]') FROM (SELECT * FROM "+table+") t;"))
            result[table]=sorted(rows,key=canonical)
        return result
    def observe(self):
        rows=self.rows()
        obj=self.s3_request('GET','source/article.json')
        stream=self.nats_request('$JS.API.STREAM.INFO.BACKUP_FIXTURE',{})
        message=self.nats_request('$JS.API.STREAM.MSG.GET.BACKUP_FIXTURE',{'seq':1})
        consumer=self.nats_request('$JS.API.CONSUMER.INFO.BACKUP_FIXTURE.fixture-consumer',{})
        msg=message['message']
        return {'schema_version':1,'relations':rows,
            'objects':[{'bucket':'fixture','key':'source/article.json','sha256':digest(obj),'bytes':len(obj)}],
            'jetstream':{'stream':'BACKUP_FIXTURE','sequence':msg['seq'],'subject':msg['subject'],
                'payload_sha256':digest(base64.b64decode(msg['data'])),'consumer':'fixture-consumer',
                'delivered_stream_seq':consumer['delivered']['stream_seq'],
                'ack_floor_stream_seq':consumer['ack_floor']['stream_seq'],'messages':stream['state']['messages']}}
    def seed_database(self):
        migrations=sorted((ROOT/'db/migrations').glob('*.sql'))
        driver=self.c.process(['/bin/sh',str(ROOT/'scripts/dev/migrate_sql.sh'),'--emit'],timeout=10)
        self.sql(driver.decode())
        ledger=json.loads(self.sql("SELECT json_agg(version ORDER BY version) FROM schema_migrations;"))
        write_json(self.e/'migration-ledger.json',ledger)
        require(ledger==[p.stem for p in migrations],'migration ledger mismatch')
        self.sql(seed_sql(self.run))
        return {p.name:digest(p.read_bytes()) for p in migrations}
    # Injected real backup Host adapter. Writers are the finite seed calls; no
    # configured application, payment worker, or provider client is started.
    def preflight(self,verb,state=None):
        if verb in ('restore','validate'):return self.plan,self.manifest,self.status,self.archive,self.inventory
        for role in (self.pg,self.nats,self.s3):self.d.verified(self.d.resource(role))
        return self.manifest,{'resources':{'data_disk_filesystem_uuid':self.disk}}
    def step(self,phase,store,deadline):
        self.events.append(phase)
        if phase=='dump':
            with store.create_dump() as output:
                self.exec(self.pg,['pg_dump','--no-password','-U','fixture','-d','fixture','--format=custom'],timeout=60,maximum=self.b.MAX_EXPORT-1,output=output)
        elif phase=='stop_stateful':
            for role in (self.pg,self.nats,self.s3):self.d.action(role,'stop')
        elif phase=='sync':self.cold_copy()
        elif phase=='start_stateful':
            for role in (self.pg,self.nats,self.s3):self.d.action(role,'start')
            self.wait_pg()
        elif phase=='ready':self.observe_ready()
        else:require(phase in ('maintenance','stop_writers','start_apps','open_ingress'))
    def verify_dump(self,store,deadline):
        with store.open_file('postgres.dump') as source:
            self.exec(self.pg,['pg_restore','--list'],input_data=source.read(),timeout=30)
    def fail_closed(self,deadline):
        # The isolated fixture has no ingress or lease dependency to change.
        self.events.append('fail-closed-maintenance')
    def check_stopped(self):self.d.require_stopped()
    def observe_ready(self):require(canonical(self.observe())==canonical(self.inventory),'source resume changed evidence')
    def cold_copy(self):
        self.d.require_stopped()
        for suffix in ('pg','nats','s3'):self.d.volume('cold-'+suffix)
        mounts=[]
        for suffix in ('pg','nats','s3'):
            mounts.extend([('source-'+suffix,'/source/'+suffix,True),('cold-'+suffix,'/copy/'+suffix,False)])
        helper=self.d.container('copy',IMAGES['postgres']['id'],['/bin/bash','-ec',
            'for role in pg nats s3; do sync -f /source/$role; cp -a /source/$role/. /copy/$role/; sync -f /copy/$role; done'],128,extra_mounts=mounts)
        self.d.action('copy','start');code=self.c(['container','wait',helper],timeout=90).strip();require(code==b'0','cold copy failed')
        self.d.remove(self.d.resource('copy'));self.events.append('cold-copy-stopped-owned-volumes')
    # Injected restore Target adapter, no command/SQL field consumed from plan.
    def create(self,plan,manifest):
        require(not self.target_created)
        self.restore_observation={'stage':'create'}
        self.d.volume('restore-pg');self.d.container('restore-pg',IMAGES['postgres']['id'],['postgres','-c','shared_buffers=64MB'],512,'restore-pg','/var/lib/postgresql/data',env=['POSTGRES_USER=fixture','POSTGRES_DB=fixture','POSTGRES_PASSWORD=synthetic-fixture-only'])
        self.target_created=True;self.pg='restore-pg';self.d.action(self.pg,'start');self.wait_pg()
    def restore_dump(self,data):
        self.restore_observation={'stage':'restore_dump'}
        self.exec(self.pg,['pg_restore','--exit-on-error','--no-owner','--no-privileges','--no-password','-U','fixture','-d','fixture'],input_data=data,timeout=90)
        if self.fault=='owner':
            # Valid paired owner switch preserves actual FKs while defeating an
            # owner-blind count-only oracle. All SQL and UUIDs are fixed here.
            self.sql("UPDATE dataset_requests SET organization_id=(SELECT personal_organization_id FROM customer_accounts ORDER BY firebase_uid DESC LIMIT 1) WHERE idempotency_key='fixture-request-1';")
    def inspect(self,inventory):
        self.restore_observation={'stage':'inspect'}
        try:observed=self.observe()
        except Exception as error:
            self.restore_observation={'stage':'inspect_failed','error':str(error)}
            raise
        self.restore_observation={'stage':'inspect_completed'}
        return observed
    def cleanup(self):
        for role in ('restore-pg',):
            for item in reversed(self.d.resources):
                if item['role']==role and not item['removed']:self.d.remove(item)
        self.target_created=False


def seed_sql(run_id):
    """Fixed fixture SQL against released relations and their real constraints."""
    # UUID literals derive exclusively from a fresh locally generated UUID.
    uid=lambda key:str(uuid.uuid5(uuid.UUID(run_id),key))
    q=lambda value:"'"+value.replace("'","''")+"'"
    u=lambda key:q(uid(key))
    sha=digest(PAYLOAD)
    lines=["BEGIN;", "INSERT INTO source_snapshots(source_snapshot_id,adapter_name,source_uri,source_version,content_sha256,object_key,license_metadata,retrieved_at) VALUES("+u('snapshot')+",'fixture','fixture://source/article.json','v1','"+sha+"','source/article.json','{}',now());",
        "INSERT INTO extraction_evidence(extraction_evidence_id,source_snapshot_id,locator,artifact_key,extracted_text,confidence,reviewer_state) VALUES("+u('evidence')+","+u('snapshot')+",'fixture','source/article.json','Synthetic workshop source article',1,'approved');"]
    for index in (1,2):
        k=str(index)
        lines.extend([
          "INSERT INTO vehicles(vehicle_id,vehicle_key,make,model,model_year,region,source_snapshot_id,source_watermark) VALUES("+u('vehicle'+k)+",'fixture-vehicle-"+k+"','Synthetic','Workshop',2026,'US',"+u('snapshot')+",'v1');",
          "INSERT INTO vehicle_identity_bases(vehicle_identity_base_id,canonical_base_key,vehicle_id,make,model,model_year,region,source_snapshot_id,extraction_evidence_id,source_locator,evidence_locator,evidence_confidence,reviewer_state) VALUES("+u('base'+k)+",'fixture-base-"+k+"',"+u('vehicle'+k)+",'Synthetic','Workshop',2026,'US',"+u('snapshot')+","+u('evidence')+",'fixture','fixture',1,'approved');",
          "INSERT INTO vehicle_configurations(vehicle_configuration_id,configuration_key,vehicle_identity_base_id,vehicle_id,source_snapshot_id,extraction_evidence_id,source_locator,evidence_locator,evidence_confidence,reviewer_state) VALUES("+u('config'+k)+",'fixture-config-"+k+"',"+u('base'+k)+","+u('vehicle'+k)+","+u('snapshot')+","+u('evidence')+",'fixture','fixture',1,'approved');",
          "INSERT INTO customer_accounts(customer_account_id,firebase_project_id,firebase_uid,personal_organization_id) VALUES("+u('account'+k)+",'synthetic-fixture','fixture-user-"+k+"',"+u('org'+k)+");",
          "INSERT INTO auth_sessions(session_token_hash,customer_account_id,firebase_auth_time,created_at,expires_at) VALUES(decode('"+digest(('session'+k).encode())+"','hex'),"+u('account'+k)+",1,now(),now()+interval '1 hour');",
          "INSERT INTO dataset_requests(dataset_request_id,dataset_product_id,vehicle_key,region,status,lane,correlation_id,idempotency_key,processing_version,organization_id,vehicle_id) SELECT "+u('request'+k)+",dataset_product_id,'fixture-vehicle-"+k+"','US','viewable','fast',"+u('correlation'+k)+",'fixture-request-"+k+"','v1',"+u('org'+k)+","+u('vehicle'+k)+" FROM dataset_products WHERE product_key='workshop-configuration-v1';",
          "INSERT INTO workshop_orders(order_id,customer_account_id,organization_id,configuration_id,region,dataset_product_id,terms_version,amount_minor,currency,stripe_account_id,livemode,expected_price_id,provider_idempotency_key,status,first_create_attempt_at,dataset_request_id) SELECT "+u('order'+k)+","+u('account'+k)+","+u('org'+k)+","+u('config'+k)+",'US',dataset_product_id,'workshop-v1',2000,'USD','acct_synthetic',false,'price_synthetic','fixture-order-"+k+"','paid',now(),"+u('request'+k)+" FROM dataset_products WHERE product_key='workshop-configuration-v1';",
          "INSERT INTO entitlements(entitlement_id,organization_id,dataset_request_id,provider_event_id,status,granted_at,customer_account_id,configuration_id,region,commerce_order_id) VALUES("+u('grant'+k)+","+u('org'+k)+","+u('request'+k)+",'fixture-event-"+k+"','active',now(),"+u('account'+k)+","+u('config'+k)+",'US',"+u('order'+k)+");",
          "UPDATE workshop_orders SET entitlement_id="+u('grant'+k)+" WHERE order_id="+u('order'+k)+";"])
    lines.extend([
       "INSERT INTO canonical_articles(canonical_article_id,provider_slug,vehicle_id,vehicle_configuration_id,scope_key,source_vehicle_ref,source_article_ref,identity_key,descriptor,descriptor_source_snapshot_id,title) VALUES("+u('article')+",'bankone',"+u('vehicle1')+","+u('config1')+",'configuration:"+uid('config1')+"','fixture-vehicle-1','fixture-article','"+digest(b'article')+"','{}',"+u('snapshot')+",'Synthetic source article');",
       "INSERT INTO source_fetch_jobs(source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_article_ref,source_version,connector_name,idempotency_key,status,job_kind,canonical_article_id,normalization_version,rewrite_profile_version) VALUES("+u('job')+",'bankone',"+u('vehicle1')+",'fixture-vehicle-1','fixture-article','v1','fixture','fixture-source-job','completed','article',"+u('article')+",'ordered-article-v1','technical-prose-v1');",
       "INSERT INTO canonical_article_source_revisions(source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,resource_manifest,source_document,source_images,source_body,source_steps,projection_status,evidence_manifest,captured_at) VALUES("+u('revision')+","+u('article')+",'"+sha+"',"+u('snapshot')+",'[{\"role\":\"body\",\"bucket\":\"fixture\",\"key\":\"source/article.json\",\"sha256\":\""+sha+"\"}]','{\"blocks\":[{\"type\":\"paragraph\",\"text\":\"Synthetic workshop source article\"}]}','[]','Synthetic workshop source article','[]','readable','[\"fixture-evidence\"]',now());",
       "UPDATE canonical_articles SET current_job_id="+u('job')+",current_source_revision_id="+u('revision')+" WHERE canonical_article_id="+u('article')+";",'COMMIT;'])
    return '\n'.join(lines)


def prerequisites(commands):
    context=json.loads(commands(['context','inspect','default']))[0]
    require(context['Endpoints']['docker']['Host']=='unix:///var/run/docker.sock','daemon context mismatch')
    require(platform.system()=='Linux' and platform.machine() in ('x86_64','amd64'),'fixture platform mismatch')
    info=json.loads(commands(['info','--format','{{json .}}']))
    require(info['OSType']=='linux' and info['Architecture'] in ('x86_64','amd64'),'daemon platform mismatch')
    result={}
    for role,pin in IMAGES.items():
        image=json.loads(commands(['image','inspect',pin['id']]))[0]
        require(image['Id']==pin['id'] and image['Os']=='linux' and image['Architecture']=='amd64','cached image/platform mismatch')
        if role=='seaweed':require(pin['digest'] in image['RepoDigests'],'hosting SeaweedFS digest mismatch')
        if role=='postgres':require('PG_MAJOR=17' in image['Config']['Env'],'PG major17 required')
        result[role]={'id':image['Id'],'digests':image['RepoDigests'],'os':image['Os'],'architecture':image['Architecture']}
    return result


def execute_fixture(evidence):
    started=now();start=time.monotonic();run_id=str(uuid.uuid4())
    commands=Commands(evidence,start+780);owned=OwnedDocker(run_id,commands);flags={name:False for name in ASSERTIONS}
    failures=[];cleanup={'passed':False,'leftovers':['unverified']};receipts={};backup=load_backup()
    fixture=Fixture(owned,commands,evidence,run_id,backup)
    hashes={};source_sha='';image_pins={}
    try:
        source_sha=commands.process(['/usr/bin/git','-C',str(ROOT),'rev-parse','HEAD']).decode().strip()
        for path in [Path(__file__),Path(__file__).with_name('test_workshop_backup_restore_fixture.py'),ROOT/'infra/deploy/gce/backup_restore.py',ROOT/'scripts/dev/migrate_sql.sh']:
            hashes[str(path.relative_to(ROOT))]=digest(path.read_bytes())
        image_pins=prerequisites(commands);flags['cached_image_pins']=True
        write_json(evidence/'images.json',image_pins)
        owned.network();fixture.services('source')
        fixture.manifest={'source_sha':source_sha,'images':{'postgres':{'image_id':IMAGES['postgres']['id']}},'migrations':{'files':[{'name':p.name,'sha256':digest(p.read_bytes())} for p in sorted((ROOT/'db/migrations').glob('*.sql'))]}}
        migrations=fixture.seed_database();write_json(evidence/'migrations.json',migrations);flags['released_migrations']=True
        fixture.seed_protocols();fixture.inventory=fixture.observe()
        verify_seed_inventory(fixture.inventory,run_id)
        write_json(evidence/'inventory.json',fixture.inventory);flags['seed_readback']=True
        leases=evidence/'leases';leases.mkdir(mode=0o700)
        store=backup.LeaseStore(leases,run_id,owner=os.getuid());clock=backup.Clock()
        code,receipts['begin']=backup.run_backup('begin',run_id,fixture,store,clock)
        require(code==0,'real backup begin rejected');flags['backup_state_machine']=True
        flags['stopped_owned_cold_copy']='cold-copy-stopped-owned-volumes' in fixture.events
        code,receipts['resume']=backup.run_backup('resume',run_id,fixture,store,clock);require(code==0,'real backup resume rejected')
        code,fixture.status=backup.run_backup('status',run_id,fixture,store,clock);require(code==0)
        output=io.BytesIO();backup.export_archive(store,fixture.manifest,fixture.status,output);fixture.archive=output.getvalue()
        with (evidence/'export.tar').open('xb') as out:out.write(fixture.archive)
        (evidence/'export.tar').chmod(0o600);flags['explicit_resume_export']=True
        for role in ('source-pg','source-nats','source-s3'):owned.remove(owned.resource(role))
        # Use only copied cold NATS/SeaweedFS. The copied PG volume is retained
        # for cold-copy evidence; the target PG always gets the portable dump.
        fixture.nats,fixture.s3='cold-nats','cold-s3'
        owned.container('cold-nats',IMAGES['nats']['id'],['nats-server','-js','-sd','/data','--name','backup-fixture','--user','fixture-user','--pass','fixture-password'],256,'cold-nats','/data')
        owned.container('cold-s3',IMAGES['seaweed']['id'],['mini','-dir=/data','-s3.port=9000'],256,'cold-s3','/data',env=['AWS_ACCESS_KEY_ID=fixture-access','AWS_SECRET_ACCESS_KEY=fixture-secret','S3_BUCKET=fixture'])
        for role in ('cold-nats','cold-s3'):owned.action(role,'start')
        fixture.plan={'schema_version':1,'run_id':run_id,'source_sha':source_sha,'manifest_sha256':digest(canonical(fixture.manifest)),
            'archive_sha256':digest(fixture.archive),'expected_disk_uuid':fixture.disk,'restore_disk_uuid':fixture.restore_disk,
            'postgres_image_id':IMAGES['postgres']['id'],'fixture_inventory_sha256':digest(canonical(fixture.inventory))}
        write_json(evidence/'restore-plan.json',fixture.plan)
        code,result=backup.run_restore('restore',run_id,fixture,store,clock);receipts['restore']=result
        require(code==0,'portable restore rejected');flags['portable_restore']=True
        flags['object_persistence']=flags['jetstream_persistence']=True
        code,result=backup.run_restore('validate',run_id,fixture,store,clock);receipts['validate']=result;require(code==0)
        fixture.cleanup()
        # Every failure receipt gets a distinct file and must actually reject.
        original_archive,original_plan=fixture.archive,dict(fixture.plan)
        for case in ('corrupt_dump','missing_object','altered_owner','missing_message'):
            fixture.fault=None
            if case=='corrupt_dump':
                entries={}
                with tarfile.open(fileobj=io.BytesIO(original_archive),mode='r:') as archive:
                    for member in archive:entries[member.name]=archive.extractfile(member).read()
                entries['postgres.dump']=b'PGDMP deliberately corrupt portable dump'
                corrupt_status=json.loads(entries['backup.json']);corrupt_status.update(dump_bytes=len(entries['postgres.dump']),dump_sha256=digest(entries['postgres.dump']))
                entries['backup.json']=canonical(corrupt_status);output=io.BytesIO()
                with tarfile.open(fileobj=output,mode='w',format=tarfile.USTAR_FORMAT) as archive:
                    for name,data in entries.items():
                        member=tarfile.TarInfo(name);member.size=len(data);archive.addfile(member,io.BytesIO(data))
                fixture.archive=output.getvalue();fixture.status=corrupt_status;fixture.plan['archive_sha256']=digest(fixture.archive)
            elif case=='missing_object':
                # Start target PG only for its internal TCP primitive, then the
                # restore adapter reuses this freshly created empty target.
                fixture.create(fixture.plan,fixture.manifest);fixture.s3_request('DELETE','source/article.json');fixture.cleanup()
            elif case=='altered_owner':fixture.fault='owner'
            elif case=='missing_message':
                fixture.create(fixture.plan,fixture.manifest);fixture.nats_request('$JS.API.STREAM.PURGE.BACKUP_FIXTURE',{});fixture.cleanup()
            code,result=backup.run_restore('restore',run_id,fixture,store,clock)
            write_json(evidence/('negative-'+case+'.json'),{'code':code,'receipt':result,'rejected':negative_rejected(case,code,result,fixture.restore_observation),'fault_observation':fixture.restore_observation,'archive_sha256':digest(fixture.archive)})
            require(negative_rejected(case,code,result,fixture.restore_observation),'negative case did not reject the intended fault '+case)
            flags['negative_'+case]=True;fixture.cleanup()
            fixture.archive=original_archive;fixture.plan=dict(original_plan)
            # Manifest/backup contract uses an explicit fresh status receipt.
            with tarfile.open(fileobj=io.BytesIO(original_archive),mode='r:') as archive:fixture.status=json.loads(archive.extractfile('backup.json').read())
            if case=='missing_object':
                fixture.create(fixture.plan,fixture.manifest);fixture.s3_request('PUT','source/article.json',PAYLOAD);fixture.cleanup()
    except BaseException as error:
        failures.append(type(error).__name__+': '+str(error))
    finally:
        commands.deadline=min(start+900,time.monotonic()+120)
        cleanup=owned.cleanup()
        write_json(evidence/'commands.json',commands.entries)
        write_json(evidence/'receipts.json',receipts)
        write_json(evidence/'protocol-observations.json',fixture.protocol_events)
        write_json(evidence/'resources.json',owned.resources)
        write_json(evidence/'cleanup.json',cleanup)
        for path in sorted(evidence.iterdir()):
            if path.is_file():hashes[path.name]=digest(path.read_bytes())
        result={'schema_version':1,'run_id':run_id,'started_at':started,'finished_at':now(),'seconds':round(time.monotonic()-start,3),
            'source_sha':source_sha,'source_file_sha256':hashes,'image_pins':image_pins,
            'assertions':flags,'failures':failures,'cleanup':cleanup,'passed':not failures and success(flags,cleanup),
            'scope':'portable PG17 + synthetic local stopped-volume cold-copy proof; no cloud snapshot, RPO/RTO, production completeness or owner/privilege recovery claim'}
        write_json(evidence/'result.json',result)
    print(canonical({'passed':result['passed'],'evidence_dir':str(evidence),'result_sha256':digest((evidence/'result.json').read_bytes()),'failures':failures}).decode())
    return 0 if result['passed'] else 1


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-local-fixture',action='store_true')
    parser.add_argument('--evidence-dir',type=Path)
    args=parser.parse_args(argv)
    if not args.execute_local_fixture:
        if args.evidence_dir:parser.error('--evidence-dir requires --execute-local-fixture')
        print('Inert. Use --execute-local-fixture --evidence-dir <new-absolute-directory> for the disposable local proof.')
        return 0
    if args.evidence_dir is None:parser.error('explicit new absolute --evidence-dir required')
    try:evidence=new_evidence(args.evidence_dir)
    except (OSError,ValueError) as error:parser.error(str(error))
    previous=signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(InterruptedError('fixture terminated')))
    try:return execute_fixture(evidence)
    finally:signal.signal(signal.SIGTERM,previous)


if __name__=='__main__':raise SystemExit(main())
