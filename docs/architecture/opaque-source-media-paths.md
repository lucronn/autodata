# Opaque Source-Derived Media Paths

**Status:** planned for implementation under
[Issue #116](https://github.com/lucronn/autodata/issues/116) and
[Project #8](https://github.com/users/lucronn/projects/8).

AutoData's public article API must not expose source-provider artifact paths in
image URLs. Existing query-based proxy references such as
`/v1/catalog/images?src=https%3A...` encode the complete upstream URL in the
browser-visible request and therefore reveal the provider and artifact path.

## Contract

- AutoData remains the public API and system of record; normalized article
  content and private source provenance stay in AutoData.
- Public image URLs use `/v1/catalog/images/{opaque-token}`. Each projection
  mints a fresh token, so repeated projections of the same source image have
  distinct paths.
- The token contains an AES-256-GCM authenticated ciphertext of the source
  URL, protected by a stable AutoData-only key and a fresh random nonce. Tokens
  must not contain raw URL text or be plain hashes of source URLs.
- Resolve the key from a dedicated key setting when configured; otherwise
  derive it with domain-separated HMAC-SHA-256 from the existing
  `AUTODATA_INGESTION_INTERNAL_TOKEN`. Fail closed if neither stable secret is
  configured. All API replicas must use the same key material.
- The image handler decrypts the token, validates the HTTPS origin against
  the existing strict provider allowlist, and keeps the current timeout,
  image media-type, response-size, and redirect protections.
- Reject old `?src=` requests. Do not reflect decrypted paths in errors,
  headers, logs, or public API payloads.
- Keep source URLs and source hashes inside stored provenance/original
  records, where they remain available to authorized review and debugging.
- AutoDBtwo's internal source URI headers remain an internal worker contract;
  public AutoData image responses must not expose them.

## Verification

Tests must prove randomized token uniqueness, round-trip decryption, tamper
rejection, provider allowlisting after decryption, rejection of the legacy
query endpoint, and redaction from serialized public article responses. Run
the Go API tests and relevant Python image-normalization tests. Exercise a
representative local article response and image fetch, and verify that private
source provenance remains intact.

## Todo

- Implement the opaque image reference codec, key configuration, projection,
  and path-based image handler.
- Remove the source-bearing query route from the public API contract.
- Add security-focused tests and verify public/private representation
  boundaries.
