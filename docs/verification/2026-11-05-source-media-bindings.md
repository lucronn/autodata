# Source media binding consumer verification

Implementation: `0b7cd11d230f16cb7287d0b3940486e77550d8b5`
PR: https://github.com/lucronn/autodata/pull/332
Planning base: `5be336ccfbe1bb2323a546eac0169291ecc485dc`
Tracking: https://github.com/lucronn/autodata/issues/331

## Local evidence

- Machine preflight: `python scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-source-media-bindings.json --base-sha 5be336ccfbe1bb2323a546eac0169291ecc485dc` returned `status: synchronized`.
- `PYTHONPATH=workers/ingestion-python/src pytest -q workers/ingestion-python/tests/test_source_asset_bindings.py workers/ingestion-python/tests/test_banktwo_connector.py workers/ingestion-python/tests/test_article_document.py workers/ingestion-python/tests/test_source_revision_reprojection.py --tb=short`: **100 passed, 7 skipped, 2 subtests passed**. Skips require database fixtures.
- Earlier broader connector/capture run: `PYTHONPATH=workers/ingestion-python/src pytest -q workers/ingestion-python/tests/test_source_asset_bindings.py workers/ingestion-python/tests/test_source_article_capture.py workers/ingestion-python/tests/test_source_connector_client.py`: **184 passed, 9 subtests passed**, before the final C1 and embedded-image fixes.
- Capture-only recheck: `PYTHONPATH=workers/ingestion-python/src pytest -q workers/ingestion-python/tests/test_source_article_capture.py --tb=short`: **140 passed**. This run started at `43af494` before the embedded guard fix; the final focused suite above covers the embedded fix.
- `git diff --check`: passed.
- Tests were observed failing before the boundary acceptance, source fingerprint, C1-control, and embedded-image overwrite fixes. Independent review rechecked the embedded fix at the implementation SHA and reported no remaining findings.

## Scope and release boundary

The consumer validates strict bounded sidecars, retains them in source metadata
and body provenance, and applies exact decoded image attributes without URL
normalization or ordinal inference. Tests verify repeated/nested placement, raw
byte/hash invariance, unavailable fallback, one provider-bound asset fetch, and
no detached duplicate for positioned assets. Explicit HTML refs remain supported.

Bindings participate in source identity while raw body hashes stay unchanged.
Changing a sidecar on recapture can trigger a new transformation and Mercury
rewrite. Canonical reuse/backfill needs separate work. Use new or unpublished
articles for deployment canaries. No live canary, merge, or deployment is claimed.

CI for the implementation SHA is queued/in progress at
https://github.com/lucronn/autodata/actions/runs/42086258312.
