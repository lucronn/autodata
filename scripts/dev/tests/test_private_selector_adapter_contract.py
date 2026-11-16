import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from private_selector_adapter_fakes import Backend, manifest, c


class Tests(unittest.TestCase):
    def test_dry_validation_never_authorizes_execution(self):
        for phase in ('fixture', 'runtime'):
            v = manifest(phase); v['execution_approved'] = False
            self.assertFalse(c.validate(v, phase)['execution_authorized'])

    def test_boundary_drift_precedes_any_mutation(self):
        for patch in [{'docker_root': '/wrong'}, {'socket_identity': [0, 0]},
                      {'artifact_hashes': {}}, {'home_free': 0}, {'docker_free': 0},
                      {'home_allocated': 128 * c.MIB + 1}, {'docker_allocated': 64 * c.MIB + 1},
                      {'offloaded_allocated': 64 * c.MIB + 1}, {'offloaded_free': 0}]:
            v = manifest('fixture'); b = Backend(v); b.proof_patch = patch
            with self.assertRaises(c.Refused): c.boundary(b, v, 'fixture')
            self.assertFalse(any(e[0] in ('stop', 'start', 'fixture_create') for e in b.events))

    def test_pin_and_cap_drift_refused(self):
        for key, value in [('pins', {}), ('home_cap', 256 * c.MIB), ('offloaded_cap', 0)]:
            v = manifest('fixture'); v[key] = value
            with self.assertRaises(c.Refused): c.validate(v, 'fixture')

    def test_cli_has_no_execute_option_and_never_creates_backend(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): c.cli('fixture', ['--execute'])
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'manifest'; p.write_text(json.dumps(manifest('fixture'))); p.chmod(0o600)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(c.cli('fixture', ['--validate-only', '--manifest', str(p)]), 0)
            self.assertFalse(json.loads(out.getvalue())['live_backend_supplied'])

    def test_unknown_lifecycle_status_refused_even_if_hash_missing(self):
        from private_selector_adapter_fakes import state
        value = state(c.OLD_IDENTITY, 'running'); value['status'] = 'unknown'; value['hostconfig'] = None
        with self.assertRaises(c.Refused): c.identity(value, c.OLD_IDENTITY)

    def test_created_running_normalization_accepts_only_reviewed_hashes(self):
        from private_selector_adapter_fakes import state
        expected = manifest('runtime')['candidate']
        for status in ('created', 'running', 'exited'):
            self.assertEqual(c.identity(state(expected, status), expected)['status'], status)
        value = state(expected, 'running'); value['hostconfig'] = expected['hostconfig_by_status']['created']
        with self.assertRaises(c.Refused): c.identity(value, expected)

    def test_secondary_drift_refuses_at_boundary(self):
        v = manifest('fixture'); b = Backend(v); b.states[c.SECONDARY]['pid'] = 1
        with self.assertRaises(c.Refused): c.boundary(b, v, 'fixture')

    def test_boolean_and_number_policy_fields_are_distinct(self):
        self.assertFalse(c.typed_equal({'readonly': 1}, {'readonly': True}))


if __name__ == '__main__': unittest.main()
