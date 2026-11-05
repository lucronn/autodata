# Mercury-2 Output Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound every Mercury-2 completion request so the existing OpenRouter route can perform canonical article rewrites without an unaffordable 50,000-token reservation.

**Architecture:** Keep the existing OpenAI-compatible `Mercury2Client` and its official Inception default endpoint. Add a positive, bounded output-token setting to the client and include `max_tokens` in the JSON request. Operators may select the exact Inception-compatible endpoint and model through existing environment settings; credentials stay outside the repository.

**Tech Stack:** Python, `urllib.request`, pytest, the ingestion worker's existing Mercury-2 client.

**Spec:** `docs/architecture/normalized-article-document.md`

**Tracking:** [Issue #327](https://github.com/lucronn/autodata/issues/327); [Project #8](https://github.com/users/lucronn/projects/8). Parent release: [Issue #186](https://github.com/lucronn/autodata/issues/186).

## Global Constraints

- The default official Inception endpoint and `mercury-2` model remain unchanged.
- Default `max_tokens` is 8192; `INCEPTION_MAX_TOKENS` may override it only with an integer from 1 through 32768.
- No credential value enters source control, test output, GitHub, or documentation.
- This change only bounds the request; it does not bypass terminal transformation ownership, provider request limits, source-rights checks, or the atomic publication gate.
- Full live publication acceptance remains separately required before production release.

---

### Task 1: Bound Mercury-2 completion requests

**Files:**
- Modify: `workers/ingestion-python/src/autodata_ingestion/mercury2.py`
- Test: `workers/ingestion-python/tests/test_mercury2.py`
- Modify: `docs/architecture/normalized-article-document.md`

**Interfaces:**
- Consumes: `Mercury2Client.from_environment()` and `complete_json(prompt)`.
- Produces: `Mercury2Client(..., max_tokens=8192)` and `INCEPTION_MAX_TOKENS` environment override.

- [ ] **Step 1: Write a failing request-payload test.** Capture the `Request` passed to the existing fake transport; assert that its JSON body contains `max_tokens: 8192` by default and that `INCEPTION_MAX_TOKENS=2048` yields `2048`. Assert invalid values `0`, `32769`, and `abc` raise `ValueError` before transport.
- [ ] **Step 2: Run the focused tests and observe the expected failure.** Run `PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_mercury2.py -q`.
- [ ] **Step 3: Implement the minimal client change.** Parse the environment value as an integer, validate `1 <= max_tokens <= 32768`, and include it in `complete_json`'s JSON body. Keep all other request fields and response parsing unchanged.
- [ ] **Step 4: Run focused and worker tests.** Run the focused command above and `PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests -q`; review `git diff --check`.
- [ ] **Step 5: Update the canonical architecture note and commit.** Document the goal, tracking references, bounded setting, and remaining live-acceptance todo. Commit the focused milestone and push the feature branch.

## Concrete todo

- [ ] Record synchronized Issue/Project/document checkpoint and pass exact-base preflight before implementation.
- [ ] Add the failing request-payload and invalid-setting tests.
- [ ] Bound the client request, run focused and worker verification, and push the reviewed change.
- [ ] Verify a real bounded Mercury-2 call in isolated TEST; then separately resolve connector limits and terminal job recovery before claiming canonical publication.
