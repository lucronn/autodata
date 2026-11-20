# Local Workshop image token verification

Issue: https://github.com/lucronn/autodata/issues/438
Project: https://github.com/users/lucronn/projects/8
Plan: [local image tokens](../superpowers/plans/2026-11-15-workshop-local-image-tokens.md)

## Gate and implementation

Pushed planning checkpoint `16e0c50d` is rooted at protected source `f534d0aeb76973ca3b8c70b14c806973edb1b457`. Issue/Project readbacks matched the goal, plan and todos. Preflight before implementation returned `{"status":"synchronized","errors":[]}`.

Client accepts an unprefixed token only for exact authMode local, only in the existing same-origin /v1/catalog/images/ route, and only for bounded base64url syntax. Default/Firebase modes still require v2. Both initial image creation and token reconciliation pass current session mode. Broad compatibility is not enabled, and server decryption/session/authorization are unchanged.

## Red-first evidence

On unchanged production code, both new Node regressions failed: local opaque URL acceptance returned null and the referenced step emitted no img. The Go-to-Node contract also failed because the actual URL produced by rewriteCatalogImageURLs/sealCatalogImageReference was rejected by the local client. This test uses a real randomized sealed token, not a synthetic client-only fixture.

## Passing checks

- `node --test apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`: **307 passed, zero failed/skipped**. Includes referenced step image rendering, local-token renewal, stale-generation protection, default/Firebase v2 restrictions, and malicious origin/path/query/hash/credential/encoding rejection.
- From apps/api-go: `/home/corp/go-sdk/bin/go test . -run 'Test(LocalCatalogImageTokenClientContract|CatalogImage|PaidCatalogMedia)' -count=1 -v`: **15 top-level tests passed**, including actual producer/client integration and existing paid-media authorization tests, no skips. The bridge explicitly skips only if Node is absent; Node was present and the bridge ran here.
- JS syntax checks for app.mjs and catalog.mjs: passed.
- gofmt on the new Go test and git diff --check: passed.

## Runtime boundary

No runtime, M2A data or service state was changed. No provider, Stripe or Firebase request was made. Root must coordinate the isolated M2A rebuild/start and browser check. Expected next proof is a visible referenced image with actual same-origin opaque image request and successful decoded PNG, while keeping the six-service runtime stopped until authorized. This source verification is not runtime acceptance or deployment evidence.

## Modern Web Guidance

Reviewed validate-origins and security. Retained parsed URL tuple comparison rather than introducing hostname-prefix matching, following the same-origin fallback rule: “parse both the candidate and trusted URLs with new URL()”. Expanded local-mode tests retain those origin boundaries; no broad compatibility path or DOM HTML interpolation was introduced.
