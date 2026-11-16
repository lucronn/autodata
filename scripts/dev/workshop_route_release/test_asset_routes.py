import unittest,tempfile,pathlib,json,hashlib
from unittest.mock import patch
import fixture_guard as f
class Response:
 def __init__(self,status,body,location=None):self.status=status;self.body=body;self.location=location
 def read(self,limit):return self.body[:limit]
 def getheader(self,name):return self.location if name=='Location' else None
class Connection:
 def __init__(self,response):self.response=response;self.requests=[];self.closed=False
 def request(self,method,path):self.requests.append((method,path))
 def getresponse(self):return self.response
 def close(self):self.closed=True
class AssetRouteTests(unittest.TestCase):
 def setup(self,d,response):
  r=pathlib.Path(d);self.connection=Connection(response)
  return patch.multiple(f,R=r),patch.object(f.http.client,'HTTPConnection',return_value=self.connection)
 def test_index_actual_content_uses_canonical_root_and_hashes(self):
  body=b'actual candidate HTML';item={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
  with tempfile.TemporaryDirectory() as d:
   a,b=self.setup(d,Response(200,body))
   with a,b:
    record=f.verify_asset('index.html',item)
    self.assertEqual(record['path'],'/workshop/');self.assertEqual(self.connection.requests,[('GET','/workshop/')]);self.assertTrue(self.connection.closed)
    self.assertEqual(json.loads((pathlib.Path(d)/'LOCAL-ASSET-REQUESTS.ndjson').read_text())['sha256'],item['sha256'])
 def test_all15_routes_and_exact_hashes(self):
  assets=json.loads((f.PKG/'asset-manifest.json').read_text());self.assertEqual(len(assets),15)
  for name in assets:
   self.assertEqual(f.asset_path(name),'/workshop/' if name=='index.html' else '/workshop/'+name)
  self.assertEqual(list(assets).index('index.html'),12)
 def test_index_redirect_exact301_relative_target_no_autofollow(self):
  with tempfile.TemporaryDirectory() as d:
   a,b=self.setup(d,Response(301,b'<a href="./">Moved</a>','./'))
   with a,b:
    _,r=f.fetch('/workshop/index.html',expected_status=301,expected_location='./')
    self.assertEqual(r['status'],301);self.assertEqual(self.connection.requests,[('GET','/workshop/index.html')])
 def test_wrong_status_location_and_oversize_record_before_refusal(self):
  cases=[(Response(302,b'x','./'),301,'./',10),(Response(301,b'x','https://example.test'),301,'./',10),(Response(301,b'x','./'),200,None,10),(Response(200,b'xxxx'),200,None,3)]
  for response,status,location,cap in cases:
   with tempfile.TemporaryDirectory() as d:
    a,b=self.setup(d,response)
    with a,b,self.assertRaises(AssertionError):f.fetch('/workshop/index.html',cap=cap,expected_status=status,expected_location=location)
    self.assertTrue((pathlib.Path(d)/'LOCAL-ASSET-REQUESTS.ndjson').exists());self.assertTrue(self.connection.closed)
 def test_200_redirect_header_and_bad_hash_refuse(self):
  with tempfile.TemporaryDirectory() as d:
   a,b=self.setup(d,Response(200,b'x','https://example.test'))
   with a,b,self.assertRaisesRegex(AssertionError,'location'):f.fetch('/workshop/')
  with tempfile.TemporaryDirectory() as d:
   a,b=self.setup(d,Response(200,b'x'))
   with a,b,self.assertRaisesRegex(AssertionError,'hash_or_size'):f.verify_asset('index.html',{'sha256':'0'*64,'bytes':1})
 def test_unknown_or_external_path_never_dispatches(self):
  with patch.object(f.http.client,'HTTPConnection',side_effect=AssertionError('must not construct connection')):
   for path in ['https://accounts.google.com/','/workshop/index.html?x=1','/workshop/unknown.mjs','/v1/catalog/years']:
    with self.assertRaisesRegex(AssertionError,'unexpected_local_asset_path'):f.fetch(path)
