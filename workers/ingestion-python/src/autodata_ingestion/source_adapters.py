"""Provider-neutral source intake and format classification.

The intake layer accepts bytes from any connector.  It stores the original
resource identity and content hash before an optional extractor interprets
the payload.  Extractors may add typed candidates, but an unfamiliar shape is
never silently dropped.
"""

from __future__ import annotations

import base64
import csv
import hashlib
from html.parser import HTMLParser
import io
import json
import mimetypes
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol
from urllib.parse import unquote, urljoin, urlparse, urlsplit
from xml.etree import ElementTree


_JSON_TYPES = {"application/json", "application/problem+json", "text/json"}


def _is_json_media_type(media_type: str) -> bool:
    """Accept JSON suffix types (e.g. application/hal+json) as JSON."""

    return media_type in _JSON_TYPES or (
        media_type.startswith("application/") and media_type.endswith("+json")
    )
_STRUCTURED_TYPES = _JSON_TYPES | {"application/xml", "text/xml", "text/csv"}
_DOCUMENT_TYPES = {"text/html", "application/pdf", "text/plain"}
_DIAGRAM_TYPES = {"image/svg+xml"}
_IMAGE_TYPES = {"image/bmp", "image/jpeg", "image/png", "image/tiff", "image/webp"}
_GENERIC_MEDIA_TYPES = {"application/octet-stream", "binary/octet-stream", "text/plain"}
_MAX_BOUND_EMBEDDED_PDF_BYTES = 6 * 1024 * 1024
_MAX_BOUND_EMBEDDED_PDF_PAGES = 24


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


MediaTypeAdapter = Callable[[SourceResource, dict[str, Any]], SourceArtifact]
_MEDIA_TYPE_ADAPTERS: dict[str, MediaTypeAdapter] = {}


def register_media_type_adapter(media_type: str, adapter: MediaTypeAdapter) -> None:
    """Register an extractor for a source media type without changing intake."""

    normalized_type = str(media_type).split(";", 1)[0].strip().casefold()
    if "/" not in normalized_type or any(character.isspace() for character in normalized_type):
        raise ValueError("media type must be a lowercase type/subtype token")
    if not callable(adapter):
        raise TypeError("media type adapter must be callable")
    _MEDIA_TYPE_ADAPTERS[normalized_type] = adapter


def detect_media_type(source_uri: str, payload: bytes, media_type: str | None = None) -> str:
    """Resolve a stable media type from connector metadata, URL, and magic bytes."""

    stripped = payload.lstrip(b"\xef\xbb\xbf \t\r\n")
    declared_type = media_type.split(";", 1)[0].strip().lower() if media_type else None
    sniffed_type = _sniff_media_type(stripped)
    # Connector media types and filenames are hints when they are generic. A
    # provider may label JSON, HTML, XML, or CSV as octet-stream/text/plain;
    # content signatures take precedence in that case. Specific declared
    # types remain authoritative enough to preserve invalid-payload errors.
    if sniffed_type and (declared_type is None or declared_type in _GENERIC_MEDIA_TYPES):
        return sniffed_type
    if declared_type:
        return declared_type
    path_type, _ = mimetypes.guess_type(urlparse(source_uri).path)
    if path_type:
        return path_type.lower()
    if b"\x00" not in payload:
        return "text/plain"
    return "application/octet-stream"


def _sniff_media_type(payload: bytes) -> str | None:
    if payload.startswith(b"%PDF-"):
        return "application/pdf"
    if payload.startswith(b"<svg") or b"<svg" in payload[:512]:
        return "image/svg+xml"
    if payload.startswith(b"<"):
        if payload.lower().startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
            return "text/html"
        return "application/xml"
    try:
        json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        if _looks_like_csv(payload):
            return "text/csv"
        return None
    return "application/json"


def _looks_like_csv(payload: bytes) -> bool:
    """Recognize delimited text conservatively without trusting a filename."""

    if b"\x00" in payload:
        return False
    try:
        sample = payload[:65536].decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    lines = [line for line in sample.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    try:
        dialect = csv.Sniffer().sniff("\n".join(lines[:10]), delimiters=",\t;|")
        rows = list(csv.reader(lines[:10], dialect))
    except csv.Error:
        return False
    if len(rows) < 2 or len(rows[0]) < 2:
        return False
    width = len(rows[0])
    return all(len(row) == width for row in rows[1:]) and all(cell.strip() for cell in rows[0])


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
    custom_adapter = _MEDIA_TYPE_ADAPTERS.get(resource.media_type)
    if custom_adapter is not None:
        return custom_adapter(resource, metadata)
    if _is_json_media_type(resource.media_type):
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
        candidates = classify_json_candidates(
            document,
            source_uri=resource.source_uri,
            target_article_id=resource.metadata.get("target_article_id"),
        )
        metadata.update(
            {
                "candidate_count": len(candidates),
                "extraction_status": "candidate_ready" if candidates else "needs_review",
            }
        )
        embedded_candidates, embedded_metadata = _adapt_embedded_json_resources(resource, document)
        candidates.extend(embedded_candidates)
        metadata.update(embedded_metadata)
        metadata["candidate_count"] = len(candidates)
        metadata["extraction_status"] = "candidate_ready" if candidates else "needs_review"
        if embedded_metadata.get("embedded_needs_review"):
            metadata["extraction_warnings"] = [
                *metadata.get("extraction_warnings", []),
                "one or more embedded resources need review",
            ]
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
        return _adapt_svg_resource(resource, metadata)
    if resource.media_type in _IMAGE_TYPES:
        return _adapt_image_resource(resource, metadata)
    if resource.media_type in _DOCUMENT_TYPES:
        return _adapt_document_resource(resource, metadata)
    if resource.media_type == "text/csv":
        return _adapt_csv_resource(resource, metadata)
    if resource.media_type in {"application/xml", "text/xml"}:
        return _adapt_xml_resource(resource, metadata)
    return _binary_artifact("quarantine", resource, {**metadata, "quarantine_reason": "unsupported_media_type"})


def _embedded_hal_article(body: dict[str, Any]) -> NormalizationCandidate | None:
    """Build an article candidate from a HAL ``_embedded.data.article`` record."""

    embedded = body.get("_embedded")
    if not isinstance(embedded, dict):
        return None
    data = embedded.get("data")
    if not isinstance(data, dict):
        return None
    article = data.get("article")
    if not isinstance(article, dict):
        return None
    record = {
        **article,
        "id": article.get("id") or body.get("id"),
        "title": article.get("title") or body.get("title"),
    }
    content = record.get("content")
    if isinstance(content, str) and "<" in content and ">" in content:
        # HAL article bodies are full HTML documents; persist readable lines
        # so downstream normalization can build ordered steps from them.
        record["content"] = _html_lines(content.encode("utf-8"))
    candidate = _candidate_from_record(record, "body._embedded.data.article")
    if candidate is None or candidate.kind != "article":
        return None
    return candidate


def classify_json_candidates(
    document: Any,
    *,
    source_uri: str = "",
    target_article_id: Any = None,
) -> list[NormalizationCandidate]:
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

    if isinstance(body, dict):
        vehicle_candidate = _candidate_from_record(body, "body")
        # HAL-style payloads carry the full article (including its HTML body)
        # under _embedded.data.article while the top level only repeats the
        # title/id; prefer the embedded record over the thin top-level one.
        embedded_article = _embedded_hal_article(body)
        if embedded_article is not None and vehicle_candidate is not None and vehicle_candidate.kind == "article":
            vehicle_candidate = embedded_article
        if vehicle_candidate is not None:
            candidates.append(vehicle_candidate)
        if vehicle_candidate is None or vehicle_candidate.kind != "vehicle_identity":
            # Many APIs wrap the actual record under a vehicle-shaped key.
            # Inspect only known identity wrappers so arbitrary nested JSON is
            # not mistaken for canonical vehicle data.
            for key in ("vehicle", "vehicleIdentity", "vehicle_identity", "car"):
                nested = body.get(key)
                if isinstance(nested, dict):
                    nested_candidate = _candidate_from_record(nested, f"body.{key}")
                    if nested_candidate is not None and nested_candidate.kind == "vehicle_identity":
                        candidates.append(nested_candidate)
                        break
        raw_specifications = body.get("specifications")
        if isinstance(raw_specifications, dict):
            for name, value in raw_specifications.items():
                if str(name).strip():
                    unit = None
                    if isinstance(value, dict) and "value" in value:
                        unit = _field(value, "unit", "units") or None
                        value = value["value"]
                    candidates.append(
                        NormalizationCandidate(
                            "specification",
                            f"specification:{name}",
                            {"name": str(name).strip(), "value": value, "unit": unit},
                            "body.specifications." + str(name),
                        )
                    )
        elif isinstance(raw_specifications, list):
            for index, specification in enumerate(raw_specifications):
                if isinstance(specification, dict):
                    candidate = _candidate_from_specification(
                        specification, f"body.specifications[{index}]"
                    )
                    if candidate is not None:
                        candidates.append(candidate)

    articles = body.get("articleDetails") if isinstance(body, dict) else None
    if isinstance(articles, list):
        for index, article in enumerate(articles):
            if isinstance(article, dict):
                article_id = str(article.get("id") or f"index-{index}")
                candidates.append(NormalizationCandidate("article", f"article:{article_id}:{index}", article, f"body.articleDetails[{index}]"))

    # AutoAPI exposes labor as a separate JSON resource. Keep it typed so the
    # source bundle can join it to the article while preserving its evidence.
    if "/labor/" in source_uri.casefold():
        article_id = str(target_article_id or "").strip()
        if not article_id:
            article_id = unquote(urlsplit(source_uri).path.rsplit("/", 1)[-1]).strip()
        operations = body.get("operations") if isinstance(body, dict) else body
        if operations is None and isinstance(body, dict) and (
            isinstance(body.get("mainOperation"), dict)
            or isinstance(body.get("includedOperations"), list)
        ):
            operations = body
        if article_id and isinstance(operations, (dict, list)):
            candidates.append(
                NormalizationCandidate(
                    "article_operations",
                    f"article-operations:{article_id}",
                    {"article_id": article_id, "operations": operations},
                    "body.operations" if isinstance(body, dict) and "operations" in body else "body",
                )
            )

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


def _adapt_embedded_json_resources(
    resource: SourceResource,
    document: Any,
) -> tuple[list[NormalizationCandidate], dict[str, Any]]:
    """Adapt explicitly declared HTML/PDF fields while retaining outer provenance."""

    body = document.get("body") if isinstance(document, dict) and "body" in document else document
    if not isinstance(body, dict):
        return [], {}
    # Bankone article resources often wrap a PDF/HTML payload without a
    # documentId. When the connector fetch tagged the resource with the
    # caller's article id, use that id's final opaque segment so
    # ``_attach_document_content`` can join extracted text to the index row.
    document_id = _field(body, "document_id", "documentId", "id")
    if not document_id:
        target_article_id = str(resource.metadata.get("target_article_id") or "").strip()
        if target_article_id:
            document_id = target_article_id.rsplit(":", 1)[-1].strip() or target_article_id
        else:
            document_id = "embedded"
    candidates: list[NormalizationCandidate] = []
    resources: list[dict[str, Any]] = []
    needs_review = False

    html = body.get("html")
    if isinstance(html, str) and html.strip():
        embedded_resource = SourceResource.from_bytes(
            f"{resource.source_uri}#embedded/{document_id}/html",
            resource.source_version,
            html.encode("utf-8"),
            "text/html",
            locator=f"body.html:{document_id}",
            metadata={"embedded_in_content_sha256": resource.content_sha256},
        )
        embedded_artifact = _adapt_document_resource(embedded_resource, {
            "embedded_in_content_sha256": resource.content_sha256,
        })
        mapped, record = _map_embedded_artifact(
            resource,
            embedded_resource,
            embedded_artifact,
            f"body.html:{document_id}",
        )
        candidates.extend(mapped)
        resources.append(record)
        needs_review = needs_review or record["extraction_status"] == "needs_review"

    encoded_pdf = body.get("pdf")
    if isinstance(encoded_pdf, str) and encoded_pdf.strip():
        locator = f"body.pdf:{document_id}"
        try:
            pdf_payload = _decode_embedded_pdf(encoded_pdf)
        except ValueError as error:
            resources.append(
                {
                    "locator": locator,
                    "media_type": "application/pdf",
                    "extraction_status": "needs_review",
                    "extraction_error": str(error),
                }
            )
            needs_review = True
        else:
            embedded_resource = SourceResource.from_bytes(
                f"{resource.source_uri}#embedded/{document_id}/pdf",
                resource.source_version,
                pdf_payload,
                "application/pdf",
                locator=locator,
                metadata={"embedded_in_content_sha256": resource.content_sha256},
            )
            embedded_artifact = adapt_source_resource(embedded_resource)
            mapped, record = _map_embedded_artifact(
                resource,
                embedded_resource,
                embedded_artifact,
                locator,
            )
            candidates.extend(mapped)
            resources.append(record)
            needs_review = needs_review or record["extraction_status"] == "needs_review"

    if not resources:
        return candidates, {}
    return candidates, {
        "embedded_resources": resources,
        "embedded_needs_review": needs_review,
    }


def _decode_embedded_pdf(encoded_pdf: str, *, max_bytes: int | None = None) -> bytes:
    if not isinstance(encoded_pdf, str):
        raise ValueError("embedded PDF is not valid base64")
    value = encoded_pdf.strip()
    if value.lower().startswith("data:application/pdf;base64,"):
        value = value.split(",", 1)[1]
    value = re.sub(r"\s+", "", value)
    if max_bytes is not None and len(value) > ((max_bytes + 2) // 3) * 4:
        raise ValueError("embedded PDF exceeds its byte limit")
    try:
        payload = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError("embedded PDF is not valid base64") from error
    if max_bytes is not None and len(payload) > max_bytes:
        raise ValueError("embedded PDF exceeds its byte limit")
    if not payload.startswith(b"%PDF-"):
        raise ValueError("embedded PDF does not contain a PDF signature")
    return payload


def _map_embedded_artifact(
    outer_resource: SourceResource,
    embedded_resource: SourceResource,
    embedded_artifact: SourceArtifact,
    locator_prefix: str,
) -> tuple[list[NormalizationCandidate], dict[str, Any]]:
    """Rebase embedded candidate locators and keys to the outer source path."""

    mapped: list[NormalizationCandidate] = []
    for candidate in embedded_artifact.candidates:
        locator = (
            candidate.locator
            if candidate.locator == locator_prefix or candidate.locator.startswith(f"{locator_prefix}:")
            else f"{locator_prefix}:{candidate.locator}"
        )
        mapped.append(
            NormalizationCandidate(
                candidate.kind,
                f"embedded:{outer_resource.content_sha256}:{candidate.kind}:{locator}",
                {
                    **candidate.data,
                    **({"id": str(outer_resource.metadata["target_article_id"])}
                       if candidate.kind == "article" and outer_resource.metadata.get("target_article_id")
                       else {}),
                    "outer_content_sha256": outer_resource.content_sha256,
                    "embedded_content_sha256": embedded_resource.content_sha256,
                    "embedded_media_type": embedded_resource.media_type,
                },
                locator,
            )
        )
    return mapped, {
        "locator": locator_prefix,
        "media_type": embedded_resource.media_type,
        "content_sha256": embedded_resource.content_sha256,
        "candidate_count": len(mapped),
        "extraction_status": embedded_artifact.metadata.get("extraction_status", "needs_review"),
        **({"extraction_error": embedded_artifact.metadata["extraction_error"]}
           if embedded_artifact.metadata.get("extraction_error") else {}),
    }


def _adapt_csv_resource(resource: SourceResource, metadata: dict[str, Any]) -> SourceArtifact:
    try:
        text = resource.payload.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or any(not str(field).strip() for field in reader.fieldnames):
            raise ValueError("CSV source is missing a non-empty header")
        records = [dict(row) for row in reader]
        candidates = [
            candidate
            for index, record in enumerate(records)
            if (candidate := _candidate_from_record(record, f"row[{index}]")) is not None
        ]
        return _structured_artifact(
            resource,
            metadata,
            records,
            candidates,
        )
    except (UnicodeDecodeError, csv.Error, ValueError) as error:
        return _structured_error_artifact(resource, metadata, error)


def _adapt_xml_resource(resource: SourceResource, metadata: dict[str, Any]) -> SourceArtifact:
    try:
        lowered = resource.payload.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise ValueError("XML DTD and entity declarations are not supported")
        root = ElementTree.fromstring(resource.payload)
        records: list[dict[str, Any]] = []
        candidates: list[NormalizationCandidate] = []
        for element in root.iter():
            record_type = _local_name(element.tag).casefold()
            if record_type not in {"vehicle", "vehicleidentity", "part", "model", "article"}:
                continue
            if not list(element):
                continue
            record = {
                _local_name(child.tag): (child.text or "").strip()
                for child in element
                if isinstance(child.tag, str)
            }
            records.append(record)
            candidate = _candidate_from_record(record, _local_name(element.tag), record_type=record_type)
            if candidate is not None:
                candidates.append(candidate)
        return _structured_artifact(resource, metadata, records, candidates)
    except (ElementTree.ParseError, ValueError) as error:
        return _structured_error_artifact(resource, metadata, error)


def _structured_artifact(
    resource: SourceResource,
    metadata: dict[str, Any],
    records: list[dict[str, Any]],
    candidates: list[NormalizationCandidate],
) -> SourceArtifact:
    metadata = {
        **metadata,
        "record_count": len(records),
        "candidate_count": len(candidates),
        "extraction_status": "candidate_ready" if candidates else "needs_review",
    }
    return SourceArtifact(
        kind="structured",
        source_uri=resource.source_uri,
        source_version=resource.source_version,
        media_type=resource.media_type,
        content_sha256=resource.content_sha256,
        payload=records,
        raw_payload=resource.payload,
        metadata=metadata,
        candidates=tuple(candidates),
    )


def _structured_error_artifact(
    resource: SourceResource,
    metadata: dict[str, Any],
    error: Exception,
) -> SourceArtifact:
    return _structured_artifact(
        resource,
        {**metadata, "extraction_error": str(error)},
        [],
        [],
    )


def _adapt_document_resource(
    resource: SourceResource,
    metadata: dict[str, Any],
) -> SourceArtifact:
    """Extract only literal text from safe document types; preserve other bytes."""

    if resource.media_type == "application/pdf":
        return _adapt_pdf_resource(resource, metadata)
    try:
        if resource.media_type == "text/html":
            text = _html_text(resource.payload)
        else:
            text = resource.payload.decode("utf-8-sig").strip()
    except UnicodeDecodeError as error:
        return _binary_artifact(
            "document",
            resource,
            {**metadata, "extraction_status": "needs_review", "extraction_error": str(error)},
        )
    if not text:
        return _binary_artifact("document", resource, {**metadata, "extraction_status": "needs_review"})
    locator = resource.locator or "document"
    candidates = [NormalizationCandidate(
        "document_text",
        f"document-text:{resource.content_sha256}",
        {
            "text": text,
            "images": _html_media_references(resource) if resource.media_type == "text/html" else [],
        },
        locator,
    )]
    if resource.media_type == "text/html":
        candidates.extend(_html_article_candidates(resource))
    return SourceArtifact(
        kind="document",
        source_uri=resource.source_uri,
        source_version=resource.source_version,
        media_type=resource.media_type,
        content_sha256=resource.content_sha256,
        payload=resource.payload,
        raw_payload=resource.payload,
        metadata={
            **metadata,
            "candidate_count": len(candidates),
            "extraction_status": "candidate_ready",
            "text_char_count": len(text),
        },
        candidates=tuple(candidates),
    )


def _extract_pdf_page_images(
    page: Any, *, page_number: int, allow_compact_figure: bool = False,
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Return browser-safe embedded images from one PDF page."""

    try:
        virtual_images = getattr(page, "images", []) or []
        embedded = (list(virtual_images.items()) if hasattr(virtual_images, "items")
                    else [(None, image) for image in virtual_images])
    except Exception:
        return [], []
    extracted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, (pdf_key, image) in enumerate(embedded, start=1):
        payload = getattr(image, "data", None)
        if not isinstance(payload, (bytes, bytearray)):
            continue
        payload = bytes(payload)
        compact = len(payload) < 2_048
        if compact and (not allow_compact_figure or len(embedded) != 1):
            continue
        converted = _browser_safe_image_payload(payload)
        if converted is None:
            continue
        media_type, safe_payload = converted
        digest = hashlib.sha256(safe_payload).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        source_name = str(getattr(image, "name", "") or f"page-{page_number}-image-{index}")
        extracted.append(
            {
                "page": page_number,
                "image_id": f"pdf-page-{page_number}-{digest[:12]}",
                "alt": f"Figure from page {page_number}",
                "media_type": media_type,
                "content_sha256": digest,
                "byte_count": len(safe_payload),
                "source_name": source_name,
                "pdf_key": str(pdf_key) if isinstance(pdf_key, str) else None,
                **({"_compact_pdf_figure": True} if compact else {}),
                "url": (
                    f"data:{media_type};base64,"
                    + base64.b64encode(safe_payload).decode("ascii")
                ),
            }
        )
    return extracted, [key for key, _ in embedded]


def _browser_safe_image_payload(payload: bytes) -> tuple[str, bytes] | None:
    """Normalize PDF-embedded images to RGB PNG/JPEG browsers can display."""

    try:
        from PIL import Image
    except ImportError:
        if payload.startswith(b"\x89PNG"):
            return "image/png", payload
        if payload.startswith(b"\xff\xd8\xff"):
            return "image/jpeg", payload
        return None
    try:
        image = Image.open(io.BytesIO(payload))
        image.load()
    except Exception:
        return None
    width, height = image.size
    if width < 64 or height < 64:
        return None
    if image.mode not in {"RGB", "RGBA", "L"}:
        image = image.convert("RGB")
    elif image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    elif image.mode == "L":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "image/png", buffer.getvalue()


def _is_blank_pdf_page(page: Any) -> bool:
    """Recognize empty pages and the harmless setup used by PDF generators."""
    try:
        if page.get("/Annots"):
            return False
        contents = page.get_contents()
        return contents is None or all(
            operator in {b"cm", b"q", b"Q", b"BT", b"ET", b"Tf", b"TL"}
            for _, operator in contents.operations
        )
    except Exception:
        # Leave uncertain pages on the existing OCR path.
        return False


def _adapt_pdf_resource(
    resource: SourceResource,
    metadata: dict[str, Any],
    *,
    max_pages: int | None = None,
    figure_gaps: dict[str, tuple[int, int, int]] | None = None,
    keep_multiple_pdf_figures: bool = False,
    keep_repeated_pdf_figures: bool = False,
    keep_pdf_figures_with_margins: bool = False,
    keep_compact_pdf_figures: bool = False,
    skip_blank_pages: bool = False,
    keep_single_line_compact_figures: bool = False,
    keep_wordless_pdf_figures: bool = False,
    step_parser=None,
) -> SourceArtifact:
    """Extract native PDF text and OCR pages that contain no native text."""

    from .ocr import build_ocr_candidates
    from .article_document import segment_plain_article_text
    from .pdf_figure_order import figure_text_gaps, is_single_wordless_figure

    pages: list[Any] = []
    native_text_pages: set[int] = set()
    blank_pages: set[int] = set()
    candidates: list[NormalizationCandidate] = []
    warnings: list[str] = []
    text_extractor_status = "available"

    try:
        from pypdf import PdfReader
    except ImportError:
        text_extractor_status = "unavailable"
        warnings.append("PDF text extractor is not installed")
    else:
        try:
            reader = PdfReader(io.BytesIO(resource.payload))
            if max_pages is None or 0 < len(reader.pages) <= max_pages:
                pages = list(reader.pages)
        except Exception as error:
            text_extractor_status = "failed"
            warnings.append(f"PDF text extraction could not read the document: {error}")
    if max_pages is not None and not pages:
        raise ValueError("embedded PDF has no readable pages within its page limit")

    page_errors: list[dict[str, str]] = []
    page_texts: list[tuple[int, str]] = []
    page_image_digests: dict[str, set[int]] = {}
    page_image_payloads: dict[str, dict[str, Any]] = {}
    multi_figure_groups: list[list[str]] = []
    positioned_images: list[dict[str, Any]] = []
    margin_positions: dict[str, list[tuple[dict[str, Any], tuple[int, int, int]]]] = {}
    margin_pages: dict[str, set[int]] = {}
    compact_figures: list[dict[str, Any]] = []
    compact_positions: dict[str, tuple[int, int, int]] = {}
    wordless_candidates: list[dict[str, Any]] = []
    for index, page in enumerate(pages, start=1):
        try:
            # Keep line breaks so TSB/PDF text can be segmented into headings,
            # steps, and notes instead of one collapsed workshop paragraph.
            raw_text = str(page.extract_text() or "")
            lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw_text.splitlines()]
            text = "\n".join(line for line in lines if line)
        except Exception as error:
            page_errors.append({"locator": f"page:{index}", "error": str(error)})
            continue
        if skip_blank_pages and not text and _is_blank_pdf_page(page):
            blank_pages.add(index)
            continue
        single_line = bool(text) and "\n" not in text and keep_single_line_compact_figures
        extracted_images, page_image_keys = _extract_pdf_page_images(
            page, page_number=index,
            allow_compact_figure=(
                bool(text) and figure_gaps is not None and (keep_compact_pdf_figures or single_line)
                or not text and keep_wordless_pdf_figures
            ),
        )
        if extracted_images and extracted_images[0].get("_compact_pdf_figure") is True:
            [figure] = extracted_images
            if text:
                segments = segment_plain_article_text(text, step_parser=step_parser)
                gaps = figure_text_gaps(page, text, segments, page_image_keys, allow_single_line_figure=single_line)
                if figure["pdf_key"] in gaps:
                    if single_line:
                        figure["_single_line_pdf_figure"] = True
                    compact_figures.append(figure)
                    compact_positions[figure["image_id"]] = (gaps[figure["pdf_key"]], len(segments), 0)
            elif is_single_wordless_figure(page, figure["pdf_key"]):
                wordless_candidates.append(figure)
            # Compact candidates must not alter legacy image or OCR fallback.
            extracted_images = []
        for extracted in extracted_images:
            digest = str(extracted["content_sha256"])
            page_image_digests.setdefault(digest, set()).add(index)
            page_image_payloads.setdefault(digest, extracted)
        if text:
            native_text_pages.add(index)
            page_texts.append((index, text))
            if (figure_gaps is not None and extracted_images and len(extracted_images) == len(page_image_keys)
                    and (keep_multiple_pdf_figures or len(extracted_images) == 1)):
                segments = segment_plain_article_text(text, step_parser=step_parser)
                by_key = {image["pdf_key"]: image["image_id"] for image in extracted_images if image["pdf_key"]}
                if len(by_key) == len(extracted_images):
                    gaps = figure_text_gaps(
                        page, text, segments, page_image_keys,
                        allow_margin_images=keep_repeated_pdf_figures and keep_pdf_figures_with_margins,
                    )
                    if gaps and len(gaps) < len(by_key):
                        if len(gaps) == 1:
                            for image in extracted_images:
                                digest = image["content_sha256"]
                                if image["pdf_key"] in gaps:
                                    position = (gaps[image["pdf_key"]], len(segments), 0)
                                    occurrence = {**image, "url": page_image_payloads[digest]["url"]}
                                    margin_positions.setdefault(digest, []).append((occurrence, position))
                                else:
                                    margin_pages.setdefault(digest, set()).add(index)
                        continue
                    for order, (key, gap) in enumerate(gaps.items()):
                        figure_gaps[by_key[key]] = (gap, len(segments), order)
                    if len(gaps) > 1:
                        multi_figure_groups.append([by_key[key] for key in gaps])
                    if keep_repeated_pdf_figures:
                        for image in extracted_images:
                            if image["image_id"] in figure_gaps:
                                digest = image["content_sha256"]
                                positioned_images.append({**image, "url": page_image_payloads[digest]["url"]})

    # Keep unique images and recurring figures with proven interior placements.
    # Use the large-image fallback only when neither kind of figure remains.
    kept_images = [
        payload
        for digest, payload in page_image_payloads.items()
        if len(page_image_digests.get(digest, ())) == 1
    ]
    repeats = [image for image in positioned_images if len(page_image_digests[image["content_sha256"]]) > 1]
    margin_ids = set()
    if margin_positions and not repeats:
        unique_pages = {image["page"] for image in kept_images}
        proposed = {
            digest: positions for digest, positions in margin_positions.items()
            if len(positions) > 1 and {image["page"] for image, _ in positions} == page_image_digests[digest]
            and unique_pages.isdisjoint(page_image_digests[digest])
        }
        # Preserve any large recurring image the old fallback would retain unless
        # every extracted occurrence is proven to be out in the page margins.
        if proposed and (kept_images or all(
            digest in proposed or payload["byte_count"] < 8_000
            or margin_pages.get(digest) == page_image_digests[digest]
            for digest, payload in page_image_payloads.items()
        )):
            for positions in proposed.values():
                for image, position in positions:
                    repeats.append(image)
                    figure_gaps[image["image_id"]] = position
                    margin_ids.add(image["image_id"])
    repeated_ids = {image["image_id"] for image in repeats}
    if not kept_images and not repeats:
        kept_images = [
            payload
            for payload in page_image_payloads.values()
            if int(payload.get("byte_count") or 0) >= 8_000
        ]
        if figure_gaps is not None:
            # The legacy fallback keeps one copy of recurring artwork.
            figure_gaps.clear()
    kept_images.extend(repeats)
    if figure_gaps is not None and multi_figure_groups:
        kept_ids = {image["image_id"] for image in kept_images}
        for group in multi_figure_groups:
            if any(image_id not in kept_ids for image_id in group):
                for image_id in group:
                    figure_gaps.pop(image_id, None)
    if figure_gaps is not None and compact_figures:
        figure_gaps.update(compact_positions)
        kept_images.extend(compact_figures)
        if keep_repeated_pdf_figures:
            compact_digests = {image["content_sha256"] for image in compact_figures}
            counts = Counter(image["content_sha256"] for image in kept_images if image["content_sha256"] in compact_digests)
            repeated_ids.update(
                image["image_id"] for image in kept_images if counts[image["content_sha256"]] > 1
            )
    covered_pages = native_text_pages | blank_pages
    missing_pages = set(range(1, len(pages) + 1)) - covered_pages if pages else set()
    should_rasterize = bool(missing_pages) or not pages
    rasterization_status = "not_needed"
    extraction_mode = "text_pdf"
    ocr_candidates = []
    wordless_figures = []
    if should_rasterize:
        # Native or known blank pages outside this range never need pixels.
        page_range = (min(missing_pages), max(missing_pages)) if covered_pages and missing_pages else None
        try:
            scanned_blocks = extract_scanned_pdf_text(
                resource.content_sha256, resource.payload, covered_pages, page_range=page_range,
            )
            ocr_candidates = list(build_ocr_candidates(resource.content_sha256, scanned_blocks))
            rasterization_status = "complete"
            extraction_mode = "mixed_pdf_ocr" if native_text_pages else "scanned_pdf_ocr"
            if wordless_candidates:
                recognized_pages = {candidate.data["page_number"] for candidate in ocr_candidates}
                wordless_figures = [figure for figure in wordless_candidates if figure["page"] not in recognized_pages]
                kept_images.extend(wordless_figures)
        except Exception as error:
            rasterization_status = "unavailable"
            warnings.append(str(error))
            extraction_mode = "mixed_pdf_ocr" if native_text_pages else "unavailable"
    figure_records = [
        {
            "url": image["url"],
            "alt": image["alt"],
            "image_id": image["image_id"],
            "media_type": image["media_type"],
            "content_sha256": image["content_sha256"],
            "page": image["page"],
            **({"_retained_repeated_pdf_figure": True} if image["image_id"] in repeated_ids else {}),
            **({"_retained_pdf_figure_with_margins": True} if image["image_id"] in margin_ids else {}),
            **({"_compact_pdf_figure": True} if image.get("_compact_pdf_figure") is True else {}),
            **({"_single_line_pdf_figure": True} if image.get("_single_line_pdf_figure") is True else {}),
        }
        for image in kept_images
    ]
    for index, text in page_texts:
        payload = {"text": text}
        # Carry extracted figures on the first text page so article join sees them.
        if figure_records and index == page_texts[0][0]:
            payload["images"] = figure_records
        candidates.append(
            NormalizationCandidate(
                "document_text",
                f"document-text:{resource.content_sha256}:page:{index}",
                payload,
                f"page:{index}",
            )
        )
    if figure_records and not page_texts:
        candidates.append(
            NormalizationCandidate(
                "document_text",
                f"document-text:{resource.content_sha256}:figures",
                {"text": " ", "images": figure_records},
                "page:figures",
            )
        )

    candidates.extend(ocr_candidates)

    extraction_metadata: dict[str, Any] = {
        **metadata,
        "page_count": len(pages),
        "text_extractor_status": text_extractor_status,
        "extracted_page_count": len({
            candidate.locator.split(":", 1)[1]
            for candidate in candidates
            if candidate.kind == "document_text" and candidate.locator.startswith("page:")
        }),
        "extracted_region_count": sum(candidate.kind == "image_text" for candidate in candidates),
        "rasterized_page_count": len(missing_pages) if pages else None,
        "rasterization_status": rasterization_status,
        "extraction_mode": extraction_mode,
        "extraction_status": "candidate_ready" if candidates else "needs_review",
        **({"skipped_blank_pages": True} if blank_pages else {}),
        **({"retained_wordless_pdf_figures": True} if wordless_figures else {}),
    }
    if page_errors:
        extraction_metadata["page_errors"] = page_errors
    if warnings:
        extraction_metadata["extraction_warnings"] = warnings
        extraction_metadata["extraction_error"] = "; ".join(warnings)
    return SourceArtifact(
        kind="document",
        source_uri=resource.source_uri,
        source_version=resource.source_version,
        media_type=resource.media_type,
        content_sha256=resource.content_sha256,
        payload=resource.payload,
        raw_payload=resource.payload,
        metadata=extraction_metadata,
        candidates=tuple(candidates),
    )


def _adapt_svg_resource(
    resource: SourceResource,
    metadata: dict[str, Any],
) -> SourceArtifact:
    """Extract literal SVG labels while leaving geometry as an opaque diagram."""

    try:
        lowered = resource.payload.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise ValueError("SVG DTD and entity declarations are not supported")
        root = ElementTree.fromstring(resource.payload)
    except (ElementTree.ParseError, ValueError) as error:
        return _binary_artifact(
            "diagram",
            resource,
            {**metadata, "extraction_status": "needs_review", "extraction_error": str(error)},
        )

    candidates: list[NormalizationCandidate] = []
    counts: dict[str, int] = {}
    for element in root.iter():
        tag = _local_name(str(element.tag)).casefold()
        if tag not in {"title", "desc", "text"}:
            continue
        text = re.sub(r"\s+", " ", " ".join(element.itertext())).strip()
        if not text:
            continue
        counts[tag] = counts.get(tag, 0) + 1
        candidates.append(
            NormalizationCandidate(
                "diagram_text",
                f"diagram-text:{resource.content_sha256}:{tag}:{counts[tag]}",
                {"text": text},
                f"svg:{tag}[{counts[tag]}]",
            )
        )

    extraction_metadata: dict[str, Any] = {
        **metadata,
        "extracted_label_count": len(candidates),
        "extraction_status": "candidate_ready" if candidates else "needs_review",
    }
    return SourceArtifact(
        kind="diagram",
        source_uri=resource.source_uri,
        source_version=resource.source_version,
        media_type=resource.media_type,
        content_sha256=resource.content_sha256,
        payload=resource.payload,
        raw_payload=resource.payload,
        metadata=extraction_metadata,
        candidates=tuple(candidates),
    )


def extract_image_text(
    content_sha256: str,
    payload: bytes,
    media_type: str,
) -> Iterable[Any]:
    """Load the configured OCR provider lazily to keep intake provider-neutral."""

    from .ocr import extract_image_text as extract

    return extract(content_sha256, payload, media_type)


def extract_scanned_pdf_text(
    content_sha256: str,
    payload: bytes,
    native_text_pages: Iterable[int] = (),
    *,
    page_range: tuple[int, int] | None = None,
) -> Iterable[Any]:
    """Load the optional PDF rasterizer/OCR provider lazily for testable intake."""

    from .pdf_ocr import extract_scanned_pdf_text as extract

    return extract(content_sha256, payload, native_text_pages, page_range=page_range)


def _adapt_image_resource(
    resource: SourceResource,
    metadata: dict[str, Any],
) -> SourceArtifact:
    """Run optional OCR and retain the original image when it is unavailable."""

    from .ocr import build_ocr_candidates

    try:
        blocks = extract_image_text(resource.content_sha256, resource.payload, resource.media_type)
        candidates = build_ocr_candidates(resource.content_sha256, blocks)
    except Exception as error:
        return _binary_artifact(
            "document",
            resource,
            {
                **metadata,
                "media_role": "image",
                "extraction_status": "needs_review",
                "extraction_error": f"image OCR unavailable: {error}",
            },
        )
    return SourceArtifact(
        kind="document",
        source_uri=resource.source_uri,
        source_version=resource.source_version,
        media_type=resource.media_type,
        content_sha256=resource.content_sha256,
        payload=resource.payload,
        raw_payload=resource.payload,
        metadata={
            **metadata,
            "media_role": "image",
            "extracted_region_count": len(candidates),
            "extraction_status": "candidate_ready" if candidates else "needs_review",
        },
        candidates=tuple(candidates),
    )


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "template"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "template"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _html_text(payload: bytes) -> str:
    parser = _VisibleTextParser()
    parser.feed(payload.decode("utf-8-sig"))
    parser.close()
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


class _VisibleLinesParser(_VisibleTextParser):
    """Visible-text extraction that keeps block boundaries as line breaks."""

    _BLOCK_TAGS = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "section", "article"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        super().handle_starttag(tag, attrs)
        if tag.casefold() == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        super().handle_endtag(tag)
        if tag.casefold() in self._BLOCK_TAGS:
            self.parts.append("\n")


def _html_lines(payload: bytes) -> str:
    parser = _VisibleLinesParser()
    parser.feed(payload.decode("utf-8-sig"))
    parser.close()
    lines = []
    for raw in "".join(parser.parts).splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _html_media_references(resource: SourceResource) -> list[dict[str, str]]:
    parser = _ArticleHTMLParser()
    parser.feed(resource.payload.decode("utf-8-sig"))
    parser.close()
    return [dict(image) for image in parser.images]


class _ArticleHTMLParser(HTMLParser):
    """Collect low-risk HTML metadata without interpreting arbitrary markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, list[str]] = {}
        self.headings: list[str] = []
        self._heading_parts: list[str] | None = None
        self._title_parts: list[str] | None = None
        self._title_value = ""
        self._json_ld_parts: list[str] | None = None
        self.json_ld: list[str] = []
        self.has_article_element = False
        self._article_depth = 0
        self._article_ignored_depth = 0
        self._article_body_parts: list[str] = []
        self._list_item_parts: list[str] | None = None
        self.ordered_items: list[str] = []
        self.images: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {
            str(key).casefold(): str(value).strip()
            for key, value in attrs
            if value is not None
        }
        normalized_tag = tag.casefold()
        if normalized_tag == "article":
            self.has_article_element = True
            self._article_depth += 1
        elif self._article_depth and normalized_tag in {"script", "style", "template"}:
            self._article_ignored_depth += 1
        if normalized_tag == "meta":
            key = attributes.get("name") or attributes.get("property") or attributes.get("itemprop")
            content = attributes.get("content", "")
            if key and content:
                self.meta.setdefault(key.casefold(), []).append(content)
        elif normalized_tag == "title":
            self._title_parts = []
        elif normalized_tag in {"h1", "h2", "h3"}:
            self._heading_parts = []
        elif normalized_tag == "li":
            self._list_item_parts = []
        elif normalized_tag == "script" and attributes.get("type", "").casefold() == "application/ld+json":
            self._json_ld_parts = []
        elif normalized_tag == "img" and attributes.get("src"):
            image = {"url": attributes["src"]}
            if attributes.get("alt"):
                image["alt"] = attributes["alt"]
            self.images.append(image)
        elif normalized_tag == "mtr-image" and attributes.get("id"):
            image = {"image_id": attributes["id"]}
            if attributes.get("alt"):
                image["alt"] = attributes["alt"]
            self.images.append(image)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.casefold()
        if normalized_tag == "article" and self._article_depth:
            self._article_depth -= 1
        elif (
            self._article_depth
            and normalized_tag in {"script", "style", "template"}
            and self._article_ignored_depth
        ):
            self._article_ignored_depth -= 1
        if normalized_tag == "title" and self._title_parts is not None:
            self._title_value = _compact_text(" ".join(self._title_parts))
            self._title_parts = None
        elif normalized_tag in {"h1", "h2", "h3"} and self._heading_parts is not None:
            value = _compact_text(" ".join(self._heading_parts))
            if value:
                self.headings.append(value)
            self._heading_parts = None
        elif normalized_tag == "li" and self._list_item_parts is not None:
            value = _compact_text(" ".join(self._list_item_parts))
            if value:
                self.ordered_items.append(value)
            self._list_item_parts = None
        elif normalized_tag == "script" and self._json_ld_parts is not None:
            value = "".join(self._json_ld_parts).strip()
            if value:
                self.json_ld.append(value)
            self._json_ld_parts = None

    def handle_data(self, data: str) -> None:
        if self._article_depth and not self._article_ignored_depth:
            self._article_body_parts.append(data)
        if self._title_parts is not None:
            self._title_parts.append(data)
        if self._heading_parts is not None:
            self._heading_parts.append(data)
        if self._list_item_parts is not None:
            self._list_item_parts.append(data)
        if self._json_ld_parts is not None:
            self._json_ld_parts.append(data)

    @property
    def title(self) -> str:
        return self._title_value

    @property
    def article_body(self) -> str:
        return _compact_text(" ".join(self._article_body_parts))


def _html_article_candidates(
    resource: SourceResource, *, parser: _ArticleHTMLParser | None = None
) -> list[NormalizationCandidate]:
    """Extract one article and any explicit vehicle identity from generic HTML."""

    if parser is None:
        parser = _ArticleHTMLParser()
        parser.feed(resource.payload.decode("utf-8-sig"))
        parser.close()
    json_ld_records = _json_ld_records(parser.json_ld)

    vehicle_values = _meta_values(
        parser.meta,
        "vehicle",
        "vehicle.name",
        "vehicle_name",
        "dc.vehicle",
    )
    article_meta_title = _first_meta_value(parser.meta, "og:title", "article:title", "headline")
    article_values: dict[str, Any] = {
        "title": article_meta_title or parser.title,
        "id": _first_meta_value(parser.meta, "article:id", "article_id", "dc.identifier", "identifier"),
        "bucket": _first_meta_value(parser.meta, "article:section", "article_section", "section", "category"),
        "releaseDate": _first_meta_value(
            parser.meta, "article:published_time", "datepublished", "date_published", "published_time"
        ),
        "bulletinNumber": _first_meta_value(
            parser.meta, "article:bulletin_number", "bulletin_number", "bulletin", "tsb"
        ),
        "body": parser.article_body,
        "steps": parser.ordered_items or None,
        "images": parser.images,
    }
    for record in json_ld_records:
        record_types = _json_ld_types(record)
        if any("article" in record_type for record_type in record_types):
            article_values = {
                **article_values,
                "title": _json_ld_text(record, "headline", "name") or article_values["title"],
                "id": _json_ld_text(record, "identifier", "articleBodyId") or article_values["id"],
                "bucket": _json_ld_text(record, "articleSection", "section") or article_values["bucket"],
                "releaseDate": _json_ld_text(record, "datePublished") or article_values["releaseDate"],
                "bulletinNumber": _json_ld_text(record, "bulletinNumber") or article_values["bulletinNumber"],
                "body": _json_ld_text(record, "articleBody") or article_values["body"],
                "steps": _json_ld_steps(record) or article_values["steps"],
            }
        for field in ("vehicle", "about", "mainEntity"):
            value = record.get(field)
            if isinstance(value, str):
                vehicle_values.append(value.strip())
            elif isinstance(value, dict):
                name = _json_ld_text(value, "name", "vehicleName")
                if name:
                    vehicle_values.append(name)

    candidates: list[NormalizationCandidate] = []
    for index, display_name in enumerate(dict.fromkeys(value for value in vehicle_values if value)):
        identity = parse_vehicle_display_name(display_name)
        if identity is None:
            continue
        candidates.append(
            NormalizationCandidate(
                "vehicle_identity",
                f"vehicle-identity:html:{index}",
                identity,
                f"html:vehicle[{index}]",
            )
        )

    article_signal = bool(
        article_values["title"]
        or article_meta_title
        or parser.has_article_element
        or any("article" in record_type for record in json_ld_records for record_type in _json_ld_types(record))
        or ("/article/" in resource.source_uri.casefold() and bool(parser.headings))
    )
    title = _compact_text(
        str(article_values.get("title") or (parser.headings[0] if article_signal and parser.headings else ""))
    )
    if title:
        article_id = _compact_text(str(article_values.get("id") or ""))
        if not article_id:
            article_id = f"url:{hashlib.sha256(resource.source_uri.encode()).hexdigest()[:24]}"
        article_data = {
            "id": article_id,
            "title": title,
            "bucket": _compact_text(str(article_values.get("bucket") or "")) or None,
            "bulletinNumber": _compact_text(str(article_values.get("bulletinNumber") or "")) or None,
            "releaseDate": _compact_text(str(article_values.get("releaseDate") or "")) or None,
        }
        body = _compact_text(str(article_values.get("body") or ""))
        if body:
            article_data["body"] = body
        steps = article_values.get("steps")
        if isinstance(steps, list) and all(isinstance(step, (str, dict)) for step in steps):
            article_data["steps"] = steps
        images = article_values.get("images")
        if isinstance(images, list):
            article_data["images"] = [
                {
                    **image,
                    "url": urljoin(resource.source_uri, str(image["url"])),
                }
                for image in images
                if isinstance(image, dict) and str(image.get("url") or "").strip()
            ]
        candidates.append(
            NormalizationCandidate(
                "article",
                f"article:{article_id}:html",
                article_data,
                "html:article",
            )
        )
    return candidates


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _meta_values(meta: dict[str, list[str]], *keys: str) -> list[str]:
    return [value for key in keys for value in meta.get(key.casefold(), [])]


def _first_meta_value(meta: dict[str, list[str]], *keys: str) -> str:
    values = _meta_values(meta, *keys)
    return values[0] if values else ""


def _json_ld_records(values: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for value in values:
        try:
            document = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            continue
        records.extend(_flatten_json_ld(document))
    return records


def _flatten_json_ld(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        records = [value]
        graph = value.get("@graph")
        if isinstance(graph, list):
            records.extend(item for item in graph if isinstance(item, dict))
        return records
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _json_ld_types(record: dict[str, Any]) -> set[str]:
    value = record.get("@type")
    values = value if isinstance(value, list) else [value]
    return {str(item).casefold() for item in values if item}


def _json_ld_text(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, (str, int, float)):
            return str(value).strip()
        if isinstance(value, dict):
            nested = value.get("value") or value.get("name")
            if nested:
                return str(nested).strip()
    return ""


def _json_ld_steps(record: dict[str, Any]) -> list[Any] | None:
    value = record.get("steps")
    if isinstance(value, list) and value and all(isinstance(step, (str, dict)) for step in value):
        return value
    return None


def _candidate_from_record(
    record: dict[str, Any],
    locator: str,
    record_type: str | None = None,
) -> NormalizationCandidate | None:
    kind = _field(record, "record_type", "recordType", "type", "kind")
    kind = (record_type or kind or "").replace("_", "").replace("-", "").casefold()
    make = _field(record, "make", "manufacturer")
    model = _field(record, "model", "model_name", "modelName")
    year = _field(record, "year", "model_year", "modelYear")
    region = _field(record, "region", "market")
    if kind in {"vehicle", "vehicleidentity"} or (make and model and year):
        data = {"make": make, "model": model, "year": _number_or_text(year)}
        if region:
            data["region"] = region
        trim = _field(record, "trim", "variant")
        if trim:
            data["trim"] = trim
        body_style = _field(record, "body_style", "bodyStyle", "body_type", "bodyType")
        if body_style:
            data["body_style"] = body_style
        drivetrain = _field(
            record,
            "drivetrain",
            "drive_train",
            "driveType",
            "drive_type",
        )
        if drivetrain:
            data["drivetrain"] = drivetrain
        engine = _field(
            record,
            "engine",
            "engine_displacement_l",
            "engineDisplacementL",
            "engine_size",
            "engineSize",
        )
        if engine:
            data["engine"] = engine
        return NormalizationCandidate("vehicle_identity", f"vehicle-identity:{locator}", data, locator)

    if kind in {"specification", "spec", "fluid", "dimension"}:
        return _candidate_from_specification(record, locator)

    part_number = _field(record, "part_number", "partNumber", "part_no", "partNo")
    if kind == "part" or part_number:
        if not part_number:
            return None
        data = {
            "partNumber": part_number,
            "partDescription": _field(record, "part_description", "partDescription", "description"),
        }
        for source_name, target_name in (
            ("quantity", "quantity"),
            ("price", "price"),
            ("currency", "currency"),
        ):
            value = _field(record, source_name)
            if value:
                data[target_name] = value
        return NormalizationCandidate("part", f"part:{part_number}:{locator}", data, locator)

    model_id = _field(record, "id", "model_id", "modelId")
    if kind == "model" or (model_id and model):
        if not model_id or not model:
            return None
        return NormalizationCandidate(
            "model",
            f"model:{model_id}:{locator}",
            {"id": model_id, "model": model},
            locator,
        )

    article_id = _field(record, "article_id", "articleId", "id")
    title = _field(record, "title", "name")
    if kind == "article" or (article_id and title):
        if not article_id or not title:
            return None
        data = {
            "id": article_id,
            "title": title,
            "bucket": _field(record, "bucket", "category"),
            "bulletinNumber": _field(record, "bulletin_number", "bulletinNumber"),
            "releaseDate": _field(record, "release_date", "releaseDate"),
        }
        body = _field(record, "body", "article_body", "articleBody", "content")
        if body:
            data["body"] = body
        steps = record.get("steps")
        if isinstance(steps, list) and all(isinstance(step, (str, dict)) for step in steps):
            data["steps"] = steps
        blocks = record.get("blocks")
        if isinstance(blocks, list):
            # Preserve the adapter's ordered source stream.  The normalizer
            # will create the authoritative document; flattening it here
            # would permanently lose tables and interleaved media.
            data["blocks"] = blocks
        if record.get("normalized_document"):
            data["normalized_document"] = record["normalized_document"]
        source_original = record.get("source_original", record.get("sourceOriginal"))
        if source_original not in (None, ""):
            data["source_original"] = source_original
        for source_name in ("images", "imageUrls", "image_urls", "diagrams", "media"):
            value = record.get(source_name)
            if value:
                data[source_name] = value
        return NormalizationCandidate(
            "article",
            f"article:{article_id}:{locator}",
            data,
            locator,
        )
    return None


def _candidate_from_specification(
    record: dict[str, Any], locator: str
) -> NormalizationCandidate | None:
    name = _field(record, "name", "specification_name", "specificationName", "key")
    if not name:
        return None
    value = next(
        (record[key] for key in ("value", "specification_value", "specificationValue") if key in record),
        None,
    )
    if value is None:
        return None
    unit = _field(record, "unit", "units") or None
    return NormalizationCandidate(
        "specification",
        f"specification:{name}:{locator}",
        {"name": name, "value": value, "unit": unit},
        locator,
    )


def _field(record: dict[str, Any], *names: str) -> str:
    normalized = {
        re.sub(r"[^a-z0-9]", "", str(key).casefold()): str(value).strip()
        for key, value in record.items()
        if key is not None and value is not None
    }
    for name in names:
        value = normalized.get(re.sub(r"[^a-z0-9]", "", name.casefold()), "")
        if value:
            return value
    return ""


def _number_or_text(value: str) -> int | str:
    try:
        return int(value)
    except ValueError:
        return value


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


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


def _looks_like_bound_article_xml(text: str) -> bool:
    """Recognize leading XML syntax without treating comparison prose as XML."""
    leading = text.lstrip("\ufeff \t\r\n")
    if re.match(r"<(?:[!?]|/?[A-Za-z_][\w:.-]*(?=[\s/>]|$))", leading) is None:
        return False
    # Preserve the existing nested HTML path. Unknown XML roots must not become
    # fabricated prose, even when their children happen to use HTML tag names.
    html_leading = re.sub(r"^(?:<!--.*?-->\s*)+", "", leading, flags=re.S)
    html_leading = re.sub(
        r"^<!doctype\s+html(?:\s+[^>\[]*)?>\s*", "", html_leading, flags=re.I
    )
    html_root = re.match(r"<([A-Za-z][\w.-]*)(?=[\s/>])", html_leading)
    html_tags = {
        "a", "abbr", "address", "area", "article", "aside", "audio", "b", "base",
        "bdi", "bdo", "blockquote", "body", "br", "button", "canvas", "caption",
        "center", "cite", "code", "col", "colgroup", "data", "datalist", "dd",
        "del", "details", "dfn", "dialog", "div", "dl", "dt", "em", "embed",
        "fieldset", "figcaption", "figure", "font", "footer", "form", "h1", "h2",
        "h3", "h4", "h5", "h6", "head", "header", "hgroup", "hr", "html", "i",
        "iframe", "img", "input", "ins", "kbd", "label", "legend", "li", "link",
        "main", "map", "mark", "menu", "meta", "meter", "nav", "noscript", "object",
        "ol", "optgroup", "option", "output", "p", "picture", "pre", "progress",
        "q", "rp", "rt", "ruby", "s", "samp", "script", "search", "section",
        "select", "slot", "small", "source", "span", "strong", "style", "sub",
        "summary", "sup", "table", "tbody", "td", "template", "textarea", "tfoot",
        "th", "thead", "time", "title", "tr", "track", "u", "ul", "var", "video", "wbr",
    }
    return not (html_root and html_root.group(1).casefold() in html_tags)


def _maintenance_xml_blocks(text: str) -> list[dict[str, Any]]:
    """Project only the observed, fixed-depth maintenance grammar into blocks."""
    error = "invalid maintenance XML"
    # Reject declarations before invoking Expat; no entity or external-resource
    # resolution is part of this adapter. Decode bytes before this check so
    # alternate byte encodings cannot bypass it.
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
        raise ValueError(error)

    class MaintenanceTreeBuilder(ElementTree.TreeBuilder):
        def start_ns(self, prefix, uri):
            # Includes unused namespace declarations that ElementTree would
            # otherwise discard, as well as namespaced elements/attributes.
            raise ValueError(error)

    try:
        root = ElementTree.fromstring(
            text.lstrip("\ufeff"),
            parser=ElementTree.XMLParser(target=MaintenanceTreeBuilder(
                insert_comments=True, insert_pis=True
            )),
        )
    except ElementTree.ParseError:
        raise ValueError(error) from None

    blocks: list[dict[str, Any]] = []

    def attributes(node, tag, names):
        if node.tag != tag or set(node.attrib) != names:
            raise ValueError(error)

    def structure(node, allowed):
        if (node.text or "").strip():
            raise ValueError(error)
        for child in node:
            if child.tag not in allowed or (child.tail or "").strip():
                raise ValueError(error)

    def heading(node, level):
        blocks.append({
            "kind": "heading", "level": level,
            "text": f"{node.attrib['name']} ({node.attrib['id']})",
        })

    def content(node):
        attributes(node, node.tag, set())

        def text_block(value):
            if value and value.strip():
                # All XML fields are explicit source notes, not unstructured
                # prose: avoid plain-text page/number/step inference here.
                blocks.append({"kind": "callout", "label": node.tag.title(), "text": value})

        text_block(node.text)
        for child in node:
            if node.tag != "notes":
                raise ValueError(error)
            if child.tag == "br":
                attributes(child, "br", set())
                if child.text or len(child):
                    raise ValueError(error)
            elif child.tag == "a":
                attributes(child, "a", {"href"})
                if len(child) or not (child.text or "").strip():
                    raise ValueError(error)
                blocks.append({
                    # Capture strips raw href/url fields. The existing target
                    # alias reaches the normalizer's same safe-link filter.
                    "kind": "link", "text": child.text, "target": child.attrib["href"],
                })
            else:
                raise ValueError(error)
            text_block(child.tail)

    attributes(root, "maintenance_schedule", {"title"})
    structure(root, {"operation", "footnote"})
    blocks.append({"kind": "heading", "level": 1, "text": root.attrib["title"]})
    for operation in root:
        if operation.tag == "footnote":
            content(operation)
            continue
        attributes(operation, "operation", {"id", "name"})
        structure(operation, {"component"})
        heading(operation, 2)
        for component in operation:
            attributes(component, "component", {"id", "name"})
            structure(component, {"notes", "warranty", "qualifier"})
            heading(component, 3)
            for field in component:
                content(field)
    return blocks


def adapt_bound_article(
    resource: SourceResource, context, *, keep_embedded_pdf: bool = False,
    keep_html_headings: bool = False, keep_bound_pdf_iframes: bool = False,
    keep_html_section_titles: bool = False,
    keep_bankone_html_flow: bool = False,
    keep_pdf_figure_order: bool = False, keep_multiple_pdf_figures: bool = False,
    keep_html_table_image_order: bool = False,
    keep_repeated_pdf_figures: bool = False, keep_pdf_figures_with_margins: bool = False,
    keep_compact_pdf_figures: bool = False,
    keep_html_figure_captions: bool = False,
    keep_html_table_captions: bool = False,
    keep_html_media_table_headers: bool = False,
    keep_html_table_spans: bool = False,
    keep_html_nested_tables: bool = False,
    keep_html_numeric_superscripts: bool = False,
    keep_html_document_links: bool = False,
    keep_mixed_html_pdf_embeds: bool = False,
    keep_html_flow_figure_captions: bool = False,
    keep_html_multiline_figure_captions: bool = False,
    keep_structured_table_cell_order: bool = False,
    keep_image_only_headings: bool = False,
    keep_ordered_step_instructions: bool = False,
    keep_image_only_step_instructions: bool = False,
    keep_bound_html_images: bool = False,
    skip_noscript_images: frozenset[tuple[int, int]] = frozenset(),
    lazy_image_alts: dict[tuple[int, int], str] | None = None,
    declared_image_refs: frozenset[str] = frozenset(),
    step_parser=None, resolved_pdf_refs: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Adapt fetched bytes under proven connector scope, without weakening URL intake."""
    from .banktwo_connector import ArticleParser
    from .article_document import image_only_heading_figures, ordered_numbered_step, segment_plain_article_text
    from .article_lifecycle_types import ORDERED_STEP_IMAGE_ONLY_LAYOUT, ORDERED_STEP_INSTRUCTIONS_LAYOUT

    def project_html(html_resource, *, include_untyped_pdf_positions=False):
        html = html_resource.payload.decode("utf-8-sig")
        parser = ArticleParser(
            asset_bindings=html_resource.metadata.get("asset_bindings", []),
            preserve_legacy_list_starts=False,
            keep_html_headings=keep_html_headings,
            keep_html_section_titles=keep_html_section_titles,
            keep_bankone_html_flow=keep_bankone_html_flow and context.key.provider == "bankone",
            keep_bound_pdf_iframes=keep_bound_pdf_iframes,
            resolved_pdf_refs=resolved_pdf_refs,
            include_untyped_pdf_positions=include_untyped_pdf_positions,
            keep_html_table_image_order=keep_html_table_image_order,
            keep_html_figure_captions=keep_html_figure_captions,
            keep_html_table_captions=keep_html_table_captions,
            keep_html_media_table_headers=keep_html_media_table_headers,
            keep_html_table_spans=keep_html_table_spans,
            keep_html_nested_tables=keep_html_nested_tables,
            keep_html_numeric_superscripts=keep_html_numeric_superscripts,
            keep_html_document_links=keep_html_document_links,
            keep_html_flow_figure_captions=keep_html_flow_figure_captions,
            keep_html_multiline_figure_captions=keep_html_multiline_figure_captions,
            keep_bound_html_images=keep_bound_html_images and not include_untyped_pdf_positions,
            skip_noscript_images=skip_noscript_images,
            lazy_image_alts=lazy_image_alts,
            declared_image_refs=declared_image_refs,
        )
        parser.feed(html)
        parser.close()
        parser.flush()
        # Check explicit structured vehicle metadata independently of body text.
        metadata_parser = _ArticleHTMLParser()
        metadata_parser.feed(html)
        metadata_parser.close()
        for field, keys in {
            "year": ("vehicle.year", "vehicle_year", "year"),
            "make": ("vehicle.make", "vehicle_make"),
            "model": ("vehicle.model", "vehicle_model"),
        }.items():
            supplied = _first_meta_value(metadata_parser.meta, *keys)
            if (
                supplied
                and field in context.vehicle
                and supplied != str(context.vehicle[field])
            ):
                raise ValueError("wrong applicability")
        for candidate in _html_article_candidates(html_resource, parser=metadata_parser):
            if candidate.kind == "vehicle_identity":
                for field in ("year", "make", "model"):
                    if (
                        field in candidate.data
                        and field in context.vehicle
                        and str(candidate.data[field]) != str(context.vehicle[field])
                    ):
                        raise ValueError("wrong applicability")
        return {
            "blocks": parser.blocks,
            "asset_resource_refs": [],
            **({"authored_html_headings": True} if keep_html_headings else {}),
            **({"html_section_titles": True} if parser.html_section_titles else {}),
            **({"bankone_html_flow": True} if parser.bankone_html_flow else {}),
            **({"handled_pdf_embeds": True} if parser.handled_pdf_embeds else {}),
            **({"untyped_pdf_embed_refs": tuple(parser.untyped_pdf_embed_refs)} if parser.untyped_pdf_embed_refs else {}),
            **({"positioned_html_table_images": True} if parser.positioned_html_table_images else {}),
            **({"html_figure_captions": True} if parser.html_figure_captions else {}),
            **({"html_flow_figure_captions": True} if parser.html_flow_figure_captions else {}),
            **({"html_multiline_figure_captions": True} if parser.html_multiline_figure_captions else {}),
            **({"html_table_captions": True} if parser.html_table_captions else {}),
            **({"html_media_table_headers": True} if parser.html_media_table_headers else {}),
            **({"html_table_spans": True} if parser.html_table_spans else {}),
            **({"html_nested_tables": True} if parser.html_nested_tables else {}),
            **({"html_numeric_superscripts": True} if parser.html_numeric_superscripts else {}),
            **({"html_document_links": True} if parser.html_document_links else {}),
            **({"html_bound_images": True} if parser.html_bound_images else {}),
            **({"html_image_mirrors": frozenset(parser.html_image_mirrors)} if parser.html_image_mirrors else {}),
            **({"html_lazy_image_alts": parser.html_lazy_image_alts} if parser.html_lazy_image_alts else {}),
        }

    media = resource.media_type.split(";", 1)[0]
    if media in {"application/json", "application/hal+json"}:
        value = json.loads(resource.payload)
        if not isinstance(value, dict):
            raise ValueError("invalid article document")
        if media == "application/hal+json":
            embedded = value.get("_embedded")
            data = embedded.get("data") if isinstance(embedded, dict) else None
            article = data.get("article") if isinstance(data, dict) else None
            if not isinstance(article, dict) or (
                "content" in article and not isinstance(article["content"], str)
            ):
                raise ValueError("invalid article document")
        identity_layers = [value]
        embedded = value.get("_embedded")
        if isinstance(embedded, dict) and isinstance(embedded.get("data"), dict):
            identity_layers.append(embedded)
            value = embedded["data"]
            identity_layers.append(value)
        article = value.get("article", value)
        if not isinstance(article, dict):
            raise ValueError("invalid article document")
        if article is not value:
            identity_layers.append(article)
        blocks = article.get("blocks")
        needs_blocks = not isinstance(blocks, list) or not blocks
        embedded_pdf = None
        embedded_text = ""
        if keep_embedded_pdf and needs_blocks and not article.get("steps"):
            nested_body = article.get("body")
            if isinstance(nested_body, dict) and "pdf" in nested_body:
                embedded_pdf = nested_body
                identity_layers.append(nested_body)
            elif "pdf" in article:
                embedded_pdf = article
            if embedded_pdf is not None:
                embedded_text = next((
                    article[field] for field in ("body", "text", "content")
                    if isinstance(article.get(field), str) and article[field].strip()
                ), "")
        aliases = {
            "model_year": "year",
            "vehicle_id": "vehicle_id",
            "vehicle_configuration_id": "vehicle_configuration_id",
            "source_vehicle_ref": "source_vehicle_ref",
        }
        expected = {
            **context.vehicle,
            "vehicle_id": str(context.key.vehicle_id),
            "vehicle_configuration_id": (
                str(context.key.vehicle_configuration_id)
                if context.key.vehicle_configuration_id
                else None
            ),
            "source_vehicle_ref": context.key.source_vehicle_ref,
        }
        for layer in identity_layers:
            explicit = layer.get("vehicle") or {}
            if not isinstance(explicit, dict):
                raise ValueError("wrong applicability")
            for field, actual in explicit.items():
                key = aliases.get(field, field)
                if key in expected and str(actual) != str(expected[key]):
                    raise ValueError("wrong applicability")
            for field in (
                "vehicle_id",
                "vehicle_configuration_id",
                "source_vehicle_ref",
            ):
                if field in layer and str(layer[field]) != str(expected[field]):
                    raise ValueError("wrong applicability")
        if needs_blocks:
            if article.get("steps"):
                blocks = [
                    {
                        "kind": "step",
                        "number": i,
                        **({"text": s} if isinstance(s, str) else {
                            field: s[field]
                            for field in ("text", "instruction", "description", "instructions", "images")
                            if field in s
                        }),
                    }
                    for i, s in enumerate(article["steps"], 1)
                ]
            elif embedded_pdf is not None and not embedded_text:
                payload = _decode_embedded_pdf(embedded_pdf["pdf"], max_bytes=_MAX_BOUND_EMBEDDED_PDF_BYTES)
                nested = SourceResource.from_bytes(
                    resource.source_uri, resource.source_version, payload, "application/pdf",
                    locator="body.pdf",
                    metadata={"embedded_in_content_sha256": resource.content_sha256},
                )
                return {
                    **adapt_bound_pdf_embed(
                        nested, keep_pdf_figure_order=keep_pdf_figure_order,
                        keep_multiple_pdf_figures=keep_multiple_pdf_figures,
                        keep_repeated_pdf_figures=keep_repeated_pdf_figures,
                        keep_pdf_figures_with_margins=keep_pdf_figures_with_margins,
                        keep_compact_pdf_figures=keep_compact_pdf_figures,
                        step_parser=step_parser,
                    ),
                    "asset_resource_refs": article.get("asset_resource_refs", []),
                    "embedded_pdf": True,
                }
            else:
                text = embedded_text or str(
                    article.get("body")
                    or article.get("text")
                    or article.get("content")
                    or ""
                )
                if _looks_like_bound_article_xml(text):
                    return {
                        "blocks": _maintenance_xml_blocks(text),
                        "asset_resource_refs": article.get("asset_resource_refs", []),
                    }
                # Anchor labels need HTML parsing even on a pinned source
                # whose PDF-link projection remains disabled.
                html_tags = r"a(?=[\s/>])|p|div|ol|ul|li|table|h[1-6]|script|style|img"
                if keep_bound_pdf_iframes:
                    html_tags += r"|iframe|object|embed"
                if re.search(rf"</?(?:{html_tags})\b", text, re.I):
                    nested = SourceResource.from_bytes(
                        resource.source_uri,
                        resource.source_version,
                        text.encode(),
                        "text/html",
                        resource.locator,
                        resource.metadata,
                    )
                    return adapt_bound_article(
                        nested, context, keep_html_headings=keep_html_headings,
                        keep_html_section_titles=keep_html_section_titles,
                        keep_bankone_html_flow=keep_bankone_html_flow,
                        keep_bound_pdf_iframes=keep_bound_pdf_iframes,
                        resolved_pdf_refs=resolved_pdf_refs,
                        keep_pdf_figure_order=keep_pdf_figure_order,
                        keep_multiple_pdf_figures=keep_multiple_pdf_figures,
                        keep_html_table_image_order=keep_html_table_image_order,
                        keep_repeated_pdf_figures=keep_repeated_pdf_figures,
                        keep_pdf_figures_with_margins=keep_pdf_figures_with_margins,
                        keep_compact_pdf_figures=keep_compact_pdf_figures,
                        keep_html_figure_captions=keep_html_figure_captions,
                        keep_html_table_captions=keep_html_table_captions,
                        keep_html_media_table_headers=keep_html_media_table_headers,
                        keep_html_table_spans=keep_html_table_spans,
                        keep_html_nested_tables=keep_html_nested_tables,
                        keep_html_numeric_superscripts=keep_html_numeric_superscripts,
                        keep_html_document_links=keep_html_document_links,
                        keep_html_flow_figure_captions=keep_html_flow_figure_captions,
                        keep_html_multiline_figure_captions=keep_html_multiline_figure_captions,
                        keep_bound_html_images=keep_bound_html_images,
                        skip_noscript_images=skip_noscript_images,
                        lazy_image_alts=lazy_image_alts,
                        declared_image_refs=declared_image_refs,
                        step_parser=step_parser,
                    )
                blocks = segment_plain_article_text(text, step_parser=step_parser)
        image_only_headings = False
        if keep_image_only_headings and not needs_blocks:
            placed = []
            for block in blocks:
                figures = image_only_heading_figures(block)
                if figures:
                    placed.extend(figures)
                    image_only_headings = True
                else:
                    placed.append(block)
            blocks = placed
        ordered_steps = False
        has_image_only_steps = False
        if keep_ordered_step_instructions:
            for index, block in enumerate(blocks):
                ordered, has_image_only = ordered_numbered_step(block, keep_image_only=keep_image_only_step_instructions)
                if ordered is not block:
                    blocks[index] = ordered
                    ordered_steps = True
                    has_image_only_steps |= has_image_only
        step_layout = ORDERED_STEP_IMAGE_ONLY_LAYOUT if has_image_only_steps else ORDERED_STEP_INSTRUCTIONS_LAYOUT
        untyped_refs, placed_pdfs = (), False
        html = article.get("content")
        if (keep_mixed_html_pdf_embeds and keep_bound_pdf_iframes
                and (not needs_blocks or article.get("steps"))
                and resource.metadata.get("asset_bindings")
                and isinstance(html, str) and re.search(r"<(?:iframe|object|embed|a)\b", html, re.I)):
            from .mixed_article_documents import place_bound_documents

            try:
                nested = SourceResource.from_bytes(
                    resource.source_uri, resource.source_version, html.encode(), "text/html",
                    resource.locator, resource.metadata,
                )
                alternate = project_html(nested, include_untyped_pdf_positions=True)
            except ValueError:
                # Secondary HTML can be unusable even when structured content is valid.
                pass
            else:
                untyped_refs, placed_pdfs = place_bound_documents(
                    blocks, alternate["blocks"], resolved_pdf_refs=resolved_pdf_refs,
                )
        return {
            "blocks": blocks,
            "asset_resource_refs": article.get("asset_resource_refs", []),
            **({"image_only_headings": True} if image_only_headings else {}),
            **({"authored_json_blocks": True} if keep_structured_table_cell_order and not needs_blocks else {}),
            **({"ordered_step_instructions_layout": step_layout} if ordered_steps else {}),
            **({"handled_pdf_embeds": True, "mixed_html_pdf_embeds": True} if placed_pdfs else {}),
            **({"untyped_pdf_embed_refs": tuple(untyped_refs)} if untyped_refs else {}),
        }
    if media in {"application/xml", "text/xml"}:
        return {
            "blocks": _maintenance_xml_blocks(resource.payload.decode("utf-8-sig")),
            "asset_resource_refs": [],
        }
    if media == "text/html":
        return project_html(resource)
    if media == "text/plain":
        return {
            "blocks": segment_plain_article_text(resource.payload.decode("utf-8-sig"), step_parser=step_parser),
            "asset_resource_refs": [],
        }
    if media == "application/pdf":
        return {**_adapt_bound_pdf(
            resource, keep_pdf_figure_order=keep_pdf_figure_order,
            keep_multiple_pdf_figures=keep_multiple_pdf_figures,
            keep_repeated_pdf_figures=keep_repeated_pdf_figures,
            keep_pdf_figures_with_margins=keep_pdf_figures_with_margins,
            keep_compact_pdf_figures=keep_compact_pdf_figures,
            step_parser=step_parser,
        ), "asset_resource_refs": []}
    raise ValueError("unsupported article media")


def bound_pdf_embed_blocks(
    resource: SourceResource, *, require_complete_ocr: bool = False, keep_pdf_figure_order: bool = False,
) -> list[dict[str, Any]]:
    return adapt_bound_pdf_embed(
        resource, require_complete_ocr=require_complete_ocr,
        keep_pdf_figure_order=keep_pdf_figure_order,
    )["blocks"]


def adapt_bound_pdf_embed(
    resource: SourceResource, *, require_complete_ocr: bool = False, keep_pdf_figure_order: bool = False,
    keep_multiple_pdf_figures: bool = False, keep_repeated_pdf_figures: bool = False,
    keep_pdf_figures_with_margins: bool = False,
    keep_compact_pdf_figures: bool = False,
    skip_blank_pages: bool = False,
    keep_single_line_compact_figures: bool = False,
    keep_wordless_pdf_figures: bool = False,
    step_parser=None,
) -> dict[str, Any]:
    return _adapt_bound_pdf(
        resource, embedded=True, require_complete_ocr=require_complete_ocr,
        keep_pdf_figure_order=keep_pdf_figure_order,
        keep_multiple_pdf_figures=keep_multiple_pdf_figures,
        keep_repeated_pdf_figures=keep_repeated_pdf_figures,
        keep_pdf_figures_with_margins=keep_pdf_figures_with_margins,
        keep_compact_pdf_figures=keep_compact_pdf_figures,
        skip_blank_pages=skip_blank_pages,
        keep_single_line_compact_figures=keep_single_line_compact_figures,
        keep_wordless_pdf_figures=keep_wordless_pdf_figures,
        step_parser=step_parser,
    )


def _adapt_bound_pdf(resource, *, embedded=False, require_complete_ocr=False, keep_pdf_figure_order=False,
                     keep_multiple_pdf_figures=False, keep_repeated_pdf_figures=False,
                     keep_pdf_figures_with_margins=False, keep_compact_pdf_figures=False, skip_blank_pages=False,
                     keep_single_line_compact_figures=False, keep_wordless_pdf_figures=False, step_parser=None):
    if embedded and (resource.media_type != "application/pdf"
            or len(resource.payload) > _MAX_BOUND_EMBEDDED_PDF_BYTES
            or not resource.payload.startswith(b"%PDF-")):
        raise ValueError("invalid embedded PDF")
    figure_gaps = {} if keep_pdf_figure_order else None
    if embedded or (keep_pdf_figure_order and resource.media_type not in _MEDIA_TYPE_ADAPTERS):
        artifact = _adapt_pdf_resource(
            resource, resource.metadata, max_pages=_MAX_BOUND_EMBEDDED_PDF_PAGES if embedded else None,
            figure_gaps=figure_gaps,
            keep_multiple_pdf_figures=keep_multiple_pdf_figures,
            keep_repeated_pdf_figures=keep_repeated_pdf_figures,
            keep_pdf_figures_with_margins=keep_pdf_figures_with_margins,
            keep_compact_pdf_figures=keep_compact_pdf_figures,
            skip_blank_pages=skip_blank_pages,
            keep_single_line_compact_figures=keep_single_line_compact_figures,
            keep_wordless_pdf_figures=keep_wordless_pdf_figures,
            step_parser=step_parser,
        )
    else:
        artifact = adapt_source_resource(resource)
    if require_complete_ocr and artifact.metadata.get("rasterization_status") == "unavailable":
        raise ValueError("linked PDF has pages requiring unavailable OCR")
    result = _bound_pdf_blocks(artifact, figure_gaps or {}, step_parser=step_parser)
    if artifact.metadata.get("skipped_blank_pages") is True:
        result["skipped_blank_pages"] = True
    if artifact.metadata.get("retained_wordless_pdf_figures") is True:
        result["retained_wordless_pdf_figures"] = True
    return result


def _bound_pdf_blocks(artifact: SourceArtifact, figure_gaps: dict[str, tuple[int, int, int]], *, step_parser=None) -> dict[str, Any]:
    from .article_document import segment_plain_article_text

    text_candidates = [
        c
        for c in artifact.candidates
        if c.kind in ("document_text", "ocr_text", "image_text")
    ]
    pages: dict[int, list[dict[str, Any]]] = {}
    unplaced = []
    images = {}
    # Native text and OCR candidates are produced in separate passes.
    for candidate in text_candidates:
        segments = segment_plain_article_text(candidate.data.get("text", ""), step_parser=step_parser)
        page = re.match(r"^page:(\d+)(?:$|:)", candidate.locator)
        if page:
            pages.setdefault(int(page[1]), []).extend(segments)
        else:
            unplaced.extend(segments)
        for image in candidate.data.get("images", []):
            images.setdefault(image["image_id"], image)
    page_images: dict[int, list[dict[str, Any]]] = {}
    for image in images.values():
        figure = {"kind": "image", **image}
        figure.pop("_retained_pdf_figure_with_margins", None)
        figure.pop("_compact_pdf_figure", None)
        figure.pop("_single_line_pdf_figure", None)
        page_number = image.get("page")
        if isinstance(page_number, int):
            pages.setdefault(page_number, [])
            page_images.setdefault(page_number, []).append(figure)
        else:
            unplaced.append(figure)
    blocks = []
    positioned = False
    positioned_with_margins = False
    positioned_compact_figures = False
    positioned_single_line_figures = False
    legacy_asset_order = []
    for page in sorted(pages):
        text = pages[page]
        figures = page_images.get(page, [])
        gaps = {figure["image_id"]: figure_gaps.get(figure["image_id"]) for figure in figures}
        if figures and all(gap is not None and gap[1] == len(text) for gap in gaps.values()):
            at_gap = {}
            for figure in sorted(figures, key=lambda f: gaps[f["image_id"]][2]):
                at_gap.setdefault(gaps[figure["image_id"]][0], []).append(figure)
            for index, block in enumerate(text):
                blocks.extend(at_gap.get(index, ()))
                blocks.append(block)
            blocks.extend(at_gap.get(len(text), ()))
            positioned = True
            positioned_with_margins |= any(
                images[image_id].get("_retained_pdf_figure_with_margins") is True for image_id in gaps
            )
            positioned_compact_figures |= any(
                images[image_id].get("_compact_pdf_figure") is True and not images[image_id].get("_single_line_pdf_figure")
                for image_id in gaps
            )
            positioned_single_line_figures |= any(images[image_id].get("_single_line_pdf_figure") is True for image_id in gaps)
            if len(figures) > 1:
                group = [figure["image_id"] for figure in figures]
                legacy_asset_order.append(group)
        else:
            blocks.extend(text)
            blocks.extend(figures)
    blocks.extend(unplaced)
    return {
        "blocks": blocks,
        **({"positioned_pdf_figures": True} if positioned else {}),
        **({"pdf_legacy_asset_order": legacy_asset_order} if legacy_asset_order else {}),
        **({"retained_repeated_pdf_figures": True}
           if any(image.get("_retained_repeated_pdf_figure") is True for image in images.values()) else {}),
        **({"retained_pdf_figures_with_margins": True} if positioned_with_margins else {}),
        **({"positioned_compact_pdf_figures": True} if positioned_compact_figures else {}),
        **({"positioned_single_line_pdf_figures": True} if positioned_single_line_figures else {}),
    }
