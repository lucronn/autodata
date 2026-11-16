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

Status: checkpoint only; implementation and tests pending.
