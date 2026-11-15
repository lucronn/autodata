"""Browser route boundaries; actual browser acceptance is separate."""
import importlib.util
from pathlib import Path
import unittest
import shutil
spec=importlib.util.spec_from_file_location('smoke',Path(__file__).with_name('workshop_owned_article_smoke.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class BrowserBoundaryTests(unittest.TestCase):
 def test_only_exact_session_route_is_simulated(self):
  self.assertEqual(s.request_policy(s.ORIGIN+'/auth/session','GET'),'session')
  for p in ['/auth/config','/workshop/','/v1/catalog/vehicles/owned/articles','/v1/catalog/vehicles/owned/articles/owned','/v1/catalog/images/opaque','/workshop/purchase-config.json']:
   self.assertNotEqual(s.request_policy(s.ORIGIN+p,'GET'),'session')
  self.assertEqual(s.request_policy(s.ORIGIN+'/auth/session?extra=1','GET'),'abort')
  self.assertEqual(s.request_policy(s.ORIGIN+'/auth/session','POST'),'abort')
 def test_authorization_scoped_to_real_catalog_not_images_or_other_origin(self):
  self.assertEqual(s.request_policy(s.ORIGIN+'/v1/catalog/years','GET'),'catalog')
  self.assertEqual(s.request_policy(s.ORIGIN+'/v1/catalog/images/opaque','GET'),'real')
  for origin in ['https://external.invalid','http://localhost:3042','http://127.0.0.1:3041','http://127.0.0.1:3042@external.invalid']:
   self.assertEqual(s.request_policy(origin+'/v1/catalog/years','GET'),'abort')
 def test_trace_rejects_any_mocked_catalog_or_outbound_request(self):
  self.assertEqual(s.trace_errors(['/auth/session'],[],[]),[])
  self.assertTrue(s.trace_errors(['/auth/session','/v1/catalog/years'],[],[]))
  self.assertTrue(s.trace_errors(['/auth/session'],['external'],[]))
  self.assertTrue(s.trace_errors(['/auth/session'],[],['console']))
 @unittest.skipUnless(s.NODE.is_file(),'Node optional offline policy probe')
 def test_actual_node_policy_matches_boundary_cases(self):
  cases=[(s.ORIGIN+'/auth/session','GET'),(s.ORIGIN+'/auth/session?x=1','GET'),(s.ORIGIN+'/auth/session','POST'),(s.ORIGIN+'/v1/catalog/years','GET'),(s.ORIGIN+'/v1/catalog/years/2026/makes/owned/models/training/configurations?region=US','GET'),(s.ORIGIN+'/v1/catalog/images/opaque','GET'),(s.ORIGIN+'/v1/catalog/arbitrary','GET'),('https://external.invalid/workshop/','GET')]
  denials=[(s.ORIGIN+'/v1/workshop/quote',503,True),(s.ORIGIN+'/auth/session',401,False),(s.ORIGIN+'/auth/session',401,True),(s.ORIGIN+'/v1/catalog/years',503,True)]
  actual=s.node_run({'action':'policy','cases':cases,'denials':denials},5)
  self.assertEqual(actual['policies'],[s.request_policy(*case) for case in cases])
  self.assertEqual(actual['denials'],[s.expected_http_denial(*case) for case in denials])
 def test_expected_http_denials_are_exact_and_not_javascript_errors(self):
  self.assertFalse(s.expected_http_denial(s.ORIGIN+'/v1/workshop/quote?configuration_id=owned&region=US',503,True))
  self.assertTrue(s.expected_http_denial(s.ORIGIN+'/auth/session',401,False))
  self.assertFalse(s.expected_http_denial(s.ORIGIN+'/auth/session',401,True))
  for url,status in [(s.ORIGIN+'/v1/catalog/years',503),(s.ORIGIN+'/v1/workshop/quote',500),('https://external.invalid/v1/workshop/quote',503)]:
   self.assertFalse(s.expected_http_denial(url,status,True))
 def test_unsupported_catalog_routes_receive_no_bearer(self):
  for path in ['/v1/catalog/arbitrary','/v1/catalog/vehicles/x/source','/v1/catalog/years/2026/makes/a/models/b/refresh']:
   self.assertEqual(s.request_policy(s.ORIGIN+path,'GET'),'abort')
 def test_commerce_disabled_has_no_quote_or_prepare_authority(self):
  for path,method in [('/v1/workshop/quote','GET'),('/v1/workshop/quote?configuration_id=owned','GET'),('/v1/catalog/vehicles/a/articles/b/prepare','POST')]:
   self.assertEqual(s.request_policy(s.ORIGIN+path,method),'abort')
 @unittest.skipUnless(s.NODE.is_file(),'Node optional offline validation probe')
 def test_real_config_must_precede_simulation(self):
  cases=[({'mode':'local'},{'enabled':False},True),({'mode':'firebase'},{'enabled':False},False),({'mode':'local'},{'enabled':True},False),({}, {'enabled':False},False),({'mode':'local'},{},False)]
  result=s.node_run({'action':'validate','configs':[[a,b] for a,b,_ in cases],'presentations':[]},5)
  self.assertEqual(result['configs'],[ok for _,_,ok in cases])
 @unittest.skipUnless(s.NODE.is_file(),'Node optional offline validation probe')
 def test_original_body_once_before_headings_and_instructions(self):
  f={'body':'Original authored intro.','steps':[{'heading':'First','instructions':['Do first.']},{'heading':'Second','instructions':['Do second.']}]}
  good='Original authored intro.\nFirst\nDo first.\nSecond\nDo second.'
  bad=[good.replace(f['body'],''),good+'\n'+f['body'],good.replace('First\nDo first.','Do first.\nFirst'),good.replace('Original authored intro.\n','')+'\nOriginal authored intro.']
  result=s.node_run({'action':'validate','configs':[],'presentations':[[good,f]]+[[text,f] for text in bad]},5)
  self.assertEqual(result['presentations'],[True]+[False]*len(bad))
if __name__=='__main__':unittest.main()
