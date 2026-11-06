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
