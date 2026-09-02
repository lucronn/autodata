# AutoData Release Controller

## Purpose

The release controller is the only component allowed to turn a validated agent run into a GitHub release transition. It is deliberately separate from the model runner: provider worktrees cannot call `gh`, while this adapter receives only the least-privilege GitHub identity needed by the release job.

Before any external command, the controller verifies:

- `run-manifest.json` passes `scripts/autonomy/validate_run.py` with every evidence hash inside the supplied evidence root.
- The implementation SHA is a 40-character exact match for the checked-out candidate `HEAD`.
- The run decision and every required gate decision are `pass`.
- Critical and high findings are zero.
- The repository is `OWNER/REPO` and the deployment target is not production.
- The registry designates exactly `autodata-release-agent` as merge authority.

## Command behavior

[`scripts/autonomy/release_controller.py`](../../scripts/autonomy/release_controller.py) has two modes:

```bash
# Read-only plan and validation; recommended for inspection
python3 scripts/autonomy/release_controller.py \
  --repo-root . \
  --manifest /path/to/run-manifest.json \
  --evidence-root /path/to/run \
  --head-branch automation/task-123 \
  --project-number 7 \
  --pr-number 12
```

The plan pins merge with `gh pr merge --match-head-commit <implementation_sha>`. When configured, it adds the PR to the Project and edits the item with discovered field and option IDs. It does not invent view or field IDs; discovery remains an explicit bootstrap step.

Execution is opt-in for a dedicated release job only:

```bash
AUTODATA_RELEASE_AUTOMATION=enabled \
python3 scripts/autonomy/release_controller.py \
  --repo-root . \
  --manifest /path/to/run-manifest.json \
  --evidence-root /path/to/run \
  --head-branch automation/task-123 \
  --project-number 7 \
  --pr-number 12 \
  --execute
```

The execution path uses structured argv and never invokes a shell. It requires a known PR number before mutation, so PR discovery and Project item identity are explicit and auditable. The automation environment must provide an isolated GitHub identity with only the repository and Project permissions required for the operation; production cloud credentials are not part of this controller.

The controller does not rewrite published data, force-push, delete revisions, bypass required checks, or deploy production. A failed command stops the sequence and returns `blocked` with the command exit evidence.
