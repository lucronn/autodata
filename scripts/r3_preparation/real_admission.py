"""Pure admission for an externally authenticated, single preparation attempt.

ApprovalBundle is supplied by a separately reviewed trusted embedding. Constructing
JSON or this value does not authenticate its provenance. No module performs I/O
at import, and no synthetic admission/observation object is relabelled.
"""
from dataclasses import dataclass
import hashlib
import re
import time
from contextlib import contextmanager
from . import policy as p

CHECKPOINT = '20b2696fcfeef580b43aeb026567e1ab9dd010ee'
WINDOWS = ('python','docker','plugin','git','source','route','socket','root','runtime')
ROLES = ('operator','reviewer','cancellation','host','daemon','installation','watchdog')
MiB = 1024**2


@dataclass(frozen=True, slots=True)
class ApprovalBundle:
    document_sha256: str
    checkpoint: str
    adapter_sha: str
    token: str
    now_ns: int
    expires_ns: int
    identities: tuple
    command_manifest_sha256: str
    channel_artifact: str


@dataclass(frozen=True, slots=True)
class FileIdentity:
    dev: int
    inode: int
    uid: int
    gid: int
    mode: int
    size: int
    mtime_ns: int
    ctime_ns: int
    nlink: int


@dataclass(frozen=True, slots=True)
class Anchor:
    reference: str
    fd: int
    identity: FileIdentity


@dataclass(frozen=True, slots=True)
class FileRecipe:
    id: str
    anchor: str
    components: tuple
    kind: str
    identity: FileIdentity | None
    parents: tuple
    sha256: str | None
    literal: bytes | None


@dataclass(frozen=True, slots=True)
class ActualCommand:
    id: str
    argv: tuple
    cwd: str
    env: tuple
    kind: str
    prerequisites: tuple
    expected_returncode: int = 0


@dataclass(frozen=True, slots=True)
class ActualContract:
    document: bytes
    document_sha256: str
    commands: tuple
    files: tuple
    approvals: ApprovalBundle
    evidence_kind: str = 'preparation_observation'


class _Rejected(Exception):
    pass


class BudgetFault(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)


class JsonBudget:
    """Fixed production JSON ceilings and one nonrenewable attempt ledger.

    Standalone admission measures local CPU elapsed time only. It cannot certify
    freshness or resource accounting for a later collection attempt.
    """
    def __init__(self,outer_deadline_ns=None,cancel=None):
        now=time.monotonic_ns()
        self.outer=now+1800*10**9 if outer_deadline_ns is None else outer_deadline_ns
        if type(self.outer) is not int:raise BudgetFault('integrity')
        self.cancel=cancel;self.limits=p.Limits();self.spent_ns=0;self.fault=None;self._stack=[]

    def check_json(self):
        if self.fault:raise BudgetFault(self.fault)
        now=time.monotonic_ns()
        if self.cancel is not None and self.cancel.is_set():self.fault='cancel'
        elif now>=self.outer:self.fault='deadline'
        elif self._stack and now>=self._stack[-1][1]:self.fault='cap'
        elif self.spent_ns>=60*10**9:self.fault='cap'
        if self.fault:raise BudgetFault(self.fault)

    def require(self,value):
        self.check_json();_need(value)

    @contextmanager
    def operation(self):
        self.check_json();start=time.monotonic_ns()
        deadline=min(self.outer,start+5*10**9,start+max(0,60*10**9-self.spent_ns))
        if self._stack:deadline=min(deadline,self._stack[-1][1])
        self._stack.append((start,deadline))
        try:
            self.check_json();yield self;self.check_json()
        finally:
            self._stack.pop()
            if not self._stack:self.spent_ns+=max(0,time.monotonic_ns()-start)


def _need(value):
    if not value:
        raise _Rejected()


def _hash(value, length=64):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(length)+'}',value) is not None


def _identifier(value):
    return (type(value) is str and re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.:@-]{0,127}',value)
            is not None and not any(x in value.lower() for x in ('synthetic','unresolved','todo')))


def _path(value):
    return (type(value) is str and value.startswith('/') and not any(x in value for x in ('\0','\r','\n'))
            and len(value.encode('utf-8'))<=4096 and len(value.split('/'))<=65
            and (value=='/' or all(x not in ('','.','..') for x in value.split('/')[1:])))


def _budget(value):
    if value is None:return JsonBudget()
    if type(value) is not JsonBudget:raise BudgetFault('integrity')
    return value


def _parse(raw, budget=None):
    budget=_budget(budget)
    with budget.operation():
        budget.require(type(raw) is bytes and len(raw)<=16*MiB)
        result=p.parse_bounded_json((raw[i:i+65536] for i in range(0,len(raw),65536)),budget)
        budget.require(not isinstance(result,p.Problem))
        return result


def serialize(value, budget=None):
    budget=_budget(budget)
    with budget.operation():
        result=p.serialize_bounded(value,budget)
        budget.require(not isinstance(result,p.Problem))
        return result


def values(contract, budget=None):
    _need(type(contract) is ActualContract)
    return _parse(contract.document,budget)


def command_graph(d):
    """Construct the only permitted literal graph. This function performs no I/O."""
    P,G,D=(d['tools'][n] for n in ('python','git','docker'))
    R,C,T=d['prep_root'],d['checkout'],d['token']
    env=tuple(sorted(d['env'].items()))
    gp=(G,'--no-optional-locks','-C',C)
    cp=(D,'compose','--env-file','/dev/null','-p','autodata-r3-'+T,'-f',
        C+'/infra/compose/compose.article-lifecycle-test.yaml')
    daemon=('docker','runtime','route','socket','context_show','context_inspect')
    chain=daemon+('daemon_version','daemon_info')
    git=('git','runtime','source')
    rows=[('python_version',(P,'-I','-B','--version'),('python','runtime')),
          ('git_version',(G,'--version'),('git','runtime')),
          ('docker_version',(D,'--version'),('docker','runtime')),
          ('compose_version',(D,'compose','version','--format','json'),('docker','plugin','runtime')),
          ('context_show',(D,'context','show'),('docker','runtime','route','socket')),
          ('context_inspect',(D,'context','inspect','default','--format','{{json .}}'),
           ('docker','runtime','route','socket','context_show')),
          ('daemon_version',(D,'version','--format','{{json .}}'),daemon),
          ('daemon_info',(D,'info','--format','{{json .}}'),daemon),
          ('create_help',(D,'create','--help'),('docker','runtime')),
          ('compose_up_help',(D,'compose','up','--help'),('docker','plugin','runtime')),
          ('compose_run_help',(D,'compose','run','--help'),('docker','plugin','runtime'))]
    rows += [(name,(D,'image','inspect',image),chain) for name,image in zip(p.COMMAND_IDS[11:15],p.IMAGES)]
    rows += [('inventory_names',(D,'ps','-a','--no-trunc','--format','{{.Names}}'),chain),
             ('inventory_owner',(D,'ps','-aq','--no-trunc','--filter','label=autodata.owner='+T),chain),
             ('inventory_project',(D,'ps','-aq','--no-trunc','--filter',
                                   'label=com.docker.compose.project=autodata-r3-'+T),chain)]
    rows += [(name,gp+args,git) for name,args in (
        ('git_files',('ls-files','--stage','-z')),('git_head',('rev-parse','--verify','HEAD')),
        ('git_tree',('rev-parse','HEAD^{tree}')),('git_status',('status','--porcelain=v1','--untracked-files=all')),
        ('git_remote',('remote',)),('git_symbolic',('symbolic-ref','-q','HEAD')))]
    rows += [('compose_baseline',cp+('config','--format','json'),git+('docker','plugin')+p.COMMAND_IDS[18:24]),
             ('compose_effective',cp+('-f',R+'/effective.json','config','--format','json'),
              git+('docker','plugin','compose_baseline','effective_output'))]
    return tuple(ActualCommand(name,argv,C if name in p.COMMAND_IDS[24:] else R,env,
                'source' if name in p.COMMAND_IDS[18:] else 'ordinary',prereqs,
                1 if name=='git_symbolic' else 0) for name,argv,prereqs in rows)


def _same(left,right,budget=None):
    """JSON equality without Python's bool/int or container subclass coercion."""
    if budget is not None:budget.check_json()
    if type(left) is not type(right):return False
    if type(left) is dict:
        return set(left)==set(right) and all(_same(left[k],right[k],budget) for k in left)
    if type(left) is list:
        return len(left)==len(right) and all(_same(x,y,budget) for x,y in zip(left,right))
    return type(left) in (str,int,float,bool,type(None)) and left==right


def _identity(d,budget):
    need=budget.require
    need(type(d) is dict and set(d)==set(FileIdentity.__dataclass_fields__))
    need(all(type(v) is int and v>=0 for v in d.values()))
    need(d['inode']>0 and d['nlink']>0 and d['mode']<=0o177777)
    return FileIdentity(**d)


def _recipes(d,budget):
    need=budget.require
    need(type(d['anchors']) is list and 1<=len(d['anchors'])<=128)
    anchors={}
    for row in d['anchors']:
        need(type(row) is dict and set(row)=={'reference','path','identity'})
        need(_identifier(row['reference']) and _path(row['path']) and row['reference'] not in anchors)
        identity=_identity(row['identity'],budget);need(identity.mode&0o170000==0o040000 and not identity.mode&0o022)
        anchors[row['reference']]=row
    root=anchors.get('root');need(root is not None and root['path']==d['prep_root'] and root['identity']['mode']&0o7777==0o700)
    for name in ('home','artifacts','minio'):
        row=anchors.get(name);need(row is not None and row['path']==d['prep_root']+'/'+name and row['identity']['mode']&0o7777==0o700 and row['identity']['dev']==root['identity']['dev'] and row['identity']['uid']==root['identity']['uid'])
    files=[]
    need(type(d['files']) is list and len(d['files'])<=20000)
    for row in d['files']:
        need(type(row) is dict and set(row)=={'id','anchor','components','kind','identity','parents','sha256','literal'})
        need(_identifier(row['id']) and row['anchor'] in anchors)
        components=row['components'];need(type(components) is list and 1<=len(components)<=64)
        need(all(type(x) is str and x not in ('','.','..') and '/' not in x and
                  not any(c in x for c in ('\0','\r','\n')) for x in components))
        need(_path(anchors[row['anchor']]['path'].rstrip('/')+'/'+ '/'.join(components)))
        need(row['kind'] in ('regular','absence','socket'))
        ident=None if row['identity'] is None else _identity(row['identity'],budget)
        parents=tuple(_identity(x,budget) for x in row['parents'])
        need(len(parents)==len(components) and parents[0]==_identity(anchors[row['anchor']]['identity'],budget))
        need(all(x.mode&0o170000==0o040000 and not x.mode&0o022 for x in parents))
        if row['kind']=='absence': need(ident is None and row['sha256'] is None and row['literal'] is None)
        elif row['kind']=='socket': need(ident is not None and ident.mode&0o170000==0o140000 and row['sha256'] is None and row['literal'] is None)
        else:
            need(ident is not None and ident.mode&0o170000==0o100000 and not ident.mode&0o022 and ident.nlink==1 and ident.size<=64*MiB and _hash(row['sha256']))
            need(row['literal'] is None or row['literal']==p.CONFIG)
        files.append(FileRecipe(row['id'],row['anchor'],tuple(components),row['kind'],ident,parents,
                                row['sha256'],None if row['literal'] is None else row['literal'].encode()))
    need(len({x.id for x in files})==len(files))
    need(len({(x.anchor,x.components) for x in files})==len(files))
    need(type(d['prerequisites']) is dict and set(d['prerequisites'])==set(WINDOWS))
    for group,ids in d['prerequisites'].items():
        need(type(ids) is list and ids and len(ids)==len(set(ids)) and set(ids)<={f.id for f in files})
    return tuple(files)


_KEYS = frozenset(('schema_version','evidence_kind','checkpoint','adapter_sha','token','issued_ns','expires_ns',
 'identities','prep_root','checkout','local_socket','tools','env','windows','resources','git_provenance',
 'anchors','files','prerequisites','image_configs','image_rootfs','image_repo_digests','baseline','required_flags',
 'tracked_manifest','planned_names','output_owners','daemon_identity_sha256','created_container_evidence','commands'))


def _validate_actual(document, approvals, budget):
    """Validate already authenticated external bindings; never discover authority."""
    need=budget.require
    try:
        need(type(approvals) is ApprovalBundle)
        need(all(_hash(getattr(approvals,n)) for n in ('document_sha256','command_manifest_sha256','channel_artifact')))
        need(type(document) is bytes and hashlib.sha256(document).hexdigest()==approvals.document_sha256)
        d=_parse(document,budget);need(type(d) is dict and set(d)==_KEYS)
        need(type(d['schema_version']) is int and d['schema_version']==1)
        need(d['evidence_kind']=='preparation_observation' and d['checkpoint']==CHECKPOINT==approvals.checkpoint)
        need(_hash(d['adapter_sha'],40) and d['adapter_sha']==approvals.adapter_sha)
        need(type(d['token']) is str and re.fullmatch('[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}',d['token']) is not None and d['token']==approvals.token)
        need(all(type(v) is int for v in (d['issued_ns'],d['expires_ns'],approvals.now_ns,approvals.expires_ns)))
        need(0<=d['issued_ns']<=approvals.now_ns<d['expires_ns']==approvals.expires_ns<=d['issued_ns']+1800*10**9)
        ids=d['identities'];need(type(ids) is dict and set(ids)==set(ROLES))
        for row in ids.values():
            need(type(row) is dict and set(row)=={'person','session','artifact'} and
                  _identifier(row['person']) and _identifier(row['session']) and _hash(row['artifact']))
        need(ids['operator']['person']!=ids['reviewer']['person'] and ids['operator']['session']!=ids['reviewer']['session'])
        need(type(approvals.identities) is tuple and approvals.identities==tuple((n,v['person'],v['session'],v['artifact']) for n,v in sorted(ids.items())))
        need(all(_path(d[n]) for n in ('prep_root','checkout')) and d['prep_root']!=d['checkout'])
        need(type(d['local_socket']) is str and d['local_socket'].startswith('unix://') and _path(d['local_socket'][7:]))
        need(type(d['tools']) is dict and set(d['tools'])=={'python','git','docker','compose'} and all(_path(v) for v in d['tools'].values()))
        env=d['env'];need(type(env) is dict and set(env)==p.ENV_KEYS)
        need(all(type(v) is str and v and not any(c in v for c in ('\0','\r','\n')) for v in env.values()))
        expected={'HOME':d['prep_root']+'/home','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC',
                  'AUTODATA_R3_TEST_IMAGE':p.IMAGES[0],'AUTODATA_R3_CANDIDATE_SHA':p.CANDIDATE,
                  'AUTODATA_LIFECYCLE_ARTIFACT_DIR':d['prep_root']+'/artifacts'}
        need(all(env[k]==v for k,v in expected.items()) and all(_path(v) for v in env['PATH'].split(':')))
        need(_identifier(env['USER']) and _identifier(env['LOGNAME']))
        need(type(d['windows']) is dict and set(d['windows'])==set(WINDOWS) and all(_hash(v) for v in d['windows'].values()))
        r=d['resources'];need(type(r) is dict and set(r)=={'memory_bytes','processes','open_fds','no_swap','no_core','containment','watchdog','embedding'})
        need(all(type(r[k]) is int and r[k]==v for k,v in (('memory_bytes',1024**3),('processes',32),('open_fds',128))))
        need(all(_hash(r[k]) for k in ('no_swap','no_core','containment','watchdog','embedding')))
        g=d['git_provenance'];need(type(g) is dict and set(g)=={'config_literal','installation_manifest','installation_sources','absent_paths'})
        need(g['config_literal']==p.CONFIG and _hash(g['installation_manifest']))
        absent=g['absent_paths'];need(type(absent) is list and len(absent)>=4 and len(absent)==len(set(absent)) and all(_path(v) for v in absent))
        need({d['prep_root']+'/home/.gitconfig',d['prep_root']+'/home/.config/git/config',d['checkout']+'/.git/config.worktree'}<=set(absent))
        sources=g['installation_sources'];need(type(sources) is dict and set(sources)=={'system','global_paths','xdg','local','worktree'})
        need(sources['global_paths']==[d['prep_root']+'/home/.gitconfig'] and sources['xdg']==[d['prep_root']+'/home/.config/git/config'] and sources['local']==[d['checkout']+'/.git/config'] and sources['worktree']==[d['checkout']+'/.git/config.worktree'])
        declared=[]
        for category,paths in sources.items():
            need(type(paths) is list and paths and all(_path(v) for v in paths))
            if category!='local':declared.extend(paths)
        need(len(declared)==len(set(declared)) and set(declared)==set(absent))
        need(hashlib.sha256(serialize(sources,budget)).hexdigest()==g['installation_manifest'])
        files=_recipes(d,budget)
        # A route/window attestation never replaces concrete file identities.
        pathmap={next(x['path'] for x in d['anchors'] if x['reference']==f.anchor).rstrip('/')+'/'+ '/'.join(f.components):f for f in files}
        need(all(path in pathmap and pathmap[path].kind=='regular' for path in d['tools'].values()))
        need(all(path in pathmap and pathmap[path].kind=='absence' for path in absent))
        need(d['local_socket'][7:] in pathmap and pathmap[d['local_socket'][7:]].kind=='socket')
        cfg=pathmap.get(d['checkout']+'/.git/config');need(cfg is not None and cfg.literal==p.CONFIG.encode())
        # Bind every dependency window to concrete recipes, rather than trusting
        # membership in an arbitrary nonempty list supplied by the document.
        groups=d['prerequisites'];R=d['prep_root'];C=d['checkout']
        required={name:set() for name in WINDOWS}
        for tool,group in (('python','python'),('git','git'),('docker','docker'),('compose','plugin')):
            required[group].add(pathmap[d['tools'][tool]].id)
        required['git'].update(pathmap[x].id for x in absent)
        required['git'].add(cfg.id)
        required['socket'].add(pathmap[d['local_socket'][7:]].id)
        required['route'].update(required['socket'])
        for path,recipe in pathmap.items():
            if path.startswith(C+'/'):required['source'].add(recipe.id)
            elif path.startswith(R+'/'):
                required['root'].add(recipe.id)
                if recipe.kind=='absence':required['route'].add(recipe.id)
            elif recipe.kind=='regular':required['runtime'].add(recipe.id)
        for group,ids in required.items():need(ids<=set(groups[group]))
        need(all(set(d[key])==set(p.IMAGES) for key in ('image_configs','image_rootfs','image_repo_digests')))
        for index,image in enumerate(p.IMAGES):
            config=d['image_configs'][image];need(type(config) is dict and 'Env' in config and 'WorkingDir' in config)
            need(_path(config['WorkingDir']))
            _validate_env(config['Env'],index==0,budget)
            need(type(d['image_rootfs'][image]) is dict and set(d['image_rootfs'][image])=={'Type','Layers'} and d['image_rootfs'][image]['Type']=='layers')
            need(type(d['image_rootfs'][image]['Layers']) is list and all(type(v) is str and v.startswith('sha256:') and _hash(v[7:]) for v in d['image_rootfs'][image]['Layers']))
            need(type(d['image_repo_digests'][image]) is list and all(type(v) is str and re.fullmatch(r'[a-z0-9./:_-]+@sha256:[0-9a-f]{64}',v) for v in d['image_repo_digests'][image]))
        need(type(d['baseline']) is dict and type(d['baseline'].get('services')) is dict and set(d['baseline']['services'])=={'postgres','nats','minio','go-test-runner','test-runner'})
        need(all(type(v) is dict for v in d['baseline']['services'].values()))
        need(set(d['required_flags'])=={'create_help','compose_up_help','compose_run_help'} and all(type(v) is list and v and all(type(x) is str and re.fullmatch('--[a-z-]+',x) for x in v) for v in d['required_flags'].values()))
        need(_hash(d['tracked_manifest']) and _hash(d['daemon_identity_sha256']))
        need(d['created_container_evidence'] is None or _hash(d['created_container_evidence']))
        need(type(d['planned_names']) is list and all(_identifier(v) for v in d['planned_names']))
        need(d['output_owners']=={n:'operator' if n in p.OUTPUT_NAMES[:2] else 'reviewer' if n=='independent-review.md' else 'collector' for n in p.OUTPUT_NAMES})
        commands=command_graph(d)
        manifest=[dict(id=c.id,argv=list(c.argv),cwd=c.cwd,env=dict(c.env),kind=c.kind,prerequisites=list(c.prerequisites)) for c in commands]
        need(_same(d['commands'],manifest,budget) and hashlib.sha256(serialize(manifest,budget)).hexdigest()==approvals.command_manifest_sha256)
        return ActualContract(document,approvals.document_sha256,commands,files,approvals)
    except (_Rejected,KeyError,TypeError,ValueError,AttributeError,UnicodeError,OverflowError,MemoryError,RecursionError):
        return p.Problem('invalid_actual_contract')


def _admit_actual(document,approvals,budget):
    budget=_budget(budget)
    with budget.operation():return _validate_actual(document,approvals,budget)


def admit_actual(document,approvals):
    """No host/file/process effects; local monotonic timing only bounds work."""
    try:return _admit_actual(document,approvals,JsonBudget())
    except BudgetFault:return p.Problem('actual_resource_limit')


def _validate_env(env,runner,budget):
    need=budget.require
    need(type(env) is list and all(type(v) is str and '=' in v for v in env))
    pairs=[v.split('=',1) for v in env];need(len({k for k,v in pairs})==len(pairs))
    if runner:
        need(all(k in p.ENV_IMAGE_KEYS for k,v in pairs))
        for key,value in pairs:
            need(value and not any(x in value for x in ('\0','\r','\n')))
            if key in ('PATH','SSL_CERT_DIR'): need(all(_path(v) for v in value.split(':')))
            elif key in ('HOME','SSL_CERT_FILE'): need(_path(value))
            elif key in ('LANG','LC_ALL'): need(value in ('C','C.UTF-8','en_US.UTF-8'))
            elif key=='TZ': need(value=='UTC')


def _effective_model(contract,budget):
    budget.check_json();d=values(contract,budget);model=d['baseline'];s=model['services'];s.pop('test-runner')
    for name,image in zip(('go-test-runner','postgres','nats','minio'),p.IMAGES):
        s[name]['image']=image;s[name]['pull_policy']='never'
    s['go-test-runner'].pop('build',None);s['minio']['volumes']=[d['prep_root']+'/minio:/data']
    _need(set(s)=={'go-test-runner','postgres','nats','minio'} and not any('build' in v for v in s.values()))
    return model


def _project(kind, value, contract, budget):
    """Only closed projections leave this boundary; rejected bodies are withheld."""
    need=budget.require
    try:
        d=values(contract,budget);need(kind in p.COMMAND_IDS)
        if kind in ('python_version','git_version','docker_version'):
            need(type(value) is str and len(value)<=512)
            prefixes={'python_version':r'Python ','git_version':r'git version ','docker_version':r'Docker version '}
            text=value.rstrip('\n');need(re.fullmatch(prefixes[kind]+r'[0-9]+(?:\.[0-9]+){1,3}(?:[a-z0-9.,+ -]{0,128})?',text))
            return {'version':text}
        if kind=='compose_version':
            need(type(value) is dict and type(value.get('version')) is str and re.fullmatch(r'v?[0-9]+(?:\.[0-9]+){1,3}',value['version']))
            return {'version':value['version']}
        if kind=='context_show': need(value=='default\n' or value=='default');return {'context':'default'}
        if kind=='context_inspect':
            need(type(value) is dict and value.get('Name')=='default' and type(value.get('Endpoints')) is dict and set(value['Endpoints'])=={'docker'})
            endpoint=value['Endpoints']['docker'];need(type(endpoint) is dict and set(endpoint)=={'Host','SkipTLSVerify'} and endpoint['Host']==d['local_socket'] and endpoint['SkipTLSVerify'] is False)
            return {'context':'default','endpoint_sha256':hashlib.sha256(d['local_socket'].encode()).hexdigest(),'skip_tls_verify':False}
        if kind=='daemon_info':
            need(type(value) is dict and value.get('OSType')=='linux' and value.get('Architecture') in ('amd64','x86_64') and all(value.get(k)=='' for k in ('HTTPProxy','HTTPSProxy','NoProxy')))
            need(type(value.get('ID')) is str and hashlib.sha256(value['ID'].encode()).hexdigest()==d['daemon_identity_sha256'])
            return {'os':'linux','raw_architecture':value['Architecture'],'architecture':'amd64','identity_sha256':d['daemon_identity_sha256']}
        if kind=='daemon_version':
            need(type(value) is dict and type(value.get('Server')) is dict)
            v=value['Server'];need(v.get('Os')=='linux' and v.get('Arch') in ('amd64','x86_64') and type(v.get('Version')) is str and re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}',v['Version']))
            return {'os':'linux','raw_architecture':v['Arch'],'architecture':'amd64','version':v['Version']}
        if kind in p.COMMAND_IDS[8:11]:
            need(type(value) is str and all(flag in value.split() for flag in d['required_flags'][kind]))
            return {'flags':d['required_flags'][kind]}
        if kind in p.COMMAND_IDS[11:15]:
            image=p.IMAGES[p.COMMAND_IDS[11:15].index(kind)]
            need(type(value) is list and len(value)==1 and type(value[0]) is dict)
            v=value[0];need(v.get('Id')==image and v.get('Os')=='linux' and v.get('Architecture')=='amd64')
            need(_same(v.get('Config'),d['image_configs'][image],budget) and _same(v.get('RootFS'),d['image_rootfs'][image],budget) and _same(v.get('RepoDigests'),d['image_repo_digests'][image],budget))
            _validate_env(v['Config']['Env'],kind=='image_runner',budget)
            return {'Id':image,'Os':'linux','Architecture':'amd64','Config':v['Config'],
                    'Config_sha256':hashlib.sha256(serialize(v['Config'],budget)).hexdigest(),
                    'RootFS':v['RootFS'],'RepoDigests':v['RepoDigests']}
        if kind=='inventory_names':
            need(type(value) is str and not any(x in set(value.splitlines()) for x in d['planned_names']))
            return {'planned_name_collisions':0}
        if kind in ('inventory_owner','inventory_project','git_status','git_remote','git_symbolic'):
            need(value=='');return {'empty':True}
        if kind=='git_head': need(value==p.CANDIDATE+'\n');return {'candidate':p.CANDIDATE}
        if kind=='git_tree': need(value==p.TREE+'\n');return {'tree':p.TREE}
        if kind=='git_files':
            need(type(value) is bytes and hashlib.sha256(value).hexdigest()==d['tracked_manifest'])
            return {'tracked_manifest_sha256':d['tracked_manifest']}
        if kind in ('compose_baseline','compose_effective'):
            expected=d['baseline'] if kind=='compose_baseline' else effective_model(contract,budget)
            need(_same(value,expected,budget));return expected
        raise _Rejected()
    except (_Rejected,KeyError,ValueError,TypeError,UnicodeError,MemoryError,RecursionError):
        return p.Problem('unsafe_observation')


def effective_model(contract,budget=None):
    budget=_budget(budget)
    with budget.operation():return _effective_model(contract,budget)


def project(kind,value,contract,budget=None):
    budget=_budget(budget)
    with budget.operation():return _project(kind,value,contract,budget)
