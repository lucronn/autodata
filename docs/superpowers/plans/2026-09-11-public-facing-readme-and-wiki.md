# Public-Facing README and Wiki Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh AutoData’s public repository entry point and publish a small, navigable GitHub Wiki without creating a second source of truth for technical documentation.

**Architecture:** Keep the root `README.md` as the concise public landing page, with one local visual asset and links to canonical repository documentation. Store the wiki page sources under `docs/wiki/`; each page explains the product or points to the authoritative architecture and development documents under `docs/`, then the same page files are published to the GitHub Wiki repository. Record the public-facing documentation contract in `docs/github/operating-model.md` and `docs/public-facing/README-and-wiki.md`.

**Tech Stack:** Markdown, a repository-local raster hero asset, GitHub CLI for Issue and Project synchronization, and the GitHub Wiki Git repository for publication.

**Spec:** `docs/superpowers/specs/2026-09-01-autodata-platform-design.md`

## Global Constraints

- Normative technical content remains under `docs/`; the GitHub Project is an index and the Wiki is a navigational/public-facing projection.
- The README contains one local visual asset and no redundant remote repository-image embed.
- Public-facing copy must describe the current deterministic local path accurately, sell the problem/solution clearly, and label generated automotive content as unreviewed until human review.
- Wiki pages must not contain credentials, private source payloads, or instructions that imply production readiness beyond the verified local path.
- Preserve the user-owned untracked `sample data/` directory and do not stage it.
- GitHub mutations are limited to the dedicated documentation Issue, its Project #8 item, and publication of the requested README/wiki change; no unrelated issues, projects, or pull requests are changed.

## Gate synchronization record

- **GitHub Issue:** [#88 — Refresh the public README and publish a navigable Wiki](https://github.com/lucronn/autodata/issues/88)
- **GitHub Project:** [Project #8 — AutoData Portfolio](https://github.com/users/lucronn/projects/8)
- **Repository record:** `docs/agents/records/2026-09-11-public-facing-readme-and-wiki.json`
- **Synchronized status:** `synchronized` at the preflight boundary; implementation remains `in progress` until the GitHub Wiki is initialized and published.
- **Planning checkpoint:** `94e69d60b4ca6739025a75ee07d641ed9134f005`
- **Work items:** refresh the README opening and remove the redundant remote image; replace the rough visual with an inspected local asset; publish four Wiki projection pages sourced from `docs/`; verify documentation hygiene and synchronize the final SHA in GitHub.

### Synchronized todo

- Remove the redundant remote image embed and tighten the README opening.
- Replace the rough visual with an inspected local asset.
- Publish four Wiki projection pages sourced from `docs/`.
- Verify documentation hygiene and synchronize the final SHA in GitHub.

## Files and publication targets

- Modify: `README.md` — public landing page, navigation, current-status framing, and single visual reference.
- Create: `docs/assets/autodata-platform-overview.png` — replacement public-facing visual.
- Delete: `docs/assets/autodata-architecture-preview.jpeg` — obsolete rough visual after all references are removed.
- Create: `docs/public-facing/README-and-wiki.md` — canonical editorial/source-of-truth note for public-facing documentation.
- Create: `docs/wiki/Home.md` — wiki landing page and navigation.
- Create: `docs/wiki/Architecture.md` — architecture map linking canonical docs.
- Create: `docs/wiki/Getting-Started.md` — deterministic local setup and verification links.
- Create: `docs/wiki/Contributing.md` — contribution, documentation, and planning-gate expectations.
- Create: `docs/agents/records/2026-09-11-public-facing-readme-and-wiki.json` — machine-checked synchronized pre-implementation record.
- Modify: `docs/github/operating-model.md` — document the README/Wiki publication boundary and canonical source rule.
- Publish: the four `docs/wiki/*.md` files to the `lucronn/autodata.wiki` repository with GitHub Wiki-compatible names.

### Task 1: Establish synchronized tracking and canonical public-facing documentation policy

**Files:**
- Modify: `docs/superpowers/plans/2026-09-11-public-facing-readme-and-wiki.md`
- Modify: `docs/github/operating-model.md`
- Create: `docs/public-facing/README-and-wiki.md`

**Interfaces:**
- Consumes: the existing repository operating model and pre-implementation gate.
- Produces: a synchronized Issue/Project/documentation record that names the public-facing deliverables and states that `docs/` is authoritative.

- [x] Create or identify the dedicated GitHub Issue for the README, visual, and Wiki refresh, then add or identify its item in Project #8.
- [x] Add the exact Issue URL, Project URL, concrete work items, and synchronized status to this plan, `docs/public-facing/README-and-wiki.md`, and `docs/github/operating-model.md`.
- [x] Commit the plan and canonical-document checkpoint, verify the staged path list excludes `sample data/`, and record the checkpoint SHA.
- [x] Run the repository preflight against that exact checkpoint SHA; stop if the record is missing, stale, malformed, or unsynchronized.

### Task 2: Replace the rough visual and refresh the README entry point

**Files:**
- Modify: `README.md`
- Create: `docs/assets/autodata-platform-overview.png`
- Delete: `docs/assets/autodata-architecture-preview.jpeg`

**Interfaces:**
- Consumes: the canonical architecture, lifecycle, infrastructure, and current development-slice documentation.
- Produces: one readable local hero image, a concise public opening, stable navigation to the Wiki and canonical docs, and accurate local verification guidance.

- [x] Generate a polished wide visual for the repository front page: a clear problem-to-solution story with readable marketing labels, a vehicle-specific workspace, procedure/quote/evidence outcomes, no invented product claims, and no watermark.
- [x] Inspect the generated image, copy it to `docs/assets/autodata-platform-overview.png`, and confirm its dimensions and format.
- [x] Remove the remote `repository-images.githubusercontent.com` embed and the obsolete JPEG reference from `README.md`; place the replacement image once near the title.
- [x] Add a short navigation row for the Wiki, architecture docs, local setup, current slice, and Project #8; preserve the existing detailed commands below it while tightening inaccurate or duplicate opening prose.
- [x] Search the repository for references to the deleted JPEG and confirm no README or asset reference remains.

### Task 3: Author and publish the GitHub Wiki projection

**Files:**
- Create: `docs/wiki/Home.md`
- Create: `docs/wiki/Architecture.md`
- Create: `docs/wiki/Getting-Started.md`
- Create: `docs/wiki/Contributing.md`
- Publish: `lucronn/autodata.wiki` pages `Home.md`, `Architecture.md`, `Getting-Started.md`, and `Contributing.md`

**Interfaces:**
- Consumes: canonical repository documents and the refreshed README.
- Produces: a four-page Wiki with relative navigation, explicit source-of-truth links, and no duplicated private or unverified content.

- [x] Write `Home.md` with the product summary, current status boundary, navigation links, and a clear statement that repository `docs/` remains authoritative.
- [x] Write `Architecture.md` as a concise map to the domain model, fast/deep lifecycle, contracts, infrastructure, and the single replacement visual.
- [x] Write `Getting-Started.md` with the deterministic Compose path, dashboard URL, smoke-test intent, and links back to the full development guide.
- [x] Write `Contributing.md` with the operating model, Issue/Project workflow, documentation source rule, pre-implementation gate, and secret-handling boundary.
- [ ] Clone or initialize the GitHub Wiki repository only after confirming the target repository and authenticated identity; publish only the four requested pages. Blocked until GitHub's first Wiki page is saved in the web UI.
- [ ] Verify that each published page is readable from the Wiki remote and that every repository-relative link resolves from the corresponding Wiki context or uses an absolute repository URL. Pending remote initialization.

### Task 4: Verify the public-facing delivery and synchronize GitHub state

**Files:**
- Modify: `docs/public-facing/README-and-wiki.md`
- Modify: `docs/github/operating-model.md`
- Modify: `docs/superpowers/plans/2026-09-11-public-facing-readme-and-wiki.md`

**Interfaces:**
- Consumes: the completed README, asset, canonical source pages, and published Wiki.
- Produces: exact-SHA local evidence and synchronized GitHub Issue/Project status.

- [x] Run `git diff --check`, Markdown fence/link/reference scans, secret-marker scans, the repository-governance tests, and the applicable documentation checks.
- [x] Inspect the rendered README and replacement image, confirming the title, navigation, image count, local setup commands, and review-status disclaimer are all visible and accurate.
- [x] Re-read the GitHub Issue and Project #8 item, update their status and exact commit/source references, and preserve the repository-docs-as-authority statement. Final evidence comment remains to be added with the current head.
- [x] Commit only the requested README, asset, canonical docs, plan, and Wiki source paths; inspect `git diff --cached --name-only` before committing.
- [x] Push the requested repository branch, verify the local SHA matches the remote SHA, and record the Wiki initialization blocker; remote Wiki page read-back remains pending.

## Expected outcome

The GitHub repository has a clear public front page with one intentional visual, the obsolete rough visual and redundant remote embed are gone, and the Wiki source provides a useful first-time path through AutoData while linking back to canonical repository documentation. Remote Wiki publication remains the single blocked follow-up until GitHub's first page is initialized.
