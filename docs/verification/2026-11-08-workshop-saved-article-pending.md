# Workshop saved article links during index preparation

`loadArticles()` currently throws an article-unavailable error whenever a saved ID is absent from the latest article-index response. A bounded `readCollection()` result can still be incomplete, so this result is not proof that the article is absent. The correction keeps the saved target across manual retry and reserves the definitive unavailable error for a completed index.

Acceptance and verification:

- [x] A missing saved ID in an incomplete hydrated index reports preparation and retains the same ID for Retry; a later index containing the ID opens it.
- [x] An ID present in a partial index still opens immediately; a completed index without the ID still reports unavailable.
- [x] A terminal failed index without the ID reports the index failure, not a definitive article-missing result.
- [x] Focused red/green regression, full Workshop client/demo Node tests, Go API tests, JavaScript syntax, and diff checks pass on the local candidate.
- [ ] Independent review and required CI pass before integration.

This is local client-behavior evidence, not live article-access, payment, or production-release acceptance.

The baseline Workshop client/demo Node and full Go API suites passed before this change. Three actual-`loadArticles()` tests were added. Before the browser edit, the pending and terminal-failed missing-ID tests failed with `This article is unavailable for the selected vehicle.`; the completed-index absence control passed. After the minimal branch edit, all three focused cases passed. The full Workshop client/demo Node suite, Go API suite (`ok github.com/lucronn/autodata/apps/api-go 8.619s`), `node --check`, and `git diff --check` passed on the working tree. Exact committed candidate and CI disposition are tracked in Issue #379 and its PR.

Tracking: [Issue #379](https://github.com/lucronn/autodata/issues/379) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-saved-article-pending.md).
