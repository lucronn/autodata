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


## Authentic Banktwo HAL resources

Goal: Accept authentic Banktwo application/hal+json article resources through the existing bound JSON/HTML adapter without losing source content, media references or provenance.

Issue: https://github.com/lucronn/autodata/issues/317; related #300; parent #186; Project https://github.com/users/lucronn/projects/8. Plan: `docs/superpowers/plans/2026-11-05-banktwo-hal-source-adaptation.md`; record: `docs/agents/records/2026-11-05-banktwo-hal-source-adaptation.json`.

Observed private capture: 20/20 authentic Banktwo resources have exact application/hal+json media and currently reject as unsupported article media. The observed body is `_embedded.data.article.content` HTML. Route only this exact media through the existing bound nested JSON/HTML adapter, preserving original bytes, hashes, provider scope, applicability, ordered tables/media and evidence. Reject malformed HAL; preserve existing media behavior. Only source_adapters.py and test_source_article_capture.py may change. Private corpus evidence paths/hashes and limitations are in the plan. This is an ingestion compatibility repair, not accepted rewrite coverage or release readiness; no live provider/model calls, activation or deployment.

Concrete todo:
- [ ] Add red regressions for HAL nested article HTML, ordered structure, source identity and malformed envelopes.
- [ ] Accept exact application/hal+json through the existing bound JSON adaptation path with fail-closed envelope handling; preserve all other media behavior.
- [ ] Run focused source capture/adapter regressions and offline replay of all 20 privately retained authentic Banktwo resources; record hashes, normalization and remaining media/rewrite blockers.
- [ ] Obtain independent exact-SHA review and synchronize Issue/Project evidence; keep activation and deployment disabled.

Implementation checkpoint `5d9fc1ad60cf899c46017417d7122914be6924ea` accepts all 20 retained authentic Banktwo HAL resources without changing original payload or envelope hashes. Focused tests passed (157 tests and six subtests); 11 raw normalized documents passed strict validation and nine retain unresolved image errors. The supported capture path records unavailable optional assets explicitly and yielded strict-valid source fallback for all 40 retained cross-bank resources in offline replay. Independent review found no P1/P2; exact-head CI is pending. This does not establish live asset availability, rewrite eligibility, lifecycle completion or production release readiness.

## Bankone CLI timeout compatibility

Goal: Restore Bankone ingestion CLI construction by passing --timeout-seconds to the existing SourceConnectorClient timeout parameter.

Issue: https://github.com/lucronn/autodata/issues/318; parent #186; Project https://github.com/users/lucronn/projects/8. Plan: `docs/superpowers/plans/2026-11-05-bankone-cli-timeout-compatibility.md`; record: `docs/agents/records/2026-11-05-bankone-cli-timeout-compatibility.json`.

The public --timeout-seconds flag forwards its float to SourceConnectorClient timeout; default30.0 and existing client validation stay authoritative. Scope is only the CLI constructor keyword plus a focused offline test using the real constructor and mocked traversal/persistence. Credentials, selectors, output and persistence behavior remain intact. No live ingestion, shared-client alias, deployment or unrelated compatibility work is authorized.

Concrete todo:
- [ ] Add a focused offline CLI regression using the real SourceConnectorClient constructor and mocked traversal/persistence.
- [ ] Change only the CLI constructor keyword from timeout_seconds to timeout, retaining the flag, default, credentials and persist behavior.
- [ ] Run red/green focused checks, Bankone batch regressions and diff checks; commit/push the validated two-file fix for independent exact-SHA review.

Bankone CLI implementation `f15ce05bd29d0f5a0cceb9ab8f3642c6f73b268c` changes only the connector constructor keyword to `timeout`. Three real-constructor CLI regressions and ten Bankone batch tests passed after the original TypeError was reproduced. Exact-head GitHub verification passed in run `42044574931`; PR #320 merged as `ccdfbbedab0a90957ddb077595bcc8f050373c02`. The bounded real-source staging rerun remains a separate acceptance step.
