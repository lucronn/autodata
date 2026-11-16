import importlib.util,io,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
spec=importlib.util.spec_from_file_location('anon',Path(__file__).with_name('workshop_public_anonymous.py'));a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class AdmissionTests(unittest.TestCase):
 def test_exact_connect_authority_and_header_bound(self):
  self.assertTrue(a.valid_connect(b'CONNECT autodata.cars.tk:443 HTTP/1.1\r\n',[b'Host: autodata.cars.tk:443\r\n']))
  for line in [b'CONNECT google.com:443 HTTP/1.1\r\n',b'CONNECT autodata.cars.tk:80 HTTP/1.1\r\n',b'GET / HTTP/1.1\r\n',b'CONNECT user@autodata.cars.tk:443 HTTP/1.1\r\n']:
   self.assertFalse(a.valid_connect(line,[]))
  self.assertFalse(a.valid_connect(b'CONNECT autodata.cars.tk:443 HTTP/1.1\r\n',[b'Authorization: x\r\n']))
 def test_capacity_home_tmpfs_burst_and_memory(self):
  good={'home':5900000000,'root':2900000000,'docker':990000000,'offload':3000000000,'tmp':6000000000,'memory':2000000000,'growth':0,'tmp_growth':0,'artifact':0}
  self.assertEqual(a.capacity_errors(good),[])
  for k,v in [('home',5570035712),('growth',33554432),('tmp_growth',100663296),('memory',1073741823),('artifact',4194305),('docker',813694976),('tmp',536870911)]:self.assertTrue(a.capacity_errors({**good,k:v}),k)
 def test_one_use_marker_and_profile_refusal(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'marker';a.reserve_marker(p,b'pinned');self.assertEqual(p.stat().st_mode&0o777,0o600)
   with self.assertRaises(FileExistsError):a.reserve_marker(p,b'again')
 def test_owned_pid_reuse_not_killed(self):
  with patch.object(a,'proc_identity',return_value=('9','999')),patch.object(a.os,'kill') as kill:a.kill_owned({123:('8','999')});kill.assert_not_called()
 def test_default_check_does_not_dispatch(self):
  with patch.object(a,'load',return_value={}),patch.object(a,'runtime_guard'),patch.object(a,'capacity',return_value={}),patch.object(a.subprocess,'Popen',side_effect=AssertionError('dispatch')) as pop,patch.object(a.socket,'create_connection',side_effect=AssertionError('network')) as connect:
   self.assertEqual(a.main(['--reviewed-seal','a'*64]),0);pop.assert_not_called();connect.assert_not_called()
 def test_dns_rejects_non_global(self):
  for ip in ['127.0.0.1','10.0.0.1','169.254.1.1','0.0.0.0','224.0.0.1']:
   with patch.object(a.socket,'getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443))]):
    with self.assertRaises(a.Refused):a.public_addresses()
 def test_proxy_rejects_before_connect(self):
  state=a.ProxyState(['1.1.1.1']);handler=object.__new__(a.Tunnel);handler.rfile=io.BytesIO(b'CONNECT evil.example:443 HTTP/1.1\r\nHost: evil.example:443\r\n\r\n');handler.wfile=io.BytesIO();handler.server=type('S',(),{'state':state})();handler.connection=Mock()
  with patch.object(a.socket,'create_connection') as connect:handler.handle();connect.assert_not_called()
  self.assertEqual(state.denied,1)

 def test_proxy_concurrency_and_total_caps(self):
  s=a.ProxyState(['1.1.1.1'])
  for _ in range(16):self.assertTrue(s.enter())
  self.assertFalse(s.enter());self.assertTrue(s.failed)
  t=a.ProxyState(['1.1.1.1']);t.total=128;self.assertFalse(t.enter())
  self.assertFalse(a.ProxyState(['1.1.1.1']).account(33554433))

 def test_consumed_marker_survives_guard_failure_and_prevents_second_attempt(self):
  with tempfile.TemporaryDirectory() as d,patch.object(a,'ROOT',Path(d)),patch.object(a,'capacity',return_value={}),patch.object(a,'runtime_guard',side_effect=a.Refused('changed')),patch.object(a,'descendants',return_value={}),patch.object(a,'kill_owned') as killed,patch.object(a.socket,'create_connection') as connect,patch.object(a.subprocess,'Popen') as pop:
   self.assertEqual(a.run_once({},'a'*64),1);self.assertTrue((Path(d)/'browser-attempted').exists());self.assertTrue((Path(d)/'OUTCOME.json').exists())
   with self.assertRaises(FileExistsError):a.run_once({},'a'*64)
   connect.assert_not_called();pop.assert_not_called()
 def test_owned_identity_can_be_killed_only_on_exact_identity(self):
  with patch.object(a,'proc_identity',return_value=('1000','42')),patch.object(a.os,'kill') as kill:a.kill_owned({123:('1000','42')});kill.assert_called_once_with(123,a.signal.SIGKILL)
 def test_proxy_duplicate_host_and_unsupported_headers_denied(self):
  line=b'CONNECT autodata.cars.tk:443 HTTP/1.1\r\n';host=b'Host: autodata.cars.tk:443\r\n'
  self.assertFalse(a.valid_connect(line,[host,host]));self.assertFalse(a.valid_connect(line,[host,b'Proxy-Authorization: secret\r\n']))

 def test_control_and_dependency_mutations_fail_lifetime_guard(self):
  with tempfile.TemporaryDirectory() as d,patch.object(a,'ROOT',Path(d)):
   root=Path(d);(root/'PACKAGE-SEAL.json').write_text('sealed');(root/'helper').write_text('original')
   m={'_reviewed_seal':a.sha(root/'PACKAGE-SEAL.json'),'_sealed_files':{'helper':'0'*64},'_dependency_guard':{}}
   with self.assertRaises(a.Refused):a.runtime_guard(m)
 def test_upstream_failure_diagnostics_are_safe_and_specific(self):
  state=a.ProxyState(['1.1.1.1']);handler=object.__new__(a.Tunnel);handler.rfile=io.BytesIO(b'CONNECT autodata.cars.tk:443 HTTP/1.1\r\nHost: autodata.cars.tk:443\r\n\r\n');handler.wfile=io.BytesIO();handler.server=type('S',(),{'state':state})();handler.connection=Mock()
  with patch.object(a.socket,'create_connection',side_effect=OSError('do not expose')) as connect:handler.handle();connect.assert_called_once()
  self.assertEqual(state.upstream_attempted,1);self.assertEqual(state.upstream_connected,0);self.assertEqual(state.upstream_failed,1)
