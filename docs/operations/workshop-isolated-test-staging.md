# Isolated Workshop Stripe TEST staging

Issue https://github.com/lucronn/autodata/issues/445; parent https://github.com/lucronn/autodata/issues/398.
Project https://github.com/users/lucronn/projects/8.
Source base: a82b31dc8850aa3956972928b8c720969765a972.

Goal: Prepare current-source isolated Workshop Stripe TEST staging with truthful TEST-only notices and durable secret delivery.

Plan: `docs/superpowers/plans/2026-11-16-workshop-isolated-test-staging.md`. Record: `docs/agents/records/2026-11-16-workshop-isolated-test-staging.json`.

This lane prepares an isolated runtime and test-only notices; no production purchase policy is approved. No new runtime is running at this planning checkpoint. Historical local stage recovery restored its disabled-commerce API but is not this staging deployment.

Existing checkout-test credentials are private configuration inventory, not proof of current authenticated merchant readiness. Its API cannot start because transient ADC/config files disappeared; current-source staging uses new durable per-service secret files after explicit review. Legacy authorized-user ADC belongs to the existing gcloud account, has no offline verified scopes and must not be silently reused.

The selected API origin must be separate HTTPS and Firebase-authorized, with exact registered tester UIDs. Existing public aliases are forbidden. Cloudflare local authority currently consists of a run token, not verified DNS/account-management authority; cars.tk DNS uses Vercel. No stable staging route has been established. Root reviews DNS/origin and Docker starts separately. No real bank/model content enters without source authorization.

TEST-only pages describe simulated charges, temporary test grants, diagnostic handling and maintainer feedback without production seller, privacy-retention or final tax promises. They do not approve PR348. Enabled test purchase config points all four URLs at the same reviewed staging origin; no real tax is collected in TEST mode. Live purchase configuration remains disabled.

## Concrete todo
- [ ] Synchronize plan, Issue445, Project8 and canonical documentation; pass exact-base preflight
- [ ] Add server-gated TEST-only notices with route and production-mode denial tests
- [ ] Add offline isolated-stack renderer and durable JSON secret launcher; test production/live/shared-resource/empty-tester refusal
- [ ] Prepare reviewed current-source runtime inputs; hold Docker, DNS/origin and external Stripe TEST calls for coordinator review
- [ ] Run actual restricted authenticated TEST checkout/grant/read/denial/refund acceptance only after runtime prerequisites; do not substitute fixtures or claim missing licensed acceptance
