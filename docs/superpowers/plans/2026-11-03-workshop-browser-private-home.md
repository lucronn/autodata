# Workshop real-API browser fixture: private home directory

Source integration base: `fe7d206` on `codex/production-release-orchestration`. The exact `2de36a1` real-API run at `/tmp/autodata-workshop-browser-api-2de36a1` failed all 21 cases before Playwright entered any browser scenario. Every retained browser stderr reports Node `uv_os_homedir returned ENOENT`; the numeric UID 1000 runner has no passwd entry and the repository fixture drops `HOME` at both subprocess boundaries. The run's failed receipt remains unchanged. The read-only diagnosis at `/tmp/autodata-browser-home-diagnosis/diagnosis.md` is local evidence, not release acceptance.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Canonical UI plan: `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md`
Task: `docs/agents/tasks/2026-11-03-production-release/workshop-browser-private-home.json`
Record: `docs/agents/records/2026-11-03-workshop-browser-private-home.json`

## Decision and exact scope

After Issue/Project/canonical documentation synchronization, a committed `status: synchronized` record and passing exact-base preflight, modify only:

1. `workers/ingestion-python/tests/test_workshop_browser_integration.py`
2. `scripts/dev/test_workshop_browser_environment.py`

The fixture's final browser subprocess environment must create a fresh per-case `browser-home` directory inside the existing private case artifact directory, with mode `0700`, no reuse, no symlink or collision, and an absolute path. It must explicitly set `browser_env['HOME']` to that directory immediately before launching `workshop_browser_smoke.py`. Do not forward the host/container `HOME`, use `/`, add a passwd fallback, or widen the general environment allowlists. Keep this limited to the Playwright child; Go fixture and parent pytest environment remain allowlisted as before. A small helper in the owned fixture file may make the actual environment construction testable. If creating or verifying the directory fails, fail before browser startup and preserve the current failure/cleanup behavior.

This is a test-environment repair. Do not alter the Go API, authentication, grants, purchase, source/canonical/media assertions, browser scenario code, four pytest roots, 3+6+6+6 actual-case parametrization, 120 DTO inventory, six immutable image inputs, frozen external browser supervisor, resource deadlines, or prior receipts. The fixture must still reject unexpected outbound transport and retain owned loopback TLS/served-asset provenance. No Docker/image build, browser, provider, cloud, deployment, DNS or secrets action belongs to the implementation agent.

## Concrete synchronized todo

1. Synchronize Issue186/Project8 and the canonical UI plan, this plan, task and record; commit the checkpoint and pass exact-base machine preflight before implementation.
2. Add a focused red regression that exercises the actual final browser subprocess environment when inherited `HOME` is missing, `/`, empty or a host-only path; reject shared, symlinked and colliding case homes.
3. Create one private absolute `0700` home per case and set only final `browser_env['HOME']`; retain required Playwright/Go cache variables and reject secret sentinel forwarding.
4. Run focused unit and fixture syntax checks, inventory/scope/diff checks, commit/push one coherent fixture milestone and obtain independent exact-commit review.
5. Retain the failed 21-case run, then execute a fresh pilot and unchanged full 21-case real-API inventory with the frozen wrapper/image at one clean integrated SHA; independently inspect raw receipts and cleanup.

The new unit test should execute the same environment-building helper used by the real `_child` path, not a copied allowlist constant. Its red state must reproduce a missing home at the final subprocess boundary. Green checks should verify absolute owned `0700` home, distinct paths across cases, no symlink/collision reuse, no inherited host `HOME`, and preserved required nonsecret cache inputs. A non-browser Node `os.homedir()` probe can corroborate the symptom but cannot replace the actual browser run.

The coordinator will independently review the exact fixture diff, red/green logs, frozen build-input hashes and 21/120 inventories. Only a fresh 21-case run with no missing/extra/skipped/failed cases, real API/browser evidence, correct source-to-canonical and payment/media behavior, provenance and cleanup can close API acceptance. The prior failure proves no downstream customer behavior. Even a passing fixture run would not certify licensed bank, Firebase Google or Stripe TEST staging, hosting recovery, or production readiness.
