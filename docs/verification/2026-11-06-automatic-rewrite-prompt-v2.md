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

## Remaining release boundary

Exact-SHA independent review and required CI remain coordinator responsibilities before integration. No licensed provider request, enrollment, queue drain, deployment or canary was performed. The exhausted frozen Bankone identity and Banktwo provider counters were not touched. The bounded fresh-identity canary in the plan remains pending coordinator dispatch; mechanical integrity does not prove semantic equivalence or an originality percentage.
