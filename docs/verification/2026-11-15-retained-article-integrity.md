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
