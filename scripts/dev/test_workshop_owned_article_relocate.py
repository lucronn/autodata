"""Owned temporary evidence trees only; never real relocation paths."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('relocate',Path(__file__).with_name('workshop_owned_article_relocate.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class RelocationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.parent=Path(self.temp.name);self.source=self.parent/'held';self.source.mkdir(mode=0o700);(self.source/'nested').mkdir();(self.source/'nested/file').write_bytes(b'owned immutable fixture');(self.source/'nested/file').chmod(0o444);self.target=self.parent/'published';self.expected=r.inventory(self.source)
 def tearDown(self):self.temp.cleanup()
 def test_verified_copy_preserves_source_and_private_modes(self):
  receipt=r.copy_verified(self.source,self.target,self.expected)
  self.assertEqual(r.inventory(self.source),self.expected);self.assertEqual(r.content(r.inventory(self.target)),r.content(self.expected));self.assertEqual(self.target.stat().st_mode&0o777,0o700);self.assertEqual((self.target/'nested/file').stat().st_mode&0o777,0o444);self.assertTrue(receipt['source_preserved'])
 def test_only_verified_copy_receipt_permits_cleanup(self):
  receipt=r.copy_verified(self.source,self.target,self.expected);r.cleanup_verified(self.source,self.target,self.expected,receipt)
  self.assertFalse(self.source.exists());self.assertEqual(r.content(r.inventory(self.target)),r.content(self.expected))
 def test_changed_source_rejects_before_copy(self):
  (self.source/'extra').write_bytes(b'changed')
  with self.assertRaises(ValueError):r.copy_verified(self.source,self.target,self.expected)
  self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())
 def test_changed_target_or_receipt_blocks_original_cleanup(self):
  receipt=r.copy_verified(self.source,self.target,self.expected);(self.target/'nested/file').chmod(0o644);(self.target/'nested/file').write_bytes(b'changed')
  with self.assertRaises(ValueError):r.cleanup_verified(self.source,self.target,self.expected,receipt)
  self.assertTrue(self.source.exists())
 def test_symlink_and_hardlink_rejected(self):
  (self.source/'link').symlink_to(self.parent)
  with self.assertRaises((ValueError,OSError)):r.inventory(self.source)
  (self.source/'link').unlink();os.link(self.source/'nested/file',self.source/'hard')
  with self.assertRaises(ValueError):r.inventory(self.source)
 def test_existing_final_or_pending_never_overwritten(self):
  for name in ['published','.published.copying']:
   target=self.parent/name;target.mkdir()
   with self.assertRaises((ValueError,OSError)):r.copy_verified(self.source,self.target,self.expected)
   self.assertEqual(list(target.iterdir()),[]);target.rmdir()
 def test_source_substitution_and_forged_receipt_rejected(self):
  receipt=r.copy_verified(self.source,self.target,self.expected);receipt['target_root']['inode']+=1
  with self.assertRaises(ValueError):r.cleanup_verified(self.source,self.target,self.expected,receipt)
  self.assertTrue(self.source.exists())
 def test_exclusive_lock_is_private_and_nonblocking(self):
  fd=r.acquire_lock(self.parent)
  try:
   self.assertEqual((self.parent/'held-ebed-relocation.lock').stat().st_mode&0o777,0o600)
   with self.assertRaises(BlockingIOError):r.acquire_lock(self.parent)
  finally:os.close(fd)
 def test_atomic_publish_has_no_replace(self):
  (self.parent/'a').mkdir();(self.parent/'b').mkdir()
  fd=r.open_dir(self.parent)
  try:
   with self.assertRaises(OSError):r.rename_noreplace(fd,'a',fd,'b')
  finally:os.close(fd)
  self.assertTrue((self.parent/'a').is_dir());self.assertTrue((self.parent/'b').is_dir())
 def test_private_receipt_is_exclusive(self):
  p=self.parent/'receipt.json';r.write_receipt(p,{'owned':True});self.assertEqual(p.stat().st_mode&0o777,0o600)
  with self.assertRaises(FileExistsError):r.write_receipt(p,{'owned':False})
 def test_changed_source_after_copy_blocks_cleanup(self):
  receipt=r.copy_verified(self.source,self.target,self.expected);(self.source/'extra').write_bytes(b'preserve')
  with self.assertRaises(ValueError):r.cleanup_verified(self.source,self.target,self.expected,receipt)
  self.assertTrue(self.source.exists());self.assertEqual((self.source/'extra').read_bytes(),b'preserve')
 def test_occupied_quarantine_preserves_original(self):
  receipt=r.copy_verified(self.source,self.target,self.expected);q=self.parent/'.held.relocated';q.mkdir();(q/'unrelated').write_bytes(b'preserve')
  with self.assertRaises(OSError):r.cleanup_verified(self.source,self.target,self.expected,receipt)
  self.assertEqual((q/'unrelated').read_bytes(),b'preserve');self.assertTrue(self.source.exists())
 def test_file_and_directory_fsync_precede_publish(self):
  from unittest.mock import patch
  events=[];sync=r.os.fsync;rename=r.rename_noreplace
  def tracked_sync(fd):events.append('sync');return sync(fd)
  def tracked_rename(*args):self.assertGreaterEqual(events.count('sync'),3);events.append('publish');return rename(*args)
  with patch.object(r.os,'fsync',tracked_sync),patch.object(r,'rename_noreplace',tracked_rename):r.copy_verified(self.source,self.target,self.expected)
  self.assertIn('sync',events[events.index('publish')+1:])
if __name__=='__main__':unittest.main()
