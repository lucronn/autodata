# Selector UI API rollout operator preparation

Goal: Prepare and review a bounded API-only selector UI rollout operator that preserves the now-active catalog consumer; no runtime mutation or deployment.

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8.

Reviewed UI head `35cac9f65a8604f3ac3962417fa2d5b2757b772c`; isolated docs-only branch `codex/selector-ui-rollout-preparation`. Existing UI agent worktree and implementation stay untouched. This gate authorizes only private operator/test/release-note preparation under `/home/corp/autodata-evidence/selector-ui-release-draft`; create separate v2 files and preserve previous draft.

## Concrete todo

- [ ] Prepare a separate private API-only operator/test copy preserving exact active ingestion, article and catalog container identities/payloads and worker services through success and rollback.
- [ ] Scope exact-repository Git safe.directory only for Git and pinned validator subprocesses; require isolated root interpreter and vetted command PATH without global Git configuration.
- [ ] Bind root-sealed source/binary/manifest/script under root-owned ancestry, plus exact merged-source Node selector test receipt and post-switch served-byte equality; preserve honest live-canary limits.
- [ ] Run meaningful mocked root Git/environment, catalog identity/service and interrupt rollback regressions; independently review final script/test hashes before a separate merged-product release checkpoint and fresh coordinator dispatch.

## Exact implementation decision

Keep the existing API-only drop-in swap, exact merged PR367/source/tree/reviewed apps/api-go blobs/required CI/checkpoint binding, root-sealed source inventory and binary hashes, no migrations/worker restart/commerce change, bounded BaseException rollback and honest live completed-empty/timeout unavailable assertions. Add sealed manifest fields for exact active article and catalog IDs in addition to ingestion ID; inspect all three by full ID, canonical-sort complete Mounts, and require article+catalog services active. Compare the exact frozen projections and schema ledger after switch/canaries and recovery. No process counters/timestamps in equality.

Use vetted PATH /usr/bin:/bin:/home/corp/go-sdk/bin only if Node is elsewhere explicitly bind an absolute executable. Require sys.flags.isolated under root. Every subprocess gets a sanitized environment retaining only PATH, necessary GitHub auth/config fields supplied by the coordinator, and LANG/LC_ALL; only Git and preflight subprocesses get GIT_CONFIG_COUNT=1/KEY_0=safe.directory/VALUE_0=exact repo. No global/system or wildcard safe.directory. Do not print secret values. Gate must exercise pinned preflight in isolated root against this corp-owned checkout.

Final dispatch script/manifest/source/binary must reside under root-owned non-writable ancestry such as /var/lib/autodata-release; /home/corp ancestry cannot pass sealed(). Require separate root-sealed exact-product Node selector test receipt with status passed, product/source tree, source asset hashes, command/exit code and receipt hash in manifest. Verify receipt before mutation. Then post-switch compare served app.mjs/bootstrap.mjs bytes to those exact tested merged-source files. This is tested-source+served-byte identity evidence, not a live browser timeout/completed-empty claim. Coordinator accepts documented unavailable live-canary limits before dispatch.

Tests cover all three full IDs/order-independent mounts, catalog down/changed identity rejection, scoped root Git trust/restoration/no leakage into non-Git children, missing/wrong test evidence rejection, successful API-only retention and KeyboardInterrupt/SystemExit/signal/health/canary failure rollback without worker mutation. Final product binding and actual API restart require a new synchronized release checkpoint after merge plus independent review/fresh coordinator dispatch. No runtime operation is authorized here.
