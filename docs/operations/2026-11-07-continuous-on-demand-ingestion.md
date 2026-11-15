# Continuous on-demand ingestion planning checkpoint

Status: synchronized code-only planning checkpoint. Scope https://github.com/lucronn/autodata/issues/186#issuecomment-6699585681; dedicated Project8 field `PVTF_lAHOCSJ8cc4BiQ2Bzho53nE` exact readback verified. No runtime authority.

Add opt-in schema2 continuous on-demand article admission with a durable rolling10jobs/24h cap, one attempt per fresh job and permanent no-replay ledger, while preserving finite schema1 unchanged.

Decision-complete [plan](../superpowers/plans/2026-11-07-continuous-on-demand-ingestion.md). Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8; productbaseb3a5c83bfd5238b72b2eca534c61d9d9637b116e.

Schema2 is opt-in --continuous, initializeddisabled with sourcepin/activationDBcutoff. Strictroot-owned atomic JSON keeps at most10000 spentIDs/2MiB permanently; trailing24h reservations count toward10cap, each jobcap1/no replay. At ceiling failclosed/no pruning/reset (at most1000 full10-job days). Disabled stops; quota-full/empty enabled worker polls2s. Legacy schema1 expiry/state/admission behavior unchanged; installed finite unit unchanged by this code-only work.

Older untouched descriptors are eligible ONLYfor freshly created postactivation jobs with every existing pristine/nohistory/fencing constraint retained. No historical job/revision/attempt/candidate replay, creation timestamp edit or generic sweep. The existing preview unit selects --continuous/restart-onfailure/throttle/bootInstall with the same container singleton; installation/activation/restart requires separate future runtime gate. Existing five spent jobs/four disabled rollouts untouched. No lifecycle/model/validator/API/catalog/payment/schema change.

Concrete todo:
- [ ] Add failing state/admission/loop regressions for opt-in schema2 rolling quota, permanent reservation retention/crash no-replay, untouched older descriptors with freshly created jobs, negative historical lanes and unchanged finite schema1.
- [ ] Implement minimal schema2 state and admission/dispatch predicates in new_article_worker.py plus the inert continuous preview service unit; retain shared exact-job lifecycle, cap1/sourcefallback behavior and root-owned atomic locking protections.
- [ ] Run focused unit and realPG worker/lifecycle tests, existing autonomy checks and independent review; commit/push coherent milestones and exact PR/CI evidence. A separate merged-source runtime gate must authorize archival/newdisabledstate/install/enable/start/restart; this code gate deploys nothing.

Ledger validation uses MAX(reserved_at) across all entries for DBclock regression and checks <=10 reservations in EVERY saved open-left24h historical window (including unsorted arrays); a future earlier entry or malformed old overquota window failsclosed, not only the newest array element/current count.
