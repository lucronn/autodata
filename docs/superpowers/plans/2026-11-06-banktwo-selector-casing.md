# Banktwo selector casing repair

**Goal:** Make public Workshop make/model IDs resolve to exact provider labels and persist/query complete configurations so the real vehicle cascade works for Banktwo.

**Issue:** https://github.com/lucronn/autodata/issues/186

**Project:** https://github.com/users/lucronn/projects/8

**Base:** merged catalog repair `27ac83f4b97421db3ef067eee60a12d21b8874d2`; release gate checkpoint `af822832becf4f97e7d2d882801d7ec6b5c3442a`.

The live 2020 Ford model selector returns 29 options but remains incomplete. Direct Banktwo catalog calls return nine models for `Ford` and HTTP 404 for public ID `ford`. Configurations return one row for `Ford` / `Figo (MEXICO)` and 404 for `ford` / `figo (mexico)`. Public slugs can also discard punctuation, so a case-only transformation is insufficient.

Implement a bounded provider-bound lookup from public selector IDs to unique exact source labels. Preserve exact-label fast paths, fail closed on ambiguous or absent matches, and keep provider errors visible as incomplete hydration. Update the Go durable selector/vehicle lookup so normalized public IDs match persisted display labels without broadening year, region, or make scope. Add focused regression tests for the Banktwo 404 case and punctuation. Keep purchase and article authorization unchanged.

## Concrete todo

- [ ] Reproduce the make/model case and punctuation mismatch with both configured source scopes and public IDs; pin the exact implementation base.
- [ ] Add bounded Python source-label resolution for make and model selector calls, with focused exact/slug/ambiguous/error tests.
- [ ] Add Go slug-aware scoped vehicle/configuration lookup with focused mixed-case and punctuation tests.
- [ ] Verify CI and a bounded live Ford / Figo (MEXICO) vehicle cascade, then record the exact release result without changing article or payment access.

## Verification

Run focused Python and Go selector tests, the repository-required PR checks, and a live bounded US 2020 Ford/Figo model/configuration probe. Confirm the existing catalog makes canary and purchase-disabled setting remain intact. Do not claim article readability from selector acceptance.
