# Vehicle Workspace: Chat, Source Fallback, and Procedure Compilation

## Purpose and tracked scope

After a user selects an engine/base configuration, the dashboard opens a
vehicle-bound repair workspace. The workspace has a natural-language chatbox
and a bounded agent-terminal view. The chat request is handled by the existing
cache-first worker path; it does not call a provider directly from the
browser.

Tracked delivery: [Issue #108](https://github.com/lucronn/autodata/issues/108),
[Project #8](https://github.com/users/lucronn/projects/8), and the
[implementation plan](../superpowers/plans/2026-09-18-dashboard-agent-workspace.md).

## User flow

1. The selector starts at the decade row and replaces that row with years,
   makes, models, and engine/base configurations as each choice is made.
2. A Back control is available whenever the user is below the decade row. It
   clears the current level and all dependent levels while preserving the
   previously loaded catalog in memory. Browser history is not required for
   this local selector.
3. Selecting an engine/base configuration displays the selected vehicle and
   opens the workspace beside it. The workspace contains a chat transcript,
   a request box, a send action, and an agent terminal.
4. The request box accepts natural language such as “oil pump and water pump
   replacement procedure and quote”. The selected vehicle is sent as a
   structured request context as well as being shown to the user.
5. The default response is a concise consumer-facing answer. A Markdown
   procedure is available in the response as a structured field and can be
   viewed without exposing worker internals. The terminal shows stage names,
   source/provider summaries, article names, retries, and publication state;
   it does not stream full procedure text.

## Request and processing contract

The dashboard calls `POST /chat/queries` with an idempotency key and a body of
the form:

```json
{
  "message": "oil pump and water pump replacement procedure and quote",
  "request_params": {
    "vehicle": {
      "year": 1999,
      "make": "Chevrolet",
      "model": "Silverado 1500",
      "configuration_key": "1999-chevrolet-silverado-1500-5.3l-2wd",
      "vehicle_id": "canonical-vehicle-id",
      "vehicle_configuration_id": "canonical-configuration-id"
    }
  }
}
```

The worker must bind the request to the supplied canonical configuration before
interpreting the job. It follows this order:

```text
chat request
  -> canonical vehicle/configuration binding
  -> normalized article and derived-procedure lookup
  -> cache hit: return persisted normalized/derived data
  -> cache miss: call the bounded AutoAPItwo adapter
  -> persist source snapshot and normalized article records
  -> select component procedures and calculate overlap-aware labor
  -> compile the procedure into a new derived article identity
  -> persist an immutable Markdown revision with lineage and evidence
  -> publish answer and bounded progress events
```

AutoAPItwo (`autoapitwo.vercel.app`) is the primary fallback source through the
existing provider connector. Other source adapters remain possible. Every
provider response is persisted as a source snapshot or normalized cache entry
before it is used for a later lookup. Repeated requests use the normalized
cache and derived-article identity rather than re-calling the provider.

The request, source retrieval, normalization, composition, and publication
stages are idempotent. Their idempotency key includes the selected vehicle,
request fingerprint, source snapshot, processing version, and lane. Transient
failures retry with bounded backoff and then enter the existing dead-letter
path. A failure must not discard a prior published revision.

## Procedure compilation and storage

The worker keeps individual source articles separate and uses their canonical
article identities as lineage inputs. The compiler merges overlapping setup,
access, drain/refill, inspection, and cleanup steps. It sums labor only for
independent work and records overlap deductions in the labor breakdown. It
does not invent vehicle facts or silently resolve an ambiguous source match.

The compiled result receives a deterministic derived identity scoped to the
vehicle, requested component set, and procedure version. It is stored in the
existing `derived_articles`, `derived_article_revisions`, and
`derived_article_lineage` tables. The revision `body` is Markdown, while the
structured `steps`, `labor`, `images`, `provenance`, and evidence references
remain queryable JSON. Published revisions are immutable; a new source result,
correction, or compiler version creates a new revision and changelog entry.

Minimum Markdown sections are:

```markdown
# <consumer-facing procedure title>
## Vehicle
## Quote
## What this includes
## Procedure
## Safety and notes
## Sources and review status
```

The public response exposes the Markdown field and the structured procedure.
The terminal only reports bounded summaries such as “cache miss”, “AutoAPItwo
article list retrieved (12)”, “normalized 4 articles”, “merged 3 overlapping
setup steps”, and “published derived revision”.

## Progress and failure behavior

The dashboard consumes the existing chat event stream and polls the durable
query state as a fallback. Events are redacted and limited to an allow-listed
stage/message shape. The UI retains a bounded terminal history and marks the
request as complete, failed, retrying, or dead-lettered.

- Cache hit: report the normalized/derived article identity and render it
  immediately.
- Source miss: report the provider call and ingestion stages; render a
  provisional source-backed result when available while normalization runs.
- Partial enrichment failure: keep the last viewable revision and label the
  affected section or source as unreviewed/failed.
- Invalid or missing selected vehicle: refuse the request with an actionable
  error rather than making an unscoped provider call.
- Duplicate request or retried webhook: return the existing durable query and
  do not create duplicate source snapshots or derived revisions.

All evidence references remain linked to their source article or extraction
record. The workspace may show a short evidence count and source names; full
evidence remains available from the detailed result view.

## Security and operational boundaries

Provider credentials stay server-side in environment or secret-manager
interfaces. The browser receives neither credentials nor unrestricted provider
URLs. The Go API remains the authentication and authorization boundary.
Worker terminal messages must redact tokens, cookies, signed URLs, raw source
payloads, and full procedure bodies. The workspace is a read path plus the
existing authenticated chat command path; it does not grant new entitlement
scope.

## Verification contract

The delivery must include focused unit/contract tests for back navigation,
vehicle-context binding, cache-first source fallback, Markdown persistence, and
bounded progress rendering. The local browser test must select a real
decade/year/make/model/engine-base path, press Back, reselect the configuration,
submit a natural-language job, and observe both the chat response and terminal
progress. The exact implementation SHA, CI run, and browser result are recorded
in the plan and Issue #108 after verification.

## Verified delivery

Implementation commit `7319e6c95c6e657d4620d987c46ed1bb141b0971` was verified
locally on `phobos/fix-chat-source-failure`. The rebuilt browser flow reached a
1999 Chevrolet Silverado 1500 5.3L 2WD workspace, exercised Back navigation,
submitted a multi-component request, showed the AutoAPItwo ingestion summary in
the worker terminal, and rendered an available Markdown procedure. The local
Go and Python suites, JavaScript syntax check, and whitespace check passed.

## Mercury-2 overlap-aware composition

Multi-component procedure generation is a separate reasoning step after the
source articles have been normalized. The worker sends Mercury-2 the selected
vehicle, every selected article's source-authored procedure, labor operation
IDs, evidence records, and prepared image metadata. Mercury-2 must identify
shared access, drain/refill, inspection, cleanup, and other overlap work;
represent each shared operation once; and order disassembly, component work,
reassembly, refill/bleed, adjustment, and final verification by dependency.

The application remains authoritative for labor arithmetic, vehicle identity,
source/evidence bindings, image bytes, and publication. Unknown labor hours do
not prevent the combined procedure from being generated. An invalid or failed
Mercury-2 response falls back to the deterministic source-bound procedure and
marks the result for review rather than hiding a usable answer. The detailed
prompt, response schema, and validation rules are canonical in
`docs/architecture/mercury2-procedure-composition.md` and tracked by
[Issue #110](https://github.com/lucronn/autodata/issues/110).
