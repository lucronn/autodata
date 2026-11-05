# Production Workshop origin alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Coordinator owns dispatch; this planning lane changes documentation only.

**Goal:** Align production Workshop authentication, checkout and hosted runtime origin validation with https://autodata.cars.tk while retaining exact https://cars.tk compatibility.

**Architecture:** Keep each existing language/runtime validator and its strict URL parsing. Replace the production singleton restriction with the same exact two-string allowlist at each boundary. Preserve the hosted runtime production/staging separation and exclude the new production hostname in the independent staging deployment input guard.

**Tech Stack:** Go API, Python ingestion commerce, Python self-contained hosted deployment tooling, unittest and Go testing.

**Spec:** `docs/architecture/workshop-commerce.md`, “Production Workshop origin alignment — Issue323” below.

Issue: https://github.com/lucronn/autodata/issues/323
Project: https://github.com/users/lucronn/projects/8
Project item: `PVTI_lAHOCSJ8cc4BiQ2BzhGUEXg`
Source base: `e8c1993dc317d8f05f73b5610123c90bde767b46` (verified clean master before planning).
Implementation base: the committed planning checkpoint containing this plan and synchronized record, resolved by full SHA and preflight before implementation; the source base alone does not pass the new gate.

## Global constraints

- Production accepts exactly `https://autodata.cars.tk` and `https://cars.tk` as configured origin strings. No wildcard, hostname suffix match, normalization, URL path, port or trailing slash is introduced.
- The public Workshop is `https://autodata.cars.tk/workshop/`; `https://cars.tk` remains the marketing domain and backward-compatible production deployment origin.
- Firebase identity/project/emulator restrictions, production local-mode denial, session cookie/origin/CSRF checks, commerce ownership, Stripe destination validation, settlement and purchase interlock remain unchanged.
- Runtime host config binds either production origin to environment=production; staging must reject both. Existing staging restrictions remain intact.
- No dependency, API contract, schema, secret, runtime environment, DNS, reverse proxy, Kubernetes, deployment or live-sales change is included. Source verification cannot prove deployed Firebase authorization or session/checkout behavior.
- No broad authentication refactor or shared cross-language configuration mechanism. The three validators keep one identical explicit allowlist contract, checked with the same matrix.

## File scope and audit

Implementation paths (exact eight):
1. `apps/api-go/auth_config.go`: production auth origin membership only.
2. `apps/api-go/auth_config_test.go`: valid production Firebase configuration and strict origin rejection matrix.
3. `workers/ingestion-python/src/autodata_ingestion/commerce_service.py`: production checkout return-origin membership only.
4. `workers/ingestion-python/tests/test_commerce_service.py`: same production origin matrix and unchanged staging/test controls.
5. `infra/deploy/gce/runtime-check.py`: production iff allowlist membership, preserving self-contained validator and all schema/hash rules.
6. `infra/deploy/gce/test_host_runtime.py`: both production origins accepted, both denied as staging, invalid production strings rejected, rendered service origin remains literal.
7. `infra/deploy/gce/staging_deploy.py`: add `autodata.cars.tk` to existing cars.tk/www.cars.tk exclusion in independent staging_origin input validation.
8. `infra/deploy/gce/test_staging_deploy.py`: new production hostname denied before deployment work.

Documentation: this plan, synchronized record `docs/agents/records/2026-11-05-workshop-production-origin.json`, and `docs/architecture/workshop-commerce.md`. Completion evidence may be added to the plan/contract and Issue323/Project8.

Audit findings: `publisher_live.runtime_config` and `staging_bootstrap.validate_approval` invoke the hosted runtime validator before side effects, so its environment-membership rule already excludes both production origin strings. Their redundant legacy checks do not need an edit. `infra/k8s/base.yaml` defaults to the still-supported legacy `https://cars.tk`; switching its actual deployment host is outside this source contract. Bankone/Banktwo source URLs are unrelated provider origins. The runtime renderer already passes public_origin through to API/commerce; do not rewrite render templates.

## Todo

- [ ] Commit the synchronized plan/contract/record checkpoint and pass exact-checkpoint machine preflight.
- [ ] Add failing Go/Python/runtime origin matrix cases and the independent staging deploy collision case.
- [ ] Change only exact production origin allowlists and the staging deploy production-host exclusion.
- [ ] Run focused suites, full Go API tests/vet, diff checks, and independent review; commit and push validated milestones.
- [ ] Record exact source verification in canonical docs and GitHub tracking; deployment and live authentication/checkout remain separate.

## Task 1: Establish failing strict origin cases

**Files:** the four test paths in the implementation scope above.
**Interfaces:** Go `loadCustomerAuthConfig(getenv func(string) string) (customerAuthConfig, error)`; Python `checkout_return_origin(environment, value)`; hosted `validate_config(config)`; independent staging `validate_config(value, source, *, bootstrap=False)`.

- [ ] Extend Go auth tests with `identityTestConfig()` and environment=production, using the valid Firebase fields already supplied. For each allowed origin require no error and preservation of c.Origin. Test both default project.firebaseapp.com and matching public hostname auth domains. For each denied production string require an error. Retain production local-mode and emulator rejection assertions.

```go
for _, origin := range []string{"https://autodata.cars.tk", "https://cars.tk"} {
    m := identityTestConfig()
    m["AUTODATA_ENV"] = "production"
    m["AUTODATA_PUBLIC_ORIGIN"] = origin
    c, err := loadCustomerAuthConfig(func(k string) string { return m[k] })
    if err != nil || c.Origin != origin { t.Fatalf("origin %q: %v", origin, err) }
}
```

- [ ] Extend `test_return_origin_is_server_configured_and_environment_bound` with both production successes and the denial matrix below. Keep `https://stage.example:8443` staging and `http://127.0.0.1:8080` test acceptance.

```python
for origin in ('https://autodata.cars.tk', 'https://cars.tk'):
    self.assertEqual(checkout_return_origin('production', origin), origin)
```

- [ ] In `test_config_hash_and_origin_bind_environment`, validate each allowed origin in a deepcopy of the existing host config with environment=production; reject both in the existing staging config. Reject each denial vector with environment=production. Extend the existing renderer literal-origin assertion to cover the new origin without changing hash/schema expectations.

```python
for origin in ('https://autodata.cars.tk', 'https://cars.tk'):
    production = copy.deepcopy(self.config)
    production.update(environment='production', public_origin=origin)
    self.rt.validate_config(production)
    staging = copy.deepcopy(self.config)
    staging['public_origin'] = origin
    with self.assertRaises(self.rt.ContractError):
        self.rt.validate_config(staging)
```

- [ ] Add `https://autodata.cars.tk` to the existing denied staging_origin vector loop in `test_staging_deploy.py`.
- [ ] Run the focused commands below and capture the expected new-origin failures before implementation. Existing baseline failures are blockers to inspect, not assertions to weaken.

Production denied vector matrix for Go auth, Python checkout and hosted runtime:

```text
https://other.example
https://www.cars.tk
https://evil.autodata.cars.tk
https://autodata.cars.tk.evil.example
http://autodata.cars.tk
https://autodata.cars.tk/
https://autodata.cars.tk/workshop/
https://autodata.cars.tk:443
https://user@autodata.cars.tk
https://autodata.cars.tk?q=1
https://autodata.cars.tk#fragment
https://autodata.cars.tk.
https://AUTODATA.cars.tk
```

## Task 2: Minimal aligned validators and verification

**Files:** the four implementation paths in scope above.
**Interfaces:** unchanged signatures; allowed strings pass through verbatim; invalid configuration uses existing errors.

- [ ] Replace only the production check in Go:

```go
if c.Environment == "production" && c.Origin != "https://cars.tk" && c.Origin != "https://autodata.cars.tk" {
    return c, invalid
}
```

- [ ] Replace only Python checkout production equality:

```python
if environment == 'production':
    valid = valid and value in {'https://cars.tk', 'https://autodata.cars.tk'}
```

- [ ] Replace only hosted runtime production/environment equivalence:

```python
require((config['public_origin'] in ('https://cars.tk', 'https://autodata.cars.tk')) == (config['environment'] == 'production'))
```

- [ ] Extend only independent staging hostname exclusion:

```python
require(origin.hostname not in ('cars.tk', 'www.cars.tk', 'autodata.cars.tk'))
```

- [ ] Run formatting and focused suites; then full Go tests/vet and the hosted runtime/staging suites. Review the diff for unchanged session/commerce security and production gating. Commit a coherent validated milestone and promptly push to `codex/workshop-production-origin`.

Commands from repository root:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-workshop-production-origin.json --base-sha "$CHECKPOINT_SHA"
cd apps/api-go
gofmt -w auth_config.go auth_config_test.go
go test ./... -run TestCustomerAuthConfiguration -count=1
go test ./...
go vet ./...
cd ../..
python3 -m unittest discover -s workers/ingestion-python/tests -p test_commerce_service.py
python3 -m unittest discover -s infra/deploy/gce -p test_host_runtime.py
python3 -m unittest discover -s infra/deploy/gce -p test_staging_deploy.py
git diff --check
```

If a command needs dependencies, use the repository's existing compatible runtime/container. Record any genuine environment blocker. Do not alter assertions, add dependency manifests or claim passing checks without output.

- [ ] Coordinator obtains independent review of the exact implementation SHA, addresses findings within this scope, records exact commands/results and source SHA in this plan/contract and Issue323, updates Project8 status and pushes the final documentation milestone. No merge or deployment follows from this plan alone.

## Synchronized pre-implementation record

The standalone JSON is the handoff record; its contents are identical to this embedded record at checkpoint creation:

```json
{
  "goal": "Align production Workshop authentication, checkout and hosted runtime origin validation with https://autodata.cars.tk while retaining exact https://cars.tk compatibility.",
  "plan_ref": "docs/superpowers/plans/2026-11-05-workshop-production-origin.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/323",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/architecture/workshop-commerce.md"
  ],
  "todo": [
    "Commit the synchronized plan/contract/record checkpoint and pass exact-checkpoint machine preflight.",
    "Add failing Go/Python/runtime origin matrix cases and the independent staging deploy collision case.",
    "Change only exact production origin allowlists and the staging deploy production-host exclusion.",
    "Run focused suites, full Go API tests/vet, diff checks, and independent review; commit and push validated milestones.",
    "Record exact source verification in canonical docs and GitHub tracking; deployment and live authentication/checkout remain separate."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-05T15:28:27.917787Z"
}
```

## Planning verification

The checkpoint commit contains this plan, the canonical contract amendment and synchronized record. The coordinator must use that full commit SHA as implementation base and retain the passing machine preflight output. Exact checkpoint SHA and GitHub source links are recorded externally in Issue323 after commit to avoid a self-referential commit hash.
