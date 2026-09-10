"""Normalize typed source candidates into an evidence-backed source bundle."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .article_identity import canonicalize_article_identity
from .source_adapters import NormalizationCandidate, SourceArtifact
from .vehicle_identity import canonicalize_vehicle_observation


_PRICE_RE = re.compile(
    r"^\s*(?P<symbol>[$€£])\s*(?P<whole>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.(?P<fraction>\d{1,2}))?\s*$"
)
_CURRENCY_BY_SYMBOL = {"$": "USD", "€": "EUR", "£": "GBP"}
# A title overlap of 95% or more is too close to publish as a second article.
ARTICLE_SIMILARITY_THRESHOLD = 0.95


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
    article_operations: dict[str, list[dict[str, Any]]] = {}
    document_text_records: list[dict[str, Any]] = []
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
                article_record = {
                    "article_key": candidate.key,
                    "article_id": str(candidate.data.get("id")),
                    "bucket": candidate.data.get("bucket"),
                    "title": candidate.data.get("title"),
                    "bulletin_number": candidate.data.get("bulletinNumber"),
                    "release_date": candidate.data.get("releaseDate"),
                    "sort": candidate.data.get("sort"),
                    "evidence_id": evidence_item["evidence_id"],
                    "content_locator": evidence_item["locator"],
                    "source_uri": artifact.source_uri,
                    "source_version": artifact.source_version,
                    "content_sha256": artifact.content_sha256,
                }
                body = _article_body(candidate.data)
                if body is not None:
                    article_record["body"] = body
                steps = _article_steps(candidate.data)
                if steps is not None:
                    article_record["steps"] = steps
                images = _article_images(candidate.data)
                if images:
                    article_record["images"] = images
                article_records.append(article_record)
            elif candidate.kind == "article_operations":
                article_id = str(candidate.data.get("article_id") or "").strip()
                operations = _article_operations(
                    candidate.data.get("operations"), evidence_item["evidence_id"]
                )
                if article_id and operations:
                    article_operations.setdefault(article_id, []).extend(operations)
            elif candidate.kind == "document_text":
                document_text_records.append(
                    {
                        "text": candidate.data.get("text"),
                        "images": candidate.data.get("images", []),
                        "evidence_id": evidence_item["evidence_id"],
                        "locator": evidence_item["locator"],
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

    article_records, document_content_evidence = _attach_document_content(
        article_records, document_text_records, diagram_records, evidence
    )
    for article in article_records:
        operations = article_operations.get(str(article.get("article_id")), [])
        if operations:
            article["operations"] = operations
    evidence.extend(document_content_evidence)
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
    parsed: list[tuple[SourceArtifact, NormalizationCandidate, dict[str, Any]]] = []
    for item in candidates:
        if not {"year", "make", "model"}.issubset(item[2]):
            continue
        try:
            canonical = canonicalize_vehicle_observation(
                {
                    **item[2],
                    "region": item[2].get("region", region),
                }
            ).to_dict()
        except (TypeError, ValueError):
            quarantined.append(
                {
                    "source_uri": item[0].source_uri,
                    "content_sha256": item[0].content_sha256,
                    "reason": "invalid_vehicle_identity",
                    "evidence_id": item[2].get("evidence_id"),
                }
            )
            continue
        parsed.append((item[0], item[1], {**canonical, "evidence_id": item[2]["evidence_id"]}))
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
    _, _, first_record = parsed[0]
    record = dict(first_record)
    for _, _, candidate_record in parsed[1:]:
        for field_name in (
            "body_style",
            "trim",
            "drivetrain",
            "engine_displacement_l",
        ):
            existing_value = record.get(field_name)
            incoming_value = candidate_record.get(field_name)
            if existing_value is None and incoming_value is not None:
                record[field_name] = incoming_value
                continue
            if (
                existing_value is not None
                and incoming_value is not None
                and existing_value != incoming_value
            ):
                conflicts.append(
                    {
                        "kind": "vehicle_identity",
                        "field": field_name,
                        "resolution": "needs_review",
                        "candidates": [
                            {
                                "value": existing_value,
                                "evidence_id": record["evidence_id"],
                            },
                            {
                                "value": incoming_value,
                                "evidence_id": candidate_record["evidence_id"],
                            },
                        ],
                        "evidence_ids": [
                            record["evidence_id"],
                            candidate_record["evidence_id"],
                        ],
                    }
                )
                quarantined.append(
                    {
                        "reason": "conflicting_vehicle_dimension",
                        "field": field_name,
                        "evidence_ids": [
                            record["evidence_id"],
                            candidate_record["evidence_id"],
                        ],
                    }
                )
                return None
    make = str(record["make"]).strip()
    model = str(record["model"]).strip()
    year = int(record["year"])
    normalized_region = str(record.get("region", region)).strip().upper()
    if expected_vehicle is not None:
        try:
            expected = canonicalize_vehicle_observation(
                {**expected_vehicle, "region": expected_vehicle.get("region", normalized_region)}
            )
        except (TypeError, ValueError):
            expected = None
        expected_make = expected.make if expected is not None else str(expected_vehicle.get("make", "")).strip()
        expected_model = expected.model if expected is not None else str(expected_vehicle.get("model", "")).strip()
        expected_region = expected.region if expected is not None and expected.region else str(expected_vehicle.get("region", normalized_region)).strip().upper()
        source_region = str(record.get("region", normalized_region)).strip().upper()
        try:
            expected_year = int(expected_vehicle.get("year"))
        except (TypeError, ValueError):
            expected_year = None
        expected_trim = expected.trim if expected is not None else str(expected_vehicle.get("trim", "")).strip() or None
        expected_body_style = expected.body_style if expected is not None else None
        expected_drivetrain = expected.drivetrain if expected is not None else None
        expected_engine = expected.engine_displacement_l if expected is not None else None
        source_trim = record.get("trim")
        source_body_style = record.get("body_style")
        source_drivetrain = record.get("drivetrain")
        source_engine = record.get("engine_displacement_l")
        mismatch = (
            make.casefold() != expected_make.casefold()
            or not _compatible_vehicle_model(model, expected_model)
            or year != expected_year
            or source_region != expected_region
            or (expected_trim is not None and source_trim is not None and source_trim != expected_trim)
            or (expected_body_style is not None and source_body_style is not None and source_body_style != expected_body_style)
            or (expected_drivetrain is not None and source_drivetrain is not None and source_drivetrain != expected_drivetrain)
            or (expected_engine is not None and source_engine is not None and abs(source_engine - expected_engine) >= 0.0001)
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
                        **({"body_style": source_body_style} if source_body_style else {}),
                        **({"drivetrain": source_drivetrain} if source_drivetrain else {}),
                        **(
                            {"engine_displacement_l": source_engine}
                            if source_engine is not None
                            else {}
                        ),
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
    # The selector supplied by the caller is the canonical identity. The
    # provider display name may contain trim, engine, fuel, and marketing
    # suffixes; those remain in source evidence/configuration records rather
    # than creating a second vehicle family in the local database.
    canonical_make = expected_make if expected_vehicle is not None and expected_make else make
    canonical_model = expected_model if expected_vehicle is not None and expected_model else model
    canonical_year = expected_year if expected_vehicle is not None and expected_year is not None else year
    canonical_region = expected_region if expected_vehicle is not None and expected_region else normalized_region
    return {
        "vehicle_key": f"{_slug(canonical_make)}-{_slug(canonical_model)}-{canonical_year}-{_slug(canonical_region)}",
        "make": canonical_make,
        "model": canonical_model,
        "model_year": canonical_year,
        "region": canonical_region,
        "body_style": expected_body_style if expected_vehicle is not None and expected_body_style is not None else record.get("body_style"),
        "trim": expected_trim if expected_vehicle is not None and expected_trim is not None else record.get("trim"),
        "drivetrain": expected_drivetrain if expected_vehicle is not None and expected_drivetrain is not None else record.get("drivetrain"),
        "engine_displacement_l": expected_engine if expected_vehicle is not None and expected_engine is not None else record.get("engine_displacement_l"),
        "evidence_id": record["evidence_id"],
    }


def _compatible_vehicle_model(source_model: object, expected_model: object) -> bool:
    """Accept provider trim/engine suffixes for a selected base model."""

    source = " ".join(str(source_model or "").split()).casefold()
    expected = " ".join(str(expected_model or "").split()).casefold()
    return (
        source == expected
        or source.startswith(expected + " ")
        or expected.startswith(source + " ")
    )


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
    accepted_by_id: dict[str, dict[str, Any]] = {}
    accepted_by_title: dict[str, dict[str, Any]] = {}
    accepted_by_token: dict[str, set[int]] = {}
    accepted_positions: dict[int, int] = {}
    for record in ordered:
        article_id = _article_text(record.get("article_id"))
        exact = accepted_by_id.get(article_id) if article_id else None
        if exact is not None:
            _merge_article(exact, record)
            _index_article_tokens(
                exact,
                accepted_positions[id(exact)],
                accepted_by_token,
            )
            continue
        title = _article_text(record.get("title"))
        similar = accepted_by_title.get(title) if title else None
        if similar is not None and _article_roles_differ(similar, record):
            similar = None
        if similar is None:
            candidate_indices = sorted(
                {
                    index
                    for token in _article_search_tokens(record)
                    for index in accepted_by_token.get(token, ())
                }
            )
            similar = next(
                (
                    accepted[index]
                    for index in candidate_indices
                    if not _article_roles_differ(accepted[index], record)
                    and _similar_article(accepted[index], record)
                ),
                None,
            )
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
                    "similarity": round(_article_similarity(similar, record), 6),
                }
            )
            continue
        record["evidence_ids"] = [record["evidence_id"]]
        record["duplicate_count"] = 1
        record["source_uris"] = [record["source_uri"]]
        record["source_versions"] = [record["source_version"]]
        accepted_index = len(accepted)
        accepted.append(record)
        accepted_positions[id(record)] = accepted_index
        if article_id:
            accepted_by_id[article_id] = record
        if title:
            accepted_by_title.setdefault(title, record)
        _index_article_tokens(record, accepted_index, accepted_by_token)
    return accepted


def _attach_document_content(
    articles: list[dict[str, Any]],
    document_text_records: list[dict[str, Any]],
    media_artifacts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Join AutoAPI document responses to their article index records.

    AutoAPI exposes article metadata in ``v2.json`` and document bodies in
    separate responses. The document locator carries the numeric document ID,
    while the article ID is commonly ``<document-id>:<content-id>``.
    """

    by_document_id: dict[str, list[dict[str, Any]]] = {}
    for record in sorted(document_text_records, key=_document_content_order):
        locator = str(record.get("locator", ""))
        if not locator.startswith(("body.html:", "body.pdf:")):
            continue
        prefix = "body.html:" if locator.startswith("body.html:") else "body.pdf:"
        document_id = locator.removeprefix(prefix).split(":", 1)[0].strip()
        if document_id and record.get("text"):
            by_document_id.setdefault(document_id, []).append(record)

    aggregate_evidence: list[dict[str, Any]] = []
    for article in articles:
        article_id = str(article.get("article_id") or "")
        document_id = article_id.split(":", 1)[0].strip()
        content_records = by_document_id.get(document_id, [])
        if not content_records:
            continue
        html_records = [
            record
            for record in content_records
            if str(record.get("locator", "")).startswith("body.html:")
        ]
        selected_records = html_records or content_records
        content = _document_content_record(selected_records, aggregate_evidence)
        article.setdefault("body", content["text"])
        article["content_evidence_id"] = content["evidence_id"]
        article["content_locator"] = content["locator"]
        article["content_source_uri"] = content["source_uri"]
        article["content_source_version"] = content["source_version"]
        article["content_sha256"] = content["content_sha256"]
        images = _resolve_document_images(selected_records, media_artifacts, evidence)
        if images:
            article["images"] = images
    return articles, aggregate_evidence


def _resolve_document_images(
    records: list[dict[str, Any]],
    media_artifacts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve guide image IDs to the original persisted media artifact."""

    media_by_id: dict[str, dict[str, Any]] = {}
    for artifact in media_artifacts:
        source_uri = str(artifact.get("source_uri") or "")
        filename = source_uri.rsplit("/", 1)[-1].split("?", 1)[0]
        image_id = filename.rsplit(".", 1)[0]
        if image_id:
            media_by_id[image_id] = artifact
    evidence_by_uri: dict[str, str] = {}
    for item in evidence:
        source_uri = str(item.get("source_uri") or "")
        if source_uri and item.get("evidence_id"):
            evidence_by_uri.setdefault(source_uri, str(item["evidence_id"]))
    images: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        raw_images = record.get("images", [])
        if not isinstance(raw_images, list):
            continue
        for raw in raw_images:
            if not isinstance(raw, dict):
                continue
            image = dict(raw)
            image_id = str(image.get("image_id") or "").strip()
            artifact = media_by_id.get(image_id) if image_id else None
            if artifact is not None:
                image["url"] = str(artifact.get("source_uri") or "")
                image["artifact_key"] = str(artifact.get("object_key") or "")
                evidence_id = evidence_by_uri.get(str(artifact.get("source_uri") or ""))
                if evidence_id:
                    image["evidence_id"] = evidence_id
            url = str(image.get("url") or "").strip()
            if not url or url in seen:
                continue
            image["url"] = url
            image.pop("image_id", None)
            image.setdefault("alt", "Source diagram")
            seen.add(url)
            images.append({key: value for key, value in image.items() if value})
    return images


def _document_content_record(
    records: list[dict[str, Any]],
    aggregate_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(records) == 1:
        return records[0]
    first = records[0]
    last = records[-1]
    locators = [str(record["locator"]) for record in records]
    locator = f"{locators[0]}..{locators[-1]}"
    evidence_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            "autodata-document-content:" + "|".join(
                str(record["evidence_id"]) for record in records
            ),
        )
    )
    aggregate = {
        "evidence_id": evidence_id,
        "source_uri": first["source_uri"],
        "content_sha256": first["content_sha256"],
        "locator": locator,
        "candidate_key": f"document-content:{evidence_id}",
        "extracted_text": "\n\n".join(str(record["text"]) for record in records),
        "confidence": min(float(record.get("confidence", 1.0)) for record in records),
        "reviewer_state": "pending",
    }
    aggregate_evidence.append(aggregate)
    return {
        **first,
        "text": aggregate["extracted_text"],
        "evidence_id": evidence_id,
        "locator": locator,
    }


def _document_content_order(record: dict[str, Any]) -> tuple[str, int, str]:
    locator = str(record.get("locator", ""))
    page_match = re.search(r":page:(\d+)$", locator)
    page = int(page_match.group(1)) if page_match else 0
    return (locator.split(":page:", 1)[0], page, str(record.get("evidence_id", "")))


def _index_article_tokens(
    record: dict[str, Any],
    accepted_index: int,
    accepted_by_token: dict[str, set[int]],
) -> None:
    for token in _article_search_tokens(record):
        accepted_by_token.setdefault(token, set()).add(accepted_index)


def _article_search_tokens(record: dict[str, Any]) -> set[str]:
    return _article_tokens(
        " ".join(
            (
                _article_text(record.get("title")),
                _article_text(record.get("body")),
            )
        )
    )


def _article_order(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _article_text(record.get("title")),
        _article_text(record.get("article_id")),
        str(record.get("evidence_id", "")),
    )


def _article_roles_differ(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Keep a provider procedure and its labor row as distinct source records."""

    def role(record: dict[str, Any]) -> str:
        article_id = str(record.get("article_id") or "").casefold()
        bucket = str(record.get("bucket") or "").casefold()
        if article_id.startswith("p:"):
            return "procedure"
        if article_id.startswith("l:") or bucket == "labor":
            return "labor"
        return "article"

    return role(left) != role(right)


def _similar_article(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_title = _article_text(left.get("title"))
    right_title = _article_text(right.get("title"))
    if left_title and left_title == right_title:
        return True
    if _article_similarity(left, right) >= ARTICLE_SIMILARITY_THRESHOLD:
        return True
    left_tokens = _article_tokens(left.get("title"))
    right_tokens = _article_tokens(right.get("title"))
    if len(left_tokens & right_tokens) < 3:
        return False
    return _title_similarity(left.get("title"), right.get("title")) >= ARTICLE_SIMILARITY_THRESHOLD


def _article_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    """Compare complete article content when both records contain bodies."""

    if left.get("body") and right.get("body"):
        try:
            identity = canonicalize_article_identity(
                right,
                existing_articles=(left,),
                near_duplicate_gate=ARTICLE_SIMILARITY_THRESHOLD,
            )
        except ValueError:
            pass
        else:
            return identity.near_duplicate_score
    return _title_similarity(left.get("title"), right.get("title"))


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


def _article_body(data: dict[str, Any]) -> str | None:
    for key in ("body", "articleBody", "content"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return re.sub(r"\s+", " ", value).strip()
    return None


def _article_steps(data: dict[str, Any]) -> list[Any] | None:
    value = data.get("steps")
    if isinstance(value, list) and value and all(isinstance(step, (str, dict)) for step in value):
        return value
    return None


def _article_operations(value: Any, evidence_id: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        # AutoAPI labor responses expose one priced main operation and zero or
        # more operations included in that price. Optional operations are not
        # part of the requested replacement unless explicitly selected later.
        operation_values: list[Any] = []
        main_operation = value.get("mainOperation")
        if isinstance(main_operation, dict):
            operation_values.append(main_operation)
        included_operations = value.get("includedOperations")
        if isinstance(included_operations, list):
            operation_values.extend(included_operations)
        value = operation_values
    if not isinstance(value, list):
        return []
    operations: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            continue
        operation_type = str(raw.get("operationType") or "").casefold()
        title = str(raw.get("title") or "").strip()
        operation_id = str(
            raw.get("operation_id")
            or raw.get("operationId")
            or raw.get("key")
            or raw.get("code")
            or raw.get("id")
            or f"operation-{index + 1}"
        ).strip()
        if operation_type == "included operation" and title:
            # Provider IDs for equivalent included work can differ between
            # labor articles. A normalized title gives the overlap calculator
            # a stable cross-article key while the evidence retains the source
            # operation ID in the action metadata below.
            operation_id = f"included:{_slug(title)}"
        action = str(
            raw.get("action")
            or raw.get("name")
            or raw.get("description")
            or raw.get("operation")
            or raw.get("title")
            or operation_id
        ).strip()
        duration = next(
            (
                raw[key]
                for key in (
                    "duration_hours", "durationHours", "hours",
                    "labor_hours", "laborHours", "laborTime", "time",
                )
                if raw.get(key) is not None
            ),
            None,
        )
        if duration is None and str(raw.get("operationType") or "").casefold() == "included operation":
            # Included work is already priced in the main operation. Retain it
            # for procedure composition without adding labor twice.
            duration = 0.0
        if operation_id and action:
            operations.append(
                {
                    "operation_id": operation_id,
                    "action": action,
                    "duration_hours": duration,
                    "evidence_ids": [evidence_id],
                }
            )
    return operations


def _article_images(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep only safe, displayable source-media references on an article."""

    values: list[Any] = []
    for key in ("images", "imageUrls", "image_urls", "diagrams", "media"):
        value = data.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value:
            values.append(value)
    images: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        if isinstance(value, str):
            url = value.strip()
            image = {"url": url} if url else None
        elif isinstance(value, dict):
            url = str(value.get("url") or value.get("src") or value.get("href") or "").strip()
            image = {"url": url} if url else None
            if image is not None:
                for key in ("alt", "title", "evidence_id", "source_uri"):
                    if value.get(key):
                        image[key] = str(value[key]).strip()
        else:
            image = None
        if image is None:
            continue
        identity = (image["url"], image.get("alt", image.get("title", "")))
        if identity not in seen:
            seen.add(identity)
            images.append(image)
    return images


def _merge_article(target: dict[str, Any], duplicate: dict[str, Any]) -> None:
    for field in ("bucket", "title", "bulletin_number", "release_date"):
        if not target.get(field) and duplicate.get(field):
            target[field] = duplicate[field]
    for field in ("body", "steps", "operations"):
        if not target.get(field) and duplicate.get(field):
            target[field] = duplicate[field]
    if duplicate.get("images"):
        merged = target.setdefault("images", [])
        existing = {(item.get("url"), item.get("alt", item.get("title", ""))) for item in merged}
        for image in duplicate["images"]:
            identity = (image.get("url"), image.get("alt", image.get("title", "")))
            if identity not in existing:
                merged.append(image)
                existing.add(identity)
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
