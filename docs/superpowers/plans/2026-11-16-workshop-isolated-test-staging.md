# Isolated Workshop Stripe TEST staging

Issue https://github.com/lucronn/autodata/issues/445; parent https://github.com/lucronn/autodata/issues/398.
Project https://github.com/users/lucronn/projects/8.
Source base: a82b31dc8850aa3956972928b8c720969765a972.

Goal: Prepare current-source isolated Workshop Stripe TEST staging with truthful TEST-only notices and durable secret delivery.

## Decision-complete scope

Use a new branch/checkpoint on the reviewed current source. Add GET/HEAD notice pages at `/workshop/test-notices/terms`, `privacy`, `refund`, and `contact`, served only when the existing server-owned nonproduction Firebase Stripe TEST mode predicate is true; absent elsewhere, uncached, with no arbitrary filename/template input. Explain no real money, test cards only, temporary isolated grants, diagnostic/test data and existing maintainer issue feedback. State no production seller identity, retention duration, permanent-access or final tax/refund promise. Tax notice says the displayed USD20 is simulated and no actual payment/tax collected. Draft PR348 remains separate and unapproved.

Prepare a standalone offline Python renderer and JSON-secret process launcher, reusing the six fixed cached-image service shapes from the merged local stack without changing that stack. Use a unique project `autodata-workshop-stripe-staging-20261116`, fresh bound DB/S3/NATS under an explicit durable directory, read-only archived source and compiled binary, staging environment, Firebase auth, explicit nonproduction HTTPS origin and nonempty UID allowlist. Backend dependencies stay on one isolated bridge; only API may attach an egress bridge. Bind API host port to 127.0.0.1:3043. No production volumes/networks/mounts or inherited source credentials. Runtime source preparation uses git archive and a pinned source SHA, no writable repository mounts or go-run. Root reviews resource capacity and immutable source/binary/image identities before start.

Renderer starts with commerce disabled and purchase configuration disabled. An explicit test-enabled rendering selects stripe_test for both authorities only after root reviews; this may trigger authentic Stripe account/Price checks at private startup, so do not start it during offline implementation. Strong live-key denial before exec, exact per-role allowed secret names, credentials file0600 and no symlinks; private JSON read only by Python launcher and mapped to process environment, never printed or embedded in Compose. Firebase ADC has a separate durable read-only bind and is not silently copied from legacy gcloud state. No banking/model credentials or licensed seed in this lane. Empty startup is useful but not supplier/payment acceptance.

The existing tester restriction applies only in staging stripe_test; required UIDs are immutable server config. Never relax Firebase to local mode, emulator or browser-supplied identity. Do not use public aliases or redirect returns to production. A stable DNS route and Firebase authorized domain require actual account authority. An owner UID and additional tester UIDs require actual registered users. Test grants cannot grant live access; normal source/media rights remain enforced.

## Exact implementation allowlist

- apps/api-go/main.go (register fixed notice subtree)
- apps/api-go/workshop_test_notices.go and workshop_test_notices_test.go
- scripts/dev/workshop_test_staging.py and test_workshop_test_staging.py
- This plan, canonical operation and gate record/evidence documents

No other application/contracts/schema/UI purchase flow files are authorized. No production release, DNS/service mutation, Stripe operation or reuse of legacy ADC follows from code approval alone. Root coordinates Docker and runtime review.

## Validation

Meaningful denial tests cover unavailable production/disabled modes, four exact pages, unknown/encoded traversal/methods, HEAD and cache/security headers. Renderer tests cover production origins, HTTP, malformed or empty tester IDs, live secret material, unapproved secret keys, symlink/permissions, shared runtime roots, no secret values in rendered Compose, disabled default, stripe_test equality and exact resource isolation. Run focused/full Go API and Python helper tests plus diff check. Review exact candidate before runtime; preserve failures.

## Concrete todo
- [ ] Synchronize plan, Issue445, Project8 and canonical documentation; pass exact-base preflight
- [ ] Add server-gated TEST-only notices with route and production-mode denial tests
- [ ] Add offline isolated-stack renderer and durable JSON secret launcher; test production/live/shared-resource/empty-tester refusal
- [ ] Prepare reviewed current-source runtime inputs; hold Docker, DNS/origin and external Stripe TEST calls for coordinator review
- [ ] Run actual restricted authenticated TEST checkout/grant/read/denial/refund acceptance only after runtime prerequisites; do not substitute fixtures or claim missing licensed acceptance
