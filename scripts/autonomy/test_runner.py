import json
import tempfile
import unittest
from pathlib import Path


from runner import (
    build_provider_command,
    changed_paths,
    redact_text,
    validate_envelope,
)


class RunnerTests(unittest.TestCase):
    def test_codex_command_is_noninteractive_and_workspace_scoped(self):
        command = build_provider_command(
            provider="codex",
            cwd=Path("/tmp/worktree"),
            output_file=Path("/tmp/last.json"),
            schema_file=Path("/tmp/schema.json"),
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
            )

    def test_envelope_rejects_production_and_unregistered_agent(self):
        registry = {"agents": [{"name": "autodata-go-builder", "prompt": "agent.md"}]}
        policy = {"autonomy": {"production_deployment": False, "allowed_deployment_targets": ["dev"]}}

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
        policy = {"autonomy": {"production_deployment": False, "allowed_deployment_targets": []}}

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
                "if [ \"$1\" = diff ]; then printf 'apps/api/main.go\\n'; fi\n"
                "if [ \"$1\" = ls-files ]; then printf 'docs/new.md\\n'; fi\n",
                encoding="utf-8",
            )
            git.chmod(0o755)
            result = changed_paths(root, "a" * 40, git_executable=str(git))

        self.assertEqual(result, ["apps/api/main.go", "docs/new.md"])

    def test_redacts_common_secret_shapes(self):
        text = "token=sk-abc123 github_pat_abc123 AKIAIOSFODNN7EXAMPLE"

        redacted = redact_text(text)

        self.assertNotIn("sk-abc123", redacted)
        self.assertNotIn("github_pat_abc123", redacted)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", redacted)
        self.assertEqual(redacted.count("[REDACTED_SECRET]"), 3)


if __name__ == "__main__":
    unittest.main()
