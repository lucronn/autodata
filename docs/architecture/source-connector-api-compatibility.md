# Source Connector API compatibility

AutoData consumes Bankone and Banktwo through the same versioned, read-only
contract. AutoData remains responsible for its product API, canonical vehicle
identity, source capture, normalization, provenance, review, and persistence.
Provider-specific upstream paths, schemas, and credentials belong inside the
corresponding bank service.

The canonical contract is
[`packages/contracts/source-connector/v1/openapi.yaml`](../../packages/contracts/source-connector/v1/openapi.yaml),
with shared contract metadata in
[`packages/contracts/contract.json`](../../packages/contracts/contract.json)
and conformance fixtures under `packages/contracts/source-connector/v1/fixtures/`.
The AutoData HTTP adapter is
`workers/ingestion-python/src/autodata_ingestion/source_connector_client.py`.
It validates envelopes, bounds response sizes, rejects redirects, and converts
resource bytes into AutoData `SourceResource` records without interpreting
provider-specific payload formats.

## Operations and routes

Both bank APIs implement the following contract operations:

| Operation | Route | Purpose |
| --- | --- | --- |
| Capabilities | `GET /v1/capabilities` | Declare supported source operations |
| Catalog | `GET /v1/catalog/{scope}` | Read bounded `years`, `makes`, `models`, or `configurations` pages |
| Vehicle resolution | `POST /v1/vehicle-resolutions` | Return zero or more source candidates for a selector |
| Article list | `GET /v1/vehicles/{opaqueRef}/articles` | List a source vehicle's articles |
| Article search | `POST /v1/vehicles/{opaqueRef}/article-search` | Search articles within a source vehicle |
| Resource read | `GET /v1/resources/{opaqueRef}` | Retrieve article, labor, text, or binary source content |
| Liveness | `GET /healthz` | Report service liveness |
| Readiness | `GET /readyz` | Report whether the service can accept requests |

The contract defines paginated results with `complete` and, when incomplete,
`next_cursor`. Catalog items, vehicle candidates, articles, and resources use
opaque references. AutoData stores and returns a reference only to the bank
that issued it; it must not treat a reference as a URL or construct a
provider-specific upstream route from it. Vehicle resolution may return
multiple candidates. Ambiguity remains explicit for caller selection.

Responses carry a request ID, wire provider, source revision, fetched time, and
where applicable a source locator. Resource reads provide original text/bytes,
media type, and SHA-256. AutoData verifies the declared content hash and stores
the resource and its source metadata in its own snapshot/evidence pipeline.
Opaque asset references are resolved by their originating bank. Signed source
URLs, cookies, credentials, and raw authentication material are not part of
the public AutoData record.

Stable error codes include `INVALID_INPUT`, `NOT_FOUND`, `AMBIGUOUS`,
`UNAUTHORIZED`, `RATE_LIMITED`, `UPSTREAM_UNAVAILABLE`, and
`INVALID_UPSTREAM_RESPONSE`. The adapter maps transport and contract failures
to these sanitized categories; source-specific error bodies are not forwarded
as product responses.

## Naming and configuration

The source API uses wire provider slugs `bankone` and `banktwo`. AutoData maps
those slugs to existing persisted lineage values `autoapi` and `autoapitwo` in
`source_connector_client.py` and `packages/contracts/contract.json`. Historical
database keys and migration names retain their original spellings; this is
compatibility behavior, not evidence that the current services are named
AutoDBone or AutoDBtwo.

AutoData reads `BANKONE_BASE_URL` and `BANKTWO_BASE_URL` independently. Local
Compose defaults and Kubernetes config point to `https://bankone.cars.tk` and
`https://banktwo.cars.tk`; `.env.example` shows the same origins. Optional
`BANKONE_API_TOKEN` and `BANKTWO_API_TOKEN` values are read from the runtime
environment. No example token is checked in. A configured URL or token does
not establish that the domain, authentication policy, or remote API is live.

The contract's corresponding source implementations are in the independent
[`lucronn/bankone`](https://github.com/lucronn/bankone) and
[`lucronn/banktwo`](https://github.com/lucronn/banktwo) repositories. They do
not live under an AutoDBone/AutoDBtwo path in this repository. AutoData no longer
uses a Git submodule or builds either bank as a Compose service. Live DNS,
Vercel ownership, TLS, auth, deployment, canary, and release verification remain
pending; contract and local configuration inspection do not prove live service
compatibility.

## AutoData persistence boundary

Source snapshots, hashes, normalization, evidence, and stored assets remain in
AutoData. Catalog synchronization uses the generic client and retains source
completeness and cursors. Article fetch jobs are persisted through
`workers/ingestion-python/src/autodata_ingestion/source_job_persistence.py` in
the provider-neutral `source_fetch_jobs` table. Migration
`db/migrations/036_source_fetch_jobs.sql` imports the legacy Bankone job rows
additively and checks that UUIDs, status, retry count, idempotency keys, and
snapshot links survive. The historical tables remain available during
compatibility/rollback; no bank service receives access to them.

For ownership and local-versus-live status, see
[Independent Bankone and Banktwo connectors](independent-bank-connectors.md)
and [Bankone/Banktwo domain routing](bankone-banktwo-domain-routing.md).
