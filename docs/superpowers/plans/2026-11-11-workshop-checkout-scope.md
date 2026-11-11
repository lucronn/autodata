# Workshop Checkout Scope Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a rapid selected-vehicle change from reusing another vehicle's in-flight Checkout result, while preserving same-scope deduplication and idempotency.

**Architecture:** Keep the current one-at-a-time Checkout client and session-storage attempt. Associate the in-flight promise with its exact configuration/region and signal. Same-scope callers share a live request; a different scope or an already-aborted request waits for settlement and then starts a fresh validated attempt. This is a bounded client change, not a payment or grant contract change.

**Tech Stack:** Browser ES module, Node built-in test runner.

**Spec:** `docs/verification/2026-11-11-workshop-checkout-scope.md`.

**Issue:** https://github.com/lucronn/autodata/issues/396

**Project:** https://github.com/users/lucronn/projects/8

## Global constraints

- Change only `apps/api-go/workshop/commerce.mjs` and `apps/api-go/workshop-client.test.mjs` after the planning checkpoint.
- Preserve the existing Checkout URL, quote, response, CSRF, and idempotency-key contracts.
- Never start two different-scope Checkout requests concurrently. Never issue a queued request after its navigation signal aborts.
- No Stripe API, backend, schema, price, entitlement, production service, DNS, or traffic changes.

## Concrete todo

- [ ] Commit this plan, the verification spec, and a synchronized record; read back Issue #396 and Project #8; pass exact-SHA machine preflight.
- [ ] Add red-first overlapping-scope and aborted-queue client tests, then implement the one-at-a-time scope-aware Checkout behavior.
- [ ] Run the focused and full Workshop client tests and diff checks; obtain independent exact-head review and current CI before merge.

### Task 1: Scope in-flight Checkout starts

**Files:**
- Modify: `apps/api-go/workshop/commerce.mjs` (`createCheckout` only).
- Test: `apps/api-go/workshop-client.test.mjs` (Checkout tests near the existing in-flight test).

**Interfaces:** `createCheckout({request,storage,uuid}).start(scope,csrf,{signal})` retains the same Promise result and request headers/body; no caller changes.

- [ ] **Step 1: Write failing behavior tests.** With two valid literal configuration IDs and deferred request responses, assert the second scope does not get the first promise, the first network request completes before the second starts, and the second response/body/idempotency key belong to the second scope. With an aborted queued signal, assert no second network request is sent. Retain the existing same-scope shared-request test.
- [ ] **Step 2: Verify red.** Run `node --test --test-name-pattern='checkout attempt' workshop-client.test.mjs` in `apps/api-go`; the new cross-scope test must fail because the current code returns the global in-flight promise.
- [ ] **Step 3: Implement the minimal fix.** Replace the unqualified `if (inflight) return inflight` in `createCheckout` with a scope/signal check. For a different scope or aborted first signal, wait for the previous promise to settle, check the queued signal, then call `start` again. Keep the request one-at-a-time and clear in-flight metadata in `finally` only for that request. Leave `read`, `save`, response validation, and headers unchanged.
- [ ] **Step 4: Verify green.** Run the focused test, then `node --test --test-reporter=tap workshop-client.test.mjs workshop-demo.test.mjs`. Check `git diff --check`; inspect that the only implementation path is `commerce.mjs`.
- [ ] **Step 5: Review and integrate.** Commit/push a coherent candidate, obtain independent exact-head AI review, check current required CI and branch protection, and only then merge/close Issue #396/update Project #8. Do not call this live Stripe acceptance.
