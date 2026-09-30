import io
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.parse import urlsplit

from autodata_ingestion.autoapitwo_connector import (
    AutoAPITwoConnector,
    ArticleParser,
    SourceUnavailable,
    _source_failure_reason,
)


class ConnectorTests(unittest.TestCase):
    def test_transient_source_reads_are_retried_before_success(self):
        calls = []

        def opener(req, **kwargs):
            calls.append(req.full_url)
            if len(calls) < 3:
                raise HTTPError(req.full_url, 502, "bad gateway", {}, io.BytesIO(b"upstream error"))
            return io.BytesIO(b"figure-bytes")

        client = AutoAPITwoConnector(opener=opener, retry_delay=0)
        result = client.read(
            "/api/v1/content/carids/1/images/figure.png",
            car_id="1",
            binary=True,
        )

        self.assertEqual(result, b"figure-bytes")
        self.assertEqual(len(calls), 3)

    def test_persistent_transient_source_failure_is_bounded(self):
        calls = []

        def opener(req, **kwargs):
            calls.append(req.full_url)
            raise HTTPError(req.full_url, 503, "unavailable", {}, io.BytesIO())

        client = AutoAPITwoConnector(opener=opener, retry_attempts=3, retry_delay=0)
        with self.assertRaises(SourceUnavailable):
            client.read("/api/v1/content/carids/1/images/figure.png", car_id="1", binary=True)

        self.assertEqual(len(calls), 3)

    def test_retry_after_is_capped_and_rate_limit_cooldown_is_bounded(self):
        error = HTTPError(
            "https://autoapitwo.vercel.app/api/v1/content/carids/1/images/figure.png",
            429,
            "rate limited",
            {"Retry-After": "300"},
            io.BytesIO(),
        )
        client = AutoAPITwoConnector(retry_after_cap=2, retry_delay=0)

        self.assertEqual(client._retry_delay(error, 0), 2)

    def test_non_transient_source_failure_is_not_retried(self):
        calls = []

        def opener(req, **kwargs):
            calls.append(req.full_url)
            raise HTTPError(req.full_url, 404, "not found", {}, io.BytesIO())

        client = AutoAPITwoConnector(opener=opener, retry_attempts=3, retry_delay=0)
        with self.assertRaises(SourceUnavailable):
            client.read("/api/v1/content/carids/1/images/figure.png", car_id="1", binary=True)

        self.assertEqual(len(calls), 1)

    def test_rejects_unsafe_links_and_vehicle_mismatch(self):
        client = AutoAPITwoConnector()
        for url in ['https://evil.test/api/v1/content/carids/1/a', '/api/v1/session', '/api/v1/content/carids/2/a', '/api/v1/content/carids/1/%2e%2e/account']:
            with self.assertRaises(ValueError):
                client.safe_url(url, '1')

    def test_parser_preserves_order_values_and_images_without_executable_html(self):
        parser = ArticleParser()
        parser.feed('<script>bad()</script>1. Install gasket<br/>Torque: <b>8.8 Nm</b><img src="/figure"/><a class="image">Click for full-size image</a><br/>2. Install cover')
        parser.flush()
        self.assertEqual([b['kind'] for b in parser.blocks], ['text','text','image','text'])
        self.assertEqual(parser.blocks[1]['text'], 'Torque: 8.8 Nm')
        self.assertNotIn('Click', str(parser.blocks))
        self.assertNotIn('bad()', str(parser.blocks))

    def test_concurrent_reads_coalesce_and_do_not_share_mutable_results(self):
        calls = []
        def opener(req, **kwargs):
            calls.append(req.full_url)
            return io.BytesIO(b'{"results":[{"id":"1"}]}')
        client = AutoAPITwoConnector(opener=opener)
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda _: client.search_vehicles('1997 RAV4'), range(4)))
        self.assertEqual(len(calls), 1)
        results[0][0]['id'] = 'changed'
        self.assertEqual(results[1][0]['id'], '1')

    def test_article_checks_identity_and_retains_figure_evidence(self):
        payload = {'id':'9', 'car':{'id':'1'}, '_embedded':{'data':{'article':{'content':'Install pump<br/><img src="/api/v1/content/carids/1/thumbnails/a"/>'}}}}
        client = AutoAPITwoConnector(opener=lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
        article = client.article('1','/api/v1/content/carids/1/a')
        self.assertEqual(article['images'][0]['evidence_ids'], article['evidence_ids'])
        other = AutoAPITwoConnector(opener=lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
        with self.assertRaises(SourceUnavailable):
            other.article('2','/api/v1/content/carids/2/a')

    def test_article_body_preserves_provider_block_boundaries(self):
        payload = {
            'id': '9',
            'car': {'id': '1'},
            '_embedded': {'data': {'article': {
                'content': '<h2>ACCELERATION TYPE</h2><p>Remote sensors are mounted in the vehicle.</p><p>They cannot be repaired.</p>',
            }}},
        }
        client = AutoAPITwoConnector(opener=lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
        article = client.article('1', '/api/v1/content/carids/1/a')
        self.assertEqual(
            article['body'],
            'ACCELERATION TYPE\n\nRemote sensors are mounted in the vehicle.\n\nThey cannot be repaired.',
        )

    def test_article_ignores_document_anchors_and_external_inline_links(self):
        payload = {
            'id': '9',
            'car': {'id': '1'},
            '_embedded': {'data': {'article': {
                'content': (
                    '<p>Remove the bearing.</p>'
                    '<a href="#essentialToolSpan">Special tools</a>'
                    '<a href="https://external.example/advert">Related</a>'
                    '<a href="/api/v1/content/carids/1/components/867">Component</a>'
                ),
            }}},
        }
        client = AutoAPITwoConnector(opener=lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
        article = client.article('1', '/api/v1/content/carids/1/a')
        self.assertEqual(
            article['component_links'],
            ['https://autoapitwo.vercel.app/api/v1/content/carids/1/components/867'],
        )

    def test_parts_and_labor_article_builds_body_when_html_missing(self):
        payload = {
            'id': 'labor-9',
            'title': 'Oil Pump',
            'car': {'id': '13218'},
            '_embedded': {
                'data': {
                    'article': {'content': ''},
                    'partsAndLabor': {
                        'labors': {
                            'operations': [
                                {
                                    'operation': 'Replace',
                                    'qualifiers': [
                                        {
                                            'name': 'Oil Pump',
                                            'labor': {
                                                'standardtime': '2.5',
                                                'note': 'Includes gasket replacement.',
                                            },
                                        }
                                    ],
                                }
                            ]
                        }
                    },
                }
            },
        }
        client = AutoAPITwoConnector(opener=lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
        article = client.article('13218', '/api/v1/content/carids/13218/a', title='Oil Pump')
        self.assertEqual(article['content_kind'], 'parts_and_labor')
        self.assertIn('Includes gasket replacement', article['body'])
        self.assertEqual(article['labor_hours'], 2.5)
        self.assertTrue(article['blocks'])

    def test_oversize_rejected(self):
        client = AutoAPITwoConnector(max_bytes=2, opener=lambda *a, **k: io.BytesIO(b'large'))
        with self.assertRaises(SourceUnavailable): client.search_vehicles('test')

    def test_null_search_arrays_are_treated_as_empty(self):
        payload = json.dumps({'results': None, '_embedded': {'data': {'results': None}}}).encode()
        client = AutoAPITwoConnector(opener=lambda *a, **k: io.BytesIO(payload))
        self.assertEqual(client.search_vehicles('test'), [])
        self.assertEqual(client.search('1', 'starter'), [])

    def test_article_catalog_uses_bounded_search_index_without_fetching_bodies(self):
        calls = []
        progress = []

        def response(payload):
            return io.BytesIO(json.dumps(payload).encode())

        def opener(req, **kwargs):
            path = urlsplit(req.full_url).path
            calls.append(path)
            if '/search/' in path:
                return response({
                    '_embedded': {'data': {
                        'results': [{
                            'display': 'Engine and Cooling >> Service and Repair >> Engine Oil Pump Removal And Installation',
                            'itypeCategory': {'name': 'Service and Repair'},
                            '_links': {'self': {'href': '/api/v1/content/carids/1/components/72/itypes/401/nonstandards/1535667'}},
                        }] if path.endswith('/search/a') else [],
                    }},
                })
            raise AssertionError(f'unexpected catalog read: {path}')

        client = AutoAPITwoConnector(opener=opener, retry_delay=0)
        result = client.fetch_article_catalog('1', on_progress=progress.append)

        self.assertEqual(result['index_reads'], 36)
        self.assertEqual(result['component_reads'], 0)
        self.assertEqual(result['information_type_reads'], 0)
        self.assertEqual(result['articles'][0]['id'], 'autoapitwo:1:1535667')
        self.assertEqual(result['articles'][0]['title'], 'Engine Oil Pump Removal And Installation')
        self.assertNotIn('/api/v1/content/carids/1/nonstandards/1535667', calls)
        self.assertTrue(all('/search/' in path for path in calls))
        self.assertEqual(progress[-1]['processed_units'], 36)
        self.assertEqual(progress[-1]['total_units'], 36)
        self.assertEqual(progress[-1]['phase'], 'indexing')
        self.assertEqual(progress[-1]['outcome'], 'succeeded')
        self.assertIn('Article-index query', progress[-1]['detail'])
        self.assertIn('article links returned', progress[-1]['detail'])

    def test_article_catalog_failure_progress_names_failure_reason(self):
        progress = []

        def opener(req, **kwargs):
            raise HTTPError(req.full_url, 429, 'rate limited', {}, io.BytesIO())

        client = AutoAPITwoConnector(opener=opener, retry_attempts=1, retry_delay=0)
        with self.assertRaises(SourceUnavailable):
            client.fetch_article_catalog('1', on_progress=progress.append)

        self.assertTrue(progress)
        self.assertTrue(all(item['outcome'] == 'failed' for item in progress))
        self.assertTrue({item['term'] for item in progress} >= {'a', 'b', 'c'})
        self.assertTrue(all('rate limited' in item['detail'] for item in progress))

    def test_source_failure_reason_classifies_common_provider_failures(self):
        self.assertEqual(
            _source_failure_reason(HTTPError('https://example.test', 401, 'expired token', {}, io.BytesIO())),
            'authentication expired or unauthorized',
        )
        self.assertEqual(
            _source_failure_reason(HTTPError('https://example.test', 504, 'gateway timeout', {}, io.BytesIO())),
            'server timed out',
        )
        self.assertEqual(_source_failure_reason(TimeoutError('timed out')), 'server timed out')
        self.assertEqual(
            _source_failure_reason(SourceUnavailable('AutoAPItwo did not resolve a matching vehicle')),
            'returned no matching vehicle',
        )
