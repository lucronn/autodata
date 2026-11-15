# Catalog buffered-body connector repair evidence

Status: focused code repair implemented; broader fixture verification and required CI pending. No runtime deployment or fleet hydration.

Goal: Restore bounded catalog connector reads when urllib has closed the underlying socket while buffered response bytes remain.

Contract: docs/superpowers/plans/2026-11-07-catalog-closed-socket.md; record: docs/agents/records/2026-11-07-catalog-closed-socket.json. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8.

Read-only diagnosis: deployed connector deadline reads consistently raise OSError errno9 at transport_socket.settimeout while ordinary reads return complete authentic source pages. Background deepening uses the deadline path. Public2027 makes6 are marked complete despite source counts27 and34; 2014 has0 durable bases despite34/57 source makes; Ford2020 has9 durable models vs21/9 source pages. Both connector origins and credentials are configured; AUTODATA_SOURCE_PERSIST=1. Years62 match union of source43/62 and do not show a missing-years defect. No secrets or provider article content retained here.

Required todo:

- [x] Reproduce closed-socket deadline failure with real loopback urllib responses for plain and chunked bodies, retaining foreground behavior and slow-body deadline tests.
- [x] Fix only deadline body reads so buffered bytes remain readable after transport close while live socket and elapsed deadline controls remain enforced.
- [ ] Run focused connector/selector/catalog tests and full ingestion checks as appropriate, obtain independent review and required CI, and push small coherent commits.
- [x] Record exact evidence and outstanding selector completeness limitations; do not deploy, hydrate the fleet, or modify serving data under this code-only gate.

## Focused implementation evidence

Documentation checkpoint `48f04cea619ad71fe6d7b7c44cfa98ca901d4a15` was committed/pushed before implementation; exact-base preflight returned `status: synchronized`, `errors: []`. Issue186 comment6700687063 and dedicated Project8 Catalog connector repair reference were read back before dispatch. Work is isolated on `codex/catalog-closed-socket` from master `0ebbd72c6c3ee29ec65255c207e129e539befa57`.

Implementation `3d6379bbe205a3ffcc4b4f4a6a6d38db1ce0a2c3` catches only EBADF from socket timeout adjustment; it leaves actual response reads, other errors, elapsed deadline checks, and the joined shutdown timer intact. A real loopback Connection:close/fixed-length response reproduced two failing subtests on the old code: direct bounded call and actual background catalog adapter both raised errno9. Ordinary foreground and chunked reads succeeded. With the fix, all six framing/path combinations pass, alongside trickled body and chunk-framing deadline regressions. Focused connector/selector/catalog verification passed 55 tests and 15 subtests; 13 database-dependent tests skipped. `git diff --check` passed.

PR https://github.com/lucronn/autodata/pull/362 is the integration boundary. The API/ingestion HTTP background daemon owns vehicle selector hydration. The separately stopped catalog-index-worker serves article descriptor jobs and does not populate makes/models/configurations. The two paths must not be conflated during rollout.

Full ingestion fixture suite is still running in `/tmp/autodata-catalog-socket-venv` with pinned Stripe16.1.0, which the host Python lacks. Its uncommitted local log is `/tmp/catalog-connector-full-tests.log`; no full-suite success is claimed before its terminal result. Required GitHub checks are pending at PR362. Coordinator inspection found the narrow catch appropriately scoped; independent review and integration remain coordinator-owned.
