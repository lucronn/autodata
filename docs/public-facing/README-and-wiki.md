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
- **Status:** `synchronized` before implementation

## Concrete work items

1. Remove the redundant remote repository-image embed and tighten the README's public opening while preserving accurate local setup guidance.
2. Replace the rough architecture preview with one inspected, readable local visual that makes no unverified claims.
3. Author and publish `Home`, `Architecture`, `Getting Started`, and `Contributing` Wiki pages from the repository's canonical documentation boundary.
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
until an authorized human review changes its status.
