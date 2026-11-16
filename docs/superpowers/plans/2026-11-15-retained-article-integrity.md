# One retained article hash-only integrity proof

Issue: https://github.com/lucronn/autodata/issues/428
Project: https://github.com/users/lucronn/projects/8 itemPVTI_lAHOCSJ8cc4BiQ2BzhI0nNU.
Source base4048f3fae50161af5b5ab8300670e3beb817ce1a; public5981r2 and private083f are observed context, not modified targets.

Goal: prove source-blob hash plus opaque article/source/current canonical identity and document schema for one already retained readable article. Internal processing only; no body bytes/IDs/titles/images in logs/receipts, no display, no grants/auth bypass, no paid GET, no supplier/model/ingestion calls, no serving/DB/object writes. User authorizes internal real-data test; root must review concrete package BEFORE any new runtime access.

Transport: fixed SQL selects exactly one existing readable available canonical article with matching source/canonical pointer and active membership/takedown. PostgreSQL connection explicitly read-only with statement2s/lock250ms/idle5s timeout, repeatable-read transaction; query row/projection size predicates and limited1. Keep identity and content exclusively in process memory. Validate configured DB/S3 against exact reviewed literal loopback host:port allowlist, no DNS/service DSN/credential output. One local S3 GET max64KiB(+1 sentinel) using SDK retry0/connect2s/read3s and outer process20s/CPU5s/memory256MiB. Input envelope including documents <=512KiB. No object create/version/list/write. Content may include text/HTML/HAL bytes: hash bytes without interpreting executable markup.

Isolation: parent orchestration captures transport stdout in memory and NEVER forwards raw output, only to a fresh cached-image Python child over stdin. Validator child uses Docker networknone, read-only filesystem, capdropall, no-new-privileges, pids32, memory128MiB, cpus0.5, CPU5s, timeout10s; source mounted read-only, PYTHONDONTWRITEBYTECODE and no volumes writable. No protected payload disk file. No supplier/model connectors or app worker invocation. Parent transport itself uses only reviewed fixed local DB/S3 endpoints with fixed SQL and no content execution; this is audited endpoint restriction, not a claim that a Python monkeypatch enforces kernel network isolation. Root reviews actual runtime access implementation/limits before any real dispatch.

Validation: input top-level exact schema, UUID identity/source/canonical consistency, source snapshot SHA256 equals fetched body and content-addressed storage key, bounded ordered source/current document shape/node counts, available/current canonical origin and published/readable flags. Emit only stable version/pass/boolean/count/hash fields. Reject malformed/deep/oversized documents, mismatched IDs/hash/key, missing content, transport timeout and unexpected SDK failures with generic codes; no exception trace/HTTPbody/rawstdout. Known UNREVIEWED and empty license metadata remain visible only as booleans and do not imply rights. Hash proof is storage/projection integrity, not canonical quality or paid-reader acceptance.

Synthetic tests cover valid bytes/doc schema, altered body/source/pointer/key, unknown schema, depth/node/bytes/timeout limits and receipt redaction; all real transport remains held for root review. Do not use ambient live credentials in synthetic tests. No new Docker image build or cleanup; cached image exactdigest must be root-approved, as must DB/S3 loopbackports. Genuine test settlement/Firebase/terms/origin/scoped entitlement and supplier-authorized SVG recapture are separate gates. No stored SVG originals exist for automatic image reprocessing. Hold final PR CI while #427 may advance base; never merge/deploy here.

Concrete todo:
- Synchronize exact4048 source plan Issue428 Project8 canonical docs and preflight before implementation
- Implement fixed-read-only SQL and one bounded local S3 GET with private in-memory transport only
- Validate source hash identity and projection schema in no-network read-only resource-bounded child
- Test negative hash schema identity input limits and write/egress guards with authored data
- Send exact implementation limits SQL endpoint image and command allowlist to root before any real runtime access
- Hold final PR CI until coordinated protected base; preserve paid reader rights and image limits


## Pre-runtime hardening gate amendment

Root holds real --run and all Docker run/exec/DB/S3 access. Narrow exact-candidate Docker inspect mounts/env and local source-file hashes are authorized read-only, never raw Env/secret output. Before implementation edits, synchronize this amendment/Issue428/Project8/record and preflight.

Concrete todo:
- Pin exact343896 candidate ID/image3132/running/read-only/host-network/mount and independently reviewed source hashes before/after transport; exact nonsecret DB/user autodata/bucket autodata-sources/endpoints127:5432/19000. Raw inspect remains private.
- Require physical0700 root-owned package and regular nonsymlink read-only script; hash/file identity before/after. Pass captured reviewed bytes to transport and same sealed file to validator; fail closed on drift.
- Strict exact redacted receipt key/type/range/hash schema before printing; reject swapped child/free text/unknown fields.
- Bound concurrent stdout/stderr and input pipes with absolute deadlines and own-child cleanup; fixed redacted errors.
- Test runtime/source/script/receipt drift, output overflow and timeout with authored local fixtures only. No Docker run/exec or real DB/S3/payload GET before root revised-package review. Hold final CI for coordinated base.

Source mount/hash anchors must be independently pinned, not trusted from execution-time readback. Root-owned seal is preparation only, not runtime authority. Existing fixed SELECT/read-only transaction/local oneGET limits remain. No grant/paid reader/rights/display claims.


## Actual bounded retained-body integrity proof — PASS

The coordinator independently reviewed exact sealed code `9424dfee0474d44b7eb2511d64945c0c3a92e57b`, verified root-owned package hashes, ran the authored-only Docker validator fixture PASS, then executed **exactly one** real hash-only --run from the sealed physical package under clean env. No additional runtime/DB/S3/Docker/provider request was made while recording this outcome.

Private receipt `/home/corp/.local/state/autodata-retained-integrity-outcome-20261115/receipt.json`, mode0600, SHA256 `7abd8798fa6e864c1afae6290579f57e1b724aa0c8d2f95870b859e58247e455`. This documentation agent independently read the receipt locally, verified its file hash and extracted only the following redacted fields. Article identity/title, protected body, source-body hash, projection hashes and selection hash remain private and are not published here.

- passed, source_hash_verified, identity_verified, ordered_projection_schema_verified and canonical_published: true.
- Retained body length:2283bytes; source document9blocks/103JSONnodes; current document10blocks/113JSONnodes.
- unreviewed and license_metadata_empty: true.
- licensed_display and paid_reader_acceptance: false; supplier_calls and model_calls:0.

The coordinator independently postchecked candidate343896 running with restart count0, unchanged StartedAt and image3132, no residual authored/integrity validator containers, public health200 and stable Docker/home capacity. Those postchecks are coordinator observations, not extra requests by the documentation agent. The harness's pre/post exact candidate/env/source/script guards passed as prerequisites of its successful receipt.

This proves one already retained source object's bytes matched the persisted source snapshot hash, the selected opaque article/source/current published canonical identities were consistent, and source/current ordered projection structure met the bounded validator checks. It does not prove canonical semantic correctness, human review, supplier permission or real catalog completeness. It did not render licensed content or access images, paid-reader routes, Firebase/Stripe/session/grant creation, supplier/model/ingestion work. Existing published data remains UNREVIEWED and lacks affirmative license metadata. No stored SVG original or localized real image was repaired by this run.

Normal paid-reader acceptance remains blocked on an authorized exact configuration-scoped entitlement via genuine TEST settlement after owner UID/project/origin/terms, plus applicable content permissions. Legacy nonpaid list/detail may schedule writes and were not called. Paid GET remains grant-gated and requires Firebase GetUser/internal read-only grants-check dependencies; this lower-layer integrity proof does not bypass or replace them. Any real image recapture still requires supplier rights and an exact bounded provider-GET gate. External/public licensed exposure stays disabled.

The internal integrity objective is complete; code PR/final CI/protected-base integration remain HELD for coordinator scheduling and review. No merge/deploy/second real read is authorized by this result. Prior gate/negative tests and first-preparation limitations are retained as history, superseded only as to the now-observed authored Docker launch and one real integrity run.


## Protected-base PR refresh — 2026-11-15

PR #434 is refreshed onto protected `a82b31dc8850aa3956972928b8c720969765a972` for integration review. The prior exact head `9bddc35a577f6f571e1805f78f32c1df99f6b001` passed all three required checks in [run 43673423719](https://github.com/lucronn/autodata/actions/runs/43673423719). Its earlier final-CI holds above are historical; fresh exact-head remote CI is now authorized and required after this refresh.

The implementation and its historical candidate343/source083f runtime/source pins remain byte-identical. They describe the reviewed one-shot proof, not the current serving runtime or authorization for another run. The single redacted proof and all rights/paid-reader limitations remain unchanged. No new runtime, SQL, object-store, Docker, browser, provider or real-data access is part of this refresh. M2A retains exclusive local build capacity; no local test or build is run.

Concrete todo for this refresh (Issue [#428](https://github.com/lucronn/autodata/issues/428), [Project #8](https://github.com/users/lucronn/projects/8), status Review):
- Rebase the existing PR onto exact protected a82b31dc without changing implementation or historical proof.
- Synchronize Issue/Project, this plan, canonical documentation and record; run machine preflight at the committed checkpoint.
- Verify unchanged implementation blobs and the seven-path PR scope; push with the exact old-head lease and obtain strict remote CI.
- Hold merge, deployment and all further real-data runs for the coordinator.


## Protected historical-docs integration refresh — 2026-11-15

Current PR #434 base is protected `b3214b693c58e3fc13b607f24f232db2ea4e8a2a` (merged PR #442). This supersedes the a82 integration checkpoint only for PR base/CI scheduling. The ordinary rebase was conflict-free; all three implementation/test blobs, historical candidate343/source083f pins, the single redacted proof and every prior rights/paid-reader limitation remain unchanged. Fresh strict remote CI is required for the resulting head; prior-head CI is historical.

Concrete todo (Issue #428 / Project #8 Review): synchronize this base update and record, commit and preflight the checkpoint, verify the unchanged three implementation blobs/seven-path scope, push with an exact old-head lease and update the PR head/base/CI report. Hold merge, deployment and any new real-data run. Validation is metadata/preflight only; no local tests, build, Docker, browser, SQL/S3 or provider access. Existing offloaded worktree only; no runtime package allocation.
