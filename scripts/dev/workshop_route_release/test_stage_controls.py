import hashlib,importlib.util,os,pathlib,tempfile,unittest
from unittest.mock import patch
P=pathlib.Path(__file__).with_name('stage_controls.py')
spec=importlib.util.spec_from_file_location('stage',P);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class StageTests(unittest.TestCase):
 def test_import_never_dispatches(self):
  with patch('subprocess.Popen',side_effect=AssertionError('no child')):spec.loader.exec_module(s)
 def test_inventory_rejects_changed_bytes_and_preserves_original(self):
  with tempfile.TemporaryDirectory() as d,patch.object(s,'R',pathlib.Path(d)):
   p=s.R/'file';p.write_bytes(b'original');seal={'files':{'file':{'bytes':8,'sha256':hashlib.sha256(b'original').hexdigest()}}}
   s.inventory(seal,os.stat(d).st_dev,os.getuid());p.write_bytes(b'modified')
   with self.assertRaisesRegex(AssertionError,'packet_bytes'):s.inventory(seal,os.stat(d).st_dev,os.getuid())
 def test_inventory_rejects_symlinks_and_hardlinks(self):
  with tempfile.TemporaryDirectory() as d,patch.object(s,'R',pathlib.Path(d)):
   p=s.R/'file';p.write_bytes(b'original');seal={'files':{'file':{'bytes':8,'sha256':hashlib.sha256(b'original').hexdigest()}}};link=s.R/'link';link.symlink_to(p)
   with self.assertRaisesRegex(AssertionError,'packet_metadata'):s.inventory({'files':{'link':seal['files']['file']}},os.stat(d).st_dev,os.getuid())
   link.unlink();os.link(p,link)
   with self.assertRaisesRegex(AssertionError,'packet_metadata'):s.inventory(seal,os.stat(d).st_dev,os.getuid())
 def test_wrong_device_or_owner_fails(self):
  with tempfile.TemporaryDirectory() as d,patch.object(s,'R',pathlib.Path(d)):
   p=s.R/'file';p.write_bytes(b'x');seal={'files':{'file':{'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}}}
   for device,uid in [(os.stat(d).st_dev+1,os.getuid()),(os.stat(d).st_dev,os.getuid()+1)]:
    with self.assertRaisesRegex(AssertionError,'packet_metadata'):s.inventory(seal,device,uid)
