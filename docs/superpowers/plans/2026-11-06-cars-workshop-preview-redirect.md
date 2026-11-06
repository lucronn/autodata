# Cars Workshop Preview Redirect Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to execute the following bounded steps after the exact checkpoint preflight and coordinator dispatch.

**Goal:** Provide a working cars.tk/workshop link through a temporary Vercel redirect to the existing Firebase-enabled autodata.cars.tk Workshop preview while preserving the landing page and purchase-disabled behavior.

**Architecture:** Keep cars.tk assigned to cars-landing. Add a temporary HTTP307 external redirect in its existing Vercel configuration, so browser navigation reaches the already configured preview Firebase origin. No application, catalog, auth, payment, domain assignment or DNS changes.

**Tech Stack:** Existing static cars-landing Vercel project and Vercel CLI.

**Spec:** `docs/verification/2026-11-06-cars-workshop-preview-redirect.md`

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Record: `docs/agents/records/2026-11-06-cars-workshop-preview-redirect.json`

## Concrete todo

- [ ] Synchronize the redirect goal, exact route, canonical documents and these four todos with Issue186 and Project8; commit/push the docs checkpoint and pass full-SHA machine preflight before implementation.
- [ ] Recover the three exact deployed cars-landing source files from deployment dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf into a private release directory; preserve index.html, package.json and all existing vercel.json settings and security headers.
- [ ] Add only the temporary /workshop/:path* redirect to https://autodata.cars.tk/workshop/:path*, verify bare and nested paths plus query preservation on a preview deployment, and have the coordinator authorize production promotion.
- [ ] Promote the verified cars-landing deployment, verify apex redirect and unchanged home/security headers plus disabled preview purchase configuration, record exact deployment evidence, and restore previous deployment dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf if verification fails.

## Global constraints and evidence

This checkpoint is documentation only; implementation and deployment belong to the coordinator after passing full-SHA preflight. cars.tk is currently assigned to cars-landing (project prj_1PcItrLSRbQXJL4lOYIUKeUmo8I2), with production deployment dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf at cars-landing-ksupv50cx-curtt.vercel.app. Its /workshop currently returns Vercel404. The preview /workshop and /readyz return200. Its purchase-config is enabled:false. Both running API processes use AUTODATA_PUBLIC_ORIGIN=https://autodata.cars.tk; Firebase authorizedDomains includes autodata.cars.tk and excludes cars.tk. Apex alias migration would break identity origin checks, so it is outside this task.

## Task 1: Recover and change only the redirect configuration

Files: private deployment artifact directory `/home/corp/autodata-evidence/cars-workshop-preview-redirect/deployment-src/`; recover index.html, package.json and vercel.json, then modify only vercel.json. No repository implementation files are authorized by this checkpoint.

- [ ] Recheck the current production deployment identity before recovery. If it differs from dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf, stop and reconcile rather than overwriting someone else's change.
- [ ] Recover source using read-only `vercel api /v6/deployments/dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf/files --scope curtt`, then GET `/v7/deployments/dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf/files/<uid>` and decode its base64 data privately. Known UIDs: index.html a0f7b9a24258ed12b177df6738b9908ca3894c4b, package.json 1f52173f4eaa6213bc0cc4cfdd6b9d6d6ed194c5, vercel.json 064bd48c8454c71c7bf4bda5844074c7f29a9a97. Record SHA256 of originals.
- [ ] Retain `cleanUrls:true`, `trailingSlash:false`, and existing X-Content-Type-Options:nosniff, Referrer-Policy:strict-origin-when-cross-origin, X-Frame-Options:DENY headers. Add only this redirects entry:

```json
{"redirects": [{"source": "/workshop/:path*", "destination": "https://autodata.cars.tk/workshop/:path*", "permanent": false}]}
```

- [ ] Compare parsed original/new config after removing only the new redirects key; require exact equality. Require index.html/package.json SHA256 unchanged. Link the private artifact to existing project ID prj_1PcItrLSRbQXJL4lOYIUKeUmo8I2/team team_XlZCzZhR4wXeCFW8XdgisOuz; do not create a project. Keep private local metadata outside Git.

## Task 2: Verify and promote the isolated deployment

- [ ] Deploy a preview of that existing project with `vercel --cwd /home/corp/autodata-evidence/cars-workshop-preview-redirect/deployment-src --scope curtt --yes`. Save the exact Ready deployment ID and original/new config hashes.
- [ ] Use GET without following redirects against preview `/workshop`, `/workshop/`, `/workshop/example`, and `/workshop?order=redirect-probe&region=US`. Require HTTP307 with correct destination path, allowing existing trailing-slash normalization as a bounded intermediate hop; require each query value survives the final redirect. Never create a payment or authenticated session. If Vercel preview protection prevents public probes, use its authenticated CLI request tooling without logging tokens, or do not promote.
- [ ] Require preview `/` HTTP200 and all three existing security headers. Compare its landing body byte-for-byte to baseline after removing only the exact Vercel-injected preview feedback suffix allowed by the acceptance amendment below; record raw and comparison hashes. Require no new redirect for `/auth/config` or `/v1/catalog/years`; these remain owned by the landing project and their baseline status must match.
- [ ] Coordinator reviews exact deployment/config diff and promotes only after required verification. Use `vercel promote <verified-deployment-url> --scope curtt`; do not move domains or DNS.
- [ ] Repeat apex route/query/home/header checks, requiring the raw production home body to match baseline byte-for-byte without any normalization or script removal. Confirm preview `/workshop/purchase-config.json` remains enabled:false. Record exact status/Location, hashes, deployment ID and UTC timestamp in the canonical verification document and Issue186/Project8.

## Rollback

Restore the exact previous production deployment with `vercel promote cars-landing-ksupv50cx-curtt.vercel.app --scope curtt` (deployment dpl_FewQnGj6wVh7GodgrML8QbrSd7Uf), then verify `/` and its three headers match baseline and `/workshop` returns its original404. This is a redeploy/re-promotion of the previous source, not a domain reassignment. If promotion cannot reuse the retained deployment, recover and redeploy its unchanged three files to the same cars-landing project. Never restore/delete application databases. No rollback action is executed by this planning agent.

Tracking readback: https://github.com/lucronn/autodata/issues/186#issuecomment-6680119766; Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4 Release hotfix reference preserves its complete prior prefix and indexes this exact plan/todos/docs comment. Readback verified before checkpoint commit.

## Preview feedback script acceptance amendment

The coordinator's Ready preview is `dpl_8oTwc6JNM38pMgyDAXnJ9jZwKqSX`. Read-only retained-body comparison independently confirms Vercel appends exactly one163-byte feedback script after the original closing `</html>` and newline. Baseline home SHA256 is `fb4b28780cabd9b72db5e063ac0dc49ceba2c93c4fe06ec954e7a2218b61cc3a`; raw preview home SHA256 is `9f91843b34673c371fa814eb9ed1b4c754d4400594b8b65726f6659cc42cfecb`. The exact appended suffix is:

```html
<script async data-explicit-opt-in="true" data-deployment-id="dpl_8oTwc6JNM38pMgyDAXnJ9jZwKqSX" src="https://vercel.live/_next-live/feedback/feedback.js"></script>
```

For this exact preview deployment only, require that exact suffix occurs once at the end, record its163-byte length and SHA256 `b56e688a449710b744f885c2672b93d2e602d74ff47a5c7cf50e59728d3aa389`, remove only those exact bytes in the comparison buffer, and require all remaining bytes equal the baseline body. Do not alter the served page or source, strip arbitrary scripts, normalize whitespace, parse/reserialize HTML, or ignore other differences. For another preview deployment, capture and explicitly review its exact platform-injected suffix before accepting an equivalent narrowly scoped comparison.

Production apex `/` after promotion and after any rollback must match the unmodified baseline body byte-for-byte with raw SHA256 `fb4b28780cabd9b72db5e063ac0dc49ceba2c93c4fe06ec954e7a2218b61cc3a`; no script removal or normalization is permitted. If production differs, stop acceptance and restore the prior deployment. Existing security-header, redirect path/query, landing config and disabled-purchase requirements remain mandatory.

Coordinator-reported preview observations: Workshop307, nested307, preserved query, trailing slash308 normalization hop, non-Workshop paths404 and unchanged security headers. These observations do not substitute for post-promotion production verification. This amendment is docs only; this planning agent did not deploy or promote.
