# Workshop SVG localization plan

Issue: https://github.com/lucronn/autodata/issues/419
Project: https://github.com/users/lucronn/projects/8
Canonical design: `docs/architecture/workshop-svg-localization.md`

Goal: Localize provider SVG illustrations as bounded PNG derivatives while preserving exact source provenance.

Fourteen distinct failed resources were classified with bounded provider reads: all SVG, all Bankone, 25,912–179,288 bytes. No identifiers or licensed bytes were retained in output. Existing runtime has Pillow/reportlab/poppler, but no SVG renderer. Use maintained CairoSVG exactly 2.9.1, verified against upstream release notes; it fixes the long-path denial-of-service vulnerability and includes the 2.9.0 recursive-use limit. Add libcairo2 to ingestion runtime/dev/integration images and the pinned Python dependency. No client-side SVG, raw SVG media route, new external fetch, or existing authorization change.

Rasterization accepts at most 2MB input, requires defused XML with DTD/entities/external resolution forbidden, rejects active content, external links, imports and non-fragment CSS URLs before rendering; only embedded PNG/JPEG image data is allowed after strict base64, MIME/format, byte, pixel and decode checks. A fresh short-lived subprocess repeats validation, blocks socket construction and URL/file resource fetching, has CPU/address-space/open-file/output/time bounds, uses no source-derived paths, and emits only validated PNG. Dimensions preserve aspect ratio under a 4096px edge and 16M pixel cap; invalid dimensions fail closed. Only a bounded approved subset is supported; unsupported SVG stays unavailable with a stable reason. Process environment excludes service credentials. Runtime CPU/memory limits are Unix-specific; unsupported environments fail closed.

Capture stores exact SVG originals and separate content-addressed PNG derivatives. Original and derivative resources both enter immutable manifest/provenance, with source hash and rasterizer version linkage. Browser image projection uses only PNG bytes/key/hash; fingerprints include original and derivation metadata. Rendering/storage failure cannot mark an image available. Preserve stable failure codes for appended unpositioned figures as well as inline figures. Existing whole-capture deadlines and maximum four fetch tasks remain authoritative.

Concrete todo:
- Add pinned renderer and bounded isolated SVG rasterization with external-reference denial.
- Preserve exact originals and PNG derivation metadata and honest capture failure reasons.
- Test hostile and valid synthetic SVG capture and run required checks without production mutation.

Tests: valid geometry/dimensions/aspect and actual decoded PNG, external HTTP/file/data references, CSS imports/escaped resource URLs, DTD/entities, scripts/foreignObject, invalid XML, oversized input/output, runtime timeout/failure, exact original preservation and derivative lineage, unavailable failure reasons, nested/appended image projections, existing capture/lifecycle suites. Run full ingestion suite and strict required CI at exact candidate; no skipped real-data case counts as acceptance. No licensed bytes, credentials, production data mutation, refresh, grants, or external tester display. Supplier rights, actual Firebase/test settlement and retained browser evidence remain separate open dependencies.

Pre-implementation synchronized record: `docs/agents/records/2026-11-14-workshop-svg-localization.json`. Commit this checkpoint, synchronize Issue/Project and validate the exact pinned SHA before implementation.

## Embedded-raster and inert-DOCTYPE amendment

The first memory-only live dry-run recovered 0/14: four INVALID_SVG and ten SVG_EXTERNAL_REFERENCE. Structural metadata classification found ten embedded PNG images; the other four contain external SVG DOCTYPE declarations without entity declarations and embedded JPEGs plus internal fragments. No HTTP/file/other hrefs or stylesheet processing instructions were observed. Keep the initial failed result separate from corrected acceptance.

Before expanded behavior, synchronize and pin this amendment. Strip only tightly recognized standard W3C SVG 1.0/1.1 PUBLIC DOCTYPE declarations with recognized W3C DTD URLs and no internal subset, then require defused parsing with DTD/entities/external resolution forbidden and serialize the validated tree before rendering. No DTD is fetched or passed to CairoSVG. Preserve exact original bytes separately. Embedded PNG/JPEG data must be strict base64 (ASCII whitespace may be removed), at most 2MB decoded per resource, at most 8M pixels in total, actual format must match declared MIME, and full Pillow decode must succeed. Canonical data URLs map to these validated bytes in a per-render memory dictionary; the runtime fetcher accepts dictionary members only and performs no filesystem/network I/O. All other URI schemes, unrecognized DTDs/internal subsets/entities and nested SVG/other data media stay denied. The parent checks only byte type/nonempty/input length and timeout before spawning; XML/CSS parsing and full embedded decode happen solely inside the resource-bounded child. Add tests for inert DOCTYPE removal, continued entity/internal-subset denial, embedded PNG/JPEG success, false MIME, corrupt base64/image, pixel limits and runtime allowlist denial. Repeat bounded in-memory dry-run and record initial and corrected aggregate outcomes separately before proposing rollout.

Verification extension: run one opt-in lifecycle fixture with real isolated PostgreSQL/S3 to prove original/derivative manifests and observation lineage survive `store_captured_source` and `catalog_article_current` exposes only an available PNG reference. Use a fresh synthetic database/bucket only; retain shared fixture services. A source mount alone does not install CairoSVG/libcairo/fonts, so a separately built reviewed image and authorized runtime acceptance remain required after source merge.

## Protected-base integration checkpoint

Coordinator-authorized protected master: `92d81a1afbcf9e025d017b9b30f6dd4bb54f3e8a`, tree `0e4038a6bd506fd1349caa0bfa320813106ce5ad`, after protected merge of #417. Create this documentation-only checkpoint directly on that exact master, synchronize Issue #419/Project #8 and run the pinned machine preflight before integrating it into the reviewed SVG feature branch. Existing reviewed SVG implementation is `a021fcc50ed29b7ca61772f383f7c221ad2d08c5`; preserve its implementation files byte-for-byte while bringing in the current protected base.

Integration todo:
- Integrate exact protected master through this synchronized checkpoint while preserving reviewed SVG implementation.
- Run focused synthetic actual-image and fresh PostgreSQL/S3 lifecycle persistence checks after integration; run appropriate current-base suites.
- Push the integrated exact head and pass strict required CI; keep PR #422 draft for coordinator review and runtime image decision.

Hold all merges, serving changes, licensed/provider recapture and additional cleanup without concrete space need. Prior private 14/14 conversion evidence remains historical compatibility evidence; do not repeat provider reads as part of current-base verification. Source merge remains separate from image deployment, rights, grants and real authenticated browser acceptance.

## Protected #421 integration checkpoint

Protected master `5b3e19d3b34208773a77b4b9cfccd3085726cabe`, tree `92da3c0238725728e43a2bbd4df7a0ec29d02de6`, contains merged #421 after #417. This docs-only checkpoint is created directly on that exact base; synchronize Issue #419/Project #8 and pass pinned preflight before feature integration. Preserve reviewed SVG implementation from `a021fcc50ed29b7ca61772f383f7c221ad2d08c5`.

Current integration todo:
- Integrate this exact protected #421 base through the synchronized checkpoint; report conflicts and branch checkpoint.
- Run focused actual-image synthetic SVG and enabled isolated PostgreSQL/S3 lifecycle checks without provider calls or serving writes.
- Hold final review-head push and strict CI until coordinator supplies #415 protected merge; then synchronize the final current-base gate and verify once. Keep #422 draft and hold all merges/runtime activation/licensed recapture.
