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

## Exact-source production rebuild fallback

Vercel CLI63.1.0 refused direct noninteractive promotion of preview cars-landing-ea40ttfgb-curtt.vercel.app because a production build is required. Its `promote --yes` help promises only to skip project-link confirmation; do not infer that it safely bypasses the preview-to-production rebuild requirement. The coordinator may instead build production from the already verified exact private source with:

```sh
vercel deploy --prod --yes --cwd /home/corp/autodata-evidence/cars-workshop-preview-redirect/deployment-src --scope curtt
```

This fallback is limited to existing cars-landing project `prj_1PcItrLSRbQXJL4lOYIUKeUmo8I2`, team `team_XlZCzZhR4wXeCFW8XdgisOuz`. Verify its private `.vercel/project.json` linkage before dispatch; never relink to/create another project. Freeze and require these exact three source SHA256 values immediately before and after the rebuild:

- index.html: `fb4b28780cabd9b72db5e063ac0dc49ceba2c93c4fe06ec954e7a2218b61cc3a`
- package.json: `866293bdde2425fc4dfcf8ea544f8d9ab095f89134c1df839876883160b52e79`
- vercel.json: `9890691d9fab0b7c187c699ad35da320f0dde404c21ff848ec25e0c4ae92d2f2`

Require parsed vercel.json to equal the recovered original config after removing only the one permitted redirects entry. Keep all original security headers, cleanUrls and trailingSlash settings. No additional application source, environment setting, domain assignment, DNS record, Firebase setting, payment setting, dependency or build command change is allowed. Capture the exact new production deployment ID and source hashes; retrieve its three source files through the read-only Vercel Files API and require identical hashes to the frozen local artifacts.

A production deploy may immediately assign cars.tk to the new deployment; it is a release action, so only the coordinator executes it after the successor full-SHA preflight. After Ready, verify apex `/workshop` temporary307, nested path307, bounded existing slash308 normalization, exact destination/query preservation, unchanged non-Workshop path statuses, all three security headers, and raw production `/` SHA256 `fb4b28780cabd9b72db5e063ac0dc49ceba2c93c4fe06ec954e7a2218b61cc3a`. No preview feedback stripping or other normalization is allowed on production. Verify preview purchase-config remains enabled:false. Any source, config, route, query, body or security check failure blocks acceptance and requires restoration of prior production deployment `dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf` (`cars-landing-ksupv50cx-curtt.vercel.app`) using the rollback procedure above. Record exact new/previous IDs, hashes, statuses, Locations and UTC timestamps in the canonical verification and Issue186. This planning agent performs no deployment/promotion.
