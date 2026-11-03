# Workshop commerce verification

Issue: https://github.com/lucronn/autodata/issues/186

Project: https://github.com/users/lucronn/projects/8

The integrated commerce candidate is `d2eb70fa9b96fcebe1c33ef6cddcdad5c4a5eec7`.
The gated implementation covers the 39 paths in the commerce plan. Authoritative
Python orders, official Stripe 16.1.0 integration, migration 040 and the Go
session/CSRF boundary are implemented. Only verified settlement matching the
stored merchant, mode, Price, owner, amount and exact configuration/region grants
permanent access. Content preparation and payment state remain independent.

This verifies the development dependency. Live Firebase/Stripe configuration,
actual merchant payments, purchased catalog/media integration, browser acceptance,
hosting and deployment remain separate release requirements.

## Actual database and HTTP acceptance

All following runs used a clean plain clone of the exact candidate, immutable
independently reviewed supervisors, isolated fixture services, raw evidence and
successful cleanup. Each result has status `passed`, exit code 0 and no failures.

| Run | Result | Receipt SHA256 |
| --- | --- | --- |
| Commerce | All 14 required PostgreSQL cases; 67 pytest cases plus 7 native subtests; actual Go HTTP client to Python HTTP/PostgreSQL root; 327.046 seconds | `67b88304208d675e703f627d28e53c31396e006fd61e418b5983c569d5ca3e44` |
| Identity through 040 | All 5 PostgreSQL/SDK scenarios; 57 pytest cases plus 7 native subtests; historical 038 startup refusal; 258.668 seconds | `9d4ea6678dbed5b5283bcd472138dc5c0c0ec4879894b0314ce4152d57bda374` |
| Dual-bank regressions through 040 | All 8 real HTTP/worker/PostgreSQL/S3 cases and 8 distinct databases; 236.362 seconds | `d308e52c1561c2809080e37d5d08464e6710718cc9fe7bbb9891ed1e116042e8` |

Receipts are `artifacts/acceptance-result.json` beneath
`/tmp/autodata-commerce-040-acceptance-d2eb70f`,
`/tmp/autodata-r5-040-acceptance-d2eb70f` and
`/tmp/autodata-r3-040-acceptance-d2eb70f`, respectively. Raw logs, migration data,
input manifests and before/after repository observations remain beside them.

The commerce inventory exercises ownership, replay/conflict, concurrent keys,
single active grants, uncertain provider responses, expiry races, early/duplicate
webhooks, financial binding, monotonic refund/chargeback revocation, persistence,
library pagination and exact-scope checks. Concurrent different keys can issue
two idempotent SDK attempts, but produce one actual provider checkout session.
The Go seam proves trusted organization binding and the real versioned DTOs.

The R3 cases retain readable permitted source content during a held rewrite,
one durable article job and one atomic publication, provider-scoped identities,
observational active/warm reads and fresh/empty/populated migration replay.
These remain fixture-provider proofs, not evidence of licensed live-bank content.

Supervisor hashes:

- Commerce: `/tmp/autodata-workshop-commerce-040-source-fixture-supervisor.py`,
  `fefe49edb125b7c1e7c98b225accd884fdecea8308d3443cef9b83e0ef31db69`.
- Identity: `/tmp/autodata-r5-040-access-supervisor.py`,
  `94f81fd8665351eb2fab07c59e5752874634855b8ba3a5f5862dfd4ea0a20adb`.
- R3: `/tmp/autodata-r3-040-acceptance-supervisor.py`,
  `039a42c5287be5ed25d8b1c0b4724c1f9bad5f0e7f727a1270830a48304d28fa`.

## Corrections and independent review

Original failed receipts are retained unchanged. Candidate `4a74e16` had nine
PostgreSQL failures caused by an untyped standalone nullable SQL parameter.
Reviewed correction `9d33e1e` compares the three values directly to typed columns;
it preserves null nonmatching behavior. Its next run passed 66 tests plus 7
subtests and exposed one invalid source fixture: a current source pointer lacked
the required article job. Candidate `d2eb70f` creates that job through the actual
store before assigning the source pointer. Production code and schema were not
relaxed to accommodate the fixture.

SQL correction review: `/tmp/autodata-workshop-commerce-9d33e1e-review.md`,
SHA256 `e4d6b1d6df9c07dbd63b2f81415d8c8e3d17e3f428ddeea8d1c1159067d85b81`.
Fixture and strict supervisor review:
`/tmp/autodata-commerce-source-fixture-review.md`, SHA256
`94fe0421899ad326ef35deb3664d0230700544a28cf9d505780ab2f5845383d7`.
The successor supervisor passed 15 pure checks, including nine source-job
mutation rejections; no case or earlier invariant was removed.

## Production image and CI

The actual ingestion production Dockerfile built from the exact candidate.
The resulting image `sha256:ec6c79dbe4ca49b54579770474e41dbe3a9dce787235d612c756f058bf49f723`
successfully imported Stripe 16.1.0, the HTTP service, commerce service and payment
reconciler without source mounts, network access or secrets. The temporary image
tag was removed. Receipt `/tmp/autodata-commerce-production-image-d2eb70f/result.json`,
SHA256 `82ed82a45f548a75bc984dde5dc3eef0e69b459ea53c5819ebe36eec2f83e8d1`.
This is installation/runtime import evidence; it is not a published release image.

Full [GitHub CI 41705272372](https://github.com/lucronn/autodata/actions/runs/41705272372)
passed at the same candidate, including Go, ingestion/enrichment tests, Compose
validation and the live Compose smoke test. Subsequent paid-access/UI integration
must provide its own exact-candidate evidence before release.
