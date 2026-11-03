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
import signal
import selectors
import stat
import time
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

try:
    from .pre_implementation import validate_record
except ImportError:  # Support direct execution: python scripts/autonomy/runner.py
    from pre_implementation import validate_record


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
    provider: str, cwd: Path, output_file: Path, schema_file: Path, *, execution: dict
) -> list[str]:
    if provider != "local-cli":
        raise ValueError(f"unsupported provider: {provider}")
    errors = validate_execution_profile(execution)
    if errors:
        raise RunnerError("; ".join(errors))
    return [
        "codex",
        "exec",
        "--json",
        "--ephemeral",
        "--approve-for-me",
        "--ignore-user-config",
        "--model",
        "gpt-6.1-sol",
        "-c",
        'model_reasoning_effort="medium"',
        "-c",
        'service_tier="fast"',
        "-c",
        "features.fast_mode=true",
        "--output-schema",
        str(schema_file),
        "-o",
        str(output_file),
        "-C",
        str(cwd),
        "-",
    ]


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
    for field in (
        "run_id",
        "task_id",
        "agent_name",
        "base_sha",
        "allowed_paths",
        "deployment_target",
    ):
        if field not in envelope:
            errors.append(f"missing required envelope field: {field}")

    for field in ("run_id", "task_id", "agent_name", "deployment_target"):
        if field in envelope and not isinstance(envelope[field], str):
            errors.append(f"{field} must be a string")

    run_id = envelope.get("run_id")
    if isinstance(run_id, str) and not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]*", run_id
    ):
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
    if (
        not isinstance(allowed_paths, list)
        or not allowed_paths
        or not all(
            isinstance(item, str) and item and "\x00" not in item
            for item in allowed_paths
        )
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
        raise RunnerError(
            f"git {' '.join(args)} failed: {redact_text(result.stderr.strip())}"
        )
    return result.stdout


def changed_paths(root: Path, base_sha: str, git_executable: str = "git") -> list[str]:
    tracked = _run_git(
        root,
        ["diff", "--name-only", "-z", "--no-renames", base_sha, "--"],
        git_executable,
    )
    untracked = _run_git(
        root, ["ls-files", "--others", "--exclude-standard", "-z"], git_executable
    )
    return sorted(set(filter(None, tracked.split("\0") + untracked.split("\0"))))


def path_is_allowed(path: str, allowed_patterns: Sequence[str]) -> bool:
    normalized = PurePosixPath(path)
    if normalized.is_absolute() or ".." in normalized.parts:
        return False
    return any(
        fnmatch.fnmatchcase(path, pattern) or normalized.match(pattern)
        for pattern in allowed_patterns
    )


def document_scope_violations(
    paths: Sequence[str], policy: dict[str, Any]
) -> list[str]:
    """Return documentation paths outside the repository's canonical document tree."""

    document_paths = sorted(
        path
        for path in paths
        if PurePosixPath(path).suffix.lower() in {".md", ".mdx", ".rst", ".adoc"}
    )
    if not document_paths:
        return []
    documentation = policy.get("documentation")
    if not isinstance(documentation, dict):
        return document_paths
    extensions = documentation.get("document_extensions", [])
    allowed_paths = documentation.get("canonical_paths", [])
    if not isinstance(extensions, list) or not all(
        isinstance(item, str) for item in extensions
    ):
        return document_paths
    if not isinstance(allowed_paths, list) or not all(
        isinstance(item, str) for item in allowed_paths
    ):
        return document_paths
    return sorted(
        path
        for path in document_paths
        if PurePosixPath(path).suffix.lower() in extensions
        and not path_is_allowed(path, allowed_paths)
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
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _make_guard_bin(directory: Path) -> Path:
    """Create command guards for the provider process, not for runner setup."""

    directory.mkdir(parents=True, exist_ok=True)
    real_git = shutil.which("git")
    if not real_git:
        raise RunnerError("git executable is unavailable")
    git_guard = directory / "git"
    git_guard.write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        '  case "$arg" in\n'
        "    clone|fetch|pull|push|remote|reset|restore|clean|checkout|--force|--force-with-lease)\n"
        "      echo 'blocked by AutoData runner: external or destructive git command' >&2\n"
        "      exit 126\n"
        "      ;;\n"
        "  esac\n"
        "done\n"
        f'exec {shlex_quote(real_git)} "$@"\n',
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
        and key
        not in {
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


# Fixed v2 record validators. No mutable-checkout schema or provider text is authoritative.
EXECUTION = {
    "model": "gpt-6.1-sol",
    "reasoning_effort": "medium",
    "service_tier": "fast",
    "features": {"fast_mode": True},
    "allow_fallback": False,
}
GATES = (
    "deterministic_ci",
    "contract_compatibility",
    "schema_integrity",
    "source_provenance",
    "data_quality",
    "security",
    "reliability",
    "independent_review",
)
CONTRACT_FIELDS = (
    "task_id",
    "goal",
    "bounded_contexts",
    "inputs",
    "outputs",
    "acceptance_tests",
    "forbidden_scope",
    "compatibility",
    "pre_implementation",
    "execution",
    "verification",
)
MAX_ARTIFACT = 16 * 1024 * 1024
MAX_CHECK = 64 * 1024 * 1024
MAX_LOG = 4 * 1024 * 1024
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
KINDS = (
    "command-result",
    "stdout",
    "stderr",
    "provider-response",
    "test-result",
    "provenance-population",
    "provenance-result",
    "trusted-input",
    "change-set",
)
FIELDS = {
    "AgentResponseV2": (
        "schema_version",
        "run_id",
        "task_id",
        "agent_name",
        "subject_sha",
        "decision",
        "summary",
        "task_contract",
        "findings",
        "assessments",
        "evidence_ids",
    ),
    "Finding": (
        "finding_id",
        "severity",
        "category",
        "path",
        "line",
        "message",
        "reproduction",
        "blocking",
        "resolved_by",
        "evidence_ids",
    ),
    "Assessment": ("check_id", "decision", "evidence_ids", "explanation"),
    "ArtifactRecord": (
        "artifact_id",
        "kind",
        "ref",
        "sha256",
        "size_bytes",
        "subject_sha",
        "check_id",
    ),
    "CommandRecord": (
        "schema_version",
        "check_id",
        "subject_sha",
        "argv",
        "executable",
        "cwd",
        "started_at",
        "finished_at",
        "status",
        "exit_code",
        "stdout_id",
        "stderr_id",
        "output_ids",
    ),
    "FactProof": (
        "fact_id",
        "source_sha256",
        "extraction_sha256",
        "source_pointer",
        "extraction_pointer",
        "value_sha256",
    ),
    "ProvenanceResult": (
        "schema_version",
        "subject_sha",
        "population_id",
        "scope",
        "population_sha256",
        "eligible_ids",
        "covered_ids",
        "uncovered",
        "records",
    ),
    "Uncovered": ("fact_id", "reason"),
    "Check": (
        "check_id",
        "gate",
        "argv",
        "cwd",
        "timeout_seconds",
        "expected_exit_code",
        "outputs",
    ),
    "Output": ("artifact_id", "kind", "relative_path", "format"),
    "Verification": ("checks", "provenance", "required_agent_evidence"),
    "Provenance": ("check_id", "population_ref", "report_artifact_id"),
    "Execution": tuple(EXECUTION),
    "Features": ("fast_mode",),
    "TaskContract": CONTRACT_FIELDS,
    "Compatibility": ("api", "events", "schema"),
    "PreImplementation": (
        "goal",
        "plan_ref",
        "issue_ref",
        "project_ref",
        "repository_doc_refs",
        "todo",
        "status",
        "updated_at",
    ),
}
ENUMS = {
    "decision": sorted(DECISIONS),
    "severity": ["critical", "high", "medium", "low", "info"],
    "category": [
        "schema",
        "provenance",
        "quality",
        "security",
        "reliability",
        "contract",
        "test",
    ],
    "kind": list(KINDS),
    "status": ["completed", "timed_out", "unavailable"],
    "scope": ["synthetic-regression"],
    "gate": list(GATES),
    "format": ["json", "text"],
}


def finding(
    code: str, message: str, path: str = ".", category: str = "reliability"
) -> dict:
    return {
        "finding_id": code,
        "severity": "high",
        "category": category,
        "path": path,
        "line": 0,
        "message": message,
        "reproduction": "replay retained runner evidence",
        "blocking": True,
        "resolved_by": None,
        "evidence_ids": [],
    }


def safe_ref(value: object, dot: bool = False) -> bool:
    return (
        type(value) is str
        and bool(value)
        and "\\" not in value
        and "\x00" not in value
        and not value.startswith("/")
        and (
            value == "."
            and dot
            or all(p not in ("", "..", ".") for p in value.split("/"))
        )
    )


def _shape(value: object, name: str) -> list[str]:
    if type(value) is not dict:
        return [f"{name} must be an object"]
    return [f"{name}.{k} is required" for k in FIELDS[name] if k not in value] + [
        f"{name}.{k} is unknown" for k in value if k not in FIELDS[name]
    ]


def _strings(value: object, nonempty: bool = False) -> bool:
    return (
        type(value) is list
        and (bool(value) or not nonempty)
        and all(type(x) is str and x for x in value)
    )


def _ids(value: object) -> bool:
    return (
        _strings(value)
        and all(ID_RE.fullmatch(x) for x in value)
        and len(value) == len(set(value))
    )


def validate_execution_profile(execution: object) -> list[str]:
    # JSON equality alone would equate True and 1.
    if (
        type(execution) is not dict
        or _shape(execution, "Execution")
        or type(execution.get("features")) is not dict
        or _shape(execution["features"], "Features")
        or execution != EXECUTION
        or execution.get("allow_fallback") is not False
        or execution["features"].get("fast_mode") is not True
    ):
        return [
            "execution must specify gpt-6.1-sol / medium / fast, Fast enabled, no fallback"
        ]
    return []


def validate_schema_inventory(schema: dict) -> list[str]:
    errors = []
    response = schema.get("$defs", {}).get("AgentResponseV2", {})
    if any(
        schema.get(field) != response.get(field)
        for field in ("type", "additionalProperties", "properties", "required")
    ):
        errors.append("provider root schema differs from AgentResponseV2")
    for name, fields in FIELDS.items():
        definition = schema.get("$defs", {}).get(name, {})
        if (
            set(definition.get("properties", {})) != set(fields)
            or set(definition.get("required", [])) != set(fields)
            or definition.get("additionalProperties") is not False
        ):
            errors.append(f"schema inventory differs: {name}")
        for field, prop in definition.get("properties", {}).items():
            if (
                field in ENUMS
                and not (name == "PreImplementation" and field == "status")
                and prop.get("enum") != ENUMS[field]
            ):
                errors.append(f"schema enum differs: {name}.{field}")
    if (
        schema.get("$defs", {})
        .get("PreImplementation", {})
        .get("properties", {})
        .get("status", {})
        .get("const")
        != "synchronized"
    ):
        errors.append("schema pre-implementation status differs")
    for name, field, value in [
        *(
            ("Execution", key, value)
            for key, value in EXECUTION.items()
            if key != "features"
        ),
        ("Features", "fast_mode", True),
        *(
            (name, "schema_version", 2)
            for name in ("AgentResponseV2", "CommandRecord", "ProvenanceResult")
        ),
    ]:
        prop = (
            schema.get("$defs", {}).get(name, {}).get("properties", {}).get(field, {})
        )
        if type(prop.get("const")) is not type(value) or prop.get("const") != value:
            errors.append(f"schema constant differs: {name}.{field}")
    return errors


def _validate_verification(value: object) -> list[str]:
    errors = _shape(value, "Verification")
    if errors:
        return errors
    checks = value["checks"]
    if type(checks) is not list or not checks:
        return ["verification checks must be nonempty"]
    seen = set()
    outputs = set()
    gates = set()
    for check in checks:
        e = _shape(check, "Check")
        errors += e
        if e:
            continue
        cid = check["check_id"]
        if type(cid) is not str or not ID_RE.fullmatch(cid) or cid in seen:
            errors.append("invalid or duplicate check_id")
        else:
            seen.add(cid)
        if check["gate"] not in GATES:
            errors.append("unknown check gate")
        else:
            gates.add(check["gate"])
        if (
            not _strings(check["argv"], True)
            or check["argv"][0] not in ("python3", "go", "node")
            or not safe_ref(check["cwd"], True)
            or type(check["timeout_seconds"]) is not int
            or not 1 <= check["timeout_seconds"] <= 1800
            or type(check["expected_exit_code"]) is not int
            or check["expected_exit_code"] != 0
        ):
            errors.append("invalid check execution definition")
        if type(check["outputs"]) is not list:
            errors.append("outputs must be a list")
            continue
        paths = set()
        for output in check["outputs"]:
            e = _shape(output, "Output")
            errors += e
            if e:
                continue
            oid = output["artifact_id"]
            if type(oid) is not str or not ID_RE.fullmatch(oid) or oid in outputs:
                errors.append("invalid or duplicate output ID")
            else:
                outputs.add(oid)
            if (
                output["kind"] not in KINDS
                or not safe_ref(output["relative_path"])
                or output["relative_path"] in paths
                or output["format"] not in ("json", "text")
            ):
                errors.append("invalid output definition")
            if type(output["relative_path"]) is str:
                paths.add(output["relative_path"])
    if gates != set(GATES):
        errors.append("every required gate needs a command")
    errors += _shape(value["provenance"], "Provenance")
    p = value["provenance"]
    if type(p) is dict:
        if (
            p.get("check_id") not in seen
            or p.get("report_artifact_id") not in outputs
            or not safe_ref(p.get("population_ref"))
        ):
            errors.append("invalid provenance definition")
    if (
        not _ids(value["required_agent_evidence"])
        or len(value["required_agent_evidence"]) != 10
    ):
        errors.append("ten independent agent evidence IDs are required")
    return errors


def validate_verification(value: object) -> list[str]:
    try:
        return _validate_verification(value)
    except (TypeError, ValueError, KeyError, AttributeError):
        return ["verification contains invalid primitive types"]


def validate_contract(value: object) -> list[str]:
    errors = _shape(value, "TaskContract")
    if errors:
        return errors
    for key in ("task_id", "goal"):
        if type(value[key]) is not str or not value[key].strip():
            errors.append(f"{key} must be a non-empty string")
    for key in (
        "bounded_contexts",
        "inputs",
        "outputs",
        "acceptance_tests",
        "forbidden_scope",
    ):
        if not _strings(value[key], True):
            errors.append(f"{key} must be nonempty strings")
    errors += _shape(value["compatibility"], "Compatibility")
    if type(value["compatibility"]) is dict and not all(
        type(v) is str and v for v in value["compatibility"].values()
    ):
        errors.append("invalid compatibility")
    errors += _shape(value["pre_implementation"], "PreImplementation")
    record = value["pre_implementation"]
    if type(record) is dict:
        for k in FIELDS["PreImplementation"]:
            if k in ("todo", "repository_doc_refs"):
                if not _strings(record.get(k), True):
                    errors.append(f"invalid pre_implementation.{k}")
            elif type(record.get(k)) is not str or not record[k]:
                errors.append(f"invalid pre_implementation.{k}")
        if record.get("status") != "synchronized":
            errors.append("pre_implementation is not synchronized")
    return (
        errors
        + validate_execution_profile(value["execution"])
        + validate_verification(value["verification"])
    )


def validate_finding(value: object) -> list[str]:
    errors = _shape(value, "Finding")
    if errors:
        return errors
    for key in ("finding_id", "message", "reproduction", "path"):
        if type(value[key]) is not str or not value[key]:
            errors.append(f"invalid finding {key}")
    if type(value["finding_id"]) is str and not ID_RE.fullmatch(value["finding_id"]):
        errors.append("invalid finding ID")
    if (
        value["severity"] not in ENUMS["severity"]
        or value["category"] not in ENUMS["category"]
    ):
        errors.append("invalid finding enum")
    if (
        type(value["line"]) is not int
        or value["line"] < 0
        or type(value["blocking"]) is not bool
    ):
        errors.append("invalid finding line/blocking")
    if value["resolved_by"] is not None and (
        type(value["resolved_by"]) is not str
        or not ID_RE.fullmatch(value["resolved_by"])
    ):
        errors.append("invalid resolution")
    if not _ids(value["evidence_ids"]):
        errors.append("invalid finding evidence IDs")
    if not safe_ref(value["path"], True):
        errors.append("invalid finding path")
    return errors


def _validate_agent_response(value: object, schema: dict, expected: dict) -> list[str]:
    errors = _shape(value, "AgentResponseV2")
    if errors:
        return errors
    if type(value["schema_version"]) is not int or value["schema_version"] != 2:
        errors.append("schema_version must be 2")
    for k in ("run_id", "task_id", "agent_name", "subject_sha"):
        if value[k] != expected.get(k):
            errors.append(f"{k} differs from observed identity")
        pattern = SHA_RE if k == "subject_sha" else ID_RE
        if type(value[k]) is not str or not pattern.fullmatch(value[k]):
            errors.append(f"invalid {k}")
    if (
        type(value["decision"]) is not str
        or value["decision"] not in DECISIONS
        or type(value["summary"]) is not str
        or not value["summary"]
    ):
        errors.append("invalid decision/summary")
    ids = expected.get("artifact_ids", [])
    checks = expected.get("check_ids", [])
    role = expected.get("role")
    contract = expected.get("task_contract")
    if role in ("architecture", "planning"):
        errors += validate_contract(value["task_contract"])
        if value["task_contract"] != contract:
            errors.append("architect changed frozen task_contract")
    elif value["task_contract"] is not None:
        errors.append("only architect may return task_contract")
    if type(value["findings"]) is not list:
        errors.append("findings must be a list")
    else:
        seen = set()
        for f in value["findings"]:
            errors += validate_finding(f)
            if type(f) is dict:
                fid = f.get("finding_id")
                if type(fid) is str:
                    if fid in seen:
                        errors.append("duplicate finding ID")
                    seen.add(fid)
                if type(f.get("evidence_ids")) is list and any(
                    x not in ids for x in f["evidence_ids"]
                ):
                    errors.append("dangling finding evidence")
    if not _ids(value["evidence_ids"]) or any(
        x not in ids for x in value["evidence_ids"]
    ):
        errors.append("unknown/duplicate evidence IDs")
    assessments = value["assessments"]
    seen = []
    if type(assessments) is not list:
        errors.append("assessments must be a list")
    else:
        for a in assessments:
            e = _shape(a, "Assessment")
            errors += e
            if e:
                continue
            if (
                type(a["check_id"]) is not str
                or a["check_id"] not in checks
                or type(a["decision"]) is not str
                or a["decision"] not in DECISIONS
                or not _ids(a["evidence_ids"])
                or any(x not in ids for x in a["evidence_ids"])
                or type(a["explanation"]) is not str
                or not a["explanation"]
            ):
                errors.append("invalid assessment")
            if type(a["check_id"]) is str:
                seen.append(a["check_id"])
    assigned = (
        checks if role not in ("architecture", "planning", "implementation") else []
    )
    if sorted(seen) != sorted(assigned):
        errors.append("assessments must match assigned checks exactly")
    return errors


def validate_agent_response(value: object, schema: dict, expected: dict) -> list[str]:
    try:
        return _validate_agent_response(value, schema, expected)
    except (TypeError, ValueError, KeyError, AttributeError):
        return ["agent response contains invalid primitive types"]


def _blob(root: Path, sha: str, path: str) -> bytes:
    if not safe_ref(path):
        raise RunnerError("unsafe trusted input path")
    p = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=root, capture_output=True)
    if p.returncode:
        raise RunnerError(f"file is absent at pinned base SHA: {path}")
    return p.stdout


def resolve_commit(root: Path, sha: str) -> str:
    if type(sha) is not str or not SHA_RE.fullmatch(sha):
        raise RunnerError("commit must be a full lowercase SHA")
    actual = _run_git(root, ["rev-parse", "--verify", f"{sha}^{{commit}}"]).strip()
    if actual != sha:
        raise RunnerError("commit mismatch")
    return actual


def _load_trusted_inputs(repo_root: Path, trusted_base_sha: str, task_ref: str) -> dict:
    resolve_commit(repo_root, trusted_base_sha)
    if (
        not safe_ref(task_ref)
        or not task_ref.startswith("docs/agents/tasks/")
        or not task_ref.endswith(".json")
    ):
        raise RunnerError("unsafe task_ref")
    snapshots = {}

    def read(path):
        data = _blob(repo_root, trusted_base_sha, path)
        snapshots[path] = data
        return json.loads(data)

    task = read(task_ref)
    policy = read(".autodata-autonomy-policy.json")
    registry = read(".autodata-agent-registry.json")
    schema = read("scripts/autonomy/agent-output.schema.json")
    errors = (
        validate_schema_inventory(schema)
        + validate_execution_profile(task.get("execution"))
        + validate_verification(task.get("verification"))
    )
    if (
        type(task.get("evidence_contract_version")) is not int
        or task.get("evidence_contract_version") != 2
        or task.get("task_ref") != task_ref
    ):
        errors.append("committed task must declare v2 and its task_ref")
    if set(policy.get("merge_gate", {}).get("required_decisions", [])) != set(GATES):
        errors.append("required policy gates differ")
    for k in ("min_evidence_completeness", "min_fast_lane_provenance_coverage"):
        if (
            type(policy.get("merge_gate", {}).get(k)) not in (int, float)
            or policy.get("merge_gate", {}).get(k) != 1.0
        ):
            errors.append("unsupported policy coverage threshold")
    allowed = task.get("allowed_paths")
    if not _strings(allowed, True) or any(not safe_ref(path) for path in allowed):
        errors.append("task allowed_paths must be safe relative patterns")
    builder = _registry_agent(registry, task.get("builder_agent"))
    if builder is None or builder.get("role") != "implementation":
        errors.append("task builder must be a registered implementation agent")
    errors += validate_record(
        task.get("pre_implementation"), repo_root, trusted_base_sha, policy
    )
    contract = {k: task.get(k) for k in CONTRACT_FIELDS}
    errors += validate_contract(contract)
    if errors:
        raise RunnerError("; ".join(errors))
    for path in [
        task["pre_implementation"]["plan_ref"],
        *task["pre_implementation"]["repository_doc_refs"],
    ]:
        snapshots[path] = _blob(repo_root, trusted_base_sha, path)
    prompts = {}
    for agent in registry.get("agents", []):
        path = agent["prompt"]
        data = _blob(repo_root, trusted_base_sha, path)
        snapshots[path] = data
        prompts[agent["name"]] = data.decode("utf-8")
    for path in (
        "scripts/autonomy/runner.py",
        "scripts/autonomy/orchestrator.py",
        "scripts/autonomy/pre_implementation.py",
        "scripts/autonomy/validate_run.py",
    ):
        data = _blob(repo_root, trusted_base_sha, path)
        snapshots[path] = data
        loaded = Path(__file__).parent / Path(path).name
        if loaded.read_bytes() != data:
            raise RunnerError(f"loaded evaluator differs from trusted base: {path}")
    population_ref = task["verification"]["provenance"]["population_ref"]
    population = read(population_ref)
    inputs = {}
    for rec in population.get("records", []):
        for field in ("source_ref", "extraction_ref"):
            ref = rec[field]
            if not safe_ref(ref):
                raise RunnerError("unsafe population input")
            path = str(PurePosixPath(population_ref).parent / ref)
            inputs[ref] = _blob(repo_root, trusted_base_sha, path)
            snapshots[path] = inputs[ref]
    return {
        "trusted_base_sha": trusted_base_sha,
        "task": task,
        "policy": policy,
        "registry": registry,
        "schema": schema,
        "prompts": prompts,
        "artifacts": snapshots,
        "population": population,
        "provenance_inputs": inputs,
    }


def load_trusted_inputs(repo_root: Path, trusted_base_sha: str, task_ref: str) -> dict:
    try:
        return _load_trusted_inputs(repo_root, trusted_base_sha, task_ref)
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        raise RunnerError("trusted input records are malformed") from error


def validate_task_input(task: dict, trusted: dict) -> list[str]:
    committed = trusted["task"]
    return (
        []
        if canonical({k: v for k, v in task.items() if k != "run_id"})
        == canonical({k: v for k, v in committed.items() if k != "run_id"})
        else ["external task overrides frozen authorization"]
    )


def _status(worktree: Path) -> list[str]:
    return list(
        filter(
            None,
            _run_git(
                worktree,
                [
                    "status",
                    "--porcelain=v1",
                    "-z",
                    "--untracked-files=all",
                    "--ignored=matching",
                ],
            ).split("\0"),
        )
    )


def inspect_candidate(
    worktree: Path,
    trusted_base_sha: str,
    subject_sha: str,
    role: str,
    allowed_paths: list[str],
    trusted: dict,
) -> dict:
    findings = []
    observed = _run_git(worktree, ["rev-parse", "HEAD"]).strip()
    if observed != subject_sha:
        findings.append(finding("runner.subject-sha", "HEAD differs from subject"))
    resolve_commit(worktree, subject_sha)
    resolve_commit(worktree, trusted_base_sha)
    ancestor = (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", trusted_base_sha, subject_sha],
            cwd=worktree,
        ).returncode
        == 0
    )
    if not ancestor:
        findings.append(
            finding("runner.ancestry", "candidate is not descended from trusted base")
        )
    changed = list(
        filter(
            None,
            _run_git(
                worktree,
                [
                    "diff",
                    "--name-only",
                    "-z",
                    "--no-renames",
                    trusted_base_sha,
                    subject_sha,
                    "--",
                ],
            ).split("\0"),
        )
    )
    status = _status(worktree)
    if status:
        findings.append(
            finding(
                "runner.dirty-tree",
                "candidate has staged, unstaged, untracked, or ignored changes",
            )
        )
    if role != "implementation" and observed != trusted.get("subject_sha", subject_sha):
        findings.append(finding("runner.reviewer-commit", "reviewer changed HEAD"))
    if role == "implementation" and (subject_sha == trusted_base_sha or not changed):
        findings.append(
            finding(
                "runner.no-implementation", "builder must produce a nonempty commit"
            )
        )
    protected = list(trusted.get("policy", {}).get("protected_paths", [])) + [
        ".autodata-agent-registry.json",
        "scripts/autonomy/agent-output.schema.json",
        "scripts/autonomy/runner.py",
        "scripts/autonomy/orchestrator.py",
        trusted.get("task", {}).get("task_ref", ""),
    ]
    protected += list(trusted.get("artifacts", {}))
    protected += [
        a.get("prompt", "") for a in trusted.get("registry", {}).get("agents", [])
    ]
    for path in document_scope_violations(changed, trusted.get("policy", {})):
        findings.append(
            finding(
                "runner.documentation-scope",
                "changed document outside canonical docs tree",
                path,
            )
        )
    for path in changed:
        if role == "implementation" and not path_is_allowed(path, allowed_paths):
            findings.append(
                finding("runner.path-scope", "changed path outside allowed scope", path)
            )
        if any(
            p
            and (
                path == p.rstrip("/")
                or path.startswith(p.rstrip("/") + "/")
                or path_is_allowed(path, [p])
            )
            for p in protected
        ):
            findings.append(
                finding(
                    "runner.protected-path",
                    "normal task changed trust-bearing/protected input",
                    path,
                )
            )
    return {
        "subject_sha": observed,
        "changed_paths": sorted(changed),
        "status_entries": status,
        "findings": findings,
    }


def _directory_fd(path: Path) -> int:
    """Walk directories by descriptor so symlink substitution cannot escape containment."""
    absolute = path.absolute()
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in absolute.parts[1:]:
            if part in ("..", "."):
                raise RunnerError("unsafe directory component")
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as error:
        os.close(descriptor)
        raise RunnerError("unsafe artifact directory") from error
    except BaseException:
        os.close(descriptor)
        raise


def _regular_bytes(root: Path, relative_path: str, limit: int = MAX_ARTIFACT) -> bytes:
    if not safe_ref(relative_path):
        raise RunnerError("unsafe artifact path")
    directory = _directory_fd(root)
    descriptor = None
    try:
        parts = relative_path.split("/")
        for part in parts[:-1]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            os.close(directory)
            directory = child
        info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise RunnerError("artifact must be bounded regular file with one link")
        descriptor = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
        actual = os.fstat(descriptor)
        if (actual.st_dev, actual.st_ino, actual.st_size, actual.st_nlink) != (
            info.st_dev,
            info.st_ino,
            info.st_size,
            1,
        ):
            raise RunnerError("artifact changed during open")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        after = os.fstat(descriptor)
        if len(data) > limit or (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) != (actual.st_size, actual.st_mtime_ns, actual.st_ctime_ns):
            raise RunnerError("artifact changed during read")
        return data
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def _save_artifact(
    data: bytes,
    destination_root: Path,
    artifact_id: str,
    kind: str,
    subject_sha: str,
    check_id: str | None,
) -> dict:
    if (
        not ID_RE.fullmatch(artifact_id)
        or kind not in KINDS
        or not SHA_RE.fullmatch(subject_sha)
    ):
        raise RunnerError("invalid artifact identity")
    if len(data) > MAX_ARTIFACT:
        raise RunnerError("artifact exceeds size budget")
    text = data.decode("utf-8", errors="replace")
    if kind not in ("stdout", "stderr") and redact_text(text) != text:
        raise RunnerError("structured artifact withheld: credential pattern")
    target = destination_root / "evidence"
    target.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or destination_root.is_symlink():
        raise RunnerError("unsafe destination root")
    path = target / f"{artifact_id}.bin"
    directory = _directory_fd(target)
    try:
        descriptor = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
    finally:
        os.close(directory)
    retained = _regular_bytes(destination_root, str(path.relative_to(destination_root)))
    return {
        "artifact_id": artifact_id,
        "kind": kind,
        "ref": str(path.relative_to(destination_root)),
        "sha256": hashlib.sha256(retained).hexdigest(),
        "size_bytes": len(retained),
        "subject_sha": subject_sha,
        "check_id": check_id,
    }


def retain_artifact(
    staging_root: Path,
    relative_path: str,
    destination_root: Path,
    artifact_id: str,
    kind: str,
    subject_sha: str,
    check_id: str | None,
) -> dict:
    data = _regular_bytes(staging_root, relative_path)
    text = data.decode("utf-8", errors="replace")
    if redact_text(text) != text:
        raise RunnerError("structured artifact withheld: credential pattern")
    return _save_artifact(
        data, destination_root, artifact_id, kind, subject_sha, check_id
    )


def validate_artifact(
    record: object, evidence_root: Path, subject_sha: str | None = None
) -> list[str]:
    errors = _shape(record, "ArtifactRecord")
    if errors:
        return errors
    if (
        type(record["artifact_id"]) is not str
        or not ID_RE.fullmatch(record["artifact_id"])
        or record["kind"] not in KINDS
        or type(record["sha256"]) is not str
        or not HASH_RE.fullmatch(record["sha256"])
        or type(record["subject_sha"]) is not str
        or not SHA_RE.fullmatch(record["subject_sha"])
        or type(record["size_bytes"]) is not int
        or not 0 <= record["size_bytes"] <= MAX_ARTIFACT
        or (
            record["check_id"] is not None
            and (
                type(record["check_id"]) is not str
                or not ID_RE.fullmatch(record["check_id"])
            )
        )
    ):
        return ["invalid artifact record"]
    if subject_sha is not None and record["subject_sha"] != subject_sha:
        errors.append("stale artifact subject")
    try:
        data = _regular_bytes(evidence_root, record["ref"])
        if (
            len(data) != record["size_bytes"]
            or hashlib.sha256(data).hexdigest() != record["sha256"]
        ):
            errors.append("artifact hash/size mismatch")
    except (OSError, RunnerError) as error:
        errors.append(str(error))
    return errors


def bounded_process(
    argv: list[str],
    cwd: Path,
    environment: dict[str, str],
    timeout: int,
    stdin: bytes = b"",
) -> dict:
    started = utc_now()
    outputs = [bytearray(), bytearray()]
    status = "completed"
    code = None
    budget = False
    try:
        with tempfile.TemporaryFile() as source:
            source.write(stdin)
            source.seek(0)
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=environment,
                stdin=source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            selector = selectors.DefaultSelector()
            for i, stream in enumerate((process.stdout, process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, i)
            deadline = time.monotonic() + timeout
            try:
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        status = "timed_out"
                        break
                    for key, _ in selector.select(
                        min(0.1, max(0, deadline - time.monotonic()))
                    ):
                        data = os.read(key.fileobj.fileno(), 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        index = key.data
                        remaining = MAX_LOG - len(outputs[index])
                        outputs[index].extend(data[: max(0, remaining)])
                        if len(data) > remaining:
                            budget = True
                            status = "timed_out"
                            break
                    if budget:
                        break
                if status == "completed":
                    try:
                        code = process.wait(
                            timeout=max(0.001, deadline - time.monotonic())
                        )
                    except subprocess.TimeoutExpired:
                        status = "timed_out"
            finally:
                # Kill the whole session even if the direct child already exited.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                grace = time.monotonic() + 2
                while time.monotonic() < grace:
                    try:
                        os.killpg(process.pid, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.02)
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                selector.close()
                process.stdout.close()
                process.stderr.close()
    except OSError as error:
        status = "unavailable"
        outputs[1].extend(str(error).encode())
    return {
        "started_at": started,
        "finished_at": utc_now(),
        "status": status,
        "exit_code": code,
        "stdout": bytes(outputs[0]),
        "stderr": bytes(outputs[1]),
        "output_budget_exhausted": budget,
    }


def _command_errors(value: object) -> list[str]:
    errors = _shape(value, "CommandRecord")
    if errors:
        return errors
    if type(value["schema_version"]) is not int or value["schema_version"] != 2:
        errors.append("invalid command schema_version")
    if (
        not _strings(value["argv"], True)
        or not Path(value["executable"]).is_absolute()
        or not safe_ref(value["cwd"], True)
    ):
        errors.append("invalid command argv/cwd")
    for key in ("check_id", "stdout_id", "stderr_id"):
        if type(value[key]) is not str or not ID_RE.fullmatch(value[key]):
            errors.append("invalid command ID")
    if not _ids(value["output_ids"]):
        errors.append("invalid command output IDs")
    if type(value["subject_sha"]) is not str or not SHA_RE.fullmatch(
        value["subject_sha"]
    ):
        errors.append("invalid command subject")
    for key in ("started_at", "finished_at"):
        try:
            parsed = datetime.fromisoformat(value[key].replace("Z", "+00:00"))
            if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            errors.append("invalid command timestamp")
    if value["status"] not in ENUMS["status"]:
        errors.append("invalid command status")
    if value["status"] == "completed":
        if type(value["exit_code"]) is not int:
            errors.append("completed command needs integer exit")
    elif value["exit_code"] is not None:
        errors.append("incomplete command exit must be null")
    return errors


def execute_required_checks(
    worktree: Path,
    subject_sha: str,
    checks: list[dict],
    output_root: Path,
    environment: dict[str, str],
) -> tuple[list, list, list]:
    commands = []
    artifacts = []
    findings = []
    output_root.mkdir(parents=True, exist_ok=True)
    for check in checks:
        cid = check["check_id"]
        stage = output_root / "staging" / cid
        stage.mkdir(parents=True, exist_ok=False)
        unsafe_argv = any(
            redact_text(argument) != argument for argument in check["argv"]
        )
        executable = (
            None
            if unsafe_argv
            else shutil.which(check["argv"][0], path=environment.get("PATH"))
        )
        if unsafe_argv:
            findings.append(
                finding(
                    f"runner.{cid}.credential",
                    "command containing credential pattern was withheld and not executed",
                )
            )
        if check["argv"][0] not in ("python3", "go", "node"):
            raise RunnerError("executable not permitted")
        cwd = worktree / check["cwd"]
        if (
            not safe_ref(check["cwd"], True)
            or not cwd.resolve().is_relative_to(worktree.resolve())
            or cwd.is_symlink()
        ):
            raise RunnerError("unsafe check cwd")
        env = {
            **environment,
            "AUTODATA_EVIDENCE_ROOT": str(stage.resolve()),
            "AUTODATA_SUBJECT_SHA": subject_sha,
            "AUTODATA_CHECK_ID": cid,
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        argv = [
            str(Path(executable).resolve()) if executable else check["argv"][0],
            *(redact_text(arg) for arg in check["argv"][1:]),
        ]
        process = (
            bounded_process(argv, cwd, env, check["timeout_seconds"])
            if executable
            else {
                "started_at": utc_now(),
                "finished_at": utc_now(),
                "status": "unavailable",
                "exit_code": None,
                "stdout": b"",
                "stderr": b"executable unavailable",
                "output_budget_exhausted": False,
            }
        )
        log_ids = []
        for name in ("stdout", "stderr"):
            aid = f"{cid}:{name}"
            log_ids.append(aid)
            data = redact_text(process[name].decode("utf-8", errors="replace")).encode()
            artifacts.append(
                _save_artifact(data, output_root, aid, name, subject_sha, cid)
            )
        output_ids = []
        total = sum(len(process[n]) for n in ("stdout", "stderr"))
        declared = {o["relative_path"] for o in check["outputs"]}
        allowed_directories = {
            str(parent)
            for ref in declared
            for parent in PurePosixPath(ref).parents
            if str(parent) != "."
        }
        present = {
            str(path.relative_to(stage))
            for path in stage.rglob("*")
            if not path.is_dir()
            or path.is_symlink()
            or str(path.relative_to(stage)) not in allowed_directories
        }
        if present - declared:
            findings.append(
                finding(
                    f"runner.{cid}.undeclared-output",
                    "check created undeclared outputs",
                )
            )
        for output in check["outputs"]:
            try:
                data = _regular_bytes(stage, output["relative_path"])
                total += len(data)
                if total > MAX_CHECK:
                    raise RunnerError("check artifact budget exceeded")
                if output["format"] == "json":
                    parsed = json.loads(data)
                    if output["kind"] == "provenance-result":
                        errors = validate_provenance_record(parsed)
                        if errors:
                            raise RunnerError("; ".join(errors))
                elif output["format"] == "text":
                    data.decode("utf-8")
                else:
                    raise RunnerError("unknown output format")
                artifacts.append(
                    retain_artifact(
                        stage,
                        output["relative_path"],
                        output_root,
                        output["artifact_id"],
                        output["kind"],
                        subject_sha,
                        cid,
                    )
                )
                output_ids.append(output["artifact_id"])
            except (OSError, ValueError, RunnerError) as error:
                findings.append(
                    finding(f"runner.{cid}.output", redact_text(str(error)))
                )
        record = {
            "schema_version": 2,
            "check_id": cid,
            "subject_sha": subject_sha,
            "argv": argv,
            "executable": (
                str(Path(executable).resolve())
                if executable
                else "/unavailable/" + check["argv"][0]
            ),
            "cwd": check["cwd"],
            "started_at": process["started_at"],
            "finished_at": process["finished_at"],
            "status": process["status"],
            "exit_code": process["exit_code"],
            "stdout_id": log_ids[0],
            "stderr_id": log_ids[1],
            "output_ids": output_ids,
        }
        commands.append(record)
        artifacts.append(
            _save_artifact(
                (json.dumps(record, sort_keys=True) + "\n").encode(),
                output_root,
                f"{cid}:command",
                "command-result",
                subject_sha,
                cid,
            )
        )
        if (
            process["status"] != "completed"
            or process["exit_code"] != 0
            or process["output_budget_exhausted"]
        ):
            findings.append(
                finding(
                    f"runner.{cid}.execution",
                    f"check {process['status']}, exit={process['exit_code']}, output_budget={process['output_budget_exhausted']}",
                )
            )
        # A staging directory may contain secret-bearing data; it is never part of the bundle.
        try:
            shutil.rmtree(stage)
        except OSError:
            findings.append(
                finding(
                    "runner.cleanup",
                    "check staging cleanup failed; evidence records retained",
                )
            )
    if (worktree / ".git").exists() and _status(worktree):
        findings.append(
            finding("runner.check-dirty-tree", "required check modified candidate")
        )
    return commands, artifacts, findings


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def pointer(value: object, path: str) -> object:
    if type(path) is not str or not path.startswith("/"):
        raise ValueError("invalid JSON pointer")
    for part in path[1:].split("/"):
        if re.search(r"~(?![01])", part):
            raise ValueError("invalid pointer escape")
        key = part.replace("~1", "/").replace("~0", "~")
        if type(value) is list:
            if not re.fullmatch(r"0|[1-9][0-9]*", key):
                raise ValueError("invalid array pointer")
            value = value[int(key)]
        elif type(value) is dict:
            value = value[key]
        else:
            raise ValueError("pointer into scalar")
    return value


def validate_provenance_record(value: object) -> list[str]:
    errors = _shape(value, "ProvenanceResult")
    if errors:
        return errors
    if type(value["schema_version"]) is not int or value["schema_version"] != 2:
        errors.append("invalid provenance schema_version")
    for key, pattern in (
        ("subject_sha", SHA_RE),
        ("population_sha256", HASH_RE),
        ("population_id", ID_RE),
    ):
        if type(value[key]) is not str or not pattern.fullmatch(value[key]):
            errors.append("invalid provenance " + key)
    if (
        value["scope"] != "synthetic-regression"
        or not _ids(value["eligible_ids"])
        or not _ids(value["covered_ids"])
    ):
        errors.append("invalid provenance scope/IDs")
    for key, name in (("records", "FactProof"), ("uncovered", "Uncovered")):
        if type(value[key]) is not list:
            errors.append("invalid provenance " + key)
            continue
        seen = set()
        for record in value[key]:
            e = _shape(record, name)
            errors += e
            if e:
                continue
            fid = record["fact_id"]
            if type(fid) is not str or not ID_RE.fullmatch(fid) or fid in seen:
                errors.append("invalid/duplicate provenance fact ID")
            else:
                seen.add(fid)
            for field, item in record.items():
                if field.endswith("_sha256") and (
                    type(item) is not str or not HASH_RE.fullmatch(item)
                ):
                    errors.append("invalid proof hash")
                elif field.endswith("_pointer") and (
                    type(item) is not str or not item.startswith("/")
                ):
                    errors.append("invalid proof pointer")
                elif field == "reason" and (type(item) is not str or not item):
                    errors.append("missing uncovered reason")
    return errors


def measure_provenance(
    population: dict, retained_inputs: dict, report: dict, subject_sha: str
) -> dict:
    findings = []
    eligible = []
    covered = []

    def bad(message):
        findings.append(finding("runner.provenance", message, category="provenance"))

    if (
        type(population) is not dict
        or set(population) != {"population_id", "scope", "records"}
        or population.get("scope") != "synthetic-regression"
        or type(population.get("records")) is not list
    ):
        bad("invalid trusted population")
        population = {
            "population_id": "invalid",
            "scope": "synthetic-regression",
            "records": [],
        }
    definitions = {}
    for rec in population["records"]:
        if (
            type(rec) is not dict
            or set(rec)
            != {
                "fact_id",
                "source_ref",
                "source_pointer",
                "extraction_ref",
                "extraction_pointer",
            }
            or type(rec.get("fact_id")) is not str
            or not ID_RE.fullmatch(rec["fact_id"])
            or rec["fact_id"] in definitions
        ):
            bad("invalid/duplicate population record")
            continue
        definitions[rec["fact_id"]] = rec
    eligible = sorted(definitions)
    errors = validate_provenance_record(report)
    if errors:
        bad("; ".join(errors))
        report = {}
    if (
        type(report.get("schema_version")) is not int
        or report.get("schema_version") != 2
        or report.get("subject_sha") != subject_sha
        or report.get("scope") != "synthetic-regression"
        or report.get("population_id") != population["population_id"]
        or report.get("population_sha256")
        != hashlib.sha256(canonical(population)).hexdigest()
    ):
        bad("provenance identity/hash mismatch")
    for key in ("eligible_ids", "covered_ids"):
        if not _ids(report.get(key)):
            bad("invalid/duplicate " + key)
    if report.get("eligible_ids") != eligible:
        bad("eligible IDs differ from trusted population")
    proofs = report.get("records", [])
    seen = set()
    if type(proofs) is not list:
        bad("invalid proofs")
        proofs = []
    for proof in proofs:
        e = _shape(proof, "FactProof")
        if e:
            bad("invalid proof shape")
            continue
        fid = proof["fact_id"]
        if type(fid) is not str or fid not in definitions or fid in seen:
            bad("foreign/duplicate proof")
            continue
        seen.add(fid)
        rec = definitions[fid]
        try:
            source = retained_inputs[rec["source_ref"]]
            extraction = retained_inputs[rec["extraction_ref"]]
            if not isinstance(source, bytes) or not isinstance(extraction, bytes):
                raise ValueError("inputs must retain raw bytes")
            left = pointer(json.loads(source), rec["source_pointer"])
            right = pointer(json.loads(extraction), rec["extraction_pointer"])
            if canonical(left) != canonical(right):
                raise ValueError("source/extraction values differ")
            expected = {
                "fact_id": fid,
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "extraction_sha256": hashlib.sha256(extraction).hexdigest(),
                "source_pointer": rec["source_pointer"],
                "extraction_pointer": rec["extraction_pointer"],
                "value_sha256": hashlib.sha256(canonical(left)).hexdigest(),
            }
            if proof != expected:
                raise ValueError("proof hash/pointer mismatch")
            covered.append(fid)
        except (KeyError, IndexError, ValueError, TypeError):
            bad(f"invalid proof for {fid}")
    covered = sorted(covered)
    uncovered = sorted(set(eligible) - set(covered))
    if report.get("covered_ids") != covered:
        bad("claimed coverage differs from replay")
    u = report.get("uncovered", [])
    if type(u) is not list:
        bad("invalid uncovered records")
        u = []
    if (
        any(
            _shape(x, "Uncovered")
            or type(x.get("reason")) is not str
            or not x["reason"]
            for x in u
        )
        or sorted(x.get("fact_id", "") for x in u if type(x) is dict) != uncovered
    ):
        bad("uncovered IDs/reasons differ")
    if not eligible:
        bad("empty eligible population")
    return {
        "scope": "synthetic-regression",
        "population_id": population["population_id"],
        "population_sha256": hashlib.sha256(canonical(population)).hexdigest(),
        "eligible_ids": eligible,
        "covered_ids": covered,
        "uncovered_ids": uncovered,
        "eligible_count": len(eligible),
        "covered_count": len(covered),
        "ratio": len(covered) / len(eligible) if eligible else None,
        "findings": findings,
    }


def trusted_artifact_id(path: str) -> str:
    return "trusted:" + hashlib.sha256(path.encode()).hexdigest()[:24]


def retain_trusted_inputs(trusted: dict, output_root: Path) -> list[dict]:
    return [
        _save_artifact(
            data,
            output_root,
            trusted_artifact_id(path),
            "trusted-input",
            trusted["trusted_base_sha"],
            None,
        )
        for path, data in sorted(trusted["artifacts"].items())
    ]


def _runtime_metadata(stdout: str) -> dict:
    # Only structured CLI runtime events count; response prose is never metadata.
    observed = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if type(event) is dict and event.get("type") == "session_config":
            for key in ("model", "reasoning_effort", "service_tier"):
                if type(event.get(key)) is str:
                    value = redact_text(event[key])
                    previous = observed.get(key)
                    equivalent = (
                        {previous, value} <= {"fast", "priority"}
                        if type(previous) is str
                        else False
                    )
                    if previous is not None and previous != value and not equivalent:
                        observed["conflicting_runtime_metadata"] = True
                    observed[key] = value
            features = event.get("features")
            if (
                type(features) is dict
                and "fast_mode" in features
                and features["fast_mode"] is not True
            ):
                observed["conflicting_runtime_metadata"] = True
    return observed


def run_agent(
    repo_root: Path,
    envelope: dict,
    provider: str,
    output_root: Path,
    timeout_seconds: int = 1800,
    *,
    trusted: dict | None = None,
) -> tuple[int, Path]:
    if trusted is None:
        if _status(repo_root):
            raise RunnerError("coordinator checkout must be clean")
        base = _run_git(repo_root, ["rev-parse", "HEAD"]).strip()
        trusted = load_trusted_inputs(repo_root, base, envelope.get("task_ref"))
    task = trusted["task"]
    base = trusted["trusted_base_sha"]
    subject = envelope.get("subject_sha", envelope.get("base_sha"))
    resolve_commit(repo_root, subject)
    errors = validate_execution_profile(envelope.get("execution"))
    agent = _registry_agent(trusted["registry"], envelope.get("agent_name"))
    if agent is None:
        errors.append("unregistered agent")
    if envelope.get("task_id") != task["task_id"]:
        errors.append("task identity differs")
    if not ID_RE.fullmatch(str(envelope.get("run_id", ""))):
        errors.append("invalid run_id")
    if envelope.get("task_contract") != {k: task[k] for k in CONTRACT_FIELDS}:
        errors.append("task_contract differs from frozen task")
    if envelope.get("execution") != task["execution"]:
        errors.append("execution differs from trusted task")
    role = agent.get("role") if agent else None
    if role == "implementation" and (
        envelope.get("agent_name") != task["builder_agent"]
        or envelope.get("allowed_paths") != task["allowed_paths"]
    ):
        errors.append("builder authorization differs")
    if envelope.get("deployment_target") != "none":
        errors.append("no deployment authority")
    if role == "implementation":
        errors += validate_record(
            task.get("pre_implementation"), repo_root, base, trusted["policy"]
        )
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 1800:
        errors.append("invalid provider timeout")
    if output_root.resolve().is_relative_to(repo_root.resolve()):
        errors.append("evidence output must be outside checkout")
    if errors:
        raise RunnerError("; ".join(errors))
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, subject], cwd=repo_root
    ).returncode:
        raise RunnerError("subject is not descended from trusted base")
    output_root.mkdir(parents=True, exist_ok=False)
    schema_file = output_root / "agent-output.schema.json"
    schema_file.write_bytes(
        trusted["artifacts"]["scripts/autonomy/agent-output.schema.json"]
    )
    _write_json(output_root / "task-envelope.json", envelope)
    worktree = output_root / "worktree"
    _run_git(repo_root, ["worktree", "add", "--detach", str(worktree), subject])
    artifacts = []
    commands = []
    findings = []
    response = None
    observed = subject
    changed = []
    runtime = {}
    provider_command = None
    label = envelope.get("evidence_label", envelope["agent_name"])
    response_id = envelope.get("response_artifact_id", label + ":response")
    staging = output_root / "provider-staging"
    staging.mkdir()
    guard = output_root / "guard-bin"
    _make_guard_bin(guard)
    config = output_root / "isolated-gh-config"
    config.mkdir()
    environment = _safe_environment(guard, config)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = build_provider_command(
        provider,
        worktree,
        staging / "provider-output.json",
        schema_file,
        execution=envelope["execution"],
    )
    try:
        if _status(worktree):
            raise RunnerError("isolated worktree is initially dirty")
        assigned = [
            c
            for c in task["verification"]["checks"]
            if c["gate"] == envelope.get("gate")
        ]
        commands, artifacts, command_findings = execute_required_checks(
            worktree, subject, assigned, output_root, environment
        )
        findings.extend(command_findings)
        if _status(worktree):
            findings.append(
                finding("runner.check-dirty-tree", "required check modified candidate")
            )
        available_artifact_ids = [a["artifact_id"] for a in artifacts]
        prompt = trusted["prompts"][envelope["agent_name"]]
        prompt += "\nFROZEN ENVELOPE:\n" + json.dumps(envelope, sort_keys=True)
        prompt += "\nRUNNER COMMAND RECORDS:\n" + json.dumps(commands, sort_keys=True)
        prompt += "\nAVAILABLE ARTIFACT IDS:\n" + json.dumps(
            [a["artifact_id"] for a in artifacts]
        )
        prompt += "\nBOUNDED LOG EXCERPTS:\n"
        for a in artifacts:
            if a["kind"] in ("stdout", "stderr"):
                prompt += (
                    a["artifact_id"]
                    + ": "
                    + _regular_bytes(output_root, a["ref"]).decode(
                        "utf-8", errors="replace"
                    )[:8192]
                    + "\n"
                )
        prompt += "\nUse only this worktree. Do not contact GitHub/deploy. Do not print credentials. Builders must commit locally. Reviewers must never modify files or HEAD. Return strict v2 JSON; reference only supplied evidence IDs.\n"
        process = bounded_process(
            command, worktree, environment, timeout_seconds, prompt.encode()
        )
        observed = _run_git(worktree, ["rev-parse", "HEAD"]).strip()
        runtime = _runtime_metadata(process["stdout"].decode("utf-8", errors="replace"))
        for name in ("stdout", "stderr"):
            artifacts.append(
                _save_artifact(
                    redact_text(
                        process[name].decode("utf-8", errors="replace")
                    ).encode(),
                    output_root,
                    label + ":" + name,
                    name,
                    observed,
                    None,
                )
            )
        if (
            process["status"] != "completed"
            or process["exit_code"] != 0
            or process["output_budget_exhausted"]
        ):
            findings.append(
                finding(
                    "runner.provider-exit",
                    f"provider {process['status']}, exit={process['exit_code']}",
                )
            )
        # Effective model/tier support requires independent runtime metadata, not provider prose.
        expected_runtime = {
            "model": "gpt-6.1-sol",
            "reasoning_effort": "medium",
            "service_tier": "fast",
        }
        normalized = {**runtime}
        if normalized.get("service_tier") == "priority":
            normalized["service_tier"] = "fast"
        if normalized != expected_runtime:
            findings.append(
                finding(
                    "runner.runtime-profile",
                    "requested execution profile not established by CLI runtime metadata",
                )
            )
        observed = _run_git(worktree, ["rev-parse", "HEAD"]).strip()
        candidate = inspect_candidate(
            worktree,
            base,
            observed,
            role,
            task["allowed_paths"],
            {**trusted, "subject_sha": subject},
        )
        findings.extend(candidate["findings"])
        changed = candidate["changed_paths"]
        if role != "implementation" and observed != subject:
            findings.append(
                finding("runner.reviewer-commit", "read-only agent changed HEAD")
            )
        try:
            raw = _regular_bytes(staging, "provider-output.json")
            if redact_text(raw.decode("utf-8")) != raw.decode("utf-8"):
                raise RunnerError("provider response contains credential pattern")
            response = json.loads(raw)
            artifacts.append(
                retain_artifact(
                    staging,
                    "provider-output.json",
                    output_root,
                    response_id,
                    "provider-response",
                    observed,
                    None,
                )
            )
            expected = {
                "run_id": envelope["run_id"],
                "task_id": task["task_id"],
                "agent_name": envelope["agent_name"],
                "subject_sha": observed if role == "implementation" else subject,
                "role": (
                    "architecture"
                    if envelope["agent_name"] == "autodata-architect"
                    else role
                ),
                "check_ids": [c["check_id"] for c in assigned],
                "artifact_ids": available_artifact_ids,
                "task_contract": {k: task[k] for k in CONTRACT_FIELDS},
            }
            response_errors = validate_agent_response(
                response, trusted["schema"], expected
            )
            if response_errors:
                raise RunnerError("; ".join(response_errors))
            findings.extend(response["findings"])
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RunnerError,
        ) as error:
            findings.append(
                finding("runner.malformed-agent-response", redact_text(str(error)))
            )
            response = None
        provider_command = {
            "schema_version": 2,
            "check_id": label + ":provider",
            "subject_sha": observed,
            "argv": command,
            "executable": shutil.which(command[0], path=environment.get("PATH"))
            or "/unavailable/codex",
            "cwd": ".",
            "started_at": process["started_at"],
            "finished_at": process["finished_at"],
            "status": process["status"],
            "exit_code": process["exit_code"],
            "stdout_id": label + ":stdout",
            "stderr_id": label + ":stderr",
            "output_ids": (
                [response_id]
                if any(a["artifact_id"] == response_id for a in artifacts)
                else []
            ),
        }
        artifacts.append(
            _save_artifact(
                canonical(provider_command),
                output_root,
                label + ":invocation",
                "command-result",
                observed,
                None,
            )
        )
        if role == "implementation":
            changes = {
                "trusted_base_sha": base,
                "subject_sha": observed,
                "changed_paths": changed,
                "status_entries": candidate["status_entries"],
            }
            artifacts.append(
                _save_artifact(
                    canonical(changes),
                    output_root,
                    "candidate:changes",
                    "change-set",
                    observed,
                    None,
                )
            )
            if observed != subject:
                _run_git(
                    repo_root,
                    [
                        "update-ref",
                        f"refs/autodata/runs/{envelope['run_id']}",
                        observed,
                    ],
                )
    except (OSError, RunnerError, ValueError) as error:
        findings.append(finding("runner.integrity", redact_text(str(error))))
    finally:
        try:
            _run_git(repo_root, ["worktree", "remove", "--force", str(worktree)])
        except RunnerError as error:
            findings.append(finding("runner.cleanup", redact_text(str(error))))
        try:
            shutil.rmtree(staging)
        except OSError:
            findings.append(
                finding("runner.cleanup", "provider staging cleanup failed")
            )
    integrity = any(
        f["finding_id"].startswith(
            (
                "runner.integrity",
                "runner.malformed",
                "runner.runtime",
                "runner.cleanup",
                "runner.provider",
                "runner.dirty",
                "runner.check-dirty",
                "runner.subject",
                "runner.ancestry",
                "runner.reviewer",
                "runner.protected",
                "runner.path",
                "runner.documentation",
            )
        )
        for f in findings
    )
    decision = response["decision"] if response else "blocked"
    if integrity:
        decision = "blocked"
    elif any(
        f.get("blocking") or f.get("severity") in ("critical", "high") for f in findings
    ):
        decision = "fail"
    manifest = {
        "schema_version": 2,
        "run_id": envelope["run_id"],
        "task_id": task["task_id"],
        "agent": envelope["agent_name"],
        "trusted_base_sha": base,
        "base_sha": base,
        "implementation_sha": observed,
        "subject_sha": observed,
        "changed_paths": changed,
        "agent_decision": decision,
        "decision": decision,
        "findings": findings,
        "commands_run": commands,
        "artifacts": artifacts,
        "response": response,
        "execution": task["execution"],
        "provider_argv": command,
        "provider_command": provider_command,
        "observed_execution": runtime,
        "provider_runtime_validation": (
            "passed"
            if not any(f["finding_id"] == "runner.runtime-profile" for f in findings)
            else "blocked"
        ),
    }
    manifest_path = output_root / "run-manifest.json"
    _write_json(manifest_path, manifest)
    # One agent cannot independently satisfy the full eight-gate bundle.
    return 20, manifest_path


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
        root = (
            args.output_root
            or Path(tempfile.gettempdir()) / "autodata-runs" / envelope["run_id"]
        )
        code, path = run_agent(
            args.repo_root.resolve(),
            envelope,
            args.provider,
            root.resolve(),
            args.timeout_seconds,
        )
        print(json.dumps({"exit_code": code, "manifest": str(path)}))
        return code
    except (OSError, ValueError, RunnerError, KeyError) as error:
        print(json.dumps({"exit_code": 30, "error": redact_text(str(error))}))
        return 30


if __name__ == "__main__":
    sys.exit(main())
