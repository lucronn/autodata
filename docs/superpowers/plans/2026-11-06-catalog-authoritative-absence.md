# Authoritative catalog absence implementation plan

> **For agentic workers:** Use the existing synchronized gate and implement this bounded fix with a failing focused test before production code.

**Goal:** Finish a merged Workshop selector scope when one bank proves the requested make or model is absent in a complete parent catalog, while keeping the other bank's rows and authentic source provenance.

**Issue:** https://github.com/lucronn/autodata/issues/186

**Project:** https://github.com/users/lucronn/projects/8

**Base product:** `814a1c26e893fe181327516cfa4b48a800978c43`

**Observed trigger:** US 2027 Ford models return 13 Bankone rows but `complete:false` forever. Banktwo's complete 2027 makes catalog contains 34 rows and no Ford. The Banktwo child 404 is repaired through parent enumeration, then the client reduces proven absence to generic `NOT_FOUND`; the all-provider completion rule counts it as a failure. This is not an authorization or article reader change.

**Files:** `workers/ingestion-python/src/autodata_ingestion/source_connector_client.py`, `workers/ingestion-python/src/autodata_ingestion/catalog_service.py`, their focused tests under `workers/ingestion-python/tests/`, and this task's verification document. No Go/API/schema/UI, payment, rewrite, or article changes.

## Concrete todo

- [ ] Add a failing client test: Banktwo child 404 plus a complete make page lacking the requested make produces a distinct authoritative-absence outcome carrying the validated parent page; incomplete/ambiguous/error pages remain failures.
- [ ] Add a failing provider/service test: Bankone rows plus Banktwo proven absence yield one complete merged selector with both sources' real provenance; no synthetic child envelope is emitted.
- [ ] Implement the smallest typed internal absence outcome with original parent pages, parent/requested scope and selector metadata. Emit it only after complete advancing parent pagination with zero matching labels; preserve the current shared deadline and request accounting.
- [ ] Convert that outcome only at the source catalog provider boundary to `rows:[]`, `complete:true`, `missing_scopes:[]`, and provenance derived from each authentic parent envelope with `coverage_basis:complete_parent_absence`; retain all other failures as incomplete.
- [ ] Verify model and configuration absence, paginated evidence, exact-label repair, ambiguity, malformed cursor, 429/5xx/auth/timeout, and child 404 after a parent match. Run focused/full ingestion tests and required PR CI, then bounded public 2027 Ford canary without altering the article worker or checkout.

## Acceptance

The public US 2027 Ford model list keeps the 13 real Bankone rows and reaches `complete:true`; its persisted scope contains Bankone model provenance plus Banktwo complete-parent absence provenance. A parent that contains the label but whose child fails must remain incomplete. No provider request is fabricated, no rights are widened, and no source article text or credentials enter evidence.
