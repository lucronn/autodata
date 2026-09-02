# Autonomy Gate Tooling

The scripts in this directory are deterministic controls for autonomous agent runs. They do not invoke a model, access production, or decide that an incomplete run is safe. An external orchestrator or project-scoped agent supplies the run manifest and gate reports; this tooling independently evaluates the evidence.

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
- `.autodata-autonomy-policy.json` contains merge, data-quality, retry, and protected-path policy.
- [Agent contracts](../../docs/agents/agent-contracts.md) define manifests, findings, decisions, and evidence bundles.
- [Data-integrity gates](../../docs/agents/data-integrity-gates.md) define publication and release invariants.
- [Runner interface](../../docs/agents/runner-interface.md) defines the provider-neutral invocation and output boundary.

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

The runner removes secrets from the provider environment and redacts provider logs. It also blocks `gh`, cloud/deployment CLIs, and external/destructive Git subcommands in the provider process. These controls are intentionally tested as policy behavior and must be supplemented by the deployment environment's network and credential isolation.

## Run the full local agent chain

[`orchestrator.py`](orchestrator.py) coordinates one architect, one builder, and all seven independent policy gates. It accepts a task JSON document, obtains a structured architect contract, passes that contract to the builder, pins the builder commit for downstream gate worktrees, preserves each agent response, and assembles a final manifest for `validate_run.py`.

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

[`release_controller.py`](release_controller.py) validates a complete manifest against the policy and produces an exact-SHA GitHub PR/Project/merge plan. It is read-only by default. The separate `--execute` path requires `AUTODATA_RELEASE_AUTOMATION=enabled`, a known PR number, a checked-out `HEAD` equal to the verified implementation SHA, and an isolated release-job identity. It executes structured `gh` argv only; it does not use a shell, force-push, deploy production, or rewrite published data.
