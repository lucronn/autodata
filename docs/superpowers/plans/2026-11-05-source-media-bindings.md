# Dual-bank source media bindings

Goal: preserve each provider's raw article and provenance while placing its declared image resources at the exact image positions in the Workshop source fallback and canonical article. This is tracked by [Issue #331](https://github.com/lucronn/autodata/issues/331) in [Project #8](https://github.com/users/lucronn/projects/8), under parent release [Issue #186](https://github.com/lucronn/autodata/issues/186).

The connector text-resource response may include `asset_bindings`, an optional list of at most 128 objects with exactly `source_url` and `resource_ref` string fields. `source_url` is the exact decoded HTML `img src` value in the returned raw body; `resource_ref` must also appear in `asset_resource_refs`. Each source URL has one binding. The same URL may occur at multiple image positions, which all use the same declared resource. A conflicting or malformed sidecar fails closed; no ordinal or basename inference is allowed. The sidecar is metadata only: raw content, byte hash, source revision, rights, and source provenance remain unchanged.

AutoData validates the bounded sidecar at its authenticated connector boundary, retains it in source metadata, and applies a binding only when a parsed image URL exactly matches. It then uses the existing declared-ref asset fetch and article placement flow. Unbound images remain unavailable placeholders; the reader continues to show source fallback until an accepted canonical rewrite is atomically published. Connector image delivery remains authenticated and tied to the same vehicle/source resource. Banktwo's legacy image route must return binary bytes for image links, with its asset-only refs scoped to an allowlisted same-vehicle thumbnail path and bounded locale/region query. Bankone maps its discovered source image URL to its existing opaque asset ref. Deploy AutoData consumer before either connector producer, then run bounded dual-bank canaries before broader ingestion.

Concrete todo:

- [x] Commit this plan, Project/Issue tracking, canonical document, and synchronized record at a pinned base SHA; run machine preflight.
- [x] Add failing connector-envelope and article-placement tests for valid, repeated, conflicting, unknown, and oversized bindings, including raw body/hash invariance.
- [x] Implement bounded AutoData consumer validation and exact-URL image binding with existing source fallback.
- [ ] Review, test, and merge the AutoData consumer before the Bankone and Banktwo connector PRs.
- [ ] Verify both connector producers' raw-byte invariance, binary image delivery, and authenticated references; merge and deploy in dependency order.
- [ ] Run bounded real Bankone and Banktwo article canaries and confirm ordered images, no duplicate gallery, stable canonical/source hashes, and no unexpected model call.

Acceptance requires exact-position images for declared refs, original content/hash/provenance, deterministic rejection of invalid sidecars, and unchanged source fallback while rewrite is pending. This plan does not authorize a production rollout or claim that historical missing S3 objects are recovered.

## AutoData consumer implementation evidence

The planning checkpoint `5be336ccfbe1bb2323a546eac0169291ecc485dc` passed the
machine preflight before implementation. Consumer implementation and review
fixes are pushed through `0b7cd11d230f16cb7287d0b3940486e77550d8b5` in
[PR #332](https://github.com/lucronn/autodata/pull/332).

Binding, Banktwo facade, ordered-document, and offline replay suites pass with
100 tests, 2 subtests, and 7 database-dependent skips. The broader capture and
connector run passed 184 tests and 9 subtests. Independent review found an
embedded-image overwrite edge case; a failing regression reproduced it and the
fix was re-reviewed with no remaining findings. Parent review also caught C1
controls; both fields now reject them with regression coverage.

Nonempty sidecars enter source identity without changing raw body hashes. A
metadata-only recapture may therefore schedule another rewrite under the current
lifecycle; canonical reuse/backfill is separate work. No merge, deployment, live
provider canary, or historical article recapture has been performed by this
implementation agent. CI and exact test commands are recorded in
`docs/verification/2026-11-05-source-media-bindings.md`.
