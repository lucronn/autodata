# Contributing to AutoData

AutoData is developed through the public repository and GitHub Project #8. The
Project tracks outcomes, dependencies, risk, and release status. Normative
technical decisions remain in the canonical documents under `docs/`; do not
create a second design or infrastructure-document tree.

## Before changing code

1. Find or create the GitHub issue describing the measurable outcome.
2. Add the issue to Project #8 and set its Area, Priority, Risk, Target release,
   and Source or dependency reference fields.
3. Confirm the affected bounded context and contract in the relevant document.
4. Keep the supplied `sample data/` directory local-only unless redistribution
   rights have been explicitly approved. Never commit source payloads,
   credentials, tokens, or production identifiers.

## Branches and pull requests

Create a short-lived branch from `master` using the `automation/<topic>` naming
convention. The protected `master` branch is the only release line. Use a
small pull request, link it to the issue, and use squash merging. Do not force
push or create parallel long-lived development branches.

The pull-request template is the delivery checklist. In particular, describe
API/event/schema/entitlement impact, preserve provenance and evidence for every
published fact, and state idempotency, retry, and dead-letter behavior for
asynchronous work. Explain any infrastructure check that could not run rather
than reporting it as passed.

## Verification

Run the checks relevant to the change. The baseline commands are:

```sh
(cd apps/api-go && go test ./...)
(cd packages/contracts/go && go test ./...)
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v
python3 -m unittest discover -s scripts/contracts -p 'test_*.py' -v
python3 -m unittest discover -s scripts/dev -p 'test_*.py' -v
```

Changes to workers, contracts, migrations, infrastructure, source adapters,
or publication behavior require the corresponding integration or Compose
verification described in `docs/architecture/infrastructure-and-dev.md` and
the workflow. Local credentials are deterministic development values only;
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

Put normative Markdown, architecture decisions, operations guidance, and
runbooks under `docs/`. Update the relevant Project #8 item in the same release
flow and include the verified commit or release reference. Releases are tagged
from `master` and must summarize schema, API, worker, data-contract, and
operational changes where applicable.
