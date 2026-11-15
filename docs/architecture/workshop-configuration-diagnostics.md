# Configuration hydration anomaly diagnostics

Status: integrated conflict-free onto protected415 base `76fb21e8f7c080e93f6d38de93a2e1a22cd11f39` / tree `c4b63d3635e7cc5b084f0d9df6154334e6dc36a3`. Reviewed diagnostics implementation byte delta from971ad64 is unchanged. Fresh integration checkpoint/preflight and focused checks are required; final PR/strict CI/merge remain held for protected422 SHA/tree. No provider GET or serving mutation.

Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8. Plan docs/superpowers/plans/2026-11-15-configuration-hydration-diagnostics.md; verification docs/verification/2026-11-15-configuration-hydration-diagnostics.md.

Configuration item usability is separate from authoritative enumeration. Preserve selectable cached rows, all-configured-provider coverage, marker requirements, current complete/hydrating flags and background dispatch. Never add a partial configuration scope row: current Go considers that marker existence authoritative.

Smallest change is WARNING anomaly logging in catalog_service.py only. Fixed fields are hashed collection scope, bank enum or aggregate, stage/outcome enums, allowlisted exception class or OtherError, and numeric row count. No raw exception/payload/source text, URLs, IDs, tokens, request values, traceback or dynamic class names. Exceptions and provider partials retain exactly their current propagation/continue/status behavior. Positive completion is still established only through durable provenance; no warnings does not prove success.

The exact call-site and redaction/semantic regression matrix is in the plan. Commerce/client/UI/schema/infra/dependency/pagination/timeout/storage/deepening behavior is outside this change. Both synchronized gates passed before their respective tests/application edits; no provider or serving mutation is authorized by design work. Later protected merge and separate rollout/acceptance gate remain required.

Explicit coordinator-approved amendment includes only the existing _deepen_selector_scope configuration-persistence exception print: substitute safe aggregate row_persistence diagnostic, preserving catch/continue/traversal/budgets/cleanup/coverage and all nonconfiguration logs. Checkpoint dc709e9 passed before the red-first captured stdout/log sentinel regression and call-site edit. The regression first exposed the raw exception text, then passed with the safe event; traversal/call counts/cleanup are preserved.
