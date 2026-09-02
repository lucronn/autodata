#!/usr/bin/env python3
"""Run one AutoData project agent in an isolated, policy-bounded worktree."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SECRET_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"ghp_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|"
    r"AKIA[0-9A-Z]{16}|"
    r"sk-[A-Za-z0-9_-]+"
    r")(?![A-Za-z0-9])"
)
KEY_VALUE_SECRET_RE = re.compile(
    r"(?i)(\b(?:api[_-]?key|token|secret|password|private[_-]?key)\s*[=:]\s*)[^\s,;]+"
)
DECISIONS = {"pass", "fail", "blocked", "needs_review", "not_applicable"}
BLOCKED_TOOLS = ("gh", "aws", "gcloud", "az", "kubectl", "helm", "terraform", "stripe")
class RunnerError(RuntimeError):
    """A runner configuration or execution error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def redact_text(value: str) -> str:
    """Redact common credential formats before text is persisted."""

    value = SECRET_RE.sub("[REDACTED_SECRET]", value)
    return KEY_VALUE_SECRET_RE.sub(r"\1[REDACTED_SECRET]", value)


def build_provider_command(
    provider: str,
    cwd: Path,
    output_file: Path,
    schema_file: Path,
) -> list[str]:
    """Return a provider command that reads the prompt from stdin."""

    if provider == "local-cli":
        return [
            "codex",
            "exec",
            "--json",
            "--ephemeral",
            "--approve-for-me",
            "--ignore-user-config",
            "--output-schema",
            str(schema_file),
            "-o",
            str(output_file),
            "-C",
            str(cwd),
            "-",
        ]
    raise ValueError(f"unsupported provider: {provider}")


def _registry_agent(registry: dict[str, Any], name: str) -> dict[str, Any] | None:
    agents = registry.get("agents")
    if not isinstance(agents, list):
        return None
    for agent in agents:
        if isinstance(agent, dict) and agent.get("name") == name:
            return agent
    return None


def validate_envelope(
    envelope: dict[str, Any],
    registry: dict[str, Any],
    policy: dict[str, Any],
    actual_base_sha: str,
) -> list[str]:
    """Validate runner input before creating a worktree or invoking a provider."""

    errors: list[str] = []
    for field in ("run_id", "task_id", "agent_name", "base_sha", "allowed_paths", "deployment_target"):
        if field not in envelope:
            errors.append(f"missing required envelope field: {field}")

    for field in ("run_id", "task_id", "agent_name", "deployment_target"):
        if field in envelope and not isinstance(envelope[field], str):
            errors.append(f"{field} must be a string")

    run_id = envelope.get("run_id")
    if isinstance(run_id, str) and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run_id):
        errors.append("run_id contains unsupported characters")

    base_sha = envelope.get("base_sha")
    if not isinstance(base_sha, str) or not SHA_RE.fullmatch(base_sha):
        errors.append("base_sha must be a 40-character hexadecimal SHA")
    elif base_sha.lower() != actual_base_sha.lower():
        errors.append("base_sha does not match repository HEAD")

    agent_name = envelope.get("agent_name")
    if isinstance(agent_name, str) and _registry_agent(registry, agent_name) is None:
        errors.append(f"agent_name is not registered: {agent_name}")

    allowed_paths = envelope.get("allowed_paths")
    if not isinstance(allowed_paths, list) or not allowed_paths or not all(
        isinstance(item, str) and item and "\x00" not in item for item in allowed_paths
    ):
        errors.append("allowed_paths must be a non-empty list of strings")
    elif any(".." in PurePosixPath(item).parts for item in allowed_paths):
        errors.append("allowed_paths must not contain parent traversal")

    target = envelope.get("deployment_target")
    autonomy = policy.get("autonomy", {})
    if target == "production" and autonomy.get("production_deployment") is not True:
        errors.append("production deployment is disabled by policy")
    allowed_targets = autonomy.get("allowed_deployment_targets", [])
    if target not in {"none", *allowed_targets}:
        errors.append(f"deployment target is not allowed by policy: {target}")

    return errors


def _run_git(root: Path, args: Sequence[str], git_executable: str = "git") -> str:
    result = subprocess.run(
        [git_executable, *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RunnerError(f"git {' '.join(args)} failed: {redact_text(result.stderr.strip())}")
    return result.stdout


def changed_paths(root: Path, base_sha: str, git_executable: str = "git") -> list[str]:
    """Return tracked and untracked paths changed from the pinned base."""

    tracked = _run_git(
        root,
        ["diff", "--name-only", "--diff-filter=ACMRTUXB", base_sha, "--"],
        git_executable,
    )
    untracked = _run_git(
        root,
        ["ls-files", "--others", "--exclude-standard"],
        git_executable,
    )
    return sorted({line.strip() for line in (*tracked.splitlines(), *untracked.splitlines()) if line.strip()})


def path_is_allowed(path: str, allowed_patterns: Sequence[str]) -> bool:
    normalized = PurePosixPath(path)
    if normalized.is_absolute() or ".." in normalized.parts:
        return False
    return any(
        fnmatch.fnmatchcase(path, pattern) or normalized.match(pattern)
        for pattern in allowed_patterns
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunnerError(f"cannot load JSON input {path}: {error}") from error
    if not isinstance(value, dict):
        raise RunnerError(f"JSON input must be an object: {path}")
    return value


def _git_show(root: Path, revision: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RunnerError(f"file is absent at pinned base SHA: {path}")
    return result.stdout


def _commit_exists(root: Path, revision: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _make_guard_bin(directory: Path) -> Path:
    """Create command guards for the provider process, not for runner setup."""

    directory.mkdir(parents=True, exist_ok=True)
    real_git = shutil.which("git")
    if not real_git:
        raise RunnerError("git executable is unavailable")
    git_guard = directory / "git"
    git_guard.write_text(
        "#!/bin/sh\n"
        "for arg in \"$@\"; do\n"
        "  case \"$arg\" in\n"
        "    clone|fetch|pull|push|remote|reset|restore|clean|checkout|--force|--force-with-lease)\n"
        "      echo 'blocked by AutoData runner: external or destructive git command' >&2\n"
        "      exit 126\n"
        "      ;;\n"
        "  esac\n"
        "done\n"
        f"exec {shlex_quote(real_git)} \"$@\"\n",
        encoding="utf-8",
    )
    git_guard.chmod(0o755)
    for tool in BLOCKED_TOOLS:
        guard = directory / tool
        guard.write_text(
            "#!/bin/sh\n"
            "echo 'blocked by AutoData runner: external mutation/deployment command' >&2\n"
            "exit 126\n",
            encoding="utf-8",
        )
        guard.chmod(0o755)
    return directory


def shlex_quote(value: str) -> str:
    """Small local shell-quoting helper for the generated git guard."""

    return "'" + value.replace("'", "'\\''") + "'"


def _safe_environment(guard_bin: Path, isolated_config: Path) -> dict[str, str]:
    blocked_name = re.compile(
        r"(?i)(?:token|secret|password|private[_-]?key|access[_-]?key|credential|api[_-]?key)"
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if not blocked_name.search(key)
        and key not in {
            "DATABASE_URL",
            "KUBECONFIG",
            "AWS_PROFILE",
            "GOOGLE_APPLICATION_CREDENTIALS",
        }
    }
    environment.update(
        {
            "PATH": f"{guard_bin}{os.pathsep}{environment.get('PATH', '')}",
            "CI": "true",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GH_CONFIG_DIR": str(isolated_config),
        }
    )
    return environment


def _parse_agent_response(response_file: Path) -> dict[str, Any] | None:
    if not response_file.is_file():
        return None
    try:
        value = json.loads(response_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _result_manifest(
    envelope: dict[str, Any],
    response: dict[str, Any] | None,
    base_sha: str,
    implementation_sha: str,
    changed: list[str],
    output_ref: str,
    output_hash: str,
    commands: list[dict[str, Any]],
    findings: list[Any],
    require_commit: bool,
) -> dict[str, Any]:
    result = response or {}
    response_findings = result.get("findings")
    if isinstance(response_findings, list):
        findings = [*findings, *response_findings]
    decision = result.get("decision") if result.get("decision") in DECISIONS else "blocked"
    if not response:
        findings = [
            *findings,
            {
                "finding_id": "runner.malformed-agent-response",
                "severity": "high",
                "category": "reliability",
                "path": output_ref,
                "line": 0,
                "message": "provider did not emit a valid structured response",
                "reproduction": "inspect provider-output.json and provider-stderr.log",
                "blocking": True,
                "resolved_by": None,
            },
        ]
        decision = "blocked"
    if require_commit and changed and implementation_sha == base_sha:
        findings = [
            *findings,
            {
                "finding_id": "runner.uncommitted-changes",
                "severity": "high",
                "category": "reliability",
                "path": ".",
                "line": 0,
                "message": "agent changed files without creating an implementation commit",
                "reproduction": "git status --short in the isolated worktree",
                "blocking": True,
                "resolved_by": None,
            },
        ]
        decision = "blocked"
    required = (
        "deterministic_ci",
        "contract_compatibility",
        "schema_integrity",
        "data_quality",
        "security",
        "reliability",
        "independent_review",
    )
    gate_decisions = result.get("gate_decisions")
    if not isinstance(gate_decisions, dict):
        gate_decisions = {gate: "blocked" for gate in required}
    gate_reports = result.get("gate_reports")
    if not isinstance(gate_reports, list):
        gate_reports = []
    return {
        "run_id": envelope["run_id"],
        "task_id": envelope["task_id"],
        "repository": envelope.get("repository"),
        "base_sha": base_sha,
        "implementation_sha": implementation_sha,
        "agent": envelope["agent_name"],
        "phase": result.get("phase", envelope.get("phase", "implementing")),
        "contract_versions": result.get(
            "contract_versions", {"api": "v1", "events": "v1", "schema": "v1", "policy": "1"}
        ),
        "changed_paths": changed,
        "commands_run": commands,
        "findings": findings,
        "decision": decision,
        "evidence": [
            {
                "kind": "provider-response",
                "ref": output_ref,
                "sha256": output_hash,
                "description": "structured response emitted by the isolated provider run",
            }
        ],
        "task_contract": result.get("task_contract"),
        "gate_decisions": gate_decisions,
        "gate_reports": gate_reports,
        "correlation_id": result.get("correlation_id", envelope["run_id"]),
        "idempotency_key": result.get(
            "idempotency_key", f"{envelope['task_id']}:{envelope['agent_name']}:{base_sha}"
        ),
        "retry_count": envelope.get("retry_count", 0),
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


def run_agent(
    repo_root: Path,
    envelope: dict[str, Any],
    provider: str,
    output_root: Path,
    timeout_seconds: int = 1800,
) -> tuple[int, Path]:
    """Execute one provider agent and return its process/policy exit code."""

    registry = _load_json(repo_root / ".autodata-agent-registry.json")
    policy = _load_json(repo_root / ".autodata-autonomy-policy.json")
    repository_head_sha = _run_git(repo_root, ["rev-parse", "HEAD"]).strip()
    requested_base_sha = envelope.get("base_sha")
    if (
        isinstance(requested_base_sha, str)
        and requested_base_sha.lower() != repository_head_sha.lower()
        and not _commit_exists(repo_root, requested_base_sha)
    ):
        raise RunnerError("base_sha is not an existing commit in the repository")
    actual_base_sha = requested_base_sha if isinstance(requested_base_sha, str) else repository_head_sha
    envelope_errors = validate_envelope(envelope, registry, policy, actual_base_sha)
    if envelope_errors:
        raise RunnerError("invalid task envelope: " + "; ".join(envelope_errors))

    agent = _registry_agent(registry, envelope["agent_name"])
    assert agent is not None
    prompt_path = agent.get("prompt")
    if not isinstance(prompt_path, str) or not prompt_path or Path(prompt_path).is_absolute():
        raise RunnerError("registered agent prompt must be a repository-relative path")
    prompt = _git_show(repo_root, actual_base_sha, prompt_path)
    task_contract = envelope.get("task_contract", envelope.get("task_contract_ref", "not supplied"))
    if isinstance(task_contract, str) and task_contract.startswith("path:"):
        task_contract = _git_show(repo_root, actual_base_sha, task_contract.removeprefix("path:"))

    output_root.mkdir(parents=True, exist_ok=False)
    evidence_root = output_root / "evidence"
    evidence_root.mkdir()
    logs_root = output_root / "logs"
    logs_root.mkdir()
    _write_json(output_root / "task-envelope.json", envelope)
    _write_json(output_root / "task-contract.json", task_contract if isinstance(task_contract, dict) else {"ref": task_contract})
    schema_file = output_root / "agent-output.schema.json"
    _write_json(
        schema_file,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "decision": {"enum": sorted(DECISIONS)},
                "summary": {"type": "string"},
                "task_contract": {
                    "type": ["object", "null"],
                    "additionalProperties": False,
                    "properties": {
                        "task_id": {"type": "string"},
                        "goal": {"type": "string"},
                        "bounded_contexts": {"type": "array", "items": {"type": "string"}},
                        "inputs": {"type": "array", "items": {"type": "string"}},
                        "outputs": {"type": "array", "items": {"type": "string"}},
                        "acceptance_tests": {"type": "array", "items": {"type": "string"}},
                        "forbidden_scope": {"type": "array", "items": {"type": "string"}},
                        "compatibility": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "api": {"type": "string"},
                                "events": {"type": "string"},
                                "schema": {"type": "string"},
                            },
                            "required": ["api", "events", "schema"],
                        },
                    },
                    "required": [
                        "task_id",
                        "goal",
                        "bounded_contexts",
                        "inputs",
                        "outputs",
                        "acceptance_tests",
                        "forbidden_scope",
                        "compatibility",
                    ],
                },
            },
            "required": ["decision", "summary", "task_contract"],
        },
    )
    response_file = evidence_root / "provider-output.json"
    prompt_file = output_root / "prompt.txt"
    prompt_file.write_text(
        prompt
        + "\n\nAUTOMATION ENVELOPE:\n"
        + json.dumps(envelope, indent=2, sort_keys=True)
        + "\n\nTASK CONTRACT REFERENCE:\n"
        + str(task_contract)
        + "\n\nRUNNER REQUIREMENTS:\n"
        + "Work only in this isolated worktree. Do not contact GitHub or any external deployment target. "
        + "Do not print credentials. Commit implementation changes locally so the runner can pin an exact SHA. "
        + "Return only the structured response required by the output schema, including a complete summary.\n",
        encoding="utf-8",
    )

    worktree = output_root / "worktree"
    guard_bin = output_root / "guard-bin"
    isolated_config = output_root / "isolated-gh-config"
    isolated_config.mkdir()
    _make_guard_bin(guard_bin)
    _run_git(repo_root, ["worktree", "add", "--detach", str(worktree), actual_base_sha])
    started = utc_now()
    command = build_provider_command(provider, worktree, response_file, schema_file)
    process: subprocess.CompletedProcess[str]
    try:
        try:
            process = subprocess.run(
                command,
                cwd=worktree,
                input=prompt_file.read_text(encoding="utf-8"),
                text=True,
                capture_output=True,
                env=_safe_environment(guard_bin, isolated_config),
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout if isinstance(error.stdout, str) else ""
            stderr = error.stderr if isinstance(error.stderr, str) else ""
            process = subprocess.CompletedProcess(command, 124, stdout, stderr + "\nrunner timeout")
        except OSError as error:
            process = subprocess.CompletedProcess(command, 127, "", str(error))
    finally:
        changed = changed_paths(worktree, actual_base_sha)
        implementation_sha = _run_git(worktree, ["rev-parse", "HEAD"]).strip()
        _run_git(repo_root, ["worktree", "remove", "--force", str(worktree)])
        if implementation_sha != actual_base_sha:
            _run_git(
                repo_root,
                ["update-ref", f"refs/autodata/runs/{envelope['run_id']}", implementation_sha],
            )
    finished = utc_now()

    stdout = redact_text(process.stdout or "")
    stderr = redact_text(process.stderr or "")
    (logs_root / "provider-stdout.log").write_text(stdout, encoding="utf-8")
    (logs_root / "provider-stderr.log").write_text(stderr, encoding="utf-8")
    if not response_file.is_file():
        response_file.write_text("{}\n", encoding="utf-8")
    else:
        response_file.write_text(redact_text(response_file.read_text(encoding="utf-8")), encoding="utf-8")
    response = _parse_agent_response(response_file)
    findings: list[Any] = []
    if process.returncode != 0:
        findings.append(
            {
                "finding_id": "runner.provider-exit",
                "severity": "high",
                "category": "reliability",
                "path": "logs/provider-stderr.log",
                "line": 0,
                "message": f"provider exited with code {process.returncode}",
                "reproduction": "inspect provider stderr log",
                "blocking": True,
                "resolved_by": None,
            }
        )
    outside_scope = [
        path for path in changed if not path_is_allowed(path, envelope["allowed_paths"])
    ]
    if outside_scope:
        findings.append(
            {
                "finding_id": "runner.path-scope",
                "severity": "critical",
                "category": "security",
                "path": outside_scope[0],
                "line": 0,
                "message": "agent changed a path outside the declared allowed_paths",
                "reproduction": ", ".join(outside_scope),
                "blocking": True,
                "resolved_by": None,
            }
        )
    output_hash = hashlib.sha256(response_file.read_bytes()).hexdigest()
    commands = [
        {
            "command": " ".join(command),
            "exit_code": process.returncode,
            "started_at": started,
            "finished_at": finished,
            "output_ref": "logs/provider-stdout.log",
        }
    ]
    manifest = _result_manifest(
        envelope,
        response,
        actual_base_sha,
        implementation_sha,
        changed,
        "evidence/provider-output.json",
        output_hash,
        commands,
        findings,
        require_commit=_registry_agent(registry, envelope["agent_name"]).get("role") == "implementation",
    )
    if outside_scope or process.returncode != 0:
        manifest["decision"] = "blocked"
    manifest_path = output_root / "run-manifest.json"
    _write_json(manifest_path, manifest)

    try:
        from .validate_run import evaluate
    except ImportError:  # Support direct execution: python scripts/autonomy/runner.py
        from validate_run import evaluate

    validation = evaluate(manifest, policy, evidence_root=output_root)
    _write_json(output_root / "decision.json", validation)
    if not validation["passed"]:
        return 20, manifest_path
    return 0, manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--envelope", type=Path, required=True)
    parser.add_argument("--provider", choices=["local-cli"], default="local-cli")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args(argv)

    try:
        envelope = _load_json(args.envelope)
        run_id = envelope.get("run_id") or str(uuid.uuid4())
        output_root = args.output_root or Path(tempfile.gettempdir()) / "autodata-runs" / run_id
        code, manifest_path = run_agent(
            args.repo_root.resolve(), envelope, args.provider, output_root.resolve(), args.timeout_seconds
        )
        print(json.dumps({"exit_code": code, "manifest": str(manifest_path)}, sort_keys=True))
        return code
    except (OSError, RunnerError, ValueError) as error:
        print(json.dumps({"exit_code": 30, "error": redact_text(str(error))}, sort_keys=True))
        return 30


if __name__ == "__main__":
    sys.exit(main())
