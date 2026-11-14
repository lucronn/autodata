# Workshop reader focus

Restore keyboard focus when opening Workshop articles and returning to the article index, without moving focus during background article updates.

The planning source of truth is [the implementation plan](../superpowers/plans/2026-11-14-workshop-reader-focus.md); tracking lives at https://github.com/lucronn/autodata/issues/407 and https://github.com/users/lucronn/projects/8.

An article navigation moves focus into its visible reader heading once, immediately. New article navigation announces an opening title; a same-article retry retains the title. Background rendering preserves the user's focus. Returning to the index reveals the focused index heading.

Implementation is pending the committed checkpoint and successful machine preflight.

Concrete todo:

- Move focus to the article heading once when an authenticated article navigation starts; supply an opening title for a new article and preserve the existing title when retrying the same article.
- Keep prepare and polling renders from moving focus; let Back scroll the focused article-index heading into view.
- Verify production navigation code with focused regression tests and headless Chromium at narrow and desktop viewport sizes; run the complete Workshop client suite.
- Commit and push the independently reviewable UI milestone, record exact evidence, and hand the branch to the coordinator for integration and deployment.
