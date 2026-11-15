# Configuration hydration diagnostics proposal

Status: historical PROPOSED snapshot, with no synchronized implementation record or implementation authority. Preserved only to keep the original completed-runtime receipt reference intact; no later diagnostics design is imported. This is a read-only diagnosis/proposed successor checkpoint, not a serving change.

Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8. Runtime receipt docs/verification/2026-11-14-private-read-only-runtime-rollout.md. Owning live ingestion source92d81a1afbcf9e025d017b9b30f6dd4bb54f3e8a; public product3a18d9c7ca51606a1dfb6d7691d3039d6d27c9f3 has the same catalog behavior.

## Decision from bounded evidence

Makes and Acura models achieved durable dual-bank completion. The returned Integra configuration is usable, but authoritative configuration enumeration remains unproved. Go catalog_http.go149-163 intentionally publishes usable item.complete:true with collectioncomplete:false/hydrating:false while still scheduling ensure for the missing marker. TestUsableConfigurationsAreNotBlockedByMissingHydrationScope locks in selectable rows. Itemcomplete is based on nonrejected identity/config rows, not source enumeration or rights approval. Do not replace collectioncomplete with rowcount/usable, manually insert marker, relax provider coverage or make more source requests during diagnosis.

The Python foreground path requires every configured provider to complete, then rowpersistence to succeed, before _persist_hydration_scope writes configurations coverage. The current CacheFirstCatalogService catches provider exceptions without safe diagnostics; incomplete configuration results deliberately write no marker. Rowpersistence ValueError also bypasses current class-only error logging. Thus absence of a marker cannot distinguish provider partial/exception, invalid rows, persistence error or unfinished work. Background selector deepening persists rows without a scope marker; this is a separate limitation and does not establish why the explicit configuration ensure did not persist coverage.

## Smallest proposed change, requiring a fresh synchronized gate

Preserve all API flags, providerall-complete predicates, existingrow usability, storage requirements and boundedrequest behavior. Add config-scope safe failure diagnostics only: configuredbank enum, stage enum, completion boolean/count and exceptionclass; never error text, URLs, opaqueIDs, requestbody, credentials, source prose or rawproviderpayload. Record caught provider exception/incomplete results, and internal row/coverage-persistence validation failures without changing response statuses. Do not persist partial configuration scope rows: Go currently trusts existence of a configuration scope marker, so a diagnostic-only row could falsely claim completeness. No schema, provider connector behavior, payment, grant, article, model or UI change.

Concrete todo for the future checkpoint:

- [ ] Synchronize this proposal/Issue401/Project8/canonical architecture/verification and a fresh exactbase record; commit/push and pass preflight before application/test edits.
- [ ] Red-first isolated tests: full two-provider completion plus real fixture persistence writes authoritative marker; exception/partial/persistence failure leaves missing marker and emits only safe diagnostic fields; secrets embedded in exception text never log.
- [ ] Explicit public regression preserves usableitemtrue/collectionfalse/hydratingfalse plus backgroundensure when marker missing; complete authoritative marker yields collectiontrue and warmread skipsensure.
- [ ] Minimal diagnostics implementation, focused fixture checks, independent exactheadreview/requiredCI/protectedmerge, then a separate source/image/runtime compatibility gate before any deployment. Preserve92 runtime/backup/rollback. Do not accidentally include SVG dependencies on oldimage.
- [ ] After coordinator-approved release, permit at most one separately authorized exact2024/Acura/Integra configurations request plus bounded durable/log observation, with protectedstate/disabledpurchase checks. Until then report partial enumeration; existing row stays selectable. No directprovider/article/model calls.

No code fix is warranted merely to make the observed response flags look complete. This proposal targets the missing causal evidence; a behavioral fix should follow the proven failure class instead of guessing a bank or storage fault.
