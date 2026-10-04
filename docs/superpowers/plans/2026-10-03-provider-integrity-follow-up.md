# Provider integrity follow-up

**Issues:** https://github.com/lucronn/autodata/issues/110 and https://github.com/lucronn/autodata/issues/115
**Project:** https://github.com/users/lucronn/projects/8
**Candidate base:** `3bd1362`
**Canonical contracts:** `docs/architecture/mercury2-procedure-composition.md`, `docs/architecture/source-connector-api-compatibility.md`

## Goal

Prevent cross-provider article ID collisions and false completeness in composed procedures, and make the protected AutoDBone connector usable by an approved worker runtime without bypassing deployment protection.

## Decisions

- Article identity and composition deduplication use provider-qualified source identity. The public vehicle identity remains canonical, while each provider vehicle and article identifier is retained separately.
- A provider failure is recorded as failure, not a successful empty response. A partial set of useful source articles may still produce an explicitly partial response; it cannot claim all required source scopes complete.
- Worker-created AutoDBone connectors receive approved request headers through the existing source-header configuration. No credential value is committed or logged. Authenticated CLI access is not accepted as proof of deployed worker access.
- Preserve raw source resource references and hashes where available. Publication remains blocked when rights, provenance, or retention metadata is missing.

## Concrete todo

- [ ] For Issue #110, carry provider-qualified article keys through adapter, stored reads, hydration, deduplication, and lineage; add same-raw-ID cross-provider regression tests.
- [ ] For Issues #110 and #115, propagate per-provider failures and missing scopes rather than reporting complete on one provider's success.
- [ ] For Issue #115, pass approved source request headers to all worker-created AutoDBone connectors; test headers without exposing values.
- [ ] For Issue #115, retain source resource hashes/replay references on failure and refuse publication without required source-rights evidence.
- [ ] Prove five fresh cold/warm multi-component cases on distinct vehicles, protected worker access, and source-backed output at the final SHA. Do not close either issue on fixture-only proof.

## Boundary

Implementation touches ingestion-worker source adapters, catalog service, worker connector factories, stored catalog reads, composition selection, and focused tests. It does not change cloud protection settings, commit credentials, or alter public API authentication.
