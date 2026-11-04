"""Pure, synthetic-only R3 preparation policy. No observation adapters."""
from dataclasses import dataclass

IMAGES = (
 'sha256:b43f27cfb2dc268b00baf0458bd50f411caccb8d23f037c2819d1d304463fc8c',
 'sha256:151aa1c2e849e7828ed8aef2183ae15f692cbe887d2f28921d8b44b26e154d7e',
 'sha256:8b9f712ae2148dcbd9d7f3d16a942d515e290526e5d018500931eab62b18e045',
 'sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5')
OUTPUT_NAMES = ('owner-contract.json','dispatch.json','command-manifest.json','source-pins.json',
 'file-observations.json','tool-observations.json','daemon-observations.json','image-observations.json',
 'inventory-observations.json','compose-baseline.json','effective.json','compose-effective.json',
 'command-receipts.json','classification.json','REPORT.md','SHA256SUMS','independent-review.md')
COMMAND_IDS = ('python_version','git_version','docker_version','compose_version','context_show',
 'context_inspect','daemon_version','daemon_info','create_help','compose_up_help','compose_run_help',
 'image_runner','image_postgres','image_nats','image_minio','inventory_names','inventory_owner',
 'inventory_project','git_files','git_head','git_tree','git_status','git_remote','git_symbolic',
 'compose_baseline','compose_effective')

@dataclass(frozen=True)
class Limits:
    input_files:int=20000
    metadata_entries:int=40000
    file_bytes:int=64*1024**2
    input_bytes:int=1024**3
    chunk_bytes:int=65536
    file_ms:int=5000
    files_ms:int=300000
    document_bytes:int=16*1024**2
    json_nodes:int=1000000
    json_depth:int=64
    json_string:int=1024**2
    json_members:int=20000
    operation_ms:int=5000
    json_ms:int=60000
    write_ms:int=5000
    writes_ms:int=60000
    command_bytes:int=16*1024**2
    capture_bytes:int=128*1024**2
    output_bytes:int=128*1024**2
    command_ms:int=10000
    source_command_ms:int=30000
    outer_ms:int=1800000
    free_bytes:int=1024**3
    term_ms:int=2000
    kill_ms:int=2000

@dataclass(frozen=True)
class Problem:
    code:str
    count:int=1

@dataclass(frozen=True)
class SafeObservation:
    kind:str
    data:tuple
    trusted:bool=False
    runtime_accepted:bool=False
    host_observed:bool=False
    evidence_kind:str='synthetic'

@dataclass(frozen=True)
class Identity:
    dev:int
    inode:int
    type:str
    uid:int
    gid:int
    mode:int
    size:int
    mtime_ns:int
    ctime_ns:int
    parent:str
    nlink:int=1

@dataclass(frozen=True)
class FileSpec:
    id:str
    path:str
    purpose:str
    identity:Identity
    sha256:str
    parents:tuple

@dataclass(frozen=True)
class CommandSpec:
    id:str
    argv:tuple
    cwd:object
    env:tuple
    stdin:str='DEVNULL'
    close_fds:bool=True
    deadline_ms:int=10000

@dataclass(frozen=True)
class Contract:
    data:tuple
    commands:tuple
    files:tuple
    limits:Limits=Limits()
    trusted:bool=False
    runtime_accepted:bool=False
    host_observed:bool=False
    evidence_kind:str='synthetic'

@dataclass(frozen=True)
class Receipt:
    checksum_digest:str
    covered_names:tuple
    attempt:str
    checkpoint:str
    collection_status:str='complete'
    trusted:bool=False
    runtime_accepted:bool=False
    host_observed:bool=False
    evidence_kind:str='synthetic'
    release_state:str='unverified'
    accepted_case_credit:int=0

import codecs
import hashlib
import json
import math
import re

CANDIDATE='4d82e413e04fb2401ac7bc28dc828375ac662180'
TREE='d9fb2a8f49beacd009374a76327d0736c1fc9b0a'
CHECKPOINT='e414e8537c8a6f0bc99747f6db09782b7743a949'
CONFIG='[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n\tlogallrefupdates = true\n'
ENV_KEYS=frozenset(('PATH','HOME','USER','LOGNAME','LANG','LC_ALL','TZ','AUTODATA_R3_TEST_IMAGE',
                    'AUTODATA_R3_CANDIDATE_SHA','AUTODATA_LIFECYCLE_ARTIFACT_DIR'))
ENV_IMAGE_KEYS=frozenset(('PATH','HOME','LANG','LC_ALL','TZ','SSL_CERT_FILE','SSL_CERT_DIR'))
CONTRACT_KEYS=frozenset(('schema_version','evidence_kind','trusted','runtime_accepted','host_observed',
 'operator_identity','operator_session','reviewer_identity','reviewer_session','cancellation_owner',
 'host_identity','daemon_owner','local_socket','python_abs','git_abs','docker_abs','compose_plugin_abs',
 'prep_root','token','checkout','checkpoint','review_pin','manifest_pin','candidate','tree','issued_tick',
 'expires_tick','acceptances','git_provenance','approved_files','planned_names','env','image_configs',
 'baseline','required_flags','commands','output_owners'))
ACCEPTANCES=frozenset(('freshness','storage','capture','immutability','interruption','preflight','review','owner','runtime','parents'))

class FrozenMap(tuple):
    """Tagged immutable object pairs; unlike arrays, empty objects stay objects."""

def freeze(value):
    if isinstance(value,dict): return FrozenMap((k,freeze(v)) for k,v in sorted(value.items()))
    if isinstance(value,list): return tuple(freeze(v) for v in value)
    return value

def thaw(value):
    if isinstance(value,FrozenMap): return {k:thaw(v) for k,v in value}
    if isinstance(value,tuple): return [thaw(v) for v in value]
    return value

def values(contract): return thaw(contract.data)
def digest(data): return hashlib.sha256(data).hexdigest()
def encode(value): return json.dumps(thaw(value),sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()

class _Reject(Exception):
    def __init__(self,code): self.code=code

def _need(condition,code='invalid_contract'):
    if not condition: raise _Reject(code)

class _Parser:
    """Single-lookahead recursive descent over incremental UTF-8 characters.

    Byte/chunk caps are charged before decoding. Strings/nodes/members/depth
    are charged before their next allocation. No unrestricted JSON parser is used.
    """
    def __init__(self,chunks,budget):
        self.limits=budget if isinstance(budget,Limits) else budget.limits
        self.budget=budget
        self.nodes=0
        self.chars=self.stream(chunks)
        self.char=next(self.chars,'')
    def tick(self):
        if not isinstance(self.budget,Limits): self.budget.check_json()
    def stream(self,chunks):
        decoder=codecs.getincrementaldecoder('utf-8')('strict'); total=0
        for chunk in chunks:
            self.tick(); _need(type(chunk) is bytes,'invalid_json')
            total+=len(chunk)
            _need(len(chunk)<=self.limits.chunk_bytes and total<=self.limits.document_bytes,'cap')
            for char in decoder.decode(chunk):
                self.tick(); yield char
        for char in decoder.decode(b'',final=True): yield char
    def take(self):
        c=self.char;self.char=next(self.chars,'');self.tick();return c
    def space(self):
        while self.char and self.char in ' \r\n\t': self.take()
    def literal(self,text,value):
        for c in text: _need(self.take()==c,'invalid_json')
        return value
    def string(self):
        _need(self.take()=='"','invalid_json'); pieces=[]; size=0
        while self.char!='"':
            c=self.take(); _need(c!='' and ord(c)>=32,'invalid_json')
            if c=='\\':
                c=self.take()
                if c=='u':
                    def codepoint():
                        h=''.join(self.take() for _ in range(4))
                        _need(len(h)==4 and re.fullmatch('[0-9a-fA-F]{4}',h),'invalid_json')
                        return int(h,16)
                    n=codepoint()
                    if 0xD800<=n<=0xDBFF:
                        _need(self.take()=='\\' and self.take()=='u','invalid_json')
                        low=codepoint();_need(0xDC00<=low<=0xDFFF,'invalid_json')
                        n=0x10000+(n-0xD800)*1024+low-0xDC00
                    _need(not 0xD800<=n<=0xDFFF,'invalid_json');c=chr(n)
                else:
                    escapes={'"':'"','\\':'\\','/':'/','b':'\b','f':'\f','n':'\n','r':'\r','t':'\t'}
                    _need(c in escapes,'invalid_json');c=escapes[c]
            _need(not 0xD800<=ord(c)<=0xDFFF,'invalid_json')
            size+=len(c.encode('utf-8'));_need(size<=self.limits.json_string,'cap');pieces.append(c)
        self.take();return ''.join(pieces)
    def value(self,depth=0):
        self.space(); self.nodes+=1;_need(self.nodes<=self.limits.json_nodes,'cap')
        c=self.char
        if c in ('{','['):
            _need(depth<self.limits.json_depth,'cap');self.take();self.space()
            obj={} if c=='{' else [];end='}' if c=='{' else ']'
            if self.char==end:self.take();return obj
            count=0
            while True:
                count+=1;_need(count<=self.limits.json_members,'cap');self.space()
                if c=='{':
                    key=self.string();_need(key not in obj,'duplicate_key');self.space()
                    _need(self.take()==':','invalid_json');obj[key]=self.value(depth+1)
                else: obj.append(self.value(depth+1))
                self.space();sep=self.take()
                if sep==end:return obj
                _need(sep==',','invalid_json')
        if c=='"': return self.string()
        if c=='t':return self.literal('true',True)
        if c=='f':return self.literal('false',False)
        if c=='n':return self.literal('null',None)
        token=[]
        while self.char and self.char in '-+0123456789.eE':
            _need(len(token)<128,'cap');token.append(self.take())
        text=''.join(token)
        _need(re.fullmatch(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?',text) is not None,'invalid_json')
        val=float(text) if any(c in text for c in '.eE') else int(text)
        _need(not isinstance(val,float) or math.isfinite(val),'invalid_json');return val

def parse_bounded_json(chunks,budget):
    try:
        parser=_Parser(chunks,budget);result=parser.value();parser.space()
        _need(parser.char=='','invalid_json');parser.tick();return result
    except _Reject as e:return Problem(e.code)
    except (UnicodeError,ValueError,TypeError,RecursionError):return Problem('invalid_json')

def _path(v):
    return isinstance(v,str) and v.startswith('/') and not any(s in ('','.','..') for s in v.split('/')[1:]) and not any(x in v for x in ('\x00','\n','\r','$','<','>','UNRESOLVED','TODO'))
def _identifier(v):return isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',v) is not None and not any(x in v.upper() for x in ('UNRESOLVED','TODO','PLACEHOLDER'))
def _hash(v,n=64):return isinstance(v,str) and re.fullmatch('[0-9a-f]{'+str(n)+'}',v) is not None

def _templates(d):
    P,G,D=d['python_abs'],d['git_abs'],d['docker_abs']; C,R,T=d['checkout'],d['prep_root'],d['token']
    g=(G,'--no-optional-locks','-C',C)
    comp=(D,'compose','--env-file','/dev/null','-p','autodata-r3-'+T,'-f',C+'/infra/compose/compose.article-lifecycle-test.yaml')
    args={
      'python_version':(P,'-I','-B','--version'),'git_version':(G,'--version'),'docker_version':(D,'--version'),
      'compose_version':(D,'compose','version','--format','json'),'context_show':(D,'context','show'),
      'context_inspect':(D,'context','inspect','default','--format','{{json .}}'),
      'daemon_version':(D,'version','--format','{{json .}}'),'daemon_info':(D,'info','--format','{{json .}}'),
      'create_help':(D,'create','--help'),'compose_up_help':(D,'compose','up','--help'),'compose_run_help':(D,'compose','run','--help'),
      'inventory_names':(D,'ps','-a','--no-trunc','--format','{{.Names}}'),
      'inventory_owner':(D,'ps','-aq','--no-trunc','--filter','label=autodata.owner='+T),
      'inventory_project':(D,'ps','-aq','--no-trunc','--filter','label=com.docker.compose.project=autodata-r3-'+T),
      'git_files':g+('ls-files','--stage','-z'),'git_head':g+('rev-parse','--verify','HEAD'),
      'git_tree':g+('rev-parse','HEAD^{tree}'),'git_status':g+('status','--porcelain=v1','--untracked-files=all'),
      'git_remote':g+('remote',),'git_symbolic':g+('symbolic-ref','-q','HEAD'),
      'compose_baseline':comp+('config','--format','json'),
      'compose_effective':comp+('-f',R+'/effective.json','config','--format','json')}
    for name,image in zip(('runner','postgres','nats','minio'),IMAGES): args['image_'+name]=(D,'image','inspect',image)
    return tuple(CommandSpec(k,args[k],C if k.startswith('compose_') and k in ('compose_baseline','compose_effective') else None,
               tuple(sorted(d['env'].items())),deadline_ms=30000 if k in ('compose_baseline','compose_effective') or k.startswith('git_') and k!='git_version' else 10000) for k in d['commands'])

def admit_contract(document):
    d=parse_bounded_json((document[i:i+65536] for i in range(0,len(document),65536)),Limits()) if type(document) is bytes else Problem('invalid_contract')
    if isinstance(d,Problem):return d
    try:
        _need(type(d) is dict and set(d)==CONTRACT_KEYS)
        _need(type(d['schema_version']) is int and d['schema_version']==1)
        _need(d['evidence_kind']=='synthetic' and all(d[k] is False for k in ('trusted','runtime_accepted','host_observed')))
        for key in ('operator_identity','operator_session','reviewer_identity','reviewer_session','cancellation_owner','host_identity','daemon_owner'):_need(_identifier(d[key]))
        _need(d['operator_session']!=d['reviewer_session'] and d['operator_identity']!=d['reviewer_identity'])
        _need(d['checkpoint']==CHECKPOINT and d['candidate']==CANDIDATE and d['tree']==TREE)
        _need(_hash(d['review_pin']) and _hash(d['manifest_pin']))
        _need(all(_path(d[k]) for k in ('python_abs','git_abs','docker_abs','compose_plugin_abs','prep_root','checkout')))
        _need(re.fullmatch('[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}',d['token']) is not None)
        _need(d['prep_root'].endswith('/run-'+d['token']))
        _need(d['local_socket'].startswith('unix://') and _path(d['local_socket'][7:]))
        _need(type(d['issued_tick']) is int and type(d['expires_tick']) is int and 0<=d['issued_tick']<d['expires_tick']<=d['issued_tick']+1800000)
        _need(set(d['acceptances'])==ACCEPTANCES and all(v=='synthetic-approved' for v in d['acceptances'].values()))
        env=d['env'];R=d['prep_root'];_need(set(env)==ENV_KEYS)
        _need(all(isinstance(v,str) and v and '\x00' not in v for v in env.values()))
        _need(env['HOME']==R+'/home' and env['AUTODATA_LIFECYCLE_ARTIFACT_DIR']==R+'/artifacts' and env['LANG']=='C.UTF-8' and env['LC_ALL']=='C.UTF-8' and env['TZ']=='UTC' and env['AUTODATA_R3_TEST_IMAGE']==IMAGES[0] and env['AUTODATA_R3_CANDIDATE_SHA']==CANDIDATE)
        _need(all(_path(v) for v in env['PATH'].split(':')) and _identifier(env['USER']) and _identifier(env['LOGNAME']))
        _need(type(d['commands']) is list and len(d['commands'])==len(set(d['commands'])) and set(d['commands'])<=set(COMMAND_IDS))
        _need(set(d['output_owners'])==set(OUTPUT_NAMES) and all(v in ('collector','operator','reviewer') for v in d['output_owners'].values()) and d['output_owners']['independent-review.md']=='reviewer' and all(d['output_owners'][n]=='collector' for n in ('REPORT.md','SHA256SUMS')))
        _need(type(d['planned_names']) is list and all(_identifier(v) for v in d['planned_names']))
        _need(set(d['image_configs'])==set(IMAGES) and type(d['baseline']) is dict)
        _need(set(d['required_flags'])=={'create_help','compose_up_help','compose_run_help'} and all(type(v) is list and v and all(re.fullmatch('--[a-z-]+',s) for s in v) for v in d['required_flags'].values()))
        gp=d['git_provenance'];_need(set(gp)=={'owner','complete','categories','immutable','plain_clone','config_literal','absent_paths'})
        _need(_identifier(gp['owner']) and type(gp['absent_paths']) is list and len(set(gp['absent_paths']))==len(gp['absent_paths']) and all(_path(x) for x in gp['absent_paths']))
        files=[];_need(type(d['approved_files']) is list and len(d['approved_files'])<=20000)
        for i,f in enumerate(d['approved_files']):
            _need(set(f)=={'id','path','purpose','identity','sha256','parents'})
            _need(f['id']=='file_'+str(i) and _path(f['path']) and f['purpose'] in ('source','tool','runtime','plugin','git_config','git_absent','socket','root'))
            ident=Identity(**f['identity']);parents=tuple(Identity(**v) for v in f['parents'])
            _need(all(type(getattr(ident,k)) is int and getattr(ident,k)>=0 for k in ('dev','inode','uid','gid','mode','size','mtime_ns','ctime_ns','nlink')))
            _need(_hash(f['sha256']) and parents and all(v.type=='directory' and v.mode&0o022==0 for v in parents))
            files.append(FileSpec(f['id'],f['path'],f['purpose'],ident,f['sha256'],parents))
        _need(len({f.path for f in files})==len(files))
        return Contract(freeze(d),_templates(d),tuple(files))
    except (_Reject,KeyError,TypeError,ValueError,AttributeError):return Problem('invalid_contract')

def check_command(spec,contract,seen):
    if spec.id in seen:return Problem('command_repeated')
    if spec not in _templates(values(contract)):return Problem('invalid_command')
    return None

def git_eligibility(contract):
    d=values(contract);g=d['git_provenance']
    if not (g['complete'] is True and g['immutable'] is True and g['plain_clone'] is True and set(g['categories'])=={'system','global','xdg','local','worktree'} and len(g['categories'])==5 and g['config_literal']==CONFIG):return Problem('missing_prerequisite')
    required={d['prep_root']+'/home/.gitconfig',d['prep_root']+'/home/.config/git/config',d['checkout']+'/.git/config.worktree'}
    if not required<=set(g['absent_paths']) or len(g['absent_paths'])<4:return Problem('missing_prerequisite')
    return None

def effective_model(contract):
    d=values(contract);m=d['baseline'];services=m['services']
    services.pop('test-runner',None)
    for name,image in zip(('go-test-runner','postgres','nats','minio'),IMAGES):
        services[name]['image']=image;services[name]['pull_policy']='never'
    services['go-test-runner'].pop('build',None)
    services['minio']['volumes']=[d['prep_root']+'/minio:/data']
    return m

def project(kind,value,contract):
    """Closed projections; rejected values and names never enter diagnostics."""
    try:
        d=values(contract);out={}
        if kind in ('python_version','git_version','docker_version'):
            product={'python_version':'Python','git_version':'git version','docker_version':'Docker version'}[kind]
            _need(type(value) is str and len(value)<=512,'unsafe_projection')
            match=re.fullmatch(re.escape(product)+r' ([0-9]+\.[0-9]+(?:\.[0-9]+)?)(?:, build [0-9a-f]+)?\n?',value)
            _need(match is not None,'unsafe_projection');out={'product':product,'version':match[1]}
        elif kind=='compose_version':
            _need(type(value) is dict and set(value)<= {'version','build'} and 'version' in value,'unsafe_projection')
            _need(re.fullmatch(r'v?[0-9]+\.[0-9]+\.[0-9]+',value['version']) is not None,'unsafe_projection')
            out={'product':'Compose','version':value['version']}
        elif kind=='context_show':
            _need(value in ('default','default\n'),'unsafe_projection');out={'default':True,'digest':digest(value.encode())}
        elif kind=='context_inspect':
            _need(type(value) is dict and value.get('Name')=='default','unsafe_projection')
            endpoint=value['Endpoints']['docker'];_need(endpoint['Host']==d['local_socket'] and endpoint['SkipTLSVerify'] is False,'unsafe_projection')
            _need(set(value['Endpoints'])=={'docker'},'unsafe_projection')
            out={'local_unix':True,'socket_digest':digest(d['local_socket'].encode()),'valid':True}
        elif kind=='daemon_info':
            _need(value['OSType']=='linux' and value['Architecture'] in ('amd64','x86_64'),'unsafe_projection')
            _need(all(not value.get(k,'') for k in ('HTTPProxy','HTTPSProxy','NoProxy')),'unsafe_projection')
            _need(type(value['ID']) is str and bool(value['ID']),'unsafe_projection')
            out={'OSType':'linux','Architecture':value['Architecture'],'normalized_architecture':'amd64','daemon_digest':digest(value['ID'].encode())}
        elif kind=='daemon_version':
            for side in ('Client','Server'):
                v=value[side];_need(v['Os']=='linux' and v['Arch']=='amd64','unsafe_projection');safe={}
                for key in ('Version','ApiVersion','MinAPIVersion','Os','Arch','GitCommit'):
                    if key not in v: _need(key=='MinAPIVersion','unsafe_projection');continue
                    _need(type(v[key]) is str and len(v[key])<=512 and re.fullmatch('[A-Za-z0-9_.+-]+',v[key]),'unsafe_projection')
                    safe[key]=v[key]
                out[side]=safe
        elif kind in ('create_help','compose_up_help','compose_run_help'):
            _need(type(value) is str,'unsafe_projection')
            flags=d['required_flags'][kind];_need(all(flag in value.split() for flag in flags),'missing_prerequisite')
            out={'flags':{f:True for f in flags},'digest':digest(value.encode())}
        elif kind.startswith('image_') and kind in ('image_runner','image_postgres','image_nats','image_minio'):
            index=('image_runner','image_postgres','image_nats','image_minio').index(kind)
            _need(type(value) is list and len(value)==1,'unsafe_projection');v=value[0]
            _need(v['Id']==IMAGES[index] and v['Os']=='linux' and v['Architecture']=='amd64','unsafe_projection')
            cfg=v['Config'];_need(type(cfg) is dict,'unsafe_projection')
            if index==0:
                env=cfg.get('Env');_need(type(env) is list,'unsafe_projection');seen=set();bad=0
                for entry in env:
                    _need(type(entry) is str and '=' in entry,'unsafe_projection');key,val=entry.split('=',1)
                    if key not in ENV_IMAGE_KEYS:bad+=1;continue
                    _need(key not in seen and bool(val),'unapproved_key');seen.add(key)
                    if key in ('PATH','HOME','SSL_CERT_FILE','SSL_CERT_DIR'):_need(all(_path(x) for x in val.split(':')),'unsafe_projection')
                if bad:return Problem('unapproved_key',bad)
            _need(cfg==d['image_configs'][IMAGES[index]],'unapproved_key')
            root=v['RootFS'];_need(set(root)=={'Type','Layers'} and root['Type']=='layers' and all(re.fullmatch('sha256:[0-9a-f]{64}',s) for s in root['Layers']),'unsafe_projection')
            _need(type(v['RepoDigests']) is list and all(type(s) is str and re.fullmatch('[a-z0-9./_-]+@sha256:[0-9a-f]{64}',s) for s in v['RepoDigests']),'unsafe_projection')
            out={'Id':IMAGES[index],'Os':'linux','Architecture':'amd64','Config':cfg,'config_digest':digest(encode(cfg)),'RootFS':root,'RepoDigests':v['RepoDigests']}
        elif kind in ('compose_baseline','compose_effective'):
            expected=d['baseline'] if kind=='compose_baseline' else effective_model(contract)
            _need(value==expected,'unsafe_projection')
            if kind=='compose_baseline':
                _need(set(value['services'])=={'postgres','nats','minio','go-test-runner','test-runner'} and value['services']['minio']['volumes']==['lifecycle-s3:/data'],'unsafe_projection')
            else:_need(set(value['services'])=={'postgres','nats','minio','go-test-runner'} and all('build' not in v for v in value['services'].values()),'unsafe_projection')
            out={'model':expected}
        elif kind.startswith('inventory_'):
            _need(type(value) is str,'unsafe_projection');lines=value.splitlines()
            if kind=='inventory_names':
                collision=any(n in lines for n in d['planned_names']);_need(not collision,'collision')
            elif kind in ('inventory_owner','inventory_project'):
                _need(all(re.fullmatch('[0-9a-f]{64}',s) for s in lines),'unsafe_projection');_need(not lines,'collision')
            else:raise _Reject('unsafe_projection')
            out={'count':len(lines),'collision':False,'digest':digest(value.encode())}
        elif kind in ('git_head','git_tree','git_status','git_remote','git_symbolic'):
            expected={'git_head':CANDIDATE,'git_tree':TREE,'git_status':'','git_remote':'','git_symbolic':''}[kind]
            _need(value in (expected,expected+'\n') if expected else value=='','unsafe_projection');out={'equal':True}
        elif kind=='git_files':
            _need(type(value) is str,'unsafe_projection');entries=value.split('\x00');_need(entries[-1]=='','unsafe_projection')
            expected={f.path[len(d['checkout'])+1:] for f in contract.files if f.purpose=='source'};names=set()
            for entry in entries[:-1]:
                head,path=entry.split('\t',1);_need(re.fullmatch('100(644|755) [0-9a-f]{40} 0',head) is not None and path in expected and path not in names,'unsafe_projection');names.add(path)
            _need(names==expected,'missing_prerequisite');out={'count':len(names),'digest':digest(value.encode()),'candidate':CANDIDATE}
        else:raise _Reject('unsafe_projection')
        return SafeObservation(kind,freeze(out))
    except _Reject as e:return Problem(e.code)
    except (KeyError,TypeError,ValueError,AttributeError,UnicodeError):return Problem('unsafe_projection')
