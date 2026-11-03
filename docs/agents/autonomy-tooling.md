# Autonomy Gate Tooling

The scripts in `scripts/autonomy/` are deterministic controls for autonomous agent runs. They do not invoke a model, access production, or decide that an incomplete run is safe. An external orchestrator or project-scoped agent supplies the run manifest and gate reports; this tooling independently evaluates the evidence.

## Validate a run

```bash
python3 scripts/autonomy/validate_run.py \
  --manifest path/to/run-manifest.json \
  --policy .autodata-autonomy-policy.json \
  --evidence-root path/to/evidence \
  --json
```

Exit code `0` means the policy passed. Exit code `1` means the manifest or evidence failed a gate. Input/JSON errors also return non-zero and are included in the JSON decision. When `--evidence-root` is supplied, every referenced artifact must remain inside that root and its SHA-256 must match the manifest. The validator checks required fields, SHA format, required gate decisions, per-gate evidence, gate-report SHA pinning, finding limits, evidence completeness, and fast-lane provenance coverage.

## Run the tests

```bash
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v
```

The checked-in `fixtures/pass.json` is a synthetic policy fixture only. It contains no real source data, credentials, or provider response. It proves validator behavior and is not evidence that an application task has passed.

## Agent registry and policy

- `.autodata-agent-registry.json` is the machine-readable roster and capability matrix.
- `.autodata-autonomy-policy.json` contains merge, data-quality, retry, documentation, and protected-path policy.
- [Agent contracts](agent-contracts.md) define manifests, findings, decisions, and evidence bundles.
- [Data-integrity gates](data-integrity-gates.md) define publication and release invariants.
- [Runner interface](runner-interface.md) defines the provider-neutral invocation and output boundary.
- [Documentation and Project source-of-truth policy](../github/operating-model.md#documentation-source-of-truth) defines where normative documents live and how Project items link to them.

The registry and policy are protected inputs. A task cannot modify them and then use the modified policy to approve itself in the same run; policy changes require their own independently verified change.

## Invoke one local agent

The local CLI adapter is deliberately one-agent-at-a-time. An external orchestrator supplies the task envelope, assigns isolated worktrees, invokes the architect/builder/verifier agents in order, and assembles the complete gate bundle before release. The local coordinator runs the seven policy gates plus the dedicated source/provenance gate. The adapter does not create GitHub resources, push branches, merge pull requests, deploy production, or treat a provider response as a release decision.

```bash
python3 scripts/autonomy/runner.py \
  --repo-root . \
  --envelope /path/to/task-envelope.json \
  --provider local-cli \
  --output-root /path/to/autodata-runs/<run-id>
```

The envelope must pin `base_sha` to the current `HEAD`. Use a unique output directory because the runner refuses to overwrite an existing evidence bundle. Exit `0` is reserved for a complete policy pass; `20` means the provider ran but deterministic validation failed; `30` means runner configuration/execution failed. The resulting `run-manifest.json` and `decision.json` are the source of truth for the caller.

The runner removes secrets from the provider environment and redacts provider logs. It also blocks `gh`, cloud/deployment CLIs, and external/destructive Git subcommands in the provider process. Documents changed by an agent must remain under `docs/`; a document created elsewhere is a critical scope violation. These controls are intentionally tested as policy behavior and must be supplemented by the deployment environment's network and credential isolation.

## Run the full local agent chain

[`orchestrator.py`](../../scripts/autonomy/orchestrator.py) coordinates one architect, one builder, and all independent policy gates. It accepts a task JSON document, obtains a structured architect contract, passes that contract to the builder, pins the builder commit for downstream gate worktrees, preserves each agent response, and assembles a final manifest for `validate_run.py`.

The task document must contain `task_id`, `goal`, `builder_agent`, `allowed_paths`, `bounded_contexts`, `inputs`, `outputs`, `acceptance_tests`, `forbidden_scope`, and `compatibility`. `run_id`, `repository`, and `deployment_target` are optional; the orchestrator supplies a unique run ID and always uses `none` for this local chain. Example command:

```bash
python3 scripts/autonomy/orchestrator.py \
  --repo-root . \
  --task /path/to/task.json \
  --provider local-cli \
  --output-root /path/to/autodata-runs/<run-id>
```

The chain is fail-closed. Architect output must contain a complete task contract; builders must create a local implementation commit; every gate must return `pass`; all gate reports must reference the same implementation SHA; and the final deterministic validator must pass. This coordinator never creates a PR, updates a GitHub Project, merges, pushes, or deploys. Those actions remain a separately permissioned release-controller step.

## Release transition

[`release_controller.py`](../../scripts/autonomy/release_controller.py) validates a complete manifest against the policy and produces an exact-SHA GitHub PR/Project/merge plan. It is read-only by default. The separate `--execute` path requires `AUTODATA_RELEASE_AUTOMATION=enabled`, a known PR number, a checked-out `HEAD` equal to the verified implementation SHA, and an isolated release-job identity. It executes structured GitHub CLI arguments only; it does not use a shell, force-push, deploy production, or rewrite published data.


## Dual-bank release campaign (2026-11-03)

The current campaign is defined by the
[release design](../superpowers/specs/2026-11-03-production-release-orchestration-design.md)
and [delivery plan](../superpowers/plans/2026-11-03-production-release-orchestration.md).
Its machine queue is
[`tasks/2026-11-03-production-release/queue.json`](tasks/2026-11-03-production-release/queue.json).
It reuses the existing registry and coordinator; the queue is a dispatch index,
not a second architectural contract or an automatically running scheduler.

The user requires `gpt-6.1-sol`, medium reasoning and Fast mode for every agent
after planning. Each task records the same execution profile. The local CLI
binding must pass the model, reasoning and service tier explicitly because it
uses `--ignore-user-config`. R0 adds and verifies that enforcement. The legacy
runner does not yet consume the new execution-profile field; setting the field
alone is not evidence that a provider ran with it. In the current host's
collaboration tools, GPT-6.1 Sol advertises the priority tier corresponding to
Fast mode; dispatch must also explicitly set medium reasoning.

The release is tracked in [Issue #186](https://github.com/lucronn/autodata/issues/186)
and Project #8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`. R0 evidence is the first
ready task; dependent records stay blocked until their verified dependencies and
new exact-base checkpoint are ready. The
[planning record](records/2026-11-03-production-release-orchestration.json)
and task-specific record must pass preflight at the actual committed base before
a builder starts. Do not copy a historical synchronized record to bypass this.
R1 intake may run alongside R0 through direct coordinator dispatch after its
separate synchronized checkpoint passes preflight. Their implementation paths
are disjoint. The coordinator verifies protected migrations through isolated
real-database clean/upgrade/concurrency tests and independent exact-SHA review;
the normal runner's protected-path refusal is not disabled. This mode cannot
grant local-runner or release authority before R0 is independently verified.

Dispatch sequence:

1. Verify the real Issue/Project references and reviewed task scope; update the
   task's inline planning record and the canonical record together.
2. Commit the planning checkpoint and pin that actual SHA. Run
   `pre_implementation.py` against the committed record. An expected failure
   during planning remains a failure and cannot authorize implementation.
3. Check queue dependencies against independently verified implementation
   commits. The legacy `orchestrator.py` handles one task and does not enforce
   this campaign's dependency graph. The coordinator owns that check.
4. Dispatch at most three builders in isolated worktrees with explicit file
   ownership. Re-pin dependent tasks after integration. Shared migrations and
   API contracts have one writer at a time.
5. Once R0 supports the execution profile and measured evidence, a configured
   isolated local CLI identity can run each complete task with
   `orchestrator.py --task <task-file> --provider local-cli --output-root
   <unique-external-run-directory>`. Missing profile availability is blocked;
   no silent model or tier fallback is allowed.
6. Record actual commands, artifacts, implementation SHA and independent
   reviews. R6 cannot substitute fixture results for authenticated staging,
   browser, concurrency, migration, build, scan or recovery evidence.

No production deployment is performed by this campaign's local orchestration.
The existing policy's deployment boundary remains in force.
