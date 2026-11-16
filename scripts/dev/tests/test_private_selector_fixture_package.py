"""Authored/mocked only: never starts Docker, SQL, HTTP or a supplier call."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import private_selector_fixture_package as package
import private_selector_adapter_contract as c


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


ROOT=Path(__file__).resolve().parents[3]
bootstrap=load('owned_bootstrap',ROOT/'scripts/dev/fixtures/private_selector_bootstrap.py')
client=load('owned_client',ROOT/'scripts/dev/fixtures/private_selector_client.py')


def names():
    tree=ast.parse((ROOT/'scripts/dev/private_selector_fixture_package.py').read_text())
    f=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='environment')
    mapping=next(x.value for x in f.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='overrides' for t in x.targets))
    return sorted(ast.literal_eval(k) for k in mapping.keys)


class Tests(unittest.TestCase):
    def setUp(self):
        self.run='4'*32;self.env=package.environment(names(),self.run)
        self.fixture={'database':'lifecycle_test_'+self.run,'bucket':'autodata-selector-fixture-'+self.run,
            **{x:'00000000-0000-4000-8000-000000000001' for x in ('configuration','foreign_configuration','owner','organization','entitlement')}}

    def test_payload_import_is_inert_without_optional_dependencies_or_dispatch(self):
        with patch('subprocess.Popen',side_effect=AssertionError('child forbidden')),patch('socket.socket',side_effect=AssertionError('socket forbidden')):
            load('import_bootstrap',ROOT/'scripts/dev/fixtures/private_selector_bootstrap.py')
            load('import_client',ROOT/'scripts/dev/fixtures/private_selector_client.py')

    def test_production_database_environment_and_bucket_refuse_before_adapters(self):
        for key,value in [('AUTODATA_POSTGRES_DB','autodata'),('AUTODATA_DB_ADDRESS','127.0.0.1:5432'),('AUTODATA_POSTGRES_USER','autodata'),('AUTODATA_POSTGRES_PASSWORD','other')]:
            env={**self.env,key:value};connect=Mock()
            with self.assertRaises(ValueError):bootstrap.bootstrap(env,connect=connect,identifier=Mock(),migrate=Mock(),seed=Mock(),hold=Mock())
            connect.assert_not_called()
            with self.assertRaises(ValueError):client.ownership(self.fixture,env)
        with self.assertRaises(ValueError):client.ownership({**self.fixture,'bucket':'protected'},self.env)

    def test_client_rejects_other_provider_or_commerce_before_optional_imports(self):
        for key,value in [('BANKONE_BASE_URL','https://supplier.example'),('BANKTWO_BASE_URL','http://remote:18312'),('AUTODATA_COMMERCE_MODE','stripe_test')]:
            with patch.dict(os.environ,{**self.env,key:value},clear=True):
                with self.assertRaises(ValueError):client.main(self.fixture)

    def test_bootstrap_exact_owned_name_seed_then_hold_then_cleanup(self):
        events=[]
        class Connection:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def execute(self,value,*args):
                events.append(value);return self
            def fetchone(self):return (0,)
        def connect(database,**kw):
            self.assertEqual(database,'lifecycle_fixture');self.assertTrue(kw['autocommit']);return Connection()
        expected={k:self.fixture[k] for k in ('configuration','foreign_configuration','owner','organization','entitlement')}
        bootstrap.bootstrap(self.env,connect=connect,identifier=lambda p,n:(p,n),
            migrate=lambda n:events.append(('migrate',n)),seed=lambda n:expected,
            hold=lambda data:events.append(('hold',data['database'])))
        self.assertEqual(events,[('CREATE DATABASE {}',self.fixture['database']),('migrate',self.fixture['database']),('hold',self.fixture['database']),('DROP DATABASE IF EXISTS {} WITH (FORCE)',self.fixture['database']),'SELECT count(*) FROM pg_database WHERE datname=%s'])

    def test_bootstrap_failed_migration_cleans_only_created_owned_database(self):
        db=Mock();db.__enter__=Mock(return_value=db);db.__exit__=Mock(return_value=False)
        db.execute.return_value.fetchone.return_value=(0,)
        migrate=Mock(side_effect=RuntimeError('authored failure'))
        with self.assertRaises(RuntimeError):bootstrap.bootstrap(self.env,connect=Mock(return_value=db),identifier=lambda p,n:(p,n),migrate=migrate,seed=Mock(),hold=Mock())
        self.assertEqual(db.execute.call_args_list[-2].args[0],('DROP DATABASE IF EXISTS {} WITH (FORCE)',self.fixture['database']))

    def test_create_failure_never_drops_preexisting_database(self):
        db=Mock();db.__enter__=Mock(return_value=db);db.__exit__=Mock(return_value=False);db.execute.side_effect=RuntimeError('already exists')
        with self.assertRaises(RuntimeError):bootstrap.bootstrap(self.env,connect=Mock(return_value=db),identifier=lambda p,n:(p,n),migrate=Mock(),seed=Mock(),hold=Mock())
        self.assertEqual(db.execute.call_count,1)

    def test_failed_behavior_still_emits_positive_database_and_bucket_cleanup(self):
        db=Mock();db.__enter__=Mock(return_value=db);db.__exit__=Mock(return_value=False)
        db.execute.return_value.fetchone.return_value=(0,)
        emitted=Mock();bucket=Mock(return_value=True)
        expected={k:self.fixture[k] for k in ('configuration','foreign_configuration','owner','organization','entitlement')}
        with self.assertRaisesRegex(RuntimeError,'behavior'):
            bootstrap.bootstrap(self.env,connect=Mock(return_value=db),identifier=lambda p,n:(p,n),
                migrate=Mock(),seed=lambda _:expected,hold=Mock(side_effect=RuntimeError('behavior')),
                cleanup_bucket=bucket,emit_cleanup=emitted)
        bucket.assert_called_once_with()
        emitted.assert_called_once_with({'database_removed':True,'bucket_removed':True})

    def test_failed_database_absence_still_attempts_bucket_without_success_receipt(self):
        db=Mock();db.__enter__=Mock(return_value=db);db.__exit__=Mock(return_value=False)
        db.execute.return_value.fetchone.return_value=(1,)
        emitted=Mock();bucket=Mock(return_value=True)
        with self.assertRaisesRegex(ValueError,'cleanup_unknown'):
            bootstrap.bootstrap(self.env,connect=Mock(return_value=db),identifier=lambda p,n:(p,n),
                migrate=Mock(side_effect=RuntimeError('migration')),seed=Mock(),hold=Mock(),
                cleanup_bucket=bucket,emit_cleanup=emitted)
        bucket.assert_called_once_with()
        emitted.assert_called_once_with({'database_removed':False,'bucket_removed':True})

    def test_create_collision_never_cleans_preexisting_bucket(self):
        db=Mock();db.__enter__=Mock(return_value=db);db.__exit__=Mock(return_value=False)
        db.execute.side_effect=RuntimeError('collision');bucket=Mock()
        with self.assertRaises(RuntimeError):
            bootstrap.bootstrap(self.env,connect=Mock(return_value=db),identifier=Mock(),
                migrate=Mock(),seed=Mock(),hold=Mock(),cleanup_bucket=bucket)
        bucket.assert_not_called()

    def test_authored_banks_scopes_and_partial_failure_are_deterministic(self):
        for bank in ('bankone','banktwo'):
            for scope,query in [('years',''),('makes','?year=2024'),('models','?year=2024&make=Authored')]:
                status,value=client.connector_response(bank,'/v1/catalog/'+scope+query)
                self.assertEqual((status,value['provider'],value['complete']),(200,bank,True))
                self.assertEqual(len(value['items']),1)
        self.assertEqual(client.connector_response('banktwo','/v1/catalog/makes?year=2023',partial=True)[0],503)
        self.assertEqual(client.connector_response('bankone','/v1/catalog/makes?year=2023',partial=True)[0],200)

    def test_authored_server_forbids_articles_payments_and_cursor_sweeps(self):
        for path in ['/v1/catalog/articles','/v1/catalog/configurations','/internal/commerce/checkouts','/v1/catalog/years?cursor=next','/v1/catalog/makes?secret=anything']:
            with self.assertRaises(ValueError):client.connector_response('bankone',path)

    def test_host_proof_is_not_accepted_from_behavior_client(self):
        proof={'role':'worker','image':c.IMAGE,'source':c.SOURCE,'owned_synthetic':True,'policy':client.POLICY}
        behavior=dict.fromkeys(client.BEHAVIOR_CHECKS,True)
        result=client.compose_checks(proof,behavior)
        import private_selector_image_fixture as fixture
        self.assertEqual(set(result),fixture.CHECKS)
        for changed in [{**proof,'image':'wrong'},{**proof,'policy':{}},{**proof,'owned_synthetic':False}]:
            with self.assertRaises(ValueError):client.compose_checks(changed,behavior)
        with self.assertRaises(ValueError):client.compose_checks(proof,{**behavior,'actual_image':True})
        with self.assertRaises(ValueError):client.compose_checks(proof,{**behavior,'svg_png':False})

    def test_wrapper_reverifies_host_contract_after_client_before_composition(self):
        events=[];proof={'role':'worker','image':c.IMAGE,'source':c.SOURCE,'owned_synthetic':True,'policy':client.POLICY}
        class Base:
            def fixture_identity(self,_):events.append('identity');return proof
            def exercise_fixture(self,*_):events.append('behavior');return dict.fromkeys(client.BEHAVIOR_CHECKS,True)
        self.assertEqual(len(client.wrap_transport(Base)().exercise_fixture('owned',{})),21)
        self.assertEqual(events,['identity','behavior','identity'])
        class Drift(Base):
            calls=0
            def fixture_identity(self,_):
                self.calls+=1;return proof if self.calls==1 else {**proof,'image':'drift'}
        with self.assertRaises(ValueError):client.wrap_transport(Drift)().exercise_fixture('owned',{})

    def test_review_template_cannot_pass_admission_and_transport_bytes_unchanged(self):
        files=package.review_files(names(),self.run)
        value=json.loads(files['fixture-manifest.NOT-ADMITTED.json'])
        self.assertFalse(value['execution_approved']);self.assertIsNone(value['artifacts']['source_inventory'])
        with self.assertRaises(c.Refused):c.validate(value,'fixture')
        self.assertEqual(package.sha(files['private_selector_local_transport.py']),package.TRANSPORT_SHA)
        for role in ('bootstrap','worker'):
            payload=json.loads(files['fixture-'+role+'.create.json'])
            self.assertIsNone(payload['HostConfig']['NetworkMode']);self.assertTrue(payload['HostConfig']['ReadonlyRootfs'])
            self.assertNotIn('PortBindings',payload['HostConfig'])
            self.assertEqual(payload['HostConfig']['RestartPolicy'],{'Name':'no'})
            self.assertEqual({x.split('=',1)[0] for x in payload['Env']},set(names()) | (set(package.BOOTSTRAP_DEFAULTS) if role=='bootstrap' else set()))

    def test_bootstrap_explicit_defaults_do_not_change_worker_names(self):
        files=package.review_files(names(),self.run)
        bootstrap_env=dict(x.split('=',1) for x in json.loads(files['fixture-bootstrap.create.json'])['Env'])
        worker_env=dict(x.split('=',1) for x in json.loads(files['fixture-worker.create.json'])['Env'])
        self.assertEqual(set(bootstrap_env)-set(worker_env),{'CGO_ENABLED','GOMODCACHE','GOTOOLCHAIN'})
        self.assertEqual(set(worker_env),set(names()))

    def test_builder_rejects_physical_destination_and_existing_output(self):
        with self.assertRaises(c.Refused):package.build('/home/corp/physical-package',names(),self.run)
        with tempfile.TemporaryDirectory() as temporary:
            parent=Path(temporary);output=parent/'output'
            with patch.object(package,'EVIDENCE',parent),patch.object(package,'OFFLOADED_DEVICE',parent.stat().st_dev):
                package.build(output,names(),self.run)
                before=(output/'package-seal.json').read_bytes()
                with self.assertRaises(FileExistsError):package.build(output,names(),self.run)
                self.assertEqual((output/'package-seal.json').read_bytes(),before)
                for name,entry in json.loads(before)['files'].items():self.assertEqual(package.sha((output/name).read_bytes()),entry['sha256'])

    def test_source_pinned_owned_process_stalls_killed_and_reaped_without_network(self):
        path=ROOT/'workers/ingestion-python/src/autodata_ingestion/selector_job.py'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
            '6132ce57d1c9cedcf087d70b43a80cd3523ec4f34cb444bf031889658dab5700')
        job=load('exact_source_selector_job',path)
        with tempfile.TemporaryDirectory() as temporary:
            for kind in ('dns','headers','body'):
                pidfile=Path(temporary)/kind
                program='import os,sys,time;open(sys.argv[1],"w").write(str(os.getpid()));'+('sys.stdout.write("{");sys.stdout.flush();' if kind=='body' else '')+'time.sleep(30)'
                start=time.monotonic()
                with self.assertRaises(job.SelectorJobStopped) as error:job.run_owned({},time.monotonic()+.25,command=['/usr/bin/python3','-I','-c',program,str(pidfile)])
                self.assertEqual(error.exception.reason,'elapsed');self.assertLess(time.monotonic()-start,2.5)
                self.assertTrue(pidfile.exists())
                with self.assertRaises(ProcessLookupError):os.kill(int(pidfile.read_text()),0)

    def test_source_pinned_controls_reservation_cooldown_and_byte_row_caps(self):
        job=load('exact_source_selector_control',ROOT/'workers/ingestion-python/src/autodata_ingestion/selector_job.py')
        clock=[0.0];control=job.SelectorJobControl(20,clock=lambda:clock[0],sleep=lambda t:None,dispatch_interval=0)
        for _ in range(12):control.before_request()
        with self.assertRaises(job.SelectorJobStopped) as error:control.before_request()
        self.assertEqual(error.exception.reason,'request_limit')
        control=job.SelectorJobControl(20,clock=lambda:clock[0]);clock[0]=21
        with self.assertRaises(job.SelectorJobStopped) as error:control.before_request()
        self.assertEqual(error.exception.reason,'elapsed');self.assertEqual(control.requests,0)
        clock[0]=0;gate=job.SelectorAdmission(clock=lambda:clock[0]);request={'scope':'makes','year':2024,'region':'US'}
        token=gate.acquire(request);self.assertIsNotNone(token);self.assertIsNone(gate.acquire({'scope':'years'}));gate.release(token,complete=False)
        clock[0]=7;self.assertIsNone(gate.acquire(request));clock[0]=31;self.assertIsNotNone(gate.acquire(request))
        for method,size,reason in [('consume_bytes',4*1024*1024+1,'byte_limit'),('consume_rows',5001,'row_limit')]:
            control=job.SelectorJobControl(20,clock=lambda:0)
            with self.assertRaises(job.SelectorJobStopped) as error:getattr(control,method)(size)
            self.assertEqual(error.exception.reason,reason)


if __name__=='__main__':unittest.main()
