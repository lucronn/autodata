"""Safe configuration anomalies preserve source and persistence decisions."""
import hashlib
from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from autodata_ingestion import catalog_service as catalog
from lifecycle_support import fresh_database
from autodata_ingestion.source_connector_client import SourceConnectorClient
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts/dev"))
from source_connector_fixture_server import serve_connector

SECRET = 'licensed-credential-DO-NOT-LOG'
REQUEST = {'scope': 'configurations', 'year': 2024, 'make': 'Example', 'model': 'Car', 'region': 'US'}


def scope_hash():
    fields = dict(scope='configurations', year='2024', make='example', model='car', region='US')
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]


def payload(provider, complete=True, *, empty=False):
    return {'complete': complete, 'missing_scopes': [] if complete else [SECRET],
            'rows': [] if empty else [{'year': 2024, 'make': 'Example', 'model': 'Car', 'region': 'US', 'engine': '2.0L'}],
            'provenance': [{'provider': 'autoapi' if provider == 'bankone' else 'autoapitwo',
                            'source_uri': 'fixture://' + SECRET, 'source_version': 'fixture'}]}


class Provider:
    def __init__(self, name, result):
        self.client = SimpleNamespace(provider=name, base_url='https://' + SECRET)
        self.result = result
        self.calls = 0

    def resolve_catalog(self, request):
        self.calls += 1
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class ConfigurationDiagnosticTests(unittest.TestCase):
    def service(self, providers, cached=None):
        return catalog.CacheFirstCatalogService(cache_reader=lambda _: cached or {'complete': False, 'rows': []}, providers=providers)

    def assert_safe(self, captured):
        text = '\n'.join(r.getMessage() for r in captured.records)
        self.assertNotIn(SECRET, text)
        self.assertNotIn('fixture://', text)
        self.assertNotIn('https://', text)
        self.assertTrue(all(r.exc_info is None for r in captured.records))
        self.assertIn('scope_hash=' + scope_hash(), text)
        return text

    def test_caught_provider_failures_and_partial_rows_are_safe_per_bank(self):
        for failed, order in [('bankone', False), ('banktwo', True)]:
            providers = [Provider(failed, ValueError(SECRET)), Provider('banktwo' if failed == 'bankone' else 'bankone', payload('bankone'))]
            if order:
                providers.reverse()
            with self.subTest(provider=failed), self.assertLogs(catalog._LOG, level='WARNING') as logs:
                result = self.service(providers).resolve(catalog.CatalogRequest(2024, 'Example', 'Car', scope='configurations'))
            text = self.assert_safe(logs)
            self.assertIn(f'provider={failed} stage=provider_resolution outcome=failed error_type=ValueError row_count=-1', text)
            self.assertFalse(result.complete)
            self.assertEqual(len(result.rows), 1)
            self.assertEqual([p.calls for p in providers], [1, 1])

    def test_partial_outcome_logs_counts_without_raw_missing_scopes(self):
        with self.assertLogs(catalog._LOG, level='WARNING') as logs:
            result = self.service([Provider('bankone', payload('bankone', False)), Provider('banktwo', payload('banktwo'))]).resolve(catalog.CatalogRequest(2024, 'Example', 'Car', scope='configurations'))
        self.assertIn('provider=bankone stage=provider_resolution outcome=incomplete error_type=none row_count=1', self.assert_safe(logs))
        self.assertFalse(result.complete)
        self.assertEqual(len(result.rows), 1)
        self.assertIn(SECRET, result.missing_scopes)  # Existing data decision is unchanged; logs redact it.

    def test_unknown_bank_and_exception_name_are_redacted(self):
        secret_error = type(SECRET, (Exception,), {})
        with self.assertLogs(catalog._LOG, level='WARNING') as logs:
            result = self.service([Provider(SECRET, secret_error(SECRET))]).resolve(catalog.CatalogRequest(2024, 'Example', 'Car', scope='configurations'))
        self.assertIn('provider=unknown stage=provider_resolution outcome=failed error_type=OtherError', self.assert_safe(logs))
        self.assertFalse(result.complete)

    def test_projection_failure_logs_then_preserves_exception(self):
        broken = payload('bankone')
        original = catalog._canonical_rows
        error = TypeError(SECRET)
        def rows(values, **kwargs):
            if values is broken['rows']:
                raise error
            return original(values, **kwargs)
        with patch.object(catalog, '_canonical_rows', side_effect=rows), self.assertLogs(catalog._LOG, level='WARNING') as logs:
            with self.assertRaises(TypeError) as raised:
                self.service([Provider('bankone', broken)]).resolve(catalog.CatalogRequest(2024, 'Example', 'Car', scope='configurations'))
        self.assertIs(raised.exception, error)
        self.assertIn('provider=bankone stage=provider_projection outcome=failed error_type=TypeError', self.assert_safe(logs))

    def test_healthy_empty_cached_nonconfiguration_and_cancellation_do_not_warn(self):
        cases = [([Provider('bankone', payload('bankone', empty=True))], None, 'configurations'),
                 ([Provider('bankone', ValueError(SECRET))], {'complete': True, 'rows': []}, 'configurations'),
                 ([Provider('bankone', ValueError(SECRET))], None, 'makes')]
        with patch.object(catalog._LOG, 'warning') as warning:
            for providers, cached, scope in cases:
                self.service(providers, cached).resolve(catalog.CatalogRequest(2024, 'Example', 'Car', scope=scope))
            with self.assertRaises(catalog._SelectorDeepeningStopped):
                self.service([Provider('bankone', catalog._SelectorDeepeningStopped())]).resolve(catalog.CatalogRequest(2024, 'Example', 'Car', scope='configurations'))
        warning.assert_not_called()

    def test_logging_failure_cannot_change_partial_result(self):
        provider = Provider('bankone', ValueError(SECRET))
        with patch.object(catalog._LOG, 'warning', side_effect=RuntimeError(SECRET)):
            result = self.service([provider]).resolve(catalog.CatalogRequest(2024, 'Example', 'Car', scope='configurations'))
        self.assertFalse(result.complete)
        self.assertEqual(provider.calls, 1)

    def test_scope_hash_normalizes_equivalent_request_fields(self):
        provider = Provider(['not-a-bank', SECRET], ValueError(SECRET))
        with self.assertLogs(catalog._LOG, level='WARNING') as logs:
            self.service([provider]).resolve(catalog.CatalogRequest('2024', ' EXAMPLE ', ' car ', region='us', scope='configurations'))
        self.assertIn('provider=unknown', self.assert_safe(logs))

    def test_background_configuration_persistence_redacts_and_preserves_cleanup(self):
        providers = (Provider('bankone', payload('bankone')), Provider('banktwo', payload('banktwo')))
        control = Mock()
        output = io.StringIO()
        key = 'fixture-background'
        with patch.object(catalog, '_configured_catalog_providers', return_value=providers), patch.object(catalog, '_persist_resolved_catalog_rows', side_effect=ValueError(SECRET)) as persist, patch.object(catalog, '_DEEPEN_IN_FLIGHT', {key}), patch.object(catalog, '_DEEPEN_CONTROL', control), patch.object(catalog._LOG, 'warning') as warning, redirect_stdout(output):
            result = catalog._deepen_selector_scope(REQUEST, 'models', [{'model': 'Car'}], key, control)
            self.assertIsNone(result)
            self.assertEqual(catalog._DEEPEN_IN_FLIGHT, set())
            self.assertIsNone(catalog._DEEPEN_CONTROL)
        self.assertNotIn(SECRET, output.getvalue())
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(warning.call_count, 1)
        args = warning.call_args.args
        text = args[0] % args[1:]
        self.assertNotIn(SECRET, text)
        self.assertIn('scope_hash=' + scope_hash(), text)
        self.assertIn('provider=aggregate stage=row_persistence outcome=failed error_type=ValueError row_count=1', text)
        self.assertEqual([p.calls for p in providers], [2, 2])
        persist.assert_called_once()

    def ensure(self):
        return catalog.ensure_catalog_hydration(json.dumps({**REQUEST, 'idempotency_key': uuid.uuid4().hex}))

    def test_foreground_persistence_failures_log_stage_and_reraise_unchanged(self):
        for stage, name, error in [('row_persistence', '_persist_resolved_catalog_rows', ValueError(SECRET)),
                                   ('coverage_persistence', '_persist_hydration_scope', type(SECRET, (Exception,), {})(SECRET))]:
            with self.subTest(stage=stage), patch.object(catalog, '_configured_catalog_providers', return_value=(Provider('bankone', payload('bankone')), Provider('banktwo', payload('banktwo')))), patch.object(catalog, '_persist_resolved_catalog_rows', return_value={'status': 'persisted'}), patch.object(catalog, '_persist_hydration_scope', return_value={'status': 'persisted'}), patch.object(catalog, name, side_effect=error), self.assertLogs(catalog._LOG, level='WARNING') as logs:
                with self.assertRaises(type(error)) as raised:
                    self.ensure()
            self.assertIs(raised.exception, error)
            expected = 'ValueError' if isinstance(error, ValueError) else 'OtherError'
            self.assertIn(f'provider=aggregate stage={stage} outcome=failed error_type={expected}', self.assert_safe(logs))

    def test_unconfigured_and_not_persisted_are_observable_without_semantic_change(self):
        with patch.object(catalog, '_configured_catalog_providers', return_value=()), self.assertLogs(catalog._LOG, level='WARNING') as logs:
            result = self.ensure()
        self.assertFalse(result['complete'])
        self.assertIn('provider=aggregate stage=provider_configuration outcome=unconfigured error_type=none row_count=0', self.assert_safe(logs))
        with patch.object(catalog, '_configured_catalog_providers', return_value=(Provider('bankone', payload('bankone')), Provider('banktwo', payload('banktwo')))), patch.object(catalog, '_persist_resolved_catalog_rows', return_value={'status': 'persisted'}), patch.object(catalog, '_persist_hydration_scope', return_value={'status': 'not_complete', 'secret': SECRET}), self.assertLogs(catalog._LOG, level='WARNING') as logs:
            result = self.ensure()
        self.assertTrue(result['complete'])  # Preserve the current resolver response even when coverage storage is disabled.
        self.assertIn('provider=aggregate stage=coverage_persistence outcome=not_persisted error_type=none row_count=1', self.assert_safe(logs))


@pytest.mark.parametrize('outcome', ['complete', 'partial', 'exception', 'empty', 'persistence_failure'])
def test_configuration_marker_requires_all_providers_and_successful_persistence(fresh_database, monkeypatch, caplog, outcome):
    repo = fresh_database()
    providers = [Provider('bankone', payload('bankone', outcome != 'partial', empty=outcome == 'empty')),
                 Provider('banktwo', payload('banktwo', empty=outcome == 'empty'))]
    if outcome == 'exception':
        providers[0] = Provider('bankone', ValueError(SECRET))
    _assert_configuration_marker(repo, providers, monkeypatch, caplog, outcome)
    expected_calls = [1, 0] if outcome == 'persistence_failure' else [1, 1]
    assert [p.calls for p in providers] == expected_calls


def _assert_configuration_marker(repo, providers, monkeypatch, caplog, outcome):
    env = {'AUTODATA_DB_ADDRESS': 'postgres:5432', 'AUTODATA_POSTGRES_DB': repo.database_name,
           'AUTODATA_POSTGRES_USER': 'lifecycle_test', 'AUTODATA_POSTGRES_PASSWORD': 'lifecycle_test_only',
           'AUTODATA_SOURCE_PERSIST': '1', 'AUTODATA_S3_ENDPOINT': 'minio:9000',
           'AUTODATA_S3_ACCESS_KEY': 'fixture', 'AUTODATA_S3_SECRET_KEY': 'fixture',
           'AUTODATA_SOURCE_BUCKET': 'configuration-diagnostic-' + uuid.uuid4().hex}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(catalog, '_configured_catalog_providers', lambda **_: tuple(providers))
    if outcome == 'persistence_failure':
        monkeypatch.setattr(catalog, '_persist_resolved_catalog_rows', Mock(side_effect=ValueError(SECRET)))
    with repo.connect() as conn:
        before = {t: conn.execute('SELECT count(*) AS count FROM ' + t).fetchone()['count'] for t in ('customer_accounts', 'entitlements', 'workshop_orders', 'payment_events', 'canonical_articles')}
    if outcome == 'persistence_failure':
        with pytest.raises(ValueError):
            catalog.ensure_catalog_hydration(json.dumps({**REQUEST, 'idempotency_key': uuid.uuid4().hex}))
    else:
        result = catalog.ensure_catalog_hydration(json.dumps({**REQUEST, 'idempotency_key': uuid.uuid4().hex}))
        assert result['complete'] is (outcome in {'complete', 'empty'})
    with repo.connect() as conn:
        marker = conn.execute("SELECT provenance FROM vehicle_catalog_hydration_scopes WHERE scope_key='configurations|2024|example|car|US'").fetchone()
        after = {t: conn.execute('SELECT count(*) AS count FROM ' + t).fetchone()['count'] for t in before}
    assert before == after
    assert bool(marker) is (outcome in {'complete', 'empty'})
    if marker:
        assert {p['provider'] for p in marker['provenance']} == {'autoapi', 'autoapitwo'}
    assert SECRET not in caplog.text


@pytest.mark.parametrize('outcome', ['complete', 'exception'])
def test_real_http_two_bank_configuration_persistence(fresh_database, monkeypatch, caplog, outcome):
    """Real loopback connector clients -> source objects/PostgreSQL, never live banks."""
    with ExitStack() as stack:
        servers = [stack.enter_context(serve_connector(bank)) for bank in ('bankone', 'banktwo')]
        for server in servers:
            def response(path, request_payload=None, *, fixture=server):
                fixture.calls.append(path)
                assert path.startswith('/v1/catalog/configurations?')
                if outcome == 'exception' and fixture.provider == 'bankone':
                    return 503, {'error': SECRET}
                item = {'opaque_ref': 'fixture-car', 'label': 'Example Car 2.0L',
                        'year': 2024, 'make': 'Example', 'model': 'Car', 'region': 'US', 'engine': '2.0L'}
                return 200, fixture.envelope(scope='configurations', complete=True, items=[item])
            server.response = response
        providers = [catalog._SourceCatalogProvider(SourceConnectorClient(
            server.url, token=server.token, provider=server.provider)) for server in servers]
        _assert_configuration_marker(fresh_database(), providers, monkeypatch, caplog, outcome)
        assert [len(server.calls) for server in servers] == [1, 1]
