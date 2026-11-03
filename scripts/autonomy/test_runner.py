import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


from runner import (
    RunnerError,
    build_provider_command,
    changed_paths,
    document_scope_violations,
    redact_text,
    run_agent,
    _make_guard_bin,
    validate_envelope,
)


class RunnerTests(unittest.TestCase):
    def test_builder_without_pre_implementation_record_is_rejected_before_worktree(
        self,
    ):
        repo_root = Path(__file__).resolve().parents[2]
        base_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        envelope = {
            "run_id": "run-preflight-test",
            "task_id": "issue-86",
            "base_sha": base_sha,
            "agent_name": "autodata-go-builder",
            "allowed_paths": ["apps/api-go/**"],
            "deployment_target": "none",
        }

        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "run"
            with patch("runner._git_show", return_value="builder prompt"), patch(
                "runner._run_git", return_value=base_sha
            ), patch("runner._make_guard_bin", return_value=Path(directory)), patch(
                "runner.build_provider_command", return_value=["false"]
            ) as provider:
                with self.assertRaises(RunnerError):
                    run_agent(
                        repo_root, envelope, "local-cli", output_root, timeout_seconds=1
                    )

            provider.assert_not_called()
            self.assertFalse((output_root / "worktree").exists())

    def test_local_cli_command_is_noninteractive_and_workspace_scoped(self):
        command = build_provider_command(
            provider="local-cli",
            cwd=Path("/tmp/worktree"),
            output_file=Path("/tmp/last.json"),
            schema_file=Path("/tmp/schema.json"),
            execution=PROFILE,
        )

        self.assertEqual(command[:2], ["codex", "exec"])
        self.assertIn("--json", command)
        self.assertIn("--ephemeral", command)
        self.assertIn("--approve-for-me", command)
        self.assertIn("--output-schema", command)
        self.assertEqual(command[-1], "-")

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            build_provider_command(
                provider="unknown",
                cwd=Path("/tmp/worktree"),
                output_file=Path("/tmp/last.json"),
                schema_file=Path("/tmp/schema.json"),
                execution=PROFILE,
            )

    def test_envelope_rejects_production_and_unregistered_agent(self):
        registry = {"agents": [{"name": "autodata-go-builder", "prompt": "agent.md"}]}
        policy = {
            "autonomy": {
                "production_deployment": False,
                "allowed_deployment_targets": ["dev"],
            }
        }

        errors = validate_envelope(
            {
                "run_id": "run-1",
                "task_id": "task-1",
                "base_sha": "a" * 40,
                "agent_name": "unregistered",
                "allowed_paths": ["apps/**"],
                "deployment_target": "production",
            },
            registry,
            policy,
            actual_base_sha="a" * 40,
        )

        self.assertIn("agent_name is not registered: unregistered", errors)
        self.assertIn("production deployment is disabled by policy", errors)

    def test_envelope_rejects_stale_base_and_empty_scope(self):
        registry = {"agents": [{"name": "autodata-go-builder", "prompt": "agent.md"}]}
        policy = {
            "autonomy": {
                "production_deployment": False,
                "allowed_deployment_targets": [],
            }
        }

        errors = validate_envelope(
            {
                "run_id": "run-1",
                "task_id": "task-1",
                "base_sha": "a" * 40,
                "agent_name": "autodata-go-builder",
                "allowed_paths": [],
                "deployment_target": "none",
            },
            registry,
            policy,
            actual_base_sha="b" * 40,
        )

        self.assertIn("base_sha does not match repository HEAD", errors)
        self.assertIn("allowed_paths must be a non-empty list of strings", errors)

    def test_changed_paths_includes_tracked_and_untracked_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            # A fake git executable is used so this unit test remains deterministic.
            git = root / "git"
            git.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = diff ]; then printf 'apps/api/main.go\\0'; fi\n"
                "if [ \"$1\" = ls-files ]; then printf 'docs/new.md\\0'; fi\n",
                encoding="utf-8",
            )
            git.chmod(0o755)
            result = changed_paths(root, "a" * 40, git_executable=str(git))

        self.assertEqual(result, ["apps/api/main.go", "docs/new.md"])

    def test_document_scope_allows_canonical_docs_and_rejects_parallel_docs(self):
        policy = {
            "documentation": {
                "canonical_paths": ["docs/**"],
                "document_extensions": [".md", ".mdx"],
            }
        }

        violations = document_scope_violations(
            ["docs/architecture/contracts.md", "apps/api/README.md", "notes/design.md"],
            policy,
        )

        self.assertEqual(violations, ["apps/api/README.md", "notes/design.md"])

    def test_document_scope_fails_closed_when_policy_configuration_is_invalid(self):
        violations = document_scope_violations(
            ["apps/api/README.md", "apps/api/main.go"],
            {"documentation": {"canonical_paths": "docs/**"}},
        )

        self.assertEqual(violations, ["apps/api/README.md"])

    def test_redacts_common_secret_shapes(self):
        text = "token=sk-abc123 github_pat_abc123 AKIAIOSFODNN7EXAMPLE"

        redacted = redact_text(text)

        self.assertNotIn("sk-abc123", redacted)
        self.assertNotIn("github_pat_abc123", redacted)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", redacted)
        self.assertEqual(redacted.count("[REDACTED_SECRET]"), 3)

    def test_command_guard_blocks_subcommands_after_git_options(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = _make_guard_bin(Path(directory) / "bin")
            result = subprocess.run(
                [str(guard / "git"), "-C", directory, "push"],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 126)
        self.assertIn("blocked by AutoData runner", result.stderr)


# v2 regressions use actual Git/files/processes; provider access is never required.
import os
import sys
import copy
import hashlib
import runner as r

PROFILE = {
    "model": "gpt-6.1-sol",
    "reasoning_effort": "medium",
    "service_tier": "fast",
    "features": {"fast_mode": True},
    "allow_fallback": False,
}
SHA = "a" * 40


class EvidenceSchemaTests(unittest.TestCase):
    def test_execution_profile_is_explicit_and_exact(self):
        self.assertEqual(r.validate_execution_profile(PROFILE), [])
        for value in (
            None,
            {},
            {**PROFILE, "allow_fallback": True},
            {**PROFILE, "extra": 1},
            {**PROFILE, "model": "other"},
            {**PROFILE, "features": {"fast_mode": False}},
        ):
            self.assertTrue(r.validate_execution_profile(value))
        argv = r.build_provider_command(
            "local-cli",
            Path("/tmp/w"),
            Path("/tmp/o"),
            Path("/tmp/s"),
            execution=PROFILE,
        )
        for argument in (
            "gpt-6.1-sol",
            'model_reasoning_effort="medium"',
            'service_tier="fast"',
            "features.fast_mode=true",
            "--ignore-user-config",
        ):
            self.assertIn(argument, argv)

    def test_response_rejects_legacy_identity_and_dangling_evidence(self):
        schema = json.loads(
            (Path(__file__).parent / "agent-output.schema.json").read_text()
        )
        expected = {
            "run_id": "r",
            "task_id": "t",
            "agent_name": "a",
            "subject_sha": SHA,
            "role": "verification",
            "check_ids": ["check"],
            "artifact_ids": ["log"],
        }
        value = {
            "schema_version": 2,
            "run_id": "r",
            "task_id": "t",
            "agent_name": "a",
            "subject_sha": SHA,
            "decision": "pass",
            "summary": "checked",
            "task_contract": None,
            "findings": [],
            "assessments": [
                {
                    "check_id": "check",
                    "decision": "pass",
                    "evidence_ids": ["log"],
                    "explanation": "ok",
                }
            ],
            "evidence_ids": ["log"],
        }
        self.assertEqual(r.validate_agent_response(value, schema, expected), [])
        for bad in (
            {"decision": "pass", "summary": "ok", "task_contract": None},
            {**value, "subject_sha": "b" * 40},
            {**value, "schema_version": True},
            {**value, "extra": 1},
            {**value, "evidence_ids": ["unknown"]},
            {**value, "assessments": []},
            {**value, "evidence_ids": ["log", "log"]},
            {**value, "findings": [{"finding_id": "f"}]},
        ):
            self.assertTrue(r.validate_agent_response(bad, schema, expected), bad)

    def test_schema_inventory_matches_fixed_records(self):
        schema = json.loads(
            (Path(__file__).parent / "agent-output.schema.json").read_text()
        )
        self.assertEqual(r.validate_schema_inventory(schema), [])
        altered = copy.deepcopy(schema)
        altered["$defs"]["Finding"]["properties"]["extra"] = {}
        self.assertTrue(r.validate_schema_inventory(altered))


class EvidenceExecutionTests(unittest.TestCase):
    def test_artifact_rejects_unsafe_inputs_and_retains_exact_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = root / "stage"
            stage.mkdir()
            dest = root / "dest"
            dest.mkdir()
            (stage / "x").write_bytes(b"valid\n")
            item = r.retain_artifact(stage, "x", dest, "x", "test-result", SHA, None)
            self.assertEqual(item["sha256"], hashlib.sha256(b"valid\n").hexdigest())
            self.assertEqual((dest / item["ref"]).read_bytes(), b"valid\n")
            (stage / "link").symlink_to(stage / "x")
            os.link(stage / "x", stage / "hard")
            os.mkfifo(stage / "fifo")
            for name in ("../x", "/x", "link", "hard", "fifo"):
                with self.assertRaises(r.RunnerError):
                    r.retain_artifact(
                        stage, name, dest, "bad", "test-result", SHA, None
                    )
            with self.assertRaises(r.RunnerError):
                r.retain_artifact(stage, "x", dest, "x", "test-result", SHA, None)

    def test_commands_capture_real_failure_unavailable_timeout_and_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            w = root / "work"
            w.mkdir()
            checks = [
                {
                    "check_id": "failed",
                    "gate": "security",
                    "argv": [
                        "python3",
                        "-c",
                        'import sys;print("out");print("err",file=sys.stderr);sys.exit(7)',
                    ],
                    "cwd": ".",
                    "timeout_seconds": 2,
                    "expected_exit_code": 0,
                    "outputs": [],
                }
            ]
            commands, artifacts, findings = r.execute_required_checks(
                w, SHA, checks, root / "out", dict(os.environ)
            )
            self.assertEqual(commands[0]["exit_code"], 7)
            self.assertEqual(commands[0]["status"], "completed")
            self.assertTrue(any(f["blocking"] for f in findings))
            self.assertTrue(any(a["kind"] == "stderr" for a in artifacts))
            checks[0].update(
                check_id="timeout",
                argv=["python3", "-c", "import time;time.sleep(10)"],
                timeout_seconds=1,
            )
            commands, _, findings = r.execute_required_checks(
                w, SHA, checks, root / "timeout", dict(os.environ)
            )
            self.assertEqual(commands[0]["status"], "timed_out")
            self.assertIsNone(commands[0]["exit_code"])
            checks[0].update(check_id="missing", argv=["go", "version"])
            with patch("runner.shutil.which", return_value=None):
                commands, _, _ = r.execute_required_checks(
                    w, SHA, checks, root / "missing", dict(os.environ)
                )
            self.assertEqual(commands[0]["status"], "unavailable")

    def test_commands_reject_missing_undeclared_secret_and_malformed_output(self):
        for script in (
            "pass",
            'open(__import__("os").environ["AUTODATA_EVIDENCE_ROOT"]+"/extra","w").write("x")',
            'open(__import__("os").environ["AUTODATA_EVIDENCE_ROOT"]+"/result.json","w").write("invalid")',
            'open(__import__("os").environ["AUTODATA_EVIDENCE_ROOT"]+"/result.json","w").write(\'{"token":"sk-secretvalue"}\')',
        ):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                check = {
                    "check_id": "c",
                    "gate": "security",
                    "argv": ["python3", "-c", script],
                    "cwd": ".",
                    "timeout_seconds": 2,
                    "expected_exit_code": 0,
                    "outputs": [
                        {
                            "artifact_id": "result",
                            "kind": "test-result",
                            "relative_path": "result.json",
                            "format": "json",
                        }
                    ],
                }
                _, _, findings = r.execute_required_checks(
                    root, SHA, [check], root / "out", dict(os.environ)
                )
                self.assertTrue(any(f["blocking"] for f in findings), script)

    def test_timeout_terminates_grandchild_and_output_exhaustion(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            marker = root / "escaped"
            script = (
                'import subprocess,time;subprocess.Popen(["python3","-c",'
                + repr(
                    "import time;from pathlib import Path;time.sleep(3);Path("
                    + repr(str(marker))
                    + ').write_text("escaped")'
                )
                + "]);time.sleep(10)"
            )
            result = r.bounded_process(
                ["python3", "-c", script], root, dict(os.environ), 1
            )
            self.assertEqual(result["status"], "timed_out")
            result = r.bounded_process(
                ["python3", "-c", 'import sys;sys.stdout.write("x"*100000)'],
                root,
                dict(os.environ),
                2,
            )
            self.assertEqual(result["status"], "completed")
            self.assertFalse(marker.exists())
            with patch("runner.MAX_LOG", 1024):
                result = r.bounded_process(
                    ["python3", "-c", 'print("x"*100000)'], root, dict(os.environ), 2
                )
            self.assertTrue(result["output_budget_exhausted"])
            self.assertLessEqual(len(result["stdout"]), 1024)


class CandidateScopeTests(unittest.TestCase):
    def test_deleted_newline_path_and_dirty_after_commit_are_checked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)

            def git(*args):
                return subprocess.run(
                    ["git", *args], cwd=root, capture_output=True, text=True, check=True
                ).stdout.strip()

            git("init")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            (root / "allowed").write_text("ok")
            (root / "outside\nname").write_text("x")
            git("add", ".")
            git("commit", "-m", "base")
            base = git("rev-parse", "HEAD")
            (root / "outside\nname").unlink()
            git("add", "-A")
            git("commit", "-m", "delete")
            head = git("rev-parse", "HEAD")
            trusted = {"policy": {"protected_paths": []}, "registry": {"agents": []}}
            result = r.inspect_candidate(
                root, base, head, "implementation", ["allowed"], trusted
            )
            self.assertIn("outside\nname", result["changed_paths"])
            self.assertTrue(
                any(f["finding_id"] == "runner.path-scope" for f in result["findings"])
            )
            (root / "allowed").write_text("dirty")
            result = r.inspect_candidate(
                root, base, head, "verification", ["**"], trusted
            )
            self.assertTrue(any(f["blocking"] for f in result["findings"]))

    def test_verifier_commit_and_protected_path_are_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)

            def git(*args):
                return subprocess.run(
                    ["git", *args], cwd=root, text=True, capture_output=True, check=True
                ).stdout.strip()

            git("init")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            (root / "x").write_text("a")
            git("add", ".")
            git("commit", "-m", "base")
            base = git("rev-parse", "HEAD")
            (root / ".autodata-agent-registry.json").write_text("{}")
            git("add", ".")
            git("commit", "-m", "protected")
            head = git("rev-parse", "HEAD")
            result = r.inspect_candidate(
                root,
                base,
                head,
                "verification",
                ["**"],
                {"subject_sha": base, "policy": {}, "registry": {}},
            )
            ids = {f["finding_id"] for f in result["findings"]}
            self.assertIn("runner.reviewer-commit", ids)
            self.assertIn("runner.protected-path", ids)


class ProvenanceMeasurementTests(unittest.TestCase):
    def test_real_fixture_and_independent_replay(self):
        fixture = Path(__file__).parent / "fixtures" / "provenance-v1"
        population = json.loads((fixture / "population.json").read_text())
        inputs = {
            n: (fixture / n).read_bytes() for n in ("source.json", "extraction.json")
        }
        with tempfile.TemporaryDirectory() as d:
            env = {
                **os.environ,
                "AUTODATA_EVIDENCE_ROOT": d,
                "AUTODATA_SUBJECT_SHA": SHA,
            }
            result = subprocess.run(
                [
                    sys.executable,
                    str(fixture.parent / "run_provenance_fixture.py"),
                    "--population",
                    str(fixture / "population.json"),
                ],
                env=env,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((Path(d) / "provenance.json").read_text())
        measured = r.measure_provenance(population, inputs, report, SHA)
        self.assertEqual(
            (measured["eligible_count"], measured["covered_count"], measured["ratio"]),
            (2, 2, 1.0),
        )
        bad = copy.deepcopy(report)
        bad["records"][0]["source_pointer"] = "/missing"
        measured = r.measure_provenance(population, inputs, bad, SHA)
        self.assertEqual(measured["ratio"], 0.5)
        self.assertTrue(measured["findings"])
        for bad in (
            {**report, "eligible_ids": []},
            {**report, "subject_sha": "b" * 40},
            {**report, "ratio": 1.0},
            {**report, "covered_ids": ["foreign"]},
            {**report, "records": report["records"] * 2},
        ):
            self.assertTrue(
                r.measure_provenance(population, inputs, bad, SHA)["findings"]
            )
        empty = {**population, "records": []}
        self.assertIsNone(r.measure_provenance(empty, inputs, report, SHA)["ratio"])


def make_trusted_repository(root):
    """Real clean Git fixture carrying the current evaluator, never a production fake mode."""
    import shutil

    source = Path(__file__).resolve().parents[2]
    task = json.loads(
        (
            source / "docs/agents/tasks/2026-11-03-production-release/r0-evidence.json"
        ).read_text()
    )
    task.update(
        task_id="fixture-task",
        allowed_paths=["app.txt"],
        evidence_contract_version=2,
        task_ref="docs/agents/tasks/fixture.json",
    )
    checks = []
    for i, gate in enumerate(r.GATES):
        cid = (
            "source-fixture"
            if gate == "source_provenance"
            else "quality-fixture" if gate == "data_quality" else "check-" + str(i)
        )
        outputs = []
        argv = ["python3", "-c", 'print("real local check")']
        if gate in ("source_provenance", "data_quality"):
            argv = [
                "python3",
                "scripts/autonomy/fixtures/run_provenance_fixture.py",
                "--population",
                "scripts/autonomy/fixtures/provenance-v1/population.json",
            ]
            outputs = [
                {
                    "artifact_id": cid + ":proof",
                    "kind": "provenance-result",
                    "relative_path": "provenance.json",
                    "format": "json",
                }
            ]
        checks.append(
            {
                "check_id": cid,
                "gate": gate,
                "argv": argv,
                "cwd": ".",
                "timeout_seconds": 5,
                "expected_exit_code": 0,
                "outputs": outputs,
            }
        )
    task["verification"] = {
        "checks": checks,
        "provenance": {
            "check_id": "source-fixture",
            "population_ref": "scripts/autonomy/fixtures/provenance-v1/population.json",
            "report_artifact_id": "source-fixture:proof",
        },
        "required_agent_evidence": [
            x + ":response" for x in ("architect", "builder", *r.GATES)
        ],
    }
    paths = [
        ".autodata-agent-registry.json",
        ".autodata-autonomy-policy.json",
        "scripts/autonomy/runner.py",
        "scripts/autonomy/orchestrator.py",
        "scripts/autonomy/pre_implementation.py",
        "scripts/autonomy/validate_run.py",
        "scripts/autonomy/agent-output.schema.json",
        "scripts/autonomy/fixtures/run_provenance_fixture.py",
        task["pre_implementation"]["plan_ref"],
        *task["pre_implementation"]["repository_doc_refs"],
    ]
    registry = json.loads((source / ".autodata-agent-registry.json").read_text())
    paths += [a["prompt"] for a in registry["agents"]]
    paths += [
        "scripts/autonomy/fixtures/provenance-v1/" + name
        for name in ("population.json", "source.json", "extraction.json")
    ]
    for path in paths:
        dest = root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / path, dest)
    (root / "docs/agents/tasks").mkdir(parents=True, exist_ok=True)
    (root / task["task_ref"]).write_text(json.dumps(task))
    (root / "app.txt").write_text("before")

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("add", ".")
    git("commit", "-m", "trusted fixture")
    return task, git("rev-parse", "HEAD")


class TrustBoundaryTests(unittest.TestCase):
    def test_load_uses_committed_inputs_and_external_overrides_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            task, base = make_trusted_repository(root)
            trusted = r.load_trusted_inputs(root, base, task["task_ref"])
            self.assertEqual(trusted["task"], task)
            (root / ".autodata-autonomy-policy.json").write_text("{}")
            self.assertNotEqual(
                r.load_trusted_inputs(root, base, task["task_ref"])["policy"], {}
            )
            self.assertTrue(
                r.validate_task_input({**task, "allowed_paths": ["**"]}, trusted)
            )
            self.assertTrue(
                r.validate_task_input({**task, "unknown": "override"}, trusted)
            )
            self.assertFalse(
                r.validate_task_input({**task, "run_id": "unique"}, trusted)
            )
            with self.assertRaises(r.RunnerError):
                r.load_trusted_inputs(root, base, "docs/agents/tasks/missing.json")
            with self.assertRaises(r.RunnerError):
                r.load_trusted_inputs(root, base, "../task.json")

    def test_loaded_evaluator_cannot_self_certify_candidate_version(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            task, base = make_trusted_repository(root)
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", "descendant"],
                cwd=root,
                capture_output=True,
                check=True,
            )
            # Pinning a different evaluator blob must be detected, not read as candidate authority.
            (root / "scripts/autonomy/runner.py").write_text("# alternate evaluator\n")
            subprocess.run(
                ["git", "add", "."], cwd=root, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "changed evaluator"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            candidate = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            with self.assertRaisesRegex(r.RunnerError, "loaded evaluator differs"):
                r.load_trusted_inputs(root, candidate, task["task_ref"])


class IntegrityEdgeTests(unittest.TestCase):
    def test_conflicting_runtime_profile_cannot_be_hidden_by_later_event(self):
        earlier = json.dumps({"type": "session_config", "model": "other"})
        later = json.dumps(
            {
                "type": "session_config",
                "model": "gpt-6.1-sol",
                "reasoning_effort": "medium",
                "service_tier": "fast",
            }
        )
        observed = r._runtime_metadata(earlier + "\n" + later)
        self.assertNotEqual(
            observed,
            {
                "model": "gpt-6.1-sol",
                "reasoning_effort": "medium",
                "service_tier": "fast",
            },
        )

    def test_candidate_keeps_canonical_documentation_policy(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            task, base = make_trusted_repository(root)
            (root / "outside.md").write_text("outside canonical docs")
            subprocess.run(
                ["git", "add", "outside.md"], cwd=root, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "outside docs"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            candidate = r._run_git(root, ["rev-parse", "HEAD"]).strip()
            trusted = r.load_trusted_inputs(root, base, task["task_ref"])
            result = r.inspect_candidate(
                root, base, candidate, "implementation", ["outside.md"], trusted
            )
            self.assertTrue(
                any(
                    f["finding_id"] == "runner.documentation-scope"
                    for f in result["findings"]
                )
            )

    def test_undeclared_directory_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            check = {
                "check_id": "dirs",
                "gate": "security",
                "argv": [
                    "python3",
                    "-c",
                    'import os;os.mkdir(os.environ["AUTODATA_EVIDENCE_ROOT"]+"/undeclared")',
                ],
                "cwd": ".",
                "timeout_seconds": 2,
                "expected_exit_code": 0,
                "outputs": [],
            }
            _, _, findings = r.execute_required_checks(
                root, SHA, [check], root / "out", dict(os.environ)
            )
            self.assertTrue(any(f["blocking"] for f in findings))

    def test_later_setup_failure_preserves_earlier_check_evidence(self):
        for failure in ("unsafe-cwd", "symlink-cwd", "staging-mkdir"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                work = root / "work"
                work.mkdir()
                output = root / "out"
                checks = [
                    {
                        "check_id": cid,
                        "gate": "security",
                        "argv": ["python3", "-c", 'print("retained")'],
                        "cwd": ".",
                        "timeout_seconds": 2,
                        "expected_exit_code": 0,
                        "outputs": [],
                    }
                    for cid in ("first", "second")
                ]
                if failure == "unsafe-cwd":
                    checks[1]["cwd"] = "../outside"
                elif failure == "symlink-cwd":
                    (work / "linked").symlink_to(root, target_is_directory=True)
                    checks[1]["cwd"] = "linked"
                else:
                    stage = output / "staging" / "second"
                    stage.mkdir(parents=True)
                commands, artifacts, findings = r.execute_required_checks(
                    work, SHA, checks, output, dict(os.environ)
                )
                self.assertEqual([c["check_id"] for c in commands], ["first"])
                self.assertEqual(commands[0]["exit_code"], 0)
                self.assertEqual(
                    {a["artifact_id"] for a in artifacts},
                    {"first:stdout", "first:stderr", "first:command"},
                )
                self.assertTrue(
                    all(not r.validate_artifact(a, output) for a in artifacts)
                )
                self.assertTrue(
                    any(
                        f["blocking"] and f["finding_id"] == "runner.second.setup"
                        for f in findings
                    ),
                    findings,
                )

    def test_cleanup_failure_keeps_command_and_artifact_records(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            work = root / "work"
            work.mkdir()
            check = {
                "check_id": "c",
                "gate": "security",
                "argv": ["python3", "-c", 'print("retained")'],
                "cwd": ".",
                "timeout_seconds": 2,
                "expected_exit_code": 0,
                "outputs": [],
            }
            with patch(
                "runner.shutil.rmtree", side_effect=OSError("fixture cleanup failure")
            ):
                commands, artifacts, findings = r.execute_required_checks(
                    work, SHA, [check], root / "out", dict(os.environ)
                )
            self.assertEqual(commands[0]["exit_code"], 0)
            self.assertEqual(len(artifacts), 3)
            self.assertTrue(any(f["finding_id"] == "runner.cleanup" for f in findings))

    def test_schema_profile_constants_cannot_drift(self):
        schema = json.loads(
            (Path(__file__).parent / "agent-output.schema.json").read_text()
        )
        bad = copy.deepcopy(schema)
        bad["properties"] = {}
        self.assertTrue(r.validate_schema_inventory(bad))
        for name, field, value in [
            ("Execution", "model", "other"),
            ("Features", "fast_mode", False),
            ("CommandRecord", "schema_version", 1),
        ]:
            bad = copy.deepcopy(schema)
            bad["$defs"][name]["properties"][field]["const"] = value
            self.assertTrue(r.validate_schema_inventory(bad))

    def test_symlink_staging_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            outside = root / "outside"
            outside.mkdir()
            (outside / "payload").write_text("payload")
            stage = root / "stage"
            stage.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(r.RunnerError):
                r.retain_artifact(
                    stage, "payload", root / "out", "p", "test-result", SHA, None
                )

    def test_response_malformed_primitives_return_errors(self):
        expected = {
            "run_id": "r",
            "task_id": "t",
            "agent_name": "a",
            "subject_sha": SHA,
            "role": "verification",
            "check_ids": [],
            "artifact_ids": [],
        }
        good = {
            "schema_version": 2,
            "run_id": "r",
            "task_id": "t",
            "agent_name": "a",
            "subject_sha": SHA,
            "decision": "pass",
            "summary": "ok",
            "task_contract": None,
            "findings": [],
            "assessments": [],
            "evidence_ids": [],
        }
        for key in good:
            for invalid in ({"nested": "invalid"}, True, 42):
                value = {**good, key: invalid}
                self.assertTrue(
                    r.validate_agent_response(value, {}, expected), (key, invalid)
                )

    def test_dirty_check_is_retained(self):
        # Full chain tests cover the process boundary; here the mutation is a real check.
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as out:
            root = Path(d)
            task, base = make_trusted_repository(root)
            check = {
                "check_id": "dirty",
                "gate": "security",
                "argv": ["python3", "-c", 'open("app.txt","w").write("dirty")'],
                "cwd": ".",
                "timeout_seconds": 2,
                "expected_exit_code": 0,
                "outputs": [],
            }
            _, _, findings = r.execute_required_checks(
                root, base, [check], Path(out), dict(os.environ)
            )
            self.assertTrue(
                any(f["finding_id"] == "runner.check-dirty-tree" for f in findings)
            )


if __name__ == "__main__":
    unittest.main()
