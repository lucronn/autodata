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

## Durable v2 development and review corrections

The isolated initial red (after infrastructure recovery) produced **5 failed**:
v2-only `Inspect`/torque articles hit v1 worker eligibility in both banks; unsupported
ordinary prose persisted `REWRITE_NOT_APPLICABLE` instead of its specific reason;
and a rehashed forged operation selection was accepted at publication.
The worker now routes eligibility by lease profile. Result storage, validation and
publication reconstruct v2 operations under existing locks, in addition to their
original source/result/projection/attempt checks.

Independent early code review identified the safety-keyword masking defect and
worker preflight defect. Five pure red regressions confirmed that mixed ordinary
and safety sentences were falsely accepted. Safety classification now requires an
anchored marker and a single sentence without semicolons, newline, coordination
or ambiguous commas. Other unsupported technical/safety prose remains source-
readable through whole-source fallback. Focused pure suite after narrowing and
limit/response-shape checks: **94 passed**.

The isolated stack uses project `autodata-article-v2`, the checked-in lifecycle
Compose configuration, its owned test-runner build, and no external source/model
credentials. Initial setup hit Docker-root disk exhaustion, then SeaweedFS refused
volume allocation with less than 3% free. The coordinator reclaimed unused build
cache. A local uncommitted `/tmp/article-rewrite-v2-compose.yaml` override binds
only the isolated SeaweedFS `/data` to `/tmp/article-rewrite-v2-s3`, where space is
available. No repository infrastructure files or application database were modified.
These setup errors are not counted as code red or acceptance passes.

Development corpus measurement (offline deterministic selector, no provider calls):

| Metric | Synthetic documents only |
|---|---:|
| Documents / ordinary-or-protected prose leaves | 14 / 38 |
| v1 documents with accepted opening substitutions / changed slots | 4 / 5 |
| v2 complete bounded documents / changed directive clauses | 10 / 20 |
| v2 protected prose clauses retained in accepted documents | 10 |
| v2 whole-source fallbacks | 4 |
| Authentic documents / authentic held-out documents | 0 / 0 |

The v1 figures measure its original opening substitutions; they are not meaningful
whole-article completion. These development counts are not per-bank coverage or
independent holdout performance. Every synthetic fallback has `/blocks/0/text`
unsupported with `REWRITE_UNSUPPORTED_PROSE`; the committed fixture supplies exact
source hashes for `synthetic:coordinated`, `synthetic:declarative`,
`synthetic:unknown-component` and `synthetic:ambiguous-adjunct`. Their owner is the
coordinator/content owner. Extension requires authentic family mapping, full context
review and a new reviewed grammar/profile or separately designed expert path.
Local machine-readable measurements: `/tmp/article-rewrite-v2-acceptance/development-corpus.json`.

The expanded isolated v2 suite passed **16 tests, 0 failures/errors/skips**
(`v2-integration-green.xml`). It exercises both-bank explicit v1-to-v2 profile
refresh with unchanged source and immutable v1 revisions; unchanged v2 refresh
references the completed transformation owner without resetting it; failed v2
attempts stay source-readable; unsupported articles dispatch zero model calls;
full documents retain safety/table/unavailable-media context; two worker processes
emit one publication per transformation; process death before/after durable model
results and inside publication recovers; actual HTTP request ambiguity is bounded;
exhausted same-source refresh retains the owner/budget; changed-source refresh
fences the old publisher and selects source while pending; 100 ensures/reads after
restart measure **source=0, asset=0, model=0, schedule=0** for each bank.

The first expanded test draft assumed active refresh supersedes work and completed
refresh makes the original transformation job the reader pointer. Inspection of
the existing refresh contract showed that active jobs coalesce and completed
observations reference the unchanged transformation owner in their checkpoint.
Tests now assert those existing semantics; source-job code was not changed.

An additional publication-binding rerun passed **1 test** after asserting that
both store-validation and publication reject a rehashed foreign operation.
Final focused pure suite with explicit classification-count reports: **95 passed**.
These results cover synthetic fixture lifecycle correctness, not authentic corpus
acceptance. Full exact-commit harness and final independent code review follow.

### Second independent fidelity correction

Review of `ba4bbfbfb380df2e7216f113d75ccd090dd77d49` found that the interim
punctuation-based retention rule still admitted independent ordinary directives
behind colons, em/en dashes and Unicode ellipsis. Five added tests failed before
the correction. Retention now uses a finite full-match grammar too: reviewed
negative/mandatory directives and `If equipped` forms with the finite verb/object
vocabulary (plus the tested `start the engine` safety context), optionally in
explicit Warning/Caution/Danger/Note/Notice forms. Arbitrary safety prose is not
classified complete by keywords or delimiter exclusions. It remains verbatim via
whole-source fallback. Callout/table/link/title/media blocks remain wholly immutable.
Final pure suite after correction: **100 passed**.

The intermediate exact-ba4bbfb full harness was deliberately interrupted when this
code correction was required. Its partial log earns no exact-SHA acceptance credit.
The complete harness will run against the subsequent committed corrected code.
