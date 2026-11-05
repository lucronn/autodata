# Dual-bank source fallback API verification

Issue: https://github.com/lucronn/autodata/issues/186

Project: https://github.com/users/lucronn/projects/8

Candidate `62e782c0b62ddd401193be7137f9a50f5d50a8b3` passed independent
code review and all eight required runtime cases. It is integrated by merge
`31ffe7ebcf28f345e0b5055b4dad10ebb7ed101c`, preserving six coherent development
commits. All 30 implementation paths are identical to the reviewed candidate
and remain within the original 32-path scope at gate
`258bdfe0eabf76409d4b3f93932f92f8bd548278`.

## Behavior verified

The API returns readable source content while canonical rewriting is running,
joins concurrent requests to one durable article job, and switches atomically
to the published canonical revision. Bank identities remain separate. Warm
reads reuse persisted content without source/model calls or new scheduling.
Canonical actions, ordered instructions, evidence and optional step images
survive projection; absent canonical numbering is not fabricated.

The required local fixture exercises actual Go HTTP, Python ingestion HTTP,
workers, PostgreSQL 17, S3-compatible storage and JetStream. Connector/model
responses are controlled fixtures; this is not authenticated live-bank or live
model certification.

For each bank, all four scenarios passed without skips:

1. Twenty concurrent public and internal reads create one durable job.
2. Source remains readable while the actual fixture model HTTP response is held.
3. Publication exposes consistent source/canonical tuples across the transaction.
4. Warm reads produce no external work and preserve immutable stored rows.

Fresh application of migrations001–038, empty replay and populated replay were
captured in each of eight distinct databases. Complete schema, 14-table raw
inventories, timestamps, hashes and source/canonical associations passed the
independent validator. Actual HTTP canonical steps are additionally compared
with independently decoded raw PostgreSQL JSON in all six published cases.

## Exact evidence

Run `/tmp/autodata-r3-acceptance-62e782c` completed successfully in129.981 seconds.
Pytest reported **8 passed in47.75 seconds**; the independent finalizer confirmed
eight Go executions, eight distinct fixture databases and all required
invariants. Build/start/input provenance and owned-resource cleanup passed;
there were no failures.

Frozen supervisor SHA256:
`4490d394cdffed9c2864d51a60384d687310534a8225a7e26f7fc9270dad9530`.

Independent product review: `/tmp/autodata-r3-review-62e782c/review.md`.
Independent supervisor review: `/tmp/autodata-r3-supervisor-4490d39-review.md`.
The latter passed19 pure checks and26 independent content-loss mutations.

The exact successor review passed39 focused Go tests and19 contract tests.
The integrated Go suite and19 contract tests also passed. Ordinary host tests
do not replace the eight required runtime cases. An initial integration
contract command used the API directory and failed discovery; its log is
retained, and the corrected repository-root invocation passed19 tests.

## Retained failures and remaining release work

Earlier diagnostic/runtime runs remain failed under their original roots.
They exposed scoped review/quarantine issues, R2/public shape differences,
empty-array serialization, fixture connection capacity and canonical-step
loss. The original c853 run passed its eight test cases but failed independent
evidence validation; it is not relabeled as accepted. The successor added raw
step comparisons and passed a fresh complete run.

This verifies the content API lane. Firebase customer identity, paid vehicle
authorization, session-bound media access, checkout/library UI, live providers,
backup/recovery and deployment acceptance are still required for the Workshop
launch. Production readiness is not claimed.


## CI follow-through: static privacy assertion

After the unrelated shallow-runtime tests were repaired, actual CI41691331286
passed Go/contracts/worker checks and failed one of98 developer tests: an exact
StorageKey field-spacing assertion no longer matches gofmt alignment. The
field/type/json exclusion tag and Go serialization behavior are unchanged.
The synchronized one-file catalog-runtime-assertion plan preserves that privacy
requirement while permitting horizontal whitespace, with red/green, mutation,
full development/Go privacy checks and independent review/full CI required.
This static test failure does not relabel the earlier eight R3 runtime cases.
The first checkpoint9fca22b correctly failed preflight because Project text
exceeded its limit and its record remained pending_tracking. A concise Project
update was then saved/read back before this synchronized successor checkpoint;
no implementation occurred under the failed record.
