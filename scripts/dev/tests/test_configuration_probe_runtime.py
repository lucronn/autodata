import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
P=Path(__file__).resolve().parents[1]/'configuration_probe_runtime.py'
spec=importlib.util.spec_from_file_location('probe_runtime',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SCOPE='2'*16;ATTEMPT='3'*16
START=f'catalog configuration budget scope_hash={SCOPE} attempt={ATTEMPT} state=started stop_reason=none attempted_requests=0 elapsed_ms=0'
FIN=f'catalog configuration budget scope_hash={SCOPE} attempt={ATTEMPT} state=finished stop_reason=none attempted_requests=2 elapsed_ms=100'

def log(line):return ('2026-11-15T04:00:00.123456789Z '+line+'\n').encode()
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  config={'kind':'fixture','run_root':str(self.root),'docker_config':str(self.root/'docker-config'),'unit':'autodata-probe-fixture.service','fixture_sql_delay':6,'core':{'source_sha':'1'*40,'runtime_reviewed':True,'run_id':'fixture01','scope_hash':SCOPE,'candidate':{'id':'a'*64,'fingerprint':'c'*64},'predecessor':{'id':'b'*64,'fingerprint':'d'*64}}}
  self.calls=[]
  self.a=m.Adapter(config,lambda:'e'*64,runner=self.runner)
  network=patch.object(m.HTTP,'open',side_effect=AssertionError('offline HTTP forbidden'));network.start();self.addCleanup(network.stop)
  self.a.cfg['physical_device']=self.root.stat().st_dev;self.a.cfg['socket_identity']=[0,0]
  (self.root/'docker-config').mkdir(mode=0o700)
 def runner(self,argv,**kwargs):
  self.calls.append((argv,kwargs));raise AssertionError('unmocked child forbidden')
 def test_fixed_real_child_environment(self):
  with patch.dict(os.environ,{'DOCKER_HOST':'tcp://secret','HTTPS_PROXY':'http://secret','PYTHONPATH':'/secret'}):
   result=m.bounded([sys.executable,'-I','-c','import os,json;print(json.dumps(dict(os.environ)))'])
  env=json.loads(result);self.assertNotIn('DOCKER_HOST',env);self.assertNotIn('HTTPS_PROXY',env);self.assertNotIn('PYTHONPATH',env)
 def test_output_limit_and_deadline_do_not_expose_text(self):
  for code,kwargs in [("print('SENTINEL_SECRET'*1000)",{'limit':100}),('import time;time.sleep(10)',{'timeout':.1})]:
   started=time.monotonic()
   with self.assertRaises(m.core.Refused) as error:m.bounded([sys.executable,'-I','-c',code],**kwargs)
   self.assertNotIn('SENTINEL_SECRET',str(error.exception));self.assertLess(time.monotonic()-started,2)
 def test_log_exact_formats_and_malformed_finish(self):
  lines,bad=m.parse_logs(log(START)+log('WARNING:autodata_ingestion.catalog_service:'+FIN),SCOPE)
  self.assertFalse(bad);self.assertTrue(m.core.finished(lines,SCOPE))
  lines,bad=m.parse_logs(log(START)+log(FIN.replace('attempted_requests=2','attempted_requests=99')),SCOPE)
  self.assertTrue(bad);self.assertEqual(lines,[START]);self.assertFalse(m.core.finished(lines,SCOPE))
 def test_unrelated_raw_log_not_retained(self):
  lines,bad=m.parse_logs(log('SENTINEL_SECRET https://secret')+log(START),SCOPE)
  self.assertFalse(bad);self.assertEqual(lines,[START])
 def test_supervisor_identity_drift_refused(self):
  proof={'unit':'fixture.service','pid':42,'boot_id':'boot','start_ticks':5,'python_sha256':'a','argv':['/usr/bin/python3','-I','/physical/launcher.py','watch'],'unit_file_sha256':'b'}
  props={'Id':'fixture.service','LoadState':'loaded','ActiveState':'active','SubState':'running','MainPID':'42','User':'corp','KillMode':'control-group','Restart':'no','RuntimeMaxUSec':'25s','TimeoutStopUSec':'15s','PrivateNetwork':'yes','ControlGroup':'/system.slice/fixture.service','FragmentPath':'/run/systemd/transient/fixture.service','ExecStopPost':'{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I /physical/launcher.py finalize ; ignore_errors=no ; }'}
  proc={'boot_id':'boot','start_ticks':5,'executable_sha256':'a','argv':['/usr/bin/python3','-I','/physical/launcher.py','watch'],'cgroup':'0::/system.slice/fixture.service','unit_file_sha256':'b'}
  self.assertTrue(m.supervisor_matches(proof,props,proc))
  for key,value in [('start_ticks',6),('boot_id','other'),('argv',['other']),('unit_file_sha256','drift')]:
   changed=dict(proc);changed[key]=value;self.assertFalse(m.supervisor_matches(proof,props,changed))
  changed=dict(props);changed['ActiveState']='failed';self.assertFalse(m.supervisor_matches(proof,changed,proc))
 def test_supervisor_command_is_independent_and_network_isolated(self):
  argv=self.a.unit_command(Path('/physical/launcher.py'))
  self.assertEqual(argv[:3],['/usr/bin/sudo','-n','/usr/bin/systemd-run'])
  for value in ('--property=RuntimeMaxSec=25s','--property=PrivateNetwork=yes','--property=KillMode=control-group'):self.assertIn(value,argv)
  self.assertTrue(any('ExecStopPost=/usr/bin/python3 -I /physical/launcher.py finalize' in x for x in argv))
 def test_public_fetch_is_one_curl_and_safe_fields_only(self):
  self.a.cfg['kind']='production'
  def run(argv,**kwargs):
   self.calls.append((argv,kwargs));return b'{"items":[{"complete":true}],"complete":false,"hydrating":true,"secret":"SENTINEL_SECRET"}\n200'
  self.a.runner=run;result=self.a.fetch(m.core.URL)
  self.assertEqual(result['items'],1);self.assertFalse(result['complete']);self.assertEqual(len(self.calls),1)
  argv=self.calls[0][0];self.assertEqual(argv[:2],['/usr/bin/curl','-q']);self.assertIn('--max-filesize',argv);self.assertNotIn('--retry',argv);self.assertNotIn('--location',argv)
  self.assertNotIn('SENTINEL_SECRET',(self.root/'response-safe.json').read_text())
 def test_finalizer_never_retries_unknown_stop(self):
  self.a.admit=Mock();self.a.logs=Mock(return_value=([START],False));self.a.probe=Mock()
  self.a.probe.recover.side_effect=m.core.Refused('unknown stop');self.a.stop=Mock()
  for name in ('armed','attempted','fence-attempted'):self.a.store.put(name,{})
  self.a.probe.disarm_proven.return_value=False
  with self.assertRaises(m.core.Refused):self.a.finalize()
  self.a.stop.assert_not_called();self.assertTrue(self.a.store.exists('finalizer-inconclusive'))
  hold=self.a.store.get('recovery-hold');self.assertFalse(hold['provider_ended_proven']);self.assertFalse(hold['restart_authorized']);self.assertEqual(hold['intentional_stop_attempts'],1)
  self.assertFalse(self.a.store.get('unit-finalized')['provider_ended_proven']);self.a.probe.verify_outcome.assert_not_called()
 def test_broken_arm_without_prior_fence_gets_emergency_hold(self):
  self.a.admit=Mock();self.a.logs=Mock(return_value=([START],False));self.a.probe=Mock();self.a.stop=Mock()
  self.a.probe.recover.side_effect=m.core.Refused('broken arm');self.a.probe.clock.return_value=0;self.a.store.put('attempted',{})
  self.a.probe.disarm_proven.return_value=False
  with self.assertRaises(m.core.Refused):self.a.finalize()
  self.a.stop.assert_called_once_with('a'*64)
  self.assertTrue(self.a.store.exists('emergency-fenced'));self.a.probe.verify_outcome.assert_not_called()
 def test_emergency_stop_unknown_is_durable_hard_hold(self):
  self.a.admit=Mock();self.a.logs=Mock(side_effect=m.core.Refused('logs unknown'));self.a.probe=Mock()
  self.a.probe.recover.side_effect=m.core.Refused('binding unknown');self.a.probe.disarm_proven.return_value=False;self.a.probe.clock.return_value=0
  self.a.stop=Mock(side_effect=m.core.Refused('stop unknown'));self.a.store.put('attempted',{})
  with self.assertRaises(m.core.Refused):self.a.finalize()
  self.a.stop.assert_called_once_with('a'*64)
  self.assertTrue(self.a.store.exists('recovery-hold'));self.assertFalse(self.a.store.exists('emergency-fenced'))
  self.assertFalse(self.a.store.get('unit-finalized')['provider_ended_proven']);self.a.probe.verify_outcome.assert_not_called()
 def test_catalog_edits_and_additions_require_manual_classification(self):
  for delta in ('edit','add'):
   with self.subTest(delta=delta),tempfile.TemporaryDirectory() as tmp:
    self.a.store=m.core.Store(Path(tmp));self.a.cfg.update(kind='production',protected_tables=['protected'])
    row={'row_hash':'1','column_hashes':{'scope':'2'}}
    before={'protected':{'p':row},'catalog':{'c':row}}
    after=json.loads(json.dumps(before))
    if delta=='edit':after['catalog']['c']['row_hash']='3'
    else:after['catalog']['new']=row
    self.a.probe=Mock();self.a.probe.disarm_proven.return_value=True;self.a.probe.clock.return_value=0
    self.a.store.put('armed',{'armed_at':0});self.a.store.put('disarmed',{})
    self.a.store.put('unit-finalized',{'manifest_hash':m.core.validate_manifest(self.a.cfg['core']),'provider_ended_proven':True})
    m.put_baseline(self.a.store,'baseline-before',{'tables':before})
    self.a.rollout=Mock(return_value=Mock(combined_baseline=Mock(return_value={'tables':after})))
    self.a.scope_safety=Mock(return_value={'target_marker':{'completion_version':1}})
    self.a.local_health=Mock(return_value={'healthy':True,'purchase_enabled':False})
    self.a.raw_candidate=Mock(return_value={'State':{'Running':True},'RestartCount':0})
    result=self.a.postcheck('a'*64)
    self.assertTrue(result['protected_unchanged']);self.assertFalse(result['catalog_baseline_preserved'])
    self.assertTrue(self.a.store.exists('baseline-delta'));self.assertTrue(self.a.store.exists('selector-safety-after'))
    comparison=self.a.store.get('baseline-comparison');self.assertTrue(comparison['baseline_rows_preserved']);self.assertFalse(comparison['catalog_exact']);self.assertTrue(comparison['manual_scope_classification_required'])
 def test_slow_fixture_sql_only_after_disarm_and_unit_exit(self):
  self.a.probe=Mock();self.a.probe.disarm_proven.return_value=True
  self.a.properties=Mock(return_value={'MainPID':'0','ActiveState':'inactive'})
  with patch.object(m.time,'sleep') as sleep:
   with self.assertRaises(AssertionError):self.a.postcheck('a'*64)
   sleep.assert_not_called()
   self.a.store.put('disarmed',{});self.a.store.put('unit-finalized',{'manifest_hash':m.core.validate_manifest(self.a.cfg['core']),'provider_ended_proven':True});self.a.postcheck('a'*64);sleep.assert_called_once_with(6)
   self.assertTrue(self.a.store.exists('postcheck-started'))
 def test_production_approval_refusal_precedes_unit_or_http(self):
  self.a.cfg.update(kind='production',approval_path=str(self.root/'missing'))
  self.a.admit=Mock();self.a.launcher_hash='e'*64;self.a.raw_candidate=Mock(return_value={'Id':'a'*64,'State':{'Running':True},'RestartCount':0})
  with self.assertRaises(FileNotFoundError):self.a.arm_and_dispatch(Path('/physical/launcher.py'))
  self.assertEqual(self.calls,[]);self.assertFalse(self.a.store.exists('attempted'))
 def test_baseline_delta_preserves_keys_and_columns(self):
  before={'t':{'k':{'row_hash':'a','column_hashes':{'engine':'1','updated_at':'2'}}}}
  after={'t':{'k':{'row_hash':'b','column_hashes':{'engine':'1','updated_at':'3'}},'new':{'row_hash':'c','column_hashes':{}}}}
  delta=m.baseline_delta(before,after)['t'];self.assertEqual(delta['additions'],['new']);self.assertEqual(delta['deletions'],[]);self.assertEqual(delta['changes'],{'k':['updated_at']})
 def test_exact_state_bound_created_running_hostconfig_hashes(self):
  config={'Env':['fixture'], 'WorkingDir':'/app'};mounts=[{'Source':'/exact/source','Destination':'/app','RW':False}]
  created={'NetworkMode':'none','OomKillDisable':False};running={**created,'OomKillDisable':None}
  self.a.cfg['container']={'image':'sha256:'+'1'*64,'Config_sha256':m.digest(config),'Mounts_sha256':m.digest(mounts),
      'HostConfig_sha256':m.digest(created),'HostConfig_state_sha256':{'created':m.digest(created),'running':m.digest(running),'exited':m.digest(running),'dead':m.digest(running)}}
  for state,host in [('created',created),('running',running),('exited',running)]:
   value={'Id':'a'*64,'Image':'sha256:'+'1'*64,'Config':config,'HostConfig':host,'Mounts':mounts,'State':{'Status':state}}
   self.a.cfg['kind']='production';self.a.docker=Mock(return_value=json.dumps([value]).encode())
   with self.subTest(state=state):self.assertEqual(self.a.raw_candidate()['State']['Status'],state)
  for state,host in [('running',created),('created',running),('paused',running),('running',{**running,'NetworkMode':'host'})]:
   value={'Id':'a'*64,'Image':'sha256:'+'1'*64,'Config':config,'HostConfig':host,'Mounts':mounts,'State':{'Status':state}}
   self.a.docker=Mock(return_value=json.dumps([value]).encode())
   with self.subTest(refused_state=state,host=host),self.assertRaises(AssertionError):self.a.raw_candidate()
  for key,bad in [('Config',{}),('Mounts',[]),('Image','sha256:'+'2'*64)]:
   value={'Id':'a'*64,'Image':'sha256:'+'1'*64,'Config':config,'HostConfig':running,'Mounts':mounts,'State':{'Status':'running'}};value[key]=bad
   self.a.docker=Mock(return_value=json.dumps([value]).encode())
   with self.subTest(drift=key),self.assertRaises(AssertionError):self.a.raw_candidate()
 def test_sealed_baseline_reads_91366487_byte_shape(self):
  import hashlib
  size=91366487;path=self.a.store.path('baseline-before')
  prefix=b'{"tables":{"vehicles":{';suffix=b'}}}\n';digest=hashlib.sha256()
  # Real keyed row/column-hash shape, not a91MB string or padding-only parser test.
  row=m.core.canonical({'row_hash':'a'*32,'column_hashes':{'column'+str(i):'b'*32 for i in range(24)}})
  record=b'"00000000000000000000000000000000":'+row
  count=(size-len(prefix)-len(suffix)-1)//(len(record)+1)
  with path.open('xb') as handle:
   os.chmod(path,0o600);handle.write(prefix);digest.update(prefix)
   for i in range(count):
    chunk=(b',' if i else b'')+('"%032x":'%i).encode()+row
    handle.write(chunk);digest.update(chunk)
   padding=size-handle.tell()-len(suffix)
   while padding:
    chunk=b' '*min(1048576,padding);handle.write(chunk);digest.update(chunk);padding-=len(chunk)
   handle.write(suffix);digest.update(suffix)
  self.a.store.put('baseline-before-seal',{'bytes':size,'sha256':digest.hexdigest()})
  with self.assertRaises(m.core.Refused):self.a.store.get('baseline-before')
  self.assertEqual(m.get_baseline(self.a.store,'baseline-before')['tables']['vehicles']['0'*32]['row_hash'],'a'*32)
 def test_baseline_seal_hash_size_and_missing_refuse(self):
  for failure in ('hash','size','missing'):
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
    store=m.core.Store(Path(tmp));value={'tables':{}}
    store.put('baseline-before',value)
    if failure!='missing':store.put('baseline-before-seal',{'bytes':store.path('baseline-before').stat().st_size+(failure=='size'),'sha256':'0'*64})
    with self.assertRaises(m.core.Refused):m.get_baseline(store,'baseline-before')
 def test_baseline_max_and_symlink_and_names_refuse(self):
  path=self.a.store.path('baseline-before')
  with path.open('wb') as handle:handle.truncate(128*1024*1024+1)
  path.chmod(0o600);self.a.store.put('baseline-before-seal',{'bytes':path.stat().st_size,'sha256':'0'*64})
  with self.assertRaises(m.core.Refused):m.get_baseline(self.a.store,'baseline-before')
  path.unlink();path.symlink_to(self.a.store.path('baseline-before-seal'))
  with self.assertRaises(m.core.Refused):m.get_baseline(self.a.store,'baseline-before')
  with self.assertRaises(m.core.Refused):m.get_baseline(self.a.store,'armed')
 def test_baseline_writer_seals_exact_size_hash_and_exclusive(self):
  import hashlib
  value={'tables':{'catalog':{}}};m.put_baseline(self.a.store,'baseline-after',value)
  seal=self.a.store.get('baseline-after-seal');data=self.a.store.path('baseline-after').read_bytes()
  self.assertEqual(seal,{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
  self.assertEqual(m.get_baseline(self.a.store,'baseline-after'),value)
  with self.assertRaises(m.core.Refused):m.put_baseline(self.a.store,'baseline-after',value)
 def test_socket_drift_refuses_before_docker_child(self):
  with self.assertRaises(AssertionError):self.a.docker(['inspect','a'*64])
  self.assertEqual(self.calls,[])
 def test_loopback_health_and_purchase_are_observed(self):
  response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);response.status=200;response.read.return_value=b'{"enabled":false}'
  self.a.remaining=Mock(return_value=10)
  with patch.object(m.HTTP,'open',return_value=response) as open:
   value=self.a.local_health()
  self.assertTrue(value['healthy']);self.assertFalse(value['purchase_enabled']);self.assertEqual(open.call_count,3)
  self.assertTrue(all(call.kwargs['timeout']<=1 for call in open.call_args_list))
if __name__=='__main__':unittest.main()
