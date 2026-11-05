"""Fixture safety tests use a fake Docker daemon, never production adapters."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
RUN = '12345678-1234-4234-8234-123456789abc'


def module():
    path = HERE / 'workshop_backup_restore_fixture.py'
    assert path.exists(), 'opt-in owned-resource fixture runner is missing'
    spec = importlib.util.spec_from_file_location('workshop_fixture_test', path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


class Daemon:
    def __init__(self):
        self.objects = {}; self.calls = []; self.counter = 0; self.fail_remove = False
    def __call__(self, args, **kwargs):
        self.calls.append(args)
        kind, action = args[:2]
        if action == 'inspect':
            value = self.objects.get((kind,args[2]))
            if value is None: raise RuntimeError('not found')
            return json.dumps([value]).encode()
        if action == 'create':
            name = args[-1] if kind != 'container' else args[args.index('--name')+1]
            self.counter += 1; identity = str(self.counter).zfill(64)
            label = args[args.index('--label')+1].split('=',1)
            value = {'Id':identity,'Name':name,'Labels':dict([label]),'Config':{'Labels':dict([label])},
                     'State':{'Running':False,'OOMKilled':False,'ExitCode':0}}
            self.objects[kind,name] = value; self.objects[kind,identity] = value
            return (name if kind == 'volume' else identity).encode()
        if action == 'logs': return b'fixture logs'
        if action == 'rm':
            if self.fail_remove: raise RuntimeError('remove failed')
            identity = args[-1]; value = self.objects[kind,identity]
            for key in [key for key,item in self.objects.items() if item is value]: del self.objects[key]
            return b''
        if action == 'ls':
            if '--format' in args:return '\n'.join(sorted({v['Name'] for (k,_),v in self.objects.items() if k==kind})).encode()
            return '\n'.join(sorted({v.get('Id',v['Name']) if kind != 'volume' else v['Name'] for (k,_),v in self.objects.items() if k==kind})).encode()
        raise AssertionError(args)


class FixtureSafetyTests(unittest.TestCase):
    def setUp(self): self.m = module()
    def test_fail_closed_records_maintenance_without_lease_or_ingress(self):
        fixture=self.m.Fixture(None,None,None,RUN,None)
        fixture.fail_closed(123.0)
        self.assertEqual(fixture.events,['fail-closed-maintenance'])

    def test_default_is_inert(self):
        with patch.object(self.m,'execute_fixture',side_effect=AssertionError('must remain inert')):
            self.assertEqual(self.m.main([]),0)
    def test_evidence_requires_new_absolute_private_directory(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root)/'new'
            self.assertEqual(self.m.new_evidence(target),target)
            self.assertEqual(target.stat().st_mode & 0o777,0o700)
            for bad in (target,Path('relative'),Path('/run/autodata/fixture')):
                with self.assertRaises((ValueError,FileExistsError)): self.m.new_evidence(bad)
    def test_name_collision_rejected_without_mutation(self):
        fake = Daemon(); owned = self.m.OwnedDocker(RUN,fake)
        name = owned.name('pg')
        fake.objects['volume',name]={'Name':name,'Labels':{}}
        with self.assertRaises(ValueError): owned.volume('pg')
        self.assertFalse(any(a[1]=='create' for a in fake.calls))
    def test_names_are_dns_safe_and_uuid_bound(self):
        owned=self.m.OwnedDocker(RUN,Daemon())
        self.assertLessEqual(len(owned.name('source-s3')),63)
        self.assertIn(RUN.replace('-',''),owned.name('source-s3'))

    def test_container_bounds_and_exact_image_id(self):
        fake = Daemon(); owned = self.m.OwnedDocker(RUN,fake)
        owned.network(); owned.volume('pg'); owned.container('pg',self.m.IMAGES['postgres']['id'],['postgres'],512,'pg','/var/lib/postgresql/data')
        args = next(a for a in fake.calls if a[:2]==['container','create'])
        for forbidden in ('--privileged','--publish','-p','--network=host'): self.assertNotIn(forbidden,args)
        self.assertIn('--pull=never',args); self.assertIn('512m',args); self.assertIn('--cpus=1',args)
        self.assertIn('max-size=8m',args); self.assertIn('max-file=2',args)
        self.assertIn(self.m.IMAGES['postgres']['id'],args)
        for i in range(5): owned.container('extra'+str(i),self.m.IMAGES['nats']['id'],[],256)
        with self.assertRaises(ValueError): owned.container('seventh',self.m.IMAGES['nats']['id'],[],256)
    def test_cleanup_refuses_relabelled_or_replaced_resources(self):
        fake = Daemon(); owned = self.m.OwnedDocker(RUN,fake); owned.volume('pg')
        resource = owned.resources[0]; fake.objects['volume',resource['name']]['Labels']={}
        result=owned.cleanup()
        self.assertFalse(result['passed']); self.assertTrue(fake.objects)
        self.assertFalse(any(a[1]=='rm' for a in fake.calls))
    def test_cleanup_rejects_changed_volume_options(self):
        fake=Daemon(); owned=self.m.OwnedDocker(RUN,fake); owned.volume('pg')
        resource=owned.resources[0]; fake.objects['volume',resource['name']]['Options']={'device':'foreign'}
        self.assertFalse(owned.cleanup()['passed'])
        self.assertFalse(any(a[1]=='rm' for a in fake.calls))

    def test_daemon_list_failure_never_becomes_resource_absence(self):
        calls=[]
        def broken(args,**kwargs):
            calls.append(args); raise RuntimeError('daemon inaccessible')
        owned=self.m.OwnedDocker(RUN,broken)
        with self.assertRaises(RuntimeError):owned.volume('pg')
        self.assertFalse(any(a[1]=='create' for a in calls))

    def test_cleanup_failure_is_retained_and_cannot_pass(self):
        fake = Daemon(); owned = self.m.OwnedDocker(RUN,fake); owned.volume('pg'); fake.fail_remove=True
        result=owned.cleanup(); self.assertFalse(result['passed']); self.assertTrue(result['failures'])
        self.assertFalse(self.m.success({'positive':True},result))
    def test_cleanup_records_oom_and_removes_only_owned_identities(self):
        fake=Daemon(); owned=self.m.OwnedDocker(RUN,fake); owned.network(); owned.container('pg',self.m.IMAGES['postgres']['id'],[],512)
        resource=owned.resources[-1]; fake.objects['container',resource['id']]['State']['OOMKilled']=True
        result=owned.cleanup(); self.assertFalse(result['passed']); self.assertEqual(result['leftovers'],[])
        self.assertTrue(result['container_states'][0]['OOMKilled'])
    def test_seaweed_has_finite_grace_inside_shared_cleanup_reserve(self):
        fake=Daemon()
        def slow_stop(args,**kwargs):
            if args[:2]==['container','stop']:
                seconds=int(args[args.index('--time')+1]); self.assertLessEqual(seconds,45)
                value=fake.objects['container',args[-1]];value['State']['Running']=False
                value['State']['ExitCode']=0 if seconds>=30 else 137
                return b''
            return fake(args,**kwargs)
        owned=self.m.OwnedDocker(RUN,slow_stop);owned.container('cold-s3',self.m.IMAGES['seaweed']['id'],[],256)
        fake.objects['container',owned.resources[-1]['id']]['State']['Running']=True
        self.assertTrue(owned.cleanup()['passed'])

    def test_cleanup_nonzero_service_exit_cannot_pass(self):
        fake=Daemon(); owned=self.m.OwnedDocker(RUN,fake); owned.container('pg',self.m.IMAGES['postgres']['id'],[],512)
        fake.objects['container',owned.resources[-1]['id']]['State']['ExitCode']=1
        result=owned.cleanup(); self.assertFalse(result['passed']); self.assertEqual(result['leftovers'],[])

    def test_success_requires_every_named_assertion_and_cleanup(self):
        flags={name:True for name in self.m.ASSERTIONS}; clean={'passed':True,'leftovers':[]}
        self.assertTrue(self.m.success(flags,clean))
        for name in flags:
            changed=dict(flags);changed[name]=False;self.assertFalse(self.m.success(changed,clean))
        self.assertFalse(self.m.success({},clean))
    def test_copy_requires_stopped_exact_owned_containers(self):
        fake=Daemon(); owned=self.m.OwnedDocker(RUN,fake); owned.container('pg',self.m.IMAGES['postgres']['id'],[],512)
        fake.objects['container',owned.resources[-1]['id']]['State']['Running']=True
        with self.assertRaises(ValueError): owned.require_stopped()
    def test_cold_copy_rejects_oom_or_failed_source_exit_before_restart(self):
        for change in ({'OOMKilled':True},{'ExitCode':137}):
            fake=Daemon();owned=self.m.OwnedDocker(RUN,fake);owned.container('source-pg',self.m.IMAGES['postgres']['id'],[],512)
            fake.objects['container',owned.resources[-1]['id']]['State'].update(change)
            with self.assertRaises(ValueError):owned.require_stopped()

    def test_bucket_put_accepts_only_owned_by_you_conflict(self):
        class Names:
            def name(self,role):return 'fixture-owned-s3'
        fixture=self.m.Fixture(Names(),None,None,RUN,None)
        fixture.s3='source-s3'
        response=lambda code: b'HTTP/1.1 409 Conflict\r\nContent-Type: application/xml\r\nConnection: close\r\n\r\n<Error><Code>'+code+b'</Code></Error>'
        fixture.tcp=lambda *args:response(b'BucketAlreadyOwnedByYou')
        try:result=fixture.s3_request('PUT')
        except ValueError:self.fail('owned bucket idempotent response was rejected')
        self.assertEqual(result,b'<Error><Code>BucketAlreadyOwnedByYou</Code></Error>')
        for code in (b'BucketAlreadyExists',b'AccessDenied'):
            fixture.tcp=lambda *args:response(code)
            with self.assertRaises(ValueError):fixture.s3_request('PUT')
        fixture.tcp=lambda *args:response(b'BucketAlreadyOwnedByYou')
        with self.assertRaises(ValueError):fixture.s3_request('PUT','source/article.json',b'content')

    def test_seed_readback_verifies_expected_owner_pairs_and_payload(self):
        import hashlib
        import uuid
        self.assertTrue(hasattr(self.m,'verify_seed_inventory'),'independent seed readback is missing')
        uid=lambda key:str(uuid.uuid5(uuid.UUID(RUN),key))
        rows={table:[] for table in ('customer_accounts','auth_sessions','workshop_orders','entitlements','dataset_requests','vehicle_configurations','canonical_article_source_revisions')}
        for k in ('1','2'):
            rows['customer_accounts'].append({'customer_account_id':uid('account'+k),'personal_organization_id':uid('org'+k)})
            rows['auth_sessions'].append({'customer_account_id':uid('account'+k),'session_token_hash':'\\x'+hashlib.sha256(('session'+k).encode()).hexdigest()})
            scope={'customer_account_id':uid('account'+k),'organization_id':uid('org'+k),'configuration_id':uid('config'+k),'dataset_request_id':uid('request'+k)}
            rows['workshop_orders'].append(dict(scope,order_id=uid('order'+k),entitlement_id=uid('grant'+k)))
            rows['entitlements'].append(dict(scope,entitlement_id=uid('grant'+k),commerce_order_id=uid('order'+k)))
            rows['dataset_requests'].append({'dataset_request_id':uid('request'+k),'organization_id':uid('org'+k)})
            rows['vehicle_configurations'].append({'vehicle_configuration_id':uid('config'+k)})
        rows['canonical_article_source_revisions']=[{'source_revision_id':uid('revision')}]
        inventory={'relations':rows,'objects':[{'sha256':self.m.digest(self.m.PAYLOAD),'bytes':len(self.m.PAYLOAD)}],
            'jetstream':{'sequence':1,'messages':1,'delivered_stream_seq':0,'ack_floor_stream_seq':0,'payload_sha256':self.m.digest(b'{"message":"synthetic persisted workshop backup event"}')}}
        self.m.verify_seed_inventory(inventory,RUN)
        inventory['relations']['workshop_orders'][0]['organization_id']=uid('org2')
        with self.assertRaises(ValueError):self.m.verify_seed_inventory(inventory,RUN)

    def test_negative_results_must_reach_the_specific_fault(self):
        self.assertTrue(hasattr(self.m,'negative_rejected'),'fault-specific negative oracle is missing')
        failed={'status':'failed','failure_code':'input_or_restore_failed'}
        for case,observation in (
            ('corrupt_dump',{'stage':'restore_dump'}),
            ('missing_object',{'stage':'inspect_failed','error':'S3 request failed 404'}),
            ('missing_message',{'stage':'inspect_failed','error':'JetStream request failed $JS.API.STREAM.MSG.GET.BACKUP_FIXTURE'})):
            self.assertTrue(self.m.negative_rejected(case,4,failed,observation))
            self.assertFalse(self.m.negative_rejected(case,4,failed,{'stage':'create'}))
        self.assertTrue(self.m.negative_rejected('altered_owner',4,{'status':'failed','failure_code':'inventory_mismatch'},{'stage':'inspect_completed'}))
        self.assertFalse(self.m.negative_rejected('altered_owner',4,failed,{'stage':'inspect_completed'}))

    def test_command_output_and_wall_time_are_bounded(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as root:
            executor=self.m.Commands(Path(root),__import__('time').monotonic()+10)
            with self.assertRaises(ValueError): executor.process([sys.executable,'-c','print("x"*10000)'],maximum=100)
            with self.assertRaises(subprocess.TimeoutExpired): executor.process([sys.executable,'-c','import time;time.sleep(10)'],timeout=.05)


if __name__=='__main__': unittest.main()
