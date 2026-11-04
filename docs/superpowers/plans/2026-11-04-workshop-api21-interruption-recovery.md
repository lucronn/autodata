# API21 interrupted-run recovery — decision-complete planning draft

Planning only. This draft performs no repository/GitHub/Docker mutation and launches no runtime. Coordinator must adopt, synchronize and independently review it before the new run. Profile remains gpt-6.1-sol / medium / priority, no fallback.

## Goal and evidence boundary

Obtain one complete immutable full21 author-run receipt and independent raw acceptance review at application candidate `e5fed171bb36fdb759c592cbcd0e15aea5490c97`, using the unchanged approved supervisor/runtime/fixtures. Keep the original synchronized gate `e0e50dee3a5f985dd1f7586fc7a4d681aaf77323` as historical planning provenance; the recovery amendment gets its own committed synchronized checkpoint SHA.

Original full root `/home/corp/autodata-evidence/api21-e5fed17-full-20261104` remains untouched. Its JUnit reports 21/21 passes and it contains 21 per-case result.json files. These establish observed scenario execution only, subject to independent identity/assertion/provenance audit. They do not establish successful supervisor finalization: acceptance-result.json, artifact-inventory.json and host-after.json are absent and the supervisor process is gone. Do not create substitute files there, invoke finalizer methods retrospectively, concatenate receipts, or call it a complete accepted run.

Independent raw audit `/home/corp/autodata-evidence/api21-e5fed17-full-20261104-independent-readonly-audit/audit-receipt.json`, SHA256 `543985c4fe88230f74a3adb80617b8e67f8b07931f1e3bba761b1e7bdcb320fe`, preserved all325 raw files /7,375,945 bytes. Frozen pure validate() over the extant bytes returned `{'api':21}` and re-derived21 JUnit IDs,21 distinct databases and40 migrations per case. The audit also found host-after, runner-inspect/log, browser-counts, artifact-inventory, acceptance-result and per-container final snapshots absent; command-results stops at39. This is useful validated scenario/provenance evidence with a documented finalization gap, not a complete supervisor acceptance.

The coordinator's supplemental cleanup receipt `/home/corp/autodata-evidence/api21-e5fed17-full-20261104-interruption-recovery/cleanup-recovery.json`, SHA256 `0e6587d7563a24eea00b9467d955bf6767be757f97d5730c2a2e3ae18baf9881`, records separately observed owned-project cleanup after interruption. It is retrospective cleanup evidence, not the missing original supervisor completion or original host-after snapshot. Preserve timestamps and classifications. The original pilot has a passing author receipt; count it as zero acceptance cases and independently verify it before carrying its precondition forward.

## Scope and authority

The recovery changes documentation/tracking and execution logistics only. Implementation allowlist is empty. No application, fixtures, dependencies, Compose, SDK, supervisor/base wrapper, image, input-manifest bytes, assertions, case inventory, deadlines or runner limits change. No repair is inferred from a turn interruption. A demonstrated defect or proposed harness change requires a separately narrowed synchronized gate and independently reviewed bytes.

Adoption references Issue https://github.com/lucronn/autodata/issues/186 and Project https://github.com/users/lucronn/projects/8 . Use the currently authorized sole tracking writer; do not infer this draft author has writer authority. Append the interruption classification, exact original/supplemental evidence identities, replacement root, launch mechanism, six todos below, remaining acceptance obligations and unchanged limits. Preserve previous Issue body/comments and Project fields, read back exact values and hashes, and retain synchronization evidence.

Update the existing API21 plan/task/record, canonical customer-UI plan/runbook, orchestration plan/queue and tracking-evidence record in one coherent docs-only checkpoint. Retain the original frozen manifest unchanged. Pin the full successor checkpoint SHA, run the canonical pre_implementation.py preflight against that exact checkpoint and record synchronized/errors=[]. Obtain independent exact-checkpoint review. This grants no automatic runtime authority: coordinator's explicit bounded recovery dispatch is distinct. The original no-automatic-rerun rule remains in force; this amendment is the explicit new full-run decision after retained interruption diagnosis.

## Fresh roots and launch ownership

Keep source `/home/corp/autodata-evidence/api21-e5fed17-source` only if it is still an owned clean non-symlink plain clone at the full exact application SHA, no remote/credential surprises, and frozen manifest matches committed blobs. Never repoint the shared working checkout. New full root is exactly `/home/corp/autodata-evidence/api21-e5fed17-full-recovery-20261104`; separate launch/audit root is `/home/corp/autodata-evidence/api21-e5fed17-full-recovery-20261104-supervision`. Both must be absent, non-symlink and on the verified evidence filesystem immediately before preparation. Do not precreate the full root: supervisor requires absent run-root. Precreate only owned private supervision root (0700, files0600, umask077). If either name is occupied, stop and revise/read back an explicit distinct root; never overwrite or append to a previous attempt.

Read-only observation during this draft: `systemctl --user show --property=Version --property=SystemState --no-pager` exited0 with Version=261.2-1 and SystemState=running. This confirms a reachable current user manager, not permission to launch a service or canary and not its future availability.

Select a user-manager-owned transient service, independent of chat tool subprocess lifetime, with fixed unique unit `autodata-api21-e5fed17-recovery-20261104.service`, Type=exec, RemainAfterExit=yes, Restart=no, KillMode=control-group, RuntimeMaxSec=3500 and TimeoutStopSec=200. RemainAfterExit=yes is mandatory because a successful transient service without retained active state may be garbage-collected before exit readback. Never use --collect. This is an outer emergency watchdog, not a replacement for or extension to the supervisor's internal 3300-second acceptance deadline and 180-second finalization reserve. No restart or repeat policy. Retain exact launch argv, unit properties, MainPID/start identity, start/exit status, stdout/stderr and unit completion observations in the separate supervision root. Do not put live outer stdout/stderr files inside supervisor-inventoried artifacts; their writes after inventory could invalidate hashes. Keep unit/journal output private.

Before real dispatch, verify the user manager is available, the unit name is unused, the service runs as the expected unprivileged UID/GID, and its environment can reach the intended Docker engine without credentials or ambient service secrets. A purpose-built harmless bounded user-service canary must establish that the selected mechanism is independent of the launching shell, its successful exit remains readable after the launching shell has returned, no restart occurs, and owned canary cleanup succeeds. Record canary evidence separately. Merely finding systemd-run installed is insufficient. If user service execution cannot satisfy this precondition, stop. Do not silently substitute nohup, setsid, a background shell, or a chat-owned exec session. An alternative explicitly bounded wait strategy may be separately reviewed and synchronized, with cancellation producing retained failed/incomplete status rather than a retry. No claim can guarantee survival of host reboot or user-manager shutdown.

Coordinator issues systemd-run --user with the above reviewed properties and exact command below. Redirect private stdout/stderr through service StandardOutput/StandardError properties to the supervision root; working directory is the clean owned source, and inherited environment is explicitly inspected/sanitized. Avoid login shells and shell-assembled command strings. Verify returned unit identity before observation or cancellation. On an explicit cancellation use owned unit stop/SIGTERM, permit the existing bounded finalizer, then inspect remaining exact project-owned resources. Never SIGKILL first or stop a unit identified only by a reused PID. Completion requires the original recorded InvocationID, MainPID=0, ActiveState=active, SubState=exited, Result=success, ExecMainCode=1 (CLD_EXITED), ExecMainStatus=0 and NRestarts=0, plus the original supervisor receipts. A merely active unit is not completion. A failed unit is retained and classified failed. Retain the exact readbacks and logs before an explicit owned stop; only then reset failed state if applicable. Do not remove completed unit state until exit/properties/log evidence is retained.

## Frozen execution command and preconditions

Use `/tmp/autodata-workshop-browser-supervisor-v2.py` SHA256 `a06bea8c6aa7b1fabdb29f3c2b8eba426d9004f2690e9c11ebc56dcb7b8f9c71`; inherited base `/tmp/autodata-r3-040-acceptance-supervisor.py` SHA256 `039a42c5287be5ed25d8b1c0b4724c1f9bad5f0e7f727a1270830a48304d28fa`. Re-read independent exact-byte wrapper review and pass its pure self-test. Manifest `docs/agents/records/2026-11-04-workshop-api21-inputs.json` SHA256 `ee87deb865c06a84df92c1a8b0481f5ebc35cfdbd051bf32d9e1bf264ec67f13` remains the canonical frozen input bytes. Preserve and bind original failed build receipt and separately passing historical engine probe without changing either status.

Runtime image is exactly `sha256:26aea6a9df1a7139e20a6893d9b63a11ab6b9978d113c718c6a792616be5a888`. Verify its availability, literal six image-input hashes, actual current engine availability and exact Playwright1.64.1/Chromium156.0.8078.4/Firefox157.0/WebKit27.2 revisions from the original plan. No dependency install, browser download, rebuild or fallback. Record current PG/NATS image IDs/digests and resolved Compose; source tags remain mutable and are not advertised as immutable.

Capacity is serial, one acceptance lane, no concurrent paid/DTO/build. Recheck disk headroom above 2GiB artifact allowance plus clone/cache/service volumes, RAM/CPU/PID availability, filesystem ownership, Docker context and existing/foreign resources. Original free-space observations are not current capacity proof. Runner limits remain 2GiB memory, 2GiB total memory+swap, 2 CPUs, 512 PIDs, applied after startup exactly as existing wrapper; retain actual ShmSize rather than borrowing historical engine-probe settings. No claims of service quotas or pre-start limits are added.

```sh
python3 /tmp/autodata-workshop-browser-supervisor-v2.py \
  --source-repo /home/corp/autodata-evidence/api21-e5fed17-source \
  --candidate-sha e5fed171bb36fdb759c592cbcd0e15aea5490c97 \
  --run-root /home/corp/autodata-evidence/api21-e5fed17-full-recovery-20261104 \
  --mode api \
  --prepare-timeout-seconds 120 --build-timeout-seconds 120 \
  --start-timeout-seconds 180 --test-timeout-seconds 2350 \
  --finalize-timeout-seconds 180 --total-timeout-seconds 3300
```

This is one newly authorized complete serial full21 execution; do not silently rerun the pilot or cases. Carry forward the completed pilot only after independent raw verification confirms exact source/wrapper/runtime identity and cleanup. If that pilot cannot be verified or current engine preconditions fail, stop and separately define the needed diagnostic; do not improvise one within this full-run dispatch.

## Completion, audit and cleanup

Observe service in bounded calls (at most60 seconds each) and report meaningful changes. Do not end active supervision merely because JUnit reaches21. Wait for the original supervisor process exit, its final receipt/inventory/host-after and unit exit observation. Read-only follow-up after a chat interruption uses recorded unit/MainPID/start identity and exact owned root; it does not launch another run.

Independent reviewer re-derives exactly21 unique full JUnit identities (3+6+6+6, Chromium/Firefox/WebKit, applicable banks), matching21 passed result directories and single passed browser receipts with exact candidate/engine/provider/assertion sets. No skip/xfail/error/fail/duplicate/missing/extra rows. Check original plan's actual HTTP/PG/S3, cookie/session, finance/access, response-loss key reuse, warm reload, server-replacement, isolation/revocation/refund assertions and raw logs. Pilot and old interrupted root supply zero rows to the new run.

Verify source/runner clean before/after and SHA, six image inputs, complete committed input manifest, migrations001..040, eleven served asset/SDK/TLS/input hashes, engine revisions, actual service image IDs, runtime limits and returned-ID ownership. Require acceptance-result status=passed/exit0 with all required checks and no failures, exact approved wrapper/base hashes, inventory digest binding, bounded regular files/no symlinks and matching immutable artifact hashes. Preserve author-run versus independent acceptance identities separately.

Verify wrapper-owned teardown and host-after observations, no exact owned project containers/volumes/network/builder/tag, and explicit cleanup errors. Remove only proven project-owned leftovers using original ownership/image/label validation; append supplemental recovery evidence in a distinct audit root if needed. Any missing original finalization evidence, failed cleanup, nonzero exit or mismatch makes the new attempt failed/incomplete; preserve it and stop. Never repair a receipt into passing or rerun automatically. Independently hash final receipts plus external supervision evidence after all writers exit; verify private evidence for secrets before sharing.

## Concrete todo for synchronized record (six items)

1. Preserve/classify old full run as interrupted/incomplete despite21/21 observed JUnit; retain supplemental cleanup hash and independent raw audit, without modifying/relabeling old root.
2. Synchronize exact recovery goal, these six todos, new roots, process supervision and zero implementation scope in Issue186/Project8/canonical docs/task/record; commit/push docs checkpoint, pin full SHA, pass exact-base preflight and independent checkpoint review; obtain bounded coordinator dispatch.
3. Revalidate exact clean source, approved wrapper/base/manifest/image/engines, completed pilot raw evidence, current service image identities, owned absent roots and serial host capacity; prove chosen user-service supervision with a harmless bounded owned canary, otherwise stop.
4. Dispatch the unchanged complete full21 command exactly once in its new root through the reviewed Restart=no user service; retain outer argv/identity/exit/log evidence separately, preserve existing deadlines/resources and remain under bounded observation through supervisor finalization.
5. Independently audit all21 raw cases, exact candidate and input/runtime provenance, supervisor final receipt/inventory/host-after, hashes/privacy and owned cleanup; retain every failure and require a separate synchronized gate for any repair or later attempt.
6. Keep final-head180/support/security/images/SDK/license/CI/reviewer proof and all staging/product/release/deployment/cutover gates separate; pilot/support add zero logical cases, historical evidence cannot certify another SHA, and all profile/authority promotion stays false.

## Result limits

A fully passing independently reviewed recovery establishes API21 fixture acceptance only at e5fed171. It supplies21 of 5+8+14+12+120+21=180 logical fixture cases. It does not attest a current PR head that has moved, final exact-head CI, DTO120 or other fixture/support suites, live Firebase/Stripe/bank licensing, production restart/PG recovery, staging/product certification, R6/profile enablement, merge, deploy, DNS or cars.tk cutover. Preserve all prior failed/incomplete receipts and separate reviewer identity; no release authority is derived.


## Exact reviewed service commands and environment

The draft's read-only observations resolve `/usr/bin/python3`, `/usr/bin/docker`, UID1000 and GID1000. Recheck these identities at dispatch; a mismatch blocks this recipe. The service's actual application process receives only the following allowlist through `/usr/bin/env -i`: PATH=/usr/local/bin:/usr/bin:/bin, HOME=/home/corp, USER=corp, LOGNAME=corp, LANG=C.UTF-8, LC_ALL=C.UTF-8, TZ=UTC. No ambient DOCKER_HOST, DOCKER_CONTEXT, proxy, cloud, provider, merchant, DSN or credential variables pass through. The wrapper's established private Docker config and explicit fixture environment remain authoritative. Independently verify that this sanitized environment reaches the intended default Docker engine/context before runtime dispatch; do not add an environment variable silently to make it work. Systemd-generated INVOCATION_ID is deliberately absent from the application environment; record and compare the unit's InvocationID property externally.

Create only the private supervision root, its separate canary/launch log files and exact argv records under the adopted zero-implementation scope. Do not create the supervisor full-run root. Commands below are proposed argv for review, not executions performed by this draft. Execute as argv arrays without a shell expansion; the quoted properties are single arguments.

One bounded harmless canary, no Docker, network or repository access:

```sh
/usr/bin/systemd-run --user \
  --unit=autodata-api21-e5fed17-recovery-canary-20261104.service \
  --property=Type=exec --property=RemainAfterExit=yes \
  --property=Restart=no --property=KillMode=control-group \
  --property=RuntimeMaxSec=20 --property=TimeoutStopSec=5 \
  --property=UMask=0077 --property=WorkingDirectory=/home/corp \
  --property=StandardOutput=append:/home/corp/autodata-evidence/api21-e5fed17-full-recovery-20261104-supervision/canary.stdout \
  --property=StandardError=append:/home/corp/autodata-evidence/api21-e5fed17-full-recovery-20261104-supervision/canary.stderr \
  /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/home/corp \
  USER=corp LOGNAME=corp LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC \
  /usr/bin/python3 -c 'import json,os,time; time.sleep(2); print(json.dumps({"canary":"api21-supervision","pid":os.getpid(),"uid":os.getuid(),"gid":os.getgid(),"environment":dict(os.environ),"exit":0}),flush=True)'
```

The launch tool call must return; subsequent distinct tool calls perform the readback. Record InvocationID while still running if possible, otherwise at first retained-state readback; reject any subsequent identity change. Observe two successful completed-state readbacks at least3 seconds apart (bounded waits, within the canary20-second watchdog) after the launching command returned. Both must show the same InvocationID, MainPID0, active/exited, ExecMainCode1, ExecMainStatus0, Result success, NRestarts0 and unchanged successful output containing exactly one canary row. Verify actual environment equals the allowlist, UID/GID1000, Restart=no and RemainAfterExit=yes. Retain logs/readbacks/hash before explicit owned stop. If any property is missing, unit disappears, a second canary invocation appears or success is not retained, fail this launch precondition; do not start acceptance or repeat the canary automatically.

Exact canary readback argv (substitute only the already recorded full unit name for the acceptance readback):

```sh
/usr/bin/systemctl --user show autodata-api21-e5fed17-recovery-canary-20261104.service --no-pager \
  --property=Id --property=InvocationID --property=MainPID \
  --property=ActiveState --property=SubState --property=Result \
  --property=ExecMainCode --property=ExecMainStatus --property=NRestarts \
  --property=Type --property=RemainAfterExit --property=Restart \
  --property=KillMode --property=RuntimeMaxUSec --property=TimeoutStopUSec \
  --property=ControlGroup --property=ExecMainStartTimestamp --property=ExecMainExitTimestamp
```

After retained successful canary evidence, issue exactly:

```sh
/usr/bin/systemctl --user stop autodata-api21-e5fed17-recovery-canary-20261104.service
```

Verify that this exact unit has no live process and no restart; record its post-stop state/absence. No reset is needed for successful state. If failed, retain failure evidence first, stop only the identity-checked owned unit, and use `systemctl --user reset-failed <that-exact-unit>` only if it still exists in failed state. Never reset unrelated units.

Actual acceptance launch argv, only after the synchronized checkpoint, independent review, bounded coordinator dispatch and successful retained canary:

```sh
/usr/bin/systemd-run --user \
  --unit=autodata-api21-e5fed17-recovery-20261104.service \
  --property=Type=exec --property=RemainAfterExit=yes \
  --property=Restart=no --property=KillMode=control-group \
  --property=RuntimeMaxSec=3500 --property=TimeoutStopSec=200 \
  --property=UMask=0077 \
  --property=WorkingDirectory=/home/corp/autodata-evidence/api21-e5fed17-source \
  --property=StandardOutput=append:/home/corp/autodata-evidence/api21-e5fed17-full-recovery-20261104-supervision/supervisor.stdout \
  --property=StandardError=append:/home/corp/autodata-evidence/api21-e5fed17-full-recovery-20261104-supervision/supervisor.stderr \
  /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/home/corp \
  USER=corp LOGNAME=corp LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC \
  /usr/bin/python3 /tmp/autodata-workshop-browser-supervisor-v2.py \
  --source-repo /home/corp/autodata-evidence/api21-e5fed17-source \
  --candidate-sha e5fed171bb36fdb759c592cbcd0e15aea5490c97 \
  --run-root /home/corp/autodata-evidence/api21-e5fed17-full-recovery-20261104 \
  --mode api \
  --prepare-timeout-seconds 120 --build-timeout-seconds 120 \
  --start-timeout-seconds 180 --test-timeout-seconds 2350 \
  --finalize-timeout-seconds 180 --total-timeout-seconds 3300
```

Immediately capture the exact unit's original InvocationID, process identity and properties using the show argv above with `autodata-api21-e5fed17-recovery-20261104.service`; save subsequent readbacks separately. Completion requires the exact retained properties stated above and immutable acceptance-result/inventory/host-after proof, not only JUnit. Hash the final unit evidence/logs after MainPID0 and original supervisor exit, then explicitly stop only that identity-verified owned unit with `/usr/bin/systemctl --user stop autodata-api21-e5fed17-recovery-20261104.service`. Preserve success/failure evidence before any stop/reset; never pass --collect and never use a restart policy. A failed launch or interrupted run remains a distinct failed/incomplete attempt.


## Repository adoption and current gate record

The preceding reviewed draft bytes are preserved verbatim as historical design input (SHA256 42dd282ae5c5a17cda7cf2e9b590ed4675ae46f55154c565691146bd2223e664). This docs-only adoption is based exactly on b1ac3c7c7786a922dcc89132b07add605d7ebae5; sole writer api21_recovery_plan. Tracking and exact committed preflight are pending. No implementation, canary or runtime dispatch is authorized.

Issue: https://github.com/lucronn/autodata/issues/186; Project: https://github.com/users/lucronn/projects/8. Task: `docs/agents/tasks/2026-11-03-production-release/workshop-api21-interruption-recovery.json`; record: `docs/agents/records/2026-11-04-workshop-api21-interruption-recovery.json`; complete tracking evidence: `docs/agents/records/2026-11-04-workshop-api21-interruption-recovery-tracking-evidence.json`.

Goal: Obtain one complete immutable full21 author-run receipt and independent raw acceptance review at application candidate e5fed171bb36fdb759c592cbcd0e15aea5490c97, preserving the interrupted original root and unchanged approved supervisor/runtime/fixtures; no implementation or release acceptance claim.

Concrete todo (identical in task/record/queue):

- [ ] Preserve/classify old full run as interrupted/incomplete despite21/21 observed JUnit; retain supplemental cleanup hash and independent raw audit, without modifying/relabeling old root.
- [ ] Synchronize exact recovery goal, these six todos, new roots, process supervision and zero implementation scope in Issue186/Project8/canonical docs/task/record; commit/push docs checkpoint, pin full SHA, pass exact-base preflight and independent checkpoint review; obtain bounded coordinator dispatch.
- [ ] Revalidate exact clean source, approved wrapper/base/manifest/image/engines, completed pilot raw evidence, current service image identities, owned absent roots and serial host capacity; prove chosen user-service supervision with a harmless bounded owned canary, otherwise stop.
- [ ] Dispatch the unchanged complete full21 command exactly once in its new root through the reviewed Restart=no user service; retain outer argv/identity/exit/log evidence separately, preserve existing deadlines/resources and remain under bounded observation through supervisor finalization.
- [ ] Independently audit all21 raw cases, exact candidate and input/runtime provenance, supervisor final receipt/inventory/host-after, hashes/privacy and owned cleanup; retain every failure and require a separate synchronized gate for any repair or later attempt.
- [ ] Keep final-head180/support/security/images/SDK/license/CI/reviewer proof and all staging/product/release/deployment/cutover gates separate; pilot/support add zero logical cases, historical evidence cannot certify another SHA, and all profile/authority promotion stays false.
