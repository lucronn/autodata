# Disposable Workshop stateful VM design

Status: synchronized after coordinator tracking readback; pending full-SHA preflight, independent exact-checkpoint review and fresh implementation dispatch; planning only.
Source: `e5fed171bb36fdb759c592cbcd0e15aea5490c97`.
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

## Decision and alternatives

Build an additive lab helper for a pre-provisioned, disposable, offline Linux VM. It installs a transactional nonsecret stateful profile, accepts generated synthetic credentials privately, boots PostgreSQL/NATS/SeaweedFS, and measures persistence across stop/start and reboot. This gives an executable local deliverable without owner GCP/Firebase/Stripe/bank/model accounts. It does not turn lab credentials, fake publisher observations or a local VM into cloud staging evidence.

Extending deploy.sh/host_install.py would couple the drill to owner-approved cloud configuration and publisher/mount acceptance. Relaxing those contracts would weaken accepted boundaries. Reusing normal developer Compose would leave host/volume/network identity ambiguous and would not rehearse VM reboot. Therefore both alternatives are rejected for this milestone. Existing production/inert-install files and guards remain byte-identical.

## Trust and environment

The trusted local coordinator supplies an already-created disposable KVM VM, a dedicated already-formatted/mounted data disk, tmpfs, reviewed Python/Docker/Compose binaries and cached image IDs. This milestone creates no VM and formats no device. A separate run authorization must bind the VM DMI product UUID, machine-id, boot ID, data UUID, hypervisor configuration digest, offline/no-NIC evidence, source/helper/profile/image/tool hashes and a fresh run UUID. A protected root approval is an operator decision, not cryptographic proof of disposability. The helper independently checks the observable identities and refuses mismatches, non-KVM hosts, physical hosts, unexpected host interfaces/default routes, unknown Docker resources and any production /etc/autodata or /opt/autodata/current object. A fake approval never establishes GCE ownership/IAM.

No VM NIC is attached during the drill; a hypervisor console is the control path. Docker has one internal bridge with fixed IPs and no published ports. No production nft/systemd file is installed, edited or reinterpreted. Existing rejected host-runtime guard behavior remains unchanged. Runtime isolation in this lab has separate evidence and cannot certify API-only GCE ADC or a cloud metadata guard.

## Lifecycle and data

The exact helper verbs are install, deliver, start, seed, check, stop and recover. A fixed local approval and SHA/run UUID identify every operation; callers cannot choose paths/commands/projects. Installation commits nonsecret helper/profile bytes atomically after all checks, and is idempotent only on exact tree equality. There is no current-release pointer and no application startup. Deliver consumes one bounded private pipe containing synthetic per-run secrets, writing service-specific tmpfs files with descriptor validation. Start runs only three stateful services, never pull/build. Seed explicitly writes a single deterministic run-bound row/object/message; check verifies without writes, including negative authentication and S3 read-only behavior. Stop preserves all data; recover requires fresh boot authorization and explicit private redelivery of the same synthetic bundle after reboot, then verifies the original fixture bytes/identities without reseeding.

The PostgreSQL fixture uses a dedicated lab database and table, not AutoData migrations. NATS has a dedicated stream/subject; S3 has a dedicated synthetic bucket/object. A Python probe container is ephemeral and has only internal-network access and a read-only tmpfs credential mount; it is not a fourth long-running service. No commerce, ownership, account/session, article or actual licensed source state is created. This drill is persistence and interruption evidence, not a backup/restore or RPO/RTO certification.

## Results and authorization

Every receipt identifies source/config/profile/images/VM/boot/run/phase and actual outcomes, with bounded static errors and no credentials/raw child logs. Distinguish material_committed, stateful_started, fixture_seeded, persistence_verified and recovery_verified; missing phases remain false. All receipts carry application_verified=false, cloud_staging_verified=false, production_ready=false, deployment_authorized=false and cutover_authorized=false. Success in one phase never authorizes another. Errors retain data and operation state; no automatic deletion or formatting. Timeout/cancellation owns and reaps child processes before completion; uncertain service shutdown produces incomplete recovery, not success.

The implementation gate authorizes only code and offline unit tests after synchronization/preflight/review/dispatch. A disposable VM execution is a separate coordinator run gate. Owner credentials and approved cloud/resource/origin/payment/provider/recovery inputs remain necessary for actual staging and production.

Detailed closed contracts, exact allowlist, tests and concrete todo: `docs/superpowers/plans/2026-11-04-workshop-stateful-vm.md`.

## Tracking receipt

Tracking synchronized through [issuecomment-6634690176](https://github.com/lucronn/autodata/issues/186#issuecomment-6634690176) and Project8 readback at `2026-11-04T15:30:13.620238+00:00`. Issue body SHA256 `927b46ef47b1dbf5b117273e3d3f5c0e6d9f23b722a5245869eb5323b96c4f25`; detail SHA256 `6a35d6ea11143901e11d7b42381ccf2b4635d87a5dbd0e84d34eb916140d0b86`; current Project Source SHA256 `46b8e75e2a62481d106c77c1b6677dd8c1f865ef53b5377c0d31950280c68a7b` (484 UTF8bytes); exact predecessor Source SHA256 `7988162779e1b526fef566c7288f0ab2a99dc7b34dd74650ce06c79673cbd2b5` is preserved verbatim in the detail and durable before/readback evidence. The coordinator inventoried137 prior comments and retained all other Project fields unchanged. Evidence: `/home/corp/autodata-evidence/stateful-vm-tracking-before.json` SHA256 `4487759f31c6d4d583f41dc3e9624b8b7b2c71f40b36a2239bdf4aa13090f310`, and `/home/corp/autodata-evidence/stateful-vm-tracking-readback.json` SHA256 `4799ed6745ba733ea145313981e1e4cb53d7890958c54edf1da552a795e1d699`. Planner verified these local evidence bindings without new GitHub operations.

Status is **synchronized**, pending committed full-SHA preflight, independent exact-checkpoint review and fresh coordinator implementation dispatch. All execution/verification/production/deployment/cutover flags remain false; VM/Docker execution still requires its separate exact-code local run gate. This tracking receipt does not certify the current rejected host-runtime guard or change any implementation blob.


### Stateful VM live-detail correction and successor gate

Independent gate review found that the initial live Issue detail retained a pending-synchronization heading and a proposal statement saying not synchronized. The coordinator corrected the **same** [issuecomment-6634690176](https://github.com/lucronn/autodata/issues/186#issuecomment-6634690176) in place; GitHub comment updated_at `2026-11-04T15:33:40Z`, retained correction readback `2026-11-04T15:33:41.700000+00:00`. The earlier detail hash `6a35d6ea11143901e11d7b42381ccf2b4635d87a5dbd0e84d34eb916140d0b86` above is historical. **Current live detail SHA256 is `b452e911af91b8e4a117dd4cca54f278d3a08f7ea16610d48316426a7c1adee8`.** Project Source SHA256 stays `46b8e75e2a62481d106c77c1b6677dd8c1f865ef53b5377c0d31950280c68a7b`; Issue body SHA256 stays `927b46ef47b1dbf5b117273e3d3f5c0e6d9f23b722a5245869eb5323b96c4f25`; all other Project fields and prior-history references remain unchanged per coordinator readback.

Correction evidence `/home/corp/autodata-evidence/stateful-vm-comment-correction-readback.json`, SHA256 `9cc1b859a663f623fbef0781a6cb737d091b0ca722b0561ff8fd4f09d23331ff`, retains before/after hashes and the actual comment identity. Original tracking snapshots remain historical evidence. Checkpoint `71c8b255078f4f2dea01bbb714cd724f81a67586` is **not builder-authorizing**. This successor docs-only checkpoint updates the current detail hash and needs fresh pinned machine preflight, independent exact-checkpoint review and coordinator dispatch. Source/goal/five todos/six-file prospective implementation scope and all protected production/inert-host/guard bytes remain unchanged. All implementation-dispatch, VM/Docker/cloud/production/deployment/cutover authority remains false.
