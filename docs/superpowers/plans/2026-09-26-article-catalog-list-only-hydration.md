# Article catalog list-only hydration

Goal: make a vehicle article-catalog request fetch and persist only the source article index. A catalog read must never fall through to a full all-years provider snapshot or fetch every article body. Article body, image, and labor resources remain selected-detail work performed only after a user chooses an article.

Issue: https://github.com/lucronn/autodata/issues/113
Project: https://github.com/users/lucronn/projects/8
Canonical document: `docs/architecture/article-catalog-list-only-hydration.md`

## Scope

- Keep the public article-catalog response fast and metadata-only.
- Route `scope=articles` through a bounded, vehicle-family AutoAPI path that reads the article index plus the minimum vehicle identity resources needed to normalize and persist it.
- Make the provider dispatch contract reject generic snapshot or full-catalog methods for the article scope, preventing a future regression into all-years traversal.
- Preserve the existing selected-article detail path, including its query-time targeted body fetch. No article detail, image, parts, or labor endpoint is allowed during catalog-list hydration.
- Keep the canonical raw source snapshots and normalized `catalog_articles` list rows so later reads use the database without repeating the source call.
- Treat AutoAPItwo as selector/provider input only for this scope unless it exposes an explicit article-index method; its fleet snapshot must never be used as an article catalog fallback.

## Concrete todo

- [ ] Add a list-only article hydration boundary and prohibit generic full-catalog provider fallback for `scope=articles`.
- [ ] Reuse the bounded AutoAPI article-index path to persist list rows and raw provenance without selected article resources.
- [ ] Add regression tests proving article scope never invokes `fetch_catalog_snapshot`, `fetch_catalog`, article detail, image, or labor reads.
- [ ] Rebuild the local services and verify a cold vehicle article catalog returns list rows after one bounded hydration while a selected article remains query-time.

## Acceptance

- A cold `GET /v1/catalog/vehicles/{vehicle_id}/articles` schedules only a vehicle-scoped article-index hydration and does not block on an all-years traversal.
- The worker result and source request trace contain no `/article/{id}`, `/labor/{id}`, or image/detail request during catalog hydration.
- Normalized list rows are persisted with `content_status=list_only` and remain available on the next database read.
- The selected article endpoint may fetch one article body on demand and can promote that row to `content_complete` without rehydrating the whole catalog.
- Existing selector routes, UI progress states, raw source retention, and unrelated dirty work remain compatible.
