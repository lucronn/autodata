# Opaque Source-Derived Media Paths

**Goal:** Public article responses must use unique, opaque media paths so image
URLs do not reveal or let a reader infer a source provider's original artifact
path. Keep source URI and content provenance internal to AutoData.

**Architecture:** AutoData remains the public normalized-data API. During
article response projection, AutoData replaces every supported source-backed
image URL—including legacy `/v1/catalog/images?src=...` references—with a
fresh AES-256-GCM sealed opaque token at `/v1/catalog/images/{token}`. Tokens
use random nonces, are authenticated, and are only decryptable by the AutoData
API. The image endpoint validates the decrypted URL against the existing
provider allowlist before fetching. The old query route is rejected. The API
derives a stable encryption key from a dedicated configured key when present,
or a domain-separated HMAC of the existing high-entropy internal ingestion
token; startup without either secret must fail closed for opaque image serving
rather than use a weak default. Raw source metadata and original article
copies remain internal for review and provenance.

**Issue:** https://github.com/lucronn/autodata/issues/116

**Project:** https://github.com/users/lucronn/projects/8

**Plan:** `docs/superpowers/plans/2026-10-02-opaque-source-media-paths.md`

**Canonical contract:** `docs/architecture/opaque-source-media-paths.md`

## Decisions

- Scope public path obfuscation to source-derived media artifacts; do not
  remove source provenance from the private original/source-review data.
- Use per-response randomized authenticated encryption, not a plain URL hash,
  so paths are unique and cannot be guessed or decoded without the server
  secret.
- Preserve the existing host allowlist, image-only content type validation,
  response size cap, and timeout behavior.
- Never accept a caller-supplied origin or expose upstream error bodies or
  URLs in the public path.
- Reject legacy `?src=` URLs after AutoData projections mint opaque paths.
- Do not change AutoDBtwo's internal source URI headers; AutoData consumes
  them for provenance and they are not public consumer image URLs.

## Implementation tasks

1. Add an AES-GCM opaque media reference codec using a strong stable server
   key and random nonce; configure key derivation/validation for local and
   deployed AutoData API instances.
2. Rewrite all public article image references to unique opaque path tokens
   and serve only decrypted, provider-allowlisted image URLs from the new
   path route.
3. Disable the legacy source-bearing `?src=` route and ensure errors, logs,
   response headers, and OpenAPI examples do not disclose the original path.
4. Add tests for token uniqueness, round-trip, tamper rejection, source-origin
   rejection, legacy-path rejection, and public article response redaction.
5. Verify local configuration and representative article/image responses;
   confirm private source references remain available internally for
   provenance and review.

## Acceptance criteria

- Repeated projections of one source image produce distinct opaque paths that
  do not contain the provider host or source path.
- Only the configured AutoData API can decrypt paths; modified or malformed
  tokens fail closed.
- The media handler accepts only allowlisted HTTPS provider image URLs after
  decryption and retains existing response bounds.
- Public article JSON and image URLs expose no provider path; private source
  evidence remains unchanged.
- All Go and relevant Python tests pass, and the required planning gate passes
  before implementation.

**todo:** replace source-bearing public image URLs with randomized opaque media
paths.
