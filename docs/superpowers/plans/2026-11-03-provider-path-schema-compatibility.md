# Provider path schema compatibility repair

Issue: https://github.com/lucronn/autodata/issues/186  
Project: https://github.com/users/lucronn/projects/8

## Goal and evidence

Make the provider-facing path fields compatible with Structured Outputs while
preserving deterministic path validation at every trusted-input and evidence
boundary. The isolated real CLI retry at
`e90047f2d50829ae0bcdc68c0dc8ed69c998cb4a` rejected regex lookaround in
`$defs.Finding.properties.path.pattern` with HTTP 400 `invalid_json_schema`.
The architect exited 1 after 3.43 seconds and no builder ran. Evidence is retained
in `/tmp/autodata-cli-e900-lw_pbv12/evidence/run`. The preceding `uniqueItems`
repair and runtime failure remain separately recorded.

## Concrete todo

- [ ] Pass committed-base planning preflight for this distinct remediation.
- [ ] Add a failing regression detecting unsupported regex lookaround anywhere
  in the provider schema, including unused definitions validated by the API.
- [ ] Remove only the seven lookaround `pattern` constraints from Finding.path,
  ArtifactRecord.ref, CommandRecord.cwd, Check.cwd, Output.relative_path,
  Provenance.population_ref and PreImplementation.plan_ref. Preserve all other
  fields, required sets, types, minimum lengths, enums and execution constants.
  Do not create a second schema, relax a runtime validator, or alter evaluator
  trust inputs beyond the explicitly scoped provider schema.
- [ ] Verify runtime rejection of absolute paths, parent traversal, backslashes,
  NULs, repeated separators and inappropriate dot paths at the actual finding,
  artifact, command/check/output, provenance, and planning boundaries. Valid
  relative paths and explicitly permitted root cwd/finding `.` must still work.
  Use existing public validation APIs and real temporary files where appropriate;
  direct tests of a duplicated regex are insufficient. For planning refs, use
  `load_trusted_inputs`: its `_blob` boundary invokes `safe_ref`, and architect
  contracts must exactly match those frozen validated inputs. `validate_contract`
  alone and the generic planning record helper are not that full safety boundary.
  Include real committed unusual filenames where needed so missing-file errors
  cannot accidentally stand in for path rejection. If an existing boundary
  is missing validation, report it to the coordinator for a separate scope
  checkpoint instead of editing runner/policy code under this assignment.
- [ ] Run focused tests and the full autonomy suite. Require independent
  exact-SHA review and coordinator verification before promoting the schema.
- [ ] Only after promotion, retry the unchanged bounded CLI fixture with a new
  clone/evidence directory, the explicit Sol 6.1 / medium / Fast profile, provider
  timeout 120 seconds and outer timeout 400 seconds. Preserve subsequent real
  failures. Missing effective runtime metadata is blocked, never inferred from
  model text or manufactured events.

## Ownership and verification boundary

Only `scripts/autonomy/agent-output.schema.json` and
`scripts/autonomy/test_runner.py` are implementation-owned. Coordinator documents
and task records are separate. No runner, orchestrator, policy, registry,
application, migrations or live operations may change. Unit tests must not make
provider calls. Implementation and review use Sol 6.1, medium, Fast/priority,
with no fallback. The direct coordinator workflow provides no release authority.
