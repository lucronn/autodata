# AutoData Agent Contracts

## Run manifest

Every agent run writes one JSON manifest with this shape:

```json
{
  "run_id": "uuid",
  "task_id": "github-issue-or-project-item",
  "parent_issue": 0,
  "repository": "OWNER/REPO",
  "base_sha": "40-character-sha",
  "implementation_sha": "40-character-sha-or-null",
  "agent": "autodata-data-quality-agent",
  "phase": "verifying",
  "contract_versions": {
    "api": "v1",
    "events": "v1",
    "schema": "v1",
    "policy": "1"
  },
  "changed_paths": ["path/to/file"],
  "commands_run": [
    {
      "command": "safe command without secrets",
      "exit_code": 0,
      "started_at": "UTC timestamp",
      "finished_at": "UTC timestamp",
      "output_ref": "artifact-or-log-reference"
    }
  ],
  "findings": [],
  "decision": "pass",
  "evidence": [
    {
      "kind": "test-result",
      "ref": "artifact-reference",
      "sha256": "content-hash",
      "description": "what this proves"
    }
  ],
  "gate_reports": [
    {
      "gate": "data_quality",
      "decision": "pass",
      "implementation_sha": "40-character-sha",
      "evidence": [
        {"ref": "quality.json", "sha256": "content-hash"}
      ]
    }
  ],
  "correlation_id": "uuid",
  "idempotency_key": "stable-key",
  "retry_count": 0,
  "created_at": "UTC timestamp",
  "updated_at": "UTC timestamp"
}
```

`parent_issue` may be `null` for scheduled maintenance, but `run_id`, `task_id`, `base_sha`, `agent`, `phase`, `decision`, and `evidence` are always required. `implementation_sha` is required before verification or release.

## Decision vocabulary

Agents may emit only:

- `pass`: all checks owned by the agent passed and evidence is complete.
- `fail`: a deterministic or reproducible defect exists.
- `blocked`: required input, infrastructure, or external state is unavailable.
- `needs_review`: evidence or confidence is insufficient for publication.
- `not_applicable`: the agent's gate is not relevant, with a reason.

The release controller may treat `not_applicable` as pass only when policy explicitly lists the gate as optional for the task. `fail`, `blocked`, and `needs_review` cannot be silently converted to pass.

## Finding contract

```json
{
  "finding_id": "stable-id",
  "severity": "critical|high|medium|low|info",
  "category": "schema|provenance|quality|security|reliability|contract|test",
  "path": "repository/path",
  "line": 0,
  "message": "specific reproducible finding",
  "reproduction": "command or fixture reference",
  "blocking": true,
  "resolved_by": null
}
```

Critical and high findings always block merge under the initial policy. Medium and low findings require an explicit disposition in the evidence bundle; they may not be dropped from the report.

## Task contract

Before implementation, the architect emits:

```json
{
  "task_id": "stable-task-id",
  "goal": "one measurable outcome",
  "bounded_contexts": ["api", "data-model"],
  "inputs": ["contract or source references"],
  "outputs": ["files, interfaces, or reports"],
  "acceptance_tests": ["exact behavior to prove"],
  "forbidden_scope": ["unrelated changes"],
  "compatibility": {
    "api": "preserve-or-version",
    "events": "preserve-or-version",
    "schema": "expand-migrate-contract-or-explain"
  }
}
```

Builders may not begin if the task contract has missing outputs, ambiguous acceptance, or a forbidden-scope conflict. The orchestrator must retry architecture planning or mark the task blocked.

## Capability matrix

| Capability | Orchestrator | Architect | Builder | Verifier | Release |
| --- | :---: | :---: | :---: | :---: | :---: |
| Read repository | yes | yes | yes | yes | yes |
| Write isolated branch | metadata | design | implementation | reports/fixtures | release metadata |
| Change canonical data | no | no | no | no | no |
| Create PR | no | no | no | no | yes |
| Merge PR | no | no | no | no | gate only |
| Update Project | state | no | no | no | yes |
| Deploy dev/ephemeral | no | no | no | no | yes |
| Deploy production | no | no | no | no | no |

## Evidence bundle

The release agent requires:

```text
manifest.json
task-contract.json
changed-paths.txt
deterministic-ci.json
contract-compatibility.json
schema-integrity.json
data-quality.json
security.json
reliability.json
independent-review.json
decision.json
```

Each report contains `run_id`, `implementation_sha`, `decision`, findings, commands, and evidence references. A report for another SHA is stale and cannot satisfy the current run.
