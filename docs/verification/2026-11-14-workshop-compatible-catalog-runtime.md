# Compatible catalog runtime verification

Goal: Deploy a compatible, exact-source catalog ingestion runtime on loopback3031 so real Workshop selectors persist truthful dual-bank completion, preserving article/commerce behavior and disabled purchasing.

Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8; plan docs/superpowers/plans/2026-11-14-workshop-compatible-catalog-runtime.md; record docs/agents/records/2026-11-14-workshop-compatible-catalog-runtime.json.

Status: planning only, before candidate/source/test-resource changes. Serving writable runtime7ce6c5a98bec is healthy and purchase disabled; original retained. Schema migration042 and required selector columns were read independently. Prior public2024makes remains partial because old ingestion never writes the new completion contract.

Concrete todo:

- [ ] Freeze current writable serving runtime and DB schema42 evidence; stage an immutable original-source copy with only two exact merged catalog modules replaced and audit complete source hashes.
- [ ] Run offline runtime-image catalog/connector/deepening tests and isolated PostgreSQL sparse-selector persistence/upgrade tests without serving credentials or provider access.
- [ ] Prepare a private backup/protected baseline and exact retained-runtime rollout/rollback manifest; coordinator alone replaces source mount after complete Config/HostConfig/image comparison.
- [ ] Verify runtime health/writes/protected state and one bounded real2024US selector observation through public API; record truthful partial state or completion and remaining article/paid-access gaps.

## Failed minimal-overlay acceptance and full-source boundary

Initial immutable1181-file overlay changed exactly two modules; manifestSHA256830eb53e70a2555c0a52b4b3de7a8e5fd2a0292bc3cdba90a1787288d2959c8a. Runtime-image unittest eventually passed65 with test-only pytest imports and explicit application-env scrubbing. Earlier attempts exposed missing pytest/test imports and inappropriate SOURCE_PERSIST=0 test semantics, then corrected harness only. IsolatedPG selected pytest:106passed,6failed,3errors,42subtests. Actual old-interface failures: missing store rewrite_profile_version and private HTTP expected_mode/demo-mode; environment failures: MinIOfixture absent and Go cache read-only. No merged production module was edited to fit tests. This candidate is not deployable.

Coordinator dispatched a superseding full exact61f1939 source gate. pyproject/contracts unchanged,17 ingestion source paths changed, only DB042 difference already installed. Full-source build and expanded complete internal fixture stack await amended committed-base preflight. Serving writable runtime remains untouched by this worker and purchase remains disabled.

## Exact full-source candidate acceptance and startup block

Full-source amendment78dcc391d5d720e427a3fba9d53a51e81856f0c3 passed preflight; Issue401comment6886601086 and Project8 readbacks matched before generation. Immutable complete61f1939c04b41cf6082c3361f34424e0cd9c599e source staged at /home/corp/autodata-candidate/full-ingestion-61f1939-20261114/source,1337files. git archive SHA256dfff73871d15a274cbc80fa2eb4adaa6438ed269885d1a5b4faf3c992f33b57e; manifestSHA256023cb3c36d37dda115dc49b00684e1138a64e5a8353e8e5d5570c9091a664981. No application edits.

Complete internal PG/SeaweedFS/NATS selected catalog/connector/deepening/HTTP suite passed115tests/42subtests, including real sparse-selector persistence/version upgrade and Go contract. First full fixture run had artifact-directory write permission failures; writable synthetic artifacts fixed harness only, after which acceptance passed. Runtime-image network-none unittest had65passes for prior overlay; no external connector/payment/model request occurred.

An actual-runtime isolated startup composition check with the current nonsecret settings stripe_test/production/https://autodata.cars.tk reproduced COMMERCE_CONFIGURATION_INVALID503 before DB/payment work. run_server calls configured_commerce before binding, so this exact-source/same-env candidate MUST NOT activate. Disabled mode would remove existing library/grant authority. Coordinator assigned separate Python Issue414/PR417 for explicit private read_only, paired with GoPR412, preserving configured entitlement pins and protected reads without Stripe startup. A new merged-source gate must explicitly pin the reviewed merged source plus private read_only env delta, after public API identity/mode confirmation. This full-source candidate remains retained test evidence, not a deployable release.
