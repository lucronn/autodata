# Contributing

AutoData uses short-lived branches, small Issue-linked changes, protected
`master`, and a single [AutoData Portfolio Project](https://github.com/users/lucronn/projects/8).

## Before implementation

Every implementation change follows the
[pre-implementation planning and tracking gate](https://github.com/lucronn/autodata/blob/master/docs/agents/pre-implementation-gate.md):

1. Write a decision-complete plan under `docs/superpowers/plans/`.
2. Create or identify the GitHub Issue and its Project #8 item.
3. Synchronize the Issue, Project item, and canonical repository documents.
4. Record a machine-checked `status: synchronized` record pinned to the base
   SHA.
5. Run preflight and implement only after it passes.

The Project is an index, not a competing technical source of truth. Normative
documents stay under `docs/`, and the public-facing README/Wiki policy is
defined in the [GitHub operating model](https://github.com/lucronn/autodata/blob/master/docs/github/operating-model.md)
and [public-facing documentation record](https://github.com/lucronn/autodata/blob/master/docs/public-facing/README-and-wiki.md).

## Documentation and source safety

- Keep technical truth in canonical `docs/` files and update the linked Issue or
  Project item in the same release flow.
- Wiki pages are published from `docs/wiki/` and should summarize or navigate;
  they must not silently replace repository contracts.
- Preserve provenance, evidence, review status, and source-rights boundaries.
- Never commit credentials, private source payloads, deployment diagnostics, or
  restricted sample data.
- Keep generated automotive procedures explicitly `UNREVIEWED` until human
  review authorizes a status change.

See the repository [operating model](https://github.com/lucronn/autodata/blob/master/docs/github/operating-model.md),
[agent contracts](https://github.com/lucronn/autodata/blob/master/docs/agents/agent-contracts.md),
and [data-integrity gates](https://github.com/lucronn/autodata/blob/master/docs/agents/data-integrity-gates.md)
for the full delivery and quality rules.
