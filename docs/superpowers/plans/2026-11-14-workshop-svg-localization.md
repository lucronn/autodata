# Workshop SVG localization plan

Issue: https://github.com/lucronn/autodata/issues/419
Project: https://github.com/users/lucronn/projects/8
Canonical design: `docs/architecture/workshop-svg-localization.md`

Goal: Localize provider SVG illustrations as bounded PNG derivatives while preserving exact source provenance.

Fourteen distinct failed resources were classified with bounded provider reads: all SVG, all Bankone, 25,912–179,288 bytes. No identifiers or licensed bytes were retained in output. Existing runtime has Pillow/reportlab/poppler, but no SVG renderer. Use maintained CairoSVG exactly 2.9.1, verified against upstream release notes; it fixes the long-path denial-of-service vulnerability and includes the 2.9.0 recursive-use limit. Add libcairo2 to ingestion runtime/dev/integration images and the pinned Python dependency. No client-side SVG, raw SVG media route, new external fetch, or existing authorization change.

Rasterization accepts at most 2MB input, requires defused XML with DTD/entities/external resolution forbidden, rejects active content and any non-fragment link, imports and non-fragment CSS URLs before rendering. A fresh short-lived subprocess repeats validation, blocks socket construction and URL/file resource fetching, has CPU/address-space/open-file/output/time bounds, uses no source-derived paths, and emits only validated PNG. Dimensions preserve aspect ratio under a 4096px edge and 16M pixel cap; invalid dimensions fail closed. Only a bounded approved subset is supported; unsupported SVG stays unavailable with a stable reason. Process environment excludes service credentials. Runtime CPU/memory limits are Unix-specific; unsupported environments fail closed.

Capture stores exact SVG originals and separate content-addressed PNG derivatives. Original and derivative resources both enter immutable manifest/provenance, with source hash and rasterizer version linkage. Browser image projection uses only PNG bytes/key/hash; fingerprints include original and derivation metadata. Rendering/storage failure cannot mark an image available. Preserve stable failure codes for appended unpositioned figures as well as inline figures. Existing whole-capture deadlines and maximum four fetch tasks remain authoritative.

Concrete todo:
- Add pinned renderer and bounded isolated SVG rasterization with external-reference denial.
- Preserve exact originals and PNG derivation metadata and honest capture failure reasons.
- Test hostile and valid synthetic SVG capture and run required checks without production mutation.

Tests: valid geometry/dimensions/aspect and actual decoded PNG, external HTTP/file/data references, CSS imports/escaped resource URLs, DTD/entities, scripts/foreignObject, invalid XML, oversized input/output, runtime timeout/failure, exact original preservation and derivative lineage, unavailable failure reasons, nested/appended image projections, existing capture/lifecycle suites. Run full ingestion suite and strict required CI at exact candidate; no skipped real-data case counts as acceptance. No licensed bytes, credentials, production data mutation, refresh, grants, or external tester display. Supplier rights, actual Firebase/test settlement and retained browser evidence remain separate open dependencies.

Pre-implementation synchronized record: `docs/agents/records/2026-11-14-workshop-svg-localization.json`. Commit this checkpoint, synchronize Issue/Project and validate the exact pinned SHA before implementation.
