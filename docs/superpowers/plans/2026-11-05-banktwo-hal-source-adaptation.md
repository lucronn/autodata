# Banktwo HAL source adaptation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this bounded task after exact-base preflight and coordinator dispatch.

**Goal:** Accept authentic Banktwo application/hal+json article resources through the existing bound JSON/HTML adapter without losing source content, media references or provenance.

**Architecture:** Reuse `adapt_bound_article(resource, context)` and its existing nested `_embedded.data.article` JSON and HTML paths. Recognize the exact `application/hal+json` resource media type; preserve provider scope, original resource bytes/hash and all applicability checks. This gate changes no normalization grammar, lifecycle schema or provider transport.

**Tech Stack:** Python, pytest, existing source capture fixture and private offline retained resources.

**Spec:** docs/architecture/source-connector-api-compatibility.md, Authentic Banktwo HAL resources.

Parent: https://github.com/lucronn/autodata/issues/186
Related: https://github.com/lucronn/autodata/issues/300
Project: https://github.com/users/lucronn/projects/8
Source baseline: `27b959bf3845bb6bc3f20c3b40db5a582c61573e`.
Branch: `codex/banktwo-hal-gate`.

## Concrete todo

- [ ] Add red regressions for HAL nested article HTML, ordered structure, source identity and malformed envelopes.
- [ ] Accept exact application/hal+json through the existing bound JSON adaptation path with fail-closed envelope handling; preserve all other media behavior.
- [ ] Run focused source capture/adapter regressions and offline replay of all 20 privately retained authentic Banktwo resources; record hashes, normalization and remaining media/rewrite blockers.
- [ ] Obtain independent exact-SHA review and synchronize Issue/Project evidence; keep activation and deployment disabled.

## Evidence and scope

Private evidence root: `/home/corp/autodata-evidence/authentic-corpus-20261105/` (0700; private bodies must never enter GitHub, Git or command logs). Selection manifest SHA256 `1b2dd359fee84a95fa06b5ea2181f87c625aa9224071eb40a85ab9451a41a4b0`; report SHA256 `18449b01302f94e18e995d6d4e3805cf39a30fdf6d417333efa6bbe2e4005220`; results SHA256 `4b13dedb53fa9605982e6faac8c50d43944cec1e3c4ac7dcb873a7157b0c21aa`.

40 exact resource payloads/envelopes were retained using existing working authenticated connector clients: 20 per bank, 20 unique source payload hashes per bank, two vehicle selectors, ten preassigned heldout identities per bank. Holdout is post-development, not pre-tuning independence. All 20 Banktwo payloads are application/hal+json; `_embedded.data.article` contains title/content/_links/id, content is HTML. Current adapter rejects all 20 with `unsupported article media`. Bankone contains 20 text/html payloads, zero v1 editable slots, zero v2 eligible; seven fail strict image verification because asset binaries were not captured. This is an initial first-page sample, not purchased-dataset coverage.

No live provider/model calls, activation, deployment, bulk requeue, profile selection, schema, UI, API response changes or private-content redistribution are authorized in implementation. Replay uses only retained local payloads. No generic arbitrary +json acceptance. Existing application/json, HTML, plain text and PDF behavior stays compatible. Unknown/malformed HAL cannot become a fabricated empty complete document. Unsupported grammar and unresolved media remain explicit source fallback, never canonical completion credit.

## One bounded task: exact HAL adaptation

**Implementation allowlist (two paths only):**
- `workers/ingestion-python/src/autodata_ingestion/source_adapters.py`
- `workers/ingestion-python/tests/test_source_article_capture.py`

Existing interface: `adapt_bound_article(resource: SourceResource, context: SourceArticleContext) -> dict` with `blocks` and `asset_resource_refs`; retain it unchanged. No new dependencies or modules.

- [ ] Add parameterized regression in the existing test file using its `capture_fixture`: HAL resource body `{"_embedded":{"data":{"article":{"title":"Pump","content":"<p>Remove the cover.</p><table><tr><td>25 Nm</td></tr></table><img data-resource-ref=\"asset:one\" src=\"https://source.invalid/a.png\">"}}}}`. Compare HAL and application/json capture under identical descriptor/context and fixture assets. Assert complete ordered text/table/image placement, preserved evidence/asset references, verified original bytes/hash/media type, and no calls to the other provider. Keep fixtures synthetic and attribution explicit.
- [ ] Add malformed HAL cases (nonobject top-level; missing/nonobject `_embedded.data`; missing/nonobject `article`; article `content` nonstring when present) that reject rather than silently producing empty blocks. Add explicit wrong vehicle/year/provider-scope cases equivalent to existing application/json identity rejection. Existing valid direct application/json support is not narrowed. These tests must fail before implementation for the real HAL rejection or malformed envelope behavior.
- [ ] Run `PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_source_article_capture.py -q` and retain red evidence privately.
- [ ] In `adapt_bound_article`, route exact media `application/hal+json` into the existing JSON path; require its observed nested object/article structure and type-check content before reuse. Keep all existing identity-layer checks and resource metadata. Reuse existing HTML parser instead of flattening content or stripping tables/images. Do not invent unverified media evidence or bypass unavailable-image handling. If further fidelity defects require another implementation file, stop and amend this gate.
- [ ] Re-run the focused tests, then `PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_source_article_capture.py workers/ingestion-python/tests/test_source_adapters.py workers/ingestion-python/tests/test_normalization.py -q`; run `git diff --check`. Tests must run without live providers or model keys.
- [ ] Replay all 20 exact private Banktwo retained resources through the changed adapter with the original stored selectors/descriptors and unchanged body hashes. Record 20/20 adaptation or exact failures, strict normalized validation/media outcomes and v1/v2 eligibility separately. Do not label adaptation alone as lifecycle/publication or independent semantic acceptance. Preserve failures and the original pre-fix corpus report.
- [ ] Commit/push the coherent validated implementation. Independent reviewer checks exact SHA, malformed content rejection, applicability, unchanged bytes/hash/provenance and ordered table/media fidelity; coordinator synchronizes evidence in this plan/canonical doc/Issue/Project before integration. No merge/deploy follows automatically.

## Gate handoff

Record: docs/agents/records/2026-11-05-banktwo-hal-source-adaptation.json. Plan/checkpoint must be committed before implementation, pinned externally by exact SHA and pass:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-banktwo-hal-source-adaptation.json --base-sha <committed-checkpoint-sha>
```

Required result: `{"status":"synchronized","errors":[]}`. Fresh Issue and Project source/status readback hashes are recorded in the synchronized record. The coordinator owns implementation dispatch and exact checkpoint pin.

Issue: https://github.com/lucronn/autodata/issues/317
Project item: PVTI_lAHOCSJ8cc4BiQ2BzhGS0GA
Tracking readback: Issue body and Project Source/status Ready matched literally before checkpoint.
