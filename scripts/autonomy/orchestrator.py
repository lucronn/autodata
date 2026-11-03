#!/usr/bin/env python3
"""Coordinate the frozen v2 chain and independently replay its retained evidence."""

from __future__ import annotations
import argparse
import copy
import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any

try:
    from . import runner as r
    from .pre_implementation import validate_record
    from .validate_run import evaluate
except ImportError:
    import runner as r
    from pre_implementation import validate_record
    from validate_run import evaluate

run_agent = r.run_agent
GATE_AGENTS = dict(
    zip(
        r.GATES,
        (
            "autodata-test-agent",
            "autodata-contract-agent",
            "autodata-schema-agent",
            "autodata-source-agent",
            "autodata-data-quality-agent",
            "autodata-security-agent",
            "autodata-reliability-agent",
            "autodata-review-agent",
        ),
    )
)
CONTRACT_FIELDS = r.CONTRACT_FIELDS


def validate_task_contract(contract: Any) -> list[str]:
    return r.validate_contract(contract)


def validate_verification_contract(task: dict, trusted: dict) -> list[str]:
    errors = r.validate_verification(
        task.get("verification")
    ) + r.validate_execution_profile(task.get("execution"))
    errors += r.validate_task_input(task, trusted)
    if not errors:
        v = task["verification"]
        p = v["provenance"]
        checks = v["checks"]
        source = [
            c
            for c in checks
            if c["check_id"] == p["check_id"] and c["gate"] == "source_provenance"
        ]
        quality = [
            c
            for c in checks
            if c["check_id"] == "quality-fixture" and c["gate"] == "data_quality"
        ]
        if p["check_id"] != "source-fixture" or not source or not quality:
            errors.append(
                "R0 needs canonical source-fixture and independent quality-fixture"
            )
        if source and not any(
            o["artifact_id"] == p["report_artifact_id"]
            and o["kind"] == "provenance-result"
            and o["format"] == "json"
            for o in source[0]["outputs"]
        ):
            errors.append("canonical provenance output missing")
        if (
            quality
            and len(
                [
                    o
                    for o in quality[0]["outputs"]
                    if o["kind"] == "provenance-result" and o["format"] == "json"
                ]
            )
            != 1
        ):
            errors.append("independent quality provenance output missing")
    if not errors:
        ids = list(v["required_agent_evidence"]) + ["candidate:changes"]
        ids += [
            label + ":" + suffix
            for label in ("architect", "builder", *GATE_AGENTS)
            for suffix in ("stdout", "stderr", "invocation")
        ]
        ids += [r.trusted_artifact_id(path) for path in trusted.get("artifacts", {})]
        ids += [
            c["check_id"] + ":" + part
            for c in v["checks"]
            for part in ("command", "stdout", "stderr")
        ]
        ids += [output["artifact_id"] for c in v["checks"] for output in c["outputs"]]
        if len(ids) != len(set(ids)):
            errors.append("artifact slots must not collide")
    return errors


def _agent_usable(result: dict, require_commit: bool, base_sha: str) -> bool:
    if result.get("agent_decision", result.get("decision")) != "pass":
        return False
    if any(
        c.get("status") != "completed" or c.get("exit_code") != 0
        for c in result.get("commands", result.get("commands_run", []))
    ):
        return False
    if any(
        f.get("blocking") or f.get("severity") in ("critical", "high")
        for f in result.get("findings", [])
    ):
        return False
    return not require_commit or result.get("implementation_sha") not in (
        None,
        base_sha,
    )


def aggregate_gate_reports(
    run_id: str, implementation_sha: str, provider_runs: dict
) -> dict:
    reports = {}
    for gate in GATE_AGENTS:
        result = provider_runs.get(gate, {})
        observed = result.get("subject_sha")
        reported = (result.get("response") or {}).get("subject_sha")
        decision = result.get("agent_decision", result.get("decision", "blocked"))
        if (
            observed != implementation_sha
            or reported != implementation_sha
            or not _agent_usable(result, False, implementation_sha)
        ):
            decision = "blocked"
        reports[gate] = {
            "run_id": run_id,
            "gate": gate,
            "implementation_sha": observed,
            "decision": decision,
            "findings": result.get("findings", []),
            "commands": result.get("commands_run", result.get("commands", [])),
            "evidence": [
                a
                for a in result.get("artifacts", [])
                if a["kind"] == "provider-response"
            ],
        }
    return reports


def required_slots(trusted: dict) -> set[str]:
    v = trusted["task"]["verification"]
    result = {r.trusted_artifact_id(path) for path in trusted["artifacts"]}
    result.update(v["required_agent_evidence"])
    result.update(
        label + ":" + suffix
        for label in ("architect", "builder", *GATE_AGENTS)
        for suffix in ("stdout", "stderr", "invocation")
    )
    result.add("candidate:changes")
    for c in v["checks"]:
        result.update(
            f"{c['check_id']}:{name}" for name in ("command", "stdout", "stderr")
        )
        result.update(o["artifact_id"] for o in c["outputs"])
    return result


def calculate_coverage(
    required_ids: set[str], artifacts: list[dict], provenance: dict, evidence_root: Path
) -> dict:
    verified = set()
    seen = set()
    refs = set()
    errors = []
    if not required_ids:
        errors.append("required evidence set is empty")
    for a in artifacts:
        if type(a) is not dict:
            errors.append("invalid artifact")
            continue
        aid = a.get("artifact_id")
        ref = a.get("ref")
        if type(aid) is not str or type(ref) is not str:
            errors.append("invalid artifact identity")
            continue
        if aid in seen or ref in refs:
            errors.append("duplicate artifact ID or aliased reference")
            verified.discard(aid)
            continue
        seen.add(aid)
        refs.add(ref)
        e = r.validate_artifact(a, evidence_root)
        if e:
            errors.extend(f"{aid}: {x}" for x in e)
        elif aid in required_ids:
            verified.add(aid)
    return {
        "evidence_completeness": (
            len(verified) / len(required_ids) if required_ids else 0.0
        ),
        "fast_lane_provenance_coverage": provenance.get("ratio"),
        "coverage_scope": "synthetic-regression",
        "evidence": {
            "required_ids": sorted(required_ids),
            "verified_ids": sorted(verified),
            "missing_ids": sorted(required_ids - verified),
            "required_count": len(required_ids),
            "verified_count": len(verified),
            "errors": errors,
        },
        "provenance": provenance,
    }


def _json_artifact(artifacts: dict, aid: str, root: Path) -> dict:
    item = artifacts[aid]
    errors = r.validate_artifact(item, root)
    if errors:
        raise r.RunnerError("; ".join(errors))
    value = json.loads(r._regular_bytes(root, item["ref"]))
    if type(value) is not dict:
        raise r.RunnerError("artifact JSON must be an object")
    return value


def _measure_bundle(
    manifest: dict, trusted: dict, evidence_root: Path
) -> tuple[dict, list[str]]:
    errors = []
    artifacts = manifest.get("artifacts", [])
    if type(artifacts) is not list:
        raise r.RunnerError("artifacts must be a list")
    by_id = {
        a["artifact_id"]: a
        for a in artifacts
        if type(a) is dict and type(a.get("artifact_id")) is str
    }
    v = trusted["task"]["verification"]
    subject = manifest.get("implementation_sha")
    base = trusted["trusted_base_sha"]
    if type(subject) is not str or not r.SHA_RE.fullmatch(subject):
        raise r.RunnerError("invalid candidate SHA")
    population = trusted["population"]
    inputs = trusted["provenance_inputs"]
    provenance = {}
    quality = {}
    for check in v["checks"]:
        if check["check_id"] in (v["provenance"]["check_id"], "quality-fixture"):
            outputs = [o for o in check["outputs"] if o["kind"] == "provenance-result"]
            if len(outputs) != 1:
                errors.append("provenance check needs one typed report")
                continue
            try:
                measurement = r.measure_provenance(
                    population,
                    inputs,
                    _json_artifact(by_id, outputs[0]["artifact_id"], evidence_root),
                    subject,
                )
                errors.extend(f["message"] for f in measurement["findings"])
                if check["check_id"] == v["provenance"]["check_id"]:
                    provenance = measurement
                else:
                    quality = measurement
            except (OSError, ValueError, KeyError, r.RunnerError) as error:
                errors.append(str(error))
    if not provenance or provenance != quality:
        errors.append("independent source/quality measurements are missing or disagree")
    coverage = calculate_coverage(
        required_slots(trusted), artifacts, provenance, evidence_root
    )
    errors.extend(coverage["evidence"]["errors"])
    if coverage["evidence"]["missing_ids"]:
        errors.append("required artifact slots are missing")
    for path, data in trusted["artifacts"].items():
        item = by_id.get(r.trusted_artifact_id(path))
        if (
            item is None
            or item.get("subject_sha") != base
            or item.get("kind") != "trusted-input"
            or item.get("sha256") != hashlib.sha256(data).hexdigest()
        ):
            errors.append("trusted input copy differs: " + path)
    try:
        changes = _json_artifact(by_id, "candidate:changes", evidence_root)
        if (
            set(changes)
            != {"trusted_base_sha", "subject_sha", "changed_paths", "status_entries"}
            or changes["trusted_base_sha"] != base
            or changes["subject_sha"] != subject
            or changes["status_entries"]
            or not changes["changed_paths"]
        ):
            errors.append("candidate change-set identity/cleanliness mismatch")
        if changes.get("changed_paths") != manifest.get("changed_paths"):
            errors.append("manifest changed_paths differs from retained changes")
        protected = (
            list(trusted["artifacts"])
            + trusted["policy"].get("protected_paths", [])
            + [
                ".autodata-agent-registry.json",
                "scripts/autonomy/runner.py",
                "scripts/autonomy/orchestrator.py",
                "scripts/autonomy/agent-output.schema.json",
                trusted["task"]["task_ref"],
            ]
            + [a["prompt"] for a in trusted["registry"]["agents"]]
        )
        if r.document_scope_violations(
            changes.get("changed_paths", []), trusted["policy"]
        ):
            errors.append("candidate changed documentation outside canonical docs tree")
        for path in changes.get("changed_paths", []):
            if not r.path_is_allowed(path, trusted["task"]["allowed_paths"]):
                errors.append("candidate path outside scope")
            if any(
                path == p.rstrip("/")
                or path.startswith(p.rstrip("/") + "/")
                or r.path_is_allowed(path, [p])
                for p in protected
            ):
                errors.append("candidate changed protected input")
    except (OSError, ValueError, KeyError, r.RunnerError) as error:
        errors.append("candidate changes: " + str(error))
    runs = manifest.get("agent_runs", {})
    labels = ["architect", "builder", *GATE_AGENTS]
    if type(runs) is not dict or set(runs) != set(labels):
        errors.append("all ten independent runner records are required")
        runs = {}
    expected_commands = []
    expected_findings = []
    seen_agents = set()
    for index, label in enumerate(labels):
        run = runs.get(label)
        if type(run) is not dict:
            continue
        agent = (
            "autodata-architect"
            if label == "architect"
            else (
                trusted["task"]["builder_agent"]
                if label == "builder"
                else GATE_AGENTS[label]
            )
        )
        seen_agents.add(agent)
        wanted_subject = base if label == "architect" else subject
        checks = [c for c in v["checks"] if c["gate"] == label]
        aid = v["required_agent_evidence"][index]
        try:
            response = _json_artifact(by_id, aid, evidence_root)
            response_artifact = by_id[aid]
            if (
                response_artifact["subject_sha"] != wanted_subject
                or response_artifact["kind"] != "provider-response"
            ):
                errors.append("response artifact identity mismatch")
            available = [
                a["artifact_id"]
                for a in artifacts
                if a["check_id"] in {c["check_id"] for c in checks}
            ]
            expected = {
                "run_id": manifest["run_id"] + "-" + label,
                "task_id": trusted["task"]["task_id"],
                "agent_name": agent,
                "subject_sha": wanted_subject,
                "role": (
                    "architecture"
                    if label == "architect"
                    else "implementation" if label == "builder" else "verification"
                ),
                "check_ids": [c["check_id"] for c in checks],
                "artifact_ids": available,
                "task_contract": {k: trusted["task"][k] for k in CONTRACT_FIELDS},
            }
            errors.extend(
                r.validate_agent_response(response, trusted["schema"], expected)
            )
            if run.get("response") != response:
                errors.append("embedded response differs from retained response")
            expected_findings.extend(run.get("findings", []))
            if any(f not in run.get("findings", []) for f in response["findings"]):
                errors.append("provider finding dropped")
        except (OSError, ValueError, KeyError, r.RunnerError) as error:
            errors.append(label + ": " + str(error))
        errors.extend(r.validate_execution_profile(run.get("execution")))
        if (
            run.get("subject_sha") != wanted_subject
            or run.get("trusted_base_sha") != base
            or run.get("agent") != agent
            or not _agent_usable(run, label == "builder", base)
        ):
            errors.append(label + ": runner result is unusable/stale")
        argv = run.get("provider_argv", [])
        # Regenerate using the retained command's own paths, checking all profile flags and no conflicting duplicates.
        try:
            actual = r.build_provider_command(
                "local-cli",
                Path(argv[argv.index("-C") + 1]),
                Path(argv[argv.index("-o") + 1]),
                Path(argv[argv.index("--output-schema") + 1]),
                execution=trusted["task"]["execution"],
            )
            if argv != actual:
                errors.append("provider argv differs from exact execution profile")
        except (ValueError, IndexError, TypeError):
            errors.append("invalid provider argv")
        try:
            invocation = _json_artifact(by_id, label + ":invocation", evidence_root)
            errors.extend(r._command_errors(invocation))
            if (
                invocation != run.get("provider_command")
                or invocation["argv"] != argv
                or invocation["subject_sha"] != wanted_subject
            ):
                errors.append(
                    "provider invocation differs from retained runner observations"
                )
            if invocation["status"] != "completed" or invocation["exit_code"] != 0:
                errors.append("provider invocation did not complete successfully")
            if (
                invocation["stdout_id"] != label + ":stdout"
                or invocation["stderr_id"] != label + ":stderr"
                or invocation["output_ids"] != [aid]
            ):
                errors.append("provider invocation evidence identity mismatch")
            for pid, kind in (
                (label + ":invocation", "command-result"),
                (label + ":stdout", "stdout"),
                (label + ":stderr", "stderr"),
            ):
                if (
                    by_id[pid]["subject_sha"] != wanted_subject
                    or by_id[pid]["kind"] != kind
                    or by_id[pid]["check_id"] is not None
                ):
                    errors.append("provider artifact subject/kind mismatch")
        except (OSError, ValueError, KeyError, r.RunnerError) as error:
            errors.append("provider invocation: " + str(error))
        try:
            stdout_id = label + ":stdout"
            stdout = by_id[stdout_id]
            errors.extend(r.validate_artifact(stdout, evidence_root))
            runtime = r._runtime_metadata(
                r._regular_bytes(evidence_root, stdout["ref"]).decode()
            )
            if runtime.get("service_tier") == "priority":
                runtime["service_tier"] = "fast"
            if runtime != {
                "model": "gpt-6.1-sol",
                "reasoning_effort": "medium",
                "service_tier": "fast",
            }:
                errors.append("provider runtime profile is unconfirmed")
            if run.get("provider_runtime_validation") != "passed":
                errors.append("provider runtime certification blocked")
        except (KeyError, OSError, ValueError, r.RunnerError) as error:
            errors.append("runtime evidence: " + str(error))
        actual_commands = run.get("commands_run", [])
        if len(actual_commands) != len(checks):
            errors.append("runner command count differs from frozen checks")
        for check in checks:
            cid = check["check_id"]
            try:
                command = _json_artifact(by_id, cid + ":command", evidence_root)
                errors.extend(r._command_errors(command))
                expected_commands.append(command)
                if command not in actual_commands:
                    errors.append("command record missing from runner result")
                if (
                    command["subject_sha"] != subject
                    or command["status"] != "completed"
                    or command["exit_code"] != 0
                ):
                    errors.append(cid + ": actual command failed/stale")
                if (
                    command["argv"][1:] != check["argv"][1:]
                    or Path(command["executable"]).name
                    not in (
                        (check["argv"][0], "python3.12", "python3.13", "python3.14")
                        if check["argv"][0] == "python3"
                        else (check["argv"][0],)
                    )
                    or command["argv"][0] != command["executable"]
                    or command["cwd"] != check["cwd"]
                ):
                    errors.append(cid + ": command does not match frozen definition")
                output_ids = [o["artifact_id"] for o in check["outputs"]]
                if (
                    command["stdout_id"] != cid + ":stdout"
                    or command["stderr_id"] != cid + ":stderr"
                    or sorted(command["output_ids"]) != sorted(output_ids)
                ):
                    errors.append(cid + ": command evidence IDs differ")
                for item_id, kind in [
                    (cid + ":command", "command-result"),
                    (cid + ":stdout", "stdout"),
                    (cid + ":stderr", "stderr"),
                ] + [(o["artifact_id"], o["kind"]) for o in check["outputs"]]:
                    item = by_id[item_id]
                    if (
                        item["check_id"] != cid
                        or item["subject_sha"] != subject
                        or item["kind"] != kind
                    ):
                        errors.append("command artifact identity/kind differs")
                assessments = (run.get("response") or {}).get("assessments", [])
                if not any(
                    a["check_id"] == cid
                    and a["decision"] == "pass"
                    and cid + ":command" in a["evidence_ids"]
                    for a in assessments
                ):
                    errors.append(
                        cid
                        + ": independent passing assessment of command report missing"
                    )
            except (OSError, ValueError, KeyError, r.RunnerError) as error:
                errors.append(cid + ": " + str(error))
    if manifest.get("commands_run") != expected_commands:
        errors.append("final commands differ from retained actual reports")
    if manifest.get("findings") != expected_findings:
        errors.append("final findings differ from runner findings")
    for f in expected_findings:
        errors.extend(r.validate_finding(f))
        if f.get("blocking") or f.get("severity") in ("critical", "high"):
            errors.append("blocking finding remains")
    reports = aggregate_gate_reports(
        manifest.get("run_id", ""), subject, {g: runs.get(g, {}) for g in GATE_AGENTS}
    )
    if manifest.get("gate_reports") != list(reports.values()) or manifest.get(
        "gate_decisions"
    ) != {g: x["decision"] for g, x in reports.items()}:
        errors.append("gate aggregation differs from observed records")
    return coverage, errors


def validate_evidence_bundle(
    manifest: dict, trusted: dict, evidence_root: Path
) -> dict:
    """Read-only independent bundle replay; task/policy must come from resolved trusted inputs."""
    measurements = {}
    failures = []
    try:
        failures += validate_verification_contract(trusted["task"], trusted)
        if (
            manifest.get("schema_version") != 2
            or type(manifest.get("schema_version")) is not int
        ):
            failures.append("bundle schema_version must be 2")
        if (
            manifest.get("trusted_base_sha") != trusted["trusted_base_sha"]
            or manifest.get("base_sha") != trusted["trusted_base_sha"]
            or manifest.get("task_id") != trusted["task"]["task_id"]
        ):
            failures.append("bundle trusted/task identity differs")
        failures += r.validate_execution_profile(manifest.get("execution"))
        measurements, errors = _measure_bundle(manifest, trusted, evidence_root)
        failures += errors
        for key in (
            "evidence_completeness",
            "fast_lane_provenance_coverage",
            "coverage_scope",
        ):
            if (
                manifest.get(key) != measurements.get(key)
                or type(manifest.get(key)) is bool
            ):
                failures.append("declared metric differs from replay: " + key)
        if manifest.get("measurements") != measurements:
            failures.append("declared counts/required slots differ from replay")
        if manifest.get("evidence") != manifest.get("artifacts"):
            failures.append("legacy evidence list differs from typed artifacts")
        result = evaluate(manifest, trusted["policy"], evidence_root)
        failures += result["failures"]
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        r.RunnerError,
    ) as error:
        failures.append("invalid evidence bundle: " + r.redact_text(str(error)))
    return {"passed": not failures, "failures": failures, "measurements": measurements}


def _provider_result(run_root: Path, manifest_path: Path) -> dict:
    manifest = r._load_json(manifest_path)
    # Never read a raw provider pass as the runner-owned decision.
    manifest["decision"] = manifest.get("agent_decision", "blocked")
    return manifest


def orchestrate_task(
    repo_root: Path, task: dict, provider: str, output_root: Path, timeout_seconds: int
) -> tuple[int, Path]:
    if r._status(repo_root):
        raise r.RunnerError("coordinator checkout must be clean")
    base = r._run_git(repo_root, ["rev-parse", "HEAD"]).strip()
    trusted = r.load_trusted_inputs(repo_root, base, task.get("task_ref"))
    errors = validate_verification_contract(task, trusted)
    if errors:
        raise r.RunnerError("; ".join(errors))
    if output_root.resolve().is_relative_to(repo_root.resolve()):
        raise r.RunnerError("output must be outside checkout")
    run_id = task.get("run_id") or str(uuid.uuid4())
    if not r.ID_RE.fullmatch(run_id):
        raise r.RunnerError("invalid run_id")
    output_root.mkdir(parents=True, exist_ok=False)
    artifacts = r.retain_trusted_inputs(trusted, output_root)
    runs = {}
    subject = base
    labels = ["architect", "builder", *GATE_AGENTS]
    for index, label in enumerate(labels):
        agent = (
            "autodata-architect"
            if label == "architect"
            else task["builder_agent"] if label == "builder" else GATE_AGENTS[label]
        )
        envelope = {
            "run_id": run_id + "-" + label,
            "task_id": task["task_id"],
            "repository": task["repository"],
            "base_sha": subject,
            "subject_sha": subject,
            "trusted_base_sha": base,
            "task_ref": task["task_ref"],
            "agent_name": agent,
            "task_contract": {k: copy.deepcopy(task[k]) for k in CONTRACT_FIELDS},
            "allowed_paths": task["allowed_paths"] if label == "builder" else [],
            "deployment_target": "none",
            "execution": copy.deepcopy(task["execution"]),
            "evidence_label": label,
            "response_artifact_id": task["verification"]["required_agent_evidence"][
                index
            ],
            "gate": label if label in GATE_AGENTS else None,
        }
        root = output_root / "agents" / label
        code, path = run_agent(
            repo_root, envelope, provider, root, timeout_seconds, trusted=trusted
        )
        run = _provider_result(root, path)
        if code not in (0, 20):
            run["agent_decision"] = "blocked"
            run["decision"] = "blocked"
        # Copy every retained artifact before aggregating. Keep IDs/refs deterministic.
        copied = []
        for a in run.get("artifacts", []):
            try:
                if r.validate_artifact(a, root):
                    raise r.RunnerError("source artifact failed verification")
                retained = r._save_artifact(
                    r._regular_bytes(root, a["ref"]),
                    output_root,
                    a["artifact_id"],
                    a["kind"],
                    a["subject_sha"],
                    a["check_id"],
                )
                if retained["sha256"] != a["sha256"]:
                    raise r.RunnerError("artifact changed while copying")
                artifacts.append(retained)
                copied.append(retained)
            except (OSError, r.RunnerError) as error:
                run.setdefault("findings", []).append(
                    r.finding("runner.aggregate-copy", str(error))
                )
                run["agent_decision"] = "blocked"
        run["artifacts"] = copied
        runs[label] = run
        if label in ("architect", "builder") and not _agent_usable(
            run, label == "builder", base
        ):
            decision = {
                "state": "blocked",
                "phase": "planning" if label == "architect" else "implementation",
                "run_id": run_id,
                "trusted_base_sha": base,
                "agent_runs": runs,
                "artifacts": artifacts,
            }
            path = output_root / "orchestration-decision.json"
            r._write_json(path, decision)
            return 20, path
        if label == "builder":
            subject = run["subject_sha"]
    reports = aggregate_gate_reports(run_id, subject, {g: runs[g] for g in GATE_AGENTS})
    all_pass = all(x["decision"] == "pass" for x in reports.values())
    final = {
        "schema_version": 2,
        "run_id": run_id,
        "task_id": task["task_id"],
        "repository": task["repository"],
        "base_sha": base,
        "trusted_base_sha": base,
        "implementation_sha": subject,
        "agent": "autodata-orchestrator",
        "phase": "release-ready" if all_pass else "blocked",
        "decision": "pass" if all_pass else "blocked",
        "contract_versions": {
            "api": "v1",
            "events": "v1",
            "schema": "v1",
            "policy": "1",
        },
        "execution": task["execution"],
        "changed_paths": runs["builder"]["changed_paths"],
        "commands_run": [
            c for label in labels for c in runs[label].get("commands_run", [])
        ],
        "findings": [f for label in labels for f in runs[label].get("findings", [])],
        "artifacts": artifacts,
        "evidence": artifacts,
        "agent_runs": runs,
        "gate_reports": list(reports.values()),
        "gate_decisions": {g: x["decision"] for g, x in reports.items()},
        "correlation_id": run_id,
        "idempotency_key": task["task_id"] + ":" + base,
        "retry_count": 0,
        "coverage_scope": "synthetic-regression",
        "provider_runtime_validation": "passed",
    }
    measurements, errors = _measure_bundle(final, trusted, output_root)
    final.update(
        {
            k: measurements[k]
            for k in (
                "evidence_completeness",
                "fast_lane_provenance_coverage",
                "coverage_scope",
            )
        }
    )
    final["measurements"] = measurements
    validation = validate_evidence_bundle(final, trusted, output_root)
    if not validation["passed"]:
        final["decision"] = "blocked"
        final["phase"] = "blocked"
    path = output_root / "run-manifest.json"
    r._write_json(path, final)
    r._write_json(output_root / "decision.json", validation)
    return (0 if validation["passed"] else 20), path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--provider", choices=["local-cli"], default="local-cli")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args(argv)
    try:
        code, path = orchestrate_task(
            args.repo_root.resolve(),
            r._load_json(args.task),
            args.provider,
            args.output_root.resolve(),
            args.timeout_seconds,
        )
        print(json.dumps({"exit_code": code, "artifact": str(path)}))
        return code
    except (OSError, ValueError, KeyError, r.RunnerError) as error:
        print(json.dumps({"exit_code": 30, "error": r.redact_text(str(error))}))
        return 30


if __name__ == "__main__":
    sys.exit(main())
