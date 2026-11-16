# AutoData agent instructions

Ship the smallest working product change on the existing stack. Inspect the current behavior, change the owning code, run focused checks, and verify the user-visible path. Keep one active slice at a time. Do not assign routine work to parallel agents. Reuse an existing issue when one applies; routine user-directed work does not need a new plan, Project item, evidence packet, or approval from another agent before implementation.

Use a short pull request that says what works, how it was checked, and what remains unverified. Run deeper integration checks when the change touches payments, authentication, licensed data, schema migrations, or production deployment. Preserve source rights, access control, and rollback for those changes. Do not turn a missing optional test environment into a new infrastructure project when the product path can be tested directly.

`scripts/autonomy/runner.py` and `scripts/autonomy/orchestrator.py` have their own machine-checked planning contract. Follow [the autonomous-run gate](docs/agents/pre-implementation-gate.md) when invoking that automation. It does not gate ordinary user-directed edits.

Commit and push coherent, tested changes to a short-lived branch. Keep credentials and private source content out of commits and logs.

For sandbox commands and current service wiring, consult
`docs/architecture/infrastructure-and-dev.md` and inspect the running stack.
