# Identity session probe correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Independent coordinator gate review is required before implementation.

**Goal:** Correct the identity integration test to observe authenticated session revocation through the existing protected session endpoint.

**Architecture:** Replace the stale public selector probe with GET /auth/session inside the existing real HTTP/official Firebase SDK/PostgreSQL scenario. Retain all exact status expectations and all five integration subtests; application behavior and frozen acceptance collectors remain unchanged.

**Tech Stack:** Go 1.26, net/http/httptest, official Firebase Admin SDK, PostgreSQL, existing frozen identity5 supervisor.

**Spec:** docs/verification/2026-11-03-firebase-customer-identity.md

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Source integration base: `97511fc2c50f8e9dffbd15a1549298b94fc6b761`
Branch: `codex/identity-session-probe-gate`

## Global Constraints

- Sol6.1 medium Fast/priority, no fallback; isolated worktree and one implementation path only.
- No application authorization, selector visibility, cookie/session behavior, PostgreSQL, migration039, paid entitlement, UI, collectors, supervisor or frozen-image input change.
- Builder runs no Docker or provider/cloud/deploy command. Coordinator serializes Docker acceptance and retains all failed evidence.
- This planning checkpoint requires pinned passing preflight plus independent coordinator review before any implementation edit. Unit checks and historical passes do not establish current release readiness.

## Proven failure and data flow

Exact-head identity acceptance at `/tmp/autodata-identity-final-97511fc-1/artifacts/acceptance-result.json` failed at `97511fc2c50f8e9dffbd15a1549298b94fc6b761`: supervisor exit1, no timeout/OOM; raw Go events show four passing subtests and `FirebaseExchangeAndUserRevocation` failed at auth_http_test.go:270, `old cookie survived rotation 200`. The enclosing pytest has56 passed/1 failed plus7 subtests; the receipt's all-false scenario flags reflect failed suite validation and must not replace raw-event interpretation. Retain the entire directory unchanged.

The two successful exchanges return204. exchangeSession extracts the old cookie hash and passes it to postgresCustomerSessions.Rotate; Rotate updates revoked_at and inserts the new hash atomically before commit. Retained `r5-access-migration-rows.json` has one active fixture-user account with exactly two sessions: `78060c4d5faa474c2694945ea31c8ef25411c14ff1381783d0d48c11144f9ace` has revoked_at `2026-11-03 23:55:08+00:00`; `d9db67ca86e8e8c446bb3949131bb707a1df7b6f869f2a372274e7489557c307` is unrevoked. Lookup excludes revoked rows. Thus the observed200 does not establish surviving auth.

At main.go:240, GET /v1/catalog/years uses catalogSelector; Firebase mode enables the paid catalog boundary and catalogSelector invokes the handler without Authenticate. Commit43ec0e08bf67c97176ae1aee280db557ffc14263 deliberately made selectors public. Pre-change `d2eb70fa9b96fcebe1c33ef6cddcdad5c4a5eec7` identity5 passed because this route still required dataset_viewer. Commit`bf8527cfe65f5fad97a41ff71d7c2c9fd7373c8f` corrected the same stale assumption in main_test.go, leaving this helper unchanged.

GET /auth/session is already mounted by the actual API Handler. currentSession calls s.session(r,true), which parses the cookie, performs PostgreSQL Lookup and official Firebase CheckUser before returning200. It returns401 for locally revoked sessions/Firebase revoked or disabled users and503 for Firebase dependency outage. It requires no paid grant fixture and directly exercises the intended identity assertion.

## Task 1: Restore the existing integration observation

**Files:** Modify only `apps/api-go/auth_http_test.go`.
**Consumes:** existing testFirebaseExchangeAndUserRevocation and actual customerAuthService.currentSession.
**Produces:** unchanged five-scenario identity suite observing the genuine session boundary.

- [ ] Confirm retained red evidence and database rows above against the exact source SHA. Do not relabel or rerun the failed receipt.
- [ ] Make exactly this request path replacement inside protectedStatus (retain the helper name and all status assertions):

```diff
- request, _ := http.NewRequest("GET", server.URL+"/v1/catalog/years", nil)
+ request, _ := http.NewRequest("GET", server.URL+"/auth/session", nil)
```

- [ ] Run local focused tests from apps/api-go with existing Go toolchain, retaining stdout/stderr outside checkout:

```sh
go test -count=1 -run '^(TestCustomerAuthHTTPBoundaries|TestCustomerLocalLoginUnavailable|TestConfiguredCustomerAuthRequiresPersistenceAndWiresServer|TestOfficialFirebaseSDKVerification|TestOfficialFirebaseSDKLookupDeadline)$' .
go test -count=1 ./...
go vet ./...
git diff --check
```

Optional live PostgreSQL integrations skip outside the isolated supervisor and are not acceptance. No added mirrored/source-text test is necessary for this one-line assertion-path correction. The retained failed actual integration is the red evidence; fresh actual identity5 after independent code review supplies green.

- [ ] Verify `git diff --name-only` is exactly apps/api-go/auth_http_test.go relative to the committed planning checkpoint; commit `test(auth): observe revocation through protected session endpoint`, promptly push and obtain independent exact-commit review.
- [ ] Coordinator integrates the reviewed candidate, then uses unchanged frozen `/tmp/autodata-r5-040-access-supervisor-94f81fd8665351eb2fab07c59e5752874634855b8ba3a5f5862dfd4ea0a20adb.py` (SHA256 `94f81fd8665351eb2fab07c59e5752874634855b8ba3a5f5862dfd4ea0a20adb`). Run at a clean immutable SHA after dual-bank/commerce Docker runs finish. Require all five raw Go subtests to pass and full strict receipt validation including provenance, migration040/038 and cleanup. No acceptance/deployment/production claim before this green evidence.

## Concrete todo

- [ ] Synchronize Issue186/Project8, the dedicated plan, canonical identity document, queue, task and record; commit/push and pass exact-SHA preflight before independent coordinator gate review.
- [ ] Change only apps/api-go/auth_http_test.go: make testFirebaseExchangeAndUserRevocation probe GET /auth/session instead of the public GET /v1/catalog/years; retain all five identity subtests and exact 401/200/401/401/503 status expectations.
- [ ] Run focused auth HTTP/SDK tests and full Go test/vet with retained logs and explicit optional-integration skip disclosure; confirm the one-file diff preserves all product auth/session/SQL behavior and commit/push for independent exact-SHA review.
- [ ] Coordinator integrates the reviewed test-only correction and runs the unchanged frozen identity5 supervisor on a clean immutable integrated SHA after current Docker acceptance finishes; preserve original failed receipt and independently inspect raw events, database rows, provenance and cleanup.

Tracking synchronized/read back `2026-11-03T23:58:25.506564+00:00`: https://github.com/lucronn/autodata/issues/186#issuecomment-6618597888; Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, field Source or dependency reference. Exact issue-comment SHA256 `bdcf4f4fb7bdb74f3c65ba6a9bbccd5a0e166469c6f2fbfd1ecf723efc64e060`, Project-text SHA256 `0a1d7564da5b9e26b365fc471272c5fc0c092e409abe53efbbf8fe185cb7089d`. The compact Project index preserves all prior references; the complete prior field is verbatim in the comment. Record `status: synchronized`; checkpoint/preflight/independent review remain pending.
