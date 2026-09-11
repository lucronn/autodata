"""Validate the planning and tracking record required before implementation."""

from __future__ import annotations

import fnmatch
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any


ISSUE_URL_RE = re.compile(r"^https://github\.com/[^/]+/[^/]+/issues/[1-9][0-9]*$")
PROJECT_URL_RE = re.compile(
    r"^https://github\.com/(?:users|orgs)/[^/]+/projects/[1-9][0-9]*$"
)


def _matches_path(path: str, patterns: Any) -> bool:
    if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
        return False
    normalized = PurePosixPath(path)
    return any(
        fnmatch.fnmatchcase(path, pattern) or normalized.match(pattern) for pattern in patterns
    )


def _safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def _read_at_base(repo_root: Path, base_sha: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{base_sha}:{path}"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.utcoffset() == timedelta(0)


def validate_record(
    record: Any,
    repo_root: Path,
    base_sha: str,
    policy: dict[str, Any],
) -> list[str]:
    """Return deterministic blocking errors for one pre-implementation record."""

    errors: list[str] = []
    configuration = policy.get("pre_implementation")
    if not isinstance(configuration, dict) or configuration.get("required") is not True:
        return ["pre_implementation policy is missing or not required"]
    if not isinstance(record, dict):
        return ["pre_implementation record is required"]

    required_fields = configuration.get("required_fields", [])
    if not isinstance(required_fields, list):
        return ["pre_implementation.required_fields policy must be a list"]
    for field in required_fields:
        if not isinstance(field, str) or not field:
            errors.append("pre_implementation.required_fields policy contains an invalid field")
        elif field not in record:
            errors.append(f"pre_implementation.{field} is required")

    goal = record.get("goal")
    if "goal" in record and (not isinstance(goal, str) or not goal.strip()):
        errors.append("pre_implementation.goal must be a non-empty string")

    issue_ref = record.get("issue_ref")
    if "issue_ref" in record and (
        not isinstance(issue_ref, str) or not ISSUE_URL_RE.fullmatch(issue_ref)
    ):
        errors.append("pre_implementation.issue_ref must be a GitHub Issue URL")

    project_ref = record.get("project_ref")
    if "project_ref" in record and (
        not isinstance(project_ref, str) or not PROJECT_URL_RE.fullmatch(project_ref)
    ):
        errors.append("pre_implementation.project_ref must be a GitHub Project URL")

    todo = record.get("todo")
    if "todo" in record and (
        not isinstance(todo, list)
        or not todo
        or not all(isinstance(item, str) and item.strip() for item in todo)
    ):
        errors.append("pre_implementation.todo must be a non-empty list of strings")

    required_status = configuration.get("required_status", "synchronized")
    if "status" in record and record.get("status") != required_status:
        errors.append(f"pre_implementation.status must equal {required_status}")

    if "updated_at" in record and not _valid_timestamp(record.get("updated_at")):
        errors.append("pre_implementation.updated_at must be an ISO-8601 UTC timestamp")

    plan_ref = record.get("plan_ref")
    plan_patterns = configuration.get("plan_paths", [])
    plan_is_valid = _safe_relative_path(plan_ref) and _matches_path(plan_ref, plan_patterns)
    if "plan_ref" in record and not plan_is_valid:
        errors.append("pre_implementation.plan_ref is outside the configured plan paths")

    plan_text: str | None = None
    if plan_is_valid:
        plan_text = _read_at_base(repo_root, base_sha, plan_ref)
        if plan_text is None:
            errors.append("pre_implementation.plan_ref is absent at base_sha")

    doc_refs = record.get("repository_doc_refs")
    doc_patterns = configuration.get("repository_doc_paths", [])
    if "repository_doc_refs" in record and (
        not isinstance(doc_refs, list)
        or not doc_refs
        or not all(isinstance(item, str) and item.strip() for item in doc_refs)
    ):
        errors.append("pre_implementation.repository_doc_refs must be a non-empty list of strings")
        doc_refs = []

    if isinstance(doc_refs, list):
        for index, doc_ref in enumerate(doc_refs):
            if not _safe_relative_path(doc_ref) or not _matches_path(doc_ref, doc_patterns):
                errors.append(
                    f"pre_implementation.repository_doc_refs[{index}] is outside the configured document paths"
                )
                continue
            if _read_at_base(repo_root, base_sha, doc_ref) is None:
                errors.append(f"pre_implementation.repository_doc_refs[{index}] is absent at base_sha")

    if plan_text is not None:
        if not isinstance(issue_ref, str) or issue_ref not in plan_text:
            errors.append("pre_implementation.plan_ref does not record issue_ref")
        if not isinstance(project_ref, str) or project_ref not in plan_text:
            errors.append("pre_implementation.plan_ref does not record project_ref")
        if not re.search(r"(?im)\bto-do\b|\btodo\b", plan_text):
            errors.append("pre_implementation.plan_ref does not record todo")

    return errors
