# Staging M1 explicit boot attachment name correction plan

> **For agentic workers:** Planning draft only. After a synchronized committed checkpoint, passing full-SHA preflight, independent exact-checkpoint review and fresh coordinator dispatch, use superpowers:executing-plans for this single correction. No implementation is authorized by this draft.

**Goal:** Explicitly select the staging VM boot attachment deviceName and make the offline Compute fake distinguish attachment names from disk resource names, preserving strict readback and every existing authority boundary.

**Architecture:** Retain the reviewed M1 address/disk/bare-VM bootstrap. Add only `AttachedDisk.deviceName` to the boot entry of the instance POST; `initializeParams.diskName` continues to select the boot disk resource. Make the fake honor an explicit attachment name and otherwise return a Compute-like default, so missing request fields cannot manufacture passing readback.

**Tech stack:** Existing Python-standard-library bootstrap and unittest fake Compute transport. No new dependency, schema, launcher, cloud call or configuration input.

**Spec:** `docs/superpowers/plans/2026-11-04-workshop-staging-lifecycle.md`; canonical gate `docs/agents/pre-implementation-gate.md`.

## Draft gate and exact source

Status: **draft; unsynchronized; implementation blocked**. PG's offline successor owns the serialized [Issue186](https://github.com/lucronn/autodata/issues/186)/[Project8](https://github.com/users/lucronn/projects/8) tracking slot. This draft makes no tracking change. It is rooted directly at rejected M1 candidate `188d6e66a3edff53bb84548d78876f8c98f6aec0`, not at an assumed integrated source. Historical M1 gate `52653deef3754972230801ac260875fe92e1a403` and receipt `5bd9b82aa71b68938c130c58062b8664596c6758` are history only; they do not authorize a corrective builder or establish acceptance of the rejected candidate.

Independent candidate review `/tmp/autodata-staging-m1-188d6e6-review.md` requests one P2 correction: candidate `staging_bootstrap.py:456–458` leaves the boot attachment name unspecified while readback at line484 requires `<instance>-boot`. The fake at `test_staging_bootstrap.py:382` silently derives deviceName from `initializeParams.diskName`. That conflates two distinct API fields. `initializeParams.diskName` names the disk resource; an omitted attachment deviceName receives a Compute-selected `persistent-disk-x` name. Review evidence `/tmp/autodata-staging-m1-188d6e6-review-device-name.log` reproduces rejection after all three POSTs and retained resources. Temporary review files support this draft; later synchronization must retain their hashes and diagnosis durably.

Planner independently reproduced the same outcome without modifying implementation: intercepted fake transport mapped omitted deviceName to `persistent-disk-0`; original request returned Denied after three POSTs and retained address/data disk/boot disk/instance. A second isolated intercepted run injected only `deviceName=workshop-stage-boot` into the boot request and honored that explicit field; it returned simulated passed with the same three POSTs. These are fake-transport diagnosis observations, not a repaired candidate or any cloud/readiness evidence.

## Global constraints and two-file implementation allowlist

Only these implementation paths may change after the new gate passes:

1. `infra/deploy/gce/staging_bootstrap.py` — one explicit boot attachment request field; preserve the current strict readback requirement.
2. `infra/deploy/gce/test_staging_bootstrap.py` — realistic attachment-name default, exact request assertion and focused regressions.

Exclude `cloud-bootstrap.sh`, `staging-bootstrap.schema.json`, all runtime/host/Compose/workflow/IAM/publisher/schema code and all application files. No new input or request endpoint. Keep staging-only apply, fixed FD3 token boundary, inherited metadata/image/network/firewall/route constraints, default-route exception, requestId/ownership/idempotency, retained-resource cleanup, budgets/redaction and all production/installation/format/secret/start/readiness denials exactly as reviewed. Existing data attachment `deviceName=autodata-data` remains exact. Do not accept Compute defaults or a broader arbitrary name during production readback to make tests pass.

## Exact request amendment

In `Bootstrap.instance_body()`, the first `disks` element must carry **both** the boot attachment and resource names, each derived solely from the validated instance name:

```python
{
    'boot': True,
    'type': 'PERSISTENT',
    'autoDelete': False,
    'deviceName': self.config['resources']['instance_name'] + '-boot',
    'initializeParams': {
        'diskName': self.config['resources']['instance_name'] + '-boot',
        'sourceImage': self.image,
        'diskSizeGb': '20',
        'diskType': self.z + '/diskTypes/pd-balanced',
        'labels': self.labels,
    },
}
```

The new field is a sibling of `initializeParams`, never nested inside it. The existing instance-name length constraint keeps both derived names within63 characters. Boot disk GET and instance attachment readback must still bind the exact boot disk selfLink/resource ID/image ID and require attachment deviceName `<instance>-boot`, with existing `READ_WRITE`, PERSISTENT, boot=true and autoDelete=false checks. Resource name, attachment name and resource identity are independent checks even though the two selected name strings intentionally match. No readback relaxation or additional implementation refactor is needed.

At synchronization, append this explicit field distinction to the canonical M1 request contract in lifecycle/hosting/operations notes; do not silently reinterpret the earlier phrase “boot disk named `<instance>-boot`” as evidence the original code selected AttachedDisk.deviceName. Preserve the rejected candidate diagnosis and all prior PG/JS index/detail/pin texts with hashes before any serialized tracking replacement.

## Exact fake behavior and meaningful regression cases

In the existing FakeCompute instance POST branch, retain the boot disk resource path/name from `body['disks'][0]['initializeParams']['diskName']`. Select the observed boot attachment name independently:

```python
boot_attachment_name = body['disks'][0].get('deviceName', 'persistent-disk-0')
observed['disks'][0].pop('initializeParams')
observed['disks'][0].update(
    source=boot_path,
    deviceName=boot_attachment_name,
    mode='READ_WRITE',
)
```

`persistent-disk-0` is the deterministic fixture's representative Compute-like default; tests must not claim the exact numeric suffix is a production guarantee. An explicitly supplied name must be echoed unchanged; a missing field must never be derived from `diskName`. Preserve fake labels/boot resource identity/attachment modes, all existing call capture and transport bounds, and the unchanged data attachment behavior.

Required tests, all with intercepted transport:

- `test_boot_attachment_device_name_is_explicit`: assert the exact first disk request object above, including separate `deviceName` and `initializeParams.diskName`, and unchanged `autodata-data` on the second attachment. Run complete `Bootstrap.run()` against the realistic fake and require simulated passed.
- `test_fake_missing_attachment_name_uses_independent_default`: use a fixture-only request wrapper to remove boot `deviceName` before the fake sees the instance POST. Assert captured request omission, boot disk resource name remains `workshop-stage-boot`, observed attachment name becomes `persistent-disk-0`, all three POSTs occur and strict readback raises Denied with resources retained. This negative control proves the fake would expose the original defect; it does not make omission acceptable.
- `test_boot_attachment_name_drift_rejected`: after a complete explicit request, substitute `persistent-disk-0` and an unrelated nonempty name independently in observed boot attachment readback; require Denied and retained resources. Do not alter the boot disk resource name/ID to conceal attachment drift.
- Retain exact request inventory, first-run success, matching idempotent rerun, transport-loss/same-requestId and both-disk ownership/readback regressions. Fake default changes must not weaken any existing malformed-observation, unknown-property, field-type or authority-denial assertion.

## Single corrective milestone and concrete todo

- [ ] After PG releases the serialized tracking slot and coordinator approves this draft, synchronize the exact boot-attachment correction goal, explicit POST amendment, two-file allowlist, regression cases and todo across Issue186/Project8 and canonical plan/task/record/notes; preserve then-current full PG/JS index/detail/pins verbatim with hashes, commit/push and pass full-SHA preflight before independent exact-checkpoint review.
- [ ] Obtain independent review of that exact new checkpoint and fresh root dispatch before implementation; preserve rejected source `188d6e66a3edff53bb84548d78876f8c98f6aec0` and the prior M1 gate/receipt as distinct historical records without retrospective acceptance.
- [ ] Change the fake's omitted-name behavior and add the exact request/default/drift regressions first; demonstrate a red complete-run failure on the uncorrected request, with all three POSTs and retained resources, using only intercepted transports.
- [ ] Add only the explicit boot AttachedDisk.deviceName sibling field in staging_bootstrap.py; keep strict readback and all request/approval/config/FD3/network/receipt/authority boundaries unchanged; run focused bootstrap plus existing host/cloud regressions, syntax and diff/scope checks.
- [ ] Commit/push the exact two-file candidate, retain red/green logs and independently review its full SHA before integration; no credentials/cloud/resource operations, installation, formatting, host startup, readiness, cars.tk or production authority follows from simulated success.

Run after authorized implementation:

```sh
python3 -m unittest discover -s infra/deploy/gce -p 'test_staging_bootstrap.py' -v
python3 -m unittest discover -s infra/deploy/gce -p 'test_cloud_ops.py' -v
python3 -m unittest discover -s infra/deploy/gce -p 'test_host_runtime.py' -v
python3 -m py_compile infra/deploy/gce/staging_bootstrap.py infra/deploy/gce/test_staging_bootstrap.py
git diff --check
```

The independently reviewed source baseline had30 bootstrap tests and121 existing host/cloud tests passing; those counts are historical, not acceptance of future correction or cloud compatibility. New meaningful regressions add coverage; require actual final output rather than fixed totals. Verify `git diff --name-only <new-pinned-checkpoint> <candidate>` is exactly the two implementation paths above before review. The new plan/checkpoint may add only canonical documentation and tracking records; those are separate from implementation allowlist.

## Unsynchronized record shape and handoff

The future dedicated record/task will reference this plan, Issue186/Project8, canonical lifecycle/hosting/operations/architecture notes, exact goal/todo/two-file scope and rejected source pin above. Its status remains **draft** until actual tracking/canonical synchronization and readback exist. Do not copy the prior M1 synchronized record as authority for this amendment or label the rejected implementation accepted. No machine-checked synchronized correction record exists at source188d6e6 today. No implementation, cloud, credentials, resources or runtime action has occurred during this draft.
