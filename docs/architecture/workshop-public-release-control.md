# Public source-only release control

Goal: Prepare a separately sealed source-only public API release-control package with dry admission, exact no-provider probes and one-attempt install/switch/rollback, without executing deployment

Issue: https://github.com/lucronn/autodata/issues/431
Project: https://github.com/users/lucronn/projects/8
Protected integration basebe1a1f235e8eeacc051ac905c4ed8a953a41c8a9; selected built sourcea82b31dc8850aa3956972928b8c720969765a972/tree11503a735d7d983ca3ebf090b471c89682e77278, API treef4faba6ee59f0000522d6962478098456957ed16 equalsbe1.

## Todo

- Synchronize Issue431/Project8/current gate and pass pinned checkpoint preflight before implementation; preserve sealed build package9dfcdcf3 and all current public/private service inputs
- Implement fixed-target admission/probe/release controls with root-only physical execution fence, unchanged env, exact99 path replacement and durable one-use activation/rollback guards; prove refusal/rollback/capacity/HTTP behavior using owned offline fixtures only
- Bind exacta82 source/bb11 candidate and current1202200/ad5 public plus17295 private identities; separately reserve rootfs/home capacity and prepare an offloaded sealed artifact/command handoff for root review before any physical control copy/install/switch/probe

## Fixed boundary and identities

Prepare only on offloaded ext4; no public/systemd/Docker/provider/SQL/browser request now. Implementation allowlist:
- scripts/dev/workshop_public_release.py
- scripts/dev/test_workshop_public_release.py
- scripts/dev/workshop_public_probe.py
- scripts/dev/test_workshop_public_probe.py

Documentation allowlist: this plan/record and docs/architecture/workshop-public-release-control.md. No product code or source package mutation. The immutable build package is /home/corp/.local/state/autodata-workshop-client-preview-a82b31d-attempt2-20261115, seal9dfcdcf3a39de85f74b5b9514406ea0ec0452d65c8ed96e33936e95663443cca; artifactbb11d963666e4fc44f6b0879ebb55a14cf7b2ca221bad6ffa8d3282d5360203e,61,405,300B. Use none of its unsealed f534 helpers as an executable.

Public baseline: PID1202200/startticks10595766, old installed /usr/local/libexec/autodata/workshop-preview-5981b97-r2/autodata-api hashad5ad70c777a19c2446275cf7640e8777429d3fc3bb334cc3522ff43e1d29750, dev66312/inode714673, root0555. Env74a93e21… remains byte-identical/read_only/Firebase;99=41a658a3…, dependency493beef2…; private17295/source272/image3132 full Config/Mounts/environment/lifecycle/source/archive guards unchanged. No restart of private services or DB restore. Existing source-only gate Issue431 remains authoritative for scope; real supplier completion, Firebase authentication, licensed articles and Stripe acceptance remain separate.

Future exact install /usr/local/libexec/autodata/workshop-client-preview-a82b31d-a2/autodata-api must be absent. Only one counted old→new executable path replacement in99 is permitted, expected SHA b9d00378ce917cc53d515e7460774712c5e179ae9bfefed3bee7886b55b74c7c. No env installation during activation. Fresh physical root-only control directory /home/corp/.local/state/autodata-workshop-client-preview-a82b31d-attempt2-release-20261116 and fixed matching offloaded preparation path are separate from immutable payload. Helpers must refuse real execution from offloaded paths; all real phases need explicit root execution switch plus exact reviewed manifest/helper hashes, physical metadata and one-use reservations. Default dry admission is read-only and does not open network/SQL or spawn Docker/systemd.

## Capacity

Public home reserve stays5GiB absolute+128MiB drift+remaining128MiB prep+remaining64MiB install. Already sealed prep allocation95,612,928B counts; new physical control/browser allocation must fit remaining38,604,800B (new controls <=4MiB; optional pinned browser runtime <=20MiB). Future install is actually on separate rootfsdev66312; enforce an independent proposed2GiB rootfs absolute+64MiB install+32MiB burst reserve, strict entry2,248,146,944B and >1000 free inodes. Preserve conservative home install reservation too; no savings assumed from cross-filesystem allocation. Docker unchanged and free>813,694,976B/1000 inodes. Before/after every phase and copy chunks validate capacity, source/public/private pins; aggregate unexplained drift96MiB stop preserves32MiB within128MiB reservation. No build/image pull/new source extraction. Offloaded artifact <=4MiB and>=1GiB free; no physical writes in this preparation. Fresh root approval must accept final policy/capacity before deployment.

## Future ordered transaction and failure behavior

Root independently reviews hashes/test receipts and separately approves copying tiny release controls into fresh physical root0700, using source package read-only. Prepare verifies physical/local Docker root identity/full private source guard, current loaded+installed executable inode/hash and env/unit files, then creates exclusive root0700 backups of original99/env and exact target99 (env bytes unchanged) with file/parent fsync. Capture coherent bounded READ ONLY protected27 count/hash baseline only at a later authorized phase; never raw rows or secrets. No live SQL in preparation or dry tests.

Install reserves manifest-bound root0600 activation marker before a fresh root0555 binary copy; verify independent hash/inode/file fsync and target-parent fsync, never overwrite old executable. Switch revalidates baseline and backups, reserves exclusive switch marker, atomically stages/chowns/chmods/fsyncs only99, daemon-reload and restarts ONLY API once. Poll active/nonzeroPID/exact target executable+installed/loaded inode/hash for<=30s; tolerate transientPID0/gone only. No retry restart. Verify candidate identity, private/env/dependency/protected27, then bounded fixed HTTP canaries (each<=5s/1MiB, real<=210s outer bound), all15 canonical assets/config/status/redirect hashes. Browser acceptance needs separately sealed anonymous harness/local fixture success and independent authorization, no public auth simulation/signin click. Exact years GET and RUM POST are browser-local synthetic suppressions only, never real catalog/provider calls.

After a switch/canary failure root may execute the single pre-reviewed rollback: require manifest-bound activation and prepared immutable original backups, reject unknown live99/env state/private/old executable drift, reserve rollback marker before writes, atomically restore exact99 bytes+uid/gid/mode (env unchanged), fsync, daemon-reload and restart API once, poll exact old running inode/hash<=30s and run bounded old-source/protected checks. Rollback failure holds evidence for root recovery; no second rollback/restart or DB restore. Pre-switch refusal never starts rollback or modifies live files. No deletion of candidate or consumed markers.

## Red-first verification

Owned temporary fixtures only: no/invalid approval/execution-root/manifest/helper/root metadata; changed package/artifact/baseline/old inode/env/99/private/source; rootfs/home/Docker reserve boundaries; exclusive phase markers; one counted99 replacement; atomic restore metadata/fsync; failure after switch invokes only one explicit rollback path; PID0/gone→exact expected identity vs timeout/mismatch; fixed no-proxy/no-redirect GET route/status/body/hash/deadline limits including canonical index mapping; unknown endpoint/credential/query/method variants refused. No real HTTP, Docker, systemd, SQL, browser or provider execution. Exact helper/test hashes and no-dispatch receipt return to root before any install.
