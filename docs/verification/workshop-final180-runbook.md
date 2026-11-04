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
