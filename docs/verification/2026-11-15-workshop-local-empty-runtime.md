# Empty local Workshop M1 preparatory acceptance

Issue https://github.com/lucronn/autodata/issues/398 and Project https://github.com/users/lucronn/projects/8 remain open/In Progress. This empty local milestone does not establish real-data/payment/external-tester acceptance. No PR/merge/public deployment at this checkpoint.

## Pins and tests

Initial gate1a3044d4ef0e149cee99779e1bd24490bbf9b499 on protected76fb21e8f7c080e93f6d38de93a2e1a22cd11f39; amendment gate0c80cdfcd195a992f528c1dc7faccd59650b4579. Both exact machine preflights passed synchronized/errors[] and coordinator review.

Accepted runtime source94d3f499034253a1d1a331f50892b287c0a6d7f0, tree06f3a9e53da06f8345e0d0e1bd48ed3f00f159a5. Archive SHA2568aa1f293750d448d464d4c1312e9b8367cf18ebba211c6ba849fc2bf4b45a990; static binaryad5ad70c777a19c2446275cf7640e8777429d3fc3bb334cc3522ff43e1d29750; canonical rendered configc977e3a10e8f987bd6119f428b5407312840bd51ce0aefe4d16a5355e6e9d3d3. Binary reproduced with Go1.26.4, CGO disabled, readonly module lock, trimpath/buildvcs=false and cached file proxy. Private local-only material was not committed.

33 admission/forwarder tests,3 existing Compose tests,3 private phase-verifier tests green; diffcheck clean. Red-first coverage includes image volume/env drift, exact resource ownership/storage, actual six-service effective policy, same-ID restart, pinned local engine despite ambient overrides, post-connect identity changes, bounded source stat manifest, lifetime flock, limits/buffers and synthetic header transparency. Coordinator independently reviewed/reran33 tests.

Master later advanced through #422 to5981b97f187364e54737919fd8cdb49e7566d981/treeb3f321d0263e12da2d5c54f136c9ffcee155e1d1. This canary acceptance applies only to94d3f499; final integration requires a fresh synchronized gate/checks on that protected base.

## Actual acceptance

Full admission and actual policy/effective ENV passed before each transition. Corrected migration ran twice idempotently plus final refresh:42 ledger rows, state hash8da0fdf80336bd4f23cc545680d75485. One dataset_products bootstrap metadata row is migration040 behavior. Accounts/sessions/orders/payments/grants/articles/sources/fetch-jobs/configurations remained0. S3onebucket/zeroobjects. Source connector registry empty, implementation module bound from admitted source. No outbound provider/model/Stripe/Firebase requests.

Loopback health/ready/Workshop200; seven app modules plus entry assets200; purchase/demo flags false; catalog years empty; quote/webhook503; checkout/library401; Firebase exchange503 with synthetic headers. Coordinator independently probed health/ready/Workshop/purchase-config and exact127.0.0.1:3041 listener. No browser automation or authenticated Firebase/CSRF purchase flow executed.

All Docker actual/configured port maps empty. Internal bridge retained no foreign attachments. Binary-mtime-only mutation fenced relay/listener in0.162seconds; bytes/hash unchanged, timestamp restored. Same-ID API restart changed StartedAt/Pid and fenced second relay before private restart. Explicit fresh full-admission relaunch restored readyz200. Private restart healthy. The12.27second receipt duration covers the entire restart/relaunch sequence, not watchdog latency.

## Preserved resources and storage

Project autodata-workshop-local-m1-20261115, internal network3ebd9291b87f7e3cdad85cf3c9cb4577c0ccea071dbafcbc9f3a84727a7f41b6. Cached image IDs fixed in Compose/admission.

| Service | ID prefix | Limit MiB | Final |
|---|---|---:|---|
| postgres |328d13561c8e|768|stopped|
| nats |d92655906957|128|stopped|
| minio |650eeaaa7b68|256|stopped|
| migration-runner |4e88d506bd84|256|exited0|
| ingestion-http |385982ee418a|768|stopped|
| api |4c86cb6499ef|512|stopped|

All writable image layers0; RO roots, cap-drop ALL/no-new-privileges, bounded log/tmpfs. Final relay absent,3041 absent, network attachments0, admission errors[]. Root/config0700, private config/receipts0600; physical-home ext4 storage identities preserved. Old failed-runner anonymous volume04571933a18251e9cd4f03e17ef2adc55d3dc8365b950feed68619b5ffe14ed9 preserved. Production/checkout/stage untouched.

Docker free1,007,259,648 versus first sample1,008,435,200:1,175,552bytes net consumed across canary work/background. Home free11,056,533,504bytes; data70,438,912bytes; caches/modules/temp1,385,934,848bytes; live-sample evidence151,552bytes. Preserved snapshots/build artifacts also consume home. All reserve/budget admissions passed; these are measured budgets, not quotas.

Private0600 evidence under /home/corp/autodata-workshop-test-data-20261115/m1/evidence/: loopback-http-acceptance.json, forwarder-lifecycle-acceptance.json, final-live-storage-acceptance.json, final-stopped-acceptance.json, forwarder-migration-refresh.json and phase receipts. Raw private config is not repository evidence.

## M2 prerequisites

Separate gate: clean credential-free ingestion build/digest; explicit Stripe TEST account/webhook inputs; Firebase project/UID allowlist/tester rights; supplier display/copy/test-use rights; ingress/hosting credentials and cost choice; real-data provenance and purchase/entitlement acceptance. Cached ingestion local image embeds nonempty credential defaults and has no registry digest; M1 blanking/internal-network containment must not carry into external tester exposure.

## Protected integration history

Fresh gate eddff105bd8e2f924add34cba837367e8fff0009 passed before exact five reviewed blobs were copied onto5981b97. Integration headdebedf34c3ec3cf711941cf7bc12c085995c90c0/treef3d411ca92fe5058ef555d0845d15f21e25b2109 passed all three jobs in [CI43668033888](https://github.com/lucronn/autodata/actions/runs/43668033888).

Protected master then advanced through #425 to083f1a502a0f18d371793df59d3310408059d44e/tree2c6a681b31c0031743f5580825949ad192e87f04. Follow-up plan docs/superpowers/plans/2026-11-15-workshop-local-m1-protected425-integration.md requires a docs checkpoint/preflight before normal source merge and exact-head CI. Historical94d3 local canary remains stopped and distinct; no integrated runtime claim.
