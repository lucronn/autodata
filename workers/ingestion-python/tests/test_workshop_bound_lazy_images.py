"""Resolve lazy HTML images through the connector's exact asset bindings."""

from base64 import b64encode
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json

from PIL import Image
import pytest

from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


_LAYOUT_KEY = "html_bound_image_layout"
_LAYOUT = "html-bound-image-v1"
_FIGURE = "/fixture/alignment.png"
_COMMA_URL = "/fixture/alignment,full.png"
_LARGE = "/fixture/alignment-large.png"
_OTHER = "/fixture/other.png"
_PLACEHOLDER = "/fixture/loading.png"
_BEFORE = "Remove the access cover."
_CAPTION = "Witness marks"
_ALT = "Alignment marks"
_AFTER = "Inspect the mount."


def _figure(attributes, *, caption=_CAPTION):
    return f'<figure><img {attributes} alt="{_ALT}"><figcaption>{caption}</figcaption></figure>'


def _install(fixture, provider, encoding, markup, bindings):
    html = f"<p>{_BEFORE}</p>{markup}<p>{_AFTER}</p>"
    raw, mime = html.encode(), "text/html"
    if encoding == "hal":
        raw = json.dumps({"_embedded": {"data": {"article": {"content": html}}}}).encode()
        mime = "application/hal+json"
    refs = sorted(set(bindings.values()))
    fixture.body(provider, raw, mime, assets=refs, asset_bindings=[
        {"source_url": url, "resource_ref": ref} for url, ref in bindings.items()
    ])
    images = {}
    for ref in refs:
        image = BytesIO()
        Image.new("RGB", (24, 16), "green" if ref == "figure" else "blue").save(image, format="PNG")
        images[ref] = image.getvalue()
        fixture.body(provider, images[ref], "image/png", ref=ref, kind="asset")
    return raw, mime, images


def _capture(fixture, context, *, enabled=True):
    return capture_source_article(
        context, registry=fixture.registry, object_store=fixture.objects,
        keep_bound_html_images=enabled, keep_html_figure_captions=True, keep_html_flow_figure_captions=True,
        keep_html_multiline_figure_captions=True,
    )


def _assert_figure_at_authored_position(fixture, captured, payload, *, caption=_CAPTION):
    assert captured.projection_status == "readable"
    assert not validate_ordered_document(captured.source_document, strict=True)
    blocks = captured.source_document["blocks"]
    assert [(block["type"], block.get("text"), block.get("caption")) for block in blocks[:3]] == [
        ("paragraph", _BEFORE, None), ("image", None, caption), ("paragraph", _AFTER, None),
    ]
    figure = blocks[1]
    assert figure["alt"] == _ALT
    [image] = [image for image in captured.source_images if image["image_id"] == figure["image_id"]]
    assert image["status"] == "available"
    assert image["content_sha256"] == sha256(payload).hexdigest()
    assert fixture.objects.data[figure["storage_key"]] == (payload, "image/png")
    assert "/fixture/" not in repr(captured.source_document)


def _assert_unchanged(before, after):
    assert before.source_document == after.source_document
    assert before.source_images == after.source_images
    assert before.source_fingerprint == after.source_fingerprint
    assert before.projection_version == after.projection_version
    assert before.resource_manifest == after.resource_manifest
    assert _LAYOUT_KEY not in after.resources[0]
    assert _LAYOUT_KEY not in after.resource_manifest[0]


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("encoding", ["html", "hal"])
@pytest.mark.parametrize("attributes", [
    pytest.param(f'data-src="{_FIGURE}" loading="lazy"', id="data-src"),
    pytest.param(f'src="{_PLACEHOLDER}" data-src="{_FIGURE}"', id="placeholder-src"),
    pytest.param(f'srcset="{_COMMA_URL} 1x, {_LARGE} 2x"', id="comma-url-and-densities"),
    pytest.param(f'data-srcset="{_FIGURE} 320w, {_LARGE} 640w"', id="lazy-widths"),
])
def test_lazy_html_figure_preserves_authored_position_and_connector_bytes(capture_fixture, provider, encoding, attributes):
    raw, mime, images = _install(capture_fixture, provider, encoding, _figure(attributes), {
        _FIGURE: "figure", _COMMA_URL: "figure", _LARGE: "figure",
    })
    context = capture_fixture.context(provider)
    prior = _capture(capture_fixture, context, enabled=False)
    assert _LAYOUT_KEY not in prior.resource_manifest[0]
    assert _LAYOUT_KEY not in prior.resources[0]
    assert not any(
        block["type"] == "image" and block.get("caption") == _CAPTION
        for block in prior.source_document["blocks"][:2]
    )

    captured = _capture(capture_fixture, context)
    assert capture_fixture.resource_calls(provider, "figure") == 2
    _assert_figure_at_authored_position(capture_fixture, captured, images["figure"])
    assert len(captured.source_document["blocks"]) == 3
    assert len(captured.source_images) == 1
    assert captured.source_fingerprint != prior.source_fingerprint
    assert captured.body_source_snapshot_id == prior.body_source_snapshot_id
    assert captured.resources[0][_LAYOUT_KEY] == _LAYOUT
    assert captured.resource_manifest[0][_LAYOUT_KEY] == _LAYOUT
    assert captured.resources[0]["sha256"] == sha256(raw).hexdigest()
    assert capture_fixture.objects.data[captured.resources[0]["object_key"]] == (raw, mime)


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("encoding", ["html", "hal"])
def test_conventional_bound_src_keeps_capture_identity(capture_fixture, provider, encoding):
    _, _, images = _install(capture_fixture, provider, encoding, _figure(f'src="{_FIGURE}"'), {_FIGURE: "figure"})
    context = capture_fixture.context(provider)
    previous = _capture(capture_fixture, context, enabled=False)
    captured = _capture(capture_fixture, context)
    _assert_unchanged(previous, captured)
    _assert_figure_at_authored_position(capture_fixture, captured, images["figure"])


@pytest.mark.parametrize("provider,encoding", [("bankone", "html"), ("banktwo", "hal")])
@pytest.mark.parametrize("fallback_first", [False, True])
def test_noscript_mirror_does_not_duplicate_the_captioned_lazy_figure(capture_fixture, provider, encoding, fallback_first):
    active = f'<img data-src="{_FIGURE}" alt="{_ALT}">'
    fallback = f'<noscript><img src="{_FIGURE}" alt="{_ALT}"></noscript>'
    contents = fallback + active if fallback_first else active + fallback
    markup = f"<figure>{contents}<figcaption>{_CAPTION}</figcaption></figure>"
    raw, mime, images = _install(capture_fixture, provider, encoding, markup, {_FIGURE: "figure"})
    captured = _capture(capture_fixture, capture_fixture.context(provider))

    _assert_figure_at_authored_position(capture_fixture, captured, images["figure"])
    assert len(captured.source_document["blocks"]) == 3
    assert len(captured.source_images) == capture_fixture.resource_calls(provider, "figure") == 1
    assert captured.resource_manifest[0][_LAYOUT_KEY] == _LAYOUT
    assert capture_fixture.objects.data[captured.resources[0]["object_key"]] == (raw, mime)


def test_sole_noscript_image_keeps_the_legacy_projection(capture_fixture):
    markup = _figure(f'src="{_FIGURE}"').replace("<img", "<noscript><img").replace(
        "<figcaption>", "</noscript><figcaption>", 1,
    )
    _, _, images = _install(capture_fixture, "bankone", "html", markup, {_FIGURE: "figure"})
    context = capture_fixture.context("bankone")
    before = _capture(capture_fixture, context, enabled=False)
    after = _capture(capture_fixture, context)
    _assert_unchanged(before, after)
    _assert_figure_at_authored_position(capture_fixture, after, images["figure"])


@pytest.mark.parametrize("visible_alt", [None, "Visible timing marks"])
def test_mirrored_img_supplies_alt_only_when_the_visible_img_has_no_name(capture_fixture, visible_alt):
    visible = f'data-src="{_FIGURE}"' + (f' alt="{visible_alt}"' if visible_alt else '')
    markup = (
        f'<figure><img {visible}><noscript><img src="{_FIGURE}" alt="Fallback timing marks"></noscript>'
        f'<figcaption>{_CAPTION}</figcaption></figure>'
    )
    _install(capture_fixture, "banktwo", "hal", markup, {_FIGURE: "figure"})
    captured = _capture(capture_fixture, capture_fixture.context("banktwo"))
    [figure] = [block for block in captured.source_document["blocks"] if block["type"] == "image"]
    assert figure["alt"] == (visible_alt or "Fallback timing marks")
    assert figure["caption"] == _CAPTION


@pytest.mark.parametrize("provider,encoding", [("bankone", "html"), ("banktwo", "hal")])
def test_unrelated_noscript_figure_stays_in_the_article(capture_fixture, provider, encoding):
    png = BytesIO()
    Image.new("RGB", (20, 16), "blue").save(png, format="PNG")
    inline = b64encode(png.getvalue()).decode()
    markup = (
        f'<figure><img data-src="{_FIGURE}" alt="{_ALT}"><noscript><img src="{_FIGURE}"></noscript>'
        f'<figcaption>{_CAPTION}</figcaption></figure>'
        f'<figure><noscript><img src="data:image/png;base64,{inline}" alt="Seal"></noscript>'
        '<figcaption>Seal witness marks</figcaption></figure>'
    )
    _, _, images = _install(capture_fixture, provider, encoding, markup, {_FIGURE: "figure"})
    context = capture_fixture.context(provider)
    previous = _capture(capture_fixture, context, enabled=False)
    current = _capture(capture_fixture, context)
    blocks = current.source_document["blocks"]
    assert [block["type"] for block in blocks] == ["paragraph", "image", "image", "paragraph"]
    assert [block.get("caption") for block in blocks[1:3]] == [_CAPTION, "Seal witness marks"]
    assert blocks[2]["alt"] == "Seal"
    assert blocks[2]["image_id"] == previous.source_document["blocks"][2]["image_id"]
    for block, data in zip(blocks[1:3], (images["figure"], png.getvalue())):
        assert block["status"] == "available"
        assert capture_fixture.objects.data[block["storage_key"]] == (data, "image/png")


def test_inline_raster_src_keeps_precedence_over_a_connector_lazy_hint(capture_fixture):
    png = BytesIO()
    Image.new("RGB", (24, 16), "red").save(png, format="PNG")
    src = "data:image/png;base64," + b64encode(png.getvalue()).decode()
    markup = _figure(f'src="{src}" data-src="{_FIGURE}"')
    _install(capture_fixture, "bankone", "html", markup, {_FIGURE: "figure"})
    context = capture_fixture.context("bankone")
    before = _capture(capture_fixture, context, enabled=False)
    after = _capture(capture_fixture, context)
    _assert_unchanged(before, after)
    _assert_figure_at_authored_position(capture_fixture, after, png.getvalue())


@pytest.mark.parametrize("provider,encoding", [("bankone", "html"), ("banktwo", "hal")])
def test_lazy_image_refresh_attaches_multiline_caption_after_legacy_publication(capture_fixture, provider, encoding):
    markup = (
        f'<figure><img data-src="{_FIGURE}" alt="{_ALT}"><noscript><img src="{_FIGURE}"></noscript>'
        '<figcaption>Witness marks<br>Drive side</figcaption></figure>'
    )
    raw, _, images = _install(capture_fixture, provider, encoding, markup, {_FIGURE: "figure"})
    digest = sha256(raw).hexdigest()
    context = replace(
        capture_fixture.context(provider), legacy_published_html_flow_figure_body=digest,
        legacy_published_html_multiline_figure_body=digest,
    )
    previous = _capture(capture_fixture, context, enabled=False)
    current = _capture(capture_fixture, context)
    replay = _capture(capture_fixture, context)

    _assert_figure_at_authored_position(capture_fixture, current, images["figure"], caption="Witness marks Drive side")
    assert len(current.source_document["blocks"]) == 3
    assert current.body_source_snapshot_id == previous.body_source_snapshot_id == replay.body_source_snapshot_id
    assert _LAYOUT_KEY not in previous.resource_manifest[0]
    assert current.resource_manifest[0][_LAYOUT_KEY] == _LAYOUT
    assert current.source_fingerprint != previous.source_fingerprint
    assert replay.source_document == current.source_document
    assert replay.source_fingerprint == current.source_fingerprint
    assert replay.resource_manifest == current.resource_manifest


@pytest.mark.parametrize("attributes", [
    pytest.param(f'src="{_FIGURE}" data-src="{_OTHER}"', id="approved-direct-src"),
    pytest.param(f'src="{_PLACEHOLDER}" data-resource-ref="figure" data-srcset="{_OTHER} 1x"', id="explicit-resource-ref"),
])
def test_existing_image_binding_takes_precedence_over_lazy_hints(capture_fixture, attributes):
    _, _, images = _install(capture_fixture, "banktwo", "hal", _figure(attributes), {_FIGURE: "figure", _OTHER: "other"})
    context = capture_fixture.context("banktwo")
    previous = _capture(capture_fixture, context, enabled=False)
    captured = _capture(capture_fixture, context)
    _assert_unchanged(previous, captured)
    _assert_figure_at_authored_position(capture_fixture, captured, images["figure"])


@pytest.mark.parametrize("markup", [
    pytest.param(_figure('data-src="https://unbound.invalid/image.png"'), id="unbound-hint"),
    pytest.param(_figure(f'srcset="{_FIGURE} 1x, {_PLACEHOLDER} 2x"'), id="partly-unbound-srcset"),
    pytest.param(_figure(f'data-srcset="{_FIGURE} 1x, {_OTHER} 2x"'), id="conflicting-srcset"),
    pytest.param(_figure(f'data-src="{_FIGURE}" srcset="{_OTHER} 1x"'), id="conflicting-hint-fields"),
    pytest.param(_figure(f'data-src="{_FIGURE}" hidden'), id="hidden-img"),
    pytest.param(f'<div hidden>{_figure(f"data-src={_FIGURE!r}")}</div>', id="hidden-ancestor"),
    pytest.param(f'<template>{_figure(f"data-src={_FIGURE!r}")}</template>', id="template"),
    pytest.param(f'<noscript>{_figure(f"data-src={_FIGURE!r}")}</noscript>', id="noscript"),
])
def test_ineligible_lazy_image_hints_keep_the_legacy_projection(capture_fixture, markup):
    _install(capture_fixture, "bankone", "html", markup, {_FIGURE: "figure", _OTHER: "other"})
    context = capture_fixture.context("bankone")
    previous = _capture(capture_fixture, context, enabled=False)
    captured = _capture(capture_fixture, context)
    _assert_unchanged(previous, captured)
