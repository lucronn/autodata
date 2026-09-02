# AutoData Autonomous Agent Runbooks

## Run a task

1. Confirm the task is represented by an Issue or Project item.
2. Create a unique `run_id` and pin `base_sha`.
3. Ask the architect agent for a task contract.
4. Reject the run if the contract has ambiguous outputs or acceptance criteria.
5. Create an isolated worktree and assign one builder.
6. Run independent verifiers against the implementation SHA.
7. Assemble the evidence bundle.
8. Evaluate the deterministic policy.
9. If it passes, create/update the PR, update the Project, merge the exact SHA, and deploy only to ephemeral/dev.
10. If it fails, record the complete reason and retry or dead-letter according to policy.

## Agent disagreement

When two agents disagree:

1. Preserve both reports unchanged.
2. Compare their implementation SHA, contract version, fixtures, and commands.
3. Retry the disputed gate with an alternate reviewer.
4. Do not average contradictory decisions or discard the stricter result.
5. Mark `blocked` after the retry budget is exhausted.

## Failed fast lane

If fast-lane processing fails, do not publish `viewable`:

1. Preserve the raw source snapshot and failure evidence.
2. Classify the failure as transient, source drift, schema mismatch, missing identity, or quality failure.
3. Retry transient failures with the same idempotency key.
4. Use a new source snapshot only when the source agent records why the previous snapshot is invalid.
5. Send exhausted work to the dead-letter stream and expose `failed` or `needs_review` to the client.

## Failed deep section

If a deep section fails after the dataset is viewable:

1. Preserve the last successful section revision.
2. Mark only that section `failed`.
3. Retry with bounded backoff.
4. Dead-letter after exhaustion.
5. Keep the core dataset readable.
6. Replay only after the cause or source snapshot changes.
7. Publish a new section/revision only after evidence gates pass.

## Unsafe change

For a critical security, provenance, safety, or destructive-migration finding:

1. Stop the release controller.
2. Do not merge, deploy, or update the task to Done.
3. Preserve the finding, reproduction, and affected SHA.
4. Create a remediation task linked to the original task.
5. Allow the orchestrator to retry only after the candidate changes.

## Recovery and rollback

The release agent may roll back an ephemeral/dev deployment to the last verified artifact. It may not rewrite published dataset revisions. Data recovery uses a new corrective revision or a revocation/takedown transition with audit history preserved.

## Secret handling

Agents must redact credentials as `[REDACTED_SECRET]` in logs and reports. Do not print environment files, tokens, webhook secrets, private keys, or provider responses that contain credentials. If a secret appears in output, stop the run, redact the artifact, rotate the credential, and mark the run blocked.
