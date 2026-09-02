#!/usr/bin/env python3
"""Coordinate AutoData planning, implementation, independent gates, and evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

try:
    from .runner import run_agent
    from .validate_run import evaluate
except ImportError:  # Support direct execution: python scripts/autonomy/orchestrator.py
    from runner import run_agent
    from validate_run import evaluate


GATE_AGENTS = {
    "deterministic_ci": "autodata-test-agent",
    "contract_compatibility": "autodata-contract-agent",
    "schema_integrity": "autodata-schema-agent",
    "source_provenance": "autodata-source-agent",
    "data_quality": "autodata-data-quality-agent",
    "security": "autodata-security-agent",
    "reliability": "autodata-reliability-agent",
    "independent_review": "autodata-review-agent",
}

CONTRACT_FIELDS = (
    "task_id",
    "goal",
    "bounded_contexts",
    "inputs",
    "outputs",
    "acceptance_tests",
    "forbidden_scope",
    "compatibility",
)


def validate_task_contract(contract: Any) -> list[str]:
    """Check architect output before a builder is allowed to run."""

    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["task contract must be an object"]
    for field in CONTRACT_FIELDS:
        if field not in contract:
            errors.append(f"task contract missing field: {field}")
    for field in ("task_id", "goal"):
        if field in contract and (not isinstance(contract[field], str) or not contract[field].strip()):
            errors.append(f"{field} must be a non-empty string")
    for field in ("bounded_contexts", "inputs", "outputs", "acceptance_tests", "forbidden_scope"):
        value = contract.get(field)
        if not isinstance(value, list) or not value or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            errors.append(f"{field} must be a non-empty list of strings")
    compatibility = contract.get("compatibility")
    if not isinstance(compatibility, dict):
        errors.append("compatibility must be an object")
    else:
        for field in ("api", "events", "schema"):
            if not isinstance(compatibility.get(field), str) or not compatibility[field].strip():
                errors.append(f"compatibility.{field} must be a non-empty string")
    serialized = json.dumps(contract, sort_keys=True).lower()
    for marker in ("todo", "tbd", "to be decided", "open question"):
        if marker in serialized:
            errors.append(f"task contract contains unresolved marker: {marker}")
    return errors


def aggregate_gate_reports(
    run_id: str,
    implementation_sha: str,
    provider_runs: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Convert one provider result per gate into SHA-pinned gate reports."""

    reports: dict[str, dict[str, Any]] = {}
    for gate in GATE_AGENTS:
        result = provider_runs.get(gate, {})
        evidence = result.get("evidence")
        evidence_list = [evidence] if isinstance(evidence, dict) else []
        reports[gate] = {
            "run_id": run_id,
            "gate": gate,
            "implementation_sha": implementation_sha,
            "decision": result.get("decision", "blocked"),
            "findings": result.get("findings", []),
            "commands": result.get("commands", []),
            "evidence": evidence_list,
        }
    return reports


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return value


def _head_sha(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "cannot determine repository HEAD")
    return result.stdout.strip()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _response_for(run_root: Path) -> dict[str, Any]:
    path = run_root / "evidence" / "provider-output.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _copy_provider_evidence(source_root: Path, destination_root: Path, label: str) -> dict[str, Any]:
    source = source_root / "evidence" / "provider-output.json"
    destination = destination_root / "evidence" / f"{label}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        return {}
    shutil.copyfile(source, destination)
    return {
        "kind": "agent-response",
        "ref": f"evidence/{label}.json",
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "description": f"structured response from {label}",
    }


def _provider_result(run_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    response = _response_for(run_root)
    command = manifest.get("commands_run", [{}])
    commands = command if isinstance(command, list) else []
    local_findings = manifest.get("findings", [])
    findings = local_findings if isinstance(local_findings, list) else []
    evidence = None
    if (run_root / "evidence" / "provider-output.json").is_file():
        evidence = {
            "ref": "provider-output.json",
            "sha256": hashlib.sha256(
                (run_root / "evidence" / "provider-output.json").read_bytes()
            ).hexdigest(),
        }
    return {
        "decision": response.get("decision", "blocked"),
        "findings": findings,
        "commands": commands,
        "evidence": evidence,
        "response": response,
        "implementation_sha": manifest.get("implementation_sha"),
        "changed_paths": manifest.get("changed_paths", []),
    }


def _agent_usable(result: dict[str, Any], require_commit: bool, base_sha: str) -> bool:
    if result.get("decision") != "pass":
        return False
    if any(command.get("exit_code") != 0 for command in result.get("commands", []) if isinstance(command, dict)):
        return False
    if any(
        isinstance(finding, dict) and finding.get("severity") in {"critical", "high"}
        for finding in result.get("findings", [])
    ):
        return False
    return not require_commit or result.get("implementation_sha") not in {None, base_sha}


def orchestrate_task(
    repo_root: Path,
    task: dict[str, Any],
    provider: str,
    output_root: Path,
    timeout_seconds: int,
) -> tuple[int, Path]:
    run_id = task.get("run_id") or str(uuid.uuid4())
    base_sha = _head_sha(repo_root)
    output_root.mkdir(parents=True, exist_ok=False)
    _write_json(output_root / "task-input.json", task)

    architect_envelope = {
        "run_id": f"{run_id}-architect",
        "task_id": task["task_id"],
        "repository": task.get("repository"),
        "base_sha": base_sha,
        "agent_name": "autodata-architect",
        "task_contract_ref": json.dumps(task, sort_keys=True),
        "allowed_paths": ["docs/architecture/**", "docs/agents/**"],
        "deployment_target": "none",
        "phase": "planning",
    }
    architect_root = output_root / "agents" / "architect"
    architect_code, architect_manifest = run_agent(
        repo_root, architect_envelope, provider, architect_root, timeout_seconds
    )
    architect_result = _provider_result(architect_root, architect_manifest)
    contract = architect_result["response"].get("task_contract")
    contract_errors = validate_task_contract(contract)
    if architect_code not in {0, 20} or not _agent_usable(architect_result, False, base_sha) or contract_errors:
        decision = {
            "state": "blocked",
            "phase": "planning",
            "run_id": run_id,
            "base_sha": base_sha,
            "architect": architect_result,
            "contract_errors": contract_errors,
        }
        _write_json(output_root / "orchestration-decision.json", decision)
        return 20, output_root / "orchestration-decision.json"
    _write_json(output_root / "task-contract.json", contract)

    builder_name = task.get("builder_agent", "autodata-go-builder")
    builder_envelope = {
        "run_id": f"{run_id}-builder",
        "task_id": task["task_id"],
        "repository": task.get("repository"),
        "base_sha": base_sha,
        "agent_name": builder_name,
        "task_contract": contract,
        "allowed_paths": task["allowed_paths"],
        "deployment_target": "none",
        "phase": "implementation",
    }
    builder_root = output_root / "agents" / "builder"
    builder_code, builder_manifest = run_agent(
        repo_root, builder_envelope, provider, builder_root, timeout_seconds
    )
    builder_result = _provider_result(builder_root, builder_manifest)
    implementation_sha = builder_result.get("implementation_sha")
    if (
        builder_code not in {0, 20}
        or not _agent_usable(builder_result, True, base_sha)
        or not isinstance(implementation_sha, str)
    ):
        decision = {
            "state": "blocked",
            "phase": "implementation",
            "run_id": run_id,
            "base_sha": base_sha,
            "architect": architect_result,
            "builder": builder_result,
        }
        _write_json(output_root / "orchestration-decision.json", decision)
        return 20, output_root / "orchestration-decision.json"

    provider_runs: dict[str, dict[str, Any]] = {}
    all_commands = architect_result.get("commands", []) + builder_result.get("commands", [])
    all_findings = architect_result.get("findings", []) + builder_result.get("findings", [])
    final_evidence: list[dict[str, Any]] = []
    for label, root in (("architect", architect_root), ("builder", builder_root)):
        evidence = _copy_provider_evidence(root, output_root, label)
        if evidence:
            final_evidence.append(evidence)

    for gate, agent_name in GATE_AGENTS.items():
        gate_envelope = {
            "run_id": f"{run_id}-{gate}",
            "task_id": task["task_id"],
            "repository": task.get("repository"),
            "base_sha": implementation_sha,
            "agent_name": agent_name,
            "task_contract": contract,
            "allowed_paths": [".autodata-agent-reports/**"],
            "deployment_target": "none",
            "phase": "verifying",
        }
        gate_root = output_root / "agents" / gate
        gate_code, gate_manifest = run_agent(
            repo_root, gate_envelope, provider, gate_root, timeout_seconds
        )
        gate_result = _provider_result(gate_root, gate_manifest)
        if gate_code not in {0, 20}:
            gate_result["decision"] = "blocked"
        evidence = _copy_provider_evidence(gate_root, output_root, gate)
        if evidence:
            final_evidence.append(evidence)
            gate_result["evidence"] = {
                "ref": evidence["ref"],
                "sha256": evidence["sha256"],
            }
        provider_runs[gate] = gate_result
        all_commands.extend(gate_result.get("commands", []))
        all_findings.extend(gate_result.get("findings", []))

    gate_reports_by_gate = aggregate_gate_reports(run_id, implementation_sha, provider_runs)
    gate_decisions = {gate: report["decision"] for gate, report in gate_reports_by_gate.items()}
    all_pass = all(decision == "pass" for decision in gate_decisions.values()) and not any(
        isinstance(finding, dict) and finding.get("severity") in {"critical", "high"}
        for finding in all_findings
    )
    final_manifest = {
        "run_id": run_id,
        "task_id": task["task_id"],
        "repository": task.get("repository"),
        "base_sha": base_sha,
        "implementation_sha": implementation_sha,
        "agent": "autodata-orchestrator",
        "phase": "release-ready" if all_pass else "blocked",
        "contract_versions": {"api": "v1", "events": "v1", "schema": "v1", "policy": "1"},
        "changed_paths": builder_result.get("changed_paths", []),
        "commands_run": all_commands,
        "findings": all_findings,
        "decision": "pass" if all_pass else "blocked",
        "evidence": final_evidence,
        "gate_decisions": gate_decisions,
        "gate_reports": list(gate_reports_by_gate.values()),
        "correlation_id": run_id,
        "idempotency_key": f"{task['task_id']}:{base_sha}",
        "retry_count": task.get("retry_count", 0),
        "evidence_completeness": 1.0 if all_pass else 0.0,
        "fast_lane_provenance_coverage": 1.0 if all_pass else 0.0,
    }
    manifest_path = output_root / "run-manifest.json"
    _write_json(manifest_path, final_manifest)
    validation = evaluate(final_manifest, _load_json(repo_root / ".autodata-autonomy-policy.json"), output_root)
    _write_json(output_root / "decision.json", validation)
    return (0 if validation["passed"] else 20), manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--provider", choices=["codex"], default="codex")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args(argv)
    try:
        code, artifact = orchestrate_task(
            args.repo_root.resolve(),
            _load_json(args.task),
            args.provider,
            args.output_root.resolve(),
            args.timeout_seconds,
        )
        print(json.dumps({"exit_code": code, "artifact": str(artifact)}, sort_keys=True))
        return code
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(json.dumps({"exit_code": 30, "error": str(error)}, sort_keys=True))
        return 30


if __name__ == "__main__":
    sys.exit(main())
