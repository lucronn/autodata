# Workshop table-row image deduplication

**Goal:** A row-attached image in a normalized Workshop table remains in its table and is not repeated as an unrelated trailing figure when the article-level media list references the same image.

This is a bounded slice of [Issue #184](https://github.com/lucronn/autodata/issues/184) in [Project #8](https://github.com/users/lucronn/projects/8). The normalized article document remains the authoritative display order, and a genuinely unattached article-level image must still be queued after the table. No source bytes, schema, payment, grant, or production-service behavior changes.

## Acceptance and evidence

- [ ] A red-first test reproduces the duplicate `row-image` trailing block on the planning base.
- [ ] The ordered document has one table block containing `row-image`, followed only by the distinct `unattached-image` block.
- [ ] Focused and full ingestion tests, syntax/diff checks, independent exact-head AI review, required CI, and branch protection pass before merge.

Plan: [Workshop table-row image deduplication](../superpowers/plans/2026-11-10-workshop-table-row-image-dedup.md). The live Workshop origin 502 remains separately tracked in [Issue #391](https://github.com/lucronn/autodata/issues/391); local tests do not prove live paid-access acceptance.
