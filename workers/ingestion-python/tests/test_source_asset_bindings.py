"""Exact source URL bindings survive the connector and ordered capture boundaries."""
from hashlib import sha256
import json
from uuid import uuid4

import pytest

from autodata_ingestion.article_lifecycle_types import ArticleKey, SourceArticleContext
from autodata_ingestion.source_article_capture import capture_source_article
from autodata_ingestion.source_connector_client import SourceConnectorClient, SourceConnectorError


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, body, url):
        self.raw = json.dumps(body).encode()
        self.url = url

    def geturl(self):
        return self.url

    def read(self, limit=-1):
        value, self.raw = self.raw[:limit], self.raw[limit:]
        return value

    read1 = read

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def client_for(body, provider="bankone"):
    envelope = dict(request_id=str(uuid4()), provider=provider, source_revision="revision-1",
                    fetched_at="2026-11-05T12:00:00Z", **body)
    return SourceConnectorClient(f"https://{provider}.test", provider=provider,
                                 opener=lambda request, timeout: Response(envelope, request.full_url))


def text_body(bindings):
    raw = '<p>Remove pump.</p><img src="/figure?a=1&amp;b=2">'
    return dict(kind="article", media_type="text/html", content=raw,
                sha256=sha256(raw.encode()).hexdigest(), asset_resource_refs=["asset-1"],
                asset_bindings=bindings)


@pytest.mark.parametrize("kind", ["article", "text", "labor"])
def test_valid_binding_retained_as_metadata_without_changing_bytes_or_hash(kind):
    bindings = [{"source_url": "/figure?a=1&b=2", "resource_ref": "asset-1"}]
    body = {**text_body(bindings), "kind": kind}
    resource = client_for(body).read_resource("body").to_source_resource()
    assert resource.payload == body["content"].encode()
    assert resource.content_sha256 == body["sha256"]
    assert resource.metadata["asset_bindings"] == bindings


@pytest.mark.parametrize("bindings", [
    None, {}, "binding", [None], [{}],
    [{"source_url": "/a"}],
    [{"source_url": "/a", "resource_ref": "asset-1", "extra": True}],
    [{"source_url": 1, "resource_ref": "asset-1"}],
    [{"source_url": "", "resource_ref": "asset-1"}],
    [{"source_url": "/a", "resource_ref": "unknown"}],
    [{"source_url": "/a\n", "resource_ref": "asset-1"}],
    [{"source_url": "/a", "resource_ref": "asset-1\x00"}],
    [{"source_url": "/a", "resource_ref": 1}],
    [{"source_url": "a" * 2049, "resource_ref": "asset-1"}],
    [{"source_url": "/a", "resource_ref": "a" * 2049}],
    [{"source_url": "/a", "resource_ref": "asset-1"}] * 2,
    [{"source_url": f"/{i}", "resource_ref": "asset-1"} for i in range(129)],
])
def test_malformed_sidecar_fails_closed(bindings):
    with pytest.raises(SourceConnectorError, match="invalid_upstream_response"):
        client_for(text_body(bindings)).read_resource("body")


def test_binding_limits_and_empty_sidecar_are_accepted():
    for bindings in ([], [{"source_url": "a" * 2048, "resource_ref": "asset-1"}],
                     [{"source_url": f"/{i}", "resource_ref": "asset-1"} for i in range(128)]):
        assert client_for(text_body(bindings)).read_resource("body").raw_resource


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_exact_repeated_positions_no_detached_duplicate_and_raw_provenance(provider):
    raw = (b'<p>Remove pump.</p><img src="/figure?a=1&amp;b=2">'
           b'<table><tr><td>Inspect seal.<img src="/figure?a=1&amp;b=2"></td></tr></table>'
           b'<p>Install pump.</p><img src="/figure?a=1&amp;b=3">')
    bindings = [{"source_url": "/figure?a=1&b=2", "resource_ref": "asset-1"}]
    body = {**text_body(bindings), "content": raw.decode(), "sha256": sha256(raw).hexdigest()}
    body_client = client_for(body, provider)
    import base64
    asset = b"image-bytes"
    asset_client = client_for(dict(kind="asset", media_type="image/png",
                                  content_base64=base64.b64encode(asset).decode(), sha256=sha256(asset).hexdigest()), provider)
    calls = []

    class Client:
        def read_resource(self, ref, *, timeout):
            calls.append(ref)
            return (body_client if ref == "body" else asset_client).read_resource(ref, timeout=timeout)

    client = Client()
    client.provider = provider
    objects = {}

    class Store:
        def put_object(self, key, payload, media):
            objects[key] = (payload, media)

    context = SourceArticleContext(ArticleKey(provider, uuid4(), None, "vehicle", "article"),
        {"year": 2024}, {"title": "Pump", "resource_ref": "body"}, uuid4(), uuid4(), ("evidence",))
    captured = capture_source_article(context, registry={provider: client}, object_store=Store())
    assert [b["type"] for b in captured.source_document["blocks"]] == ["paragraph", "image", "table", "paragraph", "image"]
    assert [i["status"] for i in captured.source_images] == ["available", "available", "unavailable"]
    assert captured.source_images[0]["storage_key"] == captured.source_images[1]["storage_key"]
    assert captured.source_images[2]["unavailable_reason"] == "UNBOUND_SOURCE_IMAGE"
    assert calls == ["body", "asset-1"]
    assert objects[captured.resources[0]["object_key"]][0] == raw
    assert captured.resources[0]["sha256"] == sha256(raw).hexdigest()
    assert captured.resource_provenance[0]["source_revision"] == "revision-1"
    assert captured.resource_provenance[0]["asset_bindings"] == bindings
    assert captured.projection_status == "partial"
    assert "/figure" not in str(captured.source_document)
    changed = [{"source_url": "/figure?a=1&b=3", "resource_ref": "asset-1"}]
    body_client = client_for({**body, "asset_bindings": changed}, provider)
    updated = capture_source_article(context, registry={provider: client}, object_store=Store())
    assert updated.source_fingerprint != captured.source_fingerprint
    assert updated.resources[0]["sha256"] == captured.resources[0]["sha256"]
    assert [i["status"] for i in updated.source_images] == ["unavailable", "unavailable", "available"]


def test_parser_matches_decoded_attribute_without_url_normalization():
    from autodata_ingestion.banktwo_connector import ArticleParser
    bindings = [{"source_url": " /a?x=&notit; ", "resource_ref": "figure"}]
    parser = ArticleParser(asset_bindings=bindings)
    parser.feed('<p>Remove pump.</p><img src=" /a?x=&amp;notit; "><img src="/a?x=&amp;notit;">')
    parser.flush()
    images = [b for b in parser.blocks if b["kind"] == "image"]
    assert images[0]["asset_resource_ref"] == "figure"
    assert "asset_resource_ref" not in images[1]


def test_binary_resources_reject_text_sidecar():
    import base64
    raw = b"png-bytes"
    body = dict(kind="asset", media_type="image/png", content_base64=base64.b64encode(raw).decode(),
                sha256=sha256(raw).hexdigest(), asset_bindings=[])
    with pytest.raises(SourceConnectorError):
        client_for(body).read_resource("asset")


@pytest.mark.parametrize("field", ["source_url", "resource_ref"])
def test_sidecar_rejects_c1_controls_even_when_ref_is_declared(field):
    binding = {"source_url": "/figure", "resource_ref": "asset-1"}
    binding[field] += "\x85"
    body = {**text_body([binding]), "asset_resource_refs": [binding["resource_ref"]]}
    with pytest.raises(SourceConnectorError):
        client_for(body).read_resource("body")
