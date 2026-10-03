# Plan: Fail visibly on unknown AutoDBtwo catalog response shapes

## Goal

Prevent AutoData from reporting a successful empty selector catalog when AutoDBtwo changes or returns an unrecognized response envelope.

## Tracking

- **Issue:** https://github.com/lucronn/autodata/issues/115
- **Project:** https://github.com/users/lucronn/projects/8
- **Plan:** `docs/superpowers/plans/2026-10-03-autodb-two-response-shape.md`
- **Canonical contract:** `docs/architecture/source-connector-api-compatibility.md`
- **Follow-up PR:** #120

## Evidence and decision

`AutoAPITwoCatalogConnector._items` currently returns an empty list for every unrecognized payload. A changed JSON envelope can therefore look like a legitimate empty make/model/engine list and be cached as success. Preserve valid empty lists from supported list/envelope shapes, but raise a normalized source-shape error when the root value or recognized envelope is malformed or unsupported. Do not cache malformed payloads as successful empty catalog data.

## todo

1. Synchronize this plan and concrete work items to Issue #115 and Project #8.
2. Define explicitly supported catalog list response shapes and fail clearly on unknown/malformed envelopes.
3. Add tests proving valid empty lists remain empty while unknown shapes return an error and are not cached.
4. Run the ingestion worker suite and hosted verification for PR #120 and descendants.

## Acceptance

- Supported array/envelope responses, including an explicitly empty list, retain existing semantics.
- Unknown/malformed catalog payloads surface as a source failure, never as empty success.
- A subsequent valid response can be fetched after a malformed response; the failure is not cached.
