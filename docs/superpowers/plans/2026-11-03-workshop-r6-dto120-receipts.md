# DTO120 receipt consistency implementation plan

> **For agentic workers:** Use superpowers:executing-plans after independent exact-checkpoint review and passing pinned preflight. No implementation is authorized by this planning document alone.

**Goal:** Add one internal DTO120 raw outcome and source-derived asset-binding consistency inspector; preserve unavailable results, no verified cases, all disabled profiles and every false authority flag.

**Architecture:** Add one disconnected internal inspector over the existing confined ArtifactStore and fixed three-member ZIP parser. It checks the entire 40-scenario x 3-engine DTO receipt inventory against a closed producer v1 contract and literal source-derived expected hashes. All observations remain consistency diagnostics: they do not establish execution, collector authorship, authenticated capture, UI assertion truth or release authority.

**Tech Stack:** Python standard library, existing strict JSON/Decimal and bounded ZIP parsing, inline synthetic unittest fixtures.

**Spec:** [Canonical assembler boundary](2026-11-03-workshop-product-evidence-assembler.md), sections 1, 4a, 4b and 10; [runbook](../../verification/release-acceptance-runbook.md).
**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8
**Source inspection SHA:** `99df69caaeb4d5ccf6d0ffbf0377fe6d5d872a3d`; parent draft PR https://github.com/lucronn/autodata/pull/188.
**Status:** Synchronized plan only; independent exact-checkpoint review remains required. Source SHA is not the future authorizing checkpoint SHA. The exact checkpoint is supplied externally to preflight after commit, never self-referentially embedded.

## Global constraints and scope

- Execution: `gpt-6.1-sol`, medium, Fast/priority, no fallback.
- Prospective implementation allowlist is exactly `scripts/dev/release_acceptance.py`, `scripts/dev/test_release_acceptance.py`, `docs/verification/release-acceptance-runbook.md`. No standalone fixtures, new source contract files or extra implementation paths.
- Planning-only allowlist is this plan, its new task/record, existing queue, canonical assembler/release/orchestration plans. No implementation bytes change in this checkpoint.
- New owned branch/worktree starts from exact `99df69caaeb4d5ccf6d0ffbf0377fe6d5d872a3d`. Root acceptance candidate `eddcf724028683dbb083191e4f8c42064b866bf0` and PR188 remain unchanged. No integration or merge is authorized. Authorized GitHub tracking readback/mutation and Git push occur only after root releases the tracking lock; they are planning operations, not inspector behavior.
- No browser, Docker, provider/cloud/DNS/secret operations, network activity from the inspector or parser tests, execution/import of candidate modules, arbitrary schema dispatch, CI/workflow/runner/orchestrator/policy/controller/application/SQL edits, profile enablement, deployment or cutover.
- Preserve existing 2 MiB envelope, 4 MiB raw JSON, 8 MiB per-file and 64 MiB total transport limits. Profile source `docs/agents/tasks/2026-11-03-production-release/r6-release.json` stays byte-for-byte unchanged: all profiles false, no supervisors, no enabled tiers.
- Existing paid inspectors and every inherited gap remain unchanged. DTO120 cannot supply API21, paid12, identity5, catalog8 or commerce14. Support files add zero logical cases. Six-lane 180 execution inventory remains distinct from machine verification and release certification.

## Inspected source, artifact and trust boundary

Source99df69c hashes: assembler `57f0b6608f04c17e7aa3cd303ba0d8bcf81027f01650475878e3ea13b8fc12b2`; tests `ac3ed257a72c860a275a81e68c66f268e9731d44d80bcc9733c860990902c90a`; runbook `adc3612c8061ac4bf25892292a02a8fcf68f13a9e483d42170faa959849f8a1b`; disabled profile task `e980162ca709b3b7622126ab943a3a9f4c9efc7e3d51eea30d9bbe0699aea5d0`.

Read-only producer references are `scripts/dev/workshop_browser_smoke.py` (`verify_provenance`, `validate_results`, `DTOFixture.route`, `run_dto_case`, `run`) and `apps/api-go/workshop_browser_fixture_test.go`. Their exact six input hashes are below. No producer change is included.

Inspected retained archive `/tmp/autodata-cross-lane-180-eddcf72/dto-artifact.zip` has 12,932 bytes and SHA256 `2aec15b39f4c87de827a5debcab798655e056a4dd8d0d34e943c869447944315`. Its candidate is historical tested `eddcf724028683dbb083191e4f8c42064b866bf0`, not99df69c or a future checkpoint. Retained artifact metadata identifies run41744117994/artifact13282298240, creation2026-11-04T00:09:15Z, expiry2026-11-18T00:09:14Z, and matching digest. Local metadata/readback establishes inspected consistency only; this checkpoint does not acquire authenticated GitHub capture or register CI/reviewer authority. Full original metadata and private local evidence remain retained; do not copy trace values/session data into repository/Issue fixtures. Test data is independently synthetic.

| Observed member | Bytes | SHA256 |
| --- | ---: | --- |
| `go-fixture.log` | 27390 | `ae732dcd027f0d9a119d07daf35843d39ca7bcfbc180640528cb54138381ec29` |
| `ready.json` | 240 | `df7196522c2f465aac755eadf71df61722d6e3dfb6268f2823980c84a85d7c9c` |
| `browser/evidence.json` | 383912 | `6a253fb5c2c37751c791c8e05a7a4e6cc4f8929b0a62a380fe4a7b85909fbc4f` |

All six input and eleven asset expectations below were independently re-derived from Git source99df69c checkout bytes and matched the retained receipt. The implementation freezes them as literal code constants reviewed with this plan. It must never populate expected values from receipt `input_sha256`, receipt `provenance`, readiness, archive metadata, envelope-supplied profile hashes, mutable checkout bytes or caller-defined maps. These fixed expectations bind reported values to this reviewed source-content inventory; they do not prove that a later candidate actually served/executed those bytes or descended from trusted tooling. A source-content change needs a separately reviewed successor contract/checkpoint, not runtime caller override. Hashes copied between untrusted fields cannot serve as independent authentication.

### Literal six source-derived input expectations

| Path | SHA256 |
| --- | --- |
| `apps/api-go/workshop_browser_fixture_test.go` | `7cf50daeb190686dc55c33c90056b87a62eece96640759b180f1282a0a1a6dd2` |
| `scripts/dev/fixtures/workshop_customer/firebase_transport.js` | `96bd315271bf05f363dc74ebb8d60c243f0ede8f0e7a649d3d7eeb7ea8f9dc63` |
| `scripts/dev/fixtures/workshop_customer/hostile_source.json` | `076b68d46991bd32a8ba73f61b93d7c22b52784c3df2d58d0c9e8d33891483d1` |
| `scripts/dev/fixtures/workshop_customer/scenarios.json` | `83ae0b9a08148fc5321663ce1f4647d29535726d7af93f6299abd4171ebc65d9` |
| `scripts/dev/fixtures/workshop_customer/stripe_checkout.html` | `26c1c7ea312630626792f89290b318ca36d01f72c7906d94cab9baf03dc74083` |
| `scripts/dev/workshop_browser_smoke.py` | `45299888e56a78679148f575ac071856f0a3c1941faf059cd586ff2980069de8` |

### Literal eleven source-derived asset expectations

Names are relative to `apps/api-go/workshop/`. Asset entries have exactly `sha256` and `bytes`; bytes is an exact nonnegative integer excluding bool. Require every literal hash and length, with no omissions/extra entries.

| Name | Bytes | SHA256 |
| --- | ---: | --- |
| `app.mjs` | 37127 | `bc1b0d5e1c1181c1ff2a833ab8dc8c9ab88bf84e38b00b018ffa5fc9206e5ab5` |
| `article-read.mjs` | 2507 | `fefa9ba05d05e8a48f8135d07a53f92d7ef32bf848db075005981848cc8d8f08` |
| `auth.mjs` | 7908 | `ec71ad49dc21fc8633e1165ff759f1d05467f40d045ca056c8be5460cce285e2` |
| `catalog.mjs` | 11688 | `cf518ae376f7d61ac6dc09e9a09b12baca6be66e64b8b79d54bab2393286db52` |
| `commerce.mjs` | 7321 | `be291187bdbd3ef7faeb9ace6c244eed8a0b28b0edc91f1e01881c7d32c9ae26` |
| `firebase-web.mjs` | 112641 | `bd2f3d36daaecdb5556e601603bea4e80cd202fc515faa931b2b0c5d0f7344f1` |
| `firebase-web.mjs.LEGAL.txt` | 35536 | `70b7365a8d96e19330fbc64e69fa03c03452787b8bcf52d0fc7ad2e184dfd319` |
| `firebase-web.provenance.json` | 2237 | `0ac4b7ddfa58ef0ac800095a4a16f29d96518792b9b81c8dcc81b262a918fa9a` |
| `index.html` | 10868 | `8910a2b9021af306f1f3698a094bbc0b8da01b9038666ec2c57879b8fb65ac68` |
| `progress.mjs` | 1076 | `dd41a36c18871aacb6c1dfb16cfb6c3659c51e92acb479481897f77cffbe7e48` |
| `styles.css` | 20773 | `c57c63c0661c500a83f2c3e5ffd57d18eac5910733a0d978e829dfa23ac09a0c` |

`evidence.sdk_sha256` and readiness SDK must equal the literal `firebase-web.mjs` hash above. The provenance JSON asset is treated as a source-derived byte/hash entry only: its internal SDK dependency/lockfile/build/license claims are NOT semantically authenticated here. Reproducible SDK build/package provenance remains missing.

## Closed API, fixed artifacts and result

```python
def inspect_dto_receipts(store, *, candidate_sha, trusted_base_sha,
    profile_sha256, profile_version='dto-fixture-v1') -> dict:
    # Explicit internal call only; never selected from CLI or candidate filename.
    # Fixed ref dto-artifact.zip is declared in store.by_ref.
    # read -> strict_dto_archive -> strict typed JSON -> store.recheck().
    ...
```

Digest-check invocation SHA40/SHA40/SHA256 and require literal profile version. Fixed declared ref is `dto-artifact.zip`, require declared kind `raw`, and read through `store.read` with no discovery/extraction. The store's declaration hash is a transport consistency check, never a CI trust anchor. The existing strict_dto_archive validates exactly its three existing literal members in memory, unchanged ZIP32 format, no unknown/symlink/encrypted/extra/comment/descriptor/multi-disk/ZIP64/traversal/CRC/deflate-tail trick. No partial archive fallback. Expanded member ceilings stay4MiB for browser/evidence.json,4MiB for ready.json and8MiB for go-fixture.log: at most16MiB by this fixed inventory, within the existing64MiB aggregate ceiling. `go-fixture.log` is retained opaque bounded bytes; no invented test/log/cleanup proof.

Parse evidence and readiness with existing strict `_strict_json(..., MAX_RAW_JSON_BYTES, 'raw_json_size', exact_floats=True)`. Reject duplicate keys at all levels, malformed UTF8/surrogates, nonfinite/overflow, unrecognized fields/versions, wrong primitives and size excess before parsing. Do not modify default strict parser behavior. Preserve the reserved identity walker: refactor only if necessary into a private helper applied to these parsed members, checking every nested `candidate_sha`, `trusted_base_sha`, `profile_sha256` if present against invocation values; no missing identity backfill. The closed schemas below normally admit only the top-level candidate identity. End with store.recheck().

Return exactly: `status: unavailable`, `complete: false`, `profile_version`, `candidate_sha`, `trusted_base_sha`, `observed_case_ids` (120 closed `{browser,scenario}` records in canonical existing DTO_ENGINES x DTO_SCENARIOS order), `verified_case_ids: []`, `observed_request_count` (sum actual validated request-list lengths), `observed_asset_count: 11`, `source_expectations_sha: 99df69caaeb4d5ccf6d0ffbf0377fe6d5d872a3d`, `missing_validation_families` (literal inventory below), and all five existing FLAGS false. Never expose raw request/query values or candidate-controlled exception text in diagnostics. No derived acceptance counts, status passed or partial verified subset. This inspector is independent of paid APIs and cannot remove their gaps.

Missing families remain exactly `dto_scenario_assertion_provenance`, `dto_request_origin_and_response_provenance`, `dto_source_execution_binding`, `dto_browser_installation_and_process_provenance`, `dto_tls_capture_provenance`, `dto_sdk_build_provenance`, `dto_supervisor_commands_and_cleanup`, `dto_host_and_input_provenance`, `dto_authenticated_ci_archive_provenance`, `dto_supervisor_and_reviewer_authority`. None is removed on receipt success.

## Closed evidence and readiness schemas

Evidence has exactly ten keys: `browser_versions`, `candidate_sha`, `engine_revisions`, `input_sha256`, `mode`, `playwright_version`, `provenance`, `results`, `sdk_sha256`, `version`. Require literal `version: v1`, `mode: dto-fixture`, candidate equals invocation, SDK as above, `playwright_version: 1.64.1`. API fixture mode cannot satisfy it.

`browser_versions` exact map: chromium `156.0.8078.4`, firefox `157.0`, webkit `27.2`. `engine_revisions` exact seven-key string map: chromium `1248`, chromium-headless-shell `1248`, firefox `1555`, webkit `2370`, ffmpeg `1013`, winldd `1007`, android `1001`. These are fixed receipt metadata expectations observed in this producer environment, not independently attested installed browser binaries. A changed version inventory fails closed and needs review.

`input_sha256` is exactly the six path keys and literal hashes above. `provenance` has exactly `assets` (eleven entries above) and `certificate_sha256` (lowercase64hex). Readiness has exactly `certificate_sha256`, `kind`, `origin`, `sdk_sha256`, `version`; version v1, kind dto-fixture, SDK literal expected hash, certificate digest equal evidence provenance digest. `origin` matches exactly `https://127.0.0.1:<port>` with canonical decimal port1..65535, no leading zero/sign, userinfo/path/query/fragment/encoded host; do not pin an ephemeral port. Certificate matching is duplicate-observation consistency only, explicitly not independently captured TLS proof. No absent source/host/supervisor identity is synthesized from readiness.

`results` is exactly120 objects, one for each existing literal scenario below x exactly `chromium`, `firefox`, `webkit`. Use existing frozen DTO identity functions/constants, never import scenarios from candidate code/data. Record ordering need not be canonical; require no duplicates/missing/extras and normalize diagnostics only. Per row exact six keys: `browser`, `elapsed_seconds`, `requests`, `scenario`, `sdk_requests`, `status`. Require status literal passed; fail/skip/unavailable rows and producer alternate error shapes fail rather than being dropped. No row can be converted into verified case authority.

```text
bankone-cascade
banktwo-cascade
dual-bank-coverage
one-bank-unavailable
pending-no-content
source-to-canonical
source-rewrite-failure
review-required
warm-reload
selection-change-in-flight
source-review-change-in-flight
cancel-and-retry
history-restore
document-only
missing-media
withdrawal
keyboard-print-mobile
source-media-isolation
auth-cookie-reload
google-popup-exchange
google-popup-blocked
google-popup-cancelled
google-stale-reauthentication
firebase-memory-persistence
signin-unavailable-local
signin-malformed-config
session-expired
session-blocked
auth-dependency-unavailable
quote-exact-scope
terms-config-unavailable
checkout-double-click-retry
checkout-processing-return
checkout-untrusted-return
checkout-expired
already-owned-no-pay
library-pagination-and-states
paid-prepare-before-poll
media-renew-coalesced
logout-and-bfcache-clear
```

`elapsed_seconds` is finite int/Decimal excluding bool/string/null, exact inclusive0..120; negative tiny values must not underflow and120+tiny must not round down. 120s is this new diagnostic acceptance ceiling proposed for independent gate review, not a producer wall-clock deadline or assertion that the source enforces a120s timeout. The inspected artifact maximum11.3s does not set the limit. Retain existing float-overflow rejection. Never equate declared row duration to independent supervisor runtime (which the archive cannot prove).

`requests` is a list length0..256 per row and at most8,192 total. It may contain duplicates/retries and concurrent ordering; do not require observed incidental lengths or one exact request sequence per scenario. Each request exact keys `method`, `path`, `query`. Method/path pair must occur in the literal table below. Require path literal equality (no URL, fragment, encoded path alternative, added query string, traversal or capability substitution). `query` is a closed map whose key set is a subset of that route's allowed-key inventory; absent allowed optional keys are accepted. Each key/value is strict text with no NUL/CR/LF/surrogates; each value is a list of1..8 strings, each at most512 UTF8 bytes; keys at most64 UTF8 bytes, at most16 keys. Query values are opaque bounded fixture strings: do not infer issuer, redirect-origin, credentials, request payload, network destination or source truth. Safe diagnostic output never includes them. SDK count exact int excluding bool,0..256, and equal to the number of rows with path `/workshop/firebase-web.mjs` (which table permits only GET). Empty request lists are allowed by the observed producer schema and cannot prove scenario behavior; do not invent request-presence predicates absent a separately reviewed scenario semantic contract.

| Method | Literal path | Allowed query keys (subset) |
| --- | --- | --- |
| `GET` | `/__/auth/handler` | `apiKey`, `appName`, `authType`, `eventId`, `providerId`, `redirectUrl`, `scopes`, `v` |
| `GET` | `/auth/config` | (none) |
| `GET` | `/auth/session` | (none) |
| `GET` | `/c/pay/fixture` | (none) |
| `GET` | `/js/api.js` | `onload` |
| `GET` | `/v1/catalog/images/v2.expired-one` | (none) |
| `GET` | `/v1/catalog/images/v2.expired-two` | (none) |
| `GET` | `/v1/catalog/images/v2.renewed-one` | (none) |
| `GET` | `/v1/catalog/images/v2.renewed-two` | (none) |
| `GET` | `/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles` | (none) |
| `GET` | `/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles/33333333-3333-4333-8333-333333333333` | (none) |
| `GET` | `/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles/33333333-3333-4333-8333-333333333333/source` | `source_revision_id` |
| `GET` | `/v1/catalog/vehicles/22222222-2222-4222-8222-222222222222/articles` | (none) |
| `GET` | `/v1/catalog/years` | (none) |
| `GET` | `/v1/catalog/years/2024/makes` | `region` |
| `GET` | `/v1/catalog/years/2024/makes/fixture-make/models` | `region` |
| `GET` | `/v1/catalog/years/2024/makes/fixture-make/models/fixture-model/configurations` | `region` |
| `GET` | `/v1/projects` | `key` |
| `GET` | `/v1/workshop/library` | `cursor`, `limit` |
| `GET` | `/v1/workshop/orders/55555555-5555-4555-8555-555555555555` | (none) |
| `GET` | `/v1/workshop/quote` | `configuration_id`, `region` |
| `GET` | `/workshop/` | `configuration`, `make`, `model`, `order`, `region`, `year` |
| `GET` | `/workshop/app.mjs` | (none) |
| `GET` | `/workshop/article-read.mjs` | (none) |
| `GET` | `/workshop/auth.mjs` | (none) |
| `GET` | `/workshop/catalog.mjs` | (none) |
| `GET` | `/workshop/commerce.mjs` | (none) |
| `GET` | `/workshop/firebase-web.mjs` | (none) |
| `GET` | `/workshop/fonts/InstrumentSans.ttf` | (none) |
| `GET` | `/workshop/progress.mjs` | (none) |
| `GET` | `/workshop/purchase-config.json` | (none) |
| `GET` | `/workshop/styles.css` | (none) |
| `POST` | `/auth/firebase/session` | (none) |
| `POST` | `/auth/logout` | (none) |
| `POST` | `/v1/accounts:lookup` | `key` |
| `POST` | `/v1/accounts:signInWithIdp` | `key` |
| `POST` | `/v1/catalog/vehicles/11111111-1111-4111-8111-111111111111/articles/33333333-3333-4333-8333-333333333333/prepare` | (none) |
| `POST` | `/v1/token` | `key` |
| `POST` | `/v1/workshop/checkout-sessions` | (none) |

This table freezes the observed retained request family with producer reference review, not complete application endpoint coverage. New paths/query keys, including a legal but newly observed producer branch, fail closed for review. Request records omit original hostname and responses; approved external destination checks performed inside the producer cannot be re-derived from these rows. Do not claim that schema/status checks reproduce the producer's DOM/assertion tests or real Firebase/Stripe service behavior.

## Task 1: internal DTO inspector, adversarial tests and runbook

**Files:** modify only the three implementation paths above. Consumes unchanged confined ArtifactStore/strict archive/JSON parsers and literal source expectations; produces only internal API and diagnostic result above.

- [ ] Add `DTOReceiptTests` with inline independently constructed synthetic three-member ZIP, all120 literal tuples, complete fixed input/asset/engine metadata and readiness. Fixtures must not read retained archive or derive expected values from implementation constants; copy reviewed static data deliberately and independently. Initial positive test must fail because inspect_dto_receipts is absent; retain red log externally.
- [ ] Add independent mutations below. Rebuild ZIP CRC/lengths and enclosing artifact declaration hashes when testing a semantic layer; keep separate unrepaired transport mutations. Tests must reach intended rejection, never merely assert every bad value trips some unrelated hash error.
- [ ] Implement fixed source expectation maps, closed typed private helpers and explicit inspector. Preserve existing paid code/default parser/CLI behavior. No generalized parser registry, external map override, source import, arbitrary Git/network command, extraction or new profile dispatch.
- [ ] Positive tests cover shuffled result order, duplicate/retry request entries, empty request list with SDK0, both0 and120 elapsed boundaries, allowed optional query subsets, ephemeral valid TLS port and unchanged unavailable/no verified/allfalse output. Negative tests cover shape/identity/hash boundaries below and exact Decimal underflow/upper-bound precision.
- [ ] Run a positive and missing/symlink/hash/post-read mutation through real ArtifactStore. Patch inspect_dto_receipts to raise in existing disabled CLI plan and validate tests, proving no dispatch and plan no evidence-root I/O.
- [ ] Controlled production mutation: remove one required tuple or input/asset equality check temporarily, show corresponding test fails, restore production bytes, then run green checks. Keep red logs outside repository; never commit the deliberate defect.
- [ ] Update runbook with interpreted schema, source expectation pin, opaque request/SDK/CI/TLS fields and missing authority. Run checks below, commit/push coherent three-path milestones and obtain independent exact-code review. No integration, acceptance rerun or authority promotion.

### Independent failure mutations required

1. Each missing/unknown top-level/evidence/readiness/provenance/asset/row/request key; wrong declared archive kind/ref; duplicate nested JSON key; invalid UTF8/surrogate, recursion/size ceiling, raw version/mode mismatch; unsupported profile version and malformed invocation hashes.
2. Missing/duplicate/extra/substituted scenario or engine while retaining total120; unknown scenario; API tuple or mocked DTO presented as API; status failed/skipped/unavailable/error-shaped/pre-launch failure; no successful-browser version entry; candidate identity mismatch and forbidden nested reserved identity values.
3. Every integer/count replaced by bool/string/null/negative; elapsed negative tiny `-1e-999`,120+tiny, NaN/Infinity/overflow; zero and120 accepted; SDK count disagreement; per-row257 and aggregate8,193 with every row still <=256; query list empty/9 items, >512UTF8 bytes, control characters, unknown keys/method/path and encoded/absolute/traversal/fragment variants.
4. Missing/extra six-input key, changed input hash with all receipt copies repaired, changed asset hash/byte count, SDK digest/readiness mismatch, malformed certificate hash/evidence-readiness mismatch, nonloopback/http/userinfo/encoded or zero/overflow/leading-zero port origin. Changing both certificate copies consistently may pass only as consistency, never TLS provenance; explicitly test missing family persists.
5. Missing/extra/duplicate/unsafe ZIP member; archive hash/size mismatch, malformed local/central/header/CRC/truncated/oversize/hidden expansion streams, symlink/encrypted/ZIP64/descriptor/multi-disk/unsupported format; retain existing adversarial archive suite rather than weakening it. Alter opaque log bytes with repaired declaration may pass and must not create test/cleanup authority.
6. Real confined store missing file, symlink ancestor/leaf, changed bytes between read/recheck, declared ref missing or extra undeclared file; static secret-safe exception codes only, including a synthetic query SECRET_SENTINEL that must never appear in diagnostic output. Every positive result preserves exact missing-family inventory, verified IDs empty/allfalse, no profile/source task byte change, and disabled CLI zero counts/no dispatch.

### Required checks and milestone cadence

Run from the implementation worktree:

```sh
python3 -m unittest scripts/dev/test_release_acceptance.py -v
python3 -m unittest discover -s scripts/dev -p 'test_*.py'
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
```

AST-parse the edited Python files without writing repository bytecode; git diff --check; compare actual changed paths against literal three-path allowlist; verify disabled profile task unchanged and all existing CLI assertions pass. After candidate commit/push, fresh shallow clone exact candidate and run focused tests; depth1 is tooling validation only, never ancestry proof. Reread remote branch SHA and clean worktree. Independently review exact candidate before integration. No Docker/browser/network/service commands are part of parser verification.

A test-only red milestone is retained externally until the coherent implementation is green; do not publish knowingly failing code. Commit/push meaningful validated implementation and validation/runbook milestones promptly. Do not modify published history solely for activity.

## Coordinator synchronization todo and preflight

1. Synchronize this closed DTO120 receipt contract, source-derived expected hashes, three-path allowlist and todo in Issue186/Project8 and canonical plan/task/record/queue after coordinator tracking-lock release; commit/push, pass exact-base preflight and obtain independent gate review before implementation.
2. Add failing inline synthetic tests for the exact forty scenarios crossed with three engines, closed typed rows and requests, fixed input/asset bindings, readiness consistency, strict limits and unsafe or contradictory archives.
3. Implement only the internal inspect_dto_receipts API with fixed dto-fixture-v1 dispatch and source99df69c hash constants, existing bounded archive/strict JSON/confinement checks, observed diagnostics and explicit unverified provenance gaps.
4. Keep disabled CLI plan/validate disconnected from the inspector; retain zero CLI counts, unavailable/incomplete results, empty verified IDs, all profiles disabled, enabled_tiers empty and all five verification/deployment/cutover flags false.
5. Run controlled red/green mutations, focused/developer/autonomy, syntax, shallow-clone and exact three-path checks; update the runbook, commit/push coherent milestones and obtain independent exact-SHA code review before any integration.

Tracking synchronization was coordinator-authorized after the publisher and PG17 adoption turns. For every future update, reread the actual current Project Source/dependency field/status; preserve its complete exact text and every prior reference ID in a new Issue comment; append this goal/todo/plan/task/record/source references. Compact only after preserving that predecessor, retain every reference ID in current index, stay under1024 characters, and independently reread/hash the result and Issue comment. If references cannot fit, escalate to coordinator instead of silently dropping IDs. Preserve historical receipts/comments/hashes, including prior DTO comment6617902111 and correction comment6619194720; no earlier field hash is the current live readback by assumption.

Then copy identical synchronized record into new task and record, update canonical plans/queue with receipt references, commit/push docs-only checkpoint and run:

```sh
python3 scripts/autonomy/pre_implementation.py \
  --record docs/agents/records/2026-11-03-r6-dto120-receipts.json \
  --base-sha "$R6_DTO_CHECKPOINT_SHA" \
  --repo-root /home/corp/.codex/worktrees/workshop-r6-dto120-plan/autodata
```

`R6_DTO_CHECKPOINT_SHA` is the actual full40-character newly committed/pushed checkpoint, supplied externally. Require exact output `status: synchronized` with `errors: []`; reread remote exact SHA and clean owned worktree. Issue followup records exact checkpoint/preflight output without rewriting original receipt. Request independent plan review; this planning agent implements nothing. Parent PR188 is a source dependency, not this gate's implementation review. All authority and source99/actualedd/futuretool distinctions remain.

## Tracking readback receipt (planning only)

Root released this serialized tracking turn after publisher/PG17 adoption. Issue [comment6621102242](https://github.com/lucronn/autodata/issues/186#issuecomment-6621102242) records the identical goal/todo/refs and complete predecessor Project text verbatim. Comment body SHA256 `9c7251167de52b3b9d3bdcdd2ac071dc795930fdde8edd8058fed3ab18ce98f3`. Prior field: 606 characters, SHA256 `e05d13f3c018713ea7200aa5d860d63355cee5d0576ed25836bed7cb30f4ac7d`. Readback at `2026-11-04T02:43:04.572252+00:00`: Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, status In Progress, Source/dependency field `PVTF_lAHOCSJ8cc4BiQ2BzhhJhxU`, 879 characters, SHA256 `f6b01dc0fe6cb7909d045b567505549909e71d4fe8853ac40d55f1a6d649e6b0`.

Every predecessor comment ID remains in the live field: `6617360191`, `6617521783`, `6618084753`, `6618111784`, `6618124676`, `6618597888`, `6619139974`, `6619358812`, `6621014641`, `6621071257`, `6621086102`. Earlier DTO/selector receipts `6617902111`, `6619194720`, `6619208212` are additionally explicit. The new field retains the full predecessor text; nothing was dropped to fit the1024-character limit. Source-derived constants,120s diagnostic limit and all unverified provenance gaps are unchanged from root-reviewed local design SHA256 `31b44e511a747424738a655b46b188d278398b2594b53fb2f77bf474cc9562a3`. Exact commit/push/preflight receipt follows externally after this docs-only checkpoint is committed. No implementation or trust promotion has occurred.
