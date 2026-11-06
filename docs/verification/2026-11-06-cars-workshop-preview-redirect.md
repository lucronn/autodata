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

Status: initial checkpoint9fd3639b7dfaa34c330610d02f798016e66e5e2a passed exact-SHA preflight; coordinator prepared a Ready preview. This documentation successor requires its own committed full-SHA preflight before coordinator promotion; production acceptance remains unexecuted. No claim of purchase, full article, or apex Firebase acceptance follows from this redirect.

Rollback baseline: deployment dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf, cars-landing-ksupv50cx-curtt.vercel.app. Restore/promote that exact previous deployment and reverify original landing bytes/security headers and Workshop404.

Tracking readback: https://github.com/lucronn/autodata/issues/186#issuecomment-6680119766; Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4 Release hotfix reference preserves its complete prior prefix and indexes this exact plan/todos/docs comment. Readback verified before checkpoint commit.

## Preview feedback script acceptance amendment

The coordinator's Ready preview is `dpl_8oTwc6JNM38pMgyDAXnJ9jZwKqSX`. Read-only retained-body comparison independently confirms Vercel appends exactly one163-byte feedback script after the original closing `</html>` and newline. Baseline home SHA256 is `fb4b28780cabd9b72db5e063ac0dc49ceba2c93c4fe06ec954e7a2218b61cc3a`; raw preview home SHA256 is `9f91843b34673c371fa814eb9ed1b4c754d4400594b8b65726f6659cc42cfecb`. The exact appended suffix is:

```html
<script async data-explicit-opt-in="true" data-deployment-id="dpl_8oTwc6JNM38pMgyDAXnJ9jZwKqSX" src="https://vercel.live/_next-live/feedback/feedback.js"></script>
```

For this exact preview deployment only, require that exact suffix occurs once at the end, record its163-byte length and SHA256 `b56e688a449710b744f885c2672b93d2e602d74ff47a5c7cf50e59728d3aa389`, remove only those exact bytes in the comparison buffer, and require all remaining bytes equal the baseline body. Do not alter the served page or source, strip arbitrary scripts, normalize whitespace, parse/reserialize HTML, or ignore other differences. For another preview deployment, capture and explicitly review its exact platform-injected suffix before accepting an equivalent narrowly scoped comparison.

Production apex `/` after promotion and after any rollback must match the unmodified baseline body byte-for-byte with raw SHA256 `fb4b28780cabd9b72db5e063ac0dc49ceba2c93c4fe06ec954e7a2218b61cc3a`; no script removal or normalization is permitted. If production differs, stop acceptance and restore the prior deployment. Existing security-header, redirect path/query, landing config and disabled-purchase requirements remain mandatory.

Coordinator-reported preview observations: Workshop307, nested307, preserved query, trailing slash308 normalization hop, non-Workshop paths404 and unchanged security headers. These observations do not substitute for post-promotion production verification. This amendment is docs only; this planning agent did not deploy or promote.
