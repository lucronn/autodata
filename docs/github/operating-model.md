# AutoData GitHub Operating Model

## Repository workflow

AutoData uses trunk-based development with a protected `master` branch (the repository's current default branch):

- Work is performed on short-lived branches named `automation/<topic>` or an equivalent team convention.
- Pull requests are small, linked to a GitHub Issue, and use squash merge.
- `master` requires successful CI, review from the owning CODEOWNERS group, and no unresolved blocking review thread.
- Releases are created from tagged commits on `master`; release notes identify schema, API, worker, and data-contract changes.
- No long-lived `develop` or release branches are required for the initial organization.
- Emergency changes still pass the same automated checks and receive a follow-up incident or review record.

### Delivery-state rules for the natural-language generator

Issue #87 and its Project #8 item are the single delivery record for the
natural-language quote/procedure generator. Work follows the plan's task
order, but the repository plan remains the technical source of truth and the
Project item remains an index. Do not create a second roadmap, progress
document, or parallel acceptance checklist for the same work.

Use Project Status as an evidence-backed state machine:

- `Backlog`: scoped in the plan but not ready for implementation.
- `Ready`: the plan, Issue, Project item, repository references, concrete
  todo list, and synchronized preflight record are present at the pinned base
  SHA.
- `In Progress`: implementation or verification is underway. Local changes
  without a commit remain here and are recorded as `uncommitted`; they must
  not be described as pushed or verified at a SHA.
- `Blocked`: a required dependency, source authorization, review, CI check, or
  planning-gate condition prevents safe progress. Record the exact blocker and
  the next observable condition in the Issue and Project source/dependency
  field.
- `Review`: the scoped implementation is committed and pushed, focused tests
  have passed, and the reviewer has the exact commit range. A green focused
  test run alone is not sufficient when the scoped review has not completed.
- `Done`: the acceptance evidence for the relevant task is complete and the
  Issue, Project item, plan, and repository documents identify the same exact
  verified commit or release. `Canceled` is reserved for an explicitly
  abandoned scope with a recorded reason.

For every status transition, update the existing Issue or Project item rather
than opening a duplicate tracking record. The source/dependency text should
identify the Issue, plan reference, exact pushed implementation SHA (or
`uncommitted`), review state, tests/CI evidence, and any external dependency.
An uncommitted working-tree change is progress, not a release checkpoint.

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

Changes implementing Issue #87 also include evidence for the behavior they
touch. The evidence must cover the applicable cold and warm paths: one
natural-language request, vehicle resolution and clickable options when
ambiguous, an immediate procedure when source data is available, raw
`source_unnormalized` visibility while normalization runs, required versus
recommended labor, shared-operation overlap deduction, source prices with
`priced_at` and no markup, immutable derived revisions, provenance/evidence
links, and correlated worker progress with bounded retry/dead-letter behavior.
Warm replay evidence must show that normalized data is reused without another
source or model call. A Mercury-2 result is advisory evidence only; it cannot
replace application-owned vehicle scope, source allowlisting, arithmetic,
provenance, or publication validation.

## CI contract

Required checks are:

1. Formatting and static analysis.
2. Go unit tests.
3. Python unit tests.
4. Integration tests against PostgreSQL/pgvector, NATS JetStream, and MinIO.
5. Migration validation from a clean database and an upgrade database.
6. API and event contract compatibility checks.
7. Container builds for the API and both worker images.
8. Dependency, secret, and container vulnerability scanning.
9. Deterministic end-to-end purchase -> fast-lane -> `viewable` ->
   deep-enrichment smoke test, including cold and warm chat paths when the
   generator is in scope.
10. Artifact publication for versioned release tags.

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

Project fields are used consistently for the generator and its supporting
work: `Area` identifies the delivery seam (`Product`, `API`, `Data Model`,
`Fast Lane`, `Deep Lane`, `Search`, `Billing`, `Dev Infra`, `Platform`, or
`Security`); `Data section` identifies the affected vehicle-data section;
`Priority` and `Risk` express delivery urgency and exposure; `Target release`
is the intended milestone date; and `Source or dependency` carries the Issue,
plan, exact SHA/release, review state, CI run, and dependency notes. Labels
remain the stable query surface for automation and must agree with the fields.

For Issue #87, the Project item stays `In Progress` until the committed
implementation, scoped review, and final cold/warm acceptance evidence are
complete. Do not set it to `Done` for a focused unit-test checkpoint, and do
not replace its existing item with a duplicate issue or draft item.

## Documentation source of truth

Normative architecture, infrastructure, API, data-quality, agent, and delivery documents live under `docs/`. The Project is the synchronized roadmap and navigation index; it must link to the canonical repository document and must not contain a competing copy of its acceptance criteria, operating rules, or technical contract. Issues may summarize the relevant outcome, but the repository document at the pinned implementation commit remains authoritative.

All implementation work follows the [pre-implementation planning and tracking gate](../agents/pre-implementation-gate.md): plan first, synchronize the Issue, Project item, and repository records, pass the machine preflight, and only then modify implementation files. The gate is enforced at the autonomy runner and orchestrator boundaries and applies regardless of agent, provider, model, IDE, or automation interface.

Agents may create or modify Markdown, MDX, reStructuredText, and AsciiDoc only under `docs/`. The runner treats a document changed outside that tree as a critical scope violation. Run evidence, logs, and machine-readable reports belong in the external run directory or their explicitly declared fixture/report paths; they are not replacement documentation.

Every documentation change must update the relevant Project index item or linked implementation issue in the same release flow. The item records the canonical document path, affected area, review status, source/dependency reference, and the commit or release where it was verified. If a Project item and repository document disagree, the repository document at the exact verified SHA wins and the Project item is marked `Blocked` until synchronized.

The canonical documentation set for this work is the approved design and plan
under `docs/superpowers/`, the architecture documents under `docs/architecture/`,
the pre-implementation gate under `docs/agents/`, and these two GitHub
operating documents under `docs/github/`. Agents must update an existing
canonical document or linked Issue/Project record; they must not create an
ad-hoc roadmap, duplicate progress ledger, or competing technical contract.
Task-specific test output may live in its declared report location, but it is
evidence linked from the canonical record, not a new source of truth.

### Public-facing README and Wiki

The root `README.md` is the repository's public landing page: it should explain
what AutoData does, show one intentional local visual, identify the current
verified development slice, and route readers to the canonical documentation.
It is an index and product introduction, not a replacement for the technical
documents under `docs/`.

The GitHub Wiki is a lightweight public-facing projection for first-time
readers. Wiki page sources live under `docs/wiki/` and are published to the
repository Wiki only after they are reviewed against the repository documents.
The Wiki may summarize and navigate, but it must link to repository `docs/`
for architecture, lifecycle, contracts, infrastructure, governance, and
agent-policy details. Repository `docs/` at the verified commit remains the
source of truth when a Wiki page or README summary differs.

The README/Wiki refresh tracked by [Issue #88](https://github.com/lucronn/autodata/issues/88)
and [Project #8](https://github.com/users/lucronn/projects/8) has four concrete
work items: remove the redundant remote image embed and tighten the README
opening; replace the rough local visual; publish the four `docs/wiki/` pages;
and verify exact-SHA documentation and GitHub synchronization. The machine
checked pre-implementation record is
`docs/agents/records/2026-09-11-public-facing-readme-and-wiki.json`.
