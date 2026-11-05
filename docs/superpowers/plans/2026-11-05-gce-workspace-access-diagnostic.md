# GCE workspace-access diagnostic implementation plan

> For agentic workers: planning and tracking are synchronized. Execute only after the actual checkpoint is committed/sealed, committed-base preflights pass, independent checkpoint review passes and explicit narrow dispatch is given.

**Goal:** Diagnose UID1000 source and temporary-path access on a fresh hosted checkout of exact Task65 source without modifying the required verification workflow or granting repair or acceptance credit.

**Architecture:** A standalone five-minute push job observes a fixed Task65 checkout under ambient and sanitized UID1000 identities, then retains the unchanged original first preflight result and fail-closed cleanup evidence. The new workflow is defined by the pushed branch revision and deliberately absent from the fixed target checkout.

**Tech stack:** GitHub Actions, Bash, Python3.12 and existing host metadata tools. No package installation.

**Spec:** `docs/agents/specs/2026-11-05-gce-workspace-access-diagnostic.json`. The corrected proposal below supplies the complete frozen assembly, inline Bash and validation contract; independent corrected-design review passed (external design only; receipt below).

## Task67: standalone GCE workspace-access diagnostic — synchronized planning; checkpoint pending

Goal: Diagnose UID1000 source and temporary-path access on a fresh hosted checkout of exact Task65 source without modifying the required verification workflow or granting repair or acceptance credit.

Status: synchronized planning and tracking; actual checkpoint commit/seal, exact-base preflights and independent checkpoint review remain pending. Current implementation allowlist=[]; all authorities and dispatch flags=false; accepted_case_credit=0; accepted_new_case_credit=0; verified_case_ids=[]; release_state=unverified.

Materialization parent and observed source `25d44588cb1ab82fab3e39d28ef1ee5a12b5fb44`, tree `264fc8d7711c461d781d7eaa7af34391c802edac`; assigned branch `codex/gce-workspace-access-diagnostic`. The isolated checkout is materialized directly at that exact source on the assigned branch; never reset an unrelated branch or substitute current orchestration/Task66/default HEAD. Null committed checkpoint_sha/checkpoint_tree/implementation_base_sha are intentional; actual post-commit values belong externally in `/home/corp/autodata-evidence/task67-diagnostic-gate/CHECKPOINT.json`.

Plan `docs/superpowers/plans/2026-11-05-gce-workspace-access-diagnostic.md`; spec `docs/agents/specs/2026-11-05-gce-workspace-access-diagnostic.json`; standalone record `docs/agents/records/2026-11-05-gce-workspace-access-diagnostic.json`; task `docs/agents/tasks/2026-11-03-production-release/gce-workspace-access-diagnostic.json`; verification `docs/verification/2026-11-05-gce-workspace-access-diagnostic.md`. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8; existing item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`. Root is the sole tracking writer.

Tracking synchronized by root at `2026-11-05T07:24:33.095813Z`: Issue https://github.com/lucronn/autodata/issues/186#issuecomment-6652269167 and existing Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`. Before snapshot `/home/corp/autodata-evidence/task67-tracking/before-publish.json` SHA256 `646f09e4d3cdec5fba20c089e823cec636a24e6bb3f42327c31b9f9fca107faf`; after/readback snapshot `/home/corp/autodata-evidence/task67-tracking/after-publish.json` SHA256 `13f666da95fa6a2d6a7de0d1bddb784ecc009962e0993c59bc4d26c20a8b092e`; preservation proof `/home/corp/autodata-evidence/task67-tracking/TRACKING-PRESERVATION-VERIFY.json` SHA256 `9ccdbc56a51450ced2786a8fbfa3e2e87139f8f5423581a7dbb5deb7b3df6af8`. The Issue body, all271 prior comments and other Project fields are preserved; the previous Project Source is retained verbatim in the new Issue comment. This establishes tracking alignment only.

Independent external gate-draft PASS `/home/corp/autodata-evidence/task67-gate-draft-independent/REPORT.md` SHA256 `f1ccf74e8bee833220af3170c06053c9462b20c630da60bab09d4b0f96a7f8b0` applies to the external draft only; checkpoint review is pending.

Exactly eight gate-document paths are enumerated in the plan/spec/record/task; the sole future implementation path is `.github/workflows/gce-workspace-access-diagnostic.yml`. Gate docs must be pushed before a separate workflow-only commit. The gate push may trigger the existing autonomous workflow; that is unrelated evidence. The later diagnostic push is branch-and-path scoped and may run once only after separate narrow dispatch. Its workflow revision/event SHA is distinct from its fixed Task65 checkout. No PR or workflow_dispatch trigger is planned.

Task65 source-push41983350226 and actual-PR41983396445 are terminal failures after607 development adapter tests OK, at the first required GCE source read with EACCES. Actual PR checkout `e4b00a767026de274885f75093588e37ba3bb69e` is distinct from source with the same tree. GCE discovery did not start; Compose validation and fake/live Compose smoke were skipped. DTO/R3 succeeded independently; ingestion's210 skips remain. Python3.12.15 versus3.12.16 does not prove causality. No inherited CI green. Supplemental local cross-UID lab evidence establishes neither hosted causality nor acceptance.

The future job observes metadata and runs the exact original UID1000 first preflight only. Preserve the existing required workflow/governance/R6 bytes and disabled profile. No helper/test/production change, source export, ACL/mode/group repair, alias creation, package install, GCE discovery, Compose or suite replacement is authorized. Missing/incomplete/mismatched provenance or cleanup evidence fails diagnosis. Green diagnostic grants no repair or acceptance credit.

Historical approved external proposal `/home/corp/autodata-evidence/task67-standalone-diagnostic-design/PROPOSAL.md` SHA256 `e8a9e4ebc22e270e36c887ab3aa687b0d679a92f0f772f71adf36aebe5d720f2`; historical independent design PASS `/home/corp/autodata-evidence/task67-standalone-diagnostic-review/REPORT.md` SHA256 `4463136c0a6a4f7b50e93956b41d4cc9c9ce1d5482c59ac3e62d03950c2ef53b`. That verdict applies to the original design only.

Planning correction after independent script preflight REVISE of checkpoint `2ba3d923112092e9ae98975f2e09496e3a755569`: both observer subprocess collectors now retain bounded output while draining/discarding excess under the existing deadline and cleaning their owned sessions; security labels read at most4097 bytes and report truncation. The original `run_gce` wrapper, original first preflight and DEVNULL search are unchanged. Revised immutable external proposal `/home/corp/autodata-evidence/task67-standalone-diagnostic-design-revised/PROPOSAL.md` SHA256 `559b97b40993099bc00c87b64d6cc6bc337fe14d34d713b036fc64e2afa299df`; corrected frozen Bash SHA256 (including final newline) `7f4557b390b433a14cc8cdfe6dbf82bfeec86c11898c22603cb7c2b8a4adb3d6`. Exact replacement `/home/corp/autodata-evidence/task67-script-preflight/BOUNDED-REPLACEMENT.md` SHA256 `f419da9be78a3f5c1c6b57e40b806ab9e55bdfeb1985a90c877a6a865f2bc98d`; independent original-script REVISE `/home/corp/autodata-evidence/task67-script-preflight/REPORT.md` SHA256 `91956f0978c48f95b786b2c6585f7857b51cd383146fbe4953f582c79353567e`. The original proposal/design PASS and gate-draft PASS remain historical and do not approve the corrected design. Independent corrected-design PASS (external design only) `/home/corp/autodata-evidence/task67-corrected-design-review/REPORT.md` SHA256 `0557d89e14ac9ec8982855cf377cc37b55b98446e9a0d0e5326608079b1d0644` approves the corrected frozen design only. Corrected checkpoint review and fresh narrow dispatch remain pending; synchronized goal/todos/tracking are unchanged. All authorities remain false, current implementation allowlist=[], credits0 and release unverified.

Todo:

- [ ] Preserve terminal Task65 source-push and actual-PR receipts and exact source/tree identities without granting acceptance credit.
- [ ] Synchronize the diagnostic-only goal, eight gate paths, one workflow path and six todos in Issue186, Project8 and canonical records; seal and preflight the actual checkpoint.
- [ ] Add the branch-scoped standalone diagnostic workflow with fixed Task65 checkout, bounded metadata, exact UID1000 first preflight and fail-closed cleanup.
- [ ] Validate trigger, identity, sanitization, provenance, metadata, original failure propagation and cleanup using external checks; verify protected bytes and review the exact candidate SHA.
- [ ] After narrow coordinator authorization, obtain one diagnostic push run and retain terminal raw job/log/artifact receipts with workflow revision separate from checkout SHA/tree.
- [ ] Classify the hosted access evidence honestly, preserve credits0 and release-unverified, and separately gate any later attribution experiment or repair.

Tracking synchronization is retained above. Actual checkpoint sealing, standalone and extracted queue-nested preflights at that committed SHA, independent checkpoint review and narrow dispatch remain required. Then validate external failure controls, preserve original nonzero and cleanup status, review exact candidate, and obtain separate one-push-run dispatch. Retain terminal run/jobs/raw logs/action and image receipts, artifact ID/archive/extracted hashes, workflow-definition bytes/hash at workflow SHA, and checkout HEAD/tree. A pass, incomplete metadata or unexplained failure requires a separately gated before/after experiment in the original workflow; an identified denied component requires a separately designed/gated measured correction. No automatic rerun or repair.


## Exact gate-document responsibilities

1. `docs/superpowers/plans/2026-11-05-gce-workspace-access-diagnostic.md` — decision-complete design, fixed inline command and literal todos
2. `docs/agents/specs/2026-11-05-gce-workspace-access-diagnostic.json` — machine-readable scope, authority and provenance contract
3. `docs/agents/records/2026-11-05-gce-workspace-access-diagnostic.json` — standalone canonical pre-implementation record
4. `docs/agents/tasks/2026-11-03-production-release/gce-workspace-access-diagnostic.json` — Task67 queue handoff with nested record and unchanged execution policy
5. `docs/verification/2026-11-05-gce-workspace-access-diagnostic.md` — evidence ledger, honest terminal history and future verification obligations
6. `docs/agents/tasks/2026-11-03-production-release/queue.json` — append one Task67 entry; retain every existing field, task and policy
7. `docs/operations/workshop-gcp.md` — append Task67 operational boundary without rewriting history
8. `docs/github/operating-model.md` — append Task67 tracking boundary without rewriting history

## Coordinator and implementation sequence

1. Retain the independent external draft review and root-verified Issue186/Project8/item readback, literal goal/six todos/references/scope and before/after preservation proof cited above. Task67 planning/tracking statuses are synchronized; preserve false authorities/empty current allowlist.
2. Verify assigned branch ownership/history; materialize exactly these eight documents directly on Task65 source. Run required schema/governance, append-only/scope/protected-byte and whitespace checks; commit/push only the gate milestone. Record actual checkpoint SHA/tree externally. Do not claim CI success if the docs push starts existing workflows.
3. Run `python scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-gce-workspace-access-diagnostic.json --base-sha <actual-checkpoint-SHA>` and the same command with the externally extracted Task67 queue nested record. Retain exit0/status:synchronized/errors:[] for both plus independent exact-checkpoint review. The angle-bracket value denotes a real future receipt, never a guessed or committed self-reference. Obtain narrow implementation dispatch.
4. Assemble only `.github/workflows/gce-workspace-access-diagnostic.yml` from the fixed contract below; carry its Bash fence verbatim except YAML indentation. Use external validation scripts, YAML1.2/BaseLoader, Bash/Python syntax, literal wrapper/probe parity, protected-byte/scope checks and the specified injected failure/environment/symlink/different-owner controls. If a control reveals a frozen-listing defect, stop for plan revision and exact-source review; no silent repair.
5. Obtain independent exact-candidate review before committing/pushing. A separate narrow coordinator push-run dispatch permits one coherent validated workflow-only push; retain actual candidate/workflow revision, raw terminal run/jobs/logs and artifact provenance. No PR is required. No automatic rerun.
6. Report original probe, observer and cleanup outcomes independently and preserve unverified release/credits0. Follow the separately gated terminal decision in the contract.

## Frozen corrected design contract

The original proposal was independently approved and subsequently received the bounded-collection REVISE above. Its historical pending-review status line is omitted here; the corrected external proposal remainder is copied verbatim. Independent corrected-design review passed (external design only; receipt above). Neither historical design PASS nor the proposal's imperative future steps establishes execution authority or test results.


Goal: Diagnose UID1000 source and temporary-path access on a fresh hosted checkout of exact Task65 source without modifying the required verification workflow or granting repair or acceptance credit.

## Fixed evidence and source

Target source is **25d44588cb1ab82fab3e39d28ef1ee5a12b5fb44**, tree **264fc8d7711c461d781d7eaa7af34391c802edac**. Do not select another source, use a moving branch ref, or substitute the future planning checkpoint. Task65 source push [41983350226](https://github.com/lucronn/autodata/actions/runs/41983350226) and actual PR [41983396445](https://github.com/lucronn/autodata/actions/runs/41983396445) are terminal failures. Both completed all 607 development adapter tests with OK, then failed the first required GCE source read with EACCES on `/home/runner/work/autodata/autodata/infra/deploy/gce/runtime-entrypoint.sh`. GCE discovery did not start; Compose validation and downstream fake/live Compose smoke were skipped. DTO browser and R3 jobs succeeded independently.

The actual PR checkout was **e4b00a767026de274885f75093588e37ba3bb69e**, with the same tree as source; commit identities remain distinct. Both run API head SHAs name source and do not identify the actual PR checkout. Retain Task65 ingestion's 210 skips; do not describe all suites as zero-skip. Source main timeout was 30 minutes. Python was 3.12.15 on push and 3.12.16 on PR; that difference does not establish interpreter causality.

Primary external inputs are `/home/corp/autodata-evidence/task67-gce-access-proposal-review/REPORT.md`, `/home/corp/autodata-evidence/task65-terminal-ci-independent/audit.md`, and the original `/home/corp/autodata-evidence/task67-gce-workspace-access-design/PROPOSAL.md`. The terminal audit and review supersede the original proposal's in-progress snapshot and unconditional three-path/R6 claim. The retained full required GCE script digest is `5adc3b0b3b56c75f8df1faed2dd461a71ac37c3622b973af185baf99941e3502`. Its first read follows successful four-ID and Python-version assertions. `Path.cwd()` and Git mode100755 do not establish hosted path search rights.

The coordinator reports a disposable cross-UID local lab reproduced EACCES behind a UID1001-owned0700 ancestor, while an isolated UID1000-owned export of the exact tree passed the first preflight. This is supplemental hypothesis evidence only; it neither identifies the hosted denied component nor authorizes export/ACL repair. The final report is `/home/corp/autodata-evidence/task67-cross-uid-repro/REPORT.md`, SHA256 `97b08f93f20c730fd0986e0292e250202c79d9cb6e1db20628ccd60948c2b4a2`; it reports 1067 exact blobs/modes and an isolated local tmpfs GCE run of274 tests with0 skips. No local lab result is represented here as hosted acceptance or independently verified by this author.

## Exact change boundary and branch/event decision

The sole future implementation path is `.github/workflows/gce-workspace-access-diagnostic.yml`. Its only job/status is `GCE workspace access diagnostic (no acceptance credit)`. No helper, permanent test, production code, existing workflow or permission change is included. Its diagnostic command contains only metadata observation and the original first preflight; the diagnostic does not run or substitute for GCE discovery, Compose, or the developer suite. Absence of those commands is the deliberate standalone diagnostic scope, not a passing/skipped-test acceptance result.

Create the future planning branch **codex/gce-workspace-access-diagnostic** directly from exact Task65 source25d44588/tree264fc8d above. The coordinator commits only the eight gate documents listed below and publishes that branch at the checkpoint before implementation. The same assigned branch then receives a workflow-only implementation commit after gate preflight/review/dispatch. Do not rebase onto current orchestration HEAD, Task66, a default-branch tip or a synthetic merge. Existing remote branch names must be checked for ownership and unexpected history; stop rather than reset an unrelated branch.

The workflow trigger is exactly a `push` with `branches: [codex/gce-workspace-access-diagnostic]` AND `paths: [.github/workflows/gce-workspace-access-diagnostic.yml]`. No PR trigger, schedule, workflow_dispatch, workflow_run, arbitrary-ref input or retry is added. Push workflows are read at the pushed branch revision, so the new file can run on that branch before it exists on default. `workflow_dispatch` would introduce default-branch availability ambiguity and is unnecessary. Its actions/checkout@v4 has `ref: 25d44588cb1ab82fab3e39d28ef1ee5a12b5fb44`, no `path` override, and otherwise original defaults (fetch-depth1, clean and persisted-credentials behavior). This deliberately means the executing workflow definition is absent from its target checkout. Inline code comes from the event revision; observed source comes from the fixed checkout. Never read diagnostic code back from the target or equate github.sha with target HEAD.

The gate-document push matches the old autonomous workflow's docs filters and may start its existing jobs. This proposal neither changes those filters nor claims to avoid that launch. Publish the gate checkpoint first, then push only the new workflow in a subsequent commit on this established branch: that later push matches the diagnostic filter and does not match the existing autonomous workflow's path list. Do not combine gate docs with the implementation push or use PR opening as the diagnostic trigger. Existing unrelated CI can run independently; the diagnostic has no `needs` or approval dependency on its slow suite. Gate/diagnostic run permissions still require coordinator authority; this proposal does not grant push/run authority.

The future job uses `ubuntu-latest`, `timeout-minutes: 5`, `permissions: {contents: read}`, actions/checkout@v4, actions/setup-python@v5 with python-version3.12, the exact inline command below, and actions/upload-artifact@v4 with `if: always()`. No environments, secrets, dependency/package installation, cache, deployment permissions, continue-on-error or automatic retry. No Go/Node setup or prior suites. Preserve action version tags for parity with Task65; retain actual resolved action SHAs from runner setup logs. Keep default workspace layout `/home/runner/work/autodata/autodata`; verify it rather than staging source. Match image label, record actual ImageOS/ImageVersion/runner receipt, and do not claim an exact old image.

Explicit diagnostic-step environment bindings are: `DIAG_EVENT_SHA=${{ github.sha }}`, `DIAG_WORKFLOW_SHA=${{ github.workflow_sha }}`, `DIAG_WORKFLOW_REF=${{ github.workflow_ref }}`, `DIAG_EVENT=${{ github.event_name }}`, `DIAG_REF=${{ github.ref }}`, `DIAG_RUN=${{ github.run_id }}`, and `DIAG_ATTEMPT=${{ github.run_attempt }}`. These are data passed through env, never interpolated into shell source. The script prints only this whitelist and ImageOS/ImageVersion; no environment dump. The artifact name is `gce-access-diagnostic-${{ github.run_id }}-${{ github.run_attempt }}`, path `${{ runner.temp }}/gce-access-diagnostic`, retention-days14, if-no-files-found:error. Artifact files are observer-owned metadata.log, uid1000.log, original-preflight.log and result.json, never source/config contents or credentials. Export no secrets to the child.

## Eight concrete coordinator gate paths

Only these eight repository-document paths are permitted for the future planning checkpoint; they are separate from the one implementation path:

1. `docs/superpowers/plans/2026-11-05-gce-workspace-access-diagnostic.md`
2. `docs/agents/specs/2026-11-05-gce-workspace-access-diagnostic.json`
3. `docs/agents/records/2026-11-05-gce-workspace-access-diagnostic.json`
4. `docs/agents/tasks/2026-11-03-production-release/gce-workspace-access-diagnostic.json`
5. `docs/verification/2026-11-05-gce-workspace-access-diagnostic.md`
6. `docs/agents/tasks/2026-11-03-production-release/queue.json`
7. `docs/operations/workshop-gcp.md`
8. `docs/github/operating-model.md`

Reuse Issue [#186](https://github.com/lucronn/autodata/issues/186), Project [#8](https://github.com/users/lucronn/projects/8), item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, after live readback confirms identity/ownership and current content. Add a Task67 diagnostic section/comment with the literal goal, plan/spec/task/verification references and all six literal todos below; update only the existing Project item's corresponding index section and retain prior history/status evidence. No new issue or item is needed. Root/coordinator owns tracking mutations. Capture before/after receipts and preservation proof. A stale or unavailable item blocks synchronization; no inferred tracking success.

All plan/spec/task/standalone and queue-nested records carry the exact same goal and todo array. The plan contains Issue/Project URLs and a visible todo record. `repository_doc_refs` are paths2,4,5,7,8 above. Allowed future implementation paths are exactly the single workflow path. Current implementation allowlist is empty; authorities and dispatch flags remain false, accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified. Record task ordinal67/id `gce-workspace-access-diagnostic`, exact materialization parent/source SHA/tree, branch assignment above and external proposal hash. Append only the new Task67 queue entry; preserve queue root, prior entries/history and execution policy. Preserve current model/reasoning/tier/no-fallback policy rather than inventing a new execution profile.

Use null checkpoint_sha/checkpoint_tree/implementation_base_sha in committed documents. Record **actual** checkpoint SHA/tree after commit in external `/home/corp/autodata-evidence/task67-diagnostic-gate/CHECKPOINT.json`; never put a future SHA or self-referential assertion into its own commit. `status: synchronized` means verified literal tracking alignment, not passing implementation or a guessed checkpoint. Run `scripts/autonomy/pre_implementation.py` on the standalone record and extracted queue-nested record with `--base-sha <actual-checkpoint-SHA>` against the exact committed checkpoint, retain exit0 and `status:synchronized, errors:[]`, independently review that checkpoint, then obtain narrowly scoped implementation/push-run dispatch. No Task65 record authorizes Task67. A machine preflight alone does not verify live GitHub tracking; retain both proofs.

Literal todo array (six entries; copy verbatim):

- [ ] Preserve terminal Task65 source-push and actual-PR receipts and exact source/tree identities without granting acceptance credit.
- [ ] Synchronize the diagnostic-only goal, eight gate paths, one workflow path and six todos in Issue186, Project8 and canonical records; seal and preflight the actual checkpoint.
- [ ] Add the branch-scoped standalone diagnostic workflow with fixed Task65 checkout, bounded metadata, exact UID1000 first preflight and fail-closed cleanup.
- [ ] Validate trigger, identity, sanitization, provenance, metadata, original failure propagation and cleanup using external checks; verify protected bytes and review the exact candidate SHA.
- [ ] After narrow coordinator authorization, obtain one diagnostic push run and retain terminal raw job/log/artifact receipts with workflow revision separate from checkout SHA/tree.
- [ ] Classify the hosted access evidence honestly, preserve credits0 and release-unverified, and separately gate any later attribution experiment or repair.

## Frozen proposed inline diagnostic command

This listing is design text, not a repository workflow implementation or an already-tested candidate. The builder must carry it verbatim into the single workflow `run: |` block, except YAML indentation. A necessary correction to it requires explicit plan revision and exact-source review before run. Workflow assembly described above is also fixed. Runtime dynamic values are only listed metadata and mktemp paths.

The ordinary caller observes metadata. The system Python child supplies an independent UID1000 observer even if the setup-python interpreter cannot execute; the original first preflight still uses the captured setup-python interpreter. Both children use the literal original `run_gce` wrapper. Reads are bounded and discard contents. Metadata may fail but each failure is reported; no metadata failure prevents the final original preflight. Unexpected missing required observer tools mark diagnostic infrastructure failure; optional ACL/mount/security tooling absence is reported. No observer repairs permissions or runs tests as root.

```bash
set -euo pipefail
umask_value="$(umask)"
gce_temp=''
evidence="${RUNNER_TEMP:?}/gce-access-diagnostic"
test ! -e "$evidence"
mkdir -m 700 "$evidence"
diag_rc=0
probe_rc=null
cleanup() {
  code=$?
  trap - EXIT INT TERM
  cleanup_rc=0
  if [ "$probe_rc" = null ]; then diag_rc=1; fi
  if [ -n "$gce_temp" ]; then
    sudo -n /bin/rm -rf -- "$gce_temp" || cleanup_rc=1
    test ! -e "$gce_temp" && test ! -L "$gce_temp" || cleanup_rc=1
  fi
  printf 'cleanup_exit=%s\n' "$cleanup_rc" >> "$evidence/metadata.log"
  if [ "$cleanup_rc" -ne 0 ]; then code=1; fi
  printf '{"original_preflight_exit":%s,"diagnostic_infrastructure_exit":%s,"cleanup_exit":%s,"final_exit":%s}\n' \
    "$probe_rc" "$diag_rc" "$cleanup_rc" "$code" > "$evidence/result.json"
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for tool in /usr/bin/sudo /usr/bin/setpriv /usr/bin/env /usr/bin/python3 /usr/bin/namei /usr/bin/timeout; do
  test -x "$tool" || { printf 'required_tool_missing=%s\n' "$tool" >> "$evidence/metadata.log"; exit 1; }
done
sudo -n /usr/bin/true
gce_python="$(python -c 'import sys; print(sys.executable)')"
case "$gce_python" in /*) ;; *) exit 1 ;; esac
test -x "$gce_python"
export DIAG_GCE_PYTHON="$gce_python" DIAG_UMASK="$umask_value"
test "$(git rev-parse HEAD)" = 25d44588cb1ab82fab3e39d28ef1ee5a12b5fb44
test "$(git rev-parse HEAD^{tree})" = 264fc8d7711c461d781d7eaa7af34391c802edac
test "$PWD" = /home/runner/work/autodata/autodata
printf 'actual_checkout_sha=%s\nactual_checkout_tree=%s\n' "$(git rev-parse HEAD)" "$(git rev-parse HEAD^{tree})" >> "$evidence/metadata.log"
run_gce() {
  sudo -n /usr/bin/setpriv --reuid=1000 --regid=1000 --clear-groups /usr/bin/env -i \
    HOME="$gce_temp/home" TMPDIR="$gce_temp/tmp" PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 AUTODATA_REQUIRE_PURCHASE_CONFIG_DELIVERY_COMPOSE=1 "$@"
}
observe() {
  /usr/bin/timeout 45 /usr/bin/python3 -B - "$gce_temp" <<'PY'
import json, os, pathlib, stat, subprocess, sys
import os, selectors, signal, subprocess, time

def bounded_capture(argv, *, limit, timeout):
    # Retain at most limit bytes, drain/discard excess, and time-bound our owned session.
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    selector = selectors.DefaultSelector()
    retained = bytearray()
    truncated = False
    deadline = time.monotonic() + timeout
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map() or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout, output=bytes(retained))
            for key, _ in selector.select(min(remaining, 0.1)):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                room = limit - len(retained)
                retained.extend(chunk[:room])
                if len(chunk) > room:
                    truncated = True
        return process.returncode, bytes(retained), truncated
    finally:
        # Also stop descendants that could otherwise retain our pipe after the leader exits.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        selector.close()
        process.stdout.close()
        process.wait(timeout=1)

def emit(**value): print(json.dumps(value, sort_keys=True), flush=True)
def attempt(label, operation):
    try: emit(label=label, result=operation())
    except OSError as error: emit(label=label, errno=error.errno, error=type(error).__name__)
def command(argv):
    try:
        code, output, truncated = bounded_capture(argv, limit=16384, timeout=5)
        emit(command=argv, exit=code, output=output.decode('utf-8','replace'), truncated=truncated)
    except (OSError, subprocess.TimeoutExpired) as error:
        emit(command=argv, unavailable=type(error).__name__, errno=getattr(error,'errno',None))
emit(observer='ambient', uid=os.getuid(), gid=os.getgid(), euid=os.geteuid(), egid=os.getegid(), groups=os.getgroups(), cwd=os.getcwd(), runner_temp=os.environ['RUNNER_TEMP'], interpreter=sys.executable, version=sys.version)
for key in ('DIAG_EVENT_SHA','DIAG_WORKFLOW_SHA','DIAG_WORKFLOW_REF','DIAG_EVENT','DIAG_REF','DIAG_RUN','DIAG_ATTEMPT','DIAG_GCE_PYTHON','DIAG_UMASK','ImageOS','ImageVersion'):
    emit(metadata_key=key, value=os.environ.get(key))
root=pathlib.Path.cwd()
paths=[str(root/'infra/deploy/gce/runtime-entrypoint.sh'),str(root/'workers/ingestion-python/src/autodata_ingestion/commerce_service.py'),os.environ['RUNNER_TEMP'],os.environ['DIAG_GCE_PYTHON']]
if sys.argv[1]: paths += [sys.argv[1],sys.argv[1]+'/home',sys.argv[1]+'/tmp']
seen=set()
for target in paths:
    resolved=os.path.realpath(target)
    emit(target=target, resolved=resolved)
    command(['/usr/bin/namei','-l',target])
    for spelling in (target,resolved):
        p=pathlib.Path(spelling)
        for component in [*reversed(p.parents),p]:
            name=str(component)
            if name in seen: continue
            seen.add(name)
            if len(seen)>160: raise SystemExit('ancestry_limit_exceeded')
            for follow in (False,True):
                def inspect():
                    s=os.stat(name,follow_symlinks=follow)
                    return dict(mode=oct(stat.S_IMODE(s.st_mode)),type=stat.S_IFMT(s.st_mode),uid=s.st_uid,gid=s.st_gid,dev=s.st_dev,ino=s.st_ino,link=os.readlink(name) if not follow and stat.S_ISLNK(s.st_mode) else None)
                attempt(name+(':stat' if follow else ':lstat'),inspect)
            if os.path.isfile('/usr/bin/getfacl'):
                command(['/usr/bin/getfacl','-n','-p','--',name])
            if os.path.isfile('/usr/bin/findmnt'):
                command(['/usr/bin/findmnt','--noheadings','--target',name,'--output','TARGET,FSTYPE,OPTIONS'])
emit(optional_getfacl_available=os.path.isfile('/usr/bin/getfacl'),optional_findmnt_available=os.path.isfile('/usr/bin/findmnt'))
# Metadata only, bounded security labels; no complete /proc, environment or mount dumps.
def security_label(name):
    with open(name, 'rb') as stream:
        value = stream.read(4097)
    return dict(text=value[:4096].decode('utf-8','replace'), truncated=len(value)>4096)
for name in ('/proc/self/attr/current','/sys/kernel/security/lsm'):
    attempt(name,lambda: security_label(name))
PY
}
observe >> "$evidence/metadata.log" 2>&1 || diag_rc=1
gce_temp="$(mktemp -d "${RUNNER_TEMP:?}/gce-contract.XXXXXXXX")"
mkdir -m 700 "$gce_temp/home" "$gce_temp/tmp"
sudo -n /bin/chown 1000:1000 "$gce_temp" "$gce_temp/home" "$gce_temp/tmp"
observe >> "$evidence/metadata.log" 2>&1 || diag_rc=1
run_gce /usr/bin/timeout 45 /usr/bin/python3 -B - "$gce_python" <<'PY' > "$evidence/uid1000.log" 2>&1 || diag_rc=1
import errno, json, os, pathlib, stat, subprocess, sys, tempfile
import os, selectors, signal, subprocess, time

def bounded_capture(argv, *, limit, timeout):
    # Retain at most limit bytes, drain/discard excess, and time-bound our owned session.
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    selector = selectors.DefaultSelector()
    retained = bytearray()
    truncated = False
    deadline = time.monotonic() + timeout
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map() or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout, output=bytes(retained))
            for key, _ in selector.select(min(remaining, 0.1)):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                room = limit - len(retained)
                retained.extend(chunk[:room])
                if len(chunk) > room:
                    truncated = True
        return process.returncode, bytes(retained), truncated
    finally:
        # Also stop descendants that could otherwise retain our pipe after the leader exits.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        selector.close()
        process.stdout.close()
        process.wait(timeout=1)

def emit(**value): print(json.dumps(value, sort_keys=True),flush=True)
def attempt(label,operation):
    try: emit(label=label,result=operation())
    except OSError as error: emit(label=label,errno=error.errno,error=type(error).__name__)
emit(observer='uid1000',uid=os.getuid(),gid=os.getgid(),euid=os.geteuid(),egid=os.getegid(),groups=os.getgroups(),interpreter=sys.executable,version=sys.version)
assert (os.getuid(),os.getgid(),os.geteuid(),os.getegid())==(1000,1000,1000,1000)
assert os.getgroups()==[]
assert set(os.environ)=={'HOME','TMPDIR','PATH','LANG','LC_ALL','PYTHONDONTWRITEBYTECODE','AUTODATA_REQUIRE_PURCHASE_CONFIG_DELIVERY_COMPOSE'}
attempt('cwd',os.getcwd)
root=pathlib.Path.cwd()
paths=[str(root/'infra/deploy/gce/runtime-entrypoint.sh'),str(root/'workers/ingestion-python/src/autodata_ingestion/commerce_service.py'),os.environ['HOME'],os.environ['TMPDIR'],sys.argv[1]]
seen=set()
for target in paths:
    for spelling in (target,os.path.realpath(target)):
        p=pathlib.Path(spelling)
        for component in [*reversed(p.parents),p]:
            name=str(component)
            if name in seen: continue
            seen.add(name)
            if len(seen)>160: raise SystemExit('ancestry_limit_exceeded')
            def inspect():
                s=os.stat(name)
                return dict(mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,gid=s.st_gid,dev=s.st_dev,ino=s.st_ino)
            attempt(name+':stat',inspect)
            # Traversal/chdir yields an actual search errno, not an os.access boolean.
            def search():
                result=subprocess.run(['/usr/bin/true'],cwd=name,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,check=False)
                return dict(chdir_exit=result.returncode)
            try: attempt(name+':search',search)
            except subprocess.TimeoutExpired: emit(label=name+':search',error='TimeoutExpired')
    if target in paths[:2]:
        def read():
            with open(target,'rb') as stream: return dict(bytes_read=len(stream.read(1)),contents_discarded=True)
        attempt(target+':read',read)
def temporary():
    with tempfile.TemporaryDirectory() as directory:
        with tempfile.TemporaryFile(dir=directory) as stream: stream.write(b'x'); stream.flush()
    return 'create_write_cleanup_ok'
attempt('temporary_file',temporary)
def interpreter():
    code, output, truncated = bounded_capture(
        [sys.argv[1],'-B','-c','import sys; print(sys.executable); print(sys.version)'],
        limit=4096, timeout=5)
    return dict(exit=code, output=output.decode('utf-8','replace'), truncated=truncated)
try: attempt('setup_python_execution',interpreter)
except subprocess.TimeoutExpired: emit(label='setup_python_execution',error='TimeoutExpired')
PY
# This is the original first preflight, unchanged; the captured setup-python interpreter is intentional.
set +e
run_gce "$gce_python" -B -c 'import os,pathlib,sys,tempfile; assert (os.getuid(),os.getgid(),os.geteuid(),os.getegid())==(1000,1000,1000,1000); assert sys.version_info>=(3,12); root=pathlib.Path.cwd(); assert (root/"infra/deploy/gce/runtime-entrypoint.sh").read_bytes(); assert (root/"workers/ingestion-python/src/autodata_ingestion/commerce_service.py").read_bytes(); assert os.access(sys.executable,os.X_OK); d=tempfile.TemporaryDirectory(); d.cleanup(); print("gce_ci_preflight:identity_paths_temp_pass")' > "$evidence/original-preflight.log" 2>&1
probe_rc=$?
set -e
cat "$evidence/original-preflight.log"
if [ "$probe_rc" -ne 0 ]; then exit "$probe_rc"; fi
exit "$diag_rc"
```

No `/usr/bin/python` alias creation is included: that mutation is unnecessary to the original first preflight and outside diagnostic permissions. Original later alias/system-Python/tool-version/discovery commands are not run. The only root mutations are chown of the just-created GCE leaf/home/tmp and deletion of that owned leaf; observer evidence-directory creation is by the ambient runner. No checkout, ancestry, ACL, mode, group, source export or security-policy modification. Temporary-file writes occur only as UID1000 in its disposable tmp. The first preflight itself reads full original source probes exactly as before but prints no bytes.

Each observer invocation has a 45-second process timeout; optional subprocesses also have five-second bounds. Observers run before and after leaf setup, and finish before the original preflight. Their bounded tool outputs are metadata. Mount/security evidence is collected unconditionally, avoiding a speculative automated permission-cause classifier. ACL absence remains an evidence limit. `namei -l` plus numeric stat/lstat records both spellings and symlink targets; UID1000 actual chdir and open operations produce errno, including later boundary observations even after one EACCES. Non-directory search attempts honestly report ENOTDIR. An inaccessible system Python may prevent the child observer; its failure is retained and the setup-python original probe still runs. Required prerequisite/provenance failure exits before a potentially misleading probe and is diagnostic infrastructure failure, never repaired.

Original nonzero status wins over a successful collector. A collector failure makes an otherwise successful original probe fail. Cleanup failure forces job exit1 and is recorded alongside original status, so neither masks the other in result.json. Trap cleanup runs on normal exit/signals; a hard runner kill may prevent it. In that case missing terminal cleanup proof means unverified cleanup and failed/incomplete diagnosis, never a claimed clean result. `if: always()` uploads existing metadata despite probe failure; timeout/platform failure may prevent artifact upload, requiring raw logs and an explicit incomplete result. Do not rerun automatically to hide this.

## Validation, provenance and terminal decision

Before committing, use external validation scripts/files rather than expanding the implementation allowlist. Parse YAML with a YAML1.2-aware parser (or PyYAML BaseLoader so `on` remains a key), validate branch/path conjunction and sole job, permissions, timeout, action versions/settings, env whitelist, artifact retention and always behavior. Extract `run`, run `bash -n`, compile each Python heredoc without executing the workflow, compare the wrapper and original first preflight literally against Task65, and reject missing identity, environment, failure/cleanup/provenance terms. Validate exactly one new implementation path and no cache/secrets/ref input/continue-on-error.

Exercise external disposable failure controls: injected original probe exit17 stays17; observer failure plus probe0 exits1; cleanup failure exits1 while retaining original status; UID1000 metadata exposes empty supplemental groups and only the declared child environment. Exercise symlink ancestry and an inaccessible different-owner parent without mutating the real checkout or running GCE tests as root/ambient. Retain commands, outputs, failures and environment limits. If these controls reveal a listing defect, revise the plan and review it before implementation; no silent builder choice. No permanent tests or altered protected fixtures are needed for this standalone diagnostic.

Protected source bytes must match Task65 both at gate and implementation commit:

| Path | SHA256 | Git blob |
|---|---|---|
| `.github/workflows/autonomous-verification.yml` | `b9ccf5f8c8fc974d113f0461871e9288e30a1a61ddeff6fc67cfd8a6fb3e7418` | `02688d0e504cb914fb691d05d692f9c11a9900de` |
| `scripts/dev/test_repository_governance.py` | `ba42d12411b746e93b32052cb6f1d586b33b4bc3ea7577d53a13adafee295822` | `306d71ecf75b8b0025dee96470bfbd6f069fd0af` |
| `docs/agents/tasks/2026-11-03-production-release/r6-release.json` | `09562c3da23fbf1283c5276023967c97ab51d53b1133c49ddf7cd6b6f4b87be7` | `132307774cb0baabb1f320b0e2ea7bde3aae9526` |

Preserve R6 enabled:false and all bytes, PurchaseTransportTests' UID/GID assertion, every existing gate and test command. New workflow is not hashed by the inspected named-workflow bindings; no R6 rebind or governance digest update is required. This is specific to the standalone file; changing the bound workflow later requires its own gate/bindings. Run git diff --check, gate schema/governance checks required by the checkpoint, and exact protected-byte/scope checks. Do not claim a full developer/GCE rerun from these structural checks. Promptly commit and push a coherent validated workflow milestone only after independent exact-candidate review and narrow coordinator dispatch; the push itself starts the one intended diagnostic. No draft PR or merge is needed for the experiment.

Retain external run API, jobs API and full raw terminal logs, resolved action/runner setup receipts, diagnostic artifact ID/archive SHA256 and hashes of extracted evidence. Read the workflow file at DIAG_WORKFLOW_SHA through GitHub and hash its exact bytes; prove it equals the independently reviewed candidate definition. Bind run id/attempt, event/ref, reported event head, workflow ref/revision, actual checkout HEAD/tree, script digest, interpreter path/version, image receipt, original probe exit, metadata failures and cleanup status. Reject rerun attempts or mismatched source/workflow as outside the one-run contract; preserve their receipts if they occur. Do not confuse github.workflow_sha, github.sha and target git HEAD even when two happen to be equal.

If UID1000 fails and metadata identifies a denied component, retain that result and separately design/gate one measured correction. If it passes, metadata is incomplete, or original failure is unexplained, retain uncertainty and separately gate before/after observations in the original workflow, immediately after checkout and immediately before GCE, with original prerequisite order unchanged. The standalone job intentionally omits preceding suites and cannot attribute an old after-developer permission change. No source/temp repair is preapproved by either outcome. A green diagnostic is not a repair, required-check replacement, real API/browser acceptance or production credit. Credits remain0 and release remains unverified.
