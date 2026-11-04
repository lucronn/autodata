# final180 Stage A offline diagnostics

Stage A admits immutable source and reconciles **caller-supplied claims**. It measures no fixture execution, reads no producer formats, and supplies no acceptance evidence. Even an exit0 `consistent` diagnostic has every authority false. Source ancestry is a separate, unproven fact.

The synchronized authorizing checkpoint is `b8ffaa39e6b9104df67f69541ce4da8a936adc0f`; selected application source is `4d82e413e04fb2401ac7bc28dc828375ac662180`. The tooling checkout HEAD is independently recorded as `runner_sha`. These three identities have different roles. Historical source inspection `df52326b2a12fd17db39d9368f66a28a366f38ad` does not select executable source. The immutable inventory is `docs/agents/specs/2026-11-04-workshop-final180-inventory.json` at the authorizing checkpoint: identity5, catalog8, commerce14, paid12, browser_dto120, browser_api21. Support contributes zero cases.

Use a preexisting owned plain candidate clone, detached at that selected application SHA. The runner never clones or repairs source. Admission rejects tracked changes, missing or extra files, untracked and ignored files, remotes, alternates, submodules, unsafe file types, links, custom hooks, configured hooksPath, configuration includes and partial-clone/promisor configuration. Stock `.sample` hooks are admitted regardless of executable bits. Every tracked file is compared to its immutable Git blob, including its executable mode; all82 inventory pins are checked separately. Files are hashed in1MiB chunks. Reads and source identity are checked for drift.

Use a fresh absolute output path outside candidate source under an existing owned parent that is not writable by group or others. Every directory component must be free of symlinks. The runner exclusively creates the output directory0700 and atomically publishes files0600. No output path is reused. Keep these diagnostics private.

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

Input JSON rejects duplicate keys, nonfinite numbers, BOM, invalid UTF8, excessive depth and oversized strings/arrays. Observations are limited to4MiB and512 rows. An input with513 rows is rejected before reconciliation with only `observation_count_exceeded`; there is no prefix result. Reconciliation reports all missing IDs in inventory order, then per-family observed extra/duplicate/nonpass failures in input order. Every admitted complete diagnostic fits4MiB; a serialization invariant failure instead produces unavailable with `diagnostic_size_invariant`. The source manifest is limited to64MiB; source admission allows at most100000 tracked files and4GiB of tracked bytes, with a300-second inspection budget. Each Git read has a30-second bound and64MiB stdout/1MiB stderr ceiling.

`diagnostic.json` records the exact checkpoint, runner, candidate, inventory, source-manifest and observation hashes; the fixed resolved Git executable path/content SHA256/version; six observed family counts; status; failures; and all nine authority flags set false. `source-manifest.json` contains sorted path/mode/byte-length/SHA256 members and is hash-bound by the diagnostic. Both use canonical compact UTF8 JSON with sorted keys and one trailing LF. Stdout prints only the diagnostic's absolute path and status. Admission failure may leave only a diagnostic; unsafe output roots cannot receive one. Interrupted reads/writes retain an `interrupted` diagnostic when the owned output root remains writable; a broken or moved output directory can prevent retention, and is never success.

Exit0 means `consistent` source admission or claim reconciliation. Exit1 means `inconsistent` claims or `interrupted`. Exit2 means unavailable contract/input/output or an argparse usage error. `run`, runtime-lock options and every unknown option are rejected before output creation. There is no preflight-receipt CLI or file dependency: exact-base preflight, independent gate review and fresh Issue186/Project8 tracking are coordinator dispatch requirements.

The runner resolves Git only from `/usr/local/bin:/usr/bin:/bin`, records the canonical regular executable, and hashes it before and after fixed commands. It uses a private empty HOME, isolated Git environment, disabled hooks/fsmonitor and no caller-supplied argv/config/environment. Available subprocesses are Git version, object/tree reads, and read-only checkout observations. No candidate module is imported.

Stage B remains blocked on a separate synchronized implementation gate: concrete Docker/service/image supervision, exact raw producer schemas and result mappings, runtime locks/run authorization and observed tool/image/cache/storage/operator facts. Actual final180 execution, R3 evidence, raw validators, acceptance transport and profile promotion remain separate gates. Stage A does not enable assembler/evaluator profiles, merge, deploy, create resources, launch Docker or contact providers.

Verification commands:

```sh
python3 -m unittest scripts/dev/test_workshop_final180_runner.py -v
python3 -m unittest discover -s scripts/dev -p 'test_*.py'
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
python3 -m py_compile scripts/dev/workshop_final180_runner.py scripts/dev/test_workshop_final180_runner.py
git diff --check
```
