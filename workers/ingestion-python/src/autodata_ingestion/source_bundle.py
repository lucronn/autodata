"""Normalize typed source candidates into an evidence-backed source bundle."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .source_adapters import NormalizationCandidate, SourceArtifact


_PRICE_RE = re.compile(
    r"^\s*(?P<symbol>[$€£])\s*(?P<whole>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.(?P<fraction>\d{1,2}))?\s*$"
)
_CURRENCY_BY_SYMBOL = {"$": "USD", "€": "EUR", "£": "GBP"}


@dataclass(frozen=True)
class SourceBundle:
    status: str
    vehicle: dict[str, Any] | None
    models: tuple[dict[str, Any], ...]
    powertrains: tuple[dict[str, Any], ...]
    parts: tuple[dict[str, Any], ...]
    articles: tuple[dict[str, Any], ...]
    documents: tuple[dict[str, Any], ...]
    diagrams: tuple[dict[str, Any], ...]
    evidence: tuple[dict[str, Any], ...]
    quarantined: tuple[dict[str, Any], ...]
    conflicts: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_source_bundle(artifacts: Iterable[SourceArtifact], region: str) -> SourceBundle:
    """Join heterogeneous artifacts without making unsupported facts canonical."""

    artifact_list = list(artifacts)
    evidence: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    vehicle_candidates = []
    model_records: list[dict[str, Any]] = []
    powertrain_records: list[dict[str, Any]] = []
    part_records: list[dict[str, Any]] = []
    article_records: list[dict[str, Any]] = []
    document_records: list[dict[str, Any]] = []
    diagram_records: list[dict[str, Any]] = []

    for artifact in artifact_list:
        if artifact.kind == "quarantine":
            quarantined.append(
                {
                    "source_uri": artifact.source_uri,
                    "content_sha256": artifact.content_sha256,
                    "reason": artifact.metadata.get("quarantine_reason", "unsupported_artifact"),
                }
            )
        if artifact.kind == "diagram":
            diagram_records.append(_artifact_record(artifact))
        if artifact.kind == "document" and not artifact.candidates:
            document_records.append(_artifact_record(artifact))
        if artifact.kind == "structured" and not artifact.candidates:
            quarantined.append(
                {
                    "source_uri": artifact.source_uri,
                    "content_sha256": artifact.content_sha256,
                    "reason": "no_typed_candidates",
                }
            )
        for candidate in artifact.candidates:
            evidence_item = _evidence(artifact, candidate)
            evidence.append(evidence_item)
            record = {**candidate.data, "evidence_id": evidence_item["evidence_id"]}
            if candidate.kind == "vehicle_identity":
                vehicle_candidates.append((artifact, candidate, record))
            elif candidate.kind == "model":
                model_id = str(candidate.data["id"])
                model_records.append(
                    {
                        "model_key": f"model:{model_id}",
                        "provider_model_id": model_id,
                        "name": str(candidate.data["model"]).strip(),
                        "evidence_id": evidence_item["evidence_id"],
                    }
                )
                for index, engine in enumerate(candidate.data.get("engines", [])):
                    if not isinstance(engine, dict) or not engine.get("id") or not engine.get("name"):
                        quarantined.append(
                            {
                                "source_uri": artifact.source_uri,
                                "content_sha256": artifact.content_sha256,
                                "reason": "invalid_powertrain_candidate",
                                "locator": f"{candidate.locator}.engines[{index}]",
                            }
                        )
                        continue
                    engine_evidence = _evidence(
                        artifact,
                        NormalizationCandidate(
                            "powertrain",
                            f"powertrain:{engine['id']}",
                            engine,
                            f"{candidate.locator}.engines[{index}]",
                        ),
                    )
                    evidence.append(engine_evidence)
                    powertrain_records.append(
                        {
                            "powertrain_key": f"powertrain:{engine['id']}",
                            "provider_powertrain_id": str(engine["id"]),
                            "model_key": f"model:{model_id}",
                            "name": str(engine["name"]).strip(),
                            "evidence_id": engine_evidence["evidence_id"],
                        }
                    )
            elif candidate.kind == "part":
                part_records.append(_normalize_part(record, artifact, candidate, quarantined))
            elif candidate.kind == "article":
                article_records.append(
                    {
                        "article_key": candidate.key,
                        "article_id": str(candidate.data.get("id")),
                        "bucket": candidate.data.get("bucket"),
                        "title": candidate.data.get("title"),
                        "bulletin_number": candidate.data.get("bulletinNumber"),
                        "release_date": candidate.data.get("releaseDate"),
                        "sort": candidate.data.get("sort"),
                        "evidence_id": evidence_item["evidence_id"],
                    }
                )
            elif candidate.kind == "document":
                document_records.append(
                    {
                        **_artifact_record(artifact),
                        "document_id": str(candidate.data["documentId"]),
                        "has_html": "html" in candidate.data,
                        "has_embedded_pdf": "pdf" in candidate.data,
                        "evidence_id": evidence_item["evidence_id"],
                    }
                )

    vehicle = _normalize_vehicle(vehicle_candidates, region, evidence, quarantined, conflicts)
    if not vehicle_candidates:
        quarantined.append({"reason": "vehicle_identity_not_found"})
    if not evidence:
        quarantined.append({"reason": "no_evidence"})
    evidence = list(dict((item["evidence_id"], item) for item in evidence).values())
    status = "ready" if vehicle and not quarantined else "needs_review"
    return SourceBundle(
        status=status,
        vehicle=vehicle,
        models=tuple(model_records),
        powertrains=tuple(powertrain_records),
        parts=tuple(part_records),
        articles=tuple(article_records),
        documents=tuple(document_records),
        diagrams=tuple(diagram_records),
        evidence=tuple(evidence),
        quarantined=tuple(quarantined),
        conflicts=tuple(conflicts),
    )


def _normalize_vehicle(
    candidates: list[tuple[SourceArtifact, NormalizationCandidate, dict[str, Any]]],
    region: str,
    evidence: list[dict[str, Any]],
    quarantined: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    parsed = [item for item in candidates if {"year", "make", "model"}.issubset(item[2])]
    if not parsed:
        return None
    identities = {(item[2]["year"], item[2]["make"], item[2]["model"]) for item in parsed}
    if len(identities) > 1:
        conflict_candidates = [
            {
                "identity": {
                    "year": item[2]["year"],
                    "make": item[2]["make"],
                    "model": item[2]["model"],
                },
                "source_uri": item[0].source_uri,
                "source_version": item[0].source_version,
                "evidence_id": item[2]["evidence_id"],
            }
            for item in parsed
        ]
        conflicts.append(
            {
                "kind": "vehicle_identity",
                "field": "year/make/model",
                "resolution": "needs_review",
                "candidates": conflict_candidates,
                "evidence_ids": [item["evidence_id"] for item in conflict_candidates],
            }
        )
        quarantined.append({"reason": "conflicting_vehicle_identity", "candidates": sorted(map(str, identities))})
        return None
    _, _, record = parsed[0]
    make = str(record["make"]).strip()
    model = str(record["model"]).strip()
    year = int(record["year"])
    normalized_region = region.strip().upper()
    return {
        "vehicle_key": f"{_slug(make)}-{_slug(model)}-{year}-{_slug(normalized_region)}",
        "make": make,
        "model": model,
        "model_year": year,
        "region": normalized_region,
        "trim": record.get("trim"),
        "evidence_id": record["evidence_id"],
    }


def _normalize_part(
    record: dict[str, Any],
    artifact: SourceArtifact,
    candidate: NormalizationCandidate,
    quarantined: list[dict[str, Any]],
) -> dict[str, Any]:
    price_minor, currency = _parse_price(record.get("price"))
    price_status = "normalized" if price_minor is not None else "needs_review"
    if price_status == "needs_review":
        quarantined.append(
            {
                "source_uri": artifact.source_uri,
                "content_sha256": artifact.content_sha256,
                "locator": candidate.locator,
                "reason": "ambiguous_part_price",
            }
        )
    return {
        "part_number": str(record.get("partNumber")),
        "description": record.get("partDescription"),
        "quantity": record.get("quantity"),
        "price_minor": price_minor,
        "currency": currency,
        "price_status": price_status,
        "evidence_id": record["evidence_id"],
    }


def _parse_price(value: Any) -> tuple[int | None, str | None]:
    if not isinstance(value, str):
        return None, None
    match = _PRICE_RE.match(value)
    if not match:
        return None, None
    fraction = (match.group("fraction") or "").ljust(2, "0")
    whole = match.group("whole").replace(",", "")
    amount_minor = int(whole) * 100 + int(fraction or "0")
    return amount_minor, _CURRENCY_BY_SYMBOL[match.group("symbol")]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _evidence(artifact: SourceArtifact, candidate: NormalizationCandidate) -> dict[str, Any]:
    evidence_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata-evidence:{artifact.content_sha256}:{candidate.locator}"))
    return {
        "evidence_id": evidence_id,
        "source_uri": artifact.source_uri,
        "content_sha256": artifact.content_sha256,
        "locator": candidate.locator,
        "candidate_key": candidate.key,
        "extracted_text": json.dumps(candidate.data, sort_keys=True, separators=(",", ":")),
        "confidence": 1.0,
        "reviewer_state": "pending",
    }


def _artifact_record(artifact: SourceArtifact) -> dict[str, Any]:
    return {
        "source_uri": artifact.source_uri,
        "source_version": artifact.source_version,
        "media_type": artifact.media_type,
        "content_sha256": artifact.content_sha256,
        "object_key": artifact.object_key,
        "metadata": artifact.metadata,
    }
