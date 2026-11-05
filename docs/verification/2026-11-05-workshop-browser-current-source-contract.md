# Task53 browser current-source static contract verification

Status: **planning/tracking synchronized; implementation blocked pending committed checkpoint admission**. No implementation, fixture, runtime, acceptance, CI success or release claim.

Goal: Bind the offline browser compiler to the exact Task51 API21 producer and current DTO timing contract without changing producers, executing services, or granting fixture acceptance.

Plan `docs/superpowers/plans/2026-11-05-workshop-browser-current-source-contract.md`; spec `docs/agents/specs/2026-11-05-workshop-browser-current-source-contract.json`; standalone `docs/agents/records/2026-11-05-workshop-browser-current-source-contract.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-browser-current-source-contract.json`; queue `docs/agents/tasks/2026-11-03-production-release/queue.json`. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`. Coordinator supplied literal tracking synchronization at [comment6647728558](https://github.com/lucronn/autodata/issues/186#issuecomment-6647728558),2026-11-05T02:12:02Z. This planner verified the retained before/after snapshots; it made no GitHub writes.

## Exact source and scope

Planning parent `3fe138d6e93f005f314a942ef43b504fbe64551c` / `0a0339d0e36ca3b2a43ad7ba40d80f7ee5777f6e`; application/source `6949eb1b1a5b93c9b2eb0579328e24c697f6f331` / `47ec54b1896c83a39b6637a6ce944d3620414f4e`. Current worktree is a new native checkout on `codex/workshop-browser-current-source-contract-gate`, initially detached at exact3fe138d then assigned that branch. Native attachment hit the app's100-identity limit; retry returned overload. No duplicate checkout was created. Future builder branch reserved `codex/workshop-browser-current-source-contract-code`.

Prospective implementation is exactly `scripts/dev/workshop_browser_execution_contract.py` and `scripts/dev/test_workshop_browser_execution_contract.py`. This draft changes only the six listed documents; current implementation allowlist is empty. Queue append53 preserves52 predecessor objects, root fields and order. Task52 consumer/runbook bytes remain unchanged.

## Source findings frozen in spec

- Current API binding requires candidate6949 and source tree47ec; old spec supplies4d82 and lacks tree. New exact API environment includes both; absent or stale data rejects without ambient fallback.
- New spec contains full copied/adapted static schemas/schedules and inventories, exact current-source manifest records and independent frozen section digests. Historical static spec remains unchanged.
-21 ordered API identities and120 DTO identities remain; current API required refs190=148 baseline+42 process sidecars, including original JUnit `workshop-browser-api.xml`. Dynamic optional worker logs are separately declared from actual source worker mapping,max42; historical UUIDs are not a whitelist.
- Source timing JSON, smoke DTO_TIMING_V1 and Go expected-map agree: fixture4800,Go5040,CI exercise5100,producer4440,worker4380. Chosen compiler DTO per-command/operation abort bound5100000ms includes5040+60 headroom, while per-phase readiness/seal120000ms and unrelated resource timers remain separate. This is not a full aggregate schedule proof.
- Unchanged supervisor PHASE_NS.dto_running4560 and whole-attempt7500 remain. Compiler must retain blocked_timer_dependency and supervisor_dto_deadline_mismatch; no executable schedule/readiness claim follows. API2100 remains abort ceiling with finite-success proof missing.

## Required verification after dispatch

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider scripts/dev/test_workshop_browser_execution_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider scripts/dev/test_workshop_browser_execution_contract.py scripts/dev/test_workshop_browser_execution_evidence.py scripts/dev/test_workshop_browser_execution_supervisor.py scripts/dev/test_workshop_browser_preparation_probe.py`
- `git diff --check`
- `git diff --name-only <EXTERNALLY_PINNED_TASK53_CHECKPOINT>..<EXACT_TASK53_CODE_SHA>`


Use independent source-byte/AST inspection and spec negative_test_matrix. Record actual red failures before implementation, green focused/full offline counts and skips, exact two-file code diff, preserved source/historical/Task52/policy/workflow/profile blobs and queue invariants. Missing spec, stale/mixed source or assets, tree/env omission and invalid typed timeout boundaries must reject without silent fallback. Generic4560000 remains valid but cannot satisfy exact current DTO rendering;5100000 valid,5100001 and bool/string/nonpositive invalid.

## Checkpoint admission still outstanding

1. Independent planning-only draft review PASS158 completed; exact-checkpoint review remains required.
2. Coordinator Issue186/Project8 before/after literal synchronization completed at comment6647728558; standalone/nested records synchronized. Prior241 comments, Issue body and other Project fields unchanged; prior Source archived.
3. Committed/pushed synchronized six-document checkpoint from3fe138d; external actual SHA/tree seal.
4. Extract standalone/nested record and policy from that checkpoint; both canonical preflights errors=[]. Synchronized working-tree records still fail at3fe138d because new referenced documents are absent from that committed base.
5. Independent exact-checkpoint review; explicit coordinator two-path offline dispatch.
6. Independent exact-code review and fresh actual push/PR checkout CI readback after implementation.

No implementation/test/CI/preflight success is claimed by this draft. Documentation/source checks are recorded in the external planning report, not relabeled as code verification.

## Explicit remaining blocks

- `live_adapter_not_admitted`
- `runtime_observations_missing`
- `source_observer_not_admitted`
- `filesystem_identity_not_observed`
- `go_path_resolution_not_observed`
- `runtime_admission_not_verified`
- `independent_watchdog_not_admitted`
- `descendant_containment_not_admitted`
- `blocked_timer_dependency`
- `unchanged_supervisor_dto_4560s_vs_compiler_5100s`
- `api_finite_success_proof_missing`
- `trace_16MiB_producer_8MiB_consumer_not_admitted`
- `original_junit_and_log_capture_not_authenticated`
- `same_candidate_fixture180_not_verified`
- `authentic_staging_and_release_not_verified`

Accepted IDs[]; case credits0; runtime, fixture, staging, release, merge, deployment and every authority false. Task52 completion remains required before claiming current-v2 raw consistency inspection; neither lane authenticates capture or grants fixture acceptance.

## Exact tracking receipts

Before `/home/corp/autodata-evidence/browser-current-source-task53-before-tracking.json`, SHA256 `390d911d31197c039dfc23e85cefba53ce2f31bc073827c703ea3d2a90e5dc61`; after `/home/corp/autodata-evidence/browser-current-source-task53-after-tracking.json`, SHA256 `3523305fea409f7c18bca108ab2bcdd66f507e1122cdb65c93e406f5f6bf4b65`. Comment body SHA256 `90238bc72b4fa3d2fde4b7a22326afa4a391d71eced8e4bd8f50b46d10986e58`. Issue body SHA256 `927b46ef47b1dbf5b117273e3d3f5c0e6d9f23b722a5245869eb5323b96c4f25` unchanged. Project Source after SHA256 `ff2182f5d62ae69912ad6a58517eb33f2cb7f4c385c8a81b643e7c06d46ca8e1`. Snapshot observations `2026-11-05T02:11:55Z` and `2026-11-05T02:12:14Z`; canonical updated_at is actual comment timestamp `2026-11-05T02:12:02Z`. Tracking only; all implementation/runtime/release authorities false and current implementation allowlist empty.
