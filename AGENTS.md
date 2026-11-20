# AutoData agent instructions

Ship the smallest change that makes a Workshop user path work on the existing
stack. Reproduce the problem, edit the code that owns it, and verify the user
path. Use the current code, tests, and deployed configuration to understand the
system. Architecture notes and past plans are references. Change a design
when doing so makes the product simpler or closes a release blocker. Preserve
public API and data compatibility or provide a versioned transition.

Start routine work directly. Use a short branch and pull request. Reuse an
existing issue when useful. Delegate independent work when it saves time, with
clear ownership of each change. Plans, Project entries, and agent review chains
are optional for routine work. The synchronized planning record applies only
to jobs explicitly submitted to the [autonomous runner or orchestrator](docs/agents/pre-implementation-gate.md).

## Verify and release Workshop

- Start in `apps/api-go/workshop/` for the UI and `apps/api-go/` for its API.
  From the repo root, run `node --test apps/api-go/workshop-client.test.mjs`
  for UI changes and `(cd apps/api-go && go test ./...)` for API changes.
  Use the [local stack instructions](README.md#start-the-local-stack)
  to exercise the browser flow.
  When the user flow changes, smoke test it in a browser on local or approved
  staging. Include worker or integration checks when the change crosses
  those boundaries. Report what you exercised and what is still unverified.
- Protect credentials, licensed source content, provenance, and access
  controls. Test auth and entitlement denials when touched. Use Stripe TEST
  for purchase testing and verify server-side grants. For schema changes,
  verify the upgrade and recovery path against a disposable database.
- Follow required CI and branch protection. Use the approved environment and
  release path to promote the tested revision. Confirm staging smoke,
  readiness, and a compatible rollback before authorized production rollout.
  Report a missing capability as a release blocker and work the next safe
  step. The checked-in [production workflow](.github/workflows/release-workshop.yml)
  still has blocked production publish and deploy jobs. See the
  [staging runbook](docs/operations/workshop-staging-executable.md) for the
  supported staging commands.
