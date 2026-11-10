# Workshop article search and step descriptions

**Goal:** The ingestion article-query utility can find terms in a selected
vehicle's article summary, description, or structured blocks, and a procedure
step whose source supplies only a description retains its displayed instruction.

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
- [x] The JSON bound-article source adapter forwards description and nested
  instruction fields to document normalization, so an actual fetched article
  does not collapse to a numbered placeholder.
- [x] A normalized step or list label that the Workshop renderer hides does
  not create a local article-search match by itself; displayed callout and
  table labels remain searchable.
- [x] The same hidden-label behavior holds after the full document normalization
  path projects compatibility `body` and `steps` fields.
- [x] JSON bound-article adaptation uses populated `steps` when `blocks` is
  empty and does not let whitespace-only step text shadow a valid instruction.
- [x] Nested callout image captions and list/table object labels that Workshop
  does not render cannot create local article-query matches.
- [ ] Focused and full ingestion tests, exact-head independent review, required
  GitHub CI, and branch protection pass before integration.

The implementation changes only article lookup and ordered-document text
fallbacks. It does not change article schemas, source fetch, checkout, grants,
prices, production service state, or live content availability. The public
Workshop origin currently returns 502; these tests do not prove live article
delivery or paid-access acceptance. The Workshop UI search box uses a separate
`filterArticles` path that currently searches only title, component, and kind;
this Python utility is not wired to it. This slice does not fix UI content
search, which needs a separate tracked task.

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

Independent re-review of head `a84fee2f9f021275b6767680b4ce36e42d22501d`
found two further end-to-end gaps: `adapt_bound_article` drops description and
instruction fields from JSON `steps` before normalization, and search indexes
the label of a normalized step even though the Workshop renders only its text,
action, instructions, and images. These source-to-UI boundaries must have
red-first regression coverage and a fresh exact-head re-review before merge.
The same renderer omits normalized list labels, so the visibility correction
will use rendered block types rather than a step-only exception.

The adapter-path test failed first with `Step 1` and passed after forwarding
the source step's description and instructions. Hidden normalized step and
list labels each failed their negative search tests before the rendered-field
correction, while displayed callout and table labels were positive controls.
After the correction, the focused query/document/adapter suites passed 87
tests and 62 subtests. The full ingestion suite passed 1,186 tests, 475 skips,
and 180 subtests at code head `cdd424e7fab2267d4d73bc787f31beba37eaa785`;
Python compilation and `git diff --check` passed. This evidence is local and
does not establish live origin, purchase, or grant readiness. Final exact-head
review and CI are still pending.

Independent review of `eed84300596a7547dc95b4cf984c74e013b0c514`
reproduced three additional gaps. Compatibility `body` generated from a
normalized document reintroduces hidden step/list labels into lookup. The
JSON adapter treats empty `blocks` as authoritative over populated `steps` and
lets whitespace-only `text` shadow valid `instruction`. Nested image/list/table
objects can contribute caption/label text that the Workshop renderer hides.
These are merge blockers for this bounded slice; add red-first source-path
regressions and correct them before claiming exact-head review or CI complete.

Planning checkpoint `18b2638` passed exact-SHA preflight (`status:
synchronized`, no errors) before the final correction phase. The new full
normalization, nested rendered-field, empty-block, and whitespace-shadow
regressions failed for the expected behavior before implementation (eight
failures, including six subtest failures), then passed. Focused
query/document/adapter suites passed 91 tests and 74 subtests. The full
ingestion suite passed 1,190 tests, 475 skips, and 192 subtests at code head
`5aba33bc7d211288cc1b0ff92f02ac5a98ba0705`; Python compilation and
`git diff --check` passed. The source adapter now falls back to populated
steps when `blocks` is empty and preserves candidate fields independently.
Lookup treats a nonempty normalized document as authoritative over projected
compatibility fields and searches nested objects by what Workshop renders.
This does not wire Python lookup to the Workshop UI; that feature is tracked
as [Issue #393](https://github.com/lucronn/autodata/issues/393).

Plan: [2026-11-10-workshop-article-search-step-description](../superpowers/plans/2026-11-10-workshop-article-search-step-description.md).
