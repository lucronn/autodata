# Workshop table-row image deduplication

**Goal:** A row-attached image in a normalized Workshop table appears once beside that table in the reader, not again as an unrelated trailing figure when the article-level media list references it.

This is a bounded slice of [Issue #184](https://github.com/lucronn/autodata/issues/184) in [Project #8](https://github.com/users/lucronn/projects/8). The normalized article document remains the authoritative display order, and a genuinely unattached article-level image must still be queued after the table. No source bytes, schema, payment, grant, or production-service behavior changes.

## Acceptance and evidence

- [x] A red-first test reproduces the duplicate `row-image` trailing block on the planning base.
- [x] The ordered document has one table block containing `row-image`, followed only by the distinct `unattached-image` block.
- [x] Red-first reader tests show the row image directly after the semantic table on both source and canonical paths; ID-less and missing assets use the unavailable fallback rather than an unrelated pool image, and cell images are not repeated.
- [ ] Focused and full relevant tests, syntax/diff checks, independent exact-head AI review, required CI, and branch protection pass before merge.

Planning checkpoint `070c31f2d804a2e8a941782d8b74fad078626e7c` passed the exact-SHA machine preflight with `status: synchronized` and no errors before implementation. The regression failed first because the ordered document had three blocks (`table`, duplicate `image`, unattached `image`), then passed after the pre-scan included row mapping images. All 46 focused document tests passed. Full ingestion verification passed 1,191 tests, 475 skips, and 192 subtests at code commit `e7716076d96f71f9762de179619a84b5219243bb`; Python compilation and `git diff --check` passed.

The first full-suite attempts could not establish a code result because this sandbox denied local fixture sockets and then reused `/tmp` instead of a private temp directory outside its `.git` marker. A final run created a private `/dev/shm` temp directory and ran the suite in the same permitted process, without changing repository code or live services.

Independent review at `4bd430dde4fd1345ebfc1a0be4632d9ee33add45` found an important reader regression: suppressing the trailing figure would hide a row-attached image because the Workshop table branch ignored `block.images`. PR #395 was marked draft. This amended plan adds a red-first reader test and bounded renderer correction before a fresh exact-head review and CI gate. The existing source/canonical article image pool remains the only permitted media URL source.

The amended planning checkpoint `3a326f1bcc1bd236919e0a2a2f41c0ea47846dff` passed the exact-SHA machine preflight with `status: synchronized` and no errors before the reader implementation. Five initial named Workshop reader regressions failed because table-block figures were absent. After the table renderer correction at `bbb631dfe77486dd26b52bf67bd1df354e1c1eee`, six named cases and all 255 Workshop client tests passed; all 46 focused Python document tests passed. JavaScript syntax and `git diff --check` passed. The full ingestion suite result above remains applicable because its Python implementation was unchanged. Local Go tests could not run: `go` is not installed in this environment, so required CI remains an explicit merge gate.

Plan: [Workshop table-row image deduplication](../superpowers/plans/2026-11-10-workshop-table-row-image-dedup.md). The live Workshop origin 502 remains separately tracked in [Issue #391](https://github.com/lucronn/autodata/issues/391); local tests do not prove live paid-access acceptance.
