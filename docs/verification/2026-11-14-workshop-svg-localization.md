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
40×20 PNG/red-pixel probe. Final full ingestion suite evidence is pending.

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
- [ ] Complete final full ingestion checks and independent exact-head review.
- [ ] Update once to the integrated base after the coordinator's preceding
  merges and pass strict required CI at that exact head.
- [ ] Build/deploy a separately approved runtime image and perform authorized
  capture/reader/media acceptance; supplier test-use rights, the named Firebase
  tester, normal settled test order and exact scoped grant remain required.
