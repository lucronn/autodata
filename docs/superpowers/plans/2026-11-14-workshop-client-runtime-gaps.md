# Workshop client runtime route compatibility

Goal: Avoid unusable Workshop quote requests when purchasing is not enabled and honor explicit local authentication mode when choosing the existing article read route, preserving paid Firebase preparation and existing authorization.

Issue: https://github.com/lucronn/autodata/issues/430
Project: https://github.com/users/lucronn/projects/8
Canonical document: `docs/architecture/workshop-client-runtime-gaps.md`
Record: `docs/agents/records/2026-11-14-workshop-client-runtime-gaps.json`
Implementation source base: `4048f3f` (protected master at dispatch).

## Verified gaps and decision

selectVehicle currently awaits quote regardless of merchant.enabled, so source-only runtimes can produce an unnecessary503 before continuing article reads. Guard only the quote try/catch with merchant?.enabled === true; retain the remainder of selection unchanged.

loadArticle currently always POSTs prepare, but local-auth servers do not mount that paid route. Add nullable normalized mode to createSession.state, set only after a current successful auth/config response to exact local/firebase values, and reset on clear/bootstrap. In loadArticle, choose GET article with the existing requestArticleJSON transport and abort signal only for mode === local; otherwise preserve the current prepare POST/body/CSRF. Feed the actual first response into unchanged rendering/polling. No synthetic DTO, entitlement, identity, cookie, or grant is added.

Implementation paths: apps/api-go/workshop/app.mjs, apps/api-go/workshop/auth.mjs, apps/api-go/workshop-client.test.mjs. Planning/architecture/verification documents may also change. No API, ingestion, commerce backend, Firebase SDK, sample, auth authority, runtime assets, deployment, or CI changes.

## Concrete todo

- Request and validate vehicle quotes only when purchase configuration enabled is exactly true; retain article loading, enabled Stripe TEST quote handling, and stale/abort protection.
- Expose only normalized local/firebase auth configuration mode in session state; reset it on invalidation/bootstrap and keep authenticated cookie validation unchanged.
- Use the real authenticated GET article route instead of POST prepare only for explicit local mode; retain prepare for Firebase, absent, malformed, or unknown mode.
- Add focused regressions for quote gating, enabled quotes, mode reset and races, local GET, paid prepare, article polling, missing authentication, and stale/aborted navigation; run the complete client/demo tests and syntax/diff checks.
- Commit and push the validated milestone for coordinator review; hold PR/CI until coordinator resolves the #429 base boundary. Do not merge, deploy, mutate M2A, or call provider/payment/auth services.

## Verification and boundary

Use only local mocked transport executing production functions. Test enabled=false/missing/malformed config produces zero quote calls and still loads article index; enabled=true validates a quote and preserves 503 tolerance and abort/stale behavior. Test mode defaults/reset/unknown/failure/obsolete bootstrap; local authenticated article makes GET without prepare/body/CSRF, Firebase and unknown modes POST prepare exactly as before, stale or aborted reads cannot publish, and signed-out local mode cannot read. Run client/demo suites, JS syntax checks, and git diff --check. M2A browser checks are coordinator-owned: open authored vehicle/index/article/image with zero quote and zero prepare requests in explicit local mode. This lane does not mutate that runtime.

## Synchronized record

```json
{
  "goal": "Avoid unusable Workshop quote requests when purchasing is not enabled and honor explicit local authentication mode when choosing the existing article read route, preserving paid Firebase preparation and existing authorization.",
  "plan_ref": "docs/superpowers/plans/2026-11-14-workshop-client-runtime-gaps.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/430",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/architecture/workshop-client-runtime-gaps.md"
  ],
  "todo": [
    "Request and validate vehicle quotes only when purchase configuration enabled is exactly true; retain article loading, enabled Stripe TEST quote handling, and stale/abort protection.",
    "Expose only normalized local/firebase auth configuration mode in session state; reset it on invalidation/bootstrap and keep authenticated cookie validation unchanged.",
    "Use the real authenticated GET article route instead of POST prepare only for explicit local mode; retain prepare for Firebase, absent, malformed, or unknown mode.",
    "Add focused regressions for quote gating, enabled quotes, mode reset and races, local GET, paid prepare, article polling, missing authentication, and stale/aborted navigation; run the complete client/demo tests and syntax/diff checks.",
    "Commit and push the validated milestone for coordinator review; hold PR/CI until coordinator resolves the #429 base boundary. Do not merge, deploy, mutate M2A, or call provider/payment/auth services."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-15T03:31:42.402593+00:00"
}
```

## Verification checkpoint

Pushed planning checkpoint `c991311` passed synchronized machine preflight before implementation. The complete client/demo suites pass 287 tests with zero failures/skips. See [verification evidence](../../verification/2026-11-14-workshop-client-runtime-gaps.md). Coordinator retains PR/CI, M2A runtime, release, and deployment control.
