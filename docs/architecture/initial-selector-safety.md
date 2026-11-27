# Initial public selector safety

Issue: https://github.com/lucronn/autodata/issues/436
Project: https://github.com/users/lucronn/projects/8
Project item: `PVTI_lAHOCSJ8cc4BiQ2BzhI01Rs`.

The internal `/v1/catalog/ensure` route sends years, makes and models through
one owned initial-selector resolver. It no longer routes public years to the
legacy Banktwo manifest daemon, and successful makes/models never schedule
background descendant deepening. The explicit non-public manifest and
deepening helpers retain their separate behavior. Configuration #429 retains
its existing class, dispatch/body controls and START/FIN diagnostic schema.
No article, payment, entitlement, authentication or public response schema changes.

One job is active per ingestion process across initial selector scopes.
Normalized scope identity coalesces concurrent requests independently of the
caller idempotency key. Release starts a global six-second cooldown; an
incomplete or failed scope also receives a thirty-second cooldown. A denied
request returns incomplete/deferred and cannot start a supplier request.
Complete cache hits still perform no supplier work.

The shared control covers all configured providers, pagination and hidden
Banktwo 404 parent-label enumeration/retry:

| Bound | Limit |
| --- | --- |
| Supplier dispatch attempts | 12 |
| Absolute provider/IPC elapsed deadline, including child startup | 20 seconds |
| Minimum spacing between dispatches | 6 seconds |
| Decoded HTTP response body | 1 MiB per response; 4 MiB cumulative |
| Response rows before deduplication, including repair pages | 5,000 |
| IPC input/output | 16 KiB / 4 MiB final result plus up to 128 KiB of partial choices |
| Child address space / CPU / open files | 512 MiB / 22 CPU seconds / 64 |

Normally at most four dispatches fit the elapsed/spacing limits; the request
counter is an independent guard. Byte limits cover response bodies, not HTTP
headers; the HTTP parser also runs inside the child memory/deadline boundary.
A 429 stops the shared job before the next provider. Source failures never
become empty complete coverage. All configured sources must prove complete
coverage for these initial scopes, including years.

The child imports only selector resolution and performs no persistence.
Parent IPC is nonblocking and bounded, stderr is discarded, and fixed stop
codes replace child exception text. On deadline, the parent kills and reaps
only the owned process group, covering DNS, headers and trickling bodies.
The parent may save a partial Year, Make or Model list after a provider finishes
enumerating that scope, before the next provider dispatch. A failed or expired
remaining traversal leaves verified partial options readable. It cannot mark
the scope complete.

Parent persistence has a two-second allowance beyond the supplier deadline
for evidence the child delivered on time. It checks remaining time before
connection, writes and commit and uses one-second connect/statement and 250 ms
lock timeouts. Makes/models store sparse rows and provenance in their
normal scoped marker: version 0 remains partial, version 1 proves complete.
Progress writes leave an existing complete scope intact. These choices do
not enter full vehicle/S3 evidence persistence.

The Workshop-owned global Year entry in `vehicle_catalog_syncs` stores each
supplier's verified choices and exact page provenance in its checkpoint.
The row count measures distinct Years. Partial choices remain selectable and
are eligible for the existing retry after cooldown. Each retry traverses
the configured suppliers under the original budget. A provider roster
change starts a separate set of staged evidence.

After successful global coverage, one bounded PostgreSQL transaction records
complete Year coverage and updates the existing year manifest using the exact
row/page provider, source version and source URI. A source-proven empty set
records completion without a year row. Incomplete state remains separate so
older readers continue to see the legacy projection. An existing legacy
manifest takes precedence during a mixed-version rollout. Inventory years
join the choices while a staged Year read remains incomplete and retryable.
`response_hash` explicitly hashes the normalized selected-year projection,
not supplier body bytes. `source_snapshot_id` stays null; no snapshot or S3
write is fabricated. Missing year facts or page provenance fail closed.

This is synthetic code acceptance. Supplier compatibility, runtime activation,
external licensed display and real browsing acceptance require separate gates.
See the [plan](../superpowers/plans/2026-11-15-initial-selector-safety.md) and
[verification](../verification/2026-11-15-initial-selector-safety.md).

Strict CI import follow-up: child source must bind to the package root that loaded the parent, instead of assuming pytest/runtime sys.path changes were exported in PYTHONPATH. Build the child environment with that absolute source root first, preserve explicitly configured source credentials, disable bytecode writes, and test owned successful/DNS/header/trickle paths with PYTHONPATH absent. Keep stderr redacted and provider/IPC/resource bounds unchanged. This is not supplier compatibility evidence.
