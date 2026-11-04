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
