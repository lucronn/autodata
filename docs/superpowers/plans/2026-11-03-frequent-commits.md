# Frequent meaningful commits

Goal: Require frequent, small, meaningful commits and prompt GitHub pushes while preserving planning, verification and branch ownership.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

The user requested frequent GitHub activity as an agent rule. Add the rule directly to AGENTS.md. Agents should commit at coherent, independently reviewable milestones and push after the relevant checks pass, following their assigned branch ownership and coordinator integration instructions. The rule must not encourage empty commits, unrelated cosmetic edits, broken intermediate states or rewriting published history to inflate activity. Existing pre-implementation and verification gates remain in force.

Scope: AGENTS.md only after this checkpoint; coordinator planning/tracking documents belong to this planning commit. This documentation change needs diff/Markdown inspection, with no application test suite or new tests.

## Todo

- [ ] Commit this plan and synchronized Issue186/Project8/canonical documentation record, then pass exact-base preflight.
- [ ] Add a concise AGENTS.md rule for small coherent commits, meaningful messages and prompt pushes of validated milestones on the assigned branch.
- [ ] Preserve existing planning/testing requirements and branch ownership; prohibit empty or artificial history changes made only to inflate activity.
- [ ] Inspect the Markdown diff, commit the instruction change separately and push the assigned coordination branch.
