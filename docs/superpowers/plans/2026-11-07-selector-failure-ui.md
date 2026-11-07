# Workshop selector failure states

Current status: live API/UI release passed; see the exact r3 receipt and acceptance limits below.

Goal: Distinguish Workshop selector loading failures and timeouts from authoritative empty configurations.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Source base: 814a1c26e893fe181327516cfa4b48a800978c43

## Diagnosis and decision

loadOptions ignores readCollection.timedOut and reports empty or ready after its one-minute polling budget. Async provider failures are logged rather than returned by selector GET; do not invent source-error details. Report incomplete/timeout outcomes as choices not finished loading, with retry and retained partial rows. Preserve saved-choice resume if its real row exists; a missing saved choice is only declared unavailable for completed scopes. Authoritative completed-empty configuration scopes must return complete=true/hydrating=false and schedule no hydration. Existing incomplete rows still require hydration even with a scope marker. No synthetic rows, paywall changes, provider changes, runtime changes or architecture expansion.

## Concrete todo
- [x] Add failing Go regressions for completed-empty, incomplete-empty and malformed/incomplete configuration scopes.
- [x] Add actual loadOptions browser-logic tests for timeout, partial, saved-choice and completed-empty outcomes.
- [x] Keep completed-empty configurations terminal; show incomplete selectors as retryable loading failures while preserving usable rows.
- [x] Run Go and browser checks, obtain independent review, push coherent commits and open a PR; coordinate release separately.

## Verification

Go handler tests must cover empty-complete, empty-incomplete, usable markerless and incomplete-row cases. Actual loadOptions VM tests cover partial/empty timeout, nonhydrating incomplete responses, completed empty, saved-choice resume and stale generation. Run node --test workshop-client.test.mjs and go test ./... in apps/api-go. Use existing status live regions and native Retry button; avoid duplicate announcements.

## Product-bound API/UI release checkpoint

Issue release reference: https://github.com/lucronn/autodata/issues/186#issuecomment-6702178675
Project: https://github.com/users/lucronn/projects/8 — dedicated Selector failure UI reference field read back.
Merged product `cad924e88a77781af594fa7dbdc26dc43d4f27d8`, tree `ce346ed13f70ed2b118afd13861bee8da820e6fd`; reviewed head `35cac9f65a8604f3ac3962417fa2d5b2757b772c` has identical full tree and all `apps/api-go` blobs match the independent code-reviewed head `2cf62b76be5a0115e5dc72072fb5d3cde1445ea8`. Required CI https://github.com/lucronn/autodata/actions/runs/42336760347 passed all required checks.

Release todo:
- [ ] Commit/push this clean descendant checkpoint and run machine preflight at its exact SHA.
- [ ] Archive and verify every merged-source blob, run the exact merged-source Go and browser checks, build an immutable Linux API binary, and seal source, binary, operator and dispatch under root-owned paths.
- [ ] Independently review an API-only atomic drop-in switch, scoped Git checkout trust, rollback, and exact preservation of the active catalog, ingestion and article worker identities and schema.
- [ ] Verify served Workshop bytes, complete real selector canaries, public/local health, disabled checkout and worker preservation; record any unavailable live completed-empty/timeout canary honestly.
- [ ] Record the live result in Issue #186, Project #8 and this verification document without claiming paid article browsing or new source completion.

The API switch does not change provider credentials, permissions, payment status, migrations, article grants or source workers. If any binding or canary fails, restore the previous API drop-in and executable. Catalog worker boot persistence and paid access remain separate release questions.

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
