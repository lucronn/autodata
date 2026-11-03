# AutoData Release Controller

The controller proposes structured commands and, only in an isolated release
job, requests an exact-candidate merge. Its default is read-only validation.
It does not deploy production. A successful merge command means a request was
accepted; only remote `MERGED` metadata confirms a merge.

## Trusted inputs and context

Use an independently pinned full `--trusted-base-sha` and committed `--task-ref`
for a v2 task. `runner.load_trusted_inputs` loads the frozen policy, registry,
plan, documents, verification commands, population and evaluator artifacts from
that base. The loaded evaluator must match the base. The controller calls
`orchestrator.validate_evidence_bundle(manifest, trusted, evidence_root)` again
before any GitHub discovery. It reopens artifacts and recomputes command,
profile, SHA, eight-gate and coverage validity. Claimed metrics, old decision
files, and legacy `evaluate` alone cannot authorize a release.

The implementation SHA must equal the checked-out candidate HEAD. Manifest,
frozen task and release-context repositories must agree. The frozen policy
must permit the requested merge/Project operations, and the registry must name
only `autodata-release-agent` as merge authority. Production remains forbidden.
Synthetic regression evidence remains synthetic; it cannot certify real
staging. The separately reviewed staging adapter and real staging collection
are prerequisites for production-candidate acceptance.

`--context` is a JSON object with exactly these fields (use discovered IDs):

```json
{
  "repository": "lucronn/autodata",
  "base_branch": "master",
  "head_branch": "codex/candidate",
  "pr_number": 123,
  "issue_number": 186,
  "project_owner": "lucronn",
  "project_number": 8,
  "project_id": "PVT_discovered",
  "project_item_id": "PVTI_discovered",
  "status_field_id": "PVTSSF_discovered",
  "review_option_id": "review_discovered",
  "done_option_id": "done_discovered",
  "dependency_field_id": "PVTF_discovered"
}
```

Numbers must be positive integers, excluding booleans. Strings reject empty
values, control characters and option prefixes. IDs have a restricted alphabet;
branches pass `git check-ref-format --branch` at the CLI boundary. Project owner
is independent of repository owner. The context references the existing Issue
item; no duplicate PR item is created.

The Issue body must retain exactly one machine-readable tracking comment:

```text
<!-- autodata-release
{...all fields of the frozen task's pre_implementation record...,
 "candidate_sha": "<40-character verified implementation SHA>",
 "evidence_sha256": "<plan evidence_sha256>",
 "unresolved_blockers": []}
-->
```

The ellipsis above is explanatory, not valid JSON: copy the complete frozen
record with its goal, canonical plan/document links, Issue/Project links,
concrete todo, synchronized status and timestamp. Then add the three shown
fields. This explicit record prevents ambiguous prose from being treated as a
verified blocker clearance or candidate reference. Non-ASCII issue prose is
supported. `blocked` and `blocker` labels block execution.

`build_release_plan` is pure and exposes `evidence_sha256` and `evidence_text`.
The digest is SHA-256 of the manifest serialized as UTF-8 with sorted keys,
compact separators, and `ensure_ascii=False`. The Project dependency text must
already equal that exact evidence text in normal merge mode. A coordinator
first synchronizes this Issue/Project index and then runs preflight. The
controller never invents tracking identifiers or treats a task title as proof.

## Read-only discovery and proposals

```bash
python3 scripts/autonomy/release_controller.py \
  --repo-root /path/to/candidate \
  --manifest /external/run/run-manifest.json \
  --evidence-root /external/run \
  --trusted-base-sha VERIFIED_FULL_BASE_SHA \
  --task-ref docs/agents/tasks/committed-v2-task.json \
  --context /external/release-context.json
```

Default validation writes no tracking, receipt or event files. Discovery uses:

- `gh pr view NUMBER --repo OWNER/REPO --json ...` for exact SHA, head/base,
  OPEN/non-draft state, merge readiness and successful check rollup;
- `gh pr checks NUMBER --repo OWNER/REPO --required --json name,state,bucket`
  to require a nonempty set of passing required checks;
- `gh project view NUMBER --owner OWNER --format json` for Project identity;
- `gh project field-list NUMBER --owner OWNER --limit 100 --format json` for
  field IDs and named Review/Done options;
- read-only GraphQL for Project field data types, complete item enumeration,
  Issue association and current field values; and
- `gh issue view NUMBER --repo OWNER/REPO --json number,url,state,body,labels`
  for the exact canonical tracking record and blocker state.

Project field inventories are bounded to 100 with explicit completion proof.
Item lookup follows at most 100 pages of 100 items, rejecting repeated cursors,
duplicate items, incomplete nested field inventories and unavailable scope.
Unrelated item-value variants such as Repository and Labels count toward
enumeration completeness and are ignored for tracking. The required Status and
dependency fields still require their exact IDs and value types, with duplicate
required values rejected. A first-page miss never authorizes a mutation.
A larger or incomplete inventory
blocks for an explicit discovery refinement. Mismatched IDs, wrong candidates,
unknown/pending checks or absent/stale tracking block before any mutation.

PR creation is a separate command proposal:

```bash
python3 scripts/autonomy/release_controller.py \
  --manifest /external/run/run-manifest.json --evidence-root /external/run \
  --propose-pr --head-branch codex/candidate --base-branch master \
  --body-file /external/release-body.md
```

It prints `gh pr create` argv without executing it. The default base is
`master`. The coordinator creates/discovers and attaches the PR separately,
then supplies a complete context. `--execute`, `--repair-tracking` and
`--propose-pr` are mutually exclusive; incomplete legacy flags cannot execute.

## Guarded execution and states

Add `--execute` to the complete validation command and set
`AUTODATA_RELEASE_AUTOMATION=enabled` only in the isolated release job.
The evidence/state directory must be outside the checkout. All commands are
structured argv with no shell. Project edits use the installed CLI's
`--project-id`, `--id`, `--field-id`, `--single-select-option-id` and `--text`.
No admin merge, protection bypass, automatic issue closure or branch deletion
is introduced.

The normal sequence is Review update, dependency/evidence update, immediate
PR recheck, `gh pr merge --squash --match-head-commit SHA`, remote confirmation,
and finally Done. A tracking failure or changed head stops before merge.
The immediate recheck also rejects a newly pending/failed check rollup.
Even a nonzero merge command is followed by read-only confirmation to resolve
an ambiguous remote outcome.

| Decision | Meaning |
| --- | --- |
| `proposal` | PR-create argv only; nothing executed. |
| `validated` | Local replay and live discovery passed; nothing mutated. |
| `blocked` | Validation/discovery/command failed; no confirmed merge is claimed. |
| `merge_pending` | Request accepted or retained as outstanding; remote PR remains OPEN; Project stays Review. |
| `merged` | Remote MERGED exact candidate and merge commit confirmed; tracking succeeded. |
| `merged_tracking_failed` | Exact merge remains confirmed; tracking failed; retry with `--repair-tracking`. |
| `tracking_repaired` | Confirmed merged candidate tracking agrees, including a no-op repeat. |

Under `evidence-root/release/`, `release-events.jsonl` retains phase, argv and
exit code for every executed discovery/mutation command. Failure text is
sanitized; raw stdout/stderr and Issue bodies are withheld. The atomic
`release-operation.json` records merge intent before requesting it so an
interruption cannot silently issue a second merge. A retained outstanding
request first requires an exact retained context, candidate SHA and evidence
digest. The controller then reads only the live PR identity and OPEN state;
queue checks becoming pending do not retroactively fail the original request.
It remains pending without another merge request or tracking mutation. Changed
heads/targets, closed-unmerged PRs, and mismatched retained records block. A
remote MERGED PR requires the separate tracking-repair mode. Older operation
records without candidate identity block for inspection rather than inferring
authorization. Read-only queue observation leaves all state files unchanged.
`release-outcome.json` retains the final sanitized decision, failures and mutation
results. `release-receipt.json` retains repository/PR/context, candidate, evidence digest,
target branch, merge commit and merge time. Local state and remote state are
both consulted on later invocations. A remote merged PR goes through repair,
not the normal OPEN preflight.

## Tracking-only repair

Use the same trusted inputs and context with `--repair-tracking` and the same
environment guard. The repair plan contains only Project evidence/Done updates;
it contains no PR create, PR merge or Review transition.

Repair replays the immutable bundle and rediscovers Issue/Project identities.
It requires remote `MERGED`, the exact candidate/head/base, merge commit and
merge time. It compares these with a retained receipt. If the process died
after merge before saving a receipt, repair reconstructs one from the verified
remote metadata before updating tracking. Closed-unmerged PRs, another merged
head, wrong target or conflicting receipt block. OPEN/draft/check readiness
conditions are not applied to a confirmed merged repair.

Only differing tracking fields are written. A failed repair after confirming
the merge returns `merged_tracking_failed` with its receipt, even if later
Project/Issue discovery fails before a tracking command. If no receipt survived
the original process, confirmed remote metadata reconstructs it before returning
that failure. A conflicting retained receipt still blocks without replacement.
Read-only repair validation may return a reconstructed receipt in its response
but never writes it or other state files. A third
invocation after successful repair returns `tracking_repaired` without a
mutation. Receipts are retained even when Done updates fail.

## Verification boundary

Controller tests use a complete v2 artifact bundle from real local checks with
a fake provider, and deterministic fake GitHub command responses. They verify
ordered argv, negative preflights with zero mutations, Unicode, pagination,
queued/confirmed outcomes, receipt reconstruction, failure and repeat repair.
Installed `gh project item-edit`, `item-add`, `field-list`, `pr checks` and
`pr merge` help are checked read-only for supported flags.

These are deterministic tooling results only. Real release-identity GitHub
runtime certification is **blocked / not_executed**. No live provider fixture,
GitHub mutation, production deployment, or real staging certification is
claimed. Independent exact-SHA review and integration verification remain
coordinator gates.
