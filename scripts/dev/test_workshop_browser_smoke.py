import ast
import asyncio
import copy
import json
import importlib.util
import unittest
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
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


class CheckoutResponse:
    def __init__(self, route, data, status=201):
        self.route, self.data, self.status = route, data, status
        self.json_error = None

    async def json(self):
        self.route.events.append('json')
        if self.json_error is not None:
            raise self.json_error
        return self.data


class CheckoutRoute:
    def __init__(self, *, method='POST', url='https://127.0.0.1:32001/v1/workshop/checkout-sessions',
                 key='66666666-6666-4666-8666-666666666666', body=None, data=None, status=201, failure=None):
        self.request = SimpleNamespace(method=method, url=url,
            headers={'idempotency-key': key}, post_data=body if body is not None else json.dumps({
                'configuration_id': smoke.CONFIG, 'region': 'US', 'purchase_terms_version': 'workshop-v1'}))
        self.events, self.backend_committed, self.forwarded_response = [], False, None
        self.failure, self.abort_error = failure, None
        self.fetched_response = CheckoutResponse(self, data if data is not None else dict(
            version='v1', state='checkout', order_id=smoke.ORDER, configuration_id=smoke.CONFIG,
            region='US', checkout_url='https://checkout.stripe.com/c/pay/cs_test_' + 'a'*32 + '#fidkdFixtureFragment',
            provider_expires_at='2099-01-01T00:00:00Z'), status)
        self.fetch_entered, self.fetch_release = None, None

    async def fetch(self, *, max_redirects, max_retries):
        assert (max_redirects, max_retries) == (0, 0)
        self.events.append('fetch')
        if self.fetch_entered is not None:
            self.fetch_entered.set()
            await self.fetch_release.wait()
        if self.failure is not None:
            raise self.failure
        self.backend_committed = True
        return self.fetched_response

    async def abort(self):
        self.events.append('abort')
        if self.abort_error is not None:
            raise self.abort_error

    async def continue_(self):
        self.events.append('continue')

    async def fulfill(self, *, response):
        self.events.append('fulfill')
        self.forwarded_response = response


class BrowserCheckoutResponseLoss(unittest.IsolatedAsyncioTestCase):
    def fixture(self, scenario=None):
        return smoke.APIFixture('https://127.0.0.1:32001', scenario or smoke.API_CASES[0])

    async def test_actual_api_commits_before_only_first_browser_response_is_lost(self):
        fixture = self.fixture()
        first, retry = CheckoutRoute(), CheckoutRoute(status=200)
        await fixture.route(first)
        self.assertEqual(first.events, ['fetch', 'json', 'abort'])
        self.assertTrue(first.backend_committed)
        self.assertEqual(fixture.lost_response_count, 1)
        await fixture.route(retry)
        self.assertEqual(retry.events, ['fetch', 'json', 'fulfill'])
        self.assertIs(retry.forwarded_response, retry.fetched_response)
        self.assertEqual(fixture.checkout_count, 2)
        self.assertEqual(fixture.lost_response_count, 1)
        self.assertEqual(fixture.keys, [first.request.headers['idempotency-key']]*2)
        self.assertEqual(fixture.checkout_bodies, [first.request.post_data]*2)
        third = CheckoutRoute()
        with self.assertRaises(AssertionError):
            await fixture.route(third)
        self.assertEqual(third.events, [])

    async def test_actual_fixture_url_fragment_survives_response_loss_and_retry(self):
        fixture, first, retry = self.fixture(), CheckoutRoute(), CheckoutRoute(status=200)
        hosted = 'https://checkout.stripe.com/c/pay/cs_test_' + 'a'*32 + '#fidkdFixtureFragment'
        self.assertEqual(first.fetched_response.data['checkout_url'], hosted)
        await fixture.route(first)
        self.assertEqual(first.events, ['fetch', 'json', 'abort'])
        self.assertTrue(first.backend_committed)
        await fixture.route(retry)
        self.assertEqual(retry.events, ['fetch', 'json', 'fulfill'])
        self.assertIs(retry.forwarded_response, retry.fetched_response)
        self.assertEqual([response['checkout_url'] for response in fixture.checkout_responses], [hosted, hosted])
        self.assertEqual(fixture.checkout_count, 2)
        self.assertEqual(fixture.lost_response_count, 1)

    async def test_unrelated_routes_leave_one_shot_available(self):
        for kwargs, scenario, events in [
            ({}, smoke.API_CASES[1], ['continue']),
            ({'method': 'GET'}, None, ['continue']),
            ({'url': 'https://127.0.0.1:32001/v1/workshop/orders'}, None, ['continue']),
            ({'url': 'https://127.0.0.1:32002/v1/workshop/checkout-sessions'}, None, ['abort']),
            ({'url': 'https://evil.invalid/v1/workshop/checkout-sessions'}, None, ['abort']),
        ]:
            with self.subTest(kwargs=kwargs, scenario=scenario):
                fixture = self.fixture(scenario)
                unrelated = CheckoutRoute(**kwargs)
                await fixture.route(unrelated)
                self.assertEqual(unrelated.events, events)
                self.assertEqual(fixture.checkout_count, 0)
                self.assertEqual(fixture.lost_response_count, 0)
                if scenario is None:
                    first = CheckoutRoute()
                    await fixture.route(first)
                    self.assertEqual(first.events, ['fetch', 'json', 'abort'])

    async def test_concurrent_activation_cannot_drop_a_second_response(self):
        fixture, first, concurrent = self.fixture(), CheckoutRoute(), CheckoutRoute()
        first.fetch_entered, first.fetch_release = asyncio.Event(), asyncio.Event()
        task = asyncio.create_task(fixture.route(first))
        # A missing fetch must fail immediately rather than hang this regression.
        await asyncio.wait_for(first.fetch_entered.wait(), .2)
        try:
            with self.assertRaises(AssertionError):
                await fixture.route(concurrent)
            self.assertEqual(concurrent.events, [])
        finally:
            first.fetch_release.set()
            await task
        self.assertEqual(fixture.lost_response_count, 1)

    async def test_fetch_failure_and_non_checkout_status_never_count_as_loss(self):
        for status in (202, 400, 500):
            with self.subTest(status=status):
                fixture, route = self.fixture(), CheckoutRoute(status=status)
                with self.assertRaises(AssertionError):
                    await fixture.route(route)
                self.assertEqual(route.events, ['fetch'])
                self.assertEqual(fixture.lost_response_count, 0)
        fixture, route = self.fixture(), CheckoutRoute(failure=RuntimeError('transport failed'))
        with self.assertRaises(RuntimeError):
            await fixture.route(route)
        self.assertEqual(route.events, ['fetch'])
        self.assertEqual(fixture.lost_response_count, 0)

    async def test_malformed_json_and_failed_abort_never_count_as_completed_loss(self):
        fixture, route = self.fixture(), CheckoutRoute()
        route.fetched_response.json_error = json.JSONDecodeError('invalid JSON', '', 0)
        with self.assertRaises(json.JSONDecodeError):
            await fixture.route(route)
        self.assertEqual(route.events, ['fetch', 'json'])
        self.assertEqual(fixture.lost_response_count, 0)
        fixture, route = self.fixture(), CheckoutRoute()
        route.abort_error = RuntimeError('browser closed before abort completed')
        with self.assertRaises(RuntimeError):
            await fixture.route(route)
        self.assertEqual(route.events, ['fetch', 'json', 'abort'])
        self.assertEqual(fixture.lost_response_count, 0)

    async def test_invalid_checkout_response_fails_before_browser_abort(self):
        valid = CheckoutRoute().fetched_response.data
        variants = [None, [], {}, dict(valid, version='v2'), dict(valid, state='processing'),
            dict(valid, configuration_id=smoke.OTHER), dict(valid, region='CA'),
            dict(valid, order_id='invalid'), dict(valid, order_id=None),
            dict(valid, checkout_url='https://checkout.stripe.com.evil/c/pay/cs_test_'+'a'*32+'#fidkdFixtureFragment'),
            dict(valid, checkout_url='https://checkout.stripe.com/c/pay/fixture'),
            dict(valid, checkout_url='https://checkout.stripe.com/c/pay/cs_test_'+'a'*32+'?token=x'),
            dict(valid, checkout_url='https://evil.invalid/c/pay/cs_test_'+'a'*32)]
        for data in variants:
            with self.subTest(data=data):
                fixture, route = self.fixture(), CheckoutRoute()
                route.fetched_response.data = data
                with self.assertRaises(AssertionError):
                    await fixture.route(route)
                self.assertEqual(route.events, ['fetch', 'json'])
                self.assertEqual(fixture.lost_response_count, 0)

    async def test_invalid_key_and_body_never_reach_api(self):
        for kwargs in ({'key': None}, {'key': 'not-a-uuid'}, {'body': '{}'}, {'body': 'not-json'},
                       {'body': '[]'}, {'body': json.dumps({'configuration_id': 'bad', 'region': 'US'})}):
            with self.subTest(kwargs=kwargs):
                fixture, route = self.fixture(), CheckoutRoute(**kwargs)
                with self.assertRaises(AssertionError):
                    await fixture.route(route)
                self.assertEqual(route.events, [])
                self.assertEqual(fixture.lost_response_count, 0)

    async def test_changed_retry_key_or_exact_body_never_reaches_api(self):
        for kwargs in ({'key': '77777777-7777-4777-8777-777777777777'},
                       {'body': CheckoutRoute().request.post_data + ' '},
                       {'body': json.dumps({'configuration_id': smoke.OTHER, 'region': 'US'})}):
            with self.subTest(kwargs=kwargs):
                fixture = self.fixture()
                await fixture.route(CheckoutRoute())
                retry = CheckoutRoute(**kwargs)
                with self.assertRaises(AssertionError):
                    await fixture.route(retry)
                self.assertEqual(retry.events, [])
                self.assertEqual(fixture.lost_response_count, 1)

    async def test_changed_actual_retry_order_or_session_is_never_forwarded(self):
        valid = CheckoutRoute().fetched_response.data
        for data in (dict(valid, order_id=smoke.OTHER),
                     dict(valid, checkout_url='https://checkout.stripe.com/c/pay/cs_test_'+'b'*32+'#fidkdFixtureFragment'),
                     dict(valid, checkout_url='https://checkout.stripe.com/c/pay/cs_test_'+'a'*32+'#changed-fragment')):
            with self.subTest(data=data):
                fixture = self.fixture()
                await fixture.route(CheckoutRoute())
                retry = CheckoutRoute(data=data)
                with self.assertRaises(AssertionError):
                    await fixture.route(retry)
                self.assertEqual(retry.events, ['fetch', 'json'])
                self.assertEqual(fixture.lost_response_count, 1)

    async def test_pending_durability_rejects_duplicates_grants_or_changed_provider_session(self):
        fixture = self.fixture()
        await fixture.route(CheckoutRoute())
        measure = dict(workshop_orders=1, workshop_checkout_requests=1, entitlements=0,
            orders=[dict(order_id=smoke.ORDER, state='open', configuration_id=smoke.CONFIG, region='US')])
        snapshot = dict(payment_calls=1, paid_rows={'workshop_orders': [dict(order_id=smoke.ORDER,
            status='open', configuration_id=smoke.CONFIG, region='US', checkout_session_id='cs_test_'+'a'*32)],
            'entitlements': []})
        fixture.validate_pending_checkout(measure, snapshot)
        await fixture.route(CheckoutRoute())
        fixture.validate_pending_checkout(measure, snapshot, snapshot)
        for field, value in (('workshop_orders', 2), ('workshop_checkout_requests', 2), ('entitlements', 1),
                             ('orders', [dict(measure['orders'][0], state='processing')]),
                             ('orders', [dict(measure['orders'][0], order_id=smoke.OTHER)])):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                fixture.validate_pending_checkout(dict(measure, **{field: value}), snapshot)
        for mutate in (
            lambda s: s.update(payment_calls=2),
            lambda s: s['paid_rows']['workshop_orders'][0].update(checkout_session_id='cs_test_'+'b'*32),
            lambda s: s['paid_rows']['workshop_orders'].append(s['paid_rows']['workshop_orders'][0]),
            lambda s: s['paid_rows']['entitlements'].append({'id': 'unexpected'}),
        ):
            changed = copy.deepcopy(snapshot)
            mutate(changed)
            with self.assertRaises(AssertionError):
                fixture.validate_pending_checkout(measure, changed, snapshot)


class DTOActionTimeout(Exception):
    pass


class DTOLocator:
    def __init__(self, page, selector):
        self.page, self.selector = page, selector
        self.first = self

    async def select_option(self, value):
        self.page.selections.append((self.selector, value))

    async def click(self):
        self.page.clicks += 1
        self.page.context.fixture.requests.append({'method': 'GET', 'path': '/v1/catalog/years',
            'query': {'region': ['US'], 'id_token': ['do-not-retain']}})
        if self.page.mode != 'passed': self.page.errors('synthetic-page-error')
        self.page.click_entered.set()
        if self.page.mode == 'action_timeout':
            raise DTOActionTimeout('Locator.click: timed out\nCall log: waiting for element stability')
        if self.page.mode == 'held':
            await self.page.release.wait()

    def filter(self, **kwargs): return self
    def nth(self, index): return self
    async def wait_for(self): pass


class DTOPage:
    def __init__(self, context, mode):
        self.context, self.mode = context, mode
        self.selections, self.clicks = [], 0
        self.click_entered, self.release = asyncio.Event(), asyncio.Event()
        self.screenshot_error = None
        self.screenshot_delay = 0

    def on(self, name, callback):
        assert name == 'pageerror'
        self.errors = callback

    async def goto(self, url): pass
    def locator(self, selector): return DTOLocator(self, selector)

    async def screenshot(self, *, path, timeout):
        if self.screenshot_delay: await asyncio.sleep(self.screenshot_delay)
        if self.screenshot_error: raise self.screenshot_error
        Path(path).write_bytes(b'owned synthetic screenshot')


class DTOTrace:
    def __init__(self):
        self.started = False
        self.start_error = self.stop_error = None
        self.size = 8
        self.omit_export = False
        self.exported = False
        self.stop_entered, self.release = asyncio.Event(), asyncio.Event()
        self.hold = False
        self.resist_cancel = False

    async def start(self, *, screenshots, snapshots, sources):
        assert screenshots and snapshots and not sources
        if self.start_error: raise self.start_error
        self.started = True

    async def stop(self, *, path=None):
        self.stop_entered.set()
        if self.hold:
            try: await self.release.wait()
            except asyncio.CancelledError:
                if not self.resist_cancel: raise
                await self.release.wait()
        if self.stop_error: raise self.stop_error
        if path and not self.omit_export:
            self.exported = True
            with Path(path).open('wb') as stream: stream.truncate(self.size)


class DTOContext:
    def __init__(self, mode='action_timeout'):
        self.tracing, self.page = DTOTrace(), DTOPage(self, mode)
        self.closed = False
        self.close_hold = False
        self.close_delay = 0
        self.trace_existed_at_close = False
        self.close_release = asyncio.Event()
        self.close_entered = asyncio.Event()
        self.action_timeout = self.navigation_timeout = None

    def set_default_timeout(self, timeout): self.action_timeout = timeout
    def set_default_navigation_timeout(self, timeout): self.navigation_timeout = timeout
    async def route(self, pattern, callback): self.fixture = callback.__self__
    async def new_page(self): return self.page
    async def close(self):
        self.close_entered.set()
        self.trace_existed_at_close = self.tracing.exported
        if self.close_delay: await asyncio.sleep(self.close_delay)
        if self.close_hold: await self.close_release.wait()
        self.closed = True


class DTOBrowser:
    def __init__(self, context): self.context = context
    async def new_context(self, **kwargs): return self.context


class DTOExpectation:
    async def to_contain_text(self, value): pass
    async def to_have_text(self, value): pass


class BrowserDTOTimeoutDiagnostics(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory()
        self.output = Path(self.directory.name) / 'webkit'
        self.api = patch.dict(sys.modules, {'playwright.async_api': SimpleNamespace(
            expect=lambda locator: DTOExpectation(), TimeoutError=DTOActionTimeout)})
        self.api.start()
        self.contexts = []

    async def asyncTearDown(self):
        for context in self.contexts:
            context.page.release.set(); context.tracing.release.set(); context.close_release.set()
        pending = list(getattr(smoke, '_DTO_PENDING_TASKS', ()))
        if pending: await asyncio.wait(pending, timeout=0.2)
        self.api.stop()
        self.directory.cleanup()

    def context(self, mode='action_timeout'):
        context = DTOContext(mode); self.contexts.append(context); return context

    async def execute(self, context, **kwargs):
        self.assertTrue(callable(getattr(smoke, 'run_dto_case', None)),
            'DTO timeout wrapper must retain failure diagnostics')
        return await smoke.run_dto_case(DTOBrowser(context), 'https://127.0.0.1:32001',
            'bankone-cascade', self.output, **kwargs)

    def assert_failed_evidence(self, result, kind):
        self.assertEqual(result['status'], 'failed')
        diagnostics = result['diagnostics']
        self.assertEqual(diagnostics['failure_kind'], kind)
        self.assertEqual(diagnostics['failure_stage'], 'article.open.click')
        self.assertEqual(diagnostics['requests'], [{'method': 'GET', 'path': '/v1/catalog/years',
            'query': {'region': ['US']}}])
        self.assertEqual(diagnostics['errors'], ['synthetic-page-error'])
        self.assertNotIn('do-not-retain', json.dumps(result))
        with self.assertRaises(ValueError):
            smoke.validate_results([dict(browser='webkit', scenario='bankone-cascade', **result)],
                [('webkit', 'bankone-cascade')])
        stored = json.loads((self.output / 'bankone-cascade-failure.json').read_text())
        self.assertEqual(stored['status'], 'failed')
        self.assertEqual(stored['diagnostics']['failure_stage'], 'article.open.click')

    async def test_inner_action_timeout_keeps_call_log_and_trace(self):
        context = self.context()
        result = await self.execute(context)
        self.assert_failed_evidence(result, 'action_timeout')
        self.assertIn('Call log: waiting for element stability', result['error'])
        self.assertEqual(result['diagnostics']['trace_status'], 'retained')
        self.assertTrue((self.output / 'bankone-cascade-failure-trace.zip').is_file())
        self.assertEqual(context.page.clicks, 1)
        self.assertEqual((context.action_timeout, context.navigation_timeout), (10000, 10000))
        self.assertTrue(context.closed)
        for path in self.output.iterdir(): self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)

    async def test_outer_timeout_retains_actual_stage_observations_and_failure(self):
        context = self.context('held')
        result = await self.execute(context, case_timeout=0.03)
        self.assert_failed_evidence(result, 'case_timeout')
        self.assertTrue(context.page.click_entered.is_set())
        self.assertEqual(context.page.clicks, 1)
        self.assertEqual(result['diagnostics']['trace_status'], 'retained')
        self.assertLess(result['diagnostics']['execution_elapsed_seconds'], 0.5)

    async def test_external_cancellation_propagates_after_retaining_diagnostics(self):
        context = self.context('held')
        self.assertTrue(callable(getattr(smoke, 'run_dto_case', None)))
        task = asyncio.create_task(self.execute(context))
        await asyncio.wait_for(context.page.click_entered.wait(), timeout=0.2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        stored = json.loads((self.output / 'bankone-cascade-failure.json').read_text())
        self.assertEqual(stored['diagnostics']['failure_kind'], 'cancelled')
        self.assertTrue(context.closed)

    async def test_cancellation_resistant_trace_and_stalled_close_are_bounded(self):
        context = self.context()
        context.tracing.hold = context.tracing.resist_cancel = context.close_hold = True
        start = asyncio.get_running_loop().time()
        result = await asyncio.wait_for(self.execute(context, cleanup_timeout=0.05), timeout=0.5)
        self.assert_failed_evidence(result, 'action_timeout')
        self.assertLess(asyncio.get_running_loop().time() - start, 0.3)
        self.assertLess(result['diagnostics']['cleanup_elapsed_seconds'], 0.2)
        self.assertEqual(result['diagnostics']['trace_status'], 'timeout')
        self.assertTrue(result['diagnostics']['diagnostic_errors'])
        context.tracing.release.set(); context.close_release.set()
        pending = list(smoke._DTO_PENDING_TASKS)
        if pending: await asyncio.wait(pending, timeout=0.2)
        self.assertFalse((self.output / 'bankone-cascade-failure-trace.zip').exists(),
            'a late trace export must not recreate an unbounded artifact')

    async def test_screenshot_and_trace_errors_preserve_primary_timeout(self):
        context = self.context()
        context.page.screenshot_error = RuntimeError('screenshot unavailable')
        context.tracing.stop_error = RuntimeError('trace unavailable')
        result = await self.execute(context)
        self.assert_failed_evidence(result, 'action_timeout')
        self.assertIn('element stability', result['error'])
        self.assertEqual(result['diagnostics']['trace_status'], 'failed')
        self.assertEqual(len(result['diagnostics']['diagnostic_errors']), 2)

    async def test_oversize_trace_is_removed_without_losing_failure(self):
        context = self.context(); context.tracing.size = 16 * 1024 * 1024 + 1
        result = await self.execute(context)
        self.assert_failed_evidence(result, 'action_timeout')
        self.assertEqual(result['diagnostics']['trace_status'], 'oversize')
        self.assertFalse((self.output / 'bankone-cascade-failure-trace.zip').exists())

    async def test_trace_start_failure_is_explicit_and_never_executes_scenario(self):
        context = self.context(); context.tracing.start_error = RuntimeError('cannot start trace')
        result = await self.execute(context)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['diagnostics']['failure_stage'], 'trace.start')
        self.assertEqual(result['diagnostics']['trace_status'], 'start_failed')
        self.assertEqual(result['diagnostics']['requests'], [])
        self.assertEqual(context.page.clicks, 0)
        self.assertTrue(context.closed)

    async def test_passing_case_deletes_trace_after_close_and_keeps_success_fields(self):
        context = self.context('passed')
        result = await self.execute(context)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['sdk_requests'], 0)
        self.assertEqual(context.page.clicks, 1)
        self.assertTrue(context.closed)
        self.assertFalse(list(self.output.glob('*')))
        smoke.validate_results([dict(browser='webkit', scenario='bankone-cascade', **result)],
            [('webkit', 'bankone-cascade')])

    async def test_successful_case_with_failed_cleanup_cannot_pass(self):
        context = self.context('passed'); context.tracing.stop_error = RuntimeError('cannot stop trace')
        result = await self.execute(context)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['diagnostics']['trace_status'], 'failed')

    async def test_close_longer_than_one_second_uses_remaining_shared_budget(self):
        context = self.context('passed'); context.close_delay = 1.1
        result = await self.execute(context)
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(context.closed)
        self.assertTrue(context.trace_existed_at_close)
        self.assertFalse(list(self.output.glob('*')))

    async def test_cleanup_only_close_timeout_retains_preclose_trace(self):
        context = self.context('passed'); context.close_hold = True
        start = asyncio.get_running_loop().time()
        result = await self.execute(context, cleanup_timeout=0.05)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['diagnostics']['failure_stage'], 'context.close')
        self.assertEqual(result['diagnostics']['trace_status'], 'retained')
        self.assertTrue((self.output / 'bankone-cascade-failure-trace.zip').is_file())
        self.assertTrue(context.trace_existed_at_close)
        self.assertEqual(context.page.clicks, 1)
        self.assertLess(asyncio.get_running_loop().time() - start, .3)
        with self.assertRaises(ValueError):
            smoke.validate_results([dict(browser='webkit', scenario='bankone-cascade', **result)],
                [('webkit', 'bankone-cascade')])

    async def test_missing_empty_or_oversize_trace_cannot_pass_scenario_success(self):
        for size, omit, status in [(8, True, 'missing'), (0, False, 'empty'),
                                    (16 * 1024 * 1024 + 1, False, 'oversize')]:
            with self.subTest(status=status):
                context = self.context('passed'); context.tracing.size = size
                context.tracing.omit_export = omit
                result = await self.execute(context)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['diagnostics']['failure_stage'], 'trace.stop')
                self.assertEqual(result['diagnostics']['trace_status'], status)
                self.assertFalse((self.output / 'bankone-cascade-failure-trace.zip').exists())
                self.assertTrue(context.closed)

    async def test_trace_deletion_failure_keeps_zip_and_failed_row(self):
        context = self.context('passed')
        original = Path.unlink
        def fail_owned_trace(path, *args, **kwargs):
            if path.name.endswith('-failure-trace.zip'):
                raise OSError('owned trace deletion denied')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail_owned_trace):
            result = await self.execute(context)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['diagnostics']['failure_stage'], 'trace.delete')
        self.assertEqual(result['diagnostics']['trace_status'], 'retained')
        self.assertTrue((self.output / 'bankone-cascade-failure-trace.zip').exists())
        self.assertTrue(context.closed)

    async def test_trace_export_time_subtracts_from_close_budget(self):
        context = self.context('passed'); context.tracing.hold = context.close_hold = True
        start = asyncio.get_running_loop().time()
        async def release_export():
            await context.tracing.stop_entered.wait()
            await asyncio.sleep(.12)
            context.tracing.release.set()
        release = asyncio.create_task(release_export())
        result = await self.execute(context, cleanup_timeout=.2)
        await release
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['diagnostics']['failure_stage'], 'context.close')
        self.assertEqual(result['diagnostics']['trace_status'], 'retained')
        self.assertLess(asyncio.get_running_loop().time() - start, .28)

    async def test_screenshot_and_export_keep_individual_one_second_caps(self):
        context = self.context(); context.page.screenshot_delay = 1.5
        context.tracing.hold = True
        start = asyncio.get_running_loop().time()
        result = await self.execute(context)
        elapsed = asyncio.get_running_loop().time() - start
        self.assert_failed_evidence(result, 'action_timeout')
        self.assertEqual(result['diagnostics']['trace_status'], 'timeout')
        self.assertEqual(len(result['diagnostics']['diagnostic_errors']), 2)
        self.assertTrue(context.closed)
        self.assertGreater(elapsed, 1.8)
        self.assertLess(elapsed, 2.5)

    async def test_cancellation_during_close_retains_trace_and_propagates(self):
        context = self.context('passed'); context.close_hold = True
        task = asyncio.create_task(self.execute(context))
        await asyncio.wait_for(context.close_entered.wait(), timeout=.2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        stored = json.loads((self.output / 'bankone-cascade-failure.json').read_text())
        self.assertEqual(stored['diagnostics']['failure_kind'], 'cancelled')
        self.assertEqual(stored['diagnostics']['failure_stage'], 'context.close')
        self.assertEqual(stored['diagnostics']['trace_status'], 'retained')
        self.assertTrue((self.output / 'bankone-cascade-failure-trace.zip').is_file())

    async def test_failed_export_and_failed_deletion_keep_primary_timeout_and_close(self):
        context = self.context(); context.tracing.stop_error = RuntimeError('trace export unavailable')
        original = Path.unlink
        def fail_owned_trace(path, *args, **kwargs):
            if path.name.endswith('-failure-trace.zip'):
                raise OSError('failed export deletion denied')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail_owned_trace):
            result = await self.execute(context)
        self.assert_failed_evidence(result, 'action_timeout')
        self.assertIn('element stability', result['error'])
        self.assertEqual(result['diagnostics']['trace_status'], 'failed')
        self.assertTrue(any('failed export deletion denied' in error
            for error in result['diagnostics']['diagnostic_errors']))
        self.assertTrue(context.closed)

    async def test_late_export_deletion_error_persists_after_wrapper_return(self):
        context = self.context(); context.tracing.hold = context.tracing.resist_cancel = True
        original = Path.unlink
        def fail_owned_trace(path, *args, **kwargs):
            if path.name.endswith('-failure-trace.zip') and path.exists():
                raise OSError('late export deletion denied')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail_owned_trace):
            result = await self.execute(context, cleanup_timeout=.03)
            self.assert_failed_evidence(result, 'action_timeout')
            context.tracing.release.set()
            pending = list(smoke._DTO_PENDING_TASKS)
            if pending: await asyncio.wait(pending, timeout=.2)
            # Allow the completion callback to publish the late cleanup error.
            await asyncio.sleep(0)
        self.assertTrue((self.output / 'bankone-cascade-failure-trace.zip').exists())
        self.assertTrue(any('late export deletion denied' in error
            for error in result['diagnostics']['diagnostic_errors']))
        stored = json.loads((self.output / 'bankone-cascade-failure.json').read_text())
        self.assertTrue(any('late export deletion denied' in error
            for error in stored['diagnostics']['diagnostic_errors']))
        self.assertEqual(stored['diagnostics']['failure_stage'], 'article.open.click')
        self.assertEqual(stored['diagnostics']['failure_kind'], 'action_timeout')
        self.assertIn('element stability', stored['error'])

    async def test_late_context_creation_is_closed_in_tracked_bounded_task(self):
        context=self.context();release=asyncio.Event()
        class Browser:
            async def new_context(self,**kwargs):
                try:await release.wait()
                except asyncio.CancelledError:await release.wait()
                return context
        try:
            result=await smoke.run_dto_case(Browser(),'https://localhost:1','bankone-cascade',self.output,case_timeout=.01,cleanup_timeout=.03)
            self.assertEqual(result['status'],'failed');self.assertEqual(result['diagnostics']['failure_stage'],'context.create')
            release.set()
            await asyncio.wait_for(context.close_entered.wait(),timeout=.2)
            await asyncio.sleep(0)
            self.assertTrue(context.closed);self.assertFalse(hasattr(context,'fixture'))
        finally:release.set()

    async def test_dto_browser_shutdown_cannot_hang_acceptance(self):
        self.assertTrue(callable(getattr(smoke, 'close_dto_browser', None)))
        close_entered, release = asyncio.Event(), asyncio.Event()
        async def close():
            close_entered.set()
            try: await release.wait()
            except asyncio.CancelledError: await release.wait()
        try:
            with self.assertRaisesRegex(RuntimeError, 'shutdown'):
                await asyncio.wait_for(smoke.close_dto_browser(SimpleNamespace(close=close), timeout=0.03), timeout=0.2)
            self.assertTrue(close_entered.is_set())
        finally: release.set()


class DTOTimingContract(unittest.TestCase):
    def test_complete_inventory_budget_and_equal_deadline(self):
        timing = smoke.load_dto_timing(smoke.FIXTURES / 'timing.json')
        self.assertEqual(smoke.validate_dto_schedule(timing, 120), dict(serial_seconds=2994,
            parent_total_seconds=4430, fixture_requirement_seconds=4640, go_requirement_seconds=4980))
        self.assertEqual(smoke.remaining(12., 12.), 0)
        for count in (0, 40, 119, 121):
            with self.assertRaises(ValueError): smoke.validate_dto_schedule(timing, count)

    def test_invalid_contract_fails_closed(self):
        timing = smoke.load_dto_timing(smoke.FIXTURES / 'timing.json')
        invalid = [dict(timing, unknown=1), dict(timing, version='v2')]
        for value in (True, 0, -1, 1.5, float('nan'), float('inf')):
            invalid.append(dict(timing, worker_hard_seconds=value))
        missing = dict(timing); del missing['worker_hard_seconds']; invalid.append(missing)
        for field, value in [('worker_hard_seconds',2994), ('producer_hard_seconds',4430),
                ('dto_fixture_seconds',4640), ('go_test_seconds',4980), ('ci_exercise_seconds',5060)]:
            invalid.append(dict(timing, **{field:value}))
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError): smoke.validate_dto_schedule(value,120)
        with TemporaryDirectory() as directory:
            path=Path(directory)/'timing.json'; path.write_text('{"version":"v1","version":"v1"}')
            with self.assertRaises(ValueError): smoke.load_dto_timing(path)


class DTOLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.timing=smoke.load_dto_timing(smoke.FIXTURES/'timing.json')
        self.now=0.; self.actions=[]; self.snapshots=[]; self.failure=None
        owner=self
        class Lifecycle:
            evidence={'candidate_sha':'a'*40, 'input_sha256':{'timing':'b'*64}}
            async def start(self): owner.actions.append('start'); return self
            async def launch(self,engine,timeout):
                owner.actions.append(('launch',engine,timeout))
                if owner.failure=='launch': raise TimeoutError('uncertain launch')
                return SimpleNamespace(version='fake')
            async def case(self,browser,name,output):
                owner.actions.append(('case',name)); return {'status':'passed'}
            async def close(self,browser):owner.actions.append('close')
            async def stop(self):
                owner.actions.append('stop')
                if owner.failure=='stop':raise TimeoutError('stop held')
        self.lifecycle=Lifecycle()
        self.args=SimpleNamespace(browser='all',output='/unused',candidate_sha='a'*40,mode='dto-fixture')
    async def phase(self,awaitable,seconds,**kwargs):
        return await awaitable
    async def persist(self,evidence):self.snapshots.append(copy.deepcopy(evidence));return True
    async def execute(self):
        return await smoke.run_dto_inventory(self.args,clock=lambda:self.now,lifecycle=self.lifecycle,
            persist=self.persist,timing=self.timing,bounded=self.phase)
    async def test_full_inventory_and_explicit_lifecycle(self):
        evidence=await self.execute()
        self.assertEqual(len(evidence['results']),120)
        self.assertTrue(all(row['status']=='passed' for row in evidence['results']))
        self.assertEqual(self.actions[0],'start');self.assertEqual(self.actions[-1],'stop')
        self.assertEqual([x for x in self.actions if isinstance(x,tuple) and x[0]=='launch'],
            [('launch','chromium',15000),('launch','firefox',15000),('launch','webkit',15000)])
        self.assertGreaterEqual(len(self.snapshots),120)
        self.assertEqual(evidence['cleanup_status'],'verified')
    async def test_complete_120_worst_cost_schedule_approaches_2994(self):
        # Hand-derived envelope: 150+10+45+120*23+9+10+10 = 2994.
        self.now=150.;epsilon=.000001
        original_case=self.lifecycle.case
        async def case(*args):
            result=await original_case(*args);self.now+=23-epsilon;return result
        self.lifecycle.case=case
        async def persist(evidence):
            self.now+=10/126-epsilon
            self.snapshots.append(copy.deepcopy(evidence));return True
        self.persist=persist
        async def cost_phase(awaitable,seconds,**kwargs):
            name=awaitable.cr_code.co_name
            result=await awaitable
            if name in ('start','launch','close','stop'):
                self.now+=dict(start=10,launch=15,close=3,stop=10)[name]-epsilon
            return result
        self.phase=cost_phase
        evidence=await self.execute()
        self.assertEqual(len(evidence['results']),120);self.assertTrue(all(r['status']=='passed' for r in evidence['results']))
        self.assertEqual(len(self.snapshots),126);self.assertLess(self.now,2994);self.assertGreater(self.now,2993.99)
    async def test_third_engine_exact_launch_deadline_stops_new_cases(self):
        async def edge(awaitable,seconds,**kwargs):
            name=awaitable.cr_code.co_name;result=await awaitable
            if name=='launch' and len([a for a in self.actions if isinstance(a,tuple) and a[0]=='launch'])==3:
                self.now+=15
            return result
        self.phase=edge;evidence=await self.execute()
        self.assertEqual(len([a for a in self.actions if isinstance(a,tuple) and a[0]=='case']),80)
        self.assertTrue(all(r['status']=='failed' for r in evidence['results']))
        self.assertEqual(evidence['results'][79]['observed_case_result']['status'],'passed')
        self.assertNotIn('observed_case_result',evidence['results'][80])

    async def test_global_stop_failure_preserves_observations(self):
        self.failure='stop';evidence=await self.execute()
        self.assertEqual(len(evidence['results']),120)
        self.assertTrue(all(row['status']=='failed' for row in evidence['results']))
        self.assertEqual(evidence['results'][0]['observed_case_result']['status'],'passed')
        with self.assertRaises(ValueError):smoke.validate_results(evidence['results'],[(e,n) for e in smoke.ENGINES for n in smoke.inventory()])
    async def test_uncertain_launch_stops_engine_admission(self):
        self.failure='launch';evidence=await self.execute()
        self.assertEqual(len([x for x in self.actions if isinstance(x,tuple) and x[0]=='launch']),1)
        self.assertEqual(evidence['results'][0]['failure_kind'],'not_started_after_lifecycle_failure')
        self.assertEqual(evidence['cleanup_status'],'unverified')
    async def test_native_playwright_launch_timeout_stops_engine_admission(self):
        # Playwright's timeout derives from its own Error, not built-in TimeoutError.
        class NativeTimeoutError(Exception): pass
        async def launch(engine,timeout):
            self.actions.append(('launch',engine,timeout))
            raise NativeTimeoutError('BrowserType.launch: Timeout 15000ms exceeded')
        self.lifecycle.launch=launch
        with patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(TimeoutError=NativeTimeoutError)}):
            evidence=await self.execute()
        self.assertEqual([a for a in self.actions if isinstance(a,tuple) and a[0]=='launch'],
            [('launch','chromium',15000)])
        self.assertEqual(len(evidence['results']),120)
        self.assertTrue(all(row['status']=='failed' for row in evidence['results']))
        self.assertEqual(evidence['failure_stage'],'engine.launch')
        self.assertEqual(evidence['error'],'BrowserType.launch: Timeout 15000ms exceeded')
        self.assertEqual(evidence['cleanup_status'],'unverified')
        self.assertEqual(self.actions[-1],'stop')
    async def test_late_launch_closes_returned_browser_without_new_engine(self):
        release=asyncio.Event();closed=asyncio.Event()
        async def close():closed.set()
        async def late_launch(engine,timeout):
            self.actions.append(('launch',engine,timeout))
            while not release.is_set():
                try:await release.wait()
                except asyncio.CancelledError:pass
            return SimpleNamespace(version='fake',close=close)
        self.lifecycle.launch=late_launch
        async def short_bound(awaitable,seconds,**kwargs):return await smoke._dto_bounded(awaitable,.01,**kwargs)
        self.phase=short_bound
        try:
            evidence=await self.execute()
            self.assertTrue(all(row['status']=='failed' for row in evidence['results']))
            self.assertEqual(len([a for a in self.actions if isinstance(a,tuple) and a[0]=='launch']),1)
            release.set();await asyncio.wait_for(closed.wait(),timeout=.2)
        finally:
            release.set()
            tasks=list(smoke._DTO_PENDING_TASKS)
            if tasks:await asyncio.wait(tasks,timeout=.2)

    async def test_cumulative_persistence_and_backward_clock(self):
        async def slow(evidence): self.now+=6;return True
        self.persist=slow;evidence=await self.execute()
        self.assertEqual(evidence['failure_stage'],'persistence')
        self.assertTrue(all(row['status']=='failed' for row in evidence['results']))
        self.now=0
        async def backwards(evidence):self.now-=1;return True
        self.persist=backwards;evidence=await self.execute()
        self.assertEqual(evidence['failure_kind'],'clock_or_lifecycle_failure')
    async def test_primary_cancellation_survives_secondary_close_failure(self):
        async def cancelled(*args):
            error=asyncio.CancelledError('original external cancellation')
            error.dto_diagnostics=SimpleNamespace(error='original external cancellation',snapshot=lambda:dict(requests=[{'path':'/original'}],trace_path='raw.zip'))
            raise error
        async def failed_close(*args):raise RuntimeError('secondary close failure')
        self.lifecycle.case=cancelled;self.lifecycle.close=failed_close
        with self.assertRaisesRegex(asyncio.CancelledError,'original external cancellation'):await self.execute()
        final=self.snapshots[-1]
        self.assertEqual(final['failure_stage'],'case');self.assertEqual(final['failure_kind'],'cancelled')
        self.assertEqual(final['results'][0]['observed_case_result']['diagnostics']['trace_path'],'raw.zip')
        self.assertTrue(any('secondary close failure' in entry for entry in final['secondary_errors']))

    async def test_cancellation_in_each_phase_is_sticky_and_stages_failed_inventory(self):
        for phase in ('start','launch','case','close','stop','persist'):
            with self.subTest(phase=phase):
                self.snapshots=[];self.actions=[];self.now=0
                lifecycle=self.lifecycle
                target=self.persist if phase=='persist' else getattr(lifecycle,phase)
                calls=0
                async def cancel_once(*args,**kwargs):
                    nonlocal calls
                    calls+=1
                    if calls==1:raise asyncio.CancelledError('first cancellation')
                    return await target(*args,**kwargs)
                if phase=='persist':self.persist=cancel_once
                else:setattr(lifecycle,phase,cancel_once)
                try:
                    with self.assertRaises(asyncio.CancelledError):await self.execute()
                    self.assertTrue(self.snapshots)
                    self.assertTrue(all(row['status']=='failed' for row in self.snapshots[-1]['results']))
                    self.assertEqual(self.snapshots[-1]['failure_kind'],'cancelled')
                    self.assertEqual(self.snapshots[-1]['error'],'first cancellation')
                finally:
                    if phase=='persist':self.persist=target
                    else:setattr(lifecycle,phase,target)

    def test_failure_rows_preserve_original_diagnostics_and_order(self):
        ids=[(e,n) for e in smoke.ENGINES for n in smoke.inventory()]
        observed=[dict(browser=ids[0][0],scenario=ids[0][1],status='failed',error='primary',
            diagnostics={'requests':[{'path':'/original'}],'trace_path':'raw.zip'})]
        rows=smoke.complete_dto_failure(ids,observed,stage='stop',kind='timeout',cleanup='unverified')
        self.assertEqual([(r['browser'],r['scenario']) for r in rows],ids)
        self.assertEqual(rows[0]['observed_case_result'],observed[0]);self.assertEqual(rows[0]['error'],'primary')
        self.assertEqual(rows[0]['diagnostics'],observed[0]['diagnostics'])
        self.assertNotIn('elapsed_seconds',rows[1]);self.assertNotIn('requests',rows[1])


class DTOPlaywrightAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_adapter_stops_returned_playwright_not_context_manager(self):
        actions=[]
        async def stop():actions.append('playwright.stop')
        class Manager:
            async def start(self):actions.append('manager.start');return SimpleNamespace(stop=stop)
            async def __aexit__(self,*args):actions.append('manager.exit')
        manager=Manager()
        with patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(async_playwright=lambda:manager)}):
            lifecycle=smoke.DTOPlaywrightLifecycle(SimpleNamespace(),{})
            await lifecycle.start();await lifecycle.stop()
        self.assertEqual(actions,['manager.start','playwright.stop'])
    async def test_uncertain_start_uses_context_manager_exit(self):
        actions=[]
        class Manager:
            async def start(self):raise TimeoutError('uncertain start')
            async def __aexit__(self,*args):actions.append('manager.exit')
        with patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(async_playwright=lambda:Manager())}):
            lifecycle=smoke.DTOPlaywrightLifecycle(SimpleNamespace(),{})
            with self.assertRaises(TimeoutError):await lifecycle.start()
            await lifecycle.stop()
        self.assertEqual(actions,['manager.exit'])


class DTOTerminalFenceTests(unittest.TestCase):
    def request_ack(self,attempt,kind='final'):
        request=attempt.request(kind)
        ack=dict(attempt_id=request['attempt_id'],epoch=request['epoch'],stage_nonce=request['stage_nonce'],
            content_sha256='b'*64,byte_length=100,candidate_sha='a'*40,timing_contract_sha256='c'*64,
            input_fingerprint='d'*64,complete=True,cleanup_verified=True)
        return request,ack
    def test_terminal_revocation_rejects_late_and_duplicate_acks(self):
        attempt=smoke.DTOAttempt('1'*32,'a'*40)
        request,ack=self.request_ack(attempt,'init');self.assertTrue(attempt.ack(request,ack));attempt.activate()
        request,ack=self.request_ack(attempt);self.assertTrue(attempt.ack(request,ack))
        self.assertFalse(attempt.ack(request,ack))
        attempt.revoke('timeout');epoch=attempt.epoch
        self.assertFalse(attempt.ack(request,ack));attempt.revoke('late cancel')
        self.assertEqual(attempt.epoch,epoch);self.assertEqual(attempt.reason,'timeout')
        self.assertFalse(attempt.commit_eligible(10,100,False))
    def test_old_attempt_epoch_nonce_hash_length_are_rejected(self):
        for field,value in [('attempt_id','2'*32),('epoch',1),('stage_nonce','2'*32),
                ('content_sha256','short'),('byte_length',0),('candidate_sha','e'*40)]:
            attempt=smoke.DTOAttempt('1'*32,'a'*40);request,ack=self.request_ack(attempt,'init')
            with self.subTest(field=field):self.assertFalse(attempt.ack(request,dict(ack,**{field:value})))
    def test_strict_commit_fence_and_receipt_consumer(self):
        attempt=smoke.DTOAttempt('1'*32,'a'*40);request,ack=self.request_ack(attempt,'init')
        self.assertTrue(attempt.ack(request,ack));attempt.activate()
        request,ack=self.request_ack(attempt);self.assertTrue(attempt.ack(request,ack));attempt.prepare(ack)
        self.assertFalse(attempt.commit_eligible(98,100,False));self.assertFalse(attempt.commit_eligible(1,100,True))
        self.assertTrue(attempt.commit_eligible(97.9,100,False))
        ids=[(e,n) for e in smoke.ENGINES for n in smoke.inventory()]
        evidence=dict(attempt_id='1'*32,epoch=0,candidate_sha='a'*40,timing_contract_sha256='c'*64,
            publication_state='requires_commit_receipt',cleanup_status='verified',input_sha256={'fixture':'e'*64},
            input_fingerprint=smoke.hashlib.sha256(smoke._dto_bytes({'fixture':'e'*64})).hexdigest(),
            results=[dict(browser=e,scenario=n,status='passed') for e,n in ids])
        raw=(json.dumps(evidence,sort_keys=True)+'\n').encode()
        receipt=smoke.dto_receipt(ack,attempt)
        receipt['evidence_sha256']=smoke.hashlib.sha256(raw).hexdigest()
        invocation=dict(attempt_id='1'*32,epoch=0,exit_code=0,terminal_state='COMMITTED')
        self.assertTrue(smoke.accept_dto_success(raw,receipt,invocation=invocation,expected_attempt='1'*32,
            candidate_sha='a'*40,timing_sha256='c'*64,expected=ids,expected_input_sha256={'fixture':'e'*64}))
        for invocation in (None,dict(invocation,exit_code=1),dict(invocation,attempt_id='2'*32)):
            self.assertFalse(smoke.accept_dto_success(raw,receipt,invocation=invocation,expected_attempt='1'*32,
                candidate_sha='a'*40,timing_sha256='c'*64,expected=ids,expected_input_sha256={'fixture':'e'*64}))


class DTOFakeClock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


class DTOSupervisorTests(unittest.TestCase):
    def execute(self,blocked=None,cancel_at=None,commit_seconds=0,progress_at=None,worker_seconds=.1,resist_cleanup=False,ack_transform=None,publish_error=False,progress_seconds=.1):
        clock=DTOFakeClock();actions=[];owner=self;self.handles=[];self.fake_clock=clock;self.cancel_latched=False
        class Handle:
            def __init__(self,kind,request):self.kind,self.request,self.begin=kind,request,clock();self.killed=False;self.closed=False;self.signalled=False
            def poll(self):
                if self.signalled and resist_cleanup:return None
                held=self.kind in blocked if isinstance(blocked,tuple) else self.kind==blocked
                duration=worker_seconds if self.kind=='worker' else (progress_seconds if self.kind=='progress' else .1)
                return 0 if self.killed or (not held and clock()-self.begin>=duration) else None
            def progress_ready(self):return self.kind=='worker' and progress_at is not None and clock()>=progress_at
            def read_ack(self):
                if self.kind=='worker' or self.poll() is None:return None
                r=self.request
                ack=dict(attempt_id=r['attempt_id'],epoch=r['epoch'],stage_nonce=r['stage_nonce'],content_sha256='b'*64,
                    byte_length=100,candidate_sha='a'*40,timing_contract_sha256='c'*64,input_fingerprint='d'*64,
                    complete=True,cleanup_verified=True)
                return ack_transform(self.kind,ack) if ack_transform else ack
            def signal_owned_group(self,kind):
                actions.append((kind,self.kind,owner.attempt.state,clock()));self.killed=kind=='KILL';self.signalled=True
            def close(self):self.closed=True
        def factory(kind,request,args):
            actions.append(('create',kind,clock()));handle=Handle(kind,request);self.handles.append(handle);return handle
        def publish(ack,attempt,success):
            actions.append(('publish',success,attempt.state,clock()));clock.sleep(commit_seconds if success else 0)
            if success and publish_error:raise OSError('publication fsync failed')
            return not (cancel_at is not None and clock()>=cancel_at)
        def observer(attempt):owner.attempt=attempt
        args=SimpleNamespace(output='/unused',candidate_sha='a'*40,browser='all',mode='dto-fixture',base_url='https://localhost:1')
        result=smoke.supervise_dto(args,clock=clock,process_factory=factory,writer_factory=factory,
            timing=smoke.load_dto_timing(smoke.FIXTURES/'timing.json'),sleep=clock.sleep,publisher=publish,
            cancelled=lambda:self.cancel_latched or (cancel_at is not None and clock()>=cancel_at),observer=observer)
        return result,clock,actions
    def test_success_requires_reaped_worker_helpers_and_fenced_parent_commit(self):
        code,clock,actions=self.execute();self.assertEqual(code,0);self.assertEqual(self.attempt.state,'COMMITTED')
        self.assertEqual([a[:2] for a in actions if a[0]=='publish'],[('publish',False),('publish',True)])
    def test_f2_blocked_initialization_never_starts_worker_or_claims_evidence(self):
        code,clock,actions=self.execute(blocked='init')
        self.assertEqual(code,1);self.assertEqual(self.attempt.state,'REVOKED')
        self.assertFalse(any(a[:2]==('create','worker') for a in actions));self.assertFalse(any(a[0]=='publish' for a in actions))
        self.assertLessEqual(clock(),16.1)
    def test_f2_worker_hard_deadline_is_not_delayed_by_reader(self):
        code,clock,actions=self.execute(blocked='worker')
        self.assertEqual(code,1)
        term=next(a for a in actions if a[:2]==('TERM','worker'))
        self.assertEqual(term[2],'REVOKED');self.assertLessEqual(term[3],4381)
        self.assertLessEqual(clock(),4430)
    def test_f1_cancel_and_ambiguous_commit_remain_nonpass(self):
        code,clock,actions=self.execute(cancel_at=.25)
        self.assertEqual(code,1);self.assertFalse(any(a[:2]==('publish',True) for a in actions))
        code,clock,actions=self.execute(commit_seconds=3)
        self.assertEqual(code,1);self.assertEqual(self.attempt.state,'REVOKED')
        self.assertEqual(self.attempt.reason,'commit_uncertain')
    def test_f2_failed_final_helper_is_bounded(self):
        code,clock,actions=self.execute(blocked='final')
        self.assertEqual(code,1);self.assertLessEqual(clock(),4430)
        self.assertTrue(all(a[2]=='REVOKED' for a in actions if a[0] in ('TERM','KILL')))

class FakeStageWriter:
    def __init__(self,request,held_operation='stage.private.rename',output=None):
        self.request=request;self.held_operation=held_operation;self.actions=[];self.output=output
        if output is not None:
            self.target=smoke.dto_stage_path(output,request)
            self.target.parent.mkdir(mode=0o700,parents=True)
            self.pending=self.target.with_suffix('.private-pending')
            self.pending.write_bytes(b'uncommitted observed success')
    def rename_private_and_ack(self):
        path=str(smoke.dto_stage_path('.',self.request))
        self.actions.append((self.held_operation,path))
        if self.output is not None:smoke.os.replace(self.pending,self.target)
        return dict(attempt_id=self.request['attempt_id'],epoch=self.request['epoch'],stage_nonce=self.request['stage_nonce'],
            content_sha256='b'*64,byte_length=100,candidate_sha='a'*40,timing_contract_sha256='c'*64,
            input_fingerprint='d'*64,complete=True,cleanup_verified=True)


class DTORevision2Schedules(DTOSupervisorTests):
    def test_F1_timeout_before_commit_and_late_private_rename_ack(self):
        original=smoke.DTOAttempt.prepare
        def prepare(attempt,ack):
            original(attempt,ack)
            self.fake_clock.now=4438  # Strict producer_deadline-2 commit fence.
        with patch.object(smoke.DTOAttempt,'prepare',prepare):
            code,clock,actions=self.execute()
        self.assertEqual(code,1);self.assertEqual(self.attempt.state,'REVOKED')
        self.assertFalse(any(a[:2]==('publish',True) for a in actions))
        final=next(h for h in self.handles if h.kind=='final')
        # Execute a delayed source-owned writer action after the terminal decision.
        writer=FakeStageWriter(final.request)
        late_ack=writer.rename_private_and_ack()
        self.assertTrue(writer.actions[0][1].startswith('staging/'))
        self.assertFalse(self.attempt.ack(final.request,late_ack))
        self.assertEqual(self.attempt.state,'REVOKED')
    def test_late_stage_rename_executes_after_term_kill_timeout_without_publication(self):
        code,clock,actions=self.execute(blocked='final',resist_cleanup=True)
        self.assertEqual(code,1);self.assertEqual(self.attempt.state,'REVOKED')
        final=next(h for h in self.handles if h.kind=='final')
        self.assertEqual([a[0] for a in actions if len(a)>2 and a[1]=='final' and a[0] in ('TERM','KILL')],['TERM','KILL'])
        with TemporaryDirectory() as directory:
            writer=FakeStageWriter(final.request,output=directory)
            self.assertFalse(writer.target.exists());ack=writer.rename_private_and_ack()
            self.assertTrue(writer.target.exists());self.assertFalse(self.attempt.ack(final.request,ack))
            self.assertFalse((Path(directory)/'evidence.json').exists());self.assertFalse((Path(directory)/'commit.json').exists())
        self.assertFalse(any(a[:2]==('publish',True) for a in actions))
    def test_F1_cancel_before_fence(self):
        code,clock,actions=self.execute(cancel_at=.25)
        self.assertEqual(code,1);self.assertFalse(any(a[:2]==('publish',True) for a in actions))
    def test_cancellation_after_final_ack_immediately_before_commit_fence(self):
        original=smoke.DTOAttempt.prepare
        def prepare(attempt,ack):original(attempt,ack);self.cancel_latched=True
        with patch.object(smoke.DTOAttempt,'prepare',prepare):code,clock,actions=self.execute()
        self.assertEqual(code,1);self.assertEqual(self.attempt.state,'REVOKED')
        self.assertFalse(any(a[:2]==('publish',True) for a in actions))
    def test_cancellation_inside_commit_keeps_nonzero_invocation(self):
        code,clock,actions=self.execute(commit_seconds=.1,cancel_at=.35)
        self.assertEqual(code,1);self.assertEqual(self.attempt.reason,'commit_uncertain')
        self.assertEqual(len([a for a in actions if a[:2]==('publish',True)]),1)
    def test_partial_parent_publication_exception_is_uncertain_without_recovery_publish(self):
        code,clock,actions=self.execute(publish_error=True)
        self.assertEqual(code,1);self.assertEqual(self.attempt.reason,'commit_uncertain')
        self.assertFalse(any(a[:2]==('create','nonpass') for a in actions))
        self.assertEqual([a[:2] for a in actions if a[0]=='publish'],[('publish',False),('publish',True)])
    def test_lost_final_ack_never_commits(self):
        code,clock,actions=self.execute(ack_transform=lambda kind,ack:None if kind=='final' else ack)
        self.assertEqual(code,1);self.assertFalse(any(a[:2]==('publish',True) for a in actions))
    def test_F1_old_attempt_and_epoch_acks(self):
        for field,value in [('attempt_id','2'*32),('epoch',9),('stage_nonce','3'*32)]:
            with self.subTest(field=field):
                code,clock,actions=self.execute(ack_transform=lambda kind,ack:dict(ack,**{field:value}))
                self.assertEqual(code,1);self.assertFalse(any(a[:2]==('create','worker') for a in actions))
    def test_F1_ambiguous_commit(self):
        code,clock,actions=self.execute(commit_seconds=2)
        self.assertEqual(code,1);self.assertEqual(self.attempt.reason,'commit_uncertain')
        self.assertTrue(any(a[:2]==('publish',True) for a in actions))
    def test_F1_receipt_without_exit_zero(self):
        DTOTerminalFenceTests().test_strict_commit_fence_and_receipt_consumer()
    def test_F2_init_read_blocked(self):
        self.assert_blocked_initialization('config.read')
    def test_F2_init_write_blocked(self):
        self.assert_blocked_initialization('initial.stage.write')
    def test_initialization_parse_hash_and_allocation_blocked(self):
        for operation in ('inventory.parse','inventory.hash','directory.allocate'):
            with self.subTest(operation=operation):self.assert_blocked_initialization(operation)
    def assert_blocked_initialization(self,operation):
        code,clock,actions=self.execute(blocked='init',resist_cleanup=True)
        self.assertEqual(code,1);self.assertFalse(any(a[:2]==('create','worker') for a in actions))
        self.assertFalse(any(a[0]=='publish' for a in actions));self.assertLessEqual(clock(),16.01)
        initial=self.handles[0]
        # Independent helper operation is held; completing it after parent cleanup
        # can only materialize a private stage, never initial canonical evidence.
        writer=FakeStageWriter(initial.request,held_operation=operation)
        ack=writer.rename_private_and_ack()
        self.assertEqual(writer.actions[0][0],operation)
        self.assertFalse(self.attempt.ack(initial.request,ack))
        self.assertFalse(any(a[0]=='publish' for a in actions))
    def test_F2_progress_parse_blocked_at_worker_deadline(self):
        code,clock,actions=self.execute(blocked=('worker','progress'),progress_at=4379,resist_cleanup=True)
        self.assertEqual(code,1)
        term=next(a for a in actions if a[:2]==('TERM','worker'))
        self.assertLessEqual(term[3],4380.2);self.assertEqual(term[2],'REVOKED');self.assertLessEqual(clock(),4430)
    def test_progress_ack_at_exact_cumulative_deadline_is_expired(self):
        code,clock,actions=self.execute(progress_at=0,worker_seconds=11,progress_seconds=10)
        self.assertEqual(code,1);self.assertEqual(self.attempt.state,'REVOKED')
        self.assertEqual(self.attempt.reason,'cumulative progress read/parse exhausted')
        self.assertFalse(any(a[:2]==('publish',True) for a in actions))
    def test_F2_two_helper_cleanup_episodes(self):
        code,clock,actions=self.execute(blocked=('progress','nonpass'),progress_at=0,worker_seconds=100,resist_cleanup=True)
        self.assertEqual(code,1)
        helper_terms=[a for a in actions if a[0]=='TERM' and a[1]!='worker']
        self.assertEqual([a[1] for a in helper_terms],['progress','nonpass'])
        helper_kills=[a for a in actions if a[0]=='KILL' and a[1]!='worker']
        self.assertEqual(len(helper_kills),2);self.assertLessEqual(clock(),4430)
        self.assertEqual(len([a for a in actions if a[:2]==('create','nonpass')]),1)
        nonpass_begin=next(a[2] for a in actions if a[:2]==('create','nonpass'))
        self.assertAlmostEqual((nonpass_begin-helper_terms[0][3])+(clock()-helper_terms[1][3]),12)
    def test_F2_parent_syscall_stalled_does_not_claim_unconditional_bound(self):
        self.assertIn('independent_watchdog_not_admitted',smoke.DTO_RUNTIME_BLOCKERS)
        code,clock,actions=self.execute(commit_seconds=5000)
        self.assertEqual(code,1);self.assertGreater(clock(),4440);self.assertEqual(self.attempt.reason,'commit_uncertain')


class DTOStageProtocolTests(unittest.TestCase):
    def test_stage_helpers_never_publish_and_parent_receipt_is_last(self):
        with TemporaryDirectory() as directory:
            output=Path(directory)/'fresh'
            args=SimpleNamespace(output=str(output),candidate_sha='a'*40,browser='all',mode='dto-fixture',base_url='https://localhost:1')
            attempt=smoke.DTOAttempt('1'*32,'a'*40);request=attempt.request('init')
            ack=smoke.perform_dto_io('init',request,args)
            self.assertFalse((output/'evidence.json').exists());self.assertFalse((output/'commit.json').exists())
            stage=smoke.dto_stage_path(output,request)
            self.assertTrue(stage.is_file());self.assertEqual(stage.stat().st_mode & 0o777,0o600)
            self.assertEqual(output.stat().st_mode & 0o777,0o700)
            self.assertTrue(attempt.ack(request,ack));self.assertTrue(smoke.publish_dto_stage(output,ack,attempt,False))
            self.assertTrue((output/'evidence.json').exists());self.assertFalse((output/'commit.json').exists())
            with self.assertRaises(FileExistsError):smoke.perform_dto_io('init',request,args)
    def test_final_stage_receipt_and_input_pins_required_together(self):
        with TemporaryDirectory() as directory:
            output=Path(directory)/'fresh'
            args=SimpleNamespace(output=str(output),candidate_sha='a'*40,browser='all',mode='dto-fixture',base_url='https://localhost:1')
            attempt=smoke.DTOAttempt('1'*32,'a'*40);request=attempt.request('init')
            ack=smoke.perform_dto_io('init',request,args);self.assertTrue(attempt.ack(request,ack));attempt.activate()
            initial=json.loads((output/'initial-observation.json').read_text())
            ids=[(e,n) for e in smoke.ENGINES for n in smoke.inventory()]
            progress=dict(initial,cleanup_status='verified',results=[dict(browser=e,scenario=n,status='passed') for e,n in ids])
            smoke._dto_write_private(output/'progress.json',progress)
            request=attempt.request('final');ack=smoke.perform_dto_io('final',request,args)
            self.assertFalse((output/'commit.json').exists());self.assertTrue(attempt.ack(request,ack));attempt.prepare(ack)
            self.assertTrue(smoke.publish_dto_stage(output,ack,attempt,True))
            raw=(output/'evidence.json').read_bytes();receipt=json.loads((output/'commit.json').read_text())
            invocation=dict(attempt_id=attempt.attempt_id,epoch=0,exit_code=0,terminal_state='COMMITTED')
            kwargs=dict(invocation=invocation,expected_attempt=attempt.attempt_id,candidate_sha=args.candidate_sha,
                timing_sha256=ack['timing_contract_sha256'],expected=ids,expected_input_sha256=initial['input_sha256'])
            self.assertTrue(smoke.accept_dto_success(raw,receipt,**kwargs))
            self.assertFalse(smoke.accept_dto_success(raw,dict(receipt,evidence_sha256='0'*64),**kwargs))
            self.assertFalse(smoke.accept_dto_success(raw,receipt,**dict(kwargs,expected_input_sha256={})))
            self.assertFalse(smoke.accept_dto_success(raw,receipt,**dict(kwargs,expected_epoch=1)))
            self.assertFalse(smoke.accept_dto_success(raw,{},**kwargs))
    def test_owned_factory_uses_exact_vector_and_no_credentials(self):
        args=SimpleNamespace(output='/tmp/fresh',candidate_sha='a'*40,browser='all',mode='dto-fixture',base_url='https://localhost:1')
        request=smoke.DTOAttempt('1'*32,'a'*40).request('worker')
        with patch.dict(smoke.os.environ,{'PATH':'/usr/bin','HOME':'/tmp','INCEPTION_API_KEY':'secret'},clear=True), patch.object(smoke.subprocess,'Popen') as popen:
            handle=smoke.create_dto_process('worker',request,args)
            vector=popen.call_args.args[0];kwargs=popen.call_args.kwargs
            self.assertEqual(vector[:3],[sys.executable,str(smoke.ROOT/'scripts/dev/workshop_browser_smoke.py'),'--_dto-owned-fd'])
            self.assertTrue(kwargs['start_new_session']);self.assertTrue(kwargs['close_fds'])
            self.assertEqual(kwargs['env'],{'PATH':'/usr/bin','HOME':'/tmp'});self.assertNotIn('shell',kwargs)
            self.assertEqual(kwargs['pass_fds'],(int(vector[3]),));handle.close()

    def test_environment_allowlist_rejects_relative_paths_and_omits_credentials(self):
        env=smoke.dto_worker_environment({'PATH':'/usr/bin:/bin','HOME':'/tmp/home','LANG':'C','SECRET':'never',
            'INCEPTION_API_KEY':'never','AUTODATA_WORKSHOP_BROWSER_CASE':'never'})
        self.assertEqual(env,{'PATH':'/usr/bin:/bin','HOME':'/tmp/home','LANG':'C'})
        for key,value in [('HOME','relative'),('PATH','/bin:relative'),('LANG','C\x00secret')]:
            with self.subTest(key=key),self.assertRaises(ValueError):smoke.dto_worker_environment({key:value})
    def test_fixed_control_ack_roundtrip_and_size_limit(self):
        ack=dict(attempt_id='1'*32,epoch=3,stage_nonce='2'*32,content_sha256='a'*64,byte_length=123,
            candidate_sha='b'*40,timing_contract_sha256='c'*64,input_fingerprint='d'*64,complete=True,cleanup_verified=True)
        raw=smoke.encode_dto_ack(ack);self.assertLess(len(raw),512);self.assertEqual(smoke.decode_dto_ack(raw),ack)
        for bad in (raw[:-1],raw+b'X'):
            with self.assertRaises(ValueError):smoke.decode_dto_ack(bad)
    def test_watchdog_body_contains_no_file_json_or_unbounded_wait_operations(self):
        source=ast.parse(Path(smoke.__file__).read_text())
        parent=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='supervise_dto')
        for node in ast.walk(parent):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                self.assertNotIn(node.func.attr,('read_text','read_bytes','loads','load','wait','join','run_until_complete','run'))
        # Fixed control parser rejects a second complete ACK without JSON decoding.
        ack=dict(attempt_id='1'*32,epoch=0,stage_nonce='2'*32,content_sha256='a'*64,byte_length=123,
            candidate_sha='b'*40,timing_contract_sha256='c'*64,input_fingerprint='d'*64,complete=True,cleanup_verified=True)
        raw=smoke.encode_dto_ack(ack)
        channel=SimpleNamespace(recv=lambda size:raw,close=lambda:None)
        process=SimpleNamespace(poll=lambda:0)
        handle=smoke.DTOOwnedProcess(process,channel,'final')
        self.assertEqual(handle.read_ack(),ack)
        with self.assertRaises(ValueError):handle.read_ack()

    def test_direct_worker_request_without_owned_descriptor_rejected(self):
        with self.assertRaises(ValueError):smoke.dto_internal_entry(['--_dto-owned-fd','999999','bad'])
    def test_v1_phase_expansion_rejected_even_if_arithmetic_fits(self):
        timing=smoke.load_dto_timing(smoke.FIXTURES/'timing.json')
        for key,value in [('parent_progress_read_parse_seconds',5000),('worker_deadline_reserve_seconds',1500),
                ('worker_deadline_reserve_seconds',1000001),('engine_launch_seconds',16)]:
            with self.subTest(key=key),self.assertRaises(ValueError):smoke.validate_dto_schedule(dict(timing,**{key:value}),120)

class DTOWorkflowBindingTests(unittest.TestCase):
    def test_dto_job_matches_shared_contract_and_disabled_r6_hash(self):
        # Workflow commands are inspected offline; this test launches no fixtures.
        workflow=(smoke.ROOT/'.github/workflows/autonomous-verification.yml').read_bytes()
        dto=workflow.split(b'  workshop-dto-browser:',1)[1].split(b'  r3-preparation-unit:',1)[0].decode()
        timing=smoke.load_dto_timing(smoke.FIXTURES/'timing.json')
        self.assertIn('timeout-minutes: '+str(timing['ci_job_minutes']),dto)
        self.assertIn('timeout-minutes: '+str(timing['ci_exercise_seconds']//60),dto)
        self.assertIn("load_dto_timing",dto);self.assertIn("timing_contract_sha256",dto);self.assertIn("lifetime_seconds",dto)
        self.assertIn("timing['go_test_seconds']",dto);self.assertIn("timing['readiness_seconds']",dto)
        self.assertNotIn('wait "$fixture_pid"',dto);self.assertIn('if: always()',dto)
        r6=json.loads((smoke.ROOT/'docs/agents/tasks/2026-11-03-production-release/r6-release.json').read_text())
        self.assertEqual(r6['product_evidence']['ci_profile']['workflow_sha256'],smoke.hashlib.sha256(workflow).hexdigest())


class API21FakeResponse:
    def __init__(self,url,data,status=200,request=None):
        self.url,self.data,self.status=url,data,status
        self.request=request or SimpleNamespace(method='GET')
    async def body(self):return self.data if isinstance(self.data,bytes) else json.dumps(self.data).encode()
    async def json(self):return self.data


class API21FakeBrowser:
    """Scripted browser surfaces only; real API producer logic remains exercised."""
    def __init__(self,name,bank='bankone',missing=None):
        self.name,self.bank,self.missing=name,bank,missing
        self.contexts=[];self.version='fake-browser';self.closed=False
        self.scope=dict(configuration=smoke.CONFIG,article=smoke.ARTICLE,adjacent=smoke.OTHER,
            other_region=smoke.REVISION,unscoped=smoke.ORDER,vehicle=smoke.OTHER,provider=bank)
        self.paid=False;self.revoked=False;self.generation=1;self.reads=0
    async def new_context(self,**kwargs):
        context=API21FakeContext(self,other=bool(self.contexts));self.contexts.append(context);return context
    async def close(self):self.closed=True
    def measurement(self,context):
        exists=bool(context.transport and context.transport.checkout_count) or self.paid
        order=dict(order_id=smoke.ORDER,configuration_id=smoke.CONFIG,region='US',
            state='revoked' if self.revoked else 'paid' if self.paid else 'open',owner='owner')
        return dict(auth_sessions=int(context.signed),hashed_sessions=int(context.signed),sdk_cert_calls=1,
            sdk_user_calls=2,sdk_unexpected=0,workshop_orders=int(exists),workshop_checkout_requests=int(exists),
            entitlements=int(self.paid),dataset_requests=int(self.paid),dataset_projections=int(self.paid),
            payment_events=int(self.paid),image_reads=self.reads,orders=[order] if exists else [])
    def snapshot(self):
        return dict(payment_calls=1,paid_rows=dict(workshop_orders=[dict(order_id=smoke.ORDER,
            configuration_id=smoke.CONFIG,region='US',status='open',checkout_session_id='cs_test_'+'a'*32)],entitlements=[]),
            provider_calls={'bankone':1,'banktwo':0},source_calls={'bankone':1,'banktwo':0},asset_calls={'bankone':1,'banktwo':0},
            model_calls=1,counts={'published_revisions':1},immutable_sha256='a'*64)


class API21FakeContext:
    def __init__(self,browser,other=False):
        self.browser,self.other=browser,other
        self.request=self;self.transport=None;self.signed=False;self.disabled=False;self.page=None;self.closed=False
    async def route(self,pattern,handler):self.transport=handler.__self__
    async def new_page(self):self.page=API21FakePage(self);return self.page
    async def close(self):self.closed=True
    async def cookies(self,origin):return [dict(name='__Host-autodata_session',secure=True,httpOnly=True,sameSite='Lax')]
    async def get(self,url,**kwargs):
        browser=self.browser;path=smoke.urlsplit(url).path
        phase=getattr(getattr(self,'_api21',None),'phase','')
        data={};status=200
        if path=='/__fixture/metadata':data=dict(kind='api-fixture',scope=browser.scope)
        elif path=='/__fixture/measurement':data=browser.measurement(self)
        elif path=='/__fixture/snapshot':data=browser.snapshot()
        elif path=='/__fixture/runtime':data={'application_generation':browser.generation}
        elif 'denial' in phase:
            status=404 if phase in ('other-image-denial','adjacent-denial','other-region-denial','unscoped-article-denial','legacy-vehicle-denial') else 401 if phase in ('logout-image-denial','disabled-image-denial') else 403
            data={'error':'denied'}
        elif phase=='other-library-http':data={'items':[]}
        elif '/images/' in path:browser.reads+=1;data=b'image-original-bytes'
        return API21FakeResponse(url,data,status)
    async def post(self,url):
        path=smoke.urlsplit(url).path
        if path=='/__fixture/payment/settle':self.browser.paid=True
        if path=='/__fixture/payment/refund':self.browser.revoked=True
        if path=='/__fixture/restart':self.browser.generation+=1
        if path=='/__fixture/disable':self.disabled=True
        return API21FakeResponse(url,{},200)


class API21FakePage:
    def __init__(self,context):self.context=context;self.handlers={};self.url='about:blank'
    def on(self,event,callback):self.handlers[event]=callback
    def locator(self,selector):return API21FakeLocator(self,selector)
    def emit(self,url,data,request=None):
        observations=getattr(self.context,'_api21',None)
        if observations and observations.phase==self.context.browser.missing:return
        callback=self.handlers.get('response')
        if callback:callback(API21FakeResponse(url,data,request=request))
    def library(self):
        self.emit('https://127.0.0.1:32001/v1/workshop/library?limit=20',dict(items=[dict(
            library_item_id=smoke.ORDER,configuration_id=smoke.CONFIG,region='US',access_state='paid')]))
    async def goto(self,url):
        self.url=url
        if 'article=' in url:
            self.emit('https://127.0.0.1:32001/v1/catalog/vehicles/'+smoke.CONFIG+'/articles/'+smoke.ARTICLE,{'content':'source'})
    async def reload(self):
        phase=getattr(getattr(self.context,'_api21',None),'phase','')
        if phase.startswith('owner-library-'):self.library()
        elif phase=='warm-page-http':self.emit('https://127.0.0.1:32001/v1/catalog/vehicles/'+smoke.CONFIG+'/articles/'+smoke.ARTICLE,{'content':'canonical'})
    async def wait_for_url(self,pattern):pass
    async def evaluate(self,code):return []
    async def screenshot(self,**kwargs):raise RuntimeError('fake screenshot unavailable')


class API21FakeLocator:
    def __init__(self,page,selector):self.page,self.selector=page,selector;self.first=self
    async def click(self,**kwargs):
        context=self.page.context;browser=context.browser
        if self.selector=='#signin':context.signed=True
        elif self.selector=='#signout':context.signed=False
        elif self.selector=='#my-vehicles':self.page.library()
        elif self.selector=='#source-review-load':
            self.page.emit('https://127.0.0.1:32001/v1/catalog/vehicles/'+smoke.CONFIG+'/articles/'+smoke.ARTICLE+'/source',{'source':'Remove the pump.'})
        elif self.selector in ('#purchase-action','#retry'):
            route=CheckoutRoute()
            route.fetched_response.data['checkout_url']='https://checkout.stripe.com/c/pay/cs_test_'+'a'*32
            route.request.post_data_buffer=route.request.post_data.encode()
            route.fetched_response.body=lambda:asyncio.sleep(0,result=json.dumps(route.fetched_response.data).encode())
            await context.transport.route(route)
            if browser.name!=smoke.API_CASES[0]:
                context.transport.checkout_count=1
                self.page.emit(route.request.url,route.fetched_response.data,route.request)
            if browser.name!=smoke.API_CASES[0] or self.selector=='#retry':self.page.url=route.fetched_response.data['checkout_url']
    async def check(self):pass
    async def get_attribute(self,name):
        if name=='src':return 'https://127.0.0.1:32001/v1/catalog/images/v2.fake-capability'
        return '/v1/catalog/vehicles/'+smoke.CONFIG+'/articles/'+smoke.ARTICLE+'/source?source_revision_id='+smoke.REVISION
    def __getattr__(self,name):
        async def expectation(*args,**kwargs):pass
        return expectation


class API21ObservationsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Any accidental service, process, socket or urllib use fails this suite.
        self.sentinels=[]
        for owner,name in ((smoke.subprocess,'Popen'),(smoke.subprocess,'run'),(smoke,'urlopen'),
                (smoke.socket,'socket'),(smoke.os,'killpg')):
            item=patch.object(owner,name,side_effect=AssertionError('forbidden real operation'))
            item.start();self.sentinels.append(item)
        import urllib.request
        item=patch.object(urllib.request,'urlopen',side_effect=AssertionError('forbidden real operation'))
        item.start();self.sentinels.append(item)
    async def asyncTearDown(self):
        for item in reversed(self.sentinels):item.stop()

    def binding(self):
        return dict(binding_state='complete',unavailable_reason=None,
            api_observability_version='api21-producer-v2',run_id='a'*32,attempt_id='b'*32,
            case_id=smoke.API_CASES[0]+'[chromium]',root=smoke.API_CASES[0],engine='chromium',
            bank='bankone',candidate_sha='c'*40,source_tree='d'*40,
            source_input_sha256={'input': 'e'*64},producer_role='browser-runner')

    def buffer(self, **kwargs):
        return smoke.APIObservations(self.binding(), **kwargs)

    def test_original_body_bytes_and_strict_json(self):
        raw=b' { "ok" : true } \n'
        body=smoke.api21_body(raw,'playwright-response-body')
        self.assertEqual(body['availability'],'retained')
        self.assertEqual(smoke.base64.b64decode(body['base64']),raw)
        self.assertEqual(body['sha256'],smoke.hashlib.sha256(raw).hexdigest())
        self.assertEqual(body['parsed'],{'ok':True})
        for raw,reason in [(b'{"a":1,"a":2}','invalid_json'),(b'{"x":NaN}','invalid_json'),
                (b'"\xff"','invalid_utf8'),(b'{"token":"secret"}','secret_detected')]:
            with self.subTest(raw=raw):
                body=smoke.api21_body(raw,'playwright-response-body')
                self.assertEqual(body['availability'],'unavailable')
                self.assertEqual(body['reason'],reason)
                self.assertIsNone(body['base64'])

    def test_bounds_fail_without_discarding_prefix_or_promoting_pass(self):
        buffer=self.buffer(max_events=1)
        buffer.lifecycle('setup','setup','completed')
        with self.assertRaises(smoke.APIObservationError):buffer.lifecycle('setup','page-create','requested')
        self.assertEqual(len(buffer.snapshot()['events']),1)
        self.assertEqual(buffer.snapshot()['primary_failure'],'over_limit')
        buffer.finish()
        self.assertEqual(buffer.snapshot()['status'],'failed')
        self.assertEqual(smoke.api21_body(b'x'*131073,'playwright-response-body')['reason'],'over_limit')

    async def test_response_tasks_keep_initiating_phase_and_all_library_replies(self):
        buffer=self.buffer();gate=asyncio.Event()
        class Response:
            status=200;url='https://127.0.0.1:32001/v1/workshop/library?limit=20'
            request=SimpleNamespace(method='GET')
            async def body(self):
                await gate.wait()
                return b'{"items":[{"order_id":"paid"}]}'
        buffer.phase='owner-library-initial-http'
        buffer.page_response(Response());buffer.page_response(Response())
        buffer.phase='owner-library-reload-http';gate.set()
        await buffer.drain()
        events=buffer.snapshot()['events']
        self.assertEqual([e['phase'] for e in events],['owner-library-initial-http']*2)
        self.assertEqual([e['payload']['attempt'] for e in events],[1,2])
        buffer.require_window('owner-library-initial-http')
        with self.assertRaises(smoke.APIObservationError):buffer.require_window('owner-library-reload-http')

    async def test_library_missing_original_or_empty_body_cannot_pass(self):
        for raw in (b'{"items":[]}',b'not json'):
            buffer=self.buffer();buffer.phase='owner-library-initial-http'
            response=SimpleNamespace(status=200,url='https://127.0.0.1:32001/v1/workshop/library',
                request=SimpleNamespace(method='GET'),body=lambda:asyncio.sleep(0,result=raw))
            buffer.page_response(response);await buffer.drain()
            with self.assertRaises(smoke.APIObservationError):buffer.require_window(buffer.phase)

    async def test_checkout_retains_fetch_before_abort_and_exact_original_request(self):
        buffer=self.buffer();fixture=smoke.APIFixture('https://127.0.0.1:32001',smoke.API_CASES[0],observations=buffer)
        route=CheckoutRoute();route.fetched_response.data['checkout_url']='https://checkout.stripe.com/c/pay/cs_test_'+'a'*32
        raw=route.request.post_data.encode()
        route.request.post_data_buffer=raw
        route.fetched_response.body=lambda:asyncio.sleep(0,result=json.dumps(route.fetched_response.data).encode())
        await fixture.route(route)
        events=buffer.snapshot()['events']
        self.assertEqual(events[0]['phase'],'checkout-first-http')
        self.assertEqual(smoke.base64.b64decode(events[0]['payload']['request']['base64']),raw)
        self.assertEqual([e['payload'].get('state') for e in events[1:]],
            ['fetch-completed','response-abort-requested','response-aborted'])
        self.assertEqual(events[1]['payload']['http_event']['seq'],events[0]['seq'])

    def test_private_atomic_publication_rejects_links_and_preserves_primary(self):
        buffer=self.buffer();buffer.fail('assertion_failed')
        with TemporaryDirectory() as temp:
            root=Path(temp);target=root/'evidence.json'
            self.assertTrue(smoke.api21_publish(target,{'results':[{'observations':buffer.snapshot()}]},buffer))
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
            target.unlink();target.symlink_to(root/'elsewhere')
            with patch('sys.stderr') as stderr:
                self.assertFalse(smoke.api21_publish(target,{},buffer))
            self.assertFalse((root/'elsewhere').exists())
            self.assertEqual(buffer.snapshot()['primary_failure'],'assertion_failed')
            self.assertIn('API21_PUBLICATION_FAILED',str(stderr.write.call_args_list))

    async def test_api_case_retains_failure_before_context_creation(self):
        buffer=self.buffer()
        class Browser:
            async def new_context(self,**kwargs):raise RuntimeError('secret-from-browser')
        with patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(expect=lambda value:None)}):
            with self.assertRaises(RuntimeError):
                await smoke.api_case(Browser(),'https://127.0.0.1:32001',smoke.API_CASES[0],Path('/unused'),observations=buffer)
        snapshot=buffer.snapshot()
        self.assertEqual(snapshot['status'],'failed')
        self.assertEqual(snapshot['primary_failure'],'launch_failed')
        self.assertNotIn('secret-from-browser',json.dumps(snapshot))
        self.assertEqual(snapshot['events'][-1]['payload']['state'],'failed')

    async def test_run_metadata_failure_publishes_safe_failed_prefix(self):
        buffer=self.buffer()
        with TemporaryDirectory() as temp:
            args=SimpleNamespace(mode='api-fixture',browser='chromium',output=temp,
                base_url='https://127.0.0.1:32001',candidate_sha='c'*40)
            with (patch.dict(smoke.os.environ,{
                    'AUTODATA_WORKSHOP_BROWSER_CASE':smoke.API_CASES[0],
                    'AUTODATA_API21_BINDING':json.dumps(self.binding())}),
                    patch.object(smoke,'verify_provenance',side_effect=RuntimeError('secret-token')),
                    patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(async_playwright=lambda:None)})):
                with self.assertRaises(Exception):await smoke.run(args)
            value=json.loads((Path(temp)/'evidence.json').read_bytes())
            self.assertEqual(value['results'][0]['status'],'failed')
            self.assertNotIn('secret-token',json.dumps(value))
            self.assertEqual(value['results'][0]['observations']['primary_failure'],'source_binding_failed')

    async def test_actual_api_case_all_21_scripted_surfaces_retain_phase_matrix(self):
        matrix=json.loads((smoke.ROOT/'docs/agents/specs/2026-11-04-workshop-api21-producer-observability.json').read_text())['phase_matrix']
        count=0
        for name in smoke.API_CASES:
            for engine in smoke.ENGINES:
                for bank in ('bankone',) if name==smoke.API_CASES[0] else ('bankone','banktwo'):
                    binding=self.binding();binding.update(root=name,engine=engine,bank=bank)
                    buffer=smoke.APIObservations(binding);browser=API21FakeBrowser(name,bank)
                    with self.subTest(name=name,engine=engine,bank=bank),TemporaryDirectory() as temp, \
                            patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(expect=lambda value:value)}):
                        result=await smoke.api_case(browser,'https://127.0.0.1:32001',name,Path(temp),observations=buffer)
                        self.assertEqual(result['status'],'passed',buffer.snapshot())
                        phases=list(dict.fromkeys(e['phase'] for e in result['observations']['events']))
                        self.assertEqual(phases,matrix[name])
                        self.assertTrue(all(c.closed for c in browser.contexts));count+=1
        self.assertEqual(count,21)

    async def test_source_window_without_actual_response_cannot_pass(self):
        buffer=self.buffer();browser=API21FakeBrowser(smoke.API_CASES[1],missing='source-page-http')
        with TemporaryDirectory() as temp,patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(expect=lambda value:value)}):
            result=await smoke.api_case(browser,'https://127.0.0.1:32001',smoke.API_CASES[1],Path(temp),observations=buffer)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['observations']['primary_failure'],'assertion_failed')

    async def test_runtime_poll_ceiling_is_phase_specific(self):
        buffer=self.buffer();response=API21FakeResponse('https://local/__fixture/runtime',{'application_generation':1})
        for attempt in range(100):await buffer.http(response,response.url,phase='runtime-poll')
        self.assertEqual(buffer.snapshot()['events'][-1]['payload']['attempt'],100)
        with self.assertRaises(smoke.APIObservationError):await buffer.http(response,response.url,phase='runtime-poll')
        buffer=self.buffer()
        for attempt in range(16):await buffer.http(response,response.url,phase='runtime-before')
        with self.assertRaises(smoke.APIObservationError):await buffer.http(response,response.url,phase='runtime-before')

    async def test_actual_run_fake_playwright_success_keeps_exact_extensions_and_binding(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);manifest=root/'browsers.json';manifest.write_text('{"browsers":[{"name":"chromium","revision":"123"}]}')
            output=root/'browser'
            args=SimpleNamespace(mode='api-fixture',browser='chromium',output=str(output),
                base_url='https://127.0.0.1:32001',candidate_sha='c'*40)
            binding=self.binding()
            names=['scripts/dev/workshop_browser_smoke.py','scripts/dev/fixtures/workshop_customer/scenarios.json',
                'scripts/dev/fixtures/workshop_customer/firebase_transport.js','scripts/dev/fixtures/workshop_customer/hostile_source.json',
                'scripts/dev/fixtures/workshop_customer/stripe_checkout.html','apps/api-go/workshop_browser_fixture_test.go',
                'workers/ingestion-python/tests/test_workshop_browser_integration.py']
            binding['source_input_sha256']={name:smoke.hashlib.sha256((smoke.ROOT/name).read_bytes()).hexdigest() for name in names}
            browser=API21FakeBrowser(smoke.API_CASES[0]);calls=[]
            class Manager:
                async def __aenter__(self):return SimpleNamespace(chromium=self)
                async def __aexit__(self,*args):return False
                async def launch(self,**kwargs):calls.append(kwargs);return browser
            with (patch.dict(smoke.os.environ,{'AUTODATA_WORKSHOP_BROWSER_CASE':smoke.API_CASES[0],
                    'AUTODATA_API21_BINDING':json.dumps(binding)}),
                    patch.object(smoke,'verify_provenance',return_value={'kind':'api-fixture'}),
                    patch.object(smoke.importlib.metadata,'distribution',return_value=SimpleNamespace(locate_file=lambda path:manifest)),
                    patch.object(smoke.importlib.metadata,'version',return_value='1.64.1'),
                    patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(async_playwright=Manager,expect=lambda value:value)})):
                result=await smoke.run(args)
            value=smoke.api21_load((output/'evidence.json').read_bytes())
            self.assertEqual(value['binding'],binding)
            self.assertEqual(set(value['input_sha256']),set(names[:-1]))
            self.assertEqual(value['results'][0]['provider'],'bankone')
            self.assertEqual(value['results'][0]['observations']['publication'],'written')
            self.assertEqual(value['results'][0]['observations']['status'],'passed')
            self.assertEqual(calls,[{}]);self.assertTrue(browser.closed)
            self.assertEqual(result,value)

    async def test_capacity_failure_does_not_prevent_context_cleanup(self):
        browser=API21FakeBrowser(smoke.API_CASES[1]);buffer=self.buffer(max_events=4)
        with TemporaryDirectory() as temp,patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(expect=lambda value:value)}):
            try:await smoke.api_case(browser,'https://127.0.0.1:32001',smoke.API_CASES[1],Path(temp),observations=buffer)
            except smoke.APIObservationError:pass
        self.assertEqual(buffer.snapshot()['primary_failure'],'over_limit')
        self.assertTrue(browser.contexts[0].closed)

    async def test_empty_control_keeps_original_bytes(self):
        buffer=self.buffer()
        for status,raw,content_type in ((204,b'',''),):
            response=API21FakeResponse('https://local/__fixture/disable',raw,status)
            response.headers={'content-type':content_type}
            await buffer.http(response,response.url,phase='disable-control')
            body=buffer.snapshot()['events'][-1]['payload']['response']
            self.assertEqual(body['availability'],'retained')
            self.assertEqual(smoke.base64.b64decode(body['base64']),raw)
            self.assertIsNone(body['parsed'])

    def test_failed_publication_retries_minimal_receipt_and_keeps_primary(self):
        buffer=self.buffer();buffer.fail('assertion_failed');writes=[]
        def write(path,value):
            writes.append(copy.deepcopy(value))
            if len(writes)==1:raise OSError('secret disk detail')
        with patch.object(smoke,'api21_write',side_effect=write):
            self.assertFalse(smoke.api21_publish(Path('/unused'),{'results':[]},buffer))
        self.assertEqual(len(writes),2)
        row=writes[1]['results'][0]
        self.assertEqual(row['status'],'failed')
        self.assertEqual(row['observations']['primary_failure'],'assertion_failed')
        self.assertEqual(row['observations']['publication'],'failed')
        self.assertNotIn('secret disk detail',json.dumps(writes))

    async def test_fragment_conflict_retains_original_response_but_never_passes_closed_identity(self):
        buffer=self.buffer();fixture=smoke.APIFixture('https://127.0.0.1:32001',smoke.API_CASES[0],observations=buffer)
        route=CheckoutRoute();route.request.post_data_buffer=route.request.post_data.encode()
        raw=json.dumps(route.fetched_response.data).encode()
        route.fetched_response.body=lambda:asyncio.sleep(0,result=raw)
        await fixture.route(route)
        event=buffer.snapshot()['events'][0]['payload']
        self.assertEqual(smoke.base64.b64decode(event['response']['base64']),raw)
        self.assertIsNone(event['checkout_identity'])
        self.assertEqual(buffer.snapshot()['primary_failure'],'source_binding_failed')
        self.assertTrue(fixture.checkout_responses[0]['checkout_url'].endswith('#fidkdFixtureFragment'))

    def test_body_shape_and_payload_types_are_closed(self):
        body=smoke.api21_body(b'{"ok":true}','playwright-response-body')
        smoke.api21_validate_body(body)
        for changed in (dict(body,length=True),dict(body,base64=body['base64']+'\n'),
                dict(body,sha256='0'*64),dict(body,extra='unknown')):
            with self.subTest(changed=changed),self.assertRaises(ValueError):smoke.api21_validate_body(changed)
        buffer=self.buffer()
        for payload in (dict(kind='lifecycle',operation='setup',state='completed',reason=None,extra=True),
                dict(kind='producer-assertion',name='assertion',result=1,reason=None)):
            with self.subTest(payload=payload),self.assertRaises(smoke.APIObservationError):buffer.event('setup',payload)
        self.assertEqual(buffer.snapshot()['events'],[])

    def test_binding_invalid_value_never_leaks_unknown_environment_fields(self):
        args=SimpleNamespace(browser='chromium',candidate_sha='c'*40)
        supplied=self.binding();supplied['bank']='secret-provider-token'
        with patch.dict(smoke.os.environ,{'AUTODATA_API21_BINDING':json.dumps(supplied)}):
            binding=smoke.api21_binding(args,smoke.API_CASES[0])
        self.assertEqual(binding['binding_state'],'partial')
        self.assertNotIn('secret-provider-token',json.dumps(binding))

    def test_causal_references_require_an_actual_earlier_http_event(self):
        buffer=self.buffer()
        ref=dict(stream='observations',producer_role='browser-runner',seq=1)
        payload=dict(kind='checkout-delivery',attempt=1,state='fetch-completed',http_event=ref)
        with self.assertRaises(smoke.APIObservationError):buffer.event('checkout-first-delivery',payload,[ref])
        self.assertEqual(buffer.snapshot()['events'],[])

    async def test_missing_or_wrong_owner_library_item_cannot_satisfy_window(self):
        buffer=self.buffer();buffer.owner_scope=(smoke.CONFIG,smoke.ORDER)
        response=API21FakeResponse('https://local/v1/workshop/library',dict(items=[dict(
            library_item_id=smoke.ORDER,configuration_id=smoke.OTHER,region='US',access_state='paid')]))
        await buffer.http(response,response.url,phase='owner-library-initial-http')
        with self.assertRaises(smoke.APIObservationError):buffer.require_window('owner-library-initial-http')

    async def test_fetch_failure_retains_request_and_unavailable_response(self):
        buffer=self.buffer();fixture=smoke.APIFixture('https://127.0.0.1:32001',smoke.API_CASES[0],observations=buffer)
        route=CheckoutRoute(failure=RuntimeError('secret-fetch-detail'))
        route.request.post_data_buffer=route.request.post_data.encode()
        with self.assertRaises(RuntimeError):await fixture.route(route)
        payload=buffer.snapshot()['events'][0]['payload']
        self.assertIsNone(payload['status'])
        self.assertEqual(payload['request']['availability'],'retained')
        self.assertEqual(payload['response']['availability'],'unavailable')
        self.assertNotIn('secret-fetch-detail',json.dumps(buffer.snapshot()))

    def test_body_event_and_case_exact_capacity_boundaries(self):
        raw=b'"'+b'a'*131070+b'"'
        self.assertEqual(smoke.api21_body(raw,'playwright-response-body')['availability'],'retained')
        self.assertEqual(smoke.api21_body(raw+b' ','playwright-response-body')['reason'],'over_limit')
        buffer=self.buffer(clock=lambda:0)
        payload=dict(kind='lifecycle',operation='setup',state='completed',reason=None)
        buffer.event('setup',payload)
        boundary=len(smoke.api21_json(dict(buffer.snapshot(),status='partial',
            primary_failure=max(smoke.API21_REASONS,key=len))))
        accepted=self.buffer(max_bytes=boundary,clock=lambda:0);accepted.event('setup',payload)
        rejected=self.buffer(max_bytes=boundary-1,clock=lambda:0)
        with self.assertRaises(smoke.APIObservationError):rejected.event('setup',payload)
        self.assertEqual(rejected.snapshot()['events'],[])
        big=smoke.api21_body(b'"'+b'x'*120000+b'"','playwright-response-body')
        http=dict(kind='http',channel='application',method='GET',route_template='/v1/workshop/library',
            actor='owner',attempt=1,status=200,idempotency_key=None,request=None,response=big,checkout_identity=None)
        with self.assertRaises(smoke.APIObservationError):self.buffer().event('owner-library-initial-http',http)

    def test_private_publication_rejects_hardlink_and_nonprivate_directory(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);original=root/'original';original.write_text('original')
            linked=root/'evidence.json';smoke.os.link(original,linked)
            with self.assertRaises(OSError):smoke.api21_write(linked,{'value':True})
            self.assertEqual(original.read_text(),'original');linked.unlink()
            root.chmod(0o755)
            try:
                with self.assertRaises(OSError):smoke.api21_write(linked,{'value':True})
            finally:root.chmod(0o700)

    async def test_checkout_retry_original_bytes_and_identity_are_independent(self):
        buffer=self.buffer();fixture=smoke.APIFixture('https://127.0.0.1:32001',smoke.API_CASES[0],observations=buffer)
        responses=[]
        for index in range(2):
            route=CheckoutRoute();route.request.post_data_buffer=route.request.post_data.encode()
            route.fetched_response.data['checkout_url']='https://checkout.stripe.com/c/pay/cs_test_'+'a'*32
            raw=json.dumps(route.fetched_response.data,indent=2 if index else None).encode()
            route.fetched_response.body=lambda raw=raw:asyncio.sleep(0,result=raw)
            await fixture.route(route);responses.append(raw)
        http=[e['payload'] for e in buffer.snapshot()['events'] if e['payload']['kind']=='http']
        self.assertNotEqual(http[0]['response']['sha256'],http[1]['response']['sha256'])
        self.assertEqual(http[0]['checkout_identity'],http[1]['checkout_identity'])
        self.assertEqual(http[0]['request'],http[1]['request'])
        self.assertEqual(buffer.snapshot()['primary_failure'],None)
        third=CheckoutRoute();third.request.post_data_buffer=third.request.post_data.encode()
        with self.assertRaises(AssertionError):await fixture.route(third)
        self.assertFalse(third.backend_committed)

    async def test_google_response_body_is_read_once_before_parsed_assertions(self):
        buffer=self.buffer();fixture=smoke.APIFixture('https://127.0.0.1:32001',smoke.API_CASES[0],observations=buffer)
        route=CheckoutRoute();route.request.post_data_buffer=route.request.post_data.encode();calls=[]
        route.fetched_response.data['checkout_url']='https://checkout.stripe.com/c/pay/cs_test_'+'a'*32
        async def body():
            calls.append(True)
            if len(calls)>1:raise AssertionError('body was reconstructed or re-read')
            return json.dumps(route.fetched_response.data).encode()
        route.fetched_response.body=body
        await fixture.route(route)
        self.assertEqual(len(calls),1)

    async def test_every_http_phase_failure_retains_nonpass_prefix_under_actual_api_case(self):
        matrix=json.loads((smoke.ROOT/'docs/agents/specs/2026-11-04-workshop-api21-producer-observability.json').read_text())['phase_matrix']
        for name,phases in matrix.items():
            for phase in phases:
                if phase=='setup' or phase.endswith('-delivery') or phase.startswith('checkout'):continue
                browser=API21FakeBrowser(name);buffer=self.buffer()
                original=API21FakeResponse.body
                async def body(response):
                    if buffer.phase==phase:raise OSError('safe fake read failure')
                    return await original(response)
                with self.subTest(name=name,phase=phase),TemporaryDirectory() as temp, \
                        patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(expect=lambda value:value)}), \
                        patch.object(API21FakeResponse,'body',body):
                    try:result=await smoke.api_case(browser,'https://127.0.0.1:32001',name,Path(temp),observations=buffer)
                    except (smoke.APIObservationError,OSError):result={'status':'failed'}
                    self.assertEqual(result['status'],'failed')
                    self.assertIsNotNone(buffer.snapshot()['primary_failure'])
                    self.assertTrue(browser.contexts[0].closed)

    async def test_duplicate_or_out_of_order_delivery_never_upgrades_complete_case(self):
        buffer=self.buffer();browser=API21FakeBrowser(smoke.API_CASES[0])
        with TemporaryDirectory() as temp,patch.dict(sys.modules,{'playwright.async_api':SimpleNamespace(expect=lambda value:value)}):
            result=await smoke.api_case(browser,'https://127.0.0.1:32001',smoke.API_CASES[0],Path(temp),observations=buffer)
        self.assertEqual(result['status'],'passed')
        delivery=next(e['payload'] for e in buffer.events if e['payload']['kind']=='checkout-delivery')
        buffer.event('checkout-first-delivery',delivery,[delivery['http_event']])
        buffer.complete_case(smoke.API_CASES[0])
        self.assertEqual(buffer.snapshot()['status'],'failed')

    def test_safe_routes_exclude_auth_and_all_capabilities_queries_hosts(self):
        self.assertIsNone(smoke.api21_route('https://local/v1/auth/session'))
        self.assertEqual(smoke.api21_route('https://local/v1/catalog/images/v2.secret?token=secret'),
            '/v1/catalog/images/{capability}')
        self.assertEqual(smoke.api21_route('https://local/__fixture/payment/settle?order_id=secret'),
            '/__fixture/payment/settle')


if __name__ == '__main__': unittest.main()
