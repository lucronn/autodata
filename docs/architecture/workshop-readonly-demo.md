# Workshop read-only demonstration

The explicit `/workshop/?demo=1` entry is a separate browser bootstrap path for fictional, repository-authored sample content. A visible persistent banner says “Demo — sample content. No purchase or vehicle access is granted.” The fixture uses a fictional vehicle (“2026 Example Motors Sample”, “Demonstration trim”) and a non-procedural sample article (“Understanding this sample manual”). It contains no licensed provider article, provider identifier, service instruction, torque value or invented source citation. Its provenance says “Illustrative content authored for this demo; not supplied by Bankone or Banktwo. Not vehicle service information.”

The demo reuses Workshop markup and styles, but its module is loaded before any normal application module. The normal `app.mjs` remains the default bootstrap. The demo enables selector progression, article search, reader and back navigation entirely in browser memory. A displayed $20 USD amount is labeled “Illustrative price — checkout unavailable in demo”. Purchase, sign-in, order checks and account/library mutations are disabled. No database writes, entitlement grants, live source/canonical reads, model calls or API requests occur. Reloading `?demo=1` returns to the sample. A link to the regular Workshop exits demo mode explicitly.

Normal Workshop authentication, rights and paid-catalog enforcement retain their existing contracts. Demo mode never adds a server entitlement exception, client fake grant, Stripe fixture or seeded production customer. Static sample assets are public demonstration material.

## Inception model configuration

The coordinator verified the official provider catalog lists `mercury-3` as current/newest on 2026-11-06. `mercury-2` and `mercury-2.5` remain listed; no retirement or deprecation is claimed. Update constructor/environment and Compose defaults to `mercury-3`; explicit `INCEPTION_MODEL` overrides continue to work. The shared client sends `temperature: 0.5` for Mercury-3 (valid provider range 0.5–1) and `max_completion_tokens` with the existing `INCEPTION_MAX_TOKENS` budget. Explicit older-model overrides retain their prior compatible `temperature: 0` and `max_tokens` request shape. Historical extraction-mode/generation metadata and legacy class/module names are not renamed.

Secrets remain environment/platform managed. This change does not require or print keys, and demo mode never consumes the model client.

## Tracking and acceptance

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-06-workshop-readonly-demo.md`
Record: `docs/agents/records/2026-11-06-workshop-readonly-demo.json`

Concrete todo:
- [ ] Implement an explicit fixture-only Workshop demo entry with a fictional vehicle, article search/reader/back navigation, an illustrative $20 USD quote and persistent sample-content labeling; load no live application/auth/commerce modules in demo mode.
- [ ] Keep demo purchase/sign-in/library mutations disabled and make zero catalog, auth, commerce, preparation, ingestion or model requests; preserve paid routes, grants and production authentication.
- [ ] Update Inception model defaults to mercury-3 and make its request temperature/token fields compatible while retaining explicit INCEPTION_MODEL overrides and historical Mercury-2 metadata.
- [ ] Run focused client/Go/Python regressions and browser verification proving demo navigation and no live API requests; record exact candidate evidence, commit/push coherent milestones and synchronize Issue186/Project8.

- [ ] Securely deliver the validated current model key outside the repository, recover the verified purchase-disabled preview runtime after its restart loss, resume only the two frozen parked jobs with existing fences/budgets, and record canonical/warm-read acceptance or the exact blocker without claiming paid launch.

## Operational completion: existing preview and exactly two jobs

The coordinator verified the current local key by a tiny official Mercury-3 JSON completion (HTTP200, model mercury-3, one choice), fingerprint `07f40f8fd62b`. This is authentication/API compatibility evidence, not canonical acceptance. Deliver that validated key by private file/secure environment update only: no value in Git, chat, logs, CLI argv or GitHub. Use private0700 evidence/config directories and0600 files. Preserve all unrelated environment keys; inject `INCEPTION_MODEL=mercury-3`. Verify only fingerprint/presence, never dump environment. The demo remains static and completely independent of commerce readiness.

Freshly inspect database `autodata` at `127.0.0.1:5432`, S3 at `127.0.0.1:19000`, existing systemd API and retained private launch/inspect/source evidence. Prior preview `autodata-ingestion-preview-auto-park` no longer exists after host restart; never assume it survives. Prior source is `fc7a73ad9002bd04f821b767d0a70bdbbdfc1dca`, image `sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4`. Recover only the same preview role using inspected immutable source at the coordinator-reviewed new implementation SHA and existing image; preserve command, network, read-only/capability/security/user/resource configuration from the retained launch evidence. Preserve rollback inputs and current data; persist the existing service/restart configuration rather than another reboot. Inspect before writes; any mismatched/missing baseline input blocks recovery, and is reported without guessing runtime settings. Reuse existing exact API build/launch process for the new embedded demo assets. Do not modify source connectors, schema, payment configuration or customer grants.

Resume only:

| Bank | Canonical article | Job |
| --- | --- | --- |
| Bankone | `aad66f67-355c-5d92-ab21-b4894bca9069` | `a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d` |
| Banktwo | `8ae431dd-69b2-5f27-a696-6d64b0ff0a81` | `64888ce4-429e-4e22-9892-48d1fb4b82eb` |

Use existing `run_article_worker_once(..., job_id=exact_uuid)` with existing claim/source-generation/profile fences, as in `docs/superpowers/plans/2026-11-06-preview-automatic-rewrite-deployment.md`. Verify each current job belongs to its frozen article/source scope before invocation. Retain retry counts and model-attempt history; maximum2 model attempts/article and4 total, with no budget reset, generic worker/daemon/queue drain, new enrollment or manual retry after model/auth/integrity failure. Keep a private database backup and unchanged unrelated business/queue/source fingerprints. If either exact job is stale/missing or required services are unavailable, stop that operational step and report the exact blocker; static demo verification can still complete independently.

Require persisted automatic canonical revision with `full-prose-auto-v1`, truthful `UNREVIEWED` metadata, protected technical/table/safety/media/evidence/order retention and no manual approval row. For each published article perform ten warm reads/ensures with actual measured zero source/media/model/schedule calls and unchanged revision/content hashes; fresh-process persistence read is mandatory. A generation failure remains explicit and cannot be represented as publication. Mechanical integrity does not certify semantic equivalence. The licensed two-job canary is private operational verification and is never exposed in fixture demo content.

Verify local/public readiness200, the normal Workshop, `/workshop/?demo=1` and `purchase-config` `enabled:false` after recovery;503 is a failure, not disabled-purchase success. Keep all checkout disabled and grant/customer data unchanged. Record source/image/container/service IDs, full candidate SHA, fingerprint only, per-job attempt/model counters/revisions, measured warm-call counts and rollback evidence privately; synchronize sanitized results to the canonical doc/Issue/Project. Production paid launch, unrestricted source access, new grants and broad catalog acceptance remain outside this scope.

Fresh coordinator observation before checkpoint: `autodata-postgres-1` maps `127.0.0.1:5432`; both frozen jobs survive with `status=failed`, `phase=rewriting`, `error_code=MODEL_NOT_CONFIGURED`. No resume performed. S3 endpoint identity still requires fresh runtime verification.
