# Workshop selector writable recovery verification

Goal: Diagnose and recover real Workshop selector persistence through a bounded identical-runtime replacement while preserving truthful provider completeness and disabled purchasing.

Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8. Plan docs/superpowers/plans/2026-11-14-workshop-selector-writable-recovery.md; record docs/agents/records/2026-11-14-workshop-selector-writable-recovery.json.

Status: planning/read-only evidence only. No Docker/service mutation or provider call by this worker. The coordinator owns #391 origin recovery and any separately dispatched runtime execution.

Read-only evidence: public origin502 at2026-11-14T23:13Z; Docker inactive; API restart loop on DB5432 refused. Persisted serving ingestion efdda4a448db has read-only PGOPTIONS, host networking, read-only rootfs/source bind, cap-dropALL, no-new-privileges, and unless-stopped restart. Docker data-root is /mnt/openfoam/docker. Running transaction and specific #401 failure remain unverified until origin recovery. Existing catalog_service source SHA256 is5fef4cb075e2efc87067f68ae21d0110d3bf5c20dfc6b3ed5923224be17ed10a, differing from master diagnostics. No provider is blamed and no selector completion is claimed.

Concrete todo:

- [ ] Verify restored Docker/DB, exact serving ingestion/source/database identities, read-only transaction behavior, private backup and protected-table baseline before mutation.
- [ ] If the serving ingestion alone forces read-only transactions, retain the original and create an identical replacement with only PGOPTIONS removed; verify structural equality, health, and rollback-only writes.
- [ ] Observe one 2024 US makes scope through the existing bounded selector hydration path and read durable coverage/results; retain truthful partial state and safe error classes.
- [ ] Record exact runtime identities, redacted evidence and remaining catalog/article/paid-access gaps; synchronize Issue401/Project8 and keep rollback available.

## Exact-base gate and restored-runtime diagnosis

Planning checkpoint `801ec43a2d51ed82a4ba0a2debda46699c12b0fd` was committed/pushed before runtime dispatch. `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-14-workshop-selector-writable-recovery.json --base-sha HEAD` returned `{"status":"synchronized","errors":[]}` there. Issue comment [6885729745](https://github.com/lucronn/autodata/issues/401#issuecomment-6885729745) and Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhH8cbE were read back and matched the bounded goal/todos.

After the coordinator restored Docker/DB/API under #391, serving container efdda4a448db was running. A Python connection created inside that exact container with its effective DB environment returned database/user autodata/autodata, default_transaction_read_only=on, transaction_read_only=on, pg_is_in_recovery=false. A rollback-only transaction attempted CREATE TEMP TABLE then INSERT and failed with error class ReadOnlySqlTransaction; finally rollback and close ran. An independent connection inside autodata-postgres-1 returned off/off/false. This proves client-enforced read-only persistence in the serving ingestion, but does not exclude additional provider failures after repair.

One public GET for2024 US makes returned200 with9 choices, complete:false and hydrating:true. A separate DB read still showed makes|2024|||US at completion_version0, selector_rows length0, updated2026-10-27T04:44:27.668942Z. Public /workshop/purchase-config.json returned enabled:false. No direct connector request or article/model operation was made by this worker.

Read-only inventory shows existing retained content: catalog_articles21614; catalog_article_vehicle_links21598; canonical_articles8275; canonical_article_revisions7; canonical_article_reviews0; source_fetch_jobs13; vehicle_provider_mappings0. These counts prove retained rows only. They do not prove accessible customer articles, usable vehicle mappings, published full-prose coverage, rights, or paid browser acceptance. Existing exact connector fallback may supply provider references; it was not exercised here.

Runtime replacement and its backup/protected-state checks remain with the coordinator. This worker has not changed any Docker/service/application/schema/provider/payment state.

## Prepared rollback evidence before replacement

Private directory /home/corp/autodata-evidence/selector-writable-20261114 is mode0700. The read-only preparation phase retained complete original inspect, exact replacement create payload, and18 protected-table fingerprints as mode0600 files. Custom-format DB backup before.dump is15,886,405bytes; SHA2568aa6a1098abff285f2c13adff9dfd4929985f6ced99a05cd2238fd00502783c6. pg_restore --list succeeded. Exact source container efdda4a448db093940f1d4a1d6a69b57f15584afc570d6433aaf0fd23a2b5e0c and image sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4 were verified before capture. Purchase remained disabled.

The private operational helper runtime_replacement.py was syntax-checked and sent to the coordinator for inspection before any runtime execution; SHA25646656fb051110fb6773865000b3ff0981c6e1bffc990a1e915a7292a084959cd. Exact create-payload SHA2569d470969d388a66c981b3b5fa9c471006e94712cb89a8eacbbb7dcb339894efb. Its separate prepare/replace/verify/rollback phases do not expose credentials. Replace requires unchanged original config/hostconfig and protected state, removes exactly PGOPTIONS, compares complete resulting Config/HostConfig/image/mounts before start, retains original and restarts it on create/diff/start failure. Verify requires health200, rollback-only temp write with DB settings off/off/notrecovery, disabled purchase and unchanged18 fingerprints. Rollback selects exact retained original and does not restore/delete DB data. Health/write verification failure requires coordinator rollback; the helper never treats starting a container as acceptance. No replacement has been executed by this worker.
