# Production Release Orchestration Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the current-session execution. Follow AGENTS.md and the repository planning gate before implementation.

**Goal:** Set up and execute a traceable multi-agent delivery queue for the dual-bank platform, once-published rewritten articles, and source fallback until ingestion completes.

**Architecture:** Reuse the existing registered agents, provider-neutral task contracts, isolated worktrees, deterministic gates, and GitHub Project #8. Make orchestration evidence trustworthy before handing it release authority. Deliver the application in bounded dependent workstreams.

**Tech Stack:** Go 1.26, Python 3.12+, browser JavaScript, PostgreSQL/pgvector, NATS JetStream, S3-compatible storage, GitHub Projects, existing local autonomy CLI.

**Spec:** `docs/superpowers/specs/2026-11-03-production-release-orchestration-design.md`

**Project:** https://github.com/users/lucronn/projects/8

**Issue:** https://github.com/lucronn/autodata/issues/186

**Planning state:** Reviewed checkpoint linked to verified Issue #186 and Project
#8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`. R0 evidence and disjoint R1 intake use
direct coordinator dispatch with their own passing exact-base preflight.
R0 evidence passed independent deterministic verification at
`a7493d41be4f0c4aa93bdaaa74afa14c30d49965`, integrated as
`643b8d3fc762cfdc9b456d28a47b7a4a9cde6402`; see
[the verification record](../../verification/2026-11-03-agent-evidence-hardening.md).
R1 candidate `330c29c0a1b2b7d43745dd9b2ba93cf1f9055e09` passed independent
schema/source/reliability review and 644 ingestion tests plus 25 subtests in the
isolated PostgreSQL/S3/NATS fixture. It is integrated at
`c3b7a46d1233a1af8c0f0cba19a2f169d5a9a4b4`; see the
[lifecycle verification record](../../verification/2026-11-03-canonical-article-lifecycle.md).
R2 tasks 5–8 are independently verified at candidate
`dba2d96170db5694052bd36dc7fca645fdf0a51d`, integrated at
`9fd3f9142ee22c47810765130cbc36d6284994a3`. Candidate and integration each pass762 tests
plus25 subtests; mandatory smoke passes267 with35 measured runtime records.
The reviewed shared migration-runner repair is the next synchronized task;
R3 waits for its verified integration and a fresh checkpoint.
The real CLI schema repair passed independent review and 71 autonomy tests at
`e90047f2d50829ae0bcdc68c0dc8ed69c998cb4a`; the bounded retry reached a second schema incompatibility (regex lookaround).
R0 controller candidate `6762e844d12ef0d342e28f0131d477d73e1fe4a1` is
independently approved and integrated at `116d949029edeccd3447da9dd0c5f3de4252c42b`,
with 101 integrated autonomy tests passing; see
[controller verification](../../verification/2026-11-03-release-controller-preflight.md). Other dependent
tasks remain blocked pending verified integrations and refreshed checkpoints.
Production release certification remains outstanding.

The bounded plans are [agent evidence](2026-11-03-agent-evidence-hardening.md),
[release control](2026-11-03-release-controller-preflight.md),
[canonical article lifecycle](2026-11-03-canonical-article-lifecycle.md), and
[source fallback API/Workshop](2026-11-03-source-fallback-web.md), and
[production identity/access](2026-11-03-production-access.md), and
[release acceptance](2026-11-03-release-acceptance.md). The
[machine queue](../../agents/tasks/2026-11-03-production-release/queue.json)
contains nine assignments and their dependencies.

## Global constraints

- After planning, every implementation, verification, and review agent uses `gpt-6.1-sol`, `medium` reasoning, and Fast mode (`service_tier = "fast"`, request tier `priority`). No fallback or model escalation is authorized.

- Both independent banks retain their own identities, credentials, and opaque references.
- One canonical article identity; immutable source and transformation revisions; no title-based cross-bank merging.
- Keep the existing ordered document format and source order, technical facts, warnings, evidence, and local media behavior.
- Rewriting is distinct from normalization; incomplete/failed rewrite remains source content with honest state.
- Persisted uniqueness and job leases enforce concurrency; delivery retries remain idempotent.
- Production deployment is outside current autonomy authority.
- Every implementation task has a synchronized Issue/Project record and committed exact-base preflight.
- Builders use disjoint worktrees; migrations/shared contracts serialize; reviewers cannot approve their own code.
- Preserve existing Issue #184; do not silently close or absorb its maintenance scope.

## Concrete todo

- [x] Synchronize the release issue, Project index, design, plan, and machine planning record.
- [ ] Configure versioned machine task contracts, ownership, dependencies, and reproducible dispatch commands.
- [ ] Harden orchestration evidence and release-controller planning, with independent review and negative tests.
- [ ] Deliver dual-provider intake and durable canonical rewrite lifecycle through R1 and R2.
- [ ] Deliver source fallback API and Workshop transitions through R3 and R4.
- [ ] Verify production access control through R5 and full staging/recovery release acceptance through R6.

## R0: Orchestration setup and evidence

**Files:** `scripts/autonomy/{runner.py,orchestrator.py,release_controller.py,agent-output.schema.json,test_runner.py,test_orchestrator.py,test_release_controller.py}`, `docs/agents/{autonomy-tooling.md,runner-interface.md,release-controller.md}`, and this plan's task/record JSON under `docs/agents/`.

**Consumes:** Existing registry/policy and this design. **Produces:** Runnable scoped contracts, a documented queue, exact-SHA evidence, and a release plan that is valid before any external mutation.

- [ ] Add task JSON contracts for R0–R6 using the existing `validate_task_contract` shape. Include explicit dependencies, allowed paths, acceptance tests, forbidden scope, and pre-implementation record references.
- [ ] Enforce the requested model/reasoning/Fast profile through task, envelope, and explicit local CLI arguments; `--ignore-user-config` must not discard it. Record the effective settings and block unavailable configurations without a silent fallback.
- [ ] Extend provider result handling to retain findings, command outcomes, evidence references/hashes, and measured coverage. A natural-language `pass` without required successful commands and artifacts must fail closed.
- [ ] Test missing/tampered artifacts, failed commands with a claimed pass, stale SHAs, and fabricated coverage. Preserve synthetic fixtures as synthetic.
- [ ] Correct release Project operations to use resolved project IDs and validate all required IDs/capabilities before merge. Test the installed GitHub CLI argument contract and post-merge failure behavior. Keep production deployment forbidden.
- [ ] Run `python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v` and an independent review at the resulting SHA. A real provider fixture must run under an isolated automation identity before unattended provider execution is certified.

## R1: Both-bank intake correctness

**Files:** ingestion `source_connector_client.py`, `catalog_service.py`, `procedure_images.py`, `bankone_job_persistence.py`, new `source_job_persistence.py`, corresponding ingestion tests, and additive migrations after the existing latest migration when required.

**Consumes:** Source Connector v1 and existing provider identity mapping. **Produces:** Explicit provider lineage through detail/media fetch, honest completeness, generic durable job persistence retaining legacy UUIDs/idempotency/retry/snapshot links.

- [ ] Add regressions for title-only Banktwo fallback, colliding article IDs/titles across banks, opaque asset refs without prefixes, partial bank enumeration, and failed-primary/healthy-secondary selection.
- [ ] Require a matching published canonical revision before `complete:true`; readable normalized source remains fallback with honest processing state.
- [ ] Carry the originating provider with every asset reference; deduplicate descriptor/materialization reads.
- [ ] Connect generic source job persistence to runtime callers and test legacy import, concurrent claims, retries, restart, and provider separation against PostgreSQL.
- [ ] Run the connector, catalog service, document, image, persistence and durable job suites. Add authenticated per-bank canaries separately from deterministic fixture evidence.

## R2: Durable canonical rewrite

**Files:** ingestion `catalog_service.py`, `worker.py`, `procedure_rewrite.py`, `procedure_normalize.py`, `article_document.py`, `article_identity.py`, `persistence.py`, `source_job_persistence.py`, worker HTTP boundary, associated tests, and additive schema/contracts.

**Consumes:** R1 provider identity/jobs and the ordered document. **Produces:** Durable source snapshot → normalized → rewrite validated → published revision lifecycle with stable transformation key and recoverable jobs.

- [ ] Add a two-worker PostgreSQL race test asserting one canonical revision and one logical publication event for the same transformation key.
- [ ] Add crash tests before/after source persistence, model result persistence, revision commit, and outbox delivery. Verify lease expiry and fencing reject a stale worker's publication.
- [ ] Invoke the rewrite adapter in background ingestion; persist provider/model/profile metadata and output before publication. Reuse persisted successful output on retry.
- [ ] Test numeric/unit/tool/warning/order preservation and reject incomplete or altered output. A missing model configuration or rejection returns an explicit pending/failed source state.
- [ ] Test warm replay with source/model call counters equal to zero, changed-source revision behavior, and identical source IDs from different banks remaining distinct.
- [ ] Test unchanged-source refresh after exhausted rewriting: retain the original terminal transformation and attempt budget, record new source provenance, and avoid assigning its unique key to another job.

## R3: Source fallback API

**Files:** `apps/api-go/catalog_http.go`, `catalog_store.go`, `catalog_source.go`, related catalog/media tests, ingestion catalog HTTP boundary, and versioned catalog OpenAPI/schema files.

**Consumes:** R2 identity/state contract and immutable source references. **Produces:** Additive source/canonical origin, processing state, job/revision identifiers, and retry guidance using the ordered document projection.

- [ ] Test cold reads while rewrite is blocked: readable sanitized source arrives without waiting for the model, and repeated reads join one job.
- [ ] Test worker failure/retry while source remains readable, canonical transition after publication, and unavailable source with honest retry status.
- [ ] Link stored raw snapshots into a safe source projection for both banks; localize images during ingestion and use explicit unavailable placeholders until local media exists.
- [ ] Test partial/failed nonempty indexes do not report complete; preserve vehicle/configuration scope, authorization, and takedown across all projections.
- [ ] Migrate article listing to canonical descriptors with scoped legacy compatibility; keep both banks selectable when local IDs or titles collide, without downloading detail during list/search.
- [ ] Run Go catalog/media tests and Python catalog tests; validate additive OpenAPI compatibility.

## R4: Workshop application

**Files:** `apps/api-go/workshop/`, `apps/api-go/workshop-client.test.mjs`, related embedded-asset Go tests, and browser acceptance tooling under `scripts/dev/`.

**Consumes:** R3 additive API contract. **Produces:** Accessible source/canonical article views with selection-safe polling, retry/error states, and atomic replacement by the completed revision.

- [ ] Add browser tests for both banks through year → make → model → configuration → article, source-first loading, completion, failure, refresh, cancellation, and keyboard navigation.
- [ ] Render the existing ordered blocks, including table/callout/image positions, without provider-specific browser logic or credentials.
- [ ] Bound polling/backoff and cancel stale requests after selection changes. Keep usable source content during ingestion/retry failure.
- [ ] Run `node --test apps/api-go/workshop-client.test.mjs`, Go embedded-asset tests, and real browser acceptance against the local deterministic stack.

## R5: Production access controls

**Files:** API authentication/request middleware, `main.go`, catalog/media authorization paths, Workshop session integration, API tests, and deployment configuration for the approved identity provider.

**Consumes:** R3 routes and existing role/entitlement model. **Produces:** Verified production authentication and scope enforcement across canonical/source/job/media reads.

- [ ] Inventory the deployment identity boundary and select its supported verified token/session integration before code changes.
- [ ] Ensure development authentication cannot be enabled by a production default; test malformed, expired, wrong-audience, wrong-issuer and forged credentials.
- [ ] Test organization/role/entitlement isolation and revoked/taken-down source/media access using deterministic principals and a staging identity.
- [ ] Keep credential values out of browser bundles, logs, manifests, test artifacts and Git. Private security findings follow SECURITY.md.

## R6a: Real release evidence adapter

**Files:** `scripts/autonomy/{runner.py,orchestrator.py,agent-output.schema.json,test_runner.py,test_orchestrator.py}`, a staging provenance collector under `scripts/dev/`, and `docs/agents/agent-contracts.md`.

**Consumes:** Independently verified R0 tooling and R2/R3 persistence/read contracts. **Produces:** A versioned real staging-population evidence adapter accepted by the same release-bundle validator.

- [ ] Freeze a versioned staging population contract before implementation: candidate SHA, immutable population definition/hash, selected source-bank identities, article/source/transformation revision IDs, evidence locators, covered/eligible IDs, and collector command/artifact IDs. Reject empty, duplicate, changed or cross-candidate populations.
- [ ] Implement a trusted collector against the actual candidate database/object store. Enumerate the required population from pinned selection criteria, verify source/revision/evidence associations and hashes, and record measured counts. Keep licensed content and credentials out of published evidence; retain protected raw proof only in the isolated evidence store when needed for replay.
- [ ] Extend strict schemas and `validate_evidence_bundle` with an explicit staging adapter version. A synthetic-regression report cannot satisfy a staging task, and relabeling fixture scope cannot promote it. Unknown scope/version remains blocked.
- [ ] Test missing provenance, tampered population/hash, changed SHA, dropped eligible records, unavailable source storage and synthetic-to-staging relabeling. Run actual staging collection separately from deterministic adapter fixtures.
- [ ] Independently review the adapter and promote its commit to a new trusted checkpoint before R6 release verification. The adapter cannot approve itself by replacing evaluator code during a run.

## R6: Candidate and release acceptance

**Files:** `.github/workflows/autonomous-verification.yml`, `infra/compose/`, `infra/k8s/`, `scripts/dev/`, and canonical infrastructure/release runbooks.

**Consumes:** Independently reviewed R0–R5 candidate commits and the separately verified R6a real-evidence adapter. **Produces:** A reproducible candidate and exact-SHA release evidence; production deployment is a separate user-authorized action.

- [ ] Run clean and upgrade migrations, unit/contract suites, browser tests, container builds/scans, secret/dependency scans, and two-bank end-to-end ingestion.
- [ ] Exercise restart, lease recovery, broker redelivery, object-store failures, backup/restore and forward recovery. Record actual pass/fail/unavailable outcomes.
- [ ] Run authenticated staging canaries for each bank and both together, with one bank unavailable, without publishing source payloads or credentials.
- [ ] Require all eight independent gate reports at the candidate SHA and measured 100% required evidence/provenance coverage. Record deployment target, rollback/forward-recovery procedure and observability checks.
- [ ] Publish a reviewable release PR/candidate. A successful health endpoint or fixture workflow never substitutes for these gates.

## Dispatch and integration rules

R0 precedes trusted automated release execution. R1 precedes R2. Freeze the R2
state contract before R3; freeze R3 before R4. R5 may proceed after contract
freeze in a separate worktree; integrate its identity/session boundary before R4 completes so Workshop authentication and reader changes have one writer. R6 waits for all application lanes. If two tasks
need the same file, integrate the producer first and re-pin the consumer base.

R0 evidence and R1 intake may be implemented concurrently through the current
coordinator's collaboration tools: their implementation paths are disjoint and
each has its own synchronized committed record and machine preflight. R1 does
not invoke the legacy local runner or consume unverified R0 evidence. This
bounded scheduling refinement was independently reviewed against the existing
policy; it changes no required gate or protected input. Local-runner execution
and release automation remain blocked until R0 tooling is independently verified.

R1's 037/038 migrations have one writer. Before integration, the coordinator
collects clean/upgrade/legacy-preservation and concurrency results from the
isolated real PostgreSQL fixture, plus independent schema/source/reliability
review at the exact R1 SHA. Use this explicit protected-change workflow; the
normal runner's protected-path refusal remains intact. All eight required gates
still apply before release/merge, and no migration touches production data.

The coordinator records each builder's actual commit, commands, results and
review; preserves failures; and never combines reports from different heads.
Task JSON describes the next bounded assignment. The coordinator rechecks
dependencies, current head, GitHub tracking and preflight before dispatch;
the current local orchestrator does not itself schedule a multi-task DAG.

## Baseline checks

At the inspection baseline: 41 autonomy tests passed; 150 focused ingestion
tests plus 9 subtests passed; 14 Workshop JavaScript tests passed; focused Go
catalog/media/Workshop tests passed. These establish a starting point only.
Master CI and public bank probe references are in the design. No full release
acceptance is claimed.

## Planning review checkpoint

Nine task contracts pass the existing structural validator, reference existing
plans/docs, have an acyclic dependency graph, and record the requested Sol 6.1 /
medium / Fast profile. These are draft-input checks; the legacy runner does not
yet enforce the new execution field. Every task references verified Issue #186. Only the first R0 evidence record is
synchronized at the initial checkpoint; the separately committed R1 direct-dispatch
refinement has its own synchronized record. Other dependent task records remain
blocked until their dependency integration and fresh preflight.

Independent planning review resolved the staging-evidence adapter boundary,
post-merge tracking repair, canonical index/legacy query handoff, exhausted
transformation reuse, bounded media URL renewal, and deterministic auth-fixture
startup findings. Retry counts and catalog ordering are aligned across the
product plans. These reviews concern design and planned tests, not implemented
behavior. R5 production verification still requires real issuer registration; deterministic
implementation can use its frozen provider-neutral contract. R6/R6a scope and live
evidence must be refined against their integrated dependencies before dispatch.

## Read/access verification refinement

Independent plan review narrowed R3 to exact Go, contract and nine fixture paths
and a Go/Python bridge within the existing isolated lifecycle container. It must
exercise actual R2 scheduling against real migrated PostgreSQL; ordinary skipped
integration tests cannot certify the handoff. Exact R2 fixture bindings remain
to freeze after verified R2 integration.

R5 requires real PostgreSQL sessions and rejects executable memory fallback in
OIDC mode. Its optional API bearer audience must differ from the web client ID.
Local mode retains headless bearer clients only; Workshop login uses configured
OIDC, including development. The session401 `error.details.login_available`
discriminator and local login503/no-redirect behavior are frozen across R5, the
web spec and R4 acceptance. Unavailable login stops requests and clears protected
content without a redirect loop. Actual issuer/client/origin registration remains
pending for live acceptance, not a reason to block deterministic implementation.
These refinements are planning only; downstream task records remain blocked
until their dependency checkpoint and committed-base preflight pass.

## Migration-runner restart repair dependency

The [reviewed migration-runner plan](2026-11-03-lifecycle-migration-replay.md)
addresses the actual second-run037 failure and031 constraint regression without
editing SQL001–038. Its concrete todo is one shared POSIX/psql driver with a
session advisory lock, existing-version skips, transactional application and
marker checks; delegation from Compose/Base44/native/container/fixture paths;
real fresh/replay/upgrade/concurrent/crash tests; independent exact-SHA review
and actual CI confirmation. Markerless033 is explicitly replayed once using
its unchanged semantics and recorded atomically; the coordinator accepts the
documented reviewer-state/timestamp effects for isolated implementation
acceptance. Production migration remains outside current authority.

This writer waits for verified R2 because the fixture helper is shared, and R3
waits for the verified migration repair. R5 must audit planned039 against the
shared driver at its own scope checkpoint. The external Kubernetes migrator
image has no build source here and remains an explicit R6 certification
prerequisite. No fixture or local pass certifies that external image.

## App-server implementation and packaging checkpoint

App-server candidate `f43508beedc4d5ccb1a29ed8e49912d5d6d55a49` is independently approved and integrated at `f4d95680f721ce32f4d3cb2f8da0552ef1673750`, with131 integrated tests. The first actual app-server attempt blocked on a missing-bubblewrap startup warning before discovery or inference. The [narrow packaging remediation](2026-11-03-runtime-packaging.md) is synchronized for fresh preflight and one bounded retry, preserving strict warning rejection and all isolation/profile settings. Application work continues through the separately gated migration repair; runtime/release certification remains outstanding.

The current CI also exposes an independent [development test import-path defect](2026-11-03-dev-test-discovery.md) after ingestion passes. Its one-file test-only repair has a separate synchronized checkpoint; workflow/test assertions and the migration writer's ownership are preserved. Both verified repairs must integrate before claiming actual CI success.

The package-only runtime retry cleared the missing dependency and then blocked on the official disabled remote-control startup snapshot before inference. A [separate three-file protocol amendment](2026-11-03-runtime-disabled-notification.md) has passed independent planning review and is being synchronized for its own gate; it preserves exact profile, strict warning rejection and all container restrictions.

## Verified repair dependencies and R3 dispatch checkpoint

The shared migration runner candidate e401a54 and discovery candidate c76f7a2
are independently approved and integrated at1d07ce2. Combined fixture acceptance
passed809 tests plus32 subtests with no skips, and actual GitHub run41627289946
passed including live Compose smoke. The independently reviewed R3 runtime
refinement now pins supported Compose flags, captured fresh/empty/populated
replay through038, concrete Go packaging and the actual worker/hook handles.
R3's32 implementation paths remain unchanged; its synchronized task requires
this committed checkpoint and a zero-error preflight before dispatch.

Disabled startup amendment0da3c88 is independently approved and integrated
atf4cc249, with137 exact tests and44 independent adversarial checks. Its separate
one-trial coordinator record requires this fresh gate and preserves unchanged
container restrictions/profile settings. Runtime certification remains unverified.

## Runtime check-contract implementation checkpoint

The [independently reviewed runtime repair](2026-11-03-runtime-check-contract.md) has an exact five-file contract and synchronized concrete todo. It addresses observed Python3.11 command matching, trusted-check environment and fixture-local verifier scope while retaining strict replay/redaction and every global gate. Implementation follows a new committed-base preflight. Coordinator scratch receives separate independent review and restricted offline full-suite/eight-check acceptance; successful offline evidence is required before another separately gated live attempt. R3 continues its independent application lane, and release certification remains outstanding.

## Updated user release objective and commit cadence

The current [paid Workshop contract](../../architecture/workshop-commerce.md)
records the user's $20 price, USD assumption, cars.tk/Cloudflare domain and
proposed Firebase/Google Cloud deployment. The initial SKU is the selected
normalized configuration and region. The previous R5 OIDC-only and role-only
catalog assumptions require replacement before customer/commerce implementation.
The requested commit rule is implemented and pushed at `85aa09a`.

Runtime check repair `6992bd0` is independently reviewed and integrated at
`91c8e85`; actual restricted offline acceptance passes146 tests and all eight
frozen checks with zero provider calls. The integrated suite also passes146.
See [the verification record](../../verification/2026-11-03-runtime-check-contract.md).
Additional live synthetic trials remain deferred for product delivery.

R3 candidate `62e782c0b62ddd401193be7137f9a50f5d50a8b3` is independently
reviewed and integrated at `31ffe7ebcf28f345e0b5055b4dad10ebb7ed101c`.
All eight actual Go/Python/PostgreSQL source/canonical cases and independent
raw-projection/provenance checks passed; integrated Go and19 contract tests
passed. See [the R3 verification record](../../verification/2026-11-03-source-fallback-api.md).
The revised customer identity and commerce lanes require new synchronized
checkpoints; the older R5 scope is not automatically authorized by this result.

The user now targets launching a working production Workshop where a customer makes one payment for a single vehicle dataset and retains permanent account-bound access. Existing dual-bank ingestion, canonical rewriting and source fallback remain supporting requirements. Inspect the existing Stripe/payment reconciliation and entitlement boundaries before freezing the commerce/customer-account implementation plan. Price/currency and production domain/hosting/login configuration are still being clarified. R3 source acceptance continues; additional synthetic provider-runtime trial preparation is deferred while the product release requirements are reassessed. This objective update does not authorize an implementation agent to expand its pinned file scope without a new synchronized plan/gate.

The user also requested frequent GitHub commits. The [bounded instruction update](2026-11-03-frequent-commits.md) records the concrete todo: small coherent commits, clear messages and prompt pushes of validated milestones according to branch ownership. It preserves all planning and testing gates and avoids empty/artificial history changes. Its committed checkpoint must pass preflight before editing AGENTS.md.
