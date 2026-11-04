# final180 Stage C/D exact-adoption integration specification

Status: planning synchronized; implementation remains blocked pending committed checkpoint, exact-base preflight, independent checkpoint review, both exact source CI PASS and explicit coordinator dispatch.

## 1. Goal, immutable context and normative contracts

Consolidate the independently gated restricted synthetic commerce14 and paid12 libraries while preserving predecessor bytes, original receipts and zero real accepted-case credit.

C_FINAL `c4dd59b3ac6a1afb74f7ad1d4f54ef1eb6e7fdad` is the exact source-tree baseline and direct parent of the initial planning commit. Exactly one forward-only planning correction follows initial commit 2e3b1c7f3dcf8b0ddd36f8098feda5b6494bd16c; the final sealed checkpoint is the second commit in this planning-only chain, with the same nine-path cumulative scope. D_FINAL `2774cdfe44e7c99a0cae5606ad1ea5f20863c0d7` is the sole source for the two D implementation files and D runbook suffix. Common parent `fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc` remains the runbook/index split point. C_GATE `cd9e8355a0ccb055b4327bbbd1ecaf97e7cddbe9` and D_GATE `70c9a6ebb2cec338f938122c8c570fd5b22a6f28` are historical authorizing gates; the four D planning files are adopted exclusively from D_GATE, with their bytes and modes preserved. The independent exact-source reviews are PASS, as frozen by the pinned external receipts. The coordinator permits planning while both source CI runs are pending; source CI PASS must be recorded before adoption dispatch. This checkpoint does not claim CI success or combined behavior.

Original technical contracts remain authoritative and byte-identical: `docs/agents/specs/2026-11-04-workshop-final180-stage-c-commerce.md` at C_GATE and `docs/agents/specs/2026-11-04-workshop-final180-stage-d-paid.md` at D_GATE. Read them together with this integration spec; this spec changes adoption context only. All source symbols, literal row identities, grammar/reason ordering and serialization contracts remain exactly as implemented and independently reviewed at the frozen sources. No new parser, API, synthetic envelope or code repair is permitted.

Selected application candidate `4d82e413e04fb2401ac7bc28dc828375ac662180`, inventory digest `c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39` and literal identity5/catalog8/commerce14/paid12/browser_dto120/browser_api21=180 partition are preserved. Planning, tooling and code-head SHAs confer no application verification credit.

## 2. Disjoint planning and implementation scope

Planning checkpoint is exactly the nine paths in the machine manifest and plan. It adds four new integration files, adopts four historical D files and appends only the assembler index. No implementation/runbook change occurs in that checkpoint. The complete C tree is otherwise protected, including C source/tests, A/B1/B2 source/tests, workflows, inventory, policy, application, all prior specs/records/tasks/plans and mode bits. Exhaustive preservation is derived from immutable C_FINAL tree entries, and the freeze additionally pins 328 protected entries and all eight C/D historical files.

Builder scope relative to the NEW committed checkpoint is exactly:

1. `scripts/dev/workshop_final180_paid_adapter.py`
2. `scripts/dev/test_workshop_final180_paid_adapter.py`
3. `docs/verification/workshop-final180-runbook.md`

The two D files must equal D_FINAL bytes/modes exactly. The runbook is the sole allowed append. All checkpoint planning files, including this spec/plan/record/task, are protected. No scope union with original C/D allowlists is authorized. Whole-branch merges, rebases, cherry-picks, ours/theirs resolutions, union drivers, parser edits and new runtime or fixture integration are outside scope. If unchanged exact D source fails against preserved C/B1, stop for a refreshed plan/checkpoint before any repair.

## 3. Deterministic append algorithms

Index planning algorithm: `C_FINAL[index] + D_GATE[index][len(common[index]):] + integration_entry`. Assert the common prefix is byte-identical in both indices before slicing. Preserve all 89228 C bytes. The exact 5767-byte D suffix must match D_FINAL and D_GATE indices, both frozen equal. Joined historical prefix is 94995 bytes SHA25683fa8519304296de87412d2b0ead9380d428c91dc9e397b8da6b6fb413e953f6. The integration entry bytes/hash/marker are separately pinned below. It explains historical entries retain original checkpoint context and refers to the new integration authority.

Runbook implementation algorithm: `C_FINAL[runbook] + D_FINAL[runbook][len(common[runbook]):] + integration_note`. Require C and D to start with the exact common 22069-byte prefix; retain all C29905 bytes; append only D8753-byte suffix. The joined historical prefix is 38658 bytes SHA25661d0f6234606977618d007c39028bf34f349c9d60514b9f2f914a1429de3eecf. Byte lengths, source Git blob IDs, modes and hashes for common/C/D whole files and both suffixes are below. Do not insert separators inside either preserved prefix or D suffix.

The separately delimited integration note starts exactly `\n\n## Stage C/D integration verification and limits\n`, after byte38658. It states both frozen full source SHAs and the actual authorizing checkpoint SHA, identifies old sections as their original standalone-stage receipts, and records measured combined suite counts/skips/durations and command exit codes. It explicitly states accepted_case_credit=0, profiles_enabled=false, enabled_tiers=[], runtime_lock=null, run_record=null, every named authority false, and the synthetic/real acceptance limits in section4. No future code SHA is claimed within self-referential bytes. Source or prefix mismatch blocks adoption; textual conflict resolution is forbidden.

## 4. Acceptance and semantic boundaries

Acceptance requires exact D implementation source/test byte+mode equality, exhaustive C/predecessor/checkpoint preservation, all pinned external receipt hashes, exact index and runbook formulas, and real measured combined tests from plan Task3. Both original constructed-byte source suites must execute together and retain: C Expat callback-independent code-point precedence, exact boundary strings, independent dual-stream parsing/46-code reason ordering/12-cell product matrix, optional first-case Go support; D twelve literal slots, B1 first-raised delimiter/line-size conflict, per-slot independence and additive support receipts; both fixed refs/byte hashes, strict deterministic serializers, concrete primitive rejection, tamper resistance, zero-credit/all-false authority. AST imports remain exactly frozen below: public B1 symbols parse_identity_events, GoEvent, AdapterError, SimulatedExit only; no private B1 helper or C/D cross-import. No module I/O, CLI, clock, filesystem/process/network/payment/provider runtime behavior is introduced.

Combined libraries still translate restricted fake bytes/receipts only. Fourteen commerce rows plus twelve paid rows do not earn 26 real accepted cases and do not establish actual pytest/JUnit/Go compatibility, full raw financial semantics, process/artifact/tool/environment/manifest provenance, authenticated bank identity, payment/Stripe settlement, real fixtures/runtime supervision, dynamic support inventory, browser120/API21 or genuine same-head full180 execution. Preserve bank context ambiguity. Environment-dependent test skips remain unexecuted coverage. Profiles/evaluator/assembler policy, staging/live/release/promotion/merge/deployment remain separately blocked.

Every diagnostic remains exact integer accepted_case_credit=0, profiles_enabled=false, enabled_tiers=[], runtime_lock=null, run_record=null. All nine names remain false: fixture_verified, product_candidate_verified, staging_verified, deployment_authorized, cutover_verified, implementation_authorized, runtime_execution_authorized, profile_promotion_authorized, merge_authorized. An external coordinator dispatch permits only the scoped source edits and does not change these diagnostics.

## 5. Tracking, checkpoint and exact-head seals

Issue https://github.com/lucronn/autodata/issues/186 and Project https://github.com/users/lucronn/projects/8 contain the exact five-item todo from plan/standalone/nested record. Live readback detail https://github.com/lucronn/autodata/issues/186#issuecomment-6639755403 is newly synchronized; exact receipt SHA256 `cff205865bfc29f993fd860ea770d3185deb9c406684484854af055878ecd398` and raw before/after/preservation fields are recorded in both equal records. Coordinator remains sole GitHub writer.

Canonical todo, literally identical to the plan, standalone/nested records, task and synchronized receipt:

1. Freeze independently verified C/D source SHAs, source/append pins and historical receipts; synchronize this integration plan/spec/task/record and allowlist with Issue186/Project8, commit checkpoint, pass standalone/nested exact-base preflight and independent checkpoint review before explicit dispatch.
2. Adopt only the exact reviewed D adapter and constructed-byte tests onto the pinned C checkpoint; preserve C and every A/B1/B2/CI/inventory/historical gate byte.
3. Append the exact pinned D runbook section after the untouched C runbook and add a combined synthetic-only note preserving source/checkpoint identities, limitations and measured checks.
4. Run combined C/D and predecessor focused suites, full developer/autonomy discovery, no-bytecode compile, AST/import boundary, exact-diff and all source/prefix/suffix checks; commit/push coherent validated milestone and obtain independent exact-code-head review.
5. Read back exact integration-head CI and synchronize code-only receipts without overwriting history; retain integer0 credit, disabled profiles/tiers, null runtime records, all nine false authorities and separate real fixture/runtime/payment/final180/release blockers.
 Original C/D comments/receipts remain historical and unchanged; source code-only completion comment6639738283 is separate. Save committed checkpoint SHA externally, then load committed record/task/policy with git show; require standalone=nested and validate_record errors=[]/status=synchronized at that SHA. Obtain independent review of the exact checkpoint and explicit coordinator dispatch after source exact-head CI PASS. Any missing/failing/pending condition blocks adoption.

After adoption, require focused/full offline suites, compile/import checks, complete tracked/untracked scope verification, read-only object checker and independent exact-code-head review. Read exact integration-head Autonomous Verification, preserving URL/headSha/event/ref/conclusion/all required job states. Pending/failure is not a pass; parent/aggregate/local success is not a substitute. Coordinator appends code-only receipts without overwriting history. No merge or promotion is implied.

## 6. Machine-checkable immutable manifest

The manifest records exact Git source, blob, mode, byte length and SHA256 rather than mutable branch names. `protected_pins` are the complete freeze's 328 selected pins; exhaustive tree retention is additionally asserted against C_FINAL. External evidence paths are immutable hash-pinned observations, not substitute gate authority. Historical receipts that say pending retain provenance; fresh external seals carry new outcomes without rewriting them.

<!-- BEGIN INTEGRATION PINS -->
```json
{
  "refs": {
    "common_parent": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
    "c_gate": "cd9e8355a0ccb055b4327bbbd1ecaf97e7cddbe9",
    "d_gate": "70c9a6ebb2cec338f938122c8c570fd5b22a6f28",
    "c_final": "c4dd59b3ac6a1afb74f7ad1d4f54ef1eb6e7fdad",
    "d_final": "2774cdfe44e7c99a0cae5606ad1ea5f20863c0d7"
  },
  "protected_pins": [
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": ".autodata-autonomy-policy.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "be4d8088b3fd28c84c101a723ecc7c26768de9e7",
      "bytes": 2201,
      "sha256": "798e91b9854098a706ea4ab66a414492c044059a1c98edb9d2f1d003e3baad98"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": ".github/workflows/autonomous-verification.yml",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "08384431f5c6795eb83cae0ad4e8b8759d5e6fa9",
      "bytes": 9521,
      "sha256": "d38f4b1a5f414775b494ee801c83ebbc0473a7ab7e970cbf573529d08f1010aa"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/pre-implementation-gate.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "41076af1db25f0cff8ca41d0203c050af9b772df",
      "bytes": 5659,
      "sha256": "fa6e9c95c2674164c90d78e046a0427f6b406c313fb82ff627a2a2facb560ad0"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-11-public-facing-readme-and-wiki.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "1ecc88cc0908b7b7652f8559488d340a1c296e09",
      "bytes": 866,
      "sha256": "c00b320a528d912a6c5017f4ae7b61b2f0e8042b502b66e087216a1f69ca02c9"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-14-consumer-repair-guides.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "603f0842ae7fe88f88081a68b4fd8962c73388d6",
      "bytes": 1678,
      "sha256": "1b167e3d27cbf8178cc7ed3004fef326fe509cabd2a61cff28a9742a01687753"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-14-consumer-review-agent.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "800f93f6afff6efbcaca20537f377849a6f27cf0",
      "bytes": 4070,
      "sha256": "35214b1552790bd37f66b5df21387d20a0aa7a0526aabe06b4476dc356f247d9"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-15-chat-source-failure.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "2e6301bd2691697d7a23a8f70a4ab615e7ed9a9c",
      "bytes": 1045,
      "sha256": "3f1913f896b5d101e0986c3d35261a095e90c66a4d607ee5a926185be40b93fa"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-15-consumer-agent-artifact-detection.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "158c3c26b340ed26c165dad3892fe93a91d36bf5",
      "bytes": 1175,
      "sha256": "bce885566945c0e7358db813cf84c11341f6ca418af97433239da6f76917fd50"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-15-consumer-summary-filter.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4acd62c69b47f9bef30424c20ea49334e14a0dc4",
      "bytes": 1695,
      "sha256": "218d7ddd84067f328174fd251c15a4b911908ff51cbf9e3297912f2d6f77a2e7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-15-html-guide-and-silverado-label.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "3176a108a1cc319027039681363c92dac13c8228",
      "bytes": 1480,
      "sha256": "7db7a649670622be484b836049ef900b635e2ac00eb1b1228a3dec3fc12555b5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-15-minio-compose-ci-image.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "9646d4c694ae9b0a623475b9962d9773b97dca08",
      "bytes": 1295,
      "sha256": "d6648fb4973f3142e4bde5b2382bc199564bd9b8742c8b7bd454df966cce9c96"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-15-negative-completeness-gate.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "521963d4cfd418dad196d6f0b6b7dec169477d79",
      "bytes": 1686,
      "sha256": "6fc0055db03ab3ea0eaba405aafd603775e08cc4cf64f7fe61544af7837c4fa5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-15-pdf-caption-cleanup.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "cce72e4d1853ca04702c11a6408bedb8844e8ccd",
      "bytes": 2086,
      "sha256": "491cb27a4a9388f10f93d7f4e65f61f2a9197813173ce039f47282730f20e071"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-15-rav4-4wd-consumer-matrix.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "fca115a4f1a56d6e7015c506c1eab3d2386c38f7",
      "bytes": 4521,
      "sha256": "488e8c88b865691c3ece87bfc910d713f8d4751bb5a2435ce9b2a20f0d26ce12"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-15-source-fidelity-procedure-hydration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "df71ee15e3ad115ba5a82e434590b400596498a8",
      "bytes": 1042,
      "sha256": "0749f4acc72ff8d24f3484f925969c001757aa44981cad3232d2f323d213a6ed"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-15-vehicle-specific-guide-label.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5128c106390a35f1d82841d7a5a029398ce74d15",
      "bytes": 1693,
      "sha256": "9dae05ac9bd6dd75f85528dc76d6d4f44a8a9a3ace11533b85528bcd9bdb3e97"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-16-evidence-reference-deduplication.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "12163399d51fa82f55ef2c2cfa1dde8d150d4071",
      "bytes": 1598,
      "sha256": "72b9b6d07994c1e7b679ec9173690049f70f8023370088b857ce04cf208059c7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-16-procedure-artifact-navigation.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e26f64c26a06dc86247626e9fa2d454c74c9424c",
      "bytes": 1062,
      "sha256": "4b63033f50fea779a666339f669be04a51442dfdf233ef76df25a67e2dbe9865"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-18-provider-neutral-vehicle-identity.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8122c27d89dd072fdf3b4db39dcd75080990f399",
      "bytes": 2238,
      "sha256": "86980b9cd2dd2b7c915349715a800db9b9255d05b4f9a3d2fb0c32dc2e078ab2"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-22-fixed-order-diy-ingest-local-images.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8c27ac088f709e1491f8c244d1b60f416568f168",
      "bytes": 1177,
      "sha256": "1e694642b1d5871d21c9c8c5e8e2433ba9eee9831e4f018128fbb2aae3e8164f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-24-openapi-swagger-catalog-api.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "622394d4a228337c5b4797f2f9e73f4eec644cf6",
      "bytes": 959,
      "sha256": "a698068cc3abf550a2c1eccda64735e358ee74d9bc7306c231ae1b4276ebbdef"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-24-provider-neutral-catalog-api.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "18bc2821b9cc82dd8971a57efd373d5b805cd31c",
      "bytes": 1222,
      "sha256": "eb44ddc06829170f605b810de09c6ba4892b1a3e94df4ba94bb73f8cfd944ef1"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-25-workshop-interface.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6a6e39e1d8fe1e0109e33c6c8806b4b8a6b23945",
      "bytes": 727,
      "sha256": "7bc48b4480a3c9fb4b7866f77290371f4ab5ad89aa3429a758a109bb1b9387a0"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-25-workshop-loading-progress.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "08cad4a52ee6f8c01a8bc3c4694e8833ff4433fc",
      "bytes": 912,
      "sha256": "adb5847068a6fd62b53dcc396b4f9cc0b3045800acc2c93488ae0996ccb7676f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-26-article-catalog-list-only-hydration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "1484b21e78a7afbc60279c4e7c308e1ca199f940",
      "bytes": 1113,
      "sha256": "f5d0a1aed8f06d21ffeccd3aa70e7c6107b3b999b8d3b995b3ffccef08e9288a"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-30-catalog-source-review.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "b7752e809e0c58047a7e48ad19f0d174c50dd3d7",
      "bytes": 1034,
      "sha256": "ef5c9f9335ce6a539db06ddedc650b62ab341d54369e7bc80d3592a5b947aae5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-09-30-ordered-article-document-normalization.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a5c4a058d58ec6cc56549cb59c6fa656d880e17c",
      "bytes": 1199,
      "sha256": "69fe28606edb650dcc0b547f79d926ded850fe88f036104454c9743acfc34cb3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-02-opaque-source-media-paths.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "3ca9383459c8d43740e1caf81e0914aaf833c506",
      "bytes": 1183,
      "sha256": "3823a8419a2c3d0d42cf2bf3ca67a8e4334d9b31e8c685d1fff2758dd7aebb52"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-02-source-connector-api-compatibility.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f5a53c731c0cc97416b3bb2398079ff59fea037e",
      "bytes": 1507,
      "sha256": "ebf5c88ca21001ab0542498c0e965495dca045eb133e193c8bab0f99a2ad596c"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-03-autodb-two-response-shape.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "931daf9fe483b8b0a9fbbbfc25a3aa5e6b1b3583",
      "bytes": 841,
      "sha256": "a6c62718e3f391d3ded13024f72087859c782fc7fbbad9fd350f2a4a55881e8e"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-03-ci-s3-image-access.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "7854eb6bda13f108b0fcc14657f3a135d251bf04",
      "bytes": 1049,
      "sha256": "a76cfd036748e891878882b7d3aead5ee9510703f67c8762df0ebbdede3705e1"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-03-disable-chat-active-path.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "aab1262302e6afd6711181f5ad8f8a1dde93d46a",
      "bytes": 1255,
      "sha256": "f6f0953bc8b35c890005720cf1d3127d18b7d51fad59e2928653ae651310477d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-03-ephemeral-mercury-composition.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0eb5e566242d57d5e21c2f67b89e09c791137372",
      "bytes": 1610,
      "sha256": "70631738e0ab7dc90128b5d4b1daddbf63b28f27c961ed75887151fefc6a0f41"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-03-public-image-storage-key.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8b3407fefabd08ba1db2504c021678400840b138",
      "bytes": 766,
      "sha256": "911b4de58aad01ac618bca15b45c62e4e5e54d8d56be6edd408d9a4e6aa5ea98"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-03-source-review-container-assets.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ffecf4de8f8bed8f6d44f0be3030bed570ed5ed7",
      "bytes": 881,
      "sha256": "35168dbd240052ffb9d56651c064cfaea8e557a2ac1b9588229a81bd3d58f4ea"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-03-source-review-opaque-images.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "9e3f64817e825950b05bcdc57ae4173e01b7da62",
      "bytes": 842,
      "sha256": "0ae8dce250c82cb5c91508ebde2c37158db88feabd1548ddbe7fb95eaa723226"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-04-localized-catalog-images-112.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "47561510c74d8c2032d5cea2896fa12aa221e455",
      "bytes": 1375,
      "sha256": "4bbdb142e3fdd552ce4a5a8955319ce0118eb15e4a61b575d5ec86acb6b8b2d6"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-04-localized-catalog-images-116.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "97a912f803bd9855256e6c21af28728711fe26da",
      "bytes": 1375,
      "sha256": "87483aaead219bb9324b975e0dc2cf6053cccd29347f01994b672e25a890f37f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-08-bank-internal-rename.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6a4cbe4896bf0b21402cf0ea921560332b748ce7",
      "bytes": 969,
      "sha256": "44a127cc88fcc8b86d2fd2f20b01bf200d7eb15860dadfbe0f951375ce64ea4f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-08-catalog-step5-usable-configurations.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "34954a12f9c7436e24ff2c53749dbff115f41712",
      "bytes": 1242,
      "sha256": "19c470bc73b963f985d813debb81143cce135f81e831ef2007a74cf4725facf4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-08-independent-bank-connectors.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c1ffaaa4ef387b129e9e7ac931c175c16f856555",
      "bytes": 1097,
      "sha256": "ef68ec350ded19418f29abb2e5af2cce5d5feb8bf58954e826493d84fc130359"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-callout-step-images-persistence-address-cli.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "290125858038942b21cdb28b2192dd8217d04f50",
      "bytes": 2279,
      "sha256": "2a91e5fd5a2532461f84906548cb84af76b91b38f95640a0f479d5caf77269c8"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-connector-routing-document-hygiene-cli-ergonomics.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "fbbe6925b58510b5373b086bb0858d077033fb6b",
      "bytes": 1556,
      "sha256": "4b7c14ffe77363b0fc014244929df8dad7997880608bc8000c4f70dcfbdb5009"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-deep-lane-smoke-banktwo-service-resilience.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4782450e141d5200e0bb320d7176fe6345b47205",
      "bytes": 1181,
      "sha256": "855cf54068709fd17c6f47ee9170caf50f92e4ea27c388920f548d80a89c5db9"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-document-block-image-hydration-outbox-cli-ergonomics.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "d34aad363e32c8ac0ebe3d31943d2a7b95e331e2",
      "bytes": 1568,
      "sha256": "3d13dd3f4c0551e6d7e0d6afa029265a6cd84899f9e87e0250eafc4bc00ab5e5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-document-hydration-contracts-check-developer-ergonomics.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6fba413c2265fe4ba1d71a2e4123f4f7a3152db1",
      "bytes": 1551,
      "sha256": "18cb99d2aba6b139a5a32813069bcb8d5c34da56136d6de87d572d876d495c6f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-document-image-dedup-dev-cli-uniformity.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ddf9508fd28ad5e39f11e107c61df5f4c6c2df5c",
      "bytes": 1636,
      "sha256": "825653023025995d25a2153073188f5f50e0093ac12fb4b19ceec46ec37c99d7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-document-image-deduplication-developer-ergonomics.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "117f1ff3ea1f2f85e5cd92b0c19fd677320c276c",
      "bytes": 1303,
      "sha256": "93ecc32308a1d90d43273097cb0d55c52ae39a0d0fdf915eb306478d54db0572"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-document-image-localization-preflight-cli.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "04e2001fc8091f8b7c4ebf506a5eb497e9ab9c34",
      "bytes": 1491,
      "sha256": "6e6083c837d28d8e3a811dc94b8fdb22314bd3c1012b4cccee8ddf83ee8f7874"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-document-normalization-list-images-cli-uniformity.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ccbbd3943ffe6499d1073010185d40b346f77e3f",
      "bytes": 1426,
      "sha256": "291e879280066f1a77ca4776192c65129a8bbec351dda369d75de6aa9880f2eb"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-ingestion-persistence-resilience-cli-ergonomics.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "b635dbca577755d8c2fe24f0f3870218b68c5ada",
      "bytes": 1355,
      "sha256": "7c254aecb8ddf13c3cbcaa28b9e748c83856d4209eae70ad6f47933b0edcff4f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-list-labels-asset-refs-cli-uniformity.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "2b036b068efb4bee3f7fee2743bb6b4ff21d17de",
      "bytes": 1751,
      "sha256": "ad918e815f289672951bfbd32f7e37f229d4f97d4ad6f573774f899c227fb69c"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-nats-resilience-bank-service-filtering.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "71d419660721ca9d2fc86b3fc27b7525b414b3f2",
      "bytes": 1132,
      "sha256": "409f7f81b47e46a1fe845d74d27b9f76cb8ba7f258d75cab0847d0dca1b306b7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-outbox-relay-persistence-resilience.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "33c4674f4fe123b5ae1d1762ba6f95f02d696ff4",
      "bytes": 1290,
      "sha256": "32a19d16f38a6ac0b1cd2ccb90ca36c6d31fd1ef99310a1aaac7792499a6cff3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-pdf-figure-extraction-data-uri-localization.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "cd21105545ee348852cc60a15dd12f3fd7ce3cb2",
      "bytes": 1394,
      "sha256": "506214ff8b19d5a747b18b8d23a3fcdecb856c367a6ce06b3f5b9cc832ce9275"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-step-block-normalization-dev-cli-ergonomics.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "2f21a23ae0f8a703f5e92cc9e584ffc156208b99",
      "bytes": 1551,
      "sha256": "3b66bcdb322d4eb5ac4393b52f6c7e6df33752a90feae1e8d4ac35aa57b8d71e"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-table-figures-callouts-dev-cli-uniformity.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e3e0847f6f07e4a15d8786cf89648afe05948e2c",
      "bytes": 1662,
      "sha256": "2609a0db097963a185763cd6e33f48cd9ffa83101bfc94b3c2a75d6938b448b7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-table-figures-document-hygiene-developer-ergonomics.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f34d2fcbfa353490667b6eb68578d0fd6b8de437",
      "bytes": 1446,
      "sha256": "1796d4b9a4e6dbdf2cba918274d79dd26f67ad54479b0f81375ffa77b2388585"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-10-27-table-paragraph-images-persistence-address-cli.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "08d8c83f606d2579e7902449d31da2276aebf2ad",
      "bytes": 2614,
      "sha256": "b4fc4e1a06ec82f74d9e9118a5a61684a80d283d8e22953577386870da9a48b8"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-auth-error-cache-headers.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e6a37cff5b9ff42118186e66f087cb46a2068c4e",
      "bytes": 1183,
      "sha256": "a29a1e54f26e260f7349e40e48f392c95ba78d3d90ffdd0bb98ecc7e9884dbf9"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-catalog-runtime-assertion.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6dc0f0d1364323a2be8da2e99d247674e855773d",
      "bytes": 1062,
      "sha256": "51aa4f82b91b1b8aa82153bcf236e8c8f6d4293d69631776d5a14cec272e8e71"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-catalog-test-race.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "2a97be3137d998fe2c8497d795f6ddce019b02b5",
      "bytes": 829,
      "sha256": "75b340cf4245f8d5a3f2192d6da6baf4a8804dc0d507108c8bfd48f6c3a437e4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-frequent-commits.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "efe97cebe7a8b5a10040e36c7a895a7ad0fd8295",
      "bytes": 1141,
      "sha256": "9aea899c032802e268715bc02e13f5def04e4e6ddbd839ea147cde1a525c9d37"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-identity-session-probe.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5b712c39cae4fb324ae93a12606eb2ae4cbfa767",
      "bytes": 2409,
      "sha256": "4ff62e001325a67ed6393e71d070b1fc237247ce1c3ea7b9356d78fab1faf620"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-nested-image-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "b01d2923390d65e10122fdafbf3660b4ef094d17",
      "bytes": 1110,
      "sha256": "d08c41f852af30d1dad4b911dbca552eead9e1c19c41edd06f8af7361db0c451"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-production-release-orchestration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "20501ef6d39f79badb5abd4cc187f17c187fe964",
      "bytes": 1697,
      "sha256": "691977ccbb57f59d2c221b926e374efa5630531b1e98bd1f8604c59339e1316f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-r6-dto120-receipts.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "40a65606b7e6f4284534c8a9ae18f0c16ece26f9",
      "bytes": 3344,
      "sha256": "2eb046c5b62be9e48dd28c3c3090b77cdd058b042281d843ba59042f1b595fbf"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-r6-paid-selector-work.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5c732ffad957eb5b59983fec3ca548518d95acbe",
      "bytes": 4258,
      "sha256": "527a50425fb0e9220d618e05a13f13853502c282613569bbd6383533c6736548"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-retry-queue-test-clock.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8065a102508869f8982c74045330081fdfeb6bd4",
      "bytes": 2595,
      "sha256": "13c647b1deedf989b92032113d633f37b9ca31f82767006dcd3b2557e8541edf"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-runtime-check-contract.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f7905019998c272cc9cb846ee354abf45f22c767",
      "bytes": 1538,
      "sha256": "0dc29c8e7b12bbc3115d4380978c020a14a73a6b703df71c9f0cd92dc1858bb2"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-runtime-disabled-notification-trial.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a7190de8ae2fa3127aef97fb9179657e2f6843d1",
      "bytes": 1475,
      "sha256": "b1d6df6166556ad2f7c7c9f6a61492292d9ce74ec1078ba08f6cb09f579fb83d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-runtime-packaging.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "caa54e3a5b4e53d4d77f4770a51dab58c188f8d2",
      "bytes": 1573,
      "sha256": "d90d08f38948449f7ca38ada45ddd8478fb7e24d8d7548f0c3e6a78ce08d1ba1"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-artifact-boundary-corrections.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6a58133ab3901f7903ce9c6b86f103032ececd4c",
      "bytes": 3182,
      "sha256": "c68db6b3c9eb2c2e4daac92a32fbc7526dc16cc4584e799f44c2d8226dca2766"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-auth-provider-readiness.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "52878fbd38e4da3ab269b09a1cd5bdf541de11e0",
      "bytes": 2442,
      "sha256": "ad8ff86ae8ea964c0cbfedaf984b7c1babb4b21bb2964c4c3cc4fb40a333d00e"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-authenticated-publisher.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4211188e038be9dfff3baac96a3c04cdbacc924f",
      "bytes": 4739,
      "sha256": "6dbaca3cf7f714f2422880213d303b144d406b9132a76de3d48dfd4393a71ac7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-browser-account-media-status.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "bfc735070b13c337bb5432de93e0f8085ee462ff",
      "bytes": 1403,
      "sha256": "763be5d61d5910a05752ae1b81fda7c1d1417d62f8097d8b43d2cae15ee93d06"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-browser-client-response-loss.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4bd14b1364abdcf101d3996e40623d398a7de560",
      "bytes": 1825,
      "sha256": "0c4c4b23a19bab728520506553bd7bb090d73fa05cd81a7c46efdb1c66ad36e4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-browser-private-home.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5a8226387744228a773124fe507c53a02e3caf09",
      "bytes": 1611,
      "sha256": "04c99e68ef9ca81576ba1438e160e15d91b53dce768eb5951b245d4373e3bb23"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-catalog-region.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "01590357491e3fe8f0d5ccd8d40b4831291cbab5",
      "bytes": 1103,
      "sha256": "9c8e5009d68b59118102dc23acb1ffb0c241fc125cbc434ef086d441085ebe47"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-commerce.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0d7a4d6068c10d17ed30bc89084f5ed86127acfd",
      "bytes": 2450,
      "sha256": "80dc59f000e4c3aa2f8309d49f25a41a9a98b1558597e5d2984377e7f87ef779"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-customer-ui.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "57f2e301bb2365481d1607c91d5773359f85b383",
      "bytes": 1951,
      "sha256": "5cfb839c2dba0aed546f0f0af7481327254428c080bf6ddcba0b41a6cec7bfbd"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-dto-ci-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4fa24ebb90f3ee66c0d91aeb91fb343aa9ad5806",
      "bytes": 1004,
      "sha256": "7305398c7dffd377a853a111b54d54803ee377f705143f98ac85cec9ff0835c0"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-dto-timeout-diagnostics.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a21ddbb5747c58f5ef84f701a448d7bb50eb9755",
      "bytes": 5118,
      "sha256": "e8f405ddfee5e8bcfa102805ae3d03a8c514c44e842b295e957c53edb1497eaa"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-firebase-bundle.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ac1650c6c7adc7a88d8f771b650bb64ce7f11fd2",
      "bytes": 1217,
      "sha256": "8640f8faf52f40065b02590d431d92ff29c8f805ae110d847bd1a730dcaba598"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-firebase-identity.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0d8025c33d33c1e690aa0855fc96f315fee44481",
      "bytes": 3570,
      "sha256": "d1c5e445a8577ee037e43b39a265a78b4e34edd906688de127b30afc5c647f39"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-hosting.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f6fad098d54cad86beee7c63070715437d1574d4",
      "bytes": 11620,
      "sha256": "cea0f20327640a33de6fddbe9372bb1c58978d6cf48f04a27ad31119489a7cb6"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-migration-build-arg.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e8175284c036185c3a6c552e9ffd3f1e49e3505d",
      "bytes": 3535,
      "sha256": "a97dd651500a87db6c5b303a95183adfd7a55c04640b112beb5aa38c8e5ed899"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-paid-access.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6bd429d613bfad6cddf2c11b969ff59c2404d95e",
      "bytes": 1828,
      "sha256": "9bb8f06c27140232c4d180377925080a43b6356c4aa3ef1943c99fedd14a8ca3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-product-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "915727ca7dc6ce9442814fee549a3bce4ca57e57",
      "bytes": 2534,
      "sha256": "e2bd046827290244d0f866ef81e6fc5611ee58cb59755a82630c2781d17321e2"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-publisher-transport.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0fd1313ec6e0996a3d6d45c805a3ed886c2b1e58",
      "bytes": 3601,
      "sha256": "492c08c837baa839dd39ad78392ac9858efeccf05b3f0747cde27ee64cfe2440"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-schema-observation-harness.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "917cec61cee3128e95aed48281e9be74024af0e7",
      "bytes": 3216,
      "sha256": "4b099613986d7d95cb8e9717fc6de45448ccb4b48b33a462d0875ce76442d94e"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-03-workshop-staging-workflow-regression.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "154179a68329007f208f896c354b5a0ac8b8fc64",
      "bytes": 2287,
      "sha256": "ce176fc53a3b297c9a4edc305426180bbfced848d7b9b1048db02a5f2f3d7d84"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-r6-paid-http-completion-tracking-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8de191c084b770cff93b391a752e9b19826a225c",
      "bytes": 1399577,
      "sha256": "dd1e378cd86b75624672c8636ecf0697590d12259913993745e5943440012489"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-r6-paid-http-completion.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "86e88b8b3c4ff1d2a14268d62684307cb3a3a1b8",
      "bytes": 6592,
      "sha256": "234ded38452689e13c13c690d0b6eec23a99de11e5219e1bebf1bd5299d54a47"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-r6-paid-http-receipts.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "305d65cdf97fd23250836832bb02d5e0d260b832",
      "bytes": 8540,
      "sha256": "27a41915e43add66a756a6cad62bfe746e7398d19b384e8be99939d522e9d8ce"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-r6-paid-http-tracking-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6f635994879809f201995ae807fcdc8ed81d0996",
      "bytes": 1105169,
      "sha256": "528554501171acfc4b95c70262a63c9b83b789c9b2f1dc0489b5c5c4d3aebb2f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-r6-paid-scope-completion-tracking-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "d06e43ca8f22d23295d58d7921b633dea518dc17",
      "bytes": 1542783,
      "sha256": "471f538919e514246dc265ceb777fe2477ce1b616e5aef042c81b28623e478c0"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-r6-paid-scope-completion.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4e355f79e154c935773ce542444c7a92eb9fd9e9",
      "bytes": 12399,
      "sha256": "460e0fe11ee1af5dc6787ff55d919efbc87a4f4f04f14e9999649b2502d7df6f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-r6-paid-scope-receipts.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c676bed2f50c0106ef15cec126605ea9a847d07c",
      "bytes": 18568,
      "sha256": "54ec869e6cb6a787e4c3587e84685ca3df67b3ebd2b42aedffd6d331c65a351f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-r6-paid-scope-tracking-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8c9de3aa3aa40fa11bf79eeb6136bddf7359baf4",
      "bytes": 1548583,
      "sha256": "1e82b1bc2ade7a4d4e71437dbbbde33d672eb2090ab4dcbcefa067292bfa4ae6"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-artifact-inspection-close-failure-preflight.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "21cd5526119e98ca9e0a15e1035340a5c1faba90",
      "bytes": 2875,
      "sha256": "2bb900d8042598ccd9e8937ce11714ee514847044ff4a4d01ce1dd36b5424e6e"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-artifact-inspection-close-failure.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "74e99e5d4617b14b83b5c87713f7952c68d8139f",
      "bytes": 4199,
      "sha256": "134f380024cd63c3812dada169ba4045d04a58f1a25ffee90792b282f230fe85"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-artifact-revalidation-deadline.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "151763a06267fc2a5c0fc1c42a178b953051bd21",
      "bytes": 3868,
      "sha256": "b59df5768f2ca7032cd670e8856f3bc33f3aad03e15e818b6eed289d029a071f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-final-reviewed-leaves-integration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "9e8238ff3869e07ce30e0d8f0767e24381dd653f",
      "bytes": 25504,
      "sha256": "e4fdb0873bc84d88bb04a917f0740ddd8385fc67557addf08b4565ac2fcc91c1"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-final180-ci-integration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "adc84903321c9de8949d92f9dad531e1b4796512",
      "bytes": 9588,
      "sha256": "4f2e865bfc79fb4cd6b8a2e3d329913091b07e8660d93c2857357718aa09b986"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-final180-inventory.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ce6ad09ddee409a0503a9e6eeec7c8cbef9b697e",
      "bytes": 2292,
      "sha256": "5f1e39289471256331a873aa3be65be50479d11c92a83353b78ce59f60ba30c0"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-final180-runner.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "76fad048ba8369375623fdb19126adda482a976c",
      "bytes": 2818,
      "sha256": "90f083cf65c116cd9660269805a764e433ad0f34bf92ad5f1b6a92596e6f4752"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-final180-stage-b1-identity.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e52a6813c24dbf71ebcf9ebcb209d447cac48e1c",
      "bytes": 5060,
      "sha256": "8b518c6c467906768f3b00cf83d78fac8b64ad9469f5182c86a198286b6f29a0"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-final180-stage-b2-catalog-go.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "176f16b2e7595f0831263fb0bc1829e33f7257e6",
      "bytes": 5948,
      "sha256": "2d8234d8ff2deeaa9bf9f698b55ddfa3d3c3ad1888698d46deef3d36634bb263"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-index-readiness.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5a7beb50e7959f85a7b019bd2e6b90df0f3400ee",
      "bytes": 9800,
      "sha256": "d92ed307d716cd5c2d6ccbb5cf8735a5999a309558b280a8194733d634755f8f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-publisher-python-review-corrections.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "59e5d654b95ffae7535cdb0672202b46b0ef0bba",
      "bytes": 4061,
      "sha256": "5af984b9c5ddea00d0cd892aeee4bc878ffffcef5a91f16e42b99fce72442dea"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-publisher-sigterm-ordering-amendment.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "294d3e80fc90a60bb1681cf139e030253f971ac9",
      "bytes": 4223,
      "sha256": "5a910f3f1f916747519d76dd8ff1f84d930f7fa579ef133e00453cf4ba99af80"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-publisher-stage0-integration-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a1fb2888c2bfbf9e477860c8243c81a5c1ef32c5",
      "bytes": 107264,
      "sha256": "044b1044865831b1ee11466b24dd2302ef7b692c6f2f8d4d6512852634902e58"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-publisher-stage0-integration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "afa8461b5878775e4a4eb8a3a59ac936722aa64d",
      "bytes": 13643,
      "sha256": "8fdf493657425221dd806e1bdcf8190bed9e096278d39efe9779d063dcfafcb4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-publisher-stage1a-offline-trust-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a93470a9c3aa378fabd2cd831dfa7284055d42f8",
      "bytes": 261610,
      "sha256": "8a0bec72faada1c44ebc0594299f1ba41347d72dbc62b5202e8593275d21b4f8"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-publisher-stage1a-offline-trust.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6cb49472fff0902c83101fd1f5184fde5af26353",
      "bytes": 8020,
      "sha256": "7e5832ac439c1bd227296ca6e7ef2bb4e93ed3301c89106f109e07582140d0a2"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-retryable-reader.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4adafa5a25929b9f965efb89b8f6f057414bd043",
      "bytes": 13867,
      "sha256": "ad4cfa0ae2ef73a8149ef0f7f386838af82784e42b3e90f4ec3dcd4069d1625d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "37e2425fd8d247988e0a4e3dbb30534158a42bcb",
      "bytes": 1197713,
      "sha256": "fcf87174cf1f7caf56d1cc3c675b93a77d849b939fdee5b6d53164f233e7ae17"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "1ddd88834ed71876258dafe3137982ffea0e019a",
      "bytes": 34021,
      "sha256": "74b4070d17c7d432dcbf56046093dd1b2d5a13a9e98e3847b23573b56696456f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-staging-boot-device-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "1bbc47402a9306844d81ee24a27d087bbc5912be",
      "bytes": 125609,
      "sha256": "a47ce650807417611c26ac9d33b9b5828b3947a5f55bd44481c72e5662d98e82"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-staging-boot-device.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4075f681007f737fa7c107f19a865f02ffd37662",
      "bytes": 4100,
      "sha256": "81973d1b7d340723502c252b807db289fdcc9086215a4ff24791e57717d1c4ee"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-staging-bootstrap-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5079fff7e10443881c1b29db01d5d8866b147dc2",
      "bytes": 71646,
      "sha256": "dd732b5f713ef1d1eade8c970d64751a28529b1d02e88618ab5a2712b9b34f3c"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-staging-bootstrap.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "83d42b34bfc052fddc41f4d2648024a895d0d32e",
      "bytes": 4825,
      "sha256": "7d6e33e340c1d306cc6e70afa9d1a67aab49d8f27e2590b01f0e19538de276ee"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-staging-m2-host-install-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "31b84905efe0b356dc48982a476fc8f2ff780af9",
      "bytes": 891059,
      "sha256": "f5b51d0bd3f1189c4304d27dcb2375e5b82daa61661fec904a38dcbe7e8b5993"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/records/2026-11-04-workshop-staging-m2-host-install.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5a73791d9835e3e4154aa30adf3b5f839395c127",
      "bytes": 4070,
      "sha256": "23f6aca2790bf722914210f843d4643e6459cc809f562636e62c6c7ef38d49fd"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/specs/2026-11-04-workshop-final-reviewed-leaves-integration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "692a877faf61c304d893f75713fd5142c6a926fc",
      "bytes": 10501,
      "sha256": "6cfad85a0617a27ea50dfd7046c6dcd727e048aeddb87bd8de14286062a5a4bb"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-ci-integration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4946383f665f5ca7861eb63f295245cdc09b1a37",
      "bytes": 23483,
      "sha256": "e244ad120aa75ffbb5b5a965be2a236982178aae355a57664706ee2c95fa2425"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "24ac3e9264b85eb914daa7805d183e15f58d374a",
      "bytes": 122350,
      "sha256": "c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-inventory.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "97a3ee48e443547f538e369ebd4557644e9fec3c",
      "bytes": 10852,
      "sha256": "55fc12a771576778fb652ea8fcc3e8b81492ff3abc6fef0f00cc7fa3b015037a"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-runner.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c0948a5b604b9ae5f0ce31ab2e7864cbc9b8d527",
      "bytes": 33663,
      "sha256": "24d209a60ae2dcda461d1a65932c2dd37d6894ed7a9c3920f989fe8ff0b20ba3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-stage-b1-identity.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4a29e0915c677a2f07e3ca6b0ab9109e888651d1",
      "bytes": 82081,
      "sha256": "285e5abfe824b4b9490af8e4b2fa3655f53ea34d8afc631e69a88feb909d242a"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-stage-b2-catalog-go.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "584b12c2b880ae328ab39da73753a6f0e4a7a8ba",
      "bytes": 73739,
      "sha256": "c8e9a3f4c663fcc9e43bab3ef84e9e8dd978a4d29fa75122acf9372e5e22cb7b"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/specs/2026-11-04-workshop-publisher-stage1a-offline-trust.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c5c64de383d305892abc6cf2c7e3937548f8306b",
      "bytes": 24783,
      "sha256": "2f0504de9f7b7f7cd6c06b9b1078cb4b5b96909b5b1f3095b64a28e38389b9d2"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/specs/2026-11-04-workshop-reviewed-leaves-integration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "d676bdf3009f6c357dac7148dc7bb6a9996cffd0",
      "bytes": 34664,
      "sha256": "d471956b9aa4bd4a3977b330425b11c24adadc5b4e898c98a645c81cac5c22d3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/2026-11-03-workshop-browser-client-response-loss.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a8bad776415252e95004e86612edd1806cac9cad",
      "bytes": 4542,
      "sha256": "8fbf3d5fb8f87bc243e20eb6dd6ea6557b7d3e95011b7dda89980a63af4536d6"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/2026-11-03-workshop-navigation-recovery.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f6368741505b72b9993ef121647eeaa2e49b6e53",
      "bytes": 4609,
      "sha256": "0bbeea1c2e412abcb549e61478158dc9fe91536653c2c3d77f67f040e6716eef"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/auth-error-cache-headers.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0bfa340586f1b5ee2e1e6830d0c219143ee4567d",
      "bytes": 2877,
      "sha256": "62d7ba898f2c9fc78178b31c7921b50083148e293d6a4bab7ef774cddf1cd1ec"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/ci-dependencies.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "fdb7d8eab491c341e5b8e777ca6addea3418d7fa",
      "bytes": 2911,
      "sha256": "831f4468fc5f5c91b76cb6b22bb39987c7a1ab45b2a55007f626f2e0e9596f45"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/dev-test-discovery.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "fd5609993cf3b0a93eef445386f8246907897d5d",
      "bytes": 2919,
      "sha256": "495c3c8052ac54a357edc0db6aa19e3f30b0f7ed149769e333c79740aa905f69"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/identity-session-probe.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e083971f78715ca530d1ac7e09f0ddf31ce4ac2a",
      "bytes": 4970,
      "sha256": "d9c1973cc0cb710d0ef7dfd6a0d3d727c7e9283e4894f8089feaeef6367b7b90"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/migration-replay.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e037105d6b374d524bcaeefd551ebbce297d2216",
      "bytes": 6879,
      "sha256": "3c9a31e06ee03109d45d0896acf45d3ba3deffb0848bfee85d83cb361b7e60ba"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/queue.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f0fe4ec70237bb9f70e1a6f714a9fe2d862761b6",
      "bytes": 144527,
      "sha256": "566c7fbc3277af711cdd422f986d90d731314f4c0d1904b98dfec3f17203bbf4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r0-app-server-runtime.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f21a7e6cc0101c31777b73e395f1dfd89c5a3d17",
      "bytes": 5385,
      "sha256": "130c4e4056fcd071fee0881f8e20ec2a43e85201c3ca1e27603cb0f9287fd1a3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r0-evidence.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a84df848b6fb852ad75a5224063dab0a930c88fc",
      "bytes": 3746,
      "sha256": "fa262890bf95ca04c26c6707b5d98d4ccba02817045f91476d2be7d2fe2f60b2"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r0-provider-path-schema.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "597297a495e0ae78127df318e4b622dedfa5b205",
      "bytes": 3001,
      "sha256": "d0b927067d1ba8898860553b6922e9dd3bf17ceeea2d3addfe9db44495df8bf7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r0-provider-schema.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "58d55d09adaf4fadefc9317da32c0154735c9f57",
      "bytes": 3074,
      "sha256": "b3678d233b2d4a7aed3360173e5c3fb9674fc45530f55f936c0d27508cf85168"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r0-release.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a7bfcf3cfddba17d4c39264efa6a59b80f92296b",
      "bytes": 3410,
      "sha256": "3e97743a391778345690cdf97819ebd524ddaffe9a96253e2bffe35ea1b47112"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r0-runtime-check-contract.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "9efe7f697dc4f3df3b0e60bcd964377dd06faf91",
      "bytes": 4432,
      "sha256": "ce139da11b0188034b1617a0f0a0be0d9723d396be81ea2482563a283f6f20be"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r0-runtime-disabled-notification.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c825583641fc57f1c2d9f7274e3dae357c4d1732",
      "bytes": 3974,
      "sha256": "f911ce35c532fef5a341fc2c32868ed78a3d833a3d82cc906634e833b599f38e"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r1-connectors.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "3a95fd802f1857561fc1b363cbfd84f5f1c33b2b",
      "bytes": 4783,
      "sha256": "6c1dd39e4b9e51410a8e71625900c0bdc395ca7d1fa9e2521187192b07c286d8"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r2-rewrite.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "038e50c25a369d6166aae5fed0aea0c245cfa786",
      "bytes": 7444,
      "sha256": "429bb73dadf729f6be164d25c71ba643a933903695e6dd3dc4662c24be314fb6"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r3-fallback-api.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "726835d2b58e9f395e34cac8f1ba31be30b1089e",
      "bytes": 6520,
      "sha256": "f356c69ef401668fcc35ba2a5883970e5c28b2fda24ea247206be7b0d62cfb99"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r4-workshop.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0a3a178903be406c09ee8d62b3189ed5d3f2b7e1",
      "bytes": 8476,
      "sha256": "5a5c5271240c1f3524db30146b3d0f387eb862919859f5e14ce06c1f122e5dc0"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r5-access.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "1790d186885183742b3f94899c4386bde1aef9a3",
      "bytes": 9282,
      "sha256": "fbd97c650dfe8e64391b94bd938327b381804c4adc2ddd29ccf765a6f2879107"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r6-dto120-receipts.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "82495e689b9da53f6b429c53c7f4249a6f8ed6b1",
      "bytes": 6906,
      "sha256": "27758b1f6c9660eaeab8a7657df8985effd1485104ba1549f74e0c0d8085e819"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r6-evidence-adapter.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e3b90f9cdeff0ce0675f9c8044becc40f8e34aa1",
      "bytes": 3634,
      "sha256": "bf2564e612441877bb556ccde924f5188c94e673040343f10ee85ad019afe4ed"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r6-paid-http-receipts.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "b9d3fad416fd8bd3d605a19e7fb53b04fb2c5f40",
      "bytes": 11892,
      "sha256": "99e96ea37d9b3cd7bf0554326c3bb28040a38c8e5c61244fe803e760795b057f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r6-paid-scope-receipts.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "88a4051f27ee082d1d2d0b83186e37ea4dca6a10",
      "bytes": 41168,
      "sha256": "88a8245934537b7dd3cc8f9c205ff3016049af69f3a86702afa33e856b367d94"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r6-paid-selector-work.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ca4525cc5c79e6b546b86a1c5e19ad7f1c930a08",
      "bytes": 7448,
      "sha256": "b857c9b4a7fe73606b0da78757778098025da559b56bae6157bd08acf09e3a8f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/r6-release.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ffba5de786aa9d628c04d732b08c63d1a6b6890a",
      "bytes": 8727,
      "sha256": "e980162ca709b3b7622126ab943a3a9f4c9efc7e3d51eea30d9bbe0699aea5d0"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/retry-queue-test-clock.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4d7cef71fd87713eeba934194af08fcfc3029f98",
      "bytes": 4679,
      "sha256": "2648b1ca678a1959fa04c2edd8dcafd69bb1742873258b518baf20ffa1b7b6bb"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/runtime-fixture.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ac773998a116a17e28770e86622eb923456a4c24",
      "bytes": 7838,
      "sha256": "22eec3b0e0ec3f2eae0c4b79534cd2e71d0087920bfa70971259989d4462b8a4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-artifact-boundary-corrections.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8c73aedd249a0ca297b3d0fa7a3e67144bb7d4af",
      "bytes": 3422,
      "sha256": "3011fb4b4c8a613dfdb402b9843379e66a73766a632d5565947956f488d5ae66"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-artifact-inspection-close-failure.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c788ce96e84287ca5ddf1c887d6462f0d5639794",
      "bytes": 4462,
      "sha256": "39be7fba1bf26369517e5aeabdf07ddd570a9eb3b0531f7e7a6f1edcb75e158d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-artifact-revalidation-deadline.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "9e600c49fc4de17a19a7a38c3f0728941ff092c1",
      "bytes": 4104,
      "sha256": "d72cb677604f1bb6fe611c8593224f897da9bddbc76cc9e0e964067c139f3e77"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-auth-provider-readiness.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c2f4065efde4031182ff94da0c30a7c308c5e246",
      "bytes": 5535,
      "sha256": "afb7956f405906c73050d15d4c0430c4c056d7ba4817f6f1e3b83ada33c2507a"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-authenticated-publisher.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "b2c846f14ca14cb158c76ef06c253e1b91cddabd",
      "bytes": 8058,
      "sha256": "59108ce8696594ee2e24b0b408f0aded5d3c5c052ccfc7bae8c0dc045b150f10"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-browser-account-media-status.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "59b95f1505a10b8347c8c450f487311a001120c0",
      "bytes": 3714,
      "sha256": "d0185ad60605fd091451e26715a3830e488b30db409a865b5a6a597f1f72d181"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-browser-private-home.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "09d3129bc327f04da967cb5d7a432e9134b9e743",
      "bytes": 3938,
      "sha256": "30c4de0978c0786e54c1c37d7036e862cb85a2b02c54acd5f74704f33db007f3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-commerce.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "df2b485dfbce78b44b57fe444bd507b7019a4bd2",
      "bytes": 7432,
      "sha256": "08e2b14a4b00a947338b30ae7c052895c05c5421e78ccf106fec5df85efbdc2f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-dto-timeout-diagnostics.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c6faba8892dc06134838bcdbac7d7226ef45c80b",
      "bytes": 8588,
      "sha256": "2e435fa853a6a18324a8097ac79853831998a53e7ffc6ad712ccc890913a4c0d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final-reviewed-leaves-integration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "78b1ea7474071ff136c0741f7b01dd7e0611c42f",
      "bytes": 36119,
      "sha256": "e9a12d322b01882d068b5351d68478333b34d6f355b40c3e88f67a5f41cadef5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final180-ci-integration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8ed54b75225ac03831f94d7ac7ac9b6d7715b8bd",
      "bytes": 14559,
      "sha256": "b039bdaf9c6d3fadb1d862c547ca97559179c505dc6fa2de564d272591039e87"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final180-inventory.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "1647f0b2336f8120f67f48982f0b0e058d8ea43a",
      "bytes": 4767,
      "sha256": "2865b74f92553928a78a1fb793c98f818f0f371634836c28741b6082ec1e4795"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final180-runner.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "660a14557b1bbb9123b5a648b654d45182fdc6a5",
      "bytes": 5206,
      "sha256": "b2fb8ad4a73316e0296bdbc477a458a29d10d14c88483ae321bb23cd4eb901b7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-b1-identity.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "3120ae8753aedb4cb5ff0ac3dd9c8c662675e2f4",
      "bytes": 9719,
      "sha256": "7f8f437f7b536c327ad7135ebc8aab64ba8ff263363358f58bd19739df81a573"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-b2-catalog-go.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c67e0546ad2a14d6d10c526a90f5b86c113359d4",
      "bytes": 10698,
      "sha256": "07f82e707b106816ac533b86c24a7f8c3abffdc1422ac4aa16198ea91a4b3ce7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-firebase-bundle.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "cd894949472da139e3ec9c51fc407fdfca0cce6a",
      "bytes": 3590,
      "sha256": "d8462e927569e1cb6e95490117d7e4b011879834bb1e62209cac957eb1194d3f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-hosting.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c98cc06dc52235690f7b0574dbb22347486d5cfa",
      "bytes": 34803,
      "sha256": "e0be3d53faf9e10fc9f7627b833bcaf7da080948def69672b5fe277cad8cb9b4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-index-readiness.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "97cee4cbdb34fbb9f180cbb3e781ef2883fd874d",
      "bytes": 19659,
      "sha256": "90b579fbb1147c02d42aad33f260949866342c0fc95381d687ee739bef7a2a7c"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-migration-build-arg.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "86de6bdc96710858375aec15277a790c23383c09",
      "bytes": 5976,
      "sha256": "4d72c45bab0fda706a7427ca6f9e3f29fe4929a3415396deab656d9628df0452"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-paid-access.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e5df42e40f79ce86410253d672ec8c6a22a266f5",
      "bytes": 6006,
      "sha256": "6b096c525b7dc7d8aebcab7faeda5555f642a5b52591635da72be1a22b604466"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-publisher-python-review-corrections.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f64c5b443b97cfb898e5dc5b90ba05ed28a3d024",
      "bytes": 6726,
      "sha256": "fadc43d7c1128a5595294e7d2ac180d438134282900b713ab62a78f604e26cc2"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-publisher-sigterm-ordering-amendment.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "89bb11bbf6955aa3f1963bb7e768f0cdc1f67d38",
      "bytes": 6519,
      "sha256": "741d7e6556f4b0471a3212fa13286a1263a6b304b9d2762fcb975a8b3553941e"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-publisher-stage0-integration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "921a00a0355af11f70f5ef5695aad37d9371f486",
      "bytes": 18225,
      "sha256": "1643cb5d8d1513ecf810a852e05b1be741a9da34cc403427cbd9c8510be0add8"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-publisher-stage1a-offline-trust.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "2067dff2614024394b509e9d4b5e21e886046f55",
      "bytes": 9797,
      "sha256": "ae7077736cde53be30fd559be3bad40d545192139bbc15fe94cc595483c5219b"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-publisher-transport.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6be4547323a5651a79526d20c5afda59f52ed800",
      "bytes": 6246,
      "sha256": "9c7ba759c68cc316bba6eb0d685b9f522d6bcbb0f5b08ea9ef475bddbf435ec5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-retryable-reader.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "dd784258af2bd5895d0ec43c4936605bb8e2104d",
      "bytes": 16617,
      "sha256": "474a1bdf89288dfd518e4142b0281812e84ffdfbc66a4f56e6bb043f3e8e0acb"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-reviewed-leaves-integration.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f0aa547bf6c8964aaa53d7bd0d8b0f3f04c921f4",
      "bytes": 41051,
      "sha256": "627c7c50a30ddace6fed690eb8b5bbd17a3777033e5ea07cea1864da95d7921d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-schema-observation-harness.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "12b35c991a12ff2061699af3536d8d6ba900693a",
      "bytes": 5758,
      "sha256": "60fc95640814707c9e5565a018518be899f820b0b4e70f006668361feecf83ee"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-staging-boot-device.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a7a60bdd81e18506cee0a8d7bf93ca57a4ef5c88",
      "bytes": 6655,
      "sha256": "d4406ca1243dc5129b37b8e2c8d4b866bf0b65c477b95f977ef74e7162b02578"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-staging-bootstrap.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a9b3abba26af60b9ae2a5238fcd95bbedabcea28",
      "bytes": 8534,
      "sha256": "5fd303a27e0d4c53f49d359c7ab68f8829b02a73668ce55616604f1e58c90fa6"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-staging-m2-host-install.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "b2ccb88c027373def83251b993178bdc0b9623b5",
      "bytes": 6651,
      "sha256": "00675cab2adfbb37d3742a5c42ef67fec72b3af602018812a2e9abcc150ef4bb"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-staging-workflow-regression.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6b23f60a73d4ae67c31552a612cd9532a82f11d6",
      "bytes": 2500,
      "sha256": "95e46209b827592fdb19bc266e42f11c45293a819b1050142cd0ca102a07ba34"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-10-multi-component-job-composition.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "3ebf6d0fa292ee76d759bc6ae77ce9703af5c0ed",
      "bytes": 40172,
      "sha256": "e9c8ee06050a37dfc8fb011f45cf4f2213a1de70ca37fcfb789e0775d3dd8eff"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-11-natural-language-quote-procedure-generator.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "bcfc34ed8d5596563a0b2102947109bcc8a3b1ef",
      "bytes": 48661,
      "sha256": "41cb71f96ae85645bc566554691cc6b5328d266962d46a34eae7c7c54f5a8c6f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-11-pre-implementation-gate.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4e8d27361166d7ba2be413aa2cd5503323a4082f",
      "bytes": 9168,
      "sha256": "b2029a0c16a3d8fb508e6ab440931cf5798ca43edbde3244cc89261868818542"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-11-public-facing-readme-and-wiki.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "921edce37353ec736c5f01c2765daf25114bfaa7",
      "bytes": 10539,
      "sha256": "56aa861d536d161a44e1f8094541c7ebb051e46a344130bc6da9e3333d8b8b77"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-14-consumer-repair-guides.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4a434c8570a8d6aff179e3b7afdcb83e15913358",
      "bytes": 5081,
      "sha256": "0c410f42e47d6cbcf252d12e6ba84ee9d00cfa7192e627383b88aec03b523ada"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-14-consumer-review-agent.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "781bda7945627c47800b46914dccbf9b1da4f056",
      "bytes": 21235,
      "sha256": "e6b7f8c58ecae04b7ec9298bffcc45d0387ffe37adcb18075d8ec402da5c5b39"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-15-chat-source-failure.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "b9f5b371fd7e2f69b687218af50420782c0b8d08",
      "bytes": 5018,
      "sha256": "3626af0d021b62b209258d0f15ca16e0ff981017f21d914b23b6a1dd4429b021"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-15-consumer-agent-artifact-detection.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "00beef41ee6b4d61300ad5486d6be3faf255aa18",
      "bytes": 2888,
      "sha256": "803aa32ba574b630551cdac499c0b68873df7d150967216ac49b84ac4c618a47"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-15-consumer-summary-filter.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c6f4b6b56d84c4882086965852192fb36c277f21",
      "bytes": 3546,
      "sha256": "922747858583c09c44ba8b0a6e28714a8ebf10c2b33378760539d1034c61b17f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-15-html-guide-and-silverado-label.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "702204e1696b3bd959fcce05dbbdc74a8781d7c6",
      "bytes": 8814,
      "sha256": "35c13ef282271ba2b698fb54444538e296d0a78c08010e5f902935e957a080aa"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-15-minio-compose-ci-image.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e6a1a4d9243defb409e03563103ed44741dcfe48",
      "bytes": 2669,
      "sha256": "4b750394fa82c6c7f36b5e539be70325ca52e9604089bcf6250d9dfc5f3e201a"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-15-negative-completeness-gate.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "43de2c5b58f4df3c9973a57eb9af4e14c19d663e",
      "bytes": 2529,
      "sha256": "747316f58cec31d764563aa60d4c3859a1f87582b73a03b195b3b6b02c5fece9"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-15-pdf-caption-cleanup.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c8c08f765cb4e78ede41b53fe368e5c42608d164",
      "bytes": 2845,
      "sha256": "e428d2d13124460cfcbd16253e7a027f744f632f8a6aab2b00398ec3dc2ed8be"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-15-rav4-4wd-consumer-matrix.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "cece24d12800f9de2a190b0471df3588e08d64bf",
      "bytes": 2729,
      "sha256": "c4ff626c6b63a3727a4c6cdc1924f2187fa64be01d365535c17085a2fcce1bdd"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-15-source-fidelity-procedure-hydration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "3370080c53883210fbb6a2480dc1d4c03228efec",
      "bytes": 7446,
      "sha256": "b9544ead89385d53ddeec519a064a6d1cfe9c13994d57194da4881933a6e4185"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-15-vehicle-specific-guide-label.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "80020eb4f16ef352c03fcd032f6afff4cfe74d1b",
      "bytes": 2740,
      "sha256": "4c449b934c2ba5aac0e4b8d962c8194a215a84eaab7b2b9b32a04db15b16bfae"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-16-evidence-reference-deduplication.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "2613a12369e00241aeae648eed14da4abf7db95e",
      "bytes": 3026,
      "sha256": "99573c75450e86f7438f98ffd0e86f05170f3024ba92d256e6647cbec50bc427"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-16-procedure-artifact-navigation.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "aad285b3d23373578e92b4f7c01c1fd07141668e",
      "bytes": 3686,
      "sha256": "d4f1591a3542be7f074e8153da2a020bdfee1f60f76d4e698665adc267f55031"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-18-provider-neutral-vehicle-identity.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4227f1613def349ea80c7ff3aca952314a974eac",
      "bytes": 8142,
      "sha256": "7fb4996cf9d5c5468f05bad10b35a8ba91450a436c2fedd4f894b81d70681b2f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-19-mercury2-overlap-procedure-composition.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "bbabf1d28029ee765749eaf803a88b1854b98df0",
      "bytes": 4508,
      "sha256": "8be80eca79bf2aa31c4661b36f7b57d1053964765dbd3de57dffe0ae7bec52dd"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-22-fixed-order-diy-ingest-local-images.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "01aac63095cdbd80fd32b711b3bfd8f95f446aea",
      "bytes": 2015,
      "sha256": "c47559c03f68c297b2a2a5fb66b30ea4a064646e01c0ad429e265dd657167ef0"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-24-openapi-swagger-catalog-api.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "fe953a865fdf0a3a00725627cafe854e6ecf2129",
      "bytes": 1290,
      "sha256": "81783643306b169da0a9aa65fb5db74be96b31b3290383c3d83af87bfccd07c3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-24-provider-neutral-catalog-api.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "cfb9ed41744af502e01a4330cd05f83920e58fc8",
      "bytes": 2576,
      "sha256": "25db8949e802cec71dda9bd37854f6572467c566603e50cf2f23ea0428ab4fe5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-25-workshop-interface.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5fc4a744f815aa7bb48a1d00a022a1267b7179e9",
      "bytes": 3706,
      "sha256": "a3b4815156012e67757d19201f050e69f9df58685ab8a267eb0bb860d6e63de5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-25-workshop-loading-progress.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "33d764ffb144cccfb2d65780154c89dbae54e559",
      "bytes": 2339,
      "sha256": "913ed97d178b3aeb67c875e774e6046ececb2ff06345cff795b9f28a2520e23b"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-26-article-catalog-list-only-hydration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "212f7ea16a4d63eeef8aeaabf65ae0c6a2eb72a9",
      "bytes": 2782,
      "sha256": "f7b6b7dc46615786dba468e130f073fd2466c7d9b6fb9581ace9cedf7d969da6"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-30-catalog-source-review.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "9777d2fc3f6ef9d2d0087c99087b821526c98c2b",
      "bytes": 7838,
      "sha256": "103c8952e374034ca3ec2c9066fd68e153bd8e9545ce27a02a973de649fc28c3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-09-30-ordered-article-document-normalization.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "d4062be0df1f06c5accbf50298753cce93664f3f",
      "bytes": 4194,
      "sha256": "88451463bdb617e25e3982a11d5ecb3296d28d6be8183bf2bbfd79e3ce56cc3d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-02-opaque-source-media-paths.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "05e5597918fe497ac161fdd62d53b28ba81a4626",
      "bytes": 3718,
      "sha256": "8f4713101e65a7b1929036f8acb23fcb6776b5021ca64d7c7a101f3229ec79f5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-02-source-connector-api-compatibility.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "9d8b12cdaf82b24e74e7946dff7da4e86273b232",
      "bytes": 4632,
      "sha256": "41edea79a5a458b7d282845257789ee42491e392537992f2d9caa3b6273d1496"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-03-autodb-two-response-shape.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "1f8c039a46ba67b5cce39a99e3d3b21fcb8f64a1",
      "bytes": 1720,
      "sha256": "4d97d421a44cf4437e29969ea6dff794766f2524a16d8d0400871e06f8f45f42"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-03-ci-s3-image-access.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "165fe2929ca8eaf25ae22fc1020c9449b108c81e",
      "bytes": 3351,
      "sha256": "ca3d7cbb7cf04b2ed27c79785d5c6c6b8dde6d811e6bf05fd95ffae45016aa7c"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-03-disable-chat-active-path.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8b3b452cdd23bf53a7da04aa6b36ff31c0f4a62a",
      "bytes": 2532,
      "sha256": "fefb54dea76e6320c5d0c21f90a6b9b6f3701cea5d68ab97ef7edba0cf08f6cf"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-03-public-image-storage-key.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "61b632b1f34adc575a2570a0230423f186c195d7",
      "bytes": 1494,
      "sha256": "c02083526acb0d5aa27c6fad7735c0b2b70c7fad0c45b73f8ffd034cc8175557"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-03-source-review-container-assets.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "48814b3a76c70840f3df03bc28812cf29b6c1478",
      "bytes": 1689,
      "sha256": "5797458d12654b0e1b7952ee842b6ce618555b35f5bcabcd8915cf4238970c80"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-03-source-review-opaque-images.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ae6eab9df3f6bf3900b6c8d9d304afdeac378306",
      "bytes": 2037,
      "sha256": "85f06ed3ae2fb373e2d443f948e570e4b82e6ec1a9cbb196043af22b2ae56402"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-04-localized-opaque-catalog-images.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e1af1dbff598a399eb98e0582b57693d551c40ad",
      "bytes": 4351,
      "sha256": "d5d2298161a20c695689b9a9460beee775d74503159479c6c1eeab3a0df0dade"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-08-bank-internal-rename.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "552461eed45c3bee71a2ee859ab5dbdfadb993ba",
      "bytes": 1393,
      "sha256": "3e9edf7c602e6f6b89505057bc0ce71c2f9ce5225cb365001c08b0a794d4f1df"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-08-catalog-step5-usable-configurations.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "d4d2545a713fef5fd42f18e83ecd0a3002e38c32",
      "bytes": 2202,
      "sha256": "45bdbd3f8e61455421f37b2cc1823b371916b607a0cb2dfbfe893b0a5de9e42d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-08-independent-bank-connectors.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c3f7ad7969a1ffbb2b11f1d36e53c2bfde096b15",
      "bytes": 13961,
      "sha256": "fc4567a15c5e12510492eee119db6ab3c7382c61f39d4f20277dd18fb5e57be4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-20-workshop-bank-auth.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "9bb1abbeb352e07e8b92fd2c778e2ea468e6a2c6",
      "bytes": 2836,
      "sha256": "3462a0dcdefc0e2bade92bfa6f30efa1280e6e2702673b92860fe19662cd1678"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-callout-step-images-persistence-address-cli.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5fbae22044891d89955a582ba83a662a4fbb944e",
      "bytes": 8493,
      "sha256": "34c91680155a26ed09345fa37f56b417f5461e50b860fe272dff466f597840f6"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-connector-routing-document-hygiene-cli-ergonomics.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "7be4a112c9daa0106aabd4975da6315641023ea8",
      "bytes": 5164,
      "sha256": "722263bb169ceb8786990fb4d094bf339cd079bf7f7f7d6843bd6afbfb6de183"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-document-block-image-hydration-outbox-cli-ergonomics.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "02e92045b31fcf8d135a94908b81fff90b609c71",
      "bytes": 5012,
      "sha256": "7bcd716c33970ce76125f2041753b95c1ea2d94e6c50a774d6eed45fc52df2ec"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-document-hydration-contracts-check-developer-ergonomics.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "27bb4192b8731d9e93656cb5a5617fd87fac61d4",
      "bytes": 5407,
      "sha256": "baafccdfa97cdb5ed1cb3d4989add388323c066b75ed99706c0b86c86f7ef212"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-document-image-dedup-dev-cli-uniformity.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "9b00c84302c318179b16f5639d31acf368456f74",
      "bytes": 5384,
      "sha256": "72bf75b900a915c788e8e7f38b06685b3012b1a6e3c1177a06de5451ff9679d6"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-document-image-deduplication-developer-ergonomics.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "10a4ec107e36b16fca996d2c0bfe27784894e900",
      "bytes": 4575,
      "sha256": "fa4b74f350824404e2e824ea4248213450e9d516b8f34f32eb56ca66e451ef7c"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-document-image-localization-preflight-cli.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "45013f603119b65f9a947a13c7f0258d3b73ec3a",
      "bytes": 5185,
      "sha256": "4212081d0daad8055ecf7006f72ce856962836ff13878d330ca94f6c34409fa4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-document-normalization-list-images-cli-uniformity.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8df8b174456a06097fcbfe68d3fc1286385fdeb2",
      "bytes": 5431,
      "sha256": "4a785fdeca746d867459f152e8ffc49a65b256256f17dd08bf08dcb2db1f2b2e"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-ingestion-persistence-resilience-cli-ergonomics.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "3a7cf5605165fcb847e116a4c58ec51221c4a211",
      "bytes": 4785,
      "sha256": "4294a7961886c495c412b6e41453cd35f31b3ee380feae61d42d3bb50b88e2bf"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-list-labels-asset-refs-cli-uniformity.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "7f24ff00d706a8e63faed60ebde0ba048f069c43",
      "bytes": 6643,
      "sha256": "3213f1e9922aeff7ddaa08a09ea9bc370343ec58ba61b152496d418d214a8039"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-nats-resilience-bank-service-filtering.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "366b121d5db2958c117899b6e75f0d5f95f21dc5",
      "bytes": 3381,
      "sha256": "ee5b7c9c4c9aa5ea62ed07f51da68ca98963a9233331ccbec1acacd5c0e405b6"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-outbox-relay-persistence-resilience.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0fee135fd5ec510ea8ef181e4e800a649a899854",
      "bytes": 3796,
      "sha256": "9831f3575c59ca7ebf4732b382d7433b31078c17435c141ca9d2f5fb14f1d142"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-pdf-figure-extraction-data-uri-localization.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0d75fb5b0902b507b90b132b624cb5e607891059",
      "bytes": 4934,
      "sha256": "745a9ecda4e91bbb35423caecb4d8cfe7e702627061ddfcc194f383792f7dbf0"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-step-block-normalization-dev-cli-ergonomics.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0e1b35fc9cecfbc23c12830f24d16c5f2a372e88",
      "bytes": 4829,
      "sha256": "d1465d425b19184de77e39d9cc82df3d5dd24f50aa06130651ffb56581cb627d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-table-figures-callouts-dev-cli-uniformity.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5557442cb681a3e95c2fab13942d6668b0e96e44",
      "bytes": 6462,
      "sha256": "baeb9abe3edde3d6f5bb57f5d08f55243b4499bbfb6d7a353d460cafcd2533c9"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-table-figures-document-hygiene-developer-ergonomics.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c7cc41a004dd943db59295fefa896e13863c25aa",
      "bytes": 5746,
      "sha256": "476c11fc0d4c837e20875f2fad0821537d566109d05b9db7b4908c0284ee7611"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-10-27-table-paragraph-images-persistence-address-cli.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "db94f71bbbf9ad9cdab586a1c8aa5cc44a12377f",
      "bytes": 9074,
      "sha256": "1b5f75addbc7b54d18994af72d0f2d54093542d6a4bc72fa2fd2928f8052d7df"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-agent-evidence-hardening.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "45c2417c0b6981fdc284c48d4f0b303bd0aed70b",
      "bytes": 47286,
      "sha256": "c4772d247fc2cdff6f27c10b35915c916e26c33a71c4957e9ba72a129af7284f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-app-server-runtime-contract.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "bf05849a8d055ef331ca2f333e98f637ba0f8a3c",
      "bytes": 35751,
      "sha256": "fd0459a1ee1c1813b24e79ee0786a1153d724ef038f4253c2617947c3d2dd5f5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-auth-error-cache-headers.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "011b434a7a3c5add647a5ba7ebfd3ef8906bd6ee",
      "bytes": 5111,
      "sha256": "4ce486e2c05f6542bfa22d16d37a9ea2d6573e6faa4d085983df3b0ab872b6f2"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-canonical-article-lifecycle.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6ea53ff9d73f0f58268d9d1eadb1d10009eb4521",
      "bytes": 52884,
      "sha256": "0f6d0b8b705116513fbf24fa2a245f805767e69e8fbad23822eb896ea5aef25a"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-catalog-runtime-assertion.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "48ffaa4a393c464d544c91139489a440f705596f",
      "bytes": 1790,
      "sha256": "1ac00114a6fdca4f378a06e56c2828d57c286a8d2957d87a978201a3dfe3a9ef"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-catalog-runtime-integration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "d69d2d84b8bd8e43047d138383882bfe6908e032",
      "bytes": 72719,
      "sha256": "57664b16e55a7637d56b0b860dd4507405eeb00f0aced8a5c29e579c7823c66f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-catalog-test-race.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6b8782086d9f5e67043ca4e1dc1a5d24b70a7ac6",
      "bytes": 2733,
      "sha256": "31d3fa0d16da702144a4117eb4be90863c8eba5fac44f147c2f4bed08f6c7435"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-dev-test-discovery.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "729e5531393be06c6109149fd03e7d3f0638405e",
      "bytes": 5306,
      "sha256": "3a1a36831f279e191afb002caf4a1a36061f90ec2e221d7cf0f727bfdd852be9"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-frequent-commits.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ecbadc80c2659af2eb0005ea50794f60c8b84a76",
      "bytes": 1557,
      "sha256": "211ed44ba570bb9b85065457e99c03c68d6dd4e6d75a614c0f12965737f61c2b"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-identity-session-probe.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "3f2c982672c37ece2d1218ca2c5be1a21ce66469",
      "bytes": 7740,
      "sha256": "32723778543fdb35d34377b96f61ab1fa3c971626185b91f1798c29d7147cda4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-ingestion-ci-dependencies.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "b43c8fb522bf640b5664ad09cf72f762d77edc6e",
      "bytes": 3599,
      "sha256": "143ff2c2bb3f8590584c7b91f50ec5cd913692cb8dd67c7ee072a0dda4483447"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-lifecycle-migration-replay.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "cecd1ead3a1efee04ce8497af35cda4c65e96c1f",
      "bytes": 23999,
      "sha256": "0bdcd6a233c2178e29d635da933cd02a64f271c8d2f81639303dcbf16f13510d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-local-cli-certification.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f2e1d2aac1a7a1033eb9e9fbe3e695f4b017674f",
      "bytes": 3227,
      "sha256": "7a1e553e513db1656c963b8eac2d80ba30395b748879f2af54bb2c035a2dccb7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-nested-image-evidence.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "9db18e0dccd0900cee135702799a2777317e4b76",
      "bytes": 3230,
      "sha256": "8c1eea62f30a0dace6187e7f79ff08daff832866c8a13ca30bc45b372d86d2a1"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-production-access-migration-handoff.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "47fad5922430aa7243c157f0a81af7c872d01ba7",
      "bytes": 23135,
      "sha256": "d6cf5081255e9804fcce0336113fd8a8be03943355354a1b2316f347142956ae"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-production-access.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "119426f091d4fb3ea6413c7f30096ee4693aa849",
      "bytes": 11169,
      "sha256": "5ba17dc42bd83c528a718204316b48224e3ff2fdf9092ec28c6995c7498caa12"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-production-release-orchestration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "49edd4b12dfa119a7394fbb24fe9f6a05f34dde4",
      "bytes": 85629,
      "sha256": "bbe4768340e82f1da43acb01c2dd97935c1fb29f7c6a6b20fcbceab3f54d3982"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-provider-path-schema-compatibility.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0ac988e102a0c071546741fb62e0d9cb217cc91a",
      "bytes": 3462,
      "sha256": "5025722ba741bd4ce9551ea9adec0a353cd1464fc3adef0ad273f70d1248da66"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-provider-schema-compatibility.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "b9c97344921565cc6723e330cb63a9a9d52bfa7d",
      "bytes": 2779,
      "sha256": "478c0096f75f17c304e515a23ae87dd09d36ce21eddc271221b9c351eab0e639"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-release-acceptance.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "d7cf364b73ef5e30a44795ee5341923bd28e32b6",
      "bytes": 51834,
      "sha256": "b262f54d7ef9f73ff29da01e0ff96db97414a3c2f7ad349cef21e338458c04c5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-release-controller-preflight.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "31ebc5b3371ad40cc9a0bbcd614edb7a1ddc3bc6",
      "bytes": 12122,
      "sha256": "518585e5cf8e25694e9f84147e9056029f3e0f868f29b51c7fa7ab3bfcc4f4f5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-retry-queue-test-clock.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f5740c5007375153782933708ec5a70a921a003b",
      "bytes": 14283,
      "sha256": "69e07a52e1b76ad84747f05ba9668a5288cfbefa269434e969b85c3be08e46e9"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-runtime-check-contract.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "81576ae1c0e9dbdb9e1f4b4fca6204bedf04601b",
      "bytes": 31439,
      "sha256": "6a1cabd289bf404f19e8f038e4f63a55c53efcfc85503ec1ea6aace50f4a0ddb"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-runtime-disabled-notification-trial.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "3fd65e756d1c06130c4e73f6130451c94e2020ea",
      "bytes": 7203,
      "sha256": "a47923f4cc952a1c61f861a527558a703a0e359d5ce0368b182dda2d297fccac"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-runtime-disabled-notification.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "fe604a16e23abe56533e120c38f531c0511db124",
      "bytes": 25348,
      "sha256": "f797e4a7f7d88093dd4e4394198f5d5f51e5e280c6c13a648804a151236eff04"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-runtime-packaging.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "bdc4963bed866c93492bec7b45038f2278eb185b",
      "bytes": 10909,
      "sha256": "92f093f9dc9d38ab52b972918ba0c9d584645b6555be530ed01ba0c49d9c5191"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-source-fallback-web.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c3241f53eb56ea202c3d4ea789058e380b52b819",
      "bytes": 32945,
      "sha256": "77e12375e2f0fc586840ac4b8099de5d43f54b8bf990aeebe3fbcd6fc2491ac7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-artifact-boundary-corrections.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "38a7ae8eee089fe30d01c35927f6834713251577",
      "bytes": 22414,
      "sha256": "2b3f68349fba53f78c7b3bd434aec2622e05b8291d6dad3d8655f539ee6718db"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-auth-provider-readiness.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "10aba9abf63aed53a202d4a5bab63e250d17f2e2",
      "bytes": 11748,
      "sha256": "753059fb271c5058fbf85d3562e9dc952bcc94b243232da8085533e854daf236"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-authenticated-publisher.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "27c24c4d7501e3a12c596c13c422a251d4b03f8f",
      "bytes": 71386,
      "sha256": "92677ccd0dd1c6078bb17ae6c94a8d53b97eebdca4e724e36f9a1c57bc8df4bf"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-browser-account-media-status.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8b69220c7575121a51800652340cc57fe0a80426",
      "bytes": 8300,
      "sha256": "e83dce045711c92109c23136a9f833c189e8d32944f21ffb6723fe8a56aef1a1"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-browser-client-response-loss.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "88abcbc31a726bc01cebdfd84d7ccf3aece6973c",
      "bytes": 15786,
      "sha256": "6827e0049ae2afac9a287bea8fb96c9834422e9f9cd57fb30e3c927c02d04c78"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-browser-private-home.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a7d1d49081a1cb5bd13eb3404860347e14071222",
      "bytes": 4704,
      "sha256": "df2ea0b04cdb730e8013f1c3388b81c5aa5bb09a73482bd6fd7af2b18d443b68"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-catalog-region.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "589325a0fad9f0b4914173540842ddc55b1012f5",
      "bytes": 3700,
      "sha256": "19a857f59bf2e73432130176af9b7303fcc591bcf607b5631e753fef14eed24f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-commerce.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "2a4086b0ba210142acb01a1b4fef584a3ad1c5a3",
      "bytes": 50859,
      "sha256": "720fdc1516c70c0d3e7cf0a8282583c77fe3e8f9ea9cd08049efa6dc16c84f7b"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-customer-ui.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "e4811954040e86a45e3d3a611a00582eccdc62f6",
      "bytes": 49183,
      "sha256": "8751d4ebba7bd6ba1f73ee121919d11bcfb0df9408ecb95a305ade7effbca2b3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-dto-ci-evidence.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "aa11680fad184f5c64a623c2615770c4e8c1b797",
      "bytes": 3740,
      "sha256": "32d9e0efb80806e633664e35be7f3c6be5b55cbbf8833901b0c427a58c1784fb"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-dto-timeout-diagnostics.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "1c60de05d5c368b71a95b25ca090d1629b4921e9",
      "bytes": 29455,
      "sha256": "a28edb213eed53aac63c688eed4b67ed0becc4fc679123323f42d1c54630ef04"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-firebase-bundle.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "45ef535288b7a30f9e88a6e6c01976878072db22",
      "bytes": 7201,
      "sha256": "d374e8a46bedfc17aeefac702134bfee1d03fb22c10cabe7ae1edc6aba0ecba5"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-firebase-identity.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8cd0db51bda496888edca56f40aec886c56525ae",
      "bytes": 30455,
      "sha256": "6e2e564705793b7797fe452d37c4534e798be87f87bd80ad6584ac778f357b24"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-hosting.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "2efba65e9e9bf3bcdc40e223f52e7a3e30d5c8a2",
      "bytes": 160508,
      "sha256": "558e1d3f3fa16d97d8c0ae754f03054d2e9c64268549a79562ecc180641c22d7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-migration-build-arg.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "db85f7c98018ae8776cb20881bc5111eab113d45",
      "bytes": 12210,
      "sha256": "b7031cfa5c6ba7cace2e41d67e00498de3e332c164c8658f415dd30383bc071b"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-navigation-recovery.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "d7289b7cc3a2196a9ea0701ef35d438abdad3eb4",
      "bytes": 11135,
      "sha256": "d30af7f8005359c6383e177c76c43132502e003bfe9f93dd66ad3af85ab61704"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-paid-access.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4676a6797d9006d90338ae300c4e39c551174fba",
      "bytes": 35727,
      "sha256": "a4074b431e830680b48e5381f44284acedf1ad9936179001e3e2bbc821d4eab7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-parallel-delivery.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "fa4cecf3ca524d41e5f34400c9b36112f904d2a1",
      "bytes": 6174,
      "sha256": "01b7c11e03536ca1a57b8d71410eabdfa1d87942d89e00b62aeab981a6e33914"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-publisher-transport.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a065aca86adc5bc139a3f2586de14f9972ed32cf",
      "bytes": 48211,
      "sha256": "d0bca7b9a536481981f62163abcb22cf4fd735ed876226082baa3e38863b248b"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-r6-dto120-receipts.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "b6bccf90c8559ff00d8fbf86f3a1190a439381e9",
      "bytes": 30188,
      "sha256": "0a92ab2438f72ce5b07bc323e77fc6694ce4d797cd5e6440e9247db38edc9152"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-r6-paid-selector-work.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6ca6d9d50eaac57404afe2c919d2d5d97718cc79",
      "bytes": 18898,
      "sha256": "eea9cee67f8ade0fc517777e59bc97f51bebe195cdc413f923baf48d43320b2d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-schema-observation-harness.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "83f49de4b267bda299c6a795f4cc6bc54677b7d2",
      "bytes": 29269,
      "sha256": "e7d9475fa47c4a8756ad77efe3c728c808cb828b013f406eda51c59016ba1958"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-03-workshop-staging-workflow-regression-amendment.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a24e2e8a943fe9bec34783fdf47990059ffe9383",
      "bytes": 5502,
      "sha256": "f2814d837cf3329b8329a2d87a21ac3a0dc941c3bae9c130be554882ff552ce7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-artifact-inspection-close-failure.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "21ff22eb77fcdcdace539623b9dd452e32067a08",
      "bytes": 12893,
      "sha256": "811f418eec4782355ab3695d942361d95629a7bac30d055bf31040f60ab9f563"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-artifact-revalidation-deadline.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "041637617106ad55c95e24b1a13182c1430623f9",
      "bytes": 14170,
      "sha256": "42cffb023466e0e39c486d6681a616bbe529cf1e0cc8e7a48f8656f5347856c7"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final-reviewed-leaves-integration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "880f9e23aeb3bba63136ba1380184782d222072d",
      "bytes": 41243,
      "sha256": "449a100774f956a72fd903480f083243362dc5109cadda89031f8b58f6bdccb1"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final180-ci-integration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "008838ca55d242aeae03bb49d9d8ee5316656ad5",
      "bytes": 17531,
      "sha256": "c8026d2baec9894a7f50b55bad62800182d8a4be6d1795f5c7a51a673b3ee937"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final180-inventory.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "7f50c024fc38fec72b41014751641d1d2d3f8073",
      "bytes": 8785,
      "sha256": "52deaa68198a05fec94dbcce5fc461b38e7984934556b47fdaa7676eb348cd18"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final180-runner.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c8617fee8e43d27f80ca29c6f1a9ddae6ac79ed2",
      "bytes": 7888,
      "sha256": "6d1d5f4e8da9310669419703b298eeb17cd7c14a5e3719ea416cf5b1145ebaa9"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final180-stage-b1-identity.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8979973a5124d4f3f7a439dba31ca8104e488971",
      "bytes": 13657,
      "sha256": "02f92b355c5dcd3144f1ec80c21118a86a9624b466dfa756a6795edd13fa21ca"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final180-stage-b2-catalog-go.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5d79004dca6add657533ef6883895c7698adb988",
      "bytes": 50477,
      "sha256": "0b2899864f1964e50b4e5ca7f7d70d48331c3f1f1aad6898b8d2f7eb83b9889f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-index-readiness.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "4f452960ba24088a8623d0c4f5baca584962ae06",
      "bytes": 24676,
      "sha256": "394d99e0615d33ec53ac68a6093593a7c505053f05ddb0af638b2159b208f40f"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-publisher-python-review-corrections.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "88e7bab6ef9e1883521da6280d6008de3d22e5b2",
      "bytes": 13730,
      "sha256": "7217a7b13efadb15c3eaaef13f23d5abd3ae73acb884020dbb61bb900662bd07"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-publisher-sigterm-ordering-amendment.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c334d0c73b686c614135a5a0fdbb45dcdc8c678f",
      "bytes": 12080,
      "sha256": "d96f16b23af2fff85a23bbff2169a3c51aa4731ed32a5e2aed05287d1422874a"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-publisher-stage0-integration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "0fd8b2223c324743c957e9ae49f6714fe4dcfe91",
      "bytes": 20342,
      "sha256": "c135e55c6a3b41e51300818e2b2145225879596e93cd09a07fcb863ad158f5bf"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-publisher-stage1a-offline-trust.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a3c5d91e9973e23ded210dd6aff7d9d0ddae7bbb",
      "bytes": 19126,
      "sha256": "db5b08b7d36348032d7f935623bbbed8b8f5e09e4e52b097a9bebc55715166bd"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-r6-paid-http-receipts.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "7f547fa710480f17292da630974c7be17be2bb00",
      "bytes": 30389,
      "sha256": "07e0411dd1ec0983476489cd028b45098ec41f9d7aedaa5f1a3d6a7be40047c2"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-r6-paid-scope-receipts.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "1b11f9c858efb58d6dfa192f21793e0a64d7178c",
      "bytes": 33057,
      "sha256": "e0bd8d9b198a9d4c1049cf9fc9965f84e4b1af871a08f2b98a59bfbe08f051b4"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-retryable-reader.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "feb42d4b7ce80f9e2baaf5307de3b916c395de5a",
      "bytes": 20216,
      "sha256": "b343cd6207c098f2d4544ff3db2551d2b428b4fb84592d2ea8fbe107252c8d6a"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-reviewed-leaves-integration.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "3c784cafc1731defc89da8d9359d37fa156d5113",
      "bytes": 18628,
      "sha256": "14e07f1805ebf380b76d50125f65deac0e01c8d9a1d614cffbb1e238d78bd8d3"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-staging-boot-device.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "187009a66e88b607c024cda93b16acc262a008fc",
      "bytes": 16418,
      "sha256": "2d3ba01d575de47aaa693f59af3402c9b42b0dde62ba090c6cb73053f09a3431"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-staging-lifecycle.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "a1b29c43e0e6016c3035109520ae6d852902d8a4",
      "bytes": 42148,
      "sha256": "e20c2cc687d5cc751053d8f0b13411c4bfd08ba5e2f4e2650b86e88a72eae641"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "docs/superpowers/plans/2026-11-04-workshop-staging-m2-host-install.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "74877db7504ad75762d75ca36c1d6c2aff261139",
      "bytes": 32488,
      "sha256": "ce896f8037dccdfd2c328b11a3213d306194a1a79151e64e3d5c074b93f8bf09"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "scripts/dev/test_workshop_final180_catalog_adapter.py",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "86e78aef564c216ede5780dccadd56366d4d0a63",
      "bytes": 26977,
      "sha256": "978cbb594d9bc42f0cb02b3447e2afed6bb6764c155b657db6e5b3676cc319a9"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "scripts/dev/test_workshop_final180_identity_adapter.py",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "7391263cb874e2505f4f110df6343c8b466fc692",
      "bytes": 29838,
      "sha256": "a3f3017b1d7a85da9ae4d1883758f2494d722fb321d45c1ff758994ab6d2653c"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "scripts/dev/test_workshop_final180_runner.py",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "f4db092e0d1a83fce47b51f7c68021b6dc2053bd",
      "bytes": 33237,
      "sha256": "c0bac62eb756d84593191e82b2b240fdd77bd5128242f212e9b508e15c1740c1"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "scripts/dev/workshop_final180_catalog_adapter.py",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "060d1407ee5e71880cf7e441195cac4274f04937",
      "bytes": 15467,
      "sha256": "88f481104d66d9bda8bdf6c1a8038e8514b69d63db813b85c5ec13e40f0c6ddf"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "scripts/dev/workshop_final180_identity_adapter.py",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8c7fa87bab906955c145d7cc965be641aea48c5f",
      "bytes": 22290,
      "sha256": "0474a85c33d4f2722ad01d6e55e69a8080dc0f1983c856ca7caa1b94510a767d"
    },
    {
      "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
      "path": "scripts/dev/workshop_final180_runner.py",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "ca48cd988c5579a7d385dc1844b84306eae0861e",
      "bytes": 47124,
      "sha256": "693a408a73f3ccd37bf945bfc94d427f742878580932dab382ea9a244a141c91"
    }
  ],
  "historical_stage_bundle_pins": [
    {
      "ref": "cd9e8355a0ccb055b4327bbbd1ecaf97e7cddbe9",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final180-stage-c-commerce.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "8e4a84383c3e21486f663572e88d9d8cd1517b1a",
      "bytes": 28362,
      "sha256": "58fabe156fa57c2b750d392fc1dc476334477ee89b2673a0afd35c2d7e235da0"
    },
    {
      "ref": "cd9e8355a0ccb055b4327bbbd1ecaf97e7cddbe9",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-stage-c-commerce.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "67e98b099ff814d3891d8764a307b4845bff576c",
      "bytes": 75248,
      "sha256": "cbe819f806c7f86c35d12c101611e73fc150766897c0d593720520c53bce99b7"
    },
    {
      "ref": "cd9e8355a0ccb055b4327bbbd1ecaf97e7cddbe9",
      "path": "docs/agents/records/2026-11-04-workshop-final180-stage-c-commerce.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6c84711e5fd2af7a803e4d6dca16b00b777a386f",
      "bytes": 11016,
      "sha256": "615ce1d531b96736acb6734a96e1af51a951988b9570311672a4f95f04f5b68e"
    },
    {
      "ref": "cd9e8355a0ccb055b4327bbbd1ecaf97e7cddbe9",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-c-commerce.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "abd06c8aeede5a8d18d631fa2ebea1051f0ca11e",
      "bytes": 16245,
      "sha256": "a00e7028a70c50c953964aee73168795064ee6c2d82fa8e8dc9ea7aba35a448e"
    },
    {
      "ref": "70c9a6ebb2cec338f938122c8c570fd5b22a6f28",
      "path": "docs/superpowers/plans/2026-11-04-workshop-final180-stage-d-paid.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "417d42723aeb31e9b868de8d310f41ac85f5257f",
      "bytes": 17590,
      "sha256": "701145fb15691f4063f67e4024472bd661fd2c17edc789a1c119a45a7e374294"
    },
    {
      "ref": "70c9a6ebb2cec338f938122c8c570fd5b22a6f28",
      "path": "docs/agents/specs/2026-11-04-workshop-final180-stage-d-paid.md",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "66271c20ef12064bd03862ce85ff24c76510e147",
      "bytes": 109926,
      "sha256": "ab0cf25549dfc0e829600af8d275ef4e528865a2dd35ca56307b71b1bc740a90"
    },
    {
      "ref": "70c9a6ebb2cec338f938122c8c570fd5b22a6f28",
      "path": "docs/agents/records/2026-11-04-workshop-final180-stage-d-paid.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "c98dfa65a396d3ad9265da8988242bbb50124e93",
      "bytes": 9471,
      "sha256": "412451fce7f22388db540541a640d9483a3f51e85e9ba6dd45b454bdd5c3d9aa"
    },
    {
      "ref": "70c9a6ebb2cec338f938122c8c570fd5b22a6f28",
      "path": "docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-d-paid.json",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "5386c3726e036f01c16a0cc14552621d4ccdc639",
      "bytes": 14435,
      "sha256": "4401118e70017a5318372bfa893ff90fb3c3e20b99cacd5ae9dd6cf79c984abb"
    }
  ],
  "source_pins": [
    {
      "ref": "c4dd59b3ac6a1afb74f7ad1d4f54ef1eb6e7fdad",
      "path": "scripts/dev/workshop_final180_commerce_adapter.py",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "6fa4ed8325b15cdd230a6ed36fb2106be95d66d8",
      "bytes": 25450,
      "sha256": "68fe9d269f595f6ea361cf713591bc2735e1ba87a364001bd78cbfe697dabfc4"
    },
    {
      "ref": "c4dd59b3ac6a1afb74f7ad1d4f54ef1eb6e7fdad",
      "path": "scripts/dev/test_workshop_final180_commerce_adapter.py",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "49c975563a65d320f2ff081a1e98e0970d245724",
      "bytes": 39932,
      "sha256": "193db3d21667b0aecb87648512f6ee8792ddcc1176bab247b9d17319625a78ca"
    },
    {
      "ref": "2774cdfe44e7c99a0cae5606ad1ea5f20863c0d7",
      "path": "scripts/dev/workshop_final180_paid_adapter.py",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "92de32b5500f68f91848a064f733f689d99f22dc",
      "bytes": 17676,
      "sha256": "563d2b3f426270dac34ae3117a64b9253748aa4c2755445d5b50f1bfcc9a224a"
    },
    {
      "ref": "2774cdfe44e7c99a0cae5606ad1ea5f20863c0d7",
      "path": "scripts/dev/test_workshop_final180_paid_adapter.py",
      "mode": "100644",
      "kind": "blob",
      "git_blob": "98eda0b70e61eb2c25cc68cf7add6c438888a9cc",
      "bytes": 42741,
      "sha256": "1f66999eebc61a2a7f7218627bf9c54c45b8bc1ae6f8070cd8f1403acfaa83f1"
    }
  ],
  "appends": {
    "runbook": {
      "common_prefix": {
        "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
        "path": "docs/verification/workshop-final180-runbook.md",
        "mode": "100644",
        "kind": "blob",
        "git_blob": "05c38499f47d8960e9d6ae8c0497f5866cec200c",
        "bytes": 22069,
        "sha256": "0a36f9e46ffa767feacc3a49ead622ce3d424b5eec155300c3df58dde8da89d6"
      },
      "c": {
        "whole": {
          "ref": "c4dd59b3ac6a1afb74f7ad1d4f54ef1eb6e7fdad",
          "path": "docs/verification/workshop-final180-runbook.md",
          "mode": "100644",
          "kind": "blob",
          "git_blob": "88c6f72741fe9523f5cd9696c7049bc686b6a354",
          "bytes": 29905,
          "sha256": "0e7677c76b83fc0006ef45258a5e231c6c29be122ee54701b477d4e2c00f1270"
        },
        "suffix": {
          "bytes": 7836,
          "sha256": "e892a1a1c579c02e345469734da19c899925bacc28c26846f25632a4ccadbb99"
        }
      },
      "d": {
        "whole": {
          "ref": "2774cdfe44e7c99a0cae5606ad1ea5f20863c0d7",
          "path": "docs/verification/workshop-final180-runbook.md",
          "mode": "100644",
          "kind": "blob",
          "git_blob": "0dd6aa73096bd1b56b651e8837eb42bf5053600e",
          "bytes": 30822,
          "sha256": "7413bdc3a749df4e38cd40d69af608250b7ceb17d844daba53dffde4bdcb38a5"
        },
        "suffix": {
          "bytes": 8753,
          "sha256": "e5d8a5ae1ce097db151a0b6f4b964c6f42cee2678f6a7b41af9d0f5b2240563a"
        }
      },
      "proposed_concatenation_without_new_integration_note": {
        "bytes": 38658,
        "sha256": "61d0f6234606977618d007c39028bf34f349c9d60514b9f2f914a1429de3eecf"
      }
    },
    "assembler_index": {
      "common_prefix": {
        "ref": "fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc",
        "path": "docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md",
        "mode": "100644",
        "kind": "blob",
        "git_blob": "3b8fca73845d66e83737abb71ba0ad4d11d474b1",
        "bytes": 83750,
        "sha256": "bfba07ba34a31044df6b1f2045f35b9fdbd9a7472d1755a91d2cef2accb7738c"
      },
      "c": {
        "whole": {
          "ref": "c4dd59b3ac6a1afb74f7ad1d4f54ef1eb6e7fdad",
          "path": "docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md",
          "mode": "100644",
          "kind": "blob",
          "git_blob": "89b8ed23e621c0230f46ce47a5cf24a1c5ddddba",
          "bytes": 89228,
          "sha256": "1f7b6a1cfe096a01a3908d3403e19c1e3d9fdfa13623ed3765285975aac147f8"
        },
        "suffix": {
          "bytes": 5478,
          "sha256": "8f79d089b857bf3a0727f3ca41c60e806e10e4d1ed178a5bc387a762bae677d4"
        }
      },
      "d": {
        "whole": {
          "ref": "2774cdfe44e7c99a0cae5606ad1ea5f20863c0d7",
          "path": "docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md",
          "mode": "100644",
          "kind": "blob",
          "git_blob": "3ba6a460a7a670a06338db54b820475dbc8ca210",
          "bytes": 89517,
          "sha256": "c508e3ad20930e2cebcae73840dcc13cd08ff1b32cabbb3e947697baac84176f"
        },
        "suffix": {
          "bytes": 5767,
          "sha256": "6b634494909e7ade8d5f88b5ee212d97e0978cb09104cc126d4e42f7aa24615e"
        }
      },
      "proposed_concatenation_without_new_integration_note": {
        "bytes": 94995,
        "sha256": "83fa8519304296de87412d2b0ead9380d428c91dc9e397b8da6b6fb413e953f6"
      }
    }
  },
  "imports": {
    "c": [
      "ImportFrom(module='dataclasses', names=[alias(name='dataclass')], level=0)",
      "Import(names=[alias(name='hashlib')])",
      "Import(names=[alias(name='json')])",
      "Import(names=[alias(name='re')])",
      "ImportFrom(module='xml.parsers', names=[alias(name='expat')], level=0)",
      "ImportFrom(module='scripts.dev.workshop_final180_identity_adapter', names=[alias(name='parse_identity_events'), alias(name='GoEvent'), alias(name='AdapterError'), alias(name='SimulatedExit')], level=0)"
    ],
    "d": [
      "ImportFrom(module='dataclasses', names=[alias(name='dataclass')], level=0)",
      "Import(names=[alias(name='hashlib')])",
      "Import(names=[alias(name='json')])",
      "Import(names=[alias(name='re')])",
      "ImportFrom(module='scripts.dev.workshop_final180_identity_adapter', names=[alias(name='parse_identity_events'), alias(name='GoEvent'), alias(name='AdapterError'), alias(name='SimulatedExit')], level=0)"
    ]
  },
  "external_evidence_pins": [
    {
      "path": "/home/corp/autodata-evidence/final180-commerce-independent-review/review.json",
      "bytes": 3227,
      "sha256": "45667ebb99371465e8c0e56547b917092ed1a214d8a76815b4996a9bef696ae2"
    },
    {
      "path": "/home/corp/autodata-evidence/final180-cd-integration-plan/PLAN.md",
      "bytes": 20181,
      "sha256": "4f5920762c539f1a139d7c459479d06940e1658336c0af66ca1be1cbfe588fc6"
    },
    {
      "path": "/home/corp/autodata-evidence/final180-commerce-gate-dispatch/receipt.json",
      "bytes": 945,
      "sha256": "2d3e35d4968b35cc8728fb15b2c0b5c2654c62d697352c39faa8019d19e75d9a"
    },
    {
      "path": "/home/corp/autodata-evidence/final180-paid-gate-dispatch/receipt.json",
      "bytes": 945,
      "sha256": "cf2bf2e1dd9fde669420d2812368122042f09efeaddd6069ab237f083d001555"
    },
    {
      "path": "/home/corp/autodata-evidence/final180-paid-final-repaired-review/receipt.json",
      "bytes": 1796,
      "sha256": "29091141c2a5968c61de46f83d752e163b7549e486aa2fb4e1135af6250727b8"
    },
    {
      "path": "/home/corp/autodata-evidence/final180-cd-integration-freeze/REPORT.md",
      "bytes": 6392,
      "sha256": "b53e247a944fc80499146a818e10f96ceea16e9e7921b5846885651044bed379"
    },
    {
      "path": "/home/corp/autodata-evidence/final180-cd-integration-freeze/freeze.json",
      "bytes": 134933,
      "sha256": "be77ff20139bb42c88cf813792d9e36ee57cdcd7a2566d3255dabde413a7412b"
    },
    {
      "path": "/home/corp/autodata-evidence/final180-cd-integration-freeze/all-common-parent-protected-tree.json",
      "bytes": 159671,
      "sha256": "d02f8d538a26405adcd3239e4b41fb4b7bc7ca4abaa29566cf45c7993ac9f498"
    },
    {
      "path": "/home/corp/autodata-evidence/final180-cd-integration-gate-tracking/receipt.json",
      "bytes": 3138,
      "sha256": "cff205865bfc29f993fd860ea770d3185deb9c406684484854af055878ecd398"
    },
    {
      "path": "/home/corp/autodata-evidence/final180-cd-code-completion-tracking/receipt.json",
      "bytes": 1054,
      "sha256": "70c96732aa40f3a681c3d970af08398c004b428755b10b82c67fd1483b8be180"
    }
  ],
  "planning_paths": [
    "docs/superpowers/plans/2026-11-04-workshop-final180-cd-integration.md",
    "docs/agents/specs/2026-11-04-workshop-final180-cd-integration.md",
    "docs/agents/records/2026-11-04-workshop-final180-cd-integration.json",
    "docs/agents/tasks/2026-11-03-production-release/workshop-final180-cd-integration.json",
    "docs/superpowers/plans/2026-11-04-workshop-final180-stage-d-paid.md",
    "docs/agents/specs/2026-11-04-workshop-final180-stage-d-paid.md",
    "docs/agents/records/2026-11-04-workshop-final180-stage-d-paid.json",
    "docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-d-paid.json",
    "docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md"
  ],
  "implementation_allowlist": [
    "scripts/dev/workshop_final180_paid_adapter.py",
    "scripts/dev/test_workshop_final180_paid_adapter.py",
    "docs/verification/workshop-final180-runbook.md"
  ],
  "selected_candidate_sha": "4d82e413e04fb2401ac7bc28dc828375ac662180",
  "inventory_sha256": "c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39",
  "integration_index_entry": {
    "bytes": 3747,
    "sha256": "66957da3ced1e77b2a5ea7592cfa652804e44bc1475de813cae233e1d9b6e99f",
    "marker": "\n\n## Stage C/D exact-adoption integration checkpoint (2026-11-04)\n"
  }
}
```
<!-- END INTEGRATION PINS -->

## 7. Read-only verifier and exact adoption formulas

Copy the Python block below to an external evidence file and run with PYTHONDONTWRITEBYTECODE=1 from the assigned repository root. `draft` validates the nine uncommitted planning paths and source objects; `checkpoint` takes the full newly committed checkpoint SHA and requires a clean tree; `implementation` takes full checkpoint and code-head SHAs and requires a clean tree. The latter phases print both exact-base preflight seals. Never set a branch shorthand or C_FINAL as the new checkpoint. The command argument is a value obtained from the actual committed receipt, not a placeholder authorizing work.

```python
import ast
from functools import lru_cache
import hashlib
import json
import re
import stat
import subprocess
import sys
from pathlib import Path

# Run this read-only checker from the integration repository root.
# draft checks working planning files; checkpoint/implementation check Git objects.
phase = sys.argv[1]
assert phase in ('draft', 'checkpoint', 'implementation')
checkpoint = sys.argv[2] if len(sys.argv) > 2 else None
head = sys.argv[3] if len(sys.argv) > 3 else checkpoint
if phase != 'draft':
    assert checkpoint and re.fullmatch('[0-9a-f]{40}', checkpoint)
    assert head and re.fullmatch('[0-9a-f]{40}', head)
root = Path.cwd()
sys.path.insert(0, str(root))
def git(*args):
    return subprocess.check_output(['git', *args], cwd=root)
def blob(ref, path):
    return git('show', f'{ref}:{path}')
@lru_cache(maxsize=None)
def tree(ref):
    entries = {}
    for line in git('ls-tree', '-rz', ref).split(b'\0'):
        if line:
            meta, path = line.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            entries[path.decode()] = (mode, kind, oid)
    return entries
name = '2026-11-04-workshop-final180-cd-integration'
sp = f'docs/agents/specs/{name}.md'
text = (root / sp).read_text() if phase == 'draft' else blob(checkpoint, sp).decode()
manifest = json.loads(text.split('<!-- BEGIN INTEGRATION PINS -->\n```json\n', 1)[1].split('\n```\n<!-- END INTEGRATION PINS -->', 1)[0])
refs = manifest['refs']
C, D, DG, common = (refs[k] for k in ('c_final', 'd_final', 'd_gate', 'common_parent'))
ctree = tree(C)
index = 'docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md'
runbook = 'docs/verification/workshop-final180-runbook.md'
allow = set(manifest['implementation_allowlist'])
planning = set(manifest['planning_paths'])
assert len(allow) == 3 and len(planning) == 9
assert git('merge-base', C, D).decode().strip() == common
for gate, final in ((refs['c_gate'], C), (DG, D)):
    subprocess.run(['git', 'merge-base', '--is-ancestor', gate, final], cwd=root, check=True)
for p in manifest['protected_pins'] + manifest['historical_stage_bundle_pins'] + manifest['source_pins']:
    b = blob(p['ref'], p['path'])
    assert (len(b), hashlib.sha256(b).hexdigest()) == (p['bytes'], p['sha256']), p['path']
    assert tree(p['ref'])[p['path']] == (p['mode'], p['kind'], p['git_blob']), p['path']
for p in manifest['external_evidence_pins']:
    b = Path(p['path']).read_bytes()
    assert (len(b), hashlib.sha256(b).hexdigest()) == (p['bytes'], p['sha256']), p['path']
# Freeze exact adapter imports, including only the four public B1 symbols.
for key, ref, path in (('c', C, 'scripts/dev/workshop_final180_commerce_adapter.py'), ('d', D, 'scripts/dev/workshop_final180_paid_adapter.py')):
    parsed = ast.parse(blob(ref, path))
    imports = [ast.dump(n) for n in parsed.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert imports == manifest['imports'][key]
# Exhaustively retain every C tree entry except the separately appended index/runbook.
if phase == 'draft':
    assert git('rev-parse', 'HEAD').decode().strip() == C
    changed = set(git('diff', '--name-only', C).decode().splitlines())
    changed |= set(git('ls-files', '--others', '--exclude-standard').decode().splitlines())
    assert changed == planning, sorted(changed ^ planning)
    def current(path):
        return (root / path).read_bytes()
    for path in planning - {index}:
        assert not (root / path).is_symlink()
        assert stat.S_IMODE((root / path).stat().st_mode) == 0o644
else:
    chain = git('rev-list', '--first-parent', '--reverse', f'{C}..{checkpoint}').decode().splitlines()
    assert len(chain) == 2 and chain[0] == '2e3b1c7f3dcf8b0ddd36f8098feda5b6494bd16c' and chain[-1] == checkpoint
    previous = C
    for revision in chain:
        assert git('rev-list', '--parents', '-n', '1', revision).decode().split() == [revision, previous]
        delta = set(git('diff', '--name-only', previous, revision).decode().splitlines())
        assert delta and delta <= planning, sorted(delta - planning)
        previous = revision
    ktree, htree = tree(checkpoint), tree(head)
    changes = {p for p in set(ctree) | set(ktree) if ctree.get(p) != ktree.get(p)}
    assert changes == planning, sorted(changes ^ planning)
    assert not git('status', '--porcelain'), 'Use a clean checkout for committed-object checks'
    for p in planning - {index}:
        assert ktree[p][:2] == ('100644', 'blob')
    if phase == 'checkpoint':
        assert head == checkpoint
    else:
        changes = {p for p in set(ktree) | set(htree) if ktree.get(p) != htree.get(p)}
        assert changes == allow, sorted(changes ^ allow)
        subprocess.run(['git', 'merge-base', '--is-ancestor', checkpoint, head], cwd=root, check=True)
    def current(path):
        return blob(head, path)
    for path, pin in ctree.items():
        if path not in {index, runbook}:
            assert htree[path] == pin, path
# Historical adopted D gate files retain original bytes AND mode.
for p in manifest['historical_stage_bundle_pins']:
    assert current(p['path']) == blob(p['ref'], p['path']), p['path']
    if phase != 'draft':
        assert tree(head)[p['path']] == (p['mode'], p['kind'], p['git_blob'])
# Two independent append algorithms: index at planning time, runbook only after dispatch.
for label, path in (('assembler_index', index), ('runbook', runbook)):
    app = manifest['appends'][label]
    base, cb, db = blob(common, path), blob(C, path), blob(D, path)
    for b, pin in ((base, app['common_prefix']), (cb, app['c']['whole']), (db, app['d']['whole'])):
        assert len(b) == pin['bytes'] and hashlib.sha256(b).hexdigest() == pin['sha256']
        assert tree(pin['ref'])[path] == (pin['mode'], pin['kind'], pin['git_blob'])
    assert cb.startswith(base) and db.startswith(base)
    suffix = db[len(base):]
    assert len(suffix) == app['d']['suffix']['bytes']
    assert hashlib.sha256(suffix).hexdigest() == app['d']['suffix']['sha256']
    joined = cb + suffix
    assert len(joined) == app['proposed_concatenation_without_new_integration_note']['bytes']
    assert hashlib.sha256(joined).hexdigest() == app['proposed_concatenation_without_new_integration_note']['sha256']
    actual = current(path)
    if label == 'assembler_index':
        assert actual.startswith(joined)
        note = actual[len(joined):]
        pin = manifest['integration_index_entry']
        assert len(note) == pin['bytes'] and hashlib.sha256(note).hexdigest() == pin['sha256']
        assert note.startswith(pin['marker'].encode())
        if phase != 'draft':
            assert tree(head)[path] == tree(checkpoint)[path]
    elif phase != 'implementation':
        assert actual == cb, 'Runbook edits are forbidden at the planning checkpoint'
    else:
        assert actual.startswith(joined)
        note = actual[len(joined):]
        assert note.startswith(b'\n\n## Stage C/D integration verification and limits\n')
        assert len(note) > 100
        for required in (C, D, checkpoint, 'accepted_case_credit=0', 'profiles_enabled=false', 'runtime_lock=null', 'run_record=null'):
            assert required.encode() in note, required
        assert tree(head)[path][0] == '100644'
if phase == 'implementation':
    for p in manifest['source_pins']:
        assert current(p['path']) == blob(p['ref'], p['path'])
        assert tree(head)[p['path']] == (p['mode'], p['kind'], p['git_blob'])
rp = f'docs/agents/records/{name}.json'
tp = 'docs/agents/tasks/2026-11-03-production-release/workshop-final180-cd-integration.json'
r, task = json.loads(current(rp)), json.loads(current(tp))
assert r == task['pre_implementation']
assert task['todo'] == r['todo'] and len(r['todo']) == 5
assert task['allowed_paths'] == r['implementation_allowlist'] == manifest['implementation_allowlist']
assert task['status'] == 'blocked' and r['authorizing_checkpoint_sha'] is None
assert r['planning_parent_sha'] == C and r['adoption_source_sha'] == D
assert type(r['accepted_case_credit']) is int and r['accepted_case_credit'] == 0
assert r['profiles_enabled'] is False and r['enabled_tiers'] == []
assert r['runtime_lock'] is None and r['run_record'] is None
assert len(r['authority']) == 9 and all(v is False for v in r['authority'].values())
assert task['authority'] == r['authority']
assert task['runtime_lock'] is None and task['run_record'] is None
assert task['product_evidence'] == {'accepted_case_credit': 0, 'profiles_enabled': False, 'enabled_tiers': []}
plan_text = current(r['plan_ref']).decode()
for item in r['todo'] + [r['issue_ref'], r['project_ref'], r['goal']]:
    assert item in plan_text
    assert item in text
assert json.loads(Path(r['tracking_receipts']['receipt_ref']).read_text())['todo'] == r['todo']
if phase == 'draft':
    assert r['status'] in ('blocked', 'synchronized')
else:
    from scripts.autonomy.pre_implementation import validate_record
    policy = json.loads(blob(checkpoint, '.autodata-autonomy-policy.json'))
    for label, value in (('standalone', r), ('nested', task['pre_implementation'])):
        errors = validate_record(value, root, checkpoint, policy)
        assert errors == [], (label, errors)
        print(json.dumps({'record': label, 'base_sha': checkpoint, 'status': value['status'], 'errors': errors}))
    assert r['tracking_receipts']['status'] == 'synchronized_live_readback'
subprocess.run(['git', 'diff', '--check'], cwd=root, check=True)
print(json.dumps({'phase': phase, 'checkpoint': checkpoint, 'head': head, 'result': 'PASS', 'accepted_case_credit': 0, 'authority': r['authority']}, sort_keys=True))
```

After explicit dispatch only, the builder can perform the two-file exact adoption and prefix append using this algorithm (the new integration note is authored with actual measured results per section3):

```python
from pathlib import Path
import hashlib
import subprocess

def source(ref, path):
    return subprocess.check_output(['git', 'show', f'{ref}:{path}'])
D_FINAL = '2774cdfe44e7c99a0cae5606ad1ea5f20863c0d7'
C_FINAL = 'c4dd59b3ac6a1afb74f7ad1d4f54ef1eb6e7fdad'
COMMON = 'fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc'
for path, expected in (
    ('scripts/dev/workshop_final180_paid_adapter.py', '563d2b3f426270dac34ae3117a64b9253748aa4c2755445d5b50f1bfcc9a224a'),
    ('scripts/dev/test_workshop_final180_paid_adapter.py', '1f66999eebc61a2a7f7218627bf9c54c45b8bc1ae6f8070cd8f1403acfaa83f1'),
):
    data = source(D_FINAL, path)
    assert hashlib.sha256(data).hexdigest() == expected
    target = Path(path)
    assert not target.exists()
    target.write_bytes(data)
    target.chmod(0o644)
path = 'docs/verification/workshop-final180-runbook.md'
base, c, d = (source(ref, path) for ref in (COMMON, C_FINAL, D_FINAL))
assert c.startswith(base) and d.startswith(base)
assert Path(path).read_bytes() == c
joined = c + d[len(base):]
assert len(joined) == 38658
assert hashlib.sha256(joined).hexdigest() == '61d0f6234606977618d007c39028bf34f349c9d60514b9f2f914a1429de3eecf'
Path(path).write_bytes(joined)
```

The adoption snippet is future gated builder guidance and has not been executed by the planning agent. Before committing the code milestone, append section3's required measured note. Do not add any helper/checker file to the repository; the exact builder allowlist remains three paths.
