# Persistent prompt-v2 HTTP rollout verification

Status: synchronized planning only; no deployment performed under this gate.

Goal: Refresh only the persistent purchase-disabled Workshop ingestion HTTP service to the exact reviewed merged prompt-v2 source, proving a shadow on 3032 before a reversible 3031 swap.

Plan: docs/superpowers/plans/2026-11-06-prompt-v2-http-rollout.md; record: docs/agents/records/2026-11-06-prompt-v2-http-rollout.json. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Dedicated field: Prompt-v2 HTTP rollout reference.

Exact product pin b3618fb6e68f1734ef029096748e30e655451a26 / tree b686966c9bb4c01c7d35262c661f8645f9fb9f04. Existing reviewed PR350 source and successful one-shot Bankone canary do not mean the persistent3031 service has been refreshed. Existing container/source remain the rollback artifact;3032 shadow proof must precede3031 substitution. Environment/secrets/image/security are preserved, no API restart or generic worker/model/provider request. Actual rollout health/config/state/rollback evidence remains unverified until coordinator dispatch.

Concrete todo:

- [ ] Freeze the active container/image/source and private effective configuration; verify the exact reviewed merged b3618fb6 source tree, disabled purchase and absence of active generic article workers before deployment.
- [ ] Materialize a new immutable exact merged source tree; create a same-image shadow HTTP-only container on 127.0.0.1:3032 with the preserved effective configuration and only source/name/listen-address differences; verify bounded local health and no model/job execution.
- [ ] After shadow proof, retain the untouched original container, stop it and create/start the exact-config source replacement on 3031; verify private health, public readiness, disabled purchase, source hashes and unchanged protected state, or immediately restore the original container.
- [ ] Retain original container/source and private evidence, remove only the temporary shadow, and synchronize the exact rollout outcome without claiming ongoing automatic processing, starting a generic worker or making model/provider calls.

Tracking readback verified: https://github.com/lucronn/autodata/issues/186#issuecomment-6695151451 and dedicated Project8 field `Prompt-v2 HTTP rollout reference`; exact goal/four todos/source/rollback scope matched. No existing Project fields or historical Issue bodies/comments changed.


## Corrected-create amendment planning

Status: original first shadow was created but never started; stopped diagnostic2775219a07cf needs exact-identity cleanup. Original3031 remains healthy. No successful shadow health or source swap is claimed.

Goal: Remove only the never-started diagnostic shadow and complete one corrected, configuration-verified prompt-v2 HTTP source rollout while preserving the healthy original3031 runtime for rollback.

The plan amendment authorizes one corrected attempt after a new full-SHA preflight/dispatch. Require exactly40 unique env entries with one shadow-address replacement, preserved false AttachStdout/Stderr, a new private per-container CID path, only constrained null-to-false OomKillDisable default normalization, and complete stopped-container diff review before shadow or final startup. All worker/model/article/provider/commerce prohibitions and exact-original rollback remain unchanged. No cleanup/deployment by this documentation agent.

Amended concrete todo:

- [ ] Preserve the failed first-attempt inspect/diff privately; verify diagnostic shadow2775219a07cf is the exact stopped never-started rollout container, then remove only that container without volumes or changes to the healthy original3031 service.
- [ ] Construct one corrected shadow create payload from exact private original Config/HostConfig using Docker Engine API or an exact equivalent; require exactly40 unique environment entries with one AUTODATA_INGESTION_HTTP_ADDR replacement to3032, preserved attach settings and only explicitly approved metadata normalization.
- [ ] Before starting any corrected shadow or final container, independently compare complete inspected configuration against the frozen original and allow only the enumerated source/name/shadow-address/new-private-cidfile/default-OOM differences; prove shadow3032 health while original3031 remains untouched.
- [ ] Only after shadow proof and final stopped-container diff approval, swap3031 once with exact original40-entry environment; verify health/readiness/purchase-disabled and unchanged protected state or restore original, retaining all rollback/source/evidence and authorizing no worker/model/provider/article call.

Amendment tracking exact readback verified: https://github.com/lucronn/autodata/issues/186#issuecomment-6695220078 and dedicated Project8 `Prompt-v2 HTTP rollout reference`; original Issue history/other fields unchanged. Fresh full-SHA checkpoint required.


## First final cutover blocked and restored; second-final planning

Coordinator-reported outcome: corrected3032 shadow passed with unchanged database. First final passed payload review and local3031 health200, but a single immediate public HTTPS check raised transient HTTPError and caused rollback. Final was removed. Original3031, public /readyz and purchase config are now200/enabled:false after brief restart convergence. No DB/model/article/provider calls. This remains a blocked/rolled-back attempt; exact private error status/timing is retained rather than inferred.

Goal: Complete one second final-container prompt-v2 HTTP cutover using the unchanged approved payload and passed shadow proof, with bounded readiness polling and exact-original rollback.

Fresh amendment allows one final creation using the same approved payload except new name/private CID path, with no new shadow only if complete prior shadow/source/image/config proof is unchanged. Full stopped diff before stopping original; <=10 rounds/30seconds phase for local health/public readiness/purchase-disabled, plus a separate <=10round/30second original rollback verification. No further retry or worker/model/commerce scope. No runtime action performed by planning agent.

Second-final concrete todo:

- [ ] Retain the first final-attempt failure and successful original-runtime recovery as immutable private evidence; verify original3031/public readiness are200, purchase disabled and prior shadow/source/image/configuration proof remains exact before retry.
- [ ] Create exactly one fresh final container from the same reviewed payload, changing only its unique name and new private final-http-r2.cid path; require the complete stopped-container inspect diff and original40-entry environment match before stopping original.
- [ ] Swap3031 once and poll only local health, public readiness and public disabled-purchase configuration in at most10 sequential rounds within30seconds; record transient failures without issuing article/provider/model/work requests.
- [ ] On failed acceptance stop/remove only this new final and restart exact original, polling the same recovery endpoints for up to30seconds; retain all original/source/evidence, report recovery incomplete if needed, and synchronize the exact result with no further automatic retry.

Second-final exact tracking readback verified: https://github.com/lucronn/autodata/issues/186#issuecomment-6695299434 and dedicated HTTP Project8 field; historical comments/other fields preserved. New full-SHA preflight and coordinator dispatch required.


### Canonical public probe host correction

Before the still-unused r2 final creation, coordinator verified canonical `https://autodata.cars.tk/readyz`=200 and `https://autodata.cars.tk/workshop/purchase-config.json`=200/enabled:false. Use those exact no-redirect URLs for cutover and rollback; apex cars.tk/readyz404 and apex Workshop308 are not acceptance endpoints. The [rollout plan](../superpowers/plans/2026-11-06-prompt-v2-http-rollout.md) is corrected; same r2 payload/name/CID, ONE unused final attempt, unchanged passed-shadow proof and30second/10round/30GET phase limits. No new runtime/worker/model/article/provider/commerce scope, and no runtime action by the planning agent. Fresh full-SHA corrected preflight/dispatch required.

Canonical-host correction exact Issue/Project readback verified: https://github.com/lucronn/autodata/issues/186#issuecomment-6695326964; other fields/history preserved.


### Third-final fixed public-probe User-Agent amendment

Complete one third final-container prompt-v2 HTTP cutover using the unchanged approved payload, exact public probe User-Agent curl/8.0.0, bounded acceptance and exact-original rollback. Coordinator reports r2 rolled back; exact original3031/local/public readiness/config now200/enabled:false. Read-only diagnosis: Python urllib default User-Agent403, same canonical requests with explicit `User-Agent: curl/8.0.0`200 with/without proxy; no app failure is inferred. Keep both rolled-back attempts historical.

The [rollout plan](../superpowers/plans/2026-11-06-prompt-v2-http-rollout.md) now authorizes ONE r3 creation with the same approved r2 payload except name/private final-http-r3.cid. Require fresh synchronized checkpoint/preflight/dispatch, unchanged passed-shadow proof, exact stopped diff, same original40-entry environment/security, and exact fixed public header on baseline/cutover/rollback canonical GETs. Existing30second/10round/30GET phase limits and exact-original rollback remain. No additional shadow/fourth create, header fallback, worker/model/article/provider/API/commerce action or paid-launch claim. Planning agent touches no runtime.

Third-final concrete todo:

- [ ] Preserve the second rolled-back attempt and read-only User-Agent diagnosis; verify original3031/canonical readiness/purchase config200/enabledfalse and unchanged source/image/private configuration/passed-shadow proof before a third final creation.
- [ ] Create exactly one third final container from the same approved r2 payload, changing only its unique r3 name and exclusive new final-http-r3.cid path; require full stopped-container diff and exact original40-entry environment before stopping original.
- [ ] Swap3031 once and use exact User-Agent curl/8.0.0 for canonical public readiness/purchase GETs within the existing30second/10round/30GET acceptance limit; do not use default-UA probes, redirects, alternate identities or article/model/provider/work calls.
- [ ] On failed acceptance restore the exact original and verify recovery using the same fixed-header bounded30second polling; retain all rollback/source/failed-attempt evidence and report the exact outcome without any further automatic create/retry or worker/commerce scope.

Third-final exact tracking readback verified: https://github.com/lucronn/autodata/issues/186#issuecomment-6695399260 and dedicated HTTP Project8 field; other fields/history preserved. Fresh exact committed-base preflight/dispatch required.


## Successful persistent HTTP source refresh outcome

The coordinator executed the independently reviewed r3 script under exact gate `8dc02ef17615bded824bda45b5a2d7cda0ae8a62`. This documentation agent inspected the private result and exact script bytes; it performed no runtime operation. The r3 receipt is passed. New container `38f3bc41eb2433096fe469c6b4dd4d368d52a28b43ba678c395b48ba7c478e22` runs the persistent loopback3031 HTTP service from reviewed merged prompt-v2 source `b3618fb6e68f1734ef029096748e30e655451a26`, tree `b686966c9bb4c01c7d35262c661f8645f9fb9f04`. All1217 tracked source entries passed exact blob/mode verification and the source-extras guard. Original `3cefb07d948ae5bbee3d1cde52a8f41e5dcf837ccbdb8143f67284ff3f90dcfe` remains intact and stopped for rollback. Image, original40-entry environment, effective security/network/resource settings and reviewed configuration contract remain preserved; only approved source/name/new-private-CID/default-OOM representation differences were accepted.

Read-only probes used explicit `User-Agent: curl/8.0.0`, verified public TLS and no redirects. Baseline local3031 health, canonical `https://autodata.cars.tk/readyz` and `https://autodata.cars.tk/workshop/purchase-config.json` each returned200. Cutover round1 recorded local ConnectionRefusedError, public readiness200 and purchase-config503; round2 returned200 for all three endpoints and the script required strict purchase `enabled:false`. Nine total probe events preserve those transients. The first two final attempts remain historical blocked/rolled-back attempts; this successful outcome does not erase them.

The before/after inherited DB fingerprint was identical: `17a93216483b82cfb313a2125731e7c978d3cd6ce25addbf5f9c0a917df946b4`. The additional complete-row guard was also identical: `e23250e004e11a09552c86c2169dcc3a2bc0401b733667452b364f76412c7a8e`. The script recorded zero article/model/provider calls and no DB mutation. It did not start a generic or selected article worker, drain jobs, change commerce or restart the API. The still-disabled purchase configuration and refreshed HTTP code do not establish ongoing automatic article processing or paid-launch acceptance; worker activation requires its separate gate.

Evidence: reviewed private script SHA256 `593f808887c71731be9145d50a60d92e598aece9dd96f322bdb1e915f2bfdb8a`; private `third-final-result.json` SHA256 `a623cf5bbc778057e243021cfeca7404d8e50bfe22c320806b280202875dc84e`; final canonical-payload SHA256 `65ee1a593026f2425fadbbf153dc18f34b4cfa58b54eefad0a104b33845641bd`. Raw inspect/environment/CID files and source content stay private. The one r3 creation allocation is consumed; this evidence update authorizes no additional deployment or retry.

Outcome checklist:

- [x] Preserved both failed attempts and read-only User-Agent diagnosis; exact original/proof prerequisites verified.
- [x] Created one r3 from the approved payload with fresh private CID/name and accepted the full stopped-container diff before cutover.
- [x] Completed bounded fixed-header canonical acceptance on round2; purchase remains disabled and both DB guards are unchanged.
- [x] Retained original/source/private evidence and synchronized this narrow HTTP-only result; no worker/model/provider/article/commerce expansion.

Outcome tracking exact readback verified: https://github.com/lucronn/autodata/issues/186#issuecomment-6695577548 and dedicated HTTP Project8 field. Other Issue history/worker fields preserved.
