# AutoData GitHub Project Bootstrap

This is a future, parameterized provisioning guide. It is intentionally not executed by the architecture package. Replace the required variables only after the repository owner and target repository have been explicitly selected.

**FUTURE EXECUTION POLICY:** Every `gh` command in this document is a
future-execution step for a separately authorized provisioning run. The
commands are examples only while this document is being authored or reviewed;
they must not be run as part of the architecture/documentation package. In a
future run, execute the read-only discovery steps first, then make mutations
only after the returned IDs and existing-state checks have been reviewed.

## Parameters and prerequisites

```bash
# FUTURE EXECUTION VARIABLES — replace placeholders only in an authorized run.
export OWNER="OWNER"
export REPO="$OWNER/REPO"
export PROJECT_OWNER="OWNER"
export PROJECT_NUMBER="PROJECT_NUMBER"
export PROJECT_TITLE="AutoData Platform"
```

`OWNER` is the repository owner, `REPO` is the full `OWNER/REPO` name,
`PROJECT_OWNER` is the user or organization that owns the Project,
`PROJECT_NUMBER` is the existing or newly returned Project number, and
`PROJECT_TITLE` is the exact title to reconcile. `OWNER` and
`PROJECT_OWNER` may be the same account but are intentionally separate
parameters.

Required access:

- Authenticated GitHub CLI.
- Repository administration permission for repository settings and Actions configuration.
- Project permission for the selected project owner. The `gh project` manual identifies the `project` token scope as the minimum scope for Project operations; verify authentication before running a mutation.

Read-only discovery comes first. This is a **FUTURE EXECUTION — READ-ONLY**
step; it is not an instruction to run commands during documentation work:

```bash
# FUTURE EXECUTION ONLY — read-only authentication, repository, and Project discovery.
gh auth status
gh repo view "$REPO"
gh project list --owner "$PROJECT_OWNER" --format json --limit 100
```

The operator must select an existing project with the exact intended title or create one. Do not create a second project merely because a list command was truncated or a request was retried.

## Project creation and fields

Create the project only after discovery confirms that the title is not already
present. This is a **FUTURE EXECUTION — MUTATION** step:

```bash
# FUTURE EXECUTION ONLY — create only after the preceding discovery is reviewed.
gh project create \
  --owner "$PROJECT_OWNER" \
  --title "$PROJECT_TITLE" \
  --format json
```

Record the returned project number as `PROJECT_NUMBER`, then inspect the
built-in fields. This is a **FUTURE EXECUTION — READ-ONLY** step:

```bash
# FUTURE EXECUTION ONLY — inspect the returned Project and field IDs.
gh project view "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json
gh project field-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json --limit 100
```

Create only missing custom fields. The intended field set is:

```bash
# FUTURE EXECUTION ONLY — create only fields absent from the preceding field list.
gh project field-create "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" \
  --name "Priority" --data-type SINGLE_SELECT \
  --single-select-options "P0,P1,P2,P3"

gh project field-create "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" \
  --name "Area" --data-type SINGLE_SELECT \
  --single-select-options "Product,API,Data Model,Fast Lane,Deep Lane,Search,Billing,Dev Infra,Platform,Security"

gh project field-create "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" \
  --name "Data section" --data-type SINGLE_SELECT \
  --single-select-options "Vehicle,Powertrain,Diagnostics,Procedures,Specifications,Electrical,Inventory,Maintenance,Feedback"

gh project field-create "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" \
  --name "Risk" --data-type SINGLE_SELECT \
  --single-select-options "Low,Medium,High,Critical"

gh project field-create "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" \
  --name "Target release" --data-type DATE

gh project field-create "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" \
  --name "Source or dependency" --data-type TEXT
```

`Status` is the standard workflow field. Configure its values as `Backlog`, `Ready`, `In Progress`, `Blocked`, `Review`, `Done`, and `Canceled` through the Project configuration surface. Do not create a duplicate custom Status field.

The CLI supports field creation for `TEXT`, `SINGLE_SELECT`, `DATE`, and `NUMBER`. Project views are configured separately; the current `gh project` command list does not expose a `view-create` command. The desired view definitions are therefore recorded below for application through the supported GitHub Project UI/API path and subsequent verification.

## Views

| View | Layout | Filter/grouping intent |
| --- | --- | --- |
| Roadmap | Roadmap | Target release, Area, and major dataset milestones |
| Current Work | Board | Status columns, grouped by Area |
| Ingestion and Data Quality | Table | Area = Fast Lane/Deep Lane/Data Model; show Data section, Risk, Source/dependency |
| Platform and Developer Infrastructure | Table | Area = Dev Infra/Platform/Security; show Priority, Risk, Target release |
| Release Readiness | Table | Target release is current; show Status, Priority, Risk, linked PR |

Views should show linked issues and pull requests, preserve the standard Status field, and avoid duplicating acceptance criteria into custom fields.

## Labels

Create labels only after listing existing labels and reconciling names. This
is a **FUTURE EXECUTION — READ-ONLY** step:

```bash
# FUTURE EXECUTION ONLY — inspect existing labels before any later mutation.
gh label list --repo "$REPO" --limit 200
```

The canonical labels are:

```text
area:api
area:data-model
area:fast-lane
area:deep-lane
area:billing
area:dev-infra
area:platform
area:security
type:feature
type:bug
type:data-quality
type:source-ingestion
type:infrastructure
type:security
priority:p0
priority:p1
priority:p2
priority:p3
risk:high
risk:critical
```

Label colors and descriptions are an administrative presentation choice; names are the stable automation contract.

## Adding and updating project items

Add existing Issues or pull requests by URL only after listing the Project and
confirming that the URL is not already an item. This is a **FUTURE EXECUTION —
MUTATION** step:

```bash
# FUTURE EXECUTION ONLY — add one already-existing Issue or pull request.
gh project item-add "$PROJECT_NUMBER" \
  --owner "$PROJECT_OWNER" \
  --url "https://github.com/$REPO/issues/ISSUE_NUMBER" \
  --format json
```

Inspect the item before updating it. This is a **FUTURE EXECUTION — READ-ONLY**
step:

```bash
# FUTURE EXECUTION ONLY — discover the existing item and field values.
gh project item-list "$PROJECT_NUMBER" \
  --owner "$PROJECT_OWNER" \
  --format json \
  --field "Status" \
  --field "Priority" \
  --field "Area"
```

Update one project field at a time by issue/PR URL, using the exact field name
and single-select option. This is a **FUTURE EXECUTION — MUTATION** step:

```bash
# FUTURE EXECUTION ONLY — update after the preceding item/field discovery.
gh project item-edit "$PROJECT_NUMBER" \
  --owner "$PROJECT_OWNER" \
  --url "https://github.com/$REPO/issues/ISSUE_NUMBER" \
  --field "Priority" \
  --value "P1"
```

For automation, prefer stable project/item/field IDs obtained from JSON discovery rather than guessing names. The CLI also supports ID-based item editing. Never update or delete fields/items in parallel when a preceding command's returned ID or state is required.

For an implementation item, the `Source or dependency` text is the compact
tracking pointer: include the Issue/PR URL or number, canonical plan path,
exact pushed SHA or the literal `uncommitted`, current review state, relevant
test/CI evidence, and any source or infrastructure dependency. Keep the full
acceptance criteria in the Issue and repository plan; do not copy a second
technical specification into the Project item.

## Repository settings checklist

Configure through repository administration after the repository exists:

- Default branch: `master` for the current `lucronn/autodata` repository.
- Require pull request before merging.
- Require the CI checks listed in [operating-model.md](operating-model.md).
- Require CODEOWNERS review for owned paths.
- Require branch to be up to date before merge or use a merge queue.
- Allow squash merge; disable unnecessary merge strategies.
- Restrict force pushes and branch deletion on `master`.
- Configure `dev`, `staging`, and `production` environments with scoped secrets.
- Enable dependency/security update workflows after the repository manifests exist.
- Add issue forms, pull-request template, CODEOWNERS, security policy, and contributing guidance as repository-native files in the later scaffold phase.

## Verification and rollback

After any future provisioning run, verify the returned state. This is a
**FUTURE EXECUTION — READ-ONLY** step:

```bash
# FUTURE EXECUTION ONLY — verify Project, fields, items, and labels after a run.
gh project view "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json
gh project field-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json --limit 100
gh project item-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json --limit 100
gh label list --repo "$REPO" --limit 200
```

If a field or label was created incorrectly, stop and inspect the exact object ID before deleting or changing it. Project deletion, item deletion, field deletion, branch-rule changes, workflow reruns, and remote pushes are not rollback steps for this documentation package and require separate authorization.

## Official CLI references

- [`gh project`](https://cli.github.com/manual/gh_project)
- [`gh project create`](https://cli.github.com/manual/gh_project_create)
- [`gh project field-create`](https://cli.github.com/manual/gh_project_field-create)
- [`gh project item-edit`](https://cli.github.com/manual/gh_project_item-edit)
- [Customizing views in GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project)
