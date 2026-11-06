# Automatic permanent article rewrite verification

Implementation candidate: `034708e8587abaf3e97cefa90cc47178f6cdfeb3`.
PR: https://github.com/lucronn/autodata/pull/342
Tracking: https://github.com/lucronn/autodata/issues/186#issuecomment-6679826363
Recovery amendment: https://github.com/lucronn/autodata/issues/186#issuecomment-6679877079
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-06-automatic-permanent-article-rewrite.md`.

## Implemented behavior

New article descriptors explicitly select immutable `full-prose-auto-v1`. Successful full-prose candidates publish automatically into the existing immutable canonical revision and reuse it permanently. The worker never creates or requires a content-review row for this profile. Source remains readable until publication or after a mechanical failure; automatic terminal failures use `dead_letter` (the existing API represents this as failed).

The model must replace ordinary prose leaves. Merely retaining source text or changing whitespace, capitalization or punctuation is rejected. Technical-only token leaves can remain literal with explicit accounting. One source-bound introduction and the existing ordered article format preserve tables, safety blocks, headings, links, media, evidence and block order. Saved-source, prompt, response, projection and ownership checks are recomputed before publication. These are mechanical integrity checks, not a proof of semantic equivalence or human content approval.

Historical profiles retain their original behavior. The shared historical runtime fixture explicitly selects v1 after its actual catalog indexing; dedicated automatic runtime cases select the new profile. Existing canonical revisions are neither deleted nor rewritten. Existing source-only articles can be selected using the bounded operator CLI; preview is the default, expected source revision is rechecked under the refresh lock, and already published canonical content is retained. Applying refresh may fetch the source once again when the worker runs; it is not represented as a completely offline transformation.

## Planning checkpoints

- Initial docs-only checkpoint `e8285409482c96238e9611ee29ce661652ae8066`: preflight returned `{"status":"synchronized","errors":[]}`.
- Recovery/fixture scope checkpoint `5faca2c088622ce642feb1e6d3fcabcdc9936eec`: preflight returned `{"status":"synchronized","errors":[]}` before editing its additional paths.

## Executed checks

- Pure auto/full/v1/v2 rewrite modules: **208 passed**. Tests first showed the automatic profile unsupported, ordinary-prose retention incorrectly accepted by the old full renderer, and punctuation-only changes passing before the new guard.
- Automatic worker/publication/job cases in real isolated PostgreSQL: **8 passed**. Covers Bankone and Banktwo publication without review, 100 warm ensures/reads, invalid prose retaining source, tampered saved response rejection, saved-candidate recovery, final-attempt budget recovery without another model attempt, and failed/ambiguous output exclusion.
- Identity/default registration and generic source jobs in PostgreSQL: **28 passed**. New registrations select automatic; re-registration preserves existing profile and schedules nothing.
- Bounded refresh selection/preview/apply and stale expected-source tests: **7 passed**, including actual PostgreSQL apply and duplicate scheduling prevention.
- Actual CLI worker processes, loopback provider/model HTTP, PostgreSQL and S3: **5 passed**. Both banks independently expose source before model work, publish automatically, retain truthful `UNREVIEWED` metadata, restart and serve 100 warm reads/ensures with measured source=0, asset=0, model=0, schedule=0. Twenty ensures join one job. Killing a worker after its saved response or inside publication produces one model attempt and one event. The fifth case verifies historical v1 warm restart.
- Broader worker/publication/job/manual-review suite: **166 passed, 2 fixture setup errors** on its initial run. Both errors were SeaweedFS refusing object writes because the Docker data partition had only about2.8% free space; no application assertion failed. The owned sandbox S3 service was moved to a bind directory on the `/home` filesystem with about11GiB free. The subsequent five runtime cases passed against that isolated storage. This initial broad result is not reported as a fully passing suite.
- `git diff --check`: passed before the implementation milestone commit.

Evidence is private under `/home/corp/autodata-evidence/automatic-permanent-article-rewrite/`. Disposable project: `autodata-auto-rewrite`; runner image: `autodata-source-projection-v2-test-runner:latest`; S3 uses the repository-pinned SeaweedFS image from the unchanged lifecycle Compose definition plus a sandbox-only external storage override. No serving or production runtime was changed.

| Evidence | SHA-256 |
| --- | --- |
| automatic-focused.xml | 28b575641cc1639fa9701a3ee694fc5b25885b4e864ed15a2ae88d9c2adb4d5e |
| automatic-refresh.xml | 592acf11fd3e16ad586a9b008bb0ff83b5d70d55370e22907abaa5b8dcff95ae |
| registration-jobs.xml | dfef1b5eaa0e656c51979b865354d3f3c30821cecdd1ee27b2802e0afc612549 |
| automatic-real-runtime.xml | 070cc908252e4c098a743b194f86fa5bc1368966ee6d99e57661f6885d738eb3 |
| automatic-lifecycle-milestone.xml (initial broad run) | bb96910f8ecbc482eb7b619ba358db0e3065afebef3c02b7a5c3877983e0db8b |

## Remaining verification and preview handoff

The unchanged required lifecycle smoke and full ingestion suite remain to be recorded. The smoke is running against the exact implementation candidate after correcting isolated storage. Independent exact-code review and GitHub checks remain integration boundaries. Authentic provider/model article acceptance has not been performed by this implementation agent, so synthetic lifecycle results do not certify real article prose quality or dataset coverage.

For an authorized preview, build/restart the ingestion worker from the reviewed candidate, retain existing API/reader/schema, and trigger the ordinary catalog/article prepare flow. New descriptors use auto. Existing source-only articles require explicit JSON selection and `scripts/dev/automatic_article_refresh.py --selection <file> --actor <operator> --reason <reason>`; inspect preview before adding `--apply`. Existing completed canonical publications stay permanent. The coordinator owns preview configuration and deployment; this agent has not enabled payment or changed production.
