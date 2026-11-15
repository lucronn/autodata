# Bounded SVG localization verification

Issue: https://github.com/lucronn/autodata/issues/419
Project: https://github.com/users/lucronn/projects/8
Plan: [SVG localization](../superpowers/plans/2026-11-14-workshop-svg-localization.md)
Design: [reader media derivation](../architecture/workshop-svg-localization.md)

Planning checkpoint `103d798` and expanded embedded-raster checkpoint `3c531d3`
were synchronized with Issue/Project before their respective implementation.
Both pinned machine preflights returned `status: synchronized`, `errors: []`.

## Trigger and implementation

Fourteen distinct failed retained assets were classified by bounded connector
reads: all were Bankone SVGs, 25,912–179,288 bytes. The previous capture uploaded
the exact SVG but rejected it as `UNSUPPORTED_ASSET_MEDIA`. Appended image
references also lost their specific failure reason during ordered projection.

The new capture retains exact private SVG originals and separate PNG derivatives
with original-hash and rasterizer-version lineage in the immutable resource
manifest and observation provenance. Only the PNG key/hash/media type enters
the displayable image projection. Failures remain unavailable with fixed reasons,
including appended figures. No migration or authorization change is required.

CairoSVG is pinned to 2.9.1, checked against the upstream
[release](https://github.com/Kozea/CairoSVG/releases/tag/2.9.1) and
[documentation](https://cairosvg.org/documentation/). Ingestion runtime, dev, and
lifecycle images explicitly install libcairo2 and a basic font set. Upstream
security defaults complement application bounds and do not replace them.

The parent checks only byte type/nonempty/length and timeout before spawning.
All XML/CSS parsing and embedded image decode happens after child resource
limits. The child permits only validated embedded PNG/JPEG bytes from an exact
memory allowlist and internal fragments; network/file/other URI fetches, nested
SVG data, active content, internal DTD subsets and entities are rejected. Only
tightly recognized inert W3C SVG PUBLIC DOCTYPE declarations are stripped before
defused parsing and serialization; no DTD is fetched or passed to CairoSVG.

Bounds are 2 MB source input, 2 MB per decoded embedded resource, 8 million total
unique embedded pixels, 20,000 elements, nesting depth 64, a four-second wall
deadline, three CPU seconds, 512 MiB address space, 32 open files, and PNG output
at most 4096 pixels per edge / 16 million pixels / 12 MiB. The child receives no
service credentials in its environment. Its only outputs are PNG bytes or an
allowlisted fixed failure code; renderer errors/stderr are suppressed. Source
capture's existing whole-operation deadline still applies.

## Compatibility results, recorded separately

The initial conservative dry-run recovered **0/14** assets: four `INVALID_SVG`
and ten `SVG_EXTERNAL_REFERENCE`. Structural classification found four standard
DOCTYPE declarations, no entity declarations, four embedded JPEGs and internal
fragments; the other ten SVGs contained embedded PNGs. No remote/file/other hrefs
or stylesheet processing instructions were observed. That failed first result
prompted the synchronized amendment; it must not be described as recovery.

After bounded embedded-raster support and inert DOCTYPE removal, the corrected
memory-only dry-run converted **14/14** to decodable PNGs with zero failures.
The final image repeated **14/14** after the review correction that moved all
input parsing/decoding out of the parent. Widths were 480–576 pixels and heights
360–550 pixels. The final source-built image was
`sha256:b8c023c18741c8630d356740538e05e30390f8ed00d0cf254480b38274989849`.

These runs used a fresh read-only container with no capabilities, bounded
memory/CPU/processes, and existing private connector connectivity. Database
transactions were read-only; there were no DB/S3 writes or production service,
rights, grant, or payment changes. Asset references, original bytes and PNGs
remained in memory and were not output or persisted. Only aggregate receipts
were retained privately. No licensed content was displayed to external testers.
This establishes internal conversion compatibility, not semantic visual review,
an authenticated article/media browser read, or deployed recovery.

## Checks and release boundary

Focused synthetic renderer/capture checks passed 43 tests, including real PNG
pixels/aspect ratio, PNG/JPEG embedding, original preservation and lineage,
external/file/CSS/active-content refusal, inert versus internal/unrecognized
DOCTYPE handling, MIME/base64/pixel limits, runtime allowlist refusal, timeout,
fixed failure codes, and a regression forbidding parent source parsing.
The actual built image also passed a network-disabled, read-only synthetic
40×20 PNG/red-pixel probe. At implementation commit `7a79f76`, the full ingestion suite passed 1,240 tests with 475 opt-in integration skips and 196 passing subtests. The separately enabled new PostgreSQL/S3 integration passed with zero skips. The implementation source did not change when adding that integration case.

The added lifecycle integration uses a fresh synthetic PostgreSQL database and unique real fixture-S3 bucket. It captures an embedded-raster SVG, calls `store_captured_source`, reads the persisted resource manifest/observation/snapshots and `catalog_article_current`, verifies original/derivative lineage and the available PNG key/MIME, and reads back both exact original bytes and decoded red PNG pixels. The current image/document projection contains no original SVG key or SVG MIME/markup. Fixture cleanup removes only its database/bucket. This tests persistence and projection; it does not replace authenticated HTTP/browser media acceptance.

Runtime activation remains **blocked**. The existing private ingestion image
does not contain CairoSVG/libcairo; a read-only source mount or the separate
mount-only rollout cannot install dependencies. A separate exact-source image
build and reviewed deployment are required after source integration. Source
merge alone does not activate this behavior, and old retained revisions are not
rewritten by merging it. Any authorized recapture must preserve immutable source
history and then pass normal current article/source/media authority.

Concrete todo:

- [x] Synchronize both planning checkpoints before their implementation.
- [x] Implement bounded rasterization, exact-original/PNG lineage and honest failures.
- [x] Pass focused synthetic checks, build the actual image, and repeat the
  private memory-only retained-asset compatibility probe.
- [x] Complete final full ingestion checks and isolated PostgreSQL/S3 persistence/projection integration.
- [ ] Obtain independent exact-head review.
- [ ] Update once to the integrated base after the coordinator's preceding
  merges and pass strict required CI at that exact head.
- [ ] Build/deploy a separately approved runtime image and perform authorized
  capture/reader/media acceptance; supplier test-use rights, the named Firebase
  tester, normal settled test order and exact scoped grant remain required.

## Final protected-base integration

Protected master `76fb21e8f7c080e93f6d38de93a2e1a22cd11f39`, tree `c4b63d3635e7cc5b084f0d9df6154334e6dc36a3`, contains merged #415, #421 and #417. Documentation-only checkpoint `5cacd10` was committed directly on that base after Issue #419/Project #8 synchronization; machine preflight returned `status:synchronized`, `errors:[]` before feature integration. Integrated source checkpoint `b5e12204ea58cf6c5ad49a884d9d928771326868`, tree `594cfdcb4b936d7a988ff33a68e46b0dae189476`, has only three expected planning-document add/add resolutions and no implementation conflicts. SVG renderer/capture/tests and all three image dependency definitions are unchanged from reviewed `a021fcc`.

On the preceding #421 integrated head, full synthetic SVG/capture/read_only checks passed 189 tests with three opt-in PostgreSQL skips and 36 subtests. Earlier protected #417 integration full ingestion verification passed 1,247 tests with 479 opt-in integration skips and 232 subtests. #415 changes only Go authentication and its documentation; no ingestion/image source input changed.

The production-shaped image `sha256:3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7` was built at #421 integration. At final #415 integration, all 101 production image-context input files were hash-recorded and confirmed unchanged; loaded renderer/capture/commerce/HTTP source hashes match the final checkout. Reusing that exact image, a fresh network-none, read-only, capability-free synthetic probe passed CairoSVG 2.9.1, PNG 40×20/red pixels and read_only checkout refusal before database I/O. No additional image build was needed.

The enabled fresh synthetic PostgreSQL/S3 persistence/current-projection case and read_only commerce module were rerun on the final integrated source: **11 passed, zero skips, 36 subtests** in 4.62 seconds. This uses the existing isolated lifecycle image and current source mounted read-only, creates/removes only its unique fixture database/bucket, and retains shared services. Private aggregate receipts and JUnit remain under `/home/corp/autodata-evidence/svg-localization-20261114/`. Required strict CI and independent review must apply to the final pushed PR head; the PR remains draft pending coordinator review.

No serving mutation, provider request or licensed recapture occurred during integration. Current serving private runtime remains source92d81a1/image5c8e79b without these renderer dependencies. Separate runtime image/deployment authorization and supplier-rights/authenticated-reader acceptance remain required.
