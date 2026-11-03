# Agent evidence hardening verification

Issue: https://github.com/lucronn/autodata/issues/186  
Project: https://github.com/users/lucronn/projects/8  
Plan: [evidence hardening](../superpowers/plans/2026-11-03-agent-evidence-hardening.md)

The bounded R0 implementation passed independent deterministic acceptance.
Builder candidate: `a7493d41be4f0c4aa93bdaaa74afa14c30d49965`.
Integration: `643b8d3fc762cfdc9b456d28a47b7a4a9cde6402`.
The independent reviewer approved the final exact-SHA delta after the reported
decision-validation and evidence-retention findings were fixed.

The coordinator ran the full autonomy suite in a separate clean verification
worktree at the candidate, then at the integration commit:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/autonomy/validate_run.py --manifest scripts/autonomy/fixtures/pass.json --policy .autodata-autonomy-policy.json --json
git diff --check d09ef282c3756efd78bac112236660bff4471dad..HEAD
```

Results: **66 tests passed** at the candidate (11.975 seconds) and integration
(11.917 seconds). The legacy synthetic validator fixture passed with no
failures. Whitespace and the nine-file allowed scope checks passed. Policy,
registry, historical verifier, and protected repository rules were unchanged.

The coordinator independently replayed the final pinned samples with the
candidate evaluator:

| Sample | Actual result | Evidence coverage | Synthetic provenance |
| --- | --- | --- | --- |
| Success | pass | 95/95 | 2/2 |
| Failed required check | blocked | 95/95 | 2/2 |
| Provider unavailable | blocked | 94/95 | 2/2 |
| Malformed provider response | blocked | 95/95 | 2/2 |

Samples are retained locally at
`/tmp/autodata-r0-final-v2-bundles-jstp1qqs`, including `sample-index.json` and
`revalidate.py`. Independent command logs are
`/tmp/autodata-r0-independent-a7493d4-tests.log` and
`/tmp/autodata-r0-integrated-tests.log`. These fixtures use fake provider
responses with real local check processes; they are not source-bank canaries
or actual model executions. Full-chain regressions are reproducible from
`scripts/autonomy/test_orchestrator.py`.

Real CLI runtime validation remains **blocked / not_executed**. Profile flags,
schema support, sandbox writes, commit retention and provider interruption must
still be exercised with an isolated nonproduction identity and a complete
committed v2 fixture task. Effective model/medium/Fast metadata is required;
mocked session events do not establish installed CLI or account compatibility.
No release, staging, deployment or live-provider certification is claimed.

The [bounded runtime experiment plan](../superpowers/plans/2026-11-03-local-cli-certification.md)
and complete
[v2 fixture task](../agents/tasks/2026-11-03-production-release/runtime-fixture.json)
were independently checked for exact scope, real command definitions, all
required agent responses, synthetic labeling, and profile constraints before
execution. Their committed-base preflight and actual runtime result remain
separate evidence; document review does not certify the provider.

R0 release-controller implementation may consume the independently verified
validator interface through a freshly synchronized direct-dispatch checkpoint.
Its own tests and review remain required. R6 requires its separately verified
staging adapter and real application acceptance evidence.
