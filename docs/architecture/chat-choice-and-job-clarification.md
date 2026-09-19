# Chat Choices and Job Clarification Contract

**Status:** normative dashboard and chat behavior
**Issue:** https://github.com/lucronn/autodata/issues/109
**Project:** https://github.com/users/lucronn/projects/8
**Plan:** `docs/superpowers/plans/2026-09-19-chat-choice-and-fluid-clarification.md`

## Goal

The repair workspace must make every required choice actionable and must preserve the vehicle configuration selected before the chat starts. A user must see the available options before being asked to choose one. A job request must be interpreted against the selected vehicle, not reinterpreted as a new vehicle because a component name resembles a model or configuration phrase.

## Choice contract

When chat intent resolution has more than one compatible vehicle or configuration, the query response has `status: "awaiting_vehicle"` and includes `vehicle_options` at the top level. Each option is an object with:

- `option_number`: positive, stable number shown to the user;
- `label`: complete human-readable vehicle/configuration label;
- `clickable: true`;
- `vehicle_id` or `candidate_key`: provider-independent selection identity; and
- `selection`: the exact payload accepted by `POST /chat/queries/{query_id}/selections`.

The dashboard renders a visible choice prompt and one keyboard-accessible button per option. The button label includes the number and the complete option label. A user may also type the number, but the numbered text is not a substitute for rendering the choices. Clicking a button submits the option's selection payload to the existing query selection endpoint and resumes that query; it does not create a second query.

The same rendering rule applies to any future structured choice collection returned in an answer. A clarification without its available options is an invalid user-facing response. If no options are available, the response must state that resolution is unavailable and must not ask the user to choose an invisible option.

## Selected workspace vehicle is authoritative

The vehicle object sent in `request_params.vehicle` is the result of an explicit year, make, model, and engine/base selection. It is authoritative for that chat request. The chat parser may interpret the free-text job, requested operations, quote intent, and procedure intent, but it must not downgrade the supplied vehicle to `ambiguous`, `unmatched`, or `needs_review` based on words in the job.

The worker binds the selected vehicle to the intent with `status: "matched"`, preserving its internal and provider mappings, and then parses operations. This makes `oil and water pump procedure` a pump procedure for the selected vehicle rather than a new vehicle/configuration question.

## Fluid clarification boundary

Pump replacement is a component operation. `oil pump` and `water pump` identify components; they do not, by themselves, request an oil, coolant, or other fluid specification. The chat flow must not ask for fluid type merely because those component names contain `oil` or because source content mentions preparation fluids.

A fluid choice is permitted only when the requested operation explicitly needs a fluid decision, such as fluid replacement, flush, bleed, fill, or a source-backed fluid specification with multiple compatible alternatives. When such a choice is required, the response must include the available source-backed fluid options and preserve the selected vehicle context.

The system must never invent a fluid type to avoid a clarification. If a pump procedure has source-backed fluid requirements, they are displayed as a procedure requirement or warning unless the requested job explicitly asks for fluid replacement or the source contract requires a choice for safe completion.

## Query lifecycle

1. The dashboard submits one query with the selected vehicle context and an idempotency key.
2. The backend returns `awaiting_vehicle` plus `vehicle_options` when a choice is necessary, without starting source retrieval.
3. The dashboard renders the options immediately and keeps the query pending.
4. A click submits the option to the selection endpoint. The server validates that the option belongs to the query, clears the pending options, and starts the original query once.
5. A context-bound job proceeds through normalized cache, source retrieval, normalization, and composition without a vehicle clarification caused by job wording.
6. The worker terminal reports the same query and selected vehicle throughout the lifecycle.

## Error and accessibility behavior

- Missing or malformed options are treated as a server contract error and shown as an actionable retry/error state, not as an empty choice prompt.
- A repeated click or replayed selection is idempotent; it returns the current query rather than starting duplicate work.
- A selection for another query or an unavailable option is rejected without changing the query.
- Choice buttons use native `button` elements, visible focus styles, and labels that contain both number and option text.
- The result view may remain hidden while a query is awaiting a choice. It must not claim that a result is ready before the query reaches a terminal result state.

## Verified delivery

- Implementation: `6e96f491df7172595217227efdb9456c2ab56ff4`.
- Python worker suite: `423 passed, 3 skipped, 12 subtests passed`.
- Go API suite: `go test ./...` passed.
- Dashboard JavaScript syntax and `git diff --check` passed.
- Browser: `http://127.0.0.1:8080/dashboard/?fresh=final`; selected `1997 Toyota Rav4`, submitted `oil and water pump procedure`, received an available source-backed procedure, and saw no fluid or second-configuration question.
- Choice contract: live API resolution returned four visible candidate options for an unbound `1997 Toyota RAV4 brake line procedure`; selecting option 1 returned the same query in `processing` with `vehicle_options: []` and the selected vehicle bound.
- Compose services were rebuilt and restarted from the implementation commit. [GitHub Actions run 35425663865](https://github.com/lucronn/autodata/actions/runs/35425663865) passed, including the live Compose fast-lane smoke.
