# Workshop Autonomous Verification Timeout — DRAFT Task55

**Goal:** Restore complete Autonomous Verification for the expanded developer suite by raising only the autonomy-policy job timeout from 20 to 30 minutes, preserving every check, smoke and release block.

Issue: https://github.com/lucronn/autodata/issues/186. Project: https://github.com/users/lucronn/projects/8, existing item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4. Planning and tracking are synchronized; implementation remains blocked and all authorities false.

The existing job-wide 20-minute cap cancels the `autonomy-policy` job after all 576 developer tests pass. Exact source-push run 41955411249 and actual PR checkout run 41955418073 both exceed 20m during live Compose, with the smoke cancelled after ~81–83 seconds. The comparable successful Task53 smoke needs ~141–149 seconds. See external `/home/corp/autodata-evidence/ci-timeout-gap-audit/REPORT.md`. This is not a passing smoke or code test failure.

One-line design: in `.github/workflows/autonomous-verification.yml`, change only `jobs.autonomy-policy.timeout-minutes: 20` to `30`. Preserve all job triggers, permissions, names, steps, test commands, DTO/R3 limits and live Compose cleanup. 30 minutes covers observed ~18m53s pre-smoke plus ~2m25s smoke with margin, subject to fresh CI; it costs at most 10 additional runner minutes per job and does not relax any assertion. The immutable workflow input is 15003 bytes/SHA256 `adbe6221e09c0427d5abaf0ddaa566331abb483f8e246dad3dd42a3dbd6d23a3` at parent `0e30b18ff83c3e9fcc63dd614aa1f13562d0c026`/tree `90bb436d568c5966f4497efbbe62c9a60d8352de`. Source candidate `0a913c2c3826b1079752ca3d54003718b05fe9f5` is separate and not a merged dependency.

## Literal todo

- [ ] Independently review the exact Task54 planning parent 0e30b18ff83c3e9fcc63dd614aa1f13562d0c026 and Task52 cancelled-run timing evidence; freeze the one-line workflow scope and unchanged step inventory.
- [ ] Synchronize this literal goal, six todo strings, six gate paths and exact workflow implementation path in Issue186/Project8 with before/after preservation readbacks; commit/push the six-document checkpoint, externally seal SHA/tree, pass standalone and nested exact-base preflights and independent checkpoint review before dispatch.
- [ ] Write a source-only regression assertion that the autonomy-policy job timeout is 30 minutes while all other workflow bytes and the DTO/R3 job limits remain unchanged; then change only the one timeout scalar from 20 to 30.
- [ ] Validate YAML/workflow structure, exact one-line diff, unchanged check names/commands and smoke cleanup, and run local repository-governance/workflow checks without provider or deployment actions.
- [ ] Commit/push the validated one-line implementation; obtain independent exact-code review and fresh source-push plus actual PR checkout Actions terminal success, including the complete live Compose fast-lane smoke; retain any failures without acceptance credit.
- [ ] Keep Vercel rate-limit, provider enrollment, real API/browser acceptance, merchant enablement, DNS, staging, merge, deployment and production release as separate blocked decisions; do not widen CI timeout to hide failing assertions.

## Implementation steps after the gate

1. Independently inspect the six-document synchronized checkpoint and exact source workflow. The one implementation allowlist path is `.github/workflows/autonomous-verification.yml`; no test/script or other workflow file is allowed.
2. Add a source-only pre-change regression check in the external evidence directory that proves current timeout20 and fingerprints every other workflow byte. Change the scalar to30; rerun the check and ensure the full diff contains exactly one line. No test is deleted or skipped.
3. Run `git diff --check`, current repository governance and workflow syntax checks. Commit/push a coherent one-line milestone; obtain independent code review and both source-push/PR checkout Actions terminal success. If live Compose still fails or times out, report the failure and keep CI unverified.

No provider, staging, DNS, merchant, real customer, merge or release authority follows from this CI adjustment. Vercel rate limiting is separate. Accepted credit0.

## Coordinator tracking readback — planning synchronized

Issue comment https://github.com/lucronn/autodata/issues/186#issuecomment-6649400966 at 2026-11-05T04:07:10Z records the literal goal, all six todo strings, six gate paths, one workflow path and prior Project Source verbatim. Before snapshot `/home/corp/autodata-evidence/task55-before-tracking.json` SHA256 `7815ced413730b26519ced79d09da9f8ad6d818e90e4cbd8fb2506d8c1cd2c8c`; after snapshot `/home/corp/autodata-evidence/task55-after-tracking.json` SHA256 `ac318d19356ed481e5f7e111bd82d6e14819b692391c165a897a07a914f8e25b`. Issue body, prior248 comments and other Project fields unchanged. Project Source after SHA256 `62b6b3f470722d3c167a2c07bfc95a0d3f770b05c25e745c1da6a225461f1435`. Standalone/nested status synchronized; execution blocked, all authorities false, implementation allowlist empty. Exact checkpoint, preflights, independent review and dispatch remain required.
