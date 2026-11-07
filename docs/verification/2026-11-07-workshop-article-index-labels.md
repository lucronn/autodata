# Workshop article index labels

The real Workshop index currently displays an “Article / Type” heading but its rows show only article titles. The repository-authored demo already displays both. The real index also uses “No articles match this search” when a completed vehicle index has zero articles and no search query, and can show that copy while an index is still being prepared.

The bounded fix displays the type supplied by each protected article descriptor, preserves descriptor order and article IDs, and uses the collection's explicit completion flag for empty copy. It changes browser presentation only; it does not add categories, article content, access grants, or checkout capability.

Acceptance:

- [ ] A visible real article row contains its title and readable type; activating it retains the original article ID.
- [ ] A search with zero matches explains the search result.
- [ ] A completed empty vehicle index says no articles are currently available.
- [ ] An incomplete empty vehicle index says it is still being prepared.
- [ ] Existing Workshop Node, demo, Go API, and diff checks pass on the implementation commit.

Tracking: [Issue #371](https://github.com/lucronn/autodata/issues/371) under [paid Workshop parent issue #186](https://github.com/lucronn/autodata/issues/186), [AutoData Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-07-workshop-article-index-labels.md).
