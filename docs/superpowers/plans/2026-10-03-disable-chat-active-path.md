# Remove Chatbot from the Active AutoData Product Path

**Goal:** Retire the chatbot interface and runtime from the shipped dashboard, API, and default worker configuration so the direct catalog/article API is the only active product flow.

**Issue:** https://github.com/lucronn/autodata/issues/113  
**Project:** https://github.com/users/lucronn/projects/8  
**Architecture:** `docs/architecture/provider-neutral-catalog-api.md`  
**Related delivery:** catalog and workshop foundation in PR #117; ephemeral composition in PR #122. Prior draft PR #123 was closed without merge; this plan re-authorizes implementation on current master.

## Contract

- Direct vehicle cascade and catalog/article routes remain active and documented.
- Remove chat UI markup, client routes/state/event polling, chat API route registration, and default chat runtime/worker activation.
- A request to a removed chat route returns a normal API not-found response and never enqueues chat work.
- Chat services, schema, migrations, and historical records may remain dormant if deleting them would require data migration; no active endpoint, dashboard link, startup hook, or default worker subscription may reach them.
- Do not remove catalog article normalization, stored-source comparison, local media, or Workshop.
- Do not add labor or combined-procedure persistence.
- Keep Bankone and Banktwo as independent HTTP origins; do not reintroduce embedded bank builds.

## Concrete todo

- [x] Remove chatbot UI from the dashboard and replace the landing content with links to Swagger and Workshop.
- [x] Unregister all `/chat/*` routes and remove now-unused chat handler wiring from API startup.
- [x] Disable chat worker subscription, startup, and Compose defaults; ensure API/worker health and non-chat routes remain healthy.
- [x] Bundle same-origin Swagger UI assets required by the dashboard API Explorer link and Dockerfile embed.
- [x] Update API documentation, route tests, dashboard tests, and Compose assertions to prove chat is absent and catalog routes still work.
- [x] Run Go/worker/Compose verification and test the rebuilt local API's dashboard, chat-route 404, Swagger, and Workshop entry points.

## Validation boundary

Do not claim success from code inspection alone. The release criterion is structural tests plus a rebuilt local stack proving the dashboard no longer contains or calls chat, `/chat/*` is not registered, default workers do not subscribe/start chat, and `/openapi.json`, `/swagger/`, and `/workshop/` remain available.
