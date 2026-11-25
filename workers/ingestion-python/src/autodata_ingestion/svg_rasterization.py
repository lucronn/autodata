"""Rasterize an intentionally bounded SVG subset; never expose executable SVG."""

from io import BytesIO
import base64
import math
import os
from pathlib import Path
import re
import subprocess
import sys

MAX_INPUT_BYTES = 2_000_000
MAX_OUTPUT_BYTES = 12 << 20
MAX_EDGE = 4096
MAX_PIXELS = 16_000_000
RASTERIZER_VERSION = "cairosvg-2.9.1-bounded-v1"
MAX_EMBEDDED_PIXELS = 8_000_000
_FAILURES = frozenset({
    "SVG_EXTERNAL_REFERENCE", "INVALID_SVG", "SVG_INPUT_LIMIT",
    "SVG_COMPLEXITY_LIMIT", "UNSUPPORTED_SVG_CONTENT", "INVALID_SVG_DIMENSIONS",
    "SVG_EMBEDDED_IMAGE_LIMIT", "INVALID_SVG_EMBEDDED_IMAGE",
    "SVG_RENDER_UNAVAILABLE", "SVG_RENDER_FAILED", "SVG_OUTPUT_LIMIT",
})
# Discard inert, recognized legacy declarations; never resolve a DTD.
_W3C_DOCTYPE = re.compile(
    r'''<!DOCTYPE\s+svg\s+PUBLIC\s+(["'])-//W3C//DTD SVG 1\.[01]//EN\1\s+(["'])https?://www\.w3\.org/(?:Graphics/SVG/1\.1/DTD/svg11\.dtd|TR/2001/REC-SVG-20010904/DTD/svg10\.dtd|TR/SVG/DTD/svg10\.dtd)\2\s*>'''
)


class SVGUnavailable(ValueError):
    """Stable failure; never includes source bytes, URLs or renderer errors."""


def _deny_fetch(*args, **kwargs):
    raise SVGUnavailable("SVG_EXTERNAL_REFERENCE")


def _css_references(value):
    import tinycss2

    def visit(tokens):
        for token in tokens:
            if token.type == "error":
                raise SVGUnavailable("INVALID_SVG")
            if token.type == "at-keyword" and token.value.lower() == "import":
                _deny_fetch()
            if token.type == "url":
                if not token.value.startswith("#"):
                    _deny_fetch()
            if token.type == "function":
                if token.lower_name == "url":
                    values = [x for x in token.arguments if x.type not in {"whitespace", "comment"}]
                    if len(values) != 1 or values[0].type != "string" or not values[0].value.startswith("#"):
                        _deny_fetch()
                else:
                    visit(token.arguments)
            if hasattr(token, "content"):
                visit(token.content)

    visit(tinycss2.parse_component_value_list(value))


def _prepare_svg(payload):
    from defusedxml import ElementTree

    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_INPUT_BYTES:
        raise SVGUnavailable("SVG_INPUT_LIMIT")
    try:
        text = payload.decode("utf-8-sig")
        if "<?xml-stylesheet" in text.lower():
            _deny_fetch()
        declaration = _W3C_DOCTYPE.search(text)
        if declaration:
            prefix = text[:declaration.start()]
            prolog = re.sub(r"<\?xml\s[^?]*\?>|<!--[\s\S]*?-->", "", prefix)
            if not prolog.strip():
                text = prefix + text[declaration.end():]
        root = ElementTree.fromstring(text, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        if root.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
            raise SVGUnavailable("INVALID_SVG")
        pending = [(root, 0)]
        count = 0
        embedded = {}
        embedded_pixels = 0
        while pending:
            node, depth = pending.pop()
            count += 1
            if depth > 64 or count > 20_000:
                raise SVGUnavailable("SVG_COMPLEXITY_LIMIT")
            tag = node.tag.rsplit("}", 1)[-1].lower()
            if tag in {"script", "foreignobject", "iframe", "audio", "video"}:
                raise SVGUnavailable("UNSUPPORTED_SVG_CONTENT")
            if node.tag.startswith("{") and not node.tag.startswith("{http://www.w3.org/2000/svg}"):
                raise SVGUnavailable("UNSUPPORTED_SVG_CONTENT")
            for name, value in list(node.attrib.items()):
                local = name.rsplit("}", 1)[-1].lower()
                if local.startswith("on") or name == "{http://www.w3.org/XML/1998/namespace}base":
                    raise SVGUnavailable("UNSUPPORTED_SVG_CONTENT")
                if local in {"href", "src"} and not value.startswith("#"):
                    if tag == "a" and name in {"href", "{http://www.w3.org/1999/xlink}href"}:
                        # A raster has no navigation. Keep the wrapper and its drawing
                        # attributes while removing the link from the renderer's input.
                        del node.attrib[name]
                        continue
                    if tag != "image" or not value.startswith("data:"):
                        _deny_fetch()
                    value, data, pixels = _embedded_raster(value)
                    if value not in embedded:
                        embedded_pixels += pixels
                        if embedded_pixels > MAX_EMBEDDED_PIXELS:
                            raise SVGUnavailable("SVG_EMBEDDED_IMAGE_LIMIT")
                    embedded[value] = data
                    node.set(name, value)
                    continue
                if local == "style" or any(x in value.lower() for x in ("url", "\\", "@")):
                    _css_references(value)
            if tag == "style":
                _css_references("".join(node.itertext()))
            pending.extend((child, depth + 1) for child in node)
        viewbox = root.get("viewBox", "").replace(",", " ").split()
        if len(viewbox) == 4:
            _, _, width, height = map(float, viewbox)
        else:
            def pixels(name):
                value = root.get(name, "")
                if not re.fullmatch(r"\s*(?:\d+(?:\.\d*)?|\.\d+)(?:px)?\s*", value):
                    raise SVGUnavailable("INVALID_SVG_DIMENSIONS")
                return float(value.strip().removesuffix("px"))
            width, height = pixels("width"), pixels("height")
        if not all(math.isfinite(x) and 0 < x <= 100_000 for x in (width, height)):
            raise SVGUnavailable("INVALID_SVG_DIMENSIONS")
        scale = min(1, MAX_EDGE / width, MAX_EDGE / height, math.sqrt(MAX_PIXELS / (width * height)))
        from xml.etree.ElementTree import tostring
        return tostring(root, encoding="utf-8"), max(1, int(width * scale)), max(1, int(height * scale)), embedded
    except SVGUnavailable:
        raise
    except Exception:
        raise SVGUnavailable("INVALID_SVG") from None


def _embedded_raster(value):
    from PIL import Image

    try:
        header, encoded = value.split(",", 1)
        if header not in {"data:image/png;base64", "data:image/jpeg;base64"}:
            _deny_fetch()
        encoded = re.sub(r"[ \t\r\n]", "", encoded)
        data = base64.b64decode(encoded, validate=True)
        if not data or len(data) > MAX_INPUT_BYTES:
            raise SVGUnavailable("SVG_EMBEDDED_IMAGE_LIMIT")
        with Image.open(BytesIO(data)) as image:
            expected = "PNG" if header == "data:image/png;base64" else "JPEG"
            pixels = image.width * image.height
            if pixels > MAX_EMBEDDED_PIXELS or max(image.size) > 8192:
                raise SVGUnavailable("SVG_EMBEDDED_IMAGE_LIMIT")
            if image.format != expected or getattr(image, "is_animated", False):
                raise SVGUnavailable("INVALID_SVG_EMBEDDED_IMAGE")
            image.load()
        return header + "," + base64.b64encode(data).decode("ascii"), data, pixels
    except SVGUnavailable:
        raise
    except Exception:
        raise SVGUnavailable("INVALID_SVG_EMBEDDED_IMAGE") from None


def _validated_dimensions(payload):
    _, width, height, _ = _prepare_svg(payload)
    return width, height


def _embedded_fetcher(embedded):
    def fetch(url, resource_type):
        if url not in embedded or resource_type != "image/*":
            _deny_fetch()
        return embedded[url]
    return fetch


def rasterize_svg(payload, *, timeout=4.0):
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_INPUT_BYTES:
        raise SVGUnavailable("SVG_INPUT_LIMIT")
    if os.name != "posix" or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise SVGUnavailable("SVG_RENDER_UNAVAILABLE")
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--render"], input=payload,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=min(timeout, 4.0), check=False, env={"LANG": "C.UTF-8"},
        )
    except subprocess.TimeoutExpired:
        raise SVGUnavailable("SVG_RENDER_TIMEOUT") from None
    except OSError:
        raise SVGUnavailable("SVG_RENDER_UNAVAILABLE") from None
    if result.returncode:
        code = result.stdout.decode("ascii", errors="ignore") if len(result.stdout) < 64 else ""
        raise SVGUnavailable(code if code in _FAILURES else "SVG_RENDER_FAILED")
    if not 0 < len(result.stdout) <= MAX_OUTPUT_BYTES:
        raise SVGUnavailable("SVG_RENDER_FAILED")
    _validate_png(result.stdout)
    return result.stdout


def _validate_png(payload):
    from PIL import Image

    try:
        with Image.open(BytesIO(payload)) as image:
            if image.format != "PNG" or max(image.size) > MAX_EDGE or image.width * image.height > MAX_PIXELS:
                raise ValueError
            image.verify()
    except Exception:
        raise SVGUnavailable("SVG_RENDER_FAILED") from None


def _render_child():
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 << 20, 512 << 20))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
    payload = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    payload, width, height, embedded = _prepare_svg(payload)
    import cairosvg
    if cairosvg.__version__ != "2.9.1":
        raise SVGUnavailable("SVG_RENDER_UNAVAILABLE")
    import socket
    socket.socket = _deny_fetch
    socket.create_connection = _deny_fetch
    # The only accepted URI resolves to already-validated in-memory raster bytes.
    png = cairosvg.surface.PNGSurface.convert(
        bytestring=payload, unsafe=False, url_fetcher=_embedded_fetcher(embedded),
        output_width=width, output_height=height,
    )
    if len(png) > MAX_OUTPUT_BYTES:
        raise SVGUnavailable("SVG_OUTPUT_LIMIT")
    _validate_png(png)
    sys.stdout.buffer.write(png)


if __name__ == "__main__":
    try:
        _render_child()
    except SVGUnavailable as error:
        code = str(error)
        sys.stdout.buffer.write((code if code in _FAILURES else "SVG_RENDER_FAILED").encode("ascii"))
        sys.exit(1)
    except ImportError:
        sys.stdout.buffer.write(b"SVG_RENDER_UNAVAILABLE")
        sys.exit(1)
    except Exception:
        sys.stdout.buffer.write(b"SVG_RENDER_FAILED")
        sys.exit(1)
