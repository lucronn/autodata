# Automatic Rewrite Prompt v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Coordinator assigns implementation after the committed gate passes; this checkpoint is planning only.

**Goal:** Make automatic ordinary-prose rewriting satisfy the existing strict response contract while preserving permanent historical canonical revisions and exact evidence binding.

**Architecture:** Preserve the exact historical automatic prompt-v1 payload as a private builder. Build prompt-v2 from it with explicit output schema and per-slot action guidance; validate stored prompt hashes against only those two server-reconstructed payloads. Keep automatic profile, renderer, technical grammar and validators unchanged.

**Tech Stack:** Python ingestion worker, pytest, PostgreSQL lifecycle integration harness, Mercury-3 existing client.

**Spec:** `docs/architecture/workshop-readonly-demo.md`, section “Automatic rewrite prompt-v2 checkpoint”.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Record: `docs/agents/records/2026-11-06-automatic-rewrite-prompt-v2.json`
Starting implementation source: `887a8bc` (PR347); preserved outcome docs commit `5efb5001cf89b3565ab41916f9cb85efeb831017` (PR349).

## Global constraints and diagnosis

- Automatic profile remains `full-prose-auto-v1`, validator `full-prose-auto-validator-v1`, technical grammar `literal-technical-tokens-v1`; no schema migration, human acceptance row or new profile.
- Frozen Bankone article `aad66f67-355c-5d92-ab21-b4894bca9069` / job `a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d` is exhausted at two attempts. Never reset, mutate, re-enroll or dispatch that identity; retain all attempts and source fallback. Banktwo receives no new provider call.
- Latest response covered all34 ordered paths but29 rewrite rows omitted `reason`;16 slots were effectively unchanged (5 retain,9 exact rewrite,2 punctuation-only). These are independent shape and uniqueness failures; do not salvage or normalize a failed response.
- No strict validation relaxation: unchanged words/case/spacing/punctuation, ordinary retention, missing/extra/reordered paths, technical token changes and protected structure changes must still fail. Mechanical integrity does not establish semantic equivalence or a numeric originality percentage.
- Planning performs no implementation, provider, enrollment, runtime deployment or queue operation. Future runtime canary requires exact candidate review/CI and coordinator dispatch.
- Provider credentials/actual prompts/licensed prose/raw responses remain private. Keep checkout disabled and grants unchanged.

## Concrete todo

- [ ] Freeze byte-identical automatic prompt-v1 and introduce prompt-v2 with exact five-key response rows, explicit empty rewrite reason and per-slot action requirements.
- [ ] Accept only exact server-reconstructed v1/v2 prompt hashes at saved automatic-candidate validation; preserve all other source/attempt/model/response bindings.
- [ ] Run focused prompt/hash/integrity regressions and actual PostgreSQL lifecycle/restart coverage; push validated milestones for independent review and required CI.
- [ ] After coordinator dispatch, use one fresh prose-bearing Bankone identity and at most one persisted provider attempt; preserve frozen-job counters and source fallback on failure.
- [ ] On publication prove all eligible prose changed, protected content retained and ten warm read/ensure pairs plus fresh-process reuse with measured zero source/media/model/schedule calls; synchronize sanitized evidence.

## Task 1: Explicit automatic response contract and historical hash compatibility

**Files:**
- Modify `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite_auto.py`: prompt construction and new `_matches_auto_prompt_hash` only.
- Modify `workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py`: automatic-candidate prompt-hash comparison only.
- Test `workers/ingestion-python/tests/test_procedure_rewrite_auto.py` and `workers/ingestion-python/tests/test_article_lifecycle_integration.py`.

**Interfaces:** Existing `build_auto_prompt(document, *, context)` emits new prompt-v2; new `_build_auto_prompt_v1(document, *, context)` reproduces prior bytes; new `_matches_auto_prompt_hash(document, *, context, prompt_hash)` accepts only exact reconstructed v1/v2 SHA256 values. `automatic_candidate_validation(cur, job, candidate)` keeps its signature and every non-prompt guard.

- [ ] Add failing tests pinning the historical v1 SHA256 for a deterministic `document("Remove the cover.")`, context `{}` fixture. Compute the expected literal digest from the pinned checkpoint before edits and put it in the test. Assert the new default prompt version and exact output requirements, ordinary `required_action="rewrite"` and technical-only `required_action="rewrite_or_retain"` using the existing `_technical_only` classification.
- [ ] Add exact hash compatibility tests: v1 and v2 accept; forged hash, altered source, altered context, modified rule, missing required_action and fake version hash reject. Hash compatibility must not accept caller-supplied prompt bodies or choose a version from untrusted metadata.
- [ ] Run `PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_procedure_rewrite_auto.py -q`; observe the new assertions fail before implementation. Use the repository's available pytest runtime if system Python lacks dependencies; record its exact command.
- [ ] Move current `build_auto_prompt` body unchanged to `_build_auto_prompt_v1`. New default calls that helper, decodes JSON, sets `prompt_version="full-prose-auto-prompt-v2"`, and adds a typed response-shape example: top-level exactly `introduction` and `replacements`; each replacement exactly `block_id,path,action,text,reason`. Every rewrite uses `reason:""`; retain requires a concrete reason and exact original text only for technical-only leaves.
- [ ] Set every slot's `required_action` to `rewrite` for ordinary prose and `rewrite_or_retain` only when `_technical_only(slot["text"])` is true. Add direct rules requiring genuinely reworded ordinary text: identical wording, casing, whitespace or punctuation changes alone fail; no ordinary prose retain, skipped slot or echoed source. Preserve all inherited source-bound introduction/token/protected-content rules and stable sorted compact JSON serialization.
- [ ] Add `_matches_auto_prompt_hash` analogous to the existing full-review compatibility helper: construct v1 and v2 independently from server source/context; compare only their SHA256 digests. In `automatic_candidate_validation` replace only current single-prompt digest equality with that helper. Retain attempt/candidate prompt-hash equality, input hash, normalized source, job/source/profile/model/response and operation bindings verbatim.
- [ ] Add regression tests that v2-compliant outputs pass while missing `reason`, ordinary retain, exact rewrite, punctuation-only rewrite, case/space-only rewrite, missing/reordered/extra slots and mutated protected tokens still fail. Assert technical-only retain with concrete reason still passes. Reuse existing source/response fixtures.
- [ ] Run focused suite plus full-review and procedure rewrite tests; run `git diff --check`. Commit and promptly push this coherent prompt/compatibility milestone.

## Task 2: Persisted evidence/restart proof and reviewed runtime acceptance

**Files:**
- Extend `workers/ingestion-python/tests/test_article_lifecycle_integration.py` with persisted prompt compatibility cases using its `runtime` fixture and `automatic_runtime` helper.
- Update evidence in `docs/architecture/workshop-readonly-demo.md`; optional dedicated `docs/verification/2026-11-06-automatic-rewrite-prompt-v2.md`.

- [ ] Extend actual PostgreSQL lifecycle coverage to store valid automatic v1 evidence, then reconstruct and publish under v2 code with no additional provider call. Use deterministic fixture model output and bind original v1 prompt hash consistently in attempt/candidate; do not edit a real canonical revision. Retain an independently computed legacy literal hash fixture so helper drift cannot make a test falsely green.
- [ ] Exercise normal v2 persisted candidate publication and process-death reuse after model result commit. Tampered prompt hash, source/context, response and candidate model metadata must fail existing binding/operation checks. Reuse existing automatic restart and zero-call tests for both banks.
- [ ] Run actual PostgreSQL integration tests via the existing documented lifecycle harness, then all ingestion tests appropriate to this two-file change. Preserve exact commands, counts and failed receipts. No pass claim when tests skip for unavailable PostgreSQL; report the dependency to coordinator.
- [ ] Commit/push tests/evidence, obtain independent exact-SHA code review and required CI. Coordinator then integrates/deploys only the reviewed candidate. This planning worker does not perform that deployment.
- [ ] Before the optional licensed canary, coordinator selects an existing reachable Bankone descriptor with ordinary prose, a genuinely fresh canonical identity with no historical model attempts or publication, and a source/configuration identity distinct from frozen Bankone. Record exact article/job/source revision/profile/generation/descriptor fences privately before dispatch. Inspect all ordinary slots; prefer manageable source size without changing source content or inventing a synthetic licensed identity. If no eligible fresh descriptor exists, report blocker; do not re-key the frozen article.
- [ ] Run only that exact fresh job once through existing `run_article_worker_once(...,job_id=exact_uuid)`; persist attempt before HTTP. One provider dispatch total, including uncertain delivery; no tuning calls, retries, generic worker, scheduler daemon or queue drain. Keep inspected provider configuration unchanged from the bounded Mercury3 preview (`32768` output tokens/`60` seconds) and preserve counters. No new implementation helper/operational script is implicitly authorized.
- [ ] On failure retain explicit source fallback and exact error/counters; no salvage/repair/resubmission. On success verify persisted automatic canonical revision, `UNREVIEWED`, zero manual review rows, all ordinary slots substantively changed per strict validator, and exact technical/table/safety/media/evidence/order retention. Ten warm read/ensure pairs and separate fresh-process read must reuse revision/content hashes and produce measured zero source/media/model/schedule calls. Fingerprint frozen Bankone and unrelated queue/business state before/after; intentional fresh-identity changes are scoped explicitly.
- [ ] Verify normal Workshop/readiness200 and purchase-config200 `enabled:false`, synchronize sanitized exact-SHA outcome to canonical doc, Issue186 append-only comment and dedicated Project8 “Automatic rewrite prompt reference” field. This is bounded acceptance, not broad catalog or paid-launch readiness.

## Gate execution and handoff

Commit these docs and tracking record, push branch, and pin the full checkpoint SHA externally in Issue/Project and coordinator handoff. Run:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-06-automatic-rewrite-prompt-v2.json --base-sha FULL_CHECKPOINT_SHA
```

Expected: `{"status":"synchronized","errors":[]}`. Implementation starts only after coordinator assigns the passing exact checkpoint. Preserve all PR349 outcome text and existing Issue body/Project fields.

## Runtime-only amendment: reviewed private one-shot orchestration

This amendment explicitly permits the coordinator to stage and independently review one private one-shot orchestration script for fresh Bankone canonical candidate `8cc70d03-6794-577c-aba4-bd555996d0c9`. This narrowly supersedes the prohibition on implicitly authorized operational scripts for this exact candidate only. A distinct source_article_ref on the same known reachable 2015 GMC Terrain configuration is permitted; re-keying frozen Bankone remains forbidden.

The script may call only existing enrollment and lifecycle functions: enroll this exact fresh descriptor; perform an exact-job source-only run with model dispatch disabled and park; inspect and pin its actual job/source revision/profile/generation/descriptor fences; then invoke the existing worker for that exact job with at most one persisted model attempt. Capture private backup and before/after fingerprints, verify freshness (no prior model attempt/publication), and verify unchanged frozen Bankone/Banktwo counters and unrelated queue/business state. No generic worker/daemon/queue drain, additional candidate, model tuning/diagnostic call, retry/reset, response salvage, code/validator/schema change, checkout or grant change is authorized. Unknown delivery consumes the single-call budget. Existing Mercury3 limits32768tokens/60seconds stay unchanged.

Before any script execution, independently review the exact private script bytes/hash against these guards, the reviewed integrated PR350 candidate and existing source-only park mechanism. Record the script hash and review result privately; coordinator verifies the amended full-SHA preflight and dispatches only the reviewed bytes. Stop on any unavailable or mismatched guard rather than improvise. This amendment itself performs no source/model/runtime call.

Concrete todo for the runtime-only amendment:
- [ ] Stage the private one-shot script using only the existing exact-candidate enrollment/source-only park/worker functions, backup and fingerprint guards; independently review its exact bytes/hash before execution.
- [ ] After reviewed PR350 integration/CI and coordinator dispatch, source-only park the exact fresh candidate, pin actual persisted fences, and permit at most one persisted exact-job model dispatch with no retry.
- [ ] On success prove strict all-prose/protected-content publication plus ten warm read/ensure pairs and fresh-process reuse with measured zero source/media/model/schedule calls; on failure retain source fallback and consumed budget.
- [ ] Verify checkout disabled, frozen identities and unrelated business/queue fingerprints unchanged; synchronize sanitized outcome while private source, credentials and raw responses stay outside Git.

## Runtime-only amendment: durable exact-job attempt cap

After source-only park and before any model dispatch, the independently reviewed private script is explicitly authorized to execute one transactional exact-row SQL update setting only `source_fetch_jobs.max_attempts=1` for the actual parked job of Bankone candidate `8cc70d03-6794-577c-aba4-bd555996d0c9`. This is a reduction from the inspected default3, never a retry counter reset. Require exactly one returned row; assert the stored cap is1 before model dispatch.

The UPDATE must predicate on the exact pinned job ID/article ID/source revision/request generation/profile/normalization version/lease token/normalized hash and current canonical-article fences; parked status `failed`, error `MODEL_NOT_CONFIGURED`, no live lease, retry_count1, max_attempts3, awaiting-model checkpoint and zero rewrite attempts/publications. Lock/read and recheck the same job/article in the transaction. Preserve retry_count, attempt history, source/checkpoint, lease, profile, generation, business/queue state and every other field; if any precondition or affected-row count differs, stop with no dispatch and no reset/alternate update. Persist and read back the cap before the exact worker call.

Existing configuration-resume logic does not increment retry_count, so the parked count1 plus cap1 allows its sole model call and blocks ordinary lease-expiry reclaim afterward. Script review must verify this behavior at the exact deployed implementation SHA, including exhausted-lease dead-letter and unknown-delivery handling; no application/validator change is authorized. Retain the independent private script bytes/hash review before execution, single persisted provider attempt, no retry, backup/fingerprints and strict/warm0 proof from the previous amendment. Frozen jobs remain untouched. This planning amendment performs no runtime SQL/source/model call.

Concrete todo:
- [ ] Include and independently review the guarded exact-row max_attempts3-to1 reduction after source-only park and before dispatch; verify count1 remains unchanged, exact affected row and committed cap readback.
- [ ] Verify existing claim/recovery semantics at the deployed SHA prevent a second provider attempt after process death/lease expiry; stop on any mismatch, preserving no-retry and all earlier runtime guards.
