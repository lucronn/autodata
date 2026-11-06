# Retained failed introduction recovery contract

Status: tracking synchronized; committed exact-SHA preflight and independent coordinator dispatch remain required. No implementation or runtime operation is authorized by this document.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-05-failed-draft-introduction-recovery.md`
Record: `docs/agents/records/2026-11-05-failed-draft-introduction-recovery.json`

Goal: Recover a retained full-prose draft with an introduction-only human correction in its existing unpublished revision, consuming zero further model attempts and preserving independent full-content approval and source fallback.

## Decision and evidence

Extend the existing private human correction path; do not spend the remaining model attempt. A model retry does not solve the existing unique transformation/revision insertion boundary, can repeat the same semantic error and creates fresh provider ambiguity. The retained response already supplies the material a human can correct. The correction is deliberately introduction-only; a defective replacement body requires a new gate, not an expanded recovery exception.

Inspected implementation at prompt branch `02f863cd589aa19d27fcb06b1d2a62635957504c`, based on canonical lifecycle `d123bbf3098d87bd75d234b409039ca25a8f0d3e`. Safe receipt `/tmp/autodata-private-full-prose-canary-20261105-run2.json` SHA256 `c3ba45fe1df3213076f6fae81bbc9e5519359d3d6b123d7d18d0002480fc8e8a` records two attempts, retry_count2/max_attempts3, one retained building revision, failed attempt2 `REWRITE_TECHNICAL_MUTATION`, zero reviews/publication and null canonical pointer. The recorded source hash is `949823b5b05364976585f425f84ea28bf809860196a46d3c5a92019694db032e`; failed response hash `8b5c8ea6e445ff3694ba56d5e13cb57d5a9fbf12fc667f613769baf68baea155`; prompt hash `d673b376f52c875adc0ee2e61b09a66fca0c2c312354b75bc7a288be3d07bfdf`. The coordinator previously diagnosed introduction-only context leakage and passing nine body leaves; this planner inspected only the safe receipt/code, not raw prose or the database. That diagnosis must be independently re-established during authorized correction, never treated as acceptance evidence.

Migration038 already permits unpublished building->validated changes and enforces unique transformation_key plus unique(article, source, normalization, profile), immutable published revisions, append-only reviews and one publication event. No migration, profile bump, new canonical identity, source refresh, retry reset or failed->succeeded relabeling is required or permitted.

Existing blockers are `_load_locked` (validated + awaiting-review only), `_original_and_effective` (succeeded + original render), and three succeeded-only checks in `full_candidate_validation`, `_require_full_approval`, `publish_article_revision`. `render_full` correctly rejects the failed introduction before rendering the body. The correction must never fabricate an original rendered candidate hash. Existing saved building candidate is a source placeholder, not the failed response's rendered output.

## New private recovery boundary

Keep current normal export/correct/approve behavior. Add CLI commands `export-failed` and `correct-failed`; each requires existing private `--expected` bindings plus `--failed-attempt-id` (canonical UUID) and `--failed-response-hash` (64 lowercase hex). They call `export_failed_review(repo, *, expected, failed_attempt_id, failed_response_hash, destination)` and `record_failed_correction(repo, *, expected, failed_attempt_id, failed_response_hash, reviewer_id, allowlist, rationale, correction, retention_reviews=None, fixture_mode=False)`. `correct-failed` has no APPROVED option and returns only hashes/IDs/status. Reuse private no-symlink/owner-only JSON input and exclusive 0700/0600 export protections, generic error output and external human allowlist. No provider call, source fetch, lease acquisition, request-generation increment or publication is performed by either operation.

Under job->article->candidate row locks, require all existing exact expected binding/current-owner checks plus: profile `full-prose-review-v1`; job needs_review/validating, retryable=false, error_code=REWRITE_TECHNICAL_MUTATION, no lease owner/expiry, checkpoint.candidate_revision_id equals candidate, checkpoint.rewrite_error_code agrees and no content_review; candidate building, published_at null, not current canonical, review_status UNREVIEWED, validation_report={}, validation_hash=digest_json({}); its canonical document/hash/projection equal its normalized source placeholder; no reviews. Lock and select the explicitly named attempt (never an arbitrary failed row): same job/revision/profile, status failed/error_code REWRITE_TECHNICAL_MUTATION, completed_at present, exact caller response hash=digest_json(response), input hash and model/prompt/profile metadata consistent with candidate. Require it is the latest attempt by attempt_number and no prepared/dispatched/later attempt exists. Preserve retry_count/max_attempts, lease token, all attempt columns and source identity unchanged. Ambiguous delivery/configuration, missing/null/malformed response, any other failure or later/current job fails closed.

Rebuild normalized source from immutable captured source/context exactly as current `full_candidate_validation` does. Independently prove the original `_check_introduction` raises precisely REWRITE_TECHNICAL_MUTATION. For correction require the complete existing response shape, changed introduction, and `correction['replacements'] == attempt['response']['replacements']` structurally (no rewritten or reordered body entries). Run unchanged `render_full(source, correction)` and `validate_full(..., response=correction)`; require passing report and exact retention rationale coverage. This validates every body leaf, slot, token, structure, image and introduction without ever disabling a check or rendering the invalid original. A malformed body fails even when the intro was also invalid. Neither correction nor machine success proves semantic uniqueness or content fidelity.

`export-failed` writes source/context/images privately as normal, `candidate.json` as `{state:'failed_unrendered', response:<retained raw response>}`, reviews=[], and manifest with normal bindings, attempt ID/hash/status/error, prompt provenance and `rendered_candidate_available:false`. It must not present source placeholder as model candidate, claim validation passed or print prose. Export checks original intro failure and all source/attempt integrity; complete body validity is established by a submitted valid correction before mutation.

## Append-only correction provenance

Retain ordinary five-field correction dictionaries unchanged. Permit a second exact correction shape with those fields plus `failed_origin`; enforce this exact nested shape:

```json
{
  "schema": "autodata:failed-full-prose-correction:v1",
  "attempt_id": "canonical UUID",
  "attempt_status": "failed",
  "error_code": "REWRITE_TECHNICAL_MUTATION",
  "input_hash": "64 lowercase hex",
  "prompt_hash": "64 lowercase hex",
  "response_hash": "64 lowercase hex",
  "placeholder_hash": "64 lowercase hex"
}
```

The existing original_candidate_hash equals the pre-correction saved placeholder_hash and must equal source hash for this variant; it is never asserted to be an invalid rendered output. Existing response/response_hash bind corrected response, final_candidate_hash binds its unchanged-renderer result, actor identifies the human correction author. The referenced failed DB response remains the immutable original model evidence; do not duplicate its prose into tracking or overwrite any attempt field.

In one transaction, `correct-failed` writes the rendered document, projection, validation report/hash and result hash to the SAME candidate, sets status validated, appends a REJECTED review with failed_origin provenance, and changes job to needs_review/publishing with CONTENT_REVIEW_REQUIRED, retryable=false and content_review version1/awaiting_review exact candidate/hash/review_id; checkpoint.validation_hash agrees. ONLY after eligibility, unchanged-body render/validation and the append-only REJECTED provenance review insert have succeeded, remove the active checkpoint.rewrite_error_code key in this same locked transaction (SQL checkpoint subtraction before merging the new content_review/validation fields). Preserve the immutable failed attempt error_code/status/response/hash and failed_origin.error_code as historical evidence. Never retain the historical error as an active checkpoint flag: article_lifecycle.py:127-139 intentionally stops any saved candidate while that flag is truthy. Any validation, candidate write, review insert or job/checkpoint update failure rolls back all changes, including retaining the original active checkpoint.rewrite_error_code. Pointer and publication_events stay unchanged. A duplicate old-binding call fails stale; there is no transient publishable approval.

For subsequent normal export, correction and approval, reconstruct failed_origin from the referenced immutable attempt/source and corrected response. The original is represented by the saved source placeholder for provenance hash only; use raw failed response equality plus failed-introduction rejection to establish its origin. Additional ordinary corrections may change only introduction while carrying identical failed_origin/placeholder_hash; all original replacements remain exact. Later reviews carry that same provenance. At approval require authorized human different from every drafting identity and correction actor, explicit full_content_reviewed true, substantive rationale and complete retention rationale set. Fresh source/candidate/attempt/hash/generation bindings are mandatory.

Use one shared full-prose evidence resolver in article_content_review.py (`resolve_full_evidence(cur, job, candidate)`) returning attempt, original placeholder-or-rendered document, effective response and correction provenance. It must validate normal succeeded evidence exactly as today or this fully bound failed-origin variant; no generic `status IN ('failed','succeeded')` relaxation. Source/prompt proof remains mandatory. Use it in review reconstruction, `full_candidate_validation`, `_require_full_approval` identity checks and `publish_article_revision` attempt binding. `publish_article_revision` and worker resume still independently require validated candidate, complete exact latest independent approval, current owner, immutable source, renderer/report/projection and atomic pointer+job+outbox commit. Failed attempt remains failed forever. Published immutable trigger and canonical/event uniqueness stay intact.

## Historical prompt hash compatibility

Prompt-v2 at02f863c changes prompt bytes without changing profile. Current full_candidate_validation rebuilds current prompt only and therefore would reject the retained v1 attempt even after a good correction. Add private `_matches_full_prompt_hash(document, *, context, prompt_hash) -> bool` in procedure_rewrite_full.py. Reconstruct exactly two known prompt payloads with unchanged deterministic JSON serialization: current build_full_prompt(v2), and historical v1 payload atd123bbf obtained by omitting prompt_version, introduction_allowed_technical_tokens and exactly the one context/document disambiguation rule added by02f863c. Verify synthetic byte-for-byte legacy golden against that source. Hash must equal one reconstructed value; reject unknown hashes. Current `build_full_prompt` remains v2 only for every new request. No prompt supplied by caller/DB is accepted as authority, no profile/grammar/validator change and no broad hash exemption. Use matcher for full-prose evidence revalidation only; other profiles keep existing prompt logic.

## File scope and acceptance

Prospective code/test allowlist follows; no SQL/worker scheduler/API/UI/dependency/infra edits. In particular article_lifecycle.py remains outside the allowlist: preserve its rejecting active-error guard and repair only the authorized successful correction transaction:
- `workers/ingestion-python/src/autodata_ingestion/article_content_review.py`
- `workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py`
- `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite_full.py`
- `workers/ingestion-python/tests/test_article_content_review.py`
- `workers/ingestion-python/tests/test_procedure_rewrite_full.py`
- `workers/ingestion-python/tests/test_article_lifecycle_integration.py`
- `scripts/dev/article_content_review.py`
- `scripts/dev/test_article_content_review.py`


Required acceptance with synthetic captured source and a real isolated lifecycle fixture database: source with nine rewrite leaves; original attempt1 ambiguous unchanged; attempt2 failed intro mutation and source-placeholder candidate; no more model calls. Private export exposes original response with correct labels. Correction changes only intro, leaves every original attempt field and retry_count/max_attempts unchanged, keeps one revision and source selection, appends rejection, and removes the active checkpoint.rewrite_error_code key only at successful commit. Assert key absence explicitly; failed attempt/error/hash and failed_origin.error_code remain exact. Inject failure after candidate write, rejected review insert and job/checkpoint update; every rollback must retain the original active error, unchanged attempt rows/budget, original building placeholder and zero new reviews. Independent human fixture approval schedules saved-candidate publishing; same actor/model/synthetic outside fixture and incomplete review cannot approve. Drive the real run_article_job entry point, not direct publication helper calls, with a model client that raises if invoked and a source client that rejects fetches. Before independent full approval the corrected needs_review job cannot be claimed/published; after exact independent full approval real worker resume must publish the same revision exactly once/outbox once, with zero model/source requests. A saved uncorrected failed job retains its active rewrite error and the existing worker guard continues to block it. Warm reads retain no further calls. Source fallback persists after rejection, failed correction, stale approval or process loss before atomic publication.

Negative matrix: tamper each origin/binding/prompt/source/report/projection/response field independently; alter replacement body, stale generation/current job/source/profile, wrong attempt ID/hash/status/error, missing response, later in-flight attempt, arbitrary legacy hash, original intro valid/different error, unsupported failure class, published/rejected/validated starting candidate, existing review, lease, self-approval, missing complete-review attestation/retention rationale; all reject with no DB changes. Exercise concurrent corrections/approval/source change under same lock order and injected rollback during candidate/review/job updates and publication. Existing normal succeeded review, human correction, rejection, exact idempotent approval and all other profile tests remain green.

Runtime recovery is a separate coordinator dispatch after implementation review. A qualified correction author and independent qualified full-content human reviewer must exist in the private allowlist. Compare every source instruction and all nine body leaves, introduction, safety/conditions/negation, tables/media/references and any retained prose; a model or this planning agent cannot supply that approval. Any failed human or mechanical check leaves source fallback and original records intact; do not spend a model attempt as an automatic fallback.

## Concrete todo

- [ ] Preserve Issue186 and all Project8 fields; synchronize this recovery goal, plan, canonical spec and concrete todo, commit/push a documentation checkpoint and pass exact-SHA preflight before coordinator implementation dispatch.
- [ ] Add synthetic failed-introduction and legacy-prompt provenance regressions; implement the narrowly bound private failed-draft export/correction path without changing renderers, validators, attempt history, retry budget or canonical uniqueness.
- [ ] Revalidate corrected responses and failed-attempt provenance at export, independent approval, saved-candidate resume and atomic publication; atomically remove only the active checkpoint.rewrite_error_code after successful rejected provenance review, prove rollback retains it, and verify true run_article_job resume with a model-raises client publishes only after independent full approval.
- [ ] Run pure review/prompt/CLI regressions and isolated lifecycle database acceptance tests; commit/push coherent code milestones and obtain independent exact-SHA review before any private runtime operation.
- [ ] After separate coordinator authorization only, export the retained failed draft privately, correct only its introduction, obtain independent complete human technical review and publish the same revision at most once; retain source fallback if any requirement fails.

## Tracking synchronization evidence

Issue186 comment https://github.com/lucronn/autodata/issues/186#issuecomment-6673413206; Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, Release hotfix reference `PVTF_lAHOCSJ8cc4BiQ2BzhoxGVY` appends the recovery pointer after the complete prior value. Issue body, all302 prior comments and all other fields preserved exactly by readback, with snapshots/hashes in `/home/corp/autodata-evidence/failed-draft-recovery-gate/preservation.json`. Checkpoint full SHA and machine preflight are sealed externally after commit; this cannot imply human content approval or runtime authorization.

## Independent checkpoint-review amendment

Checkpoint a2f4efc incorrectly left historical rewrite_error_code active in the job checkpoint. Real run_article_job rejects that state at article_lifecycle.py:127-139 before saved-candidate validation/publication. This amendment requires atomic removal of only that active key after successful corrected validation and REJECTED provenance review; failed attempt and failed_origin retain historical error/hash evidence. DB assertions cover absence after commit, original attempts/budget preservation, rollback retaining active error, and real worker resume after independent full approval. Eight-path allowlist stays unchanged; article_lifecycle.py is excluded. Amendment Issue reference and amended exact checkpoint/preflight follow append-only tracking synchronization.

Amendment synchronized: https://github.com/lucronn/autodata/issues/186#issuecomment-6673446586. Exact readback preserves Issue body/all304 predecessor comments and every Project8 field with no Project mutation. Evidence `/home/corp/autodata-evidence/failed-draft-recovery-gate/amendment/preservation.json`. The amended exact committed SHA and machine preflight are sealed externally after commit; original a2f4efc is superseded for implementation dispatch.
