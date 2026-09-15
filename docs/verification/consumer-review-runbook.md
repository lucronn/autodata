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
