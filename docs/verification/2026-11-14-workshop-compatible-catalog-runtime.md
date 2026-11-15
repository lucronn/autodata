# Compatible catalog runtime verification

Goal: Deploy a compatible, exact-source catalog ingestion runtime on loopback3031 so real Workshop selectors persist truthful dual-bank completion, preserving article/commerce behavior and disabled purchasing.

Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8; plan docs/superpowers/plans/2026-11-14-workshop-compatible-catalog-runtime.md; record docs/agents/records/2026-11-14-workshop-compatible-catalog-runtime.json.

Status: planning only, before candidate/source/test-resource changes. Serving writable runtime7ce6c5a98bec is healthy and purchase disabled; original retained. Schema migration042 and required selector columns were read independently. Prior public2024makes remains partial because old ingestion never writes the new completion contract.

Concrete todo:

- [ ] Freeze current writable serving runtime and DB schema42 evidence; stage an immutable original-source copy with only two exact merged catalog modules replaced and audit complete source hashes.
- [ ] Run offline runtime-image catalog/connector/deepening tests and isolated PostgreSQL sparse-selector persistence/upgrade tests without serving credentials or provider access.
- [ ] Prepare a private backup/protected baseline and exact retained-runtime rollout/rollback manifest; coordinator alone replaces source mount after complete Config/HostConfig/image comparison.
- [ ] Verify runtime health/writes/protected state and one bounded real2024US selector observation through public API; record truthful partial state or completion and remaining article/paid-access gaps.
