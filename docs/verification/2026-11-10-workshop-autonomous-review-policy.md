# Workshop autonomous review policy verification

The single-maintainer repository maps all owned paths to `@lucronn` in `.github/CODEOWNERS`. PR #389 is authored by that same GitHub account. At the `a647ebb` planning base, GitHub branch protection required zero approving reviews and did not require CODEOWNERS approval, while `docs/github/operating-model.md` unconditionally required owning CODEOWNERS review. That mismatch blocked a reviewed, CI-green Workshop app fix even though a self-authored GitHub approval cannot be recorded.

Acceptance:

- [x] The operating model accepts a retained independent AI-review verdict at the exact candidate SHA for the single-maintainer path, without calling it a GitHub CODEOWNERS approval.
- [x] GitHub-required checks, any configured approving-review count, blocking threads, and the autonomous eight-gate release controller remain enforced in the documented rule.
- [x] The Project settings checklist and autonomous-development documentation agree with the operating model; CODEOWNERS remains unchanged.
- [x] The saved hourly automation prompt instructs the next safe Workshop app task when a PR is waiting and stays quiet on unchanged state; the next scheduled execution has not yet been observed.
- [x] PR #389 was rechecked and integrated only after current exact-head review and CI; Issue #388 and Project #8 reflect its confirmed merge pending this documentation closure.
- [ ] PR #387 documentation closure is rechecked and integrated only after current exact-head review and CI; then Issue #385/#388 and Project #8 reach Done.

Evidence and limits: Live branch-protection inspection on 2026-11-10 showed `required_approving_review_count: 0`, `require_code_owner_reviews: false`, and strict required status check `Validate autonomy policy and evidence contract`. PR #389 at `832d9558370d85ef9f5f154cfe98e26954614cf1` has all three required jobs successful and no GitHub review; its prior separate AI review found no findings. These are development-only observations. They do not establish real checkout, entitlement grant, article access, or production readiness. No production deployment is authorized.

The planning-only checkpoint `cd7b0ffa187a1f570a9df03ab2c5fc23a3215025` was committed after Issue #385 and Project #8 were updated and read back. The exact-SHA pre-implementation command exited 0 with `status: synchronized`, `errors: []` before the policy-document change.

Policy-candidate local checks: `python3 -m unittest scripts.dev.test_repository_governance -q` ran 10 tests, all passed; `python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -q` ran 146 tests, all passed (expected negative-fixture diagnostics appeared in output); `git diff --check` passed. The existing hourly automation was updated via the Codex app and its saved `ACTIVE` hourly configuration was read back. This is configuration confirmation, not evidence of a subsequent scheduled run.

Tracking: [Issue #385](https://github.com/lucronn/autodata/issues/385), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-10-workshop-autonomous-review-policy.md).
