# R3 real preparation adapter implementation plan

> For agentic workers: this six-path repository checkpoint records synchronized Issue/Project tracking only. The coordinator must bind its actual pushed SHA externally, pass standalone/nested exact-base preflight, obtain independent exact-checkpoint review and explicitly dispatch exactly ten code paths before any adoption or implementation. No host observation or runtime execution is dispatched here.

**Goal:** Implement an independently reviewable Linux preparation adapter that binds approved host/file/Git/Docker observations to the reviewed subprocess primitive, bounded descriptor I/O, nonrenewable budgets, safe evidence projection, and conservative cleanup; defer actual host observations to a separate preparation execution gate.

**Architecture:** Preserve the fake collector as a synthetic reference model. Build separate actual-contract admission, one isolated descriptor-I/O worker, and real preparation orchestration. Consume the existing `process_transport.run` for every external command, with one shared `CaptureBudget` and cancellation event. A separately admitted owner-controlled containment/watchdog boundary remains necessary for real use.

**Tech stack:** Existing Python standard library, Linux/POSIX, unittest; no new package, Docker SDK, dependency, workflow, installer, shell wrapper or application change.

**Specification:** Canonical `docs/agents/pre-implementation-gate.md`; PR240 fake specification/plan at `0da0be85b864ab829200d170a656ad6ea87651dd`; PR241 transport specification/plan at `8f0129cf21ca818c87eb1a3097ad055de9771082`; reviewed preparation policy `/home/corp/autodata-evidence/r3-preparation-gate-draft/PLAN.md`. `source-pins.json` accompanies this plan with exact file hashes. This proposal tightens implementation mechanics and does not relax the preparation policy.

## Status and evidence boundary

Status is `tracking_synchronized_checkpoint_review_pending` at 2026-11-04T20:21:18Z. This repository documentation package is based on the exact PR241 code head and has live Issue/Project readback https://github.com/lucronn/autodata/issues/186#issuecomment-6641148122. It grants no implementation or host dispatch; exact-base machine preflight and independent checkpoint review are still required.

Independent external revision2 review at `/home/corp/autodata-evidence/r3-real-adapter-plan-independent-review/revision2/verdict.json` returned PASS with no remaining actionable findings and closed F1/F2. Its exact reviewed proposal hashes are retained in the canonical record and external manifest. That PASS does not certify this draft, a committed checkpoint, implementation or host compatibility.

F1 requires truthful persisted `pre_finalization_snapshot` records with pending worker/cleanup, live monitor and false final_receipt_issued; only the separately returned final result can claim completion after verified checksum-bound artifacts and confirmed worker/monitor retirement. No file write occurs after checksums; cancellation, reap failure or monitor-join failure yields no success receipt. F2 limits the fork-order rule to the direct Python file worker before the monitor; required unchanged later PR241 Popen calls remain allowed and may fork/vfork. Synchronous Popen/startup/kernel/interpreter stalls have no guaranteed local return; independent owner containment/watchdog is mandatory. No broker or primitive repair is in scope.

Retain candidate `4d82e413e04fb2401ac7bc28dc828375ac662180`, tree `d9fb2a8f49beacd009374a76327d0736c1fc9b0a`, all frozen revision4 launcher/supervisor/probe/source/image pins and all existing acceptance contracts. Do not import or execute candidate application/runtime code.

PR240 independent revision2 PASS refers to code `0da0be85b864ab829200d170a656ad6ea87651dd` and 48 synthetic tests. PR241 independent PASS refers to code `8f0129cf21ca818c87eb1a3097ad055de9771082`, 32 synthetic local-child tests and three independent probes. These are retained predecessor claims, not tests rerun here. PR241 normal CI readback retained Vercel failure and no autonomous-verification job; no CI PASS is inferred. This drafting task performs static document/Git-object checks only, with no host observations, tests, services, Docker, providers, secrets, owner acceptance or child-process verification.

## Integration base and exact ownership

The two code branches diverge at `e414e8537c8a6f0bc99747f6db09782b7743a949`. Neither contains both implementations. Planning parent is exact PR241 code `8f0129cf21ca818c87eb1a3097ad055de9771082`, tree `de1855c3534b82dc551ea59c527f24f1f2b3e9b8`. Its branch is `codex/workshop-r3-process-transport-build`; PR240's branch is `codex/workshop-r3-preparation-collector-build` at the fake code pin. Do not reset, reuse or edit either owned checkout.

Docs-completion heads `b3e91e6a81db03b9bbb7615c3fb168bdc77c6834` (`codex/workshop-r3-process-transport-gate`) and `47f06f049ee97a57ebdbd3d034c13a303e166c39` (`codex/workshop-r3-preparation-collector-gate`) are documentation branches, not integrated code trees. Preserve their completion receipts as references; do not call either a code integration base.

The coordinator created the isolated planning branch `codex/workshop-r3-real-preparation-adapter-gate` from the exact PR241 code pin. Future builder branch is `codex/workshop-r3-real-preparation-adapter-build`, created from the externally sealed, independently reviewed planning checkpoint after explicit code-only dispatch. `implementation_base_sha` remains null until then. An invented integrated/checkpoint SHA is forbidden.

Coordinator alone owns the six gate paths:

- `docs/superpowers/plans/2026-11-04-workshop-r3-real-preparation-adapter.md`.
- `docs/agents/specs/2026-11-04-workshop-r3-real-preparation-adapter.md`.
- `docs/agents/records/2026-11-04-workshop-r3-real-preparation-adapter.json`.
- `docs/agents/tasks/2026-11-03-production-release/workshop-r3-real-preparation-adapter.json`.
- `docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md`, append successor section preserving prior bytes.
- `docs/agents/tasks/2026-11-03-production-release/queue.json`, append one new task preserving prior values.

Future implementation allowlist is exactly ten new mode100644 paths at that checkpoint. The first four are prerequisite adoption with exact bytes/modes from PR240, never modifications:

- `scripts/r3_preparation/policy.py`.
- `scripts/r3_preparation/collector.py`.
- `scripts/r3_preparation/test_policy.py`.
- `scripts/r3_preparation/test_collector.py`.

The six actual new implementation/test paths are:

| Path | Responsibility |
| --- | --- |
| `scripts/r3_preparation/real_admission.py` | Exact actual-owner/dispatch/manifest schema, argv/dependency graph, external approval binding and closed safe projections. |
| `scripts/r3_preparation/file_transport.py` | Single isolated descriptor-I/O worker, bounded local IPC, metadata/hash/absence/output operations and owned worker lifecycle. |
| `scripts/r3_preparation/host_adapter.py` | Library-only actual orchestration, shared budgets/cancel, subprocess binding, classification and finalization. |
| `scripts/r3_preparation/test_real_admission.py` | Pure hostile-contract/manifest/projection tests. |
| `scripts/r3_preparation/test_file_transport.py` | Owned temporary-tree/IPC/worker tests, bounded syscall-failure doubles. |
| `scripts/r3_preparation/test_host_adapter.py` | Scripted graph plus owned synthetic-child integration tests; zero real Git/Docker/provider calls. |

Inherited `process_transport.py` and `test_process_transport.py` remain byte/mode identical to PR241. The adopted fake four remain identical to PR240. No `__init__.py`, CLI, default host adapter, source imports, workflow or caller integration. No monkeypatching historical `CHECKPOINT`, synthetic markers or acceptances, and no feeding actual observations to `collector.collect`. Modules have no import-time I/O, environment reading, process/thread launch or signal installation.

One implementation owner works sequentially on the ten paths; independent reviewer reads exact frozen heads without repair. Coordinator is sole serialized writer for Issue186/Project8/canonical docs. Human operator/reviewer/cancellation/host/daemon/tool-installation/watchdog identities are separately required actual values at observation time; role labels and self-declared booleans cannot satisfy them. No identities are invented in this plan.

## Canonical synchronization and dispatch gate

Before importing even one PR240 file, coordinator must reserve the tracking slot, write the six canonical gate paths, synchronize Issue `https://github.com/lucronn/autodata/issues/186` and Project `https://github.com/users/lucronn/projects/8` with this same goal and literal todo from `tracking-payload.json`, retain all prior comments/Project Source, and record raw before/after hashes/detail URLs. Commit/push only the six gate paths; externally seal the actual checkpoint SHA. Validate committed standalone and nested records against that exact SHA, equality required, `status:synchronized`, `errors:[]`. Obtain independent exact-checkpoint review and explicit ten-path code-only dispatch. Existing e414e853/5b128bd preflights authorize neither adoption nor new files.

After dispatch, a byte-preserving adoption milestone supplies the integrated code tree. Integration is application-neutral; it grants no host or runtime authority. A material primitive/fake-core change or extra path requires a new gate, not an opportunistic repair in this scope.

## Actual public API and trust boundary

Proposed exact public dataclasses are frozen/slots and exact-type validated. Unknown/missing/duplicate fields, bool-as-int, subclassed instances, NUL/CR/LF paths, relative paths, components `.`/`..`, paths >4096 UTF8 bytes or >64 components, unresolved values, nonfinite clocks, repeated command IDs and noncanonical image IDs block before child/I/O activity. Public configuration cannot widen limits or choose test backends.

- `ActualContract`: contains only the admitted owner/dispatch/command/file/output contracts below, immutable manifest digests and the pinned new checkpoint. It has no trusted/authorized boolean that bypasses verification.
- `ApprovalBundle`: exact bounded externally obtained artifacts binding named actual operator/reviewer sessions, distinct people/sessions, cancellation owner, host/daemon/tool installation owners, watchdog owner, code/checkpoint/manifest hashes and a fresh single attempt. The coordinator verifies the authenticated provenance channel before supplying it. The adapter validates equality/completeness/expiry; a JSON claim alone never authenticates an approval. No network verification/discovery is added here.
- `Anchor`: owner-opened inherited directory descriptor plus exact approved root identity/closed reference. Descriptors are handed through a trusted embedding API, never guessed from numeric argv or reopened from a supplied path. Owner guarantees exclusive descriptor-table ownership through worker fork. Child validates identities before use.
- `admit_actual(document: bytes, approvals: ApprovalBundle) -> ActualContract | Problem` is pure and uses existing bounded JSON machinery with production limits. It never calls synthetic `admit_contract` or labels actual inputs synthetic-approved.
- `collect_preparation(contract: ActualContract, anchors: tuple[Anchor,...], cancel_fd: int) -> PreparationResult` has no default ports and no CLI. The later observation gate must pin/review the trusted embedding entry point and descriptor handoff; absence is a blocker, not permission to write an unreviewed wrapper.
- `PreparationResult` contains fixed status/classification/problem codes, safe observation records, command captures with complete/prefix distinction, cleanup record, optional final in-memory receipt, and all false authority diagnostics. Actual observation provenance is `evidence_kind:preparation_observation`; successful local observation can set `host_observed:true` only in its later private observation receipt. This planning package and code-only test receipts retain `host_observed:false`. Host observation never grants runtime acceptance or trust.

Reuse only public pure bounded `policy.parse_bounded_json`, `policy.serialize_bounded`, constants and immutable value types after exact production validation; their default synthetic `SafeObservation`/`Contract`/`Receipt` values cannot be relabeled. Actual projection implementations belong to real_admission and explicitly enforce this plan. This small duplication is deliberate: fake schema/markers/checkpoint remain testable historical facts. No private `_Attempt` or `_templates` dependency.

## Required immutable observation contract

A future actual contract must bind literal values for: all named identities/sessions; local host identity; default local Unix socket and daemon owner; exact Python/git/docker/system-Compose-plugin paths and hashes plus runtime libraries and parent identities; complete Git installation config-source provenance; exact plain clone C with all source/tracked manifest pins; preparation root R and fresh UUID4 hex T; exact ten-key environment; all approved inputs/absences/parents; root subdirectories home/artifacts/minio and storage device; expected baseline/effective models and full closed nonsecret image Config schemas; exact command order/manifest; freshness/storage/capture/immutability/crash/swap/containment/watchdog/cleanup acceptances; actual adapter code SHA and planning checkpoint; one-attempt dispatch hash; output ownership/privacy/schema and independent-review handoff. Literal approval artifacts remain external and private unless publication is separately allowed.

Owner supplies R and approved subdirectories already created 0700, with no existing files except independently hashed operator-owned owner-contract.json and dispatch.json. Adapter does not mkdir, create a clone, install tools, obtain images, alter permissions, repair config, obtain secrets or start services. Missing clone permits only independent approved observations; Git/Compose remain blocked. There is no ambient HOME, pwd, PATH, daemon or plugin fallback.

Source/tool/runtime/config/clone window must be owner-controlled immutable before/through every dependent command, with exact before/after no-follow identity/absence checks. Re-stats do not prove the absence of change-and-restore. Installation owner must identify every compiled-in/prefix-derived system/global/XDG/local/worktree config path before any Git invocation, including `git --version`. Require all implicit config sources absent except exact core-only `.git/config` literal bytes/hash approved by the owner; reject includes/extensions/remotes/hooks/fsmonitor/helpers/filters/LFS/submodules/alternate gitdir/common-dir and config.worktree. No `git config`, `-c`, GIT_CONFIG bypass or discovery is added.

Isolation acceptance is mandatory before actual dispatch: trusted nonescaping admitted tools, ordinary SIGCHLD, exclusive direct-child reap, no competing waitpid(-1), a single-threaded controller at initial worker fork, immutable runtime code/config, RLIMIT_CORE=0 and owner-approved no-swap/no-crash-dump policy. Owner pre-establishes a dedicated externally supervised resource scope; adapter does not create/configure/mount cgroups. It must cap combined controller/worker/command memory at 1GiB, process count at32 and controller/worker open FDs at128, with no swap and an external wall watchdog. Lower ceilings can block; higher ceilings need a new reviewed policy. Memory/FD/process exhaustion is terminal. These ceilings are deliberately distinct from data-size limits and do not promise every worst-case allowed document fits available memory.

The watchdog observes controller liveness, initial worker startup, every synchronous command Popen/exec startup stall, interpreter/controller loss and attempt expiry independently, confines scope cleanup to the named attempt, and reports cleanup unconfirmed/quarantine on inability to establish termination. Setting the cancellation Event cannot interrupt a synchronous Popen or an uninterruptible kernel call; the owner watchdog must cover those intervals without depending on the controller returning a local result. No process broker or primitive repair is included. The owner must document actual kernel/scope behavior and acceptance; a process-group assertion or a claimed cgroup path is insufficient. Without this separately verified owner contract the adapter returns blocked before actual commands. This code-only gate does not deliver or certify the watchdog.

## Exact external command graph

The complete immutable graph has 26 possible command IDs, each at most once. Manifest substitutions P/G/D/C/R/T and I0..I3 are resolved to literal approved values and serialized before dispatch; unresolved symbols block. Every `RunRequest` has absolute executable, explicit argv, exact environment, stdin DEVNULL/close_fds/new session as enforced by PR241, and fixed cwd R for ordinary/version/Git calls, C for the two Compose config calls. Binding an explicit approved R replaces the historical null cwd, preventing ambient cwd inheritance; argv is unchanged.

Exact environment keys/values for every command:
`PATH=<owner-approved literal path list>`, `HOME=R/home`, `USER=<owner-approved>`, `LOGNAME=<owner-approved>`, `LANG=C.UTF-8`, `LC_ALL=C.UTF-8`, `TZ=UTC`, `AUTODATA_R3_TEST_IMAGE=I0`, `AUTODATA_R3_CANDIDATE_SHA=4d82e413e04fb2401ac7bc28dc828375ac662180`, `AUTODATA_LIFECYCLE_ARTIFACT_DIR=R/artifacts`.
No inherited keys, credentials/config helper/proxy/PYTHONPATH/DOCKER_HOST/TLS routing. Default context/system plugin resolution must be owner-established without forbidden config content. Missing route provenance blocks; do not add environment overrides.

Let `GP=[G,"--no-optional-locks","-C",C]` and `CP=[D,"compose","--env-file","/dev/null","-p","autodata-r3-"+T,"-f",C+"/infra/compose/compose.article-lifecycle-test.yaml"]`. Concatenation here is literal argv construction, never shell.

| ID | Exact argv / prerequisites |
| --- | --- |
| python_version | `[P,"-I","-B","--version"]`; tool/runtime file eligibility. |
| git_version | `[G,"--version"]`; Git installation and all config eligibility. |
| docker_version | `[D,"--version"]`; Docker executable eligibility. |
| compose_version | `[D,"compose","version","--format","json"]`; Docker/system plugin/runtime eligibility. |
| context_show | `[D,"context","show"]`; tool/config route provenance and approved metadata-only socket. Require `default`. |
| context_inspect | `[D,"context","inspect","default","--format","{{json .}}"]`; successful context_show and socket. Require exact approved Unix endpoint, false SkipTLSVerify, sole docker endpoint. |
| daemon_version | `[D,"version","--format","{{json .}}"]`; both successful context projections and socket before/after. |
| daemon_info | `[D,"info","--format","{{json .}}"]`; same daemon prerequisites. |
| create_help | `[D,"create","--help"]`; executable eligibility only, flag presence digest. |
| compose_up_help | `[D,"compose","up","--help"]`; executable/plugin eligibility only. |
| compose_run_help | `[D,"compose","run","--help"]`; executable/plugin eligibility only. |
| image_runner / image_postgres / image_nats / image_minio | `[D,"image","inspect",I0/I1/I2/I3]`; both contexts/socket and daemon version/info accepted. |
| inventory_names | `[D,"ps","-a","--no-trunc","--format","{{.Names}}"]`; daemon chain. Exact planned-name collisions only. |
| inventory_owner | `[D,"ps","-aq","--no-trunc","--filter","label=autodata.owner="+T]`; daemon chain. Require empty full-ID lines. |
| inventory_project | `[D,"ps","-aq","--no-trunc","--filter","label=com.docker.compose.project=autodata-r3-"+T]`; daemon chain. Require empty full-ID lines. |
| git_files | `GP+["ls-files","--stage","-z"]`; config/plain clone/source/complete tracked manifest eligibility. |
| git_head | `GP+["rev-parse","--verify","HEAD"]`; same Git eligibility, require candidate. |
| git_tree | `GP+["rev-parse","HEAD^{tree}"]`; require candidate tree. |
| git_status | `GP+["status","--porcelain=v1","--untracked-files=all"]`; require empty. |
| git_remote | `GP+["remote"]`; require empty. |
| git_symbolic | `GP+["symbolic-ref","-q","HEAD"]`; require exit1 and empty stdout. |
| compose_baseline | `CP+["config","--format","json"]`; six successful source Git checks, Git config window, executable/plugin and candidate source eligibility; complete approved baseline. |
| compose_effective | `CP+["-f",R+"/effective.json","config","--format","json"]`; successful baseline, validated frozen transform and exclusive synced effective.json. |

I0=`sha256:b43f27cfb2dc268b00baf0458bd50f411caccb8d23f037c2819d1d304463fc8c`.
I1=`sha256:151aa1c2e849e7828ed8aef2183ae15f692cbe887d2f28921d8b44b26e154d7e`.
I2=`sha256:8b9f712ae2148dcbd9d7f3d16a942d515e290526e5d018500931eab62b18e045`.
I3=`sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5`.

Stable topological order is table order, expanding four images in I0..I3 order. Every actual invocation revalidates complete prerequisite identities/absence/window; no late prerequisite triggers a retry. Missing prerequisite yields fixed blocked_missing_input for dependent node; independent eligible nodes may run once. Any breach/integrity/unsafe projection/nonexpected exit/collision stops the entire attempt, preserving incomplete results. Image/full model incompatibility is terminal source_incompatible only with an approved safe counterexample; arbitrary rejected data is withheld.

Only git_files, git_head/tree/status/remote/symbolic and the two Compose config commands use `kind:source` /30s. All others, including git_version, use ordinary/10s. Primitive completed means lifecycle completion only. Require exit0 except git_symbolic exit1; every nonzero still has complete stream digests only if full EOF/cleanup succeeded.

No arbitrary `--help`, shell, command discovery, tag lookup, pull/build/create/up/run/down, container inspect, cleanup, service action, cloud/provider request or secrets are permitted. Help forms above are data reads, not authorization for the referenced runtime action.

## File transport isolation and descriptor mechanics

One persistent private worker is forked before any adapter thread starts, after pure admission and under the accepted owner scope. Parent supplies only admitted anchor FDs and a local socketpair; child calls setsid and closes all inherited FDs except exact anchors, IPC and approved null standard streams. Fork/setsid/handshake have5s accounting and external watchdog coverage. Reject unsupported fork/NOFOLLOW/CLOEXEC/WNOWAIT/selector/SIGCHLD conditions rather than fallback. No Python executable command, candidate module import, shell or worker CLI is added to the 26-command inventory. Worker is an internal owned adapter process, never a command target PID from the contract.

Parent uses nonblocking IPC with fixed version/type/sequence/length headers, each payload at most64KiB, one outstanding operation, request IDs monotonic, approved operation and file/output IDs only. No pickle, marshal, eval, unbounded recv/readline or arbitrary diagnostic. Length is checked before allocation. Disconnected, duplicate, reordered, oversized, malformed or unknown frames stop the attempt and retire the worker. Child requests cannot select arbitrary paths beyond immutable admitted recipes; operation request bodies are bounded separately and all byte totals charged before append/send. Output documents stream in <=64KiB chunks, never argv. Safe config bytes returned for exact equality are limited to the approved literal; general file bodies are hashed in worker and withheld. Hashes are complete only after same-descriptor EOF and final identity checks.

Worker operations are `observe_regular`, `observe_absence`, `observe_socket_metadata`, `revalidate`, `space`, `inventory_outputs`, `create_output`, `verify_output`, `close`. It has no mkdir/unlink/rename/overwrite/chmod/socket-read/exec facility. Open parents relative to pinned anchors using O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC, leaves O_RDONLY|O_NOFOLLOW|O_CLOEXEC; compare dev/inode/type/uid/gid/mode/size/mtime_ns/ctime_ns/nlink/approved device and mount identities after open/before-after hashing and entry re-resolution. Never reopen after hashing to parse. Absence accepts only ENOENT beneath validated parent; recheck around dependent command. Socket is stat-only. Reject symlink, special file, untrusted writable parents or device/mount change. Source-owned executable modes can include execute bits but cannot be group/world writable.

Exclusive outputs use descriptor-relative O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC mode0600 under existing0700 R; no global umask mutation is needed because restrictive creation mode and parent identity are explicit. Verify owner/dev/inode/type/nlink/parent; streamed writes and fsync use bounded worker operation. Real writes change mtime/ctime/size: compare invariant identity fields, require exact final size/hash and approved stable final metadata, rather than using the fake port's unchanged timestamp simulation. Rehash final output through the same owned descriptor or an independently admitted exact no-follow verification open after write, validating identity before/after; this reopen is output verification, never input hash/parse TOCTOU. Operator input files are read/verified, never rewritten or fsynced through a read-only descriptor.

Only the explicitly enumerated file-transport recipe operations (approved input open/read/hash/metadata/absence, socket metadata, output inventory/statvfs/create/write/fsync/verify) are isolated in the worker. For their responses, the parent uses nonblocking IPC and checks the operation deadline; when scheduled after expiry it closes IPC, latches failure and initiates bounded worker cleanup. This is not a claim that all controller-side file or process activity is isolated or absolutely bounded: unchanged PR241 synchronously invokes subprocess.Popen from the controller before its responsive capture loop, including DEVNULL and process/exec setup. That startup may stall in the OS, and the Event monitor cannot make it return. Interpreter loss, kernel stalls and synchronous Popen have no guaranteed local-return deadline; external containment/watchdog must detect and quarantine them, including cases where no PreparationResult can be returned. The possibly blocked worker receives no later operation, output stream or command request. Kernel uninterruptibility may prevent cleanup; return unconfirmed/quarantine with no final receipt. Parent cannot promise that a previously issued kernel write produces no later side effect: incomplete files remain private and the entire root is quarantined until the owner resolves actual termination. No deletion/retry filename is permitted.

## Shared limits, deadlines and cancellation

All cumulative budgets are immutable, nonrenewable and charged across revalidations/finalization/failure paths. Use monotonic_ns internally; absolute attempt deadline is fixed at start, at most30min and shortened by dispatch expiry. Per-operation smaller remaining bound always wins; cleanup consumes outer time too.

| Resource | Ceiling |
| --- | --- |
| Regular inputs / all metadata entries |20,000 /40,000 including parent/absence/rechecks/output verification. |
| Input file / aggregate input / chunk |64MiB /1GiB /64KiB. |
| Each file or absence/metadata operation / shared file time |5s /300s; startup and verification count. |
| JSON document or derived model or output |16MiB each. |
| JSON values / nesting / UTF8 string / collection members |1,000,000 /64 /1MiB /20,000 per array or object. |
| Parse / validate / serialize operation / shared JSON time |5s each /60s total. |
| Each write/flush/fsync / shared output time |5s /60s total. |
| Combined command stdout+stderr / shared command bytes |16MiB /128MiB. |
| Persisted output / exact names |128MiB total /17 names. |
| Command ordinary/source |10s /30s; min with outer remaining. |
| Outer / free-space prerequisite |30min /1GiB available before every command and write. |
| Owned command TERM/KILL cleanup |2s then2s under PR241 shared per-command cleanup allowance, shortened by outer. |
| Worker retirement TERM/KILL |one2s+2s allowance for worker lifetime, shortened by outer; never reset per operation/error. |
| Capture/IPC/cancel scheduling poll |at most50ms when scheduled; no OS scheduling guarantee. |

Exactly one `process_transport.CaptureBudget(outer_deadline_ns,128MiB)` exists for all26 external commands. Call `process_transport.run(RunRequest(...), same_budget, same_threading_event)` only after manifest/provenance/prerequisite/free-space admission. No copy/reset/new ledger, arbitrary limits, alternate subprocess backend or nested subprocess wrapper. Consume opaque result bytes in <=64KiB slices with bounded parser and clear references after safe projection. Retain hashes/safe records only; never queue128MiB raw streams or include them in output data. Parser/serializer time checks occur before allocating next token/piece and at boundaries, not only after unrestricted json.loads/dumps.

Start the worker while controller is single-threaded, then one dedicated cancellation monitor may watch the approved owner cancellation FD and fixed attempt deadline. It sets the same threading.Event; EOF/lost owner channel is cancellation. The monitor never clears event, launches commands, performs worker I/O or reaps children. The adapter's own direct Python file-worker fork precedes this thread; no direct adapter worker re-fork/replacement is permitted. Later required subprocess.Popen calls still create command processes and may use fork/vfork internally after monitor launch. They remain exactly the unchanged PR241 spawn path, with no preexec_fn, process broker or purported interruptible-spawn wrapper. The worker fork ordering rule does not prohibit those required command spawns or claim their startup is bounded. Its shutdown/join is bounded; failure stops receipt completion. JSON/file/output operations also check cancellation at each chunk/boundary. There is no global handler or ambient interrupt reinterpretation.

RunRequest source vs ordinary deadlines are exactly PR241; earlier local operation breaches set the shared event so subsequent commands fail closed. A noncommand budget breach is terminal even if primitive ledger has bytes remaining. Worker lifecycle and active external command cleanup each have only their own once-created identity-bound allowance, both shortened by outer time; no repeated TERM/KILL loops. At most one external command is active; the worker is idle during command capture. After an outer expiry no fresh4s grace is invented.

## Hostile output, privacy and closed schemas

Raw file/command content remains transient. No raw stream files, exception repr/text, debug dumps, argv/env echo, crash attachment or arbitrary JSON passthrough. Prefix digests are labeled complete:false and cannot satisfy complete-output predicates. Secure memory erasure is not claimed; actual no-swap/core-dump controls remain owner obligations.

Use bounded incremental UTF8 parsing, reject duplicate keys at all depths, nonfinite/unsupported numbers, malformed UTF8, trailing data and all resource excess before allocation. Fixed problem codes plus integer counts/closed approved identifiers only. Never persist arbitrary rejected key names or hashes of their names; optional literal names PYTHON_VERSION/PYTHON_SHA256 may be emitted only by equality to that closed set, values always withheld.

Versions are approved product/version syntax <=512 chars. Daemon info requires empty proxies/linux and raw arch exactly amd64 or x86_64, storing raw safe architecture plus normalized amd64; image architecture exactly amd64. Daemon identity is hashed; any private raw identity needed for later launcher admission requires a separately explicit closed field approval within an existing name.

Actual image projection must not require the fake top-level six-key inspect shape or Config {Env,WorkingDir}: actual Docker returns additional keys. Instead accept a complete bounded inspect object transiently, require exactly one matching immutable ID/linux/amd64 plus complete Config/RootFS/RepoDigests, and project only the literal approved nonsecret schemas/layers/repository digests. Full Config values may persist only under literal owner/reviewer closed schema equality, with complete Config hash; absence of full safe approval blocks full Config evidence rather than replacing it with a digest. Runner Env permits exactly PATH/HOME/LANG/LC_ALL/TZ/SSL_CERT_FILE/SSL_CERT_DIR with duplicates/path validation; every extra key, including empty PYTHON_* entries, blocks. No schema is learned from the observed output. Existing frozen image pins are never replaced to gain compatibility.

Baseline must equal complete owner-approved candidate-derived model. Effective transformation removes test-runner, sets four exact image IDs and pull_policy never, removes runner build, replaces minio entire volumes list with sole `R/minio:/data`, yields exactly postgres/nats/minio/go-test-runner with no build. All other model fields remain exact. Persist complete models only if every literal/substitution is approved nonsecret; redaction is not valid complete-model evidence. Write effective.json inertly after baseline validation, once, before effective config. Unknown strings/keys/unsafe/private values cause withholding and terminal blocked/source_incompatible classification as appropriate; do not expand schemas from input.

## Cleanup and evidence schema

A command is usable only with `status:completed`, expected returncode, `cleanup:reaped`, full streams and no attempt fault. Primitive cleanup_unconfirmed always overrides apparent completion while preserving its primary_fault. Command group identity remains owned/private; retain leader WNOWAIT until final signalling, as implemented by PR241. Worker has separate owned group/reap logic with the same identity rule, fixed fault codes and no supplied PID/PGID. Never signal daemon, parent group, prior attempt or unrelated resources. EOF/direct-child reap is not proof escaped descendants exited.

Closed cleanup record fields:
`schema_version=1`, `record_stage` (`pre_finalization_snapshot|final_return`), `attempt_token`, `outer_deadline_ns`, `primary_fault` (null or fixed cancel/deadline/cap/storage/integrity/port_failure), `commands_started_count` (0..26), `command_cleanup` (tuple of closed command_id/status/primary_fault/returncode/cleanup/elapsed_ns/retained_bytes/stream_digest/complete records), `file_worker_started` (bool), `file_worker_cleanup` (`not_started|pending|reaped|unconfirmed`), `capture_descriptors_closed` (bool), `worker_ipc_closed` (bool), `monitor_stopped` (bool), `scope_termination_attestation_ref` (approved digest or null), `cleanup_status` (`not_started|pending|confirmed_local|unconfirmed`), `quarantine_required` (bool), `final_receipt_issued` (bool). No PID/raw paths/commands/errors. `confirmed_local` means only owned direct-child/descriptor lifecycle, never global host cleanup. External scope attestation remains separate provenance. A pending as-of observation is not an uncertainty/failure outcome: `pending` is legal only in the persisted pre-finalization snapshot, never in a successful final return. An actual uncertainty/fault sets quarantine_required true and final_receipt_issued false; a final return never hides it behind pending.

Persisted command-receipts.json contains only a `record_stage:pre_finalization_snapshot` cleanup record as of payload creation. With the started worker still serving output/verification, require file_worker_started true, file_worker_cleanup pending, worker_ipc_closed false, monitor_stopped false, cleanup_status pending, final_receipt_issued false and primary_fault null. Command capture descriptors may truthfully be closed/reaped at this point; this does not imply worker retirement. `quarantine_required:false` means no quarantine condition has been observed as of that snapshot, not a prediction about later cleanup. Classification.json also has `record_stage:pre_finalization_snapshot`, classification `preparation_finalization_pending`, final_receipt_issued false, and `predicate_assessment` exactly `evidenced|blocked_missing_input`, describing only predicates already checked. Neither file, nor REPORT, may claim COMPLETE, preparation_complete_execution_blocked, preparation_compatible_pending_execution_gate, worker reaped, monitor stopped or final receipt issued. REPORT explicitly states that its payloads are provisional until a separately returned final receipt authenticates this exact checksum digest.

The returned in-memory PreparationResult has `record_stage:final_return`; its cleanup record uses reaped/not_started or unconfirmed, never pending. A successful finalized return requires worker reaped, IPC closed, all command descriptors closed, monitor stopped, no fault/cancel/deadline breach, quarantine_required false and final_receipt_issued true. Only that returned result can expose the final preparation classification; its receipt includes `artifact_binding` with the SHA256 of complete SHA256SUMS and the exact command-receipts.json/classification.json digests already covered by SHA256SUMS. The result does not rewrite or reinterpret pending snapshots as retrospective completion claims. Failure/cancellation after checksums produces only an in-memory incomplete result with final_receipt_issued false, a preserved primary fault, observed local cleanup outcomes and quarantine when uncertain; it never produces a success receipt. The optional checksum binding in a failure result is an observed artifact digest only, not completion authority. If the controller cannot return because of a kernel/startup stall or interpreter loss, no final receipt exists and the independent owner watchdog handles unconfirmed/quarantine.

Only these17 names are legal under R:
owner-contract.json; dispatch.json; command-manifest.json; source-pins.json; file-observations.json; tool-observations.json; daemon-observations.json; image-observations.json; inventory-observations.json; compose-baseline.json; effective.json; compose-effective.json; command-receipts.json; classification.json; REPORT.md; SHA256SUMS; independent-review.md.

No eighteenth cleanup/status/receipt file: the provisional closed snapshot lives in command-receipts.json/classification.json as safe bounded data; final cleanup/completion and receipt remain in the in-memory return only. On terminal breach no new file is written, including no error/status update; retain an in-memory result for the owner channel when local return is possible. Partial or fully hashed provisional files alone never establish completion. Root or filename collision blocks; no rename/overwrite/unlink/retry cleanup. Operator owns first two files; reviewer alone owns independent-review.md; collector must neither fabricate nor finalize a reviewer result.

Closed once-only finalization sequence is `OBSERVED -> SNAPSHOT_WRITTEN -> REPORT_WRITTEN -> CHECKSUMS_WRITTEN -> ARTIFACTS_VERIFIED -> WORKER_RETIRED -> MONITOR_RETIRED -> FINAL_RETURN`. SNAPSHOT_WRITTEN means all admitted collector payloads, including the explicit pending snapshots, have been written once; REPORT remains pending-language; SHA256SUMS covers those exact collector/operator payloads and REPORT, excludes itself and future reviewer file. ARTIFACTS_VERIFIED uses the still-live worker for same-identity hashes/exact inventory, including no unexpected files. Only then retire/reap the worker, close IPC and stop/join the monitor. With the monitor retired, make one nonblocking cancellation-channel check (including EOF/loss), check the latched Event and outer deadline, then construct the bound final in-memory receipt/result. There is no file write after CHECKSUMS_WRITTEN and no state transition can alter earlier file bytes. Failure or cancellation at any transition goes to terminal INCOMPLETE, performs only permitted owned cleanup, leaves all existing bytes provisional, and returns no success receipt; a worker reap failure or monitor join failure must preserve unconfirmed/quarantine. Independent review must receive both the exact checksum inventory and its matching final receipt; files alone are insufficient. A source of failure after output finalization still withholds final receipt.

Classification is phase-specific: persisted pre-finalization snapshots/REPORT always use preparation_finalization_pending; only the final in-memory return maps BLOCKED/incomplete to collection_blocked/collection_incomplete, fully finalized preparation with missing host/full-created-container-shape to preparation_complete_execution_blocked, and all preparation predicates supported to preparation_compatible_pending_execution_gate. No read-only command proves newly created container HostConfig/network/mount exact shape; missing saved approved evidence remains blocked. Never create a discovery container.

## Concrete implementation milestones and verification

### Task1: Byte-preserving prerequisite adoption

Consumes new reviewed canonical checkpoint; produces four exact PR240 files alongside inherited PR241 pair.

- [ ] Before edits, rerun standalone/nested exact-base preflight, inspect dispatch/checkpoint and full ten-path allowlist.
- [ ] Adopt four files using immutable Git object contents from the PR240 pin; verify each SHA256/mode against source-pins.json. No historical code edit or docs-only branch merge.
- [ ] Run `python3 -I -B -m unittest discover -s scripts/r3_preparation -p 'test_*.py' -v`; expect the existing48 fake plus32 transport tests only. They use synthetic/owned local children, no installed Git/Docker calls.
- [ ] Prove all inherited entries/modes unchanged except four additions; commit/push `integrate(r3): preserve reviewed collector and subprocess primitives` and retain measured exact head/results. A failure blocks new adapter work pending separately authorized repair.

### Task2: Pure actual admission and immutable graph

Files: real_admission.py/test_real_admission.py. Consumes preserved bounded parser/types/constants, produces ActualContract/ApprovalBundle/Anchor definitions and `admit_actual`.

- [ ] Write red tests for absent/forged external approval binding, same operator/reviewer, synthetic approvals, historical checkpoint substitution, mutable/expired token, untrusted root/route/tool/config provenance, altered argv/order/env/cwd, repeated/missing IDs, unauthorized command, malformed exact types and all size/depth/string/member limits. Each case asserts zero port/command/worker activity.
- [ ] Write exact26 graph golden assertions including all Git versions blocked before complete config provenance, context-before-daemon, source-before-Compose, independent skip without retry, fixed cwd/kind and all four image pins.
- [ ] Add hostile projections for extra inspect keys transiently ignored under approved projection, unknown Config/body withholding, forbidden Env key names/values, invalid version/architecture/proxies, mismatched full model and poisoned dynamic diagnostics. Assert raw sentinels never enter safe objects.
- [ ] Implement minimal pure admission/projection, run focused test_real_admission.py, memory syntax compile and diff check; commit/push `feat(r3): admit immutable real preparation contracts`.

### Task3: Isolated descriptor I/O and cleanup

Files: file_transport.py/test_file_transport.py. Consumes admitted recipes/anchors, produces isolated bounded worker methods and cleanup record.

- [ ] Red owned-temp-tree tests: stable regular hash; matching/different exact config; symlink at each component, FIFO/socket/device leaf, wrong owner/mode/nlink/device, parent/leaf swap, absence creation, ENOENT vs EACCES, changed same descriptor, path depth, file64MiB+1, aggregate1GiB boundary via bounded test backend, metadata40001, strict no directory walking outside exact root output inventory.
- [ ] Red output tests: O_EXCL collision/symlink, mode0600/parent0700, partial writes/EINTR/ENOSPC, fsync fault, final size/time changes, same-inode substitution, added/unexpected file after checksums, no overwrite/remove/rename/retry, cancellation during output, exact128MiB cumulative and16MiB per-file boundaries.
- [ ] Red IPC/lifecycle tests: oversize/truncated/reordered/duplicate frame, no response, broken pipe, helper blocked stand-in, cancellation, ordinary SIGCHLD rejection, fork/setup failure, FD leak, deadline expiry during cleanup, exited leader pipe holder, cleanup_unconfirmed and quarantine. Fault injection is private test-only; no real uninterruptible disk/network resource is created.
- [ ] Use actual owned local worker/temp files to verify NOFOLLOW/exclusive/hash semantics; prove a waiting/stalled synthetic helper cannot block the parent loop beyond its accounting plus bounded cleanup. Test failure teardown owns every helper and never signals external IDs. Record OS timing limits honestly.
- [ ] Implement worker/IPC/descriptor mechanics, run focused suite with trusted existing interpreter, inspect imports/forbidden operations and exact tree scope; commit/push `feat(r3): isolate descriptor preparation I/O with bounded cleanup`.

### Task4: Real adapter orchestration using the primitive

Files: host_adapter.py/test_host_adapter.py. Consumes ActualContract, descriptor worker, PR241 run/CaptureBudget; produces collect_preparation and PreparationResult.

- [ ] Write red scripted tests for all26 commands and dependency skips, complete prerequisite revalidation around every call, free-space floor each start/write, only one shared CaptureBudget/event and one call per ID, first-fault latch/outer expiry, mandatory direct Python file-worker fork before monitor-thread ordering, owner cancel FD loss, no direct adapter worker fork/replacement after monitor launch, required later unchanged Popen calls allowed, and bounded monitor shutdown. Add private controlled startup-stall tests proving that setting the Event does not interrupt synchronous spawn; owner watchdog escalation/no-local-return is the claimed outcome, not fabricated bounded completion. Do not create an actual uninterruptible child or broker.
- [ ] Add owned synthetic Python-child tests of the actual binding: invalid UTF8/binary stderr, simultaneous hot streams, nonzero exit, expected symbolic exit1, exact16MiB/cap+1, shared budget exhaustion, cancellation/10s/30s deadlines as appropriate, cleanup_unconfirmed propagation and no final receipt after any cleanup/descriptor/monitor uncertainty. These substitute admitted test commands through a private backend only; production manifest still rejects Python -c and arbitrary commands.
- [ ] Add fixture-only full flow: baseline -> frozen effective output -> effective resolution -> provisional pending snapshot payloads -> pending-language REPORT -> sums -> identity/inventory verification -> worker retirement -> monitor retirement -> final channel/Event/deadline check -> checksum-bound in-memory receipt/result. On success inspect persisted snapshots for pending worker/cleanup, live monitor, false final_receipt_issued and preparation_finalization_pending; inspect only the final result for actual reaped/closed/stopped outcomes and final preparation classification. Assert its artifact_binding exactly matches SHA256SUMS and the snapshot digests. Independent review remains absent/reviewer-owned.
- [ ] Independently cancel immediately after SHA256SUMS, fail worker reap after ARTIFACTS_VERIFIED, and fail monitor join after WORKER_RETIRED. In every case compare all written bytes/digests to the pre-fault provisional snapshots, assert no post-fault writes/reopen-for-rewrite/new filename, no complete result/success receipt, and preserve primary fault plus actual cleanup/quarantine state. Cancel at every other finalization boundary too; a later return cannot retroactively change immutable snapshot meaning.
- [ ] Assert every serialized field is closed, all sensitive sentinels/unknown names withheld, prefix digests incomplete, full Config/model withheld when unsafe, actual markers distinct from immutable synthetic markers, credit0/all nine authorities false always.
- [ ] Implement orchestration, run all six new/old focused test files and meaningful primitive regression suite; memory syntax compilation and AST/static checks. Commit/push `feat(r3): bind preparation graph to reviewed bounded transports`.

### Task5: Independent exact-head code review and completion tracking

- [ ] Full suite command remains `python3 -I -B -m unittest discover -s scripts/r3_preparation -p 'test_*.py' -v` from clean owned builder checkout with login:false. No real installed Git/Docker/version/help/provider/secret probes. Temp file/worker/owned synthetic-child tests are explicitly code verification, not host compatibility.
- [ ] Compile source bytes in memory for ten new paths and inherited pair; `git diff --check` against actual planning checkpoint. Exhaustive Git tree compare proves exactly ten additions, four adopted hashes exact, subprocess pair unchanged, every unrelated entry/mode preserved. No bytecode/cache/untracked implementation artifacts.
- [ ] Independent exact-code-head review examines IPC allocation accounting, worker fork/FD/thread ordering, real output timestamps, race/no-follow behavior, PID/PGID/reap ownership, immutable graph, actual authentication boundary, primitive ledger reuse, hostile streams/projection, cumulative limits, cleanup/quarantine and truthful kernel/watchdog limitations. Reviewer does not implement repairs.
- [ ] Read normal exact-head CI without enabling runtime jobs. Preserve failures/skips/coverage gaps and predecessor Vercel failure; local focused tests are mandatory even if workflow does not discover them. A workflow modification needs a separate gate.
- [ ] Coordinator reserves tracking slot and appends measured code-only completion, review, exact SHA and unresolved blockers to canonical task/Issue186/Project8. Validated coherent milestones are promptly committed/pushed; no empty commits, published rewrite, merge or deployment.

## Separate actual host preparation execution gate

A code PASS does not authorize invoking collect_preparation on the real host. A later owner/coordinator must resolve and authenticate every actual identity/file/tool/plugin/config/clone/socket/env/storage/containment/watchdog/entrypoint contract, approve literal image Config/full model publication policy and17 filenames, pin exact reviewed adapter SHA and one fresh attempt, synchronize its own plan/spec/task/record/Issue186/Project8, commit/push, pass standalone/nested exact-checkpoint preflight, obtain independent gate review and explicit preparation-only dispatch. Missing kernel primitives, uninterruptible-worker containment, executable provenance, private-safe schema or owner identities blocks that gate.

That future dispatch permits only the graph above and inert approved evidence writes. Runtime execution remains separately gated after preparation review/compatibility repair. Read-only preparation does not waive created-container shape, runtime interruption/cleanup/quarantine, exact one-attempt full raw retained identity/catalog/commerce/paid/browser contracts, final180/profile promotion, authenticated publisher/staging lifecycle/schema/readiness/recovery, real Firebase login, Stripe TEST settled20USD grant/persistence/refund, both licensed banks, source/canonical/media/failure behavior, production payment/DNS/TLS/recovery/alerts or cars.tk cutover requirements.

This plan's diagnostics: trusted:false; runtime_accepted:false; host_observed:false; accepted_case_credit exact integer0; profiles_enabled:false; enabled_tiers:[]; runtime_lock:null; run_record:null; authority:false; fixture_verified:false; product_candidate_verified:false; staging_verified:false; deployment_authorized:false; cutover_verified:false; implementation_authorized:false; runtime_execution_authorized:false; profile_promotion_authorized:false; merge_authorized:false. Code-only dispatch later authorizes paths/tests through the canonical boundary, without turning these diagnostic authority fields true.

## Self-review

The plan covers integration before any adoption, exact new files, immutable predecessor preservation, actual-vs-synthetic admission, every command/dependency/cwd/environment, descriptor I/O/IPC, all policy budgets, resource ceilings, cancellation/fault precedence, truthful pending snapshots versus checksum-bound final return, output ordering/privacy, local cleanup/unconfirmed/quarantine, explicit synchronous Popen/no-local-return/watchdog/entrypoint gaps, direct-worker-fork-only thread ordering, concrete adversarial tests, code tracking and a distinct actual observation gate. No current owner/host/source-schema fact is asserted. It is decision-complete as a code-only adapter proposal, with named external prerequisites that intentionally remain blocked for activation.

## Source provenance pins

The following immutable source pins are copied verbatim in value from the reviewed source-pins.json. Four adoption files must match their PR240 bytes/modes; the inherited PR241 process pair must remain unchanged. All ten allowed implementation paths must be new regular mode100644 entries relative to the eventual planning checkpoint; no other entry or mode may change.

```json
{
  "git_pins": {
    "fake_code": "0da0be85b864ab829200d170a656ad6ea87651dd",
    "process_code": "8f0129cf21ca818c87eb1a3097ad055de9771082",
    "fake_docs_completion": "47f06f049ee97a57ebdbd3d034c13a303e166c39",
    "process_docs_completion": "b3e91e6a81db03b9bbb7615c3fb168bdc77c6834"
  },
  "implementation_source_pins": {
    "scripts/r3_preparation/policy.py": {
      "source_sha": "0da0be85b864ab829200d170a656ad6ea87651dd",
      "sha256": "36d8eb70f27277faefc831c1ca3ace18695509e97e4e65352ce0f3cb01120507",
      "git_mode": "100644"
    },
    "scripts/r3_preparation/collector.py": {
      "source_sha": "0da0be85b864ab829200d170a656ad6ea87651dd",
      "sha256": "3fddb096d25ca7f1281a41469d1ca846e2ae776f986390e6479fe9df5d573599",
      "git_mode": "100644"
    },
    "scripts/r3_preparation/test_policy.py": {
      "source_sha": "0da0be85b864ab829200d170a656ad6ea87651dd",
      "sha256": "3980f876f3d93197ec70d4281c1693051f7d1eaea33c28076a2502ecde7996d2",
      "git_mode": "100644"
    },
    "scripts/r3_preparation/test_collector.py": {
      "source_sha": "0da0be85b864ab829200d170a656ad6ea87651dd",
      "sha256": "20557de448cd3a51fcf780627c2a016a6605b91b3f485e3590d4d41cb59863af",
      "git_mode": "100644"
    },
    "scripts/r3_preparation/process_transport.py": {
      "source_sha": "8f0129cf21ca818c87eb1a3097ad055de9771082",
      "sha256": "ebfb286f8048437ddc222c0ee1fb7475be2667a5b225174c61f4ea8ef0d3be4c",
      "git_mode": "100644"
    },
    "scripts/r3_preparation/test_process_transport.py": {
      "source_sha": "8f0129cf21ca818c87eb1a3097ad055de9771082",
      "sha256": "2d452341a1946b7dc2080dee59d1053324f019d0e90f104c999a6f4a15ee74bd",
      "git_mode": "100644"
    }
  },
  "external_sources_sha256": {
    "/home/corp/autodata-evidence/r3-preparation-collector-code-review-revision2/receipt.json": "90160c9864e18abbbf62204a7e9e78d548a45806539c6ee54e59e320d0eff304",
    "/home/corp/autodata-evidence/r3-preparation-collector-code-review-revision2/report.md": "acd3bafb95287cf6002038c04d1f27d79be9c648c11b58adff69ffcbb14fc82d",
    "/home/corp/autodata-evidence/r3-process-transport-code-review/verdict.json": "22a3e192f22e17a68917235b3cc3d8794a4c1538cc7e55892128ed3e522e4e39",
    "/home/corp/autodata-evidence/r3-process-transport-code-review/REPORT.md": "9aa143989a5b99ee102ece951783afb3d4a12349d48cd0a3e82b68712f2d4829",
    "/home/corp/autodata-evidence/r3-process-transport-code-tracking/receipt.json": "3e38bf3a56f17fb1b436173c0e2f5b5b09ae5e0ed877073ce00a639f73e7e75a",
    "/home/corp/autodata-evidence/r3-process-transport-completion-docs/receipt.json": "9cb33f982d8f95857aa34a0e69b49d40a8d4d587aabbe7885acaa6389edb9089",
    "/home/corp/autodata-evidence/r3-preparation-collector-completion-docs/receipt.json": "1a6538412f023e822e758b396c4fb173541b4510be9d6dce5ebf29c2c1cd1b52",
    "/home/corp/autodata-evidence/r3-preparation-gate-draft/PLAN.md": "55d0b1ea66e4125d033e4eaa8a6caf7c77da9fd32925cbbcedc56e75fa59ed2a"
  }
}
```

## Canonical draft planning record and literal todo

Issue: https://github.com/lucronn/autodata/issues/186. Project: https://github.com/users/lucronn/projects/8. The standalone record below is identical to the task's nested `pre_implementation` object and is synchronized to live coordinator readback https://github.com/lucronn/autodata/issues/186#issuecomment-6641148122. Its `synchronized` status records tracking, not implementation or host execution authority. The full pushed checkpoint SHA is bound externally after commit; exact-base preflight, independent checkpoint review and explicit ten-path dispatch remain separate conditions. The independent external revision2 plan PASS does not certify a future code or host run.

```json
{
  "schema_version": 1,
  "goal": "Implement an independently reviewable Linux preparation adapter that binds approved host/file/Git/Docker observations to the reviewed subprocess primitive, bounded descriptor I/O, nonrenewable budgets, safe evidence projection, and conservative cleanup; defer actual host observations to a separate preparation execution gate.",
  "plan_ref": "docs/superpowers/plans/2026-11-04-workshop-r3-real-preparation-adapter.md",
  "spec_ref": "docs/agents/specs/2026-11-04-workshop-r3-real-preparation-adapter.md",
  "record_ref": "docs/agents/records/2026-11-04-workshop-r3-real-preparation-adapter.json",
  "task_ref": "docs/agents/tasks/2026-11-03-production-release/workshop-r3-real-preparation-adapter.json",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/agents/specs/2026-11-04-workshop-r3-real-preparation-adapter.md",
    "docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md"
  ],
  "todo": [
    "Freeze PR241 code parent 8f0129cf21ca818c87eb1a3097ad055de9771082 and PR240 four-file adoption pin 0da0be85b864ab829200d170a656ad6ea87651dd; synchronize the dedicated six-path canonical gate and Issue186/Project8, pin the actual checkpoint, pass standalone/nested preflight and independent exact-checkpoint review before ten-path code-only dispatch.",
    "Adopt the four reviewed fake collector files byte-for-byte under the new gate, preserve the inherited subprocess primitive pair, and verify the integrated synthetic and owned-child suites without host probes.",
    "Implement and adversarially test pure actual-contract admission and the immutable 26-command dependency graph, keeping synthetic admission and historical checkpoints unchanged.",
    "Implement and adversarially test isolated descriptor I/O, bounded IPC, exclusive output creation, nonrenewable limits and owned worker cleanup with explicit unconfirmed/quarantine outcomes.",
    "Bind actual orchestration to one reviewed subprocess CaptureBudget and cancellation event, preserve synchronous Popen/startup watchdog limitations and direct-worker-fork-only thread ordering, enforce truthful pending snapshots versus checksum-bound final in-memory completion, and verify using only scripted ports, owned temporary files and owned synthetic children.",
    "Commit and promptly push validated coherent milestones, obtain independent exact-head review and honest normal CI readback, then synchronize measured code-only completion and all unresolved activation/runtime/release blockers with credit0 and false authorities."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-04T20:21:18Z",
  "planning_status": "tracking_synchronized_checkpoint_review_pending",
  "tracking_status": "synchronized",
  "planning_base_sha": "8f0129cf21ca818c87eb1a3097ad055de9771082",
  "planning_parent_sha": "8f0129cf21ca818c87eb1a3097ad055de9771082",
  "planning_parent_tree": "de1855c3534b82dc551ea59c527f24f1f2b3e9b8",
  "implementation_base_sha": null,
  "execution_gate_sha": null,
  "integration_head_sha": null,
  "scope": "proposed_code_only_adapter_library_and_synthetic_owned_local_verification",
  "allowed_gate_document_paths": [
    "docs/superpowers/plans/2026-11-04-workshop-r3-real-preparation-adapter.md",
    "docs/agents/specs/2026-11-04-workshop-r3-real-preparation-adapter.md",
    "docs/agents/records/2026-11-04-workshop-r3-real-preparation-adapter.json",
    "docs/agents/tasks/2026-11-03-production-release/workshop-r3-real-preparation-adapter.json",
    "docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md",
    "docs/agents/tasks/2026-11-03-production-release/queue.json"
  ],
  "allowed_implementation_paths": [
    "scripts/r3_preparation/policy.py",
    "scripts/r3_preparation/collector.py",
    "scripts/r3_preparation/test_policy.py",
    "scripts/r3_preparation/test_collector.py",
    "scripts/r3_preparation/real_admission.py",
    "scripts/r3_preparation/file_transport.py",
    "scripts/r3_preparation/host_adapter.py",
    "scripts/r3_preparation/test_real_admission.py",
    "scripts/r3_preparation/test_file_transport.py",
    "scripts/r3_preparation/test_host_adapter.py"
  ],
  "adoption_only_paths": [
    "scripts/r3_preparation/policy.py",
    "scripts/r3_preparation/collector.py",
    "scripts/r3_preparation/test_policy.py",
    "scripts/r3_preparation/test_collector.py"
  ],
  "new_implementation_paths": [
    "scripts/r3_preparation/real_admission.py",
    "scripts/r3_preparation/file_transport.py",
    "scripts/r3_preparation/host_adapter.py",
    "scripts/r3_preparation/test_real_admission.py",
    "scripts/r3_preparation/test_file_transport.py",
    "scripts/r3_preparation/test_host_adapter.py"
  ],
  "immutable_inherited_paths": [
    "scripts/r3_preparation/process_transport.py",
    "scripts/r3_preparation/test_process_transport.py"
  ],
  "implementation_file_mode": "100644",
  "fake_adoption_sha": "0da0be85b864ab829200d170a656ad6ea87651dd",
  "fake_adoption_tree": "4564cf95aeb73cb453af5daaedb9d1a6df18c1c7",
  "future_gate_branch": "codex/workshop-r3-real-preparation-adapter-gate",
  "future_builder_branch": "codex/workshop-r3-real-preparation-adapter-build",
  "source_document_sha256": {
    "/home/corp/autodata-evidence/r3-real-adapter-successor-plan/PLAN.md": "c535581b08361b61b19e90759955a34d0a9380452e660c04456708d7b5db9971",
    "/home/corp/autodata-evidence/r3-real-adapter-successor-plan/tracking-payload.json": "173ce872e7ea98042a26e8ce2e47ec8efc2850bccc70a58f8150bd51b97e7728",
    "/home/corp/autodata-evidence/r3-real-adapter-successor-plan/source-pins.json": "afd4cdab1a42a547969b8d7f04a198a16e06517eec0a0d76f6f6a6a6f9801993",
    "/home/corp/autodata-evidence/r3-real-adapter-successor-plan/validation.json": "bf9f35dfdca6cb17a9eff66c67b4b65868968773ab6c6ce8bf2f4b9faf151024",
    "/home/corp/autodata-evidence/r3-real-adapter-plan-independent-review/revision2/verdict.json": "f8da765bd15c287e43559c35642104b98be2251bfceb99ca2299f4dd09454b9f"
  },
  "source_pins": {
    "git_pins": {
      "fake_code": "0da0be85b864ab829200d170a656ad6ea87651dd",
      "process_code": "8f0129cf21ca818c87eb1a3097ad055de9771082",
      "fake_docs_completion": "47f06f049ee97a57ebdbd3d034c13a303e166c39",
      "process_docs_completion": "b3e91e6a81db03b9bbb7615c3fb168bdc77c6834"
    },
    "implementation_source_pins": {
      "scripts/r3_preparation/policy.py": {
        "source_sha": "0da0be85b864ab829200d170a656ad6ea87651dd",
        "sha256": "36d8eb70f27277faefc831c1ca3ace18695509e97e4e65352ce0f3cb01120507",
        "git_mode": "100644"
      },
      "scripts/r3_preparation/collector.py": {
        "source_sha": "0da0be85b864ab829200d170a656ad6ea87651dd",
        "sha256": "3fddb096d25ca7f1281a41469d1ca846e2ae776f986390e6479fe9df5d573599",
        "git_mode": "100644"
      },
      "scripts/r3_preparation/test_policy.py": {
        "source_sha": "0da0be85b864ab829200d170a656ad6ea87651dd",
        "sha256": "3980f876f3d93197ec70d4281c1693051f7d1eaea33c28076a2502ecde7996d2",
        "git_mode": "100644"
      },
      "scripts/r3_preparation/test_collector.py": {
        "source_sha": "0da0be85b864ab829200d170a656ad6ea87651dd",
        "sha256": "20557de448cd3a51fcf780627c2a016a6605b91b3f485e3590d4d41cb59863af",
        "git_mode": "100644"
      },
      "scripts/r3_preparation/process_transport.py": {
        "source_sha": "8f0129cf21ca818c87eb1a3097ad055de9771082",
        "sha256": "ebfb286f8048437ddc222c0ee1fb7475be2667a5b225174c61f4ea8ef0d3be4c",
        "git_mode": "100644"
      },
      "scripts/r3_preparation/test_process_transport.py": {
        "source_sha": "8f0129cf21ca818c87eb1a3097ad055de9771082",
        "sha256": "2d452341a1946b7dc2080dee59d1053324f019d0e90f104c999a6f4a15ee74bd",
        "git_mode": "100644"
      }
    },
    "external_sources_sha256": {
      "/home/corp/autodata-evidence/r3-preparation-collector-code-review-revision2/receipt.json": "90160c9864e18abbbf62204a7e9e78d548a45806539c6ee54e59e320d0eff304",
      "/home/corp/autodata-evidence/r3-preparation-collector-code-review-revision2/report.md": "acd3bafb95287cf6002038c04d1f27d79be9c648c11b58adff69ffcbb14fc82d",
      "/home/corp/autodata-evidence/r3-process-transport-code-review/verdict.json": "22a3e192f22e17a68917235b3cc3d8794a4c1538cc7e55892128ed3e522e4e39",
      "/home/corp/autodata-evidence/r3-process-transport-code-review/REPORT.md": "9aa143989a5b99ee102ece951783afb3d4a12349d48cd0a3e82b68712f2d4829",
      "/home/corp/autodata-evidence/r3-process-transport-code-tracking/receipt.json": "3e38bf3a56f17fb1b436173c0e2f5b5b09ae5e0ed877073ce00a639f73e7e75a",
      "/home/corp/autodata-evidence/r3-process-transport-completion-docs/receipt.json": "9cb33f982d8f95857aa34a0e69b49d40a8d4d587aabbe7885acaa6389edb9089",
      "/home/corp/autodata-evidence/r3-preparation-collector-completion-docs/receipt.json": "1a6538412f023e822e758b396c4fb173541b4510be9d6dce5ebf29c2c1cd1b52",
      "/home/corp/autodata-evidence/r3-preparation-gate-draft/PLAN.md": "55d0b1ea66e4125d033e4eaa8a6caf7c77da9fd32925cbbcedc56e75fa59ed2a"
    }
  },
  "external_plan_review_ref": "/home/corp/autodata-evidence/r3-real-adapter-plan-independent-review/revision2/verdict.json",
  "external_plan_review_result": "PASS",
  "external_plan_review_scope": "independent_external_code_only_plan_revision2_review",
  "closed_external_findings": [
    "F1",
    "F2"
  ],
  "tracking_sync": {
    "status": "synchronized_live_readback",
    "writer": "coordinator sole serialized writer",
    "goal": "Implement an independently reviewable Linux preparation adapter that binds approved host/file/Git/Docker observations to the reviewed subprocess primitive, bounded descriptor I/O, nonrenewable budgets, safe evidence projection, and conservative cleanup; defer actual host observations to a separate preparation execution gate.",
    "todo": [
      "Freeze PR241 code parent 8f0129cf21ca818c87eb1a3097ad055de9771082 and PR240 four-file adoption pin 0da0be85b864ab829200d170a656ad6ea87651dd; synchronize the dedicated six-path canonical gate and Issue186/Project8, pin the actual checkpoint, pass standalone/nested preflight and independent exact-checkpoint review before ten-path code-only dispatch.",
      "Adopt the four reviewed fake collector files byte-for-byte under the new gate, preserve the inherited subprocess primitive pair, and verify the integrated synthetic and owned-child suites without host probes.",
      "Implement and adversarially test pure actual-contract admission and the immutable 26-command dependency graph, keeping synthetic admission and historical checkpoints unchanged.",
      "Implement and adversarially test isolated descriptor I/O, bounded IPC, exclusive output creation, nonrenewable limits and owned worker cleanup with explicit unconfirmed/quarantine outcomes.",
      "Bind actual orchestration to one reviewed subprocess CaptureBudget and cancellation event, preserve synchronous Popen/startup watchdog limitations and direct-worker-fork-only thread ordering, enforce truthful pending snapshots versus checksum-bound final in-memory completion, and verify using only scripted ports, owned temporary files and owned synthetic children.",
      "Commit and promptly push validated coherent milestones, obtain independent exact-head review and honest normal CI readback, then synchronize measured code-only completion and all unresolved activation/runtime/release blockers with credit0 and false authorities."
    ],
    "issue_ref": "https://github.com/lucronn/autodata/issues/186",
    "project_ref": "https://github.com/users/lucronn/projects/8",
    "repository_doc_refs": [
      "docs/agents/specs/2026-11-04-workshop-r3-real-preparation-adapter.md",
      "docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md"
    ],
    "planning_parent_sha": "8f0129cf21ca818c87eb1a3097ad055de9771082",
    "planning_paths": [
      "docs/superpowers/plans/2026-11-04-workshop-r3-real-preparation-adapter.md",
      "docs/agents/specs/2026-11-04-workshop-r3-real-preparation-adapter.md",
      "docs/agents/records/2026-11-04-workshop-r3-real-preparation-adapter.json",
      "docs/agents/tasks/2026-11-03-production-release/workshop-r3-real-preparation-adapter.json",
      "docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md",
      "docs/agents/tasks/2026-11-03-production-release/queue.json"
    ],
    "future_implementation_paths": [
      "scripts/r3_preparation/policy.py",
      "scripts/r3_preparation/collector.py",
      "scripts/r3_preparation/test_policy.py",
      "scripts/r3_preparation/test_collector.py",
      "scripts/r3_preparation/real_admission.py",
      "scripts/r3_preparation/file_transport.py",
      "scripts/r3_preparation/host_adapter.py",
      "scripts/r3_preparation/test_real_admission.py",
      "scripts/r3_preparation/test_file_transport.py",
      "scripts/r3_preparation/test_host_adapter.py"
    ],
    "issue_comment": "https://github.com/lucronn/autodata/issues/186#issuecomment-6641148122",
    "issue_before_sha256": "c1fc95253f45309547335bc11f26f31af65049091d639280baffcee7bdb9ae72",
    "issue_after_sha256": "c4070be4162ba5c243567fbd3578410bb3e536c757809d4aa7ee2e04e9ad0101",
    "project_before_sha256": "071bf6e936f7d05d10df063013f0786019a0806990effb8fda768e832b5c78e9",
    "project_after_sha256": "903926783f7e868aa7ce2637300c095ba6d0f2822e7fa44e7e91c54ae9e83a14",
    "receipt_ref": "/home/corp/autodata-evidence/r3-real-adapter-gate-tracking/receipt.json",
    "receipt_sha256": "f1ea9c4ed4f2acd8b43a3f365df10c6b9633d28866538dada44fac63ecc8cf48",
    "accepted_case_credit": 0,
    "readback_verified": true
  },
  "implementation_blockers": [
    "The pushed documentation checkpoint must pass exact-base standalone/nested preflight and independent exact-checkpoint review before any builder dispatch.",
    "Explicit coordinator ten-path code-only dispatch remains required; tracking synchronization is not implementation authorization."
  ],
  "execution_blockers": [
    "actual named operator/reviewer/cancellation/host/daemon/tool-installation/watchdog identities and authenticated artifacts",
    "exact approved embedding entry point and inherited descriptor handoff",
    "immutable actual host/tool/plugin/runtime/Git-config/clone/socket/env/output manifests",
    "owner-verified resource containment/watchdog/no-swap/no-core/cleanup acceptance",
    "complete literal nonsecret image Config and Compose model schemas",
    "separate canonical preparation execution checkpoint, machine preflight, independent gate review and one-attempt dispatch",
    "A separate initial host runtime execution/acceptance gate remains required after reviewed real preparation; no container creation or service/provider/payment/release authority is supplied."
  ],
  "finalization_contract": {
    "persisted_record_stage": "pre_finalization_snapshot",
    "persisted_classification": "preparation_finalization_pending",
    "persisted_started_worker_cleanup": "pending",
    "persisted_cleanup_status": "pending",
    "persisted_worker_ipc_closed": false,
    "persisted_monitor_stopped": false,
    "persisted_final_receipt_issued": false,
    "final_return_record_stage": "final_return",
    "final_return_pending_allowed": false,
    "final_return_artifact_binding": [
      "complete_SHA256SUMS_sha256",
      "command-receipts.json_sha256",
      "classification.json_sha256"
    ],
    "states": [
      "OBSERVED",
      "SNAPSHOT_WRITTEN",
      "REPORT_WRITTEN",
      "CHECKSUMS_WRITTEN",
      "ARTIFACTS_VERIFIED",
      "WORKER_RETIRED",
      "MONITOR_RETIRED",
      "FINAL_RETURN"
    ],
    "post_checksum_file_writes_allowed": false,
    "post_fault_file_writes_allowed": false,
    "post_checksum_faults_require_incomplete_no_success_receipt": [
      "cancellation",
      "worker_reap_failure",
      "monitor_join_failure"
    ],
    "root_output_name_count": 17
  },
  "startup_contract": {
    "direct_adapter_python_worker_fork_before_monitor": true,
    "direct_adapter_worker_refork_allowed": false,
    "later_unchanged_Popen_spawns_allowed": true,
    "Popen_may_use_fork_or_vfork": true,
    "Popen_synchronous_controller_startup": true,
    "Event_interrupts_blocked_Popen": false,
    "guaranteed_local_return_during_kernel_startup_or_interpreter_stall": false,
    "file_worker_isolation_scope": "enumerated approved file-transport recipe operations only",
    "watchdog_required_for": [
      "initial_worker_startup",
      "synchronous_command_Popen_exec_startup_stall",
      "controller_or_interpreter_loss",
      "outer_attempt_expiry"
    ],
    "new_process_broker": false,
    "primitive_repair": false,
    "preexec_fn": false
  },
  "host_execution_authorized": false,
  "implementation_dispatched": false,
  "runtime_execution_scope": [],
  "host_execution_scope": [],
  "implementation_dispatch": null,
  "preparation_execution_dispatch": null,
  "normal_ci_predecessor": "PR241 Vercel failed; no autonomous-verification job was present; no CI PASS claimed.",
  "trusted": false,
  "runtime_accepted": false,
  "host_observed": false,
  "accepted_case_credit": 0,
  "profiles_enabled": false,
  "enabled_tiers": [],
  "runtime_lock": null,
  "run_record": null,
  "authority": false,
  "release_state": "unverified",
  "fixture_verified": false,
  "product_candidate_verified": false,
  "staging_verified": false,
  "deployment_authorized": false,
  "cutover_verified": false,
  "implementation_authorized": false,
  "runtime_execution_authorized": false,
  "profile_promotion_authorized": false,
  "merge_authorized": false,
  "authorities": {
    "fixture_verified": false,
    "product_candidate_verified": false,
    "staging_verified": false,
    "deployment_authorized": false,
    "cutover_verified": false,
    "implementation_authorized": false,
    "runtime_execution_authorized": false,
    "profile_promotion_authorized": false,
    "merge_authorized": false
  }
}
```

Tracking readback: https://github.com/lucronn/autodata/issues/186#issuecomment-6641148122; external gate-draft review PASS (31 independent checks), verdict SHA256 `158a8116d0ad03e1e65a5b37a64d6adf3ba25b548557c3ae236b1ad4a39a3944`. This is tracking/scope evidence only; code, actual host preparation and runtime remain unverified.


### R3 real preparation adapter conditional code-only completion — 2026-11-04

Status: `conditional_code_only_completion_docs_pending_independent_review`. This documentation overlay references code candidate `e88f8a9602ea9dcb67b1de31b281a8f0eb0faa4a` ([PR #247](https://github.com/lucronn/autodata/pull/247)) and preserves planning checkpoint `20b2696fcfeef580b43aeb026567e1ab9dd010ee` ([PR #244](https://github.com/lucronn/autodata/pull/244)). Independent successor whole-head review returned `PASS_CODE_ONLY` at this exact code SHA; receipt `/home/corp/autodata-evidence/r3-real-final-code-review/revision2/verdict.json` records no findings, 130 independently rerun tests OK and six startup fault probes. Exact-head CI readback at `/home/corp/autodata-evidence/code-ci-exact-readback/20261104T205541Z` shows no `Autonomous Verification` Actions run: all ten changed paths are under `scripts/r3_preparation/`, outside the workflow path filters. Vercel exact-head failure has an unconfirmed cause from available GitHub status/log readback; an earlier quota bot comment predates this head and is context only. Cursor Bugbot is neutral. These statuses establish neither application code pass nor application code failure. No normal CI PASS, host compatibility or execution authority is claimed; documentation-head CI cannot substitute for code-head CI.

The builder reports 130 offline tests OK; that original claim remains identified as builder evidence. Separate independent revision2 review confirms 130 tests OK (56.455s), six startup fault probes, exact ten-path scope, immutable predecessor hashes/modes and standalone/nested canonical preflight at gate20b2696. This closes original F1/P2 startup cleanup propagation from the retained original FINDINGS review at28803ae. The specific WorkerStartupFault lifecycle closure preserves the original reason and single retirement allowance; failed constructed workers propagate cleanup/quarantine truthfully. This documentation worker ran no application tests, owned synthetic children or actual host observations. The predecessor PR240 code pin remains `0da0be85b864ab829200d170a656ad6ea87651dd`; the PR241 code pin remains `8f0129cf21ca818c87eb1a3097ad055de9771082`. Their immutable source hashes/modes and historical review/test evidence remain unchanged. Historical PR241 Vercel failure and absent autonomous-verification job do not establish successor CI status; documentation CI cannot substitute for code CI.

This addendum follows the four-path completion documentation precedent of PR238 exact `47f06f049ee97a57ebdbd3d034c13a303e166c39` and PR239 exact `b3e91e6a81db03b9bbb7615c3fb168bdc77c6834`. Original gate goal, todo, synchronization fields, source pins and nested pre-implementation record remain historical data. The queue and specification are unchanged. The coordinator synchronized conditional completion tracking with matching Issue186/Project8 readback at https://github.com/lucronn/autodata/issues/186#issuecomment-6641900979; receipt `/home/corp/autodata-evidence/r3-real-completion-tracking/receipt.json` preserves prior Project Source and other fields. That tracking readback preceded documentation adoption and did not claim it complete. The documentation worker makes no GitHub writes. Independent review of this finalized overlay, canonical adoption and exact docs-head readback remain pending. The retained `completion_draft` JSON key is an additive completion note; its explicit status records this overlay stage.

Actual preparation still requires separately authenticated actual identities, approved embedding entry point and descriptor handoff, immutable host/tool/plugin/runtime/Git-config/clone/socket/environment/output manifests, owner-verified containment/watchdog/no-swap/no-core/cleanup acceptance, literal image Config/full Compose schemas, and its own committed synchronized execution gate, exact-base preflight, independent gate review and one-attempt preparation-only dispatch. The adapter's pending persisted snapshots versus checksum-bound final returned result and synchronous Popen/kernel/interpreter watchdog limitations remain mandatory. No actual host observation, initial runtime probe, fixture, final180, provider/payment, staging, deployment or release acceptance follows from this documentation overlay.

All authorities remain false, including `trusted:false`, `host_observed:false`, `runtime_accepted:false`, host/preparation/runtime execution, implementation, fixture/product/staging, deployment/cutover, promotion and merge. Accepted-case credit is integer `0`; profiles remain disabled, runtime_lock/run_record null and release unverified. No new implementation scope is proposed.
