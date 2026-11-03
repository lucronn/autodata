# Article catalog discovery and selected content

The November 2026 lifecycle replaces synchronous article hydration with durable
SQL scheduling. `ensure_catalog_hydration` routes `scope=articles` and
`scope=article` through `_ensure_lifecycle_catalog` before any process cache.
Other selector scopes retain their existing behavior.

A catalog ensure proves the requested vehicle/configuration and creates or
reuses one `catalog_index` job independently for Bankone and Banktwo. Workers
resolve each bank's opaque vehicle reference, capture its index and store
list-only descriptors. Index work never fetches article bodies or assets.
A selected article ensure requires its canonical UUID or an explicitly proven
legacy alias. Vehicle, configuration and any supplied bank/opaque references
must match exactly. Ambiguous bindings return `409
ARTICLE_BINDING_REVIEW_REQUIRED`; selectors never widen scope or guess from
article titles.

The selected ensure acknowledgment has exactly `job_id`, `state`,
`canonical_article_id`, `source_revision_id` and `retry_after_seconds`. Pending
work returns 202; readable source or completed content returns 200; review or
exhausted work returns 409. SQL scheduling failure returns 503
`ARTICLE_SCHEDULING_UNAVAILABLE`. The handler performs no source, asset or model
IO. Repeated complete ensures do not mutate jobs or schedule new work.

The dedicated `scripts/dev/article_worker.py` process claims jobs with PostgreSQL
row locks and expiring fencing tokens. Source capture persists immutable raw
snapshots, ordered source projections, evidence and observations before model
work. Reads remain explicit source content until the matching canonical rewrite
publishes. A failed required source upload retains the previous publication.
When changed source is captured, its source projection replaces the older
canonical projection until that new source's transformation publishes.

The reader contract is `catalog_article_current`: canonical identity, source
identity, content origin, availability, processing/retry state and ordered
projections come from SQL. R3 owns the public Go detail/ensure integration and
browser rendering. A warm public detail read must read SQL directly without
calling the ensure service; R2's direct ensure tests prove zero newly scheduled
jobs and zero bank/asset/model calls.

Catalog acknowledgment aggregation returns 202 while any provider has active or
retryable work, 409 when no active work remains and any provider needs review or
has exhausted its budget, and 200 only when both durable jobs completed. Each
provider's job/retry row remains visible, so partial coverage is not erased.
The entire SQL scheduling operation shares a monotonic budget inside two
seconds, including repeated connections and provider lock waits. Each statement
gets the remaining server timeout; expiry cancels active connections and
prevents late connections from executing SQL or late transactions from starting
commit. Timeout rolls back all job writes in that transaction and returns 503.

Offline compatibility mapping is `scripts/dev/backfill_article_lifecycle.py`.
Its default dry-run reports mapped/already-mapped/quarantined/unresolved counts.
`--apply` requires exact provider/vehicle/configuration/opaque article and body
references plus an approved extraction-evidence record bound to the actual
snapshot. Equal titles and numeric-looking references prove nothing. Invalid
mappings create review items; existing legacy job histories remain untouched.

The previous September 2026 synchronous behavior and issue #113 are historical;
current lifecycle work is tracked in issue #186 and the canonical lifecycle plan.
