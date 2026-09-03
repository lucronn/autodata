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
    specifications: tuple[dict[str, Any], ...]
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


def normalize_source_bundle(
    artifacts: Iterable[SourceArtifact],
    region: str,
    *,
    expected_vehicle: dict[str, Any] | None = None,
) -> SourceBundle:
    """Join heterogeneous artifacts without making unsupported facts canonical."""

    artifact_list = list(artifacts)
    evidence: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    vehicle_candidates = []
    specification_records: list[dict[str, Any]] = []
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
            elif candidate.kind == "specification":
                specification_records.append(
                    {
                        "name": str(candidate.data["name"]).strip(),
                        "value": candidate.data.get("value"),
                        "unit": candidate.data.get("unit"),
                        "evidence_id": evidence_item["evidence_id"],
                    }
                )
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
                        "source_uri": artifact.source_uri,
                        "source_version": artifact.source_version,
                        "content_sha256": artifact.content_sha256,
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

    article_records = _resolve_article_collisions(article_records, evidence, quarantined, conflicts)
    vehicle = _normalize_vehicle(
        vehicle_candidates,
        region,
        evidence,
        quarantined,
        conflicts,
        expected_vehicle=expected_vehicle,
    )
    if expected_vehicle is not None and vehicle is None:
        # Facts from a page that cannot be proven to belong to the requested
        # vehicle remain evidence, but cannot enter an associated bundle.
        specification_records.clear()
        model_records.clear()
        powertrain_records.clear()
        part_records.clear()
        article_records.clear()
        document_records.clear()
        diagram_records.clear()
    if not vehicle_candidates:
        quarantined.append({"reason": "vehicle_identity_not_found"})
    if not evidence:
        quarantined.append({"reason": "no_evidence"})
    evidence = list(dict((item["evidence_id"], item) for item in evidence).values())
    status = "ready" if vehicle and not quarantined else "needs_review"
    return SourceBundle(
        status=status,
        vehicle=vehicle,
        specifications=tuple(specification_records),
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
    *,
    expected_vehicle: dict[str, Any] | None = None,
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
    if expected_vehicle is not None:
        expected_make = str(expected_vehicle.get("make", "")).strip()
        expected_model = str(expected_vehicle.get("model", "")).strip()
        expected_region = str(expected_vehicle.get("region", normalized_region)).strip().upper()
        source_region = str(record.get("region", normalized_region)).strip().upper()
        try:
            expected_year = int(expected_vehicle.get("year"))
        except (TypeError, ValueError):
            expected_year = None
        expected_trim = str(expected_vehicle.get("trim", "")).strip() or None
        source_trim = str(record.get("trim", "")).strip() or None
        mismatch = (
            make.casefold() != expected_make.casefold()
            or model.casefold() != expected_model.casefold()
            or year != expected_year
            or source_region != expected_region
            or (expected_trim is not None and source_trim != expected_trim)
        )
        if mismatch:
            conflicts.append(
                {
                    "kind": "vehicle_identity",
                    "field": "target_vehicle",
                    "resolution": "rejected",
                    "expected": dict(expected_vehicle),
                    "candidate": {
                        "year": year,
                        "make": make,
                        "model": model,
                        "region": source_region,
                        **({"trim": source_trim} if source_trim else {}),
                    },
                    "evidence_ids": [record["evidence_id"]],
                }
            )
            quarantined.append(
                {
                    "reason": "vehicle_identity_mismatch",
                    "source_uri": candidates[0][0].source_uri,
                    "content_sha256": candidates[0][0].content_sha256,
                    "evidence_id": record["evidence_id"],
                }
            )
            return None
    return {
        "vehicle_key": f"{_slug(make)}-{_slug(model)}-{year}-{_slug(normalized_region)}",
        "make": make,
        "model": model,
        "model_year": year,
        "region": normalized_region,
        "trim": record.get("trim"),
        "evidence_id": record["evidence_id"],
    }


def _resolve_article_collisions(
    records: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    quarantined: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge exact article replays and quarantine deterministic near matches."""

    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    ordered = sorted(records, key=_article_order)
    accepted: list[dict[str, Any]] = []
    for record in ordered:
        exact = next((item for item in accepted if _same_article(item, record)), None)
        if exact is not None:
            _merge_article(exact, record)
            continue
        similar = next((item for item in accepted if _similar_article(item, record)), None)
        if similar is not None:
            item_evidence = evidence_by_id.get(record["evidence_id"], {})
            quarantined.append(
                {
                    "reason": "similar_article_requires_review",
                    "source_uri": item_evidence.get("source_uri"),
                    "content_sha256": item_evidence.get("content_sha256"),
                    "locator": item_evidence.get("locator"),
                    "article_id": record.get("article_id"),
                }
            )
            conflicts.append(
                {
                    "kind": "article_similarity",
                    "resolution": "needs_review",
                    "article_keys": [similar["article_key"], record["article_key"]],
                    "evidence_ids": [similar["evidence_id"], record["evidence_id"]],
                    "similarity": round(_title_similarity(similar.get("title"), record.get("title")), 6),
                }
            )
            continue
        record["evidence_ids"] = [record["evidence_id"]]
        record["duplicate_count"] = 1
        record["source_uris"] = [record["source_uri"]]
        record["source_versions"] = [record["source_version"]]
        accepted.append(record)
    return accepted


def _article_order(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _article_text(record.get("title")),
        _article_text(record.get("article_id")),
        str(record.get("evidence_id", "")),
    )


def _same_article(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_id = _article_text(left.get("article_id"))
    right_id = _article_text(right.get("article_id"))
    return bool(left_id and right_id and left_id == right_id) or (
        bool(left.get("content_sha256"))
        and left.get("content_sha256") == right.get("content_sha256")
    )


def _similar_article(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_tokens = _article_tokens(left.get("title"))
    right_tokens = _article_tokens(right.get("title"))
    if len(left_tokens & right_tokens) < 3:
        return False
    return _title_similarity(left.get("title"), right.get("title")) >= 0.8


def _title_similarity(left: Any, right: Any) -> float:
    left_tokens = _article_tokens(left)
    right_tokens = _article_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _article_tokens(value: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _article_text(value)))


def _article_text(value: Any) -> str:
    return str(value or "").casefold().strip()


def _merge_article(target: dict[str, Any], duplicate: dict[str, Any]) -> None:
    for field in ("bucket", "title", "bulletin_number", "release_date"):
        if not target.get(field) and duplicate.get(field):
            target[field] = duplicate[field]
    evidence_ids = set(target.get("evidence_ids", [target["evidence_id"]]))
    evidence_ids.add(duplicate["evidence_id"])
    target["evidence_ids"] = sorted(evidence_ids)
    target["duplicate_count"] = int(target.get("duplicate_count", 1)) + int(
        duplicate.get("duplicate_count", 1)
    )
    target["source_uris"] = sorted(set(target.get("source_uris", [target["source_uri"]])) | {
        duplicate["source_uri"]
    })
    target["source_versions"] = sorted(
        set(target.get("source_versions", [target["source_version"]]))
        | {duplicate["source_version"]}
    )


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
    evidence_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"autodata-evidence:{artifact.source_uri}:{artifact.content_sha256}:{candidate.locator}",
        )
    )
    extracted_text = (
        str(candidate.data["text"])
        if candidate.kind in {"document_text", "diagram_text", "image_text"} and candidate.data.get("text")
        else json.dumps(candidate.data, sort_keys=True, separators=(",", ":"))
    )
    candidate_confidence = candidate.data.get("confidence", 1.0)
    return {
        "evidence_id": evidence_id,
        "source_uri": artifact.source_uri,
        "content_sha256": artifact.content_sha256,
        "locator": candidate.locator,
        "candidate_key": candidate.key,
        "extracted_text": extracted_text,
        "confidence": float(candidate_confidence),
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
