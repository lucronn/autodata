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

    def test_table_caption_fallback_keeps_existing_text_and_media(self):
        for html in (
            '<table><caption>Service data</caption></table>',
            '<table><caption>Service data<tr><td>18 Nm</td></tr></table>',
            '<table><caption>Service <img src="/figure.png">data</caption><tr><td>18 Nm</td></tr></table>',
            '<table><caption>Service data</caption><tr><td><table><tr><td>18 Nm</td></tr></table></td></tr></table>',
        ):
            with self.subTest(html=html):
                old = ArticleParser()
                new = ArticleParser(keep_html_table_captions=True)
                for parser in (old, new):
                    parser.feed(html)
                    parser.close()
                    parser.flush()
                self.assertEqual(new.blocks, old.blocks)
                self.assertFalse(new.html_table_captions)

    def test_multiline_figure_caption_leaves_mixed_media_in_the_authored_flow(self):
        html = (
            '<figure><img src="/pressure.png"><figcaption>Pressure chart<br>'
            '<img src="/legend.png">Readings at idle</figcaption></figure>Check the seal.'
        )
        old = ArticleParser(keep_html_flow_figure_captions=True)
        new = ArticleParser(keep_html_flow_figure_captions=True, keep_html_multiline_figure_captions=True)
        for parser in (old, new):
            parser.feed(html)
            parser.close()
            parser.flush()
        self.assertEqual(new.blocks, old.blocks)
        self.assertFalse(new.html_multiline_figure_captions)

    def test_opt_in_preserves_heading_levels_and_ends_each_heading(self):
        parser = ArticleParser(keep_html_headings=True)
        parser.feed(
            'Read first. <h1>Repair &amp; Service</h1>'
            '<h2>Service <em>procedure</em></h2>Remove the cover.'
            '<h3>Before you begin</h3><h4>Inspection</h4>Inspect the seal.'
            '<h5>Fitting<br/>details</h5>'
            '<h6>Press <script>untrusted()</script><a href="/guide">guide</a></h6>'
            '<h4> </h4>Clean the flange.'
        )
        parser.close()
        parser.flush()
        self.assertEqual(parser.blocks, [
            {"kind": "text", "text": "Read first."},
            {"kind": "heading", "level": 1, "text": "Repair & Service"},
            {"kind": "heading", "level": 2, "text": "Service procedure"},
            {"kind": "text", "text": "Remove the cover."},
            {"kind": "heading", "level": 3, "text": "Before you begin"},
            {"kind": "heading", "level": 4, "text": "Inspection"},
            {"kind": "text", "text": "Inspect the seal."},
            {"kind": "heading", "level": 5, "text": "Fitting details"},
            {"kind": "heading", "level": 6, "text": "Press guide"},
            {"kind": "text", "text": "Clean the flange."},
        ])
        self.assertEqual(parser.links, ["/guide"])

    def test_default_and_explicitly_disabled_heading_modes_keep_legacy_blocks(self):
        html = (
            'Intro. <h2>Service <em>procedure</em></h2>Remove the cover.'
            '<h3>Before you begin</h3><p>Read the label.</p><h4>Refit</h4>Inspect the seal.'
        )
        for options in ({}, {"keep_html_headings": False}):
            with self.subTest(options=options):
                parser = ArticleParser(preserve_legacy_list_starts=False, **options)
                parser.feed(html)
                parser.close()
                parser.flush()
                self.assertEqual(parser.blocks, [
                    {"kind": "text", "text": "Intro."},
                    {"kind": "text", "text": "Service procedureRemove the cover."},
                    {"kind": "text", "text": "Before you begin"},
                    {"kind": "text", "text": "Read the label."},
                    {"kind": "text", "text": "RefitInspect the seal."},
                ])

    def test_opt_in_keeps_nested_heading_inside_its_list_item(self):
        parser = ArticleParser(keep_html_headings=True, preserve_legacy_list_starts=False)
        parser.feed(
            '<ol start="4"><li><h3>Guide adjustment</h3>Remove the cover.'
            '<p>Inspect the seal.</p><ul><li><h5>Seal details</h5>Clean the flange.</li>'
            '</ul></li><li value="9">Install the cover.</li></ol>'
        )
        parser.close()
        outer, = parser.blocks
        self.assertEqual(outer["start"], 4)
        first, second = outer["items"]
        self.assertEqual(first["text"], "")
        adjustment, remove, inspect, details = first["blocks"]
        self.assertEqual(adjustment, {"kind": "heading", "level": 3, "text": "Guide adjustment"})
        self.assertEqual(remove, {"kind": "text", "text": "Remove the cover."})
        self.assertEqual(inspect, {"kind": "text", "text": "Inspect the seal."})
        self.assertEqual(details, {
            "kind": "unordered_list",
            "items": [{"text": "", "blocks": [
                {"kind": "heading", "level": 5, "text": "Seal details"},
                {"kind": "text", "text": "Clean the flange."},
            ]}],
        })
        self.assertEqual(second, {"number": 9, "text": "Install the cover."})

    def test_opt_in_keeps_heading_images_and_table_cell_text(self):
        parser = ArticleParser(keep_html_headings=True)
        parser.feed(
            '<h2>Seal <img data-resource-ref="guide" alt="Seal marks"> adjustment</h2>'
            '<h3><img data-resource-ref="only-media"></h3>'
            '<table><tr><td><h2>Limit</h2> 8 Nm</td><td>Seal</td></tr></table>'
        )
        parser.close()
        heading, image, table = parser.blocks
        self.assertEqual(heading, {
            "kind": "heading", "level": 2, "text": "Seal adjustment",
            "images": [{"kind": "image", "alt": "Seal marks", "name": "", "asset_resource_ref": "guide"}],
        })
        self.assertEqual(image, {
            "kind": "image", "alt": "", "name": "", "asset_resource_ref": "only-media",
        })
        self.assertEqual(table, {"kind": "table", "rows": [[
            {"blocks": [{"kind": "text", "text": "Limit 8 Nm"}]},
            {"blocks": [{"kind": "text", "text": "Seal"}]},
        ]]})

    def test_bound_pdf_embeds_keep_exact_order_without_markup_or_fallback(self):
        parser = ArticleParser(
            keep_bound_pdf_iframes=True,
            asset_bindings=[
                {"source_url": "/fixture/diagram?a=1&b=2", "resource_ref": "iframe-ref"},
                {"source_url": "/fixture/object", "resource_ref": "object-ref"},
                {"source_url": "/fixture/embed", "resource_ref": "embed-ref"},
            ],
        )
        parser.feed(
            'Before<iframe src="/fixture/diagram?a=1&amp;b=2" title="Private title">'
            '<img src="/fixture/embed"><a href="/hidden">Hidden iframe text</a></iframe>'
            'Between<object data="/fixture/object" type=" Application/PDF ">'
            '<object data="/nested" type="image/svg+xml">Hidden nested object</object>'
            '<a href="/hidden">Hidden object text</a></object>'
            'After object<embed src="/fixture/embed" type="application/pdf">After embed'
        )
        parser.close()
        parser.flush()
        self.assertEqual(parser.blocks, [
            {"kind": "text", "text": "Before"},
            {"kind": "document_embed", "asset_resource_ref": "iframe-ref"},
            {"kind": "text", "text": "Between"},
            {"kind": "document_embed", "asset_resource_ref": "object-ref"},
            {"kind": "text", "text": "After object"},
            {"kind": "document_embed", "asset_resource_ref": "embed-ref"},
            {"kind": "text", "text": "After embed"},
        ])
        self.assertEqual(parser.links, [])

    def test_bound_pdf_embeds_require_exact_binding_and_reject_override(self):
        parser = ArticleParser(
            keep_bound_pdf_iframes=True,
            asset_bindings=[{"source_url": "/bound?q=1", "resource_ref": "legitimate"}],
        )
        parser.feed(
            'Keep <iframe src="/bound?q=2" data-resource-ref="legitimate">Hidden</iframe>'
            '<iframe data-resource-ref="legitimate" /><iframe src="/bound?q=1" srcdoc="Hidden"></iframe>'
            '<object data="/unbound" type="application/pdf" data-resource-ref="legitimate">Hidden</object>'
            '<object data="/bound?q=1" type="text/html"></object>'
            '<embed src="/bound?q=1" type="image/png">'
            '<script><embed src="/bound?q=1" type="application/pdf"></script>this text.'
        )
        parser.close()
        parser.flush()
        self.assertEqual(parser.blocks, [{"kind": "text", "text": "Keep this text."}])

    def test_bound_pdf_embed_stays_in_list_item_and_table_cell(self):
        parser = ArticleParser(
            keep_bound_pdf_iframes=True, preserve_legacy_list_starts=False,
            asset_bindings=[
                {"source_url": "/bound/list", "resource_ref": "list-ref"},
                {"source_url": "/bound/cell", "resource_ref": "cell-ref"},
            ],
        )
        overlap = {"kind": "document_embed", "asset_resource_ref": "list-ref"}
        cell = {"kind": "document_embed", "asset_resource_ref": "cell-ref"}
        parser.feed(
            '<ol start="4"><li>Open cover.<ol start="7"><li>Inspect seal.</li>'
            '<iframe src="/bound/list" /><li>Inspect seat.</li></ol>'
            '<table><tr><td>Wiring<embed src="/bound/cell" type="application/pdf">'
            'route</td></tr></table>Clean flange.</li><li value="9">Install cover.</li></ol>'
        )
        parser.close()
        parser.flush()
        self.assertEqual(parser.blocks, [{
            "kind": "ordered_list", "start": 4, "items": [
                {"text": "Open cover.", "blocks": [
                    {"kind": "ordered_list", "start": 7, "items": ["Inspect seal."]},
                    overlap,
                    {"kind": "ordered_list", "start": 8, "items": ["Inspect seat."]},
                    {"kind": "table", "rows": [[{"blocks": [
                        {"kind": "text", "text": "Wiring"}, cell, {"kind": "text", "text": "route"},
                    ]}]]},
                    {"kind": "text", "text": "Clean flange."},
                ]},
                {"text": "Install cover.", "number": 9},
            ],
        }])

    def test_default_bound_pdf_embed_mode_preserves_previous_parser_output(self):
        parser = ArticleParser(asset_bindings=[{"source_url": "/bound", "resource_ref": "ref"}])
        parser.feed(
            '<p>Keep text.</p><iframe src="/bound"></iframe>'
            '<object data="/bound" type="application/pdf"><p>Legacy fallback.</p></object>'
            '<embed src="/bound" type="application/pdf"><p>Keep tail.</p>'
        )
        parser.close()
        parser.flush()
        self.assertEqual(parser.blocks, [
            {"kind": "text", "text": "Keep text."},
            {"kind": "text", "text": "Legacy fallback."},
            {"kind": "text", "text": "Keep tail."},
        ])

    def test_flat_lists_keep_legacy_shape_and_top_level_figure_order(self):
        parser = ArticleParser()
        parser.feed(
            '<ol><li>Remove pump.</li><li>Check gasket.</li></ol>'
            '<img data-resource-ref="guide"><ol><li>Install pump.</li></ol>'
        )
        parser.close()
        parser.flush()
        first, image, second = parser.blocks
        self.assertEqual(first, {"kind": "ordered_list", "items": ["Remove pump.", "Check gasket."], "start": 1})
        self.assertEqual(image["asset_resource_ref"], "guide")
        self.assertEqual(second, {"kind": "ordered_list", "items": ["Install pump."], "start": 3})

    def test_nested_lists_accept_omitted_item_end_tags_and_keep_parent_tail(self):
        parser = ArticleParser()
        parser.feed("<ol><li>Inspect the pump.<ul><li>Inspect the seal.</ul>Check the fitting.<li>Replace the pump.</ol>")
        parser.close()
        parser.flush()
        first, second = parser.blocks[0]["items"]
        self.assertEqual(first["text"], "Inspect the pump.")
        self.assertEqual(first["blocks"], [
            {"kind": "unordered_list", "items": ["Inspect the seal."]},
            {"kind": "text", "text": "Check the fitting."},
        ])
        self.assertEqual(second, "Replace the pump.")

    def test_inline_figure_between_nested_items_stays_with_the_parent_item(self):
        parser = ArticleParser()
        parser.feed(
            '<ol><li>Open cover.<ol><li>Inspect seal.</li><img data-resource-ref="alignment">'
            '<li>Inspect seat.</li></ol> Clean flange.</li><li>Install cover.</li></ol>'
        )
        parser.close()
        parser.flush()
        outer, = parser.blocks
        first, second = outer["items"]
        self.assertEqual(first["text"], "Open cover.")
        before, figure, after, tail = first["blocks"]
        self.assertEqual(before, {"kind": "ordered_list", "items": ["Inspect seal."], "start": 1})
        self.assertEqual(figure["asset_resource_ref"], "alignment")
        self.assertEqual(after, {"kind": "ordered_list", "items": ["Inspect seat."], "start": 2})
        self.assertEqual(tail, {"kind": "text", "text": "Clean flange."})
        self.assertEqual(second, "Install cover.")

    def test_authored_nested_numbers_and_figure_continuation_are_independent(self):
        parser = ArticleParser()
        parser.feed(
            '<ol start="000000000004"><li>Open cover.<ol start="-3"><li>Inspect seal.</li>'
            '<li value="+0">Inspect seat.</li><img data-resource-ref="guide">'
            '<li>Clean flange.</li></ol></li><li value="9">Check cable.</li>'
            '<li>Install cover.</li></ol>'
        )
        parser.close()
        outer, = parser.blocks
        first, override, last = outer["items"]
        self.assertEqual(outer["start"], 4)
        self.assertEqual(override, {"text": "Check cable.", "number": 9})
        self.assertEqual(last, "Install cover.")
        before, guide, after = first["blocks"]
        self.assertEqual(before["start"], -3)
        self.assertEqual(before["items"], ["Inspect seal.", {"text": "Inspect seat.", "number": 0}])
        self.assertEqual(guide["asset_resource_ref"], "guide")
        self.assertEqual(after["start"], 1)
        self.assertEqual(after["items"], ["Clean flange."])

    def test_bound_html_keeps_fresh_ordered_lists_independent_after_numbered_lists(self):
        parser = ArticleParser(preserve_legacy_list_starts=False)
        parser.feed('<ol start="4"><li>Open cover.</li></ol><ol><li>Inspect seal.</li></ol>')
        parser.close()
        first, second = parser.blocks
        self.assertEqual(first["start"], 4)
        self.assertEqual(second, {"kind": "ordered_list", "items": ["Inspect seal."]})

    def test_invalid_html_numbering_is_ignored_and_unordered_values_are_ignored(self):
        parser = ArticleParser()
        parser.feed(
            '<ol start="2147483648"><li value="-2147483649">Open cover.</li>'
            '<li value="2.5">Check cable.</li><li value="xyz">Install cover.</li></ol>'
            '<p>Other procedure.</p><ul start="8"><li value="4">Note the seal.</li></ul>'
        )
        parser.close()
        ordered, _, unordered = parser.blocks
        self.assertEqual(ordered, {"kind": "ordered_list", "start": 1,
                                  "items": ["Open cover.", "Check cable.", "Install cover."]})
        self.assertEqual(unordered, {"kind": "unordered_list", "items": ["Note the seal."]})

    def test_legacy_facade_projects_structured_list_text_and_localizes_nested_image(self):
        html = (
            '<ol><li>Remove pump.<img src="/bound" alt="Alignment marks">'
            '<ul><li>Check gasket.</li></ul> Wipe flange.</li><li>Install pump.</li></ol>'
        )

        def opener(request, timeout):
            body = envelope(
                kind="article", media_type="text/html", content=html,
                sha256=sha256(html.encode()).hexdigest(), asset_resource_refs=["figure"],
                asset_bindings=[{"source_url": "/bound", "resource_ref": "figure"}],
            )
            return FixtureResponse(json.dumps(body).encode(), url=request.full_url,
                                   headers={"Content-Type": "application/json"})

        client = SourceConnectorClient("https://banktwo.cars.tk", provider="banktwo", opener=opener)
        article = BanktwoConnector(source_client=client).article_by_descriptor(
            "vehicle", {"opaque_ref": "article", "resource_ref": "body"},
        )
        self.assertEqual(article["body"].splitlines()[::2], [
            "Remove pump.", "Check gasket.", "Wipe flange.", "Install pump.",
        ])
        image, = article["images"]
        self.assertEqual(image["asset_resource_ref"], "figure")
        self.assertNotIn("url", image)

    def test_unbound_images_do_not_consume_refs_by_ordinal(self):
        html = '<p>Remove pump.</p><img src="/unknown"><img src="/bound"><img src="/bound">'

        def opener(request, timeout):
            body = envelope(kind="article", media_type="text/html", content=html,
                sha256=sha256(html.encode()).hexdigest(), asset_resource_refs=["figure"],
                asset_bindings=[{"source_url": "/bound", "resource_ref": "figure"}])
            return FixtureResponse(json.dumps(body).encode(), url=request.full_url,
                                   headers={"Content-Type": "application/json"})

        client = SourceConnectorClient("https://banktwo.cars.tk", provider="banktwo", opener=opener)
        article = BanktwoConnector(source_client=client).article_by_descriptor(
            "vehicle", {"opaque_ref": "article", "resource_ref": "body"})
        images = [b for b in article["blocks"] if b.get("kind") == "image"]
        self.assertEqual(images[0]["status"], "unavailable")
        self.assertNotIn("asset_resource_ref", images[0])
        self.assertEqual([i["asset_resource_ref"] for i in images[1:]], ["figure", "figure"])

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
                    asset_bindings=[{"source_url": "https://upstream.invalid/fig/pump.png", "resource_ref": "asset-opaque-1"}],
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
