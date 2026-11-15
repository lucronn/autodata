# Private read-only runtime rollout verification

DRAFT: publicAPI acceptance and current private identity observed; final protected Python417 mergedsource remains pending. No synchronized implementation record or rolloutauthority.

Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8; plan docs/superpowers/plans/2026-11-14-private-read-only-runtime-rollout.md. Python417 and Go412 require protection/currentCI first. Prior61f1939 passed115isolatedcatalogtests but cannot start unchanged publicStripeTest and is retained test evidence only.

Todo: finalpins/sync/preflight; immutablemergedsourcefixtureacceptance; newbackup/protectedbaseline and exactsource/mode coordinatorrollout/rollback; health/quote/purchase/DB/protected and boundedselectortruth. Earlierbackups/containerspreserved.

## Pre-merge operational evidence

At reviewed Python head9a39f0971e3db1f1c2551f9813027f6d9c2fc41b, the actual pinned image5c8e79b93db4 passed a real CLI startup test on an internal-only network with a fresh synthetic schema042 database and no Stripe keys. Health200, disabled purchase even with enabled JSON, quote200/purchasablefalse, checkout503, providerNone and commerce transaction_read_only=on all passed. Container was stopped afterward; no serving data/config/service changed. Private receipt /home/corp/autodata-evidence/private-read-only-20261114/runtime-image-startup.json; public PR evidence https://github.com/lucronn/autodata/pull/417#issuecomment-6886830744. This is dependency/startup acceptance, not live paid access.

A read-only query inside exact serving private7ce6c5a98bec found underlying stripe_test and zero workshop_orders, zero configured merchant/mode/price matches, and zero matching active commerce entitlements. Thus existing live paid-library/grant behavior is unproven despite isolated test coverage. No merchant identifiers or secrets were output.

Final source must be exact protected417 merge before SVG419 dependencies; old-image/source-only release cannot silently include CairoSVG/libcairo source. Old predecessor rollback performs inherited Stripe merchant/price startup reads; new read_only runtime does not. These limits must carry into the synchronized release record.

## Public release accepted; private release still held

Coordinator accepted public3a18d9c release; independent binary hash0b17821ca4892d7776126c349db5fe70d5292c893a9acdca2ae5e27c3f0f9f93, APIenv74a93e2198fe8b024fadce9a26845990f3c15cbc9681ddd873a704e13a16aa03, override1172a455bfb2cea79a0f01112e467c37301cac4bc083c1bcee00632d0301f878 and PID620960 match. Effective publicmode read_only; upstream127.0.0.1:3031. Private exact7ce6c5a98bec69f57d2e1c53ac584f5c9a97e74eb3da0a474c8719b81e8c0d72 remains oldstripe_test/writable, source/image/security unchanged. Full raw config hashes and concrete backup/activation/rollback/selector phases are in the draftplan.

PR417 d966f2a remains requiredCIpending/BLOCKED at this observation. Post-Go-base isolatedcommerce/PG/privateHTTP47passed53subtests; networkdisabledGo read_only/quote tests and actualpinnedimage startup passed. These are premerge evidence, not finalsource authority. No finalcandidate/helper/createpayload/gate generated, no servingmutation or providercall. Gate remains DRAFT until exact protectedmerge and synchronized checkpoint.

Draft now distinguishes exact protectedfingerprints before selector invocation from controlled append-only sourcesnapshots/vehicle/selector changes due to reviewed automaticdeepening. Customer/commerce/article rows remain protected; baseline source snapshots may not be modified/deleted. Prior25-table SQL and oldbackups retained. Rollback reuses exact7ce6 predecessor, preservesDB and publicread_onlyAPI, keeps purchasingdisabled, and discloses legacyStripe startupreads.
