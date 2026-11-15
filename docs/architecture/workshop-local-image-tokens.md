# Local Workshop image references

Render server-issued local Workshop opaque image references only in explicit local auth mode, retaining default and Firebase v2-only image URL validation and existing server authorization.

Plan: [decisions](../superpowers/plans/2026-11-15-workshop-local-image-tokens.md).
Issue: https://github.com/lucronn/autodata/issues/438
Project: https://github.com/users/lucronn/projects/8

An explicit local mode may accept only the existing same-origin opaque image route shape. Firebase and unknown modes retain v2-only validation. Token decryption, session checks and private object access remain server responsibilities.

Concrete todo:

- Add an explicit authMode option to localImageURL accepting unprefixed opaque base64url image tokens only for exact local mode; preserve same-origin, exact image path, no-query/hash/credentials, and v2 defaults without enabling broad compatibility.
- Pass current session mode to initial image rendering and media reconciliation; preserve unavailable-image handling and generation checks.
- Add red-first Node regressions and a Go-to-Node actual sealed-token contract test covering local rendering/renewal, default/Firebase rejection, v2 behavior, and malformed/cross-origin URLs; run client/demo and relevant Go media tests.
- Push a coherent validated milestone and PR with exact gate/head/tests; coordinate with root before M2A service/browser work. Do not restart services, call providers/payments/Firebase, merge, or deploy.

Implementation awaits the committed synchronized checkpoint/preflight.
