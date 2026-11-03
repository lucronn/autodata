# Workshop DTO CI Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Retain actual Workshop DTO browser evidence on success and failure in GitHub Actions.

**Architecture:** Keep the existing actual Go TLS fixture and strict40×3 sequential browser runner. Publish its owned temporary directory through GITHUB_ENV before starting the fixture, then upload it in a separate always-run step. No application, SDK, API acceptance or host runtime changes.

**Tech Stack:** GitHub Actions, Bash, Python3.14, Go1.26, Playwright1.64.1.

**Spec:** docs/superpowers/plans/2026-11-03-workshop-customer-ui.md

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Canonical document: docs/verification/2026-11-03-workshop-dto-ci-evidence.md

## Global constraints

Only implementation path: `.github/workflows/autonomous-verification.yml`. Planning paths are this plan, its synchronized record and the canonical evidence document. Preserve120 DTO and21 separate actual API cases; no local Docker/browser launch, host evidence deletion, provider/credential access, production mutation, timeout increase or API acceptance claim.

## Concrete todo

- [ ] Expose a deterministic RUNNER_TEMP directory for actual DTO ready/log/browser evidence before fixture startup.
- [ ] Always upload the owned DTO evidence directory with a SHA-bound artifact name, finite retention and no missing-evidence silent success.
- [ ] Validate actual extracted YAML shell/readiness Python, success and failure evidence retention, unchanged strict120 inventory and bounded fixture cleanup; commit/push for independent review.


## Task1: Retain the existing actual DTO evidence

**Files:** Modify `.github/workflows/autonomous-verification.yml`; record evidence in the canonical document above.

**Consumes:** Existing `ready.json`, `go-fixture.log`, `browser/evidence.json` and failure screenshots from the actual Go TLS/Playwright command. **Produces:** downloadable `workshop-dto-browser-${{ github.sha }}` artifact, retained14days.

- [ ] Commit synchronized planning checkpoint and run `python scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-03-workshop-dto-ci-evidence.json --base-sha <checkpoint>` before workflow edits.
- [ ] Reproduce red with an external structural validator requiring a stable evidence directory, early GITHUB_ENV publication, and an `actions/upload-artifact@v4` step with `if: always()`, `if-no-files-found: error` and retention14.
- [ ] Replace `mktemp -d` with `fixture_dir="$RUNNER_TEMP/workshop-dto-browser"`; `mkdir -p`, chmod700, then `printf 'WORKSHOP_DTO_EVIDENCE_DIR=%s\n' "$fixture_dir" >> "$GITHUB_ENV"` before launching the fixture. Preserve the existing process-group trap and all120 runner arguments.
- [ ] Append the always-run upload step, path `${{ env.WORKSHOP_DTO_EVIDENCE_DIR }}`, name above, retention14 and missing-file error. The literal directory remains owned by this job; upload no unrelated workspace/home files.
- [ ] Extract the actual YAML run block, run Bash syntax validation and compile its heredoc Python. Exercise it with fake fixture/browser processes: success writes a120-row evidence document; forced browser failure remains nonzero while retaining ready/log/evidence; both modes terminate the fixture child group. Do not count fake checks as browser acceptance.
- [ ] Verify unchanged tracked scenario inventory and actual browser command, run `git diff --check`, commit/push, and request independent exact-SHA review before integration. Actual GitHub run remains pending until coordinator pushes the integrated candidate.
