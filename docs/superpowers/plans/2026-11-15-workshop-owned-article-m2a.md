# Private authored article M2A implementation gate

Goal: Prove private authored article and image display through real isolated PG/S3 and Go Workshop with explicit browser-only auth simulation.
Issue https://github.com/lucronn/autodata/issues/398; Project https://github.com/users/lucronn/projects/8.
Protectedf534d0aeb76973ca3b8c70b14c806973edb1b457/tree902287299c37c49ebb3cae2245303e0c95100e90.


Implementation requires the checkpoint/preflight below. M1 accepted source94d3f499, state marker, stopped containers, bind data, binary and receipts remain untouched. No services, databases or credentials changed for this draft. PR426 merged; this new gate authorizes only its explicit allowlist after exact preflight.

Decision: split local owned-fixture article display from actual Firebase/Stripe/provider acceptance. Use a fresh M2A fixed project/network/root with an owned synthetic article and image, commerce disabled and outbound provider credentials blank. Never reuse M2A data or auth simulation for external testers.

## Source findings

- The existing real Postgres catalog store reads vehicle_configurations/vehicle_identity_bases and catalog_articles; image bytes use configured S3 and an opaque signed local image path. This can prove real DB-to-Go-to-browser text and S3-to-Go-to-browser image display.
- The current UI checks session.state.authenticated before loading article index/detail. M1 local /auth/session returns401; adding a local Bearer header alone cannot exercise the UI reader.
- Existing workers/ingestion-python/src/autodata_ingestion/ingest_fixture.py creates fake payment events/entitlements and dataset projections. Do not invoke it for this article-only smoke. scripts/dev/workshop_backup_restore_fixture.py also seeds fake paid orders/grants; do not reuse its whole seed.
- scripts/dev/workshop_browser_smoke.py is a frozen120-case DTO/TLS fixture inventory, not a real Postgres/S3 runtime proof. Do not relabel it.
- Host Python Playwright1.55.0+ds and /usr/bin/chromium exist, but browser caches contain no installed browser payload. A gate must pin/hash/check the existing browser and prove a bounded launch, or explicitly approve installing a matched pinned runtime/browser on home storage. No image build is required for this draft path.

## Proposed smallest implementation

1. A fresh immutable protected-source snapshot and host-built binary; independent root /home/corp/autodata-workshop-owned-article-data-20261115/m2a, fixed project autodata-workshop-owned-article-m2a-20261115, separate internal network, fresh PG/S3/NATS/local-only material, host loopback3042 only. Reuse immutable cached carrier IDs only under a newly reviewed effective-ENV/image-volume contract. Embedded cached ingestion defaults require explicit local-only containment approval; before external exposure require a clean credential-free image/digest. No changes to M1 policy files or private M1 state.
2. Add an independent one-shot owned-fixture seeder with exact-project/root/database admission, fresh-empty proof, a hash-bound seed marker and idempotence check. One wholly authored fictional training vehicle, one minimal article with two harmless invented steps, one generated PNG, and owned-provenance/hash manifest. Minimal required source_snapshot/evidence/vehicle/identity_base/configuration/catalog_article rows; source_artifact row only if the selected real source-review path requires it. One image object under procedure-images/<sha256> with exact MIME/hash. Avoid all customer/account/session/payment/order/grant rows; verify their counts remain zero. Direct seed establishes display/data persistence, not provider ingestion/publishing proof. If ingestion is required instead, use persist_source_bundle with authored SourceArtifacts and publication=None under its own tests, never FakePaymentProvider.
3. Browser-only harness: fresh isolated context and local runtime origin allowlist; block service workers, external navigation/requests and downloads. Attach synthetic local Bearer only to real catalog requests on the exact admitted local origin. Fulfil ONLY /auth/session with a clearly synthetic, short-lived session-shaped response so the unchanged UI permits reading. Leave auth/config, purchase configuration, selectors, article index/detail, image and static assets real. Record the single fulfilled route explicitly. Never fulfil or rewrite catalog/article/image responses. This is article data-path acceptance with simulated browser auth; it is not full authentication/CSRF/payment acceptance.
4. Navigate the actual Workshop, select the fictional vehicle, open the article, assert exact title/step order/body, verify image natural dimensions and response MIME/hash, reload/deep-link once, capture screenshot plus console/request/error receipts. Assert no provider authority, zero checkout/payment/grant/session DB rows, disabled purchase flag and no external application request. Negative controls: article DB text change reflected in UI; missing image denied/marked unavailable; omitted synthetic browser auth remains unable to read. Do not fabricate successful paid access.
5. Apply the reviewed full actual-policy/ENV/source/lifecycle/locking/capacity guards to this independent fixed project. Pin exact new source/browser/image/binary identities, verify resource ownership before each phase, retain512MiB Docker/2GiB home reserve plus startup/log/growth allowance, stop on mismatch and preserve stores. Stop owned browser/relay/new services and write separate receipts.

Proposed independent implementation allowlist for a new gate: infra/compose/compose.workshop-owned-article.yaml; scripts/dev/workshop_owned_article_admission.py; scripts/dev/test_workshop_owned_article_admission.py; scripts/dev/workshop_owned_article_forwarder.py; scripts/dev/test_workshop_owned_article_forwarder.py; scripts/dev/workshop_owned_article_seed.py; scripts/dev/test_workshop_owned_article_seed.py; scripts/dev/workshop_owned_article_smoke.py; scripts/dev/test_workshop_owned_article_smoke.py; small owned fixtures under scripts/dev/fixtures/workshop_owned_article/; canonical ops/verification docs. For this disposable fixture milestone, use independent fixed-profile copies of reviewed admission/relay mechanics with an explicit namespace/port/store-only diff. Preserve all five M1 implementation files unchanged. Review the copy diff and run the inherited isolation tests against the M2 profile; defer a shared-profile refactor to a later gate. This trades duplicate helper code for a smaller current authority change.

Red-first tests: M1/project/production target rejection; nonempty unmarked stores; exact authored fixture schema/hash/idempotence; no payment/grant writes; real catalog responses never fulfilled; external request blocked; auth simulation limited to exact origin/path; API/source mutation fences; image object/response integrity. The browser launch/dependency probe is a prerequisite, not a fixture or acceptance substitute.

## Real end-to-end successor

If end-to-end means real session establishment, this shortcut is insufficient. Require a fresh disposable Firebase/Stripe TEST stage with approved tester UID/roles, actual local/public auth-origin and cookie/CSRF contract, clean credential-free carrier and account/webhook inputs. Seed only owned article data; obtain real TEST checkout/webhook/fulfilment/grant through actual services. Never seed fake entitlements or import M2A auth/session data.

Real provider data comes later under its separate rights/diagnostics gate: exact supplier account/scope and approved article display/copy/test-use rights; narrow diagnostic request budget; private content/provenance handling; verified credential-free build; approved internal/external ingress/tester permissions. Do not fetch/copy provider data while rights remain unconfirmed.

## Decisions to carry into the post-merge implementation gate

Use M2A database workshop_owned_article_m2a and bucket workshop-owned-article-m2a-sources, fresh local-only material and a distinct accepted marker; no connection fallback or M1 cache/config/data writes. Existing immutable source may be read to compare helper mechanics, but the runtime mounts only its own final snapshot/binary.

Browser authority must be one exact loopback origin and GET /auth/session only. That one response is deliberately simulated and counted. Add synthetic local Bearer only to catalog paths at that same origin; no global extraHTTPHeaders. Reject redirects/external requests, block service workers/downloads, use a fresh profile and owned process cleanup. Assert all selectors/article/index/image responses came from the admitted actual Go API and match seeded PG/S3 hashes. Auth/config and purchase config remain real. Failed omitted-auth negative control must remain failed; no fake DB session or grant.

New gate should name the bounded system-Chromium launch probe, fixed browser/Python identities, at most one owned fictional configuration/article/image, seed idempotence and zero-commerce-row oracle. The initial synthetic text/image display uses legacy local catalog projection intentionally; it does not claim canonical provider capture, rewrite, payment or entitlement lifecycle coverage. Real provider/canonical/paid acceptance has a separate source/rights/diagnostics gate.

## Coordinator working assumption for a later external stage

For repeat external testers, the working ingress is a stable dedicated TEST subdomain through a named tunnel/DNS, for example staging.cars.tk, with the exact hostname authorized in the separate Firebase test project. A random Quick Tunnel hostname is suitable only for one separately bounded rehearsal; it changes on restart and is not the recurring tester ingress. No DNS/Firebase mutation before a concrete reviewed TEST-stage gate. This is not authority to expose empty/local-auth M1 or M2A fixture/auth simulation, and does not establish licensed-article display rights. Keep the owned fixture project isolated from every later external stage. Stable DNS/named-tunnel credentials and exact origin/authorized-domain/webhook inputs remain external-stage prerequisites.

## Verified local-auth prerequisite

Private in-memory Go probe on exact f03816e1e7352ac948ffe1a217f6f0928c3e1e9e passed using the actual HeaderAuthenticator, requireRole, catalog handlers and opaque image handler. Exact synthetic local token with a UUID organization: selectors/index/detail200; omitted token401; wrong role403. Valid generated PNG through opaque image handler200 with or without Bearer; invalid opaque reference404. Customer /auth/session401 with or without Bearer is a separate cookie-service rule, not a hidden catalog entitlement gate. This probe uses an in-memory catalog and image-reader double; it is not PG/S3/browser proof. The initial non-PNG image double was correctly rejected; generated valid PNG passed. Receipt /home/corp/autodata-workshop-auth-probe-20261115/receipt.json is private0600.

Before any M2 fixture seed or browser shim, start the newly admitted EMPTY M2 runtime and verify exact local token against actual selector/index/detail routes, distinguishing401/403 from not-found data responses. Verify signed image-reference behavior and dependency-backed readiness. Any mismatch stops the gate before inserting data. Scope the browser Bearer shim to selectors/article catalog requests only; opaque image requests rely on their signed reference and real local S3 bytes, not a customer session or seeded grant.

Capacity note: the independent offline auth-probe source/module/build caches occupy1,518,682,112bytes; measured afterward home free8,652,828,672bytes and Docker free1,006,952,448bytes. Those are snapshots, not admission proof. The next gate may explicitly reuse the independent auth-probe Go module/build caches for host compilation (outside every runtime bind), preserving M1 caches/state, rather than materializing a third module tree. Re-measure before preparation/startup and retain the full reserve/abort policy.

M2B handoff: coordinator verified historical boolean receipts under /home/corp/autodata-evidence/stripe-test-2026-11-06/ for genuine isolated Stripe TEST Checkout, signed settlement, grant, full refund/revocation and cleanup. Historical lower-level evidence only; not current Firebase/browser/stable-origin acceptance. Reuse it to avoid unjustified duplicate payment-plumbing tests. M2A remains article-only and does not read or use those credentials/data.

## Exact implementation allowlist
- infra/compose/compose.workshop-owned-article.yaml
- scripts/dev/workshop_owned_article_admission.py
- scripts/dev/test_workshop_owned_article_admission.py
- scripts/dev/workshop_owned_article_forwarder.py
- scripts/dev/test_workshop_owned_article_forwarder.py
- scripts/dev/workshop_owned_article_seed.py
- scripts/dev/test_workshop_owned_article_seed.py
- scripts/dev/workshop_owned_article_smoke.py
- scripts/dev/test_workshop_owned_article_smoke.py
- scripts/dev/fixtures/workshop_owned_article/article.json
- scripts/dev/fixtures/workshop_owned_article/diagram.png
- docs/operations/workshop-owned-article-m2a.md
- docs/verification/2026-11-15-workshop-owned-article-m2a.md

## Todo
- Add independent fixed-profile admission/relay and red-first authored seed/browser boundary tests without changing five M1 files
- Pin source/image/binary/browser identities, prove bounded default-sandbox browser launch and obtain root review before Docker startup
- Boot fresh empty M2A on loopback3042, verify actual auth gates before one authored article/image seed, keep all customer/payment/grant rows zero
- Exercise desktop and narrow mobile selector/index/detail/image through real PG/S3, verify screenshot/no clipping/console errors/back/reload, stop owned resources and hold PR/merge for root

## Binding acceptance and lifecycle

Gate/Issue/Project/ops/record must synchronize at a docs-only checkpoint and exact machine preflight must pass before implementation. Fresh independent fixed copies preserve five M1 files and every M1 private artifact/resource/cache. Source/config/archive/binary/image pins,0700 root/0600 private files, physical-home/no-symlink/storage identity, actual ownership/ENV/image-volume/security policy and relay lifecycle/source/engine/lock guards are inherited under the new explicit namespace. M2A database workshop_owned_article_m2a and bucket workshop-owned-article-m2a-sources. Fresh local-only material; no endpoint fallback.

Default-sandbox system-browser bounded launch is prerequisite before Docker or seed. Browser/dependency failure stops for review; no unreviewed install or sandbox weakening. Root reviews committed immutable implementation/non-Docker admission before first Compose up. PG/NATS/S3/migration/private/API transitions each require admission and actual policy before accepted marker advances. Actual empty auth/readiness checks precede seed. Partial seed failure stops/preserves for review; no reset/delete/adoption.

Desktop1440x1000 and narrow mobile390x844 each cover selector→index→detail→image, back and reload/deep-link, authored text/step order, PNG hash/MIME/natural64x48 and visible box. Screenshots, no horizontal clipping and no console/page errors. Both use the same single exact-origin GET /auth/session simulation; no catalog/article/image/config/static fulfilment. Auth shim count and authentic response hashes must be evidenced. All account/session/checkout/order/payment/entitlement counts remain zero; migration040 product metadata1 permitted.

Retain Docker512MiB floor plus128MiB startup/72MiB logs/64MiB growth and home2GiB reserve with measured budgets/inodes. Six cached immutable images/RO roots/cap-drop/memory/CPU/log/tmpfs contracts inherit reviewed M1 with only namespace/port/store changes; explicit inherited credential blanking/internal isolation is permitted only for this private authored fixture, never external. No Docker build/pull.

Stop exact owned browser/relay/M2A services, preserve state, verify listener absent/no attachments and M1 unchanged. No public exposure, provider/model/Stripe/Firebase calls, fake payments/grants, PR/merge without root review. Defer expensive exact-head CI until latest protected SHA is coordinated; if PR427 lands first, create a fresh synchronized integration checkpoint/preflight before source integration.


## Protected combined UI integration checkpoint (2026-11-15 UTC)

Protected source f534d0aeb76973ca3b8c70b14c806973edb1b457/tree902287299c37c49ebb3cae2245303e0c95100e90 includes PR432 and dependent PR435. The previous ebedbc18 package remains held, unstarted and unseeded; preserve its private physical receipt and immutable pins before replacing only source/archive/binary/config at the independent M2A root. All four stores must remain empty through the next root review. M1 is unchanged.

After this docs-only checkpoint and exact preflight, copy the reviewed M2A implementation/fixture blobs and make only these allowlisted red-first corrections: require real auth/config mode local and disabled purchase-config before browser simulation; reject every quote/prepare request; retain the original authored body-visible assertion and additionally require body once before both ordered step headings/instructions; permit read-only seed-helper inspect before the empty-auth receipt while keeping seeding gated by that receipt. Preserve authoritative real PG/S3 responses, single exact-origin auth/session fulfillment and negative unauthenticated session401 classification. No product/UI edits.

Use the installed matching Node Playwright1.62.1/core1.62.1 with pinned system Chromium and chromiumSandbox:true, short private temporary directory, no install or flags weakening sandbox. Python Playwright1.55 lacks its driver and is not used. Re-pin package/runtime hashes and prove a bounded data-only launch. Rebuild the embedded Go binary from this exact final implementation snapshot with the independent existing auth-probe cache, offline modules and bounded capacity watchdog; no Docker image build/pull. Pin fresh source/tree/archive/binary/rendered config and physical storage identities. Obtain root review of the committed exact package/admission before Docker startup, empty auth checks, seed or application browser acceptance.

The old expected disabled-quote503 exception is superseded by protected PR432: zero quote and zero prepare requests are required. Missing simulated auth may still produce the explicit negative-control auth/session401; every other console/page/resource failure remains blocking. The original fixture body must be visible and must not be altered to hide omission. Seed read-only inspect may precede the empty-auth receipt only under full actual-resource admission; writes still require that receipt.

Capacity is measured, never assumed: retain Docker813694976 bytes and home7046430720 bytes plus inode floor1000. Preserve old pins within this budget, cap additional warm build growth at256MiB and abort the compiler process group before home reaches the full floor plus128MiB. No cache pruning or old-state reset. Root reviews the immutable source/archive/binary/config/manifest, tests and physical/capacity package before any M2A Docker mutation. Issue398 remains open; authored local display is not licensed provider/Firebase/payment acceptance.


## Browser diagnostics amendment (2026-11-15 UTC)

The bed88597 runtime passed six-service actual policy,42 migrations plus unchanged repeat, empty-auth/readiness, one authored six-row/two-object seed and exact repeat. First browser attempt failed before screenshots; the wrapper discarded the Node stable assertion code and partial counters. All six owned services and relay are stopped, attachments0, stores preserved. No retry before root review.

Todo: Preserve sanitized browser failure stage/code/counters/route statuses and private partial screenshot, reseal exact package and obtain root review before same-resource retry.

Allowlisted correction only in workshop_owned_article_smoke.py and its tests: strict stable error-code/stage allowlists, bounded counters and category/status aggregates, no response bodies/headers/URLs, private screenshot if a page exists when failure occurs. Preserve partial safe diagnostics through Python instead of replacing them with a generic error. Red-first synthetic failure tests must cover unsafe error text/stage rejection, counter/category/status bounds, receipt private modes and screenshot capture failure. Keep the sole session simulation, authentic PG/S3 responses, original body once/ordered steps, zero quote/prepare and no external authority unchanged. No product edits.

Rebuild/reseal immutable source/archive/binary/config/manifest within measured capacity, preserve the old exact package and historical receipts. Stopped actual resources/config and storage identities must match before only accepted-state.source_sha advances; do not let a receipt bless unexpected resources. The old seed/auth receipts retain their original source/binding. After independent root package review only: restart the same admitted resources in order, revalidate readiness and actual policy, perform read-only exact row/object readback against the historical fixture marker, and explicitly re-attest a provenance-linked seed receipt to the new source/accepted binding before retrying the browser. No fresh insert/reset/delete/upsert or fabricated empty-auth claim. Keep the successful historical first seed and empty-auth evidence intact.

Home reserve remains7046430720 bytes, warm-build abort threshold7180648448 bytes; Docker reserve813694976 bytes. Preserve immutable old archive/binary via same-filesystem links and replace source only with the exact new archive while stopped; retain the old full archive for reconstruction. Stop before a reserve breach. No runtime restart or browser retry until root reviews the complete new package.


## Evidence relocation and offloaded-build amendment

Todo: Add fixed held-ebed evidence relocation helper and owned fixture tests; permit reviewed offloaded fresh Go output/temp with physical active binary retained only on byte identity.

The original held-ebed-package is a completed historical immutable package, separate from all active M2A/M1 source/data/config and caches. Add only scripts/dev/workshop_owned_article_relocate.py and scripts/dev/test_workshop_owned_article_relocate.py to the implementation allowlist for a fixed-source/fixed-target helper. Runtime mutation is not authorized by this amendment. Root reviews exact helper/commands before copy, rename, cleanup or a local runtime restart.

Source is /home/corp/autodata-workshop-owned-article-data-20261115/held-ebed-package, physical ext4 device66315/root inode3038805. Target is /home/corp/autodata-evidence/local-staging-runtime-draft-20261115/held-ebed-package on mounted offloaded ext4 device1792. Pin private approved per-file and directory identity/content/mode inventory efdeac101b2e1c775a6361aa59ceef152e30a66b722aa5d2e2d2427d8a68ac54;1404 files/78 directories, no symlinks or multiply-linked files. The target remains evidence-only; no active runtime source/binary/data fallback. Preserve historical path-bearing receipts; append a relocation mapping receipt instead of editing them. Never move the v6 baseline/manual-classification evidence.

Commands are fixed plan/copy/cleanup with no user paths or env overrides. Plan reads only. Copy uses private pending directory, descriptor-relative no-follow opens, exact approved source inventory before/after, per-file hash/mode/size checks, file+directory fsync and atomic no-replace final rename on the target filesystem. The source remains unchanged. Cleanup is a separately reviewed command, requires a matching private copy receipt and complete final target rehash, revalidates exact source root inode/tree, atomically quarantines only that root then removes only the enumerated no-follow original entries. Reject extra/missing/changed/symlink/hardlink/cross-device/occupied target/lock conditions. Stop on any mismatch; do not broaden or recursively remove unverified paths. Private receipts are0600 and directories0700. Tests use wholly owned temporary trees; do not run copy/cleanup against real paths before root review.

Recalculate capacity using actual free bytes, including the retained v6 receipts. Current approximate home7.104GB is below build abort floor7.180648448GB. Reclaimable held package131403776bytes is only a projection until verified cleanup and fresh free-space readback. Original duplicate-binary workflow is still short after this single relocation; no assumed space authorizes work.

After separate root approval of operations, an allowed bounded alternative is fresh Go build from the immutable exact snapshot to a new private output and temporary directory on the evidence ext4 filesystem, with the independent auth-probe module/build caches unchanged in location and M1 caches untouched. Keep physical-home active binary only if fresh output SHA256 and byte comparison exactly match it; otherwise stop/preserve for review, do not install a differing build. New active source/archive/config/manifest remain physical-home and hash-admitted. Warm-build watcher still aborts at home7180648448bytes, growth256MiB and180s; require sufficient evidence and underlying backing-filesystem capacity too. Go/embed/module blobs are unchanged in this diagnostics amendment, but byte identity must be measured. No image build/pull, provider/Stripe/Firebase request or service startup under this helper gate.
