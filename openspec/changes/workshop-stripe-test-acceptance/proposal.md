## Why

Workshop already creates Stripe Checkout sessions and grants access after
verified settlement. Prove that a tester can take the complete path, from
choosing a vehicle to purchasing access and reading the article. Fix
differences between what the browser displays and what it allows a tester
to do before moving toward a production release.

## What Changes

- Reuse hosted Checkout with Stripe TEST credentials and isolated Workshop
  state. Confirm the account, one-time USD 20 Price, signed webhook delivery,
  and visible TEST notice before enabling the test purchase UI.
- Keep the browser's purchase controls and submission consistent on supported
  TEST origins. Verify return, settlement, Library, article media, reload,
  cancellation and explicit retry, and access denial for an unowned scope.
- Run the repeatable browser fixtures first. Track real Stripe TEST settlement
  and licensed-data browser acceptance separately.

## Capabilities

### New Capabilities

- `workshop-stripe-checkout`: Verified TEST purchasing and exact-scope grants.
- `workshop-purchased-article-viewing`: Browser navigation and authorization
  from Workshop selection to an owned article.

### Modified Capabilities

None. This is the first OpenSpec change in AutoData and captures behavior
owned by the existing Workshop implementation.

## Impact

Workshop browser code, the current Go API and Python commerce integration,
private TEST configuration, and browser acceptance. This change targets
an isolated test environment. Live charges, public entitlement changes and
production rollout are outside its scope.
