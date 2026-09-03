"""Provider-neutral source intake and format classification.

The intake layer accepts bytes from any connector.  It stores the original
resource identity and content hash before an optional extractor interprets
the payload.  Extractors may add typed candidates, but an unfamiliar shape is
never silently dropped.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse


_JSON_TYPES = {"application/json", "application/problem+json", "text/json"}
_STRUCTURED_TYPES = _JSON_TYPES | {"application/xml", "text/xml", "text/csv"}
_DOCUMENT_TYPES = {"text/html", "application/pdf", "text/plain"}
_DIAGRAM_TYPES = {"image/svg+xml"}


class SourceConnector(Protocol):
    """Provider-neutral connector contract implemented by source integrations."""

    name: str

    def fetch(self, request: dict[str, Any]) -> Iterable["SourceResource"]:
        ...


@dataclass(frozen=True)
class SourceResource:
    """One immutable response or file received from a source connector."""

    source_uri: str
    source_version: str
    media_type: str
    payload: bytes
    content_sha256: str
    locator: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_bytes(
        cls,
        source_uri: str,
        source_version: str,
        payload: bytes,
        media_type: str | None,
        locator: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "SourceResource":
        return cls(
            source_uri=source_uri,
            source_version=source_version,
            media_type=detect_media_type(source_uri, payload, media_type),
            payload=payload,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            locator=locator,
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True)
class NormalizationCandidate:
    """A typed extraction candidate awaiting canonical validation/publication."""

    kind: str
    key: str
    data: dict[str, Any]
    locator: str


@dataclass(frozen=True)
class SourceArtifact:
    """A classified resource whose raw bytes remain independently addressable."""

    kind: str
    source_uri: str
    source_version: str
    media_type: str
    content_sha256: str
    payload: Any
    raw_payload: bytes
    metadata: dict[str, Any]
    candidates: tuple[NormalizationCandidate, ...] = ()

    @property
    def object_key(self) -> str:
        digest_prefix = self.content_sha256[:16]
        return f"sources/{digest_prefix}/{self.content_sha256}"


def detect_media_type(source_uri: str, payload: bytes, media_type: str | None = None) -> str:
    """Resolve a stable media type from connector metadata, URL, and magic bytes."""

    if media_type:
        return media_type.split(";", 1)[0].strip().lower()
    # A source URL or filename is only a hint: provider exports frequently use
    # generic or misleading extensions. Prefer cheap content signatures before
    # falling back to the path-derived type.
    stripped = payload.lstrip(b"\xef\xbb\xbf \t\r\n")
    if stripped.startswith(b"%PDF-"):
        return "application/pdf"
    if stripped.startswith(b"<svg") or b"<svg" in stripped[:512]:
        return "image/svg+xml"
    if stripped.startswith(b"<"):
        if stripped.lower().startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
            return "text/html"
        return "application/xml"
    try:
        json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        path_type, _ = mimetypes.guess_type(urlparse(source_uri).path)
        if path_type:
            return path_type.lower()
        if b"\x00" not in payload:
            return "text/plain"
        return "application/octet-stream"
    return "application/json"


def adapt_source_resource(resource: SourceResource) -> SourceArtifact:
    """Classify a resource and expose structured JSON without losing its envelope."""

    metadata = {
        **resource.metadata,
        "source_uri": resource.source_uri,
        "source_version": resource.source_version,
        "content_sha256": resource.content_sha256,
        "media_type": resource.media_type,
        "locator": resource.locator,
    }
    if resource.media_type in _JSON_TYPES:
        try:
            document = json.loads(resource.payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"JSON source {resource.source_uri} is invalid: {error}") from error
        if isinstance(document, dict) and isinstance(document.get("header"), dict):
            header = document["header"]
            metadata.update(
                {
                    "response_date": header.get("date"),
                    "response_status": header.get("status"),
                    "response_status_code": header.get("statusCode"),
                    "response_messages": header.get("messages", []),
                }
            )
        candidates = classify_json_candidates(document)
        metadata.update(
            {
                "candidate_count": len(candidates),
                "extraction_status": "candidate_ready" if candidates else "needs_review",
            }
        )
        return SourceArtifact(
            kind="structured",
            source_uri=resource.source_uri,
            source_version=resource.source_version,
            media_type=resource.media_type,
            content_sha256=resource.content_sha256,
            payload=document,
            raw_payload=resource.payload,
            metadata=metadata,
            candidates=tuple(candidates),
        )
    if resource.media_type in _DIAGRAM_TYPES:
        return _binary_artifact("diagram", resource, metadata)
    if resource.media_type in _DOCUMENT_TYPES:
        return _binary_artifact("document", resource, metadata)
    if resource.media_type in {"application/xml", "text/xml", "text/csv"}:
        return _binary_artifact("structured", resource, metadata)
    return _binary_artifact("quarantine", resource, {**metadata, "quarantine_reason": "unsupported_media_type"})


def classify_json_candidates(document: Any) -> list[NormalizationCandidate]:
    """Recognize common source records while keeping unknown JSON shapes intact."""

    body = document.get("body") if isinstance(document, dict) and "body" in document else document
    candidates: list[NormalizationCandidate] = []
    if isinstance(body, str) and body.strip():
        identity = {"display_name": body.strip()}
        parsed_identity = parse_vehicle_display_name(body)
        if parsed_identity:
            identity.update(parsed_identity)
        candidates.append(
            NormalizationCandidate(
                kind="vehicle_identity",
                key="vehicle-identity:source",
                data=identity,
                locator="body",
            )
        )
    if not isinstance(body, (dict, list)):
        return candidates

    articles = body.get("articleDetails") if isinstance(body, dict) else None
    if isinstance(articles, list):
        for index, article in enumerate(articles):
            if isinstance(article, dict):
                article_id = str(article.get("id") or f"index-{index}")
                candidates.append(NormalizationCandidate("article", f"article:{article_id}:{index}", article, f"body.articleDetails[{index}]"))

    parts = body.get("parts") if isinstance(body, dict) else body if isinstance(body, list) else None
    if isinstance(parts, list):
        parts_locator = "body.parts" if isinstance(body, dict) else "body"
        for index, part in enumerate(parts):
            if isinstance(part, dict) and part.get("partNumber"):
                part_number = str(part["partNumber"])
                candidates.append(NormalizationCandidate("part", f"part:{part_number}", part, f"{parts_locator}[{index}]"))

    models = body.get("models") if isinstance(body, dict) else body if isinstance(body, list) else None
    if isinstance(models, list):
        models_locator = "body.models" if isinstance(body, dict) else "body"
        for index, model in enumerate(models):
            if isinstance(model, dict) and model.get("id") and model.get("model"):
                model_id = str(model["id"])
                candidates.append(NormalizationCandidate("model", f"model:{model_id}", model, f"{models_locator}[{index}]"))

    if isinstance(body, dict) and body.get("documentId"):
        document_id = str(body["documentId"])
        if "html" in body or "pdf" in body:
            candidates.append(NormalizationCandidate("document", f"document:{document_id}", body, "body"))
    return candidates


def parse_vehicle_display_name(display_name: str) -> dict[str, Any] | None:
    """Parse a common human-readable vehicle label without requiring source fields."""

    match = re.match(
        r"^\s*(?P<year>\d{4})\s+(?P<make>[\w&.-]+)\s+(?P<model>.+?)(?:\s+-\s+(?P<trim>.+))?\s*$",
        display_name,
    )
    if not match:
        return None
    parsed: dict[str, Any] = {
        "year": int(match.group("year")),
        "make": match.group("make"),
        "model": match.group("model").strip(),
    }
    if match.group("trim"):
        parsed["trim"] = match.group("trim").strip()
    return parsed


def _binary_artifact(kind: str, resource: SourceResource, metadata: dict[str, Any]) -> SourceArtifact:
    return SourceArtifact(
        kind=kind,
        source_uri=resource.source_uri,
        source_version=resource.source_version,
        media_type=resource.media_type,
        content_sha256=resource.content_sha256,
        payload=resource.payload,
        raw_payload=resource.payload,
        metadata=metadata,
    )
