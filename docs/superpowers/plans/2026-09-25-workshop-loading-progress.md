# Workshop loading progress

Goal: make every asynchronous workshop load explain its current stage and bounded progress percentage, including partial catalog hydration and article opening.

Issue: https://github.com/lucronn/autodata/issues/113
Project: https://github.com/users/lucronn/projects/8
Canonical document: `docs/architecture/workshop-loading-progress.md`

## Scope

The workshop remains a browser client of the existing catalog API. This change is limited to the loading experience:

- Show one consistent progress bar and accessible status text while a request is active.
- Report the current operation as an ordered stage: years, makes, models, engine / trim, article catalog, or article.
- Show `step N of 6` and a percentage derived from the stage's fixed range. Percentages describe client workflow progress; they do not claim that an upstream provider exposes an exact byte or row count.
- Advance within a stage while the API reports `hydrating`, but cap the estimate below the next stage until the API returns a complete result.
- Reset progress when a parent choice changes, an obsolete request is cancelled, or a request ends in an error.
- Keep the existing cancellation, retry, polling limit, source ordering, and article rendering behavior.

## Concrete todo

- [ ] Add the deterministic stage model and accessible progress markup/styles.
- [ ] Connect selector, article-catalog, and article-detail requests to stage and percentage updates, including bounded hydration polling.
- [ ] Add focused regression coverage and verify the live workshop route with a slow/partial catalog response and a completed vehicle flow.

## Acceptance

- During a year-to-make request, the page visibly says `Step 2 of 6`, identifies `Makes`, and exposes a percentage through both the progress bar and accessible status text.
- Every stage has a stable range and completion reaches the end of that range only when the corresponding API operation completes.
- A hydrating response advances within its current range and never reaches the next stage or 100% while incomplete.
- Changing the vehicle or cancelling a request cannot leave stale progress visible as if it belongs to the new selection.
- Existing workshop behavior and catalog API contracts remain unchanged.
- Client unit tests, Go tests, and live HTTP/browser checks pass.
