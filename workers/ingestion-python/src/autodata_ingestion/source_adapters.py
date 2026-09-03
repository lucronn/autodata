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
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol
from urllib.parse import urlparse
from xml.etree import ElementTree


_JSON_TYPES = {"application/json", "application/problem+json", "text/json"}
_STRUCTURED_TYPES = _JSON_TYPES | {"application/xml", "text/xml", "text/csv"}
_DOCUMENT_TYPES = {"text/html", "application/pdf", "text/plain"}
_DIAGRAM_TYPES = {"image/svg+xml"}
_IMAGE_TYPES = {"image/bmp", "image/jpeg", "image/png", "image/tiff", "image/webp"}
_GENERIC_MEDIA_TYPES = {"application/octet-stream", "binary/octet-stream", "text/plain"}


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

    if isinstance(body, dict):
        vehicle_candidate = _candidate_from_record(body, "body")
        if vehicle_candidate is not None and vehicle_candidate.kind == "vehicle_identity":
            candidates.append(vehicle_candidate)
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
    document_id = _field(body, "document_id", "documentId", "id") or "embedded"
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


def _decode_embedded_pdf(encoded_pdf: str) -> bytes:
    value = encoded_pdf.strip()
    if value.lower().startswith("data:application/pdf;base64,"):
        value = value.split(",", 1)[1]
    try:
        payload = base64.b64decode(re.sub(r"\s+", "", value), validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError("embedded PDF is not valid base64") from error
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
    candidate = NormalizationCandidate(
        "document_text",
        f"document-text:{resource.content_sha256}",
        {"text": text},
        locator,
    )
    return SourceArtifact(
        kind="document",
        source_uri=resource.source_uri,
        source_version=resource.source_version,
        media_type=resource.media_type,
        content_sha256=resource.content_sha256,
        payload=resource.payload,
        raw_payload=resource.payload,
        metadata={**metadata, "extraction_status": "candidate_ready", "text_char_count": len(text)},
        candidates=(candidate,),
    )


def _adapt_pdf_resource(
    resource: SourceResource,
    metadata: dict[str, Any],
) -> SourceArtifact:
    """Extract native PDF text and OCR pages that contain no native text."""

    from .ocr import build_ocr_candidates

    pages: list[Any] = []
    native_text_pages: set[int] = set()
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
            pages = list(reader.pages)
        except Exception as error:
            text_extractor_status = "failed"
            warnings.append(f"PDF text extraction could not read the document: {error}")

    page_errors: list[dict[str, str]] = []
    for index, page in enumerate(pages, start=1):
        try:
            text = re.sub(r"\s+", " ", str(page.extract_text() or "")).strip()
        except Exception as error:
            page_errors.append({"locator": f"page:{index}", "error": str(error)})
            continue
        if text:
            native_text_pages.add(index)
            candidates.append(
                NormalizationCandidate(
                    "document_text",
                    f"document-text:{resource.content_sha256}:page:{index}",
                    {"text": text},
                    f"page:{index}",
                )
            )

    missing_pages = set(range(1, len(pages) + 1)) - native_text_pages if pages else set()
    should_rasterize = bool(missing_pages) or not pages
    rasterization_status = "not_needed"
    extraction_mode = "text_pdf"
    if should_rasterize:
        try:
            scanned_blocks = extract_scanned_pdf_text(
                resource.content_sha256,
                resource.payload,
                native_text_pages,
            )
            ocr_candidates = list(build_ocr_candidates(resource.content_sha256, scanned_blocks))
            candidates.extend(ocr_candidates)
            rasterization_status = "complete"
            extraction_mode = "mixed_pdf_ocr" if native_text_pages else "scanned_pdf_ocr"
        except Exception as error:
            rasterization_status = "unavailable"
            warnings.append(str(error))
            extraction_mode = "mixed_pdf_ocr" if native_text_pages else "unavailable"

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
) -> Iterable[Any]:
    """Load the optional PDF rasterizer/OCR provider lazily for testable intake."""

    from .pdf_ocr import extract_scanned_pdf_text as extract

    return extract(content_sha256, payload, native_text_pages)


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
        return NormalizationCandidate(
            "article",
            f"article:{article_id}:{locator}",
            {
                "id": article_id,
                "title": title,
                "bucket": _field(record, "bucket", "category"),
                "bulletinNumber": _field(record, "bulletin_number", "bulletinNumber"),
                "releaseDate": _field(record, "release_date", "releaseDate"),
            },
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
