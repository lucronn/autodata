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
- Run the agent against multiple live vehicle/procedure cases and preserve the
  response and review reports.
- Reconcile confirmed findings, update the production-readiness evidence, and
  close only issues whose acceptance evidence is complete.

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

The negative path was also exercised against the valid RAV4 vehicle for a
battery request with no returned procedure article. It resolved the vehicle,
returned a failed lookup without fabricating a procedure, and withheld the
final PDF. This expected `fail` result is tracked separately from the
four-case release pass and is marked `expectation_met` in its report. The
negative report is
`tmp/consumer-review-negative/consumer-review-2a8a000b3220a21f90fd94b9.json`
with SHA-256
`3884e26423809b5f149ba3347eb56d3cda2198dc1f4fe54634cab4aad3f2b9b7`.
