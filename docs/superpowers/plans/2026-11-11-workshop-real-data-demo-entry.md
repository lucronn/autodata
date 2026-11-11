# Real-data Workshop demo entry

Issue: https://github.com/lucronn/autodata/issues/398  
Project: https://github.com/users/lucronn/projects/8  
Verification: `docs/verification/2026-11-11-workshop-real-data-demo-entry.md`

## Goal

Make `/workshop/?demo=1` use the ordinary, authenticated Workshop application and its real catalog, article, search, reader, source/media and library paths. The only simulated step is a Stripe **test-mode** payment; its verified test settlement still creates the existing server-owned exact-vehicle grant. Never turn a browser click into a grant or present repository-authored sample articles as real data.

## Bounded implementation

The Go API exposes an uncached public demo-readiness signal only when the process is explicitly configured as `stripe_test` with Firebase sign-in, a non-production environment, and a separate non-production public origin. Its private commerce dependency must independently confirm `stripe_test` with an enabled, valid purchase configuration. Missing, malformed (including duplicate-field) or unavailable responses fail closed. The signal is presentation-only, not an authorization input. A browser tab displaying the no-real-charge banner must include an `expected_mode=stripe_test` assertion in **each** checkout request. Go rejects that assertion if its current process is no longer in test mode, and a test-mode Go process pins the same private field for every checkout. The Python commerce authority checks the private field against its immutable configured mode **before** any payment operation. This closes both Go-restart and Python-restart stale-tab paths to a live charge. The browser loads ordinary `app.mjs` for a ready real-data demo and keeps a visible no-real-charge/test-mode banner across the Stripe return URL. If `?demo=1` is requested when readiness is false, do not load the Workshop app under a misleading demo label; show an actionable unavailable message. The old fictional sample moves to explicit `?sample=1` and remains clearly labeled as non-service information.

Existing Stripe test settlement, account identity, grant check, current source rights, exact scope, refund/revocation and protected article/media paths stay unchanged. Do not add a free public content route, fake grant or client-side entitlement. Real eligible content is not guaranteed for every vehicle/category; show only actual returned content and existing honest missing/preparing states.

No production mode, traffic, DNS, payment enablement, secret, deployment, source connector or database change is included. Test-mode checkout must not start with the public production origin, even if the environment label is wrong. A restricted, separately provisioned test audience and licensed real-data environment are still required before claiming end-to-end acceptance: a different hostname alone is not audience isolation.

## Implementation files

- `apps/api-go/main.go`, `workshop_demo_mode.go`, `commerce_client.go`, `commerce_http.go`: immutable non-production/Firebase/origin test-mode signal, strict private mode handshake, checkout-time expected-mode constraint and route wiring.
- `apps/api-go/workshop/index.html`, `bootstrap.mjs`, `app.mjs`, `commerce.mjs`, `demo.mjs`: separate real test-mode and fictional sample labels; route selection; per-tab test-only checkout assertion.
- `workers/ingestion-python/src/autodata_ingestion/commerce_service.py`, `http_service.py`: token-authenticated private mode/readiness response, checkout-time expected-mode enforcement and test-origin validation, without changing settlement or grant semantics.
- `apps/api-go/workshop_test.go`, `commerce_http_test.go`, `workshop-demo.test.mjs`, `workshop-client.test.mjs`, `workers/ingestion-python/tests/test_http_service.py`, `test_commerce_service.py`: red-first Go/browser/private-service regressions.

## Concrete todo

- [x] Synchronize this plan, Issue #398, Project #8, canonical verification document and pinned-base machine preflight (`0675a17` returned `status:synchronized`, `errors:[]`).
- [x] Add failing Go, Python and browser tests for disabled/live/production/mismatched-mode/invalid-response/test-ready modes, explicit demo refusal, real app import, sample isolation and return-page banner.
- [x] Implement the initial bounded endpoint and bootstrap behavior without changing grants or article APIs (`4ecc2d7`).
- [x] Add red-first regressions and close initial independent-review gaps: Python-only mode drift, Firebase readiness, public-origin exclusion and duplicate-key private-response rejection (`02cce3e`).
- [x] Close re-review's Go-restart stale-tab gap with a browser-carried test-only assertion, Go rejection when its current mode is live, and private test-mode pinning; red-first tests cover the live-Go/no-private-call case.
- [ ] Run focused/full Node, Go and Python tests, syntax/diff checks and local browser smoke; obtain independent exact-head re-review and current CI.
- [ ] Merge only if live branch protection permits; keep real licensed-data/test-payment browser acceptance and deployment separately blocked until evidenced.
