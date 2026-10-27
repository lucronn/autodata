# Workshop Bank Authentication and Selection Verification

**Date:** 2026-10-20 (Runtime Verification Completed 2026-10-27)
**Issue:** #139
**Plan:** `docs/superpowers/plans/2026-10-20-workshop-bank-auth.md`

## Verification Summary

This document certifies that server-side authentication for Bankone and Banktwo connectors, HTTP catalog hydration, and end-to-end Workshop catalog selection and article retrieval have been fully verified.

### 1. Automated Test Suites

- **Ingestion Worker Tests:**
  `uv run pytest workers/ingestion-python/tests -q`
  Result: 480 passed, 3 skipped, 25 subtests passed.
  Key tests verified:
  - `test_source_connector_client.py`:
    - `test_managed_keys_reach_only_the_matching_bank_and_override_legacy_tokens`: PASS
    - `test_blank_managed_key_uses_only_its_own_legacy_token`: PASS
    - `test_banktwo_custom_origin_facade_uses_the_managed_banktwo_key`: PASS
  - `test_http_service.py`:
    - `test_catalog_ensure_dispatches_years_to_year_manifest`: PASS
    - `test_catalog_ensure_dispatches_scoped_hydration`: PASS
    - `test_catalog_ensure_requires_key_and_known_scope`: PASS
  - `test_source_adapters.py`:
    - `test_hal_json_media_type_is_adapted_as_json`: PASS
    - `test_car_wrapper_yields_vehicle_identity_candidate`: PASS
  - `test_catalog_service.py`:
    - `test_http_hydration_retries_after_incomplete_result_ttl`: PASS
    - `test_http_hydration_complete_cache_is_provider_free`: PASS

- **Go API Tests:**
  `cd apps/api-go && go test ./...`
  Result: PASS (`github.com/lucronn/autodata/apps/api-go` 0.032s)

- **Go Contracts Tests:**
  `cd packages/contracts/go && go test ./...`
  Result: PASS (`github.com/lucronn/autodata/packages/contracts/go` 0.002s)

- **Shared Contracts Generation:**
  `python3 scripts/contracts/generate.py`
  Result: PASS (no diff against generated Go and Python bindings)

- **Development Adapter and Governance Tests:**
  `uv run pytest scripts/dev/test_*.py -q`
  Result: 82 passed, 2 subtests passed.

- **Autonomy Validator Tests:**
  `python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v`
  Result: 37 passed.

### 2. Live Canary Verification

- **Bankone Canary:**
  - 43 years returned.
  - 33 makes returned for model year 2020.
  - Rejection of cross-service credentials with 401 Unauthorized confirmed.

- **Banktwo Canary:**
  - 62 years returned.
  - 55 makes returned for model year 2020.
  - Rejection of cross-service credentials with 401 Unauthorized confirmed.

### 3. Local Runtime Verification (Full Workshop Selection Flow)

The local stack was brought up and verified end-to-end:
- **PostgreSQL (pgvector):** Container `autodata-postgres-1` healthy on `127.0.0.1:5432`.
- **S3 Object Storage:** Container `autodata-s3mock` healthy on `127.0.0.1:9000` (`autodata-sources` bucket).
- **Ingestion HTTP Service:** Container `autodata-ingest-ingestion-http-1` healthy on `127.0.0.1:8081` (`/healthz` returns `{"status":"ok"}`).
- **AutoData Go API:** Service `autodata-api` running on `:18080`:
  - `/readyz` returns `{"database":"ready","nats":"ready","object_storage":"ready"}`.
  - `/healthz` returns `{"status":"ok"}`.

**End-to-End Flow Validation:**
1. `GET /workshop/` -> Returns HTTP 200 with HTML application assets.
2. `GET /v1/catalog/years?region=US` -> Returns 62 model years (1966 to 2027).
3. `GET /v1/catalog/years/2020/makes?region=US` -> Returns 22 makes (Acura, Chevrolet, Ford, etc.).
4. `GET /v1/catalog/years/2020/makes/acura/models?region=US` -> Returns 6 models (ILX, NSX, RLX, TLX).
5. `GET /v1/catalog/years/2020/makes/acura/models/ilx/configurations?region=US` -> Returns vehicle ID `da143c96-8827-5fc2-ad94-deaa663e2196`.
6. `GET /v1/catalog/vehicles/da143c96-8827-5fc2-ad94-deaa663e2196/articles?region=US` -> Returns 1,830 catalog articles (`complete: true`, `hydrating: false`).
7. `GET /v1/catalog/vehicles/da143c96-8827-5fc2-ad94-deaa663e2196/articles/de47c440-3299-5b2f-adb7-55a37aa32d3c?region=US` -> Returns full procedure body for "Water Pump Removal and Installation".
