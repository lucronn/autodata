# AutoData GitHub Operating Model

## Repository workflow

AutoData uses trunk-based development with a protected `main` branch:

- Work is performed on short-lived branches named `codex/<topic>` or an equivalent team convention.
- Pull requests are small, linked to a GitHub Issue, and use squash merge.
- `main` requires successful CI, review from the owning CODEOWNERS group, and no unresolved blocking review thread.
- Releases are created from tagged commits on `main`; release notes identify schema, API, worker, and data-contract changes.
- No long-lived `develop` or release branches are required for the initial organization.
- Emergency changes still pass the same automated checks and receive a follow-up incident or review record.

## Ownership boundaries

CODEOWNERS should align with domain responsibility rather than programming language:

| Area | Owning group |
| --- | --- |
| API, auth, entitlements | API/platform owners |
| Vehicle taxonomy and canonical schema | Data-model owners |
| Fast/deep ingestion and source adapters | Ingestion owners |
| OCR, extraction, embeddings, quality | Data/AI owners |
| Procedures, diagnostics, electrical content | Domain-review owners |
| Compose, Kubernetes, CI, observability | Developer-infrastructure owners |
| Billing and webhook reconciliation | Platform/billing owners |
| Security, source rights, takedown | Security/data-governance owners |

Ownership names are configured when the actual GitHub organization is known; the blueprint does not invent accounts or teams.

## Pull-request requirements

Every change identifies its affected contract and includes the appropriate evidence:

- Schema changes include migration direction, rollback/forward-compatibility notes, and fixture impact.
- API changes include request/response examples and error behavior.
- Event changes include envelope version, consumer impact, and replay behavior.
- Worker changes include idempotency key, retry classification, and dead-letter behavior.
- Data-quality changes include a fixture or source example and expected publication result.
- Infrastructure changes include local parity, health checks, resource implications, and secret handling.
- Source changes include rights/attribution metadata and takedown implications.

## CI contract

Required checks are:

1. Go formatting, static analysis, and unit tests.
2. Python formatting, type checks, lint, and unit tests.
3. Integration tests against PostgreSQL/pgvector, NATS JetStream, and MinIO.
4. Migration validation from a clean database and an upgrade database.
5. API and event contract compatibility checks.
6. Container builds for API and both worker images.
7. Dependency, secret, and container vulnerability scanning.
8. Deterministic end-to-end purchase -> fast-lane -> `viewable` -> deep-enrichment smoke test.
9. Artifact publication for versioned release tags.

CI must distinguish code/test failures from unavailable infrastructure. A skipped external provider or unavailable optional service cannot be reported as a passing ground-truth integration test; the check must state whether it ran, skipped, or failed and why.

## Environments and secrets

The delivery model names `dev`, `staging`, and `production` environments. Each environment has scoped secrets and separate data/storage resources. Production credentials are never copied into local fixtures or GitHub variables with broader scope than required. Deployment credentials use the provider's short-lived or federated mechanism where available.

## Issue and label conventions

Issue titles should describe an outcome, not an implementation detail. Labels are namespaced and stable:

```text
area:api             area:data-model       area:fast-lane
area:deep-lane       area:billing          area:dev-infra
area:platform        area:security
type:feature         type:bug              type:data-quality
type:source-ingestion type:infrastructure type:security
priority:p0          priority:p1           priority:p2
priority:p3          risk:high             risk:critical
```

Issue forms cover feature, source/ingestion, data-quality defect, infrastructure, security/privacy incident, and dataset-enrichment request. Every form captures affected area, user impact, acceptance criteria, source/evidence references where relevant, and whether the change affects API, event, schema, or entitlement contracts.

## Project workflow

One portfolio GitHub Project is the planning system. Its views are Roadmap, Current Work, Ingestion and Data Quality, Platform and Developer Infrastructure, and Release Readiness. The project fields and parameterized provisioning steps are in [project-bootstrap.md](project-bootstrap.md).

The Project is not a substitute for repository history: issues hold problem/acceptance context, pull requests hold implementation evidence, and releases hold shipped-version notes. Project items link those records rather than duplicating their full content.
