from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts/dev"))
from source_connector_fixture_server import serve_connector
from autodata_ingestion.article_lifecycle_types import ArticleKey, SourceArticleContext
from autodata_ingestion.source_connector_client import (
    SourceConnectorClient,
    SourceConnectorError,
)


class Objects:
    def __init__(self):
        self.data = {}

    def put_object(self, key, payload, media_type):
        self.data[key] = (payload, media_type)


@pytest.fixture
def capture_fixture():
    with ExitStack() as stack:
        servers = {
            p: stack.enter_context(serve_connector(p)) for p in ("bankone", "banktwo")
        }
        registry = {
            p: SourceConnectorClient(s.url, token=s.token, provider=p)
            for p, s in servers.items()
        }

        class Fixture:
            objects = Objects()

            def context(self, provider, article_ref="same/article", asset_ref=None):
                descriptor = {
                    "opaque_ref": article_ref,
                    "title": "Pump",
                    "resource_ref": "body",
                    "asset_resource_refs": [asset_ref] if asset_ref else [],
                }
                return SourceArticleContext(
                    ArticleKey(
                        provider, uuid.uuid4(), None, "vehicle:fixture", article_ref
                    ),
                    {"year": 2024, "make": "Example", "model": "Car"},
                    descriptor,
                    uuid.uuid4(),
                    uuid.uuid4(),
                    ("fixture-evidence",),
                )

            def body(self, provider, payload, media_type="text/html", **kwargs):
                servers[provider].body(payload, media_type, **kwargs)

            def calls(self, provider):
                return servers[provider].calls

            def resource_calls(self, provider, ref):
                from urllib.parse import unquote

                return sum(
                    unquote(c).endswith("/resources/" + ref)
                    for c in self.calls(provider)
                )

        fixture = Fixture()
        fixture.registry = registry
        fixture.servers = servers
        yield fixture


def test_banktwo_plain_html_uses_resolved_descriptor_context(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    context = capture_fixture.context("banktwo")
    capture_fixture.body("banktwo", b"<ol><li>Remove the pump.</li></ol>")
    captured = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects
    )
    assert captured.context.key == context.key
    assert "Remove the pump." in captured.source_body
    assert captured.source_document["blocks"]
    assert capture_fixture.calls("bankone") == []


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_same_asset_ref_never_crosses_provider(capture_fixture, provider):
    from autodata_ingestion.source_article_capture import capture_source_article

    context = capture_fixture.context(provider, asset_ref="opaque:shared/asset")
    capture_fixture.body(
        provider,
        b'<p>Remove pump.</p><img data-resource-ref="opaque:shared/asset" src="https://provider.invalid/a.png">',
        assets=["opaque:shared/asset"],
    )
    capture_fixture.body(
        provider,
        b"image-" + provider.encode(),
        "image/png",
        ref="opaque:shared/asset",
        kind="asset",
    )
    captured = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects
    )
    assert capture_fixture.resource_calls(provider, "opaque:shared/asset") == 1
    assert captured.source_images[0]["status"] == "available"
    assert "https://" not in str(captured.source_document)
    assert (
        capture_fixture.calls("banktwo" if provider == "bankone" else "bankone") == []
    )


@pytest.mark.parametrize(
    "payload,media",
    [
        (b"Pump", "text/plain"),
        (b'{"title":"Pump"}', "application/json"),
        (b"<h1>Pump</h1>", "text/html"),
        (b"", "text/plain"),
    ],
)
def test_title_only_never_becomes_readable(capture_fixture, payload, media):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body("bankone", payload, media)
    with pytest.raises(SourceConnectorError):
        capture_source_article(
            capture_fixture.context("bankone"),
            registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
        )


@pytest.mark.parametrize(
    "payload,media",
    [
        (b"Remove the pump.", "text/plain"),
        (b'{"body":"Remove the pump."}', "application/json"),
    ],
)
def test_scoped_formats_accept_vehicle_free_body(capture_fixture, payload, media):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body("banktwo", payload, media)
    captured = capture_source_article(
        capture_fixture.context("banktwo"),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert "Remove the pump." in captured.source_body
    assert list(capture_fixture.objects.data.values())[0][0] == payload


def test_contradictory_vehicle_rejected(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body(
        "bankone",
        b'{"vehicle":{"year":1999},"body":"Remove pump."}',
        "application/json",
    )
    with pytest.raises(SourceConnectorError, match="applicability"):
        capture_source_article(
            capture_fixture.context("bankone"),
            registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
        )


def test_raw_index_envelope_is_exact(capture_fixture):
    env = capture_fixture.registry["bankone"].list_articles("vehicle:fixture")
    assert env.raw_envelope.startswith(b"{\n ")
    assert b'"complete": true' in env.raw_envelope


def test_optional_asset_failure_preserves_position(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body(
        "bankone",
        b'<p>Remove pump.</p><img data-resource-ref="missing" src="https://provider.invalid/a"><p>Install pump.</p>',
    )
    captured = capture_source_article(
        capture_fixture.context("bankone"),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert captured.projection_status == "partial"
    assert [b["type"] for b in captured.source_document["blocks"]] == [
        "paragraph",
        "image",
        "paragraph",
    ]
    assert captured.source_images[0]["status"] == "unavailable"
    assert captured.resource_manifest[-1]["failure_code"] == "SOURCE_NOT_FOUND"


def test_exact_declared_image_ref_preserves_source_position(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body(
        "bankone", b'<p>Remove pump.</p><img src="same/image"><p>Install pump.</p>'
    )
    capture_fixture.body(
        "bankone", b"fixture-image", "image/png", ref="same/image", kind="asset"
    )
    context = capture_fixture.context("bankone", asset_ref="same/image")
    captured = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects
    )
    assert [b["type"] for b in captured.source_document["blocks"]] == [
        "paragraph",
        "image",
        "paragraph",
    ]
    assert captured.source_document["blocks"][1]["status"] == "available"


def test_fixture_pdf_uses_real_adapter_and_keeps_original_bytes(capture_fixture):
    from io import BytesIO
    from reportlab.pdfgen import canvas
    from autodata_ingestion.source_article_capture import capture_source_article

    buf = BytesIO()
    pdf = canvas.Canvas(buf)
    pdf.drawString(72, 720, "Remove the pump.")
    pdf.showPage()
    pdf.save()
    payload = buf.getvalue()
    capture_fixture.body("banktwo", payload, "application/pdf", kind="binary")
    captured = capture_source_article(
        capture_fixture.context("banktwo"),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert "Remove the pump." in captured.source_body
    assert payload in [value[0] for value in capture_fixture.objects.data.values()]


def test_safe_capture_deadline_cannot_be_extended(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    with pytest.raises(ValueError):
        capture_source_article(
            capture_fixture.context("bankone"),
            registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
            deadline_seconds=31,
        )


def test_unsafe_html_never_enters_source_projection(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body(
        "bankone",
        b'<script>secret_script()</script><p onclick="bad()">Remove pump.</p><a href="javascript:bad()">Read note.</a>',
    )
    captured = capture_source_article(
        capture_fixture.context("bankone"),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert "script" not in str(captured.source_document)
    assert "javascript:" not in str(captured.source_document)
    assert "onclick" not in str(captured.source_document)


def test_json_embedded_html_is_sanitized_without_trusting_source_original(
    capture_fixture,
):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body(
        "bankone",
        b'{"body":"<script>secret_script()</script><p>Remove pump.</p>","source_original":"trusted override"}',
        "application/json",
    )
    captured = capture_source_article(
        capture_fixture.context("bankone"),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert captured.source_body == "Remove pump."
    assert "secret_script" not in str(captured.source_document)
    assert "trusted override" not in str(captured.source_document)


def test_pdf_embedded_figure_is_localized_and_retained(capture_fixture):
    from io import BytesIO
    from PIL import Image
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from autodata_ingestion.source_article_capture import capture_source_article
    import random

    image = Image.frombytes("RGB", (96, 96), random.Random(7).randbytes(96 * 96 * 3))
    figure = BytesIO()
    image.save(figure, format="PNG")
    figure.seek(0)
    buf = BytesIO()
    pdf = canvas.Canvas(buf)
    pdf.drawString(72, 720, "Remove the pump.")
    pdf.drawImage(ImageReader(figure), 72, 500, 96, 96)
    pdf.showPage()
    pdf.save()
    capture_fixture.body("banktwo", buf.getvalue(), "application/pdf", kind="binary")
    captured = capture_source_article(
        capture_fixture.context("banktwo"),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert len(captured.source_images) == 1
    assert captured.source_images[0]["status"] == "available"
    assert captured.source_images[0]["storage_key"] in capture_fixture.objects.data
    assert not any(
        "/resources/" in c and not c.endswith("/body")
        for c in capture_fixture.calls("banktwo")
    )


def test_html_explicit_vehicle_metadata_cannot_override_resolved_scope(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body(
        "banktwo",
        b'<meta name="vehicle" content="1999 Example Car"><p>Remove pump.</p>',
    )
    with pytest.raises(SourceConnectorError, match="applicability"):
        capture_source_article(
            capture_fixture.context("banktwo"),
            registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
        )


def test_optional_asset_deadline_keeps_readable_body(capture_fixture):
    import time
    from autodata_ingestion.source_article_capture import capture_source_article

    context = capture_fixture.context("bankone", asset_ref="slow")
    capture_fixture.body("bankone", b"<p>Remove pump.</p>")
    capture_fixture.body("bankone", b"image", "image/png", ref="slow", kind="asset")
    capture_fixture.servers["bankone"].delays["slow"] = 0.5
    start = time.monotonic()
    captured = capture_source_article(
        context,
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
        deadline_seconds=0.08,
    )
    assert time.monotonic() - start < 0.3
    assert (
        captured.projection_status == "partial"
        and "Remove pump." in captured.source_body
    )


def test_no_more_than_four_parallel_asset_reads(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    context = capture_fixture.context("bankone")
    refs = ["asset/" + str(i) for i in range(9)]
    context = replace(
        context, descriptor={**context.descriptor, "asset_resource_refs": refs}
    )
    capture_fixture.body("bankone", b"<p>Remove pump.</p>")
    for ref in refs:
        capture_fixture.body(
            "bankone", ref.encode(), "image/png", ref=ref, kind="asset"
        )
        capture_fixture.servers["bankone"].delays[ref] = 0.04
    captured = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects
    )
    assert captured.projection_status == "readable"
    assert 2 <= capture_fixture.servers["bankone"].max_active <= 4
    assert all(capture_fixture.resource_calls("bankone", ref) == 1 for ref in refs)


def test_hal_article_content_is_readable_under_bound_scope(capture_fixture):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    payload = {"_embedded": {"data": {"article": {"content": "<p>Remove pump.</p>"}}}}
    capture_fixture.body("bankone", json.dumps(payload).encode(), "application/json")
    captured = capture_source_article(
        capture_fixture.context("bankone"),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert captured.source_body == "Remove pump."


@pytest.mark.parametrize("intro", ["", "<p>Check the pump.</p>"])
def test_table_facts_are_readable_in_source_order(capture_fixture, intro):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body(
        "banktwo",
        (
            intro + "<table><tr><td>Torque</td><td>25 Nm</td></tr>"
            "<tr><td>Tool</td><td>T-123</td></tr></table>"
        ).encode(),
    )
    captured = capture_source_article(
        capture_fixture.context("banktwo"),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert captured.source_body.splitlines() == (
        (["Check the pump."] if intro else []) + ["Torque", "25 Nm", "Tool", "T-123"]
    )
    assert captured.source_document["blocks"][-1]["rows"] == [
        ["Torque", "25 Nm"],
        ["Tool", "T-123"],
    ]


@pytest.mark.parametrize("wrapper", ["article", "hal"])
@pytest.mark.parametrize(
    "identity",
    [
        {"vehicle": {"year": 1999}},
        {"vehicle_id": "00000000-0000-0000-0000-000000000000"},
        {"source_vehicle_ref": "different-vehicle"},
        {"vehicle_configuration_id": "00000000-0000-0000-0000-000000000000"},
    ],
)
def test_nested_article_applicability_must_match_scope(
    capture_fixture, wrapper, identity
):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    payload = {"article": {**identity, "body": "Remove pump."}}
    if wrapper == "hal":
        payload = {"_embedded": {"data": payload}}
    capture_fixture.body("bankone", json.dumps(payload).encode(), "application/json")
    with pytest.raises(SourceConnectorError, match="applicability"):
        capture_source_article(
            capture_fixture.context("bankone"),
            registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
        )


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("localized", [False, True])
def test_nested_kindless_images_require_verified_provider_bytes(
    capture_fixture, provider, localized
):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    image = {
        "asset_resource_ref": "figure",
        "storage_key": "fixture-untrusted/object",
        "artifact_key": "fixture-untrusted/artifact",
        "uri": "https://untrusted.invalid/image",
        "path": "/untrusted/image",
        "object_key": "fixture-untrusted/blob",
        "image_id": "fixture-untrusted/id",
        "content_sha256": "f" * 64,
        "status": "available",
    }
    payload = {
        "blocks": [
            {"kind": "paragraph", "text": "Check pump."},
            {"kind": "table", "rows": [[{"text": "Torque 25 Nm", "images": [image]}]]},
        ]
    }
    capture_fixture.body(provider, json.dumps(payload).encode(), "application/json")
    if localized:
        capture_fixture.body(
            provider, provider.encode(), "image/png", ref="figure", kind="asset"
        )
    captured = capture_source_article(
        capture_fixture.context(provider),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert capture_fixture.resource_calls(provider, "figure") == 1
    assert (
        capture_fixture.calls("banktwo" if provider == "bankone" else "bankone") == []
    )
    assert len(captured.source_images) == 1
    image = captured.source_document["blocks"][1]["rows"][0][0]["images"][0]
    assert image["status"] == ("available" if localized else "unavailable")
    assert image in captured.source_images
    assert "fixture-untrusted" not in str(captured.source_document)
    assert "untrusted.invalid" not in str(captured.source_document)
    assert "/untrusted/" not in str(captured.source_document)
    if localized:
        assert image["storage_key"] in capture_fixture.objects.data
    else:
        assert not image.get("storage_key")
        assert captured.projection_status == "partial"


def test_unbound_image_cannot_keep_upstream_object_locators(capture_fixture):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    payload = {
        "blocks": [
            {"kind": "paragraph", "text": "Check pump."},
            {
                "kind": "image",
                "uri": "https://untrusted.invalid/image",
                "path": "/untrusted/image",
                "storage_key": "fixture-untrusted/object",
                "artifact_key": "fixture-untrusted/artifact",
            },
        ]
    }
    capture_fixture.body("bankone", json.dumps(payload).encode(), "application/json")
    captured = capture_source_article(
        capture_fixture.context("bankone"),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert captured.source_images[0]["status"] == "unavailable"
    assert not captured.source_images[0].get("storage_key")
    assert "untrusted" not in str(captured.source_document)


def test_optional_asset_upload_failure_preserves_readable_source(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    class FailingAssets(Objects):
        def put_object(self, key, payload, media_type):
            if media_type.startswith("image/"):
                raise OSError("private object endpoint unreachable")
            super().put_object(key, payload, media_type)

    capture_fixture.body(
        "bankone", b'<p>Check pump.</p><img data-resource-ref="figure" src="figure">'
    )
    capture_fixture.body("bankone", b"figure", "image/png", ref="figure", kind="asset")
    captured = capture_source_article(
        capture_fixture.context("bankone"),
        registry=capture_fixture.registry,
        object_store=FailingAssets(),
    )
    assert captured.source_body == "Check pump."
    assert captured.projection_status == "partial"
    assert captured.source_images[0]["status"] == "unavailable"
    assert captured.resource_manifest[-1]["failure_code"] == "ASSET_STORAGE_UNAVAILABLE"
    assert "private object endpoint" not in str(captured)


def test_required_body_upload_obeys_capture_deadline(capture_fixture):
    import time
    from autodata_ingestion.source_article_capture import capture_source_article

    class SlowObjects(Objects):
        def put_object(self, *args):
            time.sleep(0.2)
            super().put_object(*args)

    capture_fixture.body("bankone", b"<p>Check pump.</p>")
    started = time.monotonic()
    with pytest.raises(SourceConnectorError, match="capture_deadline"):
        capture_source_article(
            capture_fixture.context("bankone"),
            registry=capture_fixture.registry,
            object_store=SlowObjects(),
            deadline_seconds=0.05,
        )
    assert time.monotonic() - started < 0.15


def test_embedded_asset_upload_deadline_keeps_partial_source(capture_fixture):
    import base64
    import json
    import time
    from autodata_ingestion.source_article_capture import capture_source_article

    class SlowAssets(Objects):
        def put_object(self, key, payload, media_type):
            if media_type.startswith("image/"):
                time.sleep(0.2)
            super().put_object(key, payload, media_type)

    payload = {
        "blocks": [
            {"kind": "paragraph", "text": "Check pump."},
            {
                "kind": "image",
                "url": "data:image/png;base64," + base64.b64encode(b"figure").decode(),
            },
        ]
    }
    capture_fixture.body("bankone", json.dumps(payload).encode(), "application/json")
    started = time.monotonic()
    captured = capture_source_article(
        capture_fixture.context("bankone"),
        registry=capture_fixture.registry,
        object_store=SlowAssets(),
        deadline_seconds=0.05,
    )
    assert time.monotonic() - started < 0.15
    assert captured.projection_status == "partial"
    assert captured.source_body == "Check pump."
    assert captured.source_images[0]["status"] == "unavailable"
    assert captured.source_images[0]["unavailable_reason"] == "CAPTURE_DEADLINE"


def test_required_body_upload_failure_is_fatal(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    class BrokenObjects(Objects):
        def put_object(self, *args):
            raise OSError("fixture required body upload failure")

    capture_fixture.body("bankone", b"<p>Check pump.</p>")
    with pytest.raises(OSError, match="required body"):
        capture_source_article(
            capture_fixture.context("bankone"),
            registry=capture_fixture.registry,
            object_store=BrokenObjects(),
        )
