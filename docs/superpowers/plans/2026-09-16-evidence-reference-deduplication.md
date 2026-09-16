# Evidence reference deduplication for generated guides

**Issue:** https://github.com/lucronn/autodata/issues/103

**Project:** https://github.com/users/lucronn/projects/8

## Goal

Keep generated procedure artifacts readable while preserving complete,
auditable provenance for every source-backed instruction and figure.

## Root cause

The procedure composer aggregates evidence from every source article into the
guide-level `evidence_ids` collection. The HTML renderer then unions that
guide-wide collection into every step before rendering it, and renders the
same collection again at the end of the document. A large source bundle is
therefore multiplied by the number of steps.

## Decisions

- A step displays only its own evidence IDs plus evidence IDs attached to its
  figures.
- The guide-wide evidence list is deduplicated and rendered once in the
  detailed artifact.
- Stable evidence identifiers, source locators, source URLs, and audit records
  remain unchanged; this is a presentation-scope correction.
- The default dashboard summary remains consumer-friendly; raw evidence stays
  in the detailed artifact and structured response.
- Evidence order remains deterministic for stable output and review diffs.

## Concrete todo

- [x] Add failing renderer tests covering guide-level evidence repeated across
      multiple steps and repeated figure references.
- [x] Remove guide-level evidence from per-step rendering while retaining
      step/image-specific evidence.
- [x] Keep one deduplicated aggregate evidence section in the detailed guide.
- [x] Run ingestion, guide-rendering, API, and contract tests; inspect a live
      generated guide for bounded evidence output.
- [x] Synchronize the implementation SHA, Issue #103, Project #8, and CI
      evidence, then push the branch.

## Verification

The focused renderer regression test passed, followed by the full local suites:

- ingestion: `406 passed, 3 skipped, 12 subtests passed`
- enrichment: `46 passed, 16 subtests passed`
- developer adapters: `77 passed, 2 subtests passed`
- contracts: `14 passed`
- autonomy preflight: `7 passed`

After rebuilding the local Compose `ingestion-http` service, an authenticated
HTML artifact request returned HTTP 200 and rendered 99 step evidence blocks
plus one aggregate list containing 1,104 unique references with zero aggregate
duplicates. The dashboard loaded successfully at `http://127.0.0.1:8080/dashboard/`;
the existing browser blob remained subject to the in-app browser's cross-tab
security policy. The user-owned `output/`, `sample data/`, and `tmp/`
directories were not staged.

## Acceptance criteria

- Guide-level evidence is not repeated under every procedure step.
- The aggregate evidence section contains each identifier at most once.
- Step and figure provenance remains available in detailed output.
- Source-authored procedure text, ordering, images, warnings, and revision
  identity remain unchanged.
- No `TODO` or `TBD` remains in the implementation or canonical documents.
