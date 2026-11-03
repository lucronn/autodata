# Firebase customer identity verification

Issue: https://github.com/lucronn/autodata/issues/186

Project: https://github.com/users/lucronn/projects/8

Reviewed candidate `b4f3dc86a18a8087f8ff664e37bec594909eae80`, gated at
`1211382ee3aa9bdc59c0003169ec000c2f971ced`, is integrated as
`3fdcd0bc0ac993dd15ad2219df9d09ffeed27a4e`. The merge preserves all six
meaningful implementation/correction commits. Exactly35 authorized paths;
historical SQL001–038 unchanged. Full integration CI passed as recorded below.

The official Firebase Admin SDK verifies fresh Google identity and live user
state. Server-generated accounts and opaque hashed PostgreSQL sessions enforce
rotation, expiry, revocation, Origin and CSRF; production configuration fails
closed. Paid grants/catalog/media and the final customer UI remain later lanes.
No identity-only production deployment or live Firebase configuration is claimed.

## Independent review and correction

Full8c7507 review: `/tmp/autodata-r5-8c7507-independent-review.md`. Its sole P1
placed three Firebase startup settings in ConfigMap metadata. Successor b4f3dc8
moves them into data and tests the parsed mapping; six manifest checks pass and
reject the original defect. Successor review:
`/tmp/autodata-r5-configmap-successor-review.md`, SHA256
`f0dd85b0c0c9e7db5e4cd7ea839e1caa6c6d14f8ea648f9a5e05818853875185`.
Root independently reviewed the two-path correction and repeated those tests.

## Actual identity and migration acceptance

`/tmp/autodata-r5-acceptance-b4f3dc8-junit/artifacts/acceptance-result.json`:
passed, exit0,145.518 seconds, no failures, owned resources cleaned up.
All55 exact outer pytest cases and seven native subtests passed without skips.
The actual Go root executed all five required scenarios:

- ConcurrentCustomerProvisionAndRotation
- SharedSessionRevocation
- ExpiryAndPersistedSecrecy
- FirebaseExchangeAndUserRevocation
- FirebaseStartupRequiresMigratedPostgres

The independent validator checked39 exact migration rows plus the separate
historical038 refusal database, seven safe fixture account rows,29 hashed
session rows, official SDK/HTTP scenario execution, eight raw-artifact hashes,
exact candidate/input/Git provenance and clean host/runner observations.
The immutable supervisor is `/tmp/autodata-r5-access-supervisor-junit.py`,
SHA256 `3c8528266bca246f0de5843a3a555611d6f25110129c35ea012124db278bc841`.
Independent coordinator approval: `/tmp/autodata-r5-junit-root-review.md`.

The earlier `/tmp/autodata-r5-acceptance-b4f3dc8` run remains failed: tests passed,
but its host parser expected the wrong pytest root/classnames and omitted native
subtest accounting. No receipt/artifact was changed. A separately reviewed
successor derives exact55 identities from committed config/source and seven
subtests from the two literal5+2 loops; it still rejects missing/extra names,
wrong classes/counts, skips/failures, stale provenance and cleanup failures.
Root independently ran16 pure checks and a harmless real-config55+7 probe plus
six XML mutation rejections before the fresh acceptance above.

## Actual dual-bank regression acceptance through039

`/tmp/autodata-r3-039-acceptance-b4f3dc8/artifacts/acceptance-result.json`:
passed, exit0,164.389 seconds, all eight actual HTTP/worker/PostgreSQL/S3 cases,
eight distinct fixture databases, no failures, owned resources cleaned up.
Cold repeated requests reused one durable job; source remained readable during
rewrite; publication was atomic and warm reads made no new provider/model/ensure
calls. Ordered content/action/instructions/images and no invented step number
were checked against raw PostgreSQL projections. Fresh, empty and populated
migration replay through039 preserved full schema/data evidence.

Supervisor `/tmp/autodata-r3-039-acceptance-supervisor.py`, SHA256
`ad7e51196735b4bea3149a45b53c9434fe547602a3f683a6e132fa5eaa4b4966`.
Root independent approval: `/tmp/autodata-r5-supervisors-root-review.md`.
Original038 supervisor/receipts remain unchanged.

## Integration verification and remaining gates

All35 R5 implementation paths at the integration match the reviewed candidate
except the independently approved one-line StorageKey privacy spacing assertion.
Integration Go API and Go contracts pass;104 development tests and19 shared
contract tests pass. Logs: `/tmp/autodata-r5-integrated-{go,dev,contracts}.log`.
Author SDK-inclusive race checks and independent targeted SDK/session tests pass.
Actual integration GitHub CI41696273960 passed at
472492dd868122b2b0da00dc84e15c5424aa0276, including the live Compose smoke.
This completes the identity dependency checkpoint. Later merchant/project/domain, real Google/Stripe
HTTPS staging, paid access, browser and recovery/cutover acceptance remain required.
