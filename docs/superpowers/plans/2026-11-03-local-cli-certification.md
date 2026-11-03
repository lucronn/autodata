# Bounded local CLI certification

Issue: https://github.com/lucronn/autodata/issues/186  
Project: https://github.com/users/lucronn/projects/8  
Parent: [R0 evidence hardening](2026-11-03-agent-evidence-hardening.md)

## Goal

Exercise the independently verified v2 runner with the installed real Codex CLI
using only GPT-6.1 Sol, medium reasoning and Fast mode. This fixture tests agent
execution and evidence retention, not the application or a production release.
The exact task is
`docs/agents/tasks/2026-11-03-production-release/runtime-fixture.json`.

## Concrete todo

- [ ] Commit the complete v2 fixture task and pass its exact-base planning and
  verification-contract checks with the promoted evaluator.
- [ ] Make a disposable local clone with no remote, GitHub/SSH credentials,
  source-bank credentials, host configuration, or production access. Run in an
  isolated container with only the configured model authentication available;
  never print credential values or place them in image layers or evidence.
- [ ] Have the fixture builder create only
  `docs/verification/provider-runtime-fixture.txt`, containing exactly
  `AutoData runtime fixture verified.` followed by one newline, and commit it
  locally. Never integrate or push that fixture candidate.
- [ ] Run the pinned eight check definitions and ten-agent chain with a
  120-second per-provider bound and an outer 400-second experiment deadline.
  Stop on the first unavailable or incompatible profile; do not retry with
  another model, effort, or tier. Preserve requested versus observed settings.
- [ ] Inspect actual schema acceptance, sandbox write/commit behavior, retained
  command/response evidence, and structured runtime metadata. Missing or
  conflicting effective model/medium/Fast metadata blocks certification even
  when a provider returns usable JSON. Do not manufacture a session event.
- [ ] If the primary runtime is compatible, exercise interruption/timeout and
  malformed-output retention in separate bounded fault experiments. These may
  not substitute for the primary real-provider result or overwrite evidence.
- [ ] Revalidate retained evidence read-only, record actual results and missing
  checks, then remove the disposable container and authentication mount. Keep
  evidence outside the checkout. No PR, merge, release or deployment occurs.

## Trust and interpretation

The copied runner/orchestrator/preflight/validator bytes must equal the promoted
Git blobs; task changes belong to the committed planning checkpoint, never the
candidate. Only the fixture text is allowed in the builder diff. Required
source and quality checks independently execute the existing two-fact synthetic
population. Its scope stays `synthetic-regression` and cannot satisfy staging.

The configured CLI authentication may be used for this already-authorized
bounded model experiment. Missing usable authentication, unsupported requested
profile, unavailable runtime metadata, incompatible output schema, sandbox or
timeout failures are actual blocked outcomes. Direct collaboration workstreams
may continue under their separately checked plans while this certification is
blocked. The experiment grants no unattended release authority.
