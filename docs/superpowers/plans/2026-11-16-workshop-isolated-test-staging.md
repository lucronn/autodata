# Isolated Workshop Stripe TEST staging

Issue https://github.com/lucronn/autodata/issues/445; parent https://github.com/lucronn/autodata/issues/398.
Project https://github.com/users/lucronn/projects/8.
Source base: a82b31dc8850aa3956972928b8c720969765a972.

Goal: Prepare current-source isolated Workshop Stripe TEST staging with truthful TEST-only notices and durable secret delivery.

## Decision-complete scope

Use a new branch/checkpoint on the reviewed current source. Add GET/HEAD notice pages at `/workshop/test-notices/terms`, `privacy`, `refund`, and `contact`, served only when the existing server-owned nonproduction Firebase Stripe TEST mode predicate is true; absent elsewhere, uncached, with no arbitrary filename/template input. Explain no real money, test cards only, temporary isolated grants, diagnostic/test data and existing maintainer issue feedback. State no production seller identity, retention duration, permanent-access or final tax/refund promise. Tax notice says the displayed USD20 is simulated and no actual payment/tax collected. Draft PR348 remains separate and unapproved.

Prepare a standalone offline Python renderer and JSON-secret process launcher, reusing the six fixed cached-image service shapes from the merged local stack without changing that stack. Use a unique project `autodata-workshop-stripe-staging-20261116`, fresh bound DB/S3/NATS under an explicit durable directory, read-only archived source and compiled binary, staging environment, Firebase auth, explicit nonproduction HTTPS origin and nonempty UID allowlist. Backend dependencies stay on one isolated bridge; only API, private ingestion and the TEST-only payment reconciler may attach an egress bridge (Firebase/Stripe HTTPS respectively). Bind API host port to 127.0.0.1:3043. No production volumes/networks/mounts or inherited source credentials. Runtime source preparation uses git archive and a pinned source SHA, no writable repository mounts or go-run. Root reviews resource capacity and immutable source/binary/image identities before start.

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

## Bounded TEST reconciler amendment (before implementation)

Coordinator instruction extends the fixed renderer to include a seventh payment-reconciler service only when the profile explicitly enables stripe_test. Disabled rendering still has six services and no reconciler. Existing runner scripts/dev/reconcile_payments.py and commerce/library/provider/schema implementation remain byte-unchanged. Changes stay in the two already allowlisted staging helper/test files and canonical docs/record.

The new role uses its own read-only private/reconciler.json bind with the fresh isolated staging DB/S3/internal material and reviewed TEST Stripe secret/webhook material required by the existing configured_commerce. Strict role key/public-environment allowlists exclude Firebase/Google/image/model/bank credentials. Require staging, stripe_test, separate HTTPS origin, exact postgres:5432/workshop_stripe_staging DB/user, test key prefix and configured expected merchant/Price before child creation. No public listener, production volume/network or provider credential expansion. Cached image, source, resource caps and restart:no remain fixed.

The wrapper invokes the unchanged runner in separate --once --batch-size10 child processes: at most10 passes, at most45seconds per child,15seconds between passes,600seconds wall budget. Discard child stdout/stderr and emit fixed sanitized outcomes only. Stop on timeout/nonzero/invalid mode or identity; never switch to the runner's indefinite default, retry errors forever, enable a live key or acquire provider credentials. Docker startup remains independently held. No knobs widen these bounds.

The existing runner retries verified pending events and calls reconcile_workshop_preparation. The preparation scheduler's articles path performs durable SQL job scheduling only; it does not fetch licensed source/model/media itself. The added service therefore advances reconciliation and queues/observes preparation but does not claim queued jobs complete without separately authorized source workers. Root separately reviews payment requests, source workers/rights, UID audience, IAM, origin and runtime activation.

Red/green validation: disabled service absence; enabled exact mode/DB/network/mount/command/resource/restart contract; private role/no Firebase/bank/model credentials; disabled/live/production/shared-DB refusal before child launch; exact existing-runner --once argv and finite10-pass budget; subprocess timeout/nonzero stop; wall deadline suppression and no secret/result logging. No database/provider/container needed. Run the full staging helper suite and offline Compose syntax validation, commit/push exact branch and report source/test diff.

Concrete todo:
- [ ] Pin this amendment with Issue445/Project8/canonical operation and pass preflight before implementation.
- [ ] Add red-first reconciler contract/budget/denial tests and fixed TEST-only bounded service/launcher role.
- [ ] Run offline tests/Compose syntax/diff checks; commit/push exact candidate for root review without runtime activation.
