# Workshop final180 Stage B2 catalog Go-event adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task, only after the coordinator has passed the complete gate and explicitly dispatched the exact checkpoint. Steps use checkbox syntax for tracking.

**Goal:** Add a bytes-only synthetic catalog8 Go-root adapter, with eight literal provider/root slots, no execution, zero accepted-case credit and every authority false.

**Architecture:** Eight fixed in-memory caller-selected catalog slots use only the pinned public B1 Go-event grammar parser, followed by catalog-root lifecycle evaluation and strict deterministic serialization. Every row is synthetic; provider names are unauthenticated caller context. No collector, runtime, timer scheduler or full catalog raw validator is included.

**Tech Stack:** Python standard library (`dataclasses`, `hashlib`, `json`, `re`), unittest; public B1 `parse_identity_events`, `GoEvent`, `AdapterError`, `SimulatedExit` only.

**Spec:** `docs/agents/specs/2026-11-04-workshop-final180-stage-b2-catalog-go.md` (self-contained normative contract and literal provenance/mappings).

**Status:** Issue186/Project8 planning synchronized at https://github.com/lucronn/autodata/issues/186#issuecomment-6638148203; committed B2 checkpoint, standalone/nested exact-base preflight, independent exact-checkpoint review and explicit coordinator dispatch remain pending. This document is planning only. No B2 implementation or runtime authority follows from this tracking update.

**Goal:** Add a bytes-only synthetic catalog8 Go-root adapter, with eight literal provider/root slots, no execution, zero accepted-case credit and every authority false.

**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8

**Planning parent / reviewed B1 code head:** `54a7ca32eab80654310d862f0ac6957375d16e8b`. **Application candidate:** `4d82e413e04fb2401ac7bc28dc828375ac662180`. **Historical B1 gate:** `006fab0d1380c2506330bbc0b48397a32294b6cc`. These are distinct identities; the B1 gate does not authorize B2.

The coordinator reports independent external draft/report review PASS with no findings, bound to draft SHA256 `dbd9bcbd231d04c169675f8915c0568917073a162ae9431dc233dcbf1bca0c1a` and report SHA256 `dd3c0fddc747269b071b7e0fbc5fc10bec23bb653efa8dc1d0de6c59e7e99656`. No saved reviewer receipt or committed-checkpoint review is invented. External paths below are historical audit locators; the technical contract, mappings and source pins are embedded here. Live tracking readback is https://github.com/lucronn/autodata/issues/186#issuecomment-6638148203; the prior Issue body/comments and all unrelated Project fields were preserved. Historical draft/report status fields describe their original creation, not current synchronization.

## Global constraints

- Restrict all work to synthetic bytes-only catalog8 translation; accepted_case_credit is exact int0, profiles_enabled=False, enabled_tiers=(), runtime_lock/run_record null and all nine authority flags exact False.
- Preserve Stage A runner/test and B1 module/test byte-for-byte at the embedded predecessor pins; no parser extraction/refactor, B1 fake replay or identity180s timers.
- No application/producer/SQL/Compose/workflow/assembler/evaluator/policy/profile/inventory/dependency/autonomy-runner changes; no CLI, runtime, filesystem collection, process, Docker, browser, network, provider or payment execution.
- Imports and exact frozen dataclass interfaces, literal mappings, bounds, failure vocabulary/order, per-slot/top-status precedence and serializer admission are reproduced below and normative in the spec.
- Source bank identity is unavailable from raw Go bytes. Identical bytes in two bank slots are permitted with zero real case credit. Synthetic consistency cannot prove runtime compatibility or a complete catalog validator.
- Concrete implementation milestone commits must pass their checks and be promptly pushed to the coordinator-assigned feature branch. Do not merge, deploy or rewrite published history.

## File responsibilities and exact implementation allowlist

1. `scripts/dev/workshop_final180_catalog_adapter.py` — new translation/serialization module; no CLI.
2. `scripts/dev/test_workshop_final180_catalog_adapter.py` — new constructed fake-byte/receipt unittest suite.
3. `docs/verification/workshop-final180-runbook.md` — runbook update preserving prior Stage A/B1 gate identities and behavior.

Coordinator-only planning paths: `docs/superpowers/plans/2026-11-04-workshop-final180-stage-b2-catalog-go.md`, `docs/agents/specs/2026-11-04-workshop-final180-stage-b2-catalog-go.md`, `docs/agents/records/2026-11-04-workshop-final180-stage-b2-catalog-go.json`, `docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-b2-catalog-go.json`, `docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md`. The implementation worker may change only the three paths listed above.

## Canonical todo

1. Synchronize B2 plan/spec/task/record and exact three-path implementation allowlist with Issue186 and Project8, preserving prior history; commit the checkpoint descending from reviewed B1 and pass exact-base standalone/nested preflight plus independent review before explicit dispatch.
2. Implement bytes-only eight-slot catalog Go-event translation using the pinned B1 public parser without altering it; freeze bank-context limitations, per-slot lifecycle rules, byte bounds, status precedence and strict serialization.
3. Add failing-first fake-only adversarial tests for grammar, exact IDs/slots, lifecycle, receipts, limits, serialization and unchanged B1/Stage A behavior.
4. Update the runbook; run focused/developer/autonomy and allowlist checks; commit/push validated milestones and obtain independent exact-code-head review.
5. Synchronize code-only verification at the exact implementation SHA while preserving null runtime lock/run record, disabled profiles and all authority false; retain separate blockers for complete catalog raw semantics and real runtime.

## Decision-complete adapter contract

## Decision and source sufficiency

Choose catalog8 event translation as B2. The immutable catalog producer fixes four Go roots, paired with bankone then banktwo, and runs one separate Go process for each tuple. Its `validate_go_events` checks the exact package, no fail/skip action, exactly one root run/pass and a final package pass. This supplies an independently implementable event-translation contract. B2 adds the same explicit restricted grammar and package lifecycle admission used by B1, under synthetic-only trust.

Complete catalog8 evidence validation remains blocked. The inventory requires matching JUnit plus result identity and all retained per-case migration/runtime support, not just Go events. The corrected source addendum resolves outer SQL columns/types/nullability and declared source shapes, but explicitly leaves full nested document/JSONB semantics and raw assertion translation unfinished. Exact pytest/plugin JUnit emission remains unobserved. LifecycleRuntime dynamically emits additional support files; a complete typed file inventory and bounds remain unpromoted. No actual image/tool/cache/runtime lock or independent registered profile exists. A planner could design a broader restricted semantic validator later, but those decisions are not supplied by these sources and cannot be silently inferred here.

The bank attribution limitation is source-confirmed: raw Go events name only the root and package; `go-measurement.json` has phases/views/assertions and no mandatory provider/candidate identity (Go source lines97–119). The Python process environment sets provider and the final result repeats provider/root/candidate, but neither is authenticated in this slice. Therefore no event parser can independently infer or prove bankone versus banktwo from these bytes. B2 deliberately translates eight **synthetic caller-selected slots**, never eight executed bank cases. Passing both slots with identical bytes is possible and earns no real credit. Rejecting identical hashes would invent a source guarantee and is not specified. Future real evidence requires independently admitted receipt/path/manifest/process/environment/result/JUnit bindings and semantic support.

If the desired B2 scope is a complete catalog family validator or any real case credit, the precise blocker is this missing admitted cross-artifact identity/provenance/semantic contract. The viable narrower alternative is the adapter below. This specification does not weaken the inventory's eventual requirements.

## Source citations and exact pins

The canonical spec embeds full commit/path/Git blob/byte length/SHA256 pins and literal line citations with their own SHA256. The canonical spec embeds all180 inventory IDs and the active eight slots. The inventory bytes digest is `c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39`. No consumer imports candidate code or regenerates expected IDs at runtime.

Active direct sources at application candidate4d82e413:

- `workers/ingestion-python/tests/test_catalog_api_integration.py:28–40`: four GO_NAMES and required fixture flag; lines460–469: exact event validator; lines472–481: ordered provider/root pairing and result identity; lines511–537: per-slot environment, exact Go command and source deadlines; lines538–580: additional independent measurement/runtime/migration/result requirements.
- `apps/api-go/postgres_catalog_lifecycle_test.go:36–74`: fixture flags/database/provider/candidate/control setup; lines97–119: raw measurement payload; lines216–233: nested document/body/steps/images projection; lines403,478,530,588: the four literal Go root declarations; lines287–289: index readiness remains support inside the cold root.
- `apps/api-go/go.mod:1`: `github.com/lucronn/autodata/apps/api-go`.
- The immutable inventory/spec, Stage A spec/runner, B1 spec/parser/test, runbook and canonical gate are pinned separately at B1 head. Importing the tooling parser is permitted; importing application/producer code is forbidden.

The corrected gap-closure report and every named external artifact were rehashed; all62 addendum source pins were compared against candidate Git objects. This is source verification, with no fixture execution. See the source provenance in the canonical spec for the report's exact digest and artifact list. It does not establish runtime compatibility, independent review or authority.

## Exact future implementation allowlist

Only these three paths may change after the new B2 gate:

1. Create `scripts/dev/workshop_final180_catalog_adapter.py`: standard-library in-memory translation and serialization, no CLI.
2. Create `scripts/dev/test_workshop_final180_catalog_adapter.py`: constructed fake bytes/receipts only.
3. Modify `docs/verification/workshop-final180-runbook.md`: document synthetic catalog slots, limitations and checks, preserving all Stage A/B1 behavior and gate identities.

Preserve B1 module/test and Stage A runner/test byte-for-byte. No application, producer, SQL, Docker/Compose, workflow, assembler/evaluator, policy/profile, inventory, dependency or autonomous-runner change. Do not extract a shared parser or refactor B1. Use the existing public `parse_identity_events`, `GoEvent`, `AdapterError`, `SimulatedExit` definitions from the pinned B1 tooling module; no private helpers, identity translation, FakeReplay or identity 180s timers are reused. Dependency drift at a future planning parent requires new comparison/review before gate synchronization.

## Exact public interfaces

All new dataclasses are frozen; collections are tuples. Concrete type checks reject bool where int is required. Use the public B1 `AdapterError` as the sole stable-code exception; never expose decoder/source text. Imports are `dataclasses`, `hashlib`, `json`, `re` and the four named B1 public symbols; the transitive B1 imports are standard library. No filesystem/process/network/clock imports or callback runtime are admitted.

```python
@dataclass(frozen=True)
class CatalogContext:
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str

@dataclass(frozen=True)
class CatalogCase:
    provider: str
    go_test_name: str
    events_raw: bytes
    stderr_raw: bytes
    receipt: SimulatedExit

@dataclass(frozen=True)
class CatalogOutcome:
    family: str
    logical_id: str
    status: str
    raw_refs: tuple[str, ...]
    events_sha256: str
    stderr_sha256: str
    failures: tuple[str, ...]

@dataclass(frozen=True)
class CatalogDiagnostic:
    contract: str
    observation_kind: str
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str
    status: str
    observations: tuple[CatalogOutcome, ...]
    accepted_case_credit: int
    profiles_enabled: bool
    enabled_tiers: tuple[str, ...]
    authority: tuple[tuple[str, bool], ...]

parse_catalog_events(raw: bytes) -> tuple[GoEvent, ...]
translate_catalog(cases: tuple[CatalogCase, ...], context: CatalogContext) -> CatalogDiagnostic
serialize_catalog_diagnostic(value: CatalogDiagnostic) -> bytes
```

`parse_catalog_events` directly delegates to the unchanged public B1 parser, propagating stable `AdapterError` codes. It checks grammar only, including no catalog identity admission. `translate_catalog` accepts exactly8 cases in any input order with exactly one literal `(provider,go_test_name)` per mapping. It validates **all** outer/context/receipt/slot/budget inputs before parsing any case or hashing any bytes. No partial result is emitted on caller-contract failure. Canonical output is always in inventory order.

Context requires exact CatalogContext concrete type, exact candidate above, exact inventory digest above, and source_manifest_sha256 lower64hex. This manifest digest is a caller claim, never proof that Stage A inspection occurred. No arbitrary expected-ID list, count, source path, authority, profile, argv or genuine runtime receipt parameter exists.

CatalogCase exact concrete type; provider/root exact strings from the eight mappings. `cases` exact tuple of length8. Unknown tuple => `case_identity`; duplicate or missing tuple => `case_set`; wrong outer/case type or wrong length => `cases_invalid`. Check order: context, tuple/type/length, every case concrete type and identity, set multiplicity, byte types/limits, receipt schema, aggregate bytes. Within any all-cases step use input order for deterministic first rejection; output remains canonical. Wrong context => `context_invalid`.

`events_raw` exact bytes<=67108864 per slot (`input_type` / `events_size`); `stderr_raw` exact bytes<=1048576 per slot (`stderr_type` / `stderr_size`). Sum of events+stderr across all8<=68157440 bytes inclusive (`aggregate_size`). This65MiB in-memory ceiling is an explicit synthetic resource restriction and is unrelated to acceptance-envelope or eventual raw transport limits. Empty Go bytes pass the outer schema then fail parser as `events_count`; zero-byte stderr is valid. Check integer lengths before hashing/parsing to avoid expensive work for rejected input. No truncation or discarded bytes.

`receipt` exact B1 SimulatedExit with exit_code None or concrete int[-255,255], and timed_out/interrupted/ownership_lost/cleanup_complete exact bools. Normal receipt requires exit_code, while None is allowed only if timed_out, interrupted, ownership_lost or cleanup incomplete. Invalid receipt => `receipt_invalid`. Receipt values are finite simulated observations only. B2 adds no fake timer scheduler: fixtures construct SimulatedExit directly. The producer's actual 90s Go and120s wait deadlines are source context, not implemented runtime behavior. Reusing B1 fake replay would introduce the wrong180s deadline and is forbidden.

## Restricted JSONL grammar

Adopt B1's exact frozen grammar, without extending compatibility:

- 1..65536 LF-separated nonempty object lines, <=1MiB each excluding delimiter; optional single final LF; no blank line, CRLF or raw CR, BOM, invalid UTF8 or surrogate strings.
- Total events<=64MiB per slot; JSON nesting<=32; every decoded string including keys<=65536 UTF8 bytes; duplicate keys and nonfinite numbers fail.
- Required keys exactly Time/Action/Package; optional Test/Elapsed/Output/FailedBuild; unknown keys and present null fail.
- Time nonempty <=128UTF8 bytes, opaque; Package nonempty <=256bytes; Test if present nonempty<=256bytes. Time/Output text cannot supply case identity or deadlines.
- Action exactly start/run/output/pass/fail/skip. pause/cont/bench and any other action => unsupported_go_action. start has no Test; run requires Test. Output exists iff action=output, string empty permitted. FailedBuild only on package fail, nonempty<=1024bytes. Elapsed concrete int/float, finite0..86400, never a deadline or pass proof.

Parser codes exactly B1's `input_type,events_size,events_count,line_size,line_delimiter,json_invalid,json_duplicate_key,json_nonfinite,json_depth,json_string,event_keys,event_type,unsupported_go_action`. Public parser raises. During translation, parser errors within the admitted outer limits produce an unavailable row with the parser code; no successful parsed prefix. All eight admitted cases are processed even when one parser fails. Stderr stays opaque, is hashed in full, and is never searched for status.

## Literal active mapping and retained-memory refs

Go root names and inventory IDs are exact, case-sensitive strings. The first element below is go_test_name; append the shown provider suffix only by the literal table. Do not split caller IDs, normalize suffixes, strip paths, fuzzy match or import a list from producer code.

| index | go_test_name | provider | logical_id |
|---:|---|---|---|
|0|TestPostgresCatalogLifecycleColdHTTPRaceOneJob|bankone|TestPostgresCatalogLifecycleColdHTTPRaceOneJob-bankone|
|1|TestPostgresCatalogLifecycleColdHTTPRaceOneJob|banktwo|TestPostgresCatalogLifecycleColdHTTPRaceOneJob-banktwo|
|2|TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP|bankone|TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-bankone|
|3|TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP|banktwo|TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-banktwo|
|4|TestPostgresCatalogLifecycleAtomicPublication|bankone|TestPostgresCatalogLifecycleAtomicPublication-bankone|
|5|TestPostgresCatalogLifecycleAtomicPublication|banktwo|TestPostgresCatalogLifecycleAtomicPublication-banktwo|
|6|TestPostgresCatalogLifecycleWarmReadsNoExternalCalls|bankone|TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-bankone|
|7|TestPostgresCatalogLifecycleWarmReadsNoExternalCalls|banktwo|TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-banktwo|

For each row, family is literal catalog. raw_refs exactly `(r3/<literal-provider>/<literal-root>/go-events.jsonl, r3/<literal-provider>/<literal-root>/go-stderr.log)` as fully materialized in the literal mapping appendix below. These refs designate the caller-retained byte strings only. No path is opened and no on-disk completeness claim is made. Events hash and stderr hash are SHA256 of exact input bytes, including the presence/absence of final LF. Extra package/support/JUnit/index-readiness cases contribute no IDs. The other172 final180 IDs are not emitted by B2.

## Per-slot lifecycle and status contract

Only one expected Go root exists in each process stream; it is the logical case, unlike B1's support root/five children. Every Package must be exact `github.com/lucronn/autodata/apps/api-go`. Any Test must be exactly this slot's root; a sibling root, identity test, nested `/child`, paid root or any foreign name => unknown_test. Output content is never interpreted.

A structurally valid stream has exactly one package start at index0, exactly one package pass/fail/skip as final event, and exactly one root run followed by exactly one root pass/fail/skip strictly inside the package interval. Root output occurs strictly after root run and strictly before root terminal; package output occurs strictly between package start and package terminal. Repeated outputs are allowed, contribute no IDs and cannot repair structure. Duplicate starts/runs/terminals, missing events, output after terminal, terminal before run or events after package terminal are failures. A package skip without any root still has root_lifecycle failure and cannot count as a skipped valid case; fail closed. No child event or other root is silently ignored.

Semantic failure vocabulary in fixed output order (deduplicated codes only, never deduplicate raw events):

`package_mismatch,unknown_test,package_lifecycle,root_lifecycle,root_failed,root_skipped,package_failed,package_skipped,simulated_nonzero,simulated_timeout,simulated_interrupted,ownership_lost,cleanup_incomplete`.

Record all detected structural, failure and receipt codes in this order. For a parser error, record the single parser code first then applicable receipt codes in the above receipt order; no semantic evaluation of partial events. No source text interpolation.

Each slot outcome precedence, exact:

1. Parser error => unavailable, even if the receipt is adverse; append applicable receipt codes.
2. Parsed valid grammar plus interrupted receipt => unavailable, regardless of otherwise clean or failed stream.
3. Wrong Package, unknown Test, package/root structural failure, any package/root fail, nonzero exit, timeout, ownership loss or cleanup incomplete => failed.
4. Otherwise package/root skip => skipped. This requires the structurally valid complete run/skip pattern described above and a normal exit0 complete-cleanup receipt.
5. Otherwise => passed, requiring root and package pass and normal exit0 complete-cleanup receipt.

Failure of one slot does not rewrite the other seven independent slot rows. A root fail followed by package pass remains failed. Root/package pass plus timeout remains failed. Root skip plus nonzero exit remains failed. Root skip without a run remains failed. Receipt stderr noise cannot alter results.

Top status precedence after all8 rows: interrupted if **any** admitted receipt.interrupted; otherwise unavailable if any unavailable row; otherwise inconsistent if any nonpassed row; otherwise consistent. This can yield top interrupted with an unavailable malformed row, and retains every slot's parser/receipt codes. Top status is deterministically recomputed by the serializer from row status and presence of simulated_interrupted code; it is not caller authority. All8 passed means only synthetic event/profile consistency, never source bank execution, full raw semantics or acceptance.

## Serialization and false authority

Contract literal `workshop-final180-catalog-go-synthetic-v1`; observation_kind literal `simulated-source-profile-validation`. Top fields exactly CatalogDiagnostic fields listed above. Per-row fields exactly CatalogOutcome fields. No hidden summary-count, genuine-run, supervisor or runtime-lock field. All8 ordered observations are required even when unavailable. JSON output is compact sorted-key ensure_ascii=True allow_nan=False UTF8 with exactly one LF, <=65536 bytes. Tuple pairs for authority serialize as a JSON object; enabled_tiers and all tuple sequences serialize as arrays. Reject wrong concrete types, extra/missing/out-of-order IDs, refs, statuses, digests, failure codes/ordering, count/authority claims or top-status mismatch with `diagnostic_invalid`; return no partial bytes. Failure tuples must contain only the fixed codes, without duplicates, in the specified order, and at most one parser code. A parser code may coexist only with receipt codes; no semantic lifecycle code may follow a parser error. Validator must derive each row status from its stable failure list: parser-code present => unavailable; otherwise simulated_interrupted => unavailable; otherwise the rule3 poison codes => failed; otherwise skip codes => skipped; otherwise passed. It can validate consistency of claimed hashes but cannot authenticate bytes absent from serialization input.

accepted_case_credit exact int0 (bool rejected); profiles_enabled exact False; enabled_tiers empty tuple. Authority has exactly these nine pairs in this order and all values exact False: fixture_verified, product_candidate_verified, staging_verified, deployment_authorized, cutover_verified, implementation_authorized, runtime_execution_authorized, profile_promotion_authorized, merge_authorized. Serialization revalidates all fields. No result, successful unit suite or consistent diagnostic can enable a tier/profile. Coordinating runtime_lock/run_record stay null. No acceptance envelope or normalized full180 observation file is emitted.

## Fake-only test requirements and representative construction

Use unittest and deterministic constructed JSONL; no recorded genuine-run fixture. Example test helper (all strings constant or literal table entries):

```python
import json
from scripts.dev.workshop_final180_identity_adapter import SimulatedExit

def fake_stream(root, terminal='pass'):
    def event(action, test=None):
        row = {'Time': 'synthetic', 'Action': action,
               'Package': 'github.com/lucronn/autodata/apps/api-go'}
        if test is not None:
            row['Test'] = test
        return json.dumps(row, separators=(',', ':')).encode() + b'\n'
    return b''.join((event('start'), event('run', root),
                     event(terminal, root), event(terminal)))

normal = SimulatedExit(0, False, False, False, True)
```

Test matrix is mandatory; each is an observable contract regression:

1. Eight independently constructed slot inputs translate to exact8 ordered literal IDs; reverse inputs and require identical canonical diagnostic bytes. Two bank slots intentionally sharing byte-identical events still remain two synthetic context rows with zero credit; document no bank authentication.
2. Missing/duplicate/unknown slot, wrong provider/case, case suffix mutation, wrong tuple/dataclass type, int/bool exit confusion, wrong candidate/inventory/source hash and invalid None normal exit fail before parse; every caller-schema failure returns no diagnostic.
3. Parser: empty input, empty interior/extra final line, CRLF/raw CR, BOM/bad UTF8/surrogate, duplicate nested/top keys, NaN/infinity, null, nonobject, unknown field/action/pause/cont/bench, action-specific Test/Output/FailedBuild rules, depth/string/line/event/byte limits. Exact allowed boundaries pass; +1 rejects. Public B1 parser parity required for catalog wrapper. Event count/max-byte tests may use mocking only of input construction helpers, never bypass adapter checks.
4. Lifecycle: duplicate/missing start/run/root terminal/package terminal, wrong root/nested child/package, early package terminal, output before run/after root end/after package end, failure hidden behind package pass, literal status words in Output, repeated outputs. No raw-event deduplication.
5. Receipts: each adverse flag separately plus combinations, nonzero signed exit, null permitted only with adverse receipt, clean stream cannot override timeout/interrupt/ownership/cleanup/nonzero; parser error+interruption returns unavailable row and top interrupted; one malformed slot leaves seven independently parsed rows; top precedence and per-slot code ordering exact.
6. Skip: valid run/skip + normal receipt => skipped/inconsistent; missing run skip => failed; skip+nonzero => failed; package skip without root => failed; root fail/package skip => failed.
7. Hashes and opacity: exact byte hashes, optional final LF changes only corresponding digest, zero stderr accepted, invalid UTF8 stderr stays opaque, identical bytes cannot upgrade bank proof. Synthetic source_manifest digest accepted only as claim.
8. Limits: per-file ceiling inclusive, aggregate65MiB inclusive/+1,65536lines inclusive/+1, <=1MiB lines inclusive/+1, context limits before parse/hash. No successful prefix on a late malformed line.
9. Serializer tampering: dataclasses.replace any authority True, accepted credit1/True, nonempty enabled tier, changed contract/kind, wrong/order/extra ID/ref, invalid status/failure/code order, altered overall status/hash shape must raise diagnostic_invalid. Canonical LF/ASCII escaping/size bound and repeatability asserted.
10. Static AST import/call audit: allow only the four listed standard-library imports plus four B1 public symbols; reject subprocess/socket/HTTP/Docker/os/pathlib/time/signal/eval/exec/open/importlib/dynamic imports/callback execution. No __main__ entrypoint. Check unchanged Stage A/B1 files and their tests.

## Implementation work and verification

### Task 1 — parser delegation and per-slot lifecycle translation, both new module and new tests.

- [ ] Write failing unittest cases for eight mappings, strict caller schemas, B1 parser parity, package/root lifecycle, provider ambiguity, receipt precedence and hashes, using fake_stream and constructed SimulatedExit.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_catalog_adapter.py -v`; require expected failures before implementation.
- [ ] Define the frozen types/constants and exact public interfaces above; delegate only syntax parser; validate all admitted outer shapes/budgets first; evaluate each slot independently and emit frozen canonical mapping.
- [ ] Complete adversarial parser/lifecycle/receipt/limit cases and run catalog+B1+Stage A focused suites. No fixture execution. Commit a coherent passing milestone `feat: add synthetic catalog Go-event translation` and promptly push to assigned feature branch.

### Task 2 — serializer boundary and runbook, same three-path implementation allowlist.

- [ ] Add failing serializer tamper/top-status/authority/bounds/canonicalization and AST checks, then implement exact strict serializer and fixed failure vocabulary.
- [ ] Document B2 synthetic-only status, bank identity limitation, zero credit, exact gate reference and separate remaining validator/runtime gates in the runbook.
- [ ] Run full allowed offline checks below; inspect diff against exact planning checkpoint and unchanged B1/Stage A pins. Commit `test: verify synthetic catalog boundary and document limitations` and promptly push validated milestone.
- [ ] Return exact head, tests and diff/allowlist hashes to independent reviewer. No merge, runtime, profile promotion or genuine compatibility claim.

Commands after a future authorized implementation, not results of this draft:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_catalog_adapter.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_identity_adapter.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_runner.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/dev -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
git diff --check
```

Add a no-bytecode `compile(source,filename,'exec')` check for changed Python paths and a read-only Git diff allowlist check against authorizing checkpoint. These commands are offline suite checks; no producer CLI, Docker, browser, network, provider or payment call is authorized. If discovery includes any actual runtime opt-in suites, keep opt-in flags absent and do not run externally provisioned integration phases.

## Future tracking/preflight/review order

1. Coordinator retains the reported independent external-draft review PASS and its exact draft/report hashes; committed-checkpoint review is still required. Any request for complete catalog acceptance or bank authentication changes the scope and requires a new design, not removal of caveats.
2. Coordinator verifies B1 exact-head review and source/dependency pins, chooses planning parent descending from reviewed B1 head, promotes this technical contract and literal pins/mappings into the repository spec (self-contained; external mutable files are audit locators only), creates matching plan/task/record and updates canonical assembler plan. Do not change existing inventory or prior gate records. The planning author has embedded literal source/mapping data in the canonical spec; compare those bytes before synchronization.
3. Sole serialized tracking writer updates existing Issue186 and Project8 item, preserving previous history and other fields. State same goal, references, exact three-path allowlist, concrete todo, zero authority and incomplete complete-validator/runtime successor. Retain authenticated Issue/comments/Project readbacks with hashes and timestamp. Existing B1 Project item ID is historical reference only; verify current item/fields before write.
4. Only after live tracking matches the repository content, set the new record status synchronized with accurate updated_at and tracking receipts; copy matching object into the task's pre_implementation. No fabricated readback/preflight/review receipt. Commit/push the planning checkpoint. The plan and canonical documents must exist at that exact SHA; a later uncommitted plan never authorizes implementation.
5. At exact checkpoint B2, run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-workshop-final180-stage-b2-catalog-go.json --base-sha <B2-full40> --repo-root <owned-root>` and independently validate the nested task pre_implementation object with the same machine validator/exact base. Retain full output+hash. Failure/missing freshness blocks dispatch. No use of this draft's invalid gate-template as a passing record.
6. Independent gate reviewer reads exact B2 SHA, tracking readback, source/mapping/dependency pins, preflight, allowlist and status contract. Require PASS with an exact-head receipt. Coordinator explicit dispatch pins B2, assigned feature branch, implementation allowlist and fake-only scope; status alone supplies no execution authority.
7. Builder commits/pushes small validated milestones. Reviewer inspects exact implementation head, stable frozen boundaries, all tests and no out-of-allowlist changes. Coordinator synchronizes code-only verification with Issue186/Project8/canonical record at exact head; preserve actual review provenance and remaining blockers. Any repair commit receives the necessary repeated focused checks and final exact-head review.

Runtime locks, process supervision, filesystem raw admission, genuine producer compatibility, full JUnit/result/SQL/nested semantics, final180 collection and acceptance profile promotion remain separate gates. This draft neither executes nor authorizes them.

## Planning record (tracking synchronized; committed checkpoint pending)

The exact same object is the task pre_implementation value. Live tracking is synchronized; this record still requires a committed exact checkpoint, passing preflight, independent gate review and explicit dispatch before implementation.

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
  "authorizing_checkpoint_sha": null,
  "goal": "Add a bytes-only synthetic catalog8 Go-root adapter, with eight literal provider/root slots, no execution, zero accepted-case credit and every authority false.",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "plan_ref": "docs/superpowers/plans/2026-11-04-workshop-final180-stage-b2-catalog-go.md",
  "planning_parent_sha": "54a7ca32eab80654310d862f0ac6957375d16e8b",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/agents/specs/2026-11-04-workshop-final180-stage-b2-catalog-go.md",
    "docs/agents/specs/2026-11-04-workshop-final180-inventory.json",
    "docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md"
  ],
  "selected_candidate_sha": "4d82e413e04fb2401ac7bc28dc828375ac662180",
  "status": "synchronized",
  "todo": [
    "Synchronize B2 plan/spec/task/record and exact three-path implementation allowlist with Issue186 and Project8, preserving prior history; commit the checkpoint descending from reviewed B1 and pass exact-base standalone/nested preflight plus independent review before explicit dispatch.",
    "Implement bytes-only eight-slot catalog Go-event translation using the pinned B1 public parser without altering it; freeze bank-context limitations, per-slot lifecycle rules, byte bounds, status precedence and strict serialization.",
    "Add failing-first fake-only adversarial tests for grammar, exact IDs/slots, lifecycle, receipts, limits, serialization and unchanged B1/Stage A behavior.",
    "Update the runbook; run focused/developer/autonomy and allowlist checks; commit/push validated milestones and obtain independent exact-code-head review.",
    "Synchronize code-only verification at the exact implementation SHA while preserving null runtime lock/run record, disabled profiles and all authority false; retain separate blockers for complete catalog raw semantics and real runtime."
  ],
  "tracking_receipts": {
    "status": "synchronized_live_readback",
    "issue_detail_ref": "https://github.com/lucronn/autodata/issues/186#issuecomment-6638148203",
    "issue_preserved_comment_count": 156,
    "issue_comment_count": 157,
    "issue_body_unchanged": true,
    "prior_comments_preserved": true,
    "issue_readback_ref": "/home/corp/autodata-evidence/final180-b2-gate-tracking/issue-after.json",
    "issue_readback_sha256": "36ac5feb361ee7ce677205148c46d81f03aab01b30d415c8a82ebf1f657abd8c",
    "project_item_id": "PVTI_lAHOCSJ8cc4BiQ2BzhFocs4",
    "project_field_id": "PVTF_lAHOCSJ8cc4BiQ2BzhhJhxU",
    "project_status": "In Progress",
    "project_readback_ref": "/home/corp/autodata-evidence/final180-b2-gate-tracking/project-after.json",
    "project_readback_sha256": "e58de8d627d5faf354aad1f6c3bda4ca128a3c1f9d3dcf0f15a63e4a9e4d80cd",
    "project_source_sha256": "f210e9b9568dfa16b3725efb16c533f4722107693db9b74e2e403d018f3c7e30",
    "prior_project_source_sha256": "dc72aeabd265ddcd9a61574f215f22ac2dd2a043d16aaa18970f3a5134e11b47",
    "previous_source_archived_verbatim": true,
    "other_project_fields_unchanged": true,
    "writer": "coordinator sole serialized writer"
  },
  "updated_at": "2026-11-04T18:04:13.205947+00:00",
  "external_draft_artifacts": {
    "DRAFT.md": {
      "bytes": 30745,
      "sha256": "dbd9bcbd231d04c169675f8915c0568917073a162ae9431dc233dcbf1bca0c1a",
      "historical_locator": "/home/corp/autodata-evidence/final180-b2-planning/DRAFT.md"
    },
    "report.json": {
      "bytes": 3864,
      "sha256": "dd3c0fddc747269b071b7e0fbc5fc10bec23bb653efa8dc1d0de6c59e7e99656",
      "historical_locator": "/home/corp/autodata-evidence/final180-b2-planning/report.json"
    },
    "provenance.json": {
      "bytes": 34245,
      "sha256": "31c274bd666ea8b237ec095a272b0c4e935d5b6e471b75ea4ce61e499e2f7145",
      "historical_locator": "/home/corp/autodata-evidence/final180-b2-planning/provenance.json"
    },
    "literal-mappings.json": {
      "bytes": 13438,
      "sha256": "ba7b32cc58b7d302034a4a41444e73c052c32e313938a87b75188697758b30d6",
      "historical_locator": "/home/corp/autodata-evidence/final180-b2-planning/literal-mappings.json"
    },
    "gate-template.json": {
      "bytes": 2398,
      "sha256": "adf96cd71ea9faccbff8361157066af330c920b925cff868ffd64b7df4935010",
      "historical_locator": "/home/corp/autodata-evidence/final180-b2-planning/gate-template.json"
    },
    "verification.json": {
      "bytes": 903,
      "sha256": "fd214ec174ce01728a741fba0444859e246badd348265a344ed182a2c77d7bcf",
      "historical_locator": "/home/corp/autodata-evidence/final180-b2-planning/verification.json"
    }
  },
  "draft_review": {
    "status": "PASS",
    "provenance": "Coordinator-reported independent approved external draft/report review with no findings; no separate saved receipt asserted.",
    "draft_sha256": "dbd9bcbd231d04c169675f8915c0568917073a162ae9431dc233dcbf1bca0c1a",
    "report_sha256": "dd3c0fddc747269b071b7e0fbc5fc10bec23bb653efa8dc1d0de6c59e7e99656"
  },
  "committed_gate_review": {
    "status": "pending",
    "checkpoint_sha": null
  },
  "implementation_allowlist": [
    "scripts/dev/workshop_final180_catalog_adapter.py",
    "scripts/dev/test_workshop_final180_catalog_adapter.py",
    "docs/verification/workshop-final180-runbook.md"
  ],
  "reviewed_b1_head_sha": "54a7ca32eab80654310d862f0ac6957375d16e8b",
  "historical_b1_gate_sha": "006fab0d1380c2506330bbc0b48397a32294b6cc",
  "runtime_lock": null,
  "run_record": null,
  "accepted_case_credit": 0,
  "profiles_enabled": false,
  "enabled_tiers": []
}
```

## Implementation handoff literal mapping

```json
[
  {
    "family": "catalog",
    "go_test_name": "TestPostgresCatalogLifecycleColdHTTPRaceOneJob",
    "index": 0,
    "logical_id": "TestPostgresCatalogLifecycleColdHTTPRaceOneJob-bankone",
    "provider": "bankone",
    "raw_refs": [
      "r3/bankone/TestPostgresCatalogLifecycleColdHTTPRaceOneJob/go-events.jsonl",
      "r3/bankone/TestPostgresCatalogLifecycleColdHTTPRaceOneJob/go-stderr.log"
    ]
  },
  {
    "family": "catalog",
    "go_test_name": "TestPostgresCatalogLifecycleColdHTTPRaceOneJob",
    "index": 1,
    "logical_id": "TestPostgresCatalogLifecycleColdHTTPRaceOneJob-banktwo",
    "provider": "banktwo",
    "raw_refs": [
      "r3/banktwo/TestPostgresCatalogLifecycleColdHTTPRaceOneJob/go-events.jsonl",
      "r3/banktwo/TestPostgresCatalogLifecycleColdHTTPRaceOneJob/go-stderr.log"
    ]
  },
  {
    "family": "catalog",
    "go_test_name": "TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP",
    "index": 2,
    "logical_id": "TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-bankone",
    "provider": "bankone",
    "raw_refs": [
      "r3/bankone/TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP/go-events.jsonl",
      "r3/bankone/TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP/go-stderr.log"
    ]
  },
  {
    "family": "catalog",
    "go_test_name": "TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP",
    "index": 3,
    "logical_id": "TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-banktwo",
    "provider": "banktwo",
    "raw_refs": [
      "r3/banktwo/TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP/go-events.jsonl",
      "r3/banktwo/TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP/go-stderr.log"
    ]
  },
  {
    "family": "catalog",
    "go_test_name": "TestPostgresCatalogLifecycleAtomicPublication",
    "index": 4,
    "logical_id": "TestPostgresCatalogLifecycleAtomicPublication-bankone",
    "provider": "bankone",
    "raw_refs": [
      "r3/bankone/TestPostgresCatalogLifecycleAtomicPublication/go-events.jsonl",
      "r3/bankone/TestPostgresCatalogLifecycleAtomicPublication/go-stderr.log"
    ]
  },
  {
    "family": "catalog",
    "go_test_name": "TestPostgresCatalogLifecycleAtomicPublication",
    "index": 5,
    "logical_id": "TestPostgresCatalogLifecycleAtomicPublication-banktwo",
    "provider": "banktwo",
    "raw_refs": [
      "r3/banktwo/TestPostgresCatalogLifecycleAtomicPublication/go-events.jsonl",
      "r3/banktwo/TestPostgresCatalogLifecycleAtomicPublication/go-stderr.log"
    ]
  },
  {
    "family": "catalog",
    "go_test_name": "TestPostgresCatalogLifecycleWarmReadsNoExternalCalls",
    "index": 6,
    "logical_id": "TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-bankone",
    "provider": "bankone",
    "raw_refs": [
      "r3/bankone/TestPostgresCatalogLifecycleWarmReadsNoExternalCalls/go-events.jsonl",
      "r3/bankone/TestPostgresCatalogLifecycleWarmReadsNoExternalCalls/go-stderr.log"
    ]
  },
  {
    "family": "catalog",
    "go_test_name": "TestPostgresCatalogLifecycleWarmReadsNoExternalCalls",
    "index": 7,
    "logical_id": "TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-banktwo",
    "provider": "banktwo",
    "raw_refs": [
      "r3/banktwo/TestPostgresCatalogLifecycleWarmReadsNoExternalCalls/go-events.jsonl",
      "r3/banktwo/TestPostgresCatalogLifecycleWarmReadsNoExternalCalls/go-stderr.log"
    ]
  }
]
```

## Exact source/dependency pins

Full literal citation text and all180 expected IDs are embedded in the canonical specification; the implementation consumes this fixed eight-slot mapping only. These pins refer to immutable source Git objects.

```json
[
  {
    "bytes": 30980,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "5b16ff5b5428547fcdeb09fb63c36c94a406ff6c",
    "path": "workers/ingestion-python/tests/test_catalog_api_integration.py",
    "sha256": "88e6c1fd339da60614056abd7689b6a7fcd1d16bc1e239cec888b06bb6a61974"
  },
  {
    "bytes": 40868,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "b0db236512e08851bb87c3e33cc76622e10a8378",
    "path": "apps/api-go/postgres_catalog_lifecycle_test.go",
    "sha256": "a8ec30ca66629cc0317c511450e5660911a0d90d79daa52b1816bbd781bc7943"
  },
  {
    "bytes": 3986,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "16982a9310be7447103e2bfacecf9f7cb764704e",
    "path": "apps/api-go/go.mod",
    "sha256": "3306c3736c51a3c08a4ed30613a9f0ba4db7f5094d0215ebdf54545873012923"
  },
  {
    "bytes": 19309,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "ac52c479e5e4a7f625cddd409d8d61573c271765",
    "path": "workers/ingestion-python/tests/lifecycle_support.py",
    "sha256": "746eba57bfffb760e2f779d0d0494125f8b559b07de5ff6ec11099d517bf76dc"
  },
  {
    "bytes": 1662,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "75bdbb276a5af737e9ab9651bee0d9e923320650",
    "path": "db/migrations/035_ordered_article_document.sql",
    "sha256": "fe8d1d8a69b4f2e84e9ea0770044f45ff49d2a4b3d01a09db85c49fbc5e1d2ce"
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
    "bytes": 122350,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "24ac3e9264b85eb914daa7805d183e15f58d374a",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.json",
    "sha256": "c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39"
  },
  {
    "bytes": 10852,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "97a3ee48e443547f538e369ebd4557644e9fec3c",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.md",
    "sha256": "55fc12a771576778fb652ea8fcc3e8b81492ff3abc6fef0f00cc7fa3b015037a"
  },
  {
    "bytes": 33663,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "c0948a5b604b9ae5f0ce31ab2e7864cbc9b8d527",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-runner.md",
    "sha256": "24d209a60ae2dcda461d1a65932c2dd37d6894ed7a9c3920f989fe8ff0b20ba3"
  },
  {
    "bytes": 82081,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "4a29e0915c677a2f07e3ca6b0ab9109e888651d1",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-stage-b1-identity.md",
    "sha256": "285e5abfe824b4b9490af8e4b2fa3655f53ea34d8afc631e69a88feb909d242a"
  },
  {
    "bytes": 22290,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "8c7fa87bab906955c145d7cc965be641aea48c5f",
    "path": "scripts/dev/workshop_final180_identity_adapter.py",
    "sha256": "0474a85c33d4f2722ad01d6e55e69a8080dc0f1983c856ca7caa1b94510a767d"
  },
  {
    "bytes": 29838,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "7391263cb874e2505f4f110df6343c8b466fc692",
    "path": "scripts/dev/test_workshop_final180_identity_adapter.py",
    "sha256": "a3f3017b1d7a85da9ae4d1883758f2494d722fb321d45c1ff758994ab6d2653c"
  },
  {
    "bytes": 47124,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "ca48cd988c5579a7d385dc1844b84306eae0861e",
    "path": "scripts/dev/workshop_final180_runner.py",
    "sha256": "693a408a73f3ccd37bf945bfc94d427f742878580932dab382ea9a244a141c91"
  },
  {
    "bytes": 13237,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "094cceff7b0a6a2259cf3354b61b31af5bab60c8",
    "path": "docs/verification/workshop-final180-runbook.md",
    "sha256": "3658ca8a8571454c6c027b6e619dbb391578df9159b2a6ca7e4c42be4de227d5"
  },
  {
    "bytes": 5659,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "41076af1db25f0cff8ca41d0203c050af9b772df",
    "path": "docs/agents/pre-implementation-gate.md",
    "sha256": "fa6e9c95c2674164c90d78e046a0427f6b406c313fb82ff627a2a2facb560ad0"
  },
  {
    "bytes": 8645,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "595ccf5f84c8e5ff7aa29dcc2a9284b8b7421f39",
    "path": "scripts/autonomy/pre_implementation.py",
    "sha256": "af5cf8d987dea0d63f98865a6b6bcf1d730f044a9e6dc14509a91aeb0505f1ec"
  },
  {
    "bytes": 9719,
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "git_blob": "3120ae8753aedb4cb5ff0ac3dd9c8c662675e2f4",
    "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-b1-identity.json",
    "sha256": "7f8f437f7b536c327ad7135ebc8aab64ba8ff263363358f58bd19739df81a573"
  },
  {
    "bytes": 5060,
    "commit": "006fab0d1380c2506330bbc0b48397a32294b6cc",
    "git_blob": "e52a6813c24dbf71ebcf9ebcb209d447cac48e1c",
    "path": "docs/agents/records/2026-11-04-workshop-final180-stage-b1-identity.json",
    "sha256": "8b518c6c467906768f3b00cf83d78fac8b64ad9469f5182c86a198286b6f29a0"
  }
]
```


## Code-only implementation verification (2026-11-04)

This appended delivery snapshot supplements the historical planning text above; it does not rewrite the synchronized gate record or grant new authority. The authorizing checkpoint is `3cd99224eae7012f8c6cc0bfc15a1053a8e7762f`. Draft [PR #230](https://github.com/lucronn/autodata/pull/230) contains the two validated, pushed implementation milestones `7ea63d77acb5a0972dd86b2b138017fe9b6f288b` and `0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471` on `codex/workshop-final180-stage-b2-build`. The latter is the exact reviewed code head; this docs branch does not contain those implementation changes.

Captured builder verification at that head reports 100 focused tests passing, including all 23 catalog tests, and 146 autonomy tests passing. Standalone/nested preflight, the exact three-path implementation allowlist, unchanged Stage A/B1 predecessor hashes, static AST restrictions, syntax and diff checks passed. Every evidence-manifest entry, exact implementation Git-object hash and predecessor hash was rechecked for this documentation milestone. The independent `/root/final180_b2_code_review` session reported PASS with no findings at the exact head and reran the 100 focused tests, as relayed by the coordinator; no separate saved reviewer receipt exists.

The broad developer suite remains **pending/unverified**. The builder snapshot had no final summary, and the coordinator subsequently reported that PID906630 exited without a captured completion summary. No broad-suite pass is claimed. Its historical log is `/home/corp/autodata-evidence/final180-stage-b2-builder/dev-suite.log`; discovery started before three additional grammar/schema tests were added, while current-source focused coverage includes all 23 catalog tests.

The code-only audit record is `docs/agents/records/2026-11-04-workshop-final180-stage-b2-code-review.json`. Builder handoff SHA256 is `a0e548105d7f69e708c5c6d19a78ef338009880285cce6b2de7ab53f2e67428f`; the evidence manifest SHA256 is `6cbf2eee14127926a0bb8f397b6908488cefffca71051e7298ca242da9c52a36`. Both refer to local audit artifacts under `/home/corp/autodata-evidence/final180-stage-b2-builder/`. GitHub completion tracking remains coordinator-owned and is not asserted here.

B2 translates eight synthetic caller-selected slots. Go bytes cannot authenticate bank attribution; identical bytes across bank slots remain permitted. Complete catalog raw semantics, cross-artifact identity/JUnit/result bindings, nested document/JSONB validation, retained runtime/migration support and an admitted runtime lock/profile remain blockers for real evidence. Accepted-case credit stays exactly zero, profiles stay disabled, enabled tiers stay empty, runtime lock and run record stay null, and all nine authorities stay false. Code review establishes no real-case, runtime, merge, deployment or profile-promotion authority.


## Broad developer validation addendum (2026-11-04)

The coordinator reran `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/dev -p 'test_*.py'` from the exact clean B2 code head `0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471`. At `2026-11-04T18:23:15Z`, the command exited zero with `Ran 360 tests in 441.530s` and `OK`. This supersedes the earlier pending/unverified broad-suite delivery status; that builder attempt remains preserved as historical evidence in the code-review record.

The coordinator-attributed receipt is `/home/corp/autodata-evidence/final180-b2-coordinator-broad/receipt.json`, SHA256 `cdf5153bf57e8064c5021122056726261dc9d18943d36c05d1e7bd6a73f032aa`. Its hash and exact-head/result fields were checked for this docs addendum. Full stdout was not persisted; the coordinator conversation's command/tool output is the primary result receipt. This is local offline developer validation and establishes no CI or real runtime acceptance. All nine authorities remain false, accepted-case credit remains zero, profiles remain disabled, enabled tiers remain empty, and runtime lock/run record remain null.
