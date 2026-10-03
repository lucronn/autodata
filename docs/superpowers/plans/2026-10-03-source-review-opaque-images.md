# Plan: Use opaque image URLs in stored source review

## Goal

Keep stored-source review illustrations working with the opaque media route, without exposing provider paths or emitting the disabled legacy query URL.

## Tracking

- **Issue:** https://github.com/lucronn/autodata/issues/114
- **Project:** https://github.com/users/lucronn/projects/8
- **Plan:** `docs/superpowers/plans/2026-10-03-source-review-opaque-images.md`
- **Canonical contract:** `docs/architecture/catalog-source-review.md`
- **Follow-up PR:** #119

## Evidence and decision

The source HTML sanitizer currently calls `catalogImageProxyURL`, producing `/v1/catalog/images?src=...`. PR #118 rejects that legacy route and only serves authenticated randomized `/v1/catalog/images/{token}` paths. Consequently, source-review images either fail to load or disclose provider URLs in the JSON representation. Pass the configured image key through source sanitization and seal every allowlisted resolved source image URL into an opaque path token. Reject inline `data:image` URLs and remove image elements that cannot be represented by a valid opaque token. Fail closed when the key is unavailable.

## todo

1. Synchronize this plan and concrete work items to Issue #114 and Project #8.
2. Generate source-review image links with the same opaque-token mechanism as normalized article images.
3. Add regression tests for JSON and browser source views proving no provider path or `?src=` leaks and that the opaque reference resolves.
4. Run Go tests/vet and verify the full hosted Compose fast lane for PR #119 and all stacked descendants.

## Acceptance

- Source-review HTML contains only same-origin opaque image path tokens; unsupported and inline data images are removed.
- Source-review JSON does not contain provider URLs, provider paths, or the legacy `?src=` route.
- Missing image-key configuration fails closed for source images in both JSON and browser source responses.
- The public opaque image endpoint continues to serve the sealed allowlisted image URL.
