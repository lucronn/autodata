# Production outbox relay verification — 2026-11-05

Issue: https://github.com/lucronn/autodata/issues/303  
Project: https://github.com/users/lucronn/projects/8  
Plan: `docs/superpowers/plans/2026-11-05-production-outbox-relay.md`

## Exact candidate and boundary

Implementation branch `codex/production-outbox-relay-code`, worktree
`/home/corp/.codex/worktrees/production-outbox-relay-code/autodata`.
First wiring milestone `65867aae6731695fe71275fcae173ed8a75527c1` and real-smoke
milestone `e8473a792e86d7b19f7b2de2e22bc35b3c1cf5b3` are committed and pushed.
Both descend from planning receipt `e5cb6775bb56621a7898a53dee743c323de9571e`.
Before the first implementation edit the builder independently read Issue #303,
its Project Ready item `PVTI_lAHOCSJ8cc4BiQ2BzhGO9Go` and ran:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-production-outbox-relay.json --base-sha a13cf0879d3551eec23c119829c7993b6b5bd6de --repo-root /home/corp/.codex/worktrees/production-outbox-relay-plan/autodata
```

Result: exit 0, `{"status": "synchronized", "errors": []}`.
The implementation diff against the receipt matches exactly the approved 13
implementation paths. JSON parsing, shell syntax and `git diff --check` pass.
No production service, existing database, provider or cloud endpoint was used.

## Local verification

- Focused runtime tests: 95 pass. Private-material tests: 38 pass.
- Outbox pytest: 10 pass and 4 subtests pass (`PYTHONPATH=packages/contracts/python python3 -m pytest workers/enrichment-python/tests/test_outbox.py -q`).
- Full GCE suite: 418 tests, OK, 2 expected opt-in skips (existing PG17 protocol and the relay smoke, which was separately enabled below).
- Autonomy suite: 146 tests, OK. Repository governance: 9 tests, OK.
- Deterministic evidence fixture: passed, 8 required gates, no failures.
- Failing packaging/graph/manifest/ACL/grants/authentication/redaction regressions were observed before implementation; corresponding focused suites pass afterward.

The complete host suite used the workflow's numeric identity and sanitized
required mode without weakening wrapper checks:

```sh
sudo -n /usr/bin/setpriv --reuid=1000 --regid=1000 --clear-groups /usr/bin/env -i HOME=/tmp/autodata-outbox-evidence TMPDIR=/tmp PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 AUTODATA_REQUIRE_PURCHASE_CONFIG_DELIVERY_COMPOSE=1 /usr/bin/python3 -B -m unittest discover -s infra/deploy/gce -p 'test_*.py'
```

The actual ingestion Dockerfile was built from the candidate source:

```sh
tar -cf - workers/ingestion-python/Dockerfile workers/ingestion-python/pyproject.toml workers/ingestion-python/src workers/enrichment-python/src packages/contracts/python scripts/dev infra/deploy/gce/runtime-entrypoint.sh | docker build -f workers/ingestion-python/Dockerfile -t autodata-outbox-relay-smoke:production -
AUTODATA_OUTBOX_RELAY_SMOKE=1 AUTODATA_OUTBOX_SMOKE_IMAGE=autodata-outbox-relay-smoke:production python3 -m unittest discover -s infra/deploy/gce -p test_host_outbox_relay.py -v
```

Built local image: `sha256:887ea92dc348d6c94cc99bc0262156de9954ad7a9c1d7fbc722004727a3a663a`.
The 6-test enabled suite passed in 12.121 seconds. It imported all three packaged
Python modules and ran relay `--help`, applied the repository migration runner
output and provisioning-only grants to disposable pgvector/PostgreSQL17,
inserted valid constrained canonical article/source/transform/event lineage,
and executed the packaged relay through its hosted wrapper as UID/GID1000.
It observed the real AUTODATA_CATALOG JetStream message and published database
status, then replayed the original row and verified one stored message with the
original envelope `idempotency_key` and `Nats-Msg-Id`. Metrics publication,
publisher unrelated publication and stream deletion, and database canonical
writes/INSERT/DELETE all failed with actual permissions errors. Stopping the
broker left the pending row readable, with no delivered timestamp or claim.
Synthetic observer credentials exist only in the disposable test broker. Its
metrics/publisher permission blocks retain the production template's exact ACL.
All fixture containers, anonymous volumes and the private network were removed.

Raw local logs are retained under `/tmp/autodata-outbox-evidence/`:
`image-build.log`, `real-smoke.log`, `gce-suite-final.log`, `outbox-pytest.log`,
`governance.log`, `repository-governance.log`, and `evidence-fixture.json`.

## Integration status and provisioning prerequisites

Independent review of the candidate identified that
`infra/deploy/gce/host_activation.py` maintains a separate application list and
launcher path that also needs the relay. That path is outside the initial
13-file allowlist. Implementation is paused pending a synchronized scope
amendment; the current candidate alone does not complete host activation.
GitHub CI run https://github.com/lucronn/autodata/actions/runs/42008323408 was
in progress at evidence recording time; no CI success is claimed here.

Deployment must separately provision the nonowner/nonmember `autodata_outbox`
LOGIN, remove broad PUBLIC/inherited/column grants, apply its restricted SELECT
and delivery-column UPDATE grants, and deliver separate pinned publisher
credentials to the relay and private NATS config. Metrics/publisher usernames
must differ. Private directories remain mode500 and single-link files mode400,
with no Docker Config.Env credentials. The normal runtime graph requires a
running exact-image/command/network/mount/user relay; passive readiness does not
claim actual event delivery. No activation, merge or deployment follows from
this verification.
