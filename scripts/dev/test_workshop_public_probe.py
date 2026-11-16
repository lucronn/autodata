import importlib.util,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('probe',Path(__file__).with_name('workshop_public_probe.py'));p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class ProbeTests(unittest.TestCase):
 def test_canonical_index_and_all_fifteen_assets(self):
  assets={n:{'sha256':'a'*64,'bytes':1} for n in p.ASSETS}
  routes=p.routes({'assets':assets,'baseline_assets':assets},'candidate');self.assertEqual(len([x for x in routes if x['kind']=='asset']),30)
  self.assertFalse(any('/index.html' in x['url'] for x in routes));self.assertTrue(any(x['url']=='http://127.0.0.1:18080/workshop/' and x['kind']=='asset' for x in routes))
 def test_fixed_route_refuses_protected_write_or_external(self):
  for url in ['https://evil.invalid/healthz','https://autodata.cars.tk/v1/catalog/years','https://autodata.cars.tk/auth/session','https://autodata.cars.tk/workshop/app.mjs?x=1']:
   with self.assertRaises(p.Refused):p.allowed(url)
 def test_exact_dto_and_redirect(self):
  self.assertTrue(p.validate({'kind':'health','status':200},200,None,b'{"status":"ok"}'))
  self.assertFalse(p.validate({'kind':'health','status':200},200,None,b'{"status":"different"}'))
  x={'kind':'redirect','status':308,'location':'/workshop'};self.assertTrue(p.validate(x,308,'/workshop',b''));self.assertFalse(p.validate(x,308,'https://evil.invalid',b''))
 def test_no_dispatch_route_inventory(self):
  with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('no_dispatch')) as call:
   p.routes({'assets':{n:{'sha256':'a'*64,'bytes':1} for n in p.ASSETS},'baseline_assets':{}},'candidate');call.assert_not_called()
class StrictProbeTests(unittest.TestCase):
 def test_inventory_missing_and_added_assets_refuse(self):
  for assets in [{},{'index.html':{'sha256':'a'*64,'bytes':1}}]:
   with self.assertRaises(p.Refused):p.routes({'assets':assets},'candidate')
 def test_ready_and_disabled_commerce_exact(self):
  self.assertTrue(p.validate({'kind':'ready','status':200},200,None,b'{"database":"ready","nats":"ready","object_storage":"ready"}'))
  self.assertFalse(p.validate({'kind':'ready','status':200},200,None,b'{"database":"ready"}'))
  self.assertFalse(p.validate({'kind':'purchase','status':200},200,None,b'{"enabled":true}'))
 def test_asset_hash_bytes_and_oversize_refused(self):
  import hashlib
  x={'kind':'asset','status':200,'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}
  self.assertTrue(p.validate(x,200,None,b'x'));self.assertFalse(p.validate(x,200,None,b'y'));self.assertFalse(p.validate(x,200,None,b'x'*1048577))
 def test_proxy_disabled_and_redirect_handler_never_follows(self):
  self.assertIsNone(p.NoRedirect().redirect_request(None,None,301,None,None,None))
  import io
  class Response(io.BytesIO):
   status=200;headers={}
  with patch.object(p.urllib.request,'ProxyHandler',wraps=p.urllib.request.ProxyHandler) as proxy,patch.object(p.urllib.request,'build_opener') as opener:
   opener.return_value.open.return_value=Response(b'{"status":"ok"}')
   self.assertTrue(p.fetch({'url':'https://autodata.cars.tk/healthz','kind':'health','status':200},p.time.monotonic()+5)['passed']);proxy.assert_called_once_with({})
 def test_wall_deadline_covers_slow_or_stuck_response(self):
  import time
  old=p.signal.getsignal(p.signal.SIGALRM)
  with patch.object(p,'routes',return_value=[{}]),patch.object(p,'fetch',side_effect=p.Refused('probe_deadline')):
   self.assertFalse(p.run({},'candidate')['passed'])
  self.assertEqual(p.signal.getsignal(p.signal.SIGALRM),old);self.assertEqual(p.signal.getitimer(p.signal.ITIMER_REAL),(0.0,0.0))
if __name__=='__main__':unittest.main()
