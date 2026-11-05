# Article rewrite v2 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task after exact committed-base preflight and coordinator dispatch. Keep coherent validated milestones small and push promptly.

**Goal:** Improve meaningful source-bound article rewriting through immutable technical-prose-v2, preserving complete technical instructions, consistent ordered-document display, and readable source fallback.

**Architecture:** Keep provider-scoped article identities and ordered-article-v1 documents. Add an immutable technical-prose-v2 grammar profile: source parsing creates a finite set of complete-clause transformations; the model selects only bound operation identifiers; the server renders and independently recomputes every accepted result. Retain unsupported articles as readable source pending remediation.

**Tech Stack:** Existing Python ingestion worker, PostgreSQL durable attempts/leases/outbox, ordered-document API/Workshop projection and existing Mercury transport. No new runtime dependencies.

**Spec:** docs/architecture/normalized-article-document.md, “Meaningful article rewrite v2” below.

Issue: https://github.com/lucronn/autodata/issues/300
Parent: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Project item: PVTI_lAHOCSJ8cc4BiQ2BzhGN8dM
Source baseline: `38b53eca633eee94f045fc33d9c90bb36da7618d`.
Branch: `codex/article-rewrite-v2-gate`.

## Global constraints and honest release boundary

- Planning only in this checkpoint: no implementation, provider call, activation or deployment. Implementers use GPT-6.1 Sol, medium, priority as requested. Exact committed checkpoint SHA is pinned externally after commit; run the canonical preflight against that SHA before edits.
- User outcome remains uniquely rewritten consistent-format content once for purchased datasets. A larger supported subset alone does not satisfy that outcome. Cross-bank combination is unresolved and excluded here; never join or substitute bank items by title or content hash.
- v1 is immutable and still validates existing v1 jobs/revisions. Profile, validator, grammar and rendering rules are versioned together. A new v2 target requires explicit refresh through the existing source-job version path; no bulk requeue, SQL-default migration or rewrite-on-read.
- Preserve warning/caution/note blocks, negation, modality, conditions/applicability, technical values/units, components, tools, references, source evidence, block IDs/order/nesting, tables and local asset placement. No arbitrary model prose, number/keyword-only comparison or model-judge approval.
- Retain UNREVIEWED as distinct human-review status. Publication requires deterministic validation; release acceptance additionally requires the independent content review below. Neither alone proves universal semantic equivalence.
- The current API and Workshop ordered renderer already provide consistent structure, same-origin media, source fallback and atomic source-to-current-canonical selection. Reuse these paths without UI, schema, entitlement or rendering changes.

## Concrete todo

- [ ] Freeze representative full-document corpus and baseline coverage, with provenance and unsupported cases.
- [ ] Implement source-bound complete-clause operations and server rendering with exact technical span preservation and fail-closed validation.
- [ ] Route immutable v1/v2 profiles through durable attempts, validation, publication and explicit refresh.
- [ ] Verify corpus meaning, source fallback, dual-bank isolation, concurrency, restart and zero-call warm reads; publish exact coverage and independent review.

## Task 1: Freeze the denominator before grammar tuning

**Files:** create `workers/ingestion-python/tests/fixtures/article_rewrite_v2.json`, `workers/ingestion-python/tests/test_procedure_rewrite_v2.py`; create verification document in the allowlist.

- [ ] Inventory authorized retained captures without provider requests. Freeze at least 40 complete normalized documents (20 per bank), selected by stable source identity/hash rather than rewrite eligibility, spanning multiple vehicle configurations and procedure families. Preserve private raw evidence externally; commit only authorized sanitized content and reproducible source hashes/selection manifest. If retained captures or redistribution rights are unavailable, record that blocker and use synthetic regressions for development only; synthetic fixtures never count as realistic corpus acceptance.
- [ ] Separately freeze adversarial fixtures covering numbers/units, ambiguous noun phrases, coordinated actions, conditional and negative instructions, declarative paragraphs, warnings, nested lists, tables and interleaved/unavailable images. Include v1-ineligible verbs and documents with no Remove/Install/Discard opening. Do not shorten real articles into easy isolated sentences.
- [ ] Run v1 through the existing rewrite boundary with an offline fixture selector; record exact denominator, article/clause support and changed-clause coverage by bank and document family, failure reasons, and actual block/evidence retention. Freeze a held-out half per bank before tuning; record hashes and all exclusions.
- [ ] Add intended failing cases for complete-clause v2 rendering and byte-preserving technical spans. The baseline must reject an unsupported v2 profile, so the first red is specifically missing v2 behavior rather than missing dependencies.

## Task 2: Source-bound grammar and server rendering

**Files:** new `procedure_rewrite_v2.py`; modify `procedure_rewrite.py`; tests and corpus above.

Expose `plan_v2(document) -> dict`, `build_v2_prompt(document, *, context) -> str`, `render_v2(document, response) -> dict`, and `validate_v2(source, candidate) -> ValidationResult`. Plan contains profile/grammar version, source hash, stable leaf path/block ID, source span offsets, operation ID, and classification of each prose leaf. All offsets address exact original Unicode text; no Unicode normalization of technical spans.

- [ ] Implement a deterministic, full-match parser for single positive transitive imperative clauses. Initial finite verbs: remove/removed, install/installed, disconnect/disconnected, connect/connected, loosen/loosened, tighten/tightened, replace/replaced, inspect/inspected, clean/cleaned, lubricate/lubricated. Do not blindly synonymize verbs. Parse a bounded noun phrase and explicit allowed adjuncts, not a greedy “remainder” that can hide another action or change attachment. Start with definite article + finite reviewed component/modifier vocabulary derived from the frozen training half; unknown vocabulary is unsupported, not guessed. Reject pronoun objects, ambiguous attachment, coordination, infinitives, nested clauses, quotes, newlines and extra sentences. No runtime model classification can authorize grammar.
- [ ] Render full procedural directives using only source spans plus a reviewed template: `Remove the cover.` becomes `The cover is to be removed.`; `Tighten the bolts to 25 Nm.` becomes `The bolts are to be tightened to 25 Nm.`. Number agreement is explicit in the reviewed noun dictionary. The determiner case change is an explicit nontechnical template operation; the remaining object text and complete technical adjunct stay byte-identical. The sole initial technical adjunct is `to <number><space><approved unit>` for tighten, with decimal/range grammar `[-+]?digits([.]digits)?` with optional `–` separated second number and units exactly `Nm`, `N·m`, `N m`, `lb-ft`, `lb-in` (source spelling unchanged); unsupported conversions, alternate unit spelling or free trailing prose fail closed. Preserve all other technical/safety clauses verbatim. Add further templates only with a new failing fidelity test and review; do not expand grammar based solely on a coverage target.
- [ ] Response shape is only `{"operations":[{"block_id":"...","path":"...","operation_id":"..."}]}` in plan order, exactly once per planned clause. Server binds choices to source hash, span and grammar version and renders output itself. Reject unknown/duplicate/missing/reordered operations and any supplied text or extra keys. No echoed source, heading changes, wrappers, whitespace-only changes or opening-verb synonyms count as meaningful rewriting.
- [ ] Walk only actual prose leaves in paragraphs/steps and nested list text. Preserve every other document member exactly; warn/note/callout/table/link/unknown/title/alt text is not a mutable prose slot. Classify ordinary prose that is not safely parsed as unsupported, distinguishing it from intentionally verbatim technical/safety content. Unsupported ordinary prose means whole-article source fallback in this bounded v2, with explicit reason and no false complete-rewrite flag. For eligible articles transform every eligible clause, not one token in one block.
- [ ] Validate by reconstructing the deterministic allowed candidate from the original source and operation set, comparing the complete document, and recomputing source/protected/skeleton/candidate hashes and evidence bindings. Report grammar version, changed clauses, retained protected clauses, unsupported paths/reasons and counts. Reject changed tool/part names, negation, numeric digits, comparator/range signs, units, clause order, adjunct attachment, source paths, evidence and media. Existing strict ordered-document validation remains mandatory. Limits remain 200 KiB prompt and 1 MiB response; unsupported/oversized documents make no model call.

## Task 3: Immutable profile routing through the durable worker

**Files:** `procedure_rewrite.py`, `article_lifecycle.py`, `article_lifecycle_types.py`, `article_lifecycle_store.py`, existing transform/worker/publication/types/integration tests.

- [ ] Keep `REWRITE_PROFILE_VERSION` default v1; introduce explicit supported v2 routing. `editable_slots`, prompt building, rewriting and validation dispatch by the lease profile, retaining v1 exact behavior and original validator identifiers. Do not infer v2 from latest code or modify historical stored reports.
- [ ] The v2 worker checks v2 eligibility before dispatch. Existing prepare/dispatch/store lifecycle records the bound v2 prompt, profile and operation response; preserve the existing Mercury provider/model metadata and attempt ownership. Invalid/unsupported plans persist an explicit nonretryable reason and remain source-readable. Transport ambiguity and retries retain the existing bounded durable accounting.
- [ ] Recompute v2 validation in both store_validation and publish_article_revision under the existing locks. Preserve normalized-source/result/projection/attempt hash checks and atomic revision/pointer/job/outbox transaction. Report additions live in existing JSON fields; no migration or contract expansion is authorized.
- [ ] Test explicit existing `refresh_article_job(..., rewrite_profile_version="technical-prose-v2")` with source unchanged: distinct transformation key and immutable v1 revision, one winner/event, and saved-result recovery without another model request. Same-profile/source refresh reuses completed/exhausted owner and budget. Test v1/v2 coexistence, forged reports, changed source and stale generation/lease rejection.

## Task 4: Corpus acceptance, recovery and review

- [ ] Run focused pure tests, then the existing dedicated PostgreSQL lifecycle harness (not a production database), preserving intended red and final exact-SHA evidence. Example focused command: `PYTHONPATH=workers/ingestion-python/src pytest workers/ingestion-python/tests/test_procedure_rewrite.py workers/ingestion-python/tests/test_procedure_rewrite_v2.py workers/ingestion-python/tests/test_article_lifecycle_types.py -q`. Lifecycle command: `python3 scripts/dev/article_lifecycle_smoke.py --mode fixture --output /tmp/article-rewrite-v2-acceptance --candidate-sha <actual-full-candidate-sha>` using existing `infra/compose/compose.article-lifecycle-test.yaml`; never count skips as database acceptance.
- [ ] Exercise both banks with explicit v2 targets: capture, ordered normalize, operation model stub, render, save, validate, publish and API-compatible projections. Assert source while pending/rejected, current-source selection on refresh, unchanged evidence/media/order, concurrent single winner/outbox, crashes before/after saved result and publication, retry exhaustion, and 100 repeated ensures/reads after restart with zero source/media/model/rescheduling calls. Retain actual call counters.
- [ ] On the frozen full corpus report total and held-out article/clause counts per bank, v1/v2 meaningful changes, supported and unsupported reasons, intact protected spans, source fallbacks and reviewer disagreements. Require zero technical/provenance/order corruptions and zero unsupported articles mislabeled complete. Require v2 to improve meaningful article coverage over v1 in each bank and demonstrate all ten initial verbs on authentic retained material or explicitly report absent cases. Do not substitute fabricated source documents to meet a ratio.
- [ ] Independent content review compares every changed sentence and retained safety/technical context in the full corpus, checking directive force and attachment as well as units/parts; independent code review checks grammar ambiguity, profile isolation and publication recomputation. Disputed grammar is removed or narrowed and the complete corpus rerun. No model score can overrule a defect. Report exact coverage rather than claim universal rewrite.
- [ ] Keep an explicit remediation register for every unsupported purchased-article family: source hash/path, reason, owner, candidate reviewed grammar extension or authorized expert rewrite and acceptance evidence needed. Expert rewrite must preserve source evidence and use a separately designed approval/publication path; this checkpoint does not grant that missing path. User outcome stays open until every article in the intended purchased-dataset acceptance scope has a unique consistent-format rewrite accepted by that path or the bounded v2 path. Source fallback is temporary availability, never completion credit. No production activation until coordinator accepts that full measured scope and its review evidence.
- [ ] Record exact SHA, command outputs, coverage, failures, review and limitations in `docs/verification/2026-11-05-article-rewrite-v2.md`; commit and push validated milestones, then synchronize Issue300/Project8 and parent Issue186 with the remaining release requirement. No merge/deploy in this task.

## Exact implementation allowlist

- `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite.py`
- `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite_v2.py`
- `workers/ingestion-python/src/autodata_ingestion/article_lifecycle.py`
- `workers/ingestion-python/src/autodata_ingestion/article_lifecycle_types.py`
- `workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py`
- `workers/ingestion-python/tests/test_procedure_rewrite_v2.py`
- `workers/ingestion-python/tests/fixtures/article_rewrite_v2.json`
- `workers/ingestion-python/tests/test_article_transform.py`
- `workers/ingestion-python/tests/test_article_worker.py`
- `workers/ingestion-python/tests/test_article_publication.py`
- `workers/ingestion-python/tests/test_article_lifecycle_integration.py`
- `workers/ingestion-python/tests/test_article_lifecycle_types.py`
- `docs/verification/2026-11-05-article-rewrite-v2.md`
- `docs/architecture/normalized-article-document.md`
- `docs/superpowers/plans/2026-11-05-article-rewrite-v2.md`
- `docs/agents/records/2026-11-05-article-rewrite-v2.json`

No other implementation paths are authorized. Existing source-job refresh and reader paths are test dependencies, not permission to edit them. If schema/UI/refresh changes are required, stop that extension and amend/synchronize the gate before editing.

## Checkpoint verification

The record is `docs/agents/records/2026-11-05-article-rewrite-v2.json`. After committing the docs-only checkpoint, pin its actual SHA/tree externally and run:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-article-rewrite-v2.json --base-sha <actual-full-checkpoint-sha>
git diff --check
```

Expected preflight: `{"status":"synchronized","errors":[]}`. Verify Issue300 body, Project8 item Source field, and parent Issue186 link by readback. Implementation dispatch belongs to the coordinator; this plan turn performs no implementation.

Tracking readback: Issue300 body and Project8 item Source/status verified literally; parent Issue186 body unchanged. Parent link: https://github.com/lucronn/autodata/issues/186#issuecomment-6653871087. Readback hashes are in the synchronized record.

## Development progress after synchronized dispatch

The exact-base preflight passed at `694ba2af0946710ae39ef4b0f7a867766c4dceb0`.
Milestone `1d6eda5` introduced the bounded v2 parser, selector, renderer and
independent candidate validator; its first v2 test failed on the original
`REWRITE_PROFILE_UNSUPPORTED` boundary before implementation.
The durable worker now checks the lease profile and retains specific unsupported
prose failures; result/validation/publication reconstruct saved v2 operation
selections under existing locks. Independent review identified mixed safety/ordinary
leaf masking and the worker's v1-only eligibility preflight; both have red/green
regressions and narrowed behavior. No source-job, schema or UI files were changed.

The four global todo items above remain open as acceptance items. Task 1's authentic
retained corpus, pre-tuning holdout, per-bank improvement and full content review
cannot be completed from the available synthetic connector fixtures. The committed
14-document synthetic development corpus earns no authentic acceptance credit.
No activation, merge, deploy or universal rewrite claim follows from passing tests.
Measured test evidence and the remaining remediation register are in
`docs/verification/2026-11-05-article-rewrite-v2.md`.
