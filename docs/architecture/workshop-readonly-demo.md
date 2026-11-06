# Workshop read-only demonstration

The explicit `/workshop/?demo=1` entry is a separate browser bootstrap path for fictional, repository-authored sample content. A visible persistent banner says “Demo — sample content. No purchase or vehicle access is granted.” The fixture uses a fictional vehicle (“2026 Example Motors Sample”, “Demonstration trim”) and a non-procedural sample article (“Understanding this sample manual”). It contains no licensed provider article, provider identifier, service instruction, torque value or invented source citation. Its provenance says “Illustrative content authored for this demo; not supplied by Bankone or Banktwo. Not vehicle service information.”

The demo reuses Workshop markup and styles, but its module is loaded before any normal application module. The normal `app.mjs` remains the default bootstrap. The demo enables selector progression, article search, reader and back navigation entirely in browser memory. A displayed $20 USD amount is labeled “Illustrative price — checkout unavailable in demo”. Purchase, sign-in, order checks and account/library mutations are disabled. No database writes, entitlement grants, live source/canonical reads, model calls or API requests occur. Reloading `?demo=1` returns to the sample. A link to the regular Workshop exits demo mode explicitly.

Normal Workshop authentication, rights and paid-catalog enforcement retain their existing contracts. Demo mode never adds a server entitlement exception, client fake grant, Stripe fixture or seeded production customer. Static sample assets are public demonstration material.

## Inception model configuration

The coordinator verified the official provider catalog lists `mercury-3` as current/newest on 2026-11-06. `mercury-2` and `mercury-2.5` remain listed; no retirement or deprecation is claimed. Update constructor/environment and Compose defaults to `mercury-3`; explicit `INCEPTION_MODEL` overrides continue to work. The shared client sends `temperature: 0.5` for Mercury-3 (valid provider range 0.5–1) and `max_completion_tokens` with the existing `INCEPTION_MAX_TOKENS` budget. Explicit older-model overrides retain their prior compatible `temperature: 0` and `max_tokens` request shape. Historical extraction-mode/generation metadata and legacy class/module names are not renamed.

Secrets remain environment/platform managed. This change does not require or print keys, and demo mode never consumes the model client.

## Tracking and acceptance

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-06-workshop-readonly-demo.md`
Record: `docs/agents/records/2026-11-06-workshop-readonly-demo.json`

Concrete todo:
- [ ] Implement an explicit fixture-only Workshop demo entry with a fictional vehicle, article search/reader/back navigation, an illustrative $20 USD quote and persistent sample-content labeling; load no live application/auth/commerce modules in demo mode.
- [ ] Keep demo purchase/sign-in/library mutations disabled and make zero catalog, auth, commerce, preparation, ingestion or model requests; preserve paid routes, grants and production authentication.
- [ ] Update Inception model defaults to mercury-3 and make its request temperature/token fields compatible while retaining explicit INCEPTION_MODEL overrides and historical Mercury-2 metadata.
- [ ] Run focused client/Go/Python regressions and browser verification proving demo navigation and no live API requests; record exact candidate evidence, commit/push coherent milestones and synchronize Issue186/Project8.
