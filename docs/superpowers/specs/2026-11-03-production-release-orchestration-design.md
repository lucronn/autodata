# Dual-source production release orchestration

**Date:** 2026-11-03  
**Baseline:** `0ed449fe5119484f8dd8f40b40607aa3beb11e49`  
**Scope:** AutoData platform, catalog API, and Workshop web application.

**Issue:** https://github.com/lucronn/autodata/issues/186

## Outcome

Use both independent Bankone and Banktwo APIs. Preserve immutable source
content, publish one validated, uniquely worded canonical article revision in
the existing ordered document format, and serve readable source content until
that revision is ready. Repeated requests reuse persisted work. A production
release requires evidence from the complete system, not just successful agent
responses or unit tests.

## Architecture decision

Extend the existing Go API, Python ingestion/enrichment workers, PostgreSQL,
NATS, object storage, agent registry, and local autonomy tools. A new agent
framework would duplicate existing planning and release controls; rewriting the
application would discard functioning catalog, document, and provenance code.
Neither is required for this release.

The coordinator uses the existing registered roles. Three worker slots may run
independent tasks while the coordinator integrates and verifies. Each builder
owns an isolated worktree and an explicit path set. Shared contracts and schema
changes are serialized before their consumers. Independent reviewers inspect
the exact candidate commit and never approve their own changes.

## Agent execution profile

After planning, every implementation and review dispatch uses GPT-6.1 Sol
(`gpt-6.1-sol`) with `medium` reasoning and Fast mode. Explicit local CLI
configuration is `service_tier = "fast"` and `features.fast_mode = true`;
the wire service tier is `priority`. User-scoped defaults are not changed.
Missing model/tier availability blocks the dispatch rather than silently
substituting a different model, reasoning level, or service tier. The planning
contracts record this request; R0 must make the legacy runner enforce it.

References: [Codex speed](https://developers.openai.com/codex/speed/) and
[configuration reference](https://developers.openai.com/codex/config-reference/),
retrieved 2026-11-03.

## Article identity and lifecycle

- Canonical identity includes provider, opaque source article reference, and
  applicable vehicle/configuration scope. Equal titles or provider-local IDs
  from different banks do not establish equivalence.
- A transformation key includes canonical identity, source content hash or
  revision, normalization version, and rewrite profile version. A new source
  revision creates an immutable revision under the same article identity.
- Work is claimed durably in PostgreSQL with a lease, fencing/ownership token,
  bounded retries, and recovery after worker death. Concurrent requests join
  the existing job. A process-local cache is only an optimization.
- Publication is effectively once: one winning persisted revision and one
  logical outbox event per transformation key. Delivery may repeat and must be
  idempotent. Exactly one external model invocation across a crash requires
  provider idempotency support; without it, record the ambiguous attempt and
  prevent duplicate publication rather than claiming impossible guarantees.
- Source bytes, content hash, source bank, retrieval time, rights, evidence,
  and local image assets remain associated with the revision. Opaque resource
  references always return to their originating bank.
- Rewriting changes eligible prose while preserving numbers, units, torque
  values, part/tool identifiers, applicability, safety warnings, block IDs,
  order, tables, image positions, and evidence. Unknown content remains visible
  with review status. Validation failure retains the source view.
- Deterministic structural normalization alone does not count as a completed
  rewrite. Generated content remains `UNREVIEWED` until authorized review.

## Source coverage

Both banks contribute to the configured catalog union, with explicit completion
and failure state per provider. A nonempty Bankone result does not suppress
Banktwo discovery or prove combined completeness. Usable rows from a healthy
bank remain available when the other bank is unavailable. A selected opaque
article reference stays bound to its originating bank; trying another bank
requires a separately resolved descriptor, never reusing or guessing that ref.

## Read contract

Keep the existing ordered document schema as the single rendering format.
Expose content origin (`source` or `canonical`), processing state, stable
article/job identifiers, revision, review status, and retry information as
additive, documented API fields. The API returns validated canonical content
when ready; otherwise it returns a safe source projection and the pending or
failed processing state. No article detail is fetched while browsing indexes.

If neither stored nor bounded source content is available, return an honest
pending/unavailable result with retry guidance; never fabricate a complete
article from a title. Source text is sanitized. Images use local opaque media
URLs or explicit unavailable placeholders. Browser rendering never receives
bank credentials or fetches provider assets directly.

Workshop preserves vehicle/article selection, displays source and processing
status, polls with bounded backoff and cancellation, and switches atomically to
the completed canonical revision. Failure keeps an available source view
readable. Authorization, vehicle scope, entitlements, and takedown rules apply
equally to canonical, source, status, and media responses.

## Release workstreams

| ID | Owner | Result | Dependencies |
| --- | --- | --- | --- |
| R0 | coordinator + reliability/review agents | Verifiable orchestration and release-control evidence | Planning synchronization |
| R1 | Python builder + source/schema agents | Provider-correct identities, resource routing, complete-detail checks, durable job store | R0 |
| R2 | Python builder + quality/reliability agents | Durable normalize/rewrite/publish lifecycle, concurrency and replay recovery | R1 |
| R3 | Go builder + contract/source agents | Immediate source fallback and explicit additive lifecycle API | R2 contract |
| R4 | Go/web builder + consumer/test agents | Workshop source-to-canonical experience and browser tests | R3, R5 identity/session contract |
| R5 | Go/platform builder + security agent | Production identity, existing access policy, and media access verification | R3 |
| R6a | evidence builder + source/review agents | Versioned real staging-population evidence adapter | R0, R2, R3 |
| R6 | release/test/reliability agents | Reproducible production candidate, staging canaries, recovery and rollout evidence | R0–R5, R6a |

The detailed queue and acceptance commands live in the linked implementation
plan and machine task files. Those files are a dispatch interface, not a second
technical specification. Downstream tasks require a committed planning record
and a fresh exact-base preflight before their implementation starts.

## Release gates

All eight existing policy decisions must pass for one exact implementation
SHA: deterministic CI, contracts, schema, source provenance, data quality,
security, reliability, and independent review. Findings and evidence must be
preserved as structured artifacts. Completeness and provenance coverage must
come from measured evidence, not from a model returning `pass`.

The acceptance matrix covers both banks independently, both together, one
bank unavailable, duplicate/concurrent reads, changed source revisions,
rewrite rejection, worker crash/lease recovery, database/object-store/broker
failure, partial media, takedown, unauthorized access, and cold/warm browser
flows. Warm reads make no source or model call for a completed revision.

Clean and upgrade migrations, container builds, dependency/secret/container
scans, authenticated staging canaries, backup/restore, and forward recovery
must have actual results. A health probe or fixture run cannot replace them.
Production deployment remains outside the repository's current autonomy
authority and requires the user's explicit deployment instruction when the
candidate and rollout plan are reviewable.

## Baseline evidence and limits

The three parallel audits found existing catalog/document/test functionality
but material release gaps: rewrite helpers are not on the intake path; selected
article work lacks durable deduplication; a Banktwo title-only response can be
marked complete; provider-neutral fetch-job documentation exceeds runtime
implementation; and article reads do not provide the required asynchronous
source fallback. Production access control and release evidence require their
own acceptance work. These findings are tasks, not completed fixes.

Existing master CI passed at
https://github.com/lucronn/autodata/actions/runs/41166877658 . Public `/healthz`
probes returned HTTP 200 for both configured bank domains on 2026-11-03.
Authenticated source reads and production readiness were not established by
those probes. No production deployment or schema mutation was performed.
