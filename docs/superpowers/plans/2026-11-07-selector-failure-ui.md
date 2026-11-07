# Workshop selector failure states

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
