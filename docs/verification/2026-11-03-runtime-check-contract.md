# Runtime check-contract repair verification

Issue: https://github.com/lucronn/autodata/issues/186

Project: https://github.com/users/lucronn/projects/8

Candidate `6992bd08f6e20013288947d893f9b00745d45d7f` passed independent
code review and is integrated as `91c8e85`.

The five-file repair allows the trusted Python 3.11 check executable, separates
the trusted-check environment from the provider guard, and limits synthetic
fixture review prompts to their assigned scope. Strict artifact binding,
redaction, replay and global verification gates remain enforced.

## Actual offline acceptance

Retained run: `/tmp/autodata-runtime-offline-6992bd0-logparse`.

- Exact candidate full suite: **146 tests passed**, no skips, 49.634 seconds.
- All **eight frozen checks** completed with exit zero and no findings against
  the quarantined one-file synthetic child `80f76498360fcebf7e76bf44c11e84da18388b06`.
- Zero provider sentinel calls; network disabled; no provider package or auth
  available; nonroot UID 1000, no capabilities, no-new-privileges and noexec /tmp.
- Source checkout unchanged; owned container and executable scratch removed.
- Complete bounded run: 112.427 seconds, no failures.
- Integrated checkout full autonomy suite: **146 tests passed**, 44.576 seconds.

The synthetic child is evidence only and is not integrated or pushed. This
acceptance does not certify a live provider trial or production Workshop.

Frozen offline supervisor SHA256:
`41daa6520dd104a4f08bd6ecb61c7578d0dd7b844bf3139a05d1bfb4411d459e`.

Pinned local image ID:
`sha256:3348a8a15a76e1fe91baae8a3d7ebe124979edbb2f0aeb142a66021848b469ca`.

Independent code report: `/tmp/autodata-runtime-check-contract-review-6992bd0/review.md`.
Independent final parser report: `/tmp/autodata-runtime-offline-supervisor-41daa65-review.md`.
The final parser review accepted the retained actual 146-test diagnostic log and
rejected six independent before/between/after standalone FAIL/ERROR mutations;
14 pure receipt/deadline/mount tests passed.

Earlier failed runs remain unchanged under their original roots: generated
cache cleanliness checks, Docker tmpfs inspection, and verbose-log parsing
failed before this fresh acceptance. They are not relabeled as passing.
Further live synthetic provider trials remain deferred while product work
targets the paid Workshop launch.


## Shallow GitHub checkout successor

Actual runs41689471428/41688178571 exposed two historical git-show dependencies
in the prompt tests despite full-clone offline success. Candidate
`d0a8aceffa41fe46ea0265ad036933ab1cf992b8`, gated at6d9f2f59 and integrated
`1b53dc3e22e195cc996588d8fbb20ffd73758238`, changes only test_runner.py:
read the actual complete prompt bytes after asserting the independently frozen
5da393 SHA256, then decode strict UTF-8. All semantic assertions are unchanged.

Author146 tests passed with no skips; original depth-one red remains retained;
fresh exact-candidate depth-one focused2 passed while5da393 remained absent.
Root independently checked diff/scope/AST and frozen-byte equality, reran both
focused cases in full/shallow clones and rejected three changed-byte cases.
Independent report: /tmp/autodata-runtime-shallow-root-review.md.
Evidence: /tmp/autodata-runtime-shallow-repair-ug1erqt4.

Actual CI41691331286 passed runtime, Go, contracts and worker tests, then failed
an unrelated exact-spacing developer assertion; that one-line repair22db145
has separate synchronized gate,98 development passes, Go privacy checks and
independent review. Full CI41692463236 is pending. Earlier failed CI/runtime
evidence is retained; no live-provider or release certification is claimed.
