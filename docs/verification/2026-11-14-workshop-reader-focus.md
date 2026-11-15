# Workshop article navigation focus verification

Issue: https://github.com/lucronn/autodata/issues/407
Project: https://github.com/users/lucronn/projects/8
Plan: [reader focus recovery](../superpowers/plans/2026-11-14-workshop-reader-focus.md)

Planning checkpoint: `0788d1f`; the checkpoint was pushed before implementation. Machine preflight at that checkpoint returned `{"status": "synchronized", "errors": []}`. Issue and Project readbacks contained the same goal, plan, and concrete todos.

## Before repair

A headless system Chromium probe executed current-master `loadArticle`, `renderArticle`, and rendering helpers against the actual HTML/CSS. At 390px, opening a fixture article hid the catalog while `document.activeElement` remained the hidden catalog anchor. The new focused tests failed against unmodified implementation (missing opening title/focus and missing obsolete-generation guard).

## Local candidate checks

- `node --test apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`: 267 passed, zero failures, zero skips. This includes pending preparation, repeated render updates, obsolete navigation, and the existing same-article retry-title behavior.
- `node --check apps/api-go/workshop/app.mjs`: passed.
- `git diff --check`: passed.
- Headless system Chromium at 390×844 and 1440×844 executed the candidate production navigation functions, rendering helpers, and Back handler against actual HTML/CSS with an in-memory article response. Focus immediately entered `article-title` with “Opening article…”, remained there after the article loaded, stayed on Print when another revision rendered, and moved to the visible `catalog-title` after Back from a scrolled reader. Neither viewport had horizontal document overflow. The probes are local UI fixtures, not authenticated live-article acceptance.

## Live read-only check

On 2026-11-14, the live origin recovered from its earlier 502. `https://autodata.cars.tk/workshop/` returned 200; `/readyz` reported database, NATS, and object storage ready. Chromium at 390×844 loaded the live Workshop without JavaScript errors, with 63 year-selector options, an enabled sign-in button, “Choose your vehicle to continue.” status, and no horizontal overflow. No account, payment, or paid-article request was made. This checks the deployed entry page; the focus repair still requires coordinator integration/deployment.

## Guidance

The `html` guide requires moving focus into newly injected content after a workflow navigation and preserving focus for background updates. The existing tabindex=-1 headings provide native programmatic focus targets. Its warning against unvalidated preventScroll informed the Back change. The `responsive-design` guide was reviewed; this repair changes no layout APIs.
