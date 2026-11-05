# Workshop navigation recovery

Synchronized planning amendment to [customer UI](../superpowers/plans/2026-11-03-workshop-customer-ui.md), based on inspected SHA `3578d981942092ecc738a3ea7bc1776cefddd9b6`. [Issue186](https://github.com/lucronn/autodata/issues/186), [Project8](https://github.com/users/lucronn/projects/8), [bounded plan](../superpowers/plans/2026-11-03-workshop-navigation-recovery.md) and [task/record](../agents/tasks/2026-11-03-production-release/2026-11-03-workshop-navigation-recovery.json) were synchronized by the coordinator with Issue186 comment https://github.com/lucronn/autodata/issues/186#issuecomment-6616750128 and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` (In Progress). The committed checkpoint still requires exact-SHA preflight and independent coordinator review before implementation.

Goal: Prevent stale source-review failures from changing a newer selection and restore the requested Workshop library, article or order route after successful Google sign-in.

A source-review operation owns the navigation generation captured at activation. Its error callback must use that same generation; aborts and late401/403/410 from an older selection cannot update status or clear the newer selection. Current-generation denial keeps the existing protected-data clearing behavior.

After successful explicit Google login, resume the current validated route through existing `restoreRoute`: order return has precedence, then My vehicles, then configuration/article or selector route. Preserve the requested article ID and ignore prior in-memory vehicle state when the route selects the library. Failed/canceled login does not restore or initiate checkout. Route restoration may perform the existing authorized article prepare/read; it never initiates checkout or another popup.

Only `apps/api-go/workshop/app.mjs` and `apps/api-go/workshop-client.test.mjs` are implementation-owned. Keep the browser response-loss fixture repair separate. Preserve all40 DTO scenarios across3 engines (120 cases),7 real-API cases across3 engines (21 cases), backend dependencies and frozen acceptance/receipt requirements. Deterministic unit tests do not substitute for final integrated browser acceptance.

## Concrete todo

- [ ] Synchronize Issue186/Project8, this plan, canonical navigation-recovery document and task record; commit the checkpoint, pass exact-base preflight and obtain coordinator approval before implementation.
- [ ] Add failing regressions executing the real source-load click closure after navigation A to B; capture the original generation so stale abort/auth/rights errors cannot change B, while current-generation denials still clear protected state.
- [ ] Add failing regressions executing the real signIn and restoreRoute functions; resume library, saved article and order routes after successful sign-in without checkout replay, and retain canceled/failed-sign-in behavior.
- [ ] Run all Workshop Node tests, JavaScript syntax and scope/diff checks; commit/push two coherent validated milestones and obtain independent exact-candidate review.
- [ ] Coordinator integrates the reviewed UI fix separately from browser response-loss repair, then reruns unchanged120 DTO and21 real-API browser inventories at one immutable integrated SHA with frozen acceptance inputs and independently inspected receipts.
