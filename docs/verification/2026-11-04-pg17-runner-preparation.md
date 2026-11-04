# PG17 disposable runner preparation evidence

Status: adopted preparation gate passed; preparation unexecuted and held for coordinator verification/go-ahead. Actual PostgreSQL startup and harness execution remain unexecuted and unauthorized.

- Reviewed corrected plan: `7988c7de30e6de930d36a3b8d907cdb4e90264ba`; review receipt `79d5f089acbdcd09d490c5ca56f582da8bc24be6`.
- Adopted synchronized checkpoint: `bad940db48d649fd8d5b08d119c66defde19884c` on `codex/workshop-pg17-runner-prep`.
- Pinned machine preflight: exit0, `{"status": "synchronized", "errors": []}`; exact pinned record SHA256 `afbfd4f5a387eba2e60f32678592573a72af41a8edd51c117c93e8cd4aca7692`.
- Tracking readback: [Issue186 adoption](https://github.com/lucronn/autodata/issues/186#issuecomment-6621086102); Project8 prior index preserved verbatim in that comment.
- Immutable harness source: `54ab7dce19c36ce7ea3403259dd1ecc66bf323aa`; source archive SHA256 `4666eec4f3575fcc4f12ec6956af41fe055c740f53430e0057d7163b85096b80`.
- Five harness files byte-identical to immutable source; no implementation files changed.
- Private raw evidence: `/home/corp/autodata-evidence/pg17-runner-prep-20261104`; source archive, adoption hashes, tracking readbacks and exact preflight retained there.

| Harness path | SHA256 |
| --- | --- |
| `infra/deploy/gce/schema_probe.py` | `daa4a065058e568aa2b4199f10b75c471999906be1625c36c7a9bd78a9d137ae` |
| `infra/deploy/gce/test_schema_probe.py` | `c3570baab472635a0da1879beb4b229b3545f490e1cbd21a30f08cce23a02c10` |
| `infra/deploy/gce/test_schema_probe_pg17.py` | `08d59affa36835e2efcdc2905a03af712ee7a618ace16cd6d787535dcfcd8ceb` |
| `infra/deploy/gce/testdata/schema_probe_sentinel.c` | `a4dd46d294c25181c3fd0258cf4e17359d718539804aceaa61ea7e01b2a61fd4` |
| `infra/deploy/gce/testdata/schema_probe_fixtures.sql` | `4ba91d534ac3653148c5289d02f0de6fd0623d0941351a6ad04fe20b6d5bfcec` |

Runner image/APK/build/toolchain identities: unexecuted. Production schema/services/runtime_evidence/production_ready/deployment_authorized remain false.
