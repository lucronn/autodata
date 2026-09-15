"""Deterministic standalone HTML rendering for complete repair guides."""

from __future__ import annotations

from base64 import b64encode
from html import escape
import re
from typing import Any, Mapping


_GENERIC_FIGURE_CAPTIONS = frozenset(
    {
        "diagram",
        "figure",
        "image",
        "picture",
        "procedure figure",
        "source diagram",
    }
)

_INLINE_CSS = """
:root { color-scheme: light; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #27352f; background: #f5f8f6; }
body { max-width: 48rem; margin: 0 auto; padding: 2rem 1.25rem 3rem; background: #fff; line-height: 1.55; }
h1, h2, h3 { color: #17231f; line-height: 1.2; }
h1 { margin: 0 0 .35rem; font-size: 2rem; }
h2 { margin-top: 2rem; border-bottom: 1px solid #d8e0db; padding-bottom: .35rem; }
h3 { margin: 0 0 .35rem; font-size: 1.05rem; }
.subtitle { margin: 0 0 1.25rem; color: #53625c; font-size: 1.05rem; }
.metadata { display: grid; grid-template-columns: max-content 1fr; gap: .3rem .8rem; margin: 1rem 0 1.5rem; padding: .9rem 1rem; background: #eef4f0; border-radius: .5rem; font-size: .9rem; }
.metadata dt { font-weight: 700; color: #53625c; }
.metadata dd { margin: 0; overflow-wrap: anywhere; }
.warning { margin: .75rem 0; padding: .75rem 1rem; border-left: .3rem solid #e7b24a; background: #fff5df; }
.steps { padding-left: 1.75rem; }
.step { padding: .2rem 0 1.2rem .35rem; }
.instruction { margin: .35rem 0; }
figure { margin: 1rem 0; padding: .75rem; background: #f5f8f6; border: 1px solid #d8e0db; border-radius: .4rem; }
img { display: block; max-width: 100%; height: auto; margin: 0 auto; }
figcaption { margin-top: .55rem; color: #53625c; font-size: .88rem; text-align: center; }
.evidence { margin: .55rem 0 0; color: #53625c; font-size: .85rem; }
.evidence ul { margin: .2rem 0 0; }
footer { margin-top: 2rem; padding-top: .8rem; border-top: 1px solid #d8e0db; color: #53625c; font-size: .82rem; }
""".strip()

_EXTENSION_MEDIA_TYPES = {
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}


def _text(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("message", value.get("text", value.get("description", "")))
    return str(value or "").strip()


def _escaped(value: Any) -> str:
    return escape(_text(value), quote=False)


def _attribute(value: Any) -> str:
    return escape(_text(value), quote=True)


def _caption(image: Mapping[str, Any]) -> str:
    for key in ("alt", "description", "label", "title"):
        value = _text(image.get(key))
        if value and value.casefold() not in _GENERIC_FIGURE_CAPTIONS:
            return value
    return ""


def _media_type(image: Mapping[str, Any]) -> str:
    for key in ("media_type", "mime_type", "content_type"):
        value = _text(image.get(key)).split(";", 1)[0].casefold()
        if value.startswith("image/") and re.fullmatch(r"image/[a-z0-9.+-]+", value):
            return value

    url = _text(image.get("url"))
    extension = re.search(r"(\.[a-z0-9]+)(?:[?#]|$)", url.casefold())
    if extension and extension.group(1) in _EXTENSION_MEDIA_TYPES:
        return _EXTENSION_MEDIA_TYPES[extension.group(1)]

    payload = image.get("image_bytes")
    if isinstance(payload, (bytes, bytearray, memoryview)):
        raw = bytes(payload)
        if raw.startswith(b"\x89PNG"):
            return "image/png"
        if raw.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if raw.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
            return "image/webp"
        if raw.lstrip().startswith(b"<svg"):
            return "image/svg+xml"
    return "application/octet-stream"


def _image_data_uri(image: Mapping[str, Any]) -> str:
    payload = image.get("image_bytes")
    if not isinstance(payload, (bytes, bytearray, memoryview)) or not bytes(payload):
        raise ValueError("all guide figures must be prepared before HTML rendering")
    encoded = b64encode(bytes(payload)).decode("ascii")
    return f"data:{_media_type(image)};base64,{encoded}"


def _evidence_ids(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        value = value.get("evidence_ids") or value.get("evidence_id") or value.get("id")
    if isinstance(value, (str, int)):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    result: set[str] = set()
    for item in value:
        if isinstance(item, Mapping):
            item = item.get("evidence_id") or item.get("id")
        text = _text(item)
        if text:
            result.add(text)
    return sorted(result)


def _image_key(image: Mapping[str, Any]) -> tuple[str, bytes | str]:
    payload = image.get("image_bytes")
    if isinstance(payload, (bytes, bytearray, memoryview)):
        payload_key: bytes | str = bytes(payload)
    else:
        payload_key = _text(payload)
    return _text(image.get("url")), payload_key


def _guide_image_refs(guide: Mapping[str, Any], steps: list[Any]) -> list[Mapping[str, Any]]:
    """Return each guide image once, including figures not attached to a step."""

    refs: list[Mapping[str, Any]] = []
    seen: set[tuple[str, bytes | str]] = set()
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        images = step.get("images", [])
        if not isinstance(images, list):
            continue
        for image in images:
            if not isinstance(image, Mapping):
                raise ValueError("all guide figures must be prepared before HTML rendering")
            key = _image_key(image)
            if key not in seen:
                refs.append(image)
                seen.add(key)
    images = guide.get("images", [])
    if isinstance(images, Mapping):
        images = [images]
    if images is not None and not isinstance(images, list):
        raise ValueError("all guide figures must be prepared before HTML rendering")
    for image in images or []:
        if not isinstance(image, Mapping):
            raise ValueError("all guide figures must be prepared before HTML rendering")
        key = _image_key(image)
        if key not in seen:
            refs.append(image)
            seen.add(key)
    return refs


def _render_figure(lines: list[str], image: Mapping[str, Any], indent: str = "      ") -> None:
    data_uri = _image_data_uri(image)
    caption = _caption(image)
    alt = f' alt="{_attribute(caption)}"' if caption else ' alt=""'
    lines.append(f"{indent}<figure>")
    lines.append(f'{indent}  <img{alt} src="{data_uri}">')
    if caption:
        lines.append(f"{indent}  <figcaption>{_escaped(caption)}</figcaption>")
    lines.append(f"{indent}</figure>")


def _step_action(value: Any, sequence: int) -> str:
    action = _text(value) or f"Complete step {sequence}."
    return re.sub(rf"^\s*(?:step\s*)?{sequence}\s*[.):-]\s*", "", action, flags=re.IGNORECASE)


def _complete_guide(guide: Mapping[str, Any]) -> str:
    if guide.get("content_status") != "complete" or guide.get("pdf_ready") is not True:
        raise ValueError("a complete guide is required before creating HTML")
    revision_id = _text(guide.get("revision_id"))
    if not revision_id:
        raise ValueError("guide revision is required before creating HTML")
    return revision_id


def render_guide_html(guide: Mapping[str, Any]) -> bytes:
    """Return deterministic, self-contained UTF-8 HTML for one guide revision."""

    if not isinstance(guide, Mapping):
        raise TypeError("guide must be a mapping")
    revision_id = _complete_guide(guide)
    steps = guide.get("steps", [])
    if not isinstance(steps, list):
        steps = []

    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f'  <meta name="autodata-guide-revision" content="{_attribute(revision_id)}">',
        f"  <title>{_escaped(guide.get('title') or 'AutoData Repair Guide')}</title>",
        f"  <style>{_INLINE_CSS}</style>",
        "</head>",
        "<body>",
        f"  <h1>{_escaped(guide.get('title') or 'AutoData Repair Guide')}</h1>",
        f'  <p class="subtitle">{_escaped(guide.get("applicability") or "Vehicle-specific procedure")}</p>',
        '  <dl class="metadata">',
        f"    <dt>Guide revision</dt><dd>{_escaped(revision_id)}</dd>",
    ]

    watermark = _text(guide.get("source_watermark"))
    if not watermark:
        watermarks = guide.get("source_watermarks", [])
        if isinstance(watermarks, (list, tuple)):
            watermark = ", ".join(sorted({_text(item) for item in watermarks if _text(item)}))
    if watermark:
        lines.append(f"    <dt>Source watermark</dt><dd>{_escaped(watermark)}</dd>")
    review_state = _text(guide.get("review_label")) or _text(guide.get("review_state"))
    if review_state:
        lines.append(f"    <dt>Review state</dt><dd>{_escaped(review_state)}</dd>")
    lines.extend(["  </dl>"])

    preparation = guide.get("preparation", [])
    if isinstance(preparation, str):
        preparation = [preparation]
    if isinstance(preparation, list) and preparation:
        lines.extend(["  <h2>Before you begin</h2>", "  <ul>"])
        for item in preparation:
            lines.append(f"    <li>{_escaped(item)}</li>")
        lines.append("  </ul>")

    warnings = guide.get("warnings", [])
    if isinstance(warnings, str):
        warnings = [warnings]
    if isinstance(warnings, list) and warnings:
        lines.extend(["  <h2>Safety notes</h2>"])
        for item in warnings:
            lines.append(f'  <p class="warning"><strong>Important:</strong> {_escaped(item)}</p>')

    lines.extend(["  <h2>Procedure</h2>", '  <ol class="steps">'])
    guide_evidence = sorted(
        set(_evidence_ids(guide.get("evidence_ids")))
        | set(_evidence_ids(guide.get("evidence")))
    )
    rendered_images: set[tuple[str, bytes | str]] = set()
    for index, item in enumerate(steps, start=1):
        if not isinstance(item, Mapping):
            continue
        sequence_value = item.get("sequence", index)
        try:
            sequence = int(sequence_value)
        except (TypeError, ValueError):
            sequence = index
        action = _step_action(item.get("action"), sequence)
        lines.extend(["    <li class=\"step\">", f"      <h3>Step {sequence}: {_escaped(action)}</h3>"])
        instructions = item.get("instructions", [])
        if isinstance(instructions, str):
            instructions = [instructions]
        if isinstance(instructions, list):
            for instruction in instructions:
                lines.append(f'      <p class="instruction">{_escaped(instruction)}</p>')

        images = item.get("images", [])
        if not isinstance(images, list):
            images = []
        for image in images:
            if not isinstance(image, Mapping):
                raise ValueError("all guide figures must be prepared before HTML rendering")
            _render_figure(lines, image)
            rendered_images.add(_image_key(image))

        image_evidence = [
            image_evidence_id
            for image in images
            if isinstance(image, Mapping)
            for image_evidence_id in _evidence_ids(image.get("evidence_ids") or image.get("evidence_id"))
        ]
        evidence = sorted(
            set(guide_evidence)
            | set(_evidence_ids(item.get("evidence_ids")))
            | set(_evidence_ids(item.get("evidence")))
            | set(image_evidence)
        )
        if evidence:
            lines.extend([
                '      <div class="evidence">Evidence references:',
                "        <ul>",
                *[f"          <li>{_escaped(value)}</li>" for value in evidence],
                "        </ul>",
                "      </div>",
            ])
        lines.append("    </li>")
    lines.extend(["  </ol>"])

    extra_images = [
        image
        for image in _guide_image_refs(guide, steps)
        if _image_key(image) not in rendered_images
    ]
    if extra_images:
        lines.extend(["  <h2>Figures</h2>", '  <div class="figures">'])
        for image in extra_images:
            _render_figure(lines, image, indent="    ")
        lines.append("  </div>")

    if guide_evidence:
        lines.extend([
            "  <h2>Evidence references</h2>",
            '  <ul class="evidence">',
            *[f"    <li>{_escaped(value)}</li>" for value in guide_evidence],
            "  </ul>",
        ])
    lines.extend([
        "  <footer>AutoData DIY service guide</footer>",
        "</body>",
        "</html>",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


__all__ = ["render_guide_html"]
