# Mercury document-only introduction prompt contract proposal

Status: **draft, tracking unsynchronized; implementation blocked**.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-05-mercury-context-introduction.md`
Record: `docs/agents/records/2026-11-05-mercury-context-introduction.json`

Goal: Prevent context-only facts in full-prose introductions while preserving one durable canonical rewrite, independent exact-hash review and source fallback.

## Evidence and cause

Inspected source `5106c97c42fd62837be67cbd49f02c940c811137` is the hotfix documentation checkpoint based on merged full-prose implementation `d123bbf3098d87bd75d234b409039ca25a8f0d3e`. Safe retained run2 receipt `/tmp/autodata-private-full-prose-canary-20261105-run2.json`, SHA256 `c3ba45fe1df3213076f6fae81bbc9e5519359d3d6b123d7d18d0002480fc8e8a`, records one Mercury request, HTTP200/finish stop, `REWRITE_TECHNICAL_MUTATION`, no review or publication and null canonical pointer. The coordinator's separately inspected response diagnoses context-only vehicle tokens in the introduction while all nine body leaves passed. This planner verified the safe receipt only; it did not access private raw prose or the database and does not independently assert the nine-leaf inspection.

`build_full_prompt` supplies both `document` and `context`; its existing source-bound instruction does not explicitly distinguish those inputs. `_check_introduction` correctly accepts technical tokens only from strings inside `document`. The validator is therefore retained exactly. A prompt correction can reduce recurrence but cannot guarantee provider compliance or semantic correctness.

## Decision

In `procedure_rewrite_full.py` add `PROMPT_VERSION = "full-prose-prompt-v2"` and a `prompt_version` prompt member. Add `introduction_allowed_technical_tokens`, computed deterministically as `sorted({token for leaf in _strings(document) for token in _technical_tokens(leaf)})`. This duplicates the existing validator's source-membership definition in the prompt payload without changing validation. Use exact rule text:

> For the introduction, document is the only source of facts. Context is routing metadata, not source evidence. Do not introduce vehicle years, makes, models, engines, applicability, tools, components, conditions or values that occur only in context. Every introduction technical token must match an entry in introduction_allowed_technical_tokens verbatim; omit unsupported details and write a concise document-supported introduction.

Keep all existing prompt rules, context payload, response schema and size limits. Keep `PROFILE = full-prose-review-v1`, `VALIDATOR_VERSION = full-prose-validator-v1` and `TOKEN_GRAMMAR_VERSION = literal-technical-tokens-v1`. The new prompt marker and existing SHA256 prompt hash distinguish changed prompt bytes; there is no new transformation identity, forced refresh, retry reset or automatic rewrite of completed articles. No token grammar, renderer, validator, store, worker, publication, CLI, API, database or runtime configuration changes.

The allowable introduction token list is explanatory model input; validation remains authoritative. Unknown numeric notation still rejects/retains under existing rules. Every changed/retained leaf and introduction still requires independent human technical review; source remains selected until exact-bound approval and atomic publication. One durable canonical rewrite per existing identity remains the goal.

## Exact prospective implementation allowlist

- `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite_full.py`: only prompt version constant and `build_full_prompt` payload/rule additions.
- `workers/ingestion-python/tests/test_procedure_rewrite_full.py`: synthetic prompt and unchanged-validator regressions.

Changes to `_check_introduction`, `_check_text`, token regex/constants, render/validate functions or any other implementation file are outside this proposal. Preserve all failed attempts and receipts. Correcting a saved failed draft with human review, rearming the existing job or making another provider call requires a separate coordinator dispatch that preserves budget and provenance.

## Tracking handoff

Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` currently has Task67/68/69 in Source or dependency reference and the concurrent release hotfix link in Release hotfix reference. No field was changed. Coordinator must serialize a preservation-safe amendment, read back current Issue body/comments and Project fields, retain predecessor values, then synchronize this exact goal/todo/allowlist/documents. Set record `status: synchronized` only after actual verification, commit/push docs and run machine preflight at that exact checkpoint SHA. This draft does not pass the gate or authorize implementation.

Concrete todo:
- [ ] Preserve current Issue186 body/comments and all Project8 fields; synchronize this exact goal, plan, canonical spec, two-file allowlist and concrete todo under a coordinator-owned serialized tracking update, then commit/push the checkpoint and pass exact-SHA preflight.
- [ ] Add red prompt-contract regressions for normalized-document-only introduction support, context-only vehicle tokens, deterministic token enumeration and explicit prompt version; preserve the existing rejecting validator.
- [ ] Change only full-prose prompt construction: version its prompt bytes, disclose document-derived allowable introduction tokens and explicitly exclude context-only facts; retain all profile, grammar, validator, limits, response and lifecycle contracts.
- [ ] Run no-network synthetic full-prose and ordered-rewrite suites, verify no validator or unrelated code change, commit/push the coherent correction and obtain independent exact-SHA review.
- [ ] Only after separately authorized coordinator runtime work: retain failed canary receipts and attempt budget, run a bounded authentic canary on the reviewed candidate, independently review its complete content and publish at most one exact-bound canonical revision; otherwise retain source fallback.
