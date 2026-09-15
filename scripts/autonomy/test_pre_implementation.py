import json
import subprocess
import unittest
from pathlib import Path


from pre_implementation import validate_record


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_SHA = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, capture_output=True, check=True
).stdout.strip()
POLICY = json.loads((REPO_ROOT / ".autodata-autonomy-policy.json").read_text(encoding="utf-8"))


def valid_record() -> dict:
    return {
        "goal": "Enforce a machine-checked planning gate before implementation",
        "plan_ref": "docs/superpowers/plans/2026-09-11-pre-implementation-gate.md",
        "issue_ref": "https://github.com/lucronn/autodata/issues/86",
        "project_ref": "https://github.com/users/lucronn/projects/8",
        "repository_doc_refs": ["docs/github/operating-model.md"],
        "todo": ["Add the validator", "Run the enforcement tests"],
        "status": "synchronized",
        "updated_at": "2026-09-11T00:00:00Z",
    }


class PreImplementationTests(unittest.TestCase):
    def test_missing_record_is_blocked(self):
        errors = validate_record(None, REPO_ROOT, BASE_SHA, POLICY)

        self.assertIn("pre_implementation record is required", errors)

    def test_synchronized_record_with_existing_plan_and_docs_is_valid(self):
        errors = validate_record(valid_record(), REPO_ROOT, BASE_SHA, POLICY)

        self.assertEqual(errors, [])

    def test_missing_required_field_is_blocked(self):
        record = valid_record()
        del record["issue_ref"]

        errors = validate_record(record, REPO_ROOT, BASE_SHA, POLICY)

        self.assertIn("pre_implementation.issue_ref is required", errors)

    def test_invalid_tracking_urls_are_blocked(self):
        record = valid_record()
        record["issue_ref"] = "https://example.test/issues/86"
        record["project_ref"] = "https://example.test/projects/8"

        errors = validate_record(record, REPO_ROOT, BASE_SHA, POLICY)

        self.assertIn("pre_implementation.issue_ref must be a GitHub Issue URL", errors)
        self.assertIn("pre_implementation.project_ref must be a GitHub Project URL", errors)

    def test_empty_todo_and_unsynchronized_status_are_blocked(self):
        record = valid_record()
        record["todo"] = []
        record["status"] = "planning"

        errors = validate_record(record, REPO_ROOT, BASE_SHA, POLICY)

        self.assertIn("pre_implementation.todo must be a non-empty list of strings", errors)
        self.assertIn("pre_implementation.status must equal synchronized", errors)

    def test_timestamp_without_timezone_is_blocked(self):
        record = valid_record()
        record["updated_at"] = "2026-09-11T00:00:00"

        errors = validate_record(record, REPO_ROOT, BASE_SHA, POLICY)

        self.assertIn("pre_implementation.updated_at must be an ISO-8601 UTC timestamp", errors)

    def test_noncanonical_or_missing_references_are_blocked(self):
        record = valid_record()
        record["plan_ref"] = "README.md"
        record["repository_doc_refs"] = ["docs/does-not-exist.md"]

        errors = validate_record(record, REPO_ROOT, BASE_SHA, POLICY)

        self.assertIn("pre_implementation.plan_ref is outside the configured plan paths", errors)
        self.assertIn("pre_implementation.repository_doc_refs[0] is absent at base_sha", errors)


if __name__ == "__main__":
    unittest.main()
