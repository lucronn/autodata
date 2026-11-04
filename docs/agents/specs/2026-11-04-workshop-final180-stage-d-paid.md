# Workshop final180 Stage D paid12 restricted synthetic Go-event specification

**Status: synchronized planning.** Issue186/Project8 live tracking at https://github.com/lucronn/autodata/issues/186#issuecomment-6639038727; independent five-file pre-sync review PASS/no findings is coordinator-reported. Exact committed-checkpoint preflight, independent checkpoint review and coordinator dispatch remain required. All authority remains false; no implementation, runtime admission or accepted evidence follows.

**Exact planning parent:** `fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc`, independently reviewed CI integration code head (PR https://github.com/lucronn/autodata/pull/232). Exact-head CI was pending at coordinator readback; no pass is claimed. **Application candidate:** `4d82e413e04fb2401ac7bc28dc828375ac662180`. The historical tooling/CI planning snapshots in embedded source citations below remain historical provenance. They are superseded as planning parent by this exact reviewed integration head. Stage C commerce planning is parallel work and supplies no dependency or authority to Stage D.

**External reviewed source pins:** DRAFT SHA256 `1853c07976970b6a22931687548f4c740c87649fab9c1e14f5c8f79a56e3cc73`; SPEC.draft SHA256 `01ef4b2c0405a53b43e16b9ed5a2ecc0ee7627ef048610afb2c5348dceb6e71c`. Their complete technical contract and original source/control-flow citations are embedded below so the external files are audit locators, not implementation dependencies. Any historical statement about absent repository planning refers to external-draft creation; current live tracking synchronization is recorded above; exact-checkpoint preflight/review/dispatch remain separate implementation prerequisites.


## 1. Scope and immutable identities

Implement later only a side-effect-free Python library translating twelve supplied in-memory Go-event/stderr byte pairs plus simulated exit receipts into twelve synthetic observations. Expected IDs, roots, providers and raw reference strings are literal constants, never imported/generated from candidate code at translation time. Bank attribution is unauthenticated caller context. Identical bytes in two bank slots are valid synthetic inputs. No observation proves actual execution, real bank attribution, grant semantics, a payment or settlement.

Application candidate: `4d82e413e04fb2401ac7bc28dc828375ac662180`. Inventory SHA256: `c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39`. Read-only tooling snapshot: `0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471`. CI planning context snapshot: `8bc9371a2715f34f06f261c8abae4194be2e1ea0`, with no assertion that concurrent CI repair/review is complete. The coordinator has selected reviewed CI integration `fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc` as this planning parent and the exact dependency pins below were compared with its Git objects; the full paid checkpoint SHA and subsequent exact-base preflight are sealed externally after commit; tracking status does not establish checkpoint review or dispatch.

The canonical pre-implementation gate still requires committed plan/spec/task/record, synchronized Issue186/Project8/canonical docs/todo, exact-base standalone/nested preflight, independent gate review and coordinator dispatch. This document supplies no substitute. Preserve Stage A/B1/B2/CI scope. Future implementation allowlist is exactly:

1. `scripts/dev/workshop_final180_paid_adapter.py` (new library).
2. `scripts/dev/test_workshop_final180_paid_adapter.py` (new constructed fake-byte tests).
3. `docs/verification/workshop-final180-runbook.md` (coordinator-reconciled documentation).

No candidate producer/application/SQL/Compose/workflow/dependency/assembler/evaluator/profile/policy/autonomy runner/inventory edit. Preserve Stage A runner/test and B1/B2 adapters/tests byte-for-byte at the future gate. No B2/commerce import, parser extraction or refactor.

Direct permitted imports are `from dataclasses import dataclass`, `import hashlib`, `import json`, `import re`, and exactly these public symbols from `scripts.dev.workshop_final180_identity_adapter`: `parse_identity_events`, `GoEvent`, `AdapterError`, `SimulatedExit`. Public aliases may not mask private imports. No CLI/entrypoint, file/path opening, subprocess/network/clock/signal/async runtime, fixture/test imports, callbacks, provider clients, timers, fake replay scheduler, mutable execution plan or environment inspection. AST/import checks demonstrate scope only, not a hostile-code sandbox.

## 2. Exact public interface

Use the existing exact B1 `GoEvent`, `AdapterError` and `SimulatedExit` classes; do not redefine them. New dataclasses have `frozen=True`, listed fields in listed order, no defaults, and no additional fields. Tuple annotations do not replace runtime type checks. All instances/primitive/container types below require `type(value) is ExpectedType`; subclasses and bool-as-int reject. Values cannot be coerced. All diagnostic failure codes are stable literal strings with no source/decoder exception text.

```python
@dataclass(frozen=True)
class PaidContext:
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str

@dataclass(frozen=True)
class PaidCase:
    provider: str
    go_test_name: str
    events_raw: bytes
    stderr_raw: bytes
    receipt: SimulatedExit

@dataclass(frozen=True)
class PaidOutcome:
    family: str
    logical_id: str
    status: str
    raw_refs: tuple[str, ...]
    events_sha256: str
    stderr_sha256: str
    failures: tuple[str, ...]

@dataclass(frozen=True)
class PaidDiagnostic:
    contract: str
    observation_kind: str
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str
    status: str
    observations: tuple[PaidOutcome, ...]
    accepted_case_credit: int
    profiles_enabled: bool
    enabled_tiers: tuple[str, ...]
    authority: tuple[tuple[str, bool], ...]

def parse_paid_events(raw: bytes) -> tuple[GoEvent, ...]: ...
def translate_paid(cases: tuple[PaidCase, ...], context: PaidContext) -> PaidDiagnostic: ...
def serialize_paid_diagnostic(value: PaidDiagnostic) -> bytes: ...
```

Existing receipt fields, in order, are `exit_code: int|None`, `timed_out: bool`, `interrupted: bool`, `ownership_lost: bool`, `cleanup_complete: bool`. Existing GoEvent fields are `time: str`, `action: str`, `package: str`, `test: str|None`, `elapsed: int|float|None`, `output: str|None`, `failed_build: str|None`.

## 3. Literal constants, twelve slots and reference order

`CANDIDATE` and `INVENTORY` equal the exact candidate/inventory strings in section1. `PACKAGE = 'github.com/lucronn/autodata/apps/api-go'`. `SLOTS` is the following exact tuple of `(provider, root, logical_id, (events_ref, stderr_ref))`. The labels never authorize opening files or deriving filesystem paths. Output must follow this order regardless of caller tuple order.

```python
SLOTS = (
    ('bankone', 'TestPostgresPaidCatalogGrantBeforeWork',
     'TestPostgresPaidCatalogGrantBeforeWork-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogGrantBeforeWork/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogGrantBeforeWork/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogGrantBeforeWork',
     'TestPostgresPaidCatalogGrantBeforeWork-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogGrantBeforeWork/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogGrantBeforeWork/go-stderr.log')),
    ('bankone', 'TestPostgresPaidCatalogExactScopeAndOwnerIsolation',
     'TestPostgresPaidCatalogExactScopeAndOwnerIsolation-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogExactScopeAndOwnerIsolation/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogExactScopeAndOwnerIsolation/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogExactScopeAndOwnerIsolation',
     'TestPostgresPaidCatalogExactScopeAndOwnerIsolation-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogExactScopeAndOwnerIsolation/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogExactScopeAndOwnerIsolation/go-stderr.log')),
    ('bankone', 'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse',
     'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse',
     'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse/go-stderr.log')),
    ('bankone', 'TestPostgresPaidCatalogContextualMediaAndRevocation',
     'TestPostgresPaidCatalogContextualMediaAndRevocation-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogContextualMediaAndRevocation/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogContextualMediaAndRevocation/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogContextualMediaAndRevocation',
     'TestPostgresPaidCatalogContextualMediaAndRevocation-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogContextualMediaAndRevocation/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogContextualMediaAndRevocation/go-stderr.log')),
    ('bankone', 'TestPostgresPaidCatalogHistoricalSourceAndRights',
     'TestPostgresPaidCatalogHistoricalSourceAndRights-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogHistoricalSourceAndRights/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogHistoricalSourceAndRights/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogHistoricalSourceAndRights',
     'TestPostgresPaidCatalogHistoricalSourceAndRights-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogHistoricalSourceAndRights/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogHistoricalSourceAndRights/go-stderr.log')),
    ('bankone', 'TestPostgresPaidCatalogCustomerLegacyRoutesDenied',
     'TestPostgresPaidCatalogCustomerLegacyRoutesDenied-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogCustomerLegacyRoutesDenied/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogCustomerLegacyRoutesDenied/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogCustomerLegacyRoutesDenied',
     'TestPostgresPaidCatalogCustomerLegacyRoutesDenied-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogCustomerLegacyRoutesDenied/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogCustomerLegacyRoutesDenied/go-stderr.log')),
)
```

`AUTHORITY` is exactly this ordered tuple, and each flag remains exact False:

```python
AUTHORITY = (
    ('fixture_verified', False),
    ('product_candidate_verified', False),
    ('staging_verified', False),
    ('deployment_authorized', False),
    ('cutover_verified', False),
    ('implementation_authorized', False),
    ('runtime_execution_authorized', False),
    ('profile_promotion_authorized', False),
    ('merge_authorized', False),
)
```

Every diagnostic has contract exact `'workshop-final180-paid-go-synthetic-v1'`, observation_kind exact `'simulated-source-profile-validation'`, accepted_case_credit exact int0, profiles_enabled exact False, enabled_tiers exact empty tuple, and AUTHORITY above. Runtime lock/run record are null in planning/report metadata and are absent from this diagnostic schema. There is no full180 result.

## 4. `translate_paid`: complete outer admission and precedence

Reject outer invalid input with the B1 AdapterError containing only the listed stable code; return no diagnostic or row prefix. Complete these stages in order before parsing or hashing any stream:

1. `context` exact PaidContext, else `context_invalid`. All three fields exact str, candidate/inventory equal pinned strings, source_manifest_sha256 matches full lowercase `[0-9a-f]{64}`, else `context_invalid`. No digest is independently authenticated by its syntax.
2. `cases` exact tuple of length12, else `cases_invalid`.
3. Visit cases in caller order: each item exact PaidCase, else `cases_invalid`; provider and go_test_name exact str and pair belongs to the twelve literal slot pairs, else `case_identity`. After this complete loop require twelve unique pairs, else `case_set`. An invalid later identity wins over an earlier duplicate because uniqueness is checked after the loop.
4. Visit all cases in caller order: events_raw exact bytes else `input_type`; len<=67108864 else `events_size`; stderr_raw exact bytes else `stderr_type`; len<=1048576 else `stderr_size`. Empty event bytes pass this outer stage but fail the parser. Empty stderr is valid. A later byte failure wins over any receipt failure because all bytes are admitted first.
5. Visit receipts in caller order: exact SimulatedExit else `receipt_invalid`. Each of the four flags exact bool. exit_code is None or exact int in inclusive[-255,255]. If None, at least one of timed_out/interrupted/ownership_lost must be True or cleanup_complete False. Any violation => `receipt_invalid`. A known exit plus any abnormal flags is admitted and interpreted additively.
6. Sum len(events_raw)+len(stderr_raw) for all twelve cases and require <=68157440, else `aggregate_size`. Per-stream/receipt errors take precedence over aggregate failure. No prefix truncation, splitting, dropping stderr or count reduction can make input fit.

After admission, index by provider/root and visit SLOTS in frozen order. SHA256 each exact byte string independently, lowercase hexadecimal. Raw refs are always the two corresponding literal labels. Translate every slot independently as sections5–8 require, then compute top status. All rows have family exact `'paid'`. No summary field, arbitrary dictionary, claimed testcase count, path, callable or partial slot is an accepted input.

## 5. `parse_paid_events`: pinned B1 grammar delegation

The function calls `parse_identity_events(raw)` directly and returns its exact tuple result, propagating B1 AdapterError unchanged. It adds no preprocessing, parser fallback, JSON repair, `splitlines()` conversion, output decoding, source import, event sorting or error wrapping. B1 public parser/type pin is recorded in section12.

B1 requires exact bytes<=67108864 and nonempty stream. It strips one optional final LF, splits on LF, and requires <=65536 lines. Each line must be nonempty and contain no CR, then be <=1048576 bytes. UTF8 and JSON must be valid; duplicate keys and nonfinite JSON constants reject. Depth is bounded to32 before JSON decoding; all JSON keys/strings must encode as UTF8 and be <=65536 bytes, including escaped strings. BOM is not repaired. Unknown keys/null values reject. Required keys are Time/Action/Package; optional keys only Test/Elapsed/Output/FailedBuild. Time is nonempty str<=128 UTF8 bytes, Package nonempty str<=256, Test if present nonempty str<=256. Time is opaque text, not authenticated or parsed chronological time. Elapsed if present is exact finite int/float (bool rejects), inclusive[0,86400]. Action is exactly start/run/output/pass/fail/skip. Output is exact str, allowed only for output and required on output. FailedBuild is allowed only on package fail, nonempty str<=1024. Start has no Test; run requires Test. Unsupported build/bench/pause/cont actions reject.

### Vocabulary order versus first-raised conflict precedence

`PARSER_CODES` is this exact ordered vocabulary for diagnostic validation/serialization, not an algorithm for selecting among simultaneous errors:

```python
PARSER_CODES = (
    'input_type', 'events_size', 'events_count', 'line_size', 'line_delimiter',
    'json_invalid', 'json_duplicate_key', 'json_nonfinite', 'json_depth',
    'json_string', 'event_keys', 'event_type', 'unsupported_go_action',
)
```

First-raised parser precedence is exactly the pinned B1 source control flow. Input type/total size precede nonempty/count admission; lines are visited in source order. Each line's delimiter check precedes size, followed by UTF8 decode, predecode depth check, JSON decoding (whose duplicate/nonfinite/invalid interactions follow the delegated decoder), recursive string checks, object/keys/value-type/action/field constraints in B1 source order. Do not scan/sort the vocabulary to select an error. Do not collect multiple parser errors. The source excerpt is embedded in section12; delegation resolves overlapping decoder errors without inventing a secondary precedence policy.

Exact regression: `b' ' * 1048576 + b'\r'` violates both delimiter and line length, and must first raise `AdapterError('line_delimiter')`. The CR-free control `b' ' * 1048577` must first raise `AdapterError('line_size')`. A direct parser call with oversized total bytes raises events_size even if those bytes contain CR. A stream with >65536 LF-delimited lines raises events_count before per-line delimiter checks. Fake tests must cover these conflicts.

## 6. Receipt codes and Go package/root lifecycle

For each admitted receipt, compute applicable receipt codes in this exact order:

1. `simulated_nonzero` if exit_code is non-None and !=0.
2. `simulated_timeout` if timed_out.
3. `simulated_interrupted` if interrupted.
4. `ownership_lost` if ownership_lost.
5. `cleanup_incomplete` if not cleanup_complete.

These are simulated caller claims; they neither execute cleanup nor prove an owned process ever existed. No timer or elapsed-field arithmetic is performed.

Parse each slot using section5. If parsing raises AdapterError, failures is exactly `(raised_code,) + receipt_codes`. Do not evaluate any lifecycle semantics or preserve a successfully parsed prefix on that slot. Other admitted slots are translated normally. No other exception is deliberately reclassified as a synthetic pass.

On successful parsing, collect semantic failures as a set, then emit in the exact SEMANTIC_CODES order below:

```python
SEMANTIC_CODES = (
    'package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',
    'root_failed', 'root_skipped', 'package_failed', 'package_skipped',
    'simulated_nonzero', 'simulated_timeout', 'simulated_interrupted',
    'ownership_lost', 'cleanup_incomplete',
)
RECEIPT_CODES = SEMANTIC_CODES[-5:]
POISON_CODES = (
    'package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',
    'root_failed', 'package_failed', 'simulated_nonzero', 'simulated_timeout',
    'ownership_lost', 'cleanup_incomplete',
)
```

Each rule applies independently; add all that apply, plus all receipt codes:

- `package_mismatch`: any parsed event.package != PACKAGE, including output/start/terminal events.
- `unknown_test`: any non-None event.test != selected slot root. No nested child, suffix, parameterization, other paid root or renamed Test is accepted. A foreign event still participates in any applicable package lifetime rule; it never becomes an extra logical row.
- Package lifetime predicate: indices of every action start event must equal `[0]`; indices of every event with test None and action pass/fail/skip must equal `[len(events)-1]`. If those hold, every package output (test None, action output) must be strictly between index0 and the package terminal. Otherwise add `package_lifecycle`.
- Root lifetime predicate: indices of root action run and root action pass/fail/skip must each have exactly one entry, with run<terminal. If those hold, require exactly one start and one package terminal and start<root run<root terminal<package terminal; every root output must be strictly between root run and terminal. Otherwise add `root_lifecycle`. This predicate does not assert package terminal is a pass: fail/skip have separate codes.
- `root_failed`/`root_skipped`: any event whose Test equals this root and action fail/skip respectively.
- `package_failed`/`package_skipped`: any event whose Test is None and action fail/skip respectively.

Foreign root fail/skip produces unknown_test, not root_failed/root_skipped; the slot still fails. A missing start plus an otherwise ordered root terminal produces both package_lifecycle and root_lifecycle. Duplicate run/terminal produces root_lifecycle. Duplicate start/package terminal produces package_lifecycle and also root_lifecycle under its exactly-one requirement. A failed or skipped root/package terminal can satisfy ordering yet remains nonpass. Output content never contributes semantic assertions or reason text. Event timestamps and Elapsed are not used to authenticate timing, ordering, ownership, payments or bank identity; array order supplies the synthetic lifetime sequence.

## 7. Row and top-status overlap rules

For each row, in this exact precedence:

1. Any failure in PARSER_CODES **or** simulated_interrupted => `'unavailable'`.
2. Else any failure in POISON_CODES => `'failed'`.
3. Else root_skipped or package_skipped => `'skipped'`.
4. Else => `'passed'`.

Top status, from exactly twelve translated rows:

1. Any row contains simulated_interrupted => `'interrupted'`.
2. Else any row.status unavailable => `'unavailable'`.
3. Else any row.status !=passed => `'inconsistent'`.
4. Else => `'consistent'`.

Required overlap expectations:

| Conditions in one slot | Row | Top when all other slots pass |
|---|---|---|
| Parser error + clean receipt | unavailable | unavailable |
| Parser error + nonzero/timeout/ownership loss/incomplete cleanup | unavailable | unavailable |
| Parser error + interruption (with any other receipt flags) | unavailable | interrupted |
| Root/package skip + nonzero/timeout/lifecycle/fail/ownership loss/incomplete cleanup | failed | inconsistent |
| Root/package skip + interruption | unavailable | interrupted |
| Root fail + package skip | failed | inconsistent |
| Any semantic poison + interruption | unavailable | interrupted |
| Only root or package skip | skipped | inconsistent |
| Clean bytes + known nonzero | failed | inconsistent |
| Clean bytes + exit None, timeout True | failed | inconsistent |
| Clean bytes + exit None, interruption True | unavailable | interrupted |
| All twelve clean bytes and receipts | passed each | consistent |

Parser error + receipt flags does not add unobserved lifecycle/skip/fail codes. Invalid outer inputs raise rather than entering this status table. Two slots with different parser errors yield two unavailable rows and top unavailable; any interrupted slot overrides that top status. No passed row earns accepted-case credit.

## 8. Diagnostic construction and strict serialization admission

Translator returns PaidDiagnostic with the constant contract/kind, context digests, top status, twelve ordered PaidOutcome rows, credit0, disabled profiles/empty tiers, and AUTHORITY. Each row uses exact literal family/ID/two refs, its two hashes and failures/status derived above. Never include raw event Output, stderr, arbitrary caller text, absolute path, XML/result summary or secret. The provider name appears only through the fixed logical ID/ref strings.

Serializer accepts only an exact PaidDiagnostic. All invalid values raise `AdapterError('diagnostic_invalid')`, with no output bytes or partial encoding returned. Check and recompute every caller-constructible claim; dataclass freezing does not make a diagnostic trusted. In order:

1. Exact diagnostic type; contract and observation_kind exact str and literal equality.
2. Exact str candidate/inventory equality and exact str lowercase64hex source_manifest digest. No source authentication is inferred.
3. accepted_case_credit exact int and ==0; profiles_enabled is False; enabled_tiers exact tuple and ==(). bool credit rejects.
4. authority exact tuple length9. Each corresponding pair exact tuple length2, key exact str matching same-index AUTHORITY key, value is False. Reject wrong/duplicate/missing/extra/reordered keys, truthy/falsey replacements and dictionaries.
5. observations exact tuple length12. Visit with corresponding literal slot in fixed order. Each row exact PaidOutcome. family/logical_id exact str equal to `'paid'` and slot ID. raw_refs exact tuple length2 with each exact str matching the slot's two refs in order. Both digest fields exact str full lowercase64hex.
6. row.failures exact tuple, length<=len(PARSER_CODES+SEMANTIC_CODES), each item exact str belonging to that concatenated vocabulary, no duplicates. Order must equal sorting by position in PARSER_CODES+SEMANTIC_CODES. At most one parser code. If a parser code exists, it is first and every later code must belong to RECEIPT_CODES; no parser+semantic-lifecycle mixture. If none, only SEMANTIC_CODES appear in semantic order. Empty tuple allowed. Do not invent consistency relationships beyond this vocabulary/lifecycle-independent admission: without raw bytes the serializer cannot reprove which semantic failures occurred.
7. row.status exact str equal to recomputed section7 row status from admitted failures.
8. diagnostic.status exact str equal to recomputed top status from all twelve admitted rows/failures.
9. Build the exact JSON object below, using only revalidated values; `json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)`, append one LF, encode UTF8, require len<=65536. An exceeded bound raises diagnostic_invalid; never truncate or omit rows. No additional keys.

Top-level JSON keys are exactly: `contract`, `observation_kind`, `candidate_sha`, `inventory_sha256`, `source_manifest_sha256`, `status`, `observations`, `accepted_case_credit`, `profiles_enabled`, `enabled_tiers`, `authority`. Authority becomes an object with the exact nine keys and false values; enabled_tiers becomes `[]`. Each observation object has exactly `family`, `logical_id`, `status`, `raw_refs`, `events_sha256`, `stderr_sha256`, `failures`; tuples become arrays. JSON key sort order controls bytes, independent of authority tuple validation order. No runtime_lock/run_record field, raw source content, count/summary, extra proof or verification boolean is added.

Serializer admission does not rerun parsing, prove hash-to-byte correspondence or authenticate process receipts. Caller-constructed consistent diagnostic values remain synthetic claims; this strict serializer prevents schema/authority mutation, not fabrication of genuine evidence.

## 9. Source-observed producer, JUnit support and financial boundary

Candidate collector fixes six GO_NAMES paired bankone then banktwo. Each child runs `go test -json -count=1 -timeout=90s -run ^<root>$ .` in apps/api-go. Source `go_valid` checks nonempty events, no fail/skip, no foreign Test, one root run/pass, one package pass and final package pass; it does not enforce the stronger exact Package/full package-start/output lifetimes above. This synthetic adapter intentionally applies the existing restricted B1/B2 profile. Actual Go runtime compatibility is unobserved.

Outer JUnit requires exactly twelve names `test_required_paid_catalog_access[<literal-id>]`, classname `tests.test_paid_catalog_api_integration`, without failure/error/skipped. Each outer case launches one duplicate child JUnit case. JUnit/support/package events/migrations add zero final180 IDs. No JUnit grammar is implemented here and precise installed pytest/plugin emission remains unobserved.

The source-observed minimum paid raw inventory has344 refs: eight shared paid-level files plus28 per slot. Full literal refs and common support inventory are in literal-mappings.json, whose hash is pinned in the accompanying source-check artifact. Go pairs here are only24 of those refs, retained as labels for supplied bytes. Collector also depends on exact result/provider/root/candidate/provenance equality, assertion keys, clean exits/timeouts, per-file hash inventories, all001–040 migration replay evidence and measured runtime/probes/worker exits. Neither event translation nor claimed summaries independently validates those facts.

Go setup reads provider and candidate strings from environment. Go measurement exports phases/assertions/views/HTTP/counters/held receipt without mandatory provider/candidate identity. Identical bytes in bankone/banktwo slots are allowed. Only future independently admitted path/process/environment/manifest/receipt/result/JUnit binding can establish which bank run produced which bytes.

PaidBridge instantiates deterministic in-process StripeFixture. More decisively, Go `grant` directly inserts a paid workshop order (fixture amount2000/USD), purchased request, active entitlement and projection in a DB transaction. `payment_grants_persist` checks payment_calls==0 and two entitlements. These are seeded fixture access rights, not charges/settlements or real Stripe TEST/LIVE transactions. No webhook authenticity, owner-bound settlement, funds movement, refunds/chargebacks or other payment behavior is inferred. Commerce14 is separate and grants no transitive authority.

## 10. Required adversarial constructed-test matrix

All tests are future offline unittest cases with independently written literal expected roots/IDs/refs and constructed bytes/receipts; no candidate/test producer imports or captured evidence. Begin with missing-module failing tests only after a new gate. Test expected result values, not private helpers or a duplicate implementation algorithm. At minimum:

| Area | Required positive and negative cases |
|---|---|
| Public surface | Exact frozen dataclass fields/order; exact imported B1 types; no CLI/import side effects; allowed imports/AST scope. |
| Literal set/order | Twelve exact pairs, permuted caller order still frozen output; each slot missing/duplicate/replaced with foreign root/provider; partial tuple,13 slots,list,subclass item; later invalid identity plus earlier duplicate checks case_identity before case_set. |
| Context | Wrong candidate/inventory, wrong primitive/subclass, malformed/uppercase/short digest, unknown dict/context type; no source admission inferred from valid syntax. |
| Outer byte precedence | Wrong event/stderr types, event/stderr limit and limit+1; empty stderr; later bad bytes versus earlier bad receipt; per-stream violation versus aggregate; invalid receipt versus aggregate. |
| Receipt types | bool exit, float/str/out-of-range exit, all bool-flag violations/subclasses, None clean rejects; None with each abnormal flag admitted; known zero/nonzero with all abnormal flag combinations. |
| Parser baseline | Minimal package start/root run/root pass/package pass; optional final LF/no final LF; bounded output fields; direct wrapper returns same GoEvent tuple semantics; no dynamic output case creation. |
| Parser grammar | All B1 parser codes; duplicate keys/nonfinite/depth/long strings/surrogates/BOM/invalid UTF8/null/unknown keys/bool Elapsed/negative/too-large/nonfinite Elapsed/empty names/bad optional fields/unsupported actions. |
| Parser bounds/conflicts | Total event bytes at/beyond64MiB;65536/65537 lines;1MiB/1MiB+1 line; empty lines/CRLF/two final LFs. Exact overlap b' '*1048576+b'\r' =>line_delimiter; CR-free b' '*1048577 =>line_size. events_size beats CR at oversized total; events_count beats per-line delimiter at excess lines. Direct wrapper and per-slot translation preserve first-raised code. |
| Package lifetime | Missing/duplicate/late start; missing/duplicate/nonfinal package terminal; package output before/after lifetime; foreign Package in each event role; pass/fail/skip ordering; root outside package lifetime. |
| Root lifetime | For each of12 slots independently missing/duplicate/reversed run or terminal, root output outside lifetime; no root; root skip/fail; other root/child/suffix/parameterized Test; foreign fail produces unknown_test rather than root_failed. |
| Raw trust | Same root's bank slots accept identical event/stderr bytes; raw refs literal; arbitrary Output claims passed=true/authority/path/provider/payment never change IDs/statuses or leak; stderr arbitrary bytes hashed only. |
| Independent rows | Malformed/failing/skipped slot affects that row while other valid rows remain passed; two parser errors; interrupted slot plus another parser error; no parsed-prefix acceptance. |
| Additive/status overlaps | Every section7 overlap row; parser failure plus all receipt flags, skip plus poison, fail plus skip, lifecycle plus interruption; ordered unique code tuples and top precedence; invalid outer input raises instead of producing a diagnostic. |
| Aggregate bound | Exact68157440 total admitted with per-stream limits respected, total+1 rejects; twelve slots still required and no omitted stderr. Large valid output fixture can be constructed within parser line/string/count bounds; byte-only tests may separately expect a downstream parser rejection after outer admission. |
| Serializer schema/types | Every field mutated one at a time, subclasses/wrong primitives, bool credit, reordered/missing/extra/duplicate rows, wrong family/ID/refs/digests/contracts/kinds; unknown/duplicate/reordered codes, two parser codes, parser+nonreceipt semantic, code/status mismatch, wrong top status. |
| Serializer authority | Each of9 flags set True independently; omitted/extra/reordered/duplicate keys, bool-like values, dict instead of tuple; nonempty tiers/profiles True; no credits/authority can be serialized. |
| Serializer bytes | Deterministic byte equality, sorted compact ASCII JSON with trailing LF, exact top/row key sets, no raw Output/stderr/extraneous fields, <=65536 bytes; mutated caller diagnostic still revalidated; no authenticity inferred from serialization. |
| Preservation | Stage A/B1/B2 baseline tests; byte-for-byte predecessor pins and exact three-path allowlist/diff checks; developer/autonomy checks under then-reviewed CI policy; no runtime launch to repair environment failures. |

The specific overlap b' '*1048576+b'\r', clean receipt and empty stderr produces only `('line_delimiter',)` in its slot, row unavailable and top unavailable if other slots pass. Adding interruption yields `('line_delimiter','simulated_interrupted')`, row unavailable/top interrupted; adding nonzero/timeout alone preserves unavailable top. All still credit0/all authority false.

Minimal positive stream for each slot: compact JSON objects with bounded Time='2026-11-04T00:00:00Z', exact Package, actions start(no Test), run(root), pass(root), pass(no Test), optional trailing LF. Receipt SimulatedExit(0,False,False,False,True), empty stderr. Exactly twelve passed observations, top consistent, zero credit. This is a constructed recipe, never captured evidence.

## 11. Full raw/real acceptance remains blocked

A complete paid validator needs a separate decision-complete gate translating every source assertion and admitting sufficient evidence. Concrete blockers are:

- Authentic candidate/bank/process/path/environment/result/JUnit/manifest/receipt binding, admitted real exits/owned cleanup, actual tool/runtime compatibility and fresh run identity are absent.
- 344 paths are source-observed minimums, not a complete typed/bounded profile including LifecycleRuntime dynamic/failure/support artifacts. Installed versions and exact JUnit/plugin emission are unobserved.
- Applied PostgreSQL schema/settings/rows, exact001–040 migration hashes and fresh/empty/populated replay invariants need admitted observations and nested JSONB/constraint semantics. Corrected addendum row shapes are static source knowledge.
- HTTP records hash original bodies before redaction, redact contextual tokens, truncate text above256KiB, omit binary bytes and retain selected headers. Hashes cannot reconstruct tokens/media/body semantics. Concurrent append/counter ordering does not prove total execution order.
- Independent validation needs sufficient evidence for canonical-step DB comparisons, intermediate revocation/account/session/rights transitions, historical token/source binding, invalid media mutations, real S3 image validation, source sanitization/no-leak assertions and held-model response/release semantics. Event/status/summary flags alone do not supply that evidence.
- Paid grants are seeded and payment calls deliberately zero. No real charge/settlement/payment service outcome follows. Broader financial evidence requires its own design, source semantics and authorization.
- No registered trusted raw-reviewer/profile, promoted assembler/tooling binding, immutable image/tool/cache manifests, run-owned isolation/cleanup, storage/headroom/retention or authorized runtime lock/run record exists for this paid proposal.
- Concurrent CI/commerce/runbook work requires coordinator integration and exact fresh dependency comparison; this proposal cannot modify or borrow unreviewed implementation.

All nine authority flags false, accepted credit exact integer0, profiles disabled, enabled tiers empty, runtime_lock=null and run_record=null remain invariant in planning/report metadata. Unit success or a consistent synthetic diagnostic cannot authorize execution, grant fixture/product credit, promote profiles, merge, deploy or cut over.

## 12. Exact source pins and parser/control-flow citations

The following pin records are immutable source/context evidence; embedded historical status text is not current tracking readback. All82 inventory candidate pins and all62 corrected-addendum candidate pins were compared to local Git objects without importing repository modules. Full literal IDs/minimum raw inventory remain in the accompanying mappings, not runtime expectations regenerated from candidate source. The corrected addendum itself explicitly leaves runtime and complete nested semantics unknown.

### Direct Git source pins

```json
[
  {
    "bytes": 7639,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "5eefbd805df73c000b7b690b035448deac8c9152",
    "path": "scripts/dev/workshop_paid_access_smoke.py",
    "sha256": "1acaa6bffaf35b122b40757c78dbf01fb06244803720c951b2b828133232632f"
  },
  {
    "bytes": 19378,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "d4d8b6d26ead3023dbbe5084d1376c0009404aae",
    "path": "workers/ingestion-python/tests/test_paid_catalog_api_integration.py",
    "sha256": "efd3098953dde54d3fc38c167db1f56ab97225c185fb73f032fe7f3289b70198"
  },
  {
    "bytes": 40990,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "ba19bac67d5474cd975a1ee8fbde89a812c173c3",
    "path": "apps/api-go/postgres_catalog_access_test.go",
    "sha256": "0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31"
  },
  {
    "bytes": 31526,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "fdccc37c1d13394ecb634c17ef12614b6fc9ac76",
    "path": "workers/ingestion-python/tests/test_commerce_postgres.py",
    "sha256": "fbab00f576410393e5077351d08d108c884d4a6442549fc4192647796e19904e"
  },
  {
    "bytes": 10161,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "f427f03d77d4346e8f112430a1fdf29bcc3d987a",
    "path": "workers/ingestion-python/src/autodata_ingestion/stripe_adapter.py",
    "sha256": "bc99786ce246267109aeedbfa360d2fbbb4ae94e924f87387b76df9e40a3b047"
  },
  {
    "bytes": 40887,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "cd505e4c452331dab924ee81fe7fb729842935d4",
    "path": "workers/ingestion-python/src/autodata_ingestion/commerce_service.py",
    "sha256": "ec32793162c6a4cb1fdfe136502e2ada8b38bf59d63a2fffc58b527031c35490"
  },
  {
    "bytes": 30980,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "5b16ff5b5428547fcdeb09fb63c36c94a406ff6c",
    "path": "workers/ingestion-python/tests/test_catalog_api_integration.py",
    "sha256": "88e6c1fd339da60614056abd7689b6a7fcd1d16bc1e239cec888b06bb6a61974"
  },
  {
    "bytes": 19309,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "ac52c479e5e4a7f625cddd409d8d61573c271765",
    "path": "workers/ingestion-python/tests/lifecycle_support.py",
    "sha256": "746eba57bfffb760e2f779d0d0494125f8b559b07de5ff6ec11099d517bf76dc"
  },
  {
    "bytes": 3986,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "16982a9310be7447103e2bfacecf9f7cb764704e",
    "path": "apps/api-go/go.mod",
    "sha256": "3306c3736c51a3c08a4ed30613a9f0ba4db7f5094d0215ebdf54545873012923"
  },
  {
    "bytes": 12585,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "24a8445d9a09ae3dc45236aaeed84cd755015fd8",
    "path": "apps/api-go/catalog_access.go",
    "sha256": "86709a7e68543a8980e9eaaf934e08361da3488c0c2c23a6ff3219c13569bfa3"
  },
  {
    "bytes": 10171,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "c303616180ef121829f43b49c0ca0c792297cce1",
    "path": "apps/api-go/catalog_media_access.go",
    "sha256": "6972bb76081f0eea9184b1180799cd1d20becced9e366d8657a925e491d5fb80"
  },
  {
    "bytes": 17225,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "a6151a0d393a87e4c04d082daf92328dece85d1a",
    "path": "apps/api-go/catalog_http.go",
    "sha256": "8bf65ff6b6cfab52b8b42c4d6473e75220c19363a04ae97b103c08edf8ecab50"
  },
  {
    "bytes": 17076,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "abf37527d3206552bea8979fd5b618c42050c9ef",
    "path": "apps/api-go/catalog_source.go",
    "sha256": "6d18e7f57a4c7016585bd8838a5e2a3ebc092d7a77d1812cf4b749be810423f2"
  },
  {
    "bytes": 4956,
    "commit": "4d82e413e04fb2401ac7bc28dc828375ac662180",
    "git_blob": "18ec48100cdbb7ebbd226e97eba05ad42cfbc341",
    "path": "db/migrations/040_workshop_commerce.sql",
    "sha256": "7ff3203b5c980bf7fe688470ef737f0d29789ff9c5f04b9744257d0715cb695e"
  },
  {
    "bytes": 122350,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "24ac3e9264b85eb914daa7805d183e15f58d374a",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.json",
    "sha256": "c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39"
  },
  {
    "bytes": 10852,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "97a3ee48e443547f538e369ebd4557644e9fec3c",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.md",
    "sha256": "55fc12a771576778fb652ea8fcc3e8b81492ff3abc6fef0f00cc7fa3b015037a"
  },
  {
    "bytes": 33663,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "c0948a5b604b9ae5f0ce31ab2e7864cbc9b8d527",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-runner.md",
    "sha256": "24d209a60ae2dcda461d1a65932c2dd37d6894ed7a9c3920f989fe8ff0b20ba3"
  },
  {
    "bytes": 7888,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "c8617fee8e43d27f80ca29c6f1a9ddae6ac79ed2",
    "path": "docs/superpowers/plans/2026-11-04-workshop-final180-runner.md",
    "sha256": "6d1d5f4e8da9310669419703b298eeb17cd7c14a5e3719ea416cf5b1145ebaa9"
  },
  {
    "bytes": 82081,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "4a29e0915c677a2f07e3ca6b0ab9109e888651d1",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-stage-b1-identity.md",
    "sha256": "285e5abfe824b4b9490af8e4b2fa3655f53ea34d8afc631e69a88feb909d242a"
  },
  {
    "bytes": 13657,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "8979973a5124d4f3f7a439dba31ca8104e488971",
    "path": "docs/superpowers/plans/2026-11-04-workshop-final180-stage-b1-identity.md",
    "sha256": "02f92b355c5dcd3144f1ec80c21118a86a9624b466dfa756a6795edd13fa21ca"
  },
  {
    "bytes": 73739,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "584b12c2b880ae328ab39da73753a6f0e4a7a8ba",
    "path": "docs/agents/specs/2026-11-04-workshop-final180-stage-b2-catalog-go.md",
    "sha256": "c8e9a3f4c663fcc9e43bab3ef84e9e8dd978a4d29fa75122acf9372e5e22cb7b"
  },
  {
    "bytes": 50477,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "5d79004dca6add657533ef6883895c7698adb988",
    "path": "docs/superpowers/plans/2026-11-04-workshop-final180-stage-b2-catalog-go.md",
    "sha256": "0b2899864f1964e50b4e5ca7f7d70d48331c3f1f1aad6898b8d2f7eb83b9889f"
  },
  {
    "bytes": 47124,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "ca48cd988c5579a7d385dc1844b84306eae0861e",
    "path": "scripts/dev/workshop_final180_runner.py",
    "sha256": "693a408a73f3ccd37bf945bfc94d427f742878580932dab382ea9a244a141c91"
  },
  {
    "bytes": 22290,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "8c7fa87bab906955c145d7cc965be641aea48c5f",
    "path": "scripts/dev/workshop_final180_identity_adapter.py",
    "sha256": "0474a85c33d4f2722ad01d6e55e69a8080dc0f1983c856ca7caa1b94510a767d"
  },
  {
    "bytes": 15467,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "060d1407ee5e71880cf7e441195cac4274f04937",
    "path": "scripts/dev/workshop_final180_catalog_adapter.py",
    "sha256": "88f481104d66d9bda8bdf6c1a8038e8514b69d63db813b85c5ec13e40f0c6ddf"
  },
  {
    "bytes": 29838,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "7391263cb874e2505f4f110df6343c8b466fc692",
    "path": "scripts/dev/test_workshop_final180_identity_adapter.py",
    "sha256": "a3f3017b1d7a85da9ae4d1883758f2494d722fb321d45c1ff758994ab6d2653c"
  },
  {
    "bytes": 26977,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "86e78aef564c216ede5780dccadd56366d4d0a63",
    "path": "scripts/dev/test_workshop_final180_catalog_adapter.py",
    "sha256": "978cbb594d9bc42f0cb02b3447e2afed6bb6764c155b657db6e5b3676cc319a9"
  },
  {
    "bytes": 18423,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "5812377b4e1a1bd9f992f116cdd11e73c7168393",
    "path": "docs/verification/workshop-final180-runbook.md",
    "sha256": "23023c638cd94dd46ff7722d80a5f28a1e3e6ad2c82f417ac6485d46cabeef03"
  },
  {
    "bytes": 5659,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "41076af1db25f0cff8ca41d0203c050af9b772df",
    "path": "docs/agents/pre-implementation-gate.md",
    "sha256": "fa6e9c95c2674164c90d78e046a0427f6b406c313fb82ff627a2a2facb560ad0"
  },
  {
    "bytes": 3325,
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "git_blob": "5600feb6b56ec443bbe0b024f7f5985d87d68492",
    "path": "AGENTS.md",
    "sha256": "1fab197e77c2ac65a009d93fe7ab0ba200077cda371a079885ceaa594fcc92db"
  },
  {
    "bytes": 17531,
    "commit": "8bc9371a2715f34f06f261c8abae4194be2e1ea0",
    "git_blob": "008838ca55d242aeae03bb49d9d8ee5316656ad5",
    "path": "docs/superpowers/plans/2026-11-04-workshop-final180-ci-integration.md",
    "sha256": "c8026d2baec9894a7f50b55bad62800182d8a4be6d1795f5c7a51a673b3ee937"
  }
]
```

### Corrected external addendum pins

```json
[
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
    "bytes": 3597,
    "path": "/home/corp/autodata-evidence/final180-stage-b-gap-closure/report.json",
    "sha256": "36670a61779baa5ec2dd40d879b485c32d2a41907e1f971507ad450ca1a679ae"
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
```

### scripts/dev/workshop_paid_access_smoke.py:13–42

six roots, twelve ordered provider IDs, assertion keys, Go and JUnit collector rules. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `5eefbd805df73c000b7b690b035448deac8c9152`; file SHA256 `1acaa6bffaf35b122b40757c78dbf01fb06244803720c951b2b828133232632f`; excerpt SHA256 `488a0c8cdc5f5422e4a2e7382cbfba2c8be102c27dda3042a2d166344e42874b`.

```python

GO_NAMES=(
 'TestPostgresPaidCatalogGrantBeforeWork',
 'TestPostgresPaidCatalogExactScopeAndOwnerIsolation',
 'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse',
 'TestPostgresPaidCatalogContextualMediaAndRevocation',
 'TestPostgresPaidCatalogHistoricalSourceAndRights',
 'TestPostgresPaidCatalogCustomerLegacyRoutesDenied')
CASE_IDS=tuple(name+'-'+provider for name in GO_NAMES for provider in ('bankone','banktwo'))
CASE_ASSERTIONS=dict(zip(GO_NAMES,(
 ('public_selectors_metadata_only','unpaid_denied_before_work','expired_session_denied_before_work','paid_gets_observational','unavailable_grant_denied_before_work'),
 ('exact_scope_grants','owner_region_configuration_isolation','canonical_only','revoked_and_legacy_denied'),
 ('explicit_prepare_only','shared_article_job','actual_model_response_held','source_readable_during_hold','canonical_reused_two_owners','canonical_steps_preserved','payment_grants_persist'),
 ('actual_s3_reader','invalid_media_zero_reader','current_grant_identity_rechecked','stale_context_zero_reader','media_security_headers'),
 ('source_html_json_media','historical_source_selected','rights_denied_before_reader','source_sanitizer_no_private_leak'),
 ('thirteen_routes_denied_before_work','unauthenticated_401','explicit_local_compatibility'))))
MIGRATION_ASSERTIONS=('fresh_manifest_applied_001_040','empty_replay_noop_001_040','populated_replay_noop_001_040')
RAW_FILES=('workshop-paid-access-tests.xml','workshop-paid-access-pytest.stdout.log','workshop-paid-access-pytest.stderr.log','runner-input-before.json','runner-input-after.json','runner-git-before.json','runner-git-after.json')

def go_valid(events,name):
    if not events or any(e.get('Action') in {'skip','fail'} or (e.get('Test') is not None and e['Test']!=name) for e in events):return False
    actions=[e.get('Action') for e in events if e.get('Test')==name]
    packages=[e.get('Action') for e in events if 'Test' not in e]
    return actions.count('run')==actions.count('pass')==1 and packages.count('pass')==1 and events[-1].get('Action')=='pass' and 'Test' not in events[-1]

def junit_valid(path):
    try:
        cases=ET.parse(path).getroot().findall('.//testcase')
        names=[c.get('name') for c in cases]
        expected=['test_required_paid_catalog_access['+case+']' for case in CASE_IDS]
```

### scripts/dev/workshop_paid_access_smoke.py:44–96

collector result claims, outer pytest command and raw hash checks. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `5eefbd805df73c000b7b690b035448deac8c9152`; file SHA256 `1acaa6bffaf35b122b40757c78dbf01fb06244803720c951b2b828133232632f`; excerpt SHA256 `53e9b8f31f44c96f2425a96045478345e647217def101525772e5abd0041e4e0`.

```python
            and all(c.get('classname')=='tests.test_paid_catalog_api_integration' and not any(c.find(tag) is not None for tag in ('skipped','failure','error')) for c in cases))
    except (OSError,ET.ParseError):return False

def success(code,timed_out,flags):
    return code==0 and not timed_out and set(flags)==set(CASE_IDS) and all(v is True for v in flags.values())

def collect(candidate,output):
    started=now();flags={case:False for case in CASE_IDS};failures=[];provenance={};code=-1;timed_out=False;case_results={}
    try:
        if os.getenv('AUTODATA_LIFECYCLE_TEST')!='1' or not re.fullmatch('[a-f0-9]{40}',candidate):raise RuntimeError('explicit lifecycle fixture and exact candidate required')
        os.environ['AUTODATA_R3_CANDIDATE_SHA']=candidate
        provenance=check_inputs('before')
        allowed=('PATH','PYTHONPATH','PYTHONDONTWRITEBYTECODE','AUTODATA_LIFECYCLE_TEST','AUTODATA_R3_CANDIDATE_SHA','GOTOOLCHAIN','GOPROXY','GOFLAGS','CGO_ENABLED','GOMODCACHE','GOCACHE','GOTMPDIR')
        env={key:os.environ[key] for key in allowed if key in os.environ}
        env.update(AUTODATA_CATALOG_INTEGRATION_REQUIRED='1',AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION='1',PYTHONDONTWRITEBYTECODE='1')
        command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider','--junitxml='+str(ARTIFACTS/'workshop-paid-access-tests.xml'),'workers/ingestion-python/tests/test_paid_catalog_api_integration.py']
        with (ARTIFACTS/'workshop-paid-access-pytest.stdout.log').open('wb') as stdout,(ARTIFACTS/'workshop-paid-access-pytest.stderr.log').open('wb') as stderr:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
            try:code=process.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                timed_out=True;os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)
                code=process.returncode
        after=check_inputs('after')
        if any(provenance[k]!=after[k] for k in ('candidate_sha','candidate_origin','host_before_sha256','input_manifest_sha256')):raise RuntimeError('candidate provenance changed')
        if not junit_valid(ARTIFACTS/'workshop-paid-access-tests.xml'):failures.append('required exact twelve-case JUnit inventory failed')
        for name in GO_NAMES:
            for provider in ('bankone','banktwo'):
                case=name+'-'+provider;directory=ARTIFACTS/'paid-access'/provider/name
                result=json.loads((directory/'result.json').read_text());case_results[case]=result
                keys=set(CASE_ASSERTIONS[name]+MIGRATION_ASSERTIONS)
                events=[json.loads(line) for line in (directory/'go-events.jsonl').read_text().splitlines()]
                valid=(result['candidate_sha']==candidate and all(result.get(key)==provenance[key] for key in ('candidate_origin','host_before_sha256','input_manifest_sha256')) and result['provider']==provider and result['go_test_name']==name
                    and result['go_exit_code']==0 and result['timed_out'] is False and result['passed'] is True and result['failures']==[]
                    and set(result['assertion_results'])==keys and all(v is True for v in result['assertion_results'].values()) and go_valid(events,name))
                inventory={p.name:digest(p.read_bytes()) for p in directory.iterdir() if p.is_file() and p.name!='result.json'}
                flags[case]=valid and inventory==result['artifact_sha256']
    except Exception as error:failures.append(type(error).__name__+': '+str(error))
    hashes={}
    for name in RAW_FILES:
        path=ARTIFACTS/name
        if path.is_file():path.chmod(0o644);hashes[name]=digest(path.read_bytes())
        else:failures.append('missing artifact: '+name)
    failures.extend('failed case: '+case for case,value in flags.items() if not value)
    if code!=0:failures.append('required pytest exit: '+str(code))
    passed=success(code,timed_out,flags) and not failures
    result=dict(provenance,schema_version=1,candidate_sha=candidate,candidate_origin='coordinator-host-plain-clone',started_at=started,finished_at=now(),pytest_exit_code=code,timed_out=timed_out,pytest_test_count=12 if junit_valid(ARTIFACTS/'workshop-paid-access-tests.xml') else 0,case_results=case_results,assertion_results=flags,passed=passed,failures=failures,artifact_sha256=hashes)
    write_json(output,result);return 0 if passed else 1

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['fixture'],required=True);parser.add_argument('--candidate-sha',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();return collect(args.candidate_sha,args.output)
if __name__=='__main__':raise SystemExit(main())
```

### workers/ingestion-python/tests/test_paid_catalog_api_integration.py:29–38

PaidBridge uses in-process StripeFixture. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `d4d8b6d26ead3023dbbe5084d1376c0009404aae`; file SHA256 `efd3098953dde54d3fc38c167db1f56ab97225c185fb73f032fe7f3289b70198`; excerpt SHA256 `de29f5de29fa18ecec6e4aa359a0b085b5e621da4be73fb22a012e2abc2e2b5b`.

```python
if not REQUIRED:pytestmark=pytest.mark.skip(reason='explicit paid catalog fixture acceptance only')


class PaidBridge(Bridge):
    def __init__(self,runtime):
        super().__init__(runtime,R3_NAMES[1])
        from autodata_ingestion.commerce_service import CommerceService,CommerceConfig
        from test_commerce_postgres import StripeFixture
        self.payment=StripeFixture()
        self.commerce=CommerceService(runtime.repo.connect,CommerceConfig('stripe_test','acct_fixture','price_fixture'),self.payment.provider)
```

### workers/ingestion-python/tests/test_paid_catalog_api_integration.py:86–96

paid rows and payment call count snapshot. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `d4d8b6d26ead3023dbbe5084d1376c0009404aae`; file SHA256 `efd3098953dde54d3fc38c167db1f56ab97225c185fb73f032fe7f3289b70198`; excerpt SHA256 `b2fc860af36bc028351dc4d00543466ae7bd24688b1f064b4e5825a214f4535d`.

```python
    def snapshot(self):
        result=super().snapshot()
        with self.lock:
            result['grant_calls']=len(self.grant_calls)
            result['selector_ensure']=dict(self.selector_ensure)
            result['selector_ensure_requests']=json.loads(json.dumps(self.selector_ensure_requests))
        with self.runtime.repo.connect() as conn:
            result['paid_rows']={table:[r['record'] for r in conn.execute('SELECT to_jsonb(t) AS record FROM '+table+' t ORDER BY to_jsonb(t)::text')]
                for table in ('customer_accounts','auth_sessions','entitlements','workshop_orders','dataset_requests','dataset_projections')}
        result['payment_calls']=len(self.payment.calls)
        return result
```

### workers/ingestion-python/tests/test_paid_catalog_api_integration.py:156–231

per-case identities, commands and Go measurement/run/migration requirements. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `d4d8b6d26ead3023dbbe5084d1376c0009404aae`; file SHA256 `efd3098953dde54d3fc38c167db1f56ab97225c185fb73f032fe7f3289b70198`; excerpt SHA256 `6927e3a7508226383284e4727de2bcc66c53837d1080ff49b603b0cc5019c4ac`.

```python
def child_case(go_name,provider,fresh_database,monkeypatch,directory):
    deadline=time.monotonic()+110
    candidate=os.environ['AUTODATA_R3_CANDIDATE_SHA']
    result=dict(schema_version=1,provider=provider,go_test_name=go_name,candidate_sha=candidate,
        candidate_origin='coordinator-host-plain-clone',host_before_sha256=digest((ARTIFACTS/'host-before.json').read_bytes()),
        input_manifest_sha256=digest((ARTIFACTS/'inputs.sha256.json').read_bytes()),started_at=now(),go_exit_code=-1,timed_out=False,
        phase_snapshots={},assertion_results={},passed=False,failures=[])
    runtime=bridge=None
    try:
        repo=fresh_database(through=0);result['fixture_database']=repo.database_name
        manifest=[p.name for p in sorted((ROOT/'db/migrations').glob('*.sql'))]
        assert len(manifest)==40 and manifest[-1]=='040_workshop_commerce.sql'
        emitted=subprocess.run(['sh',str(ROOT/'scripts/dev/migrate_sql.sh'),'--emit'],cwd=ROOT,capture_output=True,timeout=10,check=False)
        (directory/'migration-driver.sql').write_bytes(emitted.stdout);(directory/'migration-driver.stderr').write_bytes(emitted.stderr);assert emitted.returncode==0
        migrations=dict(manifest=manifest,driver_sha256=digest(emitted.stdout),driver_exit_code=0,runner_sha256=digest((ROOT/'scripts/dev/migrate_sql.sh').read_bytes()))
        migrations['fresh'],empty=run_migrations(repo,directory,'fresh',manifest)
        migrations['empty_replay'],_=run_migrations(repo,directory,'replay-empty',manifest,empty)
        with ExitStack() as stack:
            runtime=LifecycleRuntime(repo,stack)
            scope=configure_scoped_runtime(runtime,provider)
            bridge=PaidBridge(runtime)
            model_url=stack.enter_context(serve(bridge.model_handler()));runtime.env['INCEPTION_API_BASE_URL']=model_url+'/v1';runtime.env['INCEPTION_API_TIMEOUT_SECONDS']='60'
            for key,value in runtime.env.items():monkeypatch.setenv(key,value)
            ensure_url=stack.enter_context(serve(bridge.ensure_handler()));control_url=stack.enter_context(serve(bridge.control_handler()))
            service_probes=probes(runtime)
            allowed=('PATH','GOTOOLCHAIN','GOPROXY','GOFLAGS','CGO_ENABLED','GOMODCACHE','GOCACHE','GOTMPDIR')
            env={key:os.environ[key] for key in allowed if key in os.environ}
            assert env['GOTOOLCHAIN']=='local' and env['GOPROXY']=='off'
            for key in ('GOCACHE','GOTMPDIR'):Path(env[key]).mkdir(parents=True,exist_ok=True)
            env.update(AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION='1',AUTODATA_CATALOG_INTEGRATION_REQUIRED='1',AUTODATA_LIFECYCLE_TEST='1',
                AUTODATA_CATALOG_TEST_DSN=f'postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{repo.database_name}?sslmode=disable',
                AUTODATA_CATALOG_TEST_ENSURE_URL=ensure_url,AUTODATA_CATALOG_TEST_CONTROL_URL=control_url,AUTODATA_CATALOG_TEST_CONTROL_TOKEN=bridge.token,
                AUTODATA_CATALOG_TEST_VEHICLE_ID=str(runtime.vehicle),AUTODATA_CATALOG_TEST_ARTICLE_ID=str(runtime.article_id),
                AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID=str(runtime.articles['banktwo' if provider=='bankone' else 'bankone']),
                AUTODATA_CATALOG_TEST_PROVIDER=provider,AUTODATA_CATALOG_TEST_CANDIDATE_SHA=candidate,AUTODATA_CATALOG_TEST_CASE_DIR=str(directory),
                AUTODATA_PAID_TEST_CONFIGURATION_ID=scope['configuration'],AUTODATA_PAID_TEST_ADJACENT_CONFIGURATION_ID=scope['adjacent'],
                AUTODATA_PAID_TEST_REGION_CONFIGURATION_ID=scope['other_region'],AUTODATA_PAID_TEST_UNSCOPED_ARTICLE_ID=scope['unscoped'],
                AUTODATA_S3_ENDPOINT='minio:9000',AUTODATA_S3_ACCESS_KEY='fixture',AUTODATA_S3_SECRET_KEY='fixture',AUTODATA_SOURCE_BUCKET=runtime.bucket)
            argv=['go','test','-json','-count=1','-timeout=90s','-run','^'+go_name+'$','.']
            write_json(directory/'go-command.json',dict(argv=argv,cwd=str(ROOT/'apps/api-go')))
            with (directory/'go-events.jsonl').open('wb') as stdout,(directory/'go-stderr.log').open('wb') as stderr:
                # Outer case owns the process group and the whole120s boundary.
                process=subprocess.Popen(argv,cwd=ROOT/'apps/api-go',env=env,stdout=stdout,stderr=stderr)
                try:result['go_exit_code']=process.wait(timeout=max(1,min(90,deadline-time.monotonic()-12)))
                except subprocess.TimeoutExpired:
                    result['timed_out']=True;process.terminate()
                    try:process.wait(timeout=2)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
                    result['go_exit_code']=process.returncode;raise
            measurement=json.loads((directory/'go-measurement.json').read_text())
            result['phase_snapshots']=measurement['phase_snapshots'];result['assertion_results']=measurement['assertion_results']
            assert result['go_exit_code']==0,(directory/'go-events.jsonl').read_text()+(directory/'go-stderr.log').read_text()
            events=[json.loads(line) for line in (directory/'go-events.jsonl').read_text().splitlines()];assert go_valid(events,go_name)
            assert set(result['assertion_results'])==set(CASE_ASSERTIONS[go_name]) and all(v is True for v in result['assertion_results'].values())
            final=bridge.snapshot();assert not final['proxy']['errors'] and final['ensure']['active']==0
            exits=bridge.stop()
            before,schema=migration_snapshot(repo,migration_env(repo));(directory/'populated-before.schema.sql').write_bytes(schema);write_json(directory/'populated-before.rows.json',before['rows'])
            migrations['populated_replay'],_=run_migrations(repo,directory,'replay-populated',manifest,before)
            result['assertion_results'].update({key:True for key in MIGRATION_ASSERTIONS})
            write_json(directory/'measured-runtime.json',dict(schema_version=1,candidate_sha=candidate,provider=provider,go_test_name=go_name,fixture_database=repo.database_name,
                snapshots=result['phase_snapshots'],migrations=migrations,service_probes=service_probes,worker_exits=exits,final_snapshot=final,
                **{key:value for key,value in measurement.items() if key not in ('phase_snapshots','assertion_results')}))
            runtime.close();runtime=None
        result['passed']=True
    except Exception as error:
        result['failures'].append(type(error).__name__+': '+str(error));raise
    finally:
        if bridge is not None:bridge.release_model.set()
        if runtime is not None:
            try:bridge.stop() if bridge else runtime.stop_workers()
            finally:runtime.close()
        result['finished_at']=now()
        for path in directory.iterdir():
            if path.is_file():path.chmod(0o644)
        result['artifact_sha256']={p.name:digest(p.read_bytes()) for p in directory.iterdir() if p.is_file() and p.name not in ('result.json','case-tests.xml','case-pytest.stdout.log','case-pytest.stderr.log')}
        write_json(directory/'result.json',result);(directory/'result.json').chmod(0o644)
```

### workers/ingestion-python/tests/test_paid_catalog_api_integration.py:234–260

exact outer parametrization and one duplicate child JUnit. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `d4d8b6d26ead3023dbbe5084d1376c0009404aae`; file SHA256 `efd3098953dde54d3fc38c167db1f56ab97225c185fb73f032fe7f3289b70198`; excerpt SHA256 `f152dad11099037be6124d1192076cf1c35d69b58b60fce7843220d4a427672b`.

```python
@pytest.mark.parametrize('go_name,provider',[(name,provider) for name in GO_NAMES for provider in ('bankone','banktwo')],ids=CASE_IDS)
def test_required_paid_catalog_access(go_name,provider,fresh_database,monkeypatch):
    assert REQUIRED
    directory=ARTIFACTS/'paid-access'/provider/go_name
    if os.getenv('AUTODATA_PAID_CASE_CHILD')=='1':
        child_case(go_name,provider,fresh_database,monkeypatch,directory);return
    directory.mkdir(parents=True,exist_ok=False)
    env={key:value for key,value in os.environ.items() if key in ('PATH','PYTHONPATH','PYTHONDONTWRITEBYTECODE','AUTODATA_R3_CANDIDATE_SHA','AUTODATA_LIFECYCLE_TEST','AUTODATA_CATALOG_INTEGRATION_REQUIRED','AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION','GOTOOLCHAIN','GOPROXY','GOFLAGS','CGO_ENABLED','GOMODCACHE','GOCACHE','GOTMPDIR')}
    env['AUTODATA_PAID_CASE_CHILD']='1'
    node='workers/ingestion-python/tests/test_paid_catalog_api_integration.py::test_required_paid_catalog_access['+go_name+'-'+provider+']'
    command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider','--junitxml='+str(directory/'case-tests.xml'),node]
    with (directory/'case-pytest.stdout.log').open('wb') as stdout,(directory/'case-pytest.stderr.log').open('wb') as stderr:
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        try:code=process.wait(timeout=114)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)
            pytest.fail('whole paid case exceeded120s; retained owned process-group evidence')
    cases=ET.parse(directory/'case-tests.xml').getroot().findall('.//testcase')
    assert code==0 and len(cases)==1 and cases[0].get('name')=='test_required_paid_catalog_access['+go_name+'-'+provider+']' and cases[0].get('classname')=='tests.test_paid_catalog_api_integration' and not any(cases[0].find(tag) is not None for tag in ('skipped','failure','error')),(directory/'case-pytest.stdout.log').read_text()
    result=json.loads((directory/'result.json').read_text())
    for path in directory.iterdir():
        if path.is_file():path.chmod(0o644)
    result['artifact_sha256']={p.name:digest(p.read_bytes()) for p in directory.iterdir() if p.is_file() and p.name!='result.json'}
    write_json(directory/'result.json',result)
    assert result['passed'] is True and result['failures']==[]
```

### apps/api-go/postgres_catalog_access_test.go:90–123

Go setup provider/candidate strings come from environment. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `ba19bac67d5474cd975a1ee8fbde89a812c173c3`; file SHA256 `0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31`; excerpt SHA256 `7a840c8c158c67dbd990e6e649861d6cd70da86bca03a8d6a5cf9c9c3d225e38`.

```go
func paidSetup(t *testing.T) *paidFixture {
	t.Helper()
	if os.Getenv("AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION") != "1" {
		t.Skip("requires isolated paid catalog runtime")
	}
	if os.Getenv("AUTODATA_LIFECYCLE_TEST") != "1" || os.Getenv("AUTODATA_CATALOG_INTEGRATION_REQUIRED") != "1" {
		t.Fatal("required lifecycle/catalog flags missing")
	}
	dsn := os.Getenv("AUTODATA_CATALOG_TEST_DSN")
	u, err := url.Parse(dsn)
	if err != nil || u.Scheme != "postgres" || u.Host != "postgres:5432" || u.User == nil || u.User.Username() != "lifecycle_test" || u.Query().Get("sslmode") != "disable" || len(u.Query()) != 1 || !regexp.MustCompile(`^/lifecycle_test_[a-f0-9]{32}$`).MatchString(u.Path) {
		t.Fatal("isolated fixture DSN required")
	}
	password, ok := u.User.Password()
	if !ok || password != "lifecycle_test_only" {
		t.Fatal("fixture credential mismatch")
	}
	f := &paidFixture{t: t, configuration: os.Getenv("AUTODATA_PAID_TEST_CONFIGURATION_ID"), adjacent: os.Getenv("AUTODATA_PAID_TEST_ADJACENT_CONFIGURATION_ID"), regionConfiguration: os.Getenv("AUTODATA_PAID_TEST_REGION_CONFIGURATION_ID"), vehicle: os.Getenv("AUTODATA_CATALOG_TEST_VEHICLE_ID"), article: os.Getenv("AUTODATA_CATALOG_TEST_ARTICLE_ID"), other: os.Getenv("AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID"), unscoped: os.Getenv("AUTODATA_PAID_TEST_UNSCOPED_ARTICLE_ID"), provider: os.Getenv("AUTODATA_CATALOG_TEST_PROVIDER"), assertions: map[string]bool{}, phases: map[string]any{}}
	for _, id := range []string{f.configuration, f.adjacent, f.regionConfiguration, f.vehicle, f.article, f.other, f.unscoped} {
		if !commerceUUID(id) {
			t.Fatal("fixture canonical UUID required")
		}
	}
	if f.provider != "bankone" && f.provider != "banktwo" {
		t.Fatal("fixture provider invalid")
	}
	if !regexp.MustCompile(`^[a-f0-9]{40}$`).MatchString(os.Getenv("AUTODATA_CATALOG_TEST_CANDIDATE_SHA")) {
		t.Fatal("candidate SHA required")
	}
	ensureURL, controlURL := os.Getenv("AUTODATA_CATALOG_TEST_ENSURE_URL"), os.Getenv("AUTODATA_CATALOG_TEST_CONTROL_URL")
	for _, raw := range []string{ensureURL, controlURL} {
		target, e := url.Parse(raw)
		if e != nil || target.Scheme != "http" || target.Hostname() != "127.0.0.1" || target.Port() == "" || target.User != nil || target.Path != "" || target.RawQuery != "" || target.Fragment != "" {
			t.Fatal("only loopback fixture HTTP permitted")
```

### apps/api-go/postgres_catalog_access_test.go:182–206

Go measurement emits snapshots/assertions/views/HTTP/held receipt but no mandatory provider/candidate identity. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `ba19bac67d5474cd975a1ee8fbde89a812c173c3`; file SHA256 `0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31`; excerpt SHA256 `a2439b17be9c28f94fe91850c3ecac96df44e9050bd12aaccaabfe5b6dae9a23`.

```go
	if f.control.token == "" {
		t.Fatal("control token required")
	}
	t.Cleanup(func() {
		if t.Failed() {
			request, _ := http.NewRequest("GET", f.control.control+"/r3-fixture/snapshot", nil)
			request.Header.Set("X-R3-Fixture-Token", f.control.token)
			client := http.Client{Timeout: 2 * time.Second}
			if response, err := client.Do(request); err == nil {
				var snapshot map[string]any
				if response.StatusCode == 200 && json.NewDecoder(io.LimitReader(response.Body, 8<<20)).Decode(&snapshot) == nil {
					snapshot["reader_calls"] = f.reader.calls.Load()
					snapshot["identity_checks"] = f.verifier.calls.Load()
					f.phases["failure"] = snapshot
				}
				response.Body.Close()
			}
		}
		raw, _ := json.MarshalIndent(map[string]any{"phase_snapshots": f.phases, "assertion_results": f.assertions, "observed_views": f.views, "identity_checks": f.verifier.calls.Load(), "reader_calls": f.reader.calls.Load(), "http_observations": f.observations, "held_model_receipt": f.heldModelReceipt}, "", "  ")
		if err := os.WriteFile(filepath.Join(os.Getenv("AUTODATA_CATALOG_TEST_CASE_DIR"), "go-measurement.json"), raw, 0644); err != nil {
			t.Error(err)
		}
	})
	return f
}
```

### apps/api-go/postgres_catalog_access_test.go:222–252

paid grant inserts paid order and active entitlement directly in database. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `ba19bac67d5474cd975a1ee8fbde89a812c173c3`; file SHA256 `0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31`; excerpt SHA256 `bdfd1d55fa0b2384f07807a90be15fc8553406f9a169907f00f03f0e68975234`.

```go
func (f *paidFixture) grant(owner int, configuration, region string) string {
	f.t.Helper()
	o := f.owners[owner].session
	order, request, entitlement := f.uuid(), f.uuid(), f.uuid()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	tx, err := f.pool.Begin(ctx)
	if err != nil {
		f.t.Fatal(err)
	}
	defer tx.Rollback(ctx)
	statements := []struct {
		q    string
		args []any
	}{
		{`INSERT INTO workshop_orders(order_id,customer_account_id,organization_id,configuration_id,region,dataset_product_id,terms_version,amount_minor,currency,stripe_account_id,livemode,expected_price_id,provider_idempotency_key,status,first_create_attempt_at,paid_at) SELECT $1::uuid,$2::uuid,$3::uuid,$4::uuid,$5,dataset_product_id,'workshop-v1',2000,'USD','acct_fixture',false,'price_fixture',$6,'paid',now(),now() FROM dataset_products WHERE product_key='workshop-configuration-v1' AND product_version=1`, []any{order, o.AccountID, o.OrganizationID, configuration, region, "fixture:" + order}},
		{`INSERT INTO dataset_requests(dataset_request_id,dataset_product_id,vehicle_key,region,status,lane,correlation_id,idempotency_key,processing_version,organization_id) SELECT $1::uuid,dataset_product_id,$2,$3,'purchased','fast',$4::uuid,$5,'workshop-v1',$6::uuid FROM dataset_products WHERE product_key='workshop-configuration-v1' AND product_version=1`, []any{request, configuration, region, order, "fixture:" + request, o.OrganizationID}},
		{`INSERT INTO entitlements(entitlement_id,organization_id,dataset_request_id,provider_event_id,status,granted_at,customer_account_id,configuration_id,region,commerce_order_id) VALUES($1::uuid,$2::uuid,$3::uuid,$4,'active',now(),$5::uuid,$6::uuid,$7,$8::uuid)`, []any{entitlement, o.OrganizationID, request, "fixture:" + entitlement, o.AccountID, configuration, region, order}},
		{`INSERT INTO dataset_projections(dataset_projection_id,dataset_product_id,dataset_request_id,entitlement_id) SELECT gen_random_uuid(),dataset_product_id,$1::uuid,$2::uuid FROM dataset_requests WHERE dataset_request_id=$1::uuid`, []any{request, entitlement}},
		{`UPDATE workshop_orders SET entitlement_id=$1::uuid,dataset_request_id=$2::uuid WHERE order_id=$3::uuid`, []any{entitlement, request, order}},
	}
	for _, s := range statements {
		if _, err = tx.Exec(ctx, s.q, s.args...); err != nil {
			f.t.Fatal(err)
		}
	}
	if err = tx.Commit(ctx); err != nil {
		f.t.Fatal(err)
	}
	return order
}
```

### apps/api-go/postgres_catalog_access_test.go:261–297

HTTP hash before redaction, text truncation and omission of binary bodies. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `ba19bac67d5474cd975a1ee8fbde89a812c173c3`; file SHA256 `0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31`; excerpt SHA256 `a85f2934266dfe3decd330c9498697b6cf65a12b680ca7f737f4905bc6a3d5c7`.

```go
func paidObservationRedact(value string) string {
	return paidObservationMediaURL.ReplaceAllStringFunc(value, func(url string) string {
		sum := sha256.Sum256([]byte(strings.TrimPrefix(url, "/v1/catalog/images/")))
		return "/v1/catalog/images/[sha256:" + hex.EncodeToString(sum[:]) + "]"
	})
}
func (f *paidFixture) observe(owner int, method, path string, status int, headers http.Header, raw []byte, readerBefore, identityBefore int64) {
	sum := sha256.Sum256(raw)
	observation := paidHTTPObservation{Method: method, Path: paidObservationRedact(path), OwnerIndex: owner, Status: status, Headers: map[string]string{}, BodySHA256: hex.EncodeToString(sum[:]), BodySize: len(raw), ReaderBefore: readerBefore, ReaderAfter: f.reader.calls.Load(), IdentityBefore: identityBefore, IdentityAfter: f.verifier.calls.Load()}
	for _, key := range []string{"Content-Type", "Cache-Control", "Cross-Origin-Resource-Policy", "X-Content-Type-Options", "Content-Security-Policy", "Referrer-Policy", "Retry-After"} {
		if value := headers.Get(key); value != "" {
			observation.Headers[key] = value
		}
	}
	contentType := headers.Get("Content-Type")
	if strings.HasPrefix(contentType, "application/json") || strings.HasPrefix(contentType, "text/html") {
		projection := raw
		if len(projection) > 256<<10 {
			projection = projection[:256<<10]
			observation.BodyTruncated = true
		}
		redacted := paidObservationRedact(string(projection))
		if strings.HasPrefix(contentType, "application/json") && !observation.BodyTruncated {
			var body any
			if json.Unmarshal([]byte(redacted), &body) == nil {
				observation.Body = body
			} else {
				observation.Body = redacted
			}
		} else {
			observation.Body = redacted
		}
	}
	f.observationMu.Lock()
	defer f.observationMu.Unlock()
	f.observations = append(f.observations, observation)
}
```

### apps/api-go/postgres_catalog_access_test.go:550–614

canonical reuse case checks payment_calls zero and two entitlements. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `ba19bac67d5474cd975a1ee8fbde89a812c173c3`; file SHA256 `0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31`; excerpt SHA256 `a48b1cb3e667c878ce1d0d506f10f653019f3fa6b46580abd0484f702a7813f6`.

```go
func TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse(t *testing.T) {
	f := paidSetup(t)
	f.grant(0, f.configuration, "US")
	f.grant(1, f.configuration, "US")
	cold := f.snapshot("cold")
	f.expect(0, "GET", f.path("/"+f.article), "", 503)
	f.check("explicit_prepare_only", paidWorkUnchanged(cold, f.snapshot("before_prepare")))
	var wg sync.WaitGroup
	statuses := make(chan int, 8)
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func(owner int) {
			defer wg.Done()
			status, _, _ := f.call(owner, "POST", f.path("/"+f.article+"/prepare"), "{}")
			statuses <- status
		}(i % 2)
	}
	wg.Wait()
	close(statuses)
	responses := 0
	for status := range statuses {
		responses++
		if status != 202 {
			t.Fatal("concurrent prepare did not observe durable accepted work", status)
		}
	}
	if responses != 8 {
		t.Fatal("missing concurrent prepare response", responses)
	}
	scheduled := f.snapshot("scheduled")
	f.check("shared_article_job", r3Int(r3Map(scheduled, "counts"), "article_jobs") == 1)
	f.control.controlCall("POST", "start-workers")
	held := f.control.wait("model-held", func(m map[string]any) bool {
		return r3Int(m, "downstream_waiting") == 1 && m["response_captured"] == true
	})
	f.heldModelReceipt = held
	f.check("actual_model_response_held", held["response_captured"] == true)
	source := f.detail(0)
	f.check("source_readable_during_hold", r3Origin(source, "source") && source.Processing != nil)
	f.snapshot("source_held")
	f.control.controlCall("POST", "release-model")
	f.control.wait("snapshot", func(m map[string]any) bool { return r3Int(r3Map(m, "counts"), "published_revisions") == 1 })
	first := f.detail(0)
	before := f.snapshot("published")
	second := f.detail(1)
	f.expect(1, "POST", f.path("/"+f.article+"/prepare"), "{}", 200)
	after := f.snapshot("reopened")
	f.check("canonical_reused_two_owners", first.CanonicalRevisionID != nil && samePaidCatalogID(first.CanonicalRevisionID, second.CanonicalRevisionID) && paidWorkUnchanged(before, after))
	var raw []byte
	if err := f.pool.QueryRow(context.Background(), `SELECT canonical_steps FROM canonical_article_revisions WHERE canonical_article_revision_id=$1::uuid`, *first.CanonicalRevisionID).Scan(&raw); err != nil {
		t.Fatal(err)
	}
	var expected []CatalogStep
	if json.Unmarshal(raw, &expected) != nil {
		t.Fatal("raw steps invalid")
	}
	copy := first
	clonePaidCatalogArticleImages(&copy)
	expectedArticle := CatalogArticle{Steps: expected}
	clonePaidCatalogArticleImages(&expectedArticle)
	actual, _ := json.Marshal(copy.Steps)
	want, _ := json.Marshal(expectedArticle.Steps)
	f.check("canonical_steps_preserved", bytes.Equal(actual, want) && len(first.Steps) > 0 && first.Steps[0].Action != "" && first.Steps[0].Number == 0)
	f.check("payment_grants_persist", r3Int(after, "payment_calls") == 0 && len(r3Map(after, "paid_rows")["entitlements"].([]any)) == 2)
}
```

### apps/api-go/postgres_catalog_access_test.go:635–703

contextual media assertions rely on token mutation and reader operations. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `ba19bac67d5474cd975a1ee8fbde89a812c173c3`; file SHA256 `0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31`; excerpt SHA256 `6b9ddbf7117cda440123033f42393222fd54bc214169de7425396af091032acb`.

```go
func TestPostgresPaidCatalogContextualMediaAndRevocation(t *testing.T) {
	f := paidSetup(t)
	order := f.grant(0, f.configuration, "US")
	f.grant(1, f.configuration, "US")
	f.publish()
	a := f.detail(0)
	if len(a.Images) == 0 || a.Images[0].URL == "" || len(a.Steps) == 0 || a.Steps[0].Images == nil || len(*a.Steps[0].Images) == 0 {
		t.Fatal("actual nested/top-level source asset projections required")
	}
	before := f.reader.calls.Load()
	headers := f.image(0, a.Images[0].URL, 200)
	f.image(0, (*a.Steps[0].Images)[0].URL, 200)
	f.check("actual_s3_reader", f.reader.calls.Load() == before+2)
	f.check("media_security_headers", headers.Get("Cross-Origin-Resource-Policy") == "same-origin" && headers.Get("X-Content-Type-Options") == "nosniff" && strings.Contains(headers.Get("Content-Security-Policy"), "sandbox") && headers.Get("Referrer-Policy") == "no-referrer")
	before = f.reader.calls.Load()
	ref, err := openPaidCatalogImageReference(strings.TrimPrefix(a.Images[0].URL, "/v1/catalog/images/"), f.applications[0].catalogImageKey, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	f.image(1, a.Images[0].URL, 404)
	f.image(0, "/v1/catalog/images/v2.forged", 404)
	legacy, _ := sealCatalogImageReference(ref.ObjectKey, f.applications[0].catalogImageKey)
	f.image(0, "/v1/catalog/images/"+legacy, 404)
	for _, mutate := range []func(*paidCatalogImageReference){func(r *paidCatalogImageReference) { r.SourceVehicleRefSHA256 = strings.Repeat("a", 64) }, func(r *paidCatalogImageReference) { r.SourceArticleRefSHA256 = strings.Repeat("b", 64) }, func(r *paidCatalogImageReference) {
		r.ProviderSlug = "banktwo"
		if f.provider == "banktwo" {
			r.ProviderSlug = "bankone"
		}
	}, func(r *paidCatalogImageReference) { r.AssetID = "unmapped-asset" }, func(r *paidCatalogImageReference) { r.ObjectKey = "procedure-images/" + strings.Repeat("f", 64) }, func(r *paidCatalogImageReference) { r.CanonicalArticleID = f.other }} {
		changed := ref
		mutate(&changed)
		f.image(0, f.token(changed, time.Now()), 404)
	}
	old := time.Now().Add(-301 * time.Second)
	expired := ref
	expired.IssuedAt = old.Unix()
	expired.ExpiresAt = old.Unix() + 300
	f.image(0, f.token(expired, old), 404)
	f.check("invalid_media_zero_reader", f.reader.calls.Load() == before)
	f.exec(`UPDATE entitlements SET status='revoked',revoked_at=now(),revoke_reason='fixture' WHERE commerce_order_id=$1::uuid`, order)
	f.image(0, a.Images[0].URL, 403)
	f.exec(`UPDATE entitlements SET status='active',revoked_at=NULL,revoke_reason=NULL WHERE commerce_order_id=$1::uuid`, order)
	f.exec(`UPDATE customer_accounts SET status='blocked' WHERE customer_account_id=$1::uuid`, f.owners[0].session.AccountID)
	f.image(0, a.Images[0].URL, 403)
	f.exec(`UPDATE customer_accounts SET status='active' WHERE customer_account_id=$1::uuid`, f.owners[0].session.AccountID)
	f.exec(`UPDATE auth_sessions SET revoked_at=now() WHERE customer_account_id=$1::uuid`, f.owners[0].session.AccountID)
	f.image(0, a.Images[0].URL, 401)
	// A fresh same-account session may retain a valid account-bound reference.
	token, hash, _ := newCustomerSessionToken()
	now := time.Now()
	session, e := (&postgresCustomerSessions{pool: f.pool}).Rotate(context.Background(), VerifiedCustomerIdentity{ProjectID: "fixture-project", UID: f.owners[0].session.UID, AuthTime: now.Unix(), IssuedAt: now.Unix(), Expires: now.Add(time.Hour).Unix()}, hash, nil, now, now.Add(time.Hour))
	if e != nil {
		t.Fatal(e)
	}
	f.owners[0] = paidFixtureOwner{token: token, session: session}
	f.image(0, a.Images[0].URL, 200)
	f.check("current_grant_identity_rechecked", f.verifier.calls.Load() > 0 && f.reader.calls.Load() == before+1)
	before = f.reader.calls.Load()
	f.exec(`UPDATE canonical_articles SET current_canonical_revision_id=NULL WHERE canonical_article_id=$1::uuid`, f.article)
	f.image(0, a.Images[0].URL, 404)
	f.exec(`UPDATE canonical_articles SET current_canonical_revision_id=$1::uuid WHERE canonical_article_id=$2::uuid`, *a.CanonicalRevisionID, f.article)
	f.controlPaid("refresh-source")
	f.control.wait("snapshot", func(s map[string]any) bool { return r3Int(r3Map(s, "counts"), "published_revisions") == 2 })
	f.image(0, a.Images[0].URL, 404)
	f.check("stale_context_zero_reader", f.reader.calls.Load() == before)
	fresh := f.detail(0)
	f.image(0, fresh.Images[0].URL, 200)
	f.snapshot("media_final")
}
```

### apps/api-go/postgres_catalog_access_test.go:704–801

rights/historical assertions and projections. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `ba19bac67d5474cd975a1ee8fbde89a812c173c3`; file SHA256 `0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31`; excerpt SHA256 `b9194c52878e10ec00fbfe04fd23e675defab9895850f890e61dd4c88934641b`.

```go
func TestPostgresPaidCatalogHistoricalSourceAndRights(t *testing.T) {
	f := paidSetup(t)
	f.grant(0, f.configuration, "US")
	f.publish()
	a := f.detail(0)
	oldSource := *a.SourceRevisionID
	sourcePath := f.path("/" + f.article + "/source?source_revision_id=" + oldSource)
	raw := f.expect(0, "GET", sourcePath, "", 200)
	var source CatalogSourceContentResponse
	if json.Unmarshal(raw, &source) != nil || len(source.Images) == 0 || source.Images[0].URL == "" || !strings.Contains(source.Content, "<img") {
		t.Fatal("ordered source JSON lacks permitted embedded media")
	}
	f.image(0, source.Images[0].URL, 200)
	request, _ := http.NewRequest("GET", f.servers[0].URL+sourcePath, nil)
	request.Header.Set("Accept", "text/html")
	request.AddCookie(customerSessionCookie(f.owners[0].token, f.owners[0].session.ExpiresAt, time.Now()))
	readerBefore, identityBefore := f.reader.calls.Load(), f.verifier.calls.Load()
	response, err := f.servers[0].Client().Do(request)
	if err != nil {
		t.Fatal(err)
	}
	html, _ := io.ReadAll(response.Body)
	response.Body.Close()
	f.observe(0, "GET", sourcePath, response.StatusCode, response.Header, html, readerBefore, identityBefore)
	f.check("source_html_json_media", response.StatusCode == 200 && bytes.Contains(html, []byte("<img")))
	f.controlPaid("refresh-source")
	f.control.wait("snapshot", func(s map[string]any) bool { return r3Int(r3Map(s, "counts"), "published_revisions") == 2 })
	fresh := f.detail(0)
	raw = f.expect(0, "GET", sourcePath, "", 200)
	if json.Unmarshal(raw, &source) != nil {
		t.Fatal("historical JSON invalid")
	}
	ref, err := openPaidCatalogImageReference(strings.TrimPrefix(source.Images[0].URL, "/v1/catalog/images/"), f.applications[0].catalogImageKey, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	f.check("historical_source_selected", ref.SelectedSourceRevisionID == oldSource && ref.AnchorSourceRevisionID == *fresh.SourceRevisionID)
	f.image(0, source.Images[0].URL, 200)
	before := f.reader.calls.Load()
	rightsBefore := f.snapshot("rights_before")
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=(SELECT body_source_snapshot_id FROM canonical_article_source_revisions WHERE source_revision_id=$1::uuid)`, *fresh.SourceRevisionID)
	f.expect(0, "GET", f.path("/"+f.article), "", 410)
	f.image(0, fresh.Images[0].URL, 410)
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=(SELECT body_source_snapshot_id FROM canonical_article_source_revisions WHERE source_revision_id=$1::uuid)`, *fresh.SourceRevisionID)
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE content_sha256::text IN (SELECT asset->>'sha256' FROM canonical_article_source_revisions, jsonb_array_elements(resource_manifest) asset WHERE source_revision_id=$1::uuid AND asset->>'role'='asset')`, *fresh.SourceRevisionID)
	f.expect(0, "GET", f.path("/"+f.article), "", 410)
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE content_sha256::text IN (SELECT asset->>'sha256' FROM canonical_article_source_revisions, jsonb_array_elements(resource_manifest) asset WHERE source_revision_id=$1::uuid AND asset->>'role'='asset')`, *fresh.SourceRevisionID)
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=(SELECT descriptor_source_snapshot_id FROM canonical_articles WHERE canonical_article_id=$1::uuid)`, f.article)
	var index CatalogArticlesResponse
	if json.Unmarshal(f.expect(0, "GET", f.path(""), "", 200), &index) != nil {
		t.Fatal("descriptor index JSON invalid")
	}
	for _, descriptor := range index.Items {
		if descriptor.ID == f.article {
			t.Fatal("withdrawn descriptor exposed by paid index")
		}
	}
	f.expect(0, "GET", f.path("/"+f.article), "", 410)
	f.image(0, fresh.Images[0].URL, 410)
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=(SELECT descriptor_source_snapshot_id FROM canonical_articles WHERE canonical_article_id=$1::uuid)`, f.article)
	rows, err := f.pool.Query(context.Background(), `SELECT snapshot.source_snapshot_id::text FROM canonical_articles a JOIN canonical_article_source_revisions revision ON revision.source_revision_id=a.current_source_revision_id JOIN source_snapshots snapshot ON snapshot.source_snapshot_id IN (a.descriptor_source_snapshot_id,revision.body_source_snapshot_id) OR EXISTS(SELECT 1 FROM jsonb_array_elements(revision.resource_manifest) asset WHERE asset->>'sha256'=snapshot.content_sha256::text) WHERE a.canonical_article_id::text=$1 ORDER BY snapshot.source_snapshot_id`, f.article)
	if err != nil {
		t.Fatal(err)
	}
	var snapshots []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			t.Fatal(err)
		}
		snapshots = append(snapshots, id)
	}
	rows.Close()
	if rows.Err() != nil || len(snapshots) < 3 {
		t.Fatal("descriptor/body/resource rights fixture incomplete", rows.Err(), len(snapshots))
	}
	for _, snapshot := range snapshots {
		var review string
		if err := f.pool.QueryRow(context.Background(), `INSERT INTO source_review_items(source_review_item_id,item_key,item_kind,reason_code,source_snapshot_ids) VALUES(gen_random_uuid(),gen_random_uuid()::text,'quarantine','FIXTURE',jsonb_build_array($1::text)) RETURNING source_review_item_id::text`, snapshot).Scan(&review); err != nil {
			t.Fatal(err)
		}
		f.expect(0, "GET", f.path("/"+f.article), "", 404)
		f.expect(0, "GET", sourcePath, "", 404)
		f.image(0, fresh.Images[0].URL, 404)
		f.exec(`UPDATE source_review_items SET status='approved' WHERE source_review_item_id::text=$1`, review)
	}
	f.exec(`UPDATE canonical_articles SET membership_status='retired' WHERE canonical_article_id=$1::uuid`, f.article)
	f.expect(0, "GET", f.path("/"+f.article), "", 404)
	f.exec(`UPDATE canonical_articles SET membership_status='active' WHERE canonical_article_id=$1::uuid`, f.article)
	f.exec(`UPDATE vehicle_configurations SET reviewer_state='rejected' WHERE vehicle_configuration_id=$1::uuid`, f.configuration)
	f.expect(0, "GET", f.path("/"+f.article), "", 404)
	f.exec(`UPDATE vehicle_configurations SET reviewer_state='approved' WHERE vehicle_configuration_id=$1::uuid`, f.configuration)
	f.expect(0, "GET", f.path("/"+f.other+"/source?source_revision_id="+oldSource), "", 404)
	f.check("rights_denied_before_reader", f.reader.calls.Load() == before && paidWorkUnchanged(rightsBefore, f.snapshot("rights_denied")))
	sanitized, err := sanitizeCatalogSourceHTML(`<img src="https://provider.invalid/private"><script>secret()</script>`, "https://provider.invalid/private", f.applications[0].catalogImageKey)
	f.check("source_sanitizer_no_private_leak", err == nil && !strings.Contains(sanitized, "https://provider.invalid") && !strings.Contains(sanitized, "script") && !bytes.Contains(raw, []byte("storage_key")) && !bytes.Contains(raw, []byte("source_article_ref")))
	f.snapshot("rights_final")
}
```

### apps/api-go/postgres_catalog_access_test.go:802–826

legacy denied routes are within one root. Commit `4d82e413e04fb2401ac7bc28dc828375ac662180`; Git blob `ba19bac67d5474cd975a1ee8fbde89a812c173c3`; file SHA256 `0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31`; excerpt SHA256 `c4738479498db1c13e261425c14fb18727a2cba127a1944aec5273d0e2ce9401`.

```go
func TestPostgresPaidCatalogCustomerLegacyRoutesDenied(t *testing.T) {
	f := paidSetup(t)
	order := f.grant(0, f.configuration, "US")
	legacyRequest := f.uuid()
	f.exec(`INSERT INTO dataset_requests(dataset_request_id,dataset_product_id,vehicle_key,region,status,lane,correlation_id,idempotency_key,processing_version,organization_id) SELECT $1::uuid,dataset_product_id,vehicle_key,region,status,lane,gen_random_uuid(),$1,'fixture-legacy',organization_id FROM dataset_requests WHERE dataset_request_id=(SELECT dataset_request_id FROM workshop_orders WHERE order_id=$2::uuid)`, legacyRequest, order)
	f.exec(`INSERT INTO entitlements(organization_id,dataset_request_id,provider_event_id,status,granted_at) VALUES($1::uuid,$2::uuid,$3,'active',now())`, f.owners[0].session.OrganizationID, legacyRequest, "legacy:"+legacyRequest)
	before := f.snapshot("before")
	routes := []string{"POST /dataset-requests", "GET /dataset-requests/x", "POST /vehicle-identities/resolve", "GET /vehicle-identities/selectors", "POST /knowledge-queries", "POST /job-plans", "GET /datasets/x", "GET /datasets/x/sections", "GET /datasets/x/revisions", "GET /datasets/x/evidence/x", "GET /datasets/x/search", "GET /datasets/x/knowledge", "POST /datasets/x/feedback"}
	for _, route := range routes {
		parts := strings.SplitN(route, " ", 2)
		f.expect(0, parts[0], parts[1], "{}", 403)
	}
	f.check("thirteen_routes_denied_before_work", paidWorkUnchanged(before, f.snapshot("denied")))
	for _, route := range routes {
		parts := strings.SplitN(route, " ", 2)
		f.expect(-1, parts[0], parts[1], "{}", 401)
	}
	f.check("unauthenticated_401", true)
	local := catalogServer(catalogFixtureStore())
	w := httptest.NewRecorder()
	local.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/v1/catalog/vehicles/vehicle-1/articles/article-1", nil))
	f.observe(-1, "GET", "/v1/catalog/vehicles/vehicle-1/articles/article-1", w.Code, w.Header(), w.Body.Bytes(), f.reader.calls.Load(), f.verifier.calls.Load())
	f.check("explicit_local_compatibility", w.Code == 200 && !local.paidCatalogEnabled())
	f.snapshot("final")
}
```

### scripts/dev/workshop_final180_identity_adapter.py:1–102

public parser/types/constants and all false authority. Commit `0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471`; Git blob `8c7fa87bab906955c145d7cc965be641aea48c5f`; file SHA256 `0474a85c33d4f2722ad01d6e55e69a8080dc0f1983c856ca7caa1b94510a767d`; excerpt SHA256 `7569dd49a06f83d257ebbf5a5aa0453a5daf73c41e58610bb0a70c14e27e138a`.

```python
"""Bounded synthetic identity translation. No execution or artifact I/O authority."""
from dataclasses import dataclass
import hashlib
import json
import math
import re

CANDIDATE = '4d82e413e04fb2401ac7bc28dc828375ac662180'
INVENTORY = 'c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39'
PACKAGE = 'github.com/lucronn/autodata/apps/api-go'
ROOT = 'TestPostgresAuthSessionsIntegration'
IDENTITY_IDS = tuple(ROOT + '/' + name for name in (
    'ConcurrentCustomerProvisionAndRotation', 'SharedSessionRevocation',
    'ExpiryAndPersistedSecrecy', 'FirebaseExchangeAndUserRevocation',
    'FirebaseStartupRequiresMigratedPostgres'))
RAW_REFS = ('r5-access-go-events.jsonl', 'r5-access-go-stderr.log')
AUTHORITY = tuple((name, False) for name in (
    'fixture_verified', 'product_candidate_verified', 'staging_verified',
    'deployment_authorized', 'cutover_verified', 'implementation_authorized',
    'runtime_execution_authorized', 'profile_promotion_authorized', 'merge_authorized'))
EVENTS_LIMIT = 67108864
STDERR_LIMIT = 1048576
PARSER_CODES = (
    'input_type', 'events_size', 'events_count', 'line_size', 'line_delimiter',
    'json_invalid', 'json_duplicate_key', 'json_nonfinite', 'json_depth',
    'json_string', 'event_keys', 'event_type', 'unsupported_go_action')
SEMANTIC_CODES = (
    'package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',
    *(f'child_lifecycle:{i}' for i in range(5)), 'root_failed', 'root_skipped',
    'package_failed', 'package_skipped', *(f'child_failed:{i}' for i in range(5)),
    *(f'child_skipped:{i}' for i in range(5)), 'simulated_nonzero',
    'simulated_timeout', 'simulated_interrupted', 'ownership_lost', 'cleanup_incomplete')


class AdapterError(ValueError):
    """A stable code only; never embeds source strings or decoder exceptions."""


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
    family: str
    logical_id: str
    status: str
    raw_refs: tuple[str, ...]


@dataclass(frozen=True)
class IdentityDiagnostic:
    contract: str
    observation_kind: str
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str
    events_sha256: str
    stderr_sha256: str
    status: str
    observations: tuple[CaseOutcome, ...]
    failures: tuple[str, ...]
    accepted_case_credit: int
    profiles_enabled: bool
    enabled_tiers: tuple[str, ...]
    authority: tuple[tuple[str, bool], ...]


@dataclass(frozen=True)
class FakeFrame:
    at_ns: int
    kind: str
    data: bytes
    code: int | None


@dataclass(frozen=True)
class FakeReplay:
    result: SimulatedExit
```

### scripts/dev/workshop_final180_identity_adapter.py:128–240

exact restricted existing public grammar; no real Go compatibility claim. Commit `0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471`; Git blob `8c7fa87bab906955c145d7cc965be641aea48c5f`; file SHA256 `0474a85c33d4f2722ad01d6e55e69a8080dc0f1983c856ca7caa1b94510a767d`; excerpt SHA256 `8007b2aa2d22a662a4c78bbf9015a6a8c8b42b9a3da09d4a11d214b5a7bdd091`.

```python
    _require(value.exit_code is None or (type(value.exit_code) is int
                 and -255 <= value.exit_code <= 255), 'receipt_invalid')
    _require(value.exit_code is not None or value.timed_out or value.interrupted
             or value.ownership_lost or not value.cleanup_complete, 'receipt_invalid')


def _outer(raw):
    _require(type(raw) is bytes, 'input_type')
    _require(len(raw) <= EVENTS_LIMIT, 'events_size')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'json_duplicate_key')
        result[key] = value
    return result


def _nonfinite(_):
    raise AdapterError('json_nonfinite')


def _depth(text):
    # Bound the decoder before invoking it, respecting quoted/escaped delimiters.
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            _require(depth <= 32, 'json_depth')
        elif char in ']}':
            depth -= 1


def _strings(value):
    if type(value) is str:
        try:
            size = len(value.encode('utf-8'))
        except UnicodeError:
            raise AdapterError('json_string') from None
        _require(size <= 65536, 'json_string')
    elif type(value) is dict:
        for key, item in value.items():
            _strings(key)
            _strings(item)
    elif type(value) is list:
        for item in value:
            _strings(item)


def _text(value, limit, empty=False):
    return type(value) is str and (empty or bool(value)) and len(value.encode('utf-8')) <= limit


def parse_identity_events(raw: bytes) -> tuple[GoEvent, ...]:
    _outer(raw)
    _require(bool(raw), 'events_count')
    body = raw[:-1] if raw.endswith(b'\n') else raw
    lines = body.split(b'\n')
    _require(len(lines) <= 65536, 'events_count')
    events = []
    for line in lines:
        _require(bool(line) and b'\r' not in line, 'line_delimiter')
        _require(len(line) <= 1048576, 'line_size')
        try:
            text = line.decode('utf-8')
            _depth(text)
            row = json.loads(text, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
            if type(exc) is AdapterError:
                raise
            raise AdapterError('json_invalid') from None
        _strings(row)
        _require(type(row) is dict, 'event_type')
        _require({'Time', 'Action', 'Package'} <= row.keys()
                 and row.keys() <= {'Time', 'Action', 'Package', 'Test', 'Elapsed', 'Output', 'FailedBuild'},
                 'event_keys')
        _require(all(v is not None for v in row.values()), 'event_type')
        _require(_text(row['Time'], 128) and _text(row['Package'], 256)
                 and type(row['Action']) is str, 'event_type')
        action = row['Action']
        _require(action in ('start', 'run', 'output', 'pass', 'fail', 'skip'), 'unsupported_go_action')
        test = row.get('Test')
        elapsed = row.get('Elapsed')
        output = row.get('Output')
        failed = row.get('FailedBuild')
        _require('Test' not in row or _text(test, 256), 'event_type')
        _require('Elapsed' not in row or (type(elapsed) in (int, float)
                 and 0 <= elapsed <= 86400 and math.isfinite(elapsed)), 'event_type')
        _require(('Output' not in row or (action == 'output' and type(output) is str))
                 and (action != 'output' or 'Output' in row), 'event_type')
        _require('FailedBuild' not in row or (action == 'fail' and test is None
                 and _text(failed, 1024)), 'event_type')
        _require((action != 'start' or test is None) and (action != 'run' or test is not None), 'event_type')
        events.append(GoEvent(row['Time'], action, row['Package'], test, elapsed, output, failed))
    return tuple(events)


def _receipt_failures(receipt):
    return tuple(code for flag, code in (
        (receipt.exit_code is not None and receipt.exit_code != 0, 'simulated_nonzero'),
        (receipt.timed_out, 'simulated_timeout'), (receipt.interrupted, 'simulated_interrupted'),
        (receipt.ownership_lost, 'ownership_lost'), (not receipt.cleanup_complete, 'cleanup_incomplete')) if flag)
```


## 13. Current reviewed-parent preservation pins

These exact Git-object hashes bind Stage A/B1/B2/CI and the initial shared runbook. All listed code/test/workflow/inventory bytes must remain unchanged during Stage D. Only the listed runbook is a future allowed append after coordinator reconciliation; Stage C runbook changes must be integrated by the coordinator with a fresh exact checkpoint and review, never silently adopted. Historical section12 source pins remain immutable citations.

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
    "path": ".github/workflows/autonomous-verification.yml",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "08384431f5c6795eb83cae0ad4e8b8759d5e6fa9",
    "bytes": 9521,
    "sha256": "d38f4b1a5f414775b494ee801c83ebbc0473a7ab7e970cbf573529d08f1010aa"
  },
  {
    "path": "docs/verification/workshop-final180-runbook.md",
    "commit": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "git_blob": "05c38499f47d8960e9d6ae8c0497f5866cec200c",
    "bytes": 22069,
    "sha256": "0a36f9e46ffa767feacc3a49ead622ce3d424b5eec155300c3df58dde8da89d6"
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

## 14. Live coordinator tracking receipt

Coordinator synchronization is recorded at https://github.com/lucronn/autodata/issues/186#issuecomment-6639038727; saved receipt `/home/corp/autodata-evidence/final180-paid-gate-tracking/receipt.json` SHA256 `fcc31f428c6f49f41d4a523d2c62b071ff74c7515a25c5cf4751943913298761` has status `synchronized_live_readback`. Issue before/after SHA256 are `46a8b5e3fda4f6efc54ce390e3ab93b1ec16ad662cc289b62f67a078fdeeeb35` / `17cd1425c2300b4c68b321ef99a06291a0a3e68dea85d237620a32c0d5bd73fd`; Project before/after SHA256 are `8900b3a8fd1ca381c66e4c22763e313ece3ba15e745a0380cb76ad0cd6c3cf18` / `87454561a76fae5f08b45b3ce94af847a4963d11fcb37872275e2e479700f5fd`. All 166 prior comments are preserved (167 total), Issue body and unrelated Project fields are unchanged, and previous Source is archived verbatim. Previous/current Project Source SHA256 are `52904c974a884f2e8c3da217e954118cb02aac28c4914df44c54b05604c8a3f3` / `bd9b9e55ec29d898de6e8fb2c56b3834abf44ab4b08658dbcee18e28b603fcc7`; Project remains In Progress. Standalone and nested records retain the full receipt. Independent five-file pre-sync review PASS/no findings is coordinator-reported. This receipt does not assert checkpoint preflight, committed-checkpoint review or implementation dispatch.
