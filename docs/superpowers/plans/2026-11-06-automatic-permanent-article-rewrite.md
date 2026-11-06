# Automatic permanent article rewrite Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans after exact committed-base preflight. Execute inline in this isolated branch; the coordinator owns integration and runtime selection.

**Goal:** Automatically publish one materially unique, consistent-format canonical rewrite per bank-scoped source article, retain the accepted revision permanently, and serve stored source until the rewrite is ready; no manual article review.

**Architecture:** Add immutable `full-prose-auto-v1` to the existing stored-source and canonical-publication lifecycle. Reuse the ordered document, source fallback, model transport, immutable revisions and fenced deduplication. The automatic profile publishes after mechanical validation; it never creates or requires a human approval.

**Tech Stack:** Existing Python ingestion worker, PostgreSQL, Mercury transport and pytest; existing Go API and Workshop reader.

**Spec:** `docs/architecture/normalized-article-document.md`, “Automatic permanent article rewriting”.

Issue: https://github.com/lucronn/autodata/issues/186
Synchronized scope: https://github.com/lucronn/autodata/issues/186#issuecomment-6679826363
Project: https://github.com/users/lucronn/projects/8 (Release hotfix reference points to the synchronized scope comment)
Inspected source base: `4513c387c900add7138330555ccfca92f74b9894`
Planning branch: `codex/automatic-permanent-article-rewrite`
Record: `docs/agents/records/2026-11-06-automatic-permanent-article-rewrite.json`

## Global constraints

- The user's current requirement removes manual article review for this successor. Historical `full-prose-review-v1`, `technical-prose-v1` and `technical-prose-v2` remain immutable and retain their existing behavior.
- Preserve numeric/technical/table/safety/media/evidence/order guards, bank-scoped identity, source capture and immutable source/canonical rows. No forged approval, schema/auth/payment/provider redesign, deletion of immutable rows or production deployment.
- Metadata says mechanically validated automatic publication, never human-approved. Mechanical checks do not prove semantic equivalence; do not claim that they do.
- Reuse the saved accepted canonical revision permanently. No expiry, regeneration on read, or automatic repeated refresh. Explicit changed-source/profile refresh is a separate bounded operation and preserves history.
- Source stays readable during drafting or validation failure. Failure must not introduce a manual-review obligation for this automatic profile. Preserve existing bounded delivery retries and ambiguous-delivery handling.
- Implementation starts only after this docs-only checkpoint is committed/pushed and the exact checkpoint preflight passes. This plan permits local/sandbox verification; production activation remains outside scope.

## Concrete todo

- [ ] Add immutable full-prose-auto-v1 prompt/render/validation using complete prose leaves, source-bound introduction and existing ordered format.
- [ ] Publish valid automatic candidates through the existing durable fenced lifecycle without human review, preserving source fallback, saved-response integrity and once-per-transformation dedupe.
- [ ] Select automatic rewriting for newly captured articles and provide an explicit bounded refresh for existing stored sources; preserve all old profiles and published revisions.
- [ ] Prove both-bank automatic publication, integrity failures retaining source, concurrent/restart reuse, and zero provider/model/schedule calls on warm reads; start and verify the working local app.

## Task 1: Add the automatic full-prose boundary

**Files:** create `procedure_rewrite_auto.py` and its pure test module; modify `procedure_rewrite.py`. If helpers need parameters, modify `procedure_rewrite_full.py` with historical default values and keep its existing tests.

**Interfaces:** expose `PROFILE = "full-prose-auto-v1"`, `build_auto_prompt(document, *, context)`, `render_auto(source, response)` and `validate_auto(source, candidate, *, response=None)`. Dispatch them from existing `editable_slots`, `build_rewrite_prompt`, `rewrite_ordered_document` and `validate_article_rewrite` entrypoints.

- [ ] Add failing tests using synthetic paragraph/step/nested-list/table documents: materially changed ordinary prose succeeds; missing/extra/reordered replacement rows, unchanged/whitespace-only ordinary prose, invented technical tokens and changed protected structure fail. Explicitly test the old full-review profile output remains unchanged.
- [ ] Implement full prose replacement and one source-bound introduction using existing protected-token and ordered-document helpers. Do not use mutable module globals to switch profiles. Retained technical-only leaves must be accounted for explicitly; a model's arbitrary retain reason cannot exempt ordinary prose from rewriting. Table-only documents may obtain a useful source-bound introduction while their technical table remains exact.
- [ ] Produce an automatic profile/validator report with honest changed and retained path accounting, no human acceptance requirement, and no semantic-proof claim. Bind render output to the complete response. Retain the existing 200KiB prompt, 1MiB response and transport token limits.
- [ ] Run the new pure tests plus full/v1/v2 regression modules; commit/push the passing milestone.

## Task 2: Automatically publish through existing durable storage

**Files:** `article_lifecycle.py`, `article_lifecycle_store.py`, worker/publication/integration tests.

- [ ] Add failing lifecycle tests for a valid auto draft completing without any review row; an invalid draft retaining stored source; altered saved response/candidate/report rejection; a concurrent or restarted worker producing only one publication and one current pointer.
- [ ] Admit the new profile in the worker. After storing a successful automatic result, continue normal validation/publication rather than entering the review-specific early return. Preserve the original review profile parking behavior.
- [ ] Independently rebuild the automatic candidate from the persisted successful response at store/validation/publication boundaries, analogous to existing v2 operation binding. Verify source/input/prompt/profile/output hashes, projected body/steps/images, attempt ownership and existing lease/generation/source fences. Do not call human-specific approval/correction resolution for auto candidates.
- [ ] Publish atomically with the existing revision/pointer/job/event transaction and once-per-transformation key. Record existing truthful `UNREVIEWED` review status rather than inventing approval. Automatic failures remain source-readable with their actual error and existing retry policy.
- [ ] Run focused PostgreSQL worker/publication/integration cases and historical manual-review regressions; commit/push the passing milestone.

## Task 3: Select automatic work and bounded refresh

**Files:** `article_lifecycle_store.py` registration function, identity tests, optional `scripts/dev/automatic_article_refresh.py` and its test module.

- [ ] Add a regression proving new descriptor registration explicitly chooses `full-prose-auto-v1`, while registering an existing descriptor neither changes its old target/profile nor schedules new work.
- [ ] Set the target profile explicitly on new `canonical_articles` inserts. Do not alter historical SQL migration defaults or globally change old profile constants.
- [ ] Provide an operator-only bounded refresh command, default preview, that accepts explicit canonical article UUIDs, expected current source revision UUIDs, actor and reason. Apply uses existing explicit refresh lifecycle APIs, refuses changed expected sources and already automatic/published rows, and records selected identities/counts without article bodies or secrets. The coordinator must select actual serving rows before any runtime apply; never bulk discover/requeue the catalog. Reuse captured source evidence where supported; report any live connector/model calls as such rather than claiming an offline refresh.
- [ ] Test preview has no mutation, stale selection fails, duplicate identities do not schedule twice, and historical publications remain immutable. Commit/push the validated milestone.

## Task 4: Verify permanent reuse and the working app

**Files:** affected tests and `docs/verification/2026-11-06-automatic-permanent-article-rewrite.md`.

- [ ] In disposable PostgreSQL lifecycle infrastructure test Bankone and Banktwo separately and together: source-first read, successful automatic replacement, failed rewrite retaining source, concurrent ensure, stale lease, crash after saved model response, restart, and 100 warm reads/ensures with zero source/media/model/schedule calls. Synthetic fixtures count as lifecycle proof, not authentic content acceptance.
- [ ] Run the unchanged fixture lifecycle smoke at the actual candidate SHA and explicitly include the new pure/refresh test modules. Retain test commands, exact SHA, counts, runtime identity and limitations; do not substitute skipped tests for database coverage.
- [ ] Run the full ingestion suite and `git diff --check`, then commit/push the validated implementation and evidence. Obtain independent exact-SHA review under existing integration policy.
- [ ] Identify the actual serving checkout/service before changing runtime. Existing read-only observation found healthy APIs at local ports18080 and3017; port18080 readiness confirms DB/NATS/S3. Verify the authorized local app health/readiness and stored source-to-auto transition, with measured warm requests. Do not start a duplicate base44 stack or make production changes under this checkpoint.

## Exact implementation allowlist

- `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite_auto.py`
- `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite_full.py`
- `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite.py`
- `workers/ingestion-python/src/autodata_ingestion/article_lifecycle.py`
- `workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py`
- `workers/ingestion-python/tests/test_procedure_rewrite_auto.py`
- `workers/ingestion-python/tests/test_procedure_rewrite_full.py`
- `workers/ingestion-python/tests/test_article_worker.py`
- `workers/ingestion-python/tests/test_article_publication.py`
- `workers/ingestion-python/tests/test_article_lifecycle_integration.py`
- `workers/ingestion-python/tests/test_article_identity.py`
- `scripts/dev/automatic_article_refresh.py`
- `scripts/dev/test_automatic_article_refresh.py`
- `docs/verification/2026-11-06-automatic-permanent-article-rewrite.md`
- `docs/superpowers/plans/2026-11-06-automatic-permanent-article-rewrite.md`
- `docs/agents/records/2026-11-06-automatic-permanent-article-rewrite.json`
- `docs/architecture/normalized-article-document.md`

All other implementation paths require a synchronized scope amendment. In particular, migrations, contracts, API/UI assets, auth/payment code and deployment files remain outside this plan.

## Verification and checkpoint

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-06-automatic-permanent-article-rewrite.json --base-sha <full-committed-checkpoint-sha>
PYTHONPATH=workers/ingestion-python/src python3 -m pytest -q workers/ingestion-python/tests/test_procedure_rewrite_auto.py workers/ingestion-python/tests/test_procedure_rewrite_full.py workers/ingestion-python/tests/test_procedure_rewrite.py workers/ingestion-python/tests/test_procedure_rewrite_v2.py
PYTHONPATH=workers/ingestion-python/src python3 -m pytest -q scripts/dev/test_automatic_article_refresh.py
```

Use the existing `infra/compose/compose.article-lifecycle-test.yaml` isolated PostgreSQL runner for lifecycle/database evidence, never the serving application database. Run its unchanged `scripts/dev/article_lifecycle_smoke.py --mode fixture --candidate-sha <full-actual-sha> --output /artifacts/automatic-rewrite-smoke.json`; explicitly run new modules that its frozen list does not include. Record zero-call counters and review/status truthfulness in the verification document.

The planning coordinator read back Issue186 comment6679826363 and the Project8 Release hotfix reference (length1009) before this checkpoint. The record carries those exact goal/todo/reference facts. Planning verification itself does not claim implementation or content success.


### Automatic lifecycle recovery scope amendment

Issue186 amendment https://github.com/lucronn/autodata/issues/186#issuecomment-6679877079 and Project8 Release hotfix reference were synchronized/read back by the coordinator (field length990). This adds the following exact paths to the implementation allowlist:

- `workers/ingestion-python/src/autodata_ingestion/source_job_persistence.py`
- `workers/ingestion-python/tests/test_source_job_persistence.py`
- `workers/ingestion-python/tests/lifecycle_support.py`

Automatic-profile nonretryable mechanical failures enter `dead_letter` with source still readable, never a manual-review wait. A successfully saved automatic candidate may reclaim a fenced publication lease after its model-attempt budget is exhausted, without incrementing or resetting that budget, invoking the model, or reviving a failed/ambiguous result. Existing manual-review and legacy retry behavior remains intact. Tests must cover final-attempt restart/publication, failed candidate exclusion and stale leases.

New production descriptor registration defaults explicitly to the automatic profile. The shared test insertion helper explicitly requests historical `technical-prose-v1` unless a test selects another profile, preserving historical test coverage. The production upsert accepts an explicit profile only at its existing internal registration interface; HTTP clients cannot select a profile. These extra files may change only after this amendment is committed/pushed and exact-head preflight passes.
