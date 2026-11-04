# Exact-Candidate Real-API Browser21 Acceptance Plan

> For agentic workers: planning only. Coordinator owns runtime execution and resource cleanup. Use the reviewed plan execution and independent review workflow only after a committed synchronized checkpoint and pinned preflight where implementation is needed. Execution/review profile: gpt-6.1-sol, medium, priority/Fast; no fallback.

**Goal:** Collect and independently assess exactly 21 real-API browser cases at immutable PR #198 head e5fed171bb36fdb759c592cbcd0e15aea5490c97 without changing implementation or claiming final release acceptance.

**Architecture:** Reuse the already reviewed external browser supervisor and frozen browser-runtime image. Run a one-case diagnostic pilot, then a separate fresh-root complete serial API lane at the same immutable SHA. A repair, if necessary, gets its own synchronized gate and new immutable candidate; never combine different candidates or selected-case repeats into a 21-case result.

**Tech stack:** Go 1.26, Python/pytest, Playwright 1.64.1, Chromium/Firefox/WebKit, PostgreSQL17/pgvector, NATS JetStream, SeaweedFS S3, production Firebase browser/Admin SDK and commerce/reconciler/worker code with synthetic external transports.

**Spec:** Candidate versions of `docs/verification/workshop-customer-ui-runbook.md`, `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md`, `docs/verification/release-acceptance-runbook.md`, `docs/agents/pre-implementation-gate.md`. Issue: https://github.com/lucronn/autodata/issues/186 ; Project: https://github.com/users/lucronn/projects/8 . Original draft performed no GitHub writes; the synchronized tracking readback below records the separately authorized writer update.

## 1. Status, authority, and exact identities

This docs-only checkpoint adopts independently approved draft SHA256 `0b88f7cacdd073984f5cad809f72be9c818d5de2d22b29afba3850c8a08db1d9` and input-manifest SHA256 `ee87deb865c06a84df92c1a8b0481f5ebc35cfdbd051bf32d9e1bf264ec67f13`. Its tracking status is **synchronized**, read back in Issue186 detail6623222525 and Project8. Only paid_evidence_plan holds the writer slot for this synchronization. Independent exact synchronized-checkpoint review, exact committed preflight and separate coordinator runtime authorization remain required; no implementation or runtime dispatch is authorized. Original research performed no application/service runtime or GitHub writes; this adoption changes only the nine named documentation paths below (including canonical tracking evidence).

Requested candidate is `e5fed171bb36fdb759c592cbcd0e15aea5490c97`. Research checkout HEAD was `eddcf724028683dbb083191e4f8c42064b866bf0`; it must not be passed directly as source to the frozen wrapper, whose prepare phase requires source HEAD equal requested candidate. Candidate files were inspected with `git show e5fed…:path`.

The lane must record independently: PR head, actual tested checkout SHA, planning checkpoint SHA, trusted historical gate base, image/build inputs, wrapper/runner hashes, CI workflow head and actual CI checkout SHA. Equal asset hashes never equate distinct candidate checkouts. Preserve previous API21 failures, one-case pilots, DTO117/3 failures and push-versus-PR-merge history as historical evidence.

Existing wrapper checks ancestry from gate `0da1309f860e475a1fa8b71a0d6b88dee04ed915`; that is not a substitute for a new repair task's committed checkpoint.

## 2. Frozen complete case inventory

File: `workers/ingestion-python/tests/test_workshop_browser_integration.py`. Engine order: chromium, firefox, webkit. Bank order: bankone, banktwo. First root has bankone fixture only and no bank suffix in pytest node ID.

1. `test_browser_google_exchange_checkout_library_real_api[chromium]`
2. `test_browser_google_exchange_checkout_library_real_api[firefox]`
3. `test_browser_google_exchange_checkout_library_real_api[webkit]`
4. `test_browser_owned_source_canonical_and_media_real_api[chromium-bankone]`
5. `test_browser_owned_source_canonical_and_media_real_api[chromium-banktwo]`
6. `test_browser_owned_source_canonical_and_media_real_api[firefox-bankone]`
7. `test_browser_owned_source_canonical_and_media_real_api[firefox-banktwo]`
8. `test_browser_owned_source_canonical_and_media_real_api[webkit-bankone]`
9. `test_browser_owned_source_canonical_and_media_real_api[webkit-banktwo]`
10. `test_browser_account_scope_and_revocation_real_api[chromium-bankone]`
11. `test_browser_account_scope_and_revocation_real_api[chromium-banktwo]`
12. `test_browser_account_scope_and_revocation_real_api[firefox-bankone]`
13. `test_browser_account_scope_and_revocation_real_api[firefox-banktwo]`
14. `test_browser_account_scope_and_revocation_real_api[webkit-bankone]`
15. `test_browser_account_scope_and_revocation_real_api[webkit-banktwo]`
16. `test_browser_signed_refund_blocks_old_links_real_api[chromium-bankone]`
17. `test_browser_signed_refund_blocks_old_links_real_api[chromium-banktwo]`
18. `test_browser_signed_refund_blocks_old_links_real_api[firefox-bankone]`
19. `test_browser_signed_refund_blocks_old_links_real_api[firefox-banktwo]`
20. `test_browser_signed_refund_blocks_old_links_real_api[webkit-bankone]`
21. `test_browser_signed_refund_blocks_old_links_real_api[webkit-banktwo]`

No engine selection, xdist, retries, xfail, skip, missing/unavailable engine, duplicate/extra row, or partial collection can pass this full lane. The pilot repeats case 1 diagnostically in a separate database/root; it adds zero logical acceptance cases.

## 3. Actual services and fixture boundaries

Use `infra/compose/compose.article-lifecycle-test.yaml`, not Base44 or production Compose. The frozen supervisor owns a unique Compose project, internal-only network, volumes, containers, temporary image tag, private Docker config and plain clone. Mount only exact candidate read-only at `/workspace` and owned writable evidence at `/artifacts`; no published ports, host networking, privilege, env_file, host credentials, or arbitrary bind paths.

Services: postgres `pgvector/pgvector:pg17` with disposable `lifecycle_fixture` plus unique `lifecycle_test_<uuid>` DB per case; nats `nats:2.10-alpine` with JetStream; minio service is SeaweedFS `ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d`, S3 port9000, unique lifecycle bucket per case. PostgreSQL/NATS tags are mutable in source: retain actual inspected image IDs/digests and Compose resolution; do not imply immutable service tags. Freeze them in a separately reviewed harness amendment if stronger reproducibility is required; do not silently rewrite Compose during this lane.

Each child uses `fresh_database()` and committed `scripts/dev/migrate_sql.sh` for migrations001..040, then `LifecycleRuntime`, `configure_scoped_runtime`, `BrowserBridge(PaidBridge)` and Go `paidSetup`. Bankone/Banktwo source upstreams and the model upstream are synthetic local HTTP fixtures, alongside synthetic Google/Firebase and Stripe external transports/events. Production connector/model adapters, actual Go/Python application and worker code, real CommerceService/private payment HTTP, PostgreSQL and S3 object IO execute against those fixtures; local ensure/control servers coordinate the owned test services. Actual public TLS auth/session, quote, checkout, order, library, prepare, detail, source/image handlers remain unintercepted; no authenticated cookie/role injection. Synthetic signatures enter the actual public webhook and private verifier/reconciler. The one-shot checkout response loss observes a successful actual API response before aborting it; manual retry must reuse exact key/body and response and add no provider work.

`TestWorkshopBrowserFixtureHTTP` is guarded by required test flags and owned ready path. It serves the exact eleven embedded assets, replacing only disabled merchant configuration in its guarded test mux with synthetic local policies. Official bundled browser SDK exchanges a fixture-signed token through actual `/auth/firebase/session`; official Admin SDK checks certificates/current users for two synthetic accounts. Keep production purchase-config disabled.

## 4. Immutable runtime and input manifest

Frozen external wrapper `/tmp/autodata-workshop-browser-supervisor-v2.py` SHA256 `a06bea8c6aa7b1fabdb29f3c2b8eba426d9004f2690e9c11ebc56dcb7b8f9c71`; immutable reviewed copy `/tmp/autodata-browser-v2-a06bea8-independent-review/candidate.py`. Inherited base `/tmp/autodata-r3-040-acceptance-supervisor.py` SHA256 `039a42c5287be5ed25d8b1c0b4724c1f9bad5f0e7f727a1270830a48304d28fa`. Independent v2 wrapper review: `/tmp/autodata-browser-v2-a06bea8-independent-review/review.md` and `results.json`, including retained exact-byte validation and negative mutations. The v2 validator requires the first-case `client_response_loss_same_key_one_checkout` assertion; the predecessor rejects that expanded exact assertion inventory and must not be used. The reviewed change leaves runner commands, image/build inputs, returned-ID resource checks, deadlines and cleanup unchanged. Wrapper changes require independent exact-byte review; no inline patching during acceptance.

Runtime image `sha256:26aea6a9df1a7139e20a6893d9b63a11ab6b9978d113c718c6a792616be5a888`, built with target browser-runtime. Original build receipt `/tmp/autodata-browser-runtime-0f2803d/result.json` has status failed because the original engine probe failed; preserve that status. It binds image/six inputs but is not a passing probe/acceptance receipt. Historical successful probe `/tmp/autodata-ui-engine-probe-78943a6c39d6/result.json`, SHA256 `5dd7060edb13f215107e8125f164cbc57c92152f8c39302f7db9b18eb914b02e`, was read back during this revision. It records source candidate `9ae280942a453b7e1d011899ce74a9ef55647c10`, this same image and six inputs, Playwright1.64.1, Chromium156.0.8078.4, Firefox157.0 and WebKit27.2, all launched with exit0 and cleanup exit0. Its isolated launch probe used network none, user1000:1000,2GiB memory,256PIDs,256MiB shared memory and768MiB /tmp tmpfs. Those settings differ from the acceptance runner; it proves historical synthetic launch only, not current image/engine availability, current host capacity or exact-e5fed17 API21 acceptance. Preserve both historical receipts. Actual image availability and current engine launch remain runtime preconditions.

Candidate six image inputs match frozen wrapper literals:

| Path | SHA256 |
|---|---|
| infra/compose/article-lifecycle-test.Dockerfile | ea1d9f043e8775ecbdeea60e9df86ade41fe2d61bd9aadb557479be745e6fc5f |
| scripts/dev/requirements-workshop-browser.txt | adeb8976dfd2edb0e44e74da84319fae6d821478330c93e39829516c01d5fe25 |
| workers/ingestion-python/pyproject.toml | 9ed011cb0de6069669b31d1ebd66ee1a0fba63ee699cd90535f46358432ef1c1 |
| apps/api-go/go.mod | 3306c3736c51a3c08a4ed30613a9f0ba4db7f5094d0215ebdf54545873012923 |
| apps/api-go/go.sum | 87fc8d7330f3b3094320ed3a09e60837944dfb0c1deb0c0ab4de6a4bb1f3959d |
| packages/contracts/go/go.mod | d12a75dfc4eaa0beeca1e2e711726e3e8bcd1dcc59383f554ff4345bd6a2b5c9 |

Playwright exactly1.64.1. Chromium156.0.8078.4 revision1248; Firefox157.0 revision1555; WebKit27.2 revision2370. Complete manifest must also match chromium-headless-shell1248, ffmpeg1013, winldd1007, android1001 as frozen wrapper requires. Do not install packages/browsers during acceptance or use a fallback image.

Canonical planning input manifest `docs/agents/records/2026-11-04-workshop-api21-inputs.json` (byte-identical research source `/tmp/autodata-api21-e5fed17-inputs.json`), SHA256 `ee87deb865c06a84df92c1a8b0481f5ebc35cfdbd051bf32d9e1bf264ec67f13`, pins the six image inputs, smoke runner/unit/environment tests, integration/lifecycle/paid helpers, Go fixture, four fixture resources, eleven embedded assets and forty migrations by SHA256 of committed Git blobs; its separate external_sha256 map pins the approved v2 wrapper/frozen copy/review/base and both historical runtime receipts. It supplements, not replaces, supervisor-generated complete host/runner input manifests and before/after observations. Record the manifest hash and actual bytes in the run inventory; preserve regenerated manifest as a distinct artifact on any successor SHA.

## 5. Concrete execution checklist and commands (future only)

- [ ] Coordinator approves this lane's exact draft hash, candidate and available serial capacity. Read back existing exact-candidate review/CI; acceptance success cannot repair their absence. Before code edits, synchronize the new plan/Issue186/Project8/canonical docs/concrete todo/task/record, commit the checkpoint and pass full-SHA preflight and independent gate review. Tracking synchronization alone grants no implementation or runtime authorization.
- [ ] Prepare a clean owned plain source clone at exact e5fed17 because the current checkout is ahead. Ensure destination absent; preserve source checkout and other agents' resources. Clone without hardlinks, remove remote, detach requested SHA and check clean status. The wrapper then creates its own separate plain clone.

```sh
git -c core.hooksPath=/dev/null clone --no-hardlinks --no-checkout /home/corp/Documents/ChatGPT/autodata /home/corp/autodata-evidence/api21-e5fed17-source
git -C /home/corp/autodata-evidence/api21-e5fed17-source remote remove origin
git -C /home/corp/autodata-evidence/api21-e5fed17-source checkout --detach e5fed171bb36fdb759c592cbcd0e15aea5490c97
git -C /home/corp/autodata-evidence/api21-e5fed17-source rev-parse HEAD
git -C /home/corp/autodata-evidence/api21-e5fed17-source status --porcelain=v1 --untracked-files=all
sha256sum /tmp/autodata-workshop-browser-supervisor-v2.py /tmp/autodata-r3-040-acceptance-supervisor.py
python3 /tmp/autodata-workshop-browser-supervisor-v2.py --self-test
```

- [ ] Verify immutable image available and read back the exact pinned historical successful engine-probe receipt; inspect image ID and literal six input equality, exact source SHA/cleanliness/ancestry, owned directories, ports/mounts/network and no foreign resources. Record actual service image IDs. If preconditions fail, preserve diagnosis and stop; do not rebuild/update dependencies to make this run pass.
- [ ] Run the diagnostic Chromium checkout/library pilot once. Use an absent root; never reuse a failure root.

```sh
python3 /tmp/autodata-workshop-browser-supervisor-v2.py \
  --source-repo /home/corp/autodata-evidence/api21-e5fed17-source \
  --candidate-sha e5fed171bb36fdb759c592cbcd0e15aea5490c97 \
  --run-root /home/corp/autodata-evidence/api21-e5fed17-pilot-20261104 \
  --mode first \
  --prepare-timeout-seconds 120 --build-timeout-seconds 120 \
  --start-timeout-seconds 180 --test-timeout-seconds 330 \
  --finalize-timeout-seconds 180 --total-timeout-seconds 1200
```

- [ ] If the pilot passes raw verification, run the complete unchanged inventory once in a separate absent root; if it fails, stop and classify/retain before repair. Do not count pilot toward21.

```sh
python3 /tmp/autodata-workshop-browser-supervisor-v2.py \
  --source-repo /home/corp/autodata-evidence/api21-e5fed17-source \
  --candidate-sha e5fed171bb36fdb759c592cbcd0e15aea5490c97 \
  --run-root /home/corp/autodata-evidence/api21-e5fed17-full-20261104 \
  --mode api \
  --prepare-timeout-seconds 120 --build-timeout-seconds 120 \
  --start-timeout-seconds 180 --test-timeout-seconds 2350 \
  --finalize-timeout-seconds 180 --total-timeout-seconds 3300
```

Actual frozen runner precompiles `go test -run '^$' .` in apps/api-go with180s cap, then runs the following within its owned go-test-runner (2050s cap,120s for pilot). Do not invoke this directly on a host/application DB:

```sh
AUTODATA_LIFECYCLE_TEST=1 \
AUTODATA_CATALOG_INTEGRATION_REQUIRED=1 \
AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION=1 \
AUTODATA_R3_CANDIDATE_SHA=e5fed171bb36fdb759c592cbcd0e15aea5490c97 \
GOTOOLCHAIN=local GOPROXY=off \
python -m pytest -q -p no:cacheprovider \
  --junitxml=/artifacts/workshop-browser-api.xml \
  workers/ingestion-python/tests/test_workshop_browser_integration.py
```

Compose supplies PYTHONPATH, lifecycle flags and GOFLAGS; wrapper sets `GOFLAGS=-mod=readonly -p=2`. Parent case whitelists env; no ambient cloud/merchant/DSN credentials enter. Runner uses host UID/GID; XDG_CACHE_HOME=/tmp/autodata-browser-cache, XDG_CONFIG_HOME=/tmp/autodata-browser-config, TMPDIR=/tmp/autodata-browser-tmp, GOCACHE=/var/tmp/autodata-browser-go-cache, GOTMPDIR=/var/tmp/autodata-browser-go-tmp (0700). Wrapper preserves its HOME. Each final browser subprocess separately receives a new owned0700 browser-home beneath its case directory, as required by the committed private-HOME repair.

## 6. Resource and time bounds

Coordinator-reported read-only resource scout on 2026-11-04 observed approximately 2.36 GiB free on /tmp tmpfs and 17.24 GiB free under /home/corp/autodata-evidence; the source/pilot/full sibling roots below were absent and non-symlink at that observation. The reviewed wrapper permits those sibling roots. Use `/home/corp/autodata-evidence/api21-e5fed17-source`, `/home/corp/autodata-evidence/api21-e5fed17-pilot-20261104` and `/home/corp/autodata-evidence/api21-e5fed17-full-20261104` for the exact source/pilot/full commands. Free space is transient availability evidence, not a reserved quota, full host-capacity proof, a launch authorization or an API21 acceptance result; coordinator must recheck ownership, absence/non-symlink paths and disk headroom immediately before any separately authorized launch. No wrapper bytes, frozen manifest, image/input hashes, case inventory, deadlines or resource limits change.

Fully serial execution, one lane at a time; no parallel paid/DTO/container build on the host during this lane. Host capacity is coordinator-owned and unverified by planning. Frozen wrapper updates only exact returned owned runner ID to2GiB RAM,2GiB total RAM+swap,2CPUs,512PIDs, then inspects exact limits and UID/GID into `owned-runner-limits.json`. These apply after startup; no pre-launch guarantee or limits on PG/NATS/S3 services are claimed. Current Compose has no explicit shm_size; do not borrow historical256MiB probe shared-memory claim for this acceptance runner. Record actual inspected ShmSize. Changing limits/shm/service resource bounds requires separately reviewed supervisor/fixture adaptation.

Full outer run3300s includes180s finalization reserve, below canonical4500s ceiling and at least60s reserve. Start services wait150s with165s subprocess cap inside180s phase; precompile180s then pytest2050s inside2350s test phase. Child parent waits84s from start, with six seconds reserved in nominal90s case budget for group termination/fixture/database cleanup. Child has78s deadline, Go test85s safety timeout, browser api_case65s; fixture readiness must leave15s, browser subprocess leaves8s of child budget. Preserve these exact bounds. The parent finalizer may not itself prove every DB/network teardown completed inside90s; outer finalization and cleanup observations must be retained rather than claiming a stronger bound than implementation.

Wrapper artifact inventory permits at most20,000 paths,128MiB per file,2GiB aggregate and rejects symlink/nonregular paths. These are post-run inventory bounds, not disk quotas. Reserve host disk headroom above2GiB plus clone/cache/service volumes before launch. API mode has screenshot best effort1500ms and context.close in finally under api_case watchdog; DTO trace/3s cleanup amendment does not apply to API mode. No required API trace ZIP or16MiB API trace guarantee exists.

## 7. Failure retention and diagnosis

- [ ] Preserve every original pilot/full root with acceptance-result, commands/logs, inventory, resolved Compose, input manifests, host/runner before/after, image inspection/runtime binding, owned limits, JUnit, compile/Go fixture/browser/child logs, ready/result/browser evidence, synthetic screenshots, service logs and cleanup receipts. Files private0600/directories0700 under owned root. Never modify raw evidence or delete failed screenshots to gain pass.
- [ ] Failure classes: preflight/provenance or candidate mismatch; engine unavailable; service readiness; compile; actual scenario assertion; timeout/cancellation/OOM/resource failure; artifact/cleanup failure. Keep observed stage and actual failure; no inferred cause from a later selected-case pass.
- [ ] Missing evidence is unavailable/failed, never filled from other runs. API request logs use safe route templates and exclude raw auth headers/tokens/signed capability paths. Treat synthetic screenshots/low-level logs as private; independently scan retained evidence before sharing. Do not add raw secret capture for debugging.
- [ ] On timeout/SIGINT/TERM, kill/reap only owned process groups; child teardown stops Go/worker/model activity and removes its bucket, parent drops owned DBs, outer supervisor stops only verified project-owned containers and removes owned volumes/network/tag/builder. Retain explicit cleanup errors and remaining owned IDs; never broad Docker prune or removal of foreign processes. Runtime image itself remains available; temporary tag only is owned cleanup.
- [ ] No automatic rerun. A subsequent explicitly authorized diagnostic or fresh acceptance uses a new root and full immutable SHA identity; earlier failed result remains failed.

## 8. Contingent fixture-repair scope and required gate

Default acceptance execution edits zero repository files. If an observed fixture defect prevents the lane, stop full acceptance, retain evidence, and draft the smallest repair under the canonical gate. Prospective maximum fixture-only scope for review (not present authority to edit):

- `scripts/dev/workshop_browser_smoke.py`: API fixture transport/assertion/provenance/teardown only; preserve DTO semantics, exact four roots, deadlines and actual application responses.
- `scripts/dev/test_workshop_browser_smoke.py`: focused deterministic regression for that observed defect, including rejection/unchanged assertions.
- `workers/ingestion-python/tests/test_workshop_browser_integration.py`: owned test process/env/setup/cleanup only.
- `scripts/dev/test_workshop_browser_environment.py`: focused regression for owned subprocess environment/setup/cleanup changes.
- `apps/api-go/workshop_browser_fixture_test.go`: guarded test mux/dependency transport/restart fixture and test-only regression only.

Each repair gate must narrow this list to actual required paths. Shared lifecycle_support.py, PaidBridge/helpers, production handlers/auth/catalog/commerce/UI/assets, migrations/contracts, dependencies/lockfiles, image six inputs, Compose/workflows, external frozen supervisor, R6 assembler/profiles and deployment/hosting are excluded. A demonstrated defect in those paths returns to its owning separately synchronized lane; do not weaken a browser expectation to hide a product defect. Frozen fixture JSON/transport resources also remain unchanged unless separately reviewed scope explicitly includes the named file.

Required planning paths for adoption: dedicated `docs/superpowers/plans/2026-11-04-workshop-api21-acceptance.md`, dedicated task and record under docs/agents, canonical UI plan/runbook, production orchestration plan and queue. Exact goal/todo/allowlist/limitations go into Issue186 and Project8 Source/dependency field with prior text retained and readback hashes. Commit/push plan-only checkpoint, pin full SHA, then:

```sh
python3 scripts/autonomy/pre_implementation.py \
  --record docs/agents/records/2026-11-04-workshop-api21-acceptance.json \
  --base-sha "$PINNED_CHECKPOINT_SHA" \
  --repo-root "$OWNED_REPAIR_CHECKOUT"
```

PINNED_CHECKPOINT_SHA and OWNED_REPAIR_CHECKOUT are coordinator-resolved immutable checkpoint and clean owned checkout, never inferred from this draft. Required record fields are goal, plan_ref, issue_ref, project_ref, repository_doc_refs, concrete todo, status=synchronized, updated_at. Machine result must be synchronized/errors=[] and independently approved before implementation. Small coherent regression/fix commits get appropriate checks then prompt push on assigned codex/ feature branch; no merge/deploy authority follows.

After fixture repair run focused unittest(s), syntax/inventory checks, applicable Go fixture tests; if Go fixture changed, full Go tests/vet. Baseline commands:

```sh
python3 -m unittest discover -s scripts/dev -p 'test_workshop_browser_smoke.py' -v
python3 -m unittest discover -s scripts/dev -p 'test_workshop_browser_environment.py' -v
node --test apps/api-go/workshop-client.test.mjs
go -C apps/api-go test ./... -run 'TestWorkshopBrowser' -count=1
go -C apps/api-go test ./...
go -C apps/api-go vet ./...
git diff --check
```

These are future verification commands, not executed in this planning task. Add focused meaningful red/green for actual defect, preserve21/120 identities and six image input hashes, scope/diff check, independent exact-commit review. Integrate only reviewed fix under coordinator authority, then re-pin final successor candidate and collect a fresh pilot/full21. e5fed17 results cannot certify successor SHA.

## 9. Independent acceptance review and release relationship

- [ ] Independent reviewer checks exact immutable candidate and approved wrapper bytes; actual source/runner SHA and clean plain-clone before/after; six image inputs/image IDs, migrations001..040,11 served asset bytes/SDK/TLS certificate hash, six browser-evidence input hashes and engine versions/revisions.
- [ ] Re-derive exactly21 unique pytest IDs/JUnit class `tests.test_workshop_browser_integration`, no failed/error/skipped/extra rows and matching21 result directories. Each result is passed=true with matching test/engine/provider/candidate; browser evidence has exactly one passed row of matching identity. Three first-root result directories use engine-bankone even though JUnit lacks bank suffix. Check wrapper's raw financial/access/session and provider/S3/counter validation against every retained receipt, not a top-level pass alone.
- [ ] All21 must assert official SDK cookie/hashed PG session; return-not-grant; signed webhook grants once; permanent owner library reload and actual application replacement at same HTTPS origin without another purchase and unchanged durable order/grant/session counts. First3 additionally assert actual lost browser checkout response plus exact same-key retry, one order/provider checkout, and no protected localStorage.
- [ ] Other18 additionally require readable source and actual S3 image, canonical publication and warm reload+pinned source+approved image with unchanged provider/source/asset/model calls, row hash and source/rewrite/publication counts, while actual S3 image reads increase. Six isolation cases require adjacent/other-region/unscoped/legacy and other-account denial (wrong-account image404), logout+bfcache clearing and Firebase disable denial. Six refund cases require signed full refund/revoked order and old image/source/detail403 plus UI/library revoked state. Do not reinterpret server app restart as PG restart/production deployment restart.
- [ ] Verify logs/artifact hashes and actual cleanup/resource receipts. Independent reviewer is not the code author; review at exact tested SHA and retain report/hash/identity. Author wrapper marks author_run=true and final_independent_acceptance=false; successful author run alone must not be reported as independently accepted.

Full fixture inventory is5 identity +8 R3 +14 commerce +12 paid-access +120 DTO +21 API =180 logical cases. API21 supplies only its21 slot; pilot supplies0. Supporting unit/contract/security/secret scans, production image/embedded assets/SDK/license proof, build/SBOM/provenance/CI and reviewer/supervisor authority add0 cases and remain mandatory. Historical receipts from earlier SHAs and matching bytes cannot satisfy final-head coverage. Collect all180 and support at final immutable candidate with complete exact-head CI and checkout provenance, under separately owned lanes.

R6 profiles remain disabled; current assembler unavailable results and false authority flags cannot be promoted by this lane or by a raw21 pass. A future independently verified complete fixture tier can establish only fixture_verified under its own approved profiles. Real HTTPS Google popup/domain registration, actual test-mode Stripe hosting/webhooks, merchant policy/contact/tax configuration, licensed banks, protected population, host isolation/recovery/alerts and all eight staging gates remain separate. No staging/product/deployment/cutover/cars.tk or production readiness claim follows; no credentials are requested by this plan.

## 10. Hard blockers at handoff

1. Tracking is synchronized by the readback below; this docs-only checkpoint authorizes no fixture repair or runtime dispatch. The committed checkpoint still requires full-SHA preflight, independent exact synchronized-checkpoint review and separate coordinator runtime authorization before any later dispatch.
2. Source HEAD currently differs from requested candidate. Wrapper rejects direct use; an owned clean exact-e5fed17 source clone is required.
3. The planner performed no runtime checks; the coordinator-reported read-only disk-space/path scout in section 6 supplies limited availability observations only. Broader runtime capacity, Docker availability, current immutable image presence, actual service image identities and current engine launch remain unverified by this planning task. Historical original build receipt remains failed; the later successful probe is now located, hashed and read back, but its different settings and earlier source do not prove current availability or exact-candidate acceptance. Preserve both. Do not silently replace image or versions if missing.
4. No fresh full exact-e5fed17 API21 evidence, cleanup proof, independent acceptance review or final-candidate180/support/CI completeness was collected in this task. These remain unresolved acceptance obligations, not a code defect diagnosis.

## 11. Docs-only checkpoint and synchronized tracking record

This task edits only the following documentation paths; its allowed implementation path list is empty. The five contingent repair paths in section 8 are a maximum planning boundary, never an authorized allowlist for this checkpoint. Tracking synchronization belongs exclusively to paid_evidence_plan. Preserve all existing queue entries and top-level authority.

- `docs/superpowers/plans/2026-11-04-workshop-api21-acceptance.md`
- `docs/agents/records/2026-11-04-workshop-api21-acceptance.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-api21-acceptance.json`
- `docs/agents/records/2026-11-04-workshop-api21-inputs.json`
- `docs/agents/records/2026-11-04-workshop-api21-tracking-evidence.json`
- `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md`
- `docs/verification/workshop-customer-ui-runbook.md`
- `docs/superpowers/plans/2026-11-03-production-release-orchestration.md`
- `docs/agents/tasks/2026-11-03-production-release/queue.json`

### Concrete todo

- [ ] Sole tracking writer paid_evidence_plan synchronizes this exact goal, six todos, docs-only scope, candidate and runtime limits in Issue186/Project8 with readback hashes, preserving historical indexes; coordinator commits the synchronized successor checkpoint, pins its full SHA, passes exact-base preflight and obtains independent checkpoint review before dispatch.
- [ ] Coordinator verifies a clean exact-e5fed17 source clone, approved v2 supervisor a06bea8 and inherited base, immutable runtime image and six inputs, retained successful historical probe, actual service image identities and available serial host capacity; missing preconditions remain blocked.
- [ ] After separate coordinator runtime authorization, execute one Chromium checkout/library pilot in a fresh private owned root; retain all raw outcomes, provenance and cleanup, and count zero acceptance cases from the pilot.
- [ ] If pilot passes raw verification, execute the unchanged complete 3+6+6+6 API inventory once in a different fresh root at the same immutable SHA using the approved v2 supervisor, 3300-second total and 180-second finalization reserve; no retries, skips, missing engines or combined partial runs.
- [ ] Independently review exact candidate, 21 unique JUnit/receipt identities, assertion inventories, actual HTTP/PG/S3 and warm/restart facts, input/asset/SDK/TLS/browser/image provenance, private artifact hashes and owned cleanup; retain failures and require a separately narrowed synchronized gate for any fixture repair.
- [ ] Keep final-candidate 5+8+14+12+120+21=180 logical cases, supporting scans/images/SDK/license/CI/reviewer authority and all live staging/release gates separate; support and pilot evidence add zero cases and no release profile or authority flag is promoted.

The required gate record is synchronized only after the sole tracking writer verified the complete readback below; exact committed preflight and independent synchronized-checkpoint review remain separate. No implementation base SHA is invented: the acceptance application SHA stays e5fed17; a later synchronized planning checkpoint SHA is separately pinned. Independent PASS for the temporary draft is not approval of this later committed checkpoint.

```json
{
  "goal": "Collect and independently assess exactly 21 real-API browser cases at immutable PR #198 head e5fed171bb36fdb759c592cbcd0e15aea5490c97 without changing implementation or claiming final release acceptance.",
  "plan_ref": "docs/superpowers/plans/2026-11-04-workshop-api21-acceptance.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/superpowers/plans/2026-11-04-workshop-api21-acceptance.md",
    "docs/superpowers/plans/2026-11-03-workshop-customer-ui.md",
    "docs/verification/workshop-customer-ui-runbook.md",
    "docs/superpowers/plans/2026-11-03-production-release-orchestration.md"
  ],
  "todo": [
    "Sole tracking writer paid_evidence_plan synchronizes this exact goal, six todos, docs-only scope, candidate and runtime limits in Issue186/Project8 with readback hashes, preserving historical indexes; coordinator commits the synchronized successor checkpoint, pins its full SHA, passes exact-base preflight and obtains independent checkpoint review before dispatch.",
    "Coordinator verifies a clean exact-e5fed17 source clone, approved v2 supervisor a06bea8 and inherited base, immutable runtime image and six inputs, retained successful historical probe, actual service image identities and available serial host capacity; missing preconditions remain blocked.",
    "After separate coordinator runtime authorization, execute one Chromium checkout/library pilot in a fresh private owned root; retain all raw outcomes, provenance and cleanup, and count zero acceptance cases from the pilot.",
    "If pilot passes raw verification, execute the unchanged complete 3+6+6+6 API inventory once in a different fresh root at the same immutable SHA using the approved v2 supervisor, 3300-second total and 180-second finalization reserve; no retries, skips, missing engines or combined partial runs.",
    "Independently review exact candidate, 21 unique JUnit/receipt identities, assertion inventories, actual HTTP/PG/S3 and warm/restart facts, input/asset/SDK/TLS/browser/image provenance, private artifact hashes and owned cleanup; retain failures and require a separately narrowed synchronized gate for any fixture repair.",
    "Keep final-candidate 5+8+14+12+120+21=180 logical cases, supporting scans/images/SDK/license/CI/reviewer authority and all live staging/release gates separate; support and pilot evidence add zero cases and no release profile or authority flag is promoted."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-04T05:17:24.198647+00:00"
}
```


### API21 tracking synchronization readback (2026-11-04)

Authorized sole writer `paid_evidence_plan` synchronized the unchanged exact-e5fed171 API21 goal and six todos from independently reviewed docs-only checkpoint `a3a48dae1467e6d346715252a2f824599b2ee9f5`. Detail [6623222525](https://github.com/lucronn/autodata/issues/186#issuecomment-6623222525) SHA256 `982d1fd09ac60de966c68fdfcf8c27ea0ab6fd5a74bf403298ae342778c6d3a1`; Source index959 characters SHA256 `13a3f3be5857257ad9594c051265b8cfb9971342e4f8d68bd2048e349df2d745`; read back `2026-11-04T05:17:24.198647+00:00`. Complete original Issue body/all125 predecessor comments/current Project values are preserved verbatim with SHA256 in `docs/agents/records/2026-11-04-workshop-api21-tracking-evidence.json`. Issue body/all prior comments and all other Project fields remain unchanged, Status In Progress; latest PG/integration/paid pointers retained. Canonical record/task/queue now say synchronized after readback; exact committed preflight and independent exact synchronized-checkpoint review remain required. All implementation/runtime authorization remains false and implementation allowlist empty. No Docker/browser/provider/runtime execution, API21 outcome, final180 acceptance, profile promotion or live/release authority is claimed. Six original todos, frozen input manifest/hash, application candidate, approved supervisor/image, persistent evidence roots and every runtime limit remain unchanged.


### API21 immutable synchronized gate pin

Gate `e0e50dee3a5f985dd1f7586fc7a4d681aaf77323` was pushed/read back on `codex/workshop-api21-acceptance-plan`; its exact full-SHA preflight returned exit0 and `{"status": "synchronized", "errors": []}`. Pin [6623235715](https://github.com/lucronn/autodata/issues/186#issuecomment-6623235715) body SHA256 `d7d4e31888f1ac1b1aca74254feaa2d337b5eee819097717685cb869dc3f05ea`; final Source index1020 characters SHA256 `34ec4999d518265a3c63075d6369d7d9cfcdad8f60112666fa2bc254b288e66c`, reread `2026-11-04T05:18:05.547775+00:00`. Complete preserved predecessor Issue body/all125 comments and current field/pin readbacks are in `docs/agents/records/2026-11-04-workshop-api21-tracking-evidence.json`; predecessor body/comments/detail and every non-Source Project field remain unchanged, Status In Progress. This later receipt leaves immutable application candidate e5fed171 and gate SHA distinct. Independent exact synchronized-gate review and separate coordinator runtime authorization remain required; implementation allowlist empty and runtime/implementation authorization false. No browser/Docker execution or acceptance claim occurred.


## API21 interruption-recovery successor — synchronized; exact checkpoint review pending

Dedicated plan `docs/superpowers/plans/2026-11-04-workshop-api21-interruption-recovery.md`, task `docs/agents/tasks/2026-11-03-production-release/workshop-api21-interruption-recovery.json`, record `docs/agents/records/2026-11-04-workshop-api21-interruption-recovery.json`, tracking evidence `docs/agents/records/2026-11-04-workshop-api21-interruption-recovery-tracking-evidence.json`. Obtain one complete immutable full21 author-run receipt and independent raw acceptance review at application candidate e5fed171bb36fdb759c592cbcd0e15aea5490c97, preserving the interrupted original root and unchanged approved supervisor/runtime/fixtures; no implementation or release acceptance claim. Original gate e0e50dee and final receipt b1ac3c7c remain historical; audit543985c4 confirms21 scenario receipts but missing supervisor finalization, cleanup0e6587d7 is supplemental only. New absent full root and retained-state user-service canary are prerequisites under the reviewed plan; no runtime/canary/implementation dispatch or acceptance claim.

- [ ] Preserve/classify old full run as interrupted/incomplete despite21/21 observed JUnit; retain supplemental cleanup hash and independent raw audit, without modifying/relabeling old root.
- [ ] Synchronize exact recovery goal, these six todos, new roots, process supervision and zero implementation scope in Issue186/Project8/canonical docs/task/record; commit/push docs checkpoint, pin full SHA, pass exact-base preflight and independent checkpoint review; obtain bounded coordinator dispatch.
- [ ] Revalidate exact clean source, approved wrapper/base/manifest/image/engines, completed pilot raw evidence, current service image identities, owned absent roots and serial host capacity; prove chosen user-service supervision with a harmless bounded owned canary, otherwise stop.
- [ ] Dispatch the unchanged complete full21 command exactly once in its new root through the reviewed Restart=no user service; retain outer argv/identity/exit/log evidence separately, preserve existing deadlines/resources and remain under bounded observation through supervisor finalization.
- [ ] Independently audit all21 raw cases, exact candidate and input/runtime provenance, supervisor final receipt/inventory/host-after, hashes/privacy and owned cleanup; retain every failure and require a separate synchronized gate for any repair or later attempt.
- [ ] Keep final-head180/support/security/images/SDK/license/CI/reviewer proof and all staging/product/release/deployment/cutover gates separate; pilot/support add zero logical cases, historical evidence cannot certify another SHA, and all profile/authority promotion stays false.


### Recovery tracking synchronized — exact checkpoint review still required

Authorized sole writer api21_recovery_plan appended detail https://github.com/lucronn/autodata/issues/186#issuecomment-6624161772 (SHA256 3f07b2a0ce2c191dfa1c0b39c2265567c735c7aef65c0150c5bc62038c42e9f5), and read back the 912-character Project8 Source index (SHA256 1263446217268cd3bd9e34f706ce225151038932eb5f63d0e2e2d607b82c8e26) at 2026-11-04T06:22:41.129299+00:00. Complete original Issue body/all127 predecessor comments and all other Project item fields are byte-preserved in tracking evidence; Status In Progress. Exact six todos, zero implementation scope, approved draft42dd282a, unchanged e5fed171 candidate and frozen inputs/limits are synchronized. No runtime/canary/implementation dispatch or acceptance claim; committed exact-base preflight and independent exact-checkpoint review remain required.


### Recovery exact checkpoint pin and final readback

Synchronized gate `5087d33d0e2ec57318aff0fb9d516142ca573ad6` pushed on `codex/workshop-api21-interruption-recovery`; exact full-SHA machine preflight exit0 / `status: synchronized`, `errors: []`, empty stderr. Pin https://github.com/lucronn/autodata/issues/186#issuecomment-6624174482 (SHA256 4bb66bcdc433ca89d9ac62ce6923b1e8d416abcdc44f417fb5af5d7f534cbd51); final Project Source 973 characters SHA256 a052e801bd9cc8b78073e510525ead56a4979074cbb6d6b0f6c7deb2d1a4dac2, read back 2026-11-04T06:23:19.578858+00:00. Complete original Issue body/all127 predecessor comments, detail and all other Project item fields remain unchanged; Status In Progress. Tracking evidence retains complete final readback and preflight. Draft PASS does not satisfy independent exact committed-checkpoint review, which remains pending. No implementation, runtime, canary or Docker dispatch, no acceptance or profile/release promotion. Writer slot releases after final receipt push.


## API21 recovery completion — independent PASS; tracking synchronized

The [recovery completion record](2026-11-04-workshop-api21-interruption-recovery.md#api21-recovery-independently-verified--tracking-synchronized-2026-11-04) supersedes the planning-stage pending/no-runtime statements above for this completed bounded run. Independent audit SHA256 `8b8097194fd9bb6f05e33ddeda86fef0d30c1202ee10ce304682f4bb63fdb2f2` passed exactly21 synthetic real-API cases at `e5fed171bb36fdb759c592cbcd0e15aea5490c97`. Author receipt `b8de6bb417c719c29f4283463974ac1da5264f82670263f253f5153972367818`, inventory `9b1e8e1a1b4a5ca7e269c45b5c192196eac3ac32cb801b62613f9f6d45076184` (380 files /7,947,925 bytes), original host-after `51e636f126e30da9052ea08bfe93f65b41372ec7489bc6db43ed82c49b2145b4` and external supervision `02b6d5076a1bba6f4b6123768fc37b03d88076e212e78ab86cd62520dcef7168` bind one finalized exit0/no-restart run and independent owned cleanup. Recovery todos1–5 are complete;6 remains an upheld boundary with final-head180/support/CI/live gates outstanding. Original interrupted run stays immutable/incomplete; pilot/canary add0 cases. Local upstream transports remain synthetic; application/HTTP/PG/workers/S3 execute. No launch readiness, final180, profile promotion, staging/product/release/deployment/cutover authority follows. Coordinator completion Issue186/Project8 readback is synchronized; no new runtime is authorized.


### Completion tracking readback

Coordinator completion comment [6624382132](https://github.com/lucronn/autodata/issues/186#issuecomment-6624382132), SHA256 `4676b7d60463e6d4e010438804184d7ad8f649f6183dbff34ec32845fc10d31c` (2005 bytes), and Project8 Source901 characters SHA256 `14dadd76546d67e8dbec6d56d8ef40efd7c46a12deebb927d46e915cf9b33123` were independently read back. Complete current Issue body/all132 comments and Project item are preserved verbatim in `docs/agents/records/2026-11-04-workshop-api21-interruption-recovery-tracking-evidence.json`; all historical predecessor bodies and other Project fields remain unchanged, Status In Progress. This completion documentation grants no implementation/runtime/release authority.
