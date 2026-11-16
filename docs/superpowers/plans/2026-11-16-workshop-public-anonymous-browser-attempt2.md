# Anonymous public browser attempt2 preparation

Goal: Prepare separate one-use anonymous public browser attempt2 correcting only proxy-host resolution, safe connection diagnostics and terminal empty-selector readiness; preserve failed attempt1

Issue: https://github.com/lucronn/autodata/issues/431
Project: https://github.com/users/lucronn/projects/8

## Todo

- Synchronize Issue431/Project8/plan/canonical record with failed attempt1 evidence and a fresh attempt2 checkpoint before implementation
- Add exact loopback resolver exclusion, safe network-code/proxy-stage counters and terminal empty-selector assertion with red-first pure tests
- Create a fresh offloaded attempt2 package and unused marker mapping, pin unchanged public/private source/runtime and toolchains, prove no-dispatch dry admission and seal for root review

## Failure and owning evidence

Root consumed attempt1 exactly once. Immutable PACKAGE-SEAL6e42bf1f remains preserved. OUTCOME384f79c8330d8460778074712bba982d27f6c24df8a77cf0558965f62cfa405e, BROWSER-RESULTce863864117037d3d200d7dabe10fd32a6b80807a571f53f3a968df18183f01c and journal8ea0524edbc77eaa96aa72b2f0fb0e4d97bf866c676b776f8b8cf4baefecb305 record navigate1440/real_resource_failed. Screenshot613a319a90400e535da99513b7989715c00c6e0663b2734ba75fcb790cb9196f shows ERR_PROXY_CONNECTION_FAILED. Proxy accepted0/upstream0/bytes0; no public response was observed. No claim of an article/image/auth/config GET is supported. Root verified owned process/listener absent, tmpfs profile removed, public/private unchanged. Never modify attempt1 marker, artifacts, journal or screenshots.

[Chromium's primary proxy documentation](https://new.chromium.org/developers/design-documents/network-stack/socks-proxy/) explicitly requires excluding the proxy host from MAP * ~NOTFOUND; without it, requests fail with PROXY_CONNECTION_FAILED. The retained earlier local fixture flags already excluded127.0.0.1. This is the harness resolver omission, not a product/UI or provider failure. No extra hostname is exempted: browser resolves only its loopback proxy, while proxy resolves only the admitted public API hostname.

## Narrow delta and retained boundary

Implementation allowlist remains exactly scripts/dev/workshop_public_anonymous.py, scripts/dev/workshop_public_anonymous.cjs and their two matching test files. Documentation allowlist: this plan/new record, original anonymous-browser plan/record and canonical document. No API/product/package/dependency/provider change or install.

Replace the sole browser resolver flag with `--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1`; expose a pure launch-config function so tests prove exact proxy/exclusion, sandbox enabled, no direct fallback/other exclusions. Classify requestfailed using a finite allowlist of Chromium network error identifiers plus safe route category; never emit raw error text/URL/body/header. Add bounded proxy counts for accepts/header rejection/upstream attempted/connected/failed/client I/O; no addresses or raw input. Persist these in outcome on failure. Tighten existing empty-year UI assertion to terminal Choose year plus No choices status rather than initial Loading; use the same function in pure DOM fixtures and future page wait.

Fresh package `/home/corp/autodata-evidence/workshop-public-anonymous-a82b31d-attempt2-20261116`, absent marker and new random tmpfs profile; never copy attempt1 output/marker into it. Keep identical actual public/private source, binarybb11/PID1293423/start19892443/env74a/99b9/protected27, cached runtime/dependency hashes, proxy authority/concurrency/buffer/byte/time limits, strict real static/auth only route policy, synthetic years/RUM only, no sign-in click, no provider/catalog/article/payment/auth-write dispatch, mobile/desktop dimensions, 120s browser bound and exact owned cleanup. Original gate28c56893 remains historical; this checkpoint precedes attempt2 helper edits.

Capacity policy unchanged: home strict5,570,035,712B entry,32MiB growth stop/64MiB cap; rootfs2GiB+32MiB, Docker813,694,976B, offload1GiB free/artifact4MiB, tmpfs128/96MiB/512MiB free,1GiB MemAvailable. Fresh measurement only; no builds, physical writes, cache cleanup or runtime activation. Default dry must forbid subprocess, DNS, connect and bind; pure Python/Node tests only. Report exact source/tree/helper/test/package/review seal and command to root before any browser/proxy/network. Root must separately approve one attempt2 dispatch; none is authorized now. Issue431 remains OPEN/Project8 In Progress; real Firebase/catalog/supplier/article/rights/Stripe acceptance remains separate.
