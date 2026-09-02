import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
from validate_run import evaluate  # noqa: E402


POLICY = {
    "merge_gate": {
        "required_decisions": ["deterministic_ci", "data_quality"],
        "max_critical_findings": 0,
        "max_high_findings": 0,
        "min_evidence_completeness": 1.0,
        "min_fast_lane_provenance_coverage": 1.0,
    }
}


def manifest(**overrides):
    value = {
        "run_id": "run-1",
        "task_id": "issue-1",
        "base_sha": "a" * 40,
        "implementation_sha": "b" * 40,
        "agent": "autodata-orchestrator",
        "phase": "verifying",
        "decision": "pass",
        "evidence": [
            {"kind": "test-result", "ref": "test.json", "sha256": "c" * 64}
        ],
        "gate_decisions": {
            "deterministic_ci": "pass",
            "data_quality": "pass",
        },
        "gate_reports": [
            {
                "gate": "deterministic_ci",
                "decision": "pass",
                "implementation_sha": "b" * 40,
                "evidence": [{"ref": "ci.json", "sha256": "c" * 64}],
            },
            {
                "gate": "data_quality",
                "decision": "pass",
                "implementation_sha": "b" * 40,
                "evidence": [{"ref": "quality.json", "sha256": "d" * 64}],
            },
        ],
        "findings": [],
        "evidence_completeness": 1.0,
        "fast_lane_provenance_coverage": 1.0,
    }
    value.update(overrides)
    return value


class ValidateRunTests(unittest.TestCase):
    def test_accepts_complete_run_with_matching_sha_and_gates(self):
        result = evaluate(manifest(), POLICY)

        self.assertTrue(result["passed"])
        self.assertEqual(result["failures"], [])

    def test_rejects_missing_required_gate(self):
        value = manifest(gate_decisions={"deterministic_ci": "pass"})

        result = evaluate(value, POLICY)

        self.assertFalse(result["passed"])
        self.assertIn("missing required gate decision: data_quality", result["failures"])

    def test_rejects_failed_gate_and_critical_finding(self):
        value = manifest(
            gate_decisions={"deterministic_ci": "fail", "data_quality": "pass"},
            findings=[{"severity": "critical", "message": "unsafe publication"}],
        )

        result = evaluate(value, POLICY)

        self.assertFalse(result["passed"])
        self.assertIn("gate decision is not pass: deterministic_ci=fail", result["failures"])
        self.assertIn("critical findings exceed policy limit: 1 > 0", result["failures"])

    def test_rejects_incomplete_evidence_and_provenance(self):
        value = manifest(evidence_completeness=0.5, fast_lane_provenance_coverage=0.75)

        result = evaluate(value, POLICY)

        self.assertFalse(result["passed"])
        self.assertIn("evidence completeness below policy minimum: 0.5 < 1.0", result["failures"])
        self.assertIn(
            "fast-lane provenance coverage below policy minimum: 0.75 < 1.0",
            result["failures"],
        )

    def test_rejects_invalid_implementation_sha(self):
        value = manifest(implementation_sha="not-a-sha")

        result = evaluate(value, POLICY)

        self.assertFalse(result["passed"])
        self.assertIn("implementation_sha must be a 40-character hexadecimal SHA", result["failures"])

    def test_rejects_gate_report_pinned_to_stale_sha(self):
        value = manifest()
        value["gate_reports"][0]["implementation_sha"] = "e" * 40

        result = evaluate(value, POLICY)

        self.assertFalse(result["passed"])
        self.assertIn(
            "gate report SHA mismatch: deterministic_ci",
            result["failures"],
        )

    def test_rejects_missing_evidence_file(self):
        with tempfile.TemporaryDirectory() as directory:
            result = evaluate(manifest(), POLICY, evidence_root=Path(directory))

        self.assertFalse(result["passed"])
        self.assertIn("evidence file not found: test.json", result["failures"])

    def test_rejects_tampered_evidence_file(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory)
            (evidence_root / "test.json").write_text("tampered", encoding="utf-8")
            (evidence_root / "ci.json").write_text("ci", encoding="utf-8")
            (evidence_root / "quality.json").write_text("quality", encoding="utf-8")

            result = evaluate(manifest(), POLICY, evidence_root=evidence_root)

        self.assertFalse(result["passed"])
        self.assertIn("evidence hash mismatch: test.json", result["failures"])

    def test_rejects_evidence_path_traversal(self):
        value = manifest()
        value["evidence"][0]["ref"] = "../outside.json"

        with tempfile.TemporaryDirectory() as directory:
            result = evaluate(value, POLICY, evidence_root=Path(directory))

        self.assertFalse(result["passed"])
        self.assertIn("evidence path escapes evidence root: ../outside.json", result["failures"])


if __name__ == "__main__":
    unittest.main()
