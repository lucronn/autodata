# Workshop client runtime route compatibility

Avoid unusable Workshop quote requests when purchasing is not enabled and honor explicit local authentication mode when choosing the existing article read route, preserving paid Firebase preparation and existing authorization.

Tracking: https://github.com/lucronn/autodata/issues/430 and https://github.com/users/lucronn/projects/8.
Plan: [implementation decisions](../superpowers/plans/2026-11-14-workshop-client-runtime-gaps.md).

Purchasing is enabled only by exact enabled=true. Explicit local auth mode selects the existing GET article route; Firebase and unknown modes retain paid preparation. Mode controls route selection and never grants access; existing session and server authorization remain authoritative.

Concrete todo:

- Request and validate vehicle quotes only when purchase configuration enabled is exactly true; retain article loading, enabled Stripe TEST quote handling, and stale/abort protection.
- Expose only normalized local/firebase auth configuration mode in session state; reset it on invalidation/bootstrap and keep authenticated cookie validation unchanged.
- Use the real authenticated GET article route instead of POST prepare only for explicit local mode; retain prepare for Firebase, absent, malformed, or unknown mode.
- Add focused regressions for quote gating, enabled quotes, mode reset and races, local GET, paid prepare, article polling, missing authentication, and stale/aborted navigation; run the complete client/demo tests and syntax/diff checks.
- Commit and push the validated milestone for coordinator review; hold PR/CI until coordinator resolves the #429 base boundary. Do not merge, deploy, mutate M2A, or call provider/payment/auth services.

Implementation passed pushed checkpoint `c991311` with synchronized preflight. [Verification evidence](../verification/2026-11-14-workshop-client-runtime-gaps.md) records 287 passing client/demo tests and the coordinator-owned M2A/runtime boundary. PR creation remains held pending #429 base coordination.
