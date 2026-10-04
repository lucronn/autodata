# Opaque Source-Derived Media Paths

**Status:** implementation in progress under
[Issue #116](https://github.com/lucronn/autodata/issues/116) and
[Project #8](https://github.com/users/lucronn/projects/8).

AutoData's public article API must not expose source-provider artifact paths or
internal object-storage keys in image URLs. Images are fetched and validated
during ingestion, stored in AutoData-controlled object storage, and served from
that local copy. Rendering must never fetch from a source provider. See the
active implementation plan at
`docs/superpowers/plans/2026-10-04-localized-opaque-catalog-images.md`.

## Contract

- AutoData remains the public API and system of record; normalized article
  content and private source provenance stay in AutoData.
- Public image URLs use `/v1/catalog/images/{opaque-token}`. Each projection
  mints a fresh token, so repeated projections of the same source image have
  distinct paths.
- The token contains an AES-256-GCM authenticated ciphertext of a validated
  local object key, protected by a stable AutoData-only key and a fresh random
  nonce. It must never encode an upstream URL. Tokens must not contain raw
  object-key text or be plain hashes.
- Resolve the key from a dedicated key setting when configured; otherwise
  derive it with domain-separated HMAC-SHA-256 from the existing
  `AUTODATA_INGESTION_INTERNAL_TOKEN`. Fail closed if neither stable secret is
  configured. All API replicas must use the same key material.
- The image handler decrypts the token, validates the object-key namespace,
  reads only from configured AutoData object storage, and enforces image
  media-type and response-size limits. It makes no provider network request.
- Reject old `?src=` requests. Do not reflect decrypted paths in errors,
  headers, logs, or public API payloads.
- Keep source URLs and source hashes inside stored provenance/original
  records, where they remain available to authorized review and debugging.
- Keep object keys server-side only. Public JSON and OpenAPI expose neither
  object keys nor source URLs. If an image is unavailable locally, omit its
  display URL and preserve an explicit unavailable state.
- AutoDBtwo's internal source URI headers remain an internal worker contract;
  public AutoData image responses must not expose them.

## Verification

Tests must prove randomized token uniqueness, round-trip decryption, tamper
rejection, local object namespace validation, zero provider requests during
image reads, rejection of the legacy query endpoint, and redaction from
serialized public article responses. Run the Go API tests and relevant Python
image-normalization tests. Exercise a representative local article response
and image fetch, and verify that private source provenance remains intact.

## Todo

- Implement the opaque local-object reference codec, key configuration,
  projection, and object-store-backed image handler.
- Remove the source-bearing query route from the public API contract.
- Add security-focused tests and verify public/private representation
  boundaries.

## Public image representation follow-up

Public `CatalogImage` responses must never serialize the internal object-storage
key. Keep it available to server-side storage code only; clients use the
opaque `url` field. This follow-up is tracked in
[Issue #116](https://github.com/lucronn/autodata/issues/116) and
[Project #8](https://github.com/users/lucronn/projects/8), with plan
`docs/superpowers/plans/2026-10-03-public-image-storage-key.md`.

Todo:

- Exclude `storage_key` from public JSON serialization and OpenAPI.
- Test article responses with a populated internal key.
- Pass Go tests/vet, developer contract tests, and hosted verification on PR
  #118 and descendants.

## Local-only serving follow-up

Issues #112 and #116 share the active plan
`docs/superpowers/plans/2026-10-04-localized-opaque-catalog-images.md`.
The former provider-URL proxy behavior is superseded: tokens resolve only to
objects already stored by ingestion, including images rendered in stored-source
review. A display request never contacts a provider.

The current implementation retains persisted `storage_key` values internally,
emits tokens only for validated `procedure-images/<sha256>` keys, and reads
those objects from the configured MinIO/S3 bucket. The prior source-URL proxy
has been removed. Stored-source HTML currently omits images because the stored
snapshot does not yet carry a verified source-URL-to-local-object mapping.
OpenAPI JSON/YAML alignment and live cold/warm object-store verification remain
release follow-ups. Local verification: Go API tests and vet pass; 42 focused
Python image/rewrite tests pass; Compose config validation passes with
throwaway required-value placeholders.
