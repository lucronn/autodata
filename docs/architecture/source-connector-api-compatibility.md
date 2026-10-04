# Source Connector API Compatibility

AutoData serves normalized, ingested data and owns its persistence and public
API. AutoDBone and AutoDBtwo are read-only source connectors behind AutoData's
ingestion adapters. Their independently versioned route contracts must be
reflected in AutoData's adapter paths and deployment configuration.

## AutoDBone

The current AutoDBone facade uses neutral catalog routes under
`/v1/api/catalog/{catalog}/...`. AutoData maps its existing source vocabulary
at the connector boundary:

| AutoData source name | AutoDBone catalog alias |
| --- | --- |
| `GeneralMotors` | `gm` |
| `Toyota` | `toyota` |
| `Motor` | `catalog` |

The connector exposes the shared year/make/model selector routes and catalog-
scoped vehicle, article, and resource routes. AutoData must not build legacy
`/v1/api/source/{provider}/...` paths against the new facade. Unknown source
names fail clearly rather than being mapped to an unrelated catalog.

AutoDBone normalizes article HTML and signs figure URLs under
`/v1/assets/reference/{reference}`. During ingestion, AutoData fetches these
references only from its configured AutoDBone origin, rejects redirects and
oversized/non-image responses, and stores image bytes in AutoData object
storage. It must not send these references to AutoDBtwo or retain their signed
URLs in normalized public records.

Local development and deployment use the AutoDBone origin
`https://autodbone-curtt.vercel.app` by default; deployments may override it
with `AUTODATA_AUTOAPI_BASE_URL`. This Vercel deployment is protected, so a
successful request made through the authenticated Vercel CLI proves the route
contract but does not prove that an AutoData runtime has upstream access. Do
not disable deployment protection or place bypass credentials in the
repository. Runtime authentication must be configured through an approved
deployment secret or an internal connector deployment before claiming live
AutoData-to-AutoDBone acceptance.

## AutoDBtwo

AutoData's Python adapters call the standalone AutoDBtwo service through
`AUTODATA_AUTODBTWO_BASE_URL`; only AutoDBtwo connects to the configured
AutoAPItwo upstream. The connector remains read-only and handles catalog,
article, binary asset, and image/resource transport. AutoData still owns
response interpretation, normalization, provenance, and database persistence.

The AutoDBtwo submodule revision is updated deliberately and tested against
the worker HTTP adapter. AutoData runtime configuration must not bypass that
service by issuing direct AutoAPItwo network requests.

## Verification and change control

Route and catalog-alias mappings have deterministic contract tests. Worker
tests verify safe handling of connector errors and unchanged source response
semantics. Runtime manifests are checked for the intended service URL and
startup dependency. Live connector tests are reported separately from local
unit/configuration results; an unavailable endpoint or required authentication
is a limitation, not a pass.

Implementation and acceptance evidence for the current compatibility work are
tracked in [Issue #115](https://github.com/lucronn/autodata/issues/115),
[Project #8](https://github.com/users/lucronn/projects/8), and the
[implementation plan](../superpowers/plans/2026-10-02-source-connector-api-compatibility.md).

## Unknown response-envelope handling

AutoData must distinguish an explicitly empty supported catalog response from an
unsupported or malformed AutoDBtwo response envelope. Unknown shapes fail as a
source error and are not cached as empty success. This follow-up is tracked in
[Issue #115](https://github.com/lucronn/autodata/issues/115) and
[Project #8](https://github.com/users/lucronn/projects/8), with plan
`docs/superpowers/plans/2026-10-03-autodb-two-response-shape.md`.

Todo:

- Document and parse supported list response shapes.
- Fail visibly for unknown/malformed envelopes while preserving explicit empty
  lists.
- Test failure and retry behavior, then verify PR #120 and descendants.
