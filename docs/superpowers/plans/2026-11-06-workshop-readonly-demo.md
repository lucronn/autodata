# Workshop Read-only Demo Implementation Plan

> **For agentic workers:** Execute this bounded plan task by task using `superpowers:executing-plans`. The coordinator already authorized execution; no extra approval pause is required.

**Goal:** Provide a clearly labeled fixture-only read-only Workshop demo without purchases or grants, and update the configured Inception default to the verified current mercury-3 model.

**Architecture:** Branch at the browser entry before loading the normal Workshop module. Serve a repository-authored fixture from a separate module using existing markup, with all interaction in browser memory. Separately update the existing Inception client defaults/request shape and Compose defaults without changing provider identity or historical metadata.

**Tech Stack:** Plain ES modules/HTML/CSS, Go embedded assets, Python urllib JSON client, Docker Compose.

**Spec:** `docs/architecture/workshop-readonly-demo.md`.

## Global constraints

- Fixture-only demo; no licensed source or canonical content exposure, fake grants, API writes, Stripe, model calls or entitlement bypass.
- Explicit `/workshop/?demo=1` opt-in with persistent demo/provenance labels and illustrative $20 USD price; purchase and sign-in disabled.
- No new credentials, secret values, production data or database migrations.
- `mercury-3` is the verified current model; older listed models are not described as deprecated. Preserve explicit model overrides.
- Preserve current normal Workshop behavior outside demo mode.
- No deployment, merge or paid acceptance claim follows from this checkpoint.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Start source: `fa6ed0f219e6c3f558079247d5ac4e930c275127`.

## Concrete todo

- [ ] Implement an explicit fixture-only Workshop demo entry with a fictional vehicle, article search/reader/back navigation, an illustrative $20 USD quote and persistent sample-content labeling; load no live application/auth/commerce modules in demo mode.
- [ ] Keep demo purchase/sign-in/library mutations disabled and make zero catalog, auth, commerce, preparation, ingestion or model requests; preserve paid routes, grants and production authentication.
- [ ] Update Inception model defaults to mercury-3 and make its request temperature/token fields compatible while retaining explicit INCEPTION_MODEL overrides and historical Mercury-2 metadata.
- [ ] Run focused client/Go/Python regressions and browser verification proving demo navigation and no live API requests; record exact candidate evidence, commit/push coherent milestones and synchronize Issue186/Project8.

## Task 1: Static, isolated demonstration

**Files:** Modify `apps/api-go/workshop/index.html`; create `apps/api-go/workshop/bootstrap.mjs`, `apps/api-go/workshop/demo.mjs`, and `apps/api-go/workshop-demo.test.mjs`; modify `apps/api-go/workshop/styles.css` only if labels require layout. Extend `apps/api-go/workshop_test.go` if its existing asset test must cover new modules. Update canonical documentation with verification evidence.

**Interfaces:** `bootstrap.mjs` reads `new URLSearchParams(location.search).get("demo") === "1"`; dynamically imports `./demo.mjs` when true and `./app.mjs` otherwise. `index.html` points its module script to bootstrap. The demo module imports no normal application/auth/commerce modules. Its immutable sample data and DOM event handlers live together.

- [ ] Add focused module/bootstrap checks proving only the requested branch loads and that demo does not reference fetch, normal app, auth or commerce modules. Add interactive browser acceptance covering selector progression, search, reader/back, visible demo label, disabled controls and recorded network requests.
- [ ] Implement the bootstrap branch, then populate existing `year`, `make`, `model`, `configuration`, `articles` and reader elements from one fictional sample. Reset dependent selector values on parent change. Show the catalog after selection, filter article titles using `textContent`/DOM nodes, open reader and return with `back`/Browse; no `innerHTML` interpolation. Use a non-service informational sample with clear provenance from the spec.
- [ ] Set banner and sample provenance visibly; show illustrative $20 USD quote and disabled purchase/sign-in. Hide order-check/library/account flows and normal welcome copy where it misrepresents demo. Ensure no enabled control invokes live application modules. Keep sample article reference panel explicitly illustrative; do not display a provider source link.
- [ ] Run `node --test workshop-demo.test.mjs workshop-client.test.mjs` in `apps/api-go`; run `go test ./...` there. Verify the live/static browser with `?demo=1`: selector/search/read/back work, labels remain visible, purchase/sign-in disabled, and requests contain only static assets (zero `/auth`, `/v1`, Stripe or provider requests). Verify normal `/workshop/` still loads normal bootstrap path. Commit and push this coherent milestone.

## Task 2: Current model default and compatible requests

**Files:** Modify `workers/ingestion-python/src/autodata_ingestion/mercury2.py`, `workers/ingestion-python/tests/test_mercury2.py`, `infra/compose/compose.yaml`, `docker-compose.base44.yml`. Only expand to `infra/deploy/gce/test_host_runtime.py` if its default expectation changes; do not rewrite historical generation/extraction-mode strings.

**Interfaces:** Keep `Mercury2Client`, its constructor parameters, `INCEPTION_MODEL`, `INCEPTION_MAX_TOKENS`, completion endpoint and response parser. New default model is `mercury-3`; constructor empty-model fallback agrees. For model names `mercury-3` (and an explicitly versioned `mercury-3-...` if present), send `temperature: 0.5` and `max_completion_tokens: self._max_tokens`; otherwise retain the previous temperature/token request fields.

- [ ] Update default transport tests to expect `model == "mercury-3"`, `temperature == 0.5`, `max_completion_tokens == 8192` with no `max_tokens`; verify environment output budget 2048 uses the same field. Add explicit `INCEPTION_MODEL=mercury-2` test preserving `temperature == 0` and `max_tokens` while credentials stay in environment. Run tests before implementation and retain the observed failure.
- [ ] Change only constructor/empty/environment defaults, model-conditional request fields, and three Compose model defaults. Retain other response limits, validation, secrets and explicit override paths.
- [ ] Run `PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_mercury2.py`; run related source/rewrite/lifecycle tests selected by existing suite and Compose config parsing without printing resolved secrets. Commit and push the model milestone.

## Task 3: Exact evidence and handoff

- [ ] Run `git diff --check`; record exact implementation SHA, focused checks, browser screenshot/network proof, any environment limitations and absence of provider/model requests in demo in the canonical document. Update Issue186 comment and Project8 demo field with the same evidence/todos.
- [ ] Review the exact candidate changes for the fixture isolation, normal-bootstrap regression and secret handling. The coordinator owns integration/PR/deployment decisions. Supply the demo URL path and completed verification without claiming payment or licensed article acceptance.

## Gate and synchronization

This docs-only checkpoint updates the same goal/todos in Issue186, its Project8 item, this plan and the canonical architecture document. The machine record is `docs/agents/records/2026-11-06-workshop-readonly-demo.json`. Commit/push this checkpoint before implementation and run:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-06-workshop-readonly-demo.json --base-sha FULL_CHECKPOINT_SHA
```

Only exit 0 with `{"status":"synchronized","errors":[]}` authorizes the implementation boundary. Preserve existing Issue body and Project indices; add a bounded comment and dedicated demo reference field instead of truncating historical tracking.
