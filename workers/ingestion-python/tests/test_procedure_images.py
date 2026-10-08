import io
from hashlib import sha256
from uuid import uuid4

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
