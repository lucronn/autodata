"""Conservative evidence projections for the remaining deep-lane sections."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

from .publisher import DeepSectionJob, publish_deep_section
from .search_processor import load_approved_source_evidence


class DomainProcessorError(ValueError):
    """A domain section cannot be projected safely from available evidence."""


_SECTION_RULES: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "procedures": (
        ("procedure", re.compile(r"\bprocedur\w*\b", re.IGNORECASE)),
        ("repair", re.compile(r"\brepair\w*\b", re.IGNORECASE)),
        ("remove", re.compile(r"\bremove\w*\b", re.IGNORECASE)),
        ("install", re.compile(r"\binstall\w*\b", re.IGNORECASE)),
        ("replace", re.compile(r"\breplac\w*\b", re.IGNORECASE)),
        ("torque", re.compile(r"\btorque\b", re.IGNORECASE)),
        ("step", re.compile(r"\bstep\b", re.IGNORECASE)),
        ("safety", re.compile(r"\bsafet\w*\b|\bwarning\b", re.IGNORECASE)),
    ),
    "electrical": (
        ("wiring", re.compile(r"\bwiring\b", re.IGNORECASE)),
        ("harness", re.compile(r"\bharness\w*\b", re.IGNORECASE)),
        ("connector", re.compile(r"\bconnector\w*\b", re.IGNORECASE)),
        ("circuit", re.compile(r"\bcircuit\w*\b", re.IGNORECASE)),
        ("pinout", re.compile(r"\bpinout\b|\bpin\s+assignment\b", re.IGNORECASE)),
        ("voltage", re.compile(r"\bvoltage\b", re.IGNORECASE)),
        ("ground", re.compile(r"\bground\b", re.IGNORECASE)),
        ("fuse", re.compile(r"\bfuse\w*\b", re.IGNORECASE)),
        ("relay", re.compile(r"\brelay\w*\b", re.IGNORECASE)),
        ("network", re.compile(r"\b(?:can|lin)\s+(?:bus|network)\b", re.IGNORECASE)),
    ),
    "inventory": (
        ("part", re.compile(r"\bpart\b", re.IGNORECASE)),
        ("part_number", re.compile(r"\bpart\s*(?:number|no\.?|#)\b", re.IGNORECASE)),
        ("tool", re.compile(r"\btool\w*\b", re.IGNORECASE)),
        ("inventory", re.compile(r"\binventor\w*\b", re.IGNORECASE)),
        ("catalog", re.compile(r"\bcatalog\w*\b", re.IGNORECASE)),
        ("quantity", re.compile(r"\bquantit\w*\b", re.IGNORECASE)),
        ("sku", re.compile(r"\bsku\b", re.IGNORECASE)),
        ("software_flash", re.compile(r"\bsoftware\s+flash\b|\bflash\s+(?:update|programming)\b", re.IGNORECASE)),
    ),
    "maintenance": (
        ("maintenance", re.compile(r"\bmaintenan\w*\b", re.IGNORECASE)),
        ("service_interval", re.compile(r"\bservice\s+interval\b", re.IGNORECASE)),
        ("oil", re.compile(r"\boil\b", re.IGNORECASE)),
        ("fluid", re.compile(r"\bfluid\w*\b", re.IGNORECASE)),
        ("filter", re.compile(r"\bfilter\w*\b", re.IGNORECASE)),
        ("lubricant", re.compile(r"\blubric\w*\b", re.IGNORECASE)),
        ("inspection", re.compile(r"\binspect\w*\b", re.IGNORECASE)),
        ("schedule", re.compile(r"\bschedul\w*\b|\bmileage\b", re.IGNORECASE)),
    ),
}


def build_domain_section(
    section_name: str,
    source_snapshot_id: str,
    rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Project approved evidence matching explicit rules for one section.

    Matching is a routing aid, not semantic interpretation. The output keeps
    the complete source text and evidence identity, and downstream reviewers
    remain responsible for deciding whether a fact belongs in the canonical
    domain model.
    """

    normalized_section = str(section_name).strip().casefold()
    rules = _SECTION_RULES.get(normalized_section)
    if rules is None:
        raise ValueError(f"unsupported domain section: {section_name}")
    normalized_snapshot_id = str(source_snapshot_id).strip()
    if not normalized_snapshot_id:
        raise ValueError("source snapshot id is required")

    selected: list[dict[str, Any]] = []
    matched_terms: dict[str, list[str]] = {}
    for row in rows:
        if row.get("reviewer_state") != "approved":
            raise ValueError(f"{normalized_section} projection requires approved source evidence")
        required = ("evidence_id", "locator", "artifact_key", "extracted_text", "confidence")
        missing = [field for field in required if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"source evidence is missing: {', '.join(missing)}")
        confidence = float(row["confidence"])
        if not 0 <= confidence <= 1:
            raise ValueError("source evidence confidence must be between 0 and 1")
        evidence_id = str(row["evidence_id"])
        text = str(row["extracted_text"]).strip()
        terms = [label for label, pattern in rules if pattern.search(text)]
        if not terms:
            continue
        selected.append(
            {
                "evidence_id": evidence_id,
                "locator": str(row["locator"]),
                "artifact_key": str(row["artifact_key"]),
                "extracted_text": text,
                "confidence": confidence,
                "reviewer_state": "approved",
            }
        )
        matched_terms[evidence_id] = terms

    selected.sort(key=lambda item: (item["locator"], item["evidence_id"]))
    if not selected:
        raise DomainProcessorError(f"no approved {normalized_section} evidence is available")

    records = [
        {
            "source_evidence_id": item["evidence_id"],
            "locator": item["locator"],
            "artifact_key": item["artifact_key"],
            "text": item["extracted_text"],
            "confidence": item["confidence"],
            "matched_terms": matched_terms[item["evidence_id"]],
        }
        for item in selected
    ]
    return (
        {
            "section": normalized_section,
            "source_snapshot_id": normalized_snapshot_id,
            "projection": "approved-section-evidence",
            "record_count": len(records),
            "records": records,
            "source_evidence_ids": [item["evidence_id"] for item in selected],
        },
        tuple(selected),
    )


def _process_domain_request(request: Any, section_name: str) -> dict[str, Any]:
    if str(request.section_name).strip().casefold() != section_name:
        raise DomainProcessorError(f"processor requires the {section_name} section")
    rows = load_approved_source_evidence(request)
    try:
        content, evidence = build_domain_section(section_name, request.source_snapshot_id, rows)
    except ValueError as error:
        raise DomainProcessorError(str(error)) from error
    return publish_deep_section(
        DeepSectionJob(
            projection_id=request.projection_id,
            section_name=section_name,
            content=content,
            evidence=evidence,
            processing_version=request.processing_version,
        )
    )


def build_procedures_section(
    source_snapshot_id: str,
    rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    return build_domain_section("procedures", source_snapshot_id, rows)


def build_electrical_section(
    source_snapshot_id: str,
    rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    return build_domain_section("electrical", source_snapshot_id, rows)


def build_inventory_section(
    source_snapshot_id: str,
    rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    return build_domain_section("inventory", source_snapshot_id, rows)


def build_maintenance_section(
    source_snapshot_id: str,
    rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    return build_domain_section("maintenance", source_snapshot_id, rows)


def process_procedures_request(request: Any) -> dict[str, Any]:
    return _process_domain_request(request, "procedures")


def process_electrical_request(request: Any) -> dict[str, Any]:
    return _process_domain_request(request, "electrical")


def process_inventory_request(request: Any) -> dict[str, Any]:
    return _process_domain_request(request, "inventory")


def process_maintenance_request(request: Any) -> dict[str, Any]:
    return _process_domain_request(request, "maintenance")
