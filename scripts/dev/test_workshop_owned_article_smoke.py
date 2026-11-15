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
 @unittest.skipUnless(s.NODE.is_file(),'Node optional offline diagnostics probe')
 def test_failure_diagnostics_keep_safe_stage_code_and_counts_only(self):
  cases=[{'code':'display_body_once_and_step_order','stage':'desktop_detail','requests':17,'route_statuses':[{'category':'catalog','status':200,'count':4}]},{'code':'secret https://external.invalid','stage':'unsafe/private/path','requests':999999,'route_statuses':[{'category':'https://external.invalid','status':999,'count':999999}]}]
  actual=s.node_run({'action':'policy','cases':[],'failure_policy':True,'failures':cases},5)
  safe,unsafe=actual['failures'];self.assertEqual(safe['code'],'display_body_once_and_step_order');self.assertEqual(safe['stage'],'desktop_detail');self.assertEqual(safe['counters']['requests'],17)
  self.assertEqual(unsafe['code'],'browser_runtime');self.assertEqual(unsafe['stage'],'unknown');self.assertEqual(unsafe['route_statuses'],[])
  self.assertNotIn('external.invalid',str(unsafe));self.assertLessEqual(unsafe['counters']['requests'],221)
 @unittest.skipUnless(s.NODE.is_file(),'Node optional offline diagnostics probe')
 def test_failure_screenshot_error_preserves_primary_failure(self):
  result=s.node_run({'action':'policy','cases':[],'failure_policy':True,'failures':[{'code':'display_body_once_and_step_order','stage':'mobile_detail','requests':9}],'screenshot_failure':True},5)
  self.assertEqual(result['failures'][0]['code'],'display_body_once_and_step_order');self.assertTrue(result['failures'][0]['partial_screenshot']['attempted']);self.assertFalse(result['failures'][0]['partial_screenshot']['saved'])
 def test_private_failure_receipt_rejects_unbounded_or_unknown_fields(self):
  import tempfile,json
  safe={'ok':False,'error':'owned_browser_failed_preserve_state','code':'browser_runtime','stage':'launch','counters':{'requests':0},'route_statuses':[],'partial_screenshot':{'attempted':False,'saved':False}}
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'failure.json';s.write_failure_receipt(path,safe)
   self.assertEqual(path.stat().st_mode&0o777,0o600);self.assertEqual(json.loads(path.read_text()),safe)
   for bad in [{**safe,'url':'https://external.invalid'},{**safe,'code':'secret token value'},{**safe,'counters':{'requests':222}},{**safe,'route_statuses':[{'category':'catalog','status':999,'count':1}]}]:
    with self.assertRaises(ValueError):s.write_failure_receipt(Path(directory)/'rejected.json',bad)
 @unittest.skipUnless(s.NODE.is_file(),'Node optional offline action probe')
 def test_unknown_action_fails_before_browser_or_application_request(self):
  with self.assertRaises(s.BrowserFailure) as caught:s.node_run({'action':'unknown'},5)
  self.assertEqual(caught.exception.receipt['code'],'unsupported_action');self.assertEqual(caught.exception.receipt['stage'],'input');self.assertEqual(caught.exception.receipt['counters']['requests'],0);self.assertFalse(caught.exception.receipt['partial_screenshot']['attempted'])
class RealPNGTests(unittest.TestCase):
 @unittest.skipUnless(s.NODE.is_file(),'Node offline response validation')
 def test_png_response_requires_exact_200_mime_hash_and_151_bytes(self):
  fixture={'image':{'sha256':'c'*64}}
  good={'kind':'image','status':200,'bytes':151,'mime':'image/png','sha256':'c'*64}
  bad=[{**good,'status':404},{**good,'bytes':150},{**good,'mime':'text/html'},{**good,'sha256':'d'*64}]
  result=s.node_run({'action':'validate','configs':[],'presentations':[],'pngs':[[x,fixture] for x in [good,*bad]]},5)
  self.assertEqual(result.get('pngs'),[True,False,False,False,False])
class ThirdAttemptGuardTests(unittest.TestCase):
 def test_reserve_is_private_exclusive_and_preserves_old_receipts(self):
  import tempfile,json
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);old=root/'browser-failure-diagnostics.json';old.write_text('old failure')
   output=s.reserve_attempt(root,'a'*64,'b'*64)
   self.assertEqual(output.name,'browser-image-contract-v1');self.assertEqual(output.stat().st_mode&0o777,0o700)
   marker=root/s.ATTEMPT_NAME;self.assertEqual(marker.stat().st_mode&0o777,0o600)
   self.assertEqual(json.loads(marker.read_text())['manifest_sha256'],'a'*64)
   with self.assertRaises(FileExistsError):s.reserve_attempt(root,'a'*64,'b'*64)
   self.assertEqual(old.read_text(),'old failure')
 def test_existing_output_or_result_fails_before_dispatch_marker(self):
  import tempfile
  for name in ('browser-image-contract-v1','browser-failure-image-contract-v1.json','browser-acceptance-image-contract-v1.json'):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as directory:
    root=Path(directory);(root/name).write_text('preserved')
    with self.assertRaises(FileExistsError):s.reserve_attempt(root,'a'*64,'b'*64)
    self.assertFalse((root/s.ATTEMPT_NAME).exists());self.assertEqual((root/name).read_text(),'preserved')
 def test_symlink_marker_cannot_overwrite_target(self):
  import tempfile
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);target=root/'target';target.write_text('preserved');(root/s.ATTEMPT_NAME).symlink_to(target)
   with self.assertRaises(FileExistsError):s.reserve_attempt(root,'a'*64,'b'*64)
   self.assertEqual(target.read_text(),'preserved')
if __name__=='__main__':unittest.main()
