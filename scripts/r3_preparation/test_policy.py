"""Synthetic policy acceptance tests; loads only the two sibling source files."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from dataclasses import replace

HERE = Path(__file__).resolve().parent

def load(name):
    package = 'r3_preparation'
    if package not in sys.modules:
        p = types.ModuleType(package)
        p.__path__ = [str(HERE)]
        sys.modules[package] = p
    fullname = package + '.' + name
    if fullname not in sys.modules:
        spec = importlib.util.spec_from_file_location(fullname, HERE / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = module
        spec.loader.exec_module(module)
    return sys.modules[fullname]

# Absence is an honest import failure during the first red run.
p = load('policy')
SENTINEL = 'SECRET_SENTINEL_ABC'
CONFIG = '[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n\tlogallrefupdates = true\n'

def fixture():
    root = '/synthetic/run-123456781234423492341234567890ab'
    return dict(schema_version=1, evidence_kind='synthetic', trusted=False,
                runtime_accepted=False, host_observed=False,
                operator_identity='synthetic-operator', operator_session='session-one',
                reviewer_identity='synthetic-reviewer', reviewer_session='session-two',
                cancellation_owner='synthetic-cancel', host_identity='synthetic-host',
                daemon_owner='synthetic-daemon', local_socket='unix:///synthetic/docker.sock',
                python_abs='/synthetic/python3', git_abs='/synthetic/git',
                docker_abs='/synthetic/docker', compose_plugin_abs='/synthetic/compose',
                prep_root=root, token='123456781234423492341234567890ab',
                checkout='/synthetic/clone', checkpoint='e414e8537c8a6f0bc99747f6db09782b7743a949',
                review_pin='a'*64, manifest_pin='b'*64,
                candidate='4d82e413e04fb2401ac7bc28dc828375ac662180',
                tree='d9fb2a8f49beacd009374a76327d0736c1fc9b0a',
                issued_tick=0, expires_tick=1800000,
                acceptances={k:'synthetic-approved' for k in
                    ('freshness','storage','capture','immutability','interruption','preflight','review','owner','runtime','parents')},
                git_provenance=dict(owner='synthetic-git-owner', complete=True,
                    categories=['system','global','xdg','local','worktree'],
                    immutable=True, plain_clone=True, config_literal=CONFIG,
                    absent_paths=['/synthetic/system.gitconfig',root+'/home/.gitconfig',
                                  root+'/home/.config/git/config','/synthetic/clone/.git/config.worktree']),
                approved_files=[], planned_names=['autodata-compat-123456781234423492341234567890ab'],
                env={'PATH':'/synthetic/bin','HOME':root+'/home','USER':'synthetic',
                     'LOGNAME':'synthetic','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC',
                     'AUTODATA_R3_TEST_IMAGE':'sha256:b43f27cfb2dc268b00baf0458bd50f411caccb8d23f037c2819d1d304463fc8c',
                     'AUTODATA_R3_CANDIDATE_SHA':'4d82e413e04fb2401ac7bc28dc828375ac662180',
                     'AUTODATA_LIFECYCLE_ARTIFACT_DIR':root+'/artifacts'},
                image_configs={image:{'Env':['PATH=/usr/bin:/bin'],'WorkingDir':'/'} for image in p.IMAGES},
                baseline={'services':{'postgres':{'image':'pg'},'nats':{'image':'nats'},
                    'minio':{'image':'minio','volumes':['lifecycle-s3:/data']},
                    'go-test-runner':{'build':'.'},'test-runner':{'image':'test'}}},
                required_flags={'create_help':['--pull'],'compose_up_help':['--no-build'],
                                'compose_run_help':['--no-deps']},
                commands=['python_version'], output_owners={name:('reviewer' if name=='independent-review.md' else 'collector') for name in p.OUTPUT_NAMES})

def contract(**changes):
    f=fixture(); f.update(changes)
    result=p.admit_contract(json.dumps(f).encode())
    if isinstance(result,p.Problem):
        raise AssertionError(result)
    return result

class PolicyTests(unittest.TestCase):
    def problem(self, value, code=None):
        self.assertIsInstance(value,p.Problem)
        if code: self.assertEqual(value.code,code)
        self.assertNotIn(SENTINEL,repr(value))

    def test_admission_is_strict_and_synthetic(self):
        c=contract()
        self.assertFalse(c.trusted); self.assertFalse(c.host_observed)
        for key,value in [('trusted',True),('runtime_accepted',True),('host_observed',True),
                          ('evidence_kind','real'),('operator_session','UNRESOLVED'),
                          ('reviewer_session','session-one'),('token','TODO'),
                          ('checkpoint','0'*40),('expires_tick',0),('unexpected',SENTINEL)]:
            with self.subTest(key=key):
                f=fixture(); f[key]=value
                self.problem(p.admit_contract(json.dumps(f).encode()))
        for key in fixture():
            f=fixture(); del f[key]
            self.problem(p.admit_contract(json.dumps(f).encode()))
        f=fixture(); f['acceptances']['owner']=True
        self.problem(p.admit_contract(json.dumps(f).encode()))
        self.problem(p.admit_contract(b'{"schema_version":1,"schema_version":1}'),'duplicate_key')

    def test_commands_match_exact_argv_env_cwd_and_once(self):
        c=contract(commands=list(p.COMMAND_IDS))
        for spec in c.commands:
            self.assertIsNone(p.check_command(spec,c,set()))
            for bad in (replace(spec,argv=spec.argv+('-c',)),replace(spec,argv=('/wrong',)+spec.argv[1:]),
                        replace(spec,cwd='/wrong'),replace(spec,env=spec.env+(('DOCKER_HOST','tcp://bad'),)),
                        replace(spec,stdin='PIPE'),replace(spec,close_fds=False)):
                self.problem(p.check_command(bad,c,set()))
            self.problem(p.check_command(spec,c,{spec.id}),'command_repeated')
        self.assertEqual(c.commands[0].argv,('/synthetic/python3','-I','-B','--version'))
        for forbidden in ('create','up','run','pull','build','down','inspect_container'):
            f=fixture(); f['commands']=[forbidden]
            self.problem(p.admit_contract(json.dumps(f).encode()))
        f=fixture();f['env']['DOCKER_HOST']='tcp://bad'; self.problem(p.admit_contract(json.dumps(f).encode()))

    def test_git_requires_complete_provenance_and_literal_config(self):
        c=contract(); self.assertIsNone(p.git_eligibility(c))
        for key,value in [('complete',False),('categories',['local']),('immutable',False),
                          ('plain_clone',False),('config_literal',CONFIG+'\n')]:
            f=fixture();f['git_provenance'][key]=value
            cc=p.admit_contract(json.dumps(f).encode())
            if not isinstance(cc,p.Problem): self.problem(p.git_eligibility(cc))
        for text in (CONFIG+'[include]\npath=x',CONFIG+'[core]\nfsmonitor=x',CONFIG.replace('true','false',1)):
            f=fixture();f['git_provenance']['config_literal']=text
            cc=p.admit_contract(json.dumps(f).encode())
            self.problem(cc if isinstance(cc,p.Problem) else p.git_eligibility(cc))

    def test_json_streams_duplicates_unicode_and_numeric_rejection(self):
        self.assertEqual(p.parse_bounded_json([b'{"a":[1,',b'true,null,"\\uD83D\\uDE00"]}'],p.Limits()),{'a':[1,True,None,'😀']})
        for chunks,code in [([b'{"x":{"a":1,',b'"a":2}}'],'duplicate_key'),
                            ([b'"\xff"'],'invalid_json'),([b'"\\uD800"'],'invalid_json'),
                            ([b'NaN'],'invalid_json'),([b'Infinity'],'invalid_json'),
                            ([b'{} {}'],'invalid_json'),([b'01'],'invalid_json'),
                            ([b'1e999'],'invalid_json'),([b'1'*129],'cap')]:
            self.problem(p.parse_bounded_json(chunks,p.Limits()),code)

    def test_json_exact_and_plus_one_bounds(self):
        for field,ok,bad,n in [('json_depth',b'[[0]]',b'[[[0]]]',2),
                               ('json_nodes',b'[1,2]',b'[1,2,3]',3),
                               ('json_string',b'"abcd"',b'"abcde"',4),
                               ('json_members',b'{"a":0,"b":0}',b'{"a":0,"b":0,"c":0}',2),
                               ('document_bytes',b'[1]',b'[12]',3)]:
            limits=replace(p.Limits(),**{field:n})
            self.assertNotIsInstance(p.parse_bounded_json([ok],limits),p.Problem)
            self.problem(p.parse_bounded_json([bad],limits),'cap')
        self.problem(p.parse_bounded_json([b' '*65537],p.Limits()),'cap')
        self.assertEqual(p.parse_bounded_json([b'"'+b'a'*65534+b'"'],p.Limits()),'a'*65534)

    def test_daemon_context_and_versions_are_closed(self):
        c=contract()
        for arch in ('amd64','x86_64'):
            v=p.project('daemon_info',{'OSType':'linux','Architecture':arch,'ID':SENTINEL,'HTTPProxy':'','HTTPSProxy':'','NoProxy':''},c)
            self.assertIsInstance(v,p.SafeObservation);self.assertNotIn(SENTINEL,repr(v));self.assertIn(('normalized_architecture','amd64'),v.data)
        for arch in ('aarch64','arm64'):
            self.problem(p.project('daemon_info',{'OSType':'linux','Architecture':arch,'ID':'id'},c))
        self.problem(p.project('daemon_info',{'OSType':'linux','Architecture':'amd64','ID':'id','HTTPProxy':SENTINEL},c))
        self.problem(p.project('context_show','remote',c))
        for endpoint in ('tcp://bad','ssh://bad'):
            self.problem(p.project('context_inspect',{'Name':'default','Endpoints':{'docker':{'Host':endpoint,'SkipTLSVerify':False}}},c))
        self.assertIsInstance(p.project('python_version','Python 3.12.1\n',c),p.SafeObservation)
        self.problem(p.project('python_version','Python '+SENTINEL,c))

    def test_image_env_diagnostics_never_copy_arbitrary_names(self):
        c=contract()
        image={'Id':p.IMAGES[0],'Os':'linux','Architecture':'amd64','Config':{'Env':['PATH=/usr/bin:/bin'],'WorkingDir':'/'},'RootFS':{'Type':'layers','Layers':['sha256:'+'c'*64]},'RepoDigests':[]}
        self.assertIsInstance(p.project('image_runner',[image],c),p.SafeObservation)
        for env in ([SENTINEL+'=secret'],['PYTHON_VERSION=secret'],['PYTHON_SHA256='],['PATH=/bin','PATH=/bin'],['PATH=relative']):
            v=copy.deepcopy(image);v['Config']['Env']=env
            self.problem(p.project('image_runner',[v],c))
        for key,value in [('Architecture','x86_64'),('Id','sha256:'+'0'*64)]:
            v=copy.deepcopy(image);v[key]=value;self.problem(p.project('image_runner',[v],c))
        v=copy.deepcopy(image);v['Config'][SENTINEL]='secret';self.problem(p.project('image_runner',[v],c))
        self.problem(p.project('image_runner',[image,image],c))
        self.problem(p.project(SENTINEL,{SENTINEL:SENTINEL},c))

    def test_compose_full_equality_and_inventory_privacy(self):
        c=contract(); base=fixture()['baseline']
        self.assertIsInstance(p.project('compose_baseline',base,c),p.SafeObservation)
        effective=p.effective_model(c)
        self.assertEqual(set(effective['services']),{'postgres','nats','minio','go-test-runner'})
        self.assertEqual(effective['services']['minio']['volumes'],[fixture()['prep_root']+'/minio:/data'])
        self.assertIsInstance(p.project('compose_effective',effective,c),p.SafeObservation)
        for change in ('service','build','volume','secret','redacted'):
            v=copy.deepcopy(effective)
            if change=='service':v['services']['extra']={}
            elif change=='build':v['services']['go-test-runner']['build']='.'
            elif change=='volume':v['services']['minio']['volumes'].append('x:/data')
            else:v[change]=SENTINEL
            self.problem(p.project('compose_effective',v,c))
        v=p.project('inventory_names',SENTINEL+'\n',c)
        self.assertIsInstance(v,p.SafeObservation);self.assertNotIn(SENTINEL,repr(v))
        self.problem(p.project('inventory_names',fixture()['planned_names'][0]+'\n',c),'collision')

    def test_exact_production_limits(self):
        l=p.Limits()
        expected={'input_files':20000,'metadata_entries':40000,'file_bytes':64*1024**2,'input_bytes':1024**3,
                  'chunk_bytes':65536,'file_ms':5000,'files_ms':300000,'document_bytes':16*1024**2,
                  'json_nodes':1000000,'json_depth':64,'json_string':1024**2,'json_members':20000,
                  'operation_ms':5000,'json_ms':60000,'write_ms':5000,'writes_ms':60000,
                  'command_bytes':16*1024**2,'capture_bytes':128*1024**2,'output_bytes':128*1024**2,
                  'command_ms':10000,'source_command_ms':30000,'outer_ms':1800000,
                  'free_bytes':1024**3,'term_ms':2000,'kill_ms':2000}
        self.assertEqual(vars(l),expected)

class StreamingSerializationTests(unittest.TestCase):
    def test_serialization_charges_before_allocating_next_token(self):
        for value in ({'x':'a'*100}, {'x':[1]*10}, {'x':{'y':{'z':0}}}):
            limits=replace(p.Limits(),document_bytes=20,json_string=10,json_members=3,json_depth=2)
            result=p.serialize_bounded(value,limits)
            self.assertIsInstance(result,p.Problem);self.assertEqual(result.code,'cap')
        self.assertEqual(p.serialize_bounded({'a':[1,True,None]},p.Limits()),b'{"a":[1,true,null]}')
        self.assertIsInstance(p.serialize_bounded({SENTINEL:float('nan')},p.Limits()),p.Problem)

    def test_bounded_parser_and_serializer_observe_operation_budget(self):
        class Budget:
            limits=p.Limits()
            def __init__(self):self.calls=0
            def check_json(self):
                self.calls+=1
                if self.calls>5:raise p._Reject('deadline')
        self.assertEqual(p.parse_bounded_json([b'"long string"'],Budget()),p.Problem('deadline'))
        self.assertEqual(p.serialize_bounded({'x':'long string'},Budget()),p.Problem('deadline'))

class ClosedLiteralProjectionTests(unittest.TestCase):
    def test_daemon_version_never_copies_arbitrary_identifiers(self):
        c=contract()
        v={side:{'Version':'27.1.0','ApiVersion':'1.46','MinAPIVersion':'1.24','Os':'linux','Arch':'amd64','GitCommit':'a'*7} for side in ('Client','Server')}
        self.assertIsInstance(p.project('daemon_version',v,c),p.SafeObservation)
        for side in ('Client','Server'):
            for field in ('Version','ApiVersion','MinAPIVersion','GitCommit'):
                bad=copy.deepcopy(v);bad[side][field]=SENTINEL
                result=p.project('daemon_version',bad,c)
                self.assertIsInstance(result,p.Problem);self.assertNotIn(SENTINEL,repr(result))

    def test_unapproved_repository_names_and_config_keys_are_withheld(self):
        c=contract();v={'Id':p.IMAGES[0],'Os':'linux','Architecture':'amd64',
            'Config':{'Env':['PATH=/usr/bin:/bin'],'WorkingDir':'/'},
            'RootFS':{'Type':'layers','Layers':[]},'RepoDigests':['secret-sentinel@sha256:'+'a'*64]}
        self.assertIsInstance(p.project('image_runner',[v],c),p.Problem)
        v['RepoDigests']=[];v[SENTINEL]=SENTINEL
        result=p.project('image_runner',[v],c)
        self.assertIsInstance(result,p.Problem);self.assertNotIn(SENTINEL,repr(result))
        d=fixture();d['image_configs'][p.IMAGES[0]][SENTINEL]=SENTINEL
        self.assertIsInstance(p.admit_contract(json.dumps(d).encode()),p.Problem)

class AdditionalPolicyMatrixTests(unittest.TestCase):
    def test_exact_argv_manifest_for_all_templates(self):
        c=contract(commands=list(p.COMMAND_IDS));by={s.id:s for s in c.commands};f=fixture();D=f['docker_abs'];G=f['git_abs'];C=f['checkout'];R=f['prep_root'];T=f['token']
        g=(G,'--no-optional-locks','-C',C)
        expected={
          'git_version':(G,'--version'),'docker_version':(D,'--version'),
          'compose_version':(D,'compose','version','--format','json'),'context_show':(D,'context','show'),
          'context_inspect':(D,'context','inspect','default','--format','{{json .}}'),
          'daemon_version':(D,'version','--format','{{json .}}'),'daemon_info':(D,'info','--format','{{json .}}'),
          'create_help':(D,'create','--help'),'compose_up_help':(D,'compose','up','--help'),'compose_run_help':(D,'compose','run','--help'),
          'inventory_names':(D,'ps','-a','--no-trunc','--format','{{.Names}}'),
          'inventory_owner':(D,'ps','-aq','--no-trunc','--filter','label=autodata.owner='+T),
          'inventory_project':(D,'ps','-aq','--no-trunc','--filter','label=com.docker.compose.project=autodata-r3-'+T),
          'git_files':g+('ls-files','--stage','-z'),'git_head':g+('rev-parse','--verify','HEAD'),
          'git_tree':g+('rev-parse','HEAD^{tree}'),'git_status':g+('status','--porcelain=v1','--untracked-files=all'),
          'git_remote':g+('remote',),'git_symbolic':g+('symbolic-ref','-q','HEAD')}
        for key,argv in expected.items():self.assertEqual(by[key].argv,argv)
        for key in ('compose_baseline','compose_effective'):
            expected_argv=(D,'compose','--env-file','/dev/null','-p','autodata-r3-'+T,'-f',C+'/infra/compose/compose.article-lifecycle-test.yaml')
            if key=='compose_effective':expected_argv+=('-f',R+'/effective.json')
            self.assertEqual(by[key].argv,expected_argv+('config','--format','json'))
            self.assertEqual(by[key].cwd,C);self.assertEqual(by[key].deadline_ms,30000)
        for key,image in zip(('image_runner','image_postgres','image_nats','image_minio'),p.IMAGES):self.assertEqual(by[key].argv,(D,'image','inspect',image))

    def test_utf8_multibyte_chunk_boundary_and_collection_bounds(self):
        self.assertEqual(p.parse_bounded_json([b'"\xf0',b'\x9f\x98',b'\x80"'],p.Limits()),'😀')
        self.assertEqual(p.parse_bounded_json([b'"\xf0\x9f\x98\x80"'],replace(p.Limits(),json_string=4)),'😀')
        self.assertEqual(p.parse_bounded_json([b'"\xf0\x9f\x98\x80"'],replace(p.Limits(),json_string=3)),p.Problem('cap'))
        self.assertEqual(p.parse_bounded_json([b'[0,0]'],replace(p.Limits(),json_members=2)),[0,0])
        self.assertEqual(p.parse_bounded_json([b'[0,0,0]'],replace(p.Limits(),json_members=2)),p.Problem('cap'))
        self.assertEqual(p.parse_bounded_json([b'[]'*2],p.Limits()),p.Problem('invalid_json'))

    def test_help_flags_context_tls_and_label_inventory(self):
        c=contract()
        for kind,flag in [('create_help','--pull'),('compose_up_help','--no-build'),('compose_run_help','--no-deps')]:
            self.assertIsInstance(p.project(kind,flag+' '+SENTINEL,c),p.SafeObservation)
            result=p.project(kind,flag+' '+SENTINEL,c);self.assertNotIn(SENTINEL,repr(result))
            self.assertIsInstance(p.project(kind,'missing',c),p.Problem)
        good={'Name':'default','Endpoints':{'docker':{'Host':'unix:///synthetic/docker.sock','SkipTLSVerify':False}}}
        self.assertIsInstance(p.project('context_inspect',good,c),p.SafeObservation)
        good['Endpoints']['docker']['SkipTLSVerify']=True
        self.assertIsInstance(p.project('context_inspect',good,c),p.Problem)
        for kind in ('inventory_owner','inventory_project'):
            self.assertIsInstance(p.project(kind,'',c),p.SafeObservation)
            self.assertEqual(p.project(kind,'a'*64+'\n',c),p.Problem('collision'))
            self.assertIsInstance(p.project(kind,SENTINEL,c),p.Problem)

class SourceManifestBindingTests(unittest.TestCase):
    def test_tracked_inventory_requires_independent_manifest_digest(self):
        from dataclasses import asdict
        identity=p.Identity(1,10,'regular',1000,1000,0o600,2,1,1,'parent')
        parent=p.Identity(1,1,'directory',1000,1000,0o700,0,1,1,'anchor')
        raw='100644 '+'a'*40+' 0\tinput.json\x00'
        f=fixture();f['approved_files']=[dict(id='file_0',path='/synthetic/clone/input.json',purpose='source',identity=asdict(identity),sha256='c'*64,parents=[asdict(parent)])]
        bad=p.admit_contract(json.dumps(f).encode())
        self.assertIsInstance(p.project('git_files',raw,bad),p.Problem)
        import hashlib
        f['manifest_pin']=hashlib.sha256(raw.encode()).hexdigest()
        good=p.admit_contract(json.dumps(f).encode())
        self.assertIsInstance(p.project('git_files',raw,good),p.SafeObservation)
        self.assertIsInstance(p.project('git_files',raw.replace('a'*40,'b'*40),good),p.Problem)

class ForgedFrozenSerializationTests(unittest.TestCase):
    def test_frozen_object_member_cap_precedes_mapping_conversion(self):
        frozen=p.FrozenMap((str(i),0) for i in range(4))
        self.assertEqual(p.serialize_bounded(frozen,replace(p.Limits(),json_members=3)),p.Problem('cap'))
        self.assertIsInstance(p.serialize_bounded(p.FrozenMap((('x',1),('x',2))),p.Limits()),p.Problem)
        self.assertIsInstance(p.serialize_bounded(p.FrozenMap((('x',),)),p.Limits()),p.Problem)
