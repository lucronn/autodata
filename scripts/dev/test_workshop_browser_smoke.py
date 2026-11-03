import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('workshop_browser_smoke', Path(__file__).with_name('workshop_browser_smoke.py'))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class BrowserEvidenceContract(unittest.TestCase):
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

    def test_external_transport_allowlist_is_exact(self):
        self.assertTrue(smoke.allowed_external('https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=fixture-key'))
        for value in ['https://identitytoolkit.googleapis.com.evil/v1/accounts:signInWithIdp', 'https://evil.invalid/pixel', 'https://checkout.stripe.com.evil/c/pay/fixture']:
            self.assertFalse(smoke.allowed_external(value))


if __name__ == '__main__': unittest.main()
