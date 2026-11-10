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

- [ ] A local article match in each of `summary`, `description`, and `blocks`
  returns `found` without invoking the source fallback.
- [ ] A source step whose only instruction text is its `description` produces a
  valid ordered `step` block with that text.
- [ ] A source step whose only instruction text is an instruction item's
  `description` produces a valid ordered `step` block with that text.
- [ ] Focused and full ingestion tests, exact-head independent review, required
  GitHub CI, and branch protection pass before integration.

The implementation changes only article lookup and ordered-document text
fallbacks. It does not change article schemas, source fetch, checkout, grants,
prices, production service state, or live content availability. The public
Workshop origin currently returns 502; these tests do not prove live article
delivery or paid-access acceptance.

Plan: [2026-11-10-workshop-article-search-step-description](../superpowers/plans/2026-11-10-workshop-article-search-step-description.md).
