# Ordered-document publication gate

**Issue:** https://github.com/lucronn/autodata/issues/111
**Project:** https://github.com/users/lucronn/projects/8
**Candidate base:** `1ef8594`
**Canonical contract:** `docs/architecture/normalized-article-document.md`

## Goal

Prevent an ordered article document from being marked complete when retained content blocks lack traceable source evidence or the document fails structural validation.

## Decisions

- Every retained content block in a complete published document must have a non-empty evidence ID list resolving to the article's source snapshot. Unknown blocks may be retained for review, but the article remains incomplete until the block has evidence or is removed by an explicit reviewed decision.
- The completion flag must derive from validated ordered-document content and provenance, not only a stored status string. Existing incomplete rows remain readable with an explicit incomplete status; they are not silently promoted.
- Preserve source block order and original payload. Never synthesize evidence IDs for unsupported material.

## Concrete todo

- [ ] Add publication validation for ordered block structure and evidence references.
- [ ] Ensure content-complete labeling fails closed on missing block evidence or unknown retained content.
- [ ] Add regressions for table, step, image, callout, and unknown blocks, plus valid mixed documents.
- [ ] Verify the 2012 Ram axle article and diverse real articles at exact candidate SHA, including browser image rendering and duplicate list/detail identity.

## Boundary

Implementation owns only ordered-document validation and focused tests. Runtime/browser evidence is a separate required acceptance step, and fixture proof alone does not close Issue #111.
