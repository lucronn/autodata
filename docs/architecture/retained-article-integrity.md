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


## Prepared implementation; REAL ACCESS HELD

Gate `6ce5730f5beadcc201d53e63a960929b867166a6` passed synchronized preflight before implementation. Added scripts/dev/retained_article_integrity.py plus authored-only tests;9unit tests PASS, git diff --check PASS. No Docker/API/DB/S3 runtime command was dispatched during implementation. No real payload proof has run.

Coordinator supplied/approved in principle literal DB127.0.0.1:5432 and S3 HTTP127.0.0.1:19000 for exact current candidate343896791b0377600b9825b53c1ddb1b179d54c424d19ea935c0b9b8a681eb07; cached child image3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7. Concrete runtime approval remains required. Transport imports psycopg/minio directly, no application worker/provider/model imports. Fixed SELECT (no caller identity/SQL) picks one existing available readable published canonical matching current pointer/source; bounded documents, private opaque identity only. Literal endpoint mismatch fails before client imports. DB default_transaction_read_only=on plus explicit repeatable-read/read-only transaction, SHOW enforcement, statement2s/lock250ms/idle5s/connect2s. No role/schema/grant creation. Psycopg uses existing env credentials privately and explicit literal host/port, not ambient DSN.

S3 direct local HTTP, explicit us-east-1 region avoids location lookup; retry0/connect2s/read3s; exactly one content-addressed GET <=64KiB+1sentinel, closed/released, SHA256 checked before private output. Transport alarm20s/CPU5s/addressspace256MiB/file-size0/core0. Python audit hook denies file writes/mutations/subprocess and nonallowlisted Python socket/DNS events after imports; it is defense in depth, NOT a claim that audit hooks constrain libpq C sockets. Libpq egress is controlled by fixed literal connect parameters/fixed SELECT/read-only server transaction. Root should assess this explicit trust boundary before dispatch.

Host orchestrator captures protocol stdout/stderr privately, never forwards exceptions/transport content, accepts <=512KiB only, timeout25s. It feeds memory-only input to fresh randomly named validator: Docker pinned local socket and imageID; --log-driver none --network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit32 --memory128m --memory-swap128m --cpus0.5 --ulimit cpu=5:5/fsize=0:0/core=0:0, script bind readonly, entrypoint/usr/local/bin/python3 -I -S -B /audit.py --validate; no secret environment/mount. Outer validator timeout10s; finally rm -f ONLY newly generated validator name, timeout5s. No production container is removed/reconfigured. Existing candidate receives only bounded separate Python exec, not service entrypoint/startup mutation. Root must review these exact disposable-container/runtime accesses first.

Validator checks exact envelope keys and UUID pointer equality, canonical published/readable/available booleans, content-addressed source key+payload hash, ordered-document version/types/order and tree depth<=24/nodes<=16000/blocks<=1024/doc<=128KiB. It does not render or interpret HTML/URLs. Projection hashes are reported, not asserted as model-quality or canonical-normalization checks. Stable failures redact exceptions/content. Receipt emits only booleans/counts/hashes and explicitly paid_reader_acceptance=false/licensed_display=false. Body/current/source documents never persist. UNREVIEWED/empty license metadata booleans are not rights assertions.

Synthetic tests verify redaction, mismatched body/hash/object key/article/source/canonical pointer, unpublished/schema/type/order/depth/body/doc/envelope limits, malformed IDs/unknown fields, timeout/no raw forwarding, exact child isolation argv, Python file/egress guards, local endpoint refusal before dependency imports and fixed SQL lacks mutation clauses. These are unit/command-contract tests; actual network-none Docker confinement and SDK transport have NOT yet been exercised. Next review can first authorize authored-only container/transport fixture, then one real read. Hold final PR CI for #427 coordinated base.

Proposed sole real execution after concrete approval: `/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 /home/corp/.codex/worktrees/retained-article-integrity/autodata/scripts/dev/retained_article_integrity.py --run`, capturing ONLY final redacted receipt in private evidence. Never invoke --transport directly into a tool/log/terminal; it is exclusively an internal private pipe protocol. No paid GET, session/grant write, supplier/model/ingestion dispatch, or image recapture is included.

Prepared harness SHA256 `46abb014c5cfb1cb0354b00033985d28cd8f0f56063a9a01888a8e1c8a060b7f`.


## Pre-runtime hardening gate amendment

Root holds real --run and all Docker run/exec/DB/S3 access. Narrow exact-candidate Docker inspect mounts/env and local source-file hashes are authorized read-only, never raw Env/secret output. Before implementation edits, synchronize this amendment/Issue428/Project8/record and preflight.

Concrete todo:
- Pin exact343896 candidate ID/image3132/running/read-only/host-network/mount and independently reviewed source hashes before/after transport; exact nonsecret DB/user autodata/bucket autodata-sources/endpoints127:5432/19000. Raw inspect remains private.
- Require physical0700 root-owned package and regular nonsymlink read-only script; hash/file identity before/after. Pass captured reviewed bytes to transport and same sealed file to validator; fail closed on drift.
- Strict exact redacted receipt key/type/range/hash schema before printing; reject swapped child/free text/unknown fields.
- Bound concurrent stdout/stderr and input pipes with absolute deadlines and own-child cleanup; fixed redacted errors.
- Test runtime/source/script/receipt drift, output overflow and timeout with authored local fixtures only. No Docker run/exec or real DB/S3/payload GET before root revised-package review. Hold final CI for coordinated base.

Source mount/hash anchors must be independently pinned, not trusted from execution-time readback. Root-owned seal is preparation only, not runtime authority. Existing fixed SELECT/read-only transaction/local oneGET limits remain. No grant/paid reader/rights/display claims.


## Hardened package review seal — runtime and authored Docker fixture HELD

Hardening checkpoint `4889e80a74458c5d2f95b187ab7d364747e6f5ec` passed preflight before implementation. Root authorized only narrowly filtered exact-candidate inspect and local code hashes. Those metadata reads were performed; no Docker run/exec, DB/S3 content/metadata call or article byte read occurred in this phase. Raw inspect retained private0600 under physical0700 `/home/corp/.local/state/autodata-retained-integrity-hardening-20261115/`; filtered receipt contains only approved nonsecret fields. Four selected code hashes independently match protected083f1a5.

New physical package `/home/corp/.local/state/autodata-retained-integrity-428-20261115` root:root0700; three scripts root:root0400, regular/nonsymlink/nlink1. Static root-only script_guard and all-three-file hash verification PASS without Docker or DB/S3 access. Package manifest SHA256 `b9d873fe7fb7684f4c9fbbec5c814282cddd054bbdc37b20282b1def8150f63f`. Harness SHA256 `bf24f67bda8d0a28d69f33b7efdce29399134766bc428edc4f7499d14bbf8e52`. Unit tests SHA256 `6101c4559591464050cb6d9307381b2ba0a4e79ea3077afe734ae8876daaa895`; authored-only validator fixture SHA256 `a89d207332046ed7665ee9f574d9d0bdd2179e034e59b107a13d72463da9dae2`.

Four requested hardenings:
- Runtime guard bounded Docker inspect before AND immediately after transport requires exactID/image/running/read-only/hostnetwork, sole `/app` bind from `/home/corp/autodata-candidate/private-diagnostics-svg-083f1a5-20261115/source` RWfalse, exact approved DB/user/bucket/endpoints. Four bounded nonsymlink local source-file SHA256 anchors checked both times: http_service, article_lifecycle_store, worker, commerce_service. All match protected083f source; raw Env is never emitted. Transport also requires exact same nonsecret env. No self-trusting live source seal.
- Run requires reviewed expected-script hash, physical root-owned0700 parent and root-owned0400 regular/nonsymlink/nlink1 script. Read once through O_NOFOLLOW fd with64KiB cap; byte hash+device/inode/size/mtime/ctime checked after transport and after validator. Those exact captured reviewed bytes are passed to transport argv, and same root-sealed script is validator readonly mount. Mutable-worktree --run now fails before Docker. Root package is the sole execution path; earlier worktree-only command is SUPERSEDED.
- Parent strictly validates exact receipt keys/types/ranges/boolean constants/hash syntax including nested documents before printing. Validator main uses same guard. Unknown child fields/free text/extra nested keys/string-vs-bool/invalid hashes fail fixed RECEIPT_SCHEMA; raw child output is never forwarded.
- All subprocess stdout/stderr drain concurrently through selectors, capped per stream while reading, with absolute deadlines and process kill/wait. Transport stdout512KiB/stderr4KiB/25s; inspect128KiB/4KiB/5s; validator4KiB/4KiB/10s; own-child cleanup1KiB/4KiB/5s. Inputs use concurrent bounded pipe writes. Docker child `--pull never` prevents accidental registry requests. Existing no-network/read-only/cap-drop/no-newprivs/CPU/memory/PID/no-log protections remain.

Fourteen authored-only unit tests PASS, including real LOCAL Python subprocess overflow on either stdout/stderr and deadline, runtime/source/hash drift, script mutable/symlink refusal, malicious extra child text/type/nested fields, post-transport seal change, cleanup scope, guards/receipt/body/schema tests. git diff --check PASS. These tests did not run Docker or access real data. Physical root package seal check PASS is filesystem-only. Actual kernel/Docker validator launch and actual SDK transport remain UNTESTED pending review.

Review sequence: first approve ONLY authored Docker validator fixture (no runtime inspect/transport/DB/S3):
`/usr/bin/sudo -n /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B /home/corp/.local/state/autodata-retained-integrity-428-20261115/retained_article_validator_fixture.py bf24f67bda8d0a28d69f33b7efdce29399134766bc428edc4f7499d14bbf8e52`

It generates fictional in-memory bytes/documents, uses same sealed no-network child, strict redacted receipt equality and seal checks, removes only its fresh random validator. It contains no call to transport/run/runtime_guard. No real credentials or source bytes are fed to child.

Only after separate concrete approval, one real hash-only execution command would be:
`/usr/bin/sudo -n /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B /home/corp/.local/state/autodata-retained-integrity-428-20261115/retained_article_integrity.py --run --expected-script-sha256 bf24f67bda8d0a28d69f33b7efdce29399134766bc428edc4f7499d14bbf8e52`

Both commands are currently HELD for root review. No protected payload is written to disk; output contains only strict receipt fields. No paid GET, grant/session write, supplier/model/ingestion request, image recapture, display, runtime reconfiguration or rights assertion is included. Final PR/CI still held for coordinated base.


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
