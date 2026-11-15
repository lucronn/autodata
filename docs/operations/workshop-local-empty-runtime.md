# Local empty Workshop M1 operation

Issue https://github.com/lucronn/autodata/issues/398; Project https://github.com/users/lucronn/projects/8.
Plan docs/superpowers/plans/2026-11-15-workshop-local-empty-runtime.md; record docs/agents/records/2026-11-15-workshop-local-empty-runtime.json.

Status: preparatory exact-source M1 canary accepted and stopped; see docs/verification/2026-11-15-workshop-local-empty-runtime.md. Purchases disabled; Issue398 remains open. Final protected-base integration requires a fresh synchronized gate.

Use a standalone Compose file and fixed project autodata-workshop-local-m1-20261115, internal network, zero Docker publications, and bounded host-only forwarder127.0.0.1:3041. Environment test/local auth, no Firebase, no credentials or requests to Stripe/providers/models. API ingestion URL empty prevents hydration. Fresh empty stores; six services only. No fake purchased content/grant or article seed.

## Immutable local carrier images

postgres sha256:151aa1c2e849e7828ed8aef2183ae15f692cbe887d2f28921d8b44b26e154d7e
nats sha256:8b9f712ae2148dcbd9d7f3d16a942d515e290526e5d018500931eab62b18e045
minio sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5
migration-runner sha256:ab20e934b27ba3ff927c1b4c9ff8cf6c32f315f743efe68dd3441182a87fb085
ingestion-http sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4
api sha256:93c9cc81d720d1ff82111b60a91820a263f3735a4dbb1efe189e63ec3a76e578

These are cached linux/amd64 image IDs for this host, no portable registry claim. Require pull never/no build. Host-built static binary overrides image application; immutable final source overrides every Python import path. Compare package metadata first, do not pip install into image.

## Private storage and admission

Root /home/corp/autodata-workshop-test-data-20261115/m1: prove device /dev/nvme0n1p11 ext4 and every bind no symlink/autofs escape. Evidence dir/default Go module cache elsewhere are offloaded; do not assume/home prefix means physical-home. Source/bin/config RO, PG/NATS/S3 data RW, Seaweed /tmp durable s3-work. Fresh local-only secrets; config0600/dirs0700. No prod dump/mount/network/endpoint.

Proposed limits MiB: API512, private768, PG768, NATS128, S3256, migration256. Read-only roots; tmpfs API32/private64/PG tmp32+run16/migration32/NATS16. Logs5MiB*2*6 plus overhead<=72MiB. No restart loops. Home cache/build<=4GiB/data<=512MiB/evidence<=64MiB; retain2GiB. Docker free must cover128MiB startup budget+72MiB logs+measured background growth+512MiB reserve; abort unexpected writes or projected floor crossing. All budgets are measured, not OS quotas. Capture redacted bytes/inodes/layers per phase. Request coordinator sequence approval before Docker startup or heavy writes.

## Ordered commands (pseudocode until implementation receipt)

1. Validate exact gate checkpoint with scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-15-workshop-local-empty-runtime.json --base-sha CHECKPOINT.
2. Run red-first tests, implement allowlist, run targeted and existing compose-image tests; commit/push for review. Snapshot exact immutable implementation SHA/tree, record archive/binary/config hashes.
3. Prepare private physical-home binds and ownership, no source data. Host build with home GOCACHE/GOMODCACHE/GOTMPDIR, GOTOOLCHAIN local, CGO disabled and module lock readonly. Check cached dependency metadata and image architecture/user/read-only entrypoint assumptions.
4. Secret-safe admission helper captures standalone Compose config JSON internally with explicit private env-file; never print config/env/inspect/raw logs. Check source/image/hash/network/mount/environment and disk-growth receipts. No mutation in helper.
5. Compose exact project/file/private-env up --no-build --pull never --no-deps postgres; measure/check; repeat nats/minio. Run the exact named migration-runner with its declared image volume masked by bounded tmpfs; preserve its stopped identity and volumes. Check schema and empty aggregates only in new DB. Start ingestion-http/api only; measure/check.
6. Check health/dependency-backed readyz, static assets, disabled purchase/commerce and empty catalog. Recheck source no-hydration/no-registry path and no workers. Restart only new API/private once; repeat. Record actual identities/limits/deltas and stops.
7. Stop exact new services; preserve bind dirs/config/evidence. No down -v, global prune, automatic reset or production changes. On startup/image/dependency/S3-readonly failure stop and report; do not widen scope.

No payment drain needed because purchases never enabled. On failure stop new app processes then backing resources; rollback only to independently verified M1 binary/config, otherwise leave stopped. New DB failures are never restored into production. No PR/merge/public deployment without independent coordinator review. M2 requires separate gate and actual TEST/Firebase/rights/ingress inputs.

## Loopback amendment checkpoint (2026-11-15)

Original local API boot succeeded only at its internal bridge address; Docker did not materialize127.0.0.1:3041 on internal network. All new services stopped; no loopback acceptance claimed. New plan docs/superpowers/plans/2026-11-15-workshop-local-loopback-forwarder.md and record docs/agents/records/2026-11-15-workshop-local-loopback-forwarder.json synchronize a bounded stdlib host forwarder: IPv4 loopback3041 only, exact admitted API ID/network/IP:8080, <=16concurrent/256total/600seconds, bounded64KiB buffers/15second idle timeout, per-connection+watchdog identity verification, fence on lifecycle change. Remove ineffective Compose ports; keep all Docker networking internal. No forwarder code/start before exact amendment preflight and root implementation review. Existing data, effective-ENV/image-volume guards and no-provider boundary remain. A clean credential-free ingestion build is required for external M2.

## Accepted local ingress contract

Launch only from admitted immutable source, with the pinned host Python and minimal environment. The forwarder has no target/bind arguments. Before listening it validates the exact six actual resources, policy/effective environment, storage identity, config/archive/binary hashes and capacity using the pinned local Docker executable/socket and minimal child environment.

The0600 process receipt uses exclusive lifetime flock and atomic replacement. Each connection is checked before and after upstream connect; watchdog checks API ID/network/IP/StartedAt/Pid/RestartCount plus archive/binary/source-tree stat guards. A restart, source mutation,600second lifetime or256connection limit requires explicit fresh admission/launch. Bounds:16concurrent,64KiB directional buffers,15second idle timeout. Listener127.0.0.1 only, no Docker publication. Stop verified forwarder PID then fixed M1 services; preserve data and the recorded old anonymous volume. No down-v/prune/reset.

HTTP entry/module checks and synthetic Origin/Cookie/CSRF transport tests passed. Firebase exchange is disabled; an authenticated Firebase browser/CSRF purchase flow is outside empty M1 acceptance. The cached ingestion image embeds nonempty credential defaults; explicit blanking/internal networking is M1-only containment. Replace it with a clean credential-free build before external exposure.
