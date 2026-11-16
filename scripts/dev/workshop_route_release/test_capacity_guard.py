import pathlib,tempfile,unittest,subprocess,time
import capacity_guard as g
class GuardTests(unittest.TestCase):
 def test_one_transient_retries_but_never_accepts_partial_number(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);calls=[];delays=[]
   def runner(cmd,**kw):
    calls.append(cmd)
    return subprocess.CompletedProcess(cmd,1,'1\t'+d+'\n',"du: cannot access '"+d+"/gone': No such file or directory\n") if len(calls)==1 else subprocess.CompletedProcess(cmd,0,'8192\t'+d+'\n','')
   self.assertEqual(g.allocated(p,runner=runner,sleeper=delays.append),8192);self.assertEqual(len(calls),2);self.assertEqual(delays,[.025])
 def test_persistent_enoent_stops_after_three_and_kills_owned_child(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);calls=[]
   def runner(cmd,**kw):calls.append(cmd);return subprocess.CompletedProcess(cmd,1,'1\t'+d+'\n',"du: cannot access '"+d+"/gone': No such file or directory\n")
   child=subprocess.Popen(['/usr/bin/sleep','30'],start_new_session=True)
   with self.assertRaisesRegex(g.AllocationReadError,'persistent'):
    g.wait_guarded(child,lambda:g.allocated(p,runner=runner,sleeper=lambda n:None),timeout=1,interval=.01)
   self.assertEqual(len(calls),3);self.assertIsNotNone(child.poll());self.assertNotEqual(child.returncode,0)
 def test_capacity_floor_failure_kills_owned_child_before_allocation_read(self):
  child=subprocess.Popen(['/usr/bin/sleep','30'],start_new_session=True);calls=[]
  def guard():g.require_floor(100,1001,100);calls.append('allocation_read')
  with self.assertRaisesRegex(RuntimeError,'capacity_floor'):g.wait_guarded(child,guard,timeout=1,interval=.01)
  self.assertEqual(calls,[]);self.assertIsNotNone(child.poll());self.assertNotEqual(child.returncode,0)
 def test_permission_error_never_retries_or_accepts_partial_stdout(self):
  with tempfile.TemporaryDirectory() as d:
   calls=[]
   def runner(cmd,**kw):calls.append(cmd);return subprocess.CompletedProcess(cmd,1,'1\t'+d+'\n','du: Permission denied\n')
   with self.assertRaises(g.AllocationReadError):g.allocated(d,runner=runner)
   self.assertEqual(len(calls),1)
 def test_malformed_success_refuses(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(g.AllocationReadError):g.allocated(d,runner=lambda *a,**k:subprocess.CompletedProcess(a,0,'0\twrong\n',''))
 def test_real_directory_and_missing_optional_package(self):
  with tempfile.TemporaryDirectory() as d:
   (pathlib.Path(d)/'owned').write_bytes(b'x'*4096);self.assertGreater(g.allocated(d),0);self.assertEqual(g.allocated(pathlib.Path(d)/'absent'),0)
