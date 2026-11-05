# Full article rewrite and review verification

Implementation candidate: `7c626bf72c1eff01226bf7c05cc8372d0673a8a3`
Planning checkpoint: `d7cef73bd38480640e8fc2b65f42994977459117` (merged as `5ce608c5ecb44ea6b820a7d2860e434c88a310fc`)
Tracking: [Issue #333](https://github.com/lucronn/autodata/issues/333), [Project #8](https://github.com/users/lucronn/projects/8), [PR #335](https://github.com/lucronn/autodata/pull/335)

## Scope and corpus boundary

The explicit `full-prose-review-v1` path drafts a source-bound introduction and every declared prose leaf, preserves protected structures, and stores a mechanically checked candidate. Source remains authoritative while a distinct human reviewer examines the complete source and candidate with exact hash bindings. Approval resumes the saved candidate without another model call, including exhausted-budget and unchanged-source refresh recovery. The existing v1/v2 profiles are unchanged.

The private selection manifest SHA-256 is `1b2dd359fee84a95fa06b5ea2181f87c625aa9224071eb40a85ab9451a41a4b0`. It freezes **40** retained authentic articles, **20 per bank**, with **20** preassigned held-out selections. The selection covered only the first article-list page for two predetermined vehicle selectors per bank; all four list pages report further cursors, so this is not the purchased-dataset denominator. Resource and envelope hashes matched all 40 captures. At the original bounded-profile baseline, **0/40** were v2 eligible; Banktwo's 20 captures had unsupported article media for that normalization path. Source bodies and private review exports are not in Git.

No real Mercury draft, independent human article approval, or publication of the 40 authentic articles is claimed. Synthetic fixture results below establish code behavior only. The intended full purchased-dataset scope and any newly discovered source families remain open.

## Gate and independent review

At the committed planning checkpoint, `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-full-article-review.json --base-sha d7cef73bd38480640e8fc2b65f42994977459117` returned `{"status":"synchronized","errors":[]}`. The Issue, Project item, plan and canonical architecture document were read back before dispatch and before PR creation.

Independent reviews approved the full-prose boundary, privileged review CLI, lifecycle publication/recovery, table-only publication fix, same-source refresh fix, fixture guard tests, and CI import-path fix. The final whole-branch review found and reproduced the refresh trap before its correction; the scoped re-review found no remaining Critical or Important issue in the fix.

## Exact-candidate validation

The final candidate was copied as **1,170 committed files** to an immutable read-only test snapshot. Source archive SHA-256: `d7b1bbf5e82348bf4ab1321b9c194899dd869c03883258c3cfffc20491a14acd`. The isolated test runner image ID is `sha256:35fd9a5c9f8249b424a4a97f0a3d691ef3705f718d49bdc9a775f349a3f88be7`. PostgreSQL, SeaweedFS and NATS are owned fixture services on an internal network with tmpfs; the application, TEST and candidate databases were untouched. Local evidence is retained under `/tmp/autodata-full-lifecycle-artifacts/7c626bf7-acceptance/` with exact commands, source manifest, raw logs, JUnit, runtime rows and hashes. Verification report SHA-256: `13bb75ae2484de78184c7a2dc615a245a0b788a84cf49c621677113762f4660f`.

- Explicit full-prose and content-review modules: **122 passed, 0 skipped**.
- Local reviewer CLI boundary: **4 passed, 0 skipped**.
- Canonical CI-mode ingestion command from worker cwd, with no `PYTHONPATH` and no lifecycle fixture flag: **1048 passed, 290 intentional fixture/integration skips, 145 subtests passed**. This proves CI-mode collection and unit behavior, not lifecycle acceptance.
- Mandatory unchanged isolated lifecycle smoke at this exact SHA: **329 passed, 9 subtests passed, 0 skipped** in 288.61 seconds. The unchanged `python scripts/dev/article_lifecycle_smoke.py --mode fixture --candidate-sha 7c626bf72c1eff01226bf7c05cc8372d0673a8a3 --output /artifacts/full-review-smoke.json` ran in the owned fixture runner; its JSON receipt reports `passed:true`, `invariants_match:true` and 54 runtime evidence records. Receipt SHA-256: `cc54352144ebf83622bdff65445367bfe0447a855d9a9e75cc63d8bbbbd7b97d`; raw log and JUnit are retained beside the source manifest.
- Full ingestion suite in the isolated fixture configuration at this exact SHA: **1294 passed, 44 skipped, 145 subtests passed** in 499.17 seconds. Command: `cd /workspace/workers/ingestion-python && python -m pytest -q -p no:cacheprovider --junitxml=/artifacts/full-fixture-ingestion.xml tests`. The 44 declared skips are separate acceptance lanes: 21 Workshop browser fixtures, 12 paid-catalog fixtures, 8 required fixture acceptance cases, and 3 Task59 isolated lifecycle cases. The mandatory lifecycle smoke above ran separately with zero skips. Full-suite JUnit SHA-256: `1de617ff3862b578b9376f5dcb1e830fc26a0c391e9d04d61139fccf9e650e36`; console log SHA-256: `ec4e2059c0af122458a6d1b50cfcf65aa988bc27d31cf1cb10f61b062183a719`.
- GitHub required validation at [run 42128357970](https://github.com/lucronn/autodata/actions/runs/42128357970): **in progress**.

Earlier PR CI failed because two new tests omitted the repository-standard worker `src` import path; test-only commits fixed it, and both modules independently collected from worker cwd without `PYTHONPATH`. An exploratory full fixture run with `PYTHONPATH` removed failed importing the sibling enrichment package; it combined incompatible CI and fixture environments and is not counted as acceptance. Interrupted smoke runs against moving or superseded checkouts are likewise excluded. No test skip or failure was counted as a passing lifecycle result.

## Release boundary

This implementation does not activate ingestion or payment, change public routes, or validate a purchased dataset end to end. Source fallback remains until an independently approved canonical revision publishes. Before any production release, a real provider run, full human review, exact final hashes and accepted/total by bank/family must be recorded; source fallback and introduction-only output do not satisfy the complete rewrite goal.
