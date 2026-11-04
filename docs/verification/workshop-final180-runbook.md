# final180 Stage A offline diagnostics

Stage A admits immutable source and reconciles **caller-supplied claims**. It measures no fixture execution, reads no producer formats, and supplies no acceptance evidence. Even an exit0 `consistent` diagnostic has every authority false. Source ancestry is a separate, unproven fact.

The synchronized authorizing checkpoint is `b8ffaa39e6b9104df67f69541ce4da8a936adc0f`; selected application source is `4d82e413e04fb2401ac7bc28dc828375ac662180`. The tooling checkout HEAD is independently recorded as `runner_sha`. These three identities have different roles. Historical source inspection `df52326b2a12fd17db39d9368f66a28a366f38ad` does not select executable source. The immutable inventory is `docs/agents/specs/2026-11-04-workshop-final180-inventory.json` at the authorizing checkpoint: identity5, catalog8, commerce14, paid12, browser_dto120, browser_api21. Support contributes zero cases.

Use a preexisting owned plain candidate clone, detached at that selected application SHA. The runner never clones or repairs source. Admission rejects tracked changes, missing or extra files, untracked and ignored files, remotes, alternates, submodules, unsafe file types, links, custom hooks, configured hooksPath, configuration includes, filter helpers, `.git/info/attributes` and partial-clone/promisor configuration. A passive section/key allowlist applies to common config and config.worktree before Git reads; unsupported syntax, same-line section assignments, implicit booleans and continuations fail closed. Stock `.sample` hooks are admitted regardless of executable bits. Every tracked file is compared to its immutable Git blob, including its executable mode; all82 inventory pins are checked separately. Files are hashed in1MiB chunks. Reads and source identity are checked for drift.

Use a fresh absolute output path outside candidate source under an existing owned parent that is not writable by group or others. Every directory component must be free of symlinks. Before creating output, a separate bounded no-follow scan includes every candidate directory and Git metadata directory, and compares their device/inode identities with the output parent ancestry. This rejects preexisting bind aliases of source or Git descendants as well as lexical and symlink overlap. The scan has its own300-second/100000-directory ceiling and creates no artifacts on failure. The output parent identity is rechecked before mkdir. Mount topology must stay stable during admission; concurrent privileged mount changes are outside what these filesystem snapshots can prove. The runner exclusively creates the output directory0700 and atomically publishes files0600. No output path is reused. Keep these diagnostics private.

```sh
python3 scripts/dev/workshop_final180_runner.py inspect \
  --checkpoint-sha b8ffaa39e6b9104df67f69541ce4da8a936adc0f \
  --candidate-root /absolute/owned/candidate \
  --output-root /absolute/owned/private/inspect-attempt-01

python3 scripts/dev/workshop_final180_runner.py reconcile \
  --checkpoint-sha b8ffaa39e6b9104df67f69541ce4da8a936adc0f \
  --candidate-root /absolute/owned/candidate \
  --observations /absolute/owned/normalized-claims.json \
  --output-root /absolute/owned/private/reconcile-attempt-01
```

The observations document has exactly these top-level fields:

```json
{
  "contract": "workshop-final180-observations-v1",
  "candidate_sha": "4d82e413e04fb2401ac7bc28dc828375ac662180",
  "observations": [
    {
      "family": "commerce",
      "logical_id": "test_orders_create_and_owner_scope",
      "status": "passed",
      "raw_refs": []
    }
  ]
}
```

That one-row example is incomplete and yields missing-ID failures. Supply the literal IDs from the pinned inventory to reconcile a complete180 claim set. Status is exactly passed, failed, skipped or unavailable. Duplicate observations remain distinct. Unknown IDs cannot replace expected IDs even when totals match; DTO IDs cannot satisfy API IDs. `raw_refs` are bounded safe relative POSIX strings only: the runner never opens them or asserts that they exist. Aggregate counts, profiles, summaries and authority fields are rejected.

Input JSON rejects duplicate keys, nonfinite numbers, BOM, invalid UTF8, excessive depth and oversized strings/arrays. Observations are limited to4MiB and512 rows. An input with513 rows is rejected before reconciliation with only `observation_count_exceeded`; there is no prefix result. Reconciliation reports all missing IDs in inventory order, then per-family observed extra/duplicate/nonpass failures in input order. Every admitted complete diagnostic fits4MiB; a serialization invariant failure instead produces unavailable with `diagnostic_size_invariant`. The source manifest is limited to64MiB; source admission allows at most100000 tracked files and4GiB of tracked bytes, with a300-second inspection budget checked throughout hashing and streaming directory traversal. Directory enumeration also rejects more than100000 directories and keeps only the current directory open. Each Git read has a30-second bound and64MiB stdout/1MiB stderr ceiling.

`diagnostic.json` records the exact checkpoint, runner, candidate, inventory, source-manifest and observation hashes; the fixed resolved Git executable path/content SHA256/version; six observed family counts; status; failures; and all nine authority flags set false. `source-manifest.json` contains sorted path/mode/byte-length/SHA256 members and is hash-bound by the diagnostic. Both use canonical compact UTF8 JSON with sorted keys and one trailing LF. Stdout prints only the diagnostic's absolute path and status. Admission failure may leave only a diagnostic; unsafe output roots cannot receive one. Interrupted reads/writes retain an `interrupted` diagnostic when the owned output root remains writable; a broken or moved output directory can prevent retention, and is never success.

Exit0 means `consistent` source admission or claim reconciliation. Exit1 means `inconsistent` claims or `interrupted`. Exit2 means unavailable contract/input/output or an argparse usage error. `run`, runtime-lock options and every unknown option are rejected before output creation. There is no preflight-receipt CLI or file dependency: exact-base preflight, independent gate review and fresh Issue186/Project8 tracking are coordinator dispatch requirements.

The runner resolves Git only from `/usr/local/bin:/usr/bin:/bin`, records the canonical regular executable, and hashes it before and after fixed commands. It uses a private empty HOME, isolated Git environment, disabled hooks/fsmonitor, `GIT_NO_LAZY_FETCH=1` and no caller-supplied argv/config/environment. Available subprocesses are Git version, object/tree reads, and read-only checkout observations. No candidate module is imported.

Stage B remains blocked on a separate synchronized implementation gate: concrete Docker/service/image supervision, exact raw producer schemas and result mappings, runtime locks/run authorization and observed tool/image/cache/storage/operator facts. Actual final180 execution, R3 evidence, raw validators, acceptance transport and profile promotion remain separate gates. Stage A does not enable assembler/evaluator profiles, merge, deploy, create resources, launch Docker or contact providers.

Verification commands:

```sh
python3 -m unittest scripts/dev/test_workshop_final180_runner.py -v
python3 -m unittest discover -s scripts/dev -p 'test_*.py'
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
python3 -m py_compile scripts/dev/workshop_final180_runner.py scripts/dev/test_workshop_final180_runner.py
git diff --check
```

## Stage B1 synthetic identity library

The separate B1 authorizing checkpoint is
`006fab0d1380c2506330bbc0b48397a32294b6cc`. Its plan and normative contract are
`docs/superpowers/plans/2026-11-04-workshop-final180-stage-b1-identity.md` and
`docs/agents/specs/2026-11-04-workshop-final180-stage-b1-identity.md`.
`scripts/dev/workshop_final180_identity_adapter.py` is an importable standard-library
module for synthetic bytes and finite `FakeFrame` tuples. It has no CLI, real
runtime adapter, filesystem collector, or producer imports. The Stage A commands,
historical checkpoint and rejection of `run` above retain their meaning.

Call `parse_identity_events(events_raw)` to validate the restricted simulated Go
JSONL grammar, or `translate_identity(events_raw, stderr_raw, receipt, context)`
to produce an `IdentityDiagnostic`. `IdentityContext` binds the exact selected
application SHA, inventory digest
`c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39`, and a
caller-supplied lowercase SHA256 source-manifest digest. This simulated context
does not prove source inspection. `SimulatedExit` supplies simulated exit,
timeout, interruption, ownership and cleanup facts. Even complete clean bytes
cannot override an adverse receipt.

`replay_identity_fake(frames)` merges finite, prevalidated frames with simulated
scheduled actions. Time uses integer nanoseconds; no wall clock or sleep runs.
The child deadline is 180 seconds, TERM grace is 5 seconds, and cleanup ends at
most 10 seconds after the first trigger, capped at 190 seconds. Equal-time
ordering is ownership loss, cancellation, scheduled timeout, TERM, KILL,
leftover, ordinary exit, TERM acknowledgement, KILL acknowledgement, stdout,
stderr. Ownership loss disarms scheduled actions. Cancellation during cleanup
does not extend deadlines. A TERM acknowledgement at the KILL deadline and a
KILL acknowledgement at the cleanup ceiling are too late. All remaining frames
after terminal completion are rejected.

A caller can hand retained synthetic bytes through the library without writing
artifacts:

```python
from scripts.dev.workshop_final180_identity_adapter import (
    FakeFrame, replay_identity_fake, translate_identity, serialize_identity_diagnostic,
)

# synthetic_jsonl and context are constructed in memory by the caller.
replay = replay_identity_fake((
    FakeFrame(0, 'stdout', synthetic_jsonl, None),
    FakeFrame(1, 'exit', b'', 0),
))
diagnostic = translate_identity(replay.stdout, replay.stderr, replay.result, context)
canonical_bytes = serialize_identity_diagnostic(diagnostic)
```

The parser admits at most 64MiB, 65536 lines and 1MiB per line, with strict UTF8,
no blank lines/CRLF, duplicate keys, nonfinite constants, unknown fields or
unsupported actions. A final LF is optional. It bounds JSON nesting to 32 and
decoded strings to 65536 UTF8 bytes. Stderr is opaque bytes bounded to 1MiB.
Replay accepts at most 65536 frames, 1MiB per chunk, 64MiB stdout and 1MiB stderr;
the aggregate ceiling is 65MiB. Invalid input returns no successful prefix.
Public parser and caller-schema errors raise `AdapterError` with a fixed code;
within the outer byte limits a parser error during translation returns five
unavailable rows and its stable code.

Exactly five identity rows appear in frozen inventory order. The root/package
are support and contribute zero IDs. A consistent result requires exact package
identity, one package start/final pass, and one correctly ordered run/pass for
the root and every child. Unknown tests, wrong package, duplicate/missing or
out-of-order events fail closed; repeated output adds no cases. Output strings
never supply status claims and never enter failure text. Each row's raw refs are
exactly `r5-access-go-events.jsonl` and `r5-access-go-stderr.log`: names for the
two caller-retained byte strings, never file reads or evidence that disk artifacts
exist.

`serialize_identity_diagnostic` revalidates the five ordered IDs, row statuses,
fixed failure vocabulary, digests, profiles and authority before returning
canonical compact sorted UTF8 JSON with one LF, bounded to 65536 bytes. Its
contract is `workshop-final180-identity-synthetic-v1` and observation kind is
`simulated-source-profile-validation`. Every result has `accepted_case_credit=0`,
`profiles_enabled=false`, `enabled_tiers=[]` and all nine authority flags false,
including `fixture_verified`, `runtime_execution_authorized` and
`merge_authorized`. Runtime lock and run record remain null in the coordinating
workflow. `consistent` means only that synthetic input matches this restricted
profile; this is zero real acceptance credit.

B1 omits migration, JUnit, SQL-row and nested JSONB validation. It does not cover
the other 175 IDs or emit a full180 claim set. Actual Go-version compatibility,
other-family raw validators, real process/Docker ownership supervision, runtime
locks, actual fixture execution, tool/image/cache/storage/operator observations,
acceptance transport and profile promotion require separate successor gates.
Unit success grants no execution, merge, deployment or provider authority.

Run the offline focused checks with bytecode generation disabled:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_identity_adapter.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_runner.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/dev -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
```

## Stage B2 synthetic catalog Go-event library

B2's separate authorizing checkpoint is
`3cd99224eae7012f8c6cc0bfc15a1053a8e7762f`, descending from reviewed B1 head
`54a7ca32eab80654310d862f0ac6957375d16e8b`. The selected application candidate
remains `4d82e413e04fb2401ac7bc28dc828375ac662180`. The decision-complete plan and
contract are `docs/superpowers/plans/2026-11-04-workshop-final180-stage-b2-catalog-go.md`
and `docs/agents/specs/2026-11-04-workshop-final180-stage-b2-catalog-go.md`.
Stage A and B1 retain their separate checkpoint identities and behavior above.

`scripts/dev/workshop_final180_catalog_adapter.py` translates eight synthetic
caller-selected `(provider, go_test_name)` slots in memory. Each of the four
literal catalog roots has a bankone and banktwo slot, emitted in inventory order.
`parse_catalog_events` delegates grammar only to the unchanged public B1 parser.
`translate_catalog(cases, context)` takes exactly eight frozen `CatalogCase`
values in a tuple, a frozen `CatalogContext` with the pinned candidate/inventory
and a caller-claimed source-manifest digest, and directly constructed B1
`SimulatedExit` receipts. It validates all outer schemas and byte budgets before
parsing or hashing any slot. It has no CLI, collector, timer scheduler or callback
runtime. The producer's Go/wait deadlines are source context; B1's identity
180-second fake replay is not part of this catalog adapter.

Each slot requires exactly one package start at the beginning, its exact root's
run and terminal strictly inside the package interval, and a final package
terminal. Root output is valid only between its run and terminal; package output
is valid only inside the package interval. Duplicate/missing events, other roots,
children or packages fail closed. Output and stderr content never supply status.
Parser errors make that row unavailable while preserving applicable receipt
codes; the other seven slots remain independent. Interruption makes a parsed
row unavailable. Structural/fail/nonzero/timeout/ownership/cleanup failures take
precedence over a valid skip. Top status is interrupted, then unavailable, then
inconsistent for any nonpassed row, otherwise consistent.

Events are bounded to 64MiB per slot, stderr to 1MiB per slot, and the combined
bytes of all eight slots to 65MiB. The restricted B1 grammar retains its 65536
lines, 1MiB line, depth32 and 65536-byte decoded-string bounds. There is no
truncation or successful-prefix result. Each row retains exact SHA256 hashes and
two literal `r3/<provider>/<root>/go-events.jsonl` / `go-stderr.log` memory refs;
the adapter never opens those paths or asserts that artifacts exist.

Raw Go bytes cannot authenticate bank identity. Identical bytes in the two bank
slots are deliberately permitted as two synthetic context rows. A consistent
result proves only restricted synthetic event consistency. It supplies zero
real acceptance credit and cannot establish executed catalog cases, source
inspection, actual Go compatibility or a complete catalog validator.

`serialize_catalog_diagnostic` revalidates the exact eight ordered IDs and refs,
concrete field types, digest shapes, fixed failure vocabulary/order, derived row
and top statuses, disabled profiles and every authority pair. It returns compact
sorted-key ASCII-escaped UTF8 JSON with exactly one LF, bounded to 65536 bytes,
under contract `workshop-final180-catalog-go-synthetic-v1` and observation kind
`simulated-source-profile-validation`. Rejected claims raise stable
`AdapterError('diagnostic_invalid')` without partial bytes. All diagnostics have
exact integer `accepted_case_credit=0`, `profiles_enabled=false`, empty enabled
tiers and all nine authorities false. Coordinating runtime lock and run record
remain null. No acceptance envelope or full180 observations document is emitted.

Complete catalog validation still requires separately admitted JUnit/result/
process/environment/manifest identity bindings, nested raw document/JSONB
semantics, and a typed inventory of dynamic support artifacts. Real runtime
supervision, actual tools/images/cache/storage/operator facts, genuine final180
execution, independently registered profiles and profile promotion remain
separate gates. Synthetic unit results authorize none of those actions.

Run the offline catalog suite alongside the unchanged predecessor suites:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_catalog_adapter.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_identity_adapter.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_runner.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/dev -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
git diff --check
```

The catalog tests use constructed fake JSONL/receipts and audit the adapter's
static import/call boundary. Before handing off, compile changed Python source
in memory without bytecode, check the exact three-path diff allowlist against
the B2 checkpoint, and verify Stage A/B1 modules and tests remain byte-identical.


## CI Git-metadata fixture isolation integration

The CI integration starts at independently reviewed checkpoint
`8bc9371a2715f34f06f261c8abae4194be2e1ea0`, on reviewed B2 head
`0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471`. It applies only the Stage A
test-file repair from ancestor `2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e`
to source `93b0bf4ed18737a7e57c0de6a8ea1fa0f5bdba0a`. The exact patch
SHA256 is `c4567a3b03db9d8bb56af43a701f56ebaf15d68149ff6cadd326c93ecfb921eb`;
the repaired test file is byte-identical to that source. The application
candidate remains `4d82e413e04fb2401ac7bc28dc828375ac662180`.

`ProductionGitTests` now initializes owned passive metadata in its temporary
root before constructing the reader. Constructor and argv assertions use that
root, and metadata directory creation is idempotent. CI checkout credential
configuration therefore cannot break test setup. ProductionGitReader, the
Stage A runner, both adapters, B1/B2 tests and workflow remain unchanged.
Existing configuration/helper, hook, attribute, alternate, worktree, executable
and limit rejection tests remain active; production admission stays strict.

The specification's contaminated-checkout regression imports the test module,
sets its ROOT to a temporary checkout containing an inert forbidden credential
helper marker, and runs ProductionGitTests. Before editing, all ten tests errored
in setup with `git_config` (0.078s, exit 1). After the exact repair, the same ten
tests passed (0.114s, exit 0). The marker was never executed. Standalone and nested
preflights at the exact checkpoint both returned `status: synchronized` with
empty errors before implementation.

Fresh offline focused checks passed: Stage A 52 in 1.105s, B1 25 in 3.747s, and
B2 23 in 3.911s, using the three unittest commands above with `-v`. Complete
autonomy discovery passed 146 tests in 46.363s. Complete developer discovery
passed 360 tests in 494.258s; both suites exited zero with no failures or errors.
The in-memory Python compile, exact pinned patch/source comparison, unchanged
predecessor source pins, exact two-path diff and `git diff --check` also passed.
Commands are:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/dev -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v
```

These synthetic/tooling results prove only test-fixture isolation and unchanged
restricted diagnostic behavior. B1 fake identity rows and B2 unauthenticated
bank-context rows earn no real accepted IDs. Real raw fixtures, full catalog
semantics, real Go compatibility and genuine final180 execution remain unproven.
Complete raw validators and JUnit/result/process/environment/manifest bindings,
dynamic-support inventory, real supervisor provenance and all profile, staging
and release gates remain separate. `accepted_case_credit=0`,
`profiles_enabled=false`, `enabled_tiers=[]`, `runtime_lock=null` and
`run_record=null`. All nine authority flags remain false: fixture_verified,
product_candidate_verified, staging_verified, deployment_authorized,
cutover_verified, implementation_authorized, runtime_execution_authorized,
profile_promotion_authorized and merge_authorized.

Exact-successor-head independent review and Autonomous Verification readback
are pending at this pre-commit documentation point; no successor CI success is
asserted. The coordinator records the immutable code SHA, review and exact-head
CI job states externally after commit/push. Stage A predecessor CI success and
B1 predecessor CI failures described in the pinned plan remain predecessor
evidence, not successor results.

## Stage C: restricted synthetic commerce14 adapter

Gate checkpoint: `cd9e8355a0ccb055b4327bbbd1ecaf97e7cddbe9`, based on
reviewed CI integration parent `fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc`.
The builder independently passed both standalone and nested machine preflights at
that exact clean checkpoint (`status: synchronized`, `errors: []`) after the
coordinator's exact-checkpoint review and explicit dispatch. Initial translator
milestone `b5b5e280f58ca1400537d7fb7d8426e94ed118d5` was validated and pushed;
the final code head and external evidence hashes are returned to the coordinator
after the final commit, avoiding a self-referential commit identity here.
Application candidate remains `4d82e413e04fb2401ac7bc28dc828375ac662180`.

This library accepts caller-owned bytes and simulated receipts. Its restricted
flat synthetic XML contains exactly fourteen literal commerce names and 53
nominal supporting names, with opaque bounded support classnames except the
reserved commerce classname. It admits one attribute-free `testsuite`, direct
`testcase` children and at most one `failure`, `error` or `skipped` child per case.
It does not establish actual installed pytest/plugin XML compatibility. Expat
uses UTF8, `buffer_text=False` and one final feed. The shared production checker
counts decoded UTF8 bytes by code point, including normalized outside-root
whitespace; mandatory 1MiB precedence fixtures and callback segmentations are
covered. Raw hashes retain original bytes, including original CRLF forms.

Optional Go support uses the unchanged public B1 parser. It affects only the
first commerce ID; missing support makes that ID and the top diagnostic
unavailable. Both present streams are attempted independently after all outer
validation, preserving the union of parser, semantic and simulated receipt
facts. Tests freeze all twelve clean-XML pytest/Go mixed-failure outcomes,
including parser unavailability taking precedence over interruption. Shared
JUnit/pytest failures affect all fourteen rows. Supporting pytest/Go cases add
no logical IDs. All admitted logs are opaque and hashed in full.

The strict serializer accepts exact frozen concrete types, validates receipt
facts, ordered reasons, rows, refs, hashes and derived statuses, and emits sorted
compact UTF8 JSON with one final LF. Every result retains exact integer zero
accepted-case credit, profiles disabled, no enabled tiers, null runtime lock and
run record, and all nine authority values false. A valid fixed-schema diagnostic
is below the 65536-byte output guard; the guard's final-LF boundary is exercised
with an encoder-result stub, rather than presented as a reachable oversized
valid schema. Aggregate input size is the sum of the five individual maxima
(74448896 bytes), so aggregate overflow after valid individual sizes is
unreachable; that arithmetic invariant is checked directly.

Failing-first evidence: the initial clean-row assertion failed because the
adapter was absent; the serializer assertion failed because its API was absent.
Two subsequent XML boundary regressions failed before their fixes: Expat routes
outside-root whitespace to `DefaultHandler`, and that handler retains raw CRLF
rather than the normalized character data used inside the root. The production
checker now handles both streams consistently; byte hashes remain raw. Literal
identity, parser limits/errors, lifecycle, independent parsing, all receipt flags,
optional absence, forged serializer metadata and deterministic output tests use
constructed bytes only.

Offline commands and measured results for this slice are recorded below. No
fixture collection or opt-in integration flag was used. Test logs and scope
receipts are retained outside the repository under
`/home/corp/autodata-evidence/final180-commerce-build/`.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts.dev.test_workshop_final180_commerce_adapter -v
# 31 tests, 4.605s, OK
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts.dev.test_workshop_final180_commerce_adapter scripts.dev.test_workshop_final180_runner scripts.dev.test_workshop_final180_identity_adapter scripts.dev.test_workshop_final180_catalog_adapter -v
# 131 tests, 14.963s, OK
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v
# 146 tests, 52.383s, OK
```

The initial full developer run was interrupted when the last serializer
regression was added, because unittest discovery had collected the earlier test
module. Its log is retained explicitly as interrupted, with no success claim.
The complete final developer discovery result follows below.

In-memory compilation of both new modules, AST import/call/module-level checks,
exact six frozen non-slotted dataclass shapes, independently embedded literal
maps, the 46-code vocabulary and `git diff --check` passed. The implementation
diff contains exactly the two new modules and this append-only runbook slice.
All nine canonical parent pins were checked; the inherited 22069-byte runbook
prefix remains byte-identical (SHA256
`0a36f9e46ffa767feacc3a49ead622ce3d424b5eec155300c3df58dde8da89d6`).
Stage A/B1/B2/CI implementation, test, planning, record, task and workflow bytes
remain unchanged relative to the dispatched checkpoint.

Final safe exports cannot prove omitted intermediate financial facts, signed
webhook bodies/signatures, HTTP outcomes, settlement, or race/order traces.
Full financial/raw validation, observed installed JUnit compatibility,
authenticated process/artifact provenance, real runtime acceptance and the full
final180 envelope remain blocked. Synthetic unit success enables no profile,
fixture, provider, payment, settlement, browser, Docker, VM, cloud, merge,
deployment or promotion authority. Independent exact-code-head review and
exact-head CI readback remain coordinator-owned and pending at builder handoff;
no parent CI or local test result substitutes for those results.

A subsequent completed developer discovery baseline passed 390 tests in
501.629s. Independent review then identified incomplete exact dataclass objects
constructed through `object.__new__` as a strict-boundary edge. A failing-first
regression reproduced 23 missing-field errors; narrow field-presence checks and
guarded reads now preserve `context_invalid`, `input_type`,
`go_support_invalid` and `receipt_invalid` in the original validation order,
without broadly catching unrelated errors. The complete developer and autonomy
suites are rerun for those final guarded source bytes; baseline and final logs
are retained separately. The source and test hashes were frozen in the external
`final-source-under-test.json` receipt at the start of that final discovery.

The complete guarded adapter/test source milestone is immutable commit
`d37744e09491298deba4fd63d15165778ff1c826`, pushed after the 31/131/146
commerce/focused/autonomy checks. The full developer rerun passed over the
same frozen source/test hashes; the final documentation commit records its
measured result without changing either tested module. No full-suite pass was
claimed by that intermediate source commit.

Final guarded-source developer verification completed successfully:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/dev -p 'test_*.py' -v
# 391 tests, 542.817s, OK
```

The final suite's exit code was zero. Both tested modules still match the
SHA256/byte-length values frozen at discovery start. The fresh final autonomy
run passed 146 tests in 52.383s; the final focused run passed 131 tests in
14.963s, including all 31 commerce tests. No code was modified during the final
full discovery. The intermediate source milestone and final documentation
commit preserve the exact three-path implementation boundary. Independent
exact-final-head review and CI remain separate coordinator checks.

## Stage D: restricted synthetic paid12 adapter

Stage D was dispatched from exact synchronized checkpoint
`70c9a6ebb2cec338f938122c8c570fd5b22a6f28`, descending from reviewed CI code
`fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc`. Standalone and nested preflights
both returned `status: synchronized` and `errors: []` before implementation;
all nine baseline source pins matched. The adapter/test implementation milestone
is `bff8e62c0e3aea0f99f3854152b70ec753e18122` on
`codex/workshop-final180-stage-d-paid-build`. The selected application candidate
remains `4d82e413e04fb2401ac7bc28dc828375ac662180`. This branch-local note requires
coordinator reconciliation with parallel Stage C runbook changes under a new
integration gate; Stage C supplies no predecessor code or authority here.

`workshop_final180_paid_adapter.py` accepts twelve in-memory caller-selected
bank/root slots: GrantBeforeWork, ExactScopeAndOwnerIsolation,
PrepareSourceThenCanonicalReuse, ContextualMediaAndRevocation,
HistoricalSourceAndRights and CustomerLegacyRoutesDenied, each with the literal
`TestPostgresPaidCatalog` prefix and bankone/banktwo suffix. Each slot retains
only the literal `paid-access/<bank>/<root>/go-events.jsonl` and
`paid-access/<bank>/<root>/go-stderr.log` labels, byte hashes, ordered failure
codes and synthetic status. The library opens no files and launches no runtime.
Its only repository dependency is the unchanged B1 public parser/types. All
outer input admission completes before any parse or hash, and slots translate
independently in the twelve-slot canonical order.

The constructed tests establish first-raised parser control flow, including
`b' ' * 1048576 + b'\r'` yielding only `line_delimiter` with a clean receipt;
the CR-free oversized line yields `line_size`. Parser errors plus receipt flags
retain only that parser code and applicable receipt codes. Interruption takes
top-status precedence; a skip combined with poison fails. Strict serialization
revalidates caller-created diagnostics, exact primitive/container types, every
literal row/ref/code/status and all nine false authority claims before emitting
compact sorted ASCII JSON with one LF and the 65536-byte bound. Output/stderr
text never becomes evidence or appears in the diagnostic.

The inputs are constructed fake bytes and simulated receipts only. Identical
bytes across both bank slots are admitted because bank attribution is caller
context. Hash syntax and canonical serialization authenticate no manifest,
process, candidate, bank, real Go execution or payment. The source fixture seeds
paid orders/entitlements directly, and `payment_grants_persist` asserts
`payment_calls == 0`; these grants establish no real Stripe charge, settlement,
TEST/LIVE transaction, webhook or funds movement. Commerce remains separate.

Initial paid tests failed because the module was absent; the strict serializer
existence check then failed before its implementation. Four deliberate temporary
mutations were detected for parser precedence, outer admission, top interruption
precedence and exact primitive validation, after which the correct source was
restored. The expanded focused suite passed 132 tests: paid 32, unchanged
Stage A 52, B1 25 and B2 23. Negative CLI usage messages in unchanged Stage A
are expected test output, not runtime execution.

Full raw paid acceptance still needs independently admitted result/JUnit/
manifest/process/environment/receipt binding, the complete minimum 344-ref raw
inventory and dynamic support, migrations/SQL/HTTP/media/nested semantic
validation, actual Go compatibility and authorized owned runtime execution.
Genuine bank/payment evidence, trusted profile promotion, complete final180,
staging and release acceptance remain separate blockers.
`accepted_case_credit=0`, `profiles_enabled=false`, `enabled_tiers=[]`,
`runtime_lock=null` and `run_record=null` remain invariant. All nine authority
flags remain false: fixture_verified, product_candidate_verified,
staging_verified, deployment_authorized, cutover_verified,
implementation_authorized, runtime_execution_authorized,
profile_promotion_authorized and merge_authorized. Runtime lock/run record are
planning/report metadata and are absent from the diagnostic schema.

Independent exact-successor-head review and CI readback remain pending at this
branch-local documentation point. Parent CI was pending at the gate's recorded
readback; this note asserts no parent or successor CI success. The coordinator
records exact final SHA, independent review and CI job states externally.

Final offline verification passed: paid 32 tests in 4.111s; combined paid and
unchanged Stage A/B1/B2 132 tests in 13.186s; complete developer discovery 392
tests in 499.409s; complete autonomy discovery 146 tests in 48.258s. All exited
zero with no failures/errors. Twelve additional literal status-overlap checks
also passed. The exact import/call AST boundary and public field/type checks,
in-memory compile of both new modules, eight unchanged source pins,
append-only runbook baseline, exact three-path checkpoint diff and
`git diff --check` passed. Commands used were:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_paid_adapter.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_paid_adapter.py scripts/dev/test_workshop_final180_runner.py scripts/dev/test_workshop_final180_identity_adapter.py scripts/dev/test_workshop_final180_catalog_adapter.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/dev -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
git diff --check
```

These are offline code/constructed-profile checks. No producer fixture,
application, provider, payment, browser, Docker/VM/cloud or secret-bearing
runtime was executed for Stage D evidence. The coordinator subsequently
reported parent PR232 exact-head CI success; this does not report successor
CI or review success. Final immutable documentation/code head is sealed
externally after this commit to avoid a self-referential SHA.

### Stage D exact-type field-presence repair

Independent review of `f476ba63068c7fc6a5be2d994874f4907b6daea5` found one P2:
exact frozen dataclasses allocated without initialization could escape admission
with `AttributeError` rather than the specified stable `AdapterError`. The
review is retained externally at
`/home/corp/autodata-evidence/final180-paid-exact-head-review/REVIEW.md`.

The narrow repair milestone is
`894f49b85dbabdf8f07c82074bc960f13d6910c1`. Required fields are now checked after
exact class admission and before dereference, at their original validation
stage. Missing context fields yield `context_invalid`; missing case identity,
events, stderr or receipt fields yield `case_identity`, `input_type`,
`stderr_type` or `receipt_invalid`, respectively. Incomplete exact
`SimulatedExit` yields `receipt_invalid`; incomplete exact `PaidDiagnostic` or
`PaidOutcome` yields `diagnostic_invalid`. Identity admission still precedes
uniqueness, all byte admission precedes receipts, and event type/size checks
still precede stderr. No catch-all exception conversion was added.

Six failing-first regressions cover empty exact instances and each missing field
across all five classes, plus conflicting invalid inputs for error precedence.
Before repair they reproduced 37 `AttributeError` escapes in six tests; after
repair, combined paid and unchanged Stage A/B1/B2 passed 138 tests in 21.373s
(paid 38, unchanged 100). Both exact-gate preflights were rechecked as
`status: synchronized`, `errors: []` before repair. The original three-path
allowlist and all synthetic/payment/runtime/authority boundaries above remain
in force. This repair adds no accepted credit or execution authority.

Fresh post-repair verification passed against the repaired source: paid 38 tests
in 4.065s, combined focused 138 in 21.373s, full developer discovery 398 in
521.229s, and autonomy discovery 146 in 49.044s, all exit0 with no failures or
errors. The five original independent-review probes now produce their exact
stable `AdapterError` codes. Both new modules compile in memory; static imports,
call boundaries, literal slots/refs/authority and all preserved-source checks
remain intact. Exact final-head checks and SHA256-indexed red/green/broad-suite
logs are retained in `/home/corp/autodata-evidence/final180-paid-build/`, with
`checks.json` and `receipt.json` sealed externally after final commit/push.
Independent successor-head review and CI readback remain coordinator-owned and
pending at this documentation point. Credit remains 0; profiles/tiers remain
disabled, runtime lock/run record null, and all nine authorities false.


## Stage C/D integration verification and limits

This restricted synthetic adoption preserves C_FINAL `c4dd59b3ac6a1afb74f7ad1d4f54ef1eb6e7fdad` and adopts the exact paid adapter/test from D_FINAL `2774cdfe44e7c99a0cae5606ad1ea5f20863c0d7`, authorized by checkpoint `4fe49f7f533aef94fd66c11ea735fef932f5b268`. The preceding `Stage C: restricted synthetic commerce14 adapter` and `Stage D: restricted synthetic paid12 adapter` sections remain their original standalone-stage receipts, with their original historical scope, gate identities and results. They are not combined execution receipts.

The first 29905 bytes remain the complete C runbook; the next 8753 bytes are the exact D suffix after the shared 22069-byte prefix. The resulting historical 38658-byte prefix has SHA256 `61d0f6234606977618d007c39028bf34f349c9d60514b9f2f914a1429de3eecf`. No separator was inserted inside that prefix. The D adapter/test bytes and Git 100644 modes match the frozen source exactly; all C/predecessor/checkpoint planning/index/inventory/workflow bytes are protected.

Fresh source-CI prerequisite readback confirmed [C run41894074351](https://github.com/lucronn/autodata/actions/runs/41894074351) and [D run41894466041](https://github.com/lucronn/autodata/actions/runs/41894466041), each at its full source SHA above, completed/success with both required jobs completed/success. Standalone and nested preflights at the authorizing checkpoint returned `status: synchronized`, `errors: []`. These source receipts do not establish integration-head CI.

Measured local checks on the combined adopted tree (2026-11-04; each suite used `PYTHONDONTWRITEBYTECODE=1`, with independent suites launched concurrently):

- Combined C/D and predecessor focused: `python3 -m unittest scripts.dev.test_workshop_final180_commerce_adapter scripts.dev.test_workshop_final180_paid_adapter scripts.dev.test_workshop_final180_runner scripts.dev.test_workshop_final180_identity_adapter scripts.dev.test_workshop_final180_catalog_adapter -v` — 169 tests, 0 skips, unittest duration 18.612s, wall duration 18.843s, exit code 0, `OK`.

- Full developer discovery: `python3 -m unittest discover -s scripts/dev -p 'test_*.py' -v` — 429 tests, 0 skips, unittest duration 455.515s, wall duration 456.564s, exit code 0, `OK`.

- Full autonomy discovery: `python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v` — 146 tests, 0 skips, unittest duration 49.890s, wall duration 50.114s, exit code 0, `OK`.

- In-memory syntax compilation of commerce adapter/test and paid adapter/test: four files, 0.020655s wall duration, exit code 0; no bytecode written. The command body was:

```python
from pathlib import Path
for name in ("workshop_final180_commerce_adapter.py", "test_workshop_final180_commerce_adapter.py", "workshop_final180_paid_adapter.py", "test_workshop_final180_paid_adapter.py"):
    path = Path("scripts/dev") / name
    compile(path.read_bytes(), str(path), "exec")
```

- AST/import/call review passed: C retains dataclass/hashlib/json/re/expat, D retains dataclass/hashlib/json/re, and both import only the four public B1 symbols `parse_identity_events`, `GoEvent`, `AdapterError`, `SimulatedExit`. No cross-adapter/private import, module I/O, CLI, filesystem/process/network/clock/payment/provider behavior is introduced. Exact source bytes preserve the independently reviewed bodies. Static checks establish scope, not a hostile-code sandbox.

- Exact working-tree allowlist, D source-byte/mode identity and historical-prefix checks passed; `git diff --check` returned exit code 0. Full external logs/results are retained at `/home/corp/autodata-evidence/final180-cd-integration-build/`. The clean committed code-head object checker, independent exact-head review and exact integration-head CI are separate subsequent receipts; no future self-referential code SHA is claimed here. Skips would remain unexecuted coverage; these three local suites reported none.

Diagnostics remain exact integer accepted_case_credit=0, profiles_enabled=false, enabled_tiers=[], runtime_lock=null, run_record=null. All nine authorities remain false: fixture_verified=false, product_candidate_verified=false, staging_verified=false, deployment_authorized=false, cutover_verified=false, implementation_authorized=false, runtime_execution_authorized=false, profile_promotion_authorized=false, merge_authorized=false. External dispatch permits only the scoped source adoption and leaves these diagnostics unchanged.

Fourteen commerce rows plus twelve paid rows remain restricted constructed-byte library observations and earn no 26 real accepted cases. This does not establish real fixtures, actual pytest/JUnit/Go provenance or runtime compatibility, full raw financial semantics, process/artifact/tool/environment/manifest provenance, authenticated bank identity, real payments/Stripe settlement, browser120/API21 or genuine same-head final180 execution. Bank-context ambiguity remains. No runtime supervision, enabled profile/evaluator/assembler promotion, staging, release, deployment, cutover or merge authority follows. No runtime/provider/payment/secret/actual fixture operation was performed for this adoption.
