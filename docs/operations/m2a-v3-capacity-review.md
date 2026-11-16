# Offloaded M2A V3 operational capacity review

Issue: https://github.com/lucronn/autodata/issues/443
Project: https://github.com/users/lucronn/projects/8
Related authored browser acceptance: https://github.com/lucronn/autodata/issues/398
Public exclusive-capacity lane: https://github.com/lucronn/autodata/issues/431
Protected planning base:4246264a881382676927e22adad0a1d240f03268. This is a new operational review checkpoint, never a silent historical seal rewrite.

## Goal and hold

Prepare separately sealed OFFLOADED operational helper copies with explicit current capacity arithmetic and dry-only proof for root review. Public release retains the exclusive physical capacity slot. Original M2A V3 safe-origin browser, six stopped services, SQL/read-only store attestation, relay and provider calls remain HELD. This task starts none of them and writes no physical source/data/config/seal/marker. All new operational CLI entrypoints remain review-only and reject runtime actions pending a separate root-reviewed activation gate.

Preserve original V3 harness1557e9c5d5690d8f956b7dadd4f79a6414433996/tree2c199661545e77cbd4db3a71049067d46645b66e, original V3 operational seal f299e6cad31313a81febabcde4cdb9ae3dc769c0e16ccc85edb434467e4a09a2 and V1/V2 consumed browser markers. Preserve physical runtime root /home/corp/autodata-workshop-owned-article-data-20261115/m2a, source668d4c86/archive041f834/binarybb11d963/manifestda5353/config8ad3cd1e/accepted09a32725, exact six container IDs/network/storage inode mapping and original authored rows/objects. No claim that old floor values were unsafe or services newly validated; changed guard proposal alone does not prove browser/data acceptance.

## Proposed reserve (not execution approval)

Physical absolute reserve5368709120B(5GiB), unowned drift reserve134217728B(128MiB), M2A physical cap67108864B(64MiB)/aggregate growth stop33554432B(32MiB), preserving32MiB burst. Retain PUBLIC pending install67108864B plus unused prep38604800B=105713664B unless root separately closes/releases these reservations. Effective warm floor5608640512B; strict entry>5675749376B. Aggregate physical free-space drop includes all owned and unrelated growth; do not guess/subtract external growth. Earlier public reserve amendment does not automatically lower M2A floors; these copies explicitly propose it for root review.

Docker warm floor813694976B; strict entry>880803840B, independent64MiB allowance/32MiB cumulative growth stop and remaining32MiB burst. /tmp tmpfs entry/free floor536870912B, independent128MiB cap/96MiB stop/32MiB burst. Memory>=1073741824B and finite cgroup headroom>=1073741824B; free inodes>1000 on physical home/Docker/tmp. Keep default Chromium sandbox, pinned browser/runtime packages and all security/provider/auth/commerce boundaries. Distinct actual physical/temp growth tracked against a fresh explicit candidate baseline, not historical stale df. Review proof must separately report PASS/FAIL capacity observation and HELD execution authority; no auto-reset baselines after failure.

## Inventory and implementation boundary

Inventory physical admission capacity_errors (hardcoded home7046430720B), forwarder startup_admission (calls that admission); E2 phase operator hardcoded warm7180648448/entry7247757312 and Docker813694976; pre/post attestors repeat warm floors; browser lifecycle and V3 harness load historical capacity JSON and physical helper imports. New root /home/corp/autodata-evidence/m2a-safe-origin-v3-capacity-20261116 must be absent; all copies on offloaded ext4 device1792. No build/archive/binary/store/credential copy. Operational root<=4MiB and offload>=1GiB; metadata worktree separately offloaded, no physical payload.

Copy exact original admission/forwarder/seed plus V3 harness/test and E2 phase operator/launcher/pre-post attestors/lifecycle/readonly SQL PROGRAM only (never execute it). Preserve prior file hashes and root-to-root mapping. Add one strict pinned capacity policy and pure shared module; every changed admission/relay/operator/harness capacity boundary delegates to this shared policy. Explicit offloaded helper import paths/hashes replace only host operational imports; physical runtime source/archive/config/data remain untouched. V3 harness operational guard must pin both original physical helper provenance and new offloaded operational helper identity, not monkeypatch or ignore old home_reserve. Distinct new namespace/output/marker/seal paths; no V2/V3 consumed evidence overwritten. Fix retained helper script invocation paths to offloaded copies; never rewrite physical source imports inside actual services.

All runtime-bearing copied CLI entrypoints must refuse execution in review-only package; dry checker may read file hashes/source guards and Docker INSPECT only, never compose config/service start/stop/exec, SQL, HTTP, relay bind or browser. Tests use owned synthetic fixtures/mocks and pure policy checks. Record exact old floor/import locations and new route mapping in inventory, AST compile all copies and prove non-capacity application/runtime security logic remains unchanged apart from explicit host path/seal/namespace/read-only locks.

## Verification and handoff

Test exact arithmetic, strict boundary entry/warm refusal, public reservation preservation, aggregate own/external growth without guessed attribution, home/Docker32MiB and tmp96MiB early stops, hard caps, unknown/negative/malformed observations/policy, memory/cgroup/inodes, no stale-baseline refresh, source/import pin refusal, runtime-action CLI rejection and no live command dispatch during dry proof. Retain original V3 diagnostics/strict zero-errors tests with safe mocked imports; if they require changed operational identity, add explicit revised tests rather than waiving checks. Prove original source/operational seals/helpers/markers unchanged before/after; confirm six fixed containers stopped/restart-no and network no attachment through bounded inspect only if needed. No DB/store reads or SQL.

After synchronized plan/Issue/Project/canonical record and pinned machine preflight, create copies and tests; seal policy/helper/test/original inventories and no-dispatch receipt, return exact paths/hashes and pending root decisions. No runtime approval follows from dry PASS.

## Todo

- Synchronize this plan, dedicated Issue/Project8 item, canonical document and machine record; pin checkpoint and pass preflight before copies/edits.
- Inventory original hardcoded floors/imports and pin physical/original/offloaded identities; create narrow operational copies and explicit review-only capacity policy.
- Run meaningful pure/no-dispatch tests and source-preservation proof; seal exact copies/policy/receipt and report root.
- Keep public-exclusive slot and M2A services/SQL/relay/browser/provider work held for separate root review and activation gate.

## Review-only outcome — sealed, execution held

Preparation checkpoint ebd0111ac1d445481d6d78be3adbab0203b3b30c passed synchronized machine preflight before implementation. The separately offloaded review root is /home/corp/autodata-evidence/m2a-safe-origin-v3-capacity-20261116 (device1792). Package seal SHA256 370f42e3a7456d1f576782e89af35f08a8c5ad500491a5dcdfdfc04de14051ad; operational seal275c435200e170c724dae0f5dd738314764dc5c4c3f0bb576e758118ac1dacdd; capacity policybbf9c3cfb7a63c9805b073eb7627d026d8264ef602b21528221e6d1e7078ca74. HANDOFF.md SHAe3b2c3c3ef2bc14b9ff6204a21d3e67a424b08f5b138bf5823d5df2f505aebfd and original-to-operational.diff SHAc50b3319a086fe545b976fed046965ee75aba929125954d65762f1c9b77099e1 provide exact review scope/mapping.

43 tests passed:28 retained V3 harness tests and15 capacity/fence/preservation tests. Historical copied tests first failed on the intentionally new namespace/schema; red receipt retained and narrow fixtures updated with original assertions retained. Original JavaScript RUNNER is byte-identical; forwarder function/class ASTs differ only in the explicit process-receipt namespace. All copied runtime-bearing CLI/import entrypoints refuse service/SQL/relay/browser execution; this is an inert review package requiring a separately gated executable successor.

Consumed DRY-CAPACITY-PROOF.json SHA2d09539cdc13e6f201d1531e8c7f336edbe0f47f7a6e56857bdbc7806eea01a7 reports DRY_CAPACITY_PASS_EXECUTION_HELD/errors[]. Observed home5926051840B, Docker990830592B, tmp6770307072B, RAM/cgroup7782793216B; minimum free inodes1022760. This timestamped observation is not current execution admission. Original21 pinned files,1506 source metadata paths and four store root device/inodes unchanged; six exact containers exited/restart-no, internal network unattached. Docker inspect only; no service, SQL, HTTP, relay, browser or provider work. Store contents were not freshly attested and historical row/object/migration counts remain historical. V3 unconsumed markers absent; both earlier consumed markers preserved. Public retains exclusive capacity; proposed reservations remain unchanged pending root decision.

Completed: synchronized checkpoint; floor/import inventory33 sites; explicit offloaded copies/shared policy/fences; tests/dry proof/seal. Remaining: independent root review and any separately synchronized activation successor. No runtime approval follows from this outcome.
