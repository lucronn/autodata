# Paid catalog current-migration fixture repair

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

## Source-only result

Pinned checkpoint2f1c3417 passed machine preflight before implementation. The paid child and typed ledger validator now require42 migrations; the terminal file is042_catalog_selector_rows.sql. Producer/validator receipt keys explicitly cover001_042 and the exact manifest includes041_article_source_projection_v2.sql and042_catalog_selector_rows.sql. Old40-file ledgers remain rejected. The new regression uses actual checked-out migration files and compiles only the owning child assertion AST, without importing database fixture runtime code. No general-catalog receipt or product/SQL/Go behavior changed.

Red: both new source-contract tests failed against prior assumptions; a full synthetic run then exposed the separate stale typed-ledger40-row guard, retained in the red log and corrected. Final green: six paid collector tests; all164 synthetic release-receipt tests (640.359s); AST parse of all five changed Python files; git diff --check. Logs and hash inventory: /home/corp/autodata-evidence/paid-catalog-current-migrations-tests-20261116/SUMMARY.json. These are synthetic parser/contract checks, never PostgreSQL/HTTP or payment acceptance.

PR394 remains draft. Actual12-case paid PostgreSQL/HTTP fixture and authenticated paid-reader/search acceptance remain NOT_RUN, pending a separately reviewed exclusive slot, pinned local test images, candidate plain-clone/input attestations, resource bounds and cleanup gate. No Docker, SQL, browser, real provider, Stripe or public/private service change was performed. Exact-head CI will follow the push. Protected master advanced to09524db599a82e7f8c79a1d8fb43bfadc6bbe2f3; its merge conflict will be handled as a separately synchronized amendment, preserving the route-state fix and paid search.
