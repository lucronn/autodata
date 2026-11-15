# Private read-only runtime rollout verification

DRAFT: final protected mergedsource, deployedpublicAPImode/identity and privatecontainer/config pin pending. No synchronized implementation record or rolloutauthority.

Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8; plan docs/superpowers/plans/2026-11-14-private-read-only-runtime-rollout.md. Python417 and Go412 require protection/currentCI first. Prior61f1939 passed115isolatedcatalogtests but cannot start unchanged publicStripeTest and is retained test evidence only.

Todo: finalpins/sync/preflight; immutablemergedsourcefixtureacceptance; newbackup/protectedbaseline and exactsource/mode coordinatorrollout/rollback; health/quote/purchase/DB/protected and boundedselectortruth. Earlierbackups/containerspreserved.

## Pre-merge operational evidence

At reviewed Python head9a39f0971e3db1f1c2551f9813027f6d9c2fc41b, the actual pinned image5c8e79b93db4 passed a real CLI startup test on an internal-only network with a fresh synthetic schema042 database and no Stripe keys. Health200, disabled purchase even with enabled JSON, quote200/purchasablefalse, checkout503, providerNone and commerce transaction_read_only=on all passed. Container was stopped afterward; no serving data/config/service changed. Private receipt /home/corp/autodata-evidence/private-read-only-20261114/runtime-image-startup.json; public PR evidence https://github.com/lucronn/autodata/pull/417#issuecomment-6886830744. This is dependency/startup acceptance, not live paid access.

A read-only query inside exact serving private7ce6c5a98bec found underlying stripe_test and zero workshop_orders, zero configured merchant/mode/price matches, and zero matching active commerce entitlements. Thus existing live paid-library/grant behavior is unproven despite isolated test coverage. No merchant identifiers or secrets were output.

Final source must be exact protected417 merge before SVG419 dependencies; old-image/source-only release cannot silently include CairoSVG/libcairo source. Old predecessor rollback performs inherited Stripe merchant/price startup reads; new read_only runtime does not. These limits must carry into the synchronized release record.
