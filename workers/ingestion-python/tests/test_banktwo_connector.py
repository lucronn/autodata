import base64
from hashlib import sha256
import io
import json
import unittest
from urllib.error import HTTPError
from urllib.parse import urlsplit
from uuid import uuid4

from autodata_ingestion.banktwo_connector import BanktwoConnector, ArticleParser, SourceUnavailable
from autodata_ingestion.source_connector_client import SourceConnectorClient, SourceConnectorError


class FixtureResponse(io.BytesIO):
    status = 200

    def __init__(self, payload, *, url, headers):
        super().__init__(payload)
        self.url = url
        self.headers = headers

    def geturl(self):
        return self.url


def envelope(**body):
    return {
        "request_id": str(uuid4()),
        "provider": "banktwo",
        "source_revision": "fixture-r7",
        "fetched_at": "2026-10-08T12:00:00Z",
        "source_locator": "https://banktwo.cars.tk/source/article/opaque",
        **body,
    }


class ConnectorTests(unittest.TestCase):
    def test_legacy_article_id_maps_by_exact_unambiguous_opaque_suffix(self):
        descriptors = [
            {"opaque_ref": "1535667", "resource_ref": "resource-opaque"},
            {"opaque_ref": "1535668", "resource_ref": "other-resource"},
        ]
        legacy_id = "autoapitwo:52597:1535667"
        descriptor = BanktwoConnector.descriptor_for_legacy_article_id(legacy_id, descriptors)
        self.assertEqual(descriptor["resource_ref"], "resource-opaque")

        # The descriptor ref is not expanded or substituted into the persisted
        # identity when the caller resolved the historical ID.
        self.assertEqual(legacy_id, "autoapitwo:52597:1535667")
        with self.assertRaises(SourceUnavailable):
            BanktwoConnector.descriptor_for_legacy_article_id(
                "autoapitwo:52597:missing", descriptors
            )
        with self.assertRaises(SourceUnavailable):
            BanktwoConnector.descriptor_for_legacy_article_id(
                legacy_id, descriptors + [{"opaque_ref": "1535667", "resource_ref": "duplicate"}]
            )

    def test_legacy_article_output_id_can_be_preserved_while_reading_opaque_resource(self):
        raw = b"<p>Remove the pump.</p>"
        legacy_id = "autoapitwo:52597:1535667"

        def opener(request, timeout):
            self.assertEqual(urlsplit(request.full_url).path, "/v1/resources/article-resource")
            body = envelope(kind="article", media_type="text/html", sha256=sha256(raw).hexdigest(),
                            content=raw.decode())
            return FixtureResponse(json.dumps(body).encode(), url=request.full_url,
                                   headers={"Content-Type": "application/json"})

        client = SourceConnectorClient("https://banktwo.cars.tk", provider="banktwo", opener=opener)
        article = BanktwoConnector(source_client=client).article_by_legacy_id(
            "vehicle-opaque", legacy_id,
            [{"opaque_ref": "1535667", "resource_ref": "article-resource"}],
        )
        self.assertEqual(article["article_id"], legacy_id)
        self.assertEqual(article["source_resource_ref"], "article-resource")

    def test_parser_preserves_order_values_and_images_without_executable_html(self):
        parser = ArticleParser()
        parser.feed('<script>bad()</script>1. Install gasket<br/>Torque: <b>8.8 Nm</b><img src="https://upstream.invalid/figure"/><br/>2. Install cover')
        parser.flush()
        self.assertEqual([b["kind"] for b in parser.blocks], ["text", "text", "image", "text"])
        self.assertEqual(parser.blocks[1]["text"], "Torque: 8.8 Nm")
        self.assertNotIn("bad()", str(parser.blocks))

    def test_selected_article_labor_and_asset_use_only_opaque_v1_refs(self):
        html = '<h2>REMOVAL</h2><p>Remove the pump.</p><img src="https://upstream.invalid/fig/pump.png"/><p>Torque 8.8 Nm.</p>'
        article_bytes = html.encode()
        labor_bytes = b"Labor 2.5 hours; includes gasket replacement."
        asset_bytes = b"\x89PNG\r\n\x1a\nfixture-image"
        calls = []

        def opener(request, timeout):
            path = urlsplit(request.full_url).path
            calls.append((request.method, path))
            if path.endswith("/v1/resources/article-resource"):
                body = envelope(
                    kind="article", media_type="text/html", sha256=sha256(article_bytes).hexdigest(),
                    content=html, asset_resource_refs=["asset-opaque-1"],
                )
                return FixtureResponse(json.dumps(body).encode(), url=request.full_url,
                                       headers={"Content-Type": "application/json"})
            if path.endswith("/v1/resources/labor-resource"):
                body = envelope(kind="labor", media_type="text/plain", sha256=sha256(labor_bytes).hexdigest(),
                                content=labor_bytes.decode())
                return FixtureResponse(json.dumps(body).encode(), url=request.full_url,
                                       headers={"Content-Type": "application/json"})
            if path.endswith("/v1/resources/asset-opaque-1"):
                headers = {
                    "Content-Type": "application/octet-stream",
                    "X-Request-Id": str(uuid4()),
                    "X-Provider": "banktwo",
                    "X-Source-Revision": "fixture-r7",
                    "X-Fetched-At": "2026-10-08T12:00:00Z",
                    "X-Source-Locator": "https://banktwo.cars.tk/source/assets/opaque",
                    "X-Source-Sha256": sha256(asset_bytes).hexdigest(),
                    "X-Source-Media-Type": "image/png",
                }
                return FixtureResponse(asset_bytes, url=request.full_url, headers=headers)
            raise AssertionError(f"unexpected connector route {path}")

        generic = SourceConnectorClient("https://banktwo.cars.tk", provider="banktwo", opener=opener)
        connector = BanktwoConnector(source_client=generic)
        article = connector.article_by_descriptor("vehicle-opaque-1", {
            "opaque_ref": "article-opaque-1", "resource_ref": "article-resource",
            "labor_resource_ref": "labor-resource", "asset_resource_refs": ["asset-opaque-1"],
            "title": "Oil Pump Removal", "category": "Service and Repair",
        })

        self.assertEqual(article["raw_html"], html)
        self.assertEqual(article["article_id"], "autoapitwo:vehicle-opaque-1:article-opaque-1")
        self.assertEqual(article["source_sha256"], sha256(article_bytes).hexdigest())
        self.assertEqual(article["source_revision"], "fixture-r7")
        self.assertEqual(article["source_provider"], "banktwo")
        self.assertEqual(article["source_asset_refs"], ["asset-opaque-1"])
        self.assertEqual(article["labor_body"], labor_bytes.decode())
        self.assertEqual(article["labor_source_sha256"], sha256(labor_bytes).hexdigest())
        self.assertEqual(article["images"][0]["asset_resource_ref"], "asset-opaque-1")
        self.assertNotIn("url", article["images"][0])
        self.assertEqual(calls, [
            ("GET", "/v1/resources/article-resource"),
            ("GET", "/v1/resources/labor-resource"),
        ])

        asset = generic.read_resource("asset-opaque-1").to_source_resource()
        self.assertEqual(asset.payload, asset_bytes)
        self.assertEqual(asset.content_sha256, sha256(asset_bytes).hexdigest())
        self.assertEqual(calls[-1], ("GET", "/v1/resources/asset-opaque-1"))
        self.assertTrue(all(path.startswith("/v1/") for _, path in calls))

    def test_mismatched_source_hash_is_rejected_before_resource_use(self):
        raw = b"content"

        def opener(request, timeout):
            body = envelope(kind="article", media_type="text/html", sha256="0" * 64, content=raw.decode())
            return FixtureResponse(json.dumps(body).encode(), url=request.full_url,
                                   headers={"Content-Type": "application/json"})

        client = SourceConnectorClient("https://banktwo.cars.tk", provider="banktwo", opener=opener)
        with self.assertRaises(SourceConnectorError) as raised:
            client.read_resource("article-ref")
        self.assertEqual(raised.exception.code, "INVALID_UPSTREAM_RESPONSE")

    def test_unauthorized_and_unavailable_errors_keep_stable_codes(self):
        for status, expected in ((401, "UNAUTHORIZED"), (503, "UPSTREAM_UNAVAILABLE")):
            def opener(request, timeout, status=status):
                raise HTTPError(request.full_url, status, "provider detail is sanitized", {}, io.BytesIO())

            client = SourceConnectorClient("https://banktwo.cars.tk", provider="banktwo", opener=opener)
            with self.subTest(status=status), self.assertRaises(SourceConnectorError) as raised:
                client.read_resource("opaque-ref")
            self.assertEqual(raised.exception.code, expected)

    def test_compatibility_facade_maps_connector_errors_without_provider_text(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 401, "secret detail", {}, io.BytesIO())

        connector = BanktwoConnector(source_client=SourceConnectorClient(
            "https://banktwo.cars.tk", provider="banktwo", opener=opener
        ))
        with self.assertRaises(SourceUnavailable) as raised:
            connector.read_resource("opaque-ref")
        self.assertEqual(raised.exception.code, "UNAUTHORIZED")
        self.assertNotIn("secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
