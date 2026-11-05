"""Independent synthetic byte fixtures for the inert merchant preparation lane."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import workshop_merchant_manifest as merchant

ROOT = Path(__file__).resolve().parents[2]
# Archived disabled, non-deployable test inputs copied verbatim from
# b6388596cf4419559fc6a8a5fbcd0b4fc33cc7cb: apps/api-go/main.go and
# apps/api-go/workshop/purchase-config.json. These are historical bindings,
# not evidence for the current server-owned purchase configuration route.
FIXTURES = ROOT/'scripts/dev/fixtures/workshop_merchant_manifest'
KINDS = ('terms', 'privacy', 'refund', 'contact')
BASELINE_SHA = 'edb1d6d182c5eeee6c33885e873bc5b44ac7a3eb4465d9e92af5d1bc60d4b45f'
AUTHORITIES = '''implementation implementation_dispatch provider runtime host host_execution docker network cloud dns capture profile_activation acceptance fixture_execution image_build_pull_install service_start payment account_mutation staging release merge deployment cutover secrets github_write code_approval ci_success merchant_enablement manifest_injection artifact_admission owner_approval stripe_test_acceptance live_sales'''.split()
EXTERNAL = ['independent_owner_approval', 'published_policy_byte_verification', 'approved_manifest_injection_rebuild', 'immutable_artifact_and_binary_binding', 'exact_running_image_served_byte_capture', 'authentic_stripe_test_enrollment_and_acceptance', 'explicit_operational_release_authorization']


def binding(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode('utf-8')


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.manifest = {'enabled': True, 'terms_version': 'workshop-v1', **{k+'_url': 'https://merchant.example/'+k for k in KINDS}, 'tax_notice': 'Synthetic final-price notice.\nNo extra collection. é'}
        self.policy_bytes = {k: ('Synthetic '+k+' snapshot.\n').encode() for k in KINDS}
        self.build = (ROOT/'apps/api-go/Dockerfile').read_bytes()
        self.embed = (FIXTURES/'historical-main.go.txt').read_bytes()
        self.approval = {'schema': 'workshop-merchant-preparation-v1', 'provenance': 'synthetic', 'owner_approval_ref': 'synthetic reference only', 'policy_revision': 'synthetic-revision-1', 'source': {'sha': '6949eb1b1a5b93c9b2eb0579328e24c697f6f331', 'tree': '47ec54b1896c83a39b6637a6ce944d3620414f4e'}, 'build_recipe': binding(self.build), 'embed_source': binding(self.embed), 'manifest': {**binding(encoded(self.manifest)), 'served_path': '/workshop/purchase-config.json', 'terms_version': 'workshop-v1'}, 'policies': {k: {'url': self.manifest[k+'_url'], **binding(self.policy_bytes[k])} for k in KINDS}, 'tax': {'notice_sha256': hashlib.sha256(self.manifest['tax_notice'].encode()).hexdigest(), 'notice_bytes': len(self.manifest['tax_notice'].encode()), 'final_price_treatment': 'owner_confirms_usd20_final_no_additional_tax_collection', 'owner_decision_ref': 'synthetic decision reference'}, 'product': {'id': 'workshop-configuration-v1', 'currency': 'USD', 'amount_minor': 2000, 'recurrence': 'one_time'}, 'enrollment': {'mode': 'stripe_test', 'account_id': 'acct_SYNTHETIC', 'price_id': 'price_SYNTHETIC'}}
        self.paths = {'manifest': self.dir/'manifest.json', 'approval': self.dir/'approval.json', 'policies': {k: self.dir/(k+'.txt') for k in KINDS}, 'build_recipe': self.dir/'Dockerfile', 'embed_source': self.dir/'main.go'}
        self.write()

    def write(self):
        self.paths['manifest'].write_bytes(encoded(self.manifest))
        self.paths['approval'].write_bytes(encoded(self.approval))
        for k in KINDS:
            self.paths['policies'][k].write_bytes(self.policy_bytes[k])
        self.paths['build_recipe'].write_bytes(self.build)
        self.paths['embed_source'].write_bytes(self.embed)

    def evaluate(self):
        result = merchant.evaluate_files(**self.paths)
        self.assertEqual(set(result), {'schema', 'status', 'provenance', 'manifest_sha256', 'manifest_bytes', 'baseline_disabled', 'reasons', 'missing_external_prerequisites', 'authorities', 'accepted_case_credit'})
        self.assertEqual(result['schema'], 'workshop-merchant-preparation-result-v1')
        self.assertEqual(result['authorities'], dict.fromkeys(AUTHORITIES, False))
        self.assertEqual(result['accepted_case_credit'], 0)
        self.assertEqual(result['missing_external_prerequisites'], EXTERNAL)
        self.assertEqual(result['reasons'], sorted(set(result['reasons'])))
        return result

    def blocked(self):
        self.assertEqual(self.evaluate()['status'], 'blocked')

    def rebind_manifest(self):
        self.approval['manifest'].update(binding(encoded(self.manifest)))
        self.write()

    def test_pinned_build_inputs(self):
        self.assertEqual(binding(self.build), {'sha256':'bd7a4d022e89c76432cd5b8e086166252303710cb8cb24a72b5eeff31fc52559','bytes':928})
        self.assertEqual(binding(self.embed), {'sha256':'6a6c78c4d84604ec4e626b49dc10e20603018e9db398c709073e689723801a77','bytes':30491})

    def test_current_embed_cannot_self_admit_historical_binding(self):
        current = (ROOT/'apps/api-go/main.go').read_bytes()
        self.assertNotEqual(binding(current), {'sha256': '6a6c78c4d84604ec4e626b49dc10e20603018e9db398c709073e689723801a77', 'bytes': 30491})
        self.paths['embed_source'].write_bytes(current)
        result = self.evaluate()
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('embed_source_binding_mismatch', result['reasons'])
        self.approval['embed_source'] = binding(current)
        self.paths['approval'].write_bytes(encoded(self.approval))
        result = self.evaluate()
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('embed_source_binding_mismatch', result['reasons'])

    def test_synthetic_prepared_is_consistency_only(self):
        result = self.evaluate()
        self.assertEqual(result['status'], 'prepared_offline')
        self.assertEqual(result['reasons'], [])
        self.assertEqual(result['provenance'], 'synthetic')
        self.assertEqual(result['manifest_sha256'], hashlib.sha256(encoded(self.manifest)).hexdigest())
        self.assertEqual(result['manifest_bytes'], len(encoded(self.manifest)))
        self.assertFalse(result['baseline_disabled'])
        self.assertEqual(result, self.evaluate())

    def test_owner_supplied_unverified_is_consistency_only(self):
        self.approval['provenance'] = 'owner_supplied_unverified'
        for k in KINDS:
            self.manifest[k+'_url'] = 'https://merchant.company/'+k
            self.approval['policies'][k]['url'] = self.manifest[k+'_url']
        self.rebind_manifest()
        self.assertEqual(self.evaluate()['status'], 'prepared_offline')

    def test_historical_exact_disabled_baseline_and_every_byte_mutation(self):
        raw = (FIXTURES/'historical-disabled-purchase-config.json').read_bytes()
        self.assertEqual(len(raw), 168)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), BASELINE_SHA)
        self.assertIs(json.loads(raw)['enabled'], False)
        self.paths['manifest'].write_bytes(raw)
        result = self.evaluate()
        self.assertTrue(result['baseline_disabled'])
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('merchant_inputs_pending', result['reasons'])
        self.assertNotIn('manifest_schema_invalid', result['reasons'])
        for index in range(len(raw)):
            with self.subTest(byte=index):
                changed = raw[:index]+bytes([raw[index] ^ 1])+raw[index+1:]
                self.paths['manifest'].write_bytes(changed)
                self.assertFalse(self.evaluate()['baseline_disabled'])

    def test_each_input_missing_symlink_directory(self):
        files = [self.paths[k] for k in ('manifest','approval','build_recipe','embed_source')]+list(self.paths['policies'].values())
        for path in files:
            raw = path.read_bytes()
            for mode in ('missing','symlink','directory'):
                with self.subTest(path=path.name, mode=mode):
                    path.unlink()
                    if mode == 'symlink': path.symlink_to(self.dir/'nonexistent')
                    if mode == 'directory': path.mkdir()
                    self.blocked()
                    if mode == 'directory': path.rmdir()
                    elif mode == 'symlink': path.unlink()
                    path.write_bytes(raw)

    def test_read_limits(self):
        for key, limit in [('manifest',65536),('approval',65536)]:
            with self.subTest(key=key):
                raw=self.paths[key].read_bytes(); padded=raw+b' '*(limit-len(raw))
                self.paths[key].write_bytes(padded)
                if key == 'manifest':
                    self.approval['manifest'].update(binding(padded)); self.paths['approval'].write_bytes(encoded(self.approval))
                self.assertEqual(self.evaluate()['status'], 'prepared_offline')
                self.paths[key].write_bytes(padded+b' '); self.blocked()
                self.paths[key].write_bytes(raw)
                self.approval['manifest'].update(binding(encoded(self.manifest))); self.write()
        for key, limit in [('build_recipe',65536),('embed_source',1048576)]:
            self.paths[key].write_bytes(b'x'*(limit+1)); self.blocked(); self.write()
        for count in (1048576,1048577):
            raw=b'x'*count; self.paths['policies']['terms'].write_bytes(raw)
            self.approval['policies']['terms'].update(binding(raw)); self.paths['approval'].write_bytes(encoded(self.approval))
            self.assertEqual(self.evaluate()['status'], 'prepared_offline' if count==1048576 else 'blocked')

    def test_strict_json_and_closed_schema(self):
        invalid=[b'\xff', b'\xef\xbb\xbf{}', b'[]', b'null', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":{"a":1,"a":2}}']
        for key in ('manifest','approval'):
            for raw in invalid:
                with self.subTest(key=key, raw=raw):
                    self.paths[key].write_bytes(raw); self.blocked(); self.write()
        for key in list(self.manifest):
            with self.subTest(missing=key):
                value=self.manifest.pop(key); self.rebind_manifest(); self.blocked(); self.manifest[key]=value; self.rebind_manifest()
        objects=[self.approval]+[self.approval[k] for k in ('source','build_recipe','embed_source','manifest','policies','tax','product','enrollment')]+list(self.approval['policies'].values())
        for obj in objects:
            for key in list(obj):
                with self.subTest(missing=key, object=list(obj)):
                    value=obj.pop(key); self.write(); self.blocked(); obj[key]=value
            for extra in ('approved','test_passed','artifact','image_tag'):
                obj[extra]=True; self.write(); self.blocked(); del obj[extra]
        self.manifest['extra']='bad'; self.rebind_manifest(); self.blocked()

    def test_manifest_value_mutations(self):
        for key, values in {'enabled':[False,'true',1,None], 'terms_version':[None,'','future-v2'], 'tax_notice':[None,'',' \t\n','bad\x00','bad\r','bad\u007f','bad\u0080'], **{k+'_url':[None,'','https://'] for k in KINDS}}.items():
            old=self.manifest[key]
            for value in values:
                with self.subTest(key=key,value=value):
                    self.manifest[key]=value; self.rebind_manifest(); self.blocked()
            self.manifest[key]=old; self.rebind_manifest()

    def test_url_rejections_and_provenance(self):
        malformed=['http://merchant.company/t','/terms','https:///terms','https://user@merchant.company/t','https://merchant.company/t#frag','https://merchant.company:bad/t','https://merchant.company:65536/t','https://merchant.company/white space','https://merchant.company/\n','https://merchant.company/\\t','https://merchant.company/\u0080']
        reserved=['https://localhost/t','https://sub.localhost/t','https://merchant.local/t','https://merchant.test/t','https://merchant.invalid/t','https://merchant.example/t','https://example.com/t','https://sub.example.net/t','https://example.org/t','https://127.0.0.1/t','https://[::1]/t','https://merchant.company/fixture/t','https://merchant.company/fixtures/t']
        for url in malformed+reserved:
            self.manifest['terms_url']=url; self.approval['policies']['terms']['url']=url; self.rebind_manifest()
            with self.subTest(url=url,provenance='synthetic'):
                self.assertEqual(self.evaluate()['status'], 'blocked' if url in malformed else 'prepared_offline')
            self.approval['provenance']='owner_supplied_unverified'; self.write(); self.blocked(); self.approval['provenance']='synthetic'

    def test_policy_and_raw_manifest_bindings(self):
        self.paths['policies']['terms'].write_bytes(self.policy_bytes['privacy']); self.blocked(); self.write()
        for k in KINDS:
            raw=self.policy_bytes[k]; self.paths['policies'][k].write_bytes(raw+b'!'); self.blocked(); self.write()
            for field,value in [('url',self.manifest[k+'_url']+'?changed'),('bytes',len(raw)+1),('sha256','0'*64)]:
                old=self.approval['policies'][k][field]; self.approval['policies'][k][field]=value; self.write(); self.blocked(); self.approval['policies'][k][field]=old
        self.write(); self.paths['manifest'].write_bytes(encoded(self.manifest)+b'\n'); self.blocked()

    def test_envelope_tuple_mutations(self):
        mutations={'schema':['bad'], 'provenance':['owner_approved','',None], 'owner_approval_ref':['',' ', 'x'*2049], 'policy_revision':['',' ', 'x'*257], 'source.sha':['0'*40,None], 'source.tree':['0'*40], 'build_recipe.sha256':['0'*64,'A'*64], 'build_recipe.bytes':[True,929], 'embed_source.sha256':['0'*64], 'embed_source.bytes':[True,30492], 'manifest.sha256':['0'*64,'bad'], 'manifest.bytes':[True,0,-1], 'manifest.served_path':['/other'], 'manifest.terms_version':['other'], 'tax.notice_sha256':['0'*64], 'tax.notice_bytes':[True,0], 'tax.final_price_treatment':['automatic_tax'], 'tax.owner_decision_ref':['',' ', 'x'*2049], 'product.id':['other'], 'product.currency':['usd'], 'product.amount_minor':[True,1999,2000.0], 'product.recurrence':['monthly'], 'enrollment.mode':['stripe_live'], 'enrollment.account_id':['','acct_','acct_é','acct_'+'a'*252], 'enrollment.price_id':['','price_','price_é','price_'+'a'*251]}
        for dotted, values in mutations.items():
            parts=dotted.split('.'); obj=self.approval
            for part in parts[:-1]: obj=obj[part]
            key=parts[-1]; old=obj[key]
            for value in values:
                with self.subTest(field=dotted,value=value):
                    obj[key]=value; self.write(); self.blocked()
            obj[key]=old
        self.write()
        for key in ('build_recipe','embed_source'):
            self.paths[key].write_bytes(self.paths[key].read_bytes()+b'\n'); self.blocked(); self.write()
        self.manifest['tax_notice']+='é'; self.rebind_manifest(); self.blocked()

    def test_policy_mapping_and_nonobject_nested_inputs(self):
        for key in ('source','build_recipe','embed_source','manifest','policies','tax','product','enrollment'):
            old=self.approval[key]
            for value in (None,[],True,'wrong'):
                self.approval[key]=value; self.write(); self.blocked()
            self.approval[key]=old
        self.write()
        for mapping in ({}, {'terms':self.paths['policies']['terms']}, {**self.paths['policies'],'other':self.dir/'other'}):
            with self.subTest(mapping=list(mapping)):
                self.assertEqual(merchant.evaluate_files(**{**self.paths,'policies':mapping})['status'],'blocked')

    def test_symlinked_parent_directory_is_rejected(self):
        alias = self.dir/'alias'
        actual = self.dir/'actual'
        actual.mkdir()
        alias.symlink_to(actual, target_is_directory=True)
        for key in ('manifest', 'approval', 'build_recipe', 'embed_source'):
            original = self.paths[key]
            (actual/original.name).write_bytes(original.read_bytes())
            self.paths[key] = alias/original.name
            with self.subTest(input=key): self.blocked()
            self.paths[key] = original
        for kind in KINDS:
            original = self.paths['policies'][kind]
            (actual/original.name).write_bytes(original.read_bytes())
            self.paths['policies'][kind] = alias/original.name
            with self.subTest(input=kind): self.blocked()
            self.paths['policies'][kind] = original

    def test_relative_paths_and_invalid_path_values(self):
        original = self.paths['manifest']
        self.paths['manifest'] = Path(os.path.relpath(original))
        self.assertEqual(self.evaluate()['status'], 'prepared_offline')
        for invalid in (None, 0, b'bytes-path', 'bad\x00path'):
            with self.subTest(path=repr(invalid)):
                self.paths['manifest'] = invalid
                result = self.evaluate()
                self.assertEqual(result['status'], 'blocked')
                self.assertIn('manifest_file_invalid', result['reasons'])
                self.assertIsNone(result['manifest_sha256'])
        self.paths['manifest'] = original

    def test_opened_ancestor_remains_pinned_during_directory_swap(self):
        parent = self.dir/'parent'
        parent.mkdir()
        original = self.paths['manifest']
        (parent/original.name).write_bytes(original.read_bytes())
        self.paths['manifest'] = parent/original.name
        moved = self.dir/'moved'
        replacement = self.dir/'replacement'
        replacement.mkdir()
        (replacement/original.name).write_bytes(b'invalid replacement')
        real_open = os.open
        swapped = False

        def swap_after_open(path, flags, **kwargs):
            nonlocal swapped
            descriptor = real_open(path, flags, **kwargs)
            if path == 'parent' and not swapped:
                parent.rename(moved)
                parent.symlink_to(replacement, target_is_directory=True)
                swapped = True
            return descriptor

        with patch('os.open', side_effect=swap_after_open):
            self.assertEqual(self.evaluate()['status'], 'prepared_offline')
        self.assertTrue(swapped)
        self.blocked()  # A later evaluation must reject the new symlink ancestor.

    def test_nonregular_and_unreadable_files(self):
        path = self.paths['manifest']
        path.unlink()
        os.mkfifo(path)
        self.blocked()
        path.unlink()
        self.write()
        with patch('os.open', side_effect=PermissionError('SECRET INPUT')):
            result = self.evaluate()
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['manifest_sha256'])
        self.assertIsNone(result['manifest_bytes'])
        self.assertNotIn('SECRET INPUT', json.dumps(result))

    def test_decoded_tax_bytes_and_unicode_are_bound(self):
        for notice in ('Valid\nnotice\twith tabs é', 'bad\x80', 'bad\x00', '\ud800'):
            with self.subTest(notice=notice):
                self.manifest['tax_notice'] = notice
                # JSON escapes can represent an unpaired surrogate but UTF-8 cannot.
                raw = json.dumps(self.manifest, ensure_ascii=True).encode()
                self.paths['manifest'].write_bytes(raw)
                self.approval['manifest'].update(binding(raw))
                if notice != '\ud800':
                    data = notice.encode()
                    self.approval['tax'].update(notice_sha256=hashlib.sha256(data).hexdigest(), notice_bytes=len(data))
                self.paths['approval'].write_bytes(encoded(self.approval))
                self.assertEqual(self.evaluate()['status'], 'prepared_offline' if notice.startswith('Valid') else 'blocked')

    def test_policy_digest_types_and_limits(self):
        for field, values in {'bytes':[True,0,-1,1.0], 'sha256':['bad','A'*64,None], 'url':[None,'']}.items():
            obj=self.approval['policies']['terms']; old=obj[field]
            for value in values:
                with self.subTest(field=field,value=value):
                    obj[field]=value; self.write(); self.blocked()
            obj[field]=old
        self.write()
        self.paths['policies']['terms'].write_bytes(b'')
        self.approval['policies']['terms'].update(binding(b''))
        self.paths['approval'].write_bytes(encoded(self.approval))
        self.blocked()

    def test_read_only_and_no_ambient_access(self):
        before={str(p):p.read_bytes() for p in self.dir.iterdir()}
        class NoEnvironment(dict):
            def get(self, *args): raise AssertionError('environment')
            def __getitem__(self, key): raise AssertionError('environment')
            def __iter__(self): raise AssertionError('environment')
            def __contains__(self, key): raise AssertionError('environment')
        with patch('socket.socket', side_effect=AssertionError('network')), patch('subprocess.run', side_effect=AssertionError('subprocess')), patch('os.getenv', side_effect=AssertionError('environment')), patch('os.environ', NoEnvironment()):
            self.assertEqual(self.evaluate()['status'],'prepared_offline')
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.dir.iterdir()})

    def test_cli_status_usage_and_no_content_echo(self):
        args=['--manifest',str(self.paths['manifest']),'--approval',str(self.paths['approval']),'--build-recipe',str(self.paths['build_recipe']),'--embed-source',str(self.paths['embed_source'])]
        for k in KINDS: args+=['--policy',k+'='+str(self.paths['policies'][k])]
        for expected in (0,3):
            out=io.StringIO()
            with contextlib.redirect_stdout(out), patch('sys.argv',['tool']+args): code=merchant.main()
            self.assertEqual(code,expected); result=json.loads(out.getvalue())
            self.assertEqual(result,self.evaluate())
            for secret in ('merchant.example','acct_SYNTHETIC','Synthetic final-price'):
                self.assertNotIn(secret,out.getvalue())
            self.paths['manifest'].unlink(missing_ok=True)
        for bad in ([],args+['--policy','terms=x'],args+['--policy','unknown=x'],args+['--policy','broken']):
            with self.subTest(args=bad),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as caught:
                merchant.main(bad)
            self.assertEqual(caught.exception.code,2)


if __name__ == '__main__':
    unittest.main()
