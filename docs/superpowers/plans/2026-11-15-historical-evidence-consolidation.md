# Historical Workshop evidence consolidation plan

Status: synchronized planning checkpoint; imports remain blocked until exact committed checkpoint preflight passes.
Protected base: `a82b31dc8850aa3956972928b8c720969765a972` (PR439). Planning checkpoint will be its direct descendant; machine validation uses that committed checkpoint so the plan is actually present at the validated SHA.
Issue: https://github.com/lucronn/autodata/issues/441
Project: https://github.com/users/lucronn/projects/8
Canonical verification: `docs/verification/2026-11-15-historical-evidence-consolidation.md`.
Record: `docs/agents/records/2026-11-15-historical-evidence-consolidation.json`.

Project item: `PVTI_lAHOCSJ8cc4BiQ2BzhI2DKQ`; source/dependency field records this plan and exact protected base.

## Goal and scope

Replace seven stalled documentation PRs with one current-base documentation PR containing their unique historical evidence. Preserve November6 TEST settlement/refund, November7 selector/consumer outcomes, November14 retained-reader blockers and completed public/private/canary release receipts. Runtime observations and acceptance tests belong only to their dated source checkpoints; no present service health, supplier right, real tester acceptance, usable media, or payment acceptance is inferred.

Import the25 approved paths below, plus only this task's3 planning/verification/record paths. Source JSON records stay byte-identical. Markdown may receive explicit historical/non-replayable wrappers, supersession/correction notes, and narrowly necessary path/link fixes; preserve original receipt hashes, counts, failure and recovery outcomes. Existing canonical documents receive only the source PR's additive historical sections. Do not merge source branch histories. Omit #427's3 obsolete preservation-gate documents because this new synchronized gate replaces them and none of the11 imported runtime snapshots references them.

Do not import private receipts, credentials, licensed prose/media, helpers, executable files, runtime config, source/article grants or unverified new assertions. Existing source-linked assertions are attributed historical reports, not independently rerun observations. Explicitly correct #408's inactive-YAML inference and stale current-readiness claims. Missing rights metadata is not proof of permission or prohibition. M1/M2A owned fixtures and synthetic browser/SDK/HMAC tests do not prove real Firebase, paid settlement, licensed reader/media or stable external staging.

## Exact source manifest

| PR | Source head | Path | Git blob |
| --- | --- | --- | --- |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/agents/records/2026-11-14-workshop-preview-read-only-rollout.json` | `c44bf889dbb61bc0056fc7fd6debf1f033126b28` |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/agents/records/2026-11-15-private-read-only-runtime.json` | `01e9c95c89746981404137872c5e812957748125` |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/agents/records/2026-11-15-workshop-preview-canary-5981b97.json` | `ee15bf9ef6800009a30190cff49e99dffbc71baf` |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/architecture/workshop-preview-canary-5981b97.md` | `b487ed7b06ada857e77ed047f0d27a5e87ecebb3` |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/architecture/workshop-private-read-only-runtime.md` | `6749be079320a63ee7b35df15e1e5d4630579bbf` |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/superpowers/plans/2026-11-14-private-read-only-runtime-rollout.md` | `9505748584d19a1e9b9052ac84763309a92b8c06` |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/superpowers/plans/2026-11-14-workshop-preview-read-only-rollout.md` | `08615fd569008925c8687f4a7fb0c3dc40848c04` |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/superpowers/plans/2026-11-15-workshop-preview-canary-5981b97.md` | `db9614c0d3b8d93ae0b68237613eb771c16e564f` |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/verification/2026-11-14-private-read-only-runtime-rollout.md` | `5017d98cb34cc4701478fc1ee92fa72b7fffa666` |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/verification/2026-11-14-workshop-preview-read-only-rollout.md` | `0c4e33ecc4ab5994a74f6e51709be57fb5e02dcb` |
| #427 | `b8ad80e9f0dcccdb68e809ab14f54ae0f2969776` | `docs/verification/2026-11-15-workshop-preview-canary-5981b97.md` | `6a67bbac0ef053ef66b4da6fb5d50e62e0a87b31` |
| #408 | `6037c9af34cf41e92cffd67ceaf26f65d5991a44` | `docs/superpowers/plans/2026-11-11-workshop-real-data-demo-entry.md` | `6e0b434d616bfdc2e44a81f6149ee56d7e21d5af` |
| #408 | `6037c9af34cf41e92cffd67ceaf26f65d5991a44` | `docs/verification/2026-11-14-workshop-stripe-test-readiness.md` | `2b17e71cc9cf8c6af41504824f1d3e0f4bd3fbe6` |
| #370 | `90f8ca1959f69415235fd56645598fc3313765ff` | `docs/agents/records/2026-11-07-selector-failure-ui.json` | `96884e3465e79ecaf2f92f73919f8705b2610a88` |
| #370 | `90f8ca1959f69415235fd56645598fc3313765ff` | `docs/superpowers/plans/2026-11-07-selector-failure-ui.md` | `32c35b1752c02fc906710f9f4764fe0005f24407` |
| #370 | `90f8ca1959f69415235fd56645598fc3313765ff` | `docs/verification/2026-11-07-selector-failure-ui.md` | `730f3944f1fe4c9922408d22ecd48aaa1428df6a` |
| #369 | `1c44fb50e5e957959c0ab9351d17b50a7dbf7bba` | `docs/agents/records/2026-11-07-catalog-consumer-reactivation.json` | `157e1ad82b33a73d481548e9da8e92649d37e074` |
| #369 | `1c44fb50e5e957959c0ab9351d17b50a7dbf7bba` | `docs/superpowers/plans/2026-11-07-catalog-consumer-reactivation.md` | `3c56426ae4db38ef34a55889935609cda19cb7cc` |
| #369 | `1c44fb50e5e957959c0ab9351d17b50a7dbf7bba` | `docs/verification/2026-11-07-catalog-consumer-reactivation.md` | `77e052743c6b6a8ec09937815c30698c9d808cb8` |
| #368 | `ecd5ccc53974225e85b884b421ffd7d3b3691773` | `docs/agents/records/2026-11-06-catalog-authoritative-absence.json` | `2ceb81877f0b00557d853fab138ea5c1f7dde78f` |
| #368 | `ecd5ccc53974225e85b884b421ffd7d3b3691773` | `docs/verification/2026-11-06-catalog-authoritative-absence.md` | `b4990e645e91e09ba6f5100c7c1ecbdb5b1caf8b` |
| #365 | `403c1b40f28fcd04bd68a062294228fa0cb9611a` | `docs/agents/records/2026-11-06-banktwo-selector-casing.json` | `2f573b7e52b4784ff1da8957e8be9b87f3bd7668` |
| #365 | `403c1b40f28fcd04bd68a062294228fa0cb9611a` | `docs/verification/2026-11-06-banktwo-selector-casing.md` | `9cd243d0b5e460c40d28a61ab52ba6dceec25df5` |
| #418 | `9760230e6f0939b16ac38d3b3c0135c63f29564d` | `docs/architecture/opaque-source-media-paths.md` | `95130410833bb8d295c3b919545892ae7a687217` |
| #418 | `9760230e6f0939b16ac38d3b3c0135c63f29564d` | `docs/verification/2026-11-14-workshop-retained-reader-acceptance.md` | `f90b70370d38aaaaeb08b7394b2f80e42a679978` |

## Concrete todo

- [ ] Synchronize focused plan, Issue, Project8 item/readback, canonical verification and machine record on protected a82; commit/push checkpoint and pass exact-checkpoint preflight before imports.
- [ ] Import only25 approved source paths, preserve original JSON bytes/receipt facts, archive all historical runtime language, and correct stale readiness/tunnel interpretation without claiming a fresh inspection.
- [ ] Run lightweight exact-scope/provenance/JSON/Markdown-link/chronology/redaction/whitespace checks only; no build, Docker, runtime or external provider tests. Preserve the active M2A build slot.
- [ ] Commit/push validated milestone, open one draft PR, synchronize Issue/Project with exact head/tree/gate/checks and remote CI; hold merge and all seven source PR closures for root.

## Review boundaries and replacement mapping

#427 contributes11 release/canary snapshots; #408 contributes2 readiness/plan paths; #370 contributes3 selector UI outcome paths; #369 contributes3 catalog-consumer paths; #368 contributes2 authoritative-absence paths; #365 contributes2 Banktwo selector paths; #418 contributes2 retained-reader/architecture paths. This PR replaces their documentation content after independent review and protected merge; this task closes none of them.

#348 remains a separate unresolved owner-policy draft. Customer-use/refund wording was already selected; actual privacy/retention/deletion/markets/tax/support operation facts, final publication URLs/effective date and separate publication/payment gate are not supplied by this archival task.

## Gate and delivery

Canonical rule: `docs/agents/pre-implementation-gate.md`. No implementation source changes are authorized. Root owns independent exact-head review/merge. A later protected-base change requires coordination and strict up-to-date CI; remote CI validates broader suites. Do not run local builds or start services to validate documentation. Historical plans/JSON are never replay authority. There is no DNS/Firebase/tunnel/payment/service mutation, new Checkout, refund or grant in this task.
