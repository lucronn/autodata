# Real-data Workshop demo entry

Issue: https://github.com/lucronn/autodata/issues/398  
Project: https://github.com/users/lucronn/projects/8  
Verification: `docs/verification/2026-11-11-workshop-real-data-demo-entry.md`

## Goal

Make `/workshop/?demo=1` use the ordinary, authenticated Workshop application and its real catalog, article, search, reader, source/media and library paths. The only simulated step is a Stripe **test-mode** payment; its verified test settlement still creates the existing server-owned exact-vehicle grant. Never turn a browser click into a grant or present repository-authored sample articles as real data.

## Bounded implementation

The Go API exposes an uncached public demo-readiness signal only when the process is explicitly configured as `stripe_test` in a non-production environment and its private commerce dependency independently confirms `stripe_test` with an enabled, valid purchase configuration. This private mode handshake prevents a Go/Python configuration mismatch from labeling a live charge as a test purchase. The signal is presentation-only, not an authorization input. Missing, malformed or unavailable responses fail closed. The browser loads ordinary `app.mjs` for a ready real-data demo and keeps a visible no-real-charge/test-mode banner across the Stripe return URL. If `?demo=1` is requested when readiness is false, do not load the Workshop app under a misleading demo label; show an actionable unavailable message. The old fictional sample moves to explicit `?sample=1` and remains clearly labeled as non-service information.

Existing Stripe test settlement, account identity, grant check, current source rights, exact scope, refund/revocation and protected article/media paths stay unchanged. Do not add a free public content route, fake grant or client-side entitlement. Real eligible content is not guaranteed for every vehicle/category; show only actual returned content and existing honest missing/preparing states.

No production mode, traffic, DNS, payment enablement, secret, deployment, source connector or database change is included. A restricted, separately provisioned test audience and licensed real-data environment are required before claiming end-to-end acceptance.

## Implementation files

- `apps/api-go/main.go`, `workshop_demo_mode.go`, `commerce_client.go`: immutable non-production test-mode signal, private mode handshake and route wiring.
- `apps/api-go/workshop/index.html`, `bootstrap.mjs`, `demo.mjs`: separate real test-mode and fictional sample labels; route selection.
- `workers/ingestion-python/src/autodata_ingestion/commerce_service.py`, `http_service.py`: token-authenticated private mode/readiness response, without payment or grant mutation.
- `apps/api-go/workshop_test.go`, `workshop-demo.test.mjs`, `workers/ingestion-python/tests/test_http_service.py`: red-first Go/browser/private-service regressions.

## Concrete todo

- [ ] Synchronize this plan, Issue #398, Project #8, canonical verification document and pinned-base machine preflight.
- [ ] Add failing Go and browser tests for disabled/live/production/invalid-config/test-ready modes, explicit demo refusal, real app import, sample isolation and return-page banner.
- [ ] Implement the bounded endpoint and bootstrap behavior without changing auth, commerce, grants or article APIs.
- [ ] Run focused/full Node and Go tests, syntax/diff checks and local browser smoke; obtain independent exact-head review and current CI.
- [ ] Merge only if live branch protection permits; keep real licensed-data/test-payment browser acceptance and deployment separately blocked until evidenced.
