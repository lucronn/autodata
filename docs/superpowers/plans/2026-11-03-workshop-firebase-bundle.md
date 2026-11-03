# Pinned Firebase browser SDK packaging

Issue: https://github.com/lucronn/autodata/issues/186

Project: https://github.com/users/lucronn/projects/8

Status: independently reviewed and tracking synchronized; no implementation until committed
checkpoint and exact-base preflight. This is an independent packaging milestone
inside the reviewed unified customer UI plan, not a separate customer flow.
Execution profile: gpt-6.1-sol, medium reasoning, Fast/priority, no fallback.

## Goal and dependency

Prepare the self-hosted official Firebase app/auth ESM bundle, deterministic
build inputs, license/provenance and actual embedded-asset checks. It can run
in parallel with commerce after verified R5 integration because it consumes no
checkout, entitlement, prepare or media interface. The final unified UI remains
a later gate and alone integrates customer behavior and browser acceptance.
Basis: root472492dd868122b2b0da00dc84e15c5424aa0276 and independently reviewed
`2026-11-03-workshop-customer-ui.md` (source draft0b960209,33-path scope).

## Fixed implementation contract

Use exactly firebase12.19.0 and esbuild0.28.2, Node >=20 (available22.23.1).
The reviewed public registry archive integrity values and app/auth versions in
the unified UI plan are authoritative; compare them with the generated lock.
Commit the complete npm lock with transitive integrity. Run npm ci --ignore-scripts;
esbuild uses its installed platform optional package, with no postinstall download.
No Node process/dependency is added to the production Go image.

Build-only directory `apps/api-go/workshop-client/` is outside embedded assets.
Its firebase-entry.mjs re-exports initializeApp from firebase/app and exactly
initializeAuth, inMemoryPersistence, setPersistence, GoogleAuthProvider,
browserPopupRedirectResolver, signInWithPopup, reauthenticateWithPopup,
getIdTokenResult and signOut from firebase/auth. It does not initialize an app,
choose persistence, fetch a token or contact a provider. No getAuth, persistent
storage, emulator, analytics, remote module import or application credentials.
Actual in-memory initialization, popup/storage behavior and cookie exchange are
the later auth.mjs/browser lane; packaging alone does not certify them.

Build with esbuild ESM/browser/ES2022, minified and legalComments external,
without source maps. Commit firebase-web.mjs, firebase-web.mjs.LEGAL.txt and
firebase-web.provenance.json. Provenance has fixed schema/version, pinned SDK,
resolved included app/auth/dependency versions, build tool version/options,
canonical repository-relative source/lock/build hashes, license and bundle hashes
and sizes. Exclude timestamps, hostnames, absolute paths and ambient environment
values. Include only reproducible build inputs; no circular self-hash.
Metafile must have no external import or source-map output; SDK endpoint string
constants are not remote module imports. Preserve all dependency license notices.

The build script defaults to deterministic generation of these three assets.
--check rebuilds in a fresh external temporary directory and byte-compares all
three against committed artifacts, exits nonzero for stale/missing/altered
inputs or outputs, cleans only its owned temporary directory, and never rewrites
the checkout. Require clean install and supported toolchain; missing platform
esbuild is a failed check, not an alternate downloading build. Hash input paths
canonically and keep output basenames stable across scratch paths.

Ignore only `/apps/api-go/workshop-client/node_modules/`; generated assets remain
tracked. Extend the existing actual Go HTTP Workshop asset test to serve all
three files without authentication, verify MIME/nonempty contents, inspect the
provenance contract and compare actual served SDK/license hashes and sizes.
Existing assets/source markers/redirect checks stay intact. Keep all current
HTML/app/auth behavior unchanged: no new module is loaded until final UI wiring.
No main.go, Dockerfile, CI workflow, auth, commerce, catalog, SQL or fixture changes.

## Exactly ten allowed paths

```text
apps/api-go/workshop-client/package.json
apps/api-go/workshop-client/package-lock.json
apps/api-go/workshop-client/build.mjs
apps/api-go/workshop-client/firebase-entry.mjs
apps/api-go/workshop/firebase-web.mjs
apps/api-go/workshop/firebase-web.mjs.LEGAL.txt
apps/api-go/workshop/firebase-web.provenance.json
apps/api-go/workshop_test.go
.gitignore
docs/verification/workshop-customer-ui-runbook.md
```

These are ten paths already within the final UI33-path envelope. That later task
will consume verified packaging and may update it only within its own gate.
Its create/modify manifest must be reconciled to actual files before dispatch.
The runbook records this limited milestone and explicitly leaves120 DTO/browser,
21 integrated API/browser and live HTTPS acceptance pending. No fixture or live
browser proof is claimed from source scans or the bundle's existence.

## Concrete todo and verification

- [ ] Independently review this bounded split, synchronize Issue186/Project8,
  canonical UI/task/queue and this record, commit and pass exact-base preflight.
- [ ] Add failing actual Go asset/hash checks, then generate pinned build inputs,
  complete lock, official bundle, preserved license and deterministic provenance.
- [ ] Run clean npm ci --ignore-scripts, generation then --check and a second
  fresh check with identical bytes. Prove modified bundle/license/provenance or
  a source/lock change is rejected in owned scratch copies, not by editing the
  authoritative checkout. Verify clean --check leaves tracked input bytes intact.
- [ ] Verify actual emitted ESM named exports and zero external imports without
  initializing Firebase or making provider calls; actual Go HTTP asset/hash
  tests and existing Workshop tests pass. Run Go ./... and diff --check.
- [ ] Independently review exact candidate, push coherent validated milestones,
  integrate with byte/provenance comparison and record actual CI. Final UI still
  requires all backend dependencies, real browser scenarios and fresh gate.

No credentials, cloud project choice, payment or live Google action is needed.
No production readiness, login functionality or browser-storage behavior is
claimed by this asset-only milestone. Actual production image asset proof remains
the final UI release check because that includes the complete customer app.

Independent planning approval: `/tmp/autodata-workshop-firebase-bundle-plan-review.md`, SHA256 `e23a76e6de2a345f43360424e4d4a802a9ec4a215a3ea92d1649bd8b3834e383`, reviewed source draft `cc5eec450b4689f035efe5e39ccc14465e4a7ab4f84599f4901b4ff1bc50c4f2`. Verified dependency CI41696273960 passed at472492d; actual Issue186/Project8 updates were saved/read back. Archive/lock/export verification remains required implementation evidence.
