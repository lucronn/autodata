# Automatic rewrite prompt v2 builder verification

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-06-automatic-rewrite-prompt-v2.md`

Planning base `0e41da96acd58107ee8d035cd706777391e3c5ce` was pushed before implementation. The builder reran the machine preflight at that exact SHA: exit 0, `status: synchronized`, no errors. Implementation milestone `28f625b` adds only prompt construction and exact historical/current prompt-hash compatibility; validators, profile identity, renderer and technical grammar are unchanged.

## Evidence

- Baseline automatic rewrite tests: 12 passed.
- Four new prompt/compatibility tests failed before implementation (v2 identity/schema and historical helper absent), then passed after implementation.
- `PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_procedure_rewrite_auto.py workers/ingestion-python/tests/test_procedure_rewrite_full.py workers/ingestion-python/tests/test_procedure_rewrite.py workers/ingestion-python/tests/test_procedure_rewrite_v2.py -q`: **212 passed**.
- Historical `document("Remove the cover.")`, context `{}` prompt-v1 SHA256 was measured before edits and pinned independently: `cc5ef47228dc07abee81956adabf0de870247950fc3f5867ce6ed8b110f62e51`.
- Real PostgreSQL/HTTP/process fixture command below: **13 passed, 102 deselected**, no skips. It covers both banks' publication and zero-call warm/restart reuse; process death after model-result commit and inside publication for both v1/v2 saved hashes; forged matching attempt/candidate prompt hashes, source, response and model metadata rejection at saved validation and publication. Captured-context mutation is rejected by the existing database immutability trigger; original evidence remains valid. Unit tests separately reject hashes computed from changed source/context and modified v2 payloads.
- Broad local ingestion run excluding the lifecycle integration file: **1071 passed, 356 skipped, 148 subtests passed**, with two failures because system Python lacked `stripe`. Installing the repository-pinned `stripe==16.1.0` into isolated `/tmp/autodata-prompt-v2-python` and rerunning `test_stripe_adapter.py` produced **7 passed**. This is not a claim that the entire broad suite passed in a single run; skipped PostgreSQL cases are not counted as passing integration tests.
- `git diff --check`: passed.

## Isolated fixture command and recovery

The fixture used Compose project `autodata-prompt-v2`, the checked-in `infra/compose/compose.article-lifecycle-test.yaml`, and existing local image `autodata-source-projection-v2-test-runner:latest`. No application runtime was deployed.

An external `/tmp/autodata-prompt-v2-compose.yaml` override selected that image and mounted SeaweedFS `/data` as a 1 GiB tmpfs. The override was necessary because the host filesystem was 97.6% full: the first rerun had nine setup errors (`S3 InternalError`, no writable volumes) and four passes. Only this owned fixture stack/volumes were removed and recreated; no repository infrastructure change was made.

```sh
AUTODATA_LIFECYCLE_ARTIFACT_DIR=/tmp/autodata-prompt-v2-artifacts \
AUTODATA_R3_TEST_IMAGE=autodata-source-projection-v2-test-runner:latest \
AUTODATA_R3_CANDIDATE_SHA=28f625b \
docker compose -p autodata-prompt-v2 \
  -f infra/compose/compose.article-lifecycle-test.yaml \
  -f /tmp/autodata-prompt-v2-compose.yaml run --rm --no-deps test-runner \
  python -m pytest \
  workers/ingestion-python/tests/test_article_lifecycle_integration.py \
  workers/ingestion-python/tests/test_article_publication.py \
  -k automatic -q -p no:cacheprovider
```

Earlier test-authoring runs exposed fixture assumptions (the normalized document stores prose in nested lists, and captured context is immutable). Those tests were corrected without changing production validation. Final integration result was 13 passed in 37.93 seconds.

## Builder handoff boundary (historical)

Exact-SHA independent review and required CI remain coordinator responsibilities before integration. No licensed provider request, enrollment, queue drain, deployment or canary was performed. The exhausted frozen Bankone identity and Banktwo provider counters were not touched. The bounded fresh-identity canary in the plan remains pending coordinator dispatch; mechanical integrity does not prove semantic equivalence or an originality percentage.

## Verified fresh Bankone publication and permanent reuse, 2026-11-06

[PR350](https://github.com/lucronn/autodata/pull/350) merged as `b3618fb6e68f1734ef029096748e30e655451a26` after required CI passed. Its tree equals reviewed/runtime candidate `530d4cce9934336a66bf11940212b895c6c01728`. Runtime amendments were synchronized and machine-checked at `60fdc962a758ffc2b74c8786c652d91a939d4d62` before execution; the exact private one-shot script was independently approved before execution.

The fresh Bankone canary `8cc70d03-6794-577c-aba4-bd555996d0c9` published canonical revision `4b09c34b-46e4-4aee-a764-e7cba856583a` with one measured Mercury3 HTTP call. All9 eligible ordinary-prose leaves changed and none was retained. Existing strict mechanical validation passed, protected content remained bound to source, publication is automatic with `UNREVIEWED` metadata and no human review row. The exact fresh job completed with retry_count1/max_attempts1; the durable cap was reduced before source-only execution.

Ten warm read/ensure pairs and a separate fresh-process pair reused the same revision and content hash with measured source/media/model/scheduling/HTTP calls all zero. Frozen Bankone/Banktwo and unrelated queue/business fingerprints remained unchanged. The exhausted original Bankone job remains frozen on source fallback; no historical budget was reset. Checkout remains disabled. This verifies the bounded fresh prose-bearing Bankone canary and permanent reuse; mechanical checks do not certify semantic equivalence or an originality percentage, broad catalog readiness or paid launch.

Completed todo:
- [x] Preserve prompt-v1 bytes and exact reconstructed v1/v2 hash bindings; implement explicit v2 shape/action rules without validator relaxation.
- [x] Pass212 focused rewrite tests,13 real PostgreSQL publication/restart/binding cases, independent exact-candidate review and required CI.
- [x] Independently review the exact private driver, enforce the exact fresh-job cap before source-only run, and complete one persisted provider attempt.
- [x] Verify9/9 ordinary-prose changes, protected-content retention and warm10/fresh1 zero-call permanent reuse; preserve frozen/unrelated fingerprints.
- [x] Retain private backup, review/preflight/dispatch/warm/fresh receipts and synchronize sanitized outcome documentation.

Canonical evidence: `docs/verification/2026-11-06-automatic-rewrite-prompt-v2.md`. Private source references, licensed content, raw responses, credentials and backup bytes remain outside Git.

### Runtime evidence and limits

Private receipts: `amended-gate-preflight.json`, `runtime-review.json`, `backup-receipt.json`, `parked-result.json`, `dispatch-result.json`, `warm-result.json`, and `fresh-result.json` under the coordinator-owned evidence directory. The gate receipt verifies exact SHA60fdc962a758ffc2b74c8786c652d91a939d4d62 with exit0/status synchronized/errors[]. The review approved exact script SHA256 `d6446c28eca8f21328857bec986f3c24770b7608036a7af1dd5beb2bf787ad64`. The dispatch/warm/fresh receipts agree on the canonical revision and document SHA256 `f9209382442df60b84c1057295e6a8c7380a1353218f5dc6daad35d4dbf91e92`. Warm and fresh-process receipts separately record all five call counters as zero.

Required check “Validate autonomy policy and evidence contract” passed at [CI run42287416076](https://github.com/lucronn/autodata/actions/runs/42287416076). This docs follow-up imports the already-approved runtime amendments and records the completed operation; it does not authorize another provider attempt or enrollment. Previous failed frozen-job receipts remain historical failures.
