# Retained Workshop reader acceptance evidence

> **Archived report (2026-11-14), preserved from PR #418 at `9760230e6f0939b16ac38d3b3c0135c63f29564d`.** Runtime, source, health and acceptance statements describe that dated checkpoint only, not present service state. Operational steps and old planning records are historical/non-replayable; this import creates no execution authority. See the [consolidated evidence and corrections](2026-11-15-historical-evidence-consolidation.md).

Issue: https://github.com/lucronn/autodata/issues/416
Project: https://github.com/users/lucronn/projects/8
Source inspected: `c115dcde11bee0ecc64052e8d51d15de7e572da9`

Eight retained current articles have ordered documents. Real authenticated
Workshop reader and media acceptance remains **unverified**. This report records
aggregate database inspection and existing code checks; it does not report a
Firebase login, Stripe settlement, entitled browser article read, or media read.

## Isolation and evidence boundary

On 2026-11-14 the coordinator authorized an internal local database clone of the
private serving backup for inspection. The backup was restored with
`pg_restore --no-owner --no-acl --exit-on-error` into a new PostgreSQL container
on a dedicated Docker network. Restore succeeded; inspection confirmed
`Internal=true`, no network gateway, and an empty published-port map. Aggregate
read-only queries against serving data and the clone agreed on current article
availability, rights metadata, and entitlement scope. The clone is a snapshot,
not evidence that a deployed API executes the inspected source revision.

The evidence directory is private (mode 0700). Query receipts contain aggregate
counts and fixed status values only. No article prose, customer identifiers,
media bytes, provider URLs, storage keys, session tokens, or credentials are
included in this report. No production grants, services, rights records, payment
configuration, or data were changed. No provider or identity/payment service was
called. No fixture order, grant, or authentication session was created in the
clone.

## Retained content and media

`catalog_article_current` contains eight available articles across two exact
vehicle configurations, with these document projections:

| Origin | Provider | Articles | Ordered document blocks | Articles with image references |
| --- | --- | ---: | ---: | ---: |
| canonical | bankone | 2 | 50 | 1 |
| canonical | banktwo | 2 | 20 | 0 |
| source | bankone | 1 | 24 | 1 |
| source | banktwo | 3 | 124 | 0 |

All eight documents have an object containing a `blocks` array. Four current
canonical revisions are published; the four source-origin views do not imply
canonical publication. Source revision projections comprise six `readable` and
two `partial` records. These are storage facts, not a review of the licensed
instructions or an authenticated reader result.

All 14 current image occurrences have `status=unavailable`, reason
`source image reference is missing`, and no storage key. The source resource
manifests contain 14 `UNSUPPORTED_ASSET_MEDIA` entries and eight entries without
a failure code. Their observed keys are `failure_code`, `media_type`,
`opaque_ref`, `role`, and `sha256`; they do not themselves provide an
authoritative localized-object mapping. The current images therefore cannot
produce displayable paid-media URLs through the existing projection rules.
Eight nonfailed resource entries must not be reported as eight displayable
images. The missing references and unsupported media require investigation
under a separate, authorized ingestion task; this inspection does not determine
their upstream cause.

## Authority and rights

All eight current articles and their descriptor/body source snapshots have
`takedown_status=active`. Every relevant descriptor and body snapshot lacks a
`redistribution_status` value, and every relevant body snapshot lacks a `terms`
key. Missing metadata does not establish either permission or prohibition;
affirmative supplier authorization for the proposed staging test remains a
coordinator dependency. An active takedown flag is not that authorization.

The single retained active entitlement has no customer account, configuration,
or commerce order scope. It is a legacy dataset entitlement and cannot satisfy
the ordinary Workshop exact-configuration grant check.

The inspected server contracts preserve these boundaries:

- Article index, detail, explicit preparation, and source routes authenticate
  the customer and resolve the exact configuration and region before consulting
  the server-owned grant authority. Article identity must match that scope.
- Paid article GETs are observational; preparation is a separate authenticated,
  origin/CSRF-checked POST. An available source document can remain readable
  independently of canonical rewrite progress.
- Source review pins the selected source revision. Media references bind the
  customer, configuration, article, provider identity, source/canonical anchors,
  selected revision, and asset. Reads revalidate current grant and source rights
  before reading the localized object. Unavailable images do not receive URLs.

Owning source: `apps/api-go/catalog_access.go`, `catalog_http.go`,
`catalog_source.go`, and `catalog_media_access.go`.

## Verification and remaining todo

At the inspected source revision, `go test ./... -count=1` in `apps/api-go`
passed. The existing Workshop client/demo Node suite passed 267 tests with zero
failures or skips. These are existing local code tests. Opt-in PostgreSQL
integration cases were not enabled, and no real browser acceptance ran here.

The existing `workshop_paid_access_smoke.py` / `test_paid_catalog_api_integration.py`
harness runs isolated fresh synthetic databases with a fixture Firebase verifier
and `StripeFixture` through the real commerce service. It is useful authority
regression coverage. It must not be pointed at the retained clone or represented
as real Firebase, real Stripe test settlement, or retained-content browser proof.
No reader implementation defect was established in this lane, so no application
change or implementation-gate exception is proposed. A future implementation
requires its own synchronized checkpoint under the canonical gate.

Concrete todo, synchronized with Issue #416 and Project #8:

- [x] Inspect current paid article/source/media authority and existing fixture limits.
- [x] Restore the private snapshot into an isolated internal-network database
  with no published port; inspect aggregate content, rights, and media metadata.
- [x] Record storage availability separately from grant authority, usable media,
  and real browser acceptance.
- [ ] Confirm supplier test-use rights and the named Firebase staging tester
  through the coordinator.
- [ ] Exercise ordinary isolated sign-in, test settlement, exact scoped grant,
  retained article/source reads, and media in the browser; keep protected receipts
  private and publish aggregate outcomes only.

The final item remains open even if all fixture suites pass. Actual media
acceptance additionally requires retained supported localized assets or an
explicitly documented unavailable-media outcome; unavailable placeholders do
not prove a successful retained-image read.
