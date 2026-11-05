# Full article rewrite and content review Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans after exact committed-base preflight and coordinator review/dispatch. No implementation is authorized by this planning turn.

**Goal:** Publish uniquely rewritten complete dual-bank articles once through full-prose drafting, exact-hash human content approval and durable review resume, serving source until publication.

**Architecture:** Add one explicit immutable full-prose profile to the existing durable article lifecycle. Store complete drafts, retain source during independent exact-hash review, and resume the same saved candidate for atomic publication without another model call. Reuse existing review storage and the ordered-document reader.

**Tech Stack:** Existing Python ingestion worker, PostgreSQL lifecycle/reviews, Mercury transport, local operator CLI and pytest; no new runtime dependencies.

**Spec:** `docs/architecture/normalized-article-document.md`, “Full article drafting with exact-hash content review”.

Issue: https://github.com/lucronn/autodata/issues/333
Parent: https://github.com/lucronn/autodata/issues/186
Prior bounded grammar: https://github.com/lucronn/autodata/issues/300
Project: https://github.com/users/lucronn/projects/8
Project item: PVTI_lAHOCSJ8cc4BiQ2BzhGaXx0
Inspected source base: `008669db6782d6e26b0eee645decb1868295e5e9`
Planning branch: `codex/full-article-review-gate`
Record: `docs/agents/records/2026-11-05-full-article-review.json`

## Global constraints

- Planning/documentation only until machine preflight passes at the committed checkpoint and the coordinator dispatches the builder. No implementation edits, model/provider calls, environment changes or deployment in this turn.
- Preserve immutable v1/v2 profiles/defaults, provider identities, existing source-projection behavior, model retry limits, original raw responses and publication fences. Explicit `full-prose-review-v1` refresh only; no bulk requeue or rewrite-on-read.
- One new introduction paragraph plus text-leaf replacements; existing table/safety/heading/media/evidence blocks remain exact and relatively ordered. No schema/API/UI/contract/auth/entitlement/connector changes.
- Full-prose structural validation is necessary but never semantic approval. Independent human review of the complete document is mandatory before this profile publishes. No model judge.
- Raw articles and private review exports remain outside Git/GitHub. Commit only synthetic tests and private manifest hashes/counts. Never log credentials or source bodies.
- “Once” means one durable accepted candidate/publication reused on reads; bounded transport ambiguity may still yield more than one actual provider delivery, which must be measured honestly.
- Synthetic tests, unavailable-media placeholders and readable source earn no authentic complete-rewrite credit. Scope remains open until every intended article has a materially unique, complete approved rewrite.

## Decision and alternatives

Selected: full-prose drafting plus exact-hash human approval and durable resume. Expanding v2's finite dictionary cannot cover declarative prose/table articles or prove full semantics. Unrestricted auto-publication based on tokens/LLM judges cannot establish technical fidelity. A public review application/new schema is unnecessary because the repository already has immutable review rows and a local operator boundary.

## Concrete todo

- [ ] Freeze intended dual-bank source scope, hashes and retained40 baseline.
- [ ] Add immutable full-prose-review-v1 drafting and complete document integrity checks.
- [ ] Persist review waits; add exact-hash human approve/reject/correct and zero-redraft resume.
- [ ] Enforce approval at publication; test races, budgets, recovery and zero-call warm reads.
- [ ] Verify isolated lifecycle and every authentic final article; separately authorize live Mercury acceptance.

### Task 1: Freeze denominator and implement the full-prose boundary

**Files:** new `procedure_rewrite_full.py`, modify `procedure_rewrite.py`, new `test_procedure_rewrite_full.py` (full paths in allowlist).

- [ ] Freeze the retained40 identity/resource/envelope hashes and original split privately; preserve original0/40 evidence. Record exact intended scope, families, private artifact hashes and source/media limitations in the verification document. Broaden with authentic full procedural families only under separate connector-call authority, reporting the changed denominator. Do not filter by eligibility.
- [ ] Write red pure regressions for complete declarative/multiple-sentence/conditional procedural documents, nested lists, table-only content and source-bound introduction; reject foreign/missing/duplicate/reordered/extra rows, supplied structural members, whitespace-only changes, `retain` with changed text or blank justification, invented numeric values, protected mutations and JSON bool/int confusion. Synthetic fixtures live in the test module and earn no corpus credit.
- [ ] Implement `prose_slots`, `build_full_prompt`, `render_full`, `validate_full` under immutable `full-prose-review-v1`. Exact response shape is in the canonical spec. Server derives one introduction paragraph ID from source hash/profile, evidence union and position. Original blocks are deep-copied; only declared prose leaves change. Keep introduction useful and fact-bound for table-only articles; ordinary prose still requires full rewrite.
- [ ] Define and test the deterministic token guards, exact protected projection, retained-path accounting and structural report (`content_acceptance_required:true`). Prevent report claims of semantic completion. Dispatch profile through existing `editable_slots`, prompt/rewrite/validation functions without changing v1/v2. Model output only proposes retentions, which remain explicit review obligations. Keep200KiB/1MiB bounds and current Mercury token settings.
- [ ] Run pure full/v1/v2/types tests, inspect intended red/green logs, commit/push this coherent milestone.

### Task 2: Persist draft, exact-hash review and zero-redraft resume

**Files:** `article_lifecycle.py`, `article_lifecycle_store.py`, `source_job_persistence.py`; new `article_content_review.py`, `scripts/dev/article_content_review.py`; new focused review/CLI tests and existing worker/job tests.

- [ ] Write database red tests: saved full draft remains source-readable and `needs_review/CONTENT_REVIEW_REQUIRED`; 100 ensures do not dispatch/reschedule. Existing v1/v2 remain unchanged. Missing/forged/foreign/stale approvals fail and latest rejection blocks. Review-resume succeeds with retry_count3 without a fourth attempt, a count reset, or a model call.
- [ ] Store structurally valid full candidate/attempt, then park the job with a versioned awaiting-review checkpoint and no active lease. Add a profile-specific original-response renderer binding. Plain `claim_source_job` must not revive it. Store-validation and publication each recompute mechanical integrity; no stored-report trust.
- [ ] Implement privileged local CLI subcommands `export`, `approve`, `reject`. Require reviewer allowlist external to Git and independent from drafting identity, expected job/article/source/profile/generation/candidate IDs and source/candidate hashes, complete retention review and substantive rationale. Export source/candidate privately for actual human comparison, with restrictive file permissions; never print article bodies by default. Versioned review reason JSON carries exact source/candidate bindings and full-content/retention attestations. Store approvals only from this local operator action; synthetic reviewers accepted only in explicitly isolated fixture mode, never from model output.
- [ ] Permit optional reviewer corrections supplied with expected original hash. Under job/article/candidate locks in the same order as `_lock_transform` reject published/stale candidates, render complete corrected replacements with same boundary, recompute projections/report/hashes and append review recording original/final hashes plus correction provenance. Preserve original model response/attempt. Existing approvals lose authority when hash changes. An explicitly corrected rejected draft may later be independently approved without a new model draft.
- [ ] Commit APPROVED review and pending publishing-resume checkpoint atomically; reject leaves source selected. Review-resume claim gets a new fenced token for the same current owner/candidate without consuming a model attempt or resetting budgets, including retry_count3. Restrict this exception to exact-bound approved saved full-profile candidates. Recovery loads candidate and never dispatches Mercury. Cover claim, expired-lease reclaim and exhaustion sweep consistently; review resumes must not become delivery-ambiguous or dead-letter solely because their already-saved model budget is exhausted. No generic resurrection of terminal jobs.
- [ ] Run focused review/CLI/jobs/worker tests and the dedicated isolated PostgreSQL cases, retain failure/recovery evidence, commit/push.

### Task 3: Enforce approval in publication and prove complete lifecycle

**Files:** `article_lifecycle_store.py`, existing publication/integration tests and verification doc.

- [ ] Write red publication tests for missing approval, modified document with recomputed hashes/report, changed source/generation/profile/identity, invalid correction provenance, approval for another revision, rejection races, duplicate commands and a stale worker. Require locking and latest-decision consistency with existing review-reader ordering.
- [ ] Require exact-bound latest APPROVED human review and complete source context for this profile inside atomic publish. Reconstruct original model draft from saved response; if corrected, verify original/final hashes and stored explicit correction provenance. Independently recompute document/report/projections and all existing source/attempt ownership fences. Event review status is APPROVED for this profile. Preserve v1/v2 event/status semantics.
- [ ] Test concurrent approvals/claims produce one revision/pointer/event; crashes after saved result, while awaiting review, after approval before claim, after resume claim, inside publication and after commit recover without model repeat. Failed/rejected/stale draft serves current source. Changed-source refresh invalidates approval. Warm100 reads/ensures after worker restart measure source=0, media=0, model=0, schedule=0 per bank.
- [ ] Run the existing mandatory isolated lifecycle smoke at the exact candidate, then run new pure/review/CLI modules explicitly because the frozen smoke file list may not include them. No smoke exclusions, skip-as-pass, runner alterations or application database. Retain commands, candidate SHA, raw logs/JUnit, runtime rows/counters and artifact hashes.
- [ ] Run full ingestion suite, relevant scripts/dev tests and `git diff --check`; independently review exact code and content acceptance boundaries. Commit/push measured implementation and documentation milestones.

### Task 4: Actual authentic completion acceptance

- [ ] After separately authorized credential/TEST setup, perform bounded real Mercury drafting through the same deployed worker on the frozen intended scope. Account for all requests, ambiguous delivery and failures; verify real provider/model route and bound output tokens without exposing credentials. No local stub earns live acceptance credit.
- [ ] Independent qualified human reviewer compares every final article against its complete source: every changed/retained sentence, introduction fact, technical value/tool/component, condition/negation/modality, ordering/reference/applicability and available/unavailable media. Use correction path when needed, preserve original model result and rejection history, and require exact final hashes. Model-generated approval is never independent human content evidence.
- [ ] Report accepted/total by bank/family, complete prose and justified retained paths, private source/candidate/review hashes, duplicate/generic rewrite checks, media limitations and review disagreements. Require every intended article accepted; neither intro-only procedural output nor0/N source fallbacks satisfies the outcome. Broader purchased-dataset scope beyond the frozen sample stays explicitly open.
- [ ] Synchronize Issue/Project, canonical spec, plan/record and verification document with exact SHA, independent review and actual acceptance evidence. Coordinator alone decides integration/activation/release after necessary checks; this gate grants none.

## Exact implementation allowlist

- `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite_full.py`
- `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite.py`
- `workers/ingestion-python/src/autodata_ingestion/article_lifecycle.py`
- `workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py`
- `workers/ingestion-python/src/autodata_ingestion/source_job_persistence.py`
- `workers/ingestion-python/src/autodata_ingestion/article_content_review.py`
- `scripts/dev/article_content_review.py`
- `workers/ingestion-python/tests/test_procedure_rewrite_full.py`
- `workers/ingestion-python/tests/test_article_content_review.py`
- `workers/ingestion-python/tests/test_article_worker.py`
- `workers/ingestion-python/tests/test_article_publication.py`
- `workers/ingestion-python/tests/test_source_job_persistence.py`
- `workers/ingestion-python/tests/test_article_lifecycle_integration.py`
- `scripts/dev/test_article_content_review.py`
- `docs/verification/2026-11-05-full-article-review.md`
- `docs/superpowers/plans/2026-11-05-full-article-review.md`
- `docs/architecture/normalized-article-document.md`
- `docs/agents/records/2026-11-05-full-article-review.json`

All other files remain out of scope, particularly migrations, v2 grammar, media/connector clients, API/Workshop assets, compose and deployment files. If this bounded design cannot reuse existing storage/reader/lease contracts, stop that extension and amend the synchronized plan before implementation. No silent scope expansion.

## Validation commands and evidence

Run from an isolated checkout at the dispatched exact SHA; resolve the existing pinned test dependencies before interpreting collection failures.

```sh
PYTHONPATH=workers/ingestion-python/src python3 -m pytest -q workers/ingestion-python/tests/test_procedure_rewrite_full.py workers/ingestion-python/tests/test_procedure_rewrite.py workers/ingestion-python/tests/test_procedure_rewrite_v2.py workers/ingestion-python/tests/test_article_lifecycle_types.py
PYTHONPATH=workers/ingestion-python/src python3 -m pytest -q scripts/dev/test_article_content_review.py
```

Use `infra/compose/compose.article-lifecycle-test.yaml` with an owned project/artifact directory, fixture credentials and no application database. Run new review modules and affected worker/job/publication/integration cases inside its test-runner with actual PostgreSQL; zero skips required for that evidence. Run the unchanged `scripts/dev/article_lifecycle_smoke.py --mode fixture --candidate-sha <full-actual-sha> --output /artifacts/full-review-smoke.json` and full ingestion suite inside the same isolated configuration. New full-profile pure/review/CLI tests must be run explicitly in addition to the frozen smoke. Do not imply that the unchanged smoke automatically includes new files. Record real commands and project/image provenance in `docs/verification/2026-11-05-full-article-review.md`.

## Planning checkpoint and handoff

The coordinator pins the committed checkpoint SHA externally. Run:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-full-article-review.json --base-sha <actual-full-checkpoint-sha>
git diff --check
```

Expected preflight: `{"status":"synchronized","errors":[]}`. Read back Issue333 and Project8 Source/status and ensure literal goal/todo/references match. Documentation synchronization is not implementation/content/live acceptance. Builder starts only after coordinator reviews/dispatches the exact checkpoint.
