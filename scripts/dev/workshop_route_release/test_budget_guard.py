import unittest,subprocess
from budget_guard import *
from capacity_guard import wait_guarded
class BudgetTests(unittest.TestCase):
 def test_strict_entry(self):
  with self.assertRaisesRegex(RuntimeError,'capacity'):budget(ENTRY,1001,0,0,ENTRY,0)
  self.assertEqual(budget(ENTRY+1,1001,0,0,ENTRY+1,0)['external_growth'],0)
 def test_owned_growth_releases_only_matching_remaining_prep(self):
  b=ENTRY+200000000;p=100000000
  x=budget(b-p,1001,p,0,b,0)
  self.assertEqual(x['external_growth'],0);self.assertEqual(x['required_free_exclusive'],ENTRY-p)
 def test_external_growth_stop_and_burst(self):
  b=ENTRY+200000000
  self.assertEqual(budget(b-EXTERNAL_STOP+1,1001,0,0,b,0)['external_growth'],EXTERNAL_STOP-1)
  with self.assertRaisesRegex(RuntimeError,'external'):budget(b-EXTERNAL_STOP,1001,0,0,b,0)
  self.assertEqual(DRIFT-EXTERNAL_STOP,33554432)
 def test_caps_and_install_reservation(self):
  b=ENTRY+200000000
  for p,i in [(PREP+1,0),(0,INSTALL+1),(-1,0)]:
   with self.assertRaises(RuntimeError):budget(b,1001,p,i,b,0)
  x=budget(b-PREP,1001,PREP,0,b,0)
  self.assertEqual(x['required_free_exclusive'],ABSOLUTE+DRIFT+INSTALL)
 def test_baseline_owned_and_external_drift(self):
  b=ENTRY+200000000
  self.assertEqual(budget(b-999,1001,1999,0,b,1000)['external_growth'],0)
  self.assertEqual(budget(b-10999,1001,1999,0,b,1000)['external_growth'],10000)
 def test_capacity_failure_kills_real_owned_child(self):
  child=subprocess.Popen(['/usr/bin/sleep','30'],start_new_session=True)
  with self.assertRaisesRegex(RuntimeError,'capacity'):
   wait_guarded(child,lambda:budget(ENTRY,1001,0,0,ENTRY,0),timeout=1,interval=.01)
  self.assertIsNotNone(child.poll());self.assertNotEqual(child.returncode,0)
 def test_external_failure_kills_real_owned_child(self):
  child=subprocess.Popen(['/usr/bin/sleep','30'],start_new_session=True);b=ENTRY+200000000
  with self.assertRaisesRegex(RuntimeError,'external'):
   wait_guarded(child,lambda:budget(b-EXTERNAL_STOP,1001,0,0,b,0),timeout=1,interval=.01)
  self.assertIsNotNone(child.poll())
