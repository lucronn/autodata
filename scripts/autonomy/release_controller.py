#!/usr/bin/env python3
"""Validate and optionally execute the AutoData GitHub release transition."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .validate_run import evaluate
except ImportError:  # Support direct execution: python scripts/autonomy/release_controller.py
    from validate_run import evaluate


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_release_inputs(
    manifest: dict[str, Any],
    policy: dict[str, Any],
    registry: dict[str, Any],
    current_head_sha: str,
) -> list[str]:
    """Validate release-only invariants before any GitHub command is called."""

    failures: list[str] = []
    implementation_sha = manifest.get("implementation_sha")
    if not isinstance(implementation_sha, str) or not SHA_RE.fullmatch(implementation_sha):
        failures.append("implementation_sha must be a 40-character lowercase SHA")
    elif implementation_sha != current_head_sha:
        failures.append("implementation SHA does not match checked-out HEAD")
    if manifest.get("decision") != "pass":
        failures.append(f"run decision is not pass: {manifest.get('decision')}")

    repository = manifest.get("repository")
    if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
        failures.append("repository must be OWNER/REPO")

    target = manifest.get("deployment_target", "none")
    autonomy = policy.get("autonomy", {})
    if target == "production" and autonomy.get("production_deployment") is not True:
        failures.append("production deployment is disabled by policy")
    if target not in {"none", *autonomy.get("allowed_deployment_targets", [])}:
        failures.append(f"deployment target is not allowed by policy: {target}")

    release_agents = [
        agent
        for agent in registry.get("agents", [])
        if isinstance(agent, dict) and agent.get("can_merge") is True
    ]
    if len(release_agents) != 1 or release_agents[0].get("name") != "autodata-release-agent":
        failures.append("registry must designate exactly autodata-release-agent as merge authority")
    return failures


def build_release_plan(
    manifest: dict[str, Any],
    head_branch: str,
    project_number: int | None = None,
    pr_number: int | None = None,
    project_item_id: str | None = None,
    status_field_id: str | None = None,
    status_option_id: str | None = None,
    body_file: str = "<release-evidence-body>",
) -> dict[str, Any]:
    """Build auditable gh commands without executing them."""

    repository = manifest["repository"]
    implementation_sha = manifest["implementation_sha"]
    task_id = manifest["task_id"]
    if not BRANCH_RE.fullmatch(head_branch):
        raise ValueError("head_branch contains unsupported characters")
    if not ID_RE.fullmatch(str(task_id)):
        raise ValueError("task_id contains unsupported characters for a release title")
    argv_commands: list[list[str]] = []
    if pr_number is None:
        argv_commands.append(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                repository,
                "--base",
                "main",
                "--head",
                head_branch,
                "--title",
                f"AutoData: {task_id}",
                "--body-file",
                body_file,
            ]
        )
    if pr_number is not None:
        argv_commands.append(
            [
                "gh",
                "pr",
                "merge",
                str(pr_number),
                "--repo",
                repository,
                "--squash",
                "--match-head-commit",
                implementation_sha,
            ]
        )
        if project_number is not None:
            argv_commands.append(
                [
                    "gh",
                    "project",
                    "item-add",
                    str(project_number),
                    "--owner",
                    repository.split("/", 1)[0],
                    "--url",
                    f"https://github.com/{repository}/pull/{pr_number}",
                ]
            )
            if project_item_id and status_field_id and status_option_id:
                argv_commands.append(
                    [
                        "gh",
                        "project",
                        "item-edit",
                        "--id",
                        project_item_id,
                        "--project-number",
                        str(project_number),
                        "--field-id",
                        status_field_id,
                        "--single-select-option-id",
                        status_option_id,
                    ]
                )
    return {
        "repository": repository,
        "head_branch": head_branch,
        "implementation_sha": implementation_sha,
        "commands": [shlex.join(command) for command in argv_commands],
        "argv": argv_commands,
        "deployment_target": manifest.get("deployment_target", "none"),
    }


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
        raise RuntimeError(result.stderr.strip() or "cannot determine HEAD")
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--head-branch", required=True)
    parser.add_argument("--project-number", type=int)
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--project-item-id")
    parser.add_argument("--status-field-id")
    parser.add_argument("--status-option-id")
    parser.add_argument("--execute", action="store_true", help="execute gh mutations after validation")
    args = parser.parse_args(argv)

    try:
        manifest = _load_json(args.manifest)
        policy = _load_json(args.repo_root / ".autodata-autonomy-policy.json")
        registry = _load_json(args.repo_root / ".autodata-agent-registry.json")
        validation = evaluate(manifest, policy, evidence_root=args.evidence_root)
        failures = list(validation["failures"])
        failures.extend(validate_release_inputs(manifest, policy, registry, _head_sha(args.repo_root)))
        plan = build_release_plan(
            manifest,
            args.head_branch,
            args.project_number,
            args.pr_number,
            args.project_item_id,
            args.status_field_id,
            args.status_option_id,
            str(args.evidence_root / "release-evidence-body.md"),
        )
        if failures:
            print(json.dumps({"decision": "blocked", "failures": failures, "plan": plan}, sort_keys=True))
            return 20
        if not args.execute:
            print(json.dumps({"decision": "validated", "plan": plan}, sort_keys=True))
            return 0
        if os.environ.get("AUTODATA_RELEASE_AUTOMATION") != "enabled":
            print(
                json.dumps(
                    {
                        "decision": "blocked",
                        "failures": ["set AUTODATA_RELEASE_AUTOMATION=enabled in the isolated release job"],
                        "plan": plan,
                    },
                    sort_keys=True,
                )
            )
            return 20
        if args.pr_number is None:
            print(
                json.dumps(
                    {
                        "decision": "blocked",
                        "failures": ["--execute requires --pr-number after PR discovery"],
                        "plan": plan,
                    },
                    sort_keys=True,
                )
            )
            return 20
        results = []
        for argv in plan["argv"]:
            # The release job supplies a controlled argv through its wrapper; this
            # controller never interpolates secrets and always pins merge by SHA.
            result = subprocess.run(argv, text=True, capture_output=True, check=False)
            results.append({"command": shlex.join(argv), "exit_code": result.returncode})
            if result.returncode != 0:
                return_code = 20
                print(json.dumps({"decision": "blocked", "results": results}, sort_keys=True))
                return return_code
        print(json.dumps({"decision": "executed", "results": results}, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(json.dumps({"decision": "blocked", "failures": [str(error)]}, sort_keys=True))
        return 30


if __name__ == "__main__":
    sys.exit(main())
