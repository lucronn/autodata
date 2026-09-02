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
