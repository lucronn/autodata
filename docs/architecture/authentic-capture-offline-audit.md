# Authentic capture audit contract

Goal: Audit retained authentic captures offline with integrity, positional media binding, binary availability and explicit rights evidence while withholding external display acceptance.

Issue: https://github.com/lucronn/autodata/issues/401
Project: https://github.com/users/lucronn/projects/8

## Concrete todo

- [x] Implement metadata-only offline audit using existing connector envelope and article adapters; no network, runtime or persistence
- [x] Verify retained body/envelope hashes, exact per-position bindings including repeats, declared references and local asset bytes
- [x] Validate explicit content-hash-bound rights evidence references; unknown, incomplete or forged evidence blocks external display
- [x] Add owned regressions for repeated images, missing/forged bindings, hash mismatch, unavailable binaries, unknown rights and output redaction; run retained40 corpus and push reviewable evidence

The audit reads the retained capture layout and optional local rights/asset evidence. It emits only opaque hashes, numeric counts, boolean checks and fixed reason codes: no source bodies, URLs, refs, credentials or evidence text. It uses the existing SourceConnector envelope validation and bound article parser, never a live connector. Raw article bytes and envelope bytes remain immutable. Every repeated image position is counted separately and binds only through an exact decoded URL sidecar or explicit declared ref; no positional guessing. Local binary envelope/content integrity must be proven against a declared reference. Rights input must identify a locally retained, hashed evidence document and explicit provider/content hashes, audience, use, validity and reviewer; a record alone is evidence to review, never an automatic legal permission or external display release. Unknown rights fail closed.

Output external_display_allowed remains false: this offline audit cannot establish live ownership, independent technical review, authentication or legal approval. It reports technical readiness and rights-evidence completeness separately. CLI returns success for a completed truthful audit even when coverage is incomplete, and nonzero for malformed inputs/integrity failure. The40 retained articles have no media binaries/rights evidence; preserve this honest outcome.

No provider requests, Docker/runtime changes, database/S3 writes, model calls or public content exposure. Implement only this developer tool, owned tests and documentation. Test against the retained40 corpus without committing it.

## Command and input contract

Run from a checkout with the existing ingestion dependencies:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=workers/ingestion-python/src:packages/contracts/python python3 -m autodata_ingestion.capture_audit /private/capture-root
```

The command emits JSON to stdout; operators may save it in a private evidence directory. Exit0 means a truthful audit completed, including incomplete media or unknown rights. Exit2 means malformed input, integrity failure or adaptation failure. No output field grants display permission: `external_display_allowed` is always false, including when every local file and evidence reference checks out.

Required inputs are `selection-manifest.json`, `file-hashes.json`, and the selected folders' `metadata.json`, `source-envelope.json`, and `source-resource.bin`. The supplied hashes establish local consistency, not authenticated origin or entitlement. No Python from the capture directory is imported or executed. Reads refuse parent traversal, symlinks and non-regular/oversized files. JSON duplicate keys are rejected.

Optional `audit-assets.json` has one `resources` array. Each entry has exactly `provider`, `resource_ref`, `envelope_path`, `payload_path`, `envelope_sha256`, and `payload_sha256`. Paths are relative to the capture root. Each entry refers to the retained connector response envelope and original binary bytes; the existing envelope validator verifies provider, embedded bytes and hash. Duplicate provider/ref entries fail closed. Only declared image resources are used; no URLs are fetched. A local manifest association remains an assertion to review, not independently authenticated resource provenance.

Optional `audit-rights.json` has one `records` array. Each record has exactly these fields:

```json
{
  "provider": "bankone",
  "resource_sha256": ["<body SHA256>", "<available asset SHA256>"],
  "audience": "restricted_external_testers",
  "permitted_use": "display",
  "reviewer": "<private responsible reviewer reference>",
  "valid_until": "2027-01-01T00:00:00Z",
  "evidence": {"path": "rights/private-evidence.pdf", "sha256": "<evidence file SHA256>"}
}
```

A matching record must cover the article body and all available declared binary hashes, match provider/audience/use, name a reviewer, remain unexpired and reference nonempty local evidence bytes with the exact hash. The audit outputs evidence hashes only. `EVIDENCE_REFERENCED` means that local references check out; the reviewer identity, document meaning, supplier permission and legal validity remain unverified. An absent, invalid, wrong-scope or expired record cannot authorize display. Unknown binary identities or unbound positions remain media gaps irrespective of rights records.

## Meaning of coverage

Each adapter-detected image occurrence is a separate position, including repeats and images nested in tables. A repeated exact binding shares a retained binary while preserving each position. `missing_binaries` counts declared refs without a local asset entry, separately from unbound positions; it does not count remote404s. Position refs are hashed in output.

`local_capture_complete` means body/envelope consistency, successful adaptation, every detected position bound to a declared locally retained binary, and no missing declared binary. It does not establish decoded-image validity, image order beyond the existing adapter, render acceptance, source completeness, canonical review, DB/S3 persistence, current provider access or rights. Image-free articles can satisfy this limited local check. The audit deliberately does not rasterize SVG or invoke any subprocess.

## Verification at implementation761b9f17

Protected parent09524db; synchronized planning checkpointf657ee77 was pushed and machine preflight returned synchronized/errors[] before implementation. Prior planning-only391b8cb8 is superseded and absent from this branch ancestry.

- Owned audit suite:22 passed. Audit/bindings/connector group:88 passed,36 subtests passed/1.82s.
- Broader group also including source capture:229 passed,36 subtests passed;4 existing `test_svg_asset_derives_png_and_retains_exact_original` cases failed/119.55s. Host lacks pinnedCairoSVG2.9.1; the unchanged baseline renderer reportsSVG_RENDER_UNAVAILABLE. Existing capture/renderer/test files match09524db. No dependency install, runtime change or suppressed test.
- Retained40 corpus:40 body/envelope integrity checks and40 adaptations pass;118 adapter image positions,0bound/0binary;64 declared refs lack local binaries;24 articles have no local image/asset gaps;0 rights evidence references; external_display_allowed=false. These are local observations, not representative supplier coverage or tester acceptance.
- Private JSON report: `/home/corp/autodata-evidence/authentic-capture-audit-761b9f17-20261116.json`, SHA256 `2d314e26ceb49efcf6f771978716a68dd79d4dfab12401d84db2ac23ff3ab178`. No retained source content is committed.
- Tests cover repeated/nested positions, missing bindings and binaries, forged/cross-provider references, body/envelope/metadata/manifest/asset tampering, unknown/expired/wrong-scope/altered rights evidence, forbidden socket/subprocess construction, redaction, duplicate asset records and path/symlink rejection.

No supplier/model request, Docker/runtime mutation, DB/S3 write or external content exposure occurred. Independent branch review and normal CI/integration remain separate from this local verification.
