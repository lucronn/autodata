# RAV4 4WD consumer-matrix extension plan

**Goal:** Add the exact 1997 Toyota RAV4 2-door 4WD multi-component request to
the reproducible consumer review matrix and retain live evidence for its
vehicle match, complete removal/installation procedure, illustrations, and
revision-matched PDF.

**Tracking:** [Issue #85](https://github.com/lucronn/autodata/issues/85) and
[Project #8](https://github.com/users/lucronn/projects/8)

**Canonical documentation:**
`docs/architecture/consumer-review-agent.md` and
`docs/verification/consumer-review-runbook.md`.

**Todo:**

- [x] Add the exact 2-door 4WD RAV4 case to the consumer review case file.
- [x] Run the case through the live dev API with bounded polling and report-only
  issue behavior.
- [x] Verify applicability, four requested components, removal and installation
  phases, minimum figures, required torque/check depth, consumer-copy safety,
  and PDF revision parity.
- [x] Record the report path and hashes in the canonical review documentation
  and synchronized tracking record.
- [x] Keep human source-evidence review and uncached AutoAPI hydration as
  explicit follow-ups; automated readiness is not technician approval.

## Scope and boundaries

This is a test-matrix extension only. It does not change provider credentials,
source payloads, review state, production deployment, or GitHub push state.
Reports remain outside the tracked source tree under the approved local `tmp/`
artifact directory. The existing 2WD RAV4, Camry, Forester, and Civic cases
remain in the matrix.

## Verification contract

The case must pass against a running non-production Compose stack. A missing
exact vehicle match, transport failure, incomplete guide, invalid figure/PDF,
or timeout is a blocked release finding. The report must contain no provider
credentials, raw source content, or internal provenance fields in its consumer
projection.

## Completed evidence

The case passed at implementation `1c4d69c154e3346caa398b0ae7e9e43a511e3247`.
The report is
`tmp/consumer-review-live/rav4-4wd-formal-v2/consumer-review-f6156af1dbaeea0df7c055f3.json`
with SHA-256
`746224da1c5c251ca92f95348ec4ed2fae2485352bf17dca3e20161ed8f7404d`.
The response matched provider vehicle `41216`, passed all six dimensions,
returned 131 steps and 89 figures, and returned a revision-matched PDF with
SHA-256 `754407d8d5abda5f81865bf5136f6d603e0c4d07ee24d3af2d951e67fd8a3c32`.
