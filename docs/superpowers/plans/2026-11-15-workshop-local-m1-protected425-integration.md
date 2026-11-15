# Empty local M1 protected #425 integration

Goal: Integrate the empty local Workshop M1 milestone on protected #425 source with all five reviewed implementation blobs unchanged.

Issue https://github.com/lucronn/autodata/issues/398; Project https://github.com/users/lucronn/projects/8.

Protected source083f1a502a0f18d371793df59d3310408059d44e/tree2c6a681b31c0031743f5580825949ad192e87f04. Commit this docs-only checkpoint and pass exact machine preflight before copying implementation. Preserve the stopped historical94d3f499034253a1d1a331f50892b287c0a6d7f0 canary and published branch.

Merge only protected #425 source after checkpoint preflight; retain all five reviewed M1 implementation blobs unchanged from94d3f499. Contract: six fixed-project services, cached immutable images, RO roots/bounded limits and logs, fresh isolated physical-home storage identity, commerce disabled, no provider/Firebase/Stripe credentials or requests, internal Docker network with no publication, bounded host-only127.0.0.1:3041 relay, full startup actual-policy/ENV and lifecycle/source/engine/locking guards. No application/schema/frontend changes, new runtime startup or external deployment. Preserve protected #422 source.

Allowlist:
- infra/compose/compose.workshop-local-empty.yaml
- scripts/dev/workshop_local_admission.py
- scripts/dev/test_workshop_local_admission.py
- scripts/dev/workshop_local_forwarder.py
- scripts/dev/test_workshop_local_forwarder.py
- docs/operations/workshop-local-empty-runtime.md
- docs/verification/2026-11-15-workshop-local-empty-runtime.md

Todo:
- Merge exact protected #425 source after this docs checkpoint passes preflight, preserving all five M1 implementation blobs
- Run focused tests and strict CI at the exact merged feature head; hold merge for root
- Record integrated source/tree/blob and CI evidence; keep Issue398 open and historical94d3 runtime untouched

Acceptance:33 focused tests plus3 existing Compose tests; clean diff; strict required CI at exact integrated head; root review before merge. Canary acceptance remains only94d3; no integrated runtime claim. Compatibility failure requires scoped checkpoint correction, not application/runtime expansion. Rollback: abandon integration branch, preserve stopped canary/resources/volumes and protected master.

Issue398/Project8 remain open/In Progress. M2 requires separate gate, clean credential-free ingestion build, Stripe TEST/Firebase/tester inputs, supplier rights, ingress/cost choice and actual data/payment acceptance.

Previous #422 integration head debedf34c3ec3cf711941cf7bc12c085995c90c0 passed all three CI jobs in run43668033888. This follow-up preserves published PR426 history: fresh docs checkpoint and preflight, then a normal merge of protected083f1a5 (no force push) and exact-head rerun. No local runtime restart or M2 implementation.
