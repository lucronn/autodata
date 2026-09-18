# Minimal Vehicle Selector Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dense local dashboard with a minimal, keyboard-accessible year-and-make selector that prepares a vehicle context for the existing repair query flow.

**Architecture:** Keep the existing same-origin Go dashboard route and use vanilla HTML, CSS, and JavaScript. The browser fetches `/vehicle-identities/selectors`, derives decade/year/make groups from the returned durable selector data, and keeps the selection state in the page without adding a new backend catalog or frontend framework.

**Tech Stack:** Embedded Go dashboard assets, semantic HTML, small CSS file, vanilla JavaScript, existing `/vehicle-identities/selectors` JSON endpoint, Go route contract tests, local browser verification.

**Spec:** `docs/architecture/dashboard-selector.md`

**Issue:** https://github.com/lucronn/autodata/issues/105

**Project:** https://github.com/users/lucronn/projects/8

## Global Constraints

- Keep the dashboard to HTML, CSS, and JavaScript; do not add a frontend framework or build step.
- Use the existing same-origin `/vehicle-identities/selectors` endpoint and bearer-token helper.
- Show all available decade buttons before any year is selected.
- Reveal only the years in the selected decade.
- After year selection, group available makes by their first letter and reveal a make list after a letter click.
- Preserve keyboard focus visibility, explicit loading/error/empty states, and narrow-screen spacing.
- Preserve the `/dashboard/` route and leave the repair API, worker, and persistence contracts unchanged.
- Preserve user-owned untracked `output/`, `sample data/`, and `tmp/` directories.

---

### Task 1: Replace the dashboard shell with the selector flow

**Files:**
- Modify: `apps/api-go/dashboard/index.html`
- Modify: `apps/api-go/dashboard/styles.css`
- Modify: `apps/api-go/dashboard/app.js`

**Interfaces:**
- Consumes: `GET /vehicle-identities/selectors` returning `years` and canonical `vehicles` records.
- Produces: a page with `#decade-list`, `#year-list`, `#make-letter-list`, `#make-list`, and selected context text.

- [x] **Step 1: Write the failing route-marker test**

Update `apps/api-go/dashboard_test.go` so the dashboard contract requires the selector IDs and minimal-flow copy, and no longer requires the old chatbot-only shell markers.

- [x] **Step 2: Run the focused route test and verify it fails**

Run: `go test ./apps/api-go -run 'TestDashboardRouteServes(ChatbotShell|JavaScriptAsset|WorkerAndAnswerStyles)' -count=1`

Expected: FAIL because the current dashboard does not expose the decade/year/make selector markers.

- [x] **Step 3: Implement the minimal HTML structure**

Create one page title, one selector region, a decade button list, a hidden year list, a hidden make-letter list, a hidden make list, a selected-context line, and a link/button that makes the existing repair-query next step clear. Keep the script and stylesheet on the existing dashboard route.

- [x] **Step 4: Implement selector data and interaction logic**

Fetch `/vehicle-identities/selectors` with the existing auth header. Normalize numeric years, derive decade labels using `Math.floor(year / 10) * 10`, filter vehicle records by selected year, sort makes case-insensitively, group them by the first alphanumeric letter, and render buttons with text content rather than HTML interpolation. Clicking a decade reveals its years; clicking a year reveals letters; clicking a letter reveals makes; clicking a make renders the selected year and make context and enables the next action.

- [x] **Step 5: Implement minimal responsive styling**

Use one centered content column, consistent `gap`/`margin` values, simple borders, visible focus outlines, button wrapping, and one narrow-screen breakpoint. Avoid gradients, cards-within-cards, decorative terminals, animation, and unnecessary copy.

- [x] **Step 6: Run the focused route test and verify it passes**

Run: `go test ./apps/api-go -run 'TestDashboardRouteServes(ChatbotShell|JavaScriptAsset|WorkerAndAnswerStyles)' -count=1`

Expected: PASS.

### Task 2: Verify the selector behavior in the browser

**Files:**
- Modify: `apps/api-go/dashboard_test.go` only if the route contract needs a precise selector marker.
- Verify: local dashboard at `http://127.0.0.1:8080/dashboard/`.

**Interfaces:**
- Consumes: the running API and its `/vehicle-identities/selectors` response.
- Produces: browser evidence for decade, year, make-letter, make, and selected-context transitions.

- [x] **Step 1: Run the complete applicable checks**

Run: `(cd apps/api-go && go test ./...)`, `node --check apps/api-go/dashboard/app.js`, and `git diff --check`.

Expected: all commands exit zero.

- [x] **Step 2: Exercise the browser flow**

Open the dashboard, verify decade buttons are visible together, click one decade, verify only its years appear, click a year, verify make-letter buttons appear, click a letter, verify matching makes appear, and click a make to verify the selected vehicle context and next action.

- [x] **Step 3: Synchronize delivery evidence**

Record the verified commit, local/browser results, and CI run in this plan, the canonical dashboard document, Issue #105, and Project #8. Mark all plan tasks complete only after the remote branch points to the verified commit.

- [x] **Step 4: Commit and push**

```bash
git add apps/api-go/dashboard/index.html apps/api-go/dashboard/styles.css apps/api-go/dashboard/app.js apps/api-go/dashboard_test.go docs/architecture/dashboard-selector.md docs/superpowers/plans/2026-09-18-minimal-vehicle-selector-dashboard.md docs/agents/records/2026-09-18-minimal-vehicle-selector-dashboard.json
git commit -m "feat: simplify vehicle selector dashboard"
git push origin phobos/fix-chat-source-failure
```

### Delivery evidence

- Implementation commit: `8914194544afe62f5ab9b2866312fd89e4dbf476` on
  `phobos/fix-chat-source-failure`.
- Local checks: `go test ./...` in `apps/api-go`, `node --check
  apps/api-go/dashboard/app.js`, and `git diff --check` passed.
- Browser checks at `http://127.0.0.1:8080/dashboard/`: the live rebuilt stack
  showed 1990s → 1999 → F → Ford → selected `1999 Ford`.
- Remote verification: [Autonomous Verification run
  35382320679](https://github.com/lucronn/autodata/actions/runs/35382320679)
  passed for the implementation commit.

## Self-review checklist

**todo:** complete the selector implementation, browser verification, and synchronized delivery record.

- [x] The page does not show a long year list before a decade is clicked.
- [x] The year list is limited to the selected decade.
- [x] Makes are grouped by first letter after a year is selected.
- [x] A letter click reveals the matching makes without another API call.
- [x] A make click preserves year and make in the selected context.
- [x] Loading, empty, and error states are visible and actionable.
- [x] No implementation file was changed before the synchronized preflight passed.
