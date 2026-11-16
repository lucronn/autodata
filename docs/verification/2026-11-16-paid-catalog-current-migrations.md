# Paid catalog current-migration verification

Issue: https://github.com/lucronn/autodata/issues/393
Project: https://github.com/users/lucronn/projects/8
Draft PR: https://github.com/lucronn/autodata/pull/394

Start at exact draft head034f145514c888eab3ddd0793c9681b628c6cea6 in the isolated offloaded worktree. The paid child runner expects40 migrations ending040, while this source has42 ending042_catalog_selector_rows.sql. Its collector/typed receipt validator also hardcode001_040 and an exact40-file inventory. These stale assumptions prevent current-head paid acceptance.

Correct only the paid child assertion, collector/validator migration receipt keys and exact inventory, and their tests. Preserve exact-inventory fail-closed validation. Add source-only regressions that inspect the actual child assertion AST without importing or executing PostgreSQL fixture code, compare the actual checked-out migration inventory with producer and typed validator, and reject an old40-file ledger. Do not change SQL, general catalog receipt contracts, Go/API/search/reader/product behavior, flags or runtime checks.

Run red/green source-only unittest suites and syntax/diff checks with bytecode/cache disabled. No Go compilation, Docker starts/builds/pulls, SQL, browser, provider, Stripe or public/private service mutation. Catalog owns the Docker slot. Push validated commits to existing draft PR branch without rewriting history; inspect exact-head CI. The runtime12-case acceptance remains NOT_RUN and requires a separately admitted slot/pinned-image/capacity/cleanup package. Synthetic collector tests do not prove real PostgreSQL/HTTP or paid reader acceptance.

## Todo

- Synchronize Issue393/Project8, plan, canonical verification doc and record; commit checkpoint and pass pinned preflight.
- Add source-only red regression for exact current 42-file migration manifest and paid producer/validator agreement.
- Correct only paid migration count, terminal filename, exact inventory and 001_042 receipt assertions; verify targeted offline suites.
- Push draft PR394 head and inspect exact-head CI; keep guarded paid PostgreSQL/HTTP and authenticated reader/search acceptance pending.

Status: source repair verified; paid runtime acceptance pending.

## Source-only result

Pinned checkpoint2f1c3417 passed machine preflight before implementation. The paid child and typed ledger validator now require42 migrations; the terminal file is042_catalog_selector_rows.sql. Producer/validator receipt keys explicitly cover001_042 and the exact manifest includes041_article_source_projection_v2.sql and042_catalog_selector_rows.sql. Old40-file ledgers remain rejected. The new regression uses actual checked-out migration files and compiles only the owning child assertion AST, without importing database fixture runtime code. No general-catalog receipt or product/SQL/Go behavior changed.

Red: both new source-contract tests failed against prior assumptions; a full synthetic run then exposed the separate stale typed-ledger40-row guard, retained in the red log and corrected. Final green: six paid collector tests; all164 synthetic release-receipt tests (640.359s); AST parse of all five changed Python files; git diff --check. Logs and hash inventory: /home/corp/autodata-evidence/paid-catalog-current-migrations-tests-20261116/SUMMARY.json. These are synthetic parser/contract checks, never PostgreSQL/HTTP or payment acceptance.

PR394 remains draft. Actual12-case paid PostgreSQL/HTTP fixture and authenticated paid-reader/search acceptance remain NOT_RUN, pending a separately reviewed exclusive slot, pinned local test images, candidate plain-clone/input attestations, resource bounds and cleanup gate. No Docker, SQL, browser, real provider, Stripe or public/private service change was performed. Exact-head CI will follow the push. Protected master advanced to09524db599a82e7f8c79a1d8fb43bfadc6bbe2f3; its merge conflict will be handled as a separately synchronized amendment, preserving the route-state fix and paid search.

## Exact protected-master integration amendment

Issue: https://github.com/lucronn/autodata/issues/393
Project: https://github.com/users/lucronn/projects/8
Draft PR: https://github.com/lucronn/autodata/pull/394

The verified migration fix is pushed at6dfe602c3b1a2ab4a8098e8ae30aab9ca32b8ffe (collector6/full synthetic receipt164 PASS). Root explicitly requested integrating protected master09524db599a82e7f8c79a1d8fb43bfadc6bbe2f3 after PR447 merged. Read-only merge-tree resultd290eb9822907178b293389e7c16f26d3fb8898c shows one conflict only, in apps/api-go/workshop-client.test.mjs: draft adds searchNavigation; master adds rows:{} and Option to the same library test context. Keep the union. apps/api-go/workshop/app.mjs auto-merges: its delta from draft is exactly the protected route-state fix (clear descendant option rows/search; restore URL q and reset vehicle/quote before all route branches), preserving paid query generations, denial and metadata-only behavior. Do not redesign routing, search, rendering, payment or grants.

Review the resulting app delta against exact PR447 source; retain master route regressions and draft search regressions. Run the complete Node Workshop test harness and JS syntax checks plus the six source-only paid migration collector tests and exact typed-ledger regression. No Go compilation or rerun of unchanged full synthetic Python suite is required unless a new failure/source change justifies it; CI reruns all required checks on final head. Modern-web-guidance navigation search and stack-drill-down guide were consulted; no new browser API, scrolling component or history mechanism is needed for this merge.

All edits/logs/cache remain in the isolated offloaded worktree/evidence location. No Docker starts/builds/pulls, SQL, provider, Stripe, browser runtime or public/private service change. Preserve source fixture flags and all runtime acceptance holds. PR394 stays draft;12-case paid PG/HTTP fixture and authenticated reader/search acceptance remain NOT_RUN until separately admitted.

## Todo

- Synchronize this exact-master integration amendment in Issue393/Project8 and canonical docs; commit checkpoint and pass preflight.
- Merge exact protected09524db599a82e7f8c79a1d8fb43bfadc6bbe2f3 into verified draft head6dfe602c without rewriting history.
- Resolve only the test harness namespace conflict by retaining searchNavigation plus rows/Option, preserving the auto-merged route-state and paid search source.
- Run all Workshop Node harness tests, JS syntax checks and focused Python migration/receipt regressions; push draft head and verify exact-head CI. Keep runtime12-case acceptance NOT_RUN.

## Protected09524 integration result

Amendment checkpointf5e65035 passed pinned preflight. Merged exact protected09524db599a82e7f8c79a1d8fb43bfadc6bbe2f3, resolving the only textual conflict in the library test context by retaining searchNavigation, rows:{} and Option. No hand-authored production JS change: the auto-merged app.mjs added/removed lines exactly equal protected PR447, independently compared in MERGE-REVIEW.json; all five paid migration Python files are byte-identical to verified6dfe602c. Thus the route-state baseline is retained together with draft paid search.

Merged-tree verification: all331 Workshop Node tests PASS/zero skips; app/test JS syntax PASS; seven focused paid-migration/typed-ledger checks PASS; staged diff whitespace PASS. Evidence: /home/corp/autodata-evidence/paid-catalog-master09524-tests-20261116. The unchanged full synthetic Python suite previously passed164 tests at6dfe602c. Final-head CI remains required after push. PR394 stays draft and actual12-case paid PG/HTTP plus authenticated reader/search acceptance remain NOT_RUN. No Docker, Go build, SQL, provider, Stripe, browser or service dispatch.
