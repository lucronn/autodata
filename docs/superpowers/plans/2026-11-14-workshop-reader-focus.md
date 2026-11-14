# Workshop article navigation focus

Goal: Restore keyboard focus when opening Workshop articles and returning to the article index, without moving focus during background article updates.

Issue: https://github.com/lucronn/autodata/issues/407
Project: https://github.com/users/lucronn/projects/8
Canonical architecture: `docs/architecture/workshop-reader-focus.md`
Gate record: `docs/agents/records/2026-11-14-workshop-reader-focus.json`

## Observed defect

On current master 61f1939, production loadArticle/renderArticle executed in Chromium at 390px leaves document.activeElement on the catalog article anchor after the catalog is hidden. The reader title never receives focus. Back focuses the index heading with preventScroll, which can leave that heading offscreen.

## Implementation decision

At authenticated loadArticle entry, reveal the reader, set the title to Opening article… for a different article, and focus its existing tabindex=-1 heading once. Keep the title for same-article retries. Polling and renderArticle must not focus. Remove preventScroll from the existing Back heading focus. Scope is apps/api-go/workshop/app.mjs and apps/api-go/workshop-client.test.mjs only, plus these planning/verification documents. No data, ingestion, commerce, authorization, styling, or deployment changes.

## Concrete todo

- Move focus to the article heading once when an authenticated article navigation starts; supply an opening title for a new article and preserve the existing title when retrying the same article.
- Keep prepare and polling renders from moving focus; let Back scroll the focused article-index heading into view.
- Verify production navigation code with focused regression tests and headless Chromium at narrow and desktop viewport sizes; run the complete Workshop client suite.
- Commit and push the independently reviewable UI milestone, record exact evidence, and hand the branch to the coordinator for integration and deployment.

## Verification

Focused tests must hold preparation pending, inspect title/focus immediately, render repeated updates while another control is focused, preserve retry title, and reject obsolete navigation updates. Browser checks execute the production functions and Back handler against the actual HTML/CSS at 390px and 1440px, checking visible focus and no horizontal overflow. Run node --test workshop-client.test.mjs workshop-demo.test.mjs, node --check workshop/app.mjs, and git diff --check.

## Synchronized pre-implementation record

```json
{
  "goal": "Restore keyboard focus when opening Workshop articles and returning to the article index, without moving focus during background article updates.",
  "plan_ref": "docs/superpowers/plans/2026-11-14-workshop-reader-focus.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/407",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/architecture/workshop-reader-focus.md"
  ],
  "todo": [
    "Move focus to the article heading once when an authenticated article navigation starts; supply an opening title for a new article and preserve the existing title when retrying the same article.",
    "Keep prepare and polling renders from moving focus; let Back scroll the focused article-index heading into view.",
    "Verify production navigation code with focused regression tests and headless Chromium at narrow and desktop viewport sizes; run the complete Workshop client suite.",
    "Commit and push the independently reviewable UI milestone, record exact evidence, and hand the branch to the coordinator for integration and deployment."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-14T23:14:05.499144+00:00"
}
```
