# Automatic permanent article rewrite verification

Implementation candidate: `7a1ae1689c8c65292dd409fa7bcab851e12289ca` (includes scoped historical fixture fix and missing-model configuration recovery).
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

## Missing-model recovery verification

Docs-only amendment checkpoint `9b67744` was committed/pushed and its exact-head preflight passed before implementation. Issue186 comments6680123658 and6680125162 and Project8 were synchronized/read back (length920). The code milestone `7a1ae1689c8c65292dd409fa7bcab851e12289ca` also passed exact-head preflight.

Without a configured model client, automatic work captures source and saves its normalized checkpoint, then parks with `MODEL_NOT_CONFIGURED`, status `failed`, no next-attempt time and zero rewrite attempts. Both bank tests prove that the existing reader continues returning `content_origin=source` and no canonical pointer. Repeated worker polls without a model do not claim the parked job. When a real model client is supplied after restart, the same current job/source/generation/profile resumes with a new fenced lease, preserving the original source-claim retry count without increment or reset. The accepted output publishes through the existing validation path. Existing missing-model dead letters recover only when no rewrite attempt exists; stale source/generation and failed or ambiguous attempts cannot recover. Historical profiles retain their original missing-model behavior.

Focused PostgreSQL verification: **9 passed, 38 deselected** in12.42s, covering both-bank park/resume, historical missing-key behavior, terminal no-attempt recovery, source/generation fences, failed/ambiguous exclusion and exact-job claim/sweep isolation. The first new test run exposed old terminal behavior as expected. One new stale-source fixture initially tried a forbidden source-projection downgrade; it was corrected to remove the job's source binding, and all nine focused cases passed. A separate exact-job test run passed1 case. The broader worker/job/publication run began before this fixture correction and finished **89 passed, 1 failed** in151.45s; its single failure is the same invalid test fixture already corrected and proven by the final focused run.

The scoped historical configuration fixture fix at `83b0b727736b36223e1859364bfeb49f67c3d93a` passed all **8 affected tests**. Root independently reviewed core code at `89b643336e47a9e2ecc9208a77552dd96d527e08` and the missing-key delta `9b67744..7a1ae16`; both reviews found no blocking issue.

| Additional evidence | SHA-256 |
| --- | --- |
| automatic-model-wait-focused.xml | 17f6d32dcada6d5babe381da419aeb280ee7cd6022f08de4961c8116fbff05c0 |
| automatic-exact-job.xml | a9f1d15a29fc57fa1c217b829a33aa4c6b6469fa37a9277c9e90a369fe772256 |
| legacy-scoped-fixture.xml | 329221dc93ea8efc1cd3db4df99490e099bea6b7f690e7ffab1a5f3a87724e3d |

## Remaining verification and preview handoff

The first unchanged fixture lifecycle smoke at `034708e8587abaf3e97cefa90cc47178f6cdfeb3` completed344 tests with6 historical applicability/configuration fixture failures, zero errors and zero skips. Those six cases are among the eight passing affected tests after the explicit v1 fixture correction. The second unchanged smoke started at `83b0b727736b36223e1859364bfeb49f67c3d93a` and completed **344 passed**, zero failures/errors/skips. The bind-mounted worktree advanced during this long-running process, so the result is not represented as immutable final-head verification. The original full ingestion suite completed **1375 passed, 7 failed, 44 skipped, 145 subtests passed** in719.58s. Six failures are the corrected historical applicability fixture cases. The seventh is the same profile-default mismatch in historical commerce `seed_readable_source`, now explicitly registered as v1 to match its unchanged ensure. This test-only scope amendment was synchronized in Issue186 comment6680197528/Project8 (readback951), committed at `9aa607f4b93bfbf4f67a8536a0a3a7c1b29cd262`, and passed exact-head preflight before its one-line fixture edit. No product/payment implementation changes. Neither broad run was restarted solely for repeat coverage; CI continues the final repository-wide checks. The initial full-suite result remains a known-failure run, not a fully passing suite. Authentic provider/model article acceptance has not been performed by this implementation agent, so synthetic lifecycle results do not certify real article prose quality or dataset coverage.

For an authorized preview, build/restart the ingestion worker from the reviewed candidate, retain existing API/reader/schema, and trigger the ordinary catalog/article prepare flow. New descriptors use auto. Existing source-only articles require explicit JSON selection and `scripts/dev/automatic_article_refresh.py --selection <file> --actor <operator> --reason <reason>`; inspect preview before adding `--apply`. Existing completed canonical publications stay permanent. The coordinator owns preview configuration and deployment; this agent has not enabled payment or changed production.


For strictly bounded preview capture/resume, call existing `autodata_ingestion.article_lifecycle.run_article_worker_once(repo, worker_id=uuid4(), registry=registry, object_store=objects, model_client=model, job_id=UUID(selected_job_id))` once per selected UUID. Construct repository, source registry, object store and actual optional model client exactly as `worker.article_worker_main` does. The optional UUID restricts successful-candidate resume, configuration resume, review resume, exhausted-job sweep and normal claim. The existing CLI `--once` remains global and is not the bounded preview entrypoint. Pass `model_client=None` while configuration is absent; provide the actual environment-built client after the secret is delivered and process restarted. Initial source acquisition consumes its normal lease claim; configuration polling/resume does not consume another model attempt. No preview deployment or real model acceptance is claimed by this evidence.


| Completed broad evidence | SHA-256 |
| --- | --- |
| automatic-rewrite-smoke.json (344 passed; worktree advanced during run) | fbddc9354d4dcf435c8f1d3171f4dbe1d6ee6f633e5b80e83ebf230436490fd4 |
| automatic-rewrite-smoke.xml | 69091917a7d4be22dafe219d5f9ec412561e5175dcdd4df7c4f88d092657494f |
| automatic-full-ingestion.xml (initial seven fixture failures) | 423f84eefb8dac57b87d10c176fadbf4fb7ae97836743e59ddc15d6b3a3f8496 |
| automatic-model-configuration.xml (initial one corrected fixture failure) | 6d7371617eb45a00e42859768ff8f97ed1570d0c82c94f1c8466176c34e75720 |

Final affected commerce plus missing-key/historical/exact-job PostgreSQL regression: **10 passed, 38 deselected** in13.33s. Evidence `automatic-final-focused.xml` SHA-256 `16bb22ea2008d70f190daded10780a7fb8a854cb91ac1cfd8e4b503198a77460`. Production implementation remains exactly the independently reviewed `7a1ae1689c8c65292dd409fa7bcab851e12289ca`; subsequent changes are docs and the one-line historical test registration.
