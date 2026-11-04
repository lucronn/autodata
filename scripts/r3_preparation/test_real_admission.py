"""Pure actual admission tests; identities and documents below are fictional."""
import copy
import hashlib
import json
import unittest
from dataclasses import replace
from test_policy import load

p = load('policy')
a = load('real_admission')


def encode(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':')).encode()


def fixture():
    root = '/owned/preparation'
    names = ('operator', 'reviewer', 'cancellation', 'host', 'daemon', 'installation', 'watchdog')
    identities = {n: {'person': 'person-' + n, 'session': 'session-' + n,
                      'artifact': hashlib.sha256(n.encode()).hexdigest()} for n in names}
    d = dict(schema_version=1, evidence_kind='preparation_observation',
             checkpoint=a.CHECKPOINT, adapter_sha='a' * 40,
             token='123456781234423492341234567890ab', issued_ns=100, expires_ns=1000000100,
             identities=identities, prep_root=root, checkout='/owned/clone',
             local_socket='unix:///var/run/docker.sock',
             tools={'python': '/tools/python3', 'git': '/tools/git', 'docker': '/tools/docker',
                    'compose': '/tools/docker-compose'},
             env=dict(PATH='/tools:/usr/bin', HOME=root+'/home', USER='owner', LOGNAME='owner',
                      LANG='C.UTF-8', LC_ALL='C.UTF-8', TZ='UTC',
                      AUTODATA_R3_TEST_IMAGE=p.IMAGES[0], AUTODATA_R3_CANDIDATE_SHA=p.CANDIDATE,
                      AUTODATA_LIFECYCLE_ARTIFACT_DIR=root+'/artifacts'),
             windows={n: 'b'*64 for n in a.WINDOWS},
             resources=dict(memory_bytes=1024**3, processes=32, open_fds=128,
                            no_swap='c'*64, no_core='d'*64, containment='e'*64,
                            watchdog='f'*64, embedding='1'*64),
             git_provenance=dict(config_literal=p.CONFIG, installation_manifest='2'*64,
                                 absent_paths=['/etc/gitconfig',root+'/home/.gitconfig',
                                 root+'/home/.config/git/config','/owned/clone/.git/config.worktree']),
             anchors=[], files=[], prerequisites={n: [] for n in a.WINDOWS},
             image_configs={im: {'Env': ['PATH=/usr/bin:/bin'], 'WorkingDir': '/', 'Labels': {}}
                            for im in p.IMAGES},
             image_rootfs={im: {'Type':'layers', 'Layers':[]} for im in p.IMAGES},
             image_repo_digests={im: [] for im in p.IMAGES},
             baseline={'services': {'postgres': {'image':'pg'},'nats':{'image':'nats'},
                 'minio':{'image':'minio','volumes':['old:/data']},
                 'go-test-runner':{'build':'.'},'test-runner':{'image':'test'}}},
             required_flags={'create_help':['--pull'], 'compose_up_help':['--no-build'],
                             'compose_run_help':['--no-deps']},
             tracked_manifest='3'*64, planned_names=['autodata-r3-test'],
             output_owners={n: 'operator' if n in p.OUTPUT_NAMES[:2] else
                            'reviewer' if n == 'independent-review.md' else 'collector'
                            for n in p.OUTPUT_NAMES},
             daemon_identity_sha256='4'*64, created_container_evidence=None)
    directory=dict(dev=1,inode=1,uid=1000,gid=1000,mode=0o40700,size=0,mtime_ns=1,ctime_ns=1,nlink=1,mount_id=1)
    d['anchors']=[dict(reference='filesystem',path='/',identity=directory),
                  dict(reference='root',path=root,identity=directory)]
    d['anchors'] += [dict(reference=n,path=root+'/'+n,identity=directory.copy()) for n in ('home','artifacts','minio')]
    paths=[(v,'regular') for v in d['tools'].values()]
    paths += [(v,'absence') for v in d['git_provenance']['absent_paths']]
    paths += [('/var/run/docker.sock','socket'),('/owned/clone/.git/config','regular'),
              (root+'/owner-contract.json','regular'),(root+'/dispatch.json','regular')]
    for i,(path,kind) in enumerate(paths):
        ident=dict(directory,mode=0o100600 if kind=='regular' else 0o140600,inode=i+2)
        literal=p.CONFIG if path.endswith('/.git/config') else None
        raw=(literal or ('owned contract' if path.endswith('/owner-contract.json') else 'owned dispatch' if path.endswith('/dispatch.json') else '')).encode();ident['size']=len(raw)
        d['files'].append(dict(id='file_'+str(i),anchor='filesystem',components=path[1:].split('/'),
            kind=kind,identity=None if kind=='absence' else ident,
            parents=[directory]*len(path[1:].split('/')),sha256=hashlib.sha256(raw).hexdigest() if kind=='regular' else None,
            literal=literal))
    sources=dict(system=['/etc/gitconfig'],global_paths=[root+'/home/.gitconfig'],xdg=[root+'/home/.config/git/config'],local=['/owned/clone/.git/config'],worktree=['/owned/clone/.git/config.worktree'])
    d['git_provenance']['installation_sources']=sources
    d['git_provenance']['installation_manifest']=hashlib.sha256(encode(sources)).hexdigest()
    d['prerequisites']={n:[f['id'] for f in d['files']] for n in a.WINDOWS}
    d['daemon_identity_sha256']=hashlib.sha256(b'private').hexdigest()
    d['commands'] = [dict(id=c.id, argv=list(c.argv), cwd=c.cwd, env=dict(c.env),
                          kind=c.kind, prerequisites=list(c.prerequisites))
                     for c in a.command_graph(d)]
    return d


def bundle(document):
    d=json.loads(document)
    return a.ApprovalBundle(hashlib.sha256(document).hexdigest(), a.CHECKPOINT,
        d['adapter_sha'], d['token'], 200, d['expires_ns'],
        tuple((n, v['person'], v['session'], v['artifact']) for n,v in sorted(d['identities'].items())),
        hashlib.sha256(encode(d['commands'])).hexdigest(), '5'*64)


def contract():
    doc=encode(fixture()); c=a.admit_actual(doc,bundle(doc))
    if isinstance(c,p.Problem): raise AssertionError(c)
    return c


class AdmissionTests(unittest.TestCase):
    def test_exact_binding_and_actual_marker(self):
        c=contract(); self.assertIs(type(c),a.ActualContract)
        self.assertEqual(c.evidence_kind,'preparation_observation')
        self.assertEqual(len(c.commands),26)
        self.assertNotEqual(a.CHECKPOINT,p.CHECKPOINT)

    def test_forged_and_changed_bindings_are_pure_rejections(self):
        doc=encode(fixture()); b=bundle(doc)
        for value in (None, replace(b,document_sha256='0'*64), replace(b,checkpoint=p.CHECKPOINT),
                      replace(b,now_ns=True),replace(b,now_ns=b.expires_ns),replace(b,channel_artifact=''),
                      replace(b,token='0'*32),replace(b,command_manifest_sha256='0'*64)):
            self.assertIsInstance(a.admit_actual(doc,value),p.Problem)
        self.assertIsInstance(a.admit_actual(doc+b' ',b),p.Problem)

    def test_hostile_contracts_and_manifest_mutation(self):
        changes=[('checkpoint',p.CHECKPOINT),('evidence_kind','synthetic'),('extra','PRIVATE_SENTINEL'),
                 ('prep_root','relative'),('prep_root','/a/../b'),('prep_root','/x\nsecret'),
                 ('adapter_sha',True),('issued_ns',True),('token','0'*32),('expires_ns',101)]
        for key,value in changes:
            d=fixture(); d[key]=value; doc=encode(d)
            with self.subTest(key=key): self.assertIsInstance(a.admit_actual(doc,bundle(doc)),p.Problem)
        for mutation in ('same_owner','argv','order','env','cwd','window','synthetic','git_config'):
            d=fixture()
            if mutation=='same_owner': d['identities']['reviewer']=d['identities']['operator'].copy()
            elif mutation=='argv': d['commands'][0]['argv'].append('-c')
            elif mutation=='order': d['commands'].reverse()
            elif mutation=='env': d['commands'][0]['env']['SECRET']='PRIVATE_SENTINEL'
            elif mutation=='cwd': d['commands'][0]['cwd']='/wrong'
            elif mutation=='window': d['windows'].pop('git')
            elif mutation=='synthetic': d['identities']['operator']['person']='synthetic-approved'
            else: d['git_provenance']['config_literal']+='[include]\npath=private\n'
            doc=encode(d); result=a.admit_actual(doc,bundle(doc))
            with self.subTest(mutation=mutation): self.assertIsInstance(result,p.Problem)
            self.assertNotIn('PRIVATE_SENTINEL',repr(result))

    def test_prerequisite_windows_cannot_substitute_unrelated_absence(self):
        d=fixture();d['prerequisites']={n:['file_4'] for n in a.WINDOWS};doc=encode(d)
        self.assertIsInstance(a.admit_actual(doc,bundle(doc)),p.Problem)

    def test_git_implicit_config_paths_cannot_be_replaced_without_manifest(self):
        d=fixture();d['git_provenance']['absent_paths'][0]='/unrelated/absence'
        d['files'][4]['components']=['unrelated','absence'];doc=encode(d)
        self.assertIsInstance(a.admit_actual(doc,bundle(doc)),p.Problem)

    def test_literal_config_and_models_do_not_coerce_bool_and_int(self):
        d=fixture();im=p.IMAGES[0];d['image_configs'][im]['Labels']={'flag':1}
        doc=encode(d);c=a.admit_actual(doc,bundle(doc));self.assertIsInstance(c,a.ActualContract)
        image=dict(Id=im,Os='linux',Architecture='amd64',Config=copy.deepcopy(d['image_configs'][im]),
                   RootFS=d['image_rootfs'][im],RepoDigests=[])
        image['Config']['Labels']['flag']=True
        self.assertIsInstance(a.project('image_runner',[image],c),p.Problem)
        d=fixture();d['baseline']['services']['postgres']['scale']=1;doc=encode(d)
        c=a.admit_actual(doc,bundle(doc));observed=copy.deepcopy(d['baseline'])
        observed['services']['postgres']['scale']=True
        self.assertIsInstance(a.project('compose_baseline',observed,c),p.Problem)

    def test_root_requires_private_directories(self):
        for mode in (0o40755,0o40750):
            d=fixture();next(x for x in d['anchors'] if x['reference']=='root')['identity']['mode']=mode
            doc=encode(d);self.assertIsInstance(a.admit_actual(doc,bundle(doc)),p.Problem)

    def test_json_ledger_nested_deadline_cumulative_time_and_cancel(self):
        from unittest.mock import patch
        import threading
        now=[0];event=threading.Event()
        with patch.object(a.time,'monotonic_ns',side_effect=lambda:now[0]):
            budget=a.JsonBudget(200*10**9,event)
            for i in range(12):
                with budget.operation():now[0]+=5*10**9-1;budget.check_json()
            self.assertGreater(budget.spent_ns,59*10**9)
            with self.assertRaises(a.BudgetFault):
                with budget.operation():now[0]+=100;budget.check_json()
            now[0]=0;budget=a.JsonBudget(200*10**9,event)
            with self.assertRaises(a.BudgetFault):
                with budget.operation():
                    now[0]=4*10**9
                    with budget.operation():now[0]=5*10**9;budget.check_json()
            self.assertIsNotNone(budget.fault)
            event.set()
            with self.assertRaises(a.BudgetFault):
                with budget.operation():pass

    def test_shared_json_ledger_is_used_by_readmission_and_projection(self):
        import threading
        import time
        d=fixture();raw=encode(d);budget=a.JsonBudget(time.monotonic_ns()+10**10,threading.Event())
        c=a._admit_actual(raw,bundle(raw),budget)
        self.assertIsInstance(c,a.ActualContract);first=budget.spent_ns
        a.project('python_version','Python 3.12.1',c,budget)
        self.assertGreater(budget.spent_ns,first)
        budget.cancel.set()
        self.assertRaises(a.BudgetFault,a.values,c,budget)

    def test_duplicate_nested_keys_invalid_utf8_and_nonfinite(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":{"a":1,"a":2}}',b'\xff',b'{"x":NaN}',b'['*65+b']'*65):
            self.assertIsInstance(a.admit_actual(raw,bundle(encode(fixture()))),p.Problem)

    def test_graph_exact_dependencies_kind_cwd_and_images(self):
        d=fixture(); graph=a.command_graph(d)
        self.assertEqual(tuple(c.id for c in graph),p.COMMAND_IDS)
        for c in graph:
            self.assertEqual(c.cwd,d['checkout'] if c.id.startswith('compose_') and c.id in
                             ('compose_baseline','compose_effective') else d['prep_root'])
            self.assertEqual(c.kind,'source' if c.id in p.COMMAND_IDS[18:] else 'ordinary')
        self.assertIn('git',graph[1].prerequisites)
        self.assertIn('context_show',graph[5].prerequisites)
        for c in graph[11:15]:
            self.assertIn('daemon_info',c.prerequisites); self.assertIn(c.argv[-1],p.IMAGES)
        self.assertEqual(graph[23].expected_returncode,1)
        self.assertTrue(set(p.COMMAND_IDS[18:24]) <= set(graph[24].prerequisites))

    def test_image_full_literal_schema_and_unknown_top_level(self):
        c=contract(); d=fixture(); im=p.IMAGES[0]
        image=dict(Id=im,Os='linux',Architecture='amd64',Config=d['image_configs'][im],
                   RootFS=d['image_rootfs'][im],RepoDigests=[],Extra='PRIVATE_SENTINEL')
        result=a.project('image_runner',[image],c)
        self.assertNotIsInstance(result,p.Problem); self.assertNotIn('PRIVATE_SENTINEL',repr(result))
        self.assertIn('Config',result)
        for change in ({'Env':['PATH=/bin','PYTHON_VERSION=']},{'Private':'PRIVATE_SENTINEL'}):
            bad=copy.deepcopy(image);bad['Config'].update(change)
            self.assertIsInstance(a.project('image_runner',[bad],c),p.Problem)
        image['Architecture']='x86_64'
        self.assertIsInstance(a.project('image_runner',[image],c),p.Problem)

    def test_versions_daemon_and_models_fail_closed(self):
        c=contract()
        self.assertIsInstance(a.project('python_version','Python PRIVATE_SENTINEL',c),p.Problem)
        self.assertEqual(a.project('python_version','Python 3.12.1\n',c),{'version':'Python 3.12.1'})
        info=dict(OSType='linux',Architecture='x86_64',ID='private',HTTPProxy='',HTTPSProxy='',NoProxy='')
        safe=a.project('daemon_info',info,c);self.assertEqual(safe['architecture'],'amd64')
        info['HTTPProxy']='PRIVATE_SENTINEL';self.assertIsInstance(a.project('daemon_info',info,c),p.Problem)
        self.assertIsInstance(a.project('compose_baseline',{'private':'PRIVATE_SENTINEL'},c),p.Problem)
        self.assertEqual(a.effective_model(c)['services']['minio']['volumes'],['/owned/preparation/minio:/data'])
