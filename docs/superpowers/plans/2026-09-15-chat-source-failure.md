# Repair the natural-language source-retrieval acceptance path

Issue: https://github.com/lucronn/autodata/issues/96
Project: https://github.com/users/lucronn/projects/8
Canonical repository record: `docs/architecture/guide-artifacts.md`

## Goal

Make the browser acceptance request

`oil pump, water pump, timing belt, and power steering pump replacement for a 1999 Chevrolet Silverado 1500 2WD 5.3L`

resolve to the canonical Chevrolet vehicle, retrieve the vehicle-scoped source data, and publish a visible procedure/quote result. When source retrieval exhausts its retries, the public answer must say that the lookup failed instead of retaining the stale `processing · normalizing` state.

## Diagnosis

The live 8080 dashboard is served by the `autodata-api-1` container and its worker, both older than the current repository checkout. The current natural-language parser also matches the filler phrase `for a` as the make, producing `make=For` and `model=A Chevrolet Silverado 1500`; this prevents the source connector from resolving the intended vehicle. A separate projection bug occurs after three source failures: the job becomes `dead_letter` and the query becomes `failed`, but the nested answer remains `answer_status=processing` and `data_state=normalizing`. The dashboard correctly prefers that nested answer state, so it displays a request that is no longer running.

The first rebuilt browser run then exposed a warm-cache compatibility defect: the cached combined article contained complete nested `procedure.steps` and `labor.operations` for all four requested components, but the legacy composer only read top-level operation fields. It therefore reduced the cached answer to an oil-pump placeholder with unknown labor, even though the stored revision was complete. The fix must preserve the reusable revision shape when a warm read falls through to the compatibility composer.

## Design

1. Extend the bounded vehicle parser to ignore grammatical vehicle introducers such as `for a`, while preserving existing year/make/model, drivetrain, body, engine, and later-year parsing behavior. Canonical vehicle fields remain authoritative; no provider prose is used as identity.
2. On terminal failure of a lane that has no usable or provisional answer, update the persisted answer to `answer_status=failed` and `data_state=unavailable`, retain the vehicle and warning context, and publish a correlated terminal answer event. A provisional source-backed answer remains visible if a later normalization or composition stage fails; deep work cannot hide available data.
3. Make the compatibility composer read persisted nested labor from a composed article, so a warm answer preserves all requested components, labor durations, overlap metadata, and source-linked steps. Add deterministic regressions for the `for a` vehicle phrase, nested terminal failure projection, and complete-vs-incomplete composed-cache behavior. Keep the Go proxy unchanged unless a test demonstrates a forwarding defect.
4. Rebuild only the local API and ingestion containers from the checked-out revision without removing PostgreSQL, NATS, MinIO, or their volumes. Verify health/readiness and AutoAPI source reachability without printing secrets.
5. Run the exact browser flow in the in-app dashboard. Verify the canonical Silverado label, correlated Workers terminal progress, a visible procedure and quote, and the correct explicit failure state for a forced source failure. Do not claim completion from unit tests alone.

## Concrete todo list

- [x] Add the natural-language `for a` parser regression.
- [x] Add the terminal source-failure answer-projection regression.
- [x] Implement filler handling and terminal answer-state publication.
- [x] Preserve complete nested labor/procedure data when a composed cache row is read through the compatibility composer.
- [x] Run focused and full applicable tests with diff checks.
- [x] Rebuild/restart the local API and worker containers from this revision.
- [x] Rerun the exact Silverado flow in the browser and record the observed result.
- [ ] Synchronize the final commit, Issue #96, Project #8, and CI evidence.

## Acceptance

- The parsed vehicle is `1999 Chevrolet Silverado 1500`, with `2WD` and `5.3L` preserved.
- A source-retrieval dead letter exposes `failed`/`unavailable` in both the query and nested answer, with no stale processing state.
- A valid provisional source answer remains visible across later-stage retry/dead-letter behavior.
- A fresh browser run reaches a user-visible procedure and quote when AutoAPI returns the required source data, or an explicit unavailable result when the source is unavailable.
- A warm composed revision does not regress to a single-component placeholder: all requested components, known labor, overlap metadata, and source-linked steps remain visible.
- The browser Workers terminal shows the same query’s source and terminal events.
- No user-owned `output/`, `sample data/`, or `tmp/` files are staged or modified.
