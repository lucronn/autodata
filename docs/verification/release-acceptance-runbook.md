# Workshop product evidence: offline diagnostics and confined transport

The current bounded assembler implements strict v1 envelope structure, a
coordinator-supplied trusted invocation, confined artifact transport and internal
raw format/identity primitives and a paid common-outcome inspection API. It does
not yet corroborate complete paid/DTO
producer semantics or verify either tier. All profiles at the authorizing checkpoint
`0e21f6dbdf5ad0402b8bef42d3e1f2566964b309` are disabled and the assembler hash is
unpromoted. The actual planning task therefore returns exit 3 (`unavailable`)
from `validate`, even for a structurally valid envelope with supplied pass reports.

Run from the owned checkout, with an explicit dedicated evidence directory:

```sh
python3 scripts/dev/release_acceptance.py plan \
  --manifest /protected/evidence/envelope.json \
  --evidence-root /protected/evidence/raw \
  --trusted-base-sha 0e21f6dbdf5ad0402b8bef42d3e1f2566964b309 \
  --task-ref docs/agents/tasks/2026-11-03-production-release/r6-release.json \
  --requested-tier fixture
```

Use `validate` in place of `plan` to check the declared raw inventory and then
receive the unavailable result. Keep the envelope and output outside the dedicated
raw directory: every file there must have exactly one declared artifact reference. `plan`
exits 0 only for a valid diagnostic request; its `planned` status is not
acceptance. `validate` cannot exit 0 in this milestone. Every verification,
deployment and cutover flag is always false. All observed counts are zero, all
required slots remain missing and all eight gate statuses remain unavailable.
The envelope's declared pass reports, artifact hashes and commands cannot
change these outputs. `plan` leaves the evidence directory unread, including when it does not exist.
`validate` reads and checks declared artifact integrity, which cannot promote a tier.

The manifest is one UTF-8 JSON object of at most 2 MiB. Duplicate and unknown
keys, nonfinite numbers, booleans in integer positions, invalid versions,
identifiers, paths, hashes and internal references are rejected. Declared slot
profile hashes must match canonical committed slot profiles where those profiles
exist; disabled or absent profiles remain unavailable. Commands are
validated as data and never executed. Parse failures emit static diagnostic
codes without echoing candidate strings or private contents. The only subprocess
reads pinned Git objects from the tool's owned repository, with isolated Git
configuration; candidate code is never imported and evaluator/controller code
is never executed. The trusted base, task and requested tier come from the
coordinator's invocation and must match the envelope.

The confined transport reader opens every directory component with `O_NOFOLLOW`
and uses directory-relative file descriptors. It rejects symlink roots/ancestors,
symlink files/directories, special files, hardlink aliases, undeclared inventory,
missing files, changed inode/device/mode/link count/size/mtime/ctime and incorrect
hashes. It checks the complete inventory before and after each read, reopens every
file on every call and retains no cached buffers. Root or nested directory
replacement also fails. Declared per-file and aggregate bounds are checked before
content reads; fixed transport ceilings are 8 MiB per file and 64 MiB total.
These ceilings do not substitute for future profile-specific raw bounds.

The explicit `ArtifactStore.read_identity_json` API reopens/rechecks bytes before
JSON parsing and rechecks inventory afterward. When called with trusted expected
identities, any declared `candidate_sha`, `trusted_base_sha` or `profile_sha256`
field, including nested declarations, must match exactly. It never fills missing
identity fields or proves schema completeness. Its strict JSON limit is 2 MiB.
The disabled CLI path deliberately does not choose this parser for any raw kind
or filename: a reviewed enabled profile must first freeze the slot's actual raw
format and required fields. CLI validation currently checks transport integrity
only, then returns unavailable. Candidate graph ancestry remains unavailable
pending an explicit complete Git provenance contract; a shallow clone is not an
ancestry proof.

Exit 2 means invalid contract, invocation, trusted object or raw transport integrity. Exit 3
means unavailable verification. Future gated raw validation will additionally
use exit 4 for actual execution/assertion/policy failure, with precedence
2, then 4, then 3. That raw validation behavior is not implemented here.

Before any promotion, independently review the exact implementation commit,
freeze the reviewed assembler hash and complete raw profiles in a new
synchronized task checkpoint, then run the exact-base gate again. A promoted
profile is deliberately rejected by this milestone until its validators are
implemented under that gate. Hashes alone do not authenticate authors. Candidate
ancestry, raw producer format/completeness, exact case IDs,
source/migration/image/SDK/CI bindings, report identities and policy derivation
remain required future work; structural parsing proves none of them.

Fixture verification will require actual 5+8+14+12+120+21 raw cases plus
supporting evidence. DTO mocks cannot satisfy the real API browser slot or
live Google/Stripe proof. Staging requires the separately gated collector,
licensed enrollment, protected proof and actual host/isolation/recovery/alert
receipts. Neither the synthetic tests nor historical paid12/DTO evidence verify
a final candidate, staging, deployment or the separately unverified runtime.
The policy, evaluator and workflows remain authoritative and unchanged.

The fixed-profile design checkpoint is recorded in
[the assembler plan, section 4a](../superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md#4a-fixed-raw-profile-design-checkpoint-planning-only).
The design amendment itself is planning only. The separately synchronized
section 4b implementation gate is `f18ca7bb9d5822dc96b5a5e31d0254e6dd985a03`;
its bounded first milestone adds the internal primitives below and leaves all
committed profiles unchanged and disabled.

The inspected historical paid12 and DTO120 receipts both identify
`2de36a1305bfbe45992995e6caf0ba52f30fddcc`. Paid evidence under
`/tmp/autodata-paid-access-040-acceptance-2de36a1-v2/artifacts` has 499 files totaling
30,437,073 bytes; 331 declared receipt hash references were independently matched.
Its collector JSON is 3,715,668 bytes, exceeding the original 2 MiB identity
reader. The new explicitly invoked raw JSON reader is bounded at **4 MiB
(4,194,304 bytes)**; the envelope and original identity reader stay capped at
**2 MiB (2,097,152 bytes)**. Transport ceilings remain unchanged. This parser
bound alone does not validate that historical collector or establish authority.

Historical DTO CI run 41721947690 / artifact 13273366580 retains the 12,713-byte archive
with SHA256 `653df2e839f65f6bc16484e9257f7138b0abf87edc437cdc201a958f8f1b0a5a`.
Its three entries expand to 405,292 bytes and include actual 120 DTO rows, fixture
log and readiness metadata. The plan retains the exact paid/DTO hashes and
review/supervisor paths. These local byte-consistency observations do not supply
registered reviewer identities, authenticated capture provenance, complete CI
run/required-check metadata or future trusted-profile linkage. Exact browser
wrapper `b41ae0a538b3c5b62b33c32483146462886851e3c60768f8fdc0ac79495a3964`
is independently approved in `/tmp/autodata-nested-evidence-expiry-browser-cache-review.md:17`.
Registered approval authority and complete profile linkage still must be frozen
before promotion; matching hashes are insufficient.

Internal raw foundations are format and identity checks only:

- `strict_raw_json` applies the separate 4 MiB UTF-8 object limit and the same
  duplicate-key/nonfinite/invalid Unicode rejection as envelope JSON.
  `ArtifactStore.read_raw_json` explicitly reopens and checks the immutable
  inventory before/after parsing, and rejects conflicting declared reserved
  candidate/base/profile identities. Missing required producer identities are
  not supplied by this helper.
- `strict_jsonl` accepts only complete newline-terminated object records, at
  most 4 MiB and 65,536 records. It does not interpret Go run/pass outcomes.
- `strict_junit_xml` accepts UTF-8 non-namespaced JUnit roots, at most 4 MiB,
  20,000 elements and depth 64. It rejects DTDs/entities, comments, processing
  instructions, namespaced tags/attributes and conflicting encoding declarations.
  It does not interpret case verdicts or counters.
- `strict_dto_archive` reads exactly `browser/evidence.json`, `go-fixture.log`
  and `ready.json` in memory. JSON members are bounded at 4 MiB each and the
  fixture log at 8 MiB; compressed input stays within the 8 MiB transport
  ceiling. Only regular ZIP32 stored/deflated members without descriptors,
  comments or extra fields are supported. Local/central metadata, CRC and
  complete deflate streams must agree. Central-directory headers are parsed
  directly: all three frames must consume exactly the declared directory bytes,
  declared extra/comment lengths and member disk-start must be zero, and the
  complete extraction-version field (including its reserved byte), DOS time/date
  and other local/central metadata must match. DOS dates/times must be valid.
  Symlinks, duplicate/extra/missing names,
  traversal, encryption, overlapping/gapped layout, trailing bytes and hidden
  expansion fail. It never extracts an archive to the filesystem.
- `paid_case_identities` and `dto_case_identities` check the fixed 12 paid IDs
  and 120 scenario/engine pairs. Exact identity coverage is distinct from raw
  outcome corroboration. These functions cannot certify any logical case.

None of these helpers is selected by the CLI, a raw kind, a filename or candidate
code. Tests explicitly forbid their dispatch from both fixture and staging plan/
validate paths. Complete producer schemas, typed assertion/phase/outcome checks,
source/migration/image/SDK/CI corroboration and trusted profile promotion remain
unfinished. A valid internal parse never changes the unavailable CLI result.

The internal `inspect_paid_common` API accepts only the explicit
`paid-selector-v2` format selector and expected candidate/base/profile/input/host
identities. Raw collector and case receipts remain schema version 1. It reads
only fixed declared references through the confined store, checks all seven
collector and 27-per-case raw hash entries, requires the collector's embedded
case receipts to equal retained bytes, and checks exact six-root/two-bank IDs,
12 distinct fixture database names and exact phase inventories. It checks the
recorded outer/child JUnit identities/outcomes/deadlines, exact Go argv/cwd,
ordered package/root run/pass events, typed assertion declarations, measurement
copy seams, v2 observed-view null/list inventories and recorded worker cleanup.
These checks reject failed raw outcomes even if outer receipts claim pass.

This API **always returns `status: unavailable`, `complete: false`, no verified
case IDs and false verification/deployment/cutover flags**. Its observed IDs are
common-record identities only. Paid Go-event elapsed numbers retain exact JSON
decimal values for the inclusive 0–90 second bound, including fractional values
that binary floats would round across either boundary. Booleans, strings and
nonfinite/overflowed numbers remain rejected. Assertion declarations and matching
raw copies are not proof of the underlying product facts. The result always retains these
missing validation families:

- `paid_source_pg_bindings`;
- `paid_http_media_rights`;
- `paid_selector_work_and_model`;
- `paid_migration_replay`;
- `paid_runtime_image_inputs`;
- `paid_host_and_input_provenance`;
- `paid_supervisor_commands_and_isolation`;
- `paid_supervisor_authority`.

In particular, hashing migration/host/input records does not validate their
contents, source/PG/media payloads are not yet corroborated, and two cleanup
receipts do not establish trusted worker authority or host isolation. The API
is never selected by CLI plan/validate, any artifact kind or an enabled profile.
Synthetic tests deliberately supply incomplete deeper payloads and assert this
unavailable result, including one test through the real confined ArtifactStore.
DTO producer corroboration is unchanged and remains unfinished. Independent
exact-commit review is required before extending into any deeper family.

All profiles and verification flags remain blocked. Actual API21, complete 180
cases and supporting scans/images/reviews at the final immutable candidate,
exact-head CI and complete Git ancestry provenance remain required. Historical
receipts and a one-case browser pilot cannot satisfy those obligations. A future
complete fixture result may set only `fixture_verified`, with evaluator unevaluated;
staging/product/deployment/cutover claims do not follow from it.

The separate internal `inspect_paid_pg_snapshots` API first enforces all common
outcomes, then checks the 40 phase and 12 final PG snapshot bindings. It validates
closed snapshot/counter/probe/table-container inventories, nonnegative integer
counters, settled ensure counts, provider trace lengths, proxy consistency and
worker receipt scalar shapes. It re-derives all six article counts from the raw
SQL rows, binds the selected article/provider and checks the immutable row digest
using the frozen producer's `json.dumps(rows, sort_keys=True)` encoding (default
spacing and ASCII escaping). The final populated replay rows must equal the
independently retained final snapshot; this seam alone does not validate replay.

The six paid table formats have closed column inventories and scalar/nullability
checks. This layer requires two distinct account/organization UUID identities,
session account coverage and unique hashed token/time records, and structured
grants bound to an order's customer/configuration/region and fixed TEST payment
facts. Active grant scopes must be unique. The intentional legacy negative
fixture retains its unstructured null customer/configuration/order/region scope.
PG17 database/user, S3 bucket/round-trip and JetStream probe receipts are checked
against each case's fixture database. Probe booleans are fixture observations;
they do not authenticate an independent supervisor or live services.

**This API also always remains unavailable/incomplete, with no verified IDs and
all verification/deployment flags false.** Its `observed_pg_snapshot_count` is a
binding diagnostic, not a case count or verification result. Every existing
missing family remains, and `paid_pg_row_semantics` is additionally explicit.
Lifecycle SQL row payloads and article documents, ensure request details, source
provenance, full commerce foreign-key/state semantics, source-to-public content,
media rights/body/security headers, selector/model behavior, migration chain and
fresh/empty/populated replay outcomes still require their own typed layers.
Nested lifecycle row/article/request payloads remain opaque bounded JSON here;
only the explicitly named count/identity fields are interpreted. Worker receipt
shapes do not establish process ownership or isolation. No DTO work or profile
promotion is included. Both internal paid APIs remain unselected by CLI plan and
validate; tests forbid dispatch to either and exercise this PG layer through the
real confined ArtifactStore with inline synthetic files.

The additional internal `inspect_paid_migration_receipts` layer first applies the
common and PG checks, then binds all 36 migration phase receipts to the literal
ordered 001–040 filenames. It checks the driver exit and actual driver bytes
against an explicit `expected_driver_sha256` invocation input. The closed migration
object also requires the v2 producer's `runner_sha256` field: a lowercase 64-hex
SHA256 string recording `scripts/dev/migrate_sql.sh`. The historical retained
value is `4970eab6f20be35c354547ed5acf73c991dae1a83433094715f051463790a8f3`.
This field is type-checked metadata; it is not proof of runner bytes, source
binding, execution or registered authority, and driver provenance remains missing.
The layer checks closed typed phase
and saved-command fields, fresh applied versus replay skipped vectors, and exact
complete LF-delimited stdout marker records. Unknown, duplicate, reordered,
truncated or malformed markers cannot override the declared vectors.

Each raw dump must have the exact 18 table containers and forty unique typed
ledger entries with the literal migration versions and UTC timestamps. Fresh and
empty replay dumps must contain no fixture rows. The layer re-derives ledger/data
hashes using the producer encoding and schema hashes from actual bytes, binds
all declared before/after hashes, preserves the ledger and schema across phases,
and requires identical fresh/empty and populated-before/after dumps. The prior
PG layer independently binds populated-after rows to the final snapshot. SQL
files are bounded nonempty UTF-8 data and are never executed.

This is **receipt consistency only**: SQL bodies/DDL/schema completeness and
candidate input checksums, driver generation/source authority, command capture
and actual execution remain unverified. A trusted-looking invocation digest is
not registered profile authority. The positive synthetic schema is deliberately
opaque; it is not a real pg_dump or migration acceptance fixture. All existing
missing families remain, including `paid_migration_replay`, with additional
`paid_migration_schema_semantics` and `paid_migration_driver_provenance` diagnostics.
The result remains unavailable/incomplete, with no verified IDs and every flag
false; `observed_migration_phase_count` is diagnostic only. CLI plan/validate never
select this layer. Source/document/media corroboration and DTO remain unfinished,
and no historical run or acceptance profile is promoted by these checks.


The internal `inspect_paid_selector_work` layer applies the complete existing
common/PG/migration receipt chain first, then interprets only the two fixed
`TestPostgresPaidCatalogGrantBeforeWork` Bankone/Banktwo cases. It checks six
phase snapshots per case plus each final snapshot: fourteen diagnostic snapshots.
It never supplies a final reader/identity counter absent from the producer.
The other ten paid cases retain exactly their existing validation depth.

Its closed selector request records require the exact eight fields, completed
status 200, empty test-transport request ID, three distinct makes/models/
configurations scopes and idempotency keys, and scope-specific closed payloads
for 2024/US/example/car. Request times must lie inside their child case; finite
JSON durations use exact decimal values within inclusive 0–120 seconds. Negative
nonzero decimals and values just above 120 cannot underflow or round into range.
Monotonic elapsed time is not asserted equal to wall-clock timestamp subtraction.
The separate exact-number parse preserves the unchanged raw/envelope/transport
ceilings and all reserved identity checks. Requests in case, Go measurement and
embedded collector copies are compared using parsed exact numeric values, so
sub-float duration differences cannot hide behind the older copy checks.

The before snapshot has no selector work; every later snapshot/final has exactly
three completed metadata requests and three literal provider selector routes per
bank. Concurrent initial request/trace ordering is allowed, while later lists
must retain their selected order and values. Article ensure, all six article
counts, source/asset/model/payment work, proxy activity and worker inventories
remain zero/empty; six phase reader counters remain zero. Grant/identity counts
must progress monotonically with zero selector counts, and the final grant count
must equal the last phase. Mutable account/session/grant SQL rows are not compared
as immutable whole-snapshot values.

The layer adds only `observed_selector_case_ids` (two literal identities) and
`observed_selector_snapshot_count` (14). It retains every inherited missing
validation family, including `paid_selector_work_and_model`, and explicitly adds
`paid_selector_http_outcomes` and `paid_selector_request_provenance`. HTTP status,
body, headers, actual execution, source/model/lifecycle semantics, supervisor
provenance and authority remain unverified. Results always remain unavailable/
incomplete, verified case IDs stay empty and every verification/deployment/
cutover flag remains false. No profile, filename, raw kind or CLI command selects
this API. Synthetic mutation tests and confined-store checks provide parser
regression coverage and contribute zero product acceptance cases.


Bounded local checks:

```sh
python3 -m unittest scripts/dev/test_release_acceptance.py -v
python3 -m unittest discover -s scripts/dev -p 'test_*.py'
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
git diff --check
```

Tests use inline synthetic envelopes/files and the actual disabled committed task
at the locally available HEAD, including a depth-one clone.
They are parser/tooling tests, never actual product acceptance receipts. Do not
run providers, browsers, Docker or cloud commands as part of this milestone.

## Internal DTO120 receipt consistency

The explicit internal `inspect_dto_receipts` API interprets only the declared
`raw` artifact `dto-artifact.zip`; disabled CLI plan/validate never invoke it.
It uses the existing in-memory three-member ZIP parser without extraction and
strict duplicate-free UTF-8 JSON with exact Decimal number tokens. Expanded
limits remain 4 MiB each for `browser/evidence.json` and `ready.json`, and 8 MiB
for the opaque `go-fixture.log`; transport limits remain unchanged.

The closed v1 DTO evidence requires exactly forty frozen scenarios crossed with
Chromium, Firefox and WebKit, all 120 unique rows reporting passed. Failed,
unavailable, skipped, extra or missing rows cannot become partial success.
The inspector checks the fixed Playwright/browser/revision metadata and the
source-derived six-input and eleven-asset hash/length inventories frozen at
`99df69caaeb4d5ccf6d0ffbf0377fe6d5d872a3d`. These expected values are literal
reviewed constants, never copied from supplied receipts or mutable checkout
contents. SDK hashes must match the frozen bundle hash. A source-content or
metadata inventory change needs a separately reviewed successor contract.

Each row has a finite exact numeric elapsed time in inclusive 0–120 seconds,
excluding bool/string/null. **120 seconds is a diagnostic receipt ceiling; it is
not a producer timeout or independently observed execution duration.** Request
lists allow retries, arbitrary order and empty lists, with at most 256 entries
per row and 8,192 total. Closed method/path/query inventories, bounded string
arrays and a re-derived SDK-request count reject substitutions and contradictory
counts. Query values remain opaque and are never included in diagnostics.
Readiness requires the closed DTO schema, a canonical HTTPS 127.0.0.1 port,
matching SDK hash and matching certificate digest. Matching certificate copies
are consistency observations, not independent TLS capture evidence.

The result always stays unavailable/incomplete, with no verified IDs and all five
verification/deployment/cutover flags false. The 120 normalized observed pairs,
request total and eleven asset observations are diagnostics only. Source hash
equality does not establish candidate execution, authenticated CI capture or
collector authorship. Request rows omit network origin and response bodies;
passed strings cannot independently reproduce DOM assertions. Browser binary
installation/process identity, TLS capture, reproducible SDK builds, host/input
provenance, supervisor commands/cleanup, authenticated CI/archive provenance and
registered supervisor/reviewer authority all remain explicitly missing. The Go
log and SDK provenance JSON contents are not interpreted as proof. DTO transport
mocks cannot satisfy API21 or real Firebase/Stripe/bank acceptance. Existing paid
inspectors and every disabled profile remain unchanged.


## Internal paid HTTP projections

`inspect_paid_http_receipts` is an explicit internal successor to the common,
PG, migration and selector-work inspectors. No raw kind, filename, profile or CLI
command selects it. It checks exactly 18 retained HTTP observations for each of
`TestPostgresPaidCatalogGrantBeforeWork-bankone` and `...-banktwo`: closed JSON
bodies and header projections, configuration/article PG bindings, exact redacted
routes and the declared reader/identity counter sequence. The two measurement
copies and existing result/collector hashes remain required. Other paid cases
retain their predecessor validation depth.

The only new diagnostics are `observed_http_case_ids` (those two IDs in bank
order) and `observed_http_observation_count: 36`. These are zero additional
verified cases. Every inherited diagnostic and missing family stays present;
`paid_http_wire_body_provenance` and `paid_http_transport_authority` are appended.
The result remains unavailable/incomplete with no verified IDs and all authority
flags false. CLI counts remain zero, tiers remain disabled, and `r6-release.json`
is unchanged.

`body_sha256` and `body_size` are typed retained declarations. Original response
bytes are unavailable, so the inspector does not reconstruct their digest or
length from projected JSON. Body key ordering, arbitrary valid declared digests
and sizes 1 through 262144 do not establish wire provenance. The observer retained
only selected headers; validating this projection does not establish the absence
of unrecorded wire headers. Redacted media paths are not usable capabilities or
proof of media rights. Counter relationships do not establish actual request
timing, authenticated capture, supervisor authority, licensed enrollment, model
execution, fixture/staging acceptance or release authority.

Synthetic regression coverage constructs both banks independently of production
helpers and private historical evidence. Semantic negatives repair measurement,
phase, immutable-row, migration and result/collector seams to reach the closed
checks; separate copy/hash and confined-store negatives preserve transport guards.
