# Workshop product evidence: offline diagnostic milestone

The first assembler milestone implements strict v1 envelope structure and a
coordinator-supplied trusted invocation. It does not validate raw evidence or
verify either tier. All profiles at the authorizing checkpoint
`0e21f6dbdf5ad0402b8bef42d3e1f2566964b309` are disabled and the assembler hash is
unpromoted. The actual planning task therefore returns exit 3 (`unavailable`)
from `validate`, even for a structurally valid envelope with supplied pass reports.

Run from the owned checkout, with an explicit dedicated evidence directory:

```sh
python3 scripts/dev/release_acceptance.py plan \
  --manifest /protected/evidence/envelope.json \
  --evidence-root /protected/evidence/raw \
  --trusted-base-sha 0e21f6dbdf5ad0402b8bef42d3e1f2566964b309 \
  --task-ref docs/agents/tasks/2026-11-03-production-release/r6-release.json \
  --requested-tier fixture
```

Use `validate` in place of `plan` to receive the unavailable result. `plan`
exits 0 only for a valid diagnostic request; its `planned` status is not
acceptance. `validate` cannot exit 0 in this milestone. Every verification,
deployment and cutover flag is always false. All observed counts are zero, all
required slots remain missing and all eight gate statuses remain unavailable.
The envelope's declared pass reports, artifact hashes and commands cannot
change these outputs. The evidence directory and its files remain unread.

The manifest is one UTF-8 JSON object of at most 2 MiB. Duplicate and unknown
keys, nonfinite numbers, booleans in integer positions, invalid versions,
identifiers, paths, hashes and internal references are rejected. Commands are
validated as data and never executed. Parse failures emit static diagnostic
codes without echoing candidate strings or private contents. The only subprocess
reads pinned Git objects from the tool's owned repository, with isolated Git
configuration; candidate code is never imported and evaluator/controller code
is never executed. The trusted base, task and requested tier come from the
coordinator's invocation and must match the envelope.

Exit 2 means invalid contract, invocation or trusted object integrity. Exit 3
means unavailable verification. Future gated raw validation will additionally
use exit 4 for actual execution/assertion/policy failure, with precedence
2, then 4, then 3. That raw validation behavior is not implemented here.

Before any promotion, independently review the exact implementation commit,
freeze the reviewed assembler hash and complete raw profiles in a new
synchronized task checkpoint, then run the exact-base gate again. A promoted
profile is deliberately rejected by this milestone until its validators are
implemented under that gate. Hashes alone do not authenticate authors. Candidate
ancestry, evidence-directory confinement and immutable file checks, case IDs,
source/migration/image/SDK/CI bindings, report identities and policy derivation
remain required future work; structural parsing proves none of them.

Fixture verification will require actual 5+8+14+12+120+21 raw cases plus
supporting evidence. DTO mocks cannot satisfy the real API browser slot or
live Google/Stripe proof. Staging requires the separately gated collector,
licensed enrollment, protected proof and actual host/isolation/recovery/alert
receipts. Neither the synthetic tests nor historical paid12/DTO evidence verify
a final candidate, staging, deployment or the separately unverified runtime.
The policy, evaluator and workflows remain authoritative and unchanged.

Bounded local checks:

```sh
python3 -m unittest scripts/dev/test_release_acceptance.py -v
python3 -m unittest discover -s scripts/dev -p 'test_*.py'
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
git diff --check
```

Tests use inline synthetic envelopes and the actual disabled committed task.
They are parser/tooling tests, never actual product acceptance receipts. Do not
run providers, browsers, Docker or cloud commands as part of this milestone.
