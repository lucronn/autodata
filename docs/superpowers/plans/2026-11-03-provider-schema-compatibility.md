# Provider output schema compatibility repair

Issue: https://github.com/lucronn/autodata/issues/186  
Project: https://github.com/users/lucronn/projects/8

## Goal and observed failure

Make the checked-in v2 output schema acceptable to the real provider without
weakening deterministic duplicate-ID or evidence validation. The bounded CLI
experiment at `3634a59cea79dc3d36f1ec610b927ab74e6d166a` reached the API and
failed with HTTP 400 `invalid_json_schema`: `uniqueItems` is not permitted in
the provider response schema. Requested model/medium/Fast settings were retained;
effective runtime settings, writes, commits and later gates were not established.
The runner correctly retained the blocked architect response/command evidence.

The [official Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
was fetched on 2026-11-03. It specifies a subset of JSON Schema and lists
`minItems`/`maxItems` as supported array constraints. The actual API rejection is
the direct evidence for this repair. No model/tier fallback is authorized.

## Concrete todo

- [ ] Read the synchronized task record at the pinned base and pass preflight.
- [ ] Add a regression for the unsupported provider schema keyword and verify
  it fails before changing the schema. Check runtime duplicate rejection for
  provider evidence IDs, finding/assessment evidence IDs, command outputs,
  provenance eligible/covered IDs and required agent evidence IDs.
- [ ] Remove the eight `uniqueItems` declarations from the checked-in provider
  schema. Preserve field inventories, required fields, types, enums, constants,
  allowed properties and deterministic uniqueness validators. Do not introduce
  an alternate inline schema or a general schema interpreter.
- [ ] Run focused schema/response/provenance tests and the full autonomy suite.
  Obtain independent exact-SHA review before promoting the evaluator/schema
  checkpoint. The schema change cannot approve its own first provider run.
- [ ] Retry the bounded real fixture only after promotion with the unchanged
  exact profile, a fresh clean clone, a new evidence directory, and explicit
  time limits. Record subsequent provider incompatibilities or missing metadata
  as observed blocked outcomes; never manufacture a successful runtime event.

## Ownership

Only `scripts/autonomy/agent-output.schema.json` and
`scripts/autonomy/test_runner.py` may change in this repair. Coordinator-owned
documents and task records are updated separately. No policy, registry, runner,
orchestrator, release-controller, application or migration changes are allowed.
No live calls, GitHub mutations or deployment belong in implementation tests.
The implementation/review profile is Sol 6.1, medium reasoning, Fast/priority.
