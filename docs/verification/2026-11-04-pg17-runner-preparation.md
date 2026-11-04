# PG17 disposable runner preparation evidence

Status: adopted preparation gate passed and coordinator dispatched Task1 preparation only. Preparation blocked at the first builder proof guard; no acquisition, container creation/start or image construction occurred. Actual PostgreSQL startup and harness execution remain unexecuted and unauthorized.

- Reviewed corrected plan: `7988c7de30e6de930d36a3b8d907cdb4e90264ba`; review receipt `79d5f089acbdcd09d490c5ca56f582da8bc24be6`.
- Adopted synchronized checkpoint: `bad940db48d649fd8d5b08d119c66defde19884c` on `codex/workshop-pg17-runner-prep`.
- Pinned machine preflight: exit0, `{"status": "synchronized", "errors": []}`; exact pinned record SHA256 `afbfd4f5a387eba2e60f32678592573a72af41a8edd51c117c93e8cd4aca7692`.
- Tracking readback: [Issue186 adoption](https://github.com/lucronn/autodata/issues/186#issuecomment-6621086102); Project8 prior index preserved verbatim in that comment.
- Immutable harness source: `54ab7dce19c36ce7ea3403259dd1ecc66bf323aa`; source archive SHA256 `4666eec4f3575fcc4f12ec6956af41fe055c740f53430e0057d7163b85096b80`.
- Five harness files byte-identical to immutable source; no implementation files changed.
- Private raw evidence: `/home/corp/autodata-evidence/pg17-runner-prep-20261104`; source archive, adoption hashes, tracking readbacks and exact preflight retained there.

| Harness path | SHA256 |
| --- | --- |
| `infra/deploy/gce/schema_probe.py` | `daa4a065058e568aa2b4199f10b75c471999906be1625c36c7a9bd78a9d137ae` |
| `infra/deploy/gce/test_schema_probe.py` | `c3570baab472635a0da1879beb4b229b3545f490e1cbd21a30f08cce23a02c10` |
| `infra/deploy/gce/test_schema_probe_pg17.py` | `08d59affa36835e2efcdc2905a03af712ee7a618ace16cd6d787535dcfcd8ceb` |
| `infra/deploy/gce/testdata/schema_probe_sentinel.c` | `a4dd46d294c25181c3fd0258cf4e17359d718539804aceaa61ea7e01b2a61fd4` |
| `infra/deploy/gce/testdata/schema_probe_fixtures.sql` | `4ba91d534ac3653148c5289d02f0de6fd0623d0941351a6ad04fe20b6d5bfcec` |

Runner image/APK/build/toolchain identities: unexecuted. Production schema/services/runtime_evidence/production_ready/deployment_authorized remain false.

## Task1 prerequisite inspection: blocked

The cached official base matches the approved image ID/repo digest and linux/amd64 platform. It declares `VOLUME /var/lib/postgresql/data`. Docker Engine is `28.5.2+dfsg4`; selected builder is `default` with `docker` driver and reports BuildKit `v0.0.0+unknown`. Available read-only builder inspection/help does not prove exact cached-local-ID resolution without registry access or bounded private inherited-PGDATA build-sandbox handling/cleanup. The fixed Dockerfile cannot be built until those route guards are demonstrated. No fallback, mutable tag, builder replacement or weakened mount assertion was attempted.

- Blocker receipt SHA256: `9a3523df5eb0c72aa25b0e913258c22fc286e4ba7049c575335613a946ef33c7` (`preparation-blocker.json` in the private evidence directory).
- Base inspect SHA256: `d4f461c04ea432fc95e8ae3cff210a053af1c9d6dc890ba484aa4c11ac352508`.
- Builder inspect SHA256: `ebe5ca29a91c02ef83ad8d5a0decca422dea203c4e3b1bb50ecc1e536a7aca36`.
- Docker build help SHA256: `411b7dd2081ffdcbc0c6d771a40dc0a07b71c18d2e72cc1ec3f09939cc90fea1`.
- APK manifest/derivative image/toolchain/sentinel artifacts: absent, because preparation stopped before acquisition.
- Exact-owned container/mount cleanup: no containers were created, so there are no owned container or volume resources to remove.

This is a prerequisite blocker, not a failed PostgreSQL/harness run or an acceptance receipt. All runtime/readiness denials remain in force.

## Read-only feasibility conclusion

The selected `docker` driver exposes builder/node/version/platform/GC metadata through `docker buildx inspect`; it does not expose a pre-execution build-step mount inventory or exact-owned build-sandbox cleanup receipt. Its reported BuildKit version is unknown. This available inspectable state is insufficient to prove the route's required private bounded handling of inherited PGDATA or that no anonymous Docker volume will be allocated. It also does not establish that literal `FROM sha256:<local-image-ID>` resolution stays in the local image store without registry access. No conclusion that BuildKit actually creates a volume is asserted; the missing proof itself blocks this plan.

A reviewed successor decision is needed before further preparation: either provide an approved, inspectable proof mechanism for this exact builder/local-ID behavior or amend the preparation route to a mechanism whose mounts and cleanup can be established before payload execution. The current dispatch does not authorize changing the fixed Dockerfile, substituting a tag/builder, attempting a diagnostic build, or treating lack of visible volumes as proof. Read-only inspection ended; no container/download/build/PostgreSQL/harness action occurred.


## PG17 inspected preparation amendment: plan-only

Goal: Replace the blocked opaque-builder PG17 preparation step with inspected exact-ID acquisition and offline-install containers plus a stopped-container commit; preserve the separate exact-image harness authorization and every production/readiness denial.

Decision-complete successor: `docs/superpowers/plans/2026-11-04-workshop-pg17-inspected-preparation.md`; dedicated task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-inspected-preparation.json`; record `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation.json`. Planning base `79ce883458c1ac41e385cabc8d1f582b0b28cab1`; exact harness54ab and historical builder blocker preserved. This supersedes only prior route Task1 Dockerfile/build handling: later approved preparation uses exact-ID `docker create --pull=never`, full pre-start mount/network/capability inspection and bounded private PGDATA tmpfs; signed official APK acquisition; offline installation in an isolated inspected container root layer; then exact stopped-container `docker commit --change` with explicit non-root configuration, ancestry/input/package/file-delta provenance and exact-owned cleanup. No BuildKit, image pull, package upgrade, tracked implementation edit, integration or current Docker execution is allowed. Original Task2 remains unchanged and separately unauthorized; image/toolchain/harness/readiness remain unverified.

Concrete todo:

- [ ] Synchronize the inspected-create/offline-install/commit amendment, exact source/base pins, mount and cleanup contracts in Issue186/Project8 and canonical docs; commit/push and pass pinned preflight for independent plan review.
- [ ] After separate coordinator approval, create and inspect the exact cached-base acquisition container with bounded private PGDATA tmpfs, signed official APK-only networking and one private output mount; freeze the signed dependency closure and clean only its exact owned resources.
- [ ] Create and inspect a network-disabled offline installer with read-only frozen inputs, private PGDATA tmpfs and an isolated writable root layer; reject package upgrades, untrusted signatures, unexpected mounts or file changes before committing its stopped state.
- [ ] Commit only the reviewed exited-zero installer ID with explicit non-root image configuration and provenance labels; inspect exact base-layer ancestry, configuration, package/toolchain/source hashes and cleanup, then request independent frozen-image review.
- [ ] Keep actual PostgreSQL startup and harness Task2 unexecuted and unauthorized until separate exact-image/source dispatch; preserve all blocker/failure receipts and production runtime/grants/services/deployment/readiness denials.

Inspected-preparation amendment synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621173398 and Project8 readback at `2026-11-04T02:48:06.281627+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned inspected-preparation amendment checkpoint: `2cf545157ed299b8424bbebe1b01ce9c85ab3a3c`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621179539. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


Inspected PG17 preparation ICU review correction (plan-only): the fixed Python inspection script now parses pg_config --configure with `shlex.split(..., comments=False, posix=True)`, requires exactly one `--with-icu` argument and rejects `--without-icu`. A pure local fixture executes only that exact extracted AST fragment: quoted/unquoted ICU and quoted spaces pass; missing/disabled/contradictory/duplicate/substring/empty/malformed quoting reject (10 passed,0 failed). The prior whitespace split fails the quoted positive fixture. Receipt `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation-icu-fixture.json` records inputs/results/fragment hash. No container, toolchain, download or harness execution is implied; independent corrected-checkpoint review/new preparation dispatch remain pending and original Task2 stays separately unauthorized.

Narrow ICU correction synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621225616 and Project8 readback at `2026-11-04T02:51:55.028338+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned ICU-corrected inspected-preparation checkpoint: `6d65a512172f28a9f7f0960ecf41409db78455c2`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation-icu-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621229238. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.

## Inspected preparation attempt 01: acquisition blocked

Corrected gate `6d65a512172f28a9f7f0960ecf41409db78455c2` (receipt `7d993c6930792dbbc539deae5621b3139a1baed0`) passed pinned preflight and received independent coordinator Task1-only dispatch. Fresh private evidence: `/home/corp/autodata-evidence/pg17-inspected-prep-20261104-01`, owner1000:1000 mode0700; RUN_ID `inspected-20261104-01`. Earlier blocker evidence remains intact.

Exact local-base creation with `--pull=never` passed complete created-state inspection: two approved binds, three bounded tmpfs including inherited PGDATA override, read-only root, user0:0, only DAC_OVERRIDE capability, bridge network, approved security/resource configuration and no unexpected mounts or allocated volumes. The unchanged fixed script emitted x86_64/apk-tools3.0.8-r0, baseline package inventory and signing-key hashes. `apk update` then failed with `ERROR: Unable to open log: Read-only file system`. Attach and independent stopped-state exit were99; OOMKilled=false, State.Error empty. APK directory remained empty. No simulation, install, image commit, compilation, PostgreSQL startup or harness execution followed. No fallback flags/mounts/caps were attempted.

- Owned container: `5ea0276a7dbc38de2f3bbea2dfcb14605dd128fba13c486071316d933a910bdc`.
- Blocker receipt SHA256: `d276215bad457113ff5fddf554d5e2154f4a3e067001babc270e664265019d00` (`evidence/task1a-blocker.json` in the private directory).
- Fixed acquire script SHA256: `323d24180ae395abbfeb495a70678428336f8902cb00cf25e5d92654f321bdb7`.
- Before-start inspect SHA256: `8b04c1ae7c7a87118209ba1ab1a6d87380f50e6e1ca7412b232891fda6de3ad4`.
- Attach stdout SHA256: `8af31dc9a5b085b1c523524fda391d6c7f71bd57f5ae3603a0bfdfe27aad41dc`.
- Attach stderr SHA256: `08af54a80425402b9f810ead614587aee02dbe2f095f5c491fcb2f1ab68585fc`.
- Stopped inspect SHA256: `2c1908604051105ba68eb49847d142782c45589c7346c43c63f1a47375d8b406`.

Exact container removal with `docker rm --volumes` succeeded; its ID absence is verified. Complete volume inventories match after normalizing row/label order; no owned container/volume resources remain. Preparation is blocked pending a reviewed read-only acquisition/log-write correction. No frozen runner artifact exists. All raw failure/cleanup evidence is preserved and all Task2/runtime/production/readiness denials remain in force.


## PG17 APK default-log correction: plan-only

Goal: Permit only an independently reviewed PG17 preparation retry with an explicit bounded private APK log tmpfs and pre-start guard, preserving the actual exit99 blocker, exact-owned cleanup, offline provenance and separate harness authority.

Correction plan `docs/superpowers/plans/2026-11-04-workshop-pg17-apk-log.md`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-apk-log.json`; record `docs/agents/records/2026-11-04-workshop-pg17-apk-log.json`. Preserved red: approved Task1A under6d65a5 exited99 at apk update with read-only log error,0 APKs; exact-owned container removed and volume inventory unchanged (base65772079). Read-only cached libapk3.0.8 identifies default `/var/log/apk.log`. Later approved APK acquisition/simulation/install creates add only private `/var/log` tmpfs4MiB (`rw,noexec,nosuid,nodev,uid=0,gid=0,mode=0700`) and exact pre-start guard; acquisition root stays read-only, no capability/command/repository/host-volume expansion, logs cannot enter committed added layer. Original full mount/cleanup/provenance/Task2 boundaries remain. Guard fixtures are synthetic/pure and not retry evidence. Independent review/new coordinator Task1A dispatch pending; this planner creates/starts/downloads/retries nothing.

Concrete todo:

- [ ] Synchronize the exact APK log-path diagnosis, retained red proof, bounded tmpfs guard and unchanged preparation/harness limits in Issue186/Project8 and canonical docs; commit/push and pass pinned preflight for independent review.
- [ ] After independent corrected-checkpoint review and a new coordinator Task1A dispatch only, create a fresh exact-base acquisition container with the additional private4MiB /var/log tmpfs and validate the complete original mount contract plus exact new log guard before start.
- [ ] Execute only the unchanged approved signed-APK acquisition payload after its inspected log guard passes; preserve the previous exit99 and every new failure, bounded attach/log metadata and exact-owned stop/removal/volume-absence evidence.
- [ ] Require the same private log tmpfs and guard for later approved offline simulation/install containers, with no log bytes entering the committed added layer; preserve no-upgrade/signature/package/file/layer/configuration and frozen-image review requirements.
- [ ] Keep image/toolchain/sentinel/harness outcomes unverified until actually observed under their separate approved steps; preserve original Task2 authority and every production/runtime/grant/service/deployment/readiness denial.

APK-log correction synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621303386 and Project8 readback at `2026-11-04T02:57:35.939965+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.


APK-log correction adoption: independently approved checkpoint `bd59558a78a11448f89e35ef34f910bbb64cedbe` (receipt `9db69a7758228fb8997b7c1ca5f5d90c1cc7c32f`) adopted at `cc0945fb841459c68b7a6e4ced8dcb802640b979`, directly after retained failed evidence `6577207980f24e61c51ab0fcc8198ded18c0d1a4`. Five harness54ab files and raw blocker receipt remain unchanged. Live Issue186/Project8 synchronization https://github.com/lucronn/autodata/issues/186#issuecomment-6621339347 read back 2026-11-04T03:00:29.931234+00:00; exact hashes in dedicated APK-log record and predecessor Project index preserved verbatim in comment. Adoption only: no Docker/create/start/download/retry; full adopted-SHA preflight and root verification/new Task1A dispatch still required. Original Task2 and all runtime/production/readiness outcomes remain unauthorized/unverified.


Pinned APK-log adoption receipt: checkpoint `00aa840e84428a7205314299b4be97c7dd2267d0`, exact record SHA256 `6d830033cc4bc91a3f4870790776f3e5ea06762bbb245e19f37175973a562f51`; machine preflight exit0, `{"status": "synchronized", "errors": []}`. Exact record bytes checked against Git at that full SHA. Raw pinned receipt and tracking readbacks: `/home/corp/autodata-evidence/pg17-log-adoption-20261104`. Prior source/blocker hashes preserved; retry/create/start/download remain unexecuted pending root verification and new Task1A dispatch.

## APK-log retry attempt 01: database lock blocked

Coordinator verified adopted log correction gate `00aa840e84428a7205314299b4be97c7dd2267d0` and dispatched only a fresh Task1A acquisition retry. Private directory `/home/corp/autodata-evidence/pg17-apk-log-prep-20261104-01` was newly created owner1000:1000 mode0700; RUN_ID `apk-log-20261104-01`. Earlier failed evidence was not reused or altered.

Created container `c3ee9e673c030fc6bf2c47bb8f3932d9f397d089bb77b3aa9dac0440ca056961` from exact cached base with `--pull=never`. Full before-start image/config/network/capability/mount validation and the exact approved log guard passed: two approved binds, four bounded tmpfs including PGDATA and private4MiB `/var/log`, read-only root, unchanged capabilities and payload. The unchanged fixed acquisition script SHA256 remains `323d24180ae395abbfeb495a70678428336f8902cb00cf25e5d92654f321bdb7`. `apk update` exited99 with `Unable to lock database: Read-only file system` and `Failed to open apk database: Read-only file system`. No APK files were fetched.

- Blocker receipt SHA256: `76b0b24692aa3e62a317437cd87451a23d63ca296accfbe2f6de78aa6689b18f` (`evidence/task1a-blocker.json` in the private directory).
- Before-start inspect SHA256: `0aa3f5883caa8e68b38bb2ff246d7aab3511bfb089512b9ca291baf8099c2db6`.
- Attach stdout/stderr:3229/112 bytes, streamed4096-byte chunks with1MiB cap per stream; no overflow or timeout. SHA256 `8af31dc9a5b085b1c523524fda391d6c7f71bd57f5ae3603a0bfdfe27aad41dc` / `3f97af8a9d79eec50e6291b7ea859fbcfd97160b3701badf1f61797b966780f4`.
- Independent stopped state: exit99, OOMKilled=false, State.Error empty. Exact `docker rm --volumes` succeeded and ID absence verified. Complete volume inventories match after normalizing row/label order; no owned container/volume resources remain.

Task1A is blocked; no simulation/install/image commit/compilation/PostgreSQL/harness action occurred. No flags, mounts, commands or capabilities were changed after failure. Raw failure and cleanup receipts are preserved; a reviewed successor correction is required before retry. All production/runtime/Task2/readiness denials remain in force.


## PG17 acquisition-only writable overlay successor: plan-only

Goal: Replace only the blocked read-only PG17 APK acquisition root with a disposable inspected writable overlay, require stopped overlay/baseline audits before accepting APK output, and preserve offline installation, separate harness authority and every production/readiness denial.

Successor plan `docs/superpowers/plans/2026-11-04-workshop-pg17-acquisition-overlay.md`; dedicated task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-acquisition-overlay.json`; record `docs/agents/records/2026-11-04-workshop-pg17-acquisition-overlay.json`. Base226cb50f preserves both actual Task1A exit99/0APK/cleanup attempts. Only acquisition drops `--read-only` and requires explicit isolated writable root overlay; exact image, unchanged signed APK payload/official bridge scope/caps/resources/two binds/four private tmpfs remain. Require stopped complete docker diff with lock/baseline-only allowlist and unchanged package/keys/repos/PG hashes before any APK output acceptance; acquisition overlay/container is never committed, restarted, reused or passed to offline stages. Exact-owned cleanup/absence/volume inventory mandatory. Offline simulation/install/final-image/Task2 authority unchanged; independent exact-gate review/new Task1A dispatch required. No planning container/download/retry/image/harness action.

Concrete todo:

- [ ] Synchronize both preserved exit99 attempts, acquisition-only overlay decision, exact create/audit/cleanup contracts and unchanged offline/harness limits in Issue186/Project8 and canonical docs; commit/push and pass pinned preflight for independent review.
- [ ] After independent exact-checkpoint review and fresh coordinator Task1A dispatch only, create a new exact-base acquisition container with one disposable writable root overlay and unchanged private mounts/caps/network/commands; inspect its full created configuration and record baseline file hashes before start.
- [ ] Run only the unchanged signed official APK acquisition payload under the existing bounded supervisor; require zero exit, unchanged baseline package/key/repository/PG data and an exact stopped docker diff audit before freezing any APK output.
- [ ] Never commit, restart or reuse acquisition containers; retain every failure/audit/cleanup receipt, remove only the captured exact-owned ID/volumes and verify absence/unchanged volume inventory before downstream use.
- [ ] Keep offline simulation/install/commit configuration and original Task2 separately authorized and unchanged; no image/toolchain/harness/runtime/production readiness follows from plan synchronization or synthetic guard fixtures.

Acquisition-overlay successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621400986 and Project8 readback at `2026-11-04T03:04:46.045770+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.


Acquisition-overlay adoption: approved checkpoint `26989e1de7a71ac4f7c23da043dd367548e2ba45` (receipt `80d4a20dcd7603a81d1ef96307e94fafe32caafe`) adopted at `1fe22c943143d8955624ed75c0f378bdb2dc0439`, directly after actual second failed evidence `226cb50fabfbc53c9f674dd72fae9b42aa3775d0`. Five harness54ab files and both raw exit99 receipts unchanged. Issue186/Project8 live readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621449880 at 2026-11-04T03:08:28.641173+00:00; exact hashes in dedicated overlay record and full predecessor Project index preserved verbatim in comment. This is adoption only: no Docker/create/start/download/retry/install/image commit; adopted full-SHA preflight and root verification/new Task1A dispatch required. Offline stages/Task2 remain separately unauthorized; runtime/production/readiness unverified.


Pinned overlay-adoption receipt: full checkpoint `7f0201cc2b26cc8fbcd0637386f5cf047320c970`, exact record SHA256 `8a38bfbfabb9252f3a81dd2fd42252454090d454342d4b17c85c33012e7a61d6`; machine preflight exit0, `{"status": "synchronized", "errors": []}`. Record bytes checked against Git at the pinned SHA. Raw tracking/preflight receipts: `/home/corp/autodata-evidence/pg17-overlay-adoption-20261104`. No retry/Docker/download action; root verification/new Task1A dispatch required, offline and Task2 separately held.

## Acquisition overlay attempt 01: stopped diff guard blocked

Coordinator verified adopted overlay gate `7f0201cc2b26cc8fbcd0637386f5cf047320c970` and dispatched a fresh Task1A-only acquisition. Private directory `/home/corp/autodata-evidence/pg17-overlay-prep-20261104-01`, owner1000:1000 mode0700; RUN_ID `overlay-20261104-01`. Exact owned container `102eb97013e3b69e567b0179b59dc14416a167748bbd81200d5c9fabb30d1f17` passed complete before-start image/config/mount/capability/network/overlay validation. Twenty-seven baseline file/directory records from the created root matched the saved pinned base image, including APK DB/world, trust repositories/keys and fixed PG tools/headers.

The unchanged fixed payload exited0, with bounded attached output. Signed official repository update and all33 downloaded APK signature checks succeeded. Host APK SHA256 values match fixed-payload output. Stopped exit0 was independently confirmed, OOMKilled=false and State.Error empty. All27 baseline records remained unchanged. The complete stopped diff was exactly:

```text
A /apks
A /control
```

The exact approved diff guard rejects these added bind-target directories. No ad hoc filtering/normalization/allowlist exception was applied;33 APKs remain quarantined failure evidence, not an accepted dependency closure and never eligible for downstream reuse under this attempt. No simulation/install/image commit/compilation/PostgreSQL/harness action occurred.

- Attached stdout/stderr:8898/0 bytes;4096-byte reads,1MiB cap each, no overflow/timeout.
- Blocker receipt SHA256: `36ea1490633250d79fddf2f5c1f7b92abe19f043e8ab4544dc1519f3afd9ee52` (`evidence/task1a-blocker.json`).
- Quarantined APK manifest SHA256: `bc44b2eb0cede2db890e8b09ffbdf673bb3ef0e98c1ffd94a9c9e0a9c7ef8c55`.
- Complete stopped diff SHA256: `f644241d7c563ce99a81d3cf0ba36af3582bc221b19054fc1f509fea8cad221d`.
- Stopped audit SHA256: `17c03aab7df37281f535e5e2f32d0d28c7afc88191a169087a3ec8589f2d7754`.
- Before-start inspect SHA256: `0d655fcb331127f737bf9c7223e6fcb88dc139acbe60f39ae1f2ec99a86d2470`.
- Attach stdout/stderr SHA256: `e3fefb66656dac54d848ba5b734f508f6402e1e6772dd7d242bd3e523d4cb398` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Exact `docker rm --volumes` succeeded and captured ID absence was verified. Complete normalized before/after volume inventories match; no owned container/volume resources remain. Raw snapshots/argv/inspection/signature/hash/diff/failure/cleanup receipts are retained privately. Preparation is blocked pending a reviewed guard correction; all production/runtime/Task2/readiness denials remain in force.


## PG17 empty bind-target diff successor: plan only

Permit only proven Docker-created empty acquisition bind-target directories in the stopped overlay diff, retain every other audit and cleanup constraint, and keep all quarantined APKs unusable.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-bind-targets.md`; record `docs/agents/records/2026-11-04-workshop-pg17-bind-targets.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-bind-targets.json`. Retained e1ca208 attempt exited0/signatures33 but failed strict diff on A /apks and A /control;33 APKs remain quarantined and never reusable. Only exact added empty root-owned directories may pass after absent saved-base targets, exact prestart binds and bounded created/stopped underlying filesystem export audits. Files/children/other paths/missing proof reject. All original constraints, offline/Task2 authority and cleanup unchanged. No planning Docker/download/retry/harness; independent exact-gate review/new dispatch pending.

Concrete todo:

- [ ] Synchronize exact red receipt, bounded structural audit and context-bound diff guard in Issue186/Project8/canonical docs; push exact gate and pinned preflight for independent review.
- [ ] After independent exact-gate review/adoption and fresh coordinator Task1A dispatch only, create a fresh acquisition container and collect full prestart bind inventory plus bounded underlying filesystem structural audit before start.
- [ ] Require exact empty directory metadata before/after, absent saved-base targets, unchanged 27 baseline records and original complete stopped diff/signature/exit audits; reject files, descendants, aliases, deletions and missing proof.
- [ ] Retain prior 33 quarantined APKs as failed evidence, never accept/reuse them; any future fresh output requires all audits and exact-owned removal/absence/volume proof.
- [ ] Keep acquisition commands/network/caps/mounts and offline simulation/install/image/Task2 authorities unchanged; no planning Docker/download/retry/harness action or readiness claim.

Bind-target successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621533357 and Project8 readback at `2026-11-04T03:13:58.668948+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned bind-target successor checkpoint: `016ea37722f36fa0c8b2b509884e75bef6ac41b2`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-bind-targets-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621541625. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed bind-target gate adoption and mandatory operation ordering

Adopted source gate `016ea37722f36fa0c8b2b509884e75bef6ac41b2`, receipt `c7d57a3347621c5559d5a671997142da1a1f43dc`; exact reviewed plan SHA256 `40e0591c8742a37983cf289d565c9df7d4e263c7caa5cc4e8e7f38b3b36f49ed`. Coordinator relayed independent approval of this exact plan. Adoption branch `codex/workshop-pg17-bind-target-adoption`; dedicated record `docs/agents/records/2026-11-04-workshop-pg17-bind-target-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-bind-target-adoption.json`. This adoption performs no Docker operation or retry and conveys no production/harness readiness.

**Mandatory future order (resolves the created-state mountpoint feasibility condition):** (1) create exact-owned fresh acquisition container under the unchanged approved argv, validate full created inspect/config/bind inventory and pinned base archive; (2) complete **all inherited prestart `docker cp` baseline snapshots** and the unchanged27-record saved-base comparison while still created/never-started; these existing copy operations materialize the bind-target directories; (3) only **after those copies finish successfully**, perform the first bounded created-state underlying filesystem export and full prestart diff, requiring the exact empty root-owned `/apks` and `/control` directories plus `A /apks` and `A /control`; (4) only after every inherited and new prestart guard passes may the coordinator-dispatched payload start; (5) after stopped exit0, perform the bounded stopped export/full diff/unchanged-baseline audits, then exact-owned cleanup and output acceptance boundary. Never run the first export/diff before the inherited copies or start merely to materialize targets. Failed copies, missing/changed/nonempty targets or any ambiguity fail closed and clean the exact owned attempt. No extra container command, mount or authority is added.

All prior export bounds/source semantics checks, acquisition payload/image/network/caps/resources/mounts, signature verification, quarantine, baseline/row/type/empty checks and cleanup remain mandatory. This ordering clarification does not accept or reuse the historical33 quarantined APKs. Offline simulation/install/image review and original Task2 remain separately authorized and unchanged. No deployment, integration, production grant/runtime action or readiness follows.

Concrete adoption todo:

- [ ] Record independent approval of exact gate016ea377 and reviewed plan SHA256, synchronize adoption Issue186/Project8/canonical docs, then push and pin passing full-SHA preflight.
- [ ] Only after new coordinator dispatch, validate exact created acquisition ID/config/bind inventory; complete every inherited prestart docker cp baseline snapshot and unchanged27-record comparison BEFORE first created-state export/diff.
- [ ] Then require bounded created-state underlying empty-directory export and exact A /apks,A /control diff; only after all guards pass may the fixed acquisition payload start.
- [ ] Require matching stopped structural export, complete original baseline/diff/signature/exit audits and exact-owned cleanup/absence/volume proof before accepting any newly acquired APK closure.
- [ ] Never accept/reuse historical33 quarantined APKs; no Docker/download/install/harness on adoption turn; offline stages/Task2 and all production/readiness denials unchanged.

Reviewed bind-target adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621594414 and Project8 readback at `2026-11-04T03:18:09.877892+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.

Pinned reviewed bind-target adoption checkpoint: `76fd86e5a356ae611d643e621f9ae03660d50206`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-bind-target-adoption-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621597936. Reviewed source plan approved; fresh coordinator preparation dispatch required. No container/image/package/harness action or readiness claim.


## PG17 complete mount-record ordering successor: plan only

Correct only order-sensitive acquisition Mounts inspection comparison using complete records keyed by unique exact Destination, retaining all raw/canonical hashes, red receipts and unchanged acquisition guards.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-mount-order.md`; record `docs/agents/records/2026-11-04-workshop-pg17-mount-order.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-mount-order.json`. Base da1f42a; actual fresh acquisition attempt stopped before startup on inspect Mounts array order only,0 APKs, exact-owned cleanup/absence and unchanged volume inventory. Preserve red result/diagnosis exact hashes in dedicated evidence. Replace only top-level Mounts array order-sensitive equality with complete-record canonical JSON by unique exact Destination; duplicates/missing/extra paths or any field drift reject. All original config/structural/baseline/signature/diff/payload/cleanup and offline/Task2 limits unchanged. Live tracking synchronized; independent exact-checkpoint review/root dispatch remain pending. No retry authority. No planning Docker/retry/download/harness.

Concrete todo:

- [ ] Synchronize the narrow mount-order plan, exact red receipts and complete-record fixtures with Issue186/Project8/canonical docs only after coordinator releases tracking slot; commit/push and pin passing full-SHA preflight for independent review.
- [ ] Require independent exact-checkpoint review/adoption and fresh coordinator Task1A dispatch before any new Docker operation; use a new private run and never restart/reuse prior failed containers or APKs.
- [ ] Retain raw before/after inspect bytes and SHA256; canonicalize only top-level Mounts array record order by unique exact Destination, require exactly /apks and /control and preserve every complete record field/value.
- [ ] Require original complete config/mount predicates plus canonical equality at every acquisition Mounts comparison; duplicate/missing/extra destinations, field/type/value drift, invalid JSON or ambiguous input fail closed.
- [ ] Keep all predecessor created-copy/export/diff ordering, structural/exit/signature/baseline/resource/network/payload/cleanup bounds and offline/Task2 separation unchanged; no planning Docker/retry/download/harness or readiness claim.

Mount-order successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621665171 and Project8 readback at `2026-11-04T03:23:07.931845+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned mount-order successor checkpoint: `cdbedc871104484d931113ce74c84be0b8ba449e`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-mount-order-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621669759. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed complete mount-record ordering adoption: plan only

Adopt independently approved source gate `cdbedc871104484d931113ce74c84be0b8ba449e`, receipt `1e43e64a9b1b8237bbc9656aa311d0c7d13d5698`; exact reviewed plan SHA256 `8eb158a7101959b23a096487366692b6f8990c73e6ad4b79c303eb4cae5a302b`. Source review evidence `/tmp/autodata-pg17-mount-order-cdbedc87-review.json` retained as `docs/agents/records/2026-11-04-workshop-pg17-mount-order-adoption-review.json` with original hash. Adoption branch `codex/workshop-pg17-mount-order-adoption`; dedicated record `docs/agents/records/2026-11-04-workshop-pg17-mount-order-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-mount-order-adoption.json`. Live tracking synchronized after coordinator slot release. Root must verify the full adopted-SHA preflight and issue fresh Task1A dispatch before any runtime action.

The sole correction is top-level Mounts array comparison by complete records keyed/sorted by unique exact Destination. Retain every record field and raw before/after inspect hashes plus canonical hash; missing/extra/duplicate destinations, field additions/removals/type/value drift or malformed/duplicate-key JSON fail closed. All original config predicates and HostConfig equality remain. No extra Docker command, mount, capability, source, network or retry authority. All inherited created-copy27-baseline-before-export/diff ordering, exact empty underlying-target proof, bounded exports, full stopped diff/context/baseline/signature/exit audits and exact-owned removal/absence/volume inventory remain mandatory.

The prior created-state attempt remains failed with0 APKs; result SHA256 `6db4e39f3b01adb90b42985b44a6949b6670774fc8fc9e0f84ab7be96c4f5c4d`, diagnosis SHA256 `5654ed1637e63f2facb6ee2b52a8589fb685e7996bac0e44498b130db2376695`. Missing structural metadata is not inferred retroactively. Historical33APKs remain quarantined and never reusable. Root must verify full adopted-SHA preflight and separately dispatch any new Task1A. No adoption Docker/create/start/export/retry/download/install/image commit/PG startup/harness action; offline stages/Task2 and production/provider/cloud/runtime authority unchanged. All readiness remains false.

Concrete adoption todo:

- [ ] After coordinator tracking-slot release, synchronize exact independent approval/plan hash and unchanged Task1A scope in Issue186/Project8/canonical docs, preserve CURRENT prior Project index verbatim/hash, commit/push and pin full-SHA preflight.
- [ ] Only after root verifies adopted pinned preflight and dispatches fresh Task1A, use a new exact-owned private run; compare complete Mounts records by unique exact Destination, retaining raw before/after/canonical hashes and rejecting any missing/extra/duplicate destination or field drift.
- [ ] Keep all inherited complete config checks, mandatory prestart cp27 baseline comparison BEFORE created export/diff, bounded created/stopped empty-target proof, full stopped diff/signature/exit audits and exact-owned cleanup/absence/volume inventory unchanged.
- [ ] Preserve all prior failed/quarantined outputs and red receipts; never reuse historical33APKs or restart/reuse failed containers; no offline simulation/install/image commit/PG startup/harness on this adoption turn.
- [ ] Keep Task2/production/provider/cloud/runtime actions separately unauthorized and all readiness unverified; adoption alone is not a fresh retry dispatch.

Reviewed mount-order adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621749496 and Project8 readback at `2026-11-04T03:28:59.162164+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.

Pinned reviewed mount-order adoption checkpoint: `3c96b04df9ff4b7929ca8955a92d89eef6cc7617`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-mount-order-adoption-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621754534. Reviewed source plan approved; fresh coordinator preparation dispatch required. No container/image/package/harness action or readiness claim.


## PG17 acquisition diagnostics and structured volume receipts: plan only

Correct only acquisition diagnostic false positives and volume inventory serialization by anchored status checks and bounded structured complete-volume inspection, retaining all existing guards and failed-output quarantine.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-acquisition-receipts.md`; record `docs/agents/records/2026-11-04-workshop-pg17-acquisition-receipts.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-acquisition-receipts.json`. Retained second-attempt result/diagnosis hashes and full offline replay in `docs/agents/records/2026-11-04-workshop-pg17-acquisition-receipts-evidence.json`. Attempt exited0 and passed structural/context/baseline guards, then failed host substring/Labels CSV order checks; all33 fresh APKs quarantined NEVER reusable, prior33 also never reusable. Correct only anchored status/empty-stderr diagnostics and bounded read-only complete structured volume inspect metadata by unique Name; every field/value retained, only JSON key order ignored. Explicit new metadata-read authority requires reviewed/adopted gate/root dispatch. All other Task1A/Task2 constraints unchanged; no planning Docker/retry/download/harness.

Concrete todo:

- [ ] Replay the revised fixed pure predicates against complete retained second-attempt evidence and all existing positive/negative fixtures; synchronize goal/plan/todo/red evidence/structured inventory authority with Issue186/Project8/canonical docs after coordinator slot release; commit/push and pin full-SHA preflight.
- [ ] Require independent exact-gate review/adoption and root verification/fresh Task1A dispatch before any Docker/retry; use a new private exact-owned run, never historical quarantined APKs or failed containers.
- [ ] Use unchanged bounded fixed acquisition payload and source/signature/index/hash checks; classify only empty stderr plus successful supervised attach/stopped status and reject anchored diagnostic forms, preserving full raw output and hashes.
- [ ] Before create and after exact-owned removal, capture bounded volume ls names and one bounded read-only structured volume inspect per exact name; compare complete objects by unique Name preserving every field/value and ignoring JSON object key order only.
- [ ] Keep mandatory27 prestart copies BEFORE first created export/diff, complete Mounts canonical guard, empty underlying target audits, full stopped diff/context/baseline/exit checks and owned cleanup unchanged; no offline/install/image/PG/harness/production readiness follows.

Acquisition-receipts successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621817348 and Project8 readback at `2026-11-04T03:33:51.920926+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned acquisition-receipts successor checkpoint: `4bc40e26ca12521be8f20282b897f5af68d0195e`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-acquisition-receipts-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621820832. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## PG17 diagnostic Unicode Cc review correction: plan only

Correct only the blocked acquisition diagnostic character filter to reject Unicode Cc controls except LF/tab; preserve all existing receipt guards, quarantine and runtime denials.

Corrected plan `docs/superpowers/plans/2026-11-04-workshop-pg17-control-filter.md`; record `docs/agents/records/2026-11-04-workshop-pg17-control-filter.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-control-filter.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-control-filter-evidence.json`. Prior4bc40e26 remains independently BLOCKED for DEL/C1 acceptance. Only diagnostic unicodedata import/Cc predicate changed, LF/tab sole control exceptions; complete83-case offline replay plus65 Cc probes pass (148total/0fail). All structured-volume and predecessor constraints unchanged; both33APK sets quarantined NEVER reusable. Independent exact-corrected-checkpoint re-review/adoption/root dispatch required; no planning Docker/retry/download/harness.

Concrete todo:

- [ ] Preserve exact blocked gate/plan hash and reproduced DEL/C1 negatives; update only diagnostic Cc filter/import, rerun complete83-case pure/replay suite plus65 Cc probes, then synchronize Issue186/Project8/canonical docs after coordinator tracking-slot release.
- [ ] Commit/push docs-only corrected checkpoint, pin passing full-SHA preflight and exact tracking readback while preserving CURRENT Python SIGTERM and PG predecessor index verbatim/hash.
- [ ] Require independent exact-corrected-checkpoint re-review/adoption, root verification and fresh Task1A dispatch before any Docker/retry/download/harness; previous blocked gate grants no adoption authority.
- [ ] Keep structured complete volume metadata collection/comparison and every original source/payload/config/mount/copy/export/diff/baseline/signature/cleanup bound unchanged; both33APK sets remain quarantined NEVER reusable.
- [ ] Retain all red receipts as failed and offline replay as predicate evidence only; no retrospective acceptance, offline install/image commit/PG startup/harness/production action or readiness claim.

Unicode Cc corrected successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621857074 and Project8 readback at `2026-11-04T03:36:44.664156+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned Unicode Cc corrected successor checkpoint: `b96a68e59a370314a207e67b98d67a9949584432`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-control-filter-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621859742. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed Cc-safe acquisition receipt adoption

Adopt independently approved corrected gate `b96a68e59a370314a207e67b98d67a9949584432`, receipt `eee037dd1857cec1d0817b1b3421c7280c9284f6`; exact reviewed control-filter plan SHA256 `ad2a433f532e1b7b8000588d126d9789392f6e593a5c460681b900bff403420e`. Approval was relayed directly by coordinator after independent re-review. Historical predecessor4bc40e26 remains a blocked superseded checkpoint; this adoption consumes only the corrected approved chain. Adoption branch `codex/workshop-pg17-receipts-adoption`; record `docs/agents/records/2026-11-04-workshop-pg17-receipts-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-receipts-adoption.json`.

The fixed classifier requires empty stderr and zero successful supervised/stopped status, rejects anchored diagnostic forms, and rejects every UnicodeCc character except LF/tab. All original source-output/index/key/signature/package/hash checks remain mandatory. Structured volume metadata uses bounded read-only ls names plus one complete inspect object per exactName: <=32names,60s total inventory,10s each inspect,512KiBstdout/64KiBstderr each,16MiB totalstdout/2MiBstderr. Exact same Name set; compare COMPLETE objects including all fields/values and null/map distinctions, ignore only JSON object key order; duplicate/missing/extra names/fields or any drift fail. Raw/hash/canonical receipts are mandatory. No CSV Labels substitution or four-field projection.

Full predecessor chain retained: exact cached image/payload/repositories; no source/secret bind; private inherited PGDATA override plus original tmpfs/binds; original network/caps/security/resources/output/deadline bounds; complete config and uniqueDestination Mounts records; ALL27 inherited prestart cp snapshots+unchanged comparison BEFORE first created export/diff; bounded created/stopped underlying empty target proof; complete stopped diff/context/baseline/signature/exit audits; exact-owned stop/rm--volumes/absence/structured inventory proof. No acquisition commit/restart/reuse; no arbitrary retry/guard change. Offline simulation/install/image review and original Task2 remain separately authorized and unchanged.

Both historical33APK sets (overlay first and bound-target second payload attempts) remain quarantined, unaccepted and NEVER reusable. Red result/diagnosis and missing prior structured proof are not rewritten. Pure148-case/replay success is predicate evidence only. Root must independently verify full adopted-SHA preflight and issue a FRESH Task1A dispatch before any new Docker operation. This docs-only adoption performs no Docker/create/start/export/retry/download/install/image/PG/harness/implementation or production action; no readiness follows.

Concrete adoption todo:

- [ ] Synchronize exact corrected independent approval/plan hash and full Task1A guard chain in Issue186/Project8/canonical docs while preserving CURRENT prior Project index/detail verbatim/hash; commit/push and pin full-SHA passing preflight.
- [ ] Require root independent adopted-gate verification and FRESH Task1A dispatch before any Docker/retry; use a new private exact-owned run and never historical failed containers/APKs.
- [ ] Use the fixed anchored diagnostic/status classifier rejecting all UnicodeCc except LF/tab, empty stderr and successful supervised/stopped status; retain complete raw outputs/hashes and all original source/index/signature/hash checks.
- [ ] Collect complete structured volume inspect objects for exact boundedls names before create/after owned removal:32names/60s inventory/10s perinspect/512KiBstdout64KiBstderr perinspect/16MiB totalstdout2MiBstderr; compare complete objects by uniqueName, all fields/values preserved and only JSON key order ignored.
- [ ] Keep all inherited image/payload/network/caps/resources/private mount guards,27 prestart copies BEFORE first export/diff, complete Mounts comparison, bounded empty underlying target exports, full stopped diff/context/baseline/exit and owned cleanup/absence checks; both33APK sets remain quarantined NEVER reusable.
- [ ] No adoption Docker/retry/download/install/image commit/PG startup/harness/implementation/integration/production/provider/cloud action; offline stages/Task2 separate and all readiness remains unverified.

Reviewed Cc-safe acquisition receipt adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621879747 and Project8 readback at `2026-11-04T03:38:22.919883+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.

Pinned reviewed Cc-safe acquisition receipt adoption checkpoint: `691f187302440509c23da99f4fb9e1adb9cd52a4`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-receipts-adoption-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621883014. Reviewed source plan approved; fresh coordinator preparation dispatch required. No container/image/package/harness action or readiness claim.


## PG17 independently approved frozen closure: docs-only index

Record independent acceptance of the exact Task1A frozen signed33APK closure as input only, preserve acquisition/cleanup evidence and keep Task1B/image/Task2 unauthorized pending a new gate/review/root dispatch.

Acceptance plan `docs/superpowers/plans/2026-11-04-workshop-pg17-closure-acceptance.md`; record `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-closure-acceptance.json`; exact evidence index `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance-evidence.json`. Executed691f187 result SHA19002cbf07ce2879e277e1a3e7bc1d69ac28ae8e919e29a85bc4d7a415ee3d43; frozen33APK manifest SHAcfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238. Independent audit approval saved at `/tmp/autodata-pg17-task1a-closure-review.md`, SHA256 `bb0173a6f7a46f52fd7a4c3bfbcfcf00d2db5714f179abfe1124675a69616b5b`, and relayed directly by coordinator; all174receipt refs/33host hashes verified, exact cleanup/absence/four-volume equality passed. Accepted as frozen input only; raw pending-review status remains immutable. NEW Task1B gate/review/root dispatch required; offline simulation/install/image/Task2 remain unauthorized/unexecuted, both prior33APK quarantines NEVER reusable. JS deadline slot released; frozen-input acceptance index synchronized. No Docker/install/harness.

Concrete todo:

- [ ] After JS deadline coordinator releases Issue186/Project8 slot, synchronize exact reviewed closure/result/manifest/hash acceptance in Issue186/Project8 and canonical docs, preserving CURRENT full index/detail verbatim/hash; commit/push and pin docs-only full-SHA preflight.
- [ ] Keep raw Task1A receipts and accepted-apk-manifest bytes immutable; use this adjacent acceptance index to record independent review without rewriting the original pending-review manifest status or either failed/quarantined attempt.
- [ ] Accept only exact33APK filenames/versions/architectures/hashes in the pinned manifest as future input; verify all host hashes again before any later authorized consumer and reject mutation or substitution.
- [ ] Require a NEW decision-complete synchronized Task1B gate, independent review, root verification and fresh dispatch before offline simulation/install/image commit or toolchain inspection; no execution authority follows from closure acceptance.
- [ ] Keep original Task2 PG startup/harness separately unauthorized, all runtime/production/grants/services/deployment readiness unverified, and both historical33APK sets quarantined NEVER reusable.

Frozen-input closure acceptance synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621963547 and Project8 readback at `2026-11-04T03:44:34.583302+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Input closure independent approval recorded; NEW Task1B synchronized gate/review/root dispatch required; no Docker/install/image/PG/harness actions.

Pinned frozen-input closure acceptance index checkpoint: `04093a5e176499e7d8de18e9573f9fea3abe9d3a`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621970383. Frozen input independently accepted only; NEW Task1B gate/review/root dispatch required. No container/image/package/harness action or readiness claim.


## PG17 Task1B offline simulation-only successor

Gate one bounded offline Task1B simulation of the immutable independently accepted33APK closure using exact20 new-package inputs, unchanged baseline and complete cleanup; installation/image/Task2 remain separately unauthorized.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-task1b-simulation.md`; record `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-task1b-simulation.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-evidence.json`. Independent feasibility report SHA256e82b42d46639d0149b7cf644cb0bbdd29f86bb020cf5410fcdfcea007779ab88. Accepted33APK manifest SHAcfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238 remains immutable; exact20 add operands/all33 verification, created/stopped empty bind targets, exact inherited0600zero lock, deterministic Cc-safe parser/unchanged45+27 baseline, pinned BusyBox trigger.58 metadata dependencies (36base/22new) and 95 pure parser fixtures are NOT solver success. Docs only; simulation denied until independent review/adoption/root verification/fresh dispatch. Installation/image/Task2/production remain unauthorized/unverified, both prior33APK quarantines NEVER reusable.

Concrete todo:

- [ ] Synchronize this docs-only simulation successor in Issue186/Project8/canonical notes, preserving CURRENT full prior index/detail verbatim and SHA256; commit/push and pin full-SHA passing preflight.
- [ ] Obtain independent review of this exact simulation-only checkpoint; require coordinator adoption/root verification and fresh one-attempt dispatch before any Docker command.
- [ ] On authorized fresh simulation only, reverify all33 immutable APK hashes/signatures, use exact20 literal apk-add paths, inspect complete offline resources/mounts and mandatory prestart27 copies before created export/diff.
- [ ] Require deterministic bounded parser with exactly20 additions and no baseline actions, complete unchanged27/package45/world/keys/PG/scripts/trigger/lock state and created/stopped empty bind-target proof; fail closed/quarantine/no retry.
- [ ] After exact-owned removal/absence/complete-volume equality, independently review simulation receipts; a NEW installation gate must pin same20 APK argv and audit BusyBox-trigger effects. No installation/image commit/PG/harness/readiness is authorized now.

Task1B simulation-only successor synchronized by exact live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6622084338 and Project8 readback at `2026-11-04T03:53:46.055147+00:00`; full prior closure index/detail preserved verbatim/hash in comment and dedicated record. Independent exact-checkpoint review/adoption/root verification/fresh dispatch required; no Docker/retry/install/image/harness operation or solver success.

Pinned Task1B simulation-only successor gate: `808225f5fa14ca0c7dc308a5d39cd65396c694f7`; full-SHA preflight `status: synchronized`, `errors: []`, exit0; receipt `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-preflight.json`; exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622095482. Independent review/adoption/root verification/fresh dispatch required before simulation. No Docker/solver/install/image/PG/harness or readiness claim.

Pinned Task1B simulation-only successor gate: `dafbdea85477437e8cf20969b3c6571aa59c2c50`; full-SHA preflight `status: synchronized`, `errors: []`, exit0; receipt `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-corrected-preflight.json`; exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622103154. Independent review/adoption/root verification/fresh dispatch required before simulation. No Docker/solver/install/image/PG/harness or readiness claim.


## PG17 Task1B CapAdd-only ordering successor: plan only

Correct only full HostConfig.CapAdd array order comparison while preserving exact three approved unique capabilities and all other simulation guards; gate ONE fresh offline Task1B simulation after exact review/adoption/root dispatch.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-cap-order.md`; record `docs/agents/records/2026-11-04-workshop-pg17-cap-order.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-cap-order.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-cap-order-evidence.json`. Failed resultSHAf870e36f11b4eea70478f0932ea446aa904631bcda8f89b28e65dbbc6bea8224/diagnosisSHA067a4cb3284da093479301eada2519a7944a07c36839e9262a2e241f8218e37d: never started, exact cleanup/absence/all33 inputs/full4volumes unchanged; independent diagnosis/cleanup acceptance ONLY. Only HostConfig.CapAdd order may normalize after proving exact3unique approved strings; all other complete comparisons/95+148 guards unchanged. 123 new pure cases pass incl6 permutations and negative field/type/duplication drift. NEW empty PREP/container and exact review/adoption/root preflight/fresh ONE-attempt dispatch required. No planning Docker/simulation/install/image/PG/harness; all readiness false, both prior33APK quarantines NEVER reusable.

Concrete todo:

- [ ] Synchronize this docs-only CapAdd successor with Issue186/Project8/canonical notes and preserve CURRENT complete prior index/detail verbatim plus SHA256; commit/push then pin full-SHA passing preflight.
- [ ] Obtain independent exact-checkpoint review, coordinator adoption/root full-SHA preflight and fresh ONE-attempt simulation-only dispatch before Docker; use NEW empty private PREP, unique name/cidfile and newly created exact-owned container.
- [ ] Compare only HostConfig.CapAdd order-insensitively with exactly three unique strings CAP_CHOWN/CAP_FOWNER/CAP_DAC_OVERRIDE; retain all complete raw objects/hashes and reject any missing/extra/duplicate/type or non-CapAdd field drift.
- [ ] Retain and rerun all95 simulation parser plus148 predecessor fixtures and the new six-permutation/negative suite; preserve immutable failed-run result/diagnosis and all accepted/quarantined APK boundaries.
- [ ] On separately dispatched simulation, retain unchanged exact script/hash,33 verification/20 selection, offline caps/resources, created-copy-before-export/diff, stopped baseline/lock/trigger/mount/diff, cleanup/absence/full-volume proofs; any discrepancy stops with no retry, installation/image/PG/harness unauthorized.

CapAdd-only successor synchronized by exact live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6622201950 and Project8 readback at `2026-11-04T04:02:37.852702+00:00`; full CURRENT JS index/detail/pin retained verbatim/hash in comment and record. Independent exact-checkpoint review/adoption/root preflight/fresh dispatch required; no Docker/simulation/install/image/PG/harness and no retrospective acceptance.

Pinned CapAdd-only successor checkpoint `cde9652c0e3dce9a9083540d15cb25b3682f144d`; full-SHA preflight `status: synchronized`, `errors: []`, exit0; receipt `docs/agents/records/2026-11-04-workshop-pg17-cap-order-preflight.json`; exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622210398. Independent exact review/adoption/root preflight/fresh ONE-attempt dispatch still required. Historical run blocked; no Docker/simulation/install/image/harness or readiness authority.


## PG17 explicit offline APK/OOM lifecycle successor: LOCAL DRAFT ONLY

Propose one fresh offline Task1B simulation with explicit no-network/empty-repository APK argv and only source-proven created-false to stopped-null OomKillDisable lifecycle comparison; preserve all stderr/signature/state/cleanup guards.

Draft plan `docs/superpowers/plans/2026-11-04-workshop-pg17-offline.md`; record `docs/agents/records/2026-11-04-workshop-pg17-offline.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-offline.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-offline-evidence.json`. Failed resultc1f6af1f/diagnosis0660472e remain immutable FAILED; cleanup accepted only. Exact3.0.8 global no-network+empty repositories file on all5 invocations; original repositories cmp/keys/signatures and empty stderr unchanged. ExactEngine GitCommit source plus retained raw supports ONLY OomKillDisable false-created/null-stopped on pinned unsupported cgroupv2 context; CapAdd rule/other full fields unchanged. 107 new+366prior pure checks passed; no runtime. LOCAL UNSYNCHRONIZED pending draft review and later coordinator tracking slot; no Docker/retry/install/image/PG/harness or readiness.

Concrete todo:

- [ ] Keep this draft LOCAL/UNSYNCHRONIZED pending independent draft review; do not mutate Issue186/Project8 while publisher owns tracking and do not run Docker/retry/install/image/PG/harness.
- [ ] Independently review exact new script/argv/zero-byte override/source proof and phase-bound OomKillDisable predicate plus all pure negative fixtures; preserve failed result/diagnosis as failed, no retrospective acceptance.
- [ ] Only after coordinator authorizes tracking: preserve full CURRENT Project index/detail verbatim/hash, synchronize Issue186/Project8/canonical docs/task, commit/push a new gate and pin full-SHA passing preflight.
- [ ] Only after independent exact synchronized-gate review/adoption/root verification/fresh dispatch: one NEW empty PREP/container, exact33 verification/20 selected simulation, every apk invocation explicitly offline with pinned empty override, unchanged original repositories/keys, empty stderr.
- [ ] Require created/stopped empty bind target/export/diff/27+45 baseline/lock/BusyBox/Config/Mounts/CapAdd/cleanup/volume proofs; normalize only exact false-created to null-stopped on exact unsupported engine context; any other discrepancy stops/no retry. Installation/image/Task2 remain unauthorized.
