import ast
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('workshop_browser_smoke', Path(__file__).with_name('workshop_browser_smoke.py'))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class BrowserEvidenceContract(unittest.TestCase):
    def test_wrong_account_media_requires_not_found(self):
        source = ast.parse(Path(smoke.__file__).read_text())
        case = next(node for node in source.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'api_case')
        assertions = [node for node in ast.walk(case) if isinstance(node, ast.Assert)
                      and any(isinstance(value, ast.Attribute) and value.attr == 'status'
                              and isinstance(value.value, ast.Name) and value.value.id == 'denied_image'
                              for value in ast.walk(node.test))]
        self.assertEqual(len(assertions), 1)
        check = compile(ast.fix_missing_locations(ast.Module(body=assertions, type_ignores=[])), smoke.__file__, 'exec')
        exec(check, {'denied_image': SimpleNamespace(status=404)})
        for status in (200, 401, 403, 410, 503):
            with self.subTest(status=status), self.assertRaises(AssertionError):
                exec(check, {'denied_image': SimpleNamespace(status=status)})

    def test_only_owned_loopback_https_origins(self):
        for value in ['https://example.com', 'http://127.0.0.1:3000', 'https://localhost.evil:3000', 'https://user@localhost:3000', 'https://localhost:3000/path', 'https://localhost:3000?token=x']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                smoke.fixture_origin(value)
        self.assertEqual(smoke.fixture_origin('https://127.0.0.1:32001'), 'https://127.0.0.1:32001')

    def test_frozen_inventory_has_40_unique_dto_cases(self):
        inventory = smoke.inventory()
        self.assertEqual(len(inventory), 40)
        self.assertEqual(len(set(inventory)), 40)
        self.assertIn('firebase-memory-persistence', inventory)
        self.assertIn('source-media-isolation', inventory)

    def test_acceptance_rejects_missing_skipped_and_wrong_provenance(self):
        expected = [('chromium', name) for name in smoke.inventory()]
        rows = [{'browser': engine, 'scenario': name, 'status': 'passed'} for engine, name in expected]
        smoke.validate_results(rows, expected)
        for altered in [rows[:-1], rows + [rows[0]], [dict(row, status='skipped') for row in rows]]:
            with self.assertRaises(ValueError): smoke.validate_results(altered, expected)
        with self.assertRaises(ValueError): smoke.candidate_identity('short')

    def test_warm_runtime_rejects_new_external_work_but_allows_image_delivery(self):
        before = dict(provider_calls={'bankone': 2, 'banktwo': 0}, source_calls={'bankone': 1, 'banktwo': 0}, asset_calls={'bankone': 1, 'banktwo': 0}, model_calls=1, counts={'article_jobs': 1, 'source_revisions': 1, 'canonical_revisions': 1, 'published_revisions': 1, 'publication_events': 1}, immutable_sha256='a'*64)
        smoke.validate_warm_runtime(before, before, 2, 3)
        for field in ('provider_calls', 'source_calls', 'asset_calls', 'model_calls', 'counts', 'immutable_sha256'):
            changed = dict(before)
            changed[field] = 'changed'
            with self.subTest(field=field), self.assertRaises(AssertionError):
                smoke.validate_warm_runtime(before, changed, 2, 3)
        with self.assertRaises(AssertionError): smoke.validate_warm_runtime(before, before, 2, 2)

    def test_external_transport_allowlist_is_exact(self):
        self.assertTrue(smoke.allowed_external('https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=fixture-key'))
        for value in ['https://identitytoolkit.googleapis.com.evil/v1/accounts:signInWithIdp', 'https://evil.invalid/pixel', 'https://checkout.stripe.com.evil/c/pay/fixture']:
            self.assertFalse(smoke.allowed_external(value))


if __name__ == '__main__': unittest.main()
