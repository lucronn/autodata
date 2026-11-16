import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

P=Path(__file__).resolve().parents[1]/'archive_configuration_probe_baselines.py'
spec=importlib.util.spec_from_file_location('archive_baselines',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.src=self.root/'source';self.src.mkdir(mode=0o700)
  self.parent=self.root/'offloaded';self.parent.mkdir(mode=0o700);self.dest=self.parent/'archive'
  self.files={}
  for name in ('baseline-before.json','baseline-after.json'):
   p=self.src/name;p.write_bytes((name*100).encode());p.chmod(0o600);s=p.stat()
   self.files[name]={'bytes':s.st_size,'sha256':sha(p),'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'gid':s.st_gid,'mode':0o600,'links':1}
  self.manual=self.src/'manual-classification-v6.json';self.manual.write_text('{"automatic_verified":false}\n');self.manual.chmod(0o600)
  self.other=self.src/'untouched';self.other.write_text('preserve')
  self.cfg={'source_root':str(self.src),'destination':str(self.dest),'source_device':self.src.stat().st_dev,'destination_device':self.parent.stat().st_dev,'uid':os.getuid(),'gid':os.getgid(),'files':self.files,'manual_sha256':sha(self.manual)}
  self.a=m.Archive(self.cfg)
 def test_copy_then_cleanup_preserves_manual_and_other_files(self):
  result=self.a.copy();mapping=self.src/'baseline-offload-map-v1.json'
  self.assertEqual(result['mapping_sha256'],sha(mapping));self.assertTrue(all((self.src/n).exists() for n in self.files))
  for name,expected in self.files.items():self.assertEqual(sha(self.dest/name),expected['sha256']);self.assertEqual((self.dest/name).stat().st_mode&0o777,0o600)
  self.a.cleanup(result['mapping_sha256'])
  self.assertTrue(all(not(self.src/n).exists() for n in self.files));self.assertTrue(self.manual.exists());self.assertEqual(self.other.read_text(),'preserve')
  self.assertTrue((self.src/'baseline-offload-cleanup-v1.json').exists())
 def test_source_drift_refuses_without_removing_either_original(self):
  for field in ('inode','device','mode','sha256','bytes','uid','gid'):
   with self.subTest(field=field):
    cfg=json.loads(json.dumps(self.cfg));cfg['files']['baseline-before.json'][field]=('0'*64 if field=='sha256' else cfg['files']['baseline-before.json'][field]+1)
    with self.assertRaises(m.Refused):m.Archive(cfg).copy()
    self.assertTrue(all((self.src/n).exists() for n in self.files))
 def test_symlink_source_or_destination_refused(self):
  name='baseline-before.json';p=self.src/name;p.rename(self.src/'retained');p.symlink_to(self.src/'retained')
  with self.assertRaises(m.Refused):self.a.copy()
  p.unlink();(self.src/'retained').rename(p)
  self.dest.symlink_to(self.src,target_is_directory=True)
  with self.assertRaises(m.Refused):self.a.copy()
 def test_manual_drift_refuses(self):
  self.manual.write_text('changed')
  with self.assertRaises(m.Refused):self.a.copy()
 def test_target_drift_refuses_cleanup(self):
  result=self.a.copy();(self.dest/'baseline-after.json').write_bytes(b'changed')
  with self.assertRaises(m.Refused):self.a.cleanup(result['mapping_sha256'])
  self.assertTrue(all((self.src/n).exists() for n in self.files))
 def test_mapping_tamper_and_wrong_review_hash_refuse(self):
  result=self.a.copy()
  with self.assertRaises(m.Refused):self.a.cleanup('0'*64)
  p=self.src/'baseline-offload-map-v1.json';p.write_bytes(p.read_bytes()+b' ')
  with self.assertRaises(m.Refused):self.a.cleanup(result['mapping_sha256'])
  self.assertTrue(all((self.src/n).exists() for n in self.files))
 def test_source_changed_after_copy_refuses_cleanup(self):
  result=self.a.copy();(self.src/'baseline-before.json').write_bytes(b'changed')
  with self.assertRaises(m.Refused):self.a.cleanup(result['mapping_sha256'])
  self.assertTrue(all((self.src/n).exists() for n in self.files))
 def test_archive_symlink_refuses_cleanup(self):
  result=self.a.copy();p=self.dest/'baseline-after.json';p.unlink();p.symlink_to(self.src/'baseline-after.json')
  with self.assertRaises(m.Refused):self.a.cleanup(result['mapping_sha256'])
  self.assertTrue(all((self.src/n).exists() for n in self.files))
 def test_wrong_helper_hash_refuses_cli_before_live_archive_construction(self):
  import contextlib,io
  for action in ('copy','cleanup'):
   with patch.object(m,'Archive') as constructor,patch('sys.argv',[str(P),action,'--reviewed-helper-sha256','0'*64]),contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(m.main(),2);constructor.assert_not_called()
 def test_copy_is_exclusive_and_cleanup_one_attempt(self):
  result=self.a.copy()
  with self.assertRaises(m.Refused):self.a.copy()
  self.a.cleanup(result['mapping_sha256'])
  with self.assertRaises(m.Refused):self.a.cleanup(result['mapping_sha256'])
 def test_publish_failure_does_not_remove_source_or_write_mapping(self):
  with patch.object(m,'publish',side_effect=OSError('fixture')):
   with self.assertRaises(m.Refused):self.a.copy()
  self.assertFalse((self.src/'baseline-offload-map-v1.json').exists());self.assertTrue(all((self.src/n).exists() for n in self.files))
 def test_fsync_publication_mapping_precede_cleanup(self):
  events=[];sync=m.sync_dir;publish=m.publish;unlink=m.unlink_checked;fsync=os.fsync
  def fs(fd):events.append(('file-sync',os.fstat(fd).st_ino));return fsync(fd)
  def s(path):events.append(('sync',Path(path)));return sync(path)
  def p(src,dst):events.append(('publish',Path(dst)));return publish(src,dst)
  def u(path,proof):events.append(('unlink',Path(path)));self.assertTrue((self.src/'baseline-offload-map-v1.json').exists());self.assertTrue((self.src/'baseline-offload-cleanup-attempt-v1.json').exists());return unlink(path,proof)
  with patch.object(m,'sync_dir',side_effect=s),patch.object(m,'publish',side_effect=p),patch.object(m,'unlink_checked',side_effect=u),patch.object(m.os,'fsync',side_effect=fs):
   result=self.a.copy();self.a.cleanup(result['mapping_sha256'])
  publication=events.index(('publish',self.dest));first_unlink=next(i for i,e in enumerate(events) if e[0]=='unlink')
  self.assertIn(('sync',self.dest.parent),events[publication+1:first_unlink]);self.assertIn(('sync',self.src),events[publication+1:first_unlink])
  for name in self.files:self.assertIn(('file-sync',(self.dest/name).stat().st_ino),events[:publication])
  self.assertIn(('file-sync',(self.src/'baseline-offload-map-v1.json').stat().st_ino),events[:first_unlink])
 def test_cleanup_failure_keeps_verified_archive_and_attempt_receipt(self):
  result=self.a.copy()
  with patch.object(m,'unlink_checked',side_effect=OSError('fixture')):
   with self.assertRaises(m.Refused):self.a.cleanup(result['mapping_sha256'])
  self.assertTrue((self.src/'baseline-offload-cleanup-attempt-v1.json').exists());self.assertFalse((self.src/'baseline-offload-cleanup-v1.json').exists())
  self.assertTrue(all(sha(self.dest/n)==self.files[n]['sha256'] for n in self.files))
 def test_plan_is_read_only(self):
  before=set(self.src.iterdir());result=self.a.plan();self.assertEqual(set(self.src.iterdir()),before);self.assertFalse(self.dest.exists());self.assertEqual(result['files'],2)
 def test_extra_file_name_refused(self):
  self.cfg['files']['manual-classification-v6.json']=self.files['baseline-before.json']
  with self.assertRaises(m.Refused):m.Archive(self.cfg).plan()

if __name__=='__main__':unittest.main()
