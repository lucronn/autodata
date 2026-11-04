# Workshop PostgreSQL Observation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This checkpoint is plan-only and awaits independent coordinator review; it dispatches no builder or runtime action.

**Goal:** Prove a bounded catalog-before-ledger protocol under an explicit ledger-only MAINTAIN capability in a disposable PostgreSQL17 adversarial harness; preserve the production catalog-only v2 collector and every release/readiness denial.

**Architecture:** Prove the stronger observation protocol in a disconnected Python module and an explicitly invoked disposable local PostgreSQL17 harness. Give a new probe role SELECT and MAINTAIN on precisely the ledger, acquire SHARE ROW EXCLUSIVE before the first transaction snapshot, validate built-in catalog facts in Python, and only then send a bounded ledger query over the same connection. Production runtime-check.py remains catalog-only v2, with schema/services/runtime_evidence false.

**Tech Stack:** Python standard library/unittest, PostgreSQL17 server/client/development headers, local C compiler; no downloaded package or extension.

**Spec:** docs/superpowers/plans/2026-11-03-workshop-hosting.md (catalog-only v2 and full-protocol boundary); docs/agents/pre-implementation-gate.md.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8, item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Source integration: `ee57cd13a2f4e0a15d9e1212acfd1779451a4a91`.
Integrated prerequisite: `5bf59c2360066d6204ddd7303a96b45f4caf0c8b` (catalog-only v2), gate `3a511f1d8a7c3b45fcc67c93a121063286c95097`.
Excluded unsafe candidate: `c51d637708c1e2ad24719e69d32ea87654c14473`; never merge it.

## Global constraints and exact ownership

This is an explicit privilege-changing proposal for a test fixture, not permission to broaden autodata_metrics. Production role provisioning, runtime SQL, helper installation, Compose/cloud/image builds or pulls, application startup, payment/model/bank/Firebase calls, secret access and DNS remain outside scope. The only later executable activity proposed here is local disposable PG17 and local compilation after the synchronized checkpoint, pinned preflight and coordinator approval. No Docker daemon use is needed.

The new test-only `autodata_schema_probe` LOGIN role has NOINHERIT, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS, no memberships, no object/database/schema/sequence ownership, and no CREATE/TEMP. Its effective application rights, including PUBLIC and column grants, are exactly CONNECT on `autodata`, USAGE on `public`, SELECT and MAINTAIN on `public.schema_migrations`. MAINTAIN is a real maintenance capability; do not describe the role itself as read-only. Reject INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER, all column writes and any maintenance on another relation. Do not substitute UPDATE/DELETE/TRUNCATE to obtain a lock.

A distinct `autodata_schema_owner` NOLOGIN role owns public.schema_migrations; the disposable bootstrap administrator owns the database/public schema and fixture-only sentinel functions. Neither application roles nor the probe own the ledger, its indexes, types, opclasses or functions. Only the fixture administrator can arrange hostile DDL for tests. No SECURITY DEFINER helper, privileged role membership or owner-switching exists in the observation client. Provisioning SQL is fixture-only, never in runtime-grants.sql or a migration.

Trusted boundary: upstream PG17 binaries/built-in catalogs/types/operators/functions/access methods and fixture administrator. Host root, server superuser, malicious hooks/preload extensions or altered built-ins are excluded. Ordinary relation owners and concurrent DDL are tested adversaries. The harness prevents accidental production use by starting and owning its own PGDATA/socket under a private fresh temporary directory; it accepts no DSN, existing server, arbitrary database name, TCP endpoint or production paths.

Exact prospective implementation allowlist (five paths):

- `infra/deploy/gce/schema_probe.py`
- `infra/deploy/gce/test_schema_probe.py`
- `infra/deploy/gce/test_schema_probe_pg17.py`
- `infra/deploy/gce/testdata/schema_probe_sentinel.c`
- `infra/deploy/gce/testdata/schema_probe_fixtures.sql`

No existing implementation file changes are permitted, including runtime-check.py, test_host_runtime.py, runtime-grants.sql, cloud-ops.py, workflows, application/DTO/browser code and R6 parsers. Planning/evidence documentation changes require the coordinator to name their paths before dispatch; this plan's implementation allowlist contains no implicit catch-all docs permission.

## Module interfaces and fixed sequence

Create `schema_probe.py` without import-time I/O, CLI or runtime-dispatch registration. Define `observe_catalog_ledger(transport, expected_versions: tuple[str, ...]) -> dict`, `validate_catalog(value: dict) -> None`, and `ProbeUnavailable`/`ProbeTimedOut`. `transport` exposes `send(data: bytes)`, `read_frame(maximum: int, deadline: float) -> bytes`, `abort() -> None`, and `close() -> None`; production dispatch cannot instantiate it. It sends only module-owned constant bytes. Expected versions are used only for Python comparison; never interpolate them into SQL. Reject empty/>256 inventories, duplicates and strings outside ASCII `[0-9]{3}_[a-z0-9_]{1,120}` or over128 bytes before opening a transaction. An accepted result is test evidence with `protocol_version:3`, `scope:'disposable_schema_ledger'`, `ledger_matches:true`, `schema_attested:false`, `production_ready:false` and `deployment_authorized:false`; a ledger match is not proof of the entire application schema.

One persistent PG17 psql connection, `-X --no-password --no-psqlrc --quiet --tuples-only --no-align --set=ON_ERROR_STOP=1`; no shell/TTY, scripts from writable search paths or caller-selected SQL. Harness creates a private socket, peer-authenticated same-OS-user map only to the fixed test role, and launches psql with cleared environment, `PGSERVICE/PGPASSFILE/PGPASSWORD/PGHOSTADDR` absent, controlled HOME, localhost TCP disabled. Server command: `listen_addresses=''`, unix_socket_directories set to the private path, fixed port5432, `shared_preload_libraries=''`, `session_preload_libraries=''`, `local_preload_libraries=''`, logging to a private fixture log. Readiness uses the owned local socket, never HTTP or application startup.

Fixed client PGOPTIONS: `-c default_transaction_read_only=on -c statement_timeout=2000 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=5000 -c search_path=pg_catalog -c jit=off`. Do not SELECT even server_version before the initial LOCK inside the observation transaction. Exact first bytes:

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
LOCK TABLE ONLY public.schema_migrations IN SHARE ROW EXCLUSIVE MODE;
```

BEGIN/LOCK do not establish a snapshot. The first catalog SELECT must occur after the lock succeeds and conflicting DDL/ledger writers drain. SHARE alone permits CREATE INDEX; ACCESS SHARE permits both ordinary and concurrent index creation. SHARE ROW EXCLUSIVE excludes ROW EXCLUSIVE, SHARE and SHARE UPDATE EXCLUSIVE, including regular/concurrent CREATE INDEX and REINDEX. The read-only transaction can take this PG17 lock with MAINTAIN; this must be demonstrated on the actual server, not inferred from fake tests. LOCK on a view can recurse into view references even with ONLY; it does not run the view query. Fixture tests must prove sentinel nonexecution, bounded permission failures/lock waits and cleanup on this path. Foreign relations are refused by PG17 LOCK. Do not claim LOCK is relation validation.

After LOCK, send one constant catalog-only SELECT. It must not reference an application relation in FROM/JOIN/EXPLAIN/COPY/TABLE, resolve application regclass output or deparse expressions. Names only appear as catalog-name comparisons. All functions, casts, operators and collations used by the catalog and ledger queries are explicitly pg_catalog-qualified, including `OPERATOR(pg_catalog.=)` where relevant. Use exact built-in OIDs derived from pg_catalog namespace/name identities, never execute a handler to identify it. Reject any ambiguous/missing row or unexpected catalog state. Python validates the complete response before any ledger SELECT bytes are sent. The state machine sends no prequeued second query, reconnect, COMMIT, DML, maintenance command or dynamic SQL.

### Exact catalog safety predicate

Catalog JSON has exactly `protocol_version:3`, `phase:'catalog_locked'`, `identity`, `rights`, `relation`, `columns`, `indexes`, `builtins` at root. Nested fieldsets are fixed by the module and exhaustively tested. The implementation commit must include the literal catalog query and a fixture object documenting every field; independent review verifies that each predicate below is represented and there is no permissive missing/null branch. No raw expression tree, SQL definition or application value is returned.

- Identity: session_user=current_user=`autodata_schema_probe`; database=`autodata`; integer server_version_num in170000..179999, transaction/default_read_only true, isolation `repeatable read`, client_addr/client_port null. Only those two fields may be null. Observe no restricted server file setting.
- Rights: all role flags/memberships/ownership/write prohibitions above, with SELECT=true and MAINTAIN=true only for the target OID. Effective rights include PUBLIC and column grants across non-system objects. Maintenance on other application relations or privileged role membership rejects.
- Exactly one public.schema_migrations OID, ordinary permanent heap, built-in heap AM/handler identities, no partition/inheritance edges, no RLS/FORCE RLS, no rewrite rules, no triggers, no TOAST-index/custom AM exposure through user-defined AMs. pg_class.relam and pg_am.amhandler match the trusted built-in identities; do not call them. TOAST relation/index, if allocated, must also use built-in heap/btree with built-in opclasses and no expression/predicate.
- Exactly two live columns: version built-in text NOT NULL and applied_at built-in timestamptz NOT NULL; neither generated nor identity. No dropped user columns, domains or custom types. version uses built-in database default collation or built-in C/POSIX; arbitrary collation and nondeterministic collation reject. Default expressions are never deparsed/evaluated by SELECT and are not schema attestations.
- Exactly one index: the valid/ready/live, immediate unique primary-key built-in btree on version alone; no INCLUDE columns, expressions, predicates, exclusion constraint, invalid concurrent index or extra index. Check `pg_index`, `pg_constraint`, index `pg_class`, `pg_am`, `pg_opclass`, `pg_opfamily`, `pg_amproc`, `pg_amop`, `pg_operator`, `pg_proc`, `pg_collation` via built-in catalog reads. The entire selected text_ops family/operator/support-function identity set must equal the fixture baseline built from pristine same-major PG17 built-ins; compare OIDs/names/namespaces and built-in language identities without executing or deparsing support code. No custom opclass, index AM, operator, comparator, collation or support function passes. Every index is checked, including disabled/invalid indexes that the planner may still inspect.
- Row and metadata bounds: exactly2 columns, exactly1 target index, at most32 support-function/operator identity entries, ASCII metadata strings <=128 bytes, no expression payload. Trusted built-in text output/compare/octet_length, timestamptz and JSON aggregates only; applied_at is never selected/output. Python does not treat catalog acceptance as success after lock loss or connection replacement.

The probe locks only the ledger relation; it does not lock an entire database or prevent a privileged superuser modifying catalog dependencies. Under trusted built-ins, DDL affecting the ledger/index must conflict with the held lock. If a PG17 race fixture disproves this for an otherwise allowed dependency, do not add a no-concurrent-DDL disclaimer: fail the milestone and revise the gate before broadening locks/privileges.

### Frozen wire fieldsets and accepted values

Root/identity/rights/relation/indexes/builtins are exact objects. `columns` is exactly the two entries below in attnum order; no additional array exists in catalog phase. Integers are actual int values, excluding bool. All flags below are required and have the literal accepted values shown. An OID is integer1..4294967295; PG17 version uses the range above. Baseline identity verification is encoded as required booleans derived entirely from catalog comparisons; the client never accepts a missing flag or trusts a server-provided digest as the baseline. The same-major pristine baseline is obtained before any fixture extension/hostile object is installed and frozen for that harness invocation. Baseline built-in identities are matched by exact PG17 namespace/name/access-method/family signatures and internal-language/prosrc values; a new or replaced user object cannot enter that set merely by using a similar name.

```json
{
  "protocol_version": 3,
  "phase": "catalog_locked",
  "identity": {
    "session_user": "autodata_schema_probe", "current_user": "autodata_schema_probe",
    "database": "autodata", "server_version_num": 170000,
    "transaction_read_only": true, "default_transaction_read_only": true,
    "isolation": "repeatable read", "client_addr": null, "client_port": null
  },
  "rights": {
    "login": true, "superuser": false, "create_db": false, "create_role": false,
    "replication": false, "bypass_rls": false, "inherit": false, "membership_count": 0,
    "connect": true, "schema_usage": true, "ledger_select": true, "ledger_maintain": true,
    "other_maintain": false, "database_create": false, "database_temp": false,
    "database_owner": false, "schema_create": false, "schema_owner": false,
    "relation_owner": false, "sequence_owner": false, "relation_write": false,
    "column_write": false, "sequence_write": false
  },
  "relation": {
    "oid": 1, "schema": "public", "name": "schema_migrations", "kind": "r",
    "persistence": "p", "heap_builtin": true, "owner": "autodata_schema_owner",
    "owner_login": false, "is_partition": false, "has_inheritance": false,
    "rls": false, "force_rls": false, "rule_count": 0, "trigger_count": 0,
    "dropped_user_column_count": 0, "toast_builtin_safe": true
  },
  "columns": [
    {"attnum": 1, "name": "version", "type": "pg_catalog.text", "not_null": true,
     "generated": "", "identity": "", "collation_safe": true},
    {"attnum": 2, "name": "applied_at", "type": "pg_catalog.timestamptz", "not_null": true,
     "generated": "", "identity": "", "collation_safe": true}
  ],
  "indexes": {
    "count": 1, "primary_version_only": true, "valid": true, "ready": true,
    "live": true, "unique": true, "immediate": true, "include_count": 0,
    "has_expression": false, "has_predicate": false, "has_exclusion": false,
    "btree_builtin": true, "text_ops_builtin": true, "collation_safe": true,
    "support_inventory_count": 1, "support_inventory_matches_baseline": true
  },
  "builtins": {"heap_identity_matches": true, "btree_identity_matches": true,
    "text_identity_matches": true, "timestamptz_identity_matches": true,
    "text_ops_family_matches": true, "operators_and_support_match": true}
}
```

Only relation.oid, identity.server_version_num and indexes.support_inventory_count vary; the latter is integer1..32 and must equal the pristine baseline's count. The illustrative attnums1/2 are fixed: a reordered ledger fails. `relation_write` excludes only this exact target's deliberately allowed MAINTAIN, retaining all other forbidden privilege tests; `other_maintain` covers every other non-system relation. Primary-key column checks cover both conkey and indkey, indnkeyatts=1/indnatts=1 and no extra indexes. Existing ledger layouts that differ fail without automatic repair. A false derived boolean rejects; there is no default truth or empty-inventory success.

Ledger frame has exactly `protocol_version:3`, `phase:'ledger_locked'`, `count` (integer0..257), `overflow` (bool), `invalid` (bool), and `migrations` (array of0..256 safe ASCII strings, or null only when invalid/overflow). Success requires overflow=false, invalid=false, count=len(expected_versions)=len(migrations), and exact sorted versions. Error frames carry no row values. The module's success receipt has only the six keys specified above; exceptions have fixed type/message and no raw server payload. `transport.close()` must validate the fixed terminal marker, clean client exit and closed transaction or raise; merely closing a file descriptor is insufficient.

### Bounded ledger phase and lifecycle

Only after catalog acceptance, send a constant query selecting `version` from `ONLY public.schema_migrations` in a MATERIALIZED subquery with `LIMIT 257` before any aggregate/sort. Cap each value before JSON output using built-in octet_length and CASE; only ASCII inventory-shaped values <=128 bytes may enter `migrations`, otherwise return invalid=true without raw rejected bytes. Sort the bounded safe versions with explicit pg_catalog."C"; output count, overflow, invalid and migrations in one exact phase=`ledger_locked` v3 JSON object. At most256 expected rows; row257 is overflow and rejects without a matching receipt. Compare the exact version set and count against the approved manifest in Python; no manifest-derived SQL. No unbounded json_agg/string_agg, full-table count or prevalidation ORDER BY. This proves only the ledger inventory; it does not attest other table definitions or effective HBA/data paths.

Per phase stdout cap524288 bytes, chunk4096, total SQL stdout1048576, stderr discarded from client receipts, per-write cap65536, total outbound262144, monotonic whole-probe deadline12s, statement2s, lock1s, idle-in-tx5s, cleanup/reap1s. Strict UTF8 single JSON frame plus LF, duplicate/unknown/missing keys, arrays outside declared columns/indexes/migrations, maximum nesting8, maximum object members64, numeric canonical unsigned integers <=10digits, bool-as-int, nonfinite/oversized/truncated/extra frames all reject. No caller text appears in errors. No other frame can authorize transition. Partial writes/EOF/server cancellation/extra output reject and suppress ledger bytes.

On ledger success or rejection send only ROLLBACK; require a fixed client terminal marker outside the SQL transaction and clean exit before success. Marker is module-owned, never server/application text. If the pipe cannot be written safely, close it, bounded terminate/kill/reap the owned psql, and observe server-side idle timeout. Harness independently checks pg_stat_activity/pg_locks as fixture administrator for zero remaining probe sessions/ledger locks after the5s idle bound plus2s observation margin. A killed frontend does not itself prove remote cleanup. Cleanup failure returns no success evidence and the fixture server is stopped in finally. Production code receives no transport or new grants in this milestone.

## Task1: Fixed protocol with pure red/green transport tests

Files: create schema_probe.py and test_schema_probe.py.

- [ ] Write `test_no_ledger_bytes_before_catalog_acceptance`, `test_lock_is_before_first_select`, `test_invalid_catalog_aborts_without_ledger`, `test_no_reconnect_or_commit`, `test_valid_ledger_requires_rollback_and_exit`, `test_each_field_mutation`, `test_every_stream_bound` and `test_public_column_maintain_privileges`; a fake transport records byte-for-byte writes and refuses every unexpected SQL literal.
- [ ] Run `python3 -m unittest discover -s infra/deploy/gce -p test_schema_probe.py -v`; retain the initial missing-module failure as red evidence.
- [ ] Implement the minimum module/state machine and fixed catalog/ledger literals for the above contract. Expose no CLI or runtime import registration. Require the exact immutable fixture response fields in unit fixtures; no v2/v1 compatibility fallback.
- [ ] Rerun focused pure tests and existing `test_host_runtime.py`; all existing v2 no-ledger/schema-false tests must remain green. Commit and push this coherent milestone after checks; no claim of actual PG17 execution yet.

## Task2: Actual PG17 hostile execution and concurrency harness

Files: create test_schema_probe_pg17.py, testdata/schema_probe_sentinel.c and testdata/schema_probe_fixtures.sql. No Dockerfile, image pull/build or existing implementation edits.

The explicit harness invocation is `AUTODATA_SCHEMA_PROBE_PG17=1 AUTODATA_PG17_ROOT=/approved/local/pg17 python3 -m unittest discover -s infra/deploy/gce -p test_schema_probe_pg17.py -v`. The root is an operator-supplied local toolchain directory, not a production connection: require postgres/initdb/pg_ctl/psql/pg_config major17, matching version strings, local compiler and matching headers; hash binaries/header version/module/source into the receipt. Missing tools or extension compilation fails the explicit run with a blocking prerequisite receipt and nonzero exit, never skip/pass. Default unit discovery may skip actual server startup unless the explicit opt-in is present; such skips never count toward harness acceptance.

Run as a non-root OS account. initdb creates a fresh owned temporary cluster, socket0700, no TCP, no existing PGDATA/DSN. The harness compiles the C sentinel with local `pg_config --includedir-server`, `cc -shared -fPIC`; no network. It loads absolute module paths only in fixture SQL through its owned admin connection. The module exports PG_MODULE_MAGIC plus sentinel wrappers for table AM (`heap_tableam_handler`), index AM (`bthandler`), FDW handler, custom type output, and an immutable text expression/predicate function. Each emits a fixed WARNING marker `AUTODATA_PROBE_SENTINEL:<kind>` into the fixture server log before delegation/error; do not use network/files/external services as sentinels. Clear the observation offset after fixture setup so CREATE INDEX/type/FDW preparation cannot count as observer execution. A negative control deliberately invokes each path and asserts its marker; then reset the offset and run the observer. RLS uses the same warning helper. A view expands to a sentinel SELECT. Each real sentinel control must be positive or its rejection case is invalid evidence.

- [ ] Red: run the harness test suite against a deliberately unsafe test-local client that reads before catalog validation; view/FDW/RLS/type/AM/index/predicate sentinel controls must fail. Never import or merge c51d637 to obtain the red path.
- [ ] Green baseline: actual role is not owner, has no memberships, SELECT-only control cannot take SRE, MAINTAIN control can take SRE in READ ONLY. Valid heap/text/btree ledger yields exact inventory receipt and zero sentinel markers; all forbidden DML/other-table MAINTAIN remain denied. autodata_metrics retains SELECT-only behavior.
- [ ] Green hostile matrix: view, foreign table, partition/inheritance, RLS and FORCE RLS, custom type/domain/output, custom heap AM, custom index AM, extra expression/predicate/invalid index, custom opclass/support function/collation, altered version/applied_at shape, trigger/rule, missing role/rights, database/schema/relation owner, inherited privilege, PUBLIC write/MAINTAIN, column writes. Each rejects before any ledger bytes and produces zero observation sentinel markers; catalog-role mismatch and LOCK failure are separate rejection paths.
- [ ] Green value matrix: empty/missing/extra/duplicate migration,256/257 rows, over128-byte and invalid ASCII/version strings, wrong manifest version, JSON/framing/capture/timeout/pipe faults. No rejected row/log content appears in receipts. Actual DB tests exercise data bounds; fake tests exercise malformed server frames.
- [ ] Concurrent DDL with two admin connections and deterministic barriers (pg_locks/pg_stat_activity, finite polling/deadlines, no timing-only sleeps): hold writer or index DDL before probe LOCK, commit a hostile index, release barrier; first catalog snapshot must see/reject it. Once probe SRE is held, ordinary CREATE INDEX, CREATE INDEX CONCURRENTLY, REINDEX CONCURRENTLY, ALTER TYPE/RLS, DROP/recreate/rename relation and ledger INSERT must wait or hit1s lock_timeout. Ledger read cannot race an accepted index change. After probe ROLLBACK each queued controlled operation can complete. Test safe OID changes before lock and no snapshot-before-lock bug. Preserve failed race attempts.
- [ ] Lifecycle: kill local client after LOCK and after catalog; kill frontend transport without server termination; statement cancellation, lock timeout, short writes, invalid frame, EOF, process reuse attempt and containerless identity mismatch all suppress success. Within idle5s+margin2s independently observe zero probe sessions/locks. Stop server and remove only the exact owned temporary tree in finally; failed cleanup is failure.
- [ ] Preserve PG17 version/tool/source hashes, exact commit, case IDs, sentinel-control offsets/counts, SQL hashes/order, lock barriers and cleanup observations in bounded redacted JSON under an explicitly supplied owned temporary evidence directory. No credentials, DSNs, raw customer/source data, arbitrary SQL exception text or log dump enters receipts.
- [ ] Run both focused suites and existing host runtime suite, syntax/`git diff --check`, exact five-path diff and pinned gate preflight; commit/push. Obtain independent exact-SHA review before coordinator integration. Actual test results remain unverified until run; this plan is not their evidence.

## Release path after this capability

This milestone only proves a disposable ledger protocol. Later independent synchronized gates must (1) approve production probe ownership/MAINTAIN, effective socket HBA/ident and secret/config protection; (2) integrate the reviewed protocol/transport with validated Docker container identity and real staging cleanup evidence; (3) attest full application schema and service/no-work/runtime checks rather than promoting a ledger match; (4) prove actual authenticated release publisher/archive transport, manifest/image/migration integrity; (5) verify immutable full paid12/browser DTO120/API21/R6 inventories, Firebase, Stripe TEST $20 exact access, both banks, one-time rewrite and permitted source fallback; (6) prove backup/restore, reboot, alerts and TLS; then obtain specific production/cloud/payment/DNS approval for cars.tk cutover and post-deployment evidence. Historical fake archive consistency is not authenticated provenance. No production readiness or deployment authority follows from a passing harness.

## Concrete todo record

- [ ] Synchronize this exact harness goal, privilege decision, five-path implementation allowlist, tests and release limits in Issue186/Project8 and canonical documents; commit/push and pass pinned preflight before independent coordinator gate review.
- [ ] Add failing pure transport/state-machine tests and implement the disconnected fixed-SQL schema_probe module with lock-before-snapshot catalog validation, bounded ledger framing and rollback-only cleanup.
- [ ] Build the local-only PG17 harness and C sentinels with a non-owner SELECT+MAINTAIN probe role and trusted NOLOGIN ledger owner; demonstrate every sentinel fires in an intentional negative control before testing observer rejection.
- [ ] Run actual disposable PG17 safe/hostile relation, index, privilege, concurrent DDL, first-snapshot and abandoned-session cases; retain red/green receipts, hashes and cleanup proof without running application services or contacting providers.
- [ ] Run focused regressions, scope/diff and exact-base preflight; commit/push a coherent candidate for independent exact-SHA review, keeping production grants, collector integration, authenticated publication, services, deployment and cars.tk cutover behind later gates.

## Plan-only verification and synchronization

The checkpoint records live Issue/Project readback in the dedicated JSON record. `status: synchronized` means matching tracking/documents, not independent plan approval or runtime readiness. Pin the full committed checkpoint SHA when invoking `scripts/autonomy/pre_implementation.py`; the repository validator checks record/document shapes and pinned-file existence, while separate live readback proves remote synchronization. The coordinator must independently review this policy choice and the precise five-path scope before dispatch. No implementation changes, PG17 startup, compilation, Docker, cloud, provider or DNS action occurred during planning.

Tracking synchronized by live Issue186 body/comment6618084753 and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference` readback at `2026-11-03T23:26:27.924126+00:00`. Exact goal, five todos and five-path scope match the full issue body/comment; the compact Project index links that comment and retains historical DTO/A/B/R6 references, with its previous text preserved verbatim there. Dedicated record stores SHA256 readback hashes. Independent checkpoint review remains pending; synchronized tracking does not authorize a builder or live operation.


## PG17 disposable runner route successor: plan-only

Goal: Prepare and independently freeze a disposable PostgreSQL17 Alpine runner for the exact disconnected schema-probe candidate, then permit only separately approved actual harness execution; preserve production runtime, grants and all readiness denials.

Canonical route plan: `docs/superpowers/plans/2026-11-03-workshop-schema-pg17-route.md`; task `docs/agents/tasks/2026-11-03-production-release/workshop-schema-pg17-route.json`; record `docs/agents/records/2026-11-03-workshop-schema-pg17-route.json`. Planning root `eddcf724028683dbb083191e4f8c42064b866bf0`; immutable harness source `54ab7dce19c36ce7ea3403259dd1ecc66bf323aa` on `codex/workshop-schema-probe`. The route plan supersedes only the earlier native-only/no-Docker/no-download test prerequisite: a cached official PG17.11 Alpine derivative may later acquire Python3/C toolchain in a bounded preparation stage after exact-gate independent review and coordinator approval. Source-image history/cache is insufficient; exact toolchain/package/image/source identities require independent artifact review before a separately authorized network-disabled disposable harness run. No tracked implementation changes or integration are allowed by this route. Native hostPG18 cannot replace PG17. Preparation and actual harness are unexecuted; production grants/collector/services/readiness remain unchanged and unavailable.

Concrete todo:

- [ ] Synchronize the PG17 route decision, exact source/base pins, staged authority and concrete todo in Issue186/Project8 and canonical documentation; commit/push and pass exact-checkpoint preflight for independent review.
- [ ] After coordinator approval only, prepare the cached-digest Alpine derivative with Python3 and a C compiler; retain package versions, APK hashes, build inputs, base identity and immutable image identity with private tmpfs covering inherited PGDATA, verified mount inventory and exact-owned cleanup; do not start PostgreSQL.
- [ ] Independently inspect the frozen runner artifact and exact harness54ab source archive, verify matching PG17 tools/headers, ICU and non-root identity, then obtain separate exact-image execution authorization and re-pin the adopted gate.
- [ ] Only after the execution boundary is approved, run the unchanged complete PG17 adversarial harness in one network-disabled disposable container with private PGDATA tmpfs and verified mount inventory; retain every failure, sentinel control, case inventory and server/session/lock/container cleanup receipt.
- [ ] Independently review exact source/image/raw evidence before accepting any disposable-harness result; fail closed on missing prerequisites or cases and keep production grants, runtime integration, services, deployment and readiness unavailable.

Tracking synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6619358812 and Project8 readback at `2026-11-04T00:44:26.593707+00:00`; dedicated record retains SHA256 hashes and the complete prior Project index is preserved verbatim in that comment. Independent plan review pending; preparation and actual harness remain unexecuted and unauthorized.


PG17 route inherited-volume review correction (plan-only): the pinned official base declares `VOLUME /var/lib/postgresql/data`. Every later preparation/acquisition/inspection/execution container must override that exact path with private bounded tmpfs (`rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000,mode=0700`), retain complete mount inventory before payload start and cleanup/absence proof afterward, reject unexpected anonymous/named volumes, and remove only exact-owned containers/volumes. Build sandbox cleanup must also be demonstrated; inability blocks preparation. The harness cluster remains under private `/tmp`; Docker cleanup does not substitute for server/session/lock cleanup evidence. Canonical corrected plan/task/record: `docs/superpowers/plans/2026-11-03-workshop-schema-pg17-route.md`, `docs/agents/tasks/2026-11-03-production-release/workshop-schema-pg17-route.json`, `docs/agents/records/2026-11-03-workshop-schema-pg17-route.json`. Independent corrected-checkpoint review remains pending; no preparation, image build, PostgreSQL/container execution, implementation modification or readiness claim.

Corrected PGDATA route tracking synchronized by https://github.com/lucronn/autodata/issues/186#issuecomment-6621014641 and Project8 readback at `2026-11-04T02:36:36.976288+00:00`; exact hashes in dedicated record. Independent review pending; all execution remains unexecuted.
