# Local Workshop image token compatibility

Goal: Render server-issued local Workshop opaque image references only in explicit local auth mode, retaining default and Firebase v2-only image URL validation and existing server authorization.

Issue: https://github.com/lucronn/autodata/issues/438
Project: https://github.com/users/lucronn/projects/8
Canonical document: `docs/architecture/workshop-local-image-tokens.md`
Record: `docs/agents/records/2026-11-15-workshop-local-image-tokens.json`
Protected source base: `f534d0aeb76973ca3b8c70b14c806973edb1b457`.

## Decision

Go rewriteCatalogImages emits /v1/catalog/images/ followed by a randomized, encrypted base64url token without a version prefix in local mode. Client localImageURL currently requires v2 unless broad compatibility is enabled; addImage therefore omits img entirely. Add authMode exact local acceptance for unprefixed tokens bounded to38..6000 base64url characters, excluding impossible base64url lengths congruent to1 modulo4. The38-character lower bound is the encoded28-byte AES-GCM nonce+tag minimum. Keep v2 acceptance unchanged, require the same existing parsed origin/path/query/hash/credential constraints, and do not enable compatibility. Pass mode in addImage and reconcileImages. Server decryption/session/storage authorization remain unchanged.

Implementation files: apps/api-go/workshop/catalog.mjs, apps/api-go/workshop/app.mjs, apps/api-go/workshop-client.test.mjs, and one new apps/api-go/catalog_image_client_test.go. No production Go, auth, commerce, infrastructure, or runtime changes.

## Concrete todo

- Add an explicit authMode option to localImageURL accepting unprefixed opaque base64url image tokens only for exact local mode; preserve same-origin, exact image path, no-query/hash/credentials, and v2 defaults without enabling broad compatibility.
- Pass current session mode to initial image rendering and media reconciliation; preserve unavailable-image handling and generation checks.
- Add red-first Node regressions and a Go-to-Node actual sealed-token contract test covering local rendering/renewal, default/Firebase rejection, v2 behavior, and malformed/cross-origin URLs; run client/demo and relevant Go media tests.
- Push a coherent validated milestone and PR with exact gate/head/tests; coordinate with root before M2A service/browser work. Do not restart services, call providers/payments/Firebase, merge, or deploy.

## Verification

Fail meaningful Node cases and a Go-to-Node bridge on unmodified production first. Bridge derives the existing test key, seals a real local object reference, invokes the actual client validator with Node, and requires local-only acceptance plus opaque-token roundtrip. Test renderer emits img for referenced step image only in local mode and reconciliation updates local tokens; test malicious URLs rejected in local/default/Firebase modes. Existing v2 tests remain. Run node client/demo suites, relevant Go media tests, JS syntax and diff checks. M2A browser proof is a separate coordinator-controlled next step; services remain stopped.

## Synchronized gate

```json
{
  "goal": "Render server-issued local Workshop opaque image references only in explicit local auth mode, retaining default and Firebase v2-only image URL validation and existing server authorization.",
  "plan_ref": "docs/superpowers/plans/2026-11-15-workshop-local-image-tokens.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/438",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/architecture/workshop-local-image-tokens.md"
  ],
  "todo": [
    "Add an explicit authMode option to localImageURL accepting unprefixed opaque base64url image tokens only for exact local mode; preserve same-origin, exact image path, no-query/hash/credentials, and v2 defaults without enabling broad compatibility.",
    "Pass current session mode to initial image rendering and media reconciliation; preserve unavailable-image handling and generation checks.",
    "Add red-first Node regressions and a Go-to-Node actual sealed-token contract test covering local rendering/renewal, default/Firebase rejection, v2 behavior, and malformed/cross-origin URLs; run client/demo and relevant Go media tests.",
    "Push a coherent validated milestone and PR with exact gate/head/tests; coordinate with root before M2A service/browser work. Do not restart services, call providers/payments/Firebase, merge, or deploy."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-15T04:35:05.796867+00:00"
}
```

## Verification evidence

Checkpoint `16e0c50d` passed preflight before implementation. The two new Node regressions and actual Go-to-Node token contract first failed on unchanged code; after repair307 client/demo tests and15 top-level Go media tests passed with no skips. See [verification](../../verification/2026-11-15-workshop-local-image-tokens.md).
