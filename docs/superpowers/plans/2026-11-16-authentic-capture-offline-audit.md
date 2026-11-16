# Offline authentic capture audit

Goal: Audit retained authentic captures offline with integrity, positional media binding, binary availability and explicit rights evidence while withholding external display acceptance.

Issue: https://github.com/lucronn/autodata/issues/401
Project: https://github.com/users/lucronn/projects/8

## Concrete todo

- [ ] Implement metadata-only offline audit using existing connector envelope and article adapters; no network, runtime or persistence
- [ ] Verify retained body/envelope hashes, exact per-position bindings including repeats, declared references and local asset bytes
- [ ] Validate explicit content-hash-bound rights evidence references; unknown, incomplete or forged evidence blocks external display
- [ ] Add owned regressions for repeated images, missing/forged bindings, hash mismatch, unavailable binaries, unknown rights and output redaction; run retained40 corpus and push reviewable evidence

The audit reads the retained capture layout and optional local rights/asset evidence. It emits only opaque hashes, numeric counts, boolean checks and fixed reason codes: no source bodies, URLs, refs, credentials or evidence text. It uses the existing SourceConnector envelope validation and bound article parser, never a live connector. Raw article bytes and envelope bytes remain immutable. Every repeated image position is counted separately and binds only through an exact decoded URL sidecar or explicit declared ref; no positional guessing. Local binary envelope/content integrity must be proven against a declared reference. Rights input must identify a locally retained, hashed evidence document and explicit provider/content hashes, audience, use, validity and reviewer; a record alone is evidence to review, never an automatic legal permission or external display release. Unknown rights fail closed.

Output external_display_allowed remains false: this offline audit cannot establish live ownership, independent technical review, authentication or legal approval. It reports technical readiness and rights-evidence completeness separately. CLI returns success for a completed truthful audit even when coverage is incomplete, and nonzero for malformed inputs/integrity failure. The40 retained articles have no media binaries/rights evidence; preserve this honest outcome.

No provider requests, Docker/runtime changes, database/S3 writes, model calls or public content exposure. Implement only this developer tool, owned tests and documentation. Test against the retained40 corpus without committing it.

Protected implementation parent: `09524db`. Planning-only checkpoint391b8cb8 on selector ancestry is superseded; this audit branch excludes unmerged selector helpers.
