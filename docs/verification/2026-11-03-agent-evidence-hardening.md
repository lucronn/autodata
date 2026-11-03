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

Real CLI runtime validation is **blocked / invalid_json_schema**. The first
isolated experiment used the complete v2 task at
`3634a59cea79dc3d36f1ec610b927ab74e6d166a`, installed CLI `0.162.1`, explicit
Sol 6.1 / medium / Fast flags, a 120-second provider bound and a 400-second outer
deadline. The API rejected `uniqueItems` in the output schema with HTTP 400.
The provider exited 1 after 4.4 seconds; orchestration returned 20 and retained
the architect command/stdout plus its blocked decision. No builder was invoked,
no fixture commit was created, and effective runtime metadata was absent.

Evidence is retained at `/tmp/autodata-cli-3634-8weuyq91/evidence/run`; the
sanitized architect stdout SHA-256 is
`dfa7ea6e02fcfa92cdcb233570126198cce5689bbf4e2ad45882fa5bf1ec03e2`.
The container was disposable and mounted only the isolated clone/evidence,
installed CLI package and model authentication; no host configuration,
GitHub/SSH credentials or source-bank/production secrets were supplied.

The [bounded schema repair](../superpowers/plans/2026-11-03-provider-schema-compatibility.md)
passed independent exact-SHA review at
`e90047f2d50829ae0bcdc68c0dc8ed69c998cb4a` and 71 autonomy tests in 11.902 seconds.
The coordinator independently confirmed exactly eight `uniqueItems` removals,
all other schema values unchanged, and the two-file allowed scope. Duplicate
rejection remains enforced by deterministic validators with regressions.
The command log is `/tmp/autodata-r0-schema-independent-e900-tests.log`.
The second isolated runtime experiment at that exact commit passed preflight,
then received HTTP 400 `invalid_json_schema`: regex lookaround is unsupported
at `$defs.Finding.properties.path.pattern`. The architect exited 1 after
3.43 seconds; orchestration returned 20. No builder ran and effective execution
metadata was absent. Retained evidence:
`/tmp/autodata-cli-e900-lw_pbv12/evidence/run`; sanitized stdout SHA-256:
`32a44a77d933e1df352a2643036619ca9436722f5d7f9aefa2c3cd850d35d2ae`.
The same strict isolation, profile, and time bounds applied. A preparation-only
import error was corrected before this provider run; the first failed experiment
was preserved. Path-schema compatibility needs a separate reviewed checkpoint;
deterministic path validation must remain enforced. Effective model/medium/Fast
settings, sandbox writes, commit retention and interrupted-provider behavior
remain unverified.
No release, staging, deployment or live-provider certification is claimed.

The [bounded runtime experiment plan](../superpowers/plans/2026-11-03-local-cli-certification.md)
and complete
[v2 fixture task](../agents/tasks/2026-11-03-production-release/runtime-fixture.json)
were independently checked for exact scope, real command definitions, all
required agent responses, synthetic labeling, and profile constraints before
execution. The committed-base planning and complete verification-contract
checks passed with zero errors at `3634a59cea79dc3d36f1ec610b927ab74e6d166a`.
The evaluator bytes were checked equal to the independently promoted integration.
Document/preflight success did not certify the provider, as the real API rejection
above demonstrates.

R0 release-controller implementation may consume the independently verified
validator interface through a freshly synchronized direct-dispatch checkpoint.
Its own tests and review remain required. R6 requires its separately verified
staging adapter and real application acceptance evidence.

The separate [path-schema repair](../superpowers/plans/2026-11-03-provider-path-schema-compatibility.md)
passed independent exact-SHA review and coordinator verification at
`d437eff812b0efb0d3dbdf8388cd2f9c7916f12d`: **107 autonomy tests passed** in
14.789 seconds. Only seven unsupported lookaround patterns were removed; all
other parsed schema values are unchanged. Actual finding/artifact/command/
verification/trusted-input path checks remain enforced, including real unusual
filenames and committed planning blobs. The candidate was promoted unchanged
by fast-forward. Log: `/tmp/autodata-r0-path-schema-independent-d437-tests.log`.
The third bounded real CLI fixture at this exact checkpoint passed preflight
and schema acceptance. The provider exited 0 after 40.43 seconds with a retained
structured response, but orchestration returned 20: effective execution metadata
was absent, and the architect supplied six unassigned assessments instead of
its assigned empty set. No builder ran. Evidence:
`/tmp/autodata-cli-d437-ti73fxjo/evidence/run`; stdout SHA-256
`94bd830ac45ee197894716da650d0a1012976dc221883320aa5daa9c2e726051`, response SHA-256
`4e9e3393f68ab71fdcf5945a79abff9151cf6c4e73df17ebcae1e7ac97b91d20`.
A read-only audit of official CLI0.162.1 source confirms exec JSONL does not emit
`session_config`; its actual app-server startup response carries resolved runtime
settings. The [adapter/prompt plan](../superpowers/plans/2026-11-03-app-server-runtime-contract.md)
has passed independent design review and is synchronized for a fresh committed-base
gate. Its todo covers the bounded adapter, transcript replay, exact assessment
assignments, independent code verification and only then disposable real trials. Nothing
in this run certifies runtime profile, sandbox writes, builder commit retention
or release readiness. Resolved runtime Fast configuration must not be presented
as proof of the upstream tier actually served.
