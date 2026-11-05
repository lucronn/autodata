# Release controller preflight verification

Issue: https://github.com/lucronn/autodata/issues/186  
Project: https://github.com/users/lucronn/projects/8  
Plan: [release controller](../superpowers/plans/2026-11-03-release-controller-preflight.md)

Authorized base: `179a0056f39ce9d6258789442c4d1f3457b4a880`.
Final independently approved candidate: `6762e844d12ef0d342e28f0131d477d73e1fe4a1`.
Integration: `116d949029edeccd3447da9dd0c5f3de4252c42b`.

The coordinator ran `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover
-s scripts/autonomy -p 'test_*.py'` in a separate clean candidate worktree and
on the integrated branch. Results: **96 tests passed** at the candidate
(14.397 seconds), **101 passed** at integration (14.464 seconds, including the
separately integrated provider-schema regressions). Independent exact-SHA review
approved the final delta with no remaining findings. Only release_controller.py,
test_release_controller.py, and docs/agents/release-controller.md changed.
Whitespace and Python compilation checks passed.

Retained coordinator logs:
`/tmp/autodata-r0-release-independent-676-tests.log` and
`/tmp/autodata-r0-release-integrated-tests.log`. Earlier rejected candidates and
review reproductions are retained separately; no review finding was waived.

Coverage includes exact candidate and evidence identity, synchronized Issue
metadata, discovered Project IDs and required-field validation, unrelated
Project field variants, queued requests with later pending checks, confirmed
merge receipts, tracking-discovery failure, retryable post-merge repair and
conflicting-receipt rejection in both read-only and executing modes. Read-only
validation makes no state or remote mutations. Pending requests do not reissue
merge commands. Confirmed merges remain distinguishable from tracking failures.

All commands were tested through deterministic fake GitHub responses. No live
merge, tracking repair, production deployment or real candidate release was
performed. Operators must supply the documented frozen release context and all
eight independently verified gate reports before invoking actual release.
