# R3 host launcher code-only specification

Status: `tracking_synchronized_pending_checkpoint` at https://github.com/lucronn/autodata/issues/186#issuecomment-6637620320. Authority: false. Release state: `unverified`. This canonical spec and [plan](../../superpowers/plans/2026-11-04-workshop-r3-host-launcher.md) promote the independently PASS-reviewed external draft (coordinator-reported), SHA256 `7ab7435de8a79decea1bb4ffc9245be3d8345a5e3c0e1efc8f1696b7fc662d0f`, at planning base `880cd78eacdca9b60d18e7a28ca43112549b493d`. The plan carries the complete frozen interface, command/state/inspection and failing-first acceptance contract; this spec fixes its scope and completion meaning.

Goal: Prepare and independently review a fake-tested host launcher/enforcement adapter for the unchanged R3 immutable supervisor at exact app candidate 4d82e413e04fb2401ac7bc28dc828375ac662180; no Docker or compatibility execution.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Gate: `docs/agents/pre-implementation-gate.md`
Record: `docs/agents/records/2026-11-04-workshop-r3-host-launcher.json`
Task: `docs/agents/tasks/2026-11-03-production-release/workshop-r3-host-launcher.json`

## Immutable input and output boundary

App candidate is `4d82e413e04fb2401ac7bc28dc828375ac662180`, tree `d9fb2a8f49beacd009374a76327d0736c1fc9b0a`. Preserve the reviewed `supervisor.py`, `offline_probe.py`, `test_supervisor.py` and revision-3 handoff byte-for-byte under `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/`; exact hashes are in the plan/record. Frozen read-only source contract is `/home/corp/autodata-evidence/r3-probe-gate-draft/frozen-source-contract.json`, SHA256 `99c407d416b4f5996fdfeb2aad3719b784dc4009993fc041060b973cda0d64df`. Rehash and AST-compare its 19 reviewed function bodies without import before implementation/review.

Exactly two future executable source paths are permitted after separate code-only dispatch:

- `/home/corp/autodata-evidence/r3-immutable-probe-launcher-4d82e413-implementation/launcher.py`
- `/home/corp/autodata-evidence/r3-immutable-probe-launcher-4d82e413-implementation/test_launcher.py`

Only owned synthetic fixtures/receipts/temporary files may additionally exist under that root’s `test-artifacts/`. No third executable, repository implementation edit, modified reviewed source, real Docker/tool/Go/import probe, installation, service/provider/payment/cloud action or fixture execution is in scope. Unsupported wrapping behavior must block with a source-constraint report.

## Required enforcement

The launcher exposes exactly the plan’s parser/binding/pure-plan/guarded-executor/run interfaces and future explicit `-I -B .../launcher.py --execute-initial-probe --bundle .../execution-bundle.json` CLI. Import is inert. Strict canonical JSON/schema/source-origin validation occurs before subprocess or directory setup. Separate code and successor execution bindings prevent code-only/synthetic evidence from admitting runtime. Real CLI cannot select the fake transport from input.

Exact argv, environment, cwd, timeouts, full container identities and finite-state transitions guard every transport call. Before either start, inspect the complete image/name/label/entrypoint/argv/workdir/mount/tmpfs/HostConfig/effective-environment identity. Deny unknown normalizations, widened fields and arbitrary operation-label or raw transport escape. Direct exact-name and owner-token inventories precede each create; full-ID/name/token inventories prove cleanup absence with recorded-state handling of the known first container. Ownership uncertainty quarantines and preserves remaining IDs without deleting unknown resources.

Complete image Config.Env and explicit overrides are strictly merged and compared for both containers. Duplicate, secret, injection or unapproved inherited keys block, including empty forbidden values. Actual approved image-base environment belongs to the later execution gate. `compose_effective_no_build` derives from exact bounded baseline/effective config receipts and full-model structural equality; caller booleans, help text and mislabeled commands cannot establish it. No actual config observation runs in this slice.

All failing-first/green standard-library tests use explicit synthetic observations, fake executor/clock and subprocess/network deny sentinels. Temporary paths remain under owned test-artifacts. The plan’s complete negative matrix covers binding/import/CLI, every configuration widening, inventory races, environment inheritance, Compose evidence, timeout/truncated/nonzero receipts, bounded fresh-inspection ownership cleanup and fake-origin nonpromotion. Preserve raw red/green receipts, exact hashes and independent exact-source review.

## Temporal boundary and acceptance

The new code checkpoint SHA is null until the synchronized documentation commit exists; it is pinned externally afterward. The existing supervisor gate `5aeb9fb70ae041197ea57b7a33be509872a1715a` is historical input, not the new launcher gate. Launcher hashes are code-task outputs. Future successor execution-gate SHA and fresh clone/daemon/image/CLI/Compose observations are not code-gate prerequisites. Later execution explicitly authorizes bounded preparation, freezes actual observation/admission/dispatch/command bindings, then separately permits container creation.

Code-only completion means reviewed two-file source hashes, exact future CLI/command contract and fake-test evidence with `trusted:false`. Current manifest/probe acceptance, PR219 fixture execution, eight-root/42-tuple success, final180, acquisition and all release authority remain behind distinct successor gates. This task does not depend on parent PR219 execution. All authorities remain false; a passing code test changes no runtime/release state.

## Concrete todo

- [ ] Independently review this code-only draft; serialized coordinator synchronizes Issue186/Project8, canonical document, plan/record/task/queue and this exact todo, commits/pushes, then pins the real code checkpoint SHA, passes canonical preflight and independent committed-gate review before explicit external-path code-only dispatch.
- [ ] Create only launcher.py and test_launcher.py in the named external adapter root; preserve the three existing reviewed sources and historical artifacts byte-for-byte, using inert imports, synthetic fixtures, fake transports/clocks and owned test-artifacts only.
- [ ] Implement exact future CLI, separated checkpoint/runtime bindings, command/state/HostConfig/effective-env enforcement, direct-container absence checks and evidence-derived Compose no-build admission without calling real tools.
- [ ] Run failing-first then green standard-library fake tests and scope/hash/syntax checks; retain red/green artifacts, exact launcher/test hashes and independent exact-source review with every enforcement requirement checked.
- [ ] Handoff reviewed launcher/command contract and synthetic evidence only; leave fresh observations, actual probe/manifest acceptance, parent PR219 fixture execution, acquisition, final180, provider/payment/cloud/release authorities behind separate successor gates.
