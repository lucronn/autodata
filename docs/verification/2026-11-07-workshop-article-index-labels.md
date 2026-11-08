# Workshop article index labels

The real Workshop index currently displays an “Article / Type” heading but its rows show only article titles. The repository-authored demo already displays both. The real index also uses “No articles match this search” when a completed vehicle index has zero articles and no search query, and can show that copy while an index is still being prepared.

The bounded fix displays the type supplied by each protected article descriptor, preserves descriptor order and article IDs, and uses the collection's explicit completion flag for empty copy. It changes browser presentation only; it does not add categories, article content, access grants, or checkout capability.

Acceptance:

- [x] A visible real article row contains its title and readable type; activating it retains the original article ID.
- [x] A search with zero matches explains the search result.
- [x] A completed empty vehicle index says no articles are currently available.
- [x] A completed empty vehicle index keeps that message when a search query is retained in the route.
- [x] An incomplete empty vehicle index says it is still being prepared.
- [x] A terminal failed index says it could not be prepared; it does not claim work is still in progress.
- [x] Existing Workshop Node, demo, Go API, and diff checks pass on the implementation candidate.

The type and empty-state tests first failed on the old renderer. A further terminal-failure test failed on “still being prepared” before that copy was corrected. Pre-merge review found that a retained search query still mislabeled a completed empty index; the new focused test failed on the search-only copy and passed after the renderer used the unfiltered article count. On the reviewed candidate tree, the full Workshop client and demo Node tests, Go API tests, JavaScript syntax checks, and `git diff --check` each exited 0. Go was run with the installed `/home/corp/.local/go1.23.4/go/bin/go` because `go` is absent from the host PATH.

Tracking: [Issue #371](https://github.com/lucronn/autodata/issues/371) under [paid Workshop parent issue #186](https://github.com/lucronn/autodata/issues/186), [AutoData Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-07-workshop-article-index-labels.md).
