# Offline private capture supervisor

Goal: Implement offline private capture process supervision with durable16-request180-second bounds and verified kill/reap while keeping provider dispatch disabled.

Issue: https://github.com/lucronn/autodata/issues/401
Project: https://github.com/users/lucronn/projects/8

## Concrete todo

- [ ] Synchronize protected-base plan, Issue401, Project8 and canonical supervisor contract before code
- [ ] Add red child-stall, TERM-resistant descendant and exhausted-budget regressions without supplier calls
- [ ] Implement durable consumed16-request journal,180-second monotonic run budget, bounded operation child process groups, output caps and unconditional owned kill/reap
- [ ] Run offline supervisor tests and seal reviewable branch/evidence; keep dispatch null pending independently verified origin-to-deployed-commit/image attestation

Protected implementation parent09524db; isolated branch codex/private-capture-supervisor-20261116. Previous capture packet R1 remains HELD; this task implements only the missing offline supervisor, not provider transport.

Production caps are immutable maxima:16 total operations/requests,180seconds run lifetime,12seconds each operation,2seconds TERM grace,64MiB total response bytes,8MiB per response, and128MiB private retained storage reserved for eventual reviewed capture integration. A shorter test clock/budget may be injected; a caller cannot raise maxima. Before every child start, durably consume its dispatch ordinal in an exclusive one-shot journal; failure/restart cannot replenish allowance. Constructor/reopen never replays a consumed attempt.

Use a fresh owned process session per operation, filtered environment, nonblocking bounded pipe reads and independent monotonic deadline. Cleanup runs before acceptance/boundary checks and must TERM/KILL the entire owned group, wait/reap the direct child and adopted descendants, and prove the owned group absent even after timeout, output flood, child exit with living descendants or parent exception. Never signal unrelated groups. Linux child-subreaper ownership must be isolated to a dedicated supervisor process; never change the product service or long-lived agent process. A cleanup uncertainty holds/fails the receipt. Source output, command content and exceptions never enter metadata receipts.

The only CLI path is a fixed offline diagnostic child with no sockets/provider imports and a filtered environment. Library supervision may be exercised with synthetic Python children in tests; no live transport/client/URL/credential dispatch interface is installed. dispatch_argv stays null and external_display_allowed false. Adding producer transport requires separate exact-code review and current origin-to-build attestation; main branch, health status and upstream source_revision are insufficient.

No supplier/model calls, DB/S3/productHTTP/Docker/service changes or external content exposure. Changes only developer supervisor/tests/docs; retain failures and do not install dependencies or alter runtimes.
