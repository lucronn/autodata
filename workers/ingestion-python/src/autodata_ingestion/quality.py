"""Deterministic provenance and publication-quality checks for normalized bundles."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from typing import Any

from .source_bundle import SourceBundle


@dataclass(frozen=True)
class QualityFinding:
    code: str
    severity: str
    message: str
    record: str | None = None
    count: int = 1


@dataclass(frozen=True)
class QualityReport:
    status: str
    evidence_coverage: float
    findings: tuple[QualityFinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evidence_coverage": self.evidence_coverage,
            "findings": [asdict(finding) for finding in self.findings],
        }


def evaluate_source_bundle(bundle: SourceBundle) -> QualityReport:
    evidence_by_id = {item.get("evidence_id"): item for item in bundle.evidence}
    referenced = list(_fact_records(bundle))
    findings: list[QualityFinding] = []
    resolved = 0
    for record_name, record in referenced:
        evidence_id = record.get("evidence_id")
        if not evidence_id or evidence_id not in evidence_by_id:
            findings.append(
                QualityFinding(
                    "missing_evidence",
                    "critical",
                    "published candidate has no matching evidence record",
                    record_name,
                )
            )
            continue
        resolved += 1

    for evidence_id, evidence in evidence_by_id.items():
        if not evidence.get("source_uri") or not evidence.get("content_sha256"):
            findings.append(
                QualityFinding(
                    "missing_source_provenance",
                    "critical",
                    "evidence is missing source identity or content hash",
                    str(evidence_id),
                )
            )
        if not evidence.get("locator") or not evidence.get("extracted_text"):
            findings.append(
                QualityFinding(
                    "incomplete_evidence",
                    "high",
                    "evidence is missing a locator or extracted text",
                    str(evidence_id),
                )
            )
        try:
            confidence = float(evidence.get("confidence"))
        except (TypeError, ValueError):
            confidence = -1
        if not 0 <= confidence <= 1:
            findings.append(
                QualityFinding(
                    "invalid_confidence",
                    "high",
                    "evidence confidence must be between 0 and 1",
                    str(evidence_id),
                )
            )
        elif confidence < 0.8:
            findings.append(
                QualityFinding(
                    "low_confidence",
                    "high",
                    "evidence confidence is below the publication threshold",
                    str(evidence_id),
                )
            )
        if evidence.get("reviewer_state") != "approved":
            findings.append(
                QualityFinding(
                    "review_required",
                    "high",
                    "evidence has not passed human review",
                    str(evidence_id),
                )
            )

    for item in bundle.quarantined:
        findings.append(
            QualityFinding(
                "quarantined_input",
                "medium",
                str(item.get("reason", "source input requires review")),
                item.get("source_uri"),
            )
        )
    if bundle.vehicle is None:
        findings.append(
            QualityFinding(
                "vehicle_identity_unresolved",
                "critical",
                "the bundle has no canonical vehicle identity",
            )
        )

    findings = _aggregate_findings(findings)
    coverage = resolved / len(referenced) if referenced else 0.0
    if any(finding.severity == "critical" for finding in findings):
        status = "failed"
    elif findings:
        status = "needs_review"
    else:
        status = "pass"
    return QualityReport(status, coverage, tuple(findings))


def _aggregate_findings(findings: list[QualityFinding]) -> list[QualityFinding]:
    grouped: dict[tuple[str, str, str], QualityFinding] = {}
    for finding in findings:
        key = (finding.code, finding.severity, finding.message)
        if key not in grouped:
            grouped[key] = finding
        else:
            grouped[key] = replace(grouped[key], count=grouped[key].count + finding.count)
    return list(grouped.values())


def _fact_records(bundle: SourceBundle) -> Iterable[tuple[str, dict[str, Any]]]:
    if bundle.vehicle is not None:
        yield "vehicle", bundle.vehicle
    for collection_name in ("models", "powertrains", "parts", "articles", "documents"):
        for index, record in enumerate(getattr(bundle, collection_name)):
            if "evidence_id" in record:
                yield f"{collection_name}[{index}]", record
