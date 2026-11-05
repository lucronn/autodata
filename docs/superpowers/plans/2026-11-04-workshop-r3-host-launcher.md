# R3 code-only host launcher and enforcement adapter implementation plan

> For agentic workers: this is a canonical documentation-only blocked plan. Read the canonical spec and gate before any work; implementation remains blocked pending the committed checkpoint. A synchronized committed checkpoint, exact-base machine preflight, independent committed-gate review and explicit absolute-path code-only dispatch are required before writing the proposed adapter. No Docker execution is authorized by this draft or by completion of its code task.

**Goal:** Prepare and independently review a fake-tested host launcher/enforcement adapter for the unchanged R3 immutable supervisor at exact app candidate 4d82e413e04fb2401ac7bc28dc828375ac662180; no Docker or compatibility execution.

**Architecture:** Add one external launcher and one standard-library test file beside a private test-artifacts directory. Preserve the already reviewed supervisor/probe/tests byte-for-byte. The adapter supplies an exact future CLI and a fail-closed command/state/inspection boundary around the existing initial-probe API. All execution observations in this slice are synthetic and all subprocesses are fakes. A separate successor initial-probe execution gate consumes the reviewed launcher hashes and later fresh observations.

**Tech stack:** Python standard library, unittest, fake executor/clock/filesystem fixtures. Existing Docker/Compose argv construction is reviewed as data only.

**Spec:** `docs/agents/specs/2026-11-04-workshop-r3-host-launcher.md`; canonical `docs/agents/pre-implementation-gate.md`; canonical lifecycle verification at PR220 head `880cd78eacdca9b60d18e7a28ca43112549b493d`; reviewed external immutable supervisor handoff; blocked parent runtime PR219. This supersedes the rejected initial-probe gate draft SHA256 `eb04c87fc8822aa80dd1f66b15886e9b0be68b7325f5f30586f6da034f25e156`. That draft is not an execution authority.

## Status, tracking and temporal boundary

Status `tracking_synchronized_pending_checkpoint` at https://github.com/lucronn/autodata/issues/186#issuecomment-6637620320, authority false, release state `unverified`. Issue: https://github.com/lucronn/autodata/issues/186 . Project: https://github.com/users/lucronn/projects/8 . Canonical plan: `docs/superpowers/plans/2026-11-04-workshop-r3-host-launcher.md`; canonical record: `docs/agents/records/2026-11-04-workshop-r3-host-launcher.json`; canonical task: `docs/agents/tasks/2026-11-03-production-release/workshop-r3-host-launcher.json`.

The coordinator owns serialized Issue/Project updates, history preservation/readback, canonical document/queue synchronization and checkpoint commit/push. The planning worker made no GitHub mutation, commit, push or implementation; coordinator tracking is now synchronized at https://github.com/lucronn/autodata/issues/186#issuecomment-6637620320. The eventual code checkpoint must contain the same goal, scope, references and concrete todo in those records. Pin its actual full SHA externally after commit and pass canonical preflight and independent gate review before code dispatch. The record's code implementation base is null in this draft; it is not a self-referential or fabricated SHA.

Fixed precheckpoint facts are the candidate SHA/tree, existing source hashes, scope, API and fake-test acceptance contract below. The later committed code-gate SHA is supplied only after that checkpoint exists. Launcher source hashes become deliverables only after code implementation/review. A later successor execution-gate SHA and fresh clone/daemon/image/CLI/Compose observations do not exist at code planning time and are neither required nor manufactured for code-gate synchronization. Successor dispatch gathers those observations in its own explicitly allowed preparation phase; it then freezes exact admission/dispatch/commands before any container creation. This removes the rejected circular prerequisite.

This is an independent code-only task with no dependency on parent PR219 execution. Probe execution, fixture execution and acquisition are successor tasks. Parent runtime remains blocked. All authority fields remain false in this draft, including implementation until separate dispatch. Code completion confers no runtime permission.

## Exact read-only inputs

Candidate/tree: `4d82e413e04fb2401ac7bc28dc828375ac662180` / `d9fb2a8f49beacd009374a76327d0736c1fc9b0a`. Existing code gate: `5aeb9fb70ae041197ea57b7a33be509872a1715a`.

Root `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/`:

| Immutable input | SHA256 |
| --- | --- |
| `supervisor.py` | `6c64cad2e3c490a2762367bdfe4e0bb662320d48f3f9cc7a3af831c6c356c0ed` |
| `offline_probe.py` | `ec2850f3f463c724498ee8bbfd6c7fef5e7e693b56b424579389dfcb72a32947` |
| `test_supervisor.py` | `d3d3f4a6e5aad509950b4a3ff85215eedb3407cfd68cad77e181404b7183b9fd` |
| `test-artifacts/offline-handoff-revision3.json` | `41d94659a5211da0a66892898ab2b73efbf640b9da1cf297db924ff9eae56ef8` |

The handoff's 44 passing tests and timeout ordering are fake-executor/code-only evidence, `trusted:false`. No Docker, actual tool/import/Go probe, current manifest or fixture acceptance follows. Preserve historical supervisor hash `e4a8f054f85207b5dc8e83155cf1b39e67ffcbc467d8f0a44eb08bc86a0e26b9` and audit report hash `b48449fb92e7541ee2f727dd0edba7a53f67bd36ef7d0a2b88f7c3a3046c96af`. Historical image availability is never a fresh observation. The source contract extraction remains inert JSON data with exact reviewed function bodies; it must match the read-only source bytes before implementation and review.

## Exact implementation and evidence allowlist after code-only dispatch

Create only:

- `/home/corp/autodata-evidence/r3-immutable-probe-launcher-4d82e413-implementation/launcher.py`: CLI/parser, immutable-source loading, pure admission/command/inspection policy and guarded initial-probe executor.
- `/home/corp/autodata-evidence/r3-immutable-probe-launcher-4d82e413-implementation/test_launcher.py`: standard-library unittest with fake executor/clock and explicit synthetic observations only.
- Artifacts/temporary fixtures only beneath `/home/corp/autodata-evidence/r3-immutable-probe-launcher-4d82e413-implementation/test-artifacts/`.

No repository implementation file, existing external source, historical artifact, real Docker resource, package/cache or service may be modified. No third executable source file, wrapper shell script, vendored supervisor or implicit plugin is allowed. If those two files cannot enforce the specified boundary while leaving reviewed sources unchanged, stop with a source-constraint report; do not patch the supervisor or silently expand scope. The adapter may reject unsupported existing behavior.

The coordinator-authorized documentation checkpoint changes only this canonical plan, its canonical spec, record and task, the canonical lifecycle verification document and existing release queue. The spec is the sole additive path beyond the reviewed draft’s five-document proposal. Preserve predecessor records/fields; no source changes occur during synchronization.

## Required adapter interfaces and future invocation

`parse_document(raw: bytes) -> dict` rejects duplicate keys, malformed/noncanonical JSON, unknown schema/extra top-level fields, empty or conflicting bindings. Pure policy functions consume explicit data; no ambient environment, time, subprocess, network or filesystem probe is permitted during parsing/import.

`validate_code_binding(binding: dict) -> dict` checks candidate/tree, this task's actual code checkpoint binding, reviewed supervisor/probe hashes and adapter source hash. It accepts no execution authority. A distinct `validate_execution_bundle(bundle: dict) -> dict` requires a later actual passing execution-gate SHA, exact successor record/review/dispatch hashes and explicit initial-probe stage. Null SHA, code gate reused as execution gate, fake origin or missing future observation fails. Unit tests use clearly synthetic bundle fixtures without claiming authority.

`build_initial_probe_plan(admission: dict, observation: dict) -> dict` is pure and produces canonical commands/environment/timeouts/paths plus hash and expected container configuration. It calls the unchanged supervisor admission/command APIs only after the adapter's stricter schema/evidence checks. It derives, rather than trusts, all evidence booleans. It never creates files or resources.

`GuardedExecutor(plan, receipt_sink, transport)` wraps an explicit argv transport with a finite state machine. It permits only the exact admitted initial-probe command graph described below. No fixture stage, arbitrary Docker argument, shell, alternate executable, operation-label-only permission or raw transport escape is allowed. Every transition records actual command, environment, timeout, stdout/stderr/exit/timing and inspected identity. The real transport is private and reachable only after CLI execution-bundle validation. Tests inject a transport marked `is_offline_fake=True`; every test invocation asserts no real transport use.

`run_initial_probe(bundle, *, transport, clock) -> dict` validates the bundle, obtains an unchanged `admit_probe` context, verifies exact `dispatch_binding`, and invokes unchanged `supervisor.execute` through the guarded executor. It adds initial/final direct-container absence receipts and HostConfig/env checks that the supervisor lacks. No `admit_fixture` call, synthetic execute context or fallback is possible. Unchanged supervisor result remains `trusted:false`/measured, never self-accepted.

Freeze the future CLI in the code deliverable as:

```text
<explicit-host-python> -I -B /home/corp/autodata-evidence/r3-immutable-probe-launcher-4d82e413-implementation/launcher.py --execute-initial-probe --bundle <owned-run-root>/execution-bundle.json
```

The exact existing host Python path/hash and owned-run-root are successor execution-gate inputs, not guessed here. No bare `python supervisor.py`, ad hoc `-c`, shell wrapper, default execution on import or omitted execution flag is supported. A future command-line invocation without valid passing successor bundle fails before any subprocess or directory setup. Loading existing supervisor/probe must first rehash exact absolute source paths and verify module origins; no ambient sys.path shadow module is accepted. Import is inert. Code tests invoke pure functions or CLI with fake transport through a test seam that real CLI cannot enable from untrusted bundle data.

## Closed command/state/inspection policy

This is a requirement to implement and fake-test, not authorization to run commands now. The adapter recognizes only exact argv from frozen reviewed `_unbound_commands` plus required read-only preparation/verification/cleanup observations below. Freeze all allowed commands in the final launcher handoff JSON; unknown commands fail before transport.

Initial-probe main argv consists only of compatibility and cleanup-interpreter create/start/wait/logs, using exact runner ID `sha256:b43f27cfb2dc268b00baf0458bd50f411caccb8d23f037c2819d1d304463fc8c`. Create uses `--pull never`, owner UUID4 token, network none, read-only root, cap-drop ALL, no-new-privileges and explicit `/usr/local/bin/python`. Compatibility binds only unchanged candidate clone `/workspace:ro` and reviewed probe `/probe.py:ro`, with single `/tmp:rw,exec,nosuid,size=4g` tmpfs and exact reviewed compatibility environment. Cleanup-interpreter has no bind/tmpfs and uses exactly the reviewed Python assertion. Existing source contract freezes flag order, command payloads, hashes and 180s compatibility wait/30s interpreter wait/30s create/10s start/inspect/log bounds. Compile inside future probe remains exact `go test -c -o /tmp/r3-compat.test .`, 180s, offline env; outer 180s wait is not extended.

Guarding an operation string is insufficient. State transitions require exact argv, fixed environment and timeout/cwd, full container-ID create receipt, matching fresh inspect, then start. Deny alternate tags, added mounts/env/ports/devices, privileged flags, build/pull/retag/import/export/save/load/buildx, package installs, downloads, fixture Compose up/run/create/down, services, broad cleanup and provider/payment calls. Source observations are exact supervisor Git/read-only hash functions, never mutable source preparation inside the unchecked executor.

Before any start, the guarded executor must validate the full inspect: exact full ID, exact name, exact immutable image, exact owner label, absent Compose project/service labels, exact argv/entrypoint/workdir, exact effective environment, intended bind projection/full admitted mount record, exact tmpfs, HostConfig.NetworkMode=none, ReadonlyRootfs=true, Privileged=false, CapDrop containing exactly ALL, SecurityOpt containing only no-new-privileges in the installed normalized form accepted by the successor gate, no port bindings/published ports, no devices/device requests/socket bind/cap additions/links/extra hosts/external DNS/network attachments. Define and fake-test normalized forms explicitly; unknown normalization returns blocked, never weakens equality. Do not accept a create command alone as proof of effective runtime configuration.

All inspect fields must be checked before start, including the cleanup-interpreter container. Each Docker mutation uses full ID after create, never a name/prefix/label alone. Unknown/mismatched inspect prevents start and yields quarantine/remaining_ids. Cleanup may proceed only after separately established ownership checks; the adapter never removes an unidentified resource to make a failed inspect disappear.

## Direct-container absence observations

Existing supervisor project-label inventory does not detect direct probe containers. Add explicit checks in the adapter's guarded graph. Before each create, obtain both `docker ps -a --no-trunc --format '{{.Names}}'` and `docker ps -aq --no-trunc --filter label=autodata.owner=<token>`. Require no exact planned compatibility/interpreter name and no owner-token container; require no repeated/malformed names/IDs. These are explicit inventory observations, not assumptions from a fresh UUID. An existing stopped container or owner label collision blocks create. Inventory is rechecked immediately before each create; cleanup of the first owned probe precedes the second if the unchanged supervisor orders it that way, or the policy permits only the known first ID in the owner inventory while requiring the second name absent. Derive this expected set from recorded state; never require globally empty owner inventory while a known first container legitimately exists.

After cleanup, query each created full ID using `docker ps -aq --no-trunc --filter id=<full-id>`, repeat exact-name inventory and owner-token inventory; require every created ID/name absent and owner-token inventory empty. A project inventory alone never proves absence. Preserve raw inventory receipts and failure/quarantine records. Any unexpected owner-token ID fails without deleting it. No real inventory is required or run in this code-only slice; tests supply deterministic rows, collisions and race changes.

## Image environment inheritance policy

Docker image Config.Env is inherited even when create lists explicit env flags. The adapter must model and enforce the complete effective environment for both containers, including cleanup-interpreter which has no override flags. Future bundle contains the fresh image Config.Env, its image/config digest, an independently reviewed allowed image-base environment map and exact expected merged map. Parse KEY=VALUE entries strictly, reject duplicate keys/NUL/unapproved keys and preserve values including `=`. Merge only explicit planned overrides; an empty override does not remove a key.

Only the future execution owner may approve that exact base map under the successor gate. The code gate neither asserts the current image Env nor invents safe values. Deny credentials/provider/model/bank/payment/production routing and secret keys even if empty, as well as unapproved Python/Go/proxy/config injection variables. Explicit compatibility env is exactly the existing probe's `compatibility_plan()['env']`; inherited keys additionally require literal independent approval. Actual container Config.Env must equal the full computed map with no extra/duplicate keys. Any unexpected base image env blocks reuse; no image change, env-clearing fiction or extra override is authorized. Fake tests cover inherited credentials, harmless approved defaults, overridden PATH/HOME, duplicate env, cleanup-interpreter inheritance and effective-env drift.

## Evidence for `compose_effective_no_build`

Existing supervisor initial admission requires this boolean inside cli_support even though initial probe starts no Compose service. The adapter must not blindly set it true, omit it or redefine it as help-text support. The successor execution gate must expressly authorize bounded config-only preparation and owned evidence-file creation before container admission:

1. Resolve exact candidate `infra/compose/compose.article-lifecycle-test.yaml` with installed Compose, `/dev/null` env and explicit allowed host env, record exact argv/raw/canonical JSON and candidate raw-file hash `c9c0c6f58d7e60efe574c33000b97c087834163bffd8bc92ed16322587d2dd4e`.
2. Apply unchanged pure `effective_compose` to that baseline: four exact immutable image IDs, pull_policy never, remove test-runner and go-test-runner build, replace only minio `/data` mount with reserved owned Seaweed path/create_host_path=false. No actual Seaweed directory/service/network/volume is created. Preserve baseline/effective canonical hashes and exact allowed delta.
3. Write that owned effective JSON only under successor-authorized run root; run installed Compose `config --format json` on that exact file with `/dev/null` env and same fixed env. Require complete resolved model equality and no build key in any executable service, all images exact, pull policy never, no widened service/env/mount/port/network/command/config delta.
4. Derive `compose_effective_no_build=true` only from both successful bounded config receipts, file/model hashes and explicit structural checks. CLI help support for up/run/create flags is recorded separately. Missing/contradictory evidence blocks admission before containers.

Code-only tests provide fake installed-Compose receipts and temporary synthetic effective files. They must fail on unresolved/missing keys, hidden inherited build, extra service, bad delta, changed model, caller-supplied true without evidence and a fake command mislabeled config. Current actual Compose config/version/support is unmeasured and remains a successor execution blocker. If installed Compose cannot normalize the unchanged model without unauthorized changes, the adapter returns blocked; no source amendment occurs here.

## Offline test and verification contract

All tests use standard-library unittest and explicit fake transport/clock. TemporaryDirectory and bytecode/cache locations are explicitly below this adapter's test-artifacts, never default host temp. No Docker binary, real tool `--version`, Go compile, candidate import, service/network/provider/cloud call or package installation is allowed, including in test setup/teardown. The test harness must patch/deny the real subprocess/network entrypoints and assert the deny sentinel was never invoked. Existing supervisor/probe may be imported inertly only after verified source loading; their execution receives fakes.

Required failing-first regressions then green coverage:

- Split checkpoint/code/output/later execution bindings without circular SHA or future-observation requirements; execution rejects missing actual successor gate.
- Import/CLI inertness, exact source/hash/module-origin checks, no default executor, real CLI cannot select fake mode from input.
- Exact command/cwd/timeout/env comparison and state graph; arbitrary command/shell/fixture attempts denied before fake transport.
- Full HostConfig/argv/mount/label/merged-env validation before either start, testing every widened field and unknown normalized form.
- Direct exact-name/owner/full-ID observations, stopped-name collision, unexpected token-owned ID, concurrent inventory change, valid known-first-container set, successful cleanup absence and residual-resource failure.
- Image-env inheritance for both containers including duplicate keys, secrets, empty overrides and drift.
- `compose_effective_no_build` evidence derivation, not a caller boolean; fake canonical model/config receipts and unauthorized deltas.
- Timeout/nonzero/malformed/truncated receipt, full-ID ownership cleanup stop 5/kill/rm with fresh inspections under total 30s, no destructive call on uncertain identity, quarantine/remaining_ids and immutable failed receipts.
- Synthetic/code-only observations cannot be relabeled or used as current/independently accepted manifests; no fixture/eight-root/42-tuple/final180/release success inferred.

After code dispatch the only allowed test command family is `<explicit-host-python> -B -m unittest -v test_launcher`, cwd the exact adapter root, with TMPDIR/PYTHONPYCACHEPREFIX directed beneath its test-artifacts and test-owned explicit env. Freeze that existing Python path in code dispatch. A standard-library AST/syntax/read-only hash/scope check is allowed; no dependency/tool compatibility probes. Preserve red/green command argv, exit/stdout/stderr, test names/count, fake transport receipts and output/source hashes; unit-test pass is code evidence only. Review must recompute immutable supervisor/probe hashes and confirm no edits, inspect exact launcher/test bytes and enforce every boundary case above. No fake receipt is accepted as current runtime evidence.

## Concrete todo

- [ ] Independently review this code-only draft; serialized coordinator synchronizes Issue186/Project8, canonical document, plan/record/task/queue and this exact todo, commits/pushes, then pins the real code checkpoint SHA, passes canonical preflight and independent committed-gate review before explicit external-path code-only dispatch.
- [ ] Create only launcher.py and test_launcher.py in the named external adapter root; preserve the three existing reviewed sources and historical artifacts byte-for-byte, using inert imports, synthetic fixtures, fake transports/clocks and owned test-artifacts only.
- [ ] Implement exact future CLI, separated checkpoint/runtime bindings, command/state/HostConfig/effective-env enforcement, direct-container absence checks and evidence-derived Compose no-build admission without calling real tools.
- [ ] Run failing-first then green standard-library fake tests and scope/hash/syntax checks; retain red/green artifacts, exact launcher/test hashes and independent exact-source review with every enforcement requirement checked.
- [ ] Handoff reviewed launcher/command contract and synthetic evidence only; leave fresh observations, actual probe/manifest acceptance, parent PR219 fixture execution, acquisition, final180, provider/payment/cloud/release authorities behind separate successor gates.

## Cleanup, rollback and successor boundary

Code-only rollback is deletion/replacement of only the two new external files before publication, owned by the coordinator; retain failed test/review receipts. Preserve existing sources/historical evidence unchanged. No Docker cleanup is run because no Docker resource is created. No recursive deletion outside explicitly owned test-artifacts is permitted; cleanup scope itself is fake-tested as data.

Successor initial-probe execution requires a new synchronized committed execution gate, exact reviewed adapter and existing-source hashes, explicit host Python/git/docker paths and allowlisted environment, fixed local clone source/run-root protocol, current daemon/image/CLI/config observations, independently reviewed image-base env and complete admission/dispatch/commands. The execution gate authorizes preparation observations first, then freezes actual observations/dispatch before container creation. Accepted tool/package/cache manifests are probe outputs, not circular prerequisites to initial probe. Independent audit is required before any output is marked accepted. Any unavailable/unsafe immutable input blocks instead of acquiring or weakening it.

Parent PR219 fixture run remains a separate successor: independently accepted current manifests/probe receipt plus reconciled exact paths/Compose/commands, passing parent gate, fresh fixture ownership and explicit runtime dispatch. The adapter implemented here rejects fixture execution. No code-only completion changes release_state or any runtime/release authority.

## Canonical promotion and blocked synchronization checkpoint

Planning base is PR220 head `880cd78eacdca9b60d18e7a28ca43112549b493d`. This promotion preserves the independently PASS-reviewed external draft contract (coordinator-reported review), SHA256 `7ab7435de8a79decea1bb4ffc9245be3d8345a5e3c0e1efc8f1696b7fc662d0f`. External draft inventory SHA256 bindings are `2eba1ae56760c131de7540f9b2c2042e54659e7335b620d299519eb4b3d1de0e` for the draft record and `99c407d416b4f5996fdfeb2aad3719b784dc4009993fc041060b973cda0d64df` for the frozen source contract. These are read-only planning inputs, not execution authority.

The record/task remain blocked until the sole coordinator tracker writer preserves Issue186 and Project8 history, appends the matching goal/six-document scope/references/five todos, archives the prior compact Project Source and updates only that index, then independently reads back matching live tracking. No predecessor task state, source or runtime evidence is promoted. Coordinator must then synchronize standalone/nested records, commit/push the six-document checkpoint, externally pin its real full SHA, run exact-base machine preflight, obtain independent committed-gate review and issue an explicit absolute-path code-only dispatch. The checkpoint and later execution gate remain null here. This plan grants no implementation or runtime authority.

## Code-only work sequence after the separate dispatch

### Task 1: Establish fail-closed binding and inert loading

Files: create only the named `launcher.py` and `test_launcher.py`; synthetic fixtures/receipts stay in named `test-artifacts/`. Implement the specified `parse_document`, `validate_code_binding` and `validate_execution_bundle` interfaces. Write regression tests first for every split-binding, duplicate/unknown-schema field, source/hash/origin mismatch, import side effect and default-CLI/fake-mode bypass listed in the offline contract. Run the allowed fake unittest command, retain the failing receipt, implement the smallest closed parser/loader, and rerun to green. Exact code checkpoint is supplied by coordinator dispatch; future execution facts are not required to build code.

### Task 2: Enforce commands, state and effective configuration

In the same two files, implement `build_initial_probe_plan`, `GuardedExecutor` and `run_initial_probe` exactly as specified above. Add failing regressions for every command/cwd/env/timeout deviation, widened HostConfig field, inventory collision/race/residual, inherited environment defect, false Compose evidence and cleanup identity/timeout failure. Use only explicit synthetic fixtures, fake transport and fake clock; then implement and rerun to green. If the unchanged supervisor cannot be wrapped safely, return a source-constraint report instead of editing it or expanding scope.

### Task 3: Preserve code-only evidence and independent review

Run the full fake unittest family with all host subprocess/network entrypoints denied and explicit owned temporary paths; retain every red/green command, exit, stdout/stderr, test name/count and fake receipt. Perform static syntax/AST/hash/scope checks without candidate/tool imports or compatibility probes. Rehash all immutable input bytes, freeze launcher/test hashes and exact command contract in owned handoff JSON, and obtain independent review of exact source bytes against every acceptance case above. Stop at the synthetic code-only handoff; all later execution/acceptance authorities remain false. No repository source commit or push is delegated by this plan.


## Revision4 code-only completion receipt — 2026-11-04

The external launcher revision4 at code checkpoint `c1a70fe488b3864098f1722da78b341c9fdde567` received an independent exact-source **PASS** with no material findings (coordinator-reported). The reviewer reran 39 nonwriting tests and verified the sealed 47-test synthetic `OK` log. The prior revision3 P2 credential-persistence finding is closed; the cumulative nonrenewable 30-second cleanup budget is sound. This documentation task rehashed the handoff, source/test, sealed test log and unchanged supervisor/probe inputs; it did not rerun the review or tests.

Reviewed launcher SHA256: `8d611a882954675d6eff21b5f1e756898e246b748e40b9a5d9f61209497fa577`; test SHA256: `18899babcd78e06472cec71b6bca2eb0f658c9fc0ad62b303c65e3b0593096e6`. Preserved external `test-artifacts/launcher-handoff.json` SHA256: `3decaef678bdf0f2523ceed936d04fd035523b4a10507f3487f974e5783f3cd7`. The handoff's historical `ready_for_independent_exact_source_review` status is unchanged; this later receipt records the coordinator-reported review outcome. Full bindings and limitations are in `docs/agents/records/2026-11-04-workshop-r3-probe-launcher-code-review.json`.

Completion is limited to reviewed external code and synthetic evidence (`trusted:false`). No Docker/runtime execution or acceptance follows. Actual Docker normalization, image environment, direct-container absence and CLI/Compose behavior remain unmeasured; unknown normalization blocks. A separately passing successor initial-probe gate, canonical record/preflight, exact-hash independent review/dispatch and fresh authorized preparation observations remain required. Parent PR219 fixture execution remains separately blocked; no accepted current manifest/probe, eight-root/42-tuple, final180 or release result exists. All evidence authorities remain false and release state remains `unverified`.

This append-only receipt preserves the original synchronized gate record, task/spec, implementation and external files. Coordinator owns subsequent Issue/Project/PR synchronization; this documentation task performs no tracker writes.
