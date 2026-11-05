# Workshop final180 Stage C commerce14 restricted synthetic adapter — canonical specification

Status: Issue186/Project8 planning `synchronized` with live readback at https://github.com/lucronn/autodata/issues/186#issuecomment-6638920703. Coordinator preserved the Issue body, all164 prior comments (now165), archived the prior Project Source verbatim and preserved unrelated Project fields; Project remains In Progress. Independent five-file pre-sync draft review PASS/no findings is coordinator-reported. Committed-checkpoint standalone/nested preflight, independent exact-checkpoint review and explicit coordinator dispatch remain required. No implementation or runtime authority follows. Coordinator also reports independent exact external DRAFT/SPEC review PASS for restricted synthetic scope.

Planning parent / independently reviewed CI integration code head: `fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc` ([PR232](https://github.com/lucronn/autodata/pull/232)); CI was pending at planning dispatch and is not claimed passed. Application candidate remains `4d82e413e04fb2401ac7bc28dc828375ac662180`. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Plan `docs/superpowers/plans/2026-11-04-workshop-final180-stage-c-commerce.md` and standalone/nested record paths `docs/agents/records/2026-11-04-workshop-final180-stage-c-commerce.json` / `docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-c-commerce.json` are the gate index.

This specification promotes the exact technical body of externally reviewed `SPEC.draft.md` SHA256 `ad1c3cfa26315babfbc0820b2bf0b06463a204eb30e18516bc876888d4a12d41`. Its historical descriptions of external status or a future stable parent remain provenance, superseded for this repository proposal by this paragraph and section 11. The technical signatures, grammar, mappings, status rules and serializer remain unchanged.

## 1. Purpose, identity, source truth and chosen restrictions

Implement a future standard-library, bytes-only library that translates a restricted synthetic JUnit profile into exactly fourteen commerce rows and optionally evaluates the first row's Go support stream. Every result is synthetic and earns exact integer0 accepted-case credit, with profiles disabled, enabled tiers empty, runtime_lock/run_record null and all nine authority flags false. No actual commerce assertion or financial acceptance is established.

Application candidate is literal `4d82e413e04fb2401ac7bc28dc828375ac662180`. Inventory digest is literal `c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39`. Reviewed B1 dependency head is literal `54a7ca32eab80654310d862f0ac6957375d16e8b`. Source pins and literal support/case names are embedded below, not dynamically discovered by the adapter. Active B2 source read `7ea63d77acb5a0972dd86b2b138017fe9b6f288b` and B2 gate `3cd99224eae7012f8c6cc0bfc15a1053a8e7762f` are historical inspection identities, not dependencies or review claims. No B2 code is imported.

Source-established facts: the collector's exact fourteen commerce names/classname, global no-failure/error/skipped predicate, first-case-only Go support, nominal53 supporting pytest names, shared pytest process, and source export shape. Source collector checks exact commerce membership but does not require53 support identities. The synthetic flat XML grammar, exact67-name requirement, stronger Go lifecycle, optional-Go absence result, bounded types, status/reason vocabulary, receipt merging and serializer below are explicit proposed design restrictions. They are not observed pytest/plugin/Go compatibility. Support classnames remain opaque because exact installed module classname emission is unobserved.

The actual raw inventory also names workshop-commerce.json, workshop-commerce-migration-rows.json and runner before/after records. This adapter accepts none of those artifacts and claims none were validated. Final safe exports omit signed webhook bodies/signatures, portions of expanded intent financial facts, HTTP outcomes and intermediate race/order traces; their hashes/final states cannot independently prove all14 assertions. Full financial/raw acceptance, applied schema, actual SDK/JUnit emission, authenticated source/process/artifact identity, runtime locks and enabled profiles remain blocked successors.

## 2. Import surface, execution boundaries and public interfaces

New implementation module has no CLI, entrypoint, module-level I/O, callbacks, mutable runtime options, timer/scheduler/replay, filesystem, environment, clock, process, network, container, browser or SDK access. Permitted imports are `from dataclasses import dataclass`, `hashlib`, `json`, `re`, `from xml.parsers import expat`, and exactly the public B1 symbols `parse_identity_events`, `GoEvent`, `AdapterError`, `SimulatedExit` from `scripts.dev.workshop_final180_identity_adapter`. No private B1 helper, identity translator/replay, Stage A runner, B2 module, producer, collector, test, SQL or application import is permitted. B1 parser/module/test and Stage A runner/test remain unchanged at embedded pins. B1's180s fake scheduler is not a commerce deadline. Source900s pytest/120s Go waits and3s cleanup waits are context only; this library does not enforce elapsed runtime.

All dataclasses below are frozen, non-slotted ordinary dataclasses. All collections at the interface are exact tuples; no subclass/coercion is admitted. Field and function names/signatures are exact. Public symbols from B1 retain their existing definitions; AdapterError is the sole stable-code exception. It contains only the exact error code, never caller/decoder/source text. Parser return strings are decoded XML attribute values, with XML1.0 normalization described below.

```python
@dataclass(frozen=True)
class CommerceContext:
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str

@dataclass(frozen=True)
class CommerceGoSupport:
    events_raw: bytes
    stderr_raw: bytes
    receipt: SimulatedExit

@dataclass(frozen=True)
class CommerceInput:
    junit_raw: bytes
    pytest_stdout_raw: bytes
    pytest_stderr_raw: bytes
    pytest_receipt: SimulatedExit
    go_support: CommerceGoSupport | None

@dataclass(frozen=True)
class JUnitCase:
    classname: str
    name: str
    terminal: str | None

@dataclass(frozen=True)
class CommerceOutcome:
    family: str
    logical_id: str
    status: str
    raw_refs: tuple[str, ...]

@dataclass(frozen=True)
class CommerceDiagnostic:
    contract: str
    observation_kind: str
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str
    junit_sha256: str
    pytest_stdout_sha256: str
    pytest_stderr_sha256: str
    go_support_present: bool
    go_events_sha256: str | None
    go_stderr_sha256: str | None
    pytest_receipt: SimulatedExit
    go_receipt: SimulatedExit | None
    status: str
    observations: tuple[CommerceOutcome, ...]
    reasons: tuple[str, ...]
    accepted_case_credit: int
    profiles_enabled: bool
    enabled_tiers: tuple[str, ...]
    authority: tuple[tuple[str, bool], ...]
    runtime_lock: None
    run_record: None

parse_commerce_junit(raw: bytes) -> tuple[JUnitCase, ...]
parse_commerce_go_events(raw: bytes) -> tuple[GoEvent, ...]
translate_commerce(value: CommerceInput, context: CommerceContext) -> CommerceDiagnostic
serialize_commerce_diagnostic(value: CommerceDiagnostic) -> bytes
```

parse_commerce_junit checks grammar/bounds only, returns all testcase records in document order, and does not admit identities/counts/global cleanliness. parse_commerce_go_events directly delegates to unchanged B1 parse_identity_events with no catch/rewrap. translate_commerce performs identity/lifecycle evaluation and status derivation; caller contract errors raise, while admitted stream parser errors become diagnostics. No parser output includes terminal text, stdout/stderr text or decoded Go Output content in failures. Source manifest SHA is caller-supplied lower64hex context, never proof Stage A inspection occurred.

## 3. Outer validation order, budgets and receipt facts

Validation is strictly ordered and completes before hashing/parsing any bytes. First failing outer condition raises its code and emits no diagnostic:

1. Context is exact CommerceContext; all three fields exact str; candidate/inventory equal literals and source_manifest_sha256 full lower64hex: `context_invalid`.
2. value is exact CommerceInput: `input_invalid`. junit_raw, pytest_stdout_raw, pytest_stderr_raw are exact bytes, checked in that order: `input_type`. go_support is None or exact CommerceGoSupport: `go_support_invalid`. If present its events_raw then stderr_raw must be exact bytes: `input_type`.
3. Check each per-stream size in order: JUnit <=4194304 (`junit_size`); pytest stdout <=1048576 (`pytest_stdout_size`); pytest stderr <=1048576 (`pytest_stderr_size`); if Go present events <=67108864 (`events_size`) then Go stderr <=1048576 (`stderr_size`). Empty streams pass outer sizes; empty JUnit/Go subsequently fail parsers. Empty opaque logs are valid.
4. Validate pytest_receipt, then optional Go receipt: `receipt_invalid`. Exact B1 SimulatedExit; exit_code None or concrete int in[-255,255], never bool; timed_out/interrupted/ownership_lost/cleanup_complete exact bool. None exit allowed only if timed_out or interrupted or ownership_lost or not cleanup_complete. No flag mutual exclusivity is invented; retain all applicable facts.
5. Sum all admitted streams including logs <=74448896 bytes (71MiB) inclusive: `aggregate_size`. Absent Go contributes0. This bound is intentionally equal to the sum of per-stream maxima; an aggregate overflow cannot coexist with passing all per-stream bounds. It remains an explicit invariant, not a separately reachable bound+1 test through valid per-stream inputs.

Only after successful outer validation hash each admitted raw stream with SHA256 including every byte, original XML newline form, and optional final Go LF. Never truncate. Go absence uses go_support_present=False, both Go digests None, go_receipt None; Go presence uses True, two lower64hex digests and the exact validated receipt. No empty bytes are synthesized to stand in for absent support. Always preserve validated receipts unchanged in diagnostics; they are simulated facts only. Opaque logs are hashed, never parsed for status. No artifact path is opened.

Receipt reasons, separately under pytest: and go:, are emitted in fixed order: simulated_nonzero iff exit_code is non-None and !=0; simulated_timeout iff timed_out; simulated_interrupted iff interrupted; ownership_lost iff ownership_lost; cleanup_incomplete iff not cleanup_complete. Clean receipt is exactly exit0 and all adverse flags False with cleanup_complete True.

## 4. Restricted XML grammar and deterministic errors

parse_commerce_junit public outer checks are exact bytes (`input_type`) then <=4194304 (`junit_size`). After these, deterministic admission order is:

1. Decode strict UTF8 once. Failure => `xml_encoding`.
2. Reject a UTF8 BOM prefix, or any raw occurrence of `<?` or `<!` => `xml_forbidden`. Thus declarations, processing instructions, comments, CDATA and every DTD/entity declaration are outside the profile before Expat sees them. This lexical restriction intentionally also rejects these literal markers in otherwise forbidden markup. Do not strip a BOM/declaration.
3. Parse with an XML1.0 Expat parser created by `expat.ParserCreate(encoding="UTF-8", namespace_separator=None)`. Set `buffer_text=False` explicitly. Feed the original admitted raw bytes through exactly one `Parse(raw, True)` call; no incremental feed, caller feed setting or alternate parser configuration is admitted. Character-data checks below operate per decoded code point, so Expat internal callback fragmentation cannot change their result. Explicit handlers reject doctype, entity declarations, external entities, comments, PI, CDATA and XML declaration as `xml_forbidden` as a second line of enforcement. No external resolving callback is installed; handlers never perform I/O. Undefined named entities, duplicate attributes, invalid XML1.0 characters, malformed bytes/markup, mismatched tags, missing/multiple roots and other Expat syntax failures => `xml_invalid`. The five predefined entities and valid numeric character references are admitted through ordinary XML1.0 decoding. Custom declarations cannot reach expansion.
4. On each start callback increment total elements and active depth, then check total<=256 (`xml_nodes`) and depth<=3 (`xml_depth`) in that order, before retaining node/attribute text. Next validate grammar position/tag/attribute-key set (`xml_structure`), then each required attribute's nonempty exact str and UTF8 length<=1024 (`xml_string`), in classname then name order. Expat XML1.0 attribute normalization applies; no additional strip/casefold/Unicode normalization is performed. Attribute order in source is irrelevant.
5. Within each character-data callback, inspect decoded Unicode code points in order, one at a time; never pre-add or prevalidate an entire callback chunk. For each code point first add its UTF8 byte width to the document character-data counter, including whitespace outside/root/between nodes and terminal content. If the new total exceeds1048576, raise `xml_text` immediately at that code point. Second, if inside a terminal, add that code point width to the current terminal counter and raise `xml_text` if it exceeds4096. Third, if outside a terminal and that same code point is not XML whitespace (U+0020, U+0009, U+000A, U+000D), raise `xml_structure` immediately. Therefore a resource violation wins over a whitespace violation on the same code point, but a later resource violation never masks an earlier forbidden character. Counter state continues across callbacks; callback boundaries are never semantic boundaries. Do not scan future characters in a callback after the first violating code point. Original CR normalization by XML1.0 does not alter the original raw hash. Terminal text is opaque and discarded after counting; no text content is status evidence.
6. End callbacks close the current node only; syntax nesting/duplicate-root errors remain xml_invalid. Entire document must be consumed; no successful prefix. Return tuple in document order only if parse completed.

Grammar: one `testsuite` root, no attributes; zero or more `testcase` direct children. Each testcase has exactly `classname` and `name` attributes, no other attributes; both nonempty <=1024 UTF8 bytes. Each has zero or one direct terminal child, exact `failure`, `error` or `skipped`, no terminal attributes or nested elements. Text rules above apply. Terminal presence sets JUnitCase.terminal to its exact tag, absent sets None. Any other element, duplicate terminal child, testsuites envelope, properties, system-out/system-err, suite summary attributes or nested testcase is xml_structure. XML prefixed names and xmlns attributes fail exact tag/key sets as xml_structure; no namespace stripping or inference. A literal colon in an opaque attribute value is permitted. Document order and attribute order never change identity/status results; order remains available only in parser return values.

For competing handler errors, the first decoded source-position violation wins, using start-event checks and per-code-point character checks above. Character-data callback chunking must not change source-position precedence. XML syntax errors detected by the fixed Expat configuration before invoking the next handler win as xml_invalid at that point; handlers must not postpone an already detected violation to inspect later syntax. The UTF8/forbidden-marker prepasses always precede parsing and retain their stated precedence. Any parser error raises only one stable code and discards the whole stream's partial records. Resource/handler checks must happen during streaming admission before growing retained collections; constructing an unrestricted DOM then checking limits is outside this contract.


### 4.1 Mandatory character-data precedence regressions

The following are synthetic negative parser fixtures; spaces mean ASCII U+0020 bytes. They do not involve application execution. They must assert the exact public parse_commerce_junit exception code and translate_commerce's corresponding xml:-prefixed reason, with no successful prefix:

- `b'<testsuite>' + b' ' * 1048574 + b'X' + b' ' * 100 + b'</testsuite>'` => `xml_structure`. At X the character-data total is1048575, within budget, so the invalid nonterminal character is encountered before the later overflow. The old whole-callback addition could incorrectly return xml_text and is forbidden.
- `b'<testsuite>' + b' ' * 1048575 + b'X</testsuite>'` => `xml_structure`. X makes total exactly1048576 and then fails whitespace admission.
- `b'<testsuite>' + b' ' * 1048576 + b'X</testsuite>'` => `xml_text`. X would be both the first nonwhite character and byte1048577; same-code-point resource priority applies.
- `b'<testsuite>' + b' ' * 1048576 + b'</testsuite>'` => successful grammar parse yielding empty tuple. Identity admission later fails case_count/missing_case; it must not retroactively turn the grammar parse into xml_text.
- In an otherwise grammatically valid testcase/terminal, terminal character text of4096 ASCII spaces succeeds grammar, while4097 spaces fails xml_text. The terminal counter is independent of callback boundaries and counts decoded UTF8 bytes, not Python character count.

The future test suite must cover these exact fixtures, repeat each parse with the same bytes and expect the same code/result, and verify the parser's one-final-feed/buffer_text=False configuration. It must also exercise the character-data checker with equivalent segmentations of the first fixture's decoded text: one segment, one code point per segment, and boundaries immediately before/after X and the1048576-byte crossing. These checker-level tests may call an implementation-private character-data state/checker in the test module; no new public parser/stream/feed API is authorized. Every segmentation must identify xml_structure at X and stop without counting the later100 spaces. Such tests verify fragmentation independence directly; merely testing the default Expat callback split is insufficient. No alternative test-only parsing behavior may be substituted for the production code-point checker.

## 5. JUnit semantic admission, literal support identity and global-clean rule

Expected names are the disjoint literal14 commerce plus literal53 support names embedded below. Semantics inspect every parsed testcase even when another is invalid, and retain all applicable summary reasons without caller text:

- xml:case_count iff parsed testcase count !=67.
- xml:unknown_case iff at least one name is outside the67 literal names.
- xml:identity_mismatch iff a commerce name's classname is not exact `tests.test_commerce_postgres`, or a support name's classname equals that reserved string. Unknown names produce unknown_case only, without invented classname expectations.
- xml:duplicate_case iff any known literal name occurs more than once, counting occurrences by name regardless of classname.
- xml:missing_case iff any known literal name occurs zero times, counting by name regardless of classname. A wrong-classname known case is therefore identity_mismatch, not automatically missing_case.
- xml:testcase_failure, xml:testcase_error, xml:testcase_skipped iff any parsed terminal has the respective value, including on a testcase with invalid identity.

For support names every nonempty valid bounded classname except the reserved exact commerce classname is admitted. An unfamiliar `synthetic.anything` support classname alone is a positive case; no installed support-module identity is claimed. Commerce names never receive this opacity exception. No fuzzy/path/suffix matching, parameter ID reconstruction or source importing is admitted. Requiring all53 names is an explicit synthetic restriction stronger than the source collector. All support cases add zero logical IDs.

XML semantic reasons are a set, not early exits, and are serialized in the literal order above. If XML parsing failed, none of these semantic reasons is emitted. Any XML semantic reason makes the shared JUnit baseline nonpass, even if names otherwise match. Clean means no XML parser or semantic reason. Case order, valid opaque support classname replacements and terminal message contents cannot change those reasons.

## 6. Go support grammar, lifecycle and absence

Go support is optional at the interface only. Absence emits sole Go availability reason `go:support_absent`, no Go parser/lifecycle/receipt reason, and makes ID1 unavailable; ID2–ID14 still use the shared baseline. Absence never produces a consistent all14 result. This makes missing support explicit without claiming the source first-case acceptance permits omission.

Present support uses unchanged B1 parser exactly. Inherited public parser codes/order are input_type, events_size, events_count, line_size, line_delimiter, json_invalid, json_duplicate_key, json_nonfinite, json_depth, json_string, event_keys, event_type, unsupported_go_action. Outer admission makes input_type/events_size unreachable as translated parser diagnostics; they remain public delegated-parser exceptions. A translated Go parse reason must be one of the remaining codes prefixed go:.

The inherited grammar is1..65536 nonempty LF-separated JSON object lines; optional one final LF, no blank line/raw CR/CRLF/BOM/invalid UTF8/surrogate strings; <=1MiB per line excluding delimiter, <=64MiB raw; JSON depth<=32; every decoded key/string<=65536 UTF8 bytes; duplicate keys/nonfinite numbers fail. Keys required Time/Action/Package, optional Test/Elapsed/Output/FailedBuild, no unknown/present-null fields. Time nonempty<=128 bytes opaque; Package nonempty<=256; Test present nonempty<=256. Actions exactly start/run/output/pass/fail/skip. start has no Test, run requires Test. Output present iff action output, exact str with empty allowed. FailedBuild only package fail and nonempty<=1024 bytes. Elapsed if present concrete int/float, finite0..86400, never bool. Time/Elapsed/Output cannot authenticate identity/deadline/behavior. The pinned B1 source controls exact first error when inherited conditions compete; do not fork/extend the parser.

On successful parse independently collect all applicable Go semantic reasons in fixed order:

1. go:package_mismatch: any event package differs from exact `github.com/lucronn/autodata/apps/api-go`.
2. go:unknown_test: any present Test differs from exact `TestWorkshopCommercePythonIntegration`; nested children and sibling roots are unknown.
3. go:package_lifecycle: action=start indices are not exactly[0], or package terminal events (Test None and action pass/fail/skip) are not exactly one at final event. A package-level output is allowed only between start and final terminal. The start event has no Test under B1 grammar.
4. go:root_lifecycle: expected-root run is not exactly one; expected-root terminal pass/fail/skip is not exactly one; run is not before terminal; or any root output is outside that open interval; or, when package lifecycle is valid, root run/terminal are not strictly inside package start/final terminal. Package lifecycle invalid does not by itself imply root_lifecycle if the root's own run/output/terminal rules hold.
5. go:root_failed if any expected-root fail.
6. go:root_skipped if any expected-root skip.
7. go:package_failed if any package fail.
8. go:package_skipped if any package skip.

No reason is inferred from stderr/Output text or positive suite summaries. Unknown tests/packages are inspected for package lifecycle based on their event fields but are not mistaken for the expected root. Parsed Go semantic failure makes only ID1 nonpass. Go parser failure suppresses only this Go semantic evaluator and preserves all simulated receipts/XML reasons. No Go root/package/support case adds a final180 ID.

## 7. Independent parsing, complete reason order and row/top precedence

After successful outer checks always attempt XML and, if present, Go parsing independently. Always evaluate both validated receipts. An XML/pytest error must not suppress Go parsing; a Go rejection must not suppress XML parsing. A parser rejection skips only that stream's semantic evaluator. No failure can replace a previously retained reason. All hashes and receipts survive any admitted stream failure.

The complete ordered diagnostic reason vocabulary is the concatenation below, with each code at most once. No other reason/string is admitted:

```text
xml:xml_encoding
xml:xml_forbidden
xml:xml_invalid
xml:xml_nodes
xml:xml_depth
xml:xml_structure
xml:xml_string
xml:xml_text
xml:case_count
xml:unknown_case
xml:identity_mismatch
xml:duplicate_case
xml:missing_case
xml:testcase_failure
xml:testcase_error
xml:testcase_skipped
go:support_absent
go:events_count
go:line_size
go:line_delimiter
go:json_invalid
go:json_duplicate_key
go:json_nonfinite
go:json_depth
go:json_string
go:event_keys
go:event_type
go:unsupported_go_action
go:package_mismatch
go:unknown_test
go:package_lifecycle
go:root_lifecycle
go:root_failed
go:root_skipped
go:package_failed
go:package_skipped
pytest:simulated_nonzero
pytest:simulated_timeout
pytest:simulated_interrupted
pytest:ownership_lost
pytest:cleanup_incomplete
go:simulated_nonzero
go:simulated_timeout
go:simulated_interrupted
go:ownership_lost
go:cleanup_incomplete
```

At most one XML parser code; XML parser code excludes every XML semantic code. At most one Go parser code; Go parser code excludes every Go semantic code. Go absence excludes all other go: codes and Go receipt. Other groups combine without erasure. The parser code list order controls canonical serialization, not which error an underlying parser encounters first. XML/Go semantic evaluators accumulate their full summary sets. Receipt reasons must match the retained receipt objects exactly, including all adverse flags.

Derivation uses the following functions in order, with no optional policy:

- Shared baseline: XML parser reason => all14 unavailable; otherwise pytest interruption => all14 unavailable; otherwise any XML semantic reason or adverse pytest receipt reason => all14 failed; otherwise all14 passed.
- Go local status for ID1: absent, Go parser reason, or Go interruption => unavailable; otherwise any Go semantic reason or adverse Go receipt reason => failed; otherwise passed. Merge baseline ID1/local by severity unavailable > failed > passed. Other13 keep baseline, never Go local status.
- Top: XML/Go parser reason or go:support_absent => unavailable; otherwise any pytest/Go interruption => interrupted; otherwise any nonpass row => inconsistent; otherwise consistent. Parser unavailability outranks interruption; interruption outranks nonzero/semantic failure. No failure combination can yield new positive rows.

The clean-XML12-cell product matrix is mandatory. P=passed, F=failed, U=unavailable. Columns except Go-interrupted use clean Go receipt; pytest nonzero/interrupted rows use only the named adverse condition (interrupted may use exit0/cleanup True to isolate the flag).

| Pytest receipt | Go clean | Go malformed JSONL | Go semantic/lifecycle failure | Go interrupted receipt, clean stream |
|---|---|---|---|---|
| clean | consistent; ID1 P; ID2–14 P | unavailable; ID1 U; ID2–14 P | inconsistent; ID1 F; ID2–14 P | interrupted; ID1 U; ID2–14 P |
| nonzero | inconsistent; all14 F | unavailable; ID1 U; ID2–14 F | inconsistent; all14 F | interrupted; ID1 U; ID2–14 F |
| interrupted | interrupted; all14 U | unavailable; all14 U | interrupted; all14 U | interrupted; all14 U |

Normative mixed examples: Go raw `b'{\n'` raises B1 json_invalid. Clean XML + pytest SimulatedExit(1,False,False,False,True) + malformed Go/clean Go receipt yields ID1 U, other13 F, top unavailable, reasons exactly(go:json_invalid,pytest:simulated_nonzero). Clean XML + pytest SimulatedExit(None,False,True,False,False) + malformed Go/clean Go receipt yields all14 U, top unavailable, reasons exactly(go:json_invalid,pytest:simulated_interrupted,pytest:cleanup_incomplete). Simultaneous pytest nonzero/interruption preserves both codes and chooses the interruption baseline; malformed Go still wins top unavailable. Clean XML+clean pytest+Go absent yields first U, others P, top unavailable and only go:support_absent. XML malformed+Go malformed preserves both parser codes plus every receipt reason and all14 U. No case earns real acceptance credit.

## 8. Rows, refs, metadata and strict serialization

Diagnostic contract is exact `workshop-final180-commerce-synthetic-v1`; observation_kind exact `simulated-source-profile-validation`. All scalar strings are exact str, status one of consistent/inconsistent/unavailable/interrupted derived above. Every successful translate emits exact tuple of14 exact CommerceOutcome objects in embedded inventory order. family literal commerce; row status exact passed/failed/unavailable from derivation. First row raw_refs is the embedded5-ref tuple when Go present, the common3-ref tuple when absent. Other rows always use common3. They designate caller-retained memory only, not observed artifact files. No arbitrary caller ID/ref/path or normalized ID is admitted.

Authority is exact ordered tuple of these pairs; each pair exact tuple, key exact str, value exact False:

```text
fixture_verified
product_candidate_verified
staging_verified
deployment_authorized
cutover_verified
implementation_authorized
runtime_execution_authorized
profile_promotion_authorized
merge_authorized
```

accepted_case_credit exact int0 (bool rejected), profiles_enabled exact False, enabled_tiers exact empty tuple, runtime_lock/run_record exactly None. Context identity fixed; all present digests exact lower64hex; go_support_present exact bool with digest/receipt/absence constraints above. pytest_receipt and any Go receipt exact validated B1 type.

serialize_commerce_diagnostic accepts only exact CommerceDiagnostic, then validates in this order: concrete type and fixed contract/observation/context strings; all mandatory digest types/syntax; go_support_present and optional field coherence; receipt schemas; exact authority/credit/profile/lock fields; reasons type/vocabulary/order/uniqueness/exclusions and exact correspondence to receipt facts; observations exact type/count/order/IDs/families/refs/status derived from reasons; top status derived from reasons. Every invalid field raises sole `diagnostic_invalid`, no partial bytes. Reasons exact tuple of<=46 distinct exact strings (actual literal vocabulary count is authoritative); receipt reason omissions/extras fail. In absent-Go diagnostics go:support_absent is mandatory and sole go: reason; present-Go diagnostics forbid it. No defaulted or missing metadata is silently repaired. Serializer accepts only a valid typed synthetic result; it does not claim to reparse raw bytes or authenticate that supplied digest/reason facts came from an actual translator call.

Serialization object has exactly the dataclass field names, with receipts converted to objects having exactly exit_code, timed_out, interrupted, ownership_lost, cleanup_complete. Optional Go receipt serializes null when absent; authority converts to object; tuples serialize arrays; observations objects have exactly family,logical_id,status,raw_refs. No source text, byte arrays, tracebacks or extra keys. Output is `json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)` encoded UTF8 plus exactly one final LF; <=65536 bytes inclusive. Over bound => `diagnostic_size`; otherwise return exact bytes. Canonical output repeat is identical. Authority key input order is checked even though JSON sort_keys canonicalizes final key order. No JSON deserializer is public. Direct dataclass construction can only create synthetic metadata; valid serialization conveys no runtime authority.

## 9. Future verification and three-file implementation boundary

Only after a new synchronized committed gate, standalone/nested exact-base preflights, independent gate review and explicit coordinator dispatch may an implementation worker change these three files:

1. scripts/dev/workshop_final180_commerce_adapter.py
2. scripts/dev/test_workshop_final180_commerce_adapter.py
3. docs/verification/workshop-final180-runbook.md

New tests must construct bytes independently from this literal contract, never import source collector expectations or launch its CLI. Cover all14 commerce IDs and53 supports missing/duplicate/wrong identity; opaque unfamiliar support classname positive and reserved classname negative; document/attribute/order permutations; each XML error and semantic code; every parser/budget bound and reachable bound+1; inherited Go parser regressions without modifying B1; package/root run/output/terminal lifecycle; every12-cell matrix outcome and optional support absence; simultaneous flags; continued dual parsing/reason retention; receipt None/bool invalid cases; serializer forged types/rows/refs/reasons/status/credit/profile/authority/receipt/digest/optional-field coherence; deterministic encoding. Parser/limit tests must not execute an application or external resource. XML entity/DTD tests assert rejection with no resolver callback I/O. AST/import checks are scope evidence, not a security sandbox.

Preserve Stage A runner/test and B1 adapter/test byte-for-byte at embedded pins; B2 files remain out of scope. Future coordinator chooses a reviewed stable integration parent and reconciles the shared runbook after B2. Appropriate later checks are focused commerce, unchanged B1/Stage A/B2 offline tests if present, developer/autonomy offline suites, compile without bytecode, diff/allowlist/pin checks and independent exact-code-head review. Do not run opt-in integration/fixture flags, Docker, browser, network, providers or payments. No changes to application, source tests/collectors, SQL, Compose/workflow, dependencies, assembler, policy/profile, inventory or autonomy runner are authorized by this spec.

This external draft has no synchronized tracking record, no preflight receipt, no committed-gate review and no implementation authority. Independent review must assess the exact current spec bytes, parser/error/budget completeness, optional-support policy, source pins, mixed matrix and serializer consistency. Later repository promotion needs exact-head gate review in addition to this external technical review. All financial, runtime compatibility, actual collection and acceptance blockers remain separate and cannot be removed by synthetic unit success.

## 10. Embedded literal mappings and source pins

The appendices below are normative data. Implementer must transcribe fixed literals, not load this file or any external planning file at runtime. Source class arrays for support are documentary; only literal name and opaque-classname policy above control synthetic support admission. Source refs are documentary and cannot be opened by the adapter.

### 10.1 Exact commerce IDs and memory refs

```json
{
  "commerce_classname": "tests.test_commerce_postgres",
  "common_raw_refs": [
    "workshop-commerce-tests.xml",
    "workshop-commerce-pytest.stdout.log",
    "workshop-commerce-pytest.stderr.log"
  ],
  "first_case_go_refs_if_present": [
    "workshop-commerce-go-events.jsonl",
    "workshop-commerce-go-stderr.log"
  ],
  "commerce": [
    {
      "family": "commerce",
      "index": 0,
      "logical_id": "test_orders_create_and_owner_scope",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log",
        "workshop-commerce-go-events.jsonl",
        "workshop-commerce-go-stderr.log"
      ],
      "source": {
        "end_line": 192,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 162
      }
    },
    {
      "family": "commerce",
      "index": 1,
      "logical_id": "test_same_key_replay_and_conflict",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 201,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 195
      }
    },
    {
      "family": "commerce",
      "index": 2,
      "logical_id": "test_concurrent_keys_share_one_checkout",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 209,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 204
      }
    },
    {
      "family": "commerce",
      "index": 3,
      "logical_id": "test_scope_races_single_active_grant",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 218,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 212
      }
    },
    {
      "family": "commerce",
      "index": 4,
      "logical_id": "test_lost_create_response_and_retention_boundary",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 229,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 221
      }
    },
    {
      "family": "commerce",
      "index": 5,
      "logical_id": "test_expiry_requires_remote_nonchargeable_proof",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 239,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 232
      }
    },
    {
      "family": "commerce",
      "index": 6,
      "logical_id": "test_completion_races_expiry_without_recharge",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 246,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 242
      }
    },
    {
      "family": "commerce",
      "index": 7,
      "logical_id": "test_webhook_before_create_response",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 253,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 249
      }
    },
    {
      "family": "commerce",
      "index": 8,
      "logical_id": "test_settlement_binds_financial_owner_scope",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 264,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 256
      }
    },
    {
      "family": "commerce",
      "index": 9,
      "logical_id": "test_duplicate_and_distinct_events_grant_once",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 274,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 267
      }
    },
    {
      "family": "commerce",
      "index": 10,
      "logical_id": "test_refund_chargeback_ordering_and_monotonic_revocation",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 296,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 277
      }
    },
    {
      "family": "commerce",
      "index": 11,
      "logical_id": "test_payment_survives_source_unavailable_and_restart",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 345,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 299
      }
    },
    {
      "family": "commerce",
      "index": 12,
      "logical_id": "test_library_is_owner_only_and_paginated",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 363,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 348
      }
    },
    {
      "family": "commerce",
      "index": 13,
      "logical_id": "test_grant_check_exact_scope_legacy_and_revoked",
      "raw_refs": [
        "workshop-commerce-tests.xml",
        "workshop-commerce-pytest.stdout.log",
        "workshop-commerce-pytest.stderr.log"
      ],
      "source": {
        "end_line": 382,
        "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
        "start_line": 367
      }
    }
  ]
}
```

### 10.2 Exact53 nominal support names

```json
[
  {
    "name": "test_migrations_are_numeric_and_ordered",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_customer_identity_migration_and_all_four_driver_boundaries",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_commerce_migration_has_structured_owner_and_financial_guards",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_dataset_request_ownership_is_backfilled_without_overwriting_existing_values",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_schema_migrations_cover_platform_spine_and_vector",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_foundation_fixture_is_separate_from_schema_migrations",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_chat_quote_revision_publication_state_and_immutability_are_database_enforced",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_price_snapshots_are_immutable_and_refresh_failures_are_separate",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_visual_artifacts_require_and_preserve_source_artifact_linkage",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_quote_arithmetic_and_overlap_bounds_are_database_enforced",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_quote_persists_required_and_recommended_operation_collections",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_quote_operation_categories_upgrade_existing_025_table",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_worker_events_persist_the_complete_event_envelope",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_reusable_derived_article_key_prevents_query_uniqueness_collisions",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_markup_is_structurally_prohibited",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_psql_command_includes_host_and_port_when_address_provided",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_resolve_database_address_respects_explicit_and_environment",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "MigrationPlanTests"
    ]
  },
  {
    "name": "test_emit_is_embedded_and_uses_one_session_lock",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "SharedDriverTests"
    ]
  },
  {
    "name": "test_manifest_rejects_holes_unsafe_names_symlinks_and_wrong_stems",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "SharedDriverTests"
    ]
  },
  {
    "name": "test_fixture_prefix_accepts_only_contiguous_canonical_prefix",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "SharedDriverTests"
    ]
  },
  {
    "name": "test_default_refuses_truncated_manifest_before_sql_output",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "SharedDriverTests"
    ]
  },
  {
    "name": "test_default_invocation_executes_identical_emit_output_and_cleans_tempfile",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "SharedDriverTests"
    ]
  },
  {
    "name": "test_fixed_transaction_contract_is_audited",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "SharedDriverTests"
    ]
  },
  {
    "name": "test_adapter_streams_one_driver_and_returns_only_actual_applications",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "SharedDriverTests"
    ]
  },
  {
    "name": "test_adapter_propagates_generator_and_psql_failure",
    "source_path": "scripts/dev/test_migrations.py",
    "source_classes_documentary_only": [
      "SharedDriverTests"
    ]
  },
  {
    "name": "test_full_chain_restart_preserves_every_marker_and_schema",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_partial_catalog_row_survives_full_restart",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_empty_bootstrap_and_untracked_application_rejection[False]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_empty_bootstrap_and_untracked_application_rejection[True]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_invalid_ledger_fails_before_pending_application_ddl[unknown]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_invalid_ledger_fails_before_pending_application_ddl[wrong_stem]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_invalid_ledger_fails_before_pending_application_ddl[gap]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_invalid_ledger_fails_before_pending_application_ddl[duplicate_shape]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_invalid_ledger_fails_before_pending_application_ddl[wrong_timestamp]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_original_038_adoption_and_markerless_033_effects_are_once_only",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_genuine_036_upgrade_preserves_jobs_and_matches_fresh_schema",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_migration_failure_rolls_back_only_active_file_then_retry[2]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_migration_failure_rolls_back_only_active_file_then_retry[33]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_migration_failure_rolls_back_only_active_file_then_retry[36]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_migration_failure_rolls_back_only_active_file_then_retry[37]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_migration_failure_rolls_back_only_active_file_then_retry[38]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_migration_failure_rolls_back_only_active_file_then_retry[39]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_migration_failure_rolls_back_only_active_file_then_retry[40]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_recorded_001_and_partial_unmarked_next_file_remain_retryable",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_two_full_runners_serialize_and_apply_each_version_once[False]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_two_full_runners_serialize_and_apply_each_version_once[True]",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_connection_death_releases_lock_and_rolls_back_active_file",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_restart_after_committed_037_only_applies_038_and_039",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_native_python_adapter_applies_then_skips_in_one_session",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_markerless_033_failure_rolls_back_reviewer_effects_and_marker",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_populated_publication_and_all_lifecycle_records_survive_restart",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_populated_038_upgrade_only_adds_identity_schema",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  },
  {
    "name": "test_populated_customer_identity_restart_preserves_rows_and_ledger",
    "source_path": "workers/ingestion-python/tests/test_article_lifecycle_migrations.py",
    "source_classes_documentary_only": []
  }
]
```

### 10.3 Immutable direct source/dependency pins

```json
{
  "active_b2_review_status": "not assessed; snapshot only, no dependency on B2",
  "active_b2_snapshot_read_sha": "7ea63d77acb5a0972dd86b2b138017fe9b6f288b",
  "b2_gate_read_sha": "3cd99224eae7012f8c6cc0bfc15a1053a8e7762f",
  "candidate_sha": "4d82e413e04fb2401ac7bc28dc828375ac662180",
  "external_addendum_pins": [
    {
      "bytes": 3105,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/REPORT.md",
      "sha256": "4229dc2b8ee8429b0014b074c5dd1c87dae76c4d5bf3b35d1d35d28170498bed"
    },
    {
      "bytes": 3597,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/report.json",
      "sha256": "36670a61779baa5ec2dd40d879b485c32d2a41907e1f971507ad450ca1a679ae"
    },
    {
      "bytes": 17985,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/source-pins.json",
      "sha256": "b6f30101a457ea99df668a772ea4123cb3f2eecab9697d158146bd7ed2fc3692"
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
      "bytes": 270936,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/sql-row-schemas.json",
      "sha256": "ad4a304df66d6472abfd9ccfd5900b4e8889b0312c87e81cdab0e74f5f1afac9"
    },
    {
      "bytes": 49312,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/http-route-body-outcomes.json",
      "sha256": "b0dfb32d879d76c1ea8d7b563606c77fa31290e78ae1739cd8da370a825d9366"
    },
    {
      "bytes": 694,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/verification.json",
      "sha256": "5510f4a05686bff8b0d92bdc89b718ef7ecbab3d1b24e868a5387b2825e6e71a"
    },
    {
      "bytes": 681,
      "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/verification-independent.json",
      "sha256": "4ad31c52f58fea832efc6c29c2eb61647ce31800eeda1ec4bcd7efce53f360d7"
    }
  ],
  "reviewed_b1_head_sha": "54a7ca32eab80654310d862f0ac6957375d16e8b",
  "source_pins": [
    {
      "bytes": 7443,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "bba155614122d795e4a91ee05dba51e21a76d144",
      "path": "scripts/dev/workshop_commerce_smoke.py",
      "sha256": "3fa9b5f4d13fee71d8c6cd2b0592a2d6a128485b161f727bcc96685d2a59d2f9"
    },
    {
      "bytes": 31526,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "fdccc37c1d13394ecb634c17ef12614b6fc9ac76",
      "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
      "sha256": "fbab00f576410393e5077351d08d108c884d4a6442549fc4192647796e19904e"
    },
    {
      "bytes": 2062,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "2f03fe4f793f179485fffec9fe5ea519708b3a77",
      "path": "scripts/dev/test_workshop_commerce_smoke.py",
      "sha256": "7c0956c6563bc97e8ddb7de478421db205289b619d53f728e23bb1ebe0332173"
    },
    {
      "bytes": 40887,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "cd505e4c452331dab924ee81fe7fb729842935d4",
      "path": "workers/ingestion-python/src/autodata_ingestion/commerce_service.py",
      "sha256": "ec32793162c6a4cb1fdfe136502e2ada8b38bf59d63a2fffc58b527031c35490"
    },
    {
      "bytes": 10161,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "f427f03d77d4346e8f112430a1fdf29bcc3d987a",
      "path": "workers/ingestion-python/src/autodata_ingestion/stripe_adapter.py",
      "sha256": "bc99786ce246267109aeedbfa360d2fbbb4ae94e924f87387b76df9e40a3b047"
    },
    {
      "bytes": 20203,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "6e23c15c67b54e3b053aa709ebfa4da920d18605",
      "path": "workers/ingestion-python/src/autodata_ingestion/payment_reconciliation.py",
      "sha256": "e52439e7ce59c4d93aa4f3bb62931a35ab5b1dd012f032be6e6272e121fa41ac"
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
      "bytes": 18502,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "648a6dbb6a2995161c2bcc535af526140cb3380f",
      "path": "scripts/dev/test_migrations.py",
      "sha256": "2ce5c434d5f48a265d448b9f2c01d68433177cb1fd7199c227f908434adbddc0"
    },
    {
      "bytes": 4956,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "18ec48100cdbb7ebbd226e97eba05ad42cfbc341",
      "path": "db/migrations/040_workshop_commerce.sql",
      "sha256": "7ff3203b5c980bf7fe688470ef737f0d29789ff9c5f04b9744257d0715cb695e"
    },
    {
      "bytes": 1359,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "e34a75f6e34f575d12c4bc95f37132965b952142",
      "path": "db/migrations/012_payment_fulfillment_reconciliation.sql",
      "sha256": "a1f2de68abbcefef86659c6b6f5e4a98f28c8c8de4e0ebe44ea7833fe9a4d169"
    },
    {
      "bytes": 11067,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "9a62dff8589f5f96d44df966a9109f63abfab354",
      "path": "apps/api-go/commerce_client_test.go",
      "sha256": "972b456f70c8f29afb65505a54266907c74875c7e534bf354884079d757cefc2"
    },
    {
      "bytes": 4272,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "35f46e9a0a90c5abf30c2b2ace2f2c9011dc325b",
      "path": "apps/api-go/commerce_client.go",
      "sha256": "a567c42fadbef7e29b2f3a1de23f9766f851656de647b06c188b27b229c9e772"
    },
    {
      "bytes": 7841,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "7f7e8f0393d74762b7114d18ab4e994b743cd6af",
      "path": "apps/api-go/commerce_http.go",
      "sha256": "5e98078040e95d0b5d8b5945f0defa4caa037513734e78ca6190d013c395b7c7"
    },
    {
      "bytes": 7972,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "90b32ed811fc0c7df36119ae81eef7fb09b48d85",
      "path": "apps/api-go/commerce.go",
      "sha256": "e9c35f997b15d8fab2a4b31b9ef40f39758bc20afa9b6963b15c5a5a719aab6c"
    },
    {
      "bytes": 3986,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "16982a9310be7447103e2bfacecf9f7cb764704e",
      "path": "apps/api-go/go.mod",
      "sha256": "3306c3736c51a3c08a4ed30613a9f0ba4db7f5094d0215ebdf54545873012923"
    },
    {
      "bytes": 1385,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "a6d7663a663fdb2d3bec0d58506fc5e161d3cf32",
      "path": "infra/compose/article-lifecycle-test.Dockerfile",
      "sha256": "ea1d9f043e8775ecbdeea60e9df86ade41fe2d61bd9aadb557479be745e6fc5f"
    },
    {
      "bytes": 6162,
      "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
      "git_blob": "d83059380930535ed520ba3c0ed99de1b2297196",
      "path": "docs/architecture/workshop-commerce.md",
      "sha256": "7bca04fe632427949b0415e0c17a37d16729437def4a7193bec702f167307895"
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
      "bytes": 13657,
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "8979973a5124d4f3f7a439dba31ca8104e488971",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final180-stage-b1-identity.md",
      "sha256": "02f92b355c5dcd3144f1ec80c21118a86a9624b466dfa756a6795edd13fa21ca"
    },
    {
      "bytes": 82081,
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "4a29e0915c677a2f07e3ca6b0ab9109e888651d1",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-stage-b1-identity.md",
      "sha256": "285e5abfe824b4b9490af8e4b2fa3655f53ea34d8afc631e69a88feb909d242a"
    },
    {
      "bytes": 47124,
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "ca48cd988c5579a7d385dc1844b84306eae0861e",
      "path": "scripts/dev/workshop_final180_runner.py",
      "sha256": "693a408a73f3ccd37bf945bfc94d427f742878580932dab382ea9a244a141c91"
    },
    {
      "bytes": 32981,
      "commit": "54a7ca32eab80654310d862f0ac6957375d16e8b",
      "git_blob": "2cfa9dc8ea116b7aa5b0c541529712b4b5d24be3",
      "path": "scripts/dev/test_workshop_final180_runner.py",
      "sha256": "2f92614e937b5b3d6a17da7ab9f4b758b34a4a542fbe5564b29ddefd4f7b148a"
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
      "bytes": 50477,
      "commit": "3cd99224eae7012f8c6cc0bfc15a1053a8e7762f",
      "git_blob": "5d79004dca6add657533ef6883895c7698adb988",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final180-stage-b2-catalog-go.md",
      "sha256": "0b2899864f1964e50b4e5ca7f7d70d48331c3f1f1aad6898b8d2f7eb83b9889f"
    },
    {
      "bytes": 73739,
      "commit": "3cd99224eae7012f8c6cc0bfc15a1053a8e7762f",
      "git_blob": "584b12c2b880ae328ab39da73753a6f0e4a7a8ba",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-stage-b2-catalog-go.md",
      "sha256": "c8e9a3f4c663fcc9e43bab3ef84e9e8dd978a4d29fa75122acf9372e5e22cb7b"
    },
    {
      "bytes": 11486,
      "commit": "7ea63d77acb5a0972dd86b2b138017fe9b6f288b",
      "git_blob": "68174a5ecf20091f4ca819b1e667fefdf8c7419d",
      "path": "scripts/dev/workshop_final180_catalog_adapter.py",
      "sha256": "2de00fbb898d7fff140ba26cf0d9701cb8710e15272e8d9e1fa4b059ce0b1277"
    },
    {
      "bytes": 14379,
      "commit": "7ea63d77acb5a0972dd86b2b138017fe9b6f288b",
      "git_blob": "2f031d7fb3afda5b66ea6e264a14abe7f226aa35",
      "path": "scripts/dev/test_workshop_final180_catalog_adapter.py",
      "sha256": "470133f5fa78f9210bb9886290f7cd506b957639898b5cdebe1036eb60aaa6a7"
    }
  ]
}
```

### 10.4 Prior external review inputs

This spec advances the repaired external proposal rather than inheriting a review PASS. Prior DRAFT.md SHA256 is `9d706bc850fc6aad24560f732a376625da3afb3fa9d2117a88bca619f1ae96e4`; prior report.json SHA256 is `614340d358570389a7104958b352e75672cefab5eb23a1bf4544633fdb87a903`. Source-only verification was repeated for all33 direct pins, all82 inventory candidate paths and all62 corrected-addendum pins. The public interfaces, exact XML error checks, full vocabulary, optional-Go absence state and serializer contract are newly frozen here and require fresh independent review. No reviewer result is fabricated.

## 11. Repository promotion pins and precedence

The current planning parent above supersedes historical recommendations to choose a later stable integration parent; no silent rebase is allowed. Historical B1 source pins in section 10 document the original external inspection. The unchanged public B1 adapter/test match those pins at the current parent. Stage A test source now includes the reviewed CI fixture isolation repair; use the current parent pins below for preservation, not the historical B1-era Stage A test blob. B2 is not imported. Preserve every predecessor planning/record/task/implementation/test/workflow byte; the sole existing-file edit in this gate is an append to the assembler planning index. During later implementation only the runbook is an allowed existing-file edit, append-only for this slice. No external planning path is a runtime dependency.

External audit artifacts (source-only checks and historical status, not acceptance or current gate receipts):

```json
{
  "DRAFT.md": {
    "bytes": 25079,
    "sha256": "9d706bc850fc6aad24560f732a376625da3afb3fa9d2117a88bca619f1ae96e4",
    "historical_locator": "/home/corp/autodata-evidence/final180-commerce-planning/DRAFT.md"
  },
  "SPEC.draft.md": {
    "bytes": 65156,
    "sha256": "ad1c3cfa26315babfbc0820b2bf0b06463a204eb30e18516bc876888d4a12d41",
    "historical_locator": "/home/corp/autodata-evidence/final180-commerce-planning/SPEC.draft.md"
  },
  "report.json": {
    "bytes": 5561,
    "sha256": "614340d358570389a7104958b352e75672cefab5eb23a1bf4544633fdb87a903",
    "historical_locator": "/home/corp/autodata-evidence/final180-commerce-planning/report.json"
  },
  "SPEC.source-check.json": {
    "bytes": 2907,
    "sha256": "a5f1dd9546fc018de45bab1946f0aa234733bbff4278190e391e9deeae11271e",
    "historical_locator": "/home/corp/autodata-evidence/final180-commerce-planning/SPEC.source-check.json"
  },
  "source-pins.json": {
    "bytes": 12483,
    "sha256": "5c66f5f911a5da893393d4a16debd0536fe4b13a6261e326898a4c6026583d5b",
    "historical_locator": "/home/corp/autodata-evidence/final180-commerce-planning/source-pins.json"
  },
  "literal-mappings.json": {
    "bytes": 41200,
    "sha256": "52cea4301b9ca8fd67bfdb0502d640f76697517c893d2d58d87f8642b494b897",
    "historical_locator": "/home/corp/autodata-evidence/final180-commerce-planning/literal-mappings.json"
  },
  "verification.json": {
    "bytes": 912,
    "sha256": "f12201ca00e473c4377467d12c57874d218bc89c41a5708a13e39c6314faecef",
    "historical_locator": "/home/corp/autodata-evidence/final180-commerce-planning/verification.json"
  },
  "citations.json": {
    "bytes": 38493,
    "sha256": "ee9bb8cfd77954818c0274a224455cd74fd374bacd8f8c7a9e40cced38fd926f",
    "historical_locator": "/home/corp/autodata-evidence/final180-commerce-planning/citations.json"
  }
}
```

Exact parent implementation and canonical invariant pins:

```json
[
  {
    "path": "scripts/dev/workshop_final180_runner.py",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "ca48cd988c5579a7d385dc1844b84306eae0861e",
    "bytes": 47124,
    "sha256": "693a408a73f3ccd37bf945bfc94d427f742878580932dab382ea9a244a141c91"
  },
  {
    "path": "scripts/dev/test_workshop_final180_runner.py",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "f4db092e0d1a83fce47b51f7c68021b6dc2053bd",
    "bytes": 33237,
    "sha256": "c0bac62eb756d84593191e82b2b240fdd77bd5128242f212e9b508e15c1740c1"
  },
  {
    "path": "scripts/dev/workshop_final180_identity_adapter.py",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "8c7fa87bab906955c145d7cc965be641aea48c5f",
    "bytes": 22290,
    "sha256": "0474a85c33d4f2722ad01d6e55e69a8080dc0f1983c856ca7caa1b94510a767d"
  },
  {
    "path": "scripts/dev/test_workshop_final180_identity_adapter.py",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "7391263cb874e2505f4f110df6343c8b466fc692",
    "bytes": 29838,
    "sha256": "a3f3017b1d7a85da9ae4d1883758f2494d722fb321d45c1ff758994ab6d2653c"
  },
  {
    "path": "scripts/dev/workshop_final180_catalog_adapter.py",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "060d1407ee5e71880cf7e441195cac4274f04937",
    "bytes": 15467,
    "sha256": "88f481104d66d9bda8bdf6c1a8038e8514b69d63db813b85c5ec13e40f0c6ddf"
  },
  {
    "path": "scripts/dev/test_workshop_final180_catalog_adapter.py",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "86e78aef564c216ede5780dccadd56366d4d0a63",
    "bytes": 26977,
    "sha256": "978cbb594d9bc42f0cb02b3447e2afed6bb6764c155b657db6e5b3676cc319a9"
  },
  {
    "path": "docs/verification/workshop-final180-runbook.md",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "05c38499f47d8960e9d6ae8c0497f5866cec200c",
    "bytes": 22069,
    "sha256": "0a36f9e46ffa767feacc3a49ead622ce3d424b5eec155300c3df58dde8da89d6"
  },
  {
    "path": "docs/agents/pre-implementation-gate.md",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "41076af1db25f0cff8ca41d0203c050af9b772df",
    "bytes": 5659,
    "sha256": "fa6e9c95c2674164c90d78e046a0427f6b406c313fb82ff627a2a2facb560ad0"
  },
  {
    "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.json",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "24ac3e9264b85eb914daa7805d183e15f58d374a",
    "bytes": 122350,
    "sha256": "c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39"
  }
]
```

Repository promotion must preserve technical sections 1-10 byte-for-byte except the title/status preamble. The source-check file records the prior segmentation defect and repair; the coordinator reports independent repaired-spec review PASS at the exact digest above. No source-check or external review constitutes synchronized tracking, a committed repository gate review or passing parent CI.

Predecessor code-only review tracking is https://github.com/lucronn/autodata/issues/186#issuecomment-6638840314; the coordinator reports the Project Source begins `CI fixture integration headfa0c1b code-only independent review PASS`. This predecessor synchronization does not synchronize Stage C or establish CI Actions success; exact-parent CI remains pending at the observed readback.

## 12. Synchronized repository planning index

Issue186/Project8 planning `synchronized` with live readback at https://github.com/lucronn/autodata/issues/186#issuecomment-6638920703. Coordinator preserved the Issue body, all164 prior comments (now165), archived the prior Project Source verbatim and preserved unrelated Project fields; Project remains In Progress. Independent five-file pre-sync draft review PASS/no findings is coordinator-reported. Committed-checkpoint standalone/nested preflight, independent exact-checkpoint review and explicit coordinator dispatch remain required. No implementation or runtime authority follows.

## Live tracking receipt

The coordinator is the sole serialized GitHub writer. Receipt `/home/corp/autodata-evidence/final180-commerce-gate-tracking/receipt.json`, SHA256 `5e44e24272d77ce2402026ddea783dcb544af9f6de3b173374abc47dda55dc99`, records `synchronized_live_readback`. Issue before/after SHA256 `0cfbf7cb250943873bf0e60f8d15a2827431f71d03e8e6754eb48595ca92986b` / `5e1789d6c595508c2fc22257eb461da52b51bcb6ba7704d51565fddbba47935b`; Project before/after SHA256 `33aff0d836b5dd418b4a075f34a046c8a6f0a454806b3b5cf1a4390af70c1efa` / `8b36b7fe8a54b4fe6a700ee8a33401496855b6c9af3bb53a4337f3e9094a2e37`; prior/current Source SHA256 `a1a9e1f920c1c344076ec77d998af8d085b0cd15bad92a80c1589be495d6e62c` / `ad0b1d9d0c93ce3171a428c7ea6be9d783fb2a7554e9309f57851bd0b447d67e`. Project item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, field Source or dependency reference, status In Progress. The standalone record and identical nested record retain all exact receipt/readback references. These saved bytes were hash-checked and the Issue body/comments plus unrelated Project fields compared before checkpoint preparation; no Gate-checkpoint review or dispatch is claimed.

The reproduced external technical sections retain their original external-draft/no-tracking provenance statements; those refer to the original external artifact. This section and the repository status preamble record the new dedicated repository planning synchronization. Public interfaces, XML segmentation/grammar, matrix, vocabulary, serializers, IDs and source pins are unchanged. Standalone/nested records now contain status synchronized and identical receipt objects; no historical external JSON pin is relabeled as a live receipt.
