# Contributing to AutoData

AutoData is developed on `master` through short pull requests. GitHub Project #8
tracks multi-step initiatives; routine fixes can use the pull request alone.
Keep durable technical decisions under `docs/` when they affect future work.

## Before changing code

1. Reproduce the user-visible problem on the existing stack and choose the
   smallest change that can make one path work.
2. Reuse an existing issue when one applies. Create a new issue or Project #8
   item only when coordination across several changes is actually needed.
3. Keep the supplied `sample data/` directory local-only unless redistribution
   rights have been explicitly approved. Never commit source payloads,
   credentials, tokens, or production identifiers.

## Branches and pull requests

Create a short-lived branch from `master` (for example, `automation/<topic>` or
`codex/<topic>`). The protected `master` branch is the release line. Use a small
pull request, link an existing issue if there is one, and prefer squash merging.

State the working outcome and focused verification in the pull request. For
payment, authentication, licensed data, schema, or production changes, include
the specific risk and rollback check. Preserve provenance for published facts;
describe idempotency, retry, and dead-letter behavior when asynchronous work
changes. Report missing test coverage plainly.

## Verification

Run focused checks relevant to the change. Examples:

```sh
(cd apps/api-go && go test ./...)
(cd packages/contracts/go && go test ./...)
python3 -m unittest discover -s scripts/contracts -p 'test_*.py' -v
```

Run the corresponding integration or Compose check before merging payment,
authentication, source-ingestion, migration, and production-deployment changes.
The extended GitHub workflow runs on `master` and can be dispatched before a
high-risk merge. Local credentials are deterministic development values only;
production or provider credentials belong in secret-managed environment
configuration.

## Data and safety rules

- Published facts require provenance; extracted facts require an evidence path.
- Published revisions are immutable. Corrections publish a new revision with a
  changelog and source watermark.
- Deep-lane failure must not revoke an already-viewable revision.
- Unknown or ambiguous source material is reviewable and must not be silently
  discarded.
- Security or privacy concerns use the private reporting path in `SECURITY.md`.

## Documentation and release tracking

Put durable architecture decisions and runbooks under `docs/`. Update Project #8
for initiatives it already tracks; do not create tracking work for a small fix.
Releases from `master` summarize material schema, API, worker, data-contract,
and operational changes.
