# M2A serialized physical-slot amendment

Issue: https://github.com/lucronn/autodata/issues/444
Project: https://github.com/users/lucronn/projects/8
Private lane: https://github.com/lucronn/autodata/issues/401

## Goal

Run exactly one actual-store M2A authored-article browser acceptance before the held private selector fixture, under an exclusive released physical slot and a reviewed successor gate.

This amendment changes sequencing only: the private selector fixture stays held while M2A runs. Private acceptance is unfinished. The existing private worker17295/PID1552737 remains running and pinned, public PID1293423/binarybb11 remains unchanged. No supplier, Stripe, Firebase or other real external request is authorized. No Docker dispatch occurs while preparing this gate.

## Evidence and smallest executable correction

Sealed predecessor /home/corp/autodata-evidence/m2a-safe-origin-v3-executable-20261116/package-seal.json SHA603073cd09c1430ca6b1740d9369e4f04d24094af23bdc446ec901c122d7e17e remains immutable. Its schema incorrectly requires completed private acceptance for the newly requested order; do not write a false private_lane_complete statement. A uniquely sealed successor must replace only that requirement with a root-reviewed HOLD_EXCLUSIVE_DIAGNOSTIC_SLOT_M2A receipt (the exclusive M2A slot lease), pinned by SHA. It must preserve exact public/private process monitoring each cycle and reject lease mutation, wrong lane, missing hold/no-fixture statement, expiry or changed runtime identities before any dispatch. Root owns release of the shared lease and cannot authorize private fixture dispatch until M2A teardown evidence is accepted. A locally authored receipt alone is not independent evidence that fixtures stopped. Root must inspect exact private fixture/container/process/listener ownership first.

The predecessor old baseline home5914226688 minus observed5834194944 yielded80031744B drop and failed32MiB guard/64MiB cap; preserve that observation. Root subsequently removed114 pip HTTP cache files (143.1MB), retaining packages/data, and bounded old BuildKit cache. Fresh epoch1794808493.9617634 observation home5977300992/Docker2204266496/tmp6998933504B, RAM/cgroup7759732736B, inodes1041912 PASSES every unchanged predecessor capacity guard with home/docker/tmp growth0. Do not reset baseline, lower thresholds or release any reservation: the smallest successor keeps capacity-policy.json and m2a_capacity_policy.py byte-identical. Public SHA3102e80b8d52b44e225cfd4d23f6403080054660bc1b8e02665a618ad70455b7 and private PID1552737/startticks11073806 validated via /proc; no Docker call by this lane. Planning observations never authorize execution.

Private coordinator HOLD receipt /home/corp/autodata-evidence/private-selector-hold-for-m2a-20261116/HOLD.json SHA7b226815bd1bc5d7edc5db50b376a026bd35aee2930337b50396e5a2902b810f states selector fixture containers/processes/listeners18311,18312 absent and candidate physical source unallocated, private worker17295/PID1552737 running/restart0, private acceptance UNFINISHED_ACTUAL_IMAGE_NOT_RUN. M2A owns exclusive diagnostic slot until teardown and coordinator release; selector will not run concurrently. Root must independently review this receipt and current pins before creating the exact package authorization. Successor references this immutable HOLD receipt by exact path/SHA; its absence/change/wrong scope must refuse before imports or dispatch.

A separate canned-HTTP browser diagnostic /home/corp/autodata-evidence/article-reader-local-diagnostic-20261116 passed desktop/mobile body/step/image/back/reload/anonymous denial with120 requests and zero page/validator errors. It does not satisfy real PG/S3 acceptance, classify historical V2 error, authorize product edits or waive strict zero-error acceptance. Retain V3 RUNNER byte-identically and its safe error-origin journal in the real-store successor.

## Exact unchanged capacity admission

Keep capacity-policy.json SHA88b4f4c7a05af77b3928d15347111c6586ee0488b87742ee2139c1825fd3c01f byte-identical. Retain home physical5GiB5368709120B, unowned drift128MiB134217728B, public pending prep38604800B/install67108864B, private provisional128MiB134217728B, M2A64MiB67108864B =>warm5742858240B and strict entry>5809967104B. Retain Docker warm947912704B/strict entry>1015021568B including private64MiB and drift64MiB; tmp floor>=603979776B including private64MiB. Reservation arithmetic is conservative admission, not simultaneous fixture authorization. Private remains held regardless of capacity.

Retain sealed baseline epoch1794804436.660257/home5914226688/Docker990793728/tmp6696927232B; M2A home/Docker64MiB caps,32MiB aggregate free-drop stop including unrelated growth,32MiB burst; tmp128MiB cap/96MiB stop/32MiB burst. RAM/finite cgroup>=1GiB and inodes>1000. Any failed guard holds manual review with consumed stage receipts intact; no reset or retry. Current free passes unchanged thresholds, not proof of future admission.

## Exact authorization amendment

Authorization version2 exact fields: version, gate_sha, package_seal_sha256, public_identity_sha256, private_hold_path, private_hold_sha256, private_fixture_held(true), physical_slot_released(true), private_runtime(exact current process identity), stages(same sorted fixed list), created_epoch(same24h lifetime). No private_lane_complete or private_completion status remains. The supplied hold path/SHA must equal the exact reviewed receipt above, status HOLD_EXCLUSIVE_DIAGNOSTIC_SLOT_M2A; nested slot.owner must name M2A article diagnostic lane and selector_execution_held/selector_will_not_run_concurrently true; private_selector_acceptance remains UNFINISHED_ACTUAL_IMAGE_NOT_RUN; empty fixture lists; serving id/image/PID/running/restart0 match retained private baseline and exact /proc monitor. No authority writer is supplied; root reviews and writes version2 authorization only after candidate review. All prior absent-authority and one-use fences remain.

## One actual run boundary

After synchronized preflight, only explicit offloaded helper/metadata/test copies may change; <=4MiB, offload device1792/free>=1GiB, no binary/archive/store/credential copies. Preserve predecessor input metadata, all source/storage inodes, exact six IDs, source668d4c86/archive041f834/binarybb11/manifestda5353/config8ad/accepted09a and consumed V1/V2 markers. Use a new unique serialized namespace. No broad cleanup or source/product edits.

Successor review must demonstrate absent-authority and held-private refusal tests, exact thresholds/baseline arithmetic, current pins, unchanged browser/forwarder behavior and one-use pre-dispatch reservations. Root separately reviews package and issues exact authorization bound to the held shared slot lease. Then start only six exact existing containers sequentially postgres,nats,minio,migration-runner,ingestion-http,api; no create/build/pull/recreate. Read-only prebrowser actual schema/rows/objects attestation, exactly one loopback3042 relay/browser lifecycle with session-only auth simulation and actual PG/S3 article/image bytes, read-only postattestation, exact-owned cleanup and final pins. No standalone seed, synthetic catalog/body/image fulfillments, commerce or provider calls. Failures preserve diagnostics and stop the run; no automatic retry. Strict zero page/console/validator errors remains required.

## Todo

- Synchronize this amendment on Issue444/Project8 and validate the committed planning base before changing executable helpers.
- Root independently verifies private selector fixtures stopped/reaped and records an exclusive M2A slot lease; keep existing private worker/public process pinned without claiming private acceptance complete.
- Create one separately sealed offloaded V3 successor with slot-held authorization semantics and unchanged conservative reservations/baseline; preserve original seals and all one-use attempt markers.
- Run focused authorization/capacity/refusal tests and independent exact-package review, then root may authorize one six-container PG/S3 diagnostic, pre/post read-only store attestation and one browser lifecycle.
- Preserve all failures; tear down only exact six M2A IDs and owned relay/browser processes before root releases the slot to the private fixture.
