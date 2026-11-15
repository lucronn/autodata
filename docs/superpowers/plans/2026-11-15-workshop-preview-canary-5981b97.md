# Protected-source public Workshop preview canary

Issue: https://github.com/lucronn/autodata/issues/424
Project: https://github.com/users/lucronn/projects/8 item PVTI_lAHOCSJ8cc4BiQ2BzhI0NZI.
Canonical design: docs/architecture/workshop-preview-canary-5981b97.md
Receipt: docs/verification/2026-11-15-workshop-preview-canary-5981b97.md
Record: docs/agents/records/2026-11-15-workshop-preview-canary-5981b97.json

Goal: promote exact protected public API source5981b97f187364e54737919fd8cdb49e7566d981/treeb3f321d0263e12da2d5c54f136c9ffcee155e1d1 as a bounded purchase-disabled source-only preview canary on autodata.cars.tk, preserving private runtime/data/entitlement authority. PR422 protected merge is tree-identical to revieweded7ffa6; allthree required CI success43665654018. Root accepted the draft boundary and requires concrete helper/command review before runtime mutation.

## Scope and source pin

Create this docs-only checkpoint directly on the exact protected commit, synchronize Issue424/Project8 and canonicaldocs/record, commit/push then pass pinned preflight before preparing private artifacts/helpers. Build a full immutable git archive of5981b97, never from the later documentation branch or uncommitted checkout. Record archive SHA256, filemanifest, toolchain/flags/buildmetadata, binarySHA256 and all13embedded asset hashes. Build linux/amd64 Go1.26.4 with CGO_ENABLED=0 and -trimpath, then source suites appropriate to merged API. Existing requiredCI/source review is evidence; it is not final artifact/runtime acceptance.

Current expected public baseline is API3a18d9c/read_only/binary0b17821ca4892d7776126c349db5fe70d5292c893a9acdca2ae5e27c3f0f9f93; remeasure liveMainPID/exe/config/files before sealing. Private baseline must be exact running6fcc910d46d5740b556c2fc0d0ac527a9e180cf0f27c1a60e5d8815ca84ef9a4/image5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4/immutable92d81a1 source. Verify quote/library/grant/source-media compatibility of oldprivate with mergedGo using owning source; preserve all existing source rights/grant checks.

Only allowed effective live difference: new immutable API executable binary/path/embedded assets via existing99 systemd override. APIenv must remain byte-for-byte unchanged and explicitlyread_only, with staging/public audience/origin/auth/session settings unchanged. Preserve dependencydrop-in, serviceaddress/security, proxy/DNS, allprivate containers/source/image/env/network/security, DB/storage/NATS/data. No migrations, provider/model/article/ensure/media request, SVG privateimage installation, licensed recapture/display/testergrant/settlement or payment/customer/session mutation. Existing scoped entitled reads remain governed by unchanged authority; anonymous canary does not establish rights or authenticated reader acceptance.

## Private baseline and preparation

After preflight create new persistent0700 evidence root /home/corp/autodata-evidence/preview-canary-5981b97-20261115. Never overwrite existing historical artifacts. Retain rawconfig/backup/inspect0600 privately; publish safe hashes/counts/status only. Capture APIenv /etc/autodata/preview/api-public-preview.env and99 /etc/systemd/system/autodata-api.service.d/99-public-preview.conf exact bytes/uid/gid/mode;10-docker-dependency.conf metadata/hash; MainPID/executable/binaryhash; full privatecontainer contract; currentpublic/private disabledpurchase/readiness. Record source/archive/assets/binary and proposed override hashes. Rejectsymlinks/duplicate or non-read_only commerceconfig/inputdrift/unexpectedreplacement count. Newinstall path /usr/local/libexec/autodata/workshop-preview-5981b97-r1/autodata-api must be absent before preparation. Keep oldbinary untouched.

Read-only SQL fingerprint27protectedtables (auth/customer/entitlement/payment/checkout/order/publication/source/article/request/projection families) before/after preparation and postrelease, count+aggregate rowhash only, no rows/IDs/content. Build/probes are not allowed to trigger cataloghydration, account or article endpoints; unexpected protectedstate drift blocks and requires root decision, never baseline replacement or automaticDBrestore. No schema/data writes or privilegedSQL. Exact privatecontainer inspect comparison covers ID/image/mounts/restart/network/read-onlyroot/running. Stage may not recreate/restart it.

Build on persistent evidence filesystem with fresh free-space check and preserve cached artifacts; do not buildDocker/prune. Preparation writes only new evidence/helper/backup/targetpayload files; no live config install/restart. Reuse reviewed old probe/rollback design via new pinned manifest/source/environment-specific helper; old gate/helper commands must not be rerun because they target7ce6 and stripe_test→read_only. Newhelper allows check, prepare, restore only; it has no apply/install operation. Fixture tests must prove actualnewhelper drift refusal before backup/attemptreservation, exact bytes+ownership/mode restoration, duplicate/repeatedrollback denial and one inertrestart only. Reserve one attempt before any restore; atomic same-directory override replacement/fsync. APIenv restored only if within exact baseline/approvedexpected hashes, which are identical for this release.

## Concrete coordinator review boundary

Seal final manifest/helper/probe/test hashes and exactbaseline/targetoverride/binary/asset pins in docs and privateROOT-COMMANDS before rootreview. Provide no-secret commandallowlist for read-onlycheck, preparebackups, installartifact to newroot-owned0555 path, atomicallyreplace only99 withoriginalmetadata, daemonreload, oneAPIrestart, boundedcandidateprobe and explicitonfailureone-rollback. Root independently reviews exacthashes/config diff/protection/source/fixture results and authorizes execution after that review. This checkpoint permits preparation only; it does not authorize skipping the concrete review.

Rootexecution should recheck identity/config/dependencies/protectedstate immediately before switch, rejectstale input, save exactpersistent privatebackups, verifyinstalled artifacthash, and atomicallychange onlyoverride executable path. If artifact/config installfails restore exact oldoverride before restart. Restart onlyautodata-api.service once; never enable/reboot/restart dependencies. VerifynewMainPID/executablepath/hash/envunchanged/dependencyunchanged/privatecontractunchanged. Wrongidentity/readiness/assets/purchase/demo/protectedstate/browser signals require exactrollback, not anothercandidate.

Rollback restores originaloverride/env bytes andmetadata from pinned0600 backup, daemonreloads/restartsAPI once, rechecks oldbinary/executable/env/drop-in/private/readiness/purchasefalse. NoautomaticDBrestore. If rollbackfails preservecandidate/evidence and stop for rootrecovery. Realrollback remains unexercised until needed; fixturetest is not actualrecovery.

## Bounded anonymous acceptance

Probe with fixed allowlist only: loopback3031/healthz, local18080/healthz and/readyz, publiccanonical/healthz and/readyz, local/public/workshop/purchase-config.json and/demo-mode.json, knownWorkshoproutes,13embeddedassets andapexredirect/query. TLSverified, loopbackproxybypass,noredirectfollow,User-Agentcurl/8.0.0,Cache-Controlno-cache,identityencoding,JSON16KiBmax2seconds/request,assets1MiBmax5seconds/request. Absolute30second readiness phase with atmost10rounds andremainingdeadline-awaretimeouts. Requirehealth200, allreadydependencies, purchaseenabledfalse, demoenabledfalse, canonical/workshop/308→/workshop200, localloopback/workshop/200 andcars.tk/workshop307 to canonical/workshop/ preservingquery. Baseline/rollback existing3a source already supportsdemofalse; requireit inallphases. Candidate13assets match finalsource; baseline/rollback13assets match baselinebinary/source manifest. Do not addcachebustingqueries. Write only sanitizedresponsemetadata/hash/passedstatus; no account/checkout/webhook/orderstatus/article/media/provider/ensure/model paths.

FreshChromium mobile390x844+desktop1440x900 anonymousinspection must preserve sign-in initiallydisabled thenreadyenabled, nohorizontaloverflow/uncaughtappmessage and purchaseUIhidden. Rootmayapprove exactlyonepopupentry closedataccounts.google.com beforecredentials; no sign-in/sessioncreation. Captureonlysafeanonymousscreenshots/origins/results. This is source/productreadiness, notauth/payment/rights/articleacceptance. Independentpost-switchobserver rechecks runtimepins/disabledpurchase/privatecontract/protectedstate. Coldbootdurability remains separate.

Concrete todo:
- Synchronize exactbase plan/Issue/Project/canonicaldocs/record and pass pinned checkpointpreflight before artifact/helperwork.
- Build/hash exactprotectedsource/binary/assets; capturefresh privatebaseline/config/metadata/compatibility/protectedfingerprints with noservingmutation.
- Prepare boundedprobes/exactrollbackbackups/testedone-attempthelper and send concreteartifact/config/commandallowlist to root before runtime mutation.
- Onlyafterrootreview/decision execute oneAPIcanary and boundedanonymous/independentchecks or exactonerollback; recordactualoutcome/remaininggates.

No licensed bytes, IDs, credentials or rawprivateconfig inGitHub. Existing privateSVG compatibility14/14 remains privatehistoricalevidence and is not affected by this API-onlycanary.

## Prepared review package

Preparationgate fde78f74eafeb6101a969a16c2483fdc573d8edf passed beforeartifact/helperwork. Exactbinary/config/probe/helper/commandhashes, sourcearchive tests,40baselinechecks androllbackfixtureevidence are sealed in the canonicalverificationreceipt. Allthree preparationtodos completed; rootconcretereview/runtimeexecution/acceptance remains pending. Nohelperapply orservingmutation. PrivateHANDOFF.md andROOT-COMMANDS.md supply the exactreviewableallowlist.

## Physical execution package and local Docker amendment

Root review blocks the earlier execution package under autofs/loop-backed autodata-evidence: reboot/mount durability is unverified. Keep it historical; it is not an activation/rollback source. Before package/helper edits, synchronize this amendment/Issue424/Project8/canonicaldocs/record and pass a new pinned checkpoint. Move/reseal to fresh physical `/home/corp/.local/state/autodata-preview-canary-5981b97-20261115` on `/dev/nvme0n1p11` ext4, verified by findmnt and device/realpath checks. All execution/rollback helper, manifest, artifact, probe, protected baseline and original/target backups must resolve exclusively under physical package; no loop/autofs file dependency may remain. Existing installed previousbinary/config/systemd/private serving-source paths are inspected dependencies only, not copied execution/rollback payload references. Retain oldpackage unmodified as historical evidence.

Pin Docker calls to `/usr/bin/docker --host unix:///var/run/docker.sock`, with an explicit fresh empty physical DockerCLI config and a minimal fixed child environment (no inherited DOCKER_HOST/DOCKER_CONTEXT/DOCKER_CONFIG/TLS/proxy/PATH overrides). Pin critical systemctl/Python child executables to absolute paths too. Verify read-only actual localdaemon baseline under hostile inherited Docker/PATH/config settings; fixture tests must prove generated inspect/exec argument/environment contracts and context override isolation. No remote daemon or inherited CLI context selection is permitted. Recheck physicalmount/device/path contract at helper load before operations.

Amendment todo:
- Synchronize/commit this exact amendment and pass pinned preflight before relocation/helper edits.
- Copy/reseal execution package onto physicalhome; preserve oldpackage; regenerate all rootpath-sensitive manifest/helper/probe/browser/command/hash pins.
- Pin localDocker/minimal childenv/physicalconfig and test hostilecontext/PATH overrides plus exact metadata/one-attempt rollback on isolated fixtures.
- Rerun exact livebaseline/read-only40probes/protected27 checks and send fresh concrete package for independent rootreview; no serving mutation until that review.

## Activation marker and durable override amendment

Before changing package/helper, synchronize this additional rootreview requirement and pass the amended checkpoint. restore() must refuse before reserving rollback or restarting unless the physicalpackage contains the exclusive activation-attempted marker bound to the exactmanifest, with validated owner/mode/nosymlink/content. Fixturetest no-marker refusal before writes/restart/rollbackreservation, then oneallowedactivationmarker/rollback and repeatedrollbackrefusal. Rootreserves thatmarker exclusively beforeinstall/switch.

Make the promised durable atomicreplacement explicit: fsync stagedoverridefile and containingdirectory before rename; after same-directory rename fsync finaloverridefile and directory before daemonreload. Rollback's atomic_restore must fsync the restoredfile and containingdirectory too. Rootcommandallowlist must contain exactbounded fsync operations; no implieddurability frominstall/mv alone. Allmanifestartifact/probe/browser/helper/backup/command paths must be physical; retain loopbackpackage onlyas historicalevidence.

## Current prepared execution root

Use onlyphysical `/home/corp/.local/state/autodata-preview-canary-5981b97-20261115`, finalhelpermanifest `8ee47c6705ee4a0ac62c8282580485808f004f6956fdbf74ad06992c32be4eed`. Priorautofs/loopexecutionpathisblocked/historical. Amendmentgate801a964 passed beforechanges; physicalpath/localDocker/minimalenv/activationmarker/fsync/user+rootcontext/no-navigationChromiumfixtures andfreshbaselinepassed. Canonicalverificationreceipt containsallfinalhashes. Rootconcretereview/activation remains pending; no serving mutation.

## Deterministic browser QA and exact safe auth routes amendment

Independent review blocksactivation: browser QA deniedrequired GET/auth/config and post-domcontentloaded initialDisabled sampling couldfalse-failfasthealthybootstrap. Before QAhelper/fixture edits, synchronize this amendment/Issue424/Project8/canonicaldocs/record and pass pinnedpreflight. These areprivate test-tooling changes, notproduct/UI/runtimebehaviorchanges.

Routepolicy mustpermit exactsame-origin GET/auth/config and GET/auth/session (noquery) whiledenyingallwrites andotherprotecteddynamicroutes. Theactualanonymousappautomaticallyrequests GET/v1/catalog/years afterauthbootstrap; suppress onlythatknownGETprefetch withoutdispatch/providertrigger and recordit separately as expected canarysuppression, notcatalogacceptance or unexpectedwrite. Otherprotected/writerequests remainfailures. Coordinator explicitlyagreed tothisboundary.

Make signintransitiondeterministic byholding onlythebrowser's safe/auth/config completion behindaboundedclient-sidebarrier. Navigateatcommit, observeattachedsigninbuttondisabled whilebarrierclosed, thenrelease andrequirebuttonreadiness. Neverdependonpost-DOMContentLoadedtiming/sleepsforinitialstate. Includehandoffdisclosureofcontrolledrequest/suppressedcatalogscope.

Meaningfulregression: locallyserveexactprotectedWorkshopHTML/bootstrap/app/authassets withsyntheticauthconfig/session andfixtureFirebaseSDK (noexternalnetwork/provider). Testexactrouteallow/deny/expected-suppressioncontract, fastconfig/smallpagehealthytransition andwronginitialenabled/missingreadyfailures; exerciseactualQAfunctions fromactualpage. Keepfixtureslocal/noaccount/sessionwrites, no publicnavigation. Rerunexactclean-envChromiumlaunch, physicalbaseline40checks/protected27, andmanifest/packageintegrity. ResealallphysicalQA/probe/helper/command/dependencyhashes andsendfreshconcretepackageforindependentrootreview; no servingmutation.

## Browser QA final review seal

Browser amendment checkpoint `c140fd4d9ab4a2ca439cd3bf35c4b27952af203e` passed synchronized preflight before QA edits. Product source `5981b97f187364e54737919fd8cdb49e7566d981`, binary, release manifest, rollback helper, HTTP probe and executable shell command blocks are unchanged. Only private QA tooling, its fixture evidence and command documentation changed.

Current physical package: `/home/corp/.local/state/autodata-preview-canary-5981b97-20261115` (203 sealed files).

- Helper manifest: `7de273c6df8dba83d39c38870e2ddadd5378076ecb5d1ebe80c6b27db31f98b7`.
- Release manifest: `8047ee4ddc638626db7b43e5506987b03fa9c45cd7eb733f409fb67d4a0a3674` (unchanged).
- Rollback helper: `7a2c8f1440e099dbc548b4af3a0d9ae697c03e412c421ab672a089222c766927` (unchanged).
- Browser acceptance: `99b2f9eb578096c408d34f02ff86e7633a84ae8bda5f3412bcb753fc4a7f056c`.
- Shared browser contract: `1c25a9461b724ac760de7fb3e9f1bd9603a9c668022208cc4cc8b2fa6970c9fa`.
- ROOT-COMMANDS.md: `70edfa89fa2f158a1eef201fe425804a3412bed1eff8aca174bcd7770a45fcba`; executable command blocks are unchanged.

The browser permits exact GET `/auth/config` and `/auth/session`, waits until config interception is observed while held, samples the disabled button, releases config, then requires sign-in readiness. Writes and other protected requests fail QA without dispatch. Only the known automatic GET `/v1/catalog/years` receives a browser-local synthetic empty complete response, separately recorded. This suppresses provider HTTP; it is **not real catalog acceptance**.

The controlled local fixture serves actual protected HTML/bootstrap/app/auth assets and synthetic auth/session/SDK responses. It reproduced the prior post-DOMContentLoaded false failure causally, passed mobile and desktop transitions with config not dispatched before the initial sample, and rejected initially enabled, never-ready and missing-interception cases. Exact safe auth GETs reached the fixture; unexpected writes/protected GETs did not. Critical-error remained empty. Public requests, provider catalog requests and serving mutations were zero.

Clean-env no-navigation Chromium launch passed again (Playwright 1.62.1, Chromium 145.0.7632.159). Fresh baseline output: phase baseline, passed true, 40 checks, receipt `baseline-probes-1794710587519019968.json`. Read-only check output: `{"baseline_identity":"verified","live_mutation":false}`. Protected check output: `{"protected_tables_equal":27,"live_mutation":false}`.

Updated sealed files versus prior 8ee47 manifest: ROOT-COMMANDS.md (QA explanation only), browser_acceptance.cjs, new browser_contract.cjs, new verify_browser_contract.cjs, new browser-contract-fixture.log, new baseline probe receipt and new postqa-protected-check.log. Physical HANDOFF.md and physical-preparation.json contain the exact delta and current pins.

No root rollback state, activation marker or installed candidate exists. Independent root re-review and execution remain pending. No public runtime mutation, provider recapture, licensed-content exposure or private image rollout occurred.

## Same-attempt privileged read-only checks amendment

Root has completed prepare, the exclusive activation marker and immutable candidate install. API override/service have NOT switched. The unprivileged post-install helper check failed with PermissionError because valid rollback-state is root0700; the same sudo clean-env check passed. This is an execution-command permission correction within the existing attempt, not a new activation.

Synchronize this amendment/Issue424/Project8/canonicaldocs/record and pass pinned preflight before editing package commands or manifests. Keep source/binary/release manifest/rollback helper unchanged. Never rewrite the existing activation marker, root backups, installed binary or service configuration. Do not repeat prepare/marker/install/restart.

Run post-prepare/post-install check, post-switch candidate-check (including independent QA recheck) and failure protected-check under `/usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 /usr/bin/python3` using the physical helper path. Initial pre-prepare historical check may remain unprivileged; the continuation command uses sudo because root-only state now exists.

Verify helper check/candidate-check/protected-check branches only inspect/read (no create/replace/fsync/restart path). Add isolated root-only0700 state fixture proving privileged read-only dispatch, unprivileged denial and unchanged metadata/bytes for checks. Rerun actual root check/protected-check against current baseline without switching API. Capture safe dynamic marker/root-backup/installed-binary hash+metadata before/after, without raw config/content, to prove no changes. Reseal static commands/fixture evidence/helper manifest and send exact command diff/hash pins for root re-review. Dynamic release state is retained, never included as mutable payload in a new static seal.


## Same-attempt privilege correction final seal

Planning checkpoint `97b8530aaa51fecf050e54845e0966857087fb9c` passed synchronized preflight before package edits. This supersedes earlier absent-marker/state/install statements: root already completed prepare, exclusive marker and candidate installation; the API still runs baseline old3a/PID620960. No new prepare/marker/install/restart/switch was performed.

Physical package `/home/corp/.local/state/autodata-preview-canary-5981b97-20261115`; 211 static files sealed by helper-manifest SHA256 `c55f87a2af8d062ba223db5a6312eeb994c2790a60bb81a6e8eb44ac4df3f218`. ROOT-COMMANDS.md SHA256 `cfbb389bfeed404611241d597ab5492c2ce55086872ca58f465a521623028016`. Exact diff `same-attempt-command.diff` SHA256 `1d29d31c267796bda580c811e17f3a976f83c1ff524c26dd06d0ca9ed1ed1479`.

Executable command delta is exactly four `/usr/bin/sudo ` prefixes: post-install `check`, both post-switch `candidate-check` calls, and failure `protected-check`; all retain clean env and physical helper. Steps1–3 are clearly historical and MUST NOT be repeated. No helper/product/source/release-manifest change. Release manifest remains `8047ee4ddc638626db7b43e5506987b03fa9c45cd7eb733f409fb67d4a0a3674`, helper `7a2c8f1440e099dbc548b4af3a0d9ae697c03e412c421ab672a089222c766927`, binary `ad5ad70c777a19c2446275cf7640e8777429d3fc3bb334cc3522ff43e1d29750` from protected source5981b97/treeb3f321d.

Root0700 synthetic state fixture passed all three check dispatches under sudo, denied them unprivileged, and preserved bytes/metadata. Actual helper check call graph inspection found no file mutation; production SQL explicitly read-only. Actual sudo baseline output `{"baseline_identity":"verified","live_mutation":false}`; protected output `{"protected_tables_equal":27,"live_mutation":false}`. Shell syntax PASS. Candidate identity check is fixture-only before switch. Safe before/after hashes+uid/gid/mode/size/mtime/ctime for existing marker/root backups/installed candidate/live env+override plus PID/exe are byte-identical. Dynamic state is excluded from static payload; receipts contain hashes/metadata only. No raw config/content emitted.

Only static command instructions/syntax extraction, isolated fixture/script/log, safe before/after receipts, package metadata/handoff and manifest were updated. Existing dynamic marker, root backups, installed binary and live configuration/runtime remain unchanged. Root review is the next step for continuation of the existing attempt. Purchases and licensed exposure remain disabled; no provider calls/recapture/private image rollout.


## First attempt CLOSED — recovered baseline; do not retry

Candidate identity and candidate probe40 passed. Browser mobile/desktop had all acceptance fields pass except one denied POST per viewport. Exactly one rollback was invoked; the helper reported immediate `rollback_executable_mismatch` after restart. This reported verifier failure is distinct from recovery: independent root checks subsequently verified old executable/PID1178108, original override/env hashes, baseline probe40 and protected27 PASS. Existing activation marker and rollback reservation remain preserved. No second marker or restart is permitted under that attempt.

Read-only bounded browser reproduction against recovered old source identified same-origin POST `/cdn-cgi/rum` without query, resourceType xhr; it was aborted. Cloudflare documents this as automatic Web Analytics telemetry (https://developers.cloudflare.com/web-analytics/faq/). It is not required app authority. A new package may classify only exact same-origin query-free POST `/cdn-cgi/rum` as browser-local synthetic suppression with no network dispatch; all other writes remain blocked and acceptance-failing.

## New attempt preparation gate — no activation

Prepare a fresh physical package `/home/corp/.local/state/autodata-preview-canary-5981b97-attempt2-20261115` and new installed binary path `workshop-preview-5981b97-r2`. Retain protected source5981b97/treeb3f321d and exact binaryad5ad70c. Never copy/reuse old activation marker/root backup/rollback reservation or write old package. Re-capture safe baseline metadata and protected counts, independently recheck source/binary pins; target only executable path to r2. New release manifest/hash and helpers/commands must bind this new package; root review required before any prepare/install/marker/switch.

Rollback verifier currently samples MainPID executable immediately after Type=simple start of `/usr/bin/env ... binary`; env may not have execed the pinned binary yet. This is a plausible timing race, not proven forensic causation. Add bounded monotonic identity polling after exactly one restart: tolerate missing PID/process and transient env, require old executable+hash and active service within deadline, then run existing bounded readiness/asset probe. Polling never restarts service. Timeout fails closed and retains one-attempt reservation. Synthetic fixtures must cover env→binary, PID0/disappearance, permanent mismatch/timeouts and exactly one inert restart, alongside existing marker/drift/fsync/repeat refusals.

Concrete todo:
- Record first attempt as closed and independently recovered; synchronize Issue424/Project8/canonical docs/record and pass pinned gate before new package edits.
- Create fresh physical package with no dynamic attempt state; preserve source/binary and new exact path/manifest pins.
- Suppress only exact Cloudflare telemetry locally and test negative route variants plus actual protected app bootstrap.
- Fix bounded rollback identity/readiness verification; test race/timeout and single restart on isolated synthetic files only.
- Run clean-env browser launch/baseline/protected checks, reseal new package/commands and send root review; perform no serving mutation/provider/account/payment writes.
