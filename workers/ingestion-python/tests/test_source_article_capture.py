from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
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
def test_captured_rotation_retains_the_component_and_direction_when_rewritten(capture_fixture, provider):
    import json

    from autodata_ingestion.article_document import project_ordered_document
    from autodata_ingestion.procedure_rewrite import build_rewrite_prompt, rewrite_ordered_document
    from autodata_ingestion.source_article_capture import capture_source_article
    from test_procedure_rewrite_full import Draft

    opening = "Remove the retaining clip."
    instruction = "Turn the adjuster 1.5 turns clockwise."
    if provider == "bankone":
        payload = {"blocks": [{"type": "paragraph", "text": text} for text in (opening, instruction)]}
        capture_fixture.body(provider, json.dumps(payload).encode(), "application/json")
    else:
        capture_fixture.body(provider, f"<p>{opening}</p><p>{instruction}</p>".encode())

    captured = capture_source_article(
        capture_fixture.context(provider), registry=capture_fixture.registry, object_store=capture_fixture.objects,
    )
    assert captured.source_body.splitlines() == [opening, instruction]
    source = captured.source_document
    profile = "full-prose-auto-v1"
    prompt = json.loads(build_rewrite_prompt(source, context={}, profile_version=profile))
    assert [slot["required_action"] for slot in prompt["slots"]] == ["rewrite", "retain"]
    replacements = ("Take the retaining clip off.", "Give the locknut 1.5 turns counterclockwise.")
    response = {
        "introduction": "This procedure describes component access.",
        "replacements": [
            {"block_id": slot["block_id"], "path": slot["path"], "action": "rewrite", "reason": "", "text": text}
            for slot, text in zip(prompt["slots"], replacements, strict=True)
        ],
    }
    rejected = rewrite_ordered_document(source, client=Draft(response), context={}, profile_version=profile)
    assert rejected.error_code == "REWRITE_SPEC_SCOPE_MUTATION"
    assert rejected.document == source

    response["replacements"][1].update(action="retain", text=instruction, reason="Exact rotation specification.")
    retained = rewrite_ordered_document(source, client=Draft(response), context={}, profile_version=profile)
    assert retained.error_code is None
    assert project_ordered_document(retained.document)["body"].splitlines() == [
        response["introduction"], "Take the retaining clip off.", instruction,
    ]


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


@pytest.mark.parametrize("positioned", [False, True])
@pytest.mark.parametrize("embedded", [False, True])
def test_svg_asset_derives_png_and_retains_exact_original(capture_fixture, positioned, embedded):
    from autodata_ingestion.source_article_capture import capture_source_article
    from io import BytesIO
    from PIL import Image

    original = b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20" fill="red"/></svg>'
    if embedded:
        import base64
        image_bytes = BytesIO()
        Image.new("RGB", (40, 20), "red").save(image_bytes, format="PNG")
        uri = "data:image/png;base64," + base64.b64encode(image_bytes.getvalue()).decode()
        original = ('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><image width="40" height="20" href="'+uri+'"/></svg>').encode()
    body = b'<p>Remove pump.</p>' + (b'<img data-resource-ref="figure">' if positioned else b'')
    capture_fixture.body("bankone", body, assets=["figure"])
    capture_fixture.body("bankone", original, "image/svg+xml", ref="figure", kind="asset")
    captured = capture_source_article(capture_fixture.context("bankone", asset_ref="figure"), registry=capture_fixture.registry, object_store=capture_fixture.objects)
    source = next(r for r in captured.resources if r["role"] == "asset_original")
    derived = next(r for r in captured.resources if r["role"] == "asset")
    assert capture_fixture.objects.data[source["object_key"]] == (original, "image/svg+xml")
    assert derived["derived_from_sha256"] == sha256(original).hexdigest()
    assert "2.9.1" in derived["derivation_version"]
    assert derived["sha256"] != source["sha256"]
    with Image.open(BytesIO(capture_fixture.objects.data[derived["object_key"]][0])) as image:
        assert image.format == "PNG" and image.size == (40, 20)
    assert captured.source_images[0]["storage_key"] == derived["object_key"]
    assert captured.source_images[0]["status"] == "available"
    assert captured.source_images[0]["media_type"] == "image/png"
    assert captured.projection_status == "readable"
    assert [r["role"] for r in captured.resource_manifest] == ["body", "asset_original", "asset"]
    assert captured.resource_manifest[-1]["derived_from_sha256"] == source["sha256"]


def test_unpositioned_unsafe_svg_remains_unavailable_with_reason(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article
    capture_fixture.body("bankone", b'<p>Remove pump.</p>', assets=["figure"])
    original = b'<svg width="40" height="20"><image href="file:///private"/></svg>'
    capture_fixture.body("bankone", original, "image/svg+xml", ref="figure", kind="asset")
    captured = capture_source_article(capture_fixture.context("bankone", asset_ref="figure"), registry=capture_fixture.registry, object_store=capture_fixture.objects)
    assert captured.projection_status == "partial"
    assert captured.source_images[0]["status"] == "unavailable"
    assert captured.source_images[0]["unavailable_reason"] == "SVG_EXTERNAL_REFERENCE"
    assert "storage_key" not in captured.source_images[0]
    assert captured.resource_manifest[-1]["failure_code"] == "SVG_EXTERNAL_REFERENCE"
    source = next(r for r in captured.resources if r["role"] == "asset_original")
    assert capture_fixture.objects.data[source["object_key"]][0] == original


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


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("attribute", ["data-resource-ref", "asset_resource_ref"])
def test_html_ref_only_image_keeps_its_position(capture_fixture, provider, attribute):
    from autodata_ingestion.source_article_capture import capture_source_article

    raw = (
        '<p>Remove pump.</p>'
        f'<img {attribute}="diagram" alt="Pump diagram">'
        '<p>Install pump.</p>'
    ).encode()
    capture_fixture.body(provider, raw, assets=["diagram"])
    capture_fixture.body(
        provider, b"image", "image/png", ref="diagram", kind="asset"
    )

    captured = capture_source_article(
        capture_fixture.context(provider, asset_ref="diagram"),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )

    assert [block["type"] for block in captured.source_document["blocks"]] == [
        "paragraph",
        "image",
        "paragraph",
    ]
    [figure] = captured.source_images
    assert figure["alt"] == "Pump diagram"
    assert figure["status"] == "available"
    assert capture_fixture.resource_calls(provider, "diagram") == 1


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("available", [False, True])
def test_json_steps_keep_attached_figures(capture_fixture, provider, available):
    import json
    from autodata_ingestion.article_document import validate_ordered_document
    from autodata_ingestion.source_article_capture import capture_source_article

    raw = {
        "steps": [
            {
                "text": "Remove the pump.",
                "images": [
                    {
                        "asset_resource_ref": "diagram",
                        "alt": "Pump diagram",
                        "caption": "Installation marks",
                        "storage_key": "untrusted/object",
                    }
                ],
            },
            "Install the replacement.",
        ]
    }
    capture_fixture.body(provider, json.dumps(raw).encode(), "application/json")
    if available:
        capture_fixture.body(
            provider, b"image", "image/png", ref="diagram", kind="asset"
        )

    captured = capture_source_article(
        capture_fixture.context(provider),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )

    first, second = captured.source_document["blocks"]
    assert first["text"] == "Remove the pump."
    assert second["text"] == "Install the replacement."
    [figure] = first["images"]
    assert figure["alt"] == "Pump diagram"
    assert figure["caption"] == "Installation marks"
    assert [figure] == captured.source_images
    assert capture_fixture.resource_calls(provider, "diagram") == 1
    assert validate_ordered_document(captured.source_document, strict=True) == []
    assert "untrusted/object" not in str(captured.source_document)
    if available:
        assert figure["status"] == "available"
        assert captured.projection_status == "readable"
        assert capture_fixture.objects.data[figure["storage_key"]] == (b"image", "image/png")
    else:
        assert figure["unavailable_reason"] == "SOURCE_NOT_FOUND"
        assert captured.projection_status == "partial"


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("wrap_hal", [False, True])
def test_html_list_keeps_nested_table_figures_and_tail(capture_fixture, provider, wrap_hal):
    import json

    from autodata_ingestion.article_document import has_structured_list_items, validate_ordered_document
    from autodata_ingestion.source_article_capture import capture_source_article

    html = (
        '<ol><li>Remove the pump.'
        '<ul><li>Do not reuse the seal.<ol><li>Inspect the seat.</li></ol>Check the flange.</li></ul>'
        '<p>Inspect the seal first.</p>'
        '<table><tr><th>Part</th><th>Torque</th></tr><tr><td>Cover</td>'
        '<td>40 Nm<img src="torque" alt="Torque diagram"></td></tr></table>'
        '<p>Check the fitting.</p>'
        '<figure><img data-resource-ref="orientation" alt="Orientation">'
        '<figcaption>Top view.</figcaption></figure>Wipe the flange.'
        '<script>excluded-script</script><style>excluded-style</style>'
        ' <a href="https://upstream.invalid/private">Verify the seat.</a>'
        '</li><li>Install the replacement.</li></ol>'
        '<img data-resource-ref="outside" alt="Summary diagram">'
    )
    if wrap_hal:
        raw = json.dumps({"_embedded": {"data": {"article": {"content": html}}}}).encode()
        mime = "application/hal+json"
    else:
        raw, mime = html.encode(), "text/html"
    capture_fixture.body(provider, raw, mime, assets=["torque"])
    for ref in ("torque", "orientation", "outside"):
        capture_fixture.body(provider, ref.encode(), "image/png", ref=ref, kind="asset")

    captured = capture_source_article(
        capture_fixture.context(provider), registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )

    assert has_structured_list_items(captured.source_document)
    assert validate_ordered_document(captured.source_document, strict=True) == []
    ordered, outside = captured.source_document["blocks"]
    assert ordered["type"] == "ordered_list"
    assert outside["alt"] == "Summary diagram"
    first, second = ordered["items"]
    assert first["text"] == "Remove the pump."
    assert second == "Install the replacement."
    children = first["blocks"]
    assert [child["type"] for child in children] == [
        "unordered_list", "paragraph", "table", "paragraph", "image", "paragraph", "paragraph",
    ]
    alert, = children[0]["items"]
    assert alert["text"] == "Do not reuse the seal."
    assert alert["blocks"][0]["type"] == "ordered_list"
    assert alert["blocks"][0]["items"] == ["Inspect the seat."]
    assert alert["blocks"][1]["text"] == "Check the flange."
    torque = children[2]["rows"][1][1]
    assert torque["text"] == "40 Nm"
    assert torque["images"][0]["alt"] == "Torque diagram"
    assert children[4]["alt"] == "Orientation"
    assert captured.source_body.splitlines() == [
        "Remove the pump.", "Do not reuse the seal.", "Inspect the seat.", "Check the flange.",
        "Inspect the seal first.", "Part", "Torque", "Cover", "40 Nm", "Check the fitting.",
        "Top view.", "Wipe the flange. Verify the seat.", "Install the replacement.",
    ]
    assert [image["alt"] for image in captured.source_images] == [
        "Torque diagram", "Orientation", "Summary diagram",
    ]
    assert all(image["status"] == "available" for image in captured.source_images)
    assert all(capture_fixture.resource_calls(provider, ref) == 1 for ref in ("torque", "orientation", "outside"))
    assert "upstream.invalid" not in str(captured.source_document)
    assert "excluded" not in captured.source_body
    assert capture_fixture.objects.data[captured.resources[0]["object_key"]][0] == raw


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("embedded", [False, True])
@pytest.mark.parametrize("file_format,mime,available", [
    ("JPEG", "image/jpeg", True),
    ("GIF", "image/gif", True),
    ("WEBP", "image/webp", True),
    ("BMP", "image/bmp", False),
    ("TIFF", "image/tiff", False),
])
def test_capture_raster_availability_matches_paid_media(
    capture_fixture, provider, embedded, file_format, mime, available,
):
    from base64 import b64encode
    from io import BytesIO

    from PIL import Image

    from autodata_ingestion.article_document import validate_ordered_document
    from autodata_ingestion.source_article_capture import capture_source_article

    stream = BytesIO()
    Image.new("RGB", (24, 18), "green").save(stream, format=file_format)
    original = stream.getvalue()
    if embedded:
        figure = f'<img src="data:{mime};base64,{b64encode(original).decode()}" alt="Alignment marks">'
    else:
        figure = '<img data-resource-ref="figure" alt="Alignment marks">'
        capture_fixture.body(provider, original, mime, ref="figure", kind="asset")
    raw = f"<p>Inspect the seal.</p>{figure}<p>Install the replacement.</p>".encode()
    capture_fixture.body(provider, raw)
    captured = capture_source_article(
        capture_fixture.context(provider),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )

    assert validate_ordered_document(captured.source_document, strict=True) == []
    assert [block["type"] for block in captured.source_document["blocks"]] == [
        "paragraph", "image", "paragraph",
    ]
    [image] = captured.source_images
    assert image["alt"] == "Alignment marks"
    assert image["status"] == ("available" if available else "unavailable")
    assert captured.projection_status == ("readable" if available else "partial")
    _, retained = captured.resources
    assert retained["sha256"] == sha256(original).hexdigest()
    assert capture_fixture.objects.data[retained["object_key"]] == (original, mime)
    assert retained in captured.resource_provenance
    assert "data:" not in str(captured.source_document)
    if available:
        assert retained["role"] == ("embedded_asset" if embedded else "asset")
        assert image["storage_key"] == retained["object_key"]
        assert image["content_sha256"] == retained["sha256"]
        assert image["media_type"] == mime
    else:
        assert retained["role"] == "asset_original"
        assert captured.resource_manifest[1]["role"] == "asset_original"
        assert image["unavailable_reason"] == "UNSUPPORTED_ASSET_MEDIA"
        assert "storage_key" not in image
        assert "content_sha256" not in image
        assert retained["object_key"] not in str(captured.source_document)
        if not embedded:
            assert captured.resource_manifest[-1] == {
                "role": "asset", "opaque_ref": "figure", "failure_code": "UNSUPPORTED_ASSET_MEDIA",
            }


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("wrap_hal", [False, True])
def test_capture_preserves_authored_ordinals_through_normalization_and_rewrite(capture_fixture, provider, wrap_hal):
    import json

    from autodata_ingestion.article_document import project_ordered_document, validate_ordered_document
    from autodata_ingestion.procedure_normalize import normalize_procedure_article
    from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    from autodata_ingestion.source_article_capture import capture_source_article

    html = (
        '<ol start="4"><li>Remove the cover.</li><li value="9">Inspect the seal.</li>'
        '<li>Install the plate.</li></ol>'
    )
    if wrap_hal:
        body = json.dumps({"_embedded": {"data": {"article": {"content": html}}}}).encode()
        media_type = "application/hal+json"
    else:
        body, media_type = html.encode(), "text/html"
    capture_fixture.body(provider, body, media_type)
    captured = capture_source_article(
        capture_fixture.context(provider), registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    source = captured.source_document
    assert validate_ordered_document(source, strict=True) == []
    ordered, = source["blocks"]
    assert ordered["start"] == 4
    assert ordered["items"] == ["Remove the cover.", {"text": "Inspect the seal.", "number": 9}, "Install the plate."]
    assert [step["number"] for step in captured.source_steps] == [4, 9, 10]
    normalized = normalize_procedure_article({
        "normalized_document": source, "body": captured.source_body, "steps": captured.source_steps,
    })
    assert normalized["normalized_document"] == source
    assert [step["number"] for step in normalized["steps"]] == [4, 9, 10]

    rewritten_text = ["Take off the cover.", "Check the seal.", "Fit the plate into place."]
    response = {
        "introduction": "This article describes cover service.",
        "replacements": [
            {**slot, "action": "rewrite", "reason": "", "text": draft}
            for slot, draft in zip(prose_slots(source), rewritten_text, strict=True)
        ],
    }
    canonical = render_auto(source, response)
    assert validate_auto(source, canonical, response=response).passed
    rewritten_list = canonical["blocks"][1]
    assert rewritten_list["start"] == 4
    assert rewritten_list["items"] == [rewritten_text[0], {"text": rewritten_text[1], "number": 9}, rewritten_text[2]]
    assert [step["number"] for step in project_ordered_document(canonical)["steps"]] == [4, 9, 10]

    for obj, key, number in (
        (rewritten_list, "start", 5),
        (rewritten_list["items"][1], "number", 8),
    ):
        old = obj[key]
        obj[key] = number
        assert not validate_auto(source, canonical, response=response).passed
        obj[key] = old


def test_legacy_flat_html_keeps_original_unnumbered_document_shape(capture_fixture):
    from autodata_ingestion.article_document import has_ordered_list_numbering
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body("bankone", b"<ol><li>Remove the cover.</li><li>Inspect the seal.</li></ol>", "text/html")
    captured = capture_source_article(
        capture_fixture.context("bankone"), registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    ordered, = captured.source_document["blocks"]
    assert ordered["items"] == ["Remove the cover.", "Inspect the seal."]
    assert "start" not in ordered
    assert has_ordered_list_numbering(captured.source_document) is False
    assert [step["number"] for step in captured.source_steps] == [1, 2]


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


@pytest.mark.parametrize(("provider", "wrapper"), [
    ("banktwo", None),
    ("bankone", "root"),
    ("banktwo", "body"),
])
def test_mixed_pdf_keeps_ocr_text_and_embedded_figure_in_page_order(
    capture_fixture, monkeypatch, provider, wrapper,
):
    import base64
    import json
    import random
    from io import BytesIO

    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    from autodata_ingestion import source_adapters
    from autodata_ingestion.ocr import OCRTextBlock
    from autodata_ingestion.source_article_capture import capture_source_article

    image = Image.frombytes("RGB", (96, 96), random.Random(7).randbytes(96 * 96 * 3))
    figure = BytesIO()
    image.save(figure, format="PNG")
    figure.seek(0)
    buf = BytesIO()
    pdf = canvas.Canvas(buf)
    pdf.drawString(72, 720, "Remove the pump.")
    pdf.showPage()
    pdf.drawImage(ImageReader(figure), 72, 500, 96, 96)
    pdf.showPage()
    pdf.drawString(72, 720, "Install the replacement.")
    pdf.showPage()
    pdf.save()

    def read_scanned_page(_digest, _payload, native_pages):
        assert native_pages == {1, 3}
        return (
            OCRTextBlock("Check the seal.", 0.96, (72, 96, 180, 30), page_number=2),
            OCRTextBlock("Wipe the flange.", 0.96, (72, 140, 180, 30), page_number=2),
        )

    monkeypatch.setattr(source_adapters, "extract_scanned_pdf_text", read_scanned_page)
    pdf_payload = buf.getvalue()
    if wrapper is None:
        body_payload, body_media = pdf_payload, "application/pdf"
    else:
        encoded = base64.b64encode(pdf_payload).decode()
        if wrapper == "body":
            wrapped_pdf = {"body": {"documentId": 42, "pdf": "data:application/pdf;base64," + encoded}}
        else:
            wrapped_pdf = {"pdf": encoded}
        body_payload, body_media = json.dumps(wrapped_pdf).encode(), "application/json"
    capture_fixture.body(
        provider, body_payload, body_media, kind="binary" if wrapper is None else "article",
    )
    context = capture_fixture.context(provider)
    captured = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects,
        keep_embedded_pdf=wrapper is not None,
    )
    assert captured.projection_version == ("source-projection-v5" if wrapper else "source-projection-v2")

    body_resource, figure_resource = captured.resource_provenance
    assert body_resource["sha256"] == sha256(body_payload).hexdigest()
    assert capture_fixture.objects.data[body_resource["object_key"]] == (body_payload, body_media)
    assert figure_resource["role"] == "embedded_asset"
    assert figure_resource["opaque_ref"].startswith("embedded:" + body_resource["sha256"] + ":")
    assert capture_fixture.resource_calls(provider, "body") == 1
    assert not any("/resources/" in call and not call.endswith("/body") for call in capture_fixture.calls(provider))
    assert not capture_fixture.calls("banktwo" if provider == "bankone" else "bankone")
    assert [(resource["role"], resource["media_type"]) for resource in captured.resource_manifest] == [
        ("body", body_media), ("embedded_asset", "image/png"),
    ]
    assert all(
        entry["body_source_snapshot_id"] == body_resource["source_snapshot_id"]
        for entry in captured.evidence_manifest
    )
    if wrapper is not None:
        assert len(capture_fixture.objects.data) == 2
        assert encoded not in captured.source_body
        assert encoded not in str(captured.source_document)

    contents = [
        (block["type"], block.get("text") or block.get("alt"))
        for block in captured.source_document["blocks"]
    ]
    assert contents == [
        ("paragraph", "Remove the pump."),
        ("paragraph", "Check the seal."),
        ("paragraph", "Wipe the flange."),
        ("image", "Figure from page 2"),
        ("paragraph", "Install the replacement."),
    ]
    assert captured.source_body.splitlines() == [
        "Remove the pump.",
        "Check the seal.",
        "Wipe the flange.",
        "Install the replacement.",
    ]
    [localized] = captured.source_images
    payload, media_type = capture_fixture.objects.data[localized["storage_key"]]
    assert media_type == "image/png"
    with Image.open(BytesIO(payload)) as stored:
        assert stored.tobytes() == image.tobytes()


@pytest.mark.parametrize("payload", [
    {"pdf": "invalid base64"},
    {"body": {"pdf": "Tm90IGEgUERGLg=="}},
    {"body": {"pdf": ["not-a-string"]}},
])
def test_invalid_embedded_pdf_is_not_projected_as_article_text(capture_fixture, payload):
    import json

    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body("bankone", json.dumps(payload).encode(), "application/json")
    with pytest.raises(SourceConnectorError) as raised:
        capture_source_article(
            capture_fixture.context("bankone"), registry=capture_fixture.registry,
            object_store=capture_fixture.objects, keep_embedded_pdf=True,
        )
    assert raised.value.code == "INVALID_ARTICLE_BODY"


@pytest.mark.parametrize("limit", ["bytes", "pages"])
def test_embedded_pdf_bounds_apply_before_extraction_and_ocr(capture_fixture, monkeypatch, limit):
    import base64
    import json
    from io import BytesIO

    from reportlab.pdfgen import canvas

    from autodata_ingestion import source_adapters
    from autodata_ingestion.source_article_capture import capture_source_article

    def unexpected_extraction(*_):
        pytest.fail("PDF exceeds the bound before extraction or OCR")

    monkeypatch.setattr(source_adapters, "_extract_pdf_page_images", unexpected_extraction)
    monkeypatch.setattr(source_adapters, "extract_scanned_pdf_text", unexpected_extraction)
    if limit == "bytes":
        monkeypatch.setattr(source_adapters, "_MAX_BOUND_EMBEDDED_PDF_BYTES", 8)
    else:
        monkeypatch.setattr(source_adapters, "_MAX_BOUND_EMBEDDED_PDF_PAGES", 1)
    stream = BytesIO()
    document = canvas.Canvas(stream)
    for _ in range(2):
        document.drawString(72, 720, "Check the cover.")
        document.showPage()
    document.save()
    encoded = base64.b64encode(stream.getvalue()).decode()
    capture_fixture.body("bankone", json.dumps({"pdf": encoded}).encode(), "application/json")
    with pytest.raises(SourceConnectorError) as raised:
        capture_source_article(
            capture_fixture.context("bankone"), registry=capture_fixture.registry,
            object_store=capture_fixture.objects, keep_embedded_pdf=True,
        )
    assert raised.value.code == "INVALID_ARTICLE_BODY"


@pytest.mark.parametrize("article", [
    {"body": {"pdf": "unused"}, "text": "Inspect the pump."},
    {"pdf": "unused", "steps": ["Inspect the pump."]},
    {"pdf": "unused", "blocks": [{"type": "paragraph", "text": "Inspect the pump."}]},
])
def test_embedded_pdf_does_not_override_explicit_article_content(capture_fixture, article):
    import json

    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body("bankone", json.dumps(article).encode(), "application/json")
    captured = capture_source_article(
        capture_fixture.context("bankone"), registry=capture_fixture.registry,
        object_store=capture_fixture.objects, keep_embedded_pdf=True,
    )
    assert captured.source_body == "Inspect the pump."
    assert captured.source_images == []


def test_retained_wrapper_keeps_legacy_adapter_default(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body(
        "bankone", b'{"body":{"documentId":"synthetic","pdf":"legacy-fixture"}}', "application/json",
    )
    captured = capture_source_article(
        capture_fixture.context("bankone"), registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert captured.source_body == "{'documentId': 'synthetic', 'pdf': 'legacy-fixture'}"
    assert captured.projection_version == "source-projection-v2"


@pytest.mark.parametrize("metadata", [
    b'<meta name="vehicle" content="1999 Example Car">',
    b'<meta name="vehicle.year" content="1999">',
    b'<script type="application/ld+json">{"about":{"name":"1999 Example Car"}}</script>',
])
def test_html_explicit_vehicle_metadata_cannot_override_resolved_scope(capture_fixture, metadata):
    from autodata_ingestion.source_article_capture import capture_source_article

    capture_fixture.body("banktwo", metadata + b"<p>Remove pump.</p>")
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
@pytest.mark.parametrize("placement", ["single_paragraph", "paragraph", "step", "table", "standalone"])
def test_short_captured_document_keeps_media_for_auto_rewrite(capture_fixture, provider, placement):
    import json

    from autodata_ingestion.article_document import build_ordered_document, validate_ordered_document
    from autodata_ingestion.article_lifecycle_store import StoredSource
    from autodata_ingestion.procedure_normalize import normalize_procedure_article
    from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    from autodata_ingestion.source_article_capture import _image_nodes, capture_source_article

    figures = [
        {"asset_resource_ref": "available", "alt": "Installation marks"},
        {"asset_resource_ref": "missing", "alt": "Seal orientation"},
    ]
    if placement == "table":
        positioned = [{"kind": "table", "rows": [[{"text": "Pump seal", "images": figures}]]}]
    elif placement == "standalone":
        positioned = [{"kind": "image", **figure} for figure in figures]
    else:
        positioned = [{"kind": placement, "text": "Inspect the seal.", "images": figures}]
    opening = {"kind": "paragraph", "text": "Remove the pump."}
    if placement == "single_paragraph":
        opening.update(text="Service the pump.", images=figures)
        positioned = []
    payload = {"blocks": [opening, *positioned]}
    capture_fixture.body(provider, json.dumps(payload).encode(), "application/json")
    capture_fixture.body(provider, b"localized", "image/png", ref="available", kind="asset")
    captured = capture_source_article(
        replace(capture_fixture.context(provider), evidence_ids=()),
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert validate_ordered_document(captured.source_document, strict=True) == []
    source = StoredSource(
        source_revision_id=uuid.uuid4(),
        context=captured.context,
        source_document=captured.source_document,
        source_images=captured.source_images,
        source_body=captured.source_body,
        source_steps=captured.source_steps,
        source_fingerprint=captured.source_fingerprint,
        evidence_manifest=captured.evidence_manifest,
        body_source_snapshot_id=captured.body_source_snapshot_id,
        resource_manifest=captured.resource_manifest,
        projection_status=captured.projection_status,
        captured_at=captured.captured_at,
        projection_version=captured.projection_version,
    )
    article = source.as_article()
    normalized = normalize_procedure_article(article)["normalized_document"]
    assert normalized == captured.source_document

    rebuilt = build_ordered_document(article, article["blocks"])
    assert validate_ordered_document(rebuilt, strict=True) == []
    localized, unavailable = list(_image_nodes(rebuilt["blocks"]))
    assert localized["status"] == "available"
    assert localized["media_type"] == "image/png"
    assert localized["storage_key"] == captured.source_images[0]["storage_key"]
    assert localized["content_sha256"] == sha256(b"localized").hexdigest()
    assert unavailable["status"] == "unavailable"
    assert unavailable["unavailable_reason"] == "SOURCE_NOT_FOUND"
    assert "storage_key" not in unavailable
    assert localized["evidence_ids"] == unavailable["evidence_ids"] == [
        "source:" + str(captured.body_source_snapshot_id)
    ]

    rewrite = {
        "introduction": "This procedure covers pump removal.",
        "replacements": [
            {**slot, "action": "rewrite", "reason": "", "text": {
                "Remove the pump.": "Take the pump off.",
                "Service the pump.": "Perform the pump service.",
                "Inspect the seal.": "Check the seal.",
            }[slot["text"]]}
            for slot in prose_slots(normalized)
        ],
    }
    candidate = render_auto(normalized, rewrite)
    assert validate_auto(normalized, candidate, response=rewrite).passed
    rewritten_figures = list(_image_nodes(candidate["blocks"]))
    if placement == "standalone":
        # Auto rewrite inserts an introduction before the protected original blocks.
        assert [figure["source_order"] for figure in rewritten_figures] == [3, 4]
        rewritten_figures = [
            {**figure, "source_order": figure["source_order"] - 1}
            for figure in rewritten_figures
        ]
    assert rewritten_figures == captured.source_images


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("localized", [False, True])
@pytest.mark.parametrize("context_evidence", [False, True])
@pytest.mark.parametrize("location", ["step", "instruction", "table", "list", "callout"])
def test_nested_kindless_images_require_verified_provider_bytes(
    capture_fixture, provider, localized, context_evidence, location
):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article, _image_nodes

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
        "evidence_ids": ["upstream-forged"],
    }
    nested = {
        "step": {"kind": "step", "text": "Check the pump.", "images": [image]},
        "instruction": {"kind": "step", "instructions": [{"text": "Check the pump.", "images": [image]}]},
        "table": {"kind": "table", "rows": [[{"text": "Torque 25 Nm", "images": [image]}]]},
        "list": {"kind": "ordered_list", "items": [{"text": "Check the pump.", "images": [image]}]},
        "callout": {"kind": "callout", "items": [{"text": "Check the pump.", "images": [image]}]},
    }[location]
    payload = {"blocks": [{"kind": "paragraph", "text": "Remove the pump."}, nested]}
    capture_fixture.body(provider, json.dumps(payload).encode(), "application/json")
    if localized:
        capture_fixture.body(
            provider, provider.encode(), "image/png", ref="figure", kind="asset"
        )
    context = capture_fixture.context(provider)
    if not context_evidence:
        context = replace(context, evidence_ids=())
    captured = capture_source_article(
        context,
        registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert capture_fixture.resource_calls(provider, "figure") == 1
    assert (
        capture_fixture.calls("banktwo" if provider == "bankone" else "bankone") == []
    )
    assert len(captured.source_images) == 1
    nested_images = list(_image_nodes(captured.source_document["blocks"][1]))
    assert len(nested_images) == 1
    image = nested_images[0]
    assert image["status"] == ("available" if localized else "unavailable")
    assert image in captured.source_images
    from autodata_ingestion.article_document import validate_ordered_document
    assert validate_ordered_document(captured.source_document, strict=True) == []
    expected_evidence = list(context.evidence_ids) or [
        "source:" + str(captured.body_source_snapshot_id)
    ]
    assert image["evidence_ids"] == expected_evidence
    from autodata_ingestion.procedure_rewrite import rewrite_ordered_document

    class Model:
        calls = 0

        def complete_json(self, prompt):
            self.calls += 1
            slots = json.loads(prompt)["slots"]
            return {"replacements": [{**slot, "text": slot["text"].replace("Remove", "Take off")} for slot in slots]}

    model = Model()
    rewritten = rewrite_ordered_document(captured.source_document, client=model, context=context.vehicle)
    assert model.calls == 1
    assert rewritten.error_code is None
    assert list(_image_nodes(rewritten.document["blocks"][1])) == [image]
    assert validate_ordered_document(rewritten.document, strict=True) == []
    assert "fixture-untrusted" not in str(captured.source_document)
    assert "untrusted.invalid" not in str(captured.source_document)
    assert "/untrusted/" not in str(captured.source_document)
    if localized:
        assert image["storage_key"] in capture_fixture.objects.data
        assert image["content_sha256"] == sha256(provider.encode()).hexdigest()
        assert capture_fixture.objects.data[image["storage_key"]] == (
            provider.encode(), "image/png"
        )
    else:
        assert not image.get("storage_key")
        assert captured.projection_status == "partial"


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_capture_keeps_structured_list_actions_and_media_through_full_rewrite(capture_fixture, provider):
    import json

    from autodata_ingestion.article_document import (
        has_structured_list_items, project_ordered_document, validate_ordered_document,
    )
    from autodata_ingestion.procedure_normalize import normalize_procedure_article
    from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    from autodata_ingestion.source_article_capture import capture_source_article, project_document

    payload = {
        "blocks": [
            {"kind": "ordered_list", "items": [
                "Drain the pump.",
                {"text": "Remove the pump.", "images": [
                    {"asset_resource_ref": "orientation", "alt": "Orientation"},
                ], "blocks": [
                    {"kind": "step", "text": "Inspect the seal."},
                    {"kind": "warning", "text": "Do not reuse the seal."},
                    {"kind": "table", "columns": ["Part", "Torque"],
                     "rows": [["Cover", {"text": "40 Nm", "images": [
                         {"asset_resource_ref": "torque", "alt": "Torque diagram"},
                     ]}]]},
                    {"kind": "image", "asset_resource_ref": "missing", "alt": "Optional detail"},
                ]},
                {"blocks": [{"kind": "step", "text": "Fit the replacement."}]},
                "Check the fitting.",
            ], "images": [{"asset_resource_ref": "after", "alt": "Summary diagram"}]},
        ],
    }
    raw = json.dumps(payload).encode()
    capture_fixture.body(provider, raw, "application/json")
    for ref in ("orientation", "torque", "after"):
        capture_fixture.body(provider, ref.encode(), "image/png", ref=ref, kind="asset")
    context = capture_fixture.context(provider)
    captured = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects,
    )
    assert capture_fixture.objects.data[captured.resources[0]["object_key"]][0] == raw
    assert has_structured_list_items(captured.source_document)
    assert validate_ordered_document(captured.source_document, strict=True) == []
    assert captured.source_body.splitlines() == [
        "Drain the pump.", "Remove the pump.", "Inspect the seal.", "Do not reuse the seal.",
        "Part", "Torque", "Cover", "40 Nm", "Fit the replacement.", "Check the fitting.",
    ]
    assert [step["text"] for step in captured.source_steps] == [
        "Drain the pump.", "Remove the pump.", "Inspect the seal.", "Fit the replacement.",
        "Check the fitting.",
    ]
    assert [step["number"] for step in captured.source_steps] == [1, 2, 3, 4, 5]
    assert [image["alt"] for image in captured.source_images] == [
        "Orientation", "Torque diagram", "Optional detail", "Summary diagram",
    ]
    assert [image["status"] for image in captured.source_images] == [
        "available", "available", "unavailable", "available",
    ]
    assert captured.source_images[2]["unavailable_reason"] == "SOURCE_NOT_FOUND"
    round_trip = json.loads(json.dumps(captured.source_document, sort_keys=True))
    assert project_document(round_trip) == (
        captured.source_body, captured.source_steps, captured.source_images,
    )
    article = {
        "normalized_document": captured.source_document,
        "body": captured.source_body,
        "steps": captured.source_steps,
        "images": captured.source_images,
    }
    normalized = normalize_procedure_article(article)["normalized_document"]
    assert normalized == captured.source_document

    slots = prose_slots(normalized)
    assert [slot["text"] for slot in slots] == [step["text"] for step in captured.source_steps]
    substitutions = {
        "Drain the pump.": "Empty the pump.",
        "Remove the pump.": "Take the pump off.",
        "Inspect the seal.": "Check the seal condition.",
        "Fit the replacement.": "Install the replacement.",
        "Check the fitting.": "Inspect the fitting.",
    }
    response = {
        "introduction": "This procedure covers pump service.",
        "replacements": [
            {**slot, "action": "rewrite", "reason": "", "text": substitutions[slot["text"]]}
            for slot in slots
        ],
    }
    canonical = render_auto(normalized, response)
    assert validate_auto(normalized, canonical, response=response).passed
    [_, rewritten_list] = canonical["blocks"]
    rewritten_item = rewritten_list["items"][1]
    source_item = captured.source_document["blocks"][0]["items"][1]
    assert rewritten_item["images"] == source_item["images"]
    assert rewritten_item["blocks"][0]["text"] == "Check the seal condition."
    assert rewritten_item["blocks"][1:] == source_item["blocks"][1:]
    canonical_projection = project_ordered_document(canonical)
    assert [step["action"] for step in canonical_projection["steps"]] == list(substitutions.values())
    assert canonical_projection["images"] == captured.source_images


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


@pytest.fixture(params=["os", "s3", "connection"])
def storage_failure(request):
    if request.param == "s3":
        from minio.error import S3Error

        return S3Error(
            response=None,
            code="ServiceUnavailable",
            message="private object endpoint unreachable",
            resource=None,
            request_id=None,
            host_id=None,
        )
    if request.param == "connection":
        from urllib3.exceptions import NewConnectionError

        return NewConnectionError(None, "private object endpoint unreachable")
    return OSError("private object endpoint unreachable")


def test_optional_asset_upload_failure_preserves_readable_source(
    capture_fixture, storage_failure
):
    from autodata_ingestion.source_article_capture import capture_source_article

    class FailingAssets(Objects):
        def put_object(self, key, payload, media_type):
            if media_type.startswith("image/"):
                raise storage_failure
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


def test_required_body_upload_failure_is_fatal(capture_fixture, storage_failure):
    from autodata_ingestion.source_article_capture import capture_source_article

    class BrokenObjects(Objects):
        def put_object(self, *args):
            raise storage_failure

    capture_fixture.body("bankone", b"<p>Check pump.</p>")
    with pytest.raises(
        SourceConnectorError, match="asset_storage_unavailable"
    ) as error:
        capture_source_article(
            capture_fixture.context("bankone"),
            registry=capture_fixture.registry,
            object_store=BrokenObjects(),
        )
    assert "private object endpoint" not in str(error.value)
    assert error.value.retryable is True


def test_embedded_asset_storage_failure_preserves_readable_source(
    capture_fixture, storage_failure
):
    import base64
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    class BrokenAssets(Objects):
        def put_object(self, key, payload, media_type):
            if media_type.startswith("image/"):
                raise storage_failure
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
    capture_fixture.body("banktwo", json.dumps(payload).encode(), "application/json")
    captured = capture_source_article(
        capture_fixture.context("banktwo"),
        registry=capture_fixture.registry,
        object_store=BrokenAssets(),
    )
    assert captured.source_body == "Check pump."
    assert captured.projection_status == "partial"
    assert captured.source_images[0]["status"] == "unavailable"
    assert (
        captured.source_images[0]["unavailable_reason"] == "ASSET_STORAGE_UNAVAILABLE"
    )
    assert "private object endpoint" not in str(captured)


@pytest.mark.parametrize("media", ["application/json", "application/hal+json"])
def test_nested_html_capture_preserves_order_and_original_resource(capture_fixture, media):
    """Synthetic connector content exercises the authentic HAL envelope shape."""
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    payload = json.dumps({"_embedded": {"data": {"article": {
        "title": "Pump",
        "content": '<p>Remove the cover.</p><table><tr><td>25 Nm</td></tr></table>'
                   '<img data-resource-ref="asset:one" src="https://source.invalid/a.png">',
    }}}}).encode()
    context = capture_fixture.context("banktwo", asset_ref="asset:one")
    capture_fixture.body("banktwo", payload, media)
    capture_fixture.body("banktwo", b"synthetic-figure", "image/png", ref="asset:one", kind="asset")
    captured = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects
    )
    blocks = captured.source_document["blocks"]
    assert [block["type"] for block in blocks] == ["paragraph", "table", "image"]
    assert blocks[0]["text"] == "Remove the cover."
    assert blocks[1]["rows"] == [["25 Nm"]]
    assert captured.source_body == "Remove the cover.\n25 Nm"
    assert all(block["evidence_ids"] == list(context.evidence_ids) for block in blocks)
    image = blocks[2]
    assert any(row["opaque_ref"] == "asset:one" and row["role"] == "asset"
               for row in captured.resource_manifest)
    assert image["status"] == "available"
    assert image["content_sha256"] == sha256(b"synthetic-figure").hexdigest()
    assert capture_fixture.objects.data[image["storage_key"]] == (b"synthetic-figure", "image/png")
    body = next(row for row in captured.resource_provenance if row["role"] == "body")
    assert body["provider"] == "banktwo"
    assert body["sha256"] == sha256(payload).hexdigest()
    assert body["media_type"] == media
    assert capture_fixture.objects.data[body["object_key"]] == (payload, media)
    assert capture_fixture.calls("bankone") == []
    assert capture_fixture.resource_calls("banktwo", "asset:one") == 1
    if media == "application/hal+json":
        capture_fixture.body("banktwo", payload, "application/json")
        json_capture = capture_source_article(
            context, registry=capture_fixture.registry, object_store=capture_fixture.objects
        )
        assert captured.source_document == json_capture.source_document
        assert captured.source_body == json_capture.source_body
        assert captured.source_images == json_capture.source_images


@pytest.mark.parametrize("payload", [
    [], None, "article", {},
    {"_embedded": []}, {"_embedded": {}},
    {"_embedded": {"data": []}}, {"_embedded": {"data": {}}},
    {"_embedded": {"data": {"article": []}}},
    *({"_embedded": {"data": {"article": {"body": "Remove pump.", "content": value}}}}
      for value in [None, 1, False, [], {}]),
])
def test_hal_malformed_envelope_rejected_before_projection(capture_fixture, payload):
    import json
    from autodata_ingestion.source_adapters import SourceResource, adapt_bound_article

    resource = SourceResource.from_bytes(
        "connector:synthetic", "fixture", json.dumps(payload).encode(), "application/hal+json"
    )
    with pytest.raises(ValueError, match="invalid article document"):
        adapt_bound_article(resource, capture_fixture.context("banktwo"))


@pytest.mark.parametrize("media", ["application/json", "application/hal+json"])
@pytest.mark.parametrize("layer", ["root", "embedded", "data", "article"])
@pytest.mark.parametrize("identity", [
    {"vehicle": {"year": 1999}},
    {"source_vehicle_ref": "another-provider/vehicle"},
    {"vehicle_id": "00000000-0000-0000-0000-000000000000"},
])
def test_hal_identity_layers_cannot_override_bound_scope(capture_fixture, media, layer, identity):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    article = {"content": "<p>Remove pump.</p>"}
    data = {"article": article}
    embedded = {"data": data}
    payload = {"_embedded": embedded}
    {"root": payload, "embedded": embedded, "data": data, "article": article}[layer].update(identity)
    capture_fixture.body("banktwo", json.dumps(payload).encode(), media)
    with pytest.raises(SourceConnectorError, match="applicability"):
        capture_source_article(
            capture_fixture.context("banktwo"), registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
        )
    assert capture_fixture.calls("bankone") == []


@pytest.mark.parametrize("media", ["application/json", "application/hal+json"])
def test_hal_capture_rejects_registry_provider_mismatch(capture_fixture, media):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    payload = {"_embedded": {"data": {"article": {"content": "Remove pump."}}}}
    capture_fixture.body("banktwo", json.dumps(payload).encode(), media)
    registry = {"banktwo": capture_fixture.registry["bankone"]}
    with pytest.raises(SourceConnectorError):
        capture_source_article(
            capture_fixture.context("banktwo"), registry=registry,
            object_store=capture_fixture.objects,
        )
    assert capture_fixture.calls("bankone") == capture_fixture.calls("banktwo") == []


def test_bound_article_does_not_accept_arbitrary_json_suffix(capture_fixture):
    from autodata_ingestion.source_adapters import SourceResource, adapt_bound_article

    resource = SourceResource.from_bytes(
        "connector:synthetic", "fixture", b'{"body":"Remove pump."}', "application/custom+json"
    )
    with pytest.raises(ValueError, match="unsupported article media"):
        adapt_bound_article(resource, capture_fixture.context("banktwo"))


MAINTENANCE_XML = '''<?xml version="1.0"?>
<maintenance_schedule title="Service &amp; checks">
  <footnote>Initial footnote.</footnote>
  <operation id="op1" name="Inspect &lt;inert&gt;">
    <component id="c1" name="Belt">
      <notes>Before<br/>After <a href="https://example.invalid/manual">manual</a> tail <![CDATA[<literal> & text]]></notes>
      <warranty>Keep receipt.</warranty><qualifier>Severe service only.</qualifier>
    </component>
    <component id="c2" name="Hose"><notes>Check hose.</notes></component>
  </operation>
  <footnote>Do not omit footnote.</footnote>
  <operation id="op2" name="Replace"><component id="c3" name="Filter"><notes>Replace filter.</notes></component></operation>
</maintenance_schedule>'''


@pytest.mark.parametrize("media", ["application/xml", "text/xml", "application/hal+json"])
def test_maintenance_xml_capture_preserves_fields_order_and_resource(capture_fixture, media):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article
    from autodata_ingestion.article_document import validate_ordered_document

    payload = MAINTENANCE_XML.encode()
    if media == "application/hal+json":
        payload = json.dumps({"_embedded": {"data": {"article": {"content": MAINTENANCE_XML}}}}).encode()
    context = capture_fixture.context("banktwo")
    capture_fixture.body("banktwo", payload, media)
    captured = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects
    )
    assert captured.source_body.splitlines() == [
        "Service & checks", "Initial footnote.", "Inspect <inert> (op1)", "Belt (c1)",
        "Before", "After", "manual", "tail <literal> & text", "Keep receipt.",
        "Severe service only.", "Hose (c2)", "Check hose.", "Do not omit footnote.",
        "Replace (op2)", "Filter (c3)", "Replace filter.",
    ]
    blocks = captured.source_document["blocks"]
    link = next(block for block in blocks if block["type"] == "link")
    assert (link["text"], link["href"]) == ("manual", "https://example.invalid/manual")
    assert validate_ordered_document(captured.source_document, strict=True) == []
    assert all(block["evidence_ids"] == list(context.evidence_ids) for block in blocks)
    assert captured.context == context
    assert captured.projection_status == "readable"
    provenance = next(row for row in captured.resource_provenance if row["role"] == "body")
    assert provenance["provider"] == "banktwo"
    assert provenance["sha256"] == sha256(payload).hexdigest()
    assert provenance["media_type"] == media
    assert capture_fixture.objects.data[provenance["object_key"]] == (payload, media)
    assert capture_fixture.calls("bankone") == []
    assert not any("example.invalid" in call for call in capture_fixture.calls("banktwo"))


@pytest.mark.parametrize("text", ["Pressure < 3 bar is allowed.", "<p>Check pressure.</p>", "<br/><p>Check pressure.</p>"])
def test_nested_maintenance_routing_preserves_existing_prose_and_html(capture_fixture, text):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    payload = {"_embedded": {"data": {"article": {"content": text}}}}
    capture_fixture.body("banktwo", json.dumps(payload).encode(), "application/hal+json")
    captured = capture_source_article(
        capture_fixture.context("banktwo"), registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert captured.source_body == ("Check pressure." if "<p>" in text else text)


def test_xml_validation_cannot_precede_hal_applicability(capture_fixture):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    payload = {"vehicle": {"year": 1999}, "_embedded": {"data": {"article": {
        "content": "<maintenance_schedule malformed",
    }}}}
    capture_fixture.body("banktwo", json.dumps(payload).encode(), "application/hal+json")
    with pytest.raises(SourceConnectorError, match="applicability"):
        capture_source_article(
            capture_fixture.context("banktwo"), registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
        )


@pytest.mark.parametrize("nested", [False, True])
def test_maintenance_xml_rejection_never_creates_readable_capture(capture_fixture, nested):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    xml = '<maintenance_schedule title="Check"><unknown>Remove pump.</unknown></maintenance_schedule>'
    payload, media = xml.encode(), "application/xml"
    if nested:
        payload = json.dumps({"_embedded": {"data": {"article": {"content": xml}}}}).encode()
        media = "application/hal+json"
    capture_fixture.body("banktwo", payload, media)
    with pytest.raises(SourceConnectorError, match="invalid_article_body"):
        capture_source_article(
            capture_fixture.context("banktwo"), registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
        )


@pytest.mark.parametrize("note,expected", [
    ("5.0 Nm\n6.0 Nm", "5.0 Nm 6.0 Nm"),
    ("Page 1 of 2\nCheck belt.\nCheck hose.", "Page 1 of 2 Check belt. Check hose."),
    ("1. Remove pump.", "1. Remove pump."),
])
def test_maintenance_xml_notes_preserve_literal_numbers_and_cdata(capture_fixture, note, expected):
    import json
    from autodata_ingestion.source_article_capture import capture_source_article

    xml = ('<maintenance_schedule title="Service"><operation id="o" name="Inspect">'
           '<component id="c" name="Belt"><notes><![CDATA[' + note +
           ']]></notes></component></operation></maintenance_schedule>')
    payload = {"_embedded": {"data": {"article": {"content": xml}}}}
    capture_fixture.body("banktwo", json.dumps(payload).encode(), "application/hal+json")
    captured = capture_source_article(
        capture_fixture.context("banktwo"), registry=capture_fixture.registry,
        object_store=capture_fixture.objects,
    )
    assert captured.source_body.splitlines() == ["Service", "Inspect (o)", "Belt (c)", expected]
    assert captured.source_steps == []


def test_capture_explicitly_versions_corrected_projection(capture_fixture):
    from autodata_ingestion.source_article_capture import capture_source_article
    context = capture_fixture.context("banktwo")
    capture_fixture.body("banktwo", MAINTENANCE_XML.encode(), "application/xml")
    captured = capture_source_article(context, registry=capture_fixture.registry,
                                     object_store=capture_fixture.objects)
    assert captured.projection_version == "source-projection-v2"
    historical = replace(captured, projection_version="source-projection-v1")
    assert historical.source_fingerprint == captured.source_fingerprint
    assert historical.body_source_snapshot_id == captured.body_source_snapshot_id
    assert historical.resources == captured.resources


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("wrap_hal", [False, True])
def test_authored_headings_keep_metadata_and_instruction_boundaries(capture_fixture, provider, wrap_hal):
    import json

    from autodata_ingestion.procedure_normalize import normalize_procedure_article
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    from autodata_ingestion.source_article_capture import capture_source_article

    markup = "<h2>Pump <em>removal</em></h2>Remove the pump.<h4>Inspection</h4><p>Inspect the cover.</p>"
    if wrap_hal:
        body = json.dumps({"_embedded": {"data": {"article": {"content": markup}}}}).encode()
        media = "application/hal+json"
    else:
        body, media = markup.encode(), "text/html"
    capture_fixture.body(provider, body, media)
    args = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects)
    legacy = capture_source_article(capture_fixture.context(provider), **args)
    new = capture_source_article(capture_fixture.context(provider), keep_html_headings=True, **args)
    assert legacy.projection_version == "source-projection-v2"
    assert new.projection_version == "source-projection-v5"
    assert legacy.source_fingerprint == new.source_fingerprint
    assert legacy.resource_manifest == new.resource_manifest
    assert "Pump removalRemove the pump." in legacy.source_body
    document = normalize_procedure_article({
        "normalized_document": new.source_document, "blocks": new.source_document["blocks"],
        "body": new.source_body, "steps": new.source_steps,
    })["normalized_document"]
    assert [(block["type"], block.get("level"), block["text"]) for block in document["blocks"]] == [
        ("heading", 2, "Pump removal"),
        ("paragraph", None, "Remove the pump."),
        ("heading", 4, "Inspection"),
        ("paragraph", None, "Inspect the cover."),
    ]
    assert [slot["text"] for slot in prose_slots(document)] == ["Remove the pump.", "Inspect the cover."]


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("position", ["before", "between", "after"])
def test_html_table_cell_preserves_png_position_without_rewriting_cell_text(
    capture_fixture, provider, position,
):
    import json
    from io import BytesIO

    from PIL import Image
    from autodata_ingestion.article_document import validate_ordered_document
    from autodata_ingestion.procedure_normalize import normalize_procedure_article
    from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    from autodata_ingestion.source_article_capture import capture_source_article

    png = BytesIO()
    Image.new("RGB", (20, 20), "green").save(png, format="PNG")
    image = '<img src="/diagram" alt="Alignment marks">'
    before, after = "Before turning.", "After fitting."
    cell_markup = {
        "before": image + before + " " + after,
        "between": before + image + after,
        "after": before + " " + after + image,
    }[position]
    markup = f"<p>Remove the pump.</p><table><tr><td>{cell_markup}</td></tr></table>"
    body, media = markup.encode(), "text/html"
    if provider == "banktwo":
        body = json.dumps({"_embedded": {"data": {"article": {"content": markup}}}}).encode()
        media = "application/hal+json"
    fixture = capture_fixture
    fixture.body(provider, body, media, assets=["figure"],
                 asset_bindings=[{"source_url": "/diagram", "resource_ref": "figure"}])
    fixture.body(provider, png.getvalue(), "image/png", ref="figure", kind="asset")
    context = fixture.context(provider)
    options = {"registry": fixture.registry, "object_store": fixture.objects, "keep_bound_pdf_iframes": True}
    legacy = capture_source_article(context, **options)
    corrected = capture_source_article(context, keep_html_table_image_order=True, **options)
    historic_cell = legacy.source_document["blocks"][1]["rows"][0][0]
    cell = corrected.source_document["blocks"][1]["rows"][0][0]
    assert historic_cell["text"] == f"{before} {after}"
    assert historic_cell["images"][0]["alt"] == "Alignment marks"
    assert legacy.projection_version == "source-projection-v2"
    assert corrected.source_fingerprint == legacy.source_fingerprint
    assert corrected.resource_manifest == legacy.resource_manifest
    assert corrected.evidence_manifest == legacy.evidence_manifest
    assert corrected.source_body.split() == legacy.source_body.split()
    assert corrected.source_steps == legacy.source_steps
    assert corrected.projection_status == "readable"
    assert not validate_ordered_document(corrected.source_document, strict=True)
    assert "/diagram" not in repr(corrected.source_document)

    if position == "after":
        assert corrected.projection_version == legacy.projection_version
        assert corrected.source_document == legacy.source_document
    else:
        assert corrected.projection_version == "source-projection-v9"
        assert cell["protected_text"] is True
        assert [(block["type"], block.get("text")) for block in cell["blocks"]] == (
            [("image", None), ("paragraph", f"{before} {after}")]
            if position == "before" else [("paragraph", before), ("image", None), ("paragraph", after)]
        )
        normalized = normalize_procedure_article({
            "normalized_document": corrected.source_document,
            "body": corrected.source_body, "steps": corrected.source_steps,
        })["normalized_document"]
        assert normalized == corrected.source_document
        slots = prose_slots(normalized, include_cell_blocks=True)
        assert [slot["text"] for slot in slots] == ["Remove the pump."]
        response = {
            "introduction": "This procedure covers pump removal.",
            "replacements": [{**slots[0], "action": "rewrite", "text": "Take off the pump.", "reason": ""}],
        }
        canonical = render_auto(normalized, response)
        assert validate_auto(normalized, canonical, response=response).passed
        assert canonical["blocks"][2]["rows"][0][0] == cell

    [old_image], [new_image] = legacy.source_images, corrected.source_images
    for field in ("asset_id", "image_id", "storage_key", "content_sha256", "evidence_ids", "status", "media_type"):
        assert new_image[field] == old_image[field]
    assert fixture.objects.data[new_image["storage_key"]] == (png.getvalue(), "image/png")
    assert fixture.resource_calls(provider, "figure") == 2


@pytest.mark.parametrize("provider,available", [
    ("bankone", True), ("banktwo", True), ("banktwo", False),
])
def test_authored_table_figure_caption_and_following_instruction_are_distinct(capture_fixture, provider, available):
    import json
    from io import BytesIO

    from PIL import Image
    from autodata_ingestion.article_document import validate_ordered_document
    from autodata_ingestion.article_lifecycle_types import HTML_FIGURE_CAPTION_LAYOUT
    from autodata_ingestion.procedure_normalize import normalize_procedure_article
    from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    from autodata_ingestion.source_article_capture import capture_source_article

    markup = (
        '<p>Remove the pump.</p><table><tr><td>Check the reference mark.'
        '<figure><img src="/fixture/diagram" alt="Alignment marks">'
        '<figcaption>Alignment <em>witness</em> marks<script>Hidden script</script></figcaption>'
        '</figure>Keep the shim seated.</td></tr></table>'
    )
    raw, media = markup.encode(), "text/html"
    if provider == "banktwo":
        raw = json.dumps({"_embedded": {"data": {"article": {"content": markup}}}}).encode()
        media = "application/hal+json"
    capture_fixture.body(provider, raw, media, assets=["figure"], asset_bindings=[
        {"source_url": "/fixture/diagram", "resource_ref": "figure"},
    ])
    if available:
        raster = BytesIO()
        Image.new("RGB", (24, 24), "green").save(raster, format="PNG")
        capture_fixture.body(provider, raster.getvalue(), "image/png", ref="figure", kind="asset")

    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects,
                   keep_bound_pdf_iframes=True, keep_html_table_image_order=True)
    previous = capture_source_article(context, **options)
    previous_cell = previous.source_document["blocks"][1]["rows"][0][0]
    assert previous_cell["blocks"][-1]["text"] == "Alignment witness marksKeep the shim seated."

    guarded = capture_source_article(
        replace(context, legacy_published_html_figure_body=sha256(raw).hexdigest()),
        keep_html_figure_captions=True, **options,
    )
    assert guarded.source_document == previous.source_document
    assert guarded.source_fingerprint == previous.source_fingerprint

    captured = capture_source_article(context, keep_html_figure_captions=True, **options)
    assert captured.source_body.splitlines() == [
        "Remove the pump.", "Check the reference mark.", "Alignment witness marks", "Keep the shim seated.",
    ]
    assert captured.evidence_manifest == previous.evidence_manifest
    assert captured.resource_manifest[0]["html_figure_caption_layout"] == HTML_FIGURE_CAPTION_LAYOUT
    assert captured.resource_manifest[1:] == previous.resource_manifest[1:]
    assert captured.projection_status == ("readable" if available else "partial")
    assert not validate_ordered_document(captured.source_document, strict=True)
    cell = captured.source_document["blocks"][1]["rows"][0][0]
    blocks = cell["blocks"]
    assert [(block["type"], block.get("text")) for block in blocks] == [
        ("paragraph", "Check the reference mark."), ("image", None),
        *([] if available else [("paragraph", "Alignment witness marks")]),
        ("paragraph", "Keep the shim seated."),
    ]
    assert blocks[1].get("caption") == ("Alignment witness marks" if available else None)
    assert blocks[1]["image_id"] == previous.source_images[0]["image_id"]
    assert "Hidden script" not in repr(captured.source_document) and "/fixture/diagram" not in repr(captured.source_document)
    if available:
        assert capture_fixture.objects.data[blocks[1]["storage_key"]] == (raster.getvalue(), "image/png")

    normalized = normalize_procedure_article({
        "normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps,
    })["normalized_document"]
    [slot] = prose_slots(normalized, include_cell_blocks=True)
    assert slot["text"] == "Remove the pump."
    response = {"introduction": "This procedure covers pump removal.", "replacements": [
        {**slot, "action": "rewrite", "text": "Take off the pump.", "reason": ""},
    ]}
    canonical = render_auto(normalized, response)
    assert validate_auto(normalized, canonical, response=response).passed
    assert canonical["blocks"][2]["rows"][0][0] == cell


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_authored_html_table_caption_stays_with_table_through_rewrite(capture_fixture, provider):
    import json

    from autodata_ingestion.article_document import validate_ordered_document
    from autodata_ingestion.article_lifecycle_types import HTML_TABLE_CAPTION_LAYOUT
    from autodata_ingestion.procedure_normalize import normalize_procedure_article
    from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    from autodata_ingestion.source_article_capture import capture_source_article

    markup = (
        '<p>Remove the pump.</p><table>'
        '<caption>Service <em>data</em><br>Front flange<script>Hidden script</script></caption>'
        '<tr><th>Fastener</th><th>Torque</th></tr><tr><td>Cover bolt</td><td>18 Nm</td></tr></table>'
    )
    raw, media = markup.encode(), "text/html"
    if provider == "banktwo":
        raw = json.dumps({"_embedded": {"data": {"article": {"content": markup}}}}).encode()
        media = "application/hal+json"
    capture_fixture.body(provider, raw, media)
    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects)

    previous = capture_source_article(context, **options)
    assert [(block["type"], block.get("text")) for block in previous.source_document["blocks"]] == [
        ("paragraph", "Remove the pump."), ("paragraph", "Service data"),
        ("paragraph", "Front flange"), ("table", None),
    ]
    assert not previous.source_document["blocks"][-1].get("label")
    guarded = capture_source_article(
        replace(context, legacy_published_html_table_caption_body=sha256(raw).hexdigest()),
        keep_html_table_captions=True, **options,
    )
    assert guarded.source_document == previous.source_document
    assert guarded.source_fingerprint == previous.source_fingerprint

    captured = capture_source_article(context, keep_html_table_captions=True, **options)
    assert captured.projection_version == "source-projection-v5"
    assert captured.body_source_snapshot_id == previous.body_source_snapshot_id
    assert captured.evidence_manifest == previous.evidence_manifest
    [body] = captured.resource_manifest
    assert body["html_table_caption_layout"] == HTML_TABLE_CAPTION_LAYOUT
    [paragraph, table] = captured.source_document["blocks"]
    assert paragraph["text"] == "Remove the pump."
    assert table["label"] == "Service data Front flange"
    assert table["rows"] == previous.source_document["blocks"][-1]["rows"]
    assert captured.source_body.splitlines() == [
        "Remove the pump.", "Service data Front flange", "Fastener", "Torque", "Cover bolt", "18 Nm",
    ]
    assert not validate_ordered_document(captured.source_document, strict=True)

    normalized = normalize_procedure_article({
        "normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps,
    }, resource_manifest=captured.resource_manifest)["normalized_document"]
    [slot] = prose_slots(normalized, include_cell_blocks=True)
    assert slot["text"] == "Remove the pump."
    response = {"introduction": "This procedure covers pump removal.", "replacements": [
        {**slot, "action": "rewrite", "text": "Take off the pump.", "reason": ""},
    ]}
    canonical = render_auto(normalized, response)
    assert validate_auto(normalized, canonical, response=response).passed
    assert canonical["blocks"][2] == {**table, "source_order": 3}


def test_bound_pdf_embed_keeps_table_cell_order_and_refuses_unbound_markup(capture_fixture):
    from io import BytesIO

    from PIL import Image
    from reportlab.pdfgen import canvas
    from autodata_ingestion.article_document import validate_ordered_document
    from autodata_ingestion.procedure_rewrite_full import prose_slots
    from autodata_ingestion.source_article_capture import capture_source_article

    pdf_bytes = BytesIO()
    pdf = canvas.Canvas(pdf_bytes)
    pdf.drawString(72, 718, "Check the drive seal.")
    pdf.save()
    png = BytesIO()
    Image.new("RGB", (20, 20), "green").save(png, format="PNG")
    fixture = capture_fixture
    fixture.body("bankone", (
        b'<p>Inspect the housing.</p><table><tr><td>Drive reference'
        b'<img data-resource-ref="alignment" alt="Alignment marks">'
        b'<iframe src="/docs/drive"></iframe>Finish the inspection.</td><td>Torque reference'
        b'<object type="application/pdf" data="/docs/drive"></object></td></tr></table>'
        b'<iframe src="/docs/unbound"><p>Hidden fallback text</p></iframe>'
        b'<p>Install the cover.</p>'
    ), assets=["drive", "alignment"], asset_bindings=[{"source_url": "/docs/drive", "resource_ref": "drive"}])
    fixture.body("bankone", pdf_bytes.getvalue(), "application/pdf", ref="drive", kind="asset")
    fixture.body("bankone", png.getvalue(), "image/png", ref="alignment", kind="asset")
    context = fixture.context("bankone")
    options = {"registry": fixture.registry, "object_store": fixture.objects, "keep_bound_pdf_iframes": True}
    historical = capture_source_article(context, **options)
    captured = capture_source_article(context, keep_html_table_image_order=True, **options)
    assert captured.projection_version == "source-projection-v6"
    assert captured.source_document == historical.source_document
    assert captured.source_fingerprint == historical.source_fingerprint
    assert captured.projection_status == "readable"
    assert not validate_ordered_document(captured.source_document, strict=True)
    table = captured.source_document["blocks"][1]
    left, right = table["rows"][0]
    assert [node.get("text") or node.get("alt") for node in left["blocks"]] == [
        "Drive reference", "Alignment marks", "Check the drive seal.", "Finish the inspection.",
    ]
    assert [node["text"] for node in right["blocks"]] == ["Torque reference", "Check the drive seal."]
    assert [slot["text"] for slot in prose_slots(captured.source_document, include_cell_blocks=True)].count(
        "Check the drive seal.",
    ) == 2
    assert "Hidden fallback text" not in captured.source_body
    assert "/docs/" not in repr(captured.source_document)
    assert fixture.resource_calls("bankone", "drive") == 2
    assert fixture.resource_calls("bankone", "alignment") == 2
    assert fixture.resource_calls("bankone", "unbound") == 0


@pytest.mark.parametrize(("mime", "payload", "reason"), [
    ("image/png", b"not permitted", "UNSUPPORTED_DOCUMENT_MEDIA"),
    ("application/pdf", b"not a PDF", "DOCUMENT_EXTRACTION_UNAVAILABLE"),
    ("application/pdf", None, "DOCUMENT_EXTRACTION_UNAVAILABLE"),
])
def test_bound_embed_validation_keeps_surrounding_procedure(capture_fixture, monkeypatch, mime, payload, reason):
    from autodata_ingestion.source_article_capture import capture_source_article

    if payload is None:
        from io import BytesIO

        from reportlab.pdfgen import canvas

        from autodata_ingestion import source_adapters
        from autodata_ingestion.ocr import OCRUnavailable

        stream = BytesIO()
        pdf = canvas.Canvas(stream)
        pdf.drawString(72, 718, "Readable first page.")
        pdf.showPage()
        pdf.line(72, 718, 200, 700)
        pdf.showPage()
        pdf.save()
        payload = stream.getvalue()

        def unavailable(_digest, _payload, native_pages):
            assert native_pages == {1}
            raise OCRUnavailable("Fixture second page could not be recognized")

        monkeypatch.setattr(source_adapters, "extract_scanned_pdf_text", unavailable)

    fixture = capture_fixture
    fixture.body("banktwo", (
        b'<p>Remove the cover.</p><embed type="application/pdf" src="/docs/drive">'
        b'<p>Install the cover.</p>'
    ), assets=["drive"], asset_bindings=[{"source_url": "/docs/drive", "resource_ref": "drive"}])
    fixture.body("banktwo", payload, mime, ref="drive", kind="asset")
    captured = capture_source_article(
        fixture.context("banktwo"), registry=fixture.registry, object_store=fixture.objects,
        keep_bound_pdf_iframes=True,
    )
    assert captured.projection_version == "source-projection-v6"
    assert captured.projection_status == "partial"
    before, placeholder, after = captured.source_document["blocks"]
    assert before["text"] == "Remove the cover." and after["text"] == "Install the cover."
    assert placeholder["type"] == "callout" and placeholder["label"] == "Embedded document unavailable"
    assert captured.source_images == []
    assert captured.resource_manifest[-1] == {
        "role": "document_asset", "opaque_ref": "drive", "failure_code": reason,
    }
    if mime == "application/pdf":
        [retained] = [entry for entry in captured.resources if entry["role"] == "document_asset"]
        assert captured.resource_manifest[-2]["sha256"] == sha256(payload).hexdigest()
        assert fixture.objects.data[retained["object_key"]] == (payload, mime)
