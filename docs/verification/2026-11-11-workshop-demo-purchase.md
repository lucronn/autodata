# Workshop no-charge demo purchase rehearsal

Issue: https://github.com/lucronn/autodata/issues/398

Project: https://github.com/users/lucronn/projects/8

Plan: `docs/superpowers/plans/2026-11-11-workshop-demo-purchase.md`

Existing demo record: `docs/architecture/workshop-readonly-demo.md`

## Goal and boundary

The explicit `/workshop/?demo=1` route will let a visitor rehearse choosing a
fictional vehicle, reviewing an illustrative $20 USD checkout, canceling or
confirming a no-charge simulation, then searching and reading fictional sample
articles and opening an in-page sample library. This is a UI rehearsal only:
confirmation creates no Stripe session, payment, order, customer record, grant,
or entitlement. It does not validate live paid access. Normal `/workshop/`
continues to load the ordinary application and retains every existing auth,
quote, checkout, library, and paid-catalog contract.

## Expected demo sequence

1. The persistent banner says the purchase is simulated and no real vehicle
   access is granted. Sign-in, order status, terms agreement, printing, and
   source-review controls remain disabled or hidden. The illustrative price
   says no charge will be made.
2. Before all four fictional vehicle choices are made, the demo-purchase
   action is disabled and the article index/reader/library are hidden.
3. Completing the selection enables `Try demo checkout`. The first click
   reveals an inline review panel with the fictional vehicle, illustrative
   amount, `Complete demo purchase`, and `Cancel` buttons. No card details are
   collected. Cancel returns to the selection without unlocking articles.
4. Confirming once sets a page-memory-only demo-access flag, hides the review,
   announces a no-charge simulation, and opens the sample article index. A
   second confirmation cannot create another transition. The purchase action
   becomes `Open demo articles`; `My vehicles` opens a fixture-only library
   item that returns to the index.
5. The index includes the existing overview and one clearly fictional,
   non-service-information example for each requested Workshop category:
   diagnostics, repair procedures, maintenance intervals, specifications,
   fluids, wiring diagrams, component locations, technical service bulletins,
   and diagnostic trouble codes. Search, reader/back, Browse, and library
   navigation use only this static fixture. No actual procedure, interval,
   specification, fluid, diagram, bulletin, DTC definition, licensed article,
   or invented source citation appears.
6. A reload clears the simulated state. Switching away from the fictional
   selection hides the reader/index until it is selected again; it never
   creates access for any real vehicle.

## Verification and non-goals

- The demo module must remain separate from `app.mjs`, `auth.mjs`, and
  `commerce.mjs`; it makes zero transport, storage, `/v1`, `/auth`, Stripe,
  provider, or model calls. Static markup/styles may be shared.
- Node DOM tests will prove the pre-purchase gate, review/cancel/confirm,
  double-confirm guard, page-memory reset, category search/reader/back and
  library route. A structural test will retain the zero-network and normal
  bootstrap boundary.
- Run focused and full Workshop Node tests, Go API tests, syntax/diff checks,
  a local browser smoke of the explicit demo route when browser tooling is
  available, independent exact-head AI review, current CI, and live branch
  protection before merge. A browser fixture check is not live Stripe or
  production paid-access acceptance.
- No production deployment, payment enablement, DNS, traffic, schema, backend,
  grant, or source-data change belongs to this task. The separate live catalog
  partial-hydration warning shown by a user remains a distinct issue; the
  fixture demo does not claim to repair that source condition.

## Concrete todo

- [ ] Commit synchronized planning documents/Issue/Project and pass exact-SHA
  pre-implementation machine preflight.
- [ ] Add red-first demo tests for the full no-charge rehearsal and isolation.
- [ ] Implement the bounded demo UI and fictional fixture categories.
- [ ] Verify local and browser behavior, obtain exact-head review and CI, then
  integrate only if current branch protection permits.
