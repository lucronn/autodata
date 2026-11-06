# Mercury3 Bounded Rewrite Reliability

Status: synchronized planning only; no implementation or runtime execution authorized before exact-base preflight and coordinator dispatch.

Goal: Make Mercury3 article rewriting use the documented instant reasoning mode within the existing one-attempt and 32768-token limits, without replaying spent jobs.

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8, dedicated `Mercury3 reliability reference` field. Plan `docs/superpowers/plans/2026-11-06-mercury3-instant-reliability.md`; canonical `docs/verification/2026-11-06-mercury3-instant-reliability.md`; record `docs/agents/records/2026-11-06-mercury3-instant-reliability.json`.

## Concrete todo record

- [ ] Add reasoning_effort=instant only to Mercury3/current-version request payloads; preserve legacy model payloads, JSON response format, temperature, output cap, timeout and existing failure guards.
- [ ] Add transport-boundary tests proving explicit Mercury3 instant reasoning, unchanged legacy payloads and fail-closed length responses with no automatic retry; run focused and required repository checks.
- [ ] Document exact failure evidence and provider contract, preserve complete_rewrite metadata semantics and all historical jobs/reports; commit and independently review the minimal change before merge.
- [ ] Keep worker disabled and two spent jobs/reservations unchanged; require separate synchronized rollout and fresh authentic unseen Banktwo identity proof after reviewed CI/merge, with no retry/reset/replay or new budget.

## Evidence and smallest change

The exact live Banktwo job `e536239d-4425-4c24-a8cf-43d5bd34af5b` failed once with public `REWRITE_RESPONSE_INVALID`, checkpoint `MERCURY_OUTPUT_TRUNCATED`, finish_reason=length, configured max_completion_tokens32768. Read-only receipt `rewrite-readonly-diagnostics.json` under `/var/lib/autodata/new-article-worker-evidence/two-bank-enqueue-review/` SHA256 `0e4c48c7707d6657b245fa88e2fbd18cdd916f78b9ece42edbbfbadc699328df` reports HTTP200, completion_tokens32098 but only3 visible content bytes, 52 source blocks and zero editable prose leaves. Hidden reasoning exhaustion is a strong indication, not a proven token breakdown. Do not rerun this identity. Worker was disabled/stopped with exactly2 consumed reservations (`failure-stop.json` SHA256 `cb595dfc9f53373fa6d803fc5e1b3efed93e4c5ddfe2601cf4b907b0da0022e9`).

Official provider contract read publicly on2026-11-06: https://docs.inceptionlabs.ai/capabilities/reasoning-efforts.md supports `instant`, `low`, `medium`, `high` and states Mercury3 omitted reasoning defaults to low. https://docs.inceptionlabs.ai/api-reference/chat/create-a-chat-completion.md defines max_completion_tokens as including visible and reasoning tokens and supports instant reasoning. Specify `reasoning_effort: "instant"` in the existing Mercury3-only generation options; preserve max_completion_tokens32768, temperature0.5 and JSON object mode. Do not raise the token cap, use legacy max_tokens, change prompts, add retries, or add deterministic transformation/persistence paths. Legacy Mercury2 options remain unchanged. This bounded change may improve output reliability; it does not guarantee every article will publish.

Bankone's prior `complete_rewrite=false` is hardcoded automatic-validator metadata, not proof of retained prose: independent read-only comparison found20/20 ordinary prose leaves changed. Keep flag/report/history semantics unchanged here; document its limitation without claiming semantic or human quality acceptance.

## Implementation allowlist and verification

Implementation allowlist: `workers/ingestion-python/src/autodata_ingestion/mercury2.py` and `workers/ingestion-python/tests/test_mercury2.py` only; the plan/canonical/record may receive evidence updates. No schema, lifecycle, store, worker, service, source connector, runtime env, prompt, validator or deployment changes.

Tests must inspect actual serialized request data for default, explicit and versioned Mercury3 and ensure reasoning_effort=instant, while legacy Mercury2 retains previous fields and receives no new reasoning option. Existing malformed/truncated-output guard tests must remain green, with meaningful assertion that length failure remains content-free, terminal and does not invoke another transport call. Run focused Mercury tests plus relevant existing automatic rewrite/worker tests and required CI. Record exact implementation SHA/results.

## Separate runtime proof boundary

This gate authorizes code implementation only after exact synchronized checkpoint and coordinator dispatch. No deployment, enable/start, identity creation, provider/model call, attempt reset or replay is authorized. Existing spent Bankone and Banktwo identities/jobs, two reservations, original rollout UUID/cutoff/expiry/max10, source fallback and receipts stay unchanged. A later reviewed/merged source may be activated only through a separate synchronized rollout gate. Any live proof must select at most one authentic previously unseen Banktwo descriptor from an exact persisted snapshot member, fence absence, preserve original budget/expiry and use one model attempt with bounded observation/disable-stop. If the finite rollout is expired or prerequisites fail, stop rather than recreate/reset it. No manufactured identity or substitute retry is permitted.

Tracking scope synchronized: https://github.com/lucronn/autodata/issues/186#issuecomment-6696809050; dedicated Project8 `Mercury3 reliability reference` (`PVTF_lAHOCSJ8cc4BiQ2Bzho5Ng0`). Exact committed pin/preflight required before implementation dispatch.
