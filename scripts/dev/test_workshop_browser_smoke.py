import ast
import asyncio
import copy
import json
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
            region='US', checkout_url='https://checkout.stripe.com/c/pay/cs_test_' + 'a'*32,
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
            dict(valid, checkout_url='https://checkout.stripe.com.evil/c/pay/cs_test_'+'a'*32),
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
                     dict(valid, checkout_url='https://checkout.stripe.com/c/pay/cs_test_'+'b'*32)):
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


if __name__ == '__main__': unittest.main()
