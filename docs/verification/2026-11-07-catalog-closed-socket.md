# Catalog buffered-body connector repair evidence

Status: planning only, no implementation under this gate yet.

Goal: Restore bounded catalog connector reads when urllib has closed the underlying socket while buffered response bytes remain.

Contract: docs/superpowers/plans/2026-11-07-catalog-closed-socket.md; record: docs/agents/records/2026-11-07-catalog-closed-socket.json. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8.

Read-only diagnosis: deployed connector deadline reads consistently raise OSError errno9 at transport_socket.settimeout while ordinary reads return complete authentic source pages. Background deepening uses the deadline path. Public2027 makes6 are marked complete despite source counts27 and34; 2014 has0 durable bases despite34/57 source makes; Ford2020 has9 durable models vs21/9 source pages. Both connector origins and credentials are configured; AUTODATA_SOURCE_PERSIST=1. Years62 match union of source43/62 and do not show a missing-years defect. No secrets or provider article content retained here.

Required todo:

- [ ] Reproduce closed-socket deadline failure with real loopback urllib responses for plain and chunked bodies, retaining foreground behavior and slow-body deadline tests.
- [ ] Fix only deadline body reads so buffered bytes remain readable after transport close while live socket and elapsed deadline controls remain enforced.
- [ ] Run focused connector/selector/catalog tests and full ingestion checks as appropriate, obtain independent review and required CI, and push small coherent commits.
- [ ] Record exact evidence and outstanding selector completeness limitations; do not deploy, hydrate the fleet, or modify serving data under this code-only gate.
