# Local empty Workshop M1

Issue https://github.com/lucronn/autodata/issues/398; Project https://github.com/users/lucronn/projects/8.
Canonical operation: `docs/operations/workshop-local-empty-runtime.md`.
Gate record: `docs/agents/records/2026-11-15-workshop-local-empty-runtime.json`.

## Goal and source

Boot a local-only empty Workshop, purchases disabled, no external ingress, Firebase/Stripe/provider credentials or requests. This is preparatory evidence;398 stays open for real-data/test-payment acceptance. Protected source76fb21e8f7c080e93f6d38de93a2e1a22cd11f39, tree c4b63d3635e7cc5b084f0d9df6154334e6dc36a3, parent5b3e19d;415 CI43664308427 passed. Exact source inspected: auth test/local remains supported;415 restricts staging+stripe_test via AUTODATA_WORKSHOP_TESTER_UIDS_JSON and is not exercised by M1. Snapshot/build from the final reviewed implementation commit, never shared mutable HEAD.

## Decisions

Standalone six services: api, ingestion-http, postgres, nats, minio, migration-runner. Fixed project autodata-workshop-local-m1-20261115; internal bridge network; only API host127.0.0.1:3041 to8080. No worker/reconciler/relay/fake service. Fresh empty DB workshop_local_m1 and bucket workshop-local-m1-sources. Environment test, local auth, commerce disabled, loopback HTTP origin localhost3041. Empty API ingestion URL prevents hydration: main constructs no ingestion client and catalog years stays in fresh PostgreSQL. Private HTTP gets health checks only; no provider-facing route. Empty bank/model/source URL configuration and no credentials, no inherited env files/ADC/host gateway/host network/external network. No DB/S3 data import or seed.

Storage root /home/corp/autodata-workshop-test-data-20261115/m1 must resolve entirely to physical ext4 /dev/nvme0n1p11, not autofs/offload. Data, source, binary, private config, Go caches/temp and evidence bind there. Secrets only fresh local random DB/S3/internal material, dirs0700/files0600. Pin cached local image IDs from operation doc; no pull/build/install into Docker. Host Go1.26.4, CGO disabled, readonly modules, explicit home caches. Verify Python installed package metadata against final pyproject; stop if incompatible.

Read-only container roots and bounded tmpfs, persistent PG/NATS/S3 home binds. SeaweedFS writes essential-looking work files under/tmp: bind durable s3-work there and test startup; do not substitute tmpfs. Any image/dependency/read-only startup contract failure stops this lane; no Dockerfile/app/schema change.

Budget: home build/cache4GiB, data512MiB, evidence64MiB, >=2GiB reserve. Docker admission requires measured startup allowance128MiB, capped six-service logs72MiB including overhead, measured unrelated-host growth over bounded run window, and512MiB reserve. Current free~962MiB is conditional headroom, not acceptance. Record actual bytes/inodes/layer deltas; stop before reserve violation. Root coordinator sequences Docker phases with article build lane.

## Red-first verification

Implement failing stdlib unit tests for semantic admission before helper/config: wrong/public port, extra service, build/pull fallback, wrong image, noninternal/host/external network, privilege/socket/device/host alias, RW source/config, escaping/symlink/autofs/device path, production/shared resources, enabled commerce or ingestion hydration, provider/Firebase/Stripe secrets/endpoints, unknown env/config keys, absent source/tree/archive/binary/config hashes, invalid images/dependency receipt, missing caps/read-only/tmpfs/S3 durable work, insufficient disk/inodes/unknown background growth and redaction. Use synthetic secret sentinels, captured config/inspect internally, fixed errors only. Helper is read-only, never up/run/exec/build/pull/start/stop/remove. Unit tests need no Docker/provider. Run existing compose-image tests once.

Actual bounded canary: exact project only; start backing services one at a time; measure disk/layers; migrate fresh DB; start private/API. Check dependency-backed readiness, Workshop/static modules, canonical disabled purchase, pinned disabled commerce responses, empty catalog and no product/order/grant/article/source writes (aggregate counts only). Confirm no ingestion client/worker and empty registry from exact source; do not call provider-facing routes. Restart only new API/private; recheck; stop new stack, preserve binds/evidence. Never touch production or old stage/checkout stacks.

## Exact file ownership

Planning checkpoint only: this plan, canonical ops and gate record. After passing exact-checkpoint preflight, implementation allowlist:
- infra/compose/compose.workshop-local-empty.yaml
- scripts/dev/workshop_local_admission.py
- scripts/dev/test_workshop_local_admission.py
- docs/operations/workshop-local-empty-runtime.md
- docs/verification/2026-11-15-workshop-local-empty-runtime.md

Coordinator can synchronize this record/tracking with evidence. No other repo files. No PR/merge/public deploy until independent coordinator review. If source changes required, stop and amend/recheck gate first.

## Todo
- [ ] Add red-first isolation/admission tests and standalone six-service cached-image Compose config
- [ ] Build immutable exact-source Go binary on verified physical-home storage and verify cached Python dependencies
- [ ] Measure fresh isolated startup/readiness, empty catalog and disabled commerce with no provider calls
- [ ] Stop only new resources and record exact-SHA acceptance and remaining398 blockers

## Successor

New synchronized gate required for Firebase/415 UID enforcement, Stripe TEST merchant/account/Price/webhook/purchase content, explicit egress/ingress and rights-cleared article/workers. Supplier rights, external tester UIDs and hosting access remain unresolved. M1 provides no paid/article/live-data/external-readiness claim and does not authorize GCE/DNS/publication changes.
