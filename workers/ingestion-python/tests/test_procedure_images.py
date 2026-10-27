from __future__ import annotations

import io
import sys
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion import procedure_images
from autodata_ingestion.source_connector_client import SourceConnectorClient


class BinaryResponse(io.BytesIO):
    status = 200

    def __init__(self, payload, *, url, headers):
        super().__init__(payload)
        self.url = url
        self.headers = headers

    def geturl(self):
        return self.url


def test_localization_reads_opaque_asset_ref_and_keeps_verified_provenance(monkeypatch):
    payload = b"\x89PNG\r\n\x1a\nverified-image"
    requests = []

    def opener(request, timeout):
        requests.append(request.full_url)
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Request-Id": str(uuid4()),
            "X-Provider": "banktwo",
            "X-Source-Revision": "asset-revision-8",
            "X-Fetched-At": "2026-10-08T12:00:00Z",
            "X-Source-Locator": "https://banktwo.cars.tk/source/assets/figure",
            "X-Source-Sha256": sha256(payload).hexdigest(),
            "X-Source-Media-Type": "image/png",
        }
        return BinaryResponse(payload, url=request.full_url, headers=headers)

    client = SourceConnectorClient("https://banktwo.cars.tk", provider="banktwo", opener=opener)
    monkeypatch.setattr(
        "autodata_ingestion.source_connector_client.source_connector_registry",
        lambda **_kwargs: {"banktwo": client},
    )
    stored = []
    monkeypatch.setattr(procedure_images, "_put_object", lambda key, data, media: stored.append((key, data, media)))

    result = procedure_images.localize_procedure_images({
        "images": [{"image_id": "stable-figure-id", "asset_resource_ref": "opaque-asset-1", "alt": "Pump"}],
        "normalized_document": {"blocks": [{"type": "image", "image_id": "stable-figure-id"}]},
    })

    image = result["images"][0]
    digest = sha256(payload).hexdigest()
    assert requests == ["https://banktwo.cars.tk/v1/resources/opaque-asset-1"]
    assert stored == [(f"procedure-images/{digest}", payload, "image/png")]
    assert image["content_sha256"] == digest
    assert image["source_sha256"] == digest
    assert image["source_asset_ref"] == "opaque-asset-1"
    assert image["source_revision"] == "asset-revision-8"
    assert image["storage_key"] == f"procedure-images/{digest}"
    assert image["url"] == "artifact://stable-figure-id"
    assert result["normalized_document"]["blocks"][0]["status"] == "available"
    assert "https://upstream.invalid" not in str(result["images"])


def test_invalid_binary_hash_never_reaches_object_storage(monkeypatch):
    payload = b"image-bytes"

    def opener(request, timeout):
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Request-Id": str(uuid4()),
            "X-Provider": "banktwo",
            "X-Source-Revision": "asset-revision-bad",
            "X-Fetched-At": "2026-10-08T12:00:00Z",
            "X-Source-Locator": "https://banktwo.cars.tk/source/assets/figure",
            "X-Source-Sha256": "0" * 64,
            "X-Source-Media-Type": "image/png",
        }
        return BinaryResponse(payload, url=request.full_url, headers=headers)

    client = SourceConnectorClient("https://banktwo.cars.tk", provider="banktwo", opener=opener)
    monkeypatch.setattr(
        "autodata_ingestion.source_connector_client.source_connector_registry",
        lambda **_kwargs: {"banktwo": client},
    )
    writes = []
    monkeypatch.setattr(procedure_images, "_put_object", lambda *args: writes.append(args))

    result = procedure_images.localize_procedure_images({
        "images": [{"image_id": "bad-figure", "asset_resource_ref": "opaque-bad-asset"}],
    })

    assert writes == []
    assert result["images"][0]["fetch_failed"] is True
    assert "url" not in result["images"][0]


def test_localize_data_uri_image_persists_payload_and_rewrites_url(monkeypatch):
    import base64

    payload = b"\x89PNG\r\n\x1a\ninline-data-uri-content"
    encoded = base64.b64encode(payload).decode("ascii")
    data_uri = f"data:image/png;base64,{encoded}"
    digest = sha256(payload).hexdigest()

    stored = []
    monkeypatch.setattr(procedure_images, "_put_object", lambda key, data, media: stored.append((key, data, media)))

    result = procedure_images.localize_procedure_images({
        "images": [
            {
                "image_id": "inline-figure-1",
                "url": data_uri,
                "alt": "Diagnostic schematic",
            }
        ],
        "normalized_document": {
            "blocks": [{"type": "image", "image_id": "inline-figure-1"}]
        },
    })

    assert stored == [(f"procedure-images/{digest}", payload, "image/png")]
    image = result["images"][0]
    assert image["image_id"] == "inline-figure-1"
    assert image["storage_key"] == f"procedure-images/{digest}"
    assert image["content_sha256"] == digest
    assert image["media_type"] == "image/png"
    assert image["url"] == "artifact://inline-figure-1"
    assert "fetch_failed" not in image
    assert result["normalized_document"]["blocks"][0]["status"] == "available"


def test_localize_data_uri_image_handles_malformed_uris(monkeypatch):
    stored = []
    monkeypatch.setattr(procedure_images, "_put_object", lambda key, data, media: stored.append((key, data, media)))

    # Not base64
    result = procedure_images.localize_procedure_images({
        "images": [{"image_id": "malformed-1", "url": "data:image/png;charset=utf-8,rawtext"}],
    })
    assert stored == []
    assert result["images"][0]["fetch_failed"] is True

    # Missing comma
    result2 = procedure_images.localize_procedure_images({
        "images": [{"image_id": "malformed-2", "url": "data:image/png;base64"}],
    })
    assert result2["images"][0]["fetch_failed"] is True


def test_rewrite_document_images_handles_table_cells():
    result = procedure_images.localize_procedure_images({
        "images": [
            {
                "image_id": "cell-img-1",
                "storage_key": "procedure-images/abcd1234",
                "alt": "Diagram 1",
            }
        ],
        "normalized_document": {
            "blocks": [
                {
                    "type": "table",
                    "rows": [
                        [
                            {
                                "text": "Step 1 diagram",
                                "images": [{"image_id": "cell-img-1", "status": "unavailable"}],
                            }
                        ]
                    ],
                }
            ]
        },
    })
    cell_img = result["normalized_document"]["blocks"][0]["rows"][0][0]["images"][0]
    assert cell_img["status"] == "available"
    assert cell_img["asset_id"] == "procedure-images/abcd1234"
    assert cell_img["image_id"] == "cell-img-1"


def test_hydrate_article_image_urls_hydrates_normalized_document(monkeypatch):
    monkeypatch.setattr(procedure_images, "_read_storage_bytes", lambda key: b"\x89PNG\r\n\x1a\nfake-bytes")

    article = {
        "article_id": "art-doc-hydrate",
        "images": [
            {
                "image_id": "img-main",
                "storage_key": "procedure-images/1111",
                "media_type": "image/png",
            }
        ],
        "normalized_document": {
            "blocks": [
                {
                    "type": "image",
                    "image_id": "img-main",
                    "storage_key": "procedure-images/1111",
                    "media_type": "image/png",
                },
                {
                    "type": "table",
                    "rows": [
                        [
                            {
                                "text": "Cell diagram",
                                "images": [
                                    {
                                        "image_id": "img-cell",
                                        "storage_key": "procedure-images/2222",
                                        "media_type": "image/png",
                                    }
                                ],
                            }
                        ]
                    ],
                },
            ]
        },
    }

    # 1. Default artifact:// hydration
    hydrated_default = procedure_images.hydrate_article_image_urls(article)
    assert hydrated_default["images"][0]["url"] == "artifact://img-main"
    assert hydrated_default["normalized_document"]["blocks"][0]["url"] == "artifact://img-main"
    assert hydrated_default["normalized_document"]["blocks"][1]["rows"][0][0]["images"][0]["url"] == "artifact://img-cell"

    # 2. Embedded data-URI hydration for offline PDF/HTML
    hydrated_embed = procedure_images.hydrate_article_image_urls(article, embed_data_uri=True)
    assert hydrated_embed["images"][0]["url"].startswith("data:image/png;base64,")
    assert hydrated_embed["normalized_document"]["blocks"][0]["url"].startswith("data:image/png;base64,")
    assert hydrated_embed["normalized_document"]["blocks"][1]["rows"][0][0]["images"][0]["url"].startswith("data:image/png;base64,")


def test_collect_image_records_includes_document_and_table_cells():
    article = {
        "images": [{"image_id": "top-img"}],
        "steps": [{"images": [{"image_id": "step-img"}]}],
        "normalized_document": {
            "blocks": [
                {"type": "image", "image_id": "doc-img"},
                {
                    "type": "table",
                    "rows": [
                        [
                            {
                                "images": [{"image_id": "cell-img"}],
                                "blocks": [{"type": "image", "image_id": "nested-cell-img"}],
                            }
                        ]
                    ],
                },
            ]
        },
    }
    records = procedure_images._collect_image_records(article)
    image_ids = [r.get("image_id") for r in records]
    assert "top-img" in image_ids
    assert "step-img" in image_ids
    assert "doc-img" in image_ids
    assert "cell-img" in image_ids
    assert "nested-cell-img" in image_ids


def test_localization_localizes_document_only_article_with_opaque_asset_ref(monkeypatch):
    payload = b"\x89PNG\r\n\x1a\ndoc-only-image"
    digest = sha256(payload).hexdigest()

    def opener(request, timeout):
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Request-Id": str(uuid4()),
            "X-Provider": "banktwo",
            "X-Source-Revision": "doc-rev-1",
            "X-Fetched-At": "2026-10-08T12:00:00Z",
            "X-Source-Locator": "https://banktwo.cars.tk/source/assets/doc-figure",
            "X-Source-Sha256": digest,
            "X-Source-Media-Type": "image/png",
        }
        return BinaryResponse(payload, url=request.full_url, headers=headers)

    client = SourceConnectorClient("https://banktwo.cars.tk", provider="banktwo", opener=opener)
    monkeypatch.setattr(
        "autodata_ingestion.source_connector_client.source_connector_registry",
        lambda **_kwargs: {"banktwo": client},
    )
    stored = []
    monkeypatch.setattr(procedure_images, "_put_object", lambda key, data, media: stored.append((key, data, media)))

    article = {
        "article_id": "doc-only-article",
        "normalized_document": {
            "blocks": [
                {
                    "type": "image",
                    "image_id": "doc-figure-1",
                    "asset_resource_ref": "opaque-doc-asset",
                    "alt": "Diagram in doc",
                }
            ]
        },
    }
    result = procedure_images.localize_procedure_images(article)
    assert stored == [(f"procedure-images/{digest}", payload, "image/png")]
    block = result["normalized_document"]["blocks"][0]
    assert block["status"] == "available"
    assert block["storage_key"] == f"procedure-images/{digest}"
    assert block["url"] == "artifact://doc-figure-1"


def test_localization_localizes_document_and_cell_data_uris(monkeypatch):
    import base64

    payload1 = b"\x89PNG\r\n\x1a\ndoc-data-uri"
    payload2 = b"\x89PNG\r\n\x1a\ncell-data-uri"
    digest1 = sha256(payload1).hexdigest()
    digest2 = sha256(payload2).hexdigest()
    data_uri1 = f"data:image/png;base64,{base64.b64encode(payload1).decode('ascii')}"
    data_uri2 = f"data:image/png;base64,{base64.b64encode(payload2).decode('ascii')}"

    stored = []
    monkeypatch.setattr(procedure_images, "_put_object", lambda key, data, media: stored.append((key, data, media)))

    article = {
        "normalized_document": {
            "blocks": [
                {
                    "type": "image",
                    "image_id": "uri-doc-1",
                    "url": data_uri1,
                },
                {
                    "type": "table",
                    "rows": [
                        [
                            {
                                "images": [
                                    {
                                        "image_id": "uri-cell-1",
                                        "url": data_uri2,
                                    }
                                ]
                            }
                        ]
                    ],
                },
            ]
        }
    }
    result = procedure_images.localize_procedure_images(article)
    assert (f"procedure-images/{digest1}", payload1, "image/png") in stored
    assert (f"procedure-images/{digest2}", payload2, "image/png") in stored

    doc_block = result["normalized_document"]["blocks"][0]
    cell_img = result["normalized_document"]["blocks"][1]["rows"][0][0]["images"][0]
    assert doc_block["status"] == "available"
    assert doc_block["storage_key"] == f"procedure-images/{digest1}"
    assert cell_img["status"] == "available"
    assert cell_img["storage_key"] == f"procedure-images/{digest2}"


def test_read_asset_resource_routes_connector_prefixes(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    bankone_mock = MagicMock()
    bankone_envelope = MagicMock()
    bankone_envelope.to_source_resource.return_value = SimpleNamespace(
        locator="bankone://img-1",
        source_version="v1",
        media_type="image/jpeg",
        payload=b"bankone-bytes",
        metadata={"kind": "asset"},
    )
    bankone_mock.read_resource.return_value = bankone_envelope

    banktwo_mock = MagicMock()
    banktwo_envelope = MagicMock()
    banktwo_envelope.to_source_resource.return_value = SimpleNamespace(
        locator="banktwo://img-2",
        source_version="v2",
        media_type="image/png",
        payload=b"banktwo-bytes",
        metadata={"kind": "asset"},
    )
    banktwo_mock.read_resource.return_value = banktwo_envelope

    monkeypatch.setattr(
        "autodata_ingestion.source_connector_client.source_connector_registry",
        lambda **_kwargs: {"bankone": bankone_mock, "banktwo": banktwo_mock},
    )

    res1 = procedure_images._read_asset_resource("bankone:asset/1001")
    assert res1["payload"] == b"bankone-bytes"
    assert res1["media_type"] == "image/jpeg"
    bankone_mock.read_resource.assert_called_once_with("bankone:asset/1001")

    res2 = procedure_images._read_asset_resource("banktwo:asset/2002")
    assert res2["payload"] == b"banktwo-bytes"
    assert res2["media_type"] == "image/png"
    banktwo_mock.read_resource.assert_called_once_with("banktwo:asset/2002")

    monkeypatch.setattr(
        "autodata_ingestion.source_connector_client.source_connector_registry",
        lambda **_kwargs: {"banktwo": banktwo_mock},
    )
    with pytest.raises(ValueError, match="unknown or unconfigured source connector 'bankone'"):
        procedure_images._read_asset_resource("bankone:asset/3003")

    monkeypatch.setattr(
        "autodata_ingestion.source_connector_client.source_connector_registry",
        lambda **_kwargs: {},
    )
    with pytest.raises(ValueError, match="unknown or unconfigured source connector 'banktwo'"):
        procedure_images._read_asset_resource("opaque-asset-ref")


def test_collect_and_rewrite_arbitrary_block_images():
    article = {
        "article_id": "art-block-images",
        "normalized_document": {
            "blocks": [
                {
                    "type": "callout",
                    "label": "WARNING",
                    "text": "Check belt alignment",
                    "images": [
                        {
                            "image_id": "callout-img",
                            "storage_key": "procedure-images/callout123",
                        }
                    ],
                },
                {
                    "type": "section",
                    "blocks": [
                        {
                            "type": "step",
                            "text": "Inspect tensioner",
                            "images": [
                                {
                                    "image_id": "step-img",
                                    "storage_key": "procedure-images/step456",
                                }
                            ],
                        }
                    ],
                },
            ]
        },
    }

    collected = procedure_images._collect_image_records(article)
    collected_ids = [img.get("image_id") for img in collected]
    assert "callout-img" in collected_ids
    assert "step-img" in collected_ids

    localized = procedure_images.localize_procedure_images(article)
    callout_img = localized["normalized_document"]["blocks"][0]["images"][0]
    assert callout_img["status"] == "available"
    assert callout_img["url"] == "artifact://callout-img"
    assert callout_img["storage_key"] == "procedure-images/callout123"

    step_img = localized["normalized_document"]["blocks"][1]["blocks"][0]["images"][0]
    assert step_img["status"] == "available"
    assert step_img["url"] == "artifact://step-img"
    assert step_img["storage_key"] == "procedure-images/step456"


def test_hydrate_article_image_urls_hydrates_arbitrary_blocks_and_children(monkeypatch):
    monkeypatch.setattr(procedure_images, "_read_storage_bytes", lambda key: b"\x89PNG\r\n\x1a\nfake-block-bytes")

    article = {
        "article_id": "art-block-hydrate",
        "normalized_document": {
            "blocks": [
                {
                    "type": "callout",
                    "label": "CAUTION",
                    "text": "Hot exhaust component",
                    "images": [
                        {
                            "image_id": "callout-fig-1",
                            "storage_key": "procedure-images/caution-fig",
                            "media_type": "image/png",
                        }
                    ],
                },
                {
                    "type": "section",
                    "children": [
                        {
                            "type": "step",
                            "text": "Loosen bracket",
                            "images": [
                                {
                                    "image_id": "step-fig-1",
                                    "storage_key": "procedure-images/step-fig",
                                    "media_type": "image/png",
                                }
                            ],
                        }
                    ],
                },
            ]
        },
    }

    # 1. Default artifact:// hydration
    hydrated_default = procedure_images.hydrate_article_image_urls(article)
    callout_img = hydrated_default["normalized_document"]["blocks"][0]["images"][0]
    assert callout_img["url"] == "artifact://callout-fig-1"
    step_img = hydrated_default["normalized_document"]["blocks"][1]["children"][0]["images"][0]
    assert step_img["url"] == "artifact://step-fig-1"

    # 2. Embedded data-URI hydration
    hydrated_embed = procedure_images.hydrate_article_image_urls(article, embed_data_uri=True)
    callout_embed = hydrated_embed["normalized_document"]["blocks"][0]["images"][0]
    assert callout_embed["url"].startswith("data:image/png;base64,")
    step_embed = hydrated_embed["normalized_document"]["blocks"][1]["children"][0]["images"][0]
    assert step_embed["url"].startswith("data:image/png;base64,")
