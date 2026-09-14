# Architecture

AutoData is a modular, cloud-neutral monorepo with a synchronous API boundary,
provider-neutral Python workers, durable messaging, relational persistence, and
S3-compatible source storage.

## Platform map

1. The Go API authenticates callers, enforces organization and dataset
   entitlements, accepts requests, and serves projection-oriented reads.
2. The Python ingestion worker retrieves source resources, preserves raw bytes
   and provenance, normalizes vehicle and article facts, and publishes the first
   viewable revision.
3. The Python enrichment worker processes independent deep-lane sections such
   as procedures, diagnostics, documents, diagrams, embeddings, and quality
   review.
4. PostgreSQL with `pgvector` stores canonical records and retrieval vectors;
   NATS JetStream carries durable versioned events; MinIO provides local
   S3-compatible source-object storage.

## Fast lane and deep lane

The fast lane validates vehicle identity and core facts, records source and
evidence links, and publishes an immutable revision as soon as the minimum
viewable contract is satisfied. The deep lane works asynchronously and can
publish section revisions independently. A deep-lane failure affects its
section; it does not hide a previously viewable revision.

## Canonical technical documents

- [Domain model](https://github.com/lucronn/autodata/blob/master/docs/architecture/domain-model.md)
- [Dataset lifecycle](https://github.com/lucronn/autodata/blob/master/docs/architecture/dataset-lifecycle.md)
- [API, event, and persistence contracts](https://github.com/lucronn/autodata/blob/master/docs/architecture/contracts.md)
- [Infrastructure and developer workflow](https://github.com/lucronn/autodata/blob/master/docs/architecture/infrastructure-and-dev.md)
- [Platform design specification](https://github.com/lucronn/autodata/blob/master/docs/superpowers/specs/2026-09-01-autodata-platform-design.md)

The [repository architecture overview](https://github.com/lucronn/autodata/blob/master/docs/assets/autodata-platform-overview.png)
is a visual orientation aid, not a substitute for those contracts.

## Chat guide path

The chat answer is an additive projection over the existing quote/procedure
contract. Vehicle resolution remains application-owned. Read-only AutoAPI Two
content is fetched only for the selected provider vehicle, and the guide
composer retains ordered source text, torque values, warnings, evidence IDs,
and figure associations. Removal and installation are separate required
coverage checks, with timing-belt access included when the selected vehicle's
repair content requires it. The PDF renderer consumes the same complete guide
revision and checks each referenced image before serving it through the
authenticated chat boundary.

See [the canonical consumer repair-guide contract](https://github.com/lucronn/autodata/blob/master/docs/architecture/consumer-repair-guides.md)
and [Issue #89](https://github.com/lucronn/autodata/issues/89).
