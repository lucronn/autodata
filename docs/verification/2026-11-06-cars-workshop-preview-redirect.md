# Cars Workshop temporary preview redirect verification

Goal: Provide a working cars.tk/workshop link through a temporary Vercel redirect to the existing Firebase-enabled autodata.cars.tk Workshop preview while preserving the landing page and purchase-disabled behavior.

Plan: `docs/superpowers/plans/2026-11-06-cars-workshop-preview-redirect.md`. Gate record: `docs/agents/records/2026-11-06-cars-workshop-preview-redirect.json`.
Issue: https://github.com/lucronn/autodata/issues/186. Project: https://github.com/users/lucronn/projects/8.

Canonical scope: one temporary307 Vercel redirect, /workshop/:path* → https://autodata.cars.tk/workshop/:path*, in the existing cars-landing project only. Preserve query parameters, static landing home bytes, existing cleanUrls/trailingSlash settings and all three security headers. Keep application purchase configuration disabled. No domain transfer, DNS change, backend origin change, Firebase change, payment operation or article/model call is included.

Concrete todo (same as plan and tracking):

- [ ] Synchronize the redirect goal, exact route, canonical documents and these four todos with Issue186 and Project8; commit/push the docs checkpoint and pass full-SHA machine preflight before implementation.
- [ ] Recover the three exact deployed cars-landing source files from deployment dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf into a private release directory; preserve index.html, package.json and all existing vercel.json settings and security headers.
- [ ] Add only the temporary /workshop/:path* redirect to https://autodata.cars.tk/workshop/:path*, verify bare and nested paths plus query preservation on a preview deployment, and have the coordinator authorize production promotion.
- [ ] Promote the verified cars-landing deployment, verify apex redirect and unchanged home/security headers plus disabled preview purchase configuration, record exact deployment evidence, and restore previous deployment dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf if verification fails.

Status: planning synchronized after tracking readback; checkpoint commit and full-SHA preflight still required before implementation. Deployment and runtime acceptance remain unexecuted. No claim of purchase, full article, or apex Firebase acceptance follows from this redirect.

Rollback baseline: deployment dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf, cars-landing-ksupv50cx-curtt.vercel.app. Restore/promote that exact previous deployment and reverify original landing bytes/security headers and Workshop404.

Tracking readback: https://github.com/lucronn/autodata/issues/186#issuecomment-6680119766; Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4 Release hotfix reference preserves its complete prior prefix and indexes this exact plan/todos/docs comment. Readback verified before checkpoint commit.
