# Initial-selector private runtime rollout draft

Status: protected a82 gate synchronized; M2A exclusive capacity slot HOLD; no package, serving or probe authority before the stated releases.
Issue: https://github.com/lucronn/autodata/issues/401
Source implementation: https://github.com/lucronn/autodata/pull/437 (Issue436).
Project: https://github.com/users/lucronn/projects/8

PR437 remains OPEN/BLOCKED at head2f766d103f75990351e3759b89249fce5b0784d7/treee167e3ecab877ca8fde0ca4cf39916a750281733, basef534d0aeb76973ca3b8c70b14c806973edb1b457. CI43676364154 R3/DTO green, policy in progress at inspection. Final protected source SHA/tree UNRESOLVED. No package/archive extraction/build/container fixture/stop/start/provider request until protected merge pin, fresh synchronized Issue/Project/plan/record/preflight and root approval. This draft is not the checkpoint authorizing implementation.

## Current authority and preserved outcome

Read-only exact serving identity17295fae5fe60b5b9c78b81206a3a0c8f3e202b811093f91ebb821babe648f3e, image3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7, protectedsource272aeeaad8399c305468e5d486cc391d7340f6a4, running/Pid1552737/restart0/StartedAt2026-11-15T04:15:19.01131429Z. Mount /home/corp/autodata-candidate/private-configuration-budget-272aeea-20261115/source. Retain this entire container/config/source as immediate rollback,343 as secondary,6fcc as historical retained fallback; do not delete/prune or reuse their names.

Prior v6 oneGET is permanently historical, incomplete/manualINCONCLUSIVE, not replayable. Response200/oneitem/itemcomplete true/collectioncompletefalse/hydratingfalse; worker5attempts9384ms FIN/disarm proven. Automatic finish failed on91MB baseline read; manual protected27exact/five target updated_at-only changes/noaddsdeletes, causal attribution unproven, no target configurations marker. Manual receipt1edb69ae5c56ea843d1831ddd7f2aaa8907557d76caa671bf0b2e174e1b829f0 remains authoritative. Preserve archive mapping if original baselines were subsequently offloaded; never change/replay v6 runroot/approval/unit. Payment read_only/providerNone/purchasefalse/quotefalse and existing grants/library/merchant validation must remain. Rights metadata/article display state and all existing licensed material unchanged; no recapture/article/payment requests.

## Exact preliminary source delta

272→PR437head worker runtime changes only:

| Module | Added/deleted lines | Runtime implication |
| --- | --- | --- |
| catalog_service.py |144/20|Initial years/makes/models dispatch through owned resolver; one active admission/global6s+incomplete30s cooldown; parent bounded selector-only persistence; complete years projection/provenance only; no descendant scheduling. Configuration429 control and safe START/FIN schema retained.|
| http_service.py |2/6|Public years uses same initial resolver, bypasses legacy manifest daemon.|
| selector_job.py |228/0|New owned child:12requests/20s absolute,6s spacing,1MiB/response4MiB cumulative,5000rows,16KiB input4MiB output,512MiBAS/22CPU/64FD; parent kills/reaps owned group including stalls. Source-root PYTHONPATH binding.|
| source_connector_client.py |24/8|Initial-only dispatch/read/byte/row accounting includes pagination and nested repair;429/elapsed stops.|

398insertions/34deletions in runtime modules. Five worker test files also change; Go adds fixture test only. Full repo delta includes already-protected Workshop JS/docs: these ride a full immutable source archive but do not change serving Go binary or this worker's mounted production modules. Dockerfile, pyproject/native dependency declarations, migrations, contracts and hosted entrypoint are byte-identical to272. Existing cached3132 image is a source-only candidate, not yet proven for final merged tree. No image build/pull allowed. Final pin must rerun this exact diff and101-image-input comparison; any additional executable/dependency/schema delta outside this reviewed four-module change blocks for review.

## Physical capacity admission (no reservation)

Last read-only free: /home7,413,874,688B (device66315, physicalnvme0n1p11); Docker1,005,174,784B (device66309). Values drift and are not reserved. Coordinator floors: /home full7,046,430,720B; activeM2A warm-abort7,180,648,448B. Proposed private total incremental physical-home cap128MiB=134,217,728B, admission at least7,314,866,176B with no concurrent claim; after every phase free must remain>=warm floor while build active. Current surplus over admission99,008,512B. Preview also proposes128MiB, not reserved: simultaneous two caps would breach warm floor by35,209,216B. Serialize packaging/fixtures/DB dump with coordinator and remeasure, stop before allocating if admission fails. Do not count promised cleanup/headroom.

Docker activeM2A floor813,694,976B supersedes earlier private512MiB floor. Private metadata/fixture allowance64MiB, admission880,803,840B; current surplus124,370,944B. No pulls/builds/newimages. Recheck exact local daemon DockerRootDir and filesystem before every admitted create/start; stop on unexpected layer allocation. Owned fixtures one at a time, limited tmpfs/outputs/DB rows; retain serving/rollback images and containers.

Git-tree metadata estimate at PR head:1404files/32,730,023logical bytes;4KiB file allocation35,799,040B+74directories/303,104B. Prior source.tar33,730,560B; new archive estimated<=36MiB (final exact measurement required). Plan128MiB host cap: archive<=36MiB +extractedROsource<=40MiB +freshdump/TOC<=24MiB +helpers/manifests/receipts<=8MiB +bounded scratch<=20MiB. Use off-home temp for test artifacts/fixtures; exact runtime source/archive and crash-critical dump/rollback/seals remain physical home. Existing DB dump15,887,579B is estimate only; fresh dump must fit24MiB or block/replan. Do not regenerate two91MB per-row baseline files on physical home. Activation requires one coherent39-table READ ONLY transaction yielding compact table count/hash fingerprints only (no provider GET), before/after exact; if later probe needs per-row deltas, separate gate can stream archive evidence off-home with physical hashed mapping and explicitly stated durability limits. Existing full v6 snapshots/manual evidence retained.

## Post-merge gate and isolated compatibility proof (held)

1. Root provides protected merge SHA/tree; reread actual public API binary/env/identity and17295 image/Config/HostConfig/Mount/source/status/restarts (safe hashes only), verify retained343 identity. Fresh plan/Issue401/Project8/record at exact protected base, commit/push/readback/preflight before any helper/package implementation. Keep source budget/helper fixes and final runtime source distinct; do not silently deploy feature branch.
2. Serialize capacity slot; measure floors. Prepare one immutable source archive/fullROmanifest under fresh physical candidate dir, exact mergeSHA/tree/files+hashes. Reuse3132 only after unchanged build inputs/native libs and actual-image compatibility tests. Pin direct Python override/currentUser/workdir/env names/rootfsRO/mounts/hostnetwork/argv and Docker normalization map, preserving only approved source path/name/hostname delta. Hosted file-secret entrypoint untouched.
3. Under separate admitted owned fixture: actual3132+exactmergedsource read-only root and source; prove sys.executable/source-root child import with PYTHONPATH absent, subprocess group kill/reap/resource limits/stall cleanup, child successful synthetic resolution, no leftover child; actualHTTP initial years+makes/models→ownedchild→synthetic PG plus partial/no false completion/complete provenance/cooldown; no fullvehicle/S3article pipeline. Run focused437 and429 fixture tests using cached test image only, and existing read_only quote/grant/library/merchant/checkoutdeny/providerNone/SVGPNG compatibility. No real provider credentials/network, use fixture egress isolation and bounded logs; cleanup only owned resources. No Docker image build.
4. Compact coherent39table before/after fingerprints + fresh fsyncedphysical dump/TOC, protected authentication/payment/grants/article exact. New source/createdpayload/metadata hashes, helper seal/runtime command wrapper fixed absolutes/minimalenv/localUnixDocker socket+inode+rootdir; file+parent fsync and external launch hash at each mutation phase. New helper must incorporate reviewed v3 rollback nonoverlap/oneattempt semantics and explicit Createdfalse→runningnull HostConfig hashes; targetnewcandidateID only after staged reviewed phase. No stale v6 seal/ID/cursor reuse.
5. Root independently reviews stage and activation commands; root alone stages/activates. Stop exact17295 only at reviewed swap, keep immutable and retained; intentional newcandidate stop+stableRunningfalse/Pid0/Restartingfalse proof before any rollback17295start. Unknown state holds manual recovery, no overlap/no automatic DB restore. Reverify same17295 Config/Host/Mount/source after rollback. Already-running verified17295 is serving, no duplicate start. Purchasefalse/quotefalse/library/grants/merchantdenial/health probes allowed; activation issues no selector/provider/article calls. Unchanged ingress can still independently cause provider traffic; narrow claim, inspect safe counters ifavailable.
6. Acceptance activation only: exactsource/image/env/runtime identity, source-root child fixture proof, health/read_only/purchasefalse/quotefalse, compact39 fingerprints exact, free>=sharedfloors, no unexplained errors. This does not establish real supplier completeness or article rights. Publish truthful activation outcome and retain rollback/backup.

## Separate first initial-selector real probe (held; not this gate)

After root exactwatchdog review only. Fresh runroot/unit/approval/attempt markers, one public GET/no retry/redirect/polling. Pick one legitimately incomplete known selector scope via bounded SELECT-only counts/provenance; no row/marker deletion/cache clear to manufacture work. CachedyearsGET currently would not prove hydration; completecachedmakes/model GET likewise insufficient. Finite12/20s/4MiB/5000rows ownedworker budget does not prove DBcleanup outerdeadline. New initial selector path lacks configuration START/FIN attempt telemetry, so v6log watcher cannot be reused as completion proof. Separate watchdog gate must choose a synthetic-proven provider-end signal or explicit independently supervised exactcandidate outer fence before disarm; prove dead caller/unknownunit/stop failure behavior, exact intentionalstop/Pid0/Restartingfalse/nooverlap before restart, no logging payloads/credentials. At mostone initial job process-global admission; simultaneous config requests/otheringress remain separate observations, not zero-egress claim.

Future probe compares compact protected/auth/payment/article exact and baseline catalog hashes/deltas with target/provenance manualclassification when expected persistence occurs; no automatic rollback/retry for legitimate target changes. Large audit receipts use reviewed128MiB size/SHA-reader and correct off-home evidence mapping; no Store.get64KiB replay. Incomplete/429/localbudget/providerclass outcomes remain truthful, no blanket supplier failure attribution. No article recapture/payment/delivery test in selector probe.

Todo:
- [x] Read-only current serving/source/PRdiff/floor measurement and draft.
- [ ] Protected PR437 merge SHA/tree + settled serialized capacity, fresh synchronized gate/preflight.
- [ ] Root-admitted immutable package/actual-image owned fixture + compactbackupbaseline/helperseals.
- [ ] Root independently reviewed stage/activation, no supplier GET.
- [ ] Separate bounded initial-selector probe/watchdog gate and truthful observations.


## Offline launcher/end-proof readiness amendment

Historical v6 execution seal30file hashes all match; exactlauncherSHA6be6e5651da90fea907942f886651eb8264814ca8abb53270c841582881cdf7a verified read-only. It is NOT reusable: configURL/scope/cursor/START-FIN and known-START restart proof do not implement initial-job end. Stored r4FIN7076ms/malformed8552ms/absent33049ms fixtures PASS/allcleaned prove only priorbytes/syntheticboundary. No new fixture/unit/package/build run; M2Astaging quiescent.

After protectedmerge/rootapproval, launcher must seal finalsourceSHA/tree/archive/fullROinventory+cachedimage+actualfixture and exact env/Config/Mount/lifecycleHostConfig hashes. Fixedabsolute localDocker/socketinode/DockerRootDir/minimalenv/no inheritedproxycontext and external reviewed-script hashes at everymutation. Bind new compact coherentbaseline implementation/queries, freshphysicaldump/TOC; no old v6approval/unit/runroot/markers. Rollback17295 requires independently verifiedidentity and exactnewcandidateintentionalstop+stablePid0/Runningfalse/Restartingfalse proof; unknownstate holds, already-running verifiedold supported, exactpoststartidentity/protectedfingerprints, noDBrestore.

### One first initial-selector probe, separately held

| Scope | Public route shape | Required passive preselection | Truth limit |
| --- | --- | --- | --- |
| years |/v1/catalog/years|Go ensures only with zero durable years; lastrecorded62rows means warmcache.|No row deletion/cacheclear to manufacture coldwork; warmGET cannot prove newjob.|
| makes |/v1/catalog/years/{year}/makes?region=US|One supported existingyear with genuinely incomplete/missing makesmarker.|Preferred firstrealjob ifavailable; cachedresponse/hydratingflag is not completionproof.|
| models |/v1/catalog/years/{year}/makes/{approved_make}/models?region=US|Existing returnedmake and incomplete modelsmarker, exactlabelURLrootapproved.|Alternative, NOTsecondGET. Known2024Acura marker complete so unsuitable.|

No scope chosen/dispatched and no SQL here. One URL only, no retries/redirects/routepoll/branchfollow/configurationreplay/directprovider/article/payment requests. Root exactapproval required. Productactivation after merge may proceed independently with noselectorGET.

### Owned termination/fence checklist after protected gate

1. Actual3132+exactmergedsource/rootfsRO: childimports with inheritedPYTHONPATH absent, synthetic two-source years/makes/models throughactualHTTP/PG, globaladmission/cooldowns independentofcallerkey, no descendantscheduling; config429 unchanged. DNS/header/trickle/429/byte/row/IPC/resource stops kill/reap onlyownedprocessgroup; no laterdispatch/falsemarker. Completeyearspageprovenance and partialyearsno-write; parentDBcleanup proved separately from hardownedproviderdeadline.
2. New independentunit/runtime bounds+ExecStopPost; sealunit/PID/startticks/boot/argv/cgroup, freshlivenessbeforeexclusiveattemptmarker. Callercrash/deadunit/missing/malformedend do notcancel fence. No SQL/unboundedlogs under fencelock; slowSQL only afterdurableend/disarm+finalizer.
3. Initialjobs lack configurationSTART/FIN. HTTP200/cache response/timeelapsed/single nochildobservation cannotdisarm. Separate exactrootreview must approve positiveendsignal or explicit intentionalcandidatefence; do notsilentlyweakenknownSTART semantics. PrivatePIDnamespace+owneddescendantcontainment, successful exactIDstop--time0+stableRunningfalse/Pid0/Restartingfalse, durableproofbefore restart/disarm. Unknownstoptimeout/stillrunning=>nonzerorecoveryhold/noT25claim/no restart.
4. Internalrequest-ended proof is mandatory before samecandidate restart: Go makes/models clonesBackground; HTTPIngestionClientPOST carriesIdempotency-Key. Publiccurl exiting does notendprivatePOST. Restart resets process-local admission/cooldown, so late internal dispatch must not be assumed harmless. Owned interruption/latePOST fixture must prove originatinginternalrequest/transportended; otherwise holdstopped/INCONCLUSIVE. No automaticpredecessorstartup while candidate terminationunknown. Root agreed this boundary belongs in gate/checklist.
5. Test normalend, missing/malformedend, deadcaller/supervisoridentitydrift, stopunknown/stillrunning/restartfailure, lateinternalPOST, slowSQLdrift andoneattemptreplay. Actualrootadmission neededbeforeanyownedcontainer/unitfixture; no real credentials/network. Anycatalogdelta manualscopeclassification/candidatepreserved, no secondGET/automaticrollback. No91MB physical-home receipts; anylargeaudit uses reviewed128MiB reader+offhomehashmapping.

Latestreadonlyfree home7,357,726,720B/Docker1,005,068,288B; only42,860,544B above privatehome128MiBadmission7,314,866,176. Notreserved. MaintainM2Astagingquiescent andserializedrootcapacityslot, warmhomefloor7,180,648,448/Dockerfloor813,694,976 plusnamedallowances. Finalprotected437pin unresolved (currentmasterf534d0a); recordremainsplanning and no machinepreflight run. No productactivation/providerGET authorized by this draft.


## Protected b435 package/owned-fixture checkpoint

Protectedb435d71d1090cd5a5a22ef229c5d302937bad0cb/treee167e3ecab877ca8fde0ca4cf39916a750281733 merged437 at04:45:21, reviewedheadtree/all3CIgreen. This supersedes unresolved-source draft statements. Root authorizes source/archive+ownedsyntheticfixture preparation AFTER synchronizedcheckpoint/preflight and capacityholdrelease; no servingstop/start/providerGET. Productarchive exactprotectedb435, never helperbranch. UIremoteCI/lightworkonly; M2Astagingquiescent. CurrentallocationHOLD pending rootverifiedhistoricaltaroffload; no source/archive writes beforecompletion+freshcapacitymeasure.

Exactroots: /home/corp/autodata-candidate/private-initial-selector-b435d71-20261115 (ROsource/archive), /home/corp/.local/state/autodata/initial-selector-runtime-20261115 (physicalseals/rollbackauthority), privateoffhomeautodata-evidencefixtures (notrollbackauthority). Caps128MiBhome/64MiBDocker; warmhomefloor7,180,648,448/admission7,314,866,176; Dockerfloor813,694,976/admission880,803,840. Lastrootfree7,326,941,184/Docker1,005,006,848; no promisedheadroom. No imagepull/build. Retainrunning17295/source272/image3132 exact and343stopped, preservev6manualINCONCLUSIVE/no replay. Probeheldseparate/internalend/fenceproof.

Todo for this checkpoint:
1. Synchronize Issue401/Project8/canonicaldocs/record/checkpoint/readback/preflight before implementation.
2. Aftercapacityrelease, freshsafe17295/343identity+image/Config/Mounts/HostConfiglifecyclenormalization/socket/DockerRootDir/capacity readback; privateenvvalues never output.
3. Immutable exactprotectedb435source.tar/fullROmanifest/file+dirfsync, fourworkermoduleallowlist/native/dependency/schema/entrypoint comparison; incrementalallocatedreceipt undercaps.
4. Actualcached3132 ownedisolatedfixture finalsource/rootfsRO/sourceRO/directPythonenvname/user/workdir contract; childimport absentPYTHONPATH, synthetic2bank years/makes/models HTTP→ownedchild→PG complete+partialprovenance/cooldowns/stallkillreap; config429/read_onlyquote/grant/library/paymentdeny/providerNone/SVGPNG compatibility. No actualcredentials/provider/testpaymentcalls, ownedsyntheticresourcesonly, cleanupreceipt, nobuild/pull.
5. Prepare compactcoherent39fingerprint/freshphysicalbackup/helperseal/rollbackcommand reviewpackage; anylivebackupSQLbeyondread-onlymetadata or candidate stage/activation heldforrootreview/exactapproval. No new91MBhomebaselines.
6. Publish milestone exactsource/image/fixture/capacityhashes forrootreview. Initialprobe remainsseparatelyheld; activationcanproceedwithoutGETafterapproval. Preservepayment/grant/article/rightsstate.

## Protected a82 checkpoint; capacity slot held by M2A

This is the current checkpoint and supersedes the b435 source/root/hold assumptions below or above. Product source is protected a82b31dc8850aa3956972928b8c720969765a972, tree11503a735d7d983ca3ebf090b471c89682e77278, after protected PR439. Read-only Git comparison confirms all worker files are byte-identical to b435; 272→a82 production delta remains exactly four modules,398 additions/34 deletions: catalog_service.py144/20, http_service.py2/6, selector_job.py228/0, source_connector_client.py24/8. Dockerfile, pyproject.toml, migrations and contracts are unchanged from272. No helper-branch source may enter the product archive.

Root verified historical readonly92 source.tar offload (33,392,640B, SHAfcf878bb07c54ab3c779cd66ae3bf23d7fe0995b7e133de2c26b668ec74e3abd); original tar absent and retained source mount unchanged. Root reported physical-home free7,371,923,456B at06:55; this is historical, unreserved evidence. M2A now owns the exclusive heavy package/build/browser capacity slot. HOLD all archive/extraction/fixtures/containers/build/activation until root releases that slot, then remeasure home/Docker admission and caps before any allocation. No provider GET. Existing running17295/source272/image3132 and stopped343 remain untouched; historical v6 outcome remains manual INCONCLUSIVE with no replay.

Eventual source root is /home/corp/autodata-candidate/private-initial-selector-a82b31d-20261115; physical execution root remains /home/corp/.local/state/autodata/initial-selector-runtime-20261115, not created by this checkpoint. Preserve128MiB total incremental physical-home cap/home admission7,314,866,176B/warmfloor7,180,648,448B and64MiB Docker allowance/admission880,803,840B/floor813,694,976B; coordinator may raise floors, never reserve promised headroom.

Current todo:
1. Commit fresh a82 gate/record/docs; synchronize Issue401/Project8, verify readbacks, pass machine preflight before implementation.
2. Hold archive/fixture/container work until root releases M2A slot; fresh capacity/identity readback before allocations.
3. Package immutable exact a82 archive/RO source plus manifest/file-and-directory fsync under caps; recheck four-module allowlist and image input/dependency/schema compatibility.
4. Run owned synthetic actual3132 HTTP/child/PG/read_only/SVG fixtures with synthetic credentials only; no shared persistent-role changes, builds/pulls or supplier/payment calls; verify cleanup and serving identity unchanged.
5. Hand exact package/seal/capacity/fixture and backup/rollback recipe to root; stage/activation still held for independent review and explicit coordinator authorization.
6. Keep first initial-selector real probe separate and held without positive internal-request-ended/fence proof; no route GET in activation and no configuration replay.


## Current source-only PR440 integration checkpoint

Protected `be1a1f235e8eeacc051ac905c4ed8a953a41c8a9`; current integration plan `docs/superpowers/plans/2026-11-15-pr440-protected-be1-integration.md`; all earlier source/runtime TODOs are historical and do not grant execution authority. Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8.

- Synchronize Issue401/Project8, corrected canonical current-versus-historical docs and matching records at a docs-only protected-base checkpoint; pass exact checkpoint preflight before copying helper files
- Copy the exact four helper and four test blobs from reviewed0212dd8d, run focused owned/offline tests and verify all eight Git blob IDs unchanged
- Push the refreshed draft PR440 with an exact old-head lease, update its base/head verification text and run required exact-head CI; hold merge, build, activation, runtime and provider requests for root
