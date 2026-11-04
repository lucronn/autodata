# Workshop disconnected publisher and host-check implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after a passing pinned gate and independent coordinator dispatch. This checkpoint authorizes planning only; do not dispatch implementation from a draft record.

**Goal:** Implement concrete disconnected publisher orchestration for fixed checkout, three image builds/pushes, SBOM/provenance verification and release artifact upload through injected executor/transports, plus a bounded fixed IAP host check; preserve all live execution and readiness denials.

**Architecture:** Extend the existing B module with a deterministic two-member producer and typed fake-interface protocol. Validate a separately approved v2 publication binding, fixed fake observations and simulated provenance reports before requesting one fixed host check. No real executable, HTTP client, token discovery or workflow activation is introduced.

**Tech Stack:** Python standard library, existing strict v1 runtime manifest/config validators and ZIP32 verifier, unittest and inline adversarial fixtures.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-hosting.md`, especially the historical B archive-reader/future-publication gate; `docs/agents/pre-implementation-gate.md` is normative for authorization.

Source integration: `eddcf724028683dbb083191e4f8c42064b866bf0`. Issue: https://github.com/lucronn/autodata/issues/186 . Project: https://github.com/users/lucronn/projects/8 . Dedicated task: `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-transport.json`. Dedicated record: `docs/agents/records/2026-11-03-workshop-publisher-transport.json`.

Status: **synchronized** after live Issue186 comment6621071257 and matching Project8 readback. Committed pinned preflight and independent checkpoint review remain required. Existing catalog-only A, historical B ZIP and disconnected PG17 authority remain separate. The current historical B `future_publication_gate` stays unverified.

## Scope and non-goals

Future implementation may modify only:

- `infra/deploy/gce/cloud-ops.py`: pure producer, strict DTO validators, fake transport orchestration and fixed host-check request.
- `infra/deploy/gce/test_cloud_ops.py`: synthetic producer, fake transport/provenance/host adversarial tests.
- `docs/operations/workshop-gcp.md`: executable boundary, digest meanings, remaining live evidence.

The coordinator's planning checkpoint modifies the dedicated plan/task/record plus hosting plan, runbook, architecture, orchestration plan and `docs/agents/tasks/2026-11-03-production-release/queue.json`. These are planning documents only. No workflow, `runtime-check.py`, `deploy.sh`, schema, Compose, grants, application, SQL or PG17 harness edit belongs to this gate.

Every existing CLI operation remains exit3/missing_dependency for valid inputs; every malformed CLI input remains exit2. Workflows remain contents:read definitions with their unconditional missing_dependency steps. Fake-interface budget enforcement checks requests/results and fake-clock ordering; it cannot establish real subprocess/network cancellation. No production receipt is introduced. The normative concrete orchestrator section below supersedes narrower observational wording in this draft.

This milestone runs **no actual artifact or image publication** and authenticates no live token/signature. It implements concrete checkout/build/push/evidence/upload sequencing through injected fake executor/transports; a later authenticated adapter supplies those exact operations. Only real adapter installation, actual download-envelope decoding, signature verification and live execution remain separate. The code must orchestrate production publication behavior, not merely compare caller-supplied transcript claims.

## Freeze before dispatch

Use reviewed v1 manifest/config validation unchanged, exact source SHA, linux/amd64, migration inventory/runner hashes, seven image roles and existing dependency pins. Config is passed explicitly and must hash to manifest.service_config_sha256. Secret values never enter these interfaces; numeric secret-version references remain manifest-bound. Rollback manifest is independently supplied when required by v1.

No unresolved owner identity is invented. Synthetic tests use clearly fake numeric repository/owner IDs, example provider project number, account and VM names. An actual run needs owner-selected host/Firebase/backup projects, project numbers, costs/region, protected environments, WIF trust, principals, reviewed toolchain/actions and authorized staging evidence.

All DTOs below are exact objects: missing/unknown keys, duplicate JSON keys and bool/int/float substitutions fail. Numeric IDs are strings matching `[1-9][0-9]{0,19}`, hashes lowercase64 hex, SHAs lowercase40 hex, digest strings `sha256:` plus64 hex. Canonical JSON uses existing rt.canonical_bytes/strict_json. Limits: JSON1MiB (`rt.MAX_JSON_BYTES`), archive8MiB, receipt64KiB, max7 images. Do not silently change the existing ZIP subset or raw-JSON fake API.

## Exact public Python interfaces

```python
def produce_release_archive(manifest: dict, config: dict, images: dict, *,
                            rollback_manifest: dict | None = None) -> tuple[bytes, dict]: ...

def evaluate_publication_v2(manifest: dict, config: dict, binding: dict,
                            trust: dict, fake_transport, *,
                            rollback_manifest: dict | None = None) -> dict: ...

def evaluate_host_check(manifest: dict, config: dict, binding: dict,
                        trust: dict, publication: dict, fake_transport) -> dict: ...
```

No default transport, executable path, output path, clock, token, local config lookup, subprocess, socket or HTTP import is added. Dependency loading uses the existing fixed sibling runtime helper. Return bytes only from producer; no temporary archive/extraction filesystem operation.

### Producer and digest envelope

`images` is exactly manifest.images with each role containing the four existing image fields plus platform=manifest.platform. Validate manifest/config/rollback first, then require canonical type-strict image equality.

Encode release.json=canonical_bytes(manifest), images.json=canonical_bytes(images). Produce deterministic ZIP32 stored entries in exactly that order, date1980-01-01 00:00:00, creator OS0, version10, flags0, method0, no extras/comments/descriptors, internal/external attributes0, CRC32 and identical central/local size/name/time metadata. Implement explicit struct packing using the existing imported struct/binascii; avoid zipfile's platform/version-dependent metadata. EOCD has two entries, disk0, comment0; no prefix/gaps/trailer. Max raw member size1MiB and total archive8MiB. Repeated identical input produces identical bytes. The producer can satisfy the existing verifier without importing an external ZIP library.

Producer envelope exact fields:

```json
{"protocol_version":2,"source_sha":"<40hex>","service_config_sha256":"<64hex>","archive_sha256":"<64hex>","archive_bytes":1,"member_sha256":{"release.json":"<64hex>","images.json":"<64hex>"},"member_bytes":{"release.json":1,"images.json":1},"manifest_sha256":"<64hex>"}
```

Every byte count is an actual integer in its bound. Hash original ZIP bytes, each raw JSON member and canonical manifest separately. Since producer uses canonical release bytes its raw release hash happens to equal canonical manifest hash; verifier must still require both fields and reject rebinding/type drift. Generated envelope describes output, **not independent approval**. An independently supplied binding must authorize the resulting digests before consumption. Producer returns no authenticated/provenance/deploy result.

### Trust and publication binding v2

`trust` exact fields: `repository`, `repository_id`, `repository_owner_id`, `environment`, `ref`, `workflow_ref`, `oidc_issuer`, `oidc_audience`, `wif_provider`, `publish_service_account`, `deploy_service_account`, `builder_id`.

The first six fields use existing validate_identity semantics for publish; environment is staging|production. Require repository=lucronn/autodata, ref=refs/heads/master, workflow_ref=lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master. Existing validate_identity is called on an explicit six-field projection, not the larger object. `oidc_issuer` is exactly https://token.actions.githubusercontent.com, audience exactly https://iam.googleapis.com/ + wif_provider, provider matches the current workflow's projects/NUM/locations/global/workloadIdentityPools/POOL/providers/PROVIDER syntax. Both service accounts match the current workflow SA syntax and differ. builder_id equals `https://github.com/lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master`. Audience is the chosen protocol expectation, not evidence of a configured Google provider.

`binding` is exact producer-envelope fields plus `published_run_id`, `artifact_id`, `artifact_name`, `artifact_digest`. artifact_name is workshop-release-SHA; artifact_digest independently hashes the original GitHub transport ZIP, which wraps exactly one inner release.zip; it is not required to equal inner archive_sha256. Add artifact_bytes (actual integer1..16777216) to binding. archive_bytes remains the inner archive count. Artifact IDs/run IDs are independent approved inputs; producer must not manufacture them. This is protocol_version2 and a new function; the existing evaluate_published_release raw-JSON binding is untouched.

### Fixed fake transport request/response protocol

All callback requests exact `{name, method, url, argv, body, timeout_seconds, max_output_bytes}`; body is bytes or None. For logical operations without a documented live transport, url=None/method=None/argv=[] explicitly denotes a disconnected interface. No fake logical name is advertised as a real GitHub API endpoint. Request order is fixed below; first failure stops, and no host request occurs in evaluate_publication_v2.

1. `run`: GET https://api.github.com/repos/lucronn/autodata/actions/runs/RUN; argv=[],body=None,30s,64KiB.
2. `artifact`: GET https://api.github.com/repos/lucronn/autodata/actions/artifacts/ID; same bounds.
3. `archive`: GET https://api.github.com/repos/lucronn/autodata/actions/artifacts/ID/zip; argv=[],body=None,300s,16MiB. Response exact {transport_archive:bytes,release_archive:bytes}; independently hash original transport bytes against artifact_digest/artifact_bytes, then inner bytes against archive_sha256/archive_bytes. This fake transport boundary does not implement actual redirect/authentication/outer ZIP decoding.
4. `images`: logical read-only registry observation, method/url=None,argv=[],body=None,300s,64KiB.
5. `provenance`: logical detached verification report, method/url=None,argv=[],body=None,300s,64KiB.

Metadata responses are strict dicts with canonical bytes bounded before validation; archive response contains actual byte fields within16MiB transport/8MiB inner bounds. A callback exception or oversized output stops evaluation with a fixed redacted receipt; never include callback result/exception text. Timeouts reported by callback map to timed_out; these tests do not prove actual I/O deadlines.

`run` exact fields: id, repository, repository_id, repository_owner_id, source_sha, workflow_ref, event, status, conclusion. IDs/source/workflow match trust and binding; event=workflow_dispatch,status=completed,conclusion=success.

`artifact` exact fields: id, run_id, name, expired, digest, bytes. IDs/name match binding; expired is actual False; digest=artifact_digest; bytes=artifact_bytes. Hash original transport bytes against artifact_digest/artifact_bytes and inner bytes against archive_sha256/archive_bytes before invoking existing verify_release_archive with binding.member_sha256; validate canonical manifest/images through the unchanged verifier. Unknown/mutable/ref-selected artifact lookup is unavailable.

`images` response exactly the seven images described above, unchanged image ID, digest references, platform, provenance_uri and sbom_uri. It is an observation assertion only, never an authenticated registry attestation.

`provenance` exact `{protocol_version:2, simulation:true, identity, subjects}`. identity exact trust fields except service accounts/wif_provider; add signer_workflow_ref=trust.workflow_ref and source_sha=manifest.source_sha. Compare all expected identity fields/type-strictly. This fake report is never a verified signature. subjects exact three owned image roles (api,ingestion,migration); each exact `{image_digest, image_id, source_sha, service_config_sha256, platform, provenance_uri, sbom_uri, signature_valid, sbom_digest_valid}`. image_digest is the reference's terminal sha256 digest, image_id/URIs/platform match manifest, source/config hashes match approved inputs, signature_valid and sbom_digest_valid are actual True. These booleans exercise rejection logic only. Third-party roles remain the independently approved manifest/config pins; no owned-source/signature assertion is fabricated for them. Provenance verification here covers only the three rebuilt owned images. Actual upstream provenance/SBOM references still require independent dependency approval before live publication; this gate cannot invent that approval.

### Publication result and failure contract

Return exact `{protocol_version:2, operation:'publication-transcript-v2', status, simulation:true, provenance_authenticated:false, deployment_authorized:false, source_sha, binding_sha256, checks, failure_code}`. checks exact run,artifact,archive,images,provenance (actual booleans, initiallyFalse). status=transcript_consistent only when all pass; failure_code=None. Failed result status=failed/failure_code=operation_failed; timeout status=timed_out/failure_code=operation_timed_out. Input validation failures raise ContractError('invalid publication input') before callback. No partial success binding/token can authorize anything. binding_sha256 hashes canonical independently supplied binding, never callback content.

## Fixed host-check adapter

Revalidate manifest/config, exact binding/trust and publication result, including protocol/source/binding hash, all checksTrue and simulation=True/provenance_authenticated=False/deployment_authorized=False. This only proves an internally consistent simulation; reject a caller changing those booleans to pretend live authority. Do not accept a legacy transcript/receipt as v2.

Emit exactly one fake request named host_check, method/url=None, body=None, timeout_seconds=30,max_output_bytes=65536 with argv:

```python
['/usr/bin/gcloud', 'compute', 'ssh', config['resources']['instance_name'],
 '--project', config['resources']['host_project_id'], '--zone', config['resources']['zone'],
 '--tunnel-through-iap', '--quiet', '--command',
 'sudo -n /opt/autodata/bin/deploy.sh check ' + manifest['source_sha']]
```

No account/configuration/environment override, user-supplied command, SSH flag, path, helper alias or arbitrary instance is accepted. The config's validated resource names/source prevent shell metacharacters. No `--impersonate-service-account`, token, environment or secret appears in argv. Because actual credential selection is unavailable, this request must **never execute** under this gate. Real WIF/OS Login account selection and enforced IAP deadlines require a later authenticated executor design; `gcloud --quiet` and local timeout alone do not prove remote cancellation.

Callback response exact `{exit_code, receipt}`; exit_code actual2|3|5 only. A host exit0 is rejected even with plausible success JSON. receipt exact existing common operation_receipt keys; schema_version actual1,operation='deploy.sh check',run_id=None,source_sha=selectedSHA,status=failed,valid ordered UTC timestamps,checks exact the existing deploy_cli check set (config,manifest,disk_uuid,metadata_guard,storage_guard,secrets,cached_images,migration_tree,schema,services,runtime_evidence), all booleans, with schema/services/runtime_evidence=False. Require exit3/failure_code=missing_dependency; exit5/operation_timed_out may be recorded as timed_out. An exit2/invalid_input is a rejected host operation, never unavailable readiness evidence. Reject unknown checks/fields, large strings, scalar drift, wrong source and affirmative readiness. Existing timestamp/check receipt helpers may be reused without modifying runtime-check.py.

Return exact `{protocol_version:2, operation:'host-check-transcript-v2',status,simulation:true,provenance_authenticated:false,deployment_authorized:false,source_sha,binding_sha256,checks:{publication_consistent:bool,host_reply_valid:bool,schema:false,services:false,runtime_evidence:false},failure_code}`. Valid exit3 gives status=unavailable,failure_code=missing_dependency. Callback timeout/valid exit5 yields timed_out/operation_timed_out; malformed/exit2/zero/exception yields failed/operation_failed. Input failures raise fixed ContractError before callback. No success status is defined.

## Producer/upload/authentication boundary

This producer defines two-member ZIP bytes only. The real GitHub Actions artifact service chooses an outer download envelope; no current evidence proves it matches this ZIP subset or the generated bytes. This milestone defines an injected uploader below, with no live upload API, asserted undocumented actions/runtime endpoint, automatic archive extraction or redirect/token implementation. It cannot close the historical future_publication_gate. An authorized future publisher must capture authenticated actual run/artifact metadata and original download bytes, verify provider-reported digest semantics, and prove exact compatibility or amend/review the protocol (including a safe outer-envelope parser if needed) before transport use. Do not advertise deterministic producer success as GitHub compatibility or authentic publication.

A future actual provenance gate must verify signature chain/trusted issuer/audience, exact signer/builder/workflow/ref/source and artifact subject; fetch and verify immutable SBOM content; pin verifier binaries/actions by reviewed hashes; prove OIDC/WIF and negative IAM/environment tests. Current claims/evidence/signature booleans are fixtures only. Owner values and exact upstream image provenance policy remain prerequisites to that separate gate, not placeholders implementers may invent here.

## Concrete todo

- [ ] Synchronize this exact publisher-orchestration/host-check goal, three-path allowlist, fixed checkout/build/push/evidence/upload operations, trust/DTOs and five todos in Issue186/Project8 and canonical documents; preserve prior Project index, commit/push and pass pinned preflight before independent coordinator gate review.
- [ ] Add failing fake-executor publisher sequencing tests and implement fixed source checkout, three digest-bound build/push operations and post-build registry identity verification; no real executable, network or credential discovery may run.
- [ ] Implement deterministic inner release.zip production, bounded SBOM/provenance publish/verify and artifact upload/readback through injected interfaces, with versioned independent transport/payload/member/manifest digests and adversarial identity/subject/signature fixtures.
- [ ] Add failing fixed IAP host-check tests and implement only the configured VM deploy.sh check SHA request with strict failed-readiness receipt handling; keep every mutation, schema/service/runtime readiness and CLI/workflow activation unavailable.
- [ ] Run focused B and unchanged A regressions, syntax, scope/diff and pinned preflight; commit/push coherent candidates for independent exact-SHA review, retaining red/green evidence and actual authentication/archive compatibility, owner/provider, staging and paid-product gates.

## Implementation tasks after a passing gate

### Task1: deterministic producer and versioned binding

Files: cloud-ops.py, test_cloud_ops.py. Interfaces: produce_release_archive and exact producer/binding validators above.

- [ ] Add failing producer test: call producer twice on existing valid host fixtures; assert byte-for-byte equality, exact two members, verify_release_archive(...,expected_archive_sha256=envelope['archive_sha256'],expected_member_sha256=envelope['member_sha256']) returns archive_consistent, and no CLI/network invocation occurred.
- [ ] Add rejection cases for invalid config/rollback/manifest, unknown image role, bool byte count, wrong platform/hash/image ID and >1MiB member. Build independently altered member/ZIP fixtures to verify raw versus canonical bindings.
- [ ] Run `python -m unittest discover -s infra/deploy/gce -p test_cloud_ops.py -v` to red; retain stdout/input hashes outside checkout. Implement only fixed stored ZIP construction and exact validators. Run the same suite green, inspect diff and commit/push `feat: add disconnected Workshop archive producer` after coordinator implementation dispatch.

### Task2: disconnected publication transcript orchestration

Files: same two B paths. Interface: evaluate_publication_v2 and exact fixed observations/result above.

- [ ] Add success fake which raises on any request other than the five literal ordered envelopes. Its provenance fixture has simulationTrue and matching synthetic three-owned-role subjects; assert result remains unauthenticated and unauthorized.
- [ ] Independently mutate each numeric owner/repository identity, workflow/environment/source/config/builder/signer/subject/image/SBOM field; reject missing/extra/duplicate keys, bool/int drift, unsigned/False report, expired/failed run, wrong run/artifact linkage, archive/member/raw size/hash drift. Assert invalid top-level inputs cause zero callbacks; later failures suppress subsequent requests. All fake observation text must be absent from receipts.
- [ ] Add callback timeout, oversized output, exception and partial-request cases. Patch subprocess/socket and existing legacy fake APIs to raise if touched. No fake clock/cancellation claim is introduced: callback timeout is only an injected exception.
- [ ] Run focused suite red, implement bounded exact DTO/request orchestration, run green and legacy tests; inspect diff and commit/push `feat: validate simulated Workshop publication bindings`.

### Task3: fixed host check and documented limits

Files: all three allowed paths. Interface: evaluate_host_check above.

- [ ] Add fake recording exactly one literal gcloud argv from valid configuration. Supply valid existing failed deploy receipt; assert status unavailable and all readiness false. Assert no actual process launch.
- [ ] Reject injected host/zone/project/command/path/flags through strict config; reject mismatched publication/binding/source, simulated receipt promoted to authenticated, legacy receipt, exit0, unexpected keys, affirmative readiness and wrong operation. Exercise timeout/oversize/unknown checks/bool exit/status failure and redaction. Callback failure cannot produce success or trigger cleanup mutations.
- [ ] Run focused tests red, implement fixed request and response handling green; update only runbook executable-boundary text without changing historical evidence.
- [ ] Run both focused suites and syntax/diff/scope checks below. Commit/push `feat: model bounded Workshop host check without readiness promotion`; independent exact-SHA review precedes integration.

## Verification and tracking handoff

```text
python -m unittest discover -s infra/deploy/gce -p test_cloud_ops.py -v
python -m unittest discover -s infra/deploy/gce -p test_host_runtime.py -v
python -m py_compile infra/deploy/gce/cloud-ops.py infra/deploy/gce/test_cloud_ops.py
git diff --check
git diff --name-only <implementation-base> HEAD
python scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-03-workshop-publisher-transport.json --base-sha <full-committed-planning-checkpoint-sha>
```

During this planning turn validate JSON, canonical scope and diff only. Commit/push only after serialized live Issue186/Project8 readback establishes exact goal/todos/scope, preserving prior index verbatim. Then run machine preflight at the full committed checkpoint SHA and obtain independent coordinator review. Status synchronized does not dispatch a builder by itself. Record exact readback references/hashes and review findings. At integration re-pin to the integrated planning SHA and rerun preflight; never infer authorization from an uncommitted/later plan.

Production blockers remain owner project/billing/region/cost/recovery/operator/alerts/maintenance/cutover approvals; verified protected environments/WIF/IAM identities; pinned real toolchain/actions; authenticated actual publication/archive/SBOM/provenance evidence; bootstrap/host/mount/guards/secrets; approved schema-observation integration; services/no-work and restore/monitoring evidence; separately authorized bank/model/Firebase/merchant/price verification and final $20 USD single-vehicle permanent account-bound access/browser acceptance. Existing Vercel/DNS and cars.tk stay unchanged.

## Normative concrete publisher orchestration (supersedes observational-only descriptions)

This section is part of this same gate. Implementation is incomplete without the following orchestrator and red/green fake tests. Existing archive/observation APIs remain useful components; comparing supplied metadata alone cannot satisfy this task.

```python
def orchestrate_publication(manifest: dict, config: dict, trust: dict,
                            execution_policy: dict, *, executor,
                            registry_transport, evidence_transport,
                            artifact_transport,
                            rollback_manifest: dict | None = None) -> dict: ...
```

All four dependencies are explicitly supplied callables and **have no default real adapter**. Calls invoke concrete operations below, with bounded requests/results; they are not replaced by caller-supplied success flags. Production adapters can implement the same protocol without changing the orchestrator/producer/binding/host-check interfaces. CLI/workflows cannot reach this function. Tests patch subprocess/network APIs to fail if called; injected fakes record every call and return independently constructed bytes/metadata. Code implements sequence/validation/failure handling now, rather than promising it for a future milestone.

Inputs are an independently reviewed full expected release manifest/config (with exact expected owned image digests/config IDs/evidence locators), trust above and execution_policy. This is a **promotion/rebuild publisher**: build output must match reviewed immutable expected digests. It does not invent a manifest after an unexpected build. Non-reproducible outputs fail publication and require a separately reviewed pin update; no tag is treated as authority. The orchestrator may already have pushed an unexpected image by the time digest mismatch is observed, but it must not publish a release artifact or invoke a host check. Record that side effect as partial, never roll it back by deleting registry objects.

execution_policy exact keys: run_id, source_epoch, tool_sha256. run_id positive numeric GitHub run ID, source_epoch actual integer0..4102444800 (expected source committer timestamp), tool_sha256 exact git,docker,syft with64hex values. Tool paths fixed /usr/bin/git,/usr/bin/docker,/usr/bin/syft. Pinned adapters must later attest executable hashes/dependency/plugin versions; current fake execution starts with `verify_tools` request carrying this exact mapping and then must report the same hashes. No actual tool pins or owner identity are guessed by the implementation agent. Toolchain package identities in manifest still validate unchanged. execution_policy.source_epoch must equal the checkout's actual committer timestamp as read below.

Executor request exact `{name,argv,cwd,env,timeout_seconds,max_output_bytes}`. cwd is /work/workshop-release (trusted runner-owned empty workspace supplied by the future adapter). env is exact PATH=/usr/bin:/bin,LANG=C,LC_ALL=C,GIT_CONFIG_NOSYSTEM=1,GIT_CONFIG_GLOBAL=/dev/null,GIT_TERMINAL_PROMPT=0,DOCKER_CONFIG=/run/workshop-publisher/docker. This object is passed as data only in this gate. No caller HOME/PATH/credential injection. Future real adapter supplies narrowly scoped registry authentication via private tmpfs DOCKER_CONFIG, with cleanup and denial evidence; it cannot use VM/developer credentials. Executor response exact `{exit_code,stdout}` with actual integer exit0..255 and actual bounded bytes. Nonzero stops publication. All executor calls are noninteractive (stdin DEVNULL in the future adapter), with one operation deadline per request; no arbitrary command/string override exists.

Operations in order:

1. executor `verify_tools`: argv=[],10s,64KiB; fake stdout is strict JSON exact tool_sha256 mapping. This is an explicit adapter operation, not a nonexistent executable command.
2. executor `checkout_init`: ['/usr/bin/git','-c','core.hooksPath=/dev/null','init','/work/workshop-release/source']; cwd=/work/workshop-release,10s,64KiB.
3. executor `checkout_fetch`: ['/usr/bin/git','-C','/work/workshop-release/source','-c','core.hooksPath=/dev/null','fetch','--no-tags','--depth=1','https://github.com/lucronn/autodata.git',manifest.source_sha];120s,64KiB.
4. executor `checkout_select`: ['/usr/bin/git','-C','/work/workshop-release/source','-c','core.hooksPath=/dev/null','checkout','--detach',manifest.source_sha];30s,64KiB.
5. executor `checkout_identity`: ['/usr/bin/git','-C','/work/workshop-release/source','show','--no-patch','--format=%H%n%ct','HEAD'];10s,128bytes. Exact stdout is SHA+'\n'+decimal source_epoch+'\n'; reject anything else. No submodule execution, hooks, pull by branch or recursive checkout.
6. For roles api,ingestion,migration in exactly that order, executor build_ROLE uses cwd=/work/workshop-release/source,1800s,64KiB, fixed Dockerfiles apps/api-go/Dockerfile, workers/ingestion-python/Dockerfile, infra/deploy/gce/migration.Dockerfile:

```python
['/usr/bin/docker','buildx','build','--platform','linux/amd64',
 '--provenance=mode=max','--sbom=true','--push',
 '--build-arg','SOURCE_DATE_EPOCH='+str(execution_policy['source_epoch']),
 '--file',dockerfile,'--tag',repository+'/'+role+':source-'+source_sha,
 '--metadata-file','/work/workshop-release/'+role+'-build.json','.']
```

The source tag is a publishing locator only; no release uses it as an immutable identity. Future registry repository must enforce tag immutability or an independently reviewed no-overwrite policy. This code does not configure registry IAM. Buildkit SBOM/provenance dependencies/plugins must be pinned by the later toolchain adapter gate; flags alone are not verification.

7. After each build, registry_transport request exact `{name:'image',repository,role,source_tag,expected_reference,platform,timeout_seconds:60,max_output_bytes:65536}`; response exactly `{reference,image_id,platform,build_source_sha,build_config_sha256}`. Digest reference/config ID must match independently approved manifest, platform linux/amd64, build_source_sha selectedSHA, build_config_sha256=config digest. This is the adapter's content inspection result; future actual adapter must read OCI manifest/config bytes and verify their hashes and build provenance. No simulated equality is called authenticated.
8. For each owned role, executor sbom_ROLE: ['/usr/bin/syft',manifest.images[role].reference,'-o','spdx-json'];cwd=/work/workshop-release/source,300s,4MiB. Parse bounded duplicate-key-free JSON, require spdxVersion='SPDX-2.3', documentNamespace a nonempty HTTPS URI<=4096, name nonempty<=4096, packages actual list<=10000. Retain original bytes and sha256; full SPDX semantic approval remains later verifier policy. No archive/receipt includes SBOM bytes.
9. evidence_transport request exact `{name:'publish_and_verify',role,image_reference,image_id,source_sha,service_config_sha256,workflow_ref,builder_id,oidc_issuer,oidc_audience,sbom_bytes,sbom_sha256,expected_provenance_uri,expected_sbom_uri,timeout_seconds:300,max_output_bytes:65536}`. Adapter operation must publish immutable SBOM/evidence and verify owned-image build provenance/signature subject/source/config before responding. This is an injected transport operation, not a fabricated public API URL. No cloud bearer token or signing secret is supplied. Response is the matching owned subject report defined above plus `simulation:true`, `sbom_sha256` and `oidc_issuer`, `oidc_audience`, `signer_workflow_ref`, `builder_id`; require exact keys/values and actual True signature/SBOM-valid assertions. In this gate only a fake implements it; real OIDC acquisition/cosign/Sigstore verification and evidence-URI hashing are a separately pinned authenticated adapter. Matching fixtures cannot prove authentic publication.
10. With all three builds and evidence accepted, produce_release_archive from the independently approved manifest/config and exact seven image observations. Call artifact_transport with exact `{name:'upload',artifact_name:'workshop-release-'+SHA,run_id,source_sha,members:{'release.zip':archive_bytes},payload_sha256:archive_sha256,timeout_seconds:300,max_output_bytes:65536}`. Future adapter uses a pinned GitHub upload-artifact action/library, not an invented REST upload endpoint. It must upload exactly one inner release.zip with no sensitive input files, immutable run linkage and no overwrite. Response exact `{artifact_id,run_id,name,expired:false,digest,bytes,simulation:true}`: validate positive IDs, matching run/name, sha256 transport digest, artifact byte count1..16MiB. These wrapper outputs are distinct from the inner ZIP digest/count.
11. artifact_transport `readback` request exact `{name:'readback',artifact_id,run_id,artifact_name,timeout_seconds:300,max_output_bytes:16777216}`. Response exact `{metadata,transport_archive,release_archive}`; metadata matches upload response except simulation flag absent; original outer bytes hash/count to digest/bytes, inner bytes exactly producer archive. Future trusted adapter must parse the outer ZIP boundedly and prove exactly one regular release.zip, no symlink/duplicate/extensions/traversal/extra files and no extraction. This gate tests the interface and corrupt-wrapper rejection, **does not implement/claim actual GitHub envelope compatibility**. Existing verify_release_archive verifies only inner bytes.
12. Return v2 publication binding assembled from independent producer envelope plus accepted run/artifact/name/digest/artifact_bytes, and checks. Never invoke host-check automatically. Publishing and host operation remain separate explicit calls.

Orchestrator result exact `{protocol_version:2,operation:'publisher-orchestration-v2',status,simulation:true,provenance_authenticated:false,deployment_authorized:false,source_sha,binding,checks,failure_code}`. checks exact tools,checkout,images,evidence,archive,upload,readback all actual booleans initializedFalse. Complete status=transcript_consistent,binding=v2 DTO,failure_code=None; failed status=failed,failure_code=operation_failed,binding=None; callback TimeoutError yields timed_out/operation_timed_out. All input invalidity raises fixed ContractError('invalid publisher input') before any dependency call. Partial writes may exist externally in a future adapter; no delete/rollback authority is introduced. All failed results retain simulation and cannot become a publication receipt. Result canonical bytes<=64KiB and no stdout/SBOM/token/exception text.

Additional required red/green tests in Tasks1–3: exact checkout argv/order/source timestamp; all three role/Dockerfile/tag/platform flags; no artifact upload before all digest/evidence checks pass; registry wrong digest/config/source; false/wrong signer/issuer/audience/source/subject/SBOM report; SBOM malformed/duplicate/oversize; upload wrapper digest/count mismatch; readback wrong inner bytes; timeout/nonzero/exception/partial push at each stage; absent/extra/unknown callbacks fail; every CLI/workflow still denied. The success test must drive orchestrate_publication from fake process stdout through fake registry/evidence/upload/readback and then a **separate** evaluate_host_check, asserting exact requests and readiness denials. A test that supplies only final matching claims cannot satisfy orchestration acceptance.

### Exact follow-on: authenticated publisher adapter and workflow activation gate

Follow-on planning scope is a new dedicated task/record and amendment permitting .github/workflows/release-workshop.yml, cloud-ops.py, test_cloud_ops.py and runbook. Freeze actual numeric owner/repository/project identities, distinct publish/deploy SAs and WIF providers, protected environments, SHA-pinned checkout/auth/build/upload tools/actions and real verifier/dependency policy. Implement the above executor/transports with bounded streaming/deadlines/cleanup, actual OIDC/WIF signature/audience and artifact/OCI/SBOM/evidence verification; prove outer ZIP compatibility or amend its adapter parser without changing inner producer/v2 binding semantics. Publish principal receives only one-registry writer; no VM/secrets/backup authority. Obtain separate owner-authorized staging execution and negative IAM/environment/identity denial tests. Only then replace the publish job's missing_dependency step; keep deploy disabled until independent schema/service/host acceptance. This follow-on is concrete and separately gated because credentials, action/tool pins, real artifact format and authentic trust-denial evidence do not exist in this checkpoint. It is not waived by successful fake orchestration.


Publisher successor tracking readback: [Issue186 comment6621071257](https://github.com/lucronn/autodata/issues/186#issuecomment-6621071257), Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference`, verified `2026-11-04T02:40:50.163236+00:00`. Exact issue body/comment and Project index SHA256 hashes are retained in the dedicated publisher record. Prior Project index is preserved verbatim with hash in that comment. This is synchronized planning only; committed pinned preflight and independent coordinator review still precede any builder dispatch. No implementation or actual publication evidence exists.
