# Article rewrite v2 development evidence

Issue: https://github.com/lucronn/autodata/issues/300
Project: https://github.com/users/lucronn/projects/8
Plan: ../superpowers/plans/2026-11-05-article-rewrite-v2.md

## Authorization and initial red

Pinned planning base: `694ba2af0946710ae39ef4b0f7a867766c4dceb0`.
Exact-base preflight returned `{"status": "synchronized", "errors": []}` before implementation.
The first v2 test failed specifically because the existing rewrite boundary returned
`REWRITE_PROFILE_UNSUPPORTED` for `Tighten the bolts to 25 Nm.` (1 failed).

## Development milestone

The finite grammar renders full directive clauses using source object/adjunct spans,
explicit noun number agreement and reviewed active-to-passive directive templates.
All ten initial verbs have synthetic regressions. Numeric source spelling, including
range signs, decimals and Unicode middle-dot units, remains byte-identical.
Unknown ordinary clauses reject the whole article before model dispatch. The selector
can return only all bound operation identifiers, in source order. Validation rebuilds
the complete expected document and retains existing strict ordered validation.
The v1 default, renderer and validator identifiers remain unchanged.

Focused command:

```sh
PYTHONPATH=workers/ingestion-python/src pytest workers/ingestion-python/tests/test_procedure_rewrite.py workers/ingestion-python/tests/test_procedure_rewrite_v2.py workers/ingestion-python/tests/test_article_lifecycle_types.py -q
```

Result: **81 passed**. Separate transform regression run: **99 passed, 2 skipped**;
the skips require the isolated database harness and do not count as lifecycle acceptance.
`git diff --check` passed.

## Authentic corpus blocker and release boundary

No authorized retained authentic bank capture package was found in this checkout.
The existing `test_source_article_capture.py` uses hand-authored connector stubs;
these are not authentic retained captures. No provider requests were made.
Authentic denominator: **0 total, 0 bankone, 0 banktwo, 0 held out**. Authentic
article/clause coverage, verb presence, improvement over v1 and content review are
**unmeasured**, not zero-defect acceptance. The requested 40-document corpus and
pre-tuning held-out evaluation are unavailable. The vocabulary is supported only
by synthetic regression evidence and requires authentic content review before release.

`tests/fixtures/article_rewrite_v2.json` is explicitly **synthetic development only**:
14 complete authored documents with safety, table and unavailable-image context,
source identities and reproducible hashes. Ten are intended transformable documents;
four represent unsupported coordination, declarative prose, unknown component and
ambiguous adjunct families. They have no bank attribution and earn no realistic
corpus acceptance credit. The initial red preceded implementation; this fixture
package was frozen during development and is not an independent held-out corpus.

Remediation register:

| Scope | Source hash/path | Reason | Owner | Evidence required |
|---|---|---|---|---|
| Intended purchased bankone articles | unavailable | Authorized captures absent | Coordinator/content owner | 20 complete authorized captures, stable selection/hashes, 10 held out, every changed sentence reviewed |
| Intended purchased banktwo articles | unavailable | Authorized captures absent | Coordinator/content owner | 20 complete authorized captures, stable selection/hashes, 10 held out, every changed sentence reviewed |
| Unsupported development families | fixture identities/hashes and unsupported prose paths | Complete clause outside finite grammar | Coordinator/content owner | Authentic family mapping, separately reviewed grammar/version or separately designed expert publication path |

Source fallback preserves availability; it is not rewrite completion. No production
activation, deployment, universal coverage or purchased-dataset completion is claimed.
Independent content/code review and exact-SHA isolated lifecycle evidence remain pending.
