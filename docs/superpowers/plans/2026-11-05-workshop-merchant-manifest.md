# Workshop Merchant Manifest Implementation Plan — DRAFT Task54

> **For agentic workers:** After explicit dispatch only, use superpowers:executing-plans to execute the approved task steps. This draft grants no implementation authority.

**Goal:** Add an inert offline validator for exact-byte Workshop merchant manifest preparation while preserving the shipped disabled manifest and every owner approval, Stripe TEST, runtime and release block.

**Architecture:** A pure standard-library evaluator reads explicitly supplied local files and checks exact-byte/hash consistency under a closed approval-envelope schema. Its read-only CLI returns prepared_offline or blocked; neither establishes merchant approval, deployment or authentic TEST acceptance. The Go embedded default stays byte-identical and disabled.

**Tech Stack:** Python3 standard library unittest, hashlib, json, pathlib, argparse and urllib.parse; existing unchanged Node/Go regression tests.

**Spec:** `docs/agents/specs/2026-11-05-workshop-merchant-manifest.json` — canonical G1b draft amendment; architecture documents are read-only context.

Issue: https://github.com/lucronn/autodata/issues/186. Project: https://github.com/users/lucronn/projects/8, existing item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4. Planning/tracking are synchronized; standalone/nested record status is synchronized; execution state is blocked. All authorities false; current implementation allowlist empty. No GitHub write, commit/push or code change is authorized by this draft.

## Global constraints and source identity

Exact planning parent c374f77af461f01d367a8b802c7d7bea886fe7ec, tree a29bd3380144303394e1cf680d031af91009430d, queue53. Application source declaration remains admitted Task51 6949eb1b1a5b93c9b2eb0579328e24c697f6f331/tree47ec54b1896c83a39b6637a6ce944d3620414f4e. The spec freezes actual seven read-only source pins at this parent. Parent/checkpoint/implementation identities are distinct; checkpoint fields remain null until external sealing. Task52/53 code is independent and must not be overwritten or claimed as merchant evidence. Recompute/review pins before admitting a later source successor that changes packaging/manifest inputs.

Prospective implementation allowlist exactly:
- NEW `scripts/dev/workshop_merchant_manifest.py`: pure evaluator and local read-only CLI.
- NEW `scripts/dev/test_workshop_merchant_manifest.py`: independent tempfile synthetic tests and immutable default assertion.

No Go edit: existing TestWorkshopPurchaseConfigDisabledByDefault checks semantics; Python adds exact baseline. Default must remain 168 bytes and SHA256 edb1d6d182c5eeee6c33885e873bc5b44ac7a3eb4465d9e92af5d1bc60d4b45f. Do not normalize, inject, copy or ship enabled fixture bytes. No runtime override or new packaging hook.

## Literal todo

- [ ] Independently review this six-document draft at exact Task53 planning parent c374f77af461f01d367a8b802c7d7bea886fe7ec, preserve all 53 prior queue objects and root fields, and freeze the two-new-Python-file implementation scope and disabled manifest bytes.
- [ ] Synchronize this literal goal, six todo strings, six gate paths and exact two implementation paths in Issue186 and existing Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4 with before/after readbacks; commit/push the planning checkpoint, externally seal its SHA/tree, pass standalone and nested canonical exact-base preflights and independent checkpoint review before explicit branch dispatch.
- [ ] Write independent synthetic red tests for strict bounded inputs, exact raw-byte bindings, policy URL/snapshot mapping, tax/product/enrollment tuple mutations and immutable disabled baseline; then implement only the pure standard-library offline evaluator and read-only CLI in the two allowed Python files.
- [ ] Keep prepared_offline limited to locally consistent supplied bytes with explicit provenance; report absent or mismatched prerequisites as blocked, preserve exact input bytes, and keep owner approval, artifact admission, authentic TEST acceptance, enablement and all operational authorities false.
- [ ] Run focused and full developer tests, developer discovery checks, unchanged Node Workshop readiness and Go Workshop tests, exact allowlist/baseline checks and diff checks; record actual red/green receipts, skips and failures without customer acceptance credit.
- [ ] After authorized implementation, commit and promptly push coherent validated milestones, obtain independent exact-code review and fresh source-push plus actual PR checkout CI; leave owner-supplied real policy/tax inputs, injection/rebuild, immutable artifact/served-byte proof, authentic Stripe TEST enrollment and live release to separate gates.

## Implementation steps after gate admission

### Task 1: Independent failing preparation tests

Files: create `scripts/dev/test_workshop_merchant_manifest.py`. Consumes the spec closed schemas and pinned baseline; produces unittest evidence for `evaluate_files(*, manifest: Path, approval: Path, policies: dict[str, Path], build_recipe: Path, embed_source: Path) -> dict[str, object]`.

- [ ] Build byte literals in temporary directories; derive digests in test helpers using hashlib directly rather than importing validator schema/hash helpers. Distinct policy bytes map to distinct URLs. Explicit synthetic provenance is mandatory for synthetic success. Read pinned Dockerfile/main.go for local build-byte inputs and retain known constant digests.
- [ ] Establish red import/API failure with `python3 -m unittest discover -s scripts/dev -p 'test_workshop_merchant_manifest.py' -v`; retain exact output and exit. Test successful synthetic consistency and owner_supplied_unverified consistency with all authorities false; no future artifact is required.
- [ ] Add subtests for every matrix row in the verification draft, including baseline exact168/hash and every-byte mutation. Snapshot temporary directory contents before/after and patch socket/subprocess/environment access to fail if attempted. Exercise CLI via patched argv/captured stdout calling main directly; do not invoke providers or shells.

Representative independent assertions (fixtures come from test-local byte literals; they do not use implementation helpers):

```python
self.assertEqual(result["status"], "prepared_offline")
self.assertEqual(result["manifest_sha256"], hashlib.sha256(candidate_bytes).hexdigest())
self.assertFalse(any(result["authorities"].values()))
self.assertEqual(result["accepted_case_credit"], 0)
self.assertEqual(baseline_result["status"], "blocked")
self.assertTrue(baseline_result["baseline_disabled"])
self.assertIn("merchant_inputs_pending", baseline_result["reasons"])
```

### Task 2: Pure offline evaluator and CLI

Files: create `scripts/dev/workshop_merchant_manifest.py`; modify only the test file from Task1. Consumes explicit file paths; produces exactly the spec result shape. There is no injection, artifact-verification or live-admission API.

- [ ] Implement bounded regular-file reads, strict JSON duplicate/non-finite/unknown-field rejection, stable reason-code collection and closed typed schemas exactly as spec. Keep raw bytes; compute SHA256 before JSON parsing; reject bool-as-int. Invalid/missing files return blocked without echoing input text.
- [ ] Validate URLs without normalization, per-policy exact URL/digest/length mapping, supported terms, nonblank tax bytes and final-price treatment, fixed USD2000 one_time product, declared source identity, actual supplied build file hashes and stripe_test account/Price reference tuple. An account/Price string is an unverified reference.
- [ ] Return deterministic sorted reasons, all false authorities and zero credit. Preserve prepared_offline even while external prerequisites are absent; exact baseline is valid disabled evidence with merchant_inputs_pending. CLI emits JSON to stdout only, exit0/3, argparse usage2, no timestamps/default writes or secrets.
- [ ] Run focused tests to green, retain red/green commands/counts; commit/push a coherent validated milestone only after explicit dispatch.

### Task 3: Source-only regression and independent review

Files remain exactly the two Python paths; future evidence updates are coordinator-owned gate records, not expanded builder scope.

- [ ] Run the exact commands in the verification draft, compare all seven immutable pins and allowed diff, retain failures/skips and commands honestly.
- [ ] Obtain independent exact implementation SHA/tree review and actual source-push/PR checkout CI readback. Fresh CI checks source consistency only; preserve external failed/pending checks separately. No TEST, customer, fixture, staging or release credit.

## Later owner and release boundary

Owner URLs, policy/contact bytes, tax decision and authentic Stripe TEST enrollment remain pending. A later separately synchronized gate must approve injection/rebuild, actual immutable OCI/binary/served-byte bindings, and real TEST evidence; local consistency cannot grant these. Vercel DNS control is current owner context, not authority to mutate DNS. Current Checkout lacks extra tax collection; tax prose cannot implement it.

## Planning provenance and limitations

Read external `/home/corp/autodata-evidence/merchant-manifest-plan/REPORT.md`, canonical gate, actual embedding, Dockerfile, current readiness predicates and tests, plus PR258 read-only. PR258 is draft/unmerged and explicitly excludes G1b; its synthetic readiness/DTO evidence supplies no merchant acceptance. No implementation tests were run during drafting. Only six planning paths change, preserving queue root and all53 objects. At the unchanged parent, canonical preflight still fails because these new documents are absent at that pinned SHA; a committed synchronized checkpoint is required.

## Coordinator tracking readback — planning synchronized

Updated at 2026-11-05T02:20:31Z. Exact goal, six todo strings, six gate paths and two prospective implementation paths are read back in https://github.com/lucronn/autodata/issues/186#issuecomment-6647901931; existing Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4 indexes that comment. Before snapshot `/home/corp/autodata-evidence/merchant-manifest-task54-before-tracking.json` SHA256 53eace0d9196c6ee4f12dc7b97fdc0afc0453f54210c3a822e5d6fd28ae3a2c9; after snapshot `/home/corp/autodata-evidence/merchant-manifest-task54-after-tracking.json` SHA256 7bdd2d118e39c2cfc3a4b911c55e3a0c8f5c71922cb5ad030d5393653cec0bde. Issue body SHA256 927b46ef47b1dbf5b117273e3d3f5c0e6d9f23b722a5245869eb5323b96c4f25; Project Source after SHA256 d2308af4c50c3083224c95f8bdf5d6323164975ed3e4f235235c0e01b6c6cfe2. Issue body, prior243 comments and other Project fields are unchanged; prior Project Source is archived verbatim in the comment. This agent made no GitHub write. Standalone/nested status and planning/tracking are synchronized; execution state remains blocked, all authorities false and current implementation allowlist empty. Checkpoint commit/push, external SHA/tree seal, exact-base positive preflights, independent review and explicit dispatch remain required.
