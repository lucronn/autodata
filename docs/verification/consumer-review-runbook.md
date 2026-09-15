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

The report contains the consumer-visible query/answer projection, response and
PDF hashes, dimension evidence, findings, and issue actions. It deliberately
omits raw provider HTML, source URLs, evidence internals, credentials,
authorization material, cookies, and arbitrary headers. Retain reports in the
approved run-artifact store; do not commit live responses to the source tree.

A report with `pass` has no issue actions. `needs_review` means the consumer
response is incomplete or ambiguous and must be dispositioned before release.
`fail` or `blocked` is release-blocking until the reproduction is corrected or
the dependency is restored. Re-run the same case after a fix and link the new
report hash in the issue before closing it.

The PDF link is part of the consumer contract. A guide that advertises a ready
PDF but returns a transient 502/503/504 is a release-blocking finding until the
proxy's bounded retry behavior is verified by a fresh cold and warm matrix.

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
steps, figure URLs, review state, and PDF revision identifiers must remain.

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
