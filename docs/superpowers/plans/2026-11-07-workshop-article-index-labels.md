# Workshop Article Index Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Workshop's real article index show each article type and describe empty search, empty completed index, and pending index states accurately.

**Architecture:** Keep the existing protected article list and its ordering. The browser renderer will add a text label beside each title and use the collection's explicit completion flag to choose the empty message. No API, entitlement, checkout, source, or article data contract changes.

**Tech Stack:** Plain browser JavaScript, semantic HTML, CSS already in `apps/api-go/workshop/styles.css`, Node's built-in test runner.

**Spec:** `docs/superpowers/specs/2026-11-03-source-fallback-web-design.md` (existing Workshop browse and reader contract).

**Tracking:** [Issue #371](https://github.com/lucronn/autodata/issues/371), [Project #8](https://github.com/users/lucronn/projects/8), and [verification record](../../verification/2026-11-07-workshop-article-index-labels.md).

## Global Constraints

- Keep the protected article list inaccessible before the existing server entitlement check.
- Preserve article order, IDs, link URLs, search matching, and navigation cancellation.
- Use text nodes for source-provided titles and kinds; never insert provider HTML.
- An incomplete index must not be presented as authoritatively empty.
- Change only the Workshop presentation, its focused Node tests, and required tracking documents.

---

## Concrete todo

- [ ] Add failing browser tests for article type rows and the three empty states.
- [ ] Render type and truthful empty copy without changing protected reads or article links.
- [ ] Run focused and full checks, then push the scoped change for review.

### Task 1: Article row type and empty-state presentation

**Files:**
- Modify: `apps/api-go/workshop/app.mjs` (`clearProtected`, `loadArticles`, `renderArticles`)
- Modify: `apps/api-go/workshop/index.html` (`#no-results` default copy)
- Test: `apps/api-go/workshop-client.test.mjs` (`articleIndexHarness` and focused list cases)

**Interfaces:**
- Consumes: the existing `readCollection` result with `items` and `complete`, plus each article's `title`, `kind`, and `id`.
- Produces: the existing list of same-origin article links with title and type text; `#no-results` reflects query and completion state.

- [ ] **Step 1: Write the failing tests.** Extend the existing `articleIndexHarness` with an `indexComplete` state and assert a procedure row contains separate title and `Procedure` text spans, its article URL still contains the original ID, and an unknown kind is displayed as readable text. Assert that a nonmatching query says no articles match, a completed empty index says no articles are available, and a pending empty index says the index is still being prepared.
- [ ] **Step 2: Run the focused red tests.** Run `node --test --test-name-pattern='article index type|article index empty' apps/api-go/workshop-client.test.mjs`; each new assertion must fail because the current renderer omits type or uses the search-only empty copy.
- [ ] **Step 3: Implement the minimal browser change.** In `renderArticles`, append a title `<span>` and type `<span class="article-type">` to the existing link, preserving its handler and URL. Format the kind as plain text by replacing separators with spaces and capitalizing the first letter, with `Article` for a missing kind. Track `result.complete === true` in `loadArticles`, reset the flag in `clearProtected`, and choose the three empty messages from query text and the completion flag. Keep the existing `<ul>` list and add `role="list"` because its CSS removes list markers outside navigation.
- [ ] **Step 4: Run green and regression checks.** Run the focused Node command, then `node --test apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`, `go -C apps/api-go test ./...`, and `git diff --check`. Review the final diff for unchanged auth, commerce, and API boundaries.
- [ ] **Step 5: Commit and push the validated app change.** Commit only the scoped app, test, and tracking paths with a clear message; push the feature branch and open a PR linked to the dedicated issue and Project #8 item.
