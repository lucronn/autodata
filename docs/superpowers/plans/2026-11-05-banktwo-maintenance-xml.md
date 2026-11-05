# Banktwo maintenance XML source adaptation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans after coordinator dispatch and exact-base preflight.

**Goal:** Preserve authentic Banktwo custom maintenance XML as ordered, readable source content without changing rewrite eligibility.

**Architecture:** Add one strict maintenance_schedule XML path inside the existing bound article adapter, including nested HAL article content. Project validated source structure into existing ordered blocks; retain original resource bytes, hashes, identity and evidence. Existing capture and normalization contracts remain authoritative.

**Tech Stack:** Python standard-library XML parser, existing ingestion capture, pytest.

**Spec:** docs/architecture/source-connector-api-compatibility.md, Banktwo maintenance XML source fidelity.

Issue: https://github.com/lucronn/autodata/issues/321
Project: https://github.com/users/lucronn/projects/8
Project item: PVTI_lAHOCSJ8cc4BiQ2BzhGTyPY
Parent: https://github.com/lucronn/autodata/issues/186
Related: https://github.com/lucronn/autodata/issues/300 and https://github.com/lucronn/autodata/issues/317
Inspected source baseline: e8c1993 (current master).
Branch: codex/banktwo-maintenance-xml-plan.

## Evidence and constraints

The privately retained authentic sample contains 20 Banktwo HAL envelopes, eight with custom maintenance_schedule XML inside article content. Generic prose fallback exposes XML tags and loses meaningful structure. All 40 cross-bank retained resources currently have zero v2 eligible documents; this repair addresses source fidelity and does not assert that eligibility must increase. Use the original retained bytes locally; publish only aggregate results and hashes, never authentic bodies, source URLs or credentials.

The accepted grammar is maintenance_schedule with title; ordered operation elements with id/name, their ordered component elements with id/name, and component notes/warranty/qualifier children, followed/interspersed with root footnote in original order. Inline notes may contain br and a href with text/tails. The root title and operation/component id/name are attributes; reject unobserved elements, attributes, hierarchy or non-whitespace structural text instead of flattening them silently. Preserve source title, operation/component names and IDs, note/warranty/qualifier/footnote text, inline link destinations, CDATA literal text and mixed-content/tail order in the existing document representation. Never parse CDATA text as markup. Render attribute values as inert text; respect existing safe-link handling and never fetch XML links.

Reject DTD/entity declarations before XML parsing and prevent external resolution; reject malformed/truncated XML, unsupported roots/namespaces and unknown structure with explicit source adaptation errors. XML recognition must not classify ordinary comparison prose as XML. Retain original HAL bytes/hash/media and context; provider applicability checks must execute before nested adaptation. Do not mutate the envelope to relabel it as XML. No new dependencies, eligibility-policy changes, provider/model calls, activation, deployment, bulk requeue, API/UI/schema changes or source-content redistribution.

## Concrete todo

- [x] Add failing synthetic regressions for maintenance XML structure, mixed content, source identity and fail-closed rejection.
- [x] Add the bounded maintenance_schedule parser and route direct XML and nested HAL XML through it without changing eligibility policy.
- [x] Run focused adapter/capture/normalization regressions and replay retained authentic resources with unchanged hashes; report source fidelity and eligibility separately.
- [x] Obtain independent exact-SHA review and synchronize plan, canonical documentation, Issue and Project evidence before integration.

## One bounded task: maintenance XML adaptation

**Implementation allowlist:**
- workers/ingestion-python/src/autodata_ingestion/source_adapters.py
- workers/ingestion-python/tests/test_source_article_capture.py
- workers/ingestion-python/tests/test_source_adapters.py

**Interface:** Keep adapt_bound_article(resource: SourceResource, context: SourceArticleContext) -> dict with blocks and asset_resource_refs. Add private XML helpers only if needed. Existing build_ordered_document handles resulting heading, paragraph/callout and link blocks; do not expand its schema. If any additional implementation path is necessary, amend this gate before editing it.

- [ ] Add a synthetic fixture resembling this shape (root title and id/name are attributes):

```xml
<maintenance_schedule title="Service &amp; checks">
  <operation id="op1" name="Inspect">
    <component id="c1" name="Belt">
      <notes>Before<br/>After <a href="https://example.invalid/manual">manual</a> tail <![CDATA[<literal> & text]]></notes>
      <warranty>Keep receipt.</warranty><qualifier>Severe service only.</qualifier>
    </component>
  </operation>
  <footnote>Do not omit footnote.</footnote>
</maintenance_schedule>
```

Assert source order for title, names/IDs, before/after/link/tail/CDATA, warranty, qualifier and footnote. Capture direct application/xml and text/xml plus identical content nested inside application/hal+json; assert unchanged stored payload/hash and provider/vehicle context. Verify nested HTML/plain-text regressions remain compatible. Use synthetic content only.
- [ ] Add rejection cases: DTD with internal/external entities; unknown root; malformed XML; wrong hierarchy; unsupported element/attribute/namespace; unexpected structural text; invalid nested link/line-break shape. Include innocent plain prose with a less-than comparison and ordinary existing HTML. Rejected forms must not yield a readable/complete fabricated source. Run the focused tests before implementation and retain the actual failing assertions.
- [ ] Implement strict XML detection/validation and a depth-bounded schema walk over this fixed grammar. Consume element.text, each supported child, and child.tail in source order. CDATA contributes literal text. Emit existing block types, representing title/operation/component identity explicitly and preserving link href through existing safe-link normalization. Preserve every supported field; reject unsupported structure before returning blocks. Never use regex tag stripping or an unrestricted generic XML-to-text fallback. Apply this only after existing HAL envelope/identity validation and to direct XML media. Keep nested HTML/plain prose behavior intact.
- [ ] Run PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_source_article_capture.py workers/ingestion-python/tests/test_source_adapters.py workers/ingestion-python/tests/test_normalization.py -q and git diff --check. Verify actual red-to-green evidence before committing; promptly push each coherent validated milestone.
- [ ] Replay all 20 original Banktwo resources, reporting all eight XML documents with exact hashes, presence/order of each source field and strict document validation. Replay the full 40 retained cross-bank resources to expose regressions and report unchanged v1/v2 eligibility counts independently. Do not claim adaptation equals accepted rewrite, publication or release readiness. Preserve pre-fix reports privately.
- [ ] Independent reviewer inspects the exact implementation SHA, XML safety/rejection, preserved text/attributes/order/tails, source bytes/provenance, context checks and unchanged eligibility policy. Coordinator records test/replay/review evidence in this plan, canonical doc, Issue and Project before integration.

## Gate handoff

Record: docs/agents/records/2026-11-05-banktwo-maintenance-xml.json. Commit the planning checkpoint, pin its exact SHA externally and pass:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-banktwo-maintenance-xml.json --base-sha CHECKPOINT_SHA
```

Required result: {"status":"synchronized","errors":[]}. This planning checkpoint authorizes only the allowlisted source fidelity repair after coordinator dispatch.

## Verified implementation candidate and integration boundary

PR [#322](https://github.com/lucronn/autodata/pull/322) contains the three allowlisted implementation/test paths at commit `1aa8e81acc19476e32f539ba000e9fd96438e908`. The exact checkpoint preflight still returns `{"status":"synchronized","errors":[]}`. The final source adapter/capture/normalization suite passed **171 tests and 60 subtests** in 114.17 seconds; independent exact-implementation-SHA review passed, including 15 focused XML tests and 54 subtests. The review reproduced and fixed numeric/CDATA text loss, fabricated steps and truncated-XML fallback before approval. `git diff --check` passed.

An offline replay of the identical 40 privately retained resources on the checkpoint and candidate preserved every original resource/envelope hash. All 40 adapted; strict-valid documents stayed 24/40 (16 pre-existing media/evidence blockers). The eight XML documents improved from zero to eight with complete observed field/order/link/evidence fidelity, and all eight passed strict validation. v1 editable coverage stayed two documents/ten slots; v2 eligibility stayed zero of 40. Private report SHA-256: `42f2ccc7245c1cb6657a56d64521a096e790e3ff72605a6386bbba2f09ee1f2b`; baseline report SHA-256: `5e10479e5d3ff4ced83d044e3e6f75473be464528f8bf9b096bd40fdb0de21ed`. No private body or credential is committed.

Issue #321 and Project #8 were read back in Review with the same candidate, test and coverage facts. GitHub CI is pending at the time of this documentation checkpoint; integration still requires a passing final-head run and merge review. This source fallback repair does not satisfy the separate full-article rewrite, commerce or production release requirements.
