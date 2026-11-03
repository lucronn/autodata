# AutoData Agent Runner Interface

## Purpose

The project-scoped prompts define agent behavior, but a model/provider runtime must still invoke them. This document is the boundary between that runtime and the repository. A runner may use a local CLI, another agent host, or an organization-controlled service; the repository does not assume a provider-specific API.

## Invocation

The v2 runner receives an envelope referencing a committed task:

```json
{
  "run_id": "uuid",
  "task_id": "github-issue-or-project-item",
  "repository": "OWNER/REPO",
  "base_sha": "40-character-sha",
  "subject_sha": "40-character-sha",
  "task_ref": "docs/agents/tasks/committed-task.json",
  "agent_name": "autodata-architect",
  "allowed_paths": ["docs/architecture/**"],
  "deployment_target": "none",
  "execution": {
    "model": "gpt-6.1-sol",
    "reasoning_effort": "medium",
    "service_tier": "fast",
    "features": {"fast_mode": true},
    "allow_fallback": false
  }
}
```

The example contains placeholders and is not a dispatch authorization. The task
must declare `evidence_contract_version: 2`, the same `task_ref`, a synchronized
pre-implementation record, and the full `verification` contract. The strict
[schema](../../scripts/autonomy/agent-output.schema.json) defines checks,
outputs, response findings, assessments, and provenance records. Every gate has
a fixed argv/cwd/timeout/zero-exit requirement, with declared outputs written to
`AUTODATA_EVIDENCE_ROOT`. Ten response artifact IDs cover architect, builder,
and eight gates. The architect cannot replace the frozen task contract.

`trusted_base_sha` pins task, policy, registry, prompts, schema, evaluator and
fixture bytes. `subject_sha` identifies the actual candidate under inspection.
The evaluator's loaded bytes must match the trusted blobs. A builder cannot
modify protected inputs and use its modified evaluator to approve itself.

The runner must:

1. Resolve `agent_name` only through `.autodata-agent-registry.json`.
2. Load the referenced prompt from the exact commit pinned by `base_sha`.
3. Create an isolated worktree or equivalent sandbox.
4. Pass no production credentials or unrestricted tokens to the agent.
5. Enforce `allowed_paths` outside the model prompt.
6. Capture commands, exit codes, changed paths, and artifacts.
7. Write the run manifest and per-gate reports defined in [agent-contracts.md](agent-contracts.md).
8. Revalidate v2 evidence with `orchestrator.validate_evidence_bundle`, which
   recomputes artifact/command/profile/SHA validity and coverage before invoking
   the unchanged `validate_run.py` policy evaluator.

## Output

The runner writes an evidence directory containing:

```text
run-manifest.json
task-contract.json
gate-reports/
evidence/
logs/
```

The manifest must contain the exact implementation SHA. Every gate report must
contain the same SHA and verified evidence. Provider responses alone cannot
satisfy required command/artifact slots. Failure, timeout, malformed response,
and cleanup failure evidence remains in the bundle. The runner returns:

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

## Local CLI provider binding

The checked-in `scripts/autonomy/runner.py` is the first provider adapter. It invokes the installed local agent CLI in non-interactive JSON mode with an ephemeral session and a workspace-write sandbox. It does not invoke GitHub, deployment, or cloud commands from the provider process. The runner creates the worktree and removes it itself; the provider can only leave evidence in the external run directory and local commits in its isolated worktree.

Example future local execution, after replacing the placeholders with intentional values:

```bash
python3 scripts/autonomy/runner.py \
  --repo-root . \
  --envelope /path/to/task-envelope.json \
  --provider local-cli \
  --output-root /path/to/autodata-runs/<run-id>
```

The task envelope must pin the current repository `HEAD` in `base_sha`, name an agent present in `.autodata-agent-registry.json`, declare a non-empty `allowed_paths` scope, and use `none`, `ephemeral`, or `dev` according to policy. The runner rejects stale base SHAs, unknown agents, production targets, parent traversal, and scopes that do not match the task contract.

The provider receives the prompt from the exact pinned commit plus the envelope and contract reference. It is instructed to commit local changes and return a structured response. The runner records redacted stdout/stderr, the provider response, changed paths, the implementation commit SHA, and the deterministic validator decision under the run directory. A malformed response, non-zero process exit, uncommitted change, out-of-scope path, missing gate report, or stale evidence is a blocked/failing run and cannot reach release.

The command guards are defense in depth, not a substitute for an externally isolated runner. `gh`, cloud CLIs, deployment CLIs, and external/destructive Git subcommands are blocked for the provider process. Provider authentication must use an isolated automation identity configured outside the repository; common token, key, password, and credential environment variables are removed before invocation. Production credentials must never be made available to this adapter.

## Local orchestration

[`scripts/autonomy/orchestrator.py`](../../scripts/autonomy/orchestrator.py) composes the adapter into the local lifecycle. It obtains a structured contract from `autodata-architect`, runs the selected implementation builder from the original pinned base, retains the resulting implementation commit under `refs/autodata/runs/<run-id>`, and runs each policy gate plus source/provenance validation against that exact commit. It copies provider responses into a single evidence bundle and invokes the deterministic validator only after all required gate decisions have been assembled.

An orchestration run is not allowed to infer a task contract from prose, reuse a stale builder SHA, or turn a provider process exit into a gate pass. Missing contracts, missing commits, non-pass gate decisions, missing evidence, and mismatched SHAs produce a blocked run. GitHub and deployment actions remain outside this local coordinator and require a separately permissioned release controller.

## Runner safety requirements

- The runner must refuse production deployment targets because policy sets `production_deployment` to false.
- The runner must not accept a task that changes the autonomy policy and uses the changed policy to approve itself.
- The runner must not merge a SHA other than the one independently verified.
- The runner must redact secrets before writing logs or evidence.
- The runner must retain failed and blocked evidence rather than replacing it with a later pass.
- The runner must stop on disagreement after the configured alternate-reviewer retry budget.
- External provider outages must produce `blocked` or `fail`, never a synthetic `pass`.

## Verified v2 boundary and remaining certification

The v2 implementation was independently reviewed and tested at
`a7493d41be4f0c4aa93bdaaa74afa14c30d49965`; its integration is
`643b8d3fc762cfdc9b456d28a47b7a4a9cde6402`. All 66 autonomy tests passed at
both commits, and independent retained-bundle replay passed the success fixture
while blocking failed-check, unavailable-provider, and malformed-response
fixtures. These use fake provider responses and real local check processes.

Real provider certification remains blocked. Two schema compatibility repairs
passed independent review; the third bounded CLI trial at
`d437eff812b0efb0d3dbdf8388cd2f9c7916f12d` returned structured output but lacked
resolved execution metadata and used unassigned architect assessments. The
installed0.162.1 exec JSONL does not emit the mocked `session_config` event.
No builder ran and no runtime profile certification is claimed.

The independently reviewed
[app-server runtime plan](../superpowers/plans/2026-11-03-app-server-runtime-contract.md)
is synchronized for a new committed-base gate. Its concrete todo is a bounded
version-pinned adapter with actual catalog/startup/completion evidence, retained
bidirectional transcript and independent replay, explicit role/check assignments,
focused/full tests and independent exact-SHA promotion, then disposable real
trials. The resolved profile must be exactly Sol6.1, medium, priority/Fast with
no fallback. It certifies resolved request settings, not the unobserved upstream
served/billed tier. Ordinary userMessage lifecycle items must be accepted and
bound without being treated as responses.

Real adapter execution is limited to the disposable non-root fixture container
with a verified supervisor proof, authorized read-only Codex authentication,
no GitHub/bank/production credentials or integrations, and truthfully recorded
standard Docker unrestricted outbound networking. The coordinator prepares the
scratch launch; no repository launcher or host execution fallback is added.
Current source/data-quality measurement is synthetic only and cannot be relabeled
as authenticated staging or production acceptance.
