# AutoData Agent Runner Interface

## Purpose

The project-scoped prompts define agent behavior, but a model/provider runtime must still invoke them. This document is the boundary between that runtime and the repository. A runner may be Codex, another agent host, or an organization-controlled service; the repository does not assume a provider-specific API.

## Invocation

The runner receives a task envelope:

```json
{
  "run_id": "uuid",
  "task_id": "github-issue-or-project-item",
  "repository": "OWNER/REPO",
  "base_sha": "40-character-sha",
  "agent_name": "autodata-architect",
  "task_contract_ref": "artifact-or-path",
  "allowed_paths": ["docs/architecture/**"],
  "deployment_target": "none|ephemeral|dev"
}
```

The runner must:

1. Resolve `agent_name` only through `.autodata-agent-registry.json`.
2. Load the referenced prompt from the exact commit pinned by `base_sha`.
3. Create an isolated worktree or equivalent sandbox.
4. Pass no production credentials or unrestricted tokens to the agent.
5. Enforce `allowed_paths` outside the model prompt.
6. Capture commands, exit codes, changed paths, and artifacts.
7. Write the run manifest and per-gate reports defined in [agent-contracts.md](agent-contracts.md).
8. Invoke `scripts/autonomy/validate_run.py` before returning a successful release decision.

## Output

The runner writes an evidence directory containing:

```text
run-manifest.json
task-contract.json
gate-reports/
evidence/
logs/
```

The manifest must contain the exact implementation SHA. Every gate report must contain the same SHA and at least one content-hashed evidence artifact. The runner returns:

| Exit code | Meaning |
| ---: | --- |
| 0 | Policy decision passed; release controller may continue |
| 10 | Safe block due to missing input, disagreement, or unavailable infrastructure |
| 20 | Deterministic or policy failure; remediation is required |
| 30 | Runner configuration or contract error |

Only exit code `0` may reach the release controller. A runner process that crashes, times out, or emits malformed JSON is a failure, not a pass.

## GitHub integration

The external runner may be invoked by a GitHub Actions job after a task receives the `autonomous:ready` label or an authorized workflow dispatch. The job must pass the repository SHA and task ID, upload the evidence bundle, and expose the run ID in the PR and Project item. The release controller then calls the deterministic validator and uses the exact head SHA for merge.

The repository's `autonomous-verification.yml` workflow validates the deterministic policy tool and synthetic evidence fixture. It does not pretend to invoke an agent provider. A provider binding is complete only when the runner contract above is implemented, its permissions are tested, and a real fixture task completes end to end.

## Runner safety requirements

- The runner must refuse production deployment targets because policy sets `production_deployment` to false.
- The runner must not accept a task that changes the autonomy policy and uses the changed policy to approve itself.
- The runner must not merge a SHA other than the one independently verified.
- The runner must redact secrets before writing logs or evidence.
- The runner must retain failed and blocked evidence rather than replacing it with a later pass.
- The runner must stop on disagreement after the configured alternate-reviewer retry budget.
- External provider outages must produce `blocked` or `fail`, never a synthetic `pass`.
