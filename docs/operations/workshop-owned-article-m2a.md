# Private authored article M2A operation

Goal: Prove private authored article and image display through real isolated PG/S3 and Go Workshop with explicit browser-only auth simulation.
Issue https://github.com/lucronn/autodata/issues/398; Project https://github.com/users/lucronn/projects/8.
Protected4048f3fae50161af5b5ab8300670e3beb817ce1a/treea1aa86183a2e015e74565fd939a70b3eb96010b1.

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
