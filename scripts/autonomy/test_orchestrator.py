import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runner as r
import orchestrator as o
from test_runner import PROFILE, SHA

REPO_ROOT = Path(__file__).resolve().parents[2]


class EvidenceAggregationTests(unittest.TestCase):
    def test_summary_only_gate_cannot_receive_candidate_sha(self):
        reports = o.aggregate_gate_reports(
            "run", SHA, {"security": {"decision": "pass"}}
        )
        self.assertEqual(reports["security"]["decision"], "blocked")
        self.assertIsNone(reports["security"]["implementation_sha"])
        self.assertEqual(reports["source_provenance"]["decision"], "blocked")

    def test_coverage_reopens_files_and_nonempty_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = r._save_artifact(b"one", root, "one", "test-result", SHA, None)
            p = {"ratio": 0.5, "eligible_count": 2, "covered_count": 1}
            measured = o.calculate_coverage({"one", "two"}, [a], p, root)
            self.assertEqual(measured["evidence_completeness"], 0.5)
            self.assertEqual(measured["evidence"]["missing_ids"], ["two"])
            (root / a["ref"]).write_bytes(b"tampered")
            self.assertEqual(
                o.calculate_coverage({"one"}, [a], p, root)["evidence_completeness"], 0
            )
            self.assertTrue(
                o.calculate_coverage(set(), [a], p, root)["evidence"]["errors"]
            )
            self.assertTrue(
                o.calculate_coverage({"one"}, [a, a], p, root)["evidence"]["errors"]
            )

    def test_configuration_blocks_before_provider_or_output_creation(self):
        with tempfile.TemporaryDirectory() as d, patch(
            "orchestrator.run_agent"
        ) as provider:
            root = Path(d) / "run"
            with self.assertRaises(r.RunnerError):
                o.orchestrate_task(
                    REPO_ROOT, {"task_id": "legacy"}, "local-cli", root, 1
                )
            provider.assert_not_called()
            self.assertFalse(root.exists())

    def test_agent_usable_reads_runner_state_and_blocking_medium(self):
        self.assertFalse(
            o._agent_usable(
                {"response": {"decision": "pass"}, "decision": "blocked"}, False, SHA
            )
        )
        self.assertFalse(
            o._agent_usable(
                {
                    "decision": "pass",
                    "findings": [{"severity": "medium", "blocking": True}],
                },
                False,
                SHA,
            )
        )

    def test_bundle_rejects_fabricated_legacy_metrics_and_missing_required_slots(self):
        trusted = {
            "trusted_base_sha": SHA,
            "task": {
                "task_id": "t",
                "execution": PROFILE,
                "verification": {
                    "checks": [],
                    "required_agent_evidence": [],
                    "provenance": {
                        "check_id": "source-fixture",
                        "population_ref": "fixture/population.json",
                        "report_artifact_id": "source",
                    },
                },
            },
            "policy": json.loads(
                (REPO_ROOT / ".autodata-autonomy-policy.json").read_text()
            ),
            "artifacts": {},
            "population": {
                "population_id": "x",
                "scope": "synthetic-regression",
                "records": [],
            },
            "provenance_inputs": {},
        }
        with tempfile.TemporaryDirectory() as d:
            result = o.validate_evidence_bundle(
                {
                    "evidence_completeness": 1.0,
                    "fast_lane_provenance_coverage": 1.0,
                    "implementation_sha": SHA,
                },
                trusted,
                Path(d),
            )
            self.assertFalse(result["passed"])
            self.assertTrue(result["failures"])


class FullChainV2Tests(unittest.TestCase):
    def run_fixture(self, directory, fail_check=False, unavailable=False):
        from test_runner import make_trusted_repository

        root = directory / "repo"
        root.mkdir()
        task, base = make_trusted_repository(root)
        trusted = r.load_trusted_inputs(root, base, task["task_ref"])
        original = r.bounded_process
        if fail_check:
            # Commit a failed command as a frozen requirement, never modify it after trust resolution.
            task["verification"]["checks"][0]["argv"] = [
                "python3",
                "-c",
                "raise SystemExit(7)",
            ]
            (root / task["task_ref"]).write_text(json.dumps(task))
            import subprocess

            subprocess.run(
                ["git", "add", "."], cwd=root, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "failed fixture requirement"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            base = r._run_git(root, ["rev-parse", "HEAD"]).strip()
            trusted = r.load_trusted_inputs(root, base, task["task_ref"])
        envelopes = []

        def process(argv, cwd, env, timeout, stdin=b""):
            if argv[0] != "codex":
                return original(argv, cwd, env, timeout, stdin)
            envelope = json.loads((cwd.parent / "task-envelope.json").read_text())
            envelopes.append(envelope)
            if unavailable and envelope.get("gate") == "security":
                return {
                    "started_at": r.utc_now(),
                    "finished_at": r.utc_now(),
                    "status": "unavailable",
                    "exit_code": None,
                    "stdout": b"",
                    "stderr": b"fixture unavailable",
                    "output_budget_exhausted": False,
                }
            if envelope["agent_name"] == task["builder_agent"]:
                import subprocess

                (cwd / "app.txt").write_text("after")
                subprocess.run(
                    ["git", "add", "app.txt"], cwd=cwd, check=True, capture_output=True
                )
                subprocess.run(
                    ["git", "commit", "-m", "fixture implementation"],
                    cwd=cwd,
                    check=True,
                    capture_output=True,
                )
            subject = r._run_git(cwd, ["rev-parse", "HEAD"]).strip()
            checks = [
                c
                for c in task["verification"]["checks"]
                if c["gate"] == envelope.get("gate")
            ]
            assessments = [
                {
                    "check_id": c["check_id"],
                    "decision": "pass",
                    "evidence_ids": [c["check_id"] + ":command"],
                    "explanation": "assessed retained actual report",
                }
                for c in checks
            ]
            response = {
                "schema_version": 2,
                "run_id": envelope["run_id"],
                "task_id": task["task_id"],
                "agent_name": envelope["agent_name"],
                "subject_sha": subject,
                "decision": "pass",
                "summary": "test-only fake provider",
                "task_contract": (
                    envelope["task_contract"]
                    if envelope["agent_name"] == "autodata-architect"
                    else None
                ),
                "findings": [],
                "assessments": assessments,
                "evidence_ids": [],
            }
            Path(argv[argv.index("-o") + 1]).write_text(json.dumps(response))
            return {
                "started_at": r.utc_now(),
                "finished_at": r.utc_now(),
                "status": "completed",
                "exit_code": 0,
                "stdout": b'{"type":"session_config","model":"gpt-6.1-sol","reasoning_effort":"medium","service_tier":"priority"}\n',
                "stderr": b"",
                "output_budget_exhausted": False,
            }

        output = directory / "bundle"
        with patch("runner.bounded_process", process):
            code, path = o.orchestrate_task(root, task, "local-cli", output, 5)
        return code, path, trusted, envelopes

    def test_real_checks_fake_provider_complete_bundle_and_replay_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            code, path, trusted, envelopes = self.run_fixture(Path(d))
            final = json.loads(path.read_text())
            self.assertEqual(code, 0, (path.parent / "decision.json").read_text())
            self.assertEqual(len(envelopes), 10)
            self.assertEqual(
                final["agent_runs"]["architect"]["provider_command"]["exit_code"], 0
            )
            self.assertTrue(
                any(
                    a["artifact_id"] == "architect:invocation"
                    for a in final["artifacts"]
                )
            )
            self.assertTrue(all(e["execution"] == PROFILE for e in envelopes))
            self.assertEqual(final["measurements"]["provenance"]["eligible_count"], 2)
            self.assertTrue(
                o.validate_evidence_bundle(final, trusted, path.parent)["passed"]
            )
            for mutate in (
                "metric",
                "count",
                "slots",
                "missing-gate",
                "stale",
                "blocking-medium",
            ):
                bad = copy.deepcopy(final)
                if mutate == "metric":
                    bad["fast_lane_provenance_coverage"] = 0.5
                elif mutate == "count":
                    bad["measurements"]["provenance"]["covered_count"] = 1
                elif mutate == "slots":
                    bad["measurements"]["evidence"]["required_ids"] = []
                elif mutate == "missing-gate":
                    del bad["agent_runs"]["security"]
                elif mutate == "stale":
                    bad["agent_runs"]["security"]["subject_sha"] = "b" * 40
                else:
                    bad["agent_runs"]["security"]["findings"] = [
                        {**r.finding("medium", "blocked"), "severity": "medium"}
                    ]
                self.assertFalse(
                    o.validate_evidence_bundle(bad, trusted, path.parent)["passed"],
                    mutate,
                )
            response_artifact = next(
                a for a in final["artifacts"] if a["artifact_id"] == "security:response"
            )
            response_path = path.parent / response_artifact["ref"]
            original_response = response_path.read_bytes()
            for nonpass in ("fail", "blocked", "needs_review", "not_applicable"):
                bad = copy.deepcopy(final)
                response = copy.deepcopy(bad["agent_runs"]["security"]["response"])
                response["decision"] = nonpass
                changed = json.dumps(response).encode()
                response_path.write_bytes(changed)
                bad["agent_runs"]["security"]["response"] = response
                digest = hashlib.sha256(changed).hexdigest()

                def refresh(value):
                    if isinstance(value, dict):
                        if value.get("artifact_id") == "security:response":
                            value["sha256"] = digest
                            value["size_bytes"] = len(changed)
                        for child in value.values():
                            refresh(child)
                    elif isinstance(value, list):
                        for child in value:
                            refresh(child)

                refresh(bad)
                try:
                    replay = o.validate_evidence_bundle(bad, trusted, path.parent)
                    self.assertFalse(replay["passed"], nonpass)
                    self.assertTrue(
                        any(
                            "provider decision" in error for error in replay["failures"]
                        ),
                        replay,
                    )
                finally:
                    response_path.write_bytes(original_response)
            artifact = final["artifacts"][0]
            (path.parent / artifact["ref"]).write_bytes(b"tampered")
            self.assertFalse(
                o.validate_evidence_bundle(final, trusted, path.parent)["passed"]
            )

    def test_real_failed_check_cannot_be_overridden_by_fake_provider_pass(self):
        with tempfile.TemporaryDirectory() as d:
            code, path, trusted, _ = self.run_fixture(Path(d), fail_check=True)
            self.assertEqual(code, 20)
            final = json.loads(path.read_text())
            self.assertEqual(final["commands_run"][0]["exit_code"], 7)
            self.assertFalse(
                o.validate_evidence_bundle(final, trusted, path.parent)["passed"]
            )

    def test_unavailable_provider_keeps_successful_actual_command_records(self):
        with tempfile.TemporaryDirectory() as d:
            code, path, trusted, _ = self.run_fixture(Path(d), unavailable=True)
            self.assertEqual(code, 20)
            final = json.loads(path.read_text())
            security = final["agent_runs"]["security"]
            self.assertEqual(security["commands_run"][0]["exit_code"], 0)
            self.assertEqual(security["agent_decision"], "blocked")
            validation = o.validate_evidence_bundle(final, trusted, path.parent)
            self.assertNotIn(
                "final findings differ from runner findings", validation["failures"]
            )
            self.assertFalse(
                o.validate_evidence_bundle(final, trusted, path.parent)["passed"]
            )


if __name__ == "__main__":
    unittest.main()
