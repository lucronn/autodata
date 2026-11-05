# Workshop final180 Stage B2 catalog Go-event adapter specification

**Status:** Issue186/Project8 planning synchronized at https://github.com/lucronn/autodata/issues/186#issuecomment-6638148203; committed B2 checkpoint, standalone/nested exact-base preflight, independent exact-checkpoint review and explicit coordinator dispatch remain pending. This document is planning only. No B2 implementation or runtime authority follows from this tracking update.

**Goal:** Add a bytes-only synthetic catalog8 Go-root adapter, with eight literal provider/root slots, no execution, zero accepted-case credit and every authority false.

**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8

**Planning parent / reviewed B1 code head:** `54a7ca32eab80654310d862f0ac6957375d16e8b`. **Application candidate:** `4d82e413e04fb2401ac7bc28dc828375ac662180`. **Historical B1 gate:** `006fab0d1380c2506330bbc0b48397a32294b6cc`. These are distinct identities; the B1 gate does not authorize B2.

The coordinator reports independent external draft/report review PASS with no findings, bound to draft SHA256 `dbd9bcbd231d04c169675f8915c0568917073a162ae9431dc233dcbf1bca0c1a` and report SHA256 `dd3c0fddc747269b071b7e0fbc5fc10bec23bb653efa8dc1d0de6c59e7e99656`. No saved reviewer receipt or committed-checkpoint review is invented. External paths below are historical audit locators; the technical contract, mappings and source pins are embedded here. Live tracking readback is https://github.com/lucronn/autodata/issues/186#issuecomment-6638148203; the prior Issue body/comments and all unrelated Project fields were preserved. Historical draft/report status fields describe their original creation, not current synchronization.

## Decision and source sufficiency

Choose catalog8 event translation as B2. The immutable catalog producer fixes four Go roots, paired with bankone then banktwo, and runs one separate Go process for each tuple. Its `validate_go_events` checks the exact package, no fail/skip action, exactly one root run/pass and a final package pass. This supplies an independently implementable event-translation contract. B2 adds the same explicit restricted grammar and package lifecycle admission used by B1, under synthetic-only trust.

Complete catalog8 evidence validation remains blocked. The inventory requires matching JUnit plus result identity and all retained per-case migration/runtime support, not just Go events. The corrected source addendum resolves outer SQL columns/types/nullability and declared source shapes, but explicitly leaves full nested document/JSONB semantics and raw assertion translation unfinished. Exact pytest/plugin JUnit emission remains unobserved. LifecycleRuntime dynamically emits additional support files; a complete typed file inventory and bounds remain unpromoted. No actual image/tool/cache/runtime lock or independent registered profile exists. A planner could design a broader restricted semantic validator later, but those decisions are not supplied by these sources and cannot be silently inferred here.

The bank attribution limitation is source-confirmed: raw Go events name only the root and package; `go-measurement.json` has phases/views/assertions and no mandatory provider/candidate identity (Go source lines97–119). The Python process environment sets provider and the final result repeats provider/root/candidate, but neither is authenticated in this slice. Therefore no event parser can independently infer or prove bankone versus banktwo from these bytes. B2 deliberately translates eight **synthetic caller-selected slots**, never eight executed bank cases. Passing both slots with identical bytes is possible and earns no real credit. Rejecting identical hashes would invent a source guarantee and is not specified. Future real evidence requires independently admitted receipt/path/manifest/process/environment/result/JUnit bindings and semantic support.

If the desired B2 scope is a complete catalog family validator or any real case credit, the precise blocker is this missing admitted cross-artifact identity/provenance/semantic contract. The viable narrower alternative is the adapter below. This specification does not weaken the inventory's eventual requirements.

## Source citations and exact pins

The embedded source provenance below contains full commit/path/Git blob/byte length/SHA256 pins and literal line citations with their own SHA256. The embedded literal mappings below embed all180 inventory IDs and the active eight slots. The inventory bytes digest is `c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39`. No consumer imports candidate code or regenerates expected IDs at runtime.

Active direct sources at application candidate4d82e413:

- `workers/ingestion-python/tests/test_catalog_api_integration.py:28–40`: four GO_NAMES and required fixture flag; lines460–469: exact event validator; lines472–481: ordered provider/root pairing and result identity; lines511–537: per-slot environment, exact Go command and source deadlines; lines538–580: additional independent measurement/runtime/migration/result requirements.
- `apps/api-go/postgres_catalog_lifecycle_test.go:36–74`: fixture flags/database/provider/candidate/control setup; lines97–119: raw measurement payload; lines216–233: nested document/body/steps/images projection; lines403,478,530,588: the four literal Go root declarations; lines287–289: index readiness remains support inside the cold root.
- `apps/api-go/go.mod:1`: `github.com/lucronn/autodata/apps/api-go`.
- The immutable inventory/spec, Stage A spec/runner, B1 spec/parser/test, runbook and canonical gate are pinned separately at B1 head. Importing the tooling parser is permitted; importing application/producer code is forbidden.

The corrected gap-closure report and every named external artifact were rehashed; all62 addendum source pins were compared against candidate Git objects. This is source verification, with no fixture execution. See the embedded source provenance for the report's exact digest and artifact list. It does not establish runtime compatibility, independent review or authority.

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

For each row, family is literal catalog. raw_refs exactly `(r3/<literal-provider>/<literal-root>/go-events.jsonl, r3/<literal-provider>/<literal-root>/go-stderr.log)` as fully materialized in the embedded literal mappings. These refs designate the caller-retained byte strings only. No path is opened and no on-disk completeness claim is made. Events hash and stderr hash are SHA256 of exact input bytes, including the presence/absence of final LF. Extra package/support/JUnit/index-readiness cases contribute no IDs. The other172 final180 IDs are not emitted by B2.

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

## Embedded literal mappings (normative)

The active eight rows and fully materialized raw_refs are normative. The other172 IDs are frozen inventory context and are never emitted by this adapter. No runtime import or regeneration of expected IDs is permitted.

```json
{
  "accepted_case_credit": 0,
  "active_catalog_mapping": [
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
  ],
  "all180_expected_ids": {
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
  "contract": "final180-b2-catalog-go-mappings-draft-v1",
  "expected_counts": {
    "browser_api": 21,
    "browser_dto": 120,
    "catalog": 8,
    "commerce": 14,
    "identity": 5,
    "paid": 12,
    "total": 180
  },
  "inventory_sha256": "c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39"
}
```

## Embedded inspected source provenance

These exact source bytes and citations were rechecked by this planning author against Git objects. External source artifact entries are audit pins only; their shapes are not promoted to a complete semantic validator. Original provenance booleans and historical draft labels remain source-only claims. Every enabled-tier, profile, runtime and authority restriction in the contract above applies.

```json
{
  "acceptance_claimed": false,
  "accepted_case_credit": 0,
  "all_addendum_source_pins_rechecked": 62,
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
  "authorizing_b2_checkpoint_sha": null,
  "candidate_sha": "4d82e413e04fb2401ac7bc28dc828375ac662180",
  "contract": "final180-b2-read-only-provenance-draft-v1",
  "enabled_tiers": [],
  "external_source_artifacts": [
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
    },
    {
      "bytes": 3597,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/report.json",
      "sha256": "36670a61779baa5ec2dd40d879b485c32d2a41907e1f971507ad450ca1a679ae"
    }
  ],
  "historical_b1_gate_sha": "006fab0d1380c2506330bbc0b48397a32294b6cc",
  "inventory_sha256": "c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39",
  "network_executed": false,
  "profiles_enabled": false,
  "proposed_planning_parent_sha": "54a7ca32eab80654310d862f0ac6957375d16e8b",
  "reviewed_b1_head_sha": "54a7ca32eab80654310d862f0ac6957375d16e8b",
  "runtime_executed": false,
  "source_only": true,
  "sources": [
    {
      "bytes": 30980,
      "citations": [
        {
          "claim": "Four source roots and explicit required/skip fixture flags",
          "end_line": 40,
          "sha256": "328aae6e90f5e88903b17dd832d928c0bcbba2d83b61d1229491eeb235b7bcc7",
          "start_line": 28,
          "text": "ROOT = Path(__file__).resolve().parents[3]\nARTIFACTS = Path('/artifacts')\nGO_NAMES = (\n    'TestPostgresCatalogLifecycleColdHTTPRaceOneJob',\n    'TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP',\n    'TestPostgresCatalogLifecycleAtomicPublication',\n    'TestPostgresCatalogLifecycleWarmReadsNoExternalCalls',\n)\nREQUIRED = os.getenv('AUTODATA_CATALOG_INTEGRATION_REQUIRED') == '1'\nif REQUIRED and os.getenv('AUTODATA_LIFECYCLE_TEST') != '1':\n    raise RuntimeError('required acceptance needs explicit lifecycle fixture flag')\nif not REQUIRED:\n    pytestmark = pytest.mark.skip(reason='explicit required fixture acceptance only')\n"
        },
        {
          "claim": "Full row-export tables are additional support",
          "end_line": 49,
          "sha256": "649be602dde072b660ad03953b714384d5fb26727fb6dee3d02bb88ff9857d73",
          "start_line": 43,
          "text": "TABLES = ('schema_migrations', 'catalog_articles', 'canonical_articles',\n          'canonical_article_source_revisions', 'canonical_article_source_observations',\n          'canonical_article_revisions', 'canonical_article_reviews',\n          'canonical_article_rewrite_attempts', 'source_fetch_jobs', 'publication_events',\n          'source_snapshots', 'catalog_article_provider_scopes', 'catalog_article_index_pages',\n          'canonical_article_aliases', 'customer_accounts', 'auth_sessions',\n          'workshop_orders', 'workshop_checkout_requests')\n"
        },
        {
          "claim": "Dynamic JSONB SQL exports and migration receipts",
          "end_line": 180,
          "sha256": "6f11ba18bc96e9b3d24e98c9ec56015389a735a0693c7de1217d559631f0129c",
          "start_line": 133,
          "text": "def immutable_rows(repo):\n    with repo.connect() as conn:\n        return {table: [row['record'] for row in conn.execute(\n            'SELECT to_jsonb(t) AS record FROM ' + table + ' t ORDER BY to_jsonb(t)::text')]\n                for table in TABLES}\n\n\ndef rows_hash(rows):\n    return digest(json.dumps(rows, default=str, sort_keys=True).encode())\n\n\ndef migration_snapshot(repo, env):\n    rows = immutable_rows(repo)\n    dump = bounded(['pg_dump', '--schema-only', '--no-owner', '--no-privileges'], env=env)\n    assert dump.returncode == 0, dump.stderr.decode()\n    normalized = b'\\n'.join(line for line in dump.stdout.splitlines()\n                             if not line.startswith((b'\\\\restrict ', b'\\\\unrestrict ')))\n    return {'ledger': rows['schema_migrations'], 'rows': rows,\n            'ledger_sha256': rows_hash(rows['schema_migrations']),\n            'schema_sha256': digest(normalized), 'data_sha256': rows_hash(rows)}, normalized\n\n\ndef run_migrations(repo, directory, phase, manifest, before=None):\n    env = migration_env(repo)\n    command = ['sh', str(ROOT / 'scripts/dev/migrate_sql.sh')]\n    process = bounded(command, env=env, timeout=90)\n    (directory / f'migration-{phase}.stdout').write_bytes(process.stdout)\n    (directory / f'migration-{phase}.stderr').write_bytes(process.stderr)\n    applied = re.findall(r'^AUTODATA_APPLIED\\s+(\\S+)', process.stdout.decode(), re.M)\n    skipped = re.findall(r'^AUTODATA_SKIPPED\\s+(\\S+)', process.stdout.decode(), re.M)\n    result = {'exit_code': process.returncode, 'timed_out': False,\n              'applied': applied, 'skipped': skipped}\n    write_json(directory / f'migration-{phase}.json', result)\n    assert process.returncode == 0, process.stdout.decode() + process.stderr.decode()\n    if phase == 'fresh':\n        assert applied == manifest and not skipped\n    else:\n        assert skipped == manifest and not applied\n    after, schema = migration_snapshot(repo, env)\n    assert sorted(row['version'] for row in after['ledger']) == [name[:-4] for name in manifest]\n    (directory / f'migration-{phase}.schema.sql').write_bytes(schema)\n    write_json(directory / f'migration-{phase}.rows.json', after['rows'])\n    for kind in ('ledger', 'schema', 'data'):\n        result[kind + '_after_sha256'] = after[kind + '_sha256']\n        if before is not None:\n            result[kind + '_before_sha256'] = before[kind + '_sha256']\n            assert before[kind + '_sha256'] == after[kind + '_sha256'], phase + ':' + kind\n    return result, after\n"
        },
        {
          "claim": "Exact package; no fail/skip; one root run/pass and final package pass",
          "end_line": 469,
          "sha256": "397e102f30593949148198f0d259b0283607e6f18d2cc79a63f24fd358a5581d",
          "start_line": 460,
          "text": "def validate_go_events(path, name):\n    events = [json.loads(line) for line in path.read_text().splitlines()]\n    assert events\n    package = 'github.com/lucronn/autodata/apps/api-go'\n    assert all(event['Package'] == package for event in events)\n    assert not any(event['Action'] in ('skip', 'fail') for event in events)\n    runs = [event.get('Test') for event in events if event['Action'] == 'run']\n    passes = [event.get('Test') for event in events if event['Action'] == 'pass' and 'Test' in event]\n    assert runs == passes == [name]\n    assert events[-1]['Action'] == 'pass' and 'Test' not in events[-1]\n"
        },
        {
          "claim": "Eight root/provider parameter pairs and producer identity",
          "end_line": 481,
          "sha256": "7ec45b55589e3efaafb06c16096acd3e870bd659d8ce72bc2d27ec106fbe470a",
          "start_line": 472,
          "text": "@pytest.mark.parametrize('go_name,provider', [(name, provider) for name in GO_NAMES for provider in ('bankone', 'banktwo')], ids=[name + '-' + provider for name in GO_NAMES for provider in ('bankone', 'banktwo')])\ndef test_required_go_catalog_lifecycle(go_name, provider, fresh_database, monkeypatch):\n    assert REQUIRED and os.environ['AUTODATA_LIFECYCLE_TEST'] == '1'\n    provenance = check_inputs('before')\n    directory = ARTIFACTS / 'r3' / provider / go_name\n    directory.mkdir(parents=True, exist_ok=False)\n    started = now()\n    result = {'schema_version': 1, 'provider': provider, 'go_test_name': go_name,\n              **provenance, 'started_at': started, 'go_exit_code': None, 'timed_out': False,\n              'phase_snapshots': {}, 'assertion_results': {}}\n"
        },
        {
          "claim": "Per-slot environment and Go argv, 90s Go/120s wait source deadlines",
          "end_line": 537,
          "sha256": "548166501781286b8ecae0856d74edb69b9a71f4deeedb185be4ffd4f7f64550",
          "start_line": 511,
          "text": "            go_env = {key: os.environ[key] for key in ('PATH', 'HOME', 'GOTOOLCHAIN', 'GOPROXY', 'GOFLAGS', 'CGO_ENABLED', 'GOMODCACHE', 'GOCACHE', 'GOTMPDIR') if key in os.environ}\n            assert go_env['GOTOOLCHAIN'] == 'local' and go_env['GOPROXY'] == 'off'\n            Path(go_env['GOCACHE']).mkdir(parents=True, exist_ok=True)\n            Path(go_env['GOTMPDIR']).mkdir(parents=True, exist_ok=True)\n            go_env.update(AUTODATA_CATALOG_INTEGRATION_REQUIRED='1', AUTODATA_LIFECYCLE_TEST='1',\n                          AUTODATA_CATALOG_TEST_DSN=f'postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{repo.database_name}?sslmode=disable',\n                          AUTODATA_CATALOG_TEST_ENSURE_URL=ensure_url,\n                          AUTODATA_CATALOG_TEST_CONTROL_URL=control_url,\n                          AUTODATA_CATALOG_TEST_CONTROL_TOKEN=bridge.token,\n                          AUTODATA_CATALOG_TEST_VEHICLE_ID=str(runtime.vehicle),\n                          AUTODATA_CATALOG_TEST_ARTICLE_ID=str(runtime.article_id),\n                          AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID=str(runtime.articles['banktwo' if provider == 'bankone' else 'bankone']),\n                          AUTODATA_CATALOG_TEST_PROVIDER=provider,\n                          AUTODATA_CATALOG_TEST_CANDIDATE_SHA=provenance['candidate_sha'],\n                          AUTODATA_CATALOG_TEST_CASE_DIR=str(directory))\n            argv = ['go', 'test', '-json', '-count=1', '-timeout=90s', '-run', '^' + go_name + '$', '.']\n            write_json(directory / 'go-command.json', {'argv': argv, 'cwd': str(ROOT / 'apps/api-go')})\n            with (directory / 'go-events.jsonl').open('wb') as stdout, (directory / 'go-stderr.log').open('wb') as stderr:\n                process = subprocess.Popen(argv, cwd=ROOT / 'apps/api-go', env=go_env, stdout=stdout, stderr=stderr)\n                try:\n                    result['go_exit_code'] = process.wait(timeout=120)\n                except subprocess.TimeoutExpired:\n                    result['timed_out'] = True\n                    process.kill()\n                    process.wait(timeout=3)\n                    result['go_exit_code'] = process.returncode\n                    raise\n"
        },
        {
          "claim": "Measurement, lifecycle evidence, migrations, worker outcomes and result are additional support",
          "end_line": 580,
          "sha256": "506445e3fc722f90194dabbd565c026165d29461e9b5aab7f08d08edbf32edc4",
          "start_line": 538,
          "text": "            measurement = json.loads((directory / 'go-measurement.json').read_bytes())\n            result['phase_snapshots'] = measurement['phase_snapshots']\n            result['assertion_results'] = measurement['assertion_results']\n            assert result['go_exit_code'] == 0, (directory / 'go-events.jsonl').read_text() + (directory / 'go-stderr.log').read_text()\n            validate_go_events(directory / 'go-events.jsonl', go_name)\n            final = bridge.snapshot()\n            assert not final['proxy']['errors'] and final['ensure']['active'] == 0\n            runtime.record_evidence(go_name + '-' + provider)\n            worker_exits = bridge.stop()\n            before, schema = migration_snapshot(repo, migration_env(repo))\n            (directory / 'populated-before.schema.sql').write_bytes(schema)\n            write_json(directory / 'populated-before.rows.json', before['rows'])\n            migrations['populated_replay'], _ = run_migrations(repo, directory, 'replay-populated', manifest, before)\n            result['assertion_results'].update(fresh_manifest_applied_001_040=True,\n                                             empty_replay_noop_001_040=True,\n                                             populated_replay_noop_001_040=True)\n            versions = {}\n            for tool, argv in {'go': ['go', 'version'], 'python': ['python', '--version'], 'psql': ['psql', '--version'], 'pg_dump': ['pg_dump', '--version']}.items():\n                version = bounded(argv)\n                assert version.returncode == 0\n                versions[tool] = version.stdout.decode().strip()\n            measured = {'schema_version': 1, 'provider': provider, 'go_test_name': go_name,\n                        'fixture_database': repo.database_name, 'candidate_sha': provenance['candidate_sha'],\n                        'snapshots': result['phase_snapshots'], 'migrations': migrations,\n                        'service_probes': service_probes, 'worker_exits': worker_exits,\n                        'versions': versions, **{key: value for key, value in measurement.items() if key not in ('phase_snapshots', 'assertion_results')}}\n            write_json(directory / 'measured-runtime.json', measured)\n            runtime.close()\n            runtime = None\n    finally:\n        if bridge is not None:\n            bridge.release_model.set()\n            if runtime is not None and runtime.barrier:\n                runtime.release('inside_publication')\n        if runtime is not None:\n            try:\n                bridge.stop()\n            finally:\n                runtime.close()\n        result['finished_at'] = now()\n        result['artifact_sha256'] = {path.name: digest(path.read_bytes()) for path in sorted(directory.iterdir()) if path.is_file() and path.name != 'result.json'}\n        write_json(directory / 'result.json', result)\n        check_inputs('after')\n"
        }
      ],
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "5b16ff5b5428547fcdeb09fb63c36c94a406ff6c",
      "path": "workers/ingestion-python/tests/test_catalog_api_integration.py",
      "sha256": "88e6c1fd339da60614056abd7689b6a7fcd1d16bc1e239cec888b06bb6a61974"
    },
    {
      "bytes": 40868,
      "citations": [
        {
          "claim": "Setup flags, fixture database, provider, candidate and loopback controls",
          "end_line": 74,
          "sha256": "84fcb5690d239e2af86e74ea61ec4e7d8fc5f564ce31c1ea855503710b02e02e",
          "start_line": 36,
          "text": "func r3Setup(t *testing.T) *r3Fixture {\n\tt.Helper()\n\tif os.Getenv(\"AUTODATA_CATALOG_INTEGRATION_REQUIRED\") != \"1\" {\n\t\tt.Skip(\"required fixture acceptance is a separate explicit run\")\n\t}\n\tif os.Getenv(\"AUTODATA_LIFECYCLE_TEST\") != \"1\" {\n\t\tt.Fatal(\"lifecycle fixture flag required\")\n\t}\n\tdsn := os.Getenv(\"AUTODATA_CATALOG_TEST_DSN\")\n\tu, err := url.Parse(dsn)\n\tif err != nil || u.Scheme != \"postgres\" || u.Host != \"postgres:5432\" || u.User == nil || u.User.Username() != \"lifecycle_test\" || u.Query().Get(\"sslmode\") != \"disable\" || len(u.Query()) != 1 || !regexp.MustCompile(`^/lifecycle_test_[a-f0-9]{32}$`).MatchString(u.Path) {\n\t\tt.Fatal(\"invalid isolated database target\")\n\t}\n\tpassword, ok := u.User.Password()\n\tif !ok || password != \"lifecycle_test_only\" {\n\t\tt.Fatal(\"invalid fixture credential\")\n\t}\n\tf := &r3Fixture{t: t, vehicle: os.Getenv(\"AUTODATA_CATALOG_TEST_VEHICLE_ID\"), article: os.Getenv(\"AUTODATA_CATALOG_TEST_ARTICLE_ID\"), other: os.Getenv(\"AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID\"), provider: os.Getenv(\"AUTODATA_CATALOG_TEST_PROVIDER\"), control: os.Getenv(\"AUTODATA_CATALOG_TEST_CONTROL_URL\"), token: os.Getenv(\"AUTODATA_CATALOG_TEST_CONTROL_TOKEN\"), phases: map[string]any{}, assertions: map[string]bool{}, extra: map[string]any{}}\n\tuuidPattern := regexp.MustCompile(`^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$`)\n\tfor _, id := range []string{f.vehicle, f.article, f.other} {\n\t\tif !uuidPattern.MatchString(id) {\n\t\t\tt.Fatal(\"fixture UUID required\")\n\t\t}\n\t}\n\tif f.provider != \"bankone\" && f.provider != \"banktwo\" {\n\t\tt.Fatal(\"fixture provider required\")\n\t}\n\tif f.token == \"\" {\n\t\tt.Fatal(\"control token required\")\n\t}\n\tif !regexp.MustCompile(`^[a-f0-9]{40}$`).MatchString(os.Getenv(\"AUTODATA_CATALOG_TEST_CANDIDATE_SHA\")) {\n\t\tt.Fatal(\"candidate SHA required\")\n\t}\n\tensureURL := os.Getenv(\"AUTODATA_CATALOG_TEST_ENSURE_URL\")\n\tfor _, raw := range []string{ensureURL, f.control} {\n\t\tv, e := url.Parse(raw)\n\t\tif e != nil || v.Scheme != \"http\" || v.Hostname() != \"127.0.0.1\" || v.Port() == \"\" || v.User != nil || v.RawQuery != \"\" || v.Fragment != \"\" || v.Path != \"\" {\n\t\t\tt.Fatal(\"only explicit loopback fixture URLs allowed\")\n\t\t}\n"
        },
        {
          "claim": "Measurement payload has phase/views/assertions but no mandatory provider identity",
          "end_line": 119,
          "sha256": "74d465b368c91c923666cbc58976046d8d7f7b436d48d2bdfa99039369a8f317",
          "start_line": 97,
          "text": "\tt.Cleanup(func() {\n\t\tviews := f.views\n\t\tif t.Name() == \"TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP\" {\n\t\t\tviews = nil\n\t\t\tfor _, a := range f.views {\n\t\t\t\tif r3Origin(a, \"source\") {\n\t\t\t\t\tviews = append(views, a)\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t\tobservations := []map[string]any{}\n\t\tfor _, a := range views {\n\t\t\tobservations = append(observations, r3EvidenceArticle(a))\n\t\t}\n\t\tpayload := map[string]any{\"phase_snapshots\": f.phases, \"observed_views\": observations, \"assertion_results\": f.assertions}\n\t\tfor k, v := range f.extra {\n\t\t\tpayload[k] = v\n\t\t}\n\t\traw, _ := json.MarshalIndent(payload, \"\", \"  \")\n\t\tif err := os.WriteFile(filepath.Join(os.Getenv(\"AUTODATA_CATALOG_TEST_CASE_DIR\"), \"go-measurement.json\"), raw, 0644); err != nil {\n\t\t\tt.Error(err)\n\t\t}\n\t})\n"
        },
        {
          "claim": "Nested document/body/steps/images projection",
          "end_line": 233,
          "sha256": "9418972abebdd25ea2436ec76cc68ab13b67e3454d2252b0ab2dae974a5f42a0",
          "start_line": 216,
          "text": "func r3EvidenceArticle(a CatalogArticle) map[string]any {\n\traw, _ := json.Marshal(a)\n\tvar evidence map[string]any\n\tjson.Unmarshal(raw, &evidence)\n\t// Evidence retains optional public fields explicitly and separately records\n\t// the durable job identity for comparison with PostgreSQL snapshots.\n\tfor key, value := range r3Projection(a) {\n\t\tevidence[key] = value\n\t}\n\tif a.Processing != nil {\n\t\tevidence[\"job_id\"] = a.Processing.JobID\n\t\tevidence[\"processing_state\"] = a.Processing.State\n\t}\n\treturn evidence\n}\nfunc r3Projection(a CatalogArticle) map[string]any {\n\treturn map[string]any{\"document\": a.Document, \"body\": a.Body, \"steps\": a.Steps, \"images\": a.Images}\n}\n"
        },
        {
          "claim": "Index readiness stays within one existing root",
          "end_line": 289,
          "sha256": "5977b53cef149ba6bac90b87dd9b9f5f47cc10b0d55fea0d985ed6a157ad1e2a",
          "start_line": 287,
          "text": "// verifyIndexReadiness runs inside the existing cold root: the fixture bridge\n// deliberately accepts exactly one Go root event stream per provider/case.\nfunc (f *r3Fixture) verifyIndexReadiness() {\n"
        },
        {
          "claim": "Cold root declaration",
          "end_line": 404,
          "sha256": "46036333cef07465348248d31900f2f6c208d73dc901790d771e69def5d2fe34",
          "start_line": 403,
          "text": "func TestPostgresCatalogLifecycleColdHTTPRaceOneJob(t *testing.T) {\n\tf := r3Setup(t)\n"
        },
        {
          "claim": "Source-readable root declaration",
          "end_line": 479,
          "sha256": "95ae16d82d4f3dc33bb916c4274072581211a73495524fc8828fe6690416ba0e",
          "start_line": 478,
          "text": "func TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP(t *testing.T) {\n\tf := r3Setup(t)\n"
        },
        {
          "claim": "Atomic publication root declaration",
          "end_line": 531,
          "sha256": "ac2dbc3604f037c5eadb89144436e3abe7fe891f11a57e94157834ace82eff38",
          "start_line": 530,
          "text": "func TestPostgresCatalogLifecycleAtomicPublication(t *testing.T) {\n\tf := r3Setup(t)\n"
        },
        {
          "claim": "Warm-read root declaration",
          "end_line": 589,
          "sha256": "81e8ed8123e69e3097c02768d74b02173b459d8ea906c371a6b3f870f6aef609",
          "start_line": 588,
          "text": "func TestPostgresCatalogLifecycleWarmReadsNoExternalCalls(t *testing.T) {\n\tf := r3Setup(t)\n"
        }
      ],
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "b0db236512e08851bb87c3e33cc76622e10a8378",
      "path": "apps/api-go/postgres_catalog_lifecycle_test.go",
      "sha256": "a8ec30ca66629cc0317c511450e5660911a0d90d79daa52b1816bbd781bc7943"
    },
    {
      "bytes": 3986,
      "citations": [
        {
          "claim": "Exact package module",
          "end_line": 1,
          "sha256": "6612ed14729761e0b34ecd43385d0c46fc54d4059edaf447204e2c063f7aaa41",
          "start_line": 1,
          "text": "module github.com/lucronn/autodata/apps/api-go\n"
        }
      ],
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "16982a9310be7447103e2bfacecf9f7cb764704e",
      "path": "apps/api-go/go.mod",
      "sha256": "3306c3736c51a3c08a4ed30613a9f0ba4db7f5094d0215ebdf54545873012923"
    },
    {
      "bytes": 19309,
      "citations": [],
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "ac52c479e5e4a7f625cddd409d8d61573c271765",
      "path": "workers/ingestion-python/tests/lifecycle_support.py",
      "sha256": "746eba57bfffb760e2f779d0d0494125f8b559b07de5ff6ec11099d517bf76dc"
    },
    {
      "bytes": 1662,
      "citations": [],
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "75bdbb276a5af737e9ab9651bee0d9e923320650",
      "path": "db/migrations/035_ordered_article_document.sql",
      "sha256": "fe8d1d8a69b4f2e84e9ea0770044f45ff49d2a4b3d01a09db85c49fbc5e1d2ce"
    },
    {
      "bytes": 12905,
      "citations": [],
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "649d50b212980d7eede2ca0423e2b68f4e298ae7",
      "path": "db/migrations/037_article_source_lifecycle.sql",
      "sha256": "3a1df6fb260a3afd979cdd65dcebed89f51a7e8b2098d4190b03fdccdbc7ca07"
    },
    {
      "bytes": 12863,
      "citations": [],
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "449056c1478fca769c53abaf4a51093b8f350895",
      "path": "db/migrations/038_article_transform_publication.sql",
      "sha256": "343df92024c5e394c1878eb598bfd8e83c96998e19bf03f9523fff35ac62f2ff"
    },
    {
      "bytes": 122350,
      "citations": [],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "24ac3e9264b85eb914daa7805d183e15f58d374a",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.json",
      "sha256": "c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39"
    },
    {
      "bytes": 10852,
      "citations": [],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "97a3ee48e443547f538e369ebd4557644e9fec3c",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.md",
      "sha256": "55fc12a771576778fb652ea8fcc3e8b81492ff3abc6fef0f00cc7fa3b015037a"
    },
    {
      "bytes": 33663,
      "citations": [],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "c0948a5b604b9ae5f0ce31ab2e7864cbc9b8d527",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-runner.md",
      "sha256": "24d209a60ae2dcda461d1a65932c2dd37d6894ed7a9c3920f989fe8ff0b20ba3"
    },
    {
      "bytes": 82081,
      "citations": [],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "4a29e0915c677a2f07e3ca6b0ab9109e888651d1",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-stage-b1-identity.md",
      "sha256": "285e5abfe824b4b9490af8e4b2fa3655f53ea34d8afc631e69a88feb909d242a"
    },
    {
      "bytes": 22290,
      "citations": [
        {
          "claim": "Side-effect-free standard-library parser dependency and frozen bounds/codes",
          "end_line": 41,
          "sha256": "30e8077f7787a1af9657b9ef297ccbbf187b14ad7fb16cef62b3d57a524f198b",
          "start_line": 1,
          "text": "\"\"\"Bounded synthetic identity translation. No execution or artifact I/O authority.\"\"\"\nfrom dataclasses import dataclass\nimport hashlib\nimport json\nimport math\nimport re\n\nCANDIDATE = '4d82e413e04fb2401ac7bc28dc828375ac662180'\nINVENTORY = 'c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39'\nPACKAGE = 'github.com/lucronn/autodata/apps/api-go'\nROOT = 'TestPostgresAuthSessionsIntegration'\nIDENTITY_IDS = tuple(ROOT + '/' + name for name in (\n    'ConcurrentCustomerProvisionAndRotation', 'SharedSessionRevocation',\n    'ExpiryAndPersistedSecrecy', 'FirebaseExchangeAndUserRevocation',\n    'FirebaseStartupRequiresMigratedPostgres'))\nRAW_REFS = ('r5-access-go-events.jsonl', 'r5-access-go-stderr.log')\nAUTHORITY = tuple((name, False) for name in (\n    'fixture_verified', 'product_candidate_verified', 'staging_verified',\n    'deployment_authorized', 'cutover_verified', 'implementation_authorized',\n    'runtime_execution_authorized', 'profile_promotion_authorized', 'merge_authorized'))\nEVENTS_LIMIT = 67108864\nSTDERR_LIMIT = 1048576\nPARSER_CODES = (\n    'input_type', 'events_size', 'events_count', 'line_size', 'line_delimiter',\n    'json_invalid', 'json_duplicate_key', 'json_nonfinite', 'json_depth',\n    'json_string', 'event_keys', 'event_type', 'unsupported_go_action')\nSEMANTIC_CODES = (\n    'package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',\n    *(f'child_lifecycle:{i}' for i in range(5)), 'root_failed', 'root_skipped',\n    'package_failed', 'package_skipped', *(f'child_failed:{i}' for i in range(5)),\n    *(f'child_skipped:{i}' for i in range(5)), 'simulated_nonzero',\n    'simulated_timeout', 'simulated_interrupted', 'ownership_lost', 'cleanup_incomplete')\n\n\nclass AdapterError(ValueError):\n    \"\"\"A stable code only; never embeds source strings or decoder exceptions.\"\"\"\n\n\n@dataclass(frozen=True)\nclass IdentityContext:\n    candidate_sha: str\n"
        },
        {
          "claim": "Public bytes-only parser grammar",
          "end_line": 241,
          "sha256": "e42cabfc5aef4ad9db618ffb11b98d716866a5afbb39785c5e53238a9e690f41",
          "start_line": 192,
          "text": "def parse_identity_events(raw: bytes) -> tuple[GoEvent, ...]:\n    _outer(raw)\n    _require(bool(raw), 'events_count')\n    body = raw[:-1] if raw.endswith(b'\\n') else raw\n    lines = body.split(b'\\n')\n    _require(len(lines) <= 65536, 'events_count')\n    events = []\n    for line in lines:\n        _require(bool(line) and b'\\r' not in line, 'line_delimiter')\n        _require(len(line) <= 1048576, 'line_size')\n        try:\n            text = line.decode('utf-8')\n            _depth(text)\n            row = json.loads(text, object_pairs_hook=_pairs, parse_constant=_nonfinite)\n        except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:\n            if type(exc) is AdapterError:\n                raise\n            raise AdapterError('json_invalid') from None\n        _strings(row)\n        _require(type(row) is dict, 'event_type')\n        _require({'Time', 'Action', 'Package'} <= row.keys()\n                 and row.keys() <= {'Time', 'Action', 'Package', 'Test', 'Elapsed', 'Output', 'FailedBuild'},\n                 'event_keys')\n        _require(all(v is not None for v in row.values()), 'event_type')\n        _require(_text(row['Time'], 128) and _text(row['Package'], 256)\n                 and type(row['Action']) is str, 'event_type')\n        action = row['Action']\n        _require(action in ('start', 'run', 'output', 'pass', 'fail', 'skip'), 'unsupported_go_action')\n        test = row.get('Test')\n        elapsed = row.get('Elapsed')\n        output = row.get('Output')\n        failed = row.get('FailedBuild')\n        _require('Test' not in row or _text(test, 256), 'event_type')\n        _require('Elapsed' not in row or (type(elapsed) in (int, float)\n                 and 0 <= elapsed <= 86400 and math.isfinite(elapsed)), 'event_type')\n        _require(('Output' not in row or (action == 'output' and type(output) is str))\n                 and (action != 'output' or 'Output' in row), 'event_type')\n        _require('FailedBuild' not in row or (action == 'fail' and test is None\n                 and _text(failed, 1024)), 'event_type')\n        _require((action != 'start' or test is None) and (action != 'run' or test is not None), 'event_type')\n        events.append(GoEvent(row['Time'], action, row['Package'], test, elapsed, output, failed))\n    return tuple(events)\n\n\ndef _receipt_failures(receipt):\n    return tuple(code for flag, code in (\n        (receipt.exit_code is not None and receipt.exit_code != 0, 'simulated_nonzero'),\n        (receipt.timed_out, 'simulated_timeout'), (receipt.interrupted, 'simulated_interrupted'),\n        (receipt.ownership_lost, 'ownership_lost'), (not receipt.cleanup_complete, 'cleanup_incomplete')) if flag)\n\n"
        }
      ],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "8c7fa87bab906955c145d7cc965be641aea48c5f",
      "path": "scripts/dev/workshop_final180_identity_adapter.py",
      "sha256": "0474a85c33d4f2722ad01d6e55e69a8080dc0f1983c856ca7caa1b94510a767d"
    },
    {
      "bytes": 29838,
      "citations": [],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "7391263cb874e2505f4f110df6343c8b466fc692",
      "path": "scripts/dev/test_workshop_final180_identity_adapter.py",
      "sha256": "a3f3017b1d7a85da9ae4d1883758f2494d722fb321d45c1ff758994ab6d2653c"
    },
    {
      "bytes": 47124,
      "citations": [],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "ca48cd988c5579a7d385dc1844b84306eae0861e",
      "path": "scripts/dev/workshop_final180_runner.py",
      "sha256": "693a408a73f3ccd37bf945bfc94d427f742878580932dab382ea9a244a141c91"
    },
    {
      "bytes": 13237,
      "citations": [],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "094cceff7b0a6a2259cf3354b61b31af5bab60c8",
      "path": "docs/verification/workshop-final180-runbook.md",
      "sha256": "3658ca8a8571454c6c027b6e619dbb391578df9159b2a6ca7e4c42be4de227d5"
    },
    {
      "bytes": 5659,
      "citations": [],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "41076af1db25f0cff8ca41d0203c050af9b772df",
      "path": "docs/agents/pre-implementation-gate.md",
      "sha256": "fa6e9c95c2674164c90d78e046a0427f6b406c313fb82ff627a2a2facb560ad0"
    },
    {
      "bytes": 8645,
      "citations": [],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "595ccf5f84c8e5ff7aa29dcc2a9284b8b7421f39",
      "path": "scripts/autonomy/pre_implementation.py",
      "sha256": "af5cf8d987dea0d63f98865a6b6bcf1d730f044a9e6dc14509a91aeb0505f1ec"
    },
    {
      "bytes": 9719,
      "citations": [],
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "3120ae8753aedb4cb5ff0ac3dd9c8c662675e2f4",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-b1-identity.json",
      "sha256": "7f8f437f7b536c327ad7135ebc8aab64ba8ff263363358f58bd19739df81a573"
    },
    {
      "bytes": 5060,
      "citations": [],
      "commit": "006fab0d1380c2506330bbc0b48397a32294b6cc",
      "git_blob": "e52a6813c24dbf71ebcf9ebcb209d447cac48e1c",
      "path": "docs/agents/records/2026-11-04-workshop-final180-stage-b1-identity.json",
      "sha256": "8b518c6c467906768f3b00cf83d78fac8b64ad9469f5182c86a198286b6f29a0"
    }
  ]
}
```

Additional current planning-parent pins (the assembler pin describes the append-only baseline, not the resulting file):

```json
[
  {
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "path": "scripts/dev/test_workshop_final180_runner.py",
    "git_blob": "2cfa9dc8ea116b7aa5b0c541529712b4b5d24be3",
    "bytes": 32981,
    "sha256": "2f92614e937b5b3d6a17da7ab9f4b758b34a4a542fbe5564b29ddefd4f7b148a"
  },
  {
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "path": ".autodata-autonomy-policy.json",
    "git_blob": "be4d8088b3fd28c84c101a723ecc7c26768de9e7",
    "bytes": 2201,
    "sha256": "798e91b9854098a706ea4ab66a414492c044059a1c98edb9d2f1d003e3baad98"
  },
  {
    "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
    "path": "docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md",
    "git_blob": "1eb7c096b9f579513855dc7f7348272106e8f3ee",
    "bytes": 74753,
    "sha256": "0865f92942ca77f37ba5c423ea3baf182b767acaf1efe7cdf280fa39326a50b3"
  }
]
```
