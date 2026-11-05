# Production Outbox Relay Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task after exact-base preflight and coordinator dispatch. Planning does not deploy the service.

**Goal:** Wire the existing publication outbox relay into the production GCE host graph with packaged code, dedicated PostgreSQL/NATS credentials, restricted broker permissions and fail-closed runtime verification.

**Architecture:** Reuse the ingestion image and existing enrichment relay; add one backend-only process. Give it a dedicated database identity and NATS publisher identity. Extend existing declarative host contracts and verification, preserving delivery leases, retries, idempotency and all release guards.

**Tech Stack:** Python, PostgreSQL, NATS JetStream, Docker Compose, stdlib host tests.

**Spec:** `docs/architecture/independent-bank-connectors.md`, publication lifecycle.

**Source baseline:** `c0be267fe31dc578bec0b8528679b6fd6671ed12` (`origin/master`).
**Issue:** https://github.com/lucronn/autodata/issues/303 (child of #186).
**Project:** https://github.com/users/lucronn/projects/8
**Record:** `docs/agents/records/2026-11-05-production-outbox-relay.json`

## Evidence and boundary

At the source baseline, development `infra/compose/compose.yaml:266` declares `outbox-relay`, while production `infra/compose/compose.production.yaml` and `runtime-check.py` NORMAL_SERVICES omit it. Canonical publication documentation requires a separate relay. The ingestion image omits the enrichment package and relay script. Production NATS authorizes only its metrics user for `$JS.API.INFO`; simply starting a relay would fail authentication/publication. These are repository facts, not a live-host observation.

This work permits repository implementation and isolated test infrastructure after dispatch. No live host, cloud, credentials, provider, payment, service activation, deployment, merge or DNS operation follows. Provisioning actual identities/passwords and installing private NATS config remain separately authorized deployment prerequisites. Do not alter application publication transactions, projection contracts, source capture or browser behavior. Do not weaken existing host ownership, mount, cached-image, metadata, no-work or readiness checks.

## Intended implementation allowlist

- `infra/compose/compose.production.yaml`
- `infra/deploy/gce/runtime-check.py`
- `infra/deploy/gce/runtime-entrypoint.sh`
- `infra/deploy/gce/release.schema.json`
- `infra/deploy/gce/private_material.py`
- `infra/deploy/gce/nats.conf.template`
- `infra/deploy/gce/runtime-grants.sql`
- `infra/deploy/gce/test_host_runtime.py`
- `infra/deploy/gce/test_private_material.py`
- `infra/deploy/gce/test_host_outbox_relay.py`
- `workers/ingestion-python/Dockerfile`
- `workers/enrichment-python/src/autodata_enrichment/outbox.py`
- `workers/enrichment-python/tests/test_outbox.py`

Planning/evidence updates may touch this plan, its record, `docs/architecture/independent-bank-connectors.md` and new `docs/verification/2026-11-05-production-outbox-relay.md`. Any other implementation file requires coordinator review and a synchronized scope amendment before editing.

## Concrete todo

- [ ] Add failing relay packaging, render/topology, secret-contract, NATS authentication/ACL and runtime graph/readiness regressions.
- [ ] Package the existing relay in the ingestion image and wire its dedicated backend-only service, credentials, manifest/private-material contract and narrowly scoped database/broker privileges.
- [ ] Run focused and complete host regressions plus an isolated real PostgreSQL/NATS relay smoke proving canonical event delivery, replay identity and denied unrelated permissions; retain exact candidate evidence.
- [ ] Commit and push validated milestones, independently review the exact candidate, and synchronize Issue/Project/canonical documentation with verification evidence; deployment remains a separate decision.

## Task 1: Wire the smallest working relay

- [ ] First add failing cases in host runtime/private-material tests and enrichment outbox tests for each contract below. Add `test_host_outbox_relay.py` for narrow SQL/ACL/packaging assertions and the opt-in isolated real-service smoke. Observe expected failures before implementation.
- [ ] In the existing ingestion Dockerfile, copy `scripts/dev/outbox_relay.py` to `/app/scripts/outbox_relay.py` and the enrichment source tree to `/app/enrichment-src`; append `/app/enrichment-src` to existing PYTHONPATH without replacing ingestion/contracts paths. Existing ingestion dependencies already include psycopg and nats-py; add no new image role or dependency.
- [ ] Add `outbox-relay` to production Compose by copying the existing application hardening/logging/tmpfs conventions. Use IMAGE_INGESTION, UID/GID1000, wrapper entrypoint, command `['python','/app/scripts/outbox_relay.py','--poll-seconds','5','--batch-size','50','--max-attempts','3']`, no ports, no workers-egress, backend address `172.30.20.14`, read-only `/run/autodata/outbox-relay` bind with create_host_path false; depend on healthy postgres and started nats. Migration remains the launcher's separately enforced schema prerequisite. No data/source mount or side-effecting healthcheck.
- [ ] Update NORMAL_SERVICES, TOPOLOGY backend addresses, COMMANDS, both image-role mappings, `_service_environments` and host inspection/test fixture mappings. Relay environment uses AUTODATA_ENV/public origin conventions, DB address `postgres:5432`, database `autodata`, user `autodata_outbox`, runtime service `outbox-relay`, NATS URL `nats://nats:4222` and the three explicit bounded tuning defaults above. Do not give it provider/S3/Stripe credentials or egress.
- [ ] Add relay secret tuple `('AUTODATA_POSTGRES_PASSWORD','NATS_OUTBOX_USER','NATS_OUTBOX_PASSWORD')` consistently in runtime SECRET_NAMES, wrapper and private-material SERVICE_NAMES. Extend release schema with mandatory relay secret-version map and NATS server NATS_OUTBOX_USER/PASSWORD references. Enforce equal pinned user/password version references between relay and NATS; reject missing/extra maps and ambient aliases. Add new NATS names to wrapper ambient-credential rejection. Preserve per-service500 directories/400 single-link files, secret-free Docker Config.Env and redacted failures.
- [ ] Add a dedicated second NATS user in `nats.conf.template`, using `@@NATS_OUTBOX_USER@@`/`@@NATS_OUTBOX_PASSWORD@@`. Publish allowlist is the exact nine EVENT_SUBJECTS currently declared in outbox.py plus `$JS.API.STREAM.INFO.AUTODATA`, `$JS.API.STREAM.INFO.AUTODATA_CATALOG`, `$JS.API.STREAM.CREATE.AUTODATA`, `$JS.API.STREAM.CREATE.AUTODATA_CATALOG`; subscribe only `_INBOX.>`. Metrics user remains INFO-only. No wildcard management, consumer, purge, delete or unrelated publish permissions. Reject equal metrics/publisher usernames in private-file validation. Extend frozen NATS-template matching to all four tokens; this validates bytes without claiming server permissions were provisioned.
- [ ] Add an optional authentication adapter in enrichment outbox.py: when neither NATS_OUTBOX variable exists retain existing development behavior; if either exists require both nonempty, pass them as `user`/`password` arguments to nats.connect, never embed credentials in URL/error output. Hosted wrapper requires both. Return a fixed broker-unreachable status rather than raw connection exception text, preventing credential leakage. Preserve all claim/ack/failure/lease/stream/idempotency behavior. Test paired/missing credentials and sensitive exception redaction.
- [ ] Extend provisioning-only runtime-grants.sql for an already separately provisioned, nonowner/nonmember `autodata_outbox` LOGIN: revoke broad grants, grant CONNECT on autodata, USAGE public, SELECT publication_events and UPDATE only delivery_status, delivery_attempts, delivery_lease_owner, delivery_lease_token, delivery_lease_expires_at, last_delivery_error, next_delivery_at, delivered_at. No INSERT/DELETE, canonical-content modification, role creation/passwords/admin fallback. Existing role ownership/membership and PUBLIC/column grants must be audited at provisioning. Activation never executes this SQL.
- [ ] Make readiness observe the relay as a required normal service using existing exact image/command/network/mount/user/running checks; missing/stopped/drifted relay fails. A running process alone does not prove event delivery. Keep startup no-work validation read-only; real event creation belongs solely to isolated verification.
- [ ] Update canonical architecture and verification notes with the resulting service contract, required separate provisioning and exact tested candidate. Commit and promptly push the coherent validated milestone.

## Task 2: Verify and hand off

- [ ] Run focused tests: `python3 -m unittest discover -s infra/deploy/gce -p 'test_host_runtime.py'`, corresponding `test_private_material.py` and `test_host_outbox_relay.py`; run enrichment `test_outbox.py` with the project's existing test interpreter/PYTHONPATH. Host wrapper cases require numeric UID/GID1000; use the sanitized required-mode command already recorded in `.github/workflows/autonomous-verification.yml`, without weakening identity or skipping those cases.
- [ ] Run complete required GCE suite using the existing verification workflow command, repository governance checks, shell syntax, JSON parse, `git diff --check` and exact allowlist comparison. Changes to shared fixture expectations in allowlisted tests must preserve existing assertions.
- [ ] Run the new smoke against disposable local PostgreSQL/NATS services only, using synthetic credentials and the rendered publisher ACL. Apply repository migrations and provisioning grants, construct a valid canonical catalog.article.published outbox row, run the packaged ingestion-image relay once, read actual AUTODATA_CATALOG JetStream message and database published status. Assert original envelope idempotency_key and Nats-Msg-Id survive replay. Authenticate the metrics identity and show publication is denied; show publisher unrelated subjects/stream-delete denied and database canonical writes denied. Also prove broker outage leaves pending data readable and no delivered flag. Check packaged image can import autodata_ingestion, autodata_enrichment.outbox and autodata_contracts and run relay --help. Retain commands and raw pass/failure evidence; mocks do not count as actual delivery proof.
- [ ] If local Docker/required numeric-identity environment is unavailable, report that verification as blocked and do not claim runtime delivery success. Do not use production as a test target.
- [ ] Push exact implementation candidate and obtain independent review; synchronize child Issue and Project status/evidence, and update canonical verification document with exact SHA and honest local/CI results. No release or deployment follows automatically.

## Gate handoff

The planning-only checkpoint contains this plan, canonical document and synchronized JSON record. After commit, pin its full SHA externally in the child Issue, run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-production-outbox-relay.json --base-sha <full-checkpoint-sha> --repo-root <worktree>` and retain status synchronized/errors[]. The literal SHA is recorded in a following verification receipt to avoid a self-referential commit. Builder must use that exact base and read back the Issue/Project before its first implementation edit.
