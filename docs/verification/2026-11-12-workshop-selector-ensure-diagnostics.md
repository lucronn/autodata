# Workshop selector ensure failure diagnostics

Issue: [#401](https://github.com/lucronn/autodata/issues/401). Project: [#8](https://github.com/users/lucronn/projects/8). Plan: [2026-11-12-workshop-selector-ensure-diagnostics](../superpowers/plans/2026-11-12-workshop-selector-ensure-diagnostics.md).

## Bounded live evidence

The public 2024 US makes selector returned nine choices with `complete:false` and `hydrating:true` on 2026-11-11 and again on 2026-11-12. The Go API journal records the exact 2024 US makes hydration key `fd3600fb0e00595cc1609c09` receiving ingestion HTTP 502 at 2026-11-11 21:39:25, 2026-11-12 00:44:12, and 02:16:52 EST. A read-only Postgres query found `makes|2024|||US` at `completion_version=0`, zero `selector_rows`, last updated 2026-10-27 04:44:27 UTC. API and ingestion health checks succeeded, but the running ingestion container has no stdout/stderr diagnostic lines for the checked window. These facts locate the failing boundary but do not identify an exception or provider.

## Acceptance and limits

The existing selector ensure path will record only a fixed stage, fixed scope, and exception class when an unexpected exception escapes. It will not log raw exception messages, request data, provider URLs or content, credentials, customer IDs, or article text. The original exception, generic HTTP 502 response, partial-row semantics, and durable completeness rules remain unchanged. Red-first tests must prove the diagnostic record and redaction at resolution and persistence boundaries.

This is diagnostic Workshop app work, not a provider or architecture redesign. It does not deploy production, call live provider APIs, enable purchasing, change grants, or mark the live selector complete. A later authorized rollout and read-only observation are required before the underlying 502 can be diagnosed from the new log. Unit tests cannot establish real vehicle-data or paid-access acceptance.
