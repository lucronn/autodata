# Workshop Merchant Manifest Verification — DRAFT Task54

Goal: Add an inert offline validator for exact-byte Workshop merchant manifest preparation while preserving the shipped disabled manifest and every owner approval, Stripe TEST, runtime and release block.

Execution state blocked; standalone/nested record status synchronized; planning/tracking synchronized; current implementation allowlist []; all authorities false; both case credits0; verified IDs[]; release unverified. Source parent c374f77af461f01d367a8b802c7d7bea886fe7ec/tree a29bd3380144303394e1cf680d031af91009430d. Plan `docs/superpowers/plans/2026-11-05-workshop-merchant-manifest.md` and canonical draft spec `docs/agents/specs/2026-11-05-workshop-merchant-manifest.json` define the closed contract. No implementation, runtime, TEST or customer checks were run in drafting.

## Independent mutation matrix

| Family | Required synthetic test |
|---|---|
| Parser/read bounds | Each missing file; symlink/directory; limit and limit+1; invalid UTF-8/BOM; duplicate nested keys; NaN/Infinity; top-level nonobject; unknown/missing nested field; bool in integer fields; malformed digest. |
| Candidate vs baseline | Exact disabled168/hash is valid baseline evidence, preparation blocked merchant_inputs_pending; prospective false/string/omitted enabled blocked; null/blank/missing URL/tax blocked; every baseline byte mutation loses baseline_disabled. |
| Terms/URLs | Missing/null/wrong/equal-unsupported terms; http/relative/empty-host/userinfo/control/whitespace/backslash/fragment/bad-port URL; reserved host/fixture URL blocked for owner_supplied_unverified and accepted only with synthetic provenance. Blacklist is no approval proof. |
| Policy bytes | Swap terms/privacy snapshots, change exact URL, policy revision absent, approval reference blank, change one policy byte/length/hash, change manifest whitespace with stale digest; no reserialization equivalence. |
| Tax/product | Change decoded UTF-8 notice byte with stale digest/length; wrong final-price treatment, missing owner decision ref; wrong product, amount/currency/recurrence or bool amount. No automatic tax claim. |
| Source/build | Wrong/missing/mixed SHA/tree; changed actual supplied Dockerfile/main.go bytes; envelope digest/length tamper; mutable image tag, artifact field or test_passed/approved boolean rejected as unknown. Source identity remains declared, local build bytes are actually hashed. |
| Enrollment/provenance | Wrong mode/missing acct_/price_ reference; malformed provenance; change a bound field with stale envelope; synthetic consistent fixture and owner_supplied_unverified consistent fixture can reach prepared_offline but every authority/credit remains false. |
| Outcome/side effects | Missing future artifact/real TEST evidence still permits internally consistent preparation; fixed external prerequisites remain listed. Stable sorted reasons, deterministic output, exact exit0/3 and usage2, no content echo, no writes, no environment/network/subprocess access. |

Future artifact, served-image and authentic TEST proof are separate-gate acceptance tests, not commands in this two-file lane. Missing/mismatched actual image/binary/manifest/TEST tuple must block that future admission; do not add an incomplete artifact verifier here.

## Commands after synchronized gate and implementation

Run and retain actual red then green receipts:

```text
python3 -m unittest discover -s scripts/dev -p 'test_workshop_merchant_manifest.py' -v
python3 -m unittest discover -s scripts/dev -p 'test_*.py' -v
node --test apps/api-go/workshop-client.test.mjs
(cd apps/api-go && go test ./... -run Workshop -count=1)
git diff --check
```

Actual `.github/workflows/autonomous-verification.yml:145` uses the full scripts/dev unittest discovery command above; there is no separate discovery-check command in that workflow. Retain that receipt with no workflow edits. Also run `python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v` for the unchanged gate/adapters. If a Go test-file amendment becomes needed, stop/revise gate then run full Go suite. Existing Node/Go checks remain unchanged. Independently compare exact two-file code diff, seven spec pins, raw purchase-config length/hash and disabled semantics; enumerate skipped/failed checks without transferring historical CI credit.

## Checkpoint requirements

Before implementation: independent draft review, literal Issue186/Project8 sync with before/after readbacks, committed/pushed six-file checkpoint K, external full SHA/tree seal, policy and standalone/nested records extracted from K, canonical `validate_record` errors=[] for both at base K, independent exact-K review, explicit assigned branch dispatch. Own checkpoint fields stay null until externally sealed. At the unchanged parent this checkpoint draft must fail preflight because new documents are absent there; a positive result requires the future committed checkpoint.

After implementation: independent exact code SHA/tree review, fresh actual source-push and PR merge-checkout CI readbacks including checkout identity and all external failures/pending statuses. Neither source tests nor browser fixture replacement prove approved merchant URLs, authentic Stripe TEST, customer readiness, artifact admission or live sales.

## Draft evidence

Native worktree created from exact parent. App attachment exceeded100 identities and retry returned overloaded; returned checkout is usable. Read PR258 body/head b6279480dc57f81f11f93435ae5b3d10b5ae262f; it remains draft/unmerged and merchant enablement excluded. Source pins reflect actual local bytes. No GitHub mutation, commit/push or implementation change. Draft structural and blocking checks are recorded externally by the planning agent; future code/CI results are absent.

## Coordinator tracking readback — planning synchronized

Updated at 2026-11-05T02:20:31Z. Exact goal, six todo strings, six gate paths and two prospective implementation paths are read back in https://github.com/lucronn/autodata/issues/186#issuecomment-6647901931; existing Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4 indexes that comment. Before snapshot `/home/corp/autodata-evidence/merchant-manifest-task54-before-tracking.json` SHA256 53eace0d9196c6ee4f12dc7b97fdc0afc0453f54210c3a822e5d6fd28ae3a2c9; after snapshot `/home/corp/autodata-evidence/merchant-manifest-task54-after-tracking.json` SHA256 7bdd2d118e39c2cfc3a4b911c55e3a0c8f5c71922cb5ad030d5393653cec0bde. Issue body SHA256 927b46ef47b1dbf5b117273e3d3f5c0e6d9f23b722a5245869eb5323b96c4f25; Project Source after SHA256 d2308af4c50c3083224c95f8bdf5d6323164975ed3e4f235235c0e01b6c6cfe2. Issue body, prior243 comments and other Project fields are unchanged; prior Project Source is archived verbatim in the comment. This agent made no GitHub write. Standalone/nested status and planning/tracking are synchronized; execution state remains blocked, all authorities false and current implementation allowlist empty. Checkpoint commit/push, external SHA/tree seal, exact-base positive preflights, independent review and explicit dispatch remain required.
