"""Launcher boundaries only: all live capabilities mocked and forbidden by default."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
# The physical client is sourced from the exact repo payload for this owned test only.
spec = importlib.util.spec_from_file_location('fixture_client', ROOT / 'scripts/dev/fixtures/private_selector_client.py')
client = importlib.util.module_from_spec(spec); spec.loader.exec_module(client)
sys.modules.setdefault('fixture_client', client)
import private_selector_fixture_launcher as m


class Tests(unittest.TestCase):
    def test_metadata_only_never_constructs_or_wraps_a_live_backend(self):
        with patch.object(m.fixture_client, 'wrap_transport', side_effect=AssertionError('dispatch forbidden')), \
             patch.object(m.t, 'LocalTransport', side_effect=AssertionError('backend forbidden')):
            result = m.launch({'execution_approved': True}, 'a' * 64)
        self.assertFalse(result['live_backend_constructed'])

    def test_execution_without_approval_refuses_before_capability(self):
        with patch.object(m.fixture_client, 'wrap_transport') as wrap:
            with self.assertRaises(m.c.Refused):m.launch({'execution_approved': False}, 'a' * 64, execute=True)
        wrap.assert_not_called()

    def test_hash_failure_prevents_handoff_even_when_execute_flag_present(self):
        with patch.object(m, 'verify', side_effect=m.c.Refused('fixture_manifest_hash')), \
             patch.object(m, 'launch') as launch:
            with self.assertRaises(m.c.Refused):
                m.main(['--manifest', '/authored', '--approved-manifest-sha', 'a' * 64,
                        '--external-seal-sha', 'b' * 64, '--execute'])
        launch.assert_not_called()

    def test_explicit_execution_composes_sealed_wrapper_once_and_closes_on_failure(self):
        backend = Mock(); constructor = Mock(return_value=backend)
        fixture = Mock(); fixture.run.side_effect = m.c.Refused('authored failure')
        manifest = {'execution_approved': True}
        with patch.object(m.fixture_client, 'wrap_transport', return_value=constructor) as wrap, \
             patch.object(m.f, 'Fixture', return_value=fixture):
            with self.assertRaises(m.c.Refused):m.launch(manifest, 'a' * 64, execute=True)
        wrap.assert_called_once_with(m.t.LocalTransport)
        constructor.assert_called_once_with(manifest, external_seal_sha='a' * 64, dispatch_enabled=True)
        fixture.run.assert_called_once_with(); backend.close.assert_called_once_with()


if __name__ == '__main__': unittest.main()
