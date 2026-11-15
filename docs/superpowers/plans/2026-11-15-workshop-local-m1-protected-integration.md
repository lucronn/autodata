# Empty local M1 protected-source integration

Goal: Integrate the empty local Workshop M1 milestone on protected #422 source with purchases and external access disabled.

Issue https://github.com/lucronn/autodata/issues/398; Project https://github.com/users/lucronn/projects/8.

Protected source5981b97f187364e54737919fd8cdb49e7566d981/treeb3f321d0263e12da2d5c54f136c9ffcee155e1d1. Commit this docs-only checkpoint and pass exact machine preflight before copying implementation. Preserve the stopped historical94d3f499034253a1d1a331f50892b287c0a6d7f0 canary and published branch.

Copy only reviewed five implementation blobs from94d3f499. Contract: six fixed-project services, cached immutable images, RO roots/bounded limits and logs, fresh isolated physical-home storage identity, commerce disabled, no provider/Firebase/Stripe credentials or requests, internal Docker network with no publication, bounded host-only127.0.0.1:3041 relay, full startup actual-policy/ENV and lifecycle/source/engine/locking guards. No application/schema/frontend changes, new runtime startup or external deployment. Preserve protected #422 source.

Allowlist:
- infra/compose/compose.workshop-local-empty.yaml
- scripts/dev/workshop_local_admission.py
- scripts/dev/test_workshop_local_admission.py
- scripts/dev/workshop_local_forwarder.py
- scripts/dev/test_workshop_local_forwarder.py
- docs/operations/workshop-local-empty-runtime.md
- docs/verification/2026-11-15-workshop-local-empty-runtime.md

Todo:
- Copy exact five reviewed Compose/admission/forwarder implementation and test blobs after checkpoint preflight
- Run focused checks and strict CI at the exact integrated head; hold merge for root
- Record source/tree/blob and CI evidence; keep Issue398 open for real-data/payment acceptance

Acceptance:33 focused tests plus3 existing Compose tests; clean diff; strict required CI at exact integrated head; root review before merge. Canary acceptance remains only94d3; no integrated runtime claim. Compatibility failure requires scoped checkpoint correction, not application/runtime expansion. Rollback: abandon integration branch, preserve stopped canary/resources/volumes and protected master.

Issue398/Project8 remain open/In Progress. M2 requires separate gate, clean credential-free ingestion build, Stripe TEST/Firebase/tester inputs, supplier rights, ingress/cost choice and actual data/payment acceptance.
