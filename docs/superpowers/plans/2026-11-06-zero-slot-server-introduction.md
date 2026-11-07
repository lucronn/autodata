# Zero-slot source-bound server introduction implementation plan

> **For agentic workers:** Execute the scoped plan task by task with review checkpoints. No implementation until exact committed synchronized gate and coordinator dispatch.

**Goal:** Publish zero-editable-prose automatic articles through a source-bound deterministic introduction before any model attempt, preserving technical validation and the nonzero-slot model path.

**Architecture:** A pre-model branch for profile full-prose-auto-v1 and exactly zero full.prose_slots builds an introduction from ONE exact existing heading. The unchanged renderer/validator preserve every protected block. Persist honest server provenance and reconstruct it under existing publication locks; no invented model attempts or schema changes.

**Tech stack:** Existing Python ingestion lifecycle, PostgreSQL persistence and pytest.

**Spec:** `docs/verification/2026-11-06-zero-slot-server-introduction.md`

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Product base587dedc15993c9833d6d4baf0dc31586f879433c, merged PR358. Planning only; no runtime authority.

## Decision and constraints

The fd4d proof correctly emitted prompt-v3 with replacements[] but failed technical validation because its generated introduction introduced two unsupported technical tokens. Retained resultSHA256bd0b832b4711d834409be66b1d32e239c73ead1170f17b48fea1438cd223f83c is historical failure evidence. This fix is an explicit PRE-MODEL method, not repair of saved failed output, model fallback/retry, or replay of spent jobs.

Select only full-prose-auto-v1 with exactly zero editable prose slots; nonzero slots (including technical-only leaves) retain the existing model path. Choose one exact nonempty heading text in source order, without wrapper/concatenation/case/punctuation/whitespace edits. Construct response introduction=that exact text and replacements=[], run unchanged render_auto/validate_auto; use first eligible heading that passes unchanged guards. Missing/ambiguous/oversize/no valid heading fails closed with readable source, without model call. Enforce existing response/storage bounds. Preserve all source blocks/order/structure/evidence/media and normalize from durable source. No routing facts, manufactured prose or semantic safety claim.

Persist server method/version, drafting_actor=server, model=server-zero-slot-v1 and both model_calls=0/model_dispatch_count=0 (and complete_rewrite:false). DB published CHECK requires nonempty model/profile_version metadata: use an honest server identifier, never Mercury/fake model result. Metadata is only a selector, never sufficient authority: rebuild the exact normalized source, selected heading, response/candidate/hash/projection and expected provenance under existing locked automatic_candidate_validation; require zero rewrite-attempt rows for the transformation/job. Reject forged/extra method data, tampered source/candidate/provenance, or any prior attempt. No successful-attempt substitute rows, raw model response/prompt fiction, schema/profile changes, validator weakening or edits to historical candidates.

## Implementation allowlist

Only these implementation/test files plus the three gate documents may change:
- workers/ingestion-python/src/autodata_ingestion/procedure_rewrite_auto.py — deterministic source-bound helper, existing model/prompt/renderer/validator behavior preserved.
- workers/ingestion-python/src/autodata_ingestion/article_lifecycle.py — pre-model zero-slot branch before missing-model parking/prepare/mark/rewrite; use existing later validation/publication path.
- workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py — NEW server candidate store (keep _store_rewrite_result model-only), exact automatic_candidate_validation reconstruction; narrow publish_article_revision server branch AFTER validation. Existing succeeded-attempt model branch stays byte-equivalent in else.
- workers/ingestion-python/src/autodata_ingestion/source_job_persistence.py — _claim_automatic_resume selection admits existing succeeded-attempt OR exact deterministic-method metadata, followed by current locked validation BEFORE exhausted-cap sweep; saved cap1/retry1 candidates resume without model redelivery. Preserve fencing/lease/token/cap semantics.
- workers/ingestion-python/tests/test_procedure_rewrite_auto.py
- workers/ingestion-python/tests/test_article_lifecycle_integration.py

No schema, prompt builders/model clients, runtime units/env/state, API/UI, generic scheduler, quota/admission or paid-auth changes. Four prior spent jobs across three preserved disabled rollouts remain untouched. New runtime proof must separately archive/pin fresh source state; this code gate authorizes none.

## Concrete todo and checks

- [ ] Add failing helper and real lifecycle regressions for a zero-slot source-bound deterministic candidate, zero model dispatch/attempt rows, tamper rejection and crash-safe exactly-once publication.
  Helper cases: realistic zero-slot protected 63-block shape => intro exactly one source heading, replacements[], source blocks/order/images/evidence unchanged, validation passes; ambiguous/no eligible/oversize heading => fail closed/no generic intro. Unsupported token/tampered heading/extra replacement => rejected by unchanged guards. Identical headings may produce identical prose: do NOT claim global uniqueness or complete rewrite.
  Lifecycle cases: model client raises if called, successful server source capture/candidate/UNREVIEWED canonical/event with model calls0 and attempt rows0; no human review. Tampered metadata/source/hash/candidate or any attempt => publication rejected. Existing nonzero success/failure unchanged.
- [ ] Implement the narrow deterministic helper, pre-model lifecycle branch, locked server candidate storage/reconstruction/publication binding and bounded existing resume selector branch; keep nonzero model behavior and leases unchanged.
  Crash after server candidate commit and inside publication: resume under expired lease at attempt cap1, no model/attempt, exactly one canonical/current pointer/event; source fallback on failure; existing model resume still succeeds. Resume SQL closes selection transaction before IO as existing behavior; do not bypass validator via metadata.
- [ ] Run focused helper/lifecycle tests and required repository checks; independently review, commit/push small coherent milestones and synchronize exact PR/CI evidence. Runtime/deploy/fresh-identity proof require a separate future synchronized gate.
  Run from workers/ingestion-python: `PYTHONPATH=src pytest -q tests/test_procedure_rewrite_auto.py`; run `PYTHONPATH=src pytest -q tests/test_article_lifecycle_integration.py` with existing real PostgreSQL fixture prerequisites (no live DB). Include source job/persistence tests appropriate to resume change and existing required autonomy CI; report unavailable prerequisites honestly. Use independently reviewable commits after passing meaningful checks, then PR/CI exact head review.

## Verification limits

A source heading is retained source prose; only a new introduction block is deterministically produced. It does not rewrite protected content or certify semantic equivalence/global uniqueness. complete_rewrite remains false. Validation, candidate/source binding, publication and no-attempt crash recovery must all pass before claiming code success. A later separate gated authentic unseen identity proof is required for production acceptance; no rerun/reset of38c4391c,65a3d56f or earlier spent jobs.
