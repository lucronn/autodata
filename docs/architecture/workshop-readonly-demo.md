# Workshop read-only demonstration

The explicit `/workshop/?demo=1` entry is a separate browser bootstrap path for fictional, repository-authored sample content. A visible persistent banner says “Demo — sample content. No purchase or vehicle access is granted.” The fixture uses a fictional vehicle (“2026 Example Motors Sample”, “Demonstration trim”) and a non-procedural sample article (“Understanding this sample manual”). It contains no licensed provider article, provider identifier, service instruction, torque value or invented source citation. Its provenance says “Illustrative content authored for this demo; not supplied by Bankone or Banktwo. Not vehicle service information.”

The demo reuses Workshop markup and styles, but its module is loaded before any normal application module. The normal `app.mjs` remains the default bootstrap. The demo enables selector progression, article search, reader and back navigation entirely in browser memory. A displayed $20 USD amount is labeled “Illustrative price — checkout unavailable in demo”. Purchase, sign-in, order checks and account/library mutations are disabled. No database writes, entitlement grants, live source/canonical reads, model calls or API requests occur. Reloading `?demo=1` returns to the sample. A link to the regular Workshop exits demo mode explicitly.

Normal Workshop authentication, rights and paid-catalog enforcement retain their existing contracts. Demo mode never adds a server entitlement exception, client fake grant, Stripe fixture or seeded production customer. Static sample assets are public demonstration material.

## Inception model configuration

The coordinator verified the official provider catalog lists `mercury-3` as current/newest on 2026-11-06. `mercury-2` and `mercury-2.5` remain listed; no retirement or deprecation is claimed. Update constructor/environment and Compose defaults to `mercury-3`; explicit `INCEPTION_MODEL` overrides continue to work. The shared client sends `temperature: 0.5` for Mercury-3 (valid provider range 0.5–1) and `max_completion_tokens` with the existing `INCEPTION_MAX_TOKENS` budget. Explicit older-model overrides retain their prior compatible `temperature: 0` and `max_tokens` request shape. Historical extraction-mode/generation metadata and legacy class/module names are not renamed.

Secrets remain environment/platform managed. This change does not require or print keys, and demo mode never consumes the model client.

## Tracking and acceptance

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-06-workshop-readonly-demo.md`
Record: `docs/agents/records/2026-11-06-workshop-readonly-demo.json`

Concrete todo:
- [x] Implement an explicit fixture-only Workshop demo entry with a fictional vehicle, article search/reader/back navigation, an illustrative $20 USD quote and persistent sample-content labeling; load no live application/auth/commerce modules in demo mode.
- [x] Keep demo purchase/sign-in/library mutations disabled and make zero catalog, auth, commerce, preparation, ingestion or model requests; preserve paid routes, grants and production authentication.
- [x] Update Inception model defaults to mercury-3 and make its request temperature/token fields compatible while retaining explicit INCEPTION_MODEL overrides and historical Mercury-2 metadata.
- [x] Run focused client/Go/Python regressions and browser verification proving demo navigation and no live API requests; record exact candidate evidence, commit/push coherent milestones and synchronize Issue186/Project8.

- [ ] Securely deliver the validated current model key outside the repository, recover the verified purchase-disabled preview runtime after its restart loss, resume only the two frozen parked jobs with existing fences/budgets, and record canonical/warm-read acceptance or the exact blocker without claiming paid launch.

## Operational completion: existing preview and exactly two jobs

The coordinator verified the current local key by a tiny official Mercury-3 JSON completion (HTTP200, model mercury-3, one choice), fingerprint `07f40f8fd62b`. This is authentication/API compatibility evidence, not canonical acceptance. Deliver that validated key by private file/secure environment update only: no value in Git, chat, logs, CLI argv or GitHub. Use private0700 evidence/config directories and0600 files. Preserve all unrelated environment keys; inject `INCEPTION_MODEL=mercury-3`. Verify only fingerprint/presence, never dump environment. The demo remains static and completely independent of commerce readiness.

Freshly inspect database `autodata` at `127.0.0.1:5432`, S3 at `127.0.0.1:19000`, existing systemd API and retained private launch/inspect/source evidence. Prior preview `autodata-ingestion-preview-auto-park` no longer exists after host restart; never assume it survives. Prior source is `fc7a73ad9002bd04f821b767d0a70bdbbdfc1dca`, image `sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4`. Recover only the same preview role using inspected immutable source at the coordinator-reviewed new implementation SHA and existing image; preserve command, network, read-only/capability/security/user/resource configuration from the retained launch evidence. Preserve rollback inputs and current data; persist the existing service/restart configuration rather than another reboot. Inspect before writes; any mismatched/missing baseline input blocks recovery, and is reported without guessing runtime settings. Reuse existing exact API build/launch process for the new embedded demo assets. Do not modify source connectors, schema, payment configuration or customer grants.

Resume only:

| Bank | Canonical article | Job |
| --- | --- | --- |
| Bankone | `aad66f67-355c-5d92-ab21-b4894bca9069` | `a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d` |
| Banktwo | `8ae431dd-69b2-5f27-a696-6d64b0ff0a81` | `64888ce4-429e-4e22-9892-48d1fb4b82eb` |

Use existing `run_article_worker_once(..., job_id=exact_uuid)` with existing claim/source-generation/profile fences, as in `docs/superpowers/plans/2026-11-06-preview-automatic-rewrite-deployment.md`. Verify each current job belongs to its frozen article/source scope before invocation. Retain retry counts and model-attempt history; maximum2 model attempts/article and4 total, with no budget reset, generic worker/daemon/queue drain, new enrollment or manual retry after model/auth/integrity failure. Keep a private database backup and unchanged unrelated business/queue/source fingerprints. If either exact job is stale/missing or required services are unavailable, stop that operational step and report the exact blocker; static demo verification can still complete independently.

Require persisted automatic canonical revision with `full-prose-auto-v1`, truthful `UNREVIEWED` metadata, protected technical/table/safety/media/evidence/order retention and no manual approval row. For each published article perform ten warm reads/ensures with actual measured zero source/media/model/schedule calls and unchanged revision/content hashes; fresh-process persistence read is mandatory. A generation failure remains explicit and cannot be represented as publication. Mechanical integrity does not certify semantic equivalence. The licensed two-job canary is private operational verification and is never exposed in fixture demo content.

Verify local/public readiness200, the normal Workshop, `/workshop/?demo=1` and `purchase-config` `enabled:false` after recovery;503 is a failure, not disabled-purchase success. Keep all checkout disabled and grant/customer data unchanged. Record source/image/container/service IDs, full candidate SHA, fingerprint only, per-job attempt/model counters/revisions, measured warm-call counts and rollback evidence privately; synchronize sanitized results to the canonical doc/Issue/Project. Production paid launch, unrestricted source access, new grants and broad catalog acceptance remain outside this scope.

Fresh coordinator observation before checkpoint: `autodata-postgres-1` maps `127.0.0.1:5432`; both frozen jobs survive with `status=failed`, `phase=rewriting`, `error_code=MODEL_NOT_CONFIGURED`. No resume performed. S3 endpoint identity still requires fresh runtime verification.

## Verified implementation and live preview, 2026-11-06

The implemented and deployed source is `32373defb4237e4a9e3db59a109a4d2ccf092236` (PR #346). The private, immutable source export and offline Go API build passed byte verification and `go test ./...`. The Node Workshop client/demo suite passed 188 tests; the focused Mercury client suite passed 18 tests. Independent review found no actionable issue. Desktop and mobile Chromium checks passed selector, search, reader/back, disabled controls and persistent provenance. The demo requested exactly its five static resources and made no live API, authentication, payment or model call. The regular Workshop loaded its normal `app.mjs` path. Public `/workshop/` and `/workshop/?demo=1`, API readiness and the model service health returned 200. Public purchase configuration returned 200 with `enabled:false` after the persistent preview service was recovered. The validated model key was delivered through a private runtime environment file; only its fingerprint `07f40f8fd62b` is recorded here.

Both frozen job/source/profile/generation fences were checked before execution. Banktwo job `64888ce4-429e-4e22-9892-48d1fb4b82eb` used one Mercury-3 call and published canonical revision `563bd31d-8e07-4ccb-8549-2189fe52bd1a`, with automatic validation, `UNREVIEWED` metadata and no manual review row. Ten warm read/ensure pairs and a separate fresh-process read reused that revision; measured source, media, model, scheduling and HTTP calls were all zero, and full database fingerprints stayed unchanged. Its source has zero eligible ordinary-prose slots, so this proves automatic introduction generation, protected-structure retention and permanent reuse, not full ordinary-prose rewriting.

Bankone job `a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d` used one Mercury-3 call and ended `REWRITE_RESPONSE_INVALID` before any candidate revision or response was stored. It remains on source fallback. The retained metadata does not identify the exact parse or output-budget cause. No retry, queue drain, new enrollment, checkout enablement or customer-grant change was made. A diagnosed response handling/output-budget fix and a prose-bearing Bankone acceptance remain necessary before the dual-bank canonical rewrite goal can be claimed. Sanitized tracking: [Issue #186 comment](https://github.com/lucronn/autodata/issues/186#issuecomment-6693522651) and Project #8's dedicated demo preview field. Detailed runtime/model evidence and rollback inputs remain private outside Git.

## Bankone exact-job diagnostic recovery checkpoint

Goal: Classify Mercury-3 response failures without retaining content and permit at most one guarded recovery dispatch for the existing Bankone prose canary.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-06-bankone-diagnostic-recovery.md`
Record: `docs/agents/records/2026-11-06-bankone-diagnostic-recovery.json`
Canonical document: `docs/architecture/workshop-readonly-demo.md`
Branch: `codex/bankone-diagnostic-recovery`, starting source `0d2db0d8abdb9531627252c2f6c12ef04ceeb29d` (PR346).

Frozen scope: Bankone job `a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d`, article `aad66f67-355c-5d92-ab21-b4894bca9069`, source revision `acd11534-199a-40f7-bf94-717b34895752`, profile `full-prose-auto-v1`, 34 eligible prose slots. Existing outcome is `dead_letter` / `REWRITE_RESPONSE_INVALID`, one consumed dispatch, no candidate. Banktwo already published with one dispatch and zero ordinary-prose slots; it receives no further call. Original parse/output-budget cause remains unproven.

Maximum one additional Bankone provider dispatch, including diagnostic calls; cumulative Bankone <=2 and two-bank global <=4. Unknown delivery counts as consumed. Preserve every attempt/counter: no reset, new article/enrollment, broad worker/queue drain, fallback model, automatic second call, schema/profile/validator relaxation, checkout or grant change. For this sole recovery, pin `INCEPTION_MAX_TOKENS=32768` and `INCEPTION_API_TIMEOUT_SECONDS=60`. These bounded settings are a coordinator-approved hypothesis to accommodate 34 prose slots, not a proven diagnosis of the earlier 8192-token/20-second failure. The provider supports a higher token cap; 32768 is the existing client maximum. No separate tuning/diagnostic call and no further settings change or dispatch after failure is permitted. Never log or persist raw model body/content, prompt, licensed source, headers or exception text as diagnostics. Retain source fallback on failure.

Concrete todo:
- [ ] Add content-free Mercury-3 response diagnostics and focused parser/privacy regressions.
- [ ] Add an atomic one-use recovery claim for the frozen Bankone job with unchanged source/generation/profile fences and historical attempt budgets.
- [ ] Validate and push coherent implementation milestones; obtain exact-SHA review and required CI before coordinator deployment.
- [ ] Dispatch the frozen Bankone job at most once after fresh guards, or record its exact blocker; retain source fallback on failure.
- [ ] Verify all 34 prose slots, protected structure and permanent warm reuse on success; synchronize sanitized outcome evidence.

This is a docs-only checkpoint. The committed checkpoint must pass machine preflight at its full SHA before implementation. Runtime work follows coordinator integration/review/CI and fresh exact-job guards; this planning turn performs no provider or job call.


## Bankone recovery outcome, 2026-11-06

[PR #347](https://github.com/lucronn/autodata/pull/347) merged at
`887a8bc3a53da93b05bc8a0ab3ba84e4783779a2` after required
[CI passed](https://github.com/lucronn/autodata/actions/runs/42283387442).
The coordinator took a fresh private backup, rechecked the frozen job/source/
generation/profile fences and dispatched the sole remaining Bankone attempt
once with the approved 32768-token/60-second settings. The exact job
`a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d` ended `dead_letter`, retry count 2,
with `REWRITE_SLOT_MISMATCH`. Bankone has consumed two Mercury-3 attempts;
Banktwo retains its one successful attempt. The three cumulative two-bank
attempts do not create another Bankone allowance: its per-article limit is
exhausted. No further dispatch is authorized under this checkpoint.

Sanitized structural inspection found all 34 ordered prose-slot paths present,
but 29 rewrite rows omitted the required `reason` key. The prose comparison also
found 16 ordinary-prose slots effectively unchanged: five retain rows, nine
rewrite rows with exactly unchanged text and two rewrite rows with the same
words and punctuation-only differences. The other 18 slots were substantially
changed. Thus adding missing metadata would not make this response satisfy the
automatic full-prose requirement. It cannot be published or salvaged under the
existing `full-prose-auto-v1` validator. These counts disclose no source,
prompt, response text or secret; detailed operational evidence remains private.

Bankone remains on source fallback with no canonical publication. Banktwo's
stored revision and zero-remote warm-read result remain the limited acceptance
described above: its source has zero eligible ordinary-prose slots. Full
ordinary-prose acceptance and the dual-bank canonical rewrite goal remain
unmet. Checkout remains disabled. Any future Bankone work requires a separate
reviewed plan and authorization; this result permits no counter reset, model
retry, manual response repair, validator relaxation or publication.

Recovery todo outcome:

- [x] Add content-free response diagnostics and parser/privacy regressions.
- [x] Add the atomic one-use exact-job claim with historical attempt fences.
- [x] Obtain exact-SHA review and required CI before the guarded dispatch.
- [x] Run the one permitted recovery after a fresh backup and guards; preserve
  the failed result and source fallback.
- [x] Synchronize sanitized failure diagnostics to the canonical document,
  Issue #186 and Project #8's Bankone recovery reference.
- [ ] Achieve all-34-slot automatic full-prose acceptance, protected-structure
  retention and permanent warm reuse for Bankone; blocked by the failed
  exhausted-budget attempt, with no retry authorized by this checkpoint.

## Automatic rewrite prompt-v2 checkpoint

Goal: Make automatic ordinary-prose rewriting satisfy the existing strict response contract while preserving permanent historical canonical revisions and exact evidence binding.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-06-automatic-rewrite-prompt-v2.md`
Record: `docs/agents/records/2026-11-06-automatic-rewrite-prompt-v2.json`
Branch: `codex/automatic-rewrite-prompt-v2`; starting source `887a8bc`, with preserved PR349 outcome documentation.

The failed Bankone response revealed independent shape and uniqueness failures: all34 paths present,29 missing reason fields,16 effectively unchanged leaves. Prompt-v2 explicitly requires exactly five keys per replacement (`block_id,path,action,text,reason`), empty rewrite reason, ordinary-slot `required_action=rewrite`, and substantive rewording beyond punctuation/case/spacing. Technical-only slots may use explicit retention with a concrete reason. Preserve exact historical prompt-v1 bytes; saved-candidate validation accepts only server-reconstructed v1/v2 hashes for the same source/context, with every other binding and strict validator unchanged. Profile remains full-prose-auto-v1; this is a prompt clarification, not validator/profile relaxation or semantic certification.

Concrete todo:
- [ ] Freeze byte-identical automatic prompt-v1 and introduce prompt-v2 with exact five-key response rows, explicit empty rewrite reason and per-slot action requirements.
- [ ] Accept only exact server-reconstructed v1/v2 prompt hashes at saved automatic-candidate validation; preserve all other source/attempt/model/response bindings.
- [ ] Run focused prompt/hash/integrity regressions and actual PostgreSQL lifecycle/restart coverage; push validated milestones for independent review and required CI.
- [ ] After coordinator dispatch, use one fresh prose-bearing Bankone identity and at most one persisted provider attempt; preserve frozen-job counters and source fallback on failure.
- [ ] On publication prove all eligible prose changed, protected content retained and ten warm read/ensure pairs plus fresh-process reuse with measured zero source/media/model/schedule calls; synchronize sanitized evidence.

Frozen Bankone job a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d and its canonical identity remain exhausted and untouched; no reset/re-key/re-enrollment/salvage. Banktwo receives no further call. The future fresh identity must be an existing reachable licensed descriptor with no prior attempt/publication, distinctly fenced before one exact-job dispatch. Unknown delivery consumes the single-call allowance. Source fallback persists on failure; checkout stays disabled and grants unchanged. Planning is docs-only. Exact pinned machine preflight and coordinator assignment precede implementation; independent candidate review/CI and coordinator dispatch precede runtime canary/deployment.

### Automatic prompt-v2 implementation evidence

The automatic prompt-v2 builder preserves prompt-v1 bytes and accepts only exact server-reconstructed v1/v2 prompt hashes for saved candidates. Strict validation remains unchanged. Verification: 212 focused rewrite tests and 13 real PostgreSQL automatic publication/restart/binding tests passed. Commands and honest fixture/dependency receipts are in `docs/verification/2026-11-06-automatic-rewrite-prompt-v2.md`. No licensed provider call or runtime deployment occurred in this builder lane; the fresh-identity canary remains pending coordinator dispatch.
