# Workshop interface

The consumer interface lives at `/workshop/` beside the administrative dashboard and Swagger. It is a plain HTML, CSS, and JavaScript client of the provider-neutral catalog API. It owns no ingestion or procedure rewriting.

The user selects year, make, model, and engine/trim, then searches the returned article index and opens an article. The browser uses returned identifiers and preserves procedure order and image associations. Catalog hydration is represented as a bounded waiting state; failed and empty reads offer recovery. Changing a parent selection invalidates dependent choices and outstanding reads.

The visual direction combines native selects, underlined article links, thin structural rules, locally served Instrument Sans, and a restrained mechanical masthead. The reader supports back navigation, reloadable article links, printing, keyboard use, reduced motion, and mobile screens. Stored body text is the fallback when a legacy record lacks usable structured steps; missing images are not invented.

Tracking: https://github.com/lucronn/autodata/issues/113 in https://github.com/users/lucronn/projects/8.
Plan: `docs/superpowers/plans/2026-09-25-workshop-interface.md`.

Todo: standalone layout/route; cancellable catalog and article workflow; focused regression tests and live browser verification.


The approved customer identity API is Firebase Google sign-in, followed by an
opaque application session. A separately implemented Workshop login reads
GET /auth/config, uses its public Firebase web configuration for a Google popup,
POSTs a fresh id_token to /auth/firebase/session with the exact Origin and
X-Autodata-Session-Exchange:1, then reads GET /auth/session. Successful exchange
returns204 and sets a Secure HttpOnly SameSite=Lax host cookie; no token is placed
in application local storage. Session state provides expiry, dataset_viewer role
and a session-bound CSRF token. Mutations, including /auth/logout, send
X-CSRF-Token with the exact Origin. Logout commits revocation before expiring the
cookie. There is no application OIDC callback/PKCE transaction.

Explicit local mode reports login_available:false and no providers. The browser
must show sign-in unavailable without a demo customer. This backend lane does
not implement that UI, checkout, grants, library, or paid catalog enforcement.
Google project registration, authorized domain cars.tk, runtime IAM and actual
staging sign-in remain deployment prerequisites. The canonical implementation
plan is docs/superpowers/plans/2026-11-03-workshop-firebase-identity.md.
