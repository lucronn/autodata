# Compatible Workshop catalog runtime rollout

Goal: Deploy a compatible, exact-source catalog ingestion runtime on loopback3031 so real Workshop selectors persist truthful dual-bank completion, preserving article/commerce behavior and disabled purchasing.
Issue https://github.com/lucronn/autodata/issues/401
Project https://github.com/users/lucronn/projects/8
Canonical receipt docs/verification/2026-11-14-workshop-compatible-catalog-runtime.md
Record docs/agents/records/2026-11-14-workshop-compatible-catalog-runtime.json

## Exact scope and decision

The prior writable repair passed but old e4af862 _persist_hydration_scope cannot write selector_rows/completion_version expected by newer API. Serving DB already records migration042_catalog_selector_rows and both required columns. Do not manually fabricate completion or run migrations on the serving DB.

Stage a new private immutable source tree copied byte-for-byte from /home/corp/autodata-candidate/grant-ready-e4af862/source. Replace only workers/ingestion-python/src/autodata_ingestion/catalog_service.py and source_connector_client.py with exact merged commit61f1939c04b41cf6082c3361f34424e0cd9c599e blobs. These two modules include merged#363 dual-bank/sparse persistence, #364 Banktwo proved-label retry, #366 complete-parent absence, and#405 safe-stage logs. They are unchanged in subsequently fetched master. Hash every regular source file before/after and require exactly these two changed paths with no additions/deletions; runtime image remains sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4. Preserve all article/commerce/source bytes outside those modules. Do not edit either merged module, add dependencies, expand application scope or update the live source tree.

## Offline build and compatibility acceptance

After synchronized committed-base preflight, create the candidate tree and a separate test harness from exact61f1939. Run unittest catalog_service, source_connector_client, selector_deepening and http_service against the candidate modules using the actual runtime image with --network none, no published ports, no serving environment or credentials, and read-only candidate mount. Current tests may be mounted separately with their sibling src resolving to candidate production src. Use existing pinned test-runner sha256:35fd9a5c9f8249b424a4a97f0a3d691ef3705f718d49bdc9a775f349a3f88be7 for pytest integration only. Create an isolated internal Docker network and disposable PostgreSQL image sha256:151aa1c2e849e7828ed8aef2183ae15f692cbe887d2f28921d8b44b26e154d7e with fixture-only credentials and a disposable volume; no host ports or serving data/backup mounts. Run current sparse selector persistence tests using existing isolated lifecycle fixtures with candidate src and exact current migration/test harness; assert version0 upgrade, durable selector rows, all-provider completion, partial semantics and successful module imports. Stop at test failure rather than editing merged code. Remove only task-created test resources after recording logs, or retain stopped for inspection; never touch existing resources.

## Coordinator rollout boundary

Worker may build/test and prepare read-only manifests/backups but may not mutate live ingestion/services. Coordinator captures current writable container7ce6c5a98bec configuration, exact source/image/DB identity, disabled purchase, a new mode0600 custom-format DB backup with pg_restore-list/hash, and18 protected fingerprints plus optional wider independent baseline. Verify DB42 columns and effective writes; require immutable candidate manifest hashes before dispatch.

Create one new candidate container with identical effective Config/HostConfig/image/env/command/user/security/network/restart settings except container name and the /app read-only bind mount source now pointing at the candidate tree. Do not change credentials, ports, image, PGOPTIONS, purchase/model/source settings or any other mount. Complete raw comparison must permit only exact changed mount-source paths; preserve original grant-ready and current writable containers for rollback. OomKillDisable remains false as in current writable runtime; do not add broader normalization exceptions. Stop/retain current writable runtime only after full checks, then start candidate. On failed create/start/health/write checks stop candidate and restart retained writable runtime; never auto-restore/delete DB data. Health must be200, DB off/off/notrecovery with rollback-only temporary write, purchase disabled, protected fingerprints unchanged. Record safe stage/error-class logs only; never raw provider URLs, exceptions or content.

After coordinator dispatch, use one bounded public2024USmakes GET and independent durable scope read after at most30seconds; no direct connectors, manual provider retry, broad traversal, article/model/worker action or fabricated completeness. Existing source connectors/deepening retain their reviewed deadlines and budgets; report available aggregate source-request evidence without inventing a ceiling. A representative deeper cascade needs a separately stated bounded selection if makes completes. Protected commerce/customer/article state must remain unchanged. Keep Issue401 open unless real cascade acceptance is shown. Source rights, paid/test settlement, article publication, DNS and public launch remain independently unproven.

## Concrete todo

- [ ] Freeze current writable serving runtime and DB schema42 evidence; stage an immutable original-source copy with only two exact merged catalog modules replaced and audit complete source hashes.
- [ ] Run offline runtime-image catalog/connector/deepening tests and isolated PostgreSQL sparse-selector persistence/upgrade tests without serving credentials or provider access.
- [ ] Prepare a private backup/protected baseline and exact retained-runtime rollout/rollback manifest; coordinator alone replaces source mount after complete Config/HostConfig/image comparison.
- [ ] Verify runtime health/writes/protected state and one bounded real2024US selector observation through public API; record truthful partial state or completion and remaining article/paid-access gaps.
