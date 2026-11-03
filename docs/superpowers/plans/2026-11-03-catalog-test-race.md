# Repair the catalog hydration test race

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

The full Go race suite fails at `7e7249f1ed9c65fa75f2ccf484a9336ad70d6c5d`
before any commerce Go implementation. The existing test
`TestUsableConfigurationsAreNotBlockedByMissingHydrationScope` polls
fakeIngestionClient.path while background hydration writes it. Root reproduced
this independently in `/tmp/autodata-pre-commerce-api-full-race.log`; this is a
test synchronization bug, not evidence of a payment or production application race.

## Exact scope and implementation

Modify only `apps/api-go/catalog_test.go`. Reuse its existing
blockingCatalogHydrationClient, initialize its started/release/finished channels
and close release before making the request so the observer never blocks work.
Replace shared-field polling/sleeps with a bounded select on finished. The helper
only signals completion for the expected `/v1/catalog/ensure` path, retaining the
original assertion. Preserve the HTTP/configuration/complete/Hydrating assertions.
No application behavior, shared fake, catalog hydration or other test changes.

## Concrete todo

- Synchronize Issue/Project/canonical documentation and this record, commit the
  checkpoint and pass exact-base preflight before modifying the single test file.
- Replace the unsafe field observation with existing channel synchronization.
- Run the exact affected test under the race detector, then full `go test -race
  -count=1 ./...` and ordinary Go suite; retain the original failure unchanged.
- Independently review the one-file diff, commit/push and integrate before final
  commerce acceptance. Record actual results; do not call the earlier race run a pass.

Model remains Sol6.1, medium, Fast/priority. This bounded repair does not expand
either commerce builder's39-path scope or their disjoint31+8 ownership.


## Verified repair

Gate347cc2042b245e71861e62c9606085bb1d01f04f passed exact-base preflight.
Implementation79c17ae12ed45d7ee86eae0f385e95acff4c9b07 changes only the
authorized test file. Root targeted race1.035s, full race2.455s and ordinary
Go1.162s pass. An independent Sol6.1/medium/Fast reviewer approved the exact
one-file diff with no findings and reran the target10times under the race
detector (1.059s). Original red log remains at
`/tmp/autodata-pre-commerce-api-full-race.log`; green logs use
`/tmp/autodata-catalog-test-race-{targeted,full,normal}-green.log`.
The received native review is recorded in
`/tmp/autodata-catalog-test-race-independent-review.md`.
Final combined commerce acceptance must include this verified repair; it does
not count as executing the fourteen PostgreSQL commerce cases.
