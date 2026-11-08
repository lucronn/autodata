# Workshop saved article links during index preparation

`loadArticles()` currently throws an article-unavailable error whenever a saved ID is absent from the latest article-index response. A bounded `readCollection()` result can still be incomplete, so this result is not proof that the article is absent. The correction keeps the saved target across manual retry and reserves the definitive unavailable error for a completed index.

Acceptance and verification:

- [ ] A missing saved ID in an incomplete hydrated index reports preparation and retains the same ID for Retry; a later index containing the ID opens it.
- [ ] An ID present in a partial index still opens immediately; a completed index without the ID still reports unavailable.
- [ ] A terminal failed index without the ID reports the index failure, not a definitive article-missing result.
- [ ] Focused red/green regression, full Workshop client/demo Node tests, Go API tests, JavaScript syntax, and diff checks pass on the exact candidate.
- [ ] Independent review and required CI pass before integration.

This is local client-behavior evidence, not live article-access, payment, or production-release acceptance.

Tracking: [Issue #379](https://github.com/lucronn/autodata/issues/379) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-saved-article-pending.md).
