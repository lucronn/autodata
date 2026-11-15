# M1 local loopback forwarder amendment

Issue https://github.com/lucronn/autodata/issues/398; Project https://github.com/users/lucronn/projects/8.
Canonical operation: docs/operations/workshop-local-empty-runtime.md.
Record: docs/agents/records/2026-11-15-workshop-local-loopback-forwarder.json.

## Problem and exact base

Base e23c183b8b9c7b87093d1ed61d115f9723e7b83f/tree16bce16afb2261f476817a4967c9b7c741b4b435, descends protected415 merge76fb21e. Original gate1a3044d passed before implementation. Current internal Docker bridge records HostConfig publication but creates no actual published listener. Direct internal API health/ready/Workshop200 and purchase disabled were independently confirmed; loopback3041 fails. All six new resources stopped, data preserved. This amendment authorizes a bounded local host forwarder, not public ingress or API egress.

## Decision-complete correction

Keep Docker network internal=true; remove API ports stanza. No Docker host publication on any service. New standalone stdlib host TCP forwarder listens only IPv4 127.0.0.1:3041 and targets only exact admitted API ID's internal IPv4:8080. No configurable bind/destination/origin/port, auth injection, HTTP rewriting, DNS, firewall/tunnel/host-network/new image/package. Minimal process environment; no daemon/autostart.

Before listening read exact0700 root/0600 accepted-state+manifest; reject symlinks, wrong owner/modes/pins. Inspect fixed-project resources for exact accepted IDs/images/labels/internal single network/RO/security/mount/no-host-port policy and zero foreign attachments. API must be running; destination from that exact ID and network IPAM, private IPv4 inside its subnet. Bind that ID/image/network/IP/source identity for process lifetime. Revalidate exact API identity/network/IP before every accepted connection and in a watchdog with finite read-command timeout. Changed/stopped/failed-inspect/mismatched resource immediately fences listener and all active sockets; never automatically refresh target. After intentional API restart run full admission, explicitly launch a new forwarder and record new process/identity.

Limits: <=16 concurrent connections, <=256 total connections, <=600second lifetime, <=64KiB relay buffers/direction, finite15second idle timeout and finite2second upstream connect/inspect budget. Close semaphore slots/both sockets after EOF/error; TERM/watchdog/lifetime closes listener/clients. Emit only constant codes and IDs/hashes/counts, no body/header/env/connection strings. Record PID/process start/executable/script/source/receipt hashes privately and stop only that verified process. App remains test/local auth/commerce disabled, no provider/payment/Firebase credentials or requests, no data seed, internal-only network and existing storage/image effective-ENV safeguards.

## Exact implementation allowlist

- infra/compose/compose.workshop-local-empty.yaml
- scripts/dev/workshop_local_admission.py
- scripts/dev/test_workshop_local_admission.py
- scripts/dev/workshop_local_forwarder.py
- scripts/dev/test_workshop_local_forwarder.py
- docs/operations/workshop-local-empty-runtime.md
- docs/verification/2026-11-15-workshop-local-empty-runtime.md

Coordinator planning checkpoint files: this plan and docs/agents/records/2026-11-15-workshop-local-loopback-forwarder.json plus canonical ops. No application/schema/frontend/image/workflow/global host config changes. No public deployment, PR or merge before independent root review. Root reviews exact implementation before runtime retry.

## Red-first tests

Reject wrong/missing/source-mismatched/symlink/unsafe-mode receipt, wrong API/image/owner/network/IP/subnet/RO/user/security/actual publication, foreign attachment, configurable public/IPv6/listen/target. Enforce inspect errors/timeouts fail closed with redacted output. Changed lifecycle/IP/network closes listener/clients rather than rebinding. Test concurrent/total/lifetime/idle/buffer caps, slot cleanup, EOF/partial sends/backpressure, occupied listener, fixed read-only Docker commands. Relay synthetic HTTP request/response bytes with Origin/Cookie/CSRF/custom headers unchanged; no real auth tokens or provider calls. Unit sockets use ephemeral loopback endpoints; no Docker/provider services.

Runtime acceptance: exact source/binary/config/image/state pins; all six services under actual fixed policy; zero Docker actual host publications; launch host forwarder with exact process identity and only127.0.0.1:3041 listener. Through it verify health/ready/Workshop and all local asset modules, canonical purchase disabled, local-auth config, empty catalog using synthetic local fixture header, denied commerce and appropriate auth/CSRF behavior. Since Firebase is intentionally absent, do not claim authenticated Firebase CSRF/session acceptance; header transparency is exercised by synthetic relay test, local auth-disabled HTTP path checked honestly. Check immutable Python source, empty registry and blank external effective material. DB remains42migrations/one canonical bootstrap product, zero customer/session/order/payment/grant/article/source/configuration rows. Stop API to prove relay fences, restart/admit API and explicitly launch new relay; recheck. Stop relay then only new M1 services; verify3041 absent/all resources stopped/no foreign attachments/data preserved/storage reserve. Old failed-runner anonymous volume remains preserved. No production/old stack mutation.

## Storage and rollback

Existing physical-home/cached-image/no-build caps/reserves unchanged; new forwarder allocates bounded memory on host and writes only bounded private receipts. Recheck Docker/home bytes before phases; terminate relay before reserve breach. Failed isolation/readiness/ingress stops only M1 resources, preserving binds/receipts. Never delete/reset/prune globally or kill by port/name pattern. Cached ingestion image has embedded nonempty credential defaults, local checkout-test tag and no registry digest; M1 explicit safe overrides/internal network contain it, but M2 external testing must use a clean credential-free build.

## Todo
- [ ] Add red-first fixed-loopback relay/identity/lifecycle/concurrency/buffer/header-transparency tests
- [ ] Remove ineffective Compose publication and add bounded host forwarder with exact API/container/network/IP binding
- [ ] Build immutable amended source and prove loopback health/assets/disabled empty-state plus fail-closed restart behavior
- [ ] Stop only new M1 forwarder/services, preserve data and record evidence; keep398 real-data acceptance open
