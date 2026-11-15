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
