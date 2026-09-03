"""Provider-neutral source intake and format classification.

The intake layer accepts bytes from any connector.  It stores the original
resource identity and content hash before an optional extractor interprets
the payload.  Extractors may add typed candidates, but an unfamiliar shape is
never silently dropped.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import mimetypes
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse
from xml.etree import ElementTree


_JSON_TYPES = {"application/json", "application/problem+json", "text/json"}
_STRUCTURED_TYPES = _JSON_TYPES | {"application/xml", "text/xml", "text/csv"}
_DOCUMENT_TYPES = {"text/html", "application/pdf", "text/plain"}
_DIAGRAM_TYPES = {"image/svg+xml"}
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
