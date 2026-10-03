# Repair legacy ordered article documents without source calls

**Issue:** https://github.com/lucronn/autodata/issues/111  
**Project:** https://github.com/users/lucronn/projects/8  
**Canonical contract:** `docs/architecture/normalized-article-document.md`  
**Planning base:** `ce33b3c8828068e7eb3115b3f0f64d13d79dd5c8`

## Goal

Repair selected catalog articles whose rows claim `content_complete` but have
an empty ordered document, using the immutable source copy already stored with
the article. This must preserve the provider document's original order and
image positions, avoid every upstream source call, retain the exact original,
and update the existing canonical row without creating another list-only/detail
row.

## Reproduced failure

On the running local database, the selected list-row ID for the 2012 Ram 1500
DS axle article resolves to the same provider article identity as a complete
detail row. The complete row has stored source HTML and compatibility body and
steps, but its `normalized_document.blocks` array is empty. The legacy local
runtime serves the list-only row as unreadable. The current branch has a body
fallback in Workshop, but no stored-source repair path rebuilds the authoritative
ordered document. The API and worker containers currently running locally
predate this branch, so the regression must be proved against a fresh candidate
running the current implementation.

## Concrete todo

- [x] Treat an empty or invalid ordered document as repair-needed even when a
  legacy row is marked `content_complete`.
- [x] Load the existing immutable source snapshot by canonical article and
  vehicle identity; never call AutoAPI or AutoAPItwo for article/catalog data,
  and never call an LLM for this repair.
- [x] Reparse the stored source through the existing provider adapter/parser
  and verify the selected article identity; rebuild from the already-normalized
  ordered steps and attached image references so prior DIY wording, step order,
  and image positions remain intact.
- [x] Reuse already-localized image assets. If a referenced image is not stored,
  fetch only that image resource once through the existing allowlisted image
  adapter, persist it locally, and serve it through an AutoData URL. A failed
  media read remains an unavailable block at its source position; never move it
  to a detached gallery.
- [x] Update the existing canonical article row idempotently, preserve the
  source snapshot and byte-identical `source_original`, and avoid duplicate
  list-only/detail rows.
- [x] If the stored source cannot be parsed or validated, mark the row partial
  and return a concrete repair/source failure; do not claim complete content.
- [x] Add failing-first regressions for the stored-source repair, zero upstream
  calls, order/image preservation, idempotence, and list-row alias resolution.
- [ ] Run focused Python/Go/Workshop tests and a clean isolated Compose replay
  against a copied candidate database; verify no article/catalog provider or
  LLM request occurs, each missing image is fetched at most once, the source
  snapshot remains unchanged, and a repeat repair makes no image request.
- [x] Update Issue #111, Project #8, and this plan with exact test and runtime
  evidence; rerun the complete hosted stack checks.

## Verification at implementation commit `95381f4`

- Worker suite: 369 passed, 3 skipped.
- Go API tests and `go vet ./...` passed.
- Python compileall, Compose configuration, and `git diff --check` passed.
- Both hosted Autonomous Verification runs passed, including the live Compose
  fast-lane: [37108159899](https://github.com/lucronn/autodata/actions/runs/37108159899)
  and [37108163117](https://github.com/lucronn/autodata/actions/runs/37108163117).
- The copied-candidate database replay and Workshop verification remain open;
  the running user database was not used or modified.

## Design constraints

- The immutable raw source is reference material and is never overwritten.
- Existing non-empty valid ordered documents remain authoritative and are not
  regenerated on ordinary reads.
- Repair is deterministic and idempotent; it does not reorder, deduplicate,
  rewrite, infer missing steps, or synthesize facts.
- Source images remain at their stored source positions. Only missing image
  assets may be fetched once; the repair never re-fetches article/catalog data.
- A repair failure is explicit and retryable only after the stored input or
  parser changes; it must never be converted into a successful empty article.
- The user's running database is not used as the test target; use an isolated
  candidate copy and leave the current runtime untouched.

## Acceptance

- A legacy `content_complete` row with non-empty stored source and an empty
  ordered document repairs to a valid non-empty document from stored bytes.
- Every resulting block's `source_order` matches parser source order; existing
  images retain their positions and evidence references.
- Article/catalog connector and LLM call counters remain zero. Each missing
  image asset is fetched at most once and is reused on subsequent reads.
- The same request twice returns the same canonical article ID and content hash
  without adding rows or changing the immutable source snapshot.
- A malformed stored source becomes explicitly `content_partial` with a
  readable failure state and no upstream retry.
- The list-row URL resolves to the repaired complete canonical detail row and
  renders readable ordered content in Workshop.
