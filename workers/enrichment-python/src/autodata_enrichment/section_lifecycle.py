"""Pure lifecycle rules shared by deep-lane handlers and tests."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Iterable


class DeepSectionValidationError(ValueError):
    """Raised when a section cannot be published with an auditable contract."""


def deep_job_idempotency_key(
    source_snapshot_id: str,
    dataset_request_id: str,
    section_name: str,
    processing_version: str,
) -> str:
    value = ":".join(
        (source_snapshot_id, dataset_request_id, "deep", section_name, processing_version)
    )
    return hashlib.sha256(value.encode()).hexdigest()


def merge_revision_content(
    prior_content: dict[str, Any], section_name: str, section_content: dict[str, Any]
) -> dict[str, Any]:
    merged = copy.deepcopy(prior_content)
    merged[section_name] = copy.deepcopy(section_content)
    return merged


def validate_evidence(evidence: Iterable[dict[str, Any]]) -> None:
    items = list(evidence)
    if not items:
        raise DeepSectionValidationError("at least one evidence record is required")
    for item in items:
        required = ("evidence_id", "locator", "extracted_text", "confidence", "reviewer_state")
        missing = [field for field in required if not item.get(field)]
        if missing:
            raise DeepSectionValidationError(f"evidence is missing: {', '.join(missing)}")
        try:
            confidence = float(item["confidence"])
        except (TypeError, ValueError) as error:
            raise DeepSectionValidationError("evidence confidence must be numeric") from error
        if not 0 <= confidence <= 1:
            raise DeepSectionValidationError("evidence confidence must be between 0 and 1")
        if item["reviewer_state"] != "approved":
            raise DeepSectionValidationError("evidence requires human approval before publication")


def evidence_input_hash(evidence: Iterable[dict[str, Any]]) -> str:
    serialized = json.dumps(list(evidence), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def next_job_status(attempt_count: int, max_attempts: int) -> str:
    if attempt_count >= max_attempts:
        return "dead_letter"
    return "failed"
