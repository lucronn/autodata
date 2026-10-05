# Preserve AutoDBone relative graphic images through ingestion

Issue: https://github.com/lucronn/autodata/issues/112
Project: https://github.com/users/lucronn/projects/8
Canonical repository document: `docs/architecture/source-connector-api-compatibility.md`
Provider implementation repository: `https://github.com/lucronn/autodbone`

## Goal

Preserve AutoDBone's relative graphic URLs through its HTML normalization so
AutoData can fetch and store the actual provider image bytes. Keep article
detail hydration scoped to the requested procedure; an article-index lookup
must not materialize the entire vehicle's catalog.

## Verified behavior

- The live 1997 Toyota RAV4 oil-pump article has no image URL.
- The water-pump article contains two references to
  `api/source/MOTOR/graphic/16619615`; the provider's graphic route returns an
  image/gif response (46,716 bytes).
- AutoDBone's normal response strips that relative image source because the
  rewriter currently recognizes only `/m1/api/...` source paths. The raw
  article response and exact graphic route are available through the
  authenticated Vercel CLI.
- An AutoData article-scope refresh must persist only the selected article and
  its fetched media, not every list-only row returned by the index request.

## Concrete todo

- [ ] Recognize AutoDBone relative `/api/source/{source}/graphic/{id}` URLs and
  rewrite them to opaque same-origin asset references.
- [ ] Canonicalize source names case-insensitively (`MOTOR` to `Motor`) before
  minting references so the binary allowlist accepts the result.
- [ ] Add regression tests for relative and `/m1/api/` graphic paths, encoded
  identifiers, source casing, and unsafe external URL rejection.
- [ ] Restrict `scope=article` persistence to the one requested article while
  retaining its index and detail snapshots as provenance; test that no sibling
  list-only articles or duplicate links are written.
- [ ] Re-ingest only the two exact RAV4 source articles; prove oil has no
  provider image, water's image is localized to AutoData storage, provenance
  points to the canonical provider deployment, and no sibling catalog rows
  were created.

## Boundaries

- Do not disable Vercel Deployment Protection or store bypass credentials in
  the repository.
- Do not attach PDF-extracted figures to provider articles unless the source
  response identifies and returns those exact images.
- Do not alter unrelated vehicle articles, source rows, or historical
  provenance.

## Acceptance

- A normal AutoDBone article response retains a same-origin opaque image
  reference for each supported source graphic URL.
- The reference fetch returns image bytes and ingestion stores them locally;
  the public article does not expose the upstream URL.
- Article-scope ingestion writes only the requested detail record and its
  source evidence, leaving unrelated RAV4 article counts unchanged.
- The oil and water source image counts are reported separately and accurately.
