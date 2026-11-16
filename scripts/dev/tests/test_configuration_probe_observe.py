import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/'configuration_probe_observe.py'
spec=importlib.util.spec_from_file_location('observer',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
S='a'*16
BASE=f'catalog configuration diagnostic scope_hash={S} provider=banktwo stage=provider_resolution outcome=failed error_type=SourceConnectorError row_count=-1'
def log(text):return ('2026-11-15T04:00:00.123456789Z '+text+'\n').encode()
class Tests(unittest.TestCase):
 def test_only_fixed_fields_retained(self):
  value=m.safe_diagnostics(log('SENTINEL_SECRET https://secret')+log(BASE),S)
  self.assertEqual(len(value['events']),1);self.assertNotIn('SENTINEL_SECRET',str(value));self.assertEqual(value['events'][0]['provider'],'banktwo')
 def test_other_scope_and_unknown_error_rejected(self):
  raw=log(BASE.replace(S,'b'*16))+log(BASE.replace('SourceConnectorError','SECRET_TYPE'))
  value=m.safe_diagnostics(raw,S);self.assertEqual(value['events'],[]);self.assertEqual(value['rejected_rows'],1)
 def test_persistence_stage_and_local_stop_truth(self):
  text=BASE.replace('provider_resolution','coverage_persistence').replace('failed','incomplete').replace('SourceConnectorError','_ConfigurationHydrationStopped')
  event=m.safe_diagnostics(log(text),S)['events'][0];self.assertEqual(event['stage'],'coverage_persistence');self.assertEqual(event['error_type'],'_ConfigurationHydrationStopped')
 def test_warning_prefix_supported(self):
  self.assertEqual(len(m.safe_diagnostics(log('WARNING:autodata_ingestion.catalog_service:'+BASE),S)['events']),1)
 def test_unframed_and_out_of_range_never_return_payload(self):
  value=m.safe_diagnostics((BASE+' SENTINEL_SECRET\n').encode()+log(BASE.replace('row_count=-1','row_count=-999')),S)
  self.assertEqual(value['events'],[]);self.assertNotIn('SENTINEL_SECRET',str(value))
if __name__=='__main__':unittest.main()
