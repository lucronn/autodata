from io import BytesIO
import subprocess
import base64
import pytest
from PIL import Image

from autodata_ingestion.svg_rasterization import (
    rasterize_svg, SVGUnavailable, _validated_dimensions, MAX_INPUT_BYTES,
)

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20" fill="red"/></svg>'


def test_actual_raster_has_original_aspect_and_pixels():
    png = rasterize_svg(SVG)
    with Image.open(BytesIO(png)) as image:
        assert image.format == "PNG"
        assert image.size == (40, 20)
        assert image.convert("RGB").getpixel((10, 10)) == (255, 0, 0)
    assert rasterize_svg(SVG) == png


def test_large_viewbox_is_bounded_without_changing_aspect():
    svg = SVG.replace(b'width="40" height="20"', b'viewBox="0 0 10000 5000"', 1)
    png = rasterize_svg(svg)
    with Image.open(BytesIO(png)) as image:
        assert image.size == (4096, 2048)


@pytest.mark.parametrize("content", [
    '<image href="http://127.0.0.1:9876/private"/>',
    '<image href="file:///etc/passwd"/>',
    '<image href="data:image/svg+xml;base64,AA=="/>',
    '<use href="//remote.invalid/image#x"/>',
    '<style>@import "https://remote.invalid/a.css";</style>',
    '<style>@im\\70ort "https://remote.invalid/a.css";</style>',
    '<rect style="fill:u\\72l(https://remote.invalid/a)"/>',
    '<rect style="fill:url(\'file:///etc/passwd\')"/>',
    '<g xml:base="file:///etc/"/>',
    '<script>fetch("https://remote.invalid/")</script>',
    '<foreignObject><body xmlns="http://www.w3.org/1999/xhtml">x</body></foreignObject>',
    '<rect onclick="alert(1)"/>',
])
def test_hostile_references_denied_inside_bounded_child(content):
    with pytest.raises(SVGUnavailable):
        rasterize_svg(('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'+content+'</svg>').encode())


@pytest.mark.parametrize("payload", [
    b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg>&x;</svg>',
    b'<!DOCTYPE svg><svg/>', b'<svg', b'<html/>',
    b'<svg width="NaN" height="20"/>',
    b'<svg viewBox="0 0 inf 20"/>',
    b'<svg width="0" height="20"/>',
    b'<svg>'+b'<g>'*70+b'</g>'*70+b'</svg>',
    b'x'*(MAX_INPUT_BYTES+1),
])
def test_invalid_and_unbounded_input_rejected(payload):
    with pytest.raises(SVGUnavailable):
        rasterize_svg(payload)


@pytest.mark.parametrize("attribute", ["href", "xlink:href"])
def test_navigation_links_keep_their_transformed_drawing(attribute):
    href = f' {attribute}="/fixture/related-article?region=US"'.encode()
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
        b' viewBox="-0.5 -0.5 40 20"><a transform="translate(7,2)"' + href
        + b'><rect width="20" height="14" style="fill:#155ca0"/></a></svg>'
    )
    png = rasterize_svg(svg)
    assert png == rasterize_svg(svg.replace(href, b""))
    with Image.open(BytesIO(png)) as image:
        assert image.size == (40, 20)
        assert image.convert("RGB").getpixel((12, 8)) == (21, 92, 160)


def test_navigation_wrapper_keeps_visual_source_references_checked():
    svg = (b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
           b'<a href="/fixture/related"><image href="/fixture/required-graphic"/></a></svg>')
    with pytest.raises(SVGUnavailable, match="^SVG_EXTERNAL_REFERENCE$"):
        rasterize_svg(svg)


def test_internal_fragment_paint_and_use_are_supported():
    svg = b'''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><defs><rect id="r" width="10" height="10"/><linearGradient id="g"><stop stop-color="blue"/></linearGradient></defs><use href="#r" fill="url(#g)"/></svg>'''
    assert rasterize_svg(svg).startswith(b'\x89PNG\r\n\x1a\n')


def test_runtime_timeout_and_failure_are_redacted(monkeypatch):
    def timeout(*args, **kwargs):
        assert kwargs["env"] == {"LANG": "C.UTF-8"}
        assert kwargs["stderr"] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired("redacted", 1)
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(SVGUnavailable, match="^SVG_RENDER_TIMEOUT$"):
        rasterize_svg(SVG)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 1, b"private source"))
    with pytest.raises(SVGUnavailable, match="^SVG_RENDER_FAILED$"):
        rasterize_svg(SVG)


def test_invalid_renderer_output_cannot_be_published(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, b"not png"))
    with pytest.raises(SVGUnavailable, match="^SVG_RENDER_FAILED$"):
        rasterize_svg(SVG)


def test_actual_child_wall_deadline_is_enforced():
    with pytest.raises(SVGUnavailable, match="^SVG_RENDER_TIMEOUT$"):
        rasterize_svg(SVG, timeout=0.00001)


def test_complexity_and_square_output_caps():
    with pytest.raises(SVGUnavailable, match="SVG_COMPLEXITY_LIMIT"):
        _validated_dimensions(b'<svg width="20" height="20">'+b'<g/>'*20_001+b'</svg>')
    width, height = _validated_dimensions(b'<svg viewBox="0 0 10000 10000"/>')
    assert (width, height) == (4000, 4000)


@pytest.mark.parametrize("format,media", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_embedded_raster_and_inert_standard_doctype(format, media):
    image = Image.new("RGB", (40, 20), "red")
    buffer = BytesIO()
    image.save(buffer, format=format)
    uri = "data:"+media+";base64,"+base64.b64encode(buffer.getvalue()).decode()
    svg = ('<?xml version="1.0"?>\n<!-- Generator: fixture -->\n'
           '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">'
           '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
           '<image width="40" height="20" href="'+uri+'"/></svg>').encode()
    from autodata_ingestion.svg_rasterization import _prepare_svg
    normalized, _, _, resources = _prepare_svg(svg)
    assert b'DOCTYPE' not in normalized
    assert list(resources.values()) == [buffer.getvalue()]
    png = rasterize_svg(svg)
    with Image.open(BytesIO(png)) as decoded:
        red, green, blue = decoded.convert("RGB").getpixel((10, 10))
        assert red > 240 and green < 10 and blue < 10


def test_legacy_w3c_svg_11_doctype_renders_without_loading_the_declaration():
    doctype = (
        b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
        b'"http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg11.dtd"'
    )
    assert rasterize_svg(doctype + b">" + SVG) == rasterize_svg(SVG)
    with pytest.raises(SVGUnavailable):
        rasterize_svg(doctype + b" [ ]>" + SVG)


@pytest.mark.parametrize("prefix", [
    '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" []>',
    '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" [<!ENTITY test "red">]>',
    '<!DOCTYPE svg SYSTEM "file:///etc/passwd">',
    '<!DOCTYPE svg PUBLIC "other" "https://unrecognized.invalid/other.dtd">',
])
def test_unrecognized_and_internal_doctypes_stay_denied(prefix):
    with pytest.raises(SVGUnavailable):
        rasterize_svg(prefix.encode()+SVG)


def test_embedded_data_integrity_and_limits():
    from autodata_ingestion.svg_rasterization import _embedded_raster
    for uri in ['data:image/png;base64,!!!!', 'data:image/png;base64,AA==', 'data:text/plain;base64,AA==']:
        with pytest.raises(SVGUnavailable):
            _embedded_raster(uri)
    buf = BytesIO()
    Image.new("RGB", (40, 20)).save(buf, format="PNG")
    with pytest.raises(SVGUnavailable, match="INVALID_SVG_EMBEDDED_IMAGE"):
        _embedded_raster('data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode())
    buf = BytesIO()
    Image.new("1", (3000, 3000)).save(buf, format="PNG")
    with pytest.raises(SVGUnavailable, match="SVG_EMBEDDED_IMAGE_LIMIT"):
        _embedded_raster('data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode())


def test_runtime_fetcher_has_only_exact_memory_allowlist():
    from autodata_ingestion.svg_rasterization import _embedded_fetcher
    fetch = _embedded_fetcher({'data:image/png;base64,approved': b'validated bytes'})
    assert fetch('data:image/png;base64,approved', 'image/*') == b'validated bytes'
    for uri in ['https://remote.invalid', 'file:///etc/passwd', 'data:image/png;base64,other']:
        with pytest.raises(SVGUnavailable, match="SVG_EXTERNAL_REFERENCE"):
            fetch(uri, 'image/*')
    with pytest.raises(SVGUnavailable):
        fetch('data:image/png;base64,approved', 'image/svg+xml')


def test_parent_does_not_parse_or_decode_source(monkeypatch):
    import autodata_ingestion.svg_rasterization as module
    def forbidden(*args, **kwargs):
        pytest.fail("parent parsed source before entering bounded child")
    monkeypatch.setattr(module, "_prepare_svg", forbidden)
    monkeypatch.setattr(module, "_validated_dimensions", forbidden)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 1, b"SVG_RENDER_UNAVAILABLE"))
    with pytest.raises(SVGUnavailable, match="^SVG_RENDER_UNAVAILABLE$"):
        rasterize_svg(SVG)
