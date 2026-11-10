# AutoData GitHub Operating Model

## Repository workflow

AutoData uses trunk-based development with a protected `master` branch (the repository's current default branch):

- Work is performed on short-lived branches named `automation/<topic>` or an equivalent team convention.
- Pull requests are small, linked to a GitHub Issue, and use squash merge.
- `master` requires successful configured CI, an independent review of the exact candidate SHA, no unresolved blocking review thread, and every approval that live branch protection requires. A CODEOWNERS mapping identifies ownership and routes review; it does not by itself require a GitHub approval from the PR author.
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

### Single-maintainer Workshop review

For a bounded Workshop app or documentation PR in this single-maintainer
repository, a read-only AI reviewer separate from the implementer may satisfy
the repository's independent-review decision. The retained review must identify
the exact head SHA and base, inspect the diff against the linked plan and tests,
record Critical/Important/Minor findings and a merge verdict, and leave no
unresolved Critical or Important finding. A changed head requires a fresh review
of the changed range. The PR or its linked verification document points to the
review evidence and exact-head CI. The implementer's own assessment is not an
independent review, and an AI verdict is never described as a GitHub approval.

`.github/CODEOWNERS` remains the source of path ownership and review routing.
When the only eligible CODEOWNER is also the PR author, the repository does not
wait for a self-authored GitHub approval that GitHub cannot record. If live
branch protection requires an approving review or code-owner approval, that
GitHub requirement still blocks merge until satisfied; no automation bypasses
it or changes protection settings to make a PR mergeable. The same applies to
failed/pending required checks and blocking review threads. Payment, grant,
authentication, schema, source-rights, security, and production changes retain
their own stronger task-specific gates; this paragraph grants no acceptance or
deployment authority for them.

The autonomous release controller still requires its eight independent
decisions and its designated release-agent authority for controller-managed
runs. A Codex-managed PR may use this documented exact-head review and GitHub
checks without claiming to have passed a release-controller run it did not
execute. If one PR is waiting on a genuine gate, record the blocker and take
the next safe, independently tracked Workshop app task; unchanged PR polling
alone is not development progress. Changing this review rule requires direct
repository-owner authorization, exact-head independent review, and required CI.

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


## Task64 GCE CI coverage — synchronized planning checkpoint

Status=synchronized; planning_status=synchronized; tracking_status=synchronized. Planning parent 4fe83b29b86411d104b1edb203e9b26fde67ad02 / tree 9364c8442e27bbcd0a38c7ffafceb5c24b7736aa. Current implementation allowlist=[]; all authorities=false; accepted_case_credit=0; accepted_new_case_credit=0; verified_case_ids=[]; release_state=unverified.

Goal: Include every infra/deploy/gce change in both push and pull_request Autonomous Verification triggers and run the complete required-mode GCE delivery suite under its protected numeric UID/GID1000 fixture contract in the existing main verification job, with structural stdlib governance regressions and no deployment or acceptance authority.

Plan: `docs/superpowers/plans/2026-11-05-workshop-gce-ci-coverage.md`. Spec: `docs/agents/specs/2026-11-05-workshop-gce-ci-coverage.json`. Record: `docs/agents/records/2026-11-05-workshop-gce-ci-coverage.json`. Task: `docs/agents/tasks/2026-11-03-production-release/workshop-gce-ci-coverage.json`. Verification: `docs/verification/2026-11-05-workshop-gce-ci-coverage.md`. Tracking: https://github.com/lucronn/autodata/issues/186 and https://github.com/users/lucronn/projects/8 (root sole writer; tracking synchronized by verified saved readback).

Concrete todo:

- [ ] Independently review the approved Task64 proposal/review, exact Task62 source4fe83b29b86411d104b1edb203e9b26fde67ad02/tree9364c8442e27bbcd0a38c7ffafceb5c24b7736aa, eight gate paths/two implementation paths and UID1000 executable/environment contract; preserve all prior queue/root/history bytes and credits0.
- [ ] Synchronize this literal goal, six todos, exact eight/two-path scopes and canonical references in Issue186/Project8 using root-owned before/after preservation readbacks; only then set standalone/nested records synchronized, commit/push the planning-only checkpoint, externally seal its actual SHA/tree, pass both exact-checkpoint preflights errors=[], obtain independent checkpoint review and explicit two-path dispatch.
- [ ] Write failing structural stdlib governance tests proving separate push and pull_request GCE coverage, required complete suite/UID1000 temp ownership/flag/order and complete reviewed script identity, and negative mutation rejection; add only the two GCE filters and the preflighted sanitized numeric-identity test step without changing existing jobs, permissions, timeout or protected source.
- [ ] Run focused governance and complete required-mode GCE tests with actual executable/identity/Compose/tempfile readbacks, ordinary developer regressions and exact two-path/protected integrity checks; retain raw failures and do not weaken or skip wrapper/Unicode transport requirements.
- [ ] Commit and promptly push small coherent validated milestones to the assigned feature branch, obtain independent exact-source review, then retain fresh source-push and actual pull_request checkout SHA/tree/workflow/job receipts for all three required jobs including GCE and live Compose; manual dispatch remains supplemental.
- [ ] Synchronize verified source and honest CI coverage evidence while preserving Task61 actual-PR, owner/host/immutable-generation/activation/staging/restore/provider/identity/payment/browser/DNS release limits and acceptance credits0; no merge, deployment, publication or live-sales authority.

Exact future implementation scope: `.github/workflows/autonomous-verification.yml`, `scripts/dev/test_repository_governance.py` only. Both event filters gain GCE coverage; one mandatory main-job suite runs after dependencies and before Compose under preflighted sanitized UID/GID1000 using sudo-n/setpriv/clear-groups/env-i. Fixed executable paths/system Python alias and owned temp HOME/TMPDIR are explicit runner prerequisites. Governance uses stdlib bounded structural scopes/negative mutations. Existing jobs/permissions/timeouts and protected GCE/application/policy/Compose paths remain intact.

Task62 source review and five-lane fixture PASS are coordinator-reported source evidence, not Actions coverage. Task61 CI audit PASS_CI_AUDIT: source-push41977565019 and actual-PR41977907070 succeeded all three jobs/live Compose at source e200cfd6b473e9231844d133f63244f3a627a356/tree269bd94410df22a8718f005c1d0b0142238cdafc; PR checkout97d4d975efdb396fafa91e27c92f5a30b3a4fcc8 has equal tree. Audit /home/corp/autodata-evidence/task61-final-ci-audit/REPORT.json SHA256486e069a4a08587853b84d89a41b403ee2e95057482b453493f5166b42915681. Qualifications:210 ingestion skips in each CI run, local Go roots TestWorkshopCommercePythonIntegration/TestWorkshopPurchaseConfigAuthorityIntegration skipped, so no whole-workflow-zero-skips claim. Developer/R3/Node/DTO skips0; DTO120 remains inventory only with observer/containment/trace-admission blockers, acceptance credit0. This is Task61 evidence, not fresh Task62/64 coverage. Task62 final local source report /home/corp/autodata-evidence/task62-config-delivery-code/FINAL-SOURCE-REPORT.json SHA256d0803f8645eb08e01e5b0726b9629ef00b13f42c77c1b808f010eda138a5a802 records local/source/owned-fixture PASS at source4fe83b29b86411d104b1edb203e9b26fde67ad02/tree9364c8442e27bbcd0a38c7ffafceb5c24b7736aa; coordinator confirms complete local developer604 PASS. Supplemental workflow_dispatch41979473005 remains pending; actual source-push/pull_request GCE CI coverage remains absent. These local results provide no CI, deployment or acceptance credit.  GCE source-push/PR CI gap remains open until this separately gated change produces fresh actual event receipts. Task60 publication and external Task63 generation design retain ownership; no absent queue history is reconstructed. Root has independently reviewed the corrected draft and synchronized literal tracking. Planning checkpoint commit/push, external actual SHA/tree seal, both pinned preflights, independent checkpoint review and explicit dispatch remain required. No implementation, CI success, merge/deployment/DNS or authentic acceptance is authorized here.

Revision after independent draft REVISE: complete normalized GCE run script is SHA256-bound to literal `5adc3b0b3b56c75f8df1faed2dd461a71ac37c3622b973af185baf99941e3502` (dedent10, strip trailing LF blank lines, append one LF; UTF-8). The governance guard must reject any differing script bytes, including early exit/conditional bypass, missing private temp mkdir/numeric chown and wrong ownership. Expected hash is independently reviewed, never derived from workflow. Expanded mutation evidence and renewed independent draft review remain required.


## Root tracking readback — synchronized planning checkpoint

Root synchronized the exact goal, six literal todos, eight gate paths and two future implementation paths in [Issue186 comment6651421313](https://github.com/lucronn/autodata/issues/186#issuecomment-6651421313) and Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4. Before snapshot `/home/corp/autodata-evidence/task64-gce-ci-coverage-design/BEFORE-TRACKING-FINAL.json` SHA2564119eec2face30558869172fb686c4480de3fc16dd878b10bc7d57197bbe1b41; after `/home/corp/autodata-evidence/task64-gce-ci-coverage-design/AFTER-TRACKING.json` SHA25657313623e26513af3d6d6fc699290a8df8202a5bf9357c0b804b76364204a574. Preservation PASS9 `/home/corp/autodata-evidence/task64-gce-ci-coverage-design/TRACKING-VERIFY.json` SHA256b060c5d63dfcd6d4ee13816bec1121543cb78bb3f194d4fe5b1b6005f5d4680c verifies unchanged Issue body/prior comments/other Project fields and prior Source archived verbatim. Corrected exact-draft independent review PASS54 `/home/corp/autodata-evidence/task64-gate-draft-independent/REPORT-RECHECK.json` SHA2561ec2ac5d9d42053fa4cf4d99f7a74be0dbb105363555ce44044a4e7e00a5bf30. This planning lane verified saved literal/preservation readbacks and performed no tracking write. Posted comment retains reviewed draft wording as history; records now reflect completed tracking synchronization.

Status/planning/tracking=synchronized. Current implementation allowlist=[]; all authorities=false; accepted_case_credit=0; accepted_new_case_credit=0; verified_case_ids=[]; release_state=unverified. Checkpoint actual SHA/tree is sealed externally after commit/push; standalone+nested exact-checkpoint preflight, independent checkpoint review and explicit two-path dispatch remain required. No source implementation, hosted CI success, publication/deployment or authentic acceptance is authorized. Historical Task61/Task62 evidence retains its recorded qualification.

## Task65: CI binding and deterministic installer fixture checkpoint

Goal: Restore verification of the unchanged Task64 workflow by rebinding only the disabled R6 planning profile to its exact current workflow digest and ensuring the pre-promotion replacement fixture reliably exercises identity-based cleanup refusal, with every authority and acceptance credit unchanged.

Synchronized planning checkpoint on exact Task64 source `c7d1bba38c80288ab0f2e0c2a8b86e2eb5c35e4b`, tree `2119fb9d394994472b20243cfbbebe0cbba7ae25`. Plan `docs/superpowers/plans/2026-11-05-workshop-ci-binding-fixtures.md`; spec `docs/agents/specs/2026-11-05-workshop-ci-binding-fixtures.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-ci-binding-fixtures.json`; standalone record `docs/agents/records/2026-11-05-workshop-ci-binding-fixtures.json`; evidence `docs/verification/2026-11-05-workshop-ci-binding-fixtures.md`. Issue https://github.com/lucronn/autodata/issues/186#issuecomment-6651645549; Project https://github.com/users/lucronn/projects/8 / item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4.

Eight coordinator gate paths and exact two future implementation paths are enumerated in plan/spec/task/record. Future R6 correction changes only `product_evidence.ci_profile.workflow_sha256` from `b7dc37359faea4cdaff29ce7b0460d2f5d289ad7d3ae4c2c0c788a8992556e4d` to `b9ccf5f8c8fc974d113f0461871e9288e30a1a61ddeff6fc67cfd8a6fb3e7418`; expected8727 bytes/mode100644/SHA256 `09562c3da23fbf1283c5276023967c97ab51d53b1133c49ddf7cd6b6f4b87be7`/Git blob `132307774cb0baabb1f320b0e2ea7bde3aae9526`. R6 itself remains byte-identical during this checkpoint. Future fixture change retains an open original inode through cleanup and asserts distinct identities plus code6/recovery_incomplete/incomplete/no promotion/preserved injection.

Task64 push41981562383 and actual PR41981617643 main failed at unchanged R6 workflow binding; GCE/live Compose skipped; R3/DTO passed. Task62 supplemental manual41979473005 passed all3 including live Compose, remains supplemental. Original R6 digest/raw bytes and Task64 failures remain historical; all existing queue/root/task/history entries remain unchanged. No inherited CI green.

Todo:

- [ ] Independently review Task64 exact source, unchanged whole-workflow trusted-loader/browser contracts, red receipts and the two-path correction; preserve historical evidence and every authority/credit limit.
- [ ] Synchronize this goal, six todos, eight gate paths, two implementation paths, exact old/new R6 metadata and canonical refs in Issue186/Project8; commit/push the checkpoint, seal its actual SHA/tree, pass both exact-base preflights and obtain independent checkpoint review before dispatch.
- [ ] Retain original browser-binding and trusted-boundary failures; replace only the single R6 ASCII workflow hash with the exact reviewed current-workflow digest, prove every other R6 byte/field unchanged and expected output hash/blob/length, run focused existing binding/trusted-boundary/disabled CLI tests, and commit/push the independently reviewable one-field milestone.
- [ ] Retain exact-wrapper inode-reuse red evidence; pin the temporary manifest with an open descriptor through installer cleanup, assert distinct identities and existing6/no-commit/preserved-injected-file outcomes, run focused repeats on disk-backed/tmpfs storage and host-install verification, then commit/push the fixture-only milestone.
- [ ] Run complete release-acceptance/browser/developer/governance checks and required-mode GCE under the unchanged UID/GID1000 wrapper, check exact two-path/protected integrity at final source, obtain independent exact-source review and retain fresh source-push plus actual-PR receipts for all three jobs/GCE/live Compose.
- [ ] Append honest exact-source local/CI results and retain the prior R6 digest/Task64 failures as historical evidence; preserve all disabled profiles, trusted-loader boundaries, owner/staging/activation/payment/browser/provider/DNS blockers, credits0 and every release authority false; perform no merge/deployment/publication.

Current implementation allowlist=[]; independent checkpoint review and explicit two-path dispatch required after actual checkpoint seal and standalone/nested exact-base preflights. Every authority false; credits0; verified_case_ids=[]; release_state=unverified. Preserve disabled profiles/trusted-loader contract and all owner/staging/activation/payment/browser/provider/DNS blockers. No merge/deployment/publication.


## Task69 release essentials integration (tracking synchronized)

Goal: Integrate the reviewed Task58 supervisor patch and private-material helper into the corrected release candidate, finish the remaining Vercel DNS plan corrections, and verify the combined source without runtime or release operations.

Plan: [Task69 release essentials integration](../superpowers/plans/2026-11-05-workshop-release-essentials-integration.md). Issue: https://github.com/lucronn/autodata/issues/186; Project: https://github.com/users/lucronn/projects/8. Base `3421df91184e4a428450ee089a628ed144c05b15`; adopt exactly six reviewed technical files and the two remaining PR272 plan corrections listed in the plan. PR225 historical gate remains referenced at `ec93551a39c157ee4f5b428e248e8fd766f68dee`; no wholesale historical gate import. Tracking synchronized after root-confirmed Issue186 comment6652770502 exact-body readback and Project8 Source readback (1016 bytes, previous prefix preserved), status In Progress. Implementation blocked until committed synchronized checkpoint, canonical preflight and root checkpoint review/dispatch. Credits0/verified IDs[]; no runtime, release, DNS or deployment operations.

TODO:

- [ ] Synchronize Issue186/Project8, the Task69 plan and canonical operating-model entry; commit the planning checkpoint and pass canonical preflight at its exact SHA before implementation.
- [ ] Adopt the exact four Task58 files and two reviewed private-material helper files, and apply only the two remaining Vercel DNS plan corrections while preserving all other source and historical gates.
- [ ] Run focused supervisor, private-material, governance and workflow-binding checks plus exact byte/scope verification; commit and promptly push the validated candidate for independent review and full hosted CI.
- [ ] Retain exact candidate review and fresh source-push and actual-PR three-job CI evidence, record remaining blockers and keep credits0, verified IDs[] and runtime/release authorities disabled.

Root confirmed Issue186 [comment6652770502](https://github.com/lucronn/autodata/issues/186#issuecomment-6652770502) exact-body readback PASS and Project8 Source appended-pointer readback PASS (1016 bytes, prior prefix preserved), status In Progress. Recorded at `2026-11-05T07:55:25.114444+00:00`. This tracking synchronization grants no implementation or runtime authority.


## CI cost: feature-push verification deduplication — synchronized planning

Goal: Avoid duplicate Autonomous Verification suites for feature-branch pushes while retaining pull_request verification and push verification on master.

Issue: https://github.com/lucronn/autodata/issues/315; Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhGR-0Q`. Plan: `docs/superpowers/plans/2026-11-05-ci-cost-trigger-deduplication.md`. Machine record: `docs/agents/records/2026-11-05-ci-cost-trigger-deduplication.json`. Status: synchronized. Amended docs-only checkpoint supersedes `263d408c07e55f1bed287e32dc8444a3fbff5f4d`; exact new SHA is sealed in Issue #315 after commit/push and required preflight.

Todo:

- [ ] Re-run the exact-checkpoint planning preflight before implementation.
- [ ] Add focused governance regression coverage for feature push, master push, pull_request and manual dispatch.
- [ ] Limit push to master while preserving all existing paths, jobs and required checks.
- [ ] Rebind only product_evidence.ci_profile.workflow_sha256 in the disabled R6 task to the exact master-only-push workflow digest; preserve every other byte and all disabled authorities.
- [ ] Run structural/workflow-binding checks, inspect unchanged job definitions and push a validated implementation milestone for independent review and actual PR CI evidence.
- [ ] Synchronize exact-source evidence and remaining blockers in canonical docs and GitHub; retain master-push verification as pending until available.

Exact future implementation paths: `.github/workflows/autonomous-verification.yml`, `scripts/dev/test_repository_governance.py`, `docs/agents/tasks/2026-11-03-production-release/r6-release.json`. Only the R6 field `product_evidence.ci_profile.workflow_sha256` may change in the third path: old `3c54e7ba0613d1cd3a78819eede4915b1d268ffd904df83b2c034d914dca10e6` to new `de53b6f0552165d4ce07549d07e5cb38999995befe9369e0d030fe7d6beb543d`. Preserve every other R6 byte and disabled profile/release-authority semantic. Expected result8727 bytes/SHA256 `136619978274a7b541651ac7e9ed4cac58bc10cf826358d6f658c0c2f813cb78`/Git blob `e9f2d5c4784212d9d922628fc84c4873d89dce99`. Full-workflow binding consumers remain unchanged. Baseline binding/trusted-boundary8 PASS; builder-reported trigger-only digest mismatch is expected red evidence. Final committed source must pass binding/trusted-boundary and focused governance tests with exact byte proofs; see plan for command and evidence details. Preserve every workflow job/check/path filter and manual/PR events. This planning lane performs no implementation, PR, merge or deployment.
