# Complete Paid Workshop Customer UI Implementation Plan

**Browser client response loss correction (2026-11-03):** [2026-11-03-workshop-browser-client-response-loss](2026-11-03-workshop-browser-client-response-loss.md) governs a two-file fixture repair after the exact `8a1746dc6b449c77dd3adab5794669a5155b7bf5` Chromium pilot failed with hidden Retry and correct processing UI. Existing `control/lose-response` loses the provider response; preserve its commerce processing/same-key coverage. The browser scenario must instead fetch a real successful checkout, abort its browser response once, then retry the identical key/body and prove one order/session with unchanged provider calls. Keep all customer assertions/deadlines,21/120 inventories, private HOME, frozen supervisor and six image build inputs; no product changes. Builder owns only `scripts/dev/workshop_browser_smoke.py` and `scripts/dev/test_workshop_browser_smoke.py`, with unit/syntax/inventory checks and no Docker/browser/provider/cloud execution. Task `docs/agents/tasks/2026-11-03-production-release/2026-11-03-workshop-browser-client-response-loss.json` and record `docs/agents/records/2026-11-03-workshop-browser-client-response-loss.json` carry the synchronized todo; coordinator reviews the committed exact-SHA gate before implementation and owns fresh pilot/full21 provenance/cleanup acceptance. Failed receipts remain unchanged; API acceptance and production readiness remain unverified.

Concrete todo: 1) Synchronize Issue186/Project8, the dedicated plan, canonical UI plan, queue, task and record; commit/push the checkpoint and pass exact-SHA preflight before independent coordinator approval. 2) Add failing async route regressions for actual API fetch before browser abort, exact one-shot scope, same-key/body retry, unchanged real response forwarding and fail-closed invalid responses. 3) Replace the first real-API case provider lose-response control with browser-route response loss after successful checkout; retain retry visibility, hosted redirect, exact request reuse, durable order/session and provider-call assertions. 4) Run focused browser fixture units, syntax, 21/120 inventory, frozen-input and two-file scope checks; commit/push the coherent fixture fix and obtain independent exact-commit review. 5) Coordinator integrates the reviewed fix, reruns the Chromium pilot then the unchanged full21 actual API inventory at a clean immutable SHA using the frozen supervisor/image, and independently checks raw provenance and cleanup.

**Real-API fixture HOME repair (2026-11-03):** [the bounded private-home plan](2026-11-03-workshop-browser-private-home.md) governs only the pytest final browser subprocess environment and its new focused unit test. The exact `2de36a1` API21 run failed all 21 cases before browser startup because UID1000 lacked a passwd home and the fixture dropped `HOME`. The failed run is retained; no browser behavior was verified. The new gate preserves the 3+6+6+6 API and 120 DTO inventories, frozen wrapper/image, customer assertions and separate live staging requirements. Implementation waits for a committed synchronized record and exact-base preflight.


Current dispatch amendment: [parallel delivery](2026-11-03-workshop-parallel-delivery.md) replaces serial implementation prerequisites. A synchronized exact-base gate still precedes edits; complete dependency/runtime verification remains required for release acceptance.
> For agentic workers: use the approved plan execution/review workflow only after the coordinator commits this plan, synchronizes its task/Issue186/Project8/canonical documents, pins integrated dependencies and passes machine preflight. This draft authorizes no implementation.

**Goal:** let a customer safely browse, sign in with Google, buy the selected configuration and region for $20 USD once, and return to purchased articles/source/media from My vehicles.

**Architecture:** one final customer UI lane replaces the future split auth-only R4 and payment UI execution. Retain native HTML/CSS/ES modules and the ordered-document renderer; consume verified Firebase039, commerce040 and paid-access HTTP contracts without creating client payment/access authority. Self-host the official pinned Firebase app/auth bundle inside existing Go-embedded Workshop assets. No runtime frontend service, Stripe.js, framework, client entitlement ledger or new API is introduced.

**Tech stack:** existing Go1.26 embedded assets, native browser modules, Firebase web12.19.0, esbuild0.28.2 build-only, Python Playwright1.64.1 verification-only. Execution/review profile gpt-6.1-sol / medium / Fast(priority), no fallback.

**Specification:** docs/architecture/workshop-commerce.md and the preserved ordered-source/lifecycle/media/cancellation requirements in docs/superpowers/specs/2026-11-03-source-fallback-web-design.md, amended for the final paid product and explicit prepare POST.

## Inspection and gate prerequisites

Inspected clean root `9e958698d77eaa8c624e5e06c2c6984eb634ac83`. Actual current files are workshop/{index.html,app.mjs,catalog.mjs,styles.css} **plus** progress.mjs; preserve and test the latter rather than assuming only four files. Current app has localStorage/demo bearer, uses configuration.vehicle_id, one-shot detail GET, no customer purchase/library flow and no implemented browser runner. Existing workshop-client.test.mjs has fourteen helper tests; workshop_test.go checks embedding/source-review markers. Browser files mentioned in the earlier R4 plan are planned files, not existing executable acceptance.

Dependencies: canonical Firebase identity plan (official Admin Go4.22.0), canonical commerce plan and canonical `docs/superpowers/plans/2026-11-03-workshop-paid-access.md`, committed by coordinator at fcbabf1c5c501ccc830d618542953a41722835d6 (inspected file SHA256 cd8e75b93a8df9a52a142733dc7c7d4bd221af5f6776c1083eeb1b56af38cb9b; approved source draft4ebb8b0e8ff62edf32769472a3064ee257b81c52f51b7f893efee88935a75f8a). Their implementation is not asserted integrated/verified by this UI draft. Before UI gate the coordinator must re-pin the final verified039+040+paid-access base and check actual OpenAPI/handlers/fixtures, including literal order-state/error field names, quote/library DTOs, CSRF helper behavior and prepare acknowledgement. Do not implement compatibility guesses or accept several speculative field aliases. Any missing backend contract returns to its owning lane for a reviewed amendment; UI does not add business endpoints.

Actual039 candidate additionally inspected read-only: 8c750723dd0af0ecf054a2daa08616c88b785d92, auth_http.go/auth_session.go/auth_firebase_test.go/auth_http_test.go. Its /auth/config field names and /auth/session authenticated/roles/expires_at/csrf_token shape match the plan; exchange and logout return204 with no JSON body; mutations use X-CSRF-Token and browser-generated exact Origin. Dependency503 is AUTHENTICATION_UNAVAILABLE with retryable:true; unavailable local exchange uses that code with retryable:false/login_available:false, so code alone cannot select retry/login behavior. Forbidden account and CSRF errors both use FORBIDDEN: distinguish by current operation, never assume every403 means account revoked. Existing newFirebaseSDKFixture and its token(t,mutate) produce fixture-project signed tokens and actual local certificate/user verification; reuse in the new same-package fixture server where applicable, with second-user fixture behavior explicitly implemented there rather than modifying frozen SDK tests. This candidate is evidence of actual symbols, not a claim of integrated039 acceptance.

Coordinator supersedes the auth-only R4 goal and separate future payment UI task, preserving all earlier reading/browser criteria. Amend canonical source-fallback/Firebase/R4 docs to distinguish public selector metadata read-through from observational paid GETs and explicit paid prepare POST. Issue https://github.com/lucronn/autodata/issues/186 ; Project https://github.com/users/lucronn/projects/8 . Actual owner legal/contact/tax details and Firebase/Stripe/domain registration remain external configuration prerequisites, not invented content or reasons to block deterministic implementation.

## User flow and state boundaries

Use page navigation sections, native buttons/links/selects and the existing visual style; no new modal framework. Header has Browse, My vehicles, Sign in with Google or Sign out. Public browsing works even if sign-in is unavailable. Do not put API/storage/model/job-ledger/provider-registration details in the customer flow.

Selection is exactly the server's configuration.id + its returned region, with year/make/model/engine/trim and readable region shown before purchase. Preserve public query/history selectors and search; never use configuration.vehicle_id as purchased scope. No private article list/detail/source/progress/media is requested while signed out. Selected public quote is DB-only; fetch `/v1/workshop/quote?configuration_id=<id>&region=<region>` and display server price only when amount_minor=2000,currency=USD, product_key/terms version and scope match expected contract. Format $20 USD / one-time; never accept a browser price or a broader family/VIN scope. Do not display article previews/counts before access is established.

After a valid session, one observational exact-scope article-list request may establish whether the server permits opening this selection:200 renders the paid index,403 ENTITLEMENT_REQUIRED shows purchase,403 ENTITLEMENT_REVOKED shows revoked access with configured contact,503 is unknown/retryable and must not be treated as unpaid. Existing loaded library ownership can offer Open immediately, but server reads still decide access. An unloaded page of the library is not evidence that a customer does not own a selection.

The quote/purchase panel shows the complete selected vehicle configuration, region, one-time price and an unchecked agreement checkbox linked to the actual published terms/refund/privacy/contact configuration. Primary action before sign-in is Sign in with Google; after sign-in and confirmed missing grant it is Buy for $20 USD. Already owned opens without payment. Revoked does not offer automatic repurchase/restoration. Payment unavailability, unknown quote or incomplete merchant terms disables buying while browsing remains usable. Customer copy explains account ownership with no renewal, subject to published terms and source availability, without promising offline export/all future content or an immutable snapshot.

My vehicles loads owner-only `/v1/workshop/library`, default20/max50 using server cursor and Load more. Do not infer owner/account from email, URL, public IDs or Firebase claims. Show paid→Owned, ready to open; preparing→Preparing articles; viewable→Open articles; revoked→Access revoked and configured contact. Paid/preparing can be opened and retry content without checkout. Source unavailability does not change payment ownership or offer another charge. No invented completion percentage. Empty state links Browse; library dependency failure preserves no stale protected article body and provides explicit Retry. Cursor pages cannot overwrite a newer account/selection generation. Required `next_cursor` is nullable string: null and an empty string both end pagination; a nonempty cursor is opaque and forwarded unchanged with URL encoding. Missing, wrongly typed or excessively long cursors are malformed. An unloaded page is not evidence that a purchase is absent.

### Checkout and return

`POST /v1/workshop/checkout-sessions` requires app cookie, current CSRF, JSON `{configuration_id,region,terms_version}`, and cryptographic UUID Idempotency-Key. One in-flight creation per selected scope and attempt, disable double activation. Reuse the same key/body on a bounded transport retry or manual retry of the same unresolved attempt; never generate a new key merely because a response was lost. Preserve only non-secret attempt UUID/scope/returned order UUID in sessionStorage for same-tab return/reload; never store cookies, CSRF, ID/refresh/provider tokens, source/article bodies or media URLs there. Clear attempt metadata on explicit logout/new sign-in or owner404. Do not automatically POST checkout after reload or a return URL. A new attempt after authoritative expiration requires a fresh explicit purchase confirmation; server decides whether the old session is nonchargeable. No local timer frees a server order or creates a replacement checkout.

Handle checkout discriminant checkout/processing/owned exactly as the integrated backend: hosted checkout URL only in checkout; processing enters order status; owned opens the server library scope with no payment. Validate hosted URL is HTTPS, no username/password or explicit port, no whitespace/control characters, and exact hostname checkout.stripe.com with a nonempty supported `/c/pay/` path. Preserve the exact provider-returned opaque fragment; official Checkout Session URLs use it. No custom/untrusted return URL or Stripe.js; navigate the top-level page to the server-returned hosted URL. A future provider-host change requires a deliberate reviewed allowlist amendment.

Fixed success/cancel destinations use the validated server public origin: production cars.tk or the explicit HTTPS staging origin. Both return to `/workshop/?order=<stored-order-UUID>`. Browser consumes only the opaque UUID `order` return parameter; a `success=true`, session ID, status string or mismatched URL configuration never grants access. Fetch owner-only `/v1/workshop/orders/{order_id}`; unknown/other owner404 clears attempt and shows a safe unavailable-order state. The version-v1 order status is HTTP200. Literal states `expired` and `canceled` require `retry_disposition: new_key`; `creating`, `open`, `processing`, `paid`, `reconciliation_required` and `revoked` require `do_not_repay`. Creating/open/processing/reconciliation_required remain unresolved. Do not conflate this DTO with checkout’s state-specific200/201/202 response, or quote `purchase_terms_version` with checkout `terms_version`. Paid financial state prompts a fresh library/exact-scope authorized read; only an actual server grant permits content. Canceled/expired permits a deliberate server-controlled next action, never automatic charge. Revoked clears protected data. Returning from Cancel does not assume payment failed: check owner order because settlement may race navigation. Allow return resolution after sign-in without replaying a checkout POST.

Order polling is sequential,120s absolute budget, delays1/2/4/8/10s (then10s), each request<=10s and remaining time, honor longer Retry-After within budget. Stop on terminal/owner denial/logout/selection change or exhausted budget; show Check payment status manually. Only transient transport or retryable429/503 retries, no overlapping fetch or new-charge loop. Rendering and financial status remain separate from article preparation.

## Official browser identity integration

Verified public npm registry metadata/archive, no ambient keys or cloud calls: firebase12.19.0 archive integrity `sha512-kwXCLcI0ly2lkwygkbuRx6SsX3DSO96355YrWh9SWZ5ncsxK/y5cirn3sY6nZVSiBVE++2nL6Hchzu1EB8uohQ==`, https://registry.npmjs.org/firebase/12.19.0 . It resolves @firebase/app0.16.2 and @firebase/auth1.13.6. Auth archive integrity `sha512-MKRLvF72HJ/irNn2fJR0Gv5FOZNtqv1IBeJHRwK8l8pZ/wi9vuUw8ecyCMvQDDNxfS6uW0MWACL5KC4Y8Pp+fA==`; archive was fetched and integrity checked, and auth-public.d.ts confirms initializeAuth, setPersistence, inMemoryPersistence, browserPopupRedirectResolver, signInWithPopup and reauthenticateWithPopup. Auth/app require Node>=20, compatible with inspected Node22.23.1. Latest Firebase13.2.0 was deliberately not selected because its auth dependency requires Node>=24.12; no runtime/toolchain upgrade is needed.

Official wrapper imports initializeApp from firebase/app and initializeAuth, inMemoryPersistence, setPersistence, GoogleAuthProvider, browserPopupRedirectResolver, signInWithPopup, reauthenticateWithPopup, getIdTokenResult and signOut from firebase/auth only. Initialize exactly one named app from complete public `/auth/config` Firebase values, then `initializeAuth(app,{persistence:inMemoryPersistence,popupRedirectResolver:browserPopupRedirectResolver})` and **await setPersistence(auth,inMemoryPersistence) before enabling the popup button**. Never call getAuth for implicit defaults, browserLocalPersistence/browserSessionPersistence/indexedDBLocalPersistence, connectAuthEmulator or a fallback custom verifier. Tests must exercise actual bundled SDK storage behavior; deleting app localStorage calls alone is insufficient. Provider-owned Google cookies are not app-token persistence.

Bootstrap public `/auth/config`, then cookie `/auth/session`, same-origin credentials/cache:no-store. Explicit login_available:true and complete expected Firebase config alone enable Google; false/missing/malformed config shows unavailable and retains public browse. Session response is the authority for authenticated/roles/expiry/current CSRF, not Firebase currentUser. A valid app cookie after reload works without recovering any Firebase ID token. SDK load/init failure keeps sign-in unavailable; never offers local/demo auth or loops.

When session is valid, cookie-only reload does not initialize Firebase or request provider-user/token state. When sign-in is needed, prepare SDK/config/persistence before the user clicks so signInWithPopup starts directly within a user gesture. Use GoogleAuthProvider with no additional scopes or staff claims. Read fresh token only in memory and POST `/auth/firebase/session` with application/json, X-Autodata-Session-Exchange:1 and browser-generated exact Origin; then fetch `/auth/session`. Do not set forbidden Origin manually, put a Firebase token in Authorization/query/storage, or assume popup success created an app session. Drop raw-token references after exchange; sign out the Firebase SDK after successful application exchange so its token is not retained unnecessarily in memory. No assertion that JavaScript can erase immutable string bytes.

If SDK token-result auth_time is stale (>5min) or exchange requires fresh sign-in, offer a new explicit Confirm Google sign-in gesture using reauthenticateWithPopup(currentUser,provider); if no user remains, signInWithPopup. Fresh getIdToken(true) alone cannot repair stale auth_time. One explicit retry, no popup/redirect loop. SDK local claims inform only this UX;039 performs actual verification/authority. Fixed distinct copy for popup canceled, popup blocked, unavailable config, invalid/expired session401, account denial403 and dependency503; never render raw SDK/provider/internal errors. 401 clears protected state and offers login only when availability is explicitly true;403 clears protected state without interpreting every denial as sign-in;503 is a retryable outage with no stale authenticated fallback.

Logout calls `/auth/logout` with current CSRF/JSON-origin contract, immediately aborts/clears protected UI and SDK state, then awaits durable revoke. If the server cannot confirm logout, say Sign-out could not be confirmed and offer Retry; don't claim server session revocation. Public browse remains. Changing app account is explicit Sign out then Sign in; no role/org/account selector. BroadcastChannel can send a token-free logout/invalidation notice to other tabs; it carries no identity or data and is not authority. Every tab rechecks session on pageshow/focus before resuming protected work.

## Reader, source, media and cancellation

Create article-read.mjs preserving prior planned interfaces: requestArticleJSON returns `{status,data,retryAfterSeconds}` and CatalogRequestError exposes safe status/code/retryable/retryAfterSeconds/requestId. readArticle(read,{signal,onUpdate,wait,now,budgetMs:120000}) is sequential with1/2/4/8/10s backoff, <=10s/remaining request deadlines, bounded Retry-After and no invented percent. Terminal review/failed/withdrawn/unmanaged states stop. Only transient network/retryable429/503 retries; available source remains visible during transient polling failure. Descriptor-only202 never enables Print; nonempty ordered document blocks count as readable even with no body/steps.

On explicit article open from a permitted index, POST exact-scope `/articles/{canonical_article_id}/prepare` with `{}`, CSRF and same-origin cookie BEFORE observational detail polling; repeat only on explicit retry/new open using existing durable server idempotency. Warm prepare returns existing current content and must not create new work. Consume the returned current article immediately, then GET poll when processing is active; media renewal and source loading NEVER POST prepare. Only actual durable processing metadata can show Preparing. GET no-job/no-content503 alone is not queued proof. Paid GET list/detail/source/image cannot be used as an alternate scheduler.

Both origins use one ordered renderer. Detached fragments replace document content atomically only when content origin/view_revision changes, preserving selected article/configuration, focus, scroll/anchor and source panel. Same view revision updates processing copy/media URLs without replacing unchanged text. Preserve block order/headings/warnings/numeric values/tools/tables/table-cell images/list items/unknown/unavailable blocks, canonical action then following instructions, optional nested step images and explicit numbers without inventing source numbers. Use textContent/createElement, no upstream HTML sink; zero/false table cells use nullish handling. Do not use storage_key as browser asset identity. Retain compatibility body/steps for explicit legacy fixtures, but production authority is the managed exact-scope server projection.

Stored source loads the pinned same-origin JSON source-review DTO and renders its normalized document/images through the same ordered renderer beside the article. Keep source metadata/provenance and evidence/source-locator anchors; verify exact requested source_revision_id as well as route identity. Existing raw-srcdoc approach is replaced: opaque sandboxed srcdoc can interfere with cookie-authenticated image requests and does not need to remain the customer rendering mechanism. No untrusted innerHTML/srcdoc, no allow-scripts or external image fetch. A direct View stored source link may open only the server's same-origin protected source route with noopener/noreferrer; server sanitization/CSP remain independently enforced. A DTO lacking a usable document shows unavailable (or textContent for explicitly declared plain JSON), never trusts arbitrary source HTML. Old-selection/pinned-revision responses cannot replace the current source panel.

v2 images accept only same-origin `/v1/catalog/images/v2.<opaque>` from authorized DTOs, no data/provider/arbitrary same-origin URL in production renderer. One coalesced automatic detail/source renewal budget per selected view_revision after an image error; simultaneous top-level/nested/table/source-panel failures share that budget/controller. An unchanged revision reconciles only URL values matched by stable asset ID in the selected revision, preserves content DOM/focus/scroll and retries each replacement once. If source/canonical context changed, use the normal guarded atomic view transition, reset budget only for the genuinely new view revision. Repeated failure consumes budget and shows Illustration unavailable plus manual refresh; no image error loop. Pinned historical source refreshes that exact source DTO rather than substituting current images. Renewal is GET-only, no source/model/ensure work. Image onerror gives no HTTP status: bounded authorized refresh distinguishes401/403/410 and clears/stops; do not infer ownership from a broken image alone.

One navigation generation/auth epoch owns all selector, quote, library, checkout-status, prepare, detail, source and media callbacks. Abort controllers, request deadlines and identity checks guard every await/onUpdate/finally/timer/image listener. Vehicle/article/history/back/cancel/logout/account denial invalidate the relevant work; stale A after B never writes content/status/button state. Cancellation stops browser work, not a claim of canceling committed payment/shared durable jobs. Preserve public selection on login/payment/source retry where safe. No protected localStorage, IndexedDB, Cache API, service worker/offline cache or persistent DOM snapshots. Clear protected DOM/source/images/object URLs and pending operations synchronously on logout/denial/pagehide; pageshow (including bfcache) rechecks session and exact scope before restoring content, so Back cannot reveal cached paid data after logout. CSRF is memory-only and refreshed via session, never leaked to hosted Checkout.

## Accessibility and honest progress

Use existing labels/native controls/headings/skip link/local font, visible focus, logical tab order and mobile/print styles. Selected quote/terms/total/sign-in/purchase controls are reachable by keyboard. Restore focus after user navigation/login cancellation; background polling/renewal must not steal focus or repeatedly announce progress. One polite completion/status region and one critical error region, fixed transition copy; no per-poll announcement spam. Terms errors link to the actual checkbox; don't make links inside terms labels unintentionally toggle agreement. Native progress only for actual measurable server work; omit value for indeterminate loading. Keep the six ordered flow stages, but remove attempt-derived completion percentages; no fake payment/model percent or claim source normalization is canonical completion. Respect reduced motion; keep default native indeterminate appearance unless fully implementing tested vendor-specific progress styling. Print is enabled for readable permitted source/canonical content only and excludes account/purchase/navigation controls. Browser fixtures also verify320px layout,200% zoom, contrast/focus and print behavior.

Modern Web Guidance consulted first. Root-supplied autofill-sign-in-form guidance says "Use <button> for buttons"; Google-only sign-in needs no fabricated password form. Retrieved accessibility guidance: "Don't use live regions for interstitial states"; progress guidance: "Omit value for an indeterminate state" and "Announce completion without stealing focus". These drive the planned native controls/status/progress behavior. Sources retained in `/tmp/autodata-workshop-auth-guidance.md` and `/tmp/autodata-workshop-customer-ui-guidance.md`; no UI code was changed.

## Bundle, packaging and exact files

Use build-only package directory apps/api-go/workshop-client/ outside the embedded workshop tree. package.json pins firebase12.19.0 and esbuild0.28.2 exactly, Node>=20; package-lock.json freezes transitives/integrities. esbuild registry integrity `sha512-HKVLS8dvII+xoKW9kmqxbRKrnWEXfJJr/FZhhJmiqIB0e053QNYFqOBouTMO/k5sID4MvCiUCvv8b9M4h32wIA==`. `npm ci --ignore-scripts` then the build script uses the installed platform esbuild optional package (no downloaded postinstall executable). Bundle only official firebase/app and firebase/auth wrapper, ESM/browser/ES2022, minified, no source maps/analytics/remote module imports, legalComments external. Commit firebase-web.mjs + .LEGAL.txt + provenance JSON with SDK/transitive/tool versions, source/lock/license/bundle SHA256 and sizes. --check rebuilds into an external temp directory and compares exact bytes/metadata; no working-tree rewrite. Existing //go:embed workshop/* and production Docker COPY workshop already package these assets recursively, so production Dockerfile needs no Node and no change. Verify actual rebuilt Go image serves the committed bundle/license and no secret/source map/node_modules. Current source modules remain native, no bundling/framework conversion.

Public purchase-config.json is owner/deployment configuration: enabled false until real terms/privacy/refund/contact HTTPS URLs, matching terms_version and published tax notice are supplied/approved. Initial unavailable values are null and cannot enable Buy; do not fabricate legal identities/policies/URLs. Validate configured links (HTTPS, no credentials/javascript) from trusted deployed config only, never query parameters. Fixture config uses clearly synthetic local policy pages and is never shipped as enabled merchant content. Same quote stays server-authoritative. Coordinator/hosting owner must supply these real values before live acceptance; UI code does not create policy text.

Create these13 paths:

```text
apps/api-go/workshop/auth.mjs
apps/api-go/workshop/commerce.mjs
apps/api-go/workshop/article-read.mjs
apps/api-go/workshop/purchase-config.json
apps/api-go/workshop_browser_fixture_test.go
scripts/dev/workshop_browser_smoke.py
scripts/dev/test_workshop_browser_smoke.py
scripts/dev/requirements-workshop-browser.txt
scripts/dev/fixtures/workshop_customer/scenarios.json
scripts/dev/fixtures/workshop_customer/firebase_transport.js
scripts/dev/fixtures/workshop_customer/stripe_checkout.html
scripts/dev/fixtures/workshop_customer/hostile_source.json
workers/ingestion-python/tests/test_workshop_browser_integration.py
```

The manifest now contains13 creates +20 existing paths =33 paths. The ten Firebase packaging paths are already delivered; consume them and preserve their verified bytes unless an actual integration change requires rebuilding and verification.

Use or modify these20 existing paths (including .gitignore):

```text
apps/api-go/workshop/index.html
apps/api-go/workshop/app.mjs
apps/api-go/workshop/catalog.mjs
apps/api-go/workshop/progress.mjs
apps/api-go/workshop/styles.css
apps/api-go/workshop-client.test.mjs
apps/api-go/workshop_test.go
infra/compose/article-lifecycle-test.Dockerfile
.github/workflows/autonomous-verification.yml
.gitignore
docs/architecture/workshop-interface.md
docs/architecture/workshop-loading-progress.md
apps/api-go/workshop/firebase-web.mjs
apps/api-go/workshop/firebase-web.mjs.LEGAL.txt
apps/api-go/workshop/firebase-web.provenance.json
apps/api-go/workshop-client/package.json
apps/api-go/workshop-client/package-lock.json
apps/api-go/workshop-client/build.mjs
apps/api-go/workshop-client/firebase-entry.mjs
docs/verification/workshop-customer-ui-runbook.md
```

Ignore only workshop-client/node_modules (not generated tracked artifacts); package/install never writes node_modules inside the embedded assets. auth.mjs owns official SDK/session lifecycle, commerce.mjs quote/checkout/order/library, article-read.mjs bounded reader coordinator, existing app.mjs navigation/rendering. Browser transport fixtures are test inputs, never app runtime switches. No main.go/OpenAPI/auth/payment/catalog/SQL/Compose service changes, production Dockerfile or autonomy/supervisor edit. Coordinator canonical plan/spec/task/tracking amendments are separate checkpoint work.

Optional browser-runtime target in the SAME existing article-lifecycle-test.Dockerfile shares its unchanged named lifecycle-runtime base, Go1.26/Python/PG tools and candidate module cache. Copy requirements-workshop-browser.txt (playwright==1.64.1, public PyPI metadata Python>=3.10 verified) and install package + Chromium/Firefox/WebKit OS/runtime dependencies at build time. End with an unchanged final/default lifecycle-runtime target so ordinary R3 builds don't acquire browser dependencies. Explicit owned buildx `--target browser-runtime` produces the UI fixture image tag; use existing go-test-runner service with AUTODATA_R3_TEST_IMAGE/CANDIDATE_SHA, run --pull never --no-deps, readonly source, executable/tmp, same internal fixture network. No new image lineage/service/host port or runtime package installation; the browser target is a cached extension of the actual R3 toolchain. Record actual pinned browser revisions/OS support after successful image build, no pretense metadata proves engines install. Coordinator independently reviews the supervisor's extended timeout/inventory/image target before execution. Keep production package image proof separate from this browser fixture image.

## Deterministic browser and API acceptance

CLI `python scripts/dev/workshop_browser_smoke.py --base-url <fixture-origin> --mode dto-fixture|api-fixture --browser chromium|firefox|webkit|all --candidate-sha <40hex> --output <private-directory>`. Required mode fails on missing dependencies/engine, zero or skipped inventory, unexpected external request, timeout or provenance mismatch. No arbitrary live URL by default: accept only explicit loopback fixture origins; no inherited secrets/provider credentials. API fixture uses real Go httptest TLS with test-only certificate acceptance for its exact origin so Secure __Host cookies are actually tested, not downgraded to insecure fixtures. The actual Go asset server is always used.

DTO-fixture mode is clearly browser/DTO/error-race evidence: intercept exact app endpoints with versioned synthetic DTOs and record route ordering; never describe it as server access/settlement proof. Preserve the earlier eighteen named scenarios:

```text
bankone-cascade, banktwo-cascade, dual-bank-coverage, one-bank-unavailable,
pending-no-content, source-to-canonical, source-rewrite-failure, review-required,
warm-reload, selection-change-in-flight, source-review-change-in-flight,
cancel-and-retry, history-restore, document-only, missing-media, withdrawal,
keyboard-print-mobile, source-media-isolation
```

Add these22 names, yielding exactly40 scenarios per engine (120 for all):

```text
auth-cookie-reload, google-popup-exchange, google-popup-blocked,
google-popup-cancelled, google-stale-reauthentication, firebase-memory-persistence,
signin-unavailable-local, signin-malformed-config, session-expired, session-blocked,
auth-dependency-unavailable, quote-exact-scope, terms-config-unavailable,
checkout-double-click-retry, checkout-processing-return, checkout-untrusted-return,
checkout-expired, already-owned-no-pay, library-pagination-and-states,
paid-prepare-before-poll, media-renew-coalesced, logout-and-bfcache-clear
```

Use real browser contexts, actual app assets and actual pinned SDK in SDK-storage/transport scenarios. External Firebase/Google fixture handles SDK project configuration, Google iframe/popup auth-event transport, accounts:signInWithIdp and accounts:lookup with synthetic local signed tokens; it never replaces SDK signInWithPopup, the app auth adapter or production code functions. Pin its protocol to the inspected @firebase/auth1.13.6 distribution and test against the bundled SDK. Popup-blocked UI fault may narrowly simulate browser window.open refusal in DTO mode, explicitly marked as a platform-fault fixture, not real successful Google transport evidence. Assert awaited NONE/inMemory persistence before popup; inspect same-origin local/session storage and IndexedDB after successful login, failed exchange, reauth and reload: no Firebase user/access/refresh/ID-token payloads, no app bearer. Non-secret checkout metadata is the only allowed app sessionStorage. Cookie-only reload performs no Firebase token recovery/refresh. Unexpected provider/source/model/CDN connection fails rather than reaching network.

api-fixture mode uses real039 sessions/SDK verification,040 order/reconciler/grants/private HTTP, paid catalog guard/prepare and fixture PG/S3/workers. Only external Firebase/Google and Stripe network responses are deterministic test transports; do not intercept app auth/session/quote/checkout/status/library/prepare/source/media/grant responses or replace backend authorization. Reuse integrated039 local certificate/user fixtures and040 official-client transport helpers after actual-symbol reinspection. Browser's official SDK exchanges a fixture-signed Google token through actual `/auth/firebase/session`; never inject an authenticated cookie or role via browser JavaScript. Stripe hosted fixture executes a local signed test event through actual public webhook/private verifier/reconciler; server ledger and grant prove payment. Provider URLs/keys are synthetic and cannot contact a merchant/project. Source/model endpoints are the existing local R3 fixture workers, not browser mocks.

New pytest module freezes four roots: test_browser_google_exchange_checkout_library_real_api (three engines, no provider parameter); test_browser_owned_source_canonical_and_media_real_api; test_browser_account_scope_and_revocation_real_api; test_browser_signed_refund_blocks_old_links_real_api (each three engines × both banks), exactly21 integrated cases. Each creates an isolated fixture DB through the real040 shared runner and exact configuration canonical identities using paid-access fixture helpers, never reparents immutable vehicle-only R3 identities. New Go TestWorkshopBrowserFixtureHTTP runs real production-mode Handler with explicit injected fixture dependencies and embedded UI, publishing only owned loopback TLS/control endpoints under a guarded required-test flag. No production test/debug route or request-selected fallback. Run server subprocess/worker fixtures serially per case, only one active global SDK transport modification, bounded teardown.

Integrated assertions: Google exchange creates real hashed PG session and cookie; one double-click/retried checkout owns one order/session; Stripe return alone leaves pending with zero grants until signed settlement; permanent owner library survives reload/server restart and no re-payment; both-bank exact-config content/source first, one canonical transition and warm reuse; actual S3 v2 image with current session/grant; adjacent/other owner/direct legacy denied before work; logout/Firebase disable/full signed refund revoke next protected read, including old image URLs and bfcache. Missing source preserves paid ownership and readable permitted source; no fake percentage/completion. Honor source/canonical ordering, nested images, table0 values, hostile HTML/CSS/SVG/URLs, no script or external request. Browser-side badge/copy is never the financial/access assertion.

Every case records candidate/input/SDK bundle hashes, browser/version/revision, fixture kind, scenario/test/provider, safe route-template request order/counters, explicit assertions/exit/timeout and screenshot on failure; no raw ID/session/provider tokens, signed image paths or customer secrets in logs. Fixture-only screenshots contain synthetic content. Retain R3 clean plain-clone/host-before runner-before-after host-after/input-manifest/image provenance and resource ownership. DTO scenarios <=20s each; integrated cases <=90s each including fixture/cleanup; suite hard4500s with final60s reserved, all child phases capped to remaining budgets. Kill/reap owned subprocess groups, stop HTTP/workers and remove owned PG/buckets/artifacts on timeout; outer reviewed supervisor bounds containers/network/image ownership. Missing engine or unavailable service is failed/unavailable evidence, never a pass/skip. Runtime assertions use barriers, fake browser clocks only for polling unit cases and actual event/counter changes, not sleep guesses.

## Verification, delivery and remaining launch prerequisites

- [ ] After verified backend integration, independently review33 paths, pin literal DTO/error/CSRF/prepare/media contracts and exact source fixtures, synchronize canonical task/specs/Issue186/Project8 and run exact-base preflight.
- [ ] Add failing pure/coordinator tests for session states, quote exact scope, checkout stable key/order returns/library,120s reader/payment budgets/Retry-After, one outstanding request, source document readability, generation cancellation, stable DOM/media reconciliation, deny clearing and true progress. Implement native modules/controls until passing, retaining earlier helper behavior where still valid.
- [ ] Build official SDK with `npm --prefix apps/api-go/workshop-client ci --ignore-scripts`; `node apps/api-go/workshop-client/build.mjs --check`; `node --test apps/api-go/workshop-client.test.mjs`. Go TestWorkshop verifies all native/generated assets, provenance/license and no missing/remote scripts. Existing tests that intentionally relied on bearer or data/arbitrary image URLs are replaced by explicit compatibility fixtures plus stricter production tests, not weakened to stop testing.
- [ ] Run `python -m unittest discover -s scripts/dev -p 'test_workshop_browser_smoke.py' -v`, Go test/vet and contracts, then exact120 DTO +21 integrated cases under owned fixture tooling. CI change adds Node22 build freshness/helper tests and bounded DTO-browser job with pinned Playwright/three engines; real PG/browser acceptance stays the independently supervised fixture run, not a fabricated green ordinary test skip. Required21-case pytest command: `python -m pytest -q -p no:cacheprovider --junitxml=/artifacts/workshop-browser-api.xml workers/ingestion-python/tests/test_workshop_browser_integration.py` with AUTODATA_LIFECYCLE_TEST=1 and AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION=1; propagate exact candidate/R3 fixture flags and clear ambient cloud/payment/DSN values.
- [ ] Build the actual production Go image at candidate and verify public embedded assets/SDK version/license plus no source maps/node_modules/secrets; rerun required8 R3 +5 identity +14 commerce +12 paid-access inventories separately. Independent exact-SHA customer/source/media/security review, coherent validated commits/pushes on owned branch; no hidden fallback/profile change.
- [ ] Staging/release owner supplies actual merchant terms/contact/tax configuration, public Firebase project/app/Google authorized domain and real test-mode Stripe hosting/webhook config. On exact HTTPS cars.tk/staging deployment separately demonstrate actual Google popup/account lifecycle, SameSite/Secure cookies across hosted checkout return, settled grant/library across replicas/restart, permanent access and refund/takedown/media denial, browser privacy/CSP behavior and real supported-bank access. Deterministic fixtures do not certify domain registration, Google's live popup/third-party restrictions, Stripe onboarding, merchant legality or production readiness. No live charge/cloud/deploy action is authorized by this UI plan.


## Canonical incorporation and review

Independently approved source draft
`0b9602094f3966eb04da7eb1b08299f4f52afa66b55adbe398cf4bf3f3d34afc`.
Review `/tmp/autodata-workshop-customer-ui-independent-review.md`, SHA256
`7d215f64517d7c5c6b162532fc0b3fcd1fafec5bedd3b40ee3129e1749f399b9`.
This conditional33-path plan replaces the former auth-only R4 dispatch while
preserving its original18 browser scenarios. No implementation is authorized
until the three backend dependencies are verified and a fresh gate passes.

The final literal contract check must preserve the canonical quote field
`purchase_terms_version` versus checkout body `terms_version`. Existing source
JSON pins revision identity in `source.url`; validate its exact route/revision
and selected article without inventing a top-level field or modifying the API.
Real backend integration can refine these named contracts only before dispatch.


### Parallel SDK packaging dependency

The independently reviewed `2026-11-03-workshop-firebase-bundle.md` extracts
ten existing scope paths as a pure packaging milestone, parallel with commerce
after verified R5. It does not initialize Firebase or change the customer flow.
The final UI consumes its verified assets and still owns all customer behavior
and browser/production-image acceptance. Reconcile the create/modify inventory
against those existing files before final UI dispatch; the33-path envelope and
120+21 browser requirements remain unchanged.


### Early-refund library DTO clarification

The final commerce library includes revoked order tombstones even if the full
refund preceded any grant. `granted_at` is nullable only for that revoked,
never-granted case; display refunded/revoked honestly without inventing a purchase
activation time. Every granted item retains its actual grant timestamp.


## Parallel implementation todo

- [ ] Pass this synchronized exact-base preflight, then implement the thirty-two exclusively assigned UI paths under the parallel delivery plan.
- [ ] Coordinate only committed backend interfaces; keep all141 browser cases and separate backend/image/CI acceptance before release.


## Bounded real-API fixture status amendment — 2026-11-03

The authoritative paid-media contract returns404 when an authenticated account presents another account's contextual image capability, before grant/object reading. Same-owner missing/revoked grant remains403; logged-out/expired/disabled authentication remains401. Source inspection at fa30a2204dc8a5c0907d090ec4f41fdd8bec9b4b found the real-API browser fixture incorrectly expects403 for that wrong-account image at scripts/dev/workshop_browser_smoke.py:527, affecting six account-scope cases. Correct only that fixture expectation and its focused unit regression under [the two-file plan](2026-11-03-workshop-browser-account-media-status.md), task/record workshop-browser-account-media-status. Exact21 parametrization,120DTO inventory, actual backend transports and frozen runtime runner remain unchanged. This is a planning gate, not observed21 success. Synchronize Issue186/Project8, commit and pass pinned preflight, then obtain coordinator review before implementation; auth repair/paid12/actual21 acceptance are separately required.


## Synchronized auth provider readiness follow-up (2026-11-03)

Goal: Ensure Workshop sign-in readiness always includes an initialized Google provider after overlapping logout SDK preparation and session bootstrap, and recover consistently from synchronous popup invocation errors and asynchronous popup rejections.

[2026-11-03-workshop-auth-provider-readiness](2026-11-03-workshop-auth-provider-readiness.md) defines a two-file follow-up limited to `apps/api-go/workshop/auth.mjs` and `apps/api-go/workshop-client.test.mjs`. The deferred real-createSession reproduction confirms ready can be true while its Google provider is absent after an epoch change. It does not prove the cause of the WebKit Banktwo account-scope failure at exact `87f4d8b44d9ecccd3f0ead1d4f31a4a5f136f6cf`; preserve the failed full21 receipt (20 pass,1 fail), screenshot and raw provenance unchanged. Synchronous popup validation and asynchronous rejection require separate regressions. Existing-auth preparation must retry a missing provider before persistence; initial and retry constructor failures must stay contained with ready false and safe feedback until a later successful retry. Add a deterministic constructor-failure/retry regression. Preserve exact API21/DTO120 inventories and acceptance graph, deadlines, frozen infrastructure and SDK bytes. Sanitized browser diagnostics require a separate gate.

Issue https://github.com/lucronn/autodata/issues/186 ; Project https://github.com/users/lucronn/projects/8 . Task `docs/agents/tasks/2026-11-03-production-release/workshop-auth-provider-readiness.json` and record `docs/agents/records/2026-11-03-workshop-auth-provider-readiness.json` are `status: synchronized` at `2026-11-03T22:22:29.570981+00:00`. Coordinator saved/read back [Issue186 comment6616892250](https://github.com/lucronn/autodata/issues/186#issuecomment-6616892250) and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` with the identical goal, six todos, scope and evidence limits. Commit/push this planning checkpoint and run its exact-SHA preflight; coordinator integration, re-pinning and independent gate review remain required before code dispatch.

Concrete todo (identical to plan/task/record):

1. Synchronize the goal, exact two-file scope, evidence limits, dedicated plan, canonical customer UI plan, queue, task and record in Issue186/Project8; commit and push the planning checkpoint and pass exact-SHA preflight before implementation.
2. Add a failing deterministic Node regression for cookie-only logout preparation overlapping epoch-changing bootstrap, asserting every ready state has a constructed provider and the next explicit sign-in receives that provider and completes cookie exchange.
3. Add failing regressions for synchronous popup invocation throw and asynchronous popup rejection, requiring the same safe message, SDK sign-out cleanup, restored readiness, and no escaped rejection; retain immediate popup invocation within the user gesture.
4. Construct provider before the persistence await and move popup invocation inside the existing async try without an intervening await; retain epoch guards, memory-only persistence, fresh token checks, session exchange and cookie-session authority.
5. Run the focused red/green Node cases, full Workshop Node tests, applicable Go tests and diff/scope/provenance checks; commit and promptly push the coherent fix, then obtain independent exact-commit review.
6. Coordinator integrates the reviewed fix and collects fresh immutable-candidate API21/DTO120 evidence using the frozen infrastructure; selected-case repeats remain diagnostic only and the original failed receipt remains retained.


## Exact-candidate API21 acceptance checkpoint — pending tracking

Canonical plan: `docs/superpowers/plans/2026-11-04-workshop-api21-acceptance.md`; task: `docs/agents/tasks/2026-11-03-production-release/workshop-api21-acceptance.json`; pending record: `docs/agents/records/2026-11-04-workshop-api21-acceptance.json`; frozen input manifest: `docs/agents/records/2026-11-04-workshop-api21-inputs.json`.

Goal: Collect and independently assess exactly 21 real-API browser cases at immutable PR #198 head e5fed171bb36fdb759c592cbcd0e15aea5490c97 without changing implementation or claiming final release acceptance.

This docs-only checkpoint starts from PR198 head `e5fed171bb36fdb759c592cbcd0e15aea5490c97` and adopts independently approved draft `0b88f7cacdd073984f5cad809f72be9c818d5de2d22b29afba3850c8a08db1d9` / input manifest `ee87deb865c06a84df92c1a8b0481f5ebc35cfdbd051bf32d9e1bf264ec67f13`. State is **pending_tracking**. paid_evidence_plan is the sole Issue186/Project8 writer. No synchronized readback, passing machine preflight, committed-checkpoint review, fixture repair or runtime dispatch is authorized by this record. Existing historical synchronization and delivery entries retain their original scope.

Future lane uses approved external v2 supervisor `/tmp/autodata-workshop-browser-supervisor-v2.py`, SHA256 `a06bea8c6aa7b1fabdb29f3c2b8eba426d9004f2690e9c11ebc56dcb7b8f9c71`, immutable image `sha256:26aea6a9df1a7139e20a6893d9b63a11ab6b9978d113c718c6a792616be5a888` and unchanged six build inputs. It preserves exactly3+6+6+6 cases across Chromium/Firefox/WebKit, uses separate fresh pilot/full roots, and caps full execution at3300s with180s finalization reserve. Current image/engines/capacity are unverified. Pinned successful historical probe `5dd7060edb13f215107e8125f164cbc57c92152f8c39302f7db9b18eb914b02e` at source9ae2809 used different resource settings and proves no current acceptance; the original failed image-probe receipt remains failed. Bankone/Banktwo and model upstreams, plus Google/Firebase/Stripe transports, are synthetic local fixtures; production adapters, actual Go/Python code, PG and S3 execute.

Coordinator-reported read-only resource scout on 2026-11-04 observed approximately 2.36 GiB free on /tmp tmpfs and 17.24 GiB free under /home/corp/autodata-evidence; the source/pilot/full sibling roots below were absent and non-symlink at that observation. The reviewed wrapper permits those sibling roots. Use `/home/corp/autodata-evidence/api21-e5fed17-source`, `/home/corp/autodata-evidence/api21-e5fed17-pilot-20261104` and `/home/corp/autodata-evidence/api21-e5fed17-full-20261104` for the exact source/pilot/full commands. Free space is transient availability evidence, not a reserved quota, full host-capacity proof, a launch authorization or an API21 acceptance result; coordinator must recheck ownership, absence/non-symlink paths and disk headroom immediately before any separately authorized launch. No wrapper bytes, frozen manifest, image/input hashes, case inventory, deadlines or resource limits change.

Prospective fixture repair requires a separately narrowed synchronized gate; this task has zero implementation paths. API21 alone establishes no full180-case/support/CI/review result, R6 profile promotion or live staging/product/deployment/cutover authority. Pilot/support evidence adds zero logical cases.

Concrete todo (identical to dedicated plan/task/record):

- [ ] Sole tracking writer paid_evidence_plan synchronizes this exact goal, six todos, docs-only scope, candidate and runtime limits in Issue186/Project8 with readback hashes, preserving historical indexes; coordinator commits the synchronized successor checkpoint, pins its full SHA, passes exact-base preflight and obtains independent checkpoint review before dispatch.
- [ ] Coordinator verifies a clean exact-e5fed17 source clone, approved v2 supervisor a06bea8 and inherited base, immutable runtime image and six inputs, retained successful historical probe, actual service image identities and available serial host capacity; missing preconditions remain blocked.
- [ ] After separate coordinator runtime authorization, execute one Chromium checkout/library pilot in a fresh private owned root; retain all raw outcomes, provenance and cleanup, and count zero acceptance cases from the pilot.
- [ ] If pilot passes raw verification, execute the unchanged complete 3+6+6+6 API inventory once in a different fresh root at the same immutable SHA using the approved v2 supervisor, 3300-second total and 180-second finalization reserve; no retries, skips, missing engines or combined partial runs.
- [ ] Independently review exact candidate, 21 unique JUnit/receipt identities, assertion inventories, actual HTTP/PG/S3 and warm/restart facts, input/asset/SDK/TLS/browser/image provenance, private artifact hashes and owned cleanup; retain failures and require a separately narrowed synchronized gate for any fixture repair.
- [ ] Keep final-candidate 5+8+14+12+120+21=180 logical cases, supporting scans/images/SDK/license/CI/reviewer authority and all live staging/release gates separate; support and pilot evidence add zero cases and no release profile or authority flag is promoted.
