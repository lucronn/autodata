# Workshop migration build argument correction implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans after independent exact-plan approval, passing pinned preflight and coordinator implementation dispatch. This checkpoint is planning only.

**Goal:** Correct only the disconnected publisher migration build argv to pass POSTGRES_IMAGE from the reviewed immutable manifest postgres reference before --file; preserve other-role argv, fake-only execution and every authority/readiness denial.

**Architecture:** Amend one role-specific argument in the existing injected executor sequence. The migration image's base is the exact already validated manifest.images.postgres.reference; the executor never discovers or defaults that value. Every producer, binding, transport, host-check and CLI/workflow boundary stays intact.

**Tech Stack:** Existing Python standard-library B orchestrator and unittest fake transports; no dependency or image build.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-publisher-transport.md` (only migration argv amended here); `docs/agents/pre-implementation-gate.md` is normative for authorization.

Source base: `30cab10e548a3e078055b08447253ea90cc36bdc`. Known draft PR: https://github.com/lucronn/autodata/pull/189 . Issue: https://github.com/lucronn/autodata/issues/186 . Project: https://github.com/users/lucronn/projects/8 . Task: `docs/agents/tasks/2026-11-03-production-release/workshop-migration-build-arg.json`. Record: `docs/agents/records/2026-11-03-workshop-migration-build-arg.json`.

Status: synchronized after live Issue186 comment6621206696 and matching Project8 readback. Independent review, committed full-SHA preflight and coordinator dispatch remain required. This new record does not reuse the old publisher or PG17 record as permission.

## Verified defect and exact scope

At source30cab10, migration.Dockerfile:3 declares ARG POSTGRES_IMAGE without a default; line4 uses FROM ${POSTGRES_IMAGE}; lines5–7 additionally demand an immutable digest and PostgreSQL17 client. cloud-ops.py:799–802 supplies only SOURCE_DATE_EPOCH, including for migration. Original approved publisher plan:204–211 froze that same incomplete vector, and its exact-argv test faithfully preserved it. A real migration build would therefore fail before package verification. No real build was attempted to establish this source-level dependency defect.

Future implementation may modify only cloud-ops.py, test_cloud_ops.py and docs/operations/workshop-gcp.md. No Dockerfile, manifest schema, runtime-check, grants, workflow, Compose, application or PG17/R6 path belongs to the correction. Coordinator planning scope is this new plan/task/record, queue and five canonical repository documents (existing publisher plan, hosting plan, runbook, architecture, orchestration plan): nine documentation paths total. Existing publisher candidate30cab10, gate ddce00b, preserved failed milestone e9f082b and corrected fixture8e49e5c remain history; do not rewrite them.

## Exact corrected migration vector

Only role=migration inserts these two string elements, immediately before --file:

```python
['--build-arg', 'POSTGRES_IMAGE=' + manifest['images']['postgres']['reference']]
```

The complete migration argv is:

```python
['/usr/bin/docker','buildx','build','--platform','linux/amd64',
 '--provenance=mode=max','--sbom=true','--push',
 '--build-arg','SOURCE_DATE_EPOCH='+str(execution_policy['source_epoch']),
 '--build-arg','POSTGRES_IMAGE='+manifest['images']['postgres']['reference'],
 '--file','infra/deploy/gce/migration.Dockerfile',
 '--tag',config['resources']['artifact_repository']+'/migration:source-'+manifest['source_sha'],
 '--metadata-file','/work/workshop-release/migration-build.json','.']
```

The request remains name=build_migration,cwd=/work/workshop-release/source,timeout_seconds1800,max_output_bytes65536 and the existing exact minimal env. API and ingestion retain their full original argv with only SOURCE_DATE_EPOCH and no POSTGRES_IMAGE argument. Source checkout, ordering, registry digest/config checks, SBOM/evidence operations, artifact/readback fields, budgets, partial-failure handling and separate host request stay unchanged. No generic build-argument map, extra caller field, optional dependency argument, environment alias, tag fallback or executable override is introduced.

rt.validate_manifest still runs before every callback. Its existing image.reference pattern requires a nonempty digest-qualified reference. Read only the manifest postgres reference, never an operator environment, Dockerfile default, local Docker cache or implicit postgres:17 tag. Preserve the existing config/manifest digest bindings; no new field or default is needed. The validated digest reference is an expected base identity, not evidence of actual PostgreSQL17 contents. The existing Dockerfile version check remains a future real-build check; fake tests cannot certify PG17/pgvector ABI or runtime behavior.

## Concrete todo

- [ ] Synchronize this exact migration-only build-argument correction, three-path future scope and five todos in Issue186/Project8 and canonical documents, preserving the full prior Project index verbatim/hash; commit/push and pass pinned preflight before independent plan review and coordinator dispatch.
- [ ] Add failing exact fake-executor argv tests proving only build_migration receives --build-arg POSTGRES_IMAGE=<manifest.images.postgres.reference> immediately before --file while api/ingestion retain their existing complete argv.
- [ ] Implement the migration-only argument in cloud-ops.py from the already validated immutable manifest; reject missing/tag-only/malformed postgres references before callbacks and ignore all ambient/default POSTGRES_IMAGE or caller build-argument overrides.
- [ ] Run fake digest-propagation, no-fallback and unchanged publisher/host regressions, document that no Docker build or PostgreSQL17 runtime compatibility is proved, and retain every red/green/failure receipt outside the checkout.
- [ ] Run focused B/A suites, syntax, diff/scope and pinned preflight; commit/push a coherent three-path candidate for independent exact-SHA review without integrating, activating workflows, accessing credentials or running any real build/cloud/provider/host operation.

## Task1: red exact-vector and no-fallback tests

Files: `infra/deploy/gce/test_cloud_ops.py`. Use existing PublisherV2Tests fixtures/orchestrate fake and subprocess/socket guards. Tests exercise the public orchestrate_publication result and emitted executor request, never a real Docker command.

- [ ] Update the existing complete-vector expectation for migration only, retaining API/ingestion vectors byte-for-byte. Add a failing migration-specific assertion that the pair immediately preceding --file is --build-arg and POSTGRES_IMAGE=<fixture postgres digest>. Assert exactly one such argument exists and none occurs for API/ingestion. Expect the original candidate to fail on missing POSTGRES_IMAGE.
- [ ] Add an independent digest-propagation test: change only the reviewed manifest postgres reference terminal digest to a distinct64hex digest; regenerate the fixture archive/envelope/wrapper/binding from that manifest; keep fake observed/post-upload values consistent. Assert the resulting build_migration argument contains the new reference verbatim and original digest is absent from that command. Preserve input manifest/config validity, not a patched validator.
- [ ] Add ambient-no-fallback cases with os.environ POSTGRES_IMAGE set to postgres:17, another digest and shell metacharacters. The accepted request still uses only the manifest reference and returns simulated consistency. Changing ambient values cannot change any emitted vector.
- [ ] Add invalid reference cases: remove postgres.reference; empty string; postgres:17; postgres:latest; digest with uppercase/nonhex/63hex; unknown caller execution_policy build_args or POSTGRES_IMAGE key. With a forbidden dependency callback, assert fixed ContractError invalid publisher input and zero callbacks. This proves fallback cannot hide missing reviewed input.
- [ ] Run red and retain stdout plus hashes outside checkout:

```text
python -m unittest discover -s infra/deploy/gce -p test_cloud_ops.py -v
```

## Task2: minimal role-specific code correction

Files: cloud-ops.py and its tests. Public interfaces and expected simulated result shapes do not change.

- [ ] After the tests fail for the missing argument, construct the fixed existing build argv in its local variable, add only the migration pair before --file, then call the existing execute function. A minimal permissible implementation pattern is:

```python
base_args = ['--build-arg', 'SOURCE_DATE_EPOCH=' + str(execution_policy['source_epoch'])]
if role == 'migration':
    base_args += ['--build-arg', 'POSTGRES_IMAGE=' + manifest['images']['postgres']['reference']]
# Concatenate between the existing --push and --file elements only.
```

- [ ] Run the same focused suite green; confirm all existing source/digest/provenance/upload/readback/host/CLI/workflow denial tests pass. No real build, registry probe or credentials are required/permitted.

## Task3: document, verify and independently review

Files: runbook plus previous two paths only.

- [ ] Explain the fixed migration base argument, unchanged other roles, expected-versus-observed base identity and fake-only evidence. Do not claim an actual migration image, PG17 compatibility, authenticated publication or deployment.
- [ ] Run checks with fail-fast shell; retain all failed attempts and do not rewrite published history:

```text
python -m unittest discover -s infra/deploy/gce -p test_cloud_ops.py -v
python -m unittest discover -s infra/deploy/gce -p test_host_runtime.py -v
python -m py_compile infra/deploy/gce/cloud-ops.py infra/deploy/gce/test_cloud_ops.py
git diff --check
git diff --name-only <approved-implementation-base> HEAD
python scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-03-workshop-migration-build-arg.json --base-sha <full-committed-planning-checkpoint-sha>
```

- [ ] Commit/push the validated coherent correction to the assigned feature branch, report exact candidate SHA for independent review against the approved planning SHA, and do not integrate. No builder dispatch follows merely from synchronized tracking.

## Planning and authority boundary

Synchronize exact goal/five todos/scope/amended vector in Issue186 and Project8 after the coordinator grants the tracking turn. Preserve the full prior Project index verbatim with SHA256 in the issue comment. Read back issue body/comment/project text and store references/hashes in this dedicated record; update canonical docs/task/queue consistently. Commit/push nine-doc checkpoint, pin its full SHA and pass machine preflight, then obtain independent exact-plan approval and separate coordinator dispatch before changing implementation.

All code execution remains injected fake interfaces. CLI/workflow missing_dependency, simulation:true, provenance_authenticated:false, deployment_authorized:false, schema/services/runtime_evidence:false remain unchanged. No Docker build/push/pull, registry, credential, provider, cloud, IAP/host, DNS or paid operation is authorized. Actual GitHub outer ZIP compatibility, protected-environment/WIF identity, workflow head/source distinction, tool/image/dependency pins, production host/schema/service/no-work readiness and paid/browser acceptance remain later gates. The current correction cannot close any of them.


Migration-only correction tracking: [Issue186 comment6621206696](https://github.com/lucronn/autodata/issues/186#issuecomment-6621206696), Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference`, verified `2026-11-04T02:50:39.563760+00:00`. The dedicated correction record stores exact body/comment/index hashes; the comment preserves the prior index verbatim/hash. This is plan-only synchronization; committed pinned preflight, independent exact-plan review and coordinator dispatch still precede implementation. No code or live execution is authorized by this checkpoint alone.
