import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


from orchestrator import GATE_AGENTS, aggregate_gate_reports, orchestrate_task, validate_task_contract


class OrchestratorTests(unittest.TestCase):
    def test_all_policy_gates_have_independent_agents(self):
        required = {
            "deterministic_ci",
            "contract_compatibility",
            "schema_integrity",
            "source_provenance",
            "data_quality",
            "security",
            "reliability",
            "independent_review",
        }

        self.assertEqual(set(GATE_AGENTS), required)
        self.assertEqual(len(set(GATE_AGENTS.values())), len(required))

    def test_task_contract_requires_measurable_scope(self):
        contract = {
            "task_id": "task-1",
            "goal": "Add a deterministic endpoint",
            "bounded_contexts": ["api"],
            "inputs": ["docs/architecture/contracts.md"],
            "outputs": ["apps/api-go/"],
            "acceptance_tests": ["GET returns 200 for an entitled caller"],
            "forbidden_scope": ["web UI"],
            "compatibility": {"api": "preserve-or-version", "events": "preserve", "schema": "none"},
        }

        self.assertEqual(validate_task_contract(contract), [])
        self.assertIn("goal must be a non-empty string", validate_task_contract({**contract, "goal": ""}))

    def test_aggregate_gate_reports_preserves_sha_and_fails_missing_gate(self):
        reports = aggregate_gate_reports(
            run_id="run-1",
            implementation_sha="b" * 40,
            provider_runs={
                "deterministic_ci": {
                    "decision": "pass",
                    "evidence": {"ref": "evidence/test.json", "sha256": "c" * 64},
                }
            },
        )

        self.assertEqual(reports["deterministic_ci"]["implementation_sha"], "b" * 40)
        self.assertEqual(reports["deterministic_ci"]["decision"], "pass")
        self.assertEqual(reports["security"]["decision"], "blocked")
        self.assertEqual(reports["security"]["implementation_sha"], "b" * 40)

    def test_orchestration_assembles_a_complete_policy_manifest(self):
        task = {
            "task_id": "task-1",
            "goal": "Add a deterministic endpoint",
            "builder_agent": "autodata-go-builder",
            "allowed_paths": ["apps/api-go/**"],
            "bounded_contexts": ["api"],
            "inputs": ["docs/architecture/contracts.md"],
            "outputs": ["apps/api-go/"],
            "acceptance_tests": ["GET returns 200 for an entitled caller"],
            "forbidden_scope": ["web UI"],
            "compatibility": {"api": "preserve-or-version", "events": "preserve", "schema": "none"},
        }
        contract = {
            "task_id": "task-1",
            "goal": "Add a deterministic endpoint",
            "bounded_contexts": ["api"],
            "inputs": ["docs/architecture/contracts.md"],
            "outputs": ["apps/api-go/"],
            "acceptance_tests": ["GET returns 200 for an entitled caller"],
            "forbidden_scope": ["web UI"],
            "compatibility": {"api": "preserve-or-version", "events": "preserve", "schema": "none"},
        }
        implementation_sha = "b" * 40

        def fake_run_agent(repo_root, envelope, provider, output_root, timeout_seconds):
            output_root.mkdir(parents=True)
            evidence = output_root / "evidence"
            evidence.mkdir()
            response = {
                "decision": "pass",
                "summary": "fixture agent pass",
                "task_contract": contract if envelope["agent_name"] == "autodata-architect" else None,
            }
            (evidence / "provider-output.json").write_text(json.dumps(response), encoding="utf-8")
            manifest = {
                "implementation_sha": implementation_sha if envelope["agent_name"] == "autodata-go-builder" else envelope["base_sha"],
                "changed_paths": ["apps/api-go/main.go"] if envelope["agent_name"] == "autodata-go-builder" else [],
                "findings": [],
                "commands_run": [{"exit_code": 0}],
            }
            manifest_path = output_root / "run-manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            return 20, manifest_path

        with tempfile.TemporaryDirectory() as directory, patch("orchestrator.run_agent", fake_run_agent):
            code, manifest_path = orchestrate_task(
                Path.cwd(), task, "local-cli", Path(directory) / "run", 1
            )
            final = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(final["implementation_sha"], implementation_sha)
        self.assertEqual(final["decision"], "pass")
        self.assertEqual(set(final["gate_decisions"]), set(GATE_AGENTS))


if __name__ == "__main__":
    unittest.main()
