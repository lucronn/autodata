# Initial selector safety verification

Issue: https://github.com/lucronn/autodata/issues/436
Project: https://github.com/users/lucronn/projects/8
Project item: `PVTI_lAHOCSJ8cc4BiQ2BzhI01Rs`.

Initial protected base `272aeeaa`; final protected integration base
`f534d0aeb76973ca3b8c70b14c806973edb1b457`.
Implementation gate `8bd9814`; actual HTTP/persistence refinement gates
`1a9101d4`, `90f8872b`, `8b3b688f`; each machine preflight passed before
its corresponding implementation. Ordinary integration `b2b3b34e` had no
conflicts or changes to protected UI code.

Red-first checkpoints:

- `eaed00c4` fails against the existing public selector path because it starts
  uncharged descendant deepening.
- `78e168c7` fails against actual HTTP years dispatch because it invokes the
  legacy unbounded manifest runner. The corrected route never invokes it.

Final focused host suite: `145 passed, 17 skipped, 42 subtests passed`.
This includes initial selectors, selector persistence, catalog service,
source connector client, explicit selector deepening, configuration #429 budget
and HTTP service. Local authored tests exercise socket resolver stalls,
real header stalls/trickling responses, shared nested Banktwo repair counts,
429, bytes/rows/requests, concurrency/cooldown, no late persistence and no
public descendant work. Complete cached years performs zero dispatches.
The old in-process selector retry fixture now patches the owned boundary
and checks the new thirty-second cooldown.

Five enabled isolated PostgreSQL integrations passed on integrated code
in 6.29s. A fresh task-only internal Docker network used cached PostgreSQL 17
and S3 images, tmpfs data, read-only roots, dropped capabilities, no published
ports, no host data mounts and no supplier credentials. Tests proved:

- actual Go cold-years GET → real Python HTTP ensure → owned authored-local
  connector → durable PostgreSQL years upsert → Go ordered 2023/2024 response;
  a second Go GET dispatches no additional connector request;
- exact provider/version/page URI retained, no fake source snapshot/S3 write
  and no unfiltered years marker;
- provider 503 leaves no year rows or false marker;
- a held years-table lock times out and rolls back without a marker;
- makes partial selector marker version 0 becomes version 1 only on completion.

All task PG/S3 containers and their internal network were removed after the
final integration; no serving/shared resources were touched. Docker capacity
remained 960 MiB free (approximately); physical home 7.1 GiB free.
A private aggregate cleanup receipt is retained outside Git.

Full Go API suite passed after protected-base integration (`go test ./...`).
A wider host worker run found missing Stripe and an unavailable SVG runtime and a pre-existing
`/tmp/.git` ancestor; it also exposed the old selector retry fixture corrected
above. A pinned cached-image, network-none worker run is recorded below.
The runtime image lacks pytest, so read-only copies of installed pure Python
pytest dependencies were staged privately; the image and serving dependencies
were neither rebuilt nor changed.

No real supplier/model calls, licensed bytes, grants, paid GET, serving
mutation, merge or deployment occurred. Existing explicit manifest helpers,
article/configuration contracts, supplier rights and external display limits
remain separate from this code acceptance. Strict CI and root review remain
required before merge; runtime needs a separate activation gate.

The pinned image `sha256:3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7`
passed the full worker suite at integrated `b2b3b34e`: **1303 passed,491 skipped,
250 subtests passed** in141.47s. Two warnings were attempts to write pytest
cache into the deliberately read-only checkout. No runtime image was built.
Subsequent red-first checkpoint `8621670e` caught two narrow contract gaps:
unfiltered years region must not bypass cooldown, and fallback years page
provenance must retain its cursor. Their fixes pass the final145-test focused
suite above. Required strict CI must validate the final review head.

Task fixture/container/network label readback is zero after cleanup, including
the temporary full-worker test container. The shared compat stack and all
serving/checkout data were left untouched. Protected master still equals
`f534d0aeb76973ca3b8c70b14c806973edb1b457` before final PR creation.

Root review requested an explicit incomplete-years caller no-write result and two-source/cold-retry regression. The existing lower helper already rejects incomplete years before connecting; the follow-up strengthens the caller contract and proves the actual cold-read behavior without claiming a reproduced durable partial write.

Root review follow-up passed at the explicit caller boundary: red-first
`5074b5d1` fails when a complete source plus incomplete/error source reaches
persistence. The caller now returns `skipped_incomplete_years`/`row_count=0`
for coverage and persistence, retains retry metadata, and does not call the
lower helper. The pre-existing lower guard remains as defense in depth.
No observed durable partial write is claimed. Makes/models still persist
truthful version 0 partial rows.

Final focused follow-up: **147 passed, 17 skipped, 42 subtests**. Enabled fresh
synthetic PG/Go integrations: **6 passed** in 23.33s. The added actual Go
cold-reader case uses a complete first supplier fixture and 503 second fixture:
Go returns empty, PG years/markers remain empty, and a retry before scope
cooldown dispatches nothing. After a test-only admission clock advance beyond
30s plus simulated process-cache expiry, both authored suppliers become healthy;
the same cold Go GET reattempts and returns ordered 2023/2024. The real owned
provider process still uses real elapsed time and six-second spacing.
All task PG/S3/test containers and internal network were removed again, with
zero residual task-label matches. No real provider/service operation occurred.

Strict CI import follow-up: child source must bind to the package root that loaded the parent, instead of assuming pytest/runtime sys.path changes were exported in PYTHONPATH. Build the child environment with that absolute source root first, preserve explicitly configured source credentials, disable bytecode writes, and test owned successful/DNS/header/trickle paths with PYTHONPATH absent. Keep stderr redacted and provider/IPC/resource bounds unchanged. This is not supplier compatibility evidence.

The first exact-head CI run 43675809125 failed six owned-child cases because
pytest configured only the parent sys.path, not exported PYTHONPATH. No source
request was dispatched by those failed child imports. Red-first `19d4e373`
reproduced the failure with PYTHONPATH removed. The child now binds to the
loaded parent package root and disables bytecode writes, retaining the same
provider/deadline/IPC limits and redacted stderr.

The CI-equivalent worker-directory command with PYTHONPATH absent now passes:
**147 passed, 17 skipped, 42 subtests** in 9.16s. The standalone owned-job
module passes all 29 tests without PYTHONPATH, including real local successful
connector and DNS/header/trickle cases. Enabled PG/actual-Go fixtures reran
with the source binding fix: **6 passed** in 21.89s, with task fixtures cleaned.
The queued intermediate run 43676223215 was canceled because it predates this
concrete import fix. Final exact-head strict CI is the remaining code gate.
