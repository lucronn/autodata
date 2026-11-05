# Bind catalog discovery to the purchased configuration's region

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

## Observed mismatch and bounded decision

The paid catalog and commerce use `vehicle_identity_bases.region` for an exact
configuration. `catalog_coverage.run_catalog_index_job` instead initializes its
source selector from `vehicles.region` and only adds the configuration label.
The normal identity writer currently gives both rows the same region, but no
database constraint requires equality. The real paid fixture deliberately has
a CA configuration under a US vehicle. Such a valid exact scope must resolve
against CA in both source banks, rather than silently using the vehicle region.
This is a defensive correction; no existing production data corruption has
been established.

For a configuration-scoped job, use that configuration's identity base region
in the source selector. Keep vehicle-only discovery, label construction,
approved provider mappings, ambiguity handling, canonical identity and durable
job semantics unchanged. Do not broaden this repair to identity normalization,
schema changes or a new ingestion pipeline.

## Exclusive implementation scope

The coordinator owns exactly these two files in a separate checkout:

- `workers/ingestion-python/src/autodata_ingestion/catalog_coverage.py`
- `workers/ingestion-python/tests/test_catalog_coverage.py`

The paid-access worker continues to own its existing fixture and Go paths;
the UI worker consumes only independently reviewed dependency commits. All
workers retain Sol 6.1, medium reasoning, Fast/priority, with no fallback.

## Concrete todo and verification

- [ ] Save and read back the Issue/Project update, commit this plan and record,
  and pass the machine preflight at that exact committed base.
- [ ] Parameterize the existing real PostgreSQL/HTTP configuration-selector
  regression for matching US and differing CA base regions. Verify the actual
  selector observed by each bank and complete exact-configuration coverage.
  Retain the vehicle-only discovery and missing-label/approved-mapping cases.
- [ ] Observe the CA assertion fail before the production correction. Select
  the base region with the existing configuration query, then use it only for
  configuration-scoped resolution. No additional remote calls or migration.
- [ ] Execute the real coverage suite in an owned disposable database/runtime;
  no ordinary skipped database test counts as acceptance. Record raw results,
  input SHA and cleanup. Independently review the exact two-file diff.
- [ ] Commit/push the validated repair, authorize exact dependency merges and
  rerun affected paid/browser acceptance on their reviewed successors.

The existing paid plan permits bounded public selector-only hydration. Its
public-selector measurement must retain actual allowed scopes and completion,
then require unchanged article/model/asset work. Protected denied requests
remain strict zero-work checks against a settled baseline. This clarification
does not authorize public article enumeration or source/processing reads.

No production service, source credentials, cloud resources or customer data
are used by this repair. Staging and release acceptance remain outstanding.

## Verified bounded implementation

Candidate `2d1b6a89a1c1282c0462c97556b983726df08c39` passed independent review and the real13-case coverage suite after the observed CA failure. Integrated at `924fdc447cb2b91b85d4633b077cb8b5b3da76db`. See [retained evidence](../../verification/2026-11-03-workshop-catalog-region.md). Affected paid/browser and final release acceptance remain outstanding.
