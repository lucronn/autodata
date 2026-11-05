# Production outbox relay verification — 2026-11-05

Issue: https://github.com/lucronn/autodata/issues/303
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-05-production-outbox-relay.md`

## Exact candidate and boundary

Implementation branch `codex/production-outbox-relay-code`, worktree
`/home/corp/.codex/worktrees/production-outbox-relay-code/autodata`.
First wiring milestone `65867aae6731695fe71275fcae173ed8a75527c1` and real-smoke
milestone `e8473a792e86d7b19f7b2de2e22bc35b3c1cf5b3` are committed and pushed.
Lifecycle milestone `8f3735820670a027e2237c62bf2b85dcb94f0cd3` is the final
locally tested implementation candidate. All three descend from planning receipt `e5cb6775bb56621a7898a53dee743c323de9571e`.
Before the first implementation edit the builder independently read Issue #303,
its Project Ready item `PVTI_lAHOCSJ8cc4BiQ2BzhGO9Go` and ran:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-production-outbox-relay.json --base-sha a13cf0879d3551eec23c119829c7993b6b5bd6de --repo-root /home/corp/.codex/worktrees/production-outbox-relay-plan/autodata
```

Result: exit 0, `{"status": "synchronized", "errors": []}`.
The original implementation diff matched the approved 13 paths. The final
diff matches exactly the amended 15 implementation paths plus permitted gate
and evidence documents. JSON parsing, shell syntax and `git diff --check` pass.
No production service, existing database, provider or cloud endpoint was used.

## Local verification

- Focused runtime tests: 95 pass. Private-material tests: 38 pass.
- Outbox pytest: 10 pass and 4 subtests pass (`PYTHONPATH=packages/contracts/python python3 -m pytest workers/enrichment-python/tests/test_outbox.py -q`).
- Focused activation tests: 104 pass after the new tests failed against the old launcher.
- Full GCE suite: 433 tests, OK, 2 expected opt-in skips (existing PG17 protocol and the relay smoke, which was separately enabled below).
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
The final 6-test enabled suite passed in 11.976 seconds. It imported all three packaged
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

Sanitized raw local logs are retained durably under
`/home/corp/autodata-evidence/production-outbox-relay/`: `image-build.log`,
`real-smoke-final.log`, `gce-suite-amended.log`, `activation-red.log`,
`activation-green.log`, `outbox-pytest.log`, `governance.log`,
`repository-governance.log`, and `evidence-fixture.json`. `manifest.json` pins
the tested candidate, all 15 source hashes, image ID and each log SHA256.
The source/image packaging is unchanged by the later host-launcher changes;
the same built image was rerun after that fix. Both amended gate preflight
outputs are retained alongside the logs.

## Integration status and provisioning prerequisites

Independent review identified that `infra/deploy/gce/host_activation.py`
maintained a separate application list and eight-container bound. Work on that
file remained paused until docs-only scope amendment
`1f7ca55d5983899566c5e96240cbd5ba1717ab06` was adopted as exact builder base
`01ee4c43edcf8183341c33b1f8814c72528be3b2`. Before the two added paths were
edited, both the standalone record and task record preflights passed at that
exact base (`status: synchronized`, `errors: []`), and the builder read back the
Issue #303/Project #8 amendment. The old documentation conflict was resolved by
preserving both the existing evidence and new scope amendment.

The final launcher includes the relay in startup, orderly stop, failed-first
activation recovery and inventory. Its finite cap derives the exact nine-service
graph. Regressions reject missing/stopped relay maintenance, duplicate IDs,
duplicate service names, foreign services and a tenth container while preserving
existing maintenance-first and security checks. The local integration gap is
resolved; independent final review is pending. Candidate CI run
https://github.com/lucronn/autodata/actions/runs/42008825298 was in progress at
evidence recording time; no CI success is claimed here.

Deployment must separately provision the nonowner/nonmember `autodata_outbox`
LOGIN, remove broad PUBLIC/inherited/column grants, apply its restricted SELECT
and delivery-column UPDATE grants, and deliver separate pinned publisher
credentials to the relay and private NATS config. Metrics/publisher usernames
must differ. Private directories remain mode500 and single-link files mode400,
with no Docker Config.Env credentials. The normal runtime graph requires a
running exact-image/command/network/mount/user relay; passive readiness does not
claim actual event delivery. No activation, merge or deployment follows from
this verification.
