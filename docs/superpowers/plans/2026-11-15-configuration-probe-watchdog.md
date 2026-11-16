# Configuration probe watchdog helper

Status: helper-only core and33 offline tests complete; runtime integration and execution held.

Issue: https://github.com/lucronn/autodata/issues/401
Project: https://github.com/users/lucronn/projects/8
Protected source base: 4048f3fae50161af5b5ab8300670e3beb817ce1a
Pending product/runtime SHA: UNSET (PR429 is not merged or deployed).

Implement a helper-only, fail-closed one-request configuration watchdog core and offline synthetic tests on protected4048; product runtime source remains unresolved and all live execution held.

Implement scripts/dev/configuration_probe_watchdog.py and focused offline tests only. No Docker/provider calls or service mutation in this lane. The helper's runtime admission refuses unresolved product source, unreviewed execution manifest or absent supervisor identity. Core accepts injected clock/backend for deterministic offline tests. All child operations pin absolute Docker/local socket/empty physical config/minimal environment; no shell. Durable exclusive markers fsync file and parent before actions. Strict matching start/finish events use allowlisted fields only; missing/ambiguous events never prove finish. One exact URL and no retry; mark attempt before dispatch. Fence exact reviewed ID with intentional stop --time0 and confirm stopped/Pid0 before same-ID restart. Missing START/unknown stop is inconclusive, never unsafe restart. Rollback independently verifies predecessor identity before mutation and freshly before starting it; finally recovers only a verified predecessor after candidate failures. Post-start identity/passive fingerprints remain required; no automatic DB restore. Transient service/finalizer production integration remains for fresh merged-source gate, so this helper alone cannot arm live traffic.

Current private343896791b0377600b9825b53c1ddb1b179d54c424d19ea935c0b9b8a681eb07/source083f1a502a0f18d371793df59d3310408059d44e/image3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7 remains unchanged. Preserve6fcc910d46d5740b556c2fc0d0ac527a9e180cf0f27c1a60e5d8815ca84ef9a4 secondary. New runtime gate must pin image/config/security/env, physical archive/dump/restoration list, protected27/catalog12 baseline, storage floor512MiB+64MiB allowance and local DockerRootDir; independent root review before mutation. Runtime watchdog plan allows<=30s observation+<=15s recovery/postcheck, subject root review. No provider-zero claim with public ingress.

Todo:
- [x] Commit/push synchronized Issue401/Project8/plan/docs/record checkpoint and pass preflight before helper edits.
- [x] Red-first implement fixed-context child runner, crash-durable single-attempt state, strict safe event correlation, exact-ID fence/restart/rollback safeguards and CLI validation; offline fake backend only.
- [x] Test hostile environment, output redaction, arm/one-request ordering, timeout/identity/recovery failures and durable write order; commit/push reviewable helper.
- [ ] Hold arm, GET, Docker/service execution and runtime source unset; after429 merge fresh-sync exact protected source/runtime gate and add independently reviewed actual-image/supervised-service fixtures before activation.

## Coordinator review amendment

Pinned helper base2a7ca7b8db0718261e1e71878d460acf3918a222. Red-first predecessor fingerprint/inspection drift: no container mutation, durable attempted marker remains, no successful fence/restart/disarm receipt, no replay. Known-good predecessor still recovers after candidate stop/inspection failure, with fresh pre-start verification. Add explicit injected supervisor liveness verifier immediately before dispatch; dead/reused PID/start ticks/boot/unit mismatch refuses GET before attempted marker. Runtime adapter must supply independently supervised liveness evidence; no stub/default success. CLI validate-only/no live calls.

## Runtime admission review amendment

Supersedes unconditional finally recovery: predecessor identity alone is insufficient. Exact candidate stopped/Pid0 (or demonstrable absence) must be proven before predecessor start. Unknown inspect/stop or still-running state holds INCONCLUSIVE with durable refusal receipt; stop exception followed by confirmed stopped can recover. Already-running verified predecessor receives no duplicate start. Preserve one-attempt markers; no DB restore. Red-first regressions apply to both helper core/private adapter.

SQL guard rejects extra statements/semicolons before execution, preserving existing fixed SELECTs. Raw DockerHTTP.connect rechecks pinned socket identity at actual mutation boundary. Combined protected27/source/catalog12 baseline must use one bounded READ ONLY transaction (3s per statement,15s overall); do not claim separate transactions atomic. Red-first admission and baseline tests. No stage/activation/GET before independent review.

## Restart-policy and execution-seal amendment

Before predecessor start, issue exact-ID intentional stop even for a previously stopped/restarting candidate. Confirm exact identity, Running=false, Pid0, Restarting=false, Status in created/exited/dead and stable post-stop observation; mere crashed/stopped observation is insufficient under unless-stopped. Stop failure/unknown holds unless an owned-fixture-proven intentional-stop contract and stable stop proof exists; no automatic predecessor start from uncertain state. Prove running/restarting/already-stopped/Created in owned synthetic no-network Docker fixtures; no serving mutation.

Seal helper/passive adapter/input hashes in immutable execution manifest. External fixed-hash launcher validates manifest+scripts and injects reviewed seal binding; direct mutation CLI refuses without it. Recheck bound seal at phase admission and Docker stop/start/raw-create boundary. Final root recipe validates external launcher hash immediately before every mutating phase. Preserve earlier seals as superseded review evidence; no activation/GET.

## Staged17295 watchdog integration checkpoint

Product protected272aeeaad8399c305468e5d486cc391d7340f6a4/tree7dc98e7fcbb984c01b8deb76c8a611b4a553e240. Root stage-only execution created17295fae5fe60b5b9c78b81206a3a0c8f3e202b811093f91ebb821babe648f3e, image3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7, Configc3f41d4fd990904af072ad63ff588fb6b9527c6d9c31161fa2dbc24822026a4a, HostConfigace39cbce4c5b09bf04d83733fa238bc76c9cff5b0d42b3acfd0daabae62e5db, Mounts057d43e246c0e85a9f8c972cde61120e5e6aecdfd8384d403f60ac0540cb539c. Candidate remains Created/Pid0/never-started/restart0. Root343/source083 still serving; preserve6fcc secondary. Existing sealed rollout launcher-v3 unchanged.

Implement separate watchdog adapter/module+offline tests and private fixed manifest/launcher. Fixed exact candidate identity; at arm bind actual post-root-activation StartedAt/Pid/restarts0 and activation result. No arm before root activation/approval artifact. Watcher independently supervised system unit, RuntimeMax28s/ExecStopPost recovery, exact unit+PID/startticks/boot/argv/cgroup liveness before one durable attempt. Pre-arm safe full-history log cursor excludes open target attempt; post-arm matching new START/FINISH only. T25 exact-ID intentional stop--time0, stable stopped/Pid0/Restartingfalse status before same-ID restart. Unknown start/identity/stop/supervisor/log state holds inconclusive; no second GET. SQL/passive state observations follow finish or confirmed fence; avoid holding mutation lock on slow SQL before a necessary deadline fence. External execution seal covers adapter/core/config and pinned rollout/baseline dependencies.

HTTP adapter absolute curl -q, empty/minimal env, proxy/config disabled, no retry/redirect, connect3s/total5s/1MiB response cap; exact one URL. Safe response flags/counts/hash only; strict logs in memory, no raw docker logs/error text saved. Coherent39-table baseline before and after verified worker return/fence, exact auth/payment/article invariants, preserve baseline rows and enumerate target-scope catalog/source additions without guessing legitimacy. Local budget502/partial remains truthful. Repeat stored SELECT-only selector safety aggregate afterward; initial makes/models unbounded follow-up separate.

Offline red-first tests cover bounded child argv/env/output, supervisor liveness/identity, exclusive phase markers/caller failure, exact-ID stop/restart/no overlap/restart policy, safe event cursor ambiguity, HTTP one attempt and safe result parsing, coherent baseline receipt. Prepare a production-shaped synthetic supervisor+owned network-none container fixture for root admission; do not execute additional system unit until admitted. Root reviews concrete complete watchdog manifest/commands before activation/supplier GET. No serving mutation/provider GET by worker.


## Current source-only PR440 integration checkpoint

Protected `be1a1f235e8eeacc051ac905c4ed8a953a41c8a9`; current integration plan `docs/superpowers/plans/2026-11-15-pr440-protected-be1-integration.md`; all earlier source/runtime TODOs are historical and do not grant execution authority. Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8.

- Synchronize Issue401/Project8, corrected canonical current-versus-historical docs and matching records at a docs-only protected-base checkpoint; pass exact checkpoint preflight before copying helper files
- Copy the exact four helper and four test blobs from reviewed0212dd8d, run focused owned/offline tests and verify all eight Git blob IDs unchanged
- Push the refreshed draft PR440 with an exact old-head lease, update its base/head verification text and run required exact-head CI; hold merge, build, activation, runtime and provider requests for root
