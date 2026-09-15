# Repair-guide artifact contract

**Goal:** Serve a self-contained HTML repair guide as the fastest, most portable consumer artifact while preserving the existing PDF download for compatibility. Correct provider vehicle labels at the source boundary so canonical identity is never replaced by provider prose.

**Plan:** `docs/superpowers/plans/2026-09-15-html-guide-and-silverado-label.md`

**Project:** https://github.com/users/lucronn/projects/8

**Issue:** https://github.com/lucronn/autodata/issues/96

## Decision

The persisted procedure and immutable revision remain the single source of guide content. The authorized service prepares source figures once, then renders either:

- HTML: a standalone document with inline CSS and every prepared figure embedded as a base64 `data:` URI. It is the preferred dashboard/download output and does not require a network connection after delivery.
- PDF: the existing revision-matched compatibility artifact, retained for established consumers.

Both artifacts are gated by the same complete-guide contract and carry the same revision ID, source watermark, warnings, and review label. The persisted guide retains internal evidence linkage for auditability; public artifact serialization exposes only permitted review/evidence metadata and never raw provider HTML or internal provenance IDs. HTML rendering never fetches a remote image and never invents missing content.

Vehicle applicability is derived from canonical year, make, model, drivetrain, and engine fields when a provider candidate has a malformed prose label. A candidate value such as `For A Chevrolet` is normalized to `Chevrolet` with an alias trail; the consumer heading for the supplied Silverado example is `1999 Chevrolet Silverado 1500 2WD 5.3L`.

## Concrete todo

- [x] Synchronize the Issue, Project item, plan, canonical docs, and machine-checked pre-implementation record at one checkpoint SHA.
- [x] Add failing HTML-artifact and Silverado-label tests.
- [x] Implement HTML rendering, worker caching, internal delivery, Go proxying, answer metadata, dashboard preference, and consumer verification.
- [x] Implement provider-label sanitization without changing valid detailed vehicle labels.
- [x] Run focused/full verification and record exact evidence here and in GitHub.

## Boundaries

No source data, credentials, or user-owned runtime artifacts are part of this delivery. The GitHub Project is a synchronized delivery index; this document and the linked implementation plan are the normative technical record. Verification evidence is added below after the final local test run.

## Local verification checkpoint

Implementation commit `d63ab7b` passed the applicable local checks:

- `426 passed, 3 skipped, 12 subtests passed` across the Python worker,
  consumer, and contract suites.
- `go test ./... -count=1` passed in `apps/api-go`.
- `node --check apps/api-go/dashboard/app.js` passed.
- `git diff --check` passed.

The live/local Silverado chat run and HTML/PDF parity check remain a post-restart
acceptance step; no live result is claimed by this checkpoint.
