import io
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError

from autodata_ingestion.autoapitwo_connector import AutoAPITwoConnector, ArticleParser, SourceUnavailable


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

    def test_oversize_rejected(self):
        client = AutoAPITwoConnector(max_bytes=2, opener=lambda *a, **k: io.BytesIO(b'large'))
        with self.assertRaises(SourceUnavailable): client.search_vehicles('test')

    def test_null_search_arrays_are_treated_as_empty(self):
        payload = json.dumps({'results': None, '_embedded': {'data': {'results': None}}}).encode()
        client = AutoAPITwoConnector(opener=lambda *a, **k: io.BytesIO(payload))
        self.assertEqual(client.search_vehicles('test'), [])
        self.assertEqual(client.search('1', 'starter'), [])
