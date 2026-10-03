import hashlib
import io
import unittest
from urllib.parse import urlsplit

from autodata_ingestion.autodbtwo_http_client import AutoDBtwoHTTPClient, AutoDBtwoRequestError


class _Response(io.BytesIO):
    def __init__(self, url, payload):
        super().__init__(payload)
        self._url = url
        self.status = 200
        self.headers = {
            "Content-Type": "application/json",
            "X-Source-Uri": "https://autoapitwo.test/api/v1/content/carids/12/components/867/itypes/401/nonstandards/9",
            "X-Content-Sha256": hashlib.sha256(payload).hexdigest(),
        }

    def geturl(self):
        return self._url


class AutoDBtwoHTTPClientTests(unittest.TestCase):
    def test_article_path_is_forwarded_to_vehicle_scoped_autodbtwo_route(self):
        calls = []
        payload = b'{"ok":true}'

        def opener(request, **_kwargs):
            calls.append(request.full_url)
            return _Response(request.full_url, payload)

        client = AutoDBtwoHTTPClient("http://autodbtwo:3001", upstream_base_url="https://autoapitwo.test", opener=opener)
        result = client.read("https://autoapitwo.test/api/v1/content/carids/12/components/867/itypes/401/nonstandards/9", car_id="12")
        self.assertEqual(result.body, payload)
        self.assertEqual(result.content_sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(result.source_uri, "https://autoapitwo.test/api/v1/content/carids/12/components/867/itypes/401/nonstandards/9")
        target = urlsplit(calls[0])
        self.assertEqual(target.netloc, "autodbtwo:3001")
        self.assertEqual(target.path, "/v1/content/carids/12/resource")
        self.assertIn("path=%2Fapi%2Fv1%2Fcontent%2Fcarids%2F12", target.query)

    def test_binary_and_catalog_routes_are_mapped_to_autodbtwo(self):
        calls = []

        def opener(request, **_kwargs):
            calls.append(request.full_url)
            return _Response(request.full_url, b'{"ok":true}')

        client = AutoDBtwoHTTPClient("http://127.0.0.1:3001", upstream_base_url="https://autoapitwo.test", opener=opener)
        client.read("https://autoapitwo.test/api/v1/fleet/years/2012/makes/Ram/models/Ram%201500/engines")
        client.read("https://autoapitwo.test/api/v1/content/carids/12/images/figure.png", binary=True, car_id="12")
        self.assertIn("/v1/fleet/resource?", calls[0])
        self.assertIn("/v1/content/carids/12/resource?", calls[1])
        self.assertIn("binary=true", calls[1])

    def test_rejects_foreign_origins_and_vehicle_mismatches(self):
        client = AutoDBtwoHTTPClient("http://127.0.0.1:3001", upstream_base_url="https://autoapitwo.test", opener=lambda *_args, **_kwargs: None)
        with self.assertRaises(AutoDBtwoRequestError):
            client.read("https://elsewhere.test/api/v1/content/carids/12/article/9", car_id="12")
        with self.assertRaises(AutoDBtwoRequestError):
            client.read("https://autoapitwo.test/api/v1/content/carids/13/article/9", car_id="12")


if __name__ == "__main__":
    unittest.main()
