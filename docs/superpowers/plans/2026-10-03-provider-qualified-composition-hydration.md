# Provider-qualified article hydration for multi-component procedures

**Issue:** https://github.com/lucronn/autodata/issues/110  
**Project:** https://github.com/users/lucronn/projects/8  
**Canonical contract:** `docs/architecture/mercury2-procedure-composition.md`

## Goal

When a multi-component request cannot find a normalized article locally, resolve
the vehicle and selected article separately for AutoDBone and AutoDBtwo, ingest
only the selected individual article from a provider that actually owns its
identifier, persist its normalized form, and compose from those persisted
records. A provider-specific identifier must never be sent to another source.

## Evidence and observed failure

The current composition worker checks the local normalized catalog, then calls
`_load_autoapi_job_catalog`, which uses AutoDBone only. Its generic
`provider_vehicle_id` is interpreted as an AutoDBone ID. The candidate test
vehicles were selected from AutoDBtwo mappings; passing those AutoDBtwo IDs to
AutoDBone returned HTTP 404. The running local worker also has the retired
`https://autoapi-sigma.vercel.app` origin, while the current Compose default is
the AutoDBone neutral facade. These failures are not procedure acceptance.

## Invariants

- Check normalized individual article content first; do not make a source detail
  call for already usable content.
- Keep provider identities namespaced (`autodbone` and `autodbtwo`) through
  selection, catalog resolution, and detail retrieval. Never fall back from a
  provider-specific ID to an unqualified ID.
- On a cache miss, use the vehicle's canonical YMME/configuration to query each
  configured provider through its current connector contract. Select only the
  requested component articles; do not hydrate the full catalog.
- Normalize and persist each individual article once with source lineage and
  locally stored images. Reuse it on the next request.
- The combined procedure remains an ephemeral response. Do not persist/cache
  the composition. Labor remains excluded.
- Return explicit per-source outcomes for unavailable, not-found, unauthorized,
  and rate-limited responses; a miss from one provider must not suppress a
  usable result from the other.

## Concrete todo

- [x] Trace canonical vehicle mappings from public catalog selection into the
  composition request and define provider-qualified request fields.
- [x] Add regressions proving AutoDBtwo vehicle IDs never reach AutoDBone; a
  mixed-provider regression now also proves AutoDBone articles survive AutoDBtwo
  hydration. The complementary AutoDBone-article-ID-to-AutoDBtwo boundary test
  remains outstanding.
- [x] Resolve missing component articles through the current AutoDBone facade
  and standalone AutoDBtwo connector, fetching detail only for selected
  components and falling back across providers on a miss/error. Mixed-provider
  merges retain already usable records from either source.
- [ ] Persist normalized individual articles and local images idempotently;
  prefer a complete normalized row over a same-identity list-only row, prove a
  warm repeat performs no provider detail calls, and prove no combined article
  is written.
- [ ] Add structured source diagnostics that preserve useful failure classes
  without exposing upstream URLs, credentials, or source identifiers publicly.
- [ ] Run worker/API/connector contract tests and five newly selected,
  multi-component requests for distinct YMME vehicles; require every response
  to contain readable, source-backed procedure steps without errors. Worker
  tests pass (542 passed, 3 skipped, 27 subtests). Five cold candidate requests
  now return readable source-backed procedures, but the warm replay still calls
  AutoDBtwo for 2/5 requests because duplicate list-only rows can win over
  content-complete rows. The cache acceptance gate remains open.
- [ ] Run applicable release gates and record exact-SHA evidence; do not close
  the Issue before the release gate is satisfied.

## Acceptance

All five fresh multi-component requests use different YMME vehicles and return
non-empty procedures. Each missing individual article is selected from the
correct source namespace, ingested and stored once, and reused on repeat reads.
Provider failures are accurately reported, and no combined procedure is stored.

## Implementation sequence

1. Preserve this plan and the synchronized issue/project/document record in a
   checkpoint commit and pass repository preflight.
2. Add regression tests for identity separation and provider fallback.
3. Implement selected-article hydration and persistence through current
   connectors.
4. Run deterministic tests, then the five live-style YMME queries in an
   isolated candidate environment; fix every empty/error result and repeat the
   affected acceptance query.
5. Update Issue #110 and Project #8 with exact commit and test evidence.

## Latest implementation evidence

- Candidate worker suite: `pytest -q workers/ingestion-python/tests` — 542
  passed, 3 skipped, 27 subtests passed.
- Five newly sampled cold YMME requests passed through AutoDBtwo: 2013 Honda
  Odyssey 3.5L, 2013 Honda Pilot 3.5L, 2012 Ram 3500 6.7L, 2013 Honda Accord
  Coupe 2.4L, and 2013 Honda Crosstour 3.5L. Each selected two source article
  IDs, returned respectively 26, 29, 2, 69, and 20 readable source-referenced
  steps, emitted no labor, and returned no error.
- Warm repeat: 3/5 used `normalized_cache`; Odyssey and Ram 3500 used the
  AutoDBtwo detail path again. Database inspection found both `content_complete`
  and later `list_only` rows for the same article identity. The query-aware
  catalog ordering prioritizes engine match but does not yet prefer complete
  content. Fix this before declaring persistence/reuse acceptance.
- The first failed candidate attempt was due to Docker DNS using the container's
  full name instead of the connector's trusted `autodbtwo` alias; the isolated
  network was corrected, and the cold five-case run then passed.
- Independent review caught and the implementation fixed a mixed-provider
  merge that could drop a usable AutoDBone article when AutoDBtwo supplied a
  different requested component. Regression coverage passes.
