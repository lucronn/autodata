# Restore ingestion CI dependency setup

Issue: https://github.com/lucronn/autodata/issues/186  
Project: https://github.com/users/lucronn/projects/8

## Goal and reproduced cause

Install the ingestion worker's declared dependencies before its CI tests run.
Runs [41617122268](https://github.com/lucronn/autodata/actions/runs/41617122268)
and [41617440987](https://github.com/lucronn/autodata/actions/runs/41617440987)
fail during collection because the workflow installs only pytest while the new
real-database tests import psycopg. Source capture tests also exercise real SDK
exception types. The isolated full suite passes because its image installs the
worker's pyproject dependencies before testing.

A fresh Python 3.12 container reproduced collection exit 2 with pytest alone.
Installing the existing `project.dependencies` from the ingestion pyproject,
without any source changes, produced 594 passing tests, 50 expected isolated-DB
skips, and 25 passing subtests. Logs and JUnit are retained under
`/tmp/autodata-ci-dependency-repro`. The separate required PostgreSQL fixture run
passed all 644 tests and 25 subtests; the ordinary unit step cannot certify the
50 skipped database cases.

## Concrete todo

- [ ] Synchronize Issue/Project and this canonical plan/task, commit a fresh
  checkpoint, and pass the exact-base planning gate before edits.
- [ ] Change only the ingestion worker test step in
  `.github/workflows/autonomous-verification.yml` to install the existing
  `project.dependencies` from `workers/ingestion-python/pyproject.toml` using
  Python's `tomllib` and a structured subprocess argv. Retain pytest installation,
  all test commands, required gates and workflow triggers. Do not skip new tests,
  introduce optional-import substitutes, or duplicate dependency version ranges.
- [ ] Validate YAML and inspect the exact one-file diff. Replay the step in a
  clean Python 3.12 environment with the test-required dependencies installed.
  The already retained pytest-only failure is the regression baseline; no
  implementation-mirroring test is required for this workflow-only repair.
- [ ] Obtain independent exact-SHA review of setup, command execution, security
  boundaries and unchanged required checks. Coordinator integrates and confirms
  the actual GitHub run; any later failure remains a failing check to resolve.

## Protected workflow handling

This is an explicit direct-coordinator protected-change assignment, independently
reviewed before dispatch and at the resulting SHA. It does not run through or
relax the normal runner's protected-path refusal. The only implementation path
is `.github/workflows/autonomous-verification.yml`. Policy, registry, test cases,
application code, migrations and release gates remain unchanged. All eight
independent gates still apply before merge/release. No production deployment,
new secrets, external application writes or live source/model calls are allowed.
Implementation/review use Sol 6.1, medium reasoning, Fast/priority, no fallback.

## Verified setup and later CI failure

Exact candidate/integration `9e07beb286f6f67e5a5854c46ebc01cf82318a46`
passed independent review and a clean Python3.12 exact-step replay: 594 tests
and 25 subtests passed, with 50 separately covered database cases skipped.
Actual [run41618670467](https://github.com/lucronn/autodata/actions/runs/41618670467)
passed ingestion and failed later in live Compose smoke while replaying
migration037. The dependency repair is verified within its scope; this run is
failed overall. The migration defect requires its own reviewed checkpoint.
