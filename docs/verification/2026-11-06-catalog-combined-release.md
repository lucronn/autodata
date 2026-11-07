# Combined catalog release verification

Status: tracking synchronized; product pinned; checkpoint commit/push, exact-base preflight, final operator review and root dispatch remain required. No runtime execution.

Goal: Deploy the combined connector and sparse-selector fixes with migration 042, restore real dual-bank Workshop makes/models, and preserve protected article and commerce state with purchase disabled.

Plan: `docs/superpowers/plans/2026-11-06-catalog-combined-release.md`. Record: `docs/agents/records/2026-11-06-catalog-combined-release.json`. Canonical gate: `docs/agents/pre-implementation-gate.md`. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Dedicated field: `Catalog selector release reference`; exact saved external readbacks passed.

Read-only baseline: API source32373def… on18080 forwards to ingestion3031/container38f3bc41…/sourceb3618fb6…; continuous article worker source d18c9fed… is active. Serving DB has41 migrations, no042 columns; purchase disabled; canonical autodata.cars.tk readiness/workshop and private3031 health returned200. Exact immutable identities and constraints are recorded in the plan. No secret values are included.

Required receipts: exact combined merged source SHA/tree containing PR362+PR363; synchronized Issue/Project readback; committed checkpoint and errors[] exact-base preflight; independently reviewed operator-script hash; retained original service/configuration hashes; graceful worker quiescence; lightweight protected-count/job-status baseline/final equality;42-marker migration evidence with prior timestamps unchanged; ingestion/API paired source identity and bounded health;three2027/2014/2020 US makes scopes, durable/public counts and honest completeness under12 GETs/180seconds; purchase disabled; same-worker restoration; exact rollback outcome on failure.

Concrete todo:

- [ ] Pin merged PR363 source containing the reviewed PR362 fix; synchronize this goal, plan, canonical verification and four todos with Issue186 and the dedicated Project8 field; commit/push the checkpoint and pass exact-base machine preflight before operational dispatch.
- [ ] Freeze the current ingestion/API/continuous-worker identities and private rollback artifacts; gracefully stop the continuous worker, verify quiescence, capture lightweight protected-table counts with purchase disabled.
- [ ] Apply the exact shared 042 migration runner, replace ingestion from the combined immutable source while retaining its original container, and replace the Go API with the same-source binary using bounded health checks and exact rollback on failure.
- [ ] Run only the bounded 2027/2014/2020 US makes canary, verify configured-bank completeness and durable public results with unchanged protected state, restore the same continuous-worker unit/configuration, and synchronize exact evidence or rollback outcome.

No deployment, migration, selector/provider/article/model/payment dispatch, integration, restore test or full catalog/article/paid acceptance is claimed by this draft.

Product 27ac83f4b97421db3ef067eee60a12d21b8874d2; tree a8500ff151103fbc3b06259c3ea04ba544c129d2. Tracking receipt https://github.com/lucronn/autodata/issues/186#issuecomment-6701111042; synchronized 2026-11-07T02:36:44.150063Z.
