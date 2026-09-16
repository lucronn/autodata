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

- [ ] Add failing renderer tests covering guide-level evidence repeated across
      multiple steps and repeated figure references.
- [ ] Remove guide-level evidence from per-step rendering while retaining
      step/image-specific evidence.
- [ ] Keep one deduplicated aggregate evidence section in the detailed guide.
- [ ] Run ingestion, guide-rendering, API, and contract tests; inspect a live
      generated guide for bounded evidence output.
- [ ] Synchronize the implementation SHA, Issue #103, Project #8, and CI
      evidence, then push the branch.

## Acceptance criteria

- Guide-level evidence is not repeated under every procedure step.
- The aggregate evidence section contains each identifier at most once.
- Step and figure provenance remains available in detailed output.
- Source-authored procedure text, ordering, images, warnings, and revision
  identity remain unchanged.
- No `TODO` or `TBD` remains in the implementation or canonical documents.
