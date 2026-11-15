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
