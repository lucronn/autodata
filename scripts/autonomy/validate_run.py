#!/usr/bin/env python3
"""Validate an AutoData autonomy run against the checked-in policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
REQUIRED_FIELDS = (
    "run_id",
    "task_id",
    "base_sha",
    "implementation_sha",
    "agent",
    "phase",
    "decision",
    "evidence",
    "gate_decisions",
    "gate_reports",
    "findings",
    "evidence_completeness",
    "fast_lane_provenance_coverage",
)


def _number(value: Any, field: str, failures: list[str]) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        failures.append(f"{field} must be a number")
        return None
    return float(value)


def _verify_evidence_files(
    evidence: list[Any], evidence_root: Path | None, failures: list[str]
) -> None:
    if evidence_root is None:
        return

    root = evidence_root.resolve()
    for item in evidence:
        if not isinstance(item, dict):
            continue
        reference = item.get("ref")
        expected_hash = item.get("sha256")
        if not isinstance(reference, str) or not isinstance(expected_hash, str):
            continue
        candidate = (root / reference).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            failures.append(f"evidence path escapes evidence root: {reference}")
            continue
        if not candidate.is_file():
            failures.append(f"evidence file not found: {reference}")
            continue
        actual_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual_hash != expected_hash.lower():
            failures.append(f"evidence hash mismatch: {reference}")


def evaluate(
    manifest: dict[str, Any],
    policy: dict[str, Any],
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Return a deterministic pass/fail decision for one run manifest."""

    failures: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in manifest:
            failures.append(f"missing required field: {field}")

    for field in ("run_id", "task_id", "agent", "phase"):
        if field in manifest and not isinstance(manifest[field], str):
            failures.append(f"{field} must be a string")

    for field in ("base_sha", "implementation_sha"):
        value = manifest.get(field)
        if not isinstance(value, str) or not SHA_RE.fullmatch(value):
            failures.append(f"{field} must be a 40-character hexadecimal SHA")

    if manifest.get("decision") != "pass":
        failures.append(f"run decision is not pass: {manifest.get('decision')}")

    evidence = manifest.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        failures.append("evidence must be a non-empty list")
    else:
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                failures.append(f"evidence[{index}] must be an object")
                continue
            for field in ("kind", "ref", "sha256"):
                if not item.get(field):
                    failures.append(f"evidence[{index}] missing {field}")
        _verify_evidence_files(evidence, evidence_root, failures)

    gate_decisions = manifest.get("gate_decisions")
    if not isinstance(gate_decisions, dict):
        failures.append("gate_decisions must be an object")
        gate_decisions = {}

    merge_gate = policy.get("merge_gate", {})
    required_decisions = merge_gate.get("required_decisions", [])
    if not isinstance(required_decisions, list):
        failures.append("policy merge_gate.required_decisions must be a list")
        required_decisions = []

    for gate in required_decisions:
        if gate not in gate_decisions:
            failures.append(f"missing required gate decision: {gate}")
        elif gate_decisions[gate] != "pass":
            failures.append(f"gate decision is not pass: {gate}={gate_decisions[gate]}")

    gate_reports = manifest.get("gate_reports")
    if not isinstance(gate_reports, list):
        failures.append("gate_reports must be a list")
        gate_reports = []

    reports_by_gate: dict[str, dict[str, Any]] = {}
    for index, report in enumerate(gate_reports):
        if not isinstance(report, dict):
            failures.append(f"gate_reports[{index}] must be an object")
            continue
        gate = report.get("gate")
        if not isinstance(gate, str) or not gate:
            failures.append(f"gate_reports[{index}] missing gate")
            continue
        if gate in reports_by_gate:
            failures.append(f"duplicate gate report: {gate}")
            continue
        reports_by_gate[gate] = report

    implementation_sha = manifest.get("implementation_sha")
    for gate in required_decisions:
        report = reports_by_gate.get(gate)
        if report is None:
            failures.append(f"missing required gate report: {gate}")
            continue
        if report.get("decision") != "pass":
            failures.append(f"gate report decision is not pass: {gate}={report.get('decision')}")
        if report.get("implementation_sha") != implementation_sha:
            failures.append(f"gate report SHA mismatch: {gate}")
        report_evidence = report.get("evidence")
        if not isinstance(report_evidence, list) or not report_evidence:
            failures.append(f"gate report evidence must be non-empty: {gate}")
        elif evidence_root is not None:
            _verify_evidence_files(report_evidence, evidence_root, failures)

    findings = manifest.get("findings")
    if not isinstance(findings, list):
        failures.append("findings must be a list")
        findings = []

    critical_count = sum(
        1 for item in findings if isinstance(item, dict) and item.get("severity") == "critical"
    )
    high_count = sum(
        1 for item in findings if isinstance(item, dict) and item.get("severity") == "high"
    )
    max_critical = merge_gate.get("max_critical_findings", 0)
    max_high = merge_gate.get("max_high_findings", 0)
    if critical_count > max_critical:
        failures.append(
            f"critical findings exceed policy limit: {critical_count} > {max_critical}"
        )
    if high_count > max_high:
        failures.append(f"high findings exceed policy limit: {high_count} > {max_high}")

    evidence_completeness = _number(
        manifest.get("evidence_completeness"), "evidence_completeness", failures
    )
    if evidence_completeness is not None:
        minimum = float(merge_gate.get("min_evidence_completeness", 1.0))
        if evidence_completeness < minimum:
            failures.append(
                "evidence completeness below policy minimum: "
                f"{evidence_completeness} < {minimum}"
            )

    provenance = _number(
        manifest.get("fast_lane_provenance_coverage"),
        "fast_lane_provenance_coverage",
        failures,
    )
    if provenance is not None:
        minimum = float(merge_gate.get("min_fast_lane_provenance_coverage", 1.0))
        if provenance < minimum:
            failures.append(
                "fast-lane provenance coverage below policy minimum: "
                f"{provenance} < {minimum}"
            )

    return {
        "passed": not failures,
        "failures": failures,
        "stats": {
            "critical_findings": critical_count,
            "high_findings": high_count,
            "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
            "required_gates": len(required_decisions),
            "gate_reports": len(gate_reports),
        },
    }


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path(".autodata-autonomy-policy.json"))
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--json", action="store_true", help="emit only the JSON decision")
    args = parser.parse_args(argv)

    try:
        result = evaluate(
            _load_json(args.manifest),
            _load_json(args.policy),
            evidence_root=args.evidence_root,
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        result = {"passed": False, "failures": [f"input error: {error}"], "stats": {}}

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
