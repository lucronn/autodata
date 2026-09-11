"""Provider-neutral source-diagram vectorization boundaries.

Vectorization is an image-to-image operation.  The source bytes and source URI
are required so a generated visual can never be mistaken for a diagram
grounded only in article text.  Implementations return metadata suitable for
an immutable visual artifact record; review is intentionally not implied.
"""

from __future__ import annotations

from hashlib import sha256
from html import escape
from io import BytesIO
import re
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit
from xml.etree import ElementTree


class SourceDiagramVectorizer(Protocol):
    """Image-to-vector provider boundary."""

    def redraw(self, source_bytes: bytes, *, source_uri: str) -> dict[str, Any]:
        ...


class DeterministicLocalVectorizer:
    """Small deterministic fake used by tests and local Compose."""

    processor = "autodata-local-vectorizer"
    processor_version = "1"

    def redraw(self, source_bytes: bytes, *, source_uri: str) -> dict[str, Any]:
        if not isinstance(source_bytes, bytes) or not source_bytes:
            raise ValueError("source visual bytes are required for vectorization")
        source_uri = str(source_uri or "").strip()
        if not source_uri:
            raise ValueError("source visual URI is required for vectorization")
        source_hash = sha256(source_bytes).hexdigest()
        safe_uri = escape(source_uri, quote=True)
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 120" '
            'role="img" aria-labelledby="title">'
            "<title id=\"title\">Source diagram redraw</title>"
            f"<metadata source_sha256=\"{source_hash}\" source_uri=\"{safe_uri}\"/>"
            '<rect x="8" y="8" width="304" height="104" rx="8" '
            'fill="#f8fafc" stroke="#334155"/>'
            '<path d="M36 78h72l34-36 42 36h100" fill="none" '
            'stroke="#0f766e" stroke-width="4"/>'
            '<circle cx="108" cy="78" r="7" fill="#0f766e"/>'
            '<circle cx="184" cy="78" r="7" fill="#0f766e"/>'
            '<text x="24" y="30" font-family="sans-serif" font-size="12">'
            "AI-enhanced source redraw</text>"
            "</svg>"
        )
        if not _is_renderable_svg(svg.encode("utf-8")):
            raise ValueError("vectorizer produced a non-renderable SVG")
        return {
            "svg": svg,
            "derived_bytes": svg.encode("utf-8"),
            "media_type": "image/svg+xml",
            "source_uri": source_uri,
            "source_sha256": source_hash,
            "processor": self.processor,
            "processor_version": self.processor_version,
            "renderable": True,
            "review_state": "UNREVIEWED",
            "label": "AI-enhanced / UNREVIEWED",
        }


class ObjectStorageSourceDiagramVectorizer:
    """Persist the original and vector output through a storage-neutral API."""

    def __init__(
        self,
        storage: Any,
        vectorizer: SourceDiagramVectorizer,
        *,
        bucket: str,
        source_prefix: str = "source",
        derived_prefix: str = "derived",
    ) -> None:
        if not bucket.strip():
            raise ValueError("visual object-storage bucket is required")
        if not source_prefix.strip() or not derived_prefix.strip():
            raise ValueError("visual object-storage prefixes are required")
        self._storage = storage
        self._vectorizer = vectorizer
        self._bucket = bucket.strip()
        self._source_prefix = source_prefix.strip().strip("/")
        self._derived_prefix = derived_prefix.strip().strip("/")

    def redraw(self, source_bytes: bytes, *, source_uri: str) -> dict[str, Any]:
        if not isinstance(source_bytes, bytes) or not source_bytes:
            raise ValueError("source visual bytes are required for vectorization")
        source_uri = str(source_uri or "").strip()
        if not source_uri:
            raise ValueError("source visual URI is required for vectorization")
        source_hash = sha256(source_bytes).hexdigest()
        source_key = f"{self._source_prefix}/{source_hash}{_source_suffix(source_uri)}"
        self._put(source_key, source_bytes, _source_media_type(source_uri))

        result = self._vectorizer.redraw(source_bytes, source_uri=source_uri)
        svg_value = result.get("derived_bytes") or result.get("svg")
        if isinstance(svg_value, str):
            svg_bytes = svg_value.encode("utf-8")
        elif isinstance(svg_value, bytes):
            svg_bytes = svg_value
        else:
            raise ValueError("vectorizer did not return SVG bytes")
        if not _is_renderable_svg(svg_bytes):
            raise ValueError("vectorizer produced a non-renderable SVG")
        derived_key = f"{self._derived_prefix}/{source_hash}.svg"
        self._put(derived_key, svg_bytes, "image/svg+xml")
        return {
            **dict(result),
            "source_object_key": source_key,
            "derived_object_key": derived_key,
            "source_uri": source_uri,
            "source_sha256": source_hash,
            "derived_sha256": sha256(svg_bytes).hexdigest(),
            "renderable": True,
            "review_state": "UNREVIEWED",
            "label": "AI-enhanced / UNREVIEWED",
        }

    def _put(self, key: str, payload: bytes, media_type: str) -> None:
        self._storage.put_object(
            self._bucket,
            key,
            BytesIO(payload),
            len(payload),
            content_type=media_type,
        )


def vectorize_source_diagram(
    source_visual: Mapping[str, Any],
    *,
    vectorizer: SourceDiagramVectorizer,
) -> dict[str, Any]:
    """Vectorize an existing source visual and reject text-only requests."""

    if not isinstance(source_visual, Mapping):
        raise ValueError("source visual is required for vectorization")
    source_bytes = source_visual.get("source_bytes")
    if source_bytes is None:
        source_bytes = source_visual.get("bytes", source_visual.get("content"))
    if isinstance(source_bytes, bytearray):
        source_bytes = bytes(source_bytes)
    source_uri = source_visual.get("source_uri") or source_visual.get("uri") or source_visual.get("url")
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise ValueError("source visual bytes are required; text-only diagram requests are unsupported")
    if not str(source_uri or "").strip():
        raise ValueError("source visual URI is required for vectorization")
    return vectorizer.redraw(source_bytes, source_uri=str(source_uri).strip())


def _is_renderable_svg(payload: bytes) -> bool:
    try:
        root = ElementTree.fromstring(payload)
    except (ElementTree.ParseError, ValueError):
        return False
    return root.tag.rsplit("}", 1)[-1].casefold() == "svg"


def _source_suffix(source_uri: str) -> str:
    suffix = urlsplit(source_uri).path.rsplit("/", 1)[-1]
    match = re.search(r"(\.(?:bmp|gif|jpe?g|png|svg|tiff?|webp))$", suffix.casefold())
    return match.group(1) if match else ".bin"


def _source_media_type(source_uri: str) -> str:
    suffix = _source_suffix(source_uri)
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".svg": "image/svg+xml",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")


# Friendly aliases keep the provider-neutral boundary discoverable to local
# callers without making the deterministic fake part of the public contract.
DeterministicSvgVectorizer = DeterministicLocalVectorizer
LocalSvgVectorizer = DeterministicLocalVectorizer
ObjectStorageVectorizer = ObjectStorageSourceDiagramVectorizer


__all__ = [
    "DeterministicLocalVectorizer",
    "DeterministicSvgVectorizer",
    "LocalSvgVectorizer",
    "ObjectStorageSourceDiagramVectorizer",
    "ObjectStorageVectorizer",
    "SourceDiagramVectorizer",
    "vectorize_source_diagram",
]
