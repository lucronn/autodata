# Preserve verified nested-image evidence through source normalization

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

## Observed failure and decision

The actual paid-access run at `bdfd1c3d455ba8592219084c4df0e7bec9d4b7e2`
captured a provider-bound source body and image, then failed the rewrite before
calling the model. Both banks produced `REWRITE_DOCUMENT_INVALID`. A replay of
the retained source document returned `missing image evidence`: capture had
attached trusted context evidence to the nested image, but ordered-document
normalization dropped it. The rewrite validator correctly refused publication.

Restore the effective trusted capture evidence (context evidence, or the
existing body-snapshot fallback) to each image in the existing post-normalize
pass that already restores verified local media fields. Do not trust upstream
evidence claims or relax strict validation. Keep source URLs and private object
locators stripped, provider-local identities, object verification, order and
unavailable-image semantics intact. The exact technical design was
independently reviewed in
`/tmp/autodata-verified-nested-image-evidence-repair-plan.md` (SHA256
`242cd7fd6ecfde2a664213b7cbd7a6130d9e65a7605865f2fc70907cee3142dc`).

## Exclusive two-file implementation scope

- `workers/ingestion-python/src/autodata_ingestion/source_article_capture.py`
- `workers/ingestion-python/tests/test_source_article_capture.py`

The coordinator owns this bounded fix in its isolated checkout. The paid
worker owns its separate expired-session fixture correction; the UI worker
owns browser runtime verification. No schema, generic document normalizer,
rewrite validator, model transport or provider credentials are in scope.

## Concrete todo and acceptance

- [ ] Save and read back Issue186 and Project8 with this exact two-file scope,
  commit this plan and synchronized record, and pass the machine preflight at
  the pinned full base SHA before code changes.
- [ ] Add a failing actual capture-to-strict-validation-to-fixture-model
  regression for both banks with nested step, instruction, table, list and
  callout figures. Verify ordered position, trusted evidence, verified bytes
  and hashes, no forged upstream evidence, and no cross-bank call.
- [ ] Add unavailable-image and empty-context body-snapshot fallback cases.
  An unavailable figure retains a reason and never becomes verified media.
- [ ] Restore only the trusted evidence in the existing capture pass. Preserve
  the strict rewrite/media validator and exact source/canonical identity.
- [ ] Run focused red then green tests, the source-capture and rewrite suites,
  Python syntax/diff checks, and independent exact-commit review. Commit and
  push coherent validated work.
- [ ] Merge the reviewed correction and rerun all12 real paid-access cases
  across both banks, then the21 API/browser and120 DTO/browser cases on an
  integrated exact candidate. Unit results do not establish release readiness.

No production data, credentials, source provider or cloud resource is used by
the bounded implementation tests. The failed actual run and original source
projection remain preserved as evidence.
