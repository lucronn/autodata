# Private authored article M2A operation

Goal: Prove private authored article and image display through real isolated PG/S3 and Go Workshop with explicit browser-only auth simulation.
Issue https://github.com/lucronn/autodata/issues/398; Project https://github.com/users/lucronn/projects/8.
Protectedf534d0aeb76973ca3b8c70b14c806973edb1b457/tree902287299c37c49ebb3cae2245303e0c95100e90.

Plan docs/superpowers/plans/2026-11-15-workshop-owned-article-m2a.md; record docs/agents/records/2026-11-15-workshop-owned-article-m2a.json.
Status: planning synchronized, implementation/runtime pending. Independent root/project/internal network and loopback3042; authored fixture only; browser auth explicitly simulated; actual PG/S3 article/image responses. M1 unchanged.

Todo:
- Add independent fixed-profile admission/relay and red-first authored seed/browser boundary tests without changing five M1 files
- Pin source/image/binary/browser identities, prove bounded default-sandbox browser launch and obtain root review before Docker startup
- Boot fresh empty M2A on loopback3042, verify actual auth gates before one authored article/image seed, keep all customer/payment/grant rows zero
- Exercise desktop and narrow mobile selector/index/detail/image through real PG/S3, verify screenshot/no clipping/console errors/back/reload, stop owned resources and hold PR/merge for root

Exact topology/pins/limits/browser/auth/seed contract, per-phase admission/root review and stop-only rollback are in the plan. No external exposure or provider/payment acceptance.

Implementation preparation: independent profile copies retain M1 security/ENV/lifecycle mechanics with only fixed namespace/store/listener substitutions. The authored seed writes exactly six rows (source_snapshots, extraction_evidence, vehicles, vehicle_identity_bases, vehicle_configurations, catalog_articles). All other public operational tables remain zero; one migration bootstrap dataset_products row is permitted. The truthful source snapshot points to owned-fixture/article.json (application/json); its JSON includes the generated PNG hash. The second object is procedure-images/<PNG SHA256> (image/png). Seed readback compares inserted columns and both actual S3 byte hashes/MIME/object keys; repeat requires the exact source/fixture marker, rows and two objects. No payment/customer/grant insertion or reset/delete/upsert.

Browser prerequisite resolution: distro Python Playwright1.55.0+ds is incomplete (missing driver). The already-installed matching Node Playwright and playwright-core1.62.1 API/driver pair passes an isolated about:blank launch with chromiumSandbox:true and system Chromium145.0.7632.159. No installation/download or sandbox relaxation. The helper pins both full package trees, Node, Python, Chromium wrapper/ELF and setuid sandbox hashes. A short0700 temporary home avoids Chromium Unix socket path limits; screenshot/receipt files remain private. The broken Python driver is not used.

The browser changes only exact-origin GET /auth/session, recording every simulation. Synthetic local Bearer applies only to real selectors/article catalog requests, never images or another origin. Images retain real signed opaque capability handling. Catalog/article/image/config/static responses are never fulfilled. Desktop1440x1000/mobile390x844 check one article/image, text/steps, actual image hash/MIME/dimensions, no clipping, back/reload and screenshots; separate unshimmed browser control must remain unable to read. Node child environment excludes ambient credentials/proxy/Node settings and downloads/service workers are blocked.

Coordinator-approved console accounting preserves exact native HTTP failures from real disabled quote503 and unshimmed negative-control session401 separately. Require zero JavaScript console/page errors and zero unexpected resource failures. Do not describe expected resource denials as zero total console events. No quote response simulation or application behavior change. This may support a separately gated UI follow-up to suppress quote reads when purchasing is disabled.

Before first Docker start, send exact committed implementation/source/tree, safe rendered topology/full admission/test/package pins and measured capacity for root review. Subsequent runtime phases and empty actual auth/readiness proof precede seed. Seed/partial/browser failure preserves data for review. M1 runtime/source/cache/receipts stay unchanged. Final integration awaits coordinator's latest protected code base and a fresh checkpoint if it advances; no expensive PR CI yet.


## Protected combined UI integration checkpoint (2026-11-15 UTC)

Protected source f534d0aeb76973ca3b8c70b14c806973edb1b457/tree902287299c37c49ebb3cae2245303e0c95100e90 includes PR432 and dependent PR435. The previous ebedbc18 package remains held, unstarted and unseeded; preserve its private physical receipt and immutable pins before replacing only source/archive/binary/config at the independent M2A root. All four stores must remain empty through the next root review. M1 is unchanged.

After this docs-only checkpoint and exact preflight, copy the reviewed M2A implementation/fixture blobs and make only these allowlisted red-first corrections: require real auth/config mode local and disabled purchase-config before browser simulation; reject every quote/prepare request; retain the original authored body-visible assertion and additionally require body once before both ordered step headings/instructions; permit read-only seed-helper inspect before the empty-auth receipt while keeping seeding gated by that receipt. Preserve authoritative real PG/S3 responses, single exact-origin auth/session fulfillment and negative unauthenticated session401 classification. No product/UI edits.

Use the installed matching Node Playwright1.62.1/core1.62.1 with pinned system Chromium and chromiumSandbox:true, short private temporary directory, no install or flags weakening sandbox. Python Playwright1.55 lacks its driver and is not used. Re-pin package/runtime hashes and prove a bounded data-only launch. Rebuild the embedded Go binary from this exact final implementation snapshot with the independent existing auth-probe cache, offline modules and bounded capacity watchdog; no Docker image build/pull. Pin fresh source/tree/archive/binary/rendered config and physical storage identities. Obtain root review of the committed exact package/admission before Docker startup, empty auth checks, seed or application browser acceptance.

The old expected disabled-quote503 exception is superseded by protected PR432: zero quote and zero prepare requests are required. Missing simulated auth may still produce the explicit negative-control auth/session401; every other console/page/resource failure remains blocking. The original fixture body must be visible and must not be altered to hide omission. Seed read-only inspect may precede the empty-auth receipt only under full actual-resource admission; writes still require that receipt.

Capacity is measured, never assumed: retain Docker813694976 bytes and home7046430720 bytes plus inode floor1000. Preserve old pins within this budget, cap additional warm build growth at256MiB and abort the compiler process group before home reaches the full floor plus128MiB. No cache pruning or old-state reset. Root reviews the immutable source/archive/binary/config/manifest, tests and physical/capacity package before any M2A Docker mutation. Issue398 remains open; authored local display is not licensed provider/Firebase/payment acceptance.


Integration implementation checks:50 M2A tests,33 M1 tests and3 Compose image tests pass on the protected combined UI integration. Seed-helper read-only inspect may precede the empty-auth receipt under full resource admission; writes retain the exact receipt gate. Browser prerequisites verify real auth/config local and purchase configuration disabled before the single simulated session response. The original authored body must appear once before ordered headings/instructions; all quote and prepare attempts are errors. Old expected quote503 is no longer accepted. No application startup/seed/acceptance is authorized until root reviews the fresh immutable physical package.


## Browser diagnostics amendment (2026-11-15 UTC)

The bed88597 runtime passed six-service actual policy,42 migrations plus unchanged repeat, empty-auth/readiness, one authored six-row/two-object seed and exact repeat. First browser attempt failed before screenshots; the wrapper discarded the Node stable assertion code and partial counters. All six owned services and relay are stopped, attachments0, stores preserved. No retry before root review.

Todo: Preserve sanitized browser failure stage/code/counters/route statuses and private partial screenshot, reseal exact package and obtain root review before same-resource retry.

Allowlisted correction only in workshop_owned_article_smoke.py and its tests: strict stable error-code/stage allowlists, bounded counters and category/status aggregates, no response bodies/headers/URLs, private screenshot if a page exists when failure occurs. Preserve partial safe diagnostics through Python instead of replacing them with a generic error. Red-first synthetic failure tests must cover unsafe error text/stage rejection, counter/category/status bounds, receipt private modes and screenshot capture failure. Keep the sole session simulation, authentic PG/S3 responses, original body once/ordered steps, zero quote/prepare and no external authority unchanged. No product edits.

Rebuild/reseal immutable source/archive/binary/config/manifest within measured capacity, preserve the old exact package and historical receipts. Stopped actual resources/config and storage identities must match before only accepted-state.source_sha advances; do not let a receipt bless unexpected resources. The old seed/auth receipts retain their original source/binding. After independent root package review only: restart the same admitted resources in order, revalidate readiness and actual policy, perform read-only exact row/object readback against the historical fixture marker, and explicitly re-attest a provenance-linked seed receipt to the new source/accepted binding before retrying the browser. No fresh insert/reset/delete/upsert or fabricated empty-auth claim. Keep the successful historical first seed and empty-auth evidence intact.

Home reserve remains7046430720 bytes, warm-build abort threshold7180648448 bytes; Docker reserve813694976 bytes. Preserve immutable old archive/binary via same-filesystem links and replace source only with the exact new archive while stopped; retain the old full archive for reconstruction. Stop before a reserve breach. No runtime restart or browser retry until root reviews the complete new package.


Current hold: first bed88597 actual six-resource/empty-auth/readiness/migration-repeat/authored-seed-repeat phases passed; first browser attempt failed without retained assertion detail. All M2A services/relay stopped with stores preserved. Diagnostics amendment checkpoint97658484 passed preflight;54 M2A tests now pass. New failure receipts contain only allowlisted code/stage, bounded counters and route-category/status summaries; partial failure screenshot is private. Retry output uses separate browser-diagnostics-retry directory, preserving the first browser directory/evidence. Obtain independent new-package review before same-resource restart/read-only fixture re-attestation and browser retry. Do not rerun first-seed writes or fabricate a new empty-auth receipt for populated stores.


## Evidence relocation and offloaded-build amendment

Todo: Add fixed held-ebed evidence relocation helper and owned fixture tests; permit reviewed offloaded fresh Go output/temp with physical active binary retained only on byte identity.

The original held-ebed-package is a completed historical immutable package, separate from all active M2A/M1 source/data/config and caches. Add only scripts/dev/workshop_owned_article_relocate.py and scripts/dev/test_workshop_owned_article_relocate.py to the implementation allowlist for a fixed-source/fixed-target helper. Runtime mutation is not authorized by this amendment. Root reviews exact helper/commands before copy, rename, cleanup or a local runtime restart.

Source is /home/corp/autodata-workshop-owned-article-data-20261115/held-ebed-package, physical ext4 device66315/root inode3038805. Target is /home/corp/autodata-evidence/local-staging-runtime-draft-20261115/held-ebed-package on mounted offloaded ext4 device1792. Pin private approved per-file and directory identity/content/mode inventory efdeac101b2e1c775a6361aa59ceef152e30a66b722aa5d2e2d2427d8a68ac54;1404 files/78 directories, no symlinks or multiply-linked files. The target remains evidence-only; no active runtime source/binary/data fallback. Preserve historical path-bearing receipts; append a relocation mapping receipt instead of editing them. Never move the v6 baseline/manual-classification evidence.

Commands are fixed plan/copy/cleanup with no user paths or env overrides. Plan reads only. Copy uses private pending directory, descriptor-relative no-follow opens, exact approved source inventory before/after, per-file hash/mode/size checks, file+directory fsync and atomic no-replace final rename on the target filesystem. The source remains unchanged. Cleanup is a separately reviewed command, requires a matching private copy receipt and complete final target rehash, revalidates exact source root inode/tree, atomically quarantines only that root then removes only the enumerated no-follow original entries. Reject extra/missing/changed/symlink/hardlink/cross-device/occupied target/lock conditions. Stop on any mismatch; do not broaden or recursively remove unverified paths. Private receipts are0600 and directories0700. Tests use wholly owned temporary trees; do not run copy/cleanup against real paths before root review.

Recalculate capacity using actual free bytes, including the retained v6 receipts. Current approximate home7.104GB is below build abort floor7.180648448GB. Reclaimable held package131403776bytes is only a projection until verified cleanup and fresh free-space readback. Original duplicate-binary workflow is still short after this single relocation; no assumed space authorizes work.

After separate root approval of operations, an allowed bounded alternative is fresh Go build from the immutable exact snapshot to a new private output and temporary directory on the evidence ext4 filesystem, with the independent auth-probe module/build caches unchanged in location and M1 caches untouched. Keep physical-home active binary only if fresh output SHA256 and byte comparison exactly match it; otherwise stop/preserve for review, do not install a differing build. New active source/archive/config/manifest remain physical-home and hash-admitted. Warm-build watcher still aborts at home7180648448bytes, growth256MiB and180s; require sufficient evidence and underlying backing-filesystem capacity too. Go/embed/module blobs are unchanged in this diagnostics amendment, but byte identity must be measured. No image build/pull, provider/Stripe/Firebase request or service startup under this helper gate.


Relocation review commands from the integration worktree: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 scripts/dev/workshop_owned_article_relocate.py plan (read-only, already passed); the same fixed command with copy then separately cleanup is proposed for root review only. Neither mutation command has run. The helper accepts no source/target/env overrides. No active runtime/data/cache operations exist in it.

Offloaded build proposal after reviewed relocation and fresh capacity: create private0700 evidence/m2a-diagnostics-build with bin/tmp children; compile from the exact newly sealed physical runtime source using existing independent auth-probe module/build caches, GOPROXY offline, CGO_ENABLED0/GOTOOLCHAINlocal/GOMAXPROCS2/-mod=readonly/-trimpath/-buildvcs=false, with output and GOTMPDIR in that evidence child. Watch home7180648448bytes floor,256MiB growth and180s, plus evidence/backing capacity. Verify fresh output SHA256 and streaming byte equality against the existing physical active binary. Retain that active binary only on exact identity; stop/preserve if different. Source/archive/config/manifest remain physical-home; evidence build output is never a runtime bind/fallback. Projected post-relocation margin above build-abort is only about53MB; new physical archive consumes about34MB, so compiler cache growth must remain within the measured remainder or the watcher aborts. Do not assume projected reclamation or warm-cache behavior.


## Reviewed archive mapping and diagnostics reseal checkpoint

Root separately reviewed/ran historical held-ebed copy, independent target hash readback and exact scoped cleanup. This lane independently reread all1404 final target files and approved content/modes; old source is absent. Historical package is now /home/corp/autodata-evidence/local-staging-runtime-draft-20261115/held-ebed-package. Copy receipt SHA256851cf15c0f7e322ed3fa09c6ab03eb210bdc3f0350c9b521474406e0ee9cdd01; cleanup receipt SHA2566ebc257054aefddbed33d45b70c0dbb99f1d6bc0a4c5d7d2fe140a5da28291bb. Preserve historical original-path receipts and append this mapping; no runtime fallback to archived evidence.

Root also reports reviewed independent v6 baseline archival; that evidence/manual receipt and running candidate are owned by its lane and are not modified here. Actual measured physical-home free7412940800bytes includes the current retained usage; Docker1005162496bytes, offloaded evidence12647514112bytes. Those are snapshots only; no projected cleanup gain is counted. Active M2A bed88597 archive d161acbe5eaa45d1401cb6606454307a196580718d85614a31edfc095139bb22 and binary cfb7828a592bb416942cb5f544addf195037f959958dc68f0809b1dfef45c78d remain unchanged before reseal; all six M2A services stopped.

After this synchronized docs checkpoint/preflight, reseal the exact committed diagnostics snapshot on physical-home source/archive. Preserve the bed88597 archive/binary/manifest/accepted/seed/auth receipts; update source files only from the exact new archive while stopped, no duplicate complete tree. Build fresh Go output and compiler temp in private0700 evidence/m2a-diagnostics-build using the already reviewed independent caches, never M1 caches or cache cleanup. Monitor actual home/build/output/backing floors; require SHA256 plus streaming byte identity with the physical active binary before retaining it unchanged. Mismatch stops for review. Re-render fixed config and verify all stopped actual identities/policy/storage before advancing only accepted-state.source_sha. Historical empty-auth and seed receipts remain byte-identical until explicit later read-only re-attestation under reviewed restart. Deliver fresh archive/binary/config/manifest/physical capacity receipt for root review before any M2A restart or browser retry. No provider/Stripe/Firebase/public action.

Todo: Build/reseal exact diagnostics source using reviewed offloaded output/temp, retain physical binary only on fresh hash+byte identity; verify stopped resource/storage policy and deliver complete package for root review before runtime restart/browser retry.


## Protected image-contract acceptance gate

Pinned protected source `a82b31dc8850aa3956972928b8c720969765a972` / tree `11503a735d7d983ca3ebf090b471c89682e77278`. Plan `docs/superpowers/plans/2026-11-15-workshop-owned-article-image-contract-acceptance.md`; synchronized record `docs/agents/records/2026-11-15-workshop-owned-article-image-contract-acceptance.json`; Issue398/Project8 stay In Progress. Preserve original authored body and first-step image reference, six data rows/two objects and all prior failed receipts.

Todo: Integrate exact reviewed M2A fixture and isolation helpers on protected a82b31dc, preserve historical evidence and add exclusive third-attempt browser outputs/one-use guard with red-first tests.

Todo: Build and reseal immutable source/archive/new embedded-UI Go binary using offloaded temp/output, 128MiB maximum incremental physical-home growth and live warm-floor abort; verify stopped actual identities/config/fixture and deliver package to root before services or browser.

Todo: After separate root package and one-run approval, restart the same six services under per-phase admission, verify real served asset hashes and read-only six-row/two-object provenance, run exactly one authored desktop/mobile PNG/body/order/history acceptance, re-attest zero commerce/jobs and stop owned resources.

The next package embeds PR439 local-only image token fix, retains all fixed topology/config/image policy and unchanged fixed isolation policy. Offload compiler temp/output; maximum incremental physical-home growth128MiB with live warm-floor abort. This replaces prior256MiB proposal for this run only. Root reviews exact source/tree/archive/new binary/asset hashes, capacity and stopped full admission before any service/browser action. Use fresh exclusive phase/browser paths; no historical receipt overwrites. Current physical fixture data is populated, so only read-only re-attestation is allowed. No provider/Stripe/Firebase/public exposure.

Capacity amendment before implementation: root released physical package/build preparation only with total incremental physical-home cap134217728bytes (128MiB), entry free at least7314866176bytes and live abort7180648448bytes; service/browser hold remains. This supersedes the earlier160MiB proposal and generic approximately150MB discussion. No old343 mutation.


## Host-only tmpfs v2 gate

Plan `docs/superpowers/plans/2026-11-15-workshop-owned-article-tmpfs-browser.md`; record `docs/agents/records/2026-11-15-workshop-owned-article-tmpfs-browser.json`. Physical runtime668d/041farchive/bb11binary/da5353manifest and oldcfb mapping remain unchanged. Only offloaded smoke harness+test may change; root reviews separate operational identity before any services/browser. New physical baseline7270658048,64MiB cap/32MiB early guard; independent tmpfs128MiB cap/96MiB guard, memory/floor checks. Preserve all consumed markers/failures/data.

Todo: Keep immutable physical serving source/archive/binary/manifest and rollback binary mapping unchanged; separately pin the offloaded harness and immutable physical helper imports with no-dispatch boundary/hash-drift tests.

Todo: Use verified tmpfs private HOME/TMPDIR/XDG_CACHE_HOME, fresh current-baseline64MiB physical cap with32MiB early guard and independent tmpfs128MiB cap/96MiB guard, memory/floor checks and observed10MB burst regression.

Todo: Add exclusive v2 one-use marker and bounded durable safe stage/category/status journal, run focused offline tests and seal exact new host harness/operational receipt for root review before service or browser actions.

Todo: Only after separate root authorization restart the exact six resources, re-attest data read-only, run one authored desktop/mobile PNG/body/order/history/auth acceptance, preserve diagnostics and stop all owned processes/resources.

