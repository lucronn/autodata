# Agent Evidence Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. The coordinator must satisfy the repository planning gate before implementation begins.

**Goal:** Make the existing local agent chain produce independently checkable, exact-commit evidence instead of converting an agent's assertion of success into release proof.

**Architecture:** Keep the current architect, single-builder, and eight-verifier chain. Freeze its task, policy, registry, prompts, and result schema at a trusted planning checkpoint; execute required verification commands in clean candidate worktrees; preserve typed reports and content-hashed artifacts before removing those worktrees. The orchestrator calculates coverage from verified records and passes the existing final manifest to the existing deterministic validator.

**Tech Stack:** Python 3.12+ standard library, Git, existing Codex CLI adapter, JSON Schema, unittest.

**Spec:** [Production release orchestration design](../specs/2026-11-03-production-release-orchestration-design.md).

**Parent plan:** [Production release orchestration](2026-11-03-production-release-orchestration.md), R0 evidence portion.

**Project:** https://github.com/users/lucronn/projects/8

**Issue:** https://github.com/lucronn/autodata/issues/186

**Status:** Planning reviewed and tracking verified in Issue #186 / Project #8. R0 evidence is the first scoped implementation task. The coordinator must commit the synchronized task/record checkpoint and pass its exact-base preflight before dispatch; this document alone does not authorize a builder.

## Global constraints

- Both independent banks retain their own identities, credentials, and opaque references.
- Production deployment is outside current autonomy authority.
- Every implementation task has a synchronized Issue/Project record and committed exact-base preflight.
- Builders use disjoint worktrees; migrations/shared contracts serialize; reviewers cannot approve their own code.
- Preserve existing Issue #184; do not silently close or absorb its maintenance scope.
- All eight current policy gates remain required. Do not change policy, thresholds, registry, registered agent prompts, or release authority in this slice.
- Required evidence and provenance coverage come from measured records, not an agent decision or successful provider process exit.
- No real provider/model call is part of implementation tests. A missing or unavailable provider must remain a blocked outcome, with deterministic test evidence retained separately.
- Normative documents remain under `docs/`; JSON fixtures and test helpers may remain beside the existing autonomy tests.
- Every post-planning architect, implementation agent, and review/gate agent uses `gpt-6.1-sol`, reasoning effort `medium`, and service tier `fast`, with Fast mode enabled and no fallback.

## Ownership and exclusions

One implementation owner changes the following files together; independent review examines the resulting commit.

| File | Responsibility |
| --- | --- |
| `scripts/autonomy/runner.py` | Trusted-input loading, v2 response validation, clean candidate checks, deterministic command execution, artifact copying, provenance measurement, per-agent records |
| `scripts/autonomy/orchestrator.py` | Immutable task handoff, gate scheduling, exact-SHA aggregation, measured final manifest |
| `scripts/autonomy/agent-output.schema.json` | Single checked-in v2 provider response schema and reusable evidence definitions |
| `scripts/autonomy/test_runner.py` | Schema, trust, scope, command, artifact, provenance, and unavailable-provider regressions |
| `scripts/autonomy/test_orchestrator.py` | Chain integration, aggregation, coverage, stale-report, and compatibility regressions |
| `scripts/autonomy/fixtures/provenance-v1/{population.json,source.json,extraction.json}` | Nonempty synthetic source/evidence population, explicitly labeled as regression data |
| `scripts/autonomy/fixtures/run_provenance_fixture.py` | Deterministic local check producing the typed provenance report used by the R0 source/data gates |

Do not modify `release_controller.py`, its tests, `validate_run.py`, the policy, CI workflows, application code, database migrations, or deployment files. The coordinator owns task JSON, Issue/Project synchronization, and canonical documentation updates outside this implementation slice. The release-controller owner consumes the added manifest metadata in a separate change.

This slice does not add parallel scheduling, retries, alternate-reviewer scheduling, or deployment. Preserve the current serial gate ordering and retain explicit failed/blocked evidence. Those capabilities cannot be claimed merely because retry settings exist in policy.

## Frozen inputs and SHA semantics

Use two distinct commit identities throughout:

- `trusted_base_sha`: the current repository HEAD captured by the coordinator/orchestrator before any provider runs. The plan, task JSON, pre-implementation record, policy, registry, prompts, and provider schema must exist at this commit.
- `subject_sha`: the commit the current phase inspects. Architecture and builder start at `trusted_base_sha`; successful builder output establishes `implementation_sha`; every verifier starts at that exact implementation commit.

The input task adds `evidence_contract_version: 2` and `task_ref`, a safe repository-relative JSON path under `docs/agents/tasks/`. Load `task_ref` using `git show <trusted_base_sha>:<task_ref>`. Require the external task file's authorization-bearing values to equal the committed task: task ID, repository, goal, builder, allowed paths, bounded contexts, inputs, outputs, acceptance tests, forbidden scope, compatibility, pre-implementation record, `execution`, and `verification`. Only `run_id` may be supplied as an external unique execution identifier. Reject unknown overriding fields.

The architect may return explanatory text and findings but may not replace these binding values or weaken verification. Its `task_contract` must equal the frozen projection containing `task_id`, `goal`, `bounded_contexts`, `inputs`, `outputs`, `acceptance_tests`, `forbidden_scope`, `compatibility`, `pre_implementation`, `execution`, and `verification`. Builder identity and path permissions remain authoritative in the frozen task/envelope. A missing v2 verification contract is blocked before builder invocation, even when the architect returns `pass`.

Load policy, registry, prompt content, and schema with `git show` at `trusted_base_sha`; never reload them from a mutable working checkout or a verifier's implementation commit. Preserve their raw-byte SHA-256 values and immutable copies in the run evidence. Verify policy thresholds and required gate names once, then pass this same object through the run.

Require a clean coordinator checkout at initial dispatch. The runner's CLI may accept an existing `subject_sha` for a verifier only together with a resolved trusted context supplied by the orchestrator; do not obtain trust from a provider response. Resolve commits with `git rev-parse --verify <sha>^{commit}`, require full lowercase 40-character SHAs, and require candidate ancestry with `git merge-base --is-ancestor <trusted_base_sha> <subject_sha>`.

Compare the loaded runner/orchestrator source bytes with their Git blobs at `trusted_base_sha` before a production-evidence run. Record their hashes. This prevents a modified local tool from silently presenting itself as the pinned tool. Unit tests can construct temporary Git repositories containing their tested tool version. Bootstrap R0 through coordinator-run tests and independent review; a candidate cannot certify its own new evaluator by changing the trusted version during the same run.

### Protected changes

Check committed changed paths against both `allowed_paths` and trusted policy `protected_paths`; include the registry and registered prompt paths as trust-bearing inputs even though the current policy does not list all of them. A normal implementation task touching any trust-bearing input or protected path is blocked by this runner. Independently reviewed policy/registry/workflow/migration changes need their own separately bounded workflow; R0 does not introduce an override flag.

### Mandatory model, reasoning, and Fast execution profile

The coordinator's machine task files under `docs/agents/tasks/2026-11-03-production-release/` and queue use the following exact top-level key. Preserve this interface rather than introducing a competing `execution_profile` key:

```json
{
  "execution": {
    "model": "gpt-6.1-sol",
    "reasoning_effort": "medium",
    "service_tier": "fast",
    "features": {"fast_mode": true},
    "allow_fallback": false
  }
}
```

Validate this object against the frozen task before any provider starts and copy it unchanged into every architect, builder, and verifier envelope. The schema uses constants for every value, including `allow_fallback: false`, and rejects unknown keys. A missing profile, alternate model, alternate reasoning level/tier, disabled feature, or fallback request is a configuration block, not permission to inherit user defaults.

`build_provider_command` must add these explicit argv elements for every invocation, including planning architecture inside the post-planning chain:

```python
[
    "--model", "gpt-6.1-sol",
    "-c", 'model_reasoning_effort="medium"',
    "-c", 'service_tier="fast"',
    "-c", 'features.fast_mode=true',
]
```

Keep `--ignore-user-config`; these settings are deliberate command-line configuration rather than an assumed local default. Store the requested `execution` object and actual argv in runner-owned evidence. An unsupported model/setting/tier, account rejection, or explicit conflicting runtime metadata blocks the run. Never retry with another profile. Record observed provider model/tier separately from the requested profile when the CLI exposes them; provider-authored prose that repeats the requested values is not runtime proof.

The official [configuration reference](https://developers.openai.com/codex/config-reference/) states that `service_tier = "fast"` maps to request value `priority`, and that Fast-mode availability depends on the active model/account. The [speed documentation](https://developers.openai.com/codex/speed/) specifies `service_tier = "fast"` with `[features].fast_mode = true`. Both pages were fetched on 2026-11-03. The existing API-key login does not itself establish that this identity can use the requested mode. If effective profile metadata is unavailable, preserve that limitation and leave real-provider certification blocked until the isolated experiment establishes support; do not claim that a mocked command test proves server-side Fast execution.

## Versioned typed contracts

Provider response schema version 2 is deliberately incompatible with the old three-field response. Keep the existing provider command flags and final release-manifest field names. Do not silently upgrade an old provider response or reuse old evidence as v2 evidence. Preserve old fixtures as synthetic tests of the legacy validator; add v2 runner/orchestrator fixtures separately.

Use the checked-in schema as the only schema supplied to Codex. Remove the inline schema construction from `run_agent`. Runtime validation uses explicit standard-library validators for the fixed records in this plan, not a general-purpose JSON Schema interpreter: check exact required/allowed keys, exact primitive types, enum/constant values, ID/hash/path formats, nested record shapes, role constraints, and cross-record references. Booleans are not integers. Unknown schema versions, record fields, or unsupported values fail closed. Add a schema-consistency test comparing each fixed validator's field/enum inventory with the corresponding checked-in `$defs` record so schema changes require matching validator/tests changes. Do not add a generic schema engine or a dependency that the existing first CI step cannot import.

The following declarations define the actual record fields. JSON Schema must give every object `additionalProperties: false` and require every listed field. Nullable fields are still required. IDs match `^[A-Za-z0-9][A-Za-z0-9._:-]*$`; commit SHAs and content hashes are lowercase hexadecimal of length 40 and 64 respectively; timestamps are ISO-8601 UTC. Relative refs reject absolute paths, empty segments, `..`, NULs, and backslashes.

```python
from typing import Literal, TypedDict

Decision = Literal["pass", "fail", "blocked", "needs_review", "not_applicable"]

class ArtifactRecord(TypedDict):
    artifact_id: str
    kind: Literal["command-result", "stdout", "stderr", "provider-response",
                  "test-result", "provenance-population", "provenance-result",
                  "trusted-input", "change-set"]
    ref: str                 # destination-relative path in the final evidence root
    sha256: str              # hash computed by the runner over retained bytes
    size_bytes: int
    subject_sha: str
    check_id: str | None

class Finding(TypedDict):
    finding_id: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: Literal["schema", "provenance", "quality", "security",
                      "reliability", "contract", "test"]
    path: str
    line: int                # zero means no source line
    message: str
    reproduction: str
    blocking: bool
    resolved_by: str | None
    evidence_ids: list[str]

class Assessment(TypedDict):
    check_id: str
    decision: Decision
    evidence_ids: list[str]
    explanation: str

class AgentResponseV2(TypedDict):
    schema_version: Literal[2]
    run_id: str
    task_id: str
    agent_name: str
    subject_sha: str
    decision: Decision
    summary: str
    task_contract: dict | None  # strict frozen task-contract definition in $defs
    findings: list[Finding]
    assessments: list[Assessment]
    evidence_ids: list[str]

class CommandRecord(TypedDict):
    schema_version: Literal[2]
    check_id: str
    subject_sha: str
    argv: list[str]
    executable: str           # runner-resolved absolute executable
    cwd: str                  # safe repository-relative directory; '.' allowed
    started_at: str
    finished_at: str
    status: Literal["completed", "timed_out", "unavailable"]
    exit_code: int | None
    stdout_id: str
    stderr_id: str
    output_ids: list[str]

class ProvenanceResult(TypedDict):
    schema_version: Literal[2]
    subject_sha: str
    population_id: str
    scope: Literal["synthetic-regression"]
    population_sha256: str
    eligible_ids: list[str]
    covered_ids: list[str]
    uncovered: list[dict]     # strict {fact_id: str, reason: str}
    records: list[dict]       # strict FactProof definition below

class FactProof(TypedDict):
    fact_id: str
    source_sha256: str
    extraction_sha256: str
    source_pointer: str
    extraction_pointer: str
    value_sha256: str         # canonical JSON encoding of the selected value
```

`task_contract` includes all existing required contract fields, the existing strict pre-implementation object, the exact `execution` object, and a strict `verification` object. The provider never supplies authoritative command exit codes, artifact hashes, or numeric coverage. It references only artifact IDs already supplied by the runner. Unknown evidence/check IDs, duplicate IDs, a stale subject SHA, or findings with dangling references block the response. Architecture must return the frozen contract and empty assessments; the builder returns `task_contract: null` and empty assessments; verifiers return `task_contract: null` and exactly one assessment per assigned check.

The builder response identifies its resulting commit; the runner compares that SHA with observed HEAD. The architect and verifiers identify the prescribed SHA. All unresolved findings remain in the final manifest; any `blocking: true` finding blocks completion, and critical/high findings block under existing policy regardless of the provider's decision. Medium/low findings remain visible with explicit disposition, not silently dropped.

### Trusted verification definition

`verification` contains `checks`, `provenance`, and `required_agent_evidence`. Each check has exactly:

```json
{
  "check_id": "autonomy-unit",
  "gate": "deterministic_ci",
  "argv": ["python3", "-m", "unittest", "discover", "-s", "scripts/autonomy", "-p", "test_*.py", "-v"],
  "cwd": ".",
  "timeout_seconds": 120,
  "expected_exit_code": 0,
  "outputs": []
}
```

Every required gate has at least one command. `argv` is a nonempty list of nonempty strings, executed with `shell=False`; permitted executable names are `python3`, `go`, and `node`, resolved before launch. No shell string, provider-chosen command, or provider-chosen environment is accepted. R0 uses only Python. Timeout is an integer in `1..1800`; expected exit code is exactly zero. Each output is `{artifact_id, kind, relative_path, format}`, with `format` restricted to `json` or `text`; provenance output must use its strict JSON definition.

`provenance` is `{check_id, population_ref, report_artifact_id}`. `population_ref` points to the committed synthetic fixture population. `required_agent_evidence` lists architecture, builder, and all eight gate response IDs; missing provider evidence cannot become optional after an outage. The coordinator records these exact definitions in the R0 machine task before its checkpoint.

## Candidate integrity and evidence execution

For builders, capture committed changes using `git diff --name-status -z --no-renames <trusted_base_sha> HEAD --`; parse NUL-delimited paths and treat a rename as a deletion and addition. This includes deletions and unusual path characters. Determine dirtiness independently using `git status --porcelain=v1 -z --untracked-files=all --ignored=matching`; allow no staged, unstaged, untracked, or ignored provider-created files outside the runner-designated artifact directory. Record status before provider execution to distinguish preexisting ignored fixture/runtime state from new provider-created files; require the isolated worktree to be initially clean.

After a builder commits, require HEAD to be a descendant of the base, at least one permitted implementation change, and a clean worktree. A commit followed by an uncommitted edit/deletion/untracked file is blocked. Verifiers cannot change HEAD or implementation files. Required commands run with `PYTHONDONTWRITEBYTECODE=1`, and all task-declared outputs must be written under a runner-created directory selected by `AUTODATA_EVIDENCE_ROOT`, outside the worktree. Reject a dirty worktree after commands or provider assessment. Keep this check independent of whether a commit was created.

Run required checks in a fresh worktree at `subject_sha` before invoking each verifier. Supply the verifier with the observed command reports and bounded log excerpts. Its role is to assess actual results and findings. A failed/missing/timeout command makes the gate non-pass even if the verifier says `pass`. If the provider is unavailable, retain successful check records but set the agent gate and chain to `blocked`.

Resolve the executable, capture UTC start/end, status, exit, stdout, and stderr in the parent process. Execute every required check once per gate; R0 does not deduplicate across gates or retry failed attempts. On the supported Linux runner, start a new process session, capture bounded stdout/stderr, and terminate the entire process group on timeout or output-budget exhaustion: SIGTERM, up to two seconds of grace, then SIGKILL and reap. Do not let a child continue modifying artifacts after its parent timed out. Apply the same bounded termination helper to the provider process. Capture timeout output with status `timed_out` and exit code null, and unavailable executable with status `unavailable` and exit code null. A real completed nonzero process has status `completed`, its actual exit, and a failing check. Output-budget exhaustion is a blocking execution finding. Do not collapse these outcomes into a generic provider exit.

Pass only the existing secret-filtered environment plus fixed check metadata (`AUTODATA_EVIDENCE_ROOT`, `AUTODATA_SUBJECT_SHA`, `AUTODATA_CHECK_ID`, `PYTHONDONTWRITEBYTECODE`). Preserve external isolation requirements: filtering variable names does not remove filesystem credentials, prevent all network access, or establish that a command cannot incur cost. The deterministic acceptance runner must be provisioned without provider/source credentials and without outbound provider access.

### Artifact containment and retention

The runner owns the external output directory and creates one initially empty per-check staging directory. Require declared output files to be regular files, with no symlink in any path component; reject hard links (`st_nlink != 1`), FIFOs, sockets, devices, directories, absolute paths, traversal, and files escaping the resolved staging root. Enforce 16 MiB per declared artifact and 64 MiB per check. Use exclusive destination creation and copy bytes from an opened descriptor after checking `lstat`/`fstat` identity; hash the retained destination bytes. Validate the destination again before final aggregation. Never trust a provider-supplied hash or resolve an arbitrary path from its text.

Retain redacted stdout/stderr as generated artifacts and hash those exact retained bytes. If a structured data artifact contains a credential pattern detected by existing redaction logic, withhold it, retain a redacted diagnostic, and block the check; do not silently alter the artifact and call the original validation successful. No raw secret-bearing artifact is published in the bundle.

Copy reports and declared evidence before worktree removal. Preserve failure artifacts, command logs, response parse errors, and the candidate change set even when cleanup fails. Cleanup errors add a blocking runner finding. Aggregate references point within the final run root, not into removed worktrees or mutable temporary directories. A second run never overwrites the first.

## Exact coverage calculations

### Evidence completeness

Freeze the required artifact slots before execution. They are the trusted task/policy/registry/schema snapshots, candidate change set, architecture and builder responses, eight gate responses, and each required check's command report, stdout, stderr, and declared outputs. IDs are namespaced by gate/check so repeated filenames do not collide.

Let `E` be that nonempty set of required slots. Let `V` contain only slots whose retained artifact exists, passes type/format/size/containment checks, has the expected subject context, and whose recomputed destination hash matches the manifest. Compute `evidence_completeness = len(V) / len(E)`, and retain sorted `required_ids`, `verified_ids`, `missing_ids`, and both counts. Duplicate IDs, unexpected aliases, and extras do not increase the numerator. A failed test can have complete evidence; successful command execution is a separate required predicate.

### Provenance fixture and coverage

The initial fixture is intentionally small and nonempty. `source.json` and `extraction.json` both contain these two facts, with extraction additionally allowed to carry source pointers as metadata:

```json
{"facts":[{"id":"fixture:engine","value":"2.0 L"},{"id":"fixture:drive","value":"AWD"}]}
```

`population.json` contains `population_id: "r0-provenance-v1"`, `scope: "synthetic-regression"`, and two records with `fact_id`, `source_ref`, `source_pointer`, `extraction_ref`, and `extraction_pointer`. The engine pointers are `/facts/0/value`; the drive pointers are `/facts/1/value`. Refs resolve to the two neighboring fixture JSON files. These are explicit synthetic facts, unrelated to licensed provider content.

Load the population and fixture source/extraction bytes at `trusted_base_sha` and copy them into evidence. The deterministic fixture command reads the candidate fixture, resolves the declared JSON pointers, compares values without conversion, computes SHA-256 over `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`, and emits `ProvenanceResult` under `AUTODATA_EVIDENCE_ROOT/provenance.json`.

The runner independently replays the same pointer/value checks from the pinned trusted population and retained source/extraction bytes. It verifies every claimed proof's source hash, extraction hash, pointers, and value hash. This small synthetic fixture is a test oracle, not an inference from model text. Candidate code cannot shrink the trusted population to increase coverage.

Let `P` be the exact set of distinct eligible fact IDs from the trusted population. Require the result's eligible IDs to equal `P`, covered IDs to be unique and a subset of `P`, and uncovered IDs/reasons to equal `P - C`. Let `C` contain only independently verified proofs. Compute `fast_lane_provenance_coverage = len(C) / len(P)`; the intact fixture measures `2 / 2`, while one broken pointer/value measures `1 / 2`. Missing proof records, duplicate IDs, claimed coverage without a valid proof, or a fabricated covered/eligible list blocks the report.

If `P` is empty, record `ratio: null`, `eligible_count: 0`, `covered_count: 0`, and block the source/data gates. Do not emit 1.0 for an empty population. The legacy top-level numeric field may be null only in this blocked manifest; the existing validator will also reject it. Do not modify protected policy or introduce a no-publication exemption.

Store `coverage_scope: "synthetic-regression"`, the population ID/hash, IDs, counts, and computed ratio alongside the existing top-level fields. Both R0 source and data-quality gates consume independently executed reports for the same nonempty population. `verification.provenance.check_id` selects `source-fixture` as the canonical measurement; require `quality-fixture` to have the same independently verified IDs/counts, without unioning their results or choosing the better ratio. They never represent authenticated source access, real publication quality, or a staging canary. R6 requires its own population and actual authenticated/staging acceptance evidence. This v2 synthetic-only adapter cannot accept that evidence: the separately scheduled `r6-evidence-adapter` task must add and independently verify a versioned staging-population adapter before R6 begins. Its scope includes the runner, orchestrator, schema, tests and the staging collector; the resulting tooling is promoted to a new trusted checkpoint before it evaluates an application release. R0 remains an evidence-tooling regression gate, not a production-release certification.

### Final pass expression

The orchestrator may emit `decision: pass` only if: the frozen pre-implementation record passed; architect and builder are usable; the candidate is clean and in scope; every required command completed with exit zero; every required provider response is valid and passes; no blocking or critical/high finding remains; each gate's observed and reported subject SHA equals the candidate; all required artifacts verify; and measured coverage meets trusted policy. Then invoke the existing `evaluate` with the frozen policy and final evidence root. Preserve its failures. A provider response, CLI exit, or synthetic fixture alone never satisfies this expression.

## Proposed interfaces

Keep these functions in the two existing modules; do not add a framework or third runtime module.

```python
# runner.py; record aliases correspond to the strict schema definitions above.
def load_trusted_inputs(repo_root: Path, trusted_base_sha: str,
                        task_ref: str) -> dict: ...
def validate_execution_profile(execution: object) -> list[str]: ...
def build_provider_command(provider: str, cwd: Path, output_file: Path,
                           schema_file: Path, *, execution: dict) -> list[str]: ...
def validate_agent_response(value: object, schema: dict,
                            expected: dict) -> list[str]: ...
def inspect_candidate(worktree: Path, trusted_base_sha: str,
                      subject_sha: str, role: str,
                      allowed_paths: list[str], trusted: dict) -> dict: ...
def execute_required_checks(worktree: Path, subject_sha: str,
                            checks: list[dict], output_root: Path,
                            environment: dict[str, str]) -> tuple[list[dict], list[dict], list[dict]]: ...
def retain_artifact(staging_root: Path, relative_path: str,
                    destination_root: Path, artifact_id: str,
                    kind: str, subject_sha: str,
                    check_id: str | None) -> dict: ...
def measure_provenance(population: dict, retained_inputs: dict,
                       report: dict, subject_sha: str) -> dict: ...
def run_agent(repo_root: Path, envelope: dict, provider: str,
              output_root: Path, timeout_seconds: int = 1800,
              *, trusted: dict | None = None) -> tuple[int, Path]: ...

# orchestrator.py
def validate_verification_contract(task: dict, trusted: dict) -> list[str]: ...
def calculate_coverage(required_ids: set[str], artifacts: list[dict],
                       provenance: dict, evidence_root: Path) -> dict: ...
def validate_evidence_bundle(manifest: dict, trusted: dict,
                             evidence_root: Path) -> dict: ...
def aggregate_gate_reports(run_id: str, implementation_sha: str,
                           provider_runs: dict[str, dict]) -> dict[str, dict]: ...
```

`load_trusted_inputs` returns `{trusted_base_sha, task, policy, registry, schema, prompts, artifacts}`. `validate_execution_profile` accepts only the exact configured values; `build_provider_command` requires that validated object and never defaults it. `expected` contains run/task/agent identity, subject SHA, role, assigned check IDs, and available artifact IDs. `inspect_candidate` returns `{subject_sha, changed_paths, status_entries, findings}`. `execute_required_checks` returns `(command_records, artifact_records, findings)`. `measure_provenance` returns `{scope, population_id, eligible_ids, covered_ids, uncovered_ids, eligible_count, covered_count, ratio, findings}`. `calculate_coverage` returns both existing top-level ratios plus the detailed evidence/provenance measurement objects. Any parsing, containment, duplicate-ID, or identity error returns a blocking finding rather than a reduced denominator.

`validate_evidence_bundle` is a read-only public seam for the separately owned release controller. It derives required slots/checks from `trusted.task.verification`, reopens retained reports and files, rechecks the requested execution profile and subject identities, recomputes hashes/counts/ratios, checks successful actual command records and independent assessments, and invokes the unchanged `evaluate`. It returns `{passed, failures, measurements}`. Reject any declared manifest metric that differs from the recomputed metric. The orchestrator uses this function before returning zero; the release-controller owner must also use it for v2 bundles rather than relying on `evaluate` alone. This supplies hardened bundle validation without editing `validate_run.py` in R0.

For standalone `run_agent`, absent `trusted` means construct trust from the clean current HEAD and committed task reference before creating output directories or a worktree. For orchestration, the coordinator passes one resolved `trusted` object to all agents. Never derive a fresh trusted base from the verifier's candidate commit.

Preserve exit codes `0` (complete policy pass), `20` (recorded deterministic/policy failure or safe block), and `30` (configuration/input error before usable run artifacts). Store runner-owned `agent_decision` separately from the provider response: use `blocked` for unavailable/malformed input or any runner-integrity error, `fail` for a completed failed required command or a reproducible blocking finding, and otherwise retain the validated provider decision. Individual architecture/builder runs may still return 20 because they do not constitute the complete eight-gate release bundle. `_provider_result` and `_agent_usable` must read this runner-owned state and its findings; they cannot take a raw response's `pass` or treat all code-20 cases as usable.

## Concrete todo and implementation tasks

### Task 1: Version and validate the evidence contracts

**Files:** schema, `runner.py`, `test_runner.py`. **Consumes:** frozen contract design above. **Produces:** `validate_agent_response` and one schema source.

- [ ] Add `EvidenceSchemaTests` with valid architecture/builder/verifier responses, old three-field response rejection, unknown-property rejection, boolean-as-integer rejection, duplicate IDs, dangling evidence, wrong role payload, stale SHA, and missing typed findings/assessment fields.
- [ ] Extend the existing provider-command regression to require the exact model, medium reasoning, Fast tier/feature flags and no duplicate conflicting options. Add negative profile cases for missing configuration, wrong model/effort/tier, false Fast feature, enabled fallback, and unknown keys; assert every architect/builder/gate envelope receives the identical frozen `execution` object.
- [ ] Run `python3 -m unittest discover -s scripts/autonomy -p test_runner.py -v`; confirm new tests fail for the missing v2 boundary.
- [ ] Implement explicit strict validators for the fixed typed records and role/identity relationships. Add the field/enum inventory consistency check against the schema file; load that file rather than constructing a second inline schema.
- [ ] Add explicit execution-profile argv propagation; a provider rejection or conflicting observed profile must return a block with the requested profile retained, without invoking another profile.
- [ ] Re-run the focused suite and validate that legacy provider JSON produces a clear `schema_version` block without being promoted to pass.
- [ ] Commit the reviewed schema boundary within the task worktree.

Regression assertion shape:

```python
errors = validate_agent_response(
    {"decision": "pass", "summary": "all good", "task_contract": None},
    schema, expected_verifier,
)
self.assertTrue(any("schema_version" in error for error in errors))
self.assertTrue(any("subject_sha" in error for error in errors))
```

### Task 2: Freeze trust and enforce complete candidate scope

**Files:** `runner.py`, `orchestrator.py`, both test files. **Consumes:** v2 schema. **Produces:** `load_trusted_inputs`, `inspect_candidate`, immutable task handoff.

- [ ] Add `TrustBoundaryTests` using temporary real Git repositories: dirty local policy, candidate-modified policy/registry/prompt/schema, missing committed task, external task override, non-ancestor candidate, and architect weakening a required check all block before builder/provider invocation.
- [ ] Add `CandidateScopeTests`: in-scope deletion, out-of-scope deletion, rename crossing scope, filenames with whitespace/newlines, commit followed by dirty edit/deletion/untracked file, ignored output outside staging, verifier commit, and protected-path modification.
- [ ] Run the focused tests and confirm current deletion filtering and mutable-policy loading fail these cases.
- [ ] Implement Git-blob trust loading, exact task comparison, ancestry checks, NUL-delimited deletion-inclusive scope accounting, and independent dirtiness checks before cleanup.
- [ ] Run both autonomy runner/orchestrator suites; confirm blocked preflight still creates no provider invocation/worktree.
- [ ] Commit the independently testable trust/scope boundary.

Required deletion assertion:

```python
result = inspect_candidate(worktree, base_sha, candidate_sha,
                           "implementation", ["apps/api-go/**"], trusted)
self.assertIn("workers/ingestion-python/removed.py", result["changed_paths"])
self.assertTrue(any(f["finding_id"] == "runner.path-scope"
                    for f in result["findings"]))
```

### Task 3: Execute checks and retain verifiable artifacts

**Files:** `runner.py`, `test_runner.py`. **Consumes:** frozen checks and clean subject. **Produces:** command/artifact records from `execute_required_checks` and `retain_artifact`.

- [ ] Add `EvidenceExecutionTests` using a local Python fixture process, never Codex: success, nonzero exit with claimed pass, timeout with a surviving child process, missing executable, undeclared output, missing declared output, malformed JSON, oversized output/log streams, symlink/hardlink/FIFO/traversal, post-copy tampering, dirty worktree after tests, and cleanup failure.
- [ ] Assert actual stdout/stderr, resolved argv, timings, exit/status, subject SHA, and destination hashes; assert no hash or exit supplied by provider text can replace them.
- [ ] Implement direct argv execution, fixed staging/environment, bounded artifact validation, copy-before-cleanup, and redaction/withholding behavior.
- [ ] Re-run the focused suite; confirm failed and unavailable executions retain their own evidence and cannot be marked passed by an agent response.
- [ ] Commit the command/evidence boundary.

Required failed-command assertion:

```python
commands, artifacts, findings = execute_required_checks(
    worktree, candidate_sha, [failing_check], output_root, safe_environment,
)
self.assertEqual(commands[0]["status"], "completed")
self.assertEqual(commands[0]["exit_code"], 7)
self.assertTrue(any(item["kind"] == "stderr" for item in artifacts))
self.assertTrue(any(item["blocking"] for item in findings))
```

### Task 4: Measure nonempty provenance regression evidence

**Files:** `runner.py`, new fixture files/helper, `test_runner.py`. **Consumes:** pinned population and retained artifact bytes. **Produces:** independently measured provenance proof.

- [ ] Add the two-fact fixture exactly as specified and a helper accepting `--population`, reading `AUTODATA_SUBJECT_SHA`, and writing only `provenance.json` beneath `AUTODATA_EVIDENCE_ROOT`.
- [ ] Add `ProvenanceMeasurementTests` for 2/2, 1/2, empty population, dropped eligible ID, duplicate ID, foreign covered ID, missing proof, stale source hash, wrong pointer, value change, fabricated ratio property, and wrong subject SHA. The helper exits zero only when every eligible record is proved; partial proof exits one but retains the report.
- [ ] Implement runner replay of JSON-pointer/value checks and compute counts/ratios from the pinned population; do not consume a model-provided numeric ratio.
- [ ] Execute the helper in tests with a temporary output directory and verify its recorded SHA matches the real test commit. Assert explicit `synthetic-regression` scope in every retained result.
- [ ] Commit the fixture and measurement boundary after tests pass.

Required arithmetic assertions:

```python
measurement = measure_provenance(population, retained_inputs,
                                 report_with_one_invalid_pointer, candidate_sha)
self.assertEqual(measurement["eligible_count"], 2)
self.assertEqual(measurement["covered_count"], 1)
self.assertEqual(measurement["ratio"], 0.5)
empty = measure_provenance(empty_population, retained_inputs,
                          empty_report, candidate_sha)
self.assertIsNone(empty["ratio"])
self.assertTrue(any(item["blocking"] for item in empty["findings"]))
```

### Task 5: Aggregate actual gate evidence without losing failures

**Files:** `orchestrator.py`, `test_orchestrator.py`, runner integration seam. **Consumes:** typed agent/command/artifact records. **Produces:** final legacy-compatible manifest with v2 provenance metadata.

- [ ] Add `EvidenceAggregationTests`: complete fixture chain, one missing gate, verifier at a different observed/reported SHA, nonzero check with provider pass, blocking medium finding, unavailable provider after successful checks, removed artifact, tampered copied artifact, empty required evidence set, duplicate artifact IDs, one missing required slot, and fabricated provenance counts.
- [ ] Replace assigned verifier SHAs with observed validated SHAs; preserve every finding and command; copy all referenced gate artifacts into the final bundle and update refs/hashes deterministically.
- [ ] Calculate required-slot completeness and provenance from retained evidence; require nonempty denominators. Keep `coverage_scope` visible and invoke `evaluate` with the frozen original policy.
- [ ] Expose `validate_evidence_bundle` for independent revalidation; add tests that tamper only the manifest ratios/counts/required-slot declarations and confirm trusted task requirements prevent approval.
- [ ] Make the existing mocked chain test supply actual local command/artifact evidence; remove its assumption that eight summary-only passes can certify a run.
- [ ] Run `python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v`, the existing synthetic validator fixture, and `git diff --check` once after the integrated change.
- [ ] Commit the bounded R0 candidate and request independent review at that exact SHA.

Required missing-slot assertion:

```python
coverage = calculate_coverage(required_ids, artifacts_missing_one,
                              verified_provenance, evidence_root)
self.assertEqual(coverage["evidence"]["required_count"], len(required_ids))
self.assertEqual(coverage["evidence"]["verified_count"], len(required_ids) - 1)
self.assertEqual(coverage["evidence_completeness"],
                 (len(required_ids) - 1) / len(required_ids))
```

## R0 required check matrix

The coordinator commits these check definitions in the machine task. All commands run from the indicated clean candidate worktree. The R0 fixture population must exist at the trusted checkpoint used to exercise the newly hardened runner; its first implementation is verified through the bootstrap tests/review described above.

| Gate | Check ID | Cwd | Command |
| --- | --- | --- | --- |
| deterministic_ci | `autonomy-unit` | `.` | `python3 -m unittest discover -s scripts/autonomy -p test_*.py -v` |
| contract_compatibility | `provider-v2-schema` | `scripts/autonomy` | `python3 -m unittest test_runner.EvidenceSchemaTests -v` |
| schema_integrity | `typed-evidence-integrity` | `scripts/autonomy` | `python3 -m unittest test_runner.EvidenceSchemaTests test_runner.ProvenanceMeasurementTests -v` |
| source_provenance | `source-fixture` | `.` | `python3 scripts/autonomy/fixtures/run_provenance_fixture.py --population scripts/autonomy/fixtures/provenance-v1/population.json` |
| data_quality | `quality-fixture` | `.` | `python3 scripts/autonomy/fixtures/run_provenance_fixture.py --population scripts/autonomy/fixtures/provenance-v1/population.json` |
| security | `trust-and-scope` | `scripts/autonomy` | `python3 -m unittest test_runner.TrustBoundaryTests test_runner.CandidateScopeTests -v` |
| reliability | `evidence-failures` | `scripts/autonomy` | `python3 -m unittest test_runner.EvidenceExecutionTests test_orchestrator.EvidenceAggregationTests -v` |
| independent_review | `review-regressions` | `.` | `python3 -m unittest discover -s scripts/autonomy -p test_*.py -v`; independent reviewer additionally assesses the exact candidate diff |

For source and quality checks, declare one `provenance-result` JSON output at `provenance.json` with distinct artifact IDs. The matching strict report and check report are both required. Independent review is not satisfied by running the same tests: its valid separate provider assessment remains mandatory for automated chain completion.

## Verification commands and completion evidence

Run deterministic checks without model/source credentials or network calls:

```bash
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v
python3 scripts/autonomy/validate_run.py \
  --manifest scripts/autonomy/fixtures/pass.json \
  --policy .autodata-autonomy-policy.json \
  --evidence-root scripts/autonomy/fixtures/evidence \
  --json
git diff --check
```

The baseline is 41 autonomy tests at `0ed449fe5119484f8dd8f40b40607aa3beb11e49`. Record the resulting test count and exact implementation SHA; do not preserve that number as an expected total after adding cases. The legacy synthetic fixture must still pass the untouched validator, and summary-only/v1 output must fail at the new runner boundary.

R0 implementation acceptance consists of deterministic regression results, retained sample v2 success/failure bundles from fake providers and real local check processes, and independent review. Fake providers are injected in tests only; do not add a production CLI option that can emit fabricated provider passes.

Unattended real-provider certification is a separate required experiment after this candidate is independently verified and becomes the trusted base: use an isolated nonproduction automation identity and a bounded real fixture task; verify command flags, `gpt-6.1-sol`/medium/Fast support, schema acceptance, sandbox writes, local commit retention, malformed response, interruption, timeout, and evidence collection. The user's explicit multi-agent request and execution-profile instruction authorize the bounded necessary agent execution once the planning gate passes; do not ask for new consent solely because the CLI authenticates with an API key. Missing credentials or unavailable required capabilities remain actual external blockers. Until the experiment runs, record `provider_runtime_validation: blocked` with reason `not_executed` or the observed failure, and never describe the real chain as certified. Do not insert a synthetic pass into its place.

## External dependencies and handoff

1. Coordinator-created release Issue, verified Project #8 synchronization, canonical document updates, committed task/record/checkpoint, and passing preflight.
2. Independent coordinator/reviewer verification of the new tooling before it is promoted to `trusted_base_sha`; new fixtures and schema cannot authorize their own first run.
3. An isolated no-provider-credential environment for deterministic acceptance and an isolated nonproduction automation identity with the exact requested model/reasoning/Fast capability for the already-authorized bounded provider experiment. The installed CLI's API-key login establishes credential presence only, not those isolation/capability properties. No additional model-call consent gate is introduced.
4. Release-controller fixes and validation, owned separately. This plan preserves release-manifest fields but grants no release execution authority.
5. The `r6-evidence-adapter` prerequisite and then R6 authenticated both-bank/staging, production population, recovery, and deployment acceptance. R0's two synthetic facts and successful unit tests cannot satisfy those requirements.

The implementation owner returns the candidate SHA, full command results, v2 sample bundle paths, negative-case results, and unresolved runtime certification status. The coordinator updates tracking and canonical documentation from that evidence without marking unavailable external checks as passed.
