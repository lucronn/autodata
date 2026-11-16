import unittest,subprocess,pathlib,tempfile,os
from unittest.mock import patch
import fixture_guard as f
from capacity_guard import wait_guarded
class FixtureGuardTests(unittest.TestCase):
 def test_profile96MiB_stop_preserves32MiB(self):
  f.limits(536870912,1001,f.PROFILE_STOP-1,2147483648)
  with self.assertRaisesRegex(RuntimeError,'early_stop'):f.limits(536870912,1001,f.PROFILE_STOP,2147483648)
  self.assertEqual(f.PROFILE_CAP-f.PROFILE_STOP,33554432)
 def test_tmp_free_inodes_and_memory_fail_closed(self):
  for free,inodes,profile,mem,reason in [(536870911,1001,0,2147483648,'free_floor'),(536870912,1000,0,2147483648,'inode_floor'),(536870912,1001,0,2147483647,'memory_reserve')]:
   with self.assertRaisesRegex(RuntimeError,reason):f.limits(free,inodes,profile,mem)
 def test_actual_profile_failure_kills_owned_child(self):
  p=subprocess.Popen(['/usr/bin/sleep','30'],start_new_session=True)
  with self.assertRaisesRegex(RuntimeError,'early_stop'):wait_guarded(p,lambda:f.limits(536870912,1001,f.PROFILE_STOP,2147483648),timeout=1,interval=.01)
  self.assertIsNotNone(p.poll());self.assertNotEqual(p.returncode,0)
 def test_cleanup_reaps_only_owned_process_group(self):
  owned=subprocess.Popen(['/usr/bin/sleep','30'],start_new_session=True)
  unrelated=subprocess.Popen(['/usr/bin/sleep','30'],start_new_session=True)
  try:
   f.stop_owned(owned);self.assertIsNotNone(owned.poll());self.assertIsNone(unrelated.poll())
  finally:f.stop_owned(unrelated)
 def test_dry_import_has_no_dispatch(self):
  with patch.object(subprocess,'Popen',side_effect=AssertionError('dispatch forbidden')):
   __import__('importlib').reload(f);self.assertEqual(f.PROFILE,pathlib.Path('/tmp/ad-route-09524db-qa'));self.assertLess(len(str(f.PROFILE/'chromium'/'SingletonSocket')),108)
 def test_owned_loopback_socket_table_refuses_wrong_listener(self):
  # Explicitly prove an unrelated listener cannot satisfy PID admission.
  import socket
  with socket.socket() as s:
   s.bind(('127.0.0.1',0));s.listen();port=s.getsockname()[1]
   child=subprocess.Popen(['/usr/bin/sleep','30'],start_new_session=True)
   try:
    with self.assertRaisesRegex(AssertionError,'not_owned'):f.socket_owned(child,port)
   finally:f.stop_owned(child)

class MountParserTests(unittest.TestCase):
 def fixture(self):return {'filesystems':[{'source':'systemd-1','fstype':'autofs','maj:min':'0:63','options':'rw,relatime'},{'source':'/dev/loop0[/home/corp/autodata-evidence]','fstype':'ext4','maj:min':'7:0','options':'rw,nosuid,nodev,relatime'}]}
 def test_exact_stacked_mount_accepts_actual_device(self):self.assertEqual(f.admit_mount(self.fixture(),1792)['fstype'],'ext4')
 def test_device_source_filesystem_and_options_refuse(self):
  for key,value in [('source','/dev/loop0'),('fstype','xfs'),('maj:min','7:1'),('options','rw,nosuid,nodev,noexec'),('options','ro,nosuid,nodev'),('options','rw,nodev')]:
   sample=self.fixture();sample['filesystems'][1][key]=value
   with self.subTest(key=key,value=value),self.assertRaises(AssertionError):f.admit_mount(sample,1792)
  with self.assertRaises(AssertionError):f.admit_mount(self.fixture(),66315)
 def test_extra_missing_duplicate_rows_refuse(self):
  for rows in [self.fixture()['filesystems'][:1],self.fixture()['filesystems']*2,[self.fixture()['filesystems'][1]]*2]:
   with self.assertRaises(AssertionError):f.admit_mount({'filesystems':rows},1792)
