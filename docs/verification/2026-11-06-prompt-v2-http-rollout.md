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
