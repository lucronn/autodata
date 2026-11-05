# Workshop local backup and isolated restore verification

Status: implementation ready for independent review with blocked complete fixture proof; no production recovery claim.

Issue: [#308](https://github.com/lucronn/autodata/issues/308), child of open [#186](https://github.com/lucronn/autodata/issues/186). Branch: `codex/workshop-backup-restore-build`. The exact final candidate is recorded on Issue308 after the evidence commit; this document records code hashes to bind the disposable proof across documentation-only changes.

## Gate and implementation

Before edits, the builder read the canonical gate, plan, specification, record, task and receipt; checked fresh Issue308/Project8 Ready/parent readback; and ran the full-SHA preflight successfully (`synchronized`, errors `[]`). Planning gate: `90bc004386a8b48afac98886108c91f0484c2925`; receipt checkout: `056a0db74bb252cd7e53fa1c21d65ecdfa973d69`. Implementation is isolated from the gate checkout and root master.

Validated milestones: `56162cd240a926096ba95282aababe6c6366c79d` (backup lease, wrapper and inert watchdog); `ba41ade67a4382d410bd11996e3cdbf46970d153` (isolated restore and validation); `3a57204ab956d606d38eadbc79fd02081944301c` (adapter guard tests and rejection of forced/OOM stateful stops before quiescence).

The production wrappers accept only their fixed verbs and UUIDv4, use an empty environment and isolated Python, and expose no path or credential overrides. The new module reuses existing installed host validators/locks without changing them. Lease intent is durable before mutation; failure recovery remains incomplete. Portable exports pass the existing independent archive verifier. The restore path validates fixed mounted inputs and owns only UUID-labelled disposable resources. No installed production adapter or systemd unit was executed.

## Automated checks

Final local checks: helper42 tests, fixture safety20 tests, cloud operations57, host activation104, host runtime95, host install40, private material38. All passed (396 total). Python compilation, shell syntax, diff whitespace checks and exact planning-SHA preflight passed. Review regressions first reproduced omitted required evidence, post-ingress lease persistence failure leaving maintenance open, and a malformed lease aborting later watchdog recoveries. The fixes require all15 nonempty relation categories, two distinct account/organization identities and the core row counts, objects and persisted JetStream shape; compensate failed recovery with maintenance independent of lease storage; and continue bounded watchdog processing after individual malformed leases while returning failure.

The helper tests first failed for missing implementation; subsequent streaming and clean-stop tests failed before their fixes. The clean-stop test rejects Exit137, OOM, still-running state and boolean ExitCode.

Only the eight allowlisted implementation files and this leaf's permitted documentation changed. Backup/monitor workflows and shared host/runtime/cloud/schema files remain byte-identical to the planning gate, including workflow exit3.

## Exact code and retained fixture outcomes

Current engine SHA256: `6a1996ccaebcc16264b23c0234465e48b14c13a9f3ec62a5299e418627bb780d`. Current runner SHA256: `558a23e469a91df2f0291787f1d1f1ff09be18a74687a3cd09b3122d8d133913`; runner test SHA256: `d9438f9385e9d4c454ea4f21d4da1c60bec8c30f6f9ebfde30de4eb91671953b`. Review fixes were committed separately as `96867ed` after the real fixture attempts below. The final code has not completed a passing real fixture run.

| Attempt | Evidence | Actual result |
| --- | --- | --- |
| 3, historical earlier engine | `/tmp/autodata-workshop-restore-fixture-20261105-attempt3/result.json`, SHA256 `5b6c3517309ecd8dca9b390cba7c91de83cf6a98258c96acb5c2fe4b9e8a128a` | Passed earlier code only; not final candidate evidence |
| 7, engine before clean-stop/review fixes | `/tmp/autodata-workshop-restore-fixture-20261105-attempt7/result.json`, SHA256 `3d14c79d63328ebb488b6a24b1aa3bcaf786dbf57f27f261716949057287875a` | All13 data/negative assertions true; overall false because final cold SeaweedFS stop exceeded45 seconds, Exit137/OOMfalse; zero leftovers |
| 8, clean-stop guard | `/tmp/autodata-workshop-restore-fixture-20261105-attempt8/result.json`, SHA256 `6b0e432baf4eb3884f500f0e0496d0439c12d5b0b5ca280f008939c99e042b0c` | Failed safely before cold copy: source SeaweedFS exceeded45 seconds, Exit137/OOMfalse. Recovery resumed source; cleanup removed all owned resources, retaining the failed stop. Only image/migration/seed assertions true; ten later assertions false |

Attempt8 source HEAD is `3a57204ab956d606d38eadbc79fd02081944301c`, engine SHA256 `705cc440c9cf55c8a609ae5de7adebde7859e741fdafcd1dce7455a49fc6294f`; it predates review fixes and the runner's new fail-closed callback. The failed proof remains a blocker. No identical retry was run after attempt8. Retained Mini shutdown stderr shows metadata-log writes with no writable volumes and a deleted filer socket after teardown began. The same image sometimes stopped cleanly; no validated signal workaround was established. Docker storage was about98% used, a possible contributing condition; unrelated resources were not pruned.

Historical attempt7 negative receipts (all code4, failed status, cleanup_verified true):

| File | SHA256 | Intended rejection stage |
| --- | --- | --- |
| `negative-corrupt_dump.json` | `e930eb325773eeddf4a8334dbcb172af91d4912c3ba1cae41bffefb8eeb4f900` | Real pg_restore rejects corrupt dump |
| `negative-missing_object.json` | `83a4807179163e47c86b64c1270c5f8e395c2d2b0d37a42346976cc349e56934` | Actual S3 missing-key404 |
| `negative-altered_owner.json` | `b88fcd9886d833386a6de4c91a93004ded30d35391e156c9535cdc709025294f` | Completed observation differs from exact inventory |
| `negative-missing_message.json` | `9a50356f1c3d011a59be790a4c0434d975ac1324257cc30007ce57e62bd0d075` | Actual persisted-message lookup404/10037 |

## Disposable fixture and limits

The opt-in runner uses an empty Docker CLI configuration and fixed local socket, no pull, internal networking/no published ports, newly owned resources, bounded CPU/memory/logs, 900 seconds total including a shared120-second cleanup reserve. The default invocation is inert. The real fixture applies all40 released migrations through the canonical migration emitter, verifies two independent synthetic ownership/session/order/grant identities, article/source object bytes and JetStream message/consumer state, then uses the real backup/export/restore state machines. Cold copies use stopped owned volumes; PostgreSQL restoration uses the portable dump into a fresh database. Historical attempt7 has four separate failed receipts establishing actual rejection of corrupt dump, missing object, wrong owner and missing persisted message.

Reviewed cached Linux/amd64 immutable images:

| Role | Image ID |
| --- | --- |
| PostgreSQL17 with required vector extension | `sha256:151aa1c2e849e7828ed8aef2183ae15f692cbe887d2f28921d8b44b26e154d7e` |
| NATS2.10.29 | `sha256:8b9f712ae2148dcbd9d7f3d16a942d515e290526e5d018500931eab62b18e045` |
| SeaweedFS4.48 | `sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5` |

SeaweedFS repository digest is `ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d`. Plain cached PostgreSQL lacks the released vector extension, so the explicitly reviewed cached pgvector PG17 image is required. No mutable tag fallback exists.

Failed/intermediate evidence is retained under `/tmp/autodata-workshop-restore-fixture-20261105-*`. Early failures identified the migration033 canonical driver requirement, overlong service DNS names, NATS signal handling and SeaweedFS's already-owned bucket response. The runner accepts only the exact expected owned-bucket conflict. Attempt6 passed data checks but failed cleanup because SeaweedFS exceeded15 seconds and exited137; it is not a passing proof. SeaweedFS now has a finite45-second graceful-stop allowance inside the same shared120-second cleanup deadline; nonzero/OOM still fails. Source stopped states are retained before restart so restarts cannot hide a failed cold-copy stop.

Docker volume mountpoint inode observation is unavailable to the unprivileged runner on this host (PermissionError). Evidence explicitly records that limitation and uses exact Docker volume name, creation time, driver, options, labels and mountpoint identity; it does not claim an observed host inode.

Earlier evidence demonstrates local portable PG17 and synthetic stopped-volume recovery only; the complete final-candidate fixture proof remains blocked. It does not prove installed host mount/guard/secret handling in operation, cloud snapshots, production object completeness, owner/privilege restoration, provider/account observation, representative scale/RPO/RTO or end-to-end ingress recovery. Host installation, live cloud adapters, staging restore drill, alert delivery and owner recovery choices remain separately gated. Parent186 remains open; no last-verified-backup timestamp advances.

## Follow-up review regressions

An exact deadline-exhaustion-after-open regression first failed because maintenance compensation inherited an expired deadline. Recovery now reserves30 seconds within the existing total300-second deadline and CLI alarm; normal recovery work uses at most270 seconds, and compensation uses the remaining bounded reserve. Resume timeout remains incomplete/exit6. The regression exercises InstalledHost.fail_closed with maintenance rejecting expired deadlines.

A second regression first showed an inventory could name an unrelated object while restored snapshot/article rows referenced a missing object. Validation now requires every source snapshot key/hash and every article resource manifest bucket/key/hash to match an expected object, with the article body snapshot present. Missing keys/hashes/references fail before resource creation. Offline validation of the retained attempt7 real40-migration inventory/export passes these stricter checks; this is not a new restore run or completed fixture proof.
