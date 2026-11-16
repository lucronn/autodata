import importlib.util,unittest,tempfile,json,os,hashlib
from pathlib import Path
from unittest.mock import patch,Mock
spec=importlib.util.spec_from_file_location('release',Path(__file__).with_name('workshop_public_release.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class ReleaseTests(unittest.TestCase):
 def test_capacity_boundaries_preserve_both_filesystems(self):
  p={'home_absolute':5368709120,'drift':134217728,'prep_cap':134217728,'install_cap':67108864,'root_absolute':2147483648,'root_burst':33554432,'docker_floor':813694976,'external_stop':100663296}
  v={'home_free':6000000000,'root_free':3000000000,'docker_free':990000000,'inodes':2000,'prep':95612928,'install':0,'external_growth':0}
  self.assertEqual(r.capacity_errors(v,p),[])
  for k,x in [('home_free',1),('root_free',1),('docker_free',1),('inodes',1),('prep',134217729),('install',67108865),('external_growth',100663296)]:self.assertTrue(r.capacity_errors({**v,k:x},p))
 def test_exact_override_replacement_only(self):
  old=b'/old';new=b'/new';self.assertEqual(r.target_override(b'A /old B',old,new),b'A /new B')
  for b in [b'A',b'/old /old']:
   with self.assertRaises(r.Refused):r.target_override(b,old,new)
 def test_exclusive_private_marker_and_atomic_restore(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'marker';r.exclusive(p,b'exact');self.assertEqual(p.stat().st_mode&0o777,0o600)
   with self.assertRaises(FileExistsError):r.exclusive(p,b'again')
   f=root/'99.conf';f.write_bytes(b'target');info={'uid':os.getuid(),'gid':os.getgid(),'mode':'0o644'};r.atomic_file(f,b'original',info)
   self.assertEqual(f.read_bytes(),b'original');self.assertEqual(f.stat().st_mode&0o777,0o644)
 def test_execution_fence_rejects_before_any_command(self):
  with patch.object(r,'command',side_effect=AssertionError('no_dispatch')) as cmd:
   with self.assertRaises(r.Refused):r.execution_fence({'approved':True},'a'*64,'b'*64)
   cmd.assert_not_called()
 def test_wait_accepts_transient_pid_only_and_never_restarts(self):
  with patch.object(r,'running_identity',side_effect=[False,False,True]),patch.object(r.time,'sleep'),patch.object(r,'command') as cmd:
   r.wait_identity('/owned',{'sha256':'a'*64},timeout=1);cmd.assert_not_called()
  with patch.object(r,'running_identity',return_value=False),patch.object(r.time,'sleep'):
   with self.assertRaises(r.Refused):r.wait_identity('/owned',{},timeout=.001)
 def test_rollback_marker_precedes_restore_and_only_one_restart(self):
  c=object.__new__(r.Control);c.m={};c.root=Path('/owned');c.baseline_check=Mock();c.rollback_inputs=Mock(return_value=[]);c.persist=Mock();c.restart=Mock();c.old_check=Mock()
  c.rollback();self.assertEqual(c.persist.call_args.args[0],'rollback-attempted');c.restart.assert_called_once();c.old_check.assert_called_once()
 def test_rollback_unknown_state_refuses_before_marker(self):
  c=object.__new__(r.Control);c.m={};c.root=Path('/owned');c.rollback_inputs=Mock(side_effect=r.Refused('drift'));c.persist=Mock();c.restart=Mock()
  with self.assertRaises(r.Refused):c.rollback()
  c.persist.assert_not_called();c.restart.assert_not_called()
class AdditionalRefusalTests(unittest.TestCase):
 def test_env_policy_rejects_duplicates_and_changed_auth_without_output(self):
  good=b'AUTODATA_COMMERCE_MODE=read_only\nAUTODATA_AUTH_MODE=firebase\n';r.env_policy(good)
  for data in [good+good,good.replace(b'read_only',b'stripe_test'),good.replace(b'firebase',b'local')]:
   with self.assertRaises(r.Refused):r.env_policy(data)
 def test_marker_tamper_refuses(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'m';p.write_bytes(b'marker');p.chmod(0o600)
   with self.assertRaises(r.Refused):r.check_marker(p,b'other')
 def test_no_second_rollback_and_original_file_restored(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);target=root/'99.conf';target.write_bytes(b'candidate');info={'uid':os.getuid(),'gid':os.getgid(),'mode':'0o644'}
   c=object.__new__(r.Control);c.m={};c.hash='a'*64;c.root=root;c.rollback_inputs=Mock(return_value=[(target,b'old',info)]);c.restart=Mock();c.old_check=Mock()
   c.rollback();self.assertEqual(target.read_bytes(),b'old');self.assertEqual((root/'rollback-attempted').read_bytes(),('a'*64+'\n').encode())
   with self.assertRaises(FileExistsError):c.rollback()
   c.restart.assert_called_once()
 def test_restart_only_api_once(self):
  c=object.__new__(r.Control)
  with patch.object(r,'command') as call:c.restart()
  self.assertEqual([x.args[0] for x in call.call_args_list],[['/usr/bin/systemctl','daemon-reload'],['/usr/bin/systemctl','restart','autodata-api.service']])
 def test_switch_precondition_refusal_has_no_write_or_restart(self):
  c=object.__new__(r.Control);c.prepared=Mock(side_effect=r.Refused('backup_drift'));c.baseline_check=Mock();c.persist=Mock();c.restart=Mock()
  with patch.object(r,'atomic_file') as write:
   with self.assertRaises(r.Refused):c.switch()
  write.assert_not_called();c.persist.assert_not_called();c.restart.assert_not_called()
 def test_private_json_refuses_symlink_and_unsafe_mode(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'receipt';p.write_text('{}');p.chmod(0o644)
   with self.assertRaises(r.Refused):r.private_json(p)
   link=Path(d)/'link';link.symlink_to(p)
   with self.assertRaises(r.Refused):r.private_json(link)
 def test_rollback_does_not_depend_on_candidate_payload(self):
  c=object.__new__(r.Control);c.root=Path('/owned');c.rollback_inputs=Mock(return_value=[]);c.persist=Mock();c.restart=Mock();c.old_check=Mock()
  with patch.object(r,'payload_check',side_effect=AssertionError('candidate_not_needed')):c.rollback()
 def test_child_output_and_failure_do_not_expose_stderr(self):
  import subprocess
  with patch.object(r.subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'',b'secret')):
   with self.assertRaises(r.Refused) as caught:r.command(['/usr/bin/systemctl','show','autodata-api.service'])
  self.assertEqual(str(caught.exception),'child_failed')
class CanaryReservationTests(unittest.TestCase):
 def test_canary_reserves_before_network_and_refuses_second_dispatch(self):
  with tempfile.TemporaryDirectory() as d:
   c=object.__new__(r.Control);c.root=Path(d);c.hash='a'*64;c.m={};c.prepared=Mock();c.candidate_check=Mock();c.old_check=Mock();c.baseline_check=Mock()
   def result(*args):self.assertTrue((c.root/'candidate-probes-attempted').exists());return {'passed':True}
   with patch.object(r,'probe_receipt',side_effect=result) as fetch:
    c.canary('candidate')
    with self.assertRaises(FileExistsError):c.canary('candidate')
   fetch.assert_called_once();self.assertTrue((c.root/'candidate-probes.json').exists())
 def test_canary_failure_preserves_consumed_marker_and_never_restarts(self):
  with tempfile.TemporaryDirectory() as d:
   c=object.__new__(r.Control);c.root=Path(d);c.hash='a'*64;c.m={};c.prepared=Mock();c.candidate_check=Mock();c.old_check=Mock();c.baseline_check=Mock();c.restart=Mock()
   with patch.object(r,'probe_receipt',side_effect=r.Refused('body_hash')):
    with self.assertRaises(r.Refused):c.canary('candidate')
   self.assertTrue((c.root/'candidate-probes-attempted').exists());self.assertFalse((c.root/'candidate-probes.json').exists());c.restart.assert_not_called()
class ManifestFenceTests(unittest.TestCase):
 def test_bad_review_hash_refuses_before_package_read(self):
  with patch.object(r,'payload_check',side_effect=AssertionError('no_payload')):
   with self.assertRaises(r.Refused):r.load('not-a-sha','not-a-sha')
 def test_atomic_restore_syncs_parent_after_replace(self):
  with tempfile.TemporaryDirectory() as d:
   target=Path(d)/'99';target.write_bytes(b'new');events=[]
   replace=r.os.replace
   with patch.object(r.os,'replace',side_effect=lambda a,b:(events.append('rename'),replace(a,b))[1]),patch.object(r,'sync_dir',side_effect=lambda p:events.append('parent_sync')):
    r.atomic_file(target,b'old',{'uid':os.getuid(),'gid':os.getgid(),'mode':'0o644'})
   self.assertEqual(events,['rename','parent_sync']);self.assertEqual(target.read_bytes(),b'old')
 def test_install_refuses_existing_target_before_marker_or_file_write(self):
  with tempfile.TemporaryDirectory() as d,patch.object(r,'INSTALL',Path(d)/'api'):
   c=object.__new__(r.Control);c.prepared=Mock();c.baseline_check=Mock();c.persist=Mock()
   with self.assertRaises(r.Refused):c.install()
   c.persist.assert_not_called()
class ProbeChildFenceTests(unittest.TestCase):
 def test_low_capacity_refuses_before_probe_dispatch(self):
  with tempfile.TemporaryDirectory() as d,patch.object(r,'ROOT',Path(d)),patch.object(r,'capacity',side_effect=r.Refused('capacity')),patch.object(r.subprocess,'Popen') as child:
   (Path(d)/'release-manifest.json').write_text('{}')
   with self.assertRaises(r.Refused):r.probe_receipt({},'candidate')
   child.assert_not_called()
 def test_actual_owned_sleep_is_killed_on_capacity_failure(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'release-manifest.json').write_text('{}');(root/'workshop_public_probe.py').write_text('import time;time.sleep(10)')
   real=r.subprocess.Popen;owned=[]
   def spawn(*a,**kw):
    child=real(*a,**kw);owned.append(child);return child
   with patch.object(r,'ROOT',root),patch.object(r,'capacity',side_effect=[{},r.Refused('capacity')]),patch.object(r.subprocess,'Popen',side_effect=spawn):
    with self.assertRaises(r.Refused):r.probe_receipt({},'candidate')
   self.assertEqual(len(owned),1);self.assertIsNotNone(owned[0].poll())
if __name__=='__main__':unittest.main()
