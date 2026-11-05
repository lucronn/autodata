# One real runtime trial after disabled startup compatibility

Status: code independently approved and integrated; this trial is synchronized for a fresh committed-base preflight before execution.

Issue: https://github.com/lucronn/autodata/issues/186  
Project: https://github.com/users/lucronn/projects/8

This is the single coordinator trial already specified by the independently reviewed [disabled startup amendment](2026-11-03-runtime-disabled-notification.md). Candidate `0da3c88b2e8aeca8b04a37bf3f6c80cab2550f8f` changes only the adapter, its tests and runner documentation. It requires one source-shaped disabled startup snapshot before discovery. Its exact 137-test runs passed for the builder, independent reviewer and coordinator (28.362s, 28.338s and28.258s). The reviewer also passed44 adversarial checks and retained causality/root-binding attacks, with no findings. It is integrated at f4cc249e2ba6619673183a47889558bb5cd087d7 with identical scripts/autonomy bytes. No new implementation or packaging change is authorized by this trial.

## Concrete todo

- [ ] Obtain independent exact-candidate approval and coordinator verification of 0da3c88; integrate unchanged and retain all previous failed trials.
- [ ] Synchronize this one-trial plan, Issue186, Project8 and canonical evidence; commit a fresh checkpoint and pass its machine preflight.
- [ ] Verify the unchanged supervisor hash and existing nonroot bubblewrap image/CLI, then execute exactly one bounded success trial in a fresh owned clone.
- [ ] Retain actual protocol, profile, role/check, outcome and cleanup evidence; independently replay at the original root before any runtime success claim.
- [ ] Record success or the actual next failure without retries or fallback; interrupted and genuine-unavailable cases remain separate requirements.

## Fixed inputs and boundary

Preserve previous failures, especially `/tmp/autodata-appserver-success-6qkf9mga` (missing bubblewrap) and `/tmp/autodata-appserver-success-x0bqiuyu` (official disabled startup notification), without editing or relabeling their outcomes. The second attempt sent no model/list, thread/start or turn/start.

Use the existing `/tmp/autodata-runtime-supervisor.py` unchanged, SHA256 `d8ed38f85bd835b051bfc9f8a8eae65ee80f14f0f4559b0a3b7f056750f18057`, and image `autodata-runtime-fixture:codex-0.162.1-nonroot-bwrap`, ID `sha256:3348a8a15a76e1fe91baae8a3d7ebe124979edbb2f0aeb142a66021848b469ca`. Debian bubblewrap is `0.8.0-2+deb12u1`; the mounted CLI must remain exactly `codex-cli 0.162.1`, source pin `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`. Verify actual nonsecret input identities before the trial. Any mismatch blocks; do not repair inputs under this record.

Retain the existing UID1000/node execution, read-only root filesystem, cap-drop ALL, no-new-privileges, no added capabilities/seccomp/privilege exceptions, private default home/tmp/evidence storage, read-only installed CLI and root-owned boundary proof, resource limits, no published ports or host sockets. Network metadata remains truthful standard Docker bridge with unrestricted outbound access. The only authentication delivery is the already authorized read-only Codex auth mount. Never inspect, print or copy authentication bytes. No GitHub, bank or production credential mounts/integrations. No HOME/CODEX_HOME override.

The requested profile is exactly `gpt-6.1-sol`, reasoning `medium`, service tier `priority` (Fast), `features.fast_mode=true`, with no fallback. Unsupported profile, warnings, active remote control, malformed/repeated snapshots, approval requests and other unsupported events remain hard failures. Configured request/resolved profile evidence does not establish an unobserved upstream served or billed tier.

## Execution and acceptance

After integration, synchronize this record and commit it with canonical documents. Pin that exact checkpoint SHA, run `validate_record` against its committed record and documents, require no errors, and compare the candidate adapter/test bytes with the integrated checkpoint. A docs-only checkpoint must not silently change trusted runtime code.

Run exactly one invocation using subprocess argv:

```text
python3 /tmp/autodata-runtime-supervisor.py --approved-sha <fresh-checkpoint-sha> --trial success
```

Use the existing 120-second provider budget, 400-second outer trial budget and 425-second supervisor watchdog/owned-container cleanup. The supervisor creates a fresh clone and evidence root with no Git remotes, validates its actual clean SHA, verifies effective container mounts/namespace proof and invokes the trusted runner. Preserve the complete stdout/stderr, raw protocol, role/check assignments, candidate observations, metadata and exact outcome. No automatic retry or fixture substitution.

Success requires the full accepted workflow under the existing runtime contract: supported catalog, resolved exact profile, causally valid completed turns, correct assigned roles/checks, retained full evidence and independent replay at the original evidence root. Successful initialize, one completed turn or a provider exit0 alone is insufficient. Inspect actual method counts and distinguish pre-inference startup failure from later failures. If failure/timeout occurs, preserve all artifacts and stop this trial; any new remediation gets a separate reviewed checkpoint.

The coordinator records the actual outcome in canonical evidence and GitHub tracking. This single success-case attempt does not certify interrupted-provider or genuine-unavailable-profile behavior, application release gates, live bank integrations, identity or production readiness. No production deployment is authorized.

## Coordinator record

```json
{
  "goal": "Run one bounded real Codex app-server success trial after independent promotion of the disabled startup snapshot amendment, preserving exact execution settings and isolation.",
  "plan_ref": "docs/superpowers/plans/2026-11-03-runtime-disabled-notification-trial.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/agents/runner-interface.md",
    "docs/verification/2026-11-03-agent-evidence-hardening.md",
    "docs/superpowers/plans/2026-11-03-production-release-orchestration.md"
  ],
  "todo": [
    "Obtain independent exact-candidate approval and coordinator verification of 0da3c88; integrate unchanged and retain all previous failed trials.",
    "Synchronize this one-trial plan, Issue186, Project8 and canonical evidence; commit a fresh checkpoint and pass its machine preflight.",
    "Verify the unchanged supervisor hash and existing nonroot bubblewrap image/CLI, then execute exactly one bounded success trial in a fresh owned clone.",
    "Retain actual protocol, profile, role/check, outcome and cleanup evidence; independently replay at the original root before any runtime success claim.",
    "Record success or the actual next failure without retries or fallback; interrupted and genuine-unavailable cases remain separate requirements."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-03T11:30:36.636100+00:00"
}
```
