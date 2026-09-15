# Consumer review agent runbook

The consumer agent is a report-producing acceptance check for the chat product.
It is not a source-of-truth automotive reviewer and it never changes the
guide's `UNREVIEWED` state.

## Run against dev

Before running the matrix against a fresh local Compose project, wait for the
migration runner to complete successfully and verify the ingestion worker is
healthy. A worker that starts before `chat_runtime_queue` exists will exit and
leave requests in `processing`; that is a deployment failure, not a consumer
review result. Use a bounded cold-start timeout such as `--timeout 300` for a
clean stack.

Set `AUTODATA_CHAT_BASE_URL` to the dev API origin and provide a report
directory outside the repository when the response may contain customer or
source data:

```bash
PYTHONPATH=. python3 scripts/dev/consumer_agent.py \
  --api-base-url "$AUTODATA_CHAT_BASE_URL" \
  --case-file scripts/dev/consumer_review_cases.json \
  --report-dir "$AUTODATA_CONSUMER_REVIEW_DIR" \
  --implementation-sha "$(git rev-parse HEAD)"
```

The default is report-only. Add `--create-issues --repository lucronn/autodata`
only after inspecting the report and confirming the endpoint is dev or another
explicitly authorized non-production environment. The agent searches all open
and closed issues for each stable marker before creating a new issue.

## Case format

Each case supplies `name`, `message`, `expected_vehicle`,
`expected_components`, `min_steps`, and `min_figures`. If the API presents
multiple exact variants, the agent selects the option whose fields match
`expected_vehicle`. A missing exact match is a blocked case, not a guessed
selection.

## Report and issue handling

The report contains the consumer-visible query/answer projection, response,
HTML, and PDF hashes, dimension evidence, findings, and issue actions. It deliberately
omits raw provider HTML, source URLs, evidence internals, credentials,
authorization material, cookies, and arbitrary headers. Retain reports in the
approved run-artifact store; do not commit live responses to the source tree.

A report with `pass` has no issue actions. `needs_review` means the consumer
response is incomplete or ambiguous and must be dispositioned before release.
`fail` or `blocked` is release-blocking until the reproduction is corrected or
the dependency is restored. Re-run the same case after a fix and link the new
report hash in the issue before closing it.

The HTML link is the preferred consumer artifact. A complete guide that
advertises ready HTML must return standalone HTML with inline CSS and every
prepared figure as a valid base64 `data:image/*` URI, with no remote asset
references and the same revision ID as the chat answer. A complete guide that
advertises a ready PDF must still return a revision-matched PDF; a transient
502/503/504 is a release-blocking finding until the proxy's bounded retry
behavior is verified by a fresh cold and warm matrix.

The API-to-ingestion proxy default is 120 seconds because provider-backed PDFs
may require multiple figure reads. It retries only transient 502/503/504
responses with bounded context-aware backoff. Keep the timeout finite and
retain explicit deployment overrides; do not treat an unbounded wait as a
readiness strategy. The clean matrix remains release-blocked if a first PDF
request fails even when a later manual request succeeds.

Transient 502/503/504 responses while polling a processing query are retried
at the public API boundary with finite context-aware backoff. Persistent
failures still surface as blocked. The consumer runner's printed decision is
the same as the aggregate report decision; in particular, a blocked case is
never printed as merely `needs_review`.

The `--timeout` value is applied to both individual HTTP operations and the
case-level processing poll. Use a finite value such as 300 seconds for a cold
Compose stack; do not infer a timeout from the HTTP setting alone.

During a processing poll, the runner may observe retryable 502/503/504
responses from the public API. It backs off and continues polling until the
same finite case deadline; persistent retryable failures and deadline expiry
remain blocked. Authorization, validation, malformed-response, and other
non-retryable failures are not retried.

The public answer must remain below the API proxy response budget. Internal
evidence and provenance metadata is not consumer content and must be removed
from the serialized public projection before the 8 MB boundary; procedure
steps, figure URLs, review state, and HTML/PDF revision identifiers must remain.

For an incomplete or failed guide, neither final artifact may be advertised as
ready. A deep-lane failure may leave HTML/PDF unavailable while the already
viewable response remains accessible; it must not revoke that viewable revision.

Latest cold verification at implementation `8a2a7ee` passes 4/4. The report is
`tmp/consumer-review-live/post-public-compaction-cold-v2/consumer-review-73d119083fa152737b002ee1.json`
with SHA-256
`21d39bca197a429d6dbe16064cf756f825eb420765e3c9b78f0122ae54eb9272`.
The warm replay also passes 4/4 in
`tmp/consumer-review-live/post-public-compaction-warm/consumer-review-5188d0e5b668927d2c870249.json`
with SHA-256
`8c28ab0dc68158d499fc41e9b3a8902d2e0f57dbc677f90c7adbff255de8367e`.
Issues #90 and #91 may be closed against these reports; retain the reports
outside the source tree.

The ingestion source connector also retries only allow-listed transient
provider reads, including 502/503/504 and rate limits, with a finite capped
backoff. Origin checks, vehicle scoping, response-size limits, redirects,
validation failures, and non-transient errors remain fail-closed. Verify this
boundary with connector tests and then a fresh cold matrix; a warm replay alone
does not establish first-use reliability.

## Negative-path acceptance

Run `scripts/dev/consumer_review_negative_cases.json` separately from the
release matrix. Its expected result is `fail`: the vehicle must still resolve,
the missing source content must not become a fabricated procedure, and no
final PDF may be offered. A matching `fail` result with
`expectation_met: true` confirms safe fail-closed behavior; it does not make
the production release matrix pass.

## RAV4 4WD matrix extension

The release matrix now includes the exact 2-door 4WD case under [Issue #85](https://github.com/lucronn/autodata/issues/85)
using [the dated plan](../superpowers/plans/2026-09-15-rav4-4wd-consumer-matrix.md).
The exact 2-door 4WD 2.0L RAV4 variant is provider vehicle `41216`; the
4-door 4WD variant is `41218`. The case must be selected by exact fields when
the API presents both options. Keep the request report-only and retain the
consumer projection plus PDF hash under the local artifact directory. Do not
claim technician approval from an automated pass.

The completed report at implementation `1c4d69c154e3346caa398b0ae7e9e43a511e3247`
is `tmp/consumer-review-live/rav4-4wd-formal-v2/consumer-review-f6156af1dbaeea0df7c055f3.json`
with SHA-256
`746224da1c5c251ca92f95348ec4ed2fae2485352bf17dca3e20161ed8f7404d`. It
passed 6/6 dimensions with 131 steps, 89 figures, and a revision-matched PDF
whose SHA-256 is
`754407d8d5abda5f81865bf5136f6d603e0c4d07ee24d3af2d951e67fd8a3c32`.

The full five-case matrix was then rechecked independently at implementation
`7a4cb33ae2337bf1807144756bb5ccd735d7e480`. RAV4 4WD, RAV4 2WD, Camry,
Forester SOHC, and Civic LX each returned `pass` with a score of 100/100,
complete removal and installation phases, required `torque` and `check`
language, and a revision-matched PDF. The individual reports are retained in
`tmp/consumer-review-live/current-head/`; the five report SHA-256 values are
`5573d0075f34621bd6b98349b959fb61791d41ee9b11918c6fa54c6e487892c1`,
`4f94251cb2aaa89491129d4822eb97effedeb86f1d0cde09bc26636d0146334f`,
`41c17925e79e7e156a5ebefae6e5a5ddf8fcedabd804260e862c9d1af2042392`,
`5c016842789f3a4390755b13804ff70d4ce5d6539ef418f1928bf6be2a71c3d0`, and
`312635f7ac5fc86f9e58f498c705a07ddabc2de8df16bad77b8e2c001cc7ed75`.

The uncached-source checkpoint also passed for the 4-door 4WD RAV4 variant
(`41218`). The live event sequence confirmed a derived-cache miss, source
retrieval, normalization, and procedure publication before the consumer agent
scored the answer. It returned 131 steps, 89 figures, and a revision-matched
PDF. The report SHA-256 is
`c7aab0b58d2ede3c238b454bde1dee21a6848d6f6640d070966ed5e83d47239e` and the
report is retained at
`tmp/consumer-review-live/rav4-4wd-4door-uncached-v2/consumer-review-8aa4a17d03c034f59b436725.json`.

## Final release-hardening acceptance

The final local hardening sequence is recorded at implementation `87ca230`
and documentation head `fa76df0`. The consumer agent now detects
ellipsized/provider-reference-only procedure rows and classifies a response
marked `complete` without both removal and installation phases as blocking
`fail`.

The fresh negative-path report is
`tmp/consumer-review-live/negative-completeness-v2/consumer-review-0065a3f0d4368d9d841847ca.json`
with SHA-256
`fd7de16d67d87aa87a1088211804c598ac05caea36d96369d82f2ca4939e681d`. It
returned `fail`, `expectation_met: true`, no PDF, and a blocking high-severity
phase finding.

The fresh positive five-case report is
`tmp/consumer-review-live/final-positive-v3/consumer-review-404c3bef2992b3eb731861aa.json`
with SHA-256
`33539182a7b02eaaf3df09716bf744bef3ef8208ad817e8d8e1138db80d1b038`. RAV4
2-door 4WD, RAV4 2-door 2WD, Camry, Forester SOHC, and Civic LX all passed at
score 100 with zero findings and zero issue actions. Each response and PDF
contains the exact selected vehicle applicability label; the RAV4 cover was
visually inspected and reads `1997 Toyota Truck RAV4 2-Door 4WD L4-2.0L
(3S-FE)`.

These are local, non-production acceptance artifacts. Do not infer technician
approval or remote README delivery from them; the former remains a human
review item and the latter remains blocked until an explicit push is
authorized.
