#!/usr/bin/env python3
"""Validate repository-native contribution and ownership contracts."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _workflow_section(text: str, header: str, indent: int) -> str:
    lines = text.splitlines()
    expected = ' ' * indent + header
    hits = [i for i, line in enumerate(lines) if line == expected]
    if len(hits) != 1:
        raise ValueError('ambiguous workflow scope')
    first = hits[0] + 1
    end = first
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line.lstrip().startswith('#'):
            level = len(line) - len(line.lstrip(' '))
            if level <= indent:
                break
        end += 1
    return '\n'.join(lines[first:end]) + '\n'

def _gce_workflow_errors(text: str) -> tuple[str, ...]:
    import json
    import shlex
    import hashlib
    errors = []
    try:
        triggers = _workflow_section(text, 'on:', 0)
        for event in ('pull_request', 'push'):
            event_text = _workflow_section(triggers, event + ':', 2)
            items = _workflow_section(event_text, 'paths:', 4)
            paths = []
            for line in items.splitlines():
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                if not line.startswith('      - "'):
                    raise ValueError('invalid path list')
                item = json.loads(line[8:])
                if type(item) is not str:
                    raise ValueError('invalid path')
                paths.append(item)
            if len(paths) != len(set(paths)) or paths.count('infra/deploy/gce/**') != 1:
                errors.append(event + '_paths')
        jobs = _workflow_section(text, 'jobs:', 0)
        job = _workflow_section(jobs, 'autonomy-policy:', 2)
        steps = _workflow_section(job, 'steps:', 4)
        try:
            step = _workflow_section(steps, '- name: Run required GCE host delivery tests', 6)
        except ValueError:
            return tuple(errors + ['gce_step'])
        if re.search(r'(?m)^        (?:if|continue-on-error):', step):
            errors.append('gce_step')
        if '        shell: bash\n' not in step:
            errors.append('gce_step')
        dependency = steps.index('      - name: Run ingestion worker tests\n')
        selected = steps.index('      - name: Run required GCE host delivery tests\n')
        compose = steps.index('      - name: Validate Compose definition\n')
        if not dependency < selected < compose:
            errors.append('gce_order')
        raw = _workflow_section(step, 'run: |', 8)
        if any(line.strip() and not line.startswith('          ') for line in raw.splitlines()):
            raise ValueError('invalid run block')
        script = '\n'.join(line[10:] for line in raw.splitlines()).rstrip('\n') + '\n'
        # Literal approved script digest; never derive the expected hash from workflow.
        if hashlib.sha256(script.encode('utf-8')).hexdigest() != 'd305124edec61fca89e86d463413305f02a8c37208538d46bbe1de6c2766a602':
            errors.append('gce_script_identity')
        identity = _workflow_section(script, 'run_gce() {', 0)
        actual = shlex.split(identity.replace('\\\n', ' '), comments=True)
        expected = ['sudo', '-n', '/usr/bin/setpriv', '--reuid=1000', '--regid=1000',
                    '--clear-groups', '/usr/bin/env', '-i', 'HOME=$gce_temp/home',
                    'TMPDIR=$gce_temp/tmp', 'PATH=/usr/bin:/bin', 'LANG=C.UTF-8', 'LC_ALL=C.UTF-8',
                    'PYTHONDONTWRITEBYTECODE=1', 'AUTODATA_REQUIRE_PURCHASE_CONFIG_DELIVERY_COMPOSE=1', '$@']
        if actual != expected:
            errors.append('gce_identity')
        last = next(line for line in reversed(script.splitlines()) if line.strip())
        if shlex.split(last, comments=True) != ['run_gce', '$gce_python', '-B', '-m', 'unittest',
                'discover', '-s', 'infra/deploy/gce', '-p', 'test_*.py', '-v']:
            errors.append('gce_required_command')
    except (ValueError, TypeError, StopIteration):
        errors.append('structure')
    return tuple(errors)


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


    def test_ci_includes_gce_in_each_event_and_required_step(self) -> None:
        workflow = self.read(".github/workflows/autonomous-verification.yml")
        self.assertEqual(_gce_workflow_errors(workflow), ())

    def test_gce_event_filter_mutations_fail(self) -> None:
        workflow = self.read(".github/workflows/autonomous-verification.yml")
        self.assertEqual(_gce_workflow_errors(workflow), ())
        pattern = '      - "infra/deploy/gce/**"\n'
        for event in ("pull_request", "push"):
            scope = _workflow_section(workflow, event + ":", 2)
            mutations = {
                "removed": scope.replace(pattern, ""),
                "comment_only": scope.replace(pattern, '      # - "infra/deploy/gce/**"\n'),
                "duplicate_path": scope.replace(pattern, pattern * 2),
                "non_list_material": scope.replace(pattern, "      unexpected: value\n"),
            }
            for name, changed in mutations.items():
                with self.subTest(event=event, mutation=name):
                    mutated = workflow.replace("  " + event + ":\n" + scope,
                                               "  " + event + ":\n" + changed, 1)
                    self.assertNotEqual(mutated, workflow)
                    self.assertTrue(set(_gce_workflow_errors(mutated)) & {event + "_paths", "structure"})
            with self.subTest(event=event, mutation="duplicate_event"):
                mutated = workflow.replace("  " + event + ":\n", ("  " + event + ":\n" + scope) * 2, 1)
                self.assertIn("structure", _gce_workflow_errors(mutated))

    def test_gce_required_step_mutations_fail(self) -> None:
        workflow = self.read(".github/workflows/autonomous-verification.yml")
        self.assertEqual(_gce_workflow_errors(workflow), ())
        header = "      - name: Run required GCE host delivery tests\n"
        body = _workflow_section(workflow, header.strip(), 6)
        step = header + body
        final = '          run_gce "$gce_python" -B -m unittest discover -s infra/deploy/gce -p \'test_*.py\' -v\n'
        changes = (
            ("deleted", step, "", "gce_step"),
            ("renamed", header, header.replace("required", "optional"), "gce_step"),
            ("duplicate", step, step * 2, "gce_step"),
            ("conditional", header, header + "        if: false\n", "gce_step"),
            ("continue", header, header + "        continue-on-error: true\n", "gce_step"),
            ("shell", "        shell: bash\n", "        shell: sh\n", "gce_step"),
            ("required_flag", "AUTODATA_REQUIRE_PURCHASE_CONFIG_DELIVERY_COMPOSE=1", "AUTODATA_REQUIRE_PURCHASE_CONFIG_DELIVERY_COMPOSE=0", "gce_identity"),
            ("uid", "--reuid=1000", "--reuid=1001", "gce_identity"),
            ("gid", "--regid=1000", "--regid=1001", "gce_identity"),
            ("groups", "--clear-groups ", "", "gce_identity"),
            ("environment", "/usr/bin/env -i", "/usr/bin/env", "gce_identity"),
            ("single_file", "-p 'test_*.py'", "-p 'test_runtime.py'", "gce_required_command"),
            ("comment_command", final, final.replace("          run_gce", "          # run_gce"), "gce_required_command"),
            ("echo_command", final, final.replace("run_gce", "echo run_gce", 1), "gce_required_command"),
            ("early_exit", final, "          exit 0\n" + final, "gce_script_identity"),
            ("false_branch", final, "          if false; then\n  " + final + "          fi\n", "gce_script_identity"),
            ("false_and", final, final.replace("run_gce", "false && run_gce", 1), "gce_script_identity"),
            ("mkdir", '          mkdir -m 700 "$gce_temp/home" "$gce_temp/tmp"\n', "", "gce_script_identity"),
            ("chown", '          sudo -n /bin/chown 1000:1000 "$gce_temp" "$gce_temp/home" "$gce_temp/tmp"\n', "", "gce_script_identity"),
            ("ownership", "/bin/chown 1000:1000", "/bin/chown 1001:1001", "gce_script_identity"),
            ("runner_traversal", '          sudo -n /bin/chmod o+x /home/runner\n', "", "gce_script_identity"),
        )
        for name, old, new, expected in changes:
            with self.subTest(mutation=name):
                self.assertIn(old, step)
                mutated = workflow.replace(step, step.replace(old, new, 1), 1)
                self.assertNotEqual(mutated, workflow)
                self.assertIn(expected, _gce_workflow_errors(mutated))
        for name, anchor in (
            ("before_dependencies", "      - name: Run ingestion worker tests\n"),
            ("after_live_compose", "  workshop-dto-browser:\n"),
        ):
            with self.subTest(mutation=name):
                mutated = workflow.replace(step, "", 1).replace(anchor, step + anchor, 1)
                self.assertIn("gce_order", _gce_workflow_errors(mutated))
        with self.subTest(mutation="other_job_only"):
            mutated = workflow.replace(step, "", 1).replace("  r3-preparation-unit:\n", "  gce-other:\n    steps:\n" + step + "\n  r3-preparation-unit:\n", 1)
            self.assertIn("gce_step", _gce_workflow_errors(mutated))


if __name__ == "__main__":
    unittest.main()
