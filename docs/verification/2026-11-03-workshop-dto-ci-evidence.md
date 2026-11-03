# Workshop DTO CI evidence retention

Goal: retain actual successful and failed DTO browser outputs from GitHub Actions.

Plan: `docs/superpowers/plans/2026-11-03-workshop-dto-ci-evidence.md`.
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

## Concrete todo

- [ ] Expose a deterministic RUNNER_TEMP directory for actual DTO ready/log/browser evidence before fixture startup.
- [ ] Always upload the owned DTO evidence directory with a SHA-bound artifact name, finite retention and no missing-evidence silent success.
- [ ] Validate actual extracted YAML shell/readiness Python, success and failure evidence retention, unchanged strict120 inventory and bounded fixture cleanup; commit/push for independent review.


## Boundary and current evidence

This workflow-only change retains the actual Go TLS readiness metadata/log, Playwright JSON provenance/results and failure screenshots. The120 DTO cases remain distinct from21 actual paid API cases. Existing local partial failures remain preserved and do not establish full browser acceptance. No local runtime will be launched for this change. Exact implementation review and actual CI evidence remain pending.
