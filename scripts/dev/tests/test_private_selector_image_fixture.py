import unittest
from private_selector_adapter_fakes import Backend, manifest, c, f


class Tests(unittest.TestCase):
    def fixture(self):
        v = manifest('fixture'); b = Backend(v); return v, b, f.Fixture(v, b)

    def test_success_cleans_only_verified_owned_ids(self):
        v, b, adapter = self.fixture(); result = adapter.run()
        self.assertTrue(result['serving_unchanged']); self.assertTrue(result['owned_cleanup'])
        self.assertEqual([e[1] for e in b.events if e[0] == 'fixture_remove'], ['c' * 64, 'b' * 64])
        self.assertIn('fixture-result', b.markers)

    def test_supplier_or_payment_or_model_flag_refuses_and_cleans(self):
        v, b, adapter = self.fixture(); b.fixture_checks['no_supplier_or_payment_or_model_request'] = False
        with self.assertRaises(c.Refused): adapter.run()
        self.assertFalse(b.fixture_values); self.assertNotIn('fixture-result', b.markers)

    def test_unverified_returned_id_never_touched(self):
        v, b, adapter = self.fixture(); b.fixture_bad_role = 'worker'
        with self.assertRaises(c.Refused): adapter.run()
        self.assertNotIn(('fixture_stop', c.OLD), b.events)
        self.assertNotIn(('fixture_remove', c.OLD), b.events)
        self.assertTrue(b.markers['fixture-hold']['cleanup_unknown'])

    def test_cleanup_unknown_holds_and_never_claims_pass(self):
        v, b, adapter = self.fixture(); b.fixture_stop_errors.add('c' * 64)
        with self.assertRaises(c.Refused) as error: adapter.run()
        self.assertNotIn('SENTINEL_SECRET', str(error.exception))
        self.assertNotIn(('fixture_remove', 'c' * 64), b.events)
        self.assertIn(('fixture_remove', 'b' * 64), b.events)
        self.assertNotIn('fixture-result', b.markers)

    def test_synthetic_database_bucket_cleanup_required(self):
        v, b, adapter = self.fixture(); b.data_clean = False
        with self.assertRaises(c.Refused): adapter.run()
        self.assertTrue(b.markers['fixture-hold']['cleanup_unknown'])

    def test_one_fixture_attempt_only(self):
        v, b, adapter = self.fixture(); adapter.run()
        count = len([e for e in b.events if e[0] == 'fixture_create'])
        with self.assertRaises(c.Refused): adapter.run()
        self.assertEqual(count, len([e for e in b.events if e[0] == 'fixture_create']))


if __name__ == '__main__': unittest.main()
