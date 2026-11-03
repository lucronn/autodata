# Runtime check environment and fixture assignment implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after independent planning review, a committed synchronized checkpoint and passing exact-base preflight. This canonical plan requires the synchronized committed checkpoint and passing exact-base preflight before implementation. It authorizes no provider call or live retry.

**Goal:** Resolve the observed wsicu runtime check-version/environment and fixture assignment mismatches without weakening strict evidence, redaction, runtime profile or global certification gates.

**Architecture:** Retain the existing producer's exact resolved executable reports and explicitly recognize Python3.11 in replay. Build separate sanitized environments for trusted required checks and guarded provider processes. The coordinator supplies one owned executable TMPDIR beneath the existing /evidence mount; generated prompts scope only this synthetic task's assigned verifier turns to their retained local evidence while global replay still evaluates every gate.

**Tech Stack:** Existing Python standard library, Git, Docker, pinned Codex0.162.1 app-server. No package/image rebuild or new dependency is required.

**Spec:** docs/superpowers/plans/2026-11-03-app-server-runtime-contract.md; docs/superpowers/plans/2026-11-03-runtime-disabled-notification.md; docs/agents/runner-interface.md; docs/agents/pre-implementation-gate.md.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Inspected diagnosis base: 258bdfe0eabf76409d4b3f93932f92f8bd548278.

## Planning status and evidence

Planning only. Save the canonical reviewed proposal as docs/superpowers/plans/2026-11-03-runtime-check-contract.md and its coordinator-owned tracking record as docs/agents/tasks/2026-11-03-production-release/r0-runtime-check-contract.json. Another independent agent must review this proposal before coordinator synchronization/gate. The coordinator must synchronize Issue/Project/canonical repository documents/concrete todo, commit the checkpoint, pin its exact SHA and pass validate_record before implementation. Re-read actual integrated code at that new base; this diagnosis SHA is not implementation authority.

Original failure: /tmp/autodata-appserver-success-wsicu05i, exit20/BLOCKED. Its synthetic fixture candidate5080c93b4d0f0d600ef7bcbaf707d2761b58d488 must never be integrated or pushed. Preserve this and all older trials unchanged. Independent original-root offline replay reproduced all41 failures and identical measurements;313 original run files were hash-identical afterward. Report: /tmp/autodata-runtime-wsicu-review.md; replay/facts/integrity artifacts share that prefix.

Confirmed causes:

- All8 required commands resolve to /usr/bin/python3.11. Producer runner.py1441-1473/1559-1563 retains that actual executable. Replay orchestrator.py532-542 admits only python3/python3.12/python3.13/python3.14. Every retained argv tail/cwd matches its frozen check;7 commands exit0 and deterministic_ci independently exits1.
- run_agent currently sends the same guard-prefixed environment to required checks and provider. Nested offline fixtures inherit the outer provider Git guard, obstructing their owned worktree cleanup.
- /tmp is noexec under the actual restricted Docker tmpfs. Executable fake Codex scripts created by tempfile cannot run there; PATH lookup can fall through to the real wrapper. Root's causal run in /tmp/autodata-runtime-offline-check-env moved TMPDIR to an owned executable /evidence child and used standard image PATH/no outer guard, with no source change/no auth/no Codex package/networknone. Those failures disappeared. Its105-test result still had2 failures/1 setup error attributable to Python3.11 frozen-command mismatch. This is diagnostic, not full acceptance.
- independent_review passed its assigned runtime-independent-review fixture assessment, but its overall decision blocked on unavailable upstream gate reports. The frozen generic review prompt demands the entire bundle while generated context supplies only local assigned evidence.
- Coordinator isolated reliability's one required-redaction marker to source dumping an intentional credential-pattern test fixture. Its assigned13 reliability tests passed. Strict redaction/raw replay correctly blocked. No raw pattern is copied into this plan.

## Global constraints

- Exact execution remains gpt-6.1-sol / medium / Fast, wire priority, features.fast_mode=true, allow_fallback=false. No settings/profile/notification/privilege/auth changes.
- Preserve all10 roles and all8 global machine gates; schema, policy, registry, validate_run.py, app_server_adapter.py, protected/frozen input semantics, task/candidate/root identities, raw transcript equality, strict redaction and cancellation/output/deadline bounds stay unchanged.
- Actual configured settings do not establish upstream served/billed tier. Synthetic provenance/fixture certification never establishes staging or release approval.
- Required checks keep their exact frozen argv tails, cwd, timeout60 where specified, expected exit0 and artifact identities. No test skips, reduced test inventories, command substitutions, output rewriting, changed expected exits or manufactured provider responses.
- Preserve HOME, CODEX_HOME, /tmp noexec, readonly root, nonroot uid1000, cap-dropALL, no-new-privileges, resource limits and root-owned readonly namespace proof. Executable scratch is inside the already authorized private /evidence bind; no new mount/capability is requested.
- No implementation/review provider calls, credentials, banks, production, GitHub mutation, push, merge or deployment. Offline acceptance has networknone, no auth, no actual Codex package and a fail-closed sentinel in place of the image wrapper.

## Exact ownership and interfaces

Builder implementation paths, exactly5 existing files:

1. scripts/autonomy/runner.py: sanitized base/check environment helper, provider-only guard wrapping, task-scoped generated assignment instructions.
2. scripts/autonomy/orchestrator.py: explicit Python3.11 resolved-name compatibility only.
3. scripts/autonomy/test_runner.py: environment, nested ownership, real prompt/scoping and existing redaction regression tests.
4. scripts/autonomy/test_orchestrator.py: Python3.11/full-bundle and strict command tamper regressions.
5. docs/agents/runner-interface.md: environment split, scratch prerequisites, explicit executable spelling and fixture-only decision semantics/limits.

No .cursor agent prompt change: full release independent-review duties remain intact. No new repository helper, launcher, schema field, task discriminator or public API. Keep _safe_environment(guard_bin: Path, isolated_config: Path) -> dict[str,str], execute_required_checks(...), build_agent_prompt(..., role=..., check_ids=...), run_agent(...) and replay APIs compatible. Add only private _sanitized_environment(isolated_config: Path) -> dict[str,str].

Coordinator owns gate/tracking/canonical plan edits and scratch files /tmp/autodata-runtime-supervisor.py, /tmp/autodata-runtime-check-contract-offline.py and /tmp/autodata-runtime-no-provider.py. Scratch changes are reviewed/hashed before execution and recorded separately from the5file implementation diff. No implementation agent mutates them without coordinator assignment. No image rebuild is planned; record the actual existing image digest.

## Task1: TDD for explicit executable compatibility

Files: test_orchestrator.py and orchestrator.py.

- [ ] Add a named FullChainV2Tests regression test_python311_resolved_command_matches_frozen_check. Use the existing retained full-chain fake fixture and update only each check report's resolved argv[0]/executable to /usr/bin/python3.11, retaining actual argv tails/cwd/subjects/IDs; refresh corresponding report/hash references and frozen provider prompt/protocol through the existing fixture builder, not by bypassing replay. Prefer fixture setup parameterization before prompt construction so prompts match actual retained reports. Baseline bundle must otherwise pass. The current replay must fail solely on frozen command matching. Retain red output.
- [ ] Add test_resolved_python_compatibility_preserves_exact_command_binding with subcases for wrong tail, wrong cwd, nonabsolute executable, argv[0]!=executable, unknown python3.111/python2 basename, stale subject and altered output IDs. Use otherwise valid evidence and refreshed hashes so each negative reaches the intended validator. Existing root/causality/profile tamper regressions remain active.
- [ ] Add only the explicit python3.11 string to the existing accepted Python basename tuple. Keep command[argv][1:] exact equality, argv[0]==executable, absolute-path _command_errors, cwd equality, subject/status/exit/output checks unchanged. Do not use startswith/python regexes, realpath guesses during replay, an arbitrary interpreter alias, or normalize retained bytes.

Representative final predicate change is only:

```python
(check["argv"][0], "python3.11", "python3.12", "python3.13", "python3.14")
```

- [ ] Run both new regressions and existing AppServerReplayTests/FullChainV2Tests, retaining actual logs. This accepts the resolved Python3.11 spelling, not a new attestation of arbitrary executable binary provenance beyond the existing command contract. Actual image compatibility is separately tested below.

## Task2: TDD for check/provider environment separation

Files: test_runner.py and runner.py.

- [ ] Add named RunnerTests regressions test_required_checks_receive_sanitized_unguarded_environment and test_provider_keeps_owned_command_guards. Patch a trusted parent environment with a known ordinary PATH, HOME, TMPDIR, a nonsecret variable and synthetic blocked variable names; never read real credentials. Observe run_agent passing distinct environments to execute_required_checks and app_server.run_app_server. Check retained filtering, CI/Git isolation flags, PYTHONDONTWRITEBYTECODE=1 and identical HOME/TMPDIR. Only provider PATH has this runner's guard prefix. Retain failures before changing implementation.
- [ ] Add test_nested_fixture_owns_its_git_guard_and_cleanup: under the check environment, run a miniature existing nested fake-runner fixture using a real private Git repository; verify nested setup/owned forced-worktree cleanup succeeds through actual Git. Verify its own provider process still cannot execute blocked Git/external commands. Do not mock away cleanup or strip arbitrary PATH components. The outer check environment must never acquire the outer provider guard in the first place.
- [ ] Extract existing environment filtering/CI/Git-isolation setup into _sanitized_environment(config), preserving current blocked-name filters and explicit excluded variables. It returns the ordinary trusted caller PATH, unchanged HOME/CODEX_HOME/TMPDIR and isolated GH configuration. No credentials are added and no process environment is dumped.
- [ ] Keep _safe_environment(guard, config) as the provider-only wrapper, returning a fresh sanitized mapping with only PATH prepended by its own guard. It must not mutate os.environ or a shared dictionary.

```python
def _safe_environment(guard_bin, isolated_config):
    environment = _sanitized_environment(isolated_config)
    environment["PATH"] = f"{guard_bin}{os.pathsep}{environment.get('PATH', '')}"
    return environment
```

- [ ] In run_agent create check_environment=_sanitized_environment(config) and provider environment through _safe_environment(guard,config). Set PYTHONDONTWRITEBYTECODE=1 in both. Pass check_environment only to execute_required_checks; keep provider environment for runtime_expected/codex_home, run_app_server and invocation executable resolution. Candidate setup/inspection/Git calls remain runner-owned. No general removal of guards from arbitrary inherited PATHs is authorized: the coordinator starts the outer process with the reviewed ordinary image PATH, and each nested test runner creates its own provider guard.
- [ ] Re-run RunnerTests, TrustBoundaryTests, EvidenceExecutionTests, IntegrityEdgeTests, CallerSignalTests and existing real fake-process suites. Existing _safe_environment callers/signature remain valid. Required checks are trusted frozen programs; this split does not grant provider subprocesses the trusted check environment.

## Task3: TDD for fixture-only local review decisions and safe evidence use

Files: test_runner.py and runner.py. Leave all .cursor agent base prompts unchanged.

- [ ] Add test_runtime_fixture_assigned_verifier_prompt_scopes_local_decision using the actual frozen .cursor/agents/autodata-review-agent.md text loaded from the pinned base, real envelope.task_id, assigned check IDs and retained artifact IDs. Assert that generated assignment explicitly resolves the generic whole-bundle duty for this turn, describes local response decision, prohibits evidence invention/additional checks/broad source dumps and retains credential-pattern prohibitions. Assert no upstream gate report is falsely claimed supplied.
- [ ] Add test_nonfixture_review_retains_full_review_duty using the same real base prompt but a different task_id, and an unassigned architect/builder fixture turn. No local-verifier exception may appear. Existing full release review instructions remain unchanged.
- [ ] Add test_fixture_local_pass_does_not_hide_missing_global_gate through existing full-chain validation: valid local assigned pass is allowed, but removing/failing any upstream required gate/artifact or inserting unknown assessments/evidence IDs still blocks. Reuse existing full-bundle fake fixtures and strict validators, not a new permissive model stub.
- [ ] Add only a scoped block in build_agent_prompt for envelope.get("task_id") == "production-release-runtime-fixture" and nonempty assigned check_ids (preserve existing callers that omit task_id), using the already validated frozen task identity. No new schema/registry/task fields are needed. The block explicitly takes precedence over the generic whole-bundle duties for this fixture assignment only. Its frozen content must communicate all of:

```text
SYNTHETIC RUNTIME FIXTURE — LOCAL VERIFICATION ASSIGNMENT
For this turn, assess only the exact assigned check IDs using the supplied
runner command records and their retained artifacts. Your response decision
is local to these assignments; it does not assert overall certification,
upstream gate success, staging readiness or release approval. Generic final
whole-bundle review duties apply when that complete bundle is actually
assigned and supplied; it is not supplied in this fixture turn. The independent
coordinator/machine replay still validates all ten roles and eight gates.
Return pass only if the assigned evidence is complete, matching and passing
and no concrete observed blocker remains. Otherwise return blocked/fail with
precise findings; never fabricate unavailable evidence or suppress a genuine
observed integrity/security problem. Assess each assigned ID exactly once.
These checks have already executed. Do not run additional commands/checks,
inspect or dump unrelated source/test files, or search for upstream reports.
Do not print credential-pattern examples, including intentional synthetic test
fixtures. Use supplied evidence IDs and safe summaries only; strict redaction
and exact raw replay remain mandatory. No provider, bank, GitHub or deployment
calls and no other agents.
```

- [ ] Keep the complete frozen envelope and exact prompt rebuilding in orchestrator; producer and replay both call the same build_agent_prompt. Keep response validation, all8 gate policy checks and complete raw transcripts unchanged. Do not force a response decision, silently rewrite findings, suppress a server frame or add redaction exceptions.
- [ ] Preserve/extend the existing redaction test with a synthetic credential-shaped source-output case constructed within tests; assert that changed protocol bytes still fail certification and no raw pattern reaches retained artifacts. Never copy the live problematic value into docs/logs. The intended fix is avoiding unnecessary emission, not making such emission acceptable. Prompt tests cannot prove future provider compliance.

## Task4: Coordinator executable scratch and fully offline restricted acceptance

Scratch ownership: coordinator only. Implementation builder first runs focused and full host offline suites at its exact committed5file candidate. No real provider invocation is authorized.

### Scratch launch contract

Extend /tmp/autodata-runtime-supervisor.py for the eventual live trial and implement /tmp/autodata-runtime-check-contract-offline.py for offline acceptance. Review and hash both before use. Both create an exclusive fresh private host run-root with no-remotes plain clone and metadata, and create one owned child mapped to /evidence/check-tmp before starting Python. Use container uid1000 to create/chmod that child0700 under its owned payload, recording lstat uid/mode/path and a nonsecret executable probe result. Do not chown recursively through arbitrary caller paths. Set TMPDIR=/evidence/check-tmp on the outer Python process from initial process startup; Python tempfile caches make setting it after imports insufficient. Do not set HOME, home, CODEX_HOME or global tempfile.tempdir. No source checkout or evidence ref is relocated into TMPDIR.

Keep /tmp explicitly rw,nosuid,nodev,noexec,mode1777; verify mountinfo. Verify /evidence/check-tmp permits execution of a newly written harmless probe as uid1000 and is neither symlink nor preexisting caller-owned directory. No chmod/mount exec change to /tmp and no capability/privilege escalation. Provider/check environments both inherit the approved TMPDIR; only provider PATH receives its runner guard. Outer coordinator PATH is the ordinary reviewed image PATH, not any provider guard. HOME remains /home/node and the fresh Codex home behavior remains unchanged.

Cleanup is ownership-bound and finite: stop/kill the actual owned container first on timeout/error; then attempt removal of only the recorded scratch child via symlink-safe shutil.rmtree with a10second deadline. Verify lstat/parent identity and owned root first; never follow a substituted symlink, use broad rm patterns or remove evidence/worktrees. If safe deletion cannot complete, retain the scratch/run-root, record cleanup failure and refuse success. Preserve all logs/artifacts/clone until review; never delete original wsicu evidence. Container stop5seconds, kill if needed, and inspection each use10second CLI bounds. Cleanup cannot extend an outer deadline. Host-after hashes/status and partial evidence are always attempted, even if Docker fails.

### Offline supervisor interface and no-provider guarantee

Named owner: /tmp/autodata-runtime-check-contract-offline.py, Python standard library plus existing Docker/Git; no unnamed future repository driver. Invocation:

```bash
python3 /tmp/autodata-runtime-check-contract-offline.py \
  --source-repo /home/corp/Documents/ChatGPT/autodata \
  --candidate-sha <independently reviewable 40hex committed implementation SHA> \
  --image autodata-runtime-fixture:codex-0.162.1-nonroot-bwrap \
  --run-root /tmp/autodata-runtime-check-contract-offline-<unique-token> \
  --total-timeout-seconds 420
```

Source must be clean at the selected SHA (or select coordinator-owned clean managed implementation worktree); run-root must not exist. Record observed source HEAD/status, exact image ID, runner code hashes, tracked-input manifest, script hashes and original-boundary restrictions. Use a UUID container name and save exact container ID/ownership before acting; no shared containers/projects.

Use networknone, readonly root, nonroot uid1000, cap-dropALL, no-new-privileges, same2CPU/2GB/pids256 limits, /tmp noexec and owned writable /evidence payload. No /opt/codex package, auth file, host sockets or credentials are mounted. Bind the reviewed coordinator sentinel /tmp/autodata-runtime-no-provider.py readonly over the image's /usr/local/bin/codex wrapper. Its shebang uses the actual image Python and it only appends a fixed invocation marker (no raw args/env) to the fixed owned /evidence/no-provider-audit.jsonl file and exits97. Do not mount actual Codex elsewhere; inspect that no actual package/binary is available. This sentinel is a negative backstop, not the fake used by tests. Any sentinel call is acceptance failure even if tests otherwise pass. Existing executable fake_codex fixtures must be selected and must run from TMPDIR. An intentional offline probe of the sentinel, if used, must have a separate audit file cleared by creating a fresh exclusive acceptance audit, not hiding acceptance calls.

All phases use monotonic per-command and global deadlines and process groups. Reserve final30seconds within the420second total. Preparation30seconds; probes15seconds; full exact-candidate suite90seconds; required8-check exercise180seconds; finalization30seconds, leaving75seconds slack. Never extend the global deadline. Timeout kills actual owned container/descendants and records failure. Signal handling enters the same bounded finalizer. If infrastructure cannot satisfy these bounds, fail/retain evidence rather than skip tests or silently enlarge budgets.

### Required offline evidence, exactly what executes

- [ ] Observe root readonly/nonroot/no-capabilities/no-new-privileges/networknone/no-auth/no-real-Codex, ordinary PATH, HOME unchanged, /tmp noexec, executable TMPDIR probe and actual python3 resolve to /usr/bin/python3.11 with reported Python3.11 version. Record safe summaries only.
- [ ] At exact implementation candidate, run full unittest discovery with argv `python3 -m unittest discover -s scripts/autonomy -p test_*.py -v`, PYTHONDONTWRITEBYTECODE=1 and approved TMPDIR, within90seconds. Save raw bounded test logs and actual counts. Require no skips/failures/errors, every new named regression executed, no removed baseline tests (baseline137 is a floor, not a copied result). Inspect collection/listing against the candidate source to catch omitted tests.
- [ ] Create a separate offline-only synthetic fixture child commit in this private clone containing exactly the runtime fixture file bytes required by the frozen task. Record candidate parent and child SHA separately and assert the sole diff is that one file. Never integrate/push this child. It is required because runtime-independent-review checks the fixture file; the implementation candidate itself must not include that file. Do not reuse or rewrite the live wsicu fixture candidate.
- [ ] Load trusted runtime-fixture task/policy/prompts at the reviewed implementation candidate. Execute all8 unchanged frozen required checks against the offline synthetic child using execute_required_checks, with _sanitized_environment and approved TMPDIR, all original per-check60second limits and output IDs. Save actual command/stdout/stderr/provenance artifacts under this owned offline run root. Require8 reports/statuscompleted/exit0, no command findings, unchanged clean child tree and correct subject binding; Python argv[0]/executable must be actual /usr/bin/python3.11. Full required deterministic_ci must complete under its original60second timeout, even though the standalone full-suite bound is90seconds. Existing required security and reliability selections must execute and pass.
- [ ] Verify candidate-version fake full-chain success and all strict command/root/causality/profile/unknown/redaction negatives through the full tests. This supplies offline end-to-end machine replay; do not call actual run_agent(local-cli) with a real runtime. Offline results must be labeled synthetic/offline and cannot be inserted into a live certificate.
- [ ] Require zero sentinel calls, no live networks/auth/package, original source/candidate tracked-file hash/status unchanged, exact candidate parent/fixture child relation, actual8 check identities/counts and all required output files/hashes. Never treat bare unittest exit0 or a package-only/zero-test run as proof. Collect finally-state/partial logs even on failure.
- [ ] Write acceptance-result.json atomically with phase deadlines/exits, actual tests/counts, eight check summaries, image/code/script hashes, safety probes, sentinel count, input-before/after hashes, cleanup status and primary/subsequent failures. Exit0 only if every condition passes;124timeout;1assertion/infrastructure/evidence/cleanup failure;2invalid arguments. Parent checks both exit and JSON. Missing/truncated evidence fails. Never dump environments, raw secret patterns or auth contents.

No offline acceptance has yet passed this proposal. Root's earlier executable-TMPDIR diagnostic is evidence for the cause only. The scratch supervisor itself requires read-only independent review before its acceptance run.

## Task5: Docs, immutable verification and handoff

- [ ] Update only docs/agents/runner-interface.md among implementation docs. Explain exact Python3.11 spelling, unchanged tail/cwd/path binding, trusted check/provider environment separation, executable owned TMPDIR prerequisite with unchanged HOME and /tmp noexec, fixture-only local assessment decision, all8 global gates/full release review unchanged, and strict redaction limits. Keep old failure facts and future live success unclaimed.
- [ ] Focused tests, followed by full offline suite and exact diff:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts/autonomy python3 -m unittest test_runner test_orchestrator -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v
git diff --check
```

- [ ] Retain red regressions, actual test counts/timings, preflight output and exactly5file diff. Commit only authorized implementation paths. Re-run verification at the exact immutable candidate; no fixes after review without a new SHA/re-review. Confirm clean status before/after.
- [ ] Independent implementation reviewer verifies candidate vs authorized base, real prompt scope, Python3.11 compatibility and all negative attacks, unchanged provider guards/redaction/profile/all8 gates, offline restricted evidence/sentinel and scratch supervisor ownership/bounds. No provider call. Reviewer reports exactSHA findings/approval and limitations; coordinator independently verifies/promotes only approved implementation commit, never synthetic fixture commits.

## Separate coordinator-only single live retry checkpoint

This proposal does not authorize another live attempt. After reviewed implementation integration and successful restricted offline acceptance, coordinator synchronizes and commits a separate fresh trial checkpoint identifying approved code/image/script hashes, reviewed executable scratch and unchanged authorized readonlyauth/boundary/layout/profile. Re-run exact-base preflight. Inspect actual launch without printing auth; preserve the original /evidence/run namespace and truthfully report standard Docker bridge unrestricted outbound networking for the authorized live fixture. No new integrations/credentials/privileges/mounts are introduced.

Only that checkpoint may authorize one fresh success-path retry with provider120seconds and outer trial400seconds, actual-container shutdown/finalization bounded by425seconds overall. No automatic retry. Preserve every failure unchanged; any unknown/warning/profile/redaction/command/test/scope/integrity failure stops and requires a separately reviewed decision. A local verifier pass cannot override missing global evidence. Retain actual10 roles, all8 gates, final candidate/command/provenance measurements and exact raw protocol/selected completed responses. Successful synthetic runtime evidence still does not approve staging/release or establish upstream served/billed tier. Never integrate/push the fixture child.

## Coordinator synchronization todo

1. Obtain another agent's independent planning review of this exact file/hash; resolve concrete blockers without widening scope.
2. Promote reviewed plan to canonical path; synchronize Issue186/Project8, runner docs, concrete todo and new five-path task record; commit and pin new implementation base.
3. Run validate_record at that committed base and retain passing output before implementation.
4. Assign five-path TDD implementation; retain red/green exact-SHA evidence. Separately review/hash coordinator scratch changes and run restricted offline acceptance with no auth/realcodex/network.
5. Obtain independent exact-candidate and scratch/evidence review; integrate only approved implementation. Keep all synthetic fixture commits quarantined.
6. Commit fresh trial-only synchronized checkpoint/preflight; authorize at most one bounded live retry and record actual outcome without readiness inflation.

## Independent planning review and dispatch checkpoint

The exact proposal11851c73b006b29747f41acffd09f0478bf13482fdcaae4e4741a6bc34a93825 passed independent planning review at inspected basec5cd1a22ff9cb7eeb5dbf71c3aac763fbec5a6cf. Review SHA256f0dfc17f2973de1aeeb63dda8509ea3ff39d4b2f2f76f2d5c669ab41a65daaa2 is retained at `/tmp/autodata-runtime-check-contract-independent-review.md`. No substantive plan changes were needed. This checkpoint synchronizes the five-file task/todo and separate coordinator scratch ownership; its exact committed SHA must pass machine preflight before dispatch. Prior trial results stay blocked.
