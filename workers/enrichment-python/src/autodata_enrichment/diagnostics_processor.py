"""Evidence-backed diagnostics projection for the deep-lane worker."""

from __future__ import annotations

import re
from typing import Any, Iterable

from .publisher import DeepSectionJob, publish_deep_section
from .search_processor import load_approved_source_evidence


_DTC_PATTERN = re.compile(r"\b([PBCU]\d{4})\b", re.IGNORECASE)
_DIAGNOSTIC_LANGUAGE = re.compile(
    r"\b(?:diagnos\w*|dtc|trouble\s+code|fault\s+code|malfunction|scan\s+tool|symptom)\b",
    re.IGNORECASE,
)


class DiagnosticsProcessorError(RuntimeError):
    """The diagnostics section cannot be safely projected."""


def build_diagnostics_section(
    source_snapshot_id: str,
    rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Project only approved evidence with explicit diagnostic signals.

    This processor intentionally does not infer a fault, repair, severity, or
    vehicle applicability. It preserves the source text and evidence identity
    so a later domain extractor or reviewer can make those decisions.
    """

    normalized_snapshot_id = str(source_snapshot_id).strip()
    if not normalized_snapshot_id:
        raise ValueError("source snapshot id is required")

    selected: list[dict[str, Any]] = []
    diagnostic_codes_by_evidence: dict[str, list[str]] = {}
    for row in rows:
        if row.get("reviewer_state") != "approved":
            raise ValueError("diagnostics projection requires approved source evidence")
        required = ("evidence_id", "locator", "artifact_key", "extracted_text", "confidence")
        missing = [field for field in required if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"source evidence is missing: {', '.join(missing)}")
        confidence = float(row["confidence"])
        if not 0 <= confidence <= 1:
            raise ValueError("source evidence confidence must be between 0 and 1")
        text = str(row["extracted_text"]).strip()
        dtc_codes = sorted({match.upper() for match in _DTC_PATTERN.findall(text)})
        if not dtc_codes and _DIAGNOSTIC_LANGUAGE.search(text) is None:
            continue
        selected.append(
            {
                "evidence_id": str(row["evidence_id"]),
                "locator": str(row["locator"]),
                "artifact_key": str(row["artifact_key"]),
                "extracted_text": text,
                "confidence": confidence,
                "reviewer_state": "approved",
            }
        )
        diagnostic_codes_by_evidence[str(row["evidence_id"])] = dtc_codes

    selected.sort(key=lambda item: (item["locator"], item["evidence_id"]))
    if not selected:
        raise DiagnosticsProcessorError("no approved diagnostic evidence is available")

    records = [
        {
            "source_evidence_id": item["evidence_id"],
            "locator": item["locator"],
            "artifact_key": item["artifact_key"],
            "text": item["extracted_text"],
            "confidence": item["confidence"],
            "diagnostic_codes": diagnostic_codes_by_evidence[item["evidence_id"]],
        }
        for item in selected
    ]
    return (
        {
            "section": "diagnostics",
            "source_snapshot_id": normalized_snapshot_id,
            "projection": "approved-diagnostic-evidence",
            "record_count": len(records),
            "records": records,
            "source_evidence_ids": [item["evidence_id"] for item in selected],
        },
        tuple(selected),
    )


def process_diagnostics_request(request: Any) -> dict[str, Any]:
    """Publish diagnostics evidence through the immutable section contract."""

    rows = load_approved_source_evidence(request)
    try:
        content, evidence = build_diagnostics_section(request.source_snapshot_id, rows)
    except ValueError as error:
        raise DiagnosticsProcessorError(str(error)) from error
    return publish_deep_section(
        DeepSectionJob(
            projection_id=request.projection_id,
            section_name=request.section_name,
            content=content,
            evidence=evidence,
            processing_version=request.processing_version,
        )
    )
