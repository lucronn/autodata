# AutoData Public-Facing Documentation Record

## Purpose

This document defines the public-facing documentation boundary for the AutoData
repository. The root README is the concise landing page. The GitHub Wiki is a
small navigation and onboarding layer. Normative architecture, lifecycle,
contract, infrastructure, governance, and agent-policy content remains in the
repository `docs/` tree at the exact verified commit.

## Synchronized delivery record

- **Goal:** Refresh AutoData's public repository entry point and publish a small, navigable GitHub Wiki without creating a second source of truth for technical documentation.
- **GitHub Issue:** [#88 — Refresh the public README and publish a navigable Wiki](https://github.com/lucronn/autodata/issues/88)
- **GitHub Project:** [Project #8 — AutoData Portfolio](https://github.com/users/lucronn/projects/8)
- **Plan:** [`docs/superpowers/plans/2026-09-11-public-facing-readme-and-wiki.md`](../superpowers/plans/2026-09-11-public-facing-readme-and-wiki.md)
- **Machine record:** [`docs/agents/records/2026-09-11-public-facing-readme-and-wiki.json`](../agents/records/2026-09-11-public-facing-readme-and-wiki.json)
- **Status:** `complete`: the refreshed README and canonical documentation are merged into protected `master` by [PR #94](https://github.com/lucronn/autodata/pull/94). The visual explains the customer problem and solution; all four Wiki pages are published and read back.

## Implementation evidence

- **README and asset commit:** `3dcef0511ea4bd15ecc30923131c6981f575d44d`
- **Repository-facing verification:** PR #94 merged the synchronized implementation tree into `master` at `defec080f925e97ce3bd9b785579817c572d5807`. Required verification run [35004339067](https://github.com/lucronn/autodata/actions/runs/35004339067) passed on PR head `322441414c9e2792c56e7d88ef1b0463873b73fb`; `master` was read back with the refreshed README and Quay-pinned Compose image.
- **Local repository checks:** repository governance `6 passed`; pre-implementation validator `7 passed`; Markdown fence, local-link, secret, and redundant-image checks passed; replacement image inspected at `1942 x 809` PNG.
- **GitHub repository branch:** `automation/knowledge-fallback-runtime` delivered the refreshed README, canonical documentation, consumer readiness fixes, and Compose CI image correction through merged PR #94. Protected `master` is the current delivery branch.
- **Wiki status:** GitHub Wiki is initialized and the four requested pages are published and read back: [Home](https://github.com/lucronn/autodata/wiki), [Architecture](https://github.com/lucronn/autodata/wiki/Architecture), [Getting Started](https://github.com/lucronn/autodata/wiki/Getting-Started), and [Contributing](https://github.com/lucronn/autodata/wiki/Contributing).
- **Visual message:** scattered repair data becomes one vehicle-specific workspace that produces a procedure, labor-and-parts quote, source evidence, and review status.

## Concrete work items

1. Remove the redundant remote repository-image embed and tighten the README's public opening while preserving accurate local setup guidance.
2. Replace the rough architecture preview with one inspected, readable local visual that makes no unverified claims.
3. Author and publish `Home`, `Architecture`, `Getting Started`, and `Contributing` Wiki pages from the repository's canonical documentation boundary. All four pages are now published and linked back to canonical sources.
4. Verify Markdown hygiene, links, image references, secret handling, exact commit state, and synchronized Issue/Project records.

## Source map

| Public surface | Canonical source or contract |
| --- | --- |
| README product summary and repository map | `README.md`, supported by `docs/architecture/` |
| Wiki architecture page | `docs/architecture/domain-model.md`, `docs/architecture/dataset-lifecycle.md`, `docs/architecture/contracts.md`, and `docs/architecture/infrastructure-and-dev.md` |
| Wiki getting-started page | `docs/architecture/infrastructure-and-dev.md` and the verified commands in `README.md` |
| Wiki contributing page | `docs/github/operating-model.md`, `docs/agents/pre-implementation-gate.md`, and repository contribution templates |
| Current development status | The linked Issue/Project records and the exact verified repository commit |

The Wiki is published from `docs/wiki/` and must not receive private source
payloads, credentials, or claims that exceed the verified local runtime. A
generated procedure or source-derived result remains explicitly unreviewed
until an authorized human review changes its status. The README and canonical
repository changes are now on protected `master`; the Wiki remains its
public-facing projection.
