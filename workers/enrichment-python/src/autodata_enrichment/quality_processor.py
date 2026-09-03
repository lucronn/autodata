"""Deterministic quality reporting for approved source evidence."""

from __future__ import annotations

from typing import Any, Iterable

from .publisher import DeepSectionJob, publish_deep_section
from .search_processor import load_approved_source_evidence


class QualityProcessorError(RuntimeError):
    """The quality report cannot be published from available source evidence."""


def build_quality_report(
    source_snapshot_id: str,
    rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Summarize evidence quality without changing canonical domain data."""

    normalized_snapshot_id = str(source_snapshot_id).strip()
    if not normalized_snapshot_id:
        raise ValueError("source snapshot id is required")

    evidence: list[dict[str, Any]] = []
    for row in rows:
        if row.get("reviewer_state") != "approved":
            raise ValueError("quality reporting requires approved source evidence")
        required = ("evidence_id", "locator", "artifact_key", "extracted_text", "confidence")
        missing = [field for field in required if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"source evidence is missing: {', '.join(missing)}")
        confidence = float(row["confidence"])
        if not 0 <= confidence <= 1:
            raise ValueError("source evidence confidence must be between 0 and 1")
        evidence.append(
            {
                "evidence_id": str(row["evidence_id"]),
                "locator": str(row["locator"]),
                "artifact_key": str(row["artifact_key"]),
                "extracted_text": str(row["extracted_text"]),
                "confidence": confidence,
                "reviewer_state": "approved",
            }
        )

    evidence.sort(key=lambda item: item["evidence_id"])
    distribution = {"high": 0, "medium": 0, "low": 0}
    for item in evidence:
        bucket = "high" if item["confidence"] >= 0.8 else "medium" if item["confidence"] >= 0.5 else "low"
        distribution[bucket] += 1
    report = {
        "report_type": "approved-evidence-quality",
        "source_snapshot_id": normalized_snapshot_id,
        "evidence_count": len(evidence),
        "artifact_count": len({item["artifact_key"] for item in evidence}),
        "confidence_distribution": distribution,
        "source_evidence_ids": [item["evidence_id"] for item in evidence],
    }
    return report, tuple(evidence)


def process_quality_request(request: Any) -> dict[str, Any]:
    """Publish a deterministic quality report for one deep-lane request."""

    rows = load_approved_source_evidence(request)
    try:
        report, evidence = build_quality_report(request.source_snapshot_id, rows)
    except ValueError as error:
        raise QualityProcessorError(str(error)) from error
    if not evidence:
        raise QualityProcessorError("no approved source evidence is available for quality reporting")
    return publish_deep_section(
        DeepSectionJob(
            projection_id=request.projection_id,
            section_name=request.section_name,
            content=report,
            evidence=evidence,
            processing_version=request.processing_version,
        )
    )
