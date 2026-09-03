#!/usr/bin/env python3
"""Validate repository-native contribution and ownership contracts."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RepositoryGovernanceTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        path = ROOT / relative_path
        self.assertTrue(path.is_file(), f"missing governance file: {relative_path}")
        return path.read_text(encoding="utf-8")

    def test_required_governance_files_exist(self) -> None:
        required = (
            ".github/CODEOWNERS",
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/ISSUE_TEMPLATE/config.yml",
            ".github/ISSUE_TEMPLATE/feature.yml",
            ".github/ISSUE_TEMPLATE/source-ingestion.yml",
            ".github/ISSUE_TEMPLATE/data-quality.yml",
            ".github/ISSUE_TEMPLATE/infrastructure.yml",
            ".github/ISSUE_TEMPLATE/security-privacy.yml",
            ".github/ISSUE_TEMPLATE/dataset-enrichment.yml",
            "CONTRIBUTING.md",
            "SECURITY.md",
        )
        for relative_path in required:
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_codeowners_has_explicit_domain_coverage(self) -> None:
        content = self.read(".github/CODEOWNERS")
        for pattern in (
            "/apps/api-go/",
            "/workers/ingestion-python/",
            "/workers/enrichment-python/",
            "/packages/contracts/",
            "/db/",
            "/infra/",
            "/docs/",
            "/.github/",
            "*",
        ):
            self.assertRegex(content, rf"(?m)^{re.escape(pattern)}\s+@lucronn(?:\s|$)")
        self.assertNotRegex(content, r"(?i)(TODO|TBD|OWNER/REPO|your[-_ ]handle)")

    def test_pull_request_template_captures_delivery_contract(self) -> None:
        content = self.read(".github/PULL_REQUEST_TEMPLATE.md")
        for heading in (
            "## Linked issue",
            "## Outcome",
            "## Contract and schema impact",
            "## Provenance and evidence",
            "## Verification",
            "## Security and secrets",
            "## Documentation and Project tracking",
        ):
            self.assertIn(heading, content)
        self.assertIn("sample data/", content)
        self.assertIn("automation/<topic>", content)

    def test_issue_forms_cover_required_outcomes(self) -> None:
        forms = {
            "feature.yml": "type:feature",
            "source-ingestion.yml": "type:source-ingestion",
            "data-quality.yml": "type:data-quality",
            "infrastructure.yml": "type:infrastructure",
            "security-privacy.yml": "type:security",
            "dataset-enrichment.yml": "type:feature",
        }
        for filename, label in forms.items():
            content = self.read(f".github/ISSUE_TEMPLATE/{filename}")
            for key in ("name:", "description:", "title:", "labels:", "body:"):
                self.assertIn(key, content, filename)
            self.assertIn(label, content, filename)
            for field_id in ("area", "user-impact", "acceptance", "evidence", "contract-impact"):
                self.assertRegex(content, rf"(?m)^\s+id:\s+{re.escape(field_id)}\s*$", filename)

    def test_security_and_contributing_guidance_are_safe(self) -> None:
        security = self.read("SECURITY.md")
        contributing = self.read("CONTRIBUTING.md")
        self.assertIn("/security/advisories/new", security)
        self.assertRegex(security, r"(?i)do not.*(credential|token|secret)")
        for required_text in (
            "master",
            "automation/<topic>",
            "Project #8",
            "sample data/",
            "docs/",
            "provenance",
            "dead-letter",
        ):
            self.assertIn(required_text, contributing)
        self.assertNotRegex(
            security + contributing,
            r"(?i)(sk-[A-Za-z0-9_-]+|ghp_[A-Za-z0-9_]+|BEGIN [A-Z ]+ PRIVATE KEY)",
        )

    def test_ci_triggers_for_governance_changes(self) -> None:
        workflow = self.read(".github/workflows/autonomous-verification.yml")
        for path_pattern in (
            ".github/CODEOWNERS",
            ".github/ISSUE_TEMPLATE/**",
            ".github/PULL_REQUEST_TEMPLATE.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "scripts/dev/test_repository_governance.py",
        ):
            self.assertIn(f'"{path_pattern}"', workflow)


if __name__ == "__main__":
    unittest.main()
