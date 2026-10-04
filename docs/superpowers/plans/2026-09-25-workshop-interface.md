# AutoData workshop interface

Goal: add a separate, usable vehicle reference interface at `/workshop/`, with an old-web visual language and subtle modern typography and interaction.

Issue: https://github.com/lucronn/autodata/issues/113
Project: https://github.com/users/lucronn/projects/8
Canonical document: `docs/architecture/workshop-interface.md`

## Design

Palette: paper `#f8f9f5`, ink `#222c32`, blueprint `#234bd8`, rule `#c6cbc8`, quiet `#59645e`, selection `#edf0ff`.
Type: locally served Instrument Sans for display, controls, and text; a system monospace only for actual procedure numbers. Oversized, tightly spaced title, comfortable 16px body, restrained small supporting text.

Left-aligned layout:

```text
AutoData / workshop                          API docs
---------------------------------------------------
The workshop                  small rotating
reference.                    exploded-wheel drawing
Choose a vehicle. Find the instructions.
---------------------------------------------------
1 Year     2 Make     3 Model     4 Engine / trim
[select]   [select]   [select]    [select]
---------------------------------------------------
Vehicle + article count       [Search this catalog]
Article index                 Reader with back/print
```

The vehicle controls remain compact and native. The memorable element is the large reference-library masthead and schematic wheel, which turns only on interaction/loading. Article links are underlined; no card grid, chatbot, decorative badges, or marketing sections. The reader uses the same quiet paper and rules, with source-provided ordering and local images.

Design review: a generic dashboard would use multiple cards and status badges. This version instead uses a single working index, ordinary links/selects, and a small subject-specific mechanical drawing. Rules separate actual navigation and document sections, as requested by the old-school brief.

## Implementation contract

- Add standalone HTML/CSS/ES modules, embed and route at `/workshop/`, and include them in the API container. Preserve dashboard, root redirect, Swagger, and API contracts.
- Use `/v1/catalog` for every selector/list/article; reuse existing local authentication convention. No provider calls directly from the browser.
- Clear dependent choices immediately. Cancel obsolete requests, bound polling/timeouts, show real partial/loading/error/empty states, and support retry without phantom success.
- Search/filter actual article titles locally. Use API-returned IDs, never hardcoded sample IDs. Keep back navigation and reloadable article URLs.
- Preserve the returned step order and image associations; render untrusted text as text. Fall back to complete body text when legacy structured steps are empty. Do not manufacture missing illustrations or claim normalization quality was fixed.
- Accessible labels, visible focus, reduced motion, narrow-screen layout, and useful print layout.

## Todo

- [ ] Add the standalone workshop layout and route.
- [ ] Implement cancellable vehicle selection, catalog search, reader, and recovery states.
- [ ] Verify focused client behavior, Go routes, and live desktop/mobile flow; rebuild the local API.

## Acceptance

The local URL serves without authentication, while data reads retain existing authentication. A real year/make/model/configuration selection produces an actual catalog, search opens a matching article, and back/reload work. Stale requests cannot replace a new selection; hydration cannot spin forever. Desktop and mobile have no horizontal overflow. Existing API tests remain passing. Cached live verification is reported separately from deterministic incomplete/error coverage.
