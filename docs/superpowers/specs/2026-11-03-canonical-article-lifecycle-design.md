# Canonical article lifecycle for both banks

**Date:** 2026-11-03  
**Inspected baseline:** `0ed449fe5119484f8dd8f40b40607aa3beb11e49`  
**Workstreams:** R1 and R2 of [production release orchestration](2026-11-03-production-release-orchestration-design.md)  
**Implementation plan:** [canonical article lifecycle](../plans/2026-11-03-canonical-article-lifecycle.md)  
**Project:** https://github.com/users/lucronn/projects/8

**Issue:** https://github.com/lucronn/autodata/issues/186

This is a planning document, not evidence that the lifecycle exists. Issue #186
and its Project #8 item are verified. R1/R2 builders may start only after their
dependencies are integrated and the coordinator supplies the committed exact-base
record required by [the planning gate](../../agents/pre-implementation-gate.md).
This document alone cannot satisfy that gate.

## Outcome and fixed constraints

AutoData publishes one canonical rewritten article per **source item**, with
immutable revisions. Bankone and Banktwo items remain distinct even when their
titles, local IDs, or content hashes match. This release does not establish
cross-bank equivalence and therefore does not merge their articles. Both banks
contribute to the vehicle catalog independently. A selected article always uses
its issuing bank; an outage does not substitute another bank's similarly titled
article.

Source capture, deterministic normalization, model rewriting, validation, and
publication are separate durable states. An immutable, sanitized source document
is readable while transformation is pending or fails. A published canonical
document uses the existing ordered document schema. Repeated reads of a completed
current revision make zero source, asset, model, and ingestion-scheduling calls.

- Implementation and review agents use **GPT-6.1 Sol**, **medium** reasoning,
  **Fast / priority** service, as explicitly requested by the user.
- Use PostgreSQL uniqueness, row locks, leases, and fencing; process-local caches
  are optimizations and cannot decide lifecycle truth.
- Preserve source byte hashes, provider ownership, vehicle applicability, block
  identity/order, technical facts, warnings, tables, evidence, and image positions.
- Generated canonical content is `UNREVIEWED` until an authorized reviewer acts.
  Deterministic validation is not human approval.
- One winning revision and logical publication event are guaranteed. An external
  model request may repeat after an ambiguous crash unless its provider supports
  documented idempotency; record that ambiguity rather than claiming exactly-once
  network execution.
- Do not modify historical migrations 001–036, remove legacy source rows, expose
  provider secrets, call live providers in deterministic tests, or deploy production
  as part of R1/R2.

## Current implementation and required changes

`source_connector_client.py` already validates provider envelopes and resource
hashes. `source_snapshots`/`source_artifacts` store content-addressed blobs;
`catalog_articles` stores source observations. The ordered document, local image
storage, Mercury client, and conservative phrase validator are reusable.

They are not an integrated lifecycle. The selected Banktwo loader discards valid
articles without repeated vehicle identity; rewrite helpers have no intake
callers; a title-only fallback can become permanently complete; hydration cache
locking does not serialize work; and `source_fetch_jobs` has no runtime owner.
The existing `publication_events` relay accepts dataset events only. R1/R2 must
connect these pieces through the interfaces below, rather than extending the
existing in-memory hydration cache into another state machine.

## Identity, versions, and opaque references

`ArticleKey` is the exact tuple:

```python
@dataclass(frozen=True)
class ArticleKey:
    provider: Literal["bankone", "banktwo"]
    vehicle_id: UUID
    vehicle_configuration_id: UUID | None
    source_vehicle_ref: str
    source_article_ref: str
```

`scope_key` is `configuration:<uuid>` when a configuration is proven, otherwise
`vehicle:<uuid>`. A database constraint verifies that the configuration belongs to
the supplied vehicle. The identity key is SHA-256 of compact, sorted-key JSON
containing the five fields above with UUID strings and an explicit JSON null.
`canonical_article_id` is UUIDv5 with `uuid.NAMESPACE_URL` and name
`autodata:article:v1:<identity-key>`. A unique constraint on the tuple is the final
authority, independently of deterministic UUID generation.

Validate opaque reference length and prohibited control characters, but never
split, case-fold, strip prefixes, extract suffixes, interpret as URLs, or guess
from titles. Every resource is a `ResourceRef(provider, opaque_ref)`. The registry
lookup uses that explicit provider. Identical refs from two banks are different
resources. Resource cache keys are `(provider, opaque_ref)` within one capture;
descriptor, body-declared asset, and localization reads share this cache.

Canonical scope is not silently widened. A configuration-specific item cannot
replace a vehicle-wide or another configuration's item. Multiple source vehicle
refs for one canonical vehicle remain separate keys unless an explicit reviewed
mapping is later established outside this release.

The **source fingerprint** hashes canonical JSON containing the issuing provider,
body ref, body SHA-256, body media type, and the ordered resource manifest. Each
manifest entry contains role, opaque ref, verified hash/media type when available,
and explicit failure code when unavailable. Provider revision strings, request
IDs, timestamps, and locators are provenance, not content identity. Therefore a
revision-string-only refresh with unchanged bytes/assets reuses the source
revision and completed transformation. A byte, descriptor-asset-order, or asset
availability change creates a new source revision. Observations preserve every
provider revision and retrieval even when the content fingerprint is unchanged.

The **transformation key** is SHA-256 of compact, sorted-key JSON containing
`canonical_article_id`, `source_fingerprint`, `normalization_version`, and
`rewrite_profile_version`. Initial versions are `ordered-article-v1` and
`technical-prose-v1`. Model identity, prompt hash, generation parameters, and
attempt metadata are stored with the result; changing the selected model or
rewrite rules requires a new rewrite profile version. Routine retries never
change versions implicitly.

## Schema changes

Reserve migration numbers **037** and **038** for this work at the inspected
baseline. The coordinator must serialize these migrations before other builders
and re-pin all consumers if another migration lands first. New foreign-key
columns and tables are additive; existing article IDs, snapshot UUIDs, legacy
job UUIDs, retry state, and dataset publication behavior remain intact.

### 037_article_source_lifecycle.sql

Create `canonical_articles` with:

| Column | Type / invariant |
| --- | --- |
| `canonical_article_id` | UUID primary key |
| `provider_slug` | text, `bankone` or `banktwo` |
| `vehicle_id`, `vehicle_configuration_id` | UUID FKs; configuration nullable and belongs to vehicle |
| `scope_key` | text, exact scope construction above |
| `source_vehicle_ref`, `source_article_ref` | nonempty bounded text, preserved exactly |
| `identity_key` | 64 lowercase hex characters, unique |
| `descriptor`, `descriptor_source_snapshot_id` | object JSON and raw index snapshot FK |
| `title`, `kind`, `component`, `source_sort_order` | list metadata; no article body fetch needed |
| `request_generation` | nonnegative bigint, starts at 0 |
| `target_normalization_version`, `target_rewrite_profile_version` | text, initially `ordered-article-v1` and `technical-prose-v1`; changed only by explicit profile refresh |
| `current_job_id`, `current_source_revision_id` | nullable FKs added after their target tables exist |
| `last_seen_catalog_generation` | nonnegative bigint |
| `membership_status`, `takedown_status` | `active|retired`; `active|takedown|expired` |
| `created_at`, `updated_at` | timestamptz |

Add `UNIQUE(provider_slug, scope_key, source_vehicle_ref, source_article_ref)`.
Configuration ownership is enforced by a composite FK to a new unique index on
`vehicle_configurations(vehicle_configuration_id, vehicle_id)`, with ordinary
null semantics for the coarse vehicle scope.

Create `canonical_article_source_revisions` with `source_revision_id` UUID PK,
`canonical_article_id` FK, `source_fingerprint`, `body_source_snapshot_id` FK,
`resource_manifest` JSON array, `source_document` JSON object, `source_images`
JSON array, `source_body` text, `source_steps` JSON array, `projection_version`
text fixed to `source-projection-v1`, `projection_status` (`readable|partial`),
`evidence_manifest` JSON array, and `captured_at` timestamptz. Require
`UNIQUE(canonical_article_id, source_fingerprint)` and a composite unique key on
`(source_revision_id, canonical_article_id)` for ownership FKs. A trigger rejects
UPDATE and DELETE: projection and media availability are immutable. A title-only
or malformed response never creates a readable source revision.

Create `canonical_article_source_observations` with observation UUID PK,
canonical/source revision FKs, fetch job FK, request generation, body provider
revision, resource provenance JSON array, descriptor snapshot FK, and captured
time. `UNIQUE(source_fetch_job_id)` prevents replay observations. The provenance
array records each resource's provider, opaque ref, locator, request ID, revision,
fetched time, media type, blob snapshot ID and SHA-256, or redacted failure code.
Keep this separate from the shared blob row: `source_snapshots` is unique by
hash, so its original adapter name cannot establish ownership of another bank's
identical bytes.

Create `canonical_article_aliases` with `catalog_article_id` UUID PK/FK,
`canonical_article_id` FK, proof JSON object, and mapped time. Add nullable
`canonical_article_id` FK to `catalog_articles`. Preserve all old rows and
`catalog_article_vehicle_links`; new lifecycle reads do not use fuzzy duplicate
links to collapse source items. The alias table maps only proven identity triples
and vehicle scope. New ingestion writes canonical tables; `catalog_articles`
continues to support legacy observations and non-bank intake until its own
migration, without becoming a second publication store.

Extend `source_fetch_jobs` rather than creating another queue:

| Added column | Type / invariant |
| --- | --- |
| `job_kind` | `legacy_batch|catalog_index|article`, default `legacy_batch` |
| `canonical_article_id`, `catalog_provider_scope_id`, `source_revision_id` | nullable FKs; exactly the appropriate owner for new job kinds |
| `request_generation` | nonnegative bigint |
| `phase` | `queued|fetching_source|normalizing|rewriting|validating|publishing|completed` |
| `transformation_key` | nullable 64-hex text, unique when present |
| `normalization_version`, `rewrite_profile_version` | nonempty text for article jobs |
| `lease_owner` | nullable UUID |
| `lease_token` | bigint, starts at 0 and increases on every claim |
| `lease_expires_at`, `heartbeat_at`, `next_attempt_at` | nullable timestamptz |
| `max_attempts` | positive integer, default 3; cannot exceed the frozen policy budget |
| `error_code`, `retryable` | nullable redacted code, boolean default false |
| `correlation_id` | UUID, generated once |

Existing `retry_count` remains the persisted count of claims/attempts; do not reset
the historical values. New jobs use status `pending|processing|completed|
needs_review|failed|dead_letter`, preserving migration 036's vocabulary. A partial
unique index on `canonical_article_id` for new article jobs in
`pending|processing|failed` allows only one active job per article. A second
unique key is `(canonical_article_id, request_generation)` for article jobs.
New `processing` rows require all lease fields; terminal rows have no lease.
Imported `legacy_batch` rows are excluded from these new checks and claims.

Create `catalog_article_provider_scopes` with UUID PK, vehicle/configuration
scope, provider, exact nullable resolved vehicle ref, generation, completed
generation, `status` (`pending|running|complete|partial|failed|needs_review|
not_configured`), current job FK, next cursor, row count, error code, retry time,
and timestamps. Require `UNIQUE(scope_key, provider_slug)`. Create
`catalog_article_index_pages` keyed by `(catalog_provider_scope_id, generation,
page_number)` with raw snapshot FK, request ID, provider revision, cursor-in,
cursor-out, and complete flag. Persist original envelope bytes; do not fabricate
a JSON index and label it the exact source response.

Add `content_partial` to the legacy `catalog_articles.content_status` check so
legacy projections can describe fetched-but-incomplete content honestly. Do not
backfill any row to canonical-complete from its legacy content status.

### 038_article_transform_publication.sql

Create `canonical_article_revisions` with UUID PK, canonical/source revision FKs,
transformation key (unique), normalization/rewrite versions, status
(`building|validated|published|rejected`), normalized source document/hash,
canonical document/body/steps/images, validation report/hash, rewrite result hash,
model metadata JSON, review status (`UNREVIEWED|APPROVED|REJECTED`, initially
`UNREVIEWED`), created time and nullable published time. Require
`UNIQUE(canonical_article_id, source_revision_id, normalization_version,
rewrite_profile_version)` and `CHECK((status='published')=(published_at IS NOT
NULL))`. Composite ownership FKs prevent cross-article pointers. Publication
requires nonempty document blocks, passed validation, changed eligible prose,
nonempty model/profile metadata, and source/evidence references. SQL enforces
presence/shape; Python performs semantic checks and stores their report.

Published revision content is immutable via trigger. Review changes use a separate
append-only `canonical_article_reviews` table (review UUID, revision FK, authorized
reviewer identifier, decision, reason, timestamp); they do not mutate a published
document. The read view uses the latest review decision, or `UNREVIEWED`. R5 owns
authorization for review writes; R1/R2 exposes no public approval endpoint.

Create `canonical_article_rewrite_attempts` with UUID PK, job/revision FKs, lease
token, attempt number, provider/model/profile, prompt/input hashes, status
(`prepared|dispatched|succeeded|failed|ambiguous`), bounded response JSON/hash,
redacted error, and timestamps. Unique `(source_fetch_job_id, lease_token,
attempt_number)`. Store no credentials, upstream authorization headers, or secret
query parameters. Successful output is committed before publication and reused
after a restart.

Add `current_canonical_revision_id` to `canonical_articles`. Add nullable
`canonical_article_id` and `canonical_article_revision_id` FKs to
`publication_events`; dataset identifiers remain nullable for catalog events.
For `catalog.article.published`, require article/revision identifiers, version 1,
and null dataset identifiers. Unique partial index on
`(event_type, canonical_article_revision_id)` enforces one logical publication.
`idempotency_key` remains globally unique.

Add outbox delivery lease owner/token/expiry and `next_delivery_at`, and add
`processing` to `delivery_status`. Update the common relay to fence claims and
marks for both dataset and catalog events. Preserve dataset envelope requirements;
catalog events have their own explicit envelope with article, source revision,
canonical revision, correlation, event ID/version and idempotency key. No fake
dataset UUIDs or string `"None"` values. Route catalog events to a separate
`AUTODATA_CATALOG` JetStream stream with subjects `catalog.>`.

Create the `catalog_article_current` view described below. It is the shared read
contract for R3; HTTP and Workshop fields are owned by R3/R4, not Python.

### Upgrade and legacy policy

Migration 036's imported legacy jobs remain historical, unchanged audit records.
Stop new writes to `autoapi_article_fetch_jobs`. Compatibility batch entrypoints
use `source_job_persistence.py`; an imported batch lacking proven opaque bindings
cannot be claimed as a new article job. Binding it creates a new article job and
records the imported parent job in checkpoint metadata. Re-running 036 therefore
still finds exactly preserved legacy identity/status/retry/snapshot fields.

`scripts/dev/backfill_article_lifecycle.py` runs offline with `--dry-run` by
default and accepts an explicit JSON mapping file. Each entry contains legacy
catalog row UUID, provider, source vehicle/article refs, vehicle/configuration
scope, and source evidence proving that mapping. It verifies the full identity,
never uses title/suffix/fuzzy matches, and records unproven rows in
`source_review_items`. With `--apply`, alias creation, source projection creation,
and queued job creation commit atomically. Legacy source content is never silently
treated as a verified rewrite. An unmapped legacy row is a source-only compatibility
view with null lifecycle IDs/state; no auto-poll and no guessed rewrite request.
The release gate requires every active served legacy row mapped or explicitly
quarantined, with an auditable count; quarantined content is not silently deleted.

## Durable job protocol

`POST /v1/catalog/ensure` accepts an already authorized canonical article or exact
catalog scope and schedules work only. It must commit or return an error within
the caller's two-second deadline. It performs no provider/model/object-store
operation. Article lookup by canonical ID is scope-checked; unmanaged ambiguous
legacy IDs return a nonretryable identity-review result.

`ensure_article_job` locks the canonical row. If the current source/profile has a
published revision, return it without creating a job. Otherwise return its active
or terminal current job, or create one when there is no job at the current request
generation. Automatic retries belong to that job. Browser refresh cannot reset
`needs_review` or `dead_letter`. A requested profile different from the canonical
row's target versions returns `PROFILE_REFRESH_REQUIRED`; only the explicit
operator refresh may change those targets. An operator
refresh, with actor/reason, increments generation after the prior active job ends
and creates a fetch job; if work is active it joins that job and does not cancel it.
Refresh authorizes a source inspection, not another attempt budget for an existing
transformation. There is no operator or browser reset/resume operation for an
exhausted transformation in this release.

Workers poll due durable rows every one second. Claims use a short transaction:

```sql
SELECT source_fetch_job_id
FROM source_fetch_jobs
WHERE job_kind IN ('article', 'catalog_index')
  AND retry_count < max_attempts
  AND ((status IN ('pending', 'failed') AND
        COALESCE(next_attempt_at, '-infinity'::timestamptz) <= clock_timestamp())
       OR (status = 'processing' AND lease_expires_at < clock_timestamp()))
ORDER BY created_at, source_fetch_job_id
FOR UPDATE SKIP LOCKED
LIMIT 1;
-- In the same transaction: status=processing, retry_count=retry_count+1,
-- lease_token=lease_token+1, lease_owner=:worker_uuid,
-- lease_expires_at=clock_timestamp()+interval '90 seconds'.
```

Before claiming, the same worker sweep transitions expired `processing` jobs
already at `max_attempts` to `dead_letter:LEASE_ATTEMPTS_EXHAUSTED`, clears their
lease, and records the failure. Otherwise the claim predicate would leave an
exhausted crashed worker permanently processing. This sweep uses row locks and
the expired token, so it cannot terminate a renewed lease.

Use database time; heartbeat every 10 seconds with owner/token matching. Every
checkpoint, source commit, output commit, failure, and publication checks owner,
token, status and unexpired lease under the job row lock. Updating zero rows means
`LeaseLost`: abandon the result without source/current-pointer publication. No DB
transaction remains open during external IO. On reclaim, resume the persisted
phase; do not fetch source or call the model again if the next phase already has
durable input/output.

Retry transport timeouts, 429 and 5xx source/model failures after 5 and 30
seconds for attempts 1 and 2; attempt 3 becomes `dead_letter`. Three total
claims matches the existing persistence default and stays within the frozen
policy retry limit. Do not silently increase that budget. Clamp a valid provider
Retry-After to 1–900 seconds and use the greater of that and scheduled backoff.
Unauthorized configuration, ambiguous vehicle resolution, bad hash/envelope,
wrong applicability, malformed/changed technical content and unchanged rewrite
are `needs_review`, with explicit error codes. These are not hidden retries.
An exact selected resource that returns 404 is `needs_review:SOURCE_NOT_FOUND`;
never try another bank or descriptor with the same title.
Missing model configuration is `needs_review:MODEL_NOT_CONFIGURED`, leaving source
readable. Process death is recovered by expiry without a manual retry request.

One current-generation source commit transaction performs all of:

1. Check live lease and canonical request generation.
2. Insert immutable source revision or select the existing fingerprint.
3. Insert its source observation and raw resource/evidence links.
4. Point the canonical article at that source revision and current job.
5. Look up the transformation key's existing owner before assigning it. If it has
   a matching published transform, bind that revision and complete the inspection
   without model work. If its result is unsuccessful and terminal, apply the
   terminal-reuse rule below. Only a previously unowned key may be attached to
   this job and advanced to `normalizing`.

If the unchanged fingerprint/profile already belongs to a rejected,
`needs_review`, or `dead_letter` transformation, complete the refresh inspection
with `reused_terminal_result` and `reused_transformation_job_id` in its checkpoint.
Leave the refresh job's `transformation_key` null; the prior job retains the unique
key, status, error, retry count, maximum attempts and immutable persisted results.
Keep the new provenance observation and readable source revision, and point the
canonical article's processing state at that existing terminal job in the same
transaction. `ensure_article_job` returns this authoritative current-job pointer
even when its original generation predates the inspection generation; it must
not create another job because of that generation difference. No model call,
new transformation revision, publication event or attempt reset occurs. This
includes exhausted model transport failures that have no revision row yet.
A new source fingerprint or an explicitly selected new profile is required for
another transformation. A future bounded operator-resume feature requires its
own approved design and is outside this release.

Blob upload precedes the transaction and uses content-hash object keys. Verify
successful storage before creating references. An upload followed by rollback may
leave an unreferenced blob; it must never expose half-written content. Object-store
failure preserves the old readable view and leaves the new job retryable. Garbage
collection of such blobs is outside this release; no destructive cleanup is added.

If a recovered `dispatched` model attempt has no persisted result, record
`ambiguous` and retry only within the job's bounded attempt budget. Completed
results and validation reports are immutable inputs to later stages. Transport
success followed by worker death can produce another external invocation; only
one revision/event can win publication.

## Provider intake and catalog union

For each canonical scope, schedule one independent catalog job per configured
bank. Missing production configuration is `not_configured`, not empty success.
Use verified vehicle mappings when present; otherwise call that bank's resolution
endpoint. One candidate binds the scope; a successful zero-candidate response
completes that bank's scope as empty with `NO_MATCHING_SOURCE_VEHICLE` evidence;
multiple candidates require review. An unavailable/error response never counts as
empty coverage. Persist the resolution envelope and
the scope/ref binding as evidence. No bank may borrow the other's opaque refs.

Read every index page within the existing 1,000-page bound, rejecting repeated or
missing cursors, and persist raw page bytes plus each page's own revision. Persist
metadata rows after each page. Nonempty partial rows remain usable. Union
`complete=true` only when both configured production banks have a complete current
generation; a complete empty result counts as complete coverage for that bank.
Failures and ambiguity remain visible per bank. Successful Bankone enumeration
never suppresses Banktwo. Unconfigured providers keep production coverage
incomplete. Display ordering is provider order (`bankone`, `banktwo`), source page
and item order, then canonical ID for a deterministic tie.

An item disappears from the active catalog only after its own bank finishes a
complete newer generation without that item. Partial/failed scans cannot retire
old rows. Repeated identical descriptors in a scan are deduplicated by the exact
identity; conflicting descriptors for the same ref in one generation require
review. Browsing indexes never fetches article bodies, assets, labor or model
output. Selecting one item fetches only that item's descriptor-bound resources.
Retirement removes catalog membership, not an otherwise authorized immutable
historical article read. Takedown/expiration separately suppresses all views.

Fetch body plus declared labor/assets through the selected client's registry.
Use at most four parallel asset reads and a 30-second whole-capture deadline;
individual source timeouts cannot exceed the remaining deadline. Reuse verified
bytes for localization. Body failure is retryable/reviewable according to the
error mapping; optional asset/labor failure is recorded as unavailable/partial
without inventing content. An article body is not conditioned on labor success.

The typed `SourceArticleContext` includes the proven vehicle resolution and exact
descriptor. Pass this context to the shared adapter rather than requiring HTML,
PDF, or plain text to repeat vehicle fields. If a body explicitly contradicts
the resolved vehicle, quarantine it. Associate its article title/identity from the
descriptor only when the fetched body has readable article content; a title is
never body content. Keep arbitrary-URL intake's stricter independent-vehicle
proof rules; the trusted connector context does not weaken that unrelated route.

## Immutable source fallback and normalization

Create the source projection from actual fetched bytes and typed adapter blocks,
not a provider-supplied `source_original` field or a synthetic index. Store exact
raw bytes in the existing content-addressed object store and retain the source
revision's body snapshot reference. The source projection uses the same ordered
document schema as canonical output, with HTML sanitized to text/semantic blocks,
no script/event handlers, no executable URLs, and no direct provider image URLs.
Images are local opaque assets or explicit unavailable placeholders in position.
Unknown blocks retain sanitized readable content/locator/evidence and cause
`needs_review` for canonical publication.

All source projection and media states are immutable. A later successful media
recapture creates a new source fingerprint/revision. R3/R4 can identify a view by
`(content_origin, source_revision_id, canonical_revision_id)`; they may derive a
`view_revision` digest including policy projection, excluding randomized media
tokens. Processing progress can update without replacing the document.

Run `normalize_procedure_article` on this immutable input and store the normalized
source document/hash. Extend `validate_ordered_document` recursively to require
unique block IDs, valid order and supported nested structures, readable content,
evidence for every retained block, tables with valid cell arrays, and images
either local/verified or explicitly unavailable with reason and evidence. Do not
infer completeness from text length, one step, or a caller-supplied status.
`article_is_content_complete` remains a structural compatibility helper; only
published lifecycle state establishes API canonical completeness.

## Mercury integration and strict rewrite validation

Reuse `Mercury2Client.from_environment()` and the existing `procedure_rewrite.py`
phrase-validation helpers. Its new typed `rewrite_ordered_document` entrypoint is
called by the lifecycle worker and by the compatibility
`rewrite_procedure_article` wrapper. It accepts the authoritative ordered document
directly, including eligible paragraph/list/step text leaves; remove the current
dependency on finding every compatibility step as an exact top-level `step`
block. Preserve `rewrite_steps_for_diy` for legacy callers, implemented through
the same phrase-validation policy.

The model receives numbered editable text slots with block IDs and JSON paths,
plus immutable context. It returns only `replacements:[{block_id,path,text}]` for
the declared slots. Model JSON is limited to 1 MiB and the source prompt to 200 KiB;
larger content remains source with `needs_review:REWRITE_INPUT_LIMIT`, rather than
silent truncation. External text is data, never an instruction to change workflow.

`technical-prose-v1` deliberately uses the existing verified equivalence families
for opening phrases (`remove/take off/lift off`, `install/fit/seat`,
`discard/toss`). Extend the existing helper's application to document slots, not
its permitted semantic scope. Exact remainder must match after that substitution.
Any text containing numbers, units, warning/caution/danger/note/notice, negation,
obligation, applicability, part/tool identifiers, or specification labels is
copied verbatim. Headings, tables and cells, links, captions, identifiers,
block/order/evidence fields, image positions, operation metadata, and all
nontext fields are copied verbatim. This rejects unsupported paraphrases rather
than trusting a second model to approve them.

Validator requirements are deterministic:

- Every declared editable slot appears exactly once; no extra paths, duplicates,
  missing content, blank replacements, reordering, or shape changes.
- Changed wording passes the conservative equivalence validator; all protected
  strings and noneditable fields remain byte-equivalent in canonical JSON.
- The recursively ordered block skeleton, image references, technical facts,
  applicability, warnings, evidence and tables match the source baseline.
- At least one eligible prose slot changes beyond whitespace/case-only changes.
  Identical output is `needs_review:REWRITE_UNCHANGED`; documents with no safe
  editable slots are `needs_review:REWRITE_NOT_APPLICABLE`. Neither is described
  as rewritten. Such content remains available as source, not a failed read.
- Canonical body/steps/images are regenerated from the accepted authoritative
  document. Do not regenerate an abbreviated document from compatibility steps.

Persist source/target protected-content hashes, skeleton hash, changed slot IDs,
model/profile/prompt metadata and validator version in the validation report.
Unsafe output is retained for authorized review with `rejected` revision state;
it never replaces a source or published document. Supporting broader editorial
rewrites requires a separately versioned reviewed profile; this release does not
pretend arbitrary paraphrases can be proved equivalent by keyword matching.

## Atomic publication and outbox

`publish_article_revision` uses one database transaction: lock job then canonical
article; verify owner/token/unexpired lease/current request generation and source
pointer; verify the persisted candidate and validation hashes; mark the revision
published; set the canonical current pointer; complete the job; insert the outbox
row. The event key is `catalog.article.published:<transformation-key>`. Conflict
replay must select the same immutable revision/event, not overwrite either.
Failure at any statement rolls back all publication effects.

A late result for an older source generation cannot change a current pointer or
emit a new event. Published history remains retained. Source changes explicitly
observed by refresh set the new source pointer; reads show that source while its
new canonical transform is pending. Before a new capture commits, the old readable
view remains available with current fetch processing status. A revision-string-
only refresh of unchanged content completes by reuse. Freshness checks are an
explicit operator/scheduled sync action, never an implicit warm detail read.

Outbox delivery is at least once. Claim with a lease, publish with stable
`Nats-Msg-Id`, then mark delivered with fencing. A crash after broker ACK and before
DB mark may redeliver the same event ID/key. Subscribers must deduplicate that key;
the API reads PostgreSQL and does not wait on NATS for the canonical switch. Broker
outage leaves a durable pending event and does not undo published content.

## Shared read contract for R3/R4

`catalog_article_current` returns these named columns:

```text
canonical_article_id, vehicle_id, vehicle_configuration_id,
title, kind, component, provider_slug, source_vehicle_ref, source_article_ref,
source_revision_id, canonical_revision_id, content_origin, availability,
document, images, body, steps,
job_id, processing_state, retryable, retry_after_seconds, processing_error_code,
review_status, updated_at, takedown_status,
source_snapshot_id, source_content_sha256, source_version,
source_media_type, source_captured_at
```

Internal opaque refs, object keys and source locators stay server-side. The view
chooses canonical only when a published, nonrejected revision matches the current
source and configured profile. Otherwise it chooses the current readable source.
No source gives null origin/document. `availability` is `available` for readable
source/canonical, `pending` for active/no-content work, and `unavailable` for
terminal/no-content work. Takedown/expiration of the identity or any referenced
blob suppresses content; R5 checks authorization for every selected representation.

`processing_state` is `queued|fetching_source|normalizing|rewriting|validating|
publishing|completed|failed|needs_review`. `dead_letter` maps to `failed` with
`retryable=false`; retryable failed work has a DB-derived retry delay. Null
processing is allowed only for unmanaged legacy compatibility, or before a cold
ensure has durably acknowledged. `review_status` is `UNREVIEWED|APPROVED|REJECTED`;
source defaults to `UNREVIEWED`. API `complete` means a published matching canonical
revision, never successful normalization or source readability.
An authorized rejection of a previously published revision makes the view fall
back to source and reports `needs_review:CANONICAL_REVIEW_REJECTED` using the
durable review record; it does not relabel the rejected artifact or start another
model job. The immutable published artifact remains auditable.

R3 uses HTTP 200 for readable source/canonical, 202 only with a durable pending
job and no content, 503 for unavailable temporary dependencies/no content, 409 for
terminal review/processing failure without content, and 410 for takedown. A source
view with an existing job is a DB-only 200; browser
retry rereads it and cannot reset terminal work. Source and transformation job
creation are atomic so no managed source is exposed with fabricated processing.

## Ownership and interfaces

| Owner | Paths / boundary |
| --- | --- |
| R1 schema/job builder | migrations 037/038 serialized together before consumers; `article_lifecycle_types.py`, `article_lifecycle_store.py`, `source_job_persistence.py`, `catalog_coverage.py`, `backfill_article_lifecycle.py`; new DB/identity/job tests |
| R1 provider builder, after schema interfaces | `source_connector_client.py`, `source_article_capture.py`, `source_adapters.py`, `procedure_images.py`; provider fixture tests |
| R2 transform builder | `article_lifecycle.py`, `procedure_rewrite.py`, `procedure_normalize.py`, `article_document.py`; transformation/publication tests; consume frozen migration 038 |
| R2 outbox builder, serialized after 038 | enrichment `outbox.py`, event contracts and outbox tests; separate catalog event envelope |
| Coordinator integration | `catalog_service.py`, `worker.py`, `http_service.py`, batch compatibility, runtime command configuration; shared files are edited once after producer integration |
| R3/R4 | Go stores/routes/OpenAPI, Workshop and browser tests; consume the SQL view/DTO without writing Python state |

`article_lifecycle_types.py` defines immutable `ArticleKey`, `ResourceRef`,
`SourceArticleContext`, `CapturedSource`, `JobLease`, `EnsureResult`,
`RewriteResult`, and `ValidationResult`. UUIDs are `uuid.UUID`; timestamps are
timezone-aware UTC `datetime`; document values are JSON-compatible mappings.
`Repository` is a connection-factory protocol with `connect() -> psycopg.Connection`;
connections and transactions are never shared across worker processes.

| Type | Exact public fields |
| --- | --- |
| `ResourceRef` | `provider: str`, `opaque_ref: str`; frozen/hashable |
| `SourceArticleContext` | `key: ArticleKey`, `vehicle: dict`, `descriptor: dict`, `descriptor_snapshot_id: UUID`, `resolution_snapshot_id: UUID`, `evidence_ids: tuple[str, ...]` |
| `CapturedSource` | `context: SourceArticleContext`, `source_fingerprint: str`, `body_source_snapshot_id: UUID`, `resources: tuple[dict, ...]`, `resource_manifest: list[dict]`, `resource_provenance: list[dict]`, `source_document: dict`, `source_images: list[dict]`, `source_body: str`, `source_steps: list[dict]`, `evidence_manifest: list[dict]`, `projection_status: str`, `captured_at: datetime` |
| `JobLease` | `job_id: UUID`, `worker_id: UUID`, `token: int`, `generation: int`, `kind: str`, `phase: str`, `canonical_article_id: UUID | None`, `catalog_provider_scope_id: UUID | None`, `source_revision_id: UUID | None`, `normalization_version: str`, `rewrite_profile_version: str`, `checkpoint: dict`, `expires_at: datetime` |
| `EnsureResult` | `job_id: UUID`, `canonical_article_id: UUID | None`, `state: str`, `source_revision_id: UUID | None`, `retry_after_seconds: int | None`, `published_revision_id: UUID | None`, `created: bool` |
| `RewriteResult` | `document: dict`, `changed_slots: tuple[str, ...]`, `raw_response: dict`, `input_hash: str`, `output_hash: str`, `prompt_hash: str`, `model_metadata: dict`, `profile_version: str`, `error_code: str | None` |
| `ValidationResult` | `passed: bool`, `error_codes: tuple[str, ...]`, `report: dict` |

`CapturedSource.resources` entries contain exact provider/ref/role/media type,
verified content SHA, content-addressed object key, deterministic snapshot UUID,
source revision/request/time/locator, and evidence metadata. No raw provider
credentials are included. Source commit inserts those blob/evidence rows before
referencing their IDs. `load_source_revision` is an internal store method returning
the immutable source plus context; its `as_article()` returns the existing article
mapping shape and `vehicle` returns the resolved canonical vehicle mapping.

```python
# article_lifecycle_store.py (Repository is a psycopg connection factory)
upsert_article_descriptor(repo, key: ArticleKey, descriptor: dict,
                          descriptor_snapshot_id: UUID, generation: int) -> UUID
store_captured_source(repo, lease: JobLease, captured: CapturedSource) -> UUID
load_article_state(repo, canonical_article_id: UUID) -> dict
store_rewrite_result(repo, lease: JobLease, result: RewriteResult) -> UUID
publish_article_revision(repo, lease: JobLease, revision_id: UUID) -> UUID

# source_job_persistence.py
ensure_article_job(repo, canonical_article_id: UUID, *,
                   normalization_version: str, rewrite_profile_version: str) -> EnsureResult
refresh_article_job(repo, canonical_article_id: UUID, *, actor: str, reason: str,
                    normalization_version: str | None = None,
                    rewrite_profile_version: str | None = None) -> EnsureResult
claim_source_job(repo, *, worker_id: UUID) -> JobLease | None
heartbeat_source_job(repo, lease: JobLease) -> bool
advance_source_job(repo, lease: JobLease, *, phase: str, checkpoint: dict) -> None
fail_source_job(repo, lease: JobLease, *, code: str, retryable: bool,
                retry_after_seconds: int | None = None) -> None

# source_article_capture.py; registry values are SourceConnectorClient instances
capture_source_article(context: SourceArticleContext, *, registry: dict,
                       object_store, deadline_seconds: float = 30.0) -> CapturedSource

# catalog_coverage.py
ensure_article_catalog_jobs(repo, *, vehicle_id: UUID,
                            vehicle_configuration_id: UUID | None) -> tuple[EnsureResult, ...]
run_catalog_index_job(repo, lease: JobLease, *, registry: dict, object_store) -> None

# procedure_rewrite.py; compatibility wrapper returns the article mapping
rewrite_ordered_document(document: dict, *, client, context: dict,
                         profile_version: str = "technical-prose-v1") -> RewriteResult
validate_article_rewrite(source: dict, candidate: dict, *, profile_version: str) -> ValidationResult

# article_lifecycle.py
run_article_job(repo, lease: JobLease, *, registry: dict, object_store, model_client) -> None
run_article_worker_once(repo, *, worker_id: UUID, registry: dict,
                       object_store, model_client) -> bool
```

`JobLease` contains job UUID, worker UUID, token, generation, kind, phase, canonical
article/scope UUID, source revision UUID, normalization/rewrite versions, checkpoint
and expiry. `EnsureResult` contains `job_id`, `canonical_article_id`, `state`,
`source_revision_id`, `retry_after_seconds`, `published_revision_id` and `created`.
The internal HTTP response exposes the first five names only; it never returns a
fabricated job ID, and a 2xx status alone does not imply complete content.
`CapturedSource` carries context, immutable source projection,
verified resources/evidence/provenance and fingerprint. `RewriteResult` contains
candidate document, changed slots, raw bounded response, input/output/prompt
hashes, model/profile metadata and error code. `ValidationResult` has `passed`,
error codes and the exact report/hashes needed by publication. Errors crossing
the HTTP boundary are stable redacted codes; `LeaseLost` is internal control flow.

## Acceptance evidence

Use a standalone internal-network fixture Compose project with PostgreSQL,
JetStream, the repository-pinned SeaweedFS image, and a test runner. It has no host
ports, shared application volumes, host secrets/env files, or external runtime
network. Within the runner, bind two independent Source Connector v1 servers and
a deterministic Mercury-compatible server to loopback; spawn two real worker
processes with explicit fixture-only environment. Model/source call counters and
pause/crash barriers are controlled by the fixture server. The tests use actual
adapters, SQL transactions, object storage, worker checkpoints, and outbox relay.

Required matrix:

1. Each bank alone returns a descriptor-bound HTML/plain-text/JSON/PDF article
   without repeated vehicle fields; both together return a union. One failure,
   empty complete page, partial pagination, repeated cursor, and ambiguous vehicle
   retain accurate independent coverage. Index reads fetch zero bodies/assets.
2. Equal opaque refs and equal titles/bytes across banks create two canonical
   identities. Same-bank replay preserves one identity. Asset refs with no prefix,
   colons/slashes and identical names route only to their owner; each resource is
   fetched at most once during a successful capture.
3. Twenty same-key ensures through two processes produce one active job. Pause
   before provider/model requests and prove only one lease holder executes them.
   Exactly one source revision, transform revision and outbox event are published.
4. Expire worker A's lease, let worker B claim token N+1, then release A. Every
   stale checkpoint/source/result/publication write fails; only B can finish.
5. Kill before source commit, after source commit, after model dispatch without
   result, after result commit, inside publication transaction and after outbox
   ACK. Assert the specified resume point, ambiguous-call record where necessary,
   no half-publication, and one logical event after redelivery.
6. Inject object-store, PostgreSQL and broker outages independently. No source
   pointer references failed uploads; old/source views remain readable when
   possible; published content survives broker failure; retries obey the schedule
   and exhausted jobs never become immortal `processing` rows.
7. Reject title-only, malformed, unknown-block, numeric/unit/torque/tool/part,
   warning/negation/applicability, table, block/order/image/evidence mutations and
   unchanged model output. Source remains readable and canonical `complete=false`.
8. Freeze the model fixture after source commit. Source/view/job are present
   atomically; API consumers can read without model completion. Valid result
   switches atomically to the canonical document, still `UNREVIEWED`.
9. Restart both workers and issue 100 completed warm reads/ensures. Source,
   asset, model and schedule counters stay zero. Explicit changed-content refresh
   creates a new immutable revision under the same canonical ID; revision-only
   unchanged content reuses publication and makes no model call.
   Also exhaust a transformation's three transport attempts in real PostgreSQL,
   then explicitly refresh unchanged content/profile through two workers. The
   inspection completes with one additional source observation and no unique-key
   error; the old job retains its key, `dead_letter` status and attempt count,
   remains the current processing job, and source remains readable. Repeated
   ensures after refresh/restart make zero provider/model/scheduling calls and
   create no revision/event. Changed content or an explicit new profile may
   create a different transformation; unchanged refresh cannot.
10. Apply migrations cleanly, upgrade seeded 001–036 data, run 036 again, and
    verify imported UUIDs/idempotency/retry/snapshot links are unchanged. Exercise
    explicit alias mappings and reject ambiguous ones. Enforce ownership FKs,
    published/source immutability, and unique keys using actual PostgreSQL races.

No fixture or public health probe certifies live integration. Authenticated
per-bank staging canaries, rights/access checks, external model behavior, recovery
and release gates remain R5/R6 evidence at the final candidate SHA.
