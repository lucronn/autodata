# Watchdog helper verification

Status: helper-only implementation locally verified; no live execution adapter, deployment, or supplier GET. Product runtime SHA remains UNSET.

Gate checkpoint18aed62 was committed/pushed after Issue401 comment6888651102 and Project8 matching readbacks; machine preflight returned synchronized/errors[] before tests/helper creation. Base protected4048f3fae50161af5b5ab8300670e3beb817ce1a.

Red-first: focused unittest discovery failed before implementation with one import error/FileNotFoundError for missing helper. Green:33 offline synthetic tests passed in0.061s; py_compile and git diff --check passed. Tests exercise fixed local Docker argv/minimal child environment with mocked subprocess only; no Docker process/provider/service operation occurred.

Implemented: injected-backend state machine; fixed-context subprocess boundary; exclusive file+directory fsynced markers; single-attempt-before-fetch; arm/deadline/boot binding; safe fixed-field log correlation; interprocess finish/fence lock; intentional exact-ID fence/stopped proof/restart; damaged disarm fails closed; unknown stop or worker start holds stopped; rollback finally restarts retained predecessor and rechecks exact identity/passive invariants. No raw exception/log/response content is saved by core. CLI accepts validate only and always reports live_execution_available:false.

This is a reviewable core, not an operational watchdog. Production systemd supervision/ExecStopPost finalizer, timestamp/cursor-bound candidate log reader, physical filesystem/socket/data-root/storage admission, bounded HTTP transport, live PG fingerprints and actual-image fixtures are deliberately unwired. After429 protected merge, synchronize a new exact-source runtime gate before those adapters. Root independent artifact review remains required before staging/arming/GET. Existing343896/source083/image3132 and retained6fcc unchanged.

## Exact-head review correction

Review amendment gate17c1cfc was committed/pushed with Issue401 comment6888673684/Project matching readbacks and synchronized preflight before implementation changes. Meaningful red-first regression run:40 tests,6 failures reproducing predecessor drift/inspect/fresh-check and dead/missing/slow supervisor acceptance defects. Green:42 offline tests PASS in0.064s; diff check/py_compile PASS.

Rollback now verifies predecessor before the candidate try/finally, rechecks immediately before start and after start, and refuses mutation for initially unverified predecessor. Known-good predecessor recovery remains after candidate inspect/stop failure. Tests preserve rollback-attempted and existing GET/fence markers on refusal, with no successful restart/disarm receipt and no replay. Dispatch requires explicit injected supervisor liveness verifier immediately before attempted marker; verifier absence/error/death or elapsed admission refuses without GET/marker. CLI remains validate-only; no Docker/provider/service calls. Physical safe red/green receipts: /home/corp/.local/state/autodata/configuration-probe-watchdog-20261115/review-{red,green}.log.

No-overlap amendment9711b45c: red45 tests/4failures+1error -> green45. Candidate unknown inspect/still-running after stop timeout refuses predecessor start with durable refusal; stopped/Pid0 must be proven. Already-running verified predecessor receives no duplicate start. This supersedes earlier candidate-failure finally recovery language. CLI validate-only/no live calls.

Intentional-stop gatecc755675: core red5→48 PASS; unconditional successful exact stop required before stable stopped/Pid0/Restartingfalse proof (even already exited). Timeout/error holds. Core still validate-only; production adapter not armed.
