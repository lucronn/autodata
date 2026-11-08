# Workshop Selector Success Retry Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide the Workshop's “Try again” button after a successful vehicle-selector read while preserving retry for failed or incomplete reads.

**Architecture:** No architecture change. Keep the existing selector request, collection polling, navigation generation, and shared status renderer; omit the retry callback only from the successful `loadOptions` status call.

**Tech Stack:** Browser JavaScript, Node's built-in test runner, and the existing VM-based Workshop client test harness.

**Spec:** `docs/superpowers/plans/2026-11-07-selector-failure-ui.md` defines incomplete and failed selector behavior. `docs/superpowers/specs/2026-11-03-source-fallback-web-design.md` defines the broader Workshop browse boundary.

**Tracking:** [Issue #373](https://github.com/lucronn/autodata/issues/373) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and [verification record](../../verification/2026-11-08-workshop-selector-success-retry.md).

## Global Constraints

- Do not change selector routes, response parsing, polling limits, saved-choice resume, or the purchase flow.
- Successful completed choices, completed empty choices, and a saved row found during partial hydration must not expose a retry action.
- Failed and incomplete reads without a usable desired row must keep their existing retry action and visible “Try again” button.
- Preserve partial selector rows and navigation-generation cancellation.
- Change only Workshop browser presentation, its Node tests, and required tracking documents.

---

## Concrete todo

- [ ] Exercise the real status renderer in the selector test harness and write a failing success-state button regression.
- [ ] Remove the retry callback from the successful selector status call without changing failure behavior.
- [ ] Run focused and full Workshop Node tests, Go API tests, syntax and diff checks; review and push the scoped change.

### Task 1: Selector status and retry visibility

**Files:**
- Modify: `apps/api-go/workshop-client.test.mjs` (`selectorOptionsHarness` and selector outcome cases)
- Modify: `apps/api-go/workshop/app.mjs` (`loadOptions` success status)
- Update: `docs/verification/2026-11-08-workshop-selector-success-retry.md`

**Interfaces:**
- Consumes: `readCollection` result (`items`, `complete`, `timedOut`) and the current generation.
- Produces: existing `#activity` text and `#retry` button state through `status()`; no API or data-contract change.

- [ ] **Step 1: Make the test harness exercise the real status renderer.** Give its test nodes `hidden`, `textContent`, and `dataset` fields. Evaluate the existing `function status(` section of `app.mjs` alongside `operation` and `loadOptions`, wrapping it only to capture the message/options already asserted by tests. Keep the real `status()` call responsible for setting `#retry.hidden` and `retryAction`.
- [ ] **Step 2: Write the failing behavior test.** For completed nonempty, completed empty, and partial-with-saved-choice responses, call the actual `loadOptions` path and assert `#retry.hidden === true` and `retryAction === null` after success. Extend existing timeout and request-failure cases to assert `#retry.hidden === false` and a callable retry action. The success test must fail on the current branch because `loadOptions` passes `retry: () => restoreRoute()` even after success.
- [ ] **Step 3: Run the focused red test.** Run `node --test --test-name-pattern='selector success hides retry' apps/api-go/workshop-client.test.mjs`; expect the success button assertion to fail because `#retry.hidden` is false. Ensure the harness itself passes its existing selector tests before treating this as a product failure.
- [ ] **Step 4: Implement the minimal fix.** In the successful `loadOptions` `status()` call, omit the `{ retry: () => restoreRoute() }` option. Leave `operation()`'s catch retry callback and the incomplete/timeout branches unchanged.
- [ ] **Step 5: Verify and commit.** Run the focused test, `node --test apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`, `/home/corp/.local/go1.23.4/go/bin/go -C apps/api-go test -count=1 ./...`, `node --check apps/api-go/workshop/app.mjs`, and `git diff --check`. Review the diff for unchanged request/auth/commerce boundaries, commit the scoped paths, and push the feature branch for review.
