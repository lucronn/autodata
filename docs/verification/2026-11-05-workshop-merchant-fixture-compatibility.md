# Task61 merchant fixture compatibility verification — planning synchronized; execution blocked

Goal: Isolate historical Task54 merchant-preparation fixtures from the evolving application tree, preserving the exact validator contract and Task59 server-owned configuration authority.
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-05-workshop-merchant-fixture-compatibility.md`

Planning only. No Task61 implementation, repaired-source green, CI success, merchant approval or acceptance/release credit is asserted. Parent `8d9f1a379924ae6636369e4b3b8e01ab6c258ccb` tree `ea2992091f0d00e10d3aa89f967ba735176f284d`; diagnosis SHA256eedb7510faa232e046c25b2e41f6c8ebcab7600525d73f852345369f3869a625 at `/home/corp/autodata-evidence/task61-merchant-compat-diagnosis/REPORT.md`. Genuine diagnosis red20 tests/24 failures/1 error; historical Task58 green20 tests; failed CI603 tests/24 failures/1 error are retained as historical evidence only. In-progress Task59 runs have no claimed terminal result.

## Gate sequence

Root completed independent draft review PASS15 and literal Issue186 comment6650911660/Project8 synchronization with preservation PASS10; standalone/nested records are synchronized. Root authorized only eight-document checkpoint commit/push; externally seal actual checkpoint SHA/tree. Do not self-hash predecessor. At actual committed checkpoint extract nested record to external evidence then run:

```sh
/usr/bin/python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-workshop-merchant-fixture-compatibility.json --base-sha CHECKPOINT_SHA --repo-root .
/usr/bin/python3 scripts/autonomy/pre_implementation.py --record /home/corp/autodata-evidence/task61-merchant-compat-checkpoint/nested-record.json --base-sha CHECKPOINT_SHA --repo-root .
```

CHECKPOINT_SHA means the actual externally sealed40hex. Both exit0/errors=[]; independently review exact checkpoint and obtain explicit coordinator three-path dispatch. Draft parent negative preflights are expected and never constitute a pass.

## Source verification after dispatch

Use inspected Python3.14.7 `/usr/bin/python3`, Go1.26.4 `/home/corp/go-sdk/bin/go`, Node22.23.1 `/home/corp/.local/bin/node`; record versions and source SHA/tree before/after. Missing runtime/dependency blocks checks rather than authorizing installation or scope change.

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest discover -s scripts/dev -p test_workshop_merchant_manifest.py -v
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest discover -s scripts/dev -p 'test_*.py' -v
env -u AUTODATA_PURCHASE_CONFIG_GO_BRIDGE -u AUTODATA_REQUIRE_PURCHASE_CONFIG_INTEGRATION /home/corp/go-sdk/bin/go -C apps/api-go test -count=1 -run 'Workshop|PurchaseConfig|CommerceClient' ./...
/home/corp/.local/bin/node --test apps/api-go/workshop-client.test.mjs
/home/corp/.local/bin/node --check apps/api-go/workshop/app.mjs
git diff --check
```

Focused real red before edits, then21-or-more/no-skips green with nominal reasons=[] and explicit current-source/rebound-digest embed_source_binding_mismatch. Full discovery count is observed, never assumed603. Preserve ordinary Go integration skips by name/reason and required integrations as separate requirements; no dedicated integration flag is set here. Current Go disabled dynamic-route tests stay present and run; historical fixture cannot replace them. Keep Node/browser runtime contracts unchanged.

Exact implementation diff is the three spec paths. Historical fixtures:30491 bytes/SHA2566a6c78c4d84604ec4e626b49dc10e20603018e9db398c709073e689723801a77 and168 bytes/SHA256edb1d6d182c5eeee6c33885e873bc5b44ac7a3eb4465d9e92af5d1bc60d4b45f, modes100644, copied verbatim from b6388596cf4419559fc6a8a5fbcd0b4fc33cc7cb. Live Dockerfile928 bytes/SHA256bd7a4d022e89c76432cd5b8e086166252303710cb8cb24a72b5eeff31fc52559 remains independently pinned. Retain all168 mutations/provenance/strictness/read-only matrices. Compare evaluator and all implementation paths outside allowlist against sealed base; preserve prior59 queue objects and all root fields semantically and bytes outside insertion, prior task records, Task59's fifteen runtime paths, policy/workflow/collectors/supervisor and deleted embedded JSON.

After validated commits/push, require independent exact-source review and fresh terminal source-push and actual-PR CI required jobs/live-Compose success at exact SHA/tree. PR base should be codex/workshop-purchase-config-code where possible to isolate scope; no merge. Report external deployment/check failures separately. No historical/in-progress CI substitution.

All authorities false; current implementation allowlist empty until dispatch; accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified. Owner legal/tax/support, protected config delivery/restart/drain/rollback, Firebase/Stripe/secrets, authentic TEST/runtime/staging/host/TLS/release, real API21/DTO120/final180 and Vercel DNS blockers remain unchanged. No implementation, merchant or operational authorization follows from this draft.

## Completed planning synchronization

Task61 planning/tracking synchronized by root with literal Issue186 comment6650911660/Project8 readback, independent draft PASS15 and preservation PASS10. Only eight-document checkpoint commit/push authorized. External actual SHA/tree seal, standalone+nested exact-checkpoint preflights errors=[], independent checkpoint review and explicit three-path implementation dispatch remain required. Execution blocked; all authorities false/current implementation allowlist empty; no predecessor self-hash.

Tracking evidence: `/home/corp/autodata-evidence/task61-merchant-compat-tracking-verify.json` (PASS10), before/after snapshots beside it; independent draft `/home/corp/autodata-evidence/task61-merchant-compat-draft-independent/REPORT.json` (PASS15). Exact refs/hashes and actual UTC are retained in spec/task tracking_sync. No implementation/runtime evidence is inferred.
