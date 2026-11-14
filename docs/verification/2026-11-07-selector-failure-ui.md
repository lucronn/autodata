# Selector failure UI verification

Goal: Distinguish Workshop selector loading failures and timeouts from authoritative empty configurations.

Plan: docs/superpowers/plans/2026-11-07-selector-failure-ui.md
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

Current status: API/UI release passed; five complete public selector canaries, public readiness HTTP200 and checkout disabled. Paid authenticated browse unverified; live empty/timeout unavailable. Earlier implementation and release-checkpoint entries below retain their historical context.

- [x] Add failing Go regressions for completed-empty, incomplete-empty and malformed/incomplete configuration scopes.
- [x] Add actual loadOptions browser-logic tests for timeout, partial, saved-choice and completed-empty outcomes.
- [x] Keep completed-empty configurations terminal; show incomplete selectors as retryable loading failures while preserving usable rows.
- [x] Run Go and browser checks, obtain independent review, push coherent commits and open a PR; coordinate release separately.

## Implementation evidence

Planning checkpoint `15207c0` was pushed before implementation and machine preflight returned `status: synchronized`, no errors. Issue comment `6701702203` and dedicated Project field `Selector failure UI reference` were read back.

- Go regression initially failed: completed-empty response reported `complete=false/hydrating=true`.
- Actual `loadOptions` + `operation` tests initially failed for empty/partial timeout, nonhydrating incomplete responses and falsely unavailable saved choice.
- Commits `582bdbe` and `c490471` implement the bounded fix. No fabricated rows or provider error details.
- `/home/corp/go-sdk/bin/go test ./...` in `apps/api-go`: passed, 8.629s.
- `node --test workshop-client.test.mjs workshop-demo.test.mjs`: 196 passed, 0 failed.
- `git diff --check`: passed.

Accessibility guidance: reuse the existing error live region and native Retry button. The retrieved accessibility guide says “Announce dynamic errors via live regions”; loading updates do not add new announcements.

## Updated release candidate

Independent review passed at reviewed head `2cf62b76be5a0115e5dc72072fb5d3cde1445ea8` (coordinator confirmation). To meet branch protection after PR #366, master `c9c58fcd74e67c07d7014497a6f7433f79cf2ae3` was merged without conflicts at `5220d97ea5f93d49c834ebe2749c96dc866fbee7`, tree `1a0578b30ef6717912f0b1a4561567a79d4d415f`. Every `apps/api-go` blob remains identical to the reviewed head.

Fresh verification after the master merge:

- Pinned planning preflight at `15207c0`: `status: synchronized`, `errors: []`.
- Full Go API suite: passed.
- Workshop client and demo Node suites: 196 passed, 0 failed.
- `git diff --check`: passed.
- Issue #186 and Project #8 dedicated Selector failure UI reference were read back.

Required CI is running on the updated PR. Merge is authorized after required checks pass; deployment remains separately coordinated. No runtime operation was performed.

## Merged product and release gate

PR #367 merged as `cad924e88a77781af594fa7dbdc26dc43d4f27d8` (tree `ce346ed13f70ed2b118afd13861bee8da820e6fd`), equal to verified head `35cac9f65a8604f3ac3962417fa2d5b2757b772c`; `apps/api-go` is unchanged from independently reviewed `2cf62b76be5a0115e5dc72072fb5d3cde1445ea8`. [Required CI](https://github.com/lucronn/autodata/actions/runs/42336760347) passed all three required checks. The [Issue release checkpoint](https://github.com/lucronn/autodata/issues/186#issuecomment-6702178675) and dedicated Project field record the same product and todo.

The production switch remains pending. It must use the immutable merged source, preserve the active catalog, ingestion and article workers, run merged-source Go/Node tests and served-byte/public selector canaries, and retain checkout disabled. A real paid article path and live timeout/completed-empty scopes are not asserted by this release gate.

## Live API/UI release outcome

The coordinator completed the API-only selector UI release from merged PR #367 product `cad924e88a77781af594fa7dbdc26dc43d4f27d8` under synchronized checkpoint `7dfeac4868f21ec5b1fdc7c25973744bc296eb75`. Protected receipt `/var/lib/autodata/selector-ui-release-run-cad924e-r3/receipt.json` was read back with status `passed` and SHA256 `3e0c1fb88698ada74bde7e6ecede56f43f2ce46a68986f8850149c9f8efcf62b`. Exact merged-source Node selector test receipt SHA256 is `87c50bf1a0a828113234187338754278c23a0f3ef97578ccc009d1a0bf58ca79`; post-switch served assets matched the tested source bytes.

All five public selector canaries returned complete collections:

| Public scope | Items |
| --- | ---: |
| 2027 Ford models | 13 |
| 2020 Ford models | 29 |
| 2020 Figo configurations | 1 |
| 2014 Toyota models | 32 |
| 2014 Camry configurations | 3 |

API, article worker and catalog worker are active; public readiness returned HTTP200 and checkout remains disabled. Receipt pins the unchanged ingestion, article and catalog container IDs in the canonical record; no migration or worker stop was requested. Prior attempts r1 (permission) and r2 (strict canary) failed and rolled back with recovery verified; their evidence is preserved. The successful r3 receipt supersedes earlier pending deployment status, without relabeling either failed attempt.

Paid authenticated browse remains unverified. Live completed-empty and live timeout canaries were unavailable; merged-source tests plus exact served-byte identity support the bounded UI behavior claim. No new article/job completion or paid-access acceptance is claimed. This documentation update performs no deployment, runtime change or additional authorization.

Current release todo:

- [x] Bind merged product, reviewed code, required CI and synchronized exact checkpoint.
- [x] Verify protected test/build/source evidence and preserve exact active ingestion/article/catalog workers.
- [x] Complete API-only r3 rollout, served-byte checks and five complete public selector canaries; retain readiness and disabled checkout.
- [x] Record the successful receipt, both verified failed-attempt recoveries, and unavailable/unverified acceptance limits in canonical docs, Issue186 and Project8.
