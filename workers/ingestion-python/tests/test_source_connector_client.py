import base64
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.source_connector_client import (
    SourceConnectorClient,
    SourceConnectorError,
    source_connector_registry,
)
from autodata_ingestion.catalog_service import (
    CacheFirstCatalogService,
    CatalogRequest,
    _SourceCatalogProvider,
    _configured_catalog_providers,
    _merge_rows,
    _persist_resolved_catalog_rows,
)
from autodata_ingestion.catalog_years import _read_year_pages
from autodata_ingestion.catalog_sync import _iter_catalog_rows
from autodata_ingestion import catalog_sync, catalog_years


class _Response:
    def __init__(self, body, *, url, status=200, headers=None):
        self.payload = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.url = url
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}
        self.offset = 0

    def read(self, limit=-1):
        result = self.payload[self.offset:] if limit < 0 else self.payload[self.offset:self.offset + limit]
        self.offset += len(result)
        return result

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _envelope(provider="bankone", **extra):
    return {
        "request_id": "00000000-0000-4000-8000-000000000001",
        "provider": provider,
        "source_revision": "revision-1",
        "fetched_at": "2026-10-08T12:00:00Z",
        **extra,
    }


class SourceConnectorClientTests(unittest.TestCase):
    def test_registry_uses_separate_origins_and_tokens(self):
        env = {
            "BANKONE_BASE_URL": "https://bankone.cars.tk",
            "BANKTWO_BASE_URL": "https://banktwo.cars.tk",
            "BANKONE_API_TOKEN": "one-secret",
            "BANKTWO_API_TOKEN": "two-secret",
        }
        with patch.dict("os.environ", env, clear=True):
            registry = source_connector_registry()
        self.assertEqual(set(registry), {"bankone", "banktwo"})
        self.assertEqual(registry["bankone"].base_url, "https://bankone.cars.tk")
        self.assertEqual(registry["banktwo"].base_url, "https://banktwo.cars.tk")
        with patch.dict("os.environ", env, clear=True):
            providers = _configured_catalog_providers()
        self.assertEqual([provider.client.provider for provider in providers], ["bankone", "banktwo"])

    def test_partial_catalog_keeps_cursor_and_request_scope(self):
        calls = []

        def open_request(request, timeout):
            calls.append((request.full_url, timeout))
            return _Response(_envelope(scope="models", complete=False, next_cursor="next-2", items=[{
                "opaque_ref": "vehicle/model/1", "label": "Sedan", "year": 2020,
                "make": "Example", "model": "Sedan",
            }]), url=request.full_url)

        client = SourceConnectorClient("https://bankone.cars.tk", provider="bankone", opener=open_request)
        page = client.catalog("models", {"year": 2020, "make": "Example"}, cursor="first/1")
        self.assertFalse(page.complete)
        self.assertEqual(page.next_cursor, "next-2")
        self.assertEqual(page.persisted_provider, "autoapi")
        self.assertIn("cursor=first%2F1", calls[0][0])

    def test_ambiguous_resolution_and_article_order_are_preserved(self):
        selector = {"year": 2020, "make": "Example", "model": "Sedan"}
        resolution = _envelope(selector=selector, candidates=[
            {"opaque_ref": "car:1", "label": "Base", "confidence": 0.8},
            {"opaque_ref": "car:2", "label": "Sport", "confidence": 0.8},
        ])
        articles = _envelope(complete=True, articles=[
            {"opaque_ref": "article:2", "title": "Second", "resource_ref": "resource:2"},
            {"opaque_ref": "article:1", "title": "First", "resource_ref": "resource:1"},
        ])
        responses = [resolution, articles]
        client = SourceConnectorClient(
            "https://bankone.cars.tk", provider="bankone",
            opener=lambda request, timeout: _Response(responses.pop(0), url=request.full_url),
        )
        resolved = client.resolve_vehicle(selector)
        listed = client.list_articles("car:1")
        self.assertEqual([item["opaque_ref"] for item in resolved.body["candidates"]], ["car:1", "car:2"])
        self.assertEqual([item["resource_ref"] for item in listed.body["articles"]], ["resource:2", "resource:1"])

    def test_resource_keeps_exact_bytes_sha_and_locator(self):
        payload = b"\x89PNG\r\n\x1a\nsource bytes"
        digest = hashlib.sha256(payload).hexdigest()
        source = _envelope(
            kind="asset", media_type="image/png", content_base64=base64.b64encode(payload).decode(),
            sha256=digest, source_locator="https://bankone.cars.tk/source/item/42",
        )
        client = SourceConnectorClient(
            "https://bankone.cars.tk", provider="bankone",
            opener=lambda request, timeout: _Response(source, url=request.full_url),
        )
        resource = client.read_resource("asset/1").to_source_resource()
        self.assertEqual(resource.payload, payload)
        self.assertEqual(resource.content_sha256, digest)
        self.assertEqual(resource.source_version, "revision-1")
        self.assertEqual(resource.locator, source["source_locator"])
        self.assertEqual(resource.metadata["provider"], "autoapi")

    def test_binary_octet_stream_requires_headers_and_valid_hash(self):
        payload = b"binary evidence"
        digest = hashlib.sha256(payload).hexdigest()
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Request-Id": "00000000-0000-4000-8000-000000000001",
            "X-Provider": "banktwo", "X-Source-Revision": "rev-2",
            "X-Fetched-At": "2026-10-08T12:00:00Z",
            "X-Source-Locator": "https://banktwo.cars.tk/source/asset/1",
            "X-Source-Sha256": digest, "X-Source-Media-Type": "image/png",
        }
        client = SourceConnectorClient(
            "https://banktwo.cars.tk", provider="banktwo",
            opener=lambda request, timeout: _Response(payload, url=request.full_url, headers=headers),
        )
        resource = client.read_resource("asset:1").to_source_resource()
        self.assertEqual(resource.payload, payload)
        self.assertEqual(resource.metadata["provider"], "autoapitwo")

    def test_rejects_redirect_oversize_mismatched_provider_and_corrupt_hash(self):
        base = "https://bankone.cars.tk"
        valid = _envelope(capabilities=["catalog"])
        cases = [
            (_Response(valid, url="https://other.example/v1/capabilities"), "INVALID_UPSTREAM_RESPONSE"),
            (_Response(valid, url=base + "/v1/capabilities", headers={"Content-Type": "application/json", "Content-Length": "999999999"}), "INVALID_UPSTREAM_RESPONSE"),
            (_Response(_envelope("banktwo", capabilities=["catalog"]), url=base + "/v1/capabilities"), "INVALID_UPSTREAM_RESPONSE"),
        ]
        for response, code in cases:
            with self.subTest(response=response):
                client = SourceConnectorClient(base, provider="bankone", opener=lambda _request, timeout: response)
                with self.assertRaises(SourceConnectorError) as caught:
                    client.capabilities()
                self.assertEqual(caught.exception.code, code)
        resource = _envelope(kind="article", media_type="text/plain", content="text", sha256="0" * 64)
        client = SourceConnectorClient(base, provider="bankone", opener=lambda request, timeout: _Response(resource, url=request.full_url))
        with self.assertRaises(SourceConnectorError):
            client.read_resource("article:1")
        secret_locator = _envelope(
            kind="article", media_type="text/plain", content="safe",
            sha256=hashlib.sha256(b"safe").hexdigest(),
            source_locator="https://upstream.example/item?token=secret",
        )
        client = SourceConnectorClient(base, provider="bankone", opener=lambda request, timeout: _Response(secret_locator, url=request.full_url))
        with self.assertRaises(SourceConnectorError):
            client.read_resource("article:1")

    def test_http_failures_have_stable_redacted_errors(self):
        token = "top-secret-token"
        def reject(request, timeout):
            self.assertEqual(request.get_header("Authorization"), "Bearer " + token)
            raise HTTPError(request.full_url, 429, "upstream token leaked", {}, None)
        client = SourceConnectorClient("https://bankone.cars.tk", token=token, opener=reject)
        with self.assertRaises(SourceConnectorError) as caught:
            client.capabilities()
        self.assertEqual(caught.exception.code, "RATE_LIMITED")
        self.assertTrue(caught.exception.retryable)
        self.assertNotIn(token, str(caught.exception))
        client = SourceConnectorClient("https://bankone.cars.tk", opener=lambda request, timeout: (_ for _ in ()).throw(URLError("token leak")))
        with self.assertRaises(SourceConnectorError) as caught:
            client.capabilities()
        self.assertEqual(caught.exception.code, "UPSTREAM_UNAVAILABLE")
        self.assertNotIn("token leak", str(caught.exception))

    def test_rejects_unsafe_origins_and_refs(self):
        for base in ("https://user:password@bankone.cars.tk", "https://bankone.cars.tk/path", "http://bankone.cars.tk"):
            with self.subTest(base=base), self.assertRaises(ValueError):
                SourceConnectorClient(base)
        client = SourceConnectorClient("https://bankone.cars.tk")
        with self.assertRaises(ValueError):
            client.read_resource("..")

    def test_catalog_call_site_uses_v1_pages_and_preserves_legacy_mapping(self):
        calls = []
        pages = [
            _envelope("banktwo", scope="configurations", complete=False, next_cursor="page-2", items=[{
                "opaque_ref": "car:1", "label": "2020 Example Sedan Base", "year": 2020,
                "make": "Example", "model": "Sedan", "configuration": "Base",
            }]),
            _envelope("banktwo", scope="configurations", complete=True, items=[{
                "opaque_ref": "car:2", "label": "2020 Example Sedan Sport", "year": 2020,
                "make": "Example", "model": "Sedan", "configuration": "Sport",
            }]),
        ]

        def open_request(request, timeout):
            calls.append(request.full_url)
            return _Response(pages.pop(0), url=request.full_url)

        provider = _SourceCatalogProvider(SourceConnectorClient(
            "https://banktwo.cars.tk", provider="banktwo", opener=open_request,
        ))
        result = provider.resolve_catalog(CatalogRequest(2020, "Example", "Sedan", scope="configurations"))
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["rows"][0]["provider_mappings"][0]["provider"], "autoapitwo")
        self.assertEqual(result["rows"][0]["provider_mappings"][0]["entity_type"], "car")
        self.assertEqual(result["rows"][0]["provider_mappings"][0]["provider_id"], "car:1")
        self.assertIn("cursor=page-2", calls[1])

    def test_year_warmup_rejects_repeated_cursor(self):
        page = _envelope("banktwo", scope="years", complete=False, next_cursor="same", items=[{
            "opaque_ref": "2020", "label": "2020", "year": 2020,
        }])
        client = SourceConnectorClient(
            "https://banktwo.cars.tk", provider="banktwo",
            opener=lambda request, timeout: _Response(page, url=request.full_url),
        )
        with self.assertRaisesRegex(ValueError, "pagination did not advance"):
            _read_year_pages(client)

    def test_sparse_selector_scopes_keep_completeness_and_years_are_unfiltered(self):
        cases = (
            ("years", {"opaque_ref": "year:2020", "label": "2020", "year": 2020}, {"year"}),
            ("makes", {"opaque_ref": "make:example", "label": "Example", "year": 2020, "make": "Example"}, {"year", "make"}),
            ("models", {"opaque_ref": "model:sedan", "label": "Sedan", "year": 2020, "make": "Example", "model": "Sedan"}, {"year", "make", "model"}),
        )
        for scope, item, expected_fields in cases:
            with self.subTest(scope=scope):
                calls = []

                def open_request(request, timeout):
                    calls.append(request.full_url)
                    return _Response(_envelope("banktwo", scope=scope, complete=True, items=[item]), url=request.full_url)

                provider = _SourceCatalogProvider(SourceConnectorClient(
                    "https://banktwo.cars.tk", provider="banktwo", opener=open_request,
                ))
                request = CatalogRequest(2020, "placeholder", "placeholder", scope=scope)
                self.assertTrue(provider.resolve_catalog(request)["complete"])
                result = CacheFirstCatalogService(cache_reader=lambda _request: None, providers=[provider]).resolve(request)

                self.assertTrue(result.complete)
                self.assertEqual(len(result.rows), 1)
                self.assertTrue(expected_fields.issubset(result.rows[0]))
                self.assertFalse({"year", "make", "model", "region"}.issubset(result.rows[0]))
                persistence = _persist_resolved_catalog_rows(result.rows, scope=scope, provenance=result.provenance)
                self.assertEqual(persistence["status"], "no_persistable_rows")
                if scope == "years":
                    self.assertNotIn("year=", calls[0])

    def test_same_canonical_row_retains_both_provider_mappings(self):
        canonical = {"year": 2020, "make": "Example", "model": "Sedan", "region": "US"}
        merged = _merge_rows([], [
            {**canonical, "provider_mappings": [{"provider": "autoapi", "entity_type": "car", "provider_id": "one:1"}]},
            {**canonical, "provider_mappings": [{"provider": "autoapitwo", "entity_type": "car", "provider_id": "two:1"}]},
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual(
            {(mapping["provider"], mapping["provider_id"]) for mapping in merged[0]["provider_mappings"]},
            {("autoapi", "one:1"), ("autoapitwo", "two:1")},
        )

    def test_catalog_sync_keeps_structured_dimensions_and_opaque_ref(self):
        source_ref = "hmac:v1:opaque-vehicle"
        page = _envelope("banktwo", scope="configurations", complete=True, source_locator="source:catalog:123", items=[{
            "opaque_ref": source_ref, "label": "Example Sedan 2.4L AWD",
            "year": 2020, "make": "Example", "model": "Sedan",
            "configuration": "Touring", "engine": "2.4L",
            "drivetrain": "AWD", "region": "CA",
        }])
        client = SourceConnectorClient(
            "https://banktwo.cars.tk", provider="banktwo",
            opener=lambda request, timeout: _Response(page, url=request.full_url),
        )
        row, = list(_iter_catalog_rows(client))
        self.assertEqual((row["engine"], row["drivetrain"], row["region"]), ("2.4L", "AWD", "CA"))
        self.assertEqual(row["source_vehicle_ref"], source_ref)
        self.assertEqual(row["provider_mappings"][0]["provider_id"], source_ref)
        self.assertNotIn("autoapitwo_vehicle_id", row)

    def test_catalog_sync_uses_each_v1_page_revision_for_snapshot_watermark(self):
        pages = iter((
            _envelope("banktwo", scope="configurations", complete=False, next_cursor="page-2",
                      source_revision="bank-rev-1", source_locator="source:page:1", items=[{
                          "opaque_ref": "car:1", "label": "Example Sedan", "year": 2020,
                          "make": "Example", "model": "Sedan",
                      }]),
            _envelope("banktwo", scope="configurations", complete=True,
                      source_revision="bank-rev-2", source_locator="source:page:2", items=[{
                          "opaque_ref": "car:2", "label": "Example Coupe", "year": 2021,
                          "make": "Example", "model": "Coupe",
                      }]),
        ))

        class Client:
            base_url = "https://banktwo.cars.tk"

            def catalog(self, scope, selector=None, cursor=None):
                return SourceConnectorClient(
                    self.base_url, provider="banktwo",
                    opener=lambda request, timeout: _Response(next(pages), url=request.full_url),
                ).catalog(scope, selector, cursor)

        persisted = []
        with patch("autodata_ingestion.catalog_sync.source_connector_registry", return_value={"banktwo": Client()}), \
                patch.object(catalog_sync, "_persist_batch", side_effect=lambda *args: persisted.append(args)), \
                patch.object(catalog_sync, "_finish"):
            catalog_sync._run_claimed("sync-v1", "legacy-job-version", "legacy-traversal")

        self.assertEqual([entry[2] for entry in persisted], ["bank-rev-1", "bank-rev-2"])
        self.assertEqual([entry[3] for entry in persisted], ["source:page:1", "source:page:2"])

    def test_persist_batch_uses_row_revision_but_keeps_legacy_fallback(self):
        from autodata_ingestion import vehicle_selection_persistence

        with patch.object(vehicle_selection_persistence, "persist_vehicle_selection_list") as persist, \
                patch.object(catalog_sync, "_record_scopes"):
            catalog_sync._persist_batch("sync-1", [{"year": 2020, "source_revision": "bank-rev", "source_locator": "source:page"}], "legacy-job", "legacy-uri")
        self.assertEqual(persist.call_args.kwargs["source_version"], "bank-rev")
        self.assertEqual(persist.call_args.kwargs["source_uri"], "source:page")

        with patch.object(vehicle_selection_persistence, "persist_vehicle_selection_list") as persist, \
                patch.object(catalog_sync, "_record_scopes"):
            catalog_sync._persist_batch("sync-1", [{"year": 2020}], "legacy-job", "legacy-uri")
        self.assertEqual(persist.call_args.kwargs["source_version"], "legacy-job")
        self.assertEqual(persist.call_args.kwargs["source_uri"], "legacy-uri")

    def test_unconfigured_catalog_jobs_use_banktwo_v1_default(self):
        banktwo = type("Client", (), {"base_url": "https://banktwo.cars.tk"})()
        with patch.dict(os.environ, {}, clear=True), \
                patch("autodata_ingestion.catalog_years.source_connector_registry", return_value={"banktwo": banktwo}) as registry, \
                patch.object(catalog_years, "_read_year_pages", return_value=([2020], "https://banktwo.cars.tk/v1/catalog/years")), \
                patch.object(catalog_years, "persist_catalog_years", return_value={"year_count": 1}) as persist_years, \
                patch.object(catalog_years, "_finish") as finish_years:
            catalog_years._run_claimed("sync-1", "legacy-version")
            registry.assert_called_once_with(include_defaults=True)
            self.assertEqual(persist_years.call_args.kwargs["source_uri"], "https://banktwo.cars.tk/v1/catalog/years")
            self.assertEqual(finish_years.call_args.kwargs["status"], "completed")

        with patch.dict(os.environ, {}, clear=True), \
                patch("autodata_ingestion.catalog_sync.source_connector_registry", return_value={"banktwo": banktwo}) as registry, \
                patch("autodata_ingestion.catalog_sync._iter_catalog_rows", return_value=[{"year": 2020, "make": "Example", "model": "Sedan"}]), \
                patch.object(catalog_sync, "_persist_batch") as persist_rows, \
                patch.object(catalog_sync, "_finish") as finish_rows:
            catalog_sync._run_claimed("sync-2", "legacy-version", "legacy-traversal")
            registry.assert_called_once_with(include_defaults=True)
            self.assertEqual(persist_rows.call_args.args[3], "https://banktwo.cars.tk/v1/catalog/configurations")
            self.assertEqual(finish_rows.call_args.kwargs["status"], "completed")


if __name__ == "__main__":
    unittest.main()
