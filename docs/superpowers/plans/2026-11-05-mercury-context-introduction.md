# Mercury document-only introduction Implementation Plan

> **For agentic workers:** Execute inline with superpowers:executing-plans only after a synchronized committed checkpoint passes exact-SHA preflight and coordinator dispatch. This worker plans only.

**Goal:** Prevent context-only facts in full-prose introductions while preserving one durable canonical rewrite, independent exact-hash review and source fallback.

**Architecture:** Clarify the existing full-prose prompt boundary with document-only evidence and a deterministic source-token list. Keep the rejecting mechanical validator, persisted identity, exact-hash human approval and source fallback unchanged.

**Tech Stack:** Python, JSON, pytest; no network/model/database calls for implementation verification.

**Spec:** `docs/agents/specs/2026-11-05-mercury-context-introduction.md`

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Record: `docs/agents/records/2026-11-05-mercury-context-introduction.json`
Source base: `5106c97c42fd62837be67cbd49f02c940c811137`.
Status: draft_unsynchronized; machine gate deliberately not claimed.

## Global constraints

Only the two implementation files listed in the spec may change after a passing checkpoint. All validator/profile/grammar/response/limits/lifecycle behavior remains fixed. No provider requests, DB mutations, automatic retry or publication. This docs branch carries the hotfix planning checkpoint in ancestry; do not open a master-targeted prompt PR including its unrelated documentation. Coordinator must select the reviewed integration base and preserve/rebase this docs-only proposal before synchronization; any changed checkpoint requires fresh preflight. Never reset the shared hotfix branch or cherry-pick its implementation implicitly.

## Concrete todo

- [ ] Preserve current Issue186 body/comments and all Project8 fields; synchronize this exact goal, plan, canonical spec, two-file allowlist and concrete todo under a coordinator-owned serialized tracking update, then commit/push the checkpoint and pass exact-SHA preflight.
- [ ] Add red prompt-contract regressions for normalized-document-only introduction support, context-only vehicle tokens, deterministic token enumeration and explicit prompt version; preserve the existing rejecting validator.
- [ ] Change only full-prose prompt construction: version its prompt bytes, disclose document-derived allowable introduction tokens and explicitly exclude context-only facts; retain all profile, grammar, validator, limits, response and lifecycle contracts.
- [ ] Run no-network synthetic full-prose and ordered-rewrite suites, verify no validator or unrelated code change, commit/push the coherent correction and obtain independent exact-SHA review.
- [ ] Only after separately authorized coordinator runtime work: retain failed canary receipts and attempt budget, run a bounded authentic canary on the reviewed candidate, independently review its complete content and publish at most one exact-bound canonical revision; otherwise retain source fallback.

## Task 1: Pin prompt contract and unchanged rejection

Files: the exact two-path spec allowlist. Consumes `build_full_prompt(document, *, context) -> str`; returns the same JSON prompt interface with two extra metadata/input members. Add the following synthetic tests to the existing full-prose test module, importing `build_full_prompt`, `_technical_tokens`, `_strings`, `render_full` locally. Existing fixture helpers `document`/`response` are reused.

```python
def test_introduction_prompt_limits_facts_to_document_not_vehicle_context():
    from autodata_ingestion.procedure_rewrite_full import build_full_prompt
    source = document("Tighten the bolts to 25 Nm using tool T-42.")
    context = {"vehicle": "2012 Audi A3", "engine": "CTX-99"}
    prompt = json.loads(build_full_prompt(source, context=context))
    assert prompt["prompt_version"] == "full-prose-prompt-v2"
    assert prompt["introduction_allowed_technical_tokens"] == ["25 Nm", "T-42"]
    assert prompt["context"] == context
    assert prompt["document"] == source
    rules = " ".join(prompt["rules"])
    assert "document is the only source of facts" in rules
    assert "Context is routing metadata, not source evidence" in rules
    assert "occur only in context" in rules
    assert "introduction_allowed_technical_tokens" in rules


def test_context_only_introduction_still_rejects_and_source_supported_intro_passes():
    from autodata_ingestion.procedure_rewrite_full import render_full
    source = document("Remove the cover.")
    payload = response("Take the cover off.", introduction="Access to the cover on the 2012 Audi A3.")
    with pytest.raises(ValueError, match="REWRITE_TECHNICAL_MUTATION"):
        render_full(source, payload)
    payload["introduction"] = "This article describes removing the cover."
    candidate = render_full(source, payload)
    assert rewrite.validate_article_rewrite(source, candidate, profile_version=PROFILE).passed


def test_introduction_token_payload_matches_all_document_strings_deterministically():
    from autodata_ingestion.procedure_rewrite_full import build_full_prompt, _strings, _technical_tokens
    source = document("Tighten to 25 Nm.", "Use tool T-42.")
    source["title"] = "Tool T-42"
    before = deepcopy(source)
    first = build_full_prompt(source, context={"vehicle": "CTX-99"})
    assert first == build_full_prompt(source, context={"vehicle": "CTX-99"})
    assert json.loads(first)["introduction_allowed_technical_tokens"] == sorted(
        {token for leaf in _strings(source) for token in _technical_tokens(leaf)})
    assert source == before
```

- [ ] Run the focused tests before patch; expect missing prompt metadata/token-list failures, with existing mutation rejection already green.
- [ ] Add only the specified constant/payload fields and rule. Do not adjust the validator to make a provider response pass.
- [ ] Run the focused tests and complete pure command below. Verify exact diff scope and unchanged validator functions. Commit `fix: bind full-prose introductions to document evidence` and promptly push the assigned branch.

```sh
PYTHONPATH=workers/ingestion-python/src /tmp/autodata-mercury2-token-budget-venv/bin/python -m pytest workers/ingestion-python/tests/test_procedure_rewrite_full.py workers/ingestion-python/tests/test_procedure_rewrite.py workers/ingestion-python/tests/test_procedure_rewrite_v2.py workers/ingestion-python/tests/test_article_lifecycle_types.py -q
git diff --check
```

The existing venv is local convenience, not a new dependency; use the assigned Python environment with pytest if unavailable. This suite uses synthetic clients, performs no provider calls, and earns no authentic content acceptance. Current pre-change full-prose baseline: **92 passed in 0.17s** at source5106c97. No proposed test has been added or run yet.

## Task 2: Exact review and bounded runtime handoff

- [ ] Independent review checks exactly two changed code files and unchanged token grammar, renderer, validators, lifecycle/profile constants and publication requirement. Verify existing source-fallback failure tests remain green.
- [ ] Coordinator separately decides whether to correct/review the retained draft or authorize a bounded fresh authentic attempt against the reviewed prompt; preserve original failed attempt/raw response and remaining retry budget. Neither this plan nor passing pure tests authorizes such an operation.
- [ ] Any authentic result receives complete independent technical review, including all nine body leaves and introduction; machine acceptance alone cannot publish or prove uniqueness. Preserve one canonical identity, source fallback while unapproved, and zero new model/source calls on warm reads under the existing verified lifecycle.
