"""Accepted-cache and fresh database tests, no external registry or providers."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
import uuid
from unittest.mock import patch
from test_host_provision import load

HERE = Path(__file__).parent

class PreparationTests(unittest.TestCase):
    def test_immutable_image_binding_rejects_unapproved_digest(self):
        p = load('host_prepare_release')
        manifest = {'images':{'api':{'reference':'registry/a@sha256:'+'a'*64,'image_id':'sha256:'+'b'*64}}}
        accepted = [{'role':'api',**manifest['images']['api']}]
        self.assertEqual(p.accepted_images(manifest,accepted),accepted)
        bad = copy.deepcopy(accepted); bad[0]['reference'] += '0'
        with self.assertRaises(ValueError): p.accepted_images(manifest,bad)

    def test_password_protocol_escapes_without_argv_or_sql_injection(self):
        p = load('host_prepare_release')
        secret = b"pass'\\word:$;"
        encoded = p.password_sql('autodata_api',secret)
        self.assertNotIn(secret,encoded)
        self.assertIn(b"decode(",encoded)
        for value in (b'',b'a\nb',b'a\x00b'):
            with self.assertRaises(ValueError): p.password_sql('autodata_api',value)
        with self.assertRaises(ValueError): p.password_sql('injected;drop',b'password')

    def test_unknown_ledger_prefix_and_foreign_journal_are_rejected(self):
        p = load('host_prepare_release')
        manifest = {'source_sha':'a'*40,'migrations':{'files':[{'name':'001_initial.sql'},{'name':'002_next.sql'}]}}
        journal = {'source_sha':'a'*40,'operation':'initialize-fresh-staging-database','status':'incomplete','stages':['postgres-created']}
        self.assertTrue(p.validate_resume(manifest,journal,['001_initial'],['001_initial']))
        for prefix in (['002_next'],['001_initial','999_foreign']):
            with self.assertRaises(ValueError): p.validate_resume(manifest,journal,prefix,prefix)
        journal['source_sha'] = 'b'*40
        with self.assertRaises(ValueError): p.validate_resume(manifest,journal,[],[])

if __name__ == '__main__': unittest.main()

class RealFreshDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.container = 'autodata-host-prepare-test-'+uuid.uuid4().hex
        cls.image = 'pgvector/pgvector:pg17'
        probe = subprocess.run(['/usr/bin/docker','image','inspect',cls.image],capture_output=True,timeout=5)
        if probe.returncode:
            if os.environ.get('AUTODATA_REQUIRE_PG17') == '1': raise AssertionError('cached real PG17 required')
            raise unittest.SkipTest('cached real PG17 unavailable; schema UNVERIFIED')
        result = subprocess.run(['/usr/bin/docker','run','--pull=never','--rm','-d','--network=none','--name',cls.container,
            '-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_USER=autodata_admin','-e','POSTGRES_DB=autodata',cls.image],capture_output=True,timeout=30)
        if result.returncode: raise AssertionError('disposable PG17 startup failed')
        cls.addClassCleanup(lambda:subprocess.run(['/usr/bin/docker','rm','-f',cls.container],capture_output=True,timeout=10))
        for _ in range(100):
            if cls.sql('SELECT 1;',check=False).returncode == 0: break
            time.sleep(.1)
        else: raise AssertionError('PG17 startup timeout')
        root = HERE.parents[2]
        for source,target in ((root/'db/migrations','/tmp/migrations'),(root/'scripts/dev/migrate_sql.sh','/tmp/migrate_sql.sh')):
            subprocess.run(['/usr/bin/docker','cp',str(source),cls.container+':'+target],check=True,capture_output=True,timeout=10)

    @classmethod
    def sql(cls,sql,role='autodata_admin',check=True):
        environment = ['/usr/bin/env','-i','PGOPTIONS=-c default_transaction_read_only=on -c search_path=pg_catalog'] if role == 'autodata_metrics' else []
        result = subprocess.run(['/usr/bin/docker','exec','-i',cls.container,*environment,'/usr/lib/postgresql/17/bin/psql','-X','-A','-t','-q','-v','ON_ERROR_STOP=1',
            '-h','/var/run/postgresql','-U',role,'-d','autodata','--file=-'],input=sql.encode() if isinstance(sql,str) else sql,capture_output=True,timeout=15)
        if check and result.returncode: raise AssertionError(result.stderr.decode())
        return result

    def test_real_migrations_roles_ledger_grants_and_malformed_refusal(self):
        p = load('host_prepare_release')
        self.sql((HERE/'host-bootstrap-roles.sql').read_bytes())
        for name in p.ROLES: self.sql(p.password_sql('autodata_'+name,b"synthetic'\\password"))
        result = subprocess.run(['/usr/bin/docker','exec','--user','1000:1000',self.container,'/usr/bin/env','-i',
            'PATH=/usr/lib/postgresql/17/bin:/usr/bin:/bin','PGHOST=/var/run/postgresql','PGUSER=autodata_migrator','PGDATABASE=autodata',
            '/bin/sh','/tmp/migrate_sql.sh','--migrations-dir','/tmp/migrations'],capture_output=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.sql(p.application_grants()+(HERE/'runtime-grants.sql').read_bytes())
        expected = [path.stem for path in sorted((HERE.parents[2]/'db/migrations').glob('*.sql'))]
        actual = self.sql('SELECT version FROM public.schema_migrations ORDER BY version;','autodata_metrics').stdout.decode().splitlines()
        self.assertEqual(actual,expected)
        self.assertEqual(len(actual),40)
        rights = self.sql("SELECT has_table_privilege('autodata_api','public.schema_migrations','INSERT'),has_table_privilege('autodata_api','public.workshop_orders','INSERT'),has_table_privilege('autodata_outbox','public.publication_events','DELETE'),has_column_privilege('autodata_outbox','public.publication_events','delivery_status','UPDATE'),has_database_privilege('autodata_metrics','autodata','TEMP');").stdout.strip()
        self.assertEqual(rights,b'f|t|f|t|f')
        unsafe = self.sql("SELECT count(*) FROM pg_roles r WHERE rolname IN ('autodata_migrator','autodata_api','autodata_http','autodata_article','autodata_reconciler','autodata_metrics','autodata_outbox') AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit OR EXISTS(SELECT FROM pg_auth_members WHERE member=r.oid));").stdout.strip()
        self.assertEqual(unsafe,b'0')
        rt = load_runtime_for_prepare()
        manifest = {'migrations':{'files':[{'name':name+'.sql'} for name in expected]}}
        # Run the exact existing locked socket collector SQL as the narrow role.
        observed = self.sql(rt._postgres_schema_script(manifest),'autodata_metrics')
        wire = [line for line in observed.stdout.splitlines() if line.startswith(b'{')]
        self.assertEqual(len(wire),2)
        rt.validate_postgres_catalog(rt.strict_json(wire[0])); rt.validate_schema_ledger(manifest,rt.strict_json(wire[1]))
        self.sql("INSERT INTO schema_migrations(version) VALUES ('999_foreign');")
        rejected = self.sql(rt._postgres_schema_script(manifest),'autodata_metrics',check=False)
        self.assertNotEqual(len(rejected.stdout.splitlines()),2)
        # Fresh initialization failure never calls an application command and
        # leaves the database available. The runner itself refuses foreign state.
        rerun = subprocess.run(['/usr/bin/docker','exec','--user','1000:1000',self.container,'/usr/bin/env','-i',
            'PATH=/usr/lib/postgresql/17/bin:/usr/bin:/bin','PGHOST=/var/run/postgresql','PGUSER=autodata_migrator','PGDATABASE=autodata',
            '/bin/sh','/tmp/migrate_sql.sh','--migrations-dir','/tmp/migrations'],capture_output=True,timeout=30)
        self.assertNotEqual(rerun.returncode,0)
        self.assertEqual(self.sql('SELECT 1;').stdout.strip(),b'1')

def load_runtime_for_prepare():
    spec = importlib.util.spec_from_file_location('prepare_test_runtime',HERE/'runtime-check.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

@unittest.skipUnless(os.geteuid() == 0,"root-owned temporary filesystem test")
class ImageExecutionTests(unittest.TestCase):
    def test_exact_pulls_cleanup_success_and_partial_failure(self):
        import tempfile
        from datetime import datetime,timedelta,timezone
        p = load('host_prepare_release'); rt = load_runtime_for_prepare()
        manifest = {'source_sha':'a'*40,'platform':'linux/amd64','images':{role:{'reference':'registry.example/repo/'+role+'@sha256:'+'b'*64,
            'image_id':'sha256:'+'c'*64} for role in rt.IMAGE_ROLES}}
        class Files:
            def directory(self,*args,**kwargs): pass
            def recheck(self): pass
            def read(self,path,*args,**kwargs): return Path(path).read_bytes()
        for fail in (False,True,'malformed','inspect','cleanup'):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); registry = root/'registry'; registry.mkdir(); auth = b'{' if fail == 'malformed' else b'{"auths":{}}'; (registry/'config.json').write_bytes(auth)
                (registry/'config.json').chmod(0o600); receipts = root/'receipts'; receipts.mkdir(); run = root/'run'; (run/'state').mkdir(parents=True); data = root/'data'; (data/'operations').mkdir(parents=True)
                a = {'schema_version':1,'source_sha':'a'*40,'authorization_id':str(uuid.uuid4()),
                    'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'environment':'staging','operation':'cache-accepted-staging-images','service_config_sha256':'d'*64,
                    'bundle_inventory_sha256':'e'*64,'manifest_raw_sha256':'f'*64,'publisher_acceptance_sha256':'1'*64,
                    'registry_config_sha256':hashlib.sha256(auth).hexdigest(),
                    'images':[{'role':role,**value} for role,value in sorted(manifest['images'].items())]}
                calls = []
                def execute(argv,**kwargs):
                    calls.append(argv)
                    if 'install' in argv: return json.dumps({'status':'passed','source_sha':a['source_sha'],'release_material_committed':True,
                        'commit_state':'receipt_committed','manifest_raw_sha256':a['manifest_raw_sha256'],'service_config_sha256':a['service_config_sha256']}).encode()
                    if 'pull' in argv:
                        if fail is True: raise ValueError('synthetic pull failure')
                        return b''
                    image = next(value for value in manifest['images'].values() if value['reference'] == argv[-1])
                    template = argv[argv.index('--format')+1]
                    value = {'id':image['image_id'],'digests':[image['reference']],'os':'linux','arch':'amd64','variant':''} if '"id"' in template else {
                        'image_id':image['image_id'],'repo_digests':[image['reference']],'os':'linux','architecture':'amd64','variant':''}
                    if fail == 'inspect': value['id' if 'id' in value else 'image_id'] = 'sha256:'+'9'*64
                    return json.dumps(value).encode()
                op = p.Preparation(Files(),a,{},rt,execute)
                def installed(): op.manifest = manifest; return manifest
                with patch.object(p,'REGISTRY',str(registry)), patch.object(p.p,'RECEIPTS',str(receipts)),patch.object(p.p,'RUN',str(run)),patch.object(p.p,'DATA',str(data)),patch.object(p,'make_state'),patch.object(op,'prerequisites'),patch.object(op,'installed',side_effect=installed):
                    if fail == 'cleanup': op.image_cleanup = lambda _: (_ for _ in ()).throw(ValueError('synthetic cleanup failure'))
                    if fail:
                        with self.assertRaises(ValueError): op.images()
                    else:
                        result = op.images(); self.assertEqual(result['status'],'passed')
                        pulls = [argv[-1] for argv in calls if 'pull' in argv]
                        self.assertEqual(pulls,[item['reference'] for item in a['images']])
                    self.assertEqual(registry.exists(),fail == 'cleanup')
                    states = [json.loads(path.read_bytes())['status'] for path in receipts.glob('*.json')]
                    self.assertEqual(states,[] if fail == 'malformed' else ['incomplete'] if fail else ['passed'])
                    self.assertFalse(any('prune' in argv or 'tag' in argv for argv in calls))

class DatabaseQuiescenceTests(unittest.TestCase):
    def test_selected_release_and_any_application_container_block(self):
        p = load('host_prepare_release')
        operation = p.Preparation(None,{},None,None)
        with patch.object(p.os.path,'lexists',return_value=True),patch.object(operation,'run') as run:
            with self.assertRaises(ValueError): operation.no_applications()
            run.assert_not_called()
        for value in (b'abc123456789 api\n',b'abc123456789 postgres\n'):
            with patch.object(p.os.path,'lexists',return_value=False),patch.object(operation,'run',return_value=value):
                with self.assertRaises(ValueError): operation.no_applications()
        with patch.object(p.os.path,'lexists',return_value=False),patch.object(operation,'run',return_value=b'abc123456789 postgres\n'):
            operation.no_applications(resume=True)

class ResumePreMutationTests(unittest.TestCase):
    def test_static_resume_authority_is_checked_before_private_inputs_or_mutation(self):
        import tempfile
        p = load('host_prepare_release')
        manifest = {'source_sha':'a'*40,'migrations':{'files':[{'name':'001_initial.sql'}]}}
        a = {'source_sha':'a'*40,'manifest_raw_sha256':'b'*64,'service_config_sha256':'c'*64,
             'bundle_inventory_sha256':'d'*64,'image_cache_receipt_sha256':'e'*64}
        valid = {**a,'operation':'initialize-fresh-staging-database','status':'incomplete','stages':['postgres-created']}
        cases = [('source_sha','f'*40),('operation','cache-accepted-staging-images'),('status','passed'),
                 ('stages',[]),('manifest_raw_sha256','0'*64),('service_config_sha256','0'*64),
                 ('bundle_inventory_sha256','0'*64),('image_cache_receipt_sha256','0'*64)]
        for key,value in cases:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as directory:
                record = {**valid,key:value}; raw = json.dumps(record).encode(); target = Path(directory)/'prior.json'; target.write_bytes(raw)
                approval = {**a,'resume':{'journal_sha256':hashlib.sha256(raw).hexdigest(),'observed_ledger_prefix':[]}}
                class Files:
                    def read(self,path,*args,**kwargs):
                        if path == str(target): return raw
                        raise AssertionError('unvalidated resume reached later input')
                op = p.Preparation(Files(),approval,None,None)
                with patch.object(p.p,'RECEIPTS',directory),patch.object(op,'prerequisites'),patch.object(op,'installed',return_value=manifest),patch.object(op,'cached'),patch.object(p,'make_state') as make_state,patch.object(op,'compose') as compose,patch.object(p,'sibling') as sibling:
                    with self.assertRaises(ValueError): op.database()
                    make_state.assert_not_called(); compose.assert_not_called(); sibling.assert_not_called()
        self.assertTrue(p.validate_resume_journal(manifest,valid,a,[]))
        with self.assertRaises(ValueError): p.validate_resume_journal(manifest,valid,a,['999_foreign'])
