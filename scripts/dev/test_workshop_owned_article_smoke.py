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
   self.assertEqual(output.name,'browser-image-contract-v2');self.assertEqual(output.stat().st_mode&0o777,0o700)
   marker=root/s.ATTEMPT_NAME;self.assertEqual(marker.stat().st_mode&0o777,0o600)
   self.assertEqual(json.loads(marker.read_text())['manifest_sha256'],'a'*64)
   with self.assertRaises(FileExistsError):s.reserve_attempt(root,'a'*64,'b'*64)
   self.assertEqual(old.read_text(),'old failure')
 def test_existing_output_or_result_fails_before_dispatch_marker(self):
  import tempfile
  for name in ('browser-image-contract-v2','browser-failure-image-contract-v2.json','browser-acceptance-image-contract-v2.json'):
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
class TmpfsOperationalTests(unittest.TestCase):
 def test_physical_and_tmpfs_margins_cover_observed_burst(self):
  policy={'home_free_baseline':10000000000,'home_guard_growth':32*1024**2,'home_growth_cap':64*1024**2,'home_absolute_floor':1,'docker_absolute_floor':1,'tmp_free_baseline':2000000000,'tmp_guard_growth':96*1024**2,'tmp_growth_cap':128*1024**2,'min_available_memory':1024**3,'min_inodes':1000,'entry_home_floor':1,'tmp_entry_floor':512*1024**2}
  obs={'home_free':policy['home_free_baseline'],'docker_free':2000000000,'tmp_free':policy['tmp_free_baseline'],'memory_available':2*1024**3,'inodes':10000}
  self.assertEqual(s.capacity_errors(obs,policy),[])
  at_guard={**obs,'home_free':obs['home_free']-32*1024**2}
  self.assertIn('home_growth_guard',s.capacity_errors(at_guard,policy));self.assertLess(32*1024**2+10047488,policy['home_growth_cap'])
  self.assertIn('tmp_growth_guard',s.capacity_errors({**obs,'tmp_free':obs['tmp_free']-96*1024**2},policy))
  self.assertIn('memory_guard',s.capacity_errors({**obs,'memory_available':1},policy))
 def test_tmpfs_and_socket_boundary_rejects_before_dispatch(self):
  from unittest.mock import patch
  with patch('subprocess.Popen',side_effect=AssertionError('no_dispatch')) as dispatch:
   self.assertEqual(s.tmpfs_errors('tmpfs',46,66315,81),[])
   self.assertTrue(s.tmpfs_errors('ext4',66315,66315,81));self.assertTrue(s.tmpfs_errors('tmpfs',46,66315,108))
   self.assertEqual(dispatch.call_count,0)
 def test_changed_harness_hash_fails_closed(self):
  self.assertEqual(s.identity_errors({'harness_sha256':'a'*64,'helper_sha256':{'f':'b'*64}},{'harness_sha256':'a'*64,'helper_sha256':{'f':'b'*64}}),[])
  self.assertTrue(s.identity_errors({'harness_sha256':'a'*64,'helper_sha256':{'f':'b'*64}},{'harness_sha256':'c'*64,'helper_sha256':{'f':'b'*64}}))
  self.assertTrue(s.identity_errors({'harness_sha256':'a'*64,'helper_sha256':{'f':'b'*64}},{'harness_sha256':'a'*64,'helper_sha256':{'f':'c'*64}}))
 def test_physical_helper_import_cannot_use_changed_sibling(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  import sys
  with patch.dict(sys.modules,{'workshop_owned_article_forwarder':SimpleNamespace(__file__='/untrusted/sibling.py')}),patch('subprocess.Popen',side_effect=AssertionError('no_dispatch')) as dispatch:
   with self.assertRaises(ValueError):s.runtime_modules()
   self.assertEqual(dispatch.call_count,0)
 @unittest.skipUnless(s.NODE.is_file(),'Node offline journal fixture')
 def test_actual_journal_schema_bounds_and_preserved_prefix(self):
  good={'stage':'desktop_detail','category':'catalog','method':'GET','status':200,'count':4}
  bad=[{**good,'url':'https://secret.invalid'},{**good,'status':999},{**good,'count':221},{**good,'stage':'secret/path'}]
  result=s.node_run({'action':'policy','cases':[],'journal_test':[good,*bad]},5)
  self.assertEqual(result['journal_valid'],[True,False,False,False,False]);self.assertTrue(result['journal_prefix_preserved']);self.assertTrue(result['journal_bound_rejected'])
class ActualOperationalBoundaryTests(unittest.TestCase):
 def test_actual_temp_context_is_private_tmpfs_and_rejects_low_entry_before_dispatch(self):
  from unittest.mock import patch
  with patch('subprocess.Popen',side_effect=AssertionError('no_dispatch')) as dispatch:
   with s.browser_environment() as env:
    root=Path(env['HOME']);self.assertEqual(root.parent,Path('/tmp'));self.assertEqual(root.stat().st_mode&0o777,0o700)
    self.assertEqual(env['TMPDIR'],env['HOME']);self.assertTrue(Path(env['XDG_CACHE_HOME']).is_relative_to(root));self.assertNotEqual(root.stat().st_dev,s.RUNTIME_ROOT.stat().st_dev)
   self.assertFalse(root.exists())
   with patch.object(s,'capacity_errors',return_value=['memory_guard']):
    with self.assertRaises(ValueError):
     with s.browser_environment({'owned':'test'}):self.fail('entry_must_reject')
   self.assertEqual(dispatch.call_count,0)
 def test_actual_operational_guard_rejects_changed_owned_harness_before_dispatch(self):
  import tempfile,json,hashlib
  from unittest.mock import patch
  with tempfile.TemporaryDirectory(dir='/tmp') as directory:
   base=Path(directory);runtime=base/'runtime';physical=runtime/'source/scripts/dev';physical.mkdir(parents=True);private=runtime/'private-config';private.mkdir();(runtime/'bin').mkdir()
   harness=base/'runner.py';harness.write_text('# owned original');archive=runtime/'source.tar';archive.write_bytes(b'owned archive');binary=runtime/'bin/autodata-api';binary.write_bytes(b'owned binary');accepted=private/'accepted-state.json';accepted.write_text('{}')
   sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
   helpers={}
   for name in s.HELPERS:
    p=physical/(name+'.py');p.write_text('# owned helper');helpers[name]=sha(p)
   manifest=private/'manifest.json';manifest.write_text(json.dumps({'source_sha':'668d4c86f4097b9d2c7880dedf2e0fccc8079da6','source_tree':'1'*40,'config_sha256':'2'*64}))
   receipt={k:'' for k in ('version','gate_sha','harness_source_sha','harness_tree','harness_sha256','test_sha256','runtime_source_sha','runtime_tree','runtime_manifest_sha256','runtime_archive_sha256','runtime_binary_sha256','runtime_config_sha256','runtime_accepted_sha256','helper_sha256','capacity','namespace','dependency_pins')}
   receipt.update(version=1,namespace='image-contract-v2',harness_sha256=sha(harness),helper_sha256=helpers,runtime_source_sha='668d4c86f4097b9d2c7880dedf2e0fccc8079da6',runtime_tree='1'*40,runtime_config_sha256='2'*64,runtime_manifest_sha256=sha(manifest),runtime_archive_sha256=sha(archive),runtime_binary_sha256=sha(binary),runtime_accepted_sha256=sha(accepted),capacity={'home_growth_cap':67108864,'home_guard_growth':33554432,'tmp_growth_cap':134217728,'tmp_guard_growth':100663296})
   seal=base/'seal.json';seal.write_text(json.dumps(receipt));seal.chmod(0o600)
   with patch.object(s,'RUNTIME_ROOT',runtime),patch.object(s,'OPERATIONAL_SEAL',seal),patch.object(s,'__file__',str(harness)),patch('subprocess.Popen',side_effect=AssertionError('no_dispatch')) as dispatch:
    self.assertEqual(s.operational_guard()['harness_sha256'],sha(harness));harness.write_text('# owned changed')
    with self.assertRaises(ValueError):s.operational_guard()
    self.assertEqual(dispatch.call_count,0)
if __name__=='__main__':unittest.main()
