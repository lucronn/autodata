import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.http_connector import HttpSourceConnector  # noqa: E402


class _Response:
    status = 200

    def __init__(self, payload: bytes, headers: dict[str, str], final_url: str):
        self._payload = payload
        self._headers = headers
        self._final_url = final_url

    @property
    def headers(self):
        return self._headers

    def geturl(self):
        return self._final_url

    def read(self, size: int = -1):
        if size < 0:
            payload, self._payload = self._payload, b""
            return payload
        payload, self._payload = self._payload[:size], self._payload[size:]
        return payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class HttpSourceConnectorTests(unittest.TestCase):
    def test_fetch_preserves_http_metadata_and_sniffs_generic_content(self):
        payload = b'{"body":"2019 Cadillac Escalade ESV"}'
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return _Response(
                payload,
                {
                    "Content-Type": "application/octet-stream",
                    "ETag": '"drop-v2"',
                    "X-Source-Page": "1",
                    "Set-Cookie": "session=secret",
                },
                "https://source.example/redirected-resource",
            )

        connector = HttpSourceConnector(
            "https://source.example/resource",
            opener=opener,
            timeout_seconds=7,
            max_bytes=1024,
            request_headers={"Accept": "application/json"},
        )

        resources = connector.fetch({})

        self.assertEqual(len(resources), 1)
        resource = resources[0]
        self.assertEqual(resource.media_type, "application/json")
        self.assertEqual(resource.source_version, "drop-v2")
        self.assertEqual(resource.source_uri, "https://source.example/resource")
        self.assertEqual(resource.locator, "https://source.example/resource")
        self.assertEqual(resource.metadata["http_status"], 200)
        self.assertEqual(resource.metadata["final_source_uri"], "https://source.example/redirected-resource")
        self.assertEqual(resource.metadata["response_headers"]["x-source-page"], "1")
        self.assertNotIn("set-cookie", resource.metadata["response_headers"])
        self.assertEqual(
            requests[0][0].header_items(),
            [("User-agent", "autodata-ingestion/1"), ("Accept", "application/json")],
        )
        self.assertEqual(requests[0][1], 7)

    def test_fetch_rejects_http_payloads_over_the_configured_limit(self):
        connector = HttpSourceConnector(
            "http://source.example/resource",
            opener=lambda _request, timeout: _Response(b"12345", {}, "http://source.example/resource"),
            max_bytes=4,
        )

        with self.assertRaisesRegex(ValueError, "maximum source size"):
            connector.fetch({})

    def test_connector_rejects_non_http_urls_and_embedded_credentials(self):
        with self.assertRaisesRegex(ValueError, "http or https"):
            HttpSourceConnector("file:///tmp/source")
        with self.assertRaisesRegex(ValueError, "credentials"):
            HttpSourceConnector("https://user:password@source.example/resource")

    def test_connector_rejects_newlines_in_configured_request_headers(self):
        with self.assertRaisesRegex(ValueError, "header"):
            HttpSourceConnector("https://source.example/resource", request_headers={"X-Source": "bad\nvalue"})

    def test_request_can_supply_a_source_version_without_replacing_connector_defaults(self):
        connector = HttpSourceConnector(
            "https://source.example/resource",
            source_version="default-version",
            opener=lambda _request, timeout: _Response(
                b"plain text", {"Last-Modified": "Wed, 03 Sep 2026 12:00:00 GMT"}, "https://source.example/resource"
            ),
        )

        resource = connector.fetch({"source_version": "request-version"})[0]

        self.assertEqual(resource.source_version, "request-version")


if __name__ == "__main__":
    unittest.main()
