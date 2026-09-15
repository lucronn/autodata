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

- [ ] Add the exact 2-door 4WD RAV4 case to the consumer review case file.
- [ ] Run the case through the live dev API with bounded polling and report-only
  issue behavior.
- [ ] Verify applicability, four requested components, removal and installation
  phases, minimum figures, required torque/check depth, consumer-copy safety,
  and PDF revision parity.
- [ ] Record the report path and hashes in the canonical review documentation
  and synchronized tracking record.
- [ ] Keep human source-evidence review and uncached AutoAPI hydration as
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
