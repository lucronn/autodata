# Retained failed introduction recovery Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline after independent checkpoint review and fresh coordinator dispatch. This checkpoint is documentation only.

**Goal:** Recover a retained full-prose draft with an introduction-only human correction in its existing unpublished revision, consuming zero further model attempts and preserving independent full-content approval and source fallback.

**Architecture:** Reuse the private human correction/review and saved-candidate publication path, adding a narrowly typed failed-attempt origin. Correct the same unpublished revision and independently recheck source, original response, corrected response and approval at each boundary.

**Tech Stack:** Python, psycopg, PostgreSQL isolated lifecycle fixtures, pytest.

**Spec:** `docs/agents/specs/2026-11-05-failed-draft-introduction-recovery.md`

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Record: `docs/agents/records/2026-11-05-failed-draft-introduction-recovery.json`
Source base: `02f863cd589aa19d27fcb06b1d2a62635957504c` (prompt-v2 branch).


## Global constraints

No model request or application DB mutation occurs during this plan. Implementation may use only synthetic isolated lifecycle fixture databases. Keep profile/grammar/renderers/validators, all attempt rows/budget and canonical/event uniqueness unchanged. No migration, automatic retries, source refresh or publication authority. If root rebases prompt branch after PR336/337 merge, adopt/rebase docs and rerun preflight at actual full checkpoint SHA before code dispatch.

## Concrete todo

- [ ] Preserve Issue186 and all Project8 fields; synchronize this recovery goal, plan, canonical spec and concrete todo, commit/push a documentation checkpoint and pass exact-SHA preflight before coordinator implementation dispatch.
- [ ] Add synthetic failed-introduction and legacy-prompt provenance regressions; implement the narrowly bound private failed-draft export/correction path without changing renderers, validators, attempt history, retry budget or canonical uniqueness.
- [ ] Revalidate corrected responses and failed-attempt provenance at export, independent approval, saved-candidate resume and atomic publication; reject stale state, wrong hashes, body edits, self-approval and unsupported failure classes.
- [ ] Run pure review/prompt/CLI regressions and isolated lifecycle database acceptance tests; commit/push coherent code milestones and obtain independent exact-SHA review before any private runtime operation.
- [ ] After separate coordinator authorization only, export the retained failed draft privately, correct only its introduction, obtain independent complete human technical review and publish the same revision at most once; retain source fallback if any requirement fails.


## Task 1: Failed-origin correction and prompt evidence

Files: exact eight-path allowlist in spec, with responsibilities fixed there. Add resolver/recovery boundary to existing article_content_review.py; avoid new modules and broad lifecycle restructuring.

- [ ] Read spec and retain exact known legacy build_full_prompt payload fromd123bbf. Add synthetic golden hash reconstruction test for v1 and v2; unknown/drifted hashes reject while drafting remains v2. Run it red before adding private `_matches_full_prompt_hash` helper.
- [ ] Extend test_article_content_review.py fixture from existing `draft` fixture to seed the actual failed attempt/source placeholder shape. Add passing and negative tests named `test_failed_introduction_export_and_correction_preserve_attempts`, `test_failed_recovery_rejects_body_edits_and_stale_origin`, `test_failed_recovery_needs_independent_complete_approval`, parameterized `test_failed_origin_tamper_is_atomic` over every predicate in spec. Assert exact snapshots of all attempts/budget, single revision count, null pointer and source selection. No genuine prose or credentials in fixtures.
- [ ] Add failing CLI tests for `export-failed`/`correct-failed`, requiring all expected/attempt bindings and existing private modes; refusal must print only generic codes. Add commands with no approve shortcut and wire only the two explicit recovery functions specified in contract.
- [ ] Implement explicit locked eligibility, exact provenance shape validation and independent prompt/source rebuild; introduction-only response equality, unchanged render/validate and retention completeness. Apply one atomic source-placeholder->validated correction plus append-only rejected review/awaiting-review checkpoint exactly as spec. Check normal v1 correction reason shape remains accepted unchanged.
- [ ] Run focused pure tests and isolated fixture review tests; commit/push `feat: recover retained failed introductions through human correction` only once the contract is green. Coherent task may include publication resolver changes below before commit if needed to keep the milestone independently passing.

## Task 2: Saved-candidate publication with failed-origin proof

- [ ] Add real fixture test in test_article_lifecycle_integration.py named `test_failed_intro_correction_publishes_same_revision_without_model_calls`; synthetic model client raises if invoked on review resume. Verify no third attempt, unchanged first and failed second attempts, same revision ID, exact hash independently reviewed, one outbox event, one canonical pointer and zero extra source/model calls on warm reads. This test fails before publication succeeded-only checks are corrected.
- [ ] Route `_original_and_effective`, `full_candidate_validation`, `_require_full_approval`, and publish_article_revision through shared strict resolver while retaining all source/prompt/report/current-owner/independent approval validation. Failed-origin path must never call render_full on the invalid original introduction. No unrelated succeeded-only check for another profile changes.
- [ ] Add concurrent stale-source/approval/correction and fault-injection rollback cases, preserved source fallback checks and all spec negatives. Assert correction author cannot approve even through new CLI command aliases; fixture-only synthetic policy remains guarded by exact lifecycle_test_ DB and environment.
- [ ] Run pure command and full isolated article lifecycle suite below, syntax/diff/scope verification and root-selected existing regressions. Record actual counts and skips; a skipped isolated DB case is not acceptance. Commit/push `fix: bind corrected failed drafts at atomic publication` if split from Task1.

Pure verification (no network/provider/database):

```sh
PYTHONPATH=workers/ingestion-python/src /tmp/autodata-mercury2-token-budget-venv/bin/python -m pytest workers/ingestion-python/tests/test_procedure_rewrite_full.py workers/ingestion-python/tests/test_procedure_rewrite.py workers/ingestion-python/tests/test_procedure_rewrite_v2.py scripts/dev/test_article_content_review.py -q
git diff --check
```

Isolated DB verification uses the existing `infra/compose/compose.article-lifecycle-test.yaml` runner with `AUTODATA_LIFECYCLE_TEST=1`, database names lifecycle_test_* and synthetic fixtures; no application/recovery DB. Root supplies an owned artifact directory/test image/project and runs the existing runner, with command:

```sh
python -m pytest workers/ingestion-python/tests/test_article_content_review.py workers/ingestion-python/tests/test_article_lifecycle_integration.py workers/ingestion-python/tests/test_article_publication.py workers/ingestion-python/tests/test_article_transform.py -q
```

No container/database operation is run by this planning worker. Test design is contract-level above; implementation worker writes the exact synthetic fixture assertions before implementation rather than mirroring SQL internals.

## Task 3: Independent review and separately authorized recovery

- [ ] Obtain independent exact-code-SHA review: audit every previously succeeded-only publication check, origin hash meaning, legacy prompt-byte compatibility and unchanged renderer/validators/unique identity. Revalidate pinned planning record at actual integration SHA.
- [ ] Coordinator separately authorizes private export/correction on retained recovery database, confirms actual human corrector plus different independent qualified reviewer, retains safe before/after receipts and all original attempts, and authorizes at most same-revision publication after complete review. No operation in this paragraph occurs under planning/code authorization.
- [ ] If content review finds a body defect, ambiguous unsupported notation or provenance mismatch, stop this recovery and retain source fallback; no model fallback/identity change/budget reset. Report planning and synthetic tests distinctly from authentic human acceptance.

## Checkpoint evidence

Tracking synchronized by Issue186 comment https://github.com/lucronn/autodata/issues/186#issuecomment-6673413206; Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` Release hotfix reference `PVTF_lAHOCSJ8cc4BiQ2BzhoxGVY` appends this narrow pointer after its complete previous value. Exact readback preserved the entire Issue body, all302 prior comments and every other Project field. External before/after snapshots and SHA256 hashes: `/home/corp/autodata-evidence/failed-draft-recovery-gate/preservation.json`. Commit/push this documentation checkpoint and pin its actual full SHA externally; exact-SHA preflight and independent checkpoint review remain required. No implementation or runtime operation has occurred.
