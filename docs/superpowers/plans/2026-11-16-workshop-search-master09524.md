# Integrate protected route-state baseline into draft paid search

Issue: https://github.com/lucronn/autodata/issues/393
Project: https://github.com/users/lucronn/projects/8
Draft PR: https://github.com/lucronn/autodata/pull/394

The verified migration fix is pushed at6dfe602c3b1a2ab4a8098e8ae30aab9ca32b8ffe (collector6/full synthetic receipt164 PASS). Root explicitly requested integrating protected master09524db599a82e7f8c79a1d8fb43bfadc6bbe2f3 after PR447 merged. Read-only merge-tree resultd290eb9822907178b293389e7c16f26d3fb8898c shows one conflict only, in apps/api-go/workshop-client.test.mjs: draft adds searchNavigation; master adds rows:{} and Option to the same library test context. Keep the union. apps/api-go/workshop/app.mjs auto-merges: its delta from draft is exactly the protected route-state fix (clear descendant option rows/search; restore URL q and reset vehicle/quote before all route branches), preserving paid query generations, denial and metadata-only behavior. Do not redesign routing, search, rendering, payment or grants.

Review the resulting app delta against exact PR447 source; retain master route regressions and draft search regressions. Run the complete Node Workshop test harness and JS syntax checks plus the six source-only paid migration collector tests and exact typed-ledger regression. No Go compilation or rerun of unchanged full synthetic Python suite is required unless a new failure/source change justifies it; CI reruns all required checks on final head. Modern-web-guidance navigation search and stack-drill-down guide were consulted; no new browser API, scrolling component or history mechanism is needed for this merge.

All edits/logs/cache remain in the isolated offloaded worktree/evidence location. No Docker starts/builds/pulls, SQL, provider, Stripe, browser runtime or public/private service change. Preserve source fixture flags and all runtime acceptance holds. PR394 stays draft;12-case paid PG/HTTP fixture and authenticated reader/search acceptance remain NOT_RUN until separately admitted.

## Todo

- Synchronize this exact-master integration amendment in Issue393/Project8 and canonical docs; commit checkpoint and pass preflight.
- Merge exact protected09524db599a82e7f8c79a1d8fb43bfadc6bbe2f3 into verified draft head6dfe602c without rewriting history.
- Resolve only the test harness namespace conflict by retaining searchNavigation plus rows/Option, preserving the auto-merged route-state and paid search source.
- Run all Workshop Node harness tests, JS syntax checks and focused Python migration/receipt regressions; push draft head and verify exact-head CI. Keep runtime12-case acceptance NOT_RUN.
