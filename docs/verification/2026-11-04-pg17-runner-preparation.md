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
