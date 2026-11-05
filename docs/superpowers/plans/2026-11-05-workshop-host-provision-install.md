# Workshop Host Provision and Install Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with superpowers:executing-plans. Use a synchronized amendment before expanding its allowlist.

**Goal:** Provide an executable staging-first path from the accepted bare GCE VM to an installed host runtime, accepted immutable image cache, and migrated initial database; reuse existing inert release install and maintenance-first activation.

**Architecture:** Three local entrypoints package trusted source, prepare the accepted staging host, and cache images/initialize its fresh database. Reuse existing validation, inert installation, private delivery and activation contracts. All cloud ingress and production promotion remain external.

**Tech Stack:** Python3 standard library, Debian12 amd64, dpkg, systemd, nftables, Docker/Compose, PostgreSQL17.

**Spec:** `docs/operations/workshop-host-provision-install.md` (normative interfaces, fixed paths, limits, mutation ordering and owner inputs).

Issue: https://github.com/lucronn/autodata/issues/307 ; parent https://github.com/lucronn/autodata/issues/186 . Project: https://github.com/users/lucronn/projects/8 . Source base: `5d14c891e8efd14a297b07e482304ea2a6b9cd7f`.

## Global constraints

- Planning checkpoint only on this turn; no implementation/cloud execution.
- Implementation allowlist is exactly the eight paths below; existing relay, Compose, runtime/activation/private-delivery files remain read-only dependencies.
- Fixed Debian12/linux-amd64 staging-only profile; pinned accepted packages/images, no latest/tag/credential fallback.
- No production, DNS, paid/provider/model traffic or resource mutation during implementation tests.
- Test each milestone before commit/push. Independent exact-candidate review precedes integration; passing this gate alone authorizes no live host command.

## File responsibilities

- `infra/deploy/gce/build_host_bundle.py`
- `infra/deploy/gce/host_provision.py`
- `infra/deploy/gce/host_prepare_release.py`
- `infra/deploy/gce/host-bootstrap-roles.sql`
- `infra/deploy/gce/test_host_provision.py`
- `infra/deploy/gce/test_host_prepare_release.py`
- `docs/operations/workshop-host-provision-install.md`
- `infra/deploy/gce/test_host_schema_pg17.py` (only the baseline PG17 fixture correction below)

## Task 1: Deterministic bundle and host preparation

Create build_host_bundle.py, host_provision.py and test_host_provision.py. The builder emits the exact source inventory described in the spec; provision exposes check/apply SOURCE_SHA and uses an injectable bounded executor only in unit tests. Production entrypoint uses fixed binaries/paths, env -i equivalent, no caller-selected executor. Keep check mutation-free.

- [ ] Write failing unittest cases for deterministic inventories, dirty/wrong source rejection, traversal/link/size/hash/type/mode rejection, wrong OS/production config, expired approval and observed-device mismatch.
- [ ] Run `python3 -m unittest discover -s infra/deploy/gce -p test_host_provision.py -v`; capture the expected missing-entrypoint failure.
- [ ] Implement bundle generation, strict approved package closure and journaled preparation stages exactly in the canonical specification; do not start Docker before mount+actual guard checks.
- [ ] Add recording-executor tests asserting command order, policy-rc.d restoration on every package failure, blank-only format, mounted-disk-only data creation, bounded timeout/reap, no boot-disk fallback, and explicit partial-failure journal refusal/recovery.
- [ ] Run focused tests and py_compile, `git diff --check`, then commit/push `feat: package and prepare accepted staging host`.

Interface produced: inventory.json and fixed installed /opt/autodata/bin helpers/templates plus successful host-prepared receipt; no selected/running release. Runtime template resolution at /opt/compose must be exercised from the installed layout, not a source checkout.

## Task 2: Accepted release and image cache

Create host_prepare_release.py and test_host_prepare_release.py. It accepts images|database SOURCE_SHA and consumes Task1 installed package/runtime outputs; spec defines exact approvals and paths. Images operation consumes existing publisher acceptance and calls existing inert installer before pulling verified immutable references.

- [ ] Write failing cases with fake Docker for rejected manifest/acceptance, unapproved digest, platform/config mismatch, absent tmpfs auth, malformed JSON, timeout and cleanup failure.
- [ ] Run focused unittest; implement existing-installer receipt validation, fixed digest-only pulls, existing image validation and always-cleaned pinned tmpfs auth. Locks must follow existing order and avoid nested lock acquisition across installer calls.
- [ ] Assert no image prune/tag substitution, no registry discovery/secret fetch, no production acceptance, no cache-success on partial failure; verify installed renderer works with all supplied static templates.
- [ ] Run Task1+Task2 tests and existing host_install/host_runtime/host_activation regressions, py_compile and diff checks; commit/push `feat: cache accepted staging release images`.

Interface produced: image-cache receipt bound to manifest and all seven roles; no services started or database schema claimed.

## Task 3: Fresh database migration and verification

Extend host_prepare_release.py/test_host_prepare_release.py and create host-bootstrap-roles.sql. Consume exact image-cache receipt, manifest and separately delivered tmpfs credentials; use existing migration entrypoint/runner and existing post-migration runtime grants/PG17 collectors. No changes to collectors or relay grants are in scope.

- [ ] Add failing fake tests rejecting nonempty foreign PGDATA, current release, running app containers, incorrect migration image, unsafe role facts, concurrent lock and unknown ledger prefix; assert applications remain absent on every branch.
- [ ] Implement fresh-only postgres startup, fixed role/bootstrap SQL, bounded one-shot migration, reviewed grants, actual catalog+ledger comparison and private-input cleanup per spec. Existing-state resume accepts only explicit owner approval of same journal and observed exact prefix.
- [ ] Add disposable real PG17 tests that apply repository001-040 via accepted runner, verify exact ledger and application/metrics/relay role privileges, reject malformed ledger, and inject failing migration retaining maintenance/no app startup. Tests use synthetic local credentials, no external providers.
- [ ] Run `python3 -m unittest discover -s infra/deploy/gce -p 'test_host*.py' -v`, syntax/diff/preflight and installed-layout tests. Execute the real PG17 cases when Docker is available; if absent, record blocked runtime evidence, never passing schema/readiness.
- [ ] Update canonical spec with actual execution/remaining owner prerequisites, commit/push `feat: initialize accepted staging database schema`, and obtain independent exact-candidate review. Separate disposable Debian12 VM/package/systemd test must pass before owner authorizes real staging host execution.

## Concrete todo

- [ ] Build a deterministic credential-free host bundle with exact file inventory and existing runtime helpers, templates and source migration material.
- [ ] Prepare the accepted staging host with exact seaweedfs1000:10000700 data path, strict helper/release modes, explicit approval fields and credential paths, offline pinned packages, UUID mount and guard dependencies.
- [ ] Install accepted inert release material and populate the exact manifest image cache with transient externally supplied registry authentication, verifying every digest/platform/config identity.
- [ ] Initialize only a fresh staging PostgreSQL17 database, provision fixed scoped roles, run the exact accepted migration image/runner and grants, and verify the manifest ledger before existing activation.
- [ ] Run reject-before-mutation, mount/guard ordering, image failure, migration/retry and reboot tests with fake execution plus disposable PG17; push coherent validated milestones and synchronize evidence.

## Verification record

The synchronized JSON record is `docs/agents/records/2026-11-05-workshop-host-provision-install.json`; task envelope `docs/agents/tasks/2026-11-03-production-release/workshop-host-provision-install.json`. Pinned checkpoint SHA and actual machine-preflight output are recorded in the subsequent receipt. No implementation or live staging evidence is claimed by this plan.

## Pre-edit contract amendment

The storage bind source is exactly `/var/lib/autodata/seaweedfs`, owner1000:1000 mode0700; service name minio does not select a minio data path. Preserve strict `/opt/autodata` and release-directory modes required by existing installers. The canonical spec now names every operation-specific approval key, first-install/resume journal field, and temporary credential path/owner/mode. Existing postgres restart behavior may resume PostgreSQL behind mount/guard dependencies; this gate creates no application containers and does not authorize application auto-activation. These are corrections to compatibility with read-only dependencies; the original live-operation boundary is unchanged; the fixture-only eighth path is added explicitly below.

### Baseline fixture prerequisite within Task3

- [ ] Preserve reported untouched baseline249 tests/4 failures/1 skip. In the eighth allowed path test_host_schema_pg17.py, create the dedicated nonprivileged autodata_outbox role and minimal publication_events eight-column table named in the canonical spec before existing runtime-grants.sql. Change no collector assertions, skips, production grants or runtime code.
- [ ] Run `AUTODATA_REQUIRE_PG17=1 python3 -m unittest discover -s infra/deploy/gce -p test_host_schema_pg17.py -v` with the cached disposable PG17 image, then rerun the full host suite. Retain actual outcomes; do not replace real cases with mocks.

- [ ] Repair only the existing real PG17 fixture by creating nonprivileged autodata_outbox and the minimal eight grant-target publication_events columns before unchanged runtime-grants.sql; preserve all collector assertions and rerun real PG17/full host tests.
