# AutoData Data-Integrity and Quality Gates

## Gate expression

The release decision is:

```text
PASS iff
  every required decision = pass
  AND critical findings = 0
  AND high findings = 0
  AND evidence completeness = 1.0
  AND fast-lane provenance coverage = 1.0
  AND all required deterministic commands exit 0
  AND implementation SHA matches every report
```

No agent may lower a threshold because a source is difficult, an LLM is uncertain, or a test is inconvenient. A task that cannot satisfy the contract is `blocked`, `failed`, or `needs_review`.

## Fast-lane publication gates

Before a dataset becomes `viewable`, the system must prove:

- Vehicle identity is resolved to a canonical vehicle record.
- Source metadata and source watermark are present.
- Every product-declared core field is present, typed, unit-normalized, and applicable.
- Every published fact has source provenance.
- No unresolved referential-integrity error exists.
- No unverified unit conversion exists.
- No critical safety or source-rights finding exists.
- Duplicate request/event processing produces the same projection and revision result.

The initial policy requires 100% completeness for required fast-lane fields and 100% provenance coverage for fast-lane published facts.

## Deep-lane publication gates

Deep sections may be independently `pending`, `processing`, `complete`, `failed`, or `needs_review`. A failed deep section cannot invalidate a previously viewable revision.

A deep section may publish only when:

- Its source snapshot and extraction run are recorded.
- Each extracted fact has evidence or an explicit non-document source reference.
- Model/provider/version and confidence are recorded.
- Units and applicability pass validation.
- Duplicate and supersession checks pass.
- Critical safety findings are zero.
- The section revision has a changelog and source watermark.
- The publication event is emitted through the outbox exactly once.

## Source and provenance checks

The source agent verifies:

1. Source identity, URL or provider key, publisher, and retrieval timestamp.
2. License/terms metadata, attribution requirement, retention state, and takedown state.
3. Content hash and immutable object-storage reference.
4. Source drift against the previous snapshot.
5. Checkpoint and replay behavior for pagination, pages, and documents.
6. No publication from quarantined or unverified source material.

## Schema and migration checks

The schema agent verifies:

- Clean installation from zero migrations.
- Upgrade from the previous schema version.
- Foreign-key and uniqueness invariants.
- Immutable revision constraints.
- No destructive migration without an explicit compatibility strategy.
- API and event consumers remain compatible or are versioned together.
- Rollback or forward-recovery instructions exist for every migration.

## Quality dimensions

The data-quality agent reports each dimension separately:

| Dimension | Required evidence |
| --- | --- |
| Completeness | Required-field and section coverage |
| Correctness | Fixture/source comparisons and invariant checks |
| Consistency | Cross-table, taxonomy, unit, and applicability checks |
| Traceability | Fact-to-source/document/page/evidence coverage |
| Freshness | Source watermark and retrieval lag |
| Uniqueness | Duplicate and supersession detection |
| Safety | Critical warning and high-voltage/SRS review status |
| Reproducibility | Replay from content-addressed source snapshot |

## Review independence

The builder cannot author the final independent-review decision. The review agent receives the task contract, diff, test results, and source evidence, but not the builder's private reasoning. If two verifier agents disagree, the orchestrator retries with an alternate reviewer. Persistent disagreement blocks release.

## Evidence retention

Evidence references the exact implementation SHA and source hash. Reports must retain full reasons, not summaries that remove the failure context. A later run cannot overwrite an earlier run; it creates a new manifest linked by `correlation_id` and `retry_count`.
