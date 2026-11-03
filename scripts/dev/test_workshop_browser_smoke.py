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


if __name__ == '__main__': unittest.main()
