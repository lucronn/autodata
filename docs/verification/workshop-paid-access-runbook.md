# Paid catalog fixture verification

Use the exact immutable candidate and coordinator-reviewed isolated R3 test image
and service. No live source connector, model, Firebase or Stripe endpoint is used.
The coordinator owns Docker/image/network/container cleanup and final acceptance.
Do not reuse failed run roots or modify retained receipts.

Inside go-test-runner run:

```sh
python scripts/dev/workshop_paid_access_smoke.py --mode fixture --candidate-sha <exact40hex> --output /artifacts/workshop-paid-access.json
```

Set AUTODATA_LIFECYCLE_TEST=1 and the existing AUTODATA_R3_TEST_IMAGE and
AUTODATA_R3_CANDIDATE_SHA for the owned Compose project. Use the reviewed
infra/compose/compose.article-lifecycle-test.yaml image/cache/private network,
read-only plain-clone input and artifact mount, with run --pull never --no-deps.
The collector supplies AUTODATA_CATALOG_INTEGRATION_REQUIRED=1 and
AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION=1 to its child. No new image target,
host port, Docker socket, credential mount or HOME override is required.

The authoritative inventory is six exact Go roots in
apps/api-go/postgres_catalog_access_test.go, each for bankone and banktwo:
GrantBeforeWork, ExactScopeAndOwnerIsolation, PrepareSourceThenCanonicalReuse,
ContextualMediaAndRevocation, HistoricalSourceAndRights and
CustomerLegacyRoutesDenied (each prefixed TestPostgresPaidCatalog). The Python
bridge contains exactly12 parameterized cases; ordinary unit mode skips these
explicit isolated cases, while required mode must execute all12 with zero skips.
Fresh/empty/populated replay uses the real shared migration runner001–040 and
raw eighteen-table snapshots, schema, ledger and driver hashes.

Each case runs the same exact pytest node in an owned process group:114 seconds
plus3 seconds TERM and3 seconds KILL reserve within120 seconds. Go has90 seconds,
capped by the remaining fixture deadline minus cleanup reserve. The outer
collector has1800 seconds; the coordinator supervisor may use1900 seconds plus
its existing resource-cleanup budget. Outer and child JUnit are retained, with
only the outer twelve cases counted as authoritative. Timeout/nonzero/missing
artifact, wrong inventory or any Go skip/fail/extra root prevents passed=true.

Read /artifacts/workshop-paid-access.json and its exact seven-file top inventory.
Each nested case record binds candidate SHA/origin, host-before/input hashes,
provider/Go root/database, exact invariant keys, actual Go exit and timeout,
phase snapshots and the complete per-case artifact inventory. Raw files under
/artifacts/paid-access/<provider>/<GoName>/ include Go JSON/stderr/measurement,
child JUnit/stdout/stderr, measured runtime, fresh/replay SQL output/schema/rows
and result.json. Files are0644 for independent host review. Measurement exposes
only synthetic fixture account/session hashes and safe ledger rows; never raw
session credentials, provider credentials or media capability URLs.

The fixture uses real PostgreSQL039 sessions with identity outcome injection
only at that boundary, actual040 private HTTP grant checks, actual Go TLS HTTP,
real durable ensure/CLI workers/model-response barrier and configured S3 reader.
It proves source-readable processing, canonical step/image preservation,
separately entitled-owner reuse, contextual media and current revocation/rights
without another payment or customer rewrite. The separate five identity,
fourteen commerce and eight R3/040 inventories remain mandatory regressions.
No local compile/unit result is a claim that these runtime cases passed.
