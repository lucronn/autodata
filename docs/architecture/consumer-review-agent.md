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
source retrieval in a loopback development adapter. The aggregate report is
retained outside the source tree at
`tmp/consumer-review-live/consumer-review-45261b9ee1e274e41ffe87ef.json`.
The implementation under test is `27fa5cd03485c30d670bfe3824b58b3743a7653b`.
Its SHA-256 is
`840d08df0c48f2762cbe55f58374d5786331f323bd434d580413d3253b798091`.

| Case | Result | Steps | Figures | PDF SHA-256 |
| --- | --- | ---: | ---: | --- |
| 1997 Toyota RAV4 oil and water pumps | pass | 99 | 80 | `1e78a153641e26815adbec2666a1dbe43ce7db34da1fdddb07220e2cb22e4fc9` |
| 2005 Toyota Camry starter | pass | 14 | 4 | `476c781f567c5e1a84a752f2390cc4b6876e8801aae4218be5aadc01cb1998db` |
| 2010 Subaru Forester SOHC water pump | pass | 87 | 36 | `745371a8cdd1f6f7ed9051c1eae64d6149e06c1d030ab944b49a8ae58d063888` |
| 2002 Honda Civic LX front caliper | pass | 14 | 5 | `86eb73d8d81cb7d063d013a74c7d6587071353898687e01830d8fd98ba3d5103` |

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
