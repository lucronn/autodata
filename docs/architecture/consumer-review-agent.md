# Consumer review agent contract

Issue: https://github.com/lucronn/autodata/issues/89
Project: https://github.com/users/lucronn/projects/8
Plan: ../superpowers/plans/2026-09-14-consumer-review-agent.md

The `autodata-consumer-agent` is a release-readiness evaluator for the public
chat experience. It calls the chat HTTP boundary with real consumer prompts,
resolves vehicle choices when required, waits for the persisted answer, and
evaluates the response as a consumer would. It records a redacted response,
the exact request and answer revision, rubric dimensions, findings, command
evidence, and an overall decision in a machine-readable report.

The agent checks applicability, exact vehicle resolution, removal and
installation coverage, step ordering, figures beside steps, torque and final
checks, consumer-copy cleanliness, review labeling, PDF readiness, and PDF
revision parity. It does not invent automotive facts or approve safety-critical
content. A failed or uncertain check is retained as a finding or `needs_review`.

Issue creation is explicit (`--create-issues`) and uses structured GitHub CLI
arguments. Each generated issue contains a stable finding marker, case name,
implementation SHA, report path/hash, and a bounded reproduction. Existing
issues with the same marker are reused, so repeated reviews do not create
duplicates. Passing cases never create issues.

Reports may contain the consumer-visible response and metadata, but must omit
raw provider HTML, credentials, authorization headers, cookies, and arbitrary
request headers. The agent is allowed to exercise dev or explicitly supplied
non-production chat URLs; production deployment remains disabled by policy.

## Required decision

Every run must produce a report with `pass`, `fail`, `blocked`, or
`needs_review`, a score by rubric dimension, findings, response hash, exact
implementation SHA, and issue actions. The report is not a human approval and
does not change the guide's `UNREVIEWED` state.

## Todo

- Add the registered consumer-agent prompt and its least-privilege capability.
- Add the HTTP chat runner, consumer rubric, redacted response recorder, and
  stable finding-to-GitHub-issue workflow.
- Add deterministic transport/rubric/issue-deduplication tests.
- Enforce case-declared procedure-depth terms, including torque and final checks.
- Run the agent against multiple live vehicle/procedure cases and preserve the
  response and review reports.
- Reconcile confirmed findings, update the production-readiness evidence, and
  close only issues whose acceptance evidence is complete.
- Make clean Compose startup migration-safe: the ingestion worker must wait for
  the migration runner to complete successfully before it can process durable
  chat work.
- Make a ready PDF resilient to transient internal source-image failures with
  bounded retries at the Go proxy boundary.
- Give the internal Go-to-ingestion proxy a bounded 120-second default for
  provider-backed guide/PDF generation; explicit deployment overrides remain
  supported.
- Make provider-backed figure retrieval resilient on first use with bounded,
  serialized retries for transient source responses, while retaining strict
  origin, vehicle, size, and fail-closed validation.

## Acceptance evidence

The committed implementation was exercised in report-only mode through the
chat HTTP contract, using the real chat state machine and live AutoAPI Two
source retrieval in a loopback development adapter. The latest aggregate
report is retained outside the source tree at
`tmp/consumer-review-live/consumer-review-42469167db6ddb1f23428c4d.json`.
The implementation under test is `3175ba4dd994fff4cd752451b3791c4c0cf4df43`.
Its SHA-256 is
`23bd27b93a0918eeced3ca5f1e71f4fc2007d6dc3456f6ee635cefe4ecb19fe3`.

| Case | Result | Steps | Figures | PDF SHA-256 |
| --- | --- | ---: | ---: | --- |
| 1997 Toyota RAV4 oil and water pumps | pass | 99 | 80 | `21aa27d02f89826bddd793964e8384f98750304cd320fc199f9b03cf2d6df343` |
| 2005 Toyota Camry starter | pass | 14 | 4 | `6fe70042efa04f114486ea51789b92c48787cb0325dd3d4140d0ec79efe8115d` |
| 2010 Subaru Forester SOHC water pump | pass | 87 | 36 | `a02ddad8b39002c9f5f13455ccae413d0d12ecfcafd750eb740f1bee87680276` |
| 2002 Honda Civic LX front caliper | pass | 14 | 5 | `1735197a3de294da437788125f541c1487da500376132d2ec28f96071b791a27` |

All six rubric dimensions passed for all four cases: applicability,
procedure coverage, figures, safety/review labeling, consumer-copy hygiene,
and PDF integrity/revision parity. The report contains four passes, zero
failures, zero `needs_review` results, zero blocked cases, and no issue
actions. The projection check also confirmed that the recorded consumer
responses contain no `source_`, `evidence`, `raw_html`, or `worker_stream`
fields. A fresh 61-page RAV4 PDF from the same run was rendered at 120 DPI;
the first, representative middle, and final pages were visually inspected
for clipping, readable figures, clean numbering, headers, footers, and final
installation/check steps. Its SHA-256 is
`4f2da8686ada5dd6cb82df7155a2d338b65b1797616907c3cb40e909935f5a5d`.

After that live run, the scorer was hardened in local commit
`5c28a0a2624cbb497759030508ffe929b5910bb5` to require case-declared depth
terms such as `torque` and `check`; the focused regression and the full
developer test suite pass. The retained live report is intentionally not
relabeled as generated by this later scorer. A fresh live matrix rerun is still
required before this hardening can be called release-verified. A follow-up
Compose startup stalled in Docker's credential-helper/build step before any
containers were created, so the live report remains attributed to the earlier
implementation.

The negative path was also exercised against the valid RAV4 vehicle for a
battery request with no returned procedure article. It resolved the vehicle,
returned a failed lookup without fabricating a procedure, and withheld the
final PDF. This expected `fail` result is tracked separately from the
four-case release pass and is marked `expectation_met` in its report. The
negative report is
`tmp/consumer-review-negative/consumer-review-2a8a000b3220a21f90fd94b9.json`
with SHA-256
`3884e26423809b5f149ba3347eb56d3cda2198dc1f4fe54634cab4aad3f2b9b7`.

## Current release blocker

A fresh isolated Compose run on 2026-09-15 first reproduced a startup race:
the `ingestion-worker` began before the migration runner had created
`chat_runtime_queue` and exited with `UndefinedTable`. Commit `59d1bf1`
repairs this by requiring `migration-runner: service_completed_successfully`
before the worker starts; the focused regression passed and the isolated
worker is healthy.

The same clean runtime then exposed two remaining live reliability blockers.
The Go-to-ingestion proxy now has bounded retries for transient 502/503/504
responses and a 120-second default, but the final current-code matrix still
returned first-fetch 502s for Camry and Forester while later direct requests
succeeded. The latest report is
`tmp/consumer-review-live/post-hardening-final-timeout120/consumer-review-32506b2e5b0a2086ef74d08d.json`
with SHA-256
`d757602c2e8cbbfae679463291d8c4de1191164b8056c5c566cabf0514aa09b9`:
RAV4 and Civic passed; Camry and Forester were blocked. Issue #89 remains
blocked and no live release claim is made until first-request PDF generation
is reliable across all four vehicles.

The explicit consumer issue-creation run retained the same 2/4 outcome in
`tmp/consumer-review-live/post-hardening-issue-creation/consumer-review-7388d45911aed5a8bc27d126.json`
with SHA-256
`f9ad5659f4ad1b3d52624f5fb6e57cef055019e7b1f40e4699a3ced14eddbfa2` and
created the deduplicated reliability findings [#90](https://github.com/lucronn/autodata/issues/90)
and [#91](https://github.com/lucronn/autodata/issues/91). Passing cases created
no issues.

The next release repair is tracked in [#90](https://github.com/lucronn/autodata/issues/90)
and covers the provider-read boundary exposed by the cold matrix. The source
connector currently aborts a first PDF render when an allow-listed provider
image read returns a transient 502/503/504 or rate-limit response. The repair
will add a finite, capped retry at that boundary; it will not retry redirects,
validation failures, authorization failures, oversized content, or arbitrary
exceptions. Issues #90 and #91 remain open until a fresh cold matrix proves
all four vehicles complete their first PDF request.

The release verification at implementation `8a2a7ee` now passes cold and warm:
`tmp/consumer-review-live/post-public-compaction-cold-v2/consumer-review-73d119083fa152737b002ee1.json`
has SHA-256
`21d39bca197a429d6dbe16064cf756f825eb420765e3c9b78f0122ae54eb9272`, and
the warm replay is
`tmp/consumer-review-live/post-public-compaction-warm/consumer-review-5188d0e5b668927d2c870249.json`
with SHA-256
`8c28ab0dc68158d499fc41e9b3a8902d2e0f57dbc677f90c7adbff255de8367e`.
All four cases pass with no issue actions. The PDF hashes are stable across
cold and warm runs: RAV4 `384f036a...`, Camry `f4ef9440...`, Forester
`5b5868b6...`, and Civic `334f412a...`. Issues #90 and #91 are resolved by
the bounded poll retry, compact public projection, and aligned consumer
response limit.

The public API also retries only transient internal query-read responses while
the consumer is polling a processing query. The retry is finite, preserves
caller cancellation and response limits, and does not mask authorization or
validation errors. The consumer runner reports the aggregate `blocked` state
as `blocked`, so release evidence cannot be mistaken for a softer review
result.

The runner's `--timeout` applies to both the HTTP transport and each case's
processing poll. This keeps the documented cold-start bound authoritative for
longer provider-backed procedures such as the Forester case.

The runner also treats a retryable 502/503/504 during a processing poll as a
bounded transport event: it backs off and polls again until the same finite
case deadline. Persistent retryable failures, non-retryable failures, and
deadline expiry remain blocked. This behavior is pending a focused regression
and a fresh cold matrix at the current implementation SHA. This verification
is now complete at `8a2a7ee`.

The latest cold matrix also exposed a public-response budget issue: durable
Camry and Forester snapshots were approximately 21.6 MB and 19.3 MB because
repeated evidence/provenance metadata was still present in the serialized
answer, exceeding the API proxy's 8 MB limit. The next gated repair compacts
that metadata at the worker public-projection boundary while retaining the
consumer procedure, figures, review state, and PDF revision parity. The
current cold and warm matrices confirm the compact response remains complete.

## RAV4 4WD matrix extension

Issue: https://github.com/lucronn/autodata/issues/85
Plan: ../superpowers/plans/2026-09-15-rav4-4wd-consumer-matrix.md

The reproducible matrix now includes the exact 1997 Toyota RAV4
2-door 4WD 2.0L request for oil pump, water pump, timing belt, and power
steering pump replacement. AutoAPI Two exposes the exact 2-door variant as
provider vehicle `41216`; the 4-door variant remains a separate selectable
vehicle (`41218`) and must not be guessed when a body style is requested.

The live report-only acceptance passed at implementation
`1c4d69c154e3346caa398b0ae7e9e43a511e3247`. It resolved provider vehicle
`41216`, returned a complete 131-step procedure with 89 figures, passed all
six rubric dimensions, and returned a revision-matched PDF. The report is
`tmp/consumer-review-live/rav4-4wd-formal-v2/consumer-review-f6156af1dbaeea0df7c055f3.json`
with SHA-256
`746224da1c5c251ca92f95348ec4ed2fae2485352bf17dca3e20161ed8f7404d`; the PDF
SHA-256 is
`754407d8d5abda5f81865bf5136f6d603e0c4d07ee24d3af2d951e67fd8a3c32`.
Automated readiness does not approve the stored source evidence or procedure;
the uncached AutoAPI session and human technician review remain explicit Issue
#85 follow-ups.

### Current-head five-case recheck

Each matrix case was run independently against the live QA API at implementation
`7a4cb33ae2337bf1807144756bb5ccd735d7e480`; all five passed all six rubric
dimensions with no findings or issue actions.

| Case | Steps | Figures | Report SHA-256 | PDF SHA-256 |
| --- | ---: | ---: | --- | --- |
| 1997 RAV4 2-door 4WD, four components | 131 | 89 | `5573d0075f34621bd6b98349b959fb61791d41ee9b11918c6fa54c6e487892c1` | `754407d8d5abda5f81865bf5136f6d603e0c4d07ee24d3af2d951e67fd8a3c32` |
| 1997 RAV4 2-door 2WD, oil and water pumps | 101 | 80 | `4f94251cb2aaa89491129d4822eb97effedeb86f1d0cde09bc26636d0146334f` | `d4008dffb9c8dce162845c6a77eaa55e80e9a38ffa60ec979baf78c6bfe3c955` |
| 2005 Toyota Camry, starter | 21 | 4 | `41c17925e79e7e156a5ebefae6e5a5ddf8fcedabd804260e862c9d1af2042392` | `8afcdccb2b29022a396956722f2d5739452cfd5e2e9c8f4b697939c9b0bc6221` |
| 2010 Subaru Forester SOHC, water pump | 92 | 36 | `5c016842789f3a4390755b13804ff70d4ce5d6539ef418f1928bf6be2a71c3d0` | `978642687d8d95734271b21f2a3564b1ca587369e48c9d4af1abfd67fe7b72f9` |
| 2002 Honda Civic LX, front caliper | 14 | 5 | `312635f7ac5fc86f9e58f498c705a07ddabc2de8df16bad77b8e2c001cc7ed75` | `334f412a2608f8f39f107a79e8c52ba22f20cb34d92997ec8dbd09257a6a7c03` |
