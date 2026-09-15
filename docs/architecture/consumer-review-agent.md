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
