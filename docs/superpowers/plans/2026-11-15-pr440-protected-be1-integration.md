# PR440 protected-be1 helper integration

Goal: Refresh draft PR440 helper-only integration onto protected be1a1f23, preserve the eight independently reviewed implementation blobs and distinguish historical inconclusive evidence from current execution authority

Issue: https://github.com/lucronn/autodata/issues/401
Project: https://github.com/users/lucronn/projects/8
Protected base: `be1a1f235e8eeacc051ac905c4ed8a953a41c8a9`; reviewed old PR head: `0212dd8d708d3acb522f520f25800b24fa2d60cc`.

## Todo

- Synchronize Issue401/Project8, corrected canonical current-versus-historical docs and matching records at a docs-only protected-base checkpoint; pass exact checkpoint preflight before copying helper files
- Copy the exact four helper and four test blobs from reviewed0212dd8d, run focused owned/offline tests and verify all eight Git blob IDs unchanged
- Push the refreshed draft PR440 with an exact old-head lease, update its base/head verification text and run required exact-head CI; hold merge, build, activation, runtime and provider requests for root

## Exact implementation allowlist

- `scripts/dev/archive_configuration_probe_baselines.py` — Git blob `2dc7ff45c76688d4a516d42e0aec210ca9825f91`
- `scripts/dev/configuration_probe_observe.py` — Git blob `66ccf9ba8777f639c020dacacbbf59d225424145`
- `scripts/dev/configuration_probe_runtime.py` — Git blob `c1d38c129f1759b9d1f9bebfe409434ad961fadd`
- `scripts/dev/configuration_probe_watchdog.py` — Git blob `63b0b56aaa9db4bb4ee8064a2a989a82154a14b1`
- `scripts/dev/tests/test_archive_configuration_probe_baselines.py` — Git blob `aed46a4a6f685811bd08db3f4b8c03539e18bdcd`
- `scripts/dev/tests/test_configuration_probe_observe.py` — Git blob `3decb917c4a149d746c300b6117e24823ad68d3d`
- `scripts/dev/tests/test_configuration_probe_runtime.py` — Git blob `c8f19e95da89166b29dce01cc7722cc9e46b7e66`
- `scripts/dev/tests/test_configuration_probe_watchdog.py` — Git blob `22877a3ba12e1f98b4e78af56351ea0b6ff56ef8`

No implementation content change is authorized. Documentation allowlist is the existing eleven PR440 docs plus this integration plan/record. Preserve the original configuration GET/manual inconclusive evidence; no claim of current runtime or provider success. No build/service/provider or protected-data actions. Worktree and Git metadata are offloaded ext4; stop on any allocation conflict with preview lane. Test temporary files/cache must stay on offloaded ext4 or tmpfs, never the auth-probe caches under archival seal.

## Ordered verification and rollback

Commit/push docs-only checkpoint, pass machine preflight at that exact SHA, then copy exact reviewed blobs and compare all eight IDs. Run four focused unittest modules with bytecode disabled and private offloaded TMPDIR; do not invoke helper CLI mutation or Docker fixtures. Parse records and run diffcheck; update draft body and strict CI at final head. Push only with lease bound to old0212dd8d; refusal means stop and inspect remote. Keep draft/no merge. Historical old branch/commits and all evidence remain reachable; source-only rollback is a separately coordinated Git head update, never runtime rollback.
