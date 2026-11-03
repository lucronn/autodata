# Source fallback API and Workshop design

**Date:** 2026-11-03  
**Inspection baseline:** `0ed449fe5119484f8dd8f40b40607aa3beb11e49`  
**Workstreams:** R3 and R4 of [production release orchestration](2026-11-03-production-release-orchestration-design.md).  
**Status:** reviewed design linked to Issue #186 / Project #8; no implementation or release completion is claimed. Dependent builders still require their synchronized exact-base gate.  
**Project:** https://github.com/users/lucronn/projects/8

**Issue:** https://github.com/lucronn/autodata/issues/186

## Outcome and boundaries

Opening an article returns readable source content while its AutoData rewrite is
prepared. The source and completed canonical revision use the existing ordered
document DTO and renderer. Failure retains an available source view. A completed
revision is reused on later reads without contacting a bank or model.

R1/R2 own provider identity, source fetching, source-to-document projection,
rewriting, quality decisions, durable jobs, migrations, and immutable publication.
R3 owns authorized reads of those records, public projection, bounded scheduling,
HTTP behavior, media/source presentation, and the public API contract. R4 owns
Workshop rendering, polling, cancellation, and browser acceptance. R5 owns the
Firebase customer identity/session prerequisite. A separately synchronized
commerce/access lane owns paid configuration+region grants and catalog/media
enforcement. R6 owns staging and release evidence.
R3/R4 do not add billing, purchases, a new dashboard, provider controls, a second
document format, a model call in Go/JavaScript, or a new orchestration framework.

The existing dashboard remains a landing page. The article index remains
descriptor-only: listing or searching titles never downloads article bodies or
starts their rewrite jobs.

## Selected approach

Use the existing article detail route for both the content view and lifecycle
polling. Select a stored source or canonical projection in one database snapshot;
do not combine document text from one revision with media or source metadata
from another. Reuse the existing internal `/v1/catalog/ensure` scheduling boundary
for a cold selected article. Its article operation must return after durable
acceptance, independently of provider/model duration.

Blocking detail requests until rewriting finishes would retain the current empty
reader and timeout failure. A new status endpoint plus browser composition of
raw source and canonical content would create two authorization/read contracts
and two representations. Neither is needed: one authorized article projection
and one ordered renderer satisfy this request.

## R2 persistence/read boundary

This boundary was aligned with the ingestion planning agent. R2 provides the
`catalog_article_current` SQL view and alias resolution. The view exposes:

```text
canonical_article_id, vehicle_id, vehicle_configuration_id,
title, kind, component, provider_slug, source_vehicle_ref, source_article_ref,
source_revision_id, canonical_revision_id, source_snapshot_id,
source_content_sha256, source_version, source_media_type, source_captured_at,
content_origin, availability, document, images, body, steps,
job_id, processing_state, retryable, retry_after_seconds,
processing_error_code, review_status, updated_at, takedown_status
```

The provider slug and opaque resource references are internal store fields, not
public DTO fields. R2 uses one durable `source_fetch_jobs.job_id` through source
capture, normalization, rewriting, validation, and publication. Capturing the
immutable source projection and advancing that job are atomic. Its worker owns
retry deadlines, leases, fencing, and retry exhaustion. A browser request cannot
reset a failed job, bypass review, or create another transformation key.

Legacy row IDs remain accepted aliases scoped to the requested vehicle or
configuration. A source revision and canonical identity are assigned only after
proven provider/reference resolution. An unmapped legacy record can be shown as
source with null lifecycle identity, but cannot trigger rewriting through a
title guess. R2 must map or explicitly quarantine every active legacy row before
release. Quarantine and takedown are access policy decisions and cannot be
overridden by source fallback.

The API selects the newest captured, displayable source revision. If its validated
canonical revision is published, that canonical revision is selected; otherwise
the source is selected. A previous canonical revision is retained in storage,
but is not silently presented as the rewrite of a newer source. An explicit
takedown wins over every cached/published state.

## Public article lists and additive detail DTO

### Canonical index and legacy compatibility

`CatalogStore.Articles` must read descriptors from `canonical_articles` and its
scoped lifecycle projection, including rows with no captured body yet. New R1
ingestion does not write `catalog_articles`; retaining the existing legacy-only
query would hide every newly indexed article. A list read selects descriptor and
lifecycle metadata only, never downloads or rewrites detail.

Use the canonical UUID as `id` for managed descriptors. Keep each provider's
distinct canonical identity even when its local article reference and title
match another bank. Never use `DISTINCT ON (article_id)` or title deduplication
across providers. Resolve the requested vehicle/configuration once and apply
the same Principal, vehicle-scope, review, and withdrawal policy to both branches
of the query and to subsequent detail/source/media reads.

Union only eligible, unmapped legacy rows into the canonical list. Exclude a
legacy row when a proven in-scope alias maps it to an included canonical identity;
do not exclude it merely because a title or local reference matches. Preserve
legacy UUIDs as detail aliases and use the legacy UUID for an unmapped descriptor.
Ambiguous raw provider-local aliases fail closed; list-generated UUID links
remain unambiguous. Sort managed descriptors by R1's bank order (`bankone`,
`banktwo`), persisted `source_sort_order` (page/item order), then canonical UUID.
Append unmapped legacy descriptors ordered by title under the `C` collation,
then legacy UUID. Provider references stay internal. Descriptor `complete` is true only
for an eligible current canonical publication; overall index completeness is
independently derived from R1's per-bank coverage.

Real PostgreSQL fixtures must prove canonical-only descriptors are visible,
equal local IDs from both banks yield two selectable UUIDs, mapped legacy rows
appear once, unmapped eligible legacy rows remain available, and wrong-scope or
withdrawn aliases cannot reintroduce an excluded article. List/search counters
must prove zero body-fetch, model, and article-ensure calls, including when one
bank's index is incomplete.

### Detail properties

Keep `GET /v1/catalog/vehicles/{vehicle_id}/articles/{article_id}` and the existing
`{"version":"v1","article":{...}}` envelope. Retain `id`, `vehicle_id`, title,
kind/component, `body`, `steps`, `document`, `images`, provenance, and
`source_review`. The new article properties are optional in the compatibility
schema; the updated API emits them consistently. Null means the value is not
yet known, not an empty successful revision.

| Property | Type | Meaning |
| --- | --- | --- |
| `canonical_article_id` | opaque string or null | Stable provider-and-vehicle-scoped identity; known after resolution. Existing `id`/URL aliases remain valid. |
| `source_revision_id` | opaque string or null | Immutable captured source revision selected by this read and targeted by the displayed job. |
| `canonical_revision_id` | opaque string or null | Published validated canonical revision selected for display; null for a source view. |
| `content_origin` | `source`, `canonical`, or null | Origin of `document`, `body`, `steps`, and `images`; null when no readable content exists. |
| `availability` | `available`, `pending`, `unavailable` | Whether a readable projection exists, a durable job can still produce one, or no readable projection is currently available. |
| `view_revision` | opaque string or null | Version of the selected immutable display projection and policy; excludes random image URL tokens and processing-only updates. |
| `review_status` | `UNREVIEWED`, `APPROVED`, `REJECTED`, or null | Actual stored review decision. Successful generation never manufactures approval. |
| `processing` | object or null | Durable job projection below; null for explicitly unmanaged legacy content. |

`processing` contains `job_id` (opaque string), `state`, `retryable` (boolean),
`retry_after_seconds` (positive integer or null), `error_code` (safe enum or null),
and `updated_at` (RFC 3339 UTC). Public error codes are
`CATALOG_SOURCE_UNAVAILABLE`, `CATALOG_REWRITE_UNAVAILABLE`,
`CATALOG_REWRITE_REJECTED`, and `CATALOG_REVIEW_REQUIRED`. Provider messages,
credentials, source URLs, object keys, model output, and stack traces remain in
protected diagnostic records. Error text displayed to users is fixed copy.

```json
{
  "version": "v1",
  "article": {
    "id": "article-alias-1",
    "vehicle_id": "vehicle-1",
    "title": "Remove the cover",
    "content_status": "content_partial",
    "complete": false,
    "canonical_article_id": "article-1",
    "source_revision_id": "source-revision-1",
    "canonical_revision_id": null,
    "content_origin": "source",
    "availability": "available",
    "view_revision": "view-1",
    "review_status": "UNREVIEWED",
    "processing": {
      "job_id": "job-1",
      "state": "rewriting",
      "retryable": true,
      "retry_after_seconds": 2,
      "error_code": null,
      "updated_at": "2026-11-03T12:00:00Z"
    },
    "document": {
      "schema_version": 1,
      "normalization_version": "ordered-article-v1",
      "blocks": [{
        "block_id": "article-1:block:0001",
        "source_order": 1,
        "type": "paragraph",
        "text": "Remove the cover.",
        "evidence_ids": ["evidence-1"]
      }]
    },
    "images": []
  }
}
```

`view_revision` is computed from the selected source/canonical revision,
ordered public document, stable asset IDs/availability, and applicable display
policy. Media URL token randomness must not cause repeated DOM replacement.
R2 captures the source projection with localized assets or explicit unavailable
placeholders as one immutable source revision. A later media retry is an explicit
recapture/new source revision; it does not mutate the prior source projection.
Thus source/canonical revision identity drives replacement. `view_revision`
also accounts for display policy and is not R2's transformation uniqueness key.

For managed articles, `complete:true` and `content_status:content_complete`
mean validated canonical publication; structural source normalization alone
never meets that condition. A readable source uses `content_partial`; a
descriptor without readable detail uses `list_only`. This is a deliberate
semantic tightening of existing completeness flags, even though DTO additions
are structurally compatible. Contract tests and the coordinated API/UI rollout
must cover old clients; do not claim additions alone prove semantic compatibility.
Unmanaged legacy responses remain source with `complete:false`, null job and
revision identity, and no automatic polling.

## Lifecycle and HTTP behavior

The public job state enum is exactly:

```text
queued | fetching_source | normalizing | rewriting | validating |
publishing | completed | failed | needs_review
```

| Transition or state | Visible behavior |
| --- | --- |
| Durable acceptance → `queued` → `fetching_source` | Descriptor can be returned with `availability:pending`; content origin is null until readable source is captured. |
| Source captured → `normalizing` → `rewriting` → `validating` → `publishing` | Return the stored source ordered projection immediately. |
| Publication transaction commits → `completed` | Atomically return canonical document, matching media, revision IDs, and source-review metadata; `complete:true`. |
| Transient failure → `failed`, `retryable:true` → due worker retry | Retain source if present; publish the retry deadline. Reads join the same job. |
| Invalid/ambiguous result → `needs_review` | Retain eligible source; stop polling; `retryable:false`. |
| Exhausted/dead-letter job → `failed`, `retryable:false` | Retain eligible source; stop polling; no implicit restart. |
| New source revision | Preserve old immutable revisions; select the new source and its job until its canonical replacement is ready. |
| Takedown/revocation | Deny source, canonical, source-review, and associated media consistently. |

| HTTP result | Contract |
| --- | --- |
| `200` | A readable authorized source or canonical projection exists. A failed rewrite is represented in `processing`; it does not turn readable source into an HTTP error. |
| `202` | The article is known, no readable projection exists, and a durable active/retryable job has been accepted. Return the same article envelope with `availability:pending`, null origin/document, `complete:false`, and a nonempty job ID. |
| `401` / `403` | Authentication or existing access policy fails. Never fall through to source. |
| `404` | Article/vehicle mapping is unknown or outside the requested vehicle scope. No title-based lookup or arbitrary source fetch. |
| `410` | An authorized known article/source has been withdrawn. No fallback to an older version. |
| `422` | Invalid selector/request shape. |
| `429` | Configured API admission policy limits the request; return `Retry-After`. This design does not add a new rate-limiting subsystem. |
| `503` | No readable content and durable scheduling, source acquisition, or canonical storage is temporarily unavailable. Existing error envelope, a safe code, retryability, and `Retry-After` when retryable. |
| `409` | A known article has no displayable content and processing is terminal `needs_review` or failed/nonretryable. Use `CATALOG_REVIEW_REQUIRED` or `CATALOG_PROCESSING_FAILED`, `retryable:false`; include safe article/job IDs in error details. |

An existing complete read only reads durable local state. A cold known descriptor
without a job calls internal ensure with an absolute two-second scheduling
deadline; ensure performs a durable claim/enqueue, never provider or model work
inside that deadline. Return `202` only after job acceptance is observable.
Scheduling failure without a job is `503`, never a synthetic `queued` state.
Existing source with an existing job remains a `200` read when ingestion HTTP is
down. The Go process does not own retries in a goroutine or in-memory map.

HTTP failures retain the existing `error` envelope with `code`, fixed `message`,
`request_id`, `retryable`, and `details`. Catalog details may add only
`article_id`, `job_id`, and `retry_after_seconds` when known; they contain no
upstream error body. Scheduling uses `CATALOG_SCHEDULING_UNAVAILABLE`, source
failure uses `CATALOG_SOURCE_UNAVAILABLE`, and a storage read failure uses
`CATALOG_UNAVAILABLE`. Extend the shared error enum additively for these catalog
codes and the terminal codes above; leave existing error meanings unchanged.

All detail/source responses use `Cache-Control: private, no-store` during this
release so policy checks and state changes are not hidden behind an intermediary
cache. Preserve request IDs. `Retry-After` is integer seconds and agrees with
`processing.retry_after_seconds`; normal active work recommends two seconds,
and delayed retries reflect the persisted next-attempt time. A read or UI Retry
only refreshes status; it never resets retry counters or review state.

Article-index `complete` requires durable enumeration coverage for every required
configured bank scope, including a successful empty result. Nonempty rows do
not establish completeness. Failed/partial coverage retains usable rows with
`complete:false`; `hydrating:true` means an active durable job, not merely a
missing marker. Existing `progress` reports the safe aggregate state; the UI
offers a status refresh on failure. R1 owns coverage proof and retry scheduling.

## Source projection, source review, and media

R2 persists source text as the same version-1 ordered document used by canonical
content. The Go API does not interpret provider JSON/HTML/PDF or perform another
rewrite. It validates and projects supported blocks, including unknown blocks,
table cells, callouts, ordered numbering, stable block IDs, evidence, and image
positions. API/Workshop never render arbitrary source HTML in the main reader.
Numbers, units, identifiers, safety wording, and source order remain intact.

`source_review.url` points to the existing same-origin `/source` route and includes
`source_revision_id` when managed. Evidence/locator query parameters remain
navigation context; they do not authorize a different snapshot. The source route
resolves the exact authorized immutable source revision associated with the
article/vehicle. It performs no hydration, provider fetch, or model call.

Add optional `document`, `images`, and `view_revision` siblings to the current
JSON source response; retain `source` metadata and sanitized `content` for
existing consumers. New Workshop prefers the ordered `document`. A source
projection is useful for both Bankone and Banktwo; pretty-printed provider JSON
is not the consumer fallback. Direct HTML source navigation renders escaped
ordered blocks with restrictive CSP. The legacy `content` representation is
sanitized using an element/attribute allowlist, removes active/external resource
surfaces, and remains protected when used by a legacy frame. No public issue
needs payload-level security details.

Media URLs resolve only to already-localized, validated assets. Missing images
stay at their original block or table-cell position with an explicit unavailable
message. Browser requests never include provider URLs or credentials. Keep the
localized bytes unchanged; use a sandboxed media response, including for SVG:

```http
Content-Security-Policy: sandbox; default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
X-Content-Type-Options: nosniff
Cross-Origin-Resource-Policy: same-origin
Referrer-Policy: no-referrer
```

This policy permits embedded data-image content within a diagram and blocks
active/external loads under direct navigation as well as normal image display.
Allow only supported image media types and verify response content matches its
declared type. Browser fixtures must prove the intended rendering and isolation;
a failing format remains unavailable instead of weakening the policy. Do not
add runtime rasterization or another source fetch in Go.
R2 owns capture/materialization; R3 owns browser-safe serving. The separately
gated paid-access lane owns the final authenticated media access mechanism;
R5 Firebase identity alone does not authorize media implementation. Current
capability URLs are not evidence of revocation enforcement. The later lane must
verify current entitlement/rights and the same article/asset association after
withdrawal, before opening storage.

## Workshop state and polling

Add a pure article-read coordinator beside `catalog.mjs`; keep collection polling
separate. Its read result preserves HTTP status, payload, and `Retry-After`.
It processes `200` and `202`; it does not treat every successful HTTP status as
readable content. Every read receives the current `AbortSignal`.
Other statuses throw a `CatalogRequestError` with public `status`, `code`,
`retryable`, `retryAfterSeconds`, and `requestId` properties. The coordinator
retries only transient network errors and retryable `429`/`503`, within the same
budget; `401`, `403`, `404`, `409`, and `410` stop. Denial, withdrawal, or an
invalidated article clears its prior view rather than retaining stale access.

The initial article selection creates an incrementing selection generation and
one abort controller. Changing vehicle/article, navigating back, pressing Cancel,
or restoring a different history selection aborts all article and source-review
requests and invalidates that generation. Every callback checks both generation
and selected article/vehicle before touching the DOM. Matching response URLs
alone do not protect against a stale response from an older selection.
A source-review request also captures its pinned `source_revision_id`; changing
the displayed source revision invalidates that review request even when the
article and vehicle are unchanged.

Polling is sequential, never overlapping, with delays 1, 2, 4, 8, then 10 seconds,
and a two-minute absolute budget from the first request. Each request has a
maximum ten-second deadline, bounded by the remaining budget. Respect a longer
server retry interval; if it exceeds the remaining budget, stop with a manual
"Check again" control. Active states and `failed/retryable:true` poll; completed,
needs-review, nonretryable failure, and unmanaged legacy content stop. Retry
starts another bounded status-read window for the same identity/job.

Keep already-rendered source readable during transient polling/network failure.
Update processing copy separately from content. Render a new document only when
`content_origin` or `view_revision` changes. Construct and validate the full new
DOM fragment, including matched media, before replacing the old view. First
opening can move focus to the article title; background updates must preserve
focus, search/vehicle selection, source panel state, and a stable block anchor
when it still exists. If no anchor survives, preserve scroll rather than jumping
to the top. Printing remains available for any readable source/canonical view
and includes its origin/review label.

Media URLs can expire while `view_revision` stays unchanged. On the first media
load failure for a selected view, coalesce failures into at most one automatic
detail refetch under the same selection generation/abort signal and ten-second
request deadline. If the response has the same view revision, reconcile only
the local URLs of matching stable asset IDs in existing image/source-panel
nodes; preserve content, focus and scroll. Never associate a URL by array position
or title. A changed view follows the normal atomic replacement path. Consume
this automatic renewal budget even if the replacement media fails; show an
unavailable placeholder and an explicit manual refresh control instead of an
error/refetch loop. A new selection, new view revision or explicit manual refresh
starts a fresh budget. Late or aborted renewal responses cannot update another
selection. A renewal `401` stops work and clears protected content, then applies the R5
session login-availability contract before presenting sign-in; `403`/`410` clear the
denied/withdrawn view without retry; other failures preserve eligible readable
text and stop automatic media renewal. Renewal reads local detail and never
reschedules ingestion or calls a bank/model for completed content.

The reader uses concise labels: "Source content — preparing AutoData article",
"Source content — preparation could not finish", "Source content — review
required", and "AutoData article". Display stored review status without implying
that machine validation is human approval. An empty `202` shows preparation and
retry/cancel controls; an unknown article, unavailable source, or denied access
has distinct fixed copy. No percentages are invented for rewriting.

`document.blocks` counts as readable independently of compatibility body/steps.
Unknown retained blocks stay visible. Existing semantic tables, native selection
controls, keyboard navigation, local fonts, reduced motion, and mobile/print
layout remain. Rendering and polling tests cover the real application DOM, not
only helper functions.

## Contract and verification ownership

R2 owns shared lifecycle definitions under `packages/contracts/` and migrations;
R3 serially extends their public schema and Go API binding after the R2 contract
checkpoint. Use `packages/contracts/catalog/v1/article-lifecycle.schema.json`, referenced by
`packages/contracts/contract.json`; keep it separate from unrelated dataset and
payment schemas. Add all existing selector, article, source, and media routes to
both served OpenAPI formats. Include document block/table-cell/image schemas,
the state enum, examples, every HTTP outcome above, and compatibility fixtures.
The schema validates public DTOs without private object/provider fields.

Acceptance includes deterministic Go handler/store tests, Python-to-Go contract
fixtures, JavaScript coordinator tests with fake clocks, and Chromium/Firefox/
WebKit browser fixtures. Fixtures represent Bankone, Banktwo, both together,
one unavailable bank, colliding provider-local IDs, source-only/202 states,
publication, rejected rewrite, due/exhausted retries, takedown, missing media,
and delayed old-selection responses. Requests are intercepted/recorded; tests
fail on provider network access or any unexpected external origin. A separate
PostgreSQL integration fixture proves the API reads R2's real view/aliases.

Auth/media policy fixtures use deterministic injected principals and restricted
assets, and consume R5's deterministic login/session fixture contract before
Workshop completion. Browser interception includes that contract's exact identity
bootstrap paths; it does not invent a login endpoint or use a live account.
Fixtures do not by themselves certify the production identity adapter. The staging
two-bank canaries, distributed crash/lease tests, and production access proof
remain R2, identity, separately gated commerce/access and R6 evidence. No test
in this planning activity certifies them.

## Separate customer identity and paid-access requirements

The authoritative [Firebase identity plan](../plans/2026-11-03-workshop-firebase-identity.md)
supersedes the former OIDC discovery/code-PKCE/client-secret callback plan. R5
uses official Firebase Admin Go v4.22.0 to verify Google sign-in, map project+UID
to a persistent account/personal organization and issue an opaque PostgreSQL
session. Client email/org/role claims grant no authority; ordinary customers
receive server-defined dataset_viewer and no purchased scope or staff role.
Sessions have an absolute12-hour lifetime and current local/Firebase user-state
checks, including auth_time revocation. Missing persistence/configuration or
nonempty FIREBASE_AUTH_EMULATOR_HOST fails Firebase startup. There is no OIDC
fallback, customer callback transaction table or optional customer API bearer.

R4 consumes public no-store `GET /auth/config`, then `GET /auth/session`, Google
popup through a pinned Firebase web SDK, and `POST /auth/firebase/session` with
JSON ID token, exact Origin and X-Autodata-Session-Exchange:1. The server returns
an opaque secure cookie only after atomic account/session commit. Cookies carry
later catalog requests; no ID token goes in localStorage/query/API bearer.
`POST /auth/logout` requires exact Origin and session CSRF, commits database
revocation and expires the cookie even during Firebase outage; R4 also signs out
its Firebase browser instance. No `/auth/login` or `/auth/callback` route is part
of this customer contract.

Explicit local development/test remains headless-only: config/session report
login_available:false, and local Firebase exchange returns fixed503
AUTHENTICATION_UNAVAILABLE with `Sign-in is unavailable.`, retryable:false,
no-store and no account/session. Only explicit configured true permits sign-in.
False/missing/malformed availability clears protected content without a demo,
redirect or retry loop. Fixtures distinguish popup cancellation/blocking,
expired session401, blocked403 and dependency503, preserving source/polling
cancellation and denial behavior. Browser fixtures make no real identity calls.

The canonical [Workshop commerce policy](../../architecture/workshop-commerce.md)
requires a $20 USD one-time purchase for exactly the selected normalized
configuration+region and permanent account grant. Full source/canonical/status
and media access require that current grant plus current rights/takedown policy;
safe public selectors/previews are separately bounded. Checkout, grants, library,
paid browser UI and catalog/media enforcement belong to a later synchronized
lane, outside identity's35 paths and R4's session/content work. Historical
role-only shared-catalog access is not the final paid product policy. Completing
R3/R4 or Firebase identity does not establish paid access or production readiness.

Real Firebase project/app registration, Google provider/domain configuration,
Admin service identity/IAM and staging HTTPS setup remain deployment prerequisites;
none is invented from bank credentials. Deterministic implementation can proceed
after its gate without those live values. Actual Google login/revocation,
two-replica sessions, TLS/cookies and production access require separate measured
staging/release evidence. R5 tracking is synchronized with amended Issue186/Project8; a new committed
exact-base preflight remains required before identity implementation.

## Risks and rollout constraints

- R2 schema/view and lifecycle definitions must be committed before R3. R4
  application completion depends on both R3 and the R5 identity/backend contract;
  fixture-only preparation can occur earlier without shared-file edits. Re-pin
  and preflight each base; no overlapping Workshop or `main.go` edits with R5.
- All execution and review agents use `gpt-6.1-sol`, `medium` reasoning, and
  Fast/`priority` service, as directed by the user after the planning audit.
- Legacy `complete` semantics tighten. Audit representative consumers and retain
  compatibility fields/aliases; structural additivity alone is insufficient.
- Source and media policy must be checked together. A fallback cannot bypass
  quarantine, denied rights, or withdrawal.
- Source projection or media readiness can lag source capture. `202` and explicit
  unavailable placeholders are valid; title-only content is not a ready article.
- Repeated GET scheduling must join R2's durable job, including across API
  replicas. Process-local deduplication cannot satisfy this invariant.
- Browser tests need installed engines and deterministic fixture services. Report
  an unavailable engine as unavailable, not as passed or skipped release coverage.

The corresponding [implementation plan](../plans/2026-11-03-source-fallback-web.md)
contains bounded tasks and acceptance commands. Original release tracking was
verified in Issue #186 / Project #8; the Firebase amendment is synchronized and commerce remains in planning. Each dependent task requires its amended integrated dependency
checkpoint, synchronized record and passing exact-base preflight.
