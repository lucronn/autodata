# Workshop article search and step descriptions

**Goal:** A consumer searching a selected vehicle's article content can find
terms in an article summary, description, or structured blocks, and a procedure
step whose source supplies only a description still displays its instruction.

This is a bounded content-correctness slice of [Issue #184](https://github.com/lucronn/autodata/issues/184)
in [Project #8](https://github.com/users/lucronn/projects/8). The article query
currently searches title/body/steps but omits `summary`, `description`, and
`blocks`. The ordered-document step normalizer currently falls back through
text/action/instruction/value/content/body, but omits a step's `description`
and an instruction item's `description`.

Acceptance:

- [x] A local article match in each of `summary`, `description`, and `blocks`
  returns `found` without invoking the source fallback.
- [x] A source step whose only instruction text is its `description` produces a
  valid ordered `step` block with that text.
- [x] A source step whose only instruction text is an instruction item's
  `description` produces a valid ordered `step` block with that text.
- [x] A normalized article with visible text only in
  `normalized_document.blocks` is found locally; block type/key metadata alone
  is not treated as visible searchable text.
- [x] A step with both a description and nested instructions retains both
  pieces of consumer-visible text, and a whitespace-only instruction `text`
  does not hide its nonempty `description`.
- [ ] Focused and full ingestion tests, exact-head independent review, required
  GitHub CI, and branch protection pass before integration.

The implementation changes only article lookup and ordered-document text
fallbacks. It does not change article schemas, source fetch, checkout, grants,
prices, production service state, or live content availability. The public
Workshop origin currently returns 502; these tests do not prove live article
delivery or paid-access acceptance.

Planning checkpoint `f31e19e4467bc17bac7201ecbf8774d44c2f79b5` passed
`scripts/autonomy/pre_implementation.py` with `status: synchronized` and no
errors before implementation. Three new article-search tests failed on that
base because lookup missed the local fields and called the forbidden source
fallback; all six query tests passed after the field addition. Two new
description-only step tests failed with placeholder text (`Step 1`/`Step 2`);
they passed after the fallback addition. The focused article suite passed
49 tests. The full ingestion suite passed 1,178 tests, 475 skips, and 178
subtests on implementation head `d5052617f7381d8dc55105c649c297cad0db3932`.
Python compilation and `git diff --check` also passed.

The first full-suite attempt had four environment failures: this runner's
`/tmp/.git` marker violated private-path test fixtures, and the declared
`stripe==16.1.0` dependency was absent. A second attempt used a temporary
`/dev/shm` directory that the runner did not preserve between calls, causing
pytest setup errors. The passing run created that private temp directory in
the same command and provided the project's pinned Stripe dependency from an
isolated temporary installation. Neither workaround changed repository code.

Exact-head independent review, GitHub CI, and branch-protection checks remain
required before merge. Issue #184 remains open for its other hardening work.

Independent review of initial PR #392 head `9940bfedfb0df5cc53948627799f38d619febe74`
found four reproducible content gaps: normalization removes top-level `blocks`
after placing them in `normalized_document.blocks`; block stringification
indexes metadata such as `type: paragraph`; a step `description` wins over and
hides nested instructions; and whitespace-only item `text` hides a nonempty
item `description`. The PR is not merge-ready until red-first regressions for
these cases pass, the code is corrected, and the final head is re-reviewed.

Review correction: the four new regressions failed for the expected missing
behavior before code changes and passed afterward. Search now traverses only
consumer-visible text fields in top-level `steps`/`blocks` and
`normalized_document.blocks`; structural keys, block types, IDs, image URLs,
and evidence metadata are excluded. Step descriptions and cleaned nested
instructions are both retained when no higher-priority step text exists.
The focused article suite passed 53 tests; the full ingestion suite passed
1,182 tests, 475 skips, and 178 subtests on code head
`2ccd549c5e9b0658a9ab3cf6b41d3099a826d988`. Python compilation and
`git diff --check` passed. Fresh exact-head review and PR CI remain gates.

Plan: [2026-11-10-workshop-article-search-step-description](../superpowers/plans/2026-11-10-workshop-article-search-step-description.md).
