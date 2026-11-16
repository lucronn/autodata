import copy
import unittest
from private_selector_adapter_fakes import Backend, manifest, state, c, r


class Tests(unittest.TestCase):
    def setup_runtime(self):
        value = manifest('runtime'); backend = Backend(value)
        return value, backend, r.Runtime(value, backend)

    def test_activation_fences_old_before_new_start(self):
        v, b, adapter = self.setup_runtime(); adapter.activate()
        self.assertIn('activation-result', b.markers)
        events = b.events
        self.assertLess(events.index(('marker', 'activation-attempt')), events.index(('stop', c.OLD)))
        self.assertLess(events.index(('stop', c.OLD)), events.index(('start', v['candidate']['id'])))
        self.assertEqual(sum(e == ('pause', .2) for e in events), 2)

    def test_start_failure_created_candidate_recovers_verified_old(self):
        v, b, adapter = self.setup_runtime(); b.start_errors.add(v['candidate']['id'])
        with self.assertRaises(c.Refused): adapter.activate()
        self.assertTrue(b.markers['rollback-result']['candidate_termination_proven'])
        self.assertIn(('stop', v['candidate']['id']), b.events)
        self.assertIn(('start', c.OLD), b.events)

    def test_unknown_stop_never_starts_old(self):
        for mode in ('stop_errors', 'stop_still_running'):
            v, b, adapter = self.setup_runtime()
            b.states[c.OLD] = state(c.OLD_IDENTITY, 'exited')
            b.states[v['candidate']['id']] = state(v['candidate'], 'running')
            getattr(b, mode).add(v['candidate']['id'])
            with self.assertRaises(c.Refused) as error: adapter.rollback()
            self.assertNotIn('SENTINEL_SECRET', str(error.exception))
            self.assertNotIn(('start', c.OLD), b.events)
            self.assertIn('rollback-attempt', b.markers); self.assertIn('rollback-hold', b.markers)
            self.assertNotIn('rollback-result', b.markers)

    def test_missing_candidate_after_old_stop_is_manual_hold(self):
        v, b, adapter = self.setup_runtime(); b.states[c.OLD] = state(c.OLD_IDENTITY, 'exited')
        b.inspect_errors.add(v['candidate']['id'])
        with self.assertRaises(c.Refused): adapter.rollback()
        self.assertNotIn(('start', c.OLD), b.events)
        self.assertIn('rollback-hold', b.markers)

    def test_drifted_old_never_causes_any_container_mutation(self):
        v, b, adapter = self.setup_runtime(); b.states[c.OLD]['config'] = '0' * 64
        with self.assertRaises(c.Refused): adapter.rollback()
        self.assertFalse(any(e[0] in ('start', 'stop') for e in b.events))
        self.assertIn('rollback-attempt', b.markers); self.assertIn('rollback-hold', b.markers)

    def test_already_running_old_does_not_get_started_twice(self):
        v, b, adapter = self.setup_runtime(); adapter.rollback()
        self.assertTrue(b.markers['rollback-result']['old_already_running'])
        self.assertNotIn(('start', c.OLD), b.events)

    def test_old_reverified_after_start(self):
        v, b, adapter = self.setup_runtime(); b.states[c.OLD] = state(c.OLD_IDENTITY, 'exited')
        b.drift_old_after_start = True
        with self.assertRaises(c.Refused): adapter.rollback()
        self.assertIn('rollback-hold', b.markers); self.assertNotIn('rollback-result', b.markers)

    def test_one_attempt_replay_has_no_second_mutation(self):
        v, b, adapter = self.setup_runtime(); adapter.rollback()
        count = len([e for e in b.events if e[0] in ('stop', 'start')])
        with self.assertRaises(c.Refused): adapter.rollback()
        self.assertEqual(count, len([e for e in b.events if e[0] in ('stop', 'start')]))

    def test_candidate_hostconfig_drift_refuses_before_old_stop(self):
        v, b, adapter = self.setup_runtime(); b.states[v['candidate']['id']]['hostconfig'] = '0' * 64
        with self.assertRaises(c.Refused): adapter.activate()
        self.assertNotIn(('stop', c.OLD), b.events)

    def test_postcheck_failure_never_claims_success(self):
        v, b, adapter = self.setup_runtime(); b.postcheck_bad_ids.add(v['candidate']['id'])
        with self.assertRaises(c.Refused): adapter.activate()
        self.assertNotIn('activation-result', b.markers); self.assertIn('rollback-result', b.markers)

    def test_unapproved_phase_does_not_write_attempt(self):
        v, b, adapter = self.setup_runtime(); v['execution_approved'] = False
        with self.assertRaises(c.Refused): adapter.activate()
        self.assertFalse(b.markers)

    def test_old_stop_unknown_never_starts_candidate(self):
        for attribute in ('stop_errors', 'stop_still_running'):
            v, b, adapter = self.setup_runtime(); getattr(b, attribute).add(c.OLD)
            with self.assertRaises(c.Refused): adapter.activate()
            self.assertNotIn(('start', v['candidate']['id']), b.events)
            self.assertTrue(b.markers['rollback-result']['old_already_running'])

    def test_rollback_postcheck_drift_holds_without_second_start(self):
        v, b, adapter = self.setup_runtime(); b.states[c.OLD] = state(c.OLD_IDENTITY, 'exited')
        b.postcheck_bad_ids.add(c.OLD)
        with self.assertRaises(c.Refused): adapter.rollback()
        self.assertEqual(b.events.count(('start', c.OLD)), 1)
        self.assertIn('rollback-hold', b.markers); self.assertNotIn('rollback-result', b.markers)

    def test_incumbent_same_id_restart_refused_before_mutation(self):
        v, b, adapter = self.setup_runtime(); b.states[c.OLD]['started_at'] = 'unexpected-restart'
        with self.assertRaises(c.Refused): adapter.activate()
        self.assertFalse(any(e[0] in ('start', 'stop') for e in b.events))


if __name__ == '__main__': unittest.main()
