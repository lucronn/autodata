# Production Release Orchestration Implementation Plan

> **R6 scope update (2026-11-03):** The [bounded Workshop product-evidence assembler plan](2026-11-03-workshop-product-evidence-assembler.md) is authoritative for the offline first3 assembler and separately gated later2 staging collector. Earlier R6a/R6 broad path/dependency instructions here are retained as history and grant no implementation authority. Agent-runtime certification and full production release verification remain separate outstanding work.

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
records the user's $20 price, USD assumption, cars.tk domain with user-reported
Vercel-managed DNS and authority to change its records, and proposed
Firebase/Google Cloud deployment. DNS ownership does not verify hosting, proxy
use, TLS certificate configuration or the deployed production origin. The initial
SKU is the selected normalized configuration and region. The previous R5 OIDC-only and role-only
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


### Shallow CI repair checkpoint

Actual GitHub41689471428 at521385f and41688178571 failed two runtime prompt
tests loading historical5da393 from a shallow checkout. The complete current
prompt matches that frozen base byte for byte. The existing runtime-check
plan now specifies a checked-in byte read with fixed SHA256 assertion, preserving
all semantic assertions and production behavior. Expected implementation is
only test_runner.py inside the original five-path scope. Issue186 and Project8
record the same concrete todo: fresh committed-base preflight, depth-one
red/green, changed-byte rejection, full suite, exact-commit review and actual CI.
Prior offline acceptance remains valid for its exact SHA; current CI is failed.
No new live provider trial is planned.


### Firebase customer identity checkpoint

The reviewed Firebase identity plan supersedes the former customer OIDC/PKCE
proposal. R5 now owns exactly35 paths: official Admin Go v4.22.0, project+UID
accounts, opaque PostgreSQL sessions, same-origin exchange/CSRF/logout and
migration039. Its five real-PG cases and eight existing R3 regressions are
mandatory. Issue186/Project8 and canonical specs/tasks were synchronized and
read back; commit and exact-base preflight are required before dispatch.
Google Cloud project/domain/IAM configuration is separate from deterministic
implementation. Checkout/permanent grants, paid source/media enforcement,
customer commerce UI and deployment remain separately gated remaining work.


### Commerce and hosting planning handoff

The canonical workshop-commerce plan passed independent review after two
corrections: production installs the pinned official Stripe SDK from the same
dependency manifest, and paid orders carry a durable shared catalog-index intent
consumed by the existing reconciler. Its38-path task/fourteen real-PG cases remain
waiting for verified R5/039 and a fresh gate. Permanent ownership is independent
of source/model readiness; paid article preparation and media access are later
protected operations. The earlier GCE/Cloudflare hosting summary is historical;
the hosting proposal covers persistence, backup/restore and cutover. User-reported
Vercel DNS ownership corrects the DNS assumption only; hosting, proxy use, TLS
certificate configuration and the deployed production origin remain unverified.
Project/cost/recovery decisions and deployment configuration remain pending.
Neither plan is a deployment or live-charge gate.


### Paid access and unified customer UI handoff

The reviewed [paid catalog/media plan](2026-11-03-workshop-paid-access.md) owns
16 paths and12 actual cases across both banks. It depends on verified039/040:
exact configuration+region grants precede protected reads/preparation, explicit
CSRF-protected POST prepares shared canonical content, and paid GETs observe
state. Contextual v2 media rechecks owner, scope, rights and asset before reads.
The final customer UI consumes these contracts in one dependent lane, including
configuration.id, POST-then-poll and bounded media refresh. The former standalone
auth-only R4 scope is not dispatched. All implementation still requires a fresh
tracking checkpoint and machine preflight.

Actual CI41692463236 passed every job at22db145, including live Compose smoke.
R5 candidate8c7507 is in independent review; a Kubernetes ConfigMap placement
finding requires a corrected successor before integration/runtime acceptance.


### Unified paid customer UI planning checkpoint

The canonical `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md`
replaces the future auth-only R4 dispatch with one33-path customer lane after
verified identity039, commerce040 and paid-access integration. It preserves the
original18 browser scenarios and ordered reader/source/media requirements,
adding Google cookie sessions, server-priced checkout and permanent library.
Its120 DTO/browser and21 real API/browser cases are distinct evidence.
Actual production assets, pinned official SDK storage, real settlement/grants
and source/media access must be verified; no browser redirect or local state
grants ownership. Task/record remain waiting for dependencies and a fresh gate.


### Firebase identity implementation and runtime acceptance

Candidate b4f3dc86a18a8087f8ff664e37bec594909eae80 is independently approved
and integrated at3fdcd0bc0ac993dd15ad2219df9d09ffeed27a4e. Five actual
PostgreSQL/SDK identity scenarios,55 outer cases plus7 subtests and all8 real
dual-bank regressions through039 pass. The initial report-parser failure is
retained separately; a reviewed strict correction passed fresh acceptance.
Integrated Go/contracts,104 development and19 contract checks pass. See
`docs/verification/2026-11-03-firebase-customer-identity.md` for exact evidence.
Full integration CI is pending; commerce's reviewed39-path checkpoint follows
that verified dependency and a fresh synchronized gate. No production launch
or live identity/merchant configuration is claimed by this foundation.


### Verified identity and parallel commerce/SDK gates

Full CI41696273960 passed at472492dd868122b2b0da00dc84e15c5424aa0276,
including live Compose, completing the R5 dependency checkpoint. The reviewed
39-path commerce lane and10-path SDK packaging lane have synchronized actual
Issue186/Project8/canonical tasks and todo; each requires the new committed-base
preflight before its own isolated implementation. Their paths are disjoint.
SDK packaging remains a subset of the final33-path UI scope and introduces no
customer behavior. Paid access and final UI still wait for verified dependencies.


### Commerce staging-origin clarification

The same server-owned environment/public origin now anchors Firebase sessions and
Stripe Checkout return paths. Production remains exactly https://cars.tk; staging
uses its explicit HTTPS origin. The 39-path commerce scope is unchanged, and the
builder holds affected composition work until this amendment is tracked, committed
and passes fresh preflight. Todo: validate configuration before constructing the
provider, derive fixed Workshop paths plus stored order UUID, reject client-driven
redirects, and test production/staging/malformed origin cases.


### SDK integration and commerce ownership

The ten-path Firebase browser packaging candidate2a226577 is independently
verified and integrated at2577383; final browser/application behavior is still
owned by R4. Commerce39 continues from synchronized origin checkpointc4aaa08
with disjoint writers: commerce_api_builder owns eight Go/API/OpenAPI paths;
catalog_fallback_builder owns the remaining31 Python/schema/runtime paths.
The queue lists exact assignments. Both share the existing approved contract;
root integrates their branches before the14 real-PG cases and final review.
Status DTO uses `state` and `retry_disposition`, with `new_key` only after
authoritative expired/canceled state; every other state says `do_not_repay`.


### Commerce core review refinement

The39-path scope and disjoint31+8 ownership remain unchanged. Preserve the opaque
fragment on official Stripe-hosted Checkout URLs; app return origins remain strict.
Verify the real configured Price before offering checkout and the returned Session
financial values before returning its URL. Library includes revoked never-granted
orders with null granted_at and requires active descriptor/body/resource rights
before saying viewable. Todo: targeted regressions, synchronized refinement gate,
then all fourteen actual PostgreSQL cases and final independent review.


### Independent test race repair

The full Go race suite independently fails at7e7249f before commerce API changes:
TestUsableConfigurationsAreNotBlockedByMissingHydrationScope polls a fake field
while background hydration writes it. The separate one-path
[catalog test plan](2026-11-03-catalog-test-race.md) reuses existing channel
synchronization. Todo: synchronized gate, bounded test-only repair, targeted/full
race and ordinary Go verification, independent review and integration. Commerce
39-path ownership is unchanged; retain original failure evidence.


### Actual commerce service boundary acceptance

The39-path commerce gate now specifies one required actual Go-client/Python-HTTP/PG
root inside the first of fourteen PostgreSQL cases. This catches verified-owner
organization and checkout-version/owned200 mismatches that isolated mocks missed.
Two raw Go files extend the commerce artifact inventory to10;17assertion keys and
67outerpytest+7subtests remain. Todo: synchronized refinement gate, matched8/31
implementation, independently freeze the strict final collector and run actual
acceptance. The catalog race repair79c17ae is independently verified and must be
included before the final combined full-race run.


### Concurrent Workshop delivery

The user requested three concurrent builders. The canonical parallel plan is `docs/superpowers/plans/2026-11-03-workshop-parallel-delivery.md`: twelve article-access paths, four protected-media paths and thirty-two UI paths have exclusive owners. Reviewed interfaces permit parallel implementation after synchronized preflight while the coordinator completes dependency/runtime acceptance. This replaces serial dispatch timing, not production acceptance requirements. Commerce candidate9d33e1e remains unverified pending its remaining fixture repair and runtime/image/CI checks.


### Hosting passive-schema checkpoint: synchronized planning

**Historical A v3 checkpoint.** The blocked catalog-only v2 amendment below supersedes this material for the next A milestone; earlier synchronization is not v2 authority.

The [hosting passive-schema amendment](2026-11-03-workshop-hosting.md#passive-schema-observation-synchronized-plan-only-checkpoint), approved as plan-only v3 artifact SHA256 `65fb0e202f21e95e503ecec001da561ac1efee4accbe7e2f6c74ba8557653625`, starts from integrated planning base `bc62f86eac54eb81b61e4013f0e910f264556f6c`. This six-document checkpoint is `synchronized` after coordinator live Issue186/Project8 readback; commit/push, full-SHA preflight, coordinator integration/re-pin and independent checkpoint approval must precede implementation. The [task](../../agents/tasks/2026-11-03-production-release/workshop-hosting.json) and [record](../../agents/records/2026-11-03-workshop-hosting.json) carry the exact goal and concrete todo.

Next A scope is only runtime-check.py and test_host_runtime.py: fixed local container identity, dedicated existing socket-auth autodata_metrics role, fixed read-only schema/rights protocol and bounded fake-exec observations. Explicit database-owner/PUBLIC/column/MAINTAIN/type/RLS and ledger/capture bounds are required. Role/PGDATA HBA/ident provisioning and effective configuration proofs are future separately authorized administration; a Docker mount cannot attest superuser-only PostgreSQL settings. No password/admin fallback, secret mount or broad monitoring role is allowed.

Todo: synchronize the six canonical documents and live tracking; pin and independently approve the plan-only gate; implement/test the two A paths with no real Docker/DB/cloud/provider execution; independently review the exact candidate before integration. Keep services/readiness/runtime_evidence false and check missing_dependency; do not enable mutation/start/maintenance/deployment or claim runtime acceptance from fake transcripts.


Tracking synchronization read back: [Issue186 comment6617024444](https://github.com/lucronn/autodata/issues/186#issuecomment-6617024444) and [Project8](https://github.com/users/lucronn/projects/8) item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, field `Source or dependency reference`, at `2026-11-03T22:27:57.522560+00:00`. The comment records the same v3 goal, five concrete todos, exact two-path implementation scope and offline limits; the project note indexes it. This is a plan-only synchronization checkpoint, not implementation dispatch or runtime/deployment authorization.


### B release ZIP archive reader: synchronized planning checkpoint

**Historical synchronized B checkpoint.** Its exact comment6617360191/protocol/future-publication limitations are preserved below. Offline implementation is independently approved and integrated at052bbf9; this historical checkpoint is not the current blocked A gate.

**Goal:** Implement a bounded offline release ZIP archive verifier with independent archive and member SHA256 bindings, strict ZIP32 structure and JSON/image consistency checks; keep publication authentication and deployment unavailable.

The [canonical hosting amendment](2026-11-03-workshop-hosting.md#b-release-zip-archive-reader-synchronized-plan-only-checkpoint) proposes a pure bounded ZIP32 archive verifier at planning source base `a0eed5dce45171f5f94f72d99d2fdf694235df0d`. This is a proposed `release.json`/`images.json` producer contract with explicit local/central/EOCD agreement, signed/unsigned bounded descriptor parsing, no ZIP64 or extra fields, stored/bounded DEFLATE decoding and independent whole-archive/raw-member/canonical-manifest digest meanings. It does not claim compatibility with an actual GitHub Actions artifact: the current workflow produces none, and authenticated publisher/transport compatibility remains separately gated.

The next B implementation scope is only `infra/deploy/gce/cloud-ops.py`, `infra/deploy/gce/test_cloud_ops.py` and `docs/operations/workshop-gcp.md`. The task/record/queue are `synchronized` after live [Issue186 comment6617360191](https://github.com/lucronn/autodata/issues/186#issuecomment-6617360191) and [Project8](https://github.com/users/lucronn/projects/8) item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` readback at `2026-11-03T22:43:36.177270+00:00`; the project preserves historical A/R6 references and indexes the exact B goal/five todos/scope/limits in that comment. Independent draft review approved SHA256 `706f5fb2326ddc9e223547b4e95951f4643ba67d6b6e6a01d538198db0f319c6`. Commit/push this seven-document checkpoint, full-SHA preflight and independent coordinator gate handoff remain required before implementation dispatch. Historical synchronized A material does not authorize B. A and R6 files and workflow execution remain outside scope. Success can report only simulated archive consistency with provenance/deployment authority false; every CLI operation remains unavailable.

Concrete todo:

- [ ] Synchronize this exact B archive-reader goal, ZIP32 producer contract, scope and todo across Issue186/Project8 and canonical documents; commit/push a plan-only checkpoint, pin its full SHA and pass machine preflight before coordinator dispatch.
- [ ] Add failing synthetic archive tests for digest separation, strict local/central/EOCD and descriptor agreement, bounded stored/DEFLATE decoding, strict JSON and exact image observations; retain existing B tests.
- [ ] Implement only cloud-ops.py and test_cloud_ops.py for explicitly supplied in-memory archive bytes and independently bound raw member digests; preserve existing fake transcript API and every fail-closed CLI operation.
- [ ] Document proposed release.json/images.json producer layout, archive/raw-member/canonical-manifest digest meanings, fixed failure receipts and the lack of actual GitHub artifact compatibility or authenticated publication evidence.
- [ ] Run focused B tests, Python syntax, diff/scope and exact-base preflight checks; commit/push a coherent candidate and obtain independent exact-SHA review before coordinator integration; cloud/provider/workflow/deployment execution stays separately gated.


## Hosting catalog-only v2 correction: synchronized

Status: `synchronized` after live Issue186/Project8 readback. Independent plan-only review approved correction artifact SHA256 `7971a7ec0c260237dfea3f80be2318443981ffb40f8c63a2a3300dccf78a1d22`. This seven-document planning draft starts from integrated `052bbf9ac29a9c74163162f0f91adc2f6a656e4e` and contains no implementation. Blocked candidate `c51d637708c1e2ad24719e69d32ea87654c14473` remains unintegrated and excluded. Live Issue186 comment6617521783 and Project8 readback match the A goal/five todos/seven-doc scope/limits. Coordinator commit/push/integration/re-pin, exact-SHA preflight and independent checkpoint approval remain required before A implementation. The B archive checkpoint/source062d599/integratedb4953ef was synchronized at comment6617360191 and its independently approved offline implementation is integrated at052bbf9; that historical authority and unverified future-publication gate are preserved. A22/B8 ownership and R6/browser/application acceptance remain unchanged.

Goal: Replace the unsafe passive schema ledger read with fixed catalog-only observation and adversarial fake-exec tests; keep schema, service and deploy readiness unavailable until a separately approved stable catalog-before-ledger protocol exists.

The [canonical exact v2 contract](2026-11-03-workshop-hosting.md#exact-v2-response-and-validation-contract) fixes five response fields: integer protocol_version=2, phase=catalog, identity, rights and ledger_relation. All exact nested fields/types/ranges, duplicate/unknown/null/UTF-8/depth/member/string/numeric/capture rejection rules and unchanged exit3/exit5 behavior are normative there. AM/index metadata is explicitly deferred; no heap/index/execution safety or DDL stability is attested. v1, relabeled v1, ledger-bearing and cached/offline transcripts are rejected.

The fixed socket-only role retains SELECT-only least rights, with explicit database-owner/PUBLIC/column/MAINTAIN/type/RLS checks, future HBA/ident provisioning and no admin/password fallback. Query only built-in pg_catalog metadata, never public.schema_migrations data or application code. Valid catalog observations still leave checks.schema=false, services=false and runtime_evidence=false; deploy check exits3 missing_dependency. The catalog collector/validator return None and cannot promote schema success; offline ledger validation is disconnected from runtime dispatch. No new grants, lock helper, interactive stdin, secret mounts or readiness/start/resume/maintenance authorization.

The rejected candidate read the ledger before catalog validation. A two-SELECT ACCESS SHARE repair cannot provide complete DDL stability: SELECT-only authority cannot obtain the stronger locking needed to exclude index changes. A full snapshot/locking/privilege protocol is separately gated; read-only transaction flags alone do not prevent application code or external side effects. Docker mounts still do not attest effective PostgreSQL configuration.

Only runtime-check.py and test_host_runtime.py are the prospective A implementation scope after this committed, pinned and independently approved passing gate; no implementation is included here. Operations/runbook changes remain coordinator/B-owned. All tests are fake-exec, not actual PostgreSQL/host/cloud/provider evidence. B checkpoint062d599 and its approved offline implementation are integrated at this base; preserve its synchronized comment6617360191, future-publication gate, existing B workflow and R6/browser/application acceptance requirements.

Concrete todo (same task/record):

- [ ] Synchronize the reviewed catalog-only correction and blocked c51d637 evidence across Issue186, Project8 and seven canonical files including the coordinator queue; commit/push, independently review and pin a new passing preflight checkpoint before builder dispatch.
- [ ] Modify only runtime-check.py and test_host_runtime.py to remove all live ledger reads, implement the fixed built-in-catalog-only v2 observation, and retain fixed identity/auth/bounds/reinspection without new grants/helpers or interactive stdin.
- [ ] Add red/green fake-exec tests proving no ledger SQL is sent for any catalog fixture, including view/foreign/RLS/custom type/custom AM/expression index and concurrent-change transcripts; preserve all existing applicable offline tests.
- [ ] Run focused tests, syntax, scope/diff and pinned preflight; commit/push a coherent two-path candidate and obtain exact-SHA independent review before integration.
- [ ] Keep schema/services/runtime_evidence false and all mutation/deploy verbs blocked; any stronger lock privilege, provisioned helper, persistent interactive client, effective auth proof or real PostgreSQL/Docker/cloud execution needs separate approved scope/gate.

Coordinator integration index: [Issue186 comment6617490673](https://github.com/lucronn/autodata/issues/186#issuecomment-6617490673) records root052bbf9 and B/R6 integration. It is integration history only; A v2 goal/todos are now separately synchronized by comment6617521783 and matching Project8 readback.

Tracking receipt: [Issue186 comment6617521783](https://github.com/lucronn/autodata/issues/186#issuecomment-6617521783), [Project8](https://github.com/users/lucronn/projects/8) item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, field `Source or dependency reference`, read back at `2026-11-03T22:52:39.567389+00:00`. Exact comment SHA256 `a4164a5bf2dc5edf986ed95aed7b26e8ace7419f3e576fbb8e49bae3dd319df1`; Project text SHA256 `78148627386a398901d82a8b2e5577c51cd2a32958e99c43c24513572415396a`. The compact Project index retains historical A/B/R6/current integration references and points to the full exact A goal/five todos/scope. Tracking synchronization is plan-only; no builder dispatch or live operation is authorized.


## PostgreSQL17 schema observation harness successor: planning checkpoint

Goal: Prove a bounded catalog-before-ledger protocol under an explicit ledger-only MAINTAIN capability in a disposable PostgreSQL17 adversarial harness; preserve the production catalog-only v2 collector and every release/readiness denial.

Canonical decision-complete plan: `docs/superpowers/plans/2026-11-03-workshop-schema-observation-harness.md`; dedicated task `docs/agents/tasks/2026-11-03-production-release/workshop-schema-observation-harness.json`; record `docs/agents/records/2026-11-03-workshop-schema-observation-harness.json`. Source base `ee57cd13a2f4e0a15d9e1212acfd1779451a4a91`. This successor leaves integrated catalog-only v2 (`5bf59c2`, gate `3a511f1`) intact and excludes `c51d637`. It proposes only a disconnected module plus pure tests and an opt-in disposable local PG17/C-sentinel harness. Separate test-only autodata_schema_probe has ledger SELECT+MAINTAIN, no ownership/memberships/writes; trusted NOLOGIN autodata_schema_owner owns the ledger. Strong lock before first snapshot, complete catalog validation before ledger bytes, actual positive sentinel controls, concurrent DDL barriers and server idle cleanup are required. MAINTAIN is explicit maintenance authority; production autodata_metrics and provisioning remain unchanged. No production helper, grant, collector integration, Docker/cloud/provider/DNS action or readiness claim. Independent coordinator review and pinned passing preflight remain required before any builder dispatch.

Prospective implementation allowlist: `infra/deploy/gce/schema_probe.py`, `infra/deploy/gce/test_schema_probe.py`, `infra/deploy/gce/test_schema_probe_pg17.py`, `infra/deploy/gce/testdata/schema_probe_sentinel.c`, `infra/deploy/gce/testdata/schema_probe_fixtures.sql`. DTO/browser/R6 and all existing runtime/operations implementation paths are excluded.

Concrete todo:

- [ ] Synchronize this exact harness goal, privilege decision, five-path implementation allowlist, tests and release limits in Issue186/Project8 and canonical documents; commit/push and pass pinned preflight before independent coordinator gate review.
- [ ] Add failing pure transport/state-machine tests and implement the disconnected fixed-SQL schema_probe module with lock-before-snapshot catalog validation, bounded ledger framing and rollback-only cleanup.
- [ ] Build the local-only PG17 harness and C sentinels with a non-owner SELECT+MAINTAIN probe role and trusted NOLOGIN ledger owner; demonstrate every sentinel fires in an intentional negative control before testing observer rejection.
- [ ] Run actual disposable PG17 safe/hostile relation, index, privilege, concurrent DDL, first-snapshot and abandoned-session cases; retain red/green receipts, hashes and cleanup proof without running application services or contacting providers.
- [ ] Run focused regressions, scope/diff and exact-base preflight; commit/push a coherent candidate for independent exact-SHA review, keeping production grants, collector integration, authenticated publication, services, deployment and cars.tk cutover behind later gates.

Tracking synchronized by live Issue186 body/comment6618084753 and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference` readback at `2026-11-03T23:26:27.924126+00:00`. Exact goal, five todos and five-path scope match the full issue body/comment; the compact Project index links that comment and retains historical DTO/A/B/R6 references, with its previous text preserved verbatim there. Dedicated record stores SHA256 readback hashes. Independent checkpoint review remains pending; synchronized tracking does not authorize a builder or live operation.

## R6 DTO120 receipt planning successor

Next prospective offline family is the [DTO120 receipt plan](2026-11-03-workshop-r6-dto120-receipts.md), source `99df69caaeb4d5ccf6d0ffbf0377fe6d5d872a3d` stacked on draft PR188; task `docs/agents/tasks/2026-11-03-production-release/r6-dto120-receipts.json`, record `docs/agents/records/2026-11-03-r6-dto120-receipts.json`. Tracking readback is synchronized in Issue186 comment6621102242 and Project8 Source/dependency index (879 characters; SHA256 f6b01dc0fe6cb7909d045b567505549909e71d4fe8853ac40d55f1a6d649e6b0); full predecessor text and every prior ID are retained. Exact committed preflight and independent gate review remain required. The three implementation paths remain unchanged. Closed40x3 DTO outcomes and fixed source-derived six-input/eleven-asset expectations add diagnostic consistency only; no verified cases, enabled profiles, CLI dispatch or true authority flags. Existing selector-work/history references and every paid/CI/source/SDK/TLS/supervisor/reviewer/staging gap remain. No implementation or release certification is authorized.


## Disconnected publisher and fixed host-check successor: planning checkpoint

Goal: Implement concrete disconnected publisher orchestration for fixed checkout, three image builds/pushes, SBOM/provenance verification and release artifact upload through injected executor/transports, plus a bounded fixed IAP host check; preserve all live execution and readiness denials.

Status: synchronized after live Issue186 comment6621071257 and matching Project8 readback. Source base `eddcf724028683dbb083191e4f8c42064b866bf0`. Canonical decision-complete plan: `docs/superpowers/plans/2026-11-03-workshop-publisher-transport.md`; dedicated task `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-transport.json`; record `docs/agents/records/2026-11-03-workshop-publisher-transport.json`. This additive successor preserves historical A/B/PG17 authority. It proposes concrete injected-executor checkout/build/push/SBOM/provenance/upload orchestration, deterministic inner ZIP production and one fixed IAP `deploy.sh check SHA` request. Implementation allowlist is cloud-ops.py, test_cloud_ops.py and this operations runbook. No workflow/runtime-check/deploy/grants/application edit or real image build/publication/transport/signature verification, cloud/provider/container execution or readiness promotion is authorized. Fake interfaces exercise the complete production operation order; authentic adapters remain separately gated. Actual GitHub artifact download compatibility and authenticated publication remain unverified; the historical B future_publication_gate is unchanged. Valid host replies remain unavailable with schema/services/runtime_evidence false. Owner identities and production/paid/browser acceptance remain separate requirements.

Concrete todo:

- [ ] Synchronize this exact publisher-orchestration/host-check goal, three-path allowlist, fixed checkout/build/push/evidence/upload operations, trust/DTOs and five todos in Issue186/Project8 and canonical documents; preserve prior Project index, commit/push and pass pinned preflight before independent coordinator gate review.
- [ ] Add failing fake-executor publisher sequencing tests and implement fixed source checkout, three digest-bound build/push operations and post-build registry identity verification; no real executable, network or credential discovery may run.
- [ ] Implement deterministic inner release.zip production, bounded SBOM/provenance publish/verify and artifact upload/readback through injected interfaces, with versioned independent transport/payload/member/manifest digests and adversarial identity/subject/signature fixtures.
- [ ] Add failing fixed IAP host-check tests and implement only the configured VM deploy.sh check SHA request with strict failed-readiness receipt handling; keep every mutation, schema/service/runtime readiness and CLI/workflow activation unavailable.
- [ ] Run focused B and unchanged A regressions, syntax, scope/diff and pinned preflight; commit/push coherent candidates for independent exact-SHA review, retaining red/green evidence and actual authentication/archive compatibility, owner/provider, staging and paid-product gates.

Tracking synchronization, committed pinned preflight and independent coordinator review remain required before implementation dispatch.


Publisher successor tracking readback: [Issue186 comment6621071257](https://github.com/lucronn/autodata/issues/186#issuecomment-6621071257), Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference`, verified `2026-11-04T02:40:50.163236+00:00`. Exact issue body/comment and Project index SHA256 hashes are retained in the dedicated publisher record. Prior Project index is preserved verbatim with hash in that comment. This is synchronized planning only; committed pinned preflight and independent coordinator review still precede any builder dispatch. No implementation or actual publication evidence exists.


## Migration-only publisher build argument correction: planning checkpoint

Goal: Correct only the disconnected publisher migration build argv to pass POSTGRES_IMAGE from the reviewed immutable manifest postgres reference before --file; preserve other-role argv, fake-only execution and every authority/readiness denial.

Status: synchronized after live Issue186 comment6621206696 and matching Project8 readback. Source publisher candidate `30cab10e548a3e078055b08447253ea90cc36bdc` (draft PR189). Dedicated plan `docs/superpowers/plans/2026-11-03-workshop-migration-build-arg.md`, task `docs/agents/tasks/2026-11-03-production-release/workshop-migration-build-arg.json`, record `docs/agents/records/2026-11-03-workshop-migration-build-arg.json`. This successor changes only the previously frozen build_migration vector: insert `--build-arg`, `POSTGRES_IMAGE=` plus the already validated immutable `manifest.images.postgres.reference` immediately before `--file`. API/ingestion argv remain exact originals. Future implementation allowlist is cloud-ops.py, test_cloud_ops.py and runbook; no Dockerfile/schema/workflow/runtime/PG17/R6 edit. Exact fake-argv/digest-propagation/ambient-ignore/no-default/invalid-reference-before-callback tests are required. No real build/PG17 compatibility/publication evidence is claimed; every existing simulation, live-operation and readiness denial remains. Historical publisher/PG17/R6 checkpoints are preserved; this correction cannot authorize their expansion.

Concrete todo:

- [ ] Synchronize this exact migration-only build-argument correction, three-path future scope and five todos in Issue186/Project8 and canonical documents, preserving the full prior Project index verbatim/hash; commit/push and pass pinned preflight before independent plan review and coordinator dispatch.
- [ ] Add failing exact fake-executor argv tests proving only build_migration receives --build-arg POSTGRES_IMAGE=<manifest.images.postgres.reference> immediately before --file while api/ingestion retain their existing complete argv.
- [ ] Implement the migration-only argument in cloud-ops.py from the already validated immutable manifest; reject missing/tag-only/malformed postgres references before callbacks and ignore all ambient/default POSTGRES_IMAGE or caller build-argument overrides.
- [ ] Run fake digest-propagation, no-fallback and unchanged publisher/host regressions, document that no Docker build or PostgreSQL17 runtime compatibility is proved, and retain every red/green/failure receipt outside the checkout.
- [ ] Run focused B/A suites, syntax, diff/scope and pinned preflight; commit/push a coherent three-path candidate for independent exact-SHA review without integrating, activating workflows, accessing credentials or running any real build/cloud/provider/host operation.

Commit/push, pinned preflight, independent exact-plan review and coordinator dispatch remain required before code.


Migration-only correction tracking: [Issue186 comment6621206696](https://github.com/lucronn/autodata/issues/186#issuecomment-6621206696), Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference`, verified `2026-11-04T02:50:39.563760+00:00`. The dedicated correction record stores exact body/comment/index hashes; the comment preserves the prior index verbatim/hash. This is plan-only synchronization; committed pinned preflight, independent exact-plan review and coordinator dispatch still precede implementation. No code or live execution is authorized by this checkpoint alone.


## Workshop authenticated publisher adapter successor: planning checkpoint

Goal: Build bounded real GitHub Actions artifact, registry/evidence and fixed IAP check adapters behind an independently controlled activation boundary, preserving all production and runtime readiness denials.

Independently approved pre-sync design SHA256 `2e17c0e153ead31ae71e67b535b5d1d46b3ec10f401b8c3883773fe8c1aa4142`. Source base `1a0e2740171e6e0a2aa0bbc97a36299ecbf2106c` (publisher candidate30cab10 plus migration correction1a0e274); branch `codex/workshop-authenticated-publisher-plan`. This is a docs-only planning checkpoint; independent exact-checkpoint review and coordinator dispatch remain required before any implementation. Issue186/Project8 serialization follows PG17 acquisition-overlay gate26989e1/receipt80d4a20; those separate authorities, blockers and queue references are preserved.

Plan: `docs/superpowers/plans/2026-11-03-workshop-authenticated-publisher.md`. Task: `docs/agents/tasks/2026-11-03-production-release/workshop-authenticated-publisher.json`. Record: `docs/agents/records/2026-11-03-workshop-authenticated-publisher.json`. Canonical refs: `docs/superpowers/plans/2026-11-03-workshop-publisher-transport.md`, `docs/superpowers/plans/2026-11-03-workshop-hosting.md`, `docs/operations/workshop-gcp.md`, `docs/architecture/infrastructure-and-dev.md`, `docs/superpowers/plans/2026-11-03-production-release-orchestration.md`.

Concrete actual-adapter scope: real bounded HTTPS/GitHub Actions official-toolkit upload/raw download/OCI registry/WIF/process/IAP adapters; build-once signed immutable candidate from approved source/config/four dependencies, independent signed complete-v1-manifest approval, then finalize without rebuild/copy/per-image evidence regeneration. Post-upload signed binding authenticates returned artifact ID, outer digest/length and exact originating run+attempt using fresh SDK UploadSession evidence and verified attempt-bearing signer URI; current run endpoint cannot establish artifact attempt. Preserve source/workflow SHA split, actual outer ZIP one release.zip vs unchanged inner two members, terminal digestMismatch/digest/expiry failure and older-attempt artifact rejection despite identical inner bytes. Carry independently supplied bounded rollback_manifest through candidate/finalize/verify/host revalidation with unchanged v1 invariants and canonical approved hash; never invent image/evidence hashes or silently rewrite approval. Migration POSTGRES_IMAGE remains explicit immutable reviewed input.

Future implementation allowlist (exact9 paths):
- `infra/deploy/gce/publisher_adapters.py`
- `infra/deploy/gce/publisher_artifact.mjs`
- `infra/deploy/gce/publisher-toolkit/package.json`
- `infra/deploy/gce/publisher-toolkit/package-lock.json`
- `infra/deploy/gce/test_publisher_adapters.py`
- `infra/deploy/gce/test_publisher_artifact.mjs`
- `infra/deploy/gce/test_release_workshop_contract.py`
- `.github/workflows/release-workshop.yml`
- `docs/operations/workshop-gcp.md`

Owner identities/protected environments/resources/WIF/IAM, toolkit/tool/action/Sigstore pins, approved origins and actual artifact compatibility semantics, upstream evidence policy, independent manifest-approval public key and fixed host-key/remote deadline proof are prerequisites to separately authorized staging. Code/tests may implement the real paths using injected fake/local process/transport/crypto dependencies; no live credentials or operation is authorized here. Existing production publish/deploy jobs and cloud CLI remain blocked; staging definitions retain unconditional precredential blockers. No schema/services/runtime_evidence readiness, provider/cloud/registry/host/build/upload/signing/staging/production activation, integration, deployment or owner policy installation is authorized by this planning checkpoint.

Concrete todo:
- [ ] After accepted migration review and root tracking release, synchronize the authenticated adapter-only goal, v3 identity/digest contracts, exact allowlist, five todos and activation exclusions across Issue186/Project8/canonical docs; commit/push, pin and independently review a machine-passing checkpoint before implementation.
- [ ] Implement bounded authenticated I/O, strict real-wire projections, separate workflow/source identity, official-toolkit single-file upload, original outer ZIP decoding and post-upload signed originating-attempt binding with terminal digestMismatch/expiry/digest/older-attempt rejection; retain every existing v2 and CLI denial.
- [ ] Implement actual build-once registry candidate push/SBOM/provenance verification, independent manifest approval and rebuild-free finalization plus separate fixed IAP check library, preserving independently supplied bounded v1 rollback_manifest through every phase and migration POSTGRES_IMAGE, credential/issuer/audience separation, pinned trust/tooling and bounded cleanup; reject candidate/approved-manifest/rollback mismatch without rewriting approval.
- [ ] Add adversarial fake/local contract tests and a dormant protected staging workflow definition with unconditional precredential blocker; preserve unchanged production jobs, false readiness and all existing application/schema/deploy authority boundaries.
- [ ] Run focused regressions, syntax/scope/diff and pinned preflight; commit/push coherent candidates for independent exact-SHA review, document missing owner/tool/origin/host/staging evidence and stop before any activation or live operation until a separate synchronized gate authorizes it.


Tracking readback: [issuecomment-6621425159](https://github.com/lucronn/autodata/issues/186#issuecomment-6621425159), Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference`, verified `2026-11-04T03:06:38.051955+00:00`. Exact body/comment/Project/prior-index hashes are in the dedicated synchronized record. Full predecessor Project index SHA256 `4e26f3831956fb10f26a64e5b791e27f502a35e3ead19015622e118d22dfec20` is preserved verbatim in that comment. This synchronizes planning only; committed full-SHA preflight, independent exact-checkpoint review and coordinator dispatch still precede implementation. No staging or production activation.


## Isolated staging bare-resource bootstrap M1: synchronized planning checkpoint

Goal: Create and read back only owner-approved isolated staging IPv4 address, empty persistent data disk and bare VM; preserve all application, deployment and production denials.

Canonical plan: `docs/superpowers/plans/2026-11-04-workshop-staging-lifecycle.md`; task `docs/agents/tasks/2026-11-03-production-release/workshop-staging-bootstrap.json`; record `docs/agents/records/2026-11-04-workshop-staging-bootstrap.json`; preservation/evidence `docs/agents/records/2026-11-04-workshop-staging-bootstrap-evidence.json`. Source root `eddcf724028683dbb083191e4f8c42064b866bf0`; independently reviewed corrected draft `fb0c6f7a92b2580ae7bc993f827cfc2596a32743`.

Status: `synchronized` after live [Issue186 detail6622232881](https://github.com/lucronn/autodata/issues/186#issuecomment-6622232881) and [Project8](https://github.com/users/lucronn/projects/8) readback at `2026-11-04T04:04:56.410962+00:00`. Commit/push, full-SHA pinned preflight, independent exact-checkpoint review and fresh coordinator dispatch still precede implementation. Synchronization does not authorize cloud or host operations.

Exact prospective implementation allowlist:

- `infra/deploy/gce/cloud-bootstrap.sh`
- `infra/deploy/gce/staging_bootstrap.py`
- `infra/deploy/gce/staging-bootstrap.schema.json`
- `infra/deploy/gce/test_staging_bootstrap.py`

Only dedicated staging address+empty data disk+bare VM against approved preexisting VPC/IAM/APIs/registry. Strict owner approval, inherited metadata/image/network/effective-policy readback, fixed Compute GET/three POST bodies, deterministic requestId, ownership/idempotency, bounds and redacted receipts are defined in the plan. Only exact default0.0.0.0/0 via default-internet-gateway is exempt from Docker overlap checking; selected subnet/additional destinations must be disjoint, and extra routes remain denied. No IAM mutation, package install, disk format, secret delivery, application startup, production apply or readiness authority. Actual owner-selected GCP/billing/region/pins/staging-origin inputs and separate live authorization remain mandatory. Publisher/schema contracts and separately reviewed installation/startup/recovery gates are still required.

Concrete todo:

- [ ] Synchronize the exact bare-resource goal, four-file allowlist, approval/request/network/receipt contract and concrete todo across Issue186/Project8 and canonical documents; preserve current PG/JS index/detail/pins verbatim with hashes, commit/push and pass full-SHA pinned preflight before independent checkpoint review.
- [ ] After independent exact-checkpoint review and fresh coordinator dispatch, add offline failing tests for strict approval/token boundaries, exact request inventory, default-route exception and disjoint-subnet acceptance, overlapping-subnet/custom-next-hop rejection, ownership/idempotency, timeout/cancellation and redaction.
- [ ] Implement only the four allowlisted bootstrap files for the fixed staging-only Compute GET and three POST operations, approved resource identity readback and bounded retained-resource failure receipts; keep production apply, IAM mutation, installation, formatting, secrets, application startup and readiness unavailable.
- [ ] Run offline staging-bootstrap and existing host/cloud regression suites, syntax/scope/diff checks and pinned preflight; commit/push a coherent candidate and obtain independent exact-SHA review before integration or live use.
- [ ] Keep all cloud execution blocked pending separate owner authorization of selected GCP projects/billing/region/VPC/IAM/pins/staging origin and concrete reviewed scripts; keep host install/readiness/recovery behind separate publisher/schema-dependent gates and preserve cars.tk/production blockers.

Preservation: then-current full PG CapAdd Project index SHA256 `a67fb47f7973811904663fd8bba35a5c8ce6ad6164eb896adae83ea4dd39100d`, detail6622201950/pin6622210398, and prior JS Project index/detail6622115738/pin6622126651 remain verbatim with individual hashes in canonical evidence and the full synchronization comment. PG gate `cde9652c0e3dce9a9083540d15cb25b3682f144d` and JS gate `d105f8ae0747faa4bf4c6254e2dd1cd45ad0a830` retain their own review/dispatch/denial boundaries; no prior status is superseded.

Pinned M1 checkpoint `52653deef3754972230801ac260875fe92e1a403` is pushed on `codex/workshop-staging-lifecycle-plan`; full-SHA preflight returned `{"status":"synchronized","errors":[]}`, exit0. [Pin/readback receipt6622247097](https://github.com/lucronn/autodata/issues/186#issuecomment-6622247097) and canonical evidence record Issue/Project/comment hashes at `2026-11-04T04:05:59.945032+00:00`. Independent exact-checkpoint review and fresh coordinator dispatch remain pending; implementation and cloud execution are unauthorized.


## Staging boot attachment deviceName: synchronized corrective planning checkpoint

Goal: Explicitly select the staging VM boot attachment deviceName and make the offline Compute fake distinguish attachment names from disk resource names, preserving strict readback and every existing authority boundary.

Plan `docs/superpowers/plans/2026-11-04-workshop-staging-boot-device.md`; task `docs/agents/tasks/2026-11-03-production-release/workshop-staging-boot-device.json`; record `docs/agents/records/2026-11-04-workshop-staging-boot-device.json`; evidence `docs/agents/records/2026-11-04-workshop-staging-boot-device-evidence.json`. Rejected candidate `188d6e66a3edff53bb84548d78876f8c98f6aec0`; independently reviewed local draft `b31de33a7907bf295d4c69c8df13a2b15ebabd53` PASS via coordinator.

Status: `synchronized` after [Issue186 detail6622382607](https://github.com/lucronn/autodata/issues/186#issuecomment-6622382607) and [Project8](https://github.com/users/lucronn/projects/8) readback at `2026-11-04T04:15:55.867157+00:00`. Commit/push, full-SHA pinned preflight, independent exact-checkpoint review and fresh root dispatch still precede code. No implementation or cloud operation is authorized now.

Exact prospective implementation allowlist:

- `infra/deploy/gce/staging_bootstrap.py`
- `infra/deploy/gce/test_staging_bootstrap.py`

Narrow request amendment: select boot `AttachedDisk.deviceName=<instance>-boot` explicitly as a sibling of `initializeParams`; independently retain `initializeParams.diskName=<instance>-boot` for the disk resource. Preserve strict attachment-name/resource-ID/image readback and data deviceName `autodata-data`. Make fake echo explicit attachment name and choose representative `persistent-disk-0` when omitted, never derive it from diskName. Original omission must fail strict readback after3POSTs/resources retained; exact explicit request success and observed-name drift rejection are required. No launcher/schema/config/token/network/receipt/budget/authority change. Source188d6e6 remains rejected pending exact correction review; no historical gate is retroactive acceptance.

Concrete todo:

- [ ] After PG releases the serialized tracking slot and coordinator approves this draft, synchronize the exact boot-attachment correction goal, explicit POST amendment, two-file allowlist, regression cases and todo across Issue186/Project8 and canonical plan/task/record/notes; preserve then-current full PG/JS index/detail/pins verbatim with hashes, commit/push and pass full-SHA preflight before independent exact-checkpoint review.
- [ ] Obtain independent review of that exact new checkpoint and fresh root dispatch before implementation; preserve rejected source `188d6e66a3edff53bb84548d78876f8c98f6aec0` and the prior M1 gate/receipt as distinct historical records without retrospective acceptance.
- [ ] Change the fake's omitted-name behavior and add the exact request/default/drift regressions first; demonstrate a red complete-run failure on the uncorrected request, with all three POSTs and retained resources, using only intercepted transports.
- [ ] Add only the explicit boot AttachedDisk.deviceName sibling field in staging_bootstrap.py; keep strict readback and all request/approval/config/FD3/network/receipt/authority boundaries unchanged; run focused bootstrap plus existing host/cloud regressions, syntax and diff/scope checks.
- [ ] Commit/push the exact two-file candidate, retain red/green logs and independently review its full SHA before integration; no credentials/cloud/resource operations, installation, formatting, host startup, readiness, cars.tk or production authority follows from simulated success.

Preservation: full then-current PG offline Project index SHA256 `8e678c075d383d11fa9a63e3df05040a3b8e721e068d0c38e590728b6d009aa1`, detail6622351785/pin6622361427, and Stage0/staging/older PG/JS index/detail/pin texts are retained verbatim with individual SHA256 in canonical evidence and the exact preserved-comment references in the synchronization detail. Their statuses/independent review/dispatch/denial boundaries remain unchanged. No credentials/cloud/Docker/host/provider/DNS/runtime action or readiness/production claim occurs on this documentation turn.


## Staging M2A inert-install synchronized planning checkpoint

Goal: Install only an owner-accepted authenticated release manifest and its exact migration runner/tree into a fixed root-owned staging release directory, without formatting disks, selecting a running release, delivering secrets or starting services.

Plan `docs/superpowers/plans/2026-11-04-workshop-staging-m2-host-install.md`; record `docs/agents/records/2026-11-04-workshop-staging-m2-host-install.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-staging-m2-host-install.json`; evidence `docs/agents/records/2026-11-04-workshop-staging-m2-host-install-evidence.json`. Source independently reviewed M1 candidate `ef536cc24478424efc3cc084425322cfb8056145`; independently approved corrected draft `f1558d526d87b9d48180f00be41835c65d9944fc` PASS via coordinator. No source merge/rebase is implied.

Exact prospective implementation allowlist:

- `infra/deploy/gce/deploy.sh`
- `infra/deploy/gce/host_install.py`
- `infra/deploy/gce/test_host_install.py`

Fixed root-admin approval + local accepted inbox only: validate exact manifest/runner/SQL bytes with unchanged runtime validator; protect standard root-owned non-group/other-writable parents (0755 accepted), exact private0700 subtree; require already-approved mounted disk and tmpfs; bounded descriptor copy/no-replace inert install and redacted receipt. No formatting/mounting, remote ingress, package/unit changes, current-release selection, image pull, secrets or service startup. Publisher authentication and owner acceptance workflow remain external live-use dependencies; hashes never manufacture publisher authority. No activation/readiness/cloud authorization.

Concrete todo:

- [ ] Independently review this M2A split, exact three-file scope, trusted owner-acceptance boundary, immutable file/input/receipt contract and no-replace/cleanup primitives; synchronize goal/todo/references in Issue186/Project8/canonical docs with full then-current history preservation, commit/push and full-SHA preflight before builder dispatch.
- [ ] Obtain independent exact synchronized-checkpoint review and fresh root dispatch; establish actual authenticated publisher and separate mounted-disk/tool prerequisites before any later live installation, without inventing a verifier or owner/cloud values.
- [ ] Add failing fake-probe and temporary-inode tests for approval/publisher/mount/lock/inventory/no-replace/fault/redaction and reboot fail-closed invariants; then implement only deploy.sh, host_install.py and test_host_install.py for inert release-material installation.
- [ ] Run focused host-install tests plus existing host/cloud/bootstrap regressions, syntax/diff/scope and pinned preflight; commit/push a coherent exact candidate for independent review, preserving all startup/readiness/cloud/secret/production denials.
- [ ] Require separate decision-complete gates for authenticated remote ingress/private secret delivery, host packages/guard/units, image pull, start/schema/readiness and minimum recovery; no one may treat M2A success as completion of full M2 or live-operation authorization.

Independent exact synchronized-checkpoint review and fresh root dispatch REQUIRED before any implementation. No cloud/Docker/credential/secret/runtime action. All prior Stage1A/Stage0/staging/PG/JS authorities/statuses/denials unchanged.

Status: `synchronized` after [Issue186 detail6622589651](https://github.com/lucronn/autodata/issues/186#issuecomment-6622589651) and Project8 exact readback at `2026-11-04T04:30:30.706329+00:00`. Full then-current Project index, entire prior Issue body and all111 historical comment bodies are retained verbatim with SHA256 in `docs/agents/records/2026-11-04-workshop-staging-m2-host-install-evidence.json` and verified unchanged. Independent exact-checkpoint review and fresh root dispatch remain pending. This docs-only checkpoint authorizes no implementation or live action.


## Verified docs-only integration tracking synchronization

This additive receipt supersedes only the local-draft tracking statements above. Coordinator explicitly released PG writer slot. Independent local draft review PASS pinned plan SHA256 ea42fcac66cc397482f985be8a26e6e73dc1fc22c0b4e008eec742d4e384e553 / bundle manifest ca34e3e8be70bac131aabf7b600032a9b4531f0d87b85f5a8fa5f75f03c94a63. https://github.com/lucronn/autodata/issues/186#issuecomment-6622915925 read back at 2026-11-04T04:54:35.010852+00:00. Entire current Issue body/all115 prior comment bodies and full current PG Project index preserved verbatim+hash in `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration-evidence.json`; independent API readback confirmed Issue/prior comments unchanged. PG gate74dfe57/receiptd662cb0, Stage1A and M2A details/pins/statuses/denials preserved. Project current index SHA256 20ab190a8c0e78eb994b5e99ba133e7df2cdebd1258f29c0680d0cb32422407c.

Record/task status synchronized after actual readback. Full committed checkpoint/preflight, independent exact-checkpoint review and fresh coordinator dispatch remain required before any ordered integration. No implementation merge, provider, cloud, runtime, staging activation or deployment occurred. This synchronization alone authorizes none of them.

Goal: Integrate the three independently reviewed dormant R6, publisher and staging leaf histories into one byte-pinned offline candidate without live activation.

Refs: `docs/superpowers/plans/2026-11-04-workshop-reviewed-leaves-integration.md`, `docs/agents/specs/2026-11-04-workshop-reviewed-leaves-integration.md`, `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration.json`, `docs/agents/tasks/2026-11-03-production-release/workshop-reviewed-leaves-integration.json`, `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration-evidence.json`

Concrete todo:
- [ ] Obtain independent local-draft review; keep status unsynchronized and integration blocked until PG releases the serialized tracking slot.
- [ ] After slot release, preserve then-current Issue186/Project8 texts and hashes; synchronize exact source tuple, plan/spec/record/task/canonical notes and concrete todo; commit/push the docs-only checkpoint and pass full-SHA preflight.
- [ ] Obtain independent exact synchronized-checkpoint review and fresh coordinator code-only dispatch; create an isolated feature worktree/branch from the checkpoint.
- [ ] Merge exact R6, publisher and staging leaf histories in that deterministic order, resolving only five approved documentation/tracking conflicts and preserving all 23 implementation blob pins and historical additions.
- [ ] Run combined offline Python/Node/preflight/syntax/scope/authority checks after each milestone; commit and promptly push validated coherent merges to the assigned branch.
- [ ] Obtain independent exact-head review, freeze the combined candidate SHA and retain results; obtain separate gates before fixture/CI reruns or any live activation.


### Exact committed integration checkpoint pin

Gate `2728ac1acaf173d6f244e200e584dac7922fda1d` pushed on `codex/workshop-reviewed-leaves-integration-plan`; canonical preflight at that full SHA exit0, `status: synchronized`, `errors: []`, stderr empty. Pin https://github.com/lucronn/autodata/issues/186#issuecomment-6622928529 read back 2026-11-04T04:55:31.706681+00:00. Final Project index SHA256 `578438413fa8b6738efbf960c46e55ff7b6623772fac191b697af862d57bf0d2` (934 characters), containing every explicit predecessor reference ID including full PG gate74dfe57, receiptd662cb0 and M2A gate9a2b57d0. Complete Issue body/all115 predecessor bodies unchanged on fresh paginated readback. Evidence retains exact prior/full current index, pin hash, command/stdout/stderr and readback.

Independent exact-checkpoint review and fresh coordinator code-only dispatch remain required before any ordered integration. No code merge or activation occurred. Receipt commit records this gate without changing its pinned base.
