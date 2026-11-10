# Workshop autonomous review policy verification

The single-maintainer repository currently maps all owned paths to `@lucronn` in `.github/CODEOWNERS`. PR #389 is authored by that same GitHub account. GitHub branch protection currently requires zero approving reviews and does not require CODEOWNERS approval, while `docs/github/operating-model.md` unconditionally requires owning CODEOWNERS review. That mismatch blocked a reviewed, CI-green Workshop app fix even though a self-authored GitHub approval cannot be recorded.

Acceptance:

- [ ] The operating model accepts a retained independent AI-review verdict at the exact candidate SHA for the single-maintainer path, without calling it a GitHub CODEOWNERS approval.
- [ ] GitHub-required checks, any configured approving-review count, blocking threads, and the autonomous eight-gate release controller remain enforced.
- [ ] The Project settings checklist and autonomous-development documentation agree with the operating model; CODEOWNERS remains unchanged.
- [ ] The hourly automation continues the next safe Workshop app task when a PR is waiting and stays quiet on unchanged state.
- [ ] PR #387 and PR #389 are rechecked and integrated only after current exact-head review and CI; Issue #385/#388 and Project #8 reflect confirmed outcomes.

Evidence and limits: Live branch-protection inspection on 2026-11-10 showed `required_approving_review_count: 0`, `require_code_owner_reviews: false`, and strict required status check `Validate autonomy policy and evidence contract`. PR #389 at `832d9558370d85ef9f5f154cfe98e26954614cf1` has all three required jobs successful and no GitHub review; its prior separate AI review found no findings. These are development-only observations. They do not establish real checkout, entitlement grant, article access, or production readiness. No production deployment is authorized.

Tracking: [Issue #385](https://github.com/lucronn/autodata/issues/385), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-10-workshop-autonomous-review-policy.md).
