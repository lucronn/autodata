# Configuration hydration anomaly diagnostics

Status: protected421 base5b3e19d3b34208773a77b4b9cfccd3085726cabe/tree92da3c0238725728e43a2bbd4df7a0ec29d02de6 pinned for synchronized planning checkpoint; implementation held until checkpoint preflight. FinalPR strictCI/merge held for protected415/422 integration.

Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8. Plan docs/superpowers/plans/2026-11-15-configuration-hydration-diagnostics.md; verification docs/verification/2026-11-15-configuration-hydration-diagnostics.md.

Configuration item usability is separate from authoritative enumeration. Preserve selectable cached rows, all-configured-provider coverage, marker requirements, current complete/hydrating flags and background dispatch. Never add a partial configuration scope row: current Go considers that marker existence authoritative.

Smallest change is WARNING anomaly logging in catalog_service.py only. Fixed fields are hashed collection scope, bank enum or aggregate, stage/outcome enums, allowlisted exception class or OtherError, and numeric row count. No raw exception/payload/source text, URLs, IDs, tokens, request values, traceback or dynamic class names. Exceptions and provider partials retain exactly their current propagation/continue/status behavior. Positive completion is still established only through durable provenance; no warnings does not prove success.

The exact call-site and redaction/semantic regression matrix is in the plan. Commerce/client/UI/schema/infra/dependency/pagination/timeout/storage/deepening behavior is outside this change. A fresh synchronized protected421-base gate must precede tests/application edits; no provider or serving mutation is authorized by design work. Later protected merge and separate rollout/acceptance gate remain required.

Explicit coordinator-approved amendment includes only the existing _deepen_selector_scope configuration-persistence exception print: substitute safe aggregate row_persistence diagnostic, preserving catch/continue/traversal/budgets/cleanup/coverage and all nonconfiguration logs. A new committed synchronized checkpoint/preflight must precede this call-site edit; red-first captured stdout/log sentinel regression required.
