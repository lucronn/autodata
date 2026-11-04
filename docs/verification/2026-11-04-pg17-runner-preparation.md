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
