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
