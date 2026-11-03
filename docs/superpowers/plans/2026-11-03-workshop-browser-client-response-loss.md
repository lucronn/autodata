# Workshop browser client response loss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after the coordinator's independent gate approval. Steps use checkbox syntax for tracking. No implementation is authorized by this planning checkpoint alone.

**Goal:** Correct the real-API browser fixture to lose only the browser checkout response after a successful API commit, then prove the same-key retry preserves one order and provider session.

**Architecture:** Scope a one-shot transport fault to the first case's browser POST to the actual checkout endpoint. Playwright `route.fetch()` must complete a real successful checkout before `route.abort()` hides only that response from the browser. Forward the actual retry response unchanged and assert API persistence/idempotency using existing measurement and snapshot routes.

**Tech Stack:** Python async Playwright1.64.1 fixture, standard-library unittest async doubles, existing Go/Python/PG commerce API.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md` checkout/return contract and this bounded diagnosis amendment.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Task: `docs/agents/tasks/2026-11-03-production-release/2026-11-03-workshop-browser-client-response-loss.json`
Record: `docs/agents/records/2026-11-03-workshop-browser-client-response-loss.json`
Source integration base: `35aef11cb37cb6f1f6b6b609ff374689dde9d516` on `codex/production-release-orchestration`.
Planning branch: `codex/workshop-browser-lost-response-gate`.
Execution profile: gpt-6.1-sol, medium reasoning, Fast/priority, no fallback.

## Global constraints and evidence

The exact pilot candidate `8a1746dc6b449c77dd3adab5794669a5155b7bf5` at `/tmp/autodata-workshop-browser-pilot-8a1746d` failed Chromium `test_browser_google_exchange_checkout_library_real_api` after HOME was repaired. Its `artifacts/workshop-browser/test_browser_google_exchange_checkout_library_real_api/chromium-bankone/browser/evidence.json` records the hidden `#retry` with the existing5000ms expectation and “Payment is being confirmed. Do not pay again.” The failed receipt and screenshot remain unchanged; this is one failed pilot, not full21 acceptance.

`api_case` currently invokes `control/lose-response`; `apps/api-go/workshop_browser_fixture_test.go` forwards that control to `BrowserBridge` in `workers/ingestion-python/tests/test_workshop_browser_integration.py`, which sets `StripeFixture.lose_once`. This loses the provider response after provider commit, so the real commerce API intentionally responds202 processing and UI polls the owner order. The test expects a browser-to-API transport failure and manual retry instead. No product defect follows from this mismatch. Preserve `workers/ingestion-python/tests/test_commerce_postgres.py::test_lost_create_response_and_retention_boundary` unchanged: it asserts provider loss yields processing, same-key retry recovers the same order with exactly one provider session, and retention-boundary reconciliation remains safe. Keep its fixture control available; remove only its inappropriate invocation from the browser scenario.

Literal implementation allowlist (exactly two paths):

```text
scripts/dev/workshop_browser_smoke.py
scripts/dev/test_workshop_browser_smoke.py
```

No application, Go/Python runtime fixture, auth, grants, payments, catalog, media, schema, UI or provider behavior changes. No assertion relaxation or timeout extension. No case renaming, removal, additions or skips: four pytest roots expand to3+6+6+6=21 actual-API cases;40 DTO scenarios times three engines remain120. The builder must not execute Docker, browsers, providers, cloud, deployment, DNS or secrets operations. The coordinator owns actual pilot/full21 runs. New scope requires a separately synchronized plan/task/record checkpoint and machine gate before edits; the two owned files already contain the needed route seam and unit harness.

Keep `/tmp/autodata-workshop-browser-supervisor.py` byte-identical (pilot receipt supervisor SHA256 `b41ae0a538b3c5b62b33c32483146462886851e3c60768f8fdc0ac79495a3964`) and these six image build inputs unchanged:

```text
infra/compose/article-lifecycle-test.Dockerfile
scripts/dev/requirements-workshop-browser.txt
workers/ingestion-python/pyproject.toml
apps/api-go/go.mod
apps/api-go/go.sum
packages/contracts/go/go.mod
```

The browser evidence also hashes six source inputs; its smoke.py hash intentionally changes to match the new exact candidate. Recompute candidate provenance normally, without changing the frozen wrapper or accepting stale hashes. Preserve all other browser provenance inputs, original failed receipts, private HOME isolation, environment allowlists, owned loopback TLS, real served assets, resource deadlines and cleanup.

## Concrete synchronized todo

1. Synchronize Issue186/Project8, the dedicated plan, canonical UI plan, queue, task and record; commit/push the checkpoint and pass exact-SHA preflight before independent coordinator approval.
2. Add failing async route regressions for actual API fetch before browser abort, exact one-shot scope, same-key/body retry, unchanged real response forwarding and fail-closed invalid responses.
3. Replace the first real-API case provider lose-response control with browser-route response loss after successful checkout; retain retry visibility, hosted redirect, exact request reuse, durable order/session and provider-call assertions.
4. Run focused browser fixture units, syntax, 21/120 inventory, frozen-input and two-file scope checks; commit/push the coherent fixture fix and obtain independent exact-commit review.
5. Coordinator integrates the reviewed fix, reruns the Chromium pilot then the unchanged full21 actual API inventory at a clean immutable SHA using the frozen supervisor/image, and independently checks raw provenance and cleanup.

## Task 1: Prove and repair the browser transport fault

**Files:** modify only the two allowlisted paths above. The existing `APIFixture.route`, inherited DTO state (`checkout_count`, `keys`, `checkout_bodies`), `api_case` and unittest module are the seams; no direct server fixture changes are needed.

**Interfaces:** consume the real `route.request` method/url/headers/post_data, async `route.fetch()`, APIResponse status/json, `route.abort()`, `route.fulfill(response=actual_response)`, and existing `api_measure`/`api_snapshot`. Produce private fixture state for successful first checkout response, exact requests, lost response count and actual retry response. Never emit raw cookies, CSRF, Firebase tokens, Idempotency-Key, checkout bodies or signed URLs into evidence. A safe boolean assertion and counters are sufficient; keep sensitive comparison values in memory only.

- [ ] Step1: In `scripts/dev/test_workshop_browser_smoke.py`, add `unittest.IsolatedAsyncioTestCase` regressions exercising the real `APIFixture.route` with async route/response doubles. Record call order in the doubles. Set the scenario to `API_CASES[0]`, request method POST and URL `<fixture.origin>/v1/workshop/checkout-sessions`; supply a UUID idempotency key and exact expected JSON body. The first fake `fetch()` records a durable backend event then returns an actual-response double with status200/201, versionv1, statecheckout, valid order/configuration UUID, regionUS and exact trusted hosted session URL. Require call order `fetch`, response validation, `abort`; no `continue_` or `fulfill`. A second matching request must fetch and fulfill that actual response, never abort, with equal body/key and equal order/URL. Verify count2 and exactly one dropped browser response. Assert no third request can pass this case's exact-two invariant.

```python
# Use the actual route method; the doubles stand in only for browser transport.
fixture = smoke.APIFixture('https://127.0.0.1:32001', smoke.API_CASES[0])
await fixture.route(first_route)
self.assertEqual(first_route.events, ['fetch', 'json', 'abort'])
await fixture.route(retry_route)
self.assertEqual(retry_route.events, ['fetch', 'json', 'fulfill'])
self.assertIs(retry_route.forwarded_response, retry_route.fetched_response)
```

Add boundary subtests for another API scenario, non-POST method, different path, off-origin request and subsequent retry; none may consume the one-shot fault. On fetch exception, status202/4xx/5xx, malformed or wrong-state/scope/order/URL response, fail closed before abort and never record a successful loss. Tests should deliberately change a retry key/body/order/session URL and require failure. This proves the transport boundary, rather than merely searching source strings or duplicating an allowlist.

- [ ] Step2: Run the new focused tests and retain the red output before implementing. Existing code calls continue_ and must fail the first `fetch` assertion; do not invoke a browser to demonstrate red.

```bash
python -m unittest discover -s scripts/dev -p test_workshop_browser_smoke.py -v
```

- [ ] Step3: In `APIFixture.route`, retain existing safe request-template observation, bearer detection and external-origin rules. Intercept only same-origin exact checkout path POST in `API_CASES[0]`. Track key/body on both targeted requests. Call `await route.fetch(max_redirects=0, max_retries=0)` once per intercepted request, validate a real successful checkout response before treating it as a loss, and keep first/second order/URL in memory. Check valid trusted hosted URL with the existing allowed-external rule and checkout session path shape, and validate response scope against the browser's submitted body. Use the following transport sequence; assertions must fail the case for invalid fetch/response, rather than synthesizing checkout or turning202 into a retry:

```python
response = await route.fetch(max_redirects=0, max_retries=0)
assert response.status in (200, 201)
checkout = await response.json()
assert checkout['version'] == 'v1' and checkout['state'] == 'checkout'
# Validate exact submitted configuration/region, UUID order and hosted session URL.
# First targeted response: remember validated identity; abort browser delivery only.
# Second: assert identical request key/body and checkout identity; forward unchanged.
```

Do not call continue_ after fetch, as it could duplicate the POST. For the first response call `await route.abort()` only after fetch and validation; for retry call `await route.fulfill(response=response)` so the browser receives actual server status/body/headers. Unrelated routes still use the existing continuation/external logic. Keep race prevention explicit: consume the one-shot before awaiting fetch, but only mark successful loss after validation and abort complete, so concurrent double activation cannot drop two responses.

- [ ] Step4: In `api_case`, remove only the `control/lose-response` invocation. Keep existing double activation, `#retry` visible expectation and hosted redirect expectation at their existing deadlines. Before clicking manual retry, require the first validated fetch and exactly one dropped response; call existing measurement/snapshot routes and require one order, one checkout-request row, no entitlements, stateopen, and matching first response order/session. The snapshot `paid_rows.workshop_orders` contains `checkout_session_id`; match it to the session ID in the validated actual hosted URL. Then click Retry, wait for the actual hosted redirect, and require exactly two POSTs with identical UUID key/body, identical first/retry order/session URL, one persistent order, one checkout-request row, no entitlements and unchanged snapshot `payment_calls` across retry. Unchanged provider calls plus the durable original session and identical real responses prove no second provider session was created. Emit an explicit `assertions['client_response_loss_same_key_one_checkout']=True` only after all checks pass. Keep all later return/webhook/library/restart/media/customer assertions intact.

- [ ] Step5: Run focused units green and syntax-compile the two owned files. Verify API inventory with AST/literal evaluation so no integration import/browser/Docker is needed; check exactly four root names and the existing pytest decorators'3+6+6+6 expansion. Call `inventory()` and verify40 unique DTO names and `ENGINES` length3. Compare frozen input hashes and full source scope against the committed checkpoint; no browser or provider invocation belongs here.

```bash
python -m unittest discover -s scripts/dev -p test_workshop_browser_smoke.py -v
python -m py_compile scripts/dev/workshop_browser_smoke.py scripts/dev/test_workshop_browser_smoke.py
git diff --check
git diff --name-only
```

Retain red/green evidence outside the checkout, commit the coherent two-file change with `test: lose browser checkout response after real API commit`, push the assigned builder branch, and return the exact SHA plus checks to independent coordinator review. Passing unit doubles do not establish actual API acceptance.

## Task 2: Coordinator acceptance and integration

- [ ] Independently inspect the exact two-file candidate, request ordering and no duplicate fetch/continue, unchanged product assertions/timeouts, retained provider-loss commerce coverage,21/120 inventories, private HOME and frozen wrapper/build inputs. Reject a202 conversion, pre-API abort or manufactured checkout response.
- [ ] Integrate the reviewed candidate onto the coordinator branch, pin one clean immutable SHA and preserve failed pilot evidence. With the existing frozen supervisor/image, rerun Chromium `test_browser_google_exchange_checkout_library_real_api` first. Verify real API successful checkout before lost browser response, manual same-key/body retry, one durable order/session, unchanged provider-call count, actual served-asset/TLS/candidate hashes, no unexpected egress and complete cleanup. A failed pilot remains failed; diagnose under a fresh bounded gate if scope changes.
- [ ] Once the pilot passes, run the unchanged full21 actual-API inventory through the frozen supervisor at the exact clean integrated candidate. All21 must pass without missing/extra/skipped cases across Chromium/Firefox/WebKit and applicable banks; inspect raw per-case evidence/provenance, runtime ownership and cleanup independently. Preserve the existing DTO120 inventory/result and rerun affected DTO checks under the established acceptance policy; do not replace API21 with DTO evidence.
- [ ] Update canonical verification/queue/Issue186/Project8 with exact candidate and measured results. This fixture repair alone certifies no real Firebase/Stripe TEST/bank staging, hosting recovery, cars.tk cutover or production readiness.

## Gate handoff

The planning/checkpoint commit itself is the pinned implementation base; resolve its full40 SHA after committing these five documentation paths, then run the machine preflight against that exact SHA and record it in Issue186/Project8. The standalone record and task's `pre_implementation` object must match. The coordinator independently approves that exact checkpoint before any builder edits. If later integration changes the base, the coordinator must re-run exact-base preflight on the integrated checkpoint before dispatch.

```bash
python scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-03-workshop-browser-client-response-loss.json --base-sha <exact-checkpoint-SHA>
```

Expected output: `{"status": "synchronized", "errors": []}`. The placeholder in the invocation denotes the subsequently resolved commit identity, not an unspecified design decision. Tracking synchronization is verified by reading back the Issue and Project item after the exact SHA is published.
