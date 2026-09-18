# Minimal Vehicle Selector Dashboard Contract

## Purpose

The local AutoData dashboard begins with a simple vehicle selection flow. It is
not the repair chatbot itself and it does not duplicate the vehicle catalog.
Its job is to make the vehicle context obvious before the user continues to a
repair request.

Tracked delivery: [Issue #105](https://github.com/lucronn/autodata/issues/105)
and [Project #8](https://github.com/users/lucronn/projects/8). The synchronized
implementation plan is
[`2026-09-18-minimal-vehicle-selector-dashboard.md`](../superpowers/plans/2026-09-18-minimal-vehicle-selector-dashboard.md).

## Required flow

1. Load selector data from the same-origin `GET /vehicle-identities/selectors`
   endpoint using the existing local authentication boundary.
2. Render every available decade at once. A decade label is derived from the
   available numeric years, for example `1990s` for years 1990 through 1999.
3. Clicking a decade reveals only the available years in that decade.
4. Clicking a year filters the returned canonical vehicle records to that year
   and renders the available makes grouped by their first letter.
5. Clicking a letter reveals the complete matching make list.
6. Clicking a make displays the selected year and make and enables the next
   repair-query action. The selected context is browser state only until a
   later repair request persists or resolves a complete configuration.

## Data contract

The dashboard consumes the existing response shape:

```json
{
  "years": [1997, 1999, 2024],
  "vehicles": [
    {"year": 1997, "make": "Toyota", "model": "RAV4"},
    {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500"}
  ]
}
```

The UI must tolerate an empty `years` or `vehicles` list, malformed records,
and a failed request. It must not invent years or makes. Make grouping is
case-insensitive, output is alphabetized, and duplicate make names collapse
within a selected year.

## Presentation contract

- One centered column with a restrained heading and short instructions.
- Buttons are semantic controls, not clickable text or decorative links.
- Selected controls have a visible state and keyboard focus is always visible.
- Lists wrap naturally on narrow screens without horizontal scrolling.
- Spacing uses a small consistent scale; no dashboard panels, terminal, answer
  cards, gradients, animation, or dense technical metadata are required for
  this first selector screen.
- Loading, no-data, and error messages explain what the user can do next.

## Boundaries

The dashboard does not change vehicle identity normalization, persistence,
repair-query APIs, worker behavior, or provider mappings. It does not create a
second source of truth for vehicle data. The Go route remains `/dashboard/`,
and assets remain embedded under `apps/api-go/dashboard/`.

## Verification contract

Before delivery, verify the route contract with Go tests and JavaScript syntax
checks. In the local browser, confirm the transitions decade → year → letter →
make and confirm that the selected context is visible after the make click.
Record the exact commit, remote branch, and CI result here after verification.

## Verified delivery

- Commit: `8914194544afe62f5ab9b2866312fd89e4dbf476` on
  `phobos/fix-chat-source-failure`.
- Local verification passed: `go test ./...` from `apps/api-go`, `node --check
  apps/api-go/dashboard/app.js`, and `git diff --check`.
- Browser verification passed against the rebuilt local stack at
  `http://127.0.0.1:8080/dashboard/`: 1990s → 1999 → F → Ford → selected
  `1999 Ford`.
- GitHub verification passed in [Autonomous Verification
  35382320679](https://github.com/lucronn/autodata/actions/runs/35382320679).
