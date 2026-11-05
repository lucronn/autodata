# Finite dual-bank connector capture executor contract

Status: offline tooling specification; authenticated execution remains blocked.
Issue: https://github.com/lucronn/autodata/issues/304 (child of #186).
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhGO_X0`.

## Goal and boundary

Build and offline-verify a finite dual-bank connector capture executor that preserves raw failure evidence before parsing; authenticated execution remains separately gated.

Build only `scripts/dev/bank_canary_capture.py`, `scripts/dev/bank_canary_transport.py`
and `scripts/dev/tests/test_bank_canary_capture.py`. Use the unchanged
`SourceConnectorClient` with its injectable opener. Do not reuse ingestion,
hydration, workers, application article GETs or storage/model entry points.
The client at planning parent c0be267 has the same bytes as the externally
reviewed product candidate 4d82e413. This gate covers offline implementation
and tests with synthetic inert data only. All real-source acceptance counts
remain zero. Actual origin/key/license/selection enrollment, transport rights,
reviewer/custodian assignment and protected evidence access are absent.
A later committed run-specific gate must pin the actual product, executor,
enrollment, run window and approval before any actual DNS/TLS/provider call.

## Fixed inputs and operation graph

`validate_enrollment(document)` must reject unknown/missing fields before any
transport creation. Schema v1 has `run_id`, UTC `window_start`/`window_end`,
`product_sha`, `product_tree`, `executor_sha`, `client_sha256`,
`operator_ref`, `reviewer_ref`, `custodian_ref`, `execution_approval_ref`,
`protected_storage_ref`, `retention_delete_at`, `rights_ref`, and exactly two
`banks` keyed `bankone`/`banktwo`. Each bank has a credential-free HTTPS
`origin`, `owner_identity_ref`, `deployment_revision`, `key_version_ref`,
`egress_identity_ref`, `license_ref`, `revision_attestation_ref`,
`expected_source_revision`, UTC `minimum_fetched_at`/`maximum_fetched_at`,
`selector` (year/make/model/configuration/region only), `source_vehicle_ref`,
`article_ref`, `body_ref`, `resources`, `applicability_mapping`,
`procedure_content_rule` and `incident_procedure_ref`. Validate full SHA forms,
UTC ordering, nonempty refs, two distinct origins and per-bank key references,
future deletion/window constraints and numeric bounds. No VIN, inferred default
origin, legacy token fallback, arbitrary endpoint, caller-provided budget
increase or caller-provided shell command is permitted. References attest to
external owner approvals; syntactic validation alone proves no rights/identity.

Each resource entry freezes opaque ref, role (body/asset/labor), media type,
required flag, source revision, expected byte count and SHA256, or explicit
`first_observed` hash mode plus provider revision attestation reference. Exactly
one required body, at most four unique required assets and one required labor;
absent roles are explicit and complete membership is owner-attested. Duplicate
refs fetch once and preserve every role association. Require a nonempty body
content rule with owner-approved literal procedure markers and minimum decoded
text length; matching is byte/text inspection, never HTML/SVG execution/render.
Applicability mapping explicitly binds returned configuration/region/source
fields to the frozen selector; insufficient mapping is nonpass. Bank-owned
opaque references/cursors remain private and are percent encoded once.

For each bank sequentially: capabilities requiring catalog/vehicle_resolution/
article_list/resource_read; complete years; makes(year); models(year/make);
configurations(year/make/model); exactly one resolution POST with exact frozen
selector; complete selected vehicle article index; selected body and frozen
required resources. No region query on catalog. Require nonempty branches and
selected membership; exact semantic resolution selector correspondence and
exactly one matching source vehicle candidate; frozen article and full resource
membership; expected provider/revision/fetched window/applicability/hash/size/media.
Terminal page must be `complete:true` with `next_cursor` absent, not null;
nonterminal cursor must be nonempty, unseen and advancing. Never select the
first successful row, truncate membership or fetch newly discovered resources.
Other indexed articles are retained descriptors only, not captured details.

## Budgets and cancellation

Hard maxima per bank: 58 requests; 10 pages including terminal per catalog
branch (40 total) and 10 article-index pages; 20,000,000 wire bytes per response;
100,000,000 aggregate wire response bytes, including failed/partial responses;
25-second socket timeout; 900-second monotonic duration. Global maxima: 116
requests, one request in flight, at least one monotonic second between starts,
zero retries, zero redirects, 1,800 seconds including a reserved 10 seconds for
cleanup. Respect the existing client's stricter decoded/base64 validation limit;
20 MB wire allowance does not guarantee acceptance of 20 MB binary resources.

The parent controller accounts attempt/start before launch and enforces the
allowlisted graph/method/origin. Before each launch require remaining global
and bank time and bytes; effective deadline is
`min(bank_start+900, run_start+1800-10)`. Request count includes failed starts;
byte counts include every body byte delivered to the capture transport. Page 10
incomplete stops without page 11; no hidden probes, proxy calls or retries.

One child process owns each direct standard-library HTTPS connection, TLS
verification with system trust, no environment proxies, no ambient cookies,
Accept-Encoding identity and no automatic decompression. Parent watchdog spans
DNS/connect/TLS/read, uses monotonic polling, closes IPC, terminates then kills
and reaps the child within the reserved cleanup budget. Child streams at most
64 KiB chunks bounded by remaining response/aggregate allowance directly into
exclusive private spool files before forwarding bounded bytes to the client
adapter. Never read a sentinel byte beyond allowance: at exact byte ceiling,
accept only proven EOF (framing/Content-Length); otherwise record limit-reached
partial/nonpass and close. An HTTP-error body follows the same capture path.
The returned adapter exposes status, exact final URL, allowlisted headers and
BytesIO-compatible read/context manager; the unchanged client parses only after
transport capture. Successful transport does not imply successful validation.

The parent records an attempt before child launch. The child journals response
status/header metadata before body and flushes each captured chunk. Parent
finalizes inventory after child exit, retaining exact persisted partial bytes
and their hash even on cancellation/parse failure. UTC observations accompany
monotonic offsets; no raw exception repr/traceback reaches stdout. Hard kill may
leave an explicit incomplete journal; never claim missing buffered bytes were
preserved. Output failure stops new calls; lost evidence is nonpass. An aborted
first bank does not consume the second's independent budgets; attempt the other
only if independently enrolled and remaining global time allows, except shared
security concerns stop both. 429/Retry-After stops without waiting/retrying;
401/403/redirect/malformed or changed identity/revision/membership stop that bank.
Secret-bearing or unlicensed response stops both and invokes owner incident rules.

## Raw evidence and failure contract

Private output root is owner-only (0700), files 0600, exclusive create/no symlinks,
no overwrite of an earlier run. No source payload, enrollment detail, path,
cursor, locator, signed URL, raw header/error or credential is printed or Git
tracked. Credentials arrive later only through two pre-opened private file
descriptors, never arguments/environment dumps; refs only in manifests, never
credential values or credential hashes. Execution-only mode requires a distinct
owner approval receipt bound to run/enrollment/executor digest. This gate supplies
no receipt; offline commands reject real origins and credential descriptors.

Private `run.json` binds schema/run/enrollment digest, product SHA/tree, actual
executor/client bytes, environment/runtime identity, operator/reviewer/custodian,
key-version references, service identity/attestation refs, rights/storage/retention,
UTC/monotonic interval, limits, and fixed intended denominators per bank:
selected_articles=1; required_resources=frozen unique required refs count.
`attempts.jsonl` records every planned step and attempted call with bank,
sequence, method/encoded path/selector, page/cursor predecessor/successor,
UTC/monotonic timing, HTTP status or absent, sanitized error enum, final validation
outcome, expected/observed provider/revision/fetched time, request ID, safe locator,
TLS version/cipher/certificate digest/observed peer, and raw inventory references.
DNS/TLS failures have absent HTTP/raw evidence and a stable stage reason.
Never create invented status/body/provenance to fill absent fields.

Allowlisted private response headers only: Content-Type, Content-Length,
Retry-After, X-Request-Id, X-Provider, X-Source-Revision,
X-Fetched-At, X-Source-Locator, X-Source-SHA256 and X-Source-Media-Type (case insensitive;
retain their actual original values privately). These exact provenance names match `_binary_envelope` in the pinned client;
no extra header names are accepted. Exclude Authorization, Cookie, Set-Cookie,
WWW-Authenticate, Location and arbitrary diagnostics. Protected locator headers
can still contain secrets: quarantine rules apply before normal reviewer access.

`inventory.json` lists exact persisted raw response bytes before parsing (JSON
or binary), decoded successful resource bytes as separate objects, response
sequence, byte count, SHA256, relative private file ref and state complete/
partial/absent/quarantined, truncation cause, storage immutable version or local
unsealed status. Failed JSON/hash/schema/provider/selector validation retains
original body bytes; do not reserialize JSON as original evidence. Limit overflow
retains only bounded captured prefix labelled partial. Non-200 and HTTPError
retain approved original status/body before returning sanitized failure. Local
spools do not prove immutable protected storage; actual future reviewer acceptance
requires custodian sealing/upload and recorded immutable versions under a separate
authorized run. No S3/cloud uploader is added here.

A suspected secret stays only in incident-isolated quarantine with restricted
custodian access; no copying into ordinary evidence/public logs. Record opaque
incident reference and counts, apply owner retention/deletion, preserve the fact
and reason of any removed bytes without inventing a clean original. Detection
must inspect allowlisted header values and bounded textual payloads for the actual
in-memory credential and signed/token/password/auth query patterns, never publish
matching strings or credential hashes. Automated detection is not proof of no
secret; independent authorized original review remains mandatory.

`result.json` has per-bank pending/failed/incomplete/withdrawn/observed_complete,
intended/attempted/successful denominators, stop code, resource coverage, and
review state pending/accepted/rejected. Zero/missing denominator, partial/absent/
quarantined evidence or missing identity/rights/storage/review cannot pass.
`summary.json` contains only schema, opaque run/evidence refs, bank identifiers,
approved counts, outcome enums and fixed sanitized reason enums. Unknown fields
fail the summary schema. No public PASS from the tooling-only milestone; even a
future observed_complete result remains reviewer-pending until independent
protected-original review. Reruns get new run IDs; preserve earlier outcomes.

## Concrete todo

- [ ] Implement strict frozen enrollment validation and the sequential 58-request-per-bank operation graph using the unchanged provider-bound source client.
- [ ] Implement a cancellable streaming transport with fixed request/page/rate/byte/time budgets, no retries or redirects, and raw response capture before validation.
- [ ] Implement private append-only attempt/raw-inventory and failure outcomes with fixed denominators, quarantine handling and an allowlisted public summary.
- [ ] Prove all limits and failure retention offline with inert credentials and fake transport/socketpair tests; independently review the exact implementation SHA before any later enrolled execution gate.

## Acceptance boundaries

Offline tests must prove 58+58 maximum graph and all controls, including blocked
connect, slow trickle, framing/byte ceilings, fake-clock rate scheduling,
HTTPError/non-200 and post-capture parse rejection; raw partial evidence after
watchdog kill; selector/region/provider/revision drift; changed resource membership;
secret-bearing errors; protected-output write failure; missing enrollment;
second-bank independence; no unrelated entrypoint/environment credentials.
Tests use inert synthetic tokens and in-memory fake transports; subprocess
cancellation may use socketpair, with no external network or application stack.

After exact-SHA offline review this tool may be delivered, but execution still
requires enrolled owner approvals, protected storage, new synchronized run gate,
reviewed concrete executor and approved bounded POST read. No current bank
acceptance, canonical publication, model transfer, R6 later2 collector acceptance,
full population coverage, final180/API21/DTO120, staging/deployment or cutover is
conferred. This work does not implement the broader release architecture.
