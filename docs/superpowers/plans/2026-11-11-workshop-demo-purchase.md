# Workshop Demo Purchase Rehearsal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let visitors rehearse a no-charge purchase and post-purchase Workshop journey using only fictional, page-memory demo content.

**Architecture:** Preserve the explicit `?demo=1` bootstrap and its standalone `demo.mjs` module. Add a three-state browser-only flow (selection, checkout review, simulated access) to that module; never load the production app, authentication, or commerce modules in demo mode. Shared HTML/CSS contain a hidden review panel, but the normal Workshop does not activate it.

**Tech Stack:** Static HTML/CSS, browser ES module, Node built-in tests and the existing minimal DOM harness.

**Spec:** `docs/verification/2026-11-11-workshop-demo-purchase.md`.

**Issue:** https://github.com/lucronn/autodata/issues/398

**Project:** https://github.com/users/lucronn/projects/8

## Global constraints

- After planning preflight, implementation changes are limited to `apps/api-go/workshop/demo.mjs`, `apps/api-go/workshop/index.html`, `apps/api-go/workshop/styles.css`, and `apps/api-go/workshop-demo.test.mjs`.
- Keep normal `/workshop/` bootstrap and all server/API/payment/grant contracts unchanged.
- Demo state is memory-only; no import, fetch, storage, Stripe redirect, real entitlement, or licensed content.
- Show an unambiguous no-charge notice at the banner, price, review, and completion states.
- All example categories are fictional layout samples, not vehicle service guidance or a licensed source citation.

## Concrete todo

- [ ] Commit this plan, spec, canonical demo-document amendment and synchronized record; read back Issue #398 and Project #8; pass exact-SHA machine preflight.
- [ ] Write and run failing demo tests for the gated purchase review, cancel, confirm, page-memory reset and sample access.
- [ ] Implement the demo-only flow and category fixtures in the allowlisted files, keeping zero-network boundaries.
- [ ] Run focused/full Node, Go, syntax and browser checks; obtain independent exact-head review and current CI; merge only after live protection passes.

### Task 1: No-charge purchase rehearsal

**Files:** Modify `apps/api-go/workshop-demo.test.mjs`, `apps/api-go/workshop/demo.mjs`, `apps/api-go/workshop/index.html`, and `apps/api-go/workshop/styles.css`.

**Interfaces:** The existing `demoDOM()` harness returns the actual demo page elements; `purchase-action`, `demo-checkout`, `demo-checkout-confirm`, and `demo-checkout-cancel` are DOM IDs. Only the explicit demo module binds these controls.

- [ ] **Step 1: Write the failing test.** Extend the DOM test so that after choosing all four fixture selectors, the article index is still hidden. Assert the action opens a review panel, Cancel leaves articles locked, a second review followed by Confirm opens the sample index, and a new `demoDOM()` load returns to the locked state. For example:

  ```js
  assert.equal($('catalog').hidden, true);
  $('purchase-action').fire('click');
  assert.equal($('demo-checkout').hidden, false);
  $('demo-checkout-cancel').fire('click');
  assert.equal($('catalog').hidden, true);
  $('purchase-action').fire('click');
  $('demo-checkout-confirm').fire('click');
  assert.equal($('catalog').hidden, false);
  assert.equal(demoDOM()('catalog').hidden, true);
  ```

- [ ] **Step 2: Verify red.** Run `node --test-name-pattern='demo purchase' workshop-demo.test.mjs` in `apps/api-go`. It must fail on the pre-purchase catalog assertion against the baseline demo.
- [ ] **Step 3: Implement the minimal state transition.** Add hidden review controls in `index.html`; in `demo.mjs`, keep a boolean page-memory access flag and review-open state, bind the purchase/review/cancel/confirm buttons, and gate `showCatalog`/`openArticle` on confirmed demo access. Set the review heading focus on opening and return focus on cancellation. Keep the existing signed-out/zero-network boundary. Add only the CSS needed to distinguish the review panel while retaining native `[hidden]` behavior.
- [ ] **Step 4: Verify green.** Rerun the focused demo test; confirm that no production module or network/storage token was added and ordinary bootstrap routing is unchanged.

### Task 2: Representative post-purchase Workshop journey

**Files:** Modify `apps/api-go/workshop-demo.test.mjs` and `apps/api-go/workshop/demo.mjs`.

**Interfaces:** A static in-module sample-article array feeds the existing `articles` list, `search` control, `reader` and `library-items` nodes; the fixture is never passed to an API.

- [ ] **Step 1: Write the failing test.** After confirmation, assert ten fixture-only articles (overview plus nine named categories), search can isolate Diagnostic trouble codes, the selected reader carries the persistent provenance and returns with Back, and `my-vehicles` opens exactly one sample item that returns to the index. Assert repeated Confirm does not create a second item.
- [ ] **Step 2: Verify red.** Run `node --test-name-pattern='demo purchase' workshop-demo.test.mjs`; the baseline single-article index and disabled library must fail the new assertions.
- [ ] **Step 3: Implement the fixture and navigation.** Create the static non-instructional category rows, render them with `textContent`/`createElement`, and wire the existing search/reader/back/Browse/library controls to page-memory demo access. Do not add a real vehicle identifier, source URL, service value, or API call.
- [ ] **Step 4: Verify green and isolation.** Run `node workshop-demo.test.mjs`, `node workshop-client.test.mjs`, `node --check workshop/demo.mjs`, and `git diff --check`. Keep the normal app source byte-unchanged.

### Task 3: Review and integrate

**Files:** Update only the planning/spec verification checkboxes and linked Issue/Project records after the implementation tests; do not broaden implementation scope.

- [ ] **Step 1: Verify release evidence.** Run `GOCACHE=/tmp/autodata-workshop-go-cache /home/corp/.local/go/bin/go test ./...` in `apps/api-go` and exercise `/workshop/?demo=1` in a local browser, checking both no-charge labels and zero non-static requests. Record exact commands/results and any unavailable browser capability honestly.
- [ ] **Step 2: Commit and push.** Commit the bounded implementation and update Issue #398 and Project #8 with the exact head, tests, and pending gates.
- [ ] **Step 3: Independent review.** A separate read-only AI reviewer inspects the exact head/base against the plan, tests, and zero-network boundary, with Critical/Important/Minor findings and verdict. A changed head gets a new review.
- [ ] **Step 4: CI and merge.** Verify all current CI jobs, live branch protection and resolved conversations. Squash-merge only if those gates pass, then close/update Issue #398 and Project #8. Never claim this proves live Stripe or paid access.
