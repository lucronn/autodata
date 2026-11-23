from dataclasses import replace
from hashlib import sha256
import json

import pytest

from autodata_ingestion.article_lifecycle_types import BANKONE_GRAPHIC_POSITION_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


GRAPHIC_LOCATOR = "bankone:asset:" + sha256(b'{"kind":"graphic","id":"71"}').hexdigest()[:24]
ASSET = "provider-graphic"
HTML = (
    '<ol><li>Inspect the cover.</li><li>Remove the shield.</li>'
    '<mtr-image id="71" alt="Upper fasteners"></mtr-image><li>Clean the threads.</li></ol>'
    '<ol><mtr-image id="71" alt="Lower fasteners"></mtr-image><li>Fit the shield.</li>'
    '<p>Keep the seal in place.</p><li>Install the cover.</li></ol>'
    '<template><mtr-image id="71"></mtr-image></template>'
    '<mtr-image id="71" id="72"></mtr-image>'
)


class GraphicReceipts:
    provider = "bankone"

    def __init__(self, connector, locator=GRAPHIC_LOCATOR):
        self.connector = connector
        self.locator = locator

    def read_resource(self, ref, **options):
        response = self.connector.read_resource(ref, **options)
        return replace(response, source_locator=self.locator) if ref == ASSET else response


@pytest.mark.parametrize("media_type", ["text/html", "application/hal+json"])
def test_same_graphic_is_fetched_once_and_keeps_both_authored_positions(capture_fixture, media_type):
    payload = HTML.encode() if media_type == "text/html" else json.dumps({
        "_embedded": {"data": {"article": {"content": HTML}}},
    }).encode()
    capture_fixture.body("bankone", payload, media_type, assets=[ASSET])
    capture_fixture.body("bankone", b"fixture-authorized-png", "image/png", ref=ASSET, kind="asset")
    context = capture_fixture.context("bankone")
    options = {
        "registry": {"bankone": GraphicReceipts(capture_fixture.registry["bankone"])},
        "object_store": capture_fixture.objects,
    }
    previews = []
    captured = capture_source_article(
        context, keep_bankone_graphic_positions=True,
        on_body_preview=lambda _, document: previews.append(document), **options,
    )
    assert capture_fixture.resource_calls("bankone", ASSET) == 1
    result = captured.source_document["blocks"]
    assert [block["type"] for block in result] == [
        "ordered_list", "image", "ordered_list", "image", "ordered_list", "paragraph", "ordered_list",
    ]
    assert [block.get("start", 1) for block in result if block["type"] == "ordered_list"] == [1, 3, 1, 2]
    assert result[5]["text"] == "Keep the seal in place."
    assert [block["alt"] for block in result if block["type"] == "image"] == ["Upper fasteners", "Lower fasteners"]
    images = [block for block in result if block["type"] == "image"]
    assert images[0]["block_id"] != images[1]["block_id"]
    assert images[0]["storage_key"] == images[1]["storage_key"]
    assert [item["content_sha256"] for item in captured.source_images] == [sha256(b"fixture-authorized-png").hexdigest()] * 2
    assert [block["unavailable_reason"] for block in previews[0]["blocks"] if block["type"] == "image"] == [
        "SOURCE_MEDIA_PENDING", "SOURCE_MEDIA_PENDING",
    ]
    body = captured.resource_manifest[0]
    assert body["bankone_graphic_position_layout"] == BANKONE_GRAPHIC_POSITION_LAYOUT
    assert body["bankone_graphic_position_bindings"] == {GRAPHIC_LOCATOR: ASSET}
    assert GRAPHIC_LOCATOR not in json.dumps(captured.source_document)
    assert normalize_procedure_article(
        {"normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps},
        resource_manifest=captured.resource_manifest,
    )["normalized_document"] == captured.source_document

    legacy = replace(context, legacy_published_bankone_graphic_body=body["sha256"])
    original = capture_source_article(context, **options)
    refreshed = capture_source_article(legacy, keep_bankone_graphic_positions=True, **options)
    assert refreshed.source_document == original.source_document
    assert refreshed.source_fingerprint == original.source_fingerprint != captured.source_fingerprint


@pytest.mark.parametrize("declared", [True, False])
def test_authored_positions_require_matching_receipt_for_a_body_declared_asset(capture_fixture, declared):
    capture_fixture.body("bankone", HTML.encode(), assets=[ASSET] if declared else [])
    capture_fixture.body("bankone", b"unplaced-image", "image/png", ref=ASSET, kind="asset")
    connector = GraphicReceipts(capture_fixture.registry["bankone"], "bankone:asset:other" if declared else GRAPHIC_LOCATOR)
    captured = capture_source_article(
        capture_fixture.context("bankone", asset_ref=ASSET),
        registry={"bankone":connector}, object_store=capture_fixture.objects,
        keep_bankone_graphic_positions=True,
    )
    positions = [block for block in captured.source_document["blocks"] if block["type"] == "image"]
    assert [image["status"] for image in positions] == ["unavailable", "unavailable", "available"]
    assert captured.resource_manifest[0]["bankone_graphic_position_bindings"] == {}
