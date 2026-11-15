# Private M2A V3 safe error-origin diagnostic

Issue: https://github.com/lucronn/autodata/issues/398
Project: https://github.com/users/lucronn/projects/8
Implementation source base: a9b5b6325de0ffaf3d53c0152bdd53141d31514f. Physical runtime remains668d4c86; no build/package changes.

## Todo

- Preserve physical serving source/archive/binary/config/manifest, original authored stores and all consumed markers; independently seal only the offloaded V3 harness and tests
- Add red-first no-dispatch tests and bounded durable closed-schema origin/stage/operation diagnostics without raw JavaScript messages, stacks, URLs, headers or protected responses
- Use exclusive V3 namespaces and unchanged tmpfs/home capacity guards; synchronize exact hashes and proposed one-use operational seal for root review before any service, relay or browser action

## Evidence and purpose

V2 completed desktop/mobile article and image assertions but failed strict final validation with one entry in the shared page_errors bucket. Current offloaded harness line 260 records page.on("pageerror") as a fixed page_error string, while line 281 catches response-validator failures into that same bucket. Final serialization collapses the origin further. Existing safe records cannot establish which path fired or its original stage, including whether it preceded article navigation. Do not infer a product JavaScript exception or waive the zero-error requirement.

The four image HTTP200 events are directly recorded by the route journal. Real PNG byte/hash/MIME/dimensions and visible image were executable assertions passed before both layout completions; screenshots provide visual evidence. Full strict acceptance remains failed.

## Minimal proposed implementation boundary

After a fresh synchronized preimplementation gate, change only the offloaded scripts/dev/workshop_owned_article_smoke.py and its owned test file. No physical source/archive/binary/manifest/config or serving assets change; no Go build or source copy. Pin existing physical runtime and new offloaded harness/test hashes separately in an append-only V3 operational seal.

Add a separate bounded safe error journal (exclusive 0600 creation, at most 16 records and 8KiB total, durable fsync on each record), leaving V2 and route-journal schemas untouched. Fields are closed enums/numbers only:

- origin: page_exception or response_validator;
- stage: existing SAFE_STAGES enum captured when the event/response is observed;
- code: fixed page_exception, known allowlisted assertion code, or response_exception;
- category: existing safe route category or lifecycle;
- status: integer HTTP status or zero;
- operation: page_event, body_read, json_decode, or field_assertion.

The pageerror handler snapshots the current stage synchronously and never reads error.message/stack. A response handler snapshots stage/category/status before its first await, tracks only a fixed operation enum, and records those captured fields on rejection. This prevents a late body-read failure from being mislabeled as a later navigation stage. Keep error counts separate in final output, with bounded safe records and error-journal hash. No raw JavaScript messages, stack, URL, headers, response bodies, token or arbitrary string is persisted. Source locations are omitted in the minimal proposal.

Preserve strict zero page/validator/console errors, unchanged context-close/navigation ordering, original authored body/image fixture, exact one session shim, no response fulfillment for catalog/article/image, no quote/prepare requests, and all existing title/body/order/history/auth/commerce assertions. Do not hide a possible context-close race by changing lifecycle timing in this diagnostic.

## Red-first no-dispatch proof

Owned Node/filesystem tests only: independently inject a page event and a response-validator rejection; verify distinct origin, captured stage and operation. Reject raw or extra fields and enforce bounds. Delay a synthetic body rejection across a stage change and prove its original response stage survives. Verify known assertion-code allowlisting, discarded arbitrary error text, exclusive 0600 creation and durable prefix after synthetic process termination. Re-run existing focused tests without Chromium. Add explicit physical source_guard/admission and runtime-import boundary proof; only the offloaded harness changes. Pin the changed harness hash at launch before import/execution.

## Gate and one-use execution plan

Create synchronized plan/record/Issue398/Project8/canonical ops references on the exact reviewed harness branch/head (currently a9b5b6325de0ffaf3d53c0152bdd53141d31514f, or root-provided successor). Commit/push docs-only checkpoint and pass machine preflight before the two implementation files. Issue398 stays open; V3 is authored private acceptance, not provider/Firebase/Stripe acceptance.

Use new V3-only operator, attestation, launcher, browser marker, journal, screenshot and outcome paths with exclusive creation; neither V2 marker can be reused. Review/seal the exact operator, launcher, harness and physical package hashes before start. Ordered same-six fixed-ID phases and read-only re-attestation must establish 63 tables, original six authored rows, 42 migrations, two original S3 objects, all other operational rows zero; verify actual binary/assets/local auth/commerce and a fresh API lifecycle binding. No seed/reset/INSERT/PUT/customer/grant/job writes.

Obtain separate root authorization for exactly one relay on 127.0.0.1:3042 and one 120s browser dispatch. Keep desktop1440x1000/mobile390x844 assertions, real image200/PNG151B/hash/64x48/visible screenshot and all existing controls. On any outcome stop relay, read-only post-attest if feasible, stop all exact six services and verify no listener, attachments or owned browser processes. Preserve failure/success journals, screenshots and tmpfs residual metadata. No automatic retry.

## Capacity conditions and risks

Use a fresh explicitly root-approved post-containment baseline; do not silently reset cumulative accounting. Physical-home cap64MiB, early guard32MiB with32MiB remaining reserve, entry minimum7,247,757,312B and warm abort7,180,648,448B. Independent /tmp tmpfs cap128MiB/guard96MiB, entry512MiB; MemAvailable minimum1GiB; Docker free minimum813,694,976B and1000 free inodes. Short private /tmp profile/HOME/TMPDIR and existing default-sandbox cached browser only. V2 measured peak physical-home growth3,473,408B and tmpfs44,814,336B are supporting estimates, not guarantees. No physical build is required. Concurrent unrelated growth remains a risk; live guards must stop owned children before reserve violation.

Read-only planning measurement: physical-home free7,262,937,088B; /tmp7,033,995,264B; Docker1,003,974,656B. This is not an admission receipt or execution approval. Old binary copy-only archival does not release physical-home capacity until root separately reviews/executes unlink. Do not assume that gain.

## Archival mapping

Obsolete held cfb binary historical source /home/corp/autodata-workshop-owned-article-data-20261115/held-bed88597-package/autodata-api, SHA256 cfb7828a592bb416942cb5f544addf195037f959958dc68f0809b1dfef45c78d,61,405,300 logical bytes. Preview lane reports copy-only target /home/corp/autodata-evidence/local-staging-runtime-draft-20261115/held-bed88597-autodata-api, receipt held-bed88597-autodata-api-copy-receipt.json SHA535a31122baa7daa780d795659fc1195890060346f33fdb1241e5d41aaef5462, independent hash/fsync verified. Root completed exact scoped cleanup; original is absent. Cleanup receipt SHA256 b3c89ad3749606941f31337e5dcff840518c04a5529049d074771ba29adfce16 maps the preserved offloaded copy. Historical E1 package-seal.json SHA1e5273674b8ce99957aa4ec3b417da7b4633966a835d0447d22e48408089ca1b retains prior_binary_mapping; preserve its bytes and append mapping/cleanup evidence if root later removes the old alias. Current V2 operational seal does not depend on the old binary.

## Allowlist and execution hold

Implementation allowlist: scripts/dev/workshop_owned_article_smoke.py and scripts/dev/test_workshop_owned_article_smoke.py only. Documentation allowlist: this plan, matching record, docs/operations/workshop-owned-article-m2a.md and docs/verification/2026-11-15-workshop-owned-article-m2a.md. All writes are on verified offloaded ext4. No physical runtime or data edits. Runtime/relay/browser explicitly held for root review; proposed seal is not execution approval.
