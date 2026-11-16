import unittest
from unittest.mock import patch
from private_selector_adapter_fakes import Backend, manifest, c, f


class Tests(unittest.TestCase):
    def fixture(self):
        v = manifest('fixture'); b = Backend(v); return v, b, f.Fixture(v, b)

    def test_success_cleans_only_verified_owned_ids(self):
        v, b, adapter = self.fixture(); result = adapter.run()
        self.assertTrue(result['serving_unchanged']); self.assertTrue(result['owned_cleanup'])
        self.assertEqual([e[1] for e in b.events if e[0] == 'fixture_remove'], ['c' * 64, 'b' * 64])
        self.assertIn('fixture-result', b.markers)

    def test_readiness_failure_prevents_worker_creation_and_cleans_bootstrap(self):
        v,b,adapter=self.fixture()
        with patch.object(b,'wait_fixture_ready',side_effect=c.Refused('bootstrap_deadline')):
            with self.assertRaises(c.Refused):adapter.run()
        self.assertEqual([x for x in b.events if x[0]=='fixture_create'], [('fixture_create','bootstrap')])
        self.assertIn(('fixture_remove','b'*64),b.events)
        self.assertNotIn('fixture-result',b.markers)

    def test_started_fixture_identity_mismatch_still_reaches_exact_owned_cleanup(self):
        v,b,adapter=self.fixture(); started=set(); original=b.fixture_identity
        def identity(identifier):
            if identifier in started:raise c.Refused('unexpected_running_hostconfig')
            return original(identifier)
        def start(identifier):started.add(identifier);b.events.append(('fixture_start',identifier))
        with patch.object(b,'fixture_identity',side_effect=identity),patch.object(b,'start_fixture',side_effect=start), \
             patch.object(b,'exercise_fixture',side_effect=c.Refused('unexpected_running_hostconfig')):
            with self.assertRaises(c.Refused):adapter.run()
        self.assertIn(('fixture_stop','b'*64),b.events)
        self.assertIn(('fixture_stop','c'*64),b.events)
        self.assertFalse(b.fixture_values)
        self.assertFalse(b.markers['fixture-hold']['cleanup_unknown'])

    def test_boundary_failure_in_finally_never_blocks_owned_stop_and_remove(self):
        v,b,adapter=self.fixture(); cleanup_phase=[False]; original=adapter.check
        def check():
            if cleanup_phase[0]:raise c.Refused('public_peer_capacity_drift')
            return original()
        def exercise(*_):cleanup_phase[0]=True;return dict(b.fixture_checks)
        with patch.object(adapter,'check',side_effect=check),patch.object(b,'exercise_fixture',side_effect=exercise):
            with self.assertRaises(c.Refused):adapter.run()
        self.assertIn(('fixture_stop','b'*64),b.events)
        self.assertIn(('fixture_stop','c'*64),b.events)
        self.assertFalse(b.fixture_values)
        self.assertFalse(b.markers['fixture-hold']['cleanup_unknown'])
        self.assertTrue(b.markers['fixture-hold']['acceptance_failed'])
        self.assertNotIn('fixture-result',b.markers)

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
