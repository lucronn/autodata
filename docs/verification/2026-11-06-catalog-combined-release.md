# Combined catalog release verification

Status: deployed selector repair with successful three-year makes canary. The operator returned `RELEASE_INCOMPLETE` because its immediate worker-restoration check raced startup; a separate read-only check confirmed the original worker is active again. The residual Banktwo case-sensitive model/configuration issue is tracked under `docs/agents/records/2026-11-06-banktwo-selector-casing.json`.

Goal: Deploy the combined connector and sparse-selector fixes with migration 042, restore real dual-bank Workshop makes/models, and preserve protected article and commerce state with purchase disabled.

Plan: `docs/superpowers/plans/2026-11-06-catalog-combined-release.md`. Record: `docs/agents/records/2026-11-06-catalog-combined-release.json`. Canonical gate: `docs/agents/pre-implementation-gate.md`. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Dedicated field: `Catalog selector release reference`; exact saved external readbacks passed.

Read-only baseline: API source32373def… on18080 forwards to ingestion3031/container38f3bc41…/sourceb3618fb6…; continuous article worker source d18c9fed… is active. Serving DB has41 migrations, no042 columns; purchase disabled; canonical autodata.cars.tk readiness/workshop and private3031 health returned200. Exact immutable identities and constraints are recorded in the plan. No secret values are included.

Required receipts: exact combined merged source SHA/tree containing PR362+PR363; synchronized Issue/Project readback; committed checkpoint and errors[] exact-base preflight; independently reviewed operator-script hash; retained original service/configuration hashes; graceful worker quiescence; lightweight protected-count/job-status baseline/final equality;42-marker migration evidence with prior timestamps unchanged; ingestion/API paired source identity and bounded health;three2027/2014/2020 US makes scopes, durable/public counts and honest completeness under12 GETs/180seconds; purchase disabled; same-worker restoration; exact rollback outcome on failure.

Concrete todo:

- [x] Pin merged PR363 source containing the reviewed PR362 fix; synchronize this goal, plan, canonical verification and four todos with Issue186 and the dedicated Project8 field; commit/push the checkpoint and pass exact-base machine preflight before operational dispatch.
- [x] Freeze the current ingestion/API/continuous-worker identities and private rollback artifacts; gracefully stop the continuous worker, verify quiescence, capture lightweight protected-table counts with purchase disabled.
- [x] Apply the exact shared 042 migration runner, replace ingestion from the combined immutable source while retaining its original container, and replace the Go API with the same-source binary using bounded health checks and exact rollback on failure.
- [ ] Run only the bounded 2027/2014/2020 US makes canary, verify configured-bank completeness and durable public results with unchanged protected state, restore the same continuous-worker unit/configuration, and synchronize exact evidence or rollback outcome.

Deployment evidence (2026-11-07 UTC): merged PR #363 passed all required checks at its exact head; product SHA `27ac83f4b97421db3ef067eee60a12d21b8874d2` has the same full tree as the reviewed integration candidate. Gate checkpoint `af822832becf4f97e7d2d882801d7ec6b5c3442a` passed exact-base preflight with `status:synchronized` and `errors:[]`. Reviewed operator SHA256 `2305a59bf722797f7a0545bf611919c7457f6ecadd23916baa346a9dcd85dd1a` applied migration 042 and started ingestion/API from that product tree. Public `/readyz` returned all dependencies ready; purchase remained disabled.

Bounded public makes canary completed with both-bank durable provenance: 2027 returned 49 makes (from 6 before), 2014 returned 61 (from 0), and 2020 returned 59. Durable scoped rows were 49/62/60 respectively, completion version 1. The exact pre/post protected-table and article-job-status counts matched while the worker was stopped. The original continuous article worker is subsequently active under its unchanged `d18c9fed…` source, pinned image and mounts. The operator's receipt says `recovery_incomplete` solely because its immediate worker check failed; no service rollback ran. Keep that receipt as an incomplete automated result, not a clean operator pass.

Post-canary public 2020 Ford models exposed 29 options (from 9 before) but remained `complete:false` because Banktwo returned 404 for lowercase `ford`; the exact source spelling `Ford` returned nine rows. The same case-sensitive failure occurs for `Figo (MEXICO)` configurations. This is the next gated fix; the present release does not claim full model/engine or real-article acceptance. Fictional demo index and reader were verified separately in the live browser.

Product 27ac83f4b97421db3ef067eee60a12d21b8874d2; tree a8500ff151103fbc3b06259c3ea04ba544c129d2. Tracking receipt https://github.com/lucronn/autodata/issues/186#issuecomment-6701111042; synchronized 2026-11-07T02:36:44.150063Z.
