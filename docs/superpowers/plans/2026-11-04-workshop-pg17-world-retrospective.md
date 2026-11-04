# PG17 failed-install world-order retrospective audit — synchronized docs-only gate

Status: SYNCHRONIZED DOCS-ONLY planning checkpoint. Independent exact local draft review PASS was relayed by coordinator; exact synchronized-checkpoint review/adoption/root verification/fresh host-only dispatch remain pending. This planning synchronization grants no audit execution or installation acceptance. The retained attempt remains `installation_blocked_quarantined`. Its skipped complete audit has NOT been run here.

Goal: establish the source-derived world expectation and design one host-only retrospective audit of immutable raw bytes from the failed attempt. No Docker invocation, container operation, install/retry, image creation, PostgreSQL start, observation harness, application change, PR mutation, merge, or deployment is in scope.

Repository canonical gate: `/home/corp/Documents/ChatGPT/autodata/docs/agents/pre-implementation-gate.md`. Historical synchronized checkpoint: `d662cb01a35b07cfa0dc3788891248fc4c07d12f`. Issue: https://github.com/lucronn/autodata/issues/186 ; Project: https://github.com/users/lucronn/projects/8 . Those records do not authorize this new audit or another installation.

## Immutable failure and narrow finding

Retained result `/home/corp/autodata-evidence/pg17-install-20261104-01/evidence/installation-result.json`, SHA256 `124e43a98319c5bfcd2d79b0384925eaa3d29df3148d8bccb05409e8df5c5ffb`, declares phase `complete_finite_projection_audit`, `audit_database` world equality assertion failure. All 211 referenced raw SHA256 values were reverified during source research. The original result and raw files must remain byte-identical. Preserve exit0, quarantine, output_parser_passed=false, harness_executed=false, image_committed=false, postgres_started=false, runtime_verified=false, production_ready=false exactly as historical facts.

The prior expectation appended selected20 tokens to base7 and produced 926 bytes SHA256 `626c1405acfdae445028c35986ba1cd58368422a425d986cdf7f39a5453c4b04`. Independently deriving the ordering from the pinned source and the same exact27 unique-name tokens gives 926 bytes SHA256 `ff2c86c23fc594d35e568629e9f400e3eb86f2f0e9e1459dd75af1fab8420aa4`, exactly the retained actual world. This diagnoses the incorrect world projection; it does not prove the skipped tree/diff/output/bounds/classification audits.

## Source authentication and exact call chain

Installed apk-tools record in authenticated created-export FDB is `3.0.8-r0`, aports `c:4588b452722bd4800efdc6cce4f6e980e02a997f`. Retrieve APKBUILD at that exact commit, not the moving branch. Its source is `https://gitlab.alpinelinux.org/alpine/apk-tools/-/archive/v3.0.8/apk-tools-v3.0.8.tar.gz`; source archive SHA512 is `3616435508dead5240f8d9fe74e87e2aa93262f9e466f50af8f60100e166403393b1e491c115395864d4179b219699831ecb61dc60960b5dfb1f10816d75f95f`, SHA256 `e81c64a6e7c3806d45d4622c253e757aee970be84048554fa0eed79310e9453e`, 390114 bytes. The archive hash matches the APKBUILD.

The included `repo-hash-sha1.patch` has SHA512 `6f6442d73d994964d78f06433a611902cbb066a457f3532544278b1422aa0aa276ccec1f2438ea7e93a8a048d3fdbf72ccd9a79d210f44870fda467bc43cb9fd`, SHA256 `0ef3ecc88a5c627ee9486632bbc26e66dd0073e6a9be0c143b25c6e366162df0`, 1245 bytes, also matching APKBUILD. It changes only app_upgrade preupgrade token and database repository-index hash algorithm; neither hunk touches this world call chain, comparator, or serializer.

GitHub mirror v3.0.8 annotated tag object `875911e1828c4acc954ef58106394f32123110bc` resolves to commit `44dcdfc255c26a4e19a4a27f66a54169cce5ca72`. All ten downloaded call-chain/helper source files were compared byte-for-byte with the SHA512-pinned official archive. solver.c is 36616 bytes, SHA256 `08453ee64737af080a2c079b257854cfa560cf65aea35616874020e9f13e3a6c`, Git blob `1fefd585863eb1d6cb2e3b08805b7bc8a01f29b9`. `transport-index.json` retains requested/final HTTPS URLs, status, headers, retrieval UTC time, sizes, hashes, and saved paths. Raw tag API JSON is retained separately. No cryptographic tag-signature verification or binary reproducible-build attestation is claimed.

Exact line references below refer to these pinned unpatched source files (the earlier database patch does not shift line counts):

1. app_add.c114-119 copies db->world;146-160 reads a local package and constructs its dependency;174-180 adds it to world;191 calls apk_solver_commit.
2. commit.c959-975 calls apk_solver_solve and then apk_solver_commit_changeset on that same world.
3. solver.c1048-1052 cmp_pkgname compares dependency name pointers through apk_name_cmp_display;1083 performs apk_array_qsort(world, cmp_pkgname) before solve work.
4. apk_database.h262-264 defines `strcasecmp(a->name,b->name) ?: strcmp(a->name,b->name)`. apk_defines.h213 expands array qsort into libc qsort on the in-place item array. Therefore the sort is by package name, ignoring dependency operator/checksum. The case-sensitive comparison breaks case-insensitive ties. The exact27 names are all lowercase ASCII and unique, so ordinary byte order on extracted names is equivalent for this finite input. Do not generalize Python lower() to arbitrary locale/Unicode/package names.
5. commit.c507-508 copies the sorted world into db->world and invokes apk_db_write_config. database.c2314-2335 invokes apk_db_write_layers (and explicitly skips writes for simulate mode).
6. database.c2252-2262 writes root etc/apk/world using apk_deps_write_layer with newline separators, followed by one final newline. package.c303-315 serializes name/tag/operator/version;326-346 iterates deps in array order (apk_defines.h249-252), selecting the layer without re-sorting.

The corrected finite expectation must be generated from authenticated base7 plus already-authenticated exact20 checksum dependency tokens, checking unique names/count27, then sorting names with the above comparator. The retained observed world must never be used as the generator or normalized before comparison. Exact bytes, token values, all27 records, and final newline remain mandatory.

## Research fixtures

`world-expected-source-order` and `world-proof.json` retain the derived positive case, old/actual hashes, and 12 rejected negative variants: old append order, reverse order, missing dependency, duplicate dependency, checksum drift, name=version substitution, missing final LF, extra LF, CRLF, NUL, unexpected dependency, and whole-token lexical order. Whole-token lexical order has SHA256 `fe491c5140fcb789c90991d42dd4e2f1689be8a7c560bc5e2e2a37952ef8336e` and is rejected. In the expected order python3 precedes python3-pyc and python3-pycache-pyc0; whole-token sorting places both hyphenated names before python3 because '-' precedes '>'. This distinguishes name sorting from accidentally sorting serialized dependencies. Source research verified comparisons only; it did not execute the skipped complete audit.

## Proposed read-only audit gate and concrete todo

- [ ] Independent local draft/source/fixture review passes on exact draft, world-proof, transport-index, and retained-source hashes; report limits and any blockers explicitly.
- [ ] Coordinator assigns one serialized documentation/tracking writer and adopts the failed attempt as failed only.
- [ ] Preserve/read back the entire latest Issue186 body and all comments plus complete Project item/index, including unrelated Stage0/Stage1A/M2A/staging/PG/JS pins. Append this diagnosis/scope/links/todo; do not replace earlier receipts or use the old113-comment snapshot as current truth.
- [ ] Add proposed canonical plan `docs/superpowers/plans/2026-11-04-workshop-pg17-world-retrospective.md`, evidence `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective-evidence.json`, task/record, and update the same six canonical repository-doc references as the old gate. Record only host-only retained-byte audit authority, no runtime/installation authority, implementation_allowlist empty.
- [ ] Commit/push the docs-only checkpoint, create the required status:synchronized record at a pinned full base SHA, and run `python scripts/autonomy/pre_implementation.py --repo-root <synchronized-checkout> --record docs/agents/records/2026-11-04-workshop-pg17-world-retrospective.json --base-sha <full-checkpoint-SHA>`. Retain full passing JSON, exact SHA, and complete tracking readback; independently review that exact synchronized checkpoint. Coordinator adoption and root full-SHA verification must precede a fresh narrowly scoped host-only audit dispatch.
- [ ] In a new private evidence directory, use a separate pure host-only runner (no imports/exec of historical supervisor top-level code). Pin source code and inputs. Allow reads only from immutable retained raw and checked-in pinned evidence; allow writes only under the new audit evidence directory. No subprocess/Docker/network/install actions. Reverify original result+all211 raw hashes before and after audit.
- [ ] Reload exact reviewed guard/parser/payload/projection data from git objects at old gate SHA; preserve guard SHA `d21da6de2796c88e5088a1924049f50e7db683bbfda14d47f285ce21ff3cb38f`. Derive a new in-memory projection replacing only world_expected27/world_expected_sha256 with the independently generated name-order expectation; record a field-by-field delta proving all remaining projection fields unchanged. Do not patch the historical gate or supervisor.
- [ ] Independently reindex created-export.tar and stopped-export.tar under the unchanged bounded physical-header collector and full logical tree schema. Recompare raw hashes, original index records/header lists/counts, exact body files, copied contexts, trailer completion and physical/logical equality; no extraction to the host filesystem. Enforce the reviewed bounded_audit main-thread Linux SIGALRM deadline of60 seconds (it is a deadline guard, not a memory-limit guard) and stream caps below.
- [ ] Run each previously skipped audit independently and retain individual pass/fail/error records even if one fails: (a) database exact65 complete FDB semantics plus new exact world and original10 script semantics/triggers; (b) complete finite projected tree using exact selected20 payload, base tree, dynamically derived exact four DB bodies, sole usr/bin/strings collision and all empty bind targets; (c) full Engine stopped-diff rows with required additions/changes and narrowly exact optional ancestors/unchanged lock; (d) full raw attach stdout/stderr versus accepted simulation transcript and exact65 post-info including one busybox trigger; (e) bounds; (f) classify all original27 baseline records, 24 immutable and exactly3 source-projected DB bodies. Compare retained pre/post copies and complete copy/export context to reindexed trees.
- [ ] Enforce unchanged ceilings: created export299700000; stopped535610656 and536870912 absolute; stopped logical entries6568; copied post-lib1867776/post-etc_apk21504/post-var36352; full physical headers50000; FDB<1048576; world<4096; scripts gzip<65536 and bounded decompressed<16384 with exactly10 physical members. Preserve all other reviewed parser/header/padding/Unicode/duplicate/unknown-field/hardlink restrictions. Do not infer a pass from an existing raw index or broaden a bound after observing data.
- [ ] Report any additional failure independently and keep the new retrospective disposition blocked. On full pass, label only `retrospective_raw_audit_passed` with independent review pending; historical installation result remains failed/quarantined. No accepted installation, runtime or production readiness claim follows automatically.
- [ ] Independently review new audit result/raw hashes and synchronize this separate outcome through the same docs-only writer/commit/push/full-readback path. A future installation/retry needs an entirely new plan/gate/adoption/fresh explicit dispatch; this retrospective scope grants none.

## Source-proof limits

Exact installed metadata, pinned aports recipe, upstream archive hash match, patch hash match, file byte equivalence, and the retained926-byte agreement support a source-derived diagnosis. They do not cryptographically prove the packaged libapk binary was built from this recipe, prove all runtime branches, or replace any skipped audit. No package signature verification, compiler reproduction, binary disassembly of libapk, or new runtime experiment was performed in this research. No claim is made about mixed-case/non-ASCII/duplicate-name general ordering; this expectation is deliberately finite for the27 unique lowercase ASCII names. Source retrieval used network reads only; no package acquisition or install occurred.

## Pinned transport/source bytes

| Source | Bytes | SHA256 |
| --- | ---: | --- |
| src/solver.c | 36616 | `08453ee64737af080a2c079b257854cfa560cf65aea35616874020e9f13e3a6c` |
| src/app_add.c | 5607 | `86783ad74977093c756311251296e456e0755625d9bb90cc11a974b081fd7509` |
| src/commit.c | 28573 | `d1ffe78256e6d9b061be8cecee94f3076b665b1de830fbc3156107a8405edd24` |
| src/database.c | 104738 | `70ed32b5276d67b75a1cb923bfe503f2e698e8f3fb6e764176c0d29926d0b335` |
| src/package.c | 32203 | `6d7abea38f045d3132d73da0720f5e193658644548b53e85d8110af0db5e55b6` |
| src/apk_package.h | 7977 | `943ecd1ff5051f88b50d834088ba77e8f90554cf69c43f51274614c3ec42e36d` |
| src/apk_blob.h | 4041 | `a8ba7842b3b60a873a6a1500542e63e0dd29a59cf8711548f4b4044da9a94766` |
| src/blob.c | 15239 | `7e60d143aceb05dc20113a8f4c61c2e1f9ce5627a023462571e7c77011344f30` |
| src/apk_database.h | 11026 | `c3c62362e1629e4672d44529315cc90356c84184ebddbb01f550907ee076d94e` |
| src/apk_defines.h | 11899 | `eeaf5fcbc34bd69d4b739e1e18e96dd184284db32d5cf665fcd61ca7bb720014` |
| main/apk-tools/APKBUILD | 3962 | `492db5ec3ca2ca6cfd3cc4e5b52a0262ca7bd9c77299344efb4d786c596b7005` |
| upstream-tag-object.json | 2517 | `1238db7dc9c6098d321caa216b31c268f6513b6fdea516762625db93cdb4fc87` |
| repo-hash-sha1.patch | 1245 | `0ef3ecc88a5c627ee9486632bbc26e66dd0073e6a9be0c143b25c6e366162df0` |
| apk-tools-v3.0.8.tar.gz | 390114 | `e81c64a6e7c3806d45d4622c253e757aee970be84048554fa0eed79310e9453e` |


## Synchronized checkpoint lifecycle

The reviewed local draft is retained byte-for-byte in `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective-evidence.json` with all support files/hashes. Historical local-draft lifecycle wording above records the reviewed planning stage; this addendum records documentation synchronization only.

## PG17 failed-install world-order retrospective: synchronized docs-only gate

Goal: Synchronize one host-only read-only retrospective audit of immutable PG17 failed-install raw using source-derived exact27 name ordering; preserve failed/quarantined historical result and all runtime prohibitions.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-world-retrospective.md`; record `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-world-retrospective.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective-evidence.json`; branch `codex/workshop-pg17-world-retrospective`, base prior PG installation receipt `d662cb01a35b07cfa0dc3788891248fc4c07d12f`. Independent local draft review PASS relayed by coordinator for exact draft SHA256 `4a51279130fdcf13123fa54f86ea7b4e85ed744620564bbc169e92d93f88d0c0` and support hashes; reviewer verified all211 raw refs, exact source chain and12 negative fixtures. Exact synchronized-checkpoint review is still pending.

Historical result `/home/corp/autodata-evidence/pg17-install-20261104-01/evidence/installation-result.json` SHA256 `124e43a98319c5bfcd2d79b0384925eaa3d29df3148d8bccb05409e8df5c5ffb` remains `installation_blocked_quarantined`. The actual926-byte world SHA256 `ff2c86c23fc594d35e568629e9f400e3eb86f2f0e9e1459dd75af1fab8420aa4` matches independently source-derived name order; old append expectation `626c1405acfdae445028c35986ba1cd58368422a425d986cdf7f39a5453c4b04` was incorrect. Pinned apk3.0.8-r0 APKBUILD/archive/patch/solver.c prove the comparator/call chain; this finding does not prove skipped finite-tree/diff/output/bounds/original27 classification audits. Whole-token sorting is explicitly rejected using python3 prefix-family fixtures.

Scope after a separate exact-gate review/adoption/root verification/fresh dispatch: host-only reads of retained raw, separate new audit evidence, unchanged reviewed guards/bounds, independently reindexed raw physical headers and full semantic projection; only world_expected27/hash changes in a new in-memory projection. Every skipped audit reports separately; original result/raw/gate stay immutable. No Docker, install/retry, image commit/reuse, PG startup, harness/Task2, implementation, provider/cloud/activation/production/readiness. No retrospective audit executed or passed on this docs turn.

Full CURRENT integration Project index gate `2728ac1acaf173d6f244e200e584dac7922fda1d`, receipt `507e3ddb977ddd45910cba978c7255fac3cb669e`, integration detail6622915925+pin6622928529, PG detail6622859754+pin6622872548, Stage1A/M2A/Stage0/staging/JS details and all prior authorities/statuses/denials remain preserved unchanged. The COMPLETE Issue body/all117 prior comments/full Project index are retained verbatim+SHA256 in `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective-tracking.json` with exact paginated readback.

Concrete todo:

- [ ] Retain independently reviewed exact local source/draft proof: reviewed draft4a51279130fdcf13123fa54f86ea7b4e85ed744620564bbc169e92d93f88d0c0, all211 immutable raw refs and12 negative fixtures; historical result remains failed/quarantined.
- [ ] Synchronize docs-only gate preserving COMPLETE current Issue body/all117 comments/Project index including integration gate2728ac1acaf173d6f244e200e584dac7922fda1d and receipt507e3ddb977ddd45910cba978c7255fac3cb669e verbatim+hash/readback; commit/push and pin full-SHA passing preflight.
- [ ] Obtain independent exact synchronized-checkpoint review, coordinator adoption/root full-SHA preflight, then fresh narrowly scoped host-only read-only audit dispatch; no skipped audit on this docs turn.
- [ ] Only after fresh dispatch: independently reindex immutable retained exports, replace only world projection with source-derived exact27 name order, run each skipped database/tree/diff/output/bounds/original27 classification audit and record individual outcomes; reverify all raw before/after.
- [ ] Independently review and synchronize a separate retrospective result without relabeling historical failure accepted; any installation/retry/image/PG/harness requires entirely separate authority.

Exact tracking detail/readback https://github.com/lucronn/autodata/issues/186#issuecomment-6623016400 at `2026-11-04T05:02:01.935195+00:00`. Exact full-SHA preflight pin follows.

Pinned PG17 retained-raw retrospective docs-only gate `3c525a8fec83348790e7b3092b1ead210a63c2f6`; exact full-SHA preflight exit0/empty stderr, `status: synchronized`, `errors: []`. Receipt `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective-preflight.json`; Issue186/Project8 exact pin https://github.com/lucronn/autodata/issues/186#issuecomment-6623026632. Complete original Issue body/all117 prior comments/full integration index and all118 pre-pin comments preserved unchanged verbatim/hash/readback. Historical installation remains failed/quarantined; no skipped audit pass. Independent exact synchronized-checkpoint review/adoption/root preflight/fresh host-only dispatch remain required; no Docker/install/retry/image/PG/harness/implementation/readiness authority.


## PG17 retained-byte retrospective — independently reviewed completion

Separate retained-byte result `retrospective_raw_audit_passed` is independently reviewed PASS. Gate `3c525a8fec83348790e7b3092b1ead210a63c2f6`, receipt `0c0baa6de6a9616f3cf9b736988e40bd22c7066e`; result SHA256 `c792e730e67eb3ac6572441065b003afc8e61a79dc973c2ec9ca8b2194ede130`, runner `02b36a26155b15739e85d271f8a9038a65d9dd4129ebe17de2463d3040013a72`, independent review `a8cebd2e6994ba78e46d68cf9f4402bbe13eba3d994ac3c40939305404089792`. All ten phases passed with all211 raw unchanged: physical/logical export reindex and copied context, exact65 FDB/new source-name world/original10 scripts/triggers, complete6560-entry tree, full diff/output/bounds and original27 records24 immutable+3 projected. Reviewer reproduced all15 receipts and rejected all12 negatives with the complete database oracle.

Completion evidence `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective-completion.json` retains exact runner/result/review bytes/hashes; complete Issue body/all119 prior comments/Project index preservation and authenticated readback are in `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective-completion-tracking.json`; detail https://github.com/lucronn/autodata/issues/186#issuecomment-6623105546. The old gate's pending fields above remain historical checkpoint facts, superseded only for this completed retrospective by this additive outcome. Historical installation result SHA256 `124e43a98319c5bfcd2d79b0384925eaa3d29df3148d8bccb05409e8df5c5ffb` remains failed/quarantined; its original predicate still fails. No accepted installation, image/PG/schema/runtime readiness, retry, Docker, provider, harness or production authority follows. A future installation requires a new plan/gate/adoption/fresh explicit dispatch.

Completion todo: [x] authenticate and audit retained raw; [x] independently review exact result; [x] preserve all prior tracking and append distinct result; [ ] commit/push exact documentation SHA and retain passing machine preflight/pin readback.
