"""Owned-fixture authority and freshness tests; no stores/providers."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('seed',Path(__file__).with_name('workshop_owned_article_seed.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class OwnedSeedTests(unittest.TestCase):
 def test_authored_fixture_and_png_are_hash_bound(self):
  fixture=s.load_fixture();self.assertEqual(fixture['ownership'],'authored-synthetic')
  self.assertEqual((fixture['image']['width'],fixture['image']['height']),(64,48))
  self.assertEqual(len(fixture['article']['steps']),2)
 def test_fixture_rejects_nonowned_content_or_altered_image(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for p in s.FIXTURES.iterdir():
    if p.is_file():(root/p.name).write_bytes(p.read_bytes())
   data=json.loads((root/'article.json').read_text());data['ownership']='supplier-unknown';(root/'article.json').write_text(json.dumps(data))
   with self.assertRaises(ValueError):s.load_fixture(root)
   data['ownership']='authored-synthetic';(root/'article.json').write_text(json.dumps(data));(root/'diagram.png').write_bytes(b'invalid')
   with self.assertRaises(ValueError):s.load_fixture(root)
 def test_exact_local_target_only(self):
  self.assertEqual(s.target_errors(s.TARGET),[])
  for key,value in [('db_host','127.0.0.1'),('database','autodata'),('s3_endpoint','external.invalid'),('commerce_mode','test'),('env','production')]:
   c={**s.TARGET,key:value};self.assertTrue(s.target_errors(c))
 def test_first_seed_requires_all_operational_rows_and_objects_empty(self):
  counts={key:0 for key in s.COUNT_TABLES};counts['dataset_products']=1
  self.assertEqual(s.seed_preconditions(counts,0,None,'a'*64),[])
  for key in s.COUNT_TABLES:
   if key=='dataset_products':continue
   changed={**counts,key:1};self.assertTrue(s.seed_preconditions(changed,0,None,'a'*64))
  self.assertTrue(s.seed_preconditions(counts,1,None,'a'*64))
 def test_repeat_requires_exact_fixture_marker_and_counts(self):
  counts={key:(1 if key in s.OWNED_TABLES or key=='dataset_products' else 0) for key in s.COUNT_TABLES}
  marker={'fixture_sha256':'a'*64}
  self.assertEqual(s.seed_preconditions(counts,2,marker,'a'*64),[])
  self.assertTrue(s.seed_preconditions(counts,2,marker,'b'*64))
  self.assertTrue(s.seed_preconditions({**counts,'entitlements':1},2,marker,'a'*64))
 def test_exact_six_rows_and_truthful_source_object_references(self):
  f=s.load_fixture();rows=s.row_values(f,'a'*64)
  self.assertEqual(set(rows),set(s.OWNED_TABLES))
  self.assertEqual(rows['source_snapshots']['object_key'],s.SOURCE_KEY)
  self.assertEqual(rows['extraction_evidence']['artifact_key'],s.SOURCE_KEY)
  self.assertEqual(rows['catalog_articles']['source_snapshot_id'],f['ids']['snapshot'])
  self.assertEqual(rows['catalog_articles']['vehicle_configuration_id'],f['ids']['configuration'])
  images=json.loads(rows['catalog_articles']['images'])
  self.assertEqual(len(images),1);self.assertEqual(images[0]['storage_key'],'procedure-images/'+f['image']['sha256'])
  stored_steps=json.loads(rows['catalog_articles']['steps'])
  self.assertEqual(stored_steps[0]['image_ids'],[f['image']['id']])
  self.assertNotIn('image_ids',f['article']['steps'][0])
  self.assertEqual(json.loads(rows['catalog_articles']['source_original']),f)
  self.assertTrue(set(s.OWNED_TABLES)<=set(s.COUNT_TABLES))
 def test_seed_inserts_no_customer_payment_or_grant(self):
  self.assertEqual(set(s.INSERT_TABLES),set(s.OWNED_TABLES))
  self.assertFalse(set(s.INSERT_TABLES)&set(s.COMMERCE_TABLES))
 def test_read_only_inspect_precedes_empty_auth_but_seed_requires_it(self):
  self.assertEqual(s.auth_gate_errors('inspect',None,'m','s',('binding',)),[])
  self.assertTrue(s.auth_gate_errors('seed',None,'m','s',('binding',)))
  auth={'manifest_sha256':'m','accepted_sha256':'s','binding':['binding'],'ready':True,'catalog_local_token':True,'missing_token_401':True,'wrong_role_403':True,'customer_session_401':True,'all_operational_rows_empty':True,'s3_objects_empty':True}
  self.assertEqual(s.auth_gate_errors('seed',auth,'m','s',('binding',)),[])
  self.assertTrue(s.auth_gate_errors('seed',{**auth,'catalog_local_token':False},'m','s',('binding',)))
  self.assertTrue(s.auth_gate_errors('unknown',auth,'m','s',('binding',)))
if __name__=='__main__':unittest.main()
