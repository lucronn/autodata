# Workshop final180 Stage B1 identity translation and fake replay specification

**Status: Issue186/Project8 planning synchronized.** The current tracking receipt is https://github.com/lucronn/autodata/issues/186#issuecomment-6637529257. No implementation or runtime dispatch is authorized by this document alone. The committed checkpoint, exact-base preflight, independent gate review and explicit coordinator dispatch remain required.

**Goal:** Add only an in-memory identity Go JSONL adapter and finite fake-runtime replay for the five frozen identity IDs; preserve Stage A and zero accepted-case credit, disabled profiles and every authority false.

**Plan:** `docs/superpowers/plans/2026-11-04-workshop-final180-stage-b1-identity.md`. **Task:** `docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-b1-identity.json`. **Record:** `docs/agents/records/2026-11-04-workshop-final180-stage-b1-identity.json`.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

Planning parent is exact reviewed Stage A `2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e`; application candidate remains `4d82e413e04fb2401ac7bc28dc828375ac662180`. These are distinct from the future authorizing planning checkpoint and implementation SHA. Preserve Stage A's files, historical gate, CHECKPOINT_SHA and CLI semantics. Only the three implementation paths below may change after a separate passing gate.

This specification promotes the corrected external draft by exact digest. The coordinator reported independent draft review PASS; no independent review receipt is invented here. Embedded source JSON retains historical external-draft labels and pending-rereview metadata verbatim; those describe the source artifact and do not override this proposal's code-only planning status or claim a committed-gate review. All technical decisions, five active mappings and complete source-derived pin tables are committed within this spec; the external historical locators are audit references, not required builder inputs. References below to `literal-mappings.json` and `provenance.json` mean the embedded verbatim appendices in this file. No separate mutable mapping or provenance file is consulted at runtime.

## Decision and sufficiency

The sources are sufficient for this restricted code slice. They are insufficient for a complete six-family semantic raw validator, real process/Docker supervisor, or real180 execution gate. The corrected addendum resolves outer SQL column/nullability, source route/outcome expectations, selected runtime projections and nominal support inventories; it expressly does not prove nested JSONB semantics, emitted JUnit/plugin shapes, runtime artifacts, or all independent assertions.

This proposal deliberately selects one useful translation boundary rather than claiming all raw validators are now specified. It translates identity Go run/terminal events, strengthens the weak producer checks with exact Package/run multiplicity/package-terminal requirements already identified by Stage A, and rehearses bounded termination decisions with fake events. It neither validates identity migration/JUnit/provenance/raw-row semantics nor labels identity fixture evidence verified. The other 175 IDs remain unimplemented in this slice, not implicitly passed or unavailable rows emitted into a full180 result. The source root/package/pytest/support cases add zero logical IDs.

## Immutable source and provenance

- Application candidate: `4d82e413e04fb2401ac7bc28dc828375ac662180`.
- Inventory gate: `d8579c824eb1ebf546b46b13a0f69079890ad44e`, file `docs/agents/specs/2026-11-04-workshop-final180-inventory.json`, exact SHA256/bytes recorded in provenance.json. Full frozen counts remain identity5/catalog8/commerce14/paid12/browser_dto120/browser_api21, total180.
- Stage A synchronized plan/spec/record/task context: `b8ffaa39e6b9104df67f69541ce4da8a936adc0f`; exact Git blobs and SHA256 values recorded in provenance.json. This checkpoint authorizes only Stage A, never this proposal.
- Reviewed Stage A runner head and exact proposed planning parent: `2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e`, with exact runner/test/runbook blobs in provenance.json. This draft consumes its frozen `Observation` shape conceptually; it does not change/import that module, repin its CHECKPOINT_SHA, or change its inspect/reconcile/run CLI behavior.
- Prior report `/home/corp/autodata-evidence/final180-stage-b-schema/report.json`, SHA256 `48e915ad5589331e5718105f6dbbcfcdb967d3e92fcb73be0602bb700f89afaa`.
- Corrected addendum `/home/corp/autodata-evidence/final180-stage-b-gap-closure/report.json`, SHA256 `36670a61779baa5ec2dd40d879b485c32d2a41907e1f971507ad450ca1a679ae`. The artifact hashes it names are verified in provenance.json; the stale earlier addendum is not an input.
- Direct source truth for active translation: candidate `scripts/dev/production_access_smoke.py` GO_ROOT/GO_NAMES/GO_IDS/go_results, candidate `scripts/dev/test_production_access_smoke.py` conditional Go bridge and `go test -json` invocation, candidate `apps/api-go/postgres_auth_sessions_test.go` literal root and five `t.Run` calls, and candidate `apps/api-go/go.mod` package identity. Pin these exact bytes; do not import producer code or discover IDs from a mutable checkout.
- `literal-mappings.json` contains all180 IDs copied byte-for-byte and ordered from the immutable inventory, but only the five entries in `active_identity_mapping` are active. It includes no new case IDs.


Direct immutable source citations (all at application4d82e413; exact line text/hash in provenance.json):

| Source | Lines | Fact |
|---|---|---|
| scripts/dev/production_access_smoke.py |16-20| root/five literal IDs |
| scripts/dev/production_access_smoke.py |107-115| existing weak Go validator |
| scripts/dev/production_access_smoke.py |125-126,154-159| process/no-timeout gate and raw-event consumption |
| scripts/dev/test_production_access_smoke.py |52-57,72-74,89| conditional bridge, Go JSONL argv,180s source timeout, exit receipt fields |
| apps/api-go/postgres_auth_sessions_test.go |47,58,127,177,204-205| root and five actual Go child declarations |
| apps/api-go/go.mod |1| exact package module |

The existing collector's `go_results` admits multiple run events and does not check Package/final package success. That is a documented validator gap, not a sufficient proof rule. The stronger profile below is an explicit proposed design restriction, not a claim about observed Go output. The report states Go versions can change fields/actions. An unsupported actual event shape must fail closed in any future adapter gate; compatibility with an actual tool version remains unproven.

## Exact allowed implementation changes after the synchronized B1 gate

Implementation allowlist, exactly:

1. Create `scripts/dev/workshop_final180_identity_adapter.py`: bytes-only parse/translate/fake-replay library; no CLI or executable entrypoint.
2. Create `scripts/dev/test_workshop_final180_identity_adapter.py`: offline unittest fixtures and fake event sequences, no captured genuine-run claim.
3. Modify `docs/verification/workshop-final180-runbook.md`: document the library's synthetic-only trust boundary and continued blocked successors, preserving Stage A command semantics.

No change to `scripts/dev/workshop_final180_runner.py`, its tests, producers, assembler, evaluator, acceptance profiles/policy, application, SQL, Compose, CI/workflows, package/dependency files or existing inventory. No arbitrary runtime callback/protocol implementation, subprocess import, `os.kill`, Docker/socket/HTTP/browser client, filesystem artifact collector, runtime-lock parser, service argv renderer, run command or automatic retry.

Coordinator-only planning paths for this synchronized B1 scope are: `docs/superpowers/plans/2026-11-04-workshop-final180-stage-b1-identity.md`, `docs/agents/specs/2026-11-04-workshop-final180-stage-b1-identity.md`, `docs/agents/records/2026-11-04-workshop-final180-stage-b1-identity.json`, `docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-b1-identity.json`; the canonical product-evidence assembler plan identifies this exact blocked successor. These are not included in implementation worker scope. Do not overwrite Stage A's historical gate.

## Exact public Python contracts

All dataclasses frozen, tuple collections, concrete types checked (bool is never int), no caller authority/count/ID/argv fields. `AdapterError(ValueError)` carries only one stable code from the table below. No mutable JSON is an execution plan.

```python
@dataclass(frozen=True)
class IdentityContext:
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str

@dataclass(frozen=True)
class GoEvent:
    time: str
    action: str
    package: str
    test: str | None
    elapsed: int | float | None
    output: str | None
    failed_build: str | None

@dataclass(frozen=True)
class SimulatedExit:
    exit_code: int | None
    timed_out: bool
    interrupted: bool
    ownership_lost: bool
    cleanup_complete: bool

@dataclass(frozen=True)
class CaseOutcome:
    family: str                 # literal identity
    logical_id: str             # one of the five frozen full IDs
    status: str                 # passed|failed|skipped|unavailable
    raw_refs: tuple[str, ...]   # fixed retained-memory refs, never filesystem reads

@dataclass(frozen=True)
class IdentityDiagnostic:
    contract: str               # workshop-final180-identity-synthetic-v1
    observation_kind: str       # simulated-source-profile-validation
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str
    events_sha256: str
    stderr_sha256: str
    status: str                 # consistent|inconsistent|unavailable|interrupted
    observations: tuple[CaseOutcome, ...]
    failures: tuple[str, ...]
    accepted_case_credit: int   # always 0
    profiles_enabled: bool     # always False
    enabled_tiers: tuple[str, ...]  # always empty; serialized []
    authority: tuple[tuple[str, bool], ...]

@dataclass(frozen=True)
class FakeFrame:
    at_ns: int
    kind: str                  # stdout|stderr|exit|cancel|identity_lost|term_exit|kill_exit
    data: bytes                # only stdout/stderr; else b''
    code: int | None           # only exit/term_exit/kill_exit

@dataclass(frozen=True)
class FakeReplay:
    result: SimulatedExit
    stdout: bytes
    stderr: bytes
    decisions: tuple[tuple[int, str], ...]
    # decision values: timeout|cancel|ownership_lost|term|kill|cleanup_complete|leftover

parse_identity_events(raw: bytes) -> tuple[GoEvent, ...]
translate_identity(events_raw: bytes, stderr_raw: bytes,
                   receipt: SimulatedExit, context: IdentityContext) -> IdentityDiagnostic
replay_identity_fake(frames: tuple[FakeFrame, ...]) -> FakeReplay
serialize_identity_diagnostic(value: IdentityDiagnostic) -> bytes
```

Outer events_raw must be bytes<=67108864 and stderr_raw must be bytes<=1048576; wrong concrete type or these hard byte ceilings raise AdapterError before hashing, with no diagnostic. Codes are input_type/events_size/stderr_type/stderr_size. Context errors use context_invalid, receipt errors receipt_invalid, serializer shape/authority errors diagnostic_invalid. Context requires exact candidate above, inventory SHA256 equal to the immutable inventory pin in provenance.json, and lowercase64 source-manifest digest. This is caller-supplied context under simulation; even a matching digest does not prove a source inspection occurred. No API accepts a real-execution receipt or upgrades this trust label. `SimulatedExit` fields have exact concrete types; exit_code is null or signed int in [-255,255], no bool. A normal simulated receipt must have a code; null is permitted only for timed_out/interrupted/ownership_lost or cleanup failure. Invalid context/receipt raises AdapterError before parsing. Only fixed active IDs and raw refs enter the result.

`translate_identity` validates inputs and performs all parsing before state evaluation; parser error within the admitted outer byte limits becomes an unavailable diagnostic containing all five outcomes unavailable, never a successful parsed prefix. Public parse raises AdapterError. Caller/receipt/context schema errors raise AdapterError without a diagnostic. SHA256 of raw bytes is always recorded in a successfully returned diagnostic, even malformed JSONL; raw bytes/Output/Time/errors/paths never appear in diagnostic text. stderr is retained and hashed as opaque bytes; it is not searched for success/failure text.

## JSONL grammar and bounded Go profile

Input bytes: at most67108864; 1..65536 LF-delimited nonempty JSON lines; each line at most1048576 bytes excluding LF. A final single LF is optional; CRLF and blank lines are rejected, including interior/extra terminal blank lines. Strict UTF8, no BOM, duplicate JSON keys, NaN/Infinity, null in a present field, or non-object line. Per JSON nesting <=32; every decoded string <=65536 UTF8 bytes. Reject surrogate codepoints. Top-level keys exactly required `Time,Action,Package` plus optional `Test,Elapsed,Output,FailedBuild`; unknown keys reject. This table is an explicitly restricted simulated profile, not an admitted Go-version compatibility claim.

- Time: nonempty string<=128 UTF8 bytes. It is an opaque producer timestamp and never controls deadlines/order/acceptance. No timestamp semantic inference.
- Package: nonempty string<=256 UTF8 bytes syntactically; semantic validation requires exact `github.com/lucronn/autodata/apps/api-go` on every event.
- Action: permitted `start,run,output,pass,fail,skip`. Known Go `pause,cont,bench` and any other action fail unavailable with `unsupported_go_action`; no silent dropping.
- Test if present: nonempty string<=256 UTF8 bytes syntactically; semantic validation requires exact root or one full active child ID. Unknown/nested/foreign Test is a protocol failure after parsing, not a synthesized extra case. Preserve event occurrences.
- Elapsed if present: concrete int or float, finite 0..86400; absent maps to None. It is observational metadata, never a deadline source.
- Output if present: string (empty allowed), only with action output; action output requires it. It may include embedded newlines escaped in JSON; no raw line splitting after decode. Time/Output strings do not supply IDs or outcome claims.
- FailedBuild if present: nonempty string<=1024 bytes, only package-level fail (Test absent), yielding failure. It does not supply a package override.
- start must be package-level with no Test. run requires Test. pass/fail/skip may be package-level or test-level. No other action-specific optional-key restrictions beyond these rules; irrelevant Elapsed remains bounded and ignored.

Parser errors: `input_type`, `events_size`, `events_count`, `line_size`, `line_delimiter`, `json_invalid`, `json_duplicate_key`, `json_nonfinite`, `json_depth`, `json_string`, `event_keys`, `event_type`, `unsupported_go_action`. Package mismatch is semantic `package_mismatch`, not a parser prefix success. Unknown fields are unavailable; known invalid Test/Package identities are inconsistent. No API accepts `passed`, `assertion_results`, aggregate counts or authority booleans as a success substitute.

## Literal case mapping and state/result rules

Exactly the root `TestPostgresAuthSessionsIntegration` plus these five children; root is support only:

| Test in raw Go event | Output family/logical ID |
|---|---|
| TestPostgresAuthSessionsIntegration/ConcurrentCustomerProvisionAndRotation | identity / identical full Test string |
| TestPostgresAuthSessionsIntegration/SharedSessionRevocation | identity / identical full Test string |
| TestPostgresAuthSessionsIntegration/ExpiryAndPersistedSecrecy | identity / identical full Test string |
| TestPostgresAuthSessionsIntegration/FirebaseExchangeAndUserRevocation | identity / identical full Test string |
| TestPostgresAuthSessionsIntegration/FirebaseStartupRequiresMigratedPostgres | identity / identical full Test string |

No suffix stripping, substring/fuzzy matching, count-only reconciliation, pytest/parent duplication, DTO/API substitution or set-deduplication. Emission order is precisely the table/inventory order, independent of event arrival order.

A clean simulated stream requires: exactly one package start as first event; exactly one package terminal pass as final event; exactly one run and exactly one terminal pass for root and each child; every terminal after that Test's run; each child run/terminal lies after root run and before root terminal; no test output outside that Test's run..terminal interval; package output may appear between package start and terminal; no fail or skip anywhere; no unknown/nested Test or wrong Package. Repeated output is allowed and adds no cases. Interleaved different child tests are allowed within the root interval. Package run is invalid. Additional package starts/terminals, duplicate runs/terminals and events after a terminal are failures; preserve duplicates to detect them.

Semantic failures use a fixed bounded code vocabulary: `package_mismatch`, `unknown_test`, `package_lifecycle`, `root_lifecycle`, `child_lifecycle:0`..`:4`, `root_failed`, `root_skipped`, `package_failed`, `package_skipped`, `child_failed:0`..`:4`, `child_skipped:0`..`:4`, `simulated_nonzero`, `simulated_timeout`, `simulated_interrupted`, `ownership_lost`, `cleanup_incomplete`. Codes are emitted once in that order (within an indexed group,0..4); no source string interpolation. A skipped Test with one run and one terminal skip is structurally well-formed but nonpassing. Missing/duplicate/out-of-order terminal is lifecycle failure. Structural lifecycle failure takes precedence over skip/pass for the affected Test.

Result precedence and exact outcome mapping:

1. Invalid bytes/profile -> status unavailable, all5 unavailable, parser's stable code; receipt problems are additionally recorded in fixed code order. No parsed-prefix output.
2. Interrupted receipt -> status interrupted, all5 unavailable, even if raw events are all clean.
3. Ownership loss, incomplete cleanup, timeout, nonzero exit, package/root structural failure, package/root fail, unknown Test or wrong Package -> status inconsistent, all5 failed. This intentionally prevents a child pass hiding invalid family support.
4. With otherwise valid package/root support: per child missing/duplicate/order error or fail -> failed; exact one run+one skip -> skipped; exact run+pass -> passed. Any nonpassed child -> inconsistent; all5 passed -> consistent.
5. Root/package skip -> status inconsistent, all5 skipped, unless higher rule3 applies. If root skipped before children ran, missing child rows do not override all5 skipped; those lifecycle codes are retained as diagnostic failures. Nothing becomes a pass because the subprocess exited0.

Each row has raw_refs exactly `('r5-access-go-events.jsonl','r5-access-go-stderr.log')`, backed by the two bytes arguments retained by the caller/fake replay. These refs are never opened. This is a retained-memory diagnostic contract, not a claim that source minimum disk artifacts exist. No normalized full180 file, execution receipt, fixture-verified evidence or acceptance envelope is emitted. `consistent` means only consistency with this simulated restricted event profile.

## Finite fake-runtime contract and budgets

Only FakeFrame tuples are accepted. There is no injected callback that can block or execute commands. Max65536 frames, exact field types, integer at_ns in[0,190000000000], nondecreasing input order. Every kind requires data to be concrete bytes: stdout/stderr may carry any bytes within the chunk limits; every other kind requires exactly b''. For each exit/term_exit/kill_exit frame, code MUST be a concrete int (bool rejected) in[-255,255], never None. For stdout/stderr/cancel/identity_lost, code MUST be None, never an int or bool. Wrong code/type/presence raises fake_code before replay; wrong data/type/presence raises fake_frame_type. No frame kind or caller field can contain argv/env/PID/path/network authority. Fake time is integer nanoseconds starting0; no sleep, wall clock or OS signals.

The planned source Go bridge limit is180s; this fake's child deadline is exactly180000000000ns. A timeout/cancel at trigger T gets one cleanup interval ending C=min(T+10000000000,190000000000), with a TERM grace endpoint K=T+5000000000. No second trigger replenishes these values. All frames undergo complete shape/time/byte-budget validation first; then replay merges frames with dynamically scheduled actions. The following table is the TOTAL ordering at any equal timestamp, lowest rank first; input frame index breaks ties within the same kind. Scheduled actions are singletons. Generated actions at that timestamp are inserted immediately at their table rank before later-ranked frames.

| Rank | Event/action | Enabled state/effect |
|---|---|---|
|0|identity_lost|Any nonterminal state: record ownership_lost, terminate replay as leftover, cancel every scheduled action; no TERM/KILL at that timestamp or later.|
|1|cancel|Running only: set interrupted, choose trigger T, schedule TERM at T/KILL at K/leftover at C and disarm child timeout; during cleanup it is a no-op and does not change flags/deadlines/log.|
|2|scheduled child timeout|Running only at180s: set timed_out, choose trigger T and schedule TERM/KILL/leftover; otherwise disarmed.|
|3|scheduled TERM|Owned triggered state only at T: record term and enter TERM-wait; never enabled following ownership loss.|
|4|scheduled KILL|Owned TERM-wait only at K: record kill and enter KILL-wait; a term_exit at K is consequently too late.|
|5|scheduled cleanup leftover|Any incomplete owned cleanup at C: record leftover and finish incomplete; a kill_exit at C is consequently too late.|
|6|exit|Running before child deadline: normal terminal exit; exactly at trigger T in TERM-wait: TERM acknowledgement retaining adverse flag; any other cleanup time is fake_cleanup_sequence.|
|7|term_exit|TERM-wait and T<=time<K only: terminal cleanup acknowledgement; otherwise fake_cleanup_sequence.|
|8|kill_exit|KILL-wait and K<=time<C only: terminal cleanup acknowledgement; otherwise fake_cleanup_sequence.|
|9|stdout|Running only: append bytes; after a trigger it is fake_cleanup_sequence; after normal exit it is fake_after_exit.|
|10|stderr|Same rule as stdout.|

Only enabled scheduled actions execute. Any acknowledgement/exit finalizes replay and disarms subsequent scheduled actions. Remaining input frames must still be checked: after normal exit ANY further frame (including equal-time later-ranked frames) raises fake_after_exit; after a cleanup acknowledgement, leftover or ownership loss ANY further frame raises fake_cleanup_sequence. These checks prevent a late ownership-loss claim or duplicate terminal from being silently dropped. Before terminal completion, equal-time ownership loss wins over every other frame/action; cancel wins over a scheduled timeout; scheduled TERM wins over an equal-time term_exit; scheduled KILL wins over an equal-time term_exit/kill_exit; scheduled leftover wins over an equal-time kill_exit. This removes dependence on caller tuple order across different frame kinds.

Normal exit before deadline: collect preceding stdout/stderr; result.exit_code is that frame's mandatory int, adverse flags false, cleanup_complete=true; no TERM/KILL decision. An EOF without exit advances virtual time to the child deadline and runs timeout, TERM, KILL and leftover as applicable; no indefinite polling. For owned timeout/cancel cleanup, accepted term_exit/kill_exit (or exit exactly at T) records its mandatory code and cleanup_complete=true, without clearing the timed_out/interrupted flag. Ownership loss sets ownership_lost=true, exit_code=None and cleanup_complete=false. Cleanup with no accepted acknowledgement by C sets exit_code=None and cleanup_complete=false.

Decision log is at most4 entries: the trigger timeout/cancel, term, optionally kill, and terminal cleanup_complete/leftover/ownership_lost. Ownership loss before a trigger emits only ownership_lost; ownership loss after a trigger replaces the final cleanup_complete/leftover entry, never adds a separate leftover. Frames at timestamps before their required acknowledgement state, more than one terminal acknowledgement or ordinary exit strictly after T during cleanup raise fake_cleanup_sequence. Earliest enabled adverse trigger wins; a later cancel is a no-op, not a new trigger. Returning cleanup_complete never clears interrupted/timed_out, so clean raw cannot hide timeout/cancel.

Bounds are enforced before retaining another chunk: stdout<=64MiB, stderr<=1MiB, aggregate<=65MiB; per chunk<=1MiB. Overflows are AdapterError(`fake_stdout_size|fake_stderr_size|fake_chunk_size`) with no replay object and no success prefix. No truncation, recompression, retry or actual file emission. All bytes are supplied by the test caller; no private disk or real quota is allocated. Fake errors: `fake_frames`, `fake_frame_type`, `fake_time`, `fake_kind`, `fake_code`, `fake_after_exit`, `fake_cleanup_sequence` and the size codes above. Source-wide4GiB/100000-file quotas and real cleanup ownership checks remain future execution design, not implemented here.

## Output limits and authority

Serializer validates diagnostic shape and fixed strings/IDs before canonical UTF8 JSON with sorted keys, compact separators and one LF; all failures fixed codes, hashes lowercase64, booleans concrete. Max65536 bytes; overflow -> AdapterError(`diagnostic_size`), no partial serialized output. No disk output, user paths, exception messages, stderr content, Go Output or synthetic provider secrets. Exactly5 CaseOutcome rows and at most64 unique failure codes are required for EVERY returned/serialized diagnostic, including unavailable/interrupted. observations must be a tuple with family exactly identity in every row; logical IDs must be unique and equal the five full IDs in literal-mappings.json active_identity_mapping in that exact order, with no missing, extra, repeated or reordered row. The serializer revalidates this, statuses/raw_refs and all fixed fields, including diagnostic status/outcome rules, instead of trusting a caller-constructed dataclass. Any malformed row cardinality/order/identity or profile metadata raises diagnostic_invalid with no bytes emitted. The library is importable only; Stage A CLI remains inspect/reconcile, `run` still usage error before output creation.

Authority tuple exactly these keys, in this order, every value false: fixture_verified, product_candidate_verified, staging_verified, deployment_authorized, cutover_verified, implementation_authorized, runtime_execution_authorized, profile_promotion_authorized, merge_authorized. IdentityDiagnostic has explicit fields accepted_case_credit=0 (concrete int, bool rejected), profiles_enabled=False (concrete bool), and enabled_tiers=() (exact empty tuple). Its serialized JSON includes the exact top-level keys contract,observation_kind,candidate_sha,inventory_sha256,source_manifest_sha256,events_sha256,stderr_sha256,status,observations,failures,accepted_case_credit,profiles_enabled,enabled_tiers,authority; profiles_enabled serializes as false and enabled_tiers as []. authority serializes as an object with exactly the nine keys above, every value false. Observation rows serialize as objects with exactly family,logical_id,status,raw_refs; tuple fields serialize as arrays. Missing/unknown top-level keys are impossible from the fixed serializer; caller-constructed values with nonempty tiers, true profiles or authority, nonzero credit, malformed hashes/status/rows fail diagnostic_invalid. Proposal report metadata separately carries profiles_enabled=false and enabled_tiers=[], matching rather than replacing the diagnostic contract. A code gate may authorize a coordinator-dispatched worker only after preflight; that authorization never arises from a diagnostic's booleans. No merge/deploy/real fixture run follows a passing unit test.


## Review repair examples (normative, synthetic only)

These examples specify outcomes for future unit tests; no replay implementation or runtime test was executed while drafting.

| Input/example | Required result |
|---|---|
|FakeFrame(0,'exit',b'',None), or terminal code True|fake_code before replay; no FakeReplay. Same rule for term_exit/kill_exit.|
|FakeFrame(0,'stdout',b'x',0), or cancel with code False|fake_code before replay; no FakeReplay. Every nonterminal kind requires None.|
|exit(code0) at179999999999ns, no other frames|SimulatedExit(0,False,False,False,True), empty decisions; translation can be consistent only with complete clean raw stream.|
|exit(code0) at180000000000ns, no other frames|timeout rank2, TERM rank3, exit rank6 as exact-trigger acknowledgement; SimulatedExit(0,True,False,False,True), decisions [(180s,timeout),(180s,term),(180s,cleanup_complete)]; translation inconsistent/all5 failed.|
|cancel and term_exit(code0) both at10s (either input tuple order)|cancel rank1, generated TERM rank3, term_exit rank7; SimulatedExit(0,False,True,False,True), decisions [(10s,cancel),(10s,term),(10s,cleanup_complete)]; translation interrupted/all5 unavailable.|
|cancel at10s; identity_lost and term_exit(code0) both at11s (either tuple order)|ownership_lost rank0 forbids signals after11s and terminates leftover; the remaining term_exit is rejected with fake_cleanup_sequence, never ignored or counted as a successful acknowledgement.|
|cancel at10s; term_exit(code0) at14999999999ns|TERM acknowledgement before K=15s; cleanup_complete=true, interrupted stays true.|
|cancel at10s; term_exit(code0) at15s|scheduled KILL rank4 occurs before term_exit rank7; term_exit is the wrong acknowledgement for KILL-wait, so fake_cleanup_sequence and no replay object.|
|cancel at10s; kill_exit(code0) at15s|scheduled KILL rank4 then kill_exit rank8; cleanup_complete=true with decisions cancel,term,kill,cleanup_complete; interrupted stays true.|
|cancel at10s; kill_exit(code0) at20s|scheduled leftover rank5 at C=20s precedes kill_exit rank8; terminal-after-leftover is fake_cleanup_sequence and no replay object.|
|cancel at10s; identity_lost at15s, no later frames|ownership_lost rank0 disarms scheduled KILL rank4; decisions [(10s,cancel),(10s,term),(15s,ownership_lost)]; no kill; SimulatedExit(None,False,True,True,False).|
|identity_lost and cancel both at10s|ownership_lost wins; remaining cancel after terminal is fake_cleanup_sequence. No TERM/KILL is emitted and no successful replay is returned.|
|cancel at10s; cancel and kill_exit(code0) at15s|later cancel is a no-op rank1; KILL rank4 occurs on original15s endpoint then kill_exit rank8 completes; deadlines/flags/log unchanged by second cancel.|
|No frames|virtual180s timeout/TERM,185s KILL,190s leftover; SimulatedExit(None,True,False,False,False), exactly4 decisions; no polling/sleep.|
|Clean five rows with profiles_enabled=False, enabled_tiers=()|serialized JSON contains profiles_enabled:false, enabled_tiers:[], accepted_case_credit:0 and exactly the five ordered row objects.|
|Four rows, six rows, duplicate ID replacing another row, reversed rows, or wrong family|diagnostic_invalid with no serialized bytes, even if status claims consistent.|
|Five valid rows but profiles_enabled=True, enabled_tiers=('x',), or credit=True|diagnostic_invalid with no serialized bytes.|



## Remaining dynamic facts and separate successor gates

- Exact host Python/Git/Docker/Go executable paths/digests/versions; image recipes/digests and complete offline dependency/browser cache manifests; concrete owned create/start/inspect/stop/remove argv; service settings/network/storage ownership; operator identity; run authorization;8GiB headroom/4GiB real raw quota, retention locator and immutable external run/lock record remain unobserved. B1 consumes none and must not invent them.
- Actual Go output version/optional fields/action compatibility remains unobserved. The restricted profile can be tested and fail closed now; accepting an observed new profile needs reviewed spec/tests rather than widening at run time. Go JSONL shape cannot prove migration/SDK/auth/security correctness by itself.
- JUnit support expectations are source-resolved (identity nominal57, commerce67 incl53 support; catalog8, paid12 outer+1 child, API21 outer; DTO120 direct rows); emitted classnames/attributes/plugin/teardown/error-node behavior remain unknown. All support credit stays0. No JUnit parser is included.
- SQL outer fields and declared nullability are source-resolved; nested JSONB business semantics, runtime UUID/time/token values and independent invariants remain outside this slice. No SQL row parser or permissive opaque-data acceptance rule is introduced.
- Paid HTTP expected routes/body outcomes are source-derived, not runtime observations. Browser API request capture is a distinct producer. No response/rights/media/browser acceptance claims follow from a five-ID adapter.
- Dynamic worker/runtime/browser-home/support files and real artifact totals remain unknown. DTO traces<=16MiB can exceed existing8MiB acceptance transport. Future run must preserve oversized raw, never truncate/chunk/recompress to satisfy current acceptance; B1 allocates no trace transport or disk artifact budget.

A later full Stage B gate must make those applicable code contracts explicit and separately bind real tools/argv/run authority before execution. It cannot inherit this B1 draft as permission to execute fixtures or promote acceptance profiles.

## Promoted external artifact identity

The exact artifacts used for promotion are retained by byte length and SHA256 below. Their external paths are historical locators. Review/status metadata in embedded artifacts is historical, never current gate authority.

```json
{
  "DRAFT.md": {
    "bytes": 42142,
    "historical_locator": "/home/corp/autodata-evidence/final180-stage-b-gate-draft/DRAFT.md",
    "sha256": "1e596d2d71c11b90a4428ac094c397703706063b065261c3957ca82218284ca1"
  },
  "literal-mappings.json": {
    "bytes": 11648,
    "historical_locator": "/home/corp/autodata-evidence/final180-stage-b-gate-draft/literal-mappings.json",
    "sha256": "2611386c2074a870d67e04cc1152e2f0e4e8d32d4b62f52864b8117ae513dfdb"
  },
  "provenance.json": {
    "bytes": 35452,
    "historical_locator": "/home/corp/autodata-evidence/final180-stage-b-gate-draft/provenance.json",
    "sha256": "15e6ce82e507747dd2a93b9adca7c1e461c1a47e239305d6d620a0530ef37fb9"
  },
  "report.json": {
    "bytes": 3480,
    "historical_locator": "/home/corp/autodata-evidence/final180-stage-b-gate-draft/report.json",
    "sha256": "f8ee1a1c0bfdb3e2dbf3410937a790d30ac4247464a543763bb08596f31c1588"
  }
}
```

## Embedded literal-mappings.json (verbatim)

```json
{
  "active_identity_mapping": [
    {
      "accepted_case_credit": 0,
      "family": "identity",
      "logical_id": "TestPostgresAuthSessionsIntegration/ConcurrentCustomerProvisionAndRotation",
      "raw_refs": [
        "r5-access-go-events.jsonl",
        "r5-access-go-stderr.log"
      ],
      "raw_test": "TestPostgresAuthSessionsIntegration/ConcurrentCustomerProvisionAndRotation"
    },
    {
      "accepted_case_credit": 0,
      "family": "identity",
      "logical_id": "TestPostgresAuthSessionsIntegration/SharedSessionRevocation",
      "raw_refs": [
        "r5-access-go-events.jsonl",
        "r5-access-go-stderr.log"
      ],
      "raw_test": "TestPostgresAuthSessionsIntegration/SharedSessionRevocation"
    },
    {
      "accepted_case_credit": 0,
      "family": "identity",
      "logical_id": "TestPostgresAuthSessionsIntegration/ExpiryAndPersistedSecrecy",
      "raw_refs": [
        "r5-access-go-events.jsonl",
        "r5-access-go-stderr.log"
      ],
      "raw_test": "TestPostgresAuthSessionsIntegration/ExpiryAndPersistedSecrecy"
    },
    {
      "accepted_case_credit": 0,
      "family": "identity",
      "logical_id": "TestPostgresAuthSessionsIntegration/FirebaseExchangeAndUserRevocation",
      "raw_refs": [
        "r5-access-go-events.jsonl",
        "r5-access-go-stderr.log"
      ],
      "raw_test": "TestPostgresAuthSessionsIntegration/FirebaseExchangeAndUserRevocation"
    },
    {
      "accepted_case_credit": 0,
      "family": "identity",
      "logical_id": "TestPostgresAuthSessionsIntegration/FirebaseStartupRequiresMigratedPostgres",
      "raw_refs": [
        "r5-access-go-events.jsonl",
        "r5-access-go-stderr.log"
      ],
      "raw_test": "TestPostgresAuthSessionsIntegration/FirebaseStartupRequiresMigratedPostgres"
    }
  ],
  "active_scope": "identity Go JSONL profile translation only; all others reference-only",
  "candidate_sha": "4d82e413e04fb2401ac7bc28dc828375ac662180",
  "contract": "workshop-final180-stage-b1-external-mappings-v1",
  "expected_case_ids": {
    "browser_api": [
      "test_browser_google_exchange_checkout_library_real_api[chromium]",
      "test_browser_google_exchange_checkout_library_real_api[firefox]",
      "test_browser_google_exchange_checkout_library_real_api[webkit]",
      "test_browser_owned_source_canonical_and_media_real_api[chromium-bankone]",
      "test_browser_owned_source_canonical_and_media_real_api[chromium-banktwo]",
      "test_browser_owned_source_canonical_and_media_real_api[firefox-bankone]",
      "test_browser_owned_source_canonical_and_media_real_api[firefox-banktwo]",
      "test_browser_owned_source_canonical_and_media_real_api[webkit-bankone]",
      "test_browser_owned_source_canonical_and_media_real_api[webkit-banktwo]",
      "test_browser_account_scope_and_revocation_real_api[chromium-bankone]",
      "test_browser_account_scope_and_revocation_real_api[chromium-banktwo]",
      "test_browser_account_scope_and_revocation_real_api[firefox-bankone]",
      "test_browser_account_scope_and_revocation_real_api[firefox-banktwo]",
      "test_browser_account_scope_and_revocation_real_api[webkit-bankone]",
      "test_browser_account_scope_and_revocation_real_api[webkit-banktwo]",
      "test_browser_signed_refund_blocks_old_links_real_api[chromium-bankone]",
      "test_browser_signed_refund_blocks_old_links_real_api[chromium-banktwo]",
      "test_browser_signed_refund_blocks_old_links_real_api[firefox-bankone]",
      "test_browser_signed_refund_blocks_old_links_real_api[firefox-banktwo]",
      "test_browser_signed_refund_blocks_old_links_real_api[webkit-bankone]",
      "test_browser_signed_refund_blocks_old_links_real_api[webkit-banktwo]"
    ],
    "browser_dto": [
      "chromium::bankone-cascade",
      "chromium::banktwo-cascade",
      "chromium::dual-bank-coverage",
      "chromium::one-bank-unavailable",
      "chromium::pending-no-content",
      "chromium::source-to-canonical",
      "chromium::source-rewrite-failure",
      "chromium::review-required",
      "chromium::warm-reload",
      "chromium::selection-change-in-flight",
      "chromium::source-review-change-in-flight",
      "chromium::cancel-and-retry",
      "chromium::history-restore",
      "chromium::document-only",
      "chromium::missing-media",
      "chromium::withdrawal",
      "chromium::keyboard-print-mobile",
      "chromium::source-media-isolation",
      "chromium::auth-cookie-reload",
      "chromium::google-popup-exchange",
      "chromium::google-popup-blocked",
      "chromium::google-popup-cancelled",
      "chromium::google-stale-reauthentication",
      "chromium::firebase-memory-persistence",
      "chromium::signin-unavailable-local",
      "chromium::signin-malformed-config",
      "chromium::session-expired",
      "chromium::session-blocked",
      "chromium::auth-dependency-unavailable",
      "chromium::quote-exact-scope",
      "chromium::terms-config-unavailable",
      "chromium::checkout-double-click-retry",
      "chromium::checkout-processing-return",
      "chromium::checkout-untrusted-return",
      "chromium::checkout-expired",
      "chromium::already-owned-no-pay",
      "chromium::library-pagination-and-states",
      "chromium::paid-prepare-before-poll",
      "chromium::media-renew-coalesced",
      "chromium::logout-and-bfcache-clear",
      "firefox::bankone-cascade",
      "firefox::banktwo-cascade",
      "firefox::dual-bank-coverage",
      "firefox::one-bank-unavailable",
      "firefox::pending-no-content",
      "firefox::source-to-canonical",
      "firefox::source-rewrite-failure",
      "firefox::review-required",
      "firefox::warm-reload",
      "firefox::selection-change-in-flight",
      "firefox::source-review-change-in-flight",
      "firefox::cancel-and-retry",
      "firefox::history-restore",
      "firefox::document-only",
      "firefox::missing-media",
      "firefox::withdrawal",
      "firefox::keyboard-print-mobile",
      "firefox::source-media-isolation",
      "firefox::auth-cookie-reload",
      "firefox::google-popup-exchange",
      "firefox::google-popup-blocked",
      "firefox::google-popup-cancelled",
      "firefox::google-stale-reauthentication",
      "firefox::firebase-memory-persistence",
      "firefox::signin-unavailable-local",
      "firefox::signin-malformed-config",
      "firefox::session-expired",
      "firefox::session-blocked",
      "firefox::auth-dependency-unavailable",
      "firefox::quote-exact-scope",
      "firefox::terms-config-unavailable",
      "firefox::checkout-double-click-retry",
      "firefox::checkout-processing-return",
      "firefox::checkout-untrusted-return",
      "firefox::checkout-expired",
      "firefox::already-owned-no-pay",
      "firefox::library-pagination-and-states",
      "firefox::paid-prepare-before-poll",
      "firefox::media-renew-coalesced",
      "firefox::logout-and-bfcache-clear",
      "webkit::bankone-cascade",
      "webkit::banktwo-cascade",
      "webkit::dual-bank-coverage",
      "webkit::one-bank-unavailable",
      "webkit::pending-no-content",
      "webkit::source-to-canonical",
      "webkit::source-rewrite-failure",
      "webkit::review-required",
      "webkit::warm-reload",
      "webkit::selection-change-in-flight",
      "webkit::source-review-change-in-flight",
      "webkit::cancel-and-retry",
      "webkit::history-restore",
      "webkit::document-only",
      "webkit::missing-media",
      "webkit::withdrawal",
      "webkit::keyboard-print-mobile",
      "webkit::source-media-isolation",
      "webkit::auth-cookie-reload",
      "webkit::google-popup-exchange",
      "webkit::google-popup-blocked",
      "webkit::google-popup-cancelled",
      "webkit::google-stale-reauthentication",
      "webkit::firebase-memory-persistence",
      "webkit::signin-unavailable-local",
      "webkit::signin-malformed-config",
      "webkit::session-expired",
      "webkit::session-blocked",
      "webkit::auth-dependency-unavailable",
      "webkit::quote-exact-scope",
      "webkit::terms-config-unavailable",
      "webkit::checkout-double-click-retry",
      "webkit::checkout-processing-return",
      "webkit::checkout-untrusted-return",
      "webkit::checkout-expired",
      "webkit::already-owned-no-pay",
      "webkit::library-pagination-and-states",
      "webkit::paid-prepare-before-poll",
      "webkit::media-renew-coalesced",
      "webkit::logout-and-bfcache-clear"
    ],
    "catalog": [
      "TestPostgresCatalogLifecycleColdHTTPRaceOneJob-bankone",
      "TestPostgresCatalogLifecycleColdHTTPRaceOneJob-banktwo",
      "TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-bankone",
      "TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-banktwo",
      "TestPostgresCatalogLifecycleAtomicPublication-bankone",
      "TestPostgresCatalogLifecycleAtomicPublication-banktwo",
      "TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-bankone",
      "TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-banktwo"
    ],
    "commerce": [
      "test_orders_create_and_owner_scope",
      "test_same_key_replay_and_conflict",
      "test_concurrent_keys_share_one_checkout",
      "test_scope_races_single_active_grant",
      "test_lost_create_response_and_retention_boundary",
      "test_expiry_requires_remote_nonchargeable_proof",
      "test_completion_races_expiry_without_recharge",
      "test_webhook_before_create_response",
      "test_settlement_binds_financial_owner_scope",
      "test_duplicate_and_distinct_events_grant_once",
      "test_refund_chargeback_ordering_and_monotonic_revocation",
      "test_payment_survives_source_unavailable_and_restart",
      "test_library_is_owner_only_and_paginated",
      "test_grant_check_exact_scope_legacy_and_revoked"
    ],
    "identity": [
      "TestPostgresAuthSessionsIntegration/ConcurrentCustomerProvisionAndRotation",
      "TestPostgresAuthSessionsIntegration/SharedSessionRevocation",
      "TestPostgresAuthSessionsIntegration/ExpiryAndPersistedSecrecy",
      "TestPostgresAuthSessionsIntegration/FirebaseExchangeAndUserRevocation",
      "TestPostgresAuthSessionsIntegration/FirebaseStartupRequiresMigratedPostgres"
    ],
    "paid": [
      "TestPostgresPaidCatalogGrantBeforeWork-bankone",
      "TestPostgresPaidCatalogGrantBeforeWork-banktwo",
      "TestPostgresPaidCatalogExactScopeAndOwnerIsolation-bankone",
      "TestPostgresPaidCatalogExactScopeAndOwnerIsolation-banktwo",
      "TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse-bankone",
      "TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse-banktwo",
      "TestPostgresPaidCatalogContextualMediaAndRevocation-bankone",
      "TestPostgresPaidCatalogContextualMediaAndRevocation-banktwo",
      "TestPostgresPaidCatalogHistoricalSourceAndRights-bankone",
      "TestPostgresPaidCatalogHistoricalSourceAndRights-banktwo",
      "TestPostgresPaidCatalogCustomerLegacyRoutesDenied-bankone",
      "TestPostgresPaidCatalogCustomerLegacyRoutesDenied-banktwo"
    ]
  },
  "expected_counts": {
    "browser_api": 21,
    "browser_dto": 120,
    "catalog": 8,
    "commerce": 14,
    "identity": 5,
    "paid": 12,
    "total": 180
  },
  "inventory_pin": {
    "bytes": 122350,
    "commit": "d8579c824eb1ebf546b46b13a0f69079890ad44e",
    "git_blob": "24ac3e9264b85eb914daa7805d183e15f58d374a",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.json",
    "sha256": "c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39"
  },
  "runtime_executed": false,
  "support_credit": 0,
  "support_identity_root": "TestPostgresAuthSessionsIntegration"
}
```

## Embedded provenance.json (verbatim)

```json
{
  "authority": {
    "cutover_verified": false,
    "deployment_authorized": false,
    "fixture_verified": false,
    "implementation_authorized": false,
    "merge_authorized": false,
    "product_candidate_verified": false,
    "profile_promotion_authorized": false,
    "runtime_execution_authorized": false,
    "staging_verified": false
  },
  "candidate_sha": "4d82e413e04fb2401ac7bc28dc828375ac662180",
  "candidate_source_pins_verified": [
    {
      "bytes": 5675,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "b60c3f3930b27e1683bc1fcc564ffa810d1f37cd",
      "path": "apps/api-go/auth_http.go",
      "sha256": "2a3ce06211c6fdada9bbfbb3faba2a7d4e27d21a5e3f009670fa03ef9b8905da"
    },
    {
      "bytes": 12585,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "24a8445d9a09ae3dc45236aaeed84cd755015fd8",
      "path": "apps/api-go/catalog_access.go",
      "sha256": "86709a7e68543a8980e9eaaf934e08361da3488c0c2c23a6ff3219c13569bfa3"
    },
    {
      "bytes": 17225,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "a6151a0d393a87e4c04d082daf92328dece85d1a",
      "path": "apps/api-go/catalog_http.go",
      "sha256": "8bf65ff6b6cfab52b8b42c4d6473e75220c19363a04ae97b103c08edf8ecab50"
    },
    {
      "bytes": 21179,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "a7de23eac67c903cfdf78130bef8f5c2e2c69ecf",
      "path": "apps/api-go/catalog_lifecycle.go",
      "sha256": "5451c0875feb632dc0327243b05f370a2513f80d99d4f9d4fb00a4e0549d78b4"
    },
    {
      "bytes": 10171,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "c303616180ef121829f43b49c0ca0c792297cce1",
      "path": "apps/api-go/catalog_media_access.go",
      "sha256": "6972bb76081f0eea9184b1180799cd1d20becced9e366d8657a925e491d5fb80"
    },
    {
      "bytes": 17076,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "abf37527d3206552bea8979fd5b618c42050c9ef",
      "path": "apps/api-go/catalog_source.go",
      "sha256": "6d18e7f57a4c7016585bd8838a5e2a3ebc092d7a77d1812cf4b749be810423f2"
    },
    {
      "bytes": 30055,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "c83477ae66afeeb55172f22facaeaac822b6fe64",
      "path": "apps/api-go/catalog_store.go",
      "sha256": "e5e7c34f6e14836e6166a176aab3d9e3c092d2e778fe03239a0b23a32ce963b9"
    },
    {
      "bytes": 11067,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "9a62dff8589f5f96d44df966a9109f63abfab354",
      "path": "apps/api-go/commerce_client_test.go",
      "sha256": "972b456f70c8f29afb65505a54266907c74875c7e534bf354884079d757cefc2"
    },
    {
      "bytes": 30492,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "bf5a63233bc2d141f12e5d6147b433641178232b",
      "path": "apps/api-go/main.go",
      "sha256": "c1429d39803ad8170d5f0e4cbd64ea174362adefe7f5b2c008e29cb86888bd44"
    },
    {
      "bytes": 8676,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "ea8d5689cf3b25086f26e41079896afbd7563249",
      "path": "apps/api-go/postgres_auth_sessions_test.go",
      "sha256": "85ea27568b5edb6debc08bbedcd8cfb0cf17cb620b9c4b95e6d97c9f92e892cf"
    },
    {
      "bytes": 40990,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "ba19bac67d5474cd975a1ee8fbde89a812c173c3",
      "path": "apps/api-go/postgres_catalog_access_test.go",
      "sha256": "0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31"
    },
    {
      "bytes": 40868,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "b0db236512e08851bb87c3e33cc76622e10a8378",
      "path": "apps/api-go/postgres_catalog_lifecycle_test.go",
      "sha256": "a8ec30ca66629cc0317c511450e5660911a0d90d79daa52b1816bbd781bc7943"
    },
    {
      "bytes": 18240,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "9617877cabcda64a34edba8d34492c0aa05eb497",
      "path": "apps/api-go/workshop_browser_fixture_test.go",
      "sha256": "7cf50daeb190686dc55c33c90056b87a62eece96640759b180f1282a0a1a6dd2"
    },
    {
      "bytes": 312,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "bb3ca103f625f20c77cfd12e28a2d7e2933fcfb4",
      "path": "db/migrations/001_extensions.sql",
      "sha256": "85478d4fc35579fada5062670498e3f2717e11904c3d636d52824fcfae2f3f3e"
    },
    {
      "bytes": 8690,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "0d1a799fbc021b8c0b69779ad1339eb84aa623c9",
      "path": "db/migrations/002_platform_spine.sql",
      "sha256": "dc90eb26a57c3dcebb5b37bc3e6bdfa73906f06b39352d06f673c09449593fa1"
    },
    {
      "bytes": 1255,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "68284fbaf0f59feea796e44afbd9febfb728e5d7",
      "path": "db/migrations/003_canonical_vehicle.sql",
      "sha256": "8002381c87c08d9602cc75c84a83fe6afec0d35860477660decc7131c92f1c17"
    },
    {
      "bytes": 3927,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "a7db9acfd02423d829737718f2828d05771b3217",
      "path": "db/migrations/004_normalized_source_bundle.sql",
      "sha256": "2f8758effdcd7c46412c4ae40f5c1dc6bb463e5b46169c663d72edfb7eedcb7b"
    },
    {
      "bytes": 629,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "ee42bb606dfdc3dd5dcdd6b0f19af47e501739fc",
      "path": "db/migrations/005_preserve_duplicate_article_ids.sql",
      "sha256": "9d879156e93125590b34b45ebe63ea9da610c6a7553b0a22c5c1fa19291878a5"
    },
    {
      "bytes": 589,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "3e3a5a56d3c52ef9f3da60163897b752ad1f16a9",
      "path": "db/migrations/006_backfill_article_source_locators.sql",
      "sha256": "ffc9e0d74bf15027d50467d25309c1af661c6347feb93e0208c1aa47fbc1727f"
    },
    {
      "bytes": 364,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "9d80ca50c5669350369d570625550bac7dcca241",
      "path": "db/migrations/007_link_evidence_to_revision.sql",
      "sha256": "be7488c3fa4fa6d12f7a825b2204b23337a836e490714ab15f57ea596300d5e5"
    },
    {
      "bytes": 1288,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "8d93e1345b39175b413e0c0232ede8e13b982fd7",
      "path": "db/migrations/008_publication_outbox_delivery.sql",
      "sha256": "8100bdb3a64a275f655ff8a15261dc450f8dfb720ccf4e45ce8e91463ca80001"
    },
    {
      "bytes": 739,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "34bf7eeff9da786f4d3a65e44879bee5651b19a0",
      "path": "db/migrations/009_feedback_evidence_link.sql",
      "sha256": "c757f046b99f6b78634178aa8973ebd1be631b5efb002e20950ff40a81cf8e87"
    },
    {
      "bytes": 297,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "c5f8c8fe35cb84ecc5339c26176a0c17f1c122ff",
      "path": "db/migrations/010_evidence_review_metadata.sql",
      "sha256": "b0c3fe61510d775e212779efb2c0bc0ba31535ac1f8b36959cf308f09962270b"
    },
    {
      "bytes": 245,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "5b2440b730eda36356305b0389e561055b3600a2",
      "path": "db/migrations/011_feedback_review_metadata.sql",
      "sha256": "1e33b4d8975db45a7bb3d48c1ae4d4320f63e0ee8df19e89443ffd93edc50c9e"
    },
    {
      "bytes": 1359,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "e34a75f6e34f575d12c4bc95f37132965b952142",
      "path": "db/migrations/012_payment_fulfillment_reconciliation.sql",
      "sha256": "a1f2de68abbcefef86659c6b6f5e4a98f28c8c8de4e0ebe44ea7833fe9a4d169"
    },
    {
      "bytes": 536,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "f87c3e21f0632a4c5e77ffccb3e67c0767e32379",
      "path": "db/migrations/013_dataset_request_ownership.sql",
      "sha256": "93a6d17fceb867746abbce5252e32d6837ac9038105ed9b42e782fc48ea061a0"
    },
    {
      "bytes": 1332,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "cc30a174bb98704addbfde5e5bb1e27e3de58f7e",
      "path": "db/migrations/014_normalized_article_content.sql",
      "sha256": "aaabc8f973044f1489f34faf8f43cecfae43fd440a6db5f24e8b2341931678aa"
    },
    {
      "bytes": 6515,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "d4c9dd2dbaf1f2391ee3969622c72b8e894657ef",
      "path": "db/migrations/015_vehicle_identity_resolution.sql",
      "sha256": "ff749d43e77c5329196a769d3a84941f388694b399daa7d5b5409d4443c4bcbd"
    },
    {
      "bytes": 648,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "ae3e12a130bdb380a5cd9014f693077548de9927",
      "path": "db/migrations/016_catalog_article_configuration.sql",
      "sha256": "58f5cf17e07dc151ee29733e662923a20807dea75cc52264b85481ef2ebb1ac3"
    },
    {
      "bytes": 444,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "4b98ce3164bff82989e392b97791e198d027304d",
      "path": "db/migrations/017_knowledge_catalog_evidence_index.sql",
      "sha256": "3d5111d77911bd349248d26943a284cbcb6ea93126c19f5f2cfdf5b239c338b5"
    },
    {
      "bytes": 1373,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "7d18eeb9103b4445c3a05422bc446c3f9300ec96",
      "path": "db/migrations/018_source_review_items.sql",
      "sha256": "d2fcb0c678494d76a0a9e775ae8a23a71f659a49efdef55e7ae1b984dab90c75"
    },
    {
      "bytes": 1137,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "d40129b9f32e4154c0631dd820ad6571a7f965da",
      "path": "db/migrations/019_article_content_provenance.sql",
      "sha256": "666ac9ae863a11b116ee3b4492d229e9c23d24ce646f11438a74b755450c54fb"
    },
    {
      "bytes": 1511,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "5ab1c5e701f35d5a88933b4cd525ccbff7f695f5",
      "path": "db/migrations/020_autoapi_article_fetch_jobs.sql",
      "sha256": "5fbbdb0748fdb99b065f369d9cd951af6aeb8b29275958c8eec33b39cb7094e9"
    },
    {
      "bytes": 595,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "dc5fcc59b74acc297df4e66e253cfffd6d978f7a",
      "path": "db/migrations/021_autoapi_article_fetch_job_retries.sql",
      "sha256": "01408a1e7e354328958f33f83963733e810efb9e0e5b2cb74ad08f7f804d58bb"
    },
    {
      "bytes": 3503,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "1fc8b191ce0a410387ac296e773cdddeec8d68cb",
      "path": "db/migrations/022_job_plan_derived_articles.sql",
      "sha256": "506d55d53f82897455b8d04813797304fa534b1f357f73ad3ff55c3b0e3449a3"
    },
    {
      "bytes": 714,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "0bdc32e46f906d5684b3210a4a7e64d5d7380b6e",
      "path": "db/migrations/023_catalog_article_images.sql",
      "sha256": "066e3c06f543e9f1dca117f879b0dfb1f22f42860a6f041d28a1fca313db7923"
    },
    {
      "bytes": 737,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "c6c5e23207437111de919debfdd30be4bc1a393a",
      "path": "db/migrations/024_catalog_article_operations.sql",
      "sha256": "f70b2331a2979e83f246ed8a6939ca5c2c971d1f929d901141f25419add97158"
    },
    {
      "bytes": 12458,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "fd7b5fd2fa95a4b9ae3caa9369f9664a63dcd396",
      "path": "db/migrations/025_chat_quote_procedure.sql",
      "sha256": "9531b01d539a6afa20a7ec9de358f84590a0e6803cef9c171d91b7477fe947d6"
    },
    {
      "bytes": 899,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "0c8cb5c9328071905e7d2e0efabe8157a2007653",
      "path": "db/migrations/026_chat_quote_operation_categories.sql",
      "sha256": "3796ae1753e267f7fe5cd6fc25d30dd3c5d079e8b708d9f805f7c61e85096012"
    },
    {
      "bytes": 3496,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "33e2c8e6f4e2100f52ed8f64d93659dff6bf30c5",
      "path": "db/migrations/027_chat_runtime_durable_state.sql",
      "sha256": "3c9f0f4ae1a906f666efdd4ffb947e62081774b74c70bb3f19fe76adf2ec95ba"
    },
    {
      "bytes": 1772,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "0ba8a44f17b85a151f9af2038e7e2f34bdd9289f",
      "path": "db/migrations/028_vehicle_provider_mappings.sql",
      "sha256": "db77666011d7a5e46a17c849f15c63493e02ace104a7bc26f164c2cb3aac09c6"
    },
    {
      "bytes": 2082,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "2358da7e4d8c7460d4ce543ac514361f932bb18c",
      "path": "db/migrations/029_vehicle_catalog_sync.sql",
      "sha256": "1f298236632a42f7dd9730a1af15430b41f8dd90887d8266189d1febcdc37026"
    },
    {
      "bytes": 1121,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "857a99d22b791edf940fef12e06608c976c64546",
      "path": "db/migrations/030_vehicle_catalog_years.sql",
      "sha256": "746c2bff949fd137b5ebcb67e88102565481193e2e47b11eb1cbb04f50e399f8"
    },
    {
      "bytes": 1574,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "6d71ed4da93dd4525a5b80f007148548c872ef7c",
      "path": "db/migrations/031_catalog_article_classification.sql",
      "sha256": "0150e00308e744e24c30e8ac45ca36ba7cac658ca6ff6c1a72d424cb2f09d332"
    },
    {
      "bytes": 1300,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "5b7fb0408b5f5938cb992aff507e84b34d21366c",
      "path": "db/migrations/032_catalog_article_source_original.sql",
      "sha256": "8483793a03513de4d1d6a347dfe5d76da6e249a13b02cc89477aaa61ba38f961"
    },
    {
      "bytes": 1451,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "50fec1822508846174cc9d59a5495e2b47eb83f7",
      "path": "db/migrations/033_catalog_scope_coverage.sql",
      "sha256": "144d4786cb343c52b309feb4ded079c1686dd2a68b102fb2d9186f8334ae49f8"
    },
    {
      "bytes": 2139,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "cca45d52b344a1761308d1714976e206bd054f6d",
      "path": "db/migrations/034_catalog_article_progress.sql",
      "sha256": "e24c29be3157bdc26616a1cf02c9812e1ea62a67c83420feeea687afaa0273c3"
    },
    {
      "bytes": 1662,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "75bdbb276a5af737e9ab9651bee0d9e923320650",
      "path": "db/migrations/035_ordered_article_document.sql",
      "sha256": "fe8d1d8a69b4f2e84e9ea0770044f45ff49d2a4b3d01a09db85c49fbc5e1d2ce"
    },
    {
      "bytes": 3734,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "5afe1c409dbc5fa72d3143d6528a85c5e712209c",
      "path": "db/migrations/036_source_fetch_jobs.sql",
      "sha256": "8b4935c5949bd250d8d6fb62098ebbd34e6c5dd3474ea907e73d24c047aa15f9"
    },
    {
      "bytes": 12905,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "649d50b212980d7eede2ca0423e2b68f4e298ae7",
      "path": "db/migrations/037_article_source_lifecycle.sql",
      "sha256": "3a1df6fb260a3afd979cdd65dcebed89f51a7e8b2098d4190b03fdccdbc7ca07"
    },
    {
      "bytes": 12863,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "449056c1478fca769c53abaf4a51093b8f350895",
      "path": "db/migrations/038_article_transform_publication.sql",
      "sha256": "343df92024c5e394c1878eb598bfd8e83c96998e19bf03f9523fff35ac62f2ff"
    },
    {
      "bytes": 1298,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "5ca091ce0215babcaa3afdc45bbbd3b6587d1011",
      "path": "db/migrations/039_production_identity_sessions.sql",
      "sha256": "639048d2914f6b7477352b7b14f07d26a211434511f0af970adbc69a766a7a36"
    },
    {
      "bytes": 4956,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "18ec48100cdbb7ebbd226e97eba05ad42cfbc341",
      "path": "db/migrations/040_workshop_commerce.sql",
      "sha256": "7ff3203b5c980bf7fe688470ef737f0d29789ff9c5f04b9744257d0715cb695e"
    },
    {
      "bytes": 1385,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "a6d7663a663fdb2d3bec0d58506fc5e161d3cf32",
      "path": "infra/compose/article-lifecycle-test.Dockerfile",
      "sha256": "ea1d9f043e8775ecbdeea60e9df86ade41fe2d61bd9aadb557479be745e6fc5f"
    },
    {
      "bytes": 1386,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "38616cde5dc9f0ba45663638e772511b8adeb233",
      "path": "scripts/dev/fixtures/workshop_customer/firebase_transport.js",
      "sha256": "96bd315271bf05f363dc74ebb8d60c243f0ede8f0e7a649d3d7eeb7ea8f9dc63"
    },
    {
      "bytes": 485,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "24bdbea86de6f54abab0c26581d77675cf2d2f24",
      "path": "scripts/dev/fixtures/workshop_customer/hostile_source.json",
      "sha256": "076b68d46991bd32a8ba73f61b93d7c22b52784c3df2d58d0c9e8d33891483d1"
    },
    {
      "bytes": 1027,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "bff0b0a52aa900e144ad8e3062632e8859a87c30",
      "path": "scripts/dev/fixtures/workshop_customer/scenarios.json",
      "sha256": "83ae0b9a08148fc5321663ce1f4647d29535726d7af93f6299abd4171ebc65d9"
    },
    {
      "bytes": 503,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "acc3a065b4b6cc6c4c32f0eedb203d2cdd59c096",
      "path": "scripts/dev/fixtures/workshop_customer/stripe_checkout.html",
      "sha256": "26c1c7ea312630626792f89290b318ca36d01f72c7906d94cab9baf03dc74083"
    },
    {
      "bytes": 10262,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "33ae8760eb9e9635932fe0d378b322857165e194",
      "path": "scripts/dev/production_access_smoke.py",
      "sha256": "ac928cb722eda7e5f0d99d0f4f10fb4b78470c39a7d7d31cb41505f42672675f"
    },
    {
      "bytes": 18502,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "648a6dbb6a2995161c2bcc535af526140cb3380f",
      "path": "scripts/dev/test_migrations.py",
      "sha256": "2ce5c434d5f48a265d448b9f2c01d68433177cb1fd7199c227f908434adbddc0"
    },
    {
      "bytes": 6221,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "a6d1050ed104b15e723ad982b97740007994b3aa",
      "path": "scripts/dev/test_production_access_smoke.py",
      "sha256": "39909327d8db2002c6d2f857fa0a9929e13e952623241efe6f4223aa2c50a8b8"
    },
    {
      "bytes": 61845,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "4206692d38c476ebbd750d15a620716072ce1932",
      "path": "scripts/dev/workshop_browser_smoke.py",
      "sha256": "45299888e56a78679148f575ac071856f0a3c1941faf059cd586ff2980069de8"
    },
    {
      "bytes": 7443,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "bba155614122d795e4a91ee05dba51e21a76d144",
      "path": "scripts/dev/workshop_commerce_smoke.py",
      "sha256": "3fa9b5f4d13fee71d8c6cd2b0592a2d6a128485b161f727bcc96685d2a59d2f9"
    },
    {
      "bytes": 7639,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "5eefbd805df73c000b7b690b035448deac8c9152",
      "path": "scripts/dev/workshop_paid_access_smoke.py",
      "sha256": "1acaa6bffaf35b122b40757c78dbf01fb06244803720c951b2b828133232632f"
    },
    {
      "bytes": 327,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "1dd050f18ee178cf160fd9900271fdcddad58ba9",
      "path": "workers/ingestion-python/pyproject.toml",
      "sha256": "9ed011cb0de6069669b31d1ebd66ee1a0fba63ee699cd90535f46358432ef1c1"
    },
    {
      "bytes": 28828,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "59ada3a024b438a1234a4a2958a0546e320f6646",
      "path": "workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py",
      "sha256": "22087935412e90b17f28e746e46d454d6fb5ff65c22cf61c13c83ae39a151268"
    },
    {
      "bytes": 19309,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "ac52c479e5e4a7f625cddd409d8d61573c271765",
      "path": "workers/ingestion-python/tests/lifecycle_support.py",
      "sha256": "746eba57bfffb760e2f779d0d0494125f8b559b07de5ff6ec11099d517bf76dc"
    },
    {
      "bytes": 20964,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "c02cd78ce92b9d9ec801d8f66bb71b0d63242ca6",
      "path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
      "sha256": "c6e1e2a7d6da9d709f3c77ac4bc302ca715e2a460637e9403a5f2be169bf3875"
    },
    {
      "bytes": 30980,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "5b16ff5b5428547fcdeb09fb63c36c94a406ff6c",
      "path": "workers/ingestion-python/tests/test_catalog_api_integration.py",
      "sha256": "88e6c1fd339da60614056abd7689b6a7fcd1d16bc1e239cec888b06bb6a61974"
    },
    {
      "bytes": 31526,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "fdccc37c1d13394ecb634c17ef12614b6fc9ac76",
      "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
      "sha256": "fbab00f576410393e5077351d08d108c884d4a6442549fc4192647796e19904e"
    },
    {
      "bytes": 19378,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "d4d8b6d26ead3023dbbe5084d1376c0009404aae",
      "path": "workers/ingestion-python/tests/test_paid_catalog_api_integration.py",
      "sha256": "efd3098953dde54d3fc38c167db1f56ab97225c185fb73f032fe7f3289b70198"
    },
    {
      "bytes": 12589,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "3b8a9de3b5e7d822b36731c5c7f3e9723b1787db",
      "path": "workers/ingestion-python/tests/test_workshop_browser_integration.py",
      "sha256": "b16ab3953b863a2c7156cf57936a2bca4f56f2c3078c68f93ba616318793e801"
    }
  ],
  "citations": [
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "ac928cb722eda7e5f0d99d0f4f10fb4b78470c39a7d7d31cb41505f42672675f",
      "line": 16,
      "path": "scripts/dev/production_access_smoke.py",
      "text": "GO_ROOT = 'TestPostgresAuthSessionsIntegration'"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "ac928cb722eda7e5f0d99d0f4f10fb4b78470c39a7d7d31cb41505f42672675f",
      "line": 17,
      "path": "scripts/dev/production_access_smoke.py",
      "text": "GO_NAMES = ('ConcurrentCustomerProvisionAndRotation', 'SharedSessionRevocation',"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "ac928cb722eda7e5f0d99d0f4f10fb4b78470c39a7d7d31cb41505f42672675f",
      "line": 20,
      "path": "scripts/dev/production_access_smoke.py",
      "text": "GO_IDS = tuple(GO_ROOT + '/' + name for name in GO_NAMES)"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "ac928cb722eda7e5f0d99d0f4f10fb4b78470c39a7d7d31cb41505f42672675f",
      "line": 107,
      "path": "scripts/dev/production_access_smoke.py",
      "text": "def go_results(events):"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "ac928cb722eda7e5f0d99d0f4f10fb4b78470c39a7d7d31cb41505f42672675f",
      "line": 125,
      "path": "scripts/dev/production_access_smoke.py",
      "text": "def success(code, timed_out, assertions):"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "ac928cb722eda7e5f0d99d0f4f10fb4b78470c39a7d7d31cb41505f42672675f",
      "line": 129,
      "path": "scripts/dev/production_access_smoke.py",
      "text": "def collect(candidate, output):"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "ac928cb722eda7e5f0d99d0f4f10fb4b78470c39a7d7d31cb41505f42672675f",
      "line": 154,
      "path": "scripts/dev/production_access_smoke.py",
      "text": "events = [json.loads(line) for line in (ARTIFACTS / 'r5-access-go-events.jsonl').read_text().splitlines()]"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "39909327d8db2002c6d2f857fa0a9929e13e952623241efe6f4223aa2c50a8b8",
      "line": 52,
      "path": "scripts/dev/test_production_access_smoke.py",
      "text": "if os.getenv('AUTODATA_REQUIRE_AUTH_INTEGRATION') == '1':"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "39909327d8db2002c6d2f857fa0a9929e13e952623241efe6f4223aa2c50a8b8",
      "line": 57,
      "path": "scripts/dev/test_production_access_smoke.py",
      "text": "def test_required_postgres_auth_sessions(fresh_database):"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "39909327d8db2002c6d2f857fa0a9929e13e952623241efe6f4223aa2c50a8b8",
      "line": 72,
      "path": "scripts/dev/test_production_access_smoke.py",
      "text": "result = subprocess.run(['go', 'test', '-json', '-count=1', '-run', '^' + smoke.GO_ROOT + '$', '.'],"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "39909327d8db2002c6d2f857fa0a9929e13e952623241efe6f4223aa2c50a8b8",
      "line": 74,
      "path": "scripts/dev/test_production_access_smoke.py",
      "text": "timeout=180, check=False)"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "39909327d8db2002c6d2f857fa0a9929e13e952623241efe6f4223aa2c50a8b8",
      "line": 89,
      "path": "scripts/dev/test_production_access_smoke.py",
      "text": "'go_exit_code': code, 'go_timed_out': timed_out}"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "85ea27568b5edb6debc08bbedcd8cfb0cf17cb620b9c4b95e6d97c9f92e892cf",
      "line": 47,
      "path": "apps/api-go/postgres_auth_sessions_test.go",
      "text": "func TestPostgresAuthSessionsIntegration(t *testing.T) {"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "85ea27568b5edb6debc08bbedcd8cfb0cf17cb620b9c4b95e6d97c9f92e892cf",
      "line": 58,
      "path": "apps/api-go/postgres_auth_sessions_test.go",
      "text": "t.Run(\"ConcurrentCustomerProvisionAndRotation\", func(t *testing.T) {"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "85ea27568b5edb6debc08bbedcd8cfb0cf17cb620b9c4b95e6d97c9f92e892cf",
      "line": 127,
      "path": "apps/api-go/postgres_auth_sessions_test.go",
      "text": "t.Run(\"SharedSessionRevocation\", func(t *testing.T) {"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "85ea27568b5edb6debc08bbedcd8cfb0cf17cb620b9c4b95e6d97c9f92e892cf",
      "line": 177,
      "path": "apps/api-go/postgres_auth_sessions_test.go",
      "text": "t.Run(\"ExpiryAndPersistedSecrecy\", func(t *testing.T) {"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "85ea27568b5edb6debc08bbedcd8cfb0cf17cb620b9c4b95e6d97c9f92e892cf",
      "line": 204,
      "path": "apps/api-go/postgres_auth_sessions_test.go",
      "text": "t.Run(\"FirebaseExchangeAndUserRevocation\", func(t *testing.T) { testFirebaseExchangeAndUserRevocation(t, store) })"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "85ea27568b5edb6debc08bbedcd8cfb0cf17cb620b9c4b95e6d97c9f92e892cf",
      "line": 205,
      "path": "apps/api-go/postgres_auth_sessions_test.go",
      "text": "t.Run(\"FirebaseStartupRequiresMigratedPostgres\", func(t *testing.T) {"
    },
    {
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "file_sha256": "3306c3736c51a3c08a4ed30613a9f0ba4db7f5094d0215ebdf54545873012923",
      "line": 1,
      "path": "apps/api-go/go.mod",
      "text": "module github.com/lucronn/autodata/apps/api-go"
    }
  ],
  "contract": "workshop-final180-stage-b1-external-provenance-v1",
  "draft_review_revision": {
    "behavioral_examples_are_specification_only": true,
    "corrections": [
      "Terminal frames require concrete int code and other frames require None",
      "Total equal-time order includes scheduled TERM/KILL/leftover and cleanup acknowledgements",
      "Diagnostic explicitly serializes disabled profile metadata and exactly five unique ordered identity rows"
    ],
    "reason": "Address three independent draft review findings; pending independent rereview",
    "replay_or_application_runtime_executed": false,
    "revision": 2,
    "self_checks": {
      "complete_equal_time_order": true,
      "exact_five_unique_ordered_rows": true,
      "no_implementation_authority": true,
      "nonterminal_code_mandatory_none": true,
      "profile_and_row_rejections_examples": true,
      "profile_fields_declared": true,
      "scheduled_signal_ack_order_explicit": true,
      "terminal_code_mandatory_concrete_int": true
    },
    "supersedes_draft_sha256": "e31153ad577917004e3e8e771b80b6883500dc1bfc25ea798132d5f25d4dec32",
    "supersedes_report_sha256": "c31343f776852e8ee2e494800a72c7250b9784baaf499ce95b68492d190890c0"
  },
  "historical_stage_a_checkpoint": "b8ffaa39e6b9104df67f69541ce4da8a936adc0f",
  "inventory_pin": {
    "bytes": 122350,
    "commit": "d8579c824eb1ebf546b46b13a0f69079890ad44e",
    "git_blob": "24ac3e9264b85eb914daa7805d183e15f58d374a",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.json",
    "sha256": "c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39"
  },
  "proposed_planning_parent_sha": "2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e",
  "reports": [
    {
      "bytes": 152620,
      "path": "/home/corp/autodata-evidence/final180-stage-b-schema/report.json",
      "sha256": "48e915ad5589331e5718105f6dbbcfcdb967d3e92fcb73be0602bb700f89afaa"
    },
    {
      "bytes": 3597,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/report.json",
      "sha256": "36670a61779baa5ec2dd40d879b485c32d2a41907e1f971507ad450ca1a679ae"
    }
  ],
  "reviewed_runner_pins": [
    {
      "bytes": 47124,
      "commit": "2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e",
      "git_blob": "ca48cd988c5579a7d385dc1844b84306eae0861e",
      "path": "scripts/dev/workshop_final180_runner.py",
      "sha256": "693a408a73f3ccd37bf945bfc94d427f742878580932dab382ea9a244a141c91"
    },
    {
      "bytes": 32981,
      "commit": "2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e",
      "git_blob": "2cfa9dc8ea116b7aa5b0c541529712b4b5d24be3",
      "path": "scripts/dev/test_workshop_final180_runner.py",
      "sha256": "2f92614e937b5b3d6a17da7ab9f4b758b34a4a542fbe5564b29ddefd4f7b148a"
    },
    {
      "bytes": 7669,
      "commit": "2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e",
      "git_blob": "4cd4e77124228f8aa3db1b923315eec6d402d2dd",
      "path": "docs/verification/workshop-final180-runbook.md",
      "sha256": "d06cc51f448cd5e4adba21f73c550357f803bfc74f927717a360c04022d1ef8b"
    }
  ],
  "stage_a_context_pins": [
    {
      "bytes": 7888,
      "commit": "b8ffaa39e6b9104df67f69541ce4da8a936adc0f",
      "git_blob": "c8617fee8e43d27f80ca29c6f1a9ddae6ac79ed2",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final180-runner.md",
      "sha256": "6d1d5f4e8da9310669419703b298eeb17cd7c14a5e3719ea416cf5b1145ebaa9"
    },
    {
      "bytes": 33663,
      "commit": "b8ffaa39e6b9104df67f69541ce4da8a936adc0f",
      "git_blob": "c0948a5b604b9ae5f0ce31ab2e7864cbc9b8d527",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-runner.md",
      "sha256": "24d209a60ae2dcda461d1a65932c2dd37d6894ed7a9c3920f989fe8ff0b20ba3"
    },
    {
      "bytes": 2818,
      "commit": "b8ffaa39e6b9104df67f69541ce4da8a936adc0f",
      "git_blob": "76fad048ba8369375623fdb19126adda482a976c",
      "path": "docs/agents/records/2026-11-04-workshop-final180-runner.json",
      "sha256": "90f083cf65c116cd9660269805a764e433ad0f34bf92ad5f1b6a92596e6f4752"
    },
    {
      "bytes": 5206,
      "commit": "b8ffaa39e6b9104df67f69541ce4da8a936adc0f",
      "git_blob": "660a14557b1bbb9123b5a648b654d45182fdc6a5",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final180-runner.json",
      "sha256": "b2fb8ad4a73316e0296bdbc477a458a29d10d14c88483ae321bb23cd4eb901b7"
    }
  ],
  "verification": {
    "addendum_artifact_hashes_verified": 11,
    "addendum_source_pins_verified": 62,
    "all_literal_case_ids_equal_immutable_inventory": true,
    "corrected_addendum_pin_verified": true,
    "github_read_or_write": false,
    "prior_report_pin_verified": true,
    "prior_source_pins_verified": 22,
    "repository_files_modified": false,
    "runtime_executed": false
  },
  "verified_addendum_artifacts": [
    {
      "bytes": 3105,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/REPORT.md",
      "sha256": "4229dc2b8ee8429b0014b074c5dd1c87dae76c4d5bf3b35d1d35d28170498bed"
    },
    {
      "bytes": 29304,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/build_addendum.py",
      "sha256": "9948e1a0cbeead662eb0b62f0861a22c6507c37bdc29ce4cebd04b7f719fd8e4"
    },
    {
      "bytes": 10897,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/finalize_addendum.py",
      "sha256": "e845d410dea5767216b1f1fe61acd1522df84b4d4a9048fec15ce5d890dfe5ab"
    },
    {
      "bytes": 49312,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/http-route-body-outcomes.json",
      "sha256": "b0dfb32d879d76c1ea8d7b563606c77fa31290e78ae1739cd8da370a825d9366"
    },
    {
      "bytes": 38339,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/pytest-support-inventory.json",
      "sha256": "8a59548548b005663478dd01543083a2839f636d7be236582667522f37e206b0"
    },
    {
      "bytes": 21016,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/runtime-selected-shapes.json",
      "sha256": "5c022204dbc4548874b211dc00c4c0f7cfc7d8a4f2f69909ba7402c282435b1c"
    },
    {
      "bytes": 17985,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/source-pins.json",
      "sha256": "b6f30101a457ea99df668a772ea4123cb3f2eecab9697d158146bd7ed2fc3692"
    },
    {
      "bytes": 270936,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/sql-row-schemas.json",
      "sha256": "ad4a304df66d6472abfd9ccfd5900b4e8889b0312c87e81cdab0e74f5f1afac9"
    },
    {
      "bytes": 681,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/verification-independent.json",
      "sha256": "4ad31c52f58fea832efc6c29c2eb61647ce31800eeda1ec4bcd7efce53f360d7"
    },
    {
      "bytes": 694,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/verification.json",
      "sha256": "5510f4a05686bff8b0d92bdc89b718ef7ecbab3d1b24e868a5387b2825e6e71a"
    },
    {
      "bytes": 3217,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/verify_sources.py",
      "sha256": "e9a87aed273cb10e786680e1b29071808975c77a9bdc0d73a88133a29ab3a45c"
    }
  ]
}
```
