# Workshop client runtime gaps verification

Issue: https://github.com/lucronn/autodata/issues/430
Project: https://github.com/users/lucronn/projects/8
Plan: [client runtime compatibility](../superpowers/plans/2026-11-14-workshop-client-runtime-gaps.md)

## Synchronized boundary

Implementation began only after pushed checkpoint `c991311` rooted at protected source `4048f3f`. Issue/Project readbacks matched goal, plan, and todo, and machine preflight at exact checkpoint returned `{"status": "synchronized", "errors": []}`. Preflight was repeated at the same checkpoint after implementation and still passed.

## Verified changes

The quote request now runs only for exact `merchant.enabled === true`; otherwise the existing authenticated catalog/article path continues. Enabled configurations retain the scoped quote, validation, error tolerance, and abort/current-generation checks.

Session state exposes only normalized `local`, `firebase`, or null config mode and resets it on clear/bootstrap. Mode does not authenticate a session or enable login. Only explicit local mode selects the actual GET article response; default, Firebase, missing, and unknown modes retain the existing POST prepare/body/CSRF flow. Existing session validation and server authorization remain the authority.

## Local evidence

Seven focused new regression cases failed on the unchanged implementation before repair. After repair:

- `node --test apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`: **287 passed, zero failed, zero skipped**.
- `node --check apps/api-go/workshop/app.mjs`: passed.
- `node --check apps/api-go/workshop/auth.mjs`: passed.
- `git diff --check`: passed.

New tests execute the production functions with local transport doubles and cover disabled/missing/malformed config making zero quote calls while preserving catalog loading; enabled valid/invalid/unavailable quotes; signed-out and canceled selection; known/unknown config mode; invalid session rejection; clear/bootstrap reset, stale config, failure and abort; local-only GET without prepare/body/CSRF; unchanged Firebase/default prepare; actual repeated GET polling responses; and stale/canceled local and Firebase article reads. No external provider, payment, or authentication request was made.

## Coordinator-owned runtime verification

M2A has not been mutated or exercised by this lane. After coordinator base/release coordination, a private authored M2A check should observe explicit auth/config mode local, purchasing disabled, no quote requests, no prepare POST, a real authorized GET article response, readable stored steps and PNG, working Back, and no quote503/prepare405 warnings. An explicit image reference remains a fixture requirement. Enabled Stripe TEST quote/prepare paths are covered locally with mocks; this document claims no provider transaction, customer login, deployment, or runtime acceptance.

PR creation/PR CI is held for coordinator resolution of the #429 base boundary. No merge or publication is authorized by this evidence.

## Modern web guidance

The network-request and asynchronous cancellation topics were searched and the catalog reviewed. No specific guide matched these configuration-controlled route choices; no new platform API, layout pattern, or guide-backed change was introduced.
